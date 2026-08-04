"""Version corrigee : on TABULE au lieu de choisir deux points, et on ecarte
explicitement les points tournants, ou l'inversion parabolique change de loi.

Pour chaque longueur d'onde on compare :
  Phase A : bruit photometrique       -> Delta_d attendu ~ dT / |dT/dd|
  Phase B : bruit = dT_dd * z * s_nm  -> Delta_d attendu ~ s_nm  (constant ?)
"""
import sys

sys.path.insert(0, r"C:\dev\CERTUS\0108")

import numpy as np
import certus_physics
from certus_physics import simulate_growth_kernel

NM_ATTEN = 0
n_H = complex(2.30, 0.0)
n_L = complex(1.46, 0.0)
n_Sub = complex(1.52, 0.0)
PROBE, NMF, D = 0.5, 1.0, 120.0
p_thick = np.array([D], dtype=np.float64)
empty = np.empty(0, dtype=np.float64)


def T_of(wl, d):
    phi = 2.0 * np.pi / wl * n_H * d
    cp, sp = np.cos(phi), np.sin(phi)
    den = cp + n_Sub * (1j * sp / n_H) + 1j * n_H * sp + n_Sub * cp
    return 4.0 * n_Sub.real / abs(den) ** 2


def slope_curv(wl, h=0.5):
    tm, t0, tp = T_of(wl, D - h), T_of(wl, D), T_of(wl, D + h)
    return (tp - tm) / (2 * h), (tp - 2 * t0 + tm) / h**2


def dd(wl, noise):
    v, _ = simulate_growth_kernel(p_thick, 0, empty, wl, n_H, n_L, n_Sub, PROBE, noise, NMF, NM_ATTEN)
    return v - D


Z, S_PCT, S_NM = 1.0, 1.0, 1.0
dT = Z * S_PCT / 100.0

print(f"{'wl':>6} {'dT/dd':>11} {'|lin/quad|':>10}  {'A: Dd':>9} {'A*|p|':>9}  {'B: Dd':>9}")
print("-" * 66)
lin_ok = []
for wl in range(460, 1005, 40):
    p, c = slope_curv(float(wl))
    # dominance du terme lineaire sur le quadratique a l'echelle de l'erreur
    ratio = abs(p) / (abs(c) * 1.0 + 1e-30)
    a = dd(float(wl), dT)
    b = dd(float(wl), p * Z * S_NM)
    flag = "" if ratio > 5 else "  <- pres d'un extremum"
    print(f"{wl:>6} {p:>+11.3e} {ratio:>10.1f}  {a:>+9.4f} {abs(a*p):>9.2e}  {b:>+9.4f}{flag}")
    if ratio > 5:
        lin_ok.append((abs(a * p), abs(b)))

print()
if len(lin_ok) >= 3:
    ap = [x[0] for x in lin_ok]
    bp = [x[1] for x in lin_ok]
    disp_a = max(ap) / min(ap)
    disp_b = max(bp) / min(bp)
    print(f"Hors extrema, {len(lin_ok)} points :")
    print(f"  Phase A : |Delta_d * pente| varie d'un facteur {disp_a:.2f}")
    print(f"            -> proche de 1 = Delta_d suit bien dT/|pente|")
    print(f"  Phase B : |Delta_d| varie d'un facteur {disp_b:.2f}")
    print(f"            -> proche de 1 = Delta_d INDEPENDANT de la pente")
    print()
    print("=" * 66)
    if disp_b < 1.3:
        print("CONFIRME : hors extrema, Phase B rend une erreur INSENSIBLE a la pente.")
    else:
        print(f"INFIRME : Phase B varie d'un facteur {disp_b:.2f}, la pente joue encore.")
else:
    print("pas assez de points hors extrema pour conclure")
