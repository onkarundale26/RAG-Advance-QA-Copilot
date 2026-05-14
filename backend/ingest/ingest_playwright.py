"""Ingest Playwright TS repo into playwright_code collection."""
from __future__ import annotations

import argparse
import sys

from ..lib import chunking_code, settings
from ._runner import embed_and_upsert


def run(recreate: bool = False) -> dict:
    repo = settings.PLAYWRIGHT_REPO_DIR
    if not repo.exists() or not any(repo.iterdir()):
        print(f"Playwright repo dir empty or missing: {repo}")
        return {"collection": "playwright_code", "chunks": 0, "written": 0, "points": 0}
    print(f"Walking Playwright repo: {repo}")
    chunks = chunking_code.chunk_repo(repo, "typescript")
    for c in chunks:
        c["metadata"]["repo"] = "playwright"
    print(f"  produced {len(chunks)} TS/JS code chunks")
    return embed_and_upsert("playwright_code", chunks, recreate=recreate)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--recreate", action="store_true")
    args = p.parse_args()
    res = run(recreate=args.recreate)
    print(res)
    sys.exit(0)
