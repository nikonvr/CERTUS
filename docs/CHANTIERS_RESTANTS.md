# Chantiers restants — 15 novembre 2026

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
sans toucher au calcul (27, 28, 29) ; 39 se reconstruit en local sans publier, 40 peut installer un code TMM tiers
dans un environnement à part, 41 se trie en local (liste fusionner/fermer pour 👤, rien sur GitHub).
**Ordre de traitement validé par 👤 le 15 novembre** : 45 d'abord ; puis 44 jusqu'à sa décision (étape 7 de son
plan) ; ensuite 40, puis 34. Les chantiers 24 et 31 se traitent chacun dans une session dédiée.
**Bloqué** : la date des essais humains (33).

| Ordre | Priorité | Complexité | Chantier restant | État et critère de fin | Source |
|---:|---|---|---|---|---|
| 05 | P3 | Faible à moyenne | Jacobiens Sellmeier manquants (D6) | Mesurer la part des ajustements concernés. Valider un éventuel gradient par différences finies et mesurer le gain à paramètres identiques. | A §4 |
| 18 | P3 | Moyenne | Socle de SMOOTHER et SUBSTRATE (R7) | Ajouter thème et session communs, rien d'autre (décision du 15 novembre) ; préserver chargement, calcul et export. | A §2.2–2.3 |
| 19 | P2 | Moyenne à forte | Éprouver le sélecteur de tests | Huit cas mesurés sur `df36593f` : cinq OK, un trou réel (les scripts que `tests/regression/` lance en sous-processus échappent au graphe), deux artefacts de la sonde. Reste : relier ces sous-processus au graphe, rejouer seuls les échecs au-delà de `MAX_REPLAY` dans `probe_test_selector.py::classify`, et passer `verify_changed.py --audit-calls` sur `tests/unit`, `tests/ui` et `tests/oracle`. La validation complète reste la référence. | Q §5.3, S |
| 20 | P3 | Forte | Raffinement en longueurs d'onde complexes | Le polissage adaptatif à TOT fixée laisse un MF résolu de 0,10983 %. Comparer le raffinement complexe à ce témoin et vérifier sa tenue sur des départs éloignés. | A §3.3–3.4 et Q §10 |
| 21 | P3 | Forte | Dérivées SPLINE (D4/D5, ancien 13) | (a) fait : le polissage n, k, d par paquet de trois nœuds du Smart Init a quitté l'UI pour `spline_smart_init.py::optimize_smart_init_nkd_packet`, identique au bit ; il tourne encore sur le fil de l'interface. Reste : profiler nœuds libres et Smart Init, puis ajouter les gradients. Vérifier les dérivées des valeurs et positions aux cas limites, y compris les replis. | A §4 |
| 24 | P2 | Forte | Mérite robuste (anciens 23, 24 et 30b) | Le mérite à 1 nm dégrade le RMS déposé des trois paires étudiées. Chiffrer le compromis nominal/robuste sous un modèle de dépôt représentatif avant de tester un nuage, la descente de sensibilité ou la covariance. Confirmer sur tirages disjoints. | Q §4.2–4.5 et campagne A |
| 25 | P3 | Forte | Germes structurés Fourier pour le mémétique | Piste non mesurée : diversité de phases, conversion H/L compatible avec les contraintes, comparaison au tirage actuel sur trois-raies et cissoïde. | Q §1.3 |
| 27 | P3 | Très forte | Reprise de calcul STRAT (U12 B) | Mesurer le coût des étapes du pipeline avant de choisir les points de reprise. Vérifier la compatibilité des réglages, graines, noyaux et ouvriers, ainsi que l'identité au bit. | U12 §4–5 |
| 28 | P3 | Très forte | Reprise de calcul DESIGN (U12 B) | Mesurer séparément le mémétique et PGLOBAL. Pour le mémétique, inclure population, générateur, lot et nombre d'ouvriers dans l'état de reprise. Pour PGLOBAL, vérifier la reconstruction du regroupement. | U12 §4–5 |
| 29 | P3 | Très forte | Reprise des corridors INDEX SPLINE (U12 B) | Mesurer le coût d'un corridor réel avant de spécifier le point de reprise. Exiger un résultat identique au bit à contexte et ouvriers compatibles. | U12 §4–5 |
| 31 | P2 | Très forte | Co-conception B : varier épaisseurs et plan ensemble | La recherche locale STRAT varie actuellement le plan. Ajouter les épaisseurs, réaccorder les voisines et confirmer le gain contre les cibles sans arrêts ajoutés. | A §1.4 |
| 32 | P3 | Très forte | Co-conception C : critère de contrôlabilité dans DESIGN | Corréler les marges et dynamiques aux résultats STRAT sur des plans avec une part de Rate représentative. La campagne A a retenu 31 à 32 couches Rate sur 34. | A §1.4 et campagne A |
| 33 | P1 | Validation humaine | U13 : écran réel, Narrateur, cinq utilisateurs | Partie machine faite. Exécuter les essais humains et consigner les observations selon le protocole ; cette ligne requiert les personnes et le matériel. | U13 |
| 34 | P2 | À instruire | Bits selon l'historique de compilation | Cause du POEM trouvée : un objet du cache Numba compilé dans un long processus lie d'autres routines complexes internes et change les derniers bits. Le validateur rejoue désormais sur cache vierge (`f350044d`). Reste : vérifier que les tests de fente et de paramètres neutres relèvent du même mécanisme, et décider s'il faut rendre les noyaux indépendants de l'historique (change les bits). Revu le 15 novembre : un écart de 7,7e-12 du portage des matrices de STRAT (retiré depuis) passait d'un côté ou de l'autre de 1e-12 selon le cache. | G §6 |
| 36 | P2 | Faible à moyenne | Défauts du registre supprimé | [Tri du 14 novembre](../reports/audit_general_2026-11-14/registre_tri.md) du registre retiré par `b6fb1939` : C13, C20, ALG-03 et ALG-13 corrigés. Restent présents ALG-20 et C18 ; les UX présents relèvent du périmètre UI (16, 18). Mesurer chacun avant de le corriger. | G §8 |
| 39 | P3 | Moyenne | Exécutable gelé et version | L'exécutable date de `dbec2fc1`. Reconstruire, essai de fumée, et vérifier que les exports portent une version qui distingue l'état du code. | G §2.6 |
| 40 | P2 | Moyenne | Recoupement du TMM par un code tiers | Sonde hors noyau comparant R et T à un code externe sur des empilements absorbants et obliques. Sonde écrite (`reports/tmm_tiers_2026-11-15/probe_tmm_tiers.py`, `tmm` 0.2.0 hors du dépôt) : la lancer et écrire son bilan. | G §2.7 |
| 41 | P3 | Faible | Branches Dependabot | Douze mises à jour en attente depuis le 30 septembre : fusionner ou fermer. | G §2.8 |
| 43 | P2 | Faible | Durée de la validation | `376baef1` : fils Numba = cœurs ÷ workers ; `unit` passe de 512 à 299 s, `ui` est inchangé (~10 min). Mesurer `ui` hors du disque `D:` et, s'il le faut, son nombre de workers. | G §7 |
| 44 | P2 | Moyenne à forte | Signal OMS 5100 de STRAT | Plan en neuf étapes de l'audit (§8). Étape 1 faite : le [profil du noyau](../reports/audit_oms5100_2026-11-15/profil_noyau/bilan.md) surestimait les matrices ; leur portage d'une couche à l'autre ne gagnait que 2 à 15 % sur un plan ELITE réel : retiré. 👤 accepte un écart au dernier bit pour ces accélérations. [Recherche complète profilée](../reports/audit_oms5100_2026-11-15/profil_strat_complet/bilan.md) : STRAT et RE passent sur la couche TBB quand elle est installée (1 074 s contre 1 339 s, mêmes bits ; DESIGN reste sur OpenMP, non reproductible sous TBB ; TBB hors dépendances, licence Intel) ; la recherche locale fait désormais la moitié du temps (réutiliser la croissance du plan courant, ~10 % estimés). Puis sonde de sensibilité aux hypothèses non mesurables (D98, étalonnage, `SWING_MIN`) et options physiques inactives (retard de coupure, face arrière, fente triangulaire) avant décision de 👤. Sans accès à la salle. | O §8 |
| 45 | P1 | Forte | Corrections de l'audit du code | 27 défauts confirmés (8 critiques, 19 majeurs) ; 5 corrigés. Les 22 restants, groupés par module, avec emplacement, correction décidée et test, dans le [plan des corrections](../reports/audit_code_2026-11-15/plan_corrections.md). Fin : validation complète, `ETAT.md` et `ETAT_acquis.md` à jour, fusion sur ordre de 👤. | C |

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

Les chantiers 03, 06 et 17 sortent de la liste active pour rendement insuffisant. Le 26 est gelé
tant que les écarts et plantages du cache Numba restent ouverts. Les regroupements conservent les
identifiants 16, 21, 24 et 15.

Les points d'entrée des candidats ont été recoupés dans le code. Les mesures des chantiers terminés sont
consignées dans les bilans liés ci-dessus.

## Éléments sortis de la liste car réalisés

U1–U11, refactoring des corridors, reprise des sessions U12 A, reprise STRAT multi-graines, partie machine
d'U13, tours supplémentaires STRAT, aperçu INDEX TLU, rangement des journaux, contrôle des liens,
polisseur hybride, poids des bandes disjointes, estimateur N/TOT, grille automatique et sélection robuste
sont intégrés, ainsi que les corrections de C20, d'ALG-03 (35) et d'ALG-13, l'amorçage Numba mutualisé (07), le contrôle avant publication (37) et les polissages de DESIGN descendus dans `certus.core` (38). Chantier 42 : sur les 90 scripts Python suivis, 22 ne sont cités que dans `reports/` ; les cinq qui outillent une règle sont cités dans la référence (§6), les sondes restent en place, leur rapport donne la commande. Les mesures appariées et l'oracle sont dans les sources ci-dessus.