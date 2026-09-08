"""Aucune source ne doit porter de séquence d'échappement invalide.

🔴 CE QUE C'EST, ET POURQUOI ÇA COMPTE ICI. Un `\\p` dans une chaîne non brute est
aujourd'hui un **avertissement** ; Python annonce d'en faire une **erreur**. Le
projet écrit beaucoup de chemins Windows dans ses docstrings de sondes — c'est
exactement la forme qui déclenche le défaut, et il ne se voit pas : le fichier
s'importe, le programme tourne, et l'avertissement se perd dans la sortie.

📏 Trouvé le 2026-09-08 en élargissant le périmètre de `tools/dead_symbol_audit.py` :
**un seul** cas dans tout le dépôt, dans une docstring de `scripts/`, sur un chemin
écrit avec un antislash simple là où la ligne voisine du même fichier en écrivait
deux. Corrigé. Ce test est le cliquet qui l'empêche de revenir.

⚠️ **Lire en `utf-8-sig`, pas en `utf-8`.** Trois fichiers de tests portent une
marque d'ordre d'octets, parfaitement légale (PEP 263) : la machinerie d'import la
retire, mais `compile()` sur une chaîne la refuse. Une première version de cette
sonde les a donc signalés comme cassés alors qu'ils s'importent tous les trois.
*Un défaut de l'instrument ressemble à un défaut du code.*
"""

from __future__ import annotations

import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOSSIERS_EXCLUS = {
    ".venv",
    ".git",
    "__pycache__",
    "build",
    "dist",
    "artifacts",
    "certus_optical_suite.egg-info",
}


def _sources() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*.py") if not set(p.relative_to(ROOT).parts) & DOSSIERS_EXCLUS)


def _avertissements(chemin: Path) -> list[str]:
    source = chemin.read_text(encoding="utf-8-sig", errors="ignore")
    with warnings.catch_warnings(record=True) as captures:
        warnings.simplefilter("always")
        try:
            compile(source, str(chemin), "exec")
        except SyntaxError as erreur:
            return [f"{chemin.relative_to(ROOT)}: ne compile pas — {erreur}"]
    return [
        f"{chemin.relative_to(ROOT)}:{c.lineno}: {c.message}" for c in captures if issubclass(c.category, SyntaxWarning)
    ]


def test_the_sweep_actually_reads_the_repository():
    """Contrôle négatif : un balayage vide passerait pour vert."""
    fichiers = _sources()
    assert len(fichiers) > 400, f"seulement {len(fichiers)} source(s) balayée(s) — le périmètre s'est effondré"


def test_the_sweep_can_still_detect_one():
    """Contrôle négatif, l'autre sens : la sonde sait-elle encore mordre ?

    On lui donne le défaut à trouver, sans l'écrire dans un fichier du dépôt — un
    contrôle qui plante son propre artefact ferait échouer le balayage voisin.
    """
    faute = "x = " + '"' + chr(92) + 'p"' + "\n"
    with warnings.catch_warnings(record=True) as captures:
        warnings.simplefilter("always")
        compile(faute, "<controle>", "exec")
    assert any(issubclass(c.category, SyntaxWarning) for c in captures), (
        "la sonde ne détecte plus une séquence invalide qu'on lui met sous le nez"
    )


def test_no_source_carries_an_invalid_escape():
    trouvailles = [ligne for chemin in _sources() for ligne in _avertissements(chemin)]
    assert not trouvailles, (
        "séquence(s) d'échappement invalide(s) — une version future de Python en fera une erreur :\n"
        + "\n".join(trouvailles)
    )
