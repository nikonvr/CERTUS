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
Les résultats restaient à mesurer au moment du protocole. Aucun défaut scientifique n'est modifié.

## Arrêt demandé le 21 octobre à 08 h 09 Paris

La référence a terminé normalement : exit 0, verdict `OK`, empreintes de l'artefact et du journal vérifiées.
L'essai suivant à six tours a été interrompu pour permettre l'extinction du PC ; son journal et son audit restent conservés.
Le contrôleur est arrêté, aucun cas suivant n'a été lancé, automatisation suspendue.

| cas | tours / arrêt sans gain / budget Rate | SEEL principal (nm) | durée (s) | paquets Rate du meilleur plan | état |
|---|---|---:|---:|---:|---|
| référence neuve | 3 / actif / 120 | 0.39671478821937545 | 3241.6050043 | 3 | terminé, consensus homogène vérifié |
| six tours | 6 / désactivé / 120 | — | — | — | interrompu par le propriétaire, incomplet |
| dix tours | 10 / désactivé / 120 | — | — | — | non lancé |
| budget 40 | 3 / actif / 40 | — | — | — | non lancé |
| budget 360 | 3 / actif / 360 | — | — | — | non lancé |

Référence : 670 plans répondent au critère principal réservé. Le meilleur a l'identifiant `900951015`,
consensus `mean_std`, graines 41/42/43, `n_samples=3`. Son plan complet et les couches Rate sont conservés
dans l'artefact original et `baseline_a01/summary.json`, inclus dans l'archive. Ce résultat de recherche
ne constitue pas une confirmation indépendante de plan figé, ni une comparaison des variantes non terminées.

La lecture finale recalcule le résumé à partir des données conservées, vérifie les SHA et les paramètres
réellement reçus par le résolveur et le générateur. Les journaux des tours générateurs comprennent les
phases préliminaires et finales : leur compte n'est pas celui d'une seule boucle ELITE.
`revue_baseline_a01.json`, `revue_mesures.json`, l'état avant arrêt et le reçu d'arrêt sont archivés.
Le minimum du résumeur historique reste séparé du score principal homogène.

Reprise : [bilan d'arrêt](../ACTIONS_autonomes_2026-10-20/ARRET_propre_2026-10-21.md).
Ne pas reprendre cet ancien pilote sous une nouvelle tête ou après son échéance ; référencer la baseline
conservée dans un nouveau protocole vérifié et ouvrir une nouvelle tentative pour les six tours.

[Archive partielle des 30 preuves](preuves_A5_partielles_20261021T061232Z.zip), 1 344 359 octets,
SHA-256 `51c83a5b49d849b56ccb93e782a829261b8590b9df3f7a57f100b21e0b6b2348`.
Intégrité ZIP et empreintes archivées vérifiées ; artefact de référence, journal incomplet, audits,
états, reçus, protocoles et outils conservés. Chemins textuels neutralisés avec SHA originaux et archivés.
La lecture finale passe et nomme explicitement les quatre variantes manquantes ; Ruff E9/F des deux
outils passe. Aucun calcul physique ni test de production supplémentaire lancé pour cette sauvegarde.
