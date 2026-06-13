RE_THICKNESS_SEARCH_RADIUS_PCT = 5


# RE TRF stopping tolerances (stricter than SciPy defaults; both phases).


RE_TRF_FTOL = 1e-11


RE_TRF_GTOL = 1e-8


# Legacy aliases (historic name was L-BFGS-B; solver is now TRF).


RE_LBFGSB_FTOL = RE_TRF_FTOL


RE_LBFGSB_GTOL = RE_TRF_GTOL


# Phase 2 (REWorker): FD step on spline-knot amplitudes (not Re %); RE_SPLINE_KNOTS_NM after numpy import.


RE_PHASE2_SPLINE_FD_STEP = 5e-5


# FD step (nm) for the optimizable wavelength of interior knot index 1 (second knot).


RE_PHASE2_LAM2_FD_STEP = 0.25


# RE phase 2a: L-BFGS-B on spline amplitudes only (thicknesses fixed to phase-1 end) before joint phase 2b.


# Set to 0 in cfg key ``re_phase2_spline_prefit_maxiter`` to skip.


RE_PHASE2_SPLINE_PREFIT_MAXITER = 45


# FD on spline / lambda2: if True, forward-difference Jacobian (~half the MSE evals vs centered)  faster phase 2a/2b.


RE_PHASE2_ONESIDED_SPLINE_FD = True


# Parallel FD (ThreadPoolExecutor): MSE blocks are independent  helps unless BLAS already uses all cores.


# If slow or CPU-saturated: set False or RE_PHASE2_FD_MAX_WORKERS=1, or OMP_NUM_THREADS=1.


RE_PHASE2_FD_PARALLEL = True


RE_PHASE2_FD_MAX_WORKERS = 0  # 0 -> min(8, os.cpu_count())


# Max L-BFGS-B iterations for the joint phase-2b optimization (ep + splines + lambda₂).


# Overridable in cfg via key ``re_phase2b_maxiter``.


RE_PHASE2B_MAXITER = 400


# Phase 2a prefit uses looser convergence (good init is enough; exact convergence wastes time).


# FTOL and GTOL for prefit = RE_LBFGSB_FTOL * factor, RE_LBFGSB_GTOL * factor.


RE_PHASE2A_PREFIT_TOL_FACTOR = 50.0


# Phase 4: beam (average +/-h); ap(lambda) in N steps (RE_P4_BEAM_N_KNOTS); 1D scan + joint TRF (expensive).


RE_PHASE4_APERTURE_SCAN_POINTS = 24


# 0 = scan only (fast). >0 = joint TRF polish (each nfev ~= one full FD Jacobian build).


RE_PHASE4_TRF_MAX_NFEV = 48


RE_PHASE4_TRF_TOL_FACTOR = 35.0


# Bounds (deg) on beam width at each wavelength knot (phase 4 chromatic aperture).


# Reduced zone: stepwise search on [1.0, 2.5] (override possible: cfg re_phase4_ap_bounds_deg).


RE_P4_BEAM_AP_BOUNDS_DEG = (1.0, 2.5)


RE_GUI_DEFAULT_BEAM_APERTURE_DEG = 0.5 * (RE_P4_BEAM_AP_BOUNDS_DEG[0] + RE_P4_BEAM_AP_BOUNDS_DEG[1])


# Finite-difference step (deg) on aperture knots for phase-4 TRF Jacobian block.


RE_P4_AP_FD_STEP_DEG = 1.0e-3


# Number of lambda knots (and ap opening steps) in phase 4 - independent ap, non-monotonic.


RE_P4_BEAM_N_KNOTS = 4


RE_RESULT_LABEL_WITH_DRIFT = "Deltaln(lambda) trap + splines Re(H,L)"


# Phase 2b: Re(substrate) = a0 + a1(lambdaref/lambda)2 + a2(lambdaref/lambda)4 ; tube |nn_tab| <=  at worker wavelengths.


RE_SUB_CAUCHY_TUBE_DELTA = 0.02


RE_SUB_CAUCHY_BARRIER_SQRT_W = 250.0


RE_PHASE2_SUB_CAUCHY_FD_STEP = 1e-5


# ---------------------------------------------------------------------------


# RE preset base (optimal batch): env ×0.5 or ×1, HL √(w)=4,  QWOT 0.05, Tikhonov 1, Cauchy substrate,


# RMSE _ref 0.05, iterations 85 / 45 / 110. GUI exposes only Slow / Medium / Fast (see RE_SPEED_PRESETS).


# ---------------------------------------------------------------------------


RE_GUI_DEFAULT_RE_ENV_FULL_SCALE = False  # False = low x0.5 envelope, True = full x1


RE_PRESET_ENVELOPE_SCALE = 0.5 if not RE_GUI_DEFAULT_RE_ENV_FULL_SCALE else 1.0


RE_GUI_DEFAULT_RE_QWOT_ALPHA = 0.05


# Fixed alpha for RMSE* = sqrt(RMSE_sp^2 + alpha_ref * RMS(delta Q)^2)  ranking across runs (raw QWOT, no dead zone).


RE_RANKING_ALPHA_REF = 0.05


# Pipeline partial best (stopped batch): p1ms2_p2tk3_p3sh4, RMSE* ~0.012781  see re_pipeline_best_partial.json


RE_GUI_DEFAULT_RE_PHASE1_RESTARTS = 2


RE_GUI_DEFAULT_RE_PHASE2_TOP_K = 3


RE_GUI_DEFAULT_RE_PHASE3_SHAKES = 4


RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV = 1.0


# Max TRF iterations (Medium preset = batch #1).


RE_GUI_DEFAULT_RE_PHASE1_MAXITER = 85


RE_GUI_DEFAULT_RE_PHASE2B_MAXITER = 110


# Regularization on Delta Re splines **H and L only** (not substrate): at each knot,


# r_k = sqrt(w)*(Delta Re_k / env(lambda_k))^2 -> LS cost scales ~ w * sum (Delta Re/env)^4.


# Config stores sqrt(w) directly, not w = (re_hl_delta_re_reg_sqrt_w)^2.


RE_HL_DELTA_RE_REG_SQRT_W = 0.4


# Dead zone: |Delta Re| <= eps -> no H/L penalty; same |Delta QW| <= eps for QWOT term (absolute units).


RE_RE_DEADZONE_DELTA_RE_ABS = 0.01


RE_RE_DEADZONE_QWOT_ABS = 0.01


RE_SPLINE_CORREC_KINDS = frozenset(("spline", "spline_cached", "spline_sub3", "spline_cached_sub3"))


# Substrate: no H/L-style Delta Re penalty; optional Cauchy fit inside the tube only.


RE_GUI_DEFAULT_SUBSTRATE_CAUCHY_OPT = True


# If |RMSE_sum_1 - RMSE_sum_2| <= tol * max(|RMSE_sum_1|, eps), keep only one phase-1 candidate for phase 2.


RE_PHASE2_TOP_K_MERGE_REL_TOL = 1e-6


# Speed presets (RE GUI only). Medium = same budget as optimal batch (RE_GUI_* defaults).


# Slow / Fast: more or less exploration (multistarts, top-K, shakes, maxiter); physics unchanged.


RE_SPEED_PRESETS = {
    "medium": {
        "radius": float(RE_THICKNESS_SEARCH_RADIUS_PCT),
        "re_envelope_scale": float(RE_PRESET_ENVELOPE_SCALE),
        "re_qwot_penalty_weight": float(RE_GUI_DEFAULT_RE_QWOT_ALPHA),
        "re_enable_qwot_penalty": True,
        "re_ranking_alpha_ref": float(RE_RANKING_ALPHA_REF),
        "re_phase2b_substrate_cauchy": bool(RE_GUI_DEFAULT_SUBSTRATE_CAUCHY_OPT),
        "re_refine_h": True,
        "re_refine_l": True,
        "re_phase1_multistarts": int(RE_GUI_DEFAULT_RE_PHASE1_RESTARTS),
        "re_phase2_top_k": int(RE_GUI_DEFAULT_RE_PHASE2_TOP_K),
        "re_phase3_shake_rounds": int(RE_GUI_DEFAULT_RE_PHASE3_SHAKES),
        "re_phase2_spline_prefit_maxiter": int(RE_PHASE2_SPLINE_PREFIT_MAXITER),
        "re_spline_tikhonov_scale": float(RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV),
        "re_hl_delta_re_reg_sqrt_w": float(RE_HL_DELTA_RE_REG_SQRT_W),
        "re_phase2_skip_spline_prefit": False,
        "re_qwot_per_phase_schedule": True,
        "re_qwot_adaptive_init_scale": False,
        "re_phase1_de_maxiter": 0,
        "re_phase1_maxiter": int(RE_GUI_DEFAULT_RE_PHASE1_MAXITER),
        "re_phase2b_maxiter": int(RE_GUI_DEFAULT_RE_PHASE2B_MAXITER),
        "re_phase4_aperture_scan_points": int(RE_PHASE4_APERTURE_SCAN_POINTS),
        "re_phase4_trf_max_nfev": int(RE_PHASE4_TRF_MAX_NFEV),
    },
    "fast": {
        "radius": float(RE_THICKNESS_SEARCH_RADIUS_PCT),
        "re_envelope_scale": float(RE_PRESET_ENVELOPE_SCALE),
        "re_qwot_penalty_weight": float(RE_GUI_DEFAULT_RE_QWOT_ALPHA),
        "re_enable_qwot_penalty": True,
        "re_ranking_alpha_ref": float(RE_RANKING_ALPHA_REF),
        "re_phase2b_substrate_cauchy": bool(RE_GUI_DEFAULT_SUBSTRATE_CAUCHY_OPT),
        "re_refine_h": True,
        "re_refine_l": True,
        "re_phase1_multistarts": 1,
        "re_phase2_top_k": 1,
        "re_phase3_shake_rounds": 0,
        "re_phase2_spline_prefit_maxiter": 24,
        "re_spline_tikhonov_scale": float(RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV),
        "re_hl_delta_re_reg_sqrt_w": float(RE_HL_DELTA_RE_REG_SQRT_W),
        "re_phase2_skip_spline_prefit": False,
        "re_qwot_per_phase_schedule": True,
        "re_qwot_adaptive_init_scale": False,
        "re_phase1_de_maxiter": 0,
        "re_phase1_maxiter": 50,
        "re_phase2b_maxiter": 72,
        "re_phase4_aperture_scan_points": 12,
        "re_phase4_trf_max_nfev": 0,
    },
    "slow": {
        "radius": float(RE_THICKNESS_SEARCH_RADIUS_PCT),
        "re_envelope_scale": float(RE_PRESET_ENVELOPE_SCALE),
        "re_qwot_penalty_weight": float(RE_GUI_DEFAULT_RE_QWOT_ALPHA),
        "re_enable_qwot_penalty": True,
        "re_ranking_alpha_ref": float(RE_RANKING_ALPHA_REF),
        "re_phase2b_substrate_cauchy": bool(RE_GUI_DEFAULT_SUBSTRATE_CAUCHY_OPT),
        "re_refine_h": True,
        "re_refine_l": True,
        "re_phase1_multistarts": 4,
        "re_phase2_top_k": 5,
        "re_phase3_shake_rounds": 8,
        "re_phase2_spline_prefit_maxiter": 60,
        "re_spline_tikhonov_scale": float(RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV),
        "re_hl_delta_re_reg_sqrt_w": float(RE_HL_DELTA_RE_REG_SQRT_W),
        "re_phase2_skip_spline_prefit": False,
        "re_qwot_per_phase_schedule": True,
        "re_qwot_adaptive_init_scale": False,
        "re_phase1_de_maxiter": 0,
        "re_phase1_maxiter": 120,
        "re_phase2b_maxiter": 160,
        "re_phase4_aperture_scan_points": 40,
        "re_phase4_trf_max_nfev": 96,
    },
}


# Wavelength grid for RMSE / EVAL: one point per active measurement target (Excel RE).


RE_OPTIM_POINTS_PER_TARGET = 1


