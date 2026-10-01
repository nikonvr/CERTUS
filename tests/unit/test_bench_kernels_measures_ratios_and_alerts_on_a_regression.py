"""`tools/bench_kernels.py` measures kernels in NumPy references and alerts on a regression (audit v2, plan S7.5 and S3.5).

A threshold in seconds fails on a loaded machine and says nothing on a fast one (ETAT D38); the thresholds of `tests/performance/` were 100 to 500 times the
cost they guarded. The tool times each kernel beside a fixed NumPy workload and works with the quotient. What is pinned here, with a fake clock that only
moves when a call costs something (so that every measurement is exact):

    the cost of a call in references is the median over the passes of the quotient, not the mean, not the minimum
    a machine twice as slow, or ten times as loaded, leaves the ratio alone
    a pass lasts long enough to be measured, and a call that costs nothing does not loop forever
    a kernel more than 30 % above its baseline fails the run, one inside the tolerance does not; a spike that does not repeat does not fail it
    a kernel made slower on purpose is caught - with the fake kernels and with a real one
    the committed baseline names every kernel the tool measures
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import bench_kernels as bench  # noqa: E402


class World:
    """A clock that moves only when a call costs something, and a machine whose speed can change."""

    def __init__(self) -> None:
        self.now = 0.0
        self.speed = 1.0  # 5.0: every call takes five times as long (a slower or a loaded machine)

    def clock(self) -> float:
        return self.now

    def call(self, cost: float):
        def run() -> None:
            self.now += cost * self.speed

        return run

    def scripted(self, costs: list[float]):
        """A call whose successive costs are `costs` (the last one repeats)."""
        index = [0]

        def run() -> None:
            self.now += costs[min(index[0], len(costs) - 1)] * self.speed
            index[0] += 1

        return run


REFERENCE_COST = 1e-3


@pytest.fixture
def world() -> World:
    return World()


def run_main(world: World, kernels: dict, *args: str) -> int:
    return bench.main(list(args), benches=kernels, clock=world.clock, reference=world.call(REFERENCE_COST))


# --- the measurement -------------------------------------------------------------------------------------------------------------------------


def test_a_pass_runs_the_call_until_it_lasts_long_enough(world):
    n = bench.calls_per_pass(world.call(1e-3), min_seconds=0.02, clock=world.clock)
    assert 20 <= n <= 30  # 20 ms at 1 ms a call, with the margin of the estimate


def test_a_call_that_lasts_long_alone_is_run_once_per_pass(world):
    assert bench.calls_per_pass(world.call(0.05), min_seconds=0.02, clock=world.clock) == 1


def test_a_call_that_costs_nothing_does_not_loop_forever(world):
    assert bench.calls_per_pass(world.call(0.0), min_seconds=0.02, clock=world.clock) == bench.MAX_CALLS_PER_PASS


def test_the_ratio_is_the_cost_of_the_call_in_references(world):
    measure = bench.measure_ratio(world.call(3e-3), world.call(1e-3), passes=7, clock=world.clock)
    assert measure.ratio == pytest.approx(3.0)
    assert measure.seconds == pytest.approx(3e-3)
    assert measure.reference_seconds == pytest.approx(1e-3)
    assert len(measure.ratios) == 7


def test_the_ratio_is_the_median_of_the_passes_not_their_mean(world):
    # one call per pass (30 ms each): the first call is the one that sizes the pass, the next seven are the passes, the fourth of them a spike
    call = world.scripted([30e-3, 30e-3, 30e-3, 30e-3, 300e-3, 30e-3, 30e-3, 30e-3])
    measure = bench.measure_ratio(call, world.call(30e-3), passes=7, clock=world.clock)
    assert sorted(measure.ratios)[-1] == pytest.approx(10.0)
    assert measure.ratio == pytest.approx(1.0)  # a mean would say 2.3


def test_a_slower_or_loaded_machine_leaves_the_ratio_alone(world):
    first = bench.measure_ratio(world.call(3e-3), world.call(1e-3), passes=7, clock=world.clock)
    world.speed = 5.0
    second = bench.measure_ratio(world.call(3e-3), world.call(1e-3), passes=7, clock=world.clock)
    assert second.seconds == pytest.approx(5 * first.seconds)
    assert second.ratio == pytest.approx(first.ratio)


# --- the comparison --------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "kind"),
    [(1.29, None), (1.30, None), (1.31, "slower"), (3.0, "slower"), (0.71, None), (0.69, "faster"), (1.0, None)],
)
def test_compare_flags_what_is_more_than_the_tolerance_from_its_baseline(now, kind):
    findings = bench.compare({"k": now}, {"k": 1.0}, tolerance=0.30)
    assert [f.kind for f in findings] == ([kind] if kind else [])


def test_compare_reports_a_kernel_that_was_not_measured_and_one_without_a_baseline():
    findings = bench.compare({"new": 1.0, "kept": 1.0}, {"kept": 1.0, "gone": 2.0})
    assert {(f.name, f.kind) for f in findings} == {("gone", "missing"), ("new", "unbaselined")}


def test_only_a_slower_or_a_missing_kernel_fails():
    findings = bench.compare({"slow": 2.0, "fast": 0.1, "new": 1.0}, {"slow": 1.0, "fast": 1.0, "gone": 1.0})
    assert {f.name for f in bench.failures(findings)} == {"slow", "gone"}


# --- the tool, from the command line ---------------------------------------------------------------------------------------------------------


def fake_kernels(world: World) -> dict:
    return {"light": lambda: world.call(2e-3), "heavy": lambda: world.call(5e-3)}


def write_baseline(world: World, tmp_path: Path) -> Path:
    path = tmp_path / "baseline.json"
    assert run_main(world, fake_kernels(world), "--write-baseline", "--baseline", str(path)) == 0
    return path


def test_the_baseline_is_written_in_references(world, tmp_path):
    ratios = json.loads(write_baseline(world, tmp_path).read_text(encoding="utf-8"))["ratios"]
    assert ratios == {"heavy": pytest.approx(5.0), "light": pytest.approx(2.0)}


def test_a_run_against_its_own_baseline_passes(world, tmp_path):
    path = write_baseline(world, tmp_path)
    assert run_main(world, fake_kernels(world), "--baseline", str(path)) == 0


def test_a_kernel_made_slower_on_purpose_fails_the_run_and_is_named(world, tmp_path, capsys):
    path = write_baseline(world, tmp_path)
    kernels = fake_kernels(world)
    kernels["heavy"] = lambda: world.call(5e-3 * 1.5)  # 50 % more
    assert run_main(world, kernels, "--baseline", str(path)) == 1
    err = capsys.readouterr().err
    assert "REGRESSION: heavy: slower" in err
    assert "light" not in err


@pytest.mark.parametrize(("factor", "code"), [(1.25, 0), (1.35, 1)])
def test_the_tolerance_is_thirty_percent(world, tmp_path, factor, code):
    path = write_baseline(world, tmp_path)
    kernels = fake_kernels(world)
    kernels["light"] = lambda: world.call(2e-3 * factor)
    assert run_main(world, kernels, "--baseline", str(path)) == code


def test_a_machine_five_times_slower_does_not_fail_the_run(world, tmp_path):
    path = write_baseline(world, tmp_path)
    world.speed = 5.0
    assert run_main(world, fake_kernels(world), "--baseline", str(path)) == 0


def test_a_spike_that_does_not_repeat_does_not_fail_the_run(world, tmp_path):
    path = write_baseline(world, tmp_path)
    builds = []

    def heavy():
        builds.append(1)
        return world.call(5e-3 * (3.0 if len(builds) == 1 else 1.0))  # the first measurement meets a spike, the second does not

    kernels = fake_kernels(world)
    kernels["heavy"] = heavy
    assert run_main(world, kernels, "--baseline", str(path)) == 0
    assert len(builds) == 2  # it was measured again before being judged


def test_a_regression_that_repeats_fails_the_run_after_the_second_measurement(world, tmp_path):
    path = write_baseline(world, tmp_path)
    builds = []

    def heavy():
        builds.append(1)
        return world.call(5e-3 * 3.0)

    kernels = fake_kernels(world)
    kernels["heavy"] = heavy
    assert run_main(world, kernels, "--baseline", str(path)) == 1
    assert len(builds) == 2


def test_a_baselined_kernel_that_is_not_measured_fails_the_run(world, tmp_path, capsys):
    path = write_baseline(world, tmp_path)
    kernels = fake_kernels(world)
    del kernels["heavy"]
    assert run_main(world, kernels, "--baseline", str(path)) == 1
    assert "REGRESSION: heavy: missing" in capsys.readouterr().err


def test_an_unreadable_baseline_is_reported_and_not_taken_for_a_pass(world, tmp_path, capsys):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert run_main(world, fake_kernels(world), "--baseline", str(broken)) == 2
    assert "cannot read the baseline" in capsys.readouterr().err
    assert run_main(world, fake_kernels(world), "--baseline", str(tmp_path / "absent.json")) == 2


def test_the_report_carries_the_ratios_and_the_findings(world, tmp_path):
    path = write_baseline(world, tmp_path)
    kernels = fake_kernels(world)
    kernels["heavy"] = lambda: world.call(5e-3 * 2.0)
    out = tmp_path / "report.json"
    assert run_main(world, kernels, "--baseline", str(path), "--json", str(out)) == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["kernels"]["heavy"]["ratio"] == pytest.approx(10.0)
    assert report["kernels"]["light"]["ratio"] == pytest.approx(2.0)
    assert [(f["name"], f["kind"]) for f in report["findings"]] == [("heavy", "slower")]


def test_only_measures_the_kernels_asked_for_and_refuses_an_unknown_one(world, capsys):
    assert run_main(world, fake_kernels(world), "--only", "light") == 0
    out = capsys.readouterr().out
    assert "light" in out
    assert "heavy" not in out
    with pytest.raises(SystemExit) as stop:
        run_main(world, fake_kernels(world), "--only", "nonexistent")
    assert stop.value.code == 2


# --- the real kernels ------------------------------------------------------------------------------------------------------------------------


def test_the_committed_baseline_names_every_kernel_of_the_tool():
    baseline = bench.read_baseline(bench.BASELINE)
    assert set(baseline) == set(bench.build_benches())
    assert all(ratio > 0 for ratio in baseline.values())


def test_the_real_kernels_run_and_a_real_slowdown_is_caught(tmp_path, monkeypatch, capsys):
    """One real kernel, measured and baselined here, then made twice as slow: the tool must say so (no fake clock, no fake kernel)."""
    path = tmp_path / "real.json"
    assert bench.main(["--only", "bare_substrate", "--passes", "3", "--write-baseline", "--baseline", str(path)]) == 0
    assert bench.main(["--only", "bare_substrate", "--passes", "3", "--baseline", str(path)]) == 0  # itself, a minute later: inside the tolerance

    kernels = importlib.import_module("certus.core._certus_physics_impl")
    original = kernels.calculate_bare_substrate_RT

    def twice_the_work(*args):
        original(*args)
        return original(*args)

    monkeypatch.setattr(kernels, "calculate_bare_substrate_RT", twice_the_work)
    capsys.readouterr()
    assert bench.main(["--only", "bare_substrate", "--passes", "3", "--baseline", str(path)]) == 1
    assert "REGRESSION: bare_substrate: slower" in capsys.readouterr().err
