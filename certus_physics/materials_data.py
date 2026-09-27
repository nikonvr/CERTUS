"""CERTUS Physics - Materials Data


=============================


Silicon substrate optical constants (n, k), read from a 'Si-substrate' sheet.

Sources, in priority order: an optional LOCAL override at the project root
(material_constants.xlsx, then the legacy clues.xlsx -- neither has ever been
committed), then the VERSIONED database example/database_index/indices.xlsx.
The 15-point built-in stub is a last resort, logged as a WARNING. The source
actually used is exposed as SI_SOURCE."""





import logging
from pathlib import Path


import numpy as np


from numba import njit

from certus.utils.errors import CertusError, CertusFileError, CertusMaterialError





_log = logging.getLogger(__name__)





# =============================================================================


# SILICON DATA - Loaded from clues.xlsx -> Si-substrate (Single Source of Truth)


# =============================================================================





_SI_XLSX_SHEET = "Si-substrate"








def _silicon_stub_arrays() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Last-resort Si (n, k) when no spreadsheet loads: a coarse 15-point table.

    Its IR values (>= 1200 nm) follow the Salzberg & Villa (1957) Sellmeier formula for
    silicon, to within 5e-5 in n; a previous docstring attributed them to Li (1980).
    Below 1200 nm it is only a rough placeholder."""
    wl = np.array(
        [250.0, 400.0, 600.0, 800.0, 1000.0, 1200.0, 1500.0, 2000.0, 2500.0, 3000.0, 3500.0, 4000.0, 4500.0, 5000.0, 5200.0],
        dtype=np.float64,
    )
    n = np.array(
        [5.1, 4.2, 3.95, 3.75, 3.65, 3.5237, 3.4821, 3.4527, 3.4394, 3.4323, 3.4281, 3.4253, 3.4234, 3.4221, 3.4216],
        dtype=np.float64,
    )
    k = np.array(
        [0.15, 0.05, 0.02, 0.01, 0.008, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        dtype=np.float64,
    )
    return wl, n, k








def _find_materials_xlsx_path() -> str | None:
    """Find project-root materials constants spreadsheet (checks material_constants.xlsx then clues.xlsx)."""
    package_dir = Path(__file__).resolve().parent
    parent_dir = package_dir.parent
    
    preferred = parent_dir / "material_constants.xlsx"
    if preferred.is_file():
        return str(preferred)
        
    legacy = parent_dir / "clues.xlsx"
    if legacy.is_file():
        return str(legacy)
        
    return None








def _load_si_from_xlsx(xlsx_path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:


    """Load Silicon (n, k) from clues.xlsx -> Si-substrate sheet.





    Returns:


        (wavelengths_nm, n_data, k_data) - sorted, contiguous float64 arrays.





    Raises:


        ValueError: if the file or sheet is missing, or data is invalid."""


    if not Path(xlsx_path).is_file():


        raise CertusFileError(f"Silicon spreadsheet not found at {xlsx_path}")





    import pandas as pd





    try:


        df = pd.read_excel(


            xlsx_path, sheet_name=_SI_XLSX_SHEET, header=0, engine="openpyxl"


        )


    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:


        raise CertusFileError(f"Cannot read sheet '{_SI_XLSX_SHEET}' from {xlsx_path}: {e}") from e





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


        raise CertusMaterialError("Si-substrate sheet has fewer than 2 data points")


    if np.any(np.diff(wl) <= 0):


        raise CertusMaterialError("Silicon wavelengths are not strictly increasing after sorting")





    return wl, n, k








def _versioned_si_database_path() -> str:
    """The repository's own index database, which carries a 'Si-substrate' sheet.

    material_constants.xlsx and clues.xlsx are local overrides that have never been
    committed. Without this versioned source every clone fell back to the stub in
    silence -- measured 2026-09-25: air/Si reflectance off by -11 points at 400 nm and
    +0.9 point near 900 nm, for INDEX, RE and METAL BILAYER on a silicon substrate.
    """
    from certus.core.certus_config import get_resource_path

    return get_resource_path(str(Path("example") / "database_index" / "indices.xlsx"))


def _si_candidate_paths() -> list[str]:
    """Si sources in priority order: the local override first, then the versioned database."""
    candidates = []
    override = _find_materials_xlsx_path()
    if override:
        candidates.append(override)
    versioned = _versioned_si_database_path()
    if Path(versioned).is_file():
        candidates.append(versioned)
    return candidates


def _load_si_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    """Return (wavelengths_nm, n, k, source) from the first source that loads; stub last."""
    failures = []
    for path in _si_candidate_paths():
        try:
            wl, n, k = _load_si_from_xlsx(path)
        except (CertusError, OSError) as e:
            failures.append(f"{path}: {e}")
            continue
        _log.info("Silicon optical constants loaded from %s (%d points).", path, len(wl))
        return wl, n, k, path
    wl, n, k = _silicon_stub_arrays()
    detail = "; ".join(failures) if failures else "no Si-substrate spreadsheet found"
    _log.warning(
        f"Error loading Silicon optical constants ({detail}). "
        "Falling back to built-in Silicon constants: a 15-point approximation, off by up "
        "to 11 reflectance points in the visible."
    )
    return wl, n, k, "built-in stub"


_MATERIALS_PATH = _find_materials_xlsx_path()
SI_WAVELENGTH_NM, SI_N_DATA, SI_K_DATA, SI_SOURCE = _load_si_data()





# =============================================================================


# ACCESSORS


# =============================================================================








# NOT cached on disk: numba freezes module-level arrays as compile-time constants, and a
# cache keyed on this source file would keep serving the Si data of its FIRST compilation
# after the spreadsheet changes -- while INDEX and RE, which read the arrays at run time,
# would already see the new values. One compilation per process is the price.
@njit


def get_nk_si(wavelength_nm):


    """Return silicon complex index n̂ = n - ik (Macleod convention, k >= 0).





    CRITICAL CONVENTION: imaginary part is NEGATIVE for absorption.


    NEVER return n + ik (unphysical gain, would give R+T > 1).


    """


    n_interp = np.interp(wavelength_nm, SI_WAVELENGTH_NM, SI_N_DATA)


    k_interp = np.interp(wavelength_nm, SI_WAVELENGTH_NM, SI_K_DATA)


    k_interp = np.maximum(k_interp, 0.0)


    return n_interp - 1j * k_interp  # n - ik (Macleod)


