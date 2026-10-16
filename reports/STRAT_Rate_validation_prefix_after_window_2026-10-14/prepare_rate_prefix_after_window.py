"""Freeze the next coordinate search and fresh validation groups before any scoring."""

from __future__ import annotations

import ast
import hashlib
import json
import runpy
from datetime import UTC, datetime
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    scratch = root / "scratch"
    output = root / "reports/STRAT_Rate_prefix_after_window_2026-10-14"
    confirmation = root / "reports/STRAT_Rate_validation_prefix_after_window_2026-10-14"
    prototype = scratch / "prepare_rate_prefix_after_window_proposals.py"
    source = (scratch / "prepare_rate_prefix_trials.py").read_text(encoding="utf-8")
    source = source.replace("STRAT_Rate_prefix_joint_2026-10-14", output.name)
    source = source.replace("STRAT_Rate_validation_ablation_full_2026-10-14", "STRAT_Rate_validation_window_widths_2026-10-14")
    source = source.replace("(9900000, 9900001)", "(9900006,)").replace("(900951015, 9900000)", "(900951015, 9900006)")
    source = source.replace("wavelength - 10, wavelength + 11", "wavelength - 20, wavelength + 21").replace("9_960_000", "9_910_000")
    source = source.replace('"parents": parents,', '"parents": parents, "parent": parents[0],')
    with prototype.open("x", encoding="utf-8") as stream:
        stream.write(source)
    runpy.run_path(str(prototype), run_name="__main__")
    confirmation.mkdir(exist_ok=False)
    previous_protocol = root / "reports/STRAT_Rate_window_pairs_2026-10-14/protocole_validation_window_pairs_v9.json"
    protocol = json.loads(previous_protocol.read_text(encoding="utf-8"))
    protocol["prepared_utc"] = datetime.now(UTC).isoformat()
    protocol["holdouts"] += [{"robustness_seed": seed, "consensus_seed_list": [seed, seed + 1, seed + 2]} for seed in (2727, 2828, 2929)]
    protocol["requirements"].append("2727/2728/2729, 2828/2829/2830 and 2929/2930/2931 declared before prefix-after-window scoring; older groups reused context only")
    protocol_path = output / "protocole_validation_prefix_after_window_v10.json"
    with protocol_path.open("x", encoding="utf-8") as stream:
        json.dump(protocol, stream, indent=2)
    old_replay = (scratch / "rate_fixed_replay_confirmation_v9.py").read_text(encoding="utf-8")
    new_replay = old_replay.replace('"holdout_2626", "search"', '"holdout_2626", "holdout_2727", "holdout_2828", "holdout_2929", "search"')
    replay = scratch / "rate_fixed_replay_confirmation_v10.py"
    with replay.open("x", encoding="utf-8") as stream:
        stream.write(new_replay)
    trees = [ast.parse(old_replay), ast.parse(new_replay)]
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "choices":
                node.value = ast.Constant(None)
    if ast.dump(trees[0]) != ast.dump(trees[1]) or new_replay == old_replay:
        raise ValueError("Physical replay changed outside CLI choices")
    runner = scratch / "rate_prefix_after_window_runner.py"
    source = (scratch / "rate_pair_runner.py").read_text(encoding="utf-8")
    source = source.replace("verify_rate_window_pairs.py", "verify_rate_prefix_after_window.py")
    source = source.replace("couples de fenêtres internes", "préfixe après optimisation de fenêtre").replace("couples.", "propositions.")
    with runner.open("x", encoding="utf-8") as stream:
        stream.write(source)
    confirm_runner = scratch / "rate_prefix_after_window_confirmation_runner.py"
    source = (scratch / "rate_pair_confirmation_runner.py").read_text(encoding="utf-8")
    source = source.replace("rate_fixed_replay_confirmation_v9.py", replay.name)
    source = source.replace('"holdout_2424", "holdout_2525", "holdout_2626"', '"holdout_2727", "holdout_2828", "holdout_2929"')
    source = source.replace("paired_windows_consensus_best_s101", "prefix_after_window_consensus_best_s101").replace("9_900_007", "9_900_008")
    with confirm_runner.open("x", encoding="utf-8") as stream:
        stream.write(source)
    prior = json.loads((root / "reports/STRAT_Rate_window_pairs_2026-10-14/prepared.json").read_text(encoding="utf-8"))
    arguments = prior["arguments"][:]
    for flag, value in (("--proposals", output / "proposals.json"), ("--protocol", protocol_path),
                        ("--trial-output", root / "reports/STRAT_Rate_validation_window_pairs_2026-10-14"), ("--output", output)):
        arguments[arguments.index(flag) + 1] = str(value)
    fixed = root / "reports/STRAT_Rate_validation_window_pairs_2026-10-14/plans.json"
    (confirmation / "baseline_plans_snapshot.json").write_bytes(fixed.read_bytes())
    n = json.loads((output / "proposals.json").read_text(encoding="utf-8"))["n_proposals"]
    sources = [Path(__file__), prototype, scratch / "verify_rate_prefix_after_window.py", runner, confirm_runner, replay,
               scratch / "rate_fixed_replay.py", scratch / "campagne_a2_runner.py"]
    for folder, active, args in ((output, runner, arguments), (confirmation, confirm_runner,
            ["--worktree", prior["arguments"][1], "--pool-output", str(output), "--output", str(confirmation),
             "--reference-state", arguments[arguments.index("--reference-state") + 1], "--protocol", str(protocol_path),
             "--fixed-plans", str(confirmation / "baseline_plans_snapshot.json")])):
        for path in sources:
            (folder / path.name).write_bytes(path.read_bytes())
        hashes = {p.name: digest(p) for p in sources}
        hashes.update({"proposals.json": digest(output / "proposals.json"), "protocol": digest(protocol_path)})
        with (folder / "prepared.json").open("x", encoding="utf-8") as stream:
            json.dump({"prepared_utc": datetime.now(UTC).isoformat(), "runner": str(active), "arguments": args, "hashes": hashes,
                       "n_proposals": n, "n_stages": (n + 9) // 10 + 1, "status": "prepared_not_launched", "fresh_groups": [2727, 2828, 2929],
                       "physical_replay_ast_identical_except_cli_choices": True,
                       "scope": "Retained window688 parent only; prefix lengths2..9, original broad grid and fine +/-20nm; internal windows/partition fixed",
                       "selection": "Parent retained after confirmation; rank only search101 complete consensus; pair winner not adopted because it lost all fresh groups",
                       "deadline_utc": "2026-10-14T07:00:00Z"}, stream, indent=2)
    print("PREFIX_AFTER_WINDOW_PREPARED=GO")


if __name__ == "__main__":
    main()
