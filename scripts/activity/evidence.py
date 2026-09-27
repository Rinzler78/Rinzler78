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

File counts
    Each commit also records how many non-excluded files it analyzed, with or
    without a tech (a README counts). Per day, ``files`` is that total and
    ``file_counts`` the number of files touching each tech, so the allocation
    can give a tech the share of the day's files that touched it (ADR-013).
    Names-only commits count their files the same way; a merge counts none.

Project context (vocabulary version 2)
    Each changed file also inherits the techs of its nearest enclosing
    project file in the commit's tree (``project_files``: ``.csproj``,
    ``packages.config``, ``build.gradle``, ``package.json``,
    ``pyproject.toml``...), read from the references and target frameworks it
    declares (``project_rules``): a file of a Xamarin.iOS project counts for
    xamarin and ios as well as for its language. A rule may be limited to
    some files of the project (``scope``). A project whose tree holds the
    Model / View / ViewModel triad counts the files of those three layers for
    mvvm.

MVVM at project level (vocabulary version 4)
    A project is MVVM when its tree defines a ViewModel (a class of a file
    the file-level mvvm rules detect, or any class deriving from one,
    transitively across the tree), when it references an MVVM framework, or
    when it references a project that is (``ProjectReference``, shared-project
    ``Import``). A reference leading outside the tree (a submodule) resolves
    through the ``MvvmRegistry`` built from every repository's HEAD before
    the walk. In an MVVM project the whole presentation layer
    (``presentation``: pages, views, controls, page controllers, view models,
    bindable models, converters, renderers) counts for mvvm; a class deriving
    from a ViewModel counts wherever it lives.

Behavior rules (vocabulary version 3)
    ``conjunctions`` need every group of signatures to match the added lines
    (a file exposing commands AND raising PropertyChanged is MVVM, whatever
    its name). An ``interface IName`` definition counts for the platform
    abstraction when classes of both a ``*.iOS`` and a ``*.Droid`` /
    ``*.Android`` project implement ``IName`` (``platform_sides``).
    ``context_rules`` apply to repositories holding a mobile project
    (``mobile_markers``): build and publish scripts touching build, sign,
    ipa, apk, publish... (``keywords``, in the path or the added lines) and CI
    pipelines count for mobile-build-release. A ``.h`` header is
    Objective-C when its directory or its build root (nearest ``.xcodeproj``,
    project file, ``CMakeLists.txt``, ``Makefile`` or ``.vcxproj``, else the
    repository) holds ``.m`` / ``.mm`` files, C/C++ otherwise. Everything is
    cached by object id, so unchanged trees and project files are read once.

Test-only commits
    A commit whose analyzed files all count for ``tests`` is test-only; days
    record how many (``test_only_commits``), as evidence of test-first work.

Ownership
    Only repositories owned by the author or by a company he worked for count.
    ``owners.json`` lists allowed prefixes of repository keys; the commits of
    any other repository are dropped before deduplication and reported in
    ``summary.excluded_repos`` with their number of own commits.

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
import posixpath
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
class ProjectRule:
    tech: str
    content: re.Pattern[str]
    files: re.Pattern[str] | None
    scope: re.Pattern[str] | None


@dataclass(frozen=True)
class Conjunction:
    tech: str
    groups: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class ContextRule:
    tech: str
    requires: str
    path: re.Pattern[str]
    keywords: re.Pattern[str] | None


CONTEXT_REQUIREMENTS = ("mobile-repo",)


def _conjunctions(raw: object) -> tuple[Conjunction, ...]:
    if not isinstance(raw, list):
        raise ValueError("conjunctions must be a list")
    out = []
    for rule in raw:
        groups = rule.get("all") if isinstance(rule, dict) else None
        if not isinstance(groups, list) or not groups:
            raise ValueError("each conjunction needs a tech and non-empty 'all'")
        tech = str(rule.get("tech"))
        out.append(
            Conjunction(
                tech, tuple(_combine(g, f"conjunctions.{tech}") for g in groups)
            )
        )
    return tuple(out)


def _context_rules(raw: object) -> tuple[ContextRule, ...]:
    if not isinstance(raw, list):
        raise ValueError("context_rules must be a list")
    out = []
    for rule in raw:
        if (
            not isinstance(rule, dict)
            or not {"tech", "requires", "path"} <= rule.keys()
        ):
            raise ValueError("each context rule needs a tech, requires and path")
        if rule["requires"] not in CONTEXT_REQUIREMENTS:
            raise ValueError(f"context rule requires unknown {rule['requires']!r}")
        out.append(
            ContextRule(
                str(rule["tech"]),
                rule["requires"],
                _patterns([rule["path"]], "context rule path")[0],
                _optional_pattern(rule.get("keywords"), "context rule keywords"),
            )
        )
    return tuple(out)


def _platform_sides(raw: object) -> dict[str, re.Pattern[str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict) or set(raw) != {"ios", "android"}:
        raise ValueError("platform_sides needs exactly 'ios' and 'android'")
    return {side: _patterns([rx], "platform_sides")[0] for side, rx in raw.items()}


def _project_rules(raw: object) -> tuple[ProjectRule, ...]:
    if not isinstance(raw, list):
        raise ValueError("project_rules must be a list")
    rules = []
    for rule in raw:
        if not isinstance(rule, dict) or not {"tech", "content"} <= rule.keys():
            raise ValueError("each project rule needs a tech and content")
        files, scope = rule.get("files"), rule.get("scope")
        rules.append(
            ProjectRule(
                tech=str(rule["tech"]),
                content=_combine(rule["content"], f"project_rules.{rule['tech']}"),
                files=None if files is None else _patterns([files], "files")[0],
                scope=None if scope is None else _patterns([scope], "scope")[0],
            )
        )
    return tuple(rules)


def _optional_pattern(raw: object, what: str) -> re.Pattern[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{what} must be a regular expression")
    return _patterns([raw], what)[0]


@dataclass(frozen=True)
class Vocabulary:
    """Versioned mapping from files and added lines to techs."""

    version: int
    excluded: tuple[re.Pattern[str], ...]
    languages: dict[str, str]
    path_rules: tuple[PathRule, ...]
    signatures: dict[str, re.Pattern[str]]
    project_files: re.Pattern[str] | None = None
    project_rules: tuple[ProjectRule, ...] = ()
    conjunctions: tuple[Conjunction, ...] = ()
    context_rules: tuple[ContextRule, ...] = ()
    mobile_markers: re.Pattern[str] | None = None
    presentation: re.Pattern[str] | None = None
    platform_sides: dict[str, re.Pattern[str]] = field(default_factory=dict)
    platform_interface_tech: str | None = None

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
            project_files=_optional_pattern(raw.get("project_files"), "project_files"),
            project_rules=_project_rules(raw.get("project_rules", [])),
            conjunctions=_conjunctions(raw.get("conjunctions", [])),
            context_rules=_context_rules(raw.get("context_rules", [])),
            presentation=_optional_pattern(raw.get("presentation"), "presentation"),
            mobile_markers=_optional_pattern(
                raw.get("mobile_markers"), "mobile_markers"
            ),
            platform_sides=_platform_sides(raw.get("platform_sides")),
            platform_interface_tech=raw.get("platform_interface_tech"),
        )

    def is_excluded(self, path: str) -> bool:
        return any(p.search(path) for p in self.excluded)

    def _file_techs(
        self,
        path: str,
        added: list[str] | None,
        context: ProjectContext | None = None,
    ) -> set[str]:
        techs: set[str] = set()
        suffix = PurePosixPath(path).suffix.lower()
        language = self.languages.get(suffix)
        if context is not None and suffix in HEADER_SUFFIXES:
            language = context.header_language(path) or language
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
            for rule in self.conjunctions:
                if all(any(rx.search(ln) for ln in added) for rx in rule.groups):
                    techs.add(rule.tech)
        if context is not None:
            techs |= context.project_techs(path, added)
        return techs

    def file_techs(
        self,
        files: Iterable[tuple[str, list[str] | None]],
        context: ProjectContext | None = None,
    ) -> list[set[str]]:
        """The techs of each analyzed (non-excluded) file."""
        return [
            self._file_techs(path, added, context)
            for path, added in files
            if not self.is_excluded(path)
        ]

    def _units(
        self,
        files: Iterable[tuple[str, list[str] | None]],
        context: ProjectContext | None = None,
    ) -> dict[str, int]:
        return _count_units(self.file_techs(files, context))

    def analyze_patch(
        self, files: dict[str, list[str]], context: ProjectContext | None = None
    ) -> dict[str, int]:
        """Units per tech from the lines added to each file."""
        return self._units(files.items(), context)

    def analyze_names(
        self, paths: Iterable[str], context: ProjectContext | None = None
    ) -> dict[str, int]:
        """Units per tech from file names alone (no patch content)."""
        return self._units(((p, None) for p in paths), context)


def _count_units(sets: Iterable[set[str]]) -> dict[str, int]:
    units: dict[str, int] = defaultdict(int)
    for techs in sets:
        for tech in techs:
            units[tech] += 1
    return dict(units)


# --- project context ---------------------------------------------------------

HEADER_SUFFIXES = (".h",)
OBJC_SUFFIXES = (".m", ".mm")
_BUILD_ROOTS = re.compile(r"(?i)(\.xcodeproj|\.vcxproj|^CMakeLists\.txt|^Makefile)$")
MAX_PROJECT_FILE = 512 * 1024
_CLASS_BASES = re.compile(r"\bclass\s+\w+(?:<[^>]*>)?\s*:\s*([^{\n]+)")
_INTERFACE_NAME = re.compile(r"\b(I[A-Z]\w*)\b")
_CLASS_DECL = re.compile(r"\bclass\s+(\w+)(?:<[^>]*>)?(?:\s*:\s*(?:[\w]+\.)*(\w+))?")
_PROJECT_REF = re.compile(
    r'<(?:ProjectReference\s+Include|Import\s+Project)\s*=\s*"([^"]+\.'
    r'(?:csproj|fsproj|vbproj|projitems|shproj))"',
    re.IGNORECASE,
)
_INTERFACE_DEF = re.compile(r"\binterface\s+(I[A-Z]\w*)\b")
TRIAD_DIRS = {"models": "model", "views": "view", "viewmodels": "viewmodel"}


def _triad_role(name: str, is_dir: bool) -> str | None:
    """The MVVM layer a file or folder name belongs to, if any."""
    if is_dir:
        return TRIAD_DIRS.get(name.lower())
    stem = PurePosixPath(name).stem.lower()
    if stem.endswith("viewmodel"):
        return "viewmodel"
    if stem.endswith("model"):
        return "model"
    if stem.endswith(("view", "page")):
        return "view"
    return None


def _parent(path: str) -> str:
    parent = str(PurePosixPath(path).parent)
    return "" if parent == "." else parent


@dataclass
class MvvmRegistry:
    """MVVM projects (lowercase file names) and ViewModel classes seen at the
    HEAD of every repository, to resolve references into submodules."""

    projects: set[str] = field(default_factory=set)
    classes: set[str] = field(default_factory=set)


class ContextCache:
    """Per-run caches keyed by git object id (content-addressed)."""

    def __init__(self, registry: MvvmRegistry | None = None) -> None:
        self.registry = registry or MvvmRegistry()
        self.code: dict[str, tuple[dict[str, str], frozenset[str], frozenset[str]]] = {}
        self.blob: dict[str, tuple[tuple[tuple[str, str | None], ...], bool]] = {}
        self.viewmodels: dict[str, frozenset[str]] = {}
        self.mvvm_projects: dict[str, bool] = {}
        self.entries: dict[str, list[tuple[str, bool, object]]] = {}
        self.objc: dict[str, bool] = {}
        self.found: dict[str, list] = {}
        self.implemented: dict[str, frozenset[str]] = {}
        self.triad: dict[str, frozenset[str]] = {}
        self.content: dict[str, str | None] = {}


class ProjectContext:
    """What a commit's tree says about the project enclosing each file."""

    def __init__(
        self,
        repo: pygit2.Repository,
        tree: pygit2.Tree,
        vocabulary: Vocabulary,
        cache: ContextCache,
    ) -> None:
        self.repo, self.tree, self.voc, self.cache = repo, tree, vocabulary, cache

    # tree access
    def _dir(self, path: str) -> pygit2.Tree | None:
        if not path:
            return self.tree
        try:
            obj = self.tree[path]
        except KeyError:
            return None
        return obj if isinstance(obj, pygit2.Tree) else None

    def _entries(self, tree: pygit2.Tree) -> list[tuple[str, bool, object]]:
        key = str(tree.id)
        if key not in self.cache.entries:
            self.cache.entries[key] = [
                (e.name, e.type_str == "tree", e.id) for e in tree
            ]
        return self.cache.entries[key]

    def _subtree(self, oid: object) -> pygit2.Tree:
        return self.repo[oid]

    def _ancestors(self, path: str) -> list[str]:
        parts = PurePosixPath(path).parts[:-1]
        return ["/".join(parts[:i]) for i in range(len(parts), -1, -1)]

    def _nearest(self, path: str, match) -> tuple[str, pygit2.Tree] | None:
        for directory in self._ancestors(path):
            tree = self._dir(directory)
            if tree is not None and any(
                match(name) for name, _, _ in self._entries(tree)
            ):
                return directory, tree
        return None

    # Objective-C headers
    def _has_objc(self, tree: pygit2.Tree) -> bool:
        key = str(tree.id)
        if key not in self.cache.objc:
            found = False
            for name, is_dir, oid in self._entries(tree):
                if is_dir:
                    found = self._has_objc(self._subtree(oid))
                else:
                    found = name.lower().endswith(OBJC_SUFFIXES)
                if found:
                    break
            self.cache.objc[key] = found
        return self.cache.objc[key]

    def _is_build_root(self, name: str) -> bool:
        pf = self.voc.project_files
        return bool(_BUILD_ROOTS.search(name) or (pf and pf.search(name)))

    def header_language(self, path: str) -> str | None:
        """``objective-c`` for a header of an Objective-C project, else None."""
        here = self._dir(_parent(path))
        if here is not None and self._has_objc(here):
            return "objective-c"
        root = self._nearest(path, self._is_build_root)
        tree = root[1] if root else self.tree
        return "objective-c" if self._has_objc(tree) else None

    # project files
    def _text(self, oid: object) -> str | None:
        key = str(oid)
        if key not in self.cache.content:
            try:
                data = self.repo[oid].data[:MAX_PROJECT_FILE]
                self.cache.content[key] = data.decode("utf-8", "replace")
            except (KeyError, pygit2.GitError):
                self.cache.content[key] = None
        return self.cache.content[key]

    def _find(self, tree: pygit2.Tree, pattern: re.Pattern[str], depth: int) -> list:
        """``(name, is_dir, oid)`` entries matching ``pattern`` down to ``depth``."""
        key = f"{tree.id}:{pattern.pattern}:{depth}"
        if key not in self.cache.found:
            found = []
            for name, is_dir, oid in self._entries(tree):
                if pattern.search(name):
                    found.append((name, is_dir, oid))
                if is_dir and depth > 0:
                    found.extend(self._find(self._subtree(oid), pattern, depth - 1))
            self.cache.found[key] = found
        return self.cache.found[key]

    def is_mobile_repo(self) -> bool:
        markers = self.voc.mobile_markers
        return markers is not None and bool(self._find(self.tree, markers, 3))

    def _implemented(self, tree: pygit2.Tree) -> frozenset[str]:
        """Interface names (``I[A-Z]...``) implemented by classes under ``tree``."""
        key = str(tree.id)
        if key not in self.cache.implemented:
            names: set[str] = set()
            for name, is_dir, oid in self._entries(tree):
                if is_dir:
                    names |= self._implemented(self._subtree(oid))
                elif name.endswith(".cs"):
                    text = self._text(oid) or ""
                    for bases in _CLASS_BASES.findall(text):
                        names.update(_INTERFACE_NAME.findall(bases))
            self.cache.implemented[key] = frozenset(names)
        return self.cache.implemented[key]

    def implemented_on_both_sides(self, interface: str) -> bool:
        for pattern in self.voc.platform_sides.values():
            dirs = [
                self._subtree(oid)
                for _, is_dir, oid in self._find(self.tree, pattern, 3)
                if is_dir
            ]
            if not any(interface in self._implemented(d) for d in dirs):
                return False
        return True

    def _triad(self, tree: pygit2.Tree) -> frozenset[str]:
        key = str(tree.id)
        if key not in self.cache.triad:
            roles: set[str] = set()
            for name, is_dir, oid in self._entries(tree):
                role = _triad_role(name, is_dir)
                if role:
                    roles.add(role)
                if is_dir:
                    roles |= self._triad(self._subtree(oid))
            self.cache.triad[key] = frozenset(roles)
        return self.cache.triad[key]

    def _context_rule_techs(self, path: str, added: list[str] | None) -> set[str]:
        techs: set[str] = set()
        for rule in self.voc.context_rules:
            if not rule.path.search(path) or not self.is_mobile_repo():
                continue
            keywords = rule.keywords
            if (
                keywords is None
                or keywords.search(path)
                or any(keywords.search(ln) for ln in added or ())
            ):
                techs.add(rule.tech)
        tech = self.voc.platform_interface_tech
        if tech and added and self.voc.platform_sides:
            for line in added:
                match = _INTERFACE_DEF.search(line)
                if match and self.implemented_on_both_sides(match.group(1)):
                    techs.add(tech)
                    break
        return techs

    # MVVM at project level
    def _blob_code(self, path: str, oid: object) -> tuple:
        """``(classes, seed)`` of a C# file: ``(name, base)`` declarations and
        whether the file-level rules see a ViewModel in it."""
        key = f"{oid}:{path}"
        if key not in self.cache.blob:
            text = self._text(oid) or ""
            lines = [ln for ln in text.splitlines() if len(ln) < MAX_LINE_LENGTH]
            classes = tuple(
                (m.group(1), m.group(2))
                for ln in lines
                for m in _CLASS_DECL.finditer(ln)
            )
            seed = "mvvm" in self.voc._file_techs(path, lines[:MAX_LINES_PER_FILE])
            self.cache.blob[key] = (classes, seed)
        return self.cache.blob[key]

    def _code(self, tree: pygit2.Tree, prefix: str) -> tuple:
        """``(bases, seeds, defined)`` of every C# class under ``tree``."""
        key = f"{tree.id}:{prefix}"
        if key not in self.cache.code:
            bases: dict[str, str] = {}
            seeds: set[str] = set()
            defined: set[str] = set()
            for name, is_dir, oid in self._entries(tree):
                path = f"{prefix}{name}"
                if is_dir:
                    sub = self._code(self._subtree(oid), f"{path}/")
                    bases.update(sub[0])
                    seeds |= sub[1]
                    defined |= sub[2]
                elif name.endswith(".cs") and not self.voc.is_excluded(path):
                    classes, seed = self._blob_code(path, oid)
                    for cls, base in classes:
                        defined.add(cls)
                        if base:
                            bases[cls] = base
                        if seed:
                            seeds.add(cls)
            self.cache.code[key] = (bases, frozenset(seeds), frozenset(defined))
        return self.cache.code[key]

    def viewmodels(self) -> frozenset[str]:
        """ViewModel classes of the tree: seeds, registry, and their heirs."""
        key = str(self.tree.id)
        if key not in self.cache.viewmodels:
            bases, seeds, _ = self._code(self.tree, "")
            found = set(seeds) | self.cache.registry.classes
            grew = True
            while grew:
                heirs = {c for c, b in bases.items() if b in found and c not in found}
                found |= heirs
                grew = bool(heirs)
            self.cache.viewmodels[key] = frozenset(found)
        return self.cache.viewmodels[key]

    def _project_files(self, tree: pygit2.Tree) -> list[tuple[str, object]]:
        pf = self.voc.project_files
        return [
            (name, oid)
            for name, is_dir, oid in self._entries(tree)
            if not is_dir and pf is not None and pf.search(name)
        ]

    def is_mvvm_project(
        self, directory: str, seen: frozenset[str] = frozenset()
    ) -> bool:
        key = f"{self.tree.id}:{directory}"
        if key in self.cache.mvvm_projects:
            return self.cache.mvvm_projects[key]
        tree = self._dir(directory)
        prefix = f"{directory}/" if directory else ""
        found = tree is not None and bool(
            self._code(tree, prefix)[2] & self.viewmodels()
        )
        frameworks = [r for r in self.voc.project_rules if r.tech == "mvvm"]
        for _, oid in self._project_files(tree) if tree is not None else []:
            if found:
                break
            text = self._text(oid) or ""
            if any(r.content.search(text) for r in frameworks):
                found = True
                break
            for ref in _PROJECT_REF.findall(text):
                target = posixpath.normpath(
                    posixpath.join(directory, ref.replace("\\", "/"))
                )
                parent = _parent(target)
                if parent in seen or target.startswith(".."):
                    continue
                if self._file_exists(target):
                    found = self.is_mvvm_project(parent, seen | {directory})
                else:
                    found = PurePosixPath(target).name.lower() in (
                        self.cache.registry.projects
                    )
                if found:
                    break
        self.cache.mvvm_projects[key] = found
        return found

    def _file_exists(self, path: str) -> bool:
        try:
            self.tree[path]
        except KeyError:
            return False
        return True

    def _mvvm_techs(
        self, path: str, directory: str, added: list[str] | None
    ) -> set[str]:
        presentation = self.voc.presentation
        if (
            presentation is not None
            and presentation.search(path)
            and self.is_mvvm_project(directory)
        ):
            return {"mvvm"}
        if added and path.endswith(".cs"):
            vms = self.viewmodels()
            for line in added:
                for match in _CLASS_DECL.finditer(line):
                    if match.group(1) in vms:
                        return {"mvvm"}
        return set()

    def project_techs(self, path: str, added: list[str] | None = None) -> set[str]:
        """Techs a file inherits from its project, repository and platforms."""
        techs = self._context_rule_techs(path, added)
        pf = self.voc.project_files
        project = self._nearest(path, pf.search) if pf is not None else None
        directory, tree = project if project else ("", self.tree)
        relative = path[len(directory) + 1 :] if directory else path
        techs |= self._mvvm_techs(path, directory, added)
        if len(self._triad(tree)) == len(TRIAD_DIRS):
            parts = PurePosixPath(relative).parts
            if any(TRIAD_DIRS.get(p.lower()) for p in parts[:-1]) or _triad_role(
                parts[-1], False
            ):
                techs.add("mvvm")
        if project is None:
            return techs
        for name, _, oid in self._entries(tree):
            if not pf.search(name):
                continue
            text = self._text(oid)
            if text is None:
                continue
            for rule in self.voc.project_rules:
                if rule.files is not None and not rule.files.search(name):
                    continue
                if rule.scope is not None and not rule.scope.search(relative):
                    continue
                if rule.content.search(text):
                    techs.add(rule.tech)
        return techs


def load_vocabulary(path: Path = VOCABULARY_PATH) -> Vocabulary:
    return Vocabulary.from_dict(json.loads(path.read_text(encoding="utf-8")))


# --- owners ------------------------------------------------------------------


@dataclass(frozen=True)
class Owners:
    """Repository key prefixes whose commits count (author's or employers')."""

    allow: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: object) -> Owners:
        allow = raw.get("allow") if isinstance(raw, dict) else None
        if (
            not isinstance(allow, list)
            or not allow
            or not all(isinstance(p, str) and p for p in allow)
        ):
            raise ValueError("owners need a non-empty 'allow' list of key prefixes")
        return cls(tuple(allow))

    def allows(self, key: str) -> bool:
        return key.startswith(self.allow)


def load_owners(path: Path) -> Owners:
    return Owners.from_dict(json.loads(path.read_text(encoding="utf-8")))


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
    files: int = 0
    test_only: bool = False

    @property
    def weights(self) -> dict[str, float]:
        return normalize(self.units)


@dataclass
class CollectResult:
    commits: dict[str, CommitEvidence]
    failures: dict[str, str] = field(default_factory=dict)
    excluded: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Analysis:
    units: dict[str, int]
    has_patch: bool
    files: int
    test_only: bool


def _analysis(sets: list[set[str]], has_patch: bool) -> Analysis:
    test_only = bool(sets) and all("tests" in techs for techs in sets)
    return Analysis(_count_units(sets), has_patch, len(sets), test_only)


def analyze_commit(
    repo: pygit2.Repository,
    commit: pygit2.Commit,
    vocabulary: Vocabulary,
    cache: ContextCache | None = None,
) -> Analysis:
    """Units, files and test-only flag for one commit; names only when
    content is gone. ``files`` counts the analyzed (non-excluded) files."""
    if len(commit.parents) > 1:
        return Analysis({}, True, 0, False)  # a merge adds no lines of its own

    def keep(path: str) -> bool:
        return not vocabulary.is_excluded(path)

    try:
        tree = commit.tree
    except pygit2.GitError:
        return Analysis({}, False, 0, False)
    context = ProjectContext(repo, tree, vocabulary, cache or ContextCache())
    try:
        files = added_lines(repo, commit, keep)
        return _analysis(vocabulary.file_techs(files.items(), context), True)
    except pygit2.GitError:
        pass
    try:
        paths = touched_paths(repo, commit)
    except pygit2.GitError:
        return Analysis({}, False, 0, False)
    sets = vocabulary.file_techs(((p, None) for p in paths), context)
    return _analysis(sets, False)


def mvvm_registry(
    repos: Iterable[Path],
    vocabulary: Vocabulary,
    owned: Callable[[str], bool] = lambda key: True,
) -> MvvmRegistry:
    """MVVM projects and ViewModel classes at the HEAD of every repository."""
    registry = MvvmRegistry()
    cache = ContextCache()
    pf = vocabulary.project_files
    for path in repos:
        try:
            repo = open_repository(path)
            if repo.head_is_unborn or not owned(repo_key(remote_url(repo), path)):
                continue
            tree = repo.head.peel(pygit2.Commit).tree
        except pygit2.GitError:
            continue
        context = ProjectContext(repo, tree, vocabulary, cache)
        registry.classes |= context.viewmodels()
        stack = [("", tree)]
        while stack:
            directory, sub = stack.pop()
            for name, is_dir, oid in context._entries(sub):
                if is_dir:
                    child = f"{directory}/{name}" if directory else name
                    stack.append((child, context._subtree(oid)))
                elif pf is not None and pf.search(name):
                    if context.is_mvvm_project(directory):
                        registry.projects.add(name.lower())
    return registry


def collect(
    repos: Iterable[Path],
    identities: Identities,
    vocabulary: Vocabulary,
    is_public: Callable[[str], bool],
    progress: Callable[[str], None] | None = None,
    owned: Callable[[str], bool] = lambda key: True,
    registry: MvvmRegistry | None = None,
) -> CollectResult:
    """Walk every repository and keep each own commit once, analyzed.

    Commits of repositories ``owned`` rejects are dropped before dedupe and
    counted per repository key in ``result.excluded``.
    """
    result = CollectResult(commits={})
    excluded: dict[str, set[str]] = defaultdict(set)
    cache = ContextCache(registry)
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
        if not owned(key):
            if own:
                excluded[key].update(str(c.id) for c in own)
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
                analysis = analyze_commit(repo, commit, vocabulary, cache)
                evidence.units = analysis.units
                evidence.has_patch = analysis.has_patch
                evidence.files = analysis.files
                evidence.test_only = analysis.test_only
    result.excluded = {key: len(hashes) for key, hashes in sorted(excluded.items())}
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
                "files": 0,
                "file_counts": defaultdict(int),
                "test_only": 0,
            },
        )
        day["test_only"] += int(commit.test_only)
        day["repos"].add(commit.repo)
        day["commits"] += 1
        day["files"] += commit.files
        for tech, count in commit.units.items():
            day["file_counts"][tech] += count
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
            "files": day["files"],
            "file_counts": dict(sorted(day["file_counts"].items())),
            "test_only_commits": day["test_only"],
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
        "excluded_repos": dict(sorted(result.excluded.items())),
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
    parser.add_argument("--owners", type=Path, help="allowed repository owners")
    args = parser.parse_args(argv)

    private = os.environ.get("PROFILE_PRIVATE_DIR")
    defaults = {
        "repos": "repos.txt",
        "identities": "identities.json",
        "out": "evidence.json",
        "visibility_cache": "visibility-cache.json",
        "owners": "owners.json",
    }
    for attr, name in defaults.items():
        if getattr(args, attr) is None:
            if not private:
                parser.error(f"--{attr.replace('_', '-')} or PROFILE_PRIVATE_DIR")
            setattr(args, attr, Path(private) / name)

    vocabulary = load_vocabulary()
    repos = _read_repo_list(args.repos)
    owners = load_owners(args.owners)
    result = collect(
        repos,
        load_identities(args.identities),
        vocabulary,
        is_public=GitHubVisibility(args.visibility_cache),
        progress=lambda repo: print(f"walking {repo}", file=sys.stderr),
        owned=owners.allows,
        registry=mvvm_registry(repos, vocabulary, owners.allows),
    )
    output = aggregate(result, vocabulary.version)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=1) + "\n", encoding="utf-8")
    s = output["summary"]
    print(
        f"unique commits: {s['unique_commits']} | distinct days: "
        f"{s['distinct_days']} | repos: {s['repos']} | public day share: "
        f"{s['public_day_share']:.1%} | without patch: "
        f"{s['commits_without_patch']} | failures: {len(s['failures'])} | "
        f"excluded repos: {len(s['excluded_repos'])}"
    )
    for key, count in s["excluded_repos"].items():
        print(f"excluded {key}: {count} commit(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
