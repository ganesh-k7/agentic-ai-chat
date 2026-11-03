"""FastAPI backend: streams agent runs as Server-Sent Events.

    uv run uvicorn api.main:app --reload

Endpoints
    GET  /health
    POST /chat/stream            {"thread_id": "...", "message": "..."}
                                 {"thread_id": "...", "resume": "yes" | "no, because..."}
    GET  /threads/{thread_id}    conversation history + any pending approval

Every SSE event is `data: {"type": ..., ...}` where type is one of:
    token | tool_call | tool_result | interrupt | done | error
"""
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel

from agent.config import settings
from agent.graph import build_graph
from agent.llm import content_to_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    db = str(settings.data_dir / "checkpoints.sqlite")
    async with AsyncSqliteSaver.from_conn_string(db) as saver:
        app.state.graph = build_graph(checkpointer=saver)
        yield


app = FastAPI(title="Agentic Starter", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatRequest(BaseModel):
    thread_id: str
    message: str | None = None
    resume: str | None = None   # answer to a pending interrupt (approval)


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


async def run_stream(graph, graph_input, config) -> AsyncIterator[str]:
    try:
        async for mode, chunk in graph.astream(
            graph_input, config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                # LLM tokens as they are generated
                msg, meta = chunk
                if meta.get("langgraph_node") == "agent" and isinstance(msg, AIMessageChunk):
                    text = content_to_text(msg.content)
                    if text:
                        yield sse({"type": "token", "text": text})

            elif mode == "updates":
                # One update per finished node
                for node, update in chunk.items():
                    if node == "__interrupt__":
                        for intr in update:
                            yield sse({"type": "interrupt", "value": intr.value})
                        continue
                    for m in (update or {}).get("messages", []):
                        if node == "agent":
                            for tc in getattr(m, "tool_calls", None) or []:
                                yield sse({"type": "tool_call", "name": tc["name"],
                                           "args": tc["args"]})
                        elif node == "tools":
                            yield sse({"type": "tool_result", "name": getattr(m, "name", ""),
                                       "content": content_to_text(m.content)[:2000]})
        yield sse({"type": "done"})
    except Exception as e:  # surface errors to the client instead of a dead stream
        yield sse({"type": "error", "message": f"{type(e).__name__}: {e}"})


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/docs")   # interactive API docs; the chat UI is on :8501


@app.get("/health")
async def health():
    model = {
        "ollama": settings.ollama_model,
        "gemini": settings.gemini_model,
        "openai_compat": settings.openai_model,
    }[settings.llm_provider]
    return {"status": "ok", "provider": settings.llm_provider, "model": model}


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    if req.message is None and req.resume is None:
        raise HTTPException(400, "Provide `message` or `resume`.")
    config = {
        "configurable": {"thread_id": req.thread_id},
        "recursion_limit": settings.recursion_limit,
    }
    if req.resume is not None:
        graph_input = Command(resume=req.resume)
    else:
        graph_input = {"messages": [HumanMessage(req.message)]}
    return StreamingResponse(
        run_stream(app.state.graph, graph_input, config),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    state = await app.state.graph.aget_state({"configurable": {"thread_id": thread_id}})
    messages = []
    for m in state.values.get("messages", []) if state.values else []:
        text = content_to_text(m.content)
        if m.type in ("human", "ai") and text:
            messages.append({"role": "user" if m.type == "human" else "assistant",
                             "content": text})
    pending = [i.value for t in state.tasks for i in getattr(t, "interrupts", ())]
    return {"thread_id": thread_id, "messages": messages, "pending": pending}
