from typing import Tuple, Dict, Any, List
import asyncio
from pydantic_ai.messages import (
    ModelRequest, ModelResponse, TextPart, UserPromptPart, ImageUrl
)

def _prepare_messages_and_user_input(conversation_data: Dict[str, Any]) -> Tuple[List[Any], Any]:
    """
    Convert a dictionary of conversation data into:
      - messages: a list of ModelRequest/ModelResponse for history
      - user_input: the latest user input, either a str or a mixed list [str, ImageUrl, ...]
    """

    def add_user_prompt_to_message_history(messages: list, user_prompt: str, image_url: str | None = None):
        if user_prompt:
            parts = [UserPromptPart(content=user_prompt)]
            if image_url:
                parts.append(ImageUrl(url=image_url))
            messages.append(ModelRequest(parts=parts))

    def add_assistant_response_to_message_history(messages: list, assistant_response: str, image_url: str | None = None):
        if assistant_response:
            parts = [TextPart(content=assistant_response)]
            if image_url:
                parts.append(ImageUrl(url=image_url))
            messages.append(ModelResponse(parts=parts))

    messages: List[Any] = []   # history for model context
    user_prompt: List[Any] = []  # latest user input

    all_messages = conversation_data.get("messages", [])

    for i, entry in enumerate(all_messages):
        role = entry.get("role")
        content = entry.get("content")
        image_url = entry.get("image_url")

        if role == "user":
            is_last = i == len(all_messages) - 1
            if is_last and isinstance(content, str):
                # Latest user input; keep as a list to allow ImageUrl
                user_prompt = [content]
                if image_url:
                    user_prompt.append(ImageUrl(url=image_url))
            else:
                add_user_prompt_to_message_history(messages, content, image_url)

        elif role == "assistant":
            add_assistant_response_to_message_history(messages, content, image_url)

    # If the latest user input has only a single string, pass it as a plain str
    if len(user_prompt) == 1 and isinstance(user_prompt[0], str):
        return messages, user_prompt[0]
    return messages, user_prompt


async def respond_async(agent, payload: Dict[str, Any]) -> Any:
    messages, user_input = _prepare_messages_and_user_input(payload)
    result = await agent.run(user_input, message_history=messages)
    return result


def respond(agent, payload: Dict[str, Any]) -> Any:
    messages, user_input = _prepare_messages_and_user_input(payload)
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

# from typing import Tuple, Dict, Any
# from pydantic_ai.messages import ( ModelRequest, ModelResponse, TextPart, UserPromptPart, ImageUrl )

# def respond_to_json_pyload( agent, payload: dict ) -> str:

#     def process_conversation(conversation_data: Dict[str, Any]) -> Tuple[list, list]:
#         """
#         Converts a dictionary of conversation data into lists for further processing.
#         Returns the formatted messages and the latest user input.
#         """

#         # Helper function to add a user prompt to the message history
#         def add_user_prompt_to_message_history(messages: list, user_prompt: str, image_url: str = None ):

#             if user_prompt:
#                 parts = [(UserPromptPart(content=user_prompt))]
#                 if image_url:
#                     parts.append(ImageUrl(url=image_url))
#                 messages.append(ModelRequest(parts=parts))

#         # Helper function to add the assistant's response to the message history
#         def add_assistant_response_to_message_history(messages: list, assistant_response: str, image_url: str = None):
#             if assistant_response:
#                 parts = [TextPart(content=assistant_response)]
#                 if image_url:
#                     parts.append(ImageUrl(url=image_url))
#                 messages.append(ModelResponse(parts=parts))

#         messages = []       # List of past chat messages for model context
#         user_prompt = []    # Latest user input (last entry in conversation)

#         all_messages = conversation_data.get("messages", [])

#         for i, entry in enumerate(all_messages):
#             role = entry.get("role")
#             content = entry.get("content")
#             image_url = entry.get("image_url")

#             if role == "user":
#                 if i == len(all_messages) - 1 and isinstance(content, str):
#                     user_prompt =  [ content ]
#                     if image_url:
#                         user_prompt.append( ImageUrl(url=image_url))
#                 else:
#                     add_user_prompt_to_message_history(messages, content, image_url)

#             elif role == "assistant":
#                 add_assistant_response_to_message_history(messages, content, image_url)

#         return messages, user_prompt
    
#     # Process the conversation into history and current user input
#     messages, user_input = process_conversation( payload )

#     # Run the agent synchronously with the user input and conversation history
#     result = agent.run_sync( user_input, message_history = messages )
#     return result