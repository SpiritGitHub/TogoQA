# Schéma de base de données — TogoQA-Éducation

## Vue d'ensemble

La base utilise PostgreSQL 16 avec l'extension **pgvector** pour le stockage vectoriel.

10 tables organisées en 4 groupes :

| Groupe | Tables | Rôle |
|--------|--------|------|
| Gouvernance | `sources` | Registre des sources avec tier d'autorité |
| Corpus | `documents`, `chunks` | Documents ingérés et fragments indexés |
| Données structurées | `indicators`, `observations`, `schools`, `exam_sessions` | Faits numériques pour calculs vérifiés |
| Évaluation | `benchmark_questions`, `gold_evidence` | Benchmark TogoEduQA-Bench |
| Observabilité | `query_logs` | Journal des requêtes |

## Diagramme des relations

```
sources
  │
  ├──< documents
  │       │
  │       ├──< chunks (embeddings + FTS)
  │       │
  │       ├──< gold_evidence >── benchmark_questions
  │       │
  │       └──< observations >── indicators
  │
  ├──< observations
  ├──< schools
  └──< exam_sessions

query_logs (indépendant)
```

---

## Tables détaillées

### 1. `sources` — Registre des sources

Chaque source est classée par tier d'autorité. Les sources C exigent une corroboration.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PK | Identifiant auto |
| `name` | TEXT | NOT NULL | Nom de la source |
| `base_url` | TEXT | NOT NULL | URL de base |
| `authority_tier` | VARCHAR(2) | CHECK IN (A+, A, B+, B, C, D) | Tier d'autorité |
| `authority_score` | NUMERIC(3,2) | DEFAULT 0.75 | Score numérique (0.00 à 1.00) |
| `category` | TEXT | | Catégorie (statistique officielle, presse, etc.) |
| `source_owner` | TEXT | | Organisme propriétaire |
| `thematic_scope` | TEXT | | Périmètre thématique |
| `update_frequency` | TEXT | | Fréquence de mise à jour |
| `corroboration_required` | BOOLEAN | DEFAULT FALSE | Exige une corroboration si TRUE |
| `active` | BOOLEAN | DEFAULT TRUE | Source active ou désactivée |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Date de création |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Dernière mise à jour |

**Index :** `idx_sources_tier` sur `authority_tier`

### 2. `documents` — Documents ingérés

Chaque document est lié à une source et possède un statut de traitement.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PK | |
| `source_id` | INTEGER | FK → sources.id, NOT NULL | Source d'origine |
| `title` | TEXT | NOT NULL | Titre du document |
| `url` | TEXT | | URL du document |
| `published_at` | DATE | | Date de publication |
| `reference_period` | TEXT | | Période de référence des données |
| `school_year` | VARCHAR(9) | | Année scolaire (ex: 2023-2024) |
| `data_status` | VARCHAR(20) | CHECK IN (observed, provisional, estimated, target, revised) | Statut des données |
| `geographic_scope` | TEXT | DEFAULT 'national' | Couverture géographique |
| `education_level` | VARCHAR(20) | CHECK IN (preschool, primary, secondary1, secondary2, technical, superior, non_formal) | Niveau d'éducation |
| `document_type` | VARCHAR(30) | CHECK IN (annuaire, tableau_de_bord, article, communique, rapport, arrete, loi, decret) | Type de document |
| `status` | VARCHAR(20) | CHECK IN (ingested, parsed, trusted, needs_review, rejected), NOT NULL, DEFAULT 'ingested' | Statut de traitement |
| `checksum` | VARCHAR(64) | | SHA-256 pour détecter les duplications |
| `version` | INTEGER | DEFAULT 1 | Numéro de version |
| `supersedes_document_id` | INTEGER | FK → documents.id | Document remplacé |
| `parser_quality` | NUMERIC(3,2) | | Score de qualité du parsing |
| `metadata_confidence` | NUMERIC(3,2) | | Confiance dans les métadonnées extraites |
| `raw_storage_path` | TEXT | | Chemin MinIO du document brut |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | |

**Index :** `idx_documents_source`, `idx_documents_status`, `idx_documents_school_year`, `idx_documents_checksum`

### 3. `chunks` — Fragments de texte

Chaque chunk est un fragment de document avec son embedding vectoriel et un index full-text.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PK | |
| `document_id` | INTEGER | FK → documents.id ON DELETE CASCADE, NOT NULL | Document parent |
| `page` | INTEGER | | Numéro de page |
| `section` | TEXT | | Titre de section |
| `text` | TEXT | NOT NULL | Contenu textuel |
| `embedding` | VECTOR(1024) | | Embedding bge-m3 |
| `tsv` | TSVECTOR | GENERATED ALWAYS AS (to_tsvector('french', text)) STORED | Index full-text français |
| `tokens_count` | INTEGER | | Nombre de tokens |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |

**Index :**
- `idx_chunks_document` (B-tree) sur `document_id`
- `idx_chunks_fts` (GIN) sur `tsv` — recherche full-text
- Index IVFFlat sur `embedding` — recherche de similarité vectorielle

### 4. `indicators` — Dictionnaire des indicateurs

30 indicateurs éducatifs standardisés.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PK | |
| `code` | VARCHAR(50) | UNIQUE, NOT NULL | Code unique (ex: `success_rate`) |
| `label` | TEXT | NOT NULL | Libellé français |
| `definition` | TEXT | | Définition complète |
| `unit` | VARCHAR(20) | NOT NULL | Unité (%, nombre, ratio, FCFA, index) |
| `aliases` | TEXT[] | | Noms alternatifs |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |

### 5. `observations` — Valeurs numériques

Stocke les valeurs structurées pour les calculs et comparaisons.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PK | |
| `indicator_id` | INTEGER | FK → indicators.id, NOT NULL | Indicateur mesuré |
| `value` | NUMERIC | NOT NULL | Valeur numérique |
| `year` | INTEGER | | Année civile |
| `school_year` | VARCHAR(9) | | Année scolaire |
| `sex` | VARCHAR(10) | CHECK IN (total, male, female) | Ventilation par sexe |
| `region` | TEXT | | Région |
| `prefecture` | TEXT | | Préfecture |
| `education_level` | VARCHAR(20) | | Niveau d'éducation |
| `source_id` | INTEGER | FK → sources.id | Source de la donnée |
| `document_id` | INTEGER | FK → documents.id | Document source |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |

**Index :** `idx_observations_indicator`, `idx_observations_year`, `idx_observations_school_year`, `idx_observations_region`, `idx_observations_level`, `idx_observations_composite` (indicator_id, school_year, region, sex)

### 6. `schools` — Établissements scolaires

Répertoire des établissements avec géolocalisation.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PK | |
| `name` | TEXT | NOT NULL | Nom de l'établissement |
| `school_type` | VARCHAR(20) | CHECK IN (public, private, community, confessional) | Type |
| `level` | VARCHAR(20) | CHECK IN (preschool, primary, secondary1, secondary2, technical, superior) | Niveau |
| `region` | TEXT | | Région |
| `prefecture` | TEXT | | Préfecture |
| `locality` | TEXT | | Localité |
| `lat` | NUMERIC(9,6) | | Latitude |
| `lon` | NUMERIC(9,6) | | Longitude |
| `source_id` | INTEGER | FK → sources.id | Source des données |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | |

**Index :** `idx_schools_region`, `idx_schools_level`, `idx_schools_type`

### 7. `exam_sessions` — Sessions d'examens

Résultats agrégés par examen, année et optionnellement région.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PK | |
| `exam` | VARCHAR(20) | CHECK IN (CEPD, BEPC, BAC_I, BAC_II), NOT NULL | Type d'examen |
| `year` | INTEGER | NOT NULL | Année |
| `candidates_total` | INTEGER | | Total candidats |
| `girls` | INTEGER | | Candidates filles |
| `boys` | INTEGER | | Candidats garçons |
| `success_rate` | NUMERIC(5,2) | | Taux de réussite global (%) |
| `success_rate_girls` | NUMERIC(5,2) | | Taux de réussite filles (%) |
| `success_rate_boys` | NUMERIC(5,2) | | Taux de réussite garçons (%) |
| `centers` | INTEGER | | Nombre de centres d'examen |
| `region` | TEXT | | Région (NULL = national) |
| `source_id` | INTEGER | FK → sources.id | Source |
| `document_id` | INTEGER | FK → documents.id | Document source |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |

**Contrainte unique :** `(exam, year, region)` — une seule entrée par examen/année/région.

**Index :** `idx_exam_sessions_exam_year`

### 8. `benchmark_questions` — Questions de benchmark

TogoEduQA-Bench : questions annotées pour évaluer le système.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | VARCHAR(20) | PK | ID structuré (ex: EDU-TG-0001) |
| `question` | TEXT | NOT NULL | Question en français |
| `category` | VARCHAR(30) | NOT NULL | Catégorie (factuelle, temporelle, calcul, etc.) |
| `difficulty` | INTEGER | CHECK BETWEEN 1 AND 6, NOT NULL | Niveau de difficulté L1-L6 |
| `answerability` | VARCHAR(10) | CHECK IN (FULL, PARTIAL, NONE), NOT NULL | Répondabilité attendue |
| `gold_answer` | TEXT | | Réponse de référence |
| `gold_claims` | JSONB | | Claims atomiques de référence |
| `required_operations` | TEXT[] | | Opérations requises (lookup, compare, calculate, etc.) |
| `metadata_filters` | JSONB | | Filtres métadonnées attendus |
| `split` | VARCHAR(10) | CHECK IN (train, test, dev), DEFAULT 'train' | Partition |
| `annotator` | TEXT | | Annotateur |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |

**Index :** `idx_benchmark_category`, `idx_benchmark_difficulty`, `idx_benchmark_split`

### 9. `gold_evidence` — Preuves de référence

Citations exactes pour chaque question de benchmark.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PK | |
| `question_id` | VARCHAR(20) | FK → benchmark_questions.id ON DELETE CASCADE, NOT NULL | Question associée |
| `document_id` | INTEGER | FK → documents.id, NOT NULL | Document cité |
| `page` | INTEGER | | Numéro de page |
| `span` | TEXT | | Passage exact cité |
| `table_ref` | TEXT | | Référence de tableau |
| `claim_id` | TEXT | | Identifiant du claim vérifié |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |

**Index :** `idx_gold_evidence_question`

### 10. `query_logs` — Journal des requêtes

Chaque requête est journalisée pour l'observabilité et l'amélioration.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PK | |
| `question` | TEXT | NOT NULL | Question posée |
| `parsed_intent` | JSONB | | Intent parsé |
| `decision` | VARCHAR(10) | CHECK IN (ANSWER, PARTIAL, ABSTAIN) | Décision finale |
| `confidence` | NUMERIC(4,3) | | Score de confiance (0.000 à 1.000) |
| `confidence_features` | JSONB | | Détails des 10 features |
| `answer` | TEXT | | Réponse générée |
| `sources_used` | JSONB | | Sources utilisées |
| `retrieval_scores` | JSONB | | Scores de retrieval |
| `latency_ms` | INTEGER | | Temps de réponse en ms |
| `tokens_used` | INTEGER | | Tokens consommés |
| `model_version` | TEXT | | Version du modèle |
| `cache_hit` | BOOLEAN | DEFAULT FALSE | Résultat en cache |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |

**Index :** `idx_query_logs_decision`, `idx_query_logs_created`

---

## Migrations

Les migrations sont gérées par **Alembic** (voir `migrations/`).

```bash
# Appliquer toutes les migrations
alembic upgrade head

# Créer une nouvelle migration
alembic revision --autogenerate -m "description"

# Voir l'historique
alembic history

# Revenir en arrière
alembic downgrade -1
```

La migration initiale (`001_initial_schema.py`) crée les 10 tables, l'extension pgvector, et les index (B-tree, GIN pour FTS, IVFFlat pour embeddings).
