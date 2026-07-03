import numpy as np
import logging

logger = logging.getLogger("CERTUS_WARMUP")

def run_warmup(progress_callback=None):
    """
    Forces Numba to compile the critical physics functions by calling them with dummy data.
    This effectively eliminates the JIT warmup time when the user interacts with the UI.
    """
    logger.info("Starting Numba JIT pre-warming...")
    
    # Resolve circular imports safely
    import certus.physics.certus_opt_tmm
    
    # Dummy data
    wls = np.linspace(400, 800, 100, dtype=np.float64)
    n_sub = np.full_like(wls, 1.5)
    
    try:
        if progress_callback: progress_callback("Warming up TMM Matrix functions...")
        from certus.physics.certus_tmm_matrix import calculate_bare_substrate_R
        calculate_bare_substrate_R(wls, n_sub)
    except Exception as e:
        logger.error(f"Warmup TMM Matrix failed: {e}")
        
    try:
        if progress_callback: progress_callback("Warming up TMM Oblique functions...")
        from certus.physics.certus_tmm_oblique import calculate_bare_substrate_R as calc_oblique
        calc_oblique(wls, n_sub)
    except Exception as e:
        logger.error(f"Warmup TMM Oblique failed: {e}")

    try:
        if progress_callback: progress_callback("Warming up TMM Single Layer functions...")
        from certus.physics.certus_tmm_single_layer import calculate_bare_substrate_R as calc_single
        calc_single(wls, n_sub)
    except Exception as e:
        logger.error(f"Warmup TMM Single Layer failed: {e}")
        
    try:
        if progress_callback: progress_callback("Warming up Colorimetry functions...")
        from certus.physics.certus_colorimetry import xyz_from_spectrum
        xyz_from_spectrum(wls, np.ones_like(wls))
    except Exception as e:
        logger.error(f"Warmup Colorimetry failed: {e}")

    if progress_callback: progress_callback("Numba warmup completed.")
    logger.info("Numba JIT pre-warming finished successfully.")
