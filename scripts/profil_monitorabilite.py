"""MONITORABILITE PAR COUCHE — une grandeur PHYSIQUE, sans aucune recherche.

    .venv\\Scripts\\python.exe scripts\\profil_monitorabilite.py

👤 2026-08-15 : *« il faut absolument comprendre et donner des resultats coherents, c'est la
base de toute demarche scientifique »*.

🔴 LE DEFAUT DE L'INSTRUMENT PRECEDENT, ET IL EST DISQUALIFIANT.

La campagne des intervalles rapportait `n_deposables / n_strats`. Ce rapport ne mesure PAS
la faisabilite, parce que **le denominateur est produit par la programmation dynamique**, qui
optimise un cout de Phase A et ne sait rien du taux de plantage. Mesure : `n_strats` varie
d'un facteur 2 entre longueurs voisines (205 a [0,48), 412 a [0,52)), et les creux de taux
coincident avec les creux de volume.

Pire, une INCOHERENCE LOGIQUE en decoule : [0,50) contient toutes les couches de [0,48), donc
aucune difficulte physique de [0,48) ne peut disparaitre dans [0,50) -- la surveillance de la
couche i ne depend que des couches 0..i. Or le taux passe de 8,3 % a 25,7 %. C'est donc du
bruit de recherche, et un instrument qui produit ca ne peut pas servir de mesure.

## Ce que ce script mesure a la place

Pour CHAQUE couche i, le nombre de longueurs d'onde qui offrent un point de surveillance
utilisable. Aucun solveur, aucune DP, aucun Monte-Carlo : de la TMM pure sur l'empilement
nominal.

    swing       T_max - T_min pendant la croissance   >= dynamics_threshold
    plancher    T_min pendant la croissance           >= min_transmission_floor
    ancre       au moins un point tournant            tan 2.delta = R/Q

🔑 POURQUOI C'EST COHERENT, ET L'AUTRE NON. Cette grandeur ne depend que des couches 0..i.
Elle est donc IDENTIQUE quel que soit le sous-empilement qui contient la couche i. Le profil
de [0,99) contient exactement les profils de [0,48) et de [0,50) : il n'y a plus rien qui
puisse s'inverser. Une seule mesure decrit tous les prefixes a la fois.

⚠️ CE QU'ELLE NE DIT PAS. Qu'une couche soit surveillable ne dit pas qu'une STRATEGIE existe :
un bloc exige une lambda valable pour TOUTES ses couches a la fois, et la compensation depend
de l'histoire. C'est une condition NECESSAIRE, pas suffisante. Elle borne la faisabilite par
le haut, proprement, ce que le rapport `n_dep/n_strats` ne faisait pas.
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
    "99c": "example/example_strat/JSON-strat-bandpass-5cav-99c.json",
    "75c": "example/example_strat/JSON-strat-random75.json",
    "48c": "example/example_strat/JSON-strat-example.json",
    "35c": "example/example_strat/JSON-strat-bandpass-3cav.json",
}
N_PAS = 400


def profil(cfg: str) -> dict:
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
    s_dyn = float(prm.get("dynamics_threshold", 0.025))
    s_tmin = float(prm.get("min_transmission_floor", 0.10))
    lams = arange_inclusive(float(prm["scan_wl_min"]), float(prm["scan_wl_max"]),
                            float(prm.get("scan_wl_step", 2.0)))
    nH = get_refractive_clues_vectorized(prm["nH_id"], lams, db_instance=db)
    nL = get_refractive_clues_vectorized(prm["nL_id"], lams, db_instance=db)
    nS = get_refractive_clues_vectorized(prm["nSub_id"], lams, db_instance=db)
    nH0 = float(np.real(get_refractive_index(prm["nH_id"], l0, db_instance=db)))
    nL0 = float(np.real(get_refractive_index(prm["nL_id"], l0, db_instance=db)))
    d = np.array([(m * l0) / (4.0 * (nH0 if i % 2 == 0 else nL0)) for i, m in enumerate(mult)])

    # (couche, lambda) -> admissible ?
    adm = np.zeros((N, len(lams)), dtype=bool)      # swing + plancher
    adm_tp = np.zeros((N, len(lams)), dtype=bool)   # ... + au moins un point tournant
    for j, lam in enumerate(lams):
        M = np.eye(2, dtype=np.complex128)
        for i in range(N):
            n_i = nH[j] if i % 2 == 0 else nL[j]
            X = M[0, 0] + nS[j] * M[0, 1]
            Y = M[1, 0] + nS[j] * M[1, 1]
            C, S = X + Y, Y / n_i + n_i * X
            P = 0.5 * ((C.real**2 + C.imag**2) + (S.real**2 + S.imag**2))
            Q = 0.5 * ((C.real**2 + C.imag**2) - (S.real**2 + S.imag**2))
            R = C.imag * S.real - C.real * S.imag
            dfin = 2.0 * np.pi * float(np.real(n_i)) * d[i] / float(lam)
            u = np.linspace(0.0, dfin, N_PAS)
            T = 4.0 * float(np.real(nS[j])) / (P + Q * np.cos(2 * u) + R * np.sin(2 * u))
            ok = (float(T.max() - T.min()) >= s_dyn) and (float(T.min()) >= s_tmin)
            adm[i, j] = ok
            if ok:
                phi = 0.5 * np.arctan2(R, Q)
                demi = np.pi / 2.0
                k0 = int(np.ceil((0.0 - phi) / demi))
                if phi + k0 * demi <= 0.0:
                    k0 += 1
                adm_tp[i, j] = (int(np.floor((dfin - phi) / demi)) - k0 + 1) >= 1
            ph = 2.0 * np.pi * n_i * d[i] / lam
            c_, s_ = np.cos(ph), np.sin(ph)
            M = M @ np.array([[c_, 1j * s_ / n_i], [1j * n_i * s_, c_]], dtype=np.complex128)

    return {"N": N, "n_lams": len(lams), "adm": adm, "adm_tp": adm_tp,
            "lams": lams, "seuils": (s_dyn, s_tmin)}


def main() -> int:
    import bench_examples as Bx

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    sortie = {}

    for nom, cfg in COMPOSANTS.items():
        p = profil(cfg)
        N, nl = p["N"], p["n_lams"]
        par_couche = p["adm_tp"].sum(axis=1)
        muettes = int((par_couche == 0).sum())

        print("=" * 86)
        print(f"{nom} — {N} couches, {nl} lambda candidates, "
              f"seuils swing {p['seuils'][0]} / plancher {p['seuils'][1]}")
        print("=" * 86)
        print(f"  couches SANS aucune lambda utilisable : {muettes} / {N}")

        # 🔑 LA GRANDEUR QUI GOUVERNE UN BLOC : combien de lambda servent TOUTES les
        # couches d'un intervalle a la fois. C'est l'intersection, et elle ne peut que
        # DECROITRE quand on allonge -- monotone PAR CONSTRUCTION, donc coherente.
        print(f"\n  lambda servant TOUT le prefixe [0,b) -- intersection, monotone par construction")
        print(f"    b :", end="")
        bornes = [b for b in range(10, N + 1, 10)] + [N]
        inter = p["adm_tp"].copy()
        cum = np.ones(nl, dtype=bool)
        courbe = []
        for i in range(N):
            cum &= p["adm_tp"][i]
            courbe.append(int(cum.sum()))
        for b in bornes:
            print(f" {b:4d}", end="")
        print(f"\n    n :", end="")
        for b in bornes:
            print(f" {courbe[b - 1]:4d}", end="")
        print()
        zero = next((i + 1 for i, v in enumerate(courbe) if v == 0), None)
        if zero:
            print(f"  🔴 l'intersection tombe a ZERO des la couche {zero} : "
                  f"aucun bloc unique ne peut couvrir [0,{zero}).")
        # profil par couche, en tranches
        print(f"\n  lambda utilisables PAR COUCHE (moyenne par tranche de 10) :")
        print("    ", end="")
        for k in range(0, N, 10):
            seg = par_couche[k:k + 10]
            print(f"{k}-{min(k+9, N-1)}:{seg.mean():5.1f}  ", end="")
        print()
        sortie[nom] = {"N": N, "n_lams": nl, "muettes": muettes,
                       "intersection_prefixe": courbe,
                       "par_couche": par_couche.tolist()}
        print()

    (ROOT / "reports" / "profil_monitorabilite.json").write_text(
        json.dumps(sortie, indent=2, ensure_ascii=False), encoding="utf-8")
    print("consigne dans reports/profil_monitorabilite.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
