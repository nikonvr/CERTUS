from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from certus.spline.certus_index_spline_core import (
    SIGMA_KNOTS_MIN_SEP_REL,
    n_lambda_rising_with_wavelength_penalty,
)
from certus.spline.spline_objective import (
    sigma_knots_decode,
    _interpolate_along_sigma,
    _cached_cubic_interp_matrix_inner,
)
from certus.spline.spline_smart_init import interp_n_L_pwlnk_to_sigmas


def bench(label: str, fn, n_iter: int = 200) -> tuple[float, object]:
    t0 = time.perf_counter()
    out = None
    for _ in range(n_iter):
        out = fn()
    dt = time.perf_counter() - t0
    return dt, out


def n_lambda_penalty_old(cfg, sk, nn) -> float:
    w = float(getattr(cfg, "n_lambda_rising_penalty_weight", 0.0) or 0.0)
    band = getattr(cfg, "n_lambda_rising_penalty_band_nm", None)
    slack = float(getattr(cfg, "n_lambda_rising_penalty_slack", 0.0) or 0.0)
    if slack < 0.0:
        slack = 0.0
    if w <= 0.0 or band is None:
        return 0.0
    lam_lo = float(min(float(band[0]), float(band[1])))
    lam_hi = float(max(float(band[0]), float(band[1])))
    sk = np.asarray(sk, dtype=np.float64).ravel()
    nn = np.asarray(nn, dtype=np.float64).ravel()
    if sk.size < 2 or nn.size != sk.size:
        return 0.0
    acc = 0.0
    eps = 1e-12
    for j in range(sk.size - 1):
        s0, s1 = float(sk[j]), float(sk[j + 1])
        if s1 <= s0 + eps:
            continue
        lam_min_seg = 1.0 / s1
        lam_max_seg = 1.0 / s0
        seg_lo = min(lam_min_seg, lam_max_seg)
        seg_hi = max(lam_min_seg, lam_max_seg)
        if seg_hi < lam_lo or seg_lo > lam_hi:
            continue
        viol = float(nn[j]) - float(nn[j + 1])
        if viol > eps:
            ve = max(0.0, viol - slack)
            acc += ve * ve
    return w * acc


def interp_n_L_old(sk, sn, sL, sig_t):
    sk = np.asarray(sk, dtype=np.float64).ravel()
    sn = np.asarray(sn, dtype=np.float64).ravel()
    sL = np.asarray(sL, dtype=np.float64).ravel()
    order = np.argsort(sk)
    sk_s = sk[order]
    sn_s = sn[order]
    sL_s = sL[order]
    sig_t = np.asarray(sig_t, dtype=np.float64).ravel()
    n_out = np.empty(sig_t.shape, dtype=np.float64)
    L_out = np.empty(sig_t.shape, dtype=np.float64)
    s0 = float(sk_s[0])
    s1m = float(sk_s[-1])

    for i in range(int(sig_t.size)):
        s = float(sig_t[i])
        d = np.abs(sk_s - s)
        j = int(np.argmin(d))
        tol = 1e-14 + 1e-9 * max(abs(s), abs(float(sk_s[j])), 1e-30)
        if float(d[j]) <= tol:
            n_out[i] = float(sn_s[j])
            L_out[i] = float(sL_s[j])
        elif s <= s0:
            if sk_s.size >= 2:
                den = float(sk_s[1] - sk_s[0])
                if abs(den) < 1e-30:
                    n_out[i] = float(sn_s[0])
                    L_out[i] = float(sL_s[0])
                else:
                    t = (s - s0) / den
                    n_out[i] = float(sn_s[0] + t * (sn_s[1] - sn_s[0]))
                    L_out[i] = float(sL_s[0] + t * (sL_s[1] - sL_s[0]))
            else:
                n_out[i] = float(sn_s[0])
                L_out[i] = float(sL_s[0])
        elif s >= s1m:
            if sk_s.size >= 2:
                den = float(sk_s[-1] - sk_s[-2])
                if abs(den) < 1e-30:
                    n_out[i] = float(sn_s[-1])
                    L_out[i] = float(sL_s[-1])
                else:
                    t = (s - s1m) / den
                    n_out[i] = float(sn_s[-1] + t * (sn_s[-1] - sn_s[-2]))
                    L_out[i] = float(sL_s[-1] + t * (sL_s[-1] - sL_s[-2]))
            else:
                n_out[i] = float(sn_s[-1])
                L_out[i] = float(sL_s[-1])
        else:
            n_out[i] = float(np.interp(s, sk_s, sn_s))
            L_out[i] = float(np.interp(s, sk_s, sL_s))
    return n_out, L_out


def sigma_knots_decode_old(raw, s_lo, s_hi, eps_s):
    ww = np.exp(np.clip(raw, -20.0, 20.0))
    sw = np.sum(ww)
    if not np.isfinite(sw) or sw <= 0.0:
        ww = np.ones_like(raw)
        sw = float(ww.size)
    ds = (ww / sw) * (s_hi - s_lo)
    c = s_lo + np.cumsum(ds)
    sk = np.concatenate(([s_lo], c[:-1], [s_hi]))
    sk[1:] = np.maximum(sk[1:], sk[:-1] + eps_s)
    sk[-1] = s_hi
    return sk


def main() -> int:
    rng = np.random.default_rng(20260426)

    # 1) n(lambda) rising penalty
    class Cfg:
        n_lambda_rising_penalty_weight = 2.5
        n_lambda_rising_penalty_band_nm = (250.0, 2500.0)
        n_lambda_rising_penalty_slack = 0.003

    cfg = Cfg()
    k = 128
    sk = np.sort(rng.uniform(1.0 / 2500.0, 1.0 / 250.0, size=k))
    nn = np.clip(1.5 + np.cumsum(rng.normal(0.0, 0.01, size=k)), 1.0, 3.5)

    dt_old, out_old = bench("pen_old", lambda: n_lambda_penalty_old(cfg, sk, nn), n_iter=6000)
    dt_new, out_new = bench("pen_new", lambda: n_lambda_rising_with_wavelength_penalty(cfg, sk, nn), n_iter=6000)

    # 2) interp_n_L
    k_src = 64
    k_tgt = 96
    sk_src = np.sort(rng.uniform(1.0 / 3000.0, 1.0 / 220.0, size=k_src))
    n_src = np.clip(1.4 + rng.normal(0.0, 0.05, size=k_src), 1.0, 3.5)
    L_src = np.log(np.clip(1e-3 + rng.random(k_src) * 0.2, 1e-9, None))
    sig_tgt = np.sort(rng.uniform(sk_src.min() * 0.95, sk_src.max() * 1.05, size=k_tgt))

    dt_old_i, out_old_i = bench("interp_old", lambda: interp_n_L_old(sk_src, n_src, L_src, sig_tgt), n_iter=4000)
    dt_new_i, out_new_i = bench(
        "interp_new",
        lambda: interp_n_L_pwlnk_to_sigmas(sk_src, n_src, L_src, sig_tgt),
        n_iter=4000,
    )

    # 3) sigma_knots_decode
    raw = rng.normal(0.0, 1.0, size=80)
    s_lo = 1.0 / 2600.0
    s_hi = 1.0 / 260.0
    work = {}

    eps_s = max(1e-10, SIGMA_KNOTS_MIN_SEP_REL * max(s_hi - s_lo, 1e-12))
    dt_old_d, out_old_d = bench("decode_old", lambda: sigma_knots_decode_old(raw, s_lo, s_hi, eps_s), n_iter=10000)
    dt_new_d, out_new_d = bench("decode_new", lambda: sigma_knots_decode(raw, s_lo, s_hi, eps_s=eps_s), n_iter=10000)
    dt_new_dw, out_new_dw = bench(
        "decode_new_work",
        lambda: sigma_knots_decode(raw, s_lo, s_hi, eps_s=eps_s, work=work, reuse_output=True),
        n_iter=10000,
    )

    # 4) CubicSpline cache effect
    _cached_cubic_interp_matrix_inner.cache_clear()
    sig = np.sort(rng.uniform(s_lo, s_hi, size=1200))
    sk4 = np.sort(rng.uniform(s_lo, s_hi, size=12))
    vals = np.clip(1.7 + rng.normal(0.0, 0.03, size=12), 1.0, 3.5)

    t0 = time.perf_counter()
    cold = _interpolate_along_sigma(sig, sk4, vals, "smooth")
    t_cold = time.perf_counter() - t0

    t1 = time.perf_counter()
    for _ in range(500):
        _interpolate_along_sigma(sig, sk4, vals, "smooth")
    t_warm = time.perf_counter() - t1

    # Consistency checks
    n_eq = np.allclose(out_old_i[0], out_new_i[0], atol=1e-12, rtol=1e-12)
    L_eq = np.allclose(out_old_i[1], out_new_i[1], atol=1e-12, rtol=1e-12)
    d_eq = np.allclose(out_old_d, out_new_d, atol=1e-12, rtol=1e-12)

    print("=== spline microbench ===")
    print(f"penalty old/new: {dt_old:.4f}s / {dt_new:.4f}s | speedup x{dt_old/max(dt_new,1e-12):.2f} | equal={abs(out_old-out_new) < 1e-12}")
    print(f"interp old/new:  {dt_old_i:.4f}s / {dt_new_i:.4f}s | speedup x{dt_old_i/max(dt_new_i,1e-12):.2f} | n_eq={n_eq} L_eq={L_eq}")
    print(f"decode old/new:  {dt_old_d:.4f}s / {dt_new_d:.4f}s | speedup x{dt_old_d/max(dt_new_d,1e-12):.2f} | eq={d_eq}")
    print(f"decode new/new(work): {dt_new_d:.4f}s / {dt_new_dw:.4f}s | speedup x{dt_new_d/max(dt_new_dw,1e-12):.2f}")
    print(f"cubic cache: cold_once={t_cold*1e3:.3f} ms | warm_500={t_warm*1e3:.3f} ms | avg_warm={(t_warm/500.0)*1e3:.4f} ms")
    print(f"cubic sample checksum={float(np.sum(cold)):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
