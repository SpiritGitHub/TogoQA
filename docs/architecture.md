# Architecture — TogoQA-Éducation

## Vue d'ensemble

TogoQA suit une architecture modulaire en couches. Chaque composant est indépendant et testable isolément.

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend React                         │
│              (Interface publique + Mode chercheur)           │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / JSON
┌────────────────────────▼────────────────────────────────────┐
│                      FastAPI                                 │
│    /api/v1/ask  /api/v1/sources  /api/v1/documents  /health │
└───┬─────────┬──────────┬─────────────┬──────────────────────┘
    │         │          │             │
    ▼         ▼          ▼             ▼
┌───────┐ ┌───────┐ ┌────────┐ ┌──────────┐
│Moteur │ │Celery │ │ MinIO  │ │ MLflow   │
│TogoQA │ │Workers│ │(S3)    │ │(tracking)│
└───┬───┘ └───┬───┘ └────────┘ └──────────┘
    │         │
    ▼         ▼
┌─────────────────────────┐  ┌─────────┐
│   PostgreSQL + pgvector  │  │  Redis   │
│ (données + embeddings)   │  │ (broker) │
└─────────────────────────┘  └─────────┘
```

## Composants principaux

### 1. Frontend (`apps/web/`)

Interface React (sans TypeScript) avec Vite et Tailwind CSS.

Deux modes :
- **Interface publique** : barre de question, filtres, réponse avec badge de confiance et sources cliquables.
- **Mode chercheur** : panneaux de debug (query parser, retrieval trace, evidence graph, confidence details, benchmark mode).

### 2. API (`apps/api/`)

FastAPI orchestre les requêtes entre le frontend et le moteur TogoQA.

Endpoints principaux :
| Endpoint | Méthode | Rôle |
|----------|---------|------|
| `/api/v1/ask` | POST | Poser une question |
| `/api/v1/sources` | GET | Lister les sources |
| `/api/v1/documents` | GET | Lister les documents |
| `/api/v1/documents/{id}` | GET | Détails d'un document |
| `/api/v1/health` | GET | Santé des services |
| `/api/v1/benchmark/run` | POST | Lancer le benchmark |

### 3. Moteur TogoQA (`src/`)

Le coeur du système, organisé en modules :

#### Ingestion (`src/ingestion/`)
- **Crawlers** : récupèrent les documents depuis les sites officiels (MEN, INSEED, UNESCO, etc.)
- **Parsers** : extraient texte, métadonnées et tableaux depuis HTML et PDF
- **Qualité** : 6 contrôles automatiques avant insertion

#### Retrieval (`src/retrieval/`)
- **Lexical** : recherche full-text PostgreSQL (tsvector, français)
- **Vector** : recherche de similarité via pgvector (embeddings bge-m3, dim 1024)
- **Fusion** : Reciprocal Rank Fusion (RRF) pour combiner les résultats
- **Reranker** : bge-reranker-v2-m3 pour réordonner les candidats

#### Raisonnement (`src/reasoning/`)
- **Temporal** : logique de comparaison entre périodes et années scolaires
- **Numeric** : calculs vérifiés (différences, taux, pourcentages)
- **Contradictions** : détection et classification des divergences entre sources

#### Answerability (`src/answerability/`)
- **Features** : extraction des 10 features de confiance (A, R, E, C, G, T, N, V, X, Q)
- **Classifier** : prédiction FULL / PARTIAL / NONE

#### Vérification (`src/verification/`)
- **Decompose** : décomposition des réponses en claims atomiques
- **NLI** : vérification de chaque claim par Natural Language Inference (mDeBERTa-v3)

#### Confiance (`src/confidence/`)
- **Calibrator** : calibration du score de confiance (régression isotonique / Platt)
- **Policy** : application de la politique ANSWER / PARTIAL / ABSTAIN

#### Génération (`src/generation/`)
- **LLM** : interface fournisseur-agnostique vers le modèle de génération (Qwen3-8B local)

### 4. Base de données

PostgreSQL 16 avec l'extension pgvector pour le stockage vectoriel.

Trois types de données :
1. **Métadonnées** : sources, documents, indicateurs, établissements
2. **Contenu** : chunks de texte avec embeddings et index full-text
3. **Observations** : valeurs numériques structurées pour les calculs

### 5. Services auxiliaires

- **Redis** : broker pour Celery (jobs asynchrones de crawling et parsing)
- **MinIO** : stockage S3-compatible pour les documents bruts (PDF, HTML)
- **MLflow** : tracking des expériences et versions de modèles
- **Celery** : exécution asynchrone des crawlers et pipelines de parsing

## Pipeline d'une question

```
1.  parse_query(question)
    → intent, niveau scolaire, période, région, métrique

2.  retrieve_structured(filters)     ─┐
    retrieve_lexical(question)        ├─► fuse_results(RRF)
    retrieve_vector(question)        ─┘

3.  rerank(candidates) → top evidence

4.  build_evidence_graph(evidence)

5.  predict_answerability(question, evidence)
    → FULL / PARTIAL / NONE

6.  Si NONE → ABSTAIN immédiat

7.  generate_claims(question, evidence, tool_results)
    → réponse + claims atomiques

8.  verify_each_claim(claims, evidence)
    → NLI + vérification numérique

9.  calibrate_confidence(features)
    → score calibré p ∈ [0, 1]

10. policy(p)
    → ANSWER (p ≥ 0.82) / PARTIAL (0.60 ≤ p < 0.82) / ABSTAIN (p < 0.60)

11. return {answer, sources, confidence, trace}
```

## Score de confiance

10 features combinées :

| Feature | Code | Poids | Description |
|---------|------|-------|-------------|
| Authority | A | 0.14 | Score d'autorité moyen des sources |
| Retrieval | R | 0.15 | Score de retrieval du meilleur document |
| Entailment | E | 0.20 | Probabilité NLI d'implication |
| Coverage | C | 0.17 | Couverture des claims par les preuves |
| Agreement | G | 0.10 | Accord entre sources multiples |
| Temporal fit | T | 0.08 | Adéquation temporelle question/preuve |
| Numeric | N | 0.06 | Cohérence des calculs numériques |
| Version/status | V | 0.10 | Fiabilité de la version du document |
| Contradiction | X | -0.18 | Pénalité pour contradictions détectées |
| Query ambiguity | Q | -0.08 | Pénalité pour ambiguïté de la question |

Formule heuristique initiale :
```
z = 0.14A + 0.15R + 0.20E + 0.17C + 0.10G + 0.08T + 0.06N + 0.10V − 0.18X − 0.08Q
p = σ(z)  (sigmoïde)
```

Le calibrateur (isotonique ou Platt) remplace cette heuristique après la semaine 9.

## Politique de décision

| Décision | Condition | Comportement |
|----------|-----------|--------------|
| **ANSWER** | p ≥ 0.82, coverage ≥ 0.85, pas de contradiction critique | Réponse complète avec sources |
| **PARTIAL** | 0.60 ≤ p < 0.82 | Réponse partielle, lacunes signalées |
| **ABSTAIN** | p < 0.60 ou preuve critique absente | Refus explicite, explication |

## Modèles IA

| Composant | Modèle | Utilisation |
|-----------|--------|-------------|
| Embeddings | BAAI/bge-m3 | Encoder questions et chunks (dim 1024) |
| Reranker | BAAI/bge-reranker-v2-m3 | Réordonner les candidats retrieval |
| Générateur | Qwen3-8B | Produire réponses et claims atomiques |
| Vérificateur | mDeBERTa-v3 multilingual | NLI pour vérifier chaque claim |

Tous les modèles tournent en local pour la reproductibilité.
