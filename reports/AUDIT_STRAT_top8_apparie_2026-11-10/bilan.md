# Audit STRAT — le haut du classement en différences appariées (2026-11-10)

Les tirages `.npz` et métadonnées `.json` sont conservés localement à côté des scripts d'analyse. Les trois journaux
bruts sont dans `artifacts/archives-20261114/journaux-strat-top8-20261110.zip`.

**Question.** Les écarts entre les premiers plans sont-ils réels quand on compare les plans sur les mêmes tirages (C2),
et où chercher un meilleur plan ?

## 1. Protocole

- **Capture** : `capture_final_ranking.py` lance `bench_examples.run_strat()` sur
  `example/example_strat/JSON-strat-example.json` tel quel et écoute `dump_strat_ranking`. Commit `9632f15b`,
  `git_dirty` vrai (aucun fichier de `certus/` modifié). `RUN_S=1550.956`, `RESULT=0.005861922892702714`.
  2 653 plans classés, 301 avec leurs tirages (`keep_full_mc_top_k`), 150 tirages, niveaux 0,025 / 0,05 / 0,1.
- **Analyse** : `paired_top8.py`, sortie complète dans `paired_top8.out`. Bootstrap de 4 000 rééchantillonnages des
  tirages, mêmes indices pour tous les plans (apparié) ou indépendants (non apparié) ; 2 000 partages en deux moitiés.
- **Contrôle** : le P95 par niveau recalculé est égal au `rmse_p95` stocké (écart nul). Le `robustness_score` du
  classement est le score de consensus (`robustness_score_consensus`), pas celui de la graine de base
  (`robustness_score_base`) : les tirages capturés sont ceux de la graine de base seule, d'où 0,1537 nm ici contre
  0,1531 nm au classement pour le premier.

## 2. Modèle actuel : un plan seul en tête, un plateau en dessous

| rang | origine | blocs | P95 par niveau (0,5× / 1× / 2×) | SEEL (nm) |
|---|---|---|---|---|
| 1 | `LOCAL_SEARCH` | 34 | 0,00308 / 0,00392 / 0,00591 | 0,1537 |
| 2 | `ELITE` (son parent) | 2 | 0,00678 / 0,00711 / 0,00761 | 0,1745 |
| 3 à 6 | `ELITE` | 2 | — | 0,1769 à 0,1794 |
| 7 à 12 | `ELITE` | 3 | 0,00728 / 0,00720 / 0,00770 (identiques) | 0,1755 |

- **Le plan de la recherche locale est séparé** : écart au deuxième +0,0207 nm, σ apparié 0,0062 nm (z = +3,34) ;
  RMSE² moyen apparié au niveau nominal +155,3 % pour le deuxième (z = +9,74). Il gagne 100 % des rééchantillonnages
  et 100 % des partages en moitiés. La classe d'égalité de 0,01 nm ne contient que lui.
- **En dessous, un plateau** : choisis sur une moitié des tirages, les rangs 2 à 8 valent 0,1722 à 0,1752 nm ; jugés
  sur l'autre moitié, 0,1786 à 0,1794 nm, soit tous égaux, avec 0,004 à 0,006 nm d'optimisme de sélection.
- **Tirages communs** : corrélation des RMSE par tirage entre les huit premiers 0,855 / 0,772 / 0,735 selon le niveau
  (minimum 0,599 / 0,344 / 0,197) ; sur les 297 plans au niveau nominal, 0,793. L'appariement ne resserre pas l'écart
  entre le plan de la recherche locale et les autres (σ 0,0061 non apparié, 0,0062 apparié).
- **Le niveau 2× décide le score** de 98 % des plans. Les plans `ELITE` sont presque plats d'un niveau à l'autre ; le
  plan de la recherche locale ne l'est plus (0,79 / 1 / 1,51 rapporté au nominal).
- **Recherche locale non convergée** (journal `capture.out`) : passe 1, 22 changements ; passe 2, 38 au total, donc 16
  encore acceptés ; le plan complet est refusé au contrôle (arrêts 0 → 1), le repli après 35 changements est gardé.

## 3. Archive d'août : un plateau, sans recherche locale

`reports/probe_functional_raw.npz` (commit `9070d438`, 2026-08-06, avant le corridor d'indice et la recherche locale ;
130 plans, 150 tirages). Aucun des huit premiers ne se sépare du premier en apparié (|z| ≤ 1,36) ; 26 plans gagnent au
moins un rééchantillonnage ; le premier d'une moitié est le meilleur des huit sur l'autre dans 12,7 % des cas (hasard
12,5 %) ; optimisme de sélection du premier 0,2955 → 0,3061 nm. Les plantages n'étaient pas capturés.

## 4. Ce qui n'est pas mesuré

- Une seule graine de base, un seul composant (le dichroïque 48 couches), 150 tirages.
- Les graines du consensus ne sont pas capturées.
- `audit_stats.py` est un modèle jouet indépendant de CERTUS : ses chiffres ne valent pas mesure du code.

Les rangs 7 à 12 portent six identifiants pour un même plan : leurs tirages sont identiques un à un.

## 5. La recherche locale éprouvée dans son contexte de production

`ls_lab.py` écoute `joint_local_search` pendant un run complet : chaque variante reçoit les évaluateurs, la
configuration et les graines de production, et l'appel de production rend son résultat inchangé. Tous les plans sont
jugés sur quatre graines que ni la recherche, ni son contrôle, ni sa confirmation n'ont vues (base + 7 300 003, 011,
019, 027 ; 4 × 1 000 tirages par niveau). Écarts appariés par `lab_analysis.py` (`ls_lab_analysis.out`), sous le
corridor configuré (±0,005), référence : le plan que la production accepte.

| plan | SEEL (nm) | écart à la production | z apparié | arrêts sur 12 000 |
|---|---|---|---|---|
| départ (`ELITE`, 2 blocs) | 0,1696 | +0,0140 (+9,0 %) | +10,7 | 0 |
| production (recherche locale) | 0,1556 | — | — | 0 |
| deuxième tour depuis ce plan | 0,1532 | −0,0024 (−1,5 %) | −2,8 | 0 |
| troisième tour | 0,1506 | −0,0050 (−3,2 %) | −4,3 | 0 |
| critère jugé au niveau 2× | 0,1683 | +0,0127 (+8,2 %) | +9,9 | 0 |
| autre départ (`ELITE`, 48 blocs, tête à 489 nm) | 0,1578 | +0,0022 (+1,4 %) | +1,9 | 1 |

- **Relancer la recherche depuis son résultat gagne encore**, deux fois de suite ; sous le corridor de recherche
  (±0,010) : 0,1718 → 0,1693 → 0,1641 nm (z = −3,2 puis −8,4). Un tour coûte environ 8 minutes.
- **Juger au niveau 2× perd** : le contrôle voit 9 arrêts et le repli ne garde que 7 changements sur 23.
- **Un autre départ ne gagne pas**, mais la recherche locale le ramène de 0,2061 nm à 0,1578 nm : elle n'est pas
  prisonnière de son départ, sur ce seul essai.
- **Rejeu** : même journal de recherche locale que la capture, même classement ; `RESULT=0.005861922892702511`
  contre `0.005861922892702714`, soit un écart relatif de 3,5e-14. Les deux laboratoires rendent la même valeur au
  dernier chiffre ; `docs/REGLES_reference.md` §5 attribue ce genre d'écart à une recompilation du noyau. Je n'ai pas
  mesuré que c'est la cause ici.

## 6. Jusqu'où vont les tours, et avec quelles graines

`rounds_lab.py` : deux chaînes de tours depuis le plan de production, jusqu'au premier tour refusé. `S` reprend à chaque
tour les graines de production ; `F` décale ses graines de recherche, de contrôle et de confirmation de 16 par tour.
Mêmes graines de jugement qu'au §5 (`rounds_lab_analysis.out`), référence : le plan de production.

| plan | SEEL à ±0,005 (nm) | z apparié | SEEL à ±0,010 (nm) | z apparié | arrêts sur 12 000 (±0,005 / ±0,010) |
|---|---|---|---|---|---|
| production | 0,1556 | — | 0,1718 | — | 0 / 0 |
| `S2` | 0,1532 | −2,8 | 0,1693 | −3,2 | 0 / 0 |
| `S3` | 0,1506 | −4,3 | 0,1641 | −8,4 | 0 / 0 |
| `F2` | 0,1522 | −3,0 | 0,1648 | −6,0 | 0 / 2 |
| `F3` | 0,1506 | −4,7 | 0,1611 | −11,0 | 0 / 0 |

- **Trois tours utiles, le quatrième est refusé dans les deux chaînes** (`S4` : 7 arrêts au contrôle ; `F4` : aucun
  gain sur ses tirages de contrôle). Un tour coûte 510 à 594 s sur cette machine.
- **Les graines neuves font aussi bien à ±0,005** (`F3` contre `S3` : écart nul, z = 0,0) **et mieux à ±0,010**.
  Elles évitent aussi de rejuger un plan sur les tirages qui ont servi à choisir le précédent.
- **Rejeu exact** : `S2` et `S3` sont les plans du deuxième et du troisième tour du §5, à l'identique.
- Le plan `F3` a 37 blocs, 18 longueurs d'onde et 14 couches en Rate, contre 34, 14 et 13 pour la production.

## 7. Ce qui est porté dans le code

`strat_local_search_rounds` (défaut 1, donc le chemin d'avant) : `further_rounds` dans
`certus/core/certus_strat_local_search.py`, appelé par `run_local_search` ; le levier est déclaré dans
`certus/core/certus_strat_leviers.py` avec sa mesure et sa réserve. Chaîne `F` : graines décalées de `ROUND_SEED_STEP`
par tour, arrêt au premier tour refusé.

## 8. Pistes réfutées ou non confirmées

- Juger la recherche locale au niveau 2× (§5).
- Partir d'un autre plan (§5, un seul essai).
- Départager le haut du classement par plus de tirages : en août il n'y avait rien à départager, aujourd'hui le
  premier est seul (§2, §3).
