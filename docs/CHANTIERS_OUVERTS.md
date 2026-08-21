# CHANTIERS OUVERTS — extrait de `CLAUDE.md` §27 le 2026-08-19

> Ce dossier **fait autorité** sur les chantiers listés ici. `CLAUDE.md` n'en garde qu'un
> renvoi qui dit *ce qu'il faut retenir sans ouvrir le dossier*.

🔑 **Pourquoi cette extraction.** `CLAUDE.md` touchait **1 990 lignes** sur un plafond de
2 000, et §27 en pesait **161** — dont deux propositions de 👤 encore **non mesurées**, qui
relèvent du journal de chantier et non des directives lues à chaque session. C'est très
exactement le diagnostic de `scripts/extraire_section.py` : *« le fichier mélange quatre
natures de contenu qui n'ont pas la même fréquence de lecture »*.

⚠️ **Rien n'a été résumé ni réécrit** au passage : le contenu ci-dessous est celui de §27,
déplacé tel quel.

---

- 📌 **LE PLAN DU 2026-08-16 EST ECRIT ET AUTONOME** :
  [`docs/PLAN_2026-08-16.md`](docs/PLAN_2026-08-16.md). Campagnes longues en mode **premium**,
  ordonnees par dependance, avec durees mesurees, commandes exactes, et ce que chaque resultat
  deciderait. 👤 le lancera sous Antigravity. Les cinq pieges du 15 aout y sont en tete, et
  la phase 1 repare l'instrument avant que quoi que ce soit d'autre ne tourne.


- 🔵 **PROPOSÉ PAR 👤 le 2026-08-15 — compter en Phase A les λ qui offrent un point tournant.**

  > 👤 : *« en routine, le code pourrait ou même devrait, en Phase A, regarder pour une couche
  > i le nombre de λ permettant de passer un turning point avec le swing minimal »*.

  🔴 **Ce n'est pas ce que Phase A fait aujourd'hui, et l'écart est réel.** Le filtre actuel
  (`certus_strat_service.py:868`) retient une λ candidate sur **deux critères d'amplitude** :

  | | |
  |---|---|
  | `dynamics ≥ dynamics_threshold` (0,025) | le **swing** crête-à-crête `T_max − T_min` pendant la croissance |
  | `t_min ≥ min_transmission_floor` (0,10) | le signal ne plonge pas sous le plancher photométrique |

  ⚠️ **Aucun des deux ne teste l'EXISTENCE d'un point tournant.** Une couche dont `T` croît de
  façon monotone pendant toute sa croissance a un swing parfaitement acceptable et **aucun
  extremum sur lequel s'arrêter**. Elle passe le filtre et n'offre pourtant pas de point
  d'arrêt. C'est exactement la distinction de §14 (QWOT ≠ point tournant).

  🟢 **Et la donnée nécessaire est déjà là** — c'est ce qui rend l'action bon marché.
  `prepare_dynamics_data_kernel` (`certus_strat_growth.py:1793`) calcule déjà `M_before`,
  `n_layer` et `n_sub` pour **chaque couche × chaque λ candidate**. La forme fermée
  `layer_scan_coeffs` en tire `Q` et `R` en O(1), et le compte de points tournants s'écrit

      k1 - k0 + 1   avec   delta_TP = ½·arctan2(R, Q) + k·π/2   dans ]0, δ_final]

  C'est **une dizaine de lignes**, sans nouveau parcours de l'empilement. Prototype déjà
  écrit et validé : `scripts/probe_turning_points.py`.

  **Ce que ça donnerait** : une largeur de monitorabilité par couche — *combien de λ offrent
  au moins un point tournant ET un swing suffisant*. C'est un diagnostic que rien ne produit
  aujourd'hui, et un candidat naturel pour décider où changer de verre témoin (§23.4), là où
  `S(p−1)` a échoué.

  📏 Mesuré sur le random75, médiane des λ offrant un point tournant, par couche :
  **49/61 à ×0,5**, **61/61 à ×1, ×1,5 et ×2**.

  ##### 🔵 Et la « phase intermédiaire » proposée dans la foulée — elle existe déjà

  > 👤 : *« entre la phase A et la phase B il pourrait y avoir une phase intermédiaire qui
  > cherche à minimiser les changements de longueur d'onde pour les couches admissibles en
  > turning point et dynamique »*.

  🟢 **La moitié « minimiser les changements de λ » est déjà faite, et c'est la DP de Phase B.**
  `_find_k_best_groupings_dp_sequential` (`certus_strat_ranking.py:291`) reçoit
  `cost_map[couche][λ] → coût` et `_compute_valid_blocks_kernel` cherche les blocs où **une
  seule λ sert TOUTES les couches du bloc**. C'est exactement l'optimisation décrite, elle est
  exacte (programmation dynamique, pas une heuristique), et elle rend les `top_k` meilleurs
  groupements.

  🔴 **Ce qui manque n'est donc pas la phase, c'est le CRITÈRE D'ADMISSIBILITÉ qu'elle
  consomme.** `cost_map` est bâti sur les candidates de Phase A, filtrées sur le swing et le
  plancher photométrique — **jamais sur l'existence d'un point tournant**.

  🔑 **Les deux propositions de 👤 se réduisent donc à UN seul changement** : ajouter le
  comptage de points tournants au filtre de candidature. La DP existante minimisera alors les
  changements de λ **sur le bon ensemble**, sans qu'on écrive de phase nouvelle.

  ⚠️ **Mais pas en exclusion sèche, et voici pourquoi.** Une couche sans point tournant reste
  déposable : elle s'arrête sur un **niveau absolu**, ou en **Rate**. Ce qu'elle perd, c'est
  l'ancre de phase auto-référencée dont POEM a besoin. Le compte de points tournants doit donc
  entrer comme **coût**, pas comme couperet — sinon on interdit des stratégies qui marchent.
  🔴 Et il y a un second effet, dans l'autre sens : `CRASH_TP_MISCOUNT` sanctionne une
  stratégie qui attend *N* points tournants et en voit *N ± 1*. **Trop** de points tournants
  proches est donc aussi un risque, pas seulement trop peu. Le coût doit être **non
  monotone**, et c'est une raison de plus pour le mesurer avant de le poser.

- 🟢 **NON URGENT — la Phase A ignore qu'une couche Rate efface l'historique.**
  *Établi le 2026-08-15, chiffré, et délibérément repoussé.*

  La Phase A **suit** la continuation de bloc (`block_start_running`, passé aux candidates
  via `phase_a_block_start`, `certus_strat_objectives.py:287`) : elle sait donc qu'une λ
  inchangée conserve les ancres. **Mais elle ne connaît pas `rate_flags`.** Or une couche
  Rate efface l'historique **exactement comme un changement de λ** — le noyau l'applique
  (`certus_strat_batch.py`, frontière de bloc forcée), la Phase A ne le prévoit pas.

  **Conséquence, et elle est bornée à UNE couche** : la λ de la couche `i+1` a été choisie en
  supposant un historique hérité que la couche `i` en Rate a détruit. Les couches `i+2` et
  suivantes héritent normalement du nouveau bloc et ne sont pas concernées.

  ⚠️ **Le score, lui, reste honnête** : la simulation paie bien la pénalité de rupture de
  bloc. Ce n'est pas une erreur de mesure, seulement un choix de λ sous-optimal sur une
  couche. Et une seule couche Rate par variante, par construction — l'effet ne se cumule pas.

  📏 **L'empirique dit que ça ne bloque rien** : sur le 99c, la gagnante était
  `RATE_L25(from 900000037)`. Les variantes Rate gagnent **malgré** cette sous-optimalité.

  **Le correctif tient en deux lignes** : passer `rate_flags` à la Phase A et forcer
  `block_start_running = i_layer` après une couche Rate, même règle que pour un changement de
  λ. 👤 : *« relancer la Phase A ne changerait pas grand-chose, on est dans la subtilité »* —
  c'est exact, et c'est pourquoi ce point passe **après** tout chantier qui touche au SEEL.

  🔑 **Rappel de 👤 sur le Rate, à ne pas perdre** : le facteur est calculé sur les couches
  **de même nature déposées AVANT** la couche `i` (`certus_strat_growth.py:634`, boucle
  `range(i_layer-2, -1, -2)`). Donc **`rate(i)` et `rate(j)` ont des facteurs différents même
  sur un matériau identique.** Ce n'est pas une constante par matériau.

- **Isolation des tests** — une fuite `sys.modules` faisait échouer en sélection large des
  tests qui passent isolément. Cause racine corrigée, audit restant :
  [`docs/REPRISE_TESTS_ISOLATION.md`](docs/REPRISE_TESTS_ISOLATION.md).
- **Performance** — 📏 mesuré le 2026-08-04 : **il n'y a PAS de ×2 disponible** dans les
  pistes documentées. Seul gain acquis : −10 % sur STRAT. Le fossé machine va de ×1 à ×3,2
  selon les modules, pas ×7-10. [`docs/REPRISE_PERF.md`](docs/REPRISE_PERF.md) — ⚠️ ses
  **temps absolus** datent d'avant le déménagement hors Google Drive ; les *rapports* restent
  utiles, les secondes non.
- **Amélioration générale** — [`docs/PLAN_AMELIORATION.md`](docs/PLAN_AMELIORATION.md) : dette
  de lint, tests absents de la CI, six chantiers ordonnés.
