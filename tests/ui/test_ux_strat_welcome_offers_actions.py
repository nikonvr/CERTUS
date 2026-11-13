"""STRAT's welcome page offers actions: the example and the recent configurations (U10, decision Q37).

It showed six slogans ("Precision Targeting", "Zero-Bias Strategy", ...) where an operator looks for what to do next
(constat C2 of the corridor plan). STRAT did not record the files it loaded: the list is STRAT's own category.
"""

from __future__ import annotations

from pathlib import Path


def _buttons(widget) -> dict[str, object]:
    from PyQt6.QtWidgets import QPushButton

    return {b.text(): b for b in widget.findChildren(QPushButton) if b.isVisible()}


def test_the_example_button_opens_the_bundled_example(qapp) -> None:
    from certus.ui.certus_strat_welcome_ui import STRAT_EXAMPLE, WelcomeGuideWidget

    opened = []
    page = WelcomeGuideWidget(on_open=opened.append)
    page.show()
    qapp.processEvents()

    _buttons(page)["Open the example"].click()

    assert len(opened) == 1
    assert Path(opened[0]).as_posix().endswith(STRAT_EXAMPLE)
    assert Path(opened[0]).is_file()
    page.close()


def test_a_recent_configuration_is_offered_and_opens(qapp, tmp_path) -> None:
    from certus.ui.certus_recent import RecentCategories, clear_recent, record_recent
    from certus.ui.certus_strat_welcome_ui import WelcomeGuideWidget

    config = tmp_path / "my-strategy.json"
    config.write_text("{}", encoding="utf-8")
    clear_recent(RecentCategories.STRAT_CONFIG)
    record_recent(RecentCategories.STRAT_CONFIG, str(config))
    try:
        opened = []
        page = WelcomeGuideWidget(on_open=opened.append)
        page.show()
        qapp.processEvents()

        recent = [b for text, b in _buttons(page).items() if "my-strategy.json" in text]
        assert len(recent) == 1
        recent[0].click()
        assert Path(opened[0]) == config
        page.close()
    finally:
        clear_recent(RecentCategories.STRAT_CONFIG)


def test_without_an_opener_the_page_is_unchanged(qapp) -> None:
    from certus.ui.certus_strat_welcome_ui import WelcomeGuideWidget

    page = WelcomeGuideWidget()
    page.show()
    qapp.processEvents()

    assert "Open the example" not in _buttons(page)
    page.close()
