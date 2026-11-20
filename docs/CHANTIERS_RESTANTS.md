# Chantiers restants — 20 novembre 2026

Ouverts seuls (archivés : **31**, **32**, **26** ; lots 1a, 1b, 2a, 2b, 2c, 2d, 3, 4 (21 archivé) et chantiers 5, 6 faits la nuit du 19 au 20 ; chantiers 7 et 8 mesurés le 20 :
[reprise](../reports/nuit_2026-11-19/REPRISE.md)). Dépendances d'abord ; C3 (`CLAUDE.md §5`) ; valider entre lots.

| Lot | Prio | Chantier | Contenu et garde-fous | Fin ou arrêt | Src |
|---|---|---|---|---|---|
| **7** | P2 | Contrôle de la recherche locale | Fait (20/11) : `STRAT_BEST_ELITE` publié par le banc ; réglage `strat_local_search_check_seeds` (2 par défaut) mesuré à 6 : verdict du plan final inchangé (35c gardé, 36c refusé), le repli du 36c est refusé (RESULT +13 %). Proposition : garder 2 et comparer par `STRAT_BEST_ELITE`. | Décision 👤 sur le défaut. | [7](../reports/chantier07_2026-11-20/bilan.md) |
| **8** | P2 | Bancs STRAT et cache Numba | Cause mesurée (20/11) : STRAT est déterministe à cache donné (deux runs libres et un run sous charge identiques au bit) ; sur cache Numba vierge, le 36c rend 1 446 stratégies au lieu de 1 436 (RESULT à 3e-14) : les noyaux `fastmath` changent de derniers bits selon le contexte de compilation. Décision 👤 : bancs officiels sur cache vierge, ou cache Numba propre à la validation. | Décision 👤. | [8](../reports/chantier08_2026-11-20/bilan.md) |

- **Décidé par 👤 (20/11)** : RE garde le refus des références normalisées ; budgets de la passe 2 SPLINE au quart ; fusion locale dans `master`.
- **Hors-IA (👤)** : 5 PR Dependabot #10–#14 (41, GitHub) ; essais U13 (33, [protocole](../reports/refactor_corridors_2026-11-11/U13_protocole.md)) ; Zenodo `certus_re` & Tikhonravov 1996.

## Sources

- **Nuit du 19 au 20** : [reprise](../reports/nuit_2026-11-19/REPRISE.md) · [2c](../reports/nuit_2026-11-19/bilan_2c_sellmeier_ir_pole.md) · [lot 3](../reports/nuit_2026-11-19/lot3/bilan.md) · [gel](../reports/nuit_2026-11-19/gel/bilan.md).
