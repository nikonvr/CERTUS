"""The keys a window owes its keyboard user are bound to commands that exist (audit v2, plan S6.2).

Real gaps, measured on 2026-10-01 (the audit's other findings on this subject were measurement errors: see
test_ux_audit_measures_what_the_user_sees.py):

* METAL, both windows: Ctrl+S and Ctrl+O. `save_config` and `load_config` exist, are inherited from CertusBaseApp, round-trip a
  METAL configuration, and had no key (and no button).
* the curve smoother: F1 was PROMISED by a tooltip ("Full documentation is under Help (F1)") and bound to nothing; Ctrl+O and
  Ctrl+S had no key although Load and Save buttons exist.
* the substrate window: Ctrl+O, Ctrl+S, F1, for the same reason.
* the launcher: a file could be dropped on it, never opened from the keyboard.

Each key is its command's button (`click()` respects a greyed-out button: no data, no save) or the existing method.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


WINDOWS = {
    "CERTUS_HUB": ("CERTUS_HUB", "CertusHub"),
    "CERTUS_SMOOTHER": ("certus.utils.certus_curve_smoother", "CurveSmootherGUI"),
    "CERTUS_SUBSTRATE_INDEX": ("certus.ui.certus_substrate_ui", "SubstrateIndexGUI"),
    "CERTUS_METAL_SINGLE": ("CERTUS_METAL_SINGLE", "CertusMetalSingleApp"),
    "CERTUS_METAL_BILAYER": ("CERTUS_METAL_BILAYER", "CertusMetalBilayerApp"),
}


@pytest.mark.parametrize("tag", list(WINDOWS))
def test_a_window_carries_the_keys_it_owes(qapp, tag) -> None:
    from scripts.audit_ux_certus import vital_keys_for
    from certus.ui.certus_ui_utils import shortcut_owner

    module, cls = WINDOWS[tag]
    win = getattr(__import__(module, fromlist=[cls]), cls)()
    try:
        missing = [key for key in vital_keys_for(tag) if shortcut_owner(win, key) is None]
        assert not missing, f"{tag} owes {list(vital_keys_for(tag))} and lacks {missing}"
    finally:
        win.close()


@pytest.mark.parametrize("tag", ["CERTUS_METAL_SINGLE", "CERTUS_METAL_BILAYER"])
def test_ctrl_s_and_ctrl_o_reach_the_configuration_of_metal(qapp, tag, monkeypatch) -> None:
    """The keys run `save_config` and `load_config`, which already round-trip a METAL configuration."""
    from PyQt6.QtGui import QShortcut

    module, cls = WINDOWS[tag]
    window_class = getattr(__import__(module, fromlist=[cls]), cls)
    called: list[str] = []
    monkeypatch.setattr(window_class, "save_config", lambda self: called.append("save"))
    monkeypatch.setattr(window_class, "load_config", lambda self, filename=None: called.append("load"))
    win = window_class()
    try:
        by_key = {sc.key().toString(): sc for sc in win.findChildren(QShortcut)}
        by_key["Ctrl+S"].activated.emit()
        by_key["Ctrl+O"].activated.emit()
    finally:
        win.close()

    assert called == ["save", "load"]


def test_the_smoother_keys_are_its_buttons_and_respect_their_greyed_state(qapp, monkeypatch) -> None:
    """Ctrl+S with no data loaded does nothing, like its button; F1 is the quick guide the tooltip pointed to."""
    from PyQt6.QtGui import QShortcut
    from PyQt6.QtWidgets import QMessageBox

    import certus.utils.certus_curve_smoother as smoother

    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda _parent, title, *_a, **_k: shown.append(title)))
    saved: list[str] = []
    monkeypatch.setattr(smoother.CurveSmootherGUI, "save_file", lambda self: saved.append("save"))
    win = smoother.CurveSmootherGUI()
    try:
        assert not win.btn_save.isEnabled(), "the premise: no data, no save"
        by_key = {sc.key().toString(): sc for sc in win.findChildren(QShortcut)}

        by_key["Ctrl+S"].activated.emit()
        by_key["F1"].activated.emit()
    finally:
        win.close()

    assert saved == [], "Ctrl+S saved although the Save button is greyed out"
    assert shown == ["Help"], "F1 did not open the quick guide"
    assert "F1" in win.btn_help.toolTip()


def test_ctrl_o_opens_a_file_in_the_module_that_reads_it(qapp, monkeypatch, tmp_path) -> None:
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import QFileDialog

    import CERTUS_HUB

    chosen = tmp_path / "run_strat_config.json"
    chosen.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *_a, **_k: (str(chosen), "")))
    launched: list[tuple] = []
    monkeypatch.setattr(CERTUS_HUB.CertusHub, "launch_module", lambda self, script, files=(): launched.append((script, list(files))))
    win = CERTUS_HUB.CertusHub()
    try:
        action = next(a for a in win.findChildren(QAction) if a.shortcut().toString() == "Ctrl+O")
        action.trigger()
    finally:
        win.active_processes.clear()
        win.close()

    assert launched == [("CERTUS_STRAT.py", [str(chosen)])]


def test_ctrl_o_does_nothing_when_the_dialog_is_cancelled(qapp, monkeypatch) -> None:
    from PyQt6.QtWidgets import QFileDialog

    import CERTUS_HUB

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *_a, **_k: ("", "")))
    launched: list[tuple] = []
    monkeypatch.setattr(CERTUS_HUB.CertusHub, "launch_module", lambda self, script, files=(): launched.append((script, list(files))))
    win = CERTUS_HUB.CertusHub()
    try:
        win.open_file_in_module()
    finally:
        win.active_processes.clear()
        win.close()

    assert launched == []
