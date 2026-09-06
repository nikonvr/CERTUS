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


class HubAppCatalogItem(TypedDict, total=False):
    """Declarative metadata for one HUB launcher card."""

    title: str
    sub: str
    desc: str
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
        "desc": "Extraction of refractive clues from experimental curves using spline networks.",
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
        "script": "CERTUS_METAL_SINGLE.py",
        "icon": "🛡️",
        "color": HUB_BRAND_METAL,
        "badge": "New",
        "type": "single",
        "category": "materials_specialized",
        "contract": "material_workflow",
    },
)
