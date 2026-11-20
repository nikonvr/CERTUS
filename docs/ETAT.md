# CERTUS — état du projet

> État présent et décisions de 👤 (tenu en place ; historique dans `git log` et `reports/`). Règles : [`CLAUDE.md`](../CLAUDE.md). À la demande : [`CHANTIERS_RESTANTS.md`](CHANTIERS_RESTANTS.md), [`ETAT_acquis.md`](ETAT_acquis.md), [`REGLES_reference.md`](REGLES_reference.md).
> Mis à jour le 2026-11-20.

## 0. Reprise — à lire en premier, à tenir à jour

**Liste active** : [chantiers](CHANTIERS_RESTANTS.md) (ouverts seulement). Grille auto et sélection robuste DESIGN : optionnelles ([guide DESIGN](../pages/CERTUS_DESIGN.html#design-robust-search)).

**Branche** : `master`, poussée sur ordre de 👤 (`sparse-checkout` écarte les gros artefacts ; `git sparse-checkout disable` les restaure). **Python de référence : 3.15.2** (`requirements.lock`).

**Répertoire unique (consigne absolue 👤 2026-11-19)** : travailler **exclusivement** dans le dépôt Drive `certus1111` (`D:\drivfl\...\CERTUS\certus1111`) — jamais de clone ni de déplacement ailleurs (ex. `C:\dev`).

**Dernière validation complète** : le 2026-11-20 sous Windows sur `36f636fe` (nuit du 19 au 20 : lots 1a à 3, [reprise](../reports/nuit_2026-11-19/REPRISE.md)), `validate_parallel.py` : oracle 1 253, unit 6 483 (5 artefacts de charge verts seuls en série), ui 1 704, reste 322, performance 41, contrôles documentaires (`coherence_md`, `check_claude_md`, `check_docs`) et ruff verts, `VALIDATION=GO`.

En cas d'écart au bit : rejouer sur [cache Numba vierge](../reports/refactor_corridors_2026-11-11/cache_numba_arbre_neuf.md). **Décisions réservées à 👤** : §5.

## 1. Où en sont les programmes

| programme | état | suite |
|---|---|---|
| **Calcul (STRAT)** | étalon `r75x2`, fente 2 nm. Recherche locale finale avec garde au corridor (`r75x2` : −13,3 / −11,1 / neutre / −9,7 % SEEL, [bilan](../reports/STRAT_garde_2026-10-22/bilan.md)). Sans rampes : aucun plan optique pur déposable ; avec secours Rate : tous déposables au modèle Rate (§7) | [chantiers](CHANTIERS_RESTANTS.md) |
| **Conception (DESIGN)** | mémétique, champion sans couche < 5 nm + relances par défaut (2026-10-23) ; séparatrice 400–1200 nm à 0,000135 ([bilan](../reports/DESIGN_bs5050_2026-10-22/bilan.md)) | [chantiers](CHANTIERS_RESTANTS.md) |
| **RE** | indices tabulés en `n − ik` ; hors table, prolongement constant + avertissement | — |
| **Base de dépôts** | 140 monocouches Photon RT (`example/database_depots/`) chargées par INDEX (`references_index.json`, `scripts\bench_base_depots.py`) : 9/11 références à < 2 % d'épaisseur, 2 écarts documentés. T et R appariés à la lecture (13 paires) ; option `tlu_full_range` (inactive) ; RE : `scripts\re_depuis_depot.py` pour les références absolues (1/11), normalisées refusées | [chantiers](CHANTIERS_RESTANTS.md) |
| **Exécutable gelé** | OpenMP, 422 Mo, construit à `183ebcd9` (2026-11-20) hors Drive dans `%TEMP%\certus_gel_1120`, `release_checks` vert ([bilan](../reports/nuit_2026-11-19/gel/bilan.md) ; `BUILD_COMMIT.json`, `licenses/`). OpenMP gardé (TBB PyPI sous licence Intel hors GPL ; oneTBB Apache-2.0 optionnel) | [chantiers](CHANTIERS_RESTANTS.md) |
| **Qualité** | CI Linux (calcul) + Windows (UI/gel), `mypy` bloquant, contrôles doc dans `lint.yml`, `pip-audit`, `gitleaks`, tests isolés, 0 arête montante | [chantiers](CHANTIERS_RESTANTS.md) |
| **Validation externe** | 🔴 **aucune** : STRAT n'est validé que contre lui-même (dépôts réels du dichroïque annulés, 👤 2026-10-06) | — |

## 2. Repères mesurés — conditions précisées par ligne

Six bancs officiels et 99c remesurés le 2026-11-20, code `7a6fca38`, graine 42 ([bilan](../reports/nuit_2026-11-19/lot3/bilan.md) ; 21/10 entre parenthèses, [bilan](../reports/STRAT_A3_reperes_reprise_2026-10-21/bilan.md)) — SEEL du `RESULT`, plantage de `RANK00` :

| composant | SEEL (nm) | plantage RANK00 | condition |
|---|---:|---:|---|
| dichroïque 48 c., `JSON-strat-example` | **0,182 nm** (0,172) | 0 % | premium ; fente 2 nm (recherche) ; 2 373 strat., 12 blocs |
| passe-bande 3 cav., vrai 35 c. | **0,3466** (0,4907) | 0 % | deep ; fente 2 nm (recherche) ; 1 515 strat., 21 blocs |
| passe-bande 3 cav. deep livré, 36 c. | **0,3628** (0,3238) | 0 % | deep livré ; fente 2 nm (recherche) ; 1 436 strat., 21 blocs |
| aléatoire `JSON-strat-random75`, 75 c. | **0,2142** (0,2225) | 0 % | fast livré ; fente fixe 2 nm ; 2 072 strat., 39 blocs |
| aléatoire ×2 `r75x2`, fente native 1 nm | **0,4878** (0,5833) | 0 % | deep livré ; fente fixe 1 nm ; 4 020 strat., 43 blocs |
| `r75x2` rampes livrées, fente 2 nm | **0,5157** (0,5092) | 0 % | deep livré ; fente fixe 2 nm ; 3 998 strat., 52 blocs |
| passe-bande 5 cav., 99 c., 4 témoins | **0,544** gr. 42 (0,597 ; 0,575–0,670, gr. 42/101/202) | 0 % | fast ; fente 2 nm ; partition 0-22-42-76-99 ; `index_corridor_fixed_domain` armé ([rapport](../reports/STRAT_A3_99c_grille_2026-10-24/bilan.md)) |

**Lire ces chiffres :**
- 🔴 Les écarts au 21/10 mêlent tout ce qui a changé depuis (recherche locale, consensus, arrêt tardif `oms_arming=1`, correctifs du 19/11, lots du 20/11) : aucune cause isolée ; 35c (−29 %) et 36c (+12 %) à instruire (chantier 6). Dernier juge de paix (2026-11-16) : **0,1704 nm**.
- 🔴 SEEL non comparables d'un composant à l'autre (§7) ; à 150 tirages σ ≈ 6 % (consensus `r75x2` σ ≈ 1,8 %) : < ~8 % indiscernables.
- Comprennent le **biais de fente** ; garder `RESULT` et `RANK00` séparés (R130) ; structure > longueur pour la difficulté ; `100 %` en `fast` ne conclut rien.
- Banc : `CERTUS_BENCH_TIMEOUT_S = max(5400, 4 × durée)` (`WAIT_TIMEOUT=` -> `RESULT=None`).

## 3. Ce que 👤 a décidé — ne pas rouvrir sans mesure qui le contredise

### Réglages

| réglage | valeur |
|---|---|
| cadence machine | 4 Hz, 1 lecture témoin/tour, 1 pt / 0,125 nm à 0,5 nm/s |
| bruit de lecture | ±0,05 point (`A = 5e-4` en T) |
| `reading_smoothing_window` | 1 (inactif) en exploitation ; 8 lectures dans le modèle figé |
| `tp_hysteresis_factor` | 1,66 dans `JSON-strat-example` (0,0 hors JSON) ; `tp_hysteresis_floor` 0,000415 (maintenu 2026-10-23, [analyse](../reports/ANALYSE_claude_2026-10-22/bilan.md)) |
| `phase_a_level_margin_factor` | 1,66 dans `JSON-strat-example` (0,0 hors JSON) |
| `index_corridor` | 0,005 en indice absolu, actif |
| DESIGN global (2026-10-23) | mémétique, 1000 enfants, pop. 30 (`_memetic_children = 0` : PGLOBAL) ; champion sans couche < 5 nm ([bilan](../reports/DESIGN_bs5050_2026-10-22/bilan.md)) |
| `photometric_curvature_amp` ; `affine_scale_amp`, `affine_offset_amp` | 0,00375 ; 0,0 par défaut (sondes : 0,05 et 0,02) |
| arrêt et étalonnage STRAT | arrêt tardif (`oms_arming` = 1, 👤 2026-11-19), étalonnage parfait (2026-11-17) ([bilan](../reports/chantier44_etape3_2026-11-17/bilan.md)) |
| `allow_rate`, `rate_by_swing`, `rate_rescue` (`rate_rescue_few` 10) | vrais (2026-10-12) |
| `elite_rate_moves`, `elite_rate_max_candidates` | vrai, 120 (2026-10-13) |
| `strat_local_search` | actif : recherche/contrôle ±0,010, garde au corridor configuré (`strat_local_search_guard`, 2026-10-23) |
| `slit_bias_enabled` | vrai, nominal 2 nm (opérateur : 5 / 1 / 0,5 nm, bruit ÷1,5 / ×2 / ×5) |
| profondeurs par mode (fast / premium / deep) | `robustness_num_runs` 50 / 150 / 300, `n_screen_runs` 10 / 25 / 50, `dp_top_k` 20 / 40 / 100 ; `[MODE]` prime |
| graine réf. ; pas λ contrôle ; `machine_sampling_dd` | 42 ; 1 nm (`scan_wl_step`) ; 0 figé (~21 pts/couche, optimiste faux PT) |
| cible spectrale ; mode par défaut | non pondérée ; `premium` |

**Chaîne de lecture (OMS 5100), figée 2026-08-08** : 1 lecture/tour, bruit additif borné ±0,05 pt (`σ = A/3`) i.i.d., lissage 8 lectures dans le modèle seul, seuil PT `1,00 A` à `k = 8` (1/√k réfutée), délai nul, marge `5 σ` (`1,66 A`). Hors modèle (à laisser) : σ(T, λ), grenaille, bruit multiplicatif/corrélé.

### Règles gravées

- Une λ de contrôle est interdite si, sous bruit, elle risque faux PT ou non-arrêt ; marge comptée **en transmission** sur grille `_resolve_monitoring_wavelength_grid`. Heuristiques (15-85 %, amplitude, swing) = explicatives, jamais couperets.
- **Rate interdit couches 0 et 1** (`RATE_MIN_LAYER = 2`) ; vitesse calculée sur couches du même matériau contrôlées optiquement ; Rate lègue son erreur en boucle ouverte.
- **SEEL = 2 × √score** (nm) ; classement : classe à 0,01 nm du meilleur SEEL, puis rendement, puis marge critique (R130). `fast` crible, `extreme` sans justification ; Monte-Carlo note, ne choisit pas.
- Multi-témoins = faisabilité (« New test glass at layers: », `witness_reset_layers`, vide par défaut). Saphir unique : Sellmeier id 3 partout (2026-10-12).

### Exceptions accordées (CLAUDE.md §11)

| date | règle | portée | raison |
|---|---|---|---|
| 2026-11-19 | C1 (paramètre inactif par défaut) | SPLINE : `spline_mono_analytic_gradient` et `spline_polish_fd_prefix_maxfun` = 3000 allumés | RMSE meilleur sur les deux exemples ([bilan](../reports/chantier21_2026-11-19/bilan.md)) |
| 2026-11-19 | C1 (paramètre inactif par défaut) | SUBSTRATE : `sellmeier_ir_pole` allumé | écart au niveau du bruit sur substrats du catalogue ([bilan](../reports/chantier05_2026-11-18/bilan.md)) |
| 2026-11-19 | C1 (paramètre inactif par défaut) | STRAT : `strat_local_search_fresh_id` allumé (l'identifiant exporté du plan affiné change, le parent dans `parent_strategy_id`) | identifiants uniques contrôlés sur toute la liste (8 bancs sur 8 portaient l'identifiant du parent, [analyse](../reports/ANALYSE_claude_2026-10-22/bilan.md)) |
| 2026-11-19 | décision D98 | STRAT : arrêt tardif (`oms_arming` = 1) au lieu de l'attente sans fin | même meilleur SEEL, 101 plans optiques purs déposables contre 0 ([rapport](../reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md)) |

### STRAT

- `RESULT` = score du 1er : P95 RMSE pire des 3 bruits (tirages plantés compris) ; consensus = moyenne + `consensus_std_weight × σ` (1 graine ∞ rejette la stratégie, 👤 2026-11-15). Historique POEM : 4 couches, 16 points.
- **Arrêt** : ancre + inversion exactes POEM ; **OMS s'arrête tard** au dernier extremum (`oms_arming` = 1, 👤 2026-11-19, lecture brute ; [rapport](../reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md)).
- **Rate** : posé au temps (`_rate_layer_thickness`), secours Rate, ELITE conserve/déplace Rate, optique possible après Rate ; `rate_rescue_hard` inactif. `rank_refined_first` gardé (2026-11-17, [mesure](../reports/suite_2026-11-17/classement_recherche_locale.md)).
- Threads Numba robustesse : 4 si ≥ 16 cœurs logiques, sinon 2 (`task_numba_threads`), bit-identique.

### DESIGN, INDEX, RE et logiciel

- DESIGN : bornes propres aux couches opaques ; pas de pol « Avg » ; 4 comportements par défaut acceptés (R29).
- INDEX : absorption substrat affichée silicium seul ; stop IR garde le raffiné ; Phase 2 lit toute l'étendue des données ([chantiers](CHANTIERS_RESTANTS.md)).
- RE : 2 rayons divergence ; pénalité QWOT gardée ; avertir sans refuser extrapolation. Matériau absent refuse calcul ; Nb2O5 « Syrus » brut > 4 µm.
- `uv sync --upgrade` ; **fastmath gardé** ; tolérance C1 `10⁻¹⁰` pour code mort ; hub sans warmup JIT.
- GPL-3.0 ; gel via environnement jetable `requirements.lock` + licences. `certus_re` sous CC BY 4.0.
- Threads Numba : OpenMP, sauf STRAT et RE sous TBB optionnel (`certus_core.TBB_THREADING_LAYER`, 👤 2026-11-15 : juge de paix 1 074 s vs 1 339 s mêmes bits ; RE 17,5 s vs 28,2 s ; [STRAT](../reports/audit_oms5100_2026-11-15/profil_strat_complet/bilan.md), [INDEX/RE](../reports/audit_oms5100_2026-11-15/tbb_index_re/bilan.md)).
- Fusion `master` soumise à 👤. Caps entrypoints dans `tests/unit/test_the_ai_entry_points_stay_small.py` (à abaisser librement).
- Benchmarks litt. (2026-10-30) : Trubetskov 2020 (octave) / miroir chaud / antireflets hors champ ; OIC 2016 doit battre `0,0139`.
- Décisions 2026-11-19 (👤) : politique stricte `ValueError` (D108/D109/D114 : `NaN`/`Inf`, `d < 0`, `k < 0`, `n_sub <= 0`) ; retrait du plancher `ε1 ≥ 1` dans INDEX ; `strat_local_search_fresh_id` par défaut (exception C1 à consigner au commit Lot 2b) ; chantiers **31**, **32** et **26** archivés ; optionnels P3 écartés (dérive Rate, guides HTML offline, bande fichiers récents étendue) ; consigne absolue de rester exclusivement dans le dépôt Drive `certus1111` (jamais cloner/déplacer ailleurs).

## 4. Limites et travaux ouverts

Chantiers ouverts : [`CHANTIERS_RESTANTS.md`](CHANTIERS_RESTANTS.md). Limites : guides [DESIGN](../pages/CERTUS_DESIGN.html#design-limits) et [STRAT](../pages/CERTUS_STRAT.html). Cache Numba : [mode opératoire](../reports/refactor_corridors_2026-11-11/cache_numba_arbre_neuf.md).

## 5. Ce qui attend une décision ou action de 👤

| sujet | enjeu |
|---|---|
| **avis de tiers** | DLL Visual C++ (`THIRD_PARTY_NOTICES.md`) : droit de redistribution Microsoft avant release binaire publique |
| **paquet `certus_re`** | mise à jour Zenodo avec citation saphir (Malitson & Dodge 1972) |
| **publication** | vitrine, autorisation écrite Tikhonravov 1996 (`example/example_design/JSON-design-reference-tikhonravov-1996-published-design.json`) |
| **hors-IA** | 5 PR Dependabot CI #10–#14 (41) sur GitHub ; essais humains U13 (33) bloqués sur date/testeurs |
| **RE et dépôts normalisés** | dénormaliser T/T_sub (10 références sur 11) pour RE : quel modèle de substrat ([chantiers](CHANTIERS_RESTANTS.md)) |
| **SPLINE passe 2** | dérivées de la passe 2 d'Auto-Best (seuil franchi, gain faible) : jac hybride, budgets réduits ou statu quo (lot 4) |

## 6. Ordre de travail

[`CHANTIERS_RESTANTS.md`](CHANTIERS_RESTANTS.md) (priorité, complexité, dépendances, P1).

## 7. Les composants d'essai

| composant | fichier (`example/example_strat/`, sauf mention) | couches | plage | rôle |
|---|---|---|---|---|
| dichroïque | `JSON-strat-example.json` | 48 | 400–700 nm | juge de paix (front ~545 nm) |
| 3 cavités | `JSON-strat-bandpass-3cav.json` | 35 | 600–660 nm | résonance bande étroite |
| aléatoire | `JSON-strat-random75.json` | 75 | 550–750 nm | teste généralité hors structure |
| 5 cavités | `JSON-strat-bandpass-5cav-99c.json` | 99 | 610–655 nm | cas dur |
| aléatoire ×0,5 | `reports/serie_echelle_r75/cfg_x0.5.json` | 75 | 550–750 nm | série d'échelle mince |
| aléatoire ×2 | `JSON-strat-random75-x2-fabricable.json` (1 nm) ; `JSON-strat-random75-x2-fabricable-2nm.json` (2 nm, rampes) | 75 | 550–750 nm | étalon épaisseur doublée |

Une règle n'est acquise que si elle survit sur empilement **sans structure**. Série d'échelle (`reports/serie_echelle_r75/`) : H800-Nb2O5/SiO2, λ₀ 633 nm, ×0,5..×2 (QWOT 57,4–229,8). ×0,5 à 1 témoin : secours Rate requis ; ELITE Rate : **0,4347 / 0,3967 / 0,3967 nm** (2026-10-12). Modèle Rate STRAT = vitesse estimée à l'entrée de la queue, erreur commune sans dérive.
