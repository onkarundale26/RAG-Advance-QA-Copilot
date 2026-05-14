"""Env-driven settings. Single source of truth for paths and knobs."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

CHAPTER_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(CHAPTER_ROOT / ".env")


def _path(key: str, default_rel: str) -> Path:
    raw = os.environ.get(key, default_rel).strip()
    p = Path(raw)
    if not p.is_absolute():
        p = (CHAPTER_ROOT / p).resolve()
    return p


def _int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b").strip()

QDRANT_URL = os.environ.get("QDRANT_URL", "").strip()
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "").strip()
QDRANT_PATH = _path("QDRANT_PATH", "./qdrant_data")

EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-m3").strip()
RERANK_MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-v2-m3").strip()

SELENIUM_REPO_DIR = _path("SELENIUM_REPO_DIR", "./data/selenium_repo")
PLAYWRIGHT_REPO_DIR = _path("PLAYWRIGHT_REPO_DIR", "./data/playwright_repo")
TESTCASES_CSV = _path("TESTCASES_CSV", "./data/csv/testcases_vwo_100.csv")
PDFS_DIR = _path("PDFS_DIR", "./data/pdf")
JIRA_MD_DIR = _path("JIRA_MD_DIR", "./data/md")

TOP_K_PER_COLLECTION = _int("TOP_K_PER_COLLECTION", 12)
RERANK_TOP_K = _int("RERANK_TOP_K", 4)
CHUNK_SIZE = _int("CHUNK_SIZE", 1000)
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 150)
HISTORY_TURNS = _int("HISTORY_TURNS", 4)
INGEST_BATCH = _int("INGEST_BATCH", 16)


def _bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


INGEST_INTERVAL_MINUTES = _int("INGEST_INTERVAL_MINUTES", 60)
INGEST_AT_STARTUP = _bool("INGEST_AT_STARTUP", True)
INGEST_TARGETS = os.environ.get(
    "INGEST_TARGETS", "selenium,playwright,testcases,pdfs,jira"
).strip()
INGEST_TARGETS_LIST = [t.strip() for t in INGEST_TARGETS.split(",") if t.strip()]
INGEST_RECREATE = _bool("INGEST_RECREATE", False)
INGEST_LOCK_FILE = _path("INGEST_LOCK_FILE", "./data/.ingest.lock")


COLLECTIONS = (
    "selenium_code",
    "playwright_code",
    "vwo_testcases",
    "vwo_docs",
    "vwo_bugs",
)
