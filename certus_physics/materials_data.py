"""CERTUS Physics - Materials Data


=============================


Silicon substrate optical constants loaded from clues.xlsx (Si-substrate sheet).


SINGLE SOURCE OF TRUTH: clues.xlsx is the authoritative reference."""





import logging
from pathlib import Path


import numpy as np


from numba import njit





_log = logging.getLogger(__name__)





# =============================================================================


# SILICON DATA - Loaded from clues.xlsx -> Si-substrate (Single Source of Truth)


# =============================================================================





_SI_XLSX_SHEET = "Si-substrate"








def _silicon_stub_arrays() -> tuple[np.ndarray, np.ndarray, np.ndarray]:


    """Placeholder Si (n, k) when clues.xlsx is missing (tests / dev checkout without data)."""


    wl = np.array(


        [250.0, 400.0, 600.0, 800.0, 1000.0, 1200.0, 1500.0, 2000.0, 2500.0],


        dtype=np.float64,


    )


    n = np.array(


        [5.1, 4.2, 3.95, 3.75, 3.65, 3.55, 3.48, 3.45, 3.42],


        dtype=np.float64,


    )


    k = np.array(


        [0.15, 0.05, 0.02, 0.01, 0.008, 0.006, 0.004, 0.003, 0.002],


        dtype=np.float64,


    )


    return wl, n, k








def _clues_xlsx_path() -> str:


    """Project-root clues.xlsx (parent of certus_physics package)."""


    package_dir = Path(__file__).resolve().parent


    parent_dir = package_dir.parent


    return str(parent_dir / "clues.xlsx")








def _load_si_from_xlsx(xlsx_path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:


    """Load Silicon (n, k) from clues.xlsx -> Si-substrate sheet.





    Returns:


        (wavelengths_nm, n_data, k_data) - sorted, contiguous float64 arrays.





    Raises:


        ValueError: if the file or sheet is missing, or data is invalid."""


    if not Path(xlsx_path).is_file():


        raise ValueError(f"clues.xlsx not found at {xlsx_path}")





    import pandas as pd





    try:


        df = pd.read_excel(


            xlsx_path, sheet_name=_SI_XLSX_SHEET, header=0, engine="openpyxl"


        )


    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:


        raise ValueError(f"Cannot read sheet '{_SI_XLSX_SHEET}' from clues.xlsx:{e}")





    # Normalize column names


    df.columns = df.columns.astype(str).str.strip().str.lower()





    # Detect columns


    wl_col = next((c for c in df.columns if "wl" in c or "wave" in c or "lambda" in c), df.columns[0])


    n_col = next((c for c in df.columns if c == "n" or c.startswith("n")), df.columns[1])


    k_col = next((c for c in df.columns if c == "k" or c.startswith("k")), None)





    df = df.sort_values(by=wl_col).dropna(subset=[wl_col, n_col])





    wl = np.ascontiguousarray(df[wl_col].to_numpy(), dtype=np.float64)


    n = np.ascontiguousarray(df[n_col].to_numpy(), dtype=np.float64)


    k = np.ascontiguousarray(df[k_col].to_numpy(), dtype=np.float64) if k_col else np.zeros_like(wl)





    if len(wl) < 2:


        raise ValueError(f"Si-substrate sheet has fewer than 2 data points")


    if np.any(np.diff(wl) <= 0):


        raise ValueError("Silicon wavelengths are not strictly increasing after sorting")





    return wl, n, k








_CLUES_PATH = _clues_xlsx_path()


if not Path(_CLUES_PATH).is_file():


    SI_WAVELENGTH_NM, SI_N_DATA, SI_K_DATA = _silicon_stub_arrays()


    _log.info("Using built-in Silicon optical constants dataset.")


else:


    try:


        SI_WAVELENGTH_NM, SI_N_DATA, SI_K_DATA = _load_si_from_xlsx(_CLUES_PATH)


    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:


        raise ValueError(f"Fatal error loading Silicon optical constants: {e}") from e





# =============================================================================


# ACCESSORS


# =============================================================================








@njit(cache=True)


def get_nk_si(wavelength_nm):


    """Return silicon complex index n̂ = n - ik (Macleod convention, k >= 0).





    CRITICAL CONVENTION: imaginary part is NEGATIVE for absorption.


    NEVER return n + ik (unphysical gain, would give R+T > 1).


    """


    n_interp = np.interp(wavelength_nm, SI_WAVELENGTH_NM, SI_N_DATA)


    k_interp = np.interp(wavelength_nm, SI_WAVELENGTH_NM, SI_K_DATA)


    k_interp = np.maximum(k_interp, 0.0)


    return n_interp - 1j * k_interp  # n - ik (Macleod)


