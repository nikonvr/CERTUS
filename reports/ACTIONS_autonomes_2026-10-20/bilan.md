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
| A8, corrections simples | prochaine action : un défaut isolé, preuves avant/après |
| A3 | ensuite : refaire les repères officiels |
| A5 | ensuite : mesurer tours et budgets Rate |
| A4 | ensuite : parents optiques garantis, chemin nul identique au bit |
| A10 | ensuite : comparer les corridors et confirmer sur graines neuves |
| A9 | ensuite : protocole borné 99 couches et confirmation indépendante |
| A8, structure | en dernier : reproduire chaque défaut avant correction |

Les actions non mesurées restent ouvertes. Aucun nouveau SEEL n'est encore acquis par cette campagne.

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
