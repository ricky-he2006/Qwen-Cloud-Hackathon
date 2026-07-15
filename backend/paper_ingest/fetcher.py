"""
Fetcher module for retrieving scientific papers.
Supports:
- arXiv API
- DOI lookups
- Local file loading
"""

import os
import re
import tempfile
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import arxiv


@dataclass
class PaperMetadata:
    """Metadata for a scientific paper."""
    title: str
    authors: List[str]
    abstract: str
    published_date: str
    paper_id: str  # arXiv ID or DOI
    url: str
    categories: List[str] = None

    def __post_init__(self):
        if self.categories is None:
            self.categories = []


class PaperFetcher:
    """Fetcher for scientific papers from various sources."""

    ARXIV_API_URL = "http://export.arxiv.org/api/query"

    def __init__(self):
        self._arxiv_client = arxiv.Client()

    def _iter_arxiv_results(self, search: arxiv.Search):
        return self._arxiv_client.results(search)

    def fetch_by_arxiv_id(self, arxiv_id: str) -> Optional[PaperMetadata]:
        """
        Fetch paper metadata by arXiv ID.

        Args:
            arxiv_id: The arXiv identifier (e.g., '2301.12345')

        Returns:
            PaperMetadata object or None if not found
        """
        try:
            # Use the arxiv Python library
            search = arxiv.Search(id_list=[arxiv_id])
            result = next(self._iter_arxiv_results(search), None)

            if result is None:
                return None

            return PaperMetadata(
                title=result.title,
                authors=[a.name for a in result.authors],
                abstract=result.summary,
                published_date=result.published.strftime('%Y-%m-%d'),
                paper_id=arxiv_id,
                url=result.entry_id,
                categories=[
                    c.term if hasattr(c, "term") else str(c)
                    for c in result.categories
                ],
            )
        except Exception as e:
            print(f"Error fetching from arXiv: {e}")
            return None

    def search_arxiv(self, query: str, max_results: int = 5) -> List[PaperMetadata]:
        """
        Search arXiv for papers matching a query.

        Args:
            query: Search terms
            max_results: Maximum number of results to return

        Returns:
            List of matching PaperMetadata objects
        """
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )

            papers = []
            for result in self._iter_arxiv_results(search):
                papers.append(PaperMetadata(
                    title=result.title,
                    authors=[a.name for a in result.authors],
                    abstract=result.summary,
                    published_date=result.published.strftime('%Y-%m-%d'),
                    paper_id=result.get_short_id(),
                    url=result.entry_id,
                    categories=[
                        c.term if hasattr(c, "term") else str(c)
                        for c in result.categories
                    ],
                ))

            return papers
        except Exception as e:
            print(f"Error searching arXiv: {e}")
            return []

    def fetch_by_doi(self, doi: str) -> Optional[PaperMetadata]:
        """
        Fetch paper metadata by DOI.

        Args:
            doi: Digital Object Identifier

        Returns:
            PaperMetadata object or None if not found
        """
        headers = {
            'Accept': 'application/citeproc+json'
        }

        try:
            response = requests.get(
                f'https://dx.doi.org/{doi}',
                headers=headers,
                timeout=10
            )

            if response.status_code != 200:
                return None

            data = response.json()
            return PaperMetadata(
                title=data.get('title', ''),
                authors=[f"{a.get('given', '')} {a.get('family', '')}".strip()
                        for a in data.get('author', [])],
                abstract=data.get('abstract', ''),
                published_date=data.get('issued', {}).get('date-parts', [['']])[0][0],
                paper_id=doi,
                url=f'https://doi.org/{doi}',
                categories=[]
            )
        except Exception as e:
            print(f"Error fetching by DOI: {e}")
            return None

    def fetch_from_url(self, url: str) -> Optional[PaperMetadata]:
        """
        Attempt to extract paper metadata from a URL.
        Supports arXiv and DOI URLs.

        Args:
            url: The paper's URL

        Returns:
            PaperMetadata object or None if extraction fails
        """
        # Check for arXiv ID in URL
        arxiv_match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', url)
        if arxiv_match:
            return self.fetch_by_arxiv_id(arxiv_match.group(1))

        # Check for DOI in URL
        doi_match = re.search(r'doi\.org/(.+)$', url)
        if doi_match:
            return self.fetch_by_doi(doi_match.group(1))

        # Try direct arXiv ID
        simple_arxiv = re.search(r'(\d+\.\d+)', url)
        if simple_arxiv:
            return self.fetch_by_arxiv_id(simple_arxiv.group(1))

        return None

    def identify_paper(self, identifier: str) -> Tuple[str, Optional[PaperMetadata]]:
        """Identify paper from any supported identifier (delegates to universal resolver)."""
        from paper_ingest.resolver import resolve_identifier
        return resolve_identifier(identifier)

    def download_arxiv_pdf(self, arxiv_id: str, dest_dir: Optional[str] = None) -> str:
        """Download an arXiv paper PDF and return the local file path."""
        clean_id = re.sub(r'v\d+$', '', arxiv_id.split('/')[-1])
        url = f"https://arxiv.org/pdf/{clean_id}.pdf"
        target_dir = dest_dir or tempfile.gettempdir()
        dest_path = os.path.join(target_dir, f"{clean_id}.pdf")

        response = requests.get(url, timeout=60, headers={"User-Agent": "ResearchSociety/1.0"})
        response.raise_for_status()

        with open(dest_path, "wb") as f:
            f.write(response.content)

        return dest_path

    def extract_sections_from_metadata(
        self,
        metadata: PaperMetadata,
        paper_type: str,
    ) -> Dict[str, str]:
        """Build sections from best available full-text source."""
        from paper_ingest.fulltext import extract_full_sections

        return extract_full_sections(
            metadata,
            paper_type,
            arxiv_downloader=self.download_arxiv_pdf,
        )


def identify_paper(identifier: str) -> Tuple[str, Optional[PaperMetadata]]:
    """Convenience function to identify and fetch a paper."""
    fetcher = PaperFetcher()
    return fetcher.identify_paper(identifier)


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        identifier = sys.argv[1]
        paper_type, metadata = identify_paper(identifier)

        if metadata:
            print(f"Paper Type: {paper_type}")
            print(f"Title: {metadata.title}")
            print(f"Authors: {', '.join(metadata.authors)}")
            print(f"Abstract: {metadata.abstract[:200]}...")
            print(f"ID: {metadata.paper_id}")
        else:
            print(f"No paper found for identifier: {identifier}")
    else:
        print("Usage: python fetcher.py <arxiv_id|doi|url|search_term>")
