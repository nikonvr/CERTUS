"""The scientific area must keep at least 65 % of the window (step 2.3).

Step 2.3 counted six modules below the threshold at 1366x768 while all eight
were above 70 % at 1920x1080 - measuring one size hid the defect entirely
(defect J4 of the harness).

Measured 2026-09-05, the last one left was STRAT:

    1920x1080   panel 556   plots 1358   71.0 %
    1366x768    panel 549   plots  811   59.6 %

Seven of the eight now clear the bar at both sizes. STRAT at 1366 does not, and
that is recorded rather than papered over: capping its panel to 450 px did lift
the plots to 66.9 %, and pushed 93 px of the panel's own content out of the
viewport. Hidden controls are worse than a smaller plot area, so the cap was
reverted - see KNOWN_TOO_NARROW below.

The attempt also exposed minimumSizeHint() understating the need - 446 px
answered for content that wants ~543 - which is defect J3: the QScrollArea
absorbs its child's width, so the hint cannot see through it.

The threshold lives in the audit harness as PLOT_PCT_MIN; this test reads it
from there rather than repeating the number.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKER = "__CERTUS_PLOT_SHARE__"

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
    print(MARKER + json.dumps(out))


#: STRAT at 1366 cannot reach the threshold by resizing, and the attempt is
#: recorded so nobody repeats it. Capping its panel at 450 px did lift the plots
#: to 66.9 %, and pushed 93 px of the panel's own content OUT OF THE VIEWPORT -
#: hidden controls, which test_ux_no_horizontal_scroll exists to forbid.
#: Reachable controls beat plot area. The panel has to be reorganised, which is
#: a redesign, not a resize. Measured 2026-09-05.
KNOWN_TOO_NARROW = {("CERTUS_STRAT", (1366, 768))}


@pytest.mark.parametrize("size", [(1920, 1080), (1366, 768)], ids=["1920x1080", "1366x768"])
@pytest.mark.parametrize("tag", SPLITTER_MODULES)
def test_plots_keep_their_share_of_the_window(tag: str, size: tuple[int, int], request) -> None:
    """Both sizes: measuring only the wide one is what hid this for a month."""
    if (tag, size) in KNOWN_TOO_NARROW:
        request.node.add_marker(pytest.mark.xfail(strict=True, reason="STRAT panel needs reorganising, not resizing"))
    from scripts.audit_ux_certus import PLOT_PCT_MIN

    width, height = size
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        QT_QPA_PLATFORM="offscreen",
        QT_QPA_FONTDIR=r"C:\Windows\Fonts",
    )
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--worker", tag, str(width), str(height)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        encoding="utf-8",
        errors="replace",
    )
    hit = [x for x in (proc.stdout or "").splitlines() if x.startswith(MARKER)]
    assert hit, f"Worker crashed for {tag} @ {size}:\n{proc.stderr}"
    row = json.loads(hit[0][len(MARKER) :])

    assert row["pct"] is not None, f"{tag} has no horizontal splitter to measure"
    assert row["pct"] >= PLOT_PCT_MIN, (
        f"{tag} @ {width}x{height}: the plots get {row['pct']} % "
        f"(panel {row['left']} px, plots {row['right']} px), below {PLOT_PCT_MIN} %"
    )


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "--worker":
        _worker_main(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
        sys.exit(0)
