"""Jina AI embedding wrapper for Vercel-compatible dense vectors.

Uses Jina Embeddings v3 for high quality and serverless speed.
"""
from __future__ import annotations

import os
import requests
import numpy as np

from . import settings

JINA_API_URL = "https://api.jina.ai/v1/embeddings"

def embed_batch(texts: list[str], batch_size: int = 16) -> dict:
    """Embed texts using Jina Embeddings v3 (1024d)."""
    api_key = os.environ.get("JINA_API_KEY")
    if not api_key:
        raise ValueError("JINA_API_KEY environment variable is not set")
        
    all_dense = []
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        data = {
            "model": "jina-embeddings-v3",
            "task": "retrieval.passage",
            "dimensions": 1024,
            "late_chunking": False,
            "embedding_type": "float",
            "input": batch
        }
        try:
            resp = requests.post(JINA_API_URL, headers=headers, json=data)
            resp.raise_for_status()
            result = resp.json()
            all_dense.extend([np.array(d["embedding"], dtype=np.float32) for d in result["data"]])
        except Exception as e:
            print(f"  Batch failed at index {i}, retrying items individually...")
            # If batch fails, try one by one to find the culprit
            for text in batch:
                try:
                    single_data = {**data, "input": [text[:30000]]} # Trim very long text
                    r = requests.post(JINA_API_URL, headers=headers, json=single_data)
                    r.raise_for_status()
                    all_dense.append(np.array(r.json()["data"][0]["embedding"], dtype=np.float32))
                except Exception as inner_e:
                    print(f"    Skipping chunk due to error: {inner_e}")
                    # Use zero vector if we must skip to keep indices aligned
                    all_dense.append(np.zeros(1024, dtype=np.float32))
    
    if not all_dense:
        return {"dense": np.zeros((0, 1024), dtype=np.float32), "sparse": []}
        
    return {
        "dense": np.vstack(all_dense),
        "sparse": [{"indices": [], "values": []} for _ in all_dense]
    }

def embed_query(text: str) -> dict:
    api_key = os.environ.get("JINA_API_KEY")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": "jina-embeddings-v3",
        "task": "retrieval.query",
        "dimensions": 1024,
        "late_chunking": False,
        "embedding_type": "float",
        "input": [text]
    }
    resp = requests.post(JINA_API_URL, headers=headers, json=data)
    resp.raise_for_status()
    result = resp.json()
    dense = np.array(result["data"][0]["embedding"], dtype=np.float32)
    return {"dense": dense, "sparse": {"indices": [], "values": []}}

