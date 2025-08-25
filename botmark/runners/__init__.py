from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, List
from ..utils.helpers import get_toolset

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_core import to_jsonable_python
from pydantic_ai.messages import ModelMessagesTypeAdapter

# Runner liefert jetzt ein beliebiges Result-Objekt, nicht nur str
Runner = Callable[..., Awaitable[Any]]

class RunResponse:

    def __init__(self, all_messages: List[Any], output: Any) -> None:
        self.all_messages = all_messages
        self.output = output

def create_ai_runner(provider: str = "pydanticai", config: Optional[Dict[str, Any]] = None) -> Runner:
    
    if provider.lower() != "pydanticai":
        async def unsupported(*_: Any, **__: Any) -> Any:
            raise NotImplementedError(f"Unsupported provider '{provider}'")
        return unsupported

    defaults: Dict[str, Any] = dict(config or {})

    AGENT_KEYS = {"system_prompt", "tools"}
    RUN_KEYS = {"output_type", "toolsets"}

    async def run(input_text: str, **kwargs: Any) -> Any:
        merged = {**defaults, **kwargs}
        #model = merged.pop("model", TestModel())
        model = TestModel()

        history = kwargs.get("message_history", None )

        if history:
            history = openai_to_pydantic_ai( history )

        custom_output_text = merged.pop("custom_output_text", None)
        if not custom_output_text is None:
            model = TestModel(custom_output_text= custom_output_text)

        # fix tool set hetet wie historey!!!
        tools = merged.pop("tools", None)
        if not tools is None:
            toolset = get_toolset( tools )
            merged["toolsets"] = toolset

        agent_kwargs = {k: merged.pop(k) for k in list(merged.keys()) if k in AGENT_KEYS}
        run_kwargs = {k: merged.pop(k) for k in list(merged.keys()) if k in RUN_KEYS} | {"message_history": history }

        agent = Agent(model=model, **agent_kwargs)
        
        res = await agent.run(input_text, **run_kwargs)

        return RunResponse( all_messages=to_jsonable_python( res.all_messages() ), output= res.output if isinstance( res.output, str) else res.output )

    return run


## converters
import json
import copy
import base64
from typing import Any, Dict, Iterable, List, Sequence, Union

# ---------------------------------------------------------------------------
# pydantic-ai message classes
# ---------------------------------------------------------------------------
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    UserPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    ImageUrl,
    AudioUrl,
    DocumentUrl,
    VideoUrl,
    BinaryContent,
)

# --- Pydantic v1/v2 compatibility helpers -----------------------------------
def _export_model_jsonable(m) -> dict:
    """
    Return a plain JSON-serializable dict from a pydantic model, on both
    Pydantic v1 and v2. IMPORTANT: export with *native* field names
    (no by_alias), so re-validation works across versions.
    """
    if hasattr(m, "model_dump_json"):  # v2
        return json.loads(m.model_dump_json(by_alias=False))
    if hasattr(m, "model_dump"):       # v2
        return m.model_dump(mode="json", by_alias=False)
    if hasattr(m, "json"):             # v1
        return json.loads(m.json(by_alias=False))
    if hasattr(m, "dict"):             # v1
        return m.dict(by_alias=False)
    return json.loads(json.dumps(m, default=lambda o: getattr(o, "__dict__", str(o))))

def _validate_with_model(cls, obj):
    """Validate dict -> model for a single concrete class (v1/v2 safe)."""
    if hasattr(cls, "model_validate"):   # v2
        return cls.model_validate(obj)
    if hasattr(cls, "parse_obj"):        # v1
        return cls.parse_obj(obj)
    return cls(**obj)

def _validate_model_message(obj) -> ModelMessage:
    """
    Validate a pydantic-ai JSON dict into a ModelMessage.
    Try ModelRequest, then ModelResponse (Union-safe on v1/v2).
    """
    try:
        return _validate_with_model(ModelRequest, obj)
    except Exception:
        pass
    try:
        return _validate_with_model(ModelResponse, obj)
    except Exception as e:
        raise ValueError(f"Could not validate JSON as ModelRequest or ModelResponse: {e}\nObject: {obj}")

# =============================================================================
# Converter: OpenAI -> pydantic-ai (model instances)
# =============================================================================

def _oa_content_to_user_parts(content: Any) -> Union[str, Sequence[Any]]:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[Any] = []
        for item in content:
            if not isinstance(item, dict) or "type" not in item:
                parts.append(str(item))
                continue
            t = item["type"]
            if t in ("text", "input_text"):
                parts.append(item.get("text", ""))
            elif t in ("image_url", "input_image"):
                url_info = item.get("image_url") or {}
                url = url_info.get("url") or item.get("url") or ""
                parts.append(ImageUrl(url=url))
            elif t in ("audio_url",):
                url_info = item.get("audio_url") or {}
                url = url_info.get("url") or ""
                parts.append(AudioUrl(url=url))
            elif t in ("video_url",):
                url_info = item.get("video_url") or {}
                url = url_info.get("url") or ""
                parts.append(VideoUrl(url=url))
            elif t == "file_url":
                url_info = item.get("file_url") or {}
                url = url_info.get("url") or ""
                parts.append(DocumentUrl(url=url))
            elif t in ("input_audio",):
                audio_b64 = item.get("audio") or item.get("data")
                if audio_b64:
                    audio_bytes: bytes
                    if isinstance(audio_b64, str):
                        try:
                            audio_bytes = base64.b64decode(audio_b64, validate=False)
                        except Exception:
                            audio_bytes = audio_b64.encode()
                    else:
                        audio_bytes = audio_b64
                    parts.append(BinaryContent(data=audio_bytes, media_type="audio/wav"))
            else:
                parts.append(str(item))
        return parts
    return str(content)


def _assistant_content_to_response_parts(assistant_msg: Dict[str, Any]) -> List[Any]:
    parts: List[Any] = []
    content = assistant_msg.get("content")
    if isinstance(content, str) and content.strip():
        parts.append(TextPart(content=content))
    elif isinstance(content, list):
        text_chunks: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_chunks.append(item.get("text", ""))
        if text_chunks:
            parts.append(TextPart(content="\n".join(text_chunks)))
    for tc in assistant_msg.get("tool_calls", []) or []:
        fn = (tc.get("function") or {})
        tool_name = fn.get("name") or tc.get("type") or "tool"
        args = fn.get("arguments")
        try:
            parsed_args = json.loads(args) if isinstance(args, str) else (args or {})
        except Exception:
            parsed_args = {"_raw": args}
        parts.append(ToolCallPart(tool_name=tool_name, args=parsed_args, tool_call_id=tc.get("id") or ""))
    return parts


def openai_to_pydantic_ai(openai_messages: Iterable[Dict[str, Any]]) -> List[ModelMessage]:
    history: List[ModelMessage] = []
    tool_id_to_name: Dict[str, str] = {}
    for msg in openai_messages:
        role = msg.get("role")
        if role == "assistant":
            for tc in msg.get("tool_calls", []) or []:
                fn = (tc.get("function") or {})
                tool_id = tc.get("id") or ""
                tool_name = fn.get("name") or tc.get("type") or "tool"
                if tool_id:
                    tool_id_to_name[tool_id] = tool_name
        if role == "system":
            history.append(ModelRequest(parts=[SystemPromptPart(content=str(msg.get("content") or ""))]))
        elif role == "user":
            parts = _oa_content_to_user_parts(msg.get("content"))
            history.append(ModelRequest(parts=[UserPromptPart(content=parts)]))
        elif role == "assistant":
            response_parts = _assistant_content_to_response_parts(msg) or [TextPart(content="")]
            history.append(ModelResponse(parts=response_parts))
        elif role == "tool":
            tool_call_id = msg.get("tool_call_id") or ""
            tool_name = tool_id_to_name.get(tool_call_id, "tool")
            content = msg.get("content")
            if isinstance(content, (dict, list)):
                return_content: Any = content
            else:
                try:
                    return_content = json.loads(content) if isinstance(content, str) else str(content)
                except Exception:
                    return_content = str(content) if content is not None else ""
            history.append(ModelRequest(parts=[ToolReturnPart(tool_name=tool_name, content=return_content, tool_call_id=tool_call_id)]))
        else:
            history.append(ModelRequest(parts=[UserPromptPart(content=str(msg))]))
    return history


# =============================================================================
# Converter: pydantic-ai (model instances) -> OpenAI
# =============================================================================

def _user_part_to_oa_content(part_content: Union[str, Sequence[Any]]) -> Union[str, List[Dict[str, Any]]]:
    if isinstance(part_content, str):
        return part_content
    blocks: List[Dict[str, Any]] = []
    for p in part_content:
        if isinstance(p, str):
            blocks.append({"type": "text", "text": p})
        elif isinstance(p, ImageUrl):
            blocks.append({"type": "image_url", "image_url": {"url": p.url}})
        elif isinstance(p, AudioUrl):
            blocks.append({"type": "file_url", "file_url": {"url": p.url}})
        elif isinstance(p, VideoUrl):
            blocks.append({"type": "file_url", "file_url": {"url": p.url}})
        elif isinstance(p, DocumentUrl):
            blocks.append({"type": "file_url", "file_url": {"url": p.url}})
        elif isinstance(p, BinaryContent):
            blocks.append({"type": "text", "text": f"[binary:{p.media_type}:{len(p.data or b'')} bytes]"})
        else:
            blocks.append({"type": "text", "text": str(p)})
    return blocks if blocks else ""


def pydantic_ai_to_openai(history: Iterable[ModelMessage]) -> List[Dict[str, Any]]:
    oa_messages: List[Dict[str, Any]] = []
    def _emit(msg: Dict[str, Any]) -> None:
        if not msg.get("content") and not msg.get("tool_calls"):
            msg["content"] = ""
        oa_messages.append(msg)
    for m in history:
        if isinstance(m, ModelRequest):
            for part in m.parts:
                if isinstance(part, SystemPromptPart):
                    _emit({"role": "system", "content": part.content or ""})
                elif isinstance(part, UserPromptPart):
                    _emit({"role": "user", "content": _user_part_to_oa_content(part.content)})
                elif isinstance(part, ToolReturnPart):
                    content = part.content
                    if isinstance(content, (dict, list)):
                        content_str = json.dumps(content, ensure_ascii=False)
                    else:
                        content_str = str(content) if content is not None else ""
                    _emit({"role": "tool", "tool_call_id": part.tool_call_id or "", "content": content_str})
        elif isinstance(m, ModelResponse):
            text_chunks: List[str] = []
            tool_calls: List[Dict[str, Any]] = []
            for part in m.parts:
                if isinstance(part, TextPart):
                    text_chunks.append(part.content or "")
                elif isinstance(part, ToolCallPart):
                    args = part.args if isinstance(part.args, (dict, list)) else {"_raw": part.args}
                    tool_calls.append({
                        "id": part.tool_call_id or "",
                        "type": "function",
                        "function": {"name": part.tool_name or "tool", "arguments": json.dumps(args, ensure_ascii=False)},
                    })
            msg: Dict[str, Any] = {"role": "assistant"}
            if text_chunks:
                msg["content"] = "\n".join([t for t in text_chunks if t is not None])
            if tool_calls:
                msg["tool_calls"] = tool_calls
            _emit(msg)
    return oa_messages

# =============================================================================
# JSON-facing helpers
# =============================================================================

def openai_to_pydanticai_json(openai_messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build pydantic-ai ModelMessage list, then export as JSON-serializable dicts (v1/v2-safe, NO aliases)."""
    history = openai_to_pydantic_ai(openai_messages)
    return [_export_model_jsonable(m) for m in history]


def pydanticai_json_to_openai(history_json: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate JSON dicts back into models, then convert to OpenAI messages."""
    history_models: List[ModelMessage] = [_validate_model_message(obj) for obj in history_json]
    return pydantic_ai_to_openai(history_models)

# =============================================================================
# Canonicalization helpers (semantic comparison)
# =============================================================================

def _try_parse_json(value):
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value

def _normalize_user_content_blocks(blocks: Any) -> Any:
    if not isinstance(blocks, list):
        return blocks
    norm = []
    for b in blocks:
        if not isinstance(b, dict) or "type" not in b:
            norm.append(b)
            continue
        t = b.get("type")
        if t in ("audio_url", "video_url"):
            inner = b.get("audio_url") or b.get("video_url") or {}
            url = (inner or {}).get("url") or ""
            norm.append({"type": "file_url", "file_url": {"url": url}})
        elif t == "image_url":
            u = (b.get("image_url") or {}).get("url") or ""
            norm.append({"type": "image_url", "image_url": {"url": u}})
        elif t == "file_url":
            u = (b.get("file_url") or {}).get("url") or ""
            norm.append({"type": "file_url", "file_url": {"url": u}})
        else:
            norm.append(b)
    return norm

def _strip_empty_content(msg: Dict[str, Any]) -> Dict[str, Any]:
    if "content" in msg:
        c = msg.get("content")
        if isinstance(c, str) and c.strip() == "":
            msg = {k: v for k, v in msg.items() if k != "content"}
    return msg

def _canonicalize_messages(messages):
    canon = []
    for m in messages:
        m2 = copy.deepcopy(m)

        if m2.get("role") == "assistant" and "tool_calls" in m2 and m2["tool_calls"]:
            for tc in m2["tool_calls"]:
                fn = tc.get("function") or {}
                args = fn.get("arguments")
                fn["arguments"] = _try_parse_json(args)
                tc["function"] = fn

        if m2.get("role") == "tool":
            m2["content"] = _try_parse_json(m2.get("content"))

        if m2.get("role") == "user" and isinstance(m2.get("content"), list):
            m2["content"] = _normalize_user_content_blocks(m2["content"])

        m2 = _strip_empty_content(m2)

        def sort_dict(obj):
            if isinstance(obj, dict):
                return {k: sort_dict(obj[k]) for k in sorted(obj.keys())}
            if isinstance(obj, list):
                return [sort_dict(x) for x in obj]
            return obj

        canon.append(sort_dict(m2))
    return canon

def _json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
