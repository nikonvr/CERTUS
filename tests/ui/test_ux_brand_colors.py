"""CHAQUE MODULE DOIT AVOIR SA COULEUR — etape 3.9.

📏 Mesure du 2026-09-06 sur les 10 tuiles du HUB, avant correctif :

    DESIGN #8b5cf6 · RE #10b981 · STRAT #10b981 · INDEX #3b82f6 · INDEX SPLINE #3b82f6
    FIELD #8b5cf6 · SMOOTHER #15803d · SUBSTRATE #3b82f6 · METAL x2 #64748b

**Quatre couleurs pour dix modules.** RE portait l'emeraude de STRAT, FIELD le violet de
DESIGN, SUBSTRATE le bleu d'INDEX.

🔴 **Et SMOOTHER portait `#15803d`, qui est le jeton semantique `SUCCESS`** — pas une couleur
de marque du tout. Peindre un lanceur avec la couleur qui signifie « operation reussie » n'est
pas seulement incoherent : cela use un signal qui doit rester rare pour rester lisible.

## ⚠️ L'ETAPE 3.9 SE CONTREDIT, ET IL A FALLU TRANCHER

Elle demande d'« ajouter un jeton pour RE, FIELD, SMOOTHER, SUBSTRATE » **et** de « faire
suivre la couleur des tuiles a `category` ». Les deux ne tiennent pas sur le meme canal :
**six modules sont `core_workflow`**, ils deviendraient tous identiques et les quatre jetons
neufs ne serviraient a rien.

**Retenu : un jeton par module.** Dans une grille de dix lanceurs, la couleur sert a
RECONNAITRE une tuile ; le groupement par categorie se dit mieux par la mise en page. La
seconde moitie de l'etape n'est pas implantee, et c'est un choix, pas un oubli.

## La contrainte d'architecture, qui explique la duplication d'origine

`certus/core/certus_hub_config.py` recopiait les hexadecimaux au lieu de lire `CertusTheme`,
et **ce n'etait pas une negligence** : `core` n'a pas le droit d'importer `certus.ui`. La
source unique devait donc DESCENDRE dans la couche basse, pas monter. C'est ce qui est fait :
le catalogue definit, le theme lit.
"""

from __future__ import annotations

import pytest

#: L'icone de la tuile est peinte en BLANC sur la couleur de marque
#: (`certus_hub_widgets.py` : `background-color: {accent}` puis `color: white`).
#: WCAG 1.4.11 demande 3:1 pour un objet graphique.
SEUIL_ICONE = 3.0

#: 🔴 STRAT est SOUS le seuil et n'a PAS ete change. `#10b981` donne **2,54:1** pour une
#: icone blanche. C'est une couleur d'identite deja etablie : la modifier est une decision
#: du proprietaire du projet, pas une correction de routine. Elle est donc consignee ici
#: plutot que corrigee en silence — sans cette entree, le defaut disparaitrait de la vue.
CONNUES_SOUS_LE_SEUIL = {"STRAT"}


def _catalogue():
    from certus.core.certus_hub_config import HUB_APP_CATALOG

    return HUB_APP_CATALOG


def _couleurs_par_module() -> dict[str, str]:
    return {app["title"]: app["color"] for app in _catalogue()}


#: 🔑 Deux partages sont LEGITIMES et doivent le rester. `INDEX` / `INDEX SPLINE` et
#: `METAL SINGLE` / `METAL BILAYER` sont des outils FRERES sur le meme sujet : une couleur
#: de famille se lit comme une parente. Leur imposer quatre teintes differentes
#: DETRUIRAIT de l'information au lieu d'en ajouter.
#:
#: ⚠️ C'est pourquoi ce fichier ne teste pas « toutes distinctes ». Une premiere version le
#: faisait, et elle aurait force a inventer six couleurs au lieu de quatre, en cassant deux
#: parentes voulues. **L'etape 3.9 ne nomme d'ailleurs que quatre modules** — RE, FIELD,
#: SMOOTHER, SUBSTRATE — ce qui confirme la lecture par familles.
FRATRIES = [{"INDEX", "INDEX SPLINE"}, {"METAL SINGLE", "METAL BILAYER"}]


class TestChaqueFAMILLEAUneCouleurDistincte:
    def test_aucune_couleur_n_est_partagee_HORS_fratrie(self) -> None:
        couleurs = _couleurs_par_module()
        vus: dict[str, set[str]] = {}
        for module, couleur in couleurs.items():
            vus.setdefault(couleur, set()).add(module)

        fautives = {}
        for couleur, modules in vus.items():
            if len(modules) > 1 and not any(modules <= f for f in FRATRIES):
                fautives[couleur] = modules
        assert not fautives, (
            "des modules SANS PARENTE partagent une couleur, donc la tuile ne les "
            "distingue pas : "
            + ", ".join(f"{c} -> {'/'.join(sorted(m))}" for c, m in fautives.items())
        )

    def test_les_dix_modules_sont_couverts(self) -> None:
        couleurs = _couleurs_par_module()
        assert len(couleurs) == 10, f"{len(couleurs)} modules au catalogue, 10 attendus"
        assert all(couleurs.values()), "un module n'a pas de couleur"

    def test_les_fratries_partagent_TOUJOURS(self) -> None:
        """Controle negatif de la tolerance : elle ne doit pas devenir un fourre-tout.

        Si une fratrie cesse de partager, ce n'est pas forcement une faute -- mais alors
        l'entree ci-dessus ne sert plus a rien et doit etre retiree, pas laissee a couvrir
        un partage qui n'existe plus.
        """
        couleurs = _couleurs_par_module()
        for fratrie in FRATRIES:
            teintes = {couleurs[m] for m in fratrie if m in couleurs}
            assert len(teintes) == 1, (
                f"{sorted(fratrie)} ne partage plus sa couleur ({teintes}). Retire "
                "l'entree de FRATRIES si c'est voulu."
            )


class TestAucuneCouleurSEMANTIQUENEstDetournee:
    """🔑 Un jeton de sens ne doit pas servir d'identite : le signal s'use."""

    @pytest.mark.parametrize("semantique", ["SUCCESS", "WARNING", "DANGER", "INFO"])
    def test_aucun_module_ne_porte_un_jeton_de_sens(self, semantique: str) -> None:
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure("light")
        valeur = getattr(CertusTheme, semantique).lower()
        coupables = [m for m, c in _couleurs_par_module().items() if c.lower() == valeur]
        assert not coupables, (
            f"{', '.join(coupables)} est peint avec le jeton {semantique} ({valeur}). "
            "SMOOTHER l'etait avec SUCCESS avant l'etape 3.9."
        )


class TestLIconeBlancheResteLISIBLE:
    """La couleur de marque est le FOND de la tuile d'icone, l'icone est blanche."""

    @pytest.mark.parametrize("module", sorted(_couleurs_par_module()))
    def test_le_blanc_tient_le_seuil_sur_la_tuile(self, module: str) -> None:
        from certus.ui.certus_a11y import contrast_ratio

        couleur = _couleurs_par_module()[module]
        ratio = contrast_ratio("#ffffff", couleur)
        if module in CONNUES_SOUS_LE_SEUIL:
            assert ratio < SEUIL_ICONE, (
                f"{module} passe desormais le seuil ({ratio:.2f}:1). Retire-le de "
                "CONNUES_SOUS_LE_SEUIL : une exception qui ne mord plus cache un progres."
            )
            return
        assert ratio >= SEUIL_ICONE, (
            f"{module} : icone blanche a {ratio:.2f}:1 sur {couleur}, seuil {SEUIL_ICONE}"
        )


class TestUneSeuleSourcePourLesCouleurs:
    """« Un fait, un seul endroit » — applique au code, pas seulement aux documents."""

    def test_le_theme_lit_le_catalogue_au_lieu_de_recopier(self) -> None:
        from certus.core import certus_hub_config as source
        from certus.ui.certus_theme import CertusTheme

        for nom in ("INDEX", "DESIGN", "METAL", "STRAT"):
            attendu = getattr(source, f"HUB_BRAND_{nom}")
            obtenu = getattr(CertusTheme, f"BRAND_{nom}")
            assert obtenu == attendu, (
                f"BRAND_{nom} vaut {obtenu} dans le theme et {attendu} au catalogue. "
                "Les deux valeurs ont diverge, ce qui est exactement le defaut que la "
                "source unique doit empecher."
            )

    def test_la_couche_basse_n_importe_pas_la_couche_haute(self) -> None:
        """Le catalogue reste une feuille : c'est ce qui rend la source unique possible."""
        import ast
        from pathlib import Path

        chemin = Path(__file__).resolve().parents[2] / "certus" / "core" / "certus_hub_config.py"
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        importes = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom) and noeud.module:
                importes.add(noeud.module)
            elif isinstance(noeud, ast.Import):
                importes.update(a.name for a in noeud.names)
        interdits = {m for m in importes if m.startswith("certus.ui")}
        assert not interdits, (
            f"certus_hub_config importe {interdits} : `core` ne doit jamais importer `ui`. "
            "C'est cette regle qui a cause la duplication d'origine des hexadecimaux."
        )
