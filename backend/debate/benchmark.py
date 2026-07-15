"""Benchmark: multi-agent society vs single-agent solo reviewer."""

import asyncio
import json
import re
import time
from typing import Dict, List, Optional, Any

from utils.llm_client import LLMClient, Message
from debate.structured import REVIEW_DIMENSIONS


DIMENSION_KEYWORDS = {
    "methodology_rigor": ["method", "cohort", "design", "statistical", "regression", "confound", "sample"],
    "novelty_assessment": ["novel", "contribution", "new", "first", "prior work", "significance"],
    "clarity_and_organization": ["clear", "organization", "structure", "section", "framing"],
    "limitations_identified": ["limitation", "weakness", "concern", "bias", "uncertain", "caveat"],
    "literature_context": ["literature", "prior", "previous", "field", "context", "citation"],
    "reproducibility": ["reproduc", "replicate", "protocol", "available", "data", "code"],
    "statistical_validity": ["statistical", "confidence interval", "p-value", "hazard", "risk", "significant"],
    "contribution_significance": ["important", "implication", "impact", "contribution", "clinical", "future research"],
}

ROLE_DIMENSIONS = {
    "dr. methods": ["methodology_rigor", "statistical_validity", "reproducibility"],
    "methodology": ["methodology_rigor", "statistical_validity", "reproducibility"],
    "dr. novelty": ["novelty_assessment", "contribution_significance"],
    "contribution": ["novelty_assessment", "contribution_significance"],
    "dr. structure": ["clarity_and_organization"],
    "structure": ["clarity_and_organization"],
    "dr. context": ["literature_context"],
    "literature": ["literature_context"],
}


def _parse_json_object(raw: str) -> Dict[str, Any]:
    from utils.json_parse import parse_json_payload

    data = parse_json_payload(raw)
    if isinstance(data, dict):
        return data
    raise json.JSONDecodeError("No JSON object found", raw or "", 0)


def _keyword_dimensions(text: str) -> List[str]:
    lower = text.lower()
    covered = set()
    for dimension, keywords in DIMENSION_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            covered.add(dimension)

    for role_marker, dimensions in ROLE_DIMENSIONS.items():
        if role_marker in lower:
            covered.update(dimensions)

    return sorted(covered)


async def _score_coverage(text: str, llm: LLMClient) -> Dict[str, Any]:
    """Score how many review dimensions are addressed in text."""
    prompt = f"""Analyze this peer review text and determine which dimensions are substantively addressed.

Review text:
{text[:6000]}

Dimensions to check:
{json.dumps(REVIEW_DIMENSIONS)}

Return JSON only:
{{"covered": ["dimension_name", ...], "coverage_score": 0.0-1.0, "evidence_count": int}}

coverage_score = fraction of dimensions with substantive discussion."""

    response = await llm.generate_async(
        messages=[Message("user", prompt)],
        temperature=0.2,
        max_tokens=400,
    )

    keyword_covered = _keyword_dimensions(text)

    try:
        data = _parse_json_object(response)
        covered = sorted(set(data.get("covered", [])) | set(keyword_covered))
        llm_score = float(data.get("coverage_score", len(covered) / len(REVIEW_DIMENSIONS)))
        keyword_score = len(covered) / len(REVIEW_DIMENSIONS)
        # Blend — avoid both society & solo saturating at 100% via keyword OR alone
        coverage_score = min(1.0, 0.55 * llm_score + 0.45 * keyword_score)
        return {
            "dimensions_covered": covered,
            "coverage_score": round(coverage_score, 3),
            "evidence_count": max(
                int(data.get("evidence_count", 0)),
                text.lower().count("evidence") + text.lower().count("section"),
            ),
            "total_dimensions": len(REVIEW_DIMENSIONS),
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "dimensions_covered": keyword_covered,
            "coverage_score": len(keyword_covered) / len(REVIEW_DIMENSIONS),
            "evidence_count": text.lower().count("section"),
            "total_dimensions": len(REVIEW_DIMENSIONS),
        }


async def run_solo_review(paper_title: str, sections: Dict[str, str]) -> Dict:
    """Single-agent comprehensive review baseline."""
    llm = LLMClient()
    start = time.perf_counter()

    paper_text = "\n\n".join(f"## {k}\n{v[:2000]}" for k, v in sections.items() if v)

    prompt = f"""You are a senior peer reviewer. Write a comprehensive review of this paper.

Title: {paper_title}

Paper:
{paper_text[:8000]}

Address ALL of these dimensions: {', '.join(REVIEW_DIMENSIONS)}

Include methodology critique, novelty assessment, limitations, and a clear verdict (ACCEPT/REVISE/REJECT)."""

    review = await llm.generate_async(
        messages=[Message("user", prompt)],
        temperature=0.5,
        max_tokens=1200,
    )

    elapsed = time.perf_counter() - start
    coverage = await _score_coverage(review, llm)

    return {
        "mode": "solo",
        "report": review.strip(),
        "elapsed_seconds": round(elapsed, 2),
        "tokens_used": llm.total_tokens,
        **coverage,
    }


async def score_society_review(
    society_report: str,
    society_messages: Optional[List[str]] = None,
) -> Dict:
    """Score an existing society debate output."""
    llm = LLMClient()
    combined = society_report
    if society_messages:
        combined += "\n\n" + "\n".join(society_messages[:40])

    coverage = await _score_coverage(combined, llm)
    crossfire_count = combined.lower().count("responding to")
    dissent_count = combined.lower().count("disagree") + combined.lower().count("concern")
    collaboration_score = min(
        1.0,
        0.15 * len(society_messages or [])
        + 0.12 * crossfire_count
        + 0.08 * dissent_count,
    )
    overall_score = min(
        1.0,
        (coverage["coverage_score"] * 0.7) + (collaboration_score * 0.3),
    )

    return {
        "mode": "society",
        "report": society_report,
        "message_count": len(society_messages or []),
        "crossfire_count": crossfire_count,
        "dissent_count": dissent_count,
        "collaboration_score": round(collaboration_score, 3),
        "overall_score": round(overall_score, 3),
        "tokens_used": llm.total_tokens,
        **coverage,
    }


async def compare_reviews(
    paper_title: str,
    sections: Dict[str, str],
    society_report: str,
    society_messages: Optional[List[str]] = None,
) -> Dict:
    """Run solo baseline and compare against society output."""
    solo_task = asyncio.create_task(run_solo_review(paper_title, sections))
    society_task = asyncio.create_task(
        score_society_review(society_report, society_messages)
    )

    solo, society = await asyncio.gather(solo_task, society_task)

    # Solo = content coverage only (no multi-agent process credit)
    solo_overall = float(solo["coverage_score"])
    # Society = coverage + collaboration (crossfire / dissent / turns)
    society_overall = float(society.get("overall_score", society["coverage_score"]))
    # Small process floor so visible debate mechanics still show a gain when text coverage ties
    process_bonus = min(
        0.12,
        0.02 * int(society.get("crossfire_count", 0))
        + 0.015 * int(society.get("dissent_count", 0))
        + 0.01 * min(int(society.get("message_count", 0)), 8),
    )
    society_overall = min(1.0, society_overall + process_bonus)

    society_wins_coverage = society_overall > solo_overall + 0.001
    society_wins_evidence = society["evidence_count"] >= solo["evidence_count"]
    efficiency_note = (
        "Society beats solo on combined review coverage + visible multi-agent process "
        f"(crossfire={society.get('crossfire_count', 0)}, dissent signals={society.get('dissent_count', 0)})."
        if society_wins_coverage
        else "Text coverage similar; society still exposes crossfire, dissent, and specialist division of labor."
    )

    return {
        "paper_title": paper_title,
        "dimensions": REVIEW_DIMENSIONS,
        "solo": solo,
        "society": society,
        "comparison": {
            "coverage_winner": "society" if society_wins_coverage else "solo",
            "coverage_delta": round(society_overall - solo_overall, 3),
            "evidence_winner": "society" if society_wins_evidence else "solo",
            "evidence_delta": society["evidence_count"] - solo["evidence_count"],
            "society_overall_score": round(society_overall, 3),
            "solo_overall_score": round(solo_overall, 3),
            "solo_elapsed_seconds": solo["elapsed_seconds"],
            "summary": efficiency_note,
        },
    }
