"""LA MEILLEURE MARGE ATTEIGNABLE, COUCHE PAR COUCHE -- la seule route vers une impossibilite.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\probe_marge_atteignable.py [composant ...]

👤 2026-08-17 : *« s'acharner pour moi veut dire etre certain a 100 % qu'aucune strategie multi
lambda avec un seul verre temoin ne peut fonctionner »*.

🔴 POURQUOI UNE RECHERCHE NE PEUT PAS REPONDRE, ET CE N'EST PAS UNE OPINION. Le denombrement
exact du meme jour (`probe_denombre_couvertures.py`) donne pour le 99c, base `adm_tp`, k <= 20 :

    couvertures  1,13 x 10^20        STRATEGIES  5,02 x 10^57

La tractabilite s'arrete entre 2 et 3 blocs : k=2 coute 54 h de criblage, k=3 en coute
7 622 jours. Enumerer est donc definitivement exclu, d'un facteur ~10^50. Seule une CONDITION
NECESSAIRE violee partout peut conclure -- et elle a l'immense avantage de couvrir les 10^57
d'un coup, ET d'etre independante de toute graine.

## Ce que la mesure du jour rend cette route plausible

`probe_blocs_vs_plantage.py` sur le 99c complet : **751 strategies, de 1 a 99 blocs,
`plantage min = 100 %` PARTOUT**. Pas 90 %, pas 99 % -- exactement 100 %, uniformement, y
compris la stategie a 99 blocs qui se reancre a CHAQUE couche. Ni les blocs trop longs (pas de
compensation) ni les blocs trop nombreux (ancres perdues) n'expliquent quoi que ce soit :
l'echec est independant de la structure en blocs.

Un mur que TOUTE structure rencontre designe une couche que personne ne peut eviter.

## Ce que cette sonde mesure

Pour chaque couche i et chaque lambda candidate, en forme fermee sur l'empilement nominal :

    T(u) = 4 n_S / (P + Q cos 2u + R sin 2u)        u = 2 pi n_i d / lambda
    extrema   u = ½ arctan2(R, Q) + k pi/2          dans ]0, u_final]
    MARGE     |T(u_final) - T(dernier extremum)| / A

A = trigger_tolerance / 100, soit 5e-4 en unites de T -- le bruit de lecture mesure (§18-2).

🔴 CE QUE CETTE MARGE N'EST PAS -- corrige apres le premier run, le 2026-08-17.

J'avais annonce que cette sonde testait le critere de §24-41. ELLE NE LE TESTE PAS, et il faut
le dire avant de lire un seul chiffre.

    §24-41 mesure     la marge a la couche critique PENDANT un depot simule, avec le bruit ET
                      l'erreur accumulee. Ses valeurs vont de -1702 A a ~0,9 A, seuil a 0,6 A.
    cette sonde mesure la distance en transmission entre la fin de la couche et son dernier
                      extremum, sur l'empilement NOMINAL, erreur accumulee NULLE.

Mesure : 242 a 600 A ici, contre ~1 A la-bas. Trois ordres de grandeur. Ce ne sont pas la meme
grandeur et **le seuil de 0,6 A ne se transporte pas**. `SEUIL_PREUVE` est conserve comme
repere de lecture, pas comme critere valide.

CE QUE LE PREMIER RUN A DONNE, et pourquoi la sonde reste utile :

    99c   0/99 couche sous le seuil   marge mini 242 A   mediane 601 A   plantage reel 100 %
    75c   0/75 couche sous le seuil   marge mini  79 A   mediane 600 A   plantage reel   0 %

La couche la plus exposee du 75c est TROIS FOIS plus exposee que celle du 99c, et c'est le 99c
qui echoue. Troisieme inversion de la journee, apres la monitorabilite par couche et la
couverture en blocs. Bilan cumule :

    grandeur du signal nominal        99c        75c      verdict
    couches sans lambda utilisable      0          0      ex aequo
    blocs minimum pour couvrir          1 (26 l)   2      99c "plus facile"
    marge nominale minimale           242 A       79 A    99c "plus facile"
    PLANTAGE REEL                     100 %        0 %

🔑 AUCUNE grandeur du signal nominal ne distingue les deux. Le discriminateur n'est pas dans le
signal nominal -- il est entierement dans l'ACCUMULATION. Consequence pour le chantier
"predire sans tout calculer" : un predicteur ne peut pas etre de la TMM pure et bon marche, il
lui faut au minimum une propagation d'erreur simulee.

Si une couche avait sa MEILLEURE marge nominale tres basse, aucune strategie ne pourrait
l'eviter -- ni les 26 a lambda unique, ni les 5 x 10^57. Aucune ne l'a. La condition necessaire
ne conclut donc pas, et cette route vers l'impossibilite est fermee TELLE QUELLE : il faudrait
la rejouer sur la trajectoire accumulee, pas sur le nominal.

## Le garde-fou, parce qu'une recurrence TMM refaite est un risque

Cette sonde recalcule la recurrence de couches pour acceder aux courbes T(u), que
`profil_monitorabilite.profil()` ne rend pas. Elle REDERIVE donc `adm_tp` au passage et
**assere l'egalite** avec celle de `profil()`. Si ma recurrence est fautive, l'assertion tombe
au lieu de rendre un resultat plausible. C'est le motif de l'interdit 7 : deux bugs de signe
ont deja ete trouves dans des reimplantations, a 46 et 82 points de reflectance.

⚠️ CE QUE LA SONDE NE DIT PAS. La marge est calculee sur l'empilement NOMINAL, sans erreur
accumulee. Elle borne donc la faisabilite par le haut : la marge reelle en cours de depot ne
peut qu'etre PIRE. C'est le bon sens pour une preuve d'impossibilite -- si le nominal echoue
deja, le reel echoue aussi -- mais l'inverse ne se conclut pas.

🔒 PERIMETRE, tranche par 👤 le 2026-08-17 : « on considere les TPM pour le POEM : oui a 100 % »
et « on s'arrete sur un TPM : non a 100 % ». Le point tournant est une ANCRE, jamais une cible
d'arret. On exige donc qu'il existe, et la marge mesure la distance a lui -- pas un arret
dessus.
"""

from __future__ import annotations

import importlib.util
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

N_PAS = 400
SEUIL_PREUVE = 0.6          # en unites de A -- §24-41, valide facteur 22
DEMI = np.pi / 2.0

# 🔑 LA SERIE D'ECHELLE, ajoutee le 2026-08-17 -- et c'est elle le vrai juge.
#
# 👤 : « le 99c me gene car il est rare de deposer un empilement tout 1/4 d'onde, surtout en
# trigger POEM. Je prefere ne pas en tirer de conclusions, alors que le 75c est interessant
# avec ses 4 variantes ». Il a raison, et ca corrige ma propre synthese du meme jour.
#
# Le 99c est ADVERSE A POEM PAR CONSTRUCTION : multiplicateurs exactement 1 et 2 a l0 = 633,
# donc §14 s'applique a la lettre -- QWOT et point tournant COINCIDENT sur un empilement
# entierement QWOT a lambda_mon. Chaque couche finit pile sur un extremum, et POEM, qui vise
# un pourcentage de l'amplitude ENTRE les deux derniers extrema, se retrouve au bord degenere
# de sa plage. Signature qui aurait du m'alerter : plantage = 100 % PLAT sur 751 strategies et
# 20 nombres de blocs. Une reponse plate porte zero information.
#
# 🔴 DONC MES "TROIS INVERSIONS" NE PROUVENT PAS CE QUE J'AI DIT. Elles comparaient un cas
# degenere a un cas normal -- ce n'est pas un test loyal des grandeurs, c'est un test contre
# une reference pathologique. Les grandeurs sont peut-etre bonnes ; ma reference etait mauvaise.
#
# Le test loyal est la serie : 75 couches, structure et materiaux identiques, seule l'epaisseur
# optique varie, multiplicateurs JAMAIS entiers donc POEM en regime normal, et une issue qui
# varie continument :
#
#   x0,5   0,252 - 1,240 QWOT   59 couches sous 1   ECHOUE   0/375    crash_min  48 %
#   x1     0,504 - 2,479 QWOT      -                passe  241/662    crash_min   0 %   SEEL 0,272
#   x1,5   0,756 - 3,719 QWOT    3 couches sous 1   limite   1/704    crash_min   0 %   SEEL 0,63
#   x2     1,008 - 4,958 QWOT    0 couche sous 1    ECHOUE   0/404    crash_min 100 %
#
# LA QUESTION QUE CETTE SONDE POSE : les grandeurs du signal nominal ordonnent-elles cette
# serie ? Si oui, elles marchent et seul le 99c egarait. Si non, elles sont a jeter.
COMPOSANTS_ECHELLE = {
    "r75x0.5": "reports/serie_echelle_r75/cfg_x0.5.json",
    "r75x1.5": "reports/serie_echelle_r75/cfg_x1.5.json",
    "r75x2": "reports/serie_echelle_r75/cfg_x2.json",
}


def blocs_minimaux(adm: np.ndarray) -> list[tuple[int, int, int]]:
    """Couverture MINIMALE en blocs contigus a lambda commune. Glouton = optimal ici.

    Rend [(debut, fin_exclue, nb_lambda_communes)]. Une couche sans aucune lambda forme un
    bloc d'une couche a 0 lambda -- signalee, pas masquee.
    """
    N = adm.shape[0]
    blocs: list[tuple[int, int, int]] = []
    i = 0
    while i < N:
        inter = adm[i].copy()
        if not inter.any():
            blocs.append((i, i + 1, 0))
            i += 1
            continue
        j = i + 1
        while j < N:
            nouv = inter & adm[j]
            if not nouv.any():
                break
            inter = nouv
            j += 1
        blocs.append((i, j, int(inter.sum())))
        i = j
    return blocs


def _charger_pm():
    spec = importlib.util.spec_from_file_location(
        "pm", ROOT / "scripts" / "profil_monitorabilite.py")
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)
    return pm


def marges(cfg: str) -> dict:
    """Marge (couche, lambda) en unites de A, plus la rederivation de adm_tp pour controle."""
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
    A = float(prm.get("trigger_tolerance", 0.05)) / 100.0
    lams = arange_inclusive(float(prm["scan_wl_min"]), float(prm["scan_wl_max"]),
                            float(prm.get("scan_wl_step", 2.0)))
    nH = get_refractive_clues_vectorized(prm["nH_id"], lams, db_instance=db)
    nL = get_refractive_clues_vectorized(prm["nL_id"], lams, db_instance=db)
    nS = get_refractive_clues_vectorized(prm["nSub_id"], lams, db_instance=db)
    nH0 = float(np.real(get_refractive_index(prm["nH_id"], l0, db_instance=db)))
    nL0 = float(np.real(get_refractive_index(prm["nL_id"], l0, db_instance=db)))
    d = np.array([(m * l0) / (4.0 * (nH0 if i % 2 == 0 else nL0)) for i, m in enumerate(mult)])

    marge = np.full((N, len(lams)), np.nan)      # en unites de A
    swing = np.zeros((N, len(lams)))
    adm_tp = np.zeros((N, len(lams)), dtype=bool)

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

            def _T(u, P=P, Q=Q, R=R, j=j):
                return 4.0 * float(np.real(nS[j])) / (P + Q * np.cos(2 * u) + R * np.sin(2 * u))

            u = np.linspace(0.0, dfin, N_PAS)
            T = _T(u)
            sw = float(T.max() - T.min())
            swing[i, j] = sw
            ok = (sw >= s_dyn) and (float(T.min()) >= s_tmin)

            if ok:
                phi = 0.5 * np.arctan2(R, Q)
                k0 = int(np.ceil((0.0 - phi) / DEMI))
                if phi + k0 * DEMI <= 0.0:
                    k0 += 1
                k1 = int(np.floor((dfin - phi) / DEMI))
                if k1 - k0 + 1 >= 1:
                    adm_tp[i, j] = True
                    u_last = phi + k1 * DEMI          # dernier extremum avant la fin
                    marge[i, j] = abs(_T(dfin) - _T(u_last)) / A

            ph = 2.0 * np.pi * n_i * d[i] / lam
            c_, s_ = np.cos(ph), np.sin(ph)
            M = M @ np.array([[c_, 1j * s_ / n_i], [1j * n_i * s_, c_]], dtype=np.complex128)

    return {"N": N, "lams": np.asarray(lams), "A": A, "marge": marge,
            "swing": swing, "adm_tp": adm_tp}


def main() -> int:
    import bench_examples as Bx

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    pm = _charger_pm()
    # `pm.COMPOSANTS` n'est PAS modifie : profil_monitorabilite.py produit un artefact
    # committe et bit-identique, et y ajouter des composants le changerait.
    connus = {**pm.COMPOSANTS, **COMPOSANTS_ECHELLE}
    noms = sys.argv[1:] or ["r75x0.5", "75c", "r75x1.5", "r75x2"]
    sortie = {}
    resume: list[tuple[str, int, int, int, float, float]] = []

    for nom in noms:
        cfg = connus[nom]
        r = marges(cfg)
        ref = pm.profil(cfg)                          # 🔴 GARDE-FOU
        assert np.array_equal(r["adm_tp"], ref["adm_tp"]), (
            f"{nom}: adm_tp rederive DIFFERE de profil_monitorabilite -- "
            "recurrence fautive, ne pas lire les marges")

        m = r["marge"]
        best = np.nanmax(np.where(r["adm_tp"], m, np.nan), axis=1)
        arg = np.nanargmax(np.where(r["adm_tp"], m, -np.inf), axis=1)
        n_lam_ok = (np.where(r["adm_tp"], m, 0.0) >= SEUIL_PREUVE).sum(axis=1)

        print("=" * 78)
        print(f"{nom} — {r['N']} couches, A = {r['A']:.2e} en unites de T, "
              f"seuil de preuve {SEUIL_PREUVE} A (§24-41)")
        print("=" * 78)
        sous = [int(i) for i in range(r["N"]) if not (best[i] >= SEUIL_PREUVE)]
        print(f"  couches dont la MEILLEURE marge est sous {SEUIL_PREUVE} A : "
              f"{len(sous)} / {r['N']}")
        if sous:
            print("  🔴 CES COUCHES SONT INEVITABLES -- aucune strategie ne peut les contourner :")
            for i in sous[:20]:
                print(f"     couche {i:>3} : meilleure marge {best[i]:>8.3f} A  "
                      f"(a {r['lams'][arg[i]]:.0f} nm)  swing max {r['swing'][i].max():.4f}  "
                      f"lambda >= seuil : {n_lam_ok[i]}")
            print("\n  🔑 IMPOSSIBILITE ETABLIE sur le signal seul, sans aucune graine.")
        else:
            print("  🟢 aucune couche bloquante : la condition necessaire NE conclut PAS.")
            ordre = np.argsort(best)
            print("  les 10 couches les plus exposees :")
            for i in ordre[:10]:
                print(f"     couche {int(i):>3} : meilleure marge {best[i]:>8.3f} A  "
                      f"(a {r['lams'][arg[i]]:.0f} nm)  lambda >= seuil : {n_lam_ok[i]}")
        print(f"\n  marge la plus faible du profil : {np.nanmin(best):.3f} A  "
              f"| mediane : {np.nanmedian(best):.3f} A")

        bl = blocs_minimaux(r["adm_tp"])
        muettes = int((r["adm_tp"].sum(axis=1) == 0).sum())
        print(f"  couches MUETTES (aucune lambda) : {muettes} / {r['N']}")
        print(f"  blocs MINIMUM pour couvrir      : {len(bl)}  "
              f"(lambda communes : min {min(n for _, _, n in bl)}, "
              f"med {int(np.median([n for _, _, n in bl]))})")
        resume.append((nom, int(r["N"]), muettes, len(bl),
                       float(np.nanmin(best)), float(np.nanmedian(best))))

        sortie[nom] = {
            "N": int(r["N"]), "A": r["A"], "seuil": SEUIL_PREUVE,
            "couches_muettes": muettes,
            "blocs_minimum": len(bl),
            "blocs": [[int(a), int(b), int(n)] for a, b, n in bl],
            "meilleure_marge_par_couche": [float(x) for x in best],
            "lambda_du_max": [float(r["lams"][k]) for k in arg],
            "n_lambda_au_dessus_du_seuil": [int(x) for x in n_lam_ok],
            "couches_bloquantes": sous,
        }

    # 🔑 LE TABLEAU QUI DECIDE : les grandeurs ordonnent-elles la serie d'echelle ?
    print("\n" + "=" * 78)
    print("LES GRANDEURS DU SIGNAL NOMINAL ORDONNENT-ELLES LA SERIE ?")
    print("=" * 78)
    print(f"  {'composant':<10} {'couches':>8} {'muettes':>8} {'blocs min':>10} "
          f"{'marge mini':>12} {'marge med':>11}")
    print("  " + "-" * 62)
    for nom, N, mu, nb, mn, md in resume:
        print(f"  {nom:<10} {N:>8} {mu:>8} {nb:>10} {mn:>11.1f}A {md:>10.1f}A")
    print("\n  rappel de l'issue MESUREE (une seule graine, cf. §24-46) :")
    print("    r75x0.5  ECHOUE   0/375   crash_min  48 %")
    print("    75c      passe  241/662   crash_min   0 %   SEEL 0,272")
    print("    r75x1.5  limite   1/704   crash_min   0 %   SEEL 0,63")
    print("    r75x2    ECHOUE   0/404   crash_min 100 %")
    print("\n  Si une colonne place x0.5 et x2 aux extremes et 75c/x1.5 au milieu, elle")
    print("  ordonne la serie. Sinon elle ne predit rien, et le 99c n'y etait pour rien.")

    out = ROOT / "reports" / "marge_atteignable.json"
    out.write_text(json.dumps(sortie, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nconsigne dans {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
