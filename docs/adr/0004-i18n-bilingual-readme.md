# ADR-004 — FR/EN bilingualism with DeepL translation and committed cache

- **Status**: Accepted
- **Date**: 2026-05-27
- **Related to**: [ADR-001](0001-data-driven-svg-generation.md), [ADR-003](0003-data-schema-collections-and-derived-views.md)

## Context

The profile targets two markets: France (natural input language, narrative prose) and international (EN-only clients, English-speaking recruiters). GitHub Profile offers **no** native language negotiation mechanism: a single `README.md` is served.

The internal rule (memory `feedback_bilingual_rule`) mandates FR for intros/prose and EN for raw technical content. Multilingualism must respect this boundary without manually duplicating each input.

## Decision

### 1. Two files generated from a single source

The generator produces:
- `README.md` (FR, default language served by GitHub)
- `README.en.md` (EN, accessible via a Markdown link at the top)

Each README carries at the top a reciprocal link to the other language (text or clickable SVG image).

### 2. Form of i18n fields

- **Narrative** field (titles, descriptions, prose, pitch): `{ "fr": "..." }` at input. The hook produces `{ "fr": "...", "en": "..." }` after translation, but the EN lives in the cache, not in `data/`.
- **Factual** field (id, name, dates, URLs, tech labels, technical keywords, score): simple string/number, not i18n.

### 3. Translation by DeepL

- Engine: **DeepL Free** (`:fx` suffix on the key), 500k chars/month — largely sufficient for this volume.
- Secret: `DEEPL_API_KEY` in `.env` (local, gitignored) and a GitHub Secret of the same name (CI).
- If the key is absent or the API is down → the hook **fails** (no bypass — CLAUDE.md rule `no lazy mechanism`).

### 4. Translation cache

Cache committed under `data/i18n-cache/<entity>/<id>.<field>.en.json`:

```json
{
  "fr_hash": "ab12cd34...",
  "en": "I help companies design...",
  "manual": false,
  "reviewed": false
}
```

- `fr_hash`: SHA-256 of the FR that served to produce `en`.
- `manual: true`: Boris edited `en` by hand. The hook **never** touches this entry, even if FR changes (warning only).
- `reviewed: true`: Boris validated that the auto translation is correct. **Non-blocking**: if `false`, generation of `README.en.md` proceeds, but a warning is visible in the hook output.

### 5. Pre-commit workflow

1. Scan `data/*.json`, list the i18n fields
2. For each field: compute `hash(fr_current)`
3. If cache is absent **or** (`hash != cache.fr_hash` **and** `manual == false`):
   - Call DeepL with `source_lang=FR, target_lang=EN-US`
   - Write the cache with `manual: false, reviewed: false`
4. Generate `README.md` (FR) and `README.en.md` (EN, from the cache)
5. Display a recap of the `reviewed: false` caches (warning)

### 6. Security

- The DeepL Free key has a limited impact (quota), but remains a secret.
- `.env` is explicitly listed in `.gitignore`.
- `.env.example` documents the variable without the value.
- CI uses the GitHub Secret, never the plaintext value in the workflow.

## Consequences

### Positive

- FR input only (minimal editorial effort).
- DeepL FR↔EN quality recognized as excellent.
- Determinism: same FR → same EN (via cache), double-generation tests pass.
- Full audit of the EN diff in PRs (committed cache).
- Boris can override manually (`manual: true`) for passages where DeepL gets it wrong.

### Negative

- External API dependency in the commit workflow (key absent → blocking).
- Modest but non-zero cost if 500k chars/month is exceeded (very unlikely for a README).
- The non-blocking `reviewed: false` flag means unreviewed AI translation can be published — risk of subtle inflation. Mitigation: visible warning + disciplined periodic review.
- Doubling of the cache file base to maintain (but auto-generated).
