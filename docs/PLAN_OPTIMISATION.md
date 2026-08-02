# Plan d'optimisation CERTUS — fondé sur les exemples réels

Écrit le 2026-08-02. Toutes les mesures viennent de `example/`, chargé par les tests
`tests/headless/`, sur la machine de développement. **Aucun chiffre de ce document
n'est une estimation.**

À lire après `CLAUDE.md` et `docs/PLAN_AMELIORATION.md`.

---

> ## ⚠️ Corrigé le 2026-08-02 par la mesure — lire `docs/REPRISE_PERF.md` §5
>
> Ce document reste utile **pour METAL**, mais trois de ses affirmations ont été
> démenties en les mesurant. Ne perds pas de temps à les refaire.
>
> 1. **§2.5 est faux.** Le cache ne « se saborde » pas : le vidage total ne coûtait
>    que **15 reconstructions sur 5 522**. L'éviction LRU rapporte **+0,124 s**
>    (0,4 % d'un run), et **0 s** en production — `SplineBasisCache` n'est appelé
>    que **18 fois** par run de METAL_SINGLE. Le −53 % n'est donc pas « un plancher ».
> 2. **§5 étapes 1 et 2 ne concernent QUE METAL.** Mesuré : INDEX, INDEX_SPLINE, RE
>    et FIELD font **zéro appel** à `SplineBasisCache` et à `get_nk_from_spline`.
>    Pour les modules du quotidien, il fallait commencer par l'étape 3.
> 3. **§1 sous-évalue STRAT et DESIGN**, parce que `tests/headless/test_strat.py` et
>    `test_design.py` **remplacent le calcul par un mock**. Vrais chiffres :
>    STRAT 137 s (ramené à ~50 s), DESIGN 43–93 s. Mesurer avec
>    `scripts/bench_examples.py`, pas avec `tests/headless/`.
>
> Reste valable et non fait : le **§2.4** (basculer `use_cache=True` site par site
> sur METAL), avec la réserve notée en `REPRISE_PERF.md` §4.5 — le RMSE final
> change, ce qui n'est pas expliqué.

---

## 0. La règle qui a coûté le plus cher aujourd'hui

**Mesurer à entrée VARIABLE.** Deux fois dans la même session, un banc d'essai à
entrée figée a donné une conclusion fausse :

* un gradient mesuré à `x` fixe donnait 1,10 ms ; à `x` variable, 5,68 ms — le
  `lru_cache` touchait à chaque appel et masquait tout ;
* un test de gradient spline avec des valeurs de nœuds en `np.linspace` ne détectait
  aucun défaut : des points alignés sont interpolés identiquement par une spline
  cubique et par une linéaire par morceaux.

Un optimiseur ne repasse jamais deux fois par le même point. Un banc qui le fait ne
mesure rien.

**Et vérifier contre l'oracle.** `pytest tests/oracle/` (~2 s) après chaque
modification touchant au calcul.

---

## 1. Référence de départ, sur exemples réels

Tests `tests/headless/`, qui chargent les configurations de `example/` :

| Test | Exemple chargé | Durée |
|---|---|---|
| `test_metal_bilayer` | `JSON-metal-bilayer-example.json` | **80,6 s** |
| `test_metal_single` | `JSON-metal-example.json` | **76,8 s** |
| `test_re` | `reverse_sample.xlsx` | 41,6 s |
| `test_index` | `example_index` | 15,3 s |
| `test_strat` | `JSON-strat-example.json` | 9,3 s |

Suite complète : 2746 tests, 6 min 27.

---

## 2. LE gisement : 56 % du temps dans `CubicSpline.__init__`

### 2.1 Ce que dit le profil

`cProfile` sur `test_metal_single`, données réelles, 89,6 s et 67 millions d'appels :

| Poste | Appels | Temps cumulé |
|---|---|---|
| `_single_RTRback_mse` (fonction objectif) | 66 357 | 78,4 s |
| **`scipy...CubicSpline.__init__`** | **121 238** | **49,9 s — 56 %** |
| `scipy..._cubic.prepare_input` | 242 476 | 24,1 s |
| `scipy...PPoly.__init__` | 121 238 | 23,9 s |
| `scipy.linalg.solve_banded` | 121 238 | 4,0 s |

L'optimiseur reconstruit **deux objets `CubicSpline` à chaque évaluation de la
fonction objectif**, 66 000 fois.

### 2.2 Pourquoi c'est évitable

Instrumentation sur le même run réel :

```
appels a get_nk_from_spline    : 77 163
vecteurs de noeuds DISTINCTS   : 18 831
taux de repetition             : 75,6 %
dont use_cache=False           : 77 143   (99,97 %)
```

Les positions de nœuds sont bien des variables d'optimisation — mais lors d'un pas de
différence finie **une seule variable bouge**. Quand c'est une *valeur* de nœud et non
une *position*, les nœuds sont inchangés et la base spline est réutilisable. Trois
appels sur quatre sont dans ce cas.

`SplineBasisCache` fait exactement ce travail, et `get_nk_from_spline(use_cache=True)`
l'emploie. Presque tous les appelants passent `use_cache=False`.

### 2.3 Le gain, mesuré

Même test, même session, en forçant `use_cache=True` :

| | Durée |
|---|---|
| `use_cache=False` (actuel) | **63,1 s** |
| `use_cache=True` | **29,8 s** |

**−53 %.** Et ce gain est obtenu *malgré* un cache saboté — voir §2.5.

Équivalence numérique vérifiée : `1,78e-15` d'écart maximal entre les deux chemins
(même `bc_type="natural"`, même `extrapolate=True`).

### 2.4 Les sites à traiter

```
certus/physics/gradient_metal.py     2 occurrences
CERTUS_METAL_BILAYER.py              2
CERTUS_METAL_SINGLE.py               3
```

Ne pas basculer en aveugle : pour chacun, vérifier que les nœuds sont bien constants
sur une part significative des appels. L'instrumentation du §2.2 se réécrit en dix
lignes et donne la réponse par module.

### 2.5 Le cache se saborde lui-même

`SplineBasisCache.get` contient :

```python
if len(cls._cache) > 500:
    cls._cache.clear()      # vide TOUT
```

Avec 18 831 vecteurs de nœuds distincts sur un run, ce garde-fou anti-fuite vide
intégralement le cache en boucle. À la fin du run mesuré, il ne restait que
**33 entrées**.

Le remplacer par une éviction LRU bornée (`collections.OrderedDict` ou
`functools.lru_cache`) conserverait la localité temporelle — les pas de différences
finies consécutifs partagent leurs nœuds. **Le −53 % mesuré est donc un plancher.**

---

## 3. Le second gisement : la dérivée par rapport aux positions de nœuds

`gradient_metal.py` calcule le gradient des positions λ par **différences finies** :
une reconstruction complète de spline par position, soit `num_knots − 1` par
évaluation de gradient.

Coût mesuré : ~400 µs par pas, soit ~2,8 ms sur les 5,0 ms d'un gradient complet —
**plus de la moitié**.

La dérivée analytique d'une spline cubique par rapport à la position d'un nœud est
dérivable, mais c'est un vrai travail de mathématiques, pas un ajustement. À
entreprendre **après** le §2, qui est bien plus rentable pour bien moins d'effort.

Garde-fou disponible : `tests/oracle/test_metal_gradient_vs_fd.py` vérifie déjà les
17 composantes du gradient métal, bloc par bloc. Toute dérivée analytique nouvelle y
sera confrontée immédiatement.

---

## 4. Déjà fait, pour mémoire

| Correctif | Gain mesuré |
|---|---|
| Base spline mise en cache dans `gradient_metal` | ×241 (1974 → 8,2 µs) |
| Clé de `get_nk_from_spline` en octets | ×29 sur chemin mémorisé, −12 % de bout en bout |
| Clé de `SplineBasisCache` en octets | ×5,1 (42,5 → 8,4 µs) |
| `@njit` restaurés sur deux noyaux | tests gradient 55 s → 5 s |
| Précision mixte f32/c64 retirée | −1,1 % de temps ET 8 ordres de précision regagnés |

---

## 5. Ordre de travail recommandé

1. **§2.5** — remplacer le vidage total du cache par une éviction LRU. Sans risque,
   et conditionne le rendement de l'étape suivante.
2. **§2.4** — basculer `use_cache=True` site par site, en instrumentant d'abord
   chaque module pour confirmer le taux de répétition. **Gain attendu : −50 % sur
   METAL_SINGLE et METAL_BILAYER**, soit ~80 s sur les 157 s que pèsent ces deux
   tests.
3. **Profiler les cinq autres modules** de la même façon — RE (41,6 s), INDEX
   (15,3 s), STRAT (9,3 s), DESIGN, INDEX_SPLINE. Le motif « reconstruction de
   spline dans la boucle chaude » est probablement présent ailleurs : la commande
   qui l'a révélé est reproduite au §6.
4. **§3** — dérivée analytique des positions de nœuds, seulement ensuite.

---

## 6. Reproduire les mesures

Profil sur données réelles :

```bash
QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -c "
import cProfile, pstats, pytest, io
pr = cProfile.Profile(); pr.enable()
pytest.main(['tests/headless/test_metal_single.py','-q','--no-cov'])
pr.disable()
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats('tottime').print_stats(20)
print(s.getvalue())
"
```

Taux de répétition des nœuds : envelopper `certus.physics.certus_optical_models
.get_nk_from_spline` et collecter `knots.tobytes()` dans un `set` — voir §2.2.

Vérification obligatoire après toute modification :

```bash
.venv/Scripts/python.exe -m pytest tests/oracle/ -q --no-cov
```
