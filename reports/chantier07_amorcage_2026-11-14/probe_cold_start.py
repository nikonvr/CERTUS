"""Cold start of the five threaded-warm-up windows, one fresh process and one empty Numba cache each.

    python reports/chantier07_amorcage_2026-11-14/probe_cold_start.py TREE [TREE ...]

For each source tree (a checkout or a `git archive` of one commit) and each window, a child process points TMP and
TEMP at a new empty directory, so `numba_cache_dir()` is empty, builds the window offscreen as its entry point does,
then runs the Qt event loop until the warm-up has answered. It prints one `COLD=` JSON line per window: the tree that
`import certus` resolved to, the status texts in order, the ready/error slot calls, `numba_ready`, the kernels whose
dispatcher holds a compiled signature, and the seconds from construction to the answer.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WINDOWS = {
    "INDEX": ("certus.ui.certus_index_ui", "CertusIndexApp", "lbl_status",
              [("certus.ui.certus_index_ui_worker", "_optimize_all_points_batch"),
               ("certus.ui.certus_index_ui_worker", "calculate_bare_substrate_R_absorbing")]),
    "INDEX_SPLINE": ("certus.ui.certus_index_spline_ui", "CertusIndexSplineApp", "lbl_status", []),
    "METAL_SINGLE": ("certus.ui.certus_metal_single_gui", "CertusMetalSingleApp", "status_label",
                     [("certus.ui.certus_metal_single_gui", "calculate_RTRback_incoherent_vectorized")]),
    "METAL_BILAYER": ("certus.ui.certus_metal_bilayer_gui", "CertusMetalBilayerApp", "status_label",
                      [("certus.core._certus_physics_impl", "calculate_reflectance_bilayer_vectorized"),
                       ("certus.ui.certus_metal_bilayer_gui", "get_nk_si")]),
    "STRAT": ("certus.ui.certus_strat_ui", "CertusStratApp", "status_label",
              [("certus.ui.certus_strat_ui_worker", "simulate_growth_kernel"),
               ("certus.ui.certus_strat_ui_worker", "validate_wavelengths_batch")]),
}
WARMING = "System warming up (compiling JIT)..."


def child(tree: str, name: str) -> None:
    import importlib

    sys.path.insert(0, tree)
    os.chdir(tree)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from certus.core.certus_core import configure_numba_env, numba_cache_dir

    configure_numba_env()
    cache_files_before = sum(1 for _ in Path(numba_cache_dir()).rglob("*") if _.is_file())
    from PyQt6.QtWidgets import QApplication

    import certus
    from certus.ui.certus_base_app import CertusBaseApp

    CertusBaseApp._maybe_run_first_time_tour = lambda self: None  # as tests/conftest.py
    module, cls_name, label_attr, kernels = WINDOWS[name]
    cls = getattr(importlib.import_module(module), cls_name)
    calls: list[str] = []
    for slot in ("_on_numba_ready_ui", "_on_numba_error_ui"):
        original = getattr(cls, slot)

        def wrapper(self, _o=original, _s=slot):
            calls.append(_s)
            return _o(self)

        setattr(cls, slot, wrapper)
    app = QApplication([])
    t0 = time.perf_counter()
    win = cls()
    texts: list[str] = []
    answered = None
    while time.perf_counter() - t0 < 900:
        app.processEvents()
        label = getattr(win, label_attr, None)
        text = label.text() if label is not None else None
        if not texts or texts[-1] != text:
            texts.append(text)
        if calls and answered is None:
            answered = time.perf_counter() - t0
        if answered is not None and time.perf_counter() - t0 > answered + 1.0:
            break
        time.sleep(0.01)
    compiled = {
        f"{m.rsplit('.', 1)[-1]}.{k}": len(getattr(importlib.import_module(m), k).signatures) for m, k in kernels
    }
    print("COLD=" + json.dumps({
        "window": name,
        "certus": str(Path(certus.__path__[0]).parent),
        "cache_files_before": cache_files_before,
        "cache_files_after": sum(1 for _ in Path(numba_cache_dir()).rglob("*") if _.is_file()),
        "cache_dir": numba_cache_dir(),
        "texts": texts,
        "slot_calls": calls,
        "numba_ready": getattr(win, "numba_ready", None),
        "compiled_signatures": compiled,
        "seconds_to_answer": None if answered is None else round(answered, 2),
    }, ensure_ascii=False), flush=True)
    os._exit(0)  # no closeEvent: nothing persisted, no teardown order to fight


def main(trees: list[str]) -> None:
    for tree in trees:
        for name in WINDOWS:
            with tempfile.TemporaryDirectory(prefix="c07cold_") as tmp:
                env = dict(os.environ, TMP=tmp, TEMP=tmp, PYTHONDONTWRITEBYTECODE="1")
                env.pop("NUMBA_CACHE_DIR", None)
                env.pop("_CERTUS_NUMBA_CONFIGURED", None)
                out = subprocess.run([sys.executable, __file__, "--child", tree, name], env=env,
                                     capture_output=True, text=True, encoding="utf-8", timeout=1200)
                lines = [x for x in out.stdout.splitlines() if x.startswith("COLD=")]
                print(lines[-1] if lines else f"COLD_FAILED {name} rc={out.returncode} {out.stderr[-800:]}", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--child":
        child(sys.argv[2], sys.argv[3])
    else:
        main(sys.argv[1:])
