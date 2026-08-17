"""LA RESOLUTION SPECTRALE QU'UN DESIGN EXIGE -- calculee sans strategie et sans Monte-Carlo.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\probe_resolution_exigee.py [composant ...]

👤 2026-08-17 : *« le but ultime serait d'arriver a predire sans tout calculer si un design peut
passer avec un seul verre ou pas »*, puis *« je me pose aussi la question de la resolution
spectrale : un filtre trop epais a des pics en transmission et peut-etre que le filtre serait
monitorable en resolution 1 nm et pas 2 nm »*.

## Ce que cette sonde calcule, et pourquoi c'est le meilleur candidat restant

`_calculate_strategy_spectral_resolution` (`certus_strat_robustness.py:626`) calcule deja, POUR
UNE STRATEGIE, la resolution spectrale la plus large que la courbure tolere :

    second_diff = (T(lam - B/2) + T(lam + B/2))/2 - T(lam)      avec B = 1 nm
    res_limit   = B * sqrt(3 * T_tolerance / |second_diff|)     T_tolerance = 5e-4

Elle est evaluee COUCHE PAR COUCHE sur l'empilement CUMULE, a la lambda de controle de la couche.
Le code ne s'en sert que comme prefiltre de variantes de fente, jamais comme verdict de design.

🔑 On peut la rendre INDEPENDANTE DE TOUTE STRATEGIE : pour chaque couche, prendre la PLUS GRANDE
res_limit sur toutes les lambda ADMISSIBLES -- c'est le meilleur cas atteignable pour cette couche
-- puis le MINIMUM sur les couches, qui est la couche qui contraint le design.

    Si ce minimum est sous 0,5 nm -- la resolution la plus fine que la machine offre (§19) --
    alors AUCUNE strategie ne peut satisfaire cette couche, et le design n'est pas monitorable.

C'est une condition NECESSAIRE, calculee sans un seul tirage, et qui integre les indices par
construction : contrairement a un seuil en micrometres, elle ne depend pas du materiau.

## Ce que la mesure du 2026-08-17 rend cette piste plausible

    x2   toutes les fentes autres que 2 nm ecartees par la courbure, pour 100 % des strategies
         (log [SLIT] : "saute par la courbure : 5 nm x32, 1 nm x32, 0.5 nm x32")
    x0,5 5 nm ecarte SYSTEMATIQUEMENT, 1 nm partiellement, 0,5 nm admis
         et le plantage AGGRAVE quand on affine : 48 % -> 84 % -> 94 %

Donc la courbure decide reellement de quelles resolutions sont utilisables, et elle varie d'un
composant a l'autre. Reste a savoir si elle ORDONNE la serie d'echelle.

## Le test, et le critere de reussite ecrit d'avance

La serie d'echelle du random75 est la seule experience controlee du projet (75 couches, structure
et materiaux identiques, seule l'epaisseur optique varie) :

    x0,5   Somme QWOT  57,4   ECHOUE   crash_min  48 %
    x1                114,9   passe    crash_min   0 %
    x1,5              172,3   limite   crash_min   0 %   1 deposable sur 704
    x2                229,8   ECHOUE   crash_min 100 %

    REUSSITE : res_lim doit etre CONFORTABLE a x1, se degrader a x1,5, et passer sous 0,5 nm
    a x2. Elle n'a PAS a expliquer x0,5, dont l'echec n'est pas un probleme de resolution --
    x0,5 admet 0,5 nm sans peine et echoue quand meme.

    ECHEC : si res_lim n'ordonne pas x1 / x1,5 / x2, la cinquieme route se ferme et il faudra
    la propagation d'erreur simulee, qui n'est plus « predire sans tout calculer ».

⚠️ CE QUE LA SONDE NE DIT PAS. C'est une condition NECESSAIRE, pas suffisante : une resolution
admissible ne garantit pas qu'une strategie existe. Elle borne la faisabilite par le haut.

⚠️ Et l'approximation du second ordre sur laquelle repose `res_limit` se degrade quand la
structure spectrale devient fine devant B -- le code le mesure lui-meme, le facteur sqrt(3) passe
de 1,7321 sur une quadratique a 1,7252 sur une cosinusoide de periode 10 nm. Sur un empilement
tres epais, res_limit est donc elle-meme moins fiable, et c'est precisement la ou on l'interroge.

🔒 Aucune TMM reimplantee : `calculate_RT_vectorized_real_HL` est le chemin de production, et
l'admissibilite vient de `profil_monitorabilite.profil()` (interdit 7).
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

TEST_BW = 1.0               # B, la largeur d'essai de la difference seconde (comme le code)
FENTES_MACHINE = (5.0, 2.0, 1.0, 0.5)   # §19 -- ce que la machine offre reellement
COMPOSANTS_ECHELLE = {
    "r75x0.5": "reports/serie_echelle_r75/cfg_x0.5.json",
    "r75x1.5": "reports/serie_echelle_r75/cfg_x1.5.json",
    "r75x2": "reports/serie_echelle_r75/cfg_x2.json",
}


def _charger_pm():
    spec = importlib.util.spec_from_file_location(
        "pm", ROOT / "scripts" / "profil_monitorabilite.py")
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)
    return pm


def resolution_exigee(cfg: str, adm: np.ndarray) -> dict:
    """res_limit(couche, lambda), puis le meilleur par couche et la couche qui contraint."""
    from certus.physics.certus_opt_tmm import arange_inclusive
    from certus.physics.certus_tmm_hl import calculate_RT_vectorized_real_HL
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
    tol = float(prm.get("trigger_tolerance", 0.05)) / 100.0
    lams = np.asarray(arange_inclusive(float(prm["scan_wl_min"]), float(prm["scan_wl_max"]),
                                       float(prm.get("scan_wl_step", 2.0))), dtype=np.float64)

    # Les trois points par lambda que la difference seconde exige, en UN seul vecteur.
    demi = TEST_BW / 2.0
    wl3 = np.concatenate([np.maximum(0.1, lams - demi), lams, lams + demi])
    nH = np.asarray(get_refractive_clues_vectorized(prm["nH_id"], wl3, db_instance=db),
                    dtype=np.complex128)
    nL = np.asarray(get_refractive_clues_vectorized(prm["nL_id"], wl3, db_instance=db),
                    dtype=np.complex128)
    nS = np.asarray(get_refractive_clues_vectorized(prm["nSub_id"], wl3, db_instance=db),
                    dtype=np.complex128)
    nH0 = float(np.real(get_refractive_index(prm["nH_id"], l0, db_instance=db)))
    nL0 = float(np.real(get_refractive_index(prm["nL_id"], l0, db_instance=db)))
    d = np.array([(m * l0) / (4.0 * (nH0 if i % 2 == 0 else nL0)) for i, m in enumerate(mult)])

    nl = len(lams)
    res_lim = np.full((N, nl), np.nan)
    for i in range(N):
        _, T = calculate_RT_vectorized_real_HL(wl3, nH, nL, nS, d[: i + 1])
        T = np.asarray(T, dtype=np.float64)
        sd = (T[:nl] + T[2 * nl:]) / 2.0 - T[nl:2 * nl]
        courbure = np.abs(sd)
        with np.errstate(divide="ignore", invalid="ignore"):
            r = TEST_BW * np.sqrt(3.0 * tol / courbure)
        r[courbure <= 1e-9] = 100.0        # plate : aucune contrainte, comme le code
        res_lim[i] = r

    # Le meilleur cas ATTEIGNABLE par couche : la plus grande res_limit sur les lambda
    # ADMISSIBLES. Une lambda inadmissible ne peut pas servir, donc elle ne compte pas.
    masque = np.where(adm, res_lim, -np.inf)
    meilleur = masque.max(axis=1)
    meilleur[~adm.any(axis=1)] = np.nan     # couche sans aucune lambda admissible
    fini = meilleur[np.isfinite(meilleur)]
    i_contraint = int(np.nanargmin(np.where(np.isfinite(meilleur), meilleur, np.inf)))
    return {"N": N, "lams": lams, "res_lim": res_lim, "meilleur_par_couche": meilleur,
            "contrainte": float(fini.min()) if fini.size else float("nan"),
            "couche_contrainte": i_contraint,
            "mediane": float(np.median(fini)) if fini.size else float("nan")}


def main() -> int:
    import bench_examples as Bx

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    pm = _charger_pm()
    connus = {**pm.COMPOSANTS, **COMPOSANTS_ECHELLE}
    noms = sys.argv[1:] or ["r75x0.5", "75c", "r75x1.5", "r75x2", "99c", "48c", "35c"]

    print(f"{'composant':<10} {'couches':>8} {'res_lim exigee':>15} {'couche':>7} "
          f"{'mediane':>9}   fentes machine utilisables")
    print("-" * 88)
    sortie = {}
    for nom in noms:
        cfg = connus[nom]
        p = pm.profil(cfg)
        r = resolution_exigee(cfg, p["adm_tp"])
        ok = [f for f in FENTES_MACHINE if f <= r["contrainte"]]
        libelle = ", ".join(f"{f:g}" for f in ok) if ok else "🔴 AUCUNE"
        print(f"{nom:<10} {r['N']:>8} {r['contrainte']:>12.3f} nm {r['couche_contrainte']:>7} "
              f"{r['mediane']:>8.2f} nm   {libelle}")
        sortie[nom] = {
            "N": int(r["N"]),
            "resolution_exigee_nm": r["contrainte"],
            "couche_contraignante": int(r["couche_contrainte"]),
            "mediane_nm": r["mediane"],
            "fentes_machine_utilisables": ok,
            "meilleur_par_couche_nm": [None if not np.isfinite(x) else float(x)
                                       for x in r["meilleur_par_couche"]],
        }

    print("\n  Rappel des issues MESUREES sur la serie d'echelle (graine 42) :")
    print("    r75x0.5  ECHOUE   crash_min  48 %      75c      passe   crash_min   0 %")
    print("    r75x1.5  limite   crash_min   0 %      r75x2    ECHOUE  crash_min 100 %")
    print("\n  REUSSITE si res_lim est confortable a x1, se degrade a x1,5, et passe sous")
    print("  0,5 nm a x2. Elle n'a PAS a expliquer x0,5, qui admet 0,5 nm et echoue quand meme.")

    out = ROOT / "reports" / "resolution_exigee.json"
    out.write_text(json.dumps(sortie, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nconsigne dans {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
