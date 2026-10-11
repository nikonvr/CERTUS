"""What the STRAT window shows before any file is loaded: the settings of the real machine.

Moved as it stood out of `CertusStratStateMixin.set_default_values` (`certus_strat_ui_state.py`): data, not state. The
window writes these values into its widgets through `populate_gui_from_config`, the path a loaded file takes too.
"""

from __future__ import annotations

from typing import Any

from certus.core.certus_strat_core import (
    SYM_DEFAULT_CONTINUITY_WEIGHT,
    SYM_DEFAULT_EXTREMA_WINDOW_OT,
    SYM_DEFAULT_SAME_WL_BONUS,
    SYM_DEFAULT_SCORING_MODE,
    SYM_DEFAULT_TIE_EPS_ABS,
    SYM_DEFAULT_TIE_EPS_REL,
    SYM_DEFAULT_WEIGHT,
)

#: The example stack the window opens on, in quarter-wave multiples.
_EXAMPLE_STACK = "0.376863,0.544274,0.525625,2.014363,1.404237,1.260913,2.108868,1.619996,1.661556,1.051359,1.410965,0.96871,1.000151,0.812025,0.723532,0.679077,0.749945,0.697612,0.590237,0.654072,0.756165,0.854369,0.892505,1.147616,0.196934,0.801568,0.692039,0.793093,0.732264,0.62781,0.700873,0.742287,0.74316,0.161261,1.028982,1.563076,0.726649,0.325847,0.844091,0.496665,0.585217,0.149928,0.54806,0.302789,0.439372,1.355508"


def default_settings() -> dict[str, Any]:
    """The values `set_default_values` writes into the widgets, keyed by setting."""
    multipliers = [m.strip() for m in _EXAMPLE_STACK.split(",")]
    return {
        "h_type_custom": True,
        "l_type_custom": True,
        "nH_r": "2.3",
        "nL_r": "1.45",
        "substrate_choice": "Custom",
        "nSub_custom": "1.73",
        "l0": "1500.0",
        "stack_multipliers": multipliers,
        "wl_range_start": "1200.0",
        "wl_range_end": "1700.0",
        "wl_step": "0.2",
        "scan_wl_min": "1200.0",
        "scan_wl_max": "1700.0",
        "scan_wl_step": "2.0",
        "dynamics_threshold": "0.025",
        "min_transmission_floor": "0.10",
        "iter_divider_start": "10",
        "iter_divider_end": "3",
        "mc_runs_block": "100",
        "trigger_tolerance": "0.1",
        "noise_distribution": "gaussian",
        "non_monotonic_mode": "attenuate",
        "sim_thickness_probe_offset_ratio": "80.0",
        "robustness_noise_factors": "0.5,1,2",
        "robustness_num_runs": "150",
        "execution_mode": "premium",
        "non_monotonic_error_factor": "2.0",
        "wavelength_change_penalty": "1.2",
        "force_first_layer_same_wl": False,
        "nucleation_mc_runs": "40",
        "mining_candidates_limit": "3000",
        # ── MACHINE MODEL: the six error sources, 2026-08-12 ──────────
        #
        # 🔴 THE DEFAULTS ARE THOSE OF THE REAL MACHINE, not neutral values.
        # An empty or zero field would describe a perfect instrument that does not exist,
        # and that is precisely what 👤 asked to correct: "I do not want to be optimistic
        # about the slits but realistic", "the index biases must always be active, it is
        # the basis", "rate is the general case".
        "slit_bias_enabled": "1",
        "monochromator_resolution_nm": "2.0",
        "search_resolution": "1",
        "index_corridor": "0.005",
        "photometric_curvature_amp": "0.00375",
        "allow_rate": "1",
        # The one that stays INACTIVE: the smoothing, because the OMS algorithms are
        # not known.
        "reading_smoothing_window": "1",
        "witness_reset_layers": "",
        "n_screen_runs": "25",
        "k_keep_survivors": "10",
        "top_k_parents": "20",
        "max_fusions_per_parent": "5",
        "phase_a_scan_limit": "300",
        "nucleation_max_rmse": "1.5",
        "nucleation_degradation": "1.4",
        "sym_enable": "1",
        "sym_weight": f"{SYM_DEFAULT_WEIGHT}",
        "sym_same_wl_bonus": f"{SYM_DEFAULT_SAME_WL_BONUS}",
        "sym_extrema_window": f"{SYM_DEFAULT_EXTREMA_WINDOW_OT}",
        "sym_continuity_weight": f"{SYM_DEFAULT_CONTINUITY_WEIGHT}",
        "sym_adaptive_same_wl": "1",
        "sym_allow_hybrid": "0",
        "sym_prefer_on_tie": "1",
        "sym_tie_epsilon": f"{SYM_DEFAULT_TIE_EPS_ABS}",
        "sym_tie_epsilon_rel": f"{SYM_DEFAULT_TIE_EPS_REL}",
        "sym_scoring_mode": SYM_DEFAULT_SCORING_MODE,
        "show_plots": True,
        "export_excel": True,
    }
