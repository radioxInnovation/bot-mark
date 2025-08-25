from __future__ import annotations
import inspect
from typing import Any, Dict, List, Optional, Union
from .. import RunResponse, ProviderAdapter

# The OpenAI Agents SDK (pip install openai-agents)
try:
    from agents import Agent as OAAgent, Runner as OARunner
    from agents import RunConfig
    from agents.agent_output import AgentOutputSchemaBase
    from agents.exceptions import ModelBehaviorError
    from jsonschema import Draft202012Validator
    import json

except Exception as e:
    raise ImportError(
        "The OpenAI Agents SDK is required for the 'openai-agents' provider. "
        "Install with: pip install openai-agents"
    ) from e



class JsonSchemaOutput(AgentOutputSchemaBase):
    """
    Übergibt dem Agents SDK ein JSON-Schema + Validierung.
    Das SDK nutzt is_strict_json_schema/json_schema() für Structured Outputs
    und ruft validate_json(...) auf, um die Modellantwort zu prüfen.
    """

    def __init__(self, name: str, schema: Dict[str, Any], strict: bool = True):
        self._name = name
        self._schema = schema
        self._strict = strict
        self._validator = Draft202012Validator(schema)

    # --- geforderte Methoden ---
    def is_plain_text(self) -> bool:
        return False  # wir erwarten JSON-Objekte (kein Plain-Text)

    def name(self) -> str:
        return self._name

    def json_schema(self) -> Dict[str, Any]:
        return self._schema

    def is_strict_json_schema(self) -> bool:
        # True: SDK nutzt Strict Structured Outputs (Schema muss den strikten Regeln entsprechen)
        return self._strict

    def validate_json(self, json_str: str) -> Any:
        try:
            obj = json.loads(json_str)
        except Exception as e:
            raise ModelBehaviorError(f"Model did not return JSON: {e}")
        errs = list(self._validator.iter_errors(obj))
        if errs:
            raise ModelBehaviorError(f"JSON did not match schema: {errs[0].message}")
        return obj  # validiertes dict

class OpenAIAgentsAdapter(ProviderAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = dict(config or {})

    async def run(
        self,
        input_text: str,
        *,
        message_history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = "",
        tools: Optional[Any] = None,
        **kwargs: Any,
    ) -> RunResponse:
        # ---- Fast path: final answer provided --------------------------------
        custom_output_text = kwargs.pop("custom_output_text", None)
        if custom_output_text is not None:
            mh = message_history or []
            filtered_hist = [m for m in mh if isinstance(m, dict) and m.get("role") != "system"]
            all_messages: List[Dict[str, Any]] = []
            all_messages.extend(filtered_hist)
            all_messages.append({"role": "user", "content": input_text})
            all_messages.append({"role": "assistant", "content": custom_output_text})
            return RunResponse(output=custom_output_text, all_messages=all_messages)

        # ---- Build Agent (handle model fallback) -----------------------------
        agent_name = self.config.get("name", "Assistant")
        instructions = (system_prompt or self.config.get("system_prompt") or "").strip()

        # pull possibly-problematic kwargs so they don't leak into Runner.run
        model_hint = kwargs.pop("model", None)   # avoid Runner.run(..., model=...)
        client = kwargs.pop("client", None)

        agent_kwargs: Dict[str, Any] = {"name": agent_name}
        if instructions:
            agent_kwargs["instructions"] = instructions
        if tools is not None:
            agent_kwargs["tools"] = tools

        # reflect Agent ctor
        agent_init_params = set(inspect.signature(OAAgent).parameters.keys())
        if client is not None and "client" in agent_init_params:
            agent_kwargs["client"] = client

        if model_hint is not None:
            if "model" in agent_init_params:
                agent_kwargs["model"] = model_hint
            else:
                # Fallback: annotate the instructions so the hint is preserved
                hint = f"(model: {model_hint})"
                agent_kwargs["instructions"] = (
                    f"{agent_kwargs.get('instructions','')}\n{hint}".strip()
                )

        output_type = kwargs.get( "output_type", None )
        if output_type:
            agent_kwargs["output_type"] = JsonSchemaOutput("Schema", output_type, strict=True)

        agent = OAAgent(**agent_kwargs)
        
        # ---- Prepare input ---------------------------------------------------
        mh = message_history or []
        if not isinstance(mh, list):
            raise TypeError("message_history must be a list of messages or None")

        filtered_hist = [m for m in mh if isinstance(m, dict) and m.get("role") != "system"]

        if filtered_hist:
            turn_input: Union[str, List[Dict[str, Any]]] = filtered_hist + [
                {"role": "user", "content": input_text}
            ]
        else:
            turn_input = input_text

        # keep only kwargs supported by Runner.run to avoid surprises
        runner_params = set(inspect.signature(OARunner.run).parameters.keys())
        run_kwargs = {k: v for k, v in kwargs.items() if k in runner_params}

        # ---- Execute ---------------------------------------------------------
        result = await OARunner.run(agent, turn_input, **run_kwargs)

        output = getattr(result, "final_output", None)
        if output is None:
            output = getattr(result, "output", None)
        if output is None:
            output = getattr(result, "text", None)
        if output is None:
            output = str(result)

        all_messages: List[Dict[str, Any]] = []
        all_messages.extend(filtered_hist)
        all_messages.append({"role": "user", "content": input_text})
        all_messages.append({"role": "assistant", "content": output})

        return RunResponse(output=output, all_messages=all_messages)


def factory(config: Optional[Dict[str, Any]] = None) -> OpenAIAgentsAdapter:
    return OpenAIAgentsAdapter(config or {})
