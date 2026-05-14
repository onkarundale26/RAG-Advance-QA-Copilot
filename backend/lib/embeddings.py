"""bge-m3 wrapper producing dense + sparse vectors from one model.

Ported from Chapter_08_RAG/Advance_RAG_EXPLAIN/lib/embeddings.py.
"""
from __future__ import annotations

import os
import threading

import numpy as np

from . import settings

_MODEL = None
_LOCK = threading.Lock()


def get_embedder():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _LOCK:
        if _MODEL is not None:
            return _MODEL
        from FlagEmbedding import BGEM3FlagModel
        use_fp16 = os.environ.get("BGE_USE_FP16", "1") != "0"
        _MODEL = BGEM3FlagModel(settings.EMBED_MODEL, use_fp16=use_fp16)
    return _MODEL


def _format_sparse(raw_sparse) -> list[dict]:
    out: list[dict] = []
    for item in raw_sparse:
        if isinstance(item, dict):
            indices = list(item.keys())
            values = list(item.values())
        else:
            indices = list(getattr(item, "indices", []))
            values = list(getattr(item, "values", []))
        indices = [int(i) for i in indices]
        values = [float(v) for v in values]
        out.append({"indices": indices, "values": values})
    return out


def embed_batch(texts: list[str], batch_size: int = 16) -> dict:
    model = get_embedder()
    out_dense: list[np.ndarray] = []
    out_sparse: list[dict] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        result = model.encode(
            batch,
            batch_size=len(batch),
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense = np.asarray(result["dense_vecs"], dtype=np.float32)
        out_dense.append(dense)
        out_sparse.extend(_format_sparse(result["lexical_weights"]))
    if not out_dense:
        return {"dense": np.zeros((0, 1024), dtype=np.float32), "sparse": []}
    return {"dense": np.vstack(out_dense), "sparse": out_sparse}


def embed_query(text: str) -> dict:
    res = embed_batch([text], batch_size=1)
    return {"dense": res["dense"][0], "sparse": res["sparse"][0]}
