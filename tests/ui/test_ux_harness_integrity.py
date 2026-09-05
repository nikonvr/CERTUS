"""Integrity tests for the CERTUS UX audit harness."""

from pathlib import Path


def test_harness_pins_a_resolved_font() -> None:
    """The audit harness must never measure a machine without fonts.

    Measured 2026-09-04: with the bare offscreen plugin, QFontDatabase.families()
    returns 0 and the panel widths are wrong by up to 28 %.
    """
    src = Path("scripts/audit_ux_certus.py").read_text(encoding="utf-8")
    assert "QT_QPA_FONTDIR" in src
    assert "QFontDatabase.families()" in src
    assert '"font_family"' in src and '"qpa_platform"' in src


def test_harness_covers_every_module_the_hub_can_launch() -> None:
    """A module the HUB launches but the audit ignores receives no fix.

    Measured 2026-09-04: SMOOTHER and SUBSTRATE INDEX were missing, and they are
    the only two modules still carrying a 20 px-high button after T8.
    """
    import importlib.util
    from certus.core.certus_hub_config import HUB_APP_CATALOG

    spec = importlib.util.spec_from_file_location("_audit", "scripts/audit_ux_certus.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    audited = {k.removeprefix("CERTUS_").replace("_", " ") for k in mod.MODULES}
    launched = {item["title"] for item in HUB_APP_CATALOG}
    assert not (launched - audited), f"modules lances mais jamais audites : {launched - audited}"


def test_harness_does_not_double_count_tables() -> None:
    src = Path("scripts/audit_ux_certus.py").read_text(encoding="utf-8")
    assert "findChildren(QTableWidget) + findChildren(QTableView)" not in src.replace("win.", "")


def test_harness_says_when_the_skeleton_never_settled() -> None:
    """A partial skeleton must never be returned as if it were complete.

    The stabilisation loop exits either on three identical readings or on its
    12 s limit, and both exits produced the same-looking row. Measured
    2026-09-04: under the load of a full tests/ui run, CERTUS_DESIGN reported
    'Detach plot' and its tab widget as MISSING, while a solo run of the very
    same code matches the baseline exactly (114 controls, zero diff). The
    phantom removal was attributed to a code regression in section 0bis of
    docs/GEMINI_UX_TOP1_2026-09-04.md for half a day.

    A run that did not settle is not a measurement: it must say so.
    """
    src = Path("scripts/audit_ux_certus.py").read_text(encoding="utf-8")
    assert '"skeleton_stable"' in src, "the harness must report whether the count settled"
    assert '"skeleton_settle_s"' in src, "how long it took is what sizes the limit"


def test_harness_confirms_stability_after_a_pause() -> None:
    """An unchanging control count does not mean the window finished building.

    The settle loop accepts three identical readings, which span 150 ms, while
    the startup timers this suite defers reach 600 ms (and 1200 ms for the HUB
    splash). Worse, a window blocked in a Numba compilation reports a PERFECTLY
    constant count for as long as it is blocked, so 'stable' is exactly what a
    half-built window looks like.

    Measured 2026-09-04 on CERTUS_DESIGN: the first worker of a cold series
    returns 84 controls with stable=True and settle=1.53 s; run again once warm,
    the very same code returns 86. Three consecutive pytest suites failed on it,
    and it was mis-attributed first to a code regression, then to a polluting
    neighbour test - both wrong.

    So the count must be re-checked after a pause longer than those timers.
    """
    src = Path("scripts/audit_ux_certus.py").read_text(encoding="utf-8")
    assert "_CONFIRM_S" in src, "the harness must re-check the count after a pause"
    assert '"skeleton_confirm_delta"' in src, "how much it moved during that pause is the evidence"


def test_harness_neutralises_the_persisted_theme() -> None:
    """The audit must not depend on which theme the operator last chose.

    CertusTheme.configure("light") fixes the COLOURS, but the theme toggle reads
    load_theme_config() directly, and that reads a config FILE which
    _isolate_qsettings does not cover. Measured 2026-09-04: on this machine the
    persisted preference is "dark", so the toggle recorded itself as
    'CertusThemeToggle|◑' - on a machine set to light it would be '◐', and the
    skeleton baseline would fail for a reason that is not in the code at all.
    """
    src = Path("scripts/audit_ux_certus.py").read_text(encoding="utf-8")
    assert "load_theme_config" in src, "the harness must neutralise the persisted theme preference"


