"""Chantier 46: do the three real copies of the reflection formula give the same bits once they delegate to
`reflection_amplitudes`? `scripts/c1_diff.py` does not call them (FIELD, needle scan, METAL bilayer).

Run once before the change and once after, each in a fresh interpreter with an empty Numba cache, then compare:
    set NUMBA_CACHE_DIR=<empty dir> & python reports/nuit_2026-11-16/preuves/p_46_bits.py run before.npz
    set NUMBA_CACHE_DIR=<other empty dir> & python reports/nuit_2026-11-16/preuves/p_46_bits.py run after.npz
    python reports/nuit_2026-11-16/preuves/p_46_bits.py compare before.npz after.npz
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def _cases(seed: int):
    rng = np.random.default_rng(seed)
    return rng


def run(out: str) -> None:
    from certus.core.certus_field_core import _calculate_field_single_pol
    from certus.physics.certus_opt_needle import needle_scan_cached
    from certus.physics.certus_opt_tmm import calculate_reflectance_bilayer_vectorized

    arrays: dict[str, np.ndarray] = {}
    for seed in range(12):
        rng = _cases(seed)
        W = 120
        lam = np.sort(rng.uniform(300.0, 1600.0, W))
        nM = rng.uniform(0.1, 4.0, W) - 1j * rng.uniform(0.0, 6.0, W)
        if seed % 3 == 0:
            nM = np.conj(nM)  # n + ik on input: the kernel's own safeguard flips it
        nL = rng.uniform(1.4, 1.5, W) - 1j * rng.uniform(0.0, 1e-3, W)
        nS = rng.uniform(3.4, 4.2, W) - 1j * rng.uniform(0.0, 0.5, W)
        arrays[f"bilayer_{seed}"] = calculate_reflectance_bilayer_vectorized(
            lam, nM.astype(np.complex128), float(rng.uniform(1, 60)), float(rng.uniform(0, 400)), nL.astype(np.complex128), nS.astype(np.complex128)
        )

        N = int(rng.integers(2, 12))
        Wn = 60
        wls = np.sort(rng.uniform(400.0, 900.0, Wn))
        hi, lo = 2.3 - 1j * rng.uniform(0, 1e-3), 1.46 - 0j
        n_layers = np.array([[hi if j % 2 == 0 else lo for j in range(N)] for _ in range(Wn)], dtype=np.complex128)
        n_needle = np.array([[lo if j % 2 == 0 else hi for j in range(N)] for _ in range(Wn)], dtype=np.complex128)
        n_sub = np.full(Wn, 1.52 - 1j * (1e-6 if seed % 2 else 0.0), dtype=np.complex128)
        ep = rng.uniform(40.0, 200.0, N)
        tgt = rng.uniform(0.0, 1.0, Wn)
        wts = rng.uniform(0.5, 1.5, Wn)
        mask = np.ones(N, dtype=np.int64)
        layer, depth, cost = needle_scan_cached(wls, n_layers, n_needle, n_sub, ep, tgt, wts, 2.0, 5.0, mask)
        arrays[f"needle_{seed}"] = np.array([float(layer), float(depth), float(cost)])

        idx = np.array([2.3 - 1e-4j if j % 2 == 0 else 1.46 + 0j for j in range(N)], dtype=np.complex128)
        for pol in (False, True):
            for theta in (0.0, 0.5):
                res = _calculate_field_single_pol(idx, ep.copy(), 1.52, float(rng.uniform(400, 900)), 1.0, 30, theta, pol)
                for k, a in enumerate(res):
                    arrays[f"field_{seed}_{int(pol)}_{theta}_{k}"] = np.atleast_1d(np.asarray(a))
    np.savez(out, **arrays)
    print(f"{out}: {len(arrays)} arrays")


def _bits(a: np.ndarray) -> np.ndarray:
    a = np.ascontiguousarray(a)
    if np.iscomplexobj(a):
        a = a.view(np.float64)
    return a.astype(np.float64).view(np.uint64)


def compare(a: str, b: str) -> None:
    A, B = np.load(a), np.load(b)
    keys = sorted(set(A.files) | set(B.files))
    differ = [k for k in keys if k not in A.files or k not in B.files or A[k].shape != B[k].shape or not np.array_equal(_bits(A[k]), _bits(B[k]))]
    families: dict[str, int] = {}
    for k in differ:
        families[k.split("_")[0]] = families.get(k.split("_")[0], 0) + 1
    print(f"ARRAYS={len(keys)} DIFFER={len(differ)} {families}")
    for k in differ[:10]:
        x, y = A[k].astype(complex).ravel(), B[k].astype(complex).ravel()
        print(f"  {k}: max |diff| {float(np.max(np.abs(x - y))):.3e}")


if __name__ == "__main__":
    {"run": lambda: run(sys.argv[2]), "compare": lambda: compare(sys.argv[2], sys.argv[3])}[sys.argv[1]]()
