"""Layer-1 regex-based PII detector for TogoQA.

Detects direct identifiers, quasi-identifiers, and education-specific
PII in French/English text and structured data (column names, values).
"""

import json
import os
import re
from dataclasses import dataclass, field

RULES_PATH = os.path.join(
    os.path.dirname(__file__), "../../data/manifests/pii_rules.json"
)

# ── Regex patterns ──────────────────────────────────────────────

PHONE_TG = re.compile(
    r"(?:\+228\s?)?(?:9[0-9]|7[0-9]|2[0-9])\s?\d{2}\s?\d{2}\s?\d{2}\b"
)
EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}")
STUDENT_ID = re.compile(r"\bETU-\d{4}-\d{4,6}\b", re.IGNORECASE)
CANDIDATE_NUM = re.compile(
    r"\b(?:BAC[12I]?|BEPC|CEPD)-[A-Z]{2,}-\d{4,8}\b", re.IGNORECASE
)
PASSPORT = re.compile(r"\b[A-Z]?\d{7,9}\b")
DATE_OF_BIRTH = re.compile(
    r"\b(?:né(?:e)?\s+le\s+)(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})\b",
    re.IGNORECASE,
)
GEOLOC = re.compile(
    r"(?<!\d)[-+]?(?:[1-9]\d?|0)\.\d{3,},\s*[-+]?(?:[1-9]\d?|0)\.\d{3,}(?!\d)"
)
SECRET_PATTERN = re.compile(
    r"(?:mot\s+de\s+passe|password|api[_\s]?key|secret|token)(?:\s+\w+)?\s*[:=]\s*\S+",
    re.IGNORECASE,
)
SCORE_INDIVIDUAL = re.compile(
    r"\b\d{1,2}\s*/\s*20\b"
)

COLUMN_PII_KEYWORDS = {
    "name", "nom", "prenom", "prénom", "full_name", "nom_complet",
    "candidate_number", "numero_candidat", "numéro_candidat",
    "student_id", "matricule", "phone", "telephone", "téléphone",
    "email", "e_mail", "courriel", "date_of_birth", "date_naissance",
    "address", "adresse", "score", "note", "moyenne", "grade",
    "result", "resultat", "résultat", "disability", "handicap",
    "password", "secret", "token", "passport", "passeport",
    "parent_name", "nom_parent", "guardian", "tuteur",
}


@dataclass
class PIIMatch:
    pii_type: str
    risk: str
    span: str
    start: int
    end: int


@dataclass
class PIIDetector:
    rules: dict = field(default_factory=dict)
    risk_map: dict = field(default_factory=dict)
    redaction_tokens: dict = field(default_factory=dict)

    def __post_init__(self):
        self._load_rules()

    def _load_rules(self):
        if os.path.exists(RULES_PATH):
            with open(RULES_PATH, encoding="utf-8") as f:
                data = json.load(f)
            for rule in data.get("pii_rules", []):
                self.rules[rule["code"]] = rule
                self.risk_map[rule["code"]] = rule["risk"]
            self.redaction_tokens = data.get("redaction_tokens", {})

    def detect_text(self, text: str) -> list[PIIMatch]:
        """Scan free text for PII patterns. Returns list of matches."""
        matches = []

        for m in PHONE_TG.finditer(text):
            matches.append(PIIMatch("phone_number", "HIGH", m.group(), m.start(), m.end()))

        for m in EMAIL.finditer(text):
            matches.append(PIIMatch("email_address", "HIGH", m.group(), m.start(), m.end()))

        for m in STUDENT_ID.finditer(text):
            matches.append(PIIMatch("student_id", "HIGH", m.group(), m.start(), m.end()))

        for m in CANDIDATE_NUM.finditer(text):
            matches.append(PIIMatch("exam_candidate_number", "HIGH", m.group(), m.start(), m.end()))

        for m in DATE_OF_BIRTH.finditer(text):
            matches.append(PIIMatch("date_of_birth", "MEDIUM", m.group(), m.start(), m.end()))

        for m in GEOLOC.finditer(text):
            matches.append(PIIMatch("precise_geolocation", "HIGH", m.group(), m.start(), m.end()))

        for m in SECRET_PATTERN.finditer(text):
            matches.append(PIIMatch("password_secret_token", "CRITICAL", m.group(), m.start(), m.end()))

        if re.search(r"\b(?:empreinte|biométr|fingerprint|iris)\b", text, re.IGNORECASE):
            matches.append(PIIMatch("biometric_data", "CRITICAL", "", 0, 0))

        if re.search(r"\b(?:santé|maladie|chronique|diagnostic|medical)\b", text, re.IGNORECASE):
            matches.append(PIIMatch("health_information", "CRITICAL", "", 0, 0))

        if re.search(r"\b(?:handicap|besoins?\s+(?:spécia|éducatif)|disability|special\s+needs)\b", text, re.IGNORECASE):
            matches.append(PIIMatch("disability_or_special_needs", "CRITICAL", "", 0, 0))

        if re.search(r"\b(?:sanction|exclusion|disciplin)\b", text, re.IGNORECASE):
            matches.append(PIIMatch("disciplinary_record", "HIGH", "", 0, 0))

        if re.search(r"\b(?:présent|absent|retard)\b", text, re.IGNORECASE) and re.search(r"\bjours?\b", text, re.IGNORECASE):
            matches.append(PIIMatch("attendance_record", "HIGH", "", 0, 0))

        if re.search(r"(?:passeport|passport)\s*[:=]?\s*[A-Z]?\d{5,}", text, re.IGNORECASE):
            matches.append(PIIMatch("passport_number", "CRITICAL", "", 0, 0))

        if re.search(r"\b(?:parent|tuteur|guardian)\s*:", text, re.IGNORECASE):
            matches.append(PIIMatch("parent_guardian_identity", "HIGH", "", 0, 0))

        name_ctx = re.compile(
            r"\b(?:candidat|élève|étudiant|enseignant)\s+([A-ZÀÂÉÈÊËÏÎÔÙÛÜÇ]{2,}\s+[A-ZÀÂÉÈÊËÏÎÔÙÛÜÇa-zàâéèêëïîôùûüç]+(?:\s+[A-ZÀÂÉÈÊËÏÎÔÙÛÜÇa-zàâéèêëïîôùûüç]+)?)\b"
        )
        for m in name_ctx.finditer(text):
            matches.append(PIIMatch("person_full_name", "HIGH", m.group(1), m.start(1), m.end(1)))

        name_bare = re.compile(
            r"\b([A-ZÀÂÉÈÊËÏÎÔÙÛÜÇ]{2,})\s+([A-ZÀÂÉÈÊËÏÎÔÙÛÜÇ][a-zàâéèêëïîôùûüç]{2,}(?:\s+[A-ZÀÂÉÈÊËÏÎÔÙÛÜÇ][a-zàâéèêëïîôùûüç]+)?)\b"
        )
        for m in name_bare.finditer(text):
            matches.append(PIIMatch("person_full_name", "HIGH", m.group(0), m.start(), m.end()))

        if SCORE_INDIVIDUAL.search(text) and re.search(
            r"\b(?:candidat|élève|étudiant|a\s+obtenu|note)\b", text, re.IGNORECASE
        ):
            matches.append(PIIMatch("student_grades", "HIGH", "", 0, 0))

        return matches

    def detect_columns(self, columns: list[str]) -> list[str]:
        """Check column names for PII-indicating keywords. Returns list of PII column names."""
        flagged = []
        for col in columns:
            normalized = col.lower().replace("-", "_").replace(" ", "_")
            for kw in COLUMN_PII_KEYWORDS:
                if kw in normalized:
                    flagged.append(col)
                    break
        return flagged

    def redact(self, text: str) -> str:
        """Replace detected PII with redaction tokens."""
        matches = self.detect_text(text)
        matches.sort(key=lambda m: m.start, reverse=True)
        result = text
        for m in matches:
            if m.span and m.start < m.end:
                token = self.redaction_tokens.get(m.pii_type, f"[{m.pii_type.upper()}]")
                result = result[:m.start] + token + result[m.end:]
        return result

    def get_risk(self, pii_type: str) -> str:
        return self.risk_map.get(pii_type, "MEDIUM")

    def get_action(self, pii_type: str) -> str:
        rule = self.rules.get(pii_type)
        if rule:
            return rule.get("default_action", "quarantine_and_review")
        return "quarantine_and_review"
