"""PDF parser for TogoQA — extracts text and structure from PDF documents.

Primary: PyMuPDF (fitz) for fast text extraction with page boundaries.
Fallback: pdfplumber for complex layouts (multi-column, mixed text/table).
Detects scanned PDFs (low text ratio) and marks them NEEDS_REVIEW.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SCANNED_TEXT_THRESHOLD = 50


@dataclass
class PDFPage:
    page_num: int
    text: str
    char_count: int = 0
    has_images: bool = False


@dataclass
class PDFParseResult:
    title: str
    pages: list[PDFPage]
    text: str
    page_count: int
    metadata: dict
    is_scanned: bool = False
    quality_score: float = 1.0


def parse_pdf(raw: bytes, filename: str = "", url: str = "") -> PDFParseResult:
    """Parse a PDF document. Tries PyMuPDF first, falls back to pdfplumber."""
    result = _parse_with_pymupdf(raw, filename, url)

    if result.is_scanned or (result.text and len(result.text.strip()) < SCANNED_TEXT_THRESHOLD * result.page_count):
        logger.debug("PyMuPDF extracted little text from %s, trying pdfplumber", filename)
        plumber_result = _parse_with_pdfplumber(raw, filename, url)
        if plumber_result and len(plumber_result.text) > len(result.text):
            return plumber_result

    return result


def _parse_with_pymupdf(raw: bytes, filename: str, url: str) -> PDFParseResult:
    try:
        import fitz
    except ImportError:
        logger.error("PyMuPDF not installed: pip install pymupdf")
        return PDFParseResult(title=filename, pages=[], text="", page_count=0, metadata={})

    doc = fitz.open(stream=raw, filetype="pdf")

    metadata = {}
    pdf_meta = doc.metadata or {}
    metadata["title"] = pdf_meta.get("title", "") or ""
    metadata["author"] = pdf_meta.get("author", "") or ""
    metadata["subject"] = pdf_meta.get("subject", "") or ""
    metadata["creation_date"] = pdf_meta.get("creationDate", "") or ""
    metadata["producer"] = pdf_meta.get("producer", "") or ""
    metadata["url"] = url
    metadata["filename"] = filename

    title = metadata["title"] or _title_from_filename(filename)

    pages = []
    all_text_parts = []
    total_chars = 0
    total_images = 0

    for i, page in enumerate(doc):
        text = page.get_text("text")
        text = _clean_pdf_text(text)

        images = page.get_images(full=True)
        has_images = len(images) > 0
        if has_images:
            total_images += len(images)

        pdf_page = PDFPage(
            page_num=i + 1,
            text=text,
            char_count=len(text),
            has_images=has_images,
        )
        pages.append(pdf_page)
        total_chars += len(text)

        if text.strip():
            all_text_parts.append(f"--- Page {i + 1} ---\n{text}")

    doc.close()

    full_text = "\n\n".join(all_text_parts)
    is_scanned = total_chars < SCANNED_TEXT_THRESHOLD * len(pages) and total_images > 0

    quality = _compute_pdf_quality(pages)
    if is_scanned:
        quality = min(quality, 0.3)

    return PDFParseResult(
        title=title,
        pages=pages,
        text=full_text,
        page_count=len(pages),
        metadata=metadata,
        is_scanned=is_scanned,
        quality_score=quality,
    )


def _parse_with_pdfplumber(raw: bytes, filename: str, url: str) -> PDFParseResult | None:
    try:
        import io
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed: pip install pdfplumber")
        return None

    try:
        pdf = pdfplumber.open(io.BytesIO(raw))
    except Exception as e:
        logger.warning("pdfplumber failed to open %s: %s", filename, e)
        return None

    metadata = {
        "url": url,
        "filename": filename,
        "title": pdf.metadata.get("Title", "") if pdf.metadata else "",
        "author": pdf.metadata.get("Author", "") if pdf.metadata else "",
    }

    title = metadata.get("title", "") or _title_from_filename(filename)

    pages = []
    all_text_parts = []

    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        text = _clean_pdf_text(text)

        pdf_page = PDFPage(
            page_num=i + 1,
            text=text,
            char_count=len(text),
            has_images=bool(page.images),
        )
        pages.append(pdf_page)

        if text.strip():
            all_text_parts.append(f"--- Page {i + 1} ---\n{text}")

    pdf.close()

    full_text = "\n\n".join(all_text_parts)
    is_scanned = all(p.char_count < SCANNED_TEXT_THRESHOLD for p in pages) and any(p.has_images for p in pages)

    quality = _compute_pdf_quality(pages)
    if is_scanned:
        quality = min(quality, 0.3)

    return PDFParseResult(
        title=title,
        pages=pages,
        text=full_text,
        page_count=len(pages),
        metadata=metadata,
        is_scanned=is_scanned,
        quality_score=quality,
    )


MULTI_NEWLINE = re.compile(r"\n{3,}")
MULTI_SPACE = re.compile(r" {3,}")
HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")


def _clean_pdf_text(text: str) -> str:
    text = HYPHEN_BREAK.sub(r"\1\2", text)
    text = MULTI_NEWLINE.sub("\n\n", text)
    text = MULTI_SPACE.sub(" ", text)
    return text.strip()


def _title_from_filename(filename: str) -> str:
    import os
    name = os.path.splitext(filename)[0]
    return name.replace("_", " ").replace("-", " ").strip()


def _compute_pdf_quality(pages: list[PDFPage]) -> float:
    if not pages:
        return 0.0
    total_chars = sum(p.char_count for p in pages)
    if total_chars == 0:
        return 0.0
    all_text = " ".join(p.text for p in pages)
    useful = sum(1 for c in all_text if c.isalnum() or c.isspace())
    return useful / len(all_text) if all_text else 0.0
