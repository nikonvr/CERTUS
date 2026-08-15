"""LE FILTRE DE PHASE A LAISSE-T-IL PASSER DES LAMBDA SANS POINT TOURNANT ?

    .venv\\Scripts\\python.exe scripts\\probe_tp_admissibilite.py

👤 2026-08-15 : *« évidemment toute proposition doit être validée par l'expérience numérique.
Et voir sur le 35c, 48c avec un seul testglass s'il y a amélioration. »*

🔴 DIAGNOSTIQUER AVANT DE PRESCRIRE. La proposition est d'ajouter un critere de point tournant
au filtre de candidature de Phase A. Avant d'ecrire ce critere -- dont on ignore la forme,
puisqu'il est NON MONOTONE (trop de points tournants declenche CRASH_TP_MISCOUNT autant que
trop peu) -- il faut mesurer si le trou existe.

    la question, et elle se repond SANS toucher au pipeline :
    combien de couples (couche, lambda) passent le filtre ACTUEL et n'ont AUCUN point tournant ?

Le filtre actuel (`certus_strat_service.py:868`) retient une lambda sur deux criteres
d'amplitude, et aucun ne teste l'existence d'un extremum :

    dynamics >= dynamics_threshold   (0,025)   swing crete-a-crete T_max - T_min
    t_min    >= min_transmission_floor (0,10)  le signal ne plonge pas sous le plancher

Une couche dont T croit de facon MONOTONE pendant toute sa croissance a un swing
parfaitement acceptable et aucun extremum sur lequel s'arreter. Elle passe.

🔑 SI LE TROU EST VIDE, LA PROPOSITION NE PEUT RIEN AMELIORER SUR CES COMPOSANTS, et il est
inutile d'ecrire le critere pour aller le verifier au banc. Si le trou est plein, on sait
combien de candidates sont concernees et on peut estimer l'enjeu avant de coder.

⚠️ CE QUE CETTE SONDE NE DIT PAS : que le SEEL s'ameliorerait. Elle mesure une OPPORTUNITE
(des candidates douteuses existent), pas un gain. Le gain se mesure au banc, apres
implantation, contre les references 0,173 nm (48c) et 0,482 nm (35c).

Rappel de vocabulaire, parce que c'est l'erreur du jour : un point tournant, c'est
l'admittance du SYSTEME qui devient reelle (`tan 2.delta = R/Q`), pas une couche a 1 QWOT.
Voir docs/QWOT_ET_TURNING_POINT.md.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

COMPOSANTS = {
    "48c dichroique": "example/example_strat/JSON-strat-example.json",
    "35c 3 cavites": "example/example_strat/JSON-strat-bandpass-3cav.json",
    "75c aleatoire": "example/example_strat/JSON-strat-random75.json",
    "99c 5 cavites": "example/example_strat/JSON-strat-bandpass-5cav-99c.json",
}
N_PAS = 400          # pas de discretisation de la croissance, pour swing et t_min


def analyse(nom: str, cfg: str) -> dict:
    import bench_examples as Bx
    from certus.physics.certus_opt_tmm import arange_inclusive
    from certus.utils.certus_strat_service import (
        get_refractive_clues_vectorized,
        get_refractive_index,
    )
    from CERTUS_STRAT import CertusStratApp

    app = CertusStratApp()
    app.load_configuration(str(ROOT / cfg))
    prm = app.collect_params()
    db = prm.get("materials_db_instance") or prm.get("materials_db")

    l0 = float(prm["l0"])
    mult = np.array([float(e) for e in str(prm["stack_string"]).split(",") if e.strip()])
    N = len(mult)
    seuil_dyn = float(prm.get("dynamics_threshold", 0.025))
    seuil_tmin = float(prm.get("min_transmission_floor", 0.10))

    lams = arange_inclusive(float(prm["scan_wl_min"]), float(prm["scan_wl_max"]),
                            float(prm.get("scan_wl_step", 2.0)))
    nH = get_refractive_clues_vectorized(prm["nH_id"], lams, db_instance=db)
    nL = get_refractive_clues_vectorized(prm["nL_id"], lams, db_instance=db)
    nS = get_refractive_clues_vectorized(prm["nSub_id"], lams, db_instance=db)
    nH0 = float(np.real(get_refractive_index(prm["nH_id"], l0, db_instance=db)))
    nL0 = float(np.real(get_refractive_index(prm["nL_id"], l0, db_instance=db)))
    d = np.array([(m * l0) / (4.0 * (nH0 if i % 2 == 0 else nL0)) for i, m in enumerate(mult)])

    passe = 0            # (couche, lambda) admissibles au filtre ACTUEL
    passe_sans_tp = 0    # ... et sans AUCUN point tournant  <- LE TROU
    couches_touchees = set()
    detail = []

    for j, lam in enumerate(lams):
        M = np.eye(2, dtype=np.complex128)
        for i in range(N):
            n_i = nH[j] if i % 2 == 0 else nL[j]

            # ── T(u) pendant la croissance, par la forme fermee du noyau ──
            X = M[0, 0] + nS[j] * M[0, 1]
            Y = M[1, 0] + nS[j] * M[1, 1]
            C, S = X + Y, Y / n_i + n_i * X
            P = 0.5 * ((C.real**2 + C.imag**2) + (S.real**2 + S.imag**2))
            Q = 0.5 * ((C.real**2 + C.imag**2) - (S.real**2 + S.imag**2))
            R = C.imag * S.real - C.real * S.imag

            dfin = 2.0 * np.pi * float(np.real(n_i)) * d[i] / float(lam)
            dl = np.linspace(0.0, dfin, N_PAS)
            T = 4.0 * float(np.real(nS[j])) / (P + Q * np.cos(2 * dl) + R * np.sin(2 * dl))
            swing = float(T.max() - T.min())
            tmin = float(T.min())

            # ── nombre EXACT de points tournants : tan 2.delta = R/Q ──
            phi = 0.5 * np.arctan2(R, Q)
            demi = np.pi / 2.0
            k0 = int(np.ceil((0.0 - phi) / demi))
            if phi + k0 * demi <= 0.0:
                k0 += 1
            n_tp = max(0, int(np.floor((dfin - phi) / demi)) - k0 + 1)

            admis = (swing >= seuil_dyn) and (tmin >= seuil_tmin)
            if admis:
                passe += 1
                if n_tp == 0:
                    passe_sans_tp += 1
                    couches_touchees.add(i)
                    if len(detail) < 6:
                        detail.append({"couche": i, "lambda": round(float(lam), 1),
                                       "swing": round(swing, 4), "t_min": round(tmin, 4)})

            # empiler la couche pour la suivante
            ph = 2.0 * np.pi * n_i * d[i] / lam
            c_, s_ = np.cos(ph), np.sin(ph)
            M = M @ np.array([[c_, 1j * s_ / n_i], [1j * n_i * s_, c_]], dtype=np.complex128)

    pct = 100.0 * passe_sans_tp / passe if passe else 0.0
    return {"composant": nom, "couches": N, "lambdas": len(lams),
            "seuil_dynamics": seuil_dyn, "seuil_t_min": seuil_tmin,
            "admissibles": passe, "admissibles_sans_TP": passe_sans_tp,
            "pct_du_trou": round(pct, 2),
            "couches_concernees": len(couches_touchees), "exemples": detail}


def main() -> int:
    import bench_examples as Bx

    Bx.qapp()
    Bx.autoanswer_dialogs(True)

    print("=" * 88)
    print("LE FILTRE DE PHASE A LAISSE-T-IL PASSER DES LAMBDA SANS POINT TOURNANT ?")
    print("=" * 88)
    print("\n  composant          couches  admissibles  dont SANS point tournant   couches touchees")
    out = []
    for nom, cfg in COMPOSANTS.items():
        try:
            r = analyse(nom, cfg)
        except Exception as exc:  # noqa: BLE001
            print(f"  {nom:18s} EXCEPTION {exc!r}"[:110])
            continue
        out.append(r)
        print(f"  {r['composant']:18s} {r['couches']:5d}  {r['admissibles']:11d}  "
              f"{r['admissibles_sans_TP']:9d} ({r['pct_du_trou']:5.2f} %)      "
              f"{r['couches_concernees']:3d} / {r['couches']}")

    print("\n" + "=" * 88)
    print("LECTURE")
    print("=" * 88)
    for r in out:
        if r["admissibles_sans_TP"] == 0:
            print(f"  🟢 {r['composant']:18s} TROU VIDE -- le critere ne peut RIEN y ameliorer.")
        else:
            print(f"  🔴 {r['composant']:18s} {r['admissibles_sans_TP']} candidates douteuses "
                  f"sur {r['couches_concernees']} couches. Exemples :")
            for e in r["exemples"][:3]:
                print(f"        couche {e['couche']:3d} a {e['lambda']:.0f} nm : "
                      f"swing {e['swing']:.4f} (seuil {r['seuil_dynamics']}), t_min {e['t_min']:.4f}")

    p = ROOT / "reports" / "tp_admissibilite.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nconsigne dans {p}")
    print("\n⚠️  Ceci mesure une OPPORTUNITE, pas un gain. Le gain se mesure au banc,")
    print("    contre les references 0,173 nm (48c) et 0,482 nm (35c).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
