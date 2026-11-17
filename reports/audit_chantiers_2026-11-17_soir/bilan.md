# Audit des chantiers ouverts — 17 novembre 2026 au soir

Demande de 👤 : refaire un audit complet des chantiers ouverts et remanier l'ensemble pour qu'il soit faisable. Base :
`master` @ `21694055`. Chaque ligne de [`CHANTIERS_RESTANTS.md`](../../docs/CHANTIERS_RESTANTS.md) a été recoupée avec le
code et les rapports qu'elle cite (lecture seule ; aucune mesure de calcul lancée). Ce qui suit est constaté, sauf mention.

## Constats

| # | Constat | Effet sur le chantier |
|---|---|---|
| — | **Le dépôt de travail est dans un dossier synchronisé par Google Drive** : `D:\drivfl` porte `.tmp.drivedownload/`, `.tmp.driveupload/`, `desktop.ini` ; Google Drive File Stream est installé. Trois fichiers suivis portent un suffixe de copie de conflit « (1) » (`example/database_depots/bruts/zns yf3 quartz serieux (1).xls`, `reports/selecteur_tests_2026-11-14/runs (1)/control.json` et `infrared_center.json`, ces deux-là entrés par `0c31b627` à 14:07 et supprimés de l'arbre depuis, sans commit). | Cause **probable, non prouvée**, des 19 fichiers revenus à leur version du 16 novembre (reste ouvert du 43) et peut-être du « Permission denied » sur `.git/worktrees/certus_wt_cl4_seeds`. Un arbre que l'on modifie pendant qu'un tiers le réécrit, c'est l'erreur n° 1 de CLAUDE.md §4. Nouveau chantier 48, P1. |
| 05 | Les sites D6 existent (`certus_substrate_sellmeier.py:242`, `:665`, `:843` ; `certus_substrate_index.py:1498` ; `certus_index_utils.py:575`, `:610`) ; un seul a son Jacobien (`_jac_polish_q`). L'audit A les jugeait déjà « faible : ces ajustements sont déjà rapides ». | Règle de 👤 du 17 : archiver si la part est faible. Il ne reste qu'à chronométrer un ajustement. |
| 18 | SMOOTHER (`certus/ui/certus_curve_smoother.py`) et SUBSTRATE (`certus_substrate_index_dialog.py`) n'utilisent pas `certus_base_app_config_mixin` (session) ; ils ont leur propre code de thème. | Périmètre « thème et session » confirmé ; se scinde en deux pas indépendants. |
| 19 | La ligne place `MAX_REPLAY` dans `probe_test_selector.py::classify` : il est dans `scripts/validate_parallel.py:58` (40). `verify_changed.py --audit-calls` existe. Chantier gelé après 43 (fait). | Texte corrigé ; premier pas réduit à une commande (`--audit-calls` sur trois suites). |
| 21 | `spline_smart_init.py::optimize_smart_init_nkd_packet` existe (ligne 1140) ; aucun profil des nœuds libres ni du Smart Init n'est versionné. | Premier pas : le profil seul, avec un seuil qui décide des gradients. |
| 24, 31, 32 | La campagne A ([bilan](../codesign_2026-11-14/bilan.md)) porte sur des plans à 31–32 couches Rate sur 34, atypiques ; sa conclusion demande, pour 24, 31 et 32, **un nouvel essai sous un modèle de vitesse et une part de Rate représentatifs**. Le modèle de référence est fixé depuis le 15 (`JSON-strat-example.json`). `certus_strat_local_search.py::LocalSearchConfig` fait varier longueurs d'onde et couches Rate, pas les épaisseurs. | Les trois attendent la même mesure : une campagne commune (nouveau 49) les débloque ou les archive ensemble ; 24 et 32 n'ont plus de travail propre avant elle. |
| 33 | Protocole présent (`U13_protocole.md`). | Inchangé, bloqué par la date. |
| 41 | GitHub : **5 PR Dependabot ouvertes** (#10 à #14), toutes des actions CI (`codeql-action` ×3, `upload-artifact`, `setup-uv`), 5 branches distantes ; la ligne en annonçait douze. | Une action de 👤 sur GitHub (décision du 15 : rien sur GitHub par une IA). |
| 47 | STRAT lit `n_sub.real` ; le substrat de référence est « SiO2 » (silice fondue, k = 0 dans le visible). | Le changement de modèle n'agit que pour un substrat absorbant : à décider sur un cas d'usage, sinon sans objet comme METAL. |
| 40 | Restes hors recoupement : face arrière et gradients. | Petit chantier détachable (50), la sonde tierce existe. |
| 44 | Restes hors sonde (`SWING_MIN` en multiples de A, bruit proportionnel à T) : fermés par la décision déléguée. | Laissés dans la ligne 44, pas de nouveau chantier. |
| — | `validate_parallel.py --no-confirm` ne rejoue pas les échecs en série (voulu, documenté ligne 7) ; la validation du soir l'avait pris et a dû être rejouée à la main. | Rien à corriger ; ne pas passer `--no-confirm` pour une validation de référence. |

## Remaniement (appliqué dans `CHANTIERS_RESTANTS.md`, ordre à approuver par 👤)

Principes : chaque chantier commence par **un premier pas d'une session**, mesurable, et porte **un critère d'arrêt** qui
l'archive si la mesure est défavorable ; les chantiers qui attendent la même mesure la partagent.

1. **48** (P1) — dépôt hors du dossier synchronisé : confirmer, puis décision de 👤 (déplacer le clone ou exclure le dossier).
2. **49** (P2) — campagne A′ sous le modèle de référence : une session, alimente 24, 31 et 32.
3. **24 / 31 / 32** — conclus sur A′ : 24 et 32 s'archivent si A′ est défavorable ; 31 ne se code que si A′ montre une
   marge, derrière un réglage inactif (C1).
4. Petits chantiers indépendants, dans n'importe quel ordre : **05** (un chronométrage), **19** (une commande), **41**
   (👤 sur GitHub), **50** (sonde tierce sur la face arrière), **18a/18b**, **21** (profil).
5. **47 STRAT** : décision de 👤 sur un cas d'usage ; **33** : bloqué.
