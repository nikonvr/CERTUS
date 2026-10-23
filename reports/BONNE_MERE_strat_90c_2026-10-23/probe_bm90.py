"""Run scripts/probe_blocs_vs_plantage.py on the retained 90-layer Bonne Mere design, registered as component "bm90".

python reports/BONNE_MERE_strat_90c_2026-10-23/probe_bm90.py deep 0 0 2 0 77
(arguments after the component, as for the probe). The result goes to reports/blocs_vs_plantage_bm90_<mode>_s<seed>.json.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))
import probe_blocs_vs_plantage as P  # noqa: E402

P.COMPOSANTS["bm90"] = ("reports/BONNE_MERE_strat_90c_2026-10-23/config_strat_90c_corridor0.010.json", 90)
sys.argv = [sys.argv[0], "bm90", *sys.argv[1:]]
sys.exit(P.main())
