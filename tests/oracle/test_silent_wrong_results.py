"""Garde-fous contre les résultats FAUX ET SILENCIEUX.

Chaque test de ce fichier correspond à un défaut réellement présent dans le code, où
un mauvais résultat était produit sans exception, sans avertissement et sans journal.
C'est la catégorie la plus coûteuse : elle ne se voit ni en test ni à l'exécution, et
contamine les données publiées.

Chaque test a été vérifié comme ÉCHOUANT sur le code d'avant correctif.
"""

from __future__ import annotations

import numpy as np
import pytest


class TestSpectreEnMiroir:
    """Le lissage réappariait les valeurs sur l'abscisse triée, pas celle du fichier."""

    def test_ordre_decroissant_preserve_appariement(self) -> None:
        """Un spectre mesuré en lambda DÉCROISSANT ne doit pas ressortir inversé.

        GARDE-FOU : avant correctif, l'erreur atteignait 39,99 points de %T — la courbe
        lissée était le miroir exact de la mesure. Sortie standard de nombreux
        spectrophotomètres, donc cas courant et non exotique.
        """
        from certus.utils.certus_spectral_preproc import smooth_spectrum_auto

        lam_asc = np.linspace(400.0, 900.0, 101)
        t_asc = 10.0 + 0.08 * (lam_asc - 400.0)

        y_asc, _ = smooth_spectrum_auto(lam_asc, t_asc)
        y_desc, _ = smooth_spectrum_auto(lam_asc[::-1], t_asc[::-1])

        err_asc = float(np.max(np.abs(y_asc - t_asc)))
        err_desc = float(np.max(np.abs(y_desc - t_asc[::-1])))

        # L'erreur doit être du même ordre dans les deux sens : c'est le résidu de
        # lissage, il ne doit pas dépendre de l'ordre de lecture du fichier.
        assert err_desc == pytest.approx(err_asc, abs=0.05), (
            f"ordre croissant err={err_asc:.4f} mais decroissant err={err_desc:.4f} : "
            "le spectre est apparie a l'envers"
        )

    def test_longueur_preservee_avec_nan(self) -> None:
        """Une seule cellule vide ne doit pas raccourcir le vecteur de sortie.

        GARDE-FOU : la déduplication interne renvoyait un vecteur plus court, ce qui
        faisait lever `ValueError: Length of values does not match length of index`
        chez l'appelant pandas.
        """
        from certus.utils.certus_spectral_preproc import smooth_spectrum_auto

        lam = np.linspace(400.0, 900.0, 101)
        transmittance = 10.0 + 0.08 * (lam - 400.0)
        transmittance[5] = np.nan

        y_smoothed, _ = smooth_spectrum_auto(lam, transmittance)

        assert len(y_smoothed) == len(lam)


class TestDetectionTypeDonnees:
    """Un en-tête « Reflectance » était classé en TRANSMISSION."""

    @pytest.mark.parametrize(
        "header, expected",
        [
            ("Transmittance", "T"),
            ("Transmission", "T"),
            ("Trans", "T"),
            ("T", "T"),
            ("%T", "T"),
            ("Reflectance", "R"),
            ("Reflectance (%)", "R"),
            ("Reflection", "R"),
            ("R_exp", "R"),
            ("Refl", "R"),
            ("R", "R"),
            ("%R", "R"),
        ],
    )
    def test_entetes_courants_reconnus(self, header: str, expected: str) -> None:
        """GARDE-FOU : « Reflectance » et « R_exp » renvoyaient `unknown`.

        L'appelant basculait alors sur une heuristique statistique dont la première
        règle est `moyenne > 0,5 -> "T"`, ce qui classe tout miroir haute réflectivité
        en transmission. Le type pilote ensuite tout le fit n,k.
        """
        from certus.utils.certus_index_utils import _detect_type_from_column_name

        assert _detect_type_from_column_name(header) == expected

    @pytest.mark.parametrize("header", ["theta", "total", "temperature", "rho", "remarks"])
    def test_pas_de_faux_positifs(self, header: str) -> None:
        """Une colonne dont le nom commence par t ou r ne doit pas être capturée."""
        from certus.utils.certus_index_utils import _detect_type_from_column_name

        assert _detect_type_from_column_name(header) == "unknown"


class TestFiltreNonFini:
    """`fastmath=True` supprimait le filtre `isfinite` du calcul de coût."""

    @pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
    def test_valeurs_non_finies_exclues_du_cout(self, bad_value: float) -> None:
        """GARDE-FOU : un seul point non fini renvoyait un coût NaN à l'optimiseur.

        `fastmath=True` implique les drapeaux LLVM `nnan`/`ninf`, qui autorisent le
        compilateur à supprimer purement et simplement le test `np.isfinite(...)`.
        L'optimiseur recevait alors NaN et divergeait sans message.
        """
        from certus.physics.gradient_utils import compute_mse_vectorized

        calculated = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        calculated[2] = bad_value
        targets = np.zeros(7)
        weights = np.ones(7)

        cost, count = compute_mse_vectorized(calculated, targets, weights)

        assert count == 6, f"le point non fini n'a pas ete exclu (count={count})"
        assert np.isfinite(cost), f"cout non fini renvoye a l'optimiseur : {cost}"


class TestMateriauIntrouvable:
    """Un matériau inconnu renvoyait de l'air (n = 1), rendant la couche invisible."""

    def test_materiau_inconnu_leve_au_lieu_de_renvoyer_air(self) -> None:
        """GARDE-FOU : une faute de frappe dans un nom de matériau produisait une couche
        d'indice 1,0 — optiquement absente — et le calcul continuait sur un empilement
        amputé, sans exception ni journal.
        """
        from certus.utils.certus_strat_db import RobustMaterialDatabase

        database = RobustMaterialDatabase.__new__(RobustMaterialDatabase)
        database.materials = {}
        database.SELLMEIER_COEFFS = {}

        with pytest.raises(KeyError):
            database.get_refractive_index("Nb2O5_faute_de_frappe", 550.0)

        with pytest.raises(KeyError):
            database.get_refractive_clues_vectorized(
                "Nb2O5_faute_de_frappe", np.array([550.0])
            )
