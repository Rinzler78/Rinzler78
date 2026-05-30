# Branch protection — `master` ruleset

> Implementation of [ADR-005](adr/0005-quality-gates-ci-branch-protection.md),
> section 5 ("Protection of `main` / default branch").

The default branch of `Rinzler78/Rinzler78` is **`master`**. It is the source of
truth: the generated `README.md` and SVGs published on the GitHub profile are
served straight from it. Nothing may land on `master` without passing the full
CI cycle, and the branch history must stay clean and reproducible.

This protection is expressed as a **GitHub Repository Ruleset** (the modern
replacement for classic "branch protection rules"). It is **applied manually by
the repository owner**, once, via the GitHub UI or the reference script
[`scripts/setup_branch_protection.sh`](../scripts/setup_branch_protection.sh).
It is **not** created or maintained by CI — CI only _consumes_ it (the required
status checks below are produced by the `ci.yml` workflow). Keeping the ruleset
out of CI avoids granting any workflow `administration: write`, which keeps the
default `contents: read` permission posture described in ADR-005.

## Target

| Setting          | Value                          |
| ---------------- | ------------------------------ |
| Repository       | `Rinzler78/Rinzler78`          |
| Ruleset target   | Default branch (`master`)      |
| Enforcement      | `active`                       |
| Bypass actors    | None (the owner is _not_ a bypass actor — even solo work goes through a PR) |

## Rules

The ruleset enforces the following, each mapping to a rule type in the GitHub
Rulesets API:

| Rule                              | Ruleset rule type            | Effect |
| --------------------------------- | ---------------------------- | ------ |
| **Pull request required**         | `pull_request`               | No direct push to `master`; every change lands through a PR. Forces the PR + CI workflow even for solo work. |
| **Required status checks**        | `required_status_checks`     | A PR can only merge once the CI jobs **`quality`** and **`tests`** (from `.github/workflows/ci.yml`) report success. |
| **Branch up-to-date before merge**| `required_status_checks` → `strict_required_status_checks_policy: true` | The PR head must be rebased on the latest `master` before the checks count, so checks run against the exact tree that will land. |
| **Linear history**                | `required_linear_history`    | No merge commits — rebase/squash only. Keeps `master` a straight line, consistent with the trunk-based, rebase-only flow. |
| **Conversation resolution**       | `pull_request` → `required_review_thread_resolution: true` | All review threads must be resolved before merge. |
| **Force-push forbidden**          | `non_fast_forward`           | History on `master` cannot be rewritten / overwritten. |
| **Deletion forbidden**            | `deletion`                   | `master` cannot be deleted. |
| **Signed commits required**       | `required_signatures`        | Every commit on `master` must carry a valid signature. Free to honour since the global tooling already forbids `--no-gpg-sign`. |

### Required status checks — naming

The check names in the ruleset must match the **job names** GitHub reports, which
are the `jobs.<id>.name` (or the job id when no `name:` is set) from
`.github/workflows/ci.yml`. The current workflow exposes:

- `quality` — lint, security scan, generation diff, data validation.
- `tests` — pytest, coverage gate, dependency vulnerability audit.

If a job is renamed in `ci.yml`, the ruleset's required checks must be updated in
lockstep, otherwise the PR will wait forever on a check that is never reported.

## How it is applied

1. The owner runs the reference script (or performs the equivalent steps in
   **Settings → Rules → Rulesets → New branch ruleset** in the GitHub UI).
2. The script targets the default branch and creates the ruleset described above.
3. From then on, any push to `master` is rejected; work happens on
   `feature/<slug>` branches (in `.worktrees/<slug>/`, per the repo conventions),
   opened as PRs, merged once `quality` and `tests` are green.

The script is **idempotent-friendly** but **not destructive**: it requires an
explicit confirmation argument before touching the GitHub API, and it never
deletes an existing ruleset. To update an existing ruleset, edit it in the UI or
adapt the API call to `PATCH /repos/{owner}/{repo}/rulesets/{id}`.

## Verification

After applying, confirm the ruleset exists and is active:

```bash
gh api repos/Rinzler78/Rinzler78/rulesets --jq '.[] | {id, name, enforcement, target}'
```

A subsequent direct push attempt to `master` must be rejected by the server, and
a PR must show `quality` and `tests` as required checks before the merge button
unlocks.

## See also

- [ADR-005 — Quality gates, CI and default-branch protection](adr/0005-quality-gates-ci-branch-protection.md)
- [`scripts/setup_branch_protection.sh`](../scripts/setup_branch_protection.sh) — reference command sequence
- [GitHub Rulesets REST API](https://docs.github.com/en/rest/repos/rules)
