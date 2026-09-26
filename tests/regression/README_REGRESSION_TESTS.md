# CERTUS — tests de convergence (Golden Master)

Ce dossier vérifie que l'**optimiseur** arrive toujours au même endroit sur des exemples
réels : la RMSE de chaque module ne doit pas dépasser sa référence de plus de 1 %. C'est
complémentaire de `tests/oracle/`, qui vérifie que la **physique** est juste : un refactor peut
laisser l'oracle vert et dégrader la convergence.

```bat
python -m pytest tests/regression/ -q --no-cov
python -m pytest tests/regression/ -q --no-cov -m "not slow"
python tests/regression/test_convergence.py
```

La première commande lance un vrai pipeline par module, en sous-processus (~3 min mesurées le
2026-09-26) ; la deuxième ne garde que les contrôles rapides ; la troisième imprime le rapport
lisible. `test_convergence_guard.py` porte les tests : il **appelle** les fonctions du script
`test_convergence.py` au lieu de les recopier.

**Les références sont dans `baseline_rmse.json`, et nulle part ailleurs.** Cinq modules sont
mesurés : RE, SPLINE, METAL_SINGLE, METAL_BILAYER et INDEX. Celle d'INDEX a été **capturée**
le 2026-09-08, pas validée : elle dit « pas pire qu'alors », pas « juste ».
`scripts/collect_rmse.py` régénère les références.

DESIGN et STRAT ne sont **pas** mesurables ici : leurs scripts headless remplacent le calcul
par un mock (voir `tests/headless/README.md`). Les rendre mesurables demande un script qui
exécute vraiment le pipeline.
