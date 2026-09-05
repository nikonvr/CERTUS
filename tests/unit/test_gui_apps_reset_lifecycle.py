"""Test de cycle de vie et de robustesse du bouton Clear / Reset sur les applications CERTUS."""

from __future__ import annotations

import pytest
from certus.utils.certus_reset_framework import reset_app_to_defaults


@pytest.mark.unit
def test_design_app_reset_lifecycle(monkeypatch, qapp) -> None:
    """Vérifie que CertusDesignApp se réinitialise proprement sans exception."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _ = qapp

    from certus.ui.certus_design_ui import CertusDesignApp

    app_win = CertusDesignApp()
    try:
        success = reset_app_to_defaults(app_win, confirm=False)
        assert success is True, "CertusDesignApp reset failed"
    finally:
        app_win.close()


@pytest.mark.unit
def test_strat_app_reset_lifecycle(monkeypatch, qapp) -> None:
    """Vérifie que CertusStratApp se réinitialise proprement sans exception."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _ = qapp

    from certus.ui.certus_strat_ui import CertusStratApp

    app_win = CertusStratApp()
    try:
        success = reset_app_to_defaults(app_win, confirm=False)
        assert success is True, "CertusStratApp reset failed"
    finally:
        app_win.close()


@pytest.mark.unit
def test_index_app_reset_lifecycle(monkeypatch, qapp) -> None:
    """Vérifie que CertusIndexApp se réinitialise proprement sans exception."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _ = qapp

    from certus.ui.certus_index_ui import CertusIndexApp

    app_win = CertusIndexApp()
    try:
        success = reset_app_to_defaults(app_win, confirm=False)
        assert success is True, "CertusIndexApp reset failed"
    finally:
        app_win.close()
