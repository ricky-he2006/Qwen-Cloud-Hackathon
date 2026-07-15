"""
Full-text retrieval for papers from multiple sources (arXiv, Unpaywall, Europe PMC, HTML).
"""

import os
import re
import tempfile
from typing import Dict, Optional

import requests

from paper_ingest.fetcher import PaperMetadata

USER_AGENT = "ResearchSociety/1.0 (research-tool)"
UNPAYWALL_EMAIL = os.getenv("UNPAYWALL_EMAIL", "research@example.com")


def sections_from_plain_text(text: str) -> Dict[str, str]:
    """Split plain text into pseudo-sections using common academic headers."""
    if not text or len(text) < 100:
        return {}

    section_patterns = [
        (r"\n\s*abstract\s*\n", "abstract"),
        (r"\n\s*introduction\s*\n", "introduction"),
        (r"\n\s*(?:methods?|methodology|materials and methods)\s*\n", "methodology"),
        (r"\n\s*results?\s*\n", "results"),
        (r"\n\s*discussion\s*\n", "discussion"),
        (r"\n\s*conclusions?\s*\n", "conclusion"),
    ]

    lower = text.lower()
    boundaries = [(0, "preamble")]
    for pattern, name in section_patterns:
        match = re.search(pattern, lower)
        if match:
            boundaries.append((match.start(), name))
    boundaries.append((len(text), "end"))
    boundaries.sort(key=lambda x: x[0])

    sections: Dict[str, str] = {}
    for i in range(len(boundaries) - 1):
        start, name = boundaries[i]
        end = boundaries[i + 1][0]
        if name in ("preamble", "end"):
            continue
        content = text[start:end].strip()
        if len(content) > 80:
            sections[name] = content[:12000]

    if not sections and len(text) > 200:
        sections["full_text"] = text[:15000]

    return sections


def try_unpaywall_pdf(doi: str) -> Optional[str]:
    """Download open-access PDF via Unpaywall if available."""
    clean = doi.replace("https://doi.org/", "")
    try:
        response = requests.get(
            f"https://api.unpaywall.org/v2/{clean}",
            params={"email": UNPAYWALL_EMAIL},
            timeout=20,
            headers={"User-Agent": USER_AGENT},
        )
        if response.status_code != 200:
            return None

        data = response.json()
        oa = data.get("best_oa_location") or {}
        pdf_url = oa.get("url_for_pdf") or oa.get("url")
        if not pdf_url:
            return None

        pdf_resp = requests.get(pdf_url, timeout=60, headers={"User-Agent": USER_AGENT})
        if pdf_resp.status_code != 200 or "pdf" not in pdf_resp.headers.get("Content-Type", "").lower():
            if not pdf_url.endswith(".pdf"):
                return None

        dest = os.path.join(tempfile.gettempdir(), f"{clean.replace('/', '_')}.pdf")
        with open(dest, "wb") as f:
            f.write(pdf_resp.content)
        return dest
    except Exception as e:
        print(f"Unpaywall failed for {doi}: {e}")
        return None


def try_europepmc_text(doi: str) -> Optional[str]:
    """Fetch full text from Europe PMC when available."""
    clean = doi.replace("https://doi.org/", "")
    try:
        search = requests.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={"query": f"DOI:{clean}", "format": "json", "pageSize": 1},
            timeout=20,
        )
        if search.status_code != 200:
            return None

        results = search.json().get("resultList", {}).get("result", [])
        if not results:
            return None

        pmcid = results[0].get("pmcid")
        if not pmcid:
            return None

        full = requests.get(
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
            timeout=30,
        )
        if full.status_code != 200:
            return None

        import xml.etree.ElementTree as ET
        root = ET.fromstring(full.text)
        paragraphs = []
        for p in root.iter():
            if p.tag.endswith("p") and p.text:
                paragraphs.append(p.text.strip())
            elif p.text and p.tag.endswith("abstract"):
                paragraphs.append(p.text.strip())

        return "\n\n".join(paragraphs) if paragraphs else None
    except Exception as e:
        print(f"Europe PMC failed for {doi}: {e}")
        return None


def extract_full_sections(metadata: PaperMetadata, paper_type: str, arxiv_downloader) -> Dict[str, str]:
    """
    Build sections dict from the best available full-text source.
    arxiv_downloader: callable(arxiv_id) -> pdf_path
    """
    from paper_ingest.parser import parse_pdf

    sections: Dict[str, str] = {}

    if metadata.abstract:
        sections["abstract"] = metadata.abstract

    paper_id = metadata.paper_id

    # arXiv PDF
    if paper_type == "arxiv" or re.match(r"^\d{4}\.\d{5}", paper_id):
        try:
            pdf_path = arxiv_downloader(paper_id)
            paper = parse_pdf(pdf_path)
            for key in ("abstract", "introduction", "methodology", "results", "discussion", "conclusion"):
                content = getattr(paper, key, "") or ""
                if content.strip():
                    sections[key] = content.strip()
            return sections
        except Exception as e:
            print(f"arXiv PDF parse failed: {e}")

    # DOI-based sources
    doi = paper_id if paper_id.startswith("10.") else None
    if not doi and metadata.url and "doi.org" in metadata.url:
        doi_match = re.search(r"(10\.\d{4,9}/\S+)", metadata.url)
        doi = doi_match.group(1) if doi_match else None

    if doi:
        # Unpaywall OA PDF
        pdf_path = try_unpaywall_pdf(doi)
        if pdf_path:
            try:
                paper = parse_pdf(pdf_path)
                for key in ("abstract", "introduction", "methodology", "results", "discussion", "conclusion"):
                    content = getattr(paper, key, "") or ""
                    if content.strip():
                        sections[key] = content.strip()
                if len(sections) > 1:
                    return sections
            except Exception as e:
                print(f"OA PDF parse failed: {e}")

        # Europe PMC full text
        full_text = try_europepmc_text(doi)
        if full_text:
            parsed = sections_from_plain_text(full_text)
            sections.update(parsed)
            if len(sections) > 1:
                return sections

    # PubMed abstract may have structured sections
    if metadata.abstract and len(metadata.abstract) > 300:
        abstract_lower = metadata.abstract.lower()
        if any(kw in abstract_lower for kw in ("background:", "methods:", "results:", "conclusions:")):
            for label, key in [
                ("background", "introduction"),
                ("objective", "introduction"),
                ("methods", "methodology"),
                ("results", "results"),
                ("conclusions", "conclusion"),
            ]:
                match = re.search(rf"{label}[:\s]+(.*?)(?=(?:background|objective|methods|results|conclusions)[:\s]|$)",
                                  metadata.abstract, re.IGNORECASE | re.DOTALL)
                if match:
                    sections[key] = match.group(1).strip()

    if not sections and metadata.abstract:
        sections["abstract"] = metadata.abstract

    return sections
