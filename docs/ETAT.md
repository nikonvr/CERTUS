# CERTUS — état du projet

> Ce document porte l'**état** : où en sont les programmes, les repères mesurés, ce que 👤 a
> décidé, les défauts ouverts et les chantiers. Les **règles** sont dans
> [`CLAUDE.md`](../CLAUDE.md). Il se tient **en place** : un fait change, on corrige sa ligne,
> on ne raconte pas la correction (`git log` s'en charge). Toute mesure porte sa date.
> Le détail et l'historique sont dans `git`, sans autorité (CLAUDE.md, en-tête).
> Mis à jour le 2026-10-03.

## 0. Reprise — à lire en premier, à tenir à jour

> Ce tableau est le fil du travail. Une action commencée passe à « en cours » ; une action
> finie porte sa mesure et son commit. Corriger en place et committer l'état avec le travail.
> Avant de rendre la main : mettre à jour les défauts touchés et rendre `git status` propre.
> Relire les sections 2, 4 et 12 de `CLAUDE.md` avant de valider. Les décisions de la section 5
> reviennent à 👤.

**Point de départ.** Branche `refactor-corridors-mixins` ; première commande
`python scripts\preflight.py` → `PREFLIGHT=GO`.

**Validation du lot courant (2026-10-03, Windows 11, Python 3.14.7).** `PREFLIGHT=GO` ;
ruff propre ; oracle `1113 passed in 11.52s` ; unit `4836 passed, 5 skipped, 6 xfailed in
609.28s` ; UI `1281 passed, 12 skipped, 2 xfailed in 1301.62s` ; reste `347 passed,
2 skipped in 536.03s`. Gel PyInstaller 6.22.3 isolé : `[CERTUS] release checks PASSED`
pour le hub et les dix modules ; quatre relances supplémentaires de DESIGN et quatre de RE
sans alerte. CI [`release-windows` verte sur le commit de code `1efb4542`](https://github.com/nikonvr/CERTUS/actions/runs/37116870526)
(`[CERTUS] release checks PASSED` après le démarrage gelé) ; les CI des commits documentaires
ultérieurs sont en cours. D23 reste intermittent malgré le passage local du reste.

### Actions simples — état et ordre de finition

| priorité | action | difficulté | état / prochaine commande |
|---|---|---|---|
| 1 · R111 | Décaler le calcul automatique de Tikhonravov après le préchauffage DESIGN | simple, **fait** (`90f5adf1`) | Test rouge avant, puis `11 passed in 10.24s` ; gel et 8 relances verts ; CI de release verte sur `1efb4542`. |
| R112 | Réparer `scripts/check_compensation_gain.py` (ancien D57) | simple, **fait** (`4b02d23c`) | Échec reproduit (`ValueError: too many values to unpack`) ; le script termine maintenant avec code 0, écarte le cas non déposable à 420 nm et classe 15 longueurs d'onde valides. |
| 2 · R109 | Élaguer cet état et baliser la reprise pour Opus | simple, **fait** (`76949c5d`) | `check_docs.py` : 0 défaut ; `coherence_md.py` : 0 point ; `check_claude_md.py` : 0 contradiction. |
| 3 · R110 | Valider et publier le lot autorisé par 👤 (« go ! » le 2026-10-03) | simple, long, **fait ; CI documentaire en cours** | Quatre suites et gel local verts (chiffres ci-dessus) ; bundle complet vérifié ; branche poussée ; [PR #5](https://github.com/nikonvr/CERTUS/pull/5) ouverte vers `master`. Copie complète du dépôt dans `..\certus0310` vérifiée par `PREFLIGHT=GO` et `git status` propre. Release CI verte sur `1efb4542` ; `gh pr checks 5` pour les derniers commits documentaires. |

**Déjà fait dans ce lot :** R100 `48f6095e` (stderr, watchdog et artefact CI du gel ;
`17 passed`), R107 `4c41dba2` (un seul préchauffage RE ; `21 passed`), R108 `44e9eef2`
(un seul préchauffage DESIGN ; `5 passed`). R108 seul n'a pas suffi : DESIGN lançait encore
un calcul Numba en parallèle du préchauffage ; R111 le décale. Le gel CI est vert sur le
commit de code `1efb4542` : D77 est clos. Les commits suivants ne changent que `ETAT.md`.

### Pour Opus 5.5 — enquêtes complexes, commencer directement par la première applicable

**Départ en deux commandes dans `certus0310` :** `python scripts\preflight.py` (attendu :
`PREFLIGHT=GO`), puis `gh pr checks 5`. **Commencer D23 directement** : le gel CI du code
est vert. Si une CI documentaire ultérieure révèle une régression du gel, prendre D77
en priorité par l'artefact stderr/watchdog. Ne relire les autres sections que si l'enquête
le demande.

| ordre | difficulté / tâche | faits acquis → première action précise | fini quand |
|---|---|---|---|
| **1 · D23** | **complexe : arrêt natif Qt intermittent** | `tests/headless/` : `QThread: Destroyed while thread ... is still running` après `DeferredDelete` ; émetteur inconnu. Le 2026-10-03, arrêt natif à 22 % du reste des tests, puis deux passes réussies. **Reproduire** avec `QT_FORCE_STDERR_LOGGING=1` et pytest `-s`, tracer l'émetteur dans `tests/headless/conftest.py` et `tests/qt_lifecycle.py`, puis cibler la fixture ou le worker fautif. | Passes répétées du groupe touché sans arrêt natif ; cause et garde mesurées. Ne pas mêler l'arbitrage « Stop » d'INDEX IR (§5). |
| **2 · D75(1)** | **complexe : physique INDEX, lame absorbante** | `_calculate_RT_absorbing_sub_single` (`certus/physics/certus_tmm_single_layer.py`) prend `Re(n_sub)` à l'interface ; erreur de premier ordre jusqu'à `0,25 k`. **Comparer** au modèle indépendant `tests/oracle/tmm_reference.py::rt_plate_incoherent`, puis corriger l'interface et le test qui fige l'ancien résultat : `tests/unit/test_index_single_layer_kernels_match_the_oracle_plate.py`. | Oracle physique et tests INDEX verts ; identité bit à bit des modes non touchés (règle C1). Traiter séparément D75(2), NaN/inf sous `fastmath`. |
| **3 · D52/D67** | **complexe : reproductibilité Numba / METAL** | `python scripts\c1_diff.py . --froid-contre-chaud` : 220/5 505 tableaux diffèrent, max 424 ulp ; `fastmath=False` a donné 0/5 505 mais coûte 7–19 % selon le noyau. METAL diffère de quelques % au premier run (`certus/physics/gradient_metal.py`). **Mesurer l'effet sur le résultat d'optimisation et isoler le noyau METAL**, avec échauffement contrôlé. | Effet et coût documentés, proposition chiffrée pour 👤 ; ne pas basculer globalement `fastmath` sans sa décision (§5). |
| **Contingence D77, seulement si une nouvelle CI release échoue** | **complexe : régression du gel Windows** | Ancien symptôme : RE code 3 ; ancien gel local : `Numba workqueue ... Concurrent access`. R100 instrumente `.github/workflows/release-windows.yml` et `tools/release_checks.py`. **Lire d'abord l'artefact stderr/watchdog du job rouge**, puis isoler le premier appel fautif dans `CERTUS_RE.py`, `CERTUS_DESIGN.py` ou le noyau indiqué. | Un nouveau run `release-windows` vert sur le code en cause. |

Autres défauts : §4 ; arbitrages réservés à 👤 : §5 ; chantiers : §6. Pas d'étiquette `v*`
tant que le gel CI est rouge. Opus peut ignorer les sections 1–3 pour commencer D23.

## 1. Où en sont les programmes

| programme | état | prochaine action |
|---|---|---|
| **Calcul (STRAT)** | composant étalon : l'aléatoire ×2 (`r75x2`) à la fente de 2 nm. Fabricable avec les rampes de la configuration livrée ; sans rampes, 3 graines sur 7 trouvent des déposables. Toute la fabricabilité passe par le générateur ELITE | voir la section 6 |
| **Interface** | plan clos le 2026-09-08 : 12 critères de fin sur 13 atteints et mesurés, le treizième démontré inatteignable (`xfail` strict) | la revue visuelle et trois arbitrages de 👤 (section 5) ; la fuite des fenêtres (défaut D11) |
| **Qualité** | CI : calcul sous Linux, interface sous Windows ; tests isolés des préférences de 👤 ; dette de lint de 14 règles masquées (D25) | E402/I001, D11 et défauts de la section 4 |
| **Documentation** | règles dans `CLAUDE.md`, état ici ; anciens dossiers lisibles dans Git | tenir « un fait, un seul endroit » |
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

**Lire ces chiffres :**

- 🔴 **Les SEEL ne se comparent pas d'un composant à l'autre** : ils sont notés sur des
  domaines de largeur différente (section 7). Toute comparaison **à composant fixé** est valide.
- 🔴 **Un score seul ne départage rien.** À N = 150 tirages, la dispersion Monte-Carlo vaut
  σ ≈ 6 % ; deux runs à moins de ~8 % sont indiscernables. On compare des **classes
  d'équivalence SEEL**. Sur `r75x2`, σ ≈ 1,8 % mesuré en changeant le triplet de graines de
  consensus : un bruit emprunté à un autre composant ne vaut rien.
- Ces repères comprennent le **biais de fente** ; une mesure sans ce biais ne leur est pas comparable.
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
| `robustness_num_runs` | 300, décidé le 2026-08-13 : il commande la sensibilité du filtre de plantage, donc **quelles stratégies existent**. 🔴 Le mode d'exécution l'emporte sur le fichier (150 en `premium`), et la ligne `[MODE]` du journal le dit |
| `n_screen_runs` | 25 ; à 10, un seul plantage tue une stratégie **et** la perd comme parent |
| profondeurs par mode | `robustness_num_runs` 50 / 150 / 300, `n_screen_runs` 10 / 25 / 50, `dp_top_k` 20 / 40 / 100 pour fast / premium / deep ; `extreme` = `deep` avec une génération élargie |
| graine de référence | 42, avec `scan_wl_step` à 1,0 |
| grille des λ de contrôle | figée à 1 nm |
| `machine_sampling_dd` | 0, figé dans le noyau (ce n'est plus un réglage depuis le 2026-09-27) : pas grossier (~21 points par couche au lieu de 800), par choix de vitesse. Le modèle est donc optimiste sur les faux points tournants |
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

### Logiciel — décidé le 2026-09-27

- **CERTUS tourne toujours sur un poste à jour** : les bornes minimales de `pyproject.toml` ne comptent pas ; la CI ré-résout vers les dernières versions stables à chaque run (`uv sync --upgrade`), `uv.lock` n'est qu'un point de départ (`uv lock --upgrade`). Pas de pré-version : pydantic ≥ 2.13.4 stable, plus 2.14 bêta.
- **La non-reproductibilité est acceptée** : INDEX, RE et METAL_BILAYER ne rendent pas deux fois la même RMSE — leurs générateurs ne sont pas amorcés, et on ne les amorce pas. Mesuré le 2026-09-27 : INDEX de 0,002546 à 0,002691 sur dix exécutions, et 0,0067 (2,6 fois la référence) environ une fois sur huit ; RE 0,05 % ; METAL_BILAYER 1 %. La garde de convergence retient pour eux la meilleure de quatre exécutions au plus (`tests/regression/test_convergence_guard.py`).

### Licence et comportement par défaut — décidé le 2026-09-29

- **Le projet est publié sous GPL-3.0** : c'est ce que PyQt6 exige de l'exécutable gelé (R36).
- **Quatre changements du comportement par défaut de DESIGN, acceptés** (R29) : la porte de stagnation et les seuils de gain prédit du Needle sont ceux réglés sur la fenêtre ; la phase globale est plafonnée quand la croissance topologique est cochée ; les graphiques prennent le fond du thème compact ; le substrat complexe est lu en oblique.
- **La sauvegarde des commits locaux** est un bundle Git hors dépôt, à actualiser après chaque lot non poussé ; pousser requiert ton ordre.

### Publication — décidé le 2026-09-30

- **Rien à cacher côté public** (« je n'ai aucune crainte de tout mettre en espace public, c'est mon choix ») : l'historique n'est pas purgé — ni le nom porté par les métadonnées de 44 classeurs anciens, ni l'adresse personnelle de quatre commits — et `git filter-repo` n'est pas au programme.
- **Les œuvres de tiers restent à leurs auteurs** : la GPL-3.0 ne les couvre pas (le texte de thèse de l'historique, les PDF d'articles). Elles vont dans les avis de tiers, pas dans une purge.

### Interface — décidé le 2026-09-28

- **INDEX : les réglages d'absorption du substrat ne s'affichent que pour le silicium**, le seul
  substrat dont le calcul lit l'absorption ; pour tous les autres, le worker force k = 0 (D43).

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
(`git show 7b08dc8:docs/archives/DEFAUTS_OUVERTS.md`).

**Ils faussent un résultat ou trompent l'utilisateur**

| # | défaut | piste |
|---|---|---|
| D2 | La porte de plantage juge au **pire des trois niveaux de bruit** (0,5× / 1× / 2×) : `crash_rate` est ce maximum, et le taux au bruit réel n'est porté nulle part | exposer le taux au bruit nominal |
| D4 | Une stratégie bâtie sur des couches « forcées » (Phase A en repli) est indiscernable d'une stratégie choisie (n° 37) | remonter `n_layers_forced` dans le résultat et le classement |
| D5 | `strategy_id` n'est pas unique : 21 identifiants sur 79 portés par plusieurs stratégies (n° 51) | vérifier l'unicité avant tout appariement parente/enfant |
| D6 | Le consensus ignore `robustness_num_runs`, et `robustness_seed` dès que `consensus_seed_list` est renseignée (n° 18, 47) | exposer `consensus_num_runs` |
| D7 | Deux configurations rendent le même `RESULT` au bit alors qu'une bande diffère de 38 % (n° 15) | vérifier dans le code ce que `RESULT` agrège |
| D8 | `scripts/campagne_intervalles.py` forçait `search_resolution` à faux alors que 👤 en a fait un prérequis : les campagnes d'intervalles ont tourné sans recherche de fente (n° 49) | refaire les intervalles utiles avec la fente cherchée |
| D9 | Restreindre la plage de blocs vide la DP ; cause non établie (n° 54) | mesurer la recherche à plage complète |
| D10 | **L'ajustement Sellmeier 3 pôles est chaotique sur le saphir** : un ulp sur les données change le minimum atteint (RMSE de 0,00126 à 0,00208 sur 41 essais, 2026-09-26) ; deux machines rendent deux indices pour les mêmes données. SiO2 et BK7 sont stables | élargir le multistart ou reconditionner — change les résultats, décision de 👤 |
| D45 | **PHY-12** : le gradient analytique de DESIGN **avec pile arrière** divise par le nombre de points valides là où le coût divise par la somme des poids : il est trop grand d'un facteur Σw / nombre de points, le poids moyen sur les points des cibles. Mesuré le 2026-09-30 sur les vrais poids de DESIGN (`t.w` × poids en ln λ, nuls hors des cibles ; grille de 400 à 1 100 nm au pas de 5 nm) : facteur 1,271 pour une bande de 450 à 650 nm, 1,070 pour deux bandes, 1,939 avec des poids 1 et 3 ; exact (1,000) pour une cible qui couvre toute la grille, et **sans pile arrière dans tous les cas**. La valeur du coût est juste et la direction du gradient aussi ; ce qui manque est l'échelle : l'optimiseur reçoit un gradient qui n'est pas la dérivée du coût. Effet mesuré le 2026-09-30 sur L-BFGS-B (douze départs, huit couches, avec pile arrière) : mêmes coûts finaux, jusqu'à 25 % d'évaluations en plus (médianes 25 contre 20 pour deux bandes de poids 1 et 3). `test_normal_cost_and_gradient_agree` normalise ses poids pour cette raison | corriger en `2/Σw` ne touche que la branche avec pile arrière (le chemin sans pile reste identique au bit) mais **change les résultats de ces optimisations** : décision de 👤 |
| D46 | Une couche opaque et épaisse (un métal de k = 7 au-delà de 10 µm, k = 3,5 au-delà de 20 µm) fait déborder le cos et le sin de la phase : les noyaux rendent (R, T) = (0, 0) au lieu de l'absorbeur semi-infini. Les enveloppes Python refusent une telle couche (`require_layers_below_overflow`) ; les noyaux appelés depuis du code compilé, dont le coût de DESIGN, répondent encore (0, 0). Une borne de la phase dans les noyaux a changé les bits de 1e-15 sur les chemins à substrat réel (mesuré, puis retirée) | décision de 👤 (C1) |
| D47 | DESIGN n'a pas de polarisation moyenne « Avg » : le tableau des cibles n'offre que s et p, et une configuration ancienne « Avg » se charge en s avec un avertissement (elle était calculée en p) | la calculer demande les deux ondes, chacune avec son gradient : décision de 👤 |
| D48 | L'épaisseur du substrat (1 mm par défaut, `DEFAULT_SUBSTRATE_THICKNESS_NM`) n'est un champ ni de DESIGN ni de STRAT : un substrat qui absorbe perd du flux selon cette épaisseur | exposer le champ : décision de 👤 (section 5) |

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
| D51 | INDEX garde sa propre lame de Beer-Lambert pour le substrat (`_calculate_RT_absorbing_sub_single`) : elle s'accorde avec le modèle commun `certus_substrate_absorption` à 1e-12 (k de 1e-7 à 1e-3, à 450 et 800 nm, testé), mais c'est une seconde formule à tenir à jour |
| D52 | Un noyau relu du cache Numba ne rend pas toujours les bits du même noyau compilé à l'instant. Mesuré le 2026-09-30 (`python scripts\c1_diff.py . --froid-contre-chaud`) : 220 tableaux sur 5 505 diffèrent, **tous dans les noyaux de gradient** (analytique, normal et oblique), aucun dans les spectres ni le coût ; le plus grand écart est de 424 ulp, 9,4e-14 en relatif (une entrée de gradient proche de zéro). Cause établie par deux contre-épreuves : un seul fil donne les mêmes 220 écarts (ce n'est pas l'ordonnancement) ; **`fastmath=True` remplacé par `False` dans les 117 noyaux : 0 écart sur 5 505** (c'est la réassociation). Couper `fastmath` coûterait, mesuré sur 48 couches × 2 001 longueurs d'onde à 4 fils : spectre normal +14 % (2,14 → 2,44 ms), coût de DESIGN +7 % (1,09 → 1,16 ms), gradient analytique +19 % (3,64 → 4,34 ms), spectre oblique +8 % (1,61 → 1,73 ms). **La croissance de STRAT aussi** (corpus `strat`, 1 703 tableaux) : 50 diffèrent, dans la croissance (9, 768 ulp au plus), la propagation par lot (11, 3,5e-12 en relatif) et le profil de T (30, 4 ulp au plus). Deux lancements d'une optimisation, l'un à froid, l'autre à chaud, peuvent donc partir de gradients qui diffèrent de 1e-13 ; l'effet sur le résultat d'une optimisation n'est pas mesuré. Le harnais C1 compare froid à froid (décision de 👤 : section 5) |
| D53 | `needle_scan_cached` (`certus/physics/certus_opt_needle.py`) documente qu'un point sans cible finie ne compte pas, et le noyau compilé ne le fait pas : `fastmath=True` laisse LLVM supposer des valeurs finies et replier `np.isfinite`, donc une cible NaN de poids positif empoisonne tous les coûts (le noyau rend le coût `nan` et le candidat 0) ; interprété (`NUMBA_DISABLE_JIT=1`), le point est sauté, comme documenté (coût 0,2025). Mesuré le 2026-09-30. **Exposition** : la cible de DESIGN vient de `prepare_targets_vectorized`, finie là où le poids est positif ; seule une entrée corrompue la rend NaN. Le test qui l'affirme est un `xfail` strict hors compilation coupée. Correctif sans effet sur un bit valide : nettoyer les cibles à l'appel (poids 0 et cible 0 où elle n'est pas finie), dans `_run_needle_cached_scan` |
| D54 | `simulate_growth_kernel` avec `adaptive_scan=True` **et** la grille fine (`smoothing_window > 1` ou `machine_sampling_dd > 0`) lit hors du balayage grossier : le re-échantillonnage suppose 64 points sur trois fois l'épaisseur, le balayage adaptatif en a moins sur une autre fenêtre. La `margin_missed` rendue diffère d'un lancement à l'autre (mesuré le 2026-09-30 avec le corpus élargi de `c1_diff` : 6 cas sur 87 combinaisons, jusqu'à 20 % d'écart ; l'arbre de 421ab8f comparé à lui-même ne se retrouvait pas). **Exposition : nulle aujourd'hui** — aucun appelant, test, script ni page ne passe `adaptive_scan` (`git grep`) : l'option est morte. Le corpus de `c1_diff` évite la combinaison, faute de quoi il ne prouverait plus rien. **Même famille, même exposition nulle** : `machine_sampling_dd > 0` avec `smoothing_window == 1` prend la grille fine et **saute la dérive photométrique** (affine et courbure), qui n'est appliquée que dans la branche grossière ou dans celle du lissage ; `machine_sampling_dd` reste à 0,0 pour tous les appelants (`certus_strat_batch.py`). **À décider par 👤** : supprimer `adaptive_scan` (elle alourdit le dimensionnement de la fenêtre du noyau) et garder `machine_sampling_dd` seulement si on lui rend la dérive, ou réparer les deux |
| D55 | Sur la grille fine de la machine, une couche **rejouée** de l'historique est lue avec un pas grossier de retard : son balayage grossier commence à 1/16 de l'épaisseur (le point 0 est le dernier de la couche du dessous), l'indice d'interpolation commence à 0. Mesuré le 2026-09-30 sur `_resample_on_machine_grid` : une rampe en profondeur revient décalée de d/16 (6,25 % de l'épaisseur, 3 nm sur 50) puis plate sur le dernier seizième ; la couche courante, elle, est lue à sa vraie profondeur. **Exposition** : seulement quand la grille fine est active (`smoothing_window > 1` ou `machine_sampling_dd > 0`) ; l'effet sur les extrema rejoués n'est pas mesuré. **À décider par 👤** (le modèle de la chaîne de lecture est figé depuis le 2026-08-08). Le test est un `xfail` strict : il passera quand la lecture sera corrigée |
| D56 | Les jeux de coefficients de Sellmeier de D263T eco (n° 2) et de B270i (n° 4) de `certus/core/certus_substrate_db.py` donnent n_d = 1,5201 et 1,5257 à 587,56 nm. De mémoire, et **sans l'avoir vérifié**, les fiches du fabricant disent 1,5230 pour les deux ; la provenance de ces deux jeux n'est écrite nulle part. Les trois autres verres retrouvent leur indice publié à 1e-4 (silice fondue 1,45846, N-BK7 1,51680, saphir ordinaire 1,76820), et le noyau de production calcule l'indice de ces coefficients à 1e-12 près. Un écart de 3e-3 sur l'indice du substrat déplace la réflexion d'une face nue d'environ 4e-4 (calcul, pas mesure). Le test épingle les deux valeurs comme **mesurées, non validées** (R64) : changer ces nombres doit être une décision, donc casser un test |

**Le code et les tests**

| # | défaut |
|---|---|
| D11 | **Une fenêtre de module fermée n'est pas détruite** : des lambdas et des `functools.partial` branchés sur les signaux de ses propres widgets la capturent, et la connexion les tient du côté C++ de PyQt, où le ramasse-miettes ne voit pas le cycle (`scripts/sonde_retenants_fenetre.py`, 2026-09-27 : `CertusREApp` retenue par quatre méthodes liées, cinq fermetures et deux attributs de `CertusToast` / `CertusToastStack`). **Sans effet en production** : le hub lance chaque module dans son propre processus (`QProcess`), et fermer la fenêtre finit le processus. Les tests détruisent désormais leurs fenêtres (R5). Coûterait dans tout processus qui construirait plusieurs fenêtres. Piste : `WA_DeleteOnClose` sur `CertusBaseApp`, à condition de retenir d'abord ses `QThread` encore actifs : sans cela, libérer la fenêtre libère un thread en cours (D23) |
| D23 | Isolation des tests. Le plantage intermittent de `tests/headless/` a sa cause établie (2026-09-26) : un `QThread` reçoit un `DeferredDelete` pendant qu'il tourne, et Qt s'arrête sur « QThread: Destroyed while thread … is still running » ; l'émetteur n'est pas identifié. La fixture `headless_lifecycle` joint les threads Qt et Python avant de livrer les destructions différées, avec un délai de 180 s (R1). Restent : rien ne protège `sys.modules` ; un arrêt natif `0xC0000005` du worker Qt, 2 fois sur 120 lancements (le harnais d'interface réessaie) ; les raffinements qui suivent PGLOBAL dans l'étage IR d'INDEX ne lisent pas l'arrêt (section 5) ; un échec d'interface non identifié, une passe sur cinq du groupe INDEX le 2026-09-28 ; le 2026-10-03, une première passe du reste de `tests/` s'est arrêtée sur un accès mémoire natif pendant `headless` (22 %), puis deux passes ont réussi (`347 passed, 2 skipped`, la dernière en 536.03 s). Le défaut intermittent n'est pas clos. |
| D24 | Code mort : l'audit (`tools/dead_symbol_audit.py`) cherche ses candidats à la racine, dans `certus_physics` et dans `certus/metal`, et n'en trouve aucun, liste blanche vide. Le reste de `certus/` n'est pas dans son périmètre : il ne voit pas ce qui y meurt |
| D25 | Dette de lint masquée par `extend-ignore` : **14 règles** (31 au départ de S5.5) et 1 464 violations à la mesure du plan (3 455 au départ) ; plus aucun import étoile, et les noms indéfinis (F821, F822) sont à zéro. F401 : 629 signalements, 590 hors tests gardés exprès pour la plupart (R9) ; restent surtout E402 (548) et les confusables RUF001 à RUF003 (188, des µ, × et – voulus). Le détail est en R69. Le cliquet `tests/oracle/test_lint_debt_ratchet.py` nomme les règles restantes : aucune ne peut entrer, et une règle sortie doit quitter sa liste. RUF022 et RUF023 (trier `__all__`, `__slots__`) restent ignorées à dessein |
| D26 | Inversions de couches, comptées le 2026-08-19 : `utils → ui` (11), `core → workers` (10), cycle `physics ↔ core` (23 et 29 imports). Mesuré le 2026-09-29, module par module dans un interpréteur neuf : 72 des 73 modules de `certus/core`, `certus/physics` et `certus/domain` se chargent sans Qt, et tous ensemble n'en chargent aucun (garde-fou `test_computation_imports_no_qt`) ; le dernier, `certus.physics.gradient_analytic`, ne s'importe pas seul (cycle avec `gradient_utils`) |
| D40 | METAL BILAYER : l'analyse de faisceau minimise la MSE de réflectance seule, l'optimisation globale y ajoute une pénalité de lissage — deux objectifs, dont les RMSE ne se comparent pas |
| D41 | INDEX, INDEX SPLINE, RE, METAL et DESIGN arrêtent leurs workers dans leur propre `closeEvent` avant d'appeler celui de base : la question « un calcul tourne, fermer quand même ? » ne peut pas s'y poser. La leur donner, c'est demander avant d'arrêter, comme STRAT — un changement de comportement à la fermeture |
| D42 | Neuf modules de bibliothèque appellent `create_module_environment(__file__)` à l'import : chacun reconfigure le journal CERTUS, dont la destination dépend alors de l'ordre des imports ; leur `script_dir`, leur propre dossier, ne sert presque jamais. L'insertion dans `sys.path` (R21) et le fil de préchauffage (R24) sont corrigés |
| D50 | Le dossier gelé (`dist/CERTUS_HUB/`, 443 Mo, mesuré le 2026-09-30) embarque les bibliothèques de développement que tirent pandas et Numba (IPython, pytest, hypothesis, coverage, astroid…) ; `loky` ne marche pas gelé (repli sur des fils) ; Numba gelé n'a qu'un fil (`workqueue`), par conception ; le multigraine reste refusé dans l'exécutable gelé, le message le dit. Le job `release-windows` l'a construit et démarré sur un poste neuf le 2026-09-30 (R42) |
| D58 | `certus/utils/certus_reset_framework.py` (le bouton de remise à zéro) : la feuille de style est une chaîne ordinaire, pas un f-string, donc `font-size: {Typography.BODY_LG}pt;` est écrit tel quel et Qt ignore la déclaration : le bouton garde la police par défaut au lieu de celle que son auteur voulait. Observé le 2026-10-01 en cherchant les `color: white` ; **non changé** : le réparer change l'aspect d'un bouton, et c'est au propriétaire de dire quelle taille il veut |
| D65 | `_update_data_table` (`certus/ui/certus_index_ui_export.py`) lit encore `n_fit_R_only` (six fois), la colonne que D62 a fait retirer du tracé : aucune sortie d'optimiseur ne l'écrit (la stratégie IR n'écrit que `n_fit_T_only` / `k_fit_T_only`, `delta_n`, `delta_k`). Branches mortes du même genre ; **non changé** : le retrait est une décision de 👤, comme D62 |
| D66 | La légende de gauche du tracé n / k d'INDEX (`_update_nk_plot`) est créée par `addLegend` APRÈS le tracé des courbes n : pyqtgraph ne liste que les courbes ajoutées après elle, donc elle est vide au premier tracé d'une fenêtre et remplie aux suivants (la légende de k, construite à la main, est complète). Vu en écrivant le test du tracé (R73) ; **non changé** : créer la légende avant les courbes change l'aspect du premier tracé |
| D67 | L'analyse du faisceau METAL n'est pas reproductible bit à bit d'une exécution à la suivante dans le même processus : la première exécution d'une configuration donne un MSE final qui diffère de quelques pour cent de celui des suivantes (noyau de gradient `parallel=True, fastmath=True` de `certus/physics/gradient_metal.py`, dans la ligne de D52). Vu en comparant `run` à HEAD (R73) : le harnais fait un tour d'échauffement de chaque côté ; **non changé** : ce sont les réglages `fastmath` et parallèle que D52 laisse à 👤 |
| D68 | Deux conséquences de R74 que 👤 peut défaire ou compléter. **(1)** Le hub ne lance plus l'échauffement JIT : il ne calcule rien, et ce fil de fond lui faisait charger numba, scipy et la physique. Sur un cache Numba vide (première installation), le premier module lancé compile donc seul ses noyaux, sans que le hub l'ait amorcé ; chaque module garde son propre échauffement. Revenir en arrière : retirer `jit_warmup=False` de l'appel du hub (le test de R74 le dira). Une voie qui garde le hub léger et amorce le cache : un processus fils à basse priorité lancé après l'affichage du hub — **non fait**, c'est un choix de conception. **(2)** La physique lit le silicium (`SI_*`, feuille `Si-substrate` de `indices.xlsx`) À L'IMPORT, par pandas et openpyxl (mesuré sur la fenêtre DESIGN, machine chargée : 0,53 s pour `materials_data`, dont 0,42 s d'import d'openpyxl) ; les rendre paresseux demande que les tableaux existent avant la première compilation de `get_nk_si` (numba les fige), donc toucher le chargement de la physique — **non fait** |
| D69 | Deux définitions d'indicateurs ont changé en route, et 👤 doit le savoir. **(1)** « Couverture des noyaux, compilation coupée » : le plan la mesurait par `oracle` + `core` (base 45,9 %, cible ≥ 70 %) ; elle se mesure maintenant par ces deux répertoires, `property` et les tests de `unit` marqués `kernels` (R78 : 74,0 %). La base de l'audit reste celle de l'ancienne définition ; avec l'ancienne, l'indicateur serait à 46,0 % le 2026-10-01 (non atteint). Je tiens la nouvelle pour la bonne (les tests des noyaux de STRAT ont été écrits pour cela), mais c'est un changement de critère. **(2)** « Modules à moins de 15 % de couverture » (13, cible ≤ 8) : `metrics.py` prend déjà la meilleure couverture de chaque fichier parmi les JSON donnés ; remesuré le 2026-10-01 avec la mesure de toutes les suites (1b67dd95) et celle des noyaux (f94523a5) : **6 modules** (R87), cible atteinte |
| D70 | `check_extrema_proximity` (`certus_strat_math.py`) documente une zone interdite de **3 largeurs avant** un point tournant et de **1 largeur après** (sa docstring, le commentaire de `certus_strat_growth.py`) ; le code en refuse **2 largeurs avant et une demi-largeur après**, quelle que soit la largeur (mesuré pour 2, 5 et 10 nm, au premier et au second point tournant, contre l'oracle TMM indépendant) : il échantillonne T en d − w, d, d + w et d + 3w et compare le signe de trois pentes centrées en d − w/2, d + w/2 et d + 2w. L'asymétrie est de 4 pour 1, non de 3 pour 1. Un arrêt exactement une demi-largeur avant le point tournant passe aussi (pente exactement nulle). **Non changé** : le comportement est épinglé par un test (R80). C'est à 👤 de décider si le code ou la documentation doit bouger : changer le code change les arrêts que STRAT accepte, donc ses résultats |
| D71 | Deux observations sur Tauc-Lorentz-Urbach (`gradient_analytic.py`), non corrigées. **(1)** k est calculé par √((|ε| − ε₁)/2), qui s'annule par différence là où ε₂ ≪ ε₁ : sous ε₂ ≈ 1e-7 (loin sous le gap) k revient à 0 ou à quelques pour mille près, soit moins de 2e-7 sur 2nk ; une différence finie de n ou de k y est fausse, la dérivée analytique est juste ; sans effet sur un empilement. **(2)** ε₂ saute en E = Eg : la queue d'Urbach, utilisée pour E ≤ Eg, vaut 1,9e-4 pour l'oxyde de l'exemple, l'absorption de bande (E > Eg) vaut 0 et monte jusqu'à l'ancre de la queue, posée à Eg + 0,01 eV ; le saut est de 2e-5 du maximum, sans effet sur un empilement, mais le modèle n'est pas continu là pour un ajustement qui passerait au bord du gap |
| D72 | **Taille du gel (S7.2) : objectif ≤ 300 Mo non atteint.** Reconstruit le 2026-10-03 avec PyInstaller 6.22.3 dans un dossier temporaire, `PATH` assaini : 447 675 580 octets, 7 307 fichiers ; hub et dix modules passent `release_checks.py --check-frozen --check-frozen-run`. Aucun `excludes` n'a été essayé (`certus_hub.spec` a `excludes=[]`). L'application (`certus/`, `certus_physics/`, les `CERTUS_*.py`) n'importe aucune des bibliothèques de développement que le gel embarque (D50) — balayage AST : IPython, pytest, hypothesis, coverage, astroid, pylint, black, mypy, ruff, sphinx, jedi, parso, notebook, jupyter, ipykernel : 0 import ; setuptools, pip, wheel, tkinter aussi, à essayer avec prudence (numba en a un usage optionnel). Étape suivante : exclure les douze premières dans une copie et mesurer taille et démarrage de tous les modules ; inspecter plugins Qt et sous-modules de scipy avant d'autres exclusions |
| D73 | **`calculate_level_margins_to_extrema` a une zone aveugle autour de chaque point tournant.** De 1,25 nm avant à 1,25 nm après un point tournant (une demi-maille de la grille de 64 points sur trois épaisseurs ; 2,8 nm au quart d'onde de l'exemple), les marges rendues sont (`MARGIN_NONE`, 0,28) : le point tournant qui est sous l'arrêt n'est le voisin de personne (la boucle arrière n'y voit aucun retournement, la boucle avant commence après lui) et 0,28 est l'écart à l'AUTRE sorte d'extremum. `check_level_margin_batch` **admet donc l'arrêt pour tout seuil sous 0,28**, c'est-à-dire le pire arrêt qui soit : le niveau est celui de l'extremum et la moitié des tirages de bruit placent la cible au-delà. Hors de la zone la marge est quadratique, comme la docstring le dit. **Portée** : le mode OPT-IN `phase_a_level_margin_factor > 0` ; le défaut n'appelle pas cette fonction, et le chemin par défaut appelle `check_extrema_proximity` avec des matrices nulles, qui ne filtre rien (c'est dit dans `certus_strat_service.py`, « INERT » : un choix de 👤, « gating binaire »). **Non corrigé** : c'est de la physique d'un mode que 👤 a conçu ; un test `xfail(strict)` décrit le comportement voulu (une marge nulle d'un côté au moins pour un arrêt sur un point tournant) et un second mesure la zone. Correction possible, trois lignes : si la pente change de signe au point d'arrêt (les deux signes non nuls et opposés), les deux marges valent 0 |
| D74 | **`LBFGSBSearcher.search` appelle une fonction privée de scipy, et une signature qui change n'est pas rattrapée.** Avec un gradient et sans rappel, la recherche appelle `scipy.optimize._lbfgsb.setulb` et suit à la main les codes de tâche (3, 1, 5) et le compteur `isave[29]` : la signature de cette fonction a déjà changé une fois (L-BFGS-B réécrit en C, l'argument `ln_task`), et `search` rattrape `ValueError`, `RuntimeError` et `LinAlgError` mais **pas `TypeError`**, ce que lève une signature qui change. La CI installe les dernières versions à chaque passage : le jour où scipy change, la recherche lève au lieu de se rabattre sur `minimize`. **Non corrigé** : le test de R85 est la sentinelle (il échoue dès le premier passage de CI qui voit la nouvelle version, ce qui vaut mieux qu'un repli silencieux vers un chemin plus lent). Deux choix pour 👤 : garder la sentinelle telle quelle, ou rattraper `TypeError` et `AttributeError` pour se rabattre sur `minimize` (une ligne ; il faudrait alors que la sentinelle teste le repli et non plus l'existence de la fonction). **Observation, dite dans le test** : après un arrêt par le budget, la valeur rendue est celle du DERNIER point évalué (un essai de recherche linéaire), pas le meilleur itéré, et elle n'est pas monotone en le budget (4 évaluations : 5,7 ; 12 : 41,4 sur ce départ de Rosenbrock) — `minimize` fait de même |
| D75 | **Deux points INDEX restent ouverts après la correction du verre dépoli (R96).** (1) Pour un film sur lame absorbante, `_calculate_RT_absorbing_sub_single` emploie la partie réelle de l’indice du substrat à l’interface, contrairement au modèle commun : sur 50 films, l’écart mesuré en R et T est du premier ordre, au plus 0,25 k du substrat. (2) Avec un indice de substrat NaN ou inf, les noyaux compilés rendent (0, 0), car `fastmath` replie le test `np.isfinite`. Le choix physique sur le verre dépoli est tranché et sa correction est dans R96. |
| D76 | **Deux défauts mineurs des objectifs METAL, décrits et non corrigés.** **(1) METAL SINGLE, analyse du faisceau** : `gradient_function_fixed_eM` est exactement le gradient de la partie données (2e-10 aux différences finies de l'erreur quadratique de l'oracle), mais l'objectif qu'il sert (`objective_function_fixed_eM`, par `_single_RTRback_mse`) ajoute une pénalité de lissage 1e-2 × (Σ (Δ²n)² + Σ (Δ²k)²) dont il ne donne pas la dérivée : écart relatif au gradient du coût complet **1,7e-3 à des nœuds lisses, 1,9e-2 à des nœuds rugueux**. Deux choix pour 👤 : ajouter la dérivée de la pénalité, ou ôter la pénalité de l'objectif du faisceau. **(2) METAL BILAYER, `_validate_bilayer_spline_state`** : après une réparation (nombre faux de nœuds internes, ou un nœud sur un bout), il rend des nœuds équidistants sur NUM_KNOTS points et, comme « nœuds internes », une équidistance sur NUM_KNOTS + 1 points (quatre valeurs pour cinq nœuds, pas les trois qui sont à l'intérieur des nœuds rendus) ; les deux appelants (`certus_metal_bilayer_app.py`, tracé et export) ne gardent que les nœuds, rien n'est faux à l'écran aujourd'hui. Correction possible : `np.linspace(min_l, max_l, expected_knot_count)[1:-1]`. Chacun a un `xfail(strict)` : `test_metal_single_objective_is_the_error_it_says.py`, `test_metal_bilayer_objective_is_the_error_it_says.py` |
| D80 | **Protection de la configuration modifiée incomplète.** DESIGN, FIELD, INDEX, STRAT et les deux METAL demandent avant fermeture (R102, R105). RE et INDEX SPLINE rendent encore `{}` depuis `_collect_config` : aucune modification n’est comparée, donc aucune question n’apparaît. Définir les champs qu’ils savent sauvegarder et relire avant de brancher la garde. |
| D82 | **Thème sombre : logo et mesure de contraste à terminer.** Les textes et états vides suivent désormais le thème (R102). Le logo foncé reste peu visible en thème sombre, constat visuel sans mesure ; le harnais ne résout pas encore une encre de palette sur fond hérité. |
| D84 | **Validation locale intermittente, partiellement instruite.** Sur une copie propre de `HEAD`, `test_uniform_weights_reproduce_the_unweighted_functional` avait rendu un écart de 5,55e-17 (Numba 0.68.0 installé alors pour 0.67.0 au verrou) ; un test du workflow échouait sur une modification locale aujourd'hui absente ; la limite du test de concurrence était dépassée sur une passe Windows. Le benchmark de croissance attendait deux valeurs quand le noyau en rend cinq : corrigé par R103 et rejoué avec `pytest-benchmark 5.3.0` dans un dossier temporaire (`1 passed in 1.46s`, puis `6 passed in 5.77s` pour le fichier). Le 2026-10-02, sur l'arbre courant avec Numba 0.67.0 : les deux tests unitaires ciblés passent (`2 passed in 6.21s`), le test de concurrence ciblé passe (`1 passed in 3.94s`), puis la suite unit entière passe (`4830 passed, 5 skipped, 6 xfailed in 972.14s`) et le reste de `tests/` passe (`347 passed, 2 skipped in 579.07s`). Ces passes ne prouvent pas que les écarts intermittents ont disparu. | Établir la cause de l'écart au bit s'il revient en suite complète. |

## 5. Ce qui attend une décision de 👤

Ces sujets demandent un jugement de physicien ou de propriétaire du produit. Les choix déjà faits figurent en section 3.

| sujet | ce qui est en jeu |
|---|---|
| **le dépôt dans Google Drive** | un dépôt git synchronisé par Drive est lent et exposé aux copies de conflit dans `.git` ; ce dossier est en plus partagé par deux PC sous deux chemins différents. Recommandé : un clone hors Drive par machine. Non fait : déplacer l'arbre de travail pendant qu'on y travaille n'est pas une opération sûre |
| **données Nb2O5 « Syrus »** | dans les feuilles `Nb2O5-Syrus` et `IR-Syrus-Nb2O5` de `example/database_index/indices.xlsx`, n tombe de 2,09 à 4,0 µm à 1,19 à 4,7 µm puis remonte à 1,78 à 5 µm, quand les feuilles H400 et H800 restent entre 2,07 et 2,13. Un creux de cette taille avec k ≤ 0,018 n'est pas physique |
| **défaut D10** | fiabiliser l'ajustement Sellmeier du saphir : **change des résultats de production** |
| **interface** | Revoir visuellement les onze fenêtres et choisir les teintes de marque, la bande des fichiers récents et les bornes des champs numériques. La branche locale `claude/charming-wright-43077a` contient des couleurs à évaluer avant intégration. |
| **Stop pendant l'étage IR d'INDEX** | interrompre aussi les raffinements qui suivent PGLOBAL, ou garder le résultat raffiné livré aujourd'hui (détail : D23) — change ce que voit l'utilisateur |
| **validation externe** | deux stratégies réellement déposées du dichroïque, avec leurs spectres mesurés. Le test est **ordinal** : STRAT doit les classer dans le bon ordre |
| **fichiers hors git** | `Selenium_Optical_Constants*.pdf` (œuvre d'un tiers) et `studies/selenium_bk7/` (recherche non publiée, dont des scripts sources) : ignorés désormais, donc dans aucun clone. **À sauvegarder à la main avant tout changement de machine**, ou à commiter si tu le décides |
| **poste de travail** | le venv `C:\envs\certus` (numba 0.66) est inutilisé depuis le passage au Python système : à supprimer si tu le confirmes |
| **deux fenêtres débranchées** | STRAT montre l’accueil générique alors que `certus_strat_welcome_ui.py` existe ; le moniteur d’indices d’INDEX SPLINE (`certus_index_spline_monitor_ui.py`) n’est plus appelé que par un test. Rebrancher ou retirer ces fenêtres ? Recommandé : les rebrancher. |
| **protection de `master` et Dependabot** | Décider si l’épinglage des actions par SHA devient obligatoire, si une relecture ou `release-windows` devient un contrôle requis (après D77), et quoi faire des PR Dependabot #1 à #4. |
| **avis de tiers** | Écrire `THIRD_PARTY_NOTICES` pour les éléments redistribués sous licence propre (icônes Lucide, données d’indices, textes tiers). |
| **le substrat qui absorbe (D48)** | Confirmer l’épaisseur par défaut de 1 mm, ou en faire un champ de DESIGN et STRAT ; elle décide de la perte de flux. |
| **D45 et D46** | **D45** : corriger le gradient avec pile arrière (`2/Σw`) change les résultats des optimisations avec pile arrière (le facteur mesuré va de 1,07 à 1,94 sur les cas de D45) ; **D46** : borner la phase dans les noyaux change les derniers bits (1e-15, mesuré) des chemins à substrat réel, pour un cas qu'aucun design courant n'atteint. Deux décisions distinctes ; la règle du chemin inactif au bit près (C1) demande ton accord pour les deux |
| **`fastmath` dans les noyaux de gradient et de croissance (D52)** | le garder (7 à 19 % plus rapide, bits différents entre un lancement à froid et un à chaud, 1e-13 en relatif au plus pour les gradients, 3,5e-12 pour la propagation de STRAT), ou le couper dans ces noyaux (+19 % sur le gradient, bits reproductibles ; la vitesse de STRAT non mesurée). Couper change les derniers bits de tout ce qui passe par ces noyaux : la règle du chemin inactif au bit près (C1) demande ton accord |
| **l'option `adaptive_scan` du noyau de croissance (D54)** | morte (personne ne la passe) et fausse avec la grille fine : la supprimer, ou la réparer ; tant que 👤 n'a pas tranché, le corpus de `c1_diff` évite la combinaison |
| **la lecture des couches rejouées sur la grille fine (D55)** | décalée d'un pas grossier (d/16) puis plate sur le dernier seizième : corriger change ce que voit la grille de la machine dès que `smoothing_window > 1` ; sans effet tant que le lissage vaut 1 |
| **la polarisation « Avg » (D47)** | la retirer du tableau des cibles de DESIGN, comme aujourd'hui, ou la calculer : les deux ondes, leur moyenne et leurs gradients |

## 6. Chantiers spécifiés, en attente

**Calcul** (détail : `git show 7b08dc8:docs/archives/REPRENDRE_ICI.md`) —
dimensionner K, le nombre de graines à lancer : p ≈ 3/7 pour trouver un déposable, 2/7 pour
atteindre le niveau 0,57 · balayer `tp_hysteresis_factor` à bruit fixé · compter le criblage et
l'héritage quand un étage deviendra suspect · porter le résultat de `r75x2` dans la vitrine,
avec sa condition dans la même phrase que le chiffre.

**Modèle physique** (détail : `git show 7b08dc8:docs/archives/TRAVAUX_A_VENIR.md`) :

| | sujet | état |
|---|---|---|
| 12.2 | modéliser le lissage de lecture | ouvert — surtout ne pas remonter le seuil |
| 12.3 | méconnaissance d'indice | spécifié : corridor de dispersion |
| 12.4 | grille d'échantillonnage à la cadence machine | ouvert, à faire avant 12.2 |
| 12.5 | quantification temporelle du déclenchement | ouvert |
| 12.6 | facteur de face arrière | en dernier, ou jamais |
| 12.7 | résolution du monochromateur | spécifié |

**Réserve** (détail : `git show 7b08dc8:docs/archives/RESERVE_A25_A27.md`) —
**A25** `sigma_rate` comme prédiction : la seule grandeur vérifiable de l'extérieur, contre les
±1 à 2 % que 👤 observe en salle · **A26** un bloc de santé de run (A27, le harnais C1, est fait : R45).

**Architecture** (détail : `git show 7b08dc8:docs/archives/PLAN_AMELIORATION.md`) —
reste un cycle à l'exécution (le cœur de STRAT), 20 arêtes montantes et les points chauds
de taille, nommés dans `tests/architecture_debt.json` ; l'hygiène des imports (D25).

**Lint à effet possible (D25).** F401 est traité pour les imports sans rôle ; restent
E402/I001 et les petites règles, un cas à la fois.

| règle | ce qui peut changer un comportement | démarche proposée |
|---|---|---|
| F401 | un import « inutilisé » peut être un ré-export (y compris dans un import sur plusieurs lignes, ou un nom déclaré par `__all__.extend`), un effet de bord (enregistrement, sous-module `import a.b`, configuration numba avant un `@njit`), ou servi par une façade `CertusFacadeModule` | **fait** par lots (R9) : un nom ne part que si l'import est au niveau du module, hors `try`, sans accès dynamique du module à ses globales, et si aucun fichier suivi, aucune façade, aucun test qui charge le fichier par son chemin ni aucun code lancé depuis une chaîne ne le prend ; le reste est listé, pas retiré |
| I001, E402 | l'ordre des imports compte : cycle `physics ↔ core`, `configure_numba_env()` avant tout `@njit`, `QT_QPA_PLATFORM` avant la première `QApplication` | réordonner seulement les fichiers sans import à effet, jamais les façades ni `certus_core` ; E402 cas par cas |
| E741 | renommer `l`, `O`, `I` : sans effet, mais 89 cas dont des noyaux numba | après recompilation, `python scripts\c1_diff.py HEAD` (C1) |
| RUF046, RUF005, RUF015 | équivalences qui dépendent du type : `round(x)` d'un scalaire numpy rend bien un `int`, mais `round(x, n)` et `np.round(x)` rendent un `float64` (mesuré, numpy 2.5.2) ; `a + b` et `[*a, *b]` diffèrent si `a` est un tableau numpy | cas par cas, avec le type réel de l'argument |
| UP040, UP042, UP046 | changent l'objet à l'exécution (`TypeAliasType`, sous-classe de `str`, génériques PEP 695) | restent ignorées (arbitrage du 2026-09-27) |

**Contrôles du chantier lint** : ruff ; oracle ; unit ; `tests/ui/` ; le reste de `tests/` ; trois
photos avant/après — l'espace de noms final de chaque module touché (`scripts/lint_ns_snapshot.py`),
les modules que charge chaque script d'entrée une fois son fil de préchauffage fini, et les noms
que sert chaque façade `CertusFacadeModule`. Un nom qui disparaît ne doit être ni utilisé ni
demandé par personne.
**Ordre** : E402/I001, puis les petites règles.

**Prédictibilité** (détail : `git show 7b08dc8:docs/archives/CHANTIER_PREDICTIBILITE.md`) —
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
