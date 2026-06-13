"""Reusable physics bridge for CERTUS_DESIGN workers.

This module centralizes the oblique objective / gradient logic so worker
classes can stay thin and the same kernels can be reused by a future headless
service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from certus.core.certus_core import CFG, NUMERICAL_FAULT_EXCEPTIONS
from certus_physics import (
    calc_spectrum_full_oblique_exact,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
    compute_gradient_all_layers_analytic,
    compute_oblique_gradient_contrib_analytic,
    compute_oblique_rt_and_grads_analytic,
    cost_numba_fast,
)

from certus.workers.certus_design_worker_utils import optim_calc_oblique_selected


@dataclass
class DesignPhysicsBridge:
    """Centralized helper for design objective and gradient evaluation.

    This bridge keeps the numerical paths used by the workers in one place so
    future refactors can reuse the same TMM evaluation code without copying the
    objective / gradient logic into each worker class.
    """
    var_idx: np.ndarray
    all_variable: bool
    ep0: np.ndarray
    oblique_mode: bool
    has_back_calc: bool
    has_back_stack: bool
    d_back: np.ndarray
    n_back_T: np.ndarray
    n_layers_T: np.ndarray
    n_sub: np.ndarray
    wls: np.ndarray
    tgt_vals: Any
    tgt_weights: Any
    oblique_configs: list[dict[str, Any]]
    ep_buffer: np.ndarray | None = None

    def _build_ep(self, x: np.ndarray) -> np.ndarray:
        if self.all_variable:
            return np.ascontiguousarray(x)
        if self.ep_buffer is None:
            self.ep_buffer = np.array(self.ep0, dtype=np.float64, copy=True)
        self.ep_buffer[:] = self.ep0
        self.ep_buffer[self.var_idx] = x
        return self.ep_buffer

    def objective(self, x: np.ndarray) -> Any:
        if len(x) != len(self.var_idx):
            return 1e30
        ep_buffer = self._build_ep(x)
        if np.any((ep_buffer > 1e-12) & (ep_buffer < CFG.MIN_THICKNESS)):
            return 1e30
        if self.oblique_mode:
            return self.compute_oblique_error(ep_buffer)
        return cost_numba_fast(
            ep_buffer,
            self.n_layers_T,
            self.n_sub,
            self.wls,
            self.tgt_vals,
            self.tgt_weights,
            CFG.MIN_THICKNESS,
            self.has_back_calc,
            self.n_back_T,
            self.d_back,
        )

    def gradient(self, x: np.ndarray) -> tuple[Any, np.ndarray]:
        if len(x) != len(self.var_idx):
            return 1e30, np.zeros(len(self.var_idx), dtype=np.float64)
        ep_full = self._build_ep(x)
        violations = (ep_full > 1e-12) & (ep_full < CFG.MIN_THICKNESS)
        if np.any(violations):
            return 1e30, np.zeros(len(self.var_idx), dtype=np.float64)
        if self.oblique_mode:
            return self.compute_oblique_error_and_grad_analytic(ep_full)
        return compute_gradient_all_layers_analytic(
            ep_full,
            self.n_layers_T,
            self.n_sub,
            self.wls,
            self.tgt_vals,
            self.tgt_weights,
            CFG.MIN_THICKNESS,
            self.has_back_calc,
            self.n_back_T,
            self.d_back,
            self.var_idx,
        )

    def compute_oblique_error(self, ep_test: np.ndarray) -> Any:
        total_err = 0.0
        total_weight = 0.0
        for config in self.oblique_configs:
            R_config, T_config = optim_calc_oblique_selected(
                config["wls_config"],
                config["n_layers_T_config"],
                ep_test,
                config["n_sub_config"],
                config["angle"],
                config["pol"],
                has_back_calc=self.has_back_calc,
                has_back_stack=self.has_back_stack,
                d_back=self.d_back,
                n_back_T=self.n_back_T,
                calc_spectrum_full_oblique_exact=calc_spectrum_full_oblique_exact,
                calc_spectrum_oblique_backside_vectorized=calc_spectrum_oblique_backside_vectorized,
                calc_spectrum_oblique_vectorized=calc_spectrum_oblique_vectorized,
            )
            sw_cfg = config["sw_cfg"]
            for tgt_data in config["targets"]:
                local_positions = tgt_data["local_positions"]
                vals = R_config[local_positions] if tgt_data["target_type"] == "R" else T_config[local_positions]
                sw = sw_cfg[local_positions]
                err = np.sum(sw * (vals - tgt_data["tgt_vals"]) ** 2) * tgt_data["weight"]
                total_err += err
                total_weight += tgt_data["weight"] * np.sum(sw)
        return 1e30 if total_weight < 1e-12 else total_err / total_weight

    def compute_oblique_error_and_grad_analytic(self, ep_test: np.ndarray) -> tuple[Any, np.ndarray]:
        total_err = 0.0
        total_weight = 0.0
        grad_raw = np.zeros(len(self.var_idx), dtype=np.float64)
        for config in self.oblique_configs:
            wls_cfg = config["wls_config"]
            n_layers_cfg = config["n_layers_T_config"]
            n_sub_cfg = config["n_sub_config"]
            sw_cfg = config["sw_cfg"]
            for tgt_data in config["targets"]:
                local_positions = tgt_data["local_positions"]
                if local_positions.size == 0:
                    continue
                wls_sel = wls_cfg[local_positions]
                n_layers_sel = n_layers_cfg[local_positions, :]
                n_sub_sel = n_sub_cfg[local_positions]
                tgt_vals_sel = np.asarray(tgt_data["tgt_vals"], dtype=np.float64)
                tgt_w_sel = sw_cfg[local_positions] * float(tgt_data["weight"])
                is_reflectance = tgt_data["target_type"] == "R"
                angle = float(config["angle"])
                is_s_pol = bool(config["is_s_pol"])
                if self.has_back_calc:
                    Rf, Tf, dRf, dTf = compute_oblique_rt_and_grads_analytic(ep_test, n_layers_sel, n_sub_sel, wls_sel, self.var_idx, angle, is_s_pol, False)
                    Rf_prime, T_front_rev, dRf_prime, dT_front_rev = compute_oblique_rt_and_grads_analytic(ep_test, n_layers_sel, n_sub_sel, wls_sel, self.var_idx, angle, is_s_pol, True)
                    if self.has_back_stack:
                        n_back_sel = self.n_back_T[config["all_clues"], :][local_positions, :]
                        Rb_prime, Tb, _, _ = compute_oblique_rt_and_grads_analytic(self.d_back, n_back_sel, n_sub_sel, wls_sel, np.zeros(0, dtype=np.int64), angle, is_s_pol, True)
                    else:
                        Rb_prime, Tb, _, _ = compute_oblique_rt_and_grads_analytic(np.zeros(0, dtype=np.float64), np.zeros((len(wls_sel), 0), dtype=np.complex128), n_sub_sel, wls_sel, np.zeros(0, dtype=np.int64), angle, is_s_pol, True)
                    D = np.maximum(1.0 - Rf_prime * Rb_prime, 1e-12)
                    D2 = D * D
                    if is_reflectance:
                        y_vals = Rf + (Tf * T_front_rev * Rb_prime) / D
                        dy = dRf + ((Rb_prime[:, None] * (dTf * T_front_rev[:, None] + Tf[:, None] * dT_front_rev)) / D[:, None] + ((Tf * T_front_rev * (Rb_prime * Rb_prime))[:, None] * dRf_prime / D2[:, None]))
                    else:
                        y_vals = (Tf * Tb) / D
                        dy = Tb[:, None] * (dTf / D[:, None] + (Tf[:, None] * Rb_prime[:, None] * dRf_prime) / D2[:, None])
                    diff = y_vals - tgt_vals_sel
                    sw = sw_cfg[local_positions]
                    weight = float(tgt_data["weight"])
                    total_err += np.sum(sw * diff * diff) * weight
                    total_weight += weight * np.sum(sw)
                    grad_raw += np.sum((sw[:, None] * diff[:, None] * dy), axis=0) * weight
                else:
                    err_sum, grad_contrib, weight_sum = compute_oblique_gradient_contrib_analytic(
                        ep_test,
                        n_layers_sel,
                        n_sub_sel,
                        wls_sel,
                        tgt_vals_sel,
                        tgt_w_sel,
                        angle,
                        is_s_pol,
                        bool(is_reflectance),
                        self.var_idx,
                    )
                    total_err += err_sum
                    total_weight += weight_sum
                    grad_raw += grad_contrib
        if total_weight < 1e-12:
            return 1e30, np.zeros(len(self.var_idx), dtype=np.float64)
        return total_err / total_weight, (2.0 / total_weight) * grad_raw
