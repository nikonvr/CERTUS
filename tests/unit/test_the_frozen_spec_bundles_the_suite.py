"""The frozen build carries the whole suite: every module, the data, and a layout the code can read.

`certus_hub.spec` froze `CERTUS_HUB.py` alone, as one file, with `hiddenimports=[]` and two icons as
its only data. The ten modules were not in it, nor the `certus` package (implicit namespace
packages, which a static analysis does not reliably follow) nor the pages, the materials database or
the examples the code reads through `get_resource_path`: a frozen hub could not start any module.

PyInstaller is not run here (a build takes minutes and PyInstaller is not a test dependency): the
spec is read with stand-ins for its four build steps, and what it hands to them is checked.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "certus_hub.spec"

#: State and outputs the application writes next to itself: the build must not carry the copies
#: of the developer.
WRITTEN_AT_RUN_TIME = {"reports", "certus_theme.json", "certus_export.json"}

#: What the frozen suite needs next to its executable, whatever the literals of the code say
#: (these are built with `Path(...) / ...`, which a search for literals does not see).
NEEDED = (
    "certus.ico",
    "certus.svg",
    "data/materials_v1.json",
    "pages/CERTUS_HUB.html",
    "pages/CERTUS_DESIGN.html",
    "example/database_index/indices.xlsx",
    "example/sapphire fresnel.xlsx",
    # Loaded BY PATH by `_certus_physics_impl` when the package import cycles (a module that imports
    # it before `certus_physics`, METAL_SINGLE): CERTUS_METAL_SINGLE could not start without it.
    "certus_physics/structures.py",
)


@pytest.fixture
def frozen(monkeypatch):
    """What `certus_hub.spec` hands to Analysis, PYZ, EXE and COLLECT."""
    calls: dict[str, tuple[tuple, dict]] = {}

    def stage(name):
        def call(*args, **kwargs):
            calls[name] = (args, kwargs)
            return SimpleNamespace(pure=[], binaries=[], datas=[], scripts=[])

        return call

    scope = {"__name__": "certus_hub_spec", "SPECPATH": str(ROOT)}
    scope.update({name: stage(name) for name in ("Analysis", "PYZ", "EXE", "COLLECT")})
    monkeypatch.setattr(sys, "path", list(sys.path))  # the spec puts the repository first
    exec(compile(SPEC.read_text(encoding="utf-8"), str(SPEC), "exec"), scope)
    return SimpleNamespace(
        analysis=calls["Analysis"][1],
        scripts=calls["Analysis"][0][0],
        exe=calls["EXE"][1],
        collect=calls["COLLECT"][1],
    )


def test_the_build_starts_from_the_frozen_entry(frozen) -> None:
    assert [Path(s) for s in frozen.scripts] == [ROOT / "tools" / "frozen_entry.py"]
    assert Path(frozen.scripts[0]).is_file()


def test_the_entry_script_does_not_shadow_a_module_of_the_catalog(frozen) -> None:
    # PyInstaller searches the folder of its entry script FIRST. With the entry in `certus/core/`,
    # `--run-module certus_substrate_index` ran `certus/core/certus_substrate_index.py`, a library
    # module, instead of the root script of that name: it did nothing and exited with code 0.
    from certus.core.certus_hub_config import HUB_APP_CATALOG

    folder = Path(frozen.scripts[0]).parent
    stems = {Path(item["script"]).stem for item in HUB_APP_CATALOG}

    assert {p.stem for p in folder.glob("*.py")} & stems == set()
    assert not (ROOT / "certus" / "core").samefile(folder)


def _modules_under(package: str) -> set[str]:
    names = set()
    for path in (ROOT / package).rglob("*.py"):
        parts = path.relative_to(ROOT).with_suffix("").parts
        names.add(".".join(parts[:-1] if parts[-1] == "__init__" else parts))
    return names


def test_every_module_of_the_suite_is_a_hidden_import(frozen) -> None:
    from certus.core.certus_hub_config import HUB_APP_CATALOG

    listed = set(frozen.analysis["hiddenimports"])
    expected = _modules_under("certus") | _modules_under("certus_physics")
    expected |= {"CERTUS_HUB"} | {Path(item["script"]).stem for item in HUB_APP_CATALOG}

    assert sorted(expected - listed) == []
    # Anchors that do not depend on how the list is computed.
    for name in ("certus.core.certus_core", "certus.ui.certus_design_ui", "certus_physics.structures",
                 "CERTUS_HUB", "CERTUS_DESIGN", "certus_substrate_index"):
        assert name in listed


def _landing_of(resource: str, datas) -> str | None:
    """Where `resource` (relative to the repository) lands next to the executable, if bundled."""
    target = Path(resource)
    for source, destination in datas:
        source = Path(source)
        source = source.relative_to(ROOT) if source.is_absolute() else source
        if target == source:
            return (Path(destination) / source.name).as_posix()
        if source in target.parents:  # a folder: its contents go into `destination`
            return (Path(destination) / target.relative_to(source)).as_posix()
    return None


def _resources_asked_of_get_resource_path() -> set[str]:
    """The literals the code hands to `get_resource_path` and that name a file or folder of the repository."""
    asked = set()
    sources = [*(ROOT / "certus").rglob("*.py"), *ROOT.glob("*.py")]
    for path in sources:
        for match in re.finditer(r"get_resource_path\(\s*([\"'])([^\"']+)\1\s*\)", path.read_text(encoding="utf-8")):
            literal = match.group(2)
            if literal not in (".", "") and (ROOT / literal).exists():
                asked.add(Path(literal).as_posix())
    return asked - WRITTEN_AT_RUN_TIME


def test_the_data_the_code_reads_land_where_the_code_looks_for_them(frozen) -> None:
    datas = frozen.analysis["datas"]
    resources = sorted(set(NEEDED) | _resources_asked_of_get_resource_path())

    assert resources, "no resource found: the search itself is broken"
    for resource in resources:
        assert (ROOT / resource).exists(), f"{resource}: not in the repository"
        assert _landing_of(resource, datas) == resource, f"{resource} is not bundled at its own place"


def _module_level_imports(path: Path) -> set[str]:
    """The top-level names that `path` imports when it starts (module level, under `try` and `if` too)."""

    def imports(body):
        for node in body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                yield node
            elif isinstance(node, (ast.Try, ast.If, ast.With)):
                for block in (node.body, getattr(node, "orelse", []), getattr(node, "finalbody", [])):
                    yield from imports(block)
                for handler in getattr(node, "handlers", []):
                    yield from imports(handler.body)

    names: set[str] = set()
    for node in imports(ast.parse(path.read_text(encoding="utf-8")).body):
        if isinstance(node, ast.ImportFrom):
            names |= {node.module.split(".")[0]} if node.level == 0 and node.module else set()
        else:
            names |= {alias.name.split(".")[0] for alias in node.names}
    return names


def _scripts_imported_when_the_package_starts() -> set[str]:
    """`scripts/` files that a module of the suite imports at module level (so at start-up), and, since a
    script that is bundled starts too, the ones THEY import in turn."""
    scripts = {p.stem for p in (ROOT / "scripts").glob("*.py")}

    found: set[str] = set()
    for path in [*(ROOT / "certus").rglob("*.py"), *(ROOT / "certus_physics").rglob("*.py"), *ROOT.glob("*.py")]:
        found |= _module_level_imports(path) & scripts
    pending = set(found)
    while pending:
        more = (_module_level_imports(ROOT / "scripts" / f"{pending.pop()}.py") & scripts) - found
        found |= more
        pending |= more
    return {f"scripts/{name}.py" for name in found}


def test_the_scripts_a_module_imports_at_start_up_are_bundled(frozen) -> None:
    # The multi-seed tab of STRAT does `from orchestre_multigraine import ...` when STRAT starts:
    # with `scripts/` missing from the build, CERTUS_STRAT could not start.
    imported = _scripts_imported_when_the_package_starts()

    assert "scripts/orchestre_multigraine.py" in imported, "the search for these imports is broken"
    # `probe_blocs_vs_plantage` imports `_artefact` (its provenance) when it starts: a build that carried the
    # first and not the second ended CERTUS_STRAT with "No module named '_artefact'" (release check, 2026-09-30).
    assert "scripts/_artefact.py" in imported, "what a bundled script imports is not followed"
    for script in sorted(imported):
        assert _landing_of(script, frozen.analysis["datas"]) == script, f"{script} is imported at start-up"


def test_the_developer_state_is_not_bundled(frozen) -> None:
    for resource in WRITTEN_AT_RUN_TIME:
        assert _landing_of(resource, frozen.analysis["datas"]) is None, f"{resource} is written at run time"


def test_the_layout_is_one_folder_with_the_data_next_to_the_executable(frozen) -> None:
    # `get_resource_path` reads the folder of `sys.executable`: PyInstaller 6 would put the data in
    # `_internal/`, where it does not look, unless `contents_directory` is ".".
    assert frozen.exe["contents_directory"] == "."
    assert frozen.exe["exclude_binaries"] is True
    assert frozen.exe["name"] == "CERTUS_HUB"
    assert frozen.collect["name"] == "CERTUS_HUB"
    assert frozen.exe["console"] is False
    assert frozen.exe["icon"] == "certus.ico"


def test_a_frozen_get_resource_path_reads_the_folder_of_the_executable(monkeypatch, tmp_path) -> None:
    from certus.core.certus_config import get_resource_path

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "CERTUS_HUB.exe"))

    assert Path(get_resource_path("pages/CERTUS_HUB.html")) == (tmp_path / "pages" / "CERTUS_HUB.html").resolve()
