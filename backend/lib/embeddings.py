"""OpenAI embedding wrapper for Vercel-compatible dense vectors.

Replaces local BGE-M3 to fit within serverless size limits.
"""
from __future__ import annotations

import os
from openai import OpenAI
import numpy as np

from . import settings

_CLIENT = None

def get_openai_client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _CLIENT

def embed_batch(texts: list[str], batch_size: int = 100) -> dict:
    """Embed texts using OpenAI text-embedding-3-small (1536d)."""
    client = get_openai_client()
    all_dense = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        res = client.embeddings.create(
            input=batch,
            model="text-embedding-3-small"
        )
        all_dense.extend([np.array(d.embedding, dtype=np.float32) for d in res.data])
    
    if not all_dense:
        return {"dense": np.zeros((0, 1536), dtype=np.float32), "sparse": []}
        
    # Return empty sparse vectors for compatibility with existing Qdrant hybrid logic
    return {
        "dense": np.vstack(all_dense),
        "sparse": [{"indices": [], "values": []} for _ in all_dense]
    }

def embed_query(text: str) -> dict:
    res = embed_batch([text])
    return {"dense": res["dense"][0], "sparse": res["sparse"][0]}

