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
    "B007", "B008", "B009", "B010", "B011", "B017", "B019", "B023", "B033", "B904", "B905",
    "E401", "E402", "E701", "E702", "E713", "E731", "E741", "F401", "F403", "F405", "F541",
    "F811", "F841", "I001", "PERF102", "PERF401", "PERF403", "PT006", "PT007", "PT011",
    "PT015", "PT017", "PT018", "PT019", "RUF001", "RUF002", "RUF003", "RUF005", "RUF010",
    "RUF012", "RUF013", "RUF015", "RUF019", "RUF022", "RUF023", "RUF043", "RUF046",
    "RUF059", "RUF100", "UP006", "UP007", "UP008", "UP009", "UP015", "UP018", "UP024",
    "UP031", "UP034", "UP035", "UP036", "UP037", "UP040", "UP042", "UP045", "UP046",
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
