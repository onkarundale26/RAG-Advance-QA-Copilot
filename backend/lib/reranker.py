"""BGE reranker with a fast fallback for local CPU runs."""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from . import settings

_RERANKER = None
_FUTURE = None
_LOAD_TIMED_OUT = False
_LOCK = threading.Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bge-reranker")


def _bool_env(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_reranker():
    global _RERANKER
    if _RERANKER is not None:
        return _RERANKER
    from FlagEmbedding import FlagReranker

    use_fp16 = os.environ.get("BGE_USE_FP16", "1") != "0"
    _RERANKER = FlagReranker(settings.RERANK_MODEL, use_fp16=use_fp16)
    return _RERANKER


def get_reranker(timeout_seconds: float | None = None):
    """Return the local BGE reranker, loading it in a background worker.

    The reranker model can take a while to load on CPU. If it is not ready before
    the timeout, callers can fall back to fused search ranking instead of making
    the API appear hung or return a 500.
    """
    global _FUTURE
    if _RERANKER is not None:
        return _RERANKER
    with _LOCK:
        if _FUTURE is None:
            _FUTURE = _EXECUTOR.submit(_load_reranker)
    return _FUTURE.result(timeout=timeout_seconds)


def rerank(question: str, candidates: list[dict], top_k: int = 4) -> list[dict]:
    """Score (question, candidate.text) pairs and return top-k with scores."""
    global _LOAD_TIMED_OUT
    if not candidates:
        return []

    if not _bool_env("USE_LOCAL_RERANKER", True):
        return _fallback_rerank(question, candidates, top_k, reason="disabled")

    if _LOAD_TIMED_OUT and _FUTURE is not None and not _FUTURE.done():
        return _fallback_rerank(question, candidates, top_k, reason="loading")

    timeout = float(os.environ.get("RERANK_TIMEOUT_SECONDS", "5"))
    try:
        model = get_reranker(timeout_seconds=timeout)
        _LOAD_TIMED_OUT = False
        return _bge_rerank(model, question, candidates, top_k)
    except TimeoutError:
        _LOAD_TIMED_OUT = True
        return _fallback_rerank(question, candidates, top_k, reason=f"timeout>{timeout}s")
    except Exception as exc:
        return _fallback_rerank(question, candidates, top_k, reason=str(exc))


def _bge_rerank(model, question: str, candidates: list[dict], top_k: int) -> list[dict]:
    pairs = []
    valid: list[dict] = []
    for i, candidate in enumerate(candidates):
        text = (candidate.get("payload") or {}).get("text", "")
        if not text:
            continue
        pairs.append([question, text])
        valid.append({**candidate, "fused_rank": i + 1})
    if not pairs:
        return []

    scores = model.compute_score(pairs, normalize=True)
    if isinstance(scores, (int, float)):
        scores = [float(scores)]

    out = [{**candidate, "rerank_score": float(score)} for candidate, score in zip(valid, scores)]
    out.sort(key=lambda item: item["rerank_score"], reverse=True)
    for rank, item in enumerate(out, start=1):
        item["rerank_rank"] = rank
    return out[:top_k]


def _fallback_rerank(question: str, candidates: list[dict], top_k: int, reason: str) -> list[dict]:
    q_terms = _terms(question)
    out = []
    for i, candidate in enumerate(candidates, start=1):
        text = (candidate.get("payload") or {}).get("text", "")
        overlap = len(q_terms.intersection(_terms(text)))
        fused = float(candidate.get("rrf_score") or candidate.get("score") or 0.0)
        out.append({
            **candidate,
            "fused_rank": i,
            "rerank_score": fused + (overlap * 0.01),
            "rerank_fallback": reason,
        })
    out.sort(key=lambda item: item["rerank_score"], reverse=True)
    for rank, item in enumerate(out, start=1):
        item["rerank_rank"] = rank
    return out[:top_k]


def _terms(text: str) -> set[str]:
    return {part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if len(part) > 2}
