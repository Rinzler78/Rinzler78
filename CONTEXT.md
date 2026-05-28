# CONTEXT — Glossaire du repo `Rinzler78/Rinzler78`

Ce repo est le profil GitHub de Boris Leclere. Le README et les SVG décoratifs sont **générés** depuis des données structurées en JSON (séparation data / présentation). Ce fichier définit le vocabulaire utilisé dans le code et les données.

> Ce fichier est un **glossaire**, pas une spécification. Pour les choix d'implémentation, voir [docs/adr/](docs/adr/).

---

## Concepts data (sources de vérité dans `data/`)

### Profile

`data/profile.json` — Identité de Boris : nom, rôle, contacts (email, téléphone), liens (LinkedIn, Malt, GitHub, PyPI, Discord, YouTube, X) et **location** (city, region, country, lat, lon, zone administrative, fuseau horaire). La location est inline dans Profile, pas un fichier séparé, car elle ne change qu'en cas de déménagement.

### Domain

`data/domains.json` — Taxonomie des domaines d'expertise. Chaque domaine a un `id` snake_case stable, un `label` humain et un `order` (rang d'affichage). Les domaines actuels : `embedded`, `mobile`, `backend`, `devops`, `ai-llm`, `blockchain`. **Embarqué est en premier** par convention (parcours signature).

### Tech

`data/techs.json` — Une « tech » est une compétence technique avec un identifiant racine **stable dans le temps** (ex `csharp`, jamais `csharp-12`). Chaque tech porte : `id` (snake_case sans version), `label`, `domain-id`, `since` (année d'adoption obligatoire), `until` (année de dernier usage si abandonnée, optionnel), `notes`. Elle contient un tableau `versions[]` : chaque version a son propre `id` snake_case complet (ex `csharp_2_0`, `csharp_12`) + `version` (label) + `since` (année de cette version).

**Niveau et score** sont des **valeurs dérivées**, jamais saisies directement (sauf override). Le generator calcule `score` ∈ [0, 99] depuis les faits saisis et déduit `level` parmi 5 paliers (`expert` / `advanced` / `professional` / `working` / `explored`) via des seuils figés. Voir [ADR-002](docs/adr/0002-tech-score-derivation.md) pour la formule et les paliers.

Champ `depth` (0–3) : profondeur d'usage en production, **auto-évaluation factuelle** (y compris missions privées invisibles sur GitHub). 0 = read-level, 3 = expertise cœur. Additif (+20/niveau). Corrige le biais « la formule ne voit que le public ». Voir [ADR-002](docs/adr/0002-tech-score-derivation.md).

Champs d'override (optionnels, à utiliser quand la formule sous-évalue, par ex. usage privé non listé dans `projects.json`) :
- `level_override` — force le level qualitatif
- `score_override` — force le score numérique
- `featured` — booléen, ajoute un bonus +15 au score (sert aussi à filtrer hero/core expertise)

**Invariant temporel** (principe énoncé par Boris) : une compétence ne reste « active » (`until: null`) **que si une expérience ou un projet courant l'utilise encore**. Une tech bornée à une période passée doit porter le `until` de la fin de cette période — sinon elle prétendrait à tort à une expertise actuelle (ex. `gps` est borné à 2013, fin de l'ère embarquée GoodKap). Source de vérité des périodes : `data/timeline.json`. Tant que les events timeline ne portent pas la liste des techs *utilisées* par période (seulement `techs-added`), ce `until` est maintenu à la main avec discipline ; une dérivation automatique sera possible quand les périodes porteront leurs techs actives.

### Timeline Event

`data/timeline.json` — Un événement chronologique du parcours : `year` (ou `year-range`), `label`, `description`, `techs-added` (tableau d'ids — réf vers Tech ou tech-version), `highlight` (booléen pour les jalons majeurs : 2006 premier code, 2009 Master, 2014 CTO, 2020 .NET Core, 2023 freelance, 2026 now).

Champs optionnels pour dériver la vue **Experience** (postes professionnels) :
- `role` — intitulé de poste (ex `"CTO"`, `"Freelance CTO / Senior Engineer"`). Si présent, l'event marque un changement de poste.
- `employer` — nom de l'employeur ou label client (ex `"BIM&CO"`, `"Freelance"`).

La vue Experience est **dérivée** : on filtre les events qui portent `role`, on borne chaque période par l'année du prochain event avec `role` (ou « now » si dernier). Pas de fichier `experience.json` séparé — invariant « une valeur factuelle apparaît dans exactement un fichier data ».

Champ optionnel `kind` parmi `job` / `education` / `personal` / `tech_milestone` pour qualifier la nature de l'event et permettre des vues dérivées (`education` filtre `kind=education`, `tech_milestone` n'apparaît pas dans Experience, etc.). Un event sans `kind` est traité comme `tech_milestone` par défaut.

### Project

`data/projects.json` — Un projet public mis en avant : `name`, `github-url`, `domain-id`, `tech-ids[]`, `description`, `state` (`active` / `legacy` / `archive`). Référence techs par id pour cohérence avec les autres concepts.

### Service

`data/services.json` — Une **prestation vendable** que Boris propose à un client : `id` snake_case, `title` (i18n), `short_description` (i18n), `keywords[]` (EN, factuel), `priority` (ordre d'affichage), `visible` (booléen). Exemples : Software Architecture, Technical Audit, AI-Driven Development, Developer Tooling, RAG / Private AI, Delivery Support.

Service répond à la question « **qu'est-ce que je peux acheter à Boris** ». À ne pas confondre avec **Mode**.

### Mode

`data/modes.json` — Un **mode d'intervention** : `id` snake_case, `title` (i18n), `description` (i18n), `keywords[]`. Modes actuels : `pompier` (intervention courte, urgence/crise), `accompagnement_long` (mission étalée, build progressif), `audit` (one-shot, livrable rapport), `mentor` (montée en compétence d'une équipe).

Mode répond à la question « **comment je peux engager Boris** ». Extrait depuis `content.modes_intervention[]` historique — promotion en entité de premier ordre.

### Methodology

`data/methodology.json` — Collection de **principes de travail** de Boris : `id`, `title` (i18n), `body` (i18n), `order`. Exemples : « Comprendre le problème métier avant le code », « Simple before clever », « AI as engineering accelerator, not replacement ». Extrait depuis `content` historique — promotion en entité de premier ordre pour le rendre adressable depuis le README et les vues dérivées.

### Config

`data/config.json` — Singleton-collection (1 entrée `id: "main"`) qui pointe le **theme actif** (`theme_id`) et le **profile actif** (`profile_id`) si plusieurs sont définis. Permet de faire évoluer le design ou de versionner un test A/B sans toucher aux autres fichiers.

### Theme

`data/theme.json` — Le « design system » du repo. Trois sous-blocs :
- **palette** : couleurs nommées (`paper`, `ink`, `accent`, `term-bg`, `term-fg`, `info`, …)
- **fonts** : `display` (Fraunces), `body` (Geist), `mono` (JetBrains Mono)
- **patterns** : composants réutilisables avec leurs constantes — `terminal_window` (boutons macOS, header, padding), `ecg_divider` (couleurs, durée d'anim), `prompt` (style $/prompt), `cursor` (clignotement)

Le Theme est éditable séparément des autres data — change-le et tous les SVG se rethémenisent.

### Content

`data/content.json` — Collection de modules narratifs résiduels (ceux qui ne sont pas devenus des entités propres) : easter eggs `//` par section, `boot_log[]` (lignes du `<details>`), `blockquote_autodidacte`, `footer_eof`, prose `beyond_code`. Chaque module a `id`, `kind`, `payload` (i18n quand prose).

**Promotions** depuis content.json historique :
- `modes_intervention[]` → entité **Mode** (data/modes.json)
- principes de travail / prose `mon_approche` → entité **Methodology** (data/methodology.json)

---

## Concepts génération (dans `scripts/`)

### Template

Fichier `.jinja` dans `scripts/templates/` qui décrit le rendu d'un SVG ou du README à partir des data. Utilise la syntaxe Jinja2. Un template peut hériter d'un partial (ex `_terminal_window.svg.jinja` réutilisé par tous les terminaux).

### Generate

`scripts/generate.py` — Script Python qui charge `data/*.json`, charge `theme.json` (constantes design), résout les références par id, et produit `assets/svg/*.svg` + `README.md` via les templates Jinja2.

### Vue (view)

Une vue est un SVG ou une section du README qui **agrège** plusieurs concepts data. Exemples :
- *id-card* = projection de Profile + filter de Techs (par domain)
- *timeline-life* = Timeline Events triés
- *stack-{domain}* = Techs filtrés par domain
- *featured* = Projects groupés par domain
- *parcours* = Timeline Events filtrés (highlight=true)

Les vues sont **dérivées**, jamais stockées. C'est l'invariant qui garantit la cohérence inter-vues.

---

## Internationalisation (i18n)

Les **champs narratifs** (titres, descriptions courtes, pitch, prose) sont saisis en FR dans `data/*.json` et **traduits automatiquement en EN par DeepL** au pre-commit. Chaque champ i18n a la forme `{ "fr": "..." }` à la saisie ; la traduction EN est stockée dans un **cache committé** sous `data/i18n-cache/<entity>/<id>.<field>.en.json`.

Le cache porte `{ fr_hash, en, manual: bool, reviewed: bool }`. Si `manual: true`, le hook ne touche jamais à `en`. Si `reviewed: false`, le hook affiche un warning mais la génération de `README.en.md` procède.

Les **champs factuels** (id, name, dates, tech labels, URLs, score) ne sont pas i18n — string/number simples.

Voir [ADR-004](docs/adr/0004-i18n-bilingual-readme.md).

## Affichage adaptatif

Les SVG sont générés en **deux variantes** (`assets/svg/dark/*` et `assets/svg/light/*`). Le README utilise `<picture>` avec `prefers-color-scheme` pour servir la bonne variante selon la préférence GitHub du visiteur.

```md
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/svg/dark/hero.svg">
  <img src="assets/svg/light/hero.svg" alt="...">
</picture>
```

Voir [ADR-003](docs/adr/0003-data-schema-collections-and-derived-views.md).

## Workflow

1. Éditer un ou plusieurs fichiers dans `data/`
2. `git add data/...`
3. Le **pre-commit hook** détecte le changement, lance `python scripts/generate.py`, ajoute `assets/svg/*.svg` et `README.md` au staging
4. `git commit` (les fichiers générés sont inclus dans le même commit que les data sources)

Le hook garantit que **les SVG/README versionnés sont toujours en phase avec les data** versionnées au même commit.

---

## Invariants

- Une **valeur factuelle** (ex « Python 3.11+ Expert depuis 2023 ») apparaît dans **exactement un** fichier data — jamais répliquée.
- Les **IDs de techs et domains** sont stables dans le temps : un ID n'est jamais réutilisé pour autre chose, et on n'introduit pas la version dans l'ID racine (sinon les références cassent au moindre upgrade).
- Les fichiers générés (`assets/svg/`, `README.md`) sont **commitables** mais **jamais édités à la main** — toute modif passe par les data ou les templates.
