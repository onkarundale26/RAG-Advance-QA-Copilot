"""Shared ingest helper: chunks -> embed -> upsert -> count."""
from __future__ import annotations

import numpy as np

from ..lib import embeddings, qdrant_store, settings


def embed_and_upsert(collection: str, chunks: list[dict], recreate: bool = False) -> dict:
    if not chunks:
        return {"collection": collection, "chunks": 0, "written": 0, "points": 0}

    client = qdrant_store.get_client()
    qdrant_store.bootstrap(client, collection, recreate=recreate)

    texts = [c["text"] for c in chunks]
    bs = settings.INGEST_BATCH
    all_dense: list[np.ndarray] = []
    all_sparse: list[dict] = []
    for i in range(0, len(texts), bs):
        sub = texts[i:i + bs]
        res = embeddings.embed_batch(sub, batch_size=len(sub))
        all_dense.append(res["dense"])
        all_sparse.extend(res["sparse"])
        done = min(i + bs, len(texts))
        print(f"  embedded {done}/{len(texts)}")
    dense = np.vstack(all_dense)

    written = qdrant_store.upsert_chunks(client, collection, chunks, dense, all_sparse)
    points = qdrant_store.count(client, collection)
    return {
        "collection": collection,
        "chunks": len(chunks),
        "written": written,
        "points": points,
    }
