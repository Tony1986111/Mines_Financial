from __future__ import annotations

import json
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Command
from psycopg import Connection as PgConnection, sql as pg_sql
from psycopg.rows import dict_row as pg_dict_row
from pydantic import BaseModel

load_dotenv(override=True)

app = FastAPI(title="ASX Mining Financial Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mines.melailab.com",  
        "http://localhost:3000",        
        "http://localhost:3001",    
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory="assets"), name="assets")

from graph import graph  # noqa: E402 — import after load_dotenv
from db.progress import delete_progress, get_progress, save_progress, setup_progress_table

try:
    setup_progress_table()
except Exception as _e:
    print(f"[startup] graph_progress table setup failed: {_e}", flush=True)


# ── Request / Response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    thread_id: str
    message: str
    resume: bool = False  # True when the user is answering a clarification question


class ChatResponse(BaseModel):
    thread_id: str
    answer: str
    interrupted: bool
    clarification_question: str | None = None


class GraphMermaidResponse(BaseModel):
    diagram: str


class ProgressSaveRequest(BaseModel):
    turn_index: int
    cards: list


# ── Helpers ────────────────────────────────────────────────────────────────────

def _check_interrupt(config: dict) -> str | None:
    state = graph.get_state(config)
    for task in state.tasks:
        for intr in task.interrupts:
            return intr.value.get("question", "Please clarify your question.")
    return None


def _serialize_state(state: dict) -> dict:
    """Convert a LangGraph state dict to a JSON-serializable dict."""
    result = {}
    for k, v in state.items():
        if isinstance(v, list) and v and isinstance(v[0], BaseMessage):
            result[k] = [
                {"type": m.__class__.__name__, "content": str(m.content)[:2000]}
                for m in v
            ]
        elif isinstance(v, BaseMessage):
            result[k] = {"type": v.__class__.__name__, "content": str(v.content)[:2000]}
        else:
            try:
                json.dumps(v)
                result[k] = v
            except (TypeError, ValueError):
                result[k] = str(v)
    return result


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/api/threads")
def create_thread() -> dict:
    return {"thread_id": str(uuid.uuid4())}


@app.get("/api/threads")
def list_threads() -> list[dict]:
    """Return all threads ordered by most-recently-updated (max 30)."""
    db_url = os.getenv("DATABASE_URL", "")

    with PgConnection.connect(
        db_url, autocommit=True, prepare_threshold=0, row_factory=pg_dict_row
    ) as qconn:
        with qconn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns = ''"
            )
            thread_ids = [row["thread_id"] for row in cur.fetchall()]

    result = []
    for tid in thread_ids:
        try:
            snap = graph.get_state({"configurable": {"thread_id": tid}})
        except Exception:
            continue
        if not snap or not snap.values:
            continue
        msgs = snap.values.get("messages", [])
        first_human = next(
            (m.content for m in msgs if m.__class__.__name__ == "HumanMessage"),
            None,
        )
        if first_human is None:
            continue
        result.append({
            "id": tid,
            "label": str(first_human)[:80],
            "updated_at": snap.created_at,  # ISO-8601 string or None
        })

    result.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return result[:30]


@app.get("/api/threads/{thread_id}/history")
def get_thread_history(thread_id: str) -> list[dict]:
    """Reconstruct conversation history for a thread from its LangGraph checkpoint."""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snap = graph.get_state(config)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not snap or not snap.values:
        return []
    msgs = snap.values.get("messages", [])
    result = []
    for m in msgs:
        name = m.__class__.__name__
        if name == "HumanMessage":
            result.append({"role": "user", "content": str(m.content)})
        elif name == "AIMessage":
            result.append({"role": "assistant", "content": str(m.content)})
    return result


@app.delete("/api/threads/{thread_id}")
def delete_thread(thread_id: str) -> dict:
    """Delete all checkpoint data for a thread from PostgreSQL."""
    db_url = os.getenv("DATABASE_URL", "")
    tables = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")
    with PgConnection.connect(
        db_url, autocommit=True, prepare_threshold=0, row_factory=pg_dict_row
    ) as qconn:
        with qconn.cursor() as cur:
            for table in tables:
                try:
                    cur.execute(
                        pg_sql.SQL("DELETE FROM {} WHERE thread_id = %s").format(
                            pg_sql.Identifier(table)
                        ),
                        (thread_id,),
                    )
                except Exception:
                    pass  # table may not exist in this schema version
    delete_progress(thread_id)
    return {"deleted": thread_id}


@app.post("/api/threads/{thread_id}/progress")
def save_thread_progress(thread_id: str, req: ProgressSaveRequest) -> dict:
    save_progress(thread_id, req.turn_index, req.cards)
    return {"ok": True}


@app.get("/api/threads/{thread_id}/progress")
def get_thread_progress(thread_id: str) -> list[dict]:
    return get_progress(thread_id)


@app.get("/api/memory/conclusions")
def list_conclusions() -> list[dict]:
    """Return all semantic memory entries (conclusions collection)."""
    from memory.semantic import _get_vectorstore
    vs = _get_vectorstore()
    res = vs._collection.get(include=["documents", "metadatas"])
    items = []
    for cid, doc, meta in zip(res["ids"], res["documents"], res["metadatas"]):
        items.append({
            "id": cid,
            "query": doc,
            "answer": meta.get("answer", ""),
            "companies": meta.get("companies", ""),
            "fy": meta.get("fy", ""),
        })
    items.sort(key=lambda x: x["query"])
    return items


class ConclusionUpdateRequest(BaseModel):
    answer: str


@app.put("/api/memory/conclusions/{conclusion_id}")
def update_conclusion(conclusion_id: str, req: ConclusionUpdateRequest) -> dict:
    """Update the answer text of a conclusion, keeping the existing embedding."""
    from memory.semantic import _get_vectorstore
    vs = _get_vectorstore()
    existing = vs._collection.get(
        ids=[conclusion_id],
        include=["documents", "metadatas", "embeddings"]
    )
    if not existing["ids"]:
        raise HTTPException(status_code=404, detail="Conclusion not found")
    meta = existing["metadatas"][0].copy()
    meta["answer"] = req.answer
    vs._collection.update(
        ids=[conclusion_id],
        documents=existing["documents"],
        metadatas=[meta],
        embeddings=existing["embeddings"],
    )
    return {"updated": conclusion_id}


@app.delete("/api/memory/conclusions/{conclusion_id}")
def delete_conclusion(conclusion_id: str) -> dict:
    """Delete a single conclusion entry from semantic memory."""
    from memory.semantic import _get_vectorstore
    vs = _get_vectorstore()
    vs._collection.delete(ids=[conclusion_id])
    return {"deleted": conclusion_id}


@app.get("/api/graph/mermaid")
def get_graph_mermaid() -> GraphMermaidResponse:
    """Return the static LangGraph workflow as Mermaid source."""
    try:
        return GraphMermaidResponse(diagram=graph.get_graph().draw_mermaid())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
def chat(req: ChatRequest) -> ChatResponse:
    config = {"configurable": {"thread_id": req.thread_id}}

    try:
        if req.resume:
            result = graph.invoke(Command(resume=req.message), config=config)
        else:
            result = graph.invoke(
                {"messages": [HumanMessage(content=req.message)], "query": req.message},
                config=config,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    interrupt_q = _check_interrupt(config)
    if interrupt_q:
        return ChatResponse(
            thread_id=req.thread_id,
            answer="",
            interrupted=True,
            clarification_question=interrupt_q,
        )

    return ChatResponse(
        thread_id=req.thread_id,
        answer=result.get("final_answer", ""),
        interrupted=False,
    )


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    """SSE endpoint — streams graph node progress to the frontend.

    Uses the sync graph.stream() because PostgresSaver only implements sync
    checkpoint methods. Starlette wraps sync generators via iterate_in_threadpool.
    """
    print(f"[chat_stream] received request: thread_id={req.thread_id}, resume={req.resume}, msg={req.message[:60]!r}", flush=True)
    config = {"configurable": {"thread_id": req.thread_id}}

    def generate():
        print("[generate] generator started", flush=True)
        try:
            stream_input: dict | Command
            if req.resume:
                stream_input = Command(resume=req.message)
            else:
                stream_input = {
                    "messages": [HumanMessage(content=req.message)],
                    "query": req.message,
                }

            pending_node: str | None = None

            for chunk in graph.stream(
                stream_input, config, stream_mode=["updates", "values"]
            ):
                mode, data = chunk
                if mode == "updates":
                    node_name = next(iter(data))
                    pending_node = node_name
                    yield _sse({"type": "node_start", "node": node_name})
                elif mode == "values" and pending_node is not None:
                    yield _sse({
                        "type": "node_done",
                        "node": pending_node,
                        "state": _serialize_state(data),
                    })
                    pending_node = None

            # After stream: check for interrupt or emit final answer
            state = graph.get_state(config)
            interrupt_q: str | None = None
            for task in state.tasks:
                for intr in task.interrupts:
                    interrupt_q = intr.value.get("question", "Please clarify your question.")
                    break

            if interrupt_q:
                yield _sse({"type": "interrupt", "question": interrupt_q})
            else:
                answer     = state.values.get("final_answer", "")
                chart_data = state.values.get("chart_data", [])
                sources    = state.values.get("sources", [])
                confidence = state.values.get("confidence", "")
                yield _sse({"type": "done", "answer": answer, "chart_data": chart_data, "sources": sources, "confidence": confidence})

        except Exception as e:
            import traceback
            print(f"[stream] EXCEPTION: {e}\n{traceback.format_exc()}", flush=True)
            yield _sse({"type": "error", "detail": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
