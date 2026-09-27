"""Oracle test enforcing the lint debt ratchet (Lot D1).

The extend-ignore list in pyproject.toml is a debt whitelist that MUST NOT EXPAND.
CLAUDE.md, among the eleven prohibitions: never add rules to extend-ignore. It can only shrink.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = ROOT / "pyproject.toml"

# The rules still ignored, by NAME: a bare count let one rule be swapped for another.
# When a rule leaves pyproject.toml, delete it here too, so that it cannot come back.
ALLOWED_EXTEND_IGNORE = frozenset({
    "B007", "B008", "B019", 
    "E402", "E701", "E702", "E741", "F401", "F403", "F405", 
    "F841", "I001", "PERF401", "PT006", "PT011",
    "PT017", "PT018", "RUF001", "RUF002", "RUF003", "RUF005", 
    "RUF012", "RUF015", "RUF022", "RUF023", "RUF046",
    "RUF059", "RUF100", "UP007", 
    "UP031", "UP037", "UP040", "UP042", "UP046",
})


def _extend_ignore() -> set[str]:
    with open(PYPROJECT_PATH, "rb") as f:
        data = tomllib.load(f)
    return set(data.get("tool", {}).get("ruff", {}).get("lint", {}).get("extend-ignore", []))


def test_lint_debt_ratchet_extend_ignore():
    """Action D1 — no rule may enter extend-ignore, not even in exchange for another."""
    assert PYPROJECT_PATH.exists(), f"Missing pyproject.toml at {PYPROJECT_PATH}"
    added = _extend_ignore() - ALLOWED_EXTEND_IGNORE
    assert not added, (
        f"Lint debt ratchet violated! New rule(s) in extend-ignore: {sorted(added)}. "
        f"CLAUDE.md prohibits expanding the extend-ignore whitelist!"
    )


def test_lint_debt_ratchet_tightens():
    """A rule that left extend-ignore must leave ALLOWED_EXTEND_IGNORE, or it could return unnoticed."""
    stale = ALLOWED_EXTEND_IGNORE - _extend_ignore()
    assert not stale, f"Rule(s) {sorted(stale)} are no longer ignored: remove them from ALLOWED_EXTEND_IGNORE."
