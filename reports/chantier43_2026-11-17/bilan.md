# Chantier 43 — durée de `tests/ui/`, 2026-11-17

Commande : `python scripts\validate_parallel.py --only ui --workers 30 --ui-workers W --no-confirm`, sur `2e89294b`,
32 cœurs, Python 3.15.2, une mesure à la fois (aucun autre processus python). Résumés dans `preuves/`.

| arbre | W | durée | résultat |
|---|---:|---|---|
| `D:` (dossier synchronisé) | 6 | 9:53 | 1667 passed, 12 skipped, 2 xfailed |
| `C:\certus_clone` (clone neuf, cache Numba vierge) | 6 | 10:14 | idem |
| `D:` | 10 | 5:52 | idem |
| `D:` | 10 | 5:38 | idem |
| `D:` | 12 | 5:44 | idem |

- Le disque n'est pas la cause : le clone sur `C:` n'est pas plus rapide. Il partait sur cache vierge, ce qui le
  désavantage ; l'écart (+21 s) reste dans ce que coûte la compilation.
- Le nombre de workers l'est : 10 workers divisent la durée par 1,7, deux fois sur deux ; 12 n'apporte rien.
  `UI_WORKERS` passe de 6 à 10. Mesuré sur 32 cœurs seulement ; à 16 workers, l'audit d'ergonomie échouait (2026-10-18).
- Ne dit rien des fichiers revenus à leur version du 16 novembre ce matin : leur cause reste non prouvée.
