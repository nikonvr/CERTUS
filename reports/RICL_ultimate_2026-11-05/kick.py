"""Resonance kick for engine.py (2026-11-05, owner's idea): a few rounds of the native DESIGN resonance treatment
(`certus.physics.design_resonances.refine_resonances`, method of the companion paper), used only to leave a basin;
the caller then settles on the nominal 277 points. Three-line problem only (constant lossless indices)."""

from __future__ import annotations

import numpy as np

from certus.physics.design_resonances import ResonanceSettings, TransmissionBand, TransmissionProblem, refine_resonances

BANDS = tuple(TransmissionBand(float(a), float(b), float(t), 1.0) for a, b, t in
              [(445, 455, 1.0), (505, 515, 1.0), (635, 645, 1.0), (400, 440, 0.0), (460, 500, 0.0), (520, 630, 0.0),
               (650, 700, 0.0)])
INDEX = {"H": 2.35, "L": 1.45}


def resonance_kick(seq: str, d: np.ndarray, rounds: int, floor: float, tot: float | None) -> np.ndarray:
    prob = TransmissionProblem(np.array([INDEX[m] for m in seq]), 1.52, BANDS)
    settings = ResonanceSettings(rounds=rounds, burst=30, max_ot_nm=None if tot is None else tot + 0.5)
    ref = refine_resonances(prob, np.maximum(np.asarray(d, dtype=float), floor), settings=settings,
                            lower_bounds=np.full(len(seq), floor))
    return np.asarray(ref.thicknesses, dtype=float)
