# CERTUS — état du projet

> Ce document porte l'**état** : où en sont les programmes, les repères mesurés, ce que 👤 a
> décidé, les défauts ouverts et les chantiers. Les **règles** sont dans
> [`CLAUDE.md`](../CLAUDE.md). Il se tient **en place** : un fait change, on corrige sa ligne,
> on ne raconte pas la correction (`git log` s'en charge). Toute mesure porte sa date.
> Le détail et l'historique sont dans `git`, sans autorité (CLAUDE.md, en-tête).
> Mis à jour le 2026-11-17.

## 0. Reprise — à lire en premier, à tenir à jour

> L'état présent seulement ; l'historique est dans `git log` et `reports/`. À la demande : actions ouvertes et protocole de mesure
> ([`CHANTIERS_RESTANTS.md`](CHANTIERS_RESTANTS.md)), vocabulaire du Rate ([`ETAT_acquis.md`](ETAT_acquis.md)), preuves dans `reports/`.

**Liste active** : [chantiers](CHANTIERS_RESTANTS.md), les ouverts seulement. Reprise de la session en cours :
[REPRISE](../reports/suite_2026-11-17/REPRISE.md). La grille automatique et la sélection robuste de DESIGN sont
optionnelles ; le [guide DESIGN](../pages/CERTUS_DESIGN.html#design-robust-search) décrit leur activation et leurs limites.

**Clone de travail** : `C:\dev\certus1111`, hors de Google Drive ; l'ancien clone sous
`D:\drivfl` (dossier synchronisé, qui réécrivait des fichiers suivis) reste intact, on n'y travaille plus.

**Branche de travail** : `master`, poussée sur ordre de 👤 (dernière poussée : nuit du 17 au 18 novembre).
Le sparse-checkout écarte les gros artefacts scientifiques suivis ; git sparse-checkout disable les restaure. Les sauvegardes et données locales de novembre sont répertoriées
dans `artifacts/archives-20261114/inventaire.json` de l'ancien clone (hors Git).

**Python de référence : 3.15.2**, dépendances de requirements.lock.

**Dernière validation complète** : le 2026-11-17 dans la nuit sous Windows sur `88e854dd` : oracle 1 214, ui 1 670, reste 322, performance 30, contrôles documentaires et ruff verts ([résumé](../reports/suite_2026-11-17/validation_nuit/summary.txt)) ; unit, relancé après un `git ls-files` en échec passager à la collecte : 6 367 et deux artefacts de charge, verts seuls en série : `VALIDATION=GO` ([résumé](../reports/suite_2026-11-17/validation_nuit_unit/summary.txt)).

Pour un échec de comparaison au bit, rejouer sur [cache Numba vierge](../reports/refactor_corridors_2026-11-11/cache_numba_arbre_neuf.md).


**Décisions qui n'appartiennent qu'à 👤** : §5. Une IA ne les tranche pas, elle rapporte les mesures.

## 1. Où en sont les programmes

| programme | état | prochaine action |
|---|---|---|
| **Calcul (STRAT)** | étalon : `r75x2` à la fente de 2 nm. Recherche locale finale active avec sa garde au corridor configuré ; sur `r75x2`, −13,3 / −11,1 / neutre / −9,7 % de SEEL selon la graine de banc ([bilan](../reports/STRAT_garde_2026-10-22/bilan.md)). Sans rampes, aucun plan optique pur n'est déposable ; avec le secours Rate, tous les plans de la liste le sont, au modèle de Rate de STRAT (§7) | reprise de calcul et co-conception ([chantiers](CHANTIERS_RESTANTS.md)) |
| **Conception (DESIGN)** | étape globale mémétique, champion sans couche < 5 nm et relances par défaut depuis le 2026-10-23 ; séparatrice 400–1200 nm à 0,000135 depuis l'exemple ([bilan](../reports/DESIGN_bs5050_2026-10-22/bilan.md)) | robustesse et reprise ([chantiers](CHANTIERS_RESTANTS.md)) |
| **RE** | indices tabulés lus en n − ik ; un indice demandé hors de sa table est prolongé par une constante, avec un avertissement | — |
| **Base de dépôts** | 140 monocouches mesurées au Photon RT (`example/database_depots/`), chargées par INDEX (« Deposit database… ») ; la voie (T ou R) se lit dans la géométrie du détecteur. Onze ajustements certifiés servent de références (`references_index.json`, `scripts\bench_base_depots.py`) : neuf à moins de 2 % d'épaisseur, deux écarts documentés dans les références du banc. RE ne la lit pas (il lui faut un classeur complet) | IDX-01 ; §5 |
| **Exécutable gelé** | couche OpenMP, 420 Mo, sans les outils de développement ; construit à `260e4e8c` le 2026-11-17, hub et dix modules démarrent ; il porte son commit (`BUILD_COMMIT.json`). Licences embarquées dans `licenses/`. L'exécutable reste sur OpenMP : la roue PyPI de TBB est sous licence Intel, hors GPL (oneTBB sous Apache-2.0 à trouver, décision de 👤) | §5 |
| **Qualité** | CI : calcul sous Linux, interface et gel sous Windows, `pip-audit`, `gitleaks` ; tests isolés des préférences de 👤 ; aucune arête d'import montante | §5 |
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

- 🔴 **Ces repères sont antérieurs au code actuel de STRAT** (substrat « SiO2 », consensus) et ne se comparent pas à une
  mesure d'aujourd'hui : à remesurer avant toute comparaison. Dernier juge de paix mesuré (2026-11-16) : **0,1704 nm**.
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
| modèle d'arrêt et étalonnage de STRAT (2026-11-17, délégué par 👤) | inchangés : attente sans fin, étalonnage parfait ; arrêt au niveau ou tardif et échelle de 1 % ne changent pas l'ordre des plans déposables du juge de paix ([bilan](../reports/chantier44_etape3_2026-11-17/bilan.md)) |
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
- **SEEL = 2 × √score**, en nm ; classement final : classe à 0,01 nm du meilleur SEEL, puis rendement, puis marge critique (R130).
- `fast` crible, il ne publie pas ; `extreme` n'a aucune justification mesurée. La profondeur Monte-Carlo sert à noter, jamais à choisir.
- Le multi-témoins est un outil de faisabilité (champ « New test glass at layers: », `witness_reset_layers`, vide par défaut).
- Un seul indice de saphir : le Sellmeier d'id 3, partout (2026-10-12).

### Exceptions accordées (CLAUDE.md §11)

| date | règle | portée | raison |
|---|---|---|---|
| 2026-11-15 | interdit 3 (`reports/`) | retrait des `.md` réimportés par `20bd199d` (revert `e0c1fe70`) | déjà jugés obsolètes par `b6fb1939` ; copie hors dépôt dans `CERTUS/certus1111_hors_git_2026-11-15/` |

### STRAT

- `RESULT` est le score du premier classé : P95 du RMSE au pire des trois niveaux de bruit, **tirages plantés compris** ; le consensus
  le remplace par moyenne + `consensus_std_weight` écarts-types sur ses graines. Une graine rejetée (score
  infini) rejette la stratégie : consensus infini (décision de 👤 du 2026-11-15).
- Quatre couches d'historique POEM, 16 points d'historique ; sous un nombre minimal de blocs la DP ne rend que les graines
  structurées, et le journal le dit.
- **Arrêt** : ancre et inversion exactes de l'arrêt POEM ; **l'OMS attend sans fin** (`oms_arming` = 2) ; lecture d'arrêt
  brute ([rapport](../reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md)).
- **Rate dans tous les scénarios** : couche posée au temps, à la vitesse estimée (`_rate_layer_thickness`) ; secours Rate, enfants
  d'ELITE qui gardent et déplacent les couches Rate, optique possible après du Rate ; `rate_rescue_hard` inactif (sans gain mesuré).
- `rank_refined_first` gardé (2026-11-17, « mesurer d'abord ») : au juge de paix, classer au score final donne le même
  gagnant ([mesure](../reports/suite_2026-11-17/classement_recherche_locale.md)).
- Threads Numba d'une tâche de robustesse : 4 sur 16 cœurs logiques ou plus, 2 sinon (`task_numba_threads`), populations identiques au bit.

### DESIGN, INDEX, RE et logiciel

- DESIGN : bornes d'épaisseur propres aux couches opaques ; pas de polarisation « Avg » ; quatre comportements par défaut acceptés (R29).
- INDEX : réglages d'absorption du substrat affichés pour le silicium seul ; stop pendant l'étage IR : le résultat raffiné est gardé.
- RE : deux rayons pour la divergence du faisceau ; pénalité QWOT gardée ; avertir, ne pas refuser l'extrapolation.
- Un matériau absent de la base refuse le calcul. Données Nb2O5 « Syrus » laissées telles quelles (creux non physique au-delà de 4 µm).
- Poste toujours à jour (CI en `uv sync --upgrade`) ; non-reproductibilité d'INDEX, RE et METAL_BILAYER acceptée ; **fastmath conservé**
  dans tous les noyaux ; tolérance C1 de 10⁻¹⁰ pour retirer du code mort d'un noyau ; le hub ne lance pas l'échauffement JIT.
- GPL-3.0 ; gel construit dans un environnement jetable depuis `requirements.lock`, toutes licences embarquées.
- Couche de fils Numba : OpenMP, sauf STRAT et RE sur TBB quand `tbb` est installé (optionnel, hors dépendances :
  licence Intel ; `certus_core.TBB_THREADING_LAYER`, 👤 2026-11-15) :
  recherche STRAT du juge de paix en 1 074 s contre 1 339 s, mêmes bits ; exemple RE en 17,5 s contre 28,2 s ; sous TBB,
  le coût et le gradient de DESIGN changent de bits d'un lancement à l'autre, INDEX ne gagne rien
  ([STRAT](../reports/audit_oms5100_2026-11-15/profil_strat_complet/bilan.md), [INDEX et RE](../reports/audit_oms5100_2026-11-15/tbb_index_re/bilan.md)).
- Publication : rien à purger dans l'historique ; les œuvres de tiers vont dans les avis de tiers ; `certus_re` sous CC BY 4.0.
- Toute fusion dans `master` se redemande à 👤. Le dépôt est hors de Google Drive ; GitHub sert de sauvegarde.
- Sobriété de lecture (2026-10-18) : plafonds dans `tests/unit/test_the_ai_entry_points_stay_small.py`, à baisser librement.
- Comparaisons à Tikhonravov et Trubetskov (2026-10-30) : le miroir dispersif d'une octave de Trubetskov 2020 ne sera pas
  traité ; le miroir chaud et les antireflets sortent du champ de l'article ; la cissoïde OIC 2016 doit battre le
  vainqueur du concours (0,0139), pas seulement 0,0238.

## 4. Limites et travaux ouverts

Les chantiers ouverts sont suivis uniquement dans
[`CHANTIERS_RESTANTS.md`](CHANTIERS_RESTANTS.md). Les limites de fonctionnement sont décrites dans les guides
[DESIGN](../pages/CERTUS_DESIGN.html#design-limits) et [STRAT](../pages/CERTUS_STRAT.html).
Les précautions du cache Numba restent dans le [mode opératoire](../reports/refactor_corridors_2026-11-11/cache_numba_arbre_neuf.md).

## 5. Ce qui attend une décision de 👤

| sujet | ce qui est en jeu |
|---|---|
| **plancher ε1 d'INDEX** | le plancher ε1 ≥ 1 n'agit sur aucun des quatre exemples (ε1 physique ≥ 2,24, [mesure](../reports/audit_code_2026-11-15/preuves/p_plancher_epsilon1.txt)) : le garder ? |
| **avis de tiers** | DLL du runtime Visual C++ dans `THIRD_PARTY_NOTICES.md` : droit de redistribution réservé par Microsoft aux licenciés de Visual Studio |
| **paquet `certus_re`** | correction de la citation du saphir (Malitson et Dodge, 1972) à commiter par 👤 dans ce dépôt, puis à publier sur Zenodo |
| **interface** | revoir les onze fenêtres ; teintes de marque, bande des fichiers récents, bornes des champs numériques |
| **base de dépôts** | RE depuis un dépôt (découper `load_reverse_engineering_from_path`) ? apparier T et R d'un même échantillon nommées différemment ? INDEX phase 2 : la fenêtre λ de l'utilisateur est remplacée par toute l'étendue des données, voulu ? |
| **ELITE « tour à tour »** | `elite_round_robin` : médiane +0,7 % sur six graines, mesurée sur un code antérieur ; inactif ; il manque le bruit d'une même graine rejouée |
| **arrêt de STRAT (D98)** | attente sans fin (défaut) ou arrêt tardif (`oms_arming=1`) : même meilleur SEEL à la dispersion près, mais 101 plans optiques purs déposables avec l'arrêt tardif contre 0 ([rapport](../reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md)) |
| **le Rate et l'optique pure** | le meilleur plan porte du Rate sous tous les modèles d'arrêt ; le Rate de STRAT n'a ni dérive de la source ni bruit de vitesse (§7) ; A4 : réserver des parents optiques purs à ELITE ne donne aucun plan optique pur au modèle d'arrêt par défaut ([rapport](../reports/ANALYSE_claude_2026-10-22/bilan.md) §4). Dépend de la stabilité réelle de la vitesse (A25, §6) |
| **comportements** | D108 (lever `ValueError`), D109 (épaisseur ≥ 0 au TMM), D114 (politique des entrées invalides) : changements de comportement, test rouge d'abord |
| **CI** (D110) | déclarer `pytest-benchmark` et `pytest-xdist` ; ajouter les trois contrôles documentaires à `lint.yml` ; rendre bloquantes les étapes mypy et `bench_kernels` |
| **A9** | refiger le protocole sur la branche de travail (il refuse un code différent de son commit figé), puis donner ou non le GO |
| **réglages STRAT** | `elite_rate_moves` (actif, ou `git revert 978b8f04` ; [mesures d'A2](../reports/STRAT_A2_continuation_2026-10-14/final_bilan_A2_20261014.md)) ; `rate_rescue_hard` (inactif, sans gain : 35 déposables sur 410) ; `tp_hysteresis_floor` à bas bruit ; armer `strat_local_search_fresh_id` |
| **modèles** | D71 (continuité de Tauc-Lorentz-Urbach en E = Eg) ; D69 (nouvelle définition de la couverture des noyaux) |
| **publication** | toute poussée (`git push`), la vitrine ; le design publié de Tikhonravov et al. 1996 (`example/example_design/JSON-design-reference-tikhonravov-1996-published-design.json`), versionné « avec l'autorisation des auteurs » : garder cette autorisation par écrit, ou retirer le fichier (CLAUDE.md §1) |

## 6. Ordre de travail

La [liste unique des chantiers](CHANTIERS_RESTANTS.md) donne complexité, priorité, dépendances et critère de fin.
Elle nomme ses P1.

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
0,3967 nm** (mesure du 2026-10-12). **Le modèle de Rate de STRAT** fige l'estimation de la vitesse
à l'entrée de la queue (erreur relative commune à ses couches) et la source ne dérive pas : ces SEEL sont ceux de ce modèle.
