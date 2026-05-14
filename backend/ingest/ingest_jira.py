"""Ingest JIRA bug markdown exports into vwo_bugs."""
from __future__ import annotations

import argparse
import sys

from ..lib import chunking_md_pdf, settings
from ._runner import embed_and_upsert


def run(recreate: bool = False) -> dict:
    md_dir = settings.JIRA_MD_DIR
    if not md_dir.exists():
        print(f"JIRA MD dir not found: {md_dir}")
        return {"collection": "vwo_bugs", "chunks": 0, "written": 0, "points": 0}
    files = sorted(md_dir.glob("*.md"))
    print(f"JIRA MD files: {len(files)} in {md_dir}")
    chunks: list[dict] = []
    for path in files:
        file_chunks = chunking_md_pdf.chunk_jira_md_file(
            path, size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP,
        )
        chunks.extend(file_chunks)
        print(f"  {path.name}: {len(file_chunks)} chunks")
    print(f"  total {len(chunks)} jira chunks")
    return embed_and_upsert("vwo_bugs", chunks, recreate=recreate)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--recreate", action="store_true")
    args = p.parse_args()
    res = run(recreate=args.recreate)
    print(res)
    sys.exit(0)
