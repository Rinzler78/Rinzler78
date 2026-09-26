"""Tiny synthetic git repositories with controlled authors and dates.

Every identity, path and file content here is invented; nothing refers to a
real repository or person.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

OWN = ("Jane Sample", "jane.sample@example.org")
OTHER = ("Other Dev", "other.dev@example.net")


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's git config, hooks and hook environment out.

    Inside a git hook (pre-commit runs these tests) git exports variables such
    as ``GIT_INDEX_FILE`` and ``GIT_DIR`` that would redirect every fixture
    command to the outer repository; they are removed first.
    """
    for name in list(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Fixture")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "fixture@example.com")


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=full_env,
    ).stdout


Commit = tuple[tuple[str, str], str, dict[str, str]]


@pytest.fixture
def make_repo(tmp_path: Path) -> Callable[..., Path]:
    """Build a repo from ``(author, iso_date, {path: content})`` commits."""

    def _make(name: str, commits: list[Commit], remote: str | None = None) -> Path:
        repo = tmp_path / name
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        for (author, email), date, files in commits:
            for rel, content in files.items():
                target = repo / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            git(repo, "add", "-A")
            git(
                repo,
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "change",
                env={
                    "GIT_AUTHOR_NAME": author,
                    "GIT_AUTHOR_EMAIL": email,
                    "GIT_AUTHOR_DATE": date,
                    "GIT_COMMITTER_DATE": date,
                },
            )
        if remote:
            git(repo, "remote", "add", "origin", remote)
        return repo

    return _make
