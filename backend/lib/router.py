"""LLM intent router: classify question -> 1-2 collections."""
from __future__ import annotations

import json
import re

from . import groq_client, prompts, settings


def route(question: str) -> dict:
    """Return {'collections': [...], 'reason': str}. Falls back to all on parse error."""
    try:
        res = groq_client.complete(
            messages=[
                {"role": "system", "content": prompts.ROUTER_SYSTEM},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        text = res["text"].strip()
        obj = json.loads(text)
    except Exception as e:
        return {
            "collections": list(settings.COLLECTIONS),
            "reason": f"router fallback: {e}",
        }

    cols = obj.get("collections") or []
    cols = [c for c in cols if c in settings.COLLECTIONS][:2]
    if not cols:
        cols = list(settings.COLLECTIONS)
    return {
        "collections": cols,
        "reason": str(obj.get("reason", "")).strip()[:240],
    }


_TC_RE = re.compile(r"\b(VWO-\d+|TC-\d+)\b", re.IGNORECASE)


def heuristic_hint(question: str) -> list[str]:
    """Cheap regex hints to bias router output without a Groq call."""
    hits: list[str] = []
    if _TC_RE.search(question):
        hits.append("vwo_testcases")
    q = question.lower()
    if any(k in q for k in ("selenium", ".java", "page object", "@test ", "testng")):
        hits.append("selenium_code")
    if any(k in q for k in ("playwright", "fixture", "test(", ".ts ", "page.")):
        hits.append("playwright_code")
    if any(k in q for k in ("prd", "spec", "requirement")):
        hits.append("vwo_docs")
    if any(k in q for k in ("bug", "ticket", "issue ", "jira")):
        hits.append("vwo_bugs")
    return hits
