# -*- mode: python ; coding: utf-8 -*-
"""Frozen build of the CERTUS suite: ONE folder, ONE executable that is the hub and every module.

The build used to freeze `CERTUS_HUB.py` alone, as a single file. The ten modules were not in it,
nor the `certus` package, nor the data (pages, examples, materials), and the hub started a module by
running `<module>.exe`, which nothing produced: from the frozen hub, no card could start. Now:

* the entry is `tools/frozen_entry.py`, which calls `certus.core.certus_frozen_entry`: without an
  argument it runs the hub, with `--run-module NAME` it runs the module NAME as `python NAME.py`
  would. It is NOT in `certus/core/`: PyInstaller searches the folder of its entry script first, and
  `certus/core/certus_substrate_index.py` would replace the root script of the same name;
* the modules of the hub catalog, the `certus` package and `certus_physics` are listed as hidden
  imports. `certus` has no `__init__.py` (implicit namespace packages) and a module is started by
  its name, which the static analysis cannot see, so the list is read from the files;
* the data that the code reads through `get_resource_path`, and the two `scripts/` modules that the
  STRAT tab imports, are bundled, and
  `contents_directory="."` keeps them NEXT TO the executable, where `get_resource_path` looks for
  them (the folder of `sys.executable`; PyInstaller 6 would put them in `_internal/` otherwise).
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT))

from certus.core.certus_frozen_entry import HUB_MODULE, catalog_modules


def _module_name(path: Path) -> str:
    parts = path.relative_to(ROOT).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


PACKAGES = ("certus", "certus_physics")

hiddenimports = sorted(
    {_module_name(p) for package in PACKAGES for p in (ROOT / package).rglob("*.py")}
    | {HUB_MODULE, *catalog_modules()}
)

datas = [
    ("certus.ico", "."),
    ("certus.svg", "."),
    ("certus2.svg", "."),
    ("data", "data"),
    ("pages", "pages"),
    ("example", "example"),
    ("samples", "samples"),
    # The multi-seed tab of STRAT imports these two at start-up, from `scripts/` next to the
    # executable: without them CERTUS_STRAT ends with "No module named 'orchestre_multigraine'".
    ("scripts/orchestre_multigraine.py", "scripts"),
    ("scripts/probe_blocs_vs_plantage.py", "scripts"),
    # `_certus_physics_impl` loads this one BY PATH when the package import cycles, which is the
    # case when a module (METAL_SINGLE) imports it before `certus_physics`: without the file,
    # CERTUS_METAL_SINGLE ends with "Cannot find certus_physics/structures.py".
    ("certus_physics/structures.py", "certus_physics"),
]

a = Analysis(
    [str(ROOT / "tools" / "frozen_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CERTUS_HUB",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # a build must not depend on the machine having UPX or not
    console=False,
    icon="certus.ico",
    contents_directory=".",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CERTUS_HUB",
)
