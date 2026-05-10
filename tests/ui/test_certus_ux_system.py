"""Tests for the CERTUS UX foundation (U1 tokens, U2 icons, U3 palette)."""

from __future__ import annotations

import os
import sys
import types

# Ensure any Qt-using test runs headless
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

# =============================================================================
# U1 - Design tokens + premium QSS
# =============================================================================


def test_u1_tokens_exported():
    from certus_ux import Elevation, Motion, OBJ, Radius, Spacing, Typography, ZIndex

    # 8-pt spacing scale is monotonic and matches the declared ratios
    values = [Spacing.XS, Spacing.SM, Spacing.MD, Spacing.LG, Spacing.XL, Spacing.XXL, Spacing.XXXL]
    assert values == sorted(values)
    assert Spacing.XS == 4 and Spacing.SM == 8

    # Radius scale consistent
    assert Radius.SM < Radius.MD < Radius.LG < Radius.XL < Radius.PILL

    # Motion durations consistent
    assert Motion.INSTANT < Motion.FAST < Motion.BASE < Motion.SLOW < Motion.EMPHASIS

    # Typography scale monotonic
    sizes = [Typography.CAPTION, Typography.BODY_SM, Typography.BODY,
             Typography.BODY_LG, Typography.H3, Typography.H2, Typography.H1,
             Typography.DISPLAY]
    assert sizes == sorted(sizes)

    # Elevation tokens are 3-tuples of ints
    for tok in (Elevation.SM, Elevation.MD, Elevation.LG, Elevation.XL):
        assert len(tok) == 3 and all(isinstance(x, int) for x in tok)

    # Object-name contract is non-empty
    assert OBJ.CARD and OBJ.PRIMARY_BUTTON and OBJ.SEARCH_INPUT

    # ZIndex monotonic
    assert ZIndex.BASE < ZIndex.DROPDOWN < ZIndex.MODAL < ZIndex.TOOLTIP


def test_u1_premium_overrides_shape():
    from certus_ux import build_premium_overrides, OBJ

    css = build_premium_overrides()
    # Well-formed QSS substrings
    assert "QLineEdit:focus" in css
    assert "QScrollBar:vertical" in css
    assert "QHeaderView::section" in css
    assert OBJ.CARD in css
    assert OBJ.PRIMARY_BUTTON in css
    assert OBJ.SEARCH_INPUT in css
    # No Python format placeholders leaked
    assert "{color}" not in css
    assert "{{ " not in css or "{{" not in css  # no raw braces left


def test_u1_apply_certus_theme_accepts_premium_flag():
    from PyQt6.QtWidgets import QApplication, QWidget

    QApplication.instance() or QApplication([])
    w = QWidget()
    from certus_ui import apply_certus_theme

    # premium=True appends U1 overrides (CertusSearch object-name is unique to U1)
    apply_certus_theme(w, premium=True)
    assert "CertusSearch" in w.styleSheet()
    # premium=False reverts to legacy-only stylesheet (no U1 object-names)
    apply_certus_theme(w, premium=False)
    assert "CertusSearch" not in w.styleSheet()
    assert "CertusCard" not in w.styleSheet()


# =============================================================================
# U2 - Icons
# =============================================================================


def test_u2_icon_names_available():
    from certus_icons import ICON_SVG_SOURCES, available_icon_names

    names = available_icon_names()
    # A stable subset we guarantee exists
    for required in ("save", "folder-open", "search", "play", "stop",
                     "check", "x", "command", "moon", "sun"):
        assert required in names, f"Missing core icon: {required}"
    assert len(names) >= 25
    # Templates contain the {color} placeholder
    for name, svg in ICON_SVG_SOURCES.items():
        assert "{color}" in svg, f"{name!r} SVG missing {{color}}"
        assert svg.endswith("</svg>")


def test_u2_certus_icon_renders_non_empty():
    from PyQt6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from certus_icons import certus_icon, is_svg_icon_rendering_disabled

    ic = certus_icon("save")
    if is_svg_icon_rendering_disabled():
        assert ic.isNull()
        return
    assert not ic.isNull()
    sizes = ic.availableSizes()
    assert sizes and sizes[0].width() == 20 and sizes[0].height() == 20


def test_u2_unknown_icon_never_raises():
    from PyQt6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from certus_icons import certus_icon

    ic = certus_icon("__definitely_not_a_real_icon__")
    assert ic.isNull()  # empty QIcon, not a crash


def test_u2_custom_color_changes_output():
    from PyQt6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from certus_icons import certus_icon, clear_icon_cache, is_svg_icon_rendering_disabled

    if is_svg_icon_rendering_disabled():
        return
    clear_icon_cache()
    red = certus_icon("save", color="#ff0000", size=24)
    blue = certus_icon("save", color="#0000ff", size=24)
    r_pm = red.pixmap(24, 24).toImage()
    b_pm = blue.pixmap(24, 24).toImage()
    # At least one pixel must differ between the two colors.
    differ = False
    for x in range(0, 24, 3):
        for y in range(0, 24, 3):
            if r_pm.pixel(x, y) != b_pm.pixel(x, y):
                differ = True
                break
        if differ:
            break
    assert differ, "Icon did not recolor with custom color"


# =============================================================================
# U3 - Command palette (fuzzy + CommandAction, no Qt needed)
# =============================================================================


def test_u3_fuzzy_score_bounds_and_ordering():
    from certus_command_palette import fuzzy_score

    # Empty query returns neutral-positive
    assert 0 < fuzzy_score("", "anything") <= 1.0
    # Empty haystack with non-empty query
    assert fuzzy_score("x", "") == 0.0
    # Exact substring beats subsequence
    assert fuzzy_score("save", "save configuration") > fuzzy_score("save", "snap and verify")
    # Non-matchable subsequence
    assert fuzzy_score("zzz", "save configuration") == 0.0
    # All scores in [0, 1]
    for q, h in [("a", "banana"), ("sa", "save"), ("q", "query me")]:
        s = fuzzy_score(q, h)
        assert 0.0 <= s <= 1.0


def test_u3_rank_commands_respects_match_only():
    from certus_command_palette import CommandAction, rank_commands

    def noop():
        pass
    actions = [
        CommandAction(id="a", title="Save configuration", callback=noop),
        CommandAction(id="b", title="Load configuration", callback=noop),
        CommandAction(id="c", title="Toggle theme", callback=noop),
    ]
    ranked = rank_commands("save", actions)
    # Save must rank first; actions that don't match at all are dropped
    assert ranked
    assert ranked[0][1].id == "a"
    ids_in_result = {a.id for _s, a in ranked}
    assert "c" not in ids_in_result  # "toggle theme" doesn't contain "save"


def test_u3_rank_commands_empty_query_preserves_order():
    from certus_command_palette import CommandAction, rank_commands

    def noop():
        pass
    actions = [
        CommandAction(id="a", title="Alpha", callback=noop),
        CommandAction(id="b", title="Beta", callback=noop),
    ]
    ranked = rank_commands("", actions)
    assert [a.id for _s, a in ranked] == ["a", "b"]


def test_u3_command_action_enabled_cb_is_respected():
    from certus_command_palette import CommandAction

    a = CommandAction(id="x", title="X", callback=lambda: None, enabled_cb=lambda: False)
    assert a.is_enabled() is False
    b = CommandAction(id="y", title="Y", callback=lambda: None)
    assert b.is_enabled() is True
    # Exception in enabled_cb must default to False (not propagate)
    def _boom():
        raise RuntimeError("no")
    c = CommandAction(id="z", title="Z", callback=lambda: None, enabled_cb=_boom)
    assert c.is_enabled() is False


def test_u3_command_action_search_haystack_includes_keywords():
    from certus_command_palette import CommandAction, fuzzy_score

    a = CommandAction(
        id="x", title="Export spectra",
        callback=lambda: None,
        subtitle="Write to Excel",
        keywords=("xlsx", "report"),
    )
    hay = a.search_haystack()
    assert "export spectra" in hay
    assert "xlsx" in hay and "report" in hay
    # Searching on a keyword must score > 0
    assert fuzzy_score("xlsx", hay) > 0.0


# =============================================================================
# U3 integration on CertusBaseApp
# =============================================================================


def test_u3_certus_base_app_exposes_palette_hooks():
    from certus_ui import CertusBaseApp

    for attr in ("register_command", "_default_commands",
                 "open_command_palette", "_toggle_theme"):
        assert hasattr(CertusBaseApp, attr), f"CertusBaseApp missing {attr!r}"


def test_u3_default_commands_include_toggle_theme_and_quit():
    """Even without save/load hooks, baseline commands must exist."""
    from certus_command_palette import CommandAction
    from certus_ui import CertusBaseApp

    class _Stub:
        # Minimal duck to call the unbound method
        pass

    cmds = CertusBaseApp._default_commands(_Stub())
    ids = {c.id for c in cmds}
    assert "view.toggle_theme" in ids
    assert "app.quit" in ids


def test_u4_dashboard_card_show_event_triggers_fade_once(monkeypatch):
    from PyQt6.QtGui import QShowEvent
    from PyQt6.QtWidgets import QApplication

    QApplication.instance() or QApplication(sys.argv)
    calls: list[tuple[int, object]] = []

    fake_mod = types.SimpleNamespace(
        fade_in=lambda w, duration_ms=0: calls.append((duration_ms, w))
    )
    monkeypatch.setitem(sys.modules, "certus_animations", fake_mod)

    from certus_ui import CertusDashboardCard

    card = CertusDashboardCard("RMSE", icon_name="check-circle")
    ev = QShowEvent()
    card.showEvent(ev)
    card.showEvent(ev)

    assert len(calls) == 1
    assert calls[0][0] == 180
    assert calls[0][1] is card

