"""SONDE VITESSE : le cout d'UN appel des noyaux de DESIGN, selon le nombre de fils Numba.

    python scripts/probe_kernel_threads.py [--config FICHIER] [--calls 3000] [--out FICHIER.json]

## POURQUOI

Audit de vitesse du 2026-11-13 (reports/audits_2026-11-13). Les noyaux de cout et de gradient de DESIGN bouclent en
`prange` sur les longueurs d'onde. Sur un petit probleme (une centaine de longueurs d'onde, quelques dizaines de
couches), lancer une region parallele peut couter plus que le calcul : la question est mesurable et ne l'avait pas ete
(ALG-23 du registre le dit en passant : « chaque evaluation n'occupant que ~140 longueurs d'onde sur 8 fils »).

## CE QU'ELLE FAIT

Elle charge l'exemple de DESIGN dans la fenetre (hors ecran), prend sa grille d'optimisation, sa pile et ses cibles,
puis chronometre, pour 1, 2, 4, 8 fils et le maximum :

- `cost_lossless_front_fast` et `compute_gradient_lossless_front_fast` : les noyaux reels de la recherche globale ;
- `cost_numba_fast` et `compute_gradient_all_layers_analytic` : les noyaux complexes generiques.

Chaque mesure : `--calls` appels apres un appel d'amorce (compilation), meilleure de 5 repetitions, en microsecondes
par appel. Elle rejoue aussi les noyaux sur une grille 10 fois plus dense, ou le parallelisme doit gagner.

🔴 Une machine, un exemple : les rapports valent, pas les microsecondes (CLAUDE.md §4, « les durees ne valent que sur
leur machine »). Rien d'autre ne doit tourner pendant la mesure.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from functools import partial
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def _chrono(f, calls: int) -> float:
    """Microsecondes par appel : la meilleure de 5 repetitions de `calls` appels."""
    f()
    meilleur = float("inf")
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(calls):
            f()
        meilleur = min(meilleur, (time.perf_counter() - t0) / calls)
    return 1e6 * meilleur


def main() -> int:
    ap = argparse.ArgumentParser(description="Cout d'un appel des noyaux de DESIGN selon le nombre de fils Numba.")
    ap.add_argument("--config", type=Path, default=ROOT / "example" / "example_design" / "JSON-design-example.json")
    ap.add_argument("--calls", type=int, default=3000)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import numba
    import numpy as np
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])  # noqa: F841  (la fenetre en a besoin)
    from _artefact import ecrire_json

    from certus.core.certus_core import ensure_numba_cache_dir

    ensure_numba_cache_dir()
    from certus.physics.design_fast_normal import (
        compute_gradient_lossless_front_fast,
        cost_lossless_front_fast,
        prepare_normal_fast_context,
    )
    from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic
    from certus.physics.gradient_utils import cost_numba_fast
    from certus.ui.certus_design_ui import CertusDesignApp
    from certus_physics import prepare_targets_vectorized

    win = CertusDesignApp()
    win.load_config(str(a.config))
    win._update_thickness_display()
    mats, stack = win._get_materials(), win._get_front_stack()
    tgts = [t for t in win._get_tgts() if t.valid()]
    ep = np.ascontiguousarray(win.ep_current, dtype=np.float64)
    var_idx = np.arange(len(ep), dtype=np.int64)
    sub = "Substrate" if "Substrate" in mats else next(k for k in mats if k.lower() == "substrate")
    no_back_d = np.zeros(0, dtype=np.float64)
    grille = np.asarray(win._get_optim_wls(), dtype=np.float64)
    dense = np.linspace(grille.min(), grille.max(), 10 * len(grille))
    fils = sorted({n for n in (1, 2, 4, 8, numba.config.NUMBA_NUM_THREADS) if n <= numba.config.NUMBA_NUM_THREADS})
    sortie: dict = {"config": a.config.name, "layers": len(ep), "calls": a.calls, "threads_max": numba.config.NUMBA_NUM_THREADS,
                    "threading_layer": None, "grids": {}}

    for nom, wls in (("optimisation", grille), ("dense_x10", dense)):
        wls = np.ascontiguousarray(wls)
        n_sub = np.ascontiguousarray(np.asarray(mats[sub].get_nk(wls), dtype=np.complex128))
        n_layers_t = np.ascontiguousarray(np.array([mats[layer.mat].get_nk(wls) for layer in stack], dtype=np.complex128).T)
        tv, tw = prepare_targets_vectorized(wls, tgts)
        back_n = np.zeros((len(wls), 0), dtype=np.complex128)
        ctx = prepare_normal_fast_context(wls=wls, n_layers_T=n_layers_t, n_sub=n_sub, has_back_calc=False,
                                          n_back_T=back_n, d_back=no_back_d)
        reel = (ctx["n_layers_real"], ctx["inv_n_layers_real"], ctx["n_sub_real"], ctx["k0_wls"], tv, tw)
        noyaux = {
            "cost_lossless_front_fast": partial(cost_lossless_front_fast, ep, *reel),
            "grad_lossless_front_fast": partial(compute_gradient_lossless_front_fast, ep, *reel, var_idx),
            "cost_numba_fast": partial(cost_numba_fast, ep, n_layers_t, n_sub, wls, tv, tw, 0.0, False, back_n, no_back_d),
            "grad_all_layers_analytic": partial(
                compute_gradient_all_layers_analytic, ep, n_layers_t, n_sub, wls, tv, tw, 0.0, False, back_n, no_back_d, var_idx),
        }
        appels = a.calls if nom == "optimisation" else max(200, a.calls // 10)
        table: dict = {}
        print(f"\ngrille {nom} : {len(wls)} longueurs d'onde, {len(ep)} couches, {appels} appels")
        print(f"{'noyau':<28}" + "".join(f"{n:>9d} f" for n in fils) + "   meilleur")
        for cle, f in noyaux.items():
            ligne = {}
            for n in fils:
                numba.set_num_threads(n)
                ligne[n] = round(_chrono(f, appels), 2)
            table[cle] = ligne
            best = min(ligne, key=ligne.get)
            print(f"{cle:<28}" + "".join(f"{ligne[n]:>9.1f} µ" for n in fils) + f"   {best} fil(s)")
        sortie["grids"][nom] = {"wavelengths": len(wls), "us_per_call": table}
    sortie["threading_layer"] = numba.threading_layer()
    print(f"\ncouche de fils Numba : {sortie['threading_layer']}")
    if a.out:
        print(f"consigne dans {ecrire_json(a.out.resolve(), sortie, racine=ROOT)}")
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
