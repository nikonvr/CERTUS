from typing import Any

# Sellmeier Coefficients for Substrates (Single Source of Truth)
#
# Format: (B1, C1, B2, C2, B3, C3)
#
# IMPORTANT:
# - Sapphire is the sapphire substrate (Al2O3)
# - In CERTUS, sapphire substrates must always resolve to the Sellmeier law.

SELLMEIER_COEFFS_BY_ID: dict[int, tuple[float, ...]] = {
    0: (
        0.6961663,
        0.0684043**2,
        0.4079426,
        0.1162414**2,
        0.8974794,
        9.896161**2,
    ),  # SiO2/Silica
    1: (
        1.03961212,
        0.00600069867,
        0.231792344,
        0.0200179144,
        1.01046945,
        103.560653,
    ),  # N-BK7
    # D263T eco: SCHOTT Zemax catalog 2017-01-20b (refractiveindex.info, D263TECO), 0.334-2.325 um. Within 2.1e-4 of
    # the maker's sheet (F 1.5300, e 1.5255, d 1.5231, C 1.5204; tolerance 1.5e-3); the set before gave n_d = 1.5201 (D56).
    2: (
        1.23795755,
        0.00863080926,
        0.0466468888,
        0.0469074501,
        2.46700556,
        264.146296,
    ),  # D263T
    3: (
        1.4313493,
        0.0726631**2,
        0.65054713,
        0.1193242**2,
        5.3414021,
        18.028251**2,
    ),  # Sapphire (Al2O3)
    # B270i: SCHOTT publishes no Sellmeier constants, only eight line indices (g to C, 436-656 nm: n_d 1.5230). B1 and
    # C1 are fitted to them (largest residual 4.4e-5); the other four terms are those of the set committed before, of
    # unknown origin, which gave n_d = 1.5257 (D56). Beyond 656 nm the index rests on those four terms.
    4: (
        0.88788095,
        0.0065395174,
        0.39734436,
        0.016601149,
        0.94615601,
        111.88593,
    ),  # B270i
}


# Substrate Definitions

SUBSTRATES: dict[str, dict[str, Any]] = {
    "SiO2": {"id": 0, "min_lambda": 230.0},
    "N-BK7": {"id": 1, "min_lambda": 400.0},
    "D263T eco": {"id": 2, "min_lambda": 360.0},
    "Sapphire (Al2O3)": {"id": 3, "min_lambda": 230.0},
    "B270i": {"id": 4, "min_lambda": 400.0},
    "Silicon (Si)": {"id": -1, "min_lambda": 200.0},  # Absorbing - tabulated n,k from clues.xlsx
}


SUBSTRATE_MAPPING: dict[str, str] = {
    "N-BK7": "N-BK7",
    "SiO2": "SiO2",
    "Sapphire": "Sapphire (Al2O3)",
    "Sapphire (Al2O3)": "Sapphire (Al2O3)",
    "Si-substrate": "Si-substrate",
}


SUBSTRATE_LIST = list(SUBSTRATES.keys())

# Canonical, de-duplicated labels for UI selection lists.
SUBSTRATE_CHOICES = tuple(dict.fromkeys(
    [
        "Sapphire (Al2O3)",
        "SiO2",
        "N-BK7",
        "D263T eco",
        "B270i",
        "Silicon (Si)",
        "Air",
        "Sapphire Fresnel",
    ]
))

CANONICAL_SUBSTRATE_LABELS: dict[str, str] = {
    "sapphire": "Sapphire (Al2O3)",
    "sapphire (al2o3)": "Sapphire (Al2O3)",
    "al2o3": "Sapphire (Al2O3)",
    "saphir": "Sapphire (Al2O3)",
    "fused silica": "SiO2",
    "fusedsilica": "SiO2",
    "sio2": "SiO2",
    "n-bk7": "N-BK7",
    "bk7": "N-BK7",
    "d263t": "D263T eco",
    "d263t eco": "D263T eco",
    "b270i": "B270i",
    "silicon": "Silicon (Si)",
    "si": "Silicon (Si)",
    "si-substrate": "Silicon (Si)",
    "air": "Air",
    "void": "Air",
    "vacuum": "Air",
    "sapphire fresnel": "Sapphire Fresnel",
    "sapphire (fr)": "Sapphire Fresnel",
}


# Reverse lookup for canonicalized labels.
_CANONICAL_SUBSTRATE_LABELS_NORM: dict[str, str] = {
    key.strip().lower(): value for key, value in CANONICAL_SUBSTRATE_LABELS.items()
}


def canonicalize_substrate_label(label: str | None) -> str | None:
    """Return the canonical CERTUS substrate label for any known alias."""

    raw = str(label or "").strip()
    if not raw:
        return None

    norm = raw.casefold()
    return _CANONICAL_SUBSTRATE_LABELS_NORM.get(norm, raw)


def substrate_sellmeier_id(label: str | None) -> int | None:
    """Resolve a substrate label to its Sellmeier catalog id when known."""

    canon = canonicalize_substrate_label(label)
    if canon is None:
        return None

    info = SUBSTRATES.get(canon)
    if info is not None:
        sid = int(info.get("id", -1))
        return sid if sid >= 0 else None

    return None


def substrate_sellmeier_coeffs(label: str | None) -> tuple[float, ...] | None:
    """Resolve a substrate label to its canonical Sellmeier coefficients."""

    sid = substrate_sellmeier_id(label)
    if sid is None:
        return None
    coeffs = SELLMEIER_COEFFS_BY_ID.get(int(sid))
    if coeffs is None:
        return None
    return tuple(float(v) for v in coeffs)


SUBSTRATE_MIN_LAMBDA: dict[int, float] = {
    0: 230.0,
    1: 400.0,
    2: 360.0,
    3: 230.0,
    4: 400.0,
}


# =============================================================================

