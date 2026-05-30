#!/usr/bin/env bash
#
# setup_branch_protection.sh — Reference script (NOT auto-run).
#
# Creates the GitHub Repository Ruleset that protects the default branch
# (`master`) of Rinzler78/Rinzler78, as decided in ADR-005 and documented in
# docs/branch-protection.md.
#
# This is an OUTWARD-FACING, OWNER-OPERATED script: it is applied once, by hand,
# by the repository owner. It is NOT part of CI — no workflow has (or should have)
# the `administration: write` scope needed to manage rulesets. CI only consumes
# the required status checks this ruleset declares.
#
# Requirements:
#   - GitHub CLI `gh` authenticated as an account with admin rights on the repo
#     (run `gh auth login` first; verify with `gh auth status`).
#   - `gh` token scope must include `admin:repo` / repository administration.
#
# Usage:
#   scripts/setup_branch_protection.sh            # prints this usage and exits
#   scripts/setup_branch_protection.sh --apply    # actually creates the ruleset
#
# The script refuses to touch the GitHub API unless `--apply` is passed
# explicitly, so sourcing or running it by accident is a no-op.

set -euo pipefail

# --- Configuration ----------------------------------------------------------
# Target repository and the default branch this ruleset protects.
readonly OWNER="Rinzler78"
readonly REPO="Rinzler78"
readonly DEFAULT_BRANCH="master"
readonly RULESET_NAME="protect-default-branch"

# Required status checks: these are the CI job names reported by
# .github/workflows/ci.yml. They MUST stay in sync with that workflow — if a job
# is renamed there, update this list, otherwise PRs wait on a check that never
# arrives. See docs/branch-protection.md ("Required status checks — naming").
readonly CHECK_QUALITY="quality"
readonly CHECK_TESTS="tests"

# --- Usage / guard ----------------------------------------------------------
usage() {
  cat <<USAGE
setup_branch_protection.sh — create the '${RULESET_NAME}' ruleset.

Targets : ${OWNER}/${REPO}, default branch '${DEFAULT_BRANCH}'
Enforces: PR required, required checks (${CHECK_QUALITY}, ${CHECK_TESTS}),
          up-to-date-before-merge, linear history, conversation resolution,
          no force-push, no deletion, signed commits required.

Usage:
  $0            Show this message (no changes made).
  $0 --apply    Create the ruleset on ${OWNER}/${REPO} (requires admin 'gh' auth).

This script makes NO changes unless '--apply' is passed. It never deletes an
existing ruleset; to modify one, edit it in the GitHub UI or adapt the call to
'PATCH /repos/${OWNER}/${REPO}/rulesets/{id}'.
USAGE
}

# Require an explicit confirmation argument. Anything other than '--apply'
# (including no argument) prints usage and exits without calling the API.
if [[ "${1:-}" != "--apply" ]]; then
  usage
  exit 0
fi

# --- Preflight checks -------------------------------------------------------
# Fail early with a clear message if the CLI is missing or not authenticated,
# rather than surfacing an opaque API error mid-run.
if ! command -v gh >/dev/null 2>&1; then
  echo "error: GitHub CLI 'gh' is not installed. See https://cli.github.com/" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "error: 'gh' is not authenticated. Run 'gh auth login' first." >&2
  exit 1
fi

# --- Confirmation prompt ----------------------------------------------------
# Even with --apply, ask for an interactive yes/no so an accidental --apply in a
# script or shell history does not silently mutate repository settings.
echo "About to create ruleset '${RULESET_NAME}' on ${OWNER}/${REPO}"
echo "protecting the default branch '${DEFAULT_BRANCH}'."
read -r -p "Proceed? [y/N] " reply
if [[ "${reply}" != "y" && "${reply}" != "Y" ]]; then
  echo "Aborted. No changes made."
  exit 0
fi

# --- Create the ruleset -----------------------------------------------------
# We POST a single Repository Ruleset payload. Rule semantics (see
# docs/branch-protection.md for the full mapping):
#   - pull_request                : PR mandatory; required_review_thread_resolution
#                                   enforces "conversation resolution".
#   - required_status_checks      : 'quality' + 'tests' must pass;
#                                   strict_required_status_checks_policy = branch
#                                   must be up to date before merge.
#   - required_linear_history     : rebase/squash only, no merge commits.
#   - non_fast_forward            : force-push forbidden.
#   - deletion                    : branch deletion forbidden.
#   - required_signatures         : signed commits required.
#
# 'target: branch' + conditions ref_name '~DEFAULT_BRANCH' scopes the ruleset to
# the repository's default branch without hard-coding a branch name in the ref
# matcher (GitHub resolves '~DEFAULT_BRANCH' to 'master' here).
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "repos/${OWNER}/${REPO}/rulesets" \
  --input - <<JSON
{
  "name": "${RULESET_NAME}",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "${CHECK_QUALITY}" },
          { "context": "${CHECK_TESTS}" }
        ]
      }
    },
    { "type": "required_linear_history" },
    { "type": "non_fast_forward" },
    { "type": "deletion" },
    { "type": "required_signatures" }
  ]
}
JSON

echo
echo "Ruleset '${RULESET_NAME}' created on ${OWNER}/${REPO}."
echo "Verify with:"
echo "  gh api repos/${OWNER}/${REPO}/rulesets --jq '.[] | {id, name, enforcement, target}'"
