# ADR-003 — Schéma data : tout en collections, vues dérivées, affichage adaptatif

- **Statut** : Accepted
- **Date** : 2026-05-27
- **Lié à** : [ADR-001](0001-data-driven-svg-generation.md), [ADR-002](0002-tech-score-derivation.md), [ADR-004](0004-i18n-bilingual-readme.md)

## Contexte

ADR-001 a posé le principe data-driven. L'évolution du périmètre (services structurés, multi-langue, mode dark/light, animations, time-of-day) et la volonté de traiter les data comme une **base de données** imposent un schéma plus normalisé que la version initiale.

## Décision

### 1. Tous les fichiers `data/` sont des collections

Chaque fichier `data/*.json` est un **tableau JSON** ; chaque entrée porte un `id` snake_case stable. Les singletons d'origine (`profile`, `theme`) deviennent des collections à une (ou plusieurs) entrée, ce qui permet la coexistence de plusieurs profils ou thèmes sans refonte.

### 2. Inventaire des collections

| Fichier | Cardinalité usuelle | Rôle |
|---|---|---|
| `data/config.json` | 1 | Pointe `theme_id` et `profile_id` actifs |
| `data/profile.json` | 1 (extensible) | Identité, contacts, links, location |
| `data/themes.json` | 1+ | Design systems disponibles |
| `data/domains.json` | 6–10 | Taxonomie expertise |
| `data/techs.json` | 50+ | Compétences techniques (FK → domain) |
| `data/projects.json` | 10–20 | Projets publics (FK → domain, M:N → techs) |
| `data/timeline.json` | 10–20 | Events chronologiques (M:N → techs) |
| `data/services.json` | 4–8 | Prestations vendables |
| `data/modes.json` | 3–5 | Modes d'intervention |
| `data/methodology.json` | 5–10 | Principes de travail |
| `data/content.json` | 5–10 | Modules narratifs résiduels |

### 3. Vues dérivées (jamais stockées)

Calculées par `scripts/generate.py`, jamais persistées dans `data/` :

| Vue | Dérivation |
|---|---|
| `Skill` | `Tech` + score (formule ADR-002) + level |
| `Experience` | `TimelineEvent.filter(role != null)`, périodes calculées |
| `Education` | `TimelineEvent.filter(kind == 'education')` |
| `TechRadar` | `Skills` agrégés par cluster (Core/Advanced/Working/Explored) |
| `CoreExpertise` | `Skills.filter(featured == true)` |
| `FeaturedProjects` | `Projects.filter(highlight == true).group_by(domain)` |
| `StackByDomain` | `Techs.group_by(domain)` |
| `ParcoursStory` | `TimelineEvents.filter(highlight == true).sort(year)` |

Invariant : si une valeur factuelle peut être calculée depuis l'existant, on la **dérive** au lieu de la dupliquer.

### 4. IDs stables et intégrité référentielle

- Chaque entrée a un `id` snake_case fixé à la création, **jamais modifié**.
- Les références sont par id (`domain_id`, `tech_ids[]`, etc.).
- Un test pre-commit vérifie que chaque référence pointe sur une entité existante.

### 5. Affichage adaptatif dark/light

Le generator produit deux jeux de SVG : `assets/svg/dark/*` et `assets/svg/light/*`. Le README utilise la balise HTML `<picture>` (acceptable car standard GitHub, pas du SVG inline) :

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/svg/dark/hero.svg">
  <img src="assets/svg/light/hero.svg" alt="Hero">
</picture>
```

La palette de base **dark** (`AI Architect Dark`) :
- background `#0D1117`, surface `#161B22`
- primary `#00E5FF`, secondary `#7C3AED`, accent `#22C55E`
- text `#E6EDF3`, muted `#8B949E`

La palette **light** est dérivée par inversion contrôlée (pas un simple flip) : fond clair, primary/secondary/accent conservés mais ajustés pour le contraste WCAG AA.

### 6. Profile as Code

Une section du README affiche une représentation **code** du profil (C# inspiré de la spec V1 §5.2), générée elle aussi depuis `data/` pour rester en phase. Pas de duplication entre le code affiché et les data sources.

## Conséquences

### Positives

- Schéma normalisé, lisible comme une BDD, évolutif sans refonte.
- Pas de duplication entre data et vues.
- Affichage adaptatif dark/light sans JS, respecte les conventions GitHub.
- Permet plusieurs thèmes / profils via `config.json`.

### Négatives

- Migration depuis l'état actuel : extraction de `Mode`/`Methodology` depuis `content`, ajout `services`/`config`/`themes`, refonte de `techs` (suppression `level`, ajout `until`/`featured`/`overrides`), enrichissement `timeline` (`role`/`employer`/`kind`).
- Doublement des SVG (dark + light) — coût stockage négligeable, coût génération doublé mais reste rapide.
- Acceptation de la balise `<picture>` HTML — pas du Markdown pur strict.
