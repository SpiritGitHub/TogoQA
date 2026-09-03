"""Crawler INSEED (inseed.tg) — statistiques officielles du Togo.

Cible : annuaires statistiques, tableaux de bord éducation,
rapports PDF, indicateurs démographiques et scolaires.
"""

import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from src.ingestion.crawlers.base import BaseCrawler, CrawlResult

logger = logging.getLogger(__name__)

EDUCATION_SECTION_KEYWORDS = re.compile(
    r"(?:éducati|scolai|enseign|alphabéti|scolarisa|formation|"
    r"annuaire|tableau.de.bord|indicateur|statistique|démographi|"
    r"population.*âge.*scolaire|enquête.*ménage|recensement)",
    re.IGNORECASE,
)


@dataclass
class INSEEDCrawler(BaseCrawler):
    """Crawler for inseed.tg — Institut National de la Statistique du Togo."""

    name: str = "inseed"
    allowed_domains: list[str] = field(
        default_factory=lambda: ["inseed.tg", "www.inseed.tg"]
    )
    start_urls: list[str] = field(
        default_factory=lambda: [
            "https://inseed.tg/",
            "https://inseed.tg/statistiques-sociales/",
            "https://inseed.tg/publications/",
            "https://inseed.tg/tableaux-de-bord/",
        ]
    )
    delay: float = 2.5
    max_pages: int = 200
    download_extensions: tuple = (".pdf", ".xlsx", ".xls", ".csv")

    def filter_result(self, result: CrawlResult) -> CrawlResult | None:
        if result.content_type in ("application/pdf",) or self._is_downloadable_doc(result):
            result.metadata["source_name"] = "INSEED"
            result.metadata["source_id"] = "INSEED"
            self._extract_pdf_metadata(result)
            return result

        if result.content_type == "text/html":
            if not self._is_education_relevant(result):
                return None
            result.metadata["source_name"] = "INSEED"
            result.metadata["source_id"] = "INSEED"
            self._extract_publication_info(result)
            return result

        return result

    def _is_downloadable_doc(self, result: CrawlResult) -> bool:
        return any(result.url.lower().endswith(ext) for ext in self.download_extensions)

    def _is_education_relevant(self, result: CrawlResult) -> bool:
        searchable = (result.title or "") + " " + (result.text or "")[:3000]
        return bool(EDUCATION_SECTION_KEYWORDS.search(searchable))

    def _extract_pdf_metadata(self, result: CrawlResult):
        """Infer metadata from PDF URL and filename."""
        filename = result.metadata.get("filename", "")

        year_match = re.search(r"(20[12]\d)", filename)
        if year_match:
            result.metadata["reference_year"] = year_match.group(1)

        school_year_match = re.search(r"(20[12]\d)[-_](20[12]\d)", filename)
        if school_year_match:
            result.metadata["school_year"] = f"{school_year_match.group(1)}-{school_year_match.group(2)}"

        name_lower = filename.lower()
        if "annuaire" in name_lower:
            result.metadata["document_type"] = "annuaire"
        elif "tableau" in name_lower and "bord" in name_lower:
            result.metadata["document_type"] = "tableau_de_bord"
        elif "rapport" in name_lower:
            result.metadata["document_type"] = "rapport"
        elif "enquete" in name_lower or "enquête" in name_lower:
            result.metadata["document_type"] = "rapport"

    def _extract_publication_info(self, result: CrawlResult):
        """Extract publication date and type from INSEED HTML pages."""
        soup = BeautifulSoup(result.raw_content, "html.parser")

        time_tag = soup.find("time")
        if time_tag:
            result.published_at = time_tag.get("datetime", time_tag.get_text(strip=True))

        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if href.endswith(".pdf"):
                result.metadata.setdefault("linked_pdfs", [])
                result.metadata["linked_pdfs"].append(a["href"])

    def list_pdf_links(self, result: CrawlResult) -> list[str]:
        """Extract all PDF download links from an HTML page."""
        if result.content_type != "text/html":
            return []
        soup = BeautifulSoup(result.raw_content, "html.parser")
        pdfs = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf"):
                from urllib.parse import urljoin
                pdfs.append(urljoin(result.url, href))
        return pdfs
