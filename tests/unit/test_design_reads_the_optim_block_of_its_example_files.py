"""DESIGN applies the optimization settings of a file whose block is named ``optim``.

The window saves its settings under ``optimization`` and reads only that key, while every file of
example/example_design names the block ``optim``: their points per target, n100, clusters, pre-polish
and growth settings were silently dropped at load (found on 2026-10-23, reports/DESIGN_bs5050_2026-10-22).
"""

from __future__ import annotations

from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN optim block", main_windows_only=True)


def test_the_optim_block_of_the_example_reaches_the_window(qapp) -> None:
    import json

    from certus.ui.certus_design_ui import CertusDesignApp

    optim = json.loads(EXAMPLE.read_text(encoding="utf-8"))["optim"]
    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))

    assert app.n100_spin.value() == optim["n100"]
    assert app.max_clusters_spin.value() == optim["max_clusters"]
