"""Celery tasks for TogoQA scheduled crawling.

- crawl_men: daily crawl of education.gouv.tg
- crawl_inseed: weekly crawl of inseed.tg
- crawl_exams: daily crawl of exam result pages
"""

import asyncio
import logging
from datetime import datetime, timezone

from src.ingestion.celery_app import app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(bind=True, name="src.ingestion.tasks.crawl_men", max_retries=2)
def crawl_men(self):
    """Daily crawl of education.gouv.tg for new content."""
    from src.ingestion.crawlers.men import MENCrawler

    logger.info("Starting MEN crawl at %s", datetime.now(timezone.utc).isoformat())
    try:
        crawler = MENCrawler()
        results = _run_async(crawler.run())
        logger.info("MEN crawl complete: %d results", len(results))
        return {
            "status": "success",
            "results_count": len(results),
            "urls": [r.url for r in results[:20]],
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error("MEN crawl failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@app.task(bind=True, name="src.ingestion.tasks.crawl_inseed", max_retries=2)
def crawl_inseed(self):
    """Weekly crawl of inseed.tg for statistical publications."""
    from src.ingestion.crawlers.inseed import INSEEDCrawler

    logger.info("Starting INSEED crawl at %s", datetime.now(timezone.utc).isoformat())
    try:
        crawler = INSEEDCrawler()
        results = _run_async(crawler.run())
        pdfs = [r for r in results if r.content_type == "application/pdf"]
        logger.info("INSEED crawl complete: %d results (%d PDFs)", len(results), len(pdfs))
        return {
            "status": "success",
            "results_count": len(results),
            "pdfs_count": len(pdfs),
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error("INSEED crawl failed: %s", exc)
        raise self.retry(exc=exc, countdown=600)


@app.task(bind=True, name="src.ingestion.tasks.crawl_exams", max_retries=2)
def crawl_exams(self):
    """Daily crawl for exam results (CEPD, BEPC, BAC I, BAC II)."""
    from src.ingestion.crawlers.exams import ExamCrawler

    logger.info("Starting exam crawl at %s", datetime.now(timezone.utc).isoformat())
    try:
        crawler = ExamCrawler()
        results = _run_async(crawler.run())
        all_stats = []
        for r in results:
            if r.content_type == "text/html":
                stats = crawler.extract_exam_stats(r)
                all_stats.extend(stats)

        logger.info("Exam crawl complete: %d pages, %d exam stats extracted", len(results), len(all_stats))
        return {
            "status": "success",
            "pages_count": len(results),
            "stats_count": len(all_stats),
            "exams_found": list({s.exam for s in all_stats}),
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error("Exam crawl failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)
