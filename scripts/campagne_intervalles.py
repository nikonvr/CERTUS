"""CAMPAGNE DES INTERVALLES : mesurer une fois chaque sous-empilement, assembler ensuite.

    .venv\\Scripts\\python.exe scripts\\campagne_intervalles.py --vague 2
    .venv\\Scripts\\python.exe scripts\\campagne_intervalles.py --vague 3 --shard 0/2
    .venv\\Scripts\\python.exe scripts\\campagne_intervalles.py --etat        # ou en est-on

👤 2026-08-15 : *« je suis intimement persuade que c'est complique de trouver quand changer,
et que ce n'est pas un simple essai en coupant en 3 parties egales qui donne le resultat »*.
Il a raison, et la mesure le confirme : le tiers C -- celui ou le 99c complet n'a plus qu'UNE
lambda viable -- est le PLUS FACILE des trois sur verre nu (156 strategies deposables sur
163). Le modele « le temoin vieillit et meurt » est donc refute.

L'IDEE QUI REND LA RECHERCHE TRAITABLE. Les 441 partitions admissibles (20 a 60 couches par
temoin, 👤) ne partagent que ~251 sous-empilements DISTINCTS. On mesure donc les INTERVALLES,
une fois chacun, et toute partition s'assemble ensuite a cout NUL depuis le cache.

🔴 TROIS EXIGENCES, ecrites parce qu'elles ont chacune un defaut connu a eviter :

  REPRENABLE -- chaque intervalle mesure ecrit son propre fichier. Un intervalle deja mesure
  n'est JAMAIS recalcule, quel que soit le nombre d'arrets et de relances.

  OBSERVABLE -- `--etat` repond a tout instant, sans rien relancer.

  UN ECHEC N'EST PAS UN RESULTAT -- un run qui rend `RESULT=None` est consigne comme ECHEC,
  pas comme « aucune strategie ». L'erreur n.5 du projet est exactement celle-la : le banc
  rend None sous charge, et ca ressemble a une mesure.

🔑 LE BRUIT DE LECTURE EST UNE TRANCHE, PAS UN FLUX NEUF. Chaque intervalle declare sa
position dans le depot (`noise_layer_offset`, `noise_total_layers`), donc il lit SA tranche du
bruit continu des 99 couches. Sans ca, trois campagnes a la meme graine -- ce qu'il faut pour
partager la realisation d'indice -- ont un bruit correle a 78 % au lieu de 1 %.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from itertools import combinations
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CACHE_BASE = ROOT / "reports" / "intervalles_99c"
FULL = "example/example_strat/JSON-strat-bandpass-5cav-99c.json"
N_LAYERS = 99

# 🔴 LA BORNE HAUTE A SAUTE LE 2026-08-15, ET C'EST 👤 QUI L'A LEVEE.
#
#     👤 : « ma borne 60 couches est empirique, on peut donc la faire sauter »
#
# Elle valait 60 et la mesure l'a contredite deux fois : un empilement ALEATOIRE de 75
# couches se surveille d'un bout a l'autre a 0 % de plantage (SEEL 0,272 nm), et il porte
# 9,99 um -- PLUS que les 9,10 um du 99c. Ni le nombre de couches ni l'epaisseur accumulee
# sur le temoin ne justifiaient donc la borne.
#
# ⚠️ `HI_DEFAUT` reste a 60 pour que les 251 intervalles deja en cache restent reproductibles
# a l'identique. La vague etendue se demande explicitement : `--hi 99`.
LO = 20                  # 👤 : au moins 20 couches par verre temoin -- CETTE borne tient
HI_DEFAUT = 60
SEED = 42
CRASH_TOL = 0.05


def get_cache(mode: str = "fast") -> Path:
    return ROOT / "reports" / ("intervalles_99c" if mode == "fast" else f"intervalles_99c_{mode}")


def bornes() -> list[int]:
    """Positions admissibles : PAIRES seulement -- une campagne ouvre sur une couche H."""
    return [0] + [p for p in range(2, N_LAYERS, 2)] + [N_LAYERS]


def intervalles_par_vague(n_temoins: int, hi: int = HI_DEFAUT) -> list[tuple[int, int]]:
    """Les intervalles distincts qu'exigent les partitions a `n_temoins`."""
    besoin: set[tuple[int, int]] = set()
    for cuts in combinations([p for p in range(2, N_LAYERS, 2)], n_temoins - 1):
        b = [0, *cuts, N_LAYERS]
        parts = [(b[i], b[i + 1]) for i in range(len(b) - 1)]
        if all(LO <= y - x <= hi for x, y in parts):
            besoin |= set(parts)
    return sorted(besoin)


def fichier(a: int, b: int, cache_dir: Path) -> Path:
    return cache_dir / f"i_{a:03d}_{b:03d}.json"


def deja_mesure(a: int, b: int, cache_dir: Path) -> bool:
    return fichier(a, b, cache_dir).exists()


def mesurer(a: int, b: int, mode: str = "fast", cache_dir: Path | None = None) -> dict:
    """Un intervalle. Rend le dictionnaire consigne, echec compris."""
    import bench_examples as Bx
    from CERTUS_STRAT import CertusStratApp

    if cache_dir is None:
        cache_dir = get_cache(mode)
    cache_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    row: dict = {"a": a, "b": b, "n": b - a, "mode": mode, "stamp": datetime.now().isoformat(timespec="seconds"),
                 "instrument": _commit(), "machine": _machine(),
                 "verdict": "?", "n_strats": 0, "n_deposables": 0,
                 "crash_min": None, "crash_retenue": None, "score": None, "run_s": 0.0}
    try:
        cfg = _config_intervalle(a, b, mode=mode, cache_dir=cache_dir)
        Bx.qapp()
        Bx.autoanswer_dialogs(True)
        app = CertusStratApp()
        app.load_configuration(str(cfg))
        if "execution_mode" in getattr(app, "widgets", {}):
            app.widgets["execution_mode"].setCurrentText(mode)

        over = {
            "show_plots": False, "robustness_seed": SEED,
            "monochromator_resolution_nm": 2.0, "search_resolution": False,
            "noise_layer_offset": a, "noise_total_layers": N_LAYERS,
            "execution_mode": mode,
        }
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
        row.update({
            "n_strats": len(strats), "n_deposables": len(ok),
            "crash_min": round(min(taux) * 100, 2),
            "crash_retenue": round(float(strats[0].get("crash_rate", 1.0)) * 100, 2),
            "verdict": "DEPOSABLE" if ok else "AUCUNE_DEPOSABLE",
        })
        if ok:
            row["score"] = float(ok[0].get("robustness_score", 0.0))
            th = _epaisseurs(ok[0])
            if th is not None:
                np.save(cache_dir / f"th_{a:03d}_{b:03d}.npy", th)
                row["tirages"] = int(th.shape[0])
    except Exception as exc:  # noqa: BLE001 -- un intervalle rate ne doit pas perdre la campagne
        row["verdict"] = "EXCEPTION"
        row["erreur"] = repr(exc)[:300]
        row["run_s"] = round(time.perf_counter() - t0, 1)
    return row


def _epaisseurs(strat: dict) -> np.ndarray | None:
    per = strat.get("results_per_noise") or []
    if not per:
        return None
    ch = min(per, key=lambda r: abs(float(r.get("noise_level", 1.0)) - 1.0))
    th = ch.get("thicknesses_all")
    return np.asarray(th, dtype=np.float64) if th else None


def _config_intervalle(a: int, b: int, mode: str = "fast", cache_dir: Path | None = None) -> Path:
    if cache_dir is None:
        cache_dir = get_cache(mode)
    src = json.loads((ROOT / FULL).read_text(encoding="utf-8"))
    d = dict(src)
    d["stack_multipliers"] = src["stack_multipliers"][a:b]
    d["execution_mode"] = mode
    d["search_resolution"] = False
    d["monochromator_resolution_nm"] = 2.0
    d["_description"] = f"Sous-empilement [{a},{b}) du 99c (mode {mode}), sur verre NU."
    out = cache_dir / f"cfg_{a:03d}_{b:03d}.json"
    out.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=10).stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def _machine() -> str:
    """Empreinte de la machine qui a mesure.

    `instrument` consigne le CODE, pour qu'un run soit attribuable. Rien ne consignait
    la MACHINE, et `run_s` n'est comparable qu'a machine egale : le 2026-08-17 les durees
    du cache, mesurees ailleurs, ont servi a dimensionner un ETA et le plafond
    CERTUS_BENCH_TIMEOUT_S sur un PC bien plus modeste. Meme motif que le defaut 24-7 --
    un run qui ne consigne pas ses conditions n'est comparable a rien.

    Ce que ce champ NE dit PAS : SEEL, taux de plantage et nombre de deposables sont
    deterministes a graine et code fixes, donc portables. Seul `run_s` depend de la machine.
    """
    cpu = " ".join((platform.processor() or platform.machine() or "?").split())
    return f"{cpu} | {os.cpu_count()} threads"


def etat(cache_dir: Path | None = None) -> int:
    """Ou en est-on, sans rien relancer."""
    if cache_dir is None:
        cache_dir = CACHE_BASE
    faits = sorted(cache_dir.glob("i_*.json"))
    print("=" * 72)
    print(f"CAMPAGNE DES INTERVALLES ({cache_dir.name})")
    print("=" * 72)
    if not faits:
        print("\nAucun intervalle mesure pour l'instant.")
        return 0
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in faits]
    par_v = {}
    for r in rows:
        par_v.setdefault(r["verdict"], []).append(r)
    print(f"\n{len(rows)} intervalles mesures")
    for v, rs in sorted(par_v.items(), key=lambda kv: -len(kv[1])):
        marque = "🔴" if v.startswith(("ECHEC", "EXCEPTION", "SURCHARGES")) else "  "
        print(f"  {marque} {v:<26} {len(rs):4d}")
    dep = [r for r in rows if r["verdict"] == "DEPOSABLE"]
    if dep:
        dep.sort(key=lambda r: -r["n_deposables"])
        print(f"\n{len(dep)} intervalles DEPOSABLES. Les plus robustes :")
        print("  intervalle   couches  deposables  plantage min  duree")
        for r in dep[:10]:
            print(f"  [{r['a']:3d},{r['b']:3d})   {r['n']:5d}   {r['n_deposables']:8d}"
                  f"   {r['crash_min']:10.1f} %  {r['run_s']:6.0f} s")
    rates = [r for r in rows if r["verdict"].startswith(("ECHEC", "EXCEPTION", "SURCHARGES"))]
    if rates:
        print(f"\n🔴 {len(rates)} ECHECS -- ce ne sont PAS des « aucune strategie » :")
        for r in rates[:6]:
            print(f"  [{r['a']:3d},{r['b']:3d})  {r['verdict']}  {r.get('erreur', '')[:70]}")
    tot = sum(r["run_s"] for r in rows)
    print(f"\ntemps cumule : {tot / 3600:.2f} h | moyenne {tot / max(1, len(rows)):.0f} s par intervalle")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vague", type=int, choices=(2, 3, 4), help="nombre de temoins vise")
    ap.add_argument("--shard", default="0/1", help="i/n pour repartir sur n processus")
    ap.add_argument("--mode", default="fast", choices=("fast", "premium", "deep"), help="mode d'execution")
    ap.add_argument("--hi", type=int, default=HI_DEFAUT,
                    help=f"couches maxi par temoin (defaut {HI_DEFAUT}; borne levee par 👤 "
                         f"le 2026-08-15, mettre {N_LAYERS} pour la supprimer)")
    ap.add_argument("--etat", action="store_true")
    ap.add_argument("--limite", default=None,
                    help="HH:MM -- n'ENGAGE plus de nouvel intervalle apres cette heure")
    args = ap.parse_args()

    cache_dir = get_cache(args.mode)
    cache_dir.mkdir(parents=True, exist_ok=True)
    if args.etat or not args.vague:
        return etat(cache_dir)

    i, n = (int(x) for x in args.shard.split("/"))
    besoin = intervalles_par_vague(args.vague, args.hi)
    a_faire = [(a, b) for k, (a, b) in enumerate(besoin)
               if k % n == i and not deja_mesure(a, b, cache_dir)]
    sys.stderr.write(
        f"\nvague {args.vague} temoins | bornes {LO}-{args.hi} couches par temoin | "
        f"{len(besoin)} intervalles requis | mode {args.mode} | "
        f"shard {i}/{n} -> {len(a_faire)} a mesurer (le reste est en cache {cache_dir.name})\n\n")

    for k, (a, b) in enumerate(a_faire, 1):
        sys.stderr.write(f"[{k}/{len(a_faire)}] intervalle [{a},{b}) -- {b - a} couches\n")
        row = mesurer(a, b, mode=args.mode, cache_dir=cache_dir)
        fichier(a, b, cache_dir).write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
        sys.stderr.write(
            f"    {row['verdict']} | {row['n_deposables']}/{row['n_strats']} deposables | "
            f"plantage min {row['crash_min']} % | {row['run_s']} s\n")
    sys.stderr.write("\nvague terminee.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
