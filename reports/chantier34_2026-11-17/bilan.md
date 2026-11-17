# Chantier 34 — bits selon l'historique de compilation, 2026-11-17

Sur `08e3bb2c`, Python 3.15.2, une mesure à la fois. Trois tests au bit : la fente
(`test_a_slit_bias_moves_the_probes_and_not_the_level`, rouge à la validation du matin sous charge ;
`test_the_slit_profile_is_inert_when_absent_or_zero`, rouge par intermittence depuis le 14) et POEM
(`test_without_the_flag_the_kernel_keeps_the_coarse_samples_bit_for_bit`).

| cache Numba (`NUMBA_CACHE_DIR`) | résultat |
|---|---|
| vierge, les trois tests seuls | 3 passed ([sortie](B_cold_alone.txt)) |
| vierge, rempli par `tests/unit` entier, 30 workers | 6359 passed, aucun échec au bit ([fin](A_unit_tail.txt)) |
| ce cache rempli, les trois tests seuls | 3 passed ([sortie](A_polluted_alone.txt)) |

- Les échecs ne se reproduisent ni sur cache vierge ni après une étape `unit` complète sur ce cache : ils ne sont
  apparus que sur le cache partagé de l'arbre, rempli par des processus et des versions de code successifs. Cohérent
  avec le mécanisme établi pour POEM (audit général du 14, §6 : une spécialisation liée à d'autres `complex_mul` et
  `complex_div` selon l'historique), **non prouvé** pour la fente : il faudrait l'objet coupable, comme pour POEM.
- **Décision** (déléguée par 👤 le 2026-11-17) : les noyaux restent dépendants de l'historique. Les rendre
  indépendants changerait les bits de tous les résultats (C1) pour des écarts de l'ordre de 1e-13 nm, sans effet
  physique. Règle maintenue : comparer au bit froid contre froid ou à historique égal (`c1_diff.py`) ; un échec au bit
  en parallèle est rejoué sur cache vierge (`validate_parallel.py`, `f350044d`).
