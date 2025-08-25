import asyncio
from typing import Any, Dict, List, Tuple, Union

def extract_prompt_and_history(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    *,
    include_system: bool = True,
    include_tool_messages: bool = False,
) -> Tuple[str, List[Dict[str, str]]]:
    """
    Accepts either:
      - a dict with key "messages": [...], or
      - directly a list of messages.
    Returns (prompt, history) where:
      - prompt  = text of the LAST user message
      - history = all prior messages as [{'role','content'}], optionally filtered.

    Args:
        data: dict or list. If dict, uses data['messages']; if list, assumes it's the messages list.
        include_system: include system/developer messages in history.
        include_tool_messages: include tool/function messages in history.

    Raises:
        ValueError if messages are missing/invalid or no user message exists.
    """

    # --- resolve messages source ---
    if isinstance(data, dict):
        if "messages" not in data or not isinstance(data["messages"], list):
            raise ValueError('Expected dict with key "messages" (list).')
        messages: List[Dict[str, Any]] = data["messages"]
    elif isinstance(data, list):
        messages = data  # assume it's already the messages list
    else:
        raise ValueError("Expected a dict with 'messages' or a list of messages.")

    def flatten_content(content: Any) -> str:
        """Convert string or list-of-parts (OpenAI content) to plain text."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for p in content:
                if isinstance(p, dict):
                    # typical shapes: {"type":"text","text":"..."} or {"text":"..."} or {"content":"..."}
                    if p.get("type") == "text" and "text" in p:
                        parts.append(str(p["text"]))
                    elif "text" in p:
                        parts.append(str(p["text"]))
                    elif "content" in p:
                        parts.append(str(p["content"]))
                elif isinstance(p, str):
                    parts.append(p)
            return "\n".join(parts).strip()
        return str(content)

    # --- find last user message (the prompt) ---
    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break
    if last_user_idx is None:
        raise ValueError("No user message found.")

    prompt = flatten_content(messages[last_user_idx].get("content", ""))

    # --- build history up to (excluding) last user message ---
    allowed_roles = {"user", "assistant"}
    if include_system:
        allowed_roles |= {"system", "developer"}
    if include_tool_messages:
        allowed_roles |= {"tool", "function"}

    history: List[Dict[str, str]] = []
    for m in messages[:last_user_idx]:
        role = m.get("role")
        if role in allowed_roles:
            text = flatten_content(m.get("content", ""))
            # Optionally drop empty system/dev messages
            if text or role not in {"system", "developer"}:
                history.append({"role": role, "content": text})

    return prompt, history


async def respond_async(agent, payload: Dict[str, Any]) -> Any:
    user_input, messages = extract_prompt_and_history( payload )
    result = await agent.run(user_input, message_history=messages)
    return result


def respond(agent, payload: Dict[str, Any]) -> Any:
    user_input, messages = extract_prompt_and_history( payload )

    try:
        return asyncio.run(agent.run(user_input, message_history=messages))
    except RuntimeError as e:
        if "running event loop" in str(e):
            loop = asyncio.get_event_loop()
            if loop.is_running():
                try:
                    import nest_asyncio  # optional convenience in notebooks
                    nest_asyncio.apply()
                    return loop.run_until_complete(agent.run(user_input, message_history=messages))
                except Exception as inner:
                    raise RuntimeError(
                        "respond_sync was called inside a running event loop. "
                        "Please use 'await respond(...)' instead."
                    ) from inner
            else:
                return loop.run_until_complete(agent.run(user_input, message_history=messages))
        raise