"""Axe 1.1 — bruit de LECTURE du signal de monitoring, et ce qu'il ne doit PAS casser.

Le simulateur ne bruitait qu'un seul point de toute la chaine : la comparaison
d'arret. `Ts_r`, le signal « reel », sert pourtant aussi a la detection des points
tournants, a la lecture des ancres POEM et au test d'atteignabilite du niveau.
`poem_anchor_noise` applies the same sigma to it BEFORE these three uses.

This file locks four things, and each one has already been broken once here:

  1. DRAPEAU FERME = CHEMIN IDENTIQUE AU BIT PRES. Un drapeau « par defaut inactif »
     qui deplace le resultat de 1e-16 rendrait tout A/B contre le baseline illisible.
  2. OPEN FLAG = THE ANCHORS MOVE, even at zero stopping noise. Otherwise the noise
     n'atteint pas ce qu'il devait atteindre.
  3. COMMON RANDOM NUMBERS. The draw is a pure function of
     (seed, layer, draw, point) and does NOT depend on the strategy. It's a
     acquis du modele, protege ailleurs par un long commentaire, et il doit le rester.
  4. THE DUPLICATE POINT. `d = 0` of the current layer IS the last point of
     the history of the block: a single measurement, therefore a single draw. Two prints
     independants y fabriquaient un extremum parasite a pile ou face — 📏 taux de
     plantage de 28 % au lieu de 1,2 %, et INDEPENDANT de sigma, ce qui est la
     signature meme d'un artefact.

Reference : CLAUDE.md, regles gravees §14.

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
from certus_physics import simulate_growth_kernel, simulate_stack_robustness_batch

# --------------------------------------------------------------------------- #
#Same reference stack as tests/unit/test_strat_poem.py: 8 layers
# quart d'onde a 1500 nm. Les deux fichiers parlent du meme objet.
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
CRASH_SENTINEL = 1e5

#: Echelle de bruit de lecture, en unites de T. `trigger_tolerance` = 0,05 (% de T)
#: sur l'OMS 5100 de reference, soit 5e-4 apres division par 100.
SIG = 5.0e-4

#: 📏 Couples (layer, lambda) or POEM is ACTIVE on this stack: two extrema
#: actually crossed before the stop, therefore anchors to sound. Measures.
POEM_ACTIVE = [(3, 800.0), (5, 700.0), (5, 800.0), (7, 700.0)]

#: 📏 Couples or POEM is INACTIVE and the level is achievable: the target is then the
#: niveau nominal FIGE, et `Ts_r` ne sert plus qu'au test d'atteignabilite.
POEM_INACTIVE = [(3, 1300.0), (5, 1300.0), (5, 1700.0), (7, 1700.0)]


def _grow(i_layer, prev, wl, *, noise=0.0, block_start=-1, sig=0.0, seed=0, run=0):
    val, _dyn = simulate_growth_kernel(
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
        float(sig),
        int(seed),
        int(run),
    )
    return val


def _prev_with_error(i_layer, err_nm=2.0):
    prev = P_THICK[:i_layer].copy()
    prev[i_layer - 1] += err_nm
    return prev


# =========================================================================== #
#1. Firm flag: absolutely nothing changes
# =========================================================================== #


@pytest.mark.parametrize("i_layer, wl", POEM_ACTIVE + POEM_INACTIVE)
@pytest.mark.parametrize("block_start", [-1, 4])
def test_disabled_flag_ignores_seed_and_run_bit_for_bit(i_layer, wl, block_start):
    """A echelle nulle, ni la graine ni l'indice de tirage ne doivent exister.

    C'est la condition pour qu'un A/B contre le baseline mesure le changement de
    modele et rien d'autre. Un ecart, meme de 1e-16, signifierait que le chemin
    desactive a ete touche.
    """
    prev = _prev_with_error(i_layer)
    ref = _grow(i_layer, prev, wl, noise=1e-4, block_start=block_start)
    for seed, run in ((0, 0), (12345, 7), (2**40 + 1, 63)):
        got = _grow(
            i_layer, prev, wl, noise=1e-4, block_start=block_start, sig=0.0, seed=seed, run=run
        )
        assert got == ref, (
            f"le chemin desactive depend de (graine={seed}, tirage={run}) : "
            f"{got!r} != {ref!r}"
        )


def test_disabled_flag_matches_the_legacy_call_signature():
    """Calling the kernel WITHOUT the three new arguments should give the same thing.

    Six sites d'appel en production passaient douze arguments. Les valeurs par
    defaut doivent les laisser exactement ou ils etaient.
    """
    for i_layer, wl in POEM_ACTIVE + POEM_INACTIVE:
        prev = _prev_with_error(i_layer)
        legacy, _ = simulate_growth_kernel(
            P_THICK, i_layer, prev, float(wl), N_H, N_L, N_SUB, PROBE, 1e-4, 1.0, NM_ATTENUATE, -1
        )
        explicit = _grow(i_layer, prev, wl, noise=1e-4, block_start=-1, sig=0.0, seed=0, run=0)
        assert explicit == legacy, f"L{i_layer} @ {wl:.0f} nm : {explicit!r} != {legacy!r}"


# =========================================================================== #
#2. Open flag: the noise reaches the anchors, and NOTHING ELSE
# =========================================================================== #


@pytest.mark.parametrize("i_layer, wl", POEM_ACTIVE)
def test_enabled_flag_moves_the_poem_anchors_at_zero_trigger_noise(i_layer, wl):
    """A bruit d'ARRET nul, le resultat doit quand meme bouger.

    C'est ce qui distingue le bruit de LECTURE du bruit d'arret : si le seul effet
    passait par `target_T_noisy`, mettre le bruit d'arret a zero annulerait tout.
    POEM anchors are MEASUREMENTS, they must carry their uncertainty.
    """
    prev = _prev_with_error(i_layer)
    ref = _grow(i_layer, prev, wl, noise=0.0)
    got = _grow(i_layer, prev, wl, noise=0.0, sig=SIG, seed=777, run=0)
    assert ref < CRASH_SENTINEL
    assert got != ref, (
        f"L{i_layer} @ {wl:.0f} nm : le bruit de lecture n'atteint pas les ancres POEM"
    )


@pytest.mark.parametrize("i_layer, wl", POEM_INACTIVE)
def test_enabled_flag_leaves_the_frozen_nominal_level_alone(i_layer, wl):
    """La ou POEM est inactif et le niveau atteignable, le resultat ne doit PAS bouger.

    The target level is then the FIXED nominal target, calculated offline on the
    design: no one measures it, so nothing disturbs it. And the three points
    of the parabolic inversion are not a measure either — they resolve
    T_reel(d) = target_T_noisy.

    Ce test est le garde-fou contre la tentation de « bruiter partout » : le bruit
    de lecture ne doit agir que la ou la machine LIT.
    """
    prev = _prev_with_error(i_layer)
    ref = _grow(i_layer, prev, wl, noise=1e-4)
    assert ref < CRASH_SENTINEL, "cas mal choisi : le depot ne se termine pas"
    got = _grow(i_layer, prev, wl, noise=1e-4, sig=SIG, seed=777, run=0)
    assert got == ref, (
        f"L{i_layer} @ {wl:.0f} nm : POEM est inactif et le niveau atteignable, "
        f"le bruit de lecture ne devait rien changer ({got!r} != {ref!r})"
    )


def test_enabled_flag_is_reproducible_and_run_dependent():
    """Same (seed, draw) -> same value; different prints -> different values."""
    i_layer, wl = 5, 800.0
    prev = _prev_with_error(i_layer)
    a = _grow(i_layer, prev, wl, noise=0.0, sig=SIG, seed=99, run=3)
    b = _grow(i_layer, prev, wl, noise=0.0, sig=SIG, seed=99, run=3)
    assert a == b, "le bruit de lecture n'est pas reproductible"

    vals = {_grow(i_layer, prev, wl, noise=0.0, sig=SIG, seed=99, run=r) for r in range(12)}
    assert len(vals) >= 8, f"les tirages ne se distinguent pas assez : {sorted(vals)}"


def test_signal_noise_scale_is_proportional_to_sigma():
    """L'amplitude de la perturbation doit suivre l'echelle demandee.

    Without this, `signal_noise_scale` would not be a sigma but a simple boolean,
    et les trois niveaux de bruit de la Phase B (0,5x, 1x, 2x) ne voudraient rien
    dire pour cet etage.
    """
    i_layer, wl = 5, 800.0
    prev = _prev_with_error(i_layer)
    ref = _grow(i_layer, prev, wl, noise=0.0)
    small = [abs(_grow(i_layer, prev, wl, noise=0.0, sig=SIG / 10.0, seed=5, run=r) - ref) for r in range(16)]
    large = [abs(_grow(i_layer, prev, wl, noise=0.0, sig=SIG, seed=5, run=r) - ref) for r in range(16)]
    small = [v for v in small if v < CRASH_SENTINEL]
    large = [v for v in large if v < CRASH_SENTINEL]
    assert small and large
    assert float(np.median(large)) > 3.0 * float(np.median(small)), (
        f"un sigma dix fois plus grand ne perturbe pas davantage : "
        f"median {np.median(small):.3g} -> {np.median(large):.3g} nm"
    )


# =========================================================================== #
# 3. Le point duplique — 📏 28 % de plantage au lieu de 1,2 %
# =========================================================================== #


def _crash_rate_over_layers(depth: int, sig: float, seed: int = 4242, n_draws: int = 24) -> float:
    bad = 0
    tot = 0
    for i_layer in range(1, P_THICK.size):
        blk = max(0, i_layer - depth)
        for wl in (700.0, 800.0, 900.0, 1100.0, 1300.0):
            for r in range(n_draws):
                v = _grow(
                    i_layer, P_THICK[:i_layer], wl, noise=0.0, block_start=blk,
                    sig=sig, seed=seed, run=r,
                )
                tot += 1
                bad += int(v > CRASH_SENTINEL)
    return bad / tot


def test_history_junction_is_one_measurement_not_two():
    """Le plantage ne doit pas exploser des qu'un historique de bloc existe.

    `d = 0` of the current layer and the last point of the history are THE SAME
    measurement — T of the stack stopped at the end of the previous layer. The signal
    own there is therefore a level of zero length, in the dead band at 1e-12, or
    no extremum can be detected.

    Deux tirages independants rendaient cette difference non nulle ET de signe
    random: a parasitic extremum heads or tails, therefore `n_tp_real != n_tp_nom`,
    therefore a crash. 📏 On 48-layer dichroic, nominal history and noise
    d'arret nul : 0,63 % a profondeur 0 contre 27,4 % des la profondeur 1.

    ⚠️ The history here is NOMINAL and the shutdown noise is ZERO: without reading noise
    the rate is zero by construction. Everything that this test measures is therefore attributable
    au bruit de lecture, et rien d'autre.
    """
    assert _crash_rate_over_layers(depth=0, sig=0.0) == 0.0, "temoin invalide"
    assert _crash_rate_over_layers(depth=4, sig=0.0) == 0.0, "temoin invalide"

    flat = _crash_rate_over_layers(depth=0, sig=SIG)
    deep = _crash_rate_over_layers(depth=4, sig=SIG)
    assert deep < flat + 0.10, (
        f"le plantage explose avec l'historique du bloc ({flat:.1%} a profondeur 0 "
        f"contre {deep:.1%} a profondeur 4) : le point de jonction est probablement "
        f"compte comme DEUX mesures independantes au lieu d'une"
    )


def test_crash_rate_depends_on_sigma():
    """Un taux de plantage insensible a sigma est un artefact, pas de la physique.

    C'est la seconde signature du meme defaut, et la plus dirimante : 📏 avec deux
    tirages a la jonction, le taux valait 28,5 % a sigma/10 comme 28,1 % a 2 sigma.
    Un signe aleatoire ne depend pas d'une amplitude.
    """
    lo = _crash_rate_over_layers(depth=4, sig=SIG / 20.0)
    hi = _crash_rate_over_layers(depth=4, sig=SIG * 4.0)
    assert hi > lo, (
        f"le taux de plantage ne depend pas de sigma ({lo:.2%} a sigma/20 contre "
        f"{hi:.2%} a 4 sigma) : un mecanisme de bruit ne peut pas se comporter ainsi"
    )


# =========================================================================== #
# 4. Nombres aleatoires communs
# =========================================================================== #


def test_stream_seed_depends_only_on_seed_and_noise_level():
    """La graine du flux ne doit dependre QUE de la configuration de tirage.

    Si elle dependait de la strategie, chaque strategie affronterait un bruit
    different et la comparaison cesserait d'etre appariee. C'est l'acquis que
    `_get_cached_sobol_noise` protege pour le bruit d'arret, avec la meme exigence.

    Et le melange doit etre MULTIPLICATIF : le consensus engendre ses graines par
    `base_seed + i * stride` with a stride of 1 by default, so a sum would make
    collisionner (graine 42, niveau 1) et (graine 43, niveau 0) — le meme bruit pour
    deux configurations distinctes.
    """
    from certus.core.certus_strat_robustness import _signal_noise_stream_seed as F

    assert F(42, 1) == F(42, 1), "la graine du flux n'est pas deterministe"
    assert F(42, 1) != F(43, 0), "collision triangulaire : le melange est additif"
    assert F(42, 0) != F(42, 1) != F(42, 2)
    seeds = {F(s, n) for s in range(41, 46) for n in range(3)}
    assert len(seeds) == 15, f"collisions sur 5 graines x 3 niveaux : {len(seeds)}/15"


def test_batch_signal_noise_is_paired_across_strategies():
    """Deux strategies evaluees au meme (graine, tirage) voient le MEME bruit.

    Verified on the observable quantity: the layers located BEFORE any divergence
    de longueur d'onde doivent ressortir identiques au bit pres. Un bruit dependant
    de la strategie les ferait deja differer.
    """
    n_layers = P_THICK.size
    n_runs = 8
    noise = np.zeros((n_runs, n_layers), dtype=np.float64)
    sig = np.full(n_layers, SIG, dtype=np.float64)
    nH = np.full(n_layers, N_H, dtype=np.complex128)
    nL = np.full(n_layers, N_L, dtype=np.complex128)
    nS = np.full(n_layers, N_SUB, dtype=np.complex128)

    #A: Everything is 800 nm. B: identical up to layer 5, then 700 nm.
    wl_a = np.full(n_layers, 800.0, dtype=np.float64)
    wl_b = wl_a.copy()
    wl_b[6:] = 700.0

    sim_a, _ = simulate_stack_robustness_batch(
        P_THICK, wl_a, nH, nL, nS, noise, PROBE, 1.0, NM_ATTENUATE, sig, 4242
    )
    sim_b, _ = simulate_stack_robustness_batch(
        P_THICK, wl_b, nH, nL, nS, noise, PROBE, 1.0, NM_ATTENUATE, sig, 4242
    )
    assert np.array_equal(sim_a[:, :6], sim_b[:, :6]), (
        "les couches identiques de deux strategies ne donnent pas le meme resultat : "
        "le bruit de lecture depend de la strategie, les nombres aleatoires communs "
        "sont perdus"
    )


def test_batch_none_scale_matches_the_legacy_call():
    """`signal_noise_scale=None` should restore the previous path.

    ⚠ NOT `array_equal`, and it should be said why. Omit the argument and pass
    `None` are TWO types for numba (`Omitted(None)` and `none`), so two
    specialisations compilees de la meme fonction `parallel=True, fastmath=True`.
    Un ecart de reassociation flottante entre elles a ete observe UNE fois, a la
    toute premiere compilation, et ne s'est pas reproduit cache chaud.

    Le seuil de 1e-12 nm est vingt mille fois plus fin que le seuil physique du
    project (0.05 nm, less than one atom): it allows a difference of
    compilation et arrete net tout changement de logique. Et le motif de plantage,
    him, is required IDENTICAL — it is a discrete magnitude, it cannot
    « deriver ».

    L'identite au bit pres est verrouillee la ou elle est fiable : au niveau du
    CORE, which is not parallelized (see the first two tests of this file).
    """
    n_layers = P_THICK.size
    n_runs = 6
    rng = np.random.default_rng(7)
    noise = rng.normal(0.0, 1e-4, size=(n_runs, n_layers))
    wl = np.full(n_layers, 800.0, dtype=np.float64)
    nH = np.full(n_layers, N_H, dtype=np.complex128)
    nL = np.full(n_layers, N_L, dtype=np.complex128)
    nS = np.full(n_layers, N_SUB, dtype=np.complex128)

    legacy, _ = simulate_stack_robustness_batch(
        P_THICK, wl, nH, nL, nS, noise, PROBE, 1.0, NM_ATTENUATE
    )
    explicit, _ = simulate_stack_robustness_batch(
        P_THICK, wl, nH, nL, nS, noise, PROBE, 1.0, NM_ATTENUATE, None, 999
    )
    crashed_l = legacy > CRASH_SENTINEL
    crashed_e = explicit > CRASH_SENTINEL
    assert np.array_equal(crashed_l, crashed_e), "le motif de plantage a change"
    healthy = ~crashed_l
    assert healthy.any()
    assert float(np.abs(legacy[healthy] - explicit[healthy]).max()) < 1e-12

    # Deux appels de la MEME specialisation, en revanche, doivent etre identiques
    # au bit pres : c'est l'acquis « RESULT reproductible » du banc de mesure.
    again, _ = simulate_stack_robustness_batch(
        P_THICK, wl, nH, nL, nS, noise, PROBE, 1.0, NM_ATTENUATE, None, 999
    )
    assert np.array_equal(explicit, again)


# =========================================================================== #
# 4bis. La sentinelle de plantage porte SA CAUSE
# =========================================================================== #


def test_crash_sentinel_encodes_its_cause():
    """Les trois causes de non-terminabilite doivent etre distinguables.

    They all returned `nominal_th + 1e6`, and this blocked a diagnosis
    integer: the detection hysteresis divided the crash rate by two without
    toucher au plancher independant de sigma, et on ne pouvait pas dire si ce
    plancher venait du COMPTAGE des points tournants ou de l'ATTEIGNABILITE du
    niveau. 📏 Reponse, une fois decompose : 100 % atteignabilite, 0,000 % comptage.

    The cause is reread by `val // 1e6` without knowing the nominal thickness — it
    vaut moins de 1e4 nm sur tout empilement physique.
    """
    from certus_physics import (
        CRASH_LEVEL_UNREACHABLE,
        CRASH_NON_MONOTONIC,
        CRASH_SENTINEL_MIN,
        CRASH_SENTINEL_UNIT,
        CRASH_TP_MISCOUNT,
    )

    assert {CRASH_LEVEL_UNREACHABLE, CRASH_TP_MISCOUNT, CRASH_NON_MONOTONIC} == {1, 2, 3}

    #📏 A QWOT monitored at its own lambda_0 stops ON the turning point: the
    #level there is no longer any sensitivity to thickness. This is the textbook case of
    # niveau inatteignable, et il doit se declarer comme tel.
    val = _grow(5, P_THICK[:5], L0, noise=0.002)
    assert val > CRASH_SENTINEL_MIN
    assert int(val // CRASH_SENTINEL_UNIT) == CRASH_LEVEL_UNREACHABLE

    #REJECT mode on a layer with non-monotonic T(d): third, distinct cause.
    rejected = simulate_growth_kernel(
        P_THICK, 5, P_THICK[:5], 700.0, N_H, N_L, N_SUB, PROBE, 0.0, 1.0, 1, -1
    )[0]
    if rejected > CRASH_SENTINEL_MIN:
        assert int(rejected // CRASH_SENTINEL_UNIT) in {
            CRASH_LEVEL_UNREACHABLE,
            CRASH_TP_MISCOUNT,
            CRASH_NON_MONOTONIC,
        }


def test_crash_sentinel_keeps_every_existing_consumer_intact():
    """🔴 LE TAUX DE PLANTAGE GLOBAL NE DOIT PAS AVOIR BOUGE D'UN POUCE.

    Tous les consommateurs testent `val > 1e5`. Les trois causes valent 1e6, 2e6 et
    3e6: they therefore all cross this threshold, exactly like the single 1e6
    from before. A decomposition which would change the rate would not be a
    decomposition, ce serait un changement de modele deguise.
    """
    from certus_physics import CRASH_SENTINEL_MIN, CRASH_SENTINEL_UNIT

    assert CRASH_SENTINEL_UNIT > CRASH_SENTINEL_MIN
    assert 3.0 * CRASH_SENTINEL_UNIT > CRASH_SENTINEL_MIN
    #On a physical stack, the nominal thickness remains much lower than
    #the sentinel unity: the entire division therefore renders the cause, not a mixture.
    assert float(P_THICK.max()) < CRASH_SENTINEL_UNIT / 100.0


# =========================================================================== #
# 5. The control lambda grid is that of SCANNING, at a step of 2 nm
# =========================================================================== #


def test_monitoring_grid_is_the_scan_grid_not_the_display_grid():
    """👤 “The lengths must be able to be chosen in steps of 2 nm.”

    `clues_at_wl` contient l'UNION de la grille de balayage (pas `scan_wl_step`) et
    of the display grid (not `wl_step`), so a step of 1 nm over the entire
    recovery. The ELITE stage, which mutates “towards the neighboring lambda”, therefore mutates
    1 nm — hors grille de controle, d'ou le top 5 `551, 552, 553, 554` mesure sur le
    juge de paix.
    """
    from certus.core.certus_strat_ranking import _resolve_monitoring_wavelength_grid

    params = {"scan_wl_min": 450.0, "scan_wl_max": 700.0, "scan_wl_step": 2.0}
    # The index dictionary bears the union of the two grids: 1 nm from 400 to 700.
    clues = {float(w): {} for w in np.arange(400.0, 700.0 + 1e-9, 1.0)}
    grid = _resolve_monitoring_wavelength_grid(params, clues, np.array([450.0, 451.0]))

    assert len(grid) == 126, f"attendu 126 lambda de 450 a 700 au pas de 2 nm, obtenu {len(grid)}"
    steps = np.diff(np.asarray(grid))
    assert np.allclose(steps, 2.0), f"pas non uniforme : {sorted(set(np.round(steps, 6)))}"
    # Les quatre lambda du top 5 mesure — 551, 552, 553, 554 — ne peuvent plus
    #coexist: the 2 nm grid retains at most one out of two.
    assert 551.0 not in grid and 553.0 not in grid, "des lambda hors grille subsistent"
    assert 550.0 in grid and 552.0 in grid and 554.0 in grid
    assert not any(abs(w - round(w / 2.0) * 2.0) > 1e-9 for w in grid)


def test_monitoring_grid_falls_back_when_scan_bounds_are_missing():
    """Without scanning limits, it is better to have a grid that is too fine than no candidate."""
    from certus.core.certus_strat_ranking import _resolve_monitoring_wavelength_grid

    clues = {500.0: {}, 501.0: {}}
    grid = _resolve_monitoring_wavelength_grid({}, clues, np.array([500.0, 501.0]))
    assert sorted(grid) == [500.0, 501.0]
