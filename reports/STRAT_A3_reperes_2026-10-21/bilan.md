# A3 — Repères officiels, 21 octobre 2026

## Protocole figé avant mesure

Code `37f27cb0` ; la tête exacte après ce protocole est consignée par le pilote dans `etat.json` au lancement.
Précontrôle : `PREFLIGHT=GO`, arbre suivi propre, aucun autre processus Python.
Une seule mesure à la fois ; aucun défaut scientifique modifié, aucun exemple édité.

| ordre | profil | couches chargées | mode | graine | fente (nm) | résultat |
|---|---|---:|---|---:|---:|---|
| 1 | juge de paix | 48 | premium | 42 | 2 | échec : `RESULT=None` |
| 2 | random75 livré | 75 | fast | 42 | 2 | non mesuré |
| 3 | vrai 3 cavités, dérivé | 35 | deep | 42 | 2 | non mesuré |
| 4 | 3 cavités deep livré | 36 | deep | 42 | 2 | non mesuré |
| 5 | r75x2 natif | 75 | deep | 42 | 1 | non mesuré |
| 6 | r75x2 avec rampes livrées | 75 | deep | 42 | 2 | non mesuré |

Le JSON livré `JSON-strat-bandpass-3cav-deep.json` comporte 36 couches. Le vrai 35 couches provient de
`JSON-strat-bandpass-3cav.json`, avec le seul changement `execution_mode=premium → deep` :
[profil dérivé figé](config_35c_deep_A3.json). Ils ne sont pas interchangeables.
Le mode livré de random75 est `fast` ; il est conservé.

[Identités et règles d'acceptation](protocole.json), [337 sources SHA-256](sources_sha256.json),
[paramètres réellement collectés](params_effectifs.json), [programme du contrôle](verify_A3_loaded_params.py.txt).
Les six chargements passent : couches, mode, graine et graine de phase A, fente, corridor 0,005,
recherche locale active, plancher d'hystérésis 0,000415 et identité de l'injection attendue.
Le contrôle utilise le chargeur officiel et `collect_params`, sans lancer de recherche.

Commande de lancement, depuis la racine de l'arbre, après commit de ce protocole :

```text
python "reports/STRAT_A3_reperes_2026-10-21/run_A3_official_benches.py.txt"
```

Le [pilote figé](run_A3_official_benches.py.txt) appelle, pour chaque profil, le banc officiel :

```text
python scripts/bench_examples.py strat --auto-yes --out <nouveau-fichier.txt>
```

Il fixe `CERTUS_DESIGN_JSON`, `CERTUS_BENCH_TIMEOUT_S=21600`, Qt hors écran, et retire les surcharges de sonde.
Chaque tentative conserve la sortie officielle, `RESULT`, le classement `STRAT_RANK00..09`, le journal brut,
les durées, les SHA et le code de sortie. `RESULT=None`, délai dépassé, absence de classement ou repli
`crash_eliminated` ne sont pas un succès. Le SEEL est calculé par le convertisseur existant
`scripts.resumer_artefact_sonde.seel`, sans nouvelle formule de physique.

La graine 42 est réservée ici aux repères de recherche : aucune confirmation indépendante n'est revendiquée.
Les composants et les modes ne constituent pas des comparaisons appariées entre eux.
La tête, les sources et les entrées restent fixes pendant la séquence ; les états vivants et journaux sont non suivis.
Une reprise exige de vérifier les processus, puis d'employer `--resume-interrupted` ; les essais terminés ne sont pas rejoués.
Aucun nouveau lancement après le 21 octobre à 10 h Europe/Paris ; une mesure engagée conserve le droit de finir.

## Partie 99 couches encore ouverte

Le repère à quatre témoins doit être refait par intervalles. Le cache de `campagne_intervalles.py` teste
seulement les bornes et la graine, sans vérifier le commit ; il faut un nouveau dossier de cache.
`get_cache` reconstruit directement le chemin, donc changer seulement `CACHE_BASE` ne suffit pas.
Son option `--limite` est déclarée mais n'est pas consultée dans la boucle : le prochain pilote doit protéger
chaque lancement lui-même. Aucun ancien cache ne doit être effacé ou traité comme une nouvelle mesure.

Les six bancs ci-dessus ne clôturent donc pas A3. Le SEEL historique de 0,81 nm sur trois graines n'a pas été remesuré ici.

## Échec réel et correction validée

Premier essai au commit `58ff57c5`, du 21 octobre 01 h 04 à 01 h 24 Europe/Paris :
`RUN_S=1208.810`, `WAIT_EXIT=error`, `RESULT=None`, malgré un code de sortie 0.
Le pilote a refusé ce résultat et s'est arrêté ; aucun des cinq autres bancs n'a été lancé.
État détaillé et SHA des sorties : `etat.json`. Les journaux, sorties et exports intermédiaires sont conservés.
Aucun SEEL de cet essai n'est un nouveau repère validé.

Cause reproduite : `_finalize_and_export_pipeline_results` renvoie le dictionnaire produit par
`WorkerThreadResult.for_step_23(...).to_legacy_dict()`. Dans `FullPipelineStrategy.execute`, l'ajout du compte rendu
de recherche locale utilisait l'attribut `.final_results`, d'où `AttributeError` avant l'émission de fin.
Correction bornée : accès à la clé `['final_results']`, sans modifier calcul, plans, graines ou défauts.

Le test de frontière exécute la vraie méthode avec les phases numériques et les fils Qt simulés,
et un vrai dictionnaire du DTO. Sur le code initial : `1 failed, 9 passed in 3.16s`, sur l'`AttributeError` observée.
Après correction : `11 passed in 1.27s`, dont les chemins désactivé, recherche acceptée et recherche refusée.
Il remplace l'assertion textuelle qui exigeait précisément l'accès fautif.
Validation complète : Ruff passe ; oracle `1148 passed in 10.48s` ; unité `5594 passed, 7 skipped, 1 xfailed in 949.02s (0:15:49)` ;
interface `1324 passed, 12 skipped, 2 xfailed in 1461.37s (0:24:21)` ; reste `359 passed, 18 warnings in 612.97s (0:10:12)`.
Total : 8 425 réussis, 19 ignorés, 3 échecs attendus, aucun échec inattendu. Les trois contrôles documentaires passent.
Le premier contrôle de cohérence a tronqué le nom `.py.txt` en `.py` ; la commande a été mise entre guillemets,
sans créer de fichier factice ni modifier le contrôleur. Cet échec et sa reprise sont conservés.

[Archive des 24 preuves](correctif_transmission_preuves.zip), SHA-256
`df159a8579a549b1db6bf2288b60354dfaf6acb00190833750290375bc4e46a0` : essai officiel échoué, journaux de validation,
sources avant/après, diff et test rouge/vert. Le manifeste distingue les SHA originaux des fichiers normalisés pour les chemins.

La reprise utilisera un nouveau dossier et une nouvelle tête, avec entrées et pilote à nouveau figés ;
`--resume-interrupted` sur cet état ne convient pas après changement du code.
Le correctif est committé `cd481836` ; [nouveau protocole et reprise](../STRAT_A3_reperes_reprise_2026-10-21/bilan.md).
