"""One declarative table per window for the settings its configuration file saves and loads back.

Each row names the JSON key, the window attribute that holds the widget (a dotted path for a widget inside a panel),
how the value is read and written, and the value saved when the window has no such widget. ``collect_table`` and
``apply_table`` read the same rows, so a setting can no longer be saved without being loaded back, or shown without
being saved: the four defects of that class found by the audit of 2026-11-15 (M-L5b, M-L6d) came from two hand-written
lists that drifted apart.

A key missing from a loaded file, or saved as ``None``, leaves its widget as it is, unless its row gives ``missing``:
the value a file without the key stands for. Such a key is written only when the value differs from it, so the files
saved before the setting existed keep their meaning.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

# How a widget value is read and written.
#   float, int : a spin box, value() / setValue()
#   bool       : a check box or radio button; ``off_widget`` is checked instead when the value is false
#   text       : a combo box by its displayed text; an unknown text leaves the combo as it is
#   loose_text : the same, but an empty text is skipped and a text differing only by case, spaces, hyphens and
#                underscores is accepted (STRAT files name materials loosely)
#   data       : a combo box by its item data; an unknown value leaves the combo as it is
#   index      : a combo box by its position
#   line       : a line edit, text() / setText()
#   choice     : a group of radio buttons, ``choices`` = ((value, widget), ...); the value of the checked one, else the
#                default; a value no button stands for checks the button of the default
KINDS = ("float", "int", "bool", "text", "loose_text", "data", "index", "line", "choice")


@dataclass(frozen=True)
class ConfigField:
    """One saved setting: its JSON key, its widget, how it is read and written, its value without the widget.

    ``off_widget``: the radio button checked when the value is false. ``applies(config)``: the row is loaded only when
    true. ``missing``: see the module. ``saved_if(window)``: the row is saved only when true.
    """

    key: str
    widget: str
    kind: str
    default: Any = None
    off_widget: str | None = None
    applies: Callable[[Mapping[str, Any]], bool] | None = None
    missing: Any = None
    saved_if: Callable[[Any], bool] | None = None
    choices: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown kind {self.kind!r} for the configuration key {self.key!r}")


def resolve_widget(owner: object, path: str) -> Any:
    """The widget at ``path`` (``"panel.spin"``, ``"widgets.l0"`` in a dict) on ``owner``, or ``None`` when one step is
    missing."""
    obj: Any = owner
    for name in path.split("."):
        obj = obj.get(name) if isinstance(obj, Mapping) else getattr(obj, name, None)
        if obj is None:
            return None
    return obj


def read_field(owner: object, field: ConfigField) -> Any:
    """The value of one row as it is saved; the row default when the window has no such widget."""
    w = resolve_widget(owner, field.widget)
    if w is None:
        return field.default
    kind = field.kind
    if kind == "choice":
        return next((v for v, path in field.choices if resolve_widget(owner, path).isChecked()), field.default)
    if kind == "float":
        return float(w.value())
    if kind == "int":
        return int(w.value())
    if kind == "bool":
        return bool(w.isChecked())
    if kind in ("text", "loose_text"):
        return w.currentText()
    if kind == "data":
        return w.currentData()
    if kind == "index":
        return int(w.currentIndex())
    return w.text()


def write_field(owner: object, field: ConfigField, value: Any) -> bool:
    """Put ``value`` into the widget of one row; ``False`` when there is no widget or the combo has no such item."""
    w = resolve_widget(owner, field.widget)
    if w is None:
        return False
    kind = field.kind
    if kind == "float":
        w.setValue(float(value))
    elif kind == "int":
        w.setValue(int(value))
    elif kind == "bool":
        w.setChecked(bool(value))
        if field.off_widget and (off := resolve_widget(owner, field.off_widget)) is not None:
            off.setChecked(not value)
    elif kind == "loose_text":
        return _set_loose_text(w, str(value))
    elif kind == "choice":
        paths = dict(field.choices)
        resolve_widget(owner, paths.get(str(value).strip().lower(), paths[field.default])).setChecked(True)
    elif kind in ("text", "data"):
        idx = w.findText(str(value)) if kind == "text" else w.findData(value)
        if idx < 0:
            return False
        w.setCurrentIndex(idx)
    elif kind == "index":
        w.setCurrentIndex(int(value))
    else:
        w.setText(str(value))
    return True


def _loose(text: str) -> str:
    return text.strip().replace("_", "-").replace(" ", "-").lower()


def _set_loose_text(combo: Any, text: str) -> bool:
    """Select ``text`` in ``combo``, or the item that differs from it only by case, spaces, hyphens and underscores."""
    target = text.strip()
    if not target:
        return False
    idx = combo.findText(target)
    if idx < 0:
        idx = next((i for i in range(combo.count()) if _loose(combo.itemText(i)) == _loose(target)), -1)
    if idx < 0:
        return False
    combo.setCurrentIndex(idx)
    return True


def collect_table(owner: object, table: Iterable[ConfigField]) -> dict[str, Any]:
    """The saved values of every row, in the order of the table; a row at its ``missing`` value is left out."""
    out: dict[str, Any] = {}
    for field in table:
        if field.saved_if is not None and not field.saved_if(owner):
            continue
        value = read_field(owner, field)
        if field.missing is not None and (value is None or value == field.missing):
            continue
        out[field.key] = value
    return out


def apply_table(owner: object, table: Iterable[ConfigField], config: Mapping[str, Any]) -> None:
    """Load every row present in ``config``, in the order of the table; a missing or ``None`` key changes nothing."""
    for field in table:
        value = config.get(field.key)
        if value is None:
            if field.missing is None:
                continue
            value = field.missing
        if field.applies is not None and not field.applies(config):
            continue
        write_field(owner, field, value)

