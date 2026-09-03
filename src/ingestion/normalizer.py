"""Normalization pipeline for TogoQA ingested data.

Standardizes: school years, education levels, sex, Togo regions/prefectures,
and indicator codes to the canonical dictionary.
"""

import re

SCHOOL_YEAR_RE = re.compile(r"(20[012]\d)\s*[-/\\]\s*(20[012]\d)")
SINGLE_YEAR_RE = re.compile(r"\b(20[012]\d)\b")

# ── Education levels ─────────────────────────────────────────────

LEVEL_MAP = {
    "préscolaire": "preschool", "prescolaire": "preschool", "maternelle": "preschool",
    "pre-primaire": "preschool", "préprimaire": "preschool",
    "primaire": "primary", "élémentaire": "primary", "elementaire": "primary",
    "cp1": "primary", "cp2": "primary", "ce1": "primary", "ce2": "primary",
    "cm1": "primary", "cm2": "primary",
    "collège": "secondary1", "college": "secondary1",
    "premier cycle du secondaire": "secondary1", "secondaire 1er cycle": "secondary1",
    "6ème": "secondary1", "5ème": "secondary1", "4ème": "secondary1", "3ème": "secondary1",
    "lycée": "secondary2", "lycee": "secondary2",
    "second cycle du secondaire": "secondary2", "secondaire 2nd cycle": "secondary2",
    "2nde": "secondary2", "1ère": "secondary2", "terminale": "secondary2",
    "technique": "technical", "professionnel": "technical",
    "formation professionnelle": "technical", "enseignement technique": "technical",
    "supérieur": "superior", "superieur": "superior",
    "université": "superior", "universite": "superior",
    "non formel": "non_formal", "non-formel": "non_formal",
    "alphabétisation": "non_formal", "alphabetisation": "non_formal",
}

# ── Sex ──────────────────────────────────────────────────────────

SEX_MAP = {
    "m": "male", "masculin": "male", "garçon": "male", "garcon": "male",
    "garçons": "male", "garcons": "male", "homme": "male", "hommes": "male",
    "boys": "male", "male": "male",
    "f": "female", "féminin": "female", "feminin": "female",
    "fille": "female", "filles": "female", "femme": "female", "femmes": "female",
    "girls": "female", "female": "female",
    "t": "total", "total": "total", "ensemble": "total", "tous": "total",
    "mixte": "total", "les deux sexes": "total", "both": "total",
}

# ── Togo regions (5 regions + Lomé commune) ──────────────────────

REGIONS_TOGO = {
    "maritime": "Maritime",
    "plateaux": "Plateaux",
    "centrale": "Centrale",
    "kara": "Kara",
    "savanes": "Savanes",
    "lomé commune": "Lomé-Commune",
    "lome commune": "Lomé-Commune",
    "lomé-commune": "Lomé-Commune",
    "lome-commune": "Lomé-Commune",
    "lomé": "Lomé-Commune",
    "lome": "Lomé-Commune",
    "grand lomé": "Lomé-Commune",
}

# ── Togo prefectures ─────────────────────────────────────────────

PREFECTURES_TOGO = {
    # Maritime
    "golfe": "Golfe", "agoè-nyivé": "Agoè-Nyivé", "agoe-nyive": "Agoè-Nyivé",
    "lacs": "Lacs", "vo": "Vo", "yoto": "Yoto", "zio": "Zio", "avé": "Avé", "ave": "Avé",
    "bas-mono": "Bas-Mono",
    # Plateaux
    "ogou": "Ogou", "est-mono": "Est-Mono", "haho": "Haho", "moyen-mono": "Moyen-Mono",
    "amou": "Amou", "danyi": "Danyi", "agou": "Agou", "kloto": "Kloto", "wawa": "Wawa",
    "akébou": "Akébou", "akebou": "Akébou",
    # Centrale
    "tchaoudjo": "Tchaoudjo", "tchamba": "Tchamba", "sotouboua": "Sotouboua",
    "blitta": "Blitta", "mô": "Mô", "mo": "Mô",
    # Kara
    "kozah": "Kozah", "binah": "Binah", "doufelgou": "Doufelgou",
    "kéran": "Kéran", "keran": "Kéran", "assoli": "Assoli", "bassar": "Bassar",
    "dankpen": "Dankpen",
    # Savanes
    "tône": "Tône", "tone": "Tône", "oti": "Oti", "oti-sud": "Oti-Sud",
    "tandjouaré": "Tandjouaré", "tandjouare": "Tandjouaré",
    "cinkassé": "Cinkassé", "cinkasse": "Cinkassé",
    "kpendjal": "Kpendjal", "kpendjal-ouest": "Kpendjal-Ouest",
}

# ── Indicator code synonyms ──────────────────────────────────────

INDICATOR_SYNONYMS = {
    "nombre de candidats": "candidates_total",
    "candidats inscrits": "candidates_total",
    "candidats": "candidates_total",
    "candidates filles": "candidates_girls",
    "candidats garçons": "candidates_boys",
    "taux de réussite": "success_rate",
    "taux de reussite": "success_rate",
    "taux d'admission": "success_rate",
    "taux brut de scolarisation": "gross_enrollment_rate",
    "tbs": "gross_enrollment_rate",
    "taux net de scolarisation": "net_enrollment_rate",
    "tns": "net_enrollment_rate",
    "taux brut d'accès": "access_rate",
    "tba": "access_rate",
    "taux d'achèvement": "completion_rate",
    "taux de transition": "transition_rate",
    "taux de redoublement": "repetition_rate",
    "taux d'abandon": "dropout_rate",
    "indice de parité": "gender_parity_index",
    "ips": "gender_parity_index",
    "ratio élèves/enseignant": "pupil_teacher_ratio",
    "ratio élèves enseignant": "pupil_teacher_ratio",
    "nombre d'établissements": "schools_count",
    "nombre d'enseignants": "teachers_count",
    "effectifs scolaires": "enrollment_total",
    "effectifs scolarisés": "enrollment_total",
    "effectif total": "enrollment_total",
    "effectifs filles": "enrollment_girls",
    "effectifs garçons": "enrollment_boys",
    "taux d'alphabétisation": "literacy_rate",
}


def normalize_school_year(value: str) -> str | None:
    """Normalize school year to 'YYYY-YYYY' format."""
    if not value:
        return None

    m = SCHOOL_YEAR_RE.search(str(value))
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        if y2 == y1 + 1:
            return f"{y1}-{y2}"
        return f"{m.group(1)}-{m.group(2)}"

    return None


def normalize_year(value: str) -> int | None:
    """Extract a civil year from text."""
    m = SINGLE_YEAR_RE.search(str(value))
    return int(m.group(1)) if m else None


def normalize_education_level(value: str) -> str | None:
    """Map French education level names to canonical codes."""
    if not value:
        return None
    key = value.lower().strip()
    return LEVEL_MAP.get(key)


def normalize_sex(value: str) -> str | None:
    """Normalize sex/gender to male/female/total."""
    if not value:
        return None
    key = value.lower().strip()
    return SEX_MAP.get(key)


def normalize_region(value: str) -> str | None:
    """Normalize Togo region name to canonical form."""
    if not value:
        return None
    key = value.lower().strip()
    return REGIONS_TOGO.get(key)


def normalize_prefecture(value: str) -> str | None:
    """Normalize Togo prefecture name to canonical form."""
    if not value:
        return None
    key = value.lower().strip()
    return PREFECTURES_TOGO.get(key)


def normalize_indicator_label(label: str) -> str | None:
    """Map a French indicator label to its canonical code."""
    if not label:
        return None
    key = label.lower().strip()
    return INDICATOR_SYNONYMS.get(key)


def parse_numeric_value(text: str) -> float | None:
    """Parse a numeric value handling French formatting (spaces, commas)."""
    text = text.strip()
    text = text.replace(" ", "").replace(" ", "")
    text = text.replace(" ", "")
    text = text.rstrip("%")

    if "," in text and "." not in text:
        text = text.replace(",", ".")
    elif "," in text and "." in text:
        text = text.replace(",", "")

    try:
        return float(text)
    except ValueError:
        return None
