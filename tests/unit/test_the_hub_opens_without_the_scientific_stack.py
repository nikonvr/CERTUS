"""The hub opens without the scientific stack (audit v2, plan S7.7).

The hub is a launcher: it draws a grid of cards and starts each module as a process of its own. It imported `certus.ui.certus_ui`, the facade of the whole interface, through
`certus_hub_widgets`, `CERTUS_HUB` itself, `CertusTheme.apply_to_app` and `build_premium_overrides` - and with it pandas, pyqtgraph, numba and the physics, which a launcher never
uses: 1 888 modules loaded, 3.0 s to open (measured by the audit, offscreen, idle), 4.6 s on a loaded machine. It now loads 318 modules and opens in 0.7 s on the same loaded machine.

What keeps it that way is pinned here, in a fresh interpreter (the only place where "was it imported?" has an answer):

    the hub starts the way `main` does (`CertusApp()` then `show_hub()`) and none of pandas, pyqtgraph, numba, openpyxl, scipy is in `sys.modules`
    `init_certus_app(plots=False, jit_warmup=False)` leaves the plots and the warm-up out, and by default does neither less nor more than it always did
    `update_global_plot_config` does nothing while pyqtgraph has not been loaded (no plot exists to theme), and does what it did once it has
    `OPENPYXL_AVAILABLE` still says whether openpyxl can be imported, without importing it
    `read_data_file_robust` of the I/O module still forwards to the reader of `certus_data`, which is loaded on the first call
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HEAVY = ("pandas", "pyqtgraph", "numba", "openpyxl", "scipy", "matplotlib")

PROBE = r"""
import json, os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, sys.argv[1])
import CERTUS_HUB as hub
manager = hub.CertusApp()
manager.show_hub()
for _ in range(10):
    manager.app.processEvents()
print(json.dumps({"loaded": sorted(m for m in HEAVY_NAMES if m in sys.modules), "modules": len(sys.modules)}), flush=True)
os._exit(0)
""".replace("HEAVY_NAMES", repr(HEAVY))


def run_probe(source: str, *args: str) -> dict:
    env = {**os.environ, "CERTUS_CONFIG_DIR": os.environ.get("TEMP", ".")}
    done = subprocess.run([sys.executable, "-c", source, str(ROOT), *args], capture_output=True, text=True, env=env, cwd=ROOT, timeout=180)
    lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
    assert lines, f"the probe printed nothing: {done.stderr[-600:]}"
    return json.loads(lines[-1])


def test_the_hub_starts_the_way_main_does_without_loading_the_scientific_stack():
    result = run_probe(PROBE)
    assert result["loaded"] == [], f"the hub loaded {result['loaded']}"
    assert result["modules"] < 700  # 318 today, 1 888 with the stack


def test_a_module_does_not_load_the_stack_just_by_importing_the_core():
    source = r"""
import json, os, sys
sys.path.insert(0, sys.argv[1])
import certus.core.certus_core as core
print(json.dumps({"loaded": sorted(m for m in HEAVY_NAMES if m in sys.modules), "available": core.OPENPYXL_AVAILABLE}), flush=True)
""".replace("HEAVY_NAMES", repr(HEAVY))
    result = run_probe(source)
    assert result["loaded"] == []
    assert result["available"] is True  # openpyxl is installed here: asked of the import system, not imported


# --- init_certus_app ------------------------------------------------------------------------------------------------------------------


@pytest.fixture
def calls(monkeypatch, qapp):
    from certus.ui import certus_ui_utils

    seen = {"plots": 0, "warmup": 0}
    monkeypatch.setattr(certus_ui_utils, "setup_pyqtgraph_defaults", lambda: seen.__setitem__("plots", seen["plots"] + 1))
    monkeypatch.setattr(certus_ui_utils, "start_jit_warmup", lambda: seen.__setitem__("warmup", seen["warmup"] + 1))
    monkeypatch.setattr(certus_ui_utils.CertusTheme, "apply_to_app", classmethod(lambda cls, app, dark_mode=None: None))
    return seen, certus_ui_utils


def test_by_default_the_application_configures_the_plots_and_starts_the_warm_up(calls, qapp):
    seen, utils = calls
    utils.init_certus_app("CERTUS Test", app=qapp)
    assert seen == {"plots": 1, "warmup": 1}


def test_the_hub_leaves_the_plots_and_the_warm_up_out(calls, qapp):
    seen, utils = calls
    utils.init_certus_app("CERTUS Hub", app=qapp, plots=False, jit_warmup=False)
    assert seen == {"plots": 0, "warmup": 0}


def test_the_two_switches_are_independent(calls, qapp):
    seen, utils = calls
    utils.init_certus_app("CERTUS Test", app=qapp, plots=False)
    assert seen == {"plots": 0, "warmup": 1}
    utils.init_certus_app("CERTUS Test", app=qapp, jit_warmup=False)
    assert seen == {"plots": 1, "warmup": 1}


def test_the_hub_asks_for_neither(calls):
    source = (ROOT / "CERTUS_HUB.py").read_text(encoding="utf-8")
    assert 'init_certus_app("CERTUS Hub", app=self.app, plots=False, jit_warmup=False)' in source


# --- update_global_plot_config ------------------------------------------------------------------------------------------------------


def test_the_global_plot_configuration_waits_for_pyqtgraph(monkeypatch):
    import pyqtgraph

    from certus.ui.certus_ui_utils import update_global_plot_config

    configured = []
    monkeypatch.setattr(pyqtgraph, "setConfigOption", lambda *args, **kwargs: configured.append(args))
    monkeypatch.delitem(sys.modules, "pyqtgraph")  # as in the hub: nothing has loaded it
    assert update_global_plot_config(True) is None
    assert configured == []  # no plot exists: nothing to configure
    assert "pyqtgraph" not in sys.modules  # and nothing imported it on the way


def test_the_global_plot_configuration_still_sets_the_colours_once_pyqtgraph_is_loaded():
    import pyqtgraph

    from certus.ui.certus_theme import CertusTheme
    from certus.ui.certus_ui_utils import update_global_plot_config

    update_global_plot_config(False)
    assert pyqtgraph.getConfigOption("background") == CertusTheme.SURFACE
    assert pyqtgraph.getConfigOption("foreground") == CertusTheme.TEXT_MAIN


# --- the reader of data files -------------------------------------------------------------------------------------------------------


def test_the_reader_of_the_io_module_forwards_to_the_reader_of_certus_data(monkeypatch):
    from certus.ui import certus_io_ui
    from certus.utils import certus_data

    seen = []

    def reader(*args, **kwargs):
        seen.append((args, kwargs))
        return "the frame"

    monkeypatch.setattr(certus_data, "read_data_file_robust", reader)
    assert certus_io_ui.read_data_file_robust("a.csv", sep=";") == "the frame"
    assert seen == [(("a.csv",), {"sep": ";"})]


def test_the_io_module_does_not_import_the_data_reader_at_the_top():
    source = (ROOT / "certus" / "ui" / "certus_io_ui.py").read_text(encoding="utf-8")
    head = source.split("def read_data_file_robust", 1)[0]
    assert "certus_data" not in head
