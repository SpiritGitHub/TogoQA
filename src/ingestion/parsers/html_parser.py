"""HTML parser for TogoQA — extracts structured content from web pages.

Primary: trafilatura for main content extraction (readability algorithm).
Fallback: BeautifulSoup for poorly structured pages.
Preserves document structure: headings, paragraphs, lists.
"""

import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString

logger = logging.getLogger(__name__)


@dataclass
class HTMLSection:
    heading: str
    level: int
    content: str
    lists: list[list[str]] = field(default_factory=list)


@dataclass
class HTMLParseResult:
    title: str
    text: str
    sections: list[HTMLSection]
    metadata: dict
    tables_html: list[str] = field(default_factory=list)
    quality_score: float = 1.0


def parse_html(raw: bytes, url: str = "", encoding: str = "utf-8") -> HTMLParseResult:
    """Parse HTML and extract structured content.

    Uses trafilatura for main content, falls back to BeautifulSoup.
    """
    html_str = raw.decode(encoding, errors="replace")

    text, metadata = _extract_trafilatura(html_str, url)
    if text and len(text) > 100:
        sections = _build_sections_from_text(text)
        tables = _extract_tables_html(html_str)
        title = metadata.get("title", "")
        return HTMLParseResult(
            title=title,
            text=text,
            sections=sections,
            metadata=metadata,
            tables_html=tables,
        )

    logger.debug("Trafilatura insufficient for %s, falling back to BeautifulSoup", url)
    return _parse_with_bs4(html_str, url)


def _extract_trafilatura(html: str, url: str) -> tuple[str | None, dict]:
    try:
        import trafilatura

        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            output_format="txt",
            favor_recall=True,
        )
        metadata = {}
        meta_obj = trafilatura.extract_metadata(html, default_url=url)
        if meta_obj:
            metadata["title"] = meta_obj.title or ""
            metadata["author"] = meta_obj.author or ""
            metadata["date"] = meta_obj.date or ""
            metadata["description"] = meta_obj.description or ""
            metadata["sitename"] = meta_obj.sitename or ""
        return result, metadata
    except Exception as e:
        logger.warning("Trafilatura failed: %s", e)
        return None, {}


def _parse_with_bs4(html: str, url: str) -> HTMLParseResult:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    metadata = _extract_meta_tags(soup, url)
    if title:
        metadata["title"] = title

    main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|article|post"))
    container = main or soup.body or soup

    sections = _extract_sections(container)
    tables = _extract_tables_html(html)

    full_text = container.get_text(separator="\n", strip=True)
    full_text = _clean_text(full_text)

    quality = _compute_quality(full_text)

    return HTMLParseResult(
        title=title,
        text=full_text,
        sections=sections,
        metadata=metadata,
        tables_html=tables,
        quality_score=quality,
    )


def _extract_meta_tags(soup: BeautifulSoup, url: str) -> dict:
    meta = {"url": url}
    for tag in soup.find_all("meta"):
        name = tag.get("name", "").lower()
        prop = tag.get("property", "").lower()
        content = tag.get("content", "")
        if not content:
            continue
        if name == "description" or prop == "og:description":
            meta["description"] = content
        elif name == "author":
            meta["author"] = content
        elif name in ("date", "dc.date") or prop == "article:published_time":
            meta["date"] = content
        elif name == "keywords":
            meta["keywords"] = content
    return meta


def _extract_sections(container) -> list[HTMLSection]:
    sections = []
    current_heading = ""
    current_level = 0
    current_parts = []
    current_lists = []

    for element in container.descendants:
        if isinstance(element, NavigableString):
            continue

        if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if current_heading or current_parts:
                sections.append(HTMLSection(
                    heading=current_heading,
                    level=current_level,
                    content="\n".join(current_parts).strip(),
                    lists=current_lists,
                ))
            current_heading = element.get_text(strip=True)
            current_level = int(element.name[1])
            current_parts = []
            current_lists = []

        elif element.name == "p":
            text = element.get_text(strip=True)
            if text:
                current_parts.append(text)

        elif element.name in ("ul", "ol"):
            items = [li.get_text(strip=True) for li in element.find_all("li", recursive=False)]
            if items:
                current_lists.append(items)
                current_parts.append("\n".join(f"- {item}" for item in items))

    if current_heading or current_parts:
        sections.append(HTMLSection(
            heading=current_heading,
            level=current_level,
            content="\n".join(current_parts).strip(),
            lists=current_lists,
        ))

    return sections


def _extract_tables_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    tables = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) >= 2:
            tables.append(str(table))
    return tables


def _build_sections_from_text(text: str) -> list[HTMLSection]:
    lines = text.split("\n")
    sections = []
    current_heading = ""
    current_parts = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) < 80 and stripped == stripped.upper() and len(stripped) > 3:
            if current_heading or current_parts:
                sections.append(HTMLSection(
                    heading=current_heading, level=2,
                    content="\n".join(current_parts).strip(),
                ))
            current_heading = stripped
            current_parts = []
        else:
            current_parts.append(stripped)

    if current_heading or current_parts:
        sections.append(HTMLSection(
            heading=current_heading, level=2,
            content="\n".join(current_parts).strip(),
        ))

    return sections


WHITESPACE_RE = re.compile(r"\n{3,}")
SPACE_RE = re.compile(r"[ \t]{2,}")


def _clean_text(text: str) -> str:
    text = WHITESPACE_RE.sub("\n\n", text)
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def _compute_quality(text: str) -> float:
    if not text:
        return 0.0
    useful = sum(1 for c in text if c.isalnum() or c.isspace())
    return useful / len(text) if len(text) > 0 else 0.0
