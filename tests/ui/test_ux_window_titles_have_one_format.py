"""Every window of the suite is titled the same way: `CERTUS-MODULE — what the module does`.

Measured on 2026-11-12, one process per window (audit of the interface, A2, A3, B8; road map U2):

    CERTUS-DESIGN  Optical Filter Design & Optimization
    CERTUS_INDEX_SPLINE  CERTUS  Index Spline Optimization
    CERTUS_RE  CERTUS  Reverse Engineering
    CERTUS  Calculated Error Reduction Through Unbiased Simulation            (METAL SINGLE)
    CERTUS-METAL-BILAYER  Calculated Error Reduction Through Unbiased Simulation
    CERTUS-HUB - Calculated Error Reduction Through Unbiased Simulation

Two spaces where a separator was removed; the name of the program written with underscores, or twice, or not at all;
the two METAL windows carrying the motto of the suite instead of what they do, because they receive their title after
the base class has set the one of the window. In the task bar, METAL SINGLE was `CERTUS`.

The windows are built in a fresh interpreter each: importing the nine of them here would leave their modules, and what
these patch at import, in the interpreter of the other tests.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FORMAT = re.compile(r"^CERTUS-[A-Z]+(?:-[A-Z]+)* — \S(?:.*\S)?$")
MOTTO = "Calculated Error Reduction Through Unbiased Simulation"

SWEEP = r"""
import importlib, importlib.util, json, os, sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("certus_scripts_refactor_guard", os.path.join("scripts", "refactor_guard.py"))
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
spec.loader.exec_module(guard)
if len(sys.argv) == 1:
    print("WINDOWS=" + json.dumps(list(guard.WINDOWS)), flush=True)
else:
    from PyQt6.QtWidgets import QApplication

    application = QApplication([])
    from certus.ui.certus_base_app import CertusBaseApp

    CertusBaseApp._maybe_run_first_time_tour = lambda self: None
    module, _, name = sys.argv[1].partition(":")
    window = getattr(importlib.import_module(module), name)()
    print("TITLE=" + json.dumps(window.windowTitle()), flush=True)
    os._exit(0)
"""


def run(*arguments: str) -> str:
    out = subprocess.run([sys.executable, "-c", SWEEP, *arguments], capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=600)
    [line] = [x for x in out.stdout.splitlines() if x.startswith(("WINDOWS=", "TITLE="))] or [f"ERROR={out.stderr[-800:]}"]
    assert not line.startswith("ERROR="), line
    return line.partition("=")[2]


@pytest.fixture(scope="module")
def titles() -> dict[str, str]:
    return {window: json.loads(run(window)) for window in json.loads(run())}


def test_the_nine_windows_are_measured(titles) -> None:
    assert len(titles) == 9


def test_every_title_is_the_name_of_the_program_a_dash_and_what_it_does(titles) -> None:
    assert {window: title for window, title in titles.items() if not FORMAT.fullmatch(title)} == {}


def test_no_title_has_two_spaces_an_underscore_or_the_name_twice(titles) -> None:
    odd = {w: t for w, t in titles.items() if "  " in t or "_" in t or t.count("CERTUS") != 1}
    assert odd == {}


def test_only_the_hub_carries_the_motto_of_the_suite(titles) -> None:
    assert [window for window, title in titles.items() if MOTTO in title] == ["CERTUS_HUB:CertusHub"]


def test_no_two_windows_share_a_title(titles) -> None:
    assert len(set(titles.values())) == len(titles)
