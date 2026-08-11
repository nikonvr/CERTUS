"""POEM — Percent of Optical Extrema Monitoring, et les mecanismes qui l'entourent.

Ces tests verrouillent ce que `simulate_growth_kernel` doit produire, du point de
vue de la PHYSIQUE et non de l'implementation. Reference :

  - Arsac, these 2025, §2.3.2.2, eq. 2.2 a 2.4 (POEM et Quasi-Swing)
  - Zideluns, Lemarchand, Arhilger, Hagedorn, Lumeau, Opt. Express 29, 33398 (2021)

🔴 PERIMETRE DU MODELE. Le simulateur ne modelise QUE le monitoring par coupure
de niveau (trigger). Le monitoring par point tournant (TPM) n'est pas modelise.
C'est ce qui explique — et rend CORRECT — le resultat de
`test_qwot_at_own_l0_is_not_monitorable_by_trigger`.

⚠ PHYSICAL THRESHOLD. Below 0.05 nm there is no more thickness: it is less
of an atom. Any assertion of equality of thickness is judged by this yardstick, not by
precision machine.

🔴 PERIMETER — ONLY 48-LAYER DICHROIC IS A VALID EXAMPLE.
👤 The Physicist, 2026-08-06. The stack used here is a TOY: eight quarter layers
wave at 1500 nm, chosen because it is small, controlled and fast. It is used to check
MECHANISMS — identity to the nearest bit, does the noise reach the anchors, the sentinel
does it bear its cause — and **NO PHYSICAL CONCLUSION CAN BE DRAWN FROM IT**.

Any digit marked 📏 in this file comes from `example/example_strat/
JSON-strat-example.json` via `scripts/probe_anchor_noise.py`, never a toy. Never
measure a crash rate, yield or spectral error on this stack
to conclude anything: the justice of the peace is the 48 layers.
"""

import numpy as np
import pytest

import certus_physics  # noqa: F401  (facade : evite l'import circulaire)
from certus_physics import simulate_growth_kernel

# --------------------------------------------------------------------------- #
#Reference stack: 8 quarter-wave layers at 1500 nm.
# Volontairement le meme materiau que tests/integration/test_strat_robustness.py
# so that both files talk about the same object.
# --------------------------------------------------------------------------- #
N_H = complex(2.3, 0.0)
N_L = complex(1.45, 0.0)
N_SUB = complex(1.52, 0.0)
L0 = 1500.0
P_THICK = np.array(
    [L0 / (4.0 * (2.3 if i % 2 == 0 else 1.45)) for i in range(8)],
    dtype=np.float64,
)
PROBE = 2.0
NM_ATTENUATE = 0

#: Below, a difference in thickness has no physical meaning (< 1 atom).
ATOM_NM = 0.05

#: Sentinelle « depot non terminable » : le noyau renvoie nominal + 1e6.
CRASH_SENTINEL = 1e5


def _grow(i_layer, prev, wl, noise=0.0, block_start=-1):
    val, _dyn, _, _, _ = simulate_growth_kernel(
        P_THICK,
        i_layer,
        np.asarray(prev, dtype=np.float64),
        float(wl),
        N_H,
        N_L,
        N_SUB,
        PROBE,
        float(noise),
        1.0,
        NM_ATTENUATE,
        block_start,
    )
    return val


def _gain(i_layer, wl, block_start=-1, probe_nm=1.0):
    """Gain de compensation : |Delta_d_i| / delta_amont, a bruit NUL."""
    prev_nom = P_THICK[:i_layer].copy()
    prev_prt = prev_nom.copy()
    prev_prt[i_layer - 1] += probe_nm
    v_ref = _grow(i_layer, prev_nom, wl, block_start=block_start)
    v_prt = _grow(i_layer, prev_prt, wl, block_start=block_start)
    if v_ref > CRASH_SENTINEL or v_prt > CRASH_SENTINEL:
        return float("nan")
    return abs(v_prt - v_ref) / probe_nm


# =========================================================================== #
# 1. La cible est figee sur le NOMINAL
# =========================================================================== #

@pytest.mark.parametrize("i_layer", [3, 5, 7])
@pytest.mark.parametrize("wl", [1300.0, 1700.0, 1900.0])
def test_nominal_history_and_zero_noise_gives_nominal_thickness(i_layer, wl):
    """Without upstream error or noise, the layer should come out NOMINAL.

    C'est la condition de coherence minimale du niveau de declenchement : quand
    l'empilement reel EST l'empilement nominal, la cible calculee sur le nominal
    is exactly the transmission achieved at the nominal thickness, and POEM the
    transferred to extrema which are the same on both sides.
    """
    val = _grow(i_layer, P_THICK[:i_layer], wl)
    assert val < CRASH_SENTINEL, f"depot declare non terminable a {wl:.0f} nm"
    assert abs(val - P_THICK[i_layer]) < ATOM_NM


# =========================================================================== #
#2. Compensation exists, and it DISCRIMINATES wavelengths
# =========================================================================== #

def test_compensation_gain_discriminates_wavelengths():
    """Le gain doit varier de plus d'un ordre de grandeur selon lambda.

    C'est toute la justification du critere : si le gain etait a peu pres le meme
    partout, il n'apporterait rien au classement de la Phase A. Mesure sur cet
    stacking, layer 7: 0.07 at 1400 nm versus 10.9 at 1200 nm.
    """
    gains = {wl: _gain(7, wl) for wl in (1200.0, 1300.0, 1400.0, 1700.0, 2000.0)}
    finite = {w: g for w, g in gains.items() if not np.isnan(g)}
    assert len(finite) >= 4, f"trop de plantages pour conclure : {gains}"

    lo, hi = min(finite.values()), max(finite.values())
    assert lo < 0.5, f"aucune longueur d'onde n'amortit : {finite}"
    assert hi > 2.0, f"aucune longueur d'onde n'amplifie : {finite}"
    assert hi / max(lo, 1e-6) > 10.0, f"critere non discriminant : {finite}"


def test_compensation_gain_below_one_means_upstream_error_is_damped():
    """gain < 1 must mean, literally, that the upstream error shrinks."""
    probe = 1.0
    wl = 1400.0  # amortit fortement sur cet empilement
    g = _gain(7, wl, probe_nm=probe)
    assert not np.isnan(g)
    assert g < 1.0

    prev_prt = P_THICK[:7].copy()
    prev_prt[6] += probe
    delta_out = abs(_grow(7, prev_prt, wl) - _grow(7, P_THICK[:7], wl))
    assert delta_out < probe, (
        f"gain={g:.3f} annonce un amortissement mais |Delta_d|={delta_out:.4f} nm "
        f"n'est pas inferieur a la sonde de {probe} nm"
    )


# =========================================================================== #
# 3. L'historique du bloc monochromatique change le resultat
# =========================================================================== #

@pytest.mark.parametrize("wl", [1300.0, 1700.0])
def test_block_history_changes_the_compensation(wl):
    """With lambda unchanged, the extrema of the previous layers can be used.

    POEM scanning covers the entire length of the BLOCK, not just the layer
    current: passing block_start_layer must therefore change the breakpoint. A
    resultat identique signifierait que l'historique n'est pas lu — c'est le
    fault that commit 87bb056 corrected, and this test is there so that it does not
    revienne pas.
    """
    sans = _gain(7, wl, block_start=-1)
    avec = _gain(7, wl, block_start=4)
    assert not np.isnan(sans) and not np.isnan(avec)
    assert abs(avec - sans) > 1e-3, (
        f"l'historique du bloc n'a aucun effet a {wl:.0f} nm "
        f"(sans={sans:.4f}, avec={avec:.4f})"
    )


def test_block_history_is_bounded_by_max_lookback():
    """The return is limited to 4 layers: beyond that, no more change."""
    a = _gain(7, 1300.0, block_start=3)
    b = _gain(7, 1300.0, block_start=0)
    assert not np.isnan(a) and not np.isnan(b)
    assert abs(a - b) < 1e-9, (
        "un bloc demarrant 7 couches avant doit donner le meme resultat qu'un "
        "bloc demarrant 4 couches avant (MAX_LOOKBACK = 4)"
    )


# =========================================================================== #
# 4. Depot non terminable
# =========================================================================== #

@pytest.mark.parametrize("i_layer", [3, 5, 7])
def test_qwot_at_own_l0_is_not_monitorable_by_trigger(i_layer):
    """Un QWOT monitore a sa propre lambda_0 doit etre declare non terminable.

    Ce n'est pas un defaut du modele, c'est le bon resultat : a QWOT exact
    l'arret tombe sur le point tournant, ou dT/dd = 0. Un niveau n'y a plus
    no sensitivity to thickness, and half the noise achievements
    places the target beyond the extremum, or it will never be reached.

    En salle, ce cas se monitore en TPM — un paradigme que ce simulateur ne
    not model. Declaring it non-terminated IN TRIGGER is therefore correct.
    """
    val = _grow(i_layer, P_THICK[:i_layer], L0, noise=0.002)
    assert val > CRASH_SENTINEL, (
        f"L{i_layer} a lambda_0 = {L0:.0f} nm devrait etre non terminable en "
        f"trigger, or le noyau renvoie {val:.3f} nm"
    )


def _t_front(prev_thicks, n_cur, d, wl):
    """T on the front panel, calculates HERE and not borrows from the core tested.

    Meme convention que ``simulate_growth_kernel`` : milieu incident n = 1,
    substrat semi-infini, pas de face arriere.
    """
    two_pi = 2.0 * np.pi
    M = np.eye(2, dtype=np.complex128)
    for j, dj in enumerate(prev_thicks):
        n = N_H if j % 2 == 0 else N_L
        phi = two_pi / wl * n * dj
        cp, sp = np.cos(phi), np.sin(phi)
        M = np.array([[cp, 1j * sp / n], [1j * n * sp, cp]], dtype=np.complex128) @ M
    phi = two_pi / wl * n_cur * d
    cp, sp = np.cos(phi), np.sin(phi)
    A = np.array([[cp, 1j * sp / n_cur], [1j * n_cur * sp, cp]], dtype=np.complex128) @ M
    den = A[0, 0] + N_SUB * A[0, 1] + A[1, 0] + N_SUB * A[1, 1]
    return 4.0 * N_SUB.real / (den.real**2 + den.imag**2)


def test_unreachable_level_is_flagged_not_silently_snapped_to_the_vertex():
    """An unattainable level must be REPORTED, never absorbed in silence.

    `_solve_quadratic_target` possede une branche `discriminant < 0` qui renvoie
    the TOP of the inversion parabola without reporting anything. This is exactly the
    situation « le niveau vise n'est pas atteignable », mais rendue sous la forme
    of normal-appearing thickness.

    The non-terminability detection was guarded by `poem_ok`, therefore inactive
    precisement quand POEM est mal conditionne. Mesure sur
    example/example_strat/JSON-strat-example.json, 48 layers x 51 lengths
    waveform, upstream error +2 nm:

        silent withdrawal on the summit before: 6.68% after: 0.04%
        non-terminability reported before: 0.21% after: 7.26%

    Le taux ne dependait PAS de probe_offset (6,63 % a 0,5 nm, 6,88 % a 10 nm) :
    ce n'etait pas un artefact du fit parabolique mais la defaillance physique,
    non comptee.

    ⚠ An error of several tens of nanometers is NOT in itself a sign
    d'un plantage manque : dans les zones de faible dynamique la sensibilite
    collapses and a big error is the correct result. It's the fallback
    MUTIC that we are tracking down, not the big mistake.
    """
    from certus.physics.certus_strat_math import fit_parabola_vertex_3points

    i_layer = 6
    d_nom = P_THICK[i_layer]
    n_cur = N_H if i_layer % 2 == 0 else N_L
    prev = P_THICK[:i_layer].copy()
    prev[i_layer - 1] += 4.0  # erreur amont franche

    muets = []
    for wl in np.arange(900.0, 2400.0, 10.0):
        val = _grow(i_layer, prev, wl)
        if val > CRASH_SENTINEL:
            continue  # signale : c'est le comportement attendu
        xs = np.array([max(0.1, d_nom - PROBE), d_nom, d_nom + PROBE])
        ys = np.array([_t_front(prev, n_cur, x, wl) for x in xs])
        a, b, _c = fit_parabola_vertex_3points(xs, ys)
        if abs(a) > 1e-9 and abs(val - (-b / (2.0 * a))) < 1e-9:
            muets.append((float(wl), float(val - d_nom)))

    assert not muets, (
        "niveaux inatteignables absorbes en silence par le sommet de la parabole "
        f"(lambda, erreur nm) : {muets[:8]}"
    )


# =========================================================================== #
# 5. non_monotonic_factor n'est plus applique
# =========================================================================== #

@pytest.mark.parametrize("wl", [1300.0, 1700.0, 1900.0])
def test_non_monotonic_factor_no_longer_scales_the_error(wl):
    """Le facteur ne doit plus rien changer en mode ATTENUATE.

    He divided the error by a constant as soon as an extremum was crossed:
    la forme reduite du gain d'information apporte par le swing. Avec la cible
    frozen and POEM, this gain has become STRUCTURAL — it varies with the contrast
    reellement observe. Continuer a diviser compterait deux fois le meme effet.

    This test locks a DELIBERATE deletion: if it fails, it is because the
    pansement a ete remis.
    """
    prev = P_THICK[:5].copy()
    prev[4] += 2.0
    vals = [
        simulate_growth_kernel(
            P_THICK, 5, prev, wl, N_H, N_L, N_SUB, PROBE, 0.001, factor, NM_ATTENUATE, -1
        )[0]
        for factor in (1.0, 2.0, 5.0)
    ]
    assert max(vals) - min(vals) < 1e-9, (
        f"non_monotonic_factor influe encore sur le resultat a {wl:.0f} nm : {vals}"
    )
