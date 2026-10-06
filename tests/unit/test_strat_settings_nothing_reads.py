"""D1, second batch -- six STRAT settings that nothing read are gone, and say so.

CLAUDE.md, section 4: a visible parameter that does not reach the computation is worse than an
absent one, because it supplies a false explanation. `docs/ETAT.md` (section 5bis) fixed the rule
for STRAT: an inert setting is removed, not wired. The first batch (`test_strat_disconnected_settings`)
removed five. Six more had a field, a tooltip and a place in `collect_params`, and no line of the
computation read them: `mse_tolerance_limit_pct`, `min_spectral_resolution`, `screening_mc_runs`,
`screening_keep_top_k`, `phase_a_keep_limit`, `step0_sigma`. The `extreme` mode even « set » two
of them (`phase_a_keep_limit` to 200, `screening_keep_top_k` to 20), a budget that no run felt.

As for the first batch: no field, no key in the parameters (whatever the mode), no key in a saved
file, and a file that still carries one keeps loading, with one line that says it is ignored.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
#: The reference configuration. It is only READ here: every variant is a copy in tmp_path.
EXAMPLE = ROOT / "example" / "example_strat" / "JSON-strat-example.json"
MODES = ("fast", "premium", "deep", "extreme")
RETIRED = (
    "mse_tolerance_limit_pct",
    "min_spectral_resolution",
    "screening_mc_runs",
    "screening_keep_top_k",
    "phase_a_keep_limit",
    "step0_sigma",
    # Third batch (D70, 2026-10-04): it only fed a thickness check that ran on zero matrices and refused nothing.
    "extrema_exclusion_ratio",
)


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT retired settings", main_windows_only=True)


@pytest.fixture
def window(qapp):
    from certus.ui.certus_strat_ui import CertusStratApp

    return CertusStratApp()


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@contextmanager
def _captured(logger: logging.Logger):
    """The lines `logger` emits inside the block (the STRAT logger does not propagate)."""
    handler = _Lines()
    logger.addHandler(handler)
    try:
        yield handler.lines
    finally:
        logger.removeHandler(handler)


def _load(window, tmp_path: Path, **extra) -> dict:
    cfg = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    cfg.update(extra)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    window.load_configuration(str(path))
    return cfg


@pytest.mark.parametrize("key", RETIRED)
def test_no_field_shows_it(window, key) -> None:
    assert key not in window.widgets


@pytest.mark.parametrize("mode", MODES)
def test_no_mode_puts_any_of_them_in_the_parameters(window, mode) -> None:
    window.widgets["execution_mode"].setCurrentText(mode)

    params = window.collect_params()

    assert params["execution_mode"] == mode, "premise: the mode under test is the one run"
    assert [key for key in RETIRED if key in params] == []


@pytest.mark.parametrize("key", RETIRED)
def test_a_file_that_sets_it_still_loads_and_says_it_is_ignored(window, tmp_path, key) -> None:
    with _captured(window.logger) as lines:
        _load(window, tmp_path, **{key: 7})

    assert window._loaded_config.get(key) == 7
    told = [line for line in lines if "no longer a setting" in line]
    assert len(told) == 1, lines
    assert key in told[0], lines
    assert key not in window.collect_params()


def test_saving_no_longer_writes_any_of_them(window, tmp_path, monkeypatch) -> None:
    from PyQt6.QtWidgets import QFileDialog

    target = tmp_path / "saved.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))

    window.save_configuration()

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert "robustness_num_runs" in saved, "premise: the file was written by the window"
    assert [key for key in RETIRED if key in saved] == []
