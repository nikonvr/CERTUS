from typing import Final, TypedDict

HUB_BRAND_DESIGN: Final[str] = "#8b5cf6"
HUB_BRAND_INDEX: Final[str] = "#3b82f6"
HUB_BRAND_METAL: Final[str] = "#64748b"
HUB_BRAND_STRAT: Final[str] = "#10b981"
HUB_SUCCESS: Final[str] = "#15803d"


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
        "color": HUB_BRAND_STRAT,
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
        "color": HUB_BRAND_DESIGN,
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
        "color": HUB_SUCCESS,
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
        "color": HUB_BRAND_INDEX,
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
