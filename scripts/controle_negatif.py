"""CONTROLE NEGATIF : sur un composant ou le monitoring MARCHE, changer de temoin doit PERDRE.

    .venv\\Scripts\\python.exe scripts\\controle_negatif.py --composant 48c --shard 0/6

C'est le test de falsification de la regle trouvee le 2026-08-15 sur le 99 couches :

    « changer de verre temoin juste apres une couche de FAIBLE sensibilite,
      jamais apres une couche sensible »   (r = +0,69 entre S(p-1) et le SEEL)

🔴 SI CETTE REGLE DESIGNE UNE BONNE POSITION DE CHANGEMENT SUR LE 48c OU LE 35c, ELLE EST
FAUSSE. Sur ces deux composants le monitoring fonctionne deja -- 0,17 nm et 0,53 nm a 0 % de
plantage -- donc un changement de temoin ne peut que RETIRER de la compensation sans rien
restaurer. Toute partition doit y etre PIRE que la reference.

⚠️ BORNE RELACHEE POUR LE 35c. La contrainte de 👤 (20 a 60 couches par temoin) rend tout
changement IMPOSSIBLE sur 35 couches : 35 < 2 x 20. Pour que le controle existe, le minimum
est abaisse a 12 couches ici, et seulement ici. C'est une entorse assumee : elle rend le test
possible, elle ne change pas la contrainte de production.

Chaque sous-empilement declare sa tranche de bruit (`noise_layer_offset`), comme dans la
campagne du 99c : sans ca les campagnes se retrouvent correlees et le controle ment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

COMPOSANTS = {
    # nom : (fichier, nb couches, minimum par temoin, SEEL de reference sans changement)
    "48c": ("example/example_strat/JSON-strat-example.json", 48, 20, 0.17),
    "35c": ("example/example_strat/JSON-strat-bandpass-3cav.json", 35, 12, 0.53),
    # 🔑 EMPILEMENT ALEATOIRE, 75 couches, graine 2026. Ni cavite, ni miroir, ni
    # periodicite : c'est la validation HORS ECHANTILLON de la regle de sensibilite.
    # Une regle qui aurait besoin de la structure du design ne doit RIEN y prevoir.
    # 18 positions admissibles, contre 5 et 6 sur les petits composants : c'est le test
    # le mieux echantillonne des trois.
    "random75": ("example/example_strat/JSON-strat-random75.json", 75, 20, None),
}
SEED = 42
CRASH_TOL = 0.05


def positions(n: int, mini: int) -> list[int]:
    """Positions de changement admissibles : PAIRES, et deux parts >= mini."""
    return [p for p in range(2, n, 2) if p >= mini and n - p >= mini]


def cache_dir(comp: str) -> Path:
    d = ROOT / "reports" / f"controle_{comp}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def mesurer(comp: str, a: int, b: int) -> dict:
    import bench_examples as Bx
    from CERTUS_STRAT import CertusStratApp

    cfg_rel, n_tot, _, _ = COMPOSANTS[comp]
    d = cache_dir(comp)
    t0 = time.perf_counter()
    row = {"comp": comp, "a": a, "b": b, "n": b - a, "verdict": "?",
           "n_strats": 0, "n_deposables": 0, "crash_min": None,
           "stamp": datetime.now().isoformat(timespec="seconds")}
    try:
        src = json.loads((ROOT / cfg_rel).read_text(encoding="utf-8"))
        sub = dict(src)
        sub["stack_multipliers"] = src["stack_multipliers"][a:b]
        sub["execution_mode"] = "fast"
        sub["search_resolution"] = False
        sub["monochromator_resolution_nm"] = 2.0
        f = d / f"cfg_{a:03d}_{b:03d}.json"
        f.write_text(json.dumps(sub, indent=2, ensure_ascii=False), encoding="utf-8")

        Bx.qapp()
        Bx.autoanswer_dialogs(True)
        app = CertusStratApp()
        app.load_configuration(str(f))
        if "execution_mode" in getattr(app, "widgets", {}):
            app.widgets["execution_mode"].setCurrentText("fast")
        over = {"show_plots": False, "robustness_seed": SEED,
                "monochromator_resolution_nm": 2.0, "search_resolution": False,
                "noise_layer_offset": a, "noise_total_layers": n_tot}
        _c = app.collect_params
        vus = {"n": 0}

        def collect(*ar, **kw):
            p = _c(*ar, **kw)
            p.update(over)
            vus["n"] += 1
            return p

        app.collect_params = collect
        app.run_workflow(23)
        res = Bx.wait_for(app.worker) if getattr(app, "worker", None) else None
        row["run_s"] = round(time.perf_counter() - t0, 1)
        if vus["n"] < 2:
            row["verdict"] = "SURCHARGES_NON_APPLIQUEES"
            return row
        strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
        if not strats:
            row["verdict"] = "ECHEC_RESULT_NONE"
            return row
        taux = [float(s.get("crash_rate", 1.0)) for s in strats]
        ok = [s for s in strats if float(s.get("crash_rate", 1.0)) < CRASH_TOL]
        ok.sort(key=lambda s: float(s.get("robustness_score", 1e18)))
        row.update({"n_strats": len(strats), "n_deposables": len(ok),
                    "crash_min": round(min(taux) * 100, 2),
                    "verdict": "DEPOSABLE" if ok else "AUCUNE_DEPOSABLE"})
        if ok:
            per = ok[0].get("results_per_noise") or []
            if per:
                ch = min(per, key=lambda r: abs(float(r.get("noise_level", 1.0)) - 1.0))
                th = ch.get("thicknesses_all")
                if th:
                    np.save(d / f"th_{a:03d}_{b:03d}.npy", np.asarray(th, dtype=np.float64))
    except Exception as exc:  # noqa: BLE001
        row["verdict"] = "EXCEPTION"
        row["erreur"] = repr(exc)[:200]
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--composant", choices=sorted(COMPOSANTS), required=True)
    ap.add_argument("--shard", default="0/1")
    args = ap.parse_args()

    comp = args.composant
    _, n_tot, mini, _ = COMPOSANTS[comp]
    d = cache_dir(comp)
    besoin: list[tuple[int, int]] = []
    for p in positions(n_tot, mini):
        besoin += [(0, p), (p, n_tot)]
    besoin = sorted(set(besoin))
    i, n = (int(x) for x in args.shard.split("/"))
    a_faire = [(a, b) for k, (a, b) in enumerate(besoin)
               if k % n == i and not (d / f"i_{a:03d}_{b:03d}.json").exists()]
    sys.stderr.write(f"{comp} : {len(besoin)} sous-empilements | shard {i}/{n} -> {len(a_faire)}\n")
    for a, b in a_faire:
        row = mesurer(comp, a, b)
        (d / f"i_{a:03d}_{b:03d}.json").write_text(
            json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
        sys.stderr.write(f"  [{a},{b}) {b - a} couches : {row['verdict']} "
                         f"{row['n_deposables']}/{row['n_strats']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
