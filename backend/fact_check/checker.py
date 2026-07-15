"""
Fact Checker Agent - Cross-references claims with external sources.
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json
import re

from utils.llm_client import LLMClient, Message
from paper_ingest.fetcher import PaperFetcher
from utils.json_parse import parse_json_payload


@dataclass
class VerificationResult:
    """Result of fact verification."""
    claim: str
    claim_id: str
    is_verified: bool
    confidence: float  # 0.0 to 1.0
    supporting_sources: List[str] = field(default_factory=list)
    contradicting_sources: List[str] = field(default_factory=list)
    cross_references: List[Dict] = field(default_factory=list)


@dataclass
class Claim:
    """A claim extracted from a paper."""
    text: str
    section: str
    page_number: Optional[int] = None
    context: str = ""


class FactChecker:
    """
    Checks claims against external knowledge sources.
    Uses LLM for reasoning and arXiv/DOI lookups for cross-referencing.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.fetcher = PaperFetcher()

    async def extract_claims(self, paper_sections: Dict[str, str]) -> List[Claim]:
        """
        Extract verifiable claims from paper sections.

        Args:
            paper_sections: Dictionary of section name -> content

        Returns:
            List of Claim objects
        """
        # Combine all sections for claim extraction
        combined_text = "\n\n".join(
            f"## {section}\n{content}"
            for section, content in paper_sections.items()
            if content
        )

        prompt = f"""Extract all verifiable claims from this scientific paper.

Paper Content:
{combined_text[:5000]}

Instructions:
1. Identify specific claims (not general statements)
2. Extract claims about methods, results, conclusions
3. Include numerical claims and comparisons
4. Format as JSON array of objects with: text, section

Return ONLY valid JSON."""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.3,
            max_tokens=1500
        )

        claims_data = parse_json_payload(response)
        if isinstance(claims_data, list):
            claims = [
                Claim(
                    text=c.get("text", ""),
                    section=c.get("section", "Unknown"),
                    context=c.get("context", ""),
                )
                for c in claims_data
                if isinstance(c, dict)
            ]
            if claims:
                return claims
        return self._fallback_extract_claims(combined_text)

    def _fallback_extract_claims(self, text: str) -> List[Claim]:
        """Fallback claim extraction using pattern matching."""
        claims = []

        # Pattern for numerical claims
        num_pattern = r'(\d+(?:\.\d+)?)\s*(%|times|higher|lower|x greater)\b'
        for match in re.finditer(num_pattern, text, re.IGNORECASE):
            claims.append(Claim(
                text=match.group(0),
                section="Results",
                context=f"Context: {text[max(0, match.start()-50):match.end()+50]}"
            ))

        # Pattern for comparison claims
        comp_pattern = r'(?i)(better|superior|higher|lower|improved)\s+than'
        for match in re.finditer(comp_pattern, text):
            claims.append(Claim(
                text=match.group(0),
                section="Results",
                context=f"Context: {text[max(0, match.start()-50):match.end()+100]}"
            ))

        # Remove duplicates
        seen = set()
        unique_claims = []
        for claim in claims:
            key = (claim.text.lower(), claim.section)
            if key not in seen:
                seen.add(key)
                unique_claims.append(claim)

        return unique_claims[:20]  # Limit to top 20 claims

    async def verify_claim(
        self,
        claim: Claim,
        num_references: int = 3
    ) -> VerificationResult:
        """
        Verify a single claim using cross-referencing.

        Args:
            claim: The claim to verify
            num_references: Number of related papers to fetch

        Returns:
            VerificationResult with findings
        """
        # Generate search query from claim
        query_prompt = f"""Generate a search query for finding papers that support or contradict this claim.

Claim: "{claim.text}"

Return ONLY the search query string, 5-10 words max."""

        search_query = (
            await self.llm.generate_async(
                messages=[Message("user", query_prompt)],
                temperature=0.2,
                max_tokens=50,
            )
        ).strip()

        # Search for related papers
        try:
            related_papers = self.fetcher.search_arxiv(search_query, num_references)
        except Exception:
            related_papers = []

        cross_refs = []
        for paper in related_papers[:3]:
            cross_refs.append({
                'title': paper.title,
                'arxiv_id': paper.paper_id,
                'url': paper.url
            })

        # Analyze claims from related papers
        analysis_prompt = f"""Analyze whether this claim is supported, contradicted, or neutral based on related research.

Claim to verify: "{claim.text}"

Related Papers:
{chr(10).join(f"- [{p['arxiv_id']}] {p['title']}" for p in cross_refs)}

Provide analysis with:
1. Support level (strong/moderate/neutral/contradicting)
2. Key evidence from related work
3. Confidence score (0-1)

Format as JSON."""

        analysis = await self.llm.generate_async(
            messages=[Message("user", analysis_prompt)],
            temperature=0.3,
            max_tokens=800
        )

        result = parse_json_payload(analysis)
        if isinstance(result, dict):
            return VerificationResult(
                claim=claim.text,
                claim_id=f"claim_{hash(claim.text) % 10000:04d}",
                is_verified=result.get("support_level", "neutral")
                in ["strong", "moderate"],
                confidence=float(
                    result.get("confidence_score", result.get("confidence", 0.5))
                ),
                cross_references=cross_refs,
            )
        return VerificationResult(
            claim=claim.text,
            claim_id=f"claim_{hash(claim.text) % 10000:04d}",
            is_verified=False,
            confidence=0.3,
            cross_references=cross_refs,
        )

    async def verify_all_claims(
        self,
        paper_sections: Dict[str, str],
        max_claims: int = 10
    ) -> List[VerificationResult]:
        """
        Verify multiple claims from a paper.

        Args:
            paper_sections: Paper content by section
            max_claims: Maximum claims to verify

        Returns:
            List of verification results
        """
        claims = await self.extract_claims(paper_sections)
        claims = claims[:max_claims]

        results = []
        for claim in claims:
            result = await self.verify_claim(claim)
            results.append(result)

        return results

    async def generate_fact_check_report(
        self,
        paper_sections: Dict[str, str]
    ) -> str:
        """
        Generate a comprehensive fact-check report.

        Args:
            paper_sections: Paper content by section

        Returns:
            Markdown formatted report
        """
        results = await self.verify_all_claims(paper_sections)

        report = "# Fact-Check Report\n\n"

        verified_count = sum(1 for r in results if r.is_verified)
        report += f"**Summary**: {verified_count}/{len(results)} claims verified ({verified_count/len(results)*100:.0f}%)\n\n"

        report += "## Claim-by-Claim Analysis\n\n"
        for result in results:
            status = "VERIFIED" if result.is_verified else "UNVERIFIED"
            report += f"### [{status}] {result.claim_id}\n"
            report += f"*{result.claim}*\n\n"
            report += f"- Confidence: {result.confidence:.0%}\n"

            if result.cross_references:
                report += "\n**Cross-References:**\n"
                for ref in result.cross_references[:2]:
                    report += f"- [{ref['arxiv_id']}] {ref['title']}\n"

            report += "\n---\n\n"

        return report
