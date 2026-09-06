"""LA PALETTE SOMBRE DOIT ETRE COMPLETE — etape 3.4.

📏 Mesure du 2026-09-06, avant correctif : **8 jetons gardaient leur valeur CLAIRE en mode
sombre** — les quatre paires de badge `SUCCESS` / `WARNING` / `DANGER` / `INFO`, chacune avec
son `_BG` et son `_TEXT`. `configure()` ne les touchait pas du tout.

## ⚠️ CE N'ETAIT PAS UN ECHEC D'ACCESSIBILITE, et le dire compte

Le texte tenait **5,30 a 6,49:1 sur son propre fond** dans les deux modes : la paire est
lisible, elle l'a toujours ete. Le defaut est **visuel** — en sombre, une puce pastel mesurait
**14,5 a 16,2:1 contre la SURFACE**, donc elle trouait l'ecran.

🔑 **Confondre les deux aurait mene a un mauvais correctif.** Un « echec de contraste » se
repare en augmentant un ratio ; ici il fallait le faire *baisser* du cote fond/surface, tout
en gardant le ratio texte/fond. Ce sont deux grandeurs opposees, et une seule des deux est une
exigence WCAG.

## Ce que ce fichier verrouille

1. Les paires restent **lisibles** dans les deux modes (>= 4,5:1, AA).
2. Elles **changent** entre les modes — sans quoi le correctif serait inerte.
3. La puce reste une **puce** : son fond se distingue de la SURFACE, sans l'éblouir.
4. 🔑 Un aller-retour `dark` → `light` **restaure** les valeurs claires. Sans le point 4, une
   palette qui ne se pose qu'a l'aller laisse l'application en sombre pour toujours.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

PAIRES = ["SUCCESS", "WARNING", "DANGER", "INFO"]

#: AA pour du texte sur son fond.
LISIBILITE = 4.5

#: Une puce doit se voir sans crier. La borne haute est le defaut que l'etape corrige :
#: 📏 avant correctif, les quatre puces etaient a 14,5 a 16,2:1 contre la SURFACE sombre.
PUCE_MIN, PUCE_MAX = 1.15, 4.0


def _ratio(a: str, b: str) -> float:
    from certus.ui.certus_a11y import contrast_ratio

    return contrast_ratio(a, b)


class TestLesPairesRestentLisibles:
    @pytest.mark.parametrize("mode", ["light", "dark"])
    @pytest.mark.parametrize("nom", PAIRES)
    def test_le_texte_du_badge_tient_AA_sur_son_fond(self, mode: str, nom: str) -> None:
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure(mode)
        fond = getattr(CertusTheme, f"{nom}_BG")
        texte = getattr(CertusTheme, f"{nom}_TEXT")
        ratio = _ratio(texte, fond)
        assert ratio >= LISIBILITE, f"{mode}/{nom} : {texte} sur {fond} = {ratio:.2f}:1"


class TestLaPaletteSombreEstDISTINCTE:
    """Sans cela le correctif serait inerte, et le test ci-dessus passerait quand meme."""

    @pytest.mark.parametrize("nom", PAIRES)
    def test_chaque_paire_change_entre_les_modes(self, nom: str) -> None:
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure("light")
        clair = (getattr(CertusTheme, f"{nom}_BG"), getattr(CertusTheme, f"{nom}_TEXT"))
        CertusTheme.configure("dark")
        sombre = (getattr(CertusTheme, f"{nom}_BG"), getattr(CertusTheme, f"{nom}_TEXT"))
        assert clair != sombre, (
            f"{nom} garde ses valeurs claires en sombre : {clair}. C'est exactement le "
            "defaut que l'etape 3.4 corrige."
        )

    @pytest.mark.parametrize("nom", PAIRES)
    def test_la_puce_sombre_ne_troue_plus_l_ecran(self, nom: str) -> None:
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure("dark")
        fond = getattr(CertusTheme, f"{nom}_BG")
        ratio = _ratio(fond, CertusTheme.SURFACE)
        assert PUCE_MIN <= ratio <= PUCE_MAX, (
            f"{nom} : fond de puce a {ratio:.2f}:1 de la SURFACE. Sous {PUCE_MIN} elle "
            f"disparait, au-dessus de {PUCE_MAX} elle eblouit — avant correctif : ~15:1."
        )


class TestLeRetourAuClairRESTAURE:
    """🔑 Le piege d'une palette posee seulement a l'aller."""

    def test_un_aller_retour_rend_les_valeurs_claires(self) -> None:
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure("light")
        avant = {n: getattr(CertusTheme, f"{n}_BG") for n in PAIRES}
        CertusTheme.configure("dark")
        CertusTheme.configure("light")
        apres = {n: getattr(CertusTheme, f"{n}_BG") for n in PAIRES}
        assert avant == apres, (
            f"apres un passage en sombre, le mode clair ne revient pas : {avant} -> {apres}"
        )


class TestLesJetonsMORTSNeReviennentPas:
    """📏 Mesure : `DARK_BORDER` et `DARK_TEXT_SUB` avaient ZERO usage dans tout le depot.

    ⚠️ **Les quatre autres `DARK_*` NE SONT PAS morts** — l'etape annonçait « 6 jetons
    morts », c'etait faux. `DARK_BACKGROUND`, `DARK_SURFACE`, `DARK_CARD` et
    `DARK_TEXT_MAIN` construisent la **palette Qt** en mode sombre. Les supprimer casserait
    le rendu de tout widget qui ne passe pas par la feuille de style.
    """

    @pytest.mark.parametrize("mort", ["DARK_BORDER", "DARK_TEXT_SUB"])
    def test_ils_restent_supprimes(self, mort: str) -> None:
        from certus.ui.certus_theme import CertusTheme

        assert not hasattr(CertusTheme, mort), (
            f"{mort} est revenu. Il n'avait aucun usage ; s'il en a un desormais, dis "
            "lequel dans le meme changement."
        )

    @pytest.mark.parametrize(
        "vivant", ["DARK_BACKGROUND", "DARK_SURFACE", "DARK_CARD", "DARK_TEXT_MAIN"]
    )
    def test_les_VIVANTS_ne_sont_pas_emportes(self, vivant: str) -> None:
        """Controle negatif du menage : il ne doit pas deborder."""
        from certus.ui.certus_theme import CertusTheme

        assert hasattr(CertusTheme, vivant), (
            f"{vivant} a ete supprime, or il sert a batir la palette Qt en mode sombre"
        )
