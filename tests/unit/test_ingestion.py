"""Tests for downloader, exam crawler, storage, and Celery tasks."""

import hashlib
import json
import os
import tempfile

import pytest

from src.ingestion.crawlers.base import CrawlResult
from src.ingestion.crawlers.exams import ExamCrawler, ExamStats
from src.ingestion.downloader import DocumentDownloader, DownloadEntry
from src.ingestion.storage import compute_checksum, get_content_type, MinIOStorage


# ── Downloader ──────────────────────────────────────────────────


class TestDownloader:
    def test_compute_checksum(self):
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert DocumentDownloader.compute_checksum(data) == expected

    def test_manifest_roundtrip(self, tmp_path):
        manifest_path = str(tmp_path / "manifest.json")
        dl = DocumentDownloader(
            download_dir=str(tmp_path),
            manifest_path=manifest_path,
        )
        dl._manifest["documents"]["test.pdf"] = {
            "checksum": "abc123",
            "version": 1,
        }
        dl._save_manifest()

        dl2 = DocumentDownloader(
            download_dir=str(tmp_path),
            manifest_path=manifest_path,
        )
        assert "test.pdf" in dl2._manifest["documents"]
        assert dl2._manifest["documents"]["test.pdf"]["checksum"] == "abc123"

    def test_is_duplicate(self, tmp_path):
        dl = DocumentDownloader(
            download_dir=str(tmp_path),
            manifest_path=str(tmp_path / "manifest.json"),
        )
        dl._manifest["documents"] = {"file.pdf": {"checksum": "abc123"}}
        assert dl.is_duplicate("abc123")
        assert not dl.is_duplicate("xyz789")

    def test_get_version_new(self, tmp_path):
        dl = DocumentDownloader(
            download_dir=str(tmp_path),
            manifest_path=str(tmp_path / "manifest.json"),
        )
        assert dl.get_version("new_file.pdf") == 1

    def test_get_version_existing(self, tmp_path):
        dl = DocumentDownloader(
            download_dir=str(tmp_path),
            manifest_path=str(tmp_path / "manifest.json"),
        )
        dl._manifest["documents"] = {"old.pdf": {"version": 2}}
        assert dl.get_version("old.pdf") == 3

    def test_download_entry_to_dict(self):
        entry = DownloadEntry(
            url="https://example.tg/doc.pdf",
            filename="doc.pdf",
            checksum="abc",
            size=1024,
            downloaded_at="2026-09-03T00:00:00Z",
            version=1,
            document_type="rapport",
            reference_period="2025",
            source_id="MEPS",
        )
        d = entry.to_dict()
        assert d["url"] == "https://example.tg/doc.pdf"
        assert d["source_id"] == "MEPS"

    def test_reference_documents_defined(self):
        from src.ingestion.downloader import REFERENCE_DOCUMENTS
        assert len(REFERENCE_DOCUMENTS) >= 2
        names = [d["name"] for d in REFERENCE_DOCUMENTS]
        assert any("RSCE" in n for n in names)
        assert any("Annuaire" in n for n in names)


# ── ExamCrawler ─────────────────────────────────────────────────


class TestExamCrawler:
    def test_defaults(self):
        crawler = ExamCrawler()
        assert crawler.name == "exams"
        assert crawler.target_year == 2026

    def test_normalize_exam_name(self):
        assert ExamCrawler._normalize_exam_name("BEPC") == "BEPC"
        assert ExamCrawler._normalize_exam_name("BAC2") == "BAC_II"
        assert ExamCrawler._normalize_exam_name("BAC1") == "BAC_I"
        assert ExamCrawler._normalize_exam_name("CEPD") == "CEPD"
        assert ExamCrawler._normalize_exam_name("BACII") == "BAC_II"

    def test_parse_int(self):
        assert ExamCrawler._parse_int("1 204") == 1204
        assert ExamCrawler._parse_int("38124") == 38124
        assert ExamCrawler._parse_int("abc") is None

    def test_parse_float(self):
        assert ExamCrawler._parse_float("72,4") == 72.4
        assert ExamCrawler._parse_float("85.3") == 85.3
        assert ExamCrawler._parse_float("bad") is None

    def test_filter_relevant(self):
        crawler = ExamCrawler()
        result = CrawlResult(
            url="https://education.gouv.tg/resultats-bepc-2026",
            title="Resultats BEPC 2026",
            content_type="text/html",
            raw_content=b"<html><body>Resultats du BEPC 2026</body></html>",
            text="Resultats du BEPC 2026",
        )
        assert crawler.filter_result(result) is not None

    def test_filter_irrelevant_no_exam(self):
        crawler = ExamCrawler()
        result = CrawlResult(
            url="https://education.gouv.tg/contact",
            title="Contact",
            content_type="text/html",
            raw_content=b"<html><body>Contactez-nous</body></html>",
            text="Contactez-nous",
        )
        assert crawler.filter_result(result) is None

    def test_filter_irrelevant_wrong_year(self):
        crawler = ExamCrawler()
        result = CrawlResult(
            url="https://education.gouv.tg/resultats-bepc-2020",
            title="Resultats BEPC 2020",
            content_type="text/html",
            raw_content=b"<html><body>BEPC 2020 results</body></html>",
            text="BEPC 2020 results",
        )
        assert crawler.filter_result(result) is None

    def test_extract_exam_stats(self):
        crawler = ExamCrawler()
        html = (
            "<html><body>"
            "<p>BEPC 2026 : 120 543 candidats inscrits.</p>"
            "<p>Taux de reussite : 68,5 %</p>"
            "<p>245 centres d'examen</p>"
            "</body></html>"
        ).encode("utf-8")
        result = CrawlResult(
            url="https://education.gouv.tg/bepc-2026",
            title="BEPC 2026",
            content_type="text/html",
            raw_content=html,
            text="BEPC 2026 : 120 543 candidats inscrits. Taux de reussite : 68,5 %. 245 centres.",
        )
        stats = crawler.extract_exam_stats(result)
        assert len(stats) >= 1
        bepc = stats[0]
        assert bepc.exam == "BEPC"
        assert bepc.year == 2026

    def test_deduplicate(self):
        stats = [
            ExamStats(exam="BEPC", year=2026, candidates_total=100),
            ExamStats(exam="BEPC", year=2026, candidates_total=100),
            ExamStats(exam="CEPD", year=2026, candidates_total=200),
        ]
        unique = ExamCrawler._deduplicate(stats)
        assert len(unique) == 2


# ── Storage ─────────────────────────────────────────────────────


class TestStorage:
    def test_compute_checksum(self):
        data = b"test data"
        assert compute_checksum(data) == hashlib.sha256(data).hexdigest()

    def test_get_content_type(self):
        assert get_content_type("doc.pdf") == "application/pdf"
        assert get_content_type("page.html") == "text/html"
        assert get_content_type("data.csv") == "text/csv"
        assert get_content_type("file.xlsx") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert get_content_type("unknown.xyz") == "application/octet-stream"

    def test_build_object_name(self):
        storage = MinIOStorage.__new__(MinIOStorage)
        storage.endpoint = "localhost:9000"
        storage.bucket = "togoqa-documents"
        assert storage.build_object_name("MEPS", "rapport.pdf", "2025") == "meps/2025/rapport.pdf"
        assert storage.build_object_name("INSEED", "annuaire.pdf") == "inseed/annuaire.pdf"


# ── Celery config ───────────────────────────────────────────────


class TestCeleryConfig:
    def test_app_configured(self):
        from src.ingestion.celery_app import app
        assert app.main == "togoqa"
        assert "crawl-men-daily" in app.conf.beat_schedule
        assert "crawl-inseed-weekly" in app.conf.beat_schedule
        assert "crawl-exams-daily" in app.conf.beat_schedule

    def test_men_schedule_daily(self):
        from src.ingestion.celery_app import app
        schedule = app.conf.beat_schedule["crawl-men-daily"]
        assert schedule["schedule"] == 86400.0
        assert schedule["task"] == "src.ingestion.tasks.crawl_men"

    def test_inseed_schedule_weekly(self):
        from src.ingestion.celery_app import app
        schedule = app.conf.beat_schedule["crawl-inseed-weekly"]
        assert schedule["schedule"] == 604800.0

    def test_tasks_importable(self):
        from src.ingestion.tasks import crawl_men, crawl_inseed, crawl_exams
        assert callable(crawl_men)
        assert callable(crawl_inseed)
        assert callable(crawl_exams)
