"""The optional peak-top refinement must also judge rounds at that same peak top.

Load the two functions without importing the campaign's million-point grids. A
shifted Gaussian residual separates the pole estimate from its real maximum.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SOURCE = (Path(__file__).resolve().parents[2] / "reports" / "DESIGN_bs5050_2026-10-22"
          / "tikhonravov" / "envelope_v2" / "threeline_track.py")


def _campaign(peak_mode):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {"top", "track"}]
    field_wavelengths = []

    def residual(_seq, d, wls):
        # Round zero looks better at its pole estimate, but worse at its true top.
        height, shift = (0.8, 0.06) if d[0] == 0.0 else (0.7, 0.01)
        return height * np.exp(-((np.asarray(wls) - 500.0 - shift) / 0.1) ** 2)

    def poles(seq, d):
        return [(500.0, 0.2, float(residual(seq, d, [500.0])[0]), 0.002 + 1e-9j)]

    def field(_ns, _d, wl):
        field_wavelengths.append(wl)
        return 2.0, 0

    context = {
        "np": np, "time": SimpleNamespace(time=lambda: 0.0), "ROUNDS": 1,
        "PEAK": peak_mode, "DETECT": "complex", "NOM": {"k0": np.arange(277)},
        "fl": SimpleNamespace(N_IDX={"L": 1.45}, e2max=field),
        "gs": SimpleNamespace(GRIDS={g: g for g in ("nominal", "resolved", "check")},
                              mf=lambda _seq, _d, _grid: 0.1),
        "err": residual, "poles": poles,
        "polish": lambda _mode, _seq, _d, _peaks: np.array([1.0]),
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), context)
    return context["track"], field_wavelengths, residual


def test_top_mode_reports_the_true_peak_and_its_field_wavelength():
    track, field_wavelengths, _ = _campaign("top")
    row = track("height", "L", np.array([0.0]), rounds=0)[0]
    assert float(row["highest"]) == pytest.approx(0.8, abs=1e-6)
    assert field_wavelengths == pytest.approx([500.06], abs=1e-7)
    expected = np.sqrt(0.1 ** 2 + 1e4 * 0.8 ** 2 / 277)
    assert float(row["mf_tracked"]) == pytest.approx(expected, rel=1e-6)


def test_round_selection_follows_the_objective_optimized_at_the_top():
    track, _, _ = _campaign("top")
    rows = track("height", "L", np.array([0.0]), rounds=1)
    assert min(rows, key=lambda row: float(row["mf_tracked"]))["round"] == 1


def test_legacy_pole_mode_keeps_the_stored_height_and_field_position():
    track, field_wavelengths, residual = _campaign("pole")
    row = track("height", "L", np.array([0.0]), rounds=0)[0]
    height = float(residual("L", np.array([0.0]), [500.0])[0])
    assert row["highest"] == f"{height:.6f}"
    assert row["mf_tracked"] == f"{np.sqrt(0.1 ** 2 + 1e4 * height ** 2 / 277):.6e}"
    assert field_wavelengths == [500.0]


def test_nominal_control_adds_no_peak_charge_or_field_measurement():
    track, field_wavelengths, _ = _campaign("top")
    rows = track("nominal", "L", np.array([0.0]), rounds=1)
    assert all(float(row["mf_tracked"]) == 0.1 for row in rows)
    assert all(row["peaks"] == 0 for row in rows)
    assert field_wavelengths == []


def test_precise_export_preserves_the_full_state_for_independent_judging():
    track, _, _ = _campaign("pole")
    d = np.array([0.12345678901234567])
    row = track("height", "L", d, rounds=0, precise=True)[0]
    restored = np.array([float(value) for value in row["d_nm"].split()])
    assert np.array_equal(restored.view(np.uint64), d.view(np.uint64))
