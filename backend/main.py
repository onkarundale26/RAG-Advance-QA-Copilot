"""FastAPI app: chat (SSE), explore, health, ingest endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .ingest import ingest_jira, ingest_pdfs, ingest_playwright, ingest_selenium, ingest_testcases
from .lib import groq_client, prompts, qdrant_store, retriever, settings

logger = logging.getLogger(__name__)
_STREAM_DONE = object()

app = FastAPI(title="QA Copilot", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Turn(BaseModel):
    role: str = Field(..., description="user | assistant")
    content: str


class ChatRequest(BaseModel):
    question: str | None = None
    query: str | None = None
    history: list[Turn] = Field(default_factory=list)
    forced_collections: list[str] | None = None
    mode: str = Field("answer", description="answer | generate")
    temperature: float = 0.2


def _question(req: ChatRequest) -> str:
    text = (req.question or req.query or "").strip()
    if not text:
        raise HTTPException(400, "question is required")
    return text


@app.get("/api/health")
def health() -> dict:
    client = qdrant_store.get_client()
    collections = qdrant_store.all_counts(client)
    return {
        "ok": True,
        "status": "healthy",
        "groq_model": settings.GROQ_MODEL,
        "embed_model": settings.EMBED_MODEL,
        "rerank_model": settings.RERANK_MODEL,
        "qdrant": settings.QDRANT_URL or str(settings.QDRANT_PATH),
        "collections": collections,
        "counts": collections,
        "data_paths": {
            "selenium_repo": str(settings.SELENIUM_REPO_DIR),
            "playwright_repo": str(settings.PLAYWRIGHT_REPO_DIR),
            "testcases_csv": str(settings.TESTCASES_CSV),
            "pdfs_dir": str(settings.PDFS_DIR),
            "jira_md_dir": str(settings.JIRA_MD_DIR),
        },
    }


@app.post("/api/explore")
def explore(req: ChatRequest) -> dict:
    """Run pipeline + sync LLM call. Return full trace (no streaming)."""
    question = _question(req)
    t0 = time.time()
    trace = retriever.retrieve_with_trace(
        question,
        history=[t.model_dump() for t in req.history],
        forced_collections=req.forced_collections,
    )
    blocks = trace["context_blocks"]
    user_msg = retriever.build_user_message(trace["query"]["rewritten"], blocks)
    system = prompts.GENERATE_SYSTEM if req.mode == "generate" else prompts.ANSWER_SYSTEM

    t1 = time.time()
    res = groq_client.complete(
        messages=[
            {"role": "system", "content": system},
            *[
                {"role": t["role"], "content": t["content"]}
                for t in trace["query"]["history"][-settings.HISTORY_TURNS:]
            ],
            {"role": "user", "content": user_msg},
        ],
        temperature=req.temperature,
        max_tokens=1200,
    )
    trace["timings_ms"]["llm_ms"] = round((time.time() - t1) * 1000, 1)
    trace["timings_ms"]["total_ms"] = round((time.time() - t0) * 1000, 1)
    trace["llm"] = {
        "model": settings.GROQ_MODEL,
        "temperature": req.temperature,
        "system": system,
        "user": user_msg,
        "usage": res.get("usage", {}),
    }
    trace["answer"] = {"text": res["text"]}
    return trace


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """SSE streaming chat. Emits events: meta, sources, token, done."""
    question = _question(req)
    history = [t.model_dump() for t in req.history]

    async def event_stream():
        try:
            trace = await asyncio.to_thread(
                retriever.retrieve_with_trace,
                question,
                history,
                req.forced_collections,
            )
        except Exception as e:
            logger.exception("Chat retrieval failed")
            yield _sse("error", f"Retrieval failed: {e}")
            yield _sse("done", "")
            return

        blocks = trace["context_blocks"]
        user_msg = retriever.build_user_message(trace["query"]["rewritten"], blocks)
        system = prompts.GENERATE_SYSTEM if req.mode == "generate" else prompts.ANSWER_SYSTEM
        history_msgs = [
            {"role": t["role"], "content": t["content"]}
            for t in trace["query"]["history"][-settings.HISTORY_TURNS:]
        ]

        yield _sse("meta", {
            "rewritten": trace["query"]["rewritten"],
            "router": trace["router"],
            "timings_ms": trace["timings_ms"],
        })
        yield _sse("sources", [
            {
                "id": b["id"],
                "chunk_id": b["chunk_id"],
                "collection": b["collection"],
                "source": b["source"],
                "rerank_score": b.get("rerank_score"),
                "preview": (b["text"] or "")[:500],
                "payload": _safe_payload(b["payload"]),
            }
            for b in blocks
        ])
        try:
            iterator = groq_client.stream(
                messages=[
                    {"role": "system", "content": system},
                    *history_msgs,
                    {"role": "user", "content": user_msg},
                ],
                temperature=req.temperature,
                max_tokens=1200,
            )
            while True:
                piece = await asyncio.to_thread(_next_or_done, iterator)
                if piece is _STREAM_DONE:
                    break
                yield _sse("token", piece)
                await asyncio.sleep(0)
        except Exception as e:
            logger.exception("Chat streaming failed")
            yield _sse("error", str(e))
        yield _sse("done", "")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: Any) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _next_or_done(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return _STREAM_DONE


def _safe_payload(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "text"}


# ---- Ingest endpoints (handy when iterating without restart) ---------------

@app.post("/api/ingest/{name}")
def run_ingest(name: str, recreate: bool = False) -> dict:
    runners = {
        "selenium": ingest_selenium.run,
        "playwright": ingest_playwright.run,
        "testcases": ingest_testcases.run,
        "pdfs": ingest_pdfs.run,
        "jira": ingest_jira.run,
    }
    if name == "all":
        return _run_full_ingest(recreate=recreate)
    if name not in runners:
        raise HTTPException(404, f"unknown ingest target: {name}")
    return runners[name](recreate=recreate)


@app.get("/api/ingestion/status")
def ingestion_status() -> dict:
    client = qdrant_store.get_client()
    return {"status": "ready", "counts": qdrant_store.all_counts(client)}


@app.post("/api/ingestion/trigger")
def trigger_ingestion(background_tasks: BackgroundTasks, recreate: bool = False) -> dict:
    background_tasks.add_task(_run_full_ingest, recreate)
    return {"message": "Ingestion process started in background."}


def _run_full_ingest(recreate: bool = False) -> dict:
    runners = {
        "selenium": ingest_selenium.run,
        "playwright": ingest_playwright.run,
        "testcases": ingest_testcases.run,
        "pdfs": ingest_pdfs.run,
        "jira": ingest_jira.run,
    }
    results = []
    for name, runner in runners.items():
        try:
            results.append(runner(recreate=recreate))
        except Exception as e:
            results.append({"collection": name, "error": str(e)})
    return {"results": results}
