"""PDF + Markdown extraction & chunking.

PDFs: PyMuPDF page-by-page text. Skip pages with <50 chars. Sliding-window chunk.
JIRA MD: parse the JIRA-export header block ('Status:', 'Priority:', etc.) into
         metadata, then chunk the description body.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import chunking_text


def extract_pdf_pages(path: Path) -> list[dict]:
    """Return [{page, text}] per non-empty page. Skips pages with <50 chars."""
    import fitz  # PyMuPDF
    doc = fitz.open(str(path))
    pages: list[dict] = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if len(text) < 50:
            continue
        pages.append({"page": i, "text": text})
    doc.close()
    return pages


def chunk_pdf_file(path: Path, size: int, overlap: int) -> list[dict]:
    """One chunk per page (when small) or sliding window per page (when long)."""
    pages = extract_pdf_pages(path)
    if not pages:
        return []
    title = path.stem
    out: list[dict] = []
    for entry in pages:
        page_no = entry["page"]
        text = entry["text"]
        base_meta = {
            "doc_title": title,
            "page": page_no,
            "source_path": str(path.name),
            "kind": "pdf_page",
        }
        id_prefix = f"{path.stem}-p{page_no}"
        out.extend(chunking_text.sliding_window(text, size, overlap, base_meta, id_prefix))
    return out


# ---- JIRA markdown parsing ------------------------------------------------

JIRA_HEADER_FIELDS = (
    "Status", "Project", "Components", "Affects versions", "Fix versions",
    "Type", "Priority", "Reporter", "Assignee", "Resolution", "Votes",
    "Labels", "Sprint", "Rank",
)

_TITLE_RE = re.compile(r"\[(?P<jira_id>[A-Z]+-\d+)\]\s*(?P<summary>.+?)\s+Created:\s*(?P<created>[^ ]+)\s+Updated:\s*(?P<updated>[^ ]+)")
_FIELD_RE = re.compile(r"^(?P<field>[A-Za-z][A-Za-z ]+?):\s*(?P<value>.*)$")


def parse_jira_md(text: str, source_file: str) -> dict:
    """Return {metadata: dict, body: str}.

    Body = the description block after the header (everything from 'Description'
    line to the trailing 'Generated at ...' footer).
    """
    metadata: dict = {"source_file": source_file}
    lines = text.splitlines()

    # Title line containing jira id + summary
    for line in lines[:6]:
        m = _TITLE_RE.search(line)
        if m:
            metadata["jira_id"] = m.group("jira_id")
            metadata["summary"] = m.group("summary").strip()
            metadata["created"] = m.group("created")
            metadata["updated"] = m.group("updated")
            break

    # Header fields
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.lower().startswith("description"):
            break
        for field in JIRA_HEADER_FIELDS:
            prefix = f"{field}:"
            idx = s.find(prefix)
            if idx == -1:
                continue
            tail = s[idx + len(prefix):].strip()
            for nxt in JIRA_HEADER_FIELDS:
                cut = tail.find(f"{nxt}:")
                if cut != -1:
                    tail = tail[:cut].strip()
            key = field.lower().replace(" ", "_")
            if tail and tail.lower() not in ("none", "not specified", "unresolved", ""):
                metadata.setdefault(key, tail)

    # Body = between 'Description' marker and 'Generated at' footer
    body_lines: list[str] = []
    in_body = False
    for line in lines:
        s = line.strip()
        if not in_body:
            if s.lower().startswith("description"):
                in_body = True
            continue
        if s.lower().startswith("generated at "):
            break
        body_lines.append(line)
    body = "\n".join(body_lines).strip()
    return {"metadata": metadata, "body": body}


def chunk_jira_md_file(path: Path, size: int, overlap: int) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_jira_md(text, path.name)
    body = parsed["body"]
    if not body:
        body = text  # fallback: index whole file if header parse missed
    summary = parsed["metadata"].get("summary", "")
    jira_id = parsed["metadata"].get("jira_id", path.stem)
    composed = f"Summary: {summary}\n\n{body}" if summary else body
    base_meta = {**parsed["metadata"], "kind": "jira_bug"}
    id_prefix = f"jira-{jira_id}"
    return chunking_text.sliding_window(composed, size, overlap, base_meta, id_prefix)
