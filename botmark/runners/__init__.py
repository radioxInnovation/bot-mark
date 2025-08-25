from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol

Runner = Callable[..., Awaitable[Any]]

@dataclass
class RunResponse:
    output: Any
    all_messages: List[Dict[str, Any]]

OpenAIMessage = Dict[str, Any]

class ProviderAdapter(Protocol):
    async def run(
        self,
        input_text: str,
        *,
        message_history: Optional[List[OpenAIMessage]] = None,
        system_prompt: Optional[str] = "",
        tools: Optional[Any] = None,
        **kwargs: Any,
    ) -> RunResponse: ...

ProviderFactory = Callable[[Optional[Dict[str, Any]]], ProviderAdapter]
_REGISTRY: Dict[str, ProviderFactory] = {}

def register_provider(name: str, factory: ProviderFactory) -> None:
    _REGISTRY[name.lower()] = factory

def create_ai_runner(provider: str = "pydanticai", config: Optional[Dict[str, Any]] = None) -> Runner:
    name = provider.lower()
    if name not in _REGISTRY:
        async def unsupported(*_: Any, **__: Any) -> Any:
            raise NotImplementedError(f"Unsupported provider '{provider}'")
        return unsupported
    adapter = _REGISTRY[name](config or {})
    async def run(input_text: str, **kwargs: Any) -> Any:
        system_prompt = kwargs.pop("system_prompt", "")
        message_history = kwargs.pop("message_history", None)
        tools = kwargs.pop("tools", None)
        return await adapter.run(
            input_text,
            message_history=message_history,
            system_prompt=system_prompt,
            tools=tools,
            **kwargs,
        )
    return run

from .providers.pydanticai_adapter import factory as _pydanticai_factory
register_provider("pydanticai", _pydanticai_factory)

# Optional Aliase:
register_provider("pydantic-ai", _pydanticai_factory)
register_provider("pydantic_ai", _pydanticai_factory)
