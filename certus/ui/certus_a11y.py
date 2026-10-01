"""CERTUS accessibility toolkit (P4).

A focused helper module that raises the accessibility (a11y) baseline of
every CERTUS window by **walking the widget tree** and filling in the
fields that Qt leaves empty by default:

- :func:`apply_accessibility_defaults(root)` gives every control that still has an
  empty name the one a screen reader should say (:func:`derive_accessible_name`: the
  label laid out next to it, the first sentence of its tooltip, its placeholder; a
  button that has a caption keeps it), ties that label to it as its buddy, and
  forces ``Qt.FocusPolicy.StrongFocus`` on inputs that expect keyboard focus.
  Never the name of the class or of the object: measured on 2026-10-01 on the
  eleven windows, the earlier pass replaced the caption of a radio button by
  ``QRadioButton`` and that of the Run button by ``Certus primary btn``.
- :func:`keep_names_current(root)` runs that pass again once the window is built and
  whenever a tab or a page is turned: tooltips and pages come after the first pass.
- :func:`compute_tab_order(widgets)` returns a consistent tab chain from
  a list of widgets so apps can call ``setTabOrder`` in a loop.
- :func:`contrast_ratio(hex_fg, hex_bg)` / :func:`passes_wcag_aa(...)` :
  pure-python WCAG 2.1 contrast computation to audit the theme palette.

Design rules
------------

- **Additive**: every helper is a no-op on widgets that already declare
  an accessible name or a tab order.
- **Safe**: a11y walks catch their own exceptions so an ill-formed
  widget cannot break the parent's ``__init__``.
- **Pure-python where possible**: contrast math is testable without Qt.
- **No Qt import at module load**: everything is lazy, keeping test
  collection fast.

Public API
----------

- :func:`apply_accessibility_defaults(root, *, label_map=None)`
- :func:`derive_accessible_name(widget, *, label_map=None)`
- :func:`adjacent_label(widget)`
- :func:`keep_names_current(root, *, label_map=None)`
- :func:`install_accessible_names(window, *, label_map=None)`
- :func:`compute_tab_order(widgets)`
- :func:`contrast_ratio(hex_fg, hex_bg)`
- :func:`passes_wcag_aa(fg, bg, *, large_text=False)`
- :func:`audit_palette(palette)` - small dict-in / report-out helper
"""

from __future__ import annotations

import html
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any, Final


# =============================================================================
# Contrast math (pure-python)
# =============================================================================


WCAG_AA_NORMAL: Final[float] = 4.5
WCAG_AA_LARGE: Final[float] = 3.0
WCAG_AAA_NORMAL: Final[float] = 7.0
WCAG_AAA_LARGE: Final[float] = 4.5


def _parse_hex(color: str) -> tuple[int, int, int]:
    """Parse a ``#RRGGBB`` or ``#RGB`` string into ``(r, g, b)`` 0-255."""
    s = str(color).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) not in (6, 8):
        raise ValueError(f"Invalid hex color: {color!r}")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return r, g, b


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def contrast_ratio(hex_fg: str, hex_bg: str) -> float:
    """Return the WCAG 2.1 contrast ratio between two hex colors.

    The ratio is in ``[1.0, 21.0]``; higher is better.
    """
    fg = _relative_luminance(_parse_hex(hex_fg))
    bg = _relative_luminance(_parse_hex(hex_bg))
    lighter = max(fg, bg)
    darker = min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def passes_wcag_aa(hex_fg: str, hex_bg: str, *, large_text: bool = False) -> bool:
    """Return ``True`` if the pair passes WCAG 2.1 AA (normal or large text)."""
    ratio = contrast_ratio(hex_fg, hex_bg)
    threshold = WCAG_AA_LARGE if large_text else WCAG_AA_NORMAL
    return ratio >= threshold


def audit_palette(palette: Mapping[str, str], *, background_key: str = "surface") -> dict[str, Any]:
    """Compute contrast ratios against ``palette[background_key]``.

    Returns a dict ``{name: {ratio, passes_aa, passes_aa_large}}`` for
    every non-background entry, plus an overall ``worst`` summary.
    """
    if background_key not in palette:
        raise KeyError(f"Background key {background_key!r} not in palette")
    bg = palette[background_key]
    report: dict[str, Any] = {}
    worst_name = None
    worst_ratio = float("inf")
    for name, fg in palette.items():
        if name == background_key:
            continue
        try:
            ratio = contrast_ratio(fg, bg)
        except ValueError:
            continue
        passes = ratio >= WCAG_AA_NORMAL
        report[name] = {
            "ratio": round(ratio, 2),
            "passes_aa": passes,
            "passes_aa_large": ratio >= WCAG_AA_LARGE,
        }
        if ratio < worst_ratio:
            worst_ratio = ratio
            worst_name = name
    report["_summary"] = {
        "background": bg,
        "worst_pair": worst_name,
        "worst_ratio": round(worst_ratio, 2) if worst_name else None,
        "pairs_tested": len(report),
    }
    return report


# =============================================================================
# Widget-tree walker (lazy Qt)
# =============================================================================


# Widget classes that should receive focus + an accessible name if empty.
_INPUT_CLASS_NAMES: Final[tuple[str, ...]] = (
    "QLineEdit",
    "QSpinBox",
    "QDoubleSpinBox",
    "QComboBox",
    "QPushButton",
    "QCheckBox",
    "QRadioButton",
    "QSlider",
    "QTextEdit",
    "QPlainTextEdit",
    "QDateEdit",
    "QTimeEdit",
    "QDateTimeEdit",
)


def _cls_name(widget) -> str:
    try:
        return widget.__class__.__name__
    except AttributeError:
        return ""


#: A letter or a digit of any alphabet: a caption that has none (``✕``, ``◐``, ``?``) says nothing to a reader.
_ALNUM: Final = re.compile(r"[^\W_]")

#: Labels that are units, not the name of the field after them (``[λ min] [ 400 ] nm [ 700 ]``).
_UNIT_LABELS: Final[frozenset[str]] = frozenset(
    {"nm", "µm", "um", "mm", "cm", "m", "deg", "°", "%", "s", "ms", "hz", "khz", "mhz", "ev", "pts", "px"}
)

#: The captions of a help button: its name is its tooltip, said as help (``?`` alone is no name).
_HELP_GLYPHS: Final[frozenset[str]] = frozenset({"?", "ⓘ", "ℹ", "❓", "❔"})

#: A full stop after these ends no sentence.
_SENTENCE_END: Final = re.compile(r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\betc\.)(?<!\bvs\.)(?<=[.!?])\s")


def _plain(text: Any) -> str:
    """The text of a label or a tooltip as a reader says it: no tags, no mnemonic ampersand, one space between words."""
    stripped = re.sub(r"<[^>]+>", " ", str(text or ""))
    stripped = re.sub(r"&(?!#?\w+;)(.)", r"\1", stripped)  # a mnemonic ampersand, not an entity (`&amp;`)
    return re.sub(r"\s+", " ", html.unescape(stripped)).strip()


def _first_sentence(text: Any, limit: int = 90) -> str:
    """The first sentence of a tooltip, at most ``limit`` characters (cut on a word)."""
    sentence = _SENTENCE_END.split(_plain(text), maxsplit=1)[0].rstrip(".")
    if len(sentence) <= limit:
        return sentence
    return sentence[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _find_owner(layout, target) -> tuple | None:
    """``(layout, index)`` of the layout that holds ``target`` (a widget or a sub-layout) directly, looking below ``layout``."""
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        if item.widget() is target or item.layout() is target:
            return layout, i
        sub = item.layout()
        hit = _find_owner(sub, target) if sub is not None else None
        if hit is not None:
            return hit
    return None


def _label_of(item) -> Any:
    """The QLabel a layout item holds, or None."""
    from PyQt6.QtWidgets import QLabel

    widget = item.widget() if item is not None else None
    return widget if isinstance(widget, QLabel) else None


def _is_caption(label) -> bool:
    """A label that names a field: it has a letter, and it is not a unit."""
    text = _plain(label.text())
    return bool(_ALNUM.search(text)) and text.lower() not in _UNIT_LABELS


def _is_help_button(widget) -> bool:
    """A button whose caption is a help glyph (``?``): it sits between a label and its field, and names neither."""
    from PyQt6.QtWidgets import QAbstractButton

    return isinstance(widget, QAbstractButton) and _plain(widget.text()) in _HELP_GLYPHS


def _beside(layout, index: int) -> Any:
    """The QLabel that captions item ``index`` of ``layout``.

    Its row's label in a form; the first item to its left in a grid (or the one above, if it is first in its row); in a
    row or a column, the item before it, past a stretch or a help button (``[label] [?] <stretch> [field]``). Whatever
    else stands there (another field) means no caption.
    """
    from PyQt6.QtWidgets import QBoxLayout, QFormLayout, QGridLayout

    if isinstance(layout, QFormLayout):
        row, role = layout.getItemPosition(index)
        if role == QFormLayout.ItemRole.LabelRole:
            return None
        return _label_of(layout.itemAt(row, QFormLayout.ItemRole.LabelRole))
    if isinstance(layout, QGridLayout):
        row, col, _rows, _cols = layout.getItemPosition(index)
        for c in range(col - 1, -1, -1):
            item = layout.itemAtPosition(row, c)
            if item is not None:
                return _label_of(item)
        return _label_of(layout.itemAtPosition(row - 1, col)) if row > 0 else None
    if isinstance(layout, QBoxLayout):
        for i in range(index - 1, -1, -1):
            item = layout.itemAt(i)
            if item is not None and (item.spacerItem() is not None or _is_help_button(item.widget())):
                continue
            return _label_of(item)
    return None

def adjacent_label(widget) -> Any:
    """The QLabel that captions ``widget`` where the interface laid it out, or None.

    A field that sits in a row layout inside a grid cell is looked for one level up, a few levels at most.
    """
    from PyQt6.QtWidgets import QLayout

    parent = widget.parentWidget()
    root = parent.layout() if parent is not None else None
    found = _find_owner(root, widget) if root is not None else None
    for _ in range(4):
        if found is None:
            return None
        layout, index = found
        label = _beside(layout, index)
        if label is not None and _is_caption(label):
            return label
        outer = layout.parent()
        found = _find_owner(outer, layout) if isinstance(outer, QLayout) else None
    return None


def _name_from_label(label, tooltip: str) -> str:
    """The label without its colon; behind a label too short to say what the field is (``T``, ``wR``), its tooltip."""
    name = _plain(label.text()).rstrip(":").strip()
    sentence = _first_sentence(tooltip)
    return f"{name}: {sentence}" if len(name) < 3 and sentence else name


def derive_accessible_name(widget, *, label_map: Mapping[str, str] | None = None) -> tuple[str, Any]:
    """``(name, label)``: what a screen reader should say for ``widget``, and the QLabel that gave it (or None).

    ``""`` when nothing the interface wrote can name it. In order: ``label_map[objectName]``; for a button, nothing if
    it has a caption (Qt reads the caption) and its tooltip, as help for a ``?``, if it has none (``✕``, ``◐``); for
    the others, the label laid out next to it, the first sentence of its tooltip, its placeholder.

    Never the name of the class (``QSpinBox``) or of the object (``certus_primary_btn``, a hook for the style sheet): a
    name that says nothing is worse than none, since it is what the reader says INSTEAD of the caption.
    """
    from PyQt6.QtWidgets import QAbstractButton

    object_name = widget.objectName() or ""
    if label_map and object_name in label_map:
        return label_map[object_name], None
    if isinstance(widget, QAbstractButton):
        caption = _plain(widget.text())
        if _ALNUM.search(caption):
            return "", None
        sentence = _first_sentence(widget.toolTip())
        return (f"Help: {sentence}" if sentence else "Help") if caption in _HELP_GLYPHS else sentence, None
    label = adjacent_label(widget)
    if label is not None:
        return _name_from_label(label, widget.toolTip()), label
    for getter in ("toolTip", "placeholderText"):
        read = getattr(widget, getter, None)
        text = _first_sentence(read()) if callable(read) else ""
        if text:
            return text, None
    return "", None

def _is_inner_editor(widget) -> bool:
    """The QLineEdit inside a spin box or an editable combo box: a part of that control, not a field."""
    from PyQt6.QtWidgets import QAbstractSpinBox, QComboBox, QLineEdit

    return isinstance(widget, QLineEdit) and isinstance(widget.parentWidget(), QAbstractSpinBox | QComboBox)


def _apply_names(planned: list[tuple]) -> int:
    """Set the names planned as ``(widget, name, label)``, and tie each label to its field.

    A label that captions several fields (``[ λ range ] [ min ] [ max ]``) names none of them: each says what its own tooltip
    says, or the label and its rank, and none becomes the label's buddy.
    """
    shared = Counter(id(label) for _widget, _name, label in planned if label is not None)
    rank: Counter = Counter()
    for widget, name, label in planned:
        crowded = label is not None and shared[id(label)] > 1
        if crowded:
            rank[id(label)] += 1
            name = _first_sentence(widget.toolTip()) or f"{name} ({rank[id(label)]})"
        widget.setAccessibleName(name)
        if label is not None and not crowded and label.buddy() is None and "&" not in label.text():
            label.setBuddy(widget)
    return len(planned)

def apply_accessibility_defaults(
    root,
    *,
    label_map: Mapping[str, str] | None = None,
    focus_policy: str = "StrongFocus",
) -> int:
    """Walk ``root`` and fill missing accessibility metadata in place.

    For every control found (button, field, combo box, slider, text area):
    - if ``accessibleName()`` is empty, give it the name :func:`derive_accessible_name` finds, and make the label that
      gave it the control's buddy (no ``&`` in it: a mnemonic would grab a key; not when the label captions several
      fields). A control nothing can name stays unnamed.
    - if ``focusPolicy()`` is ``NoFocus`` on an input-class widget, force it to
      :attr:`Qt.FocusPolicy.<focus_policy>`.

    Returns the number of controls named.
    """
    if root is None:
        return 0
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import (
            QAbstractButton,
            QAbstractSlider,
            QAbstractSpinBox,
            QComboBox,
            QLineEdit,
            QPlainTextEdit,
            QTextEdit,
            QWidget,
        )
    except ImportError:
        return 0

    fp_target = getattr(Qt.FocusPolicy, focus_policy, Qt.FocusPolicy.StrongFocus)
    nameable = (QAbstractButton, QAbstractSlider, QAbstractSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QTextEdit)
    try:
        children = root.findChildren(QWidget)
    except (AttributeError, RuntimeError, TypeError):
        return 0

    planned: list[tuple] = []
    for w in children:
        try:
            if _is_inner_editor(w):
                continue
            if isinstance(w, nameable) and not w.accessibleName().strip():
                name, label = derive_accessible_name(w, label_map=label_map)
                if name:
                    planned.append((w, name, label))
            if _cls_name(w) not in _INPUT_CLASS_NAMES:
                continue
            # Focus policy. A control that asked for NoFocus ON PURPOSE says so
            # with the certus_chrome property: help buttons, theme toggles and
            # the Save/Load/Export bar. Without this exception, this pass undid
            # step 2.23 - it restored the focus to the chrome, so Space on a
            # freshly opened window still fired an action nobody chose. Two steps
            # of the same plan pulling in opposite directions; measured
            # 2026-09-05.
            if not bool(w.property("certus_chrome")) and w.focusPolicy() == Qt.FocusPolicy.NoFocus:
                w.setFocusPolicy(fp_target)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
    try:
        return _apply_names(planned)
    except (AttributeError, RuntimeError, TypeError):
        return 0

def keep_names_current(root, *, delay_ms: int = 1500, label_map: Mapping[str, str] | None = None) -> None:
    """Run the pass again ``delay_ms`` after the window is built, and whenever a tab or a page is turned.

    The first pass runs when the window is built: its tooltips are written after it, and its pages are built when they are
    first shown. The window is held by a weak reference: a pending timer or a connected signal must not keep it alive.
    """
    import weakref

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QStackedWidget, QTabWidget

    ref = weakref.ref(root)

    def run(*_args) -> None:
        target = ref()
        if target is not None:
            apply_accessibility_defaults(target, label_map=label_map)

    QTimer.singleShot(delay_ms, run)
    for pages in root.findChildren((QTabWidget, QStackedWidget)):
        pages.currentChanged.connect(lambda *_args: QTimer.singleShot(0, run))


def install_accessible_names(window, *, label_map: Mapping[str, str] | None = None) -> int:
    """Name the controls of ``window`` now, and again once it is built and whenever a tab or a page is turned.

    The one call for a window to make at the end of its constructor: ``CertusBaseApp`` makes it in ``_finalize_init``, the
    launcher and the two utility windows (which do not inherit it) make it themselves. Returns the controls named now.
    """
    keep_names_current(window, label_map=label_map)
    return apply_accessibility_defaults(window, label_map=label_map)

def compute_tab_order(widgets: Iterable) -> list[tuple]:
    """Return a list of ``(prev, next)`` pairs suitable for ``QMainWindow.setTabOrder`` calls."""
    seq = [w for w in widgets if w is not None]
    return [(seq[i], seq[i + 1]) for i in range(len(seq) - 1)]


def apply_tab_order(parent, widgets: Iterable) -> int:
    """Apply a deterministic tab order across ``widgets``.

    Returns the number of transitions configured. Silently ignores
    missing widgets.
    """
    pairs = compute_tab_order(widgets)
    if parent is None or not pairs:
        return 0
    try:
        from PyQt6.QtWidgets import QWidget  # noqa: F401 - ensures PyQt is importable
    except ImportError:
        return 0
    applied = 0
    for prev, nxt in pairs:
        try:
            parent.setTabOrder(prev, nxt)
            applied += 1
        except (AttributeError, RuntimeError, TypeError):
            pass
    return applied


__all__ = [
    "WCAG_AAA_LARGE",
    "WCAG_AAA_NORMAL",
    "WCAG_AA_LARGE",
    "WCAG_AA_NORMAL",
    "adjacent_label",
    "apply_accessibility_defaults",
    "apply_tab_order",
    "audit_palette",
    "compute_tab_order",
    "contrast_ratio",
    "derive_accessible_name",
    "install_accessible_names",
    "keep_names_current",
    "passes_wcag_aa",
]
