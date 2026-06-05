import numpy as np

def check_peak():
    A = 1.0 * np.exp(1j * 0.5)
    B = 0.8 * np.exp(1j * -1.2)
    
    dj = 1000.0
    k_vac = 2 * np.pi / 500.0
    nj = 1.5
    cos_tj = 1.0
    
    delta = k_vac * nj * dj * cos_tj
    
    z = np.linspace(0, dj, 1000)
    phase = k_vac * nj * z * cos_tj
    E = A * np.exp(-1j * phase) + B * np.exp(1j * phase)
    e2 = np.abs(E)**2
    num_peak = np.max(e2)
    
    A_abs = np.abs(A)
    B_abs = np.abs(B)
    phase_diff = np.angle(A) - np.angle(B)
    phase_diff_mod = phase_diff % (2 * np.pi)
    
    exact_peak = (A_abs + B_abs)**2
    
    print(f"Num peak: {num_peak}")
    print(f"Exact peak (if inside): {exact_peak}")
    print(f"phase_diff_mod: {phase_diff_mod}, 2*delta: {2*delta}")
    if phase_diff_mod <= 2 * np.real(delta):
        print("Peak is inside!")
    else:
        print("Peak is OUTSIDE")

check_peak()
