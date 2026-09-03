"""Crawler du Ministère des Enseignements Primaire et Secondaire (education.gouv.tg).

Cible : actualités, communiqués, résultats d'examens, chiffres clés,
textes réglementaires publiés sur le portail du MEN.
"""

import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from src.ingestion.crawlers.base import BaseCrawler, CrawlResult

logger = logging.getLogger(__name__)

EDUCATION_KEYWORDS = re.compile(
    r"(?:examen|résultat|bac|bepc|cepd|scol|éducati|enseignant|élève|effectif|"
    r"rentrée|inscription|formation|primaire|secondaire|statistique|annuaire|"
    r"communiqué|arrêté|circulaire|réforme|curricul)",
    re.IGNORECASE,
)


@dataclass
class MENCrawler(BaseCrawler):
    """Crawler for education.gouv.tg — Togo Ministry of Education."""

    name: str = "men"
    allowed_domains: list[str] = field(
        default_factory=lambda: ["education.gouv.tg", "www.education.gouv.tg"]
    )
    start_urls: list[str] = field(
        default_factory=lambda: [
            "https://education.gouv.tg/",
            "https://education.gouv.tg/actualites/",
            "https://education.gouv.tg/communiques/",
            "https://education.gouv.tg/statistiques/",
        ]
    )
    delay: float = 2.0
    max_pages: int = 300

    def filter_result(self, result: CrawlResult) -> CrawlResult | None:
        if result.content_type != "text/html":
            return result

        if not self._is_education_relevant(result):
            return None

        result.metadata["source_name"] = "MEN Togo"
        result.metadata["source_id"] = "MEPS"

        self._extract_article_date(result)

        return result

    def _is_education_relevant(self, result: CrawlResult) -> bool:
        """Check if page content relates to education."""
        searchable = (result.title or "") + " " + (result.text or "")[:2000]
        return bool(EDUCATION_KEYWORDS.search(searchable))

    def _extract_article_date(self, result: CrawlResult):
        """Try to extract publication date from article pages."""
        if result.published_at:
            return

        soup = BeautifulSoup(result.raw_content, "html.parser")

        time_tag = soup.find("time")
        if time_tag:
            result.published_at = time_tag.get("datetime", time_tag.get_text(strip=True))
            return

        date_pattern = re.compile(r"\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|"
                                   r"juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})\b",
                                   re.IGNORECASE)
        text = result.text or ""
        match = date_pattern.search(text[:1000])
        if match:
            months = {
                "janvier": "01", "février": "02", "mars": "03", "avril": "04",
                "mai": "05", "juin": "06", "juillet": "07", "août": "08",
                "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12",
            }
            day = match.group(1).zfill(2)
            month = months.get(match.group(2).lower(), "01")
            year = match.group(3)
            result.published_at = f"{year}-{month}-{day}"

    def extract_key_figures(self, result: CrawlResult) -> list[dict]:
        """Extract key education figures from homepage or statistics pages."""
        figures = []
        soup = BeautifulSoup(result.raw_content, "html.parser")

        number_pattern = re.compile(r"([\d\s.,]+)\s*(%|élèves?|enseignants?|écoles?|établissements?|candidats?|centres?)", re.IGNORECASE)
        for text_block in soup.find_all(["p", "span", "div", "li", "h2", "h3", "td"]):
            text = text_block.get_text(strip=True)
            for m in number_pattern.finditer(text):
                value_str = m.group(1).replace(" ", "").replace(",", ".")
                try:
                    value = float(value_str)
                    figures.append({
                        "value": value,
                        "unit": m.group(2).strip(),
                        "context": text[:200],
                        "url": result.url,
                    })
                except ValueError:
                    continue

        return figures
