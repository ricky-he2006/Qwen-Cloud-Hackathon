"""Shared helpers for parsing LLM JSON outputs."""

import json
import re
from typing import Any, Optional


def strip_json_fences(raw: str) -> str:
    """Remove markdown code fences often wrapped around LLM JSON."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_json_payload(raw: str) -> Optional[Any]:
    """Parse JSON from LLM output; returns None on failure."""
    text = strip_json_fences(raw)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group(0))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
    return None
