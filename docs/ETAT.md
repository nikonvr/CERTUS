# CERTUS — état du projet

> État présent et décisions de 👤 (tenu en place ; historique dans `git log` et `reports/`). Règles : [`CLAUDE.md`](../CLAUDE.md). À la demande : [`CHANTIERS_RESTANTS.md`](CHANTIERS_RESTANTS.md), [`ETAT_acquis.md`](ETAT_acquis.md), [`REGLES_reference.md`](REGLES_reference.md).
> Mis à jour le 2026-11-19.

## 0. Reprise — à lire en premier, à tenir à jour

**Liste active** : [chantiers](CHANTIERS_RESTANTS.md) (ouverts seulement). Grille auto et sélection robuste DESIGN : optionnelles ([guide DESIGN](../pages/CERTUS_DESIGN.html#design-robust-search)).

**Branche** : `master`, poussée sur ordre de 👤 (`sparse-checkout` écarte les gros artefacts ; `git sparse-checkout disable` les restaure). **Python de référence : 3.15.2** (`requirements.lock`).

**Dernière validation complète** : le 2026-11-19 sous Windows sur `7b318542` (défauts SPLINE, SUBSTRATE et arrêt tardif allumés), `validate_parallel.py` : oracle 1 238, unit 6 375 (l'intermittent POEM vert seul en série), ui 1 676, reste 322, performance 30, contrôles documentaires et ruff verts, `VALIDATION=GO` ([résumé](../reports/chantier21_2026-11-19/validation_7b318542.txt)).

En cas d'écart au bit : rejouer sur [cache Numba vierge](../reports/refactor_corridors_2026-11-11/cache_numba_arbre_neuf.md). **Décisions réservées à 👤** : §5.

## 1. Où en sont les programmes

| programme | état | suite |
|---|---|---|
| **Calcul (STRAT)** | étalon `r75x2`, fente 2 nm. Recherche locale finale avec garde au corridor (`r75x2` : −13,3 / −11,1 / neutre / −9,7 % SEEL, [bilan](../reports/STRAT_garde_2026-10-22/bilan.md)). Sans rampes : aucun plan optique pur déposable ; avec secours Rate : tous déposables au modèle Rate (§7) | [chantiers](CHANTIERS_RESTANTS.md) |
| **Conception (DESIGN)** | mémétique, champion sans couche < 5 nm + relances par défaut (2026-10-23) ; séparatrice 400–1200 nm à 0,000135 ([bilan](../reports/DESIGN_bs5050_2026-10-22/bilan.md)) | [chantiers](CHANTIERS_RESTANTS.md) |
| **RE** | indices tabulés en `n − ik` ; hors table, prolongement constant + avertissement | — |
| **Base de dépôts** | 140 monocouches Photon RT (`example/database_depots/`) chargées par INDEX (`references_index.json`, `scripts\bench_base_depots.py`) : 9/11 références à < 2 % d'épaisseur, 2 écarts documentés. RE exige un classeur complet | §5 |
| **Exécutable gelé** | OpenMP, 420 Mo, construit à `260e4e8c` (2026-11-17), hub + 10 modules démarrent, `BUILD_COMMIT.json`, `licenses/`. OpenMP gardé (TBB PyPI sous licence Intel hors GPL ; oneTBB Apache-2.0 à voir) | §5 |
| **Qualité** | CI Linux (calcul) + Windows (UI/gel), `pip-audit`, `gitleaks`, tests isolés, 0 arête montante | §5 |
| **Validation externe** | 🔴 **aucune** : STRAT n'est validé que contre lui-même (dépôts réels du dichroïque annulés, 👤 2026-10-06) | — |

## 2. Repères mesurés — conditions précisées par ligne

Six bancs officiels du 2026-10-21, code `85a9e82f`, graine 42 ([bilan](../reports/STRAT_A3_reperes_reprise_2026-10-21/bilan.md)) — SEEL du `RESULT`, plantage de `RANK00` :

| composant | SEEL (nm) | plantage RANK00 | condition |
|---|---:|---:|---|
| dichroïque 48 c., `JSON-strat-example` | **0,172 nm** | 0 % | premium ; fente 2 nm (recherche) ; 2 652 strat., 2 blocs |
| passe-bande 3 cav., vrai 35 c. | **0,4907** | 0 % | deep ; fente 2 nm (recherche) ; 1 245 strat., 5 blocs |
| passe-bande 3 cav. deep livré, 36 c. | **0,3238** | 0 % | deep livré ; fente 2 nm (recherche) ; 1 440 strat., 29 blocs |
| aléatoire `JSON-strat-random75`, 75 c. | **0,2225** | 0 % | fast livré ; fente fixe 2 nm ; 2 634 strat., 51 blocs |
| aléatoire ×2 `r75x2`, fente native 1 nm | **0,5833** | 0 % | deep livré ; fente fixe 1 nm ; 3 946 strat., 15 blocs |
| `r75x2` rampes livrées, fente 2 nm | **0,5092** | 0 % | deep livré ; fente fixe 2 nm ; 4 691 strat., 56 blocs |
| passe-bande 5 cav., 99 c., 4 témoins | **0,597** (0,575–0,670, gr. 42/101/202) | 0 % | fast ; fente 2 nm ; partition 0-22-42-76-99 ; `index_corridor_fixed_domain` armé ([rapport](../reports/STRAT_A3_99c_grille_2026-10-24/bilan.md)) |

**Lire ces chiffres :**
- 🔴 Antérieurs au code STRAT actuel (substrat « SiO2 », consensus) : à remesurer avant comparaison. Dernier juge de paix (2026-11-16) : **0,1704 nm**.
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
| `tp_hysteresis_factor` | 1,66 ; `tp_hysteresis_floor` 0,000415 (maintenu 2026-10-23, [analyse](../reports/ANALYSE_claude_2026-10-22/bilan.md)) |
| `phase_a_level_margin_factor` | 1,66 (3,33 à évaluer) |
| `index_corridor` | 0,005 en indice absolu, actif |
| DESIGN global (2026-10-23) | mémétique, 1000 enfants, pop. 30 (`_memetic_children = 0` : PGLOBAL) ; champion sans couche < 5 nm ([bilan](../reports/DESIGN_bs5050_2026-10-22/bilan.md)) |
| `photometric_curvature_amp` ; `affine_scale_amp`, `affine_offset_amp` | 0,00375 ; 0,05 et 0,02 |
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
| 2026-11-15 | interdit 3 (`reports/`) | retrait des `.md` réimportés par `20bd199d` (revert `e0c1fe70`) | obsolètes (`b6fb1939`) ; copie hors dépôt `CERTUS/certus1111_hors_git_2026-11-15/` |
| 2026-11-19 | C1 (paramètre inactif par défaut) | SPLINE : `spline_mono_analytic_gradient` et `spline_polish_fd_prefix_maxfun` = 3000 allumés | RMSE meilleur sur les deux exemples ([bilan](../reports/chantier21_2026-11-19/bilan.md)) |
| 2026-11-19 | C1 (paramètre inactif par défaut) | SUBSTRATE : `sellmeier_ir_pole` allumé | écart au niveau du bruit sur substrats du catalogue ([bilan](../reports/chantier05_2026-11-18/bilan.md)) |
| 2026-11-19 | décision D98 | STRAT : arrêt tardif (`oms_arming` = 1) au lieu de l'attente sans fin | même meilleur SEEL, 101 plans optiques purs déposables contre 0 ([rapport](../reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md)) |

### STRAT

- `RESULT` = score du 1er : P95 RMSE pire des 3 bruits (tirages plantés compris) ; consensus = moyenne + `consensus_std_weight × σ` (1 graine ∞ rejette la stratégie, 👤 2026-11-15). Historique POEM : 4 couches, 16 points.
- **Arrêt** : ancre + inversion exactes POEM ; **OMS s'arrête tard** au dernier extremum (`oms_arming` = 1, 👤 2026-11-19, lecture brute ; [rapport](../reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md)).
- **Rate** : posé au temps (`_rate_layer_thickness`), secours Rate, ELITE conserve/déplace Rate, optique possible après Rate ; `rate_rescue_hard` inactif. `rank_refined_first` gardé (2026-11-17, [mesure](../reports/suite_2026-11-17/classement_recherche_locale.md)).
- Threads Numba robustesse : 4 si ≥ 16 cœurs logiques, sinon 2 (`task_numba_threads`), bit-identique.

### DESIGN, INDEX, RE et logiciel

- DESIGN : bornes propres aux couches opaques ; pas de pol « Avg » ; 4 comportements par défaut acceptés (R29).
- INDEX : absorption substrat affichée silicium seul ; stop IR garde le raffiné ; Phase 2 lit toute l'étendue des données (§5).
- RE : 2 rayons divergence ; pénalité QWOT gardée ; avertir sans refuser extrapolation. Matériau absent refuse calcul ; Nb2O5 « Syrus » brut > 4 µm.
- `uv sync --upgrade` ; **fastmath gardé** ; tolérance C1 `10⁻¹⁰` pour code mort ; hub sans warmup JIT.
- GPL-3.0 ; gel via environnement jetable `requirements.lock` + licences. `certus_re` sous CC BY 4.0.
- Threads Numba : OpenMP, sauf STRAT et RE sous TBB optionnel (`certus_core.TBB_THREADING_LAYER`, 👤 2026-11-15 : juge de paix 1 074 s vs 1 339 s mêmes bits ; RE 17,5 s vs 28,2 s ; [STRAT](../reports/audit_oms5100_2026-11-15/profil_strat_complet/bilan.md), [INDEX/RE](../reports/audit_oms5100_2026-11-15/tbb_index_re/bilan.md)).
- Fusion `master` soumise à 👤. Caps entrypoints dans `tests/unit/test_the_ai_entry_points_stay_small.py` (à abaisser librement).
- Benchmarks litt. (2026-10-30) : Trubetskov 2020 (octave) / miroir chaud / antireflets hors champ ; OIC 2016 doit battre `0,0139`.

## 4. Limites et travaux ouverts

Chantiers ouverts : [`CHANTIERS_RESTANTS.md`](CHANTIERS_RESTANTS.md). Limites : guides [DESIGN](../pages/CERTUS_DESIGN.html#design-limits) et [STRAT](../pages/CERTUS_STRAT.html). Cache Numba : [mode opératoire](../reports/refactor_corridors_2026-11-11/cache_numba_arbre_neuf.md).

## 5. Ce qui attend une décision de 👤

| sujet | enjeu |
|---|---|
| **plancher ε1 d'INDEX** | ε1 ≥ 1 inactif sur les 4 exemples (≥ 2,24, [mesure](../reports/audit_code_2026-11-15/preuves/p_plancher_epsilon1.txt)) : garder ? |
| **avis de tiers** | DLL Visual C++ (`THIRD_PARTY_NOTICES.md`) : droit de redistribution Microsoft |
| **paquet `certus_re`** | citation saphir (Malitson & Dodge 1972) à committer puis Zenodo |
| **interface** | revoir les 11 fenêtres (teintes, fichiers récents, bornes numériques) |
| **base de dépôts** | RE depuis dépôt (`load_reverse_engineering_from_path`) ; apparier T/R ; plage λ complète phase 2 |
| **ELITE « tour à tour »** | `elite_round_robin` : +0,7 % mesuré avant, inactif, manque variance même graine |
| **Rate vs optique pure** | meilleur plan = Rate sous tous modèles d'arrêt ; Rate STRAT sans dérive/bruit vitesse (§7) ; A4 nul en arrêt tardif ([rapport](../reports/ANALYSE_claude_2026-10-22/bilan.md) §4) |
| **comportements** | D108 (`ValueError`), D109 (`épaisseur >= 0` TMM), D114 (entrées invalides) |
| **CI** (D110) | déclarer `pytest-benchmark` & `pytest-xdist`, 3 docs checks dans `lint.yml`, `mypy` et `bench_kernels` bloquants |
| **A9** | refiger le protocole sur branche de travail avant GO |
| **réglages STRAT** | `elite_rate_moves` (actif, ou `git revert 978b8f04`, [A2](../reports/STRAT_A2_continuation_2026-10-14/final_bilan_A2_20261014.md)), `rate_rescue_hard`, `tp_hysteresis_floor`, `strat_local_search_fresh_id` |
| **modèles** | D69 (nouvelle définition de la couverture des noyaux) |
| **publication** | vitrine, autorisation écrite Tikhonravov 1996 (`example/example_design/JSON-design-reference-tikhonravov-1996-published-design.json`) |

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
