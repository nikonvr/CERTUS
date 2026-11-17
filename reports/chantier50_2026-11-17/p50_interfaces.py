"""Chantier 50 : d'ou vient l'ecart CERTUS - `tmm.inc_tmm` sur un substrat absorbant ?

Trois calculs de la meme plaque (deux couches, substrat de 1 mm, incidence normale, air des deux cotes) :
  A. CERTUS, `calculate_RT_with_backside_fused` ;
  B. l'oracle independant `tests/oracle/tmm_reference.py::rt_plate_incoherent` (interfaces internes a Re(n), le modele
     que CERTUS documente) ;
  C. le meme assemblage que B, interfaces internes a n COMPLEXE (ce que fait `tmm`) ;
contre D. `tmm.inc_tmm` 0.2.0. Hypothese : A = B a l'arrondi, C = D a l'arrondi, et A - D = l'ecart de modele.

python reports/chantier50_2026-11-17/p50_interfaces.py   (tmm dans %TEMP%/certus_tmm_tiers ; tests/oracle sur le chemin)
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.environ["TEMP"], "certus_tmm_tiers"))
sys.path.insert(0, os.path.join("tests", "oracle"))
import tmm  # noqa: E402
from tmm_reference import rt_plate_incoherent, rt_stack  # noqa: E402

from certus.physics.certus_tmm_matrix import calculate_RT_with_backside_fused  # noqa: E402

WLS = np.array([450.0, 550.0, 700.0, 900.0])
N_FILM, D_FILM = [2.3 + 0j, 1.46 + 0j], [95.0, 140.0]  # index 0 = cote substrat (convention CERTUS et oracle)
D_SUB = 1.0e6


def complex_inside(lam: float, n_sub: complex) -> float:
    """B with the interfaces seen from inside at the complex index (Beer-Lambert unchanged)."""
    k = -n_sub.imag
    _r_f, t_f = rt_stack(lam, N_FILM, D_FILM, n_inc=1.0 + 0j, n_sub=n_sub)
    r_in, _t = rt_stack(lam, N_FILM[::-1], D_FILM[::-1], n_inc=n_sub, n_sub=1.0 + 0j)
    r_b, t_b = rt_stack(lam, [], [], n_inc=n_sub, n_sub=1.0 + 0j)
    t_b = 1.0 - r_b  # bare lossless interface
    tau = np.exp(-4.0 * np.pi * k * D_SUB / lam)
    return t_f * t_b * tau / (1.0 - r_in * r_b * tau * tau)


print("max |dT| sur 4 longueurs d'onde ; A CERTUS, B oracle Re(n), C oracle n complexe, D tmm.inc_tmm")
for k in (0.0, 1e-6, 4.4e-6, 2e-5, 1e-4):
    n_sub = 1.52 - 1j * k
    _R, t_a = calculate_RT_with_backside_fused(np.array(D_FILM), np.array([N_FILM] * len(WLS)), np.full(len(WLS), n_sub), WLS, D_SUB)
    t_b = np.array([rt_plate_incoherent(lam, N_FILM, D_FILM, [], [], n_sub, 0.0, True, D_SUB)[1] for lam in WLS])
    t_c = np.array([complex_inside(lam, n_sub) for lam in WLS])
    t_d = np.array([tmm.inc_tmm("s", [1.0, 1.46, 2.3, complex(1.52, k), 1.0], [np.inf, 140.0, 95.0, D_SUB, np.inf],
                                ["i", "c", "c", "i", "i"], 0.0, lam)["T"] for lam in WLS])
    print(f"k={k:<7g} A-B {np.max(np.abs(t_a - t_b)):.1e}  C-D {np.max(np.abs(t_c - t_d)):.1e}  "
          f"A-D {np.max(np.abs(t_a - t_d)):.1e}  B-C {np.max(np.abs(t_b - t_c)):.1e}")
