# TogoQA - Éducation

**Système de question-réponse fiable, vérifiable et conscient de son incertitude sur les données éducatives du Togo.**

> *Répondre quand les preuves suffisent, s'abstenir quand elles ne suffisent pas.*

---

## Qu'est-ce que TogoQA ?

TogoQA permet de poser une question en langage naturel sur l'éducation au Togo et d'obtenir :

- Une **réponse synthétique** rédigée en français clair
- Les **données exactes** utilisées pour construire la réponse
- Les **sources officielles** avec page, passage et badge d'autorité
- Un **score de confiance** calibré et interprétable
- Un **refus explicite** lorsque les preuves sont insuffisantes

Chaque réponse est classée **ANSWER** (confiance haute), **PARTIAL** (réponse partielle) ou **ABSTAIN** (preuves insuffisantes).

### Exemples de questions

| Question | Type |
|----------|------|
| *Quel est le taux de réussite au BEPC 2026 ?* | Fait direct |
| *De combien les candidats au CEPD ont-ils augmenté entre 2025 et 2026 ?* | Calcul |
| *Comment a évolué la réussite au CEPD entre 2021-2022 et 2023-2024 ?* | Temporel |
| *Compare BAC I, BEPC et CEPD 2026 en volume et réussite* | Multi-documents |
| *Pourquoi deux chiffres d'un même indicateur diffèrent entre deux publications ?* | Contradiction |
| *Quel est le taux d'abandon exact par préfecture en 2026 ?* | Abstention (aucune source ne le fournit) |

---

## Domaine couvert

Le système couvre **l'ensemble du domaine éducatif togolais** :

- Examens nationaux (CEPD, BEPC, BAC I, BAC II)
- Effectifs scolaires (élèves, enseignants, personnel)
- Établissements et infrastructures
- Indicateurs scolaires (accès, transition, achèvement, redoublement, abandon)
- Politiques éducatives, réformes, textes juridiques
- Enseignement technique et professionnel
- Enseignement supérieur et recherche
- Alphabétisation et éducation non-formelle
- Financement et budget de l'éducation
- Comparaisons internationales (UNESCO, Banque mondiale)

D'autres bases de données et sources seront ajoutées progressivement.

---

## Architecture

```
Question utilisateur
        │
        ▼
┌─────────────────┐
│  Parse Query     │  → intent, niveau, période, région, métrique
└────────┬────────┘
         ▼
┌─────────────────┐
│  Retrieval       │  Lexical (FTS) + Vector (bge-m3) + Structured (filtres)
│  hybride         │  → Fusion RRF → Reranking (bge-reranker-v2-m3)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Answerability   │  Les preuves suffisent-elles ? → FULL / PARTIAL / NONE
└────────┬────────┘
         │ si NONE → ABSTAIN
         ▼
┌─────────────────┐
│  Génération      │  LLM (Qwen3-8B) → réponse + claims atomiques
└────────┬────────┘
         ▼
┌─────────────────┐
│  Vérification    │  Chaque claim vérifié par NLI (mDeBERTa-v3)
│                  │  Claims numériques recalculés (Python/DuckDB)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Confiance       │  10 features → calibrateur → score de confiance
│                  │  Détection de contradictions entre sources
└────────┬────────┘
         ▼
┌─────────────────┐
│  Politique       │  ANSWER (p ≥ 0.82) / PARTIAL / ABSTAIN (p < 0.60)
└────────┬────────┘
         ▼
   Réponse + sources + confiance + trace
```

---

## Stack technique

| Couche | Technologie | Rôle |
|--------|-------------|------|
| **Frontend** | React + Vite + Tailwind | Interface publique et mode chercheur |
| **API** | FastAPI + Pydantic | Orchestration requêtes, ingestion, benchmark |
| **Base de données** | PostgreSQL 16 + pgvector | Métadonnées, faits structurés, embeddings |
| **Recherche lexicale** | PostgreSQL FTS | BM25 / lexical + filtres |
| **Object storage** | MinIO (S3-compatible) | Documents PDF/HTML bruts |
| **Jobs async** | Celery + Redis | Crawling, parsing, re-indexation |
| **Expériences** | MLflow + DVC | Tracking datasets, versions, benchmarks |
| **Packaging** | Docker Compose | Reproductibilité locale et démo |

### Composants IA

| Composant | Modèle |
|-----------|--------|
| Embeddings | BAAI/bge-m3 (dim 1024) |
| Reranker | BAAI/bge-reranker-v2-m3 |
| LLM générateur | Qwen3-8B local |
| Claim verifier (NLI) | mDeBERTa-v3 multilingual |
| Extraction PDF | PyMuPDF + pdfplumber + Camelot |
| Calculs numériques | Python / DuckDB |

---

## Démarrage rapide

### Prérequis

- [Docker](https://docs.docker.com/get-docker/) et Docker Compose
- [Python 3.11+](https://www.python.org/) (pour le développement local)
- [Node.js 20+](https://nodejs.org/) (pour le frontend)
- GPU optionnel (recommandé pour les embeddings et le LLM)

### 1. Cloner le dépôt

```bash
git clone https://github.com/SpiritGitHub/TogoQA.git
cd TogoQA
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
# Modifier .env si nécessaire (ports, mots de passe)
```

### 3. Démarrer les services

```bash
docker compose up -d
```

Cela lance :
- **PostgreSQL** (pgvector) sur le port `5432`
- **Redis** sur le port `6379`
- **MinIO** sur les ports `9000` (API) et `9001` (console)

### 4. Installer les dépendances et appliquer les migrations

```bash
pip install -e ".[dev]"
alembic upgrade head
```

### 5. Charger les données initiales

```bash
python data/seeds/sources.py      # 29 sources avec tiers d'autorité
python data/seeds/indicators.py   # 122 indicateurs éducatifs
```

### 6. Lancer les crawlers (optionnel)

```bash
# Worker Celery
celery -A src.ingestion.celery_app worker --loglevel=info -Q crawl

# Planificateur Beat (dans un autre terminal)
celery -A src.ingestion.celery_app beat --loglevel=info
```

---

## Structure du projet

```
TogoQA/
├── apps/
│   ├── api/                  # Backend FastAPI
│   │   ├── main.py           # Point d'entrée de l'API
│   │   ├── routes/           # Endpoints (ask, sources, documents, health)
│   │   ├── dependencies.py   # Injection de dépendances
│   │   └── config.py         # Configuration
│   └── web/                  # Frontend React + Vite + Tailwind
│       └── src/
│           ├── components/   # Composants réutilisables
│           ├── pages/        # Pages (accueil, résultats, chercheur)
│           ├── hooks/        # Hooks React personnalisés
│           └── api/          # Client API
│
├── src/                      # Moteur TogoQA (logique métier)
│   ├── models.py             # Modèles SQLAlchemy (10 tables, pgvector)
│   ├── db.py                 # Connexion PostgreSQL (psycopg3 + SQLAlchemy 2.0)
│   ├── privacy/              # Protection des données personnelles
│   │   ├── detector.py       # Détection PII par regex (28 types, français/Togo)
│   │   └── policy.py         # Règles EDU-001 à EDU-012, small-cell suppression
│   ├── ingestion/            # Pipeline d'ingestion de données
│   │   ├── crawlers/         # Crawlers async (httpx + BeautifulSoup)
│   │   │   ├── base.py       # Classe de base : BFS, robots.txt, SHA-256
│   │   │   ├── men.py        # MEN (education.gouv.tg) — filtrage, dates FR
│   │   │   ├── inseed.py     # INSEED (inseed.tg) — PDF, annuaires
│   │   │   └── exams.py      # Examens CEPD/BEPC/BAC — extraction stats
│   │   ├── downloader.py     # Téléchargeur versionnant (SHA-256 + manifest)
│   │   ├── storage.py        # Stockage MinIO (S3) avec dédup par checksum
│   │   ├── celery_app.py     # Config Celery (Redis broker, beat schedule)
│   │   ├── tasks.py          # 3 tâches Celery : MEN/INSEED/examens
│   │   └── parsers/          # Parsers HTML, PDF, tableaux (Semaine 3)
│   ├── retrieval/            # Recherche hybride (Semaine 5-6)
│   │   ├── vector.py         # Recherche vectorielle (pgvector + bge-m3)
│   │   ├── lexical.py        # Recherche FTS (PostgreSQL tsvector)
│   │   ├── fusion.py         # Fusion RRF (Reciprocal Rank Fusion)
│   │   └── reranker.py       # Reranking (bge-reranker-v2-m3)
│   ├── reasoning/            # Raisonnement (Semaine 8)
│   │   ├── temporal.py       # Logique temporelle
│   │   ├── numeric.py        # Calculs vérifiés (Python/DuckDB)
│   │   └── contradictions.py # Détection de contradictions
│   ├── answerability/        # Prédiction de répondabilité (Semaine 7)
│   │   ├── features.py       # 10 features de confiance
│   │   └── classifier.py     # Classificateur FULL/PARTIAL/NONE
│   ├── verification/         # Vérification des claims (Semaine 8)
│   │   ├── decompose.py      # Décomposition en claims atomiques
│   │   └── nli.py            # Natural Language Inference (mDeBERTa-v3)
│   ├── confidence/           # Calibration et politique (Semaine 9)
│   │   ├── calibrator.py     # Calibrateur de confiance (isotonique/Platt)
│   │   └── policy.py         # Politique ANSWER/PARTIAL/ABSTAIN
│   └── generation/           # Adaptateur LLM (Semaine 5)
│       └── llm.py            # Interface fournisseur-agnostique (Qwen3-8B)
│
├── data/
│   ├── manifests/            # Fichiers de référence JSON
│   │   ├── indicators.json   # 122 indicateurs éducatifs (16 catégories)
│   │   ├── pii_rules.json    # 28 types PII + 12 règles EDU + tokens
│   │   └── pii_tests.json    # 52 cas de test PII (11 couches)
│   ├── schemas/              # Schéma SQL initial
│   ├── seeds/                # Scripts de données initiales
│   │   ├── sources.py        # Seed des 29 sources (upsert SQL)
│   │   └── indicators.py     # Seed des 122 indicateurs (upsert + JSONB)
│   ├── downloads/            # Documents téléchargés + manifest.json
│   └── benchmark/            # TogoEduQA-Bench (questions gold)
│
├── migrations/               # Migrations Alembic
│   └── versions/             # Fichiers de migration versionnés
│
├── experiments/              # Configurations MLflow
├── tests/                    # Tests automatisés
│   ├── unit/
│   ├── integration/
│   └── benchmark/
├── docker/                   # Dockerfiles (api, web, worker)
├── docs/                     # Documentation du projet
│
├── docker-compose.yml        # Services Docker
├── pyproject.toml            # Dépendances Python
├── alembic.ini               # Configuration Alembic
├── .env.example              # Variables d'environnement
└── .gitignore
```

---

## Sources de données

TogoQA utilise **29 sources** classées par tier d'autorité :

| Tier | Score | Catégorie | Exemple |
|------|-------|-----------|---------|
| **A+** | 1.00 | Texte juridique officiel | Journal Officiel, LégiTogo |
| **A** | 0.95 | Statistique officielle / portail gouvernemental | INSEED, MEN, Open Data Togo |
| **B+** | 0.85 | Organisation internationale avec méthodologie | UNESCO, Banque mondiale, UNICEF |
| **B** | 0.75 | Presse publique | ATOP, Togo Presse |
| **C** | 0.55 | Presse privée (corroboration obligatoire) | Togo First, Icilome |
| **D** | ≤0.20 | Non vérifiée (jamais preuve finale) | Réseaux sociaux |

> Les sources C exigent une corroboration par une source A/A+ ou B+ avant de justifier une réponse factuelle. Les sources D ne sont jamais utilisées comme preuve finale.

---

## Base de données

10 tables PostgreSQL :

| Table | Rôle |
|-------|------|
| `sources` | Registre des 29 sources avec tier d'autorité |
| `documents` | Documents ingérés avec métadonnées et versionnement |
| `chunks` | Fragments de texte avec embedding vectoriel + FTS |
| `indicators` | Dictionnaire des 30 indicateurs éducatifs |
| `observations` | Valeurs numériques structurées pour les calculs |
| `schools` | Répertoire des établissements scolaires |
| `exam_sessions` | Résultats agrégés des examens nationaux |
| `benchmark_questions` | TogoEduQA-Bench (questions annotées) |
| `gold_evidence` | Citations de référence pour le benchmark |
| `query_logs` | Journal de chaque requête (observabilité) |

Voir [docs/schema.md](docs/schema.md) pour le détail complet.

---

## Documentation

| Document | Contenu |
|----------|---------|
| [docs/modules.md](docs/modules.md) | Documentation technique de chaque fichier : rôle, algorithmes, bibliothèques |
| [docs/architecture.md](docs/architecture.md) | Architecture globale, pipeline d'une question, score de confiance |
| [docs/schema.md](docs/schema.md) | Schéma des 10 tables PostgreSQL avec colonnes et index |
| [docs/sources.md](docs/sources.md) | Inventaire des 29 sources, tiers d'autorité, règles de corroboration |
| [docs/development.md](docs/development.md) | Guide d'installation, workflow Git, commandes utiles |

---

## Tests

98 tests unitaires couvrent les modules implémentés :

```bash
pytest                         # tout lancer
pytest tests/unit/test_pii.py  # 56 tests PII (détection, politique, faux positifs)
pytest tests/unit/test_crawlers.py    # 19 tests crawlers (base, MEN, INSEED)
pytest tests/unit/test_ingestion.py   # 23 tests (downloader, examens, MinIO, Celery)
```

---

## Développement

### Installer les dépendances

```bash
pip install -e ".[dev]"
```

### Linter

```bash
ruff check src/ apps/ tests/
```

### Créer une migration

```bash
alembic revision --autogenerate -m "description du changement"
alembic upgrade head
```

---

## Workflow Git

| Branche | Rôle |
|---------|------|
| `main` | Production stable, merge uniquement depuis `dev` |
| `dev` | Intégration, features mergés ici |
| `azharwork` | Branche de travail, PR vers `dev` |

Flux : `azharwork` → PR → `dev` → PR → `main`

---

## Roadmap

Le projet suit un plan de développement en **12 semaines**. Voir les [milestones GitHub](https://github.com/SpiritGitHub/TogoQA/milestones) et les [62 issues](https://github.com/SpiritGitHub/TogoQA/issues) pour le suivi détaillé.

| Semaine | Livrable | Statut |
|---------|----------|--------|
| S1 | Fondations : structure, Docker, schéma DB, sources, indicateurs, PII | Done |
| S2 | Collecte : crawlers MEN/INSEED/examens, downloader, MinIO, Celery | Done |
| S3 | Parsing : HTML, PDF, tableaux, normalisation | |
| S4 | Données structurées + 50 questions gold |
| S5 | RAG baseline (B1) |
| S6 | Retrieval hybride + reranker (B2) |
| S7 | Answerability + confiance |
| S8 | Vérification claims + contradictions |
| S9 | Benchmark 150 questions + calibration |
| S10 | Expériences B0-B4 + ablations |
| S11 | Interface publique + mode chercheur |
| S12 | Reproductibilité + article de conférence |

---

## Licence

MIT

---

## Auteur

**Azhar Barde** — bardesteven17@gmail.com
