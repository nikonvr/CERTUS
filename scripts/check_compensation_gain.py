"""Gain de compensation par longueur d'onde de monitoring.

DIRECT selection criterion, and much more telling than a local error: we
injects a probe error on the previous layer, we simulate the current layer
has ZERO noise, and we see how much it corrects.

    gain(lambda) = |Delta_d_i| / delta_sonde

    gain < 1 -> the upstream error is AMORTIZED (stable stacking)
    gain ~ 1 -> it is reported as is
    gain > 1 -> it is AMPLIFIED (divergence on N layers)

On 48 layers, it is this magnitude which decides whether the error remains bounded. She is
orthogonal to P95(|Delta_d|) of Phase A, which only measures the LOCAL error:
a layer can be specified locally and amplify what precedes it.

Cost: a few evaluations per candidate, NO Monte-Carlo.

    .venv\\Scripts\\python.exe scripts\\check_compensation_gain.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import certus_physics  # noqa: E402,F401  (facade : evite l'import circulaire)
from certus_physics import simulate_growth_kernel  # noqa: E402

NM_ATTENUATE = 0
PROBE_OFFSET = 0.5
FACTOR = 1.0


def compensation_gain(p_thick, i_layer, wl, n_H, n_L, n_Sub, probe_err=2.0):
    """Returns (gain, delta_d) for a probe error on layer i_layer-1."""
    if i_layer < 1:
        return float("nan"), float("nan")
    prev_nom = np.asarray(p_thick[:i_layer], dtype=np.float64).copy()
    prev_err = prev_nom.copy()
    prev_err[i_layer - 1] += probe_err
    d_nom = float(p_thick[i_layer])

    v_ref, _ = simulate_growth_kernel(
        p_thick, i_layer, prev_nom, wl, n_H, n_L, n_Sub, PROBE_OFFSET, 0.0, FACTOR, NM_ATTENUATE
    )
    v_err, _ = simulate_growth_kernel(
        p_thick, i_layer, prev_err, wl, n_H, n_L, n_Sub, PROBE_OFFSET, 0.0, FACTOR, NM_ATTENUATE
    )
    delta = (v_err - d_nom) - (v_ref - d_nom)
    return abs(delta) / probe_err, delta


def main() -> None:
    n_H, n_L, n_Sub = complex(2.30, 0.0), complex(1.46, 0.0), complex(1.52, 0.0)
    p_thick = np.array([120.0, 180.0, 120.0, 180.0, 120.0], dtype=np.float64)
    i_layer = 4

    print(f"empilement {list(p_thick)}  |  couche etudiee : {i_layer}")
    print(f"erreur sonde de +2,0 nm sur la couche {i_layer - 1}, bruit NUL\n")
    print(f"{'lambda':>8} {'gain':>8} {'Delta_d':>10}   verdict")
    print("-" * 48)

    rows = []
    for wl in range(420, 1021, 40):
        g, d = compensation_gain(p_thick, i_layer, float(wl), n_H, n_L, n_Sub)
        if g < 0.8:
            verdict = "AMORTIT"
        elif g < 1.2:
            verdict = "neutre"
        else:
            verdict = "AMPLIFIE"
        print(f"{wl:>8} {g:>8.3f} {d:>+10.4f}   {verdict}")
        rows.append((g, wl))

    rows.sort()
    print()
    print(f"meilleure : {rows[0][1]} nm  (gain {rows[0][0]:.3f})")
    print(f"pire      : {rows[-1][1]} nm  (gain {rows[-1][0]:.3f})")
    if rows[0][0] > 0:
        print(f"rapport   : {rows[-1][0] / rows[0][0]:.1f}x entre la meilleure et la pire")
    print()
    print("Si ce rapport est grand, le critere DISCRIMINE et merite d'entrer dans")
    print("la selection de Phase A. S'il est proche de 1, il n'apporte rien ici.")


if __name__ == "__main__":
    main()
