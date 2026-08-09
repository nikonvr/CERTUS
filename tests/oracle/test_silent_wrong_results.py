"""Safeguards against FALSE AND SILENT results.

Each test in this file corresponds to a defect actually present in the code, where
a bad result was produced without exception, without warning and without log.
This is the most expensive category: it is neither visible in testing nor at runtime, and
contaminates published data.

Every test was verified as FAILING on pre-patch code.
"""

from __future__ import annotations

import numpy as np
import pytest


class TestSpectreEnMiroir:
    """The smoothing rematched the values ​​on the sorted abscissa, not that of the file."""

    def test_ordre_decroissant_preserve_appariement(self) -> None:
        """A spectrum measured in DECREASING lambda must not come out inverted.

        GUARD: before fix, the error reached 39.99 %T points — the curve
        smoothed was the exact mirror of the measurement. Standard output of many
        spectrophotometers, therefore common and not exotic case.
        """
        from certus.utils.certus_spectral_preproc import smooth_spectrum_auto

        lam_asc = np.linspace(400.0, 900.0, 101)
        t_asc = 10.0 + 0.08 * (lam_asc - 400.0)

        y_asc, _ = smooth_spectrum_auto(lam_asc, t_asc)
        y_desc, _ = smooth_spectrum_auto(lam_asc[::-1], t_asc[::-1])

        err_asc = float(np.max(np.abs(y_asc - t_asc)))
        err_desc = float(np.max(np.abs(y_desc - t_asc[::-1])))

        #The error must be of the same order in both directions: it is the residue of
        #smoothing, it should not depend on the reading order of the file.
        assert err_desc == pytest.approx(err_asc, abs=0.05), (
            f"ordre croissant err={err_asc:.4f} mais decroissant err={err_desc:.4f} : "
            "le spectre est apparie a l'envers"
        )

    def test_longueur_preservee_avec_nan(self) -> None:
        """Une seule cellule vide ne doit pas raccourcir le vecteur de sortie.

        CAUTION: internal deduplication returned a shorter vector, which
        faisait lever `ValueError: Length of values does not match length of index`
        at the caller pandas.
        """
        from certus.utils.certus_spectral_preproc import smooth_spectrum_auto

        lam = np.linspace(400.0, 900.0, 101)
        transmittance = 10.0 + 0.08 * (lam - 400.0)
        transmittance[5] = np.nan

        y_smoothed, _ = smooth_spectrum_auto(lam, transmittance)

        assert len(y_smoothed) == len(lam)


class TestDetectionTypeDonnees:
    """A "Reflectance" header was classified as TRANSMISSION."""

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

        The caller then switched to a statistical heuristic, the first of which
        rule is `average > 0.5 -> "T"`, which classifies any high reflectivity mirror
        en transmission. Le type pilote ensuite tout le fit n,k.
        """
        from certus.utils.certus_index_utils import _detect_type_from_column_name

        assert _detect_type_from_column_name(header) == expected

    @pytest.mark.parametrize("header", ["theta", "total", "temperature", "rho", "remarks"])
    def test_pas_de_faux_positifs(self, header: str) -> None:
        """A column whose name begins with t or r should not be captured."""
        from certus.utils.certus_index_utils import _detect_type_from_column_name

        assert _detect_type_from_column_name(header) == "unknown"


class TestFiltreNonFini:
    """`fastmath=True` removed the `isfinite` filter from the cost calculation."""

    @pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
    def test_valeurs_non_finies_exclues_du_cout(self, bad_value: float) -> None:
        """GUARD: a single non-finite point returned a NaN cost to the optimizer.

        `fastmath=True` implique les drapeaux LLVM `nnan`/`ninf`, qui autorisent le
        compiler to simply remove the `np.isfinite(...)` test.
        The optimizer then received NaN and diverged without a message.
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
    """An unknown material returned air (n = 1), making the layer invisible."""

    def test_materiau_inconnu_leve_au_lieu_de_renvoyer_air(self) -> None:
        """GUARD: a typo in a material name produced a layer
        d'indice 1,0 — optiquement absente — et le calcul continuait sur un empilement
        amputee, without exception or newspaper.
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
