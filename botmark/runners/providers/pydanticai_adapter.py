from __future__ import annotations
from typing import Any, Dict, List, Optional
import importlib, inspect
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai import StructuredDict

from .. import RunResponse, ProviderAdapter
from ...utils.helpers import get_toolset
from ..converters.openai_pydantic import openai_to_pydantic_ai, pydantic_ai_to_openai

class PydanticAIAdapter(ProviderAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = dict(config or {})

    async def run(
        self,
        input_text: str,
        *,
        message_history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[Any] = None,
        **kwargs: Any,
    ) -> RunResponse:
        custom_output_text = kwargs.pop("custom_output_text", None)
        
        model_def = kwargs.get("model", None)
        if model_def:
            model = get_llm_model( model_def )
        else:
            model = self.config.get("model", TestModel())

        if custom_output_text:
            model = TestModel(custom_output_text=custom_output_text) if custom_output_text else TestModel()

        # History konvertieren (OpenAI -> pydantic-ai)
        history_models = openai_to_pydantic_ai(message_history or [])

        # Tools adaptieren
        toolsets = get_toolset(tools) if tools is not None else None

        # Agent bauen
        agent = Agent(
            model=model,
            system_prompt=system_prompt or self.config.get("system_prompt", ""),
        )

        run_kwargs: Dict[str, Any] = {}
        if toolsets is not None:
            run_kwargs["toolsets"] = toolsets
        if history_models:
            run_kwargs["message_history"] = history_models
        if "output_type" in kwargs:
            run_kwargs["output_type"] = StructuredDict( kwargs["output_type"] ) if isinstance(kwargs["output_type"], dict) else kwargs["output_type"]

        res = await agent.run(input_text, **run_kwargs)
        oa_messages = pydantic_ai_to_openai(res.all_messages())

        return RunResponse(
            output=res.output,
            all_messages=oa_messages,
        )

def factory(config: Optional[Dict[str, Any]] = None) -> ProviderAdapter:
    return PydanticAIAdapter(config or {})

def get_llm_model(model_data):

    def instantiate_filtered(model_cls, model_data: dict, provider_instance=None):
        sig = inspect.signature(model_cls)          # uses __init__ under the hood
        params = sig.parameters
        accepts_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

        # keep only kwargs that __init__ accepts (unless it has **kwargs)
        if accepts_varkw:
            kwargs = dict(model_data)
        else:
            kwargs = {k: v for k, v in model_data.items() if k in params and k != "self"}

        # add provider only if accepted (or **kwargs present)
        if provider_instance is not None and (accepts_varkw or "provider" in params):
            kwargs["provider"] = provider_instance
        
        return model_cls(**kwargs)

    if isinstance (model_data, dict ):
        provider_data = model_data.pop("provider", None)  # Extract nested provider

        # --- Load Provider ---
        provider_instance = None
        if provider_data:
            provider_data = dict(provider_data)
            provider_type_path = provider_data.pop("type", "openai.OpenAIProvider")
            provider_module_path, provider_class_name = provider_type_path.rsplit(".", 1)
            full_provider_module = f"pydantic_ai.providers.{provider_module_path}"
            provider_module = importlib.import_module(full_provider_module)
            provider_cls = getattr(provider_module, provider_class_name)
            provider_instance = provider_cls(**provider_data)

        # --- Load Model ---
        model_type_path = model_data.get("type", "test.TestModel")
        model_module_path, model_class_name = model_type_path.rsplit(".", 1)
        full_model_module = f"pydantic_ai.models.{model_module_path}"
        model_module = importlib.import_module(full_model_module)
        model_cls = getattr(model_module, model_class_name)

        return instantiate_filtered(model_cls, model_data, provider_instance)

    elif isinstance (model_data, str ):
        from pydantic_ai.models.openai import OpenAIResponsesModel
        return OpenAIResponsesModel( model_name = model_data )
    else:
        return TestModel()
