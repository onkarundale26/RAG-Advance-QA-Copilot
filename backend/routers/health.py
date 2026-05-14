from fastapi import APIRouter

from backend.lib import qdrant_store, settings

router = APIRouter()


@router.get("/health")
async def health_check():
    client = qdrant_store.get_client()
    counts = qdrant_store.all_counts(client)
    return {
        "ok": True,
        "status": "healthy",
        "groq_model": settings.GROQ_MODEL,
        "embed_model": settings.EMBED_MODEL,
        "rerank_model": settings.RERANK_MODEL,
        "collections": counts,
        "counts": counts,
    }
