"""Groq REST wrappers: completion (sync), streaming, JSON-mode classification."""
from __future__ import annotations

import json
import os
from typing import Iterator

import requests

from . import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _headers() -> dict:
    api_key = settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def complete(messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024,
             response_format: dict | None = None) -> dict:
    body = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format
    r = requests.post(GROQ_URL, headers=_headers(), data=json.dumps(body), timeout=120)
    r.raise_for_status()
    data = r.json()
    return {
        "text": data["choices"][0]["message"]["content"],
        "usage": data.get("usage", {}),
        "raw": data,
    }


def stream(messages: list[dict], temperature: float = 0.2,
           max_tokens: int = 1024) -> Iterator[str]:
    """Yield text deltas from the Groq streaming endpoint."""
    body = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    with requests.post(GROQ_URL, headers=_headers(), data=json.dumps(body),
                       stream=True, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                line = line[6:]
            if line == "[DONE]":
                break
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta", {}) or {}
            piece = delta.get("content") or ""
            if piece:
                yield piece
