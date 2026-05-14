"""Row-aware + sliding-window text chunking.

Ported from Chapter_08_RAG/Advance_RAG_EXPLAIN/lib/chunking.py.
"""
from __future__ import annotations

from typing import Iterable


def assemble_document(row: dict, text_cols: list[str]) -> str:
    parts: list[str] = []
    for col in text_cols:
        val = row.get(col)
        if val is None:
            continue
        s = str(val).strip()
        if not s or s.lower() == "nan":
            continue
        label = col.replace("_", " ").strip().title()
        parts.append(f"{label}: {s}")
    return "\n".join(parts)


def _row_test_case_id(row: dict, fallback: int) -> str:
    for key in ("id", "test_case_id", "tc_id", "case_id", "key"):
        if key in row and row[key] not in (None, "", "nan"):
            return str(row[key])
    return f"row-{fallback}"


def chunk_test_case(
    doc: str,
    row_index: int,
    metadata: dict,
    size: int = 1000,
    overlap: int = 150,
    source_file: str = "",
) -> list[dict]:
    if size <= 0:
        raise ValueError("CHUNK_SIZE must be > 0")
    if overlap < 0 or overlap >= size:
        raise ValueError("CHUNK_OVERLAP must satisfy 0 <= overlap < size")

    test_case_id = _row_test_case_id(metadata, row_index)
    base_meta = {
        "row_index": row_index,
        "test_case_id": test_case_id,
        "source_file": source_file,
        **{k: (None if str(v).lower() == "nan" else v) for k, v in metadata.items()},
    }

    n = len(doc)
    if n == 0:
        return []

    if n <= size:
        return [{
            "id": f"r{row_index}-c0",
            "text": doc,
            "metadata": {**base_meta, "chunk_index": 0, "total_chunks": 1},
        }]

    chunks: list[dict] = []
    start = 0
    chunk_idx = 0
    while start < n:
        end = min(start + size, n)
        chunks.append({
            "id": f"r{row_index}-c{chunk_idx}",
            "text": doc[start:end],
            "metadata": {**base_meta, "chunk_index": chunk_idx, "total_chunks": -1},
        })
        if end >= n:
            break
        start = end - overlap
        chunk_idx += 1

    total = len(chunks)
    for c in chunks:
        c["metadata"]["total_chunks"] = total
    return chunks


def chunk_dataframe(
    rows: Iterable[dict],
    text_cols: list[str],
    meta_cols: list[str],
    size: int,
    overlap: int,
    source_file: str = "",
) -> list[dict]:
    out: list[dict] = []
    for i, row in enumerate(rows):
        doc = assemble_document(row, text_cols)
        if not doc:
            continue
        meta = {col: row.get(col) for col in meta_cols}
        out.extend(chunk_test_case(
            doc=doc, row_index=i, metadata=meta,
            size=size, overlap=overlap, source_file=source_file,
        ))
    return out


def sliding_window(
    text: str,
    size: int,
    overlap: int,
    base_meta: dict,
    id_prefix: str,
) -> list[dict]:
    """Generic sliding-window chunker for free-form text (PDFs, MD bodies)."""
    n = len(text)
    if n == 0:
        return []
    if n <= size:
        return [{
            "id": f"{id_prefix}-c0",
            "text": text,
            "metadata": {**base_meta, "chunk_index": 0, "total_chunks": 1},
        }]
    chunks: list[dict] = []
    start = 0
    idx = 0
    while start < n:
        end = min(start + size, n)
        chunks.append({
            "id": f"{id_prefix}-c{idx}",
            "text": text[start:end],
            "metadata": {**base_meta, "chunk_index": idx, "total_chunks": -1},
        })
        if end >= n:
            break
        start = end - overlap
        idx += 1
    total = len(chunks)
    for c in chunks:
        c["metadata"]["total_chunks"] = total
    return chunks
