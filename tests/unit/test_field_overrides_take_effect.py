"""FIELD's own specialisations take effect.

`CertusFieldApp` listed `CertusBaseApp` before its mixins, so the base class shadowed every
FIELD specialisation (measured on 2026-09-28):
- « Save configuration » ran `CertusBaseApp.save_config`, whose `_collect_config` hook FIELD
  never provided: the file held `{}`; « Load configuration » ran the base `_apply_config`,
  which does nothing;
- « Detach plot » ran `CertusBaseApp.detach_current_plot`, which reads a `plot_tabs` that
  FIELD does not have: AttributeError;
- FIELD's log copy never ran. Neither did its splitter sizes and its `_apply_theme`, which
  are gone: active, they failed the UX ratchet (plot area 72.8 % against 79.1 %, 4 narrow
  buttons against 1), so the base behaviour stays the rendering the UX campaign measured.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "FIELD config", main_windows_only=True)


@pytest.fixture
def field_app(qapp, monkeypatch):
    from certus.ui.certus_field_ui import CertusFieldApp

    monkeypatch.setattr("certus.ui.certus_field_state_mixin.show_toast", lambda *a, **k: None)
    return CertusFieldApp()


def test_saved_configuration_holds_the_field_settings(field_app, tmp_path, monkeypatch) -> None:
    from PyQt6.QtWidgets import QFileDialog

    target = tmp_path / "field.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), "JSON (*.json)"))
    field_app.edit_angle.setValue(12.5)

    field_app.save_config()

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved.get("theta_inc_deg") == 12.5
    assert {"mat_H", "mat_L", "l0", "emp_factors", "layer_types"} <= set(saved)


def test_a_saved_configuration_loads_back(field_app, tmp_path, monkeypatch) -> None:
    from PyQt6.QtWidgets import QFileDialog

    target = tmp_path / "field.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), "JSON (*.json)"))
    field_app.edit_angle.setValue(33.0)
    field_app.save_config()

    field_app.edit_angle.setValue(0.0)
    field_app.load_config(str(target))

    assert field_app.edit_angle.value() == 33.0


def test_detaching_a_plot_opens_its_window_and_reattaching_closes_it(field_app, monkeypatch) -> None:
    monkeypatch.setattr("certus.ui.certus_field_plot_mixin.show_toast", lambda *a, **k: None)
    field_app.tab_widget.setCurrentIndex(1)

    field_app.detach_current_plot()
    assert list(field_app.detached_plot_windows) == ["field_profile"]

    field_app.reattach_plot("field_profile")
    assert field_app.detached_plot_windows == {}


def test_field_mixins_come_before_the_base_class() -> None:
    from certus.ui.certus_field_ui import CertusFieldApp

    for name in ("_collect_config", "_apply_config",
                 "detach_current_plot", "reattach_plot", "_get_plot_targets", "copy_logs_to_clipboard"):
        owner = next(k for k in CertusFieldApp.__mro__ if name in k.__dict__)
        assert owner.__module__.startswith("certus.ui.certus_field_"), (name, owner.__name__)
