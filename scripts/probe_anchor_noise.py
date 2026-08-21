"""Axis 1.1 — what the PLAY noise of the monitoring signal changes, before
lancer le pipeline complet.

The STRAT pipeline on the justice of the peace costs 970 s. Before paying it twice, we
measurement at the CORE LEVEL, on the real stack of the 48-layer dichroic, what
`poem_anchor_noise` does all three failure modes. Without Qt, without pipeline:
a few seconds.

    .venv/Scripts/python.exe scripts/probe_anchor_noise.py

Deux experiences.

A. CONTROLLED, layer by layer. NOMINAL history (no upstream error) and noise
   NULL STOP. Under these conditions, without reading noise, no run can
   planter par comptage divergent : `Ts_r` et `Ts_n` sont le meme signal. Tout
   observed crash is therefore attributable to READING NOISE ONLY, and we measure it in
   fonction de la PROFONDEUR D'HISTORIQUE du bloc — ce qui repond a la question qui
   decide de la validite du modele : le taux depend-il de la physique, ou de la
   densite d'echantillonnage du balayage ?

B. REALISTIC, entire stack. `simulate_stack_robustness_batch` with noise
   Sobol de production, sur des strategies monochromatiques, drapeau ferme puis
   ouvert. Donne l'ordre de grandeur du taux de plantage que la Phase B verra.

Does not write anything except reports/. Do not touch any production codes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

#: Block history depths examined. 0 = first layer of a block (none
#: history reread), 4 = MAX_LOOKBACK ceiling, that is to say the regime of all
#: layer located inside a block of more than four layers — therefore the case
#: running on the justice of the peace, whose best strategy has only five blocks.
DEPTHS = (0, 1, 2, 4)
N_DRAWS = 64


def experiment_a(S: dict) -> dict:
    """La regle d'admissibilite, appliquee a toute la grille de balayage.

    👤 “A control wavelength of layer i (i > 1) is PROHIBITED if,
    when the signal is noisy, there is a risk of incorrectly counting the number of
    turning points ou de ne pas s'arreter au niveau voulu. »

    Conditions chosen so that the measure ONLY concerns this question:
    NOMINAL history (so no upstream error to move an extremum) and noise
    zero STOP. Without reading noise, `Ts_r` and `Ts_n` are then the same signal and
    the crash rate is zero by construction. Everything we measure here is therefore
    imputable au seul bruit de lecture.

    Main output: the NUMBER of wavelengths still admissible per layer.
    This is the number that says if Phase A is still sorting anything.

    ⚠️ `N_DRAWS` prints do not resolve the threshold of 0.107% per layer: the most
    small measurable non-zero rate is worth 1/N_DRAWS. “Admissible” therefore means here
    “ZERO crashes on N_DRAWS draws”, which is an UPPER BOUND of
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

    #Without noise: witness. Must return 0 everywhere, otherwise the measurement means nothing.
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
#B. The entire stack, with production sound Sobol
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
    """How does the rate depend on sigma? This is what distinguishes physics and artifact.

    Si le plantage vient de bascules de signe a UN echantillon au voisinage du sommet,
    son taux suit la probabilite qu'un point du balayage tombe a moins de
    sigma/vertex slope — so roughly LINEARLY in sigma. A mechanism
    physique de fond (extremum reellement noye dans le bruit) saturerait au contraire.

    The factors 0.5 / 1 / 2 are those that Phase B already applies
    (`robustness_noise_factors`), so these three lines are numbers of
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
