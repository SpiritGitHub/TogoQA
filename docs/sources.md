# Sources de données — TogoQA-Éducation

## Système de tiers d'autorité

Chaque source dans TogoQA est classée par un **tier d'autorité** qui détermine le poids qu'elle a dans le calcul de confiance et les conditions dans lesquelles elle peut servir de preuve.

| Tier | Score | Catégorie | Peut servir de preuve finale ? |
|------|-------|-----------|-------------------------------|
| **A+** | 1.00 | Texte juridique officiel | Oui, toujours |
| **A** | 0.95 | Statistique officielle / portail gouvernemental | Oui |
| **B+** | 0.85 | Organisation internationale avec méthodologie | Oui |
| **B** | 0.75 | Presse publique | Oui |
| **C** | 0.55 | Presse privée identifiée | Seulement si corroborée par A/A+/B+ |
| **D** | ≤0.20 | Non vérifiée | Non, jamais |

### Règles de corroboration

- Les sources **C** ne peuvent justifier une réponse factuelle que si au moins une source **A**, **A+** ou **B+** confirme la même information.
- Les sources **D** ne sont jamais utilisées comme preuve finale. Elles peuvent être mentionnées comme information complémentaire, mais ne contribuent pas au score de confiance.
- Lorsqu'une information n'est disponible que via des sources C sans corroboration, la décision est **ABSTAIN**.

---

## Inventaire des 29 sources

### Tier A+ — Texte juridique officiel (score: 1.00)

| # | Nom | URL | Propriétaire | Périmètre |
|---|-----|-----|-------------|-----------|
| 1 | Journal Officiel de la République Togolaise | https://jo.gouv.tg/ | République Togolaise | Lois, décrets, arrêtés et textes officiels sur l'éducation |
| 2 | LégiTogo | https://legitogo.gouv.tg/ | République Togolaise | Base juridique de lois, décrets et arrêtés togolais |

### Tier A — Statistique officielle / administration (score: 0.95)

| # | Nom | URL | Propriétaire | Périmètre |
|---|-----|-----|-------------|-----------|
| 3 | INSEED | https://inseed.tg/ | Institut National de la Statistique | Annuaires scolaires, tableaux de bord, indicateurs, démographie scolaire |
| 4 | Open Data Togo | https://data.gouv.tg/ | République Togolaise | Jeux de données publics réutilisables, métadonnées et séries structurées |
| 5 | Ministère des Enseignements Primaire et Secondaire | https://education.gouv.tg/ | MEN | Examens, effectifs, établissements, réformes, communiqués |
| 6 | Ministère de l'Enseignement Supérieur et de la Recherche | https://ens-superieur.gouv.tg/ | MESR | Universités, enseignement supérieur, recherche, concours |
| 7 | Ministère de l'Enseignement Technique et de la Formation Professionnelle | https://ens-technique.gouv.tg/ | METFP | Formation professionnelle, établissements techniques, concours |
| 8 | Ministère de l'Action Sociale et de l'Alphabétisation | https://action-sociale.gouv.tg/ | MASA | Alphabétisation, éducation non-formelle et programmes connexes |
| 9 | Ministère de la Planification | https://planification.gouv.tg/ | Ministère de la Planification | PND, documents transversaux et éléments statistiques liés à l'INSEED |
| 10 | Présidence / Primature | https://presidence.gouv.tg/ | Présidence de la République | Conseils des ministres, décisions et annonces gouvernementales |
| 11 | Portail officiel du Togo | https://togo.gouv.tg/ | République Togolaise | Actualités officielles et renvois vers les institutions publiques |
| 12 | Service Public Togo | https://service-public.gouv.tg/ | République Togolaise | Démarches administratives liées à l'éducation et procédures |

### Tier B+ — Organisations internationales (score: 0.85)

| # | Nom | URL | Propriétaire | Périmètre |
|---|-----|-----|-------------|-----------|
| 13 | UNESCO UIS | https://uis.unesco.org/ | UNESCO | Indicateurs ODD4, scolarisation, apprentissage et séries harmonisées |
| 14 | UNESCO-IIPE / Planipolis | https://planipolis.iiep.unesco.org/ | UNESCO-IIPE | RESEN, plans sectoriels et documents de politique éducative |
| 15 | UNICEF Togo | https://www.unicef.org/togo/ | UNICEF | Équité, genre, apprentissage, environnement scolaire |
| 16 | Banque mondiale | https://data.worldbank.org/ | Banque mondiale | Indicateurs éducation, dépenses, scolarisation et séries harmonisées |
| 17 | BAD | https://afdb.org/ | Banque Africaine de Développement | Projets et financements liés à l'éducation et à la formation |
| 18 | BCEAO | https://bceao.int/ | BCEAO | Contexte macroéconomique et financement public, dépenses d'éducation |
| 19 | FMI | https://imf.org/en/Countries/TGO | Fonds Monétaire International | Cadrage budgétaire et dépenses publiques agrégées |
| 20 | PASEC / CONFEMEN | https://pasec.confemen.org/ | CONFEMEN | Évaluations régionales des acquis scolaires du primaire |
| 21 | Partenariat Mondial pour l'Éducation | https://globalpartnership.org/ | GPE | Financement et suivi du plan sectoriel de l'éducation |

### Tier B — Presse publique (score: 0.75)

| # | Nom | URL | Propriétaire | Périmètre |
|---|-----|-----|-------------|-----------|
| 22 | ATOP | https://atop.tg/ | Agence Togolaise de Presse | Dépêches nationales, annonces, événements éducatifs |
| 23 | Togo Presse / Editogo | https://editogo.tg/ | Editogo | Quotidien national de service public |

### Tier C — Presse privée (score: 0.55, corroboration obligatoire)

| # | Nom | URL | Propriétaire | Périmètre |
|---|-----|-----|-------------|-----------|
| 24 | Togo First | https://togofirst.com/ | Togo First | Actualité économie/gouvernance et informations sectorielles |
| 25 | Republic of Togo | https://republicoftogo.com/ | Republic of Togo | Actualité togolaise généraliste |
| 26 | Icilome | https://icilome.com/ | Icilome | Actualité togolaise généraliste |
| 27 | Liberté | https://liberte-togo.com/ | Liberté | Presse privée nationale |
| 28 | L'Alternative | https://lalternative.tg/ | L'Alternative | Média privé d'investigation |
| 29 | Fraternité | https://fraternite-info.com/ | Fraternité | Hebdomadaire privé |

---

## Ajouter une nouvelle source

1. Insérer la source dans la table `sources` avec le tier d'autorité approprié.
2. Créer un crawler dédié dans `src/ingestion/crawlers/`.
3. Ajouter la source au manifest dans `data/manifests/`.
4. Mettre à jour les tests d'intégration.

```sql
INSERT INTO sources (name, base_url, authority_tier, authority_score,
    category, source_owner, thematic_scope, update_frequency, corroboration_required)
VALUES ('Nouvelle Source', 'https://example.com/', 'B+', 0.85,
    'Organisation internationale', 'Propriétaire', 'Périmètre thématique',
    'Annuel', FALSE);
```

---

## Règles PII

Les sources sont crawlées en respectant les règles de confidentialité :

**Interdit :**
- Noms d'élèves, d'enseignants ou de personnel
- Numéros de table / matricules
- Résultats individuels de candidats
- Données personnelles
- Adresses personnelles, téléphones, photos

**Autorisé :**
- Statistiques agrégées
- Documents publics officiels
- Noms d'établissements (entités publiques)
- Noms de responsables gouvernementaux cités dans les textes officiels
