"""D105 -- a measurement script never computes on a configuration it did not load.

`CertusStratApp.load_configuration` returns False when the file is missing or refused, and leaves the window on its default
configuration (46 layers). The 23 calls of `scripts/` did not read that return. On 2026-10-12 a replay of
`probe_blocs_vs_plantage.py r75x0.5`, in a clone without `reports/serie_echelle_r75/cfg_x0.5.json`, computed for four hours on
the default stack with verdict OK and 2 743 strategies. `scripts/_composant.charger_configuration` stops the script instead, and
no call of `load_configuration` may be a bare statement in `scripts/` or `tools/`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from _composant import charger_configuration  # noqa: E402


class _Window:
    """A stand-in for the STRAT window: `load_configuration` rejects or accepts, and remembers what it was given."""

    def __init__(self, accepts: bool) -> None:
        self.accepts = accepts
        self.given: list[str] = []

    def load_configuration(self, filename: str) -> bool:
        self.given.append(filename)
        return self.accepts


def test_a_loaded_file_goes_to_the_window_as_text(tmp_path: Path) -> None:
    config = tmp_path / "cfg.json"
    config.write_text("{}", encoding="utf-8")
    window = _Window(accepts=True)

    charger_configuration(window, config)

    assert window.given == [str(config)]


def test_a_missing_file_stops_the_script_and_never_reaches_the_window(tmp_path: Path) -> None:
    window = _Window(accepts=True)

    with pytest.raises(SystemExit) as stop:
        charger_configuration(window, tmp_path / "absent.json")

    assert "introuvable" in str(stop.value)
    assert window.given == []


def test_a_file_the_window_refuses_stops_the_script(tmp_path: Path) -> None:
    config = tmp_path / "cfg.json"
    config.write_text("{}", encoding="utf-8")
    window = _Window(accepts=False)

    with pytest.raises(SystemExit) as stop:
        charger_configuration(window, config)

    assert "refuse" in str(stop.value)
    assert window.given == [str(config)]


def _bare_calls(path: Path) -> list[int]:
    """The lines where `<x>.load_configuration(...)` is a statement of its own: its return value is thrown away."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "load_configuration"
    ]


def test_no_script_throws_away_what_load_configuration_returns() -> None:
    found = {
        str(path.relative_to(ROOT)): lines
        for folder in ("scripts", "tools")
        for path in sorted((ROOT / folder).glob("*.py"))
        if (lines := _bare_calls(path))
    }

    assert not found, f"load_configuration called as a bare statement (use _composant.charger_configuration): {found}"


def test_the_search_for_bare_calls_sees_one(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text("app.load_configuration('x.json')\nok = app.load_configuration('y.json')\n", encoding="utf-8")

    assert _bare_calls(sample) == [1]
