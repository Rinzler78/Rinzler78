# ADR-014 — Claims admitted only with evidence the author holds

- **Status**: Accepted
- **Date**: 2026-09-26
- **Related to**: [ADR-013](0013-activity-timeline-evidence-hours.md), [ADR-015](0015-front-page-v2-grid-palette-type.md)

## Context

The profile states facts about a career: awards, clients, figures of impact, what a
project is used for. The 2026-09-26 audit checked the statements published so far:

- Some are **true and publicly sourced**: the 2017 French road-safety innovation award
  won by the connected-breathalyzer product, and its white-label deployments for two
  large corporate clients, both reported by the trade press.
- Some are **measurable**: a Python package on PyPI with eight releases and about 320
  downloads a month; stars, forks and contributors of each public repository.
- Some were **unfounded**: one repository was described as "used by the crypto
  community" (6 stars, no fork, a single contributor), another as "community-driven,
  regularly updated" (a single contributor, no push for fifteen months).
- Others are **plausible but without a public source**: unit volumes, availability and
  satisfaction percentages copied from a résumé.

A rule of "publicly verifiable only" was considered and refined. Much true work cannot
be public — it belongs to an employer or a client, or is not presentable as code — and
still counts. The line the author draws is not public versus private: **a statement is
admitted if it is true and the author can prove it; nothing is invented.**

That rule needs a mechanism, because a regeneration can reintroduce a sentence nobody
re-checked, and because the proof of a private fact must not leak through a public
repository — not even as a file name.

## Decision

### 1. Admission rule

A statement appears on the profile only if it carries one of:

- a **public source** cited on the page (an article, a registry, a store listing);
- a **measurable artefact** read at generation time (repository metrics, package
  statistics, the aggregates of ADR-013);
- a **private attestation**: an entry of the author's private registry pointing to the
  evidence he holds.

Anything else is removed, however flattering or plausible.

### 2. The registry is private; the repository carries identifiers

The registry lives in the author's private knowledge base, outside this repository.
Each entry holds a claim identifier, the public wording, the kind of evidence, a
pointer to it, and the date it was attested. The same private space holds the
repository classification of ADR-013 (context, organization, visibility, whether a
project may be named) and the exceptions to the employment record.

This repository only carries **claim identifiers** next to the content that states them,
and a committed **lock file** listing, for each identifier, a hash of its public wording
and its attestation date — no evidence, no pointer, no private text.

### 3. Two checks

- **Locally, before publishing** (where the registry is reachable): every identifier in
  the content resolves to a registry entry with evidence; the lock file is rewritten
  from the registry.
- **In CI** (where it is not): every identifier in the content appears in the lock
  file, and the hash of the wording on the page matches the locked hash. Rewording a
  claim without re-attesting it fails the build.

### 4. Framing rules

- The employment record (the professional network profile) is authoritative for
  **dates and job titles**, never for achievements; each achievement goes through the
  registry like any other claim.
- An achievement of a company or a product is presented as such, with the author's own
  role stated — "the product whose apps I built won …", never "I won …".
- Private projects may be named and described, without a link, unless the registry
  marks them as not nameable. An employer's internal repositories are never named; only
  its public products are.
- Private life context — health, finances, family, employment status between
  contracts — is never published, even when true. When in doubt, it is left out.

## Considered options

- **Public verifiability only** — rejected by the author: it erases true work that
  cannot be public and treats absence of a public source as falsehood.
- **Registry committed in this repository, sanitized** — every sanitized description
  still leaks something (a client's name, a document's existence). Rejected.
- **No registry, the author re-reads before each publication** — the drift this ADR
  exists to stop happened under exactly that regime. Rejected.

## Consequences

**Positive**
- Every statement on the page is either sourced in public, measured, or attested in
  private — and CI enforces that it was not reworded behind the attestation.
- The unfounded descriptions found by the audit are removed until attested or rewritten.

**Negative**
- Publishing a new claim needs a registry entry first; CI alone cannot attest a claim.
- The lock file proves that an attestation happened, not what the evidence is; trust
  in private evidence remains trust in the author, stated as such by the page.

## Success criteria

- Every claim marker in the generated content resolves in the lock file, with a
  matching hash, in CI.
- No string of the private registry (pointer, file name, client name marked
  non-public) appears anywhere in this repository.
- The two unfounded repository descriptions are absent from every generated page.
