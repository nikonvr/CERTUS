"""The UX audit measures a window once per (module, size) and per process (audit v2, plan S3.3).

Measuring one window costs 10 to 15 seconds: a process of its own, the construction, and the wait for the deferred timers to drain. Four files of `tests/ui/`
(skeleton, height of the buttons, order of the tabs, ratchet) asked for the same eleven rows at 1920 x 1080: on 2026-10-01 they took 550 s of a 1 594 s run
between them. The tree does not change during a session and neither does the measure, so `_run_worker` keeps what it has measured.

What is pinned here, with a fake worker (the real one starts a process and a window):

    the same module at the same size is measured once; another size or another module is measured again
    a reader gets a COPY: none of them can spoil the row the others will read
    `fresh=True` measures again, and the new row replaces the old one
    a row in error is never kept: the run retries up to three times, then exits, and a later success is measured and kept
"""

from __future__ import annotations

import pytest

from scripts import audit_ux_certus as audit


@pytest.fixture(autouse=True)
def _nothing_measured_yet(monkeypatch):
    monkeypatch.setattr(audit, "_ROWS", {})


@pytest.fixture
def worker(monkeypatch):
    """A fake `_run_worker_once` that records what it is asked and returns a row with nested data."""
    calls: list[tuple[str, int, int]] = []

    def fake(tag, env, width, height):
        calls.append((tag, width, height))
        return {"app": tag, "n": len(calls), "tabs": ["a", "b"], "nested": {"k": [1, 2]}}

    monkeypatch.setattr(audit, "_run_worker_once", fake)
    return calls


def test_a_module_is_measured_once_for_the_same_size(worker):
    first = audit._run_worker("CERTUS_X", 1920, 1080)
    second = audit._run_worker("CERTUS_X", 1920, 1080)
    assert worker == [("CERTUS_X", 1920, 1080)]
    assert second == first


def test_another_size_or_another_module_is_measured_again(worker):
    audit._run_worker("CERTUS_X", 1920, 1080)
    audit._run_worker("CERTUS_X", 1366, 768)
    audit._run_worker("CERTUS_Y", 1920, 1080)
    audit._run_worker("CERTUS_X", 1920, 1080)
    assert worker == [("CERTUS_X", 1920, 1080), ("CERTUS_X", 1366, 768), ("CERTUS_Y", 1920, 1080)]


def test_the_default_size_is_the_one_of_the_tests(worker):
    audit._run_worker("CERTUS_X")
    audit._run_worker("CERTUS_X", 1920, 1080)
    assert worker == [("CERTUS_X", 1920, 1080)]


def test_a_reader_cannot_spoil_the_row_the_others_read(worker):
    first = audit._run_worker("CERTUS_X", 1920, 1080)  # the row just measured
    first["tabs"].append("spoiled")
    first["nested"]["k"].append(99)
    first["added"] = True
    second = audit._run_worker("CERTUS_X", 1920, 1080)  # a row read from memory
    assert second["tabs"] == ["a", "b"]
    assert second["nested"] == {"k": [1, 2]}
    assert "added" not in second
    second["tabs"].append("spoiled too")
    second["nested"]["k"].append(7)
    third = audit._run_worker("CERTUS_X", 1920, 1080)
    assert third["tabs"] == ["a", "b"]
    assert third["nested"] == {"k": [1, 2]}


def test_fresh_measures_again_and_the_new_row_replaces_the_old_one(worker):
    audit._run_worker("CERTUS_X", 1920, 1080)
    again = audit._run_worker("CERTUS_X", 1920, 1080, fresh=True)
    assert len(worker) == 2
    assert again["n"] == 2
    assert audit._run_worker("CERTUS_X", 1920, 1080)["n"] == 2  # the next reader gets the latest measure, with no third run
    assert len(worker) == 2


def test_a_row_in_error_is_never_kept_and_the_run_exits_after_three_tries(monkeypatch):
    calls = []

    def always_failing(tag, env, width, height):
        calls.append(tag)
        return {"app": tag, "ERROR": "the window never settled"}

    monkeypatch.setattr(audit, "_run_worker_once", always_failing)
    with pytest.raises(SystemExit):
        audit._run_worker("CERTUS_X", 1920, 1080)
    assert len(calls) == 3
    assert audit._ROWS == {}


def test_a_success_after_a_failure_is_kept(monkeypatch):
    answers = [{"app": "CERTUS_X", "ERROR": "cold start"}, {"app": "CERTUS_X", "n": 2}]
    calls = []

    def flaky(tag, env, width, height):
        calls.append(tag)
        return answers.pop(0)

    monkeypatch.setattr(audit, "_run_worker_once", flaky)
    assert audit._run_worker("CERTUS_X", 1920, 1080) == {"app": "CERTUS_X", "n": 2}
    assert audit._run_worker("CERTUS_X", 1920, 1080) == {"app": "CERTUS_X", "n": 2}
    assert len(calls) == 2  # one failure, one success, and the second read costs nothing
