"""scripts/validate_parallel.py : la recette mesuree le 2026-10-18, lue et jugee sans lancer la suite.

La commande lance la suite entiere (17 minutes) : ici on ne teste que ce qu'elle DECIDE. Le plan est la recette (6 workers
pour `ui`, `performance` en serie, les controles d'abord) ; les resumes sont ceux de pytest tels qu'ils sont sortis ce soir-la ;
le verdict ne se laisse pas tromper par la phrase d'un controle documentaire (son code de sortie compte : `coherence_md.py`
disait « 0 point a instruire » et sortait en 1, une commande morte dans un rapport).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts import validate_parallel as vp

# --- lire un resume de pytest ------------------------------------------------------------------------------------------------------------

REAL_SUMMARIES = [
    ("============ 1 failed, 5514 passed, 7 skipped, 1 xfailed in 507.27s (0:08:27) ============",
     {"failed": 1, "passed": 5514, "skipped": 7, "xfailed": 1}),
    ("=========== 1324 passed, 12 skipped, 2 xfailed in 282.86s (0:04:42) ===========",
     {"passed": 1324, "skipped": 12, "xfailed": 2}),
    ("============================ 1146 passed in 57.96s ============================", {"passed": 1146}),
    ("================ 319 passed, 20 warnings in 256.44s (0:04:16) =================", {"passed": 319, "warning": 20}),
    ("2 failed, 3 errors in 1.50s", {"failed": 2, "error": 3}),
]  # fmt: skip


@pytest.mark.parametrize(("line", "expected"), REAL_SUMMARIES)
def test_the_summaries_that_pytest_wrote_that_evening_are_read(line: str, expected: dict[str, int]) -> None:
    assert vp.parse_summary(f"noise\n.... [100%]\n{line}\nrc=0\n") == expected


def test_a_log_without_a_summary_has_no_counts() -> None:
    assert vp.parse_summary("Traceback (most recent call last):\n  boom\n") == {}


def test_the_failed_ids_keep_the_node_and_lose_the_message() -> None:
    text = "\n".join(
        [
            "FAILED tests/unit/test_a.py::test_x - AssertionError: assert 1 == 3",
            "FAILED tests/unit/test_a.py::test_p[a - b] - ValueError: no",  # a parameter may hold " - "
            "FAILED tests/unit/test_a.py::test_q[a b]",  # and spaces; and the message may be absent
            "ERROR tests/ui/test_ux_tab_order.py::test_last[CERTUS_DESIGN]",
            "ERROR tests/unit/test_collect.py - ImportError: cannot import",
            "FAILED tests/unit/test_a.py::test_x - AssertionError: assert 1 == 3",  # twice: once
            "  FAILED looks like a line of a traceback, not of the summary",
        ]
    )
    assert vp.failed_ids(text) == [
        "tests/unit/test_a.py::test_x",
        "tests/unit/test_a.py::test_p[a - b]",
        "tests/unit/test_a.py::test_q[a b]",
        "tests/ui/test_ux_tab_order.py::test_last[CERTUS_DESIGN]",
        "tests/unit/test_collect.py",
    ]


# --- le plan : la recette ----------------------------------------------------------------------------------------------------------------


def test_the_plan_is_the_measured_recipe() -> None:
    plan = {s.name: s for s in vp.build_plan(16, 6, True)}

    assert list(plan) == ["ruff", "coherence_md", "check_claude_md", "check_docs", "oracle", "unit", "ui", "rest", "performance"]
    assert plan["unit"].command[-4:] == ("-n", "16", "--dist", "loadfile")
    assert plan["ui"].command[-4:] == ("-n", "6", "--dist", "loadfile")  # 16 fails the ergonomics audit, 6 passes
    assert plan["rest"].command[-4:] == ("-n", "16", "--dist", "loadfile")
    assert {"--ignore=tests/oracle", "--ignore=tests/unit", "--ignore=tests/ui", "--ignore=tests/performance"} <= set(
        plan["rest"].command
    )
    for serial in ("ruff", "oracle", "performance", "coherence_md"):  # they time, or they are one process
        assert "-n" not in plan[serial].command
    assert all(s.kind == "check" for s in (plan["ruff"], plan["coherence_md"], plan["check_claude_md"], plan["check_docs"]))
    assert all(plan[n].kind == "pytest" for n in ("oracle", "unit", "ui", "rest", "performance"))


def test_the_ui_never_gets_more_workers_than_the_machine_has() -> None:
    assert vp.build_plan(4, 6, True, ["ui"])[0].command[-3] == "4"


def test_without_xdist_every_stage_runs_in_series() -> None:
    assert all("-n" not in s.command for s in vp.build_plan(16, 6, False))


def test_only_keeps_some_stages_in_the_order_of_the_recipe() -> None:
    assert [s.name for s in vp.build_plan(8, 6, True, ["ui", "unit"])] == ["unit", "ui"]
    assert [s.name for s in vp.build_plan(8, 6, True, ["docs"])] == ["coherence_md", "check_claude_md", "check_docs"]
    with pytest.raises(ValueError, match="etape inconnue : bogus"):
        vp.build_plan(8, 6, True, ["unit", "bogus"])


def test_a_wrong_stage_is_a_usage_error_not_a_traceback() -> None:
    with pytest.raises(SystemExit) as stop:
        vp.main(["--only", "bogus"])
    assert stop.value.code == 2


# --- jouer et juger ----------------------------------------------------------------------------------------------------------------------


def _result(name: str, returncode: int = 0, failed: tuple[str, ...] = (), kind: str = "pytest") -> vp.Result:
    return vp.Result(vp.Stage(name, ("x",), kind), returncode, 1.0, {"passed": 3}, list(failed), Path(f"{name}.log"))


def _play(
    results: list[vp.Result], persistent: set[str] | None = None, *, confirm: bool = True
) -> tuple[list[vp.Result], list[list[str]]]:
    """Plays the stages with their results given, and a replay that keeps `persistent` red. Rends (results, replays made)."""
    by_name = {r.stage.name: r for r in results}
    replays: list[list[str]] = []

    def replay(ids: list[str], _out: Path, _name: str) -> list[str]:
        replays.append(ids)
        return [i for i in ids if i in (persistent or set())]

    played = vp.execute([r.stage for r in results], Path("."), confirm=confirm,
                        run=lambda stage, _out: by_name[stage.name], rerun=replay, show=lambda _line: None)  # fmt: skip
    return played, replays


def test_a_green_run_is_a_go() -> None:
    played, replays = _play([_result("unit"), _result("ui")])

    assert [r.status for r in played] == ["PASS", "PASS"]
    assert replays == []
    assert vp.verdict(played)
    assert vp.report(played)[-2] == "VALIDATION=GO"


def test_a_failure_that_passes_alone_is_an_artefact_and_a_go_that_says_so() -> None:
    played, replays = _play([_result("unit", 1, ("tests/unit/test_bench.py::test_slow",))])

    assert replays == [["tests/unit/test_bench.py::test_slow"]]
    assert played[0].status == "ARTEFACT"
    assert played[0].replayed == ["tests/unit/test_bench.py::test_slow"]
    assert played[0].persistent == []
    lines = vp.report(played)
    assert vp.verdict(played)
    assert "ARTEFACT de charge ou d'ordre (unit), verts seuls en serie :" in lines
    assert "    tests/unit/test_bench.py::test_slow" in lines
    assert "VALIDATION=GO" in lines


def test_a_failure_that_fails_alone_too_is_a_real_failure() -> None:
    ids = ("tests/unit/test_a.py::test_a", "tests/unit/test_b.py::test_b")
    played, _ = _play([_result("unit", 1, ids)], persistent={"tests/unit/test_b.py::test_b"})

    assert played[0].status == "FAIL"
    assert played[0].persistent == ["tests/unit/test_b.py::test_b"]
    assert played[0].replayed == ["tests/unit/test_a.py::test_a"]
    assert not vp.verdict(played)
    lines = vp.report(played)
    assert "ECHEC REEL (unit), rouge aussi seul en serie :" in lines
    assert "VALIDATION=NO-GO" in lines


def test_a_document_check_is_judged_on_its_exit_code_and_never_replayed() -> None:
    """The report that carried a dead command made coherence_md.py exit 1 while its last line said "0 point a instruire"."""
    results = [_result("coherence_md", 1, kind="check")]
    played = vp.execute([r.stage for r in results], Path("."), run=lambda _s, _o: results[0],
                        rerun=lambda *_a: pytest.fail("a check has nothing to replay"), show=lambda _line: None)  # fmt: skip

    assert played[0].status == "FAIL"
    assert not vp.verdict(played)


def test_a_red_stage_with_no_readable_failure_is_not_declared_green() -> None:
    played, replays = _play([_result("unit", 2)])  # pytest exited 2 (interrupted, collection error) and named no test

    assert played[0].status == "FAIL"
    assert replays == []
    assert any("non rejoue" in line for line in vp.report(played))


def test_no_confirm_leaves_the_failures_red() -> None:
    played, replays = _play([_result("unit", 1, ("tests/unit/test_a.py::test_a",))], confirm=False)

    assert played[0].status == "FAIL"
    assert replays == []


def test_too_many_failures_are_not_replayed_one_by_one() -> None:
    ids = tuple(f"tests/unit/test_{i}.py::test_x" for i in range(vp.MAX_REPLAY + 1))
    played, replays = _play([_result("unit", 1, ids)])

    assert played[0].status == "FAIL"
    assert replays == []


def test_an_empty_run_is_not_a_go() -> None:
    assert not vp.verdict([])


# --- un vrai sous-processus --------------------------------------------------------------------------------------------------------------


def test_a_stage_is_run_logged_and_read(tmp_path: Path) -> None:
    code = "print('FAILED tests/x.py::t - boom'); print('1 failed, 2 passed in 0.10s'); raise SystemExit(1)"
    result = vp.run_stage(vp.Stage("fake", (sys.executable, "-c", code), "pytest"), tmp_path)

    assert result.returncode == 1
    assert result.counts == {"failed": 1, "passed": 2}
    assert result.failed == ["tests/x.py::t"]
    assert result.log == tmp_path / "fake.log"
    assert "boom" in result.log.read_text(encoding="utf-8")
    assert result.seconds >= 0.0


def test_a_check_is_run_for_its_exit_code_only(tmp_path: Path) -> None:
    result = vp.run_stage(vp.Stage("fake_check", (sys.executable, "-c", "print('0 point(s) a instruire.'); raise SystemExit(1)"), "check"), tmp_path)

    assert result.returncode == 1
    assert result.counts == {}
    assert result.failed == []
