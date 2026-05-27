# ADR-004 — Bilinguisme FR/EN avec traduction DeepL et cache committé

- **Statut** : Accepted
- **Date** : 2026-05-27
- **Lié à** : [ADR-001](0001-data-driven-svg-generation.md), [ADR-003](0003-data-schema-collections-and-derived-views.md)

## Contexte

Le profil cible deux marchés : France (langue de saisie naturelle, prose narrative) et international (clients EN-only, recruteurs anglophones). GitHub Profile ne propose **aucun** mécanisme natif de négociation de langue : un seul `README.md` est servi.

La règle interne (mémoire `feedback_bilingual_rule`) impose FR pour intros/prose et EN pour le contenu technique brut. Multi-langue doit respecter cette frontière sans doubler manuellement chaque saisie.

## Décision

### 1. Deux fichiers générés depuis une seule source

Le generator produit :
- `README.md` (FR, langue par défaut servi par GitHub)
- `README.en.md` (EN, accessible via lien Markdown en tête)

Chaque README porte en haut un lien réciproque vers l'autre langue (texte ou image SVG cliquable).

### 2. Forme des champs i18n

- Champ **narratif** (titres, descriptions, prose, pitch) : `{ "fr": "..." }` à la saisie. Le hook produit `{ "fr": "...", "en": "..." }` après traduction, mais l'EN vit dans le cache, pas dans `data/`.
- Champ **factuel** (id, name, dates, URLs, tech labels, keywords techniques, score) : string/number simple, non i18n.

### 3. Traduction par DeepL

- Moteur : **DeepL Free** (suffixe `:fx` sur la clé), 500k chars/mois — largement suffisant pour ce volume.
- Secret : `DEEPL_API_KEY` en `.env` (local, gitignored) et GitHub Secret du même nom (CI).
- Si la clé est absente ou l'API down → le hook **échoue** (pas de bypass — règle CLAUDE.md `pas de mécanisme paresseux`).

### 4. Cache de traductions

Cache committé sous `data/i18n-cache/<entity>/<id>.<field>.en.json` :

```json
{
  "fr_hash": "ab12cd34...",
  "en": "I help companies design...",
  "manual": false,
  "reviewed": false
}
```

- `fr_hash` : SHA-256 du FR ayant servi à produire `en`.
- `manual: true` : Boris a édité `en` à la main. Le hook ne touche **jamais** à cette entrée, même si FR change (warning seulement).
- `reviewed: true` : Boris a validé que la traduction auto est correcte. **Non bloquant** : si `false`, génération de `README.en.md` procède, mais warning visible dans le hook output.

### 5. Workflow pre-commit

1. Scanner `data/*.json`, lister les champs i18n
2. Pour chaque champ : calculer `hash(fr_actuel)`
3. Si cache absent **ou** (`hash != cache.fr_hash` **et** `manual == false`) :
   - Appeler DeepL avec `source_lang=FR, target_lang=EN-US`
   - Écrire le cache avec `manual: false, reviewed: false`
4. Générer `README.md` (FR) et `README.en.md` (EN, depuis le cache)
5. Afficher un récap des caches `reviewed: false` (warning)

### 6. Sécurité

- La clé DeepL Free a un impact limité (quota), mais reste un secret.
- `.env` est explicitement listé dans `.gitignore`.
- `.env.example` documente la variable sans la valeur.
- CI utilise le GitHub Secret, jamais la valeur en clair dans le workflow.

## Conséquences

### Positives

- Saisie FR seule (effort éditorial minimal).
- Qualité DeepL FR↔EN reconnue comme excellente.
- Déterminisme : même FR → même EN (via cache), tests de double génération passent.
- Audit complet du diff EN dans les PR (cache committé).
- Boris peut overrider manuellement (`manual: true`) pour les passages où DeepL se trompe.

### Négatives

- Dépendance API externe au workflow de commit (clé absente → blocage).
- Coût modeste mais non nul si on dépasse 500k chars/mois (très improbable pour un README).
- Le flag `reviewed: false` non bloquant signifie que de la trad IA non revue peut être publiée — risque de gonflage subtil. Mitigation : warning visible + revue périodique disciplinée.
- Doublement de la base de fichiers de cache à maintenir (mais auto-générés).
