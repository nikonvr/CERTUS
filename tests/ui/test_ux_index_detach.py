"""INDEX must detach the plot of the tab you are looking at (step 2.11).

detach_current_plot dispatched on HARDCODED tab indices, and the tab order moved
under it: _add_main_control_buttons inserts "Data" before the other addTab calls.

Measured 2026-09-05 on the instantiated window:

    index 0 -> 'Data'            index 3 -> 'n & k'
    index 1 -> 'Synthesis'       index 4 -> 'Convergence'
    index 2 -> 'Spectrum'        index 5 -> 'Final Equations'

The handler assumed 0 = Spectrum and 1 = n&k, so the offset is TWO: pressing
"Detach Plot" on the Data tab detached the spectrum. One branch had already been
patched symptomatically - `elif current_index == 3 or tabText(...) == "Data"` -
which treats the symptom and leaves the cause.

The same offset explains a second defect: the layout comments "Spectrum Tab (0):
visible by default" and then calls setCurrentIndex(0), so the module opens on
Data, an empty tab. One fix puts out both.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def index_window(qapp):
    from certus.ui.certus_index_ui import CertusIndexApp

    win = CertusIndexApp()
    yield win
    for detached in list(getattr(win, "detached_plot_windows", {}).values()):
        detached.close()
    win.close()


def _tab_index(win, needle: str) -> int:
    for i in range(win.tabs.count()):
        if needle.lower() in win.tabs.tabText(i).lower():
            return i
    raise AssertionError(f"no tab matching {needle!r} among {[win.tabs.tabText(i) for i in range(win.tabs.count())]}")


def test_index_opens_on_the_spectrum_tab(index_window) -> None:
    """The layout says Spectrum; the operator must not land on an empty Data tab."""
    current = index_window.tabs.tabText(index_window.tabs.currentIndex())
    assert "spectrum" in current.lower(), f"CERTUS_INDEX opens on {current!r}"


@pytest.mark.parametrize(
    "tab_needle,expected_key",
    [
        ("Spectrum", "spectrum"),
        ("Data", "data_table"),
        ("n & k", "nk_n"),
    ],
)
def test_detach_follows_the_current_tab(index_window, tab_needle, expected_key) -> None:
    """Whatever the tab order becomes, Detach Plot must detach THIS tab."""
    index_window.detached_plot_windows.clear()
    index_window.tabs.setCurrentIndex(_tab_index(index_window, tab_needle))

    index_window.detach_current_plot()

    assert expected_key in index_window.detached_plot_windows, (
        f"on the {tab_needle!r} tab, Detach Plot produced "
        f"{sorted(index_window.detached_plot_windows)} instead of {expected_key!r}"
    )
