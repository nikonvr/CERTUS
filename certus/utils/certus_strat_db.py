import logging

from pathlib import Path


import numpy as np


import pandas as pd


from certus.core.certus_core import SELLMEIER_COEFFS_BY_ID, SUBSTRATES, NUMERICAL_FAULT_EXCEPTIONS


def _build_sellmeier_by_name() -> dict:
    """Build a name-keyed Sellmeier dict from certus.core.certus_core's ID-keyed dict (module-level helper)."""

    id_to_name = {v["id"]: k for k, v in SUBSTRATES.items()}

    result = {id_to_name.get(sid, str(sid)): coeffs for sid, coeffs in SELLMEIER_COEFFS_BY_ID.items()}

    result["Silica"] = result["SiO2"]

    result["Sapphire (FR)"] = result["Sapphire (Al2O3)"]

    result["Sapphire Fresnel"] = (1.4155, 0.00904, 0.6356, 0.00905, 3.2352, 226.57863)

    # Silicon Fresnel Sellmeier REMOVED - Si data comes from clues.xlsx (Single Source of Truth)

    return result


_SELLMEIER_COEFFS_BY_NAME = _build_sellmeier_by_name()


def find_matching_sheets(target_name: str, sheet_names: list[str]) -> list[str]:
    """Find all Excel sheets whose name matches ``target_name``, accounting for
    case, separators, process suffixes, and chemical aliases.

    Matching strategy (two-pass)
    ----------------------------
    1. **Exact match** (case-insensitive): the sheet name equals the target.
    2. **Structured match**: both the target and the sheet contain a known
       *process* token (e.g. ``"h800"``) **and** a known *material* token
       (e.g. ``"nb2o5"``).  Both tokens must agree after alias normalisation.
    3. **Substring fallback**: if either side lacks a structured token,
       stripped alphanumeric strings are compared with ``in`` containment.

    Alias table
    -----------
    ``"nb"`` is treated as a synonym for ``"nb2o5"`` (both map to
    ``"nb2o5"`` in the canonical form).  Any new alias must be added to
    **both** the ``ALIASES`` dict here **and** in the copy of this function
    in ``certus/core/_certus_physics_impl.py``.

    RULE: keep PROCESSES and MATERIALS in sync with the actual sheet names
    present in ``clues.xlsx``.  A material missing from MATERIALS will fall
    back to substring matching, which is more permissive and may return
    false positives.

    Returns
    -------
    list[str]
        Ordered list of matching sheet names (duplicates removed, insertion
        order preserved).  Empty list if nothing matches.
    """
    target_clean = target_name.lower().replace("-", " ").replace("_", " ").split()
    
    PROCESSES = {"h800", "h400", "syrus", "helios"}
    MATERIALS = {"sio2", "nb2o5", "nb", "ta2o5", "al2o3", "hfo2", "zns", "tio2", "yf3", "si"}
    
    ALIASES = {
        "nb": "nb2o5",
        "nb2o5": "nb2o5",
    }
    
    def get_canonical_material(word):
        return ALIASES.get(word, word)
    
    target_proc = None
    target_mat = None
    for word in target_clean:
        if word in PROCESSES:
            target_proc = word
        elif word in MATERIALS:
            target_mat = get_canonical_material(word)
            
    matches = []
    for sheet in sheet_names:
        sheet_lower = sheet.lower()
        if sheet_lower == target_name.lower():
            matches.append(sheet)
            continue
            
        sheet_clean = sheet_lower.replace("-", " ").replace("_", " ").split()
        sheet_proc = None
        sheet_mat = None
        for word in sheet_clean:
            if word in PROCESSES:
                sheet_proc = word
            elif word in MATERIALS:
                sheet_mat = get_canonical_material(word)
                
        if target_proc and target_mat and sheet_proc and sheet_mat:
            if target_proc == sheet_proc and target_mat == sheet_mat:
                matches.append(sheet)
        else:
            target_stripped = "".join(c for c in target_name.lower() if c.isalnum())
            sheet_stripped = "".join(c for c in sheet.lower() if c.isalnum())
            if target_stripped in sheet_stripped or sheet_stripped in target_stripped:
                matches.append(sheet)
                
    unique_matches = []
    for m in matches:
        if m not in unique_matches:
            unique_matches.append(m)
    return unique_matches


def merge_two_curves(c1, c2):
    """Merge two dispersion curves (n, k) ensuring C0 continuity at their junction.

    Each curve is a dict with keys:
    - ``'wl'`` : 1-D numpy array of wavelengths (nm), **must be sorted ascending**.
    - ``'n'``  : 1-D numpy array of real refractive index values.
    - ``'k'``  : 1-D numpy array of extinction coefficients (optional).

    The function automatically sorts the two curves so that c1 spans the
    shorter-wavelength range.

    Three cases handled
    -------------------
    1. **No overlap** (``max(wl1) < min(wl2)``): curves are simply
       concatenated.  A physical gap in wavelength coverage between the two
       sheets will produce a step discontinuity — this is acceptable only
       when the gap is large enough that no simulation target wavelength
       falls inside it.

    2. **Single-point touch** (``overlap_max <= overlap_min``, i.e. the
       curves share exactly one boundary wavelength):
       ``n2`` is **shifted** by the constant offset
       ``D = n2(wl_boundary) - n1(wl_boundary)``
       so that the merged curve is C0-continuous at the junction.
       *Rationale*: blending over a zero-width interval is undefined and
       would leave a jump equal to D.

    3. **True overlap** (``overlap_max > overlap_min``):
       Within the overlap band, values are blended linearly from
       ``weight=0`` (pure c1) at ``overlap_min`` to ``weight=1`` (pure c2)
       at ``overlap_max``.  Outside the band the curve that owns that
       wavelength region is used exclusively.

    PHYSICAL CONSTRAINT: the merged n(λ) must be monotone-enough for the
    TMM kernel to converge.  Large offsets between sheets (> ~0.1 in n)
    will produce a kink even after shifting — review the source data in
    ``clues.xlsx`` if that happens.

    WARNING: DO NOT remove the ``overlap_max <= overlap_min`` branch and
    replace it with pure blending — blending over a zero-width interval
    reduces to a weighted average of two potentially different values at
    the same wavelength, which cannot eliminate the jump.
    """
    wl1, n1 = c1['wl'], c1['n']
    wl2, n2 = c2['wl'], c2['n']
    
    has_k = ('k' in c1 or 'k' in c2)
    k1 = c1.get('k') if c1.get('k') is not None else np.zeros_like(n1)
    k2 = c2.get('k') if c2.get('k') is not None else np.zeros_like(n2)
    
    if wl1[0] > wl2[0]:
        wl1, wl2 = wl2, wl1
        n1, n2 = n2, n1
        k1, k2 = k2, k1
        
    min_wl1, max_wl1 = wl1[0], wl1[-1]
    min_wl2, max_wl2 = wl2[0], wl2[-1]
    
    if max_wl1 < min_wl2:
        merged_wl = np.concatenate([wl1, wl2])
        merged_n = np.concatenate([n1, n2])
        res = {
            'wl': merged_wl,
            'n': merged_n,
            'min_wl_valid': float(merged_wl[0]),
            'max_wl_valid': float(merged_wl[-1])
        }
        if has_k:
            res['k'] = np.concatenate([k1, k2])
        return res
        
    overlap_min = min_wl2
    overlap_max = min(max_wl1, max_wl2)
    
    # Shifting to ensure perfect continuity ONLY at single-point touch boundaries.
    # Blending over an interval handles continuity naturally.
    if overlap_max <= overlap_min:
        val1_boundary = np.interp(overlap_min, wl1, n1)
        val2_boundary = np.interp(overlap_min, wl2, n2)
        offset = val2_boundary - val1_boundary
        n2_shifted = n2 - offset
    else:
        n2_shifted = n2
        
    all_wls = np.unique(np.concatenate([wl1, wl2]))
    merged_n = np.zeros_like(all_wls)
    if has_k:
        merged_k = np.zeros_like(all_wls)
        
    def interp_c(wl, wl_orig, val_orig):
        return np.interp(wl, wl_orig, val_orig)
    
    for idx, wl in enumerate(all_wls):
        if wl < overlap_min:
            merged_n[idx] = interp_c(wl, wl1, n1)
            if has_k:
                merged_k[idx] = interp_c(wl, wl1, k1)
        elif wl > overlap_max:
            merged_n[idx] = interp_c(wl, wl2, n2_shifted)
            if has_k:
                merged_k[idx] = interp_c(wl, wl2, k2)
        else:
            val1 = interp_c(wl, wl1, n1)
            val2 = interp_c(wl, wl2, n2_shifted)
            if overlap_max > overlap_min:
                weight = (wl - overlap_min) / (overlap_max - overlap_min)
            else:
                weight = 0.5
            merged_n[idx] = (1.0 - weight) * val1 + weight * val2
            
            if has_k:
                kval1 = interp_c(wl, wl1, k1)
                kval2 = interp_c(wl, wl2, k2)
                merged_k[idx] = (1.0 - weight) * kval1 + weight * kval2
                
    res = {
        'wl': all_wls,
        'n': merged_n,
        'min_wl_valid': float(all_wls[0]),
        'max_wl_valid': float(all_wls[-1])
    }
    if has_k:
        res['k'] = merged_k
    return res


def merge_multiple_curves(curves: list[dict]) -> dict:
    """Merge an ordered list of dispersion curve dicts into a single curve.

    Curves are first sorted by their minimum wavelength, then folded
    left-to-right with :func:`merge_two_curves`.  The result therefore
    inherits all continuity guarantees of that function for each adjacent
    pair.

    RULE: if three or more sheets overlap pairwise, the pairwise sequential
    merge is not equivalent to a global weighted blend.  In practice this
    should not arise because ``clues.xlsx`` sheets are intended to cover
    disjoint or minimally-overlapping wavelength ranges.
    """
    if not curves:
        return {}
    sorted_curves = sorted(curves, key=lambda c: c['wl'][0])
    merged = sorted_curves[0]
    for next_curve in sorted_curves[1:]:
        merged = merge_two_curves(merged, next_curve)
    return merged


class MergedMaterialDict(dict):
    """Drop-in ``dict`` replacement that transparently merges multi-sheet
    material data from ``clues.xlsx`` on first access.

    Motivation
    ----------
    Some materials (e.g. Nb2O5, SiO2) are split across several Excel sheets
    covering different wavelength ranges (visible vs. IR).  A plain ``dict``
    keyed by sheet name would expose ``'Nb2O5 H800'`` and ``'Nb2O5 H800 IR'``
    as two separate, incompatible entries.  This class intercepts ``__getitem__``
    and ``__contains__`` to:

    1. Call :func:`find_matching_sheets` to discover all sheets whose name
       is consistent with the requested material key.
    2. If more than one sheet matches, merge them with
       :func:`merge_multiple_curves` (once, then cache the result).
    3. Return the merged curve as if the dict had a single entry.

    Cache
    -----
    ``self._merged_cache`` stores already-merged results keyed by the
    original lookup key.  DO NOT clear this cache during a simulation run —
    the merge is deterministic but expensive.

    RULE: ``self.sheet_names`` must stay in sync with the actual keys in
    the underlying dict (``super().keys()``).  They are set once at
    construction from ``list(self.materials.keys())`` and are not updated
    if the dict is mutated after construction.
    """
    def __init__(self, raw_data, sheet_names, logger=None):
        super().__init__(raw_data)
        self.sheet_names = sheet_names
        self.logger = logger or logging.getLogger("ThinFilm")
        self._merged_cache = {}

    def __contains__(self, key):
        if super().__contains__(key):
            return True
        matches = find_matching_sheets(key, self.sheet_names)
        return len(matches) > 0

    def __getitem__(self, key):
        if super().__contains__(key):
            matches = find_matching_sheets(key, self.sheet_names)
            if len(matches) <= 1:
                return super().__getitem__(key)
        else:
            matches = find_matching_sheets(key, self.sheet_names)
            if not matches:
                raise KeyError(key)
                
        if key in self._merged_cache:
            return self._merged_cache[key]
            
        if len(matches) > 1:
            self.logger.info(f"Merging multiple sheets for material '{key}': {matches}")
        curves = [super().__getitem__(m) for m in matches]
        merged = merge_multiple_curves(curves)
        self._merged_cache[key] = merged
        return merged


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

    # Name-keyed Sellmeier dict built from certus.core.certus_core (Single Source of Truth)

    SELLMEIER_COEFFS = _SELLMEIER_COEFFS_BY_NAME

    def __init__(self, filepath, logger=None):

        self.filepath = filepath

        self.logger = logger or logging.getLogger("ThinFilm")

        self.materials = {}

        self._load_database()

        if not isinstance(self.materials, MergedMaterialDict):
            self.materials = MergedMaterialDict(self.materials, list(self.materials.keys()), self.logger)

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

        except NUMERICAL_FAULT_EXCEPTIONS as e:
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
