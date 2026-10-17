"""The registry of the levers cannot lie about what the application routes either.

`tests/unit/test_strat_leviers.py` confronts every default of `certus/core/certus_strat_leviers.py` with the kernel (`params.get(key, default)`
in `certus_strat_robustness*.py`). But the application does not hand the kernel an absent key: `collect_params`
(`certus/ui/certus_strat_ui_state.py`) reads each setting from the loaded configuration with a default of its own, and puts it in `params`
whether the file carried it or not. A default that the kernel and the registry call True and the application reads as False is False in
every run launched from the application, and nothing fails: that was `rate_by_swing` (Rate placed where the optical signal is too poor to
stop on) from its arming on 2026-08-22 until this test.

👤 2026-10-12: Rate must be integrated in every scenario, and favoured on the layers that are hard to control optically.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from certus.core.certus_strat_leviers import LEVIERS

UI_STATE = Path(__file__).resolve().parents[2] / "certus" / "ui" / "certus_strat_ui_state.py"
READERS = {"_config_flag", "_config_flag_default", "_config_float"}


def _routed_defaults() -> dict[str, list[tuple[str, object]]]:
    """Every setting read from the configuration with a literal default: `{key: [(reader, default), ...]}`."""
    found: dict[str, list[tuple[str, object]]] = {}
    for node in ast.walk(ast.parse(UI_STATE.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") in READERS):
            continue
        if len(node.args) < 2 or not (isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
            continue
        reader = node.func.id
        if len(node.args) >= 3 and isinstance(node.args[2], ast.Constant):
            default = node.args[2].value
        else:
            default = 0.0 if reader == "_config_float" else False  # the defaults of the readers themselves
        found.setdefault(node.args[1].value, []).append((reader, default))
    return found


ROUTED = _routed_defaults()
SCALAR_LEVERS = [lv for lv in LEVIERS if lv.genre in ("bool", "int", "float") and not lv.constante and lv.cle in ROUTED]


def test_the_search_finds_what_the_application_routes() -> None:
    """A test that reads nothing proves nothing: `allow_rate` and `rate_by_swing` are routed, so they must be found."""
    assert "allow_rate" in ROUTED
    assert "rate_by_swing" in ROUTED
    assert {lv.cle for lv in SCALAR_LEVERS} >= {"allow_rate", "rate_by_swing"}


@pytest.mark.parametrize("lever", SCALAR_LEVERS, ids=lambda lv: lv.cle)
def test_the_default_the_application_reads_is_the_one_the_registry_announces(lever) -> None:
    for reader, default in ROUTED[lever.cle]:
        assert default == lever.defaut, (
            f"{lever.cle}: the registry announces {lever.defaut!r}, `{reader}` in collect_params reads {default!r} when the "
            f"file does not carry the key. Every run launched from the application takes the second."
        )


def test_a_flag_whose_absence_means_on_is_read_by_a_reader_that_says_so() -> None:
    """`_config_flag` returns False for an absent key unless it is given a default: an `on` flag read through it is a flag that is off."""
    for lever in SCALAR_LEVERS:
        if lever.genre == "bool" and lever.defaut is True:
            for reader, _ in ROUTED[lever.cle]:
                assert reader != "_config_flag", f"{lever.cle} is on by default and is read by `_config_flag`, which defaults to off"
