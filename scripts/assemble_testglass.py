"""MULTI-TEMOINS : assembler A + B + C et noter la PIECE, sans refaire un seul tirage.

    .venv\\Scripts\\python.exe scripts\\assemble_testglass.py

👤 2026-08-15 : *« il faut memoriser les epaisseurs des tirages de A, B et C pour recalculer
sur tout le design A-B-C »*, et *« il ne faut pas refaire de tirages, on utilise ceux
memorises ! »*.

CE QUE FAIT CE SCRIPT, et pourquoi c'est la bonne mesure. Trois campagnes sont deposees sur
un temoin NEUF chacune -- c'est ce que voit le faisceau. La PIECE, elle, ne quitte pas le
plateau et recoit les 99 couches. Le script prend donc les epaisseurs REELLEMENT simulees de
chaque campagne, les concatene tirage par tirage, et note le spectre de l'assemblage.

🔴 AUCUN TIRAGE N'EST REFAIT. Refaire un tirage introduirait un alea neuf et detruirait
exactement ce qu'on veut mesurer : l'accumulation des erreurs COMMISES par les trois
campagnes, sans compensation croisee entre elles.

🔑 MEME GRAINE POUR LES TROIS, ET C'EST DELIBERE. `index_seed` est une fonction pure de la
graine : trois campagnes de meme graine partagent donc la realisation du corridor d'indice.
C'est la physique d'UN SEUL depot -- les materiaux sont les memes dans la machine, seul le
MONITORING repart a zero. Trois graines independantes moyenneraient une erreur systematique
qui, en realite, est commune aux 99 couches, et rendraient un SEEL trop beau.

CE QUE LE RESULTAT DIT, ET CE QU'IL NE DIT PAS :
  * il dit le SEEL SPECTRAL de la piece assemblee ;
  * il ne dit AUCUN taux de plantage -- aucune simulation de monitoring ne tourne sur
    l'assemblage. La faisabilite s'etablit campagne par campagne (chacune doit tenir sous
    5 %), le spectre s'etablit ici. Confondre les deux est l'erreur de la journee.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as B  # noqa: E402
from certus.physics.certus_strat_batch import compute_batch_rmse  # noqa: E402
from CERTUS_STRAT import CertusStratApp  # noqa: E402

PARTS = ("A", "B", "C")
FULL = "example/example_strat/JSON-strat-bandpass-5cav-99c.json"
SEED = 42
CRASH_TOL = 0.05


def _nominal_thicknesses(prm: dict) -> np.ndarray:
    """Epaisseurs nominales, derivees EXACTEMENT comme le pipeline.

    `collect_params` ne rend pas `p_thick_nominal` : il est calcule en aval a partir des
    multiplicateurs et de `l0` (`certus_strat_pipeline.py:52-62`). On reprend la meme
    formule, sans la reinventer -- une QWOT est `m * l0 / (4 n)`, avec n = nH aux indices
    PAIRS et nL aux impairs, ce qui est la convention de parite du noyau.
    """
    from certus.utils.certus_strat_service import get_refractive_index  # noqa: PLC0415

    got = prm.get("p_thick_nominal")
    if got is not None:
        return np.asarray(got, dtype=np.float64)
    l0 = float(prm["l0"])
    mult = [float(e) for e in str(prm["stack_string"]).split(",") if e.strip()]
    # La base de materiaux voyage DANS les params -- meme resolution que la production
    # (`certus_strat_robustness.py:425`). Ne jamais coder un indice en dur : il depend de
    # la longueur d'onde et du fichier de materiau charge.
    db = prm.get("materials_db_instance") or prm.get("materials_db")
    nH0 = get_refractive_index(prm["nH_id"], l0, db_instance=db)
    nL0 = get_refractive_index(prm["nL_id"], l0, db_instance=db)
    return np.array([(m * l0) / (4.0 * np.real(nH0 if i % 2 == 0 else nL0))
                     for i, m in enumerate(mult)], dtype=np.float64)


def run_part(cfg: str, mode: str = "fast") -> tuple[dict, dict]:
    """Un run complet. Rend (strategie deposable, params effectifs)."""
    B.qapp()
    B.autoanswer_dialogs(True)
    app = CertusStratApp()
    app.load_configuration(str(ROOT / cfg))
    if "execution_mode" in getattr(app, "widgets", {}):
        app.widgets["execution_mode"].setCurrentText(mode)

    over = {"show_plots": False, "robustness_seed": SEED,
            "monochromator_resolution_nm": 2.0, "search_resolution": False}
    _collect = app.collect_params
    seen = {"n": 0}

    def collect(*a, **kw):
        p = _collect(*a, **kw)
        p.update(over)
        seen["n"] += 1
        return p

    app.collect_params = collect
    params = app.collect_params()
    app.run_workflow(23)
    res = B.wait_for(app.worker) if getattr(app, "worker", None) else None
    if seen["n"] < 2:
        raise SystemExit(f"{cfg}: run_workflow n'a pas appele collect_params, surcharges non appliquees")

    strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
    if not strats:
        raise SystemExit(f"{cfg}: RESULT=None")

    # 🔴 PAS strats[0]. Sur le sous-empilement B, la strategie la mieux notee plante a 98 %
    # alors que 54 autres ne plantent jamais. On prend ce qu'un operateur DEPOSERAIT : la
    # mieux notee PARMI CELLES QUI TIENNENT sous la tolerance.
    ok = [s for s in strats if float(s.get("crash_rate", 1.0)) < CRASH_TOL]
    if not ok:
        raise SystemExit(
            f"{cfg}: aucune strategie sous {CRASH_TOL:.0%} de plantage. "
            f"L'assemblage n'aurait aucun sens -- cette campagne n'est pas deposable."
        )
    ok.sort(key=lambda s: float(s.get("robustness_score", 1e18)))
    best = ok[0]
    print(f"   {cfg.split('/')[-1]:<38} {len(strats):4d} strategies, "
          f"{len(ok):3d} deposables | retenue : plantage {float(best['crash_rate']):.1%}, "
          f"score {float(best.get('robustness_score', 0)):.5f}")
    return best, params


def thicknesses(strat_result: dict) -> np.ndarray:
    """Les epaisseurs simulees, (n_tirages, n_couches), au niveau de bruit NOMINAL."""
    per_noise = strat_result.get("results_per_noise") or []
    if not per_noise:
        raise SystemExit("pas de results_per_noise : impossible de recuperer les tirages")
    # Le niveau nominal est celui de facteur 1.0 ; a defaut, le median.
    chosen = min(per_noise, key=lambda r: abs(float(r.get("noise_level", 1.0)) - 1.0))
    th = chosen.get("thicknesses_all")
    if not th:
        raise SystemExit("thicknesses_all absent : le resultat ne conserve pas les tirages")
    return np.asarray(th, dtype=np.float64)


def main() -> int:
    print("=" * 78)
    print("ASSEMBLAGE MULTI-TEMOINS  --  A + B + C notes comme UNE piece de 99 couches")
    print("=" * 78)
    print(f"\nGraine commune {SEED} : les trois campagnes partagent la realisation d'indice.\n")

    parts, params_by_part = {}, {}
    for p in PARTS:
        best, prm = run_part(f"example/example_strat/JSON-strat-99c-part{p}.json")
        parts[p] = thicknesses(best)
        params_by_part[p] = prm

    shapes = {p: parts[p].shape for p in PARTS}
    print("\nEpaisseurs recuperees :", shapes)
    n_runs = min(s[0] for s in shapes.values())
    total = sum(s[1] for s in shapes.values())
    if total != 99:
        raise SystemExit(f"les trois parties font {total} couches, pas 99")

    assembled = np.concatenate([parts[p][:n_runs] for p in PARTS], axis=1)
    print(f"Assemblage : {assembled.shape}  ({n_runs} tirages x {total} couches)")
    return _score(assembled, n_runs)


def _score(assembled: np.ndarray, n_runs: int) -> int:
    """Note l'assemblage par le code qui note toutes les strategies du projet."""
    from certus.core.certus_strat_robustness import _index_stream_seed  # noqa: PLC0415

    B.qapp()
    app = CertusStratApp()
    app.load_configuration(str(ROOT / FULL))
    prm = app.collect_params()

    from certus.physics.certus_tmm_hl import calculate_RT_vectorized_real_HL  # noqa: PLC0415
    from certus.physics.certus_opt_tmm import arange_inclusive  # noqa: PLC0415

    wl0, wl1 = prm["wl_range"]
    wl = arange_inclusive(wl0, wl1, float(prm["wl_step"]))
    from certus.utils.certus_strat_service import get_refractive_clues_vectorized  # noqa: PLC0415
    db = prm.get("materials_db_instance") or prm.get("materials_db")
    nH = np.asarray(get_refractive_clues_vectorized(prm["nH_id"], wl, db_instance=db), dtype=np.complex128)
    nL = np.asarray(get_refractive_clues_vectorized(prm["nL_id"], wl, db_instance=db), dtype=np.complex128)
    nS = np.asarray(get_refractive_clues_vectorized(prm["nSub_id"], wl, db_instance=db), dtype=np.complex128)
    nom = _nominal_thicknesses(prm)

    # 🔴 LE CONTROLE QUI VALIDE L'ASSEMBLAGE, AVANT TOUT CHIFFRE. Les epaisseurs NOMINALES
    # des trois parties, concatenees, doivent rendre le spectre nominal du 99c. Si l'ordre,
    # la parite ou un decalage est faux, ca echoue ICI, a cout nul, au lieu de contaminer
    # le resultat.
    # ⚠️ Ce controle a d'abord ete ecrit comme `T(nom)` contre `T(nom.copy())` -- une
    # TAUTOLOGIE, qui ne pouvait que passer. Un faux controle est pire que pas de controle :
    # il donne la confiance sans la verification. Le vrai controle compare la CONCATENATION
    # des trois parties au 99c.
    nom_parts = []
    for part in PARTS:
        a2 = CertusStratApp()
        a2.load_configuration(str(ROOT / f"example/example_strat/JSON-strat-99c-part{part}.json"))
        nom_parts.append(_nominal_thicknesses(a2.collect_params()))
    nom_cat = np.concatenate(nom_parts)
    print(f"\nControle de l'assemblage : {[len(x) for x in nom_parts]} couches -> {nom_cat.size}")
    if nom_cat.size != nom.size:
        raise SystemExit(f"assemblage {nom_cat.size} couches contre {nom.size} attendues")
    ecart = float(np.max(np.abs(nom_cat - nom)))
    print(f"  ecart max sur les epaisseurs nominales : {ecart:.3e} nm")
    if ecart > 1e-9:
        raise SystemExit("les epaisseurs concatenees ne reproduisent PAS le 99c")

    _, T_nom = calculate_RT_vectorized_real_HL(wl, nH, nL, nS, nom)
    _, T_cat = calculate_RT_vectorized_real_HL(wl, nH, nL, nS, nom_cat)
    d_spec = float(np.max(np.abs(T_nom - T_cat)))
    print(f"  ecart max sur le spectre nominal       : {d_spec:.3e}")
    if d_spec > 1e-12:
        raise SystemExit("le spectre de l'assemblage differe du 99c nominal")

    # 🔑 LE 7e ARGUMENT N'EST PAS UN TABLEAU DE PARITE, c'est la matrice des indices PAR
    # COUCHE ET PAR LONGUEUR D'ONDE, (n_wl, n_couches), exactement comme la production la
    # construit (`certus_strat_robustness.py:2460-2467`). Et nH/nL y sont passes VIDES,
    # puisque l'information est deja dans la matrice.
    parity = np.arange(nom.size) % 2 == 0
    n_layers_matrix = np.where(parity[np.newaxis, :], nH[:, np.newaxis], nL[:, np.newaxis])
    vide = np.empty(0, dtype=np.complex128)
    rmse = compute_batch_rmse(
        assembled, wl.astype(np.float64), vide, vide,
        nS.astype(np.complex128), T_nom, n_layers_matrix, None,
        index_corridor=float(prm.get("index_corridor", 0.0) or 0.0),
        index_seed=_index_stream_seed(int(SEED), 1),
        corridor_wl_min=float(wl[0]), corridor_wl_max=float(wl[-1]),
    )
    p95 = float(np.percentile(rmse, 95))
    seel = 2.0 * np.sqrt(p95)
    print("\n" + "=" * 78)
    print(f"PIECE ASSEMBLEE  --  {n_runs} tirages")
    print("=" * 78)
    print(f"  RMSE P95 : {p95:.6f}")
    print(f"  SEEL     : {seel:.3f} nm")
    print(f"\n  reperes : 48c 0,17 nm | 35c 0,53 nm | cible posee par 👤 : 0,3 nm")
    print("  ⚠️ Ce SEEL est SPECTRAL. Il ne porte aucun taux de plantage : la faisabilite")
    print("     a ete etablie campagne par campagne, chacune sous 5 %.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
