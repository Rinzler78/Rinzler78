# PRD-001 — Profile V1 : data-driven, bilingue, adaptatif, gouverné

> Statut : ready-for-agent
> Date : 2026-05-27
> Liens : [ADR-001](../adr/0001-data-driven-svg-generation.md), [ADR-002](../adr/0002-tech-score-derivation.md), [ADR-003](../adr/0003-data-schema-collections-and-derived-views.md), [ADR-004](../adr/0004-i18n-bilingual-readme.md), [ADR-005](../adr/0005-quality-gates-ci-branch-protection.md)

## Problem Statement

Boris est freelance CTO/architecte logiciel ciblant à la fois des startups, scaleups et entreprises matures, en France et à l'international. Son profil GitHub actuel (`Rinzler78/Rinzler78`) est un README data-driven (ADR-001) mais limité : mono-langue FR, schéma data simple (3 paliers Tech sans dérivation), mode visuel unique non adaptatif au thème GitHub du visiteur, pas de catalogue de services structuré, pas de tests, pre-commit shell custom non aligné sur les règles de qualité standards, pas de protection de branche.

Sans évolution, le profil :
- coupe le marché EN-only (recruteurs anglophones, clients internationaux qui ne basculent pas la langue) ;
- ne distingue pas « livré en prod » de « bidouillé en proto », ce qui floute le signal de séniorité ;
- ne montre pas l'offre commerciale (services vendables) à un prospect qui scanne 30 secondes ;
- jure visuellement avec le mode GitHub light/dark choisi par le visiteur ;
- ne prouve pas la méthode de travail (tests, CI, gouvernance) qu'un client CTO chercherait à valider.

## Solution

Refondre le repo `Rinzler78/Rinzler78` comme un **GitHub Profile Generator** : un projet logiciel à part entière, gouverné comme tel, qui prend en entrée des données JSON normalisées et produit en sortie deux README (FR + EN), des assets SVG en double variante (dark + light) servis via `<picture>` selon la préférence du visiteur, et un ensemble d'animations dynamiques sobres. Le pipeline est testé (couverture ≥ 90%), valide les schémas, vérifie l'intégrité référentielle, traduit via DeepL avec cache committé, et tourne sous CI GitHub Actions avec `main` protégée par ruleset.

Le profil V1 démontre simultanément deux choses : (1) qui est Boris et ce qu'on peut lui acheter, (2) comment Boris construit du logiciel — le repo lui-même étant la preuve.

## User Stories

### Visiteur du profil

1. En tant que recruteur anglophone qui visite `github.com/Rinzler78`, je vois immédiatement un lien vers la version EN du README, afin de basculer sans avoir à comprendre le FR.
2. En tant que client potentiel français, je lis un pitch FR clair en haut du profil, afin de saisir l'offre de Boris en 10 secondes.
3. En tant que client en GitHub Dark Mode, les SVG embarqués apparaissent en variante sombre cohérente avec le reste de la page, afin que la lecture soit confortable.
4. En tant que client en GitHub Light Mode, les SVG embarqués apparaissent en variante claire WCAG AA, afin que la lecture soit confortable.
5. En tant que prospect scannant en 30 secondes, je vois en premier les **services vendables** (Architecture, Audit, AI-Driven Dev, etc.) avant les détails techniques, afin de savoir ce que je peux acheter.
6. En tant que prospect, je vois également les **modes d'intervention** (pompier, accompagnement long, audit one-shot, mentor) pour comprendre comment engager Boris.
7. En tant que CTO en évaluation, je consulte les niveaux de maîtrise des technos avec un score défendable (dérivé, pas arbitraire), afin de valider l'expertise réelle de Boris.
8. En tant que CTO en évaluation, je distingue clairement les technos `expert` (utilisées en prod critique), `advanced` (autonome en prod), `professional` (usage prod non central), `working` (proto livré), `explored` (veille), afin de calibrer mes attentes.
9. En tant que visiteur curieux, je consulte une timeline visuelle du parcours qui mêle premier code (2006), diplômes, postes successifs et jalons techniques, afin de comprendre la trajectoire de Boris.
10. En tant que visiteur, je vois les projets featured regroupés par domaine avec une explication du « pourquoi ce projet compte », afin de comprendre la valeur de ce qui est en repo public.
11. En tant que recruteur, je consulte la section « How I work » qui formalise les principes de travail (Simple before clever, Tested before trusted, etc.), afin de juger la philosophie d'ingénierie.
12. En tant que visiteur, je vois le « Profile as Code » (snippet C# inspiré qui présente Boris comme un objet), pour le clin d'œil dev et le signal geek.
13. En tant que client B2B, je vois en bas un bloc contact pyramidal (résumé en hero rappelé + détail complet avec email, LinkedIn, Malt, etc.), afin de prendre contact rapidement.
14. En tant que visiteur, je distingue le « ton humain » via les easter eggs `~bashrc` collapsibles (basketball, papa) qui personnalisent sans casser le sérieux pro.

### Boris (utilisateur du système)

15. En tant que Boris, je saisis ou modifie un fait dans `data/*.json` et je commit ; le pipeline régénère automatiquement tous les artefacts (SVG, README FR, README EN) dans le même commit, afin d'éviter toute désynchronisation entre data et rendu.
16. En tant que Boris, je saisis uniquement la version FR des champs narratifs ; DeepL produit automatiquement la version EN au pre-commit, afin de ne pas doubler l'effort éditorial.
17. En tant que Boris, je peux overrider manuellement une traduction EN (flag `manual: true` dans le cache), afin de corriger un cas où DeepL a mal traduit.
18. En tant que Boris, je sais quelles traductions EN n'ont pas encore été reviewées (flag `reviewed: false`) car le hook affiche un warning, afin de savoir où porter mon attention.
19. En tant que Boris, je peux overrider le score ou le level d'une tech (`score_override`, `level_override`) quand la formule sous-évalue (par ex. usage privé non listé), afin de garder un signal honnête sans tricher.
20. En tant que Boris, j'ai un Makefile avec des cibles claires (`make setup`, `make test`, `make check`), afin d'agir sans mémoriser les commandes longues.
21. En tant que Boris, je commit sur `main` ne passe pas : je dois ouvrir une PR. Cela force la traçabilité et la CI complète, afin d'éviter les écrasements accidentels.
22. En tant que Boris, mes commits sont signés GPG (déjà mon usage standard), et `main` rejette tout commit non signé, afin de prouver l'authenticité.
23. En tant que Boris, je vois en local toutes les erreurs de schéma, lint, sécurité, audit deps, traduction manquante AVANT de pousser, grâce à pre-commit + pre-push, afin de ne pas dépendre de la CI pour les retours.
24. En tant que Boris, le workflow `update-profile.yml` tourne tous les lundis matin, récupère les métriques GitHub publiques et commit s'il y a un diff, afin que le profil reste à jour sans intervention.
25. En tant que Boris, j'ajoute une nouvelle tech, projet ou service en éditant un seul fichier `data/*.json` ; le radar, les barres, les sections du README, la version EN se mettent à jour automatiquement.
26. En tant que Boris, je peux changer la palette ou le thème en éditant `data/themes.json` et `data/config.json`, sans toucher aux templates, afin de tester des variantes sans risquer de casser le rendu.
27. En tant que Boris, le coût DeepL reste à 0€ (free tier 500k chars/mois) tant que je ne dépasse pas le quota, afin de garder la solution autofinancée.
28. En tant que Boris, si DeepL est indisponible ou la clé absente, le hook échoue clairement (pas de fallback silencieux), afin que je sache que la trad EN n'a pas été produite.
29. En tant que Boris, je teste mes modifications data via `make test` et `make coverage` (≥ 90%), afin de garantir que la formule de score et les vues dérivées restent cohérentes.
30. En tant que Boris, je consulte les ADRs (`docs/adr/`) pour comprendre pourquoi telle décision a été prise, afin de faire évoluer le système sans rejouer les débats passés.
31. En tant que Boris, je peux ajouter un nouveau thème (par exemple `solarized`) en créant une entrée dans `data/themes.json` et en pointant `data/config.json` dessus, afin de pivoter le design sans refonte.

### Mainteneur futur / contributeur ouvert

32. En tant que mainteneur futur du repo (ou agent autonome), je trouve dans `CONTEXT.md` un glossaire complet du vocabulaire data, afin de comprendre les concepts sans lire le code.
33. En tant que mainteneur, je trouve dans `docs/adr/` les décisions structurantes datées et motivées, afin de savoir quoi modifier ou superseder.
34. En tant que contributeur, je clone le repo, je lance `make setup`, et tout est installé (deps, pre-commit, pre-push) en une commande, afin de démarrer en moins de 5 minutes.

## Implementation Decisions

### Modules à construire / modifier

Le pipeline est éclaté en modules deep encapsulant chacun une responsabilité testable en isolation. Tous ont des tests dédiés (validation Q16).

- **DataLoader** : charge `data/*.json`, valide chaque fichier contre son JSON Schema, vérifie l'intégrité référentielle (chaque FK pointe sur une entité existante), résout le profil et le thème actif via `data/config.json`. Interface : `load() → typed entities`. Exposera une exception structurée par catégorie d'erreur (schema, FK, missing required field).
- **ScoreEngine** : implémente la formule ADR-002. Inputs : une `Tech`, la collection `Projects`, la date courante. Outputs : `(score: int, level: enum)`. Applique les overrides (`score_override`, `level_override`) en vérifiant leur cohérence (override level doit tomber dans la fourchette du score override si les deux posés). Fonction pure, déterministe, sans I/O.
- **ViewBuilder** : construit les vues dérivées à partir des entités chargées. Exposera des fonctions séparées pour `build_skills`, `build_experience`, `build_education`, `build_tech_radar`, `build_core_expertise`, `build_featured_projects`, `build_stack_by_domain`, `build_parcours_story`. Chaque vue est un view model immutable.
- **I18nTranslator** : gère le cycle traduction. Lit/écrit `data/i18n-cache/<entity>/<id>.<field>.en.json`. Calcule le hash SHA-256 du FR, détecte les besoins de retraduction, appelle l'API DeepL via le client officiel, respecte `manual: true` (jamais retraduit) et `reviewed: false` (warning seulement). Interface : `translate(entity, id, field, fr) → en`. Mockable en test.
- **ThemeResolver** : résout le thème actif depuis `config.json` et `themes.json`. Pour le thème actif, expose deux palettes : `dark` (saisie directement) et `light` (dérivée par inversion contrôlée avec garanties WCAG AA). Pure, sans I/O.
- **TemplateRenderer** : charge les templates Jinja2 (existants étendus). Produit les artefacts pour les deux langues × deux variantes (FR×dark, FR×light, EN×dark, EN×light si SVG ; FR et EN pour les README qui référencent les SVG). Déterministe : pas de timestamp, pas d'ordre instable, pas de hash random.
- **OutputWriter** : écrit atomiquement les fichiers générés (`README.md`, `README.en.md`, `assets/svg/dark/*`, `assets/svg/light/*`). Expose une fonction `diff_against_committed() → bool` utilisée par le hook generate-and-diff.
- **MetricsFetcher** (V2 anticipé V1) : récupère via l'API GitHub des métriques publiques (count stars, count public repos, dernier push). Écrit `data/metrics.json`. Mockable en test.
- **Hooks scripts** (`scripts/hooks/`) : un script par hook custom (`validate_data.py`, `check_referential_integrity.py`, `translate.py`, `generate_and_diff.py`, `validate_svg.py`). Chaque script est un wrapper court qui orchestre les modules ci-dessus.

### Schéma data (ADR-003)

Tous les fichiers `data/*.json` sont des tableaux. Chaque entrée porte un `id` snake_case stable. Inventaire :

| Fichier | Concept |
|---|---|
| `data/config.json` | Pointeur theme/profile actifs |
| `data/profile.json` | Identité (nom, role, contacts, location, links) |
| `data/themes.json` | Design systems (palette, fonts, patterns) |
| `data/domains.json` | Taxonomie d'expertise |
| `data/techs.json` | Compétences avec `since`/`until`/`versions[]`/`featured`/overrides ; `level` retiré (dérivé) |
| `data/projects.json` | Projets publics référençant techs et domain |
| `data/timeline.json` | Events enrichis avec `role`/`employer`/`kind` |
| `data/services.json` | Prestations vendables (i18n title/description) |
| `data/modes.json` | Modes d'intervention (i18n) — extrait de `content` |
| `data/methodology.json` | Principes de travail (i18n) — extrait de `content` |
| `data/content.json` | Modules narratifs résiduels (easter eggs, boot_log, footer_eof) |

Et `data/i18n-cache/` : structure miroir avec les traductions EN.

### Formule de score (ADR-002)

```
années_actives  = (until ou aujourd'hui) − since
récence_oubli   = max(0, aujourd'hui − (until ou aujourd'hui))
nb_versions     = len(tech.versions)
nb_projets      = count(p ∈ projects où tech.id ∈ p.tech_ids)
nb_domains      = count(distinct p.domain pour ces projets)

base            = min(60, années_actives × 3)
versions_pts    = min(15, nb_versions × 3)
projets_pts     = min(15, nb_projets × 3)
centralité_pts  = min(10, max(0, nb_domains − 1) × 5)

raw             = base + versions_pts + projets_pts + centralité_pts
oubli           = récence_oubli × 6
bonus_featured  = 15 si featured else 0

score = clamp(0, 99, raw − oubli + bonus_featured)
```

Mapping vers level :
- `score ≥ 85` → `expert`
- `70–84` → `advanced`
- `55–69` → `professional`
- `35–54` → `working`
- `< 35` → `explored`

### Multi-langue (ADR-004)

- README.md (FR, défaut) + README.en.md (EN), lien réciproque en tête.
- Champs narratifs : `{ "fr": "..." }` à la saisie. EN dans cache committé `data/i18n-cache/...`.
- Traduction DeepL Free (clé `DEEPL_API_KEY` en `.env` local + GitHub Secret).
- Cache porte `{ fr_hash, en, manual: bool, reviewed: bool }`.
- `manual: true` → jamais retraduit. `reviewed: false` → warning, pas bloquant.

### Affichage adaptatif (ADR-003)

Deux jeux de SVG (`assets/svg/dark/` et `assets/svg/light/`). README utilise :

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/svg/dark/hero.svg">
  <img src="assets/svg/light/hero.svg" alt="Hero">
</picture>
```

Palette dark = `AI Architect Dark` (background `#0D1117`, primary cyan `#00E5FF`, etc.). Palette light dérivée par inversion contrôlée WCAG AA.

### Layout README — 11 sections

1. Hero SVG (identité + dispo + contact pyramide)
2. Pitch FR + bandeau Services (cartes horizontales)
3. Featured projects (table par domain)
4. Tech radar + Core expertise (SVG combiné)
5. Experience timeline (vue dérivée)
6. How I work + AI-driven (fusionné)
7. Profile as Code (snippet C# inspiré, généré)
8. Detailed stack (table par domain, repliable)
9. Quality standards (badges horizontaux + lien docs/quality-gates.md)
10. Beyond code (~bashrc easter egg actuel préservé)
11. Footer contact pyramidal

### Animations dynamiques

- **Snake** : conservé (workflow `snake.yml` existant).
- **Activity graph** (Ashutosh00710) : ajouté, dark theme aligné palette.
- **Typing banner** (DenverCoder1) : ajouté en hero, cycle les accroches (Freelance CTO / Software Architect / AI-Driven Development).
- **GitHub readme stats card** (anuraghazra) : ajouté, **rank/grade désactivés** (anti-gonflage), palette custom.
- **Time-of-day endpoint Vercel** : reporté V2.

### Quality gates (ADR-005)

- `pyproject.toml` (PEP 621) remplace `scripts/requirements.txt`. Sections `dev` et `test`.
- `Makefile` avec cibles `setup`/`validate`/`generate`/`test`/`coverage`/`lint`/`format`/`security`/`audit`/`check`.
- `.pre-commit-config.yaml` orchestrant :
  - pre-commit : ruff (lint+format), bandit, detect-secrets, cspell (en), jsonschema, referential-integrity, i18n-translate, generate-and-diff, xmllint.
  - pre-push : pytest (cov ≥ 90), pip-audit, link-checker.
- Le shell hook `install-hook.sh` historique est **supprimé**, remplacé par `pre-commit install --hook-type pre-commit --hook-type pre-push`.

### CI GitHub Actions (ADR-005)

- `ci.yml` (push + PR), `permissions: contents: read` : pre-commit run all + pytest cov + diff-check + linkcheck.
- `update-profile.yml` (cron `0 6 * * 1` + workflow_dispatch), `permissions: contents: write` (isolé) : fetch metrics + regenerate + commit si diff.
- `translate-check.yml` (PR si data/ touché), `permissions: contents: read`, secret `DEEPL_API_KEY` : check cache i18n cohérent.

### Branch protection — Repository Ruleset `main`

- PR obligatoire.
- Status checks requis : `ci/precommit`, `ci/test`, `ci/diff-check`.
- Branch up-to-date avant merge.
- Linear history.
- Conversation resolution.
- Force push interdit.
- Suppression de branche interdite.
- Signed commits requis.

### Migration depuis l'état actuel

L'implémentation se fait en branche `feature/profile-v1` dans `.worktrees/profile-v1/` (règle workflow). Ordre :
1. Bootstrap : `pyproject.toml`, `Makefile`, `.pre-commit-config.yaml`, suppression `install-hook.sh`, premiers tests.
2. JSON Schemas : un schema par fichier `data/*.json` (collection avec items typés).
3. Migration `data/techs.json` : retrait `level`, ajout `until`/`featured`/`level_override`/`score_override`.
4. Création `data/services.json`, `data/modes.json`, `data/methodology.json`, `data/config.json`, `data/themes.json` (depuis `data/theme.json`).
5. Enrichissement `data/timeline.json` : `role`/`employer`/`kind`.
6. Migration `data/content.json` (allégé après extraction).
7. Implémentation `ScoreEngine` + tests.
8. Implémentation `ViewBuilder` + tests.
9. Implémentation `I18nTranslator` + tests (DeepL mocké).
10. Refonte `TemplateRenderer` pour dark/light + EN.
11. Production des SVG dark + light pour les 11 sections.
12. Génération `README.md` + `README.en.md`.
13. Mise en place CI, workflows update-profile et translate-check.
14. Configuration ruleset `main` (manuel via gh CLI ou UI).

## Testing Decisions

### Qu'est-ce qu'un bon test ici

Tester le **comportement externe**, pas l'implémentation interne. Critères :
- Un test ne doit pas casser quand on refactore le corps d'une fonction sans en changer le contrat.
- Les inputs/outputs sont les seules surfaces stables. On teste `score(tech, projects, today) → (score, level)`, pas `_compute_base()` private.
- Préférer les **tests-table** (input → expected output) pour les modules purs (ScoreEngine, ViewBuilder, ThemeResolver).
- Préférer les **golden file tests** (snapshot d'un README/SVG attendu) pour les modules de rendu, avec stratégie de mise à jour explicite.
- Mocker les I/O externes (DeepL, GitHub API, filesystem write) — ne jamais hit le réseau en test.

### Modules testés

Tous (Q16) :

- **DataLoader** : tests sur JSON valide/invalide, schema valide/invalide, FK pointant sur une entité absente, FK valide, fichier absent, fichier vide, config absente, config pointant sur un theme inexistant.
- **ScoreEngine** : table de cas couvrant chaque palier (expert / advanced / professional / working / explored), cas limites (years=0, featured=true seul, oubli total, versions vides, projets vides). Cohérence overrides (level + score posés, l'un seul, incohérence détectée).
- **ViewBuilder** : chaque vue testée séparément avec fixtures contrôlées (Experience filtre `role != null`, Education filtre `kind == 'education'`, FeaturedProjects filtre `highlight == true`, etc.). Tests sur ordre stable (tri déterministe), regroupements par domain corrects.
- **I18nTranslator** : DeepL mocké via `responses` ou `respx`. Cas : cache absent → appel API + écriture cache ; cache présent et hash identique → 0 appel API ; hash différent et `manual: false` → retraduction ; `manual: true` → aucun appel API ; clé API absente → exception structurée.
- **ThemeResolver** : table de cas dark → light dérivé. Vérification du contraste WCAG AA via une lib (par exemple `wcag-contrast`).
- **TemplateRenderer** : golden file pour chaque section × langue × variante. Détection de placeholder Jinja non remplacé (regex `{{.*}}` interdit dans output). Vérification que tous les liens internes pointent sur un fichier existant.
- **OutputWriter** : tests sur écriture atomique (pas de fichier partiel sur échec), diff vs committed (cas diff vide, cas diff présent).
- **MetricsFetcher** : GitHub API mockée. Cas : API OK → metrics écrit ; API 404 sur repo absent ; API timeout.

### Tests d'intégration

- **Pipeline complet** : depuis `data/` propre → `generate()` → produit `README.md` + `README.en.md` + SVG cohérents.
- **Déterminisme** : `generate()` × 2 → `diff` vide sur tous les fichiers produits.
- **Référentielle ronde** : modifier un id dans techs → projects qui le référence doit être détecté comme rompu.

### Prior art

Aucun test existant dans le repo. Inspiration possible : structure de tests Python standard pytest, fixtures partagées via `conftest.py`, snapshot tests via `pytest-regressions` ou `syrupy`.

### Couverture

≥ 90% bloquante en pre-push et CI. Configurée dans `pyproject.toml` via `[tool.coverage]`. Lignes templates Jinja2 difficiles à couvrir : stratégie = tester via fixtures de data variées qui exercent chaque branche conditionnelle du template.

## Out of Scope

- **Time-of-day endpoint Vercel** : reporté V2. Repo séparé ou sous-dossier endpoints/ à décider à ce moment.
- **Thèmes alternatifs** (Solarized, etc.) : la mécanique multi-thème est prête (collection `themes.json` + pointeur `config.json`) mais V1 livre uniquement `AI Architect Dark`.
- **CLI complet** : `scripts/generate.py` reste un entry point unique. Pas de CLI multi-commandes type Click/Typer en V1 (V3 spec).
- **Export portfolio web** : non livré (V3 spec).
- **Métriques GitHub avancées** : V1 commence avec stars + repos public + dernier push. Wakatime, codetime, langage breakdown via API : V2.
- **Bilingue au-delà de FR/EN** : pas d'ES, DE, etc. Modèle i18n extensible mais V1 livre 2 langues seulement.
- **Animations DOM/JS** : impossibles sur GitHub README (pas de JS). Toute animation passe par SVG SMIL ou endpoint serverless dynamique.
- **Détection de langue navigateur côté serveur** : impossible avec GitHub README. Le visiteur clique pour switcher.
- **Tests E2E browser** (Playwright) sur le rendu GitHub : non livré V1. Vérification visuelle manuelle après push initial.

## Further Notes

### Risques

- **Dépendance DeepL** : si le service est down ou la clé révoquée, le pre-commit échoue. Mitigation : DeepL a SLA très stable (~99.9%), clé régénérable. En cas de panne prolongée, possibilité d'override temporaire par script qui marque toutes les entrées `manual: true` avec valeur EN identique au FR (à utiliser exceptionnellement).
- **Couverture 90% sur Jinja** : peut être pénible. Mitigation : fixtures variées qui exercent chaque branche `{% if %}`. Si vraiment infaisable sur une portion, exclure ligne par ligne avec `# pragma: no cover` justifié.
- **`<picture>` HTML inline** : viole strictement « Markdown uniquement » de la spec V1 initiale. Décision : accepté car standard GitHub, sans alternative équivalente. Documenté dans ADR-003.
- **Migration des données existantes** : retrait `level` de `techs.json`, ajout de champs. Risque de perte d'info si mauvais mapping. Mitigation : tests référentiels post-migration + revue visuelle du README avant merge.
- **Régression visuelle du profil pendant l'impl** : pendant la branche `feature/profile-v1`, le profil public reste sur `main` (état actuel). Le merge final remplace tout d'un coup. Mitigation : preview locale via `make generate` avant push final.

### Variables d'environnement requises

- `DEEPL_API_KEY` : clé DeepL Free (suffixe `:fx`). Local : `.env`. CI : GitHub Secret.
- `GITHUB_TOKEN` : fourni automatiquement par GitHub Actions pour `update-profile.yml`.

### Conventions

- Conventional commits (`feat(profile):`, `fix(svg):`, `chore(deps):`, `docs(adr):`, `test(generator):`).
- Branches sous `.worktrees/<slug>/` (règle workflow).
- Branche feature unique pour cette refonte : `feature/profile-v1`.
- Trunk-based : pas de `develop`.

### Estimation

Implémentation TDD strict : ordre de grandeur 2–3 jours de travail focalisé. Le plus long sera (a) la rédaction des JSON Schemas et tests data, (b) la refonte des templates Jinja2 pour produire les variantes dark + light + i18n.

### Définition of Done

- `make check` passe en local (validate + generate + lint + format-check + security + audit + coverage 90%).
- CI verte sur PR.
- `main` ruleset configuré.
- README.md (FR) et README.en.md (EN) rendus visuellement OK en local et après merge.
- Snake + Activity graph + Typing banner + Stats card sobre apparaissent et se mettent à jour.
- `pre-commit install` est suffisant pour qu'un fork tourne immédiatement (à condition d'avoir une clé DeepL).
- 5 ADRs (002-005 + l'existante 001) à jour et liées entre elles.
- CONTEXT.md à jour avec tous les concepts.
- Cette PRD fermée.
