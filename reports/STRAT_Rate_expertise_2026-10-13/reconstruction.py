"""Read saved runs and reconstruct move orders without importing the physics runtime."""

from __future__ import annotations

import ast
import collections
import copy
import itertools
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "reports/STRAT_Rate_equilibre_AB_2026-10-13"


def load_functions() -> dict[str, Any]:
    namespace: dict[str, Any] = {"Any": Any, "itertools": itertools, "copy": copy, "np": np}
    selections = {
        "certus/core/certus_strat_robustness_rate.py": {
            "RATE_MIN_LAYER", "ELITE_RATE_WINDOWS", "ELITE_RATE_STEP", "ELITE_RATE_FILL_MAX",
            "_rate_runs", "_elite_rate_moves", "_balanced_elite_rate_moves", "_elite_rate_candidates",
        },
        "certus/utils/certus_strat_context.py": {"_blocks_signature", "_plan_signature", "_validate_strategy_blocks_contract"},
        "certus/core/certus_strat_consensus.py": {"_INHERITED_KEYS", "_inherited_by_children", "_elite_moves", "_generate_elite_candidate_strategies"},
        "certus/core/certus_strat_ranking.py": {"_existing_block_signatures"},
        "scripts/resumer_artefact_sonde.py": {"seel"},
    }
    import math
    namespace["math"] = math
    for filename, names in selections.items():
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
        nodes = [node for node in tree.body if getattr(node, "name", None) in names or
                 (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in names) or
                 (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names for target in node.targets))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), namespace)
    return namespace


def parent_groups(log: str) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    block_count = None
    for line in log.splitlines():
        mining = re.search(r"Mining: n_blocks=(\d+)", line)
        if mining:
            block_count = int(mining[1])
        parent = re.search(r"\[ELITE-PARENTS\] Round (\d+) #(\d+) id=(\d+)", line)
        if parent:
            if int(parent[2]) == 1:
                current = {"blocks": block_count, "round": int(parent[1]), "time": line[:8], "ids": []}
                groups.append(current)
            if current is None:
                raise ValueError("Missing first parent")
            current["ids"].append(int(parent[3]))
    return groups


def family(parent: dict[str, Any], layers: list[int]) -> str:
    current, child = set(parent["rate_layers"]), set(layers)
    removed, added = current - child, child - current
    if removed:
        return "edge" if len(removed) == 1 else f"open{len(removed)}"
    if min(added) - 1 in current and max(added) + 1 in current:
        return "fill"
    return "edge" if len(added) == 1 else f"insert{len(added)}"


def main() -> None:
    functions = load_functions()
    signature = functions["_plan_signature"]
    design = json.loads((ROOT / "example/example_strat/JSON-strat-random75.json").read_text(encoding="utf-8"))
    step = float(design["scan_wl_step"])
    wavelengths = np.arange(float(design["scan_wl_min"]), float(design["scan_wl_max"]) + step / 2, step).tolist()
    result: dict[str, Any] = {"scope": "structural order with logged parents; no physics replay; exact round-1 generator reconstructed with all 229 pre-ELITE saved plans", "groups": []}
    reference = json.loads((FOLDER / "blocs_vs_plantage_r75x0.5_deep_s101_rate_equilibre_off.json").read_text(encoding="utf-8"))
    reference_strategies = {s["id"]: s for s in reference["strategies"]}
    for variant, tag in (("actuel", "off"), ("equilibre", "on")):
        artifact = json.loads((FOLDER / f"blocs_vs_plantage_r75x0.5_deep_s101_rate_equilibre_{tag}.json").read_text(encoding="utf-8"))
        strategies = {s["id"]: s for s in artifact["strategies"]}
        groups = parent_groups((FOLDER / f"{variant}.log").read_text(encoding="utf-8"))
        for group in groups:
            if group["blocks"] != 9 or any(sid not in strategies for sid in group["ids"]):
                continue
            parents = [{"strategy": {**strategies[sid], "strategy_id": sid, "blocks": strategies[sid]["blocs"]}} for sid in group["ids"]]
            entry = {"variant": variant, **group, "orders": {}}
            for balanced in (False, True):
                ordered = functions["_elite_rate_candidates"](parents, 75, balanced=balanced)
                seen = {signature(p["strategy"]["blocks"], p["strategy"]["rate_layers"]) for p in parents}
                unique = []
                for sid, parent, blocks, layers in ordered:
                    sig = signature(blocks, layers)
                    if sig in seen:
                        continue
                    seen.add(sig)
                    unique.append((sid, parent, blocks, layers))
                targets = {}
                for sid in (900950560, 900951015):
                    target = reference_strategies.get(sid)
                    if target:
                        target_sig = signature(target["blocs"], target["rate_layers"])
                        matches = [(rank, parent_sid) for rank, (parent_sid, _, blocks, layers) in enumerate(unique, 1) if signature(blocks, layers) == target_sig]
                        targets[str(sid)] = matches
                counts = {str(cap): dict(collections.Counter(family(parent, layers) for _, parent, _, layers in unique[:cap])) for cap in (120, 240)}
                entry["orders"]["balanced" if balanced else "legacy"] = {"pool": len(unique), "counts": counts, "target_positions": targets}
            result["groups"].append(entry)
            if group["round"] == 1 and len(parents) == 10:
                existing = [{"strategy": {**s, "blocks": s["blocs"]}} for s in artifact["strategies"] if s["n_blocs"] == 9 and s["origine"] != "ELITE"]
                if len(existing) != 229:
                    raise ValueError(f"Expected 229 initial plans, got {len(existing)}")
                signatures = functions["_existing_block_signatures"](existing)
                exact = {}
                for balanced in (False, True):
                    for cap in (120, 240, 360):
                        children, _ = functions["_generate_elite_candidate_strategies"](
                            parents, wavelengths, 75, 900950321, max_candidates=120,
                            existing_signatures=signatures, rate_moves=True, max_rate_candidates=cap,
                            balanced_rate_moves=balanced,
                        )
                        rate_children = [c for c in children if c["origin_details"].startswith("ELITE_RATE")]
                        target_sig = signature(reference_strategies[900950560]["blocs"], reference_strategies[900950560]["rate_layers"])
                        matches = [{"id": c["strategy_id"], "parent": c["parent_strategy_id"]} for c in rate_children if signature(c["blocks"], c["rate_layers"]) == target_sig]
                        exact[f"{'balanced' if balanced else 'legacy'}_{cap}"] = {
                            "generated": len(children), "rate": len(rate_children), "seed_900950560": matches,
                            "families": dict(collections.Counter(family(strategies[c["parent_strategy_id"]], c["rate_layers"]) for c in rate_children)),
                        }
                entry["exact_round1"] = exact
    out = ROOT / "reports/STRAT_Rate_expertise_2026-10-13"
    out.mkdir(exist_ok=True)
    (out / "selection_structurelle.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for group in result["groups"]:
        print(json.dumps(group, ensure_ascii=False))


if __name__ == "__main__":
    main()
