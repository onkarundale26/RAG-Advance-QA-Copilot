"""Qdrant client wrapper for 5-collection QA Copilot store.

Embedded mode (file store) by default; HTTP mode if QDRANT_URL is set.
Each collection: dense (1024d cosine) + sparse named vectors.
"""
from __future__ import annotations

import threading
import uuid
import atexit
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from . import settings

DENSE_DIM = 1536


_CLIENT = None
_LOCK = threading.Lock()


def get_client() -> QdrantClient:
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    with _LOCK:
        if _CLIENT is not None:
            return _CLIENT
        if settings.QDRANT_URL:
            _CLIENT = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=60.0,
            )
        else:
            Path(settings.QDRANT_PATH).mkdir(parents=True, exist_ok=True)
            _CLIENT = QdrantClient(path=str(settings.QDRANT_PATH))
    return _CLIENT


def close_client() -> None:
    global _CLIENT
    if _CLIENT is None:
        return
    try:
        _CLIENT.close()
    finally:
        _CLIENT = None


atexit.register(close_client)


def collection_exists(client: QdrantClient, name: str) -> bool:
    try:
        return client.collection_exists(name)
    except Exception:
        cols = client.get_collections().collections
        return any(c.name == name for c in cols)


def bootstrap(client: QdrantClient, name: str, recreate: bool = False) -> None:
    if collection_exists(client, name):
        if not recreate:
            return
        client.delete_collection(name)
    client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": qm.VectorParams(size=DENSE_DIM, distance=qm.Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": qm.SparseVectorParams(),
        },
    )


def bootstrap_all(client: QdrantClient, recreate: bool = False) -> None:
    for name in settings.COLLECTIONS:
        bootstrap(client, name, recreate=recreate)


def _stable_uuid(collection: str, chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"qacopilot/{collection}/{chunk_id}"))


def upsert_chunks(
    client: QdrantClient,
    name: str,
    chunks: list[dict],
    dense,
    sparse: list[dict],
    batch_size: int = 64,
) -> int:
    n = len(chunks)
    written = 0
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        points = []
        for i in range(start, end):
            ch = chunks[i]
            pid = _stable_uuid(name, ch["id"])
            payload = {
                **{k: v for k, v in (ch.get("metadata") or {}).items() if v is not None},
                "chunk_id": ch["id"],
                "text": ch["text"],
                "collection": name,
            }
            sp = sparse[i]
            points.append(qm.PointStruct(
                id=pid,
                vector={
                    "dense": dense[i].tolist(),
                    "sparse": qm.SparseVector(indices=sp["indices"], values=sp["values"]),
                },
                payload=payload,
            ))
        client.upsert(collection_name=name, points=points)
        written += len(points)
    return written


def count(client: QdrantClient, name: str) -> int:
    if not collection_exists(client, name):
        return 0
    try:
        return int(client.count(collection_name=name, exact=True).count)
    except Exception:
        return 0


def all_counts(client: QdrantClient) -> dict[str, int]:
    return {c: count(client, c) for c in settings.COLLECTIONS}


def _build_filter(flt: dict | None):
    if not flt:
        return None
    must = []
    for k, v in flt.items():
        if v is None or v == "":
            continue
        must.append(qm.FieldCondition(key=k, match=qm.MatchValue(value=v)))
    if not must:
        return None
    return qm.Filter(must=must)


def dense_search(client, name, query_dense, limit=12, flt=None):
    return client.query_points(
        collection_name=name,
        query=query_dense.tolist() if hasattr(query_dense, "tolist") else list(query_dense),
        using="dense",
        limit=limit,
        with_payload=True,
        query_filter=_build_filter(flt),
    ).points


def sparse_search(client, name, query_sparse: dict, limit=12, flt=None):
    return client.query_points(
        collection_name=name,
        query=qm.SparseVector(
            indices=query_sparse["indices"],
            values=query_sparse["values"],
        ),
        using="sparse",
        limit=limit,
        with_payload=True,
        query_filter=_build_filter(flt),
    ).points


def rrf(rank_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    score: dict[str, float] = {}
    for ranked in rank_lists:
        for r, doc_id in enumerate(ranked, start=1):
            score[doc_id] = score.get(doc_id, 0.0) + 1.0 / (k + r)
    out = sorted(score.items(), key=lambda t: t[1], reverse=True)
    return out


def hybrid_search_collection(
    client,
    collection: str,
    query_dense,
    query_sparse: dict,
    limit: int = 12,
    flt: dict | None = None,
) -> list[dict]:
    """Run dense + sparse, fuse with RRF, return list of {chunk_id, payload, score}."""
    dense_pts = dense_search(client, collection, query_dense, limit=limit, flt=flt)
    sparse_pts = sparse_search(client, collection, query_sparse, limit=limit, flt=flt)
    payload_by_id: dict[str, dict] = {}
    for pts in (dense_pts, sparse_pts):
        for p in pts:
            payload = dict(p.payload or {})
            cid = payload.get("chunk_id") or str(p.id)
            payload_by_id.setdefault(cid, payload)
    rank_lists = [
        [(p.payload or {}).get("chunk_id") or str(p.id) for p in dense_pts],
        [(p.payload or {}).get("chunk_id") or str(p.id) for p in sparse_pts],
    ]
    fused = rrf(rank_lists, k=60)
    out: list[dict] = []
    for cid, score in fused[:limit]:
        out.append({
            "chunk_id": cid,
            "rrf_score": round(score, 6),
            "collection": collection,
            "payload": payload_by_id.get(cid, {}),
        })
    return out
