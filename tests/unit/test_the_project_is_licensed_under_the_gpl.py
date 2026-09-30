"""The project is published under the GPL-3.0, which PyQt6 (GPL-3.0-only) requires of it.

`pyproject.toml` said `Proprietary`, the repository had no LICENSE and is public, and the release
workflow builds an executable that bundles PyQt6: a licence conflict that only the owner could
settle. The owner settled it on 2026-09-29: GPL-3.0. This guards the three things that make the
promise true: the text is the official one, the metadata says the same, and no runtime dependency
is under a licence that cannot be combined with the GPL-3.0.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from importlib import metadata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: MD5 of the GPL-3.0 as published by the FSF (gpl-3.0.txt, 674 lines, LF).
GPL_3_0_MD5 = "d32239bcb673463ab874e80d47fae504"

#: What cannot be combined with a GPL-3.0 work (matched in the licence text of a distribution).
INCOMPATIBLE = re.compile(
    r"proprietary|commercial|non-?commercial|\bAGPL|Affero|\bSSPL\b|GPL-2\.0-only|GPLv2 only|CC-BY-NC",
    re.IGNORECASE,
)


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_licence_file_is_the_official_gpl_3_0() -> None:
    text = (ROOT / "LICENSE").read_bytes().replace(b"\r\n", b"\n")  # a Windows checkout may hold CRLF

    assert hashlib.md5(text).hexdigest() == GPL_3_0_MD5


def test_the_metadata_say_the_same() -> None:
    project = _pyproject()["project"]

    assert project["license"] == "GPL-3.0-only"
    # A licence expression and licence classifiers do not go together (PEP 639).
    assert [c for c in project["classifiers"] if c.startswith("License ::")] == []


def test_the_front_page_of_the_repository_states_the_licence_and_links_it() -> None:
    """Measured 2026-09-30: the public repository had no README at all, so its front page said nothing."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert _pyproject()["project"]["license"] in readme
    assert "](LICENSE)" in readme
    assert len(readme.splitlines()) <= 45, "a front page is read in one screen: the detail lives in docs/ETAT.md"


def _declared_runtime_dependencies() -> list[str]:
    return [re.split(r"[<>=!~ \[]", spec, maxsplit=1)[0] for spec in _pyproject()["project"]["dependencies"]]


@pytest.mark.parametrize("name", _declared_runtime_dependencies())
def test_no_runtime_dependency_is_under_a_licence_that_cannot_join_the_gpl(name) -> None:
    try:
        distribution = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        pytest.skip(f"{name} is not installed in this environment")

    fields = [
        distribution.metadata.get("License-Expression") or "",
        distribution.metadata.get("License") or "",
        *[c for c in distribution.metadata.get_all("Classifier", []) if c.startswith("License ::")],
    ]
    declared = " | ".join(f for f in fields if f)[:400]

    assert declared, f"{name} declares no licence: read its distribution before shipping it"
    assert not INCOMPATIBLE.search(declared), f"{name}: {declared}"
