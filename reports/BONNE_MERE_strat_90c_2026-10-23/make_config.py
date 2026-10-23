"""STRAT configuration of the retained 90-layer Bonne Mere design (fused silica), indices at +-0.01.

Base: example/example_strat/JSON-strat-example-deep.json, with the search budgets and spectral settings of the
Bonne Mere study (studies/bonne_mere/dossier_final/donnees/parametres_STRAT_effectifs.json), the substrate of the
design, index_corridor 0.010, monitoring 430-900 nm, slit fixed at 2 nm (owner, 2026-10-23). Multipliers are QWOT at l0 with STRAT's own n(l0).
"""

import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from certus.utils.certus_strat_db import RobustMaterialDatabase  # noqa: E402
from certus.utils.certus_strat_service import _PhysicsBridge  # noqa: E402
from CERTUS_STRAT import _resolve_strat_indices_db_path  # noqa: E402

design = json.loads((REPO / "reports/BONNE_MERE_design_2026-10-23/best_design_needle_swap_90_nominal.json").read_text(encoding="utf-8"))
bm = json.loads((REPO / "studies/bonne_mere/dossier_final/donnees/parametres_STRAT_effectifs.json").read_text(encoding="utf-8"))
cfg = json.loads((REPO / "example/example_strat/JSON-strat-example-deep.json").read_text(encoding="utf-8"))
for key in ["wl_step", "scan_wl_min", "scan_wl_max", "sim_thickness_probe_offset_ratio", "mining_candidates_limit", "n_screen_runs",
            "k_keep_survivors", "top_k_parents", "max_fusions_per_parent", "consensus_num_runs", "consensus_seed_list"]:
    cfg[key] = bm[key]
l0 = float(cfg["l0"])
db = RobustMaterialDatabase(_resolve_strat_indices_db_path())
n = {s: float(_PhysicsBridge.get_refractive_index(name, l0, db_instance=db).real) for s, name in ((0, cfg["h_material_file"]), (1, cfg["l_material_file"]))}
sym = design["material_indices"]
assert sym[0] == 0, "STRAT starts with H"
assert all(a != b for a, b in itertools.pairwise(sym)), "STRAT alternates H and L"
cfg["stack_multipliers"] = [d * 4.0 * n[s] / l0 for d, s in zip(design["thickness_nm"], sym, strict=True)]
cfg.update({"substrate_choice": "SiO2", "wl_range_start": 400.0, "wl_range_end": bm["wl_range"][1], "index_corridor": 0.010,
            "allow_rate": 1, "scan_wl_min": 430.0, "scan_wl_max": 900.0, "monochromator_resolution_nm": 2.0,
            "search_resolution": 0, "show_plots": False, "export_excel": False})
out = HERE / "config_strat_90c_corridor0.010.json"
out.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
print(f"n({l0}) H {n[0]:.5f} L {n[1]:.5f}; {len(sym)} layers; written {out.name}")
