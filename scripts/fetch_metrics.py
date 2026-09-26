#!/usr/bin/env python3
"""
fetch_metrics.py — Fetch the GitHub account metrics and the per-project
external counters for the daily update-profile workflow.

Account metrics: repos are listed via the GitHub CLI ('gh'); only non-fork
repositories count toward public_repos and total_stars.

External counters: each project declares its sources in data/projects.json
under ``metrics`` ({"pypi": <package>} and/or {"dockerhub": <owner/repo>}).
Counters are never hard-coded: they are fetched on every run and each project
entry carries its own ``fetched_at``, distinct from the activity date. A
failing source keeps the previous value from data/metrics.json and records the
error, so a run never zeroes a counter.

Parsing and aggregation are pure and network-free (unit-tested with injected
fetchers). The CLI main() wires 'gh' and HTTP to them and writes
data/metrics.json.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import subprocess  # nosec
import sys
from collections.abc import Callable

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DATA = _REPO_ROOT / "data"

HTTP_TIMEOUT_SECONDS = 15
USER_AGENT = "Rinzler78-profile-metrics (+https://github.com/Rinzler78/Rinzler78)"

PYPISTATS_URL = "https://pypistats.org/api/packages/{package}/recent"
PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"
DOCKERHUB_URL = "https://hub.docker.com/v2/repositories/{repository}/"

Fetcher = Callable[[str], object]


class SourceError(Exception):
    """An external source could not be fetched or returned an unusable payload."""


def compute_metrics(repos: list[dict], username: str, today: str) -> dict:
    """Aggregate raw 'gh repo list' entries into the account metrics.

    Only non-fork repositories are counted. This function performs no I/O.

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


# --- Payload parsers (pure) -------------------------------------------------


def _count(value: object, what: str) -> int:
    # bool is a subclass of int: reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceError(f"{what}: expected a non-negative integer, got {value!r}")
    return value


def parse_pypi_downloads_last_month(payload: object) -> int:
    """Downloads over the last month from a pypistats 'recent' payload."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise SourceError("pypistats: missing data object")
    return _count(data.get("last_month"), "pypistats last_month")


def parse_pypi_release_count(payload: object) -> int:
    """Number of published releases from a PyPI JSON API payload."""
    releases = payload.get("releases") if isinstance(payload, dict) else None
    if not isinstance(releases, dict):
        raise SourceError("pypi: missing releases mapping")
    return len(releases)


def parse_docker_pulls(payload: object) -> int:
    """Total pull count from a Docker Hub repository payload."""
    if not isinstance(payload, dict):
        raise SourceError("dockerhub: payload is not an object")
    return _count(payload.get("pull_count"), "dockerhub pull_count")


# --- Aggregation (pure) -------------------------------------------------------


def _repo_key(name: str) -> str:
    return name.lower().replace("_", "-")


def project_stars(projects: list[dict], repos: list[dict]) -> dict[str, int]:
    """Map project ids to the stargazer count of their GitHub repository.

    Repos are matched on the last segment of ``github_url``, ignoring case and
    '_' versus '-'. Projects without a matching repo are left out.
    """
    by_name = {
        _repo_key(repo["name"]): repo.get("stargazerCount", 0)
        for repo in repos
        if repo.get("name")
    }
    stars: dict[str, int] = {}
    for project in projects:
        name = project.get("github_url", "").rstrip("/").rsplit("/", 1)[-1]
        key = _repo_key(name)
        if key in by_name:
            stars[project["id"]] = by_name[key]
    return stars


def _source_fetches(sources: dict) -> list[tuple[str, str, str, Callable]]:
    """(source, counter, url, parser) for every counter a project declares."""
    fetches = []
    if "pypi" in sources:
        package = sources["pypi"]
        fetches.append(
            (
                "pypi",
                "pypi_downloads_last_month",
                PYPISTATS_URL.format(package=package),
                parse_pypi_downloads_last_month,
            )
        )
        fetches.append(
            (
                "pypi",
                "pypi_releases",
                PYPI_JSON_URL.format(package=package),
                parse_pypi_release_count,
            )
        )
    if "dockerhub" in sources:
        fetches.append(
            (
                "dockerhub",
                "docker_pulls",
                DOCKERHUB_URL.format(repository=sources["dockerhub"]),
                parse_docker_pulls,
            )
        )
    return fetches


def collect_external(
    projects: list[dict],
    fetch: Fetcher,
    stars: dict[str, int] | None,
    previous: dict[str, dict],
    today: str,
) -> tuple[dict[str, dict], list[dict]]:
    """Fetch every project's external counters.

    A counter whose source fails keeps its previous value (never zeroed); the
    failure is recorded. An entry's ``fetched_at`` is ``today`` only when no
    value was carried over; otherwise it keeps the previous date, so it always
    reflects the oldest value in the entry.

    Args:
        projects: data/projects.json entries.
        fetch: url -> decoded JSON; raises SourceError on failure.
        stars: project id -> stars, or None when the GitHub listing failed.
        previous: the ``external`` mapping of the last data/metrics.json.
        today: ISO date of this run.

    Returns:
        (external mapping, list of {project, source, message} errors).
    """
    external: dict[str, dict] = {}
    errors: list[dict] = []

    for project in projects:
        pid = project["id"]
        before = previous.get(pid, {})
        entry: dict = {}
        carried = False

        for source, counter, url, parser in _source_fetches(project.get("metrics", {})):
            try:
                entry[counter] = parser(fetch(url))
            except SourceError as e:
                errors.append({"project": pid, "source": source, "message": str(e)})
                if counter in before:
                    entry[counter] = before[counter]
                    carried = True

        if stars is None:
            if "stars" in before:
                entry["stars"] = before["stars"]
                carried = True
        elif pid in stars:
            entry["stars"] = stars[pid]

        if entry:
            entry["fetched_at"] = before["fetched_at"] if carried else today
            external[pid] = entry

    return external, errors


def build_document(account: dict, external: dict, errors: list[dict]) -> dict:
    """Assemble data/metrics.json from its parts (schemas/metrics.schema.json)."""
    return {**account, "external": external, "errors": errors}


# --- I/O ------------------------------------------------------------------------


def http_get_json(url: str) -> object:
    """GET a JSON document; any transport or decoding failure is a SourceError."""
    # Imported lazily so the pure functions import without the package
    # installed (the test hook environments only carry the core deps).
    import requests

    try:
        response = requests.get(
            url,
            timeout=HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
        raise SourceError(f"{url}: {e}") from e


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


def _load_json(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    username = "Rinzler78"
    today = datetime.date.today().isoformat()
    out_path = DATA / "metrics.json"
    previous = _load_json(out_path)
    projects = json.loads((DATA / "projects.json").read_text(encoding="utf-8"))
    errors: list[dict] = []

    try:
        repos = _fetch_repos(username)
    except (OSError, subprocess.CalledProcessError, ValueError) as e:
        errors.append({"project": "*", "source": "github", "message": str(e)})
        account_keys = ("username", "public_repos", "total_stars", "last_push")
        if not all(key in previous for key in account_keys):
            print(f"[fetch_metrics.py] gh failed with no history: {e}", file=sys.stderr)
            return 1
        account = {key: previous[key] for key in (*account_keys, "fetched_at")}
        stars = None
    else:
        account = compute_metrics(repos, username, today)
        stars = project_stars(projects, repos)

    external, source_errors = collect_external(
        projects, http_get_json, stars, previous.get("external", {}), today
    )
    errors.extend(source_errors)

    document = build_document(account, external, errors)
    out_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    for err in errors:
        # GitHub Actions annotation: visible on the run without failing it.
        print(
            f"::warning::{err['project']} [{err['source']}] {err['message']}",
            file=sys.stderr,
        )
    print(
        f"[fetch_metrics.py] {username}: {account['public_repos']} repos, "
        f"{account['total_stars']} stars, {len(external)} projects with external "
        f"counters, {len(errors)} source errors -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
