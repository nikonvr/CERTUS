"""INDEX shows the absorbing-substrate controls for silicon only (D43, decided 2026-09-28).

The fit reads the substrate absorption for silicon alone: for every other substrate the worker
forces k = 0 (`_resolve_substrate_absorption_inputs`). Yet the "absorbing substrate" checkbox,
the k file import and the thickness stayed visible and active for all of them -- visible
settings that never reached the computation. 👤 chose to hide them outside silicon.
"""

from __future__ import annotations

import pytest

from certus.core.certus_core import SUBSTRATE_LIST

SILICON = "Silicon (Si)"
OTHERS = [name for name in SUBSTRATE_LIST if name != SILICON]


@pytest.fixture(autouse=True)
def _windows_end_with_the_test(qapp, monkeypatch):
    """The windows a test builds are destroyed when it ends (D11): closing only hides them."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "INDEX absorbing substrate", main_windows_only=True)


@pytest.fixture
def window(qapp):
    from certus.ui.certus_index_ui import CertusIndexApp

    return CertusIndexApp()


def _hidden(window) -> bool:
    return window.chk_absorbing_sub.isHidden() and window._absorbing_sub_widget.isHidden()


def test_the_controls_are_hidden_at_start(window) -> None:
    assert SUBSTRATE_LIST[window.cb_sub.currentIndex()] != SILICON
    assert _hidden(window)


def test_silicon_shows_them_locked_on(window) -> None:
    window.cb_sub.setCurrentIndex(SUBSTRATE_LIST.index(SILICON))

    assert not window.chk_absorbing_sub.isHidden()
    assert not window._absorbing_sub_widget.isHidden()
    assert window.chk_absorbing_sub.isChecked()
    assert not window.chk_absorbing_sub.isEnabled()


@pytest.mark.parametrize("substrate", OTHERS)
def test_every_other_substrate_hides_them(window, substrate) -> None:
    window.cb_sub.setCurrentIndex(SUBSTRATE_LIST.index(SILICON))
    window.cb_sub.setCurrentIndex(SUBSTRATE_LIST.index(substrate))

    assert _hidden(window)
    assert not window.chk_absorbing_sub.isChecked()
