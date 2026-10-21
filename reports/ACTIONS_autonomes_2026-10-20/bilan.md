# Actions autonomes — 20 octobre 2026

## Reprise

Branche `codex/actions-prudentes-2026-10-20`, départ `96128ba5`. Travail séquentiel, sans agent secondaire ni push.
Le répertoire d'origine et ses modifications antérieures sont préservés.
Bilan prévu le 21 octobre 2026 à 10 h, Europe/Paris ; reprise automatique dans cette conversation toutes les 30 minutes jusque-là.

| action | état et prochaine étape |
|---|---|
| A1, A2 | déjà terminées dans la feuille de route |
| A6 | retirée sur ordre du propriétaire ; `619d84eb` |
| A7 | terminée : [neuf passages et propositions sourcées](../STRAT_vitrine_passages_a_relire_2026-10-20.md), page inchangée |
| A8, corrections simples | premier correctif terminé, `37f27cb0` : trois photos identiques, validation complète ; dette restante ouverte |
| A3 | six repères officiels publiés dans ETAT §2 ; douze intervalles mesurés, mais assemblage non conforme à C2 (flux et domaines d'indice différents) ; aucun score 99 couches retenu, [diagnostic et prototype bloqué](../STRAT_A3_C2_assemblage_2026-10-21/bilan.md) ; action partielle |
| A5 | [protocole préparé](../STRAT_A5_tours_budgets_2026-10-21/bilan.md), cinq workflows réellement chargés et vérifiés avant worker ; après commit, référence courante puis quatre variantes de tours/budget |
| A4 | ensuite : parents optiques garantis, chemin nul identique au bit |
| A10 | ensuite : comparer les corridors et confirmer sur graines neuves |
| A9 | ensuite : protocole borné 99 couches et confirmation indépendante |
| A8, structure | en dernier : reproduire chaque défaut avant correction |

Les actions non mesurées restent ouvertes.

## Validation initiale

Code `96128ba5`, inchangé pendant les tests ; seuls les documents du retrait d'A6 ont été modifiés.
Commandes exécutées successivement, sans autre calcul sur la machine.

```text
python scripts/preflight.py
PREFLIGHT=GO

python -m ruff check .
All checks passed!

python -m pytest tests/oracle/ -q --no-cov -x
1148 passed in 59.82s

python -m pytest tests/unit/ -q --no-cov -x
5591 passed, 7 skipped, 1 xfailed in 1768.45s (0:29:28)

python -m pytest tests/ui/ -q --no-cov -x
1324 passed, 12 skipped, 2 xfailed in 1699.70s (0:28:19)

python -m pytest tests/ -q --no-cov -x --ignore=tests/oracle --ignore=tests/unit --ignore=tests/ui -o faulthandler_timeout=900
359 passed, 17 warnings in 845.49s (0:14:05)

python scripts/coherence_md.py
0 point(s) a instruire.

python scripts/check_claude_md.py
CONTRADICTIONS MECANIQUES : 0

python scripts/check_docs.py
DEFAUTS MECANIQUES : 0
```

Total : 8 422 réussis, 19 ignorés, 3 échecs attendus, aucun échec inattendu.
La dernière suite, interrompue sans bilan, a été relancée seule et s'est terminée avec succès.
Ses 17 avertissements comprennent une dépréciation NumPy 2.5 dans pyqtgraph.

### Limite de reproductibilité documentaire

Dans un arbre Git neuf, `coherence_md.py` échoue sur quatre commandes historiques : leurs scripts existent dans le répertoire d'origine, mais ne sont pas versionnés.
Une copie locale exacte a été faite sous `scratch/`, sans les exécuter ; les quatre SHA-256 source/copie sont identiques.
Après copie, les trois contrôles documentaires passent. Leur succès dépend donc de fichiers locaux supplémentaires :

- `rate_fixed_replay_R0_suite.py`
- `rate_followup_controlled_20261016.py`
- `rate_native_pipeline_probe.py`
- `verify_rate_native_pipeline_trace.py`

Le contrôle de départ du répertoire d'origine échouait sur le dossier non suivi `snom/` et une modification antérieure de `docs/ETAT.md`.
L'arbre isolé a obtenu `PREFLIGHT=GO` sans les modifier. Le commit `619d84eb` a réussi malgré les avertissements Git de nettoyage d'anciennes entrées de worktree refusé par Drive.

## A8 — Imports de l'état de l'interface STRAT

Seul code modifié : `certus/ui/certus_strat_ui_state.py`. Trois imports remontés avant les fonctions, deux suppressions E402 devenues inutiles retirées. Aucun corps de fonction, paramètre ou noyau modifié ; aucun ignore élargi.

Le premier passage unitaire s'est arrêté après 4 385 réussites : le cliquet exige de conserver la réduction du fichier (1 725 → 1 722 lignes). `metrics.py --dette` a modifié cette seule borne dans le registre, sans ajouter de dette ; l'échec et son journal sont conservés avant la relance.

Mesure officielle isolée de D25 : E402 553 → 552 ; total 1 493 → 1 492. Les autres comptes sont inchangés : F401 668, RUF001 147, RUF003 59, RUF002 51, RUF100 10, RUF022 3, F811 2.
Le fichier corrigé passe E402, I et RUF100 avec les contrôles isolés.

Trois photos avant/après, source de départ `e369c324` :

- Espace de noms : identique octet pour octet avec `PYTHONHASHSEED=0`. Le premier essai, sans graine de hachage fixée, différait seulement par l'ordre de représentation du même `frozenset` ; les deux données brutes sont conservées.
- Modules chargés : identiques pour les onze points d'entrée après import de leur module et achèvement du vrai préchauffage de fond. Ce diagnostic ne lance pas la boucle graphique ; les tests d'interface assurent le contrôle graphique séparé.
- Noms servis par les façades : tous identiques.

L'utilitaire de lissage avait initialement deux modules Numba supplémentaires (`numba.core.boxing`, `numba.core.runtime.context`). Il ne charge pas le fichier modifié. Rejoué avec la source d'origine, il donne exactement la photo après modification ; ce contrôle est conservé, aucun module n'a été retiré des comparaisons.

Validation du 21 octobre : Ruff passe ; oracle `1148 passed in 12.84s` ; unité après baisse du plafond `5591 passed, 7 skipped, 1 xfailed in 929.80s (0:15:29)` ; interface `1324 passed, 12 skipped, 2 xfailed in 1472.34s (0:24:32)` ; reste `359 passed, 18 warnings in 670.96s (0:11:10)`. Chaîne terminée à 00 h 58, aucune suite active. Total : 8 422 réussis, 19 ignorés, 3 échecs attendus. Les 18 avertissements du reste sont la dépréciation NumPy 2.5 de pyqtgraph, également présente dans la référence.

[Archive des 45 preuves](A8_imports_preuves.zip), SHA-256 `731e103757d958abb4cf4fc6a740aa3e8db7b2818ff89e7b47bce2e3167fa4ad` : trois photos, contrôle de lissage, copies des sources, outil, journaux et état final, premier échec inclus. Les chemins des journaux y sont neutralisés ; les originaux restent dans `scratch/A8_e402_ui_state_20261020/`. Contrôles documentaires : `coherence_md.py`, `check_claude_md.py`, `check_docs.py`. Après le commit local de ce correctif : `python scripts/preflight.py`, puis préparer A3 et vérifier ses paramètres chargés avant mesure. Le reste d'A8 n'est pas terminé.

## A3 — Défaut de transmission corrigé et validé

Précontrôle après `37f27cb0` : `PREFLIGHT=GO`, arbre propre, aucun autre Python. Six profils préparés, tous vérifiés par le chargeur et `collect_params` (`A3_PARAMS=GO`), programme et sources figés : [protocole et preuves](../STRAT_A3_reperes_2026-10-21/bilan.md). Les différences 35/36 couches, le mode livré de random75 et les limites du cache 99 couches y sont consignés.

Le premier banc s'est arrêté sur un vrai `AttributeError` avant émission du résultat, au code `58ff57c5`. Le pilote a refusé `RESULT=None` et n'a lancé aucun autre composant. [Preuves, diagnostic et validation complète](../STRAT_A3_reperes_2026-10-21/bilan.md#échec-réel-et-correction-validée). Une ligne de `certus_strat_workers_pipeline.py` corrigée : accès à la clé du résultat hérité, aucun algorithme ni défaut modifié. Le nouveau test de frontière échoue avant et passe après, en couvrant aussi le chemin désactivé et le refus de la recherche locale.

Correctif committé localement `cd481836` : 8 425 réussis, 19 ignorés, 3 échecs attendus ; Ruff et les trois contrôles documentaires passent. L'échec documentaire initial et sa correction sont conservés dans l'archive, avec l'essai officiel et le test rouge/vert. Le précontrôle de reprise donne `PREFLIGHT=GO`, puis les six profils à nouveau chargés donnent `A3_PARAMS=GO`.

Le [nouveau protocole A3](../STRAT_A3_reperes_reprise_2026-10-21/bilan.md) réserve les six bancs et la partition historique 99 couches sur la banque de robustesse 42/101/202 ; syntaxe des pilotes et préparation contrôlées, aucune recherche de nouvelle partition ni confirmation indépendante. Après commit du protocole, lancer sa chaîne PowerShell depuis `reports/STRAT_A3_reperes_reprise_2026-10-21/run_suite.ps1`. Les états `etat.json` et `intervalles_etat.json` de ce nouveau dossier sont l'autorité pour la mesure active et les étapes terminées ; attendre la sortie réelle des processus. Pendant toute la chaîne, ne modifier aucun fichier suivi ni committer. Après sa fin, dépouiller les sorties et reprendre les actions suivantes. Ne pas reprendre l'ancien état avec une tête différente.
