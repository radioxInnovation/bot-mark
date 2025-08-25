from __future__ import annotations
import inspect
from typing import Any, Dict, List, Optional, Union
from .. import RunResponse, ProviderAdapter

# The OpenAI Agents SDK (pip install openai-agents)
try:
    from agents import Agent as OAAgent, Runner as OARunner
except Exception as e:
    raise ImportError(
        "The OpenAI Agents SDK is required for the 'openai-agents' provider. "
        "Install with: pip install openai-agents"
    ) from e


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
