"""One-shot UX probe: dump left-panel widget geometry for CERTUS_METAL_SINGLE.

Temporary diagnostic script. Runs on the real Windows platform plugin with
WA_DontShowOnScreen so no window pops up. Not part of the test suite.
"""

import sys
import time

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QSplitter

import importlib

app = QApplication.instance() or QApplication(sys.argv[:1])
mod = importlib.import_module("CERTUS_METAL_SINGLE")
win = mod.CertusMetalSingleApp()
win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
win.resize(1920, 1080)
win.show()

deadline = time.monotonic() + 3.0
while time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.02)

split = win.centralWidget()
left = split.widget(0)
print("SPLIT SIZES", split.sizes())
print("LEFT", left.width(), left.height(), "minhint", left.minimumSizeHint().width())


def walk(w, depth=0):
    if depth > 9:
        return
    for c in w.children():
        if not hasattr(c, "geometry") or not hasattr(c, "isVisible"):
            continue
        g = c.geometry()
        txt = ""
        for attr in ("title", "text"):
            f = getattr(c, attr, None)
            if callable(f):
                try:
                    txt = str(f())[:40]
                except Exception:
                    txt = ""
                if txt:
                    break
        print(
            "  " * depth,
            type(c).__name__,
            c.objectName(),
            repr(txt),
            f"g=({g.x()},{g.y()},{g.width()}x{g.height()})",
            "vis" if c.isVisible() else "HIDDEN",
        )
        walk(c, depth + 1)


walk(left)
print("--- params_widget ---")
pw = getattr(win, "params_widget", None)
if pw is not None:
    print("params_widget geom", pw.geometry(), pw.isVisible(), pw.sizeHint())
    lay = pw.layout()
    print("layout count", lay.count())
    for i in range(lay.count()):
        it = lay.itemAt(i)
        w = it.widget()
        print(i, type(w).__name__ if w else None, it.geometry(), w.isVisible() if w else None)
