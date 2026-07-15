"""
Executive Moderator Agent.
Manages the debate flow, identifies分歧 points, and synthesizes conclusions.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json
import re

from .base import BaseAgent, AgentMessage, AgentContext, TaskAssignment
from utils.llm_client import Message
from utils.json_parse import parse_json_payload


class ExecutiveModerator(BaseAgent):
    """
    The CEO of the research society.
    Manages debate structure, ensures civility, and drives toward consensus.
    """

    def __init__(self, llm_client=None):
        super().__init__(
            name="Dr. Moderator",
            role="executive_moderator",
            description=(
                "Facilitates structured scientific debate, identifies areas of agreement/disagreement, "
                "and synthesizes final conclusions from the research team."
            ),
            llm_client=llm_client
        )

        self.system_prompt = """You are Dr. Moderator, the executive moderator of a scientific research society.

Your responsibilities:
1. Design debate topics covering paper sections (abstract, intro, methods, results, discussion)
2. Ensure all agents have equal speaking time
3. Identify consensus points and disagreements clearly
4. Guide discussion toward evidence-based conclusions
5. Summarize key findings and remaining uncertainties

Debate format guidance:
- Start with high-level overview of each paper section
- Drill down into methodology for experts
- Focus discussions on claims and evidence
- When 3/5 agents agree, mark as consensus
- Document dissenting views accurately

Be authoritative but fair. Encourage constructive criticism.
"""

    ROLE_TO_AGENT = {
        "paper_structure_analyst": "structure_analyst",
        "contribution_specialist": "contribution_scout",
        "methodology_expert": "methodology_critic",
        "literature_specialist": "literature_reviewer",
        "structure_analyst": "structure_analyst",
        "contribution_scout": "contribution_scout",
        "methodology_critic": "methodology_critic",
        "literature_reviewer": "literature_reviewer",
    }

    DEFAULT_ASSIGNMENTS = [
        ("Analyze paper organization and logical flow", "paper_structure_analyst", ["introduction", "abstract"]),
        ("Evaluate novelty and contribution significance", "contribution_specialist", ["introduction", "conclusion"]),
        ("Scrutinize methodology and reproducibility", "methodology_expert", ["methodology", "results"]),
        ("Contextualize within existing literature", "literature_specialist", ["introduction", "discussion"]),
    ]

    async def decompose_tasks(
        self,
        paper_summary: str,
        sections: Dict[str, str],
        agents: List[BaseAgent],
    ) -> List[TaskAssignment]:
        """Decompose paper review into specialist subtasks."""
        role_to_name = {a.role: a.name for a in agents}
        section_keys = list(sections.keys())

        section_previews = {
            k: (v or "")[:280].replace("\n", " ")
            for k, v in sections.items()
            if v
        }
        prompt = f"""Decompose peer review of this paper into exactly 4 SPECIALIST subtasks.

Paper: {paper_summary[:1000]}
Sections available: {json.dumps(section_keys)}
Section previews: {json.dumps(section_previews)[:2500]}

Agents and roles (use these owner_role keys exactly):
- paper_structure_analyst: organization, clarity, logic flow, missing pieces
- contribution_specialist: novelty, significance, claimed vs delivered contribution
- methodology_expert: design, statistics, reproducibility, confounds
- literature_specialist: prior work context, citation gaps, positioning

Each task description must be PAPER-SPECIFIC (name methods/claims from the previews), not generic.

Return JSON array only:
[{{"task": "detailed subtask for this paper", "owner_role": "role_key", "sections": ["section_name"]}}]"""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.35,
            max_tokens=800,
            system_prompt=self.system_prompt,
        )

        assignments: List[TaskAssignment] = []
        data = parse_json_payload(response)
        try:
            if isinstance(data, list):
                for item in data[:4]:
                    role = item.get("owner_role", "")
                    assignments.append(TaskAssignment(
                        task=item.get("task", "Review subsection"),
                        owner_role=role,
                        owner_name=role_to_name.get(role, "Specialist"),
                        sections=item.get("sections", []),
                        status="pending",
                    ))
        except (TypeError, AttributeError):
            pass

        if not assignments:
            for task, role, secs in self.DEFAULT_ASSIGNMENTS:
                assignments.append(TaskAssignment(
                    task=task,
                    owner_role=role,
                    owner_name=role_to_name.get(role, role),
                    sections=[s for s in secs if s in section_keys] or section_keys[:1],
                    status="pending",
                ))

        if self.context:
            self.context.task_assignments = assignments
        return assignments

    async def set_agenda(
        self,
        paper_summary: str,
        sections: Dict[str, str],
        round_num: int
    ) -> List[str]:
        """
        Create debate topics for the current round.

        Args:
            paper_summary: Summary of the paper
            sections: Dictionary of section name -> content
            round_num: Current round number

        Returns:
            List of debate topics for this round
        """
        # Get recent history to avoid repetition
        history = self.context.get_conversation_context() if self.context else []

        prompt = f"""Create 3-5 focused debate topics for Round {round_num}.

Paper Summary: {paper_summary[:1000]}

Available Sections:
{json.dumps(list(sections.keys()), indent=2)}

Guidelines:
- Each round should focus on different aspects
- Topics should be specific enough for evidence-based discussion
- Progress from overview to deeper analysis

Return a JSON array of debate topics."""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.5,
            max_tokens=500,
            system_prompt=self.system_prompt,
        )

        try:
            topics = self._parse_agenda_topics(response)
            return topics if topics else ["General discussion of paper"]
        except Exception:
            return ["General discussion of paper"]

    def _parse_agenda_topics(self, raw: str) -> List[str]:
        """Extract clean topic strings from LLM output."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        candidates: List = []
        try:
            data = json.loads(text)
            if isinstance(data, list):
                candidates = data
            elif isinstance(data, dict):
                candidates = data.get("topics", data.get("debate_topics", []))
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    candidates = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        if not candidates:
            candidates = []
            for line in text.split("\n"):
                line = line.strip().strip("-*0123456789. ")
                if len(line) > 10:
                    candidates.append(line)

        topics: List[str] = []
        for item in candidates[:5]:
            cleaned = self._clean_topic(item)
            if cleaned and cleaned not in topics:
                topics.append(cleaned)
        return topics

    @staticmethod
    def _clean_topic(item) -> str:
        if isinstance(item, dict):
            return str(item.get("topic", item.get("name", ""))).strip()
        if not isinstance(item, str):
            return str(item).strip()
        text = item.strip()
        match = re.search(r'"topic"\s*:\s*"([^"]+)"', text)
        if match:
            return match.group(1)
        return text.strip('",{} ')

    async def synthesize_round(
        self,
        round_num: int,
        topic: str,
        round_messages: Optional[List[AgentMessage]] = None,
    ) -> Tuple[str, Dict[str, int]]:
        if not self.context:
            return "No context available.", {}

        votes = {"agree": 0, "disagree": 0, "neutral": 0}
        agent_statements = round_messages or []

        # One vote per agent (latest stance) — matches consensus detector
        latest_by_agent: Dict[str, AgentMessage] = {}
        for msg in agent_statements:
            latest_by_agent[msg.agent_name] = msg

        for msg in latest_by_agent.values():
            stance = (msg.stance or "").lower()
            if stance == "agree":
                votes["agree"] += 1
            elif stance == "disagree":
                votes["disagree"] += 1
            elif stance == "neutral":
                votes["neutral"] += 1
            else:
                content_lower = msg.content.lower()
                if any(w in content_lower for w in ["agree", "support", "valid", "strong"]):
                    votes["agree"] += 1
                elif any(w in content_lower for w in ["disagree", "counter", "weakness", "flaw"]):
                    votes["disagree"] += 1
                else:
                    votes["neutral"] += 1

        prompt = f"""Synthesize Round {round_num} discussion on: "{topic}"

Agent Statements ({len(agent_statements)}):
{chr(10).join(f"- [{m.agent_name}] ({m.stance or 'neutral'}) {m.content[:200]}" for m in agent_statements)}

Vote Counts (1 per agent): {votes}

Provide a concise summary that:
1. Identifies consensus points
2. Lists key disagreements
3. Notes evidence quality

Return the summary as plain text."""

        synthesis = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.6,
            max_tokens=400,
            system_prompt=self.system_prompt,
        )

        return synthesis.strip(), votes

    async def declare_consensus(
        self,
        topic: str,
        votes: Dict[str, int],
        threshold: float = 0.6
    ) -> Tuple[bool, str]:
        """
        Declare whether consensus was reached.

        Args:
            topic: The topic discussed
            votes: Vote counts dictionary
            threshold: Fraction needed for consensus (default 60%)

        Returns:
            Tuple of (consensus_reached, explanation)
        """
        total = sum(votes.values())
        if total == 0:
            return False, "No votes recorded"

        agree_fraction = votes.get('agree', 0) / total

        prompt = f"""Topic: {topic}

Votes: {json.dumps(votes)}
Agreement fraction: {agree_fraction:.1%}
Consensus threshold: {threshold:.0%}

Did consensus reach the threshold?
Respond with JSON:
{{"consensus_reached": true/false, "explanation": "brief explanation"}}"""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.3,
            max_tokens=200,
            system_prompt=self.system_prompt,
        )

        result = parse_json_payload(response)
        if isinstance(result, dict):
            return result.get("consensus_reached", False), result.get("explanation", "")
        # Fallback based on vote counts
        reached = agree_fraction >= threshold
        explanation = (
            f"Consensus {'reached' if reached else 'not reached'}: "
            f"{votes.get('agree', 0)}/{total} agents agreed ({agree_fraction:.0%})"
        )
        return reached, explanation

    async def close_debate(self) -> str:
        """Generate final synthesis after all rounds complete."""
        dissent = ""
        if self.context and self.context.dissent_ledger:
            dissent = "\n\nDissenting opinions:\n" + "\n".join(
                f"- {d['agent_name']}: {d['position']}" for d in self.context.dissent_ledger
            )

        history = self.context.get_conversation_context() if self.context else []
        prompt = f"""Final Research Society Debate Synthesis

Debate history ({len(history)} messages):
{json.dumps(history[-12:], indent=2)}
{dissent}

Generate a comprehensive markdown report with:
1. Executive Summary
2. Consensus Points
3. Key Disagreements
4. Methodology Assessment
5. Contribution Significance
6. Limitations
7. Final Verdict (ACCEPT / REVISE / REJECT) with justification
8. Minority Opinions (dissenting views preserved)"""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.5,
            max_tokens=1000,
            system_prompt=self.system_prompt,
        )
        return response.strip()

    async def generate_verdict(self) -> Dict:
        """Generate structured verdict card for UI."""
        history = self.context.get_conversation_context() if self.context else []
        dissent = self.context.dissent_ledger if self.context else []

        prompt = f"""Based on this research society debate, produce a verdict card as JSON only:

Debate excerpt:
{json.dumps(history[-8:], indent=2)}

Dissent ledger:
{json.dumps(dissent, indent=2)}

Return:
{{
  "verdict": "ACCEPT|REVISE|REJECT",
  "scores": {{"novelty": 1-10, "methods": 1-10, "clarity": 1-10, "impact": 1-10}},
  "consensus_summary": "one sentence",
  "dissent_summary": "one sentence about minority views"
}}"""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.3,
            max_tokens=400,
            system_prompt=self.system_prompt,
        )

        data = parse_json_payload(response)
        if isinstance(data, dict):
            data["dissent_ledger"] = dissent
            return data
        return {
            "verdict": "REVISE",
            "scores": {"novelty": 7, "methods": 6, "clarity": 7, "impact": 6},
            "consensus_summary": "Agents identified both strengths and methodological concerns.",
            "dissent_summary": "Minority views recorded in dissent ledger.",
            "dissent_ledger": dissent,
        }
