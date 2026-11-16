"""C < 2 E0 must keep its bits when the branch C >= 2 E0 is added to the Tauc-Lorentz eps1 kernels.
    set NUMBA_CACHE_DIR=<empty dir> & python reports/nuit_2026-11-16/preuves/p_eps1_bits.py run before.npz
    python reports/nuit_2026-11-16/preuves/p_eps1_bits.py compare before.npz after.npz
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def run(out: str) -> None:
    from certus.physics.certus_optical_models import epsilon1_TL_analytic
    from certus.physics.gradient_analytic import _compute_epsilon1_gradient_kernel

    rng = np.random.default_rng(7)
    arrays = {}
    for j in range(60):
        Eg = float(rng.uniform(0.5, 6.0))
        E0 = float(rng.uniform(Eg + 0.1, 10.0))
        C = float(rng.uniform(0.1, min(10.0, 2.0 * E0 - 0.01)))
        A, eps_inf = float(rng.uniform(10.0, 2000.0)), float(rng.uniform(1.0, 10.0))
        E = np.sort(rng.uniform(0.1, 9.0, 200))
        arrays[f"eps1_{j}"] = epsilon1_TL_analytic(E, Eg, A, E0, C, eps_inf)
        arrays[f"grad_{j}"] = _compute_epsilon1_gradient_kernel(E, Eg, A, E0, C, eps_inf)
    np.savez(out, **arrays)
    print(f"{out}: {len(arrays)} arrays")


def compare(a: str, b: str) -> None:
    A, B = np.load(a), np.load(b)
    differ = [k for k in A.files if not np.array_equal(A[k].view(np.uint64), B[k].view(np.uint64))]
    print(f"ARRAYS={len(A.files)} DIFFER={len(differ)} {differ[:6]}")


if __name__ == "__main__":
    {"run": lambda: run(sys.argv[2]), "compare": lambda: compare(sys.argv[2], sys.argv[3])}[sys.argv[1]]()
