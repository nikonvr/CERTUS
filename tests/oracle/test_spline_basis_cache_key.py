"""La cle de `SplineBasisCache` ecrase des geometries distinctes — et c'est assume.

🔴 CE QUE CE FICHIER VERROUILLE, ET POURQUOI IL EXISTE.

`SplineBasisCache.get` construit sa cle en ARRONDISSANT les positions de noeuds a 1e-6
et la grille cible a 1e-4. C'est delibere et documente sur place. Consequence mesuree le
2026-08-04 sur METAL_SINGLE :

    sans cache          RUN_S=154,6 s   RESULT=0,006100345590625494
    cle arrondie        RUN_S= 75,2 s   RESULT=0,00613372429822523   HITRATE=88,1 %
    cle EXACTE          RUN_S=150,3 s   RESULT=0,006100345473793503  HITRATE=18,8 %

Le x2 apparent vient de ce que l'arrondi CONFOND les perturbations de difference finie
de L-BFGS-B : le gain EST l'erreur. Une cle exacte rend le resultat juste et supprime
tout le gain.

**Le garde-fou reel n'est pas la cle, et ce n'est pas non plus le `use_cache=False` des
lignes 270 et 342 comme je l'ai d'abord ecrit.** `compute_metal_bilayer_gradient_analytic`
consulte le cache **directement** (ligne 319), donc aucun drapeau d'appelant ne le
gouverne. Mais 📏 la mesure montre que cela ne casse rien : la base memoisee ne sert
qu'au gradient par rapport aux VALEURS de noeuds, tandis que tout ce qui depend de leurs
POSITIONS passe par les deux chemins non memoises. Les positions etant figees a
l'interieur d'un appel, la base est correcte pour ce qu'elle sert. Il reste une
peremption d'ordre (dB/dlambda) x 1e-6 sur les seules composantes de valeur.

Ce fichier verrouille donc trois proprietes :

  1. la collision EXISTE sous l'arrondi — pour qu'on ne la redecouvre pas par un
     resultat faux ;
  2. au-dela de l'arrondi, le cache SEPARE bien — donc les positions sont dans la cle ;
  3. le gradient METAL REAGIT a un deplacement de noeud de 1e-9 um, mille fois sous
     l'arrondi — c'est la propriete qui garantit que l'optimiseur n'est pas aveugle.

📏 REPONSE AU CONSTAT A2 de `docs/PLAN_AMELIORATION.md`, qui demandait de trancher entre
« le cache manque systematiquement » (lenteur) et « il rend une base perimee » (resultat
faux) : **ni l'un ni l'autre.** Les positions de noeuds sont dans la cle, donc aucune base
perimee n'est rendue la ou elle compte ; et l'arrondi de cette cle cree une troisieme
situation, bornee et negligeable, que le constat n'avait pas prevue. **A2 est clos, et il
ne passe PAS en priorite absolue.**
"""

import numpy as np
import pytest

from certus.physics.certus_optical_models import SplineBasisCache, get_nk_from_spline

#: En dessous de l'arrondi de la cle (1e-6 sur les noeuds) : deux geometries que le cache
#: confond. C'est l'ordre de grandeur d'une perturbation de difference finie.
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
    """Rend ce fichier HERMETIQUE : `SplineBasisCache._cache` est un etat de CLASSE.

    Sans cela, les entrees ajoutees ici fuient vers les tests suivants —
    `test_metal_optimizations.py::test_spline_basis_cache_eviction_and_lock` compte les
    entrees et exige `< 500` sur un cache borne a 512. 📏 Mes quelques entrees l'ont fait
    passer de ~496 a 510, et ce test echouait alors qu'il n'a rien a voir avec ce
    fichier. C'est la meme famille de defaut que la fuite `sys.modules` documentee dans
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
    ce test existe pour qu'il soit VISIBLE. S'il echoue un jour, c'est que l'arrondi a
    ete affine : verifier alors que le gain de METAL n'a pas ete « retrouve » au prix
    d'un resultat faux, cf. l'en-tete de ce fichier.
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

    C'est ce qui exclut l'hypothese « base perimee » du constat A2 : les positions de
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
    ou il ne l'est pas, et l'optimiseur converge vers un mauvais optimum SANS erreur.
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

    🔴 C'EST LE GARDE-FOU QUI COMPTE, et ce n'est pas celui que je croyais.

    `compute_metal_bilayer_gradient_analytic` consulte `SplineBasisCache` une fois par
    appel (`gradient_metal.py:319`), directement — donc ni `use_cache=False` ni l'option
    `--force-cache` du banc ne le gouvernent. J'ai d'abord ecrit ce test en exigeant
    ZERO consultation du cache. 📏 La mesure m'a contredit, et la contradiction est
    instructive : la base memoisee ne sert qu'au gradient par rapport aux VALEURS de
    noeuds, tandis que tout ce qui depend de leurs POSITIONS passe par les deux
    `use_cache=False` des lignes 270 et 342. Les positions etant figees a l'interieur
    d'un appel, la base est correcte pour ce qu'elle sert.

    Il reste une peremption d'ordre (dB/dlambda) x 1e-6, soit ~1e-6 en relatif sur les
    seules composantes de valeur — negligeable, et bornee.

    📏 Verifie : un deplacement de 1e-9 um sur un noeud interne — mille fois SOUS
    l'arrondi de la cle — bouge le gradient de 2,1e-9. Ce qu'un test doit verrouiller,
    c'est donc cette REPONSE, pas un compte d'appels au cache : si elle disparaissait,
    l'optimiseur verrait un gradient nul sur les positions de noeuds et convergerait
    vers un mauvais optimum SANS lever d'erreur.
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
    # ⚠️ Pas de `try/except` ici, et c'est delibere : un repli sur une verification
    # lexicale du source ferait passer ce test SANS jamais executer l'assertion qui
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

    # Mille fois sous l'arrondi de la cle (1e-6). La base memoisee est, elle, identique.
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

