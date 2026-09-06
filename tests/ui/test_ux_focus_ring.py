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
        "selecteur,repos",
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
