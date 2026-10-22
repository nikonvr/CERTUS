# A4 v2 — contrôles avant campagne

La [tentative initiale](tentative_01/interruption.md) est conservée. Le pool est désormais réservé avant le filtre
de score fini ; les tests vérifient son passage au générateur, le maintien de la porte en sortie et `refine=False`.
Les chemins paramètre absent et zéro conservent au bit les candidats historiques.

Tests de raccordement avant correction : `3 failed, 8 passed` (`tests_avant_v2.log`). Après correction :
`100 passed` (`tests_apres_v2c.log`, avec ELITE Rate, raffinement final, façade et architecture).

Les huit commandes de CLAUDE.md §2 ont passé **en série**, avec arrêt au premier échec :
**8 441 réussis, 19 ignorés, 3 échecs attendus, aucun échec inattendu ; `VALIDATION_SERIE=GO`**.
Commandes, durées et empreintes des sources modifiées : `validation_serie_v2/resultats.json` ;
journaux complets dans ce dossier et `validation_serie_v2.log`. Les empreintes sont vérifiées inchangées en fin de validation.

`python scripts/c1_diff.py HEAD` contre `38acac0d` : **C1 TENU, 9 092 tableaux identiques au bit** (`c1_v2.log`).
Le corpus physique et le test des candidats ELITE couvrent deux chemins distincts ; aucune prétention de validation externe.
