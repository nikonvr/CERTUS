"""Tests for the CERTUS recent-files strip (U5+).

Mostly introspection + basic Qt lifecycle, kept lightweight so the suite
runs fast.
"""

from __future__ import annotations

import inspect
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


# =============================================================================
# Module surface
# =============================================================================


def test_u5plus_module_exposes_public_api():
    import certus.ui.certus_recent_strip as m

    for name in ("STRIP_MAX_ITEMS", "PILL_MAX_CHARS", "build_recent_files_strip"):
        assert hasattr(m, name)


def test_u5plus_build_factory_is_callable_without_parent():
    from certus.ui.certus_recent_strip import build_recent_files_strip

    # Should not raise even if no app exists yet (factory should resolve Qt lazily)
    from PyQt6.QtWidgets import QApplication
    _qapp = QApplication.instance() or QApplication(sys.argv)

    strip = build_recent_files_strip(None)
    assert strip is not None


# =============================================================================
# HUB integration
# =============================================================================


def test_u5plus_hub_has_attach_recent_files_strip_method():
    from CERTUS_HUB import CertusHub

    assert hasattr(CertusHub, "attach_recent_files_strip")
    assert hasattr(CertusHub, "_on_recent_config_selected")


def test_u5plus_hub_attach_signature_has_optional_parent_layout():
    from CERTUS_HUB import CertusHub

    sig = inspect.signature(CertusHub.attach_recent_files_strip)
    params = sig.parameters
    assert "parent_layout" in params
    # keyword-only "limit" with default
    assert "limit" in params
    assert params["limit"].default == 5


# =============================================================================
# Qt widget behaviour
# =============================================================================


@pytest.fixture(autouse=True)
def _isolated_recent_store(monkeypatch, tmp_path):
    """Use the in-memory fallback so QSettings isn't polluted across tests."""
    import certus.ui.certus_recent as m

    monkeypatch.setattr(m, "_qs_settings", lambda: None)
    m._MEMORY_STORE.clear()
    yield
    m._MEMORY_STORE.clear()


def test_u5plus_strip_renders_empty_state_when_no_recents():
    from PyQt6.QtWidgets import QApplication, QLabel
    from certus.ui.certus_recent_strip import build_recent_files_strip

    _qapp = QApplication.instance() or QApplication(sys.argv)
    strip = build_recent_files_strip(None, limit=3)
    # The empty sentinel label "(none yet)" must exist
    labels = strip.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert any("(none" in t for t in texts)


def test_u5plus_strip_lists_pills_after_recording(tmp_path):
    from PyQt6.QtWidgets import QApplication, QPushButton

    from certus.ui.certus_recent import RecentCategories, record_recent
    from certus.ui.certus_recent_strip import build_recent_files_strip

    _qapp = QApplication.instance() or QApplication(sys.argv)

    a = tmp_path / "alpha.json"; a.write_text("{}")
    b = tmp_path / "beta.json"; b.write_text("{}")
    record_recent(RecentCategories.CONFIG, str(a))
    record_recent(RecentCategories.CONFIG, str(b))

    strip = build_recent_files_strip(None, limit=5)
    pills = strip.findChildren(QPushButton)
    pill_tooltips = {p.toolTip() for p in pills}
    # Both recorded files are present in tooltips (absolute paths)
    assert any("alpha.json" in t for t in pill_tooltips)
    assert any("beta.json" in t for t in pill_tooltips)


def test_u5plus_strip_emits_signal_and_invokes_callback(tmp_path):
    from PyQt6.QtWidgets import QApplication, QPushButton

    from certus.ui.certus_recent import RecentCategories, record_recent
    from certus.ui.certus_recent_strip import build_recent_files_strip

    _qapp = QApplication.instance() or QApplication(sys.argv)

    target = tmp_path / "cfg.json"; target.write_text("{}")
    record_recent(RecentCategories.CONFIG, str(target))

    received: list[str] = []
    strip = build_recent_files_strip(None, on_open=received.append)

    signal_received: list[str] = []
    strip.path_selected.connect(signal_received.append)

    pills = strip.findChildren(QPushButton)
    assert pills
    pills[0].click()
    assert received and "cfg.json" in received[0]
    assert signal_received and "cfg.json" in signal_received[0]


def test_u5plus_strip_refresh_reflects_latest_state(tmp_path):
    from PyQt6.QtWidgets import QApplication, QPushButton

    from certus.ui.certus_recent import RecentCategories, record_recent
    from certus.ui.certus_recent_strip import build_recent_files_strip

    _qapp = QApplication.instance() or QApplication(sys.argv)

    strip = build_recent_files_strip(None)
    assert len(strip.findChildren(QPushButton)) == 0  # nothing yet

    f = tmp_path / "late.json"; f.write_text("{}")
    record_recent(RecentCategories.CONFIG, str(f))
    strip.refresh()
    pills = strip.findChildren(QPushButton)
    assert len(pills) == 1
    assert "late.json" in pills[0].toolTip()
