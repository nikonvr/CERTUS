"""The licence files that the frozen build carries next to its executable, in `licenses/`.

Decided by the owner on 2026-10-06: the executable that the release workflow publishes as an artifact carries CERTUS's
licence, its third-party notices, Python's licence, the licence of PyInstaller's bootloader (it is in the executable),
and the licence files of every distribution whose modules the build bundles, as the MIT and BSD terms of most of them
ask of a binary distribution. Before, it carried those of five distributions, which PyInstaller's hooks copied for
their own needs.

`certus_hub.spec` adds what `licence_toc` returns to the data of the build; `tools/release_checks.py` refuses a build
without them. Build-time only: nothing here is imported by the executable.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]

#: Where the licences go, next to the executable.
LICENCE_DIR = "licenses"

#: The project's own files, at the top of LICENCE_DIR.
OWN_FILES = ("LICENSE", "THIRD_PARTY_NOTICES.md")

#: A licence file by its name, wherever a distribution keeps it.
_LICENCE_NAME = re.compile(r"^(licen[cs]e|copying|notice)([._-].*)?$", re.IGNORECASE)


def canonical(name: str) -> str:
    """The PEP 503 form of a distribution name: the folder its licences go to."""
    return re.sub(r"[-_.]+", "-", name).lower()


def top_level_names(*tocs: Iterable[tuple]) -> set[str]:
    """The top-level names of the entries of PyInstaller TOCs: `numpy` for the module `numpy.linalg` as for the
    binary `numpy.libs/libscipy_openblas.dll`; a DLL at the top (`python314.dll`) gives a name no distribution has."""
    return {re.split(r"[/\\]", str(entry[0]), maxsplit=1)[0].split(".")[0] for toc in tocs for entry in toc}


def distributions_of(names: Iterable[str]) -> list[str]:
    """The installed distributions that provide these top-level names, in the order of their canonical names."""
    owners = metadata.packages_distributions()
    found = {canonical(dist): dist for name in names for dist in owners.get(name, ())}
    return [found[key] for key in sorted(found)]


def licence_files(distribution: str) -> list[tuple[PurePosixPath, Path]]:
    """(destination relative to the distribution's folder, source) of the licence files of one distribution.

    PEP 639 puts them in `<name>.dist-info/licenses/`; older metadata leave them at the root of the dist-info folder.
    Those come first; files named like a licence inside the package itself are taken only when the dist-info has none.
    """
    dist = metadata.distribution(distribution)
    in_info: list[tuple[PurePosixPath, object]] = []
    elsewhere: list[tuple[PurePosixPath, object]] = []
    for entry in dist.files or ():
        parts = PurePosixPath(str(entry)).parts
        if parts[0].endswith(".dist-info"):
            if len(parts) > 2 and parts[1] == "licenses":
                in_info.append((PurePosixPath(*parts[2:]), entry))
            elif len(parts) == 2 and _LICENCE_NAME.match(parts[1]):
                in_info.append((PurePosixPath(parts[1]), entry))
        elif _LICENCE_NAME.match(parts[-1]) and not parts[-1].endswith((".py", ".pyc")):
            elsewhere.append((PurePosixPath(*parts), entry))
    found = []
    for relative, entry in in_info or elsewhere:
        source = Path(dist.locate_file(entry))
        if source.is_file():
            found.append((relative, source))
    return found


def licence_toc(names: Iterable[str]) -> list[tuple[str, str, str]]:
    """PyInstaller TOC entries (destination, source, "DATA") that fill `licenses/` for a build bundling `names`."""
    toc = [(f"{LICENCE_DIR}/{name}", str(ROOT / name), "DATA") for name in OWN_FILES]
    python_licence = Path(sys.base_prefix) / "LICENSE.txt"
    if python_licence.is_file():
        toc.append((f"{LICENCE_DIR}/python/LICENSE.txt", str(python_licence), "DATA"))
    for distribution in [*distributions_of(names), "pyinstaller"]:
        try:
            files = licence_files(distribution)
        except metadata.PackageNotFoundError:
            continue
        toc.extend((f"{LICENCE_DIR}/{canonical(distribution)}/{relative}", str(source), "DATA") for relative, source in files)
    return toc
