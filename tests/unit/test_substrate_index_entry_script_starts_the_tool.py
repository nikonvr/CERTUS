"""certus_substrate_index.py, the script the hub launches for the substrate index tool, starts it.

3f775a8 (2026-06-13, the extraction of CertusSubstratePresenter) replaced its `main()` call
with `pass`: from then on the hub's substrate index button started a process that imported the
code and exited with code 0 after about 3 s, without a window (measured 2026-09-29). The tool's
main() lives in certus.ui.certus_substrate_ui.
"""

from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_running_the_script_calls_the_tool_main(monkeypatch) -> None:
    import certus.ui.certus_substrate_ui as ui

    calls = []
    monkeypatch.setattr(ui, "main", lambda: calls.append("main"))

    runpy.run_path(str(ROOT / "certus_substrate_index.py"), run_name="__main__")

    assert calls == ["main"]
