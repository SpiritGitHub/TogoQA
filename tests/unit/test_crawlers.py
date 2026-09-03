"""Tests unitaires pour les crawlers MEN et INSEED.

Tests synchrones avec mocks httpx — pas de réseau requis.
"""

import hashlib
from unittest.mock import AsyncMock, patch

import pytest

from src.ingestion.crawlers.base import BaseCrawler, CrawlResult
from src.ingestion.crawlers.men import MENCrawler
from src.ingestion.crawlers.inseed import INSEEDCrawler


# ── CrawlResult ─────────────────────────────────────────────────


class TestCrawlResult:
    def test_checksum_computed(self):
        content = b"<html>test</html>"
        result = CrawlResult(url="https://example.tg/", title="Test", content_type="text/html", raw_content=content)
        assert result.checksum == hashlib.sha256(content).hexdigest()

    def test_crawled_at_set(self):
        result = CrawlResult(url="https://example.tg/", title="Test", content_type="text/html", raw_content=b"")
        assert result.crawled_at != ""


# ── BaseCrawler ─────────────────────────────────────────────────


class TestBaseCrawler:
    def test_allowed_domain(self):
        crawler = BaseCrawler(allowed_domains=["education.gouv.tg"])
        assert crawler.is_allowed_domain("https://education.gouv.tg/page")
        assert crawler.is_allowed_domain("https://www.education.gouv.tg/page")
        assert not crawler.is_allowed_domain("https://example.com/page")

    def test_is_downloadable(self):
        crawler = BaseCrawler()
        assert crawler.is_downloadable("https://example.tg/doc.pdf")
        assert crawler.is_downloadable("https://example.tg/data.xlsx")
        assert not crawler.is_downloadable("https://example.tg/page.html")

    def test_extract_links(self):
        from bs4 import BeautifulSoup

        html = '<a href="/page1">P1</a><a href="https://education.gouv.tg/p2">P2</a><a href="https://other.com">X</a>'
        soup = BeautifulSoup(html, "html.parser")
        crawler = BaseCrawler(allowed_domains=["education.gouv.tg"])
        links = crawler.extract_links(soup, "https://education.gouv.tg/")
        assert "https://education.gouv.tg/page1" in links
        assert "https://education.gouv.tg/p2" in links
        assert "https://other.com" not in links

    def test_extract_metadata(self):
        from bs4 import BeautifulSoup

        html = """<html><head>
            <title>Page Test</title>
            <meta name="description" content="Une description">
            <meta name="author" content="MEN">
        </head><body></body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        crawler = BaseCrawler()
        meta = crawler.extract_metadata(soup, "https://example.tg/test")
        assert meta["title"] == "Page Test"
        assert meta["description"] == "Une description"
        assert meta["author"] == "MEN"

    def test_extract_links_ignores_anchors(self):
        from bs4 import BeautifulSoup

        html = '<a href="#section">Anchor</a><a href="javascript:void(0)">JS</a><a href="mailto:a@b.c">Mail</a>'
        soup = BeautifulSoup(html, "html.parser")
        crawler = BaseCrawler(allowed_domains=["example.tg"])
        links = crawler.extract_links(soup, "https://example.tg/")
        assert len(links) == 0


# ── MENCrawler ──────────────────────────────────────────────────


class TestMENCrawler:
    def test_defaults(self):
        crawler = MENCrawler()
        assert crawler.name == "men"
        assert "education.gouv.tg" in crawler.allowed_domains
        assert crawler.delay == 2.0

    def test_filter_relevant(self):
        crawler = MENCrawler()
        result = CrawlResult(
            url="https://education.gouv.tg/actualites/resultats-bac-2026",
            title="Resultats du BAC 2026",
            content_type="text/html",
            raw_content=b"<html><body>Les resultats du BAC 2026 sont disponibles.</body></html>",
            text="Les resultats du BAC 2026 sont disponibles.",
        )
        filtered = crawler.filter_result(result)
        assert filtered is not None
        assert filtered.metadata["source_id"] == "MEPS"

    def test_filter_irrelevant(self):
        crawler = MENCrawler()
        result = CrawlResult(
            url="https://education.gouv.tg/contact",
            title="Contact",
            content_type="text/html",
            raw_content=b"<html><body>Nous contacter par email.</body></html>",
            text="Nous contacter par email.",
        )
        filtered = crawler.filter_result(result)
        assert filtered is None

    def test_filter_keeps_pdf(self):
        crawler = MENCrawler()
        result = CrawlResult(
            url="https://education.gouv.tg/docs/rapport.pdf",
            title="rapport.pdf",
            content_type="application/pdf",
            raw_content=b"%PDF-1.4...",
        )
        filtered = crawler.filter_result(result)
        assert filtered is not None

    def test_extract_french_date(self):
        crawler = MENCrawler()
        text = "Publie le 15 septembre 2026 - Resultats des examens"
        html = text.encode("utf-8")
        result = CrawlResult(
            url="https://education.gouv.tg/article",
            title="Resultats examens",
            content_type="text/html",
            raw_content=html,
            text=text,
        )
        crawler._extract_article_date(result)
        assert result.published_at == "2026-09-15"

    def test_extract_key_figures(self):
        crawler = MENCrawler()
        html = "<html><body><p>1 204 eleves inscrits</p><p>72,4 % de reussite</p></body></html>".encode("utf-8")
        result = CrawlResult(
            url="https://education.gouv.tg/stats",
            title="Stats",
            content_type="text/html",
            raw_content=html,
        )
        figures = crawler.extract_key_figures(result)
        assert len(figures) >= 1
        values = [f["value"] for f in figures]
        assert 1204.0 in values or 72.4 in values


# ── INSEEDCrawler ──────────────────────────────────────────────


class TestINSEEDCrawler:
    def test_defaults(self):
        crawler = INSEEDCrawler()
        assert crawler.name == "inseed"
        assert "inseed.tg" in crawler.allowed_domains
        assert crawler.delay == 2.5

    def test_filter_education_html(self):
        crawler = INSEEDCrawler()
        result = CrawlResult(
            url="https://inseed.tg/statistiques-sociales/education",
            title="Statistiques de l'education",
            content_type="text/html",
            raw_content=b"<html><body>Taux de scolarisation au Togo</body></html>",
            text="Taux de scolarisation au Togo",
        )
        filtered = crawler.filter_result(result)
        assert filtered is not None
        assert filtered.metadata["source_id"] == "INSEED"

    def test_filter_irrelevant_html(self):
        crawler = INSEEDCrawler()
        result = CrawlResult(
            url="https://inseed.tg/contact",
            title="Contactez-nous",
            content_type="text/html",
            raw_content=b"<html><body>Bureau central de Lome</body></html>",
            text="Bureau central de Lome",
        )
        filtered = crawler.filter_result(result)
        assert filtered is None

    def test_filter_keeps_pdf(self):
        crawler = INSEEDCrawler()
        result = CrawlResult(
            url="https://inseed.tg/docs/annuaire_2024-2025.pdf",
            title="annuaire_2024-2025.pdf",
            content_type="application/pdf",
            raw_content=b"%PDF-1.4...",
            metadata={"url": "https://inseed.tg/docs/annuaire_2024-2025.pdf", "filename": "annuaire_2024-2025.pdf"},
        )
        filtered = crawler.filter_result(result)
        assert filtered is not None
        assert filtered.metadata["document_type"] == "annuaire"
        assert filtered.metadata["school_year"] == "2024-2025"

    def test_pdf_metadata_year(self):
        crawler = INSEEDCrawler()
        result = CrawlResult(
            url="https://inseed.tg/rapport_2026.pdf",
            title="rapport_2026.pdf",
            content_type="application/pdf",
            raw_content=b"%PDF",
            metadata={"filename": "rapport_2026.pdf"},
        )
        crawler._extract_pdf_metadata(result)
        assert result.metadata["reference_year"] == "2026"
        assert result.metadata["document_type"] == "rapport"

    def test_list_pdf_links(self):
        crawler = INSEEDCrawler()
        html = b'<html><body><a href="/docs/annuaire.pdf">Annuaire</a><a href="/page">Page</a></body></html>'
        result = CrawlResult(
            url="https://inseed.tg/publications/",
            title="Publications",
            content_type="text/html",
            raw_content=html,
        )
        pdfs = crawler.list_pdf_links(result)
        assert len(pdfs) == 1
        assert pdfs[0].endswith(".pdf")
