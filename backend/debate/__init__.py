"""
Debate package for orchestrating multi-agent discussions.
"""

from .manager import DebateManager, DebateSession, RoundResult
from .consensus import ConsensusDetector, ConsensusResult, ConsensusHistory
from .reporter import ReportGenerator, ConsensusItem

__all__ = [
    'DebateManager',
    'DebateSession',
    'RoundResult',
    'ConsensusDetector',
    'ConsensusResult',
    'ConsensusHistory',
    'ReportGenerator',
    'ConsensusItem'
]
