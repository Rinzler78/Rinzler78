"""Behavior specs for compute_metrics (pure aggregation, no network)."""

from scripts.fetch_metrics import compute_metrics

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
