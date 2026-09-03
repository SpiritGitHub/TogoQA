"""Metadata extraction for TogoQA documents.

Extracts and normalizes the mandatory metadata fields:
publication_date, reference_period, school_year, data_status,
geographic_scope, education_level, document_type.
"""

import logging
import re
from dataclasses import dataclass, field

import dateparser

logger = logging.getLogger(__name__)

SCHOOL_YEAR_RE = re.compile(r"(20[12]\d)\s*[-/]\s*(20[12]\d)")
YEAR_RE = re.compile(r"\b(20[12]\d)\b")

EDUCATION_LEVELS = {
    "préscolaire": "preschool", "prescolaire": "preschool", "maternelle": "preschool",
    "primaire": "primary", "cp": "primary", "ce": "primary", "cm": "primary",
    "collège": "secondary1", "college": "secondary1", "secondaire 1": "secondary1",
    "premier cycle": "secondary1", "bepc": "secondary1",
    "lycée": "secondary2", "lycee": "secondary2", "secondaire 2": "secondary2",
    "second cycle": "secondary2", "bac": "secondary2", "terminale": "secondary2",
    "technique": "technical", "professionnel": "technical", "formation professionnelle": "technical",
    "supérieur": "superior", "superieur": "superior", "université": "superior",
    "universitaire": "superior", "licence": "superior", "master": "superior",
    "alphabétisation": "non_formal", "alphabetisation": "non_formal",
    "non formel": "non_formal", "non-formel": "non_formal",
}

DOCUMENT_TYPES = {
    "annuaire": "annuaire", "statistique": "annuaire",
    "tableau de bord": "tableau_de_bord", "tableau_de_bord": "tableau_de_bord",
    "dashboard": "tableau_de_bord",
    "article": "article", "actualité": "article",
    "communiqué": "communique", "communique": "communique", "communiqué de presse": "communique",
    "rapport": "rapport", "étude": "rapport", "revue sectorielle": "rapport",
    "arrêté": "arrete", "arrete": "arrete", "arrêté ministériel": "arrete",
    "loi": "loi",
    "décret": "decret", "decret": "decret",
}

DATA_STATUSES = {
    "observé": "observed", "observe": "observed", "définitif": "observed",
    "provisoire": "provisional", "préliminaire": "provisional",
    "estimé": "estimated", "estime": "estimated", "estimation": "estimated",
    "objectif": "target", "cible": "target",
    "révisé": "revised", "revise": "revised", "corrigé": "revised",
}

GEOGRAPHIC_SCOPES = {
    "national": "national",
    "régional": "regional", "regional": "regional", "région": "regional",
    "préfectoral": "prefectoral", "prefectoral": "prefectoral", "préfecture": "prefectoral",
    "établissement": "school", "etablissement": "school", "école": "school",
}


@dataclass
class DocumentMetadata:
    title: str = ""
    publication_date: str | None = None
    reference_period: str | None = None
    school_year: str | None = None
    data_status: str | None = None
    geographic_scope: str = "national"
    education_level: str | None = None
    document_type: str | None = None
    author: str | None = None
    source_name: str | None = None
    confidence: float = 0.5


def extract_metadata(text: str, raw_meta: dict | None = None) -> DocumentMetadata:
    """Extract and normalize document metadata from text and existing raw metadata."""
    raw_meta = raw_meta or {}
    meta = DocumentMetadata()

    meta.title = raw_meta.get("title", "")

    meta.publication_date = _extract_date(text, raw_meta)
    meta.school_year = _extract_school_year(text, raw_meta)
    meta.reference_period = meta.school_year or _extract_reference_period(text)
    meta.education_level = _extract_education_level(text)
    meta.document_type = _extract_document_type(text, raw_meta)
    meta.data_status = _extract_data_status(text)
    meta.geographic_scope = _extract_geographic_scope(text)
    meta.author = raw_meta.get("author")
    meta.source_name = raw_meta.get("source_name")

    meta.confidence = _compute_confidence(meta)

    return meta


def _extract_date(text: str, raw_meta: dict) -> str | None:
    for key in ("date", "published_at", "publication_date"):
        val = raw_meta.get(key, "")
        if val:
            parsed = dateparser.parse(str(val), languages=["fr", "en"])
            if parsed:
                return parsed.strftime("%Y-%m-%d")

    french_date = re.search(
        r"\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|"
        r"août|septembre|octobre|novembre|décembre)\s+(\d{4})\b",
        text[:3000], re.IGNORECASE,
    )
    if french_date:
        parsed = dateparser.parse(french_date.group(), languages=["fr"])
        if parsed:
            return parsed.strftime("%Y-%m-%d")

    return None


def _extract_school_year(text: str, raw_meta: dict) -> str | None:
    val = raw_meta.get("school_year", "")
    if val:
        m = SCHOOL_YEAR_RE.search(str(val))
        if m:
            return f"{m.group(1)}-{m.group(2)}"

    m = SCHOOL_YEAR_RE.search(text[:5000])
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        if y2 == y1 + 1:
            return f"{y1}-{y2}"

    return None


def _extract_reference_period(text: str) -> str | None:
    m = YEAR_RE.search(text[:3000])
    if m:
        return m.group(1)
    return None


def _extract_education_level(text: str) -> str | None:
    text_lower = text[:5000].lower()
    for keyword, level in EDUCATION_LEVELS.items():
        if keyword in text_lower:
            return level
    return None


def _extract_document_type(text: str, raw_meta: dict) -> str | None:
    val = raw_meta.get("document_type", "")
    if val and val in {v for v in DOCUMENT_TYPES.values()}:
        return val

    text_lower = (text[:3000] + " " + raw_meta.get("title", "")).lower()
    for keyword, doc_type in DOCUMENT_TYPES.items():
        if keyword in text_lower:
            return doc_type
    return None


def _extract_data_status(text: str) -> str | None:
    text_lower = text[:3000].lower()
    for keyword, status in DATA_STATUSES.items():
        if keyword in text_lower:
            return status
    return None


def _extract_geographic_scope(text: str) -> str:
    text_lower = text[:5000].lower()
    if re.search(r"\bpar\s+(?:école|établissement)\b", text_lower):
        return "school"
    if re.search(r"\bpar\s+préfecture\b", text_lower):
        return "prefectoral"
    if re.search(r"\bpar\s+région\b", text_lower):
        return "regional"
    return "national"


def _compute_confidence(meta: DocumentMetadata) -> float:
    score = 0.0
    if meta.publication_date:
        score += 0.2
    if meta.school_year:
        score += 0.25
    elif meta.reference_period:
        score += 0.15
    if meta.education_level:
        score += 0.15
    if meta.document_type:
        score += 0.15
    if meta.data_status:
        score += 0.1
    if meta.title:
        score += 0.1
    if meta.author:
        score += 0.05
    return min(score, 1.0)
