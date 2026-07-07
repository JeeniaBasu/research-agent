"""
=============================================================================
utils/citation_utils.py — Citation Generation (APA, IEEE, MLA)
=============================================================================
Generates properly formatted academic citations from paper dicts.
Supports APA 7th edition, IEEE, and MLA 9th edition formats.
=============================================================================
"""

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class CitationManager:
    """
    Generates formatted citations in APA, IEEE, and MLA styles.
    All methods accept the unified paper dict schema.
    """

    SUPPORTED_STYLES = ["APA", "IEEE", "MLA"]

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def generate_citation(self, paper: dict, style: str = "APA") -> str:
        """
        Generate a citation string for a paper in the requested style.

        Args:
            paper: Unified paper dict from ResearchService.
            style: Citation style — "APA", "IEEE", or "MLA".

        Returns:
            Formatted citation string.
        """
        style = style.upper()
        if style == "APA":
            return self.apa(paper)
        elif style == "IEEE":
            return self.ieee(paper)
        elif style == "MLA":
            return self.mla(paper)
        else:
            logger.warning("Unknown citation style '%s', defaulting to APA.", style)
            return self.apa(paper)

    def generate_all_styles(self, paper: dict) -> dict:
        """Return citations in all three supported styles."""
        return {
            "APA": self.apa(paper),
            "IEEE": self.ieee(paper),
            "MLA": self.mla(paper),
        }

    def generate_bibliography(self, papers: list, style: str = "APA") -> str:
        """
        Generate a numbered bibliography from a list of papers.

        Returns:
            Formatted bibliography string.
        """
        if not papers:
            return "No references to display."

        lines = []
        for i, paper in enumerate(papers, 1):
            citation = self.generate_citation(paper, style)
            lines.append(f"[{i}] {citation}")

        header = f"References ({style} Format)\n{'=' * 40}\n"
        return header + "\n\n".join(lines)

    # ------------------------------------------------------------------
    # APA 7th Edition
    # ------------------------------------------------------------------

    def apa(self, paper: dict) -> str:
        """
        APA 7th Edition format:
        Author, A. A., & Author, B. B. (Year). Title of article. Journal Name, volume(issue), pages. DOI
        """
        authors = self._apa_authors(paper.get("authors", []))
        year = paper.get("year", "n.d.")
        title = self._sentence_case(paper.get("title", "Unknown title"))
        venue = paper.get("venue", "")
        doi = paper.get("doi", "")
        url = paper.get("url", "")
        source = paper.get("source", "")

        parts = []

        # Authors + Year
        parts.append(f"{authors} ({year}).")

        # Title (sentence case, no italics in plain text)
        parts.append(f"{title}.")

        # Source
        if venue:
            parts.append(f"*{venue}*.")
        elif source:
            parts.append(f"{source}.")

        # DOI / URL
        if doi:
            parts.append(f"https://doi.org/{doi}")
        elif url:
            parts.append(url)

        return " ".join(parts)

    def _apa_authors(self, authors: list) -> str:
        """Format authors list in APA style (Last, F. F.)."""
        if not authors:
            return "Unknown Author"

        formatted = []
        for author in authors[:20]:  # APA caps at 20 before et al.
            name = self._parse_author_name(author)
            if name["last"]:
                initials = "".join(f"{p[0].upper()}." for p in name["first_parts"] if p)
                formatted.append(f"{name['last']}, {initials}".strip().rstrip(","))
            else:
                formatted.append(author)

        if len(authors) <= 20:
            if len(formatted) == 1:
                return formatted[0]
            elif len(formatted) == 2:
                return f"{formatted[0]}, & {formatted[1]}"
            else:
                return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"
        else:
            return ", ".join(formatted[:19]) + "... " + formatted[-1]

    # ------------------------------------------------------------------
    # IEEE
    # ------------------------------------------------------------------

    def ieee(self, paper: dict) -> str:
        """
        IEEE format:
        A. A. Author and B. B. Author, "Title," Journal Name, vol. X, no. X, pp. XX-XX, Year. DOI
        """
        authors = self._ieee_authors(paper.get("authors", []))
        year = paper.get("year", "n.d.")
        title = paper.get("title", "Unknown title")
        venue = paper.get("venue", "")
        doi = paper.get("doi", "")
        url = paper.get("url", "")
        source = paper.get("source", "")

        parts = []
        parts.append(f"{authors},")
        parts.append(f'"{title},"')

        if venue:
            parts.append(f"*{venue}*,")
        elif source:
            parts.append(f"{source},")

        parts.append(f"{year}.")

        if doi:
            parts.append(f"doi: {doi}.")
        elif url:
            parts.append(f"[Online]. Available: {url}")

        return " ".join(parts)

    def _ieee_authors(self, authors: list) -> str:
        """Format authors list in IEEE style (A. A. Last)."""
        if not authors:
            return "Unknown"

        formatted = []
        for author in authors[:6]:
            name = self._parse_author_name(author)
            if name["last"]:
                initials = ". ".join(
                    p[0].upper() for p in name["first_parts"] if p
                )
                if initials:
                    formatted.append(f"{initials}. {name['last']}")
                else:
                    formatted.append(name["last"])
            else:
                formatted.append(author)

        if len(authors) > 6:
            return " and ".join(formatted[:6]) + " et al."
        elif len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]} and {formatted[1]}"
        else:
            return ", ".join(formatted[:-1]) + f", and {formatted[-1]}"

    # ------------------------------------------------------------------
    # MLA 9th Edition
    # ------------------------------------------------------------------

    def mla(self, paper: dict) -> str:
        """
        MLA 9th Edition format:
        Last, First, and First Last. "Title." Journal, vol. X, no. X, Year, pp. X-X. DOI
        """
        authors = self._mla_authors(paper.get("authors", []))
        year = paper.get("year", "n.d.")
        title = paper.get("title", "Unknown title")
        venue = paper.get("venue", "")
        doi = paper.get("doi", "")
        url = paper.get("url", "")
        source = paper.get("source", "")

        parts = []
        parts.append(f"{authors}.")
        parts.append(f'"{title}."')

        if venue:
            parts.append(f"*{venue}*,")
        elif source:
            parts.append(f"{source},")

        parts.append(f"{year}.")

        if doi:
            parts.append(f"https://doi.org/{doi}.")
        elif url:
            parts.append(f"{url}.")

        return " ".join(parts)

    def _mla_authors(self, authors: list) -> str:
        """Format authors list in MLA style."""
        if not authors:
            return "Unknown"

        formatted = []
        for i, author in enumerate(authors[:3]):
            name = self._parse_author_name(author)
            if name["last"]:
                if i == 0:
                    first = " ".join(name["first_parts"])
                    formatted.append(f"{name['last']}, {first}")
                else:
                    first = " ".join(name["first_parts"])
                    formatted.append(f"{first} {name['last']}")
            else:
                formatted.append(author)

        if len(authors) > 3:
            return formatted[0] + ", et al."
        elif len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]}, and {formatted[1]}"
        else:
            return f"{formatted[0]}, {formatted[1]}, and {formatted[2]}"

    # ------------------------------------------------------------------
    # Name parsing helper
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_author_name(name: str) -> dict:
        """
        Parse an author name string into last name and first name parts.
        Handles "First Last", "Last, First" formats.
        """
        name = name.strip()
        result = {"last": "", "first_parts": []}

        if not name:
            return result

        # Format: "Last, First Middle"
        if "," in name:
            parts = name.split(",", 1)
            result["last"] = parts[0].strip()
            result["first_parts"] = parts[1].strip().split() if len(parts) > 1 else []
        else:
            # Format: "First Middle Last"
            parts = name.split()
            if len(parts) >= 2:
                result["last"] = parts[-1]
                result["first_parts"] = parts[:-1]
            else:
                result["last"] = name
        return result

    @staticmethod
    def _sentence_case(text: str) -> str:
        """Convert a title to sentence case (first word + proper nouns capitalised)."""
        if not text:
            return text
        words = text.split()
        if not words:
            return text
        result = [words[0].capitalize()]
        for word in words[1:]:
            # Keep acronyms and proper nouns (all-caps or starts with capital)
            if word.isupper() or (len(word) > 1 and word[0].isupper() and not word[1:].isupper()):
                result.append(word)
            else:
                result.append(word.lower())
        return " ".join(result)
