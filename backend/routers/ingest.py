from fastapi import APIRouter

from backend.main import run_ingest

router = APIRouter()


@router.post("/ingest/{name}")
async def ingest_route(name: str, recreate: bool = False):
    return run_ingest(name, recreate=recreate)


@router.post("/ingest/all")
async def trigger_ingest_all(recreate: bool = False):
    return run_ingest("all", recreate=recreate)
