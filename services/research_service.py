"""
=============================================================================
services/research_service.py — Academic Database Integration
=============================================================================
Fetches scholarly papers from arXiv, Semantic Scholar, Crossref, and PubMed.
Normalises all results into a unified paper schema.
=============================================================================
"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Optional
import feedparser
import requests
from datetime import datetime

from config import ResearchConfig, AGENT_INSTRUCTIONS

logger = logging.getLogger(__name__)

# Unified paper schema keys
# {title, authors, abstract, year, source, url, doi, keywords, citations, venue}


class ResearchService:
    """
    Unified academic research retrieval service.
    Queries multiple databases according to AGENT_INSTRUCTIONS['preferred_databases']
    and returns normalised, deduplicated results.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ResearchMind-Agent/1.0 (IBM Watsonx Hackathon; mailto:agent@example.com)"
        })
        if ResearchConfig.SEMANTIC_SCHOLAR_API_KEY:
            self.session.headers.update({
                "x-api-key": ResearchConfig.SEMANTIC_SCHOLAR_API_KEY
            })

    # ------------------------------------------------------------------
    # Main search entry point
    # ------------------------------------------------------------------

    def search(self, query: str, max_results: int = None, databases: list = None) -> list:
        """
        Search across configured databases and return merged, deduplicated results.

        Args:
            query: Natural language or keyword query string.
            max_results: Maximum number of papers to return.
            databases: Override default database order from AGENT_INSTRUCTIONS.

        Returns:
            List of normalised paper dicts.
        """
        if max_results is None:
            max_results = ResearchConfig.MAX_PAPERS_PER_SEARCH

        db_order = databases or AGENT_INSTRUCTIONS.get("preferred_databases", ["arxiv"])
        per_db = max(3, max_results // len(db_order))

        all_papers = []
        seen_titles = set()

        for db in db_order:
            try:
                logger.info("Searching %s for: %s", db, query)
                if db == "arxiv":
                    results = self._search_arxiv(query, per_db)
                elif db == "semantic_scholar":
                    results = self._search_semantic_scholar(query, per_db)
                elif db == "crossref":
                    results = self._search_crossref(query, per_db)
                elif db == "pubmed":
                    results = self._search_pubmed(query, per_db)
                else:
                    logger.warning("Unknown database: %s", db)
                    continue

                # Deduplicate by normalised title
                for paper in results:
                    norm_title = paper.get("title", "").lower().strip()
                    if norm_title and norm_title not in seen_titles:
                        seen_titles.add(norm_title)
                        all_papers.append(paper)

                logger.info("  → %d unique papers from %s", len(results), db)

            except Exception as exc:
                logger.error("Error searching %s: %s", db, exc)

        # Sort by year descending (most recent first), then by citation count
        all_papers.sort(
            key=lambda p: (p.get("year", 0) or 0, p.get("citations", 0) or 0),
            reverse=True,
        )

        return all_papers[:max_results]

    def get_paper_by_id(self, paper_id: str, source: str = "arxiv") -> Optional[dict]:
        """Retrieve a single paper by its ID from a specific database."""
        try:
            if source == "arxiv":
                results = self._search_arxiv(f"id:{paper_id}", 1)
                return results[0] if results else None
            elif source == "semantic_scholar":
                return self._get_semantic_scholar_paper(paper_id)
            elif source == "pubmed":
                results = self._fetch_pubmed_details([paper_id])
                return results[0] if results else None
        except Exception as exc:
            logger.error("Error fetching paper %s from %s: %s", paper_id, source, exc)
        return None

    # ------------------------------------------------------------------
    # arXiv
    # ------------------------------------------------------------------

    def _search_arxiv(self, query: str, max_results: int) -> list:
        """Search arXiv using its Atom feed API."""
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        response = self._get(ResearchConfig.ARXIV_BASE_URL, params=params)
        if not response:
            return []

        feed = feedparser.parse(response.text)
        papers = []

        for entry in feed.entries:
            try:
                # Extract arXiv ID from the URL
                paper_id = entry.id.split("/abs/")[-1] if "/abs/" in entry.id else entry.id

                # Parse publication year
                year = None
                if hasattr(entry, "published"):
                    try:
                        year = int(entry.published[:4])
                    except (ValueError, IndexError):
                        pass

                # Extract authors
                authors = []
                if hasattr(entry, "authors"):
                    authors = [a.get("name", "") for a in entry.authors if a.get("name")]

                # Extract categories as keywords
                keywords = []
                if hasattr(entry, "tags"):
                    keywords = [t.get("term", "") for t in entry.tags if t.get("term")]

                # Find PDF link
                url = entry.get("link", "")
                for link in entry.get("links", []):
                    if link.get("type") == "application/pdf":
                        url = link.get("href", url)
                        break

                papers.append({
                    "id": f"arxiv:{paper_id}",
                    "title": entry.get("title", "").replace("\n", " ").strip(),
                    "authors": authors,
                    "abstract": entry.get("summary", "").replace("\n", " ").strip(),
                    "year": year,
                    "source": "arXiv",
                    "url": url,
                    "doi": entry.get("arxiv_doi", ""),
                    "keywords": keywords[:8],
                    "citations": None,
                    "venue": "arXiv preprint",
                    "arxiv_id": paper_id,
                })
            except Exception as exc:
                logger.debug("Error parsing arXiv entry: %s", exc)

        return papers

    # ------------------------------------------------------------------
    # Semantic Scholar
    # ------------------------------------------------------------------

    def _search_semantic_scholar(self, query: str, max_results: int) -> list:
        """Search Semantic Scholar Graph API."""
        url = f"{ResearchConfig.SEMANTIC_SCHOLAR_BASE_URL}/paper/search"
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": "title,authors,abstract,year,externalIds,citationCount,venue,publicationTypes,tldr,openAccessPdf",
        }

        response = self._get(url, params=params)
        if not response:
            return []

        data = response.json()
        papers = []

        for item in data.get("data", []):
            try:
                authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
                doi = item.get("externalIds", {}).get("DOI", "")
                arxiv_id = item.get("externalIds", {}).get("ArXiv", "")
                url_paper = ""

                open_access = item.get("openAccessPdf")
                if open_access:
                    url_paper = open_access.get("url", "")
                if not url_paper and arxiv_id:
                    url_paper = f"https://arxiv.org/abs/{arxiv_id}"

                papers.append({
                    "id": f"s2:{item.get('paperId', '')}",
                    "title": item.get("title", "").strip(),
                    "authors": authors,
                    "abstract": item.get("abstract", ""),
                    "year": item.get("year"),
                    "source": "Semantic Scholar",
                    "url": url_paper,
                    "doi": doi,
                    "keywords": [],
                    "citations": item.get("citationCount", 0),
                    "venue": item.get("venue", ""),
                    "tldr": item.get("tldr", {}).get("text", "") if item.get("tldr") else "",
                    "s2_id": item.get("paperId", ""),
                })
            except Exception as exc:
                logger.debug("Error parsing S2 paper: %s", exc)

        return papers

    def _get_semantic_scholar_paper(self, paper_id: str) -> Optional[dict]:
        """Fetch a single paper from Semantic Scholar by ID."""
        url = f"{ResearchConfig.SEMANTIC_SCHOLAR_BASE_URL}/paper/{paper_id}"
        params = {"fields": "title,authors,abstract,year,externalIds,citationCount,venue,references"}
        response = self._get(url, params=params)
        if response:
            item = response.json()
            authors = [a.get("name", "") for a in item.get("authors", [])]
            return {
                "id": f"s2:{paper_id}",
                "title": item.get("title", ""),
                "authors": authors,
                "abstract": item.get("abstract", ""),
                "year": item.get("year"),
                "source": "Semantic Scholar",
                "url": "",
                "doi": item.get("externalIds", {}).get("DOI", ""),
                "keywords": [],
                "citations": item.get("citationCount", 0),
                "venue": item.get("venue", ""),
            }
        return None

    # ------------------------------------------------------------------
    # Crossref
    # ------------------------------------------------------------------

    def _search_crossref(self, query: str, max_results: int) -> list:
        """Search Crossref for peer-reviewed publications."""
        params = {
            "query": query,
            "rows": min(max_results, 100),
            "select": "title,author,abstract,published,DOI,URL,container-title,is-referenced-by-count,subject",
            "sort": "relevance",
            "order": "desc",
        }

        response = self._get(ResearchConfig.CROSSREF_BASE_URL, params=params)
        if not response:
            return []

        data = response.json()
        papers = []

        for item in data.get("message", {}).get("items", []):
            try:
                # Extract title
                title_list = item.get("title", [])
                title = title_list[0] if title_list else ""
                if not title:
                    continue

                # Extract authors
                authors = []
                for a in item.get("author", []):
                    name_parts = [a.get("given", ""), a.get("family", "")]
                    name = " ".join(p for p in name_parts if p).strip()
                    if name:
                        authors.append(name)

                # Extract year
                year = None
                pub = item.get("published", {}) or item.get("published-print", {})
                date_parts = pub.get("date-parts", [[]])
                if date_parts and date_parts[0]:
                    try:
                        year = int(date_parts[0][0])
                    except (ValueError, IndexError):
                        pass

                # Extract abstract (may contain JATS XML)
                abstract = item.get("abstract", "")
                if abstract:
                    # Strip basic JATS tags
                    import re
                    abstract = re.sub(r"<[^>]+>", "", abstract).strip()

                venue = ""
                ct = item.get("container-title", [])
                if ct:
                    venue = ct[0]

                papers.append({
                    "id": f"cr:{item.get('DOI', '')}",
                    "title": title.strip(),
                    "authors": authors,
                    "abstract": abstract,
                    "year": year,
                    "source": "Crossref",
                    "url": item.get("URL", f"https://doi.org/{item.get('DOI', '')}"),
                    "doi": item.get("DOI", ""),
                    "keywords": item.get("subject", [])[:8],
                    "citations": item.get("is-referenced-by-count", 0),
                    "venue": venue,
                })
            except Exception as exc:
                logger.debug("Error parsing Crossref item: %s", exc)

        return papers

    # ------------------------------------------------------------------
    # PubMed
    # ------------------------------------------------------------------

    def _search_pubmed(self, query: str, max_results: int) -> list:
        """Search PubMed via NCBI E-utilities."""
        # Step 1: Search for IDs
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": min(max_results, 100),
            "retmode": "json",
            "sort": "relevance",
        }
        if ResearchConfig.PUBMED_API_KEY:
            search_params["api_key"] = ResearchConfig.PUBMED_API_KEY

        response = self._get(ResearchConfig.PUBMED_SEARCH_URL, params=search_params)
        if not response:
            return []

        ids = response.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        # Step 2: Fetch paper details
        return self._fetch_pubmed_details(ids)

    def _fetch_pubmed_details(self, pmids: list) -> list:
        """Fetch PubMed article details for a list of PMIDs."""
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        }
        if ResearchConfig.PUBMED_API_KEY:
            fetch_params["api_key"] = ResearchConfig.PUBMED_API_KEY

        response = self._get(ResearchConfig.PUBMED_FETCH_URL, params=fetch_params)
        if not response:
            return []

        papers = []
        try:
            root = ET.fromstring(response.content)
            for article in root.findall(".//PubmedArticle"):
                try:
                    paper = self._parse_pubmed_article(article)
                    if paper:
                        papers.append(paper)
                except Exception as exc:
                    logger.debug("Error parsing PubMed article: %s", exc)
        except ET.ParseError as exc:
            logger.error("XML parse error for PubMed response: %s", exc)

        return papers

    def _parse_pubmed_article(self, article) -> Optional[dict]:
        """Parse a single PubMed XML article element."""
        medline = article.find("MedlineCitation")
        if medline is None:
            return None

        # PMID
        pmid_el = medline.find("PMID")
        pmid = pmid_el.text if pmid_el is not None else ""

        art = medline.find("Article")
        if art is None:
            return None

        # Title
        title_el = art.find("ArticleTitle")
        title = title_el.text or "" if title_el is not None else ""

        # Abstract
        abstract_texts = art.findall(".//AbstractText")
        abstract = " ".join(el.text or "" for el in abstract_texts if el.text)

        # Authors
        authors = []
        for author in art.findall(".//Author"):
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            name = f"{fore} {last}".strip()
            if name:
                authors.append(name)

        # Year
        year = None
        pub_date = art.find(".//PubDate")
        if pub_date is not None:
            year_el = pub_date.find("Year")
            if year_el is not None and year_el.text:
                try:
                    year = int(year_el.text)
                except ValueError:
                    pass

        # Journal
        journal_el = art.find(".//Journal/Title")
        venue = journal_el.text if journal_el is not None else ""

        # DOI
        doi = ""
        for eid in article.findall(".//ArticleId"):
            if eid.get("IdType") == "doi":
                doi = eid.text or ""
                break

        # Keywords / MeSH
        keywords = [
            mh.findtext("DescriptorName", "")
            for mh in medline.findall(".//MeshHeading")
        ]
        keywords = [k for k in keywords if k][:8]

        return {
            "id": f"pmid:{pmid}",
            "title": title.strip(),
            "authors": authors,
            "abstract": abstract.strip(),
            "year": year,
            "source": "PubMed",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "doi": doi,
            "keywords": keywords,
            "citations": None,
            "venue": venue,
            "pmid": pmid,
        }

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _get(self, url: str, params: dict = None) -> Optional[requests.Response]:
        """Make a GET request with retries and timeout."""
        for attempt in range(ResearchConfig.MAX_RETRIES):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=ResearchConfig.REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                logger.warning("Timeout on %s (attempt %d/%d)", url, attempt + 1, ResearchConfig.MAX_RETRIES)
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response else 0
                if status == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    logger.warning("Rate limited by %s. Waiting %ds...", url, wait_time)
                    time.sleep(wait_time)
                elif status == 404:
                    logger.debug("404 Not Found: %s", url)
                    return None
                else:
                    logger.error("HTTP %d error for %s: %s", status, url, exc)
                    return None
            except requests.exceptions.RequestException as exc:
                logger.error("Request error for %s: %s", url, exc)
                return None

        logger.error("All %d retries failed for %s", ResearchConfig.MAX_RETRIES, url)
        return None
