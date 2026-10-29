"""Edge filters EF1-EF10 of Amotchkina et al., Appl. Opt. 51, 8677 (2012): their robust criterion under random errors.

Problem (their Sec. 2): R = 100 % at 585-643 nm and T = 100 % at 670-710 nm, unpolarised light, merit function Eq. (2)
at 43, 45 and 47 deg, 1 nm grid; TiO2 / SiO2 Sellmeier (their Eq. 1), TiO2 extinction from their text (0 above 600 nm);
substrate Suprasil, 1 mm (index not given in the paper: Malitson fused silica, an assumption). Designs: their Tables 1-2,
layer 1 = TiO2. Yield corridors (their Sec. 2, back side included): R > 99 % at 585-635 nm, R > 89 % at 643 nm,
T > 93.5 % at 670-710 nm, at 45 deg.

R, T and dR/dd, dT/dd: CERTUS `compute_oblique_rt_and_grads_analytic` (checked against the independent oracle by
`check`). Robust criterion: their own Eq. (5) of Tikhonravov et al., Proc. SPIE 4829, 1061 (2003),
MF^2 + sum_i alpha_i^2 |dr/dd_i|^2, with alpha_i = sigma_OT / n_i (random optical-thickness errors, n at 650 nm): the
second-order E[MF^2].

check                -> oracle comparison, layer order, sums of their tables, merit values of their Table 3
analyse SIGMAS DRAWS -> robust criterion and Monte Carlo yield (random OT errors) for EF1-EF10, ranks against Table 4
polish NAME SIGMA    -> minimise their Eq. (5) from design NAME (floor 30 nm, their thinnest layer), then yields
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import search as s  # noqa: F401  (puts the repository and the oracle on sys.path)
import tmm_reference as oracle
from scipy.optimize import least_squares
from scipy.stats import spearmanr

from certus.physics.gradient_oblique import compute_oblique_rt_and_grads_analytic

HERE = Path(__file__).resolve().parent
SUB_D_NM = 1.0e6
ANGLES = (43.0, 45.0, 47.0)
W_R = np.arange(585.0, 644.0)  # 61 points
W_T = np.arange(670.0, 711.0)  # 41 points
Y_R1, Y_T = np.arange(585.0, 636.0), np.arange(670.0, 711.0)
FLOOR = 30.0
SEED = 20261030

# Their Tables 1-2, physical thicknesses in nm, layer 1 first (TiO2), alternating.
DESIGNS = {
    "EF1": [36.24, 153.83, 154.98, 156.98, 72.17, 95.23, 87.03, 540.78, 80.17, 126.78, 206.83, 130.90, 84.93, 263.24,
            84.56, 128.30, 71.90, 126.86, 79.18, 228.91, 121.10, 132.80, 76.52, 107.75, 46.38, 92.29, 78.00, 351.75,
            30.00],
    "EF2": [60.09, 290.72, 72.09, 135.66, 78.23, 288.88, 75.06, 163.93, 162.80, 154.93, 79.64, 338.21, 90.48, 271.75,
            84.37, 132.24, 72.42, 155.07, 303.13, 153.22, 74.82, 95.65, 50.93, 350.02, 78.66, 84.63, 30.00],
    "EF3": [65.25, 288.59, 73.36, 128.54, 79.28, 286.67, 85.32, 146.30, 168.60, 146.08, 78.99, 345.50, 85.95, 275.82,
            86.84, 123.60, 75.46, 146.19, 308.24, 153.03, 74.62, 100.04, 52.90, 352.45, 69.79, 95.60, 30.00],
    "EF4": [41.37, 137.35, 160.27, 142.52, 73.82, 115.32, 102.03, 78.89, 166.74, 131.41, 83.53, 116.44, 73.16, 138.55,
            310.11, 136.29, 71.01, 123.27, 80.60, 147.43, 145.64, 150.70, 82.92, 124.35, 82.25, 51.03, 63.46, 361.02,
            50.02, 209.34],
    "EF5": [80.21, 308.90, 28.74, 163.59, 73.42, 128.62, 93.44, 247.76, 85.83, 126.30, 72.16, 126.07, 78.09, 218.22,
            121.98, 129.54, 73.15, 128.49, 76.70, 158.93, 137.15, 164.63, 78.51, 124.02, 62.80, 582.08, 57.77, 196.09],
    "EF6": [35.76, 328.71, 76.77, 148.92, 148.27, 183.21, 65.37, 129.17, 62.05, 184.69, 143.69, 142.65, 70.99, 131.11,
            74.27, 162.18, 148.01, 165.32, 202.96, 141.01, 79.36, 298.99, 78.14, 145.36, 29.96, 144.87, 45.99, 113.66,
            29.96],
    "EF7": [189.01, 314.64, 74.08, 139.71, 188.73, 324.15, 78.93, 134.90, 87.48, 270.27, 92.30, 144.39, 172.38, 139.39,
            76.85, 154.46, 152.11, 156.86, 76.44, 149.57, 163.40, 155.08, 70.33, 122.78, 33.82, 102.97, 58.05, 209.38],
    "EF8": [30.28, 113.17, 331.66, 134.81, 49.78, 152.89, 221.60, 30.00, 209.89, 149.61, 85.03, 65.19, 90.42, 135.76,
            166.59, 95.65, 87.27, 116.63, 71.48, 156.90, 306.82, 149.00, 70.96, 107.87, 43.40, 119.09, 208.91, 99.81,
            30.28],
    "EF9": [16.73, 85.88, 792.12, 120.18, 781.71, 112.88, 69.98, 128.46, 327.67, 113.04, 71.54, 81.16, 80.69, 134.72,
            321.44, 134.44, 70.34, 101.29, 52.87, 106.58, 332.44],
    "EF10": [197.05, 574.47, 69.22, 128.20, 87.80, 269.27, 90.14, 154.17, 166.71, 156.17, 74.44, 85.55, 104.56, 262.52,
             82.01, 130.13, 82.82, 321.81, 212.27, 117.53, 206.71, 87.62, 48.52, 210.84],
}
SUMS = {"EF1": (1309.99, 2636.4), "EF2": (1312.72, 2614.91), "EF3": (1334.6, 2588.41), "EF4": (1586.93, 2163.91),
        "EF5": (1119.95, 2803.24), "EF6": (1291.52, 2419.84), "EF7": (1513.90, 2518.56), "EF8": (2004.37, 1626.38),
        "EF9": (2917.53, 1118.65), "EF10": (1422.24, 2498.29)}
TABLE3_MF = {"EF1": 0.43, "EF2": 0.85, "EF3": 0.47, "EF4": 0.29, "EF5": 0.55, "EF6": 0.47, "EF7": 0.61, "EF8": 0.46,
             "EF9": 0.73, "EF10": 0.77}
TABLE3_N = {"EF1": 29, "EF2": 27, "EF3": 27, "EF4": 30, "EF5": 28, "EF6": 29, "EF7": 28, "EF8": 29, "EF9": 21, "EF10": 24}
TABLE4_YIELD = {"EF1": (95, 80), "EF2": (38, 40), "EF3": (52, 50), "EF4": (75, 70), "EF5": (67, 50), "EF6": (45, 25),
                "EF7": (100, 100), "EF8": (100, 100), "EF9": (35, 50), "EF10": (25, 15)}


def sellmeier(wl_nm: np.ndarray, a1: float, a2: float, a3: float, a4: float) -> np.ndarray:
    lu2 = (np.asarray(wl_nm) / 1000.0) ** 2
    return np.sqrt(1.0 + a1 * lu2 / (lu2 - a2) + a3 * lu2 / (lu2 - a4))


def n_tio2(wl):
    k = np.interp(wl, [400, 450, 500, 550, 600], [0.0036, 0.0015, 0.0006, 0.0003, 0.0001], right=0.0)
    k = np.where(np.asarray(wl) > 600.0, 0.0, k)
    return sellmeier(wl, 4.062, 0.048857, 1.40166, 80.0) - 1j * k


def n_sio2(wl):
    return sellmeier(wl, 1.158586, 0.010727, 0.5, 61.0) + 0j


def n_suprasil(wl):
    lu2 = (np.asarray(wl) / 1000.0) ** 2  # Malitson (1965), fused silica
    return np.sqrt(1 + 0.6961663 * lu2 / (lu2 - 0.0684043 ** 2) + 0.4079426 * lu2 / (lu2 - 0.1162414 ** 2)
                   + 0.8974794 * lu2 / (lu2 - 9.896161 ** 2)) + 0j


def n_matrix(n_layers: int, wls: np.ndarray, flip: bool) -> np.ndarray:
    """(n_wls, N) complex indices, CERTUS order (index 0 = substrate side); layer 1 of the paper is TiO2."""
    cols = [n_tio2(wls) if i % 2 == 0 else n_sio2(wls) for i in range(n_layers)]
    m = np.column_stack(cols)
    return m[:, ::-1] if flip else m


FLIP = False  # set by `check`: False = their layer 1 next to the substrate


def rt(d: np.ndarray, wls: np.ndarray, angle: float, reverse: bool = False):
    """Unpolarised R, T and their Jacobians (front stack only, no back side)."""
    nm = n_matrix(len(d), wls, FLIP)
    dd = d[::-1] if FLIP else d
    out = [compute_oblique_rt_and_grads_analytic(dd, nm, n_suprasil(wls), wls, np.arange(len(d)), angle, pol,
                                                 reverse=reverse) for pol in (True, False)]
    r, t = 0.5 * (out[0][0] + out[1][0]), 0.5 * (out[0][1] + out[1][1])
    dr, dt = 0.5 * (out[0][2] + out[1][2]), 0.5 * (out[0][3] + out[1][3])
    if FLIP:
        dr, dt = dr[:, ::-1], dt[:, ::-1]
    return r, t, dr, dt, out


def residuals(d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Residual vector of their Eq. (2) in percent (MF = |r|) and its Jacobian."""
    rs, js = [], []
    for a in ANGLES:
        r, _t, dr, _dt, _o = rt(d, W_R, a)
        rs.append(100 * (r - 1) / np.sqrt(3 * len(W_R)))
        js.append(100 * dr / np.sqrt(3 * len(W_R)))
        _r, t, _dr, dt, _o = rt(d, W_T, a)
        rs.append(100 * (t - 1) / np.sqrt(3 * len(W_T)))
        js.append(100 * dt / np.sqrt(3 * len(W_T)))
    return np.concatenate(rs), np.vstack(js)


def alpha(d: np.ndarray, sigma_ot: float) -> np.ndarray:
    n650 = np.array([n_tio2(650.0).real if i % 2 == 0 else n_sio2(650.0).real for i in range(len(d))])
    return sigma_ot / n650


def plate_rt_45(d: np.ndarray, wls: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Unpolarised R, T at 45 deg with the incoherent bare back side (Macleod, thick substrate)."""
    ns = n_suprasil(wls).real
    sin_t = np.sin(np.deg2rad(45.0)) / ns
    cos_t = np.sqrt(1 - sin_t ** 2)
    cos0 = np.sqrt(1 - (ns * sin_t) ** 2)  # back in air
    rr, tt = [], []
    for pol in (True, False):
        nm = n_matrix(len(d), wls, FLIP)
        dd = d[::-1] if FLIP else d
        rf, tf, _a, _b = compute_oblique_rt_and_grads_analytic(dd, nm, n_suprasil(wls), wls, np.arange(len(d)), 45.0,
                                                               pol, reverse=False)
        rf2, tf2, _a, _b = compute_oblique_rt_and_grads_analytic(dd, nm, n_suprasil(wls), wls, np.arange(len(d)),
                                                                 45.0, pol, reverse=True)
        eta_s, eta_0 = (ns * cos_t, cos0) if pol else (ns / cos_t, 1 / cos0)
        rb = ((eta_s - eta_0) / (eta_s + eta_0)) ** 2
        den = 1 - rf2 * rb
        rr.append(rf + tf * tf2 * rb / den)
        tt.append(tf * (1 - rb) / den)
    return 0.5 * (rr[0] + rr[1]), 0.5 * (tt[0] + tt[1])


def passes(d: np.ndarray) -> bool:
    r1, _t = plate_rt_45(d, Y_R1)
    r2, _t = plate_rt_45(d, np.array([643.0]))
    _r, t = plate_rt_45(d, Y_T)
    return bool(np.all(r1 > 0.99) and r2[0] > 0.89 and np.all(t > 0.935))


def check() -> None:
    global FLIP
    for name, d in DESIGNS.items():
        d = np.array(d)
        ti, si = d[0::2].sum(), d[1::2].sum()
        assert len(d) == TABLE3_N[name], name
        assert abs(ti - SUMS[name][0]) < 0.1, (name, ti, SUMS[name])  # table values rounded to 0.01 nm
        assert abs(si - SUMS[name][1]) < 0.1, (name, si, SUMS[name])
    print("Tables 1-2: layer counts and TiO2 / SiO2 sums match the paper")
    d = np.array(DESIGNS["EF1"])
    for flip in (False, True):
        FLIP = flip
        for a in (0.0, 45.0):
            for pol in (True, False):
                wl = 620.0
                nm = n_matrix(len(d), np.array([wl]), flip)[0]
                dd = d[::-1] if flip else d
                ro, to = oracle.rt_stack_oblique(wl, list(nm), dd, a, pol, 1.0 + 0j, complex(n_suprasil(wl)))
                o = compute_oblique_rt_and_grads_analytic(dd, nm[None, :], n_suprasil(np.array([wl])), np.array([wl]),
                                                          np.arange(len(d)), a, pol, reverse=False)
                assert abs(o[0][0] - ro) < 1e-10, (a, pol, o[0][0], ro)
                assert abs(o[1][0] - to) < 1e-10, (a, pol, o[1][0], to)
        print(f"flip={flip}: CERTUS oblique kernel = oracle at 620 nm, 0 and 45 deg, s and p")
    wls = np.array([600.0, 690.0])
    for flip in (False, True):
        FLIP = flip
        r, t = plate_rt_45(np.array(DESIGNS["EF7"]), wls)
        dd = np.array(DESIGNS["EF7"])[::-1] if flip else np.array(DESIGNS["EF7"])
        ref = []
        for wl in wls:
            nm = list(n_matrix(len(dd), np.array([wl]), flip)[0])
            o = [oracle.rt_plate_incoherent(wl, nm, dd, [], [], complex(n_suprasil(wl)), 45.0, p, SUB_D_NM) for p in
                 (True, False)]
            ref.append((0.5 * (o[0][0] + o[1][0]), 0.5 * (o[0][1] + o[1][1])))
        ref = np.array(ref)
        print(f"flip={flip}: plate R,T at 45 deg (600, 690 nm) script {np.round(r, 6)}, {np.round(t, 6)}"
              f" oracle {np.round(ref[:, 0], 6)}, {np.round(ref[:, 1], 6)}")
    err = {}
    for flip in (False, True):
        FLIP = flip
        mf = {nm_: float(np.linalg.norm(residuals(np.array(dd))[0])) for nm_, dd in DESIGNS.items()}
        err[flip] = float(np.mean([abs(v - TABLE3_MF[k]) for k, v in mf.items()]))
        print(f"flip={flip}: MF " + " ".join(f"{k} {v:.2f}({TABLE3_MF[k]})" for k, v in mf.items())
              + f"  mean |MF - Table 3| {err[flip]:.3f}")
    # 2026-10-28: Table 3 is matched by the MF at 45 deg only, R and T points pooled in one mean (not Eq. 2 at 43, 45
    # and 47 deg with one mean per zone)
    FLIP = False
    t3 = {}
    for nm_, dd in DESIGNS.items():
        dd = np.array(dd)
        sq = np.sum((100 * (rt(dd, W_R, 45.0)[0] - 1)) ** 2) + np.sum((100 * (rt(dd, W_T, 45.0)[1] - 1)) ** 2)
        t3[nm_] = float(np.sqrt(sq / (len(W_R) + len(W_T))))
    ratio = np.array([t3[k] / TABLE3_MF[k] for k in t3])
    print("MF at 45 deg, pooled mean: " + " ".join(f"{k} {v:.2f}({TABLE3_MF[k]})" for k, v in t3.items())
          + f"  ratio to Table 3 {ratio.mean():.3f} +- {ratio.std():.3f}")
    best = min(err, key=err.get)
    ok = err[best] < 0.05
    (HERE / "ef2012_flip.txt").write_text(("flip" if best else "noflip") + (" OK" if ok else " MISMATCH") + "\n",
                                          encoding="utf-8")
    print(f"layer order: {'flip' if best else 'no flip'}; reproduction {'OK' if ok else 'MISMATCH (stop)'}")


def analyse(sigmas: list[float], draws: int) -> None:
    out = [f"EF1-EF10, random OT errors; Eq. (5) of Tikhonravov 2003 with alpha = sigma_OT / n; MC {draws} draws (45 deg,"
           f" back side, their corridors); FLIP={FLIP}"]
    rows = {}
    for name, d in DESIGNS.items():
        d = np.array(d)
        r, j = residuals(d)
        mf2 = float(r @ r)
        rows[name] = {"mf": np.sqrt(mf2), "yield0": passes(d)}
        for sg in sigmas:
            a = alpha(d, sg)
            rows[name][f"R{sg}"] = np.sqrt(mf2 + float(np.sum((j * a) ** 2)))
            z = np.random.default_rng((SEED, int(name[2:]), int(sg * 100))).standard_normal((draws, len(d))) * a
            ok = sum(passes(np.maximum(d + zk, 0.0)) for zk in z)
            rows[name][f"Y{sg}"] = ok / draws
        out.append(f"{name:5s} N={len(d):2d} MF {rows[name]['mf']:.3f} nominal pass {rows[name]['yield0']} | "
                   + " | ".join(f"sigma {sg}: R {rows[name][f'R{sg}']:.3f} yield {rows[name][f'Y{sg}']:.3f}"
                                for sg in sigmas)
                   + f" | paper BBM OL {TABLE4_YIELD[name][0]} LZH {TABLE4_YIELD[name][1]}")
        print(out[-1], flush=True)
    names = list(DESIGNS)
    for sg in sigmas:
        for lab, col in (("BBM OL", 0), ("BBM LZH", 1)):
            paper = [TABLE4_YIELD[n][col] for n in names]
            rho_r, p_r = spearmanr([-rows[n][f"R{sg}"] for n in names], paper)
            rho_y, p_y = spearmanr([rows[n][f"Y{sg}"] for n in names], paper)
            out.append(f"sigma {sg}: Spearman with {lab} yield: -R rho {rho_r:+.2f} (p {p_r:.2f}); MC yield rho"
                       f" {rho_y:+.2f} (p {p_y:.2f})")
        rho, _p = spearmanr([-rows[n][f"R{sg}"] for n in names], [rows[n][f"Y{sg}"] for n in names])
        out.append(f"sigma {sg}: Spearman -R against our MC yield: {rho:+.2f}")
    (HERE / "ef2012_analyse.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out[-3 * len(sigmas):]))


def polish(name: str, sigma: float, draws: int) -> None:
    d0 = np.array(DESIGNS[name])
    a = alpha(d0, sigma)
    h = 1e-3

    def stacked(d):
        r, j = residuals(d)
        dj = np.empty((j.shape[0], len(d), len(d)))
        for k in range(len(d)):
            e = np.zeros(len(d))
            e[k] = h
            dj[:, :, k] = (residuals(d + e)[1] - residuals(d - e)[1]) / (2 * h) * a
        return np.concatenate([r, (j * a).T.ravel()]), np.vstack([j, dj.transpose(1, 0, 2).reshape(-1, len(d))])

    memo: dict = {}

    def get(x):
        key = x.tobytes()
        if key not in memo:
            memo.clear()
            memo[key] = stacked(x)
        return memo[key]

    sol = least_squares(lambda x: get(x)[0], d0, jac=lambda x: get(x)[1], bounds=(FLOOR, np.inf), method="trf",
                        x_scale="jac", max_nfev=200)
    d1 = np.maximum(sol.x, FLOOR)
    out = [f"robust polish of {name} (their Eq. 5, alpha = {sigma} nm OT / n, floor {FLOOR} nm, {sol.nfev} evaluations)"]
    for lab, d in (("before", d0), ("after", d1)):
        r, j = residuals(d)
        rr = np.sqrt(float(r @ r) + float(np.sum((j * a) ** 2)))
        z = np.random.default_rng((SEED + 1, int(name[2:]))).standard_normal((draws, len(d))) * a
        ys = np.mean([passes(np.maximum(d + zk, 0.0)) for zk in z])
        out.append(f"   {lab:6s}: MF {np.linalg.norm(r):.3f}  R {rr:.3f}  nominal pass {passes(d)}  MC yield"
                   f" {ys:.3f} ({draws} fresh draws)  thinnest {d.min():.1f} nm")
    out.append("   d_nm " + " ".join(f"{v:.2f}" for v in d1))
    with (HERE / "ef2012_polish.txt").open("a", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    if sys.argv[1] == "check":
        check()
    else:
        FLIP = sys.argv[-1] == "flip"
        args = [v for v in sys.argv[2:] if v != "flip"]
        if sys.argv[1] == "analyse":
            analyse([float(v) for v in args[0].split(",")], int(args[1]))
        else:
            polish(args[0], float(args[1]), int(args[2]))
