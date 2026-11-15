# Chantier 44 — où une recherche STRAT complète passe son temps, et la couche TBB (2026-11-15)

`python scripts/bench_examples.py strat --auto-yes --sample` sur le juge de paix (`JSON-strat-example.json`, 48 couches),
Windows, 16 cœurs logiques, Python 3.15.2, Numba 0.68.0. Une recherche par configuration. Sorties : `bench*.txt`
(résultat, classement, profil), `probe_threads*.txt`. Les journaux complets (`console*.txt`, 11 Mo chacun) ne sont pas versionnés.

## 1. Profil, couche OpenMP (`bench.txt`)

`RUN_S=1338.759`, `RESULT=0.005861922892702524`.

| phase (horodatage du journal) | durée | part |
|---|---|---|
| Phase A, cartes de coût | 2 min 47 s | 12 % |
| Phase 3 : DP, ELITE, robustesse, consensus | 10 min 30 s | 47 % |
| Recherche locale finale, deux passes (877 puis 1 686 évaluations) | 9 min 00 s | 40 % |

Temps des fils Python dans le calcul (échantillonnage) : croissance simulée (`simulate_stack_robustness_batch`) 39 %,
spectre de chaque tirage (`compute_batch_rmse`) 38 %, matrices de la phase A (`build_M_before_cache`) 14 %, spectre
nominal (`calculate_RT_vectorized_real_HL`) 8 %. Le consensus prend environ 35 % du temps de robustesse. L'échantillonneur
ne voit pas les fils natifs de Numba : ces parts sont celles des fils Python qui attendent un noyau.

## 2. Fils Numba par pool : rejeté (`bench_pools.txt`)

Chaque fil des pools de robustesse et de consensus réglé à `cœurs ÷ ouvriers` fils Numba. La sonde
(`probe_threads.py`, 128 tâches) donnait ×1,1 à ×1,4 à bits identiques. Recherche réelle : `RUN_S=1783.459`, classement
identique. L'étape à 48 blocs, qui n'évalue que 2 stratégies, passe de 25 s à 5 min 56 s (2 fils Numba par tâche au
lieu de 16) ; à 240 stratégies par bloc, aucun gain (73 s contre 79 s par bloc). Retiré.

## 3. Couche TBB : retenue pour STRAT seul (`bench_tbb.txt`)

`RUN_S=1074.208` (OpenMP : 1 338,759), `RESULT=0.005861922892702511`, classement identique au §1.

| phase | OpenMP | TBB |
|---|---|---|
| Phase A | 2 min 47 s | 23 s |
| Étape à 48 blocs | 25 s | 18 s |
| Blocs 9 à 5 | 73 s par bloc | 55 s par bloc |
| Recherche locale | 9 min 00 s | 9 min 27 s |

Identité : la croissance et le score de 16 tâches du plan ELITE réel donnent la même empreinte sha256 sous OpenMP et
sous TBB (`fcca8d613b8db8e0`). Le `RESULT` varie au 14e chiffre d'une recherche à l'autre sous la même couche
(…702524 et …702714 sous OpenMP) : c'est le chantier 34, pas la couche.

## 4. Déterminisme sous TBB (ouvrier de `c1_diff`, 4 ou 16 fils)

| comparaison | tableaux différents |
|---|---|
| OpenMP contre TBB, corpus `normal`, `oblique`, `strat`, `appelants` | 97 sur 9 172 : coût et gradient de DESIGN (`normal.cost0/1`, `normal.gradall1` et leurs variantes absorbantes), au plus 3 ulp, 4,3e-16 relatif |
| TBB contre TBB, même cache chaud, corpus `normal` | 53 sur 2 985 : les mêmes points d'entrée |
| OpenMP contre OpenMP, même cache chaud, corpus `normal` | 0 sur 2 985 |
| TBB contre TBB, corpus `strat`, `oblique`, `appelants` | 0 sur 6 187 |

Les sommes parallèles du coût et du gradient de DESIGN changent d'ordre d'un lancement TBB à l'autre ; les boucles
parallèles de STRAT calculent chaque élément à part. D'où le choix : TBB pour STRAT et les processus qu'il lance
(`certus_core.STRAT_THREADING_LAYER`, `register_tbb_runtime`), OpenMP partout ailleurs.

## 5. Limites

- Une recherche par configuration. La phase A, non modifiée entre les §1 et §2, a varié de 2 min 47 s à 3 min 34 s :
  une seule recherche ne mesure pas un écart de 10 %. Le gain de la phase A sous TBB (×7) dépasse ce bruit ; celui des
  blocs (−25 %) le dépasse de peu.
- La recherche locale ne gagne rien : elle évalue une stratégie à la fois. Elle représente maintenant la moitié du temps.
- Le juge de paix seul ; aucun composant plus profond mesuré.
