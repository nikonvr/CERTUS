# Chantiers restants — 17 novembre 2026

Identifiants du [contre-audit du 14 novembre](../reports/contre_audit_chantiers_2026-11-14/bilan.md) ; 34 à 44 viennent
de l'[audit général du 14 novembre](../reports/audit_general_2026-11-14/bilan.md), 45 de l'audit du code du 15, et ne
sont pas classés par complexité.

## Ordre du plus simple au plus complexe

La complexité est une estimation qualitative, pas une durée mesurée. Les dépendances indiquées priment
sur l'ordre : un noyau, une validation ou une mesure à la fois. Chaque changement de calcul conserve les
défauts actuels tant qu'une activation différente n'est pas décidée sur mesures.

**Priorité proposée** : **P1** = à traiter en premier (fiabilité, preuve scientifique ou fondation nécessaire) ;
**P2** = amélioration utile après les fondations ; **P3** = exploration ou rendement attendu plus faible.
La priorité est indépendante de la difficulté : un P1 complexe peut attendre son préalable plus simple.
La [campagne de co-conception A](../reports/codesign_2026-11-14/bilan.md) est terminée.
Le profilage précède les modifications de gradients.

**Décisions de 👤 du 15 novembre** : le socle UI commun se limite au thème et à la session (18), les graphes
restent tels quels (16 sort de la table) ; le modèle de dépôt de référence est celui de
`example/example_strat/JSON-strat-example.json` (24, 31, 32) ; reprise B : mesurer le coût des étapes d'abord,
39 se reconstruit en local sans publier, 40 peut installer un code TMM tiers
dans un environnement à part, 41 se trie en local (liste fusionner/fermer pour 👤, rien sur GitHub).
Les chantiers 24 et 31 se traitent chacun dans une session dédiée.
**Bloqué** : la date des essais humains (33).

**Décisions de 👤 du 17 novembre** : 34 s'instruit avant toute décision sur les bits ; 44 se réduit aux étapes 3 et 7
de son plan (2a et 2c abandonnées) ; 24 se limite au chiffre du compromis sous le modèle de référence et s'archive
s'il reste défavorable ; 05 s'archive si la part des ajustements concernés est faible ; 20, 25, 27, 28, 29 et 36
(ALG-20) sortent de la liste.

**Remaniement du 17 novembre au soir** ([audit](../reports/audit_chantiers_2026-11-17_soir/bilan.md), ordre à approuver
par 👤) : chaque chantier commence par un premier pas d'une session, mesurable, et porte un critère d'arrêt qui l'archive
si la mesure est défavorable. 24, 31 et 32 attendent la même mesure : la campagne 49 la fait une fois pour les trois.
Ordre proposé : 48, puis 49 (qui tranche 24, 31, 32), puis les petits chantiers indépendants (05, 19, 41, 50, 18, 21)
dans n'importe quel ordre.

| Ordre | Priorité | Complexité | Chantier | Premier pas (une session) | Fin, ou arrêt | Source |
|---:|---|---|---|---|---|---|
| 48 | P1 | Faible (décision) | Dépôt dans un dossier synchronisé par Google Drive | Le dépôt est sous `D:\drivfl`, synchronisé (`.tmp.drivedownload/`, `.tmp.driveupload/`) ; trois fichiers suivis sont des copies de conflit « (1) ». Cause probable, non prouvée, des 19 fichiers revenus au 16 novembre (reste du 43). Pas : 👤 choisit de déplacer le clone hors du dossier synchronisé (GitHub sert de sauvegarde) ou d'exclure le dossier de la synchronisation. | Fin : un clone hors synchronisation, `preflight` GO ; 👤 décide du sort des trois copies « (1) » suivies. | [audit](../reports/audit_chantiers_2026-11-17_soir/bilan.md), G §7 |
| 49 | P2 | Moyenne | Campagne A′ : DESIGN–STRAT sous le modèle de référence | Rejouer le protocole de la [campagne A](../reports/codesign_2026-11-14/bilan.md) (`scripts/bench_codesign.py`, trois graines, nominal contre robuste à 1 nm) avec le réglage STRAT de `JSON-strat-example.json` tel quel ; relever la part de Rate, le SEEL, l'écart des plans et des marges entre les deux bras. | Fin : un bilan qui donne, pour 24, le compromis nominal/robuste ; pour 31, l'écart d'épaisseurs que le plan laisse ; pour 32, marges et dynamiques face au SEEL. | A §1.4, campagne A |
| 24 | P2 | Faible après 49 | Mérite robuste (anciens 23, 24 et 30b) | Lire le compromis de 49. | Archivé si le robuste reste défavorable sous le modèle de référence (décision du 17) ; sinon un essai sur tirages disjoints. | Q §4.2–4.5 |
| 31 | P2 | Forte après 49 | Co-conception B : varier épaisseurs et plan ensemble | Seulement si 49 montre une marge d'épaisseur : ajouter un pas d'épaisseur à `certus_strat_local_search.py::LocalSearchConfig`, inactif par défaut (C1), mesuré au juge de paix. | Archivé si 49 ne montre pas de marge ; sinon gain confirmé sur trois graines, sans arrêts ajoutés. | A §1.4 |
| 32 | P3 | Moyenne après 49 | Co-conception C : critère de contrôlabilité dans DESIGN | Corréler marges et dynamiques au SEEL sur les plans de 49, sans nouvelle campagne. | Archivé si la corrélation est faible ; sinon un critère proposé à 👤. | A §1.4 |
| 05 | P3 | Faible | Jacobiens Sellmeier manquants (D6) | Chronométrer un ajustement SUBSTRATE Sellmeier par différences finies (les six sites de l'[audit](../reports/audit_chantiers_2026-11-17_soir/bilan.md)). | Archivé si l'ajustement prend moins d'une seconde (A le jugeait déjà rapide) ; sinon Jacobien analytique validé par différences finies. | A §4 |
| 19 | P2 | Faible | Éprouver le sélecteur de tests | Une commande : `python scripts\verify_changed.py --audit-calls` sur `tests/unit`, `tests/ui` et `tests/oracle`. Trou connu : les scripts que `tests/regression/` lance en sous-processus échappent au graphe. | Fin : les trous relevés ; relier les sous-processus seulement si l'audit en trouve d'autres. La validation complète reste la référence. | Q §5.3, S |
| 41 | P3 | Faible (👤) | PR Dependabot | Cinq PR ouvertes sur GitHub (#10 à #14), toutes des actions CI : `codeql-action` (autobuild, init, analyze), `upload-artifact`, `setup-uv`. | Fin : 👤 les fusionne ou les ferme (rien sur GitHub par une IA, décision du 15). | G §2.8 |
| 50 | P3 | Faible | Recoupement tiers de la face arrière | Étendre la sonde du 40 à la face arrière incohérente (le code tiers `tmm` la calcule) sur les mêmes cas. | Fin : écart relevé ; un écart au-delà de 1e-12 devient un défaut. | 40 |
| 18 | P3 | Moyenne | Socle de SMOOTHER et SUBSTRATE (R7) | 18a : thème commun ; 18b : session par `certus_base_app_config_mixin`. Deux pas indépendants, rien d'autre (décision du 15). | Fin : les deux fenêtres rouvrent leur session et suivent le thème ; chargement, calcul et export inchangés. | A §2.2–2.3 |
| 21 | P3 | Forte | Dérivées SPLINE (D4/D5) | Profiler nœuds libres et Smart Init (`spline_smart_init.py::optimize_smart_init_nkd_packet`, encore sur le fil de l'interface). | Gradients seulement si les différences finies dominent le temps ; sinon archivé. Dérivées vérifiées aux cas limites, replis compris. | A §4 |
| 47 | P3 | Décision | Épaisseur du substrat absorbant dans STRAT | DESIGN et RE faits, METAL simple sans objet (2026-11-17). STRAT lit `n_sub.real` ; son substrat de référence (SiO2) n'absorbe pas. | 👤 : sans objet faute de cas d'usage d'un substrat absorbant, sinon changement de modèle inactif par défaut. | 👤 2026-11-17 |
| 33 | P1 | Validation humaine | U13 : écran réel, Narrateur, cinq utilisateurs | Partie machine faite ; protocole `U13_protocole.md`. | Bloqué : date, personnes et matériel. | U13 |

## Sources conservées

- **A** : [audit du 13 novembre : co-conception, refactoring, vitesse et dérivées](../reports/audits_2026-11-13/bilan.md).
- **Q** : [questions DESIGN du 13 novembre et mesures du 14](../reports/questions_design_2026-11-13/bilan.md).
- **U12** : [spécification de reprise, actualisée le 13 novembre](../reports/refactor_corridors_2026-11-11/U12_specification.md).
- **U13** : [protocole des essais humains](../reports/refactor_corridors_2026-11-11/U13_protocole.md).
- **G** : [audit général du 14 novembre](../reports/audit_general_2026-11-14/bilan.md).
- **O** : [audit du signal OMS 5100 de STRAT, 15 novembre](../reports/audit_oms5100_2026-11-15/bilan.md).
- **S** : [sélecteur de tests face à la suite complète, 15 novembre](../reports/selecteur_tests_2026-11-14/bilan.md).
- **C** : [audit du code du 15 novembre](../reports/audit_code_2026-11-15/bilan.md).
- [Audit des chantiers du 14 novembre](../reports/audit_chantiers_2026-11-14/bilan.md) et
  [chantier 07, démarrage à froid des cinq fenêtres](../reports/chantier07_amorcage_2026-11-14/bilan.md).

Les chantiers 03, 06 et 17 sortent de la liste active pour rendement insuffisant, ainsi que 20, 25, 27, 28, 29 et 36 (décision de 👤 du 17 novembre ; C18 de 36 passe en 34). Le 26 est gelé
tant que les écarts et plantages du cache Numba restent ouverts. Les regroupements conservent les
identifiants 16, 21, 24 et 15.

Les points d'entrée des candidats ont été recoupés dans le code. Les mesures des chantiers terminés sont
consignées dans les bilans liés ci-dessus.

## Éléments sortis de la liste car réalisés

U1–U11, refactoring des corridors, reprise des sessions U12 A, reprise STRAT multi-graines, partie machine
d'U13, tours supplémentaires STRAT, aperçu INDEX TLU, rangement des journaux, contrôle des liens,
polisseur hybride, poids des bandes disjointes, estimateur N/TOT, grille automatique et sélection robuste
sont intégrés, ainsi que les corrections de l'audit du code du 15 novembre (45, `VALIDATION=GO` sur `1a0a12cf`), les copies de la formule de réflexion (46, 2026-11-17), et, le 17 novembre : bits selon l'historique de compilation (34, [bilan](../reports/chantier34_2026-11-17/bilan.md)), exécutable gelé (39, [bilan](../reports/chantier39_2026-11-17/bilan.md)), recoupement du TMM par `tmm` 0.2.0 (40, [bilan](../reports/tmm_tiers_2026-11-15/bilan.md)), durée de la validation (43, [bilan](../reports/chantier43_2026-11-17/bilan.md) ; sa cause ouverte passe en 48), signal OMS 5100 (44, rien d'activé, [bilan](../reports/chantier44_etape3_2026-11-17/bilan.md)), les corrections de C20, d'ALG-03 (35) et d'ALG-13, l'amorçage Numba mutualisé (07), le contrôle avant publication (37) et les polissages de DESIGN descendus dans `certus.core` (38). Chantier 42 : sur les 90 scripts Python suivis, 22 ne sont cités que dans `reports/` ; les cinq qui outillent une règle sont cités dans la référence (§6), les sondes restent en place, leur rapport donne la commande. Les mesures appariées et l'oracle sont dans les sources ci-dessus.