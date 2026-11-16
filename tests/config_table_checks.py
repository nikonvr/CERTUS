"""Checks shared by the configuration-table tests of the five windows (``certus/ui/certus_config_table.py``).

``editable_widgets`` lists the settings a user can edit on a window, so a test fails when one of them is neither in
the window's table nor in its list of widgets deliberately left out. ``assert_round_trip`` gives every row of a table a
value that is not the one of a new window, saves, loads into another new window and compares.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import (
    QAbstractSlider,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QRadioButton,
    QWidget,
)

from certus.ui.certus_config_table import ConfigField, read_field, resolve_widget, table_widgets

_EDITABLE = (QAbstractSpinBox, QCheckBox, QComboBox, QLineEdit, QRadioButton, QAbstractSlider)


def _is_editable(obj: object) -> bool:
    if not isinstance(obj, _EDITABLE):
        return False
    if isinstance(obj, (QLineEdit, QAbstractSpinBox)) and obj.isReadOnly():
        return False
    return True


def editable_widgets(owner: object, depth: int = 2) -> dict[int, str]:
    """The editable widgets of ``owner`` and of its CERTUS panels, ``depth`` levels down: identity -> one path to it."""
    seen: set[int] = set()
    out: dict[int, str] = {}

    def walk(obj: object, prefix: str, level: int) -> None:
        for name, value in list(vars(obj).items()):
            if not isinstance(value, QObject) or id(value) in seen:
                continue
            seen.add(id(value))
            path = prefix + name
            if _is_editable(value):
                out[id(value)] = path
            elif level < depth and isinstance(value, QWidget) and type(value).__module__.startswith("certus."):
                walk(value, path + ".", level + 1)

    seen.add(id(owner))
    walk(owner, "", 1)
    return out


def assert_every_setting_is_in_the_table(window, table, outside: dict[str, str]) -> None:
    """Every editable widget is saved by ``table`` or named in ``outside``; both name existing widgets only."""
    named = table_widgets(table) | set(outside)
    absent = sorted(p for p in named if resolve_widget(window, p) is None)
    assert not absent, f"the table names widgets the window does not have: {absent}"
    known = {id(resolve_widget(window, p)) for p in named}
    missing = sorted(path for ident, path in editable_widgets(window).items() if ident not in known)
    assert not missing, f"editable widgets neither saved nor listed as left out: {missing}"


def perturb(window, field: ConfigField) -> None:
    """Give the widget of ``field`` a value other than its present one."""
    w = resolve_widget(window, field.widget)
    if field.kind in ("float", "int"):
        v = w.value()
        step = max(w.singleStep(), 10.0 ** -w.decimals()) if hasattr(w, "decimals") else max(w.singleStep(), 1)
        w.setValue(v + step if v + step <= w.maximum() else v - step)
    elif field.kind == "bool":
        if field.off_widget and w.isChecked():
            resolve_widget(window, field.off_widget).setChecked(True)
        else:
            w.setChecked(not w.isChecked())
    elif field.kind in ("text", "data", "index"):
        assert w.count() > 1, f"{field.widget} offers a single item"
        w.setCurrentIndex((w.currentIndex() + 1) % w.count())
    else:
        w.setText(w.text() + "1")


def assert_round_trip(source, fresh, table, skip: tuple[str, ...] = ()) -> None:
    """Every row not in ``skip`` comes back from ``source`` into ``fresh`` through a saved configuration."""
    rows = [f for f in table if f.key not in skip]
    for field in rows:
        perturb(source, field)
    for field in rows:
        assert read_field(fresh, field) != read_field(source, field), f"{field.key}: no new value to carry"
    fresh._apply_config(source._collect_config())
    wrong = {f.key: (read_field(fresh, f), read_field(source, f)) for f in rows if read_field(fresh, f) != read_field(source, f)}
    assert not wrong, f"settings that did not come back (loaded, saved): {wrong}"
