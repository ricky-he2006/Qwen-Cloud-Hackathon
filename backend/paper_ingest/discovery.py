"""
Research discovery — find papers on the open web from natural-language intent.
Uses OpenAlex, PubMed, and arXiv (no API keys required).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import requests

from paper_ingest.fetcher import PaperFetcher, PaperMetadata
from paper_ingest.resolver import (
    USER_AGENT,
    REQUEST_TIMEOUT,
    fetch_pubmed,
    search_openalex,
)

DISCOVERY_SOURCES = ("openalex", "pubmed", "arxiv")


def _normalize_key(meta: PaperMetadata) -> str:
    doi = (meta.paper_id or "").lower().strip()
    if doi.startswith("10."):
        return f"doi:{doi}"
    title = re.sub(r"\W+", "", (meta.title or "").lower())[:80]
    return f"title:{title}"


def _pubmed_search(query: str, max_results: int = 5) -> List[PaperMetadata]:
    try:
        search_resp = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
                "sort": "relevance",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        if search_resp.status_code != 200:
            return []

        ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        papers: List[PaperMetadata] = []
        for pmid in ids:
            meta = fetch_pubmed(pmid)
            if meta and meta.title:
                papers.append(meta)
        return papers
    except Exception as e:
        print(f"PubMed search failed: {e}")
        return []


async def expand_research_query(user_request: str, llm=None) -> List[str]:
    """
    Turn a natural-language research goal into 1-3 search queries.
    Falls back to the raw request if LLM is unavailable.
    """
    user_request = user_request.strip()
    if not user_request:
        return []

    if llm is None:
        return [user_request]

    from utils.llm_client import Message

    prompt = f"""A researcher wants papers matching this goal:

"{user_request}"

Generate 1-3 concise academic search queries (5-12 words each) for scholarly databases.
Include subject terms, methods, or populations if implied.
Return JSON only: {{"queries": ["...", "..."]}}"""

    try:
        raw = await llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.3,
            max_tokens=200,
        )
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        import json

        data = json.loads(text)
        queries = [q.strip() for q in data.get("queries", []) if q and q.strip()]
        return queries[:3] or [user_request]
    except Exception:
        return [user_request]


def discover_papers(
    query: str,
    max_results: int = 8,
    per_source: int = 5,
) -> List[Dict]:
    """
    Search the scholarly web and return ranked paper candidates.
    """
    query = query.strip()
    if not query:
        return []

    seen = set()
    candidates: List[Dict] = []

    def add_candidate(meta: PaperMetadata, source: str, search_query: str) -> None:
        if not meta or not meta.title:
            return
        key = _normalize_key(meta)
        if key in seen:
            return
        seen.add(key)

        identifier = meta.paper_id
        if identifier and not identifier.startswith("10.") and meta.url:
            identifier = meta.url
        elif identifier and identifier.startswith("10."):
            identifier = identifier
        elif meta.url:
            identifier = meta.url
        else:
            identifier = meta.title

        candidates.append({
            "title": meta.title,
            "authors": meta.authors[:6],
            "abstract": (meta.abstract or "")[:600],
            "paper_id": meta.paper_id,
            "identifier": identifier,
            "url": meta.url,
            "published_date": meta.published_date,
            "categories": meta.categories[:5],
            "source": source,
            "search_query": search_query,
        })

    for meta in search_openalex(query, per_page=per_source):
        add_candidate(meta, "openalex", query)

    for meta in _pubmed_search(query, max_results=per_source):
        add_candidate(meta, "pubmed", query)

    try:
        fetcher = PaperFetcher()
        for meta in fetcher.search_arxiv(query, max_results=per_source):
            add_candidate(meta, "arxiv", query)
    except Exception as e:
        print(f"arXiv search in discovery failed: {e}")

    return candidates[:max_results]


async def discover_from_request(
    user_request: str,
    max_results: int = 8,
    use_llm_expansion: bool = True,
) -> Dict:
    """
    Full discovery flow: expand intent → multi-source search → deduped results.
    """
    from utils.llm_client import LLMClient

    llm = LLMClient() if use_llm_expansion else None
    queries = await expand_research_query(user_request, llm=llm)

    all_candidates: List[Dict] = []
    seen = set()

    for q in queries:
        for item in discover_papers(q, max_results=max_results, per_source=4):
            key = _normalize_key(
                PaperMetadata(
                    title=item["title"],
                    authors=item.get("authors", []),
                    abstract=item.get("abstract", ""),
                    published_date=item.get("published_date", ""),
                    paper_id=item.get("paper_id", ""),
                    url=item.get("url", ""),
                    categories=item.get("categories", []),
                )
            )
            if key in seen:
                continue
            seen.add(key)
            all_candidates.append(item)

    return {
        "request": user_request,
        "search_queries": queries,
        "results": all_candidates[:max_results],
        "total_found": len(all_candidates[:max_results]),
    }
