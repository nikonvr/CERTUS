"""Combine the predeclared top twelve fully scored moves of each internal window."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "reports/STRAT_Rate_window_widths_2026-10-14"
    output = root / "reports/STRAT_Rate_window_pairs_2026-10-14"
    confirmation = root / "reports/STRAT_Rate_validation_window_widths_2026-10-14"
    policy = json.loads((output / "selection_policy.json").read_text(encoding="utf-8"))
    manifest = json.loads((source / "proposals.json").read_text(encoding="utf-8"))
    state = json.loads((source / "etat.json").read_text(encoding="utf-8"))
    confirmed = json.loads((confirmation / "etat.json").read_text(encoding="utf-8"))
    if state["status"] != "complete" or confirmed["status"] != "complete" or len(confirmed["runs"]) != 4:
        raise ValueError("Source search and confirmation must be complete")
    if state.get("current_pid") or confirmed.get("current_pid") or (source / ".running").exists():
        raise ValueError("Source measurement has not released its checkpoint")
    if digest(source / "proposals.json") != policy["source_proposals_sha256"]:
        raise ValueError("Predeclared source proposals changed")
    if digest(output / "protocole_validation_window_pairs_v9.json") != policy["protocol_sha256"]:
        raise ValueError("Predeclared fresh groups changed")
    rows = [r for run in state["runs"] for r in run.get("results", [])]
    if len(state["runs"]) != state["n_stages"] or len(rows) != manifest["n_proposals"]:
        raise ValueError("One-window search is incomplete")
    offered = {p["source_strategy_id"]: p for p in manifest["proposals"]}
    if len(offered) != len(rows) or {r["id"] for r in rows} != set(offered):
        raise ValueError("Source identities are inconsistent")
    parent = manifest["parent"]
    selected = {}
    for block_index in (1, 3):
        candidates = sorted((r for r in rows if r["eligible"] and r["move"]["block_index"] == block_index),
                            key=lambda r: (r["score"], r["id"]))
        selected[block_index] = candidates[:12]
        if len(selected[block_index]) != 12:
            raise ValueError("Fewer than twelve eligible proposals for an internal window")
        for item in selected[block_index]:
            artifact_path = Path(item["artifact"])
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            row = next(r for r in artifact["final_results"]["all_strategies_results"] if r["strategy"]["strategy_id"] == item["id"])
            meta = row.get("robustness_consensus_meta") or {}
            if artifact["verdict"] != "OK" or row["robustness_score"] != item["score"] or meta.get("seeds") != [41, 42, 43] or meta.get("n_samples") != 3:
                raise ValueError("Selected source has no complete verified consensus")
            for field in ("blocks", "rate_layers", "monochromator_resolution_nm", "witness_reset_layers"):
                if offered[item["id"]].get(field) != row["strategy"].get(field):
                    raise ValueError(f"Source metadata changed: {field}")
            item["source_artifact_sha256"] = digest(artifact_path)
    proposals = []
    seen = set()
    for left in selected[1]:
        for right in selected[3]:
            blocks = copy.deepcopy(parent["blocks"])
            rate = set(parent["rate_layers"])
            for block_index, item in ((1, left), (3, right)):
                candidate = offered[item["id"]]
                block = parent["blocks"][block_index]
                interval = set(range(block["start"], block["end"]))
                rate = (rate - interval) | (set(candidate["rate_layers"]) & interval)
                blocks[block_index] = copy.deepcopy(candidate["blocks"][block_index])
            signature = (tuple((b["start"], b["end"], b["wavelength"]) for b in blocks), tuple(sorted(rate)))
            if signature in seen:
                continue
            seen.add(signature)
            plan = {"nom": f"pair_{left['id']}_{right['id']}", "source_strategy_id": 9_920_000 + len(proposals),
                    "blocks": blocks, "rate_layers": sorted(rate),
                    "monochromator_resolution_nm": parent["monochromator_resolution_nm"],
                    "move": {"kind": "paired_internal_windows", "parent_id": parent["source_strategy_id"],
                             "component_ids": [left["id"], right["id"]], "component_moves": [left["move"], right["move"]],
                             "component_scores": [left["score"], right["score"]]}}
            if "witness_reset_layers" in parent:
                plan["witness_reset_layers"] = copy.deepcopy(parent["witness_reset_layers"])
            proposals.append(plan)
    fixed = json.loads((confirmation / "plans.json").read_text(encoding="utf-8"))["plans"]
    reference = next(p for p in fixed if p["source_strategy_id"] == 900951015)
    incumbent = next(p for p in fixed if p["source_strategy_id"] == 9900006)
    result = {"prepared_utc": datetime.now(UTC).isoformat(), "parent": parent, "anchors": [reference, incumbent],
              "search_seed": 101, "consensus_seeds": [41, 42, 43], "n_proposals": len(proposals),
              "families": {"paired_internal_windows": len(proposals)}, "proposals": proposals,
              "selected_components": selected, "source_proposals": [offered[r["id"]] for group in selected.values() for r in group],
              "selection_policy_sha256": digest(output / "selection_policy.json"), "source_state_sha256": digest(source / "etat.json"),
              "source_proposals_sha256": digest(source / "proposals.json"), "confirmation_state_sha256": digest(confirmation / "etat.json"),
              "scope": "Predeclared top12 Cartesian product, selected on search101 only; prefix600 and partition fixed; no holdout ranking"}
    with (output / "proposals.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"n_proposals": len(proposals), "selected_ids": {k: [r["id"] for r in v] for k, v in selected.items()}}))


if __name__ == "__main__":
    main()
