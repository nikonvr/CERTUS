# =============================================================================
# CERTUS FIELD - Asynchronous workers
# =============================================================================
from __future__ import annotations

import logging
import traceback
import numpy as np
from typing import Iterable, Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from certus.workers.certus_field_workers_dto import FieldWorkerRequest, FieldWorkerResult, FieldParamsDTO
from certus.core.certus_core import get_physical_core_count
from certus.core.certus_field_core import calculate_electric_field, calculate_opt_metrics
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState

try:
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

_MAX_COST = 1e30


def _coerce_sequence(values: Iterable[float] | None, *, name: str) -> list[float]:
    if values is None:
        raise ValueError(f"Missing parameter: {name}")
    seq = list(values)
    if not seq:
        raise ValueError(f"Empty parameter: {name}")
    return seq


def _normalize_layer_types(layer_types: Iterable[int] | None, n_layers: int) -> list[int]:
    if layer_types is None:
        return [i % 2 for i in range(n_layers)]
    layer_types_list = list(layer_types)
    if len(layer_types_list) != n_layers:
        return [i % 2 for i in range(n_layers)]
    return [0 if int(v) == 0 else 1 for v in layer_types_list]


def _safe_metric_value(value: float) -> float:
    if value is None or not np.isfinite(value):
        return _MAX_COST
    return float(value)


def top_level_objective_function(
    p: np.ndarray | list[float], 
    n1_rs: Iterable[float], 
    n2_rs: Iterable[float], 
    nSub_rs: Iterable[float], 
    l0: float, 
    seuil_int_1: float, 
    seuil_int_2: float, 
    alpha: float, 
    integral_points: int, 
    n_supers: Iterable[float], 
    theta_inc: float = 0.0, 
    pol_flag: int = 0, 
    lambda_calcs: Iterable[float] | None = None, 
    params_layer_types: Iterable[int] | None = None,
    rmin: float = 1.0,
    rmax: float = 1.0,
    min_field_active: bool = False
) -> float:
    """Cost function for optimization, evaluated on all wavelengths."""
    try:
        lambda_calcs = _coerce_sequence(lambda_calcs, name="lambda_calcs")
        emp_factors_list = [float(v) for v in list(p)]
        if not emp_factors_list or not np.all(np.isfinite(emp_factors_list)):
            return _MAX_COST

        n_layers = len(emp_factors_list)
        params_layer_types = _normalize_layer_types(params_layer_types, n_layers)
        n_supers = _coerce_sequence(n_supers, name="n_supers")
        n1_rs = _coerce_sequence(n1_rs, name="n1_rs")
        n2_rs = _coerce_sequence(n2_rs, name="n2_rs")
        nSub_rs = _coerce_sequence(nSub_rs, name="nSub_rs")

        max_cost = 0.0
        for i, lambda_calc in enumerate(lambda_calcs):
            if i >= len(n1_rs) or i >= len(n2_rs) or i >= len(nSub_rs) or i >= len(n_supers):
                return _MAX_COST

            metrics = calculate_opt_metrics(
                n1_rs[i], n2_rs[i], nSub_rs[i], l0, emp_factors_list, params_layer_types, n_supers[i],
                int(integral_points), theta_inc, pol_flag, lambda_calc=lambda_calc
            )
            if not metrics:
                return _MAX_COST

            metric_1 = _safe_metric_value(metrics.get('max_peak_1'))
            metric_2 = _safe_metric_value(metrics.get('max_peak_2'))
            
            R_val = float(np.clip(metrics.get('R', 0.0), 0.0, 1.0))
            if abs(rmin - 1.0) < 1e-6 and abs(rmax - 1.0) < 1e-6:
                cost_R = 1.0 - R_val
            else:
                if R_val < rmin:
                    cost_R = 100.0 * (rmin - R_val) ** 2
                elif R_val > rmax:
                    cost_R = 100.0 * (R_val - rmax) ** 2
                else:
                    cost_R = 0.0

            if min_field_active:
                ratios = []
                if seuil_int_1 > 1e-9:
                    ratios.append(metric_1 / seuil_int_1)
                if seuil_int_2 > 1e-9:
                    ratios.append(metric_2 / seuil_int_2)
                cost_field = max(ratios) if ratios else 0.0
                local_cost = cost_R + alpha * cost_field
            else:
                penalty_1 = 0.0
                if seuil_int_1 > 1e-9:
                    penalty_1 = alpha * (max(0.0, metric_1 - seuil_int_1) / seuil_int_1) ** 2
                elif metric_1 > seuil_int_1:
                    penalty_1 = _MAX_COST

                penalty_2 = 0.0
                if seuil_int_2 > 1e-9:
                    penalty_2 = alpha * (max(0.0, metric_2 - seuil_int_2) / seuil_int_2) ** 2
                elif metric_2 > seuil_int_2:
                    penalty_2 = _MAX_COST

                local_cost = cost_R + penalty_1 + penalty_2

            if not np.isfinite(local_cost):
                return _MAX_COST
            max_cost = max(max_cost, local_cost)

        return float(max_cost)
    except Exception:
        logging.getLogger("certus").exception("Objective evaluation failed")
        return _MAX_COST


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(tuple)
    progress = pyqtSignal(int, str)
    progress_snapshot = pyqtSignal(object)
    plot = pyqtSignal(object, str)


class FieldWorkerThread(QThread):
    """Asynchronous worker for electric field calculations and optimization."""

    def __init__(self, request: FieldWorkerRequest):
        super().__init__()
        self.request = request
        self.signals = WorkerSignals()
        self._is_running = True
        from threading import Event
        self._stop_event = Event()

    def run(self) -> None:
        try:
            params = self.request.params
            action = self.request.action

            if action == "calculate":
                self._run_calculate(params)
            elif action == "optimize":
                self._run_optimize(params)
            elif action == "tolerate":
                self._run_tolerate(params)
            elif action == "needle":
                self._run_needle(params)
            else:
                raise ValueError(f"Unknown action: {action}")
        except Exception as e:
            traceback.print_exc()
            self.signals.error.emit((type(e).__name__, str(e), traceback.format_exc()))

    def stop(self) -> None:
        self._is_running = False
        self._stop_event.set()

    def _require_params(self, params: FieldParamsDTO) -> FieldParamsDTO:
        params = FieldParamsDTO.model_validate(params)
        params.lambda_calcs = _coerce_sequence(params.lambda_calcs, name="lambda_calcs")
        params.emp_factors = _coerce_sequence(params.emp_factors, name="emp_factors")
        params.n1_rs = _coerce_sequence(params.n1_rs, name="n1_rs")
        params.n2_rs = _coerce_sequence(params.n2_rs, name="n2_rs")
        params.nSub_rs = _coerce_sequence(params.nSub_rs, name="nSub_rs")
        params.n_supers = _coerce_sequence(params.n_supers, name="n_supers")
        params.layer_types = _normalize_layer_types(params.layer_types, len(params.emp_factors))

        n_wavelengths = len(params.lambda_calcs)
        for name, values in {
            "n1_rs": params.n1_rs,
            "n2_rs": params.n2_rs,
            "nSub_rs": params.nSub_rs,
            "n_supers": params.n_supers,
        }.items():
            if len(values) != n_wavelengths:
                raise ValueError(
                    f"Inconsistent parameter: {name} contains {len(values)} value(s) for {n_wavelengths} wavelength(s)."
                )

        if params.integral_points is None or params.integral_points < 5:
            params.integral_points = 5
        return params

    def _run_calculate(self, params: FieldParamsDTO) -> None:
        logger = logging.getLogger("certus")
        params = self._require_params(params)
        logger.info(f"Starting _run_calculate. Number of layers: {len(params.emp_factors)}, λ={params.lambda_calcs} nm")

        self.signals.progress_snapshot.emit(build_progress_snapshot(message="Calculating field...", display_ratio=0.10, progress_ratio=0.10, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="CALCULATE", is_indeterminate=True))

        import time
        t0 = time.perf_counter()
        z_coords_final = None
        E2_values_list = []
        ep_c1_cn_final = None

        for i, lambda_calc in enumerate(params.lambda_calcs):
            if not self._is_running:
                return
            z_coords, E2_values, ep_c1_cn, _, _ = calculate_electric_field(
                n1_r=params.n1_rs[i], n2_r=params.n2_rs[i], nSub_r=params.nSub_rs[i],
                l0=params.l0, lambda_calc=lambda_calc,
                emp_factors=params.emp_factors, layer_types=params.layer_types, n_superstrate_real=params.n_supers[i],
                integral_points=params.integral_points, theta_inc=params.theta_inc, pol_flag=params.pol_flag
            )
            if i == 0:
                z_coords_final = z_coords.tolist()
                ep_c1_cn_final = ep_c1_cn
            E2_values_list.append(E2_values.tolist())

        dt = time.perf_counter() - t0
        logger.debug(f"Numba analytical calculation finished in {dt:.4f}s. Points generated: {len(z_coords_final or [])}")

        self.signals.progress_snapshot.emit(build_progress_snapshot(message="Calculation finished.", display_ratio=1.0, progress_ratio=1.0, eta_seconds=0.0, confidence=1.0, state=StepState.DONE, module="FIELD", phase="CALCULATE"))
        self.signals.finished.emit(FieldWorkerResult(
            z_coords=z_coords_final or [],
            E2_values_list=E2_values_list,
            lambda_calcs=params.lambda_calcs,
            ep_c1_cn=ep_c1_cn_final or [],
            success=True,
            message="Calculation successful."
        ))

    def _run_tolerate(self, params: FieldParamsDTO) -> None:
        logger = logging.getLogger("certus")
        params = self._require_params(params)
        error_pct = float(params.tolerate_error or 0.0)
        logger.info(f"Starting _run_tolerate with error {error_pct*100}%")

        self.signals.progress_snapshot.emit(build_progress_snapshot(message="Starting Monte-Carlo...", display_ratio=0.10, progress_ratio=0.10, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="MONTE_CARLO", is_indeterminate=True))

        import time
        t0 = time.perf_counter()

        num_iterations = params.mc_iterations or 50
        n_layers = len(params.emp_factors)

        z_coords_mc = []
        E2_mc_runs = [[] for _ in params.lambda_calcs]

        z_coords_nominal = None
        E2_nominal_list = []
        ep_c1_cn_final = None

        for i, lambda_calc in enumerate(params.lambda_calcs):
            if not self._is_running:
                return
            z_coords, E2_values, ep_c1_cn, _, _ = calculate_electric_field(
                n1_r=params.n1_rs[i], n2_r=params.n2_rs[i], nSub_r=params.nSub_rs[i],
                l0=params.l0, lambda_calc=lambda_calc,
                emp_factors=params.emp_factors, layer_types=params.layer_types, n_superstrate_real=params.n_supers[i],
                integral_points=params.integral_points,
                theta_inc=params.theta_inc, pol_flag=params.pol_flag
            )
            if i == 0:
                z_coords_nominal = z_coords.tolist()
                ep_c1_cn_final = ep_c1_cn
            E2_nominal_list.append(E2_values.tolist())

        import concurrent.futures

        perturbations = np.random.normal(1.0, error_pct, (num_iterations, n_layers))

        def _mc_task(it: int) -> tuple[int, list, list]:
            if not self._is_running:
                return it, None, None
            p_emp = np.clip(np.asarray(params.emp_factors, dtype=float) * perturbations[it], 1e-4, None).tolist()
            z_c_out = None
            e2_out = []
            for j, lam in enumerate(params.lambda_calcs):
                z_coords, E2_values, _, _, _ = calculate_electric_field(
                    n1_r=params.n1_rs[j], n2_r=params.n2_rs[j], nSub_r=params.nSub_rs[j],
                    l0=params.l0, lambda_calc=lam,
                    emp_factors=p_emp, layer_types=params.layer_types, n_superstrate_real=params.n_supers[j],
                    integral_points=params.integral_points,
                    theta_inc=params.theta_inc, pol_flag=params.pol_flag
                )
                if j == 0:
                    z_c_out = z_coords.tolist()
                e2_out.append(E2_values.tolist())
            return it, z_c_out, e2_out

        # Pool non borne AVANT : ThreadPoolExecutor() prend min(32, cpu_count() + 4),
        # soit 12 threads sur une puce 4C/8T. L'ordre des resultats est retabli par
        # le tri sur `it` plus bas : la taille du pool n'influe sur aucune valeur.
        with concurrent.futures.ThreadPoolExecutor(max_workers=get_physical_core_count()) as executor:
            futures = [executor.submit(_mc_task, it) for it in range(num_iterations)]
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                if not self._is_running:
                    executor.shutdown(wait=False, cancel_futures=True)
                    return
                pct = 10 + int(80 * ((i + 1) / num_iterations))
                self.signals.progress_snapshot.emit(build_progress_snapshot(
                    message=f"Monte-Carlo {i+1}/{num_iterations}...",
                    display_ratio=pct / 100.0, progress_ratio=pct / 100.0, eta_seconds=None,
                    confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="MONTE_CARLO",
                    metadata={"iteration": i + 1, "total": num_iterations}
                ))

        results = [f.result() for f in futures]
        results.sort(key=lambda x: x[0])
        for it, z_c_iter, e2_out in results:
            if z_c_iter is None:
                continue
            z_coords_mc.append(z_c_iter)
            for j in range(len(params.lambda_calcs)):
                E2_mc_runs[j].append(e2_out[j])

        dt = time.perf_counter() - t0
        logger.info(f"Monte-Carlo {num_iterations} iterations finished in {dt:.2f}s.")

        self.signals.progress_snapshot.emit(build_progress_snapshot(message="Monte-Carlo calculation finished.", display_ratio=1.0, progress_ratio=1.0, eta_seconds=0.0, confidence=1.0, state=StepState.DONE, module="FIELD", phase="MONTE_CARLO"))
        self.signals.finished.emit(FieldWorkerResult(
            z_coords=z_coords_nominal or [],
            E2_values_list=E2_nominal_list,
            lambda_calcs=params.lambda_calcs,
            ep_c1_cn=ep_c1_cn_final or [],
            z_coords_mc=z_coords_mc,
            E2_mc_runs=E2_mc_runs,
            success=True,
            message=f"Tolerancing (±{error_pct*100:.1f}%) finished."
        ))

    def _run_needle(self, params: FieldParamsDTO) -> None:
        logger = logging.getLogger("certus")
        params = self._require_params(params)
        logger.info(f"Starting Needle Scan. Number of layers: {len(params.emp_factors)}")

        self.signals.progress_snapshot.emit(build_progress_snapshot(message="Preparing needle scan...", display_ratio=0.05, progress_ratio=0.05, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="NEEDLE_SCAN"))

        # Current stack cost
        current_cost = top_level_objective_function(
            params.emp_factors,
            params.n1_rs,
            params.n2_rs,
            params.nSub_rs,
            params.l0,
            params.seuil_int_1,
            params.seuil_int_2,
            params.alpha,
            params.integral_points,
            params.n_supers,
            params.theta_inc,
            params.pol_flag,
            params.lambda_calcs,
            params.layer_types,
            rmin=params.rmin if params.rmin is not None else 1.0,
            rmax=params.rmax if params.rmax is not None else 1.0,
            min_field_active=bool(params.min_field_active)
        )

        n_layers = len(params.emp_factors)
        
        STEP_QWOT = 0.05
        PROBE_QWOT = 0.0001

        best_res = None
        min_cost = current_cost

        # Build list of possible insertions
        candidates = []
        for i in range(n_layers):
            qwot_layer = params.emp_factors[i]
            if qwot_layer < (2 * STEP_QWOT):
                continue
            z_positions = np.arange(STEP_QWOT, qwot_layer - STEP_QWOT + 1e-9, STEP_QWOT)
            for z in z_positions:
                candidates.append((i, z))

        total_candidates = len(candidates)
        logger.info(f"Needle scan: found {total_candidates} candidate split positions.")

        if total_candidates == 0:
            self.signals.progress_snapshot.emit(build_progress_snapshot(message="Needle scan finished.", display_ratio=1.0, progress_ratio=1.0, eta_seconds=0.0, confidence=1.0, state=StepState.DONE, module="FIELD", phase="NEEDLE_SCAN"))
            self.signals.finished.emit(FieldWorkerResult(
                success=True,
                message="No candidate layers thick enough to split.",
                opt_emp_factors=params.emp_factors,
                opt_layer_types=params.layer_types,
            ))
            return

        import concurrent.futures

        def _needle_task(idx: int, lay_i: int, lay_z: float) -> tuple[int, int, float, float, list, list]:
            if not self._is_running:
                return idx, lay_i, lay_z, _MAX_COST, [], []
            emp_test = (
                params.emp_factors[:lay_i] +
                [lay_z, PROBE_QWOT, params.emp_factors[lay_i] - lay_z] +
                params.emp_factors[lay_i+1:]
            )
            type_i = params.layer_types[lay_i]
            alt_type = 1 - type_i
            types_test = (
                params.layer_types[:lay_i] +
                [type_i, alt_type, type_i] +
                params.layer_types[lay_i+1:]
            )
            cost = top_level_objective_function(
                emp_test, params.n1_rs, params.n2_rs, params.nSub_rs,
                params.l0, params.seuil_int_1, params.seuil_int_2,
                params.alpha, params.integral_points, params.n_supers,
                params.theta_inc, params.pol_flag, params.lambda_calcs,
                types_test, rmin=params.rmin if params.rmin is not None else 1.0,
                rmax=params.rmax if params.rmax is not None else 1.0,
                min_field_active=bool(params.min_field_active)
            )
            return idx, lay_i, lay_z, cost, emp_test, types_test

        # Pool non borne AVANT (12 threads sur une puce 4C/8T), cf. Monte-Carlo.
        with concurrent.futures.ThreadPoolExecutor(max_workers=get_physical_core_count()) as executor:
            futures = [executor.submit(_needle_task, idx, i, z) for idx, (i, z) in enumerate(candidates)]
            for i_f, future in enumerate(concurrent.futures.as_completed(futures)):
                if not self._is_running:
                    executor.shutdown(wait=False, cancel_futures=True)
                    return
                
                idx, lay_i, lay_z, cost, emp_test, types_test = future.result()
                
                if total_candidates <= 20 or i_f % max(1, total_candidates // 20) == 0 or i_f == total_candidates - 1:
                    pct = 5 + int(85 * (i_f / total_candidates))
                    self.signals.progress_snapshot.emit(build_progress_snapshot(
                        message=f"Needle scanning {i_f+1}/{total_candidates}...",
                        display_ratio=pct / 100.0, progress_ratio=pct / 100.0, eta_seconds=None,
                        confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="NEEDLE_SCAN",
                        metadata={"index": i_f + 1, "total": total_candidates}
                    ))
                
                if cost < min_cost:
                    min_cost = cost
                    best_res = {
                        "layer_idx": lay_i,
                        "depth_qwot": lay_z,
                        "cost": min_cost,
                        "emp_factors": emp_test,
                        "layer_types": types_test,
                    }

        self.signals.progress_snapshot.emit(build_progress_snapshot(message="Generating final metrics...", display_ratio=0.90, progress_ratio=0.90, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="FINALIZE"))
        self.signals.progress_snapshot.emit(build_progress_snapshot(message="Generating final metrics...", display_ratio=0.90, progress_ratio=0.90, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="FINAL_METRICS"))

        z_coords_final = None
        E2_values_list = []
        ep_c1_cn_final = None

        if best_res is not None:
            logger.info(
                f"Needle found beneficial insertion at layer {best_res['layer_idx']} "
                f"(depth QWOT={best_res['depth_qwot']:.4f}) with cost {best_res['cost']:.6f} "
                f"(previous cost: {current_cost:.6f})"
            )
            for i, lambda_calc in enumerate(params.lambda_calcs):
                z_coords, E2_values, ep_c1_cn, _, _ = calculate_electric_field(
                    n1_r=params.n1_rs[i], n2_r=params.n2_rs[i], nSub_r=params.nSub_rs[i],
                    l0=params.l0, lambda_calc=lambda_calc,
                    emp_factors=best_res["emp_factors"], layer_types=best_res["layer_types"], n_superstrate_real=params.n_supers[i],
                    integral_points=params.integral_points, theta_inc=params.theta_inc, pol_flag=params.pol_flag
                )
                if i == 0:
                    z_coords_final = z_coords.tolist()
                    ep_c1_cn_final = ep_c1_cn
                E2_values_list.append(E2_values.tolist())

            self.signals.progress_snapshot.emit(build_progress_snapshot(message="Needle scan completed.", display_ratio=1.0, progress_ratio=1.0, eta_seconds=0.0, confidence=1.0, state=StepState.DONE, module="FIELD", phase="NEEDLE_SCAN"))
            self.signals.finished.emit(FieldWorkerResult(
                z_coords=z_coords_final or [],
                E2_values_list=E2_values_list,
                lambda_calcs=params.lambda_calcs,
                ep_c1_cn=ep_c1_cn_final or [],
                opt_emp_factors=best_res["emp_factors"],
                opt_layer_types=best_res["layer_types"],
                success=True,
                message=f"Needle insertion found (cost improved to {best_res['cost']:.6f}).",
            ))
        else:
            logger.info("Needle scan: no beneficial insertion found.")
            for i, lambda_calc in enumerate(params.lambda_calcs):
                z_coords, E2_values, ep_c1_cn, _, _ = calculate_electric_field(
                    n1_r=params.n1_rs[i], n2_r=params.n2_rs[i], nSub_r=params.nSub_rs[i],
                    l0=params.l0, lambda_calc=lambda_calc,
                    emp_factors=params.emp_factors, layer_types=params.layer_types, n_superstrate_real=params.n_supers[i],
                    integral_points=params.integral_points, theta_inc=params.theta_inc, pol_flag=params.pol_flag
                )
                if i == 0:
                    z_coords_final = z_coords.tolist()
                    ep_c1_cn_final = ep_c1_cn
                E2_values_list.append(E2_values.tolist())

            self.signals.finished.emit(FieldWorkerResult(
                z_coords=z_coords_final or [],
                E2_values_list=E2_values_list,
                lambda_calcs=params.lambda_calcs,
                ep_c1_cn=ep_c1_cn_final or [],
                opt_emp_factors=params.emp_factors,
                opt_layer_types=params.layer_types,
                success=True,
                message="No beneficial needle insertion found (cost did not decrease).",
            ))

    def _run_optimize(self, params: FieldParamsDTO) -> None:
        logger = logging.getLogger("certus")
        params = self._require_params(params)
        if not SCIPY_AVAILABLE:
            logger.error("scipy is not installed. Optimization impossible.")
            raise RuntimeError("scipy is not installed. Optimization impossible.")

        from types import SimpleNamespace
        state = SimpleNamespace(
            best_cost=float('inf'),
            iteration=0,
            generation=0,
            eval_count=0
        )

        n_layers = len(params.emp_factors)
        bounds = [(0.01, 5.0) for _ in range(n_layers)]

        def cost_func(p: np.ndarray) -> float:
            if not self._is_running:
                logger.warning("Optimization interrupted by user (cost_func).")
                raise InterruptedError("Optimization cancelled by user.")
            state.eval_count += 1
            opt_integral_points = params.integral_points
            cost = top_level_objective_function(
                p,
                params.n1_rs,
                params.n2_rs,
                params.nSub_rs,
                params.l0,
                params.seuil_int_1,
                params.seuil_int_2,
                params.alpha,
                opt_integral_points,
                params.n_supers,
                params.theta_inc,
                params.pol_flag,
                params.lambda_calcs,
                params.layer_types,
                rmin=params.rmin if params.rmin is not None else 1.0,
                rmax=params.rmax if params.rmax is not None else 1.0,
                min_field_active=bool(params.min_field_active)
            )
            if cost < state.best_cost:
                state.best_cost = cost
            return cost

        # Log initial state
        initial_cost = cost_func(np.asarray(params.emp_factors, dtype=float))
        # Reset eval_count after computing initial cost so the count starts at 0 for optimization
        state.eval_count = 0
        state.best_cost = initial_cost

        logger.info(
            f"Optimization Initialized:\n"
            f"  - Mode: {'Global (Differential Evolution)' if getattr(params, 'global_opt', False) else 'Local (L-BFGS-B)'}\n"
            f"  - Number of layers: {n_layers}\n"
            f"  - Initial thicknesses: {params.emp_factors}\n"
            f"  - Initial QWOT sum: {sum(params.emp_factors):.4f}\n"
            f"  - Initial Cost: {initial_cost:.6f}\n"
            f"  - Bounds (min/max): {bounds[0]}\n"
            f"  - Thresholds: H={params.seuil_int_1}, L={params.seuil_int_2}\n"
            f"  - Alpha: {params.alpha}"
        )
        self.signals.progress_snapshot.emit(build_progress_snapshot(message="Preparing optimization...", display_ratio=0.05, progress_ratio=0.05, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION"))
        self.signals.progress_snapshot.emit(build_progress_snapshot(message="Preparing optimization...", display_ratio=0.05, progress_ratio=0.05, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION"))

        def emit_plot(xk: np.ndarray, message: str) -> None:
            z_c, E2_v, ep_c, _, _ = calculate_electric_field(
                n1_r=params.n1_rs[0],
                n2_r=params.n2_rs[0],
                nSub_r=params.nSub_rs[0],
                l0=params.l0,
                lambda_calc=params.lambda_calcs[0],
                emp_factors=xk.tolist(),
                layer_types=params.layer_types,
                n_superstrate_real=params.n_supers[0],
                integral_points=params.integral_points,
                theta_inc=params.theta_inc,
                pol_flag=params.pol_flag,
            )
            self.signals.plot.emit(
                {
                    'z_coords': z_c.tolist(),
                    'E2_values_list': [E2_v.tolist()],
                    'lambda_calcs': [params.lambda_calcs[0]],
                    'ep_c1_cn': ep_c,
                },
                message,
            )

        current_run = [1]

        def opt_callback(xk: np.ndarray) -> None:
            if not self._is_running:
                logger.warning("Optimization interrupted by user (callback).")
                raise InterruptedError("Optimization cancelled by user.")
            state.iteration += 1
            qwot_sum = float(sum(xk))
            
            # Emit only every 10 iterations to prevent flooding the GUI/logs
            if state.iteration == 1 or state.iteration % 10 == 0:
                logger.info(
                    f"[Run {current_run[0]}][Iteration {state.iteration}] "
                    f"Best Cost: {state.best_cost:.6f} | QWOT Sum: {qwot_sum:.4f} | Evals: {state.eval_count}"
                )
                
                pct = min(90, 20 + state.iteration * 2)
                self.signals.progress_snapshot.emit(build_progress_snapshot(message=f"Run {current_run[0]} | Iter {state.iteration} | Evals: {state.eval_count} | Cost: {state.best_cost:.6f}", display_ratio=pct / 100.0, progress_ratio=pct / 100.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION", metadata={"iteration": state.iteration, "evals": state.eval_count, "best_cost": state.best_cost}))
                
                emit_plot(xk, f"Optimization running (L-BFGS-B) - Iteration {state.iteration}...")

        import time
        t0 = time.perf_counter()

        best_cost = float('inf')
        best_x = None
        all_solutions = []

        if getattr(params, "global_opt", False):
            self.signals.progress_snapshot.emit(build_progress_snapshot(message="Optimization running (PGLOBAL)...", display_ratio=0.20, progress_ratio=0.20, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION", metadata={"mode": "PGLOBAL"}))
            self.signals.progress_snapshot.emit(build_progress_snapshot(message="Optimization running (PGLOBAL)...", display_ratio=0.20, progress_ratio=0.20, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION", metadata={"mode": "PGLOBAL"}))
            from certus_physics import PGlobalConfig, PGlobalOptimizer

            max_iter_run = params.maxiter if params.maxiter <= 50 else 50
            pg_conf = PGlobalConfig.for_dimension(
                dim=n_layers,
                base_samples=6000,
                max_feval=50000000,
            )

            state.best_cost = initial_cost
            state.generation = 0

            logger.info(f"OptimWorker: Starting PGLOBAL optimization - mode=global, max_iter={max_iter_run}, dim={n_layers}")
            logger.info(f"OptimWorker: Initial state - best_rmse_seen={state.best_cost:.6e}, callback_counter={state.iteration}")

            de_best = {"x": None, "fun": float("inf")}

            def de_callback(sample) -> None:
                if not self._is_running:
                    raise StopIteration("User requested stop.")
                
                state.generation = sample.generation
                cost = float(sample.y)
                if cost < de_best["fun"]:
                    de_best["fun"] = cost
                    de_best["x"] = sample.x.copy()
                
                qwot_sum = float(sum(sample.x))
                
                try:
                    n_clusters = len(optimizer.clusterer.clusters)
                    n_evals = optimizer.n_evals
                except Exception:
                    n_clusters = 0
                    n_evals = state.eval_count
                
                state.eval_count = n_evals
                state.best_cost = min(state.best_cost, de_best["fun"])

                # Weighted blend: generation drives the main perception, evaluations add smoothness.
                gen_frac = sample.generation / max(1, max_iter_run)
                eval_frac = n_evals / max(1, int(getattr(pg_conf, "max_feval", 1) or 1))
                blended = min(1.0, max(0.0, 0.7 * float(gen_frac) + 0.3 * float(eval_frac)))
                msg = (
                    f"PGLOBAL | Gen {sample.generation}/{max_iter_run} | Evals: {n_evals} | "
                    f"Clusters: {n_clusters} | Best: {state.best_cost:.6f}"
                )
                pct = min(90, 20 + int(70 * blended))
                self.signals.progress_snapshot.emit(build_progress_snapshot(message=msg, display_ratio=pct / 100.0, progress_ratio=pct / 100.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION", metadata={"mode": "PGLOBAL", "generation": sample.generation, "evals": n_evals, "clusters": n_clusters, "best_cost": state.best_cost}))
                self.signals.progress_snapshot.emit(build_progress_snapshot(message=msg, display_ratio=pct / 100.0, progress_ratio=pct / 100.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION", metadata={"mode": "PGLOBAL", "best_cost": state.best_cost, "generation": sample.generation, "evals": n_evals, "clusters": n_clusters}))

                emit_plot(sample.x, f"Optimization running (PGLOBAL) - Gen {sample.generation}...")

            optimizer = PGlobalOptimizer(
                cost_func,
                bounds,
                config=pg_conf,
                stop_event=self._stop_event,
                x0=np.asarray(params.emp_factors, dtype=float),
            )

            try:
                best_sample = optimizer.optimize(
                    max_iter=max_iter_run,
                    callback=de_callback
                )
                opt_time = time.perf_counter() - t0
                
                logger.info(
                    f"OptimWorker [Restart 1]: optimizer.optimize() returned after {opt_time:.2f}s - "
                    f"best_sample={best_sample is not None}, callback_count={state.generation}"
                )
                
                if best_sample:
                    best_cost = float(best_sample.y)
                    best_x = best_sample.x.tolist()
                    logger.info(
                        f"OptimWorker [Restart 1]: Best sample - rmse={best_cost:.6e}, n_evals={optimizer.n_evals}"
                    )
                else:
                    if de_best["x"] is not None:
                        best_cost = de_best["fun"]
                        best_x = de_best["x"].tolist()
            except StopIteration:
                if de_best["x"] is not None:
                    best_cost = de_best["fun"]
                    best_x = de_best["x"].tolist()
                else:
                    logger.info("PGLOBAL optimization stopped by user request, no candidate found.")
                    if not self._is_running:
                        return
            except Exception as e:
                logger.error(f"PGLOBAL optimization failed: {e}")
                raise
        else:
            self.signals.progress_snapshot.emit(build_progress_snapshot(message="Optimization running (L-BFGS-B)...", display_ratio=0.20, progress_ratio=0.20, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION", metadata={"mode": "L-BFGS-B"}))
            self.signals.progress_snapshot.emit(build_progress_snapshot(message="Optimization running (L-BFGS-B)...", display_ratio=0.20, progress_ratio=0.20, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION", metadata={"mode": "L-BFGS-B"}))
            start_points = [np.asarray(params.emp_factors, dtype=float)]
            is_synthesis = bool(params.get("synthesis_mode", False))
            if not is_synthesis:
                for _ in range(2):
                    perturb = np.random.uniform(0.85, 1.15, n_layers)
                    start_points.append(start_points[0] * perturb)

            n_runs = len(start_points)
            for idx, start_p in enumerate(start_points):
                if not self._is_running:
                    return

                current_run[0] = idx + 1
                state.iteration = 0
                pct = 20 + idx * 25
                self.signals.progress_snapshot.emit(build_progress_snapshot(message=f"Optimization running (Run {idx+1}/{n_runs})...", display_ratio=pct / 100.0, progress_ratio=pct / 100.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION", metadata={"mode": "L-BFGS-B", "run": idx + 1, "total_runs": n_runs}))
                self.signals.progress_snapshot.emit(build_progress_snapshot(message=f"Optimization running (Run {idx+1}/{n_runs})...", display_ratio=pct / 100.0, progress_ratio=pct / 100.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION", metadata={"mode": "L-BFGS-B", "run": idx + 1, "total_runs": n_runs}))
                res_opt = minimize(
                    cost_func,
                    start_p,
                    method='L-BFGS-B',
                    bounds=bounds,
                    callback=opt_callback,
                    options={'maxiter': params.maxiter},
                )

                cost = float(res_opt.fun)
                x_opt = res_opt.x.tolist()
                all_solutions.append({'cost': cost, 'qwot_sum': float(sum(x_opt)), 'emp_factors': x_opt, 'layer_types': list(params.layer_types)})
                
                logger.info(f"[Run {idx+1}/{n_runs}] finished. Cost: {cost:.6f} | QWOT Sum: {float(sum(x_opt)):.4f}")
                
                if np.isfinite(cost) and cost < best_cost:
                    best_cost = cost
                    best_x = x_opt

        if best_x is None:
            raise RuntimeError("No usable optimization solution found.")

        dt = time.perf_counter() - t0
        if not self._is_running:
            logger.info("Optimization stopped by user.")
            return

        dmin = getattr(params, 'dmin', 5.0)
        if dmin > 0.0:
            def clean_and_reoptimize(x_opt, layer_types):
                current_x = list(x_opt)
                current_types = list(layer_types)
                any_cleaned = False
                final_cost = None
                
                while True:
                    if not current_x:
                        break
                        
                    all_thin = True
                    for i, qwot in enumerate(current_x):
                        n_idx = params.n1_rs[0] if current_types[i] == 0 else params.n2_rs[0]
                        thick_nm = qwot * (params.l0 / 4.0) / n_idx
                        if thick_nm >= dmin:
                            all_thin = False
                            break
                    if all_thin:
                        break
                        
                    thinnest_idx = -1
                    min_thick = float('inf')
                    for i, qwot in enumerate(current_x):
                        n_idx = params.n1_rs[0] if current_types[i] == 0 else params.n2_rs[0]
                        thick_nm = qwot * (params.l0 / 4.0) / n_idx
                        if thick_nm < dmin and thick_nm < min_thick:
                            min_thick = thick_nm
                            thinnest_idx = i
                            
                    if thinnest_idx == -1:
                        break
                        
                    any_cleaned = True
                    current_x.pop(thinnest_idx)
                    current_types.pop(thinnest_idx)
                    
                    if not current_x:
                        break
                        
                    merged_x = []
                    merged_types = []
                    for i in range(len(current_x)):
                        if not merged_types:
                            merged_x.append(current_x[i])
                            merged_types.append(current_types[i])
                        else:
                            if current_types[i] == merged_types[-1]:
                                merged_x[-1] += current_x[i]
                            else:
                                merged_x.append(current_x[i])
                                merged_types.append(current_types[i])
                                
                    current_x = merged_x
                    current_types = merged_types
                    
                    clean_bounds = [(0.01, 5.0) for _ in range(len(current_x))]
                    
                    def make_cost_func(types_capture):
                        def clean_cost_func(p: np.ndarray) -> float:
                            if not self._is_running:
                                raise InterruptedError()
                            return top_level_objective_function(
                                p, params.n1_rs, params.n2_rs, params.nSub_rs, params.l0,
                                params.seuil_int_1, params.seuil_int_2, params.alpha,
                                min(10, params.integral_points), params.n_supers,
                                params.theta_inc, params.pol_flag, params.lambda_calcs,
                                types_capture, rmin=params.rmin if params.rmin is not None else 1.0,
                                rmax=params.rmax if params.rmax is not None else 1.0,
                                min_field_active=bool(params.min_field_active)
                            )
                        return clean_cost_func
                    
                    res_clean = minimize(
                        make_cost_func(current_types), np.asarray(current_x, dtype=float),
                        method='L-BFGS-B', bounds=clean_bounds,
                        options={'maxiter': params.maxiter}
                    )
                    
                    if res_clean.fun < float('inf'):
                        current_x = res_clean.x.tolist()
                        final_cost = float(res_clean.fun)
                    else:
                        break
                        
                return current_x, current_types, any_cleaned, final_cost

            self.signals.progress_snapshot.emit(build_progress_snapshot(message=f"Auto-cleaning layers thinner than {dmin} nm...", display_ratio=0.85, progress_ratio=0.85, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="OPTIMIZATION", metadata={"mode": "CLEANUP", "dmin": dmin}))
            self.signals.progress_snapshot.emit(build_progress_snapshot(message=f"Auto-cleaning layers thinner than {dmin} nm...", display_ratio=0.85, progress_ratio=0.85, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="AUTO_CLEAN"))
            
            new_best_x, new_best_types, was_cleaned, new_best_cost = clean_and_reoptimize(best_x, params.layer_types)
            if was_cleaned:
                logger.info(f"Auto-cleaned best solution: reduced layers from {len(best_x)} to {len(new_best_x)}, cost: {new_best_cost:.6f}")
                best_x = new_best_x
                params.layer_types = new_best_types
                if new_best_cost is not None:
                    best_cost = new_best_cost

            cleaned_solutions = []
            for sol in all_solutions:
                sol_types = sol.get('layer_types', params.layer_types)
                new_x, new_types, s_cleaned, new_cost = clean_and_reoptimize(sol['emp_factors'], sol_types)
                if s_cleaned and new_cost is not None:
                    cleaned_solutions.append({'cost': new_cost, 'qwot_sum': float(sum(new_x)), 'emp_factors': new_x, 'layer_types': new_types})
                else:
                    cleaned_solutions.append(sol)
            all_solutions = cleaned_solutions

        all_solutions.sort(key=lambda s: s['cost'])
        logger.info(
            f"Optimization Finished:\n"
            f"  - Total Elapsed Time: {dt:.2f}s\n"
            f"  - Total Evaluations: {state.eval_count}\n"
            f"  - Initial Cost: {initial_cost:.6f}\n"
            f"  - Final Best Cost: {best_cost:.6f}\n"
            f"  - Optimized thicknesses: {best_x}\n"
            f"  - Final QWOT sum: {sum(best_x):.4f}\n"
            f"  - Improvements: Cost reduced by {initial_cost - best_cost:.6f} ({((initial_cost - best_cost) / max(initial_cost, 1e-6)) * 100:.1f}%)"
        )
        self.signals.progress_snapshot.emit(build_progress_snapshot(message="Generating final metrics...", display_ratio=0.90, progress_ratio=0.90, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="FIELD", phase="FINAL_METRICS"))

        E2_values_list = []
        z_coords_final = None
        ep_c_final = None
        for i, lambda_calc in enumerate(params.lambda_calcs):
            z_c, E2_v, ep_c, _, _ = calculate_electric_field(
                n1_r=params.n1_rs[i],
                n2_r=params.n2_rs[i],
                nSub_r=params.nSub_rs[i],
                l0=params.l0,
                lambda_calc=lambda_calc,
                emp_factors=best_x,
                layer_types=params.layer_types,
                n_superstrate_real=params.n_supers[i],
                integral_points=params.integral_points,
                theta_inc=params.theta_inc,
                pol_flag=params.pol_flag,
            )
            if i == 0:
                z_coords_final = z_c.tolist()
                ep_c_final = ep_c
            E2_values_list.append(E2_v.tolist())

        final_metrics = calculate_opt_metrics(
            params.n1_rs[0],
            params.n2_rs[0],
            params.nSub_rs[0],
            params.l0,
            best_x,
            params.layer_types,
            params.n_supers[0],
            params.integral_points,
            params.theta_inc,
            params.pol_flag,
            params.lambda_calcs[0],
        )

        logger.debug(f"Final metrics: {final_metrics}")
        self.signals.finished.emit(FieldWorkerResult(
            z_coords=z_coords_final or [],
            E2_values_list=E2_values_list,
            lambda_calcs=params.lambda_calcs,
            ep_c1_cn=ep_c_final or [],
            opt_emp_factors=best_x,
            opt_metrics=final_metrics,
            pareto_solutions=all_solutions,
            success=True,
            message="Optimization finished successfully.",
        ))
