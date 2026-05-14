from fastapi import APIRouter, BackgroundTasks

from backend.lib import qdrant_store
from backend.main import _run_full_ingest

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


@router.get("/status")
async def get_status():
    client = qdrant_store.get_client()
    return {"status": "ready", "counts": qdrant_store.all_counts(client)}


@router.post("/trigger")
async def trigger_ingestion(background_tasks: BackgroundTasks, recreate: bool = False):
    background_tasks.add_task(_run_full_ingest, recreate)
    return {"message": "Ingestion process started in background."}
