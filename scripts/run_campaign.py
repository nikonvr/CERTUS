"""Unattended measurement campaign. ONE command, no shell, no environment typing.

    .venv\\Scripts\\python.exe scripts\\run_campaign.py

Runs the whole overnight campaign and verifies each run got the configuration it
was asked for. Takes no argument, makes no choice, writes no code.

WHY THIS EXISTS

  The 2026-08-09 campaign was driven by `set VAR=value` lines typed into a shell.
  Two of its four runs silently kept a default because one line carried a trailing
  space, and nobody could see it for 25 minutes. The probe now refuses bad values
  and announces its configuration up front -- but that check needs a human in front
  of the screen, and an overnight campaign has none.

  So the environment is built HERE, as a dictionary, and handed to a subprocess.
  There is no shell to mangle it. And after every run this script re-reads the
  configuration the probe actually applied and compares it, key by key, to what was
  requested. A mismatch marks the run FAILED instead of quietly producing a number.

  Each run is a fresh subprocess: the kernels keep class-level caches, and a
  campaign in one process would let run N-1 contaminate run N.

RESUMABLE
  A run is skipped only if its transcript exists AND that transcript still passes the
  same configuration checks. Resuming must never be a way to inherit a bad run.

  ⚠️ The neutral runs all write the same probe JSON, since the file name is derived
  from the configuration and theirs is identical -- each overwrites the previous. That
  is intended and loses nothing: every run is kept in `reports/probe_runs.tsv` and in
  its own `reports/campagne_*.log`, which is where the jitter measurement reads from.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts" / "probe_anchor_noise_pipeline.py"
REPORTS = ROOT / "reports"
SUMMARY = REPORTS / "CAMPAGNE_RESUME.md"

#: Ceiling per run, in seconds, passed to the probe. 5400 is the value 10 settled on.
BENCH_TIMEOUT_S = "5400"
#: Hard ceiling this script applies to a subprocess, well above the probe's own.
SUBPROCESS_TIMEOUT_S = 9000

#: Default probe arguments: mode, scan step, seed. A plan entry may override them,
#: which is how a whole campaign is replayed on a second seed.
DEFAULT_ARGS = ("full", "1.0", "42")

#: Reference RESULT of the neutral configuration, seed 42, measured four times at the
#: bit on 2026-08-10. Quoted here so a plan can say what it expects to reproduce.
NEUTRAL_SEED42 = "0.002948627371309867"


def entry(label, purpose, *, env=None, expect=None, args=DEFAULT_ARGS, clear_cache=False):
    """One run. `expect` is what makes it self-checking; `clear_cache` forces a
    recompilation, which is a measurement in itself -- see the day plan."""
    return {
        "label": label, "purpose": purpose, "env": env or {},
        "expect": expect or {}, "args": tuple(args), "clear_cache": clear_cache,
    }


#: NIGHT plan, run on 2026-08-10. Kept so it can be replayed or resumed.
#: Result: POEM validated at x17.5, the bench shown deterministic, the Phase A margin
#: shown inert, and the index corridor shown to dwarf everything else.
PLAN_NIGHT = [
    entry("A12.1", "POEM on, distortion off -- reference arm",
          expect={"poem_enabled": True, "affine_scale_amp": 0.0}),
    entry("A12.2", "POEM on, distortion on",
          env={"CERTUS_AFFINE_SCALE_AMP": "0.05", "CERTUS_AFFINE_OFFSET_AMP": "0.02"},
          expect={"poem_enabled": True, "affine_scale_amp": 0.05, "affine_offset_amp": 0.02}),
    entry("A12.3", "POEM OFF, distortion off",
          env={"CERTUS_POEM_ENABLED": "0"},
          expect={"poem_enabled": False, "affine_scale_amp": 0.0}),
    entry("A12.4", "POEM OFF, distortion on -- the arm that decides",
          env={"CERTUS_POEM_ENABLED": "0", "CERTUS_AFFINE_SCALE_AMP": "0.05",
               "CERTUS_AFFINE_OFFSET_AMP": "0.02"},
          expect={"poem_enabled": False, "affine_scale_amp": 0.05}),
    entry("A15.1", "Phase A margin 3.33 instead of 1.66",
          env={"CERTUS_PHASE_A_MARGIN": "3.33"},
          expect={"phase_a_level_margin_factor": 3.33}),
    entry("A14.1", "index corridor 0.0025", env={"CERTUS_INDEX_CORRIDOR": "0.0025"},
          expect={"index_corridor": 0.0025}),
    entry("A14.2", "index corridor 0.005 -- the model value",
          env={"CERTUS_INDEX_CORRIDOR": "0.005"}, expect={"index_corridor": 0.005}),
    *[entry(f"A6.{i + 1}", "neutral repeat -- bench jitter", expect={"poem_enabled": True})
      for i in range(3)],
]

#: DAY plan. Four open questions, not a sweep. Ordered so that the one which needs a
#: COLD cache runs first -- every later run warms it.
PLAN_DAY = [
    # --- Q1. Is C1 even achievable? Only a recompilation can move the bits, so force
    # one on strictly unchanged code. Identical -> the golden rule holds as written.
    # Different -> C1 needs an explicit tolerance for signature changes. See 3.
    entry("B0.recompile", f"cold numba cache, unchanged code -- must it reproduce {NEUTRAL_SEED42} ?",
          expect={"poem_enabled": True, "index_corridor": 0.0}, clear_cache=True),

    # --- Q2. The headline result rests on ONE seed. 13 used seed 77 as its second
    # seed for exactly this reason. Replay the whole POEM matrix there.
    entry("B1.1", "seed 77 -- POEM on, distortion off", args=("full", "1.0", "77"),
          expect={"poem_enabled": True, "affine_scale_amp": 0.0}),
    entry("B1.2", "seed 77 -- POEM on, distortion on", args=("full", "1.0", "77"),
          env={"CERTUS_AFFINE_SCALE_AMP": "0.05", "CERTUS_AFFINE_OFFSET_AMP": "0.02"},
          expect={"poem_enabled": True, "affine_scale_amp": 0.05}),
    entry("B1.3", "seed 77 -- POEM OFF, distortion off", args=("full", "1.0", "77"),
          env={"CERTUS_POEM_ENABLED": "0"}, expect={"poem_enabled": False}),
    entry("B1.4", "seed 77 -- POEM OFF, distortion on", args=("full", "1.0", "77"),
          env={"CERTUS_POEM_ENABLED": "0", "CERTUS_AFFINE_SCALE_AMP": "0.05",
               "CERTUS_AFFINE_OFFSET_AMP": "0.02"},
          expect={"poem_enabled": False, "affine_scale_amp": 0.05}),

    # --- Q3. WHERE DOES POEM'S PROTECTION STOP? It is exactly invariant under an
    # affine distortion of the signal -- which is why it wins x17.5 there. An index
    # error is NOT such a distortion. The corridor is the largest effect measured;
    # does POEM protect against it at all? Compare with A14.2, same corridor, POEM on.
    entry("B2.1", "corridor 0.005 with POEM OFF -- the boundary of POEM's protection",
          env={"CERTUS_INDEX_CORRIDOR": "0.005", "CERTUS_POEM_ENABLED": "0"},
          expect={"index_corridor": 0.005, "poem_enabled": False}),

    # --- Q4. The detection threshold on the CURRENT grid. A1 measured that noise alone
    # fabricates a turning point in ~33 % of layers at the configured 1.66 A, and 0 %
    # at 2.4 A. Does the bench see it? Injected as the 5th argument.
    entry("B3.1", "tp_hysteresis 2.00 A -- the anti-fabrication bound",
          args=("full", "1.0", "42", "0", "2.0"), expect={"tp_hysteresis_factor": 2.0}),
    entry("B3.2", "tp_hysteresis 2.40 A -- where fabrication measured 0 %",
          args=("full", "1.0", "42", "0", "2.4"), expect={"tp_hysteresis_factor": 2.4}),

    # --- Q5. Complete the corridor curve. 0.0025 and 0.005 are known; the effect is
    # sub-linear and two points do not give a law.
    entry("B4.1", "index corridor 0.001", env={"CERTUS_INDEX_CORRIDOR": "0.001"},
          expect={"index_corridor": 0.001}),
    entry("B4.2", "index corridor 0.010 -- twice the model value",
          env={"CERTUS_INDEX_CORRIDOR": "0.01"}, expect={"index_corridor": 0.01}),
]

#: POST-A10 plan. The corridor now reaches the SCORING path, so the finished filter is
#: evaluated with the index it really has. Every corridor figure measured before this
#: covered only the growth half and was, by construction, an UNDERESTIMATE.
#:
#: The pair that matters is C1.3 against C1.5: B2 measured POEM protecting x7.6 against
#: index error, but it measured it on the half of the problem where POEM is good. The
#: crossed mode -- error of opposite sign either side of lambda_mon, uncompensable by
#: construction -- only shows in the final spectrum. That protection should now fall.
#: If it does not, the reasoning in 12.3 is wrong and that is worth knowing.
PLAN_POSTA10 = [
    entry("C1.0", "post-A10 baseline, corridor 0 -- re-establishes the reference after recompilation",
          expect={"index_corridor": 0.0, "poem_enabled": True}),
    entry("C1.1", "corridor 0.001 -- was x1.98 with growth only",
          env={"CERTUS_INDEX_CORRIDOR": "0.001"}, expect={"index_corridor": 0.001}),
    entry("C1.2", "corridor 0.0025 -- was x3.35 with growth only",
          env={"CERTUS_INDEX_CORRIDOR": "0.0025"}, expect={"index_corridor": 0.0025}),
    entry("C1.3", "corridor 0.005, the model value -- was x5.16 with growth only",
          env={"CERTUS_INDEX_CORRIDOR": "0.005"}, expect={"index_corridor": 0.005}),
    entry("C1.4", "corridor 0.010 -- was x8.19 with growth only",
          env={"CERTUS_INDEX_CORRIDOR": "0.01"}, expect={"index_corridor": 0.01}),
    entry("C1.5", "corridor 0.005 with POEM OFF -- does the x7.6 protection survive?",
          env={"CERTUS_INDEX_CORRIDOR": "0.005", "CERTUS_POEM_ENABLED": "0"},
          expect={"index_corridor": 0.005, "poem_enabled": False}),
]

PLANS = {"night": PLAN_NIGHT, "day": PLAN_DAY, "posta10": PLAN_POSTA10}


def probe_env(overrides: dict[str, str]) -> dict[str, str]:
    """A clean environment: every CERTUS_* cleared, then exactly what was asked.

    Clearing matters. A leftover variable from an earlier shell would silently apply
    to every run of the campaign and nothing would say so.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("CERTUS_")}
    env["CERTUS_BENCH_TIMEOUT_S"] = BENCH_TIMEOUT_S
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.update(overrides)
    return env


def parse_output(text: str) -> tuple[dict[str, object] | None, str | None, str | None]:
    """Pull (applied config, RESULT, output file) out of the probe's stdout."""
    config: dict[str, object] | None = None
    result: str | None = None
    written: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("CONFIG="):
            try:
                config = json.loads(line[len("CONFIG="):])
            except json.JSONDecodeError:
                config = None
        elif "RESULT=" in line and "MODE=" in line:
            result = line.split("RESULT=", 1)[1].strip()
        elif line.startswith("PROBE_WRITTEN="):
            written = line.split("=", 1)[1].split("  strategies=")[0].strip()
    return config, result, written


def check_expectations(applied: dict[str, object] | None, expected: dict[str, object]) -> list[str]:
    """Key-by-key comparison. This is the automated replacement for a human watching."""
    if applied is None:
        return ["no CONFIG= line in the output -- the run did not reach the end"]
    problems = []
    for key, want in expected.items():
        got = applied.get(key, "<absent>")
        if isinstance(want, bool) or isinstance(got, bool):
            ok = got is want
        elif isinstance(want, float):
            ok = isinstance(got, (int, float)) and abs(float(got) - want) < 1e-12
        else:
            ok = got == want
        if not ok:
            problems.append(f"{key}: asked {want!r}, applied {got!r}")
    return problems


def _display_path(path: Path) -> str:
    """Repo-relative when it can be, absolute otherwise. Never raises on a report path."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def transcript_path(label: str) -> Path:
    return REPORTS / f"campagne_{label.replace('.', '_')}.log"


def already_done(label: str, expected: dict[str, object]) -> dict | None:
    """Re-read a previous transcript and accept it only if it PASSES the same checks.

    Resuming must not be a way to inherit a bad run. A transcript that exists but
    whose configuration did not match, or that carries no RESULT, is not a result:
    the run is redone.
    """
    path = transcript_path(label)
    if not path.exists():
        return None
    out = path.read_text(encoding="utf-8", errors="replace")
    config, result, written = parse_output(out)
    problems = check_expectations(config, expected)
    if not result or result == "None" or problems:
        return None
    return {
        "label": label, "purpose": "", "status": "OK (repris)", "result": result,
        "written": written, "config": config, "problems": [],
        "transcript": _display_path(path),
    }


def clear_numba_cache() -> int:
    """Delete numba's on-disk cache so the next run must recompile.

    That recompilation IS the measurement: it is the only event shown capable of
    moving the last digits of a RESULT (see 3). Only .nbi/.nbc are removed -- never
    .pyc, which would say nothing.
    """
    removed = 0
    for pattern in ("**/__pycache__/*.nbi", "**/__pycache__/*.nbc"):
        for path in (ROOT / "certus").glob(pattern):
            path.unlink(missing_ok=True)
            removed += 1
    print(f"  numba cache cleared: {removed} file(s) removed", flush=True)
    return removed


def run_one(item: dict) -> dict:
    label, purpose = item["label"], item["purpose"]
    overrides, expected, args = item["env"], item["expect"], item["args"]
    print(f"\n{'=' * 72}\n{label} -- {purpose}", flush=True)
    resumed = already_done(label, expected)
    if resumed is not None:
        resumed["purpose"] = purpose
        print(f"  deja fait, RESULT = {resumed['result']} -- ignore", flush=True)
        return resumed
    print(f"  args:      {' '.join(args)}", flush=True)
    print(f"  overrides: {overrides or '(none, neutral run)'}", flush=True)
    if item["clear_cache"]:
        clear_numba_cache()
    cmd = [sys.executable, str(PROBE), *args]
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, env=probe_env(overrides), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=SUBPROCESS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        print(f"  {label}: TIMEOUT after {SUBPROCESS_TIMEOUT_S} s", flush=True)
        return {"label": label, "status": "TIMEOUT", "result": None, "problems": ["subprocess timeout"]}

    out = proc.stdout + proc.stderr
    config, result, written = parse_output(out)
    problems = check_expectations(config, expected)
    status = "OK" if (result and result != "None" and not problems) else "FAILED"

    transcript = transcript_path(label)
    transcript.write_text(out, encoding="utf-8")

    print(f"  RESULT   = {result}", flush=True)
    print(f"  file     = {written}", flush=True)
    print(f"  status   = {status}", flush=True)
    for p in problems:
        print(f"  MISMATCH {p}", flush=True)
    return {
        "label": label, "purpose": purpose, "status": status, "result": result,
        "written": written, "config": config, "problems": problems,
        "transcript": str(transcript.relative_to(ROOT)),
    }


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    name = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "day"
    if name not in PLANS:
        raise SystemExit(f"usage: run_campaign.py [{'|'.join(PLANS)}]   (default: day)")
    plan = PLANS[name]

    print(f"CAMPAIGN '{name}' -- {len(plan)} runs, roughly {len(plan) * 30} minutes", flush=True)
    print("Order is by decreasing value: if it is cut short, what got measured", flush=True)
    print("is what mattered most.", flush=True)

    records = []
    for item in plan:
        records.append(run_one(item))
        write_summary(records, len(plan))
    write_summary(records, len(plan))

    n_ok = sum(1 for r in records if r["status"] == "OK")
    print(f"\n{'=' * 72}\nDONE -- {n_ok}/{len(plan)} runs OK. Summary: {SUMMARY}", flush=True)
    return 0 if n_ok == len(plan) else 1


def write_summary(records: list[dict], total: int) -> None:
    """Rewritten after every run, so the summary is readable while the campaign runs."""
    lines = [
        "# RESUME DE CAMPAGNE",
        "",
        "Ecrit par `scripts/run_campaign.py` apres chaque run. Ce fichier est une SORTIE.",
        "",
        f"Runs termines : {len(records)} / {total}",
        "",
        "| run | statut | RESULT | objet |",
        "|---|---|---|---|",
    ]
    for r in records:
        lines.append(f"| {r['label']} | {r['status']} | `{r['result']}` | {r['purpose']} |")
    problems = [(r["label"], p) for r in records for p in r["problems"]]
    if problems:
        lines += ["", "## Ecarts entre demande et configuration appliquee", ""]
        lines += [f"- **{lab}** : {p}" for lab, p in problems]
    lines += ["", "## Configurations appliquees", ""]
    for r in records:
        lines.append(f"- **{r['label']}** — `{json.dumps(r['config'], sort_keys=True)}`")
    lines += ["", "Transcriptions completes : `reports/campagne_*.log`.", ""]
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
