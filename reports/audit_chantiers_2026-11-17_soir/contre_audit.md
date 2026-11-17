# Contre-audit de l'audit des chantiers du 17 novembre au soir

Demande de 👤 : refaire un contre-audit du [bilan](bilan.md) (`e1c7d735`). Chaque affirmation et chaque premier pas ont été
rejoués contre le code ; lecture seule, aucune mesure de calcul. Cinq erreurs, dont deux qui rendaient un premier pas
infaisable ; elles sont corrigées dans [`CHANTIERS_RESTANTS.md`](../../docs/CHANTIERS_RESTANTS.md).

| Chantier | L'audit disait | Constaté | Correction |
|---|---|---|---|
| 49 | Rejouer la campagne A « avec le réglage STRAT de `JSON-strat-example.json` tel quel ». | Le banc de la campagne A l'utilisait déjà : `scripts/bench_codesign.py` charge `JSON-strat-example-fast.json`, qui ne diffère de la référence que par `execution_mode` ; ses seuls écarts sont `dynamics_threshold="0.0"` et la recherche locale coupée. La part de Rate de 31–32 couches sur 34 vient du composant (séparateur 50/50 à indices constants), pas du réglage. Le banc refuse tout autre composant (`ValueError` hors de la séquence H/L à 34 couches). | Infaisable tel qu'écrit : A′ rejouerait A. Premier pas : 👤 choisit le composant représentatif (par exemple les 48 couches de l'exemple STRAT) ; puis le banc s'ouvre à ce composant. Complexité relevée à moyenne–forte. |
| 50 | Étendre la sonde du 40 à la face arrière, que `tmm` calcule. | Le [bilan du 40](../tmm_tiers_2026-11-15/bilan.md) affirme le contraire (« `tmm` n'a que le cas cohérent ») ; c'est lui qui se trompe : la copie installée (`%TEMP%\certus_tmm_tiers`, `tmm` 0.2.0) a `inc_tmm` (ligne 751 de `tmm_core.py`) et `inc_group_layers`. | 50 confirmé, et élargi : `inc_tmm` traite une couche épaisse absorbante, donc la perte de la plaque (chantier 47) se recoupe aussi. Phrase du bilan du 40 corrigée. |
| 18 | Deux pas indépendants : 18a thème, 18b session. | Les deux fenêtres lisent déjà `CertusTheme` (couleurs) ; ce qui leur manque, selon la source (A §2.2, R7), est la migration sur `CertusBaseApp`, qui apporte ensemble `_apply_theme` et la session (`certus_base_app_config_mixin`). Thème et session ne se séparent pas. | Découpage par fenêtre : 18a SMOOTHER, 18b SUBSTRATE, chacun migré sur `CertusBaseApp`. |
| 19 | Premier pas : une commande, `--audit-calls` sur trois suites. | La durée de `--audit-calls` (profil Python de chaque test) n'est mesurée nulle part ; sur `tests/unit` (6 357 tests, 68 min en série sans profil) elle peut dépasser une session. Le rapport S propose une parade sans mesure : jouer `tests/regression/` dès qu'un module du dépôt change. | Premier pas : chronométrer `--audit-calls` sur `tests/oracle` ; la parade S en pas indépendant. Complexité faible à moyenne. |
| 48 | Trois fichiers suivis sont des copies de conflit « (1) ». | Le dossier est bien synchronisé (`desktop.ini` de `D:\drivfl` : icône de `GoogleDriveFS.exe`), et le [bilan du 43](../chantier43_2026-11-17/bilan.md) le savait. Mais `zns yf3 quartz serieux (1).xls` est entré le 2026-10-11 avec son original, dont il diffère : probablement un fichier de 👤. Les deux `runs (1)` diffèrent de `runs/` : origine non établie. | Formulation ramenée à « deux fichiers `runs (1)` d'origine non établie » ; le lien avec les 19 fichiers revenus reste une hypothèse. |

Confirmé sans changement : 05 (six sites D6, un seul Jacobien, jugé rapide par A), 21 (`optimize_smart_init_nkd_packet` appelé
depuis `run_nkd_local_opt` de l'interface SPLINE), 24 et 32 (dépendent de 49), 31 (`LocalSearchConfig` sans pas d'épaisseur),
33, 41 (cinq PR, #10 à #14), 47 (STRAT lit `ns_real` et `np.real(n_sub)`).

Leçon : l'audit avait recopié deux rapports (le 40, la campagne A) sans rouvrir le code qu'ils décrivent.
