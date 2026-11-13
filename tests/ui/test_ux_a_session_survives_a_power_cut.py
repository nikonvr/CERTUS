"""A window's configuration survives a power cut, and the next opening offers it back (U12 A, decision Q40).

Nothing survived a cut (constat C7 of the corridor plan). A window whose configuration changed writes it to its
session file every minute; a close that goes to its end erases it; a session found at the opening is offered, never
applied without the operator's answer, and never under the offscreen platform, where nobody answers.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def window_class():
    from PyQt6.QtWidgets import QWidget

    from certus.ui.certus_base_app_config_mixin import CertusAppConfigMixin

    class Window(CertusAppConfigMixin, QWidget):
        APP_NAME = "CERTUS-SESSION-TEST"

        def __init__(self) -> None:
            super().__init__()
            self.value = 1.0
            self.applied = None

        def _collect_config(self) -> dict:
            return {"value": self.value}

        def _apply_config(self, config: dict) -> None:
            self.applied = config
            self.value = config["value"]

    return Window


@pytest.fixture(autouse=True)
def _clean_session():
    from certus.ui.certus_session import clear_session

    clear_session("CERTUS-SESSION-TEST")
    yield
    clear_session("CERTUS-SESSION-TEST")


def test_the_session_is_kept_while_the_configuration_is_changed(qapp, window_class) -> None:
    from certus.ui.certus_session import read_session

    win = window_class()
    win._mark_initial_config_saved()
    win._session_autosave()
    assert read_session("CERTUS-SESSION-TEST") is None, "an unchanged configuration has nothing to keep"

    win.value = 2.5
    win._session_autosave()
    assert read_session("CERTUS-SESSION-TEST")["config"] == {"value": 2.5}

    win._session_end()
    assert read_session("CERTUS-SESSION-TEST") is None, "a finished close leaves no session"


def test_the_next_opening_offers_the_session_and_applies_it_on_yes(qapp, window_class, monkeypatch) -> None:
    from certus.ui.certus_session import read_session, write_session

    write_session("CERTUS-SESSION-TEST", {"value": 7.0})
    monkeypatch.setenv("QT_QPA_PLATFORM", "windows")
    asked = []
    monkeypatch.setattr(window_class, "_ask_to_resume_session", lambda self, when: asked.append(when) or True)

    win = window_class()
    win._session_start()
    win._session_timer.stop()

    assert len(asked) == 1
    assert win.applied == {"value": 7.0}
    assert read_session("CERTUS-SESSION-TEST") is None


def test_a_declined_session_is_not_applied(qapp, window_class, monkeypatch) -> None:
    from certus.ui.certus_session import write_session

    write_session("CERTUS-SESSION-TEST", {"value": 7.0})
    monkeypatch.setenv("QT_QPA_PLATFORM", "windows")
    monkeypatch.setattr(window_class, "_ask_to_resume_session", lambda self, when: False)

    win = window_class()
    win._session_start()
    win._session_timer.stop()

    assert win.applied is None


def test_nobody_is_asked_under_the_offscreen_platform(qapp, window_class, monkeypatch) -> None:
    from certus.ui.certus_session import read_session, write_session

    write_session("CERTUS-SESSION-TEST", {"value": 7.0})
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(window_class, "_ask_to_resume_session", lambda self, when: pytest.fail("asked offscreen"))

    win = window_class()
    win._session_start()
    win._session_timer.stop()

    assert win.applied is None
    assert read_session("CERTUS-SESSION-TEST") is not None


def test_a_session_of_another_window_or_format_is_refused(tmp_path, monkeypatch) -> None:
    from certus.ui import certus_session

    monkeypatch.setenv("CERTUS_CONFIG_DIR", str(tmp_path))
    path = certus_session.write_session("CERTUS-SESSION-TEST", {"value": 1.0})
    record = json.loads(path.read_text(encoding="utf-8"))

    record["app"] = "CERTUS-OTHER"
    path.write_text(json.dumps(record), encoding="utf-8")
    assert certus_session.read_session("CERTUS-SESSION-TEST") is None

    path.write_text('{"format": 1, "app": "CERTUS-SESSION-TEST", "config": {"val', encoding="utf-8")
    assert certus_session.read_session("CERTUS-SESSION-TEST") is None


def test_the_sessions_live_under_the_configuration_folder(tmp_path, monkeypatch) -> None:
    from certus.ui import certus_session

    monkeypatch.setenv("CERTUS_CONFIG_DIR", str(tmp_path))
    assert certus_session.session_path("CERTUS-DESIGN").parent == tmp_path / "sessions"
