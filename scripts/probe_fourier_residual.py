"""Check Fourier residual diagnostics against known paths and the fixed-TOT RICL stacks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from _artefact import ecrire_json
from probe_auto_grid import ROOT

REFERENCE = ROOT / "reports/questions_design_2026-11-13/probe_ricl_fixed_tot.json"


def wavenumber_grid(lo_nm, hi_nm, points):
    return np.linspace(1.0 / hi_nm, 1.0 / lo_nm, points)


def spectrum(sigma, residual, optical_thickness_nm):
    """Treat each target band as a window sampled uniformly in inverse wavelength."""
    window = np.hanning(len(sigma))
    centered = residual - np.average(residual, weights=window)
    step = (sigma[-1] - sigma[0]) / (len(sigma) - 1)
    paths = np.fft.rfftfreq(len(sigma), d=step)
    power = np.abs(np.fft.rfft(window * centered)) ** 2
    power[0] = 0.0
    # A Hann main lobe extends two bins to either side of a resolved peak.
    cutoff = 2.0 * optical_thickness_nm
    bin_nm = paths[1]
    guarded = cutoff + 2.0 * bin_nm
    high = paths > guarded
    total = float(power.sum())
    high_power = float(power[high].sum())
    return {
        "rms": float(np.sqrt(np.mean(residual**2))),
        "peak_path_nm": float(paths[np.argmax(power)]) if total > 0 else None,
        "path_bin_nm": float(bin_nm), "nyquist_path_nm": float(paths[-1]),
        "high_path_fraction": high_power / total if total > 0.0 else 0.0,
        "high_path_rms": float(np.sqrt(np.average(centered**2, weights=window**2) * high_power / total))
        if total > 0.0 else 0.0,
    }


def layer_controls(points):
    from certus.physics.certus_tmm_hl import calculate_RT_vectorized_real_HL

    sigma = wavenumber_grid(400.0, 1200.0, points)
    wl = 1.0 / sigma
    index = np.full(len(wl), 2.35 + 0j)
    substrate = np.full(len(wl), 1.52 + 0j)
    thickness = 5000.0
    args = (wl, index, index, substrate)
    _, thick = calculate_RT_vectorized_real_HL(*args, np.array([thickness]), with_backside=False)
    _, thin = calculate_RT_vectorized_real_HL(*args, np.array([thickness / 4]), with_backside=False)
    tot = thickness * index[0].real
    d_thick = spectrum(sigma, thick - 0.5, tot)
    d_thin = spectrum(sigma, thin - 0.5, tot / 4)
    mismatch = spectrum(sigma, thick - thin, tot / 4)
    for measured, expected in ((d_thick, 2 * tot), (d_thin, 2 * tot / 4)):
        assert abs(measured["peak_path_nm"] - expected) <= measured["path_bin_nm"] / 2, measured
    assert mismatch["high_path_fraction"] > 0.35, mismatch
    return {"thick_layer": d_thick, "thin_layer": d_thin, "thin_against_thick_target": mismatch}


def ricl_controls(points, *, first_band_only=False):
    import engine

    from certus.physics.certus_tmm_matrix import calculate_RT_no_backside

    samples = json.loads(REFERENCE.read_text(encoding="utf-8"))
    sequence = samples["sequence"]
    bands = sorted(engine.THREELINE_BANDS)
    if first_band_only:
        bands = bands[:1]
    rows = {}
    for label, stack in samples["results"].items():
        thickness = np.asarray(stack["d_nm"])
        rows[label] = []
        for lo, hi, target in bands:
            sigma = wavenumber_grid(lo, hi, points)
            wl = 1.0 / sigma
            transmission = np.empty_like(wl)
            n = engine.nvec(sequence).astype(np.complex128)
            for start in range(0, len(wl), 8192):
                part = slice(start, start + 8192)
                wavelengths = wl[part]
                indices = np.tile(n, (len(wavelengths), 1))
                substrate = np.full(len(wavelengths), complex(engine.N_SUB))
                _, transmission[part] = calculate_RT_no_backside(thickness, indices, substrate, wavelengths)
            diagnostic = spectrum(sigma, transmission - target, stack["tot_nm"])
            rows[label].append({"lo_nm": lo, "hi_nm": hi, "target": target, **diagnostic})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    from certus.core.certus_core import ensure_numba_cache_dir

    ensure_numba_cache_dir()
    trials = {}
    for points in (16_384, 32_768):
        trials[points] = {"control": layer_controls(points), "ricl": ricl_controls(points)}
    for points in (262_144, 524_288):
        trials[points] = {"ricl": ricl_controls(points, first_band_only=True)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ecrire_json(args.out, {"reference": REFERENCE.name, "trials": trials})


if __name__ == "__main__":
    main()
