"""Cliquet du système visuel (Étape 1.3).

Contrôles statiques d'invariants (lecture des sources) :
- Aucune nouvelle couleur hexadécimale hors du thème (cliquet <= 294).
- Aucune nouvelle taille de police codée en dur (cliquet <= 52).
- Aucun nouvel emoji dans les libellés utilisateur (cliquet <= 36).
- Police et taille uniformes sur toute la suite (Phase 3).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Les fichiers qui DEFINISSENT la palette, donc ou un hexadecimal est a sa place.
#:
#: `certus_hub_config.py` a rejoint la liste le 2026-09-06, a l'etape 3.9, et ce n'est pas
#: un relachement du cliquet : c'est desormais la SOURCE UNIQUE des couleurs de marque.
#: Elles ne pouvaient pas vivre dans `certus_theme.py` — `certus/core/` n'a pas le droit
#: d'importer `certus.ui`, donc le fait partage devait DESCENDRE dans la couche basse.
#:
#: 🔑 La limite a ete RESSERREE de 315 a 310 dans le meme changement, exactement du nombre
#: d'hexadecimaux que l'exemption retire du comptage. Sans cela, exempter un fichier
#: donnerait du mou a tous les autres — un cliquet qu'on desserre en le deplaçant.
THEME_FILES = {"certus_theme.py", "certus_hub_config.py"}


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
    """Ratchet. Remesure 2026-10-01 apres l'etape S6.4b : <= 265.

    Historique des paliers, parce que chacun dit ce qui l'a fait bouger : 315 avec deux
    fichiers de palette exemptes · 310 quand un troisieme les a rejoints a l'etape 3.9,
    resserre du nombre exact d'hexadecimaux que l'exemption retirait -- sans quoi
    exempter un fichier aurait donne du mou a tous les autres · 304 depuis la premiere
    passe de 3.10, qui a route les six libelles poses sur un remplissage colore dans
    `certus_ux.py`, la feuille appliquee PAR-DESSUS celle du theme · 294 depuis la
    seconde passe, qui a donne une SOURCE UNIQUE a l'identite du dialogue des noeuds
    manuels -- six nuances repandues sur dix-sept sites, ramenees a leurs declarations.

    🔑 Cette seconde passe ne CHANGE aucune valeur, seulement leur nom : l'ensemble des
    couleurs employees par le fichier est identique avant et apres, ce que le script de
    la passe verifiait avant d'ecrire. Elle a rendu visibles deux choses cachees dans
    des litteraux distants de deux cent cinquante lignes -- une regle de couleur ecrite
    DEUX FOIS mot pour mot, et une divergence entre la couleur de ligne d'un noeud et
    celle de son etiquette. 📏 Les deux etiquettes de nature echouent d'ailleurs le
    contraste en mode clair, 2,36:1 et 3,40:1 pour un seuil de 4,5 ; corriger demande
    de CHOISIR une couleur, ce que cette etape ne fait pas.

    🔑 Cette passe n'etait pas cosmetique, et c'est mesure : en mode clair le jeton et
    le blanc litteral valent la meme chose, donc la feuille CLAIRE sort identique au
    caractere -- empreinte comparee avant/apres. En mode SOMBRE le remplissage devient
    une teinte pale et le jeton passe au fonce : les trois libelles de bouton tenaient
    2,54 / 2,77 / 1,92 contre le seuil de 4,5, et rendent 7,02 / 6,45 / 9,29 apres.
    Trois echecs d'accessibilite fermes.

    ⚠️ SIX AUTRES SITES DU MEME FICHIER SONT LAISSES, deliberement : deux teintes de
    degrade et une bordure pale n'ont aucun jeton correspondant, et les trois de
    l'infobulle sont un choix assume -- elle reste sombre dans les deux modes. L'une
    d'elles porte par COINCIDENCE la valeur d'un jeton de survol de surface, dont le
    role n'a rien a voir : la router sur la seule egalite de valeur serait faux.

    🔴 CE COMPTE N'EST PAS LA DETTE. Il compte au niveau du texte, donc il inclut les
    couleurs d'un HTML EXPORTE -- qui ne doit surtout pas suivre le theme de
    l'application -- et celles qu'un commentaire cite pour expliquer un defaut.
    `scripts/sonde_couleurs_en_dur.py` fait la separation et la chiffre.

    📏 281 le 2026-10-01 au debut de S6.4 (le plafond de 294 n'avait pas suivi : 13 de mou), 272 apres S6.4b, qui retire NEUF
    hexadecimaux : les encres litterales `#fff` du stepper (deux) et des toasts (trois, plus un `#222`), le `#ffffff` de la
    ligne choisie de la palette de commandes, le `#FFFFFF` des deux icones de FIELD, devenus des jetons d'encre
    (`PRIMARY_TEXT`, `SUCCESS_LABEL`...). Le mecanisme des jetons de S6.4 n'en avait retire AUCUN : il fait suivre le theme a des
    couleurs qui sont deja des jetons, il ne dit rien de celles qui n'en sont pas. Le plafond est le compte, au hexadecimal pres.

    📏 265 apres le dernier lot de S6.4b : sept de plus, des encres et des fonds ecrits pour le seul theme clair (`#1e293b` des
    equations finales d'INDEX, `#475569` du libelle de Pareto de FIELD, `#15803d` et `#bbf7d0` d'une couche faite, `#f8f9fa`, `#ddd`
    et `#e2e6ea` de la barre d'outils des graphiques), routes vers les jetons ou vers une teinte de jeton.

    📏 217 le 2026-10-06 (257 avant) : les 40 hexadecimaux des palettes de repli du suivi d'etapes, des infobulles et des
    badges, qui ne servaient que derriere des jetons absents (`MID`, `TEXT_MUTED`) ou jamais (branche
    claude/charming-wright-43077a, portee).
    """
    count = count_hex_outside_theme()
    assert count <= 217, (
        f"Hardcoded hex colors ratchet violated! Found {count} > 217. "
        "Use CertusTheme tokens instead of hardcoded hex values."
    )


def test_no_new_hardcoded_font_size() -> None:
    """Ratchet : <= 52 depuis l'etape 3.1 du 2026-09-08 (157 le 2026-09-06).

    Depart 2026-09-04 : 173 autorisees, 162 reelles, 23 valeurs distinctes, px et pt
    MELANGES. L'etape 3.1 a route les 5 declarations en pt qui tombaient EXACTEMENT sur un
    pas de l'echelle, dans `certus_ux.py`, et la limite descend d'autant -- de 173 a 157,
    ce qui supprime aussi les 11 de mou qui trainaient.

    🔴 LES 157 QUI RESTENT NE SONT PAS UN OUBLI. La majorite est en **px** (56 fois `11px`
    a elle seule), et convertir px en pt CHANGE le rendu des onze fenetres : a 96 dpi,
    10 pt valent 13,3 px, donc un libelle a 11 px est plus PETIT que la base tout en
    paraissant plus grand dans la source. Choisir l'unite est une decision a prendre avec
    les yeux sur un ecran, pas un refactor a glisser dans une passe de nuit.
    """
    count = count_hardcoded_font_sizes()
    assert count <= 52, (
        f"Hardcoded font size ratchet violated! Found {count} > 52. "
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ux_worker import run_ux_worker  # noqa: E402


def _font_worker_main(tag: str) -> None:
    sys.path.insert(0, str(ROOT))
    from PyQt6.QtGui import QFontDatabase as _QFD
    from PyQt6.QtWidgets import QApplication as _QApp

    from scripts.audit_ux_certus import MODULES

    modname, clsname = MODULES[tag]
    _QApp.instance() or _QApp(sys.argv[:1])
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
    # D23: the native abort (0xC0000005) came after this line, while the return freed the locals (the
    # QApplication before the window) or during interpreter teardown; the marker, still in the pipe buffer,
    # was lost with it. Flush it, then leave without the teardown: it is not what this worker measures.
    print(FONT_MARKER + json.dumps(out), flush=True)
    os._exit(0)


def _measure_font(tag: str) -> dict:
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        QT_QPA_PLATFORM="offscreen",
        # Without a font directory the offscreen plugin resolves NOTHING and every
        # family would look unavailable - that is defect J1, not a finding.
        QT_QPA_FONTDIR=r"C:\Windows\Fonts",
    )
    return run_ux_worker(
        [sys.executable, os.path.abspath(__file__), "--font-worker", tag],
        FONT_MARKER,
        context=f"{tag}",
        env=env,
        cwd=str(ROOT),
    )


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
