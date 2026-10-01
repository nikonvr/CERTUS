"""UN UTILISATEUR AU CLAVIER DOIT VOIR OU EST LE FOCUS — etape 3.6.

📏 Mesure du 2026-09-06, avant correctif : **zero** regle `:focus` sur un bouton, dans les
DEUX couches QSS. `certus_theme.py` et `certus_ux.py` en portaient pour `QLineEdit`,
`QComboBox`, `QSpinBox`, `QDoubleSpinBox`, `QPlainTextEdit` et `QTextEdit` -- donc pour tout
ce qui se SAISIT, et rien pour ce qui s'ACTIONNE. Naviguer la suite au clavier revenait a
deviner.

## Pourquoi la couleur de l'anneau change selon la famille de bouton

Ce n'est pas une coquetterie : **aucune couleur unique ne tient 3:1 dans les deux themes.**
Mesure avec `certus_a11y.contrast_ratio` :

    anneau {primary} contre SURFACE        5.00:1 clair   6.98:1 sombre   retenu (defaut)
    anneau {surface} contre le remplissage 4.83:1 .. 9.29:1 dans les deux   retenu (variantes)
    anneau {primary} sur un fond PRIMARY   1:1                              REJETE
    anneau {text_main} sur SUCCESS sombre  1.56:1                           REJETE

Le dernier cas est le piege : en mode sombre le texte est CLAIR et les remplissages le sont
aussi, donc un anneau « couleur du texte » disparait exactement la ou on en a besoin.

## Ce que ce fichier verrouille surtout

🔑 **Que prendre le focus ne DEPLACE rien.** La bordure grandit de 1 px (bouton par defaut,
qui en avait deja 1) ou de 2 px (variantes, en `border: none`), et la marge interieure
diminue d'autant. Un anneau de focus qui pousse ses voisins serait pire que pas d'anneau :
l'utilisateur au clavier verrait la fenetre bouger a chaque tabulation.
"""

from __future__ import annotations

import re

import pytest

pytest.importorskip("PyQt6")


def _qss() -> str:
    from certus.utils.certus_ux import build_premium_overrides

    return build_premium_overrides()


def _bloc(qss: str, selecteur: str) -> str:
    """Le corps de la premiere regle dont le selecteur contient `selecteur`."""
    motif = re.compile(
        r"([^{}]*" + re.escape(selecteur) + r"[^{}]*)\{([^}]*)\}", re.MULTILINE
    )
    trouve = motif.search(qss)
    assert trouve, f"aucune regle ne porte {selecteur!r}"
    return trouve.group(2)


def _px(corps: str, propriete: str) -> list[float]:
    ligne = re.search(rf"{propriete}\s*:\s*([^;]+);", corps)
    assert ligne, f"propriete {propriete!r} absente de {corps!r}"
    return [float(x) for x in re.findall(r"([\d.]+)px", ligne.group(1))]


class TestLAnneauExiste:
    """Le defaut d'origine : il n'y en avait aucun."""

    def test_le_bouton_par_defaut_a_une_regle_de_focus(self, qapp) -> None:
        assert "QPushButton:focus" in _qss()

    @pytest.mark.parametrize(
        "objet", ["CertusPrimaryBtn", "CertusDangerBtn", "CertusSuccessBtn", "CertusFeaturedBtn"]
    )
    def test_chaque_variante_pleine_a_la_sienne(self, objet: str, qapp) -> None:
        """Les variantes sont en `border: none` : sans regle propre elles n'auraient RIEN."""
        assert f"QPushButton#{objet}:focus" in _qss()


class TestPrendreLeFocusNeDeplaceRien:
    """🔑 Le vrai garde-fou. bordure + marge doit etre INVARIANT.

    Sinon la fenetre bouge a chaque tabulation, ce qui est pire que l'absence d'anneau.
    """

    @pytest.mark.parametrize(
        ("selecteur", "repos"),
        [
            ("QPushButton:focus", "QPushButton {"),
            ("QPushButton#CertusPrimaryBtn:focus", "QPushButton#CertusPrimaryBtn {"),
            ("QPushButton#CertusDangerBtn:focus", "QPushButton#CertusDangerBtn {"),
            ("QPushButton#CertusSuccessBtn:focus", "QPushButton#CertusSuccessBtn {"),
            ("QPushButton#CertusFeaturedBtn:focus", "QPushButton#CertusFeaturedBtn {"),
        ],
    )
    def test_bordure_plus_marge_est_invariante(self, selecteur: str, repos: str, qapp) -> None:
        qss = _qss()
        corps_repos = _bloc(qss, repos.rstrip(" {"))
        corps_focus = _bloc(qss, selecteur)

        bordure_repos = _px(corps_repos, "border")[0] if "none" not in corps_repos.split("border:")[1].split(";")[0] else 0.0
        bordure_focus = _px(corps_focus, "border")[0]
        marge_repos = _px(corps_repos, "padding")
        marge_focus = _px(corps_focus, "padding")

        for axe, (r, f) in enumerate(zip(marge_repos, marge_focus, strict=True)):
            assert r + bordure_repos == pytest.approx(f + bordure_focus), (
                f"{selecteur} axe {axe} : au repos {r}+{bordure_repos} px, "
                f"au focus {f}+{bordure_focus} px — le bouton change de taille"
            )


class TestLAnneauEstVISIBLE:
    """Un anneau existe-t-il ne suffit pas : il doit se voir, et c'est mesurable."""

    SEUIL = 3.0  # WCAG 2.4.11, indicateur de focus contre les couleurs adjacentes

    @pytest.mark.parametrize("mode", ["light", "dark"])
    def test_l_anneau_du_bouton_par_defaut_contraste_avec_la_surface(self, mode: str, qapp) -> None:
        from certus.ui.certus_a11y import contrast_ratio
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure(mode)
        ratio = contrast_ratio(CertusTheme.PRIMARY, CertusTheme.SURFACE)
        assert ratio >= self.SEUIL, f"{mode} : anneau a {ratio:.2f}:1, seuil {self.SEUIL}"

    @pytest.mark.parametrize("mode", ["light", "dark"])
    @pytest.mark.parametrize("remplissage", ["PRIMARY", "DANGER", "SUCCESS"])
    def test_l_anneau_des_variantes_contraste_avec_leur_remplissage(
        self, mode: str, remplissage: str, qapp
    ) -> None:
        from certus.ui.certus_a11y import contrast_ratio
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure(mode)
        ratio = contrast_ratio(CertusTheme.SURFACE, getattr(CertusTheme, remplissage))
        assert ratio >= self.SEUIL, (
            f"{mode}/{remplissage} : anneau a {ratio:.2f}:1, seuil {self.SEUIL}"
        )

    @pytest.mark.parametrize("mode", ["light", "dark"])
    def test_le_candidat_REJETE_le_serait_encore(self, mode: str, qapp) -> None:
        """Controle negatif : si ce test passait, le seuil ne mordrait plus.

        `text_main` avait ete envisage comme anneau unique. Il tombe a 1,56:1 sur SUCCESS en
        mode sombre. Ce test EXIGE que le seuil sache encore le refuser -- sinon il ne
        protege rien.
        """
        from certus.ui.certus_a11y import contrast_ratio
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure(mode)
        pire = min(
            contrast_ratio(CertusTheme.TEXT_MAIN, getattr(CertusTheme, f))
            for f in ("PRIMARY", "DANGER", "SUCCESS")
        )
        if mode == "dark":
            assert pire < self.SEUIL, (
                "text_main passe desormais le seuil en sombre : soit la palette a change, "
                "soit le seuil ne mord plus. Remesure avant de simplifier l'anneau."
            )


# =============================================================================
# Les boutons que la fabrique habille elle-meme : `create_styled_button`
# =============================================================================
#
# 📏 Mesure du 2026-09-30, en peignant un bouton avant et apres `setFocus()` : **0 pixel change**,
# dans les deux themes et pour les six roles ; le bouton de la feuille premium, lui, en change
# 1 308. `create_styled_button` (73 sites d'appel) pose SA feuille sur le bouton, en `border: none` ;
# une regle posee sur le widget l'emporte sur celle de l'application quelle que soit sa
# specificite, donc la regle `QPushButton:focus` de la couche applicative ne l'atteignait jamais.
# Un utilisateur au clavier ne voyait pas ou il etait sur 73 boutons.
#
# Ce qui est verifie ici est PEINT : les pixels de l'anneau et du remplissage, pas la feuille.

ROLES_DE_LA_FABRIQUE = ["primary", "secondary", "info", "success", "warning", "danger"]
FONDS_DONNES_DIRECTEMENT = ["SECONDARY", "DANGER"]  # `create_styled_button("Load config", CertusTheme.SECONDARY)`


def _poser_un_bouton(qapp, theme: str, variante: str):
    """Un bouton de la fabrique a cote d'un autre, dans une fenetre active ; rend (hote, bouton, autre)."""
    from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from certus.ui.certus_theme import CertusTheme
    from certus.ui.certus_ui_widgets_factory import create_styled_button

    CertusTheme.configure(theme)
    hote = QWidget()
    disposition = QVBoxLayout(hote)
    bouton = create_styled_button("Load config", getattr(CertusTheme, variante) if variante.isupper() else variante)
    autre = QPushButton("autre")
    disposition.addWidget(bouton)
    disposition.addWidget(autre)
    hote.resize(300, 140)
    hote.show()
    hote.activateWindow()
    qapp.processEvents()
    autre.setFocus()
    qapp.processEvents()
    return hote, bouton, autre


def _peindre(widget):
    from PyQt6.QtGui import QImage, QPainter

    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    peintre = QPainter(image)
    widget.render(peintre)
    peintre.end()
    return image


@pytest.fixture
def theme_clair_apres():
    from certus.ui.certus_theme import CertusTheme

    yield
    CertusTheme.configure("light")


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("variante", [*ROLES_DE_LA_FABRIQUE, *FONDS_DONNES_DIRECTEMENT])
class TestLesBoutonsDeLaFabriqueOntUnAnneau:
    def test_prendre_le_focus_change_ce_qui_est_peint(self, mode, variante, qapp, theme_clair_apres) -> None:
        hote, bouton, _autre = _poser_un_bouton(qapp, mode, variante)
        try:
            repos = _peindre(bouton)
            bouton.setFocus()
            qapp.processEvents()
            assert bouton.hasFocus(), "le bouton n'a pas pris le focus : la mesure ne mesurerait rien"
            focus = _peindre(bouton)
            changes = sum(
                repos.pixel(x, y) != focus.pixel(x, y) for y in range(repos.height()) for x in range(repos.width())
            )
            assert changes > 100, f"{mode}/{variante} : {changes} pixel(s) changent au focus -- il est invisible"
        finally:
            hote.close()

    def test_l_anneau_se_lit_contre_le_remplissage(self, mode, variante, qapp, theme_clair_apres) -> None:
        """WCAG 1.4.11 : 3:1 pour l'indicateur ; lu sur les pixels du bord gauche, a mi-hauteur."""
        from certus.ui.certus_a11y import contrast_ratio

        hote, bouton, _autre = _poser_un_bouton(qapp, mode, variante)
        try:
            bouton.setFocus()
            qapp.processEvents()
            image = _peindre(bouton)
            y = image.height() // 2
            anneau = image.pixelColor(1, y).name()
            remplissage = image.pixelColor(6, y).name()
            ratio = contrast_ratio(anneau, remplissage)
            assert ratio >= 3.0, f"{mode}/{variante} : anneau {anneau} sur {remplissage} = {ratio:.2f}:1, sous 3:1"
        finally:
            hote.close()

    def test_prendre_le_focus_ne_deplace_rien(self, mode, variante, qapp, theme_clair_apres) -> None:
        """Bordure plus marge invariantes : un anneau qui pousse ses voisins serait pire que pas d'anneau."""
        hote, bouton, autre = _poser_un_bouton(qapp, mode, variante)
        try:
            avant = (bouton.geometry(), autre.geometry(), bouton.sizeHint())
            bouton.setFocus()
            qapp.processEvents()
            # Qt garde la taille qu'il avait calculee avant le focus : on la lui fait recalculer DANS l'etat
            # focalise (changer le texte vide ce cache), puis on laisse la disposition se refaire. Sans cela
            # une marge non compensee ne se voit pas ici, et se verrait au prochain remaniement de la fenetre.
            texte = bouton.text()
            bouton.setText(texte + " ")
            bouton.setText(texte)
            qapp.processEvents()
            assert (bouton.geometry(), autre.geometry(), bouton.sizeHint()) == avant, (
                f"{mode}/{variante} : prendre le focus a deplace ou redimensionne un bouton"
            )
        finally:
            hote.close()


# =============================================================================
# Cases, radios, onglets, curseurs : ce qu'un utilisateur au clavier traverse aussi
# =============================================================================
#
# 📏 Mesure du 2026-09-30, en peignant chaque controle avant et apres `setFocus()` sous les deux
# feuilles de la fenetre : une case, un radio, l'onglet selectionne et un curseur changent
# **0 pixel**. Les boutons avaient leur anneau (etape 3.6), pas ces controles-la.
#
# Ce qui est verifie est PEINT, avec la feuille que les fenetres appliquent (theme + surcharges).

CONTROLES = ["case", "radio", "onglet", "curseur"]


def _controle(nom: str):
    """(widget a peindre, widget qui prend le focus)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QCheckBox, QLabel, QRadioButton, QSlider, QTabWidget

    if nom == "case":
        w = QCheckBox("Enable the option")
        return w, w
    if nom == "radio":
        w = QRadioButton("Choice")
        return w, w
    if nom == "onglet":
        w = QTabWidget()
        w.addTab(QLabel("a"), "First")
        w.addTab(QLabel("b"), "Second")
        return w, w.tabBar()
    w = QSlider(Qt.Orientation.Horizontal)
    return w, w


@pytest.fixture
def feuille_des_fenetres(qapp):
    """La feuille que les fenetres posent : celle du theme, puis les surcharges ; l'ancienne est rendue."""
    from certus.ui.certus_theme import CertusTheme
    from certus.utils.certus_ux import build_premium_overrides

    avant = qapp.styleSheet()

    def poser(mode: str) -> None:
        CertusTheme.configure(mode)
        qapp.setStyleSheet(CertusTheme.get_standard_stylesheet() + build_premium_overrides(mode))

    try:
        yield poser
    finally:
        qapp.setStyleSheet(avant)
        CertusTheme.configure("light")


def _avec_un_voisin(qapp, widget):
    from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    hote = QWidget()
    disposition = QVBoxLayout(hote)
    voisin = QPushButton("autre")
    disposition.addWidget(widget)
    disposition.addWidget(voisin)
    hote.resize(320, 140)
    hote.show()
    hote.activateWindow()
    qapp.processEvents()
    voisin.setFocus()
    qapp.processEvents()
    return hote, voisin


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("nom", CONTROLES)
class TestLesControlesQuiSeCochentOuSeGlissentOntUnAnneau:
    def test_prendre_le_focus_dessine_l_anneau_du_theme(self, mode, nom, qapp, feuille_des_fenetres) -> None:
        from PyQt6.QtCore import Qt

        from certus.ui.certus_theme import CertusTheme

        feuille_des_fenetres(mode)
        peint, cible = _controle(nom)
        hote, _voisin = _avec_un_voisin(qapp, peint)
        try:
            repos = _peindre(peint)
            cible.setFocus(Qt.FocusReason.TabFocusReason)
            qapp.processEvents()
            assert cible.hasFocus(), "le controle n'a pas pris le focus : la mesure ne mesurerait rien"
            focus = _peindre(peint)
            primaire = CertusTheme.PRIMARY.lower()
            nouveaux = [
                (x, y)
                for y in range(repos.height())
                for x in range(repos.width())
                if repos.pixel(x, y) != focus.pixel(x, y)
            ]
            de_l_anneau = [p for p in nouveaux if focus.pixelColor(*p).name() == primaire]
            assert len(nouveaux) > 30, f"{mode}/{nom} : {len(nouveaux)} pixel(s) changent au focus -- il est invisible"
            assert len(de_l_anneau) >= 10, (
                f"{mode}/{nom} : {len(nouveaux)} pixels changent, dont {len(de_l_anneau)} a la couleur de l'anneau "
                f"({primaire}) : ce qui change n'est pas l'anneau du theme"
            )
        finally:
            hote.close()

    def test_prendre_le_focus_ne_deplace_rien(self, mode, nom, qapp, feuille_des_fenetres) -> None:
        from PyQt6.QtCore import Qt

        feuille_des_fenetres(mode)
        peint, cible = _controle(nom)
        hote, voisin = _avec_un_voisin(qapp, peint)
        try:
            avant = (peint.geometry(), voisin.geometry(), peint.sizeHint())
            cible.setFocus(Qt.FocusReason.TabFocusReason)
            qapp.processEvents()
            # Qt garde la taille d'avant le focus : on la lui fait recalculer dans l'etat focalise
            if hasattr(peint, "setText"):
                texte = peint.text()
                peint.setText(texte + " ")
                peint.setText(texte)
            elif hasattr(peint, "setTabText"):
                texte = peint.tabText(0)
                peint.setTabText(0, texte + " ")
                peint.setTabText(0, texte)
            qapp.processEvents()
            assert (peint.geometry(), voisin.geometry(), peint.sizeHint()) == avant, (
                f"{mode}/{nom} : prendre le focus a deplace ou redimensionne un controle"
            )
        finally:
            hote.close()
