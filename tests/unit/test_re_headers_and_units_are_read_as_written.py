"""RE must read a measurement column as its header and its values say (audit 2026-11-15, M-L4a, M-L4b, M-L4c).

M-L4a: a glued header "R45p" was read as R at 0 deg, s polarisation, without a note.
M-L4b: "sans arrière" (accented) kept the backside: the accented letters had been lost from the regex.
M-L4c: a column in percent whose maximum is at most 1.25 (an antireflection R) was read as a fraction, x100.
"""

from __future__ import annotations

import pytest

from certus.utils.certus_re_helpers import _re_measurement_values_are_percent, parse_re_column_header


@pytest.mark.parametrize(
    ("header", "angle", "pol"),
    [("R45p", 45.0, "p"), ("T30s", 30.0, "s"), ("R45s1f", 45.0, "s"), ("R 45 p", 45.0, "p")],
)
def test_a_glued_header_keeps_its_angle_and_polarisation(header: str, angle: float, pol: str) -> None:
    parsed = parse_re_column_header(header)
    assert parsed.angle_deg == angle
    assert parsed.pol == pol


@pytest.mark.parametrize("header", ["R 45 s sans arrière", "R 45 s sans arriere", "R 45 s sans arrières"])
def test_sans_arriere_drops_the_backside_with_or_without_accent(header: str) -> None:
    assert parse_re_column_header(header).include_backside is False


def test_an_antireflection_r_in_percent_is_read_as_percent() -> None:
    assert _re_measurement_values_are_percent([0.2, 0.6, 1.2]) is True


def test_a_fraction_stays_a_fraction() -> None:
    assert _re_measurement_values_are_percent([0.02, 0.045, 0.92, 1.01]) is False
