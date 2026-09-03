"""PostgreSQL loader for TogoQA — inserts parsed documents, chunks, observations.

Handles text chunking with overlap, document versioning (supersedes),
and extraction of numeric observations from structured data.
"""

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 500
DEFAULT_OVERLAP = 50
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ChunkInfo:
    text: str
    page: int | None = None
    section: str | None = None
    token_estimate: int = 0


def chunk_text(
    text: str,
    max_tokens: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    page_num: int | None = None,
    section: str | None = None,
) -> list[ChunkInfo]:
    """Split text into chunks of ~max_tokens words with overlap.

    Splits on sentence boundaries when possible to preserve coherence.
    """
    if not text or not text.strip():
        return []

    sentences = SENTENCE_END_RE.split(text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current_words = []
    current_count = 0

    for sentence in sentences:
        words = sentence.split()
        word_count = len(words)

        if current_count + word_count > max_tokens and current_words:
            chunk_text_str = " ".join(current_words)
            chunks.append(ChunkInfo(
                text=chunk_text_str,
                page=page_num,
                section=section,
                token_estimate=current_count,
            ))

            overlap_words = current_words[-overlap:] if overlap > 0 else []
            current_words = overlap_words + words
            current_count = len(current_words)
        else:
            current_words.extend(words)
            current_count += word_count

    if current_words:
        chunk_text_str = " ".join(current_words)
        chunks.append(ChunkInfo(
            text=chunk_text_str,
            page=page_num,
            section=section,
            token_estimate=current_count,
        ))

    return chunks


def chunk_pages(
    pages: list[dict],
    max_tokens: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[ChunkInfo]:
    """Chunk a list of pages (each with 'text' and 'page_num' keys)."""
    all_chunks = []
    for page in pages:
        page_chunks = chunk_text(
            page.get("text", ""),
            max_tokens=max_tokens,
            overlap=overlap,
            page_num=page.get("page_num"),
            section=page.get("section"),
        )
        all_chunks.extend(page_chunks)
    return all_chunks


def insert_document(
    session: Session,
    source_id: int,
    title: str,
    url: str | None = None,
    published_at: str | None = None,
    reference_period: str | None = None,
    school_year: str | None = None,
    data_status: str | None = None,
    geographic_scope: str = "national",
    education_level: str | None = None,
    document_type: str | None = None,
    checksum: str | None = None,
    raw_storage_path: str | None = None,
    parser_quality: float | None = None,
    metadata_confidence: float | None = None,
) -> int:
    """Insert or update a document record. Returns the document ID."""
    if checksum:
        existing = session.execute(
            sql_text("SELECT id, version FROM documents WHERE checksum = :checksum"),
            {"checksum": checksum},
        ).fetchone()
        if existing:
            logger.info("Document with same checksum exists (id=%d), skipping", existing[0])
            return existing[0]

    result = session.execute(
        sql_text("""
            INSERT INTO documents
                (source_id, title, url, published_at, reference_period, school_year,
                 data_status, geographic_scope, education_level, document_type,
                 checksum, raw_storage_path, parser_quality, metadata_confidence, status)
            VALUES
                (:source_id, :title, :url, :published_at, :reference_period, :school_year,
                 :data_status, :geographic_scope, :education_level, :document_type,
                 :checksum, :raw_storage_path, :parser_quality, :metadata_confidence, 'parsed')
            RETURNING id
        """),
        {
            "source_id": source_id,
            "title": title,
            "url": url,
            "published_at": published_at,
            "reference_period": reference_period,
            "school_year": school_year,
            "data_status": data_status,
            "geographic_scope": geographic_scope,
            "education_level": education_level,
            "document_type": document_type,
            "checksum": checksum,
            "raw_storage_path": raw_storage_path,
            "parser_quality": parser_quality,
            "metadata_confidence": metadata_confidence,
        },
    )
    doc_id = result.scalar_one()
    logger.info("Inserted document id=%d: %s", doc_id, title)
    return doc_id


def insert_chunks(session: Session, document_id: int, chunks: list[ChunkInfo]) -> int:
    """Insert text chunks for a document. Returns number of chunks inserted."""
    if not chunks:
        return 0

    for chunk in chunks:
        session.execute(
            sql_text("""
                INSERT INTO chunks (document_id, page, section, text, tokens_count)
                VALUES (:document_id, :page, :section, :text, :tokens_count)
            """),
            {
                "document_id": document_id,
                "page": chunk.page,
                "section": chunk.section,
                "text": chunk.text,
                "tokens_count": chunk.token_estimate,
            },
        )

    logger.info("Inserted %d chunks for document %d", len(chunks), document_id)
    return len(chunks)


def insert_observation(
    session: Session,
    indicator_code: str,
    value: float,
    year: int | None = None,
    school_year: str | None = None,
    sex: str | None = None,
    region: str | None = None,
    prefecture: str | None = None,
    education_level: str | None = None,
    source_id: int | None = None,
    document_id: int | None = None,
) -> int | None:
    """Insert a numeric observation. Returns observation ID or None if indicator not found."""
    row = session.execute(
        sql_text("SELECT id FROM indicators WHERE code = :code"),
        {"code": indicator_code},
    ).fetchone()
    if not row:
        logger.warning("Indicator code '%s' not found, skipping observation", indicator_code)
        return None

    indicator_id = row[0]

    result = session.execute(
        sql_text("""
            INSERT INTO observations
                (indicator_id, value, year, school_year, sex, region, prefecture,
                 education_level, source_id, document_id)
            VALUES
                (:indicator_id, :value, :year, :school_year, :sex, :region, :prefecture,
                 :education_level, :source_id, :document_id)
            RETURNING id
        """),
        {
            "indicator_id": indicator_id,
            "value": value,
            "year": year,
            "school_year": school_year,
            "sex": sex,
            "region": region,
            "prefecture": prefecture,
            "education_level": education_level,
            "source_id": source_id,
            "document_id": document_id,
        },
    )
    return result.scalar_one()


def supersede_document(session: Session, new_doc_id: int, old_doc_id: int):
    """Mark a document as superseding an older version."""
    session.execute(
        sql_text("UPDATE documents SET supersedes_document_id = :old_id WHERE id = :new_id"),
        {"old_id": old_doc_id, "new_id": new_doc_id},
    )
    session.execute(
        sql_text("UPDATE documents SET status = 'needs_review' WHERE id = :old_id"),
        {"old_id": old_doc_id},
    )
    logger.info("Document %d supersedes document %d", new_doc_id, old_doc_id)
