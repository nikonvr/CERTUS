# Validation après A2 — arrêt avant R0/R2, 14 octobre 2026

A2 est complète :24/24 cellules sauvegardées et contrôlées, fin16 h35 Paris. Le meilleur plan local antérieur reste0,3345159946 nm contre0,3967147882 nm, gain15,6785 % sur la recherche101, confirmé contre la référence sur neuf groupes frais. La découverte automatique native n'est toujours pas démontrée. Les minima bruts A2 restent distincts de ces rejeux homogènes.

## Vérifications réalisées et échecs conservés

- R1 :3 tests passent avec les nouveaux champs d'export ; les mêmes3 échouent par `KeyError: robustness_score_base` sur le snapshot avant R1. La première tentative échoue à l'import du snapshot déplacé ; la deuxième conserve le chemin logique original et fournit la contre-épreuve attendue. Sources inchangées entre ces deux montages.
- Ruff et oracle :GO,1143 tests oracle passent.
- Unité complète :5428 passed,7 skipped,2 failed en31 min04 s. Le lanceur s'arrête avant UI/reste/contrôles documentaires. [État et commandes](../attempt_02/validation.json), tous les journaux conservés.
- Premier défaut :le helper `_balanced_elite_rate_moves` ajouté au module Rate n'est pas ré-exporté par sa façade. Correction :un import dans `certus/core/certus_strat_robustness.py`, uniquement dans l'arbre principal. Aucun changement de sélection ou de score. [Snapshots et diff](../facade_repair/repair_applied.json).
- Vérification ciblée après correction dans un cache neuf :65 passed,1 failed. Les tests de façade et de mouvements Rate passent ; seul le test de pondération uniforme reste rouge. [Résultat](../targeted_repair_attempt_01/verification.json).
- Contre-épreuve :le même test échoue avec le même écart sur le worktree A2 propre au commit `da1af082`, dans un autre cache neuf :4 passed,1 failed. Test et noyau sont identiques aux fichiers principaux. Aucun fichier suivi du worktree n'est modifié. [Preuve](../baseline_spectral_attempt_01/verification.json).

Les contrôles utilisent16 processeurs logiques, affinité0xffff, priorité Normal et au plus15 threads de bibliothèque ; aucune mesure scientifique ne tourne en parallèle. Les deux caches de diagnostic restent conservés. Aucun oracle ou score n'est réputé vert à partir d'un seul sous-ensemble de tests.

## Nature exacte du blocage

`test_uniform_weights_reproduce_the_unweighted_functional` exige une différence exactement nulle entre `compute_batch_rmse(..., weights=None)` et les mêmes entrées avec `np.ones(301)`. Les données sont synthétiques :deux piles à quatre couches,301 longueurs d'onde. L'écart observé sur un des deux RMSE vaut5,551115123125783e-17, soit un ULP à cette valeur.

Le noyau existant `certus/physics/certus_strat_batch.py::compute_batch_rmse` est compilé avec `fastmath=True` et `parallel=True`. Il accumule `diff*diff` pour `None`, contre `w*diff*diff` et une somme des poids pour un tableau. Une différence entre spécialisations/reassociations Numba est une piste ; son rôle causal n'est pas encore prouvé par une comparaison de code compilé. Le diagnostic de cache chaud seul est écarté par les deux reprises à froid.

L'échec est préexistant au chantier Rate. Cela ne démontre ni un défaut physique de ce dernier ni l'équivalence au bit demandée par le test. Ne pas remplacer l'assertion par une tolérance, supprimer le test ou annoncer la validation générale réussie. La règle CLAUDE.md§2 impose :« Si un test est rouge avant toute modification, arrête-toi et signale-le. » Le guide Rate exige une base validée avant les nouvelles mesures. Une décision est demandée pour ouvrir un correctif séparé du noyau RMSE.

## Reprise concrète après décision

1. Relire preflight, ETAT, ce rapport et les processus ; vérifier la date d'autorisation. L'échéance existante reste le15 octobre2026 à06:00 UTC. Une pause n'étend pas cette fenêtre. Si elle est dépassée, aucun nouveau test/calcul sans nouvelle instruction.
2. Préserver tous les snapshots, protocoles et résultats Rate ; ne modifier aucun des deux worktrees de mesure historiques. Reproduire le contre-exemple dans un contexte de développement distinct et consigner les versions, sources et caches.
3. Examiner les spécialisations `None`/tableau et leurs opérations compilées. Tester une proposition isolée qui traite les poids uniformes par le même calcul que le cas non pondéré, en réutilisant les primitives existantes. Ce n'est pas encore une solution validée. Ne pas désactiver globalement fastmath ou changer les formules TMM pour masquer l'écart.
4. Maintenir C1 :chemin non pondéré et chemin désactivé identiques au bit à l'ancien code, comparaison froid contre froid ; conserver aussi les poids non uniformes, poids nuls→infini et tests de zones spectrales. Toute divergence du chemin inactif invalide le correctif.
5. Vérifier l'effet du correctif au bit et les métadonnées avant/après ; faire une revue du diff. Exécuter toutes les suites obligatoires, dont oracle, unité, UI, reste et documentation. La précédente suite ne suffit pas pour une nouvelle source. Aucun commit/push/activation avant ces validations.
6. Si une source scientifique change, créer une nouvelle description de provenance et un nouvel arbre/protocole de mesure, sans modifier les JSON historiques pour faire accepter les nouvelles empreintes. Ne pas attribuer un écart à la recherche Rate entre deux contextes numériques différents.
7. Ensuite seulement :vérificateur R2 passif, contrôle R0 des trois plans/graines/profondeurs réellement observées, une trace native R2 puis choix d'un seul facteur R3. Les lanceurs et les attentes préparés restent disponibles ; les anciens checks ne valident pas une nouvelle empreinte. Garder les confirmations réellement fraîches non consommées jusqu'au gel du candidat.
8. Continuer le programme borné R3–R6 selon le guide et l'autorisation restante. R7 attend toujours des données quantitatives machine.

## État conservé

R0 n'est pas lancé. L'observateur R2 et ses lanceurs sont préparés statiquement, pas encore vérifiés runtime ; aucune nouvelle trace physique ni essai R3–R6 lancé. Aucun nouveau défaut scientifique activé, aucune source physique ni assertion de test modifiée, aucun commit/push. La correction de façade reste locale et non committée. Le suivi est à mettre en pause jusqu'à la décision, afin de ne pas multiplier les réveils bloqués. [État détaillé](state.json).

Mise en pause effectuée et vérifiée :même automation, consigne/échéance/chat conservés, statutPAUSED. [Vérification](automation_pause_verified.json). À18 h14 Paris, aucun processus Python ni verrou scientifique résiduel ; aucun calcul arrêté.
