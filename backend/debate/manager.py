"""
Debate Manager - Orchestrates planning, multi-round debate, rebuttals, and consensus.
"""

import asyncio
from typing import List, Dict, Optional, Tuple, Callable, Awaitable, Any
from dataclasses import dataclass, field
from datetime import datetime

from agents.base import BaseAgent, AgentContext, AgentMessage, TaskAssignment
from agents.executive_moderator import ExecutiveModerator
from debate.consensus import ConsensusDetector, Vote
from debate.structured import stance_to_vote

MessageCallback = Callable[[AgentMessage, int], Awaitable[None]]
EventCallback = Callable[[Dict[str, Any]], Awaitable[None]]


@dataclass
class RoundResult:
    round_number: int
    topic: str
    messages: List[AgentMessage] = field(default_factory=list)
    votes: Dict[str, int] = field(default_factory=dict)
    consensus_reached: bool = False
    agreement_level: float = 0.0
    rebuttal_messages: List[AgentMessage] = field(default_factory=list)


@dataclass
class HandRaised:
    agent_id: str
    agent_name: str
    timestamp: float
    reason: str
    topic_focus: str


@dataclass
class DebateSession:
    paper_summary: str
    sections: Dict[str, str]
    agents: List[BaseAgent]
    rounds: List[RoundResult] = field(default_factory=list)
    current_round: int = 0
    final_report: str = ""
    task_assignments: List[TaskAssignment] = field(default_factory=list)
    verdict: Dict[str, Any] = field(default_factory=dict)
    dissent_ledger: List[Dict[str, Any]] = field(default_factory=list)
    agreement_history: List[float] = field(default_factory=list)


class DebateManager:
    def __init__(
        self,
        moderator: ExecutiveModerator,
        agents: List[BaseAgent],
        max_rounds: int = 5,
        min_rounds: int = 3,
        crossfire_passes: int = 2,
        consensus_threshold: float = 0.8,
        on_message: Optional[MessageCallback] = None,
        on_event: Optional[EventCallback] = None,
    ):
        self.moderator = moderator
        self.agents = agents
        self.max_rounds = max_rounds
        self.min_rounds = min_rounds
        self.crossfire_passes = crossfire_passes
        self.consensus_threshold = consensus_threshold
        self.on_message = on_message
        self.on_event = on_event
        self.consensus_detector = ConsensusDetector(threshold=consensus_threshold)

        self.context = AgentContext()
        self.moderator.set_context(self.context)
        for agent in self.agents:
            agent.set_context(self.context)

        self.hand_raised: Dict[str, HandRaised] = {}

    async def initialize_session(
        self,
        paper_summary: str,
        sections: Dict[str, str],
    ) -> DebateSession:
        self.context.update_paper_context(paper_summary, sections)
        self.context.round_number = 0

        return DebateSession(
            paper_summary=paper_summary,
            sections=sections,
            agents=[self.moderator] + self.agents,
        )

    async def _emit_event(self, event: Dict[str, Any]) -> None:
        if self.on_event:
            await self.on_event(event)

    async def _emit_message(self, msg: AgentMessage, round_num: int) -> None:
        if self.on_message:
            await self.on_message(msg, round_num)

    async def run_planning_phase(self, session: DebateSession) -> List[TaskAssignment]:
        """Task decomposition: moderator assigns subtasks to specialists."""
        assignments = await self.moderator.decompose_tasks(
            session.paper_summary,
            session.sections,
            self.agents,
        )
        session.task_assignments = assignments

        planning_msg = await self.moderator.speak(
            "Task assignments for this review:\n"
            + "\n".join(
                f"• {a.owner_name}: {a.task} (sections: {', '.join(a.sections)})"
                for a in assignments
            ),
            turn=len(self.context.debate_history) + 1,
            message_type="planning",
        )
        await self._emit_message(planning_msg, 0)
        await self._emit_event({
            "type": "planning_complete",
            "assignments": [a.to_dict() for a in assignments],
        })

        for a in assignments:
            a.status = "in_progress"
        return assignments

    async def raise_hand(self, agent: BaseAgent, reason: str = "", topic_focus: str = "") -> bool:
        self.hand_raised[agent.id] = HandRaised(
            agent_id=agent.id,
            agent_name=agent.name,
            timestamp=datetime.now().timestamp(),
            reason=reason or "Wants to contribute",
            topic_focus=topic_focus or "General comment",
        )
        return True

    async def lower_hand(self, agent: BaseAgent) -> bool:
        if agent.id in self.hand_raised:
            del self.hand_raised[agent.id]
            return True
        return False

    async def get_waiting_speakers(self) -> List[HandRaised]:
        return sorted(self.hand_raised.values(), key=lambda h: h.timestamp)

    async def select_next_speaker(
        self,
        current_topic: str,
        previous_speakers: List[str],
    ) -> Optional[BaseAgent]:
        waiting = await self.get_waiting_speakers()
        if not waiting:
            return None

        def speaker_priority(hand_raise: HandRaised) -> Tuple[int, float]:
            priority = 1 if hand_raise.agent_name in previous_speakers else 0
            return (priority, hand_raise.timestamp)

        sorted_hand_raises = sorted(waiting, key=speaker_priority)

        for hand_raise in sorted_hand_raises:
            if hand_raise.agent_name not in previous_speakers:
                return next((a for a in self.agents if a.id == hand_raise.agent_id), None)

        first_in_line = sorted_hand_raises[0]
        return next((a for a in self.agents if a.id == first_in_line.agent_id), None)

    async def _invite_agents_to_speak(self, current_topic: str, previous_speakers: List[str]) -> int:
        invited = 0
        for agent in self.agents:
            if agent.name in previous_speakers or agent.id in self.hand_raised:
                continue
            await self.raise_hand(
                agent,
                reason="Contributing to discussion",
                topic_focus=f"Analysis of {current_topic.lower()}",
            )
            invited += 1
        return invited

    async def _agent_speak_structured(
        self,
        speaker: BaseAgent,
        structured: Any,
        message_type: str = "speech",
    ) -> AgentMessage:
        turn = len(self.context.debate_history) + 1
        msg = await speaker.speak(
            structured.to_display(),
            turn,
            message_type=message_type,
            stance=structured.stance,
            confidence=structured.confidence,
            evidence=structured.evidence,
        )
        return msg

    def _debate_messages(self, messages: List[AgentMessage]) -> List[AgentMessage]:
        return [
            m for m in messages
            if m.message_type in ("opening", "debate", "speech", "rebuttal")
        ]

    def _latest_stance_per_agent(self, messages: List[AgentMessage]) -> List[AgentMessage]:
        """One vote per agent — use their latest debate stance in the round."""
        latest: Dict[str, AgentMessage] = {}
        for msg in self._debate_messages(messages):
            latest[msg.agent_name] = msg
        return list(latest.values())

    def _select_debate_target(
        self,
        responder: BaseAgent,
        messages: List[AgentMessage],
        pass_num: int,
    ) -> Optional[AgentMessage]:
        """Pick who this agent should respond to — prefer opposing views."""
        others = [m for m in messages if m.agent_name != responder.name]
        if not others:
            return None

        if pass_num == 0:
            return others[-1]

        # Second pass: respond to someone who disagreed or was disagreed with
        for msg in reversed(others):
            if msg.stance == "disagree":
                return msg

        # Avoid re-targeting the same person if possible
        responded_to = {
            m.content.split("→ Responding to ")[1].split(":")[0]
            for m in messages
            if m.agent_name == responder.name and "→ Responding to " in m.content
        }
        for msg in reversed(others):
            if msg.agent_name not in responded_to:
                return msg
        return others[-1]

    async def _run_opening_statements(
        self,
        topic: str,
        round_num: int,
    ) -> List[AgentMessage]:
        """Each agent states an opening position to be debated."""
        messages: List[AgentMessage] = []
        for agent in self.agents:
            structured = await agent.think_opening(topic, round_num)
            msg = await self._agent_speak_structured(agent, structured, message_type="opening")
            messages.append(msg)
            await self._emit_message(msg, round_num)
            await asyncio.sleep(0.1)
        return messages

    async def _run_crossfire(
        self,
        topic: str,
        round_num: int,
        messages: List[AgentMessage],
    ) -> List[AgentMessage]:
        """Agents respond directly to each other's claims."""
        crossfire: List[AgentMessage] = []
        pool = list(messages)

        for pass_num in range(self.crossfire_passes):
            for agent in self.agents:
                target = self._select_debate_target(agent, pool + crossfire, pass_num)
                if not target:
                    continue

                structured = await agent.think_debate_response(
                    topic, round_num, target, pool + crossfire
                )
                msg = await self._agent_speak_structured(agent, structured, message_type="debate")
                crossfire.append(msg)
                await self._emit_message(msg, round_num)
                await asyncio.sleep(0.1)

        return crossfire

    async def _run_rebuttal(
        self,
        topic: str,
        round_num: int,
        round_messages: List[AgentMessage],
    ) -> List[AgentMessage]:
        """Rebuttal round for agents who disagreed."""
        dissenters = [m for m in round_messages if m.stance == "disagree"]
        if not dissenters:
            return []

        dispute = dissenters[0].content[:300]
        rebuttals: List[AgentMessage] = []

        await self._emit_event({
            "type": "rebuttal_started",
            "topic": topic,
            "dispute": dispute[:200],
        })

        for dissenter_msg in dissenters[:2]:
            # An opposing reviewer challenges the dissenter's claim
            agreed_names = {
                m.agent_name for m in round_messages
                if m.stance == "agree" and m.agent_name != dissenter_msg.agent_name
            }
            rebutter = next(
                (a for a in self.agents if a.name in agreed_names),
                None,
            )
            if not rebutter:
                rebutter = next(
                    (a for a in self.agents if a.name != dissenter_msg.agent_name),
                    None,
                )
            if not rebutter:
                continue

            structured = await rebutter.think_rebuttal(
                topic,
                dissenter_msg.content[:400],
                opponent=dissenter_msg.agent_name,
            )
            turn = len(self.context.debate_history) + 1
            msg = await rebutter.speak(
                f"[Rebuttal] {structured.to_display()}",
                turn,
                message_type="rebuttal",
                stance=structured.stance,
                confidence=structured.confidence,
                evidence=structured.evidence,
            )
            rebuttals.append(msg)
            await self._emit_message(msg, round_num)
            await asyncio.sleep(0.1)

            # Dissenter gets a final word defending their position
            dissenter = next(
                (a for a in self.agents if a.name == dissenter_msg.agent_name),
                None,
            )
            if dissenter:
                defense = await dissenter.think_rebuttal(
                    topic,
                    structured.summary[:300],
                    opponent=rebutter.name,
                )
                turn = len(self.context.debate_history) + 1
                defense_msg = await dissenter.speak(
                    f"[Defense] {defense.to_display()}",
                    turn,
                    message_type="rebuttal",
                    stance=defense.stance,
                    confidence=defense.confidence,
                    evidence=defense.evidence,
                )
                rebuttals.append(defense_msg)
                await self._emit_message(defense_msg, round_num)
                await asyncio.sleep(0.1)

        await self._emit_event({"type": "rebuttal_complete", "count": len(rebuttals)})
        return rebuttals

    def _record_dissent(
        self,
        round_messages: List[AgentMessage],
        topic: str,
        round_num: Optional[int] = None,
    ) -> None:
        for msg in round_messages:
            if msg.stance == "disagree":
                entry = {
                    "agent_name": msg.agent_name,
                    "topic": topic,
                    "position": msg.content[:400],
                    "confidence": msg.confidence,
                    "round": round_num if round_num is not None else self.context.round_number,
                    "evidence": (msg.evidence or [])[:2],
                }
                self.context.dissent_ledger.append(entry)

    async def run_round(
        self,
        session: DebateSession,
        round_num: int,
        topics: Optional[List[str]] = None,
    ) -> RoundResult:
        self.context.round_number = round_num

        if not topics:
            topics = await self.moderator.set_agenda(
                session.paper_summary,
                session.sections,
                round_num,
            )

        current_topic = topics[0] if topics else "General discussion"
        print(f"\n--- Round {round_num}: {current_topic} ---\n")

        await self._emit_event({
            "type": "round_started",
            "round": round_num,
            "topic": current_topic,
        })

        # Phase 1: opening positions
        messages = await self._run_opening_statements(current_topic, round_num)

        # Phase 2: crossfire — agents debate each other directly
        crossfire = await self._run_crossfire(current_topic, round_num, messages)
        messages.extend(crossfire)

        for assignment in session.task_assignments:
            if assignment.owner_name in {m.agent_name for m in messages}:
                assignment.status = "complete"

        synthesis, votes = await self.moderator.synthesize_round(
            round_num, current_topic, messages
        )

        mod_turn = len(self.context.debate_history) + 1
        synth_msg = await self.moderator.speak(
            f"[Round {round_num} Summary] {synthesis}",
            mod_turn,
            message_type="synthesis",
        )
        await self._emit_message(synth_msg, round_num)

        vote_objects = [
            Vote(
                agent_id=m.agent_id,
                agent_name=m.agent_name,
                stance=stance_to_vote(m.stance or "neutral"),
                justification=m.content[:100],
            )
            for m in self._latest_stance_per_agent(messages)
        ]
        consensus_result = self.consensus_detector.detect_consensus(
            vote_objects, current_topic, synthesis[:200]
        )
        agreement_level = consensus_result.agreement_level
        session.agreement_history.append(agreement_level)
        self.context.agreement_history.append(agreement_level)

        consensus_reached = consensus_result.consensus_reached
        explanation = (
            f"Agreement: {agreement_level:.0%} "
            f"({votes.get('agree', 0)} agree, {votes.get('disagree', 0)} disagree)"
        )

        rebuttal_messages: List[AgentMessage] = []
        has_disagreement = (
            votes.get("disagree", 0) > 0
            or any(m.stance == "disagree" for m in self._debate_messages(messages))
        )
        if has_disagreement:
            rebuttals = await self._run_rebuttal(current_topic, round_num, messages)
            rebuttal_messages.extend(rebuttals)
            messages.extend(rebuttals)

            _, votes = await self.moderator.synthesize_round(
                round_num, current_topic, messages
            )
            vote_objects = [
                Vote(
                    agent_id=m.agent_id,
                    agent_name=m.agent_name,
                    stance=stance_to_vote(m.stance or "neutral"),
                )
                for m in self._latest_stance_per_agent(messages)
            ]
            consensus_result = self.consensus_detector.detect_consensus(
                vote_objects, current_topic
            )
            agreement_level = consensus_result.agreement_level
            consensus_reached = consensus_result.consensus_reached
            session.agreement_history.append(agreement_level)

        if not consensus_reached:
            self._record_dissent(messages, current_topic, round_num=round_num)

        await self._emit_event({
            "type": "consensus_update",
            "round": round_num,
            "agreement_level": agreement_level,
            "consensus_reached": consensus_reached,
            "explanation": explanation,
        })

        round_result = RoundResult(
            round_number=round_num,
            topic=current_topic,
            messages=messages,
            votes=votes,
            consensus_reached=consensus_reached,
            agreement_level=agreement_level,
            rebuttal_messages=rebuttal_messages,
        )
        session.rounds.append(round_result)
        return round_result

    async def run_debate(self, session: DebateSession) -> DebateSession:
        print(f"Starting debate on: {session.paper_summary[:100]}...")
        print(f"Participants: {[a.name for a in [self.moderator] + self.agents]}\n")

        await self.run_planning_phase(session)

        for round_num in range(1, self.max_rounds + 1):
            result = await self.run_round(session, round_num)
            if result.consensus_reached and round_num >= self.min_rounds:
                print(f"\nConsensus reached on '{result.topic}' after {round_num} rounds!")
                break
            if result.consensus_reached:
                print(f"\nRound {round_num}: early agreement ({result.agreement_level:.0%}) — continuing debate...")

        session.final_report = await self.moderator.close_debate()
        session.verdict = await self.moderator.generate_verdict()
        session.dissent_ledger = list(self.context.dissent_ledger)

        await self._emit_event({
            "type": "verdict_ready",
            "verdict": session.verdict,
            "dissent_ledger": session.dissent_ledger,
        })

        return session


async def create_and_run_debate(
    paper_summary: str,
    sections: Dict[str, str],
    moderator: Optional[ExecutiveModerator] = None,
    agents: Optional[List[BaseAgent]] = None,
    max_rounds: int = 5,
) -> DebateSession:
    from agents.base import AgentFactory

    if moderator is None:
        moderator = ExecutiveModerator()
    if agents is None:
        agents = [
            AgentFactory.create_agent("structure_analyst"),
            AgentFactory.create_agent("contribution_scout"),
            AgentFactory.create_agent("methodology_critic"),
            AgentFactory.create_agent("literature_reviewer"),
        ]

    manager = DebateManager(moderator=moderator, agents=agents, max_rounds=max_rounds)
    session = await manager.initialize_session(paper_summary, sections)
    return await manager.run_debate(session)
