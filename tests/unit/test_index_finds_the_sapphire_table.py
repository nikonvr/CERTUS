"""CERTUS INDEX finds its sapphire table, example/sapphire fresnel.xlsx.

The path was built from the folder of the module that reads it: once certus_index_core moved
into certus/core (c2b1030, 2026-05-27) it named certus/core/example/sapphire fresnel.xlsx,
which does not exist. Every import warned "Sapphire substrate reference unavailable", and
choosing sapphire showed "example/sapphire fresnel.xlsx NOT FOUND" and left the
absorbing-substrate checkbox enabled. The fit itself did not change: the worker treats every
substrate but silicon as transparent, with or without the table.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _windows_end_with_the_test(qapp, monkeypatch):
    """The windows a test builds are destroyed when it ends (D11): closing only hides them."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "INDEX sapphire", main_windows_only=True)


def test_the_sapphire_table_is_read() -> None:
    import certus.core.certus_index_core as core

    assert Path(core._SAPPHIRE_DATA_FILE).is_file(), core._SAPPHIRE_DATA_FILE
    assert core._SAPPHIRE_WLS is not None and len(core._SAPPHIRE_WLS) > 0


def test_choosing_sapphire_names_the_table_and_locks_the_absorption(qapp) -> None:
    from certus.core.certus_core import SUBSTRATE_LIST
    from certus.ui.certus_index_ui import CertusIndexApp

    window = CertusIndexApp()
    window.cb_sub.setCurrentIndex(SUBSTRATE_LIST.index("Sapphire (Al2O3)"))

    assert "NOT FOUND" not in window.lbl_ksub_file.text()
    assert not window.chk_absorbing_sub.isEnabled()
    assert not window.chk_absorbing_sub.isChecked()
