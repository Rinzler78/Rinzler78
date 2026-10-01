"""The pre-commit test selector widens when unsure, and never guesses.

Skipping a test that a change could break is the one failure mode that matters
here: it turns a green commit into a false statement. Every case below is
either an exact mapping or a deliberate widening to the full suite (``None``).
"""

from __future__ import annotations

from scripts.impacted_tests import select


def test_a_test_file_selects_itself():
    assert select(["tests/test_view_builder.py"]) == ["tests/test_view_builder.py"]


def test_a_module_selects_its_sibling_guard():
    assert select(["scripts/view_builder.py"]) == ["tests/test_view_builder.py"]


def test_generation_modules_also_pull_the_artifact_guards():
    selected = select(["scripts/generate.py"])
    assert "tests/test_generation.py" in selected
    assert "tests/test_front_page.py" in selected


def test_front_page_modules_pull_their_guard_and_the_artifact_guards():
    for module in ("front", "tiles", "icons"):
        selected = select([f"scripts/{module}.py"])
        assert "tests/test_front_page.py" in selected, module
    assert "tests/test_front.py" in select(["scripts/front.py"])
    assert "tests/test_icons.py" in select(["scripts/icons.py"])


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
    assert select(["tests/test_front_page.py", "pyproject.toml"]) is None


# --- sub-packages (scripts/<pkg>/ ↔ tests/<pkg>/) ---------------------------
# A sub-package's modules share fixtures and data files (vocabularies, maps),
# so any change inside it runs that package's whole test directory — wider
# than one sibling, far narrower than the full suite.


def test_a_subpackage_module_selects_its_package_tests():
    assert select(["scripts/activity/hours.py"]) == ["tests/activity"]


def test_a_subpackage_data_file_selects_its_package_tests():
    assert select(["scripts/activity/vocabulary.json"]) == ["tests/activity"]


def test_a_subpackage_conftest_selects_only_its_package():
    assert select(["tests/activity/conftest.py"]) == ["tests/activity"]


def test_a_subpackage_test_selects_itself():
    assert select(["tests/activity/test_hours.py"]) == ["tests/activity/test_hours.py"]


def test_the_root_conftest_still_widens_to_everything():
    assert select(["tests/conftest.py"]) is None


def test_a_subpackage_without_tests_widens_to_everything():
    assert select(["scripts/missing/module.py"]) is None
