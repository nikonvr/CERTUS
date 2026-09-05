"""Guards against horizontal scrollbars in the control panels of the 8 suite modules."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MARKER = "__CERTUS_HSCROLL_TEST__"

SPLITTER_APPS = [
    ("certus.ui.certus_design_ui", "CertusDesignApp"),
    ("certus.ui.certus_strat_ui", "CertusStratApp"),
    ("CERTUS_RE", "CertusREApp"),
    ("certus.ui.certus_index_ui", "CertusIndexApp"),
    ("certus.ui.certus_index_spline_ui", "CertusIndexSplineApp"),
    ("certus.ui.certus_field_ui", "CertusFieldApp"),
    ("CERTUS_METAL_SINGLE", "CertusMetalSingleApp"),
    ("CERTUS_METAL_BILAYER", "CertusMetalBilayerApp"),
]


def _worker_main(mod_path: str, cls_name: str, width: int, height: int) -> None:
    sys.path.insert(0, REPO_ROOT)
    # Isolate QSettings before any certus module is imported
    import PyQt6.QtCore as qtcore

    tmp = tempfile.mkdtemp(prefix="certus_hs_qs_")
    original = qtcore.QSettings

    class _Iso(original):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            if len(a) == 2 and all(isinstance(x, str) for x in a):
                super().__init__(os.path.join(tmp, f"{a[0]}__{a[1]}.ini"), original.Format.IniFormat)
            else:
                super().__init__(*a, **k)

    qtcore.QSettings = _Iso

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QScrollArea, QSplitter

    app = QApplication.instance() or QApplication(sys.argv[:1])
    cls = getattr(__import__(mod_path, fromlist=[cls_name]), cls_name)
    win = cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(width, height)
    win.show()

    deadline = time.monotonic() + 1.5
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
    hscroll_px = 0
    left = split.widget(0) if split is not None else None
    if left is not None:
        for sa in left.findChildren(QScrollArea):
            # A page that was never shown keeps Qt's default 640x480 geometry and
            # reports a huge overflow it does not have. Measured 2026-09-04:
            # that false positive credited INDEX_SPLINE with 143 clipped px.
            if not sa.isVisible():
                continue
            hbar = sa.horizontalScrollBar()
            if hbar is None:
                continue
            # A panel hides content two ways: a visible scrollbar, or
            # ScrollBarAlwaysOff with content wider than the viewport. The second
            # is worse - nothing on screen says the content exists. Measured
            # 2026-09-04 at 1366x768: METAL_SINGLE clipped 143 px and
            # METAL_BILAYER 24 px while this guard, testing isVisible(),
            # reported 0.
            if hbar.maximum() > 0:
                hscroll_px = max(hscroll_px, int(hbar.maximum()))
    win.close()
    print(MARKER + json.dumps({"hscroll_px": hscroll_px}))


@pytest.mark.parametrize("mod_path,cls_name", SPLITTER_APPS)
@pytest.mark.parametrize("size", [(1920, 1080), (1366, 768)])
def test_control_panel_never_scrolls_sideways(mod_path: str, cls_name: str, size: tuple[int, int], request) -> None:
    """Part of a control panel must never be unreachable without scrolling sideways."""
    w, h = size
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("QT_QPA_PLATFORM", None)

    proc = subprocess.run(
        [
            sys.executable,
            os.path.abspath(__file__),
            "--worker",
            mod_path,
            cls_name,
            str(w),
            str(h),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        encoding="utf-8",
        errors="replace",
    )
    hit = [x for x in (proc.stdout or "").splitlines() if x.startswith(MARKER)]
    assert hit, f"Worker crashed for {cls_name} @ {size}:\n{proc.stderr}"
    data = json.loads(hit[0][len(MARKER) :])
    assert data["hscroll_px"] == 0, f"{cls_name} @ {size}: {data['hscroll_px']} px du panneau sont hors champ"


if __name__ == "__main__":
    if len(sys.argv) >= 6 and sys.argv[1] == "--worker":
        _worker_main(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]))
        sys.exit(0)
