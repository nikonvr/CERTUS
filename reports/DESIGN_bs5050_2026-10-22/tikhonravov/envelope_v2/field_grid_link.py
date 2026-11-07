"""Grid artefacts and electric-field enhancement (2026-11-01, owner: can the grid problems be tied to field
enhancement inside the stack?).

Hypothesis: a resonance hidden between grid points is light trapped in a cavity of the stack; its width dl sets the
time light dwells there, hence the stored energy and the peak of |E|^2 (relative to the incident wave), which should grow
as 1 / dl. For every peak of |T - T'| above 1 % in the bands (0.0002 nm scan) of the three-line designs (the nominal
one and those polished on finer grids by threeline_refine_probe.py), print its wavelength, height and FWHM, the effective
optical path lambda^2 / (2 pi dl), and the largest |E|^2 in the stack at the peak and at the nearest 1 nm grid point
(CERTUS field module, certus_field_core); then the largest |E|^2 over the band, on the grid points and on a fine scan,
for each design of the three problems.
usage: SEARCH_TARGET=threeline python field_grid_link.py
"""

from __future__ import annotations

import csv
import os

import numpy as np
import threeline_refine_probe as probe

from certus.core.certus_field_core import _calculate_field_single_pol

# 2026-11-03: n_H follows SEARCH_NH as in search.py (threeline_track's Newton read it here at 2.35); unset, unchanged
N_IDX = {"H": float(os.environ.get("SEARCH_NH", "2.35")), "L": 1.45}


def e2max(ns, d, wl, n_sub=1.52) -> tuple[float, int]:
    """Largest |E|^2 in the stack (incident wave = 1) at wl, and its layer counted from the substrate (index 0)."""
    peaks = _calculate_field_single_pol(np.asarray(ns, dtype=np.complex128)[::-1], np.asarray(d, dtype=float)[::-1],
                                        n_sub, float(wl), 1.0, 64, 0.0, False)[6][::-1]
    k = int(np.argmax(peaks))
    return float(peaks[k]), k


def threeline() -> None:
    r = min(csv.DictReader(open("gradual_deep2_cont_seed89_clean2.csv", encoding="utf-8")),
            key=lambda r: float(r["mf_oracle"]))
    designs = [("nominal (1 nm)", r["seq"], np.array([float(v) for v in r["d_nm"].split()]))]
    designs += [(f"polished on {row['grid_nm']} nm", row["seq"], np.array([float(v) for v in row["d_nm"].split()]))
                for row in csv.DictReader(open("threeline_refine_probe.csv", encoding="utf-8"))]
    print("three-line filter, 109 layers: hidden resonances and the field they hold", flush=True)
    for label, seq, d in designs:
        ns = [N_IDX[m] for m in seq]
        print(f"  {label}", flush=True)
        for h, x, fw in probe.peaks(seq, d)[:4]:
            e_pk, k_pk = e2max(ns, d, x)
            e_gp, _k = e2max(ns, d, round(x))
            print(f"    {x:9.4f} nm  |T-T'| {100 * h:5.1f} %  FWHM {fw:.4f} nm  path {x * x / (2 * np.pi * fw) / 1e6:6.2f} mm"
                  f"  max|E|^2 {e_pk:9.1f} (layer {k_pk} {seq[k_pk]}), at {round(x)} nm {e_gp:6.2f}", flush=True)
        grid = np.concatenate([np.arange(a, b + 1.0) for a, b, _t in probe.gs.s._bands])
        fine = np.concatenate([np.arange(a, b + 1e-9, 0.01) for a, b, _t in probe.gs.s._bands])
        print(f"    largest |E|^2 over the band: on the 277 grid points {max(e2max(ns, d, w)[0] for w in grid):.2f}, "
              f"every 0.01 nm {max(e2max(ns, d, w)[0] for w in fine):.1f}", flush=True)


if __name__ == "__main__":
    threeline()
