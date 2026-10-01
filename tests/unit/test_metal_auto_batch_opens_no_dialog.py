"""An unattended METAL batch (`--auto-run --auto-close`) has nobody to click a dialog.

Loading a configuration ended with a modal « Load Successful » box, twice per batch (the
launcher and the batch kickoff both load the file): the run waited forever, offscreen
included (D39 of docs/ETAT.md, seen with faulthandler on 2026-09-28).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "METAL auto batch", main_windows_only=True)


@pytest.fixture
def dialogs(monkeypatch):
    import certus.metal.certus_metal_common as common

    opened: list[str] = []
    monkeypatch.setattr(common.QMessageBox, "information", lambda *a, **k: opened.append("information"))
    monkeypatch.setattr(common, "show_load_summary_dialog", lambda *a, **k: opened.append("summary"))
    return opened


@pytest.mark.parametrize(("module_name", "class_name"), [
    ("certus.metal.certus_metal_single_app", "CertusMetalSingleApp"),
    ("certus.metal.certus_metal_bilayer_app", "CertusMetalBilayerApp"),
])
def test_loading_a_configuration_in_auto_batch_opens_no_dialog(qapp, dialogs, module_name, class_name) -> None:
    import importlib

    window = getattr(importlib.import_module(module_name), class_name)()
    window._auto_batch_mode = True

    window._post_load_config("config.json", {"physical_params": {}})

    assert dialogs == []


def test_an_interactive_load_still_confirms(qapp, dialogs) -> None:
    """Negative control: outside a batch the confirmation stays, so the patch above is live."""
    from certus.metal.certus_metal_single_app import CertusMetalSingleApp

    window = CertusMetalSingleApp()
    window._auto_batch_mode = False

    window._post_load_config("config.json", {"physical_params": {}})

    assert "information" in dialogs
