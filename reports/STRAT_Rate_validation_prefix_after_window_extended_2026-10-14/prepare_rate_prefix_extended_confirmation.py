"""Freeze six additional fresh groups for the already selected prefix613 fixed plan."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    scratch = root / "scratch"
    initial = root / "reports/STRAT_Rate_validation_prefix_after_window_2026-10-14"
    pool = root / "reports/STRAT_Rate_prefix_after_window_2026-10-14"
    output = root / "reports/STRAT_Rate_validation_prefix_after_window_extended_2026-10-14"
    prior = json.loads((initial / "etat.json").read_text(encoding="utf-8"))
    if prior["status"] != "complete" or len(prior["runs"]) != 4 or prior.get("current_pid"):
        raise ValueError("Initial confirmation is incomplete")
    source_winner = prior["pool_best"]["id"]
    if source_winner != 9910275:
        raise ValueError("Selected prefix613 changed")
    output.mkdir(exist_ok=False)
    seeds = (3030, 3131, 3232, 3333, 3434, 3535)
    previous_protocol = pool / "protocole_validation_prefix_after_window_v10.json"
    protocol = json.loads(previous_protocol.read_text(encoding="utf-8"))
    protocol["prepared_utc"] = datetime.now(UTC).isoformat()
    protocol["holdouts"] += [{"robustness_seed": seed, "consensus_seed_list": [seed, seed + 1, seed + 2]} for seed in seeds]
    protocol["requirements"].append("Six additional fresh groups3030/3131/3232/3333/3434/3535 frozen after selecting prefix613, before their scores; compare fixed plans only, never rerank candidates")
    protocol_path = output / "protocole_validation_prefix_extended_v11.json"
    with protocol_path.open("x", encoding="utf-8") as stream:
        json.dump(protocol, stream, indent=2)
    old = (scratch / "rate_fixed_replay_confirmation_v10.py").read_text(encoding="utf-8")
    new = old.replace('"holdout_2929", "search"', '"holdout_2929", ' + ', '.join(f'"holdout_{s}"' for s in seeds) + ', "search"')
    replay = scratch / "rate_fixed_replay_confirmation_v11.py"
    with replay.open("x", encoding="utf-8") as stream:
        stream.write(new)
    trees = [ast.parse(old), ast.parse(new)]
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "choices":
                node.value = ast.Constant(None)
    if ast.dump(trees[0]) != ast.dump(trees[1]) or old == new:
        raise ValueError("Physical replay changed outside CLI choices")
    runner = scratch / "rate_prefix_after_window_extended_confirmation_runner.py"
    code = (scratch / "rate_prefix_after_window_confirmation_runner.py").read_text(encoding="utf-8")
    code = code.replace("rate_fixed_replay_confirmation_v10.py", replay.name)
    code = code.replace('"control", "holdout_2727", "holdout_2828", "holdout_2929"', '"control", ' + ', '.join(f'"holdout_{s}"' for s in seeds))
    code = code.replace("9_900_008", "9_900_009")
    with runner.open("x", encoding="utf-8") as stream:
        stream.write(code)
    baseline = output / "baseline_plans_snapshot.json"
    baseline.write_bytes((initial / "plans.json").read_bytes())
    prepared = json.loads((initial / "prepared.json").read_text(encoding="utf-8"))
    arguments = prepared["arguments"][:]
    for flag, value in (("--output", output), ("--protocol", protocol_path), ("--fixed-plans", baseline)):
        arguments[arguments.index(flag) + 1] = str(value)
    sources = [Path(__file__), runner, replay, scratch / "campagne_a2_runner.py"]
    for path in sources:
        (output / path.name).write_bytes(path.read_bytes())
    with (output / "prepared.json").open("x", encoding="utf-8") as stream:
        json.dump({"prepared_utc": datetime.now(UTC).isoformat(), "runner": str(runner), "arguments": arguments,
                   "hashes": {p.name: digest(p) for p in sources}, "protocol_sha256": digest(protocol_path),
                   "fixed_plans_sha256": digest(baseline), "pool_proposals_sha256": digest(pool / "proposals.json"),
                   "fresh_groups": seeds, "selected_source_id": source_winner, "selected_replay_id": 9900008,
                   "selection": "Already selected before fresh measurements; no search/ranking based on these groups",
                   "physical_replay_ast_identical_except_cli_choices": True,
                   "review": "Existing strict confirmation controller reused; equivalent winner deduplicated and fixed point checked",
                   "deadline_utc": "2026-10-14T07:00:00Z"}, stream, indent=2)
    print("PREFIX_EXTENDED_CONFIRMATION_PREPARED=GO")


if __name__ == "__main__":
    main()
