"""LECTURE DES ARTEFACTS DU BATCH RATE -- et de la PREDICTION posee avant qu'il tourne.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\lire_batch_rate.py

## Ce que cet instrument fait, et ce qu'il refuse de faire

Il lit les artefacts de balayage de queue et rend, coupure par coupure : le taux de plantage
minimal, le nombre de deposables, le meilleur SEEL, et la couche critique de la meilleure.

🔴 IL REFUSE DE DESIGNER UN OPTIMUM SANS DIRE SON BRUIT. C'est la faute exacte commise le
2026-08-19 : « la coupure a un optimum tardif, 52 » alors que l'ecart 52/46 valait 1,25 sigma.
Chaque ecart de SEEL est donc rendu EN SIGMA, et les coupures indiscernables sont annoncees
comme telles.

⚠️ Le sigma employe est une EXTRAPOLATION, pas une mesure sur ce composant. §24-26 mesure
sigma ≈ 6 % du score a N = 150 sur le 48 couches ; on le reporte en 1/sqrt(N). Il n'a jamais
ete mesure sur r75x2. C'est dit a chaque affichage, pour qu'on ne l'oublie pas.
"""

from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RXT = re.compile(r"^RATE_TAIL(\d+)\(")
CRASH_TOL = 0.05

#: §24-26 : sigma ≈ 6 % du SCORE a N = 150. SEEL = 2*sqrt(score), donc sigma_SEEL ≈ sigma/2
#: en relatif. La difference de DEUX SEEL porte sqrt(2) de plus.
SIGMA_SCORE_N150 = 0.06
N_PAR_MODE = {"fast": 50, "premium": 150, "deep": 300}

#: Longueur de chaque composant -- une queue va de la coupure jusqu'a la fin.
N_COUCHES = {"35c": 35, "48c": 48, "75c": 75, "99c": 99,
             "r75x0.5": 75, "r75x1.5": 75, "r75x1.75": 75, "r75x2": 75}


def sigma_seel_diff(mode: str) -> float:
    """Ecart-type RELATIF sur la DIFFERENCE de deux SEEL, au mode donne."""
    n = N_PAR_MODE.get(mode, 150)
    s_score = SIGMA_SCORE_N150 * math.sqrt(150.0 / n)
    return (s_score / 2.0) * math.sqrt(2.0)


def lire(p: str) -> None:
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    S = d.get("strategies") or []
    if not S:
        print(f"  {os.path.basename(p)} : VIDE")
        return
    mode = d.get("mode") or "?"
    n_mc = (d.get("profondeur") or {}).get("robustness_num_runs")
    prof = f"N={n_mc}" if n_mc else f"N deduit du mode ({N_PAR_MODE.get(mode, '?')}), NON consigne"
    print(f"\n{'=' * 92}")
    print(f"  {os.path.basename(p)}")
    print(f"  composant={d.get('composant')} mode={mode} graine={d.get('seed')}  {prof}")
    print(f"{'=' * 92}")

    coups = sorted({int(m.group(1)) for x in S
                    if (m := RXT.match(str(x.get("origine") or "")))})
    base = [x for x in S if not str(x.get("origine") or "").startswith("RATE")]
    if base:
        cb = min(x["crash_rate"] for x in base)
        db = sum(1 for x in base if x["crash_rate"] < CRASH_TOL)
        print(f"  reference SANS queue : n={len(base)}  crash_min={100 * cb:.2f}%  deposables={db}")

    print(f"\n  {'coupure':>8}{'couches Rate':>14}{'n_var':>7}{'crash_min':>11}"
          f"{'depos':>7}{'SEEL':>9}{'n_blocs':>9}{'couche critique':>17}")
    print("  " + "-" * 90)
    lignes = []
    for c in coups:
        g = [x for x in S if str(x.get("origine", "")).startswith(f"RATE_TAIL{c}(")]
        if not g:
            continue
        cm = min(x["crash_rate"] for x in g)
        dep = [x for x in g if x["crash_rate"] < CRASH_TOL]
        best = min(dep, key=lambda z: z["score"]) if dep else None
        seel = 2 * math.sqrt(best["score"]) if best else None
        cl = (best.get("critical_layer") or {}).get("layer") if best else None
        nb = best["n_blocs"] if best else None
        # Les artefacts ne portent pas `rate_layers` par ligne : une queue va de la coupure
        # jusqu'a la fin, donc le compte se deduit de la longueur de l'empilement.
        n_rate = (N_COUCHES.get(str(d.get("composant")), 0) - c) or "?"
        print(f"  {c:>8}{(n_rate or '?'):>14}{len(g):>7}{100 * cm:>10.2f}%{len(dep):>7}"
              f"{(f'{seel:.3f}' if seel else '-'):>9}{str(nb or '-'):>9}"
              f"{str(cl if cl is not None else '-'):>17}")
        if seel:
            lignes.append((c, seel, best))

    if len(lignes) < 2:
        print("\n  🟠 moins de deux coupures deposables : aucun classement possible.")
        return

    # --- le classement, AVEC son bruit -----------------------------------------------------
    sd = sigma_seel_diff(mode)
    lignes.sort(key=lambda t: t[1])
    c0, s0, b0 = lignes[0]
    print(f"\n  meilleure coupure : {c0}  (SEEL {s0:.3f})")
    print(f"  sigma sur une DIFFERENCE de deux SEEL, mode {mode} : {100 * sd:.1f} % "
          f"-- ⚠️ EXTRAPOLE de §24-26, jamais mesure sur ce composant")
    print(f"\n  {'coupure':>8}{'SEEL':>9}{'ecart':>9}{'en sigma':>10}   verdict")
    ex_aequo = [c0]
    for c, s, _ in lignes[1:]:
        rel = (s - s0) / s0
        k = rel / sd if sd > 0 else float("inf")
        v = "INDISCERNABLE de la meilleure" if k < 2.0 else "distincte"
        if k < 2.0:
            ex_aequo.append(c)
        print(f"  {c:>8}{s:>9.3f}{100 * rel:>8.1f}%{k:>10.2f}   {v}")
    print(f"\n  🔑 classe d'equivalence a 2 sigma : coupures {sorted(ex_aequo)}")
    if len(ex_aequo) == len(lignes):
        print("  🔴 TOUTES les coupures sont indiscernables : ce run ne designe AUCUN optimum.")

    # --- la prediction posee AVANT le run ---------------------------------------------------
    print("\n  --- la prediction du 2026-08-19, posee avant que ce run ne tourne ---")
    print("  « l'optimum doit se deplacer vers des queues plus COURTES (coupure plus tardive) »")
    print("  car le vivier de references ne grossit plus dans la queue : une longue queue fige")
    print("  desormais une erreur unique au lieu d'etre creditee d'un n_ref fictif.")
    print(f"  reference d'avant correctif : optimum a 52, plateau de crash plat de 58 a 46.")
    if c0 > 52:
        print(f"  📏 optimum a {c0} > 52  -> CONFORME a la prediction")
    elif c0 == 52:
        print(f"  📏 optimum a {c0} = 52  -> prediction NON confirmee, optimum inchange")
    else:
        print(f"  📏 optimum a {c0} < 52  -> prediction REFUTEE, l'optimum a recule")
    if len(ex_aequo) == len(lignes):
        print("  ⚠️ mais toutes les coupures sont indiscernables : ce run ne tranche RIEN,")
        print("     et le lire comme s'il tranchait serait refaire l'erreur de la veille.")


def main() -> int:
    motifs = sys.argv[1:] or [
        "reports/blocs_vs_plantage_r75x2_fast_s042_tail46-64.json",
        "reports/blocs_vs_plantage_r75x2_fast_s077_tail46-64.json",
        "reports/blocs_vs_plantage_r75x2_premium_s042_tail52-58.json",
    ]
    vus = 0
    for m in motifs:
        for p in sorted(glob.glob(str(ROOT / m)) or glob.glob(m)):
            lire(p)
            vus += 1
    if not vus:
        print("  aucun artefact -- le batch n'a pas encore rendu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
