"""TEST DIFFERENTIEL : un reglage qui ne change RIEN au resultat est inerte.

    .venv\\Scripts\\python.exe scripts\\check_param_effect.py
    .venv\\Scripts\\python.exe scripts\\check_param_effect.py --only machine_sampling_dd

POURQUOI CETTE METHODE PLUTOT QU'UNE AUTRE. Chercher si un parametre est *lu* demande de
suivre sa plomberie, et la plomberie a des angles morts : les reglages STRAT sont lus par
NOM DE WIDGET dans une boucle generique, invisible a une recherche textuelle. Le 2026-08-15
trois defauts de cette famille ont echappe a tout controle statique :

  * `--mode fast` du balayage ne s'appliquait pas -- ecrit sur un dict que `run_workflow`
    jette et reconstruit ;
  * le plan de coupe multi-temoins et la fente figee, pareil ;
  * `machine_sampling_dd`, expose dans l'interface et livre dans neuf configurations, que
    AUCUN des 27 sites d'appel ne passe au noyau.

Ce script ne suit aucune plomberie. Il pose la seule question qui compte :

    🔑 SI JE CHANGE CE REGLAGE, LE RESULTAT CHANGE-T-IL ?

Deux runs, deux valeurs, meme graine, meme empilement, tout le reste identique. Si le score
revient IDENTIQUE AU DERNIER BIT, le reglage n'a aucun effet -- qu'il soit lu ou non, qu'il
soit documente ou non. C'est le pendant de la contrainte C1 du projet, qui exige qu'un
chemin neutre soit bit-identique : ici on exige qu'un chemin NON neutre ne le soit PAS.

⚠️ CE QU'UN "AUCUN EFFET" NE PROUVE PAS. Le reglage peut etre inerte, mais il peut aussi
etre sans effet SUR CET EMPILEMENT : sur 8 couches, une regle qui ne mord qu'a partir de 20
couches ne montrera rien. Un resultat NEGATIF est donc une piste, pas un verdict -- il faut
le rejouer sur un empilement ou le mecanisme est cense agir. Un resultat POSITIF, lui, est
definitif : le reglage agit.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as B  # noqa: E402
from CERTUS_STRAT import CertusStratApp  # noqa: E402

#: Bac a sable de 8 couches : assez petit pour enchainer les runs, assez vrai pour porter
#: la physique. 🔴 Jamais JSON-strat-example.json -- c'est le juge de paix, interdit 4.
CONFIG = "example/example_strat/JSON-strat-sand8.json"

#: (parametre, valeur A, valeur B). Les deux valeurs doivent etre PHYSIQUEMENT distinctes :
#: comparer 0.005 a 0.0051 ne prouverait rien si le solveur quantifie.
CASES: list[tuple[str, object, object]] = [
    # Le defaut connu, en temoin positif du script lui-meme : il DOIT sortir "aucun effet".
    ("machine_sampling_dd", 0.0, 0.125),
    # Bruit et lecture
    ("tp_hysteresis_factor", 1.66, 1.00),
    ("reading_smoothing_window", 1, 8),
    ("poem_anchor_noise", True, False),
    ("poem_enabled", True, False),
    # Physique
    ("index_corridor", 0.0, 0.005),
    ("photometric_curvature_amp", 0.0, 0.00375),
    ("slit_bias_enabled", True, False),
    ("monochromator_resolution_nm", 2.0, 5.0),
    ("affine_scale_amp", 0.0, 0.05),
    # Recherche
    ("dp_top_k", 20, 60),
    ("k_keep_survivors", 6, 20),
    ("phase_a_level_margin_factor", 1.66, 3.33),
    ("allow_rate", True, False),
    ("dp_yield_weight", 0.0, 1.0),
    # Multi-temoins, ecrit le 2026-08-14 : ce script est sa verification de bout en bout.
    ("witness_reset_layers", [], [4]),
]


def run_once(overrides: dict, seed: int = 42) -> tuple[float | None, int, int]:
    """Un run complet. Rend (score, nb_strategies, nb_appels_a_collect)."""
    B.qapp()
    B.autoanswer_dialogs(True)
    app = CertusStratApp()
    app.load_configuration(str(ROOT / CONFIG))

    full = dict(overrides)
    full["show_plots"] = False
    full["robustness_seed"] = seed
    seen = {"calls": 0}
    _collect = app.collect_params

    def collect_with_overrides(*a, **kw):
        p = _collect(*a, **kw)
        p.update(full)
        seen["calls"] += 1
        return p

    app.collect_params = collect_with_overrides
    app.run_workflow(23)
    res = B.wait_for(app.worker) if getattr(app, "worker", None) else None

    strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
    score = strats[0].get("robustness_score") if strats else None
    return score, len(strats), seen["calls"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="ne tester qu'un parametre")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    cases = [c for c in CASES if not args.only or c[0] == args.only]
    if not cases:
        raise SystemExit(f"parametre inconnu : {args.only}")

    sys.stderr.write(f"\n{len(cases)} parametre(s) | empilement {CONFIG} | graine {args.seed}\n")
    inert, alive, unclear = [], [], []

    for key, va, vb in cases:
        sys.stderr.write(f"\n--- {key} : {va!r} contre {vb!r} ---\n")
        t0 = time.perf_counter()
        try:
            sa, na, ca = run_once({key: va}, args.seed)
            sb, nb, cb = run_once({key: vb}, args.seed)
        except Exception as exc:  # noqa: BLE001 -- un cas rate ne doit pas perdre les autres
            sys.stderr.write(f"    ECHEC : {exc!r}\n")
            unclear.append((key, f"exception {exc!r}"))
            continue
        dt = time.perf_counter() - t0

        if ca == 0 or cb == 0:
            unclear.append((key, "collect_params jamais appele -- surcharges non transmises"))
            sys.stderr.write("    ⚠️ les surcharges n'ont pas atteint le solveur\n")
            continue
        if sa is None or sb is None:
            unclear.append((key, f"RESULT=None (A={sa}, B={sb})"))
            sys.stderr.write(f"    ⚠️ RESULT=None -- ce n'est PAS 'aucun effet' ({dt:.0f} s)\n")
            continue

        same = repr(sa) == repr(sb) and na == nb
        (inert if same else alive).append((key, sa, sb, na, nb))
        mark = "🔴 AUCUN EFFET" if same else "✅ agit"
        sys.stderr.write(f"    {mark} | A={sa!r} ({na} strat) | B={sb!r} ({nb} strat) | {dt:.0f} s\n")

    print("\n" + "=" * 78)
    print("REGLAGES SANS AUCUN EFFET SUR CE COMPOSANT : %d" % len(inert))
    print("=" * 78)
    for key, sa, _sb, na, _nb in inert:
        print(f"  {key:<32} score identique au bit ({sa!r}), {na} strategies")
    print("\n  Un 'aucun effet' n'est pas un verdict : rejoue-le sur un empilement ou le")
    print("  mecanisme est cense mordre avant de conclure a un reglage mort.")

    print("\n" + "=" * 78)
    print("REGLAGES QUI AGISSENT : %d" % len(alive))
    print("=" * 78)
    for key, sa, sb, _na, _nb in alive:
        print(f"  {key:<32} {sa!r} -> {sb!r}")

    if unclear:
        print("\n" + "=" * 78)
        print("NON CONCLUANTS : %d" % len(unclear))
        print("=" * 78)
        for key, why in unclear:
            print(f"  {key:<32} {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
