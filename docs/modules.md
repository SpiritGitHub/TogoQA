# Documentation des modules — TogoQA-Éducation

Ce document décrit chaque fichier implémenté du projet : son rôle, son fonctionnement interne, les algorithmes utilisés et les bibliothèques dont il dépend.

---

## Table des matières

1. [Base de données](#1-base-de-données)
   - [src/db.py](#srcdbpy)
   - [src/models.py](#srcmodelspy)
2. [Migrations](#2-migrations)
   - [001_initial_schema.py](#001_initial_schemapy)
   - [002_add_indicator_category_meta.py](#002_add_indicator_category_metapy)
3. [Données initiales (Seeds)](#3-données-initiales-seeds)
   - [data/seeds/sources.py](#dataseedssourcespy)
   - [data/seeds/indicators.py](#dataseedsindicatorspy)
4. [Confidentialité (Privacy)](#4-confidentialité-privacy)
   - [src/privacy/detector.py](#srcprivacydetectorpy)
   - [src/privacy/policy.py](#srcprivacypolicypy)
5. [Ingestion — Crawlers](#5-ingestion--crawlers)
   - [src/ingestion/crawlers/base.py](#srcingestioncrawlersbasepy)
   - [src/ingestion/crawlers/men.py](#srcingestioncrawlersmenpy)
   - [src/ingestion/crawlers/inseed.py](#srcingestioncrawlersinseedpy)
   - [src/ingestion/crawlers/exams.py](#srcingestioncrawlersexamspy)
6. [Ingestion — Téléchargement et stockage](#6-ingestion--téléchargement-et-stockage)
   - [src/ingestion/downloader.py](#srcingestiondownloaderpy)
   - [src/ingestion/storage.py](#srcingestionstoragepy)
7. [Ingestion — Orchestration](#7-ingestion--orchestration)
   - [src/ingestion/celery_app.py](#srcingestioncelery_apppy)
   - [src/ingestion/tasks.py](#srcingestiontaskspy)
8. [Manifestes de données](#8-manifestes-de-données)
   - [data/manifests/indicators.json](#datamanifestsindicatorsjson)
   - [data/manifests/pii_rules.json](#datamanifestspii_rulesjson)
   - [data/manifests/pii_tests.json](#datamanifestspii_testsjson)
9. [Tests](#9-tests)
   - [tests/unit/test_pii.py](#testsunittest_piipy)
   - [tests/unit/test_crawlers.py](#testsunittest_crawlerspy)
   - [tests/unit/test_ingestion.py](#testsunittest_ingestionpy)

---

## 1. Base de données

### `src/db.py`

**Rôle** : Connexion à PostgreSQL et session factory SQLAlchemy.

**Fonctionnement** :
- Lit `DATABASE_URL` depuis les variables d'environnement (fallback : `postgresql+psycopg://togoqa:togoqa_dev@localhost:5432/togoqa`)
- Crée un `Engine` SQLAlchemy avec le driver **psycopg** (successeur de psycopg2, async-ready)
- Expose `SessionLocal` (session factory) et `get_db()` (générateur de session pour l'injection de dépendances FastAPI)
- Définit `Base` (classe de base déclarative pour tous les modèles ORM)

**Bibliothèques** :
| Bibliothèque | Version | Rôle |
|---|---|---|
| `sqlalchemy` | 2.x | ORM et moteur SQL, API déclarative 2.0 (mapped_column) |
| `psycopg` | 3.x | Driver PostgreSQL natif (C + Python), remplace psycopg2 |

---

### `src/models.py`

**Rôle** : Définition des 10 tables ORM du schéma TogoQA.

**Tables** :

| # | Classe | Table | Colonnes clés | Rôle |
|---|--------|-------|---------------|------|
| 1 | `Source` | `sources` | name, base_url, authority_tier, authority_score | Registre des 29 sources avec tier d'autorité (A+/A/B+/B/C/D) |
| 2 | `Document` | `documents` | source_id, title, url, checksum, status, raw_storage_path | Documents ingérés avec versionnement SHA-256 et métadonnées |
| 3 | `Chunk` | `chunks` | document_id, text, embedding (Vector 1024), tokens_count | Fragments de texte avec embedding vectoriel pour le RAG |
| 4 | `Indicator` | `indicators` | code, label, unit, aliases, category, meta (JSONB) | Dictionnaire des 122 indicateurs éducatifs |
| 5 | `Observation` | `observations` | indicator_id, value, year, school_year, sex, region | Valeurs numériques structurées pour calculs |
| 6 | `School` | `schools` | name, school_type, level, region, lat, lon | Répertoire des établissements scolaires |
| 7 | `ExamSession` | `exam_sessions` | exam, year, candidates_total, success_rate | Résultats agrégés des examens nationaux |
| 8 | `BenchmarkQuestion` | `benchmark_questions` | question, category, difficulty, answerability | Questions annotées du benchmark TogoEduQA-Bench |
| 9 | `GoldEvidence` | `gold_evidence` | question_id, document_id, page, span | Citations de référence pour l'évaluation |
| 10 | `QueryLog` | `query_logs` | question, decision, confidence, latency_ms | Journal de chaque requête pour observabilité |

**Fonctionnement** :
- Utilise l'API déclarative SQLAlchemy 2.0 avec `Mapped[]` et `mapped_column()`
- Les types PostgreSQL spéciaux : `ARRAY(Text)` pour les alias, `JSONB` pour les métadonnées flexibles, `TSVECTOR` pour la recherche full-text, `Vector(1024)` de pgvector pour les embeddings
- Les `CheckConstraint` appliquent la validation au niveau base (tiers d'autorité, types d'examen, statuts)
- Les `Index` B-tree optimisent les requêtes fréquentes ; GIN est utilisé pour le FTS ; IVFFlat pour les embeddings
- Les `relationship()` permettent la navigation ORM entre tables liées (Source → Documents → Chunks)

**Bibliothèques** :
| Bibliothèque | Rôle |
|---|---|
| `sqlalchemy` | ORM : modèles déclaratifs, contraintes, index, relations |
| `pgvector.sqlalchemy` | Type `Vector(1024)` pour stocker les embeddings dans PostgreSQL |

---

## 2. Migrations

### `001_initial_schema.py`

**Rôle** : Crée les 10 tables initiales du schéma, l'extension pgvector, et tous les index.

**Fonctionnement** :
- Active l'extension `vector` dans PostgreSQL (`CREATE EXTENSION IF NOT EXISTS vector`)
- Crée les tables dans l'ordre des dépendances (sources → documents → chunks, etc.)
- Ajoute les index B-tree, GIN (pour `tsv` full-text), et IVFFlat (pour les embeddings vectoriels)
- La migration est réversible (`downgrade` supprime les tables dans l'ordre inverse)

**Bibliothèque** : Alembic (gestion de migrations incrémentales pour SQLAlchemy)

### `002_add_indicator_category_meta.py`

**Rôle** : Étend la table `indicators` pour supporter les 122 indicateurs enrichis.

**Modifications** :
1. `ALTER COLUMN unit` : VARCHAR(20) → VARCHAR(30) pour accommoder les unités plus longues
2. `ADD COLUMN category` : VARCHAR(40), catégorie thématique de l'indicateur
3. `ADD COLUMN meta` : JSONB, métadonnées flexibles (dimensions, value_type, formula, source_hints, notes)
4. `CREATE INDEX idx_indicators_category` : index B-tree sur la catégorie

**Bibliothèque** : Alembic

---

## 3. Données initiales (Seeds)

### `data/seeds/sources.py`

**Rôle** : Peuple la table `sources` avec les 29 sources officielles du blueprint.

**Fonctionnement** :
1. Vérifie si la table contient déjà des données (idempotence : skip si non vide)
2. Pour chaque source : exécute un `INSERT INTO sources` avec les 9 champs (name, base_url, authority_tier, authority_score, category, source_owner, thematic_scope, update_frequency, corroboration_required)
3. Les sources sont classées par tier : 2 A+ (juridiques), 10 A (gouvernementales), 9 B+ (internationales), 2 B (presse publique), 6 C (presse privée, corroboration obligatoire)

**Algorithme** : Insertion directe via requête SQL brute avec `text()`. Transaction atomique (`engine.begin()`).

**Bibliothèques** :
| Bibliothèque | Rôle |
|---|---|
| `sqlalchemy` | Engine + exécution SQL brute |
| `python-dotenv` | Chargement des variables `.env` |

### `data/seeds/indicators.py`

**Rôle** : Peuple la table `indicators` avec les 122 indicateurs éducatifs depuis le manifeste JSON.

**Fonctionnement** :
1. Charge le fichier `data/manifests/indicators.json` (122 indicateurs, 16 catégories)
2. Pour chaque indicateur, construit un objet `meta` JSONB qui regroupe : dimensions, value_type, formula, source_hints, notes
3. Exécute un **upsert** (`INSERT ... ON CONFLICT (code) DO UPDATE`) : idempotent, peut être relancé sans risque de doublons
4. Les aliases sont insérés comme `TEXT[]` (array PostgreSQL natif)

**Algorithme** : Upsert SQL natif PostgreSQL via `ON CONFLICT`. Transaction atomique.

**Bibliothèques** : `sqlalchemy`, `python-dotenv`, `json`

---

## 4. Confidentialité (Privacy)

### `src/privacy/detector.py`

**Rôle** : Détecteur de données personnelles (PII) par expressions régulières, spécialisé pour le contexte éducatif togolais et francophone.

**Algorithme de détection** :

Le détecteur fonctionne en 3 couches :

**Couche 1 — Patterns regex directs** :
| Pattern | Type PII | Risque | Description |
|---|---|---|---|
| `PHONE_TG` | phone_number | HIGH | Numéros togolais : +228 suivi de 90/70/20 + 6 chiffres |
| `EMAIL` | email_address | HIGH | Standard RFC-like : `user@domain.ext` |
| `STUDENT_ID` | student_id | HIGH | Format `ETU-YYYY-NNNNNN` |
| `CANDIDATE_NUM` | exam_candidate_number | HIGH | Format `BAC2-LOME-001234` |
| `DATE_OF_BIRTH` | date_of_birth | MEDIUM | `né(e) le JJ/MM/AAAA` |
| `GEOLOC` | precise_geolocation | HIGH | Coordonnées lat/lon avec 3+ décimales |
| `SECRET_PATTERN` | password_secret_token | CRITICAL | `mot de passe/password/api_key : valeur` avec mot optionnel intercalé |
| `SCORE_INDIVIDUAL` | student_grades | HIGH | Notes individuelles (`N/20`) en contexte élève/candidat |

**Couche 2 — Détection par mots-clés** :
- Données biométriques (empreinte, iris)
- Informations de santé (maladie, diagnostic)
- Handicap/besoins spéciaux
- Dossier disciplinaire (sanction, exclusion)
- Présence/absence (avec mention de "jours")
- Passeport, identité parent/tuteur

**Couche 3 — Détection de noms de personnes** :
1. **Contextuelle** : après les mots "candidat", "élève", "étudiant", "enseignant" → capture le nom qui suit (PATRONYME Prénom)
2. **Bare pattern** : `PATRONYME Prénom` — le patronyme est en MAJUSCULES (2+ chars), le prénom commence par une majuscule suivie de minuscules (3+ chars). Cette distinction évite les faux positifs sur "BAC II" (II est tout en majuscules, donc ne matche pas comme prénom).

**Fonctions** :
- `detect_text(text)` → `list[PIIMatch]` : scan complet du texte
- `detect_columns(columns)` → `list[str]` : vérifie les noms de colonnes contre un set de 32 mots-clés PII
- `redact(text)` → `str` : remplace chaque PII détecté par son token de redaction (depuis le JSON de config)

**Bibliothèques** :
| Bibliothèque | Rôle |
|---|---|
| `re` (stdlib) | Moteur d'expressions régulières Python pour tous les patterns |
| `json` (stdlib) | Chargement des règles PII depuis `data/manifests/pii_rules.json` |

---

### `src/privacy/policy.py`

**Rôle** : Moteur de politique de confidentialité. Évalue les 12 règles éducatives (EDU-001 à EDU-012) à chaque étape du pipeline.

**Architecture** : La classe `PrivacyPolicy` orchestre le `PIIDetector` et applique des règles métier à 8 points de contrôle du pipeline :

| Méthode | Point de contrôle | Règle(s) | Description |
|---|---|---|---|
| `evaluate_question()` | Entrée utilisateur | EDU-001, EDU-005, EDU-006 | Bloque les questions ciblant un individu |
| `evaluate_aggregation()` | Agrégation de données | EDU-003 | Suppression des petites cellules (effectif < k=10) |
| `evaluate_ingestion()` | Import de données | EDU-007 | Quarantaine si colonnes PII détectées |
| `evaluate_llm_prompt()` | Appel au LLM externe | — | Bloque les PII CRITICAL/HIGH dans les prompts |
| `evaluate_output()` | Réponse générée | EDU-003 | Bloque PII + petites cellules dans la sortie |
| `evaluate_log()` | Journalisation | — | Redacte les PII avant écriture en log |
| `evaluate_reidentification()` | Croisement de données | EDU-011 | Bloque si count < k ET dimensions >= 2 |
| `is_minor_context()` | Toute mention de mineur | EDU-012 | Détecte "N ans" (N < 18) sauf contexte agrégé |

**Algorithmes clés** :

1. **Small-cell suppression** (EDU-003) : toute valeur numérique 1 < v < k (k=10 par défaut) dans un objet d'agrégation est bloquée. Les clés `region`, `prefecture`, `school` sont ignorées (ce sont des labels, pas des effectifs).

2. **Re-identification check** (EDU-011) : si un croisement a un effectif < k ET au moins 2 dimensions de ventilation (ex: sexe + préfecture), le risque de ré-identification est trop élevé → suppression.

3. **Minor context detection** : regex `(\d{1,2}) ans` avec vérification < 18, mais exclut les contextes agrégés détectés par les mots "statistique", "national", "n=NNN", "agrégé", "cohorte".

**Cadre légal** : Loi togolaise n°2019-014 sur la protection des données personnelles.

**Bibliothèques** : `re` (stdlib), `json` (stdlib), `PIIDetector` (interne)

---

## 5. Ingestion — Crawlers

### `src/ingestion/crawlers/base.py`

**Rôle** : Classe de base abstraite pour tous les crawlers TogoQA. Fournit la logique commune de crawling web asynchrone.

**Architecture** :

```
BaseCrawler
├── MENCrawler      (education.gouv.tg)
├── INSEEDCrawler   (inseed.tg)
└── ExamCrawler     (résultats d'examens)
```

**Algorithme de crawling** : **BFS (Breadth-First Search)** avec file de priorité.

```
INITIALISER queue ← start_urls
INITIALISER visited ← {}

TANT QUE queue non vide ET |visited| < max_pages :
    url ← queue.pop(0)       # FIFO → BFS
    SI url ∈ visited : continuer
    visited.add(url)

    résultat ← crawl_page(url)
    résultat ← filter_result(résultat)   # hook subclass

    SI résultat est HTML :
        POUR CHAQUE lien extrait :
            SI lien est fichier téléchargeable :
                queue.insert(0, lien)   # priorité haute
            SINON :
                queue.append(lien)      # priorité normale
```

**Fonctionnalités** :

| Fonctionnalité | Implémentation |
|---|---|
| **Client HTTP async** | `httpx.AsyncClient` avec User-Agent identifié, suivi de redirections, timeout 30s |
| **Respect robots.txt** | `urllib.robotparser.RobotFileParser` : fetche et cache le robots.txt par domaine |
| **Allowlist de domaines** | Vérifie que l'URL cible est dans `allowed_domains` (inclut les sous-domaines) |
| **Rate limiting** | `asyncio.sleep(delay)` après chaque requête (défaut : 2s) |
| **SHA-256 checksum** | Calculé automatiquement sur `raw_content` via `hashlib.sha256()` |
| **Extraction métadonnées** | Depuis les balises HTML `<meta>` : title, description, author, published_at, keywords |
| **Extraction de liens** | Filtre les liens `#`, `javascript:`, `mailto:`, `tel:` ; résout les URLs relatives avec `urljoin()` |
| **Détection de fichiers** | Extensions téléchargeables : `.pdf`, `.xlsx`, `.xls`, `.csv`, `.docx` |
| **Hook de filtrage** | `filter_result()` : surchargeable par les sous-classes pour filtrer/enrichir |

**Dataclass `CrawlResult`** : contient url, title, content_type, raw_content (bytes), text, checksum, published_at, metadata, status_code.

**Bibliothèques** :
| Bibliothèque | Rôle |
|---|---|
| `httpx` | Client HTTP asynchrone (remplace requests pour l'async) |
| `beautifulsoup4` | Parsing HTML, extraction de texte et de liens |
| `asyncio` (stdlib) | Boucle événementielle, rate limiting |
| `hashlib` (stdlib) | Calcul SHA-256 des contenus téléchargés |
| `urllib.parse` (stdlib) | Résolution d'URLs relatives, parsing de domaines |
| `urllib.robotparser` (stdlib) | Parsing et respect du protocole robots.txt |

---

### `src/ingestion/crawlers/men.py`

**Rôle** : Crawler spécialisé pour le site du Ministère des Enseignements Primaire et Secondaire du Togo (education.gouv.tg).

**Configuration** :
- Domaines : `education.gouv.tg`, `www.education.gouv.tg`
- URLs de départ : `/`, `/actualites/`, `/communiques/`, `/statistiques/`
- Délai : 2.0s entre requêtes
- Pages max : 300

**Algorithmes spécifiques** :

1. **Filtre de pertinence éducative** : regex `EDUCATION_KEYWORDS` avec 18 termes-clés (examen, résultat, bac, bepc, cepd, scol, éducati, enseignant, élève, effectif, rentrée, inscription, formation, primaire, secondaire, statistique, annuaire, communiqué, arrêté, circulaire, réforme, curricul). Seules les pages contenant au moins un mot-clé sont conservées.

2. **Extraction de date en français** : regex sur les dates françaises (`15 septembre 2026`), conversion en ISO 8601 (`2026-09-15`) via un dictionnaire mois → numéro. Fallback sur la balise HTML `<time>`.

3. **Extraction de chiffres clés** : regex `([\d\s.,]+)\s*(%|élèves|enseignants|écoles|...)` pour capturer les données numériques contextuelles depuis les pages d'actualités et de statistiques.

**Bibliothèques** : hérite de `BaseCrawler` (httpx, beautifulsoup4, asyncio)

---

### `src/ingestion/crawlers/inseed.py`

**Rôle** : Crawler spécialisé pour l'Institut National de la Statistique (inseed.tg).

**Configuration** :
- Domaines : `inseed.tg`, `www.inseed.tg`
- URLs de départ : `/`, `/statistiques-sociales/`, `/publications/`, `/tableaux-de-bord/`
- Délai : 2.5s (plus conservateur)
- Pages max : 200

**Algorithmes spécifiques** :

1. **Filtre de pertinence** : regex `EDUCATION_SECTION_KEYWORDS` avec des termes liés à l'éducation et aux statistiques (éducati, scolai, enseign, alphabéti, annuaire, tableau.de.bord, indicateur, statistique, démographi, population.*âge.*scolaire).

2. **Extraction de métadonnées PDF depuis le nom de fichier** :
   - Année de référence : regex `(20[12]\d)` dans le nom du fichier
   - Année scolaire : regex `(20[12]\d)[-_](20[12]\d)` → format `2023-2024`
   - Type de document : détection par mots-clés dans le nom (annuaire, tableau + bord, rapport, enquête)

3. **Extraction de liens PDF** : `list_pdf_links()` scanne les `<a href>` pour trouver tous les liens `.pdf` et les résout en URLs absolues.

**Bibliothèques** : hérite de `BaseCrawler` (httpx, beautifulsoup4, asyncio)

---

### `src/ingestion/crawlers/exams.py`

**Rôle** : Crawler spécialisé pour l'extraction de statistiques d'examens nationaux (CEPD, BEPC, BAC I, BAC II) depuis les pages du MEN.

**Configuration** :
- Cible : pages contenant des résultats d'examens 2026
- URLs de départ : `/examens/`, `/resultats/`, `/actualites/`
- Pages max : 100

**Algorithmes spécifiques** :

1. **Filtre par examen et année** : regex `EXAM_PATTERN` détecte les mentions d'examens (CEPD, BEPC, BAC I/II/1/2). Le filtre vérifie que l'année cible (2026) ou l'année précédente apparaît dans le texte.

2. **Extraction contextuelle de statistiques** (`extract_exam_stats`) :
   - Pour chaque mention d'examen dans le texte HTML (via BeautifulSoup), ouvre une fenêtre de contexte [-50, +500] caractères autour de la mention
   - Extrait par regex dans ce contexte :
     - Nombre de candidats : `(\d[\d\s]*)\s*candidats?`
     - Taux de réussite : `taux de réussite\s*:\s*(\d+[.,]?\d*)\s*%`
     - Taux filles/garçons : `filles?\s*:\s*(\d+[.,]?\d*)\s*%` / `garçons?\s*:\s*(\d+[.,]?\d*)\s*%`
     - Centres : `(\d[\d\s]*)\s*centres?`

3. **Normalisation des noms d'examens** : BAC2/BACII → BAC_II, BAC1/BACI → BAC_I, suppression des espaces internes.

4. **Parsing numérique adapté au français** :
   - `_parse_int("1 204")` → 1204 (supprime les espaces insécables comme séparateurs de milliers)
   - `_parse_float("72,4")` → 72.4 (virgule française → point décimal)

5. **Déduplication** : par clé composite `(exam, year, region)` — conserve la première occurrence.

**Dataclass `ExamStats`** : exam, year, candidates_total, girls, boys, success_rate, success_rate_girls, success_rate_boys, centers, region, source_url.

**Bibliothèques** : hérite de `BaseCrawler` (httpx, beautifulsoup4), `re` (stdlib)

---

## 6. Ingestion — Téléchargement et stockage

### `src/ingestion/downloader.py`

**Rôle** : Téléchargement de documents de référence avec versionnement par checksum SHA-256 et manifeste JSON.

**Fonctionnement** :

```
1. Télécharger le document (httpx async, timeout 120s)
2. Calculer SHA-256 du contenu
3. Vérifier dans le manifeste si ce checksum existe déjà → skip si doublon
4. Déterminer la version (v1 si nouveau, vN+1 si mise à jour)
5. Sauvegarder le fichier : "rapport.pdf" (v1) ou "rapport_v2.pdf" (v2+)
6. Mettre à jour le manifeste JSON (data/downloads/manifest.json)
```

**Manifeste** (`manifest.json`) :
```json
{
  "documents": {
    "rapport.pdf": {
      "url": "https://...",
      "checksum": "sha256:...",
      "size": 1048576,
      "version": 1,
      "downloaded_at": "2026-09-03T00:00:00Z",
      "document_type": "rapport",
      "source_id": "MEPS"
    }
  },
  "last_updated": "2026-09-03T00:00:00Z"
}
```

**Catalogue de documents** (`REFERENCE_DOCUMENTS`) : liste prédéfinie des documents clés à télécharger :
- RSCE Togo 2025 (Revue Sectorielle Conjointe de l'Education)
- Annuaire national des statistiques scolaires 2023-2024

**Algorithme de déduplication** : parcours linéaire de tous les checksums du manifeste. Un fichier avec le même SHA-256 qu'un document existant est considéré comme doublon et ignoré.

**Bibliothèques** :
| Bibliothèque | Rôle |
|---|---|
| `httpx` | Client HTTP asynchrone pour le téléchargement |
| `hashlib` (stdlib) | SHA-256 pour l'intégrité et la déduplication |
| `json` (stdlib) | Sérialisation du manifeste de versionnement |

---

### `src/ingestion/storage.py`

**Rôle** : Gestion du stockage des documents bruts (PDF, HTML, CSV) dans MinIO (stockage objet S3-compatible).

**Architecture MinIO** :
- Bucket : `togoqa-documents`
- Organisation des objets : `source_id/year/filename` (ex: `meps/2025/rapport.pdf`)
- Chaque objet est stocké avec des métadonnées personnalisées : `sha256`, `source-url`, `uploaded-at`

**Fonctionnement de l'upload** :

```
1. Calculer SHA-256 du contenu
2. SI dedup activé :
   a. Parcourir les objets existants avec le même préfixe
   b. Comparer le checksum dans les métadonnées (x-amz-meta-sha256)
   c. Si match → retourner StorageResult avec is_duplicate=True
3. Créer le bucket si inexistant (ensure_bucket)
4. Upload via put_object() avec content-type détecté et métadonnées
5. Retourner StorageResult
```

**Détection de content-type** : mapping d'extensions vers types MIME (8 types supportés : html, pdf, csv, xlsx, xls, json, txt, docx). Fallback : `application/octet-stream`.

**Construction des chemins** : `build_object_name(source_id, filename, year)` → normalise le source_id en minuscules et construit un chemin structuré.

**Bibliothèques** :
| Bibliothèque | Rôle |
|---|---|
| `minio` | Client Python pour MinIO/S3 (import lazy pour tolérer l'absence en dev) |
| `hashlib` (stdlib) | SHA-256 pour intégrité et déduplication |
| `python-dotenv` | Variables de configuration MinIO depuis `.env` |

---

## 7. Ingestion — Orchestration

### `src/ingestion/celery_app.py`

**Rôle** : Configuration de l'application Celery pour les tâches asynchrones de crawling.

**Configuration** :
| Paramètre | Valeur | Description |
|---|---|---|
| Broker | Redis (`REDIS_URL`) | File de messages pour les tâches |
| Backend | Redis | Stockage des résultats de tâches |
| Sérialisation | JSON | Format d'échange des messages |
| Timezone | `Africa/Lome` (UTC+0) | Fuseau horaire du Togo |
| `task_acks_late` | True | ACK après exécution (tolérance aux pannes) |
| `worker_prefetch_multiplier` | 1 | Un message à la fois par worker (crawling séquentiel) |

**Beat Schedule** (planificateur périodique) :
| Nom | Tâche | Intervalle | Queue |
|---|---|---|---|
| `crawl-men-daily` | `crawl_men` | 86400s (24h) | `crawl` |
| `crawl-inseed-weekly` | `crawl_inseed` | 604800s (7j) | `crawl` |
| `crawl-exams-daily` | `crawl_exams` | 86400s (24h) | `crawl` |

**Bibliothèques** :
| Bibliothèque | Rôle |
|---|---|
| `celery` | Framework de tâches asynchrones distribuées |
| `redis` | Broker de messages (via Celery) |
| `python-dotenv` | Configuration depuis `.env` |

---

### `src/ingestion/tasks.py`

**Rôle** : Définition des 3 tâches Celery pour le crawling automatisé.

**Tâches** :

| Tâche | Crawler | Retry | Countdown |
|---|---|---|---|
| `crawl_men` | MENCrawler | 2 max | 300s (5 min) |
| `crawl_inseed` | INSEEDCrawler | 2 max | 600s (10 min) |
| `crawl_exams` | ExamCrawler + extraction stats | 2 max | 300s (5 min) |

**Pont async → sync** :

Les crawlers sont asynchrones (`async/await` avec httpx), mais Celery est synchrone. Le wrapper `_run_async(coro)` crée une boucle événementielle dédiée :

```python
def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

**Retours** : chaque tâche retourne un dict JSON avec status, nombre de résultats, et timestamp.

**Gestion des erreurs** : retry automatique via `self.retry(exc=exc, countdown=N)`. Celery relance la tâche après le délai spécifié, jusqu'à `max_retries`.

**Bibliothèques** : `celery` (décorateur `@app.task`), `asyncio` (stdlib), imports lazy des crawlers (évite les imports circulaires)

---

## 8. Manifestes de données

### `data/manifests/indicators.json`

**Rôle** : Fichier de référence contenant les 122 indicateurs éducatifs répartis en 16 catégories.

**Structure** :
```json
{
  "version": "1.0",
  "indicators": [
    {
      "code": "candidates_total",
      "label": "Candidats inscrits",
      "definition": "Nombre total de candidats...",
      "unit": "nombre",
      "aliases": ["nombre de candidats", "inscrits"],
      "category": "Examens nationaux",
      "dimensions": ["exam", "year", "sex", "region"],
      "value_type": "count",
      "formula": null,
      "source_hints": ["MEPS", "INSEED"],
      "notes": null
    }
  ]
}
```

**Catégories** (16) : Examens nationaux, Effectifs scolaires, Scolarisation, Accès et admission, Transition, Achèvement, Redoublement et abandon, Parité et équité, Enseignants, Établissements, Infrastructures, Enseignement technique, Enseignement supérieur, Alphabétisation, Financement, Comparaisons internationales.

### `data/manifests/pii_rules.json`

**Rôle** : Configuration du système de protection des données personnelles.

**Contenu** :
- **28 types de PII** avec code, label, description, niveau de risque (LOW/MEDIUM/HIGH/CRITICAL), action par défaut
- **12 règles éducatives** (EDU-001 à EDU-012) avec conditions d'application et actions
- **8 actions possibles** : allow, block, redact, quarantine_and_review, refuse_or_redirect, suppress_or_coarsen, block_and_regenerate, allow_if_public_and_relevant
- **Tokens de redaction** : mapping type_PII → token (ex: phone_number → `[TELEPHONE]`)
- **Politique globale** : min_group_size_for_public_aggregate = 10

### `data/manifests/pii_tests.json`

**Rôle** : Suite de 52 cas de test pour valider le système PII.

**Structure** : 11 couches de test couvrant le pipeline complet :
1. `detector` — Détection regex des PII directs
2. `false_positive` — Vérification des faux positifs (texte sûr)
3. `aggregation` — Small-cell suppression
4. `question_policy` — Filtrage des questions utilisateur
5. `ingestion` — Quarantaine des colonnes PII
6. `external_llm` — Blocage PII dans les prompts LLM
7. `output_guard` — Blocage PII dans les réponses générées
8. `logging` — Redaction des logs
9. `reidentification` — Risque de ré-identification
10. `citation` — PII dans les citations de source
11. `minor_policy` — Protection des mineurs

**Critères d'acceptation** :
- Recall PII CRITICAL : ≥ 0.99
- Recall PII HIGH : ≥ 0.97
- Taux de faux positifs : ≤ 0.03
- Tolérance zéro : fuites de secrets, résultats individuels, petites cellules

---

## 9. Tests

### `tests/unit/test_pii.py`

**Rôle** : 56 tests couvrant les 11 couches du système PII.

**Couverture** :
| Couche | Nombre de tests | Validation |
|---|---|---|
| Détection regex | 8 | Téléphone, email, matricule, candidat, date de naissance, géoloc, mot de passe, score |
| Faux positifs | 4 | Texte agrégé sûr, pourcentages, noms d'établissements, numéros non-PII |
| Agrégation | 3 | Small-cell (< 10), effectifs suffisants (≥ 10), données agrégées |
| Questions | 5 | Résultat individuel, question générique, responsable public, liste de noms |
| Ingestion | 3 | Colonnes PII, colonnes sûres, mix |
| LLM externe | 3 | PII CRITICAL/HIGH dans prompt, prompt propre |
| Sortie | 5 | PII dans réponse, petites cellules, réponse propre |
| Logging | 3 | Redaction email, téléphone, texte propre |
| Ré-identification | 3 | Croisement risqué, effectif suffisant, dimension unique |
| Citation | 3 | PII dans citation, citation propre |
| Mineurs | 4 | Mineur identifiable, contexte agrégé, adulte |

**Bibliothèque** : `pytest`

### `tests/unit/test_crawlers.py`

**Rôle** : 19 tests pour les crawlers Base, MEN et INSEED.

**Couverture** :
| Crawler | Tests | Validation |
|---|---|---|
| BaseCrawler | 7 | User-Agent, domaine allowlist, sous-domaines, liens, métadonnées HTML, fichiers téléchargeables, hash SHA-256 |
| MENCrawler | 6 | Configuration par défaut, filtre pertinence, date française, chiffres clés, pages hors-sujet |
| INSEEDCrawler | 6 | Configuration par défaut, filtre pertinence, métadonnées PDF, liens PDF, pages hors-sujet |

**Bibliothèque** : `pytest`

### `tests/unit/test_ingestion.py`

**Rôle** : 23 tests pour le downloader, l'exam crawler, le stockage MinIO et la config Celery.

**Couverture** :
| Module | Tests | Validation |
|---|---|---|
| DocumentDownloader | 7 | Checksum SHA-256, manifeste roundtrip, détection doublons, versionnement, DownloadEntry, catalogue REFERENCE_DOCUMENTS |
| ExamCrawler | 9 | Normalisation noms examens, parsing int/float français, filtre pertinence, filtre année, extraction statistiques, déduplication |
| MinIOStorage | 3 | Checksum, content-type, construction chemins objets |
| Celery config | 4 | App configurée, schedule quotidien MEN, schedule hebdomadaire INSEED, tâches importables |

**Bibliothèque** : `pytest`, `hashlib` (stdlib), `tempfile` (stdlib)

---

## Récapitulatif des bibliothèques

| Bibliothèque | Version | Utilisée dans | Rôle |
|---|---|---|---|
| **SQLAlchemy** | 2.x | db.py, models.py, seeds | ORM, moteur SQL, API déclarative 2.0 |
| **psycopg** | 3.x | db.py (via SQLAlchemy) | Driver PostgreSQL natif |
| **pgvector** | — | models.py | Type Vector pour embeddings dans PostgreSQL |
| **Alembic** | — | migrations/ | Gestion de migrations de schéma |
| **httpx** | — | crawlers, downloader | Client HTTP asynchrone |
| **BeautifulSoup4** | — | crawlers | Parsing HTML, extraction texte/liens |
| **Celery** | 5.x | celery_app.py, tasks.py | Tâches asynchrones distribuées |
| **Redis** | — | celery_app.py | Broker Celery |
| **MinIO** | — | storage.py | Client S3 pour stockage objet |
| **python-dotenv** | — | partout | Chargement des `.env` |
| **pytest** | — | tests/ | Framework de tests |

### Bibliothèques standard Python utilisées

| Module | Utilisé dans | Rôle |
|---|---|---|
| `re` | detector.py, policy.py, crawlers | Expressions régulières (PII, filtres, extraction) |
| `hashlib` | base.py, downloader.py, storage.py | SHA-256 (intégrité, déduplication) |
| `asyncio` | tasks.py, crawlers | Boucle événementielle async |
| `json` | detector.py, seeds, downloader.py | Chargement/sauvegarde de manifestes |
| `urllib.parse` | base.py | Résolution URLs, parsing domaines |
| `urllib.robotparser` | base.py | Respect du protocole robots.txt |
| `dataclasses` | tous les modules | Dataclasses pour les structures de données |
| `os` / `pathlib` | partout | Chemins de fichiers, variables d'environnement |
