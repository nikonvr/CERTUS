"""Banc de la base de depots : CERTUS INDEX retrouve-t-il l'epaisseur et n(633) des ajustements certifies ?

    python scripts\\bench_base_depots.py                      # les onze references, trois executions chacune
    python scripts\\bench_base_depots.py --runs 1 --seulement h800,mesures-yf3vis

Les references sont dans `example/database_depots/references_index.json` : les ajustements certifies de
l'application CERTUS INDEX autonome dont le spectre est un depot de la base. Ce sont des sorties d'ajustement, pas
des mesures independantes : le banc dit si INDEX retrouve le meme optimum sur les memes donnees.

Pour chaque reference, la mesure de la base (T, ou T et R reunies quand la reference les ajuste ensemble) est chargee
dans la fenetre INDEX comme un utilisateur le fait (`load_file`), avec le substrat, la normalisation et la bande de la
reference ; INDEX estime lui-meme l'epaisseur de depart et ses bornes. Les boites de dialogue repondent OUI, donc
l'extension IR tourne quand la bande depasse 2500 nm.

🔑 CE QUI SE COMPARE. Quand la bande depasse 2500 nm et commence sous 2200 nm, INDEX ajuste le modele de
Tauc-Lorentz-Urbach jusqu'a 2200 nm seulement, puis fige l'epaisseur et n, k sous 2500 nm avant l'extension IR ;
l'application autonome ajuste le meme modele sur toute la bande. L'epaisseur et n(633) d'INDEX sont alors ceux de
l'etage TLU. Le banc l'ecrit sur chaque ligne (`etages`).

INDEX n'est pas reproductible (generateurs non amorces, ETAT section 3) : chaque reference tourne `--runs` fois, et
chaque execution est gardee.

Sortie : une ligne par execution, puis `reports/bench_base_depots_<commit>_<date>.json`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as be  # noqa: E402  (sets the offscreen platform and the working directory first)

BASE = ROOT / "example" / "database_depots"
LAMBDA_NM = 633.0


def _provenance() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()

    return {"git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}


def _measurement(ref: dict, catalogue: dict, workdir: Path) -> Path:
    """The file INDEX loads: the deposit itself, or its T and R columns side by side on their common grid."""
    from certus.utils.certus_depots_db import measurement_path

    if len(ref["depots"]) == 1:
        return measurement_path(catalogue[ref["depots"][0]], BASE)
    import numpy as np

    columns, grid = {}, None
    for depot_id in ref["depots"]:
        entry = catalogue[depot_id]
        data = np.loadtxt(measurement_path(entry, BASE), delimiter=",", skiprows=1, ndmin=2)
        if grid is None:
            grid = data[:, 0]
        elif data.shape[0] != grid.shape[0] or np.max(np.abs(data[:, 0] - grid)) > 1e-6:
            raise ValueError(f"{ref['nom']}: {depot_id} is not on the grid of {ref['depots'][0]}")
        columns[entry["voies"][0]["mode"]] = data[:, 1]
    path = workdir / f"{ref['nom']}.csv"
    order = [mode for mode in ("T", "R") if mode in columns]
    lines = ["wavelength_nm," + ",".join(order)]
    lines += [",".join([repr(float(w))] + [repr(float(columns[m][i])) for m in order]) for i, w in enumerate(grid)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _n_at(tlu, wavelength_nm: float) -> float | None:
    """n of a Tauc-Lorentz-Urbach result at one wavelength, with the functions INDEX fits with."""
    if tlu is None:
        return None
    import numpy as np

    from certus.core.certus_core import HC_EV_NM
    from certus_physics import epsilon1_TL_analytic, epsilon2_TLU_array, epsilon_to_nk

    energy = np.array([HC_EV_NM / wavelength_nm])
    eps2 = epsilon2_TLU_array(energy, tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.Eu)
    eps1 = epsilon1_TL_analytic(energy, tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.eps_inf)
    n, _k, _ok = epsilon_to_nk(eps1, eps2, 0.5, 15.0, 15.0)
    return float(n[0])


def _summary(res, middle_nm: float) -> dict | None:
    if res is None:
        return None
    import math

    mse = float(res.final_mse)
    return {
        "d_nm": float(res.optimal_thickness),
        "n633": _n_at(res.tlu_params, LAMBDA_NM),
        "n_milieu": _n_at(res.tlu_params, middle_nm),
        "rmse": math.sqrt(mse) if mse >= 0 else None,
        "methode": (res.optimization_stats or {}).get("method"),
    }


def fit_middle_nm(low: float, high: float) -> float:
    """The middle of the band INDEX fits the model on: up to 2200 nm when it splits the fit in two stages."""
    if high > 2500.0 and low < 2200.0:
        high = 2200.0
    return 0.5 * (low + high)


def _one_run(ref: dict, path: Path, timeout_s: float) -> dict:
    from PyQt6.QtCore import QEventLoop, QTimer

    from certus.ui.certus_index_ui import CertusIndexApp

    seen: dict = {"tlu": None, "final": None, "error": None}
    cls = CertusIndexApp
    originals = {name: getattr(cls, name) for name in ("_on_tlu_constrained_finished", "_on_finished", "_on_error")}

    def tlu_stage(self, res):
        seen["tlu"] = res
        return originals["_on_tlu_constrained_finished"](self, res)

    def finished(self, res):
        seen["final"] = res
        return originals["_on_finished"](self, res)

    def failed(self, message):
        seen["error"] = str(message)
        return originals["_on_error"](self, message)

    cls._on_tlu_constrained_finished, cls._on_finished, cls._on_error = tlu_stage, finished, failed
    try:
        app = cls()
        if not app.load_file(str(path)):
            return {"erreur": "load_file refused the measurement"}
        app.cb_sub.setCurrentText(ref["substrat"])
        if app.cb_sub.currentText() != ref["substrat"]:
            return {"erreur": f"substrate {ref['substrat']!r} is not in the INDEX list"}
        app.chk_normalized.setChecked(bool(ref["normalise"]))
        low, high = ref["bande_nm"]
        if low is not None:
            app.sb_lmin.setValue(float(low))
        if high is not None:
            app.sb_lmax.setValue(float(high))
        middle = fit_middle_nm(app.sb_lmin.value(), app.sb_lmax.value())
        from certus.core.certus_substrate_db import SUBSTRATE_LIST

        settings = {
            "substrat_calcul": SUBSTRATE_LIST[app.cb_sub.currentIndex()],
            "normalise": app.chk_normalized.isChecked(),
            "lambda_nm": [app.sb_lmin.value(), app.sb_lmax.value()],
            "lambda_milieu_nm": middle,
            "d_bornes_nm": [app.sb_dmin.value(), app.sb_dmax.value()],
            "d_estimee_nm": getattr(app, "_estimated_thickness_nm", None),
        }
        t0 = time.perf_counter()
        app.run_optimization()
        loop, timer = QEventLoop(), QTimer()

        def tick() -> None:
            done = (seen["final"] is not None and app.btn_run.isEnabled()) or seen["error"] is not None
            if done or time.perf_counter() - t0 > timeout_s:
                loop.quit()

        timer.timeout.connect(tick)
        timer.start(250)
        loop.exec()
        timer.stop()
        out = {
            "reglages": settings,
            "duree_s": round(time.perf_counter() - t0, 1),
            "etages": "TLU <= 2200 nm puis IR" if seen["tlu"] is not None else "TLU sur la bande",
            "tlu": _summary(seen["tlu"], middle),
            "final": _summary(seen["final"], middle),
            "erreur": seen["error"] or (None if seen["final"] is not None else f"no result within {timeout_s:.0f} s"),
        }
        app.close()
        app.deleteLater()
        return out
    finally:
        for name, method in originals.items():
            setattr(cls, name, method)


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.5f}"


def _delta(value: float | None, reference: float | None) -> str:
    return "-" if value is None or reference is None else f"{value - reference:+.5f}"


def _index_exports() -> set[Path]:
    """The `Report_INDEX_*` files in reports/: INDEX writes one .html and one .xlsx there after every fit."""
    return set((ROOT / "reports").glob("Report_INDEX_*"))


def _park_index_exports(before: set[Path], destination: Path) -> int:
    """Move the exports INDEX wrote since `before` out of the repository tree, so that a bench leaves no untracked files."""
    fresh = sorted(_index_exports() - before)
    if fresh:
        destination.mkdir(parents=True, exist_ok=True)
    for path in fresh:
        shutil.move(str(path), str(destination / path.name))
    return len(fresh)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--seulement", default="", help="noms de references separes par des virgules")
    ap.add_argument("--timeout", type=float, default=1800.0, help="secondes par execution")
    ap.add_argument("--out", default=None)
    ap.add_argument("--garder-exports", action="store_true",
                    help="laisse dans reports/ les Report_INDEX_* qu'INDEX ecrit a chaque ajustement (par defaut : deplaces dans le dossier temporaire)")
    a = ap.parse_args()

    be.qapp()
    be.autoanswer_dialogs(True)
    import certus_physics

    certus_physics.warmup_physics()
    from certus.utils.certus_depots_db import load_catalogue

    catalogue = {entry["id"]: entry for entry in load_catalogue(BASE)}
    refs = json.loads((BASE / "references_index.json").read_text(encoding="utf-8"))["references"]
    wanted = {name.strip() for name in a.seulement.split(",") if name.strip()}
    if wanted:
        refs = [ref for ref in refs if ref["nom"] in wanted]
    provenance = _provenance()
    be.emit(f"BENCH_BASE_DEPOTS commit={provenance['git_commit'][:8]} dirty={provenance['git_dirty']} "
            f"references={len(refs)} runs={a.runs}")

    results = []
    exports_before = _index_exports()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for ref in refs:
                path = _measurement(ref, catalogue, Path(tmp))
                for run in range(1, a.runs + 1):
                    out = _one_run(ref, path, a.timeout)
                    middle = (out.get("reglages") or {}).get("lambda_milieu_nm")
                    n_mid_ref = None if middle is None else _n_at(SimpleNamespace(**ref["parametres"]), middle)
                    results.append({"reference": ref["nom"], "execution": run, "reference_n_milieu": n_mid_ref, **out})
                    tlu, final = out.get("tlu") or out.get("final"), out.get("final")
                    if out.get("erreur") or tlu is None:
                        be.emit(f"REF {ref['nom']} #{run} ERREUR {out.get('erreur')}")
                        continue
                    d_pct = 100.0 * (tlu["d_nm"] - ref["d_nm"]) / ref["d_nm"]
                    be.emit(
                        f"REF {ref['nom']} #{run} {out['etages']} | d {tlu['d_nm']:.2f} nm (ref {ref['d_nm']:.2f}, "
                        f"{d_pct:+.3f} %) | n({middle:.0f}) {_fmt(tlu['n_milieu'])} (ref {_fmt(n_mid_ref)}, "
                        f"{_delta(tlu['n_milieu'], n_mid_ref)}) | n633 {_fmt(tlu['n633'])} (ref {_fmt(ref['n633'])}, "
                        f"{_delta(tlu['n633'], ref['n633'])}) | rmse final {_fmt(final['rmse'] if final else None)} "
                        f"| {out['duree_s']} s"
                    )
    finally:
        if not a.garder_exports:
            parked = Path(tempfile.gettempdir()) / "bench_base_depots_exports_INDEX" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            moved = _park_index_exports(exports_before, parked)
            if moved:
                be.emit(f"EXPORTS_INDEX={moved} fichiers deplaces vers {parked}")

    stamp = dt.date.today().isoformat()
    target = Path(a.out) if a.out else ROOT / "reports" / f"bench_base_depots_{provenance['git_commit'][:8]}_{stamp}.json"
    from certus.utils.certus_atomic_io import atomic_open

    with atomic_open(target, "w", encoding="utf-8") as handle:
        json.dump({"provenance": provenance, "references": refs, "executions": results}, handle,
                  ensure_ascii=False, indent=1)
    be.emit(f"ARTEFACT={target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
