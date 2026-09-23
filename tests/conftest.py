"""Generate once per session instead of once per assertion.

Most guards here read the real generated artifacts, so each one used to open
with its own ``gen.main()``. Generation renders 36 SVGs, two READMEs and eight
pages, and outlines display glyphs to vector paths — about two seconds a call.
Twenty-odd calls put the suite at forty seconds, which is too slow to sit
inside a red-green-refactor loop.

Generation is idempotent and writes to fixed paths, so one run serves every
test that only reads its output. Tests that genuinely need a second run (the
determinism guard, the reference-date guard) still call ``gen.main()``
themselves — that is the behavior under test, not setup.
"""

from __future__ import annotations

import pytest

import scripts.generate as gen


@pytest.fixture(scope="session", autouse=True)
def generated() -> None:
    """Render the profile once, before any test reads its output."""
    gen.main()
