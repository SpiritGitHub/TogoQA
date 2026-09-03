-- TogoQA-Éducation — Schéma initial
-- PostgreSQL 16 + pgvector

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- 1. SOURCES — Gouvernance et autorité des sources
-- ============================================================
CREATE TABLE sources (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    base_url        TEXT NOT NULL,
    authority_tier  VARCHAR(2) NOT NULL CHECK (authority_tier IN ('A+','A','B+','B','C','D')),
    authority_score NUMERIC(3,2) NOT NULL DEFAULT 0.75,
    category        TEXT,
    source_owner    TEXT,
    thematic_scope  TEXT,
    update_frequency TEXT,
    corroboration_required BOOLEAN NOT NULL DEFAULT false,
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE sources IS 'Registre des sources avec tier d''autorité (A+ à D) et règles de corroboration';
COMMENT ON COLUMN sources.authority_tier IS 'A+=juridique officiel, A=stat officielle, B+=org internationale, B=presse publique, C=presse privée, D=non vérifiée';
COMMENT ON COLUMN sources.corroboration_required IS 'true pour les sources C : exige une corroboration A/A+ ou B+ avant réponse factuelle';

CREATE INDEX idx_sources_tier ON sources (authority_tier);

-- ============================================================
-- 2. DOCUMENTS — Traçabilité et versionnement
-- ============================================================
CREATE TABLE documents (
    id                  SERIAL PRIMARY KEY,
    source_id           INTEGER NOT NULL REFERENCES sources(id),
    title               TEXT NOT NULL,
    url                 TEXT,
    published_at        DATE,
    reference_period    TEXT,
    school_year         VARCHAR(9),
    data_status         VARCHAR(20) CHECK (data_status IN ('observed','provisional','estimated','target','revised')),
    geographic_scope    TEXT DEFAULT 'national',
    education_level     VARCHAR(20) CHECK (education_level IN ('preschool','primary','secondary1','secondary2','technical','superior','non_formal')),
    document_type       VARCHAR(30) CHECK (document_type IN ('annuaire','tableau_de_bord','article','communique','rapport','arrete','loi','decret')),
    status              VARCHAR(20) NOT NULL DEFAULT 'ingested' CHECK (status IN ('ingested','parsed','trusted','needs_review','rejected')),
    checksum            VARCHAR(64),
    version             INTEGER NOT NULL DEFAULT 1,
    supersedes_document_id INTEGER REFERENCES documents(id),
    parser_quality      NUMERIC(3,2),
    metadata_confidence NUMERIC(3,2),
    raw_storage_path    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE documents IS 'Chaque document ingéré avec métadonnées obligatoires pour le filtrage temporel et géographique';
COMMENT ON COLUMN documents.reference_period IS 'Période réellement décrite par la donnée (ex: 2023-2024)';
COMMENT ON COLUMN documents.school_year IS 'Année scolaire au format YYYY-YYYY (ex: 2023-2024)';
COMMENT ON COLUMN documents.data_status IS 'observed=définitif, provisional=provisoire, estimated=estimation, target=prévision, revised=révisé';
COMMENT ON COLUMN documents.checksum IS 'SHA-256 du document brut pour détecter les doublons et versions';
COMMENT ON COLUMN documents.supersedes_document_id IS 'Lien vers le document précédent que celui-ci remplace';

CREATE INDEX idx_documents_source ON documents (source_id);
CREATE INDEX idx_documents_status ON documents (status);
CREATE INDEX idx_documents_school_year ON documents (school_year);
CREATE INDEX idx_documents_checksum ON documents (checksum);

-- ============================================================
-- 3. CHUNKS — Fragments pour RAG et citation fine
-- ============================================================
CREATE TABLE chunks (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page            INTEGER,
    section         TEXT,
    text            TEXT NOT NULL,
    embedding       vector(1024),
    tokens_count    INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE chunks IS 'Fragments de texte avec embedding vectoriel pour la recherche sémantique et la citation fine';
COMMENT ON COLUMN chunks.embedding IS 'Vecteur bge-m3 de dimension 1024';

CREATE INDEX idx_chunks_document ON chunks (document_id);
CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Recherche full-text sur les chunks
ALTER TABLE chunks ADD COLUMN tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('french', text)) STORED;
CREATE INDEX idx_chunks_fts ON chunks USING gin (tsv);

-- ============================================================
-- 4. INDICATORS — Dictionnaire statistique des indicateurs
-- ============================================================
CREATE TABLE indicators (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(50) NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    definition  TEXT,
    unit        VARCHAR(20) NOT NULL,
    aliases     TEXT[],
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE indicators IS 'Dictionnaire des 30+ indicateurs éducatifs avec code, label, définition et unité';
COMMENT ON COLUMN indicators.aliases IS 'Autres noms courants pour cet indicateur (matching flou)';

-- ============================================================
-- 5. OBSERVATIONS — Données structurées pour calculs
-- ============================================================
CREATE TABLE observations (
    id              SERIAL PRIMARY KEY,
    indicator_id    INTEGER NOT NULL REFERENCES indicators(id),
    value           NUMERIC NOT NULL,
    year            INTEGER,
    school_year     VARCHAR(9),
    sex             VARCHAR(10) CHECK (sex IN ('total','male','female')),
    region          TEXT,
    prefecture      TEXT,
    education_level VARCHAR(20),
    source_id       INTEGER REFERENCES sources(id),
    document_id     INTEGER REFERENCES documents(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE observations IS 'Valeurs numériques extraites des documents, liées à un indicateur, pour le raisonnement numérique';

CREATE INDEX idx_observations_indicator ON observations (indicator_id);
CREATE INDEX idx_observations_year ON observations (year);
CREATE INDEX idx_observations_school_year ON observations (school_year);
CREATE INDEX idx_observations_region ON observations (region);
CREATE INDEX idx_observations_level ON observations (education_level);
CREATE INDEX idx_observations_composite ON observations (indicator_id, school_year, region, sex);

-- ============================================================
-- 6. SCHOOLS — Établissements scolaires
-- ============================================================
CREATE TABLE schools (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    school_type VARCHAR(20) CHECK (school_type IN ('public','private','community','confessional')),
    level       VARCHAR(20) CHECK (level IN ('preschool','primary','secondary1','secondary2','technical','superior')),
    region      TEXT,
    prefecture  TEXT,
    locality    TEXT,
    lat         NUMERIC(9,6),
    lon         NUMERIC(9,6),
    source_id   INTEGER REFERENCES sources(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE schools IS 'Répertoire des établissements scolaires du Togo avec localisation';

CREATE INDEX idx_schools_region ON schools (region);
CREATE INDEX idx_schools_level ON schools (level);
CREATE INDEX idx_schools_type ON schools (school_type);

-- ============================================================
-- 7. EXAM_SESSIONS — Sessions d'examens nationaux
-- ============================================================
CREATE TABLE exam_sessions (
    id              SERIAL PRIMARY KEY,
    exam            VARCHAR(20) NOT NULL CHECK (exam IN ('CEPD','BEPC','BAC_I','BAC_II')),
    year            INTEGER NOT NULL,
    candidates_total INTEGER,
    girls           INTEGER,
    boys            INTEGER,
    success_rate    NUMERIC(5,2),
    success_rate_girls NUMERIC(5,2),
    success_rate_boys  NUMERIC(5,2),
    centers         INTEGER,
    region          TEXT,
    source_id       INTEGER REFERENCES sources(id),
    document_id     INTEGER REFERENCES documents(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_exam_session UNIQUE (exam, year, region)
);

COMMENT ON TABLE exam_sessions IS 'Résultats agrégés des examens nationaux par session, examen et éventuellement région';

CREATE INDEX idx_exam_sessions_exam_year ON exam_sessions (exam, year);

-- ============================================================
-- 8. BENCHMARK_QUESTIONS — Questions annotées pour évaluation
-- ============================================================
CREATE TABLE benchmark_questions (
    id              VARCHAR(20) PRIMARY KEY,
    question        TEXT NOT NULL,
    category        VARCHAR(30) NOT NULL,
    difficulty      INTEGER NOT NULL CHECK (difficulty BETWEEN 1 AND 6),
    answerability   VARCHAR(10) NOT NULL CHECK (answerability IN ('FULL','PARTIAL','NONE')),
    gold_answer     TEXT,
    gold_claims     JSONB,
    required_operations TEXT[],
    metadata_filters JSONB,
    split           VARCHAR(10) DEFAULT 'train' CHECK (split IN ('train','test','dev')),
    annotator       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE benchmark_questions IS 'TogoEduQA-Bench : questions annotées avec réponse gold, difficulté L1-L6, answerability';
COMMENT ON COLUMN benchmark_questions.category IS 'factual, calculation_temporal, multi_document, contradiction, regional, adversarial, unanswerable';
COMMENT ON COLUMN benchmark_questions.difficulty IS 'L1=fait direct, L2=filtre temporel, L3=calcul, L4=multi-doc, L5=contradiction, L6=piège answerability';

CREATE INDEX idx_benchmark_category ON benchmark_questions (category);
CREATE INDEX idx_benchmark_difficulty ON benchmark_questions (difficulty);
CREATE INDEX idx_benchmark_split ON benchmark_questions (split);

-- ============================================================
-- 9. GOLD_EVIDENCE — Citations de référence pour le benchmark
-- ============================================================
CREATE TABLE gold_evidence (
    id              SERIAL PRIMARY KEY,
    question_id     VARCHAR(20) NOT NULL REFERENCES benchmark_questions(id) ON DELETE CASCADE,
    document_id     INTEGER NOT NULL REFERENCES documents(id),
    page            INTEGER,
    span            TEXT,
    table_ref       TEXT,
    claim_id        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE gold_evidence IS 'Preuves de référence liant une question benchmark à un passage précis d''un document';

CREATE INDEX idx_gold_evidence_question ON gold_evidence (question_id);

-- ============================================================
-- 10. QUERY_LOGS — Observabilité et journalisation
-- ============================================================
CREATE TABLE query_logs (
    id              SERIAL PRIMARY KEY,
    question        TEXT NOT NULL,
    parsed_intent   JSONB,
    decision        VARCHAR(10) CHECK (decision IN ('ANSWER','PARTIAL','ABSTAIN')),
    confidence      NUMERIC(4,3),
    confidence_features JSONB,
    answer          TEXT,
    sources_used    JSONB,
    retrieval_scores JSONB,
    latency_ms      INTEGER,
    tokens_used     INTEGER,
    model_version   TEXT,
    cache_hit       BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE query_logs IS 'Journal de chaque requête utilisateur : question, décision, confiance, latence, modèle';

CREATE INDEX idx_query_logs_decision ON query_logs (decision);
CREATE INDEX idx_query_logs_created ON query_logs (created_at);
