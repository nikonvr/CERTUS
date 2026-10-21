# A5 — Préparation avant observation, 21 octobre 2026

Aucune mesure A5 lancée. La chaîne A3 reste prioritaire et doit se terminer avant toute mesure ici.
Source inspectée : `85a9e82f`. Cette préparation sera figée avec la tête réellement utilisée avant exécution.

Composant `r75x0.5` de `scripts/probe_blocs_vs_plantage.py`, fichier livré
`reports/serie_echelle_r75/cfg_x0.5.json`, 75 couches, mode deep, fente 2 nm, graine de recherche 101.
Les défauts courants de recherche locale et d'hystérésis restent actifs.
Le repère historique de 0,3967 nm ne suffit pas comme contrôle des défauts courants : une référence neuve est requise.

| ordre | cas | tours | arrêt sans gain | budget Rate | surcharge prévue |
|---|---|---:|---|---:|---|
| 1 | référence courante | 3 | oui | 120 | `elite_rounds=3`, valeur attendue du défaut deep, à vérifier au chargement |
| 2 | six tours sans arrêt | 6 | non | 120 | `elite_rounds=6,elite_stop_on_no_gain=false` |
| 3 | dix tours sans arrêt | 10 | non | 120 | `elite_rounds=10,elite_stop_on_no_gain=false` |
| 4 | petit budget | 3 | oui | 40 | `elite_rate_max_candidates=40` |
| 5 | grand budget | 3 | oui | 360 | `elite_rate_max_candidates=360` |

La comparaison six/dix tours isole le nombre de tours. Leur différence avec la référence combine nombre de tours
et règle d'arrêt ; elle ne sera pas attribuée aux seuls tours. Les deux budgets ne changent qu'un levier.
Chaque essai reçoit une étiquette unique, un emplacement neuf et un journal complet.

Commande de base de la sonde existante :

```text
python scripts/probe_blocs_vs_plantage.py r75x0.5 deep 0 0 2 0 101 0
```

Avant lancement : vérifier les paramètres réellement collectés après surcharge et leur passage au moteur ELITE.
`_resolve_elite_refinement_cfg` lit les tours et l'arrêt ; `_generate_elite_candidate_strategies` reçoit le budget Rate depuis les paramètres.
La sonde conserve ses surcharges et son étiquette ; celles-ci ne remplacent pas la vérification du raccordement.

Attention aux graines : la configuration conserve un consensus explicite tronqué à 41/42/43.
Changer `robustness_seed` ne crée donc pas une nouvelle banque de consensus. La même banque restera commune à ces cinq essais ;
aucune confirmation indépendante ni mesure de dispersion entre graines n'est revendiquée.

Le bilan donnera le SEEL homogène, la durée, les couches et le nombre de paquets Rate du meilleur plan,
les populations et les limites, sans modifier aucun défaut. Aucun nouveau lancement après 10 h Europe/Paris.

Le brouillon local `scratch/run_A5_tours_budgets.py` prépare ces cinq essais, avec une garde à l'entrée réelle de
`FullPipelineStrategy.execute`, après les surcharges : tours, arrêt, budget, géométrie, graines et paramètres physiques.
Il a été préparé avec `--prepare` après l'arrêt documenté d'A3 ; les cinq chargements réels passent avant création du worker.
Aucune mesure A5 n'a encore eu lieu à ce stade ; les audits dans le moteur restent obligatoires pendant les bancs.
Le critère principal réservé est le meilleur plan déposable dont le score de consensus est fini et dont les métadonnées
confirment `mean_std` et les graines 41/42/43. Le minimum du résumé historique est conservé séparément si sa provenance diffère.
Le nombre de paquets Rate vient de la fonction existante `scripts.resumer_artefact_sonde.paquets`.

Revue statique du brouillon : le contrôle observe aussi la résolution des tours et de l'arrêt dans le moteur,
puis le budget reçu par le générateur de candidats, en conservant leurs retours sans les modifier.
Il attend le profil deep courant : 300 tirages de robustesse et de consensus, mode `mean_std`, poids 0,35.
Ces attentes restent à éprouver à l'exécution. Les plans marqués `crash_eliminated` sont exclus du critère principal,
même si leur score de repli est fini. Toute absence du raccordement observé fait échouer l'essai.

La métadonnée `seeds` peut conserver la banque demandée alors qu'une évaluation a échoué :
le critère principal exige donc aussi `n_samples=3`. Si des plans déposables existent mais qu'aucun n'a
un consensus homogène complet, le pilote conserve l'artefact et s'arrête pour analyse de provenance.
Il ne relance pas une mesure déjà faite pour corriger seulement son dépouillement.
