"""Axe 1.1 — ce que le bruit de LECTURE du signal de monitoring change, avant de
lancer le pipeline complet.

Le pipeline STRAT sur le juge de paix coute 970 s. Avant de le payer deux fois, on
mesure au NIVEAU DU NOYAU, sur l'empilement reel du dichroique 48 couches, ce que
`poem_anchor_noise` fait aux trois modes de defaillance. Sans Qt, sans pipeline :
quelques secondes.

    .venv/Scripts/python.exe scripts/probe_anchor_noise.py

Deux experiences.

A. CONTROLEE, couche par couche. Historique NOMINAL (aucune erreur amont) et bruit
   d'ARRET NUL. Dans ces conditions, sans bruit de lecture, aucun run ne peut
   planter par comptage divergent : `Ts_r` et `Ts_n` sont le meme signal. Tout
   plantage observe est donc IMPUTABLE AU SEUL BRUIT DE LECTURE, et on le mesure en
   fonction de la PROFONDEUR D'HISTORIQUE du bloc — ce qui repond a la question qui
   decide de la validite du modele : le taux depend-il de la physique, ou de la
   densite d'echantillonnage du balayage ?

B. REALISTE, empilement entier. `simulate_stack_robustness_batch` avec le bruit
   Sobol de production, sur des strategies monochromatiques, drapeau ferme puis
   ouvert. Donne l'ordre de grandeur du taux de plantage que la Phase B verra.

N'ecrit rien hors reports/. Ne touche a aucun code de production.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

OUT = ROOT / "reports" / "probe_anchor_noise.json"
EXAMPLE = ROOT / "example" / "example_strat" / "JSON-strat-example.json"

#: Sentinelle « depot non terminable » rendue par simulate_growth_kernel.
CRASH = 1e5


def emit(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


# --------------------------------------------------------------------------- #
# L'empilement reel, reconstruit comme le fait la production
# --------------------------------------------------------------------------- #


def load_stack() -> dict:
    from certus.core.certus_strat_config import get_refractive_clues_vectorized
    from certus.physics.certus_material_db import MaterialDatabase
    from certus.workers.certus_strat_workers import _resolve_strat_indices_db_path

    cfg = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    db = MaterialDatabase(_resolve_strat_indices_db_path())

    l0 = float(cfg["l0"])
    mult = [float(m) for m in cfg["stack_multipliers"]]
    nH_id = cfg["h_material_file"]
    nL_id = cfg["l_material_file"]
    nSub_id = cfg["substrate_choice"]

    l0_arr = np.array([l0], dtype=np.float64)
    nH_l0 = float(np.real(get_refractive_clues_vectorized(nH_id, l0_arr, db_instance=db)[0]))
    nL_l0 = float(np.real(get_refractive_clues_vectorized(nL_id, l0_arr, db_instance=db)[0]))

    # Meme formule que certus/utils/certus_strat_service.py:521.
    p_thick = np.array(
        [(m * l0) / (4.0 * (nH_l0 if (i % 2) == 0 else nL_l0)) for i, m in enumerate(mult)],
        dtype=np.float64,
    )

    scan = np.arange(float(cfg["scan_wl_min"]), float(cfg["scan_wl_max"]) + 1e-9, float(cfg["scan_wl_step"]))
    nH = get_refractive_clues_vectorized(nH_id, scan, db_instance=db).astype(np.complex128)
    nL = get_refractive_clues_vectorized(nL_id, scan, db_instance=db).astype(np.complex128)
    nSub = get_refractive_clues_vectorized(nSub_id, scan, db_instance=db).astype(np.complex128)

    emit(f"empilement : {p_thick.size} couches, l0={l0:.0f} nm, nH({l0:.0f})={nH_l0:.4f} nL={nL_l0:.4f}")
    emit(f"balayage   : {scan.size} lambda de {scan[0]:.0f} a {scan[-1]:.0f} nm")
    emit(f"tolerance  : trigger_tolerance={cfg['trigger_tolerance']} (% de T)")
    return {
        "cfg": cfg,
        "p_thick": p_thick,
        "scan": scan,
        "nH": nH,
        "nL": nL,
        "nSub": nSub,
        "trigger_tolerance": float(cfg["trigger_tolerance"]),
    }


# --------------------------------------------------------------------------- #
# A. Le plantage induit par le seul bruit de lecture, par profondeur d'historique
# --------------------------------------------------------------------------- #

#: Profondeurs d'historique de bloc examinees. 0 = premiere couche d'un bloc (aucun
#: historique relu), 4 = plafond MAX_LOOKBACK, c'est-a-dire le regime de toute
#: couche situee a l'interieur d'un bloc de plus de quatre couches — donc le cas
#: courant sur le juge de paix, dont la meilleure strategie n'a que cinq blocs.
DEPTHS = (0, 1, 2, 4)
N_DRAWS = 64


def experiment_a(S: dict) -> dict:
    """La regle d'admissibilite, appliquee a toute la grille de balayage.

    👤 « Une longueur d'onde de controle de la couche i (i > 1) est INTERDITE si,
    lorsque le signal est bruite, il y a un risque de mal comptabiliser le nombre de
    turning points ou de ne pas s'arreter au niveau voulu. »

    Conditions choisies pour que la mesure ne porte QUE sur cette question :
    historique NOMINAL (donc aucune erreur amont pour deplacer un extremum) et bruit
    d'ARRET nul. Sans bruit de lecture, `Ts_r` et `Ts_n` sont alors le meme signal et
    le taux de plantage est nul par construction. Tout ce qu'on mesure ici est donc
    imputable au seul bruit de lecture.

    Sortie principale : le NOMBRE de longueurs d'onde encore admissibles par couche.
    C'est le chiffre qui dit si la Phase A trie encore quelque chose.

    ⚠️ `N_DRAWS` tirages ne resolvent pas le seuil de 0,107 % par couche : le plus
    petit taux non nul mesurable vaut 1/N_DRAWS. « Admissible » signifie donc ici
    « ZERO plantage sur N_DRAWS tirages », ce qui est une BORNE SUPERIEURE de
    l'ensemble admissible — la vraie Phase A, avec ses propres tirages, sera au moins
    aussi severe.
    """
    from certus_physics import simulate_growth_kernel as K

    p_thick = S["p_thick"]
    scan, nH, nL, nSub = S["scan"], S["nH"], S["nL"], S["nSub"]
    n_layers = p_thick.size
    scale = S["trigger_tolerance"] / 100.0  # meme sigma que la lecture d'arret
    tol = 1.0 - (1.0 - 0.05) ** (1.0 / n_layers)

    emit("")
    emit("  A. LA REGLE D'ADMISSIBILITE, SUR TOUTE LA GRILLE DE BALAYAGE")
    emit(f"     {scan.size} lambda au pas de {scan[1] - scan[0]:.0f} nm x {n_layers - 1} couches (i > 1)")
    emit("     historique nominal, bruit d'arret NUL -> sans bruit de lecture, 0 % par construction")
    emit(f"     seuil par couche : 1-(1-0,05)^(1/{n_layers}) = {tol:.3%}")
    emit(f"     resolution de la sonde : 1/{N_DRAWS} = {1.0 / N_DRAWS:.2%} -> « admissible » = ZERO plantage")
    emit("")

    # Sans bruit : temoin. Doit rendre 0 partout, sinon la mesure ne veut rien dire.
    off_bad = 0
    for i_layer in range(1, n_layers):
        for j in range(scan.size):
            v = K(
                p_thick, i_layer, p_thick[:i_layer], float(scan[j]),
                nH[j], nL[j], nSub[j], 2.0, 0.0, 1.0, 0, max(0, i_layer - 4), 0.0, 0, 0,
            )[0]
            off_bad += int(v > CRASH)
    n_cells = (n_layers - 1) * scan.size
    emit(f"     temoin drapeau FERME, profondeur 4 : {off_bad}/{n_cells} plantages ({off_bad / n_cells:.2%})")

    per_depth: dict[int, dict] = {}
    emit("")
    emit("     prof | lambda admissibles par couche : min  median  max | couches sans aucune | plantage moyen")
    for depth in DEPTHS:
        adm_counts = []
        crash_sum = 0.0
        for i_layer in range(1, n_layers):
            blk = max(0, i_layer - depth)
            prev = p_thick[:i_layer]
            n_adm = 0
            for j in range(scan.size):
                wl = float(scan[j])
                nh, nl, ns = nH[j], nL[j], nSub[j]
                bad = 0
                for r in range(N_DRAWS):
                    v = K(p_thick, i_layer, prev, wl, nh, nl, ns, 2.0, 0.0, 1.0, 0, blk, scale, 4242, r)[0]
                    if v > CRASH:
                        bad += 1
                crash_sum += bad / N_DRAWS
                if bad == 0:
                    n_adm += 1
            adm_counts.append(n_adm)
        a = np.array(adm_counts, dtype=np.int64)
        per_depth[depth] = {
            "admissible_min": int(a.min()),
            "admissible_median": float(np.median(a)),
            "admissible_max": int(a.max()),
            "layers_with_none": int((a == 0).sum()),
            "mean_crash_rate": crash_sum / n_cells,
            "per_layer": a.tolist(),
        }
        d = per_depth[depth]
        emit(
            f"     {depth:4d} | {d['admissible_min']:5d} {d['admissible_median']:7.0f} {d['admissible_max']:5d}"
            f"   / {scan.size}      | {d['layers_with_none']:3d} / {n_layers - 1}          |"
            f" {d['mean_crash_rate']:7.2%}"
        )
    return {
        "n_draws": N_DRAWS,
        "scale": scale,
        "tolerance_per_layer": tol,
        "n_scan_wls": int(scan.size),
        "off_crash_cells": int(off_bad),
        "n_cells": int(n_cells),
        "by_depth": {str(k): v for k, v in per_depth.items()},
    }


# --------------------------------------------------------------------------- #
# B. L'empilement entier, avec le bruit Sobol de production
# --------------------------------------------------------------------------- #

WLS_B = (453.0, 466.0, 476.0, 488.0, 530.0, 551.0)
N_RUNS_B = 64


def experiment_b(S: dict) -> dict:
    from certus.core.certus_strat_robustness import (
        _get_cached_sobol_noise,
        _signal_noise_stream_seed,
    )
    from certus_physics import simulate_stack_robustness_batch as B

    p_thick = S["p_thick"]
    scan, nH, nL, nSub = S["scan"], S["nH"], S["nL"], S["nSub"]
    n_layers = p_thick.size
    base = S["trigger_tolerance"] / 100.0

    raw = _get_cached_sobol_noise(42, 1, N_RUNS_B, n_layers)
    noise_matrix = raw * base

    rows = []
    emit("")
    emit("  B. EMPILEMENT ENTIER, bruit Sobol de production, strategies MONOCHROMATIQUES")
    emit(f"     {N_RUNS_B} tirages, niveau nominal 1x ({base:.2e} en unites de T)")
    emit("")
    emit("     lambda | plantage OFF | plantage ON | P95 |Delta_d| OFF -> ON  (nm, runs sains)")
    for wl in WLS_B:
        j = int(np.argmin(np.abs(scan - wl)))
        lw = np.full(n_layers, wl, dtype=np.float64)
        nHv = np.full(n_layers, nH[j], dtype=np.complex128)
        nLv = np.full(n_layers, nL[j], dtype=np.complex128)
        nSv = np.full(n_layers, nSub[j], dtype=np.complex128)

        out = {}
        for tag, sc, sd in (
            ("off", None, 0),
            ("on", np.full(n_layers, base, dtype=np.float64), _signal_noise_stream_seed(42, 1)),
        ):
            sim, _ = B(p_thick, lw, nHv, nLv, nSv, noise_matrix, 2.0, 1.0, 0, sc, sd)
            bad = np.any(sim > CRASH, axis=1)
            ok = sim[~bad]
            p95 = float(np.percentile(np.abs(ok - p_thick[None, :]), 95)) if ok.size else float("nan")
            out[tag] = {"crash": float(bad.mean()), "p95_nm": p95}
        rows.append({"wl": wl, **out})
        emit(
            f"     {wl:6.0f} | {out['off']['crash']:12.1%} | {out['on']['crash']:11.1%} | "
            f"{out['off']['p95_nm']:8.3f} -> {out['on']['p95_nm']:8.3f}"
        )
    return {"n_runs": N_RUNS_B, "rows": rows}


def experiment_c(S: dict) -> dict:
    """Comment le taux depend-il de sigma ? C'est ce qui distingue physique et artefact.

    Si le plantage vient de bascules de signe a UN echantillon au voisinage du sommet,
    son taux suit la probabilite qu'un point du balayage tombe a moins de
    sigma/pente du sommet — donc a peu pres LINEAIREMENT en sigma. Un mecanisme
    physique de fond (extremum reellement noye dans le bruit) saturerait au contraire.

    Les facteurs 0,5 / 1 / 2 sont ceux que la Phase B applique deja
    (`robustness_noise_factors`), donc ces trois lignes sont des chiffres de
    production ; 0,1 est ajoute comme point de levier.
    """
    from certus_physics import simulate_growth_kernel as K

    p_thick = S["p_thick"]
    scan, nH, nL, nSub = S["scan"], S["nH"], S["nL"], S["nSub"]
    n_layers = p_thick.size
    base = S["trigger_tolerance"] / 100.0

    emit("")
    emit("  C. DEPENDANCE EN SIGMA, profondeur d'historique 4")
    emit("     facteur | sigma (T) | plantage moyen | lambda admissibles / couche (median)")
    rows = []
    for factor in (0.1, 0.5, 1.0, 2.0):
        scale = base * factor
        crash_sum = 0.0
        adm = []
        for i_layer in range(1, n_layers):
            blk = max(0, i_layer - 4)
            prev = p_thick[:i_layer]
            n_adm = 0
            for j in range(scan.size):
                wl = float(scan[j])
                nh, nl, ns = nH[j], nL[j], nSub[j]
                bad = 0
                for r in range(N_DRAWS):
                    v = K(p_thick, i_layer, prev, wl, nh, nl, ns, 2.0, 0.0, 1.0, 0, blk, scale, 4242, r)[0]
                    if v > CRASH:
                        bad += 1
                crash_sum += bad / N_DRAWS
                if bad == 0:
                    n_adm += 1
            adm.append(n_adm)
        n_cells = (n_layers - 1) * scan.size
        row = {
            "factor": factor,
            "scale": scale,
            "mean_crash_rate": crash_sum / n_cells,
            "admissible_median": float(np.median(adm)),
        }
        rows.append(row)
        emit(
            f"     {factor:7.1f} | {scale:9.2e} | {row['mean_crash_rate']:13.2%} |"
            f" {row['admissible_median']:6.0f} / {scan.size}"
        )
    return {"n_draws": N_DRAWS, "rows": rows}


def main() -> None:
    S = load_stack()
    res = {
        "experiment_a": experiment_a(S),
        "experiment_b": experiment_b(S),
        "experiment_c": experiment_c(S),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    emit("")
    emit(f"PROBE_WRITTEN={OUT}")


if __name__ == "__main__":
    main()
