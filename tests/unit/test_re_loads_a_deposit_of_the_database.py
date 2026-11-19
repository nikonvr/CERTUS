"""RE loads a reference of the deposit database (lot 2d, 2026-11-19): `certus_depots_re` writes the three sheets.

Before: RE needed a complete workbook (docs/ETAT.md section 1), and no deposit of the database could reach it. A
reference of `references_index.json` gives the measured channels, the thickness and the Tauc-Lorentz-Urbach parameters
of its layer: enough for a one-layer design and its index. A normalized reference is refused (RE models absolute R and
T), with the reason.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from certus.utils.certus_depots_db import database_dir, load_catalogue
from certus.utils.certus_depots_re import re_workbook_sheets, write_re_workbook

CATALOGUE = {entry["id"]: entry for entry in load_catalogue()}
REFERENCES = {ref["nom"]: ref for ref in json.loads((database_dir() / "references_index.json").read_text(encoding="utf-8"))["references"]}
ABSOLUTE = "sb2s3-silice"


def test_every_normalized_reference_is_refused_with_its_reason() -> None:
    normalized = [ref for ref in REFERENCES.values() if ref["normalise"]]
    assert len(normalized) == 10
    for ref in normalized:
        with pytest.raises(ValueError, match="normalized"):
            re_workbook_sheets(ref, CATALOGUE)


def test_the_measurement_sheet_holds_the_channels_re_parses_with_the_plate() -> None:
    from certus.utils.certus_re_helpers import parse_re_column_header

    sheets = re_workbook_sheets(REFERENCES[ABSOLUTE], CATALOGUE)
    header = sheets["measurement"][0]
    assert header[0] == "Wavelength, nm"
    for title in header[1:]:
        parsed = parse_re_column_header(title)
        assert parsed.target_type in ("T", "R")
        assert parsed.include_backside is True
        assert parsed.pol == "Avg"
    wl = np.array([row[0] for row in sheets["measurement"][1:]])
    low, high = REFERENCES[ABSOLUTE]["bande_nm"]
    assert wl.min() >= low
    assert wl.max() <= high
    assert np.all(np.diff(wl) > 0)


def test_the_design_is_the_reference_layer_as_one_qwot() -> None:
    ref = REFERENCES[ABSOLUTE]
    sheets = re_workbook_sheets(ref, CATALOGUE)
    (lam, lambda_ref, substrate), (qwot,) = sheets["design"]
    assert lam == "lambda"
    assert substrate == ref["substrat"]
    index = np.array(sheets["index"][1:], dtype=np.float64)
    n_ref = float(np.interp(lambda_ref, index[:, 0], index[:, 1]))
    assert qwot == pytest.approx(4.0 * n_ref * ref["d_nm"] / lambda_ref, rel=1e-12)


def test_the_index_is_the_tauc_lorentz_urbach_of_the_reference() -> None:
    from certus.utils.certus_depots_re import _tlu_nk

    ref = REFERENCES[ABSOLUTE]
    index = np.array(re_workbook_sheets(ref, CATALOGUE)["index"][1:], dtype=np.float64)
    n, k = _tlu_nk(ref["parametres"], index[:, 0])
    assert np.array_equal(index[:, 1], n)
    assert np.array_equal(index[:, 2], k)
    assert np.all(index[:, 2] >= 0.0)
    assert np.array_equal(index[:, 1], index[:, 3])


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    """Join the window's threads, then destroy it (tests/qt_lifecycle.py, D11 and D23)."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "RE deposit workbook", main_windows_only=True)


def test_the_re_window_loads_the_workbook(tmp_path) -> None:
    from CERTUS_RE import CertusREApp

    path = write_re_workbook(REFERENCES[ABSOLUTE], CATALOGUE, tmp_path / "sb2s3.xlsx")
    window = CertusREApp()
    assert window.load_reverse_engineering_from_path(str(path)) is True
