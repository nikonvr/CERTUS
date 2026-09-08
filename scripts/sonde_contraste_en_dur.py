"""Sonde — les couleurs en dur qui produisent un defaut de CONTRASTE.

Le cliquet de `test_ux_design_system` compte 310 hexadecimaux hors du theme. Les
router tous serait un refactor mecanique sans valeur : la plupart sont des
couleurs de DONNEES (marqueurs de courbe, codes de statut) ou des consoles a
fond sombre parfaitement lisibles.

Cette sonde cherche autre chose : les feuilles de style qui posent **un fond et
un texte, tous deux en dur**, et dont la paire tombe sous le seuil WCAG AA. Ce
sont des defauts mesurables, pas des questions de gout — le meme critere que la
premiere passe de l'etape 3.10.

    python scripts/sonde_contraste_en_dur.py
    python scripts/sonde_contraste_en_dur.py --detail

Code de sortie : 1 s'il reste des paires sous le seuil, 0 sinon, 2 si le
controle negatif interne ne mord plus.
"""

from __future__ import annotations

import pathlib
import re
import sys

# La console Windows est en cp1252 : sans cette reconfiguration, la synthese leve
# `UnicodeEncodeError` A LA FIN, une fois la mesure calculee et donc perdue.
# Regle de `tests/unit/test_scripts_console_cp1252.py`.
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

RACINE = pathlib.Path(__file__).resolve().parents[1]
SEUIL_AA = 4.5

#: Fichiers qui DEFINISSENT la palette : un hexadecimal y est a sa place.
FICHIERS_THEME = {"certus_theme.py", "certus_theme_config.py", "certus_hub_config.py"}

_HEX = r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b"
_FOND = re.compile(rf"background(?:-color)?\s*:\s*({_HEX})", re.IGNORECASE)
_TEXTE = re.compile(rf"(?<!background-)(?<!border-)\bcolor\s*:\s*({_HEX})", re.IGNORECASE)


def _luminance(hexa: str) -> float:
    h = hexa.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    canaux = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canaux]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(a: str, b: str) -> float:
    """Rapport de contraste WCAG 2.1 entre deux couleurs, dans [1, 21]."""
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _fichiers_interface() -> list[pathlib.Path]:
    fichiers = list(RACINE.glob("CERTUS_*.py"))
    for p in (RACINE / "certus").rglob("*.py"):
        if "tests" not in p.parts:
            fichiers.append(p)
    return fichiers


def paires_en_defaut() -> list[tuple[str, int, str, str, float]]:
    """Rend (fichier, ligne, fond, texte, ratio) pour chaque paire sous AA.

    Une paire n'est retenue que si le fond ET le texte sont ecrits en dur sur la
    MEME ligne : c'est le seul cas ou le rendu est entierement determine par la
    source, donc mesurable sans lancer Qt.
    """
    defauts = []
    for p in _fichiers_interface():
        if p.name in FICHIERS_THEME:
            continue
        for num, ligne in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            fonds = _FOND.findall(ligne)
            textes = _TEXTE.findall(ligne)
            if not fonds or not textes:
                continue
            ratio = contraste(fonds[0], textes[0])
            if ratio < SEUIL_AA:
                defauts.append((str(p.relative_to(RACINE)), num, fonds[0], textes[0], ratio))
    return defauts


def _controle_negatif() -> bool:
    """La sonde sait-elle seulement detecter ? Un harnais toujours vert ne prouve rien."""
    plante = "background-color: #ffffff; color: #eeeeee;"
    return bool(_FOND.findall(plante)) and bool(_TEXTE.findall(plante)) and contraste("#ffffff", "#eeeeee") < SEUIL_AA


def main() -> int:
    if not _controle_negatif():
        print("🔴 CONTROLE NEGATIF EN ECHEC : la sonde ne detecte plus rien. Ne crois pas son silence.")
        return 2

    defauts = paires_en_defaut()
    print("=== Couleurs en dur dont la paire fond/texte tombe sous WCAG AA ===")
    print(f"    seuil {SEUIL_AA}:1 · controle negatif : 🟢 il mord\n")

    if not defauts:
        print("  aucune paire en defaut.")
    else:
        for fichier, num, fond, texte, ratio in sorted(defauts, key=lambda d: d[4]):
            print(f"  {ratio:5.2f}:1  {fond} / {texte}   {fichier}:{num}")
        if "--detail" in sys.argv:
            print("\n--- lignes fautives ---")
            for fichier, num, _f, _t, _r in defauts:
                ligne = (RACINE / fichier).read_text(encoding="utf-8", errors="ignore").splitlines()[num - 1]
                print(f"  {fichier}:{num}\n      {ligne.strip()[:140]}")

    print(f"\n  {len(defauts)} paire(s) a corriger.")
    print("  ⚠️ Angle mort : seules les paires ecrites SUR LA MEME LIGNE sont vues.")
    return 1 if defauts else 0


if __name__ == "__main__":
    raise SystemExit(main())
