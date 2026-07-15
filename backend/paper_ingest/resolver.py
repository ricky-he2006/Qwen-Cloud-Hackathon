"""
Universal paper resolver — arXiv, DOI, PubMed, publisher URLs, and text search.
"""

import html
import json
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, unquote, urlparse

import requests

from paper_ingest.fetcher import PaperMetadata

USER_AGENT = "ResearchSociety/1.0 (https://github.com/research-society; research-tool)"
REQUEST_TIMEOUT = 25


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _openalex_abstract(work: dict) -> str:
    if work.get("abstract"):
        return work["abstract"]
    inverted = work.get("abstract_inverted_index")
    if not inverted:
        return ""
    words: List[Tuple[int, str]] = []
    for word, positions in inverted.items():
        for pos in positions:
            words.append((pos, word))
    words.sort(key=lambda x: x[0])
    return " ".join(w for _, w in words)


def _metadata_from_openalex(work: dict) -> PaperMetadata:
    doi = (work.get("doi") or "").replace("https://doi.org/", "")
    authors = []
    for auth in work.get("authorships") or []:
        name = (auth.get("author") or {}).get("display_name")
        if name:
            authors.append(name)

    loc = work.get("primary_location") or {}
    landing = loc.get("landing_page_url") or work.get("id") or ""

    topics = [
        (t.get("display_name") or "")
        for t in (work.get("topics") or [])[:5]
        if t.get("display_name")
    ]

    return PaperMetadata(
        title=work.get("title") or work.get("display_name") or "",
        authors=authors,
        abstract=_openalex_abstract(work),
        published_date=str(work.get("publication_date") or work.get("publication_year") or ""),
        paper_id=doi or work.get("id", "").split("/")[-1],
        url=landing,
        categories=topics,
    )


def fetch_crossref(doi: str) -> Optional[PaperMetadata]:
    """Fetch metadata from Crossref REST API."""
    clean = doi.replace("https://doi.org/", "").strip()
    try:
        response = requests.get(
            f"https://api.crossref.org/works/{quote(clean, safe='')}",
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return None

        data = response.json().get("message", {})
        authors = []
        for author in data.get("author") or []:
            given = author.get("given", "")
            family = author.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                authors.append(name)

        title = ""
        if data.get("title"):
            title = data["title"][0] if isinstance(data["title"], list) else data["title"]

        pub_date = ""
        for key in ("published-print", "published-online", "created"):
            parts = (data.get(key) or {}).get("date-parts", [[]])
            if parts and parts[0]:
                pub_date = "-".join(str(p) for p in parts[0][:3])
                break

        categories = []
        for subj in (data.get("subject") or [])[:5]:
            categories.append(subj)

        return PaperMetadata(
            title=title,
            authors=authors,
            abstract=_strip_html(data.get("abstract", "") or ""),
            published_date=pub_date,
            paper_id=clean,
            url=f"https://doi.org/{clean}",
            categories=categories,
        )
    except Exception as e:
        print(f"Crossref fetch failed for {clean}: {e}")
        return None


def search_openalex(query: str, per_page: int = 5) -> List[PaperMetadata]:
    try:
        response = requests.get(
            "https://api.openalex.org/works",
            params={"search": query, "per_page": per_page, "mailto": "research@example.com"},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return []
        return [_metadata_from_openalex(w) for w in response.json().get("results", [])]
    except Exception as e:
        print(f"OpenAlex search failed: {e}")
        return []


def fetch_openalex_doi(doi: str) -> Optional[PaperMetadata]:
    clean = doi.replace("https://doi.org/", "").strip()
    try:
        response = requests.get(
            f"https://api.openalex.org/works/https://doi.org/{quote(clean, safe='')}",
            params={"mailto": "research@example.com"},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return None
        return _metadata_from_openalex(response.json())
    except Exception as e:
        print(f"OpenAlex DOI lookup failed: {e}")
        return None


def fetch_pubmed(pmid: str) -> Optional[PaperMetadata]:
    """Fetch metadata from PubMed / NCBI E-utilities."""
    try:
        response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": pmid, "retmode": "xml"},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return None

        root = ET.fromstring(response.text)
        article = root.find(".//PubmedArticle")
        if article is None:
            return None

        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""

        abstract_parts = []
        for abs_el in article.findall(".//AbstractText"):
            label = abs_el.get("Label", "")
            text = "".join(abs_el.itertext()).strip()
            if label:
                abstract_parts.append(f"{label}: {text}")
            elif text:
                abstract_parts.append(text)
        abstract = "\n".join(abstract_parts)

        authors = []
        for author in article.findall(".//Author"):
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            name = f"{fore} {last}".strip()
            if name:
                authors.append(name)

        doi = ""
        for id_el in article.findall(".//ArticleId"):
            if id_el.get("IdType") == "doi":
                doi = id_el.text or ""
                break

        year = article.findtext(".//PubDate/Year", "")

        categories = []
        for kw in article.findall(".//Keyword")[:5]:
            if kw.text:
                categories.append(kw.text)

        return PaperMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            published_date=year,
            paper_id=doi or f"pmid:{pmid}",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            categories=categories,
        )
    except Exception as e:
        print(f"PubMed fetch failed for {pmid}: {e}")
        return None


def extract_metadata_from_html(page_html: str, source_url: str) -> Optional[PaperMetadata]:
    """Extract scholarly metadata from HTML meta tags (Highwire / Dublin Core / JSON-LD)."""
    if not page_html or len(page_html) < 200:
        return None

    def meta_content(*names: str) -> str:
        for name in names:
            patterns = [
                rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
                rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(name)}["\']',
                rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            ]
            for pattern in patterns:
                match = re.search(pattern, page_html, re.IGNORECASE)
                if match:
                    return html.unescape(match.group(1)).strip()
        return ""

    title = meta_content(
        "citation_title", "dc.Title", "DC.Title", "og:title", "twitter:title"
    )
    doi = meta_content("citation_doi", "dc.identifier", "DC.Identifier", "prism.doi")
    abstract = meta_content("citation_abstract", "dc.Description", "og:description", "description")

    authors = re.findall(
        r'<meta[^>]+name=["\']citation_author["\'][^>]+content=["\']([^"\']+)["\']',
        page_html,
        re.IGNORECASE,
    )
    if not authors:
        authors = re.findall(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_author["\']',
            page_html,
            re.IGNORECASE,
        )

    if not doi:
        doi_match = re.search(r"(10\.\d{4,9}/[^\s\"\'<>]+)", page_html)
        if doi_match:
            doi = doi_match.group(1).rstrip(".,;")

    if not title:
        json_ld_blocks = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            page_html,
            re.IGNORECASE | re.DOTALL,
        )
        for block in json_ld_blocks:
            try:
                data = json.loads(block)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("@type") in ("ScholarlyArticle", "Article", "MedicalScholarlyArticle"):
                        title = title or item.get("headline") or item.get("name") or ""
                        abstract = abstract or item.get("description") or ""
                        if item.get("identifier") and not doi:
                            ident = item["identifier"]
                            if isinstance(ident, str) and ident.startswith("10."):
                                doi = ident
            except json.JSONDecodeError:
                continue

    if not title and not doi:
        return None

    if doi and not abstract:
        crossref = fetch_crossref(doi)
        if crossref:
            if not title:
                title = crossref.title
            if not authors:
                authors = crossref.authors
            abstract = abstract or crossref.abstract
            return crossref

    return PaperMetadata(
        title=title,
        authors=[html.unescape(a) for a in authors],
        abstract=_strip_html(abstract),
        published_date=meta_content("citation_publication_date", "citation_date", "dc.Date"),
        paper_id=doi or source_url,
        url=source_url,
        categories=[],
    )


def _extract_doi_from_text(text: str) -> Optional[str]:
    """Pull a DOI from free text, URLs, or citations."""
    match = re.search(r"\b(10\.\d{4,9}/[^\s\]<>\)\"']+)", text)
    if not match:
        return None
    return match.group(1).rstrip(".,;)")


def _is_cloudflare_challenge(html: str) -> bool:
    return bool(html) and (
        "Just a moment" in html
        or "cf-chl" in html
        or "challenge-platform" in html
    )


JOURNAL_SLUG_NAMES = {
    "jamaneurology": "JAMA Neurology",
    "jama": "JAMA",
    "jamainternalmedicine": "JAMA Internal Medicine",
    "jamapsychiatry": "JAMA Psychiatry",
    "jamapediatrics": "JAMA Pediatrics",
    "jamaoncology": "JAMA Oncology",
    "jamacardiology": "JAMA Cardiology",
    "jamadermatology": "JAMA Dermatology",
    "jamasurgery": "JAMA Surgery",
    "jamanetworkopen": "JAMA Network Open",
}


def _resolve_jamanetwork_url(url: str, path: str) -> Optional[PaperMetadata]:
    """Resolve JAMA Network URLs when HTML is Cloudflare-blocked."""
    match = re.search(r"/journals/([^/]+)/fullarticle/(\d+)", path)
    if not match:
        return None

    slug, article_id = match.group(1), match.group(2)
    journal_name = JOURNAL_SLUG_NAMES.get(slug.lower(), slug.replace("-", " ").title())

    try:
        search = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": f'"{journal_name}"[ta] AND {article_id}[AID]',
                "retmode": "json",
                "retmax": 3,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if search.status_code == 200:
            ids = search.json().get("esearchresult", {}).get("idlist", [])
            for pmid in ids:
                meta = fetch_pubmed(pmid)
                if meta:
                    return meta
    except Exception:
        pass

    source_ids = {
        "jamaneurology": "S164389565",
        "jama": "S137902535",
    }
    source = source_ids.get(slug.lower())
    if source:
        try:
            response = requests.get(
                "https://api.openalex.org/works",
                params={
                    "filter": f"primary_location.source.id:{source}",
                    "search": article_id,
                    "per_page": 5,
                    "mailto": "research@example.com",
                },
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code == 200:
                for work in response.json().get("results", []):
                    landing = (work.get("primary_location") or {}).get("landing_page_url") or ""
                    if article_id in landing:
                        return _metadata_from_openalex(work)
        except Exception:
            pass

    return None


def fetch_url(url: str) -> Optional[PaperMetadata]:
    """Resolve a paper from any publisher or repository URL."""
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""

    # arXiv
    arxiv_match = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", url)
    if arxiv_match:
        from paper_ingest.fetcher import PaperFetcher
        return PaperFetcher().fetch_by_arxiv_id(arxiv_match.group(1))

    # DOI redirect URLs
    doi_match = re.search(r"doi\.org/(10\.\d{4,9}/.+)", url, re.IGNORECASE)
    if doi_match:
        return fetch_crossref(unquote(doi_match.group(1))) or fetch_openalex_doi(doi_match.group(1))

    # PubMed
    pubmed_match = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", url)
    if pubmed_match:
        meta = fetch_pubmed(pubmed_match.group(1))
        if meta and meta.paper_id.startswith("10."):
            enriched = fetch_crossref(meta.paper_id)
            if enriched and enriched.abstract:
                meta.abstract = enriched.abstract or meta.abstract
        return meta

    # PMC
    pmc_match = re.search(r"/pmc/articles/(PMC\d+)", url, re.IGNORECASE)
    if pmc_match:
        meta = fetch_pubmed(pmc_match.group(1).replace("PMC", ""))
        return meta

    # biorxiv / medrxiv — extract DOI from URL
    biorxiv_match = re.search(r"(?:bio|med)rxiv\.org/content/10\.1101/\S+", url)
    if biorxiv_match:
        doi = re.search(r"(10\.1101/\S+)", url)
        if doi:
            return fetch_crossref(doi.group(1).rstrip("/"))

    # Fetch HTML and extract citation meta tags (JAMA, Nature, Wiley, Springer, etc.)
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ResearchSociety/1.0; +research-tool)",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if response.status_code == 200 and "text/html" in response.headers.get("Content-Type", ""):
            if _is_cloudflare_challenge(response.text):
                if "jamanetwork.com" in host:
                    jama_meta = _resolve_jamanetwork_url(url, path)
                    if jama_meta:
                        return jama_meta
            else:
                html_meta = extract_metadata_from_html(response.text, response.url)
                if html_meta:
                    if html_meta.paper_id.startswith("10."):
                        enriched = fetch_crossref(html_meta.paper_id)
                        if enriched:
                            if not html_meta.abstract:
                                html_meta.abstract = enriched.abstract
                            if not html_meta.authors:
                                html_meta.authors = enriched.authors
                            if not html_meta.title:
                                html_meta.title = enriched.title
                    return html_meta
    except Exception as e:
        print(f"URL HTML fetch failed for {url}: {e}")

    # JAMA Network fallback when fetch never ran (non-HTML response)
    if "jamanetwork.com" in host:
        jama_meta = _resolve_jamanetwork_url(url, path)
        if jama_meta:
            return jama_meta

    # OpenAlex: search using URL path slug as hint
    slug = path.rstrip("/").split("/")[-1]
    if slug and slug.isdigit() and "jama" in host:
        results = search_openalex(f"jama network article {slug}", per_page=3)
        for result in results:
            if slug in (result.url or ""):
                return result
        if results:
            return results[0]

    # Last resort: search OpenAlex with hostname + slug
    if slug:
        results = search_openalex(f"{host} {slug}", per_page=3)
        if results:
            return results[0]

    return None


def resolve_identifier(identifier: str) -> Tuple[str, Optional[PaperMetadata]]:
    """
    Universal resolver — accepts DOI, arXiv ID, PubMed ID, URL, or free-text search.
    Returns (source_type, metadata).
    """
    from paper_ingest.fetcher import PaperFetcher

    raw = identifier.strip()
    if not raw:
        return ("unknown", None)

    # DOI embedded in URL, citation, or pasted text (check before arXiv)
    embedded_doi = _extract_doi_from_text(raw)
    if embedded_doi and not re.match(r"^\d{4}\.\d{5}", raw):
        meta = fetch_crossref(embedded_doi) or fetch_openalex_doi(embedded_doi)
        if meta:
            return ("doi", meta)

    fetcher = PaperFetcher()

    # arXiv ID
    if re.match(r"^\d{4}\.\d{5}(v\d+)?$", raw):
        clean = re.sub(r"v\d+$", "", raw)
        return ("arxiv", fetcher.fetch_by_arxiv_id(clean))

    # DOI (bare)
    if re.match(r"^10\.\d{4,9}/\S+$", raw):
        meta = fetch_crossref(raw) or fetch_openalex_doi(raw)
        return ("doi", meta)

    # PubMed ID
    if re.match(r"^(pmid:)?\d{7,8}$", raw, re.IGNORECASE):
        pmid = re.sub(r"^pmid:", "", raw, flags=re.IGNORECASE)
        return ("pubmed", fetch_pubmed(pmid))

    # URL
    if raw.startswith("http"):
        meta = fetch_url(raw)
        if meta:
            source = "doi" if meta.paper_id.startswith("10.") else "url"
            return (source, meta)
        return ("url", None)

    # Free-text search: OpenAlex first (all publishers), then arXiv
    openalex_results = search_openalex(raw, per_page=1)
    if openalex_results:
        return ("search", openalex_results[0])

    arxiv_results = fetcher.search_arxiv(raw, max_results=1)
    if arxiv_results:
        return ("arxiv", arxiv_results[0])

    return ("unknown", None)
