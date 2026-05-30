#!/usr/bin/env python3
"""
fetch_metrics.py — Fetch and aggregate GitHub account metrics for the weekly
update-profile workflow.

Repos are listed via the GitHub CLI ('gh'); only non-fork repositories count
toward public_repos and total_stars. The aggregation logic (compute_metrics)
is pure and network-free so it can be unit-tested in isolation. The CLI
main() wires the 'gh' call to it and writes data/metrics.json.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import subprocess  # nosec
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DATA = _REPO_ROOT / "data"


def compute_metrics(repos: list[dict], username: str, today: str) -> dict:
    """Aggregate raw 'gh repo list' entries into a metrics object.

    Only non-fork repositories are counted. Returns a dict matching
    schemas/metrics.schema.json. This function performs no I/O.

    Args:
        repos: Repo entries with keys 'isFork', 'stargazerCount', 'pushedAt'.
        username: The GitHub account login.
        today: ISO date (YYYY-MM-DD) used as fetched_at.
    """
    owned = [repo for repo in repos if not repo.get("isFork", False)]

    public_repos = len(owned)
    total_stars = sum(repo.get("stargazerCount", 0) for repo in owned)

    push_dates = [repo["pushedAt"][:10] for repo in owned if repo.get("pushedAt")]
    last_push = max(push_dates) if push_dates else today

    return {
        "username": username,
        "public_repos": public_repos,
        "total_stars": total_stars,
        "last_push": last_push,
        "fetched_at": today,
    }


def _fetch_repos(username: str) -> list[dict]:
    """List the account's source repos via the GitHub CLI."""
    # Fixed argument list, shell=False, check=True: no untrusted input is
    # interpolated into a shell, so this subprocess call is safe.
    result = subprocess.run(  # nosec
        [
            "gh",
            "repo",
            "list",
            username,
            "--source",
            "--limit",
            "200",
            "--json",
            "name,isFork,stargazerCount,pushedAt",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    username = "Rinzler78"
    today = datetime.date.today().isoformat()

    repos = _fetch_repos(username)
    metrics = compute_metrics(repos, username, today)

    out_path = DATA / "metrics.json"
    out_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    print(
        f"[fetch_metrics.py] {username}: {metrics['public_repos']} repos, "
        f"{metrics['total_stars']} stars, last push {metrics['last_push']} "
        f"-> {out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
