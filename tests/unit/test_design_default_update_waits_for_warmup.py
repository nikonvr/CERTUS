"""Default DESIGN updates must not call parallel Numba during JIT warmup."""

from types import SimpleNamespace

from certus.ui.certus_design_ui_core import CoreManager


def test_tikhonravov_update_waits_for_warmup(monkeypatch) -> None:
    ui = SimpleNamespace(_warmup_done=False)
    manager = CoreManager(ui)
    calls = []
    monkeypatch.setattr(manager, "_calculate_tikhonravov_points", lambda: calls.append("calculate") or 50)

    manager._update_tikhonravov_points()

    assert calls == []
