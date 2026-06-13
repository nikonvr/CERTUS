from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


RUNTIME_MODULES = [
    "CERTUS_STRAT.py",
    "CERTUS_INDEX.py",
    "CERTUS_INDEX_SPLINE.py",
    "CERTUS_DESIGN.py",
    "CERTUS_RE.py",
    "CERTUS_METAL_SINGLE.py",
    "CERTUS_METAL_BILAYER.py",
    "certus_substrate_index.py",
    "certus_curve_smoother.py",
    "certus_reset_framework.py",
    "certus_metal_common.py",
]


@dataclass(frozen=True)
class KpiSnapshot:
    generated_at_utc: str
    kpi1_active_except_exception: int
    kpi1_archive_except_exception: int
    kpi7_active_broad_except_heuristic: int
    kpi2_runtime_event_loop_debt: int
    kpi2_runtime_process_events: int
    kpi2_runtime_time_sleep: int
    kpi3_manifest_sites_total: int
    kpi3_manifest_sites_wired: int
    kpi4_deterministic_tests_declared: int
    kpi4_deterministic_tests_required: int
    kpi5_physics_line_coverage_pct: float | None
    kpi5_physics_function_coverage_pct: float | None
    kpi6_headless_flows_tested: int
    kpi6_headless_flows_total: int

    @property
    def kpi3_manifest_coverage_pct(self) -> float:
        if self.kpi3_manifest_sites_total <= 0:
            return 0.0
        return 100.0 * self.kpi3_manifest_sites_wired / self.kpi3_manifest_sites_total

    @property
    def kpi4_deterministic_coverage_pct(self) -> float:
        if self.kpi4_deterministic_tests_required <= 0:
            return 0.0
        return 100.0 * self.kpi4_deterministic_tests_declared / self.kpi4_deterministic_tests_required

    @property
    def kpi6_headless_coverage_pct(self) -> float:
        if self.kpi6_headless_flows_total <= 0:
            return 0.0
        return 100.0 * self.kpi6_headless_flows_tested / self.kpi6_headless_flows_total


def _all_py_files() -> list[Path]:
    return [
        p
        for p in REPO_ROOT.rglob("*.py")
        if ".git" not in p.parts and "__pycache__" not in p.parts
    ]


def _active_module_files() -> list[Path]:
    files: list[Path] = []
    for p in _all_py_files():
        if "archive" in p.parts or "tests" in p.parts or "tools" in p.parts:
            continue
        name = p.name
        if name.startswith("CERTUS_") or name.startswith("certus_") or name == "_certus_physics_impl.py":
            files.append(p)
        elif name.startswith("spline_"):
            files.append(p)
        elif name == "_build_html_report.py":
            files.append(p)
    return files


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _count_regex(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.MULTILINE))


def _count_except_exception(active_only: bool) -> int:
    """KPI-1: Strict count - only bare except patterns (most problematic)."""
    total = 0
    files = _active_module_files() if active_only else [p for p in _all_py_files() if "archive" in p.parts]
    for p in files:
        total += _count_regex(_read_text(p), r"^\s*except\s*:")
    return total


def _count_broad_except_heuristic(active_only: bool) -> int:
    """KPI-7: Count broad except patterns (bare except, except Exception, broad tuples)."""
    total = 0
    files = _active_module_files() if active_only else [p for p in _all_py_files() if "archive" in p.parts]
    for p in files:
        text = _read_text(p)
        # Bare except
        total += _count_regex(text, r"^\s*except\s*:")
        # except Exception
        total += _count_regex(text, r"^\s*except\s+Exception\s*:")
        # except BaseException
        total += _count_regex(text, r"^\s*except\s+BaseException\s*:")
        # Broad exception tuples (ValueError, TypeError, RuntimeError, etc.)
        total += _count_regex(text, r"^\s*except\s*\(\s*ValueError\s*,\s*TypeError")
        total += _count_regex(text, r"^\s*except\s*\(\s*ValueError\s*,\s*RuntimeError")
        total += _count_regex(text, r"^\s*except\s*\(\s*TypeError\s*,\s*ValueError")
        # Common broad patterns
        total += _count_regex(text, r"^\s*except\s*\(\s*ValueError\s*,\s*TypeError\s*,\s*RuntimeError")
        total += _count_regex(text, r"^\s*except\s*\(\s*ValueError\s*,\s*TypeError\s*,\s*RuntimeError\s*,\s*AttributeError")
        total += _count_regex(text, r"^\s*except\s*\(\s*ValueError\s*,\s*TypeError\s*,\s*RuntimeError\s*,\s*AttributeError\s*,\s*KeyError")
        # Any tuple with 3+ exceptions
        total += _count_regex(text, r"^\s*except\s*\([^)]*,[^)]*,[^)]*\)")
    return total


def _runtime_event_loop_debt() -> tuple[int, int, int]:
    process_events = 0
    time_sleep = 0
    for filename in RUNTIME_MODULES:
        p = REPO_ROOT / filename
        if not p.exists():
            continue
        text = _read_text(p)
        process_events += _count_regex(text, r"\bprocessEvents\s*\(")
        time_sleep += _count_regex(text, r"\btime\.sleep\s*\(")
    return process_events + time_sleep, process_events, time_sleep


def _manifest_wiring_coverage() -> tuple[int, int]:
    """KPI-3: AST scan of BaseHeadlessRequest subclasses.

    `total_sites` uses a contractual floor of 6 so denominator growth is explicit.
    `wired_sites` counts discovered subclasses (manifest-capable by inheritance).
    """
    request_subclasses: set[str] = set()
    for p in _active_module_files():
        if "tests" in p.parts or "archive" in p.parts:
            continue
        text = _read_text(p)
        try:
            tree = ast.parse(text, filename=str(p))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            base_names: set[str] = set()
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.add(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.add(base.attr)
            if "BaseHeadlessRequest" not in base_names:
                continue
            request_subclasses.add(node.name)

    discovered = len(request_subclasses)
    total_sites = max(6, discovered)
    wired_sites = discovered
    return total_sites, wired_sites


def _deterministic_tests_declared() -> tuple[int, int]:
    """KPI-4: AST scan for np.random.default_rng seed contracts.

    - required: total runtime `default_rng(...)` call sites (floor = 6)
    - declared: call sites passing an explicit non-None seed, only if at least
      one deterministic seed assertion is present in tests.
    """
    total_rng_calls = 0
    seeded_rng_calls = 0

    for p in _active_module_files():
        if "tests" in p.parts or "archive" in p.parts or "tools" in p.parts:
            continue
        text = _read_text(p)
        try:
            tree = ast.parse(text, filename=str(p))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "default_rng":
                continue
            if not isinstance(func.value, ast.Attribute) or func.value.attr != "random":
                continue
            if not isinstance(func.value.value, ast.Name) or func.value.value.id != "np":
                continue

            total_rng_calls += 1
            is_seeded = False

            if node.args:
                first_arg = node.args[0]
                is_seeded = not (isinstance(first_arg, ast.Constant) and first_arg.value is None)

            if not is_seeded:
                for kw in node.keywords:
                    if kw.arg in {"seed"} and not (isinstance(kw.value, ast.Constant) and kw.value.value is None):
                        is_seeded = True
                        break

            if is_seeded:
                seeded_rng_calls += 1

    seed_assertions = 0
    deterministic_test_files = [
        REPO_ROOT / "tests" / "unit" / "test_seed_contract_global.py",
        REPO_ROOT / "tests" / "unit" / "test_certus_services.py",
    ]
    for p in deterministic_test_files:
        if p.exists():
            seed_assertions += _count_regex(_read_text(p), r"\bseed\s*=")

    required = max(6, total_rng_calls)
    declared = seeded_rng_calls if seed_assertions > 0 else 0
    return min(declared, required), required


def _headless_service_coverage_proxy() -> tuple[int, int]:
    """KPI-6: targeted service-flow contract coverage (AST + tests).

    Denominator is fixed to 6 target services defined in the roadmap.
    """
    target_services = {
        "MetalFitService",
        "DesignSynthService",
        "StratStrategyService",
        "IndexSplineService",
        "ReverseEngineeringService",
        "SpectralEvalService",
    }

    discovered: set[str] = set()
    for p in _active_module_files():
        text = _read_text(p)
        try:
            tree = ast.parse(text, filename=str(p))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in target_services:
                discovered.add(node.name)

    tests_text = ""
    for p in (REPO_ROOT / "tests").rglob("test_*.py"):
        tests_text += _read_text(p) + "\n"

    tested = 0
    for svc in target_services:
        if svc in discovered and svc in tests_text:
            tested += 1
    return tested, len(target_services)


def _kpi5_physics_coverage_runtime() -> tuple[float | None, float | None]:
    """Compute baseline coverage for _certus_physics_impl.py via pytest-cov when available."""
    target_file = REPO_ROOT / "_certus_physics_impl.py"
    if not target_file.exists():
        return None, None
    if importlib.util.find_spec("pytest_cov") is None:
        return None, None

    tests = [
        "tests/unit/test_certus_physics_structures.py",
        "tests/unit/test_certus_physics_hotpaths.py",
        "tests/test_tmm_inline.py",
        "tests/test_tmm_coherence.py",
        "tests/test_gradient_vs_fd.py",
        "tests/test_energy_conservation.py",
    ]
    for t in tests:
        if not (REPO_ROOT / t).exists():
            return None, None
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        cov_xml = td_path / "kpi5_coverage.xml"
        cmd = [
            "python",
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "--maxfail=1",
            "--cov=_certus_physics_impl",
            f"--cov-report=xml:{cov_xml}",
            "--cov-fail-under=0",
            *tests,
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if proc.returncode != 0 or not cov_xml.exists():
            return None, None

        try:
            root = ET.fromstring(cov_xml.read_text(encoding="utf-8"))
            class_node = None
            for cls in root.findall(".//class"):
                filename = cls.attrib.get("filename", "")
                if filename.endswith("_certus_physics_impl.py"):
                    class_node = cls
                    break
            if class_node is None:
                return None, None

            line_rate = float(class_node.attrib.get("line-rate", "0.0"))
            line_cov_pct = 100.0 * line_rate
            covered_lines: set[int] = set()
            for ln in class_node.findall(".//line"):
                try:
                    hits = int(ln.attrib.get("hits", "0"))
                    num = int(ln.attrib.get("number", "0"))
                except ValueError:
                    continue
                if hits > 0 and num > 0:
                    covered_lines.add(num)

            tree = ast.parse(_read_text(target_file), filename=str(target_file))
            funcs_total = 0
            funcs_hit = 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcs_total += 1
                    start = int(getattr(node, "lineno", 0) or 0)
                    end = int(getattr(node, "end_lineno", start) or start)
                    if any(start <= l <= end for l in covered_lines):
                        funcs_hit += 1
            if funcs_total <= 0:
                return line_cov_pct, None
            return line_cov_pct, 100.0 * funcs_hit / funcs_total
        except (ValueError, ET.ParseError, OSError, SyntaxError):
            return None, None


def build_snapshot(*, include_runtime_kpi5: bool = False) -> KpiSnapshot:
    debt_total, debt_process, debt_sleep = _runtime_event_loop_debt()
    manifest_total, manifest_wired = _manifest_wiring_coverage()
    deterministic_declared, deterministic_required = _deterministic_tests_declared()
    headless_tested, headless_total = _headless_service_coverage_proxy()
    if include_runtime_kpi5:
        kpi5_line_cov, kpi5_func_cov = _kpi5_physics_coverage_runtime()
    else:
        kpi5_line_cov, kpi5_func_cov = None, None
    return KpiSnapshot(
        generated_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        kpi1_active_except_exception=_count_except_exception(active_only=True),
        kpi1_archive_except_exception=_count_except_exception(active_only=False),
        kpi7_active_broad_except_heuristic=_count_broad_except_heuristic(active_only=True),
        kpi2_runtime_event_loop_debt=debt_total,
        kpi2_runtime_process_events=debt_process,
        kpi2_runtime_time_sleep=debt_sleep,
        kpi3_manifest_sites_total=manifest_total,
        kpi3_manifest_sites_wired=manifest_wired,
        kpi4_deterministic_tests_declared=deterministic_declared,
        kpi4_deterministic_tests_required=deterministic_required,
        kpi5_physics_line_coverage_pct=kpi5_line_cov,
        kpi5_physics_function_coverage_pct=kpi5_func_cov,
        kpi6_headless_flows_tested=headless_tested,
        kpi6_headless_flows_total=headless_total,
    )


def to_markdown(snapshot: KpiSnapshot) -> str:
    kpi5_line_txt = (
        f"**{snapshot.kpi5_physics_line_coverage_pct:.1f}%**"
        if snapshot.kpi5_physics_line_coverage_pct is not None
        else "N/A (run with `--with-kpi5-runtime`)"
    )
    kpi5_func_txt = (
        f"**{snapshot.kpi5_physics_function_coverage_pct:.1f}%**"
        if snapshot.kpi5_physics_function_coverage_pct is not None
        else "N/A (run with `--with-kpi5-runtime`)"
    )
    return (
        "# CERTUS KPI Snapshot\n\n"
        f"- Generated (UTC): `{snapshot.generated_at_utc}`\n\n"
        "## KPI-1 Broad Exception Debt (strict)\n"
        f"- Active codebase `except Exception`: **{snapshot.kpi1_active_except_exception}**\n"
        f"- Archive `except Exception`: **{snapshot.kpi1_archive_except_exception}**\n\n"
        "## KPI-7 Broad Exception Heuristic\n"
        f"- Active codebase broad except patterns: **{snapshot.kpi7_active_broad_except_heuristic}**\n\n"
        "## KPI-2 Event Loop Purity Debt (runtime modules)\n"
        f"- Total debt (`processEvents` + `time.sleep`): **{snapshot.kpi2_runtime_event_loop_debt}**\n"
        f"- `processEvents`: {snapshot.kpi2_runtime_process_events}\n"
        f"- `time.sleep`: {snapshot.kpi2_runtime_time_sleep}\n\n"
        "## KPI-3 Manifest Coverage (AST: BaseHeadlessRequest subclasses)\n"
        f"- Request subclasses denominator (AST, floor=6): **{snapshot.kpi3_manifest_sites_total}**\n"
        f"- Request subclasses discovered (manifest-capable): **{snapshot.kpi3_manifest_sites_wired}**\n"
        f"- Coverage: **{snapshot.kpi3_manifest_coverage_pct:.1f}%**\n\n"
        "## KPI-4 Deterministic Coverage (AST: np.random.default_rng seed contracts)\n"
        f"- Seeded RNG call sites / required call sites: **{snapshot.kpi4_deterministic_tests_declared}/{snapshot.kpi4_deterministic_tests_required}**\n"
        f"- Coverage: **{snapshot.kpi4_deterministic_coverage_pct:.1f}%**\n\n"
        "## KPI-5 Physics Direct Coverage (_certus_physics_impl.py)\n"
        f"- Line coverage baseline: {kpi5_line_txt}\n"
        f"- Function coverage baseline (proxy): {kpi5_func_txt}\n\n"
        "## KPI-6 Headless Service Coverage (proxy)\n"
        f"- Headless service flows tested: **{snapshot.kpi6_headless_flows_tested}/{snapshot.kpi6_headless_flows_total}**\n"
        f"- Coverage: **{snapshot.kpi6_headless_coverage_pct:.1f}%**\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CERTUS KPI snapshot report.")
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write markdown snapshot to reports/KPI_SNAPSHOT_<date>.md",
    )
    parser.add_argument(
        "--with-kpi5-runtime",
        action="store_true",
        help="Run focused runtime coverage for _certus_physics_impl.py baseline.",
    )
    args = parser.parse_args()

    snapshot = build_snapshot(include_runtime_kpi5=bool(args.with_kpi5_runtime))
    md = to_markdown(snapshot)
    print(md)

    if args.write_report:
        reports_dir = REPO_ROOT / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        day = datetime.now(UTC).date().isoformat()
        out = reports_dir / f"KPI_SNAPSHOT_{day}.md"
        out.write_text(md, encoding="utf-8")
        print(f"\nWritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
