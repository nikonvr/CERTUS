# CERTUS — état du projet

> Ce document porte l'**état** : où en sont les programmes, les repères mesurés, ce que 👤 a
> décidé, les défauts ouverts et les chantiers. Les **règles** sont dans
> [`CLAUDE.md`](../CLAUDE.md). Il se tient **en place** : un fait change, on corrige sa ligne,
> on ne raconte pas la correction (`git log` s'en charge). Toute mesure porte sa date.
> Le détail et l'historique sont dans `git`, sans autorité (CLAUDE.md, en-tête).
> Mis à jour le 2026-10-25.

## 0. Reprise — à lire en premier, à tenir à jour

> L'état présent seulement ; l'historique est dans `git log` et `reports/`. À la demande : actions ouvertes et protocole de mesure
> ([`ETAT_actions.md`](ETAT_actions.md)), acquis ([`ETAT_acquis.md`](ETAT_acquis.md)), registre des audits ([`AUDITS.md`](AUDITS.md),
> `grep -n "ALG-02" docs/AUDITS.md`), preuves dans `reports/` (le `bilan.md` d'un dossier).

**Branche de travail** : `claude/integration-2026-10-25` (worktree `%TEMP%\int_wt`), locale, ni poussée ni fusionnée dans `master` ; elle
réunit `gemini/2026-10-21` et `claude/2026-10-22`, séparées du 2026-10-21 au 2026-10-25 ([audit](../reports/AUDIT_travaux_2026-10-21_25/bilan.md)).

**STRAT** : réglages par défaut au §3 ; défaut ouvert : à bas bruit, le seuil des points tournants passe sous l'ondulation du biais de
fente et fabrique de faux points tournants ([analyse](../reports/ANALYSE_claude_2026-10-22/bilan.md)).

**DESIGN** : mémétique et relances par défaut depuis le 2026-10-23 ; séparatrice 400–1200 nm à 0,000135, et 8,6e-5 sur le problème de
Tikhonravov et al. 1996 contre 1,77e-4 pour leur design ([bilan](../reports/DESIGN_bs5050_2026-10-22/bilan.md)).

**Bonne Mère, 90 couches sur silice** : plan à déposer, fait à la main sous les règles de 👤 : 15 Rate, SEEL 0,2608 nm au holdout.
STRAT natif avec l'étape libre avant la conversion : 0,2655 nm, une graine, sans la garde ; A16 le remesure
([bilan](../reports/BONNE_MERE_strat_90c_2026-10-23/bilan.md)).

**Dernière validation complète** : 2026-10-25, `3260c766`, `python scripts\validate_parallel.py` GO ; C1 non remesuré après la fusion.
Avant de committer du code, la validation de CLAUDE.md §2 en entier : un sous-ensemble a déjà laissé passer une régression
(`tests/unit/test_the_architecture_debt_only_shrinks.py` ne tourne pas avec les tests voisins).

**Décisions qui n'appartiennent qu'à 👤** : §5. Une IA ne les tranche pas, elle rapporte les mesures.

## 1. Où en sont les programmes

| programme | état | prochaine action |
|---|---|---|
| **Calcul (STRAT)** | étalon : `r75x2` à la fente de 2 nm. Recherche locale finale active avec sa garde au corridor configuré ; sur `r75x2`, −13,3 / −11,1 / neutre / −9,7 % de SEEL selon la graine de banc ([bilan](../reports/STRAT_garde_2026-10-22/bilan.md)). Sans rampes, aucun plan optique pur n'est déposable ; avec le secours Rate, tous les plans de la liste le sont, au modèle de Rate de STRAT (§7) | A9, A13, A16 ([`ETAT_actions.md`](ETAT_actions.md)) |
| **Conception (DESIGN)** | étape globale mémétique, champion sans couche < 5 nm et relances par défaut depuis le 2026-10-23 ; séparatrice 400–1200 nm à 0,000135 depuis l'exemple ([bilan](../reports/DESIGN_bs5050_2026-10-22/bilan.md)) ; le mode oblique calcule sur 2 points au lieu de 135 (ALG-03) | ALG-03, ALG-13 à ALG-28 (`AUDITS.md`) |
| **RE** | indices tabulés lus en n − ik depuis R148 (2026-10-05) : un RE antérieur sur indices absorbants en incidence oblique est à refaire ; un indice demandé hors de sa table est prolongé par une constante, avec un avertissement | — |
| **Base de dépôts** | 140 monocouches mesurées au Photon RT (`example/database_depots/`), chargées par INDEX (« Deposit database… ») ; la voie (T ou R) se lit dans la géométrie du détecteur. Onze ajustements certifiés servent de références (`references_index.json`, `scripts\bench_base_depots.py`) : neuf à moins de 2 % d'épaisseur, deux écarts expliqués (`docs/AUDITS.md` IDX-01). RE ne la lit pas (il lui faut un classeur complet) | IDX-01 ; §5 |
| **Exécutable gelé** | couche OpenMP (D87), 411 Mo (D72), sans les outils de développement ; construit à `dbec2fc1`, « l'exécutable fonctionne » (👤). Licences embarquées dans `licenses/` | D72 |
| **Interface** | plan clos le 2026-09-08 : 12 critères de fin sur 13, le treizième démontré inatteignable (`xfail` strict) | §5 |
| **Qualité** | CI : calcul sous Linux, interface et gel sous Windows, `pip-audit`, `gitleaks` ; tests isolés des préférences de 👤 ; aucune arête d'import montante (D26) | §5 |
| **Validation externe** | 🔴 **aucune** : STRAT n'est validé que contre lui-même (👤, 2026-10-06 : les dépôts réels du dichroïque ne sont plus prévus) | — |

## 2. Repères mesurés — conditions précisées par ligne

Six bancs officiels du 2026-10-21, code `85a9e82f`, graine 42 ([résultats et preuves](../reports/STRAT_A3_reperes_reprise_2026-10-21/bilan.md)).
SEEL du `RESULT` officiel ; taux de plantage de `RANK00`.

| composant | SEEL (nm) | plantage RANK00 | condition |
|---|---:|---:|---|
| dichroïque 48 couches, `JSON-strat-example` | **0,172 nm** | 0 % | premium ; fente 2 nm, recherche de fente ; 2 652 stratégies, 2 blocs |
| passe-bande 3 cavités, vrai 35 couches | **0,4907** | 0 % | deep ; fente 2 nm, recherche ; 1 245 stratégies, 5 blocs |
| passe-bande 3 cavités deep livré, 36 couches | **0,3238** | 0 % | deep livré ; fente 2 nm, recherche ; 1 440 stratégies, 29 blocs |
| aléatoire `JSON-strat-random75`, 75 couches | **0,2225** | 0 % | fast livré ; fente fixe 2 nm ; 2 634 stratégies, 51 blocs |
| aléatoire ×2 `r75x2`, fente native 1 nm | **0,5833** | 0 % | deep livré ; fente fixe 1 nm ; 3 946 stratégies, 15 blocs |
| `r75x2` avec ses rampes livrées, fente 2 nm | **0,5092** | 0 % | deep livré ; fente fixe 2 nm ; 4 691 stratégies, 56 blocs |
| passe-bande 5 cavités, 99 couches, quatre verres témoins | **0,597** (médiane ; 0,575-0,670, graines 42/101/202) | 0 % | fast ; fente 2 nm ; partition 0-22-42-76-99 ; domaine d'indice = grille spectrale, `index_corridor_fixed_domain` armé ([rapport](../reports/STRAT_A3_99c_grille_2026-10-24/bilan.md)) |

**Lire ces chiffres :**

- 🔴 **Les SEEL ne se comparent pas d'un composant à l'autre** (domaines de notation différents, §7) ; à composant fixé, oui.
- 🔴 **Un score seul ne départage rien** : à 150 tirages σ ≈ 6 %, deux runs à moins de ~8 % sont indiscernables ; sur `r75x2`,
  σ ≈ 1,8 % en changeant le triplet de graines de consensus. On compare des classes d'équivalence SEEL.
- Ce sont des minimums de recherche, pas des confirmations de plans figés ; les populations ne comptent pas les plans optiques purs.
- Ils comprennent le **biais de fente** ; une mesure sans lui ne leur est pas comparable. Garder `RESULT` et `RANK00` séparés (R130).
- La **structure**, plus que la longueur, met le monitoring optique en échec (75 couches aléatoires passent, 99 couches à cavités non).
- Un 100 % en `fast` ne conclut rien ; un 100 % qui tient en `deep` est un constat.
- Banc : `CERTUS_BENCH_TIMEOUT_S = max(5400, 4 × durée attendue)` ; au-delà, `RESULT=None` (chercher `WAIT_TIMEOUT=`).

## 3. Ce que 👤 a décidé — ne pas rouvrir sans mesure qui le contredise

### Réglages

| réglage | valeur |
|---|---|
| cadence machine | 4 Hz, une lecture témoin par tour, un point tous les 0,125 nm à 0,5 nm/s |
| bruit de lecture | ±0,05 point, soit `A = 5e-4` en unités T |
| `reading_smoothing_window` | 1 (inactif) en exploitation ; 8 lectures dans le modèle figé |
| `tp_hysteresis_factor` | 1,66 (le seuil suit le niveau de bruit simulé) ; `tp_hysteresis_floor` 0,000415, maintenu par 👤 le 2026-10-23 malgré le défaut à 0,5× ([analyse](../reports/ANALYSE_claude_2026-10-22/bilan.md)) |
| `phase_a_level_margin_factor` | 1,66 ; 3,33 à évaluer |
| `index_corridor` | 0,005 en indice absolu, actif |
| DESIGN, étape globale (2026-10-23) | mémétique, 1000 enfants, population 30 (`_memetic_children = 0` : PGLOBAL) ; champion Pareto sans couche < 5 nm, actif ([bilan](../reports/DESIGN_bs5050_2026-10-22/bilan.md)) |
| `photometric_curvature_amp` ; `affine_scale_amp`, `affine_offset_amp` | 0,00375 ; 0,05 et 0,02 |
| `allow_rate`, `rate_by_swing`, `rate_rescue` (`rate_rescue_few` 10) | vrais (« le cas général », 2026-10-12) |
| `elite_rate_moves`, `elite_rate_max_candidates` | vrai, 120 (2026-10-13) |
| `strat_local_search` | actif : recherche et contrôle à ±0,010, garde au corridor configuré (`strat_local_search_guard`, 2026-10-23) |
| `slit_bias_enabled` | vrai, fente nominale 2 nm ; choix de l'opérateur 5, 1 ou 0,5 nm (bruit ÷1,5, ×2, ×5) |
| profondeurs par mode | `robustness_num_runs` 50 / 150 / 300, `n_screen_runs` 10 / 25 / 50, `dp_top_k` 20 / 40 / 100 (fast / premium / deep) ; le mode l'emporte sur le fichier (ligne `[MODE]`) |
| graine de référence ; grille des λ de contrôle | 42 ; 1 nm (`scan_wl_step`) |
| `machine_sampling_dd` | 0, figé dans le noyau (~21 points par couche) : le modèle est optimiste sur les faux points tournants |
| cible spectrale ; mode par défaut | non pondérée ; `premium` |

**Modèle de la chaîne de lecture (OMS 5100), figé le 2026-08-08** : une lecture par tour ; bruit additif borné ±0,05 point (σ = A/3),
indépendant d'une lecture à l'autre ; moyenne glissante de 8 lectures dans le modèle seulement ; seuil de point tournant mesuré 1,00 A à
k = 8 (la loi en 1/√k est réfutée) ; aucun retard de déclenchement ; marge de sélection 5 σ (1,66 A). Hors modèle, à y laisser : σ
dépendant de T ou de λ, grenaille, bruit multiplicatif ou corrélé. Seul un run réel du dichroïque rouvrirait ce modèle.

### Règles gravées

- Une λ de contrôle est interdite si, signal bruité, elle risque de mal compter les points tournants ou de ne pas s'arrêter ; la marge
  se compte **en transmission**. Les λ se choisissent sur la grille de balayage (`_resolve_monitoring_wavelength_grid`).
- Les heuristiques de la littérature (15-85 %, amplitude de départ, swing) sont des colonnes explicatives, jamais des couperets.
- **Rate interdit sur les couches 0 et 1** (`RATE_MIN_LAYER = 2`) ; la vitesse se calcule sur les couches du même matériau déposées
  optiquement ; une couche Rate lègue son erreur en boucle ouverte à ce qui suit.
- **SEEL = 2 × √score**, en nm ; classement final : classe à 0,01 nm du meilleur SEEL, puis rendement, puis marge critique (D20, R130).
- `fast` crible, il ne publie pas ; `extreme` n'a aucune justification mesurée. La profondeur Monte-Carlo sert à noter, jamais à choisir.
- Le multi-témoins est un outil de faisabilité (champ « New test glass at layers: », `witness_reset_layers`, vide par défaut).
- Un seul indice de saphir : le Sellmeier d'id 3, partout (2026-10-12).

### STRAT

- `RESULT` est le score du premier classé : P95 du RMSE au pire des trois niveaux de bruit, **tirages plantés compris** ; le consensus
  le remplace par moyenne + `consensus_std_weight` écarts-types sur ses graines (scores finis seulement) (D7, D6).
- D73 corrigé (marge au sommet interpolé) ; D70 retiré ; D17 conservé (gain négatif) ; D15 : quatre couches d'historique POEM ;
  D14 : 16 points d'historique ; D9 : sous un nombre minimal de blocs la DP ne rend que les graines structurées, et le journal le dit ;
  D8 : les quatre intervalles retenus du 99c restent déposables avec la recherche de fente ; sans changement : D12, D13, D16, D18, D19, D22.
- **Arrêt** : D96 et D97 actifs (ancre et inversion exactes de l'arrêt POEM) ; **D98, l'OMS attend sans fin** (`oms_arming` = 2) ;
  D99 n'est pas un défaut (lecture d'arrêt brute) ([rapport](../reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md)).
- **Rate dans tous les scénarios** : couche posée au temps, à la vitesse estimée (`_rate_layer_thickness`) ; secours Rate, enfants
  d'ELITE qui gardent et déplacent les couches Rate, optique possible après du Rate ; `rate_rescue_hard` inactif (sans gain mesuré).
- Threads Numba d'une tâche de robustesse : 4 sur 16 cœurs logiques ou plus, 2 sinon (`task_numba_threads`), populations identiques au bit.

### DESIGN, INDEX, RE et logiciel

- DESIGN : D45 corrigé (coût et gradient avec pile arrière), D46 (bornes d'épaisseur des couches opaques) ; polarisation « Avg » retirée ;
  substrat non absorbant (D48) ; quatre comportements par défaut acceptés (R29).
- INDEX : réglages d'absorption du substrat affichés pour le silicium seul (D43) ; stop pendant l'étage IR : le résultat raffiné est gardé.
- RE : deux rayons pour la divergence du faisceau ; pénalité QWOT gardée ; D86 : avertir, ne pas refuser l'extrapolation.
- Un matériau absent de la base refuse le calcul (D88). Données Nb2O5 « Syrus » laissées telles quelles (creux non physique au-delà de 4 µm).
- Poste toujours à jour (CI en `uv sync --upgrade`) ; non-reproductibilité d'INDEX, RE et METAL_BILAYER acceptée ; **fastmath conservé**
  dans tous les noyaux (D52, D67) ; tolérance C1 de 10⁻¹⁰ pour retirer du code mort d'un noyau (D54) ; le hub ne lance pas l'échauffement JIT.
- GPL-3.0 ; gel sur la couche OpenMP (D87), construit dans un environnement jetable depuis `requirements.lock`, toutes licences embarquées.
- Publication : rien à purger dans l'historique ; les œuvres de tiers vont dans les avis de tiers ; `certus_re` sous CC BY 4.0.
- Toute fusion dans `master` se redemande à 👤 ; le dépôt reste dans Google Drive ; sauvegarde des commits locaux en bundle hors dépôt.
- Sobriété de lecture (2026-10-18) : plafonds dans `tests/unit/test_the_ai_entry_points_stay_small.py`, à baisser librement.

## 4. Défauts ouverts

Un défaut corrigé sort de la liste ; son numéro n'est pas réattribué.

| # | défaut |
|---|---|
| D11 | **Une fenêtre de module fermée n'est pas détruite** (lambdas et `partial` branchés sur ses signaux, tenus côté C++). Sans effet en production (un processus par module). 44 sites `connect(lambda)`, plafond de la CI à 44 (`tests/unit/test_ci_lambda_connect_audit.py`) : les convertir puis ramener le plafond à 0. Piste : `WA_DeleteOnClose` après avoir retenu les `QThread` actifs (D23) |
| D23 | À instruire : six `gc.collect()` dans les threads de calcul STRAT peuvent libérer des objets Qt hors du thread GUI ; reproduire avant de toucher au cycle de vie ; avec D11 |
| D25 | Dette de lint masquée par `extend-ignore` : 8 règles, 1 416 violations hors E501 (2026-10-12 ; E402 554 le 2026-10-25, RUF001 à RUF003, RUF100, RUF022 voulue) ; cliquet `tests/oracle/test_lint_debt_ratchet.py`. E402 : action A8a |
| D26 | Aucune arête d'import montante (2026-10-23) ; reste un cycle d'imports à l'exécution (le cœur de STRAT) ; `certus.physics.gradient_analytic` ne s'importe pas seul (cycle avec `gradient_utils`) |
| D50 | Gelé, `loky` ne marche pas (repli sur des fils) et le multigraine est refusé, le message le dit |
| D68 | La physique lit le silicium (`indices.xlsx`) à l'import par pandas et openpyxl (0,53 s) ; le rendre paresseux touche le chargement de la physique (Numba fige les tableaux) |
| D69 | La couverture des noyaux se mesure maintenant avec `property` et les tests `kernels` (74,0 %) ; à l'ancienne définition elle serait de 46,0 % : changement de critère, à connaître de 👤 |
| D71 | **Tauc-Lorentz-Urbach n'est pas continu en E = Eg** (saut de 2·10⁻⁵ du maximum de ε₂) ; le raccorder change le modèle des références certifiées : à trancher avant |
| D72 | Gel de 411 Mo pour un objectif de 300 (llvmlite 115, Qt 77, scipy 68 Mo…) ; mesurer ce que l'application charge vraiment avant d'autres exclusions |
| D82 | Thème sombre : logo foncé peu visible, mesure de contraste à terminer |
| D84 | Écarts au dernier bit intermittents au premier passage après un changement de clé du cache Numba, verts à la relance ; si l'écart persiste, comparer noyaux froids et chauds |
| D107 | À instruire : l'élagage DESIGN vers un nombre cible de couches ne peut pas évaluer ses candidats (`_prune_to_target` lit des attributs absents, `except` → `inf`) ; correctif, test et rapport sur la branche locale `claude/alg02-prune-evaluator-0d2a8d` (`46261901`), non validés ; attend 👤 |
| D108 | Un NaN dans les nœuds d'une spline devient `n = k = 0` sans alerte sur le chemin par défaut (`get_nk_from_spline`, `use_cache=True`) ; attend 👤 (§5) |
| D109 | Le TMM accepte une épaisseur négative (R + T jusqu'à 2,09) ; aucun flux connu n'en produit ; attend 👤 (§5) |
| D110 | La CI ne lance pas les trois contrôles documentaires et saute les benchmarks (`pytest-benchmark`, `pytest-xdist` non déclarés) ; attend 👤 (§5) |
| D111 | Crash du cache Numba (C18) : parade `cache=False`, cause non traitée, cas minimal à rapporter à Numba (👤) ; le test `xfail` strict passera au rouge le jour où Numba est corrigé |
| D112 | `_njit_ir_global_gradient_fused` laisse `dk5` non affecté quand `arg == 0` (Numba le met à 0, juste pour β > 1) ; correction de noyau : `c1_diff` obligatoire |
| D113 | Le noyau de gradient hérité de DESIGN est faux dès que les couches absorbent (convention n + ik) ; latent (DESIGN n'a que des Cauchy réels) ; `conj(n)` le corrige, test contre l'oracle d'abord |
| D114 | Des entrées invalides (NaN, k négatif, indice nul) donnent du fini plausible ; politique à décider par 👤 (§5) |
| D115 | La suite ne fixe pas quatre formules (`xyz_to_lab`, `delta_e_2000`, signe de k) : tests de référence à écrire |
| D116 | Reproductibilité et caches : tableaux de cache modifiables, base de spline RE cachée à 1 nm, RNG global de FIELD, graines brutes voisines corrélées, coût dépendant du nombre de fils au dernier bit, `xyz_from_spectrum` |

## 5. Ce qui attend une décision de 👤

| sujet | ce qui est en jeu |
|---|---|
| **avis de tiers** | DLL du runtime Visual C++ dans `THIRD_PARTY_NOTICES.md` : droit de redistribution réservé par Microsoft aux licenciés de Visual Studio |
| **paquet `certus_re`** | correction de la citation du saphir (Malitson et Dodge, 1972) à commiter par 👤 dans ce dépôt, puis à publier sur Zenodo |
| **interface** | revoir les onze fenêtres ; teintes de marque, bande des fichiers récents, bornes des champs numériques |
| **base de dépôts** | RE depuis un dépôt (découper `load_reverse_engineering_from_path`) ? apparier T et R d'un même échantillon nommées différemment ? INDEX phase 2 : la fenêtre λ de l'utilisateur est remplacée par toute l'étendue des données, voulu ? |
| **ELITE « tour à tour »** | `elite_round_robin` : médiane +0,7 % sur six graines (avant D106) ; inactif ; il manque le bruit d'une même graine rejouée |
| **arrêt de STRAT (D98)** | attente sans fin (défaut) ou arrêt tardif (`oms_arming=1`) : même meilleur SEEL à la dispersion près, mais 101 plans optiques purs déposables avec l'arrêt tardif contre 0 ([rapport](../reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md)) |
| **le Rate et l'optique pure** | le meilleur plan porte du Rate sous tous les modèles d'arrêt ; le Rate de STRAT n'a ni dérive de la source ni bruit de vitesse (§7) ; A4 : réserver des parents optiques purs à ELITE ne donne aucun plan optique pur au modèle d'arrêt par défaut ([rapport](../reports/ANALYSE_claude_2026-10-22/bilan.md) §4). Dépend de la stabilité réelle de la vitesse (A25, §6) |
| **comportements** | D108 (lever `ValueError`), D109 (épaisseur ≥ 0 au TMM), D114 (politique des entrées invalides) : changements de comportement, test rouge d'abord |
| **CI** (D110) | déclarer `pytest-benchmark` et `pytest-xdist` ; ajouter les trois contrôles documentaires à `lint.yml` ; rendre bloquantes les étapes mypy et `bench_kernels` |
| **branches** | faire de `claude/integration-2026-10-25` la branche de travail et y amener `master` ; reprendre ou abandonner `claude/alg02-prune-evaluator-0d2a8d` (D107) et `claude/dreamy-burnell-85397a` (fenêtre admissible 48c) ; `claude/a5-tours-budgets-2026-10-25` est sans objet (A5 fait le 2026-10-24) |
| **A9** | refiger le protocole sur la branche de travail (il refuse un code différent de son commit figé), puis donner ou non le GO ; A14, son préalable, est fait |
| **réglages STRAT** | `elite_rate_moves` (actif, ou `git revert 978b8f04` ; mesures d'A2 dans `ETAT_acquis.md`) ; `rate_rescue_hard` (inactif, sans gain : 35 déposables sur 410) ; `tp_hysteresis_floor` à bas bruit ; armer `strat_local_search_fresh_id` |
| **modèles** | D71 (continuité de Tauc-Lorentz-Urbach en E = Eg) ; D69 (nouvelle définition de la couverture des noyaux) |
| **publication** | toute poussée (`git push`), la fusion de la PR #9, la vitrine ; le design publié de Tikhonravov et al. 1996 (`example/example_design/JSON-design-reference-tikhonravov-1996-published-design.json`), versionné « avec l'autorisation des auteurs » : garder cette autorisation par écrit, ou retirer le fichier (CLAUDE.md §1) |
| **dossier et archives** | 2,5 Go le 2026-10-25, dont `reports/` 1,05 Go pour une limite de 1 Go et un worktree de session de 593 Mo ; seconde copie de l'archive de 8,2 Go |

## 6. Chantiers spécifiés, en attente

- **Saphir** : modéliser son absorption au-delà de 3,9 µm (paramètre inactif par défaut) ; mesurer la polarisation du faisceau du
  spectrophotomètre (elle domine l'incertitude du niveau).
- **Calcul** : dimensionner K, le nombre de graines à lancer ; balayer `tp_hysteresis_factor` à bruit fixé sur la grille machine ; porter
  `r75x2` dans la vitrine avec sa condition ; mesurer `elite_rate_moves` sur d'autres composants, graines et nombres de tours.
- **Modèle physique** : 12.3 méconnaissance d'indice (corridor de dispersion, spécifié) ; 12.5 quantification temporelle du déclenchement
  (ouvert) ; 12.7 résolution du monochromateur (spécifié) ; 12.6 facteur de face arrière (en dernier, ou jamais). 12.2 et 12.4 sont faits
  (lecture lissée sur la grille machine, inactive par défaut : ne pas remonter le seuil).
- **Réserve** : A25, `sigma_rate` comme prédiction, contre les ±1 à 2 % observés en salle ; A26, un bloc de santé de run.
- **Architecture** : le cycle de D26 et les points chauds de taille de `tests/architecture_debt.json` (fonctions longues ou complexes,
  fichiers longs). Lint : A8a (E402, module par module), puis les petites règles RUF.
- **Prédictibilité** : prédire sans tout calculer si un design passe avec un seul verre témoin ; quatre routes déjà fermées.

## 7. Les composants d'essai

| composant | fichier (`example/example_strat/`, sauf mention) | couches | notation | rôle |
|---|---|---|---|---|
| dichroïque | `JSON-strat-example.json` | 48 | 400-700 nm | le juge de paix : passe-court, front vers 545 nm |
| passe-bande 3 cavités | `JSON-strat-bandpass-3cav.json` | 35 | 600-660 nm | une résonance, une bande étroite |
| aléatoire | `JSON-strat-random75.json` | 75 | 550-750 nm | sans structure : teste si une règle est **générale** |
| passe-bande 5 cavités | `JSON-strat-bandpass-5cav-99c.json` | 99 | 610-655 nm | le cas dur |
| aléatoire ×0,5 | `reports/serie_echelle_r75/cfg_x0.5.json` | 75 | 550-750 nm | le côté mince de la série d'échelle |
| aléatoire ×2 | `JSON-strat-random75-x2-fabricable.json` (1 nm) ; `JSON-strat-random75-x2-fabricable-2nm.json` (2 nm, rampes) | 75 | 550-750 nm | l'étalon : épaisseurs doublées |

Une règle n'est acquise que si elle survit sur un empilement **sans structure**.

**Série d'échelle** (`reports/serie_echelle_r75/`) : même empilement (H800-Nb2O5 sur H800-SiO2, λ₀ 633 nm), épaisseurs ×0,5, ×1, ×1,5,
×1,75, ×2 (somme des QWOT 57,4 à 229,8) ; seule expérience contrôlée du projet ; optique et mécanique y sont proportionnelles.

**×0,5 avec un seul verre témoin** : sans secours Rate, aucun déposable aux graines 42, 101 et 202 (niveau d'arrêt hors d'atteinte) ;
avec le secours Rate, toutes les listes sont déposables (meilleur 0,50 nm) ; avec ELITE qui déplace les couches Rate, **0,4347 / 0,3967 /
0,3967 nm** (mesure du 2026-10-12, dossier retiré de `reports/` au ménage du 2026-10-18, restaurable par git). **Le modèle de Rate de STRAT** fige l'estimation de la vitesse
à l'entrée de la queue (erreur relative commune à ses couches) et la source ne dérive pas : ces SEEL sont ceux de ce modèle.
