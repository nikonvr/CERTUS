"""Freeze sequential paired-window orchestration, keeping the physical replay unchanged."""

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
    output = root / "reports/STRAT_Rate_window_pairs_2026-10-14"
    confirm = root / "reports/STRAT_Rate_validation_window_pairs_2026-10-14"
    confirm.mkdir(exist_ok=False)
    old_replay = scratch / "rate_fixed_replay_confirmation_v8.py"
    new_replay = scratch / "rate_fixed_replay_confirmation_v9.py"
    old = old_replay.read_text(encoding="utf-8")
    new = old.replace('"holdout_2323", "search"', '"holdout_2323", "holdout_2424", "holdout_2525", "holdout_2626", "search"')
    if new == old:
        raise ValueError("CLI extension did not apply")
    with new_replay.open("x", encoding="utf-8") as stream:
        stream.write(new)
    old_ast, new_ast = ast.parse(old), ast.parse(new)
    for tree in (old_ast, new_ast):
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "choices":
                node.value = ast.Constant(None)
    if ast.dump(old_ast) != ast.dump(new_ast):
        raise ValueError("Physical replay changed outside CLI choices")
    runner = scratch / "rate_pair_runner.py"
    text = (scratch / "rate_window_runner.py").read_text(encoding="utf-8")
    text = text.replace("verify_rate_window_trials.py", "verify_rate_window_pairs.py")
    text = text.replace("Native pool confirmation", "One-window confirmation").replace("window measurement", "paired-window measurement")
    start = text.index('        lines = [')
    end = text.index('        helper["save_text"]', start)
    text = text[:start] + '''        lines = ["# Rate : couples de fenêtres internes (2026-10-14)", "",
                 f"État : {state['status']} ; {len(state['runs'])}/{len(stages)} étapes ; {scored}/{proposals['n_proposals']} couples.",
                 "Graine 101, consensus 41/42/43, profondeur 300 ; deux ancres strictes dans chaque groupe.",
                 "16 processeurs, affinité 0xffff, Normal, 15 threads ; une seule mesure."]
        best = state.get("best")
        if best:
            lines += [f"Meilleur provisoire : {2*math.sqrt(best['score']):.10f} nm ; gain {100*(1-math.sqrt(best['score']/baseline)):.4f} % contre référence.",
                      f"Plan {best['id']}, mouvement {best['move']}, artefact {best['artifact']}."]
        lines += ["", "Confirmation indépendante requise pour tout gain ; aucun défaut activé ni commit.",
                  "Les durées incluent le cache et ne prouvent pas une accélération du code."]
        if state.get("error"):
            lines += ["", f"Échec conservé : {state['error']}."]
''' + text[end:]
    with runner.open("x", encoding="utf-8") as stream:
        stream.write(text)
    confirmation_runner = scratch / "rate_pair_confirmation_runner.py"
    text = (scratch / "rate_window_confirmation_runner.py").read_text(encoding="utf-8")
    text = text.replace("rate_fixed_replay_confirmation_v8.py", "rate_fixed_replay_confirmation_v9.py")
    text = text.replace('"holdout_2121", "holdout_2222", "holdout_2323"', '"holdout_2424", "holdout_2525", "holdout_2626"')
    text = text.replace("internal_window_consensus_best_s101", "paired_windows_consensus_best_s101").replace("9_900_006", "9_900_007")
    text = text.replace("native prefix", "paired-window")
    with confirmation_runner.open("x", encoding="utf-8") as stream:
        stream.write(text)
    prior = json.loads((root / "reports/STRAT_Rate_window_widths_2026-10-14/prepared.json").read_text(encoding="utf-8"))
    args = prior["arguments"][:]
    args[args.index("--proposals") + 1] = str(output / "proposals.json")
    args[args.index("--protocol") + 1] = str(output / "protocole_validation_window_pairs_v9.json")
    args[args.index("--trial-output") + 1] = str(root / "reports/STRAT_Rate_validation_window_widths_2026-10-14")
    args[args.index("--output") + 1] = str(output)
    fixed = root / "reports/STRAT_Rate_validation_window_widths_2026-10-14/plans.json"
    (confirm / "baseline_plans_snapshot.json").write_bytes(fixed.read_bytes())
    for folder, active, arguments in ((output, runner, args), (confirm, confirmation_runner,
            ["--worktree", prior["arguments"][1], "--pool-output", str(output), "--output", str(confirm),
             "--reference-state", args[args.index("--reference-state") + 1], "--protocol", str(output / "protocole_validation_window_pairs_v9.json"),
             "--fixed-plans", str(confirm / "baseline_plans_snapshot.json")])):
        sources = [runner, confirmation_runner, new_replay, scratch / "prepare_rate_window_pairs.py", scratch / "verify_rate_window_pairs.py",
                   scratch / "prepare_rate_pair_orchestration.py", scratch / "rate_fixed_replay.py", scratch / "campagne_a2_runner.py"]
        for source in sources:
            (folder / source.name).write_bytes(source.read_bytes())
        hashes = {p.name: digest(p) for p in sources}
        hashes.update({"proposals.json": digest(output / "proposals.json"), "protocol": digest(output / "protocole_validation_window_pairs_v9.json"),
                       "selection_policy": digest(output / "selection_policy.json")})
        with (folder / "prepared.json").open("x", encoding="utf-8") as stream:
            json.dump({"prepared_utc": datetime.now(UTC).isoformat(), "runner": str(active), "arguments": arguments, "hashes": hashes,
                       "physical_replay_ast_identical_except_cli_choices": True, "n_proposals": 144,
                       "status": "prepared_not_launched", "fresh_groups": [2424, 2525, 2626],
                       "review": "Existing sequential controller/checkpoint/fixed-point logic reused; all pair contracts verified before scoring; no default or physics change",
                       "deadline_utc": "2026-10-14T07:00:00Z"}, stream, indent=2)
    print("PAIR_ORCHESTRATION_PREPARED=GO")


if __name__ == "__main__":
    main()
