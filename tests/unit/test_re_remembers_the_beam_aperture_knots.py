"""`CertusREWorkersMixin._remember_beam_aperture_knots` keeps the phase 4 beam's aperture knots for the display, or forgets them (audit v2, plan S5.2).

It was a 31-line block in the middle of `_on_re_done`, the handler that shows the reverse-engineering results (307 lines, no unit test reaches it). Three attributes of the window carry
the answer: whether the beam is active, and the aperture knots in degrees and in nanometres. The beam is active only when the best candidate carries BOTH series and at least two knots in the
shorter of them; otherwise all three attributes are reset, so a window never shows the knots of the previous run.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from certus.ui.certus_re_workers_mixin import CertusREWorkersMixin


def window() -> SimpleNamespace:
    """A window that still holds the knots of a previous run: the helper must overwrite or clear them."""
    return SimpleNamespace(_re_p4_display_beam_active=True, _re_p4_display_ap_knots_deg=np.array([1.0]), _re_p4_display_ap_knots_nm=np.array([2.0]))


def remember(win, best: dict) -> None:
    CertusREWorkersMixin._remember_beam_aperture_knots(win, best)


def test_both_series_with_two_knots_or_more_switch_the_beam_on():
    win = window()
    remember(win, {"re_p4_beam_ap_knots_deg": [0.0, 20.0, 40.0], "re_p4_beam_ap_knots_nm": [400.0, 600.0, 800.0]})
    assert win._re_p4_display_beam_active is True
    np.testing.assert_array_equal(win._re_p4_display_ap_knots_deg, [0.0, 20.0, 40.0])
    np.testing.assert_array_equal(win._re_p4_display_ap_knots_nm, [400.0, 600.0, 800.0])


def test_the_two_series_are_cut_to_the_length_of_the_shorter():
    win = window()
    remember(win, {"re_p4_beam_ap_knots_deg": [0.0, 20.0, 40.0, 60.0], "re_p4_beam_ap_knots_nm": [400.0, 600.0]})
    np.testing.assert_array_equal(win._re_p4_display_ap_knots_deg, [0.0, 20.0])
    np.testing.assert_array_equal(win._re_p4_display_ap_knots_nm, [400.0, 600.0])


def test_the_kept_knots_are_copies_of_the_result():
    degrees = np.array([0.0, 20.0, 40.0])
    nanometres = np.array([400.0, 600.0, 800.0])
    win = window()
    remember(win, {"re_p4_beam_ap_knots_deg": degrees, "re_p4_beam_ap_knots_nm": nanometres})
    degrees[0] = 99.0
    nanometres[0] = 99.0
    assert win._re_p4_display_ap_knots_deg[0] == 0.0
    assert win._re_p4_display_ap_knots_nm[0] == 400.0


@pytest.mark.parametrize(
    "best",
    [
        {},
        {"re_p4_beam_ap_knots_deg": [0.0, 20.0]},
        {"re_p4_beam_ap_knots_nm": [400.0, 600.0]},
        {"re_p4_beam_ap_knots_deg": [0.0], "re_p4_beam_ap_knots_nm": [400.0]},
        {"re_p4_beam_ap_knots_deg": [0.0, 20.0], "re_p4_beam_ap_knots_nm": []},
    ],
    ids=["no series", "degrees only", "nanometres only", "one knot", "one series empty"],
)
def test_otherwise_the_beam_is_off_and_the_previous_knots_are_forgotten(best):
    win = window()
    remember(win, best)
    assert win._re_p4_display_beam_active is False
    assert win._re_p4_display_ap_knots_deg is None
    assert win._re_p4_display_ap_knots_nm is None


def test_the_handler_calls_the_helper():
    import inspect

    assert "self._remember_beam_aperture_knots(best)" in inspect.getsource(CertusREWorkersMixin._on_re_done)
