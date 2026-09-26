"""Collect own-commit evidence from local git repositories (ADR-013 §2, §3, §6).

Every repository listed is walked once; commits are kept when their author
matches one of the author's identities, then deduplicated by hash so a
repository present in several copies or mirrors counts once. For each own
commit the lines it *added* are analyzed statically against a versioned
vocabulary (``vocabulary.json``): the language from the file extension, then
frameworks and domains from path rules and line signatures. Generated and
vendored files are dropped before any analysis.

Weights, per commit
    Each non-excluded file that received added lines contributes one unit to
    every tech it shows — its language, each matching path rule, and each
    signature that matches at least one of its added lines. A tech therefore
    counts at most once per file, so one dense file cannot outweigh the rest of
    the commit. The weights are the units divided by their sum, so they sum to
    1 over the techs detected. Language and domain overlap on purpose (a C#
    file using a BLE API yields both); ADR-013 §4 lets one hour count for
    several techs, so the raw units are kept alongside the weights and the
    allocation step decides how to use them.

Reading history
    History is read in-process with libgit2 (pygit2): no child process, no
    shell. Every ref and HEAD, peeled to commits, is walked like
    ``git log --all``. A commit's added lines come from the diff against its
    first parent (against the empty tree for a root commit), with rename
    detection off. Merge commits add no lines of their own, as with
    ``git log -p``: they count as evidence of the day, with no tech.

Missing patch content
    A blobless mirror holds commits and trees but no file contents, and
    libgit2 never fetches them lazily. Its commits fall back to file names
    only: languages and path rules without line conditions. They are reported
    as lacking patch content, and a later full copy of the same commit
    replaces the fallback.

The output is private and never lives in this repository: identities, the
repository list and the result all sit in ``$PROFILE_PRIVATE_DIR``.

Usage: ``python -m scripts.activity.evidence [--repos FILE] [--out FILE]``
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

import pygit2
import requests
from pygit2.enums import DeltaStatus, RepositoryOpenFlag, SortMode

VOCABULARY_PATH = Path(__file__).with_name("vocabulary.json")
GITHUB_API = "https://api.github.com/repos/"
MAX_LINE_LENGTH = 500
MAX_LINES_PER_FILE = 2000


# --- identities --------------------------------------------------------------


def _regex_list(raw: object, what: str) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(p, str) for p in raw):
        raise ValueError(f"{what} must be a list of regular expressions")
    return raw


def _patterns(raw: object, what: str, flags: int = 0) -> tuple[re.Pattern[str], ...]:
    try:
        return tuple(re.compile(p, flags) for p in _regex_list(raw, what))
    except re.error as exc:
        raise ValueError(f"{what}: {exc}") from exc


_GLOBAL_FLAGS = re.compile(r"^\(\?([a-zA-Z]+)\)")


def _combine(raw: object, what: str) -> re.Pattern[str]:
    """One alternation per tech: a single scan per line instead of one per regex.

    A leading global flag group such as ``(?i)`` becomes a scoped one so it
    keeps applying to its own alternative only.
    """
    patterns = _regex_list(raw, what)
    _patterns(patterns, what)  # each regex must compile on its own
    parts = []
    for pattern in patterns:
        flags = _GLOBAL_FLAGS.match(pattern)
        if flags:
            parts.append(f"(?{flags.group(1)}:{pattern[flags.end() :]})")
        else:
            parts.append(f"(?:{pattern})")
    return re.compile("|".join(parts))


@dataclass(frozen=True)
class Identities:
    """The author's identities: regexes searched case-insensitively."""

    emails: tuple[re.Pattern[str], ...]
    names: tuple[re.Pattern[str], ...]

    @classmethod
    def from_dict(cls, raw: object) -> Identities:
        if not isinstance(raw, dict):
            raise ValueError("identities must be an object")
        emails = _patterns(raw.get("email_patterns"), "email_patterns", re.I)
        names = _patterns(raw.get("name_patterns"), "name_patterns", re.I)
        if not emails and not names:
            raise ValueError("identities need at least one pattern")
        return cls(emails, names)

    def matches(self, name: str, email: str) -> bool:
        return any(p.search(email) for p in self.emails) or any(
            p.search(name) for p in self.names
        )


def load_identities(path: Path) -> Identities:
    return Identities.from_dict(json.loads(path.read_text(encoding="utf-8")))


# --- vocabulary --------------------------------------------------------------


@dataclass(frozen=True)
class PathRule:
    pattern: re.Pattern[str]
    tech: str
    lines: tuple[re.Pattern[str], ...] | None


@dataclass(frozen=True)
class Vocabulary:
    """Versioned mapping from files and added lines to techs."""

    version: int
    excluded: tuple[re.Pattern[str], ...]
    languages: dict[str, str]
    path_rules: tuple[PathRule, ...]
    signatures: dict[str, re.Pattern[str]]

    @classmethod
    def from_dict(cls, raw: object) -> Vocabulary:
        if not isinstance(raw, dict):
            raise ValueError("vocabulary must be an object")
        version = raw.get("version")
        if not isinstance(version, int):
            raise ValueError("vocabulary version must be an integer")
        languages = raw.get("languages")
        rules = raw.get("path_rules")
        signatures = raw.get("signatures")
        if not isinstance(languages, dict) or not isinstance(rules, list):
            raise ValueError("vocabulary needs languages and path_rules")
        if not isinstance(signatures, dict):
            raise ValueError("vocabulary needs signatures")
        path_rules = []
        for rule in rules:
            if not isinstance(rule, dict) or not {"pattern", "tech"} <= rule.keys():
                raise ValueError("each path rule needs a pattern and a tech")
            lines = rule.get("lines")
            path_rules.append(
                PathRule(
                    _patterns([rule["pattern"]], "path rule")[0],
                    str(rule["tech"]),
                    None if lines is None else _patterns(lines, "path rule lines"),
                )
            )
        return cls(
            version=version,
            excluded=_patterns(raw.get("excluded"), "excluded"),
            languages={str(k).lower(): str(v) for k, v in languages.items()},
            path_rules=tuple(path_rules),
            signatures={
                tech: _combine(regexes, f"signatures.{tech}")
                for tech, regexes in signatures.items()
            },
        )

    def is_excluded(self, path: str) -> bool:
        return any(p.search(path) for p in self.excluded)

    def _file_techs(self, path: str, added: list[str] | None) -> set[str]:
        techs: set[str] = set()
        language = self.languages.get(PurePosixPath(path).suffix.lower())
        if language:
            techs.add(language)
        for rule in self.path_rules:
            if not rule.pattern.search(path):
                continue
            if rule.lines is None or (
                added and any(rx.search(ln) for rx in rule.lines for ln in added)
            ):
                techs.add(rule.tech)
        if added:
            for tech, regex in self.signatures.items():
                if any(regex.search(ln) for ln in added):
                    techs.add(tech)
        return techs

    def _units(self, files: Iterable[tuple[str, list[str] | None]]) -> dict[str, int]:
        units: dict[str, int] = defaultdict(int)
        for path, added in files:
            if self.is_excluded(path):
                continue
            for tech in self._file_techs(path, added):
                units[tech] += 1
        return dict(units)

    def analyze_patch(self, files: dict[str, list[str]]) -> dict[str, int]:
        """Units per tech from the lines added to each file."""
        return self._units(files.items())

    def analyze_names(self, paths: Iterable[str]) -> dict[str, int]:
        """Units per tech from file names alone (no patch content)."""
        return self._units((p, None) for p in paths)


def load_vocabulary(path: Path = VOCABULARY_PATH) -> Vocabulary:
    return Vocabulary.from_dict(json.loads(path.read_text(encoding="utf-8")))


def normalize(units: dict[str, int]) -> dict[str, float]:
    """Weights summing to 1 over the techs detected; empty when none."""
    total = sum(units.values())
    return {tech: n / total for tech, n in units.items()} if total else {}


# --- git history -------------------------------------------------------------


def open_repository(path: Path) -> pygit2.Repository:
    """Open exactly ``path``, never a parent repository above it."""
    return pygit2.Repository(str(path), RepositoryOpenFlag.NO_SEARCH)


def remote_url(repo: pygit2.Repository) -> str:
    """The ``origin`` URL, else the first remote's, else empty."""
    urls = {remote.name: remote.url or "" for remote in repo.remotes}
    return urls.get("origin") or next(iter(urls.values()), "")


def author_day(commit: pygit2.Commit) -> str:
    """Author date as ``YYYY-MM-DD`` in the author's own timezone."""
    zone = timezone(timedelta(minutes=commit.author.offset))
    return datetime.fromtimestamp(commit.author.time, zone).strftime("%Y-%m-%d")


def walk_commits(repo: pygit2.Repository) -> Iterable[pygit2.Commit]:
    """Every commit reachable from a ref or HEAD, like ``git log --all``."""
    walker = repo.walk(None, SortMode.NONE)
    tips = [ref.peel for ref in repo.references.iterator()]
    if not repo.head_is_unborn:
        tips.append(repo.head.peel)
    for peel in tips:
        try:
            walker.push(peel(pygit2.Commit).id)
        except pygit2.GitError:
            continue  # a tag pointing at a tree or a blob: no history
    return walker


def _diff(repo: pygit2.Repository, commit: pygit2.Commit) -> pygit2.Diff:
    if commit.parents:
        return repo.diff(commit.parents[0].tree, commit.tree, context_lines=0)
    return commit.tree.diff_to_tree(context_lines=0, swap=True)


def added_lines(
    repo: pygit2.Repository, commit: pygit2.Commit, keep: Callable[[str], bool]
) -> dict[str, list[str]]:
    """``{path: added lines}`` for the files ``commit`` changed.

    Deleted and binary files, and files ``keep`` rejects, are left out. Lines
    longer than ``MAX_LINE_LENGTH`` (data, not hand-written code) are skipped
    and at most ``MAX_LINES_PER_FILE`` lines are kept per file, so a commit
    importing a huge file costs bounded memory; the file itself still counts.
    Raises ``pygit2.GitError`` when a file's content is not available.
    """
    files: dict[str, list[str]] = {}
    for patch in _diff(repo, commit):
        delta = patch.delta
        path = delta.new_file.path
        hunks = patch.hunks
        if delta.status == DeltaStatus.DELETED or not hunks or not keep(path):
            continue
        kept = files.setdefault(path, [])
        for hunk in hunks:
            for line in hunk.lines:
                if line.origin != "+" or len(kept) >= MAX_LINES_PER_FILE:
                    continue
                text = line.content.rstrip("\r\n")
                if len(text) < MAX_LINE_LENGTH:
                    kept.append(text)
    return files


def touched_paths(repo: pygit2.Repository, commit: pygit2.Commit) -> list[str]:
    """Paths ``commit`` changed, from trees only (no file content needed)."""
    return [delta.new_file.path for delta in _diff(repo, commit).deltas]


_REMOTE = re.compile(
    r"^(?:[a-z][a-z0-9+.-]*://)?(?:[^@/]+@)?([^/:]+)(?::\d+)?[:/](.+)$"
)


def repo_key(remote: str, path: Path) -> str:
    """A stable key per repository: its normalized remote, else its path."""
    match = _REMOTE.match(remote.strip())
    if not match or "." not in match.group(1) or match.group(1).startswith("."):
        return f"local:{remote.strip() or path}"
    host, rest = match.groups()
    rest = rest.strip("/")
    rest = rest.removesuffix(".git")
    return f"{host}/{rest}".lower()


# --- collection --------------------------------------------------------------


@dataclass
class CommitEvidence:
    hash: str
    day: str
    repo: str
    units: dict[str, int]
    has_patch: bool
    public: bool

    @property
    def weights(self) -> dict[str, float]:
        return normalize(self.units)


@dataclass
class CollectResult:
    commits: dict[str, CommitEvidence]
    failures: dict[str, str] = field(default_factory=dict)


def analyze_commit(
    repo: pygit2.Repository, commit: pygit2.Commit, vocabulary: Vocabulary
) -> tuple[dict[str, int], bool]:
    """``(units, has_patch)`` for one commit; names only when content is gone."""
    if len(commit.parents) > 1:
        return {}, True  # a merge adds no lines of its own

    def keep(path: str) -> bool:
        return not vocabulary.is_excluded(path)

    try:
        return vocabulary.analyze_patch(added_lines(repo, commit, keep)), True
    except pygit2.GitError:
        pass
    try:
        return vocabulary.analyze_names(touched_paths(repo, commit)), False
    except pygit2.GitError:
        return {}, False


def collect(
    repos: Iterable[Path],
    identities: Identities,
    vocabulary: Vocabulary,
    is_public: Callable[[str], bool],
    progress: Callable[[str], None] | None = None,
) -> CollectResult:
    """Walk every repository and keep each own commit once, analyzed."""
    result = CollectResult(commits={})
    commits = result.commits
    for path in repos:
        where = str(path)
        if progress:
            progress(where)
        try:
            repo = open_repository(path)
            key = repo_key(remote_url(repo), path)
            own = [
                commit
                for commit in walk_commits(repo)
                if identities.matches(commit.author.name, commit.author.email)
            ]
        except pygit2.GitError as exc:
            result.failures[where] = str(exc)
            continue
        public = is_public(key) if own else False
        for commit in own:
            h = str(commit.id)
            evidence = commits.get(h)
            if evidence is None:
                evidence = CommitEvidence(h, author_day(commit), key, {}, False, public)
                commits[h] = evidence
            evidence.public = evidence.public or public
            if not evidence.has_patch:
                evidence.units, evidence.has_patch = analyze_commit(
                    repo, commit, vocabulary
                )
    return result


# --- visibility --------------------------------------------------------------


class VisibilityUnknown(RuntimeError):
    """GitHub gave no usable answer (network error, rate limit, ...)."""


def github_is_public(slug: str) -> bool:
    """Ask the GitHub REST API whether ``owner/name`` is public.

    Unauthenticated calls cannot see private repositories, so 404 means not
    public. ``GH_TOKEN`` or ``GITHUB_TOKEN``, when set, lifts the rate limit.
    """
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(GITHUB_API + slug, headers=headers, timeout=10)
    except requests.RequestException as exc:
        raise VisibilityUnknown(str(exc)) from exc
    if response.status_code == 404:
        return False
    if response.status_code != 200:
        raise VisibilityUnknown(f"HTTP {response.status_code} for {slug}")
    return response.json().get("private") is False


class GitHubVisibility:
    """Whether a repo key is a public GitHub repository, cached on disk.

    Only definite answers are cached: an unknown one reads as private for
    this run and is asked again next time.
    """

    def __init__(
        self, cache_path: Path, lookup: Callable[[str], bool] = github_is_public
    ) -> None:
        self.cache_path = cache_path
        self.lookup = lookup
        self.cache: dict[str, bool] = (
            json.loads(cache_path.read_text(encoding="utf-8"))
            if cache_path.exists()
            else {}
        )

    def __call__(self, key: str) -> bool:
        prefix = "github.com/"
        if not key.startswith(prefix):
            return False
        slug = key[len(prefix) :]
        if slug not in self.cache:
            try:
                self.cache[slug] = self.lookup(slug)
            except VisibilityUnknown:
                return False
            self.cache_path.write_text(
                json.dumps(self.cache, indent=1, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return self.cache[slug]


# --- aggregation -------------------------------------------------------------


def aggregate(result: CollectResult, vocabulary_version: int) -> dict:
    """Per-day evidence plus a summary; per-day weights sum to 1 when set."""
    per_day: dict[str, dict] = {}
    ordered = sorted(result.commits.values(), key=lambda c: (c.day, c.hash))
    for commit in ordered:
        day = per_day.setdefault(
            commit.day,
            {
                "repos": set(),
                "commits": 0,
                "sums": defaultdict(float),
                "signal": 0,
                "public": False,
            },
        )
        day["repos"].add(commit.repo)
        day["commits"] += 1
        day["public"] = day["public"] or commit.public
        weights = commit.weights
        if weights:
            day["signal"] += 1
            for tech, weight in weights.items():
                day["sums"][tech] += weight
    days = {
        name: {
            "repos": sorted(day["repos"]),
            "commits": day["commits"],
            "public": day["public"],
            "techs": {
                tech: round(total / day["signal"], 6)
                for tech, total in sorted(day["sums"].items())
            },
            "presence": sorted(day["sums"]),
        }
        for name, day in sorted(per_day.items())
    }
    public_days = sum(1 for d in days.values() if d["public"])
    summary = {
        "vocabulary_version": vocabulary_version,
        "unique_commits": len(result.commits),
        "distinct_days": len(days),
        "repos": len({c.repo for c in result.commits.values()}),
        "public_day_share": round(public_days / len(days), 4) if days else 0.0,
        "commits_without_patch": sum(
            1 for c in result.commits.values() if not c.has_patch
        ),
        "failures": dict(sorted(result.failures.items())),
    }
    return {"summary": summary, "days": days}


# --- CLI ---------------------------------------------------------------------


def _read_repo_list(path: Path) -> list[Path]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Path(ln.strip()) for ln in lines if ln.strip() and not ln.startswith("#")]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repos", type=Path, help="file listing repository paths")
    parser.add_argument("--identities", type=Path, help="identities JSON file")
    parser.add_argument("--out", type=Path, help="evidence JSON to write")
    parser.add_argument("--visibility-cache", type=Path, help="GitHub answers cache")
    args = parser.parse_args(argv)

    private = os.environ.get("PROFILE_PRIVATE_DIR")
    defaults = {
        "repos": "repos.txt",
        "identities": "identities.json",
        "out": "evidence.json",
        "visibility_cache": "visibility-cache.json",
    }
    for attr, name in defaults.items():
        if getattr(args, attr) is None:
            if not private:
                parser.error(f"--{attr.replace('_', '-')} or PROFILE_PRIVATE_DIR")
            setattr(args, attr, Path(private) / name)

    vocabulary = load_vocabulary()
    result = collect(
        _read_repo_list(args.repos),
        load_identities(args.identities),
        vocabulary,
        is_public=GitHubVisibility(args.visibility_cache),
        progress=lambda repo: print(f"walking {repo}", file=sys.stderr),
    )
    output = aggregate(result, vocabulary.version)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=1) + "\n", encoding="utf-8")
    s = output["summary"]
    print(
        f"unique commits: {s['unique_commits']} | distinct days: "
        f"{s['distinct_days']} | repos: {s['repos']} | public day share: "
        f"{s['public_day_share']:.1%} | without patch: "
        f"{s['commits_without_patch']} | failures: {len(s['failures'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
