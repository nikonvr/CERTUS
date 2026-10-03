"""Each HUB tile says, in one sentence, what the module is for (audit UX A09, ETAT D87).

Measured 2026-10-02, a tile showed its name and an icon, nothing else: INDEX, INDEX SPLINE, RE, STRAT, FIELD or the two
METAL entries asked for prior knowledge, and the description that does exist ("Stochastic Global Optimization. PGLOBAL
algorithm with Single-Linkage Clustering.") is a method, read only in the tooltip.

The catalogue now carries a `task` for every module, a short sentence about what the operator does there, and the tile
writes it under the name, where it can be read without hovering. The hub also opens the bundled DESIGN example.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from certus.core.certus_hub_config import HUB_APP_CATALOG


def test_every_module_of_the_catalogue_has_a_task_sentence() -> None:
    for item in HUB_APP_CATALOG:
        task = item.get("task", "")
        assert task, f"{item['title']} has no task sentence"
        assert task.endswith("."), f"{item['title']}: a sentence ends with a full stop: {task!r}"
        assert len(task) <= 90, f"{item['title']}: {len(task)} characters, a tile cannot show that: {task!r}"
        assert task != item["desc"], f"{item['title']}: the task repeats the description"


def test_no_two_modules_share_a_task_sentence() -> None:
    tasks = [item["task"] for item in HUB_APP_CATALOG]
    assert len(set(tasks)) == len(tasks), "two modules read the same: the sentence would not tell them apart"


@pytest.fixture(scope="module")
def hub(qapp):
    from CERTUS_HUB import CertusHub

    win = CertusHub()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win.close()


def _cards(hub):
    from certus.ui.certus_hub_widgets import ApplicationCard

    return [card for card in hub.findChildren(ApplicationCard) if getattr(card, "script_name", "")]


def test_each_tile_writes_its_task_under_its_name(hub) -> None:
    by_script = {item["script"]: item["task"] for item in HUB_APP_CATALOG}
    cards = _cards(hub)
    assert len(cards) == len(HUB_APP_CATALOG), "a module has no tile"
    for card in cards:
        label = card.findChild(QLabel, "AppCardTask")
        assert label is not None, f"{card.accessibleName()} has no task line"
        assert label.text() == by_script[card.script_name]


def test_the_task_line_of_a_tile_is_not_cut(hub) -> None:
    for card in _cards(hub):
        label = card.findChild(QLabel, "AppCardTask")
        assert label.heightForWidth(label.width()) <= label.height(), (
            f"{card.accessibleName()}: the task needs {label.heightForWidth(label.width())} px, the line has {label.height()}"
        )
        assert label.geometry().bottom() <= card.height(), f"{card.accessibleName()}: the task line leaves the tile"


def test_the_tooltip_starts_with_the_task(hub) -> None:
    by_script = {item["script"]: item["task"] for item in HUB_APP_CATALOG}
    for card in _cards(hub):
        assert by_script[card.script_name] in card.toolTip()
        assert card.accessibleDescription().startswith(by_script[card.script_name])


def test_the_hub_opens_a_real_example_from_a_visible_button(hub, monkeypatch) -> None:
    from pathlib import Path

    from PyQt6.QtWidgets import QPushButton

    button = hub.findChild(QPushButton, "HubOpenDesignExample")
    assert button is not None
    assert button.isVisible()

    launches = []
    monkeypatch.setattr(hub, "launch_module", lambda script, *, files=(): launches.append((script, files)))
    button.click()

    assert len(launches) == 1
    script, files = launches[0]
    assert script == "CERTUS_DESIGN.py"
    assert len(files) == 1
    assert Path(files[0]).is_file()
    assert Path(files[0]).name == "JSON-design-example.json"
