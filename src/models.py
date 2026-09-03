from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


# ──────────────────────────────────────────────
# 1. SOURCES
# ──────────────────────────────────────────────
class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    authority_tier: Mapped[str] = mapped_column(
        String(2),
        CheckConstraint("authority_tier IN ('A+','A','B+','B','C','D')"),
        nullable=False,
    )
    authority_score: Mapped[float] = mapped_column(Numeric(3, 2), default=0.75)
    category: Mapped[str | None] = mapped_column(Text)
    source_owner: Mapped[str | None] = mapped_column(Text)
    thematic_scope: Mapped[str | None] = mapped_column(Text)
    update_frequency: Mapped[str | None] = mapped_column(Text)
    corroboration_required: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    documents: Mapped[list["Document"]] = relationship(back_populates="source")

    __table_args__ = (Index("idx_sources_tier", "authority_tier"),)


# ──────────────────────────────────────────────
# 2. DOCUMENTS
# ──────────────────────────────────────────────
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[date | None] = mapped_column(Date)
    reference_period: Mapped[str | None] = mapped_column(Text)
    school_year: Mapped[str | None] = mapped_column(String(9))
    data_status: Mapped[str | None] = mapped_column(
        String(20),
        CheckConstraint("data_status IN ('observed','provisional','estimated','target','revised')"),
    )
    geographic_scope: Mapped[str | None] = mapped_column(Text, default="national")
    education_level: Mapped[str | None] = mapped_column(
        String(20),
        CheckConstraint(
            "education_level IN ('preschool','primary','secondary1','secondary2','technical','superior','non_formal')"
        ),
    )
    document_type: Mapped[str | None] = mapped_column(
        String(30),
        CheckConstraint(
            "document_type IN ('annuaire','tableau_de_bord','article','communique','rapport','arrete','loi','decret')"
        ),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("status IN ('ingested','parsed','trusted','needs_review','rejected')"),
        default="ingested",
    )
    checksum: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    parser_quality: Mapped[float | None] = mapped_column(Numeric(3, 2))
    metadata_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    raw_storage_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    source: Mapped["Source"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_documents_source", "source_id"),
        Index("idx_documents_status", "status"),
        Index("idx_documents_school_year", "school_year"),
        Index("idx_documents_checksum", "checksum"),
    )


# ──────────────────────────────────────────────
# 3. CHUNKS
# ──────────────────────────────────────────────
class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1024), nullable=True)
    tokens_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (Index("idx_chunks_document", "document_id"),)


# ──────────────────────────────────────────────
# 4. INDICATORS
# ──────────────────────────────────────────────
class Indicator(Base):
    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    aliases = mapped_column(ARRAY(Text), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40))
    meta = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    observations: Mapped[list["Observation"]] = relationship(back_populates="indicator")

    __table_args__ = (Index("idx_indicators_category", "category"),)


# ──────────────────────────────────────────────
# 5. OBSERVATIONS
# ──────────────────────────────────────────────
class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id"), nullable=False)
    value: Mapped[float] = mapped_column(Numeric, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    school_year: Mapped[str | None] = mapped_column(String(9))
    sex: Mapped[str | None] = mapped_column(
        String(10), CheckConstraint("sex IN ('total','male','female')")
    )
    region: Mapped[str | None] = mapped_column(Text)
    prefecture: Mapped[str | None] = mapped_column(Text)
    education_level: Mapped[str | None] = mapped_column(String(20))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    indicator: Mapped["Indicator"] = relationship(back_populates="observations")

    __table_args__ = (
        Index("idx_observations_indicator", "indicator_id"),
        Index("idx_observations_year", "year"),
        Index("idx_observations_school_year", "school_year"),
        Index("idx_observations_region", "region"),
        Index("idx_observations_level", "education_level"),
        Index("idx_observations_composite", "indicator_id", "school_year", "region", "sex"),
    )


# ──────────────────────────────────────────────
# 6. SCHOOLS
# ──────────────────────────────────────────────
class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    school_type: Mapped[str | None] = mapped_column(
        String(20), CheckConstraint("school_type IN ('public','private','community','confessional')")
    )
    level: Mapped[str | None] = mapped_column(
        String(20),
        CheckConstraint("level IN ('preschool','primary','secondary1','secondary2','technical','superior')"),
    )
    region: Mapped[str | None] = mapped_column(Text)
    prefecture: Mapped[str | None] = mapped_column(Text)
    locality: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    lon: Mapped[float | None] = mapped_column(Numeric(9, 6))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_schools_region", "region"),
        Index("idx_schools_level", "level"),
        Index("idx_schools_type", "school_type"),
    )


# ──────────────────────────────────────────────
# 7. EXAM_SESSIONS
# ──────────────────────────────────────────────
class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam: Mapped[str] = mapped_column(
        String(20), CheckConstraint("exam IN ('CEPD','BEPC','BAC_I','BAC_II')"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    candidates_total: Mapped[int | None] = mapped_column(Integer)
    girls: Mapped[int | None] = mapped_column(Integer)
    boys: Mapped[int | None] = mapped_column(Integer)
    success_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    success_rate_girls: Mapped[float | None] = mapped_column(Numeric(5, 2))
    success_rate_boys: Mapped[float | None] = mapped_column(Numeric(5, 2))
    centers: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("exam", "year", "region", name="uq_exam_session"),
        Index("idx_exam_sessions_exam_year", "exam", "year"),
    )


# ──────────────────────────────────────────────
# 8. BENCHMARK_QUESTIONS
# ──────────────────────────────────────────────
class BenchmarkQuestion(Base):
    __tablename__ = "benchmark_questions"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    difficulty: Mapped[int] = mapped_column(
        Integer, CheckConstraint("difficulty BETWEEN 1 AND 6"), nullable=False
    )
    answerability: Mapped[str] = mapped_column(
        String(10), CheckConstraint("answerability IN ('FULL','PARTIAL','NONE')"), nullable=False
    )
    gold_answer: Mapped[str | None] = mapped_column(Text)
    gold_claims = mapped_column(JSONB, nullable=True)
    required_operations = mapped_column(ARRAY(Text), nullable=True)
    metadata_filters = mapped_column(JSONB, nullable=True)
    split: Mapped[str | None] = mapped_column(
        String(10), CheckConstraint("split IN ('train','test','dev')"), default="train"
    )
    annotator: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gold_evidence: Mapped[list["GoldEvidence"]] = relationship(back_populates="question", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_benchmark_category", "category"),
        Index("idx_benchmark_difficulty", "difficulty"),
        Index("idx_benchmark_split", "split"),
    )


# ──────────────────────────────────────────────
# 9. GOLD_EVIDENCE
# ──────────────────────────────────────────────
class GoldEvidence(Base):
    __tablename__ = "gold_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[str] = mapped_column(
        ForeignKey("benchmark_questions.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    span: Mapped[str | None] = mapped_column(Text)
    table_ref: Mapped[str | None] = mapped_column(Text)
    claim_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped["BenchmarkQuestion"] = relationship(back_populates="gold_evidence")

    __table_args__ = (Index("idx_gold_evidence_question", "question_id"),)


# ──────────────────────────────────────────────
# 10. QUERY_LOGS
# ──────────────────────────────────────────────
class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_intent = mapped_column(JSONB, nullable=True)
    decision: Mapped[str | None] = mapped_column(
        String(10), CheckConstraint("decision IN ('ANSWER','PARTIAL','ABSTAIN')")
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    confidence_features = mapped_column(JSONB, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text)
    sources_used = mapped_column(JSONB, nullable=True)
    retrieval_scores = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    model_version: Mapped[str | None] = mapped_column(Text)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_query_logs_decision", "decision"),
        Index("idx_query_logs_created", "created_at"),
    )
