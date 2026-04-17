import anthropic
from typing import Iterator

client = anthropic.Anthropic()

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer questions clearly, help with tasks, "
    "write code, analyze information, and provide thoughtful responses. "
    "Be direct and concise."
)


def stream_response(messages: list[dict]) -> Iterator[str]:
    """Stream text response from Claude with prompt caching on the system prompt."""
    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=16000,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


def get_response(messages: list[dict]) -> str:
    """Return full response text (non-streaming)."""
    return "".join(stream_response(messages))
