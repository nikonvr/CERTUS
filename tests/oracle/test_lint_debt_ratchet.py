"""Oracle test enforcing the lint debt ratchet (Lot D1).

The extend-ignore list in pyproject.toml is a debt whitelist that MUST NOT EXPAND.
Rule #2 of AGENTS.md: Never add rules to extend-ignore. It can only shrink.
"""

from pathlib import Path
import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = ROOT / "pyproject.toml"
MAX_ALLOWED_EXTEND_IGNORE = 68


def test_lint_debt_ratchet_extend_ignore():
    """Action D1 — Assert pyproject.toml extend-ignore list length does not expand beyond 68."""
    assert PYPROJECT_PATH.exists(), f"Missing pyproject.toml at {PYPROJECT_PATH}"
    with open(PYPROJECT_PATH, "rb") as f:
        data = tomllib.load(f)

    extend_ignore = data.get("tool", {}).get("ruff", {}).get("lint", {}).get("extend-ignore", [])
    current_count = len(extend_ignore)

    assert current_count <= MAX_ALLOWED_EXTEND_IGNORE, (
        f"Lint debt ratchet violated! extend-ignore count ({current_count}) "
        f"exceeds maximum allowed threshold ({MAX_ALLOWED_EXTEND_IGNORE}). "
        f"Rule #2 in AGENTS.md prohibits expanding the extend-ignore whitelist!"
    )
