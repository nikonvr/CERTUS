import pytest
import numpy as np
from certus.core._certus_physics_impl import (
    calc_spectrum_front,
    calc_spectrum_full,
)

def test_calc_spectrum_front():
    wls = np.array([500.0])
    
    # Air | Layer | Substrate
    # Substrate: n=1.5
    # Layer: n=2.0, d=0.0 (Zero thickness should be transparent, so it's just bare substrate)
    
    d_layers = np.array([0.0])
    n_layers = np.array([[complex(2.0, 0.0)]])
    n_sub = np.array([complex(1.5, 0.0)])
    
    T, R = calc_spectrum_front(wls, d_layers, n_layers, n_sub)
    
    # Bare substrate reflection R = ((1 - 1.5)/(1 + 1.5))^2 = 0.04
    # Bare substrate transmission T = 1 - 0.04 = 0.96 (since it's Front-Only without incoherent backside)
    
    assert len(R) == 1
    assert len(T) == 1
    assert np.isclose(R[0], 0.04)
    assert np.isclose(T[0], 0.96)
    
    # Layer: n=2.0, d=125.0 (QWOT at 500nm, n=2)
    # R_qwot = ((n_sub - n_film^2) / (n_sub + n_film^2))^2 = ((1.5 - 4.0) / (1.5 + 4.0))^2 = (-2.5 / 5.5)^2 = 0.206611
    d_layers_qwot = np.array([125.0]) # lambda / (4*n) = 500 / (4*2) = 125/2 = 62.5
    d_layers_qwot = np.array([62.5])
    
    T2, R2 = calc_spectrum_front(wls, d_layers_qwot, n_layers, n_sub)
    
    assert np.isclose(R2[0], 0.20661157024793386)
    assert np.isclose(T2[0], 1.0 - R2[0])

def test_calc_spectrum_full():
    wls = np.array([500.0])
    
    # Front: bare substrate
    d_front = np.array([0.0])
    n_front = np.array([[complex(2.0, 0.0)]])
    
    # Back: bare substrate
    d_back = np.array([0.0])
    n_back = np.array([[complex(2.0, 0.0)]])
    
    n_sub = np.array([complex(1.5, 0.0)])
    
    Rf, Tf, Rb, Tb = calc_spectrum_full(wls, d_front, n_front, d_back, n_back, n_sub)
    
    assert np.isclose(Rf[0], 0.04)
    assert np.isclose(Tf[0], 0.96)
    assert np.isclose(Rb[0], 0.04)
    assert np.isclose(Tb[0], 0.96)
