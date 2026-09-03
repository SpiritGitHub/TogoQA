"""Crawler des resultats d'examens 2026 (CEPD, BEPC, BAC I, BAC II).

Extrait les statistiques d'examens depuis les pages du MEN :
nombre de candidats, taux de reussite, centres d'examen.
Les resultats sont structures pour insertion dans exam_sessions.
"""

import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from src.ingestion.crawlers.base import BaseCrawler, CrawlResult

logger = logging.getLogger(__name__)

EXAM_TYPES = ("CEPD", "BEPC", "BAC_I", "BAC_II")

EXAM_PATTERN = re.compile(
    r"\b(CEPD|BEPC|BAC\s*(?:II?|[12]))\b",
    re.IGNORECASE,
)

NUMBER_PATTERN = re.compile(r"([\d\s]+(?:[.,]\d+)?)")


@dataclass
class ExamStats:
    exam: str
    year: int
    candidates_total: int | None = None
    girls: int | None = None
    boys: int | None = None
    success_rate: float | None = None
    success_rate_girls: float | None = None
    success_rate_boys: float | None = None
    centers: int | None = None
    region: str | None = None
    source_url: str = ""


@dataclass
class ExamCrawler(BaseCrawler):
    """Crawler specialized for exam result pages on education.gouv.tg."""

    name: str = "exams"
    allowed_domains: list[str] = field(
        default_factory=lambda: ["education.gouv.tg", "www.education.gouv.tg"]
    )
    start_urls: list[str] = field(
        default_factory=lambda: [
            "https://education.gouv.tg/examens/",
            "https://education.gouv.tg/resultats/",
            "https://education.gouv.tg/actualites/",
        ]
    )
    delay: float = 2.0
    max_pages: int = 100
    target_year: int = 2026

    def filter_result(self, result: CrawlResult) -> CrawlResult | None:
        if result.content_type != "text/html":
            return result

        text = (result.title or "") + " " + (result.text or "")[:3000]
        if not EXAM_PATTERN.search(text):
            return None
        if str(self.target_year) not in text and str(self.target_year - 1) not in text:
            return None

        result.metadata["source_id"] = "MEPS"
        result.metadata["crawler"] = "exams"
        return result

    def extract_exam_stats(self, result: CrawlResult) -> list[ExamStats]:
        """Extract exam statistics from an HTML page."""
        stats = []
        soup = BeautifulSoup(result.raw_content, "html.parser")
        text = soup.get_text(separator="\n")

        for exam_match in EXAM_PATTERN.finditer(text):
            raw_exam = exam_match.group(1).upper().strip()
            exam = self._normalize_exam_name(raw_exam)

            context_start = max(0, exam_match.start() - 50)
            context_end = min(len(text), exam_match.end() + 500)
            context = text[context_start:context_end]

            stat = ExamStats(exam=exam, year=self.target_year, source_url=result.url)

            candidates = re.search(
                r"(\d[\d\s]*)\s*candidats?",
                context, re.IGNORECASE,
            )
            if candidates:
                stat.candidates_total = self._parse_int(candidates.group(1))

            rate = re.search(
                r"taux\s+(?:de\s+)?r[eé]ussite\s*[:\s]*(\d+[.,]?\d*)\s*%",
                context, re.IGNORECASE,
            )
            if rate:
                stat.success_rate = self._parse_float(rate.group(1))

            girls_rate = re.search(
                r"filles?\s*[:\s]*(\d+[.,]?\d*)\s*%",
                context, re.IGNORECASE,
            )
            if girls_rate:
                stat.success_rate_girls = self._parse_float(girls_rate.group(1))

            boys_rate = re.search(
                r"gar[çc]ons?\s*[:\s]*(\d+[.,]?\d*)\s*%",
                context, re.IGNORECASE,
            )
            if boys_rate:
                stat.success_rate_boys = self._parse_float(boys_rate.group(1))

            centers = re.search(
                r"(\d[\d\s]*)\s*centres?",
                context, re.IGNORECASE,
            )
            if centers:
                stat.centers = self._parse_int(centers.group(1))

            if stat.candidates_total or stat.success_rate:
                stats.append(stat)

        return self._deduplicate(stats)

    @staticmethod
    def _normalize_exam_name(raw: str) -> str:
        raw = raw.replace(" ", "").replace("BACI", "BAC_I").replace("BACII", "BAC_II")
        if raw == "BAC1":
            return "BAC_I"
        if raw in ("BAC2", "BACII"):
            return "BAC_II"
        if raw in ("BACI",):
            return "BAC_I"
        return raw

    @staticmethod
    def _parse_int(s: str) -> int | None:
        try:
            return int(s.replace(" ", "").replace(" ", ""))
        except ValueError:
            return None

    @staticmethod
    def _parse_float(s: str) -> float | None:
        try:
            return float(s.replace(",", ".").replace(" ", ""))
        except ValueError:
            return None

    @staticmethod
    def _deduplicate(stats: list[ExamStats]) -> list[ExamStats]:
        seen = set()
        unique = []
        for s in stats:
            key = (s.exam, s.year, s.region)
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique
