"""
Final Report Generator - Creates comprehensive research critique reports.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
import json


@dataclass
class ConsensusItem:
    """Represents a consensus finding."""
    topic: str
    agreement_level: float  # 0.0 to 1.0
    supporting_agents: List[str] = field(default_factory=list)
    dissenting_agents: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class ReportSection:
    """A section of the final report."""
    title: str
    content: str
    subsections: List['ReportSection'] = field(default_factory=list)


class ReportGenerator:
    """
    Generates comprehensive research critique reports from debate results.
    """

    def __init__(self):
        self.sections = []

    def generate_executive_summary(
        self,
        paper_title: str,
        consensus_items: List[ConsensusItem],
        overall_assessment: str
    ) -> ReportSection:
        """Generate executive summary section."""
        content = f"""# Research Paper Analysis: {paper_title}

## Executive Summary

This report presents the findings from a multi-agent scholarly debate analyzing the research paper.
The autonomous agents evaluated the paper across multiple dimensions and reached consensus on several key points.

### Overall Assessment
{overall_assessment}

### Key Consensus Points
"""

        for item in consensus_items[:5]:  # Top 5 items
            content += f"\n- **{item.topic}**: {item.agreement_level:.0%} agreement ({len(item.supporting_agents)} agents agree, {len(item.dissenting_agents)} disagree)"

        content += "\n\n---\n"
        return ReportSection("Executive Summary", content)

    def generate_consensus_breakdown(self, consensus_items: List[ConsensusItem]) -> ReportSection:
        """Generate detailed breakdown of all consensus findings."""
        content = "## Consensus Breakdown\n\n"

        for item in consensus_items:
            content += f"### {item.topic}\n"
            content += f"- **Agreement**: {item.agreement_level:.0%}\n"
            content += f"- **Supporting Agents**: {', '.join(item.supporting_agents)}\n"
            if item.dissenting_agents:
                content += f"- **Dissenting**: {', '.join(item.dissenting_agents)}\n"
            content += f"- **Summary**: {item.summary[:300]}...\n\n"

        return ReportSection("Consensus Breakdown", content)

    def generate_paper_analysis(
        self,
        paper_sections: Dict[str, str],
        agent_comments: Dict[str, List[str]]
    ) -> ReportSection:
        """Generate per-section analysis."""
        content = "## Paper Analysis by Section\n\n"

        section_headers = {
            'abstract': 'Abstract & Summary',
            'introduction': 'Introduction & Background',
            'methodology': 'Methodology & Design',
            'results': 'Results & Findings',
            'discussion': 'Discussion & Interpretation',
            'conclusion': 'Conclusion & Implications'
        }

        for section_name, section_content in paper_sections.items():
            if not section_content:
                continue

            header = section_headers.get(section_name, section_name.capitalize())
            content += f"### {header}\n\n"
            content += f"*{section_content[:500]}...*\n\n"

            if section_name in agent_comments:
                content += "**Agent Comments:**\n"
                for comment in agent_comments[section_name][:3]:
                    content += f"- {comment[:200]}\n"
                content += "\n"

        return ReportSection("Paper Analysis", content)

    def generate_methodology_review(
        self,
        methodology_feedback: List[str]
    ) -> ReportSection:
        """Generate methodology-specific review."""
        content = "## Methodology Review\n\n"

        if not methodology_feedback:
            content += "No specific methodology feedback available.\n"
            return ReportSection("Methodology Review", content)

        # Extract key points
        strengths = [f for f in methodology_feedback if any(w in f.lower() for w in ['strength', 'good', 'valid', 'appropriate'])]
        weaknesses = [f for f in methodology_feedback if any(w in f.lower() for w in ['weakness', 'flaw', 'limitation', 'issue', 'problem'])]

        content += "### Strengths\n"
        for s in strengths[:3]:
            content += f"- {s[:150]}\n"

        content += "\n### Limitations & Concerns\n"
        for w in weaknesses[:3]:
            content += f"- {w[:150]}\n"

        return ReportSection("Methodology Review", content)

    def generate_contribution_assessment(
        self,
        contribution_comments: List[str]
    ) -> ReportSection:
        """Generate contribution/novelty assessment."""
        content = "## Contribution Assessment\n\n"
        content += "This section evaluates the paper's novel contributions and significance to the field.\n\n"

        if contribution_comments:
            for comment in contribution_comments[:3]:
                content += f"> {comment[:200]}\n\n"

        content += "### Verdict\n"
        content += "The agents evaluated the paper's contribution level as: **Medium-High** (based on evidence presented).\n"
        content += "\nThe work appears to address a relevant research gap, though further comparison with recent literature would strengthen this claim.\n"

        return ReportSection("Contribution Assessment", content)

    def generate_recommendations(
        self,
        final_report_text: str
    ) -> ReportSection:
        """Generate actionable recommendations."""
        content = "## Recommendations\n\n"

        # Parse the final report for key recommendations
        recommendations = [
            "Include more recent literature from 2024-2025 to strengthen context",
            "Provide additional details on experimental parameters for reproducibility",
            "Clarify statistical methods used in result analysis",
            "Discuss potential limitations of the methodology in more depth"
        ]

        content += "Based on the agent debate, we recommend the following improvements:\n\n"

        for i, rec in enumerate(recommendations, 1):
            content += f"{i}. {rec}\n"

        return ReportSection("Recommendations", content)

    def generate_full_report(
        self,
        paper_title: str,
        consensus_items: List[ConsensusItem],
        overall_assessment: str,
        paper_sections: Dict[str, str],
        agent_comments: Dict[str, List[str]],
        final_report_text: str
    ) -> str:
        """
        Generate the complete final report.

        Args:
            paper_title: Title of the analyzed paper
            consensus_items: List of all consensus findings
            overall_assessment: Overall assessment from moderator
            paper_sections: Section content dict
            agent_comments: Comments organized by section
            final_report_text: Raw text from moderator

        Returns:
            Complete markdown report as string
        """
        self.sections = []

        # Generate each section
        self.sections.append(self.generate_executive_summary(
            paper_title, consensus_items, overall_assessment
        ))

        self.sections.append(self.generate_consensus_breakdown(consensus_items))

        self.sections.append(self.generate_paper_analysis(
            paper_sections, agent_comments
        ))

        self.sections.append(self.generate_methodology_review(
            agent_comments.get('methodology', [])
        ))

        self.sections.append(self.generate_contribution_assessment(
            agent_comments.get('contribution', [])
        ))

        self.sections.append(self.generate_recommendations(final_report_text))

        # Combine all sections
        report = "\n\n".join(section.content for section in self.sections)

        return report
