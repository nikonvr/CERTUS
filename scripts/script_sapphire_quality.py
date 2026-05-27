"""

Fit quality test on RTNBrel-sapphire.xlsx

Simulates the CERTUS pipeline: Phase 1 TLU (<=2200nm) then Phase 2 Spline (full range).

"""



import sys
from pathlib import Path

import numpy as np

import pandas as pd

import time

import scipy.optimize

import logging



sys.path.insert(0, str(Path(__file__).resolve().parent.parent))



from CERTUS_INDEX import (

    SplineOptimizationWorker,

    SplineObjective,

    get_nk_from_spline,

    calculate_RT_single_layer_backside_array,

    get_n_substrate_array_by_id,

    SUBSTRATES,

    DataType,

    OptimizationConfig,

    substrateMode,

    PGlobalOptimizerINDEX,

    IndexObjective,

)

from certus_physics import (

    epsilon2_TLU_array,

    epsilon1_TL_analytic,

    epsilon_to_nk,

)

from certus.core.certus_core import HC_EV_NM



logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

logger = logging.getLogger("test_sapphire")





def rmse_fn(calc, target):

    return np.sqrt(np.mean((calc - target) ** 2))





def test_sapphire_quality_run():

    # ═══════════════════════════════════════════════════════════

    # 1. Load complete data

    # ═══════════════════════════════════════════════════════════

    df_full = pd.read_excel(r"example/example_index/H400-RTNBrel-sapphire.xlsx")

    df_full.columns = ["lambda", "R", "T"]

    df_full["R"] /= 100.0

    df_full["T"] /= 100.0

    df_full = df_full.sort_values("lambda").reset_index(drop=True)



    wls_full = df_full["lambda"].to_numpy()

    df_full["T"].to_numpy()

    df_full["R"].to_numpy()



    logger.info(

        f"Complete data:{len(wls_full)} points, lambda=[{wls_full.min():.0f}, {wls_full.max():.0f}] nm"

    )





# ═══════════════════════════════════════════════════════════

# 2. Phase 1 TLU sur <=2200nm

# ═══════════════════════════════════════════════════════════

sub_id = SUBSTRATES["Sapphire (Al2O3)"]["id"]

n_sub_full = get_n_substrate_array_by_id(sub_id, wls_full)



mask_tlu = wls_full <= 2200.0

wls_tlu = wls_full[mask_tlu]

target_T_tlu = target_T_full[mask_tlu]

target_R_tlu = target_R_full[mask_tlu]

n_sub_tlu = n_sub_full[mask_tlu]



df_tlu = df_full[mask_tlu].copy()



logger.info(

    f"Phase 1 TLU: {len(wls_tlu)} points, lambda=[{wls_tlu.min():.0f}, {wls_tlu.max():.0f}] nm"

)



config = OptimizationConfig(

    target_data=df_tlu,

    substrate="Sapphire (Al2O3)",

    substrate_mode=substrateMode.STANDARD,

    data_type=DataType.BOTH,

    thickness_min=2000.0,

    thickness_max=4000.0,

    lambda_min=wls_tlu.min(),

    lambda_max=wls_tlu.max(),

    use_normalized=True,

    weight_T=1.0,

    weight_R=1.0,

    high_precision=False,

)



logger.info("Lancement Phase 1 TLU (PGlobal)...")

t0 = time.time()



obj_tlu = IndexObjective(config, logger=logger)

bounds_tlu = obj_tlu.get_bounds()



optimizer = PGlobalOptimizerINDEX(

    objective=obj_tlu,

    bounds=bounds_tlu,

    n_workers=1,

    log_clues=None,

)

best_sample = optimizer.optimize(max_iter=30)



elapsed_tlu = time.time() - t0

logger.info(f"Phase 1 TLU completed in{elapsed_tlu:.1f}s")



if best_sample is None:

    logger.error("Phase 1 TLU failed")

    sys.exit(1)



    # Extract TLU results

    tlu_res = obj_tlu.package_results(best_sample.x, best_sample.y)

    thickness_tlu = tlu_res.optimal_thickness

    tlu_params = tlu_res.tlu_params



    E_arr = HC_EV_NM / wls_full

    e2 = epsilon2_TLU_array(

        E_arr, tlu_params.Eg, tlu_params.A, tlu_params.E0, tlu_params.C, tlu_params.Eu

    )

    e1 = epsilon1_TL_analytic(

        E_arr,

        tlu_params.Eg,

        tlu_params.A,

        tlu_params.E0,

        tlu_params.C,

        tlu_params.eps_inf,

    )

    n_tlu_full, k_tlu_full, _ = epsilon_to_nk(e1, e2, 0.5, 15.0, 15.0)



    R_tlu, T_tlu = calculate_RT_single_layer_backside_array(

        wls_full, n_tlu_full, k_tlu_full, thickness_tlu, n_sub_full

    )

    rmse_tlu = rmse_fn(

        np.concatenate([T_tlu, R_tlu]), np.concatenate([target_T_full, target_R_full])

    )

    logger.info(

        f"RMSE TLU (full range): {rmse_tlu:.6f}| thickness={thickness_tlu:.1f}nm"

    )



# ═══════════════════════════════════════════════════════════

# 3. Phase 2 Spline sur full range

# ═══════════════════════════════════════════════════════════

logger.info("=" * 60)

logger.info("Phase 2 Spline (full range 1150-5200nm)...")



IR_EXTENSION_KNOTS = SplineOptimizationWorker.IR_EXTENSION_KNOTS



# Update config with full range

config_full = OptimizationConfig(

    target_data=df_full,

    substrate="Sapphire (Al2O3)",

    substrate_mode=substrateMode.STANDARD,

    data_type=DataType.BOTH,

    thickness_min=2000.0,

    thickness_max=4000.0,

    lambda_min=wls_full.min(),

    lambda_max=wls_full.max(),

    use_normalized=True,

    weight_T=1.0,

    weight_R=1.0,

    high_precision=False,

)



knot_wls = SplineOptimizationWorker._build_knot_wavelengths_from_tlu(

    wls_full,

    n_tlu_full,

    k_tlu_full,

    lmin=wls_full.min(),

    lmax=wls_full.max(),

    num_curvature_knots=10,

    ir_extension_knots=IR_EXTENSION_KNOTS,

    logger=logger,

)

logger.info(f"Spline knots ({len(knot_wls)}): {[f'{w:.0f}' for w in knot_wls]}")



# Initialisation depuis TLU

n0 = np.interp(knot_wls, wls_full, n_tlu_full)

k0 = np.interp(knot_wls, wls_full, k_tlu_full)

x0 = np.concatenate([n0, k0])

N = len(knot_wls)



# Terminals tight VIS, wide IR (same as application)

SPLINE_TRANSITION_WL = 2200.0

nk_bounds = []

for i, ni in enumerate(n0):

    wl = knot_wls[i]

    nk_bounds.append(

        (max(1.0, ni - 0.05), ni + 0.05) if wl <= SPLINE_TRANSITION_WL else (1.0, 5.0)

    )

for i, ki in enumerate(k0):

    wl = knot_wls[i]

    nk_bounds.append(

        (max(0.0, ki - 0.01), ki + 0.01) if wl <= SPLINE_TRANSITION_WL else (0.0, 2.0)

    )



obj_spline = SplineObjective(

    wavelengths=wls_full,

    target_T=target_T_full,

    target_R=target_R_full,

    n_substrate=n_sub_full,

    data_type=DataType.BOTH,

    fixed_thickness=thickness_tlu,

    knot_wavelengths=knot_wls,

    use_normalized=True,

    weight_T=1.0,

    weight_R=1.0,

    alpha_smoothness=1.0,

)



cost_init = obj_spline(x0)

logger.info(f"Initial spline cost (from TLU): RMSE={np.sqrt(cost_init):.6f}")



t1 = time.time()

best = {"fun": cost_init, "x": x0.copy()}

iters = [0]





def callback_spline(xk):

    iters[0] += 1

    c = obj_spline(xk)

    if c < best["fun"]:

        best["fun"] = c

        best["x"] = xk.copy()

    if iters[0] % 50 == 0:

        logger.info(

            f"  iter {iters[0]:4d} | RMSE={np.sqrt(best['fun']):.6f} | evals={obj_spline.n_evals}"

        )





result = scipy.optimize.minimize(

    obj_spline,

    x0,

    method="L-BFGS-B",

    jac="2-point",

    bounds=nk_bounds,

    callback=callback_spline,

    options={"ftol": 1e-14, "gtol": 1e-10, "maxiter": 1000, "eps": 1e-7},

)



elapsed_spline = time.time() - t1

best_x = result.x if result.fun <= best["fun"] else best["x"]

best_fun = min(result.fun, best["fun"])



# ── Calcul RMSE physique final ──

n_f = best_x[:N]

k_f = best_x[N : 2 * N]

p_f = np.concatenate([n_f, k_f])

n_calc, k_calc = get_nk_from_spline(p_f, knot_wls, wls_full, use_cache=False)

R_calc, T_calc = calculate_RT_single_layer_backside_array(

    wls_full, n_calc, k_calc, thickness_tlu, n_sub_full

)



rmse_T = rmse_fn(T_calc, target_T_full)

rmse_R = rmse_fn(R_calc, target_R_full)

rmse_tot = np.sqrt((rmse_T**2 + rmse_R**2) / 2)



logger.info("=" * 60)

logger.info("FINAL RESULT COMPLETE PIPELINE")

logger.info(f"  Phase 1 TLU  : {elapsed_tlu:.1f}s | RMSE(full)={rmse_tlu:.6f}")

logger.info(f"  Phase 2 Spline: {elapsed_spline:.1f}s | {obj_spline.n_evals}evaluations")

logger.info(f"Converged:{result.success} - {result.message}")

logger.info(f"  RMSE T final : {rmse_T:.6f}")

logger.info(f"  RMSE R final : {rmse_R:.6f}")

logger.info(f"  RMSE total   : {rmse_tot:.6f}")

logger.info(f"Improvement vs TLU:{(1 - rmse_tot/rmse_tlu)*100:+.1f}%")

logger.info("=" * 60)



THRESHOLD = 0.010

if rmse_tot < THRESHOLD:

    logger.info(f"✅ OK QUALITY: RMSE={rmse_tot:.6f} < {THRESHOLD}")

else:

    logger.warning(f"❌ INSUFFICIENT QUALITY: RMSE={rmse_tot:.6f} >= {THRESHOLD}")

    assert False, f"Insufficient quality: RMSE={rmse_tot:.6f} >= {THRESHOLD}"



if __name__ == "__main__":

    test_sapphire_quality_run()

