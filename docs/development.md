# Guide de développement — TogoQA-Éducation

## Prérequis

| Outil | Version minimale | Usage |
|-------|-----------------|-------|
| Docker + Docker Compose | 24+ | Services (PostgreSQL, Redis, MinIO) |
| Python | 3.11+ | Backend, moteur TogoQA |
| Node.js | 20+ | Frontend React |
| Git | 2.40+ | Contrôle de version |
| GPU (optionnel) | CUDA 12+ | Embeddings et LLM (fonctionne aussi en CPU) |

## Installation

### 1. Cloner et configurer

```bash
git clone https://github.com/SpiritGitHub/TogoQA.git
cd TogoQA
cp .env.example .env
```

### 2. Démarrer les services Docker

```bash
docker compose up -d
```

Services lancés :
- **PostgreSQL** (pgvector) : `localhost:5432`
- **Redis** : `localhost:6379`
- **MinIO** : `localhost:9000` (API) / `localhost:9001` (console web)

Identifiants par défaut (voir `.env`) :
- PostgreSQL : `togoqa` / `togoqa_dev`
- MinIO : `togoqa` / `togoqa_minio_dev`

### 3. Installer les dépendances Python

```bash
pip install -e ".[dev]"
```

### 4. Appliquer les migrations de base de données

```bash
alembic upgrade head
```

### 5. Charger les données initiales

```bash
python data/seeds/sources.py
python data/seeds/indicators.py
```

---

## Workflow Git

### Branches

| Branche | Rôle | Merge depuis |
|---------|------|-------------|
| `main` | Production stable | `dev` uniquement |
| `dev` | Intégration | `azharwork` |
| `azharwork` | Travail quotidien | — |

### Processus de travail

1. Travailler sur `azharwork`
2. Committer régulièrement
3. Pousser vers GitHub
4. Créer une PR de `azharwork` → `dev`
5. Review et merge dans `dev`
6. Quand `dev` est stable, PR de `dev` → `main`

```bash
# Basculer sur la branche de travail
git checkout azharwork

# Committer les changements
git add <fichiers>
git commit -m "description du changement"

# Pousser
git push origin azharwork
```

---

## Structure du code

### Moteur TogoQA (`src/`)

```
src/
├── db.py              # Connexion PostgreSQL (psycopg3 + SQLAlchemy 2.0)
├── models.py          # 10 modèles ORM (pgvector, JSONB, ARRAY, TSVECTOR)
├── privacy/           # Protection des données personnelles
│   ├── detector.py    # Détection PII par regex (28 types, spécialisé FR/Togo)
│   └── policy.py      # 12 règles éducatives (EDU-001 à EDU-012)
├── ingestion/         # Pipeline d'ingestion
│   ├── crawlers/      # Crawlers async httpx + BeautifulSoup
│   │   ├── base.py    # BFS, robots.txt, allowlist, SHA-256
│   │   ├── men.py     # education.gouv.tg (dates FR, filtrage)
│   │   ├── inseed.py  # inseed.tg (PDFs, annuaires)
│   │   └── exams.py   # Résultats CEPD/BEPC/BAC (extraction stats)
│   ├── downloader.py  # Téléchargement + manifest SHA-256 + versionnement
│   ├── storage.py     # MinIO S3 : upload, dédup, chemins structurés
│   ├── celery_app.py  # Config Celery : Redis broker, beat schedule
│   ├── tasks.py       # 3 tâches : crawl_men, crawl_inseed, crawl_exams
│   └── parsers/       # Parsers HTML, PDF, tableaux (Semaine 3)
├── retrieval/         # Recherche hybride (Semaine 5-6)
├── reasoning/         # Raisonnement temporel, numérique (Semaine 8)
├── answerability/     # Prédiction de répondabilité (Semaine 7)
├── verification/      # Vérification claims NLI (Semaine 8)
├── confidence/        # Calibration et politique (Semaine 9)
└── generation/        # Adaptateur LLM (Semaine 5)
```

Pour la documentation détaillée de chaque fichier (algorithmes, bibliothèques), voir [docs/modules.md](modules.md).

### API (`apps/api/`)

FastAPI avec :
- `main.py` : point d'entrée, middleware, CORS
- `routes/` : endpoints regroupés par domaine
- `config.py` : configuration centralisée
- `dependencies.py` : injection de dépendances

### Frontend (`apps/web/`)

React + Vite + Tailwind (pas de TypeScript) :
- `src/components/` : composants réutilisables
- `src/pages/` : pages de l'application
- `src/hooks/` : hooks React personnalisés
- `src/api/` : client API

---

## Base de données

### Connexion

La connexion est définie dans `src/db.py` via la variable d'environnement `DATABASE_URL` :

```
postgresql+psycopg://togoqa:togoqa_dev@localhost:5432/togoqa
```

### Migrations Alembic

```bash
# Appliquer toutes les migrations pendantes
alembic upgrade head

# Créer une nouvelle migration auto-détectée
alembic revision --autogenerate -m "ajouter colonne X"

# Voir l'historique des migrations
alembic history

# Voir la version actuelle
alembic current

# Revenir d'une migration
alembic downgrade -1
```

Les migrations sont dans `migrations/versions/`. Le fichier `migrations/env.py` charge la `DATABASE_URL` depuis les variables d'environnement.

### Accéder à la base directement

```bash
docker compose exec db psql -U togoqa -d togoqa
```

---

## Celery — Crawlers automatisés

### Démarrer un worker

```bash
celery -A src.ingestion.celery_app worker --loglevel=info -Q crawl
```

### Démarrer le planificateur Beat

```bash
celery -A src.ingestion.celery_app beat --loglevel=info
```

Le beat schedule lance automatiquement :
- `crawl_men` : tous les jours (crawl du MEN — education.gouv.tg)
- `crawl_exams` : tous les jours (extraction de résultats d'examens)
- `crawl_inseed` : toutes les semaines (crawl INSEED — inseed.tg)

### Lancer un crawl manuellement

```python
from src.ingestion.tasks import crawl_men, crawl_inseed, crawl_exams
crawl_men.delay()       # lance le crawl MEN en arrière-plan
crawl_inseed.delay()    # lance le crawl INSEED
crawl_exams.delay()     # lance le crawl examens
```

### Monitorer les tâches

```bash
celery -A src.ingestion.celery_app flower  # interface web (nécessite pip install flower)
```

---

## Tests

```bash
# Lancer tous les tests (98 tests)
pytest

# Tests unitaires uniquement
pytest tests/unit/

# Par module
pytest tests/unit/test_pii.py          # 56 tests PII
pytest tests/unit/test_crawlers.py     # 19 tests crawlers
pytest tests/unit/test_ingestion.py    # 23 tests downloader/exams/MinIO/Celery

# Tests d'intégration (nécessite Docker)
pytest tests/integration/

# Tests de benchmark
pytest tests/benchmark/

# Avec couverture
pytest --cov=src --cov=apps
```

---

## Linter et formatage

Le projet utilise **Ruff** pour le linting et le formatage :

```bash
# Vérifier
ruff check src/ apps/ tests/

# Corriger automatiquement
ruff check --fix src/ apps/ tests/

# Formater
ruff format src/ apps/ tests/
```

---

## Variables d'environnement

Toutes les variables sont dans `.env` (copié depuis `.env.example`) :

| Variable | Valeur par défaut | Description |
|----------|------------------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://togoqa:togoqa_dev@localhost:5432/togoqa` | Connexion PostgreSQL |
| `REDIS_URL` | `redis://localhost:6379/0` | Connexion Redis |
| `MINIO_ENDPOINT` | `localhost:9000` | Endpoint MinIO |
| `MINIO_ACCESS_KEY` | `togoqa` | Clé d'accès MinIO |
| `MINIO_SECRET_KEY` | `togoqa_minio_dev` | Secret MinIO |
| `MINIO_BUCKET` | `togoqa-documents` | Bucket de stockage |
| `API_HOST` | `0.0.0.0` | Hôte de l'API |
| `API_PORT` | `8000` | Port de l'API |
| `LLM_MODEL` | `Qwen/Qwen3-8B` | Modèle de génération |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Modèle d'embeddings |
| `EMBEDDING_DIM` | `1024` | Dimension des embeddings |
| `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Modèle de reranking |

---

## Console MinIO

Accéder à la console web MinIO :
- URL : http://localhost:9001
- Login : `togoqa` / `togoqa_minio_dev`

Les documents bruts (PDF, HTML) sont stockés dans le bucket `togoqa-documents`.

---

## Documentation technique

Pour la documentation complète de chaque fichier (rôle, fonctionnement, algorithmes, bibliothèques utilisées), voir :

- [docs/modules.md](modules.md) — Documentation détaillée de chaque module implémenté
- [docs/architecture.md](architecture.md) — Architecture globale et pipeline
- [docs/schema.md](schema.md) — Schéma de base de données
- [docs/sources.md](sources.md) — Inventaire des 29 sources
