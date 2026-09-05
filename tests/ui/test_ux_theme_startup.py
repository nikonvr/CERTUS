"""The persisted theme preference must actually reach the interface (step 2.5).

Measured 2026-09-04: load_theme_config() returned "dark" on this machine and all
eleven windows opened in LIGHT. The preference reached exactly two places -
apply_os_window_effects (certus_ui_utils.py:324, the OS title bar) and the plot
palette (:937) - and never CertusTheme.configure(). The operator who chose dark
reopened the application with a dark title bar around a light interface.

The audit harness neutralises load_theme_config (it forces "light" in every
module that imported the symbol), so this change cannot make the measurements
depend on the operator's preference.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("preference", ["dark", "light"])
def test_apply_certus_theme_honours_the_persisted_preference(qapp, monkeypatch, preference) -> None:
    """Theming a window must configure CertusTheme for the persisted mode."""
    from PyQt6.QtWidgets import QWidget

    from certus.ui import certus_ui_utils as ui_utils
    from certus.ui.certus_theme import CertusTheme

    monkeypatch.setattr(ui_utils, "load_theme_config", lambda: preference)

    try:
        # Start from the opposite mode so a no-op cannot pass by accident.
        CertusTheme.configure("light" if preference == "dark" else "dark")
        widget = QWidget()
        try:
            ui_utils.apply_certus_theme(widget)
            assert CertusTheme.DARK_MODE is (preference == "dark"), (
                f"persisted preference {preference!r} did not reach CertusTheme: "
                f"DARK_MODE={CertusTheme.DARK_MODE}"
            )
        finally:
            widget.deleteLater()
    finally:
        CertusTheme.configure("light")
