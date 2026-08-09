"""La cle de `SplineBasisCache` ecrase des geometries distinctes — et c'est assume.

🔴 WHAT THIS FILE LOCKS, AND WHY IT EXISTS.

`SplineBasisCache.get` construit sa cle en ARRONDISSANT les positions de noeuds a 1e-6
et la grille cible a 1e-4. C'est delibere et documente sur place. Consequence mesuree le
2026-08-04 sur METAL_SINGLE :

    without cache RUN_S=154.6 s RESULT=0.006100345590625494
    cle arrondie        RUN_S= 75,2 s   RESULT=0,00613372429822523   HITRATE=88,1 %
    cle EXACTE          RUN_S=150,3 s   RESULT=0,006100345473793503  HITRATE=18,8 %

Le x2 apparent vient de ce que l'arrondi CONFOND les perturbations de difference finie
of L-BFGS-B: the gain IS the error. An exact key makes the result fair and removes
tout le gain.

**Le garde-fou reel n'est pas la cle, et ce n'est pas non plus le `use_cache=False` des
lignes 270 et 342 comme je l'ai d'abord ecrit.** `compute_metal_bilayer_gradient_analytic`
consults the cache **directly** (line 319), so no caller flag does
governs. But 📏 the measurement shows that this does not break anything: the memorized base is not useful
than the gradient with respect to the VALUES of nodes, while everything that depends on their
POSITIONS passe par les deux chemins non memoises. Les positions etant figees a
inside a call, the basis is correct for what it is used for. There remains one
order peremption (dB/dlambda) x 1e-6 on the value components only.

This file therefore locks three properties:

  1. la collision EXISTE sous l'arrondi — pour qu'on ne la redecouvre pas par un
     false result;
  2. beyond the rounding, the cache SEPARATES well — so the positions are in the key;
  3. le gradient METAL REAGIT a un deplacement de noeud de 1e-9 um, mille fois sous
     rounding — this is the property that ensures that the optimizer is not blind.

📏 REPONSE AU CONSTAT A2 de `docs/PLAN_AMELIORATION.md`, qui demandait de trancher entre
« le cache manque systematiquement » (lenteur) et « il rend une base perimee » (resultat
false): **neither one nor the other.** The node positions are in the key, so no basis
expired is not rendered where it counts; and the rounding of this key creates a third
situation, limited and negligible, which the report had not foreseen. **A2 is closed, and it
ne passe PAS en priorite absolue.**
"""

import numpy as np
import pytest

from certus.physics.certus_optical_models import SplineBasisCache, get_nk_from_spline

#: En dessous de l'arrondi de la cle (1e-6 sur les noeuds) : deux geometries que le cache
#: confuses. This is the order of magnitude of a finite difference disturbance.
SUB_ROUNDING = 1e-8

#: Au-dessus de l'arrondi : deux geometries que le cache doit distinguer.
ABOVE_ROUNDING = 1e-4


def _knots(shift: float = 0.0) -> np.ndarray:
    base = np.array([0.40, 0.55, 0.70, 0.85, 1.00], dtype=np.float64)
    out = base.copy()
    out[2] += shift  # on ne bouge qu'un noeud interne
    return out


TARGETS = np.linspace(0.42, 0.98, 61)


@pytest.fixture(autouse=True)
def _isolate_cache():
    """Makes this file HERMETIC: `SplineBasisCache._cache` is a CLASS state.

    Without this, entries added here leak to subsequent tests —
    `test_metal_optimizations.py::test_spline_basis_cache_eviction_and_lock` compte les
    entries and requires `< 500` on a terminal cache at 512. 📏 My few entries did it
    go from ~496 to 510, and this test failed even though it has nothing to do with this
    file. This is the same fault family as the `sys.modules` leak documented in
    `docs/REPRISE_TESTS_ISOLATION.md` : un test qui passe seul et echoue en selection
    large.
    """
    snapshot = SplineBasisCache._cache.copy()
    try:
        yield
    finally:
        SplineBasisCache._cache.clear()
        SplineBasisCache._cache.update(snapshot)


@pytest.mark.unit
def test_cache_key_conflates_geometries_below_its_rounding():
    """Deux jeux de noeuds distants de 1e-8 rendent LE MEME objet de base.

    Ce n'est pas un defaut a corriger ici — c'est le comportement mesure et assume, et
    this test exists so that it is VISIBLE. If it fails one day, it is because the rounding has
    been refined: then check that the METAL gain has not been “found” at the price
    of a false result, cf. the header of this file.
    """
    a = SplineBasisCache.get(_knots(0.0), TARGETS)
    b = SplineBasisCache.get(_knots(SUB_ROUNDING), TARGETS)
    assert a is b, (
        "l'arrondi de la cle a change : deux geometries distantes de 1e-8 ne sont plus "
        "confondues. Relire l'en-tete de ce fichier avant de s'en rejouir."
    )


@pytest.mark.unit
def test_cache_key_separates_geometries_above_its_rounding():
    """Au-dela de l'arrondi, le cache doit rendre des bases DIFFERENTES.

    This is what excludes the “outdated base” hypothesis from observation A2: the positions of
    noeuds sont bien dans la cle.
    """
    a = SplineBasisCache.get(_knots(0.0), TARGETS)
    b = SplineBasisCache.get(_knots(ABOVE_ROUNDING), TARGETS)
    assert a is not b
    assert not np.allclose(a, b), "meme matrice de base pour deux geometries distinctes"


@pytest.mark.unit
def test_uncached_path_resolves_what_the_cache_conflates():
    """`use_cache=False` distingue ce que le cache confond — c'est LE garde-fou.

    Deux geometries distantes de 1e-8 doivent donner des valeurs de n differentes. Si ce
    test echoue, la sonde de difference finie du gradient METAL voit un gradient NUL la
    or it is not, and the optimizer converges to a bad optimum WITHOUT error.
    """
    p = np.concatenate((np.linspace(1.5, 2.5, 5), np.linspace(0.0, 0.4, 5)))
    n0, _k0 = get_nk_from_spline(p, _knots(0.0), TARGETS, use_cache=False)
    n1, _k1 = get_nk_from_spline(p, _knots(SUB_ROUNDING), TARGETS, use_cache=False)
    assert not np.array_equal(n0, n1), (
        "le chemin sans cache ne distingue pas deux geometries distantes de 1e-8 : "
        "la sonde de difference finie du gradient est aveugle"
    )


@pytest.mark.unit
def test_metal_gradient_sees_knot_moves_below_the_cache_rounding():
    """Le gradient METAL doit REAGIR a un deplacement de noeud sous l'arrondi du cache.

    🔴 IT'S THE GUARD THAT COUNTS, and it's not the one I thought.

    `compute_metal_bilayer_gradient_analytic` consulte `SplineBasisCache` une fois par
    call (`gradient_metal.py:319`), directly — so neither `use_cache=False` nor the option
    `--force-cache` du banc ne le gouvernent. J'ai d'abord ecrit ce test en exigeant
    ZERO consultation du cache. 📏 La mesure m'a contredit, et la contradiction est
    instructive : la base memoisee ne sert qu'au gradient par rapport aux VALEURS de
    nodes, while everything that depends on their POSITIONS passes through both
    `use_cache=False` des lignes 270 et 342. Les positions etant figees a l'interieur
    of a call, the basis is correct for what it is used for.

    There remains a peremption of order (dB/dlambda) x 1e-6, i.e. ~1e-6 relative to the
    only components of value — negligible, and limited.

    📏 Verifie : un deplacement de 1e-9 um sur un noeud interne — mille fois SOUS
    l'arrondi de la cle — bouge le gradient de 2,1e-9. Ce qu'un test doit verrouiller,
    so it's this RESPONSE, not a count of cache calls: if it disappeared,
    l'optimiseur verrait un gradient nul sur les positions de noeuds et convergerait
    towards a bad optimum WITHOUT raising an error.
    """
    import certus.physics.gradient_metal as gm

    l_array = np.linspace(0.45, 0.95, 41)
    num_knots = 3
    spline_knot_count = num_knots + 1
    # Disposition de x, imposee par le code : [ep_metal, ep_L, n_infini, A,
    # n_knots (sc), k_knots (sc), lambdas_internes]. La grille de noeuds est
    # `[l_min] + lambdas_internes + [l_max]`, et CubicSpline exige autant de valeurs
    # que de noeuds — d'ou `len(lambdas_internes) = sc - 2` et `len(x) = 3.num_knots + 5`.
    n_internal = spline_knot_count - 2
    x = np.concatenate(
        (
            np.array([20.0, 100.0, 1.45, 0.003]),
            np.linspace(1.6, 2.6, spline_knot_count),
            np.linspace(0.05, 0.35, spline_knot_count),
            np.linspace(0.55, 0.85, n_internal),
        )
    )
    assert x.size == 3 * num_knots + 5
    # Signature reelle : (x, num_knots, l_array, r_tgt_array, _min_knot_dist, nSub=None).
    #⚠️ No `try/except` here, and this is deliberate: a fallback on a check
    #lexical source would pass this test WITHOUT ever executing the assertion which
    # compte. C'est exactement le piege « un test qui ne peut pas echouer n'est pas un
    # test » de docs/PLAN_AMELIORATION.md §0.2. Si l'appel casse, le test doit casser.
    # `nSub_complex_array=None` ne convient pas : le noyau njit en aval l'indexe.
    n_sub = np.full(l_array.size, complex(1.52, 0.0), dtype=np.complex128)
    tgt = np.ones_like(l_array) * 0.5

    def _grad(shift: float) -> tuple[float, np.ndarray]:
        xs = x.copy()
        xs[4 + 2 * spline_knot_count :] += shift  # les lambdas internes seulement
        mse, g = gm.compute_metal_bilayer_gradient_analytic(
            xs, num_knots, l_array, tgt, 0.01, n_sub
        )
        return float(mse), np.asarray(g)

    mse0, g0 = _grad(0.0)
    assert np.isfinite(mse0), "le cout rendu n'est pas fini : l'appel n'a rien calcule"
    assert g0.shape == x.shape, "le gradient ne couvre pas tout le vecteur de parametres"
    assert np.any(g0 != 0.0), "gradient identiquement nul : l'appel n'a rien calcule"

    #A thousand times under the rounding of the key (1e-6). The memorized base is identical.
    mse1, g1 = _grad(1.0e-9)
    assert abs(mse1 - mse0) > 0.0, (
        "le cout ne bouge pas pour un deplacement de noeud de 1e-9 um : le chemin de "
        "calcul du cout est passe par la base memoisee, qui l'arrondit"
    )
    assert float(np.max(np.abs(g1 - g0))) > 0.0, (
        "le gradient ne bouge pas pour un deplacement de noeud de 1e-9 um : l'optimiseur "
        "voit un gradient NUL sur les positions de noeuds et convergera vers un mauvais "
        "optimum sans lever d'erreur"
    )

