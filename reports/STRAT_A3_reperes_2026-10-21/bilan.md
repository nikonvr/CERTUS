# A3 — Repères officiels, 21 octobre 2026

## Protocole figé avant mesure

Code `37f27cb0` ; la tête exacte après ce protocole est consignée par le pilote dans `etat.json` au lancement.
Précontrôle : `PREFLIGHT=GO`, arbre suivi propre, aucun autre processus Python.
Une seule mesure à la fois ; aucun défaut scientifique modifié, aucun exemple édité.

| ordre | profil | couches chargées | mode | graine | fente (nm) | résultat |
|---|---|---:|---|---:|---:|---|
| 1 | juge de paix | 48 | premium | 42 | 2 | non mesuré |
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
python reports/STRAT_A3_reperes_2026-10-21/run_A3_official_benches.py.txt
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
