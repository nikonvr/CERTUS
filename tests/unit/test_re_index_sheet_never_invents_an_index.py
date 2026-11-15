"""RE's 'index' sheet parser must never replace an unreadable n by 1.5 (audit 2026-11-15, M-L6g).

A cell "2,30" (decimal comma stored as text) used to become n = 1.50 without a message, and the reverse engineering
ran on a wrong stack. A decimal comma is now read; a cell that still cannot be read, or an empty n cell, stops the
load with a message that names it.
"""

import logging

import pytest

from certus.ui.certus_re_excel_mixin import CertusREExcelMixin
from certus.ui.certus_re_table_mixin import CertusRETableMixin


class _Window(CertusREExcelMixin, CertusRETableMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test")


class _Sheet:
    def __init__(self, rows: list[tuple]) -> None:
        self.rows = rows

    def iter_rows(self, values_only: bool = True):
        return iter(self.rows)


_HEADER = ("lambda", "n1", "k1", "n2", "k2")


def test_a_decimal_comma_is_read_as_a_decimal_point() -> None:
    rows = [_HEADER, (500.0, 2.35, 0.0, 1.46, 0.0), (600.0, "2,30", "0,001", 1.46, 0.0), (700.0, 2.28, 0.0, "1,45", 0.0)]
    _w, n1, k1, n2, _k2 = _Window()._parse_re_index(_Sheet(rows))
    assert list(n1) == [2.35, 2.30, 2.28]
    assert list(k1) == [0.0, 0.001, 0.0]
    assert list(n2) == [1.46, 1.46, 1.45]


@pytest.mark.parametrize("cell", ["abc", None])
def test_an_unreadable_or_empty_n_cell_stops_the_load(cell) -> None:
    rows = [_HEADER, (500.0, 2.35, 0.0, 1.46, 0.0), (600.0, cell, 0.0, 1.46, 0.0), (700.0, 2.28, 0.0, 1.45, 0.0)]
    with pytest.raises(ValueError, match="n1"):
        _Window()._parse_re_index(_Sheet(rows))


def test_an_empty_k_cell_still_means_no_absorption() -> None:
    rows = [_HEADER, (500.0, 2.35, None, 1.46, 0.0), (600.0, 2.30, 0.0, 1.46, None)]
    _w, _n1, k1, _n2, k2 = _Window()._parse_re_index(_Sheet(rows))
    assert list(k1) == [0.0, 0.0]
    assert list(k2) == [0.0, 0.0]
