"""Base crawler for TogoQA — shared logic for all source crawlers.

Features: async httpx client, robots.txt respect, rate limiting,
domain allowlist, metadata extraction, SHA-256 checksums.
"""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = "TogoQA-Bot/0.1 (+https://github.com/SpiritGitHub/TogoQA)"
DEFAULT_DELAY = 2.0
DEFAULT_TIMEOUT = 30.0


@dataclass
class CrawlResult:
    url: str
    title: str
    content_type: str
    raw_content: bytes
    text: str | None = None
    checksum: str = ""
    published_at: str | None = None
    metadata: dict = field(default_factory=dict)
    crawled_at: str = ""
    status_code: int = 0

    def __post_init__(self):
        if not self.checksum and self.raw_content:
            self.checksum = hashlib.sha256(self.raw_content).hexdigest()
        if not self.crawled_at:
            self.crawled_at = datetime.now(timezone.utc).isoformat()


@dataclass
class BaseCrawler:
    """Base class for all TogoQA crawlers."""

    name: str = "base"
    allowed_domains: list[str] = field(default_factory=list)
    start_urls: list[str] = field(default_factory=list)
    delay: float = DEFAULT_DELAY
    max_pages: int = 200
    follow_links: bool = True
    download_extensions: tuple = (".pdf", ".xlsx", ".xls", ".csv", ".docx")

    _client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)
    _robots: dict[str, RobotFileParser] = field(default_factory=dict, init=False, repr=False)
    _visited: set[str] = field(default_factory=set, init=False, repr=False)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
                follow_redirects=True,
                verify=False,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_allowed_domain(self, url: str) -> bool:
        parsed = urlparse(url)
        return any(parsed.netloc == d or parsed.netloc.endswith("." + d) for d in self.allowed_domains)

    async def check_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain not in self._robots:
            rp = RobotFileParser()
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            try:
                client = await self._get_client()
                resp = await client.get(robots_url)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp.allow_all = True
            except Exception:
                rp.allow_all = True
            self._robots[domain] = rp
        return self._robots[domain].can_fetch(USER_AGENT, url)

    async def fetch(self, url: str) -> httpx.Response | None:
        if not self.is_allowed_domain(url):
            logger.debug("Skipping off-domain URL: %s", url)
            return None

        if not await self.check_robots(url):
            logger.info("Blocked by robots.txt: %s", url)
            return None

        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            await asyncio.sleep(self.delay)
            return resp
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP %d for %s", e.response.status_code, url)
        except httpx.RequestError as e:
            logger.warning("Request error for %s: %s", url, e)
        return None

    def extract_metadata(self, soup: BeautifulSoup, url: str) -> dict:
        meta = {"url": url}

        title_tag = soup.find("title")
        if title_tag:
            meta["title"] = title_tag.get_text(strip=True)

        for tag in soup.find_all("meta"):
            name = tag.get("name", "").lower()
            prop = tag.get("property", "").lower()
            content = tag.get("content", "")
            if name == "description" or prop == "og:description":
                meta["description"] = content
            elif name == "author":
                meta["author"] = content
            elif name in ("date", "dc.date", "article:published_time") or prop == "article:published_time":
                meta["published_at"] = content
            elif name == "keywords":
                meta["keywords"] = content

        return meta

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            absolute = urljoin(base_url, href)
            absolute = absolute.split("#")[0]
            if self.is_allowed_domain(absolute):
                links.append(absolute)
        return links

    def is_downloadable(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in self.download_extensions)

    async def crawl_page(self, url: str) -> CrawlResult | None:
        resp = await self.fetch(url)
        if resp is None:
            return None

        content_type = resp.headers.get("content-type", "")
        raw = resp.content

        if "text/html" in content_type:
            soup = BeautifulSoup(raw, "html.parser")
            meta = self.extract_metadata(soup, url)
            text = soup.get_text(separator="\n", strip=True)
            return CrawlResult(
                url=url,
                title=meta.get("title", ""),
                content_type="text/html",
                raw_content=raw,
                text=text,
                published_at=meta.get("published_at"),
                metadata=meta,
                status_code=resp.status_code,
            )

        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            filename = urlparse(url).path.split("/")[-1]
            return CrawlResult(
                url=url,
                title=filename,
                content_type="application/pdf",
                raw_content=raw,
                metadata={"url": url, "filename": filename},
                status_code=resp.status_code,
            )

        filename = urlparse(url).path.split("/")[-1]
        return CrawlResult(
            url=url,
            title=filename,
            content_type=content_type.split(";")[0].strip(),
            raw_content=raw,
            metadata={"url": url, "filename": filename},
            status_code=resp.status_code,
        )

    async def run(self) -> list[CrawlResult]:
        """Crawl all start_urls and follow links up to max_pages."""
        results = []
        queue = list(self.start_urls)

        while queue and len(self._visited) < self.max_pages:
            url = queue.pop(0)
            if url in self._visited:
                continue
            self._visited.add(url)

            logger.info("[%s] Crawling: %s", self.name, url)
            result = await self.crawl_page(url)
            if result is None:
                continue

            result = self.filter_result(result)
            if result:
                results.append(result)

            if self.follow_links and result and result.content_type == "text/html":
                soup = BeautifulSoup(result.raw_content, "html.parser")
                for link in self.extract_links(soup, url):
                    if link not in self._visited:
                        if self.is_downloadable(link):
                            queue.insert(0, link)
                        else:
                            queue.append(link)

        await self.close()
        logger.info("[%s] Done — %d pages crawled, %d results", self.name, len(self._visited), len(results))
        return results

    def filter_result(self, result: CrawlResult) -> CrawlResult | None:
        """Override in subclasses to filter or enrich results."""
        return result
