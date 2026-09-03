"""Initial schema — 10 tables TogoQA

Revision ID: 001
Revises: None
Create Date: 2026-09-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 1. sources
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("authority_tier", sa.String(2), nullable=False),
        sa.Column("authority_score", sa.Numeric(3, 2), server_default="0.75"),
        sa.Column("category", sa.Text),
        sa.Column("source_owner", sa.Text),
        sa.Column("thematic_scope", sa.Text),
        sa.Column("update_frequency", sa.Text),
        sa.Column("corroboration_required", sa.Boolean, server_default="false"),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("authority_tier IN ('A+','A','B+','B','C','D')"),
    )
    op.create_index("idx_sources_tier", "sources", ["authority_tier"])

    # 2. documents
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text),
        sa.Column("published_at", sa.Date),
        sa.Column("reference_period", sa.Text),
        sa.Column("school_year", sa.String(9)),
        sa.Column("data_status", sa.String(20)),
        sa.Column("geographic_scope", sa.Text, server_default="national"),
        sa.Column("education_level", sa.String(20)),
        sa.Column("document_type", sa.String(30)),
        sa.Column("status", sa.String(20), server_default="ingested", nullable=False),
        sa.Column("checksum", sa.String(64)),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("supersedes_document_id", sa.Integer, sa.ForeignKey("documents.id")),
        sa.Column("parser_quality", sa.Numeric(3, 2)),
        sa.Column("metadata_confidence", sa.Numeric(3, 2)),
        sa.Column("raw_storage_path", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("data_status IN ('observed','provisional','estimated','target','revised')"),
        sa.CheckConstraint(
            "education_level IN ('preschool','primary','secondary1','secondary2','technical','superior','non_formal')"
        ),
        sa.CheckConstraint(
            "document_type IN ('annuaire','tableau_de_bord','article','communique','rapport','arrete','loi','decret')"
        ),
        sa.CheckConstraint("status IN ('ingested','parsed','trusted','needs_review','rejected')"),
    )
    op.create_index("idx_documents_source", "documents", ["source_id"])
    op.create_index("idx_documents_status", "documents", ["status"])
    op.create_index("idx_documents_school_year", "documents", ["school_year"])
    op.create_index("idx_documents_checksum", "documents", ["checksum"])

    # 3. chunks
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page", sa.Integer),
        sa.Column("section", sa.Text),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1024)),
        sa.Column("tokens_count", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_chunks_document", "chunks", ["document_id"])

    # FTS column — ajoutée via SQL brut car GENERATED ALWAYS AS n'est pas supporté nativement par Alembic
    op.execute("ALTER TABLE chunks ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('french', text)) STORED")
    op.execute("CREATE INDEX idx_chunks_fts ON chunks USING gin (tsv)")

    # 4. indicators
    op.create_table(
        "indicators",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("definition", sa.Text),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("aliases", sa.ARRAY(sa.Text)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 5. observations
    op.create_table(
        "observations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("indicator_id", sa.Integer, sa.ForeignKey("indicators.id"), nullable=False),
        sa.Column("value", sa.Numeric, nullable=False),
        sa.Column("year", sa.Integer),
        sa.Column("school_year", sa.String(9)),
        sa.Column("sex", sa.String(10)),
        sa.Column("region", sa.Text),
        sa.Column("prefecture", sa.Text),
        sa.Column("education_level", sa.String(20)),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id")),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("sex IN ('total','male','female')"),
    )
    op.create_index("idx_observations_indicator", "observations", ["indicator_id"])
    op.create_index("idx_observations_year", "observations", ["year"])
    op.create_index("idx_observations_school_year", "observations", ["school_year"])
    op.create_index("idx_observations_region", "observations", ["region"])
    op.create_index("idx_observations_level", "observations", ["education_level"])
    op.create_index("idx_observations_composite", "observations", ["indicator_id", "school_year", "region", "sex"])

    # 6. schools
    op.create_table(
        "schools",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("school_type", sa.String(20)),
        sa.Column("level", sa.String(20)),
        sa.Column("region", sa.Text),
        sa.Column("prefecture", sa.Text),
        sa.Column("locality", sa.Text),
        sa.Column("lat", sa.Numeric(9, 6)),
        sa.Column("lon", sa.Numeric(9, 6)),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("school_type IN ('public','private','community','confessional')"),
        sa.CheckConstraint("level IN ('preschool','primary','secondary1','secondary2','technical','superior')"),
    )
    op.create_index("idx_schools_region", "schools", ["region"])
    op.create_index("idx_schools_level", "schools", ["level"])
    op.create_index("idx_schools_type", "schools", ["school_type"])

    # 7. exam_sessions
    op.create_table(
        "exam_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("exam", sa.String(20), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("candidates_total", sa.Integer),
        sa.Column("girls", sa.Integer),
        sa.Column("boys", sa.Integer),
        sa.Column("success_rate", sa.Numeric(5, 2)),
        sa.Column("success_rate_girls", sa.Numeric(5, 2)),
        sa.Column("success_rate_boys", sa.Numeric(5, 2)),
        sa.Column("centers", sa.Integer),
        sa.Column("region", sa.Text),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id")),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("exam IN ('CEPD','BEPC','BAC_I','BAC_II')"),
        sa.UniqueConstraint("exam", "year", "region", name="uq_exam_session"),
    )
    op.create_index("idx_exam_sessions_exam_year", "exam_sessions", ["exam", "year"])

    # 8. benchmark_questions
    op.create_table(
        "benchmark_questions",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("difficulty", sa.Integer, nullable=False),
        sa.Column("answerability", sa.String(10), nullable=False),
        sa.Column("gold_answer", sa.Text),
        sa.Column("gold_claims", sa.JSON),
        sa.Column("required_operations", sa.ARRAY(sa.Text)),
        sa.Column("metadata_filters", sa.JSON),
        sa.Column("split", sa.String(10), server_default="train"),
        sa.Column("annotator", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 6"),
        sa.CheckConstraint("answerability IN ('FULL','PARTIAL','NONE')"),
        sa.CheckConstraint("split IN ('train','test','dev')"),
    )
    op.create_index("idx_benchmark_category", "benchmark_questions", ["category"])
    op.create_index("idx_benchmark_difficulty", "benchmark_questions", ["difficulty"])
    op.create_index("idx_benchmark_split", "benchmark_questions", ["split"])

    # 9. gold_evidence
    op.create_table(
        "gold_evidence",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "question_id", sa.String(20), sa.ForeignKey("benchmark_questions.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("page", sa.Integer),
        sa.Column("span", sa.Text),
        sa.Column("table_ref", sa.Text),
        sa.Column("claim_id", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_gold_evidence_question", "gold_evidence", ["question_id"])

    # 10. query_logs
    op.create_table(
        "query_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("parsed_intent", sa.JSON),
        sa.Column("decision", sa.String(10)),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("confidence_features", sa.JSON),
        sa.Column("answer", sa.Text),
        sa.Column("sources_used", sa.JSON),
        sa.Column("retrieval_scores", sa.JSON),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("model_version", sa.Text),
        sa.Column("cache_hit", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("decision IN ('ANSWER','PARTIAL','ABSTAIN')"),
    )
    op.create_index("idx_query_logs_decision", "query_logs", ["decision"])
    op.create_index("idx_query_logs_created", "query_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("query_logs")
    op.drop_table("gold_evidence")
    op.drop_table("benchmark_questions")
    op.drop_table("exam_sessions")
    op.drop_table("schools")
    op.drop_table("observations")
    op.drop_table("indicators")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("sources")
    op.execute("DROP EXTENSION IF EXISTS vector")
