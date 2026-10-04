"""Closing a window over a configuration changed since it was saved asks first (audit UX A03, ETAT D80).

Measured 2026-10-02 on FIELD: `lcalc` edited, no calculation running, and `confirm_close_during_run` let the window
close without a word: the only protection was against a running worker, and `_qs_save` keeps the layout of the window
(geometry, splitters, table columns), never the configuration. An operator who had built a stack and not saved it
lost it by clicking the cross.

A window that can say what its configuration is remembers it as of its last save, load or first settled state, and asks
on a close that would discard a change: save, close without saving, or cancel.
"""

from __future__ import annotations

import json

import pytest
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QFileDialog

import certus.ui.certus_base_app as base_app


@pytest.fixture
def window(qapp):
    from certus.ui.certus_field_ui import CertusFieldApp

    win = CertusFieldApp()
    win.mark_config_saved()
    try:
        yield win
    finally:
        win.worker_manager._active_workers = []
        win.close()


@pytest.fixture
def asked(monkeypatch, window):
    """What the operator is asked, and the answer the test gives: "save", "discard" or "cancel"."""
    state = {"count": 0, "answer": "cancel"}

    def ask():
        state["count"] += 1
        return state["answer"]

    monkeypatch.setattr(window, "_ask_about_unsaved_config", ask)
    return state


def _edit(win) -> None:
    win.edit_lcalc.setText("1234.5")


def test_an_unchanged_configuration_is_not_unsaved(window) -> None:
    assert not window.has_unsaved_config()


def test_a_changed_configuration_is_unsaved_and_the_change_can_be_taken_back(window) -> None:
    before = window.edit_lcalc.text()

    _edit(window)
    assert window.has_unsaved_config()

    window.edit_lcalc.setText(before)
    assert not window.has_unsaved_config(), "the value is back where it was saved: nothing is lost by closing"


def test_closing_over_a_change_asks_and_cancel_keeps_the_window(window, asked) -> None:
    _edit(window)
    event = QCloseEvent()

    allowed = window.confirm_close_unsaved(event)

    assert asked["count"] == 1
    assert not allowed
    assert not event.isAccepted()


def test_closing_without_saving_goes_on(window, asked) -> None:
    _edit(window)
    asked["answer"] = "discard"

    assert window.confirm_close_unsaved(QCloseEvent())


def test_saving_first_lets_the_close_go_on_once_the_file_is_written(window, asked, monkeypatch, tmp_path) -> None:
    _edit(window)
    asked["answer"] = "save"
    target = tmp_path / "field_config.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: (str(target), "")))

    assert window.confirm_close_unsaved(QCloseEvent())

    assert json.loads(target.read_text(encoding="utf-8")), "the configuration was not written"
    assert not window.has_unsaved_config()


def test_a_save_that_the_operator_abandons_keeps_the_window_open(window, asked, monkeypatch) -> None:
    """The file dialog was cancelled: nothing was saved, so the close must not go on."""
    _edit(window)
    asked["answer"] = "save"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: ("", "")))
    event = QCloseEvent()

    assert not window.confirm_close_unsaved(event)
    assert not event.isAccepted()


def test_nothing_is_asked_when_nothing_changed(window, asked) -> None:
    assert window.confirm_close_unsaved(QCloseEvent())
    assert asked["count"] == 0


def test_a_run_in_progress_is_left_to_its_own_question(window, asked) -> None:
    """`confirm_close_during_run` asks about the run: a second box on top of it would be noise."""

    class Running:
        def isRunning(self) -> bool:
            return True

    _edit(window)
    window.worker_manager._active_workers = [Running()]

    assert window.confirm_close_unsaved(QCloseEvent())
    assert asked["count"] == 0


def test_loading_a_configuration_makes_it_the_saved_one(window, tmp_path) -> None:
    path = tmp_path / "field_config.json"
    path.write_text(json.dumps(window._collect_config(), default=str), encoding="utf-8")
    _edit(window)
    assert window.has_unsaved_config()

    assert window.load_config(str(path)) is True

    assert not window.has_unsaved_config()


def test_saving_makes_the_current_configuration_the_saved_one(window, monkeypatch, tmp_path) -> None:
    _edit(window)
    target = tmp_path / "field_config.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: (str(target), "")))

    window.save_config()

    assert not window.has_unsaved_config()


def test_a_window_with_no_configuration_to_save_is_never_asked(window, monkeypatch) -> None:
    """A window with no serializable state has nothing to compare or discard."""
    monkeypatch.setattr(window, "_collect_config", lambda: {})
    window.mark_config_saved()
    _edit(window)
    assert not window.has_unsaved_config()
    assert window.confirm_close_unsaved(QCloseEvent())


def test_strat_saves_the_configuration_it_compares_before_closing(qapp, monkeypatch, tmp_path) -> None:
    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    try:
        win.mark_config_saved()
        before = win.widgets["l0"].text()
        win.widgets["l0"].setText("501" if before != "501" else "502")
        assert win.has_unsaved_config()

        target = tmp_path / "strat_config.json"
        monkeypatch.setattr(win, "_ask_about_unsaved_config", lambda: "save")
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: (str(target), "")))

        assert win.confirm_close_unsaved(QCloseEvent())
        assert json.loads(target.read_text(encoding="utf-8"))["l0"] == win.widgets["l0"].text()
        assert not win.has_unsaved_config()
    finally:
        win.close()


def test_the_close_event_of_the_real_window_reaches_the_question(window, asked, monkeypatch) -> None:
    """End to end: `window.close()` goes through the event filter, which asks, and `cancel` keeps the window open."""
    monkeypatch.setattr(base_app, "_prompts_are_off", lambda: False)
    window.show()
    _edit(window)
    asked["answer"] = "cancel"

    closed = window.close()

    assert asked["count"] == 1
    assert closed is False
    assert window.isVisible()


def test_offscreen_a_close_asks_nothing(window, asked) -> None:
    """The suite closes windows it has modified (tests/unit/test_gui_apps_smoke.py closes eleven): a modal box would hang it."""
    _edit(window)

    window.close()

    assert asked["count"] == 0


@pytest.mark.parametrize("kind", ["re", "index_spline"])
def test_re_and_index_spline_saved_settings_are_guarded_and_round_trip(kind, qapp, monkeypatch, tmp_path) -> None:
    if kind == "re":
        from CERTUS_RE import CertusREApp

        win = CertusREApp()
        control = win.re_speed_fast_radio
    else:
        from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

        win = CertusIndexSplineApp()
        control = win.chk_r

    try:
        assert win._saved_config_snapshot is not None, "the window must protect edits made immediately after opening"
        assert not win.has_unsaved_config()
        initial = control.isChecked()
        control.setChecked(not initial)
        assert win.has_unsaved_config()
        win._mark_initial_config_saved()
        assert win.has_unsaved_config(), "a delayed initial snapshot must not erase the user's early edit"

        answers = []
        monkeypatch.setattr(base_app, "_prompts_are_off", lambda: False)
        monkeypatch.setattr(win, "_ask_about_unsaved_config", lambda: answers.append("asked") or "cancel")
        win.show()
        assert win.close() is False
        assert answers == ["asked"]
        assert win.isVisible()

        target = tmp_path / f"{kind}_config.json"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: (str(target), "")))
        win.save_config()
        assert json.loads(target.read_text(encoding="utf-8"))
        assert not win.has_unsaved_config()

        if kind == "re":
            win.re_speed_medium_radio.setChecked(True)
        else:
            control.setChecked(initial)
        assert win.has_unsaved_config()
        assert win.load_config(str(target)) is True
        assert control.isChecked() is not initial
        assert not win.has_unsaved_config()
    finally:
        win.hide()
        win.close()
