"""Write the LOCAL_SEARCH winner of a probe artifact as a plan file for index_share_bm90.py.

python reports/BONNE_MERE_strat_90c_2026-10-23/extract_winner.py ARTIFACT.json OUT.json
(OUT.json in %TEMP%/bm90, where index_share_bm90.py reads its plans)
"""

import json
import sys

src, out = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as fh:
    data = json.load(fh)
winners = [s for s in data["strategies"] if s.get("origine") == "LOCAL_SEARCH"]
if len(winners) != 1:
    raise SystemExit(f"expected one LOCAL_SEARCH winner, found {len(winners)}")
w = winners[0]
plan = {
    "strategy_id": w["id"],
    "origin": w["origine"],
    "blocks": w["blocs"],
    "rate_layers": w["rate_layers"],
    "monochromator_resolution_nm": w["resolution_nm"],
    "witness_reset_layers": w["witness_reset_layers"] or [],
}
with open(out, "w", encoding="utf-8") as fh:
    json.dump(plan, fh, indent=1)
print("winner", w["id"], "rate", len(w["rate_layers"]), "blocks", len(w["blocs"]), "origin", w["origine"])
