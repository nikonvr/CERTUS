"""Chantier 40: CERTUS's oblique TMM against a third-party code, `tmm` (S. Byrnes, PyPI), outside the kernel.

    python -m pip install --no-deps --target %TEMP%\\certus_tmm_tiers tmm
    python reports\\tmm_tiers_2026-11-15\\probe_tmm_tiers.py --tmm-dir %TEMP%\\certus_tmm_tiers

`tmm` writes an absorbing index n + ik (time in exp(-iwt)); CERTUS writes n - ik (Macleod, exp(+iwt)): the probe hands
`tmm` the conjugate. Layer order: CERTUS index 0 touches the substrate, `tmm` lists from the incident medium, so the
probe reverses it. Stacks are drawn from a fixed seed: lossless and absorbing dielectrics, a metal layer, absorbing
substrates, angles up to 85 degrees, s and p. Writes `tmm_tiers.json` next to this file and prints MAX_DR, MAX_DT.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

WLS = np.array([400.0, 550.0, 800.0, 1300.0])
ANGLES = [0.0, 30.0, 60.0, 85.0]
SUBSTRATES = {"glass": 1.52 + 0j, "lossy": 2.0 - 0.01j, "semiconductor": 3.5 - 0.5j, "metal": 0.15 - 3.5j}


def _stacks(rng: np.random.Generator) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    stacks = {}
    for name, n_layers, k_max, metal in (("lossless", 7, 0.0, False), ("absorbing", 9, 0.05, False),
                                        ("with-metal", 5, 0.01, True)):
        n = rng.uniform(1.35, 2.6, (WLS.size, n_layers)) - 1j * k_max * rng.random((WLS.size, n_layers))
        if metal:
            n[:, 2] = 0.2 - 3.0j
        d = rng.uniform(15.0, 220.0, n_layers)
        if metal:
            d[2] = 12.0
        stacks[name] = (n.astype(np.complex128), d)
    return stacks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tmm-dir", required=True, help="directory where the third-party `tmm` was installed")
    args = parser.parse_args()
    sys.path.insert(0, args.tmm_dir)
    import tmm

    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    rows, max_dr, max_dt = [], 0.0, 0.0
    for stack_name, (n, d) in _stacks(np.random.default_rng(40)).items():
        for sub_name, n_sub in SUBSTRATES.items():
            for angle in ANGLES:
                for pol in ("s", "p"):
                    r, t = calc_spectrum_oblique_vectorized(WLS, n, d, np.full(WLS.size, n_sub), angle, pol)
                    for i, wl in enumerate(WLS):
                        n_list = [1.0, *np.conj(n[i][::-1]), np.conj(n_sub)]
                        d_list = [np.inf, *d[::-1], np.inf]
                        ref = tmm.coh_tmm(pol, n_list, d_list, np.radians(angle), float(wl))
                        dr, dt = abs(float(r[i]) - ref["R"]), abs(float(t[i]) - ref["T"])
                        max_dr, max_dt = max(max_dr, dr), max(max_dt, dt)
                        rows.append({"stack": stack_name, "substrate": sub_name, "angle": angle, "pol": pol,
                                     "wl": float(wl), "R": float(r[i]), "T": float(t[i]), "R_tmm": float(ref["R"]),
                                     "T_tmm": float(ref["T"]), "dR": dr, "dT": dt})
    out = Path(__file__).with_name("tmm_tiers.json")
    out.write_text(json.dumps({"tmm_version": getattr(tmm, "__version__", "?"), "cases": len(rows),
                               "max_dR": max_dr, "max_dT": max_dt, "rows": rows}, indent=1), encoding="utf-8")
    print(f"CASES={len(rows)} MAX_DR={max_dr:.3e} MAX_DT={max_dt:.3e} -> {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
