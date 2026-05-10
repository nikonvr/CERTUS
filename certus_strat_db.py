import logging

from pathlib import Path


import numpy as np


import pandas as pd


from certus_core import SELLMEIER_COEFFS_BY_ID, SUBSTRATES


def _build_sellmeier_by_name() -> dict:
    """Build a name-keyed Sellmeier dict from certus_core's ID-keyed dict (module-level helper)."""

    id_to_name = {v["id"]: k for k, v in SUBSTRATES.items()}

    result = {id_to_name.get(sid, str(sid)): coeffs for sid, coeffs in SELLMEIER_COEFFS_BY_ID.items()}

    result["Silica"] = result["SiO2"]

    result["Sapphire (FR)"] = result["Sapphire (Al2O3)"]

    result["Sapphire Fresnel"] = (1.4155, 0.00904, 0.6356, 0.00905, 3.2352, 226.57863)

    # Silicon Fresnel Sellmeier REMOVED - Si data comes from clues.xlsx (Single Source of Truth)

    return result


_SELLMEIER_COEFFS_BY_NAME = _build_sellmeier_by_name()


class RobustMaterialDatabase:
    """

    A robust replacement for MaterialDatabase that handles:

    1. Excel files with missing headers (creates default headers).

    2. Excel files with headers (fuzzy matching).

    3. Silent fallbacks (logs warnings instead).

    """

    # ---------------------------------------------------------------------

    # DATA SOURCES & VALIDATION (2026-02 Upgrade)

    # 1. Sapphire Fresnel:

    #    - Source: Analytic formula from resultats_substrates.pdf

    #    - Verification: Matches reference table with Delta n < 1e-5.

    #    - Range: 280-4200 nm.

    # 2. Silicon: Data from clues.xlsx -> Si-substrate (Single Source of Truth).

    # ---------------------------------------------------------------------

    # Name-keyed Sellmeier dict built from certus_core (Single Source of Truth)

    SELLMEIER_COEFFS = _SELLMEIER_COEFFS_BY_NAME

    def __init__(self, filepath, logger=None):

        self.filepath = filepath

        self.logger = logger or logging.getLogger("ThinFilm")

        self.materials = {}

        self._load_database()

    def _load_database(self):

        if not Path(self.filepath).exists():
            self.logger.error(f"Material DB file not found: {self.filepath}")

            return

        self.logger.info(f"Loading Material DB (Robust): {self.filepath}")

        try:
            # Read all sheets

            xls = pd.read_excel(self.filepath, sheet_name=None)

            for sheet_name, df in xls.items():
                try:
                    clean_df = self._standardize_dataframe(df, sheet_name)

                    if clean_df is not None:
                        # Store as (wl, n, k) numpy arrays sorted by wl

                        clean_df.sort_values(by="wl", inplace=True)

                        self.materials[sheet_name] = {
                            "wl": clean_df["wl"].to_numpy(dtype=np.float64),
                            "n": clean_df["n"].to_numpy(dtype=np.float64),
                            "k": clean_df["k"].to_numpy(dtype=np.float64),
                        }

                        # Self-test

                        # self.logger.info(f"Loaded '{sheet_name}': {len(clean_df)} points.")

                except (
                    ValueError,
                    TypeError,
                    RuntimeError,
                    AttributeError,
                    KeyError,
                    IndexError,
                    FileNotFoundError,
                ) as e:
                    self.logger.warning(f"Skipping sheet '{sheet_name}': {e}")

            self.logger.info(f"Robust DB Loaded {len(self.materials)} materials.")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            self.logger.error(f"Failed to load Excel DB: {e}")

    def _standardize_dataframe(self, df, sheet_name):

        # 1. Check if empty

        if df.empty:
            return None

        # 2. Check header strategy

        # If headers are floats/ints, it's likely headerless

        first_col = df.columns[0]

        is_headerless = isinstance(first_col, (int, float))

        if is_headerless:
            # Reload? No, just push columns to row 0

            # Create a new df including the 'header' as the first row

            # But wait, df.columns contains the first row data.

            # We must reconstruct.

            # Extract data from columns

            header_row = pd.DataFrame([df.columns], columns=range(len(df.columns)))

            # Rename original df columns to range

            df.columns = range(len(df.columns))

            # Concat

            df = pd.concat([header_row, df], ignore_index=True)

            # Now we have data. Expect 3 cols: wl, n, k (or 2: wl, n)

            if df.shape[1] >= 3:
                df.columns = ["wl", "n", "k"] + list(range(3, df.shape[1]))

            elif df.shape[1] == 2:
                df.columns = ["wl", "n"]

                df["k"] = 0.0

            else:
                return None

        else:
            # Has headers? Try to map them

            # normalize cols

            cols = [str(c).lower().strip() for c in df.columns]

            df.columns = cols

            # Map WL

            wl_col = next((c for c in cols if "wave" in c or "lam" in c or "wl" in c), None)

            if not wl_col:
                wl_col = cols[0]  # Fallback col 0

            # Map N

            n_col = next(
                (c for c in cols if c == "n" or "n_" in c or "ref" in c or c.startswith("n")),
                None,
            )

            if not n_col:
                # Fallback: col 1 if it's not wl

                n_col = cols[1] if len(cols) > 1 else None

            # Map K

            k_col = next(
                (c for c in cols if c == "k" or "ext" in c or "k_" in c or c.startswith("k")),
                None,
            )

            if not k_col:
                # Fallback: col 2

                k_col = cols[2] if len(cols) > 2 else None

            if not wl_col or not n_col:
                # Fallback purely position based if mapping failed

                if df.shape[1] >= 2:
                    wl_col = df.columns[0]

                    n_col = df.columns[1]

                    k_col = df.columns[2] if df.shape[1] > 2 else None

                else:
                    return None

            # Rename

            rename_map = {wl_col: "wl", n_col: "n"}

            if k_col:
                rename_map[k_col] = "k"

            df.rename(columns=rename_map, inplace=True)

            if "k" not in df.columns:
                df["k"] = 0.0

        # Ensure types

        df["wl"] = pd.to_numeric(df["wl"], errors="coerce")

        df["n"] = pd.to_numeric(df["n"], errors="coerce")

        df["k"] = pd.to_numeric(df["k"], errors="coerce")

        df.dropna(subset=["wl", "n"], inplace=True)

        return df[["wl", "n", "k"]]

    def _sellmeier_n(self, wl_um, B1, C1, B2, C2, B3, C3):
        """Calculate n from Sellmeier coefficients. wl in µm."""

        wl2 = wl_um**2

        n_sq = 1 + (B1 * wl2) / (wl2 - C1) + (B2 * wl2) / (wl2 - C2) + (B3 * wl2) / (wl2 - C3)

        return np.sqrt(max(1.0, n_sq))

    def get_refractive_index(self, mat_id, wl, db_instance=None):

        # db_instance arg for compatibility but ignored (self is instance)

        # Check Excel sheets first

        if mat_id in self.materials:
            mat_data = self.materials[mat_id]

            n_val = np.interp(wl, mat_data["wl"], mat_data["n"])

            k_val = np.interp(wl, mat_data["wl"], mat_data["k"])

            return complex(n_val, -k_val)

        # Fallback: Standard substrates via Sellmeier

        if mat_id in self.SELLMEIER_COEFFS:
            coeffs = self.SELLMEIER_COEFFS[mat_id]

            wl_um = wl / 1000.0  # nm -> µm

            n = self._sellmeier_n(wl_um, *coeffs)

            return complex(n, 0.0)

        # Final fallback: Air

        return 1.0 + 0j

    def get_refractive_clues_vectorized(self, mat_id, wls, db_instance=None):

        # Check Excel sheets first

        if mat_id in self.materials:
            mat_data = self.materials[mat_id]

            n_vals = np.interp(wls, mat_data["wl"], mat_data["n"])

            k_vals = np.interp(wls, mat_data["wl"], mat_data["k"])

            return (n_vals - 1j * k_vals).astype(np.complex128)

        # Fallback: Standard substrates via Sellmeier (vectorized)

        if mat_id in self.SELLMEIER_COEFFS:
            B1, C1, B2, C2, B3, C3 = self.SELLMEIER_COEFFS[mat_id]

            wl_um = np.asarray(wls) / 1000.0

            wl2 = wl_um**2

            n_sq = 1 + (B1 * wl2) / (wl2 - C1) + (B2 * wl2) / (wl2 - C2) + (B3 * wl2) / (wl2 - C3)

            n_vals = np.sqrt(np.maximum(1.0, n_sq))

            return n_vals.astype(np.complex128)

        # Final fallback: Air

        return np.ones(len(wls), dtype=np.complex128)

    def clear_cache(self):

        pass  # No cache logic needed for simple interp
