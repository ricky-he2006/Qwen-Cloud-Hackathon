"""
Paper ingestion package.
"""

from .parser import parse_pdf, PaperParser, ScientificPaper
from .fetcher import identify_paper, PaperFetcher

__all__ = [
    'parse_pdf',
    'PaperParser',
    'ScientificPaper',
    'identify_paper',
    'PaperFetcher'
]
