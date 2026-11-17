"""Chantier 21, C1 : sans l'option `spline_mono_analytic_gradient`, SPLINE rend les memes bits qu'avant.

`scripts/c1_diff.py` ne joue pas SPLINE (corpus normal, oblique, strat, appelants) : ce script le fait. Il importe le
`certus` de l'ARBRE donne, construit la configuration comme la fenetre INDEX SPLINE (`tests/headless/test_spline.py`,
exemple `TSIO2-1700-1.xlsx` de l'arbre de travail courant), lance `worker_spline_optimization` et ecrit dans SORTIE.npz
les tableaux du resultat, puis le cout et le gradient analytique de `SplinePWLObjective` sur ce resultat (chemin
monotone, qui doit rester sans gradient, et chemin sans monotonie). On le lance sur un export de HEAD (`git archive`)
puis sur l'arbre de travail, chacun avec un cache Numba vierge, et on compare au bit :

set QT_QPA_PLATFORM=offscreen && set NUMBA_NUM_THREADS=8 && set NUMBA_CACHE_DIR=<vierge>
python reports/chantier21_2026-11-17/p21_c1_default_path.py ARBRE SORTIE.npz
python reports/chantier21_2026-11-17/p21_c1_default_path.py --compare A.npz B.npz
"""
import sys
import threading
from pathlib import Path

import numpy as np


def compare(a_path: str, b_path: str) -> int:
    a, b = np.load(a_path), np.load(b_path)
    keys = sorted(set(a.files) | set(b.files))
    differ = []
    for k in keys:
        if k not in a.files or k not in b.files:
            differ.append(f"{k}: absent d'un cote")
            continue
        x, y = np.ascontiguousarray(a[k]), np.ascontiguousarray(b[k])
        if x.dtype != y.dtype or x.shape != y.shape or x.tobytes() != y.tobytes():
            differ.append(f"{k}: bits differents")
    print(f"C1 SPLINE : {len(keys)} tableaux, {len(differ)} differents")
    for line in differ:
        print("  " + line)
    return 1 if differ else 0


def run(tree: Path, out: Path) -> None:
    example = (Path(__file__).resolve().parents[2] / "example/example_index_spline/TSIO2-1700-1.xlsx").resolve()
    sys.path.insert(0, str(tree))
    import certus

    paths = [Path(p).resolve() for p in certus.__path__]
    assert all(p.is_relative_to(tree) for p in paths), f"certus vient de {paths}, pas de {tree}"

    from PyQt6.QtWidgets import QApplication

    import certus_physics

    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    certus_physics.warmup_physics()

    from certus.spline.spline_objective import SplinePWLObjective
    from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    spline_app = CertusIndexSplineApp()
    spline_app._on_load(path=str(example))
    cfg = spline_app._build_opt_config(notify=False)
    print(f"n_mono_band_nm={cfg.n_mono_band_nm} option={getattr(cfg, 'spline_mono_analytic_gradient', 'absente')}")
    result = worker_spline_optimization(cfg, threading.Event(), progress_cb=lambda *a, **k: None, live_cb=lambda *a, **k: None)

    rec = {}
    for key, value in result.items():
        arr = np.asarray(value) if isinstance(value, (np.ndarray, float, int, list, tuple)) else None
        if arr is not None and arr.dtype != object:
            rec["result_" + key] = arr

    sk = np.asarray(result["sigma_knots"], dtype=np.float64)
    x = np.asarray(result["x"], dtype=np.float64)
    if x.size == 1 + 2 * sk.size:
        obj = SplinePWLObjective(cfg, sk)
        rec["obj_mono_cost"] = np.array(obj(x))
        g = obj.analytic_gradient(x)
        rec["obj_mono_grad_is_none"] = np.array(g is None)
        x_phys = x.copy()
        x_phys[1 : 1 + sk.size] = np.asarray(result["n_nodes_physical"], dtype=np.float64)
        obj_free = SplinePWLObjective(cfg.replace(n_mono_band_nm=None), sk)
        rec["obj_free_cost"] = np.array(obj_free(x_phys))
        rec["obj_free_grad"] = obj_free.analytic_gradient(x_phys)
    np.savez(out, **rec)
    print(f"{len(rec)} tableaux ecrits ; rmse={result.get('rmse')!r} d={result.get('d_nm')!r}")


if __name__ == "__main__":
    if sys.argv[1] == "--compare":
        sys.exit(compare(sys.argv[2], sys.argv[3]))
    run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]))
