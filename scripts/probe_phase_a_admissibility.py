"""Prouve que la regle d'admissibilite de la Phase A n'est plus muette.

On controle results_fast (rmse, std, crash_rate, gain) pour fabriquer trois
regimes — inert filter, sorting filter, total filter — and we check that
each leaves a legible trace, layer by layer.
"""
import logging
import sys
from pathlib import Path

import numpy as np

#Root of the repository deduced from the location of THIS file (scripts/..).
#NEVER code an absolute path here: several copies of the repository coexist
# sur la machine, et un chemin en dur ferait mesurer l'autre copie (CLAUDE.md §5.5).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from certus.utils import certus_strat_service as svc

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

N_CAND = 20
WLS = [450.0 + 2.0 * i for i in range(N_CAND)]
CLUES = {w: {"H": 2.30 + 0j, "L": 1.46 + 0j, "substrate": 1.46 + 0j} for w in WLS}


def make_results(crash_rates, gains):
    out = np.zeros((N_CAND, 4), dtype=np.float64)
    out[:, 0] = np.linspace(0.5, 1.5, N_CAND)  # rmse
    out[:, 1] = 0.1                            # std
    out[:, 2] = crash_rates
    out[:, 3] = gains
    return out


def run(label, crash_rates, gains, n_layers=48):
    svc._PhysicsBridge.validate_wavelengths = staticmethod(
        lambda *a, **k: make_results(crash_rates, gains)
    )
    svc._PhysicsBridge.update_run_states = staticmethod(
        lambda *a, **k: np.zeros((4, 1), dtype=np.float64)
    )
    params = {
        "reality_sim_params": {"trigger_tolerance": 0.5},
        "non_monotonic_error_factor": 2.0,
        "probe_offset_ratio": 0.0,
        "l0": 550.0,
        "nH_id": "x",
        "phase_a_seed": 42,
    }
    print(f"\n--- {label} ---")
    res, _ = svc._validate_candidates_phase_a(
        candidates=[{"wl": w} for w in WLS],
        i_layer=7,
        num_runs=4,
        p_thick_nominal=[100.0] * n_layers,
        clues_at_wl=CLUES,
        params=params,
        run_states=[{"p_thick_sim": [100.0] * 7} for _ in range(4)],
        layer_noise_array=np.zeros(4),
    )
    st = params["phase_a_admissibility_stats"][-1]
    print(f"    -> survivantes rendues={len(res)}  stats={st}")
    return st


#crash_tol for 48 layers = 1-(1-0.05)^(1/48) = 0.1068%
tol = 1.0 - (1.0 - 0.05) ** (1.0 / 48)
print(f"seuil par couche (48 couches) = {tol:.5%}")

# 1) filtre INERTE : tout le monde passe largement
run("filtre inerte (tous sous le seuil)", np.full(N_CAND, tol / 10), np.full(N_CAND, 0.5))

#2) filter which SORTS: half above the threshold, 3 with gain<0
cr = np.where(np.arange(N_CAND) < 10, tol / 10, tol * 5)
gn = np.where(np.arange(N_CAND) < 3, -1.0, 0.5)
run("filtre qui trie (regime intermediaire)", cr, gn)

#3) TOTAL filter: no one passes -> fallback to the minimum rate
run("filtre total (repli sur le min)", np.linspace(tol * 2, tol * 9, N_CAND), np.full(N_CAND, 0.5))
