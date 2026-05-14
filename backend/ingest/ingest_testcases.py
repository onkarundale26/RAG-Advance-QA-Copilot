"""Ingest VWO test cases CSV into vwo_testcases collection (row-aware)."""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from ..lib import chunking_text, settings
from ._runner import embed_and_upsert

TEXT_COLS = ["summary", "preconditions", "steps", "expected_result", "labels"]
META_COLS = ["id", "jira_id", "module", "priority", "severity", "labels",
             "sprint", "status", "owner", "test_type"]


def run(recreate: bool = False) -> dict:
    csv = settings.TESTCASES_CSV
    if not csv.exists():
        print(f"Test cases CSV not found: {csv}")
        return {"collection": "vwo_testcases", "chunks": 0, "written": 0, "points": 0}
    print(f"Reading test cases: {csv}")
    df = pd.read_csv(csv, dtype=str)
    have = set(df.columns)
    text_cols = [c for c in TEXT_COLS if c in have] or list(have)
    meta_cols = [c for c in META_COLS if c in have]
    print(f"  rows={len(df)}  text_cols={text_cols}  meta_cols={meta_cols}")
    rows = df.to_dict(orient="records")
    chunks = chunking_text.chunk_dataframe(
        rows, text_cols=text_cols, meta_cols=meta_cols,
        size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP,
        source_file=csv.name,
    )
    print(f"  produced {len(chunks)} test-case chunks")
    return embed_and_upsert("vwo_testcases", chunks, recreate=recreate)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--recreate", action="store_true")
    args = p.parse_args()
    res = run(recreate=args.recreate)
    print(res)
    sys.exit(0)
