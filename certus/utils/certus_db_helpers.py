import logging
import numpy as np

def find_matching_sheets(target_name: str, sheet_names: list[str]) -> list[str]:
    """Return sheets that match ``target_name`` using explicit token rules.

    The helper is intentionally conservative: it prefers exact matches,
    then structured matches, and only then falls back to substring checks.
    This makes material/database resolution more predictable and easier to
    reason about in production.
    """
    normalized_target = target_name.lower().replace("-", " ").replace("_", " ").split()

    PROCESSES = {"h800", "h400", "syrus", "helios"}
    MATERIALS = {"sio2", "nb2o5", "nb", "ta2o5", "al2o3", "hfo2", "zns", "tio2", "yf3", "si"}
    ALIASES = {"nb": "nb2o5", "nb2o5": "nb2o5"}

    def canonical(word: str) -> str:
        return ALIASES.get(word, word)

    def parse_tokens(text: str) -> tuple[str | None, str | None]:
        proc = None
        mat = None
        for word in text.lower().replace("-", " ").replace("_", " ").split():
            if word in PROCESSES:
                proc = word
            elif word in MATERIALS:
                mat = canonical(word)
        return proc, mat

    target_proc, target_mat = parse_tokens(target_name)
    target_stripped = "".join(c for c in target_name.lower() if c.isalnum())

    matches: list[str] = []
    for sheet in sheet_names:
        sheet_lower = sheet.lower()
        if sheet_lower == target_name.lower():
            matches.append(sheet)
            continue

        sheet_proc, sheet_mat = parse_tokens(sheet)
        if target_proc and target_mat and sheet_proc and sheet_mat:
            if target_proc == sheet_proc and target_mat == sheet_mat:
                matches.append(sheet)
            continue

        sheet_stripped = "".join(c for c in sheet_lower if c.isalnum())
        if target_stripped in sheet_stripped or sheet_stripped in target_stripped:
            matches.append(sheet)

    unique_matches: list[str] = []
    for match in matches:
        if match not in unique_matches:
            unique_matches.append(match)
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


