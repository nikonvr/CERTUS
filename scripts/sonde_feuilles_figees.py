"""Do widget-level stylesheets follow the theme, or are they frozen at build time?

A stylesheet set on a widget is an f-string evaluated ONCE, while it is built.
If the window applies the persisted theme AFTER building its widgets, every such
sheet keeps the palette that happened to be loaded at import - light, since that
is the class default. The theme then switches the window sheet and the palette,
and those widget sheets keep painting light colours on a dark window.

📏 Found on the HUB's bottom bar, 2026-09-08: dark mode, and the bar still
carried the light SURFACE. This probe asks whether the motif is general.

One window per process: theme state is global, and a second window inherits what
the first left behind.

Usage: python scripts/sonde_feuilles_figees.py <MODULE> [light|dark]
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "CERTUS_HUB"
    mode = sys.argv[2] if len(sys.argv) > 2 else "dark"

    from certus.core import certus_core

    certus_core.load_theme_config = lambda: mode
    import certus.ui.certus_ui_utils as ui_utils

    ui_utils.load_theme_config = lambda: mode

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QWidget

    from certus.ui.certus_theme import CertusTheme
    from scripts.audit_ux_certus import MODULES

    app = QApplication.instance() or QApplication([])

    modname, clsname = MODULES[tag]
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1600, 1000)
    win.show()
    app.processEvents()

    # The palette actually in force once the window is up.
    live_surface = CertusTheme.SURFACE.lower()
    live_bg = getattr(CertusTheme, "BG", "") or ""
    print(f"=== {tag} @ {mode} ===")
    print(f"  palette in force: SURFACE={live_surface} TEXT={CertusTheme.TEXT}")

    # The light palette, for comparison.
    CertusTheme.configure("light")
    light_surface = CertusTheme.SURFACE.lower()
    light_border = CertusTheme.BORDER.lower()
    CertusTheme.configure(mode)

    if live_surface == light_surface:
        print("  (this run is in light mode: nothing to compare)")
        win.close()
        return 0

    frozen = []
    for w in win.findChildren(QWidget):
        sheet = w.styleSheet()
        if not sheet:
            continue
        low = sheet.lower()
        hits = [c for c in (light_surface, light_border) if c in low]
        if hits:
            frozen.append((type(w).__name__, w.objectName(), hits, len(sheet)))

    total = sum(1 for w in win.findChildren(QWidget) if w.styleSheet())
    print(f"  widget-level stylesheets: {total}")
    print(f"  carrying a LIGHT token while the window is {mode}: {len(frozen)}")
    for name, obj, hits, size in frozen[:12]:
        print(f"      {name}#{obj or '-'}  {hits}  ({size} chars)")
    if len(frozen) > 12:
        print(f"      ... and {len(frozen) - 12} more")

    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
