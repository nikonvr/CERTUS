"""Thickness derivatives of FIELD's real-index field traces and peak intensities."""

import numba
import numpy as np

from certus.core.certus_field_core import _calculate_field_single_pol, get_layer_properties_from_list


@numba.njit(cache=True)
def _field_trace_derivatives(indices, thickness, substrate, wavelength, superstrate, points, angle, is_p):
    reflectance, _, _, fields, cosines, admittances, peaks = _calculate_field_single_pol(
        indices, thickness, substrate, wavelength, superstrate, points, angle, is_p
    )
    count = len(thickness)
    k = 2.0 * np.pi / wavelength * indices * cosines
    phases = k * thickness
    cos_d = np.cos(phases)
    sin_d = np.sin(phases)
    y0 = superstrate / np.cos(angle) if is_p else superstrate * np.cos(angle)

    # Differentiate the existing trace's boundary admittances, from the substrate up.
    derivative_y = np.zeros(count, dtype=np.complex128)
    for layer in range(count - 1, -1, -1):
        if abs(fields[layer, 0]) < 1e-14 or abs(fields[layer + 1, 0]) < 1e-14:
            raise ValueError("A field node makes the admittance derivative singular")
        current_y = fields[layer, 1] / fields[layer, 0]
        next_y = fields[layer + 1, 1] / fields[layer + 1, 0]
        y = admittances[layer]
        denominator = cos_d[layer] + 1j * next_y / y * sin_d[layer]
        if abs(denominator) <= 1e-12:
            raise ValueError("A rejected admittance denominator has no smooth derivative")
        chain = (cos_d[layer] - current_y * 1j / y * sin_d[layer]) / denominator
        derivative_y *= chain
        numerator_delta = -next_y * sin_d[layer] + 1j * y * cos_d[layer]
        denominator_delta = -sin_d[layer] + 1j * next_y / y * cos_d[layer]
        derivative_y[layer] += k[layer] * (numerator_delta - current_y * denominator_delta) / denominator

    reflection = fields[0, 0] - 1.0
    derivative_r = -0.5 * (1.0 + reflection)**2 / y0 * derivative_y
    gradient_r = 2.0 * np.real(np.conj(reflection) * derivative_r)
    derivative_e = derivative_r.copy()
    derivative_h = -y0 * derivative_r
    gradient_peaks = np.empty((count, count), dtype=np.float64)

    for layer in range(count):
        y = admittances[layer]
        electric, magnetic = fields[layer, 0], fields[layer, 1]
        forward = 0.5 * (electric + magnetic / y)
        backward = 0.5 * (electric - magnetic / y)
        gradient_forward = 0.5 * (derivative_e + derivative_h / y)
        gradient_backward = 0.5 * (derivative_e - derivative_h / y)

        best_intensity = -1.0
        best_fraction = 0.0
        for sample in range(points):
            fraction = sample / (points - 1)
            phase = phases[layer] * fraction
            value = forward * np.exp(-1j * phase) + backward * np.exp(1j * phase)
            intensity = abs(value)**2
            if intensity > best_intensity:
                best_intensity = intensity
                best_fraction = fraction

        phase = phases[layer] * best_fraction
        wave_forward = forward * np.exp(-1j * phase)
        wave_backward = backward * np.exp(1j * phase)
        value = wave_forward + wave_backward
        derivative = gradient_forward * np.exp(-1j * phase) + gradient_backward * np.exp(1j * phase)
        derivative[layer] += -1j * k[layer] * best_fraction * (wave_forward - wave_backward)
        gradient_peaks[layer] = 2.0 * np.real(np.conj(value) * derivative)

        # The primal trace upgrades a sampled peak to an internal standing-wave maximum.
        amplitude_a, amplitude_b = abs(forward), abs(backward)
        phase_difference = np.arctan2(forward.imag, forward.real) - np.arctan2(backward.imag, backward.real)
        exact_peak_active = (
            abs(phases[layer].imag) < 1e-12 and amplitude_a > 1e-12 and amplitude_b > 1e-12
            and phase_difference % (2.0 * np.pi) <= 2.0 * phases[layer].real
            and (amplitude_a + amplitude_b)**2 > best_intensity
        )
        if exact_peak_active:
            gradient_peaks[layer] = 2.0 * (amplitude_a + amplitude_b) * np.real(
                np.conj(forward) * gradient_forward / amplitude_a
                + np.conj(backward) * gradient_backward / amplitude_b
            )

        next_derivative_e = cos_d[layer] * derivative_e - 1j / y * sin_d[layer] * derivative_h
        next_derivative_h = -1j * y * sin_d[layer] * derivative_e + cos_d[layer] * derivative_h
        next_derivative_e[layer] += k[layer] * (-sin_d[layer] * electric - 1j / y * cos_d[layer] * magnetic)
        next_derivative_h[layer] += k[layer] * (-1j * y * cos_d[layer] * electric - sin_d[layer] * magnetic)
        derivative_e, derivative_h = next_derivative_e, next_derivative_h

    return reflectance, gradient_r, peaks, gradient_peaks


def field_metric_gradients(n1, n2, substrate, l0, factors, types, superstrate, points, angle, polarization, wavelength):
    """Return gradients of R and the two material peak maxima with respect to QWOT factors."""
    indices, thickness = get_layer_properties_from_list(n1, n2, factors, types, l0)
    indices, thickness = indices[::-1].copy(), thickness[::-1].copy()
    traces = [_field_trace_derivatives(
        indices, thickness, substrate, wavelength, superstrate, points, angle, pol
    ) for pol in ((False, True) if polarization == 2 else (polarization == 1,))]
    gradient_r = sum(trace[1] for trace in traces) / len(traces)
    peaks = sum(trace[2] for trace in traces) / len(traces)
    gradient_peaks = sum(trace[3] for trace in traces) / len(traces)
    types_reversed = np.asarray(types)[::-1]
    gradients = [gradient_r]
    for material in (0, 1):
        rows = np.flatnonzero(types_reversed == material)
        gradients.append(gradient_peaks[rows[np.argmax(peaks[rows])]] if rows.size else np.zeros(len(factors)))
    scale = l0 / (4.0 * indices.real[::-1])
    return tuple(gradient[::-1] * scale for gradient in gradients)
