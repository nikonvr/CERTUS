# CERTUS — état du projet

> Ce document porte l'**état** : où en sont les programmes, les repères mesurés, ce que 👤 a
> décidé, les défauts ouverts et les chantiers. Les **règles** sont dans
> [`CLAUDE.md`](../CLAUDE.md). Il se tient **en place** : un fait change, on corrige sa ligne,
> on ne raconte pas la correction (`git log` s'en charge). Toute mesure porte sa date.
> Le détail et l'historique sont dans [`archives/`](archives/), sans autorité.
> Mis à jour le 2026-09-28.

## 0. Reprise — à lire en premier, à tenir à jour

> **Consigne à l'IA qui reprend.** Ce tableau est le fil du travail. Tiens-le à jour **au fur et
> à mesure**, pas en fin de session : une action commencée passe à « en cours », une action
> finie à « faite » avec son commit et sa mesure (la sortie de la commande : CLAUDE.md,
> interdit 9) ; toute action ou découverte nouvelle ajoute une ligne. Corrige en place, sans
> récit, et commite chaque mise à jour avec le travail qu'elle décrit. Avant de rendre la main :
> ce tableau, les lignes D touchées, `git status` propre, `git push`. Relis les sections 2, 4 et
> 12 de CLAUDE.md avant de valider quoi que ce soit ou de relayer le rapport d'un autre agent.
> Les décisions de la section 5 reviennent à 👤 : **ne les tranche pas à sa place**.

**Point de départ.** Branche `refactor-corridors-mixins`. Première commande : `python scripts\preflight.py` → `PREFLIGHT=GO`.
Dernière validation locale complète, sur 2c7929f (Windows 11, le 2026-09-28) : ruff propre · oracle 569 passed · unit 2 484 passed, aucun saut · `tests/ui/` 790 passed, 10 skipped, 3 xfailed · le reste de `tests/` 337 passed, 2 skipped · **0 failed**. La garde de convergence retient la meilleure de quatre exécutions pour les modules non reproductibles (section 3).

| # | action | état | où | fini quand |
|---|---|---|---|---|
| R1 | juger la fixture headless (D23) | **faite** : trois runs CI verts de suite sur les deux jobs, dix passes locales sur dix de `tests/headless/` | `tests/headless/conftest.py` | 2026-09-26 |
| R2 | la CI installe exactement `uv.lock` (D32) | **remplacée** : la CI éprouve les dernières versions stables à chaque run (section 3, Logiciel) | `.github/workflows/tests.yml` | 2026-09-27 |
| R3 | retenir un `EvalWorker` remplacé jusqu'à son `finished` natif (D33) | **faite** : `_retain_until_finished` ; 5 tests, dont 4 échouent sur le code d'avant | `spectrum_eval_start_worker` | 2026-09-26 |
| R4 | lint sans effet à l'exécution, 13 familles | **faite**, à la main, jamais `ruff --fix` : `extend-ignore` de 48 à 35 règles | D25 | 2026-09-27 |
| R5 | les tests détruisent les fenêtres qu'ils construisent (D11) | **faite** : `tests/ui/` en un seul tenant, 20 min au lieu de 29 sur ce poste | `tests/qt_lifecycle.py`, `tests/ui/conftest.py` | 2026-09-27 |
| R6 | abandon quand METAL et headless partagent un processus (D23) | **faite** : aucun test ne crée sa `QApplication`, un gardien l'impose ; 3 passes sur 3 | `tests/unit/test_tests_borrow_the_session_qapplication.py` | 2026-09-27 |
| R7 | faux échecs à cache numba froid | **reviennent dans un arbre neuf** : 0 failed sur deux passes à cache vide le 2026-09-27, mais 3 failed à la première passe d'un worktree neuf le même jour, puis 0 aux huit suivantes. La consigne de relance est revenue dans CLAUDE.md, section 2 | — | 2026-09-28 |
| R8 | lint F811, 85 cas | **faite** : `extend-ignore` à 34 règles ; espaces de noms comparés avant et après | D25 | 2026-09-27 |
| R9 | lint à effet possible : imports (F403, F405, F401, E402, I001) puis petites règles | **étape 1 faite** : plus aucun `import *` (FIELD bab804d, DESIGN f04ab60 et 2dde2db, STRAT 23e4d50, INDEX SPLINE 1c71e7f), chaque nom importé de son origine ; F403, F405 et B019 sortent d'`extend-ignore` (a1d07f2, 3cbd15d). **Étape 2 (F401) faite pour ce qui se retire sans risque** : physique, METAL, utils, domaine, scripts (1aec9b3, 147 noms), cœur, workers, spline (46eed45, 1 604), interface (92d6dab, 2 295), scripts d'entrée (cc6bcd0, 286), alias oubliés (50965e2, 81). puis cœur STRAT, une fois ses injections par `globals()` retirées (e1216ce, 84). Restent 533 signalements gardés exprès : ré-exports réels, imports de sous-module, imports portant un commentaire, et `certus_ui`, qui sert ses ré-exports par un `__getattr__` de module. Contrôles en section 6 | section 6 | 2026-09-29 |
| R10 | un dossier de préférences laissé par chaque session pytest | **faite** | `tests/conftest.py` | 2026-09-26 |
| R11 | les tests écrivaient les réglages de 👤 dans le registre | **faite** : `certus_settings` ; `HKCU\Software\CERTUS` identique octet pour octet après une passe complète | `certus/utils/certus_qsettings.py` | 2026-09-27 |
| R12 | supprimer l'obsolète et le débranché | **faite** : 209 fichiers supprimés (27 640 lignes) depuis e3ce77d, 29 400 lignes de moins en net au 2026-09-28 — scripts de campagnes closes ou cassés, outils de refactorisation à usage unique, fichiers morts de la racine, prototype Rust, configurations sans effet (`Makefile`, `CODEOWNERS`, pre-commit qui lançait `ruff --fix`, mypy), échafaudages, copies en double, validation STRAT par schéma JSON qui ne tournait jamais, fichier d'état de réinitialisation que rien ne lisait. `requirements.lock` réexporté (32 paquets en retard) et tenu par un garde-fou ; plus de système de construction (D27) | `git log` des 2026-09-27 et 28 | 2026-09-28 |
| R13 | des tests qui ne pouvaient pas échouer | **faite** : les `check()` de quatre suites de physique n'échouaient pas sous pytest (tous forcés en échec : « 30 passed » avant, « 29 failed » après) ; 31 imports gardés changeaient un import cassé en sauts (« 1 passed, 56 skipped » avant, erreur de collecte après) ; un fichier suivi absent échoue au lieu de sauter ; une vingtaine de tests vides ou jamais collectés retirés | `tests/unit/conftest.py` | 2026-09-28 |
| R14 | D1 et D3 : réglages STRAT inertes, journal du classement muet | **faite** (fusion 668755a) : cinq réglages retirés, aucun ne pouvait être branché au bit près ; une ligne `[MODE]` dit quels budgets du fichier le mode remplace ; le classement écrit dans le journal du pipeline. Chaque test ajouté échoue sur le code d'avant | `tests/unit/test_strat_disconnected_settings.py` | 2026-09-27 |
| R15 | D24 : code mort | **faite** : symboles de la liste blanche, sept modules entiers, constantes et accesseurs du cœur, `SplineCache`, puis un balayage de tout `certus/` (audit élargi, nom nu cherché dans tous les `.py` suivis) : interface INDEX SPLINE (446 lignes), STRAT, DESIGN (onze proxies qui visaient des méthodes inexistantes), FIELD, METAL. L'audit de la CI couvre `certus/metal`, liste blanche vide | `tools/dead_symbol_audit.py` | 2026-09-28 |
| R17 | FIELD : `CertusBaseApp` passait avant les mixins et masquait toutes leurs spécialisations | **faite** (a5269eb) : « Enregistrer la configuration » écrivait `{}`, « Charger » ne faisait rien, « Détacher le tracé » levait AttributeError ; les mixins passent devant, la configuration passe par les crochets communs. Test : 4 failed avant, 4 passed après ; cliquet d'ergonomie FIELD vert | `certus/ui/certus_field_ui.py` | 2026-09-28 |
| R18 | la garde « fermer pendant un run » ne voyait aucun run | **faite** (923ef1b) : `register_worker` n'avait aucun appelant, la garde comptait toujours zéro ; STRAT et FIELD enregistrent désormais leurs workers. Test avec un vrai worker FIELD : 4 failed avant, 4 passed après | `certus/ui/certus_base_app.py` | 2026-09-28 |
| R16 | D30 : les monolithes METAL de la racine | **faite** (fusion 5ba0a44) : `CERTUS_METAL_SINGLE.py` et `CERTUS_METAL_BILAYER.py` passent de 2 728 et 2 815 lignes à 145 et 153 ; le calcul vit dans des modules sans Qt de `certus/metal/`, la fenêtre et les workers à côté. Empreintes `float.hex` des fonctions de calcul identiques avant et après ; quatre méthodes dupliquées remontées dans `MetalBaseApp`. En chemin, l'analyse de faisceau BILAYER corrigée : son gradient découpait `num_knots + 1` points par famille, chaque pas levait et le faisceau ne gardait que l'optimum, écart nul (exemple : 20 pas en erreur et 1 solution avant, 0 et 28 après) | `certus/metal/` | 2026-09-28 |
| R19 | des tests qui plantaient ou sautaient selon leur voisinage | **faite** : une fenêtre FIELD laissée vivante faisait mourir le processus à l'arrêt (12d68c6) ; tout fichier de test qui construit une fenêtre CERTUS la détruit, un gardien l'impose (c32f461) ; neuf `importorskip` sur du code du projet, dont deux qui sautaient lancés seuls, deviennent des imports, un gardien l'impose (2c8b48c) | `tests/unit/test_tests_destroy_the_windows_they_build.py`, `test_first_party_modules_are_never_skipped.py` | 2026-09-28 |
| R20 | des actions de l'interface levaient NameError depuis le découpage de juin | **faite**, révélée par R9 : DESIGN — les exports de rapport (10ef53a) et un dossier de travail `certus/ui` au lieu de la racine (f04ab60) ; STRAT — détacher la table, charger des stratégies externes, le mode non monotone « reject » (d33981a). Chaque test échoue sur le code d'avant | `tests/unit/test_design_*`, `test_strat_ui_actions_find_their_names.py` | 2026-09-28 |
| R21 | les modules de `certus/` mettaient leur dossier dans `sys.path` | **faite** (599b9ee) : 102 modules du paquet importables une seconde fois sous leur nom nu ; deux tests en vivaient | `bootstrap_app` | 2026-09-28 |
| R22 | INDEX : tableau du saphir introuvable depuis le 2026-05-27 ; réglages d'absorption affichés pour tous les substrats | **faite** : chemin rétabli (d063e49) ; D43 tranché par 👤, réglages montrés pour le silicium seul (695b807), import d'un fichier k inatteignable retiré (39ebf52). Le calcul ne change pas | `certus_index_ui_events.py` | 2026-09-28 |
| R23 | code mort et doublons révélés par R9 | **faite** : `certus_design_common` (8c5d7a7), quatre mixins INDEX SPLINE vides (320f94a), `_plot_spectrum_raw_scatter` défini trois fois (4bf7133), `CertusWindowSpyMixin` deux fois (f0105a2), vingt `import *` commentés (6c72536) | — | 2026-09-28 |
| R24 | un fil de préchauffage numba par module qui s'amorçait, lancé pendant les imports | **faite** : un seul par processus (ec66ec7), et lancé par `init_certus_app` une fois les imports de l'application faits (69d1f67) ; il interbloquait le système d'import (CI : `_DeadlockError` sur `scipy.linalg.cython_lapack` dans un run INDEX) | `start_jit_warmup` | 2026-09-29 |
| R25 | les tests INDEX sortaient une fois sur trois avec le code 1 (« lost sys.stderr ») | **faite** (97857ec) : `test_suite_ui_instantiation` laissait vivre huit fenêtres jusqu'à la sortie ; le gardien des fenêtres voit désormais celles construites par `getattr`. 5 sorties en erreur sur 18 avant, 0 sur 12 après | `tests/integration/test_suite_ui_instantiation.py` | 2026-09-29 |
| R26 | trois imports étoile déguisés (D44) : des modules recopiaient d'autres modules entiers dans leurs globales | **faite** : `certus_strat_objectives` (110964e), `certus_strat_core`, qui re-exporte désormais 29 noms un à un (673acc5), la façade `certus_substrate_index.py` (a9e91f1) ; leurs imports inutiles partent ensuite (e1216ce) et le cœur STRAT se charge sans Qt | `certus/core/certus_strat_core.py` | 2026-09-29 |
| R27 | l'outil d'indice de substrat du hub ne s'ouvrait plus depuis le 2026-06-13 (`main()` remplacé par `pass`) | **faite** (a9e91f1) ; un test exécute désormais chacun des dix scripts du hub jusqu'à sa boucle d'événements (cfdf98b) | `tests/integration/test_hub_scripts_start_their_app.py` | 2026-09-29 |

## 1. Où en sont les programmes

| programme | état | prochaine action |
|---|---|---|
| **Calcul (STRAT)** | composant étalon : l'aléatoire ×2 (`r75x2`) à la fente de 2 nm. Fabricable avec les rampes de la configuration livrée ; sans rampes, 3 graines sur 7 trouvent des déposables. Toute la fabricabilité passe par le générateur ELITE | voir la section 6 |
| **Interface** | plan clos le 2026-09-08 : 12 critères de fin sur 13 atteints et mesurés, le treizième démontré inatteignable (`xfail` strict) | la revue visuelle et trois arbitrages de 👤 (section 5) ; la fuite des fenêtres (défaut D11) |
| **Qualité** | CI GitHub sur toutes les branches : job `pytest` sous Linux (oracle, unit, puis le reste de `tests/`), job `interface` sous Windows (`tests/ui/`), dernières versions stables à chaque run. `certus/` commenté en anglais, garde-fou ; les tests n'écrivent ni les préférences ni le registre de 👤 ; dette de lint de 31 règles, cliquet nominatif (D25) | R9 étape 2 (F401), puis D11 ; l'ordre des actions est le tableau de la section 0 |
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
([`archives/DEFAUTS_OUVERTS.md`](archives/DEFAUTS_OUVERTS.md)).

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
| D23 | Isolation des tests. Le plantage intermittent de `tests/headless/` a sa cause établie (2026-09-26) : un `QThread` reçoit un `DeferredDelete` pendant qu'il tourne, et Qt s'arrête sur « QThread: Destroyed while thread … is still running » ; l'émetteur n'est pas identifié. La fixture `headless_lifecycle` joint les threads Qt et Python avant de livrer les destructions différées, avec un délai de 180 s (R1). Restent : rien ne protège `sys.modules` ; un arrêt natif `0xC0000005` du worker Qt, 2 fois sur 120 lancements (le harnais d'interface réessaie) ; les raffinements qui suivent PGLOBAL dans l'étage IR d'INDEX ne lisent pas l'arrêt (section 5) ; un échec d'interface non identifié, une passe sur cinq du groupe INDEX le 2026-09-28 |
| D24 | Code mort : l'audit (`tools/dead_symbol_audit.py`) cherche ses candidats à la racine, dans `certus_physics` et dans `certus/metal`, et n'en trouve aucun, liste blanche vide. Le reste de `certus/` n'est pas dans son périmètre : il ne voit pas ce qui y meurt |
| D25 | Dette de lint masquée par `extend-ignore` : **31 règles** ; plus aucun import étoile, et les noms indéfinis (F821, F822) sont à zéro. F401 : 533 signalements, tous gardés exprès (R9) ; restent surtout E402 et I001. Le cliquet `tests/oracle/test_lint_debt_ratchet.py` nomme les règles restantes : aucune ne peut entrer, et une règle sortie doit quitter sa liste. RUF022 et RUF023 (trier `__all__`, `__slots__`) restent ignorées à dessein |
| D26 | Inversions de couches, comptées le 2026-08-19 : `utils → ui` (11), `core → workers` (10), cycle `physics ↔ core` (23 et 29 imports). Mesuré le 2026-09-29, module par module dans un interpréteur neuf : 72 des 73 modules de `certus/core`, `certus/physics` et `certus/domain` se chargent sans Qt, et tous ensemble n'en chargent aucun (garde-fou `test_computation_imports_no_qt`) ; le dernier, `certus.physics.gradient_analytic`, ne s'importe pas seul (cycle avec `gradient_utils`) |
| D40 | METAL BILAYER : l'analyse de faisceau minimise la MSE de réflectance seule, l'optimisation globale y ajoute une pénalité de lissage — deux objectifs, dont les RMSE ne se comparent pas |
| D41 | INDEX, INDEX SPLINE, RE, METAL et DESIGN arrêtent leurs workers dans leur propre `closeEvent` avant d'appeler celui de base : la question « un calcul tourne, fermer quand même ? » ne peut pas s'y poser. La leur donner, c'est demander avant d'arrêter, comme STRAT — un changement de comportement à la fermeture |
| D42 | Neuf modules de bibliothèque appellent `create_module_environment(__file__)` à l'import : chacun reconfigure le journal CERTUS, dont la destination dépend alors de l'ordre des imports ; leur `script_dir`, leur propre dossier, ne sert presque jamais. L'insertion dans `sys.path` (R21) et le fil de préchauffage (R24) sont corrigés |
| D38 | Des seuils de durée en secondes dans `tests/performance/` peuvent échouer quand le poste est chargé : un échec non identifié le 2026-09-27 au soir, trois agents faisant tourner leurs tests en même temps, puis 0 failed à la même révision |

## 5. Ce qui attend une décision de 👤

Ces sujets demandent un jugement de physicien ou de propriétaire du produit. Ce qui a pu
être tranché sans eux l'a été (section 5bis).

| sujet | ce qui est en jeu |
|---|---|
| **historique git public** | l'historique porte encore le texte intégral d'une thèse tierce (`reports/_zideluns_text.json`), les classeurs d'avant correctif avec un nom civil, et des fichiers `.vs/`. Purger = `git filter-repo` puis force-push : tous les hash changent, étiquette `depart-gemini` comprise. 📌 **Décision du 2026-09-26 : ne pas purger sans ton accord explicite** — l'acte est irréversible sur un dépôt public et casse tous les renvois ; la thèse est par ailleurs publiquement accessible, l'enjeu est sa rediffusion. Ce qui était évitable l'a été : le papier tiers et `studies/` sont désormais dans `.gitignore` |
| **le dépôt dans Google Drive** | un dépôt git synchronisé par Drive est lent et exposé aux copies de conflit dans `.git` ; ce dossier est en plus partagé par deux PC sous deux chemins différents. Recommandé : un clone hors Drive par machine. Non fait : déplacer l'arbre de travail pendant qu'on y travaille n'est pas une opération sûre |
| **données Nb2O5 « Syrus »** | dans les feuilles `Nb2O5-Syrus` et `IR-Syrus-Nb2O5` de `example/database_index/indices.xlsx`, n tombe de 2,09 à 4,0 µm à 1,19 à 4,7 µm puis remonte à 1,78 à 5 µm, quand les feuilles H400 et H800 restent entre 2,07 et 2,13. Un creux de cette taille avec k ≤ 0,018 n'est pas physique |
| **défaut D10** | fiabiliser l'ajustement Sellmeier du saphir : **change des résultats de production** |
| **interface** | la revue visuelle des onze fenêtres, reportée le 2026-09-08 ; trois arbitrages : teintes de marque, bande des fichiers récents, bornes des champs numériques. 📌 La branche `claude/charming-wright-43077a` porte un travail **non porté** — lire les couleurs des badges, info-bulles et barre de progression dans le thème ; les trois fichiers portent encore des hexadécimaux en dur. L'appliquer **change le rendu**, donc cela attend la revue |
| **Stop pendant l'étage IR d'INDEX** | interrompre aussi les raffinements qui suivent PGLOBAL, ou garder le résultat raffiné livré aujourd'hui (détail : D23) — change ce que voit l'utilisateur |
| **validation externe** | deux stratégies réellement déposées du dichroïque, avec leurs spectres mesurés. Le test est **ordinal** : STRAT doit les classer dans le bon ordre |
| **fichiers hors git** | `Selenium_Optical_Constants*.pdf` (œuvre d'un tiers) et `studies/selenium_bk7/` (recherche non publiée, dont des scripts sources) : ignorés désormais, donc dans aucun clone. **À sauvegarder à la main avant tout changement de machine**, ou à commiter si tu le décides |
| **poste de travail** | le venv `C:\envs\certus` (numba 0.66) est inutilisé depuis le passage au Python système : à supprimer si tu le confirmes |
| **courriel dans l'historique** | quatre commits portent ton adresse personnelle ; les 1 344 autres l'adresse de non-réponse GitHub. C'est ton choix, pas un défaut — signalé une fois |
| **deux fenêtres débranchées** | trouvées par R9 : (1) STRAT montre l'accueil générique « Welcome to CERTUS » depuis 952acdc (2026-08-02, un commit « chore ») : un import explicite y a masqué l'accueil propre à STRAT, `certus/ui/certus_strat_welcome_ui.py` (état du système, capacités), que plus rien n'utilise ; (2) le moniteur d'indices en direct d'INDEX SPLINE, que Smart Init ouvrait, a été débranché par 06a1083 (2026-07-03, « Fix UI OBJ NameError ») : `certus/ui/certus_index_spline_monitor_ui.py` n'est plus appelé que par un test. Les deux ressemblent à des pertes accidentelles dans de gros commits : les rebrancher, ou les retirer ? Recommandé : les rebrancher |
| **la branche `master` sur GitHub** | `master`, branche par défaut du dépôt public, est toujours le premier commit d'avril (366 fichiers) ; tout le travail est sur `refactor-corridors-mixins`. Le workflow de sécurité, planifié chaque nuit sur `master`, y échoue chaque nuit : `pip-audit` trouve des vulnérabilités dans son verrou d'avril. Fusionner la branche dans `master`, ou changer de branche par défaut, publie : c'est ta décision |

## 5bis. Arbitrages rendus sans attendre

Le 2026-09-26, puis le 2026-09-27 sur délégation explicite de 👤 (« arbitre toi-même »).

| décidé | pourquoi |
|---|---|
| **les tests n'écrivent plus tes fichiers** | `CERTUS_CONFIG_DIR` isole les préférences, export automatique coupé ; les sous-processus héritent de la variable. Inerte sans elle : le chemin d'avant, au bit |
| **`test_config.json` retiré du suivi** | résidu d'un test de `ConfigManager`, jamais une donnée |
| **`C:\invalid\` supprimé** | résidu d'un test corrigé depuis ; deux fichiers de journal vides ou de diagnostic |
| **branche `local/sauvegarde-2026-09-25` supprimée** | redondante, **vérifié par empreinte** : les classeurs `indices.xlsx` et `reverse_sample.xlsx` y sont identiques à ceux de `HEAD`, et le travail d'interface identique à `be3b596`. Rien d'unique n'a été perdu |
| **le papier tiers et `studies/` sont ignorés** | le seul risque encore évitable sur un dépôt public est une **addition future** ; l'historique, lui, est la ligne ci-dessus |
| **l'interface se mesure sur Windows en CI** | sous Linux, 69 échecs et 12 erreurs, tous dus à l'absence de Segoe UI — l'audit refuse de mesurer des largeurs sur une machine qui n'existe pas. Job séparé, aucun test exclu |
| **le mode d'exécution fait foi sur le fichier** (D1) | c'était déjà le cas ; ce qui manquait, c'est de le dire : une ligne `[MODE]` nomme chaque budget remplacé, avec ses deux valeurs |
| **les réglages STRAT inertes sont retirés, pas branchés** (D1) | aucun ne pouvait l'être au bit près ; `dp_yield_weight` n'avait jamais reçu la probabilité de plantage |
| **les sorties d'essai de `reports/` restent suivies** | ajoutées par 👤 le 2026-08-17 comme mesures réelles, et l'interdit 3 protège `reports/` ; les nouvelles sorties de l'exemple simulé sont ignorées |
| **pre-commit est retiré** | sa configuration lançait `ruff --fix` et `ruff format`, contre l'interdit 1 et la politique de formatage ; rien ne l'installait |

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
le cycle `physics ↔ core` (lot E), l'hygiène d'imports F401 (lot C). L'oracle
couvre déjà les gradients analytiques (lot B, clos).

**Lint à effet possible (R9) — étapes 1 et 2 faites ; démarche retenue le 2026-09-27 (délégation de 👤).**
Règles et comptes du 2026-09-28, avant les lots F401 : F401 4 999, E402 813, I001 793, RUF046 98, E741 89,
RUF005 10, RUF015 3, UP042 3, UP046 3, UP040 2.

| règle | ce qui peut changer un comportement | démarche proposée |
|---|---|---|
| F401 | un import « inutilisé » peut être un ré-export (y compris dans un import sur plusieurs lignes, ou un nom déclaré par `__all__.extend`), un effet de bord (enregistrement, sous-module `import a.b`, configuration numba avant un `@njit`), ou servi par une façade `CertusFacadeModule` | **fait** par lots (R9) : un nom ne part que si l'import est au niveau du module, hors `try`, sans accès dynamique du module à ses globales, et si aucun fichier suivi, aucune façade, aucun test qui charge le fichier par son chemin ni aucun code lancé depuis une chaîne ne le prend ; le reste est listé, pas retiré |
| I001, E402 | l'ordre des imports compte : cycle `physics ↔ core`, `configure_numba_env()` avant tout `@njit`, `QT_QPA_PLATFORM` avant la première `QApplication` | réordonner seulement les fichiers sans import à effet, jamais les façades ni `certus_core` ; E402 cas par cas |
| E741 | renommer `l`, `O`, `I` : sans effet, mais 89 cas dont des noyaux numba | après recompilation, empreinte `float.hex()` des noyaux touchés (C1) |
| RUF046, RUF005, RUF015 | équivalences qui dépendent du type : `round(x)` d'un scalaire numpy rend bien un `int`, mais `round(x, n)` et `np.round(x)` rendent un `float64` (mesuré, numpy 2.5.2) ; `a + b` et `[*a, *b]` diffèrent si `a` est un tableau numpy | cas par cas, avec le type réel de l'argument |
| UP040, UP042, UP046 | changent l'objet à l'exécution (`TypeAliasType`, sous-classe de `str`, génériques PEP 695) | restent ignorées (arbitrage du 2026-09-27) |

**Contrôles à chaque commit** : ruff ; oracle ; unit ; `tests/ui/` ; le reste de `tests/` ; trois
photos avant/après — l'espace de noms final de chaque module touché (`scripts/lint_ns_snapshot.py`),
les modules que charge chaque script d'entrée une fois son fil de préchauffage fini, et les noms
que sert chaque façade `CertusFacadeModule`. Un nom qui disparaît ne doit être ni utilisé ni
demandé par personne.
**Ordre** : E402/I001, puis les petites règles.

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
