"""The curve smoother never rewrites the workbook it read (audit 2026-11-15, M-L5e).

Choosing the source file in the save dialog added the ``clean_measurements`` sheet to it in place, not atomically, and
through pandas: the charts and shapes of the workbook were lost. The smoothed data now always go to another file,
``<name>_lisse.xlsx`` next to the source by default, written through a temporary file.
"""

from __future__ import annotations

import numpy as np
import openpyxl
import pandas as pd
import pytest

import certus.ui.certus_curve_smoother as smoother_module


@pytest.fixture
def smoother(qapp, monkeypatch):
    monkeypatch.setattr(smoother_module, "notify", lambda *_a, **_k: "")
    monkeypatch.setattr(
        smoother_module.QMessageBox, "question", lambda *_a, **_k: smoother_module.QMessageBox.StandardButton.Yes
    )
    win = smoother_module.CurveSmootherGUI()
    yield win
    win.close()


def _spectrum() -> pd.DataFrame:
    lam = np.linspace(400.0, 800.0, 201)
    return pd.DataFrame({"lambda": lam, "T": 0.9 + 0.05 * np.sin(lam / 15.0)})


def _source(tmp_path, name: str = "mesure.xlsx"):
    path = tmp_path / name
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _spectrum().to_excel(writer, sheet_name="measurements", index=False)
        pd.DataFrame({"note": ["keep me"]}).to_excel(writer, sheet_name="notes", index=False)
    return path


def _save_as(monkeypatch, win, source, chosen) -> None:
    win.df = _spectrum()
    win.file_path = str(source)
    monkeypatch.setattr(smoother_module.QFileDialog, "getSaveFileName", lambda *_a, **_k: (str(chosen), ""))
    win.save_file()


def test_choosing_the_source_file_writes_next_to_it(smoother, monkeypatch, tmp_path) -> None:
    source = _source(tmp_path)
    before = source.read_bytes()

    _save_as(monkeypatch, smoother, source, source)

    assert source.read_bytes() == before, "the source workbook was rewritten"
    written = tmp_path / "mesure_lisse.xlsx"
    assert written.exists()
    assert openpyxl.load_workbook(written).sheetnames == ["clean_measurements"]
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_the_proposed_name_is_next_to_the_source(smoother, monkeypatch, tmp_path) -> None:
    source = _source(tmp_path)
    proposed: list[str] = []

    def _dialog(_parent, _caption, default, *_a, **_k):
        proposed.append(default)
        return "", ""

    smoother.df = _spectrum()
    smoother.file_path = str(source)
    monkeypatch.setattr(smoother_module.QFileDialog, "getSaveFileName", _dialog)
    smoother.save_file()

    assert proposed == [str(tmp_path / "mesure_lisse.xlsx")]


def test_another_file_is_written_as_chosen(smoother, monkeypatch, tmp_path) -> None:
    source = _source(tmp_path)
    before = source.read_bytes()
    chosen = tmp_path / "ailleurs.xlsx"

    _save_as(monkeypatch, smoother, source, chosen)

    assert source.read_bytes() == before
    rows = list(openpyxl.load_workbook(chosen)["clean_measurements"].iter_rows(values_only=True))
    assert rows[0] == ("lambda", "T")
    assert len(rows) == 202
