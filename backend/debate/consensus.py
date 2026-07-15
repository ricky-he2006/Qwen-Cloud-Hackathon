"""
Consensus Detection Module.
Implements voting and convergence logic for the agent society.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import json


@dataclass
class Vote:
    """Represents a single vote."""
    agent_id: str
    agent_name: str
    stance: int  # 1 = agree, 0 = neutral/abstain, -1 = disagree
    justification: str = ""


@dataclass
class ConsensusResult:
    """Result of consensus detection."""
    topic: str
    agreement_level: float  # fraction of agents agreeing
    vote_count: Dict[str, int]  # {agree: n, disagree: m, neutral: k}
    consensus_reached: bool
    dissenting_agents: List[str]
    evidence_for_consensus: str = ""


class ConsensusDetector:
    """
    Detects consensus among agents using voting and convergence analysis.
    """

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold

    def count_votes(self, votes: List[Vote]) -> Dict[str, int]:
        """Count votes into a dictionary."""
        counts = {'agree': 0, 'disagree': 0, 'neutral': 0}

        for vote in votes:
            if vote.stance == 1:
                counts['agree'] += 1
            elif vote.stance == -1:
                counts['disagree'] += 1
            else:
                counts['neutral'] += 1

        return counts

    def calculate_agreement(self, counts: Dict[str, int]) -> float:
        """Calculate agreement fraction."""
        total = sum(counts.values())
        if total == 0:
            return 0.0
        return counts.get('agree', 0) / total

    def detect_consensus(
        self,
        votes: List[Vote],
        topic: str,
        evidence: str = ""
    ) -> ConsensusResult:
        """
        Detect consensus from a set of votes.

        Args:
            votes: List of Vote objects
            topic: Topic being voted on
            evidence: Supporting evidence for the result

        Returns:
            ConsensusResult with all relevant data
        """
        counts = self.count_votes(votes)
        agreement = self.calculate_agreement(counts)

        # Get dissenting agents
        dissenting = [v.agent_name for v in votes if v.stance == -1]

        # Determine if consensus reached (majority after 5 rounds or threshold)
        consensus_reached = agreement >= self.threshold

        return ConsensusResult(
            topic=topic,
            agreement_level=agreement,
            vote_count=counts,
            consensus_reached=consensus_reached,
            dissenting_agents=dissenting,
            evidence_for_consensus=evidence
        )

    def analyze_convergence(
        self,
        agent_opinions: Dict[str, List[str]],
        round_num: int,
        max_rounds: int = 5
    ) -> Tuple[bool, float]:
        """
        Analyze whether agents' opinions have converged.

        Args:
            agent_opinions: Map of agent_name -> list of opinions across rounds
            round_num: Current round number
            max_rounds: Maximum rounds allowed

        Returns:
            Tuple of (converged, confidence_score)
        """
        if len(agent_opinions) == 0:
            return False, 0.0

        # Get last opinion from each agent
        current_opinions = {agent: opinions[-1] for agent, opinions in agent_opinions.items()}

        # Simple convergence detection based on keyword overlap
        agree_keywords = ['agree', 'support', 'valid', 'strong evidence']
        disagree_keywords = ['disagree', 'counter', 'flaw', 'weakness']

        converged_count = 0
        total_pairs = 0

        agents = list(current_opinions.keys())
        for i, a1 in enumerate(agents):
            for j, a2 in enumerate(agents):
                if i >= j:
                    continue

                total_pairs += 1
                op1 = current_opinions[a1].lower()
                op2 = current_opinions[a2].lower()

                # Check if both express similar stance
                has_agree = any(kw in op1 for kw in agree_keywords)
                has_disagree = any(kw in op1 for kw in disagree_keywords)
                other_has_agree = any(kw in op2 for kw in agree_keywords)
                other_has_disagree = any(kw in op2 for kw in disagree_keywords)

                if (has_agree and other_has_agree) or (has_disagree and other_has_disagree):
                    converged_count += 1

        if total_pairs == 0:
            return False, 0.0

        convergence_score = converged_count / total_pairs

        # Converged if > threshold of agent pairs agree on stance
        # AND we're at max rounds or have high confidence
        is_converged = convergence_score >= self.threshold or round_num == max_rounds

        return is_converged, convergence_score

    def parse_opinion_from_text(self, text: str) -> int:
        """
        Parse a numerical opinion from agent's text response.

        Returns:
            1 for agree, -1 for disagree, 0 for neutral/unknown
        """
        text_lower = text.lower()

        # Strong agreement indicators
        if any(kw in text_lower for kw in ['strongly agree', 'completely agree', 'fully support']):
            return 1

        # Strong disagreement indicators
        if any(kw in text_lower for kw in ['strongly disagree', 'do not agree', 'contrary to']):
            return -1

        # Basic agreement indicators
        if any(kw in text_lower for kw in ['agree', 'valid point', 'supports']):
            return 1

        # Disagreement indicators
        if any(kw in text_lower for kw in ['disagree', 'counter', 'flaw', 'issue']):
            return -1

        return 0


class ConsensusHistory:
    """Tracks consensus across multiple rounds."""

    def __init__(self):
        self.results: List[ConsensusResult] = []
        self.agent_votes: Dict[str, List[Vote]] = {}

    def add_result(self, result: ConsensusResult):
        """Add a consensus result to history."""
        self.results.append(result)

        # Track individual agent votes
        for vote in self._votes_from_result(result):
            if vote.agent_id not in self.agent_votes:
                self.agent_votes[vote.agent_id] = []
            self.agent_votes[vote.agent_id].append(vote)

    def _votes_from_result(self, result: ConsensusResult) -> List[Vote]:
        """Convert a ConsensusResult back to votes."""
        # This would be reconstructed from the actual debate history
        return []

    def get_consensus_trend(self) -> Dict[str, float]:
        """
        Get trend of agreement levels across rounds.

        Returns:
            Dict mapping topic to {start_level, end_level, change}
        """
        if not self.results:
            return {}

        trends = {}
        topics = set(r.topic for r in self.results)

        for topic in topics:
            topic_results = [r for r in self.results if r.topic == topic]

            if len(topic_results) >= 2:
                start = topic_results[0].agreement_level
                end = topic_results[-1].agreement_level

                trends[topic] = {
                    'start': start,
                    'end': end,
                    'change': end - start
                }

        return trends


def check_majority_consensus(
    agree_count: int,
    total_count: int,
    threshold: float = 0.5
) -> Tuple[bool, str]:
    """
    Check if majority consensus is reached.

    Args:
        agree_count: Number of agents agreeing
        total_count: Total number of agents
        threshold: Minimum fraction for consensus (default 50% + 1)

    Returns:
        Tuple of (reached, message)
    """
    if total_count == 0:
        return False, "No votes counted"

    agreement = agree_count / total_count
    majority_threshold = max(threshold, 0.5)  # At least 50%

    if agreement >= majority_threshold:
        explanation = f"Majority consensus reached: {agree_count}/{total_count} ({agreement:.0%})"
        return True, explanation

    remaining = int(total_count * majority_threshold) - agree_count + 1
    explanation = (
        f"No consensus yet: {agree_count}/{total_count} ({agreement:.0%}). "
        f"Need {remaining} more agreeing agents."
    )
    return False, explanation
