import re
from collections.abc import Mapping
from typing import Final, TypedDict

# =============================================================================
# BRAND COLOURS - the single source, and it lives HERE on purpose (step 3.9)
# =============================================================================
#
# `certus/ui/certus_theme.py` used to declare the same four hex values again, so the two
# could drift apart. The duplication was NOT carelessness: `core` may never import
# `certus.ui`, so the shared fact had to move DOWN into the low layer, not up. The theme
# now reads these.
#
# The colour is the background of the card's icon tile, with the icon painted white on
# top (`certus_hub_widgets.py`). White on the accent is therefore the pair that matters;
# WCAG 1.4.11 asks 3:1 for a graphical object.
#
# Measured 2026-09-06, white on each accent:
#     DESIGN 4.23  INDEX 3.68  METAL 4.76  STRAT 2.54  <- STRAT is BELOW the floor
#     RE 3.51  FIELD 3.53  SMOOTHER 3.56  SUBSTRATE 3.41
#
# STRAT is left untouched on purpose: it is an established identity colour, and changing
# it is the project owner's call, not a routine correction. It is recorded in
# `tests/ui/test_ux_brand_colors.py` so it cannot quietly drop out of sight.

HUB_BRAND_DESIGN: Final[str] = "#8b5cf6"
HUB_BRAND_INDEX: Final[str] = "#3b82f6"
HUB_BRAND_METAL: Final[str] = "#64748b"
HUB_BRAND_STRAT: Final[str] = "#10b981"

# Step 3.9 - four modules had no identity of their own.
#
# RE wore STRAT's emerald and FIELD wore DESIGN's violet, so the tile could not tell them
# apart. SUBSTRATE INDEX wore INDEX's blue although it is a `support_tool`, not part of
# the core workflow.
#
# SMOOTHER was the worst case: it was painted with the SEMANTIC success token, and the
# constant that carried it was named after it. Painting a launcher with the colour that
# means "operation succeeded" is not merely inconsistent - it spends a signal that has to
# stay rare to stay readable.
#
# Hues chosen by measurement: >= 3.4:1 for a white icon, and maximum RGB distance from the
# colours already in use. The closest pair among the eight is STRAT/FIELD at 90.
HUB_BRAND_RE: Final[str] = "#d66b1f"
HUB_BRAND_FIELD: Final[str] = "#1995ae"
HUB_BRAND_SMOOTHER: Final[str] = "#e548b1"
HUB_BRAND_SUBSTRATE: Final[str] = "#469e1a"

# NOT split, and that is deliberate: INDEX / INDEX SPLINE and METAL SINGLE / METAL BILAYER
# are sibling tools on the same subject. A shared family colour reads as kinship; forcing
# four different hues on them would destroy information rather than add any.


#: How the frozen hub starts a module. In the frozen suite the hub and every module are the ONE
#: executable, so a module is started as `CERTUS_HUB.exe --run-module CERTUS_DESIGN [file]`
#: (see `certus.core.certus_frozen_entry`); from the sources it is `python CERTUS_DESIGN.py`.
RUN_MODULE_FLAG: Final[str] = "--run-module"


class HubAppCatalogItem(TypedDict, total=False):
    """Declarative metadata for one HUB launcher card."""

    title: str
    sub: str
    desc: str
    #: One sentence on what the operator does in the module: the tile writes it under the name.
    task: str
    script: str
    icon: str
    color: str
    badge: str
    type: str
    category: str
    contract: str
    sub_apps: list[dict[str, str]]


HUB_APP_CATALOG: tuple[HubAppCatalogItem, ...] = (
    {
        "title": "DESIGN",
        "sub": "Synthesis",
        "desc": "Stochastic Global Optimization. PGLOBAL algorithm with Single-Linkage Clustering.",
        "task": "Design a multilayer optical filter from spectral targets.",
        "script": "CERTUS_DESIGN.py",
        "icon": "🧩",
        "color": HUB_BRAND_DESIGN,
        "badge": "Concept",
        "type": "single",
        "category": "core_workflow",
        "contract": "scientific_workflow",
    },
    {
        "title": "RE",
        "sub": "Reverse Engineering",
        "desc": "Extraction of refractive indices from experimental curves using spline networks.",
        "task": "Reverse-engineer a deposited filter from its measured spectrum.",
        "script": "CERTUS_RE.py",
        "icon": "🕵️",
        "color": HUB_BRAND_RE,
        "badge": "Analysis",
        "type": "single",
        "category": "core_workflow",
        "contract": "scientific_workflow",
    },
    {
        "title": "STRAT",
        "sub": "Manufacturing",
        "desc": "Predictive Monitoring Strategy. Error self-compensation analysis.",
        "task": "Choose the monitoring wavelength of each layer and test the strategy.",
        "script": "CERTUS_STRAT.py",
        "icon": "🏭",
        "color": HUB_BRAND_STRAT,
        "badge": "Production",
        "type": "single",
        "category": "core_workflow",
        "contract": "scientific_workflow",
    },
    {
        "title": "INDEX",
        "sub": "Dielectrics",
        "desc": "Advanced Tauc-Lorentz Characterization. Kramers-Kronig consistent extraction.",
        "task": "Extract the refractive index of a film from a measured spectrum.",
        "script": "CERTUS_INDEX.py",
        "icon": "🧪",
        "color": HUB_BRAND_INDEX,
        "badge": "Material",
        "type": "single",
        "category": "core_workflow",
        "contract": "scientific_workflow",
    },
    {
        "title": "INDEX SPLINE",
        "sub": "Spline Model",
        "desc": "Non-parametric n,k extraction using PWL splines. Ideal for complex IR absorption.",
        "task": "Extract n and k of a film from a spectrum, without a dispersion model.",
        "script": "CERTUS_INDEX_SPLINE.py",
        "icon": "〰️",
        "color": HUB_BRAND_INDEX,
        "badge": "Material",
        "type": "single",
        "category": "core_workflow",
        "contract": "scientific_workflow",
    },
    {
        "title": "FIELD",
        "sub": "Field & LIDT",
        "desc": "Electric field profile computation and active minimax LIDT optimization.",
        "task": "Compute the electric field in a stack and optimize it for damage threshold.",
        "script": "CERTUS_FIELD.py",
        "icon": "⚡",
        "color": HUB_BRAND_FIELD,
        "badge": "LIDT",
        "type": "single",
        "category": "core_workflow",
        "contract": "scientific_workflow",
    },
    {
        "title": "SMOOTHER",
        "sub": "Processing",
        "desc": "Parametric smoothing of spectral measurement data.",
        "task": "Smooth noisy spectral curves before using them.",
        "script": "certus_curve_smoother.py",
        "icon": "🫧",
        "color": HUB_BRAND_SMOOTHER,
        "badge": "Utility",
        "type": "single",
        "category": "support_tool",
        "contract": "utility_tool",
    },
    {
        "title": "SUBSTRATE INDEX",
        "sub": "Characterization",
        "desc": "Substrate refractive index determination from spectral measurements.",
        "task": "Find the refractive index of a substrate from bare-substrate spectra.",
        "script": "certus_substrate_index.py",
        "icon": "📏",
        "color": HUB_BRAND_SUBSTRATE,
        "badge": "Utility",
        "type": "single",
        "category": "support_tool",
        "contract": "substrate_utility",
    },
    {
        "title": "METAL BILAYER",
        "sub": "Opaque Substrate",
        "desc": "Opaque substrate strategy (Legacy).",
        "task": "Characterize a metal film on an opaque substrate.",
        "script": "CERTUS_METAL_BILAYER.py",
        "icon": "🛡️",
        "color": HUB_BRAND_METAL,
        "badge": "Std",
        "type": "single",
        "category": "materials_specialized",
        "contract": "material_workflow",
    },
    {
        "title": "METAL SINGLE",
        "sub": "Transparent Substrate",
        "desc": "Transparent substrate strategy (R/T/Rb).",
        "task": "Characterize a metal film on a transparent substrate (R, T, Rb).",
        "script": "CERTUS_METAL_SINGLE.py",
        "icon": "🛡️",
        "color": HUB_BRAND_METAL,
        "badge": "New",
        "type": "single",
        "category": "materials_specialized",
        "contract": "material_workflow",
    },
)


_METAL_PAIR: Final[tuple[str, ...]] = ("CERTUS_METAL_SINGLE.py", "CERTUS_METAL_BILAYER.py")

#: What a JSON configuration says about the module that wrote it, by the keys it holds: (scripts, keys that must all
#: be there, keys of which one must be there). The name of a file is a hint that anyone can change; what it holds is
#: what the module will read. The two METAL modules write the same keys: the content cannot tell them apart.
_CONFIG_SIGNATURES: Final[tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...]] = (
    (("CERTUS_DESIGN.py",), ("front", "targets"), ()),
    (("CERTUS_STRAT.py",), (), ("stack_multipliers", "h_type_custom")),
    (("CERTUS_STRAT.py",), ("strategy_id", "blocks"), ()),
    (("CERTUS_FIELD.py",), ("emp_factors", "lcalc"), ()),
    (_METAL_PAIR, ("physical_params", "material_params"), ()),
    (("CERTUS_INDEX_SPLINE.py",), (), ("knot_mode", "knot_count", "use_spline_interp", "optimize_n", "optimize_k")),
    (("CERTUS_INDEX.py",), ("thickness_min", "thickness_max"), ()),
    (("CERTUS_RE.py",), (), ("re_gui", "re_workbook_path", "workbook_path")),
)

#: The words of a file name that name a module, in the order they are tried ("bilayer" before "metal").
_NAME_TOKENS: Final[tuple[tuple[str, str], ...]] = (
    ("bilayer", "CERTUS_METAL_BILAYER.py"),
    ("single", "CERTUS_METAL_SINGLE.py"),
    ("strat", "CERTUS_STRAT.py"),
    ("field", "CERTUS_FIELD.py"),
    ("spline", "CERTUS_INDEX_SPLINE.py"),
    ("metal", "CERTUS_METAL_SINGLE.py"),
    ("index", "CERTUS_INDEX.py"),
)


def script_for_name(name: str) -> str | None:
    """The module that the name of a file refers to, or None. "RE" counts only as a word of its own."""
    lowered = name.lower()
    for token, script in _NAME_TOKENS:
        if token in lowered:
            return script
    return "CERTUS_RE.py" if re.search("(?<![a-z])re(?![a-z])", lowered) else None


def scripts_for_config(data: Mapping[str, object]) -> tuple[str, ...]:
    """Every module whose configuration looks like ``data``: none, one, or several when the content cannot tell."""
    found: list[str] = []
    for scripts, needs_all, needs_one in _CONFIG_SIGNATURES:
        if all(key in data for key in needs_all) and (not needs_one or any(key in data for key in needs_one)):
            found += [script for script in scripts if script not in found]
    return tuple(found)


def hub_grid_columns(n_modules: int, max_cols: int = 5) -> int:
    """Return the column count for the HUB launcher grid.

    The count used to be hard-coded at three, for a catalogue of nine. The
    catalogue holds ten, so the tenth module sat alone on a fourth row. The
    rule applied here is that no row may hold a single tile while the others
    are full, and it is derived from the catalogue so that adding a module
    cannot reopen the defect.
    """
    if n_modules <= 1:
        return 1
    if n_modules <= max_cols:
        return n_modules
    fits = [c for c in range(max_cols, 1, -1) if n_modules % c != 1]
    return max(fits) if fits else max_cols
