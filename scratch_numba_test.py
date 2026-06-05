import numba
import numpy as np

@numba.njit
def test_mod(Ai, Bi, delta):
    angle_A = np.arctan2(Ai.imag, Ai.real)
    angle_B = np.arctan2(Bi.imag, Bi.real)
    phase_diff = angle_A - angle_B
    phase_diff_mod = phase_diff % (2.0 * np.pi)
    return phase_diff_mod <= 2.0 * delta.real

print(test_mod(1.0 + 0.5j, 1.0 - 0.5j, 1.5 + 0j))
