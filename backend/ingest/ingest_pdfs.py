"""Ingest PDFs (PRDs/specs) into vwo_docs. Skip empty (<50 chars) and report."""
from __future__ import annotations

import argparse
import json
import sys

from ..lib import chunking_md_pdf, settings
from ._runner import embed_and_upsert


def run(recreate: bool = False) -> dict:
    pdf_dir = settings.PDFS_DIR
    if not pdf_dir.exists():
        print(f"PDFs dir not found: {pdf_dir}")
        return {"collection": "vwo_docs", "chunks": 0, "written": 0, "points": 0}
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    print(f"PDFs: {len(pdfs)} in {pdf_dir}")
    skip_report: list[dict] = []
    chunks: list[dict] = []
    for path in pdfs:
        try:
            file_chunks = chunking_md_pdf.chunk_pdf_file(
                path, size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP,
            )
        except Exception as e:
            skip_report.append({"file": path.name, "reason": f"error: {e}"})
            continue
        if not file_chunks:
            skip_report.append({"file": path.name, "reason": "empty/<50 chars per page"})
            continue
        chunks.extend(file_chunks)
        print(f"  {path.name}: {len(file_chunks)} chunks")
    if skip_report:
        report_path = settings.CHAPTER_ROOT / "data" / "_skip_report.json" if False else (settings.PDFS_DIR.parent / "_skip_report.json")
        report_path.write_text(json.dumps(skip_report, indent=2))
        print(f"  skip report: {report_path}")
    print(f"  total {len(chunks)} pdf chunks")
    return embed_and_upsert("vwo_docs", chunks, recreate=recreate)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--recreate", action="store_true")
    args = p.parse_args()
    res = run(recreate=args.recreate)
    print(res)
    sys.exit(0)
