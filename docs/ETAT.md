# CERTUS — état du projet

> Ce document porte l'**état** : où en sont les programmes, les repères mesurés, ce que 👤 a
> décidé, les défauts ouverts et les chantiers. Les **règles** sont dans
> [`CLAUDE.md`](../CLAUDE.md). Il se tient **en place** : un fait change, on corrige sa ligne,
> on ne raconte pas la correction (`git log` s'en charge). Toute mesure porte sa date.
> Le détail et l'historique sont dans [`archives/`](archives/), sans autorité.
> Mis à jour le 2026-09-26.

## 0. Reprise — à lire en premier, à tenir à jour

> **Consigne à l'IA qui reprend.** Ce tableau est le fil du travail. Tiens-le à jour **au fur et
> à mesure**, pas en fin de session : une action commencée passe à « en cours », une action
> finie à « faite » avec son commit et sa mesure (la sortie de la commande : CLAUDE.md,
> interdit 9) ; toute action ou découverte nouvelle ajoute une ligne. Corrige en place, sans
> récit, et commite chaque mise à jour avec le travail qu'elle décrit. Avant de rendre la main :
> ce tableau, les lignes D touchées, `git status` propre, `git push`. Relis les sections 2, 4 et
> 12 de CLAUDE.md avant de valider quoi que ce soit ou de relayer le rapport d'un autre agent.
> Les décisions de la section 5 reviennent à 👤 : **ne les tranche pas à sa place**.

**Point de départ.** Branche `refactor-corridors-mixins`, synchronisée avec `origin` à la fin de la session du 2026-09-26. Première commande : `python scripts\preflight.py` → `PREFLIGHT=GO`.
Dernière validation locale complète, sur `e05d0db` (Windows 11) : ruff propre · oracle 570 passed
· unit 2 520 passed, 5 skipped · le reste de `tests/` 338 passed, 2 skipped · **0 failed** ;
`tests/ui/` est confié au job Windows de la CI. CI du même commit (run 36252221457) : job Linux `pytest` **vert** à toutes ses étapes, `tests/headless/` compris ; `lint` vert ; job Windows `interface` **vert** (785 passed en 50 min 33 sur le runner, dès 9477d51).

| # | action | état | où | fini quand |
|---|---|---|---|---|
| R1 | juger la fixture headless (D23) | **faite** : 3 runs CI de suite verts sur les deux jobs (36252221457, 36253016921, 36253221047 : Linux « Le reste de tests/ » 338 passed, Windows `interface` vert), aucun « did not join » ni message `QThread` dans les journaux ; et **10 passes locales sur 10** de `tests/headless/` (9 passed chacune, 2 min 46 à 2 min 59). Avant la fixture : 4 morts sur 6 passes locales ; dix vertes de suite par hasard auraient une probabilité de (1/3)^10, environ 1 sur 59 000 | `tests/headless/conftest.py` | mesuré le 2026-09-26 |
| R2 | D32 : la CI installe exactement `uv.lock` | **faite** : CI verte sur le verrou (run 36274463994), le journal liste les versions d'`uv.lock` ; `uv sync --frozen --no-install-project --extra dev` dans les deux jobs, verrou régénéré (`uv lock --upgrade`) sur les versions que la CI validait déjà : numba 0.67.0, numpy 2.5.3, scipy 1.18.1, pyqt6-qt6 6.11.2. Dans un environnement construit depuis ce verrou (Python 3.14.7) : oracle 570 passed, unit 2528 passed, 5 skipped | `.github/workflows/tests.yml`, `uv.lock` | mesuré le 2026-09-26 |
| R3 | D33 : retenir un `EvalWorker` remplacé jusqu'à son `finished` natif | **faite** (commit « interface : remplacer une évaluation en cours ne détruit plus son thread ») : `_retain_until_finished` dans `certus_spectrum_eval_ui`, sur le modèle `_ORPHAN_WORKERS` du mixin spline ; un seul site écrasait le worker | `spectrum_eval_start_worker` | 5 tests, dont un contrôle négatif en sous-processus (un `QThread` lâché en cours tue le processus) ; 4 échouent sur le code d'avant. ruff propre, oracle 570, unit 2 526 passed |
| R4 | lint, règles sans effet à l'exécution : B009, B010, B904, UP009, UP015, UP034, RUF010, F541, RUF013, UP006, UP035, UP045, B905 (`strict=False` explicite)… | à faire | D25 ; à la main, jamais `ruff --fix` | chaque règle sortie d'`extend-ignore` **et** d'`ALLOWED_EXTEND_IGNORE`, un commit par famille, ruff, oracle et unit verts |
| R5 | D11 : les fenêtres fermées ne sont jamais détruites | **faite côté tests** (commits « tests : la fixture de cycle de vie headless devient un module partagé… » et « tests/ui : chaque test détruit les fenêtres principales qu'il a construites (D11) ») : `tests/ui/` détruit en fin de test les fenêtres principales sans parent qu'un test a construites, en fin de module celles de ses fixtures, après avoir joint leurs threads. `tests/ui/` complet, `test_ux_re_stop_when_idle` compris : **791 passed, 10 skipped, 3 xfailed, 0 failed en 20 min 05**, contre 785 passed en 29 min 22 pour l'ancien conftest **sans** ce fichier, mesurés le même soir sur ce poste ; ses six tests passent chacun sous 8,65 s, contre ~9 min en fin de suite auparavant. Détruire **tous** les widgets de premier niveau faisait avorter `test_certus_strat_ui_smoke` (sous-fenêtres à demi construites sous un `QWidget` libre), d'où la restriction aux fenêtres principales | `tests/qt_lifecycle.py`, `tests/ui/conftest.py` | mesuré le 2026-09-27 |
| R6 | D23 : abort quand les tests unitaires METAL et les tests headless partagent un processus | **faite** (commits « tests : les smoke tests METAL empruntent la QApplication de session… » et « tests : aucun test ne crée une QApplication qu'il pourrait perdre… ») : deux smoke tests METAL créaient leur `QApplication` dans une variable locale ; premiers tests Qt du processus, elle mourait avec eux. Commande R6 : **3 passes sur 3 vertes** (46 passed), contre un abandon (rc=127, puis corruption du tas `0xc0000374`) ; fichiers unitaires METAL seuls : 9 sur 9 contre `1 failed`. Un gardien interdit le motif, qu'il trouvait dans cinq fichiers | `tests/unit/test_tests_borrow_the_session_qapplication.py` | mesuré le 2026-09-27 |
| R7 | D23 : les trois faux échecs à cache numba froid, attribués à `sys.modules` | à instruire | reproduire à cache froid, trouver le test qui pollue, puis `tests/conftest.py` | une première passe à cache froid rend 0 failed |
| R8 | lint : F811, 85 cas, un par un | à faire | imports en double des modules racine (sûrs) ; réaffectations de noyaux dans `_certus_physics_impl.py` (`DO NOT SPLIT`) | F811 sort d'`extend-ignore` ; `tests/oracle/` vert avant et après |
| R9 | lint à effet possible : imports (F401, F405, I001, E402) et RUF005, RUF015, RUF046, UP040, UP042, UP046, B019, E741 | à spécifier | F401 compte des réexports volontaires ; l'ordre des imports compte (import circulaire) | une spécification écrite et validée par 👤 avant tout code |
| R10 | chaque session pytest laissait un dossier `certus_test_prefs_*` dans le dossier temporaire (65 en une journée) | **faite** (commit « tests : chaque session pytest supprime son dossier de préférences ») : `atexit` supprime le seul dossier créé par `tests/conftest.py`, jamais un `CERTUS_CONFIG_DIR` fourni ; test en sous-processus, qui échoue sans le correctif | `tests/conftest.py` | 0 dossier après oracle 570 passed et unit 2 521 passed, 5 skipped (mesuré le 2026-09-26) |
| R11 | les tests écrivent tes réglages dans le registre | à faire, spécifiée | `closeEvent` appelle `_qs_save()`, qui écrit géométrie, état, séparateurs et en-têtes de tableaux dans `HKCU\Software\CERTUS\<module>` par `QSettings("CERTUS", APP_NAME)` ; `_qs_restore()` les relit à la construction. Chaque fenêtre qu'un test ferme écrase donc ta disposition, et les tests d'interface dépendent du registre du poste. `QSettings.setDefaultFormat` n'agit pas sur ce constructeur. Piste : une fabrique `certus_settings(org, app)` qui, si `CERTUS_CONFIG_DIR` est posée, rend un `QSettings` au format INI dans ce dossier, et le constructeur d'aujourd'hui sinon (inerte par défaut, C1) ; 32 appels dans 16 fichiers, relevés le 2026-09-27 | `certus/core/certus_config.py` et les 16 fichiers | une passe de `tests/` ne modifie plus `HKCU\Software\CERTUS` |

## 1. Où en sont les programmes

| programme | état | prochaine action |
|---|---|---|
| **Calcul (STRAT)** | composant étalon : l'aléatoire ×2 (`r75x2`) à la fente de 2 nm. Fabricable avec les rampes de la configuration livrée ; sans rampes, 3 graines sur 7 trouvent des déposables. Toute la fabricabilité passe par le générateur ELITE | voir la section 6 |
| **Interface** | plan clos le 2026-09-08 : 12 critères de fin sur 13 atteints et mesurés, le treizième démontré inatteignable (`xfail` strict) | la revue visuelle et trois arbitrages de 👤 (section 5) ; la fuite des fenêtres (défaut D11) |
| **Qualité** | CI GitHub sur toutes les branches : job `pytest` sous Linux (oracle, unit, puis le reste de `tests/`), job `interface` sous Windows (`tests/ui/`). Le 2026-09-26 : `certus/` commenté en anglais (1 143 lignes, garde-fou) ; les tests n'écrivent plus les préférences de l'utilisateur ; plantage de `tests/headless/` expliqué (un `QThread` détruit pendant qu'il tourne, D23) et fixture de cycle de vie posée ; dette de lint ramenée de 68 à 48 règles, cliquet nominatif (D25) | **D23 avant D11** (décision de 👤 du 2026-09-26) ; l'ordre des actions est le tableau de la section 0 |
| **Documentation** | cure du 2026-09-26 : deux documents vivants, 27 archivés | tenir « un fait, un seul endroit » |
| **Validation externe** | 🔴 **aucune** : STRAT n'est validé que contre lui-même | deux dépôts réels du dichroïque (section 5) |

## 2. Repères mesurés — fente 2 nm, modèle courant

| composant | SEEL | plantage | condition |
|---|---|---|---|
| dichroïque 48 couches, `JSON-strat-example` | **0,173 nm** | 0 % | 6 blocs, une campagne |
| passe-bande 3 cavités, 35 couches | **0,482 nm** | 0 % | 6 blocs, mode `deep` |
| aléatoire `JSON-strat-random75`, 75 couches | **0,272 nm** | 0 % | une campagne, 241 déposables sur 662 |
| passe-bande 5 cavités, 99 couches | **0,81 nm** | 0 % par campagne | 4 verres témoins, partition 0-22 / 22-42 / 42-76 / 76-99 |
| le même en une seule campagne | aucun score valide | 100 % | 487 stratégies, toutes plantent : non fabricable |
| aléatoire ×2 `r75x2`, fente native 1 nm | **0,6248 nm** | 0 % | `deep`, pur optique, 277 déposables |
| `r75x2` à 2 nm, configuration livrée | **0,5676 nm** | 1,67 % | avec `example/example_strat/rampes_r75x2-2nm.json` ; étendue 0,55 % sur 3 graines |
| `r75x2` à 2 nm, sans rampes | **0,5599 nm** | — | graine 404 ; 3 graines sur 7 trouvent (77, 404, 505). Égalité avec la voie à rampes, pas supériorité |

Le passe-bande de 99 couches est chiffré en moyenne de trois graines, jamais par la meilleure.
Le 0,86 nm des anciens rapports est un score de repli, rendu quand aucune stratégie ne survit.

**Lire ces chiffres :**

- 🔴 **Les SEEL ne se comparent pas d'un composant à l'autre** : ils sont notés sur des
  domaines de largeur différente (section 7). Toute comparaison **à composant fixé** est valide.
- 🔴 **Un score seul ne départage rien.** À N = 150 tirages, la dispersion Monte-Carlo vaut
  σ ≈ 6 % ; deux runs à moins de ~8 % sont indiscernables. On compare des **classes
  d'équivalence SEEL**. Sur `r75x2`, σ ≈ 1,8 % mesuré en changeant le triplet de graines de
  consensus : un bruit emprunté à un autre composant ne vaut rien.
- Le **biais de fente** est actif depuis le 2026-08-11 : un résultat antérieur décrit une
  machine à fentes infiniment fines et ne se cite plus.
- La longueur seule ne met pas le monitoring optique en échec, la **structure** si :
  75 couches aléatoires passent, 99 couches à cavités et miroirs non. Sur un empilement
  structuré, la longueur pèse ensuite : sur 270 sous-intervalles du passe-bande de 99 couches,
  la part de déposables s'effondre avec elle (r = −0,869).
- Un taux de 100 % obtenu en `fast` ne conclut rien (la recherche peut n'avoir rien proposé) ;
  un 100 % qui tient jusqu'à `deep` est un constat sur le composant et sa fente.
- Au banc : `CERTUS_BENCH_TIMEOUT_S = max(5400, 4 × durée attendue)`. Au-delà du plafond le
  banc rend `RESULT=None` avec une poignée de stratégies : cherche `WAIT_TIMEOUT=` dans le journal.

## 3. Ce que 👤 a décidé — ne pas rouvrir sans mesure qui le contredise

### Réglages

| réglage | valeur |
|---|---|
| cadence machine | 4 Hz, une lecture témoin par tour |
| pas d'échantillonnage machine | un point tous les 0,125 nm à 0,5 nm/s |
| bruit de lecture | ±0,05 point, soit `A = 5e-4` en unités T |
| `reading_smoothing_window` | 1 (inactif) en exploitation ; 8 lectures dans le modèle figé |
| `tp_hysteresis_factor` | 1,66 en usage. Cible 1,00, mesurée à k = 8 et N = 800 : à remesurer avant de l'appliquer, les configurations tournant à k = 1. Il porte aussi le **sens** de variation du plantage avec le bruit — physique à 0,5, inversé à 1,66 |
| `phase_a_level_margin_factor` | 1,66 ; 3,33 à évaluer |
| `index_corridor` | 0,005 en indice absolu, actif |
| `photometric_curvature_amp` | **0,00375**, actif |
| `affine_scale_amp`, `affine_offset_amp` | 0,05 et 0,02 |
| `allow_rate` | vrai — « le cas général » |
| `slit_bias_enabled` | vrai, fente nominale 2 nm |
| choix de fente de l'opérateur | 5, 1 ou 0,5 nm en plus du nominal ; facteurs de bruit ÷1,5, ×2, ×5 |
| `robustness_num_runs` | 300, décidé le 2026-08-13 : il commande la sensibilité du filtre de plantage, donc **quelles stratégies existent**. 🔴 En `premium` l'application l'écrase à 150 (défaut D1) |
| `n_screen_runs` | 25 ; à 10, un seul plantage tue une stratégie **et** la perd comme parent |
| profondeurs par mode | `robustness_num_runs` 50 / 150 / 300, `n_screen_runs` 10 / 25 / 50, `dp_top_k` 20 / 40 / 100 pour fast / premium / deep ; `extreme` = `deep` avec une génération élargie |
| graine de référence | 42, avec `scan_wl_step` à 1,0 |
| grille des λ de contrôle | figée à 1 nm |
| `machine_sampling_dd` | 0 : pas grossier (~21 points par couche au lieu de 800), par choix de vitesse. Le modèle est donc optimiste sur les faux points tournants |
| cible spectrale | non pondérée jusqu'à nouvel ordre |
| mode par défaut | `premium` |

### Le modèle de la chaîne de lecture (OMS 5100) — figé le 2026-08-08

1. Une lecture témoin par tour à 4 Hz, soit un échantillon tous les 0,125 nm.
2. Bruit additif borné à ±0,05 point, σ = A/3, tirages indépendants d'une lecture à l'autre.
3. Moyenne glissante de k = 8 lectures (2 s) dans le modèle, inactive en exploitation.
4. Seuil de point tournant : la borne **mesurée** vaut 1,00 A à k = 8 et N = 800 ; la loi en
   1/√k est réfutée (elle laisse 100 % de points tournants fabriqués). Une mesure, pas une loi.
5. Aucun retard de déclenchement.
6. Marge de sélection des λ : 5 σ du bruit brut (1,66 A) ; 10 σ (3,33 A) à évaluer.
7. Quantification de l'arrêt `U(0 ; 0,125 nm)` — non implantée (défaut D13).

Hors du modèle, et à y laisser : σ dépendant de T ou de λ, grenaille, bruit multiplicatif,
bruit corrélé d'un tour à l'autre, tout filtre autre que la moyenne glissante. Seul un run réel
du dichroïque dont le plantage s'écarterait nettement du prédit rouvrirait ce modèle.

### Règles gravées

- **Une λ de contrôle est interdite** si, signal bruité, elle risque de mal compter les points
  tournants ou de ne pas s'arrêter au niveau voulu — en Phase A comme en Phase B. La marge se
  compte **en transmission, jamais en nanomètres**.
- Les λ se choisissent sur la **grille de balayage** (`_resolve_monitoring_wavelength_grid`),
  jamais d'après les clés de `clues_at_wl`, qui mêlent grille de balayage et d'affichage.
- Les heuristiques de la littérature (15-85 %, amplitude de départ, swing) sont des
  **colonnes explicatives**, jamais des couperets.
- **Rate interdit sur les couches 0 et 1, autorisé partout ailleurs, dernière comprise**
  (`RATE_MIN_LAYER = 2`) : avant la couche 2, aucune couche de même nature n'a été déposée
  dont tirer un rate. Le rate ne se calcule **que sur les couches déposées optiquement**.
  Son mécanisme est la **position terminale** : une couche Rate lègue son erreur en boucle
  ouverte à tout ce qui la suit, la dernière n'a rien en aval.
- **SEEL** est la seule grandeur à rapporter : `SEEL = 2 × √score` (`_apply_strategy_ranking`),
  en nanomètres d'erreur d'épaisseur par couche. Tri : SEEL quantifié au pas de 0,01 nm, puis
  rendement, puis marge de la couche critique. Un écart d'un pas est une égalité.
- **`fast` crible, il ne publie pas** : il est quantifié à 10 % sur le plantage, et un SEEL
  retenu en `fast` se rejoue en `premium`. **`extreme` n'a aucune justification mesurée** —
  zéro amélioration sur cinq configurations, `deep` seul fait aussi bien pour un cinquième du coût.
- **La profondeur Monte-Carlo sert à noter, jamais à choisir** : une candidate écartée parce
  que N était petit est perdue pour toujours.
- **Le multi-témoins est un outil de faisabilité**, pas d'optimisation : il rend le passe-bande
  de 99 couches fabricable et dégrade tout composant qui s'en passait (contrôle négatif 3 sur 3).

## 4. Défauts ouverts

Numérotés ici ; un défaut corrigé sort de la liste et son numéro n'est pas réattribué. Les
numéros de l'ancien registre sont entre parenthèses
([`archives/DEFAUTS_OUVERTS.md`](archives/DEFAUTS_OUVERTS.md)).

**Ils faussent un résultat ou trompent l'utilisateur**

| # | défaut | piste |
|---|---|---|
| D1 | **Des réglages visibles n'agissent pas** : `strategy_phase_timeout` (son info-bulle promet d'annuler la passe, aucune ligne de calcul ne le lit), `machine_sampling_dd` (le seul appel du noyau qui le transmet passe 0.0 en dur), `dp_yield_weight` (sans effet même à 200), `fast_auto_blocks` (journalisé, jamais lu), `seel_equivalence_half_width` sans aucun appelant (n° 33, 50, 52). Et **le mode d'exécution écrase sept budgets du JSON** dans `collect_params` : chargé dans l'application, `JSON-strat-example.json` déclare `robustness_num_runs` 300 et tourne à 150 (mesuré le 2026-09-26). Les info-bulles des deux premiers le disent depuis le 2026-09-26 | brancher ou retirer chacun, et décider qui du mode ou du fichier fait foi — décision de 👤 |
| D2 | La porte de plantage juge au **pire des trois niveaux de bruit** (0,5× / 1× / 2×) : `crash_rate` est ce maximum, et le taux au bruit réel n'est porté nulle part | exposer le taux au bruit nominal |
| D3 | Le logger `ThinFilm` est muet : tout `logger.info` du classement est perdu (n° 53). Cause établie le 2026-09-26 : ni lui ni la racine n'ont de gestionnaire, donc Python jette les `info` et ne laisse passer les avertissements que vers stderr (gestionnaire de dernier recours) ; le worker, lui, attache le sien à `W{n_blk}` | en faire un enfant du logger `CERTUS`, ou passer `params["logger"]` au classement — change ce qu'affichent les journaux de STRAT, décision de 👤 |
| D4 | Une stratégie bâtie sur des couches « forcées » (Phase A en repli) est indiscernable d'une stratégie choisie (n° 37) | remonter `n_layers_forced` dans le résultat et le classement |
| D5 | `strategy_id` n'est pas unique : 21 identifiants sur 79 portés par plusieurs stratégies (n° 51) | vérifier l'unicité avant tout appariement parente/enfant |
| D6 | Le consensus ignore `robustness_num_runs`, et `robustness_seed` dès que `consensus_seed_list` est renseignée (n° 18, 47) | exposer `consensus_num_runs` |
| D7 | Deux configurations rendent le même `RESULT` au bit alors qu'une bande diffère de 38 % (n° 15) | vérifier dans le code ce que `RESULT` agrège |
| D8 | `scripts/campagne_intervalles.py` forçait `search_resolution` à faux alors que 👤 en a fait un prérequis : les campagnes d'intervalles ont tourné sans recherche de fente (n° 49) | refaire les intervalles utiles avec la fente cherchée |
| D9 | Restreindre la plage de blocs vide la DP ; cause non établie (n° 54) | mesurer la recherche à plage complète |
| D10 | **L'ajustement Sellmeier 3 pôles est chaotique sur le saphir** : un ulp sur les données change le minimum atteint (RMSE de 0,00126 à 0,00208 sur 41 essais, 2026-09-26) ; deux machines rendent deux indices pour les mêmes données. SiO2 et BK7 sont stables | élargir le multistart ou reconditionner — change les résultats, décision de 👤 |

**Le modèle physique — connus, non corrigés**

| # | défaut |
|---|---|
| D12 | La moyenne de lecture est **causale** : elle décale un extremum de (k−1)/2 échantillons (n° 3) |
| D13 | La quantification de l'arrêt n'est pas implantée (n° 4) |
| D14 | L'historique est échantillonné 1,33× plus grossièrement que la couche courante (`NPTS_PREV = 16` contre `NPTS = 64` sur trois épaisseurs nominales) (n° 22) |
| D15 | POEM ne rejoue que les quatre dernières couches d'un bloc (`MAX_LOOKBACK_VAL = 4`) : la valeur d'un bloc long est plafonnée par construction (n° 21) |
| D16 | Le bonus « block-aware » de la Phase A écrase le coût en place, avant la normalisation, qui l'élève au carré (n° 45) |
| D17 | Le critère `forbidden_gain_negative` n'a jamais rejeté une candidate (n° 38) |
| D18 | Deux seuils de swing : `RATE_SWING_MIN_DEFAULT = 0,025` admet une λ, et 0,04 codé en dur fait abandonner POEM ; entre les deux, une couche perd POEM en silence |
| D19 | La Phase A ne vérifie jamais qu'une λ offre un point tournant ; proposition de 👤 : les compter, en coût non monotone |
| D20 | `turning_point_margins` est calculé, mais `use_margin_ranking` est inactif par défaut |
| D21 | `MachineModel` n'a aucun consommateur, et `trigger_tolerance` y est documenté en unités T alors que ses lecteurs divisent par 100 (n° 9) |
| D22 | La Phase A ignore qu'une couche Rate efface l'historique ; effet borné à une couche |

**Le code et les tests**

| # | défaut |
|---|---|
| D11 | **Une fenêtre de module fermée n'est pas détruite** : des lambdas et des `functools.partial` branchés sur les signaux de ses propres widgets la capturent, et la connexion les tient du côté C++ de PyQt, où le ramasse-miettes ne voit pas le cycle (`scripts/sonde_retenants_fenetre.py`, 2026-09-27 : `CertusREApp` retenue par quatre méthodes liées, cinq fermetures et deux attributs de `CertusToast` / `CertusToastStack`). **Sans effet en production** : le hub lance chaque module dans son propre processus (`QProcess`), et fermer la fenêtre finit le processus. Les tests détruisent désormais leurs fenêtres (R5). Coûterait dans tout processus qui construirait plusieurs fenêtres. Piste : `WA_DeleteOnClose` sur `CertusBaseApp`, à condition de retenir d'abord ses `QThread` encore actifs : sans cela, libérer la fenêtre libère un thread en cours (D23) |
| D23 | Isolation des tests. **Plantage intermittent de `tests/headless/`** (classé ici par 👤) : **cause établie le 2026-09-26** sur le binaire Qt de la CI (PyQt6-Qt6 6.11.2 ; l'adresse du journal suit un `call QMessageLogger::fatal` dont le format, `"QThread: Destroyed while thread '%ls' is still running"`, n'a qu'une référence dans la bibliothèque, atteinte depuis `QThread::~QThread`) : un `QThread` reçoit un `DeferredDelete` pendant qu'il tourne, livré par la boucle d'événements du test en cours. La capture de pytest avale le message. Mesuré sur ce poste : `deleteLater()`, ou l'abandon de sa dernière référence Python, tue le processus (code 127). L'émetteur n'est pas identifié : tous les `finished → deleteLater` du code passent par le `finished` natif, qui est sûr. La fixture `headless_lifecycle` joint les threads Qt et Python avant de livrer les destructions différées, puis détruit les fenêtres : elle couvre un thread laissé actif par un test précédent, pas une destruction postée dans le même test ; premier run Linux vert le 2026-09-26 (36252221457), trois de suite restent à obtenir (section 0, R1) ; la passe Windows de référence, sans elle, était déjà verte. Son délai de jonction est de 180 s : à 30 s, elle arrêtait la suite sous charge après `test_index`, parce que les raffinements qui suivent PGLOBAL dans l'étage IR d'INDEX (`IRGlobalModelWorker`) ne lisent pas l'arrêt — seul PGLOBAL reçoit le `stop_event`. Qu'un Stop n'interrompe pas ces raffinements est un choix de produit, décision de 👤. Restent : rien ne protège `sys.modules` (trois faux échecs à cache numba froid) ; arrêt natif `0xC0000005` du worker Qt 2 fois sur 120 lancements (le harnais UI réessaie). Le squelette de `CERTUS_DESIGN` amputé après `test_design_and_re_splitter_persistence` ne se reproduit plus (3 passes sur 3 le 2026-09-26, référence de 119 contrôles) ; mécanisme jamais établi. Diagnostic : sous Windows, Qt envoie ses messages à `OutputDebugString` quand stderr n'est pas une console — d'où les stderr vides des arrêts natifs ; `QT_FORCE_STDERR_LOGGING=1` les rend visibles (vérifié le 2026-09-26 sur le `qFatal` ci-dessus). L'abandon des fichiers unitaires METAL suivis des tests headless METAL, dans un même processus, avait pour cause une `QApplication` créée dans une variable locale par un test, donc détruite avec lui (R6, corrigé le 2026-09-27) ; `QThreadPool.globalInstance()` rendait ensuite None, et la fenêtre bilayer se fermait sur une Qt détruite puis recréée. Une fenêtre laissée vivante jusqu'à la sortie de l'interpréteur peut encore faire planter sa finalisation : mesuré sur ces fichiers, 3 fois sur 9, avant qu'ils ne détruisent leur fenêtre |
| D24 | Sept symboles morts justifiés un à un dans `tools/dead_symbol_whitelist.txt`, dont `CertusHub._apply_card_animations` et `_build_auto_batch_script` des deux modules METAL (n° 55) |
| D25 | Dette de lint masquée par `extend-ignore` : **48 règles, 12 302 violations le 2026-09-26**, presque toutes d'import (F401 5 318, F405 3 153, I001 929, E402 907) ; les noms indéfinis (F821, F822) sont à zéro. Le cliquet `tests/oracle/test_lint_debt_ratchet.py` nomme les règles restantes : aucune ne peut entrer, et une règle sortie doit quitter sa liste. RUF022 et RUF023 (trier `__all__`, `__slots__`) restent ignorées à dessein |
| D26 | Inversions de couches, comptées le 2026-08-19 : `utils → ui` (11), `core → workers` (10), cycle `physics ↔ core` (23 et 29 imports) |
| D27 | Sous-paquets PEP 420 et `packages = ["certus"]` : un `pip install` ne livrerait aucun sous-module |
| D30 | `CERTUS_METAL_SINGLE.py` et `CERTUS_METAL_BILAYER.py` restent à la racine alors que `certus/metal/` existe ; le `.coverage` pointe vers un autre snapshot |

## 5. Ce qui attend une décision de 👤

Ces sujets demandent un jugement de physicien ou de propriétaire du produit. Ce qui a pu
être tranché sans eux l'a été (section 5bis).

| sujet | ce qui est en jeu |
|---|---|
| **historique git public** | l'historique porte encore le texte intégral d'une thèse tierce (`reports/_zideluns_text.json`), les classeurs d'avant correctif avec un nom civil, et des fichiers `.vs/`. Purger = `git filter-repo` puis force-push : tous les hash changent, étiquette `depart-gemini` comprise. 📌 **Décision du 2026-09-26 : ne pas purger sans ton accord explicite** — l'acte est irréversible sur un dépôt public et casse tous les renvois ; la thèse est par ailleurs publiquement accessible, l'enjeu est sa rediffusion. Ce qui était évitable l'a été : le papier tiers et `studies/` sont désormais dans `.gitignore` |
| **le dépôt dans Google Drive** | un dépôt git synchronisé par Drive est lent et exposé aux copies de conflit dans `.git` ; ce dossier est en plus partagé par deux PC sous deux chemins différents. Recommandé : un clone hors Drive par machine. Non fait : déplacer l'arbre de travail pendant qu'on y travaille n'est pas une opération sûre |
| **données Nb2O5 « Syrus »** | dans les feuilles `Nb2O5-Syrus` et `IR-Syrus-Nb2O5` de `example/database_index/indices.xlsx`, n tombe de 2,09 à 4,0 µm à 1,19 à 4,7 µm puis remonte à 1,78 à 5 µm, quand les feuilles H400 et H800 restent entre 2,07 et 2,13. Un creux de cette taille avec k ≤ 0,018 n'est pas physique |
| **défauts D1, D10, D24** | brancher ou retirer les réglages inertes, et décider qui du mode ou du fichier fait foi ; fiabiliser l'ajustement du saphir ; supprimer ou rebrancher les symboles morts. Les trois **changent des résultats de production** |
| **interface** | la revue visuelle des onze fenêtres, reportée le 2026-09-08 ; trois arbitrages : teintes de marque, bande des fichiers récents, bornes des champs numériques. 📌 La branche `claude/charming-wright-43077a` porte un travail **non porté** — lire les couleurs des badges, info-bulles et barre de progression dans le thème ; les trois fichiers portent encore des hexadécimaux en dur. L'appliquer **change le rendu**, donc cela attend la revue |
| **Stop pendant l'étage IR d'INDEX** | interrompre aussi les raffinements qui suivent PGLOBAL, ou garder le résultat raffiné livré aujourd'hui (détail : D23) — change ce que voit l'utilisateur |
| **validation externe** | deux stratégies réellement déposées du dichroïque, avec leurs spectres mesurés. Le test est **ordinal** : STRAT doit les classer dans le bon ordre |
| **sorties de test dans `reports/`** | les 24 `Report_SINGLE` suivis sont tous des sorties de l'exemple simulé `Target_Titane_Simu_20nm`, alors que `.gitignore` les range parmi les « mesures métaux réelles » ; les 24 `Report_INDEX_H400-RTNBrel-sapphire` suivis portent le nom du fichier d'entrée du test headless INDEX. Les garder ou les retirer. Et `certus_export.json` / `certus_theme.json`, tes préférences, sont suivis par git : les tests ne les touchent plus, mais l'application les réécrit à chaque réglage |
| **fichiers hors git** | `Selenium_Optical_Constants*.pdf` (œuvre d'un tiers) et `studies/selenium_bk7/` (recherche non publiée, dont des scripts sources) : ignorés désormais, donc dans aucun clone. **À sauvegarder à la main avant tout changement de machine**, ou à commiter si tu le décides |
| **poste de travail** | le venv `C:\envs\certus` (numba 0.66) est inutilisé depuis le passage au Python système : à supprimer si tu le confirmes ; et le Python système ne suit pas `uv.lock` : pydantic 2.13.4, **sous la borne 2.14.0a1 de `pyproject.toml`**, pandas 3.0.5, numpy 2.5.2, scipy 1.18.0, pyqt6-qt6 6.11.1, ruff 0.16.3 (verrou : 2.14.0b2, 3.0.6, 2.5.3, 1.18.1, 6.11.2, 0.16.9 ; le job `lint` épingle ruff 0.15.12). Relevé le 2026-09-26. L'aligner (`uv pip sync`, ou un environnement `uv sync` hors du dépôt) change l'interpréteur de tous tes outils |
| **courriel dans l'historique** | quatre commits portent ton adresse personnelle ; les 1 344 autres l'adresse de non-réponse GitHub. C'est ton choix, pas un défaut — signalé une fois |

## 5bis. Arbitrages rendus le 2026-09-26, sans attendre

| décidé | pourquoi |
|---|---|
| **les tests n'écrivent plus tes fichiers** | `CERTUS_CONFIG_DIR` isole les préférences, export automatique coupé ; les sous-processus héritent de la variable. Inerte sans elle : le chemin d'avant, au bit |
| **`test_config.json` retiré du suivi** | résidu d'un test de `ConfigManager`, jamais une donnée |
| **`C:\invalid\` supprimé** | résidu d'un test corrigé depuis ; deux fichiers de journal vides ou de diagnostic |
| **branche `local/sauvegarde-2026-09-25` supprimée** | redondante, **vérifié par empreinte** : les classeurs `indices.xlsx` et `reverse_sample.xlsx` y sont identiques à ceux de `HEAD`, et le travail d'interface identique à `be3b596`. Rien d'unique n'a été perdu |
| **le papier tiers et `studies/` sont ignorés** | le seul risque encore évitable sur un dépôt public est une **addition future** ; l'historique, lui, est la ligne ci-dessus |
| **l'interface se mesure sur Windows en CI** | sous Linux, 69 échecs et 12 erreurs, tous dus à l'absence de Segoe UI — l'audit refuse de mesurer des largeurs sur une machine qui n'existe pas. Job séparé, aucun test exclu |

## 6. Chantiers spécifiés, en attente

**Calcul** (détail : [`archives/REPRENDRE_ICI.md`](archives/REPRENDRE_ICI.md), section 8) —
dimensionner K, le nombre de graines à lancer : p ≈ 3/7 pour trouver un déposable, 2/7 pour
atteindre le niveau 0,57 · balayer `tp_hysteresis_factor` à bruit fixé · compter le criblage et
l'héritage quand un étage deviendra suspect · porter le résultat de `r75x2` dans la vitrine,
avec sa condition dans la même phrase que le chiffre.

**Modèle physique** (détail : [`archives/TRAVAUX_A_VENIR.md`](archives/TRAVAUX_A_VENIR.md)) :

| | sujet | état |
|---|---|---|
| 12.1 | l'épreuve de POEM | acquise — la dérive photométrique n'est pas affine |
| 12.2 | modéliser le lissage de lecture | ouvert — surtout ne pas remonter le seuil |
| 12.3 | méconnaissance d'indice | spécifié : corridor de dispersion |
| 12.4 | grille d'échantillonnage à la cadence machine | ouvert, à faire avant 12.2 |
| 12.5 | quantification temporelle du déclenchement | ouvert |
| 12.6 | facteur de face arrière | en dernier, ou jamais |
| 12.7 | résolution du monochromateur | spécifié |

**Réserve** (détail : [`archives/RESERVE_A25_A27.md`](archives/RESERVE_A25_A27.md)) —
**A25** `sigma_rate` comme prédiction : la seule grandeur vérifiable de l'extérieur, contre les
±1 à 2 % que 👤 observe en salle · **A26** un bloc de santé de run · **A27** le harnais
d'empreinte `float.hex()` qu'exige la règle d'or.

**Architecture** (détail : [`archives/PLAN_AMELIORATION.md`](archives/PLAN_AMELIORATION.md)) —
le cycle `physics ↔ core` (lot E), l'hygiène d'imports F401 / F403 / F405 (lot C). L'oracle
couvre déjà les gradients analytiques (lot B, clos).

**Prédictibilité** (détail : [`archives/CHANTIER_PREDICTIBILITE.md`](archives/CHANTIER_PREDICTIBILITE.md)) —
prédire sans tout calculer si un design passe avec un seul verre témoin ; quatre routes déjà
fermées par la mesure.

## 7. Les composants d'essai

| composant | fichier (`example/example_strat/`) | couches | notation | rôle |
|---|---|---|---|---|
| dichroïque | `JSON-strat-example.json` | 48 | 400-700 nm | le juge de paix : passe-court, front vers 545 nm |
| passe-bande 3 cavités | `JSON-strat-bandpass-3cav.json` | 35 | 600-660 nm | une résonance, une bande étroite |
| aléatoire | `JSON-strat-random75.json` | 75 | 550-750 nm | ni cavité, ni miroir, ni périodicité : teste si une règle est **générale** |
| passe-bande 5 cavités | `JSON-strat-bandpass-5cav-99c.json` | 99 | 610-655 nm | le cas dur |
| aléatoire ×2 | `JSON-strat-random75-x2-fabricable.json` | 75 | 550-750 nm | l'étalon depuis le 2026-08-20 : épaisseurs doublées, fente native 1 nm |

Une règle n'est acquise que si elle survit sur un empilement **sans structure**.

## 8. Les archives — ce que chacune contient

| document | contenu |
|---|---|
| [`CLAUDE_2026-09-26.md`](archives/CLAUDE_2026-09-26.md) | l'ancien document de référence, 2 000 lignes ; les numéros de section cités par le code y renvoient |
| [`REPRENDRE_ICI.md`](archives/REPRENDRE_ICI.md) | le journal de reprise jusqu'au 2026-09-08 : campagnes `r75x2`, multiseed, DOCP, hystérésis |
| [`DEFAUTS_OUVERTS.md`](archives/DEFAUTS_OUVERTS.md) | l'ancien registre des défauts, avec leurs mesures |
| [`REPERES_MESURES.md`](archives/REPERES_MESURES.md) | les repères de la section 2 et leur protocole ; la série d'échelle du random75 |
| [`PLAN_PRODUCTION_2026-08-20.md`](archives/PLAN_PRODUCTION_2026-08-20.md) | le programme du calcul d'août : multiseed, injection de plans, voie ELITE |
| [`CHANTIER_RATE.md`](archives/CHANTIER_RATE.md), [`MODE_RATE.md`](archives/MODE_RATE.md) | le mode Rate : mécanisme, coût, `sigma_rate` dérivé du simulateur |
| [`CHANTIER_MULTITEMOINS.md`](archives/CHANTIER_MULTITEMOINS.md) | le multi-témoins sur le passe-bande de 99 couches |
| [`CHANTIER_PREDICTIBILITE.md`](archives/CHANTIER_PREDICTIBILITE.md) | prédire la fabricabilité ; le mode `extreme` |
| [`SEEL.md`](archives/SEEL.md) | la définition de SEEL et l'histoire de sa quantification |
| [`QWOT_ET_TURNING_POINT.md`](archives/QWOT_ET_TURNING_POINT.md) | la démonstration QWOT ≠ point tournant |
| [`TRAVAUX_A_VENIR.md`](archives/TRAVAUX_A_VENIR.md), [`RESERVE_A25_A27.md`](archives/RESERVE_A25_A27.md) | les chantiers du modèle physique et la réserve, spécifiés |
| [`FEUILLE_DE_ROUTE.md`](archives/FEUILLE_DE_ROUTE.md), [`ETAT_IMPLANTATION.md`](archives/ETAT_IMPLANTATION.md) | les acquis A1 à A25, et l'implantation établie contre le code |
| [`DECISIONS_TRANCHEES.md`](archives/DECISIONS_TRANCHEES.md) | les enquêtes closes : grille des λ, profondeur Monte-Carlo |
| [`COMPOSANTS.md`](archives/COMPOSANTS.md), [`RAPPORT_FILTRE_EXTREME_5CAV_99C.md`](archives/RAPPORT_FILTRE_EXTREME_5CAV_99C.md) | la fiche de chaque composant, et l'étude du 99 couches |
| [`PERFORMANCE.md`](archives/PERFORMANCE.md) | les mesures de vitesse, pistes fermées comprises |
| [`CHANTIERS_OUVERTS.md`](archives/CHANTIERS_OUVERTS.md), [`PLAN_AMELIORATION.md`](archives/PLAN_AMELIORATION.md) | les propositions non mesurées et le plan d'architecture |
| [`UX_PLAN.md`](archives/UX_PLAN.md), [`UX_DEMENTIS.md`](archives/UX_DEMENTIS.md) | le chantier d'interface et ses affirmations réfutées |
| [`MEMOIRE_PROJET.md`](archives/MEMOIRE_PROJET.md) | les pièges du poste et du banc, dont `d_lo` / `d_hi` d'INDEX SPLINE |
| [`REPRISE_TESTS_ISOLATION.md`](archives/REPRISE_TESTS_ISOLATION.md), [`MESURE_REPRODUCTIBILITE_2026-09-07.md`](archives/MESURE_REPRODUCTIBILITE_2026-09-07.md) | l'isolation des tests et la reproductibilité de la suite d'interface |
| [`ORDRE_CLOUD_2026-09-25.md`](archives/ORDRE_CLOUD_2026-09-25.md) | l'ordre de mission cloud, abandonné le 2026-09-26 au profit du travail local |
