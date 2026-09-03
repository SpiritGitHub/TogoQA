# TogoQA - Éducation

Système de question-réponse fiable, vérifiable et conscient de son incertitude sur les données éducatives du Togo.

## Principe

> **Répondre quand les preuves suffisent, s'abstenir quand elles ne suffisent pas.**

TogoQA permet de poser une question en langage naturel sur l'éducation au Togo et d'obtenir :
- Une réponse synthétique avec citations vérifiables
- Un score de confiance calibré
- Les sources officielles utilisées avec page et passage
- Un refus explicite lorsque les preuves sont insuffisantes

## Domaine

Le système couvre l'ensemble du domaine éducatif togolais :
- Examens nationaux (CEPD, BEPC, BAC I, BAC II)
- Effectifs scolaires et enseignants
- Établissements et infrastructures
- Indicateurs (accès, transition, achèvement, redoublement, abandon)
- Politiques éducatives et textes juridiques
- Enseignement technique, professionnel et supérieur
- Alphabétisation et éducation non-formelle
- Budget et financement de l'éducation

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Frontend | React + Vite + Tailwind |
| API | FastAPI + Pydantic |
| Base de données | PostgreSQL + pgvector |
| Recherche | FTS + recherche vectorielle + reranking |
| Object storage | MinIO |
| Jobs | Celery + Redis |
| Packaging | Docker Compose |

## Démarrage rapide

```bash
cp .env.example .env
docker compose up -d
```

## Structure du projet

```
togoqa/
├── apps/api/          # FastAPI backend
├── apps/web/          # React frontend
├── src/ingestion/     # Crawlers, parsers, extraction de tableaux
├── src/retrieval/     # FTS, vector, fusion, reranking
├── src/reasoning/     # Raisonnement temporel, numérique, contradictions
├── src/answerability/ # Classificateur + features
├── src/verification/  # Décomposition en claims + NLI
├── src/confidence/    # Calibration + politique de décision
├── src/generation/    # Adaptateur LLM
├── data/              # Manifests, schémas, benchmark
├── tests/             # Unit, integration, benchmark
└── docker/            # Dockerfiles
```

## Licence

MIT
