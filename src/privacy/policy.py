"""Privacy policy engine for TogoQA.

Evaluates education privacy rules (EDU-001 to EDU-012), small-cell
suppression, and pipeline-level enforcement decisions.
"""

import json
import os
import re
from dataclasses import dataclass, field

from src.privacy.detector import PIIDetector, PIIMatch

RULES_PATH = os.path.join(
    os.path.dirname(__file__), "../../data/manifests/pii_rules.json"
)

MIN_GROUP_SIZE = 10


@dataclass
class PolicyDecision:
    action: str
    rule_id: str | None = None
    reason: str = ""


@dataclass
class PrivacyPolicy:
    detector: PIIDetector = field(default_factory=PIIDetector)
    education_rules: list[dict] = field(default_factory=list)
    global_policy: dict = field(default_factory=dict)

    def __post_init__(self):
        self._load_rules()

    def _load_rules(self):
        if os.path.exists(RULES_PATH):
            with open(RULES_PATH, encoding="utf-8") as f:
                data = json.load(f)
            self.education_rules = data.get("education_privacy_rules", [])
            self.global_policy = data.get("global_policy", {})

    def evaluate_question(self, question: str) -> PolicyDecision:
        """Check if a user question should be allowed, redirected, or blocked."""
        q_lower = question.lower()

        pii_matches = self.detector.detect_text(question)
        pii_types = {m.pii_type for m in pii_matches}

        if "exam_candidate_number" in pii_types or "student_id" in pii_types:
            if re.search(r"\b(?:notes?|résultats?|results?|scores?|admis|ajourné)\b", q_lower):
                return PolicyDecision("block", "EDU-005", "Tentative de consultation de résultat individuel")

        if "person_full_name" in pii_types:
            if re.search(r"\b(?:résultat|note|score|bac|bepc|cepd|examen)\b", q_lower):
                return PolicyDecision("refuse_or_redirect_to_authorized_service", "EDU-001",
                                      "Question sur un élève/candidat identifiable")

        if re.search(
            r"\b(?:liste|noms?|numéros?|téléphone|adresse|contact)\b.*\b(?:enseignants?|élèves?|étudiants?|professeurs?)\b",
            q_lower,
        ):
            return PolicyDecision("refuse_or_redirect_to_authorized_service", "EDU-001",
                                  "Demande d'informations personnelles")

        if re.search(r"\b(?:ministre|directeur|secrétaire\s+général)\b", q_lower) and re.search(
            r"\b(?:selon|source|officiel|publié)\b", q_lower
        ):
            return PolicyDecision("allow_if_public_and_relevant", "EDU-006",
                                  "Information de responsable public")

        return PolicyDecision("allow")

    def evaluate_aggregation(self, data: dict) -> PolicyDecision:
        """Check if an aggregation respects small-cell suppression (EDU-003)."""
        min_k = self.global_policy.get("min_group_size_for_public_aggregate", MIN_GROUP_SIZE)

        for key, value in data.items():
            if key in ("region", "prefecture", "school", "expected_rule", "expected_action", "reason"):
                continue
            if isinstance(value, (int, float)) and value < min_k and value > 0:
                return PolicyDecision("suppress_or_coarsen", "EDU-003",
                                      f"Cellule {key}={value} < seuil {min_k}")

        return PolicyDecision("allow")

    def evaluate_ingestion(self, columns: list[str]) -> PolicyDecision:
        """Check if dataset columns contain PII that requires quarantine."""
        flagged = self.detector.detect_columns(columns)
        if flagged:
            return PolicyDecision("quarantine_and_review_before_indexing", "EDU-007",
                                  f"Colonnes PII détectées : {', '.join(flagged)}")
        return PolicyDecision("allow")

    def evaluate_llm_prompt(self, prompt: str) -> PolicyDecision:
        """Check if a prompt to an external LLM contains unredacted PII."""
        matches = self.detector.detect_text(prompt)
        critical_or_high = [m for m in matches if m.risk in ("CRITICAL", "HIGH")]
        if critical_or_high:
            pii_types = {m.pii_type for m in critical_or_high}
            if any(t in pii_types for t in ("password_secret_token", "passport_number",
                                             "biometric_data", "signature",
                                             "bank_account_or_payment_identifier")):
                return PolicyDecision("block", None, "PII CRITICAL dans le prompt LLM")
            if any(t in pii_types for t in ("student_id", "exam_candidate_number",
                                             "student_grades", "individual_exam_result")):
                return PolicyDecision("block", None, "Identifiant/résultat individuel dans le prompt LLM")
            return PolicyDecision("block", None, f"PII HIGH/CRITICAL non redacté : {pii_types}")
        return PolicyDecision("allow")

    def evaluate_output(self, output: str) -> PolicyDecision:
        """Check generated output for PII leaks before returning to user."""
        matches = self.detector.detect_text(output)

        critical_or_high = [m for m in matches if m.risk in ("CRITICAL", "HIGH")]
        if critical_or_high:
            return PolicyDecision("block_and_regenerate", None,
                                  "PII détecté dans la réponse générée")

        small_cell = re.search(r"\b([1-9])\s+(?:filles?|garçons?|élèves?|enfants?)\b", output)
        if small_cell:
            return PolicyDecision("suppress_or_coarsen", "EDU-003",
                                  "Petit effectif mentionné dans la réponse")

        return PolicyDecision("allow")

    def evaluate_log(self, log_text: str) -> str:
        """Redact PII from log entries before storage."""
        return self.detector.redact(log_text)

    def evaluate_reidentification(self, data: dict) -> PolicyDecision:
        """Check if cross-tabulated data could re-identify individuals (EDU-011)."""
        count = data.get("count", float("inf"))
        min_k = self.global_policy.get("min_group_size_for_public_aggregate", MIN_GROUP_SIZE)

        dimensions = sum(1 for k in data if k not in ("count", "expected_rule", "expected_action"))
        if count < min_k and dimensions >= 2:
            return PolicyDecision("suppress_or_coarsen", "EDU-011",
                                  f"Risque de ré-identification : count={count}, dimensions={dimensions}")

        return PolicyDecision("allow")

    def is_minor_context(self, text: str) -> bool:
        """Check if text mentions an identifiable minor (age < 18), not an aggregate."""
        if re.search(r"\b(?:statistique|national|n\s*=\s*\d{3,}|agrégé|cohorte)\b", text, re.IGNORECASE):
            return False
        age_match = re.search(r"\b(\d{1,2})\s*ans\b", text)
        if age_match and int(age_match.group(1)) < 18:
            return True
        return bool(re.search(r"\bélève\b.*\bnom\b|\bmineur\b", text, re.IGNORECASE))
