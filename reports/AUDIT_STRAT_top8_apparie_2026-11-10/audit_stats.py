"""Independent statistical checks for the CERTUS-STRAT audit. TOY MODEL, not CERTUS: no CERTUS code is imported.

Toy: spectral deviation = J_idx @ x + level * J_thk @ e ; RMSE = ||.|| / sqrt(m)
  x (4,) : index corridor draw per run, (aH, bH, aL, bL), same law as CERTUS (z ~ N(0,1/3) clipped +-1, b = z2 (1-|z1|))
  e (48,): per-layer stop noise, N(0,1/3) clipped +-1
`share` = part of mean RMSE^2 carried by the level-dependent noise at level 1.
"""

import math
import sys

import numpy as np
from scipy.stats import beta, norm, qmc

rng = np.random.default_rng(20261110)
M, NL = 60, 48


def tn(size, r=rng):
    return np.clip(r.normal(0.0, 1.0 / 3.0, size), -1.0, 1.0)


def corridor(n, r=rng, u=None):
    if u is None:
        z = tn((n, 4), r)
    else:
        z = np.clip(norm.ppf(u, scale=1.0 / 3.0), -1.0, 1.0)
    x = np.empty((n, 4))
    x[:, 0] = z[:, 0]
    x[:, 1] = z[:, 1] * (1 - np.abs(z[:, 0]))
    x[:, 2] = z[:, 2]
    x[:, 3] = z[:, 3] * (1 - np.abs(z[:, 2]))
    return x


def make_J(share, r):
    Ji = r.normal(size=(M, 4))
    Jt = r.normal(size=(M, NL))
    x = corridor(200000, r)
    e = tn((200000, NL), r)
    si = np.mean(np.sum((x @ Ji.T) ** 2, axis=1))
    st = np.mean(np.sum((e @ Jt.T) ** 2, axis=1))
    Jt *= math.sqrt(share / (1 - share) * si / st)
    return Ji, Jt


def rmse(Ji, Jt, x, e, level=1.0):
    d = x @ Ji.T + level * (e @ Jt.T)
    return np.sqrt(np.mean(d * d, axis=-1))


def section(t):
    print("\n=== " + t + " ===")


LEVELS = (0.5, 1.0, 2.0)
REPS = 4000

for share in (0.05, 0.31):
    jr = np.random.default_rng(7)
    Ji, Jt = make_J(share, jr)
    big = {lv: rmse(Ji, Jt, corridor(400000), tn((400000, NL)), lv) for lv in LEVELS}
    true_p95 = {lv: float(np.percentile(big[lv], 95)) for lv in LEVELS}
    true_score = max(true_p95.values())
    section(f"noise share of mean RMSE^2 at level 1 = {share:.0%}")
    print(
        "true P95 by level (0.5,1,2):",
        [round(true_p95[lv] / true_p95[1.0], 4) for lv in LEVELS],
        "(relative to level 1)",
    )
    for N in (150, 300):
        p95 = np.empty((REPS, 3))
        pooled = np.empty(REPS)
        for k in range(REPS):
            rs = []
            for j, lv in enumerate(LEVELS):
                r_ = rmse(Ji, Jt, corridor(N), tn((N, NL)), lv)
                p95[k, j] = np.percentile(r_, 95)
                rs.append(r_)
            # pooled alternative: ONE corridor draw set shared by the 3 levels would be CRN; here simply pool level 1 x3
            pooled[k] = np.percentile(rmse(Ji, Jt, corridor(3 * N), tn((3 * N, NL)), 2.0), 95)
        mx = p95.max(axis=1)
        print(
            f"N={N}: rel. SD of one P95 (level 1) = {p95[:, 1].std() / true_p95[1.0]:.3f} | "
            f"max-of-3: bias = {mx.mean() / true_score - 1:+.3f}, rel. SD = {mx.std() / true_score:.3f} | "
            f"P95 at level 2 on 3N draws: bias = {pooled.mean() / true_p95[2.0] - 1:+.3f}, rel. SD = {pooled.std() / true_p95[2.0]:.3f} | "
            f"argmax level freq (0.5,1,2) = {np.round(np.bincount(p95.argmax(axis=1), minlength=3) / REPS, 2)}"
        )

# ---------------------------------------------------------------- ordering power
section("ordering power: B truly better than A (noise share 5 %)")
jr = np.random.default_rng(7)
JiA, JtA = make_J(0.05, jr)
for gain, eta in ((0.05, 0.3), (0.05, 0.6), (0.10, 0.3)):
    pr = np.random.default_rng(11)
    JiB = JiA + eta * pr.normal(size=JiA.shape)
    JtB = JtA + eta * pr.normal(size=JtA.shape) * np.abs(JtA).mean()
    xb, eb = corridor(400000), tn((400000, NL))
    sA = max(np.percentile(rmse(JiA, JtA, xb, eb, lv), 95) for lv in LEVELS)
    sB0 = max(np.percentile(rmse(JiB, JtB, xb, eb, lv), 95) for lv in LEVELS)
    scale = (1 - gain) * sA / sB0
    JiB, JtB = JiB * scale, JtB * scale
    rA, rB = rmse(JiA, JtA, xb, eb), rmse(JiB, JtB, xb, eb)
    rho = np.corrcoef(rA, rB)[0, 1]
    mean2 = np.mean(rB**2) / np.mean(rA**2) - 1
    for N in (150, 300):
        ok = np.zeros(5)
        for _ in range(REPS):
            # code-like: independent draws per level, common across strategies (CRN)
            a, b = [], []
            for lv in LEVELS:
                x, e = corridor(N), tn((N, NL))
                a.append(rmse(JiA, JtA, x, e, lv))
                b.append(rmse(JiB, JtB, x, e, lv))
            ok[0] += max(np.percentile(v, 95) for v in b) < max(np.percentile(v, 95) for v in a)
            ok[1] += np.mean(b[1] ** 2 - a[1] ** 2) < 0  # paired mean RMSE^2, nominal level, N draws
            ok[2] += np.mean(np.concatenate(b) ** 2 - np.concatenate(a) ** 2) < 0  # same, 3N draws pooled
            # no CRN: B on fresh draws
            b2 = [rmse(JiB, JtB, corridor(N), tn((N, NL)), lv) for lv in LEVELS]
            ok[3] += max(np.percentile(v, 95) for v in b2) < max(np.percentile(v, 95) for v in a)
            # P95 on pooled 3N, CRN
            ok[4] += np.percentile(np.concatenate(b), 95) < np.percentile(np.concatenate(a), 95)
        ok /= REPS
        print(
            f"true gain {gain:.0%} on score (mean RMSE^2 {mean2:+.1%}), corr(rmseA, rmseB) = {rho:.2f}, N={N}: "
            f"P(correct order) max-P95 CRN = {ok[0]:.2f} | max-P95 no CRN = {ok[3]:.2f} | pooled-3N P95 CRN = {ok[4]:.2f} | "
            f"paired mean RMSE^2 (N) = {ok[1]:.2f} | paired mean RMSE^2 (3N) = {ok[2]:.2f}"
        )

# ---------------------------------------------------------------- screening at 25 draws
section("screening: 30 candidates, the best one truly 5 % / 10 % better, keep 10 on P95 of n draws (CRN)")
for gain in (0.05, 0.10):
    for n in (25, 50, 100):
        kept = 0
        R = 1500
        pr = np.random.default_rng(5)
        cands = []
        for _ in range(30):
            Ji = JiA + 0.3 * pr.normal(size=JiA.shape)
            Jt = JtA + 0.3 * pr.normal(size=JtA.shape) * np.abs(JtA).mean()
            cands.append((Ji, Jt))
        xb, eb = corridor(200000), tn((200000, NL))
        true = np.array([np.percentile(rmse(Ji, Jt, xb, eb), 95) for Ji, Jt in cands])
        # equalise all, then make candidate 0 better by `gain`
        cands = [(Ji * true.mean() / t, Jt * true.mean() / t) for (Ji, Jt), t in zip(cands, true, strict=True)]
        cands[0] = (cands[0][0] * (1 - gain), cands[0][1] * (1 - gain))
        for _ in range(R):
            x, e = corridor(n), tn((n, NL))
            s = np.array([np.percentile(rmse(Ji, Jt, x, e), 95) for Ji, Jt in cands])
            kept += np.argsort(s).tolist().index(0) < 10
        print(f"gain {gain:.0%}, n = {n}: P(best candidate kept in top 10 of 30) = {kept / R:.2f}  (chance level 0.33)")

# ---------------------------------------------------------------- crash gate & rare events
section("crash gate (point estimate, reject when crashes/N >= 5 %) and rare events")
from scipy.stats import binom

for N in (25, 50, 150, 300):
    kmin = math.ceil(0.05 * N - 1e-12)
    print(
        f"N={N}: rejects from {kmin} crash(es); P(reject | true 1 %) = {binom.sf(kmin - 1, N, 0.01):.3f}, "
        f"| true 3 % = {binom.sf(kmin - 1, N, 0.03):.3f}; P(accept | true 8 %) = {binom.cdf(kmin - 1, N, 0.08):.3f}; "
        f"0 crash seen -> p < {beta.ppf(0.95, 1, N):.4f} (95 %)"
    )
print(
    "draws needed to see 0 crash and conclude p < 0.5 % / 0.1 % at 95 %:",
    math.ceil(math.log(0.05) / math.log(1 - 0.005)),
    "/",
    math.ceil(math.log(0.05) / math.log(1 - 0.001)),
)

# ---------------------------------------------------------------- SEEL class width
section("SEEL = 2 sqrt(score): relative width in RMSE of the 0.01 nm equality class")
for seel in (0.17, 0.25, 0.35, 0.47, 0.60):
    s0 = (seel / 2) ** 2
    s1 = ((seel + 0.01) / 2) ** 2
    print(
        f"SEEL {seel:.2f} nm -> score {s0:.4f}; class = +{s1 / s0 - 1:.1%} in score; linear k=95.4 -> {95.4 * s0:.2f} nm"
    )

# ---------------------------------------------------------------- false turning points
section(
    "false TP by noise alone on a FLAT signal: P(running max - reading > h*A at least once in n readings), noise N(0,A/3) clipped +-A"
)
for h in (1.66, 2.0):
    for n in (3, 5, 10, 21):
        r = tn((500_000, n))
        runmax = np.maximum.accumulate(r, axis=1)
        runmin = np.minimum.accumulate(r, axis=1)
        hit = np.any((runmax - r > h) | (r - runmin > h), axis=1)
        print(f"h = {h}: n = {n:2d} readings -> {hit.mean():.2e}")

# ---------------------------------------------------------------- QMC on the 4 index dimensions
section(
    "variance of the P95 estimator: index draws iid vs scrambled Sobol on the 4 corridor dimensions (noise share 5 %)"
)
Ji, Jt = JiA, JtA
tp = float(np.percentile(rmse(Ji, Jt, corridor(400000), tn((400000, NL))), 95))
for N in (128, 256):
    a = np.empty(2000)
    b = np.empty(2000)
    c = np.empty(2000)
    for k in range(2000):
        e = tn((N, NL))
        a[k] = np.percentile(rmse(Ji, Jt, corridor(N), e), 95)
        u = qmc.Sobol(d=4, scramble=True, seed=int(rng.integers(1 << 30))).random(N)
        b[k] = np.percentile(rmse(Ji, Jt, corridor(N, u=np.clip(u, 1e-12, 1 - 1e-12)), e), 95)
        u2 = qmc.LatinHypercube(d=4, seed=int(rng.integers(1 << 30))).random(N)
        c[k] = np.percentile(rmse(Ji, Jt, corridor(N, u=u2), e), 95)
    print(
        f"N={N}: rel. SD of P95: iid {a.std() / tp:.3f} | Sobol-4D {b.std() / tp:.3f} | LHS-4D {c.std() / tp:.3f}; "
        f"same for mean RMSE^2: n/a here"
    )

# ---------------------------------------------------------------- winner's curse
section("optimism of the best-of-K observed score when all K are truly equal (idiosyncratic rel. noise s)")
for s in (0.03, 0.055):
    for K in (10, 30, 241):
        z = np.random.default_rng(3).normal(size=(200000, K)).min(axis=1).mean()
        print(f"s = {s:.1%}, K = {K}: expected best observed = {z * s:+.1%} below truth")
print("\npython", sys.version.split()[0], "numpy", np.__version__)
