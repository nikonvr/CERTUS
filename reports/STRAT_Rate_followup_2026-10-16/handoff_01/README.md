# Passation de la suite Rate,16octobre2026

Lire d'abord [le diagnostic complet](../../STRAT_Rate_reprise_20261016.md).
Il distingue programme clos, suite autorisée, preuves, limites et prototype non vérifié.

Les fichiers `sources/*.txt` sont des copies des bytes réellement présents dans `scratch/`.
`sources_sha256.json` en donne les empreintes. Pour restaurer les outils locaux après
un clone, créer `scratch/` puis copier chaque `*.py.txt` vers son nom sans le dernier
`.txt`, après vérificationSHA. Refuser d'écraser une copie locale différente sans audit.

Le script `audit_rate_followup_recorded_20261016.py` a terminé : zéroappel physique,
87252paires de tâches sous une clé plus stricte,8vecteurs de plantage différents ;
les paramètres complets historiques manquent toujours. Il trouve aussi la fenêtre48c
`[9,11)` admissible après rejet de `[36,38)` ; aucun correctif scientifique n'est écrit.

`rate_followup_controlled_20261016.py` est un **prototype non vérifié**. Sa seule tentative
`prepare` finit en sortie1 sur l'accès sandbox au worktreeR5, pendant l'import de
`bench_examples.py`, avant application/claim/mesure. Voir `preparation_failure.json`.
Ne pas lancer ses modes `h03` ou `R5`. Préparer une copie nouvelle et `controlled_02`,
vérifier les chemins réels, toutes les entrées/paramètres et les gardes avant toute mesure.

Les deux autres sources copiées sont des dépendances techniques déjà utilisées :
`campagne_a2_runner.py` fournit `limit_resources` ; `rate_R4_planner_resume_v3.py` fournit
la sauvegarde atomique bornée. Les copier ne rend pas leurs anciennes campagnes relançables.

Les preuves volumineuses sont restaurables via
[les manifestes de publication](../../STRAT_Rate_publication_2026-10-16/README.md).
Exemple pour une trace nécessaire au diagnostic enregistré :

```powershell
python scripts\restore_rate_evidence.py --path reports/STRAT_Rate_suite_2026-10-15/R5_integration/native/measurement/pipeline_trace.json
python scripts\restore_rate_evidence.py --path reports/STRAT_Rate_suite_2026-10-15/R3_h03_native_postrefinement/variant/pipeline_trace.json
```

Le suivi historique restePAUSED. Les demandes ultérieures de l'utilisateur autorisent
le commit/push et le ménage ; elles n'activent aucun défaut scientifique. Les archives
conservent les résultats et leurs SHA ; les caches compilés supprimés sont régénérables.
