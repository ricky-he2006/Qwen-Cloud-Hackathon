#!/usr/bin/env python3
"""Quick smoke test for debate loop (no LLM required)."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def test_hand_raising():
    from agents.base import AgentFactory, AgentMessage, TaskAssignment
    from agents.executive_moderator import ExecutiveModerator
    from debate.manager import DebateManager
    from debate.structured import StructuredResponse

    moderator = ExecutiveModerator()
    agents = [
        AgentFactory.create_agent("structure_analyst"),
        AgentFactory.create_agent("contribution_scout"),
    ]

    messages_received = []

    async def on_message(msg, round_num):
        messages_received.append((msg.agent_name, round_num))

    manager = DebateManager(
        moderator=moderator,
        agents=agents,
        max_rounds=1,
        min_rounds=1,
        crossfire_passes=1,
        on_message=on_message,
    )

    for agent in agents:
        async def mock_opening(topic, round_num, _agent=agent):
            return StructuredResponse(
                summary=f"Opening from {_agent.name} on {topic}",
                stance="agree",
                confidence=0.8,
                evidence=[{"section": "abstract", "quote": "test"}],
            )

        async def mock_debate(topic, round_num, target, prior, _agent=agent):
            return StructuredResponse(
                summary=f"Rebuttal from {_agent.name} to {target.agent_name}",
                stance="agree",
                confidence=0.7,
                responds_to=target.agent_name,
                evidence=[{"section": "methods", "quote": "test"}],
            )

        async def mock_structured(topic, round_num, _agent=agent):
            return StructuredResponse(
                summary=f"Analysis from {_agent.name} on {topic}",
                stance="agree",
                confidence=0.8,
                evidence=[{"section": "abstract", "quote": "test"}],
            )

        agent.think_opening = mock_opening
        agent.think_debate_response = mock_debate
        agent.think_structured = mock_structured

    async def mock_decompose(summary, sections, agents_list):
        return [
            TaskAssignment(
                "Review structure", "paper_structure_analyst", "Dr. Structure", ["abstract"]
            ),
            TaskAssignment(
                "Review methods", "methodology_expert", "Dr. Methods", ["methodology"]
            ),
        ]

    async def mock_set_agenda(summary, sections, round_num):
        return ["Test topic"]

    async def mock_synthesize(round_num, topic, round_messages=None):
        return "Round summary", {"agree": 2, "disagree": 0, "neutral": 0}

    async def mock_close():
        return "Final report"

    async def mock_verdict():
        return {"verdict": "REVISE", "scores": {"novelty": 7}, "dissent_ledger": []}

    moderator.decompose_tasks = mock_decompose
    moderator.set_agenda = mock_set_agenda
    moderator.synthesize_round = mock_synthesize
    moderator.close_debate = mock_close
    moderator.generate_verdict = mock_verdict

    session = await manager.initialize_session(
        paper_summary="Paper: Test",
        sections={"abstract": "Test abstract content"},
    )
    result = await manager.run_debate(session)

    assert len(result.task_assignments) >= 1, "Expected task assignments"
    assert len(result.rounds) >= 1, "Expected at least one round"
    assert len(result.rounds[0].messages) >= 2, "Expected agent messages"
    assert len(messages_received) >= 2, "Expected streamed messages"
    print("PASS: planning + hand-raising debate loop")


if __name__ == "__main__":
    asyncio.run(test_hand_raising())
