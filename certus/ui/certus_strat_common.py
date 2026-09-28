# =============================================================================
# CERTUS STRAT - PyQt6 User Interface components and application
# =============================================================================
import concurrent.futures

















# Conditional import of Svg for the logo

try:
    from PyQt6.QtSvgWidgets import QSvgWidget

except ImportError:
    QSvgWidget = None





# Import access config



from certus_physics import (  # STRAT-specific kernels (previously imported from certus.core._certus_physics_impl)
    MaterialDatabase,
    NON_MONOTONIC_MODE_ATTENUATE,
    calculate_RT_vectorized_real_HL,
    compute_batch_rmse,
    find_nucleation_adaptive_kernel,
    precompute_matrix_cache_kernel,
    rank_nucleation_candidates_kernel,
    simulate_growth_kernel,
    update_run_states_kernel,
    validate_wavelengths_batch,
)

# Import context system (replaces global variables)


# Robust db clues (fixed xlsx)



from certus.workers.certus_strat_workers import (
    _resolve_strat_indices_db_path,
)



class _LazyCertusStratApp:
    def __getattr__(self, name):
        from certus.ui.certus_strat_ui import CertusStratApp
        return getattr(CertusStratApp, name)

CertusStratApp = _LazyCertusStratApp()
