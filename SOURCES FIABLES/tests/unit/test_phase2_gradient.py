import numpy as np
import pytest
from scipy.optimize._numdiff import approx_derivative
from CERTUS_INDEX import IRGlobalObjective, DataType, substrateMode

def test_phase2_gradient_analytic_vs_fd():
    np.random.seed(42)
    wls = np.linspace(400, 2000, 50)
    target_T = np.linspace(0.8, 0.9, 50)
    target_R = np.linspace(0.1, 0.05, 50)
    n_sub = np.full(50, 1.5)
    T_sub = np.full(50, 0.92)
    R_sub = np.full(50, 0.08)
    thickness = 100.0
    n_tlu_ref = np.full(50, 2.0)
    
    class DummyConfig:
        pass
    
    config = DummyConfig()
    config.is_frosted_glass = False
    config.data_type = DataType.BOTH
    config.use_normalized = False
    config.weight_T = 0.5
    config.weight_R = 0.5
    config.lambda_min = 400
    config.lambda_max = 2000
    config.exclude_min = None
    config.exclude_max = None
    config.has_absorbing_substrate = False
    config.k_sub_data = None
    config.substrate_thickness_nm = None
    
    # 13 params: [5 sellmeier, 8 k_law]
    # Sellmeier: A, B1, L1, B2, L2
    # k_law: s1, p1, s2, p2, amp, L0, w, beta
    p0 = np.array([
        1.5, 0.5, 0.2, 0.1, 0.1, # Sellmeier
        -1.0, -10.0, -2.0, -15.0, # base 1 & 2
        0.05, 1.0, 0.2, 2.0 # Gauss
    ])
    
    from CERTUS_INDEX import sellmeier_2poles_eval_nj
    wl_um = wls / 1000.0
    n_tlu_ref = sellmeier_2poles_eval_nj(p0[:5], wl_um)

    obj = IRGlobalObjective(wls, target_T, target_R, n_sub, T_sub, R_sub, thickness, n_tlu_ref, config)
    obj.n_tol = 100.0 # disable n continuity guard entirely just in case

    
    def cost_wrapper(x):
        return obj(x)

    print("Base cost:", obj(p0))
        
    grad_ana = obj.gradient(p0)
    grad_fd = approx_derivative(cost_wrapper, p0, rel_step=1e-7)
    
    diff = np.abs(grad_ana - grad_fd)
    max_diff = np.max(diff)
    print("Analytic:", grad_ana)
    print("FD:      ", grad_fd)
    print("Diffs:   ", diff)
    assert max_diff < 1e-4, f"Gradient mismatch! Max diff: {max_diff}\nAna: {grad_ana}\nFD: {grad_fd}"

if __name__ == '__main__':
    test_phase2_gradient_analytic_vs_fd()
