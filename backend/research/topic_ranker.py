"""
Topic research — discover papers, debate each candidate, rank best fits.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from agents.base import AgentFactory
from agents.executive_moderator import ExecutiveModerator
from debate.manager import DebateManager
from paper_ingest.discovery import discover_from_request
from paper_ingest.fetcher import PaperFetcher
from utils.llm_client import LLMClient, Message

EventCallback = Callable[[Dict[str, Any]], Awaitable[None]]


@dataclass
class PaperEvaluation:
    rank: int = 0
    paper_id: str = ""
    title: str = ""
    identifier: str = ""
    url: str = ""
    source: str = ""
    abstract_fit_score: float = 0.0
    debate_fit_score: float = 0.0
    overall_score: float = 0.0
    verdict: str = ""
    consensus_summary: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendation: str = ""
    rounds_completed: int = 0
    message_count: int = 0
    sections_loaded: List[str] = field(default_factory=list)
    final_report: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "paper_id": self.paper_id,
            "title": self.title,
            "identifier": self.identifier,
            "url": self.url,
            "source": self.source,
            "abstract_fit_score": self.abstract_fit_score,
            "debate_fit_score": self.debate_fit_score,
            "overall_score": self.overall_score,
            "verdict": self.verdict,
            "consensus_summary": self.consensus_summary,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendation": self.recommendation,
            "rounds_completed": self.rounds_completed,
            "message_count": self.message_count,
            "sections_loaded": self.sections_loaded,
            "final_report": self.final_report[:1500],
        }


def _parse_json_object(raw: str) -> dict:
    from utils.json_parse import parse_json_payload

    data = parse_json_payload(raw)
    if isinstance(data, dict):
        return data
    raise json.JSONDecodeError("No JSON object found", raw or "", 0)


async def _emit(on_event: Optional[EventCallback], event: Dict[str, Any]) -> None:
    if on_event:
        await on_event(event)


async def shortlist_candidates(
    user_goal: str,
    candidates: List[Dict],
    papers_to_debate: int,
    llm: Optional[LLMClient] = None,
) -> List[Dict]:
    """LLM-rank discovery results by fit to the research goal."""
    if not candidates:
        return []

    llm = llm or LLMClient()
    papers_to_debate = min(papers_to_debate, len(candidates))

    listing = []
    for i, c in enumerate(candidates):
        listing.append(
            f"[{i}] {c.get('title', '')}\n"
            f"Abstract: {(c.get('abstract') or '')[:400]}\n"
            f"Source: {c.get('source', '')} | Date: {c.get('published_date', '')}"
        )

    prompt = f"""Research goal:
"{user_goal}"

Candidate papers:
{chr(10).join(listing)}

Pick the {papers_to_debate} papers that BEST match the research goal.
Score each 0.0-1.0 for relevance.

Return JSON only:
{{
  "shortlist": [
    {{"index": 0, "fit_score": 0.85, "reason": "why it matches"}},
    ...
  ]
}}"""

    response = await llm.generate_async(
        messages=[Message("user", prompt)],
        temperature=0.2,
        max_tokens=800,
    )

    try:
        data = _parse_json_object(response)
        shortlist = []
        for item in data.get("shortlist", [])[:papers_to_debate]:
            idx = int(item.get("index", -1))
            if 0 <= idx < len(candidates):
                enriched = dict(candidates[idx])
                enriched["abstract_fit_score"] = float(item.get("fit_score", 0.5))
                enriched["shortlist_reason"] = item.get("reason", "")
                shortlist.append(enriched)
        if shortlist:
            return shortlist
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    return [
        {**c, "abstract_fit_score": 0.5, "shortlist_reason": "Discovery order fallback"}
        for c in candidates[:papers_to_debate]
    ]


async def _score_debate_fit(
    user_goal: str,
    title: str,
    final_report: str,
    verdict: Dict[str, Any],
    llm: LLMClient,
) -> Dict[str, Any]:
    prompt = f"""Research goal: "{user_goal}"

Paper: {title}

Society review verdict: {verdict.get('verdict', 'REVISE')}
Consensus: {verdict.get('consensus_summary', '')[:500]}

Review excerpt:
{final_report[:2500]}

Score how well this paper serves the research goal after specialist review.
Return JSON only:
{{
  "debate_fit_score": 0.0-1.0,
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "recommendation": "1-2 sentences why or why not for this goal"
}}"""

    response = await llm.generate_async(
        messages=[Message("user", prompt)],
        temperature=0.3,
        max_tokens=500,
    )
    try:
        data = _parse_json_object(response)
        if not isinstance(data, dict):
            raise TypeError("expected object")
        return data
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "debate_fit_score": 0.5,
            "strengths": [],
            "weaknesses": [],
            "recommendation": "Review completed.",
        }


async def _load_paper_sections(candidate: Dict) -> tuple[Dict[str, str], str, str]:
    fetcher = PaperFetcher()
    identifier = candidate.get("identifier") or candidate.get("paper_id") or candidate.get("title", "")
    paper_type, metadata = fetcher.identify_paper(identifier)

    if not metadata or not metadata.title:
        abstract = candidate.get("abstract", "")
        return ({"abstract": abstract} if abstract else {}, paper_type or "unknown", identifier)

    sections = fetcher.extract_sections_from_metadata(metadata, paper_type)
    if not sections:
        if metadata.abstract:
            sections = {"abstract": metadata.abstract}
        elif candidate.get("abstract"):
            sections = {"abstract": candidate["abstract"]}

    paper_id = metadata.paper_id or candidate.get("paper_id", identifier)
    return sections, paper_type or "unknown", paper_id


async def evaluate_paper_with_debate(
    user_goal: str,
    candidate: Dict,
    debate_config: Dict[str, Any],
    on_event: Optional[EventCallback] = None,
    paper_index: int = 0,
    total_papers: int = 1,
) -> PaperEvaluation:
    title = candidate.get("title", "Unknown")
    await _emit(on_event, {
        "type": "topic_paper_review_started",
        "paper_index": paper_index,
        "total_papers": total_papers,
        "title": title,
    })

    sections, paper_type, paper_id = await _load_paper_sections(candidate)
    if not sections:
        return PaperEvaluation(
            paper_id=paper_id,
            title=title,
            identifier=candidate.get("identifier", ""),
            url=candidate.get("url", ""),
            source=candidate.get("source", ""),
            abstract_fit_score=float(candidate.get("abstract_fit_score", 0)),
            recommendation="Could not load text — skipped full debate.",
        )

    moderator = ExecutiveModerator()
    agents = [
        AgentFactory.create_agent("structure_analyst"),
        AgentFactory.create_agent("contribution_scout"),
        AgentFactory.create_agent("methodology_critic"),
        AgentFactory.create_agent("literature_reviewer"),
    ]

    async def on_message(msg, round_num: int) -> None:
        await _emit(on_event, {
            "type": "topic_paper_agent_message",
            "paper_index": paper_index,
            "title": title,
            "round_num": round_num,
            "agent_name": msg.agent_name,
            "content": msg.content[:300],
            "message_type": msg.message_type,
        })

    manager = DebateManager(
        moderator=moderator,
        agents=agents,
        max_rounds=debate_config.get("max_rounds", 2),
        min_rounds=debate_config.get("min_rounds", 1),
        crossfire_passes=debate_config.get("crossfire_passes", 1),
        consensus_threshold=debate_config.get("consensus_threshold", 0.8),
        on_message=on_message,
        on_event=on_event,
    )

    session = await manager.initialize_session(
        paper_summary=f"Paper: {title}\nResearch goal: {user_goal}",
        sections=sections,
    )
    result = await manager.run_debate(session)

    llm = LLMClient()
    fit = await _score_debate_fit(
        user_goal,
        title,
        result.final_report or "",
        result.verdict or {},
        llm,
    )

    abstract_fit = float(candidate.get("abstract_fit_score", 0.5))
    debate_fit = float(fit.get("debate_fit_score", 0.5))
    overall = round(0.35 * abstract_fit + 0.65 * debate_fit, 3)

    evaluation = PaperEvaluation(
        paper_id=paper_id,
        title=title,
        identifier=candidate.get("identifier", ""),
        url=candidate.get("url", ""),
        source=candidate.get("source", paper_type),
        abstract_fit_score=abstract_fit,
        debate_fit_score=debate_fit,
        overall_score=overall,
        verdict=(result.verdict or {}).get("verdict", ""),
        consensus_summary=(result.verdict or {}).get("consensus_summary", ""),
        strengths=fit.get("strengths", []) or [],
        weaknesses=fit.get("weaknesses", []) or [],
        recommendation=fit.get("recommendation", ""),
        rounds_completed=len(result.rounds),
        message_count=sum(len(r.messages) for r in result.rounds),
        sections_loaded=list(sections.keys()),
        final_report=result.final_report or "",
    )

    await _emit(on_event, {
        "type": "topic_paper_review_complete",
        "paper_index": paper_index,
        "evaluation": evaluation.to_dict(),
    })
    return evaluation


async def synthesize_final_ranking(
    user_goal: str,
    evaluations: List[PaperEvaluation],
    llm: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    llm = llm or LLMClient()
    if not evaluations:
        return {"summary": "No papers could be evaluated.", "ranked": []}

    for ev in evaluations:
        ev.overall_score = round(
            0.35 * ev.abstract_fit_score + 0.65 * ev.debate_fit_score,
            3,
        )

    evaluations.sort(key=lambda e: e.overall_score, reverse=True)
    for i, ev in enumerate(evaluations, start=1):
        ev.rank = i

    bullets = []
    for ev in evaluations:
        bullets.append(
            f"- {ev.title} | overall={ev.overall_score} | verdict={ev.verdict} | "
            f"{ev.recommendation}"
        )

    prompt = f"""Research goal: "{user_goal}"

After agent-society debates, here are the papers:

{chr(10).join(bullets)}

Write a final recommendation for the researcher.
Return JSON only:
{{
  "summary": "2-4 sentences on which papers are best and why",
  "top_pick": "exact title of #1 paper",
  "honorable_mentions": ["title2", "title3"]
}}"""

    response = await llm.generate_async(
        messages=[Message("user", prompt)],
        temperature=0.4,
        max_tokens=600,
    )
    try:
        synthesis = _parse_json_object(response)
    except json.JSONDecodeError:
        synthesis = {
            "summary": f"Top pick: {evaluations[0].title}",
            "top_pick": evaluations[0].title,
            "honorable_mentions": [e.title for e in evaluations[1:3]],
        }

    return {
        "summary": synthesis.get("summary", ""),
        "top_pick": synthesis.get("top_pick", evaluations[0].title if evaluations else ""),
        "honorable_mentions": synthesis.get("honorable_mentions", []),
        "ranked": [e.to_dict() for e in evaluations],
    }


async def research_topic(
    user_goal: str,
    max_discover: int = 8,
    papers_to_debate: int = 3,
    top_recommendations: int = 3,
    expand_query: bool = True,
    debate_config: Optional[Dict[str, Any]] = None,
    on_event: Optional[EventCallback] = None,
) -> Dict[str, Any]:
    """
    Full pipeline: discover → shortlist → debate each → rank recommendations.
    """
    user_goal = user_goal.strip()
    if not user_goal:
        raise ValueError("Research goal cannot be empty")

    debate_config = debate_config or {
        "max_rounds": 2,
        "min_rounds": 1,
        "crossfire_passes": 1,
        "consensus_threshold": 0.8,
    }
    papers_to_debate = max(1, min(papers_to_debate, 5))
    max_discover = max(papers_to_debate, min(max_discover, 15))

    await _emit(on_event, {
        "type": "topic_research_started",
        "goal": user_goal,
        "papers_to_debate": papers_to_debate,
    })

    discovery = await discover_from_request(
        user_goal,
        max_results=max_discover,
        use_llm_expansion=expand_query,
    )
    candidates = discovery.get("results", [])

    await _emit(on_event, {
        "type": "topic_papers_discovered",
        "count": len(candidates),
        "search_queries": discovery.get("search_queries", []),
    })

    if not candidates:
        return {
            "success": False,
            "goal": user_goal,
            "error": "No papers found for this topic.",
            "discovery": discovery,
        }

    shortlist = await shortlist_candidates(user_goal, candidates, papers_to_debate)
    await _emit(on_event, {
        "type": "topic_shortlist_ready",
        "shortlist": [
            {
                "title": p.get("title"),
                "abstract_fit_score": p.get("abstract_fit_score"),
                "reason": p.get("shortlist_reason", ""),
            }
            for p in shortlist
        ],
    })

    evaluations: List[PaperEvaluation] = []
    for idx, candidate in enumerate(shortlist):
        try:
            evaluation = await evaluate_paper_with_debate(
                user_goal,
                candidate,
                debate_config,
                on_event=on_event,
                paper_index=idx + 1,
                total_papers=len(shortlist),
            )
            evaluations.append(evaluation)
        except Exception as exc:
            print(f"Paper evaluation failed for {candidate.get('title')}: {exc}")
            evaluations.append(
                PaperEvaluation(
                    title=candidate.get("title", ""),
                    identifier=candidate.get("identifier", ""),
                    recommendation=f"Evaluation failed: {exc}",
                )
            )

    ranking = await synthesize_final_ranking(user_goal, evaluations)
    top = ranking["ranked"][:top_recommendations]

    result = {
        "success": True,
        "goal": user_goal,
        "search_queries": discovery.get("search_queries", []),
        "candidates_found": len(candidates),
        "papers_debated": len(evaluations),
        "summary": ranking.get("summary", ""),
        "top_pick": ranking.get("top_pick", ""),
        "honorable_mentions": ranking.get("honorable_mentions", []),
        "ranked_papers": ranking.get("ranked", []),
        "recommendations": top,
        "all_candidates": candidates,
    }

    await _emit(on_event, {
        "type": "topic_research_complete",
        **{k: result[k] for k in (
            "goal", "summary", "top_pick", "honorable_mentions",
            "recommendations", "papers_debated", "candidates_found",
        )},
    })
    return result
