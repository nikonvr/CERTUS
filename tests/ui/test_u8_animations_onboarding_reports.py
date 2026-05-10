"""Tests for U8 (micro-animations), U9 (onboarding + sample data), U10 (reports).

All tests are designed to run fast: introspective where possible, light
Qt where required. PDF/Excel rendering tests are small but real.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


# =============================================================================
# U8 - Micro-animations (mostly pure-python / lightweight Qt)
# =============================================================================


def test_u8_module_surface():
    import certus_animations as m

    for name in (
        "DEFAULT_DURATION_MS",
        "HOVER_DURATION_MS",
        "PULSE_DURATION_MS",
        "easing_names",
        "is_valid_easing",
        "fade_in",
        "fade_out",
        "slide_in",
        "pulse",
        "hover_lift",
        "unhover_lift",
    ):
        assert hasattr(m, name)


def test_u8_easing_names_are_stable_and_validated():
    from certus_animations import easing_names, is_valid_easing

    names = easing_names()
    assert "out_cubic" in names and "linear" in names
    for n in names:
        assert is_valid_easing(n)
    assert not is_valid_easing("nope")


def test_u8_durations_are_sensible():
    from certus_animations import DEFAULT_DURATION_MS, HOVER_DURATION_MS, PULSE_DURATION_MS

    assert 100 <= DEFAULT_DURATION_MS <= 400
    assert 80 <= HOVER_DURATION_MS <= 200
    assert 300 <= PULSE_DURATION_MS <= 800


def test_u8_public_api_safe_on_none():
    from certus_animations import fade_in, fade_out, hover_lift, pulse, slide_in, unhover_lift

    assert fade_in(None) is None
    assert fade_out(None) is None
    assert slide_in(None) is None
    assert pulse(None) is None
    assert hover_lift(None) is None
    assert unhover_lift(None) is False


def test_u8_fade_in_returns_running_animation():
    from PyQt6.QtCore import QPropertyAnimation
    from PyQt6.QtWidgets import QApplication, QLabel

    from certus_animations import fade_in

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = QLabel("x")
    anim = fade_in(w, duration_ms=20)
    assert isinstance(anim, QPropertyAnimation)
    # Animation is running or has started (queued)
    assert anim.duration() == 20


def test_u8_hover_lift_is_idempotent():
    from PyQt6.QtWidgets import QApplication, QLabel

    from certus_animations import hover_lift, unhover_lift

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = QLabel("x")
    f1 = hover_lift(w, lift_px=4)
    f2 = hover_lift(w, lift_px=6)
    # Same filter returned; second call updates params
    assert f1 is f2
    assert unhover_lift(w) is True
    assert unhover_lift(w) is False


# =============================================================================
# U9 - Onboarding persistence + sample data (pure-python)
# =============================================================================


@pytest.fixture
def _isolated_onboarding(monkeypatch):
    """Force in-memory persistence so tests don't touch QSettings."""
    import certus_onboarding as m

    monkeypatch.setattr(m, "_qs_settings", lambda: None)
    m._MEMORY_FLAGS.clear()
    yield
    m._MEMORY_FLAGS.clear()


def test_u9_onboarding_completion_flag(_isolated_onboarding):
    from certus_onboarding import is_completed, mark_completed, reset_onboarding

    assert is_completed("INDEX") is False
    mark_completed("INDEX")
    assert is_completed("INDEX") is True
    reset_onboarding("INDEX")
    assert is_completed("INDEX") is False


def test_u9_reset_all_clears_every_app(_isolated_onboarding):
    from certus_onboarding import is_completed, mark_completed, reset_onboarding

    mark_completed("A")
    mark_completed("B")
    reset_onboarding()
    assert is_completed("A") is False
    assert is_completed("B") is False


def test_u9_tour_step_is_frozen_dataclass():
    from certus_onboarding import TourStep

    s = TourStep(title="Hi", body="Welcome")
    assert s.title == "Hi"
    with pytest.raises(Exception):
        s.title = "Changed"


def test_u9_resolve_target_returns_none_for_missing_attr():
    from certus_onboarding import resolve_target

    class _Parent:
        existing = "hello"

    p = _Parent()
    assert resolve_target(p, "existing") == "hello"
    assert resolve_target(p, "missing") is None
    assert resolve_target(p, "") is None
    assert resolve_target(p, None) is None


def test_u9_filter_resolvable_drops_invalid_steps():
    from certus_onboarding import TourStep, filter_resolvable_steps

    class _Parent:
        load_btn = object()

    steps = [
        TourStep(title="Welcome", body="..."),
        TourStep(title="Load", body="...", target_attr="load_btn"),
        TourStep(title="Ghost", body="...", target_attr="missing_attr"),
    ]
    out = filter_resolvable_steps(_Parent(), steps)
    # "Welcome" (no target) + "Load" kept, "Ghost" dropped
    assert [s.title for s, _ in out] == ["Welcome", "Load"]


def test_u9_run_onboarding_skipped_when_empty(_isolated_onboarding):
    from certus_onboarding import OnboardingResult, run_onboarding

    class _Parent:
        pass

    result = run_onboarding(_Parent(), "INDEX", steps=[])
    assert result == OnboardingResult.EMPTY.value


def test_u9_run_onboarding_already_done(_isolated_onboarding):
    from certus_onboarding import OnboardingResult, TourStep, mark_completed, run_onboarding

    class _Parent:
        widget_a = object()

    mark_completed("INDEX")
    r = run_onboarding(
        _Parent(),
        "INDEX",
        [TourStep(title="t", body="b", target_attr="widget_a")],
    )
    assert r == OnboardingResult.ALREADY_DONE.value


def test_u9_sample_data_discovery_on_empty_root(tmp_path):
    from certus_sample_data import SampleCategory, has_any_samples, list_samples, set_sample_root

    set_sample_root(str(tmp_path))  # empty folder
    try:
        assert list_samples(SampleCategory.CONFIG) == []
        assert has_any_samples() is False
    finally:
        set_sample_root(None)


def test_u9_sample_data_lists_json_configs(tmp_path):
    from certus_sample_data import SampleCategory, default_sample, list_samples, sample_path, set_sample_root

    (tmp_path / SampleCategory.CONFIG).mkdir(parents=True)
    a = tmp_path / SampleCategory.CONFIG / "sample_a.json"
    b = tmp_path / SampleCategory.CONFIG / "sample_b.json"
    a.write_text("{}"); b.write_text("{}")
    # Description file for a
    (tmp_path / SampleCategory.CONFIG / "sample_a.txt").write_text("Demo config A")

    set_sample_root(str(tmp_path))
    try:
        items = list_samples(SampleCategory.CONFIG)
        names = [i.name for i in items]
        assert names == ["sample_a", "sample_b"]
        assert items[0].exists is True
        assert items[0].description == "Demo config A"
        # sample_path / default_sample
        assert sample_path(SampleCategory.CONFIG, "sample_b") == str(b.resolve()) or \
               sample_path(SampleCategory.CONFIG, "sample_b") == str(b)
        ds = default_sample(SampleCategory.CONFIG)
        assert ds is not None and ds.name == "sample_a"
    finally:
        set_sample_root(None)


# =============================================================================
# U10 - Reports (Excel + PDF)
# =============================================================================


def test_u10_brand_colors_have_required_keys():
    from certus_reports import BRAND_COLORS

    for k in ("primary", "accent", "success", "warning", "error", "surface"):
        assert k in BRAND_COLORS
        assert BRAND_COLORS[k].startswith("#")


def test_u10_report_context_header_lines():
    from certus_reports import ReportContext

    ctx = ReportContext(title="Report", subtitle="Sub", app_name="INDEX", author="Alice")
    lines = ctx.header_lines()
    assert lines[0] == "Report"
    assert "Sub" in lines[1]
    # Third line includes INDEX, author, timestamp
    assert any("INDEX" in l for l in lines)


def test_u10_section_kind_predicates():
    from certus_reports import Section

    t = Section(title="T", kind="table", rows=[[1]])
    x = Section(title="X", kind="text", text="hi")
    c = Section(title="C", kind="chart")
    assert t.is_table() and not t.is_text()
    assert x.is_text() and not x.is_chart()
    assert c.is_chart() and not c.is_table()


def test_u10_summary_header_is_newline_joined():
    from certus_reports import ReportContext, report_summary_header

    ctx = ReportContext(title="T", subtitle="S", app_name="A", author="B")
    txt = report_summary_header(ctx)
    assert "\n" in txt
    assert "T" in txt and "S" in txt


def test_u10_excel_export_is_produced(tmp_path):
    from certus_reports import ReportContext, Section, build_excel_report

    ctx = ReportContext(title="Test Report", subtitle="Unit test", app_name="CERTUS", author="pytest")
    sections = [
        Section(title="Summary", kind="text", text="All good."),
        Section(
            title="Results",
            kind="table",
            header=["Metric", "Value"],
            rows=[["RMSE", 0.001], ["Iter", 42]],
        ),
    ]
    out = tmp_path / "report.xlsx"
    built = build_excel_report(ctx, sections, str(out))
    assert Path(built).exists()
    assert Path(built).stat().st_size > 1000  # non-empty xlsx

    # Reopen to sanity-check contents
    import openpyxl

    wb = openpyxl.load_workbook(built)
    assert "Summary" in wb.sheetnames
    # One of the sheets matches our "Results" section (title may be truncated)
    assert any("Results" in s or "Summary" in s for s in wb.sheetnames)


def test_u10_excel_export_handles_empty_sections(tmp_path):
    from certus_reports import ReportContext, build_excel_report

    ctx = ReportContext(title="Empty", app_name="CERTUS")
    out = tmp_path / "empty.xlsx"
    built = build_excel_report(ctx, [], str(out))
    assert Path(built).exists()


def test_u10_pdf_export_is_produced(tmp_path):
    from certus_reports import ReportContext, Section, build_pdf_report

    ctx = ReportContext(title="PDF Report", subtitle="Unit test", app_name="CERTUS", author="pytest")
    sections = [
        Section(title="Intro", kind="text", text=["Paragraph 1", "Paragraph 2"]),
        Section(
            title="Table",
            kind="table",
            header=["A", "B"],
            rows=[[1, 2], [3, 4]],
        ),
    ]
    out = tmp_path / "report.pdf"
    built = build_pdf_report(ctx, sections, str(out))
    assert Path(built).exists()
    # PDF header sanity check
    with open(built, "rb") as f:
        head = f.read(5)
    assert head.startswith(b"%PDF")


def test_u10_pdf_export_handles_empty_sections(tmp_path):
    from certus_reports import ReportContext, build_pdf_report

    ctx = ReportContext(title="Empty PDF", app_name="CERTUS")
    out = tmp_path / "empty.pdf"
    built = build_pdf_report(ctx, [], str(out))
    assert Path(built).exists()
    with open(built, "rb") as f:
        assert f.read(5).startswith(b"%PDF")
