"""D1 -- a setting the user sees must reach the computation, or not exist.

CLAUDE.md, section 4: a visible parameter that does not reach the computation is worse than
an absent one, because it supplies a false explanation. Each class below guards one setting
that was shown, saved or logged while no computing line read it. None could be wired both
trivially and bit for bit, so each was REMOVED, and each class fails on the code before its
removal.
"""

from __future__ import annotations

import inspect

import pytest

pytest.importorskip("PyQt6")


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    """Join the window's threads, then destroy it (tests/qt_lifecycle.py, D11 and D23)."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT settings", main_windows_only=True)


@pytest.fixture
def strat_window(qapp):
    from certus.ui.certus_strat_ui import CertusSTRATApp

    return CertusSTRATApp()


class TestFastAutoBlocks:
    """`fast_auto_blocks` was set to True by `collect_params` and printed by the FAST mode
    banner, while nothing read it: the branch that consumed it had been deleted
    (`_compute_blocks_range_for_params`)."""

    def test_collect_params_no_longer_carries_it(self, strat_window):
        assert "fast_auto_blocks" not in strat_window.collect_params()

    def test_the_fast_mode_log_line_no_longer_announces_it(self):
        from certus.ui import certus_strat_ui_worker

        assert "fast_auto_blocks" not in inspect.getsource(certus_strat_ui_worker)
