"""Cliquet du système visuel (Étape 1.3).

Contrôles statiques d'invariants (lecture des sources) :
- Aucune nouvelle couleur hexadécimale hors du thème (cliquet <= 315).
- Aucune nouvelle taille de police codée en dur (cliquet <= 173).
- Aucun nouvel emoji dans les libellés utilisateur (cliquet <= 36).
- Police et taille uniformes sur toute la suite (Phase 3).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Les fichiers qui DEFINISSENT la palette, donc ou un hexadecimal est a sa place.
#:
#: `certus_hub_config.py` a rejoint la liste le 2026-09-06, a l'etape 3.9, et ce n'est pas
#: un relachement du cliquet : c'est desormais la SOURCE UNIQUE des couleurs de marque.
#: Elles ne pouvaient pas vivre dans `certus_theme.py` — `certus/core/` n'a pas le droit
#: d'importer `certus.ui`, donc le fait partage devait DESCENDRE dans la couche basse.
#: `certus_theme_config.py`, deja exempte, est dans `certus/core/` pour la meme raison.
#:
#: 🔑 La limite a ete RESSERREE de 315 a 310 dans le meme changement, exactement du nombre
#: d'hexadecimaux que l'exemption retire du comptage. Sans cela, exempter un fichier
#: donnerait du mou a tous les autres — un cliquet qu'on desserre en le deplaçant.
THEME_FILES = {"certus_theme.py", "certus_theme_config.py", "certus_hub_config.py"}


def _get_ui_python_files() -> list[Path]:
    files = list(ROOT.glob("CERTUS_*.py"))
    for p in (ROOT / "certus").rglob("*.py"):
        if "tests" not in p.parts:
            files.append(p)
    return files


def count_hex_outside_theme() -> int:
    hex_re = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
    total = 0
    for p in _get_ui_python_files():
        if p.name in THEME_FILES:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        total += len(hex_re.findall(txt))
    return total


def count_hardcoded_font_sizes() -> int:
    font_re = re.compile(r"font-size:\s*(\d+(?:\.\d+)?)(px|pt)", re.IGNORECASE)
    total = 0
    for p in _get_ui_python_files():
        if p.name in THEME_FILES:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        total += len(font_re.findall(txt))
    return total


def count_user_facing_emoji() -> int:
    emoji_re = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
    keywords = ("Button", "Action", "setText", "setTitle", "setWindowTitle", "addTab", "QLabel")
    total = 0
    for p in _get_ui_python_files():
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for line in txt.splitlines():
            if any(k in line for k in keywords):
                total += len(emoji_re.findall(line))
    return total


def test_no_new_hardcoded_hex_outside_the_theme() -> None:
    """Ratchet. Remesure 2026-09-06 : <= 310 hors des fichiers de palette.

    L'ancienne limite etait 315 avec deux fichiers exemptes. `certus_hub_config.py` est
    devenu le troisieme a l'etape 3.9, ce qui retire 8 hexadecimaux du comptage ; la limite
    descend donc de 315 a 310 et non a 307, parce que l'etape a aussi ajoute quatre
    couleurs de marque et retire l'usage detourne du jeton de succes.
    """
    count = count_hex_outside_theme()
    assert count <= 310, (
        f"Hardcoded hex colors ratchet violated! Found {count} > 310. "
        "Use CertusTheme tokens instead of hardcoded hex values."
    )


def test_no_new_hardcoded_font_size() -> None:
    """Ratchet. Measured 2026-09-04: <= 173 occurrences, 23 distinct sizes, px and pt mixed."""
    count = count_hardcoded_font_sizes()
    assert count <= 173, (
        f"Hardcoded font size ratchet violated! Found {count} > 173. "
        "Use CertusTheme font tokens instead of inline font-size."
    )


def test_no_emoji_in_user_facing_labels() -> None:
    """Ratchet. Measured 2026-09-04: <= 36 occurrences in 15 files."""
    count = count_user_facing_emoji()
    assert count <= 36, (
        f"User-facing emoji ratchet violated! Found {count} > 36. "
        "Use certus_icons instead of emoji characters."
    )


# --- typography, measured one module per process -----------------------------
#
# QApplication.font() is a PROCESS GLOBAL, and every window instantiation
# overwrites it. Reading it after building two apps in one interpreter therefore
# measures the ORDER OF EXECUTION, not the code - which is rule 0.14 of the
# mission order. Measured 2026-09-04, same code, three ways:
#
#     the test alone      -> 1 xfailed   (fails correctly)
#     its file            -> 2 xfailed   (fails correctly)
#     the whole ui suite  -> XPASS(strict) -> reported FAILED
#
# The previous version of these two tests did exactly that. The second one was
# worse still: it asserted "Open Sans" in QFontDatabase.families(), so it tested
# whether the MACHINE has a font installed - installing it would have turned the
# test green without a single line of code changing.

FONT_MARKER = "__CERTUS_FONT_TEST__"


def _font_worker_main(tag: str) -> None:
    sys.path.insert(0, str(ROOT))
    from PyQt6.QtGui import QFontDatabase as _QFD
    from PyQt6.QtWidgets import QApplication as _QApp

    from scripts.audit_ux_certus import MODULES

    modname, clsname = MODULES[tag]
    app = _QApp.instance() or _QApp(sys.argv[:1])
    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)
    win = cls()
    font = _QApp.font()
    out = {
        "family": font.family(),
        "point": font.pointSizeF(),
        # Qt keeps the REQUESTED family here even when it has to substitute at
        # paint time, so this comparison detects a silent substitution.
        "resolved": font.family() in _QFD.families(),
    }
    win.close()
    print(FONT_MARKER + json.dumps(out))


def _measure_font(tag: str) -> dict:
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        QT_QPA_PLATFORM="offscreen",
        # Without a font directory the offscreen plugin resolves NOTHING and every
        # family would look unavailable - that is defect J1, not a finding.
        QT_QPA_FONTDIR=r"C:\Windows\Fonts",
    )
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--font-worker", tag],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        encoding="utf-8",
        errors="replace",
    )
    hit = [x for x in (proc.stdout or "").splitlines() if x.startswith(FONT_MARKER)]
    assert hit, f"Font worker crashed for {tag}:\n{proc.stderr}"
    return json.loads(hit[0][len(FONT_MARKER) :])


@pytest.fixture(scope="module")
def fonts_by_module() -> dict[str, dict]:
    """One dedicated process per module: the only way this measurement means anything."""
    from scripts.audit_ux_certus import MODULES

    return {tag: _measure_font(tag) for tag in MODULES}


@pytest.mark.xfail(
    strict=True,
    reason="HUB/STRAT à 9 pt vs autres à 10 pt — sera unifié à l'étape 3.2",
)
def test_font_point_size_is_uniform_across_the_suite(fonts_by_module) -> None:
    """Every window must start from the same base point size.

    Measured 2026-09-04, one process each: HUB, STRAT, SMOOTHER and SUBSTRATE
    open at 9 pt while the other seven open at 10 pt.
    """
    sizes = {tag: row["point"] for tag, row in fonts_by_module.items()}
    distinct = sorted(set(sizes.values()))
    assert len(distinct) == 1, "base point size is not uniform: " + ", ".join(
        f"{tag}={pt:g}pt" for tag, pt in sorted(sizes.items(), key=lambda kv: kv[1])
    )


@pytest.mark.xfail(
    strict=True,
    reason="DESIGN et RE demandent 'Open Sans', que Qt remplace en silence — sera corrigé à l'étape 3.2",
)
def test_no_module_requests_a_font_qt_must_substitute(fonts_by_module) -> None:
    """A module must not ask for a family the system cannot provide.

    Qt substitutes silently, so the interface renders in a font nobody chose and
    every width shifts. This asserts a property of the CODE - which family each
    module asks for - not of the machine's font inventory.

    Measured 2026-09-04: DESIGN and RE request 'Open Sans', absent here.
    """
    missing = {tag: row["family"] for tag, row in fonts_by_module.items() if not row["resolved"]}
    assert not missing, "requested but not installed: " + ", ".join(
        f"{tag} -> {fam!r}" for tag, fam in sorted(missing.items())
    )


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--font-worker":
        _font_worker_main(sys.argv[2])
        sys.exit(0)
