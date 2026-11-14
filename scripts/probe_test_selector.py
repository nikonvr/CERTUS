"""Compare test selection with full-suite outcomes in an isolated managed checkout.

Run --control first, then --cases. Every source edit is restored in finally.
Historical cases reverse only the corrective source patch, retaining today's tests.
Mutants use mutation_pilot's operators while preserving comments and source layout.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

import mutation_pilot as mp
import validate_parallel as validation
import verify_changed as selector

SOURCE_ROOT = Path(__file__).resolve().parents[1]
HISTORY = [
    ("infrared_center", "3865ac09", ["certus/core/certus_index_objectives.py"]),
    ("empty_phase_a", "68f40d27", ["certus/utils/certus_strat_service.py"]),
    ("qwot_signal_state", "5a456ec7", ["certus/ui/certus_base_app_stack_mixin.py", "certus/ui/certus_re_table_mixin.py"]),
]
MUTATIONS = [
    ("angle_boundary", "certus/physics/certus_inputs.py", "if abs(angle) > 90.0:", ">", ">="),
    ("spectral_width", "certus/domain/spectral_weights.py", "w[0] = log_lam[1] - log_lam[0]", "-", "+"),
    ("thickness_units", "certus/domain/optical/value_objects/thickness.py", "return self.nm * 1e-9", "*", "/"),
    ("field_chain", "certus/core/certus_field_gradient.py", "return tuple(gradient[::-1] * scale for gradient in gradients)", "*", "/"),
    ("overflow_boundary", "certus/physics/certus_inputs.py", "if reach[worst] > PHASE_IMAG_OVERFLOW:", ">", ">="),
]


def git(root, *args, input_bytes=None):
    done = subprocess.run(["git", *args], cwd=root, input=input_bytes, capture_output=True, check=False)
    if done.returncode:
        raise RuntimeError(done.stderr.decode("utf-8", "replace"))
    return done.stdout


def save(path, result):
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summary(result):
    return {
        "stage": result.stage.name, "returncode": result.returncode, "seconds": result.seconds,
        "counts": result.counts, "failed": result.failed, "persistent": result.persistent,
        "replayed": result.replayed, "status": result.status,
    }


def full_suite(out, workers, *, stop_on_failure):
    out.mkdir(parents=True, exist_ok=True)
    plan = validation.build_plan(workers, min(workers, 6), workers > 1,
                                 ["oracle", "unit", "ui", "rest", "performance"])
    if stop_on_failure:
        plan = [validation.Stage(s.name, (*s.command, "-x"), s.kind) for s in plan]
    results = []
    for stage in plan:
        result = validation.execute([stage], out)[0]
        results.append(result)
        if stop_on_failure and result.status == "FAIL":
            break
        if result.returncode and not result.failed:
            raise RuntimeError(f"{stage.name} exited without a usable test result; see {result.log}")
    return {
        "green": validation.verdict(results), "stages": [summary(r) for r in results],
        "failed": sorted({test for r in results for test in r.failed if test not in r.replayed}),
    }


def selected_suite(selection, out, workers):
    if selection.full_suite:
        return full_suite(out, workers, stop_on_failure=True)
    out.mkdir(parents=True, exist_ok=True)
    command = [*validation.PYTEST, *sorted(selection.tests), "-x"]
    if not selection.tests:
        return {"green": True, "stages": [], "failed": []}
    if workers > 1:
        command += ["-n", str(workers), "--dist", "loadfile"]
    stage = validation.Stage("selected", tuple(command), "pytest")
    results = validation.execute([stage], out)
    if results[0].returncode and not results[0].failed:
        raise RuntimeError(f"Unusable selected result; see {results[0].log}")
    return {
        "green": validation.verdict(results), "stages": [summary(r) for r in results],
        "failed": [test for test in results[0].failed if test not in results[0].replayed],
    }


def classify(full_suite_reason, selected_files, selected, full):
    """Return (status, escaped); only OK proves that the selection caught a fault the full suite sees.

    UNDETECTED: both suites stay green, so the case proves nothing about the selection.
    DIVERGENT: the full suite is green but the selection is red.
    ESCAPED: the full suite is red, and the selection is green or misses a failing test file.
    """
    escaped = [] if full_suite_reason else [t for t in full["failed"] if t.split("::")[0] not in selected_files]
    if full["green"]:
        return ("UNDETECTED" if selected["green"] else "DIVERGENT"), escaped
    if selected["green"] or escaped:
        return "ESCAPED", escaped
    return "OK", escaped


def localized_mutant(source, module, line, old, new):
    matches = [m for m in mp.iter_mutants(source, module) if m.text == line and m.old == old and m.new == new]
    if len(matches) != 1:
        raise ValueError(f"Expected one mutation at {module}: {line}, found {len(matches)}")
    mutant = matches[0]
    lines = source.splitlines(keepends=True)
    original = lines[mutant.line - 1]
    position = original.index(old, mutant.col)
    lines[mutant.line - 1] = original[:position] + new + original[position + len(old):]
    changed = "".join(lines)
    if ast.dump(ast.parse(changed)) != ast.dump(ast.parse(mutant.source)):
        raise ValueError("Localized replacement differs from mutation_pilot's AST")
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--control", action="store_true")
    mode.add_argument("--cases", action="store_true")
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    if root == SOURCE_ROOT or not (root / ".git").is_file():
        raise ValueError("Use a separate managed worktree; the source checkout is never mutated")
    out.mkdir(parents=True, exist_ok=True)
    validation.ROOT = selector.ROOT = root
    os.environ.update(NUMBA_NUM_THREADS="16", NUMBA_DISABLE_JIT="0", OPENBLAS_NUM_THREADS="1",
                      OMP_NUM_THREADS="1", QT_QPA_PLATFORM="offscreen")
    os.environ.pop("NUMBA_CACHE_DIR", None)  # Let each source version choose its own compiled cache.
    head = git(root, "rev-parse", "HEAD").decode().strip()
    files = selector.git("ls-files", "*.py") + selector.git("ls-files", "--others", "--exclude-standard", "*.py")
    digest = hashlib.sha256()
    for path in sorted(set(files)):
        digest.update(path.encode())
        digest.update((root / path).read_bytes())
    control_digest = digest.hexdigest()
    control_path = out / "control.json"
    if args.control:
        result = {"head": head, "source_digest": control_digest,
                  **full_suite(out / "control", args.workers, stop_on_failure=False)}
        save(control_path, result)
        return 0 if result["green"] else 1
    control = json.loads(control_path.read_text(encoding="utf-8"))
    if not control["green"] or control["head"] != head or control["source_digest"] != control_digest:
        raise ValueError("A green full-suite control on the same HEAD is required")
    cases = [("history", name, paths, commit) for name, commit, paths in HISTORY]
    cases += [("mutation", name, [module], (line, old, new)) for name, module, line, old, new in MUTATIONS]
    verdict = True
    for kind, name, paths, fault in cases:
        result_path = out / f"{name}.json"
        if result_path.exists():
            previous = json.loads(result_path.read_text(encoding="utf-8"))
            if previous["source_digest"] != control_digest:
                raise ValueError("Existing result belongs to a different control tree")
            status, _ = classify(previous["full_suite_reason"], previous["selected_files"], previous["selected"],
                                 previous["full"])
            print(f"COMPARISON={status} {name} (resumed)", flush=True)
            verdict &= status == "OK"
            continue
        originals = {path: (root / path).read_bytes() for path in paths}
        if any(git(root, "diff", "--", path).strip() for path in paths):
            raise ValueError(f"Refusing to overwrite local edits in {paths}")
        print(f"CASE={name} ({kind})", flush=True)
        try:
            if kind == "history":
                patch = git(root, "diff", f"{fault}^", fault, "--", *paths)
                git(root, "apply", "--reverse", "--ignore-whitespace", input_bytes=patch)
            else:
                module = paths[0]
                source = (root / module).read_bytes().decode("utf-8")  # bytes: keep the file's line endings
                (root / module).write_bytes(localized_mutant(source, module, *fault).encode("utf-8"))
            graph = selector.build_graph(files)
            selection = selector.select(graph, paths, base=head)
            selected = selected_suite(selection, out / name / "selected", args.workers)
            # Never stop early: classify needs every failing test of the full suite to list the escaped ones.
            full = full_suite(out / name / "full", args.workers, stop_on_failure=False)
            status, escaped = classify(selection.full_suite, selection.tests, selected, full)
            result = {
                "head": head, "source_digest": control_digest, "kind": kind, "name": name, "paths": paths, "fault": fault,
                "selected_files": sorted(selection.tests), "full_suite_reason": selection.full_suite,
                "selected": selected, "full": full, "escaped": escaped, "status": status,
            }
            save(result_path, result)
            print(f"COMPARISON={status} {name}", flush=True)
            verdict &= status == "OK"
        finally:
            for path, content in originals.items():
                (root / path).write_bytes(content)
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
