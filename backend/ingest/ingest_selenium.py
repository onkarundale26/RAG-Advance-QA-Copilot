"""Ingest Selenium Java repo into selenium_code collection."""
from __future__ import annotations

import argparse
import sys

from ..lib import chunking_code, settings
from ._runner import embed_and_upsert


def run(recreate: bool = False) -> dict:
    repo = settings.SELENIUM_REPO_DIR
    if not repo.exists() or not any(repo.iterdir()):
        print(f"Selenium repo dir empty or missing: {repo}")
        return {"collection": "selenium_code", "chunks": 0, "written": 0, "points": 0}
    print(f"Walking Selenium repo: {repo}")
    chunks = chunking_code.chunk_repo(repo, "java")
    for c in chunks:
        c["metadata"]["repo"] = "selenium"
    print(f"  produced {len(chunks)} Java code chunks")
    return embed_and_upsert("selenium_code", chunks, recreate=recreate)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--recreate", action="store_true")
    args = p.parse_args()
    res = run(recreate=args.recreate)
    print(res)
    sys.exit(0)
