"""Own-commit evidence: identity filter, dedupe, static analysis, output.

All repositories are built in ``tmp_path`` from synthetic commits; no network.
"""

from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path

import pytest

from scripts.activity import evidence as ev
from tests.activity.conftest import OTHER, OWN, git

IDENTITIES = {"email_patterns": ["^jane\\.sample@"], "name_patterns": ["^sample jane$"]}


@pytest.fixture
def ids() -> ev.Identities:
    return ev.Identities.from_dict(IDENTITIES)


@pytest.fixture
def voc() -> ev.Vocabulary:
    return ev.load_vocabulary()


def never_public(_key: str) -> bool:
    return False


# --- identities --------------------------------------------------------------


def test_identity_match_is_case_insensitive(ids: ev.Identities) -> None:
    assert ids.matches("Anyone", "JANE.Sample@Example.ORG")
    assert ids.matches("Sample JANE", "unrelated@example.com")
    assert not ids.matches(*OTHER)


@pytest.mark.parametrize(
    "raw",
    [
        [],
        {"email_patterns": []},
        {"email_patterns": [], "name_patterns": []},
        {"email_patterns": "x", "name_patterns": []},
        {"email_patterns": [1], "name_patterns": []},
    ],
)
def test_identities_reject_malformed_config(raw: object) -> None:
    with pytest.raises(ValueError):
        ev.Identities.from_dict(raw)


def test_load_identities_reads_json(tmp_path: Path) -> None:
    path = tmp_path / "identities.json"
    path.write_text(json.dumps(IDENTITIES))
    assert ev.load_identities(path).matches(*OWN)


# --- vocabulary --------------------------------------------------------------


def test_shipped_vocabulary_is_versioned(voc: ev.Vocabulary) -> None:
    assert isinstance(voc.version, int)
    assert voc.version >= 1


@pytest.mark.parametrize(
    "raw",
    [
        [],
        {"version": 1},
        {
            "version": "1",
            "excluded": [],
            "languages": {},
            "path_rules": [],
            "signatures": {},
        },
        {
            "version": 1,
            "excluded": [],
            "languages": {},
            "path_rules": [{}],
            "signatures": {},
        },
        {
            "version": 1,
            "excluded": [],
            "languages": {},
            "path_rules": [],
            "signatures": {"x": "not-a-list"},
        },
    ],
)
def test_vocabulary_rejects_malformed_file(raw: object) -> None:
    with pytest.raises(ValueError):
        ev.Vocabulary.from_dict(raw)


@pytest.mark.parametrize(
    "path",
    [
        "App/Resources/Resource.designer.cs",
        "App/Forms/Main.Designer.cs",
        "Data/Migrations/AppModelSnapshot.cs",
        "src/bin/Debug/app.dll.config",
        "src/obj/project.assets.json",
        "web/node_modules/lib/index.js",
        "vendor/pkg/file.go",
        "package-lock.json",
        "yarn.lock",
        "poetry.lock",
        "uv.lock",
        "Cargo.lock",
        "static/app.min.js",
    ],
)
def test_generated_and_vendored_paths_are_excluded(
    voc: ev.Vocabulary, path: str
) -> None:
    assert voc.is_excluded(path)


def test_handwritten_paths_are_kept(voc: ev.Vocabulary) -> None:
    assert not voc.is_excluded("src/Binder.cs")
    assert not voc.is_excluded("lib/objects.py")


# --- static analysis ---------------------------------------------------------


def test_generated_android_resource_yields_no_signal(voc: ev.Vocabulary) -> None:
    lines = [f"public const int GattCharacteristic{i} = {i};" for i in range(2000)]
    assert voc.analyze_patch({"Droid/Resources/Resource.designer.cs": lines}) == {}


def test_wrapper_namespace_counts_as_ble(voc: ev.Vocabulary) -> None:
    units = voc.analyze_patch({"App/Scan.cs": ["using NetToolBox.Bluetooth;"]})
    assert units == {"csharp": 1, "ble": 1}


def test_signature_counts_once_per_file(voc: ev.Vocabulary) -> None:
    lines = ["import anthropic", "client = anthropic.Anthropic()"]
    units = voc.analyze_patch({"a.py": lines, "b.py": lines})
    assert units == {"python": 2, "llm-api": 2}


def test_only_root_workflow_files_are_github_actions(voc: ev.Vocabulary) -> None:
    assert "github-actions" in voc.analyze_patch({".github/workflows/ci.yml": ["on:"]})
    assert voc.analyze_patch({"docs/.github/workflows/ci.yml": ["on:"]}) == {}


def test_line_scoped_rule_disambiguates_dot_m(voc: ev.Vocabulary) -> None:
    matlab = voc.analyze_patch({"calc.m": ["function y = f(x)", "y = zeros(3);"]})
    objective_c = voc.analyze_patch({"View.m": ["#import <UIKit/UIKit.h>"]})
    assert matlab == {"matlab": 1}
    assert objective_c == {"objective-c": 1, "ios": 1}  # UIKit import


def test_sql_from_clause_is_not_docker(voc: ev.Vocabulary) -> None:
    units = voc.analyze_patch({"q.py": ['rows = db.run("SELECT id FROM users")']})
    assert units == {"python": 1, "sql": 1}


def test_names_only_use_language_and_unscoped_path_rules(voc: ev.Vocabulary) -> None:
    units = voc.analyze_names(["Dockerfile", "calc.m", "a.cs", "obj/x.cs", "README"])
    assert units == {"docker": 1, "csharp": 1}


def test_normalize_sums_to_one() -> None:
    weights = ev.normalize({"python": 3, "docker": 1})
    assert weights == {"python": 0.75, "docker": 0.25}
    assert ev.normalize({}) == {}


# --- repo keys ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("remote", "key"),
    [
        ("git@github.com:Owner/Repo.git", "github.com/owner/repo"),
        ("https://github.com/owner/repo", "github.com/owner/repo"),
        ("https://user@github.com/Owner/Repo.git/", "github.com/owner/repo"),
        ("ssh://git@git.example.com:2222/team/app.git", "git.example.com/team/app"),
    ],
)
def test_repo_key_normalizes_remotes(remote: str, key: str) -> None:
    assert ev.repo_key(remote, Path("/any")) == key


def test_repo_key_falls_back_to_path(tmp_path: Path) -> None:
    assert ev.repo_key("", tmp_path) == f"local:{tmp_path}"
    assert ev.repo_key("/some/dir", tmp_path) == "local:/some/dir"


# --- collection --------------------------------------------------------------


def test_collect_keeps_own_commits_once(make_repo, tmp_path, ids, voc) -> None:
    origin = make_repo(
        "app",
        [
            (OWN, "2021-03-04T23:30:00+02:00", {"a.py": "import anthropic\n"}),
            (OTHER, "2021-03-05T10:00:00+00:00", {"b.py": "x = 1\n"}),
            (
                ("SAMPLE Jane", "old@example.com"),
                "2021-03-06T10:00:00+00:00",
                {"Dockerfile": "FROM python:3.12\n"},
            ),
        ],
        remote="git@github.com:jane/app.git",
    )
    copy = tmp_path / "copy"
    git(tmp_path, "clone", "-q", str(origin), str(copy))

    result = ev.collect([origin, copy], ids, voc, is_public=never_public)

    assert sorted(c.day for c in result.commits.values()) == [
        "2021-03-04",
        "2021-03-06",
    ]
    first = next(c for c in result.commits.values() if c.day == "2021-03-04")
    assert first.repo == "github.com/jane/app"
    assert first.units == {"python": 1, "llm-api": 1}
    assert first.weights == {"python": 0.5, "llm-api": 0.5}
    assert first.files == 1
    assert first.has_patch
    assert result.failures == {}


def test_files_count_every_analyzed_file(make_repo, ids, voc) -> None:
    files = {
        "a.py": "import anthropic\n",
        "README.md": "notes\n",
        "obj/Debug/x.cs": "generated\n",
    }
    repo = make_repo("files", [(OWN, "2021-03-04T10:00:00+00:00", files)])
    (commit,) = ev.collect([repo], ids, voc, is_public=never_public).commits.values()
    # The generated file is excluded; the README is analyzed with no tech.
    assert commit.files == 2
    assert commit.units == {"python": 1, "llm-api": 1}


def test_owners_filter_drops_foreign_repos(make_repo, ids, voc) -> None:
    day = "2021-03-04T10:00:00+00:00"
    mine = make_repo(
        "mine", [(OWN, day, {"a.py": "x\n"})], remote="git@github.com:jane/app.git"
    )
    foreign = make_repo(
        "foreign",
        [(OWN, day, {"b.py": "x\n"}), (OWN, day, {"c.py": "y\n"})],
        remote="https://github.com/someone/fork.git",
    )
    owners = ev.Owners.from_dict({"allow": ["github.com/jane/"]})

    result = ev.collect(
        [mine, foreign], ids, voc, is_public=never_public, owned=owners.allows
    )

    assert {c.repo for c in result.commits.values()} == {"github.com/jane/app"}
    assert result.excluded == {"github.com/someone/fork": 2}
    out = ev.aggregate(result, vocabulary_version=1)
    assert out["summary"]["excluded_repos"] == {"github.com/someone/fork": 2}


def test_owners_prefix_match() -> None:
    owners = ev.Owners.from_dict({"allow": ["github.com/jane/", "local:"]})
    assert owners.allows("github.com/jane/app")
    assert owners.allows("local:/tmp/x")
    assert not owners.allows("github.com/janet/app")


@pytest.mark.parametrize(
    "raw", [[], {"allow": "x"}, {"allow": [1]}, {"allow": []}, {"allow": [""]}]
)
def test_owners_reject_malformed_config(raw: object) -> None:
    with pytest.raises(ValueError, match="allow"):
        ev.Owners.from_dict(raw)


def test_load_owners_reads_json(tmp_path: Path) -> None:
    path = tmp_path / "owners.json"
    path.write_text(json.dumps({"allow": ["local:"]}))
    assert ev.load_owners(path).allows("local:/x")


def test_unreadable_repo_is_reported(tmp_path, ids, voc) -> None:
    missing = tmp_path / "nowhere"
    result = ev.collect([missing], ids, voc, is_public=never_public)
    assert result.commits == {}
    assert str(missing) in result.failures


# --- history ----------------------------------------------------------------


def _own_env(date: str) -> dict[str, str]:
    return {
        "GIT_AUTHOR_NAME": OWN[0],
        "GIT_AUTHOR_EMAIL": OWN[1],
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
    }


def _drop_object(repo: Path, rev: str) -> None:
    oid = git(repo, "rev-parse", rev).strip()
    loose = repo / ".git" / "objects" / oid[:2] / oid[2:]
    loose.chmod(0o644)
    loose.unlink()


def test_merge_commits_add_no_lines(make_repo, ids, voc) -> None:
    day = "2021-05-05T10:00:00+00:00"
    repo = make_repo("merge", [(OWN, day, {"a.py": "x = 1\n"})])
    git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.py").write_text("import anthropic\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "side", env=_own_env(day))
    git(repo, "checkout", "-q", "main")
    (repo / "main.rs").write_text("fn main() {}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "main", env=_own_env(day))
    git(repo, "merge", "-q", "--no-ff", "-m", "merge", "side", env=_own_env(day))
    merge = git(repo, "rev-parse", "HEAD").strip()

    result = ev.collect([repo], ids, voc, is_public=never_public)

    assert len(result.commits) == 4
    assert result.commits[merge].units == {}
    assert result.commits[merge].files == 0
    assert result.commits[merge].has_patch


def test_deleted_binary_and_modified_files(make_repo, ids, voc) -> None:
    day = "2021-05-05T10:00:00+00:00"
    repo = make_repo("kinds", [(OWN, day, {"old.py": "a = 1\nb = 2\n"})])
    (repo / "old.py").write_text("a = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "shrink", env=_own_env(day))
    shrink = git(repo, "rev-parse", "HEAD").strip()
    (repo / "old.py").unlink()
    (repo / "blob.cs").write_bytes(b"\x00\x01binary")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "swap", env=_own_env(day))
    swap = git(repo, "rev-parse", "HEAD").strip()

    commits = ev.collect([repo], ids, voc, is_public=never_public).commits

    assert commits[shrink].units == {"python": 1}
    assert commits[shrink].files == 1
    assert commits[swap].files == 0
    assert commits[swap].units == {}


def test_added_lines_are_bounded_and_filtered(make_repo, monkeypatch) -> None:
    monkeypatch.setattr(ev, "MAX_LINES_PER_FILE", 2)
    long_line = "x" * ev.MAX_LINE_LENGTH
    repo = make_repo(
        "bounds",
        [
            (
                OWN,
                "2021-05-05T10:00:00+00:00",
                {
                    "big.py": f"{long_line}\none\ntwo\nthree\n",
                    "skip.py": "dropped\n",
                },
            )
        ],
    )
    handle = ev.open_repository(repo)
    commit = handle.revparse_single("HEAD")

    files = ev.added_lines(handle, commit, keep=lambda path: path != "skip.py")

    assert files == {"big.py": ["one", "two"]}


def test_walk_covers_detached_head_and_ignores_tree_tags(make_repo, ids, voc) -> None:
    day = "2021-05-05T10:00:00+00:00"
    repo = make_repo("walk", [(OWN, day, {"a.py": "x\n"})])
    git(repo, "tag", "tree-tag", "HEAD^{tree}")
    git(repo, "checkout", "-q", "--detach")
    git(repo, "commit", "-q", "--allow-empty", "-m", "detached", env=_own_env(day))

    result = ev.collect([repo], ids, voc, is_public=never_public)

    assert len(result.commits) == 2


def test_empty_repo_and_nested_folder(tmp_path, ids, voc) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init", "-q")
    nested = empty / "sub"
    nested.mkdir()

    result = ev.collect([empty, nested], ids, voc, is_public=never_public)

    assert result.commits == {}
    assert list(result.failures) == [str(nested)]


def test_missing_blob_falls_back_to_names_then_full_copy_upgrades(
    make_repo, tmp_path, ids, voc
) -> None:
    day = "2020-01-01T10:00:00+00:00"
    content = "using NetToolBox.Bluetooth;\n"
    blobless = make_repo("blobless", [(OWN, day, {"a.cs": content})])
    full = tmp_path / "full"
    git(tmp_path, "clone", "-q", "--no-hardlinks", str(blobless), str(full))
    _drop_object(blobless, "HEAD:a.cs")

    alone = ev.collect([blobless], ids, voc, is_public=never_public)
    (commit,) = alone.commits.values()
    assert not commit.has_patch
    assert commit.units == {"csharp": 1}
    assert commit.files == 1  # names-only commits count their files too

    both = ev.collect([blobless, full], ids, voc, is_public=lambda key: True)
    (commit,) = both.commits.values()
    assert commit.has_patch
    assert commit.units == {"csharp": 1, "ble": 1}
    assert commit.files == 1
    assert commit.public


def test_missing_tree_yields_no_units(make_repo, ids, voc) -> None:
    day = "2020-01-01T10:00:00+00:00"
    repo = make_repo("treeless", [(OWN, day, {"a.cs": "x\n"})])
    _drop_object(repo, "HEAD^{tree}")

    (commit,) = ev.collect([repo], ids, voc, is_public=never_public).commits.values()

    assert commit.units == {}
    assert commit.files == 0
    assert not commit.has_patch


def test_remote_url_prefers_origin_then_any(make_repo) -> None:
    repo = make_repo("remotes", [])
    assert ev.remote_url(ev.open_repository(repo)) == ""
    git(repo, "remote", "add", "upstream", "https://example.com/a/b.git")
    assert ev.remote_url(ev.open_repository(repo)) == "https://example.com/a/b.git"
    git(repo, "remote", "add", "origin", "https://example.com/c/d.git")
    assert ev.remote_url(ev.open_repository(repo)) == "https://example.com/c/d.git"


# --- aggregation -------------------------------------------------------------


def _commit(
    h: str, day: str, repo: str, units: dict[str, int], public=False, files=None
):
    return ev.CommitEvidence(
        hash=h,
        day=day,
        repo=repo,
        units=units,
        has_patch=bool(units),
        public=public,
        files=len(units) if files is None else files,
    )


def test_aggregate_per_day_and_summary() -> None:
    result = ev.CollectResult(
        commits={
            "a": _commit("a", "2021-01-01", "r1", {"python": 1}, public=True),
            "b": _commit("b", "2021-01-01", "r2", {"docker": 1, "python": 1}, files=3),
            "c": _commit("c", "2021-01-02", "r2", {}),
        },
        failures={"/x": "boom"},
    )
    out = ev.aggregate(result, vocabulary_version=7)

    day = out["days"]["2021-01-01"]
    assert day["repos"] == ["r1", "r2"]
    assert day["commits"] == 2
    assert day["public"] is True
    assert day["techs"] == {"docker": 0.25, "python": 0.75}
    assert day["presence"] == ["docker", "python"]
    assert day["files"] == 4
    assert day["file_counts"] == {"docker": 1, "python": 2}
    assert out["days"]["2021-01-02"]["techs"] == {}
    assert out["summary"] == {
        "vocabulary_version": 7,
        "unique_commits": 3,
        "distinct_days": 2,
        "repos": 2,
        "public_day_share": 0.5,
        "commits_without_patch": 1,
        "failures": {"/x": "boom"},
        "excluded_repos": {},
    }


def test_aggregate_of_nothing() -> None:
    out = ev.aggregate(ev.CollectResult(commits={}, failures={}), vocabulary_version=1)
    assert out["summary"]["public_day_share"] == 0.0


# --- visibility --------------------------------------------------------------


def test_visibility_asks_once_and_caches(tmp_path: Path) -> None:
    calls: list[str] = []

    def lookup(slug: str) -> bool:
        calls.append(slug)
        return slug == "owner/pub"

    cache = tmp_path / "cache.json"
    vis = ev.GitHubVisibility(cache, lookup=lookup)
    assert vis("github.com/owner/pub")
    assert vis("github.com/owner/pub")
    assert not vis("github.com/owner/priv")
    assert not vis("local:/x")
    assert not vis("git.example.com/team/app")
    assert calls == ["owner/pub", "owner/priv"]

    assert ev.GitHubVisibility(cache, lookup=lookup)("github.com/owner/pub")
    assert calls == ["owner/pub", "owner/priv"]


def test_unknown_visibility_is_private_and_not_cached(tmp_path: Path) -> None:
    def lookup(slug: str) -> bool:
        raise ev.VisibilityUnknown("rate limited")

    cache = tmp_path / "cache.json"
    assert not ev.GitHubVisibility(cache, lookup=lookup)("github.com/owner/x")
    assert not cache.exists()


class _Response:
    def __init__(self, status: int, body: dict | None = None) -> None:
        self.status_code = status
        self._body = body or {}

    def json(self) -> dict:
        return self._body


@pytest.mark.parametrize(
    ("response", "public"),
    [
        (_Response(200, {"private": False}), True),
        (_Response(200, {"private": True}), False),
        (_Response(404), False),
    ],
)
def test_github_answers(monkeypatch, response, public) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    seen: dict = {}

    def fake_get(url, headers, timeout):
        seen.update(url=url, headers=headers, timeout=timeout)
        return response

    monkeypatch.setattr(ev.requests, "get", fake_get)
    assert ev.github_is_public("owner/repo") is public
    assert seen["url"] == "https://api.github.com/repos/owner/repo"
    assert "Authorization" not in seen["headers"]
    assert seen["timeout"] == 10


def test_github_token_is_sent(monkeypatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "t0k")
    seen: dict = {}

    def fake_get(url, headers, timeout):
        seen.update(headers)
        return _Response(404)

    monkeypatch.setattr(ev.requests, "get", fake_get)
    ev.github_is_public("owner/repo")
    assert seen["Authorization"] == "Bearer t0k"


def test_github_rate_limit_is_unknown(monkeypatch) -> None:
    monkeypatch.setattr(ev.requests, "get", lambda *a, **k: _Response(403))
    with pytest.raises(ev.VisibilityUnknown, match="403"):
        ev.github_is_public("owner/repo")


def test_github_network_error_is_unknown(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise ev.requests.ConnectionError("offline")

    monkeypatch.setattr(ev.requests, "get", boom)
    with pytest.raises(ev.VisibilityUnknown, match="offline"):
        ev.github_is_public("owner/repo")


# --- CLI ---------------------------------------------------------------------


def _private_dir(tmp_path: Path, repo: Path) -> Path:
    private = tmp_path / "private"
    private.mkdir()
    (private / "identities.json").write_text(json.dumps(IDENTITIES))
    (private / "repos.txt").write_text(f"# comment\n\n{repo}\n")
    (private / "owners.json").write_text(json.dumps({"allow": ["local:"]}))
    return private


def test_main_uses_private_dir_defaults(
    make_repo, tmp_path, monkeypatch, capsys
) -> None:
    repo = make_repo("cli", [(OWN, "2022-02-02T10:00:00+00:00", {"a.py": "x\n"})])
    private = _private_dir(tmp_path, repo)
    monkeypatch.setenv("PROFILE_PRIVATE_DIR", str(private))

    assert ev.main([]) == 0

    out = json.loads((private / "evidence.json").read_text())
    assert out["summary"]["unique_commits"] == 1
    assert "2022-02-02" in out["days"]
    printed = capsys.readouterr().out
    assert "unique commits: 1" in printed
    assert "excluded repos: 0" in printed


def test_main_lists_excluded_repos(make_repo, tmp_path, monkeypatch, capsys) -> None:
    repo = make_repo("cli", [(OWN, "2022-02-02T10:00:00+00:00", {"a.py": "x\n"})])
    private = _private_dir(tmp_path, repo)
    (private / "owners.json").write_text(json.dumps({"allow": ["github.com/jane/"]}))
    monkeypatch.setenv("PROFILE_PRIVATE_DIR", str(private))

    assert ev.main([]) == 0

    out = json.loads((private / "evidence.json").read_text())
    assert out["days"] == {}
    assert f"excluded local:{repo}: 1 commit(s)" in capsys.readouterr().out


def test_main_accepts_explicit_paths(make_repo, tmp_path, monkeypatch) -> None:
    repo = make_repo("cli", [(OWN, "2022-02-02T10:00:00+00:00", {"a.py": "x\n"})])
    private = _private_dir(tmp_path, repo)
    monkeypatch.delenv("PROFILE_PRIVATE_DIR", raising=False)
    target = tmp_path / "out" / "e.json"

    code = ev.main(
        [
            "--repos",
            str(private / "repos.txt"),
            "--identities",
            str(private / "identities.json"),
            "--out",
            str(target),
            "--visibility-cache",
            str(tmp_path / "vis.json"),
            "--owners",
            str(private / "owners.json"),
        ]
    )

    assert code == 0
    assert target.exists()


def test_main_without_private_dir_fails(monkeypatch) -> None:
    monkeypatch.delenv("PROFILE_PRIVATE_DIR", raising=False)
    with pytest.raises(SystemExit) as exc:
        ev.main([])
    assert exc.value.code == 2


def test_module_entry_point(make_repo, tmp_path, monkeypatch) -> None:
    repo = make_repo("cli", [(OWN, "2022-02-02T10:00:00+00:00", {"a.py": "x\n"})])
    private = _private_dir(tmp_path, repo)
    monkeypatch.setenv("PROFILE_PRIVATE_DIR", str(private))
    monkeypatch.setattr(sys, "argv", ["evidence"])
    sys.modules.pop("scripts.activity.evidence", None)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("scripts.activity.evidence", run_name="__main__")
    assert exc.value.code == 0
    assert os.path.exists(private / "evidence.json")


# --- remaining edges ---------------------------------------------------------


def test_invalid_regex_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="email_patterns"):
        ev.Identities.from_dict({"email_patterns": ["("], "name_patterns": []})


def test_vocabulary_requires_signatures() -> None:
    raw = {"version": 1, "excluded": [], "languages": {}, "path_rules": []}
    with pytest.raises(ValueError, match="signatures"):
        ev.Vocabulary.from_dict(raw)


@pytest.mark.parametrize(
    "path",
    [
        "App/packages/Xamarin.Forms.1.5.1.6471/lib/MonoAndroid10/Core.xml",
        "App/Components/sample-sdk-13.0/lib/android/Docs.html",
    ],
)
def test_nuget_and_component_stores_are_excluded(voc: ev.Vocabulary, path) -> None:
    assert voc.is_excluded(path)
    assert not voc.is_excluded("web/packages/ui/src/index.ts")


def test_scoped_flags_stay_with_their_alternative() -> None:
    raw = {
        "version": 1,
        "excluded": [],
        "languages": {},
        "path_rules": [],
        "signatures": {"t": ["(?i)abc", "XYZ"]},
    }
    voc = ev.Vocabulary.from_dict(raw)
    assert voc.analyze_patch({"f": ["ABC"]}) == {"t": 1}
    assert voc.analyze_patch({"f": ["xyz"]}) == {}


# --- project context (vocabulary v2) -----------------------------------------

DAY = "2021-03-04T10:00:00+00:00"
FORMS_IOS = (
    '<Project><ItemGroup><Reference Include="Xamarin.iOS" />'
    '<PackageReference Include="Xamarin.Forms" /></ItemGroup></Project>\n'
)


def _only(make_repo, ids, voc, name: str, files: dict[str, str], extra=None):
    """Collect a repo whose last own commit adds ``extra`` over ``files``."""
    commits = [(OWN, DAY, files)]
    if extra:
        commits.append((OWN, "2021-03-05T10:00:00+00:00", extra))
    repo = make_repo(name, commits)
    result = ev.collect([repo], ids, voc, is_public=never_public)
    return max(result.commits.values(), key=lambda c: c.day)


def test_header_is_objective_c_when_its_project_has_m_files(
    make_repo, ids, voc
) -> None:
    objc = _only(
        make_repo,
        ids,
        voc,
        "objc",
        {"App/View.m": "#import <UIKit/UIKit.h>\n"},
        {"App/Model/Item.h": "@interface Item\n"},
    )
    assert objc.units == {"objective-c": 1}
    plain = _only(
        make_repo, ids, voc, "plain", {"lib/a.c": "int a;\n"}, {"lib/a.h": "int a;\n"}
    )
    assert plain.units == {"c-cpp": 1}


def test_header_in_c_directory_of_a_mixed_repo_stays_c(make_repo, ids, voc) -> None:
    commit = _only(
        make_repo,
        ids,
        voc,
        "mixed",
        {
            "ios/App.xcodeproj/project.pbxproj": "x\n",
            "ios/View.m": "#import <UIKit/UIKit.h>\n",
            "core/Core.vcxproj.filters": "x\n",
            "core/src/a.c": "int a;\n",
            "core/CMakeLists.txt": "project(core)\n",
        },
        {"core/src/a.h": "int a;\n", "ios/View.h": "@interface V\n"},
    )
    # ios/View.h sits next to .m files; core/src/a.h belongs to the core/
    # build root (CMakeLists.txt), which holds no Objective-C.
    assert commit.units == {"objective-c": 1, "c-cpp": 1}


def test_files_inherit_their_project_techs(make_repo, ids, voc) -> None:
    commit = _only(
        make_repo,
        ids,
        voc,
        "forms",
        {"App.iOS/App.iOS.csproj": FORMS_IOS},
        {"App.iOS/Services/Clock.cs": "class Clock {}\n"},
    )
    assert commit.units == {
        "csharp": 1,
        "xamarin": 1,
        "xamarin-forms": 1,
        "ios": 1,
    }


def test_native_android_project(make_repo, ids, voc) -> None:
    commit = _only(
        make_repo,
        ids,
        voc,
        "android",
        {"app/build.gradle": "apply plugin: 'com.android.application'\n"},
        {"app/src/main/java/A.java": "class A {}\n"},
    )
    assert commit.units == {"java": 1, "android": 1}


def test_test_project_files_count_as_tests_and_test_only_commits(
    make_repo, ids, voc
) -> None:
    commit = _only(
        make_repo,
        ids,
        voc,
        "tested",
        {"Core.Specs/Core.Specs.csproj": '<PackageReference Include="NUnit" />\n'},
        {"Core.Specs/ClockSpec.cs": "class ClockSpec {}\n"},
    )
    assert commit.units == {"csharp": 1, "tests": 1}
    assert commit.test_only


def test_mvvm_framework_applies_to_ui_and_viewmodel_files_only(
    make_repo, ids, voc
) -> None:
    project = {"App/App.csproj": '<PackageReference Include="MvvmCross" />\n'}
    view = _only(
        make_repo, ids, voc, "mvx1", project, {"App/Views/Home.xaml": "<Grid/>\n"}
    )
    assert view.units == {"xaml": 1, "mobile-ui": 1, "mvvm": 1}
    service = _only(
        make_repo, ids, voc, "mvx2", project, {"App/Services/Api.cs": "class A {}\n"}
    )
    assert service.units == {"csharp": 1}


def test_mvvm_triad_marks_its_three_layers(make_repo, ids, voc) -> None:
    project = {
        "App/App.csproj": "<Project/>\n",
        "App/Models/Item.cs": "class Item {}\n",
        "App/Views/ItemPage.cs": "class ItemPage {}\n",
        "App/ViewModels/ItemViewModel.cs": "class ItemViewModel {}\n",
    }
    model = _only(
        make_repo, ids, voc, "t1", project, {"App/Models/Item.cs": "class Item2 {}\n"}
    )
    assert model.units == {"csharp": 1, "mvvm": 1}
    other = _only(
        make_repo, ids, voc, "t2", project, {"App/Services/X.cs": "class X {}\n"}
    )
    assert other.units == {"csharp": 1}
    no_triad = _only(
        make_repo,
        ids,
        voc,
        "t3",
        {"App/App.csproj": "<Project/>\n", "App/Models/Item.cs": "class I {}\n"},
        {"App/Models/Item.cs": "class Item2 {}\n"},
    )
    assert no_triad.units == {"csharp": 1}


def test_ordinary_shared_code_is_not_cross_platform(make_repo, ids, voc) -> None:
    solution = {
        "Core/Core.csproj": "<TargetFramework>netstandard2.0</TargetFramework>\n",
        "App.Droid/App.Droid.csproj": "<Project/>\n",
    }
    commit = _only(
        make_repo, ids, voc, "shared", solution, {"Core/Clock.cs": "class Clock {}\n"}
    )
    assert commit.units == {"csharp": 1}


def test_interface_implemented_on_both_platforms(make_repo, ids, voc) -> None:
    both = {
        "App.iOS/Services/Clock.cs": "public class Clock : NSObject, IClock {}\n",
        "App.Droid/Clock.cs": "class Clock : Java.Lang.Object, IClock\n{\n}\n",
        "App.Droid/Other.cs": "class Other : IOther {}\n",
    }
    defined = _only(
        make_repo,
        ids,
        voc,
        "iface",
        both,
        {"Core/IClock.cs": "public interface IClock { }\n"},
    )
    assert defined.units == {"csharp": 1, "cross-platform-architecture": 1}
    one_side = _only(
        make_repo,
        ids,
        voc,
        "iface1",
        both,
        {"Core/IOther.cs": "public interface IOther { }\n"},
    )
    assert one_side.units == {"csharp": 1}


def test_release_steps_of_mobile_repos(make_repo, ids, voc) -> None:
    mobile = {"App.Droid/App.Droid.csproj": "<Project/>\n"}
    extra = {
        "buildAll.sh": "msbuild App.sln\n",
        "scripts/lint.sh": "ruff check\n",
        "scripts/ship.sh": "xcrun altool --upload-app app.ipa\n",
        ".github/workflows/ci.yml": "on: push\n",
        ".github/workflows/store.yml": "- run: appcenter distribute release\n",
    }
    commit = _only(make_repo, ids, voc, "mobile", mobile, extra)
    # Building is not a skill: only the upload and the store step count.
    assert commit.units["mobile-release"] == 2
    plain = _only(make_repo, ids, voc, "plain-ci", {"a.py": "x\n"}, extra)
    assert "mobile-release" not in plain.units


def test_container_repositories_count_every_file_for_docker(
    make_repo, ids, voc
) -> None:
    image = {"Dockerfile": "FROM alpine\n", "entrypoint.sh": "run\n"}
    named = _only(
        make_repo, ids, voc, "idena-node-docker", image, {"src/update.py": "x\n"}
    )
    assert named.units == {"python": 1, "docker": 1}
    mostly_image = {
        "Dockerfile": "FROM alpine\n",
        "docker-compose.yml": "services: {}\n",
        "start.sh": "up\n",
        "README.md": "doc\n",
    }
    shared = _only(make_repo, ids, voc, "toolbox", mostly_image, {"tool.py": "x\n"})
    assert shared.units["docker"] == 1
    app = {
        "Dockerfile": "FROM python\n",
        **{f"app/m{i}.py": "x\n" for i in range(6)},
    }
    code = _only(make_repo, ids, voc, "webapp", app, {"app/new.py": "x\n"})
    assert "docker" not in code.units
    dockerfile = _only(
        make_repo, ids, voc, "webapp2", app, {"Dockerfile": "FROM python:3.12\n"}
    )
    assert dockerfile.units == {"docker": 1}


def test_unreadable_project_file_adds_nothing(make_repo, ids, voc) -> None:
    repo = make_repo(
        "blobless-project",
        [
            (OWN, DAY, {"App.iOS/App.iOS.csproj": FORMS_IOS}),
            (OWN, "2021-03-05T10:00:00+00:00", {"App.iOS/A.cs": "class A {}\n"}),
        ],
    )
    _drop_object(repo, "HEAD:App.iOS/App.iOS.csproj")
    commits = ev.collect([repo], ids, voc, is_public=never_public).commits
    last = max(commits.values(), key=lambda c: c.day)
    assert last.units == {"csharp": 1, "ios": 1, "xamarin": 1}  # path rules only


@pytest.mark.parametrize(
    ("path", "lines", "tech"),
    [
        (
            "App.iOS/App.iOS.csproj",
            ["<CodesignKey>iPhone</CodesignKey>"],
            "mobile-release",
        ),
        ("App.Droid/App.Droid.csproj", ["<AndroidKeyStore>True"], "mobile-release"),
        ("fastlane/Fastfile", ["lane :beta"], "mobile-release"),
        ("fastlane/metadata/en-US/description.txt", ["An app"], "mobile-release"),
        (".devcontainer/devcontainer.json", ["{}"], "docker"),
        ("CMakeLists.txt", ["project(core)"], "cross-compilation-toolchains"),
        (
            "cmake/arm64.cmake",
            ["set(CMAKE_SYSTEM_NAME Linux)"],
            "cross-compilation-toolchains",
        ),
        ("GNUmakefile", ["CC ?= gcc"], "cross-compilation-toolchains"),
        ("jni/Android.mk", ["LOCAL_MODULE := core"], "cross-compilation-toolchains"),
        (
            "app/build.gradle",
            ["abiFilters 'arm64-v8a'"],
            "cross-compilation-toolchains",
        ),
        (
            "Core/Core.vcxproj",
            ["<PlatformToolset>v142</PlatformToolset>"],
            "cross-compilation-toolchains",
        ),
        ("supported_platforms.json", ["[]"], "cross-compilation-toolchains"),
        ("scripts/resolve_arch.sh", ["uname -m"], "cross-compilation-toolchains"),
        (
            "build.sh",
            ["GOOS=linux GOARCH=arm64 go build"],
            "cross-compilation-toolchains",
        ),
        ("build.sh", ["cc -march=armv7-a main.c"], "cross-compilation-toolchains"),
        ("build_android_arm64.sh", ["make"], "cross-compilation-toolchains"),
        ("Core/ClockTests.cs", ["[Test]"], "tests"),
        ("tests/test_x.py", ["x = 1"], "tests"),
        ("web/app.spec.ts", ["x"], "tests"),
        ("App/HomePresenter.cs", ["class P {}"], "mvp"),
        ("App/IHome.cs", ["public interface IHomeView {}"], "mvp"),
        ("Shop.Domain/ValueObjects/Money.cs", ["class Money {}"], "ddd"),
        ("Shop/Entities/Order.cs", ["class OrderAggregate {}"], "ddd"),
        ("App/Info.plist", ["<plist/>"], "ios"),
        ("App/Main.cs", ["using UIKit;"], "ios"),
        ("App/Main.cs", ["using Android.App;"], "android"),
        ("App/Conv.cs", ["class C : IValueConverter {}"], "mobile-ui"),
        (
            "App/HomePageController.cs",
            ["public ICommand Save { get; }", "OnPropertyChanged();"],
            "mvvm",
        ),
        (
            "App/Vm.cs",
            ["Refresh = new Command(Load);", "PropertyChanged?.Invoke(this, e);"],
            "mvvm",
        ),
        (
            "App/HomeController.cs",
            ["class HomeController : BasePageController<HomePage>"],
            "mvvm",
        ),
        ("App/Model/ItemUIModel.cs", ["OnPropertyChanged(nameof(Name));"], "mvvm"),
        ("App/Api/StatusModel.cs", ["RaisePropertyChanged();"], "mvvm"),
        (
            "App/Api.cs",
            ["DependencyService.Register<Api>();"],
            "cross-platform-architecture",
        ),
        (
            "App/Renderers.cs",
            ["[assembly: ExportRenderer(typeof(A), typeof(B))]"],
            "cross-platform-architecture",
        ),
        ("App/Paths.cs", ["#if __IOS__"], "cross-platform-architecture"),
        ("Shared/Shared.shproj", ["<Project/>"], "cross-platform-architecture"),
        (
            "Core/Core.csproj",
            ["<TargetFrameworks>netstandard2.0;net6.0</TargetFrameworks>"],
            "cross-platform-architecture",
        ),
        ("Shared/App.cs", ["using Xamarin.Forms;"], "xamarin-forms"),
        ("App/Page.xaml", ['<Label Text="{Binding Name}"/>'], "mvvm"),
    ],
)
def test_file_level_rules(voc: ev.Vocabulary, path, lines, tech) -> None:
    assert tech in voc.analyze_patch({path: lines})


@pytest.mark.parametrize(
    ("path", "lines"),
    [
        ("App/Vm.cs", ["class V : INotifyPropertyChanged {}"]),
        ("App/Vm.cs", ["public ICommand Save { get; }"]),
        ("App/Services/Sync.cs", ["OnPropertyChanged();"]),
        ("Core/Core.csproj", ["<TargetFramework>netstandard2.0</TargetFramework>"]),
        ("App/Api.cs", ["var api = DependencyService.Get<IApi>();"]),
        ("build.sh", ["dotnet build -c Release"]),
        ("app/build.gradle", ["implementation 'com.example:lib:1.0'"]),
        ("run.sh", ["docker run --rm app"]),
        ("azure-pipelines.yml", ["- task: XamarinAndroid@1"]),
    ],
)
def test_behavior_rules_need_their_evidence(voc: ev.Vocabulary, path, lines) -> None:
    units = voc.analyze_patch({path: lines})
    for tech in (
        "mvvm",
        "cross-platform-architecture",
        "cross-compilation-toolchains",
        "mobile-release",
        "docker",
    ):
        assert tech not in units


def test_aggregate_counts_test_only_commits() -> None:
    commit = _commit("a", "2021-01-01", "r1", {"tests": 1, "csharp": 1})
    commit.test_only = True
    out = ev.aggregate(ev.CollectResult(commits={"a": commit}), vocabulary_version=2)
    assert out["days"]["2021-01-01"]["test_only_commits"] == 1


@pytest.mark.parametrize(
    "extra",
    [
        {"project_files": 1},
        {"project_files": "x", "project_rules": [{"tech": "t"}]},
        {
            "project_files": "x",
            "conjunctions": [{"tech": "t", "all": "x"}],
        },
        {"project_files": "x", "project_rules": "no"},
        {"conjunctions": "no"},
        {"conjunctions": [{"tech": "t", "all": []}]},
        {"context_rules": "no"},
        {"context_rules": [{"tech": "t", "requires": "moon", "path": "x"}]},
        {"context_rules": [{"tech": "t", "requires": "mobile-repo"}]},
        {"platform_sides": {"ios": "x"}},
        {"platform_sides": "no"},
        {"container_repos": {"name": "x"}},
        {
            "container_repos": {
                "root_files": "x",
                "name": "x",
                "support": "x",
                "min_share": "half",
                "tech": "docker",
            }
        },
    ],
)
def test_vocabulary_rejects_malformed_project_rules(extra) -> None:
    raw = {
        "version": 2,
        "excluded": [],
        "languages": {},
        "path_rules": [],
        "signatures": {},
        **extra,
    }
    with pytest.raises(ValueError):
        ev.Vocabulary.from_dict(raw)


def test_mvvm_triad_from_file_names(make_repo, ids, voc) -> None:
    project = {
        "App/App.csproj": "<Project/>\n",
        "App/ItemModel.cs": "class ItemModel {}\n",
        "App/ItemView.cs": "class ItemView {}\n",
        "App/ItemViewModel.cs": "class ItemViewModel {}\n",
    }
    commit = _only(
        make_repo, ids, voc, "names", project, {"App/ItemModel.cs": "class M {}\n"}
    )
    assert commit.units == {"csharp": 1, "mvvm": 1}


def test_context_tolerates_missing_directories(make_repo, voc) -> None:
    repo_path = make_repo("ctx", [(OWN, DAY, {"lib/a.c": "int a;\n"})])
    repo = ev.open_repository(repo_path)
    tree = repo.revparse_single("HEAD").peel(ev.pygit2.Commit).tree
    context = ev.ProjectContext(repo, tree, voc, ev.ContextCache())
    assert context.header_language("gone/x.h") is None
    assert context.header_language("lib/a.c/x.h") is None  # a file, not a dir


def test_missing_parent_tree_yields_nothing(make_repo, ids, voc) -> None:
    repo = make_repo(
        "orphan",
        [
            (OWN, DAY, {"a.py": "x = 1\n"}),
            (OWN, "2021-03-05T10:00:00+00:00", {"b.py": "y = 2\n"}),
        ],
    )
    _drop_object(repo, "HEAD~1^{tree}")
    commits = ev.collect([repo], ids, voc, is_public=never_public).commits
    last = max(commits.values(), key=lambda c: c.day)
    assert (last.units, last.files, last.has_patch) == ({}, 0, False)


# --- MVVM at project level ---------------------------------------------------

BASE_VM = (
    "public class BasePageController : Bindable\n{\n"
    "    public ICommand Save { get; }\n"
    "    void Changed() => OnPropertyChanged();\n}\n"
)
SDK = {
    "Sdk/Sdk.csproj": "<Project/>\n",
    "Sdk/Base/BasePageController.cs": BASE_VM,
    "Sdk/Base/DefaultLoginPageController.cs": (
        "public class DefaultLoginPageController : BasePageController {}\n"
    ),
}
APP_PROJECT = (
    '<ItemGroup><ProjectReference Include="..\\Sdk\\Sdk.csproj" /></ItemGroup>\n'
)


def test_presentation_layer_of_an_mvvm_project(make_repo, ids, voc) -> None:
    control = _only(
        make_repo, ids, voc, "p1", SDK, {"Sdk/Controls/Badge.cs": "class Badge {}\n"}
    )
    assert "mvvm" in control.units
    service = _only(
        make_repo, ids, voc, "p2", SDK, {"Sdk/Services/Api.cs": "class Api {}\n"}
    )
    assert "mvvm" not in service.units


def test_presentation_of_a_project_without_viewmodel(make_repo, ids, voc) -> None:
    commit = _only(
        make_repo,
        ids,
        voc,
        "p3",
        {"App/App.csproj": "<Project/>\n", "App/Api.cs": "class Api {}\n"},
        {"App/Views/Home.cs": "class Home {}\n"},
    )
    assert "mvvm" not in commit.units


def test_referencing_an_mvvm_sdk_and_inheriting_its_viewmodels(
    make_repo, ids, voc
) -> None:
    tree = {**SDK, "App/App.csproj": APP_PROJECT}
    derived = _only(
        make_repo,
        ids,
        voc,
        "p4",
        tree,
        {
            "App/Login/LoginFlow.cs": (
                "public class ShopLoginFlow : DefaultLoginPageController {}\n"
            )
        },
    )
    assert "mvvm" in derived.units
    view = _only(make_repo, ids, voc, "p5", tree, {"App/Views/X.cs": "class X {}\n"})
    assert "mvvm" in view.units
    network = _only(
        make_repo, ids, voc, "p6", tree, {"App/Net/Client.cs": "class Client {}\n"}
    )
    assert "mvvm" not in network.units


def test_shared_project_import_carries_mvvm(make_repo, ids, voc) -> None:
    tree = {
        "Shared/Shared.projitems": "<Project/>\n",
        "Shared/Base/BasePageController.cs": BASE_VM,
        "App/App.csproj": '<Import Project="..\\Shared\\Shared.projitems" />\n',
    }
    commit = _only(
        make_repo, ids, voc, "p7", tree, {"App/Pages/Home.cs": "class Home {}\n"}
    )
    assert "mvvm" in commit.units


def test_registry_carries_mvvm_across_repositories(
    make_repo, tmp_path, ids, voc
) -> None:
    sdk = make_repo("sdk-repo", [(OWN, DAY, SDK)])
    app = make_repo(
        "app-repo",
        [
            (OWN, DAY, {"App/App.csproj": APP_PROJECT}),
            (
                OWN,
                "2021-03-05T10:00:00+00:00",
                {
                    "App/Views/X.cs": "class X {}\n",
                    "App/Flow.cs": "class Flow : DefaultLoginPageController {}\n",
                },
            ),
        ],
    )
    registry = ev.mvvm_registry([sdk, app, tmp_path / "missing"], voc)
    assert "sdk.csproj" in registry.projects
    assert {"BasePageController", "DefaultLoginPageController"} <= registry.classes
    alone = ev.collect([app], ids, voc, is_public=never_public)
    last = max(alone.commits.values(), key=lambda c: c.day)
    assert "mvvm" not in last.units
    shared = ev.collect([app], ids, voc, is_public=never_public, registry=registry)
    last = max(shared.commits.values(), key=lambda c: c.day)
    assert last.units["mvvm"] == 2


def test_project_references_cycles_and_escapes_terminate(make_repo, ids, voc) -> None:
    tree = {
        "A/A.csproj": '<ProjectReference Include="..\\B\\B.csproj" />\n'
        '<ProjectReference Include="..\\..\\Out\\Out.csproj" />\n',
        "B/B.csproj": '<ProjectReference Include="..\\A\\A.csproj" />\n',
    }
    commit = _only(make_repo, ids, voc, "cycle", tree, {"A/Views/V.cs": "class V {}\n"})
    assert "mvvm" not in commit.units


def test_vocabulary_without_container_rule(make_repo) -> None:
    repo_path = make_repo("bare-docker", [(OWN, DAY, {"Dockerfile": "FROM x\n"})])
    repo = ev.open_repository(repo_path)
    tree = repo.revparse_single("HEAD").peel(ev.pygit2.Commit).tree
    minimal = ev.Vocabulary.from_dict(
        {
            "version": 1,
            "excluded": [],
            "languages": {},
            "path_rules": [],
            "signatures": {},
        }
    )
    context = ev.ProjectContext(repo, tree, minimal, ev.ContextCache(), "x/docker")
    assert not context.is_container_repo()


def test_container_name_may_come_from_the_folder(make_repo) -> None:
    repo_path = make_repo(
        "stack", [(OWN, DAY, {"Dockerfile": "FROM x\n", "a.py": "1\n", "b.py": "2\n"})]
    )
    repo = ev.open_repository(repo_path)
    tree = repo.revparse_single("HEAD").peel(ev.pygit2.Commit).tree
    voc = ev.load_vocabulary()
    kept = ev.ProjectContext(
        repo, tree, voc, ev.ContextCache(), "local:/home/me/Dockers/stack"
    )
    assert kept.is_container_repo()
    other = ev.ProjectContext(repo, tree, voc, ev.ContextCache(), "github.com/me/stack")
    assert not other.is_container_repo()
