"""Behavior specs for fetch_metrics (pure aggregation and parsing, no network)."""

import json
import sys
import types
from pathlib import Path

import jsonschema
import pytest

from scripts.fetch_metrics import (
    SourceError,
    build_document,
    collect_external,
    compute_metrics,
    http_get_json,
    parse_docker_pulls,
    parse_pypi_downloads_last_month,
    parse_pypi_release_count,
    project_stars,
)

# Mix of forks/non-forks, varying stars, varying push dates.
REPOS = [
    {
        "name": "owned-a",
        "isFork": False,
        "stargazerCount": 12,
        "pushedAt": "2026-05-20T10:00:00Z",
    },
    {
        "name": "owned-b",
        "isFork": False,
        "stargazerCount": 3,
        "pushedAt": "2026-01-02T08:30:00Z",
    },
    {
        "name": "owned-c",
        "isFork": False,
        "stargazerCount": 0,
        "pushedAt": "2025-11-15T23:59:00Z",
    },
    {
        "name": "forked-x",
        "isFork": True,
        "stargazerCount": 999,
        "pushedAt": "2026-05-30T00:00:00Z",
    },
]


def test_public_repos_counts_only_non_forks():
    result = compute_metrics(REPOS, "Rinzler78", "2026-05-30")

    assert result["public_repos"] == 3


def test_total_stars_sums_only_non_fork_stargazers():
    result = compute_metrics(REPOS, "Rinzler78", "2026-05-30")

    # 12 + 3 + 0, the forked repo's 999 stars are excluded.
    assert result["total_stars"] == 15


def test_last_push_is_max_push_date_among_non_forks():
    result = compute_metrics(REPOS, "Rinzler78", "2026-05-30")

    # The fork has the latest push but is excluded; newest owned is owned-a.
    assert result["last_push"] == "2026-05-20"


def test_username_and_fetched_at_are_passed_through():
    result = compute_metrics(REPOS, "Rinzler78", "2026-05-30")

    assert result["username"] == "Rinzler78"
    assert result["fetched_at"] == "2026-05-30"


def test_result_has_exactly_the_schema_keys():
    result = compute_metrics(REPOS, "Rinzler78", "2026-05-30")

    assert set(result) == {
        "username",
        "public_repos",
        "total_stars",
        "last_push",
        "fetched_at",
    }


def test_no_owned_repos_falls_back_to_today_for_last_push():
    only_forks = [
        {
            "name": "f1",
            "isFork": True,
            "stargazerCount": 5,
            "pushedAt": "2026-05-30T00:00:00Z",
        },
    ]

    result = compute_metrics(only_forks, "Rinzler78", "2026-05-30")

    assert result["public_repos"] == 0
    assert result["total_stars"] == 0
    assert result["last_push"] == "2026-05-30"


def test_missing_optional_fields_default_to_zero_and_skip():
    sparse = [
        {"name": "no-stars", "isFork": False},
        {"name": "with-push", "isFork": False, "pushedAt": "2026-03-01T12:00:00Z"},
    ]

    result = compute_metrics(sparse, "Rinzler78", "2026-05-30")

    assert result["public_repos"] == 2
    assert result["total_stars"] == 0
    assert result["last_push"] == "2026-03-01"


# --- External counters (PyPI, Docker Hub, GitHub stars) --------------------
#
# Every counter is fetched, never hard-coded, and carries its own fetch date.
# The fetcher is injected so these specs never touch the network.

ROOT = Path(__file__).resolve().parent.parent
TODAY = "2026-09-26"
PYPISTATS = "https://pypistats.org/api/packages/pkg-a/recent"
PYPI_JSON = "https://pypi.org/pypi/pkg-a/json"
DOCKER = "https://hub.docker.com/v2/repositories/owner/img-b/"

PROJECTS = [
    {
        "id": "proj-a",
        "github_url": "https://github.com/Rinzler78/Repo_A",
        "metrics": {"pypi": "pkg-a"},
    },
    {
        "id": "proj-b",
        "github_url": "https://github.com/Rinzler78/repo-b",
        "metrics": {"dockerhub": "owner/img-b"},
    },
    {"id": "proj-c", "github_url": "https://github.com/Rinzler78/unknown-repo"},
]

PAYLOADS = {
    PYPISTATS: {"data": {"last_day": 2, "last_month": 320, "last_week": 78}},
    PYPI_JSON: {"releases": {"1.0": [], "1.1": [], "2.0": []}},
    DOCKER: {"name": "img-b", "pull_count": 1671},
}


def _fetcher(payloads: dict, failing: frozenset = frozenset()):
    def fetch(url: str) -> dict:
        if url in failing:
            raise SourceError(f"boom on {url}")
        return payloads[url]

    return fetch


def test_parse_pypi_downloads_reads_last_month():
    assert parse_pypi_downloads_last_month(PAYLOADS[PYPISTATS]) == 320


def test_parse_pypi_release_count_counts_releases():
    assert parse_pypi_release_count(PAYLOADS[PYPI_JSON]) == 3


def test_parse_docker_pulls_reads_pull_count():
    assert parse_docker_pulls(PAYLOADS[DOCKER]) == 1671


@pytest.mark.parametrize(
    ("parser", "payload"),
    [
        (parse_pypi_downloads_last_month, {}),
        (parse_pypi_downloads_last_month, {"data": {"last_month": -1}}),
        (parse_pypi_downloads_last_month, {"data": {"last_month": "320"}}),
        (parse_pypi_release_count, {"releases": []}),
        (parse_pypi_release_count, {}),
        (parse_docker_pulls, {"pull_count": None}),
        (parse_docker_pulls, {"pull_count": True}),
        (parse_docker_pulls, []),
    ],
)
def test_parsers_reject_malformed_payloads(parser, payload):
    with pytest.raises(SourceError):
        parser(payload)


def test_project_stars_matches_repos_by_github_url_case_insensitively():
    repos = [
        {"name": "repo_a", "stargazerCount": 4},
        {"name": "Repo-B", "stargazerCount": 0},
        {"name": "not-a-project", "stargazerCount": 9},
    ]

    assert project_stars(PROJECTS, repos) == {"proj-a": 4, "proj-b": 0}


def test_collect_external_fetches_every_declared_source():
    external, errors = collect_external(
        PROJECTS, _fetcher(PAYLOADS), {"proj-a": 4, "proj-b": 1}, {}, TODAY
    )

    assert errors == []
    assert external == {
        "proj-a": {
            "pypi_downloads_last_month": 320,
            "pypi_releases": 3,
            "stars": 4,
            "fetched_at": TODAY,
        },
        "proj-b": {"docker_pulls": 1671, "stars": 1, "fetched_at": TODAY},
    }


def test_failing_source_keeps_previous_value_and_date_and_records_error():
    previous = {
        "proj-b": {"docker_pulls": 1500, "stars": 1, "fetched_at": "2026-09-20"}
    }

    external, errors = collect_external(
        PROJECTS,
        _fetcher(PAYLOADS, frozenset({DOCKER})),
        {"proj-a": 4, "proj-b": 2},
        previous,
        TODAY,
    )

    assert external["proj-b"] == {
        "docker_pulls": 1500,
        "stars": 2,
        "fetched_at": "2026-09-20",
    }
    assert errors == [
        {
            "project": "proj-b",
            "source": "dockerhub",
            "message": f"boom on {DOCKER}",
        }
    ]
    # The healthy project is untouched by its neighbor's failure.
    assert external["proj-a"]["fetched_at"] == TODAY


def test_failing_source_never_zeroes_a_counter():
    previous = {
        "proj-a": {
            "pypi_downloads_last_month": 300,
            "pypi_releases": 2,
            "fetched_at": "2026-09-25",
        }
    }
    everything_down = frozenset(PAYLOADS)

    external, errors = collect_external(
        PROJECTS, _fetcher(PAYLOADS, everything_down), None, previous, TODAY
    )

    assert external == previous
    assert {(e["project"], e["source"]) for e in errors} == {
        ("proj-a", "pypi"),
        ("proj-b", "dockerhub"),
    }


def test_failing_source_without_history_omits_the_counter():
    external, _ = collect_external(
        PROJECTS, _fetcher(PAYLOADS, frozenset({PYPI_JSON})), {}, {}, TODAY
    )

    assert external["proj-a"] == {
        "pypi_downloads_last_month": 320,
        "fetched_at": TODAY,
    }


def test_malformed_payload_is_a_source_failure():
    broken = {**PAYLOADS, DOCKER: {"pull_count": "lots"}}

    external, errors = collect_external(PROJECTS, _fetcher(broken), {}, {}, TODAY)

    assert "proj-b" not in external
    assert errors[0]["source"] == "dockerhub"


def test_unavailable_stars_keep_previous_stars():
    previous = {"proj-c": {"stars": 7, "fetched_at": "2026-09-01"}}

    external, _ = collect_external(PROJECTS, _fetcher(PAYLOADS), None, previous, TODAY)

    assert external["proj-c"] == {"stars": 7, "fetched_at": "2026-09-01"}
    # Stars unknown today: the date stays the one of the oldest kept value.
    assert external["proj-a"]["fetched_at"] == TODAY
    assert "stars" not in external["proj-a"]


def test_build_document_keeps_account_keys_and_adds_external():
    account = compute_metrics(REPOS, "Rinzler78", TODAY)
    external = {"proj-a": {"stars": 4, "fetched_at": TODAY}}

    doc = build_document(account, external, [])

    assert {k: doc[k] for k in account} == account
    assert doc["external"] == external
    assert doc["errors"] == []


def _metrics_schema() -> dict:
    return json.loads(
        (ROOT / "schemas" / "metrics.schema.json").read_text(encoding="utf-8")
    )


def test_built_document_conforms_to_schema():
    account = compute_metrics(REPOS, "Rinzler78", TODAY)
    external, errors = collect_external(
        PROJECTS, _fetcher(PAYLOADS, frozenset({DOCKER})), {"proj-a": 4}, {}, TODAY
    )

    jsonschema.validate(build_document(account, external, errors), _metrics_schema())


def test_schema_rejects_unknown_counter():
    account = compute_metrics(REPOS, "Rinzler78", TODAY)
    doc = build_document(account, {"proj-a": {"downloads": 1, "fetched_at": TODAY}}, [])

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, _metrics_schema())


def test_real_metrics_file_conforms_and_references_known_projects():
    doc = json.loads((ROOT / "data" / "metrics.json").read_text(encoding="utf-8"))
    projects = json.loads((ROOT / "data" / "projects.json").read_text(encoding="utf-8"))

    jsonschema.validate(doc, _metrics_schema())
    assert set(doc["external"]) <= {p["id"] for p in projects}


def test_http_get_json_uses_requests_with_a_timeout(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": 1}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    fake = types.SimpleNamespace(get=fake_get, RequestException=OSError)
    monkeypatch.setitem(sys.modules, "requests", fake)

    assert http_get_json("https://example.test/x") == {"ok": 1}
    assert calls[0][0] == "https://example.test/x"
    assert calls[0][1]["timeout"] == 15


def test_http_get_json_wraps_transport_errors(monkeypatch):
    class Boom(Exception):
        pass

    def fake_get(url, **kwargs):
        raise Boom("down")

    fake = types.SimpleNamespace(get=fake_get, RequestException=Boom)
    monkeypatch.setitem(sys.modules, "requests", fake)

    with pytest.raises(SourceError, match="down"):
        http_get_json("https://example.test/x")
