"""UNE CASE COCHEE NE DOIT PAS SE DISTINGUER PAR LA SEULE COULEUR — etape 3.7.

📏 Mesure au PIXEL du 2026-09-06, avant correctif : une `QCheckBox` cochee rendait
**284 px de #0f62fe uni**, sans un seul pixel de coche. Les seules autres couleurs etaient
2 px d'anticrenelage dans les coins arrondis.

## 🔑 LA CAUSE N'EST PAS CELLE QUE L'ETAPE ANNONCE

L'etape 3.7 vise `certus_theme.py` (indicateur 14 px, etat coche par la couleur seule). Or
`certus_ux.py`, applique **par-dessus**, declarait deja 16 px, une coche SVG et un point
radio SVG. Le defaut aurait donc du etre repare -- il ne l'etait pas.

L'experience a separe les hypotheses au lieu de les deviner :

    SVG data-URL (ce que portait la feuille)   36 px clairs dans l'indicateur   (bruit de fond)
    PNG data-URL (meme image, en raster)       36                               (identique)
    PNG ecrit dans un FICHIER                  76                               (le glyphe apparait)

**Qt ne resout pas les data-URL dans un `url()` de QSS.** Les deux encodages ne rendent rien,
un chemin rend. La coche et le point radio n'avaient donc **jamais** fonctionne.

⚠️ **Ce n'est PAS l'instabilite QtSvg** que `is_svg_icon_rendering_disabled()` protege : le
processus a survecu a chaque essai. Deux defauts distincts partagent un symptome, et c'est
pour cela que l'experience les a separes AVANT d'ecrire le correctif -- sinon on aurait
« repare » le mauvais.

## Ce que ce fichier verrouille

Le seul enonce qui compte : **l'etat coche se voit autrement que par la teinte.** Il est
verifie en peignant le widget et en comptant les pixels, pas en relisant la feuille de style
-- c'est precisement une feuille de style d'apparence correcte qui a masque le defaut
pendant toute la campagne.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")


def _indicator_colors(checked: bool) -> dict[str, int]:
    """Couleurs presentes dans la zone de l'indicateur, widget reellement peint."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtWidgets import QCheckBox

    from certus.ui.certus_theme import CertusTheme
    from certus.utils.certus_ux import build_premium_overrides

    CertusTheme.configure("light")
    widget = QCheckBox("x")
    widget.setStyleSheet(build_premium_overrides())
    widget.setChecked(checked)
    widget.resize(120, 24)

    image = QImage(120, 24, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(painter)
    painter.end()

    counts: dict[str, int] = {}
    for y in range(2, 22):
        for x in range(0, 18):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() > 0:
                counts[pixel.name()] = counts.get(pixel.name(), 0) + 1
    return counts


class TestLEtatCocheNeTientPasQuALaCouleur:
    """WCAG 1.4.1 : la couleur ne doit pas etre le SEUL moyen visuel."""

    #: Sous ce compte, ce qu'on voit n'est que de l'anticrenelage de coin arrondi.
    #: 📏 Avant correctif il y en avait 2 ; la coche peinte en apporte des dizaines.
    MINIMUM = 12

    def test_une_case_cochee_porte_un_glyphe_clair(self, qapp) -> None:
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure("light")
        couleurs = _indicator_colors(checked=True)
        remplissage = CertusTheme.PRIMARY.lower()

        clairs = sum(
            n
            for c, n in couleurs.items()
            if c.lower() != remplissage and _luminance(c) > _luminance(remplissage) + 0.25
        )
        assert clairs >= self.MINIMUM, (
            f"seulement {clairs} px plus clairs que le remplissage : la coche ne se dessine "
            f"pas, l'etat coche ne tient qu'a la teinte. Couleurs vues : {couleurs}"
        )

    def test_cochee_et_decochee_ne_different_pas_que_par_la_teinte(self, qapp) -> None:
        """Controle de forme : les deux etats doivent differer en STRUCTURE."""
        cochee = _indicator_colors(True)
        decochee = _indicator_colors(False)
        assert len(cochee) >= 3, (
            f"l'indicateur coche n'a que {len(cochee)} couleur(s) : c'est un aplat. {cochee}"
        )
        assert cochee != decochee


class TestAucuneDataURLNeSubsisteDansLaFeuille:
    """Elles ne rendent rien, silencieusement. Une seule qui revient et le glyphe disparait."""

    def test_le_qss_n_utilise_aucune_data_url(self, qapp) -> None:
        from certus.utils.certus_ux import build_premium_overrides

        qss = build_premium_overrides()
        assert "url(\"data:" not in qss and "url('data:" not in qss and "url(data:" not in qss, (
            "une data-URL est revenue dans la feuille. Qt ne les resout pas : la propriete "
            "sera ignoree en silence et le glyphe ne s'affichera pas."
        )


class TestLeControleNegatif:
    """L'outil sait-il seulement voir la difference ? Sinon il valide n'importe quoi."""

    def test_il_distingue_un_aplat_d_un_glyphe(self) -> None:
        aplat = {"#0f62fe": 284, "#84acf7": 2}
        avec = {"#0f62fe": 210, "#ffffff": 60, "#84acf7": 2}
        seuil = TestLEtatCocheNeTientPasQuALaCouleur.MINIMUM

        def clairs(d: dict[str, int]) -> int:
            return sum(
                n
                for c, n in d.items()
                if c != "#0f62fe" and _luminance(c) > _luminance("#0f62fe") + 0.25
            )

        assert clairs(aplat) < seuil, "le controle accepterait un aplat sans coche"
        assert clairs(avec) >= seuil, "le controle refuserait une coche pourtant presente"


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
