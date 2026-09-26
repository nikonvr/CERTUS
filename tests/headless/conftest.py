"""Keep each headless test's Qt objects and background work inside that test."""

import pytest
from qt_lifecycle import qt_lifecycle


@pytest.fixture(autouse=True)
def headless_lifecycle(qapp, monkeypatch):
    """Join work before deleting windows, including after an assertion failure."""
    yield from qt_lifecycle(qapp, monkeypatch, "Headless")
