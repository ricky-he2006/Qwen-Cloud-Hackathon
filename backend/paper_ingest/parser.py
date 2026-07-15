"""
Scientific paper PDF parser.
Extracts structured information from academic papers including:
- Title, authors, abstract
- Section headers and content
- References
"""

import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re

import fitz  # PyMuPDF


@dataclass
class PaperSection:
    """Represents a section of a scientific paper."""
    title: str
    content: str
    level: int = 1  # Header level (1 for main sections)
    page_start: int = 0
    page_end: int = 0


@dataclass
class ScientificPaper:
    """Represents a parsed scientific paper."""
    filepath: str
    title: str = ""
    authors: List[str] = None
    abstract: str = ""
    keywords: List[str] = None
    introduction: str = ""
    methodology: str = ""
    results: str = ""
    discussion: str = ""
    conclusion: str = ""
    references: List[str] = None
    sections: List[PaperSection] = None

    def __post_init__(self):
        if self.authors is None:
            self.authors = []
        if self.keywords is None:
            self.keywords = []
        if self.references is None:
            self.references = []
        if self.sections is None:
            self.sections = []


class PaperParser:
    """Parser for scientific PDF papers with section extraction."""

    # Common section headers in academic papers
    SECTION_PATTERNS = {
        'abstract': [r'^(?:A|a)bstract\b'],
        'introduction': [r'^(?:I|i)ntroduction\b', r'^(?:B|b)ackground\b'],
        'methodology': [
            r'^(?:M|m)ethods?\.?$',
            r'^(?:E|e)xperimental\s+(?:S|s)etup$',
            r'^(?:P|p)rocedures?',
            r'^(?:C|c)omputational\s+(?:M|m)ethods?'
        ],
        'results': [
            r'^(?:R|r)esults?\.?$',
            r'^(?:E|e)xperimental\s+(?:R|r)esults$',
            r'^(?:D|d)ata\s+(?:A|a)nalysis'
        ],
        'discussion': [
            r'^(?:D|d)iscussion\b',
            r'^(?:I|i)nterpretation',
            r'^(?:A|a)nalysis'
        ],
        'conclusion': [r'^(?:C|c)onclusion', r'^(?:S|s)ummary'],
        'references': [
            r'^(?:R|r)eferences\b',
            r'^(?:R|r)eference\s+Literals?$',
            r'^(?:B|b)ibliography'
        ]
    }

    def __init__(self):
        self.pdf = None

    def load_pdf(self, filepath: str) -> bool:
        """Load a PDF file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"PDF not found: {filepath}")

        try:
            self.pdf = fitz.open(filepath)
            return True
        except Exception as e:
            raise ValueError(f"Failed to load PDF: {e}")

    def close(self):
        """Close the PDF file."""
        if self.pdf:
            self.pdf.close()
            self.pdf = None

    def extract_text(self, page_num: Optional[int] = None) -> str:
        """Extract text from PDF."""
        if not self.pdf:
            raise ValueError("PDF not loaded. Call load_pdf first.")

        if page_num is not None:
            return self.pdf[page_num].get_text()

        return "\n".join(page.get_text() for page in self.pdf)

    def extract_sections(self) -> List[PaperSection]:
        """Extract paper sections based on headers."""
        if not self.pdf:
            raise ValueError("PDF not loaded. Call load_pdf first.")

        sections = []
        current_section = None

        for page_num, page in enumerate(self.pdf):
            text = page.get_text()
            lines = text.split('\n')

            for line in lines:
                line = line.strip()

                # Check if this is a section header
                matched_section = self._match_header(line)

                if matched_section:
                    # Save previous section if exists
                    if current_section and current_section.content.strip():
                        sections.append(current_section)

                    current_section = PaperSection(
                        title=matched_section,
                        content="",
                        level=self._get_header_level(line),
                        page_start=page_num
                    )
                elif current_section:
                    # Add content to current section
                    if line and not self._is_inline_reference(line):
                        current_section.content += f"{line}\n"
                        current_section.page_end = page_num

        # Don't forget the last section
        if current_section and current_section.content.strip():
            sections.append(current_section)

        return sections

    def _match_header(self, line: str) -> Optional[str]:
        """Check if a line matches a known section header pattern."""
        for section_name, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    return section_name
        return None

    def _get_header_level(self, line: str) -> int:
        """Determine the header level based on formatting."""
        # Heuristic: count leading spaces or check punctuation
        stripped = line.lstrip()
        if len(line) - len(stripped) > 40:
            return 2  # Subsection
        elif '.' in line[:5] and line[1] == '.':  # "1.1 Section"
            return 2  # Subsection
        return 1  # Main section

    def _is_inline_reference(self, line: str) -> bool:
        """Check if a line is an inline citation reference."""
        return re.match(r'^\[\d+\]', line) or re.match(r'\(\w+.*\d{4}', line)

    def extract_metadata(self) -> Dict[str, any]:
        """Extract paper metadata (title, authors, etc.)."""
        if not self.pdf:
            raise ValueError("PDF not loaded. Call load_pdf first.")

        metadata = {
            'title': '',
            'authors': [],
            'abstract': ''
        }

        # Try to get title from first page
        first_page_text = self.pdf[0].get_text()
        lines = [l.strip() for l in first_page_text.split('\n') if l.strip()]

        # Title is often the first or second non-empty line
        if lines:
            metadata['title'] = lines[0]
            # If second line looks like an author name (no punctuation, short)
            if len(lines) > 1 and self._looks_like_author(lines[1]):
                metadata['authors'].append(lines[1])

        # Try to extract abstract
        for i, line in enumerate(lines):
            if re.match(r'^(?:A|a)bstract\b', line):
                # Get content after "Abstract"
                abs_start = re.sub(r'^(?:A|a)bstract[:\s]*', '', line, flags=re.IGNORECASE)
                metadata['abstract'] = abs_start
                break

        return metadata

    def _looks_like_author(self, line: str) -> bool:
        """Heuristic to check if a line looks like an author name."""
        # Author lines typically:
        # - Don't contain punctuation like periods (except in initials)
        # - Are relatively short (under 100 chars)
        # - May contain commas for multiple authors
        if len(line) > 100:
            return False

        # Check for common author name patterns
        # "John Doe" or "J. Doe"
        name_pattern = r'^[A-Z][a-z]+(?:\s+[A-Z]\.?\.?\s+)?[A-Z][a-z]+$'
        return bool(re.match(name_pattern, line)) or ',' in line

    def parse_file(self, filepath: str) -> ScientificPaper:
        """Parse a PDF file and extract all information."""
        self.load_pdf(filepath)

        paper = ScientificPaper(filepath=filepath)

        # Extract sections
        paper.sections = self.extract_sections()

        # Map sections to paper attributes
        section_map = {
            'abstract': 'abstract',
            'introduction': 'introduction',
            'methodology': 'methodology',
            'results': 'results',
            'discussion': 'discussion',
            'conclusion': 'conclusion'
        }

        for section in paper.sections:
            if section.title in section_map:
                setattr(paper, section_map[section.title], section.content)
            elif section.title == 'references':
                # Parse references
                ref_lines = [l.strip() for l in section.content.split('\n') if l.strip()]
                paper.references = ref_lines

        self.close()
        return paper


def parse_pdf(filepath: str) -> ScientificPaper:
    """Convenience function to parse a PDF file."""
    parser = PaperParser()
    return parser.parse_file(filepath)


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) > 1:
        paper_path = sys.argv[1]
        try:
            paper = parse_pdf(paper_path)
            print(f"Title: {paper.title}")
            print(f"Authors: {', '.join(paper.authors)}")
            print(f"\nAbstract:\n{paper.abstract[:200]}...")
            print(f"\nSections found: {[s.title for s in paper.sections]}")
        except Exception as e:
            print(f"Error parsing PDF: {e}")
    else:
        print("Usage: python parser.py <path_to_pdf>")
