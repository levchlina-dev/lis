import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent import stream_response, get_response

app = FastAPI(title="LIS Assistant API", version="1.0.0")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


def _to_api_messages(request: ChatRequest) -> list[dict]:
    messages = [m.model_dump() for m in request.messages]
    if not messages:
        raise HTTPException(status_code=422, detail="messages must not be empty")
    return messages


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest) -> dict:
    """Single-turn or multi-turn chat, returns full response."""
    messages = _to_api_messages(request)
    return {"response": get_response(messages)}


@app.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Streaming chat via Server-Sent Events."""
    messages = _to_api_messages(request)

    def generate():
        for chunk in stream_response(messages):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
