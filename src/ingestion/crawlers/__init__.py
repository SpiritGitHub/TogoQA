"""TogoQA crawlers — one per source."""

from src.ingestion.crawlers.base import BaseCrawler, CrawlResult
from src.ingestion.crawlers.inseed import INSEEDCrawler
from src.ingestion.crawlers.men import MENCrawler

__all__ = ["BaseCrawler", "CrawlResult", "MENCrawler", "INSEEDCrawler"]
