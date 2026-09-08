"""Measure what the HUB documentation button actually paints, per theme.

The UX dossier records "Scientific Documentation" as rendering white on white.
``open_documentation`` hands the page to the SYSTEM browser, so the claim can
only be about the button itself - and a QSS-styled widget does not report its
colours through ``palette()``. The only honest way to know is to paint it and
read the pixels back.

⚠️ One mode per process. A window applies the PERSISTED preference while it is
being built, so calling ``CertusTheme.configure()`` beforehand does not decide
what the window renders - the preference does. The preference is faked in
memory here; nothing is written to the user's configuration.

Usage: python scripts/sonde_bouton_documentation.py [light|dark]
"""

from __future__ import annotations

import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AA_NORMAL_TEXT = 4.5
#: Below this, two colours are an anti-aliasing step of one another, not ink on paper.
INK_THRESHOLD = 1.6


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = [c / 255 for c in rgb]
    linear = [(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def dominant_colours(widget, top: int = 8):
    """Paint the widget and return its most frequent opaque colours."""
    from PyQt6.QtGui import QImage, QPainter

    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    widget.render(painter)
    painter.end()

    counter: Counter = Counter()
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() < 250:
                continue
            counter[(pixel.red(), pixel.green(), pixel.blue())] += 1
    return counter.most_common(top), sum(counter.values())


def report(widget, label: str) -> None:
    print(f"  {label}: {widget.width()}x{widget.height()}")
    colours, total = dominant_colours(widget)
    if total == 0:
        print("    NOT PAINTED - every pixel transparent")
        return

    for rgb, count in colours:
        print(f"    {_hex(rgb)}  {100.0 * count / total:5.1f} %")

    paper = colours[0][0]
    ink = next((rgb for rgb, _c in colours[1:] if contrast(rgb, paper) >= INK_THRESHOLD), None)
    if ink is None:
        print(f"    VERDICT: FLAT on {_hex(paper)} - nothing distinct enough to be text")
        return

    ratio = contrast(ink, paper)
    verdict = "readable" if ratio >= AA_NORMAL_TEXT else "BELOW AA"
    print(f"    VERDICT: ink {_hex(ink)} on paper {_hex(paper)} -> {ratio:.2f}:1  {verdict}")


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "light"

    # Fake the persisted preference BEFORE any window is built.
    from certus.core import certus_core

    certus_core.load_theme_config = lambda: mode
    import certus.ui.certus_ui_utils as ui_utils

    ui_utils.load_theme_config = lambda: mode

    from PyQt6.QtWidgets import QApplication, QPushButton

    from certus.ui.certus_theme import CertusTheme

    app = QApplication.instance() or QApplication([])

    from CERTUS_HUB import CertusHub

    win = CertusHub()
    win.resize(1400, 900)
    win.show()
    app.processEvents()

    print(f"=== {mode} ===")
    print(f"  tokens in effect: PRIMARY={CertusTheme.PRIMARY} SURFACE={CertusTheme.SURFACE}")
    report(win.btn_docs, f"btn_docs {win.btn_docs.text()!r}")

    # Contrôle négatif: a button deliberately painted white on white must be
    # reported as flat, or the probe above proves nothing.
    rigged = QPushButton("invisible", win)
    rigged.setStyleSheet("background-color: #ffffff; color: #ffffff; border: none;")
    rigged.resize(220, 40)
    report(rigged, "contrôle négatif (white on white)")

    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
