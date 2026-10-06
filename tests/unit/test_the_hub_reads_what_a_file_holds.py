"""The hub names the module of a file by what the file holds, and asks when it cannot tell (audit UX A04, ETAT D81).

Measured 2026-10-02, `_module_for_dropped_file` chose by substrings of the NAME and nothing else: a METAL BILAYER
configuration called `metal_bilayer_config.json` opened METAL SINGLE ("metal" was tried first), an RE configuration
called `config_RE.json` opened DESIGN (no word matched, so a design), and an RE workbook called `mesures_RE.xlsx`
opened INDEX (every workbook did).

The content decides now: the keys of a JSON configuration, the sheets of a workbook. The name settles what the content
leaves open, and the operator is asked only when two modules read the file and nothing tells them apart (the two
METAL modules write the same keys).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QInputDialog

from certus.core.certus_hub_config import script_for_name, scripts_for_config

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "example"

DESIGN, STRAT, FIELD = "CERTUS_DESIGN.py", "CERTUS_STRAT.py", "CERTUS_FIELD.py"
INDEX, SPLINE, RE = "CERTUS_INDEX.py", "CERTUS_INDEX_SPLINE.py", "CERTUS_RE.py"
SINGLE, BILAYER = "CERTUS_METAL_SINGLE.py", "CERTUS_METAL_BILAYER.py"


def _keys(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


# ---------------------------------------------------------------------------
# The rules, with no window
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("example", "expected"),
    [
        ("example_design/JSON-design-example.json", (DESIGN,)),
        ("example_design/JSON-design-oblique-example.json", (DESIGN,)),
        ("example_strat/JSON-strat-example.json", (STRAT,)),
        ("example_strat/JSON-strat-bandpass-3cav.json", (STRAT,)),
        ("example_field/test_hr_mirror.json", (FIELD,)),
        ("example_metal_single/JSON-metal-example.json", (SINGLE, BILAYER)),
        ("example_metal_bilayer/JSON-metal-bilayer-example.json", (SINGLE, BILAYER)),
    ],
)
def test_every_example_configuration_names_its_module_by_its_keys(example, expected) -> None:
    assert scripts_for_config(_keys(EXAMPLES / example)) == expected


def _configurations(folder: str, glob: str):
    return sorted((EXAMPLES / folder).glob(glob))


@pytest.mark.parametrize("path", _configurations("example_design", "*.json"), ids=lambda p: p.name)
def test_no_design_example_is_taken_for_another_module(path) -> None:
    assert scripts_for_config(_keys(path)) == (DESIGN,)


@pytest.mark.parametrize("path", _configurations("example_strat", "*.json"), ids=lambda p: p.name)
def test_every_strat_configuration_of_the_examples_is_taken_for_strat(path) -> None:
    keys = _keys(path)
    if "stack_multipliers" not in keys:
        pytest.skip("a result or a sweep, not a configuration the STRAT window saves")
    assert scripts_for_config(keys) == (STRAT,)


@pytest.mark.parametrize(
    "path", _configurations("example_metal_single", "JSON-*.json") + _configurations("example_metal_bilayer", "JSON-*.json"), ids=lambda p: p.name
)
def test_every_metal_example_is_offered_to_both_metal_modules(path) -> None:
    assert scripts_for_config(_keys(path)) == (SINGLE, BILAYER)


@pytest.mark.parametrize(
    ("keys", "expected"),
    [
        ({"re_gui": {}, "l0": 550.0}, (RE,)),
        ({"workbook_path": "x.xlsx"}, (RE,)),
        ({"thickness_min": 50.0, "thickness_max": 900.0, "model_type": "TLU"}, (INDEX,)),
        ({"knot_mode": "uniform", "knot_count": 9, "model_type": "spline"}, (SPLINE,)),
        ({"l0": 550.0}, ()),
        ({}, ()),
    ],
    ids=["re-gui", "re-workbook", "index", "spline", "l0-alone-is-not-enough", "empty"],
)
def test_the_keys_of_the_other_modules(keys, expected) -> None:
    assert scripts_for_config(keys) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("metal_bilayer_config.json", BILAYER),
        ("metal_single_config.json", SINGLE),
        ("metal_config.json", SINGLE),
        ("strat_config.json", STRAT),
        ("my_index_spline.json", SPLINE),
        ("config_RE.json", RE),
        ("mesures_RE.xlsx", RE),
        ("re.json", RE),
        ("restore.json", None),
        ("bare_stack.json", None),
        ("spectrum.csv", None),
    ],
)
def test_the_name_names_a_module_only_by_a_word(name, expected) -> None:
    assert script_for_name(name) == expected


# ---------------------------------------------------------------------------
# The hub, with real files
# ---------------------------------------------------------------------------


@pytest.fixture
def hub(qapp):
    from CERTUS_HUB import CertusHub

    window = CertusHub()
    try:
        yield window
    finally:
        window.active_processes.clear()
        window.close()


@pytest.fixture
def asked(monkeypatch):
    """The choice offered to the operator, and the answer the test gives."""
    state = {"offered": None, "answer": None}

    def fake(_parent, _title, _label, items, _current=0, _editable=False):
        state["offered"] = list(items)
        answer = state["answer"]
        return (items[answer], True) if answer is not None else ("", False)

    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(fake))
    return state


def _file(folder: Path, name: str, source: Path | None = None, text: str | None = None) -> Path:
    path = folder / name
    if source is not None:
        shutil.copyfile(source, path)
    else:
        path.write_text(text or "", encoding="utf-8")
    return path


def test_a_bilayer_configuration_called_bilayer_opens_the_bilayer_module(hub, asked, tmp_path) -> None:
    config = _file(
        tmp_path, "metal_bilayer_config.json", EXAMPLES / "example_metal_bilayer/JSON-metal-bilayer-example.json"
    )

    assert hub._module_for_dropped_file(str(config)) == BILAYER
    assert asked["offered"] is None, "the name settled it: nobody should have been asked"


def test_an_re_configuration_opens_re_not_design(hub, asked, tmp_path) -> None:
    config = _file(tmp_path, "config_RE.json", text=json.dumps({"re_gui": {"mode": "fast"}, "l0": 550.0}))

    assert hub._module_for_dropped_file(str(config)) == RE


def test_the_content_outranks_the_name(hub, asked, tmp_path) -> None:
    """A design that someone called `strat_config.json` is still a design: STRAT would refuse it."""
    config = _file(tmp_path, "strat_config.json", EXAMPLES / "example_design/JSON-design-example.json")

    assert hub._module_for_dropped_file(str(config)) == DESIGN


def test_an_re_workbook_opens_re_whatever_it_is_called(hub, asked, tmp_path) -> None:
    workbook = _file(tmp_path, "measurements_of_monday.xlsx", EXAMPLES / "example_RE/reverse_sample.xlsx")

    assert hub._module_for_dropped_file(str(workbook)) == RE


def test_a_spectrum_workbook_still_opens_index(hub, asked, tmp_path) -> None:
    workbook = _file(tmp_path, "spectrum.xlsx", EXAMPLES / "example_index/sapphirenu.xlsx")

    assert hub._module_for_dropped_file(str(workbook)) == INDEX


def test_a_metal_configuration_that_does_not_say_which_asks_and_obeys(hub, asked, tmp_path) -> None:
    config = _file(tmp_path, "config.json", EXAMPLES / "example_metal_single/JSON-metal-example.json")
    asked["answer"] = 1

    assert hub._module_for_dropped_file(str(config)) == BILAYER
    assert asked["offered"] == ["METAL SINGLE", "METAL BILAYER"]


def test_declining_the_question_opens_nothing(hub, asked, tmp_path, monkeypatch) -> None:
    from PyQt6.QtCore import QMimeData, QProcess, QUrl

    started: list[str] = []
    monkeypatch.setattr(QProcess, "start", lambda self, *_a: started.append(self.program()))
    config = _file(tmp_path, "config.json", EXAMPLES / "example_metal_single/JSON-metal-example.json")
    asked["answer"] = None

    assert hub._module_for_dropped_file(str(config)) is None

    class Drop:
        accepted = False

        def mimeData(self):
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(config))])
            return mime

        def acceptProposedAction(self):
            self.accepted = True

    hub.dropEvent(Drop())
    assert not started, "a module was started after the operator declined"


@pytest.mark.parametrize("name", ["unreadable.json", "list.json", "absent.json"])
def test_a_configuration_that_cannot_be_read_falls_back_on_its_name(hub, asked, tmp_path, name) -> None:
    contents = {"unreadable.json": "{", "list.json": "[1, 2]"}
    path = tmp_path / name
    if name in contents:
        path.write_text(contents[name], encoding="utf-8")

    assert hub._module_for_dropped_file(str(path)) == DESIGN
    assert asked["offered"] is None
