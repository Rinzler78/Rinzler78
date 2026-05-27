# Spécification complète — GitHub Profile README data-driven, visuel et gouverné comme un vrai repo de code

> Version : 1.0  
> Format de visualisation : **Markdown uniquement**  
> Principe : les exemples visuels sont des fichiers SVG externes référencés comme images Markdown.  
> Objectif : créer un profil GitHub personnel qui fonctionne comme une landing page professionnelle, générée depuis des données structurées, testée, maintenable, sécurisée et automatisée.

---

## 1. Vision

Créer un dépôt spécial GitHub Profile du type :

```text
Rinzler78/Rinzler78
```

dont le `README.md` est généré automatiquement à partir de données JSON, avec des SVG dynamiques et une identité visuelle forte.

Le dépôt doit démontrer deux choses en même temps :

1. **Le profil professionnel** : qui je suis, ce que je propose, mes compétences, mes services, mes preuves, mon contact.
2. **La méthode de travail** : data-driven, génération déterministe, qualité automatisée, tests, sécurité, CI/CD, documentation et gouvernance Git.

> Même mon profil GitHub doit être construit comme un produit logiciel maintenable.

---

## 2. Contraintes importantes

### 2.1 Markdown uniquement

Le livrable final doit rester compatible Markdown/GitHub.

À éviter dans la spec et dans le README final :

```md
<svg>...</svg>
<div style="background:#000">...</div>
```

Beaucoup de viewers Markdown affichent ces balises comme du texte ou ignorent les styles.

À utiliser :

```md
![Hero banner](assets/generated/hero.svg)
```

Ou, pour contrôler la largeur sur GitHub :

```md
<p align="center">
  <img src="assets/generated/hero.svg" width="100%" alt="Hero banner" />
</p>
```

### 2.2 SVG externes

Tous les exemples visuels doivent être des fichiers SVG séparés :

```text
assets/
├── preview/      # exemples pour la spec Markdown
└── generated/    # assets générés pour le README final
```

La spec Markdown référence les fichiers `assets/preview/*.svg`.

Le README final référence les fichiers `assets/generated/*.svg`.

---

## 3. Palette recommandée

![Palette AI Architect Dark](assets/preview/palette-ai-architect-dark.svg)

### Palette `AI Architect Dark`

| Rôle | Couleur |
|---|---|
| Background | `#0D1117` |
| Surface | `#161B22` |
| Primary | `#00E5FF` |
| Secondary | `#7C3AED` |
| Accent | `#22C55E` |
| Text | `#E6EDF3` |
| Muted | `#8B949E` |

### Intention

Cette palette doit transmettre :

- expertise technique ;
- sérieux ;
- modernité ;
- IA / architecture ;
- sobriété premium ;
- clarté.

Elle évite l’effet “profil template junior” trop coloré.

---

## 4. Direction artistique

### Nom du thème

```text
AI Architect Dark
```

### Style

```text
Dark premium
Terminal-inspired
Data-driven
CTO / architecte
AI-assisted development
Sobriety over noise
```

### Ratio visuel recommandé

```text
70% professionnel
20% visuel
10% fun-tech
```

Le design doit servir le message, pas l’écraser.

---

## 5. Inspirations analysées

Les exemples du topic GitHub `awesome-github-profiles` montrent plusieurs familles de profils :

### 5.1 Showcase animé / fun

Caractéristiques :

- beaucoup d’images ;
- badges nombreux ;
- animations ;
- snake graph ;
- compteurs ;
- quotes ;
- hobbies ;
- sections stargazers/forkers.

À retenir :

```text
✅ Dynamisme
✅ Assets visuels nombreux
✅ Automatisation
❌ Trop de bruit
❌ Trop fun pour un profil CTO
❌ Message business dilué
```

### 5.2 Profil “code identity”

Idée intéressante : présenter la personne sous forme de code.

Exemple adapté :

```csharp
public sealed class BorisLeclere : FreelanceCto
{
    public string[] CoreSkills => ["C#", ".NET", "Python", "Docker", "AI-Driven Development"];
    public string[] Services => ["Architecture", "Audit", "Automation", "AI Tooling"];
}
```

À intégrer dans une section secondaire, pas forcément dans la première page.

### 5.3 Portfolio professionnel

À retenir :

```text
✅ Structure claire
✅ Services visibles
✅ Projets mis en avant
✅ Contact rapide
❌ Souvent trop générique
❌ Peu de personnalité
```

### 5.4 Conclusion d’inspiration

Ne pas copier un profil existant.

Construire une identité propre :

```text
Profile as Product
+
Premium CTO Landing Page
+
Data-driven Engineering Identity
```

---

## 6. Première page visible

La première zone visible sans scroll doit afficher rapidement :

- identité ;
- titre ;
- proposition de valeur ;
- services ;
- compétences clés ;
- disponibilité ;
- contact.

### Exemple de bannière — option 1 : Terminal premium

![Hero terminal premium](assets/preview/hero-banner-option-1.svg)

### Exemple de bannière — option 2 : Desk / embedded to AI

![Hero desk embedded to AI](assets/preview/hero-banner-option-2.svg)

### Décision recommandée

Pour un profil très professionnel, utiliser l’option 1.

Pour un profil plus personnel, différenciant, avec storytelling parcours embedded → cloud → IA, utiliser l’option 2.

La meilleure solution peut être hybride :

```text
Header principal = terminal premium
Section parcours = bureau / embedded / storytelling
```

---

## 7. Ordre recommandé du README final

```text
1. Hero SVG
2. Badges rapides : disponibilité, lieu, langues, contact
3. Pitch court
4. Services
5. Core expertise
6. Featured projects
7. How I work
8. Profile as Code
9. Experience timeline
10. Technical expertise matrix
11. Detailed stack
12. Education / qualifications
13. Quality standards
14. GitHub activity
15. Beyond code
16. Contact footer
```

### Principe de lecture

```text
Haut de page = convaincre vite
Bas de page = prouver en détail
```

---

## 8. Services

Les services doivent être lisibles rapidement. Ils ne doivent pas être noyés dans la stack technique.

![Service cards](assets/preview/service-cards.svg)

### Services recommandés

| Service | Objectif |
|---|---|
| Software Architecture | Concevoir des systèmes maintenables, testables et évolutifs |
| Technical Audit | Auditer code, architecture, tests, CI/CD, sécurité, documentation |
| AI-Driven Development | Structurer l’usage des agents IA, prompts, règles, mémoire et quality gates |
| Developer Tooling | Créer CLI, générateurs, scripts, automatisation |
| RAG / Private AI | Connecter des LLM aux données privées d’entreprise |
| Delivery Support | Stabiliser CI/CD, Docker, release, qualité |

### Source de données

```text
data/services.json
```

Exemple :

```json
[
  {
    "id": "architecture",
    "title": "Software Architecture",
    "shortDescription": "Design maintainable, testable and scalable software systems.",
    "keywords": ["Clean Architecture", "DDD", "Modularity"],
    "priority": 1,
    "visible": true
  }
]
```

---

## 9. Carte terminal / identité

![Terminal card](assets/preview/terminal-card.svg)

Cette section sert à ancrer le concept :

> Le profil est généré depuis des données et reflète une méthode de travail.

Elle peut être utilisée pour :

- expliquer rapidement ton identité ;
- afficher les services ;
- afficher les principes ;
- introduire la notion de `profile as code`.

---

## 10. Timeline parcours + données

![Timeline](assets/preview/timeline.svg)

### Objectif

Mélanger :

- parcours professionnel ;
- évolution technique ;
- rôles ;
- périodes ;
- domaines.

### Source

```text
data/experience.json
```

Exemple :

```json
[
  {
    "start": "2009-01-01",
    "end": "2013-12-31",
    "role": "Software Developer",
    "focus": ["Embedded", "Windows CE", "NFC", "C/C++"]
  },
  {
    "start": "2024-01-01",
    "end": null,
    "role": "Freelance CTO / Senior Engineer",
    "focus": ["Architecture", "AI-driven development", "Automation"]
  }
]
```

### Règles de génération

- Si `end` est `null`, afficher `Now`.
- Trier par date.
- Générer une version condensée en SVG.
- Générer une version détaillée en Markdown/tableau.

---

## 11. Skills matrix

![Skill bars](assets/preview/skill-bars.svg)

### Objectif

Donner une lecture crédible des compétences.

Éviter :

```text
❌ 50 badges logos
❌ une note arbitraire sans contexte
❌ des technos jamais utilisées réellement
```

Préférer :

```text
✅ Domaine
✅ Technologie
✅ Niveau
✅ Années
✅ Versions
✅ Usage réel
✅ Dernier usage
```

### Source

```text
data/skills.json
```

Exemple :

```json
[
  {
    "category": "Language",
    "name": "C#",
    "level": "expert",
    "score": 95,
    "firstUsed": "2009-01-01",
    "lastUsed": "2026-05-01",
    "versions": [".NET Framework", ".NET Core", ".NET 6", ".NET 8", ".NET 10"],
    "usage": ["Backend", "Desktop", "Mobile", "Tooling"],
    "featured": true
  }
]
```

### Niveaux normalisés

| Niveau | Score | Signification |
|---|---:|---|
| Expert | 90-100 | Maîtrise profonde, utilisé en contexte critique |
| Advanced | 75-89 | Autonome en production |
| Professional | 60-74 | Usage réel, capable de livrer |
| Working knowledge | 40-59 | Connaissance pratique |
| Explored | 20-39 | Veille, prototype, expérimentation |

---

## 12. Tech radar

![Tech radar](assets/preview/tech-radar.svg)

### Objectif

Le radar évite l’effet catalogue.

Il classe les technologies selon :

- maîtrise ;
- usage récent ;
- pertinence business ;
- capacité à livrer seul ;
- centralité dans ton positionnement.

### Règles

```text
Core         = usage fréquent + maîtrise forte + rôle central
Advanced     = autonome en production
Professional = usage réel mais moins central
Explored     = expérimentation ou veille
```

### À intégrer

Technos probables à classer :

```text
Core:
- C#
- .NET
- Architecture
- Python
- Docker

Advanced:
- GitHub Actions
- CI/CD
- AI-assisted development
- APIs / OpenAPI
- EF Core

Professional:
- MAUI
- Blazor
- FastAPI
- RAG
- LangChain / LiteLLM

Explored:
- Qdrant
- CrewAI / LangGraph
- LocalAI / Ollama
```

---

## 13. Featured projects

### Objectif

Les projets doivent prouver une compétence ou un axe de positionnement.

À éviter :

```text
❌ liste brute de repos
❌ projets non contextualisés
❌ repos abandonnés sans explication
```

À faire :

```text
✅ regrouper par domaine
✅ expliquer le problème résolu
✅ afficher stack
✅ afficher statut
✅ afficher lien
✅ afficher pourquoi c’est pertinent
```

### Source

```text
data/projects.json
```

Exemple :

```json
[
  {
    "name": "PythonRefactorToolBox",
    "description": "AST-based Python refactoring toolbox.",
    "stack": ["Python", "AST", "Refactoring"],
    "status": "active",
    "featured": true,
    "url": "https://github.com/Rinzler78/PythonRefactorToolBox",
    "domain": "Developer Tooling"
  }
]
```

### Rendu recommandé

```md
| Project | Domain | Status | Why it matters |
|---|---|---|---|
| PythonRefactorToolBox | Developer Tooling | Active | Demonstrates AST analysis and automation |
```

---

## 14. How I work

Section indispensable pour ton positionnement.

### Objectif

Montrer que tu es professionnel, structuré, polyvalent, orienté qualité.

Exemple :

```md
## How I work

I like to build software with a strong engineering foundation:

1. Understand the business problem before writing code
2. Clarify requirements and constraints
3. Design a simple and maintainable architecture
4. Implement with tests, automation and quality gates
5. Document decisions and trade-offs
6. Iterate pragmatically while keeping technical debt under control
```

### Principes courts

```text
Simple before clever
Explicit before implicit
Tested before trusted
Automated before manual
Maintainable before trendy
Business value before technical ego
```

### Source

```text
data/methodology.json
```

---

## 15. AI-driven development

Cette section est importante, mais elle doit être sérieuse.

### Message recommandé

```md
I use AI as an engineering accelerator, not as a replacement for engineering discipline.

AI-assisted development works best when combined with:
- clear specifications;
- strong architecture;
- automated tests;
- quality gates;
- controlled context;
- documented decisions;
- iterative validation.
```

### Phrase forte

```text
Without methodology, AI only generates faster chaos.
```

À utiliser seulement si le ton du profil accepte une phrase plus punchy.

---

## 16. Quality pipeline du repo

![Quality pipeline](assets/preview/quality-pipeline.svg)

### Objectif

Le repo du profil doit être traité comme un vrai projet.

Contrôles à implémenter :

```text
- validation JSON
- validation JSON Schema
- génération README/SVG
- génération déterministe
- lint
- format
- tests
- couverture
- sécurité
- audit dépendances
- détection secrets
- vérification liens
- validation SVG/XML
- vérification que les artefacts générés sont commités
```

---

## 17. Architecture du dépôt

```text
Rinzler78/
├── README.md
├── profile.config.json
├── pyproject.toml
├── Makefile
├── .pre-commit-config.yaml
├── data/
│   ├── identity.json
│   ├── services.json
│   ├── skills.json
│   ├── experience.json
│   ├── education.json
│   ├── projects.json
│   ├── methodology.json
│   ├── socials.json
│   └── design.json
├── schemas/
│   ├── identity.schema.json
│   ├── services.schema.json
│   ├── skills.schema.json
│   ├── experience.schema.json
│   └── projects.schema.json
├── templates/
│   ├── README.md.j2
│   ├── sections/
│   │   ├── hero.md.j2
│   │   ├── services.md.j2
│   │   ├── projects.md.j2
│   │   ├── timeline.md.j2
│   │   ├── skills.md.j2
│   │   └── contact.md.j2
│   └── svg/
│       ├── hero.svg.j2
│       ├── services.svg.j2
│       ├── timeline.svg.j2
│       ├── skill-bars.svg.j2
│       ├── tech-radar.svg.j2
│       └── footer.svg.j2
├── assets/
│   ├── preview/
│   │   └── *.svg
│   └── generated/
│       └── *.svg
├── scripts/
│   ├── generate_profile.py
│   ├── validate_data.py
│   ├── compute_metrics.py
│   └── check_generated.py
├── tests/
│   ├── test_data_validation.py
│   ├── test_generation.py
│   ├── test_determinism.py
│   ├── test_svg_validity.py
│   └── test_rendering_rules.py
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── rendering-pipeline.md
│   ├── quality-gates.md
│   └── branch-protection.md
└── .github/
    ├── workflows/
    │   ├── ci.yml
    │   └── update-profile.yml
    ├── pull_request_template.md
    └── dependabot.yml
```

---

## 18. Données JSON

### `data/identity.json`

```json
{
  "name": "Boris Leclere",
  "headline": "Freelance CTO · Senior Software Engineer · Software Architect",
  "location": "France / Remote",
  "availability": {
    "status": "available",
    "label": "Available for freelance missions"
  },
  "pitch": "I help companies design, build and industrialize robust software systems with clean architecture, automation and AI-assisted development workflows.",
  "contacts": {
    "email": "borisleclere.pro@gmail.com",
    "github": "https://github.com/Rinzler78",
    "linkedin": "https://www.linkedin.com/in/borisleclere"
  }
}
```

### `data/design.json`

```json
{
  "theme": "ai-architect-dark",
  "palette": {
    "background": "#0D1117",
    "surface": "#161B22",
    "primary": "#00E5FF",
    "secondary": "#7C3AED",
    "accent": "#22C55E",
    "text": "#E6EDF3",
    "muted": "#8B949E"
  },
  "animations": {
    "enabled": true,
    "intensity": "subtle"
  },
  "layout": {
    "hero": "terminal-premium",
    "services": "cards",
    "skills": "bars-and-radar",
    "timeline": "horizontal"
  }
}
```

---

## 19. Génération

### Principe

```text
data/*.json
   ↓
validation schemas
   ↓
view models calculés
   ↓
templates markdown + svg
   ↓
README.md + assets/generated/*.svg
```

### Règles

- Le README est généré.
- Les SVG sont générés.
- Les données sont la source de vérité.
- Les sorties sont déterministes.
- Les fichiers générés sont versionnés.
- Toute modification manuelle du README doit être écrasée par la génération.

---

## 20. Tests

### Tests data

```text
- Tous les JSON sont valides.
- Tous les JSON respectent leur schema.
- Aucun service visible sans titre.
- Aucun projet featured sans URL.
- Aucun skill visible sans niveau.
- Aucun lien contact obligatoire manquant.
```

### Tests génération

```text
- README généré.
- SVG générés.
- SVG valides XML.
- Aucun placeholder Jinja non remplacé.
- Génération déterministe.
- Aucun diff après double génération.
```

### Tests métier

```text
- availability.status = available → badge vert
- skill.score >= 90 → Expert
- skill.featured = true → affiché dans hero/core expertise
- project.featured = false → non affiché dans featured projects
- service.visible = false → non affiché dans services
```

### Couverture

```text
Minimum : 90%
```

---

## 21. Quality gates locaux

### Pre-commit

Rapide, exécuté avant commit.

Doit vérifier :

```text
- format
- lint
- validation JSON
- validation schema
- génération README/SVG
- absence de diff
- détection secrets
- markdown basique
```

### Pre-push

Plus lourd, exécuté avant push.

Doit vérifier :

```text
- tests complets
- couverture
- audit sécurité
- audit dépendances
- validation liens
- validation SVG/XML
- build complet
```

### Protection locale main

Ajouter un hook local qui empêche le push direct depuis `main`.

Mais ce n’est qu’une protection de confort. La vraie protection doit être côté GitHub.

---

## 22. Quality gates GitHub

### CI obligatoire

Sur `push` et `pull_request` :

```text
- install
- validate data
- generate profile
- lint
- format check
- security check
- dependency audit
- tests
- coverage
- generated files up-to-date
- SVG/XML validation
- link check
```

### Workflow d’auto-update

Sur schedule ou manuel :

```text
- récupère métriques GitHub
- met à jour metrics.json
- génère README/SVG
- commit automatique si changement
```

Attention : ce workflow doit avoir `contents: write`. Les autres workflows doivent rester en `contents: read`.

---

## 23. Protection de branche GitHub

Protéger `main`.

Règles recommandées :

```text
- Pull Request obligatoire
- Status checks requis
- Branch up-to-date obligatoire
- Conversation resolution obligatoire
- Force push interdit
- Suppression de branche interdite
- Linear history recommandé
- Signed commits optionnel
```

Utiliser idéalement GitHub Repository Rulesets.

---

## 24. Branching strategy

Simple et adaptée :

```text
main
feature/*
fix/*
chore/*
docs/*
```

Exemples :

```text
feature/profile-layout
feature/skill-radar
fix/svg-rendering
chore/update-deps
docs/rendering-pipeline
```

---

## 25. Conventional commits

Utiliser :

```text
feat(profile): add dynamic services section
fix(svg): escape special characters
chore(deps): update dependencies
docs(spec): document quality gates
test(generator): add deterministic generation tests
```

---

## 26. Makefile cible

```makefile
.PHONY: setup validate generate test coverage lint format security audit check

setup:
	pip install -e ".[dev]"
	pre-commit install
	pre-commit install --hook-type pre-push

validate:
	python scripts/validate_data.py

generate:
	python scripts/generate_profile.py

test:
	pytest

coverage:
	pytest --cov=scripts --cov-report=term-missing --cov-fail-under=90

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

security:
	bandit -r scripts

audit:
	pip-audit

check: validate generate lint format-check security audit coverage
	git diff --exit-code
```

---

## 27. Critères d’acceptation

### Design

```text
- Les couleurs sont visibles dans la spec Markdown via SVG externes.
- Les bannières sont visibles.
- Les cartes de services sont visibles.
- La timeline est visible.
- Les skill bars sont visibles.
- Le tech radar est visible.
- Le footer est visible.
- Aucun exemple visuel important n’est uniquement en HTML/SVG inline.
```

### Produit

```text
- Le README est généré depuis les JSON.
- Les SVG sont générés depuis les JSON.
- La génération est déterministe.
- Le repo passe make check.
- La CI rejoue les contrôles.
- main est protégée.
- les pre-commit et pre-push sont configurés.
```

### Profil

```text
- La première page explique rapidement qui je suis.
- Les services sont visibles avant les détails techniques.
- Le contact est accessible rapidement.
- Les détails techniques sont riches mais organisés.
- Le parcours est lisible sous forme de timeline.
- La stack est détaillée avec versions, niveaux et années.
- La méthode de travail est explicite.
- Le profil montre professionnalisme, compétence et polyvalence.
```

---

## 28. MVP recommandé

### V1

```text
- data/identity.json
- data/services.json
- data/skills.json
- data/projects.json
- data/experience.json
- templates/README.md.j2
- templates/svg/hero.svg.j2
- templates/svg/services.svg.j2
- templates/svg/skill-bars.svg.j2
- README.md généré
- 3 SVG générés
- tests génération
- tests data
- ruff
- bandit
- pip-audit
- pre-commit
- pre-push
- GitHub Actions CI
```

### V2

```text
- tech-radar.svg
- timeline.svg
- GitHub metrics
- update-profile workflow
- link checker
- Dependabot
- branch ruleset documenté
```

### V3

```text
- thèmes multiples
- bilingue EN/FR
- preview Markdown enrichie
- export portfolio web optionnel
- CLI complet
```

---

## 29. Footer visuel

![Footer](assets/preview/footer.svg)

Le footer doit rappeler :

- disponibilité ;
- contact ;
- positionnement ;
- personnalité ;
- continuité avec le thème visuel.

---

## 30. Décision finale

Le bon format n’est pas :

```text
README décoré à la main
```

Le bon format est :

```text
GitHub Profile Generator
```

Avec :

```text
Données JSON
+
Templates Markdown/SVG
+
Assets générés
+
Tests
+
Quality gates
+
CI
+
Branch protection
```

Le profil final doit donner cette impression :

> Je suis un CTO/developer senior capable de structurer un système complexe, de l’automatiser, de le tester, de le sécuriser et de le rendre lisible.

Et le dépôt lui-même doit le prouver.
