"""Help buttons are real click targets and the startup messages say what the operator can do (audit UX 2026-11-18)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QLineEdit, QPushButton

ROOT = Path(__file__).resolve().parents[2]
MIN_TARGET_PX = 24


def test_the_info_icon_is_a_24_px_target(qapp) -> None:
    from certus.ui.certus_ui_widgets_factory import create_info_icon

    button = create_info_icon("Help")

    assert button.width() >= MIN_TARGET_PX
    assert button.height() >= MIN_TARGET_PX


def test_the_metal_help_button_is_a_24_px_target(qapp) -> None:
    from certus.ui.certus_metal_base_app import MetalBaseApp

    layout = MetalBaseApp._create_labeled_input(None, "Label", QLineEdit(), "A tooltip")
    buttons = [layout.itemAt(i).widget() for i in range(layout.count()) if isinstance(layout.itemAt(i).widget(), QPushButton)]

    assert len(buttons) == 1
    assert buttons[0].width() >= MIN_TARGET_PX
    assert buttons[0].height() >= MIN_TARGET_PX


@pytest.mark.parametrize(
    "module",
    ["certus_spectrum_eval_ui.py", "certus_base_app_engine_mixin.py", "certus_strat_ui_worker.py"],
)
def test_startup_messages_do_not_speak_of_jit(module) -> None:
    source = (ROOT / "certus" / "ui" / module).read_text(encoding="utf-8")

    assert "Waiting for JIT compilation" not in source
    assert "JIT Warmup complete" not in source
