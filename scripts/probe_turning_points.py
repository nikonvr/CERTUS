"""TURNING POINT n'est PAS « couche a 1 QWOT ». Mesure de l'ecart entre les deux.

    .venv\\Scripts\\python.exe scripts\\probe_turning_points.py

👤 2026-08-15, deux fois et il a raison les deux fois :
  *« la notion de QWOT est differente de turning point, attention ! Le turning point = QWOT
  que si tout l'empilement est en QWOT, sinon ca ne correspond pas. »*
  *« le TP c'est lorsque l'admittance devient reelle, et cela n'a rien a voir avec une couche
  QWOT. »*

🔴 CE QUE J'AVAIS ECRIT DE FAUX, ET QUE CETTE SONDE EXISTE POUR REFUTER. Dans l'en-tete de
`serie_echelle_r75.py` j'ai ecrit qu'une couche « sous 1 QWOT ne traverse aucun extremum, donc
aucun point d'arret ». C'est faux. Le comptage « 59 couches sur 75 sous 1 QWOT » qui en
decoule ne mesure PAS la disponibilite d'un point d'arret.

## Ce que dit le code, et c'est la formule fermee de `layer_scan_coeffs`

Pour la couche qui pousse sur un empilement deja depose :

    T(d) = 4.n_sub / (P + Q.cos(2.delta) + R.sin(2.delta)),   delta = 2.pi.n.d/lambda

Un extremum annule la derivee : -2Q.sin(2delta) + 2R.cos(2delta) = 0, donc

    🔑 tan(2.delta) = R / Q        ->    delta_TP = (1/2).arctan(R/Q) + k.(pi/2)

Il y a donc DEUX choses, et confondre l'une avec l'autre est l'erreur :

  * LA PERIODE entre deux turning points consecutifs vaut exactement pi/2 en delta, soit
    **un quart d'onde a lambda_mon**. Ca, c'est vrai, et c'est l'origine de la confusion.

  * 🔴 LE DEPART est decale d'une phase (1/2).arctan(R/Q) que fixe **l'empilement du
    dessous**, via M et n_sub. Cette phase n'est nulle que si l'admittance est deja reelle
    a delta = 0 -- c'est-a-dire si l'empilement sous-jacent est lui-meme un nombre entier
    de quarts d'onde a lambda_mon. C'est le cas d'un empilement tout-QWOT, et de lui seul.

## 🟢 LE SEUL CAS OU LES DEUX COINCIDENT VRAIMENT — 👤 : « uniquement sur la premiere couche
## d'un substrat nu »

Et ca se DEMONTRE sur la formule, ce n'est pas une observation empirique. Sur substrat nu,
M = I (matrice identite), donc :

    X = M00 + n_sub.M01 = 1           Y = M10 + n_sub.M11 = n_sub
    C = X + Y = 1 + n_sub             S = Y/n + n.X = n_sub/n + n

Pour un dielectrique sans pertes, n_sub et n sont REELS, donc C et S sont reels, donc

    🔑 R = Im(C.conj(S)) = C.imag.S.real - C.real.S.imag = 0

d'ou tan(2.delta) = 0, soit delta = k.(pi/2) : les extrema tombent **exactement** aux
multiples du quart d'onde. 👤 a donc raison au sens strict, et c'est verifie numeriquement
plus bas (`controle 1`).

⚠️ **Meme la, c'est un quart d'onde a LAMBDA_MON, pas a lambda_0.** Une couche de 0,5 QWOT a
633 nm en fait 0,70 a 450 nm. La coincidence porte sur la longueur d'onde de CONTROLE.

🔴 Et des la couche 2 la coincidence est perdue, sauf si la couche 1 est elle-meme un nombre
entier de quarts d'onde a lambda_mon -- ce qui ramene a la condition tout-QWOT.

**Consequence directe** : une couche de 0,6 QWOT PEUT traverser un turning point si le
decalage de phase l'y amene, et une couche de 1,3 QWOT peut n'en traverser qu'un. Le compte
de QWOT de la couche ne determine pas le compte de turning points.

## Et un second effet, independant du premier

Le QWOT se compte **a une longueur d'onde**. `stack_multipliers` est en QWOT a **lambda_0**,
mais le turning point se produit a **lambda_mon**, que le solveur choisit librement dans
`scan_wl_min..scan_wl_max`. Une couche de 0,5 QWOT a 633 nm en fait 0,70 a 450 nm. Compter
les QWOT a lambda_0 ne dit donc rien de ce qui se passe a la lambda de controle retenue.

## Ce que la sonde mesure

Pour chaque facteur d'echelle, chaque couche et chaque lambda candidate : le nombre EXACT de
turning points traverses pendant la croissance, par la formule fermee ci-dessus. Puis on le
compare au comptage naif en QWOT a lambda_0. L'ecart entre les deux est le sujet.
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

SRC = ROOT / "example" / "example_strat" / "JSON-strat-random75.json"
FACTEURS = (0.5, 1.0, 1.5, 2.0)


def n_tp_exact(M: np.ndarray, n_layer: complex, n_sub: complex,
               n_real: float, d: float, lam: float) -> int:
    """Nombre de turning points traverses en faisant croitre la couche de 0 a `d`.

    Formule fermee du noyau (`layer_scan_coeffs`) : les extrema sont en
    delta = (1/2).arctan2(R, Q) + k.(pi/2). On compte les k qui tombent dans ]0, delta_fin].
    """
    X = M[0, 0] + n_sub * M[0, 1]
    Y = M[1, 0] + n_sub * M[1, 1]
    C = X + Y
    S = Y / n_layer + n_layer * X
    Q = 0.5 * ((C.real**2 + C.imag**2) - (S.real**2 + S.imag**2))
    R = C.imag * S.real - C.real * S.imag

    delta_fin = 2.0 * np.pi * n_real * d / lam
    phi = 0.5 * np.arctan2(R, Q)          # 🔑 le decalage impose par l'empilement du dessous
    demi = np.pi / 2.0
    # premier k tel que phi + k.(pi/2) > 0
    k0 = int(np.ceil((0.0 - phi) / demi))
    if phi + k0 * demi <= 0.0:
        k0 += 1
    k1 = int(np.floor((delta_fin - phi) / demi))
    return max(0, k1 - k0 + 1)


def main() -> int:
    import bench_examples as Bx
    from certus.physics.certus_opt_tmm import arange_inclusive
    from certus.utils.certus_strat_service import (
        get_refractive_clues_vectorized,
        get_refractive_index,
    )
    from CERTUS_STRAT import CertusStratApp

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    app = CertusStratApp()
    app.load_configuration(str(SRC))
    prm = app.collect_params()
    db = prm.get("materials_db_instance") or prm.get("materials_db")

    l0 = float(prm["l0"])
    mult = np.array([float(e) for e in str(prm["stack_string"]).split(",") if e.strip()])
    N = len(mult)
    lams = arange_inclusive(float(prm["scan_wl_min"]), float(prm["scan_wl_max"]), 5.0)
    nH = get_refractive_clues_vectorized(prm["nH_id"], lams, db_instance=db)
    nL = get_refractive_clues_vectorized(prm["nL_id"], lams, db_instance=db)
    nS = get_refractive_clues_vectorized(prm["nSub_id"], lams, db_instance=db)
    nH0 = float(np.real(get_refractive_index(prm["nH_id"], l0, db_instance=db)))
    nL0 = float(np.real(get_refractive_index(prm["nL_id"], l0, db_instance=db)))

    print(f"{N} couches | {len(lams)} lambda candidates de {lams[0]:.0f} a {lams[-1]:.0f} nm\n")

    # ─────────────────────────────────────────────────────────────────────────
    # CONTROLE 1 — 👤 : « uniquement sur la premiere couche d'un substrat nu ca coincide ».
    # Sur substrat nu M = I, donc C et S sont reels, donc R = 0 exactement. On le VERIFIE
    # numeriquement au lieu de le croire.
    # ─────────────────────────────────────────────────────────────────────────
    I2 = np.eye(2, dtype=np.complex128)
    r_nu, r_apres = [], []
    for j, lam in enumerate(lams):
        n0 = nH[j]
        X, Y = I2[0, 0] + nS[j] * I2[0, 1], I2[1, 0] + nS[j] * I2[1, 1]
        C, S = X + Y, Y / n0 + n0 * X
        r_nu.append(abs(C.imag * S.real - C.real * S.imag))
        # et juste apres UNE couche non-QWOT : la coincidence doit etre PERDUE
        d0 = (mult[0] * l0) / (4.0 * nH0)
        dl = 2.0 * np.pi * n0 * d0 / lam
        M1 = np.array([[np.cos(dl), 1j * np.sin(dl) / n0],
                       [1j * n0 * np.sin(dl), np.cos(dl)]], dtype=np.complex128)
        n1 = nL[j]
        X, Y = M1[0, 0] + nS[j] * M1[0, 1], M1[1, 0] + nS[j] * M1[1, 1]
        C, S = X + Y, Y / n1 + n1 * X
        Q = 0.5 * ((C.real**2 + C.imag**2) - (S.real**2 + S.imag**2))
        r_apres.append(abs(0.5 * np.arctan2(C.imag * S.real - C.real * S.imag, Q)))

    print("CONTROLE 1 — la coincidence QWOT = turning point, et ou elle s'arrete")
    print(f"  couche 1 sur substrat NU   : |R| max = {max(r_nu):.2e}  -> phase nulle, "
          f"les TP tombent PILE aux quarts d'onde")
    print(f"  couche 2, apres une non-QWOT : decalage de phase median "
          f"{np.median(r_apres):.4f} rad = {np.degrees(np.median(r_apres)):.1f} deg, "
          f"max {max(r_apres):.4f} rad")
    print(f"  🔑 des la couche 2 la coincidence est PERDUE.\n")

    resultats = {"controle_substrat_nu_R_max": float(max(r_nu)),
                 "controle_couche2_dephasage_median_rad": float(np.median(r_apres))}

    for f in FACTEURS:
        # epaisseurs physiques -- le QWOT est defini A LAMBDA_0
        d = np.array([(m * f * l0) / (4.0 * (nH0 if i % 2 == 0 else nL0))
                      for i, m in enumerate(mult)])
        qwot_l0 = mult * f

        # nombre EXACT de turning points, couche par couche, lambda par lambda
        tp = np.zeros((N, len(lams)), dtype=int)
        for j, lam in enumerate(lams):
            M = np.eye(2, dtype=np.complex128)
            for i in range(N):
                n_i = nH[j] if i % 2 == 0 else nL[j]
                tp[i, j] = n_tp_exact(M, n_i, nS[j], float(np.real(n_i)), d[i], float(lam))
                # on empile la couche pour la suivante
                dl = 2.0 * np.pi * n_i * d[i] / lam
                c, s = np.cos(dl), np.sin(dl)
                Li = np.array([[c, 1j * s / n_i], [1j * n_i * s, c]], dtype=np.complex128)
                M = M @ Li

        naif = int(np.sum(qwot_l0 < 1.0))                 # 🔴 le comptage FAUX
        muettes = int(np.sum(tp.max(axis=1) == 0))        # 🟢 le comptage juste
        # une couche est "servie" si au moins une lambda lui offre un TP
        med_lam = int(np.median(np.sum(tp > 0, axis=1)))
        resultats[f] = {"qwot_min": float(qwot_l0.min()), "naif_sous_1_qwot": naif,
                        "muettes_reel": muettes, "lambdas_servantes_medianes": med_lam,
                        "tp_total_median": float(np.median(tp.sum(axis=1)))}
        print(f"x{f:<4g}  QWOT min a l0 = {qwot_l0.min():.3f}")
        print(f"        comptage NAIF  « couches sous 1 QWOT a l0 »        : {naif:3d} / {N}")
        print(f"        comptage JUSTE « couches sans AUCUN TP, toutes l » : {muettes:3d} / {N}")
        print(f"        lambdas offrant un TP, par couche (mediane)        : {med_lam:3d} / {len(lams)}\n")

    out = ROOT / "reports" / "turning_points_vs_qwot.json"
    out.write_text(json.dumps(resultats, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 74)
    print("CONCLUSION")
    print("=" * 74)
    n1 = resultats[0.5]["naif_sous_1_qwot"]
    m1 = resultats[0.5]["muettes_reel"]
    print(f"  Sur le x0.5, le comptage naif annonce {n1} couches « sans point d'arret ».")
    print(f"  Le comptage exact en trouve {m1}. L'ecart est la mesure de l'erreur.")
    print(f"\n  consigne dans {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
