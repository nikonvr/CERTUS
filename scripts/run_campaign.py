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

#: The campaign, in order of decreasing value. If the night is cut short, what got
#: measured is what mattered most.
#:
#: Each entry: (label, purpose, env overrides, expected config after resolution).
#: The expectation is what makes the run self-checking.
CAMPAIGN: tuple[tuple[str, str, dict[str, str], dict[str, object]], ...] = (
    (
        "A12.1", "POEM on, distortion off -- the reference arm of the POEM test",
        {},
        {"poem_enabled": True, "affine_scale_amp": 0.0, "affine_offset_amp": 0.0},
    ),
    (
        "A12.2", "POEM on, distortion on",
        {"CERTUS_AFFINE_SCALE_AMP": "0.05", "CERTUS_AFFINE_OFFSET_AMP": "0.02"},
        {"poem_enabled": True, "affine_scale_amp": 0.05, "affine_offset_amp": 0.02},
    ),
    (
        "A12.3", "POEM OFF, distortion off",
        {"CERTUS_POEM_ENABLED": "0"},
        {"poem_enabled": False, "affine_scale_amp": 0.0, "affine_offset_amp": 0.0},
    ),
    (
        "A12.4", "POEM OFF, distortion on -- the arm that decides",
        {
            "CERTUS_POEM_ENABLED": "0",
            "CERTUS_AFFINE_SCALE_AMP": "0.05",
            "CERTUS_AFFINE_OFFSET_AMP": "0.02",
        },
        {"poem_enabled": False, "affine_scale_amp": 0.05, "affine_offset_amp": 0.02},
    ),
    (
        "A15.1", "Phase A margin 3.33 instead of 1.66",
        {"CERTUS_PHASE_A_MARGIN": "3.33"},
        {"phase_a_level_margin_factor": 3.33},
    ),
    (
        "A14.1", "index corridor 0.0025 -- half width",
        {"CERTUS_INDEX_CORRIDOR": "0.0025"},
        {"index_corridor": 0.0025},
    ),
    (
        "A14.2", "index corridor 0.005 -- the model value",
        {"CERTUS_INDEX_CORRIDOR": "0.005"},
        {"index_corridor": 0.005},
    ),
)

#: Neutral runs repeated to measure the bench's own jitter (A6). Same configuration
#: every time; the spread between them IS the measurement. Three points and two
#: clusters is not an envelope.
JITTER_REPEATS = 3


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


def run_one(label: str, purpose: str, overrides: dict[str, str], expected: dict[str, object]) -> dict:
    print(f"\n{'=' * 72}\n{label} -- {purpose}", flush=True)
    resumed = already_done(label, expected)
    if resumed is not None:
        resumed["purpose"] = purpose
        print(f"  deja fait, RESULT = {resumed['result']} -- ignore", flush=True)
        return resumed
    print(f"  overrides: {overrides or '(none, neutral run)'}", flush=True)
    cmd = [sys.executable, str(PROBE), "full", "1.0", "42"]
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
    plan = list(CAMPAIGN) + [
        (
            f"A6.{i + 1}", "neutral repeat -- measures the bench's own jitter",
            {}, {"poem_enabled": True, "index_corridor": 0.0, "affine_scale_amp": 0.0},
        )
        for i in range(JITTER_REPEATS)
    ]

    print(f"CAMPAIGN -- {len(plan)} runs, roughly {len(plan) * 30} minutes", flush=True)
    print("Order is by decreasing value: if the night is cut short, what got", flush=True)
    print("measured is what mattered most.", flush=True)

    records = []
    for label, purpose, overrides, expected in plan:
        records.append(run_one(label, purpose, overrides, expected))
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
