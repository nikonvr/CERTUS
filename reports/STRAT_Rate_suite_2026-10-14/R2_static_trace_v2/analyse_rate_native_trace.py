"""Read saved native traces without importing CERTUS or running a simulation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def signature(plan: dict) -> tuple:
    blocks = plan.get("blocks", plan.get("blocs", []))
    return (tuple((int(b["start"]), int(b["end"]), float(b["wavelength"])) for b in blocks),
            tuple(sorted(int(i) for i in plan.get("rate_layers", []))))


def optical_segments(plan: dict, num_layers: int) -> list[tuple]:
    rate = set(plan.get("rate_layers", []))
    segments = []
    for block in plan.get("blocks", []):
        start = None
        for layer in range(int(block["start"]), min(int(block["end"]), num_layers)):
            if layer not in rate:
                if start is None:
                    start = layer
            elif start is not None:
                segments.append((start, layer, float(block["wavelength"])))
                start = None
        if start is not None:
            segments.append((start, min(int(block["end"]), num_layers), float(block["wavelength"])))
    return segments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.relative_to(root / "reports")
    output.mkdir(parents=True, exist_ok=True)
    plans_path = root / "reports/STRAT_Rate_validation_prefix_after_window_extended_2026-10-14/plans.json"
    plans = json.loads(plans_path.read_text(encoding="utf-8"))["plans"]
    targets = {str(p["source_strategy_id"]): signature(p) for p in plans}
    sources = {str(plans_path.relative_to(root)): hashlib.sha256(plans_path.read_bytes()).hexdigest()}
    records = []
    for name in ("STRAT_Rate_native_joint_rate240_round6_2026-10-13", "STRAT_Rate_native_prefix_2026-10-14"):
        folder = root / "reports" / name
        trace_path = next(folder.rglob("generated_candidates.json"))
        artifact_path = next(folder.rglob("blocs_vs_plantage*.json"))
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        for path in (trace_path, artifact_path):
            sources[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows = artifact["strategies"]
        exported_plans = {(str(row["id"]), signature(row)) for row in rows}
        parent_last_call = {str(sid): index for index, call in enumerate(trace["calls"]) for sid in call["parent_ids"]}
        parent_ids = set(parent_last_call)
        all_offers = [c for key in ("calls", "prefix_calls") for call in trace.get(key, []) for c in call.get("offered", [])]
        id_counts = Counter(str(c["strategy_id"]) for c in all_offers)
        families = {}
        for family, key in (("joint", "calls"), ("prefix", "prefix_calls")):
            calls = trace.get(key, [])
            offered = [candidate for call in calls for candidate in call.get("offered", [])]
            counts = Counter()
            target_hits = Counter()
            indexed_offers = [(index, c) for index, call in enumerate(calls) for c in call.get("offered", [])]
            for call_index, candidate in indexed_offers:
                sid = str(candidate["strategy_id"])
                counts["id_and_plan_in_final_export"] += (sid, signature(candidate)) in exported_plans
                counts["id_seen_in_later_parent_list"] += parent_last_call.get(sid, -1) > call_index
                segments = optical_segments(candidate, 75)
                counts["has_L35_L37_window"] += any(a == 34 and b == 37 for a, b, _ in segments)
                counts["has_L35_L37_at688"] += (34, 37, 688.0) in segments
                counts["has_L1_L5_at600"] += (0, 5, 600.0) in segments
                counts["has_L1_L5_at613"] += (0, 5, 613.0) in segments
                counts["any_block_at613"] += any(float(b["wavelength"]) == 613 for b in candidate["blocks"])
                candidate_signature = signature(candidate)
                for sid_target, target in targets.items():
                    target_hits[sid_target] += candidate_signature == target
            families[family] = {"generator_calls": len(calls), "offered": len(offered),
                                "counts": dict(counts), "exact_structural_target_hits": dict(target_hits)}
        eligible = [r for r in rows if not r.get("crash_eliminated") and r.get("crash_rate", 1) <= 0.05]
        best = min(eligible, key=lambda row: row["score"])
        records.append({"experiment": name, "families": families, "exported_rows": len(rows),
                        "offer_ids_reused_across_calls": sum(n > 1 for n in id_counts.values()),
                        "exported_consensus_metadata_rows": sum("robustness_consensus_meta" in r for r in rows),
                        "raw_export_winner": best["id"], "raw_winner_seen_as_parent": str(best["id"]) in parent_ids})
    report = {"status": "static_analysis_only", "updated_utc": datetime.now(UTC).isoformat(),
              "records": records, "source_sha256": sources,
              "limitations": ["Only the additional joint/prefix candidates are saved in these traces; legacy candidates are not exhaustively traced.",
                              "Presence in the final export does not prove full or complete consensus evaluation; matching uses both id and structural plan.",
                              "Parent traces carry ids, not full parent plans; a later matching id is only an observed identifier link.",
                              "Native available_wls, per-stage scores and rejection gates are not recorded; absence alone does not identify its cause.",
                              "Exact target matching includes partition and all block wavelengths; auxiliary window matching is not a claim of physical equivalence.",
                              "Raw export winners may mix base and consensus; retain previously homogeneous pool rescoring."]}
    with (output / "static_trace_analysis.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    with (output / Path(__file__).name).open("xb") as stream:
        stream.write(Path(__file__).read_bytes())
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
