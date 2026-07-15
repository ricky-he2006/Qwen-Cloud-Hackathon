"""
Base classes for the Research Society agents.
Provides common functionality for all agent types.
"""

from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
import uuid
import json

from utils.llm_client import LLMClient, Message


@dataclass
class AgentMessage:
    """Represents a message from an agent in the debate."""
    agent_id: str
    agent_name: str
    role: str
    content: str
    turn: int
    timestamp: str = ""
    public: bool = True
    message_type: str = "speech"  # speech, rebuttal, planning, synthesis
    stance: str = ""
    confidence: float = 0.0
    evidence: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class TaskAssignment:
    """A subtask assigned to a specialist agent."""
    task: str
    owner_role: str
    owner_name: str
    sections: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, complete

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "owner_role": self.owner_role,
            "owner_name": self.owner_name,
            "sections": self.sections,
            "status": self.status,
        }


class AgentContext:
    """Shared context for all agents in a debate session."""

    def __init__(self):
        self.session_id: str = str(uuid.uuid4())
        self.paper_summary: str = ""
        self.paper_sections: Dict[str, str] = {}
        self.debate_history: List[AgentMessage] = []
        self.round_number: int = 0
        self.turn_number: int = 0
        self.task_assignments: List[TaskAssignment] = []
        self.dissent_ledger: List[Dict[str, Any]] = []
        self.agreement_history: List[float] = []

    def update_paper_context(self, summary: str, sections: Dict[str, str]):
        """Update the paper context for agents."""
        self.paper_summary = summary
        self.paper_sections = sections

    def add_message(self, message: AgentMessage):
        """Add a message to debate history."""
        self.debate_history.append(message)
        self.turn_number += 1

    def get_conversation_context(self, role_filter: Optional[str] = None) -> List[Dict]:
        """Get conversation history formatted for LLM."""
        context = []
        for msg in self.debate_history:
            if not role_filter or msg.role == role_filter:
                context.append({
                    "role": "user" if msg.public else "system",
                    "name": msg.agent_name,
                    "content": msg.content
                })
        return context

    def get_recent_messages(
        self,
        limit: int = 8,
        message_types: Optional[List[str]] = None,
    ) -> List[AgentMessage]:
        """Return the most recent debate messages, optionally filtered by type."""
        messages = self.debate_history
        if message_types:
            messages = [m for m in messages if m.message_type in message_types]
        return messages[-limit:]

    def format_messages_for_prompt(self, messages: List[AgentMessage]) -> str:
        """Format messages as readable debate transcript."""
        if not messages:
            return "(No prior remarks yet.)"
        lines = []
        for msg in messages:
            stance = f" [{msg.stance}]" if msg.stance else ""
            lines.append(f"{msg.agent_name}{stance}: {msg.content[:400]}")
        return "\n".join(lines)


class BaseAgent:
    """Base class for all research society agents."""

    def __init__(
        self,
        name: str,
        role: str,
        description: str = "",
        llm_client: Optional[LLMClient] = None
    ):
        self.id: str = str(uuid.uuid4())
        self.name: str = name
        self.role: str = role
        self.description: str = description
        self.llm = llm_client or LLMClient()
        self.context: Optional[AgentContext] = None

        # Agent personality and expertise
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the system prompt specific to this agent type."""
        return f"""You are {self.name}, a {self.role} in a live scientific peer-review debate.

Your role: {self.description}

Debate rules:
1. You are in a ROOM with other reviewers — respond to their claims by name, do not monologue
2. Explicitly agree or disagree with specific points others raised
3. Cite paper sections as evidence
4. Push back when you see flaws; concede when evidence is strong
5. Avoid generic paper summaries — debate the disputed claim

Be direct, evidence-based, and collegial but critical."""

    def set_context(self, context: AgentContext):
        """Set the shared debate context."""
        self.context = context

    async def speak(
        self,
        message: str,
        turn: int,
        public: bool = True,
        message_type: str = "speech",
        stance: str = "",
        confidence: float = 0.0,
        evidence: Optional[List[Dict[str, str]]] = None,
    ) -> AgentMessage:
        msg = AgentMessage(
            agent_id=self.id,
            agent_name=self.name,
            role=self.role,
            content=message,
            turn=turn,
            public=public,
            message_type=message_type,
            stance=stance,
            confidence=confidence,
            evidence=evidence or [],
        )

        if self.context:
            self.context.add_message(msg)

        return msg

    def _paper_context_snippet(self) -> str:
        paper_info = ""
        if self.context and self.context.paper_sections:
            for section, content in self.context.paper_sections.items():
                if content:
                    paper_info += f"\n\n### {section.capitalize()}\n{content[:1400]}"
        return paper_info

    def _related_literature_blurb(self, topic: str) -> str:
        """Light arXiv look-up for the literature specialist (no new APIs)."""
        if self.role != "literature_specialist":
            return ""
        try:
            from paper_ingest.fetcher import PaperFetcher

            title = ""
            if self.context and self.context.paper_sections:
                title = (self.context.paper_sections.get("title") or "")[:120]
            query = (title or topic or "machine learning")[:100]
            papers = PaperFetcher().search_arxiv(query, max_results=3) or []
            if not papers:
                return ""
            lines = ["Related arXiv hits (tool look-up — cite if relevant):"]
            for p in papers[:3]:
                lines.append(f"- [{getattr(p, 'paper_id', '')}] {getattr(p, 'title', '')[:120]}")
            return "\n".join(lines)
        except Exception:
            return ""

    async def think_opening(self, topic: str, round_num: int) -> "StructuredResponse":
        """Opening statement — positions the agent will defend when challenged."""
        from debate.structured import parse_structured_response

        paper_info = self._paper_context_snippet()
        lit_blurb = self._related_literature_blurb(topic)
        lit_block = f"\n\n{lit_blurb}" if lit_blurb else ""

        prompt = f"""Round {round_num} opening statement on: {topic}

Paper Context:{paper_info}{lit_block}

You are {self.name} ({self.role}). Give a DETAILED initial peer-review position.
Other specialists will challenge you — stake a clear, disputable claim.

Requirements:
- Stay in your specialist lane ({self.role})
- Cite at least 2 evidence anchors (section + short quote or paraphrase with numbers when present)
- Name one specific strength AND one specific concern when justified by the paper
- Do not give a generic overview; be concrete
{"- If related arXiv hits are listed, briefly say whether they support or contrast the paper" if lit_blurb else ""}

JSON only:
{{
  "summary": "4-6 sentences: clear position, one strength, one concern, tied to paper details",
  "stance": "agree|disagree|neutral",
  "confidence": 0.0-1.0,
  "evidence": [
    {{"section": "methods", "quote": "specific detail"}},
    {{"section": "results", "quote": "specific detail"}}
  ]
}}"""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.65,
            system_prompt=self.system_prompt,
            max_tokens=900,
        )
        return parse_structured_response(response)

    async def think_debate_response(
        self,
        topic: str,
        round_num: int,
        target: AgentMessage,
        round_messages: List[AgentMessage],
    ) -> "StructuredResponse":
        """Respond directly to another reviewer's claim — the core debate turn."""
        from debate.structured import parse_structured_response

        paper_info = self._paper_context_snippet()
        transcript = (
            self.context.format_messages_for_prompt(round_messages)
            if self.context
            else target.content
        )

        prompt = f"""Live debate on: {topic}

Paper Context:{paper_info}

You must respond to {target.agent_name} who said:
"{target.content[:700]}"
(Their stance: {target.stance or 'unknown'})

Earlier in this round:
{transcript}

Rules:
1. Start by addressing {target.agent_name} by name
2. Agree or disagree with their SPECIFIC claim — quote or paraphrase it
3. Bring counter-evidence from the paper or explain why their reasoning fails
4. Do NOT repeat your opening statement or give a generic paper overview

JSON only:
{{
  "summary": "2-5 sentences debating {target.agent_name}",
  "responds_to": "{target.agent_name}",
  "stance": "agree|disagree|neutral",
  "confidence": 0.0-1.0,
  "evidence": [{{"section": "section_name", "quote": "supporting text"}}]
}}"""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.75,
            system_prompt=self.system_prompt,
            max_tokens=650,
        )
        return parse_structured_response(response)

    async def think_structured(self, topic: str, round_num: int) -> "StructuredResponse":
        from debate.structured import parse_structured_response

        history = self.context.get_conversation_context() if self.context else []
        paper_info = ""
        if self.context and self.context.paper_sections:
            for section, content in self.context.paper_sections.items():
                if content:
                    paper_info += f"\n\n### {section.capitalize()}\n{content[:1000]}"

        prompt = f"""Topic: {topic}

Paper Context:{paper_info}

Previous discussion:
{json.dumps(history[-5:], indent=2)}

Respond as {self.name} ({self.role}) with JSON only:
{{
  "summary": "2-4 sentence analysis",
  "stance": "agree|disagree|neutral",
  "confidence": 0.0-1.0,
  "evidence": [{{"section": "methods", "quote": "brief quote from paper"}}]
}}"""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.7,
            system_prompt=self.system_prompt,
            max_tokens=600,
        )
        return parse_structured_response(response)

    async def think_rebuttal(
        self,
        topic: str,
        dispute: str,
        opponent: str = "",
    ) -> "StructuredResponse":
        from debate.structured import parse_structured_response

        opponent_line = f"\nYou are rebutting {opponent}." if opponent else ""
        prompt = f"""Final rebuttal on topic: {topic}
{opponent_line}

Disputed claim: {dispute}

Address the opponent directly. Defend or attack the specific claim with evidence.

JSON only:
{{
  "summary": "2-3 sentence rebuttal",
  "responds_to": "{opponent}",
  "stance": "agree|disagree|neutral",
  "confidence": 0.0-1.0,
  "evidence": [{{"section": "section_name", "quote": "supporting text"}}]
}}"""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.6,
            system_prompt=self.system_prompt,
            max_tokens=400,
        )
        return parse_structured_response(response)

    async def think(self, topic: str, round_num: int) -> str:
        """
        Process a topic and generate a response.

        Args:
            topic: The debate topic for this turn
            round_num: Current round number

        Returns:
            Agent's response text
        """
        # Get conversation context
        history = self.context.get_conversation_context() if self.context else []

        # Build prompt with paper context
        paper_info = ""
        if self.context and self.context.paper_sections:
            for section, content in self.context.paper_sections.items():
                if content and len(content) > 0:
                    paper_info += f"\n\n### {section.capitalize()}\n{content[:1000]}..."

        prompt = f"""Topic: {topic}

Paper Context:{paper_info}

Previous discussion:
{json.dumps(history[-5:], indent=2)}

Your analysis ({self.role}):"""

        # Generate response
        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.7,
            system_prompt=self.system_prompt
        )

        return response.strip()

    async def participate(self, topic: str) -> AgentMessage:
        """
        Participate in the debate on a given topic.

        Args:
            topic: The current debate topic

        Returns:
            AgentMessage with the response
        """
        if not self.context:
            raise ValueError("Agent context not set")

        response = await self.think(topic, self.context.turn_number)
        return await self.speak(response, self.context.turn_number)

    def vote(self, statement: str) -> int:
        """
        Cast a vote on a statement.

        Returns:
            1 (agree), 0 (neutral), -1 (disagree)
        """
        # This would be implemented by specialized agents
        return 0


class AgentFactory:
    """Factory for creating research society agents."""

    AGENT_TYPES = {
        'executive_moderator': {
            'name': 'Dr. Moderator',
            'role': 'executive_moderator',
            'description': 'Facilitates debate, ensures structure, and synthesizes final conclusions.'
        },
        'structure_analyst': {
            'name': 'Dr. Structure',
            'role': 'paper_structure_analyst',
            'description': 'Analyzes paper organization, logic flow, and section coherence.'
        },
        'contribution_scout': {
            'name': 'Dr. Novelty',
            'role': 'contribution_specialist',
            'description': 'Evaluates research novelty, significance, and contribution strength.'
        },
        'methodology_critic': {
            'name': 'Dr. Methods',
            'role': 'methodology_expert',
            'description': 'Scrutinizes experimental design, statistical validity, and reproducibility.'
        },
        'literature_reviewer': {
            'name': 'Dr. Context',
            'role': 'literature_specialist',
            'description': 'Contextualizes paper in field literature and evaluates citations.'
        }
    }

    @staticmethod
    def create_agent(agent_type: str) -> BaseAgent:
        """Create an agent of the specified type."""
        config = AgentFactory.AGENT_TYPES.get(agent_type)
        if not config:
            raise ValueError(f"Unknown agent type: {agent_type}")

        return BaseAgent(**config)

    @staticmethod
    def create_society(
        moderator_count: int = 1,
        analyst_count: int = 1,
        scout_count: int = 1,
        critic_count: int = 1,
        reviewer_count: int = 1
    ) -> List[BaseAgent]:
        """Create a complete agent society."""
        agents = []

        # Always create moderator(s)
        for _ in range(moderator_count):
            agents.append(AgentFactory.create_agent('executive_moderator'))

        # Add specialized agents based on counts
        for _ in range(analyst_count):
            agents.append(AgentFactory.create_agent('structure_analyst'))

        for _ in range(scout_count):
            agents.append(AgentFactory.create_agent('contribution_scout'))

        for _ in range(critic_count):
            agents.append(AgentFactory.create_agent('methodology_critic'))

        for _ in range(reviewer_count):
            agents.append(AgentFactory.create_agent('literature_reviewer'))

        return agents
