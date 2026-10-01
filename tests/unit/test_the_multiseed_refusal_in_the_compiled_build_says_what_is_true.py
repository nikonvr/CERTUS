"""The multi-seed search refuses to run in the compiled build, and the reason it gives is true (audit v2, S7.4; ETAT D50).

The message used to say that `scripts/` "is not bundled". Since the spec was repaired (R35) it bundles three of its modules - the tab imports two of them at
start-up - so the message was false, and a user told that a folder is missing looks for the wrong thing. What is missing is a Python interpreter: the search
runs each seed as a separate Python process, and in the compiled build `sys.executable` is the CERTUS executable.

What is pinned here:

    the compiled build refuses before any process is started, and points to the sources
    the refusal names the real reason (separate Python processes, no interpreter) and does not say that `scripts/` is not bundled while the spec bundles it
    the premise of that reason still holds: the orchestrator starts the seeds as separate processes with `subprocess.Popen`
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from certus.ui.certus_strat_multigraine_ui import interpreteur_et_script

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "certus_hub.spec"
ORCHESTRATOR = ROOT / "scripts" / "orchestre_multigraine.py"


@pytest.fixture
def compiled(monkeypatch):
    """The process is the compiled build: PyInstaller sets `sys.frozen`, and `sys.executable` is the executable."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(ROOT / "dist" / "CERTUS_HUB" / "CERTUS_HUB.exe"))


def test_the_compiled_build_refuses_before_starting_anything(compiled):
    interpreter, reason = interpreteur_et_script()
    assert interpreter is None
    assert reason


def test_the_refusal_points_to_the_sources(compiled):
    _, reason = interpreteur_et_script()
    assert "COMPILED" in reason
    assert "sources" in reason


def test_the_refusal_names_the_missing_interpreter(compiled):
    _, reason = interpreteur_et_script()
    assert "separate Python process" in reason
    assert "interpreter" in reason


def test_the_refusal_does_not_say_that_scripts_are_not_bundled_while_the_spec_bundles_them(compiled):
    spec = SPEC.read_text(encoding="utf-8")
    assert '("scripts/orchestre_multigraine.py", "scripts")' in spec  # the premise: the spec does bundle it
    _, reason = interpreteur_et_script()
    assert "not bundled" not in reason


def test_the_reason_holds_the_orchestrator_starts_each_seed_as_a_separate_process():
    source = ORCHESTRATOR.read_text(encoding="utf-8")
    assert "subprocess.Popen(" in source
    assert '"scripts/probe_blocs_vs_plantage.py"' in source  # the seed is a script run by an interpreter, not a function called in-process


def test_from_the_sources_the_search_starts_with_the_interpreter_in_use(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    interpreter, reason = interpreteur_et_script()
    assert interpreter == sys.executable
    assert reason == ""
