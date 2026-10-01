"""Benchmarks of the hottest physics kernels, as ratios to a NumPy reference timed right beside them (audit v2, plan S7.5 and S3.5).

    python tools/bench_kernels.py                       measure and print the table
    python tools/bench_kernels.py --json bench.json     ... and write the report (the artefact the CI keeps)
    python tools/bench_kernels.py --write-baseline      store today's ratios in tests/performance/kernel_baseline.json
    python tools/bench_kernels.py --baseline FILE       exit 1 if a kernel costs more than 30 % above its baseline ratio

WHY RATIOS. A threshold in seconds fails on a loaded or slower machine and says nothing on a faster one (ETAT D38: a duration test failed on 2026-09-27
with three agents running tests at once, and passed at the same revision; the thresholds of `tests/performance/` were 100 to 500 times the cost they
guarded, so they caught nothing short of a catastrophe). The cost of a kernel divided by the cost of a fixed NumPy workload, the two timed back to back,
moves with the machine's speed and its load: the quotient only moves when the code does.

WHY MEDIANS OF PASSES OF 20 ms. One timing of a sub-millisecond call is mostly the clock and the scheduler. A pass runs the call as many times as it
takes to last `MIN_PASS_SECONDS`; a measurement is the median of `PASSES` passes; the ratio is the median of the `PASSES` quotients of a pass of the
kernel by the pass of the reference taken right before it, so that a load that comes and goes cancels in each quotient.

WHY ONE THREAD. The reference is a single-threaded NumPy workload; the kernels with `parallel=True` scale with the cores of the machine. Their ratio is
measured on one Numba thread, so that it can be compared from one machine to another. How they scale with the threads is `perf.py`'s question (the audit's,
with NUMBA_NUM_THREADS=1, 4, 16), not this one's.

WHY THE RE-MEASURE. A kernel flagged as slower is measured again on twice the passes, and the lower ratio of the two counts: a regression has to show
twice before it fails a run. A spike of load that outlasts a whole measurement is the one thing the quotient cannot cancel.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import platform
import statistics
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from certus.core.certus_core import ensure_numba_cache_dir  # noqa: E402  (does not load Numba)

ensure_numba_cache_dir()

import numpy as np  # noqa: E402

PASSES = 7
TOLERANCE = 0.30
MIN_PASS_SECONDS = 0.02
MAX_CALLS_PER_PASS = 1_000_000
BASELINE = ROOT / "tests" / "performance" / "kernel_baseline.json"
REPORT_FORMAT = 1

#: The kinds of finding `compare` reports; the first two fail a run, the others are notes.
FAILING = ("slower", "missing")


# --- the measurement ----------------------------------------------------------------------------------------------------------------------


def numpy_reference() -> Callable[[], object]:
    """A fixed single-threaded NumPy workload shaped like the kernels' own arithmetic: 2 x 2 complex matrix products over a few thousand points."""
    rng = np.random.default_rng(0)
    base = (rng.standard_normal((2048, 2, 2)) + 1j * rng.standard_normal((2048, 2, 2))) * 0.5
    base[:, 0, 0] += 1.0
    base[:, 1, 1] += 1.0

    def work() -> float:
        product = base
        for _ in range(4):
            product = product @ base
            product = product / np.abs(product).max(axis=(1, 2), keepdims=True)
        return float(np.abs(product).sum())

    work()
    return work


def calls_per_pass(call: Callable[[], object], min_seconds: float = MIN_PASS_SECONDS, clock: Callable[[], float] = time.perf_counter) -> int:
    """How many calls make a pass last at least `min_seconds` (a single one when it lasts that long alone)."""
    n = 1
    while True:
        start = clock()
        for _ in range(n):
            call()
        lasted = clock() - start
        if lasted >= min_seconds or n >= MAX_CALLS_PER_PASS:
            return n
        n = min(MAX_CALLS_PER_PASS, max(n * 2, int(n * min_seconds / lasted * 1.1)) if lasted > 0 else n * 10)


def seconds_per_call(call: Callable[[], object], n: int, clock: Callable[[], float] = time.perf_counter) -> float:
    start = clock()
    for _ in range(n):
        call()
    return (clock() - start) / n


@dataclass(frozen=True)
class Measure:
    """One kernel: the median quotient of its cost by the reference's, and what it was made of."""

    ratio: float
    seconds: float
    reference_seconds: float
    ratios: tuple[float, ...]


def measure_ratio(
    call: Callable[[], object],
    reference: Callable[[], object],
    passes: int = PASSES,
    min_pass_seconds: float = MIN_PASS_SECONDS,
    clock: Callable[[], float] = time.perf_counter,
) -> Measure:
    """The cost of `call` in references: median over `passes` of (a pass of `call`) / (the pass of `reference` taken right before it)."""
    n_call = calls_per_pass(call, min_pass_seconds, clock)
    n_reference = calls_per_pass(reference, min_pass_seconds, clock)
    ratios, calls, references = [], [], []
    for _ in range(passes):
        t_reference = seconds_per_call(reference, n_reference, clock)
        t_call = seconds_per_call(call, n_call, clock)
        references.append(t_reference)
        calls.append(t_call)
        ratios.append(t_call / t_reference)
    return Measure(statistics.median(ratios), statistics.median(calls), statistics.median(references), tuple(ratios))


# --- the comparison -----------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    name: str
    kind: str  # "slower" | "missing" | "faster" | "unbaselined"
    detail: str


def compare(ratios: Mapping[str, float], baseline: Mapping[str, float], tolerance: float = TOLERANCE) -> list[Finding]:
    """What differs between today's ratios and the baseline's. `slower` is more than `tolerance` above the baseline; `faster` is as far below it."""
    findings = []
    for name, base in sorted(baseline.items()):
        if name not in ratios:
            findings.append(Finding(name, "missing", "in the baseline, not measured"))
            continue
        now = ratios[name]
        if now > base * (1 + tolerance):
            findings.append(Finding(name, "slower", f"{now:.3g} references, baseline {base:.3g} (+{100 * (now / base - 1):.0f} %, limit +{100 * tolerance:.0f} %)"))
        elif now < base * (1 - tolerance):
            findings.append(Finding(name, "faster", f"{now:.3g} references, baseline {base:.3g} ({100 * (now / base - 1):.0f} %): the baseline can come down"))
    for name in sorted(set(ratios) - set(baseline)):
        findings.append(Finding(name, "unbaselined", f"{ratios[name]:.3g} references, no baseline yet: --write-baseline"))
    return findings


def failures(findings: Sequence[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.kind in FAILING]


# --- the kernels --------------------------------------------------------------------------------------------------------------------------

N_WLS = 401  # 320 - 720 nm at 1 nm
NUM_LAYERS = 21  # a mid-size stack
N_RUNS = 32  # the Monte Carlo batch of a robustness sample
N_STEPS = 64  # growth steps


def _wavelengths() -> np.ndarray:
    return np.linspace(320.0, 720.0, N_WLS, dtype=np.float64)


def _index(value: complex) -> np.ndarray:
    return np.full(N_WLS, value, dtype=np.complex128)


def _thicknesses() -> np.ndarray:
    return np.linspace(80.0, 140.0, NUM_LAYERS, dtype=np.float64)


def build_benches() -> dict[str, Callable[[], Callable[[], object]]]:
    """name -> a factory that builds the inputs, warms the kernel up (compilation and cache load are not measured) and returns the call to time."""
    from certus.core import _certus_physics_impl as kernels

    def batch() -> Callable[[], object]:
        wls, n_h, n_l, n_sub = _wavelengths(), _index(2.35 - 0.020j), _index(1.46 + 0.0j), _index(1.52 + 0.0j)
        rng = np.random.default_rng(42)
        stacks = np.ascontiguousarray((_thicknesses()[None, :] * (1.0 + 0.05 * rng.standard_normal((N_RUNS, NUM_LAYERS)))).astype(np.float64))
        kernels.calculate_RT_batch_kernel(wls, n_h, n_l, n_sub, stacks[:1])
        return lambda: kernels.calculate_RT_batch_kernel(wls, n_h, n_l, n_sub, stacks)

    def vectorized_hl() -> Callable[[], object]:
        wls, n_h, n_l, n_sub, thicknesses = _wavelengths(), _index(2.35 - 0.020j), _index(1.46 + 0.0j), _index(1.52 + 0.0j), _thicknesses()
        kernels.calculate_RT_vectorized_real_HL(wls, n_h, n_l, n_sub, thicknesses)
        return lambda: kernels.calculate_RT_vectorized_real_HL(wls, n_h, n_l, n_sub, thicknesses)

    def matrix_cache() -> Callable[[], object]:
        wls, n_h, n_l, thicknesses = _wavelengths(), _index(2.35 - 0.020j), _index(1.46 + 0.0j), _thicknesses()
        kernels.precompute_matrix_cache_kernel(wls, n_h, n_l, thicknesses, NUM_LAYERS)
        return lambda: kernels.precompute_matrix_cache_kernel(wls, n_h, n_l, thicknesses, NUM_LAYERS)

    def dynamics() -> Callable[[], object]:
        wls, n_layer, n_sub = _wavelengths(), _index(2.35 - 0.020j), _index(1.52 + 0.0j)
        steps = np.linspace(0.0, 100.0, N_STEPS, dtype=np.float64)
        identity = np.zeros((N_WLS, 2, 2), dtype=np.complex128)
        identity[:, 0, 0] = 1.0
        identity[:, 1, 1] = 1.0
        kernels.compute_dynamics_kernel(wls, n_layer, n_sub, steps, identity)
        return lambda: kernels.compute_dynamics_kernel(wls, n_layer, n_sub, steps, identity)

    def growth() -> Callable[[], object]:
        args = (_thicknesses(), 0, np.zeros(NUM_LAYERS, dtype=np.float64), 550.0, complex(2.35, -0.020), complex(1.46, 0.0), complex(1.52, 0.0), 0.0, 0.0, 1.0, 0)
        kernels.simulate_growth_kernel(*args)
        return lambda: kernels.simulate_growth_kernel(*args)

    def single_layer_single() -> Callable[[], object]:
        kernels.calculate_RT_single_layer_single(550.0, 2.05, 0.018, 120.0, 1.52)
        return lambda: kernels.calculate_RT_single_layer_single(550.0, 2.05, 0.018, 120.0, 1.52)

    def no_backside() -> Callable[[], object]:
        wls = np.linspace(320.0, 2200.0, 1024, dtype=np.float64)
        columns = (np.full(1024, 2.35 - 0.020j), np.full(1024, 1.46 - 0.000j), np.full(1024, 2.10 - 0.015j))
        layers = np.ascontiguousarray(np.column_stack(columns).astype(np.complex128))
        n_sub = np.full(1024, 1.52, dtype=np.float64).astype(np.complex128)
        thicknesses = np.asarray([85.0, 112.0, 95.0], dtype=np.float64)
        kernels.calculate_RT_no_backside(thicknesses, layers, n_sub, wls)
        return lambda: kernels.calculate_RT_no_backside(thicknesses, layers, n_sub, wls)

    def film_arrays() -> Callable[[], object]:
        wls = np.linspace(320.0, 2200.0, 1024, dtype=np.float64)
        n_film, k_film, n_sub = np.full(1024, 2.05), np.full(1024, 0.018), np.full(1024, 1.52)
        kernels.calculate_reflection_array(wls, n_film, k_film, 120.0, n_sub)
        kernels.calculate_transmission_array(wls, n_film, k_film, 120.0, n_sub)
        return lambda: (kernels.calculate_reflection_array(wls, n_film, k_film, 120.0, n_sub), kernels.calculate_transmission_array(wls, n_film, k_film, 120.0, n_sub))

    def bare_substrate() -> Callable[[], object]:
        wls = np.linspace(320.0, 2200.0, 1024, dtype=np.float64)
        n_sub = np.full(1024, 1.52, dtype=np.float64)
        kernels.calculate_bare_substrate_RT(wls, n_sub)
        return lambda: kernels.calculate_bare_substrate_RT(wls, n_sub)

    return {
        "RT_batch": batch,
        "RT_vectorized_HL": vectorized_hl,
        "matrix_cache": matrix_cache,
        "dynamics": dynamics,
        "growth_scoring": growth,
        "RT_single_layer_single": single_layer_single,
        "RT_no_backside": no_backside,
        "film_arrays": film_arrays,
        "bare_substrate": bare_substrate,
    }


@contextlib.contextmanager
def single_numba_thread() -> Iterator[None]:
    """Numba runs on one thread inside the block (see WHY ONE THREAD)."""
    import numba

    previous = numba.get_num_threads()
    numba.set_num_threads(1)
    try:
        yield
    finally:
        numba.set_num_threads(previous)


# --- the run ------------------------------------------------------------------------------------------------------------------------------


def run(benches: Mapping[str, Callable[[], Callable[[], object]]], reference: Callable[[], object], passes: int = PASSES, clock: Callable[[], float] = time.perf_counter) -> dict[str, Measure]:
    return {name: measure_ratio(factory(), reference, passes, clock=clock) for name, factory in benches.items()}


def confirm_slower(
    measures: dict[str, Measure],
    baseline: Mapping[str, float],
    benches: Mapping[str, Callable[[], Callable[[], object]]],
    reference: Callable[[], object],
    tolerance: float,
    passes: int,
    clock: Callable[[], float],
) -> dict[str, Measure]:
    """Measure again, on twice the passes, each kernel flagged as slower; keep the lower ratio of the two (a regression has to show twice)."""
    flagged = [f.name for f in compare({n: m.ratio for n, m in measures.items()}, baseline, tolerance) if f.kind == "slower"]
    confirmed = dict(measures)
    for name in flagged:
        again = measure_ratio(benches[name](), reference, 2 * passes, clock=clock)
        if again.ratio < measures[name].ratio:
            confirmed[name] = again
    return confirmed


def make_report(measures: Mapping[str, Measure], passes: int) -> dict:
    import numba

    return {
        "format": REPORT_FORMAT,
        "passes": passes,
        "tolerance": TOLERANCE,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "numba": numba.__version__,
        "numba_threads": 1,
        "kernels": {
            name: {
                "ratio": measure.ratio,
                "seconds": measure.seconds,
                "reference_seconds": measure.reference_seconds,
                "ratios": list(measure.ratios),
            }
            for name, measure in measures.items()
        },
    }


def read_baseline(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {name: float(ratio) for name, ratio in data["ratios"].items()}


def write_baseline(path: Path, measures: Mapping[str, Measure]) -> None:
    data = {
        "_comment": (
            "Cost of each kernel in NumPy references (tools/bench_kernels.py: median of passes of 20 ms - 7 for a run, 21 for a baseline - one Numba "
            "thread, reference timed right beside it). A run fails when a kernel costs more than 30 % above its ratio here. Rewrite with `python tools/bench_kernels.py --write-baseline` "
            "in a commit that says why the code got slower (or faster)."
        ),
        "format": REPORT_FORMAT,
        "tolerance": TOLERANCE,
        "measured_on": {"python": platform.python_version(), "platform": platform.platform()},
        "ratios": {name: float(f"{measure.ratio:.3g}") for name, measure in sorted(measures.items())},
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def format_table(measures: Mapping[str, Measure], findings: Sequence[Finding]) -> str:
    by_name = {finding.name: finding for finding in findings}
    lines = [f"{'kernel':26s} {'references':>11s} {'ms / call':>11s}  verdict"]
    for name, measure in measures.items():
        verdict = by_name[name].kind if name in by_name else "ok"
        lines.append(f"{name:26s} {measure.ratio:11.3g} {1000 * measure.seconds:11.4f}  {verdict}")
    lines.extend(f"{finding.name}: {finding.kind}: {finding.detail}" for finding in findings if finding.name not in measures)
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
    benches: Mapping[str, Callable[[], Callable[[], object]]] | None = None,
    clock: Callable[[], float] = time.perf_counter,
    reference: Callable[[], object] | None = None,
) -> int:
    """0: every kernel is within its baseline (or there is none); 1: at least one is slower, or a baselined one was not measured; 2: unreadable baseline."""
    parser = argparse.ArgumentParser(description="Cost of the hottest kernels in NumPy references (median of passes).")
    parser.add_argument("--passes", type=int, default=PASSES)
    parser.add_argument("--json", type=Path, help="write the report here")
    parser.add_argument("--baseline", type=Path, help="compare with this baseline (default with --write-baseline: tests/performance/kernel_baseline.json)")
    parser.add_argument("--write-baseline", action="store_true", help="store today's ratios as the baseline")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE)
    parser.add_argument("--only", nargs="+", metavar="KERNEL", help="measure these kernels only")
    args = parser.parse_args(argv)

    real = benches is None
    registry = dict(build_benches() if real else benches)
    if args.only:
        unknown = [name for name in args.only if name not in registry]
        if unknown:
            parser.error(f"unknown kernel(s): {', '.join(unknown)}; known: {', '.join(registry)}")
        registry = {name: registry[name] for name in args.only}

    baseline: dict[str, float] = {}
    if args.baseline and not args.write_baseline:
        try:
            baseline = read_baseline(args.baseline)
        except (OSError, ValueError, KeyError) as error:
            print(f"cannot read the baseline {args.baseline}: {error}", file=sys.stderr)
            return 2
        if args.only:
            baseline = {name: ratio for name, ratio in baseline.items() if name in registry}

    reference = reference or numpy_reference()
    passes = 3 * args.passes if args.write_baseline else args.passes  # a baseline is read for months: measure it harder than a run
    with single_numba_thread() if real else contextlib.nullcontext():
        measures = run(registry, reference, passes, clock)
        if baseline:
            measures = confirm_slower(measures, baseline, registry, reference, args.tolerance, passes, clock)

    if args.write_baseline:
        target = args.baseline or BASELINE
        write_baseline(target, measures)
        print(format_table(measures, []))
        print(f"baseline written: {target} ({passes} passes)")
        return 0

    findings = compare({name: measure.ratio for name, measure in measures.items()}, baseline, args.tolerance) if baseline else []
    print(format_table(measures, findings))
    if args.json:
        report = make_report(measures, args.passes) if real else {"format": REPORT_FORMAT, "passes": args.passes, "kernels": {n: {"ratio": m.ratio} for n, m in measures.items()}}
        report["findings"] = [{"name": f.name, "kind": f.kind, "detail": f.detail} for f in findings]
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bad = failures(findings)
    for finding in bad:
        print(f"REGRESSION: {finding.name}: {finding.kind}: {finding.detail}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
