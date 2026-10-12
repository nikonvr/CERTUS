"""Le corridor d'indice du saphir (2026-10-12) repose sur des hypotheses que ces tests gardent, une par une.

`scripts/_saphir_modele.py` ajuste, sur les mesures de la base de depots, un indice de saphir Sellmeier + dn(lambda) avec des films libres. Le
resultat (reports/SAPHIR_corridor_indice_2026-10-12.md) tient en quatre faits, et chacun est ici un test :

  1. le modele oblique du depot est Fresnel pour le saphir nu, en s et en p (sinon la polarisation du faisceau n'a pas le sens qu'on lui donne) ;
  2. un niveau planté sur des spectres ABSOLUS est retrouve, et une erreur sur la fraction p du faisceau le decale de ~0,025 par unite ;
  3. ce qui fixe le niveau, c'est la photometrie ABSOLUE : le saphir nu, ou des films mesures en T ET en R. Un film en T seul, ou un
     spectre normalise au substrat, absorbe le meme decalage sans perdre un chi2 ;
  4. aucune absorption du saphir sous 3,9 um (un plancher de k = 5e-7 y avait ete pose a tort : 0,2 % de T, soit 0,008 d'indice, que dn compensait).

Le test 3 est le controle negatif du test 2 : si le test 2 passait parce que l'ajustement retrouve toujours ce qu'on lui donne, le test 3 echouerait.
(Premiere version fausse : elle opposait « absolu » a « normalise » et croyait que la normalisation creait la degenerescence. Une mutation du modele
l'a refute : un denominateur FIXE laissait le test vert. C'est l'absence de R et du saphir nu qui compte, pas la division.)
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import _saphir_modele as sm  # noqa: E402

FENETRE = (1000.0, 3300.0)


def _fresnel_lame(n: float, pol: str, theta_deg: float = 8.0) -> tuple[float, float]:
    """(R, T) totaux d'une lame transparente a faces paralleles, incoherente, ecrits a la main : 2R1/(1+R1) et (1-R1)/(1+R1)."""
    th = np.deg2rad(theta_deg)
    ct, ctt = np.cos(th), np.sqrt(1 - (np.sin(th) / n) ** 2)
    r = (ct - n * ctt) / (ct + n * ctt) if pol == "s" else (n * ct - ctt) / (n * ct + ctt)
    r1 = abs(r) ** 2
    return 2 * r1 / (1 + r1), (1 - r1) / (1 + r1)


@pytest.mark.parametrize("pol", ["s", "p"])
@pytest.mark.parametrize("lam_nm", [600.0, 1500.0, 3500.0])
def test_the_oblique_plate_of_the_repo_is_fresnel_for_the_bare_sapphire(pol: str, lam_nm: float) -> None:
    ns = sm.indice_saphir(np.array([lam_nm]))
    r, t = sm.calc_spectrum_oblique_backside_vectorized(
        np.array([lam_nm]), np.zeros((1, 0), dtype=complex), np.zeros(0), ns.astype(complex), 8.0, pol, sm.SUBSTRATE_NM
    )
    r_ref, t_ref = _fresnel_lame(float(ns[0]), pol)

    assert float(r[0]) == pytest.approx(r_ref, abs=1e-9)
    assert float(t[0]) == pytest.approx(t_ref, abs=1e-9)


def test_s_and_p_differ_by_more_than_half_a_percent_at_8_degrees() -> None:
    """Le fait qui fait de la polarisation du faisceau l'incertitude dominante : R_s - R_p = 0,58 % a 8 degres."""
    r_s, _ = _fresnel_lame(1.7557, "s")
    r_p, _ = _fresnel_lame(1.7557, "p")

    assert r_s - r_p == pytest.approx(0.0058, abs=0.0002)


def _probleme_absolu_synthetique(niveau: float, f: float, noms=("nu", "Nb")):
    refs = sm.references_saphir()
    sk = sm.noeuds_sigma(*FENETRE, 3)
    prob0 = sm.ProblemeAbsolu(sm.echantillons_absolus(refs, sk, *FENETRE, noms=noms), sk)
    x = prob0.x_start.copy()
    x[prob0.i_dn:prob0.i_dn + prob0.J] = niveau
    x[prob0.i_ft] = x[prob0.i_fr] = f
    donnees = []
    for i, s in enumerate(prob0.samples):
        t, r = prob0.TR(x, i)
        donnees.append(replace(s, T=t, R=r))  # sans bruit
    return sm.ProblemeAbsolu(donnees, sk)


def _niveau_retrouve(prob, niveau_fixe=None) -> float:
    fixed = prob.fixe_polarisation(0.5)
    if niveau_fixe is not None:
        fixed.update(prob.fixe_niveau(niveau_fixe))
    x, _res = prob.ajuster(prob.x_start, fixed=fixed)
    return float(np.mean(prob.dn_of(x)))


@pytest.mark.parametrize("niveau", [-0.0075, -0.004, 0.003])
def test_a_planted_level_is_recovered_from_absolute_spectra(niveau: float) -> None:
    prob = _probleme_absolu_synthetique(niveau, f=0.5)

    assert _niveau_retrouve(prob) == pytest.approx(niveau, abs=2e-4)


def test_a_wrong_beam_polarization_shifts_the_level_by_about_0p025_per_unit_of_f() -> None:
    """Le faisceau est en realite a f = 0,65 ; on suppose 0,5 : le niveau retrouve est decale, de ~-0,0035 (mesure sur donnees simulees)."""
    prob = _probleme_absolu_synthetique(0.0, f=0.65)

    decalage = _niveau_retrouve(prob)

    assert -0.0050 < decalage < -0.0020


def _cout_d_un_decalage(prob, decalage: float = -0.004) -> float:
    """Ce que coute au chi2 un saphir decale de `decalage`, tout le reste (films, epaisseurs) etant reajuste."""
    fixed = prob.fixe_polarisation(0.5)
    x_ref, _ = prob.ajuster(prob.x_start, fixed={**fixed, **prob.fixe_niveau(0.0)})
    x_dec, _ = prob.ajuster(x_ref, fixed={**fixed, **prob.fixe_niveau(decalage)})
    return prob.chi2(x_dec) - prob.chi2(x_ref)


def test_a_film_measured_in_T_alone_cannot_see_the_sapphire_level_but_T_and_R_can() -> None:
    """LE FAIT QUI REGLE LA QUESTION. Un film libre absorbe un decalage plat de T sans perdre un chi2 ; R, lui, ne s'y prete pas.

    Mesure (donnees simulees sans bruit, niveau 0, decalage -0,004) : 1 film T seul 0,0 ; R seul 13,8 ; T et R 21,8 ; le saphir nu T seul 47.
    Les spectres certifies sont des T NORMALISES : ils n'ont ni la photometrie absolue du saphir nu ni le R des films.
    """
    t_seul = _cout_d_un_decalage(replace_problem(_probleme_absolu_synthetique(0.0, 0.5, noms=("Nb",)), utiliser_r=False))
    t_et_r = _cout_d_un_decalage(_probleme_absolu_synthetique(0.0, 0.5, noms=("Nb",)))

    assert t_seul < 1.0
    assert t_et_r > 10.0


def replace_problem(prob, **kw):
    return sm.ProblemeAbsolu(prob.samples, prob.sk_dn, **{"poids_r_nu": prob.poids_r_nu, "utiliser_t": prob.utiliser_t, "utiliser_r": prob.utiliser_r, **kw})


def test_the_bare_sapphire_alone_fixes_the_level_in_absolute_photometry() -> None:
    assert _cout_d_un_decalage(_probleme_absolu_synthetique(0.0, 0.5, noms=("nu",))) > 50.0


def test_a_level_costs_nothing_on_a_normalised_spectrum() -> None:
    """Un spectre T(film + substrat) / T(substrat nu) d'une reference certifiee : le saphir peut etre decale de -0,004 sans perte de chi2."""
    refs = sm.references_saphir()
    sk = sm.noeuds_sigma(450.0, 5200.0, 3)
    film = sm.film_normalise("pe-ta2", refs["pe-ta2"], sk)
    seul = sm.ProblemeNormalise([film], sk)
    film = replace(film, y=seul.modele(seul.x_start, 0))  # un spectre sans bruit, de saphir = Sellmeier
    seul = sm.ProblemeNormalise([film], sk)
    y_ref, _ = seul.ajuster(seul.x_start, fixed={seul.i_dn + j: 0.0 for j in range(seul.J)})
    y_dec, _ = seul.ajuster(y_ref, fixed={seul.i_dn + j: -0.004 for j in range(seul.J)}, max_nfev=300)

    assert seul.chi2(y_dec) - seul.chi2(y_ref) < 1.0


def test_the_sapphire_does_not_absorb_below_3900_nm_and_does_beyond() -> None:
    k = sm.ks_saphir(np.array([1000.0, 2000.0, 3500.0, 3899.0, 4000.0, 4500.0, 5200.0]))

    assert np.all(k[:4] == 0.0)  # un plancher y serait echange contre l'indice : 0,2 % de T = 0,008 de n
    assert k[4] == pytest.approx(1.5e-6, rel=0.6)
    assert k[5] == pytest.approx(5.5e-6, rel=0.6)
    assert k[6] == pytest.approx(4.5e-5, rel=0.4)
    assert np.all(np.diff(k[3:]) > 0)


def test_the_references_that_start_the_absolute_films_are_in_the_database() -> None:
    refs = sm.references_saphir()

    for nom in sm.DEPART_ABSOLU.values():
        assert nom in refs, nom
        assert 2900.0 < refs[nom]["p"][0] < 3400.0  # un film de 3 um : le depart d'un film absolu doit avoir la bonne epaisseur a 3 % pres
