# Chantiers restants — 17 novembre 2026

Seuls les chantiers ouverts figurent ici ; un chantier clos sort de la page (son bilan reste dans `reports/`).
Les identifiants viennent des audits successifs et ne sont pas classés par complexité.

## Ordre du plus simple au plus complexe

La complexité est une estimation qualitative, pas une durée mesurée. Les dépendances indiquées priment
sur l'ordre : un noyau, une validation ou une mesure à la fois. Chaque changement de calcul conserve les
défauts actuels tant qu'une activation différente n'est pas décidée sur mesures.

**Priorité proposée** : **P1** = à traiter en premier (fiabilité, preuve scientifique ou fondation nécessaire) ;
**P2** = amélioration utile après les fondations ; **P3** = exploration ou rendement attendu plus faible.
La priorité est indépendante de la difficulté : un P1 complexe peut attendre son préalable plus simple.
Le profilage précède les modifications de gradients.

**Décisions de 👤 du 15 novembre** : le socle UI commun se limite au thème et à la session (18), les graphes
restent tels quels ; le modèle de dépôt de référence est celui de
`example/example_strat/JSON-strat-example.json` (24, 31, 32) ; 41 se trie en local (liste fusionner/fermer pour 👤,
rien sur GitHub).
Les chantiers 24 et 31 se traitent chacun dans une session dédiée.
**Bloqué** : la date des essais humains (33).

**Décisions de 👤 du 17 novembre** : 24 se limite au chiffre du compromis sous le modèle de référence et s'archive
s'il reste défavorable ; 48 : nouveau clone hors de Google Drive ; 49 : 👤 fournit le problème DESIGN ; 05 : pôle
infrarouge de catalogue derrière une option inactive, puis Jacobien ; 21 : session dédiée ; 18 : feu vert, 18a puis 18b.

**Remaniement du 17 novembre au soir** ([audit](../reports/audit_chantiers_2026-11-17_soir/bilan.md)) : chaque chantier commence par un premier pas d'une session, mesurable, et porte un critère d'arrêt qui l'archive
si la mesure est défavorable. 24, 31 et 32 attendent la même mesure : la campagne 49 la fait une fois pour les trois.
Ordre : 48, puis 49 (qui tranche 24, 31, 32) dès que 👤 fournit son problème ; 05, 18, 21 et 41 sont indépendants.

| Ordre | Priorité | Complexité | Chantier | Premier pas (une session) | Fin, ou arrêt | Source |
|---:|---|---|---|---|---|---|
| 48 | P1 | Faible (décision) | Dépôt dans un dossier synchronisé par Google Drive | L'ancien clone est sous `D:\drivfl`, dossier de Google Drive (`desktop.ini` : `GoogleDriveFS.exe`), qui réécrivait des fichiers suivis. Décidé le 17 : nouveau clone depuis GitHub dans `C:\dev\certus1111`, l'ancien dossier intact ; les deux `runs (1)` restaurés. | Fin : `preflight` GO dans le nouveau clone. | [audit](../reports/audit_chantiers_2026-11-17_soir/bilan.md), [contre-audit](../reports/audit_chantiers_2026-11-17_soir/contre_audit.md), G §7 |
| 49 | P2 | Moyenne à forte | Campagne A′ : DESIGN–STRAT sur un composant représentatif | Bloqué sur 👤, qui fournira le problème (17 au soir) : la [campagne A](../reports/codesign_2026-11-14/bilan.md) tournait déjà sous le réglage de référence, sa part de Rate (31–32 couches sur 34) venait du composant, et `JSON-strat-example.json` n'a pas de cibles DESIGN. Pas 1 : 👤 fournit un problème DESIGN représentatif (cibles, matériaux, nombre de couches). Pas 2 : ouvrir `scripts/bench_codesign.py` à ce problème (il exige aujourd'hui 34 couches H/L à indices constants), puis trois graines, nominal contre robuste à 1 nm. | Fin : un bilan qui donne, pour 24, le compromis nominal/robuste ; pour 31, l'écart d'épaisseurs que le plan laisse ; pour 32, marges et dynamiques face au SEEL, part de Rate relevée. | A §1.4, campagne A, [relecture](../reports/audit_chantiers_2026-11-17_soir/relecture_finale.md) |
| 24 | P2 | Faible après 49 | Mérite robuste | Lire le compromis de 49. | Archivé si le robuste reste défavorable sous le modèle de référence (décision du 17) ; sinon un essai sur tirages disjoints. | Q §4.2–4.5 |
| 31 | P2 | Très forte après 49 | Co-conception B : varier épaisseurs et plan ensemble | Seulement si 49 montre une marge d'épaisseur. `native_evaluator` fige les épaisseurs nominales : chaque pas d'épaisseur reconstruit l'évaluateur, et le gain se juge contre les cibles du problème de 49. Réglage inactif par défaut (C1). | Archivé si 49 ne montre pas de marge ; sinon gain confirmé sur trois graines, sans arrêts ajoutés. | A §1.4 |
| 32 | P3 | Moyenne après 49 | Co-conception C : critère de contrôlabilité dans DESIGN | Corréler marges et dynamiques au SEEL sur les plans de 49, sans nouvelle campagne. | Archivé si la corrélation est faible ; sinon un critère proposé à 👤. | A §1.4 |
| 05 | P3 | Moyenne | Ajustement Sellmeier de SUBSTRATE (D6) | Mesuré le 17 ([bilan](../reports/chantier05_2026-11-17/bilan.md)) : 88 % du temps dans la variante standard sans Jacobien, arrêtée sur son budget ; la variante A ne converge pas, même sur ses propres données (graines de L2, L3 au-delà de λmin, où le plancher des dénominateurs colle B2 = B3 = 0) ; l'écart de 2,9e-4 sur BK7 est la limite du modèle (aucun pôle IR). Pas (décision du 17) : pôle IR de catalogue (dénominateur signé, L1, L2 sous λmin, L3 au-delà de λmax) derrière une option inactive par défaut, mesuré sur BK7 et sur ses propres données ; puis le Jacobien de la variante standard. | Fin : variante A convergente sur ses propres données ; Jacobien gardé s'il réduit la durée. Les deux changent des indices ajustés. | A §4 |
| 41 | P3 | Faible (👤) | PR Dependabot | Cinq PR ouvertes sur GitHub (#10 à #14), toutes des actions CI : `codeql-action` (autobuild, init, analyze), `upload-artifact`, `setup-uv`. | Fin : 👤 les fusionne ou les ferme (rien sur GitHub par une IA, décision du 15). | G §2.8 |
| 18 | P3 | Moyenne | Socle de SMOOTHER et SUBSTRATE (R7) | Les fenêtres `CurveSmootherGUI` et `certus_substrate_ui.py::SubstrateIndexGUI` lisent `CertusTheme` mais n'ont ni `_collect_config` ni `_apply_config`, dont dépend la session du socle. 18a SMOOTHER, 18b SUBSTRATE : définir ce que la fenêtre sauvegarde, puis brancher thème et session, rien d'autre (décision du 15). Migration sur `CertusBaseApp` : feu vert de 👤 le 17 (plus de trois fichiers par fenêtre). | Fin : chaque fenêtre rouvre sa session et suit le thème ; chargement, calcul et export inchangés. | A §2.2–2.3 |
| 21 | P3 | Forte | Dérivées SPLINE (D4/D5) | Fait le 17 derrière `spline_mono_analytic_gradient`, allumée par défaut le 18 sur ordre de 👤 ([bilan](../reports/chantier21_2026-11-17/bilan.md)) : vérifié contre les différences finies ; sur TSIO2, 2,06 s contre 2,49 s et d = 1667,5 nm au lieu de 1699,4 (les différences finies s'arrêtaient sur leur budget). Nœuds libres et Smart Init non couverts. | Dérivées vérifiées aux cas limites, replis compris ; gardé s'il réduit la durée. | A §4 |
| 33 | P1 | Validation humaine | U13 : écran réel, Narrateur, cinq utilisateurs | Partie machine faite ; protocole `U13_protocole.md`. | Bloqué : date, personnes et matériel. | U13 |

## Sources conservées

- **A** : [audit du 13 novembre : co-conception, refactoring, vitesse et dérivées](../reports/audits_2026-11-13/bilan.md).
- **Q** : [questions DESIGN du 13 novembre et mesures du 14](../reports/questions_design_2026-11-13/bilan.md).
- **U13** : [protocole des essais humains](../reports/refactor_corridors_2026-11-11/U13_protocole.md).
- **G** : [audit général du 14 novembre](../reports/audit_general_2026-11-14/bilan.md).

Le 26 est gelé tant que les écarts et plantages du cache Numba restent ouverts.
