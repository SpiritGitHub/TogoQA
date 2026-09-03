"""Tests for Semaine 3 — parsers, table extraction, metadata, normalizer, loader, quality."""

import pytest

from src.ingestion.parsers.html_parser import (
    HTMLParseResult,
    parse_html,
    _clean_text,
    _compute_quality,
    _extract_tables_html,
)
from src.ingestion.parsers.pdf_parser import (
    PDFPage,
    _clean_pdf_text,
    _compute_pdf_quality,
    _title_from_filename,
)
from src.ingestion.parsers.table_extractor import (
    ExtractedTable,
    normalize_headers,
    table_to_records,
    extract_tables_html,
)
from src.ingestion.parsers.metadata_extractor import (
    DocumentMetadata,
    extract_metadata,
    _extract_school_year,
    _extract_education_level,
    _extract_document_type,
    _extract_data_status,
    _extract_geographic_scope,
    _compute_confidence,
)
from src.ingestion.normalizer import (
    normalize_school_year,
    normalize_year,
    normalize_education_level,
    normalize_sex,
    normalize_region,
    normalize_prefecture,
    normalize_indicator_label,
    parse_numeric_value,
)
from src.ingestion.loader import chunk_text, ChunkInfo, chunk_pages
from src.ingestion.quality import (
    check_readability,
    check_table_coherence,
    check_period_known,
    check_sums_plausible,
    check_duplication,
    check_source_allowlist,
    run_quality_checks,
)


# ── HTML Parser ───────────────────────────────────────────────────


class TestHTMLParser:
    def test_parse_simple_html(self):
        html = b"""<html><head><title>Test Page</title></head>
        <body><h1>Education au Togo</h1><p>Le taux de scolarisation est de 85%.</p></body></html>"""
        result = parse_html(html, url="https://education.gouv.tg/test")
        assert isinstance(result, HTMLParseResult)
        assert result.title
        assert "scolarisation" in result.text.lower()

    def test_parse_with_sections(self):
        html = b"""<html><body>
        <h1>Titre principal</h1><p>Introduction.</p>
        <h2>Section A</h2><p>Contenu A.</p>
        <h2>Section B</h2><p>Contenu B.</p>
        </body></html>"""
        result = parse_html(html)
        assert len(result.sections) >= 2

    def test_extract_tables_html(self):
        html = """<table><tr><th>Region</th><th>Effectif</th></tr>
        <tr><td>Maritime</td><td>5000</td></tr></table>"""
        tables = _extract_tables_html(html)
        assert len(tables) >= 1

    def test_clean_text(self):
        assert _clean_text("  hello   world  ") == "hello world"
        assert "\n\n\n" not in _clean_text("a\n\n\n\nb")

    def test_quality_score(self):
        assert _compute_quality("Hello world 123") > 0.9
        assert _compute_quality("") == 0.0

    def test_parse_empty_html(self):
        result = parse_html(b"<html><body></body></html>")
        assert isinstance(result, HTMLParseResult)


# ── PDF Parser ────────────────────────────────────────────────────


class TestPDFParser:
    def test_clean_pdf_text_hyphen(self):
        assert _clean_pdf_text("scolari-\nsation") == "scolarisation"

    def test_clean_pdf_text_whitespace(self):
        result = _clean_pdf_text("hello\n\n\n\nworld")
        assert "\n\n\n" not in result

    def test_title_from_filename(self):
        assert _title_from_filename("annuaire_2023-2024.pdf") == "annuaire 2023 2024"
        assert _title_from_filename("rapport.pdf") == "rapport"

    def test_pdf_quality_empty(self):
        assert _compute_pdf_quality([]) == 0.0

    def test_pdf_quality_normal(self):
        pages = [PDFPage(page_num=1, text="Texte normal avec du contenu", char_count=30)]
        assert _compute_pdf_quality(pages) > 0.8


# ── Table Extractor ───────────────────────────────────────────────


class TestTableExtractor:
    def test_normalize_headers(self):
        headers = ["Région", "Nombre d'élèves", "Taux (%)"]
        result = normalize_headers(headers)
        assert result[0] == "région"
        assert "élèves" in result[1] or "eleves" in result[1]

    def test_table_to_records(self):
        table = ExtractedTable(
            page_num=1,
            headers=["Region", "Effectif"],
            rows=[["Maritime", "5000"], ["Plateaux", "3000"]],
        )
        records = table_to_records(table)
        assert len(records) == 2
        assert records[0]["region"] == "Maritime"

    def test_extract_tables_html_basic(self):
        html = """<html><body>
        <table><tr><th>A</th><th>B</th></tr>
        <tr><td>1</td><td>2</td></tr>
        <tr><td>3</td><td>4</td></tr></table>
        </body></html>"""
        tables = extract_tables_html(html)
        assert len(tables) >= 1
        assert len(tables[0].rows) >= 1

    def test_extract_tables_html_no_table(self):
        tables = extract_tables_html("<html><body><p>No table here</p></body></html>")
        assert tables == []


# ── Metadata Extractor ────────────────────────────────────────────


class TestMetadataExtractor:
    def test_extract_school_year(self):
        assert _extract_school_year("Annuaire 2023-2024", {}) == "2023-2024"
        assert _extract_school_year("Rapport 2025", {}) is None

    def test_extract_school_year_from_meta(self):
        assert _extract_school_year("", {"school_year": "2022/2023"}) == "2022-2023"

    def test_extract_education_level(self):
        assert _extract_education_level("Le taux au primaire est de 85%") == "primary"
        assert _extract_education_level("Enseignement supérieur") == "superior"
        assert _extract_education_level("Aucun niveau mentionne") is None

    def test_extract_document_type(self):
        assert _extract_document_type("Annuaire statistique 2024", {}) == "annuaire"
        assert _extract_document_type("Communique de presse", {}) == "communique"

    def test_extract_data_status(self):
        assert _extract_data_status("Donnees provisoires") == "provisional"
        assert _extract_data_status("Chiffres définitifs") == "observed"

    def test_extract_geographic_scope(self):
        assert _extract_geographic_scope("Résultats par région") == "regional"
        assert _extract_geographic_scope("Donnees nationales") == "national"
        assert _extract_geographic_scope("Par préfecture") == "prefectoral"

    def test_full_extraction(self):
        text = "Annuaire statistique 2023-2024 du primaire. Donnees provisoires par région."
        meta = extract_metadata(text, {"title": "Annuaire 2023-2024"})
        assert isinstance(meta, DocumentMetadata)
        assert meta.school_year == "2023-2024"
        assert meta.education_level == "primary"
        assert meta.document_type == "annuaire"
        assert meta.data_status == "provisional"
        assert meta.geographic_scope == "regional"

    def test_confidence_score(self):
        meta = DocumentMetadata(
            title="Test",
            publication_date="2024-01-01",
            school_year="2023-2024",
            education_level="primary",
            document_type="annuaire",
        )
        score = _compute_confidence(meta)
        assert score > 0.6


# ── Normalizer ────────────────────────────────────────────────────


class TestNormalizer:
    def test_school_year(self):
        assert normalize_school_year("2023-2024") == "2023-2024"
        assert normalize_school_year("2023/2024") == "2023-2024"
        assert normalize_school_year("annee 2022-2023 scolaire") == "2022-2023"
        assert normalize_school_year("rien") is None
        assert normalize_school_year("") is None

    def test_year(self):
        assert normalize_year("en 2024 les resultats") == 2024
        assert normalize_year("aucune annee") is None

    def test_education_level(self):
        assert normalize_education_level("primaire") == "primary"
        assert normalize_education_level("Collège") == "secondary1"
        assert normalize_education_level("Lycée") == "secondary2"
        assert normalize_education_level("supérieur") == "superior"
        assert normalize_education_level("technique") == "technical"
        assert normalize_education_level("inconnu") is None

    def test_sex(self):
        assert normalize_sex("Garçons") == "male"
        assert normalize_sex("Filles") == "female"
        assert normalize_sex("Total") == "total"
        assert normalize_sex("M") == "male"
        assert normalize_sex("F") == "female"
        assert normalize_sex("") is None

    def test_region(self):
        assert normalize_region("Maritime") == "Maritime"
        assert normalize_region("savanes") == "Savanes"
        assert normalize_region("Lomé Commune") == "Lomé-Commune"
        assert normalize_region("inconnu") is None

    def test_prefecture(self):
        assert normalize_prefecture("Golfe") == "Golfe"
        assert normalize_prefecture("tchaoudjo") == "Tchaoudjo"
        assert normalize_prefecture("kozah") == "Kozah"
        assert normalize_prefecture("inconnu") is None

    def test_indicator_label(self):
        assert normalize_indicator_label("Taux de réussite") == "success_rate"
        assert normalize_indicator_label("Nombre de candidats") == "candidates_total"
        assert normalize_indicator_label("TBS") == "gross_enrollment_rate"
        assert normalize_indicator_label("inconnu") is None

    def test_parse_numeric_french(self):
        assert parse_numeric_value("1 234") == 1234.0
        assert parse_numeric_value("72,4") == 72.4
        assert parse_numeric_value("85.3%") == 85.3
        assert parse_numeric_value("1,234.56") == 1234.56
        assert parse_numeric_value("abc") is None


# ── Loader (chunking) ────────────────────────────────────────────


class TestChunking:
    def test_chunk_short_text(self):
        chunks = chunk_text("Hello world. This is a test.", max_tokens=100)
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world. This is a test."

    def test_chunk_long_text(self):
        text = ". ".join([f"Sentence number {i} with some words" for i in range(200)])
        chunks = chunk_text(text, max_tokens=20, overlap=5)
        assert len(chunks) > 1
        for c in chunks:
            assert c.token_estimate <= 30

    def test_chunk_with_overlap(self):
        sentences = ". ".join([f"Sentence number {i}" for i in range(50)])
        chunks = chunk_text(sentences, max_tokens=20, overlap=5)
        assert len(chunks) > 2
        if len(chunks) >= 2:
            words_1 = set(chunks[0].text.split()[-5:])
            words_2 = set(chunks[1].text.split()[:10])
            assert len(words_1 & words_2) > 0

    def test_chunk_empty(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_chunk_preserves_page(self):
        chunks = chunk_text("Some text here.", page_num=5, section="Intro")
        assert chunks[0].page == 5
        assert chunks[0].section == "Intro"

    def test_chunk_pages(self):
        pages = [
            {"text": "Page one content here.", "page_num": 1},
            {"text": "Page two content here.", "page_num": 2},
        ]
        chunks = chunk_pages(pages, max_tokens=100)
        assert len(chunks) == 2
        assert chunks[0].page == 1
        assert chunks[1].page == 2


# ── Quality Checks ────────────────────────────────────────────────


class TestQuality:
    def test_readability_pass(self):
        text = "Le taux de scolarisation au Togo est de 85% en 2024."
        result = check_readability(text)
        assert result.passed

    def test_readability_fail_short(self):
        result = check_readability("abc")
        assert not result.passed

    def test_readability_empty(self):
        result = check_readability("")
        assert not result.passed

    def test_table_coherence_no_tables(self):
        result = check_table_coherence([])
        assert result.passed

    def test_table_coherence_ok(self):
        tables = [{"headers": ["A", "B"], "rows": [["1", "2"], ["3", "4"]]}]
        result = check_table_coherence(tables)
        assert result.passed

    def test_table_coherence_bad_rows(self):
        tables = [{"headers": ["A", "B"], "rows": [["1", "2", "extra"]]}]
        result = check_table_coherence(tables)
        assert not result.passed

    def test_period_known_school_year(self):
        result = check_period_known("", school_year="2023-2024")
        assert result.passed

    def test_period_known_in_text(self):
        result = check_period_known("Annuaire 2023-2024 du Togo")
        assert result.passed

    def test_period_unknown(self):
        result = check_period_known("Document sans date ni annee")
        assert not result.passed

    def test_sums_plausible_ok(self):
        text = "Total : 10000. Filles : 5200. Garçons : 4800."
        result = check_sums_plausible(text)
        assert result.passed

    def test_sums_plausible_fail(self):
        text = "Total : 10000. Filles : 3000. Garçons : 3000."
        result = check_sums_plausible(text)
        assert not result.passed

    def test_sums_no_data(self):
        result = check_sums_plausible("Aucune donnee genree")
        assert result.passed

    def test_duplication_unique(self):
        result = check_duplication("abc123", {"def456", "ghi789"})
        assert result.passed

    def test_duplication_found(self):
        result = check_duplication("abc123", {"abc123", "def456"})
        assert not result.passed
        assert result.action == "reject"

    def test_source_allowlist_ok(self):
        result = check_source_allowlist("https://education.gouv.tg/page")
        assert result.passed

    def test_source_allowlist_subdomain(self):
        result = check_source_allowlist("https://stats.inseed.tg/data")
        assert result.passed

    def test_source_allowlist_rejected(self):
        result = check_source_allowlist("https://malicious-site.com/fake")
        assert not result.passed
        assert result.action == "reject"

    def test_source_allowlist_no_url(self):
        result = check_source_allowlist("")
        assert result.passed

    def test_full_report_pass(self):
        report = run_quality_checks(
            text="Le taux de scolarisation au Togo en 2023-2024 est de 85%. " * 10,
            url="https://education.gouv.tg/stats",
            checksum="unique123",
            school_year="2023-2024",
        )
        assert report.overall_passed
        assert report.suggested_status == "parsed"

    def test_full_report_rejected(self):
        report = run_quality_checks(
            text="Le taux de scolarisation au Togo en 2023-2024 est de 85%. " * 10,
            url="https://malicious.com/fake",
            checksum="unique123",
        )
        assert not report.overall_passed
        assert report.suggested_status == "rejected"
