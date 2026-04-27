"""
CERTUS Physics - Data Structures
================================
Part of CERTUS Suite (Harmonized Architecture 2026)

Contains:
- Layer: Thin film layer definition
- Target: Spectral target
- ObliqueTarget: Target for oblique incidence
- TLUParameters: Tauc-Lorentz-Urbach parameters
- Sample: Optimization sample
- PGlobalConfig: PGLOBAL optimizer configuration
"""

from dataclasses import dataclass


import numpy as np

# Import constants from core (Single Source of Truth)
from certus_core import CFG, SUBSTRATE_MIN_LAMBDA, SELLMEIER_COEFFS_BY_ID

# Alias for naming consistency
SUBSTRATE_MIN_LAMBDA_BY_ID = SUBSTRATE_MIN_LAMBDA

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass(slots=True)
class Layer:
    """Thin film layer definition (slots=True for reduced RAM footprint)"""

    mat: str  # Material ID
    qwot: float  # Optical thickness (QWOT)
    var: bool = True  # Variable (optimizable)

    def get_thickness(self, l0: float, n_at_l0: float) -> float:
        """Calculates physical thickness"""
        if n_at_l0 > CFG.EPSILON:
            return self.qwot * l0 / (4.0 * n_at_l0)
        return 0.0


@dataclass(slots=True)
class Target:
    """Spectral target (slots=True for reduced RAM footprint)"""

    lmin: float
    lmax: float
    tmin: float
    tmax: float
    w: float = 1.0
    on: bool = True

    def valid(self) -> bool:
        return self.on and self.lmax >= self.lmin and self.w > 0


@dataclass(slots=True)
class ObliqueTarget:
    """Target for oblique incidence (slots=True for reduced RAM footprint)"""

    angle: float  # Angle in degrees
    pol: str  # 'S', 'P', or 'Avg'
    lmin: float
    lmax: float
    tmin: float
    tmax: float
    target_type: str = "T"  # 'R' or 'T'
    w: float = 1.0
    on: bool = True
    # False = front stack only (semi-infinite substrate, no rear-surface specular return)
    include_backside: bool = True

    def valid(self) -> bool:
        return self.on and self.lmax >= self.lmin and self.w > 0


@dataclass(slots=True)
class TLUParameters:
    """Tauc-Lorentz-Urbach parameters (slots=True for reduced RAM footprint)"""

    Eg: float
    A: float
    E0: float
    C: float
    Eu: float
    eps_inf: float

    def to_array(self) -> np.ndarray:
        return np.array([self.Eg, self.A, self.E0, self.C, self.Eu, self.eps_inf])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "TLUParameters":
        return cls(Eg=arr[0], A=arr[1], E0=arr[2], C=arr[3], Eu=arr[4], eps_inf=arr[5])


@dataclass(frozen=True, slots=True)
class Sample:
    """Optimization Sample (frozen+slots for minimal footprint in global optimization)"""

    x: np.ndarray
    y: float
    generation: int = 0
    cluster_id: int = -1


@dataclass(frozen=True, slots=True)
class PGlobalConfig:
    """PGLOBAL Configuration

    Default values optimized via Bayesian hyperparameter search.
    """

    h_init_ratio: float = 0.03
    h_min: float = 1e-9
    max_fails_before_shrink: int = 2
    shrink_factor: float = 0.55
    accel_factor: float = 2.0
    max_line_search_steps: int = 50
    alpha: float = 0.04
    n_samples_per_iter: int = 1500
    reduction_ratio: float = 0.3
    max_active_clusters: int = 20
    local_search_budget: int = 20000
    max_feval: int = 1000000
    max_time: float = 3000.0
    convergence_tol: float = 1e-8
    random_seed: int | None = None

    @classmethod
    def for_index(
        cls, max_feval: int = 80000, max_time: float = 240.0
    ) -> "PGlobalConfig":
        return cls(max_feval=max_feval, max_time=max_time)

    @classmethod
    def for_dimension(
        cls, dim: int, base_samples: int = 5000, max_feval: int = 50000000
    ) -> "PGlobalConfig":
        """Config adapted to problem dimension.

        Values optimized via Bayesian HPO (Optuna, 50 trials × 3 repeats)
        on 26-layer beamsplitter benchmark (JSON-design-example.json).

        Key findings vs previous defaults (best RMSE=0.00526):
        - alpha 0.04 -> 0.008: finer clustering discovers more basins
        - base_samples 2000 -> 5000: more exploration per iteration
        - reduction_ratio 0.25 -> 0.34: keep more candidates before clustering
        - local_search_budget 25000 -> 42000: L-BFGS-B converges properly
        - max_active_clusters: adaptive dim*2, capped at 60
        """
        scale_factor = max(1.0, dim / 10.0)
        return cls(
            n_samples_per_iter=int(base_samples * scale_factor),
            alpha=0.008,
            reduction_ratio=0.34,
            local_search_budget=42000,
            max_active_clusters=min(60, max(10, int(dim * 2))),
            max_feval=max_feval,
            max_time=300.0,
        )

    @classmethod
    def for_local(
        cls, dim: int, max_feval: int = 10000, convergence_tol: float = 1e-8
    ) -> "PGlobalConfig":
        """Config optimized for local refinement (polish phase)."""
        return cls(
            max_feval=max_feval,
            local_search_budget=1000 + 100 * dim,
            alpha=0.02,
            convergence_tol=convergence_tol,
            n_samples_per_iter=500,
            reduction_ratio=0.2,
            h_init_ratio=0.01,
            max_active_clusters=1,
        )

    def with_overrides(self, **kwargs) -> "PGlobalConfig":
        import dataclasses

        return dataclasses.replace(self, **kwargs)


# =============================================================================
# SUBSTRATE DATA - Imported from certus_core (see imports at top)
# =============================================================================
# SELLMEIER_COEFFS_BY_ID and SUBSTRATE_MIN_LAMBDA_BY_ID are imported from certus_core
