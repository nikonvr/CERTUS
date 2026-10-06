"""The scientific area must keep at least 65 % of the window (step 2.3).

Step 2.3 counted six modules below the threshold at 1366x768 while all eight
were above 70 % at 1920x1080 - measuring one size hid the defect entirely
(defect J4 of the harness).

Measured 2026-09-05, the last one left was STRAT:

    1920x1080   panel 556   plots 1358   71.0 %
    1366x768    panel 549   plots  811   59.6 %

Seven of the eight cleared the bar at both sizes. STRAT at 1366 did not, and that
was recorded rather than papered over: capping its panel to 450 px did lift the
plots to 66.9 %, and pushed 93 px of the panel's own content out of the viewport.
Hidden controls are worse than a smaller plot area, so the cap was reverted.

The attempt also exposed minimumSizeHint() understating the need - 446 px
answered for content that wants ~543 - which is defect J3: the QScrollArea
absorbs its child's width, so the hint cannot see through it.

Measured 2026-10-02, STRAT clears the bar at 1366 too (67.2 %, panel 446 px) once
its panel was reorganised, as this module said it had to be: the "Design" page
laid its table (135 px, fixed) beside a 300 px grid of buttons and asked 525 px;
the table now sits under the buttons. KNOWN_TOO_NARROW is empty: the strict
xfail it carried for STRAT failed the day STRAT passed, which is its job.

The threshold lives in the audit harness as PLOT_PCT_MIN; this test reads it
from there rather than repeating the number.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKER = "__CERTUS_PLOT_SHARE__"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ux_worker import run_ux_worker  # noqa: E402

SPLITTER_MODULES = [
    "CERTUS_DESIGN",
    "CERTUS_STRAT",
    "CERTUS_RE",
    "CERTUS_INDEX",
    "CERTUS_INDEX_SPLINE",
    "CERTUS_FIELD",
    "CERTUS_METAL_SINGLE",
    "CERTUS_METAL_BILAYER",
]


def _worker_main(tag: str, width: int, height: int) -> None:
    import time

    sys.path.insert(0, str(ROOT))
    import PyQt6.QtCore as qtcore

    tmp = tempfile.mkdtemp(prefix="certus_share_qs_")
    original = qtcore.QSettings

    class _Iso(original):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            if len(a) == 2 and all(isinstance(x, str) for x in a):
                super().__init__(os.path.join(tmp, f"{a[0]}__{a[1]}.ini"), original.Format.IniFormat)
            else:
                super().__init__(*a, **k)

    qtcore.QSettings = _Iso

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QSplitter

    from scripts.audit_ux_certus import MODULES

    modname, clsname = MODULES[tag]
    app = QApplication.instance() or QApplication(sys.argv[:1])
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(width, height)
    win.show()

    deadline = time.monotonic() + 2.5
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()

    split = win.centralWidget()
    if not isinstance(split, QSplitter):
        split = next(
            (s for s in win.findChildren(QSplitter) if s.orientation() == Qt.Orientation.Horizontal and s.count() >= 2),
            None,
        )
    out = {"pct": None}
    if split is not None:
        left, right = split.widget(0), split.widget(1)
        total = left.width() + right.width()
        if total:
            out = {"pct": round(100.0 * right.width() / total, 1), "left": left.width(), "right": right.width()}
    win.close()
    # D23: the native abort (0xC0000005) came after this line, while the return freed the locals (the
    # QApplication before the window) or during interpreter teardown; the marker, still in the pipe buffer,
    # was lost with it. Flush it, then leave without the teardown: it is not what this worker measures.
    print(MARKER + json.dumps(out), flush=True)
    os._exit(0)


#: (module, size) pairs known to be under the threshold: each carries a strict
#: xfail, so that the day one passes the test fails and the entry is removed.
#: Empty since 2026-10-02 (STRAT left it by being reorganised, see the docstring).
KNOWN_TOO_NARROW: set[tuple[str, tuple[int, int]]] = set()


@pytest.mark.parametrize("size", [(1920, 1080), (1366, 768)], ids=["1920x1080", "1366x768"])
@pytest.mark.parametrize("tag", SPLITTER_MODULES)
def test_plots_keep_their_share_of_the_window(tag: str, size: tuple[int, int], request) -> None:
    """Both sizes: measuring only the wide one is what hid this for a month."""
    if (tag, size) in KNOWN_TOO_NARROW:
        request.node.add_marker(pytest.mark.xfail(strict=True, reason="known to be under the plot-area threshold"))
    from scripts.audit_ux_certus import PLOT_PCT_MIN

    width, height = size
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        QT_QPA_PLATFORM="offscreen",
        QT_QPA_FONTDIR=r"C:\Windows\Fonts",
    )
    row = run_ux_worker(
        [sys.executable, os.path.abspath(__file__), "--worker", tag, str(width), str(height)],
        MARKER,
        context=f"{tag} @ {size}",
        env=env,
        cwd=str(ROOT),
    )

    assert row["pct"] is not None, f"{tag} has no horizontal splitter to measure"
    assert row["pct"] >= PLOT_PCT_MIN, (
        f"{tag} @ {width}x{height}: the plots get {row['pct']} % "
        f"(panel {row['left']} px, plots {row['right']} px), below {PLOT_PCT_MIN} %"
    )


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "--worker":
        _worker_main(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
        sys.exit(0)
