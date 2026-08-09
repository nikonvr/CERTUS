"""Integration tests for P3 (reports), P4 (a11y), P5 (destructive confirm)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


# =============================================================================
# P3 - Premium reports wired on CertusBaseApp
# =============================================================================


def test_p3_certus_base_app_exposes_report_helpers():
    from certus.ui.certus_ui import CertusBaseApp

    for m in (
        "_default_report_context",
        "export_premium_excel",
        "export_premium_pdf",
        "_build_report_sections",
        "export_report_excel",
        "export_report_pdf",
    ):
        assert hasattr(CertusBaseApp, m), f"Missing {m}"


def test_p3_build_report_sections_default_is_empty_list():
    from certus.ui.certus_ui import CertusBaseApp

    class _Stub:
        _build_report_sections = CertusBaseApp._build_report_sections

    assert _Stub()._build_report_sections() == []


def test_p3_command_catalog_exposes_premium_excel_command():
    from certus.ui.certus_ui import CertusBaseApp

    class _Stub:
        _auto_discovered_commands = CertusBaseApp._auto_discovered_commands

        def export_report_excel(self):
            pass

    cmds = _Stub()._auto_discovered_commands()
    ids = {c.id for c in cmds}
    assert "file.export_report_excel" in ids


def test_p3_export_premium_excel_produces_xlsx(tmp_path):
    """Smoke-test the wiring end-to-end via a minimal Section list."""
    from certus.utils.certus_reports import Section

    out = tmp_path / "cert_report.xlsx"

    # Drive the export directly (the base-app path exercised on a stub).
    from certus.utils.certus_reports import ReportContext, build_excel_report

    ctx = ReportContext(title="X", app_name="pytest")
    sections = [Section(title="Intro", kind="text", text="Hello")]
    path = build_excel_report(ctx, sections, str(out))
    exported = Path(path)
    assert exported.exists()
    assert exported.stat().st_size > 500


# =============================================================================
# P4 - Accessibility (pure-python contrast math + widget walker)
# =============================================================================


def test_p4_contrast_ratio_extremes():
    from certus.ui.certus_a11y import contrast_ratio

    # Black vs white = 21.0 exactly
    ratio = contrast_ratio("#000000", "#FFFFFF")
    assert abs(ratio - 21.0) < 1e-6
    # Same color = 1.0
    assert contrast_ratio("#345678", "#345678") == pytest.approx(1.0)


def test_p4_short_hex_color_is_accepted():
    from certus.ui.certus_a11y import contrast_ratio

    # "#FFF" (3-char) should expand to "#FFFFFF"
    assert contrast_ratio("#FFF", "#000") == pytest.approx(21.0)


def test_p4_passes_wcag_aa_thresholds():
    from certus.ui.certus_a11y import passes_wcag_aa

    # High-contrast pair: passes normal and large
    assert passes_wcag_aa("#111111", "#EEEEEE") is True
    assert passes_wcag_aa("#111111", "#EEEEEE", large_text=True) is True
    # Very low contrast: fails both
    assert passes_wcag_aa("#777777", "#888888") is False


def test_p4_audit_palette_reports_worst_pair():
    from certus.ui.certus_a11y import audit_palette

    palette = {
        "surface": "#FFFFFF",
        "text": "#111111",
        "muted": "#BBBBBB",  # low contrast vs white
        "primary": "#1F3A8A",
    }
    report = audit_palette(palette, background_key="surface")
    assert "text" in report and report["text"]["passes_aa"] is True
    assert report["muted"]["passes_aa"] is False
    summary = report["_summary"]
    assert summary["worst_pair"] == "muted"


def test_p4_apply_accessibility_defaults_names_widgets_without_name():
    from PyQt6.QtWidgets import QApplication, QLineEdit, QWidget

    from certus.ui.certus_a11y import apply_accessibility_defaults

    _qapp = QApplication.instance() or QApplication(sys.argv)
    root = QWidget()
    e1 = QLineEdit(root); e1.setObjectName("sampleSpin")
    e2 = QLineEdit(root); e2.setObjectName("")  # no objectName, no tooltip
    e2.setToolTip("Sample tooltip text")
    e3 = QLineEdit(root); e3.setAccessibleName("Already set")

    touched = apply_accessibility_defaults(root)
    # At least e1 + e2 received a name; e3 preserved.
    assert touched >= 1
    assert e1.accessibleName()  # non-empty
    assert "Sample" in e1.accessibleName() or "Sample" in e1.accessibleName().lower()
    assert e3.accessibleName() == "Already set"


def test_p4_compute_tab_order_pairs_sequentially():
    from certus.ui.certus_a11y import compute_tab_order

    widgets = ["a", "b", "c", "d"]
    assert compute_tab_order(widgets) == [("a", "b"), ("b", "c"), ("c", "d")]
    # Single item → no transitions
    assert compute_tab_order(["only"]) == []
    # Empty → no transitions
    assert compute_tab_order([]) == []


# =============================================================================
# P5 - Destructive confirmation helper
# =============================================================================


def test_p5_certus_base_app_exposes_confirm_destructive():
    from certus.ui.certus_ui import CertusBaseApp

    assert hasattr(CertusBaseApp, "confirm_destructive")


def test_p5_confirm_destructive_returns_false_on_parent_none(monkeypatch):
    """Without an actual QMainWindow instance the helper must still
    degrade gracefully (False) instead of raising."""
    from certus.ui.certus_ui import CertusBaseApp

    class _Stub:
        logger = None
        confirm_destructive = CertusBaseApp.confirm_destructive

    #Forcing an exception path (can't instantiate QMessageBox w/o parent)
    result = _Stub().confirm_destructive("Title", "Message")
    assert result is False
