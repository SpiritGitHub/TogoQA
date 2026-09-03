"""Tests PII — 52 cas couvrant les 11 couches du manifeste pii_tests.json.

Layers: detector, false_positive, aggregation, question_policy,
        ingestion, external_llm, output_guard, logging,
        reidentification, citation, minor_policy.
"""

import pytest

from src.privacy.detector import PIIDetector
from src.privacy.policy import PrivacyPolicy


@pytest.fixture(scope="module")
def detector():
    return PIIDetector()


@pytest.fixture(scope="module")
def policy():
    return PrivacyPolicy()


# ── Detector (PII-001 to PII-015) ──────────────────────────────


class TestDetector:
    def test_pii_001_name_and_grades(self, detector):
        matches = detector.detect_text("Le candidat KOFFI Ama Mensah a obtenu 14/20.")
        types = {m.pii_type for m in matches}
        assert "person_full_name" in types
        assert "student_grades" in types

    def test_pii_002_phone(self, detector):
        matches = detector.detect_text("Contact : +228 90 12 34 56")
        types = {m.pii_type for m in matches}
        assert "phone_number" in types

    def test_pii_003_email(self, detector):
        matches = detector.detect_text("Écrire à ama.test@example.org")
        types = {m.pii_type for m in matches}
        assert "email_address" in types

    def test_pii_004_student_id(self, detector):
        matches = detector.detect_text("Matricule étudiant : ETU-2026-004812")
        types = {m.pii_type for m in matches}
        assert "student_id" in types

    def test_pii_005_candidate_number(self, detector):
        matches = detector.detect_text("Numéro de candidat : BAC2-LOME-001234")
        types = {m.pii_type for m in matches}
        assert "exam_candidate_number" in types

    def test_pii_006_dob(self, detector):
        matches = detector.detect_text("Né le 12/04/2011")
        types = {m.pii_type for m in matches}
        assert "date_of_birth" in types

    def test_pii_007_geolocation(self, detector):
        matches = detector.detect_text("Coordonnées : 6.1319, 1.2228 associées à cet élève")
        types = {m.pii_type for m in matches}
        assert "precise_geolocation" in types

    def test_pii_008_password(self, detector):
        matches = detector.detect_text("Mot de passe temporaire : DemoSecret123!")
        types = {m.pii_type for m in matches}
        assert "password_secret_token" in types

    def test_pii_009_biometric(self, detector):
        matches = detector.detect_text("Empreinte biométrique enregistrée pour l'élève.")
        types = {m.pii_type for m in matches}
        assert "biometric_data" in types

    def test_pii_010_health(self, detector):
        matches = detector.detect_text("L'élève est suivi pour une maladie chronique.")
        types = {m.pii_type for m in matches}
        assert "health_information" in types

    def test_pii_011_disability(self, detector):
        matches = detector.detect_text("L'élève présente un handicap visuel.")
        types = {m.pii_type for m in matches}
        assert "disability_or_special_needs" in types

    def test_pii_012_disciplinary(self, detector):
        matches = detector.detect_text("Sanction disciplinaire : exclusion de trois jours.")
        types = {m.pii_type for m in matches}
        assert "disciplinary_record" in types

    def test_pii_013_attendance(self, detector):
        matches = detector.detect_text("Présent 142 jours, absent 18 jours — élève ETU-001.")
        types = {m.pii_type for m in matches}
        assert "attendance_record" in types

    def test_pii_014_parent(self, detector):
        matches = detector.detect_text("Parent : KOFFI Mensah, téléphone +228 91 23 45 67.")
        types = {m.pii_type for m in matches}
        assert "parent_guardian_identity" in types
        assert "phone_number" in types

    def test_pii_015_passport(self, detector):
        matches = detector.detect_text("Passeport : P0000001")
        types = {m.pii_type for m in matches}
        assert "passport_number" in types


# ── False positives (SAFE-001 to SAFE-006) ──────────────────────


class TestFalsePositive:
    def test_safe_001_success_rate(self, detector):
        matches = detector.detect_text("Le taux de réussite au BAC II est de 72,4 %.")
        high_risk = [m for m in matches if m.risk in ("HIGH", "CRITICAL")]
        assert len(high_risk) == 0

    def test_safe_002_school_count(self, detector):
        matches = detector.detect_text("Le lycée de Tokoin compte 1 204 élèves.")
        high_risk = [m for m in matches if m.risk in ("HIGH", "CRITICAL")]
        assert len(high_risk) == 0

    def test_safe_003_candidates_variable(self, detector):
        matches = detector.detect_text("candidates_girls = 38124")
        high_risk = [m for m in matches if m.risk in ("HIGH", "CRITICAL")]
        assert len(high_risk) == 0

    def test_safe_004_budget(self, detector):
        matches = detector.detect_text("budget_education = 125000000000 FCFA")
        high_risk = [m for m in matches if m.risk in ("HIGH", "CRITICAL")]
        assert len(high_risk) == 0

    def test_safe_005_ratio(self, detector):
        matches = detector.detect_text("pupil_teacher_ratio = 42.3")
        high_risk = [m for m in matches if m.risk in ("HIGH", "CRITICAL")]
        assert len(high_risk) == 0

    def test_safe_006_establishments(self, detector):
        matches = detector.detect_text("Nombre d'établissements privés : 468")
        high_risk = [m for m in matches if m.risk in ("HIGH", "CRITICAL")]
        assert len(high_risk) == 0


# ── Aggregation / small-cell (AGG-001 to AGG-005) ──────────────


class TestAggregation:
    def test_agg_001_small_cell_girls(self, policy):
        decision = policy.evaluate_aggregation({"region": "Maritime", "girls": 4, "boys": 18})
        assert decision.rule_id == "EDU-003"
        assert "suppress" in decision.action or "coarsen" in decision.action

    def test_agg_002_large_cell(self, policy):
        decision = policy.evaluate_aggregation({"region": "Maritime", "girls": 1420, "boys": 1518})
        assert decision.action == "allow"

    def test_agg_003_single_candidate(self, policy):
        decision = policy.evaluate_aggregation({
            "school": "École Test", "successful_candidates": 1, "total_candidates": 1
        })
        assert decision.rule_id == "EDU-003"

    def test_agg_004_small_osc(self, policy):
        decision = policy.evaluate_aggregation({"prefecture": "Test", "out_of_school_children": 7})
        assert decision.rule_id == "EDU-003"

    def test_agg_005_large_gender_cell(self, policy):
        decision = policy.evaluate_aggregation({
            "region": "Centrale", "success_rate_girls": 68.2, "girls_n": 540
        })
        assert decision.action == "allow"


# ── Question policy (QUERY-001 to QUERY-007) ───────────────────


class TestQuestionPolicy:
    def test_query_001_individual_result(self, policy):
        decision = policy.evaluate_question("Quel est le résultat au BAC de KOFFI Ama Mensah ?")
        assert decision.action in ("refuse_or_redirect_to_authorized_service", "block")
        assert decision.rule_id in ("EDU-001", "EDU-005")

    def test_query_002_candidate_lookup(self, policy):
        decision = policy.evaluate_question("Voici le numéro BAC2-LOME-001234, donne-moi ses notes.")
        assert decision.action == "block"
        assert decision.rule_id == "EDU-005"

    def test_query_003_aggregate_allowed(self, policy):
        decision = policy.evaluate_question("Combien de filles ont réussi au BAC II en 2026 ?")
        assert decision.action == "allow"

    def test_query_004_regional_stat(self, policy):
        decision = policy.evaluate_question("Quel est le taux d'abandon scolaire dans la région des Savanes ?")
        assert decision.action == "allow"

    def test_query_005_personal_list(self, policy):
        decision = policy.evaluate_question(
            "Liste les noms et numéros de téléphone de tous les enseignants de cette école."
        )
        assert decision.action == "refuse_or_redirect_to_authorized_service"

    def test_query_006_public_info(self, policy):
        decision = policy.evaluate_question("Quel ministère a publié les résultats nationaux du BAC ?")
        assert decision.action == "allow"

    def test_query_007_public_official(self, policy):
        decision = policy.evaluate_question(
            "Qui est le ministre chargé de l'éducation selon la source officielle ?"
        )
        assert decision.action == "allow_if_public_and_relevant"
        assert decision.rule_id == "EDU-006"


# ── Ingestion (INGEST-001 to INGEST-005) ───────────────────────


class TestIngestion:
    def test_ingest_001_pii_columns(self, policy):
        decision = policy.evaluate_ingestion(["name", "candidate_number", "score", "school"])
        assert decision.rule_id == "EDU-007"
        assert "quarantine" in decision.action

    def test_ingest_002_safe_columns(self, policy):
        decision = policy.evaluate_ingestion(["region", "year", "candidates_total", "success_rate"])
        assert decision.action == "allow"

    def test_ingest_003_disability_column(self, policy):
        decision = policy.evaluate_ingestion(["student_id", "disability", "school"])
        assert decision.rule_id == "EDU-007"

    def test_ingest_004_teacher_aggregate(self, policy):
        decision = policy.evaluate_ingestion(["prefecture", "teachers_count", "teachers_qualified"])
        assert decision.action == "allow"

    def test_ingest_005_full_pii_columns(self, policy):
        decision = policy.evaluate_ingestion(["full_name", "phone", "email", "exam_result"])
        assert decision.rule_id == "EDU-007"


# ── External LLM (LLM-001 to LLM-005) ─────────────────────────


class TestExternalLLM:
    def test_llm_001_redacted_ok(self, policy):
        decision = policy.evaluate_llm_prompt("Prompt contient [PERSON_NAME] après redaction.")
        assert decision.action == "allow"

    def test_llm_002_passport_leak(self, policy):
        decision = policy.evaluate_llm_prompt("Prompt contient le vrai numéro de passeport P0000001.")
        assert decision.action == "block"

    def test_llm_003_aggregate_ok(self, policy):
        decision = policy.evaluate_llm_prompt("Agrégat national : success_rate=72.4%.")
        assert decision.action == "allow"

    def test_llm_004_individual_data(self, policy):
        decision = policy.evaluate_llm_prompt("Ligne individuelle avec matricule ETU-2026-004812 et note 14/20.")
        assert decision.action == "block"

    def test_llm_005_phone_redacted(self, policy):
        decision = policy.evaluate_llm_prompt("Question redigée après remplacement du téléphone par [PHONE].")
        assert decision.action == "allow"


# ── Output guard (OUTPUT-001 to OUTPUT-005) ─────────────────────


class TestOutputGuard:
    def test_output_001_phone_leak(self, policy):
        decision = policy.evaluate_output("Réponse générée : téléphone de l'élève +228 90 12 34 56.")
        assert "block" in decision.action

    def test_output_002_aggregate_ok(self, policy):
        decision = policy.evaluate_output("Réponse générée : 76,3 % des candidats ont réussi.")
        assert decision.action == "allow"

    def test_output_003_student_id_leak(self, policy):
        decision = policy.evaluate_output("Réponse générée : ETU-2026-004812 a obtenu 15/20.")
        assert "block" in decision.action

    def test_output_004_source_cite_ok(self, policy):
        decision = policy.evaluate_output("Réponse générée : selon l'INSEED, le taux brut de scolarisation...")
        assert decision.action == "allow"

    def test_output_005_small_cell_output(self, policy):
        decision = policy.evaluate_output("Réponse générée : 3 filles dans ce petit établissement ont abandonné.")
        assert decision.action in ("suppress_or_coarsen", "block_and_regenerate")


# ── Logging (LOG-001 to LOG-003) ────────────────────────────────


class TestLogging:
    def test_log_001_phone_redacted(self, policy):
        result = policy.evaluate_log("Utilisateur: mon numéro est +228 90 12 34 56")
        assert "+228 90 12 34 56" not in result
        assert "[PHONE]" in result

    def test_log_002_secret_redacted(self, policy):
        result = policy.evaluate_log("api_key=sk-example-not-real")
        assert "sk-example-not-real" not in result

    def test_log_003_safe_unchanged(self, policy):
        text = "Question: taux de réussite national 2026 ?"
        result = policy.evaluate_log(text)
        assert result == text


# ── Reidentification (REID-001 to REID-003) ────────────────────


class TestReidentification:
    def test_reid_001_small_unique(self, policy):
        decision = policy.evaluate_reidentification({
            "school": "École Test", "class": "CM2", "gender": "F", "age": 17, "count": 1
        })
        assert decision.rule_id == "EDU-011"

    def test_reid_002_large_safe(self, policy):
        decision = policy.evaluate_reidentification({
            "region": "Kara", "level": "primary", "gender": "F", "count": 14000
        })
        assert decision.action == "allow"

    def test_reid_003_rare_disability(self, policy):
        decision = policy.evaluate_reidentification({
            "village": "Test", "disability_type": "rare", "count": 2
        })
        assert decision.rule_id == "EDU-011"


# ── Minor policy (MINOR-001 to MINOR-002) ──────────────────────


class TestMinorPolicy:
    def test_minor_001_identifiable(self, policy):
        assert policy.is_minor_context("Élève de 13 ans, nom complet et moyenne trimestrielle.")

    def test_minor_002_aggregate_ok(self, policy):
        assert not policy.is_minor_context("Statistique nationale des élèves âgés de 12 à 14 ans, n=120000.")
