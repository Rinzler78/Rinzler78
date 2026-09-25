"""The pre-commit test selector widens when unsure, and never guesses.

Skipping a test that a change could break is the one failure mode that matters
here: it turns a green commit into a false statement. Every case below is
either an exact mapping or a deliberate widening to the full suite (``None``).
"""

from __future__ import annotations

from scripts.impacted_tests import select


def test_a_test_file_selects_itself():
    assert select(["tests/test_score_engine.py"]) == ["tests/test_score_engine.py"]


def test_a_module_selects_its_sibling_guard():
    assert select(["scripts/score_engine.py"]) == ["tests/test_score_engine.py"]


def test_generation_modules_also_pull_the_artifact_guards():
    selected = select(["scripts/generate.py"])
    assert "tests/test_generation.py" in selected
    assert "tests/test_hero.py" in selected


def test_data_changes_pull_the_data_and_artifact_guards():
    selected = select(["data/techs.json"])
    assert "tests/test_real_data.py" in selected
    assert "tests/test_generation.py" in selected


def test_conftest_widens_to_everything():
    assert select(["tests/conftest.py"]) is None


def test_a_module_without_a_sibling_guard_widens_to_everything():
    # Guessing coverage for an unmapped module is how a real regression slips
    # through a green pre-commit run.
    assert select(["scripts/__init__.py"]) is None


def test_packaging_and_ci_changes_widen_to_everything():
    assert select(["pyproject.toml"]) is None
    assert select([".github/workflows/ci.yml"]) is None


def test_prose_alone_selects_nothing():
    assert select(["docs/adr/0011-committed-reference-date.md"]) == []


def test_one_widening_file_widens_the_whole_set():
    assert select(["tests/test_hero.py", "pyproject.toml"]) is None
