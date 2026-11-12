# Un test « au bit » rouge à chaque relance, à cause du cache Numba d'un arbre neuf

Mesuré le 2026-11-11 et le 2026-11-12, worktree `certus-1111-reprise-60e136`, commit `e9f68946`, Python 3.15.2, clé du
cache `832213ea6465`. Trouvé par la validation complète de la Phase 10 ; sans rapport avec ses correctifs (aucun des neuf
fichiers modifiés ne cite Numba, la clé n'a pas bougé).

## Le fait

`tests/unit/test_strat_poem_anchors_are_exact_on_request.py::test_without_the_flag_the_kernel_keeps_the_coarse_samples_bit_for_bit`
compare `simulate_growth_kernel` appelé avec ses derniers arguments omis et avec `False` écrit : deux spécialisations
Numba du même noyau `fastmath`. Il exige l'égalité au bit.

| Cache lu | omis (`True`) | écrit (`True, False`) | omis | écrit (`False, False`) | Test |
|---|---|---|---|---|---|
| celui de l'arbre, rempli par plusieurs processus | 150.0000000000008 | 150.0000000000001 | 150.0000000001665 | 149.99999999996368 | **rouge**, 3 fois sur 3, en parallèle et seul |
| vierge (`NUMBA_CACHE_DIR` sur un dossier neuf), un seul processus | 150.0000000000008 | 150.0000000000008 | 150.0000000001665 | 150.0000000001665 | vert (`7 passed`) |
| celui de l'arbre, vidé puis rempli par `validate_parallel.py --only unit` | 150.0000000000008 | 150.0000000000008 | 150.0000000001665 | 150.0000000001665 | vert |
| celui du worktree précédent (`8088dc4c`, même clé) | — | — | — | — | vert (`7 passed`) |

L'écart est de 7·10⁻¹³ nm et de 2·10⁻¹⁰ nm sur une épaisseur d'arrêt : sans effet physique, mais le test demande le bit.

## Ce qui l'explique

Le cache de l'arbre neuf a reçu 41 spécialisations de ce noyau en deux temps (dates des fichiers `.nbc`) : 4 à 23:01,
pendant un lot de contrôle (le préchauffage d'une fenêtre), puis 37 entre 23:26 et 23:36, par les 16 processus de la
validation. C'est l'effet décrit en référence §5 : un noyau `fastmath` n'a pas toujours les mêmes derniers bits selon
le contexte où il est compilé. Les deux spécialisations que le test compare venaient de deux contextes.

## Deuxième occurrence, 2026-11-12 : l'écart est déterministe

La Phase 7b a changé la clé du cache (`23ad45b8a350`). La validation complète de `aa75be4f` a rendu le même test rouge,
seul aussi, avec **les quatre mêmes valeurs au chiffre près** que la veille (150.0000000000001 et 149.99999999996368
pour les deux appels écrits). Le cache avait reçu le noyau dans le même ordre : 4 spécialisations pendant un lot
(03:59), 38 pendant la validation (04:04 à 04:12). Sur cache vierge, de nouveau `7 passed`.

Deux hypothèses essayées, chacune sur un cache vierge, un seul processus, et **réfutées** :

| D'abord | Artefacts du noyau après | Puis le test | Valeurs |
|---|---|---|---|
| `tests/integration/test_suite_ui_instantiation.py` (le préchauffage des fenêtres) | 4 | `7 passed` | égales deux à deux |
| `tests/oracle/` | 0 | `7 passed` | égales deux à deux |

Ni le préchauffage des fenêtres ni l'oracle ne produisent la spécialisation décalée. Elle vient donc de l'étape `unit`
en parallèle, sur un cache qui contient déjà une partie du noyau.

**Non trouvé** : quel test, dans quel processus, compile la spécialisation décalée. Le rejeu vert de la veille (cache
vidé, puis `validate_parallel.py --only unit`) n'a été fait qu'une fois : il peut tenir à l'ordre des 16 processus.

## Ce que cela change

- La règle de la référence §2, « un échec persistant est réel », a ici un contre-exemple : l'échec persistait tant que
  le cache restait en place, et le code était juste. Le discriminant est une relance sur cache vierge :
  `NUMBA_CACHE_DIR=<dossier neuf>` devant la commande pytest.
- Même famille que l'artefact noté dans `docs/ETAT.md` (`test_neutral_parameters_are_bit_identical_to_the_legacy_call`,
  deux résultats au bit sous xdist) et que `test_strat_phase_a_state_coherence.py::test_the_slit_profile_is_inert_when_absent_or_zero`,
  rouge en parallèle et vert seul dans les deux validations de cette nuit.
- Le test n'a pas été modifié. À 👤 de dire s'il doit exiger le bit entre deux spécialisations.

Les deux caches fautifs sont gardés, hors dépôt : `%TEMP%\CERTUS_Numba_Cache_set_aside_2026-11-11_2350` et
`%TEMP%\CERTUS_Numba_Cache_set_aside_2026-11-12_0430` (quatre dossiers chacun). Le cache de l'arbre repart vide.
