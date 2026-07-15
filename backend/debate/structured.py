"""Structured agent response parsing and vote helpers."""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from utils.json_parse import parse_json_payload, strip_json_fences

__all__ = [
    "StructuredResponse",
    "REVIEW_DIMENSIONS",
    "parse_structured_response",
    "stance_to_vote",
    "parse_json_payload",
    "strip_json_fences",
]


@dataclass
class StructuredResponse:
    summary: str
    stance: str = "neutral"  # agree, disagree, neutral
    confidence: float = 0.5
    evidence: List[Dict[str, str]] = field(default_factory=list)
    responds_to: str = ""

    def to_display(self) -> str:
        lines = []
        if self.responds_to:
            lines.append(f"→ Responding to {self.responds_to}:")
        lines.append(self.summary)
        if self.evidence:
            lines.append("")
            lines.append("Evidence:")
            for item in self.evidence[:3]:
                section = item.get("section", "unknown")
                quote = item.get("quote", "")[:120]
                lines.append(f"  • [{section}] {quote}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "stance": self.stance,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


REVIEW_DIMENSIONS = [
    "methodology_rigor",
    "novelty_assessment",
    "clarity_and_organization",
    "limitations_identified",
    "literature_context",
    "reproducibility",
    "statistical_validity",
    "contribution_significance",
]


def parse_structured_response(raw: str) -> StructuredResponse:
    """Parse LLM JSON output with graceful fallback."""
    data = parse_json_payload(raw)
    try:
        if isinstance(data, dict):
            return StructuredResponse(
                summary=data.get("summary", raw[:500]),
                stance=data.get("stance", "neutral"),
                confidence=float(data.get("confidence", 0.5)),
                evidence=data.get("evidence", []) or [],
                responds_to=data.get("responds_to", "") or "",
            )
    except (TypeError, ValueError):
        pass

    stance = "neutral"
    lower = raw.lower()
    if any(w in lower for w in ("disagree", "flaw", "weakness", "concern")):
        stance = "disagree"
    elif any(w in lower for w in ("agree", "support", "valid", "strong")):
        stance = "agree"

    return StructuredResponse(summary=raw.strip(), stance=stance, confidence=0.5)


def stance_to_vote(stance: str) -> int:
    if stance == "agree":
        return 1
    if stance == "disagree":
        return -1
    return 0
