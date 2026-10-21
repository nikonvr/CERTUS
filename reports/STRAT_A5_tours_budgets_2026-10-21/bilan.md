# A5 — Tours et budget ELITE

Précontrôle au code `0820e019` : `PREFLIGHT=GO`, source scientifique inchangée depuis la dernière validation complète.
La limite C2 de l'assemblage 99 couches est consignée dans A3 ; cette expérience mono-campagne est indépendante.

[Préparation avant observation](preparation.md), [protocole figé](protocole.json),
[pilote](run_A5_tours_budgets.py.txt), [paramètres préliminaires réellement collectés](params_effectifs_preliminaires.json).
Le [contrôle de chargement](verify_A5_loaded_params.py.txt) appelle la vraie préparation de la sonde, puis
intercepte le workflow avant la création du worker : les cinq cas passent `A5_PARAMS=GO`, aucun banc exécuté par ce contrôle.
Les tours et l'arrêt sont vérifiés par le résolveur ELITE réel ; le budget reçu par le générateur sera aussi observé pendant chaque banc.

Même `r75x0.5`, deep, graine 101, fente fixe 2 nm, 300 tirages de robustesse et de consensus ; corridor 0,005,
recherche locale et hystérésis courantes actives. La banque de consensus reste 41/42/43, distincte d'une confirmation indépendante.
Ordre : référence actuelle 3 tours/arrêt actif/budget 120, puis 6 et 10 tours sans arrêt, puis budgets 40 et 360 à 3 tours/arrêt actif.
Six contre dix tours isole les tours ; contre la référence, nombre de tours et règle d'arrêt changent ensemble.

Critère principal réservé : meilleur plan déposable non marqué de repli avec score de consensus fini et positif,
métadonnées `mean_std`, graines 41/42/43 et trois évaluations réussies (`n_samples=3`).
Minimum historique calculé séparément par le résumeur existant, sans mélange de provenance. Paquets Rate comptés par l'outil existant.
Les plans complets, couches Rate, paramètres, refus et durées restent dans les artefacts et emplacements neufs.
Si des déposables existent sans score homogène complet, le pilote garde la mesure et s'arrête pour analyser le dépouillement.

Après commit du protocole et contrôle d'absence d'autre Python :

```text
python "reports/STRAT_A5_tours_budgets_2026-10-21/run_A5_tours_budgets.py.txt"
```

État vivant `etat.json`, un seul enfant à la fois. Ne pas modifier la tête ni les fichiers suivis pendant la chaîne.
Chaque lancement vérifie l'échéance du 21 octobre à 10 h ; une mesure engagée peut finir ensuite.
Les résultats restent à mesurer au moment du protocole. Aucun défaut scientifique n'est modifié.
