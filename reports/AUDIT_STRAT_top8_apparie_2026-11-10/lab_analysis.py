"""Paired judgment, on the holdout draws, of the plans a local-search lab produced.

    python reports/AUDIT_STRAT_top8_apparie_2026-11-10/lab_analysis.py [DRAWS.npz] [REFERENCE]

Defaults: ls_lab_draws.npz next to this file, reference plan `prod`. For every plan and corridor: the SEEL on the
pooled holdout draws, and its difference to the reference with a paired bootstrap (the same (seed, draw) resampled for
both plans and every noise level). Prints, writes nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
B = 4000


def seel_of(x):
    """SEEL on (..., levels, draws): 2*sqrt(max over the levels of the P95)."""
    return 2.0 * np.sqrt(np.percentile(x, 95, axis=-1).max(axis=-1))


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "ls_lab_draws.npz"
    ref_name = sys.argv[2] if len(sys.argv) > 2 else "prod"
    with np.load(path) as z:
        data = {k: z[k] for k in z.files}
    names = list(dict.fromkeys(k.split("__")[0] for k in data))
    corridors = list(dict.fromkeys(k.split("__")[1] for k in data))
    rng = np.random.default_rng(20261110)
    print(f"{path.name} : plans {names}, référence {ref_name}")
    for corr in corridors:
        ref = data[f"{ref_name}__{corr}__rmse"]  # (seeds, levels, draws)
        n_lv = ref.shape[1]
        pooled_ref = ref.transpose(1, 0, 2).reshape(n_lv, -1)
        n = pooled_ref.shape[1]
        idx = rng.integers(0, n, size=(B, n))
        boot_ref = seel_of(pooled_ref[:, idx].transpose(1, 0, 2))
        print(
            f"\n--- corridor {corr} : {n} tirages par niveau, SEEL de {ref_name} {seel_of(pooled_ref):.4f} nm "
            f"(écart-type bootstrap {boot_ref.std():.4f}) ---"
        )
        for name in names:
            if name == ref_name:
                continue
            rm = data[f"{name}__{corr}__rmse"]
            st = data[f"{name}__{corr}__stopped"]
            pooled = rm.transpose(1, 0, 2).reshape(n_lv, -1)
            d = float(seel_of(pooled) - seel_of(pooled_ref))
            boot = seel_of(pooled[:, idx].transpose(1, 0, 2)) - boot_ref
            lo, hi = np.percentile(boot, [2.5, 97.5])
            sd = float(boot.std())
            print(
                f"{name:14s} SEEL {seel_of(pooled):.4f} nm | écart {d:+.4f} nm ({d / seel_of(pooled_ref):+.1%}) | "
                f"sigma apparié {sd:.4f} | z = {d / sd if sd > 0 else 0.0:+.1f} | IC95 [{lo:+.4f}, {hi:+.4f}] | "
                f"P(meilleur que {ref_name}) {np.mean(boot < 0):.3f} | arrêts {int(st.sum())}/{st.size}"
            )


if __name__ == "__main__":
    main()
