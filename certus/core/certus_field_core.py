import numba
import numpy as np

from certus.physics.certus_opt_tmm import reflection_amplitudes


def _default_layer_types(n_layers: int) -> np.ndarray:
    return np.asarray([i % 2 for i in range(n_layers)], dtype=np.int32)


@numba.njit(cache=True)
def get_layer_properties_numba(n1_r: float, n2_r: float, emp_factors_arr: np.ndarray, layer_types_arr: np.ndarray, l0: float) -> tuple[np.ndarray, np.ndarray]:
    n1 = n1_r + 0j
    n2 = n2_r + 0j
    n_layers = len(emp_factors_arr)
    indices_complex = np.empty(n_layers, dtype=np.complex128)
    ep_physical_nm = np.empty(n_layers, dtype=np.float64)

    for i in range(n_layers):
        n_layer_complex = n1 if layer_types_arr[i] == 0 else n2
        n_layer_real = np.real(n_layer_complex)

        if n_layer_real <= 0 or not np.isfinite(n_layer_real):
            return np.empty(0, dtype=np.complex128), np.empty(0, dtype=np.float64)

        qwot_factor = emp_factors_arr[i]
        if qwot_factor <= 0 or not np.isfinite(qwot_factor):
            return np.empty(0, dtype=np.complex128), np.empty(0, dtype=np.float64)

        ep_physical_nm[i] = (qwot_factor * l0) / (4 * n_layer_real)
        indices_complex[i] = n_layer_complex

    return indices_complex, ep_physical_nm


def get_layer_properties_from_list(n1_r: float, n2_r: float, emp_factors: list[float], layer_types: list[int] | None, l0: float) -> tuple[np.ndarray, np.ndarray]:
    if np.size(emp_factors) == 0 or l0 <= 0:
        return np.empty(0, dtype=np.complex128), np.empty(0, dtype=np.float64)

    emp_factors_arr = np.asarray(emp_factors, dtype=np.float64)
    if layer_types is None:
        layer_types_arr = _default_layer_types(len(emp_factors_arr))
    else:
        layer_types_arr = np.asarray(layer_types, dtype=np.int32)
        if len(layer_types_arr) != len(emp_factors_arr):
            layer_types_arr = _default_layer_types(len(emp_factors_arr))

    return get_layer_properties_numba(n1_r, n2_r, emp_factors_arr, layer_types_arr, l0)

@numba.njit(cache=True)
def _trapz_numba(y: np.ndarray, x: np.ndarray) -> float:
    res = 0.0
    for j in range(len(y) - 1):
        res += 0.5 * (y[j] + y[j+1]) * (x[j+1] - x[j])
    return res


@numba.njit(cache=True)
def _layer_field_couplings(
    is_p_pol: bool, theta_inc: float, n0_sin_theta0: complex, nj: complex, cos_tj: complex
) -> tuple[complex, complex]:
    """Return (cx, cz) mapping tangential forward/backward waves to physical Ex, Ez."""
    if not is_p_pol:
        return 1.0 + 0j, 0.0j
    cx = np.cos(theta_inc) + 0j
    cz = -cx * (n0_sin_theta0 / (nj * cos_tj))
    return cx, cz


@numba.njit(cache=True)
def _layer_e2_profile(
    ai: complex,
    bi: complex,
    nj: complex,
    dj: float,
    cos_tj: complex,
    k_vac: float,
    integral_points: int,
    cx: complex,
    cz: complex,
) -> np.ndarray:
    """Sample total |E|^2 = |Ex|^2 + |Ez|^2 on a uniform depth grid inside one layer."""
    z_grid = np.linspace(0.0, dj, integral_points)
    e2_values = np.zeros(integral_points, dtype=np.float64)
    for k in range(integral_points):
        phase = k_vac * nj * z_grid[k] * cos_tj
        wf = ai * np.exp(-1j * phase)
        wb = bi * np.exp(1j * phase)
        ex = cx * (wf + wb)
        ez = cz * (wf - wb)
        e2_values[k] = np.abs(ex)**2 + np.abs(ez)**2
    return e2_values

@numba.njit(cache=True)
def _calculate_field_single_pol(indices_c1_cn: np.ndarray, ep_c1_cn: np.ndarray, nSub_r: float, lambda_calc: float, n_super: float, integral_points: int, theta_inc: float, is_p_pol: bool) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n_layers = len(ep_c1_cn)
    nSub_complex = nSub_r + 0j
    n0 = n_super + 0j
    
    # Snell's Law
    n0_sin_theta0 = n0 * np.sin(theta_inc)
    
    # Precompute cos_theta and admittances
    cos_theta = np.empty(n_layers, dtype=np.complex128)
    Y = np.empty(n_layers, dtype=np.complex128)
    
    for i in range(n_layers):
        nj = indices_c1_cn[i]
        cos_t = np.sqrt(1.0 - (n0_sin_theta0 / nj)**2)
        cos_theta[i] = cos_t
        if is_p_pol:
            Y[i] = nj / cos_t
        else:
            Y[i] = nj * cos_t
            
    # Substrate admittance
    cos_theta_sub = np.sqrt(1.0 - (n0_sin_theta0 / nSub_complex)**2)
    Y_sub = nSub_complex / cos_theta_sub if is_p_pol else nSub_complex * cos_theta_sub
    
    # Superstrate admittance
    Y0 = n0 / np.cos(theta_inc) if is_p_pol else n0 * np.cos(theta_inc)
    
    # Admittance recursive calculation
    Y_eff = Y_sub
    for i in range(n_layers - 1, -1, -1):
        delta = (2 * np.pi / lambda_calc) * indices_c1_cn[i] * ep_c1_cn[i] * cos_theta[i]
        cos_d, sin_d = np.cos(delta), np.sin(delta)
        num = Y_eff * cos_d + 1j * Y[i] * sin_d
        den = cos_d + 1j * (Y_eff / Y[i]) * sin_d
        if abs(den) > 1e-12:
            Y_eff = num / den
        else:
            Y_eff = 1e30 + 0j
            
    _, r, _ = reflection_amplitudes(Y0, 1.0, Y_eff)  # [B; C] = [1; Y_eff]
    R = np.abs(r)**2
    t = 1 + r
    
    fields = np.zeros((n_layers + 1, 2), dtype=np.complex128)
    fields[0, 0] = t
    fields[0, 1] = Y0 * (1 - r)
    
    k_vac = 2 * np.pi / lambda_calc
    
    integrals = np.zeros(n_layers, dtype=np.float64)
    averages = np.zeros(n_layers, dtype=np.float64)
    peaks = np.zeros(n_layers, dtype=np.float64)
    
    for i in range(n_layers):
        nj = indices_c1_cn[i]
        dj = ep_c1_cn[i]
        Yj = Y[i]
        cos_tj = cos_theta[i]
        
        delta = k_vac * nj * dj * cos_tj
        cos_d, sin_d = np.cos(delta), np.sin(delta)
        
        # Transfer matrix step
        inv_M = np.array([
            [cos_d, (-1j / Yj) * sin_d],
            [-1j * Yj * sin_d, cos_d]
        ], dtype=np.complex128)
        
        prev_E = fields[i, 0]
        prev_H = fields[i, 1]
        
        next_E = inv_M[0, 0] * prev_E + inv_M[0, 1] * prev_H
        next_H = inv_M[1, 0] * prev_E + inv_M[1, 1] * prev_H
        
        fields[i + 1, 0] = next_E
        fields[i + 1, 1] = next_H
        
        Ai = 0.5 * (prev_E + prev_H / Yj)
        Bi = 0.5 * (prev_E - prev_H / Yj)

        cx, cz = _layer_field_couplings(is_p_pol, theta_inc, n0_sin_theta0, nj, cos_tj)
        s_sum = abs(cx)**2 + abs(cz)**2
        s_diff = abs(cx)**2 - abs(cz)**2

        z_integral = np.linspace(0.0, dj, integral_points)
        e2_values = _layer_e2_profile(Ai, Bi, nj, dj, cos_tj, k_vac, integral_points, cx, cz)

        int_val = _trapz_numba(e2_values, z_integral)
        integrals[i] = int_val
        averages[i] = int_val / dj if dj > 1e-9 else 0.0

        peak_val = np.max(e2_values)
        if abs(delta.imag) < 1e-12:
            A_abs = np.abs(Ai)
            B_abs = np.abs(Bi)
            if A_abs > 1e-12 and B_abs > 1e-12:
                angle_A = np.arctan2(Ai.imag, Ai.real)
                angle_B = np.arctan2(Bi.imag, Bi.real)
                phase_diff = angle_A - angle_B
                target_phase = phase_diff if s_diff >= 0.0 else phase_diff + np.pi
                if target_phase % (2.0 * np.pi) <= 2.0 * delta.real:
                    exact_peak = s_sum * (A_abs**2 + B_abs**2) + 2.0 * abs(s_diff) * A_abs * B_abs
                    if exact_peak > peak_val:
                        peak_val = exact_peak

        peaks[i] = peak_val

    return R, averages, integrals, fields, cos_theta, Y, peaks

@numba.njit(cache=True)
def _calculate_metrics_and_field_numba(indices_c1_cn: np.ndarray, ep_c1_cn: np.ndarray, n1_r: float, n2_r: float, nSub_r: float, l0: float, lambda_calc: float, n_super: float, integral_points: int, theta_inc: float, pol_flag: int) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    # pol_flag: 0 = S, 1 = P, 2 = UNPOLARIZED
    # For layer order, we must propagate from the superstrate.
    indices_for_efield = indices_c1_cn[::-1]
    ep_for_efield = ep_c1_cn[::-1]
    
    if pol_flag == 0:
        R, averages, integrals, fields, cos_theta, Y, peaks = _calculate_field_single_pol(indices_for_efield, ep_for_efield, nSub_r, lambda_calc, n_super, integral_points, theta_inc, False)
    elif pol_flag == 1:
        R, averages, integrals, fields, cos_theta, Y, peaks = _calculate_field_single_pol(indices_for_efield, ep_for_efield, nSub_r, lambda_calc, n_super, integral_points, theta_inc, True)
    else:
        Rs, avg_s, int_s, fields_s, cos_theta, Ys, peaks_s = _calculate_field_single_pol(indices_for_efield, ep_for_efield, nSub_r, lambda_calc, n_super, integral_points, theta_inc, False)
        Rp, avg_p, int_p, _fields_p, _, _Yp, peaks_p = _calculate_field_single_pol(indices_for_efield, ep_for_efield, nSub_r, lambda_calc, n_super, integral_points, theta_inc, True)
        R = 0.5 * (Rs + Rp)
        averages = 0.5 * (avg_s + avg_p)
        integrals = 0.5 * (int_s + int_p)
        peaks = 0.5 * (peaks_s + peaks_p)
        fields = fields_s # Metrics callers ignore interface fields; calculate_electric_field traces both polarizations.
        Y = Ys
        
    return R, averages[::-1], integrals[::-1], fields, indices_for_efield, ep_for_efield, cos_theta, Y, peaks[::-1]

def calculate_opt_metrics(n1_r: float, n2_r: float, nSub_r: float, l0: float, emp_factors_list: list[float], layer_types: list[int] | None = None, n_super: float = 1.0, integral_points: int = 50, theta_inc: float = 0.0, pol_flag: int = 0, lambda_calc: float | None = None) -> dict[str, float]:
    if lambda_calc is None:
        lambda_calc = l0
    indices_c1_cn, ep_c1_cn = get_layer_properties_from_list(n1_r, n2_r, emp_factors_list, layer_types, l0)
    if indices_c1_cn.size == 0:
        return {'R': 0, 'ratio_average': 0, 'max_avg_1': 0, 'max_avg_2': 0, 'max_peak_1': 0, 'max_peak_2': 0}

    R, averages, _, _, _, _, _, _, peaks = _calculate_metrics_and_field_numba(
        indices_c1_cn, ep_c1_cn, n1_r, n2_r, nSub_r, l0, lambda_calc, n_super, integral_points, theta_inc, pol_flag
    )
    
    if layer_types is None:
        layer_types = [i % 2 for i in range(len(averages))]
        
    averages_n1 = [avg for i, avg in enumerate(averages) if layer_types[i] == 0]
    averages_n2 = [avg for i, avg in enumerate(averages) if layer_types[i] == 1]
    peaks_n1 = [p for i, p in enumerate(peaks) if layer_types[i] == 0]
    peaks_n2 = [p for i, p in enumerate(peaks) if layer_types[i] == 1]

    max_average_n1 = max(averages_n1) if averages_n1 else 0
    max_average_n2 = max(averages_n2) if averages_n2 else 0
    max_peak_n1 = max(peaks_n1) if peaks_n1 else 0
    max_peak_n2 = max(peaks_n2) if peaks_n2 else 0
    
    ratio_avg = max_average_n1 / max_average_n2 if max_average_n2 > 1e-9 else np.inf

    return {
        'R': R, 
        'ratio_average': ratio_avg,
        'max_avg_1': max_average_n1, 
        'max_avg_2': max_average_n2,
        'max_peak_1': max_peak_n1,
        'max_peak_2': max_peak_n2
    }
    
@numba.njit(cache=True)
def _trace_single_pol_e2(
    indices_for_efield: np.ndarray,
    ep_for_efield: np.ndarray,
    fields: np.ndarray,
    cos_theta: np.ndarray,
    admittances: np.ndarray,
    n_super: float,
    theta_inc: float,
    lambda_calc: float,
    integral_points: int,
    is_p_pol: bool,
) -> np.ndarray:
    """Trace total |E|^2 from superstrate to substrate for one polarization."""
    n_layers = len(ep_for_efield)
    k_vac = 2.0 * np.pi / lambda_calc
    n0_sin_theta0 = (n_super + 0j) * np.sin(theta_inc)
    e2_all = np.empty(n_layers * integral_points, dtype=np.float64)
    offset = 0
    for i in range(n_layers):
        E_interface, H_interface = fields[i, 0], fields[i, 1]
        Yj = admittances[i]
        Ai = 0.5 * (E_interface + H_interface / Yj)
        Bi = 0.5 * (E_interface - H_interface / Yj)
        nj = indices_for_efield[i]
        dj = ep_for_efield[i]
        cos_tj = cos_theta[i]
        cx, cz = _layer_field_couplings(is_p_pol, theta_inc, n0_sin_theta0, nj, cos_tj)
        e2_layer = _layer_e2_profile(Ai, Bi, nj, dj, cos_tj, k_vac, integral_points, cx, cz)
        e2_all[offset : offset + integral_points] = e2_layer
        offset += integral_points
    return e2_all


def calculate_electric_field(n1_r: float, n2_r: float, nSub_r: float, l0: float, lambda_calc: float, emp_factors: list[float], layer_types: list[int] | None = None, n_superstrate_real: float = 1.0, integral_points: int = 50, theta_inc: float = 0.0, pol_flag: int = 0) -> tuple[np.ndarray, np.ndarray, list[float], list[float], list[float]]:
    indices_c1_cn, ep_c1_cn = get_layer_properties_from_list(n1_r, n2_r, emp_factors, layer_types, l0)
    n_layers = len(ep_c1_cn)
    if n_layers == 0:
        return np.array([0]), np.array([1]), [], [], []

    indices_for_efield = indices_c1_cn[::-1]
    ep_for_efield = ep_c1_cn[::-1]
    pol_modes = (False,) if pol_flag == 0 else ((True,) if pol_flag == 1 else (False, True))
    averages_sum = np.zeros(n_layers, dtype=np.float64)
    integrals_sum = np.zeros(n_layers, dtype=np.float64)
    e2_sum = np.zeros(n_layers * integral_points, dtype=np.float64)
    for is_p in pol_modes:
        _, avg_pol, int_pol, fields_pol, cos_theta, y_pol, _ = _calculate_field_single_pol(
            indices_for_efield, ep_for_efield, nSub_r, lambda_calc, n_superstrate_real, integral_points, theta_inc, is_p
        )
        averages_sum += avg_pol[::-1]
        integrals_sum += int_pol[::-1]
        e2_sum += _trace_single_pol_e2(
            indices_for_efield,
            ep_for_efield,
            fields_pol,
            cos_theta,
            y_pol,
            n_superstrate_real,
            theta_inc,
            lambda_calc,
            integral_points,
            is_p,
        )

    scale = 1.0 / len(pol_modes)
    averages = averages_sum * scale
    integrals = integrals_sum * scale
    e2_super_to_sub = e2_sum * scale

    z_coords_final = np.empty(n_layers * integral_points, dtype=np.float64)
    current_z_start = 0.0
    offset = 0
    for d_curr in ep_for_efield:
        z_coords_final[offset : offset + integral_points] = current_z_start + np.linspace(
            0.0, d_curr, integral_points, endpoint=True
        )
        current_z_start += d_curr
        offset += integral_points

    # Return depth z from substrate (0) to superstrate (z_total), matching ep_c1_cn, integrals, averages, and plots.
    z_total = float(current_z_start)
    z_sub_to_sup = np.maximum(0.0, z_total - z_coords_final[::-1])
    e2_sub_to_sup = e2_super_to_sub[::-1]
    return z_sub_to_sup, e2_sub_to_sup, list(ep_c1_cn), list(integrals), list(averages)
