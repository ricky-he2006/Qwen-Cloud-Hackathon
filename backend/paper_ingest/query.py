"""
Unified natural-language paper query — direct load or scholarly web discovery.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from paper_ingest.discovery import discover_from_request
from paper_ingest.fetcher import PaperFetcher


def classify_query(text: str) -> Tuple[str, str]:
    """
    Decide whether input is a direct paper reference or a research question.
    Returns (mode, cleaned_input) where mode is 'direct' or 'discover'.
    """
    raw = text.strip()
    if not raw:
        return ("discover", raw)

    lower = raw.lower()

    if raw.startswith("http://") or raw.startswith("https://"):
        return ("direct", raw)

    if re.match(r"^10\.\d{4,9}/\S+$", raw):
        return ("direct", raw)

    if re.match(r"^doi:\s*10\.\d{4,9}/\S+$", lower):
        return ("direct", re.sub(r"^doi:\s*", "", raw, flags=re.IGNORECASE))

    if re.match(r"^(pmid:)?\d{7,8}$", raw, re.IGNORECASE):
        return ("direct", raw)

    if re.match(r"^\d{4}\.\d{5}(v\d+)?$", raw):
        return ("direct", raw)

    if re.search(r"doi\.org/10\.\d{4,9}/", lower):
        return ("direct", raw)

    if re.search(r"arxiv\.org/(abs|pdf)/", lower):
        return ("direct", raw)

    if re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/\d+", lower):
        return ("direct", raw)

    # Short bare title-like strings without question words → try direct search first
    word_count = len(raw.split())
    question_markers = (
        "find", "search", "looking for", "papers on", "papers about", "studies on",
        "studies about", "recent", "latest", "good", "best", "recommend", "show me",
        "i want", "i need", "help me", "what are", "which",
    )
    has_question_intent = any(m in lower for m in question_markers) or "?" in raw

    if word_count >= 6 or has_question_intent:
        return ("discover", raw)

    # Medium-length phrase: try direct resolve first on backend; frontend can fall back
    if word_count <= 5 and not has_question_intent:
        return ("direct", raw)

    return ("discover", raw)


async def handle_paper_query(
    query: str,
    max_results: int = 8,
    expand_query: bool = True,
) -> Dict:
    """
    One entry point for natural language:
    - direct identifiers/URLs → fetch full paper
    - research questions → discover candidates on the scholarly web
    """
    mode, cleaned = classify_query(query)
    fetcher = PaperFetcher()

    if mode == "direct":
        paper_type, metadata = fetcher.identify_paper(cleaned)
        if metadata and metadata.title:
            sections = fetcher.extract_sections_from_metadata(metadata, paper_type)
            return {
                "mode": "direct",
                "success": True,
                "paper": {
                    "paper_id": metadata.paper_id,
                    "type": paper_type,
                    "title": metadata.title,
                    "authors": metadata.authors,
                    "abstract": (metadata.abstract or "")[:500],
                    "categories": metadata.categories,
                    "sections": sections,
                },
            }

        # Direct resolve failed — fall back to discovery for title-like queries
        if len(cleaned.split()) >= 3:
            discovery = await discover_from_request(cleaned, max_results=max_results, use_llm_expansion=expand_query)
            if discovery.get("results"):
                return {
                    "mode": "discover",
                    "success": True,
                    "direct_failed": True,
                    "request": cleaned,
                    **discovery,
                }

        return {
            "mode": "direct",
            "success": False,
            "error_message": "Could not load that paper directly.",
            "hint": "Try a DOI, PubMed link, or describe the paper you want in more detail.",
        }

    discovery = await discover_from_request(cleaned, max_results=max_results, use_llm_expansion=expand_query)
    return {
        "mode": "discover",
        "success": True,
        "request": cleaned,
        **discovery,
    }
