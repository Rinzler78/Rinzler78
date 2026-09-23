#!/usr/bin/env python3
"""Run the tests a set of changed files can affect, and only those.

The pre-commit stage has to return in seconds or it stops being usable inside a
red-green-refactor loop. It receives the staged filenames, so it can ask a
narrower question than "is the repo green": *does what I just touched still
work*. The full suite, the coverage floor and the dependency audit stay on the
later gates, where a slower answer is the right trade.

Mapping, deliberately conservative — when in doubt, widen rather than skip:

- ``tests/test_x.py``          → itself
- ``scripts/x.py``             → ``tests/test_x.py`` when it exists
- data, schemas, templates,
  fonts, generated artifacts    → the generation and real-data guards
- anything else (pyproject,
  CI config, unmapped module)   → the whole suite

Usage: ``impacted_tests.py <changed file> [...]`` — exits with pytest's status,
or 0 when nothing selected can affect a test.
"""

from __future__ import annotations

import pathlib
import subprocess  # nosec B404 - fixed argv, no shell
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
TESTS = REPO / "tests"

# A change anywhere in these trees re-runs the guards that read real data or
# real generated output, because the mapping from file to test is not 1:1.
DATA_LIKE = (
    "data/",
    "schemas/",
    "scripts/templates/",
    "assets/",
    "pages/",
    "i18n-cache/",
)
DATA_TESTS = (
    "tests/test_generation.py",
    "tests/test_real_data.py",
    "tests/test_hero.py",
)

# Modules whose guards are not named ``test_<stem>.py``. Anything absent here
# and without a matching sibling widens to the full suite rather than guess.
MODULE_TESTS = {
    "generate": DATA_TESTS + ("tests/test_reference_date.py",),
    "validate": DATA_TESTS,
    "validate_data": DATA_TESTS + ("tests/test_real_data.py",),
    "data_loader": DATA_TESTS + ("tests/test_data_loader.py",),
    "font_outline": ("tests/test_font_outline.py", "tests/test_hero.py"),
}


def select(changed: list[str]) -> list[str] | None:
    """Return the test paths to run, or ``None`` to mean "run everything"."""
    selected: set[str] = set()
    for raw in changed:
        path = raw.replace("\\", "/")
        if path.startswith("tests/") and path.endswith(".py"):
            if path.endswith("conftest.py"):
                return None  # shared fixtures reach every test
            selected.add(path)
        elif path.startswith("scripts/") and path.endswith(".py"):
            stem = pathlib.Path(path).stem
            if stem in MODULE_TESTS:
                selected.update(MODULE_TESTS[stem])
                continue
            sibling = TESTS / f"test_{stem}.py"
            if not sibling.exists():
                return None  # no 1:1 guard — do not guess which tests cover it
            selected.add(str(sibling.relative_to(REPO)))
        elif path.startswith(DATA_LIKE) or path.startswith("README"):
            selected.update(DATA_TESTS)
        elif path.endswith((".md", ".txt", ".gitignore")):
            continue  # prose and ignore lists drive no test
        else:
            return None  # packaging, CI, tooling: widen to the full suite

    return sorted(p for p in selected if (REPO / p).exists())


def main(argv: list[str]) -> int:
    selection = select(argv)
    if selection is not None and not selection:
        print("[impacted_tests.py] no test affected by the staged files")
        return 0

    target = selection if selection is not None else []
    label = " ".join(target) if target else "the full suite"
    print(f"[impacted_tests.py] running {label}")
    return subprocess.call(  # nosec B603 - fixed argv, no shell
        [sys.executable, "-m", "pytest", "-q", "--no-header", *target],
        cwd=REPO,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
