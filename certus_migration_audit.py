#!/usr/bin/env python3
"""
certus_migration_audit.py

Audit intelligent de fin de migration:
- recherche des patterns legacy
- exécution des tests ciblés
- collecte des preuves
- génération d'un dossier d'audit exploitable par une autre IA
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "migration_audit_report"
REPORT_DIR.mkdir(exist_ok=True)

PATTERNS = [
    r"progress\.emit\(",
    r"signals\.progress\.emit\(",
    r"self\.progress\.emit\(",
    r"progress_snapshot",
    r"build_progress_snapshot\(",
    r"StepState",
    r"format_eta\(",
]

LEGACY_PATTERNS = [
    r"progress\.emit\(",
    r"signals\.progress\.emit\(",
    r"self\.progress\.emit\(",
]

TARGET_TESTS = [
    "tests/ui/test_u8_u11_ux_widgets.py",
]

TARGET_FILES = [
    "certus/utils/certus_progress_tracker.py",
    "certus/workers/certus_index_workers.py",
    "certus/workers/certus_re_workers.py",
    "certus/workers/certus_strat_workers.py",
    "certus/workers/certus_spectral_workers.py",
    "certus/workers/certus_field_workers.py",
    "certus/workers/certus_design_workers.py",
]

SEARCH_DIRS = ["certus", "tests"]


def run(cmd: list[str], cwd: Path = ROOT, timeout: int = 1200) -> dict:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return {
            "cmd": cmd,
            "returncode": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": cmd,
            "returncode": -1,
            "stdout": e.stdout or "",
            "stderr": f"TIMEOUT after {timeout}s",
        }
    except FileNotFoundError as e:
        return {
            "cmd": cmd,
            "returncode": -127,
            "stdout": "",
            "stderr": str(e),
        }


def grep_pattern(pattern: str) -> dict:
    try:
        p = subprocess.run(
            ["rg", "-n", "-S", pattern, *SEARCH_DIRS],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            shell=False,
        )
        return {
            "pattern": pattern,
            "returncode": p.returncode,
            "matches": p.stdout.strip().splitlines() if p.stdout.strip() else [],
            "stderr": p.stderr.strip(),
        }
    except FileNotFoundError:
        matches = []
        regex = re.compile(pattern)
        for folder in SEARCH_DIRS:
            base = ROOT / folder
            if not base.exists():
                continue
            for path in base.rglob("*.py"):
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for i, line in enumerate(text.splitlines(), start=1):
                    if regex.search(line):
                        matches.append(f"{path.relative_to(ROOT)}:{i}:{line.strip()}")
        return {"pattern": pattern, "returncode": 0, "matches": matches, "stderr": ""}


def read_file(path_str: str) -> str:
    path = ROOT / path_str
    if not path.exists():
        return f"[MISSING] {path_str}"
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return f"[ERROR reading {path_str}] {e}"


def count_lines(text: str) -> int:
    return 0 if not text else len(text.splitlines())


def build_context_bundle() -> dict:
    bundle = {
        "timestamp": datetime.now().isoformat(),
        "repo_root": str(ROOT),
        "target_files": {},
        "patterns": {},
    }

    for target_file in TARGET_FILES:
        content = read_file(target_file)
        bundle["target_files"][target_file] = {
            "exists": not content.startswith("[MISSING]"),
            "line_count": count_lines(content) if not content.startswith("[") else 0,
            "content_head": "\n".join(content.splitlines()[:180]),
        }

    for pattern in PATTERNS:
        bundle["patterns"][pattern] = grep_pattern(pattern)

    return bundle


def make_markdown_report(report: dict, bundle: dict) -> str:
    lines = [
        "# CERTUS migration audit report",
        "",
        f"Generated: {report['timestamp']}",
        f"Repo: `{report['repo']}`",
        f"Verdict hint: **{report['verdict_hint']}**",
        "",
        "## Legacy pattern audit",
    ]
    for pattern in LEGACY_PATTERNS:
        data = report["grep_audit"][pattern]
        lines.append(f"- `{pattern}`: {len(data['matches'])} match(es)")
        for match in data["matches"][:50]:
            lines.append(f"  - `{match}`")
    lines.extend(["", "## Positive migration signals"])
    for pattern in [r"progress_snapshot", r"build_progress_snapshot\(", r"StepState", r"format_eta\("]:
        data = report["grep_audit"][pattern]
        lines.append(f"- `{pattern}`: {len(data['matches'])} match(es)")
    lines.extend(["", "## Tests"])
    for item in report["tests"]:
        result = item["result"]
        lines.append(f"- `{item['target']}`: return code `{result['returncode']}`")
        tail = "\n".join(result["stdout"].splitlines()[-20:])
        if tail:
            lines.append("```text")
            lines.append(tail)
            lines.append("```")
    lines.extend(["", "## Files included for external IA"])
    for target_file, meta in bundle["target_files"].items():
        lines.append(f"- `{target_file}`: exists={meta['exists']}, lines={meta['line_count']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    report = {
        "timestamp": datetime.now().isoformat(),
        "repo": str(ROOT),
        "python": sys.version,
        "grep_audit": {},
        "tests": [],
        "git": {},
        "context_bundle_file": None,
        "markdown_report_file": None,
        "verdict_hint": None,
    }

    report["git"]["status"] = run(["git", "status", "--short"])
    report["git"]["log"] = run(["git", "log", "-1", "--oneline"])
    report["git"]["branch"] = run(["git", "branch", "--show-current"])

    for pattern in PATTERNS:
        report["grep_audit"][pattern] = grep_pattern(pattern)

    for test_target in TARGET_TESTS:
        report["tests"].append(
            {
                "target": test_target,
                "result": run(["pytest", "-q", test_target], timeout=1800),
            }
        )

    bundle = build_context_bundle()
    bundle_path = REPORT_DIR / "context_bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    report["context_bundle_file"] = str(bundle_path)

    legacy_hits = []
    for pattern in LEGACY_PATTERNS:
        data = report["grep_audit"][pattern]
        if data["matches"]:
            legacy_hits.append((pattern, len(data["matches"])))

    test_failures = []
    for item in report["tests"]:
        if item["result"]["returncode"] != 0:
            test_failures.append(item["target"])

    positive_signals = sum(
        len(report["grep_audit"][pattern]["matches"])
        for pattern in [r"progress_snapshot", r"build_progress_snapshot\(", r"StepState"]
    )

    if not legacy_hits and not test_failures and positive_signals > 0:
        report["verdict_hint"] = "LIKELY_SUCCESS"
    elif test_failures and not legacy_hits:
        report["verdict_hint"] = "TESTS_FAIL"
    elif legacy_hits and not test_failures:
        report["verdict_hint"] = "LEGACY_REMAINS"
    elif not positive_signals:
        report["verdict_hint"] = "NO_POSITIVE_SIGNAL"
    else:
        report["verdict_hint"] = "MIXED"

    report_path = REPORT_DIR / "audit_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    markdown_path = REPORT_DIR / "audit_report.md"
    markdown_path.write_text(make_markdown_report(report, bundle), encoding="utf-8")
    report["markdown_report_file"] = str(markdown_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Audit report written to: {report_path}")
    print(f"Context bundle written to: {bundle_path}")
    print(f"Markdown report written to: {markdown_path}")
    print(f"Verdict hint: {report['verdict_hint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
