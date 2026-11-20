# Chantiers restants — 20 novembre 2026

Ouverts seuls. Dépendances d'abord ; C3 (`CLAUDE.md §5`) ; valider entre lots.

| Lot | Prio | Chantier | Contenu et garde-fous | Fin ou arrêt | Src |
|---|---|---|---|---|---|
| **7** | P2 | Contrôle de la recherche locale | Défaut de `strat_local_search_check_seeds` : 2 (le contrôle d'avant) ou 6. Mesuré à 6 (35c, 36c, graine 42) : verdict du plan final inchangé, repli du 36c refusé (RESULT +13 %) ; proposé : garder 2 et comparer par `STRAT_BEST_ELITE`. | Décision 👤. | [7](../reports/chantier07_2026-11-20/bilan.md) |
| **8** | P2 | Bancs STRAT et cache Numba | Cause mesurée (20/11) : STRAT est déterministe à cache donné (deux runs libres et un run sous charge identiques au bit) ; sur cache Numba vierge, le 36c rend 1 446 stratégies au lieu de 1 436 (RESULT à 3e-14) : les noyaux `fastmath` changent de derniers bits selon le contexte de compilation. Décision 👤 : bancs officiels sur cache vierge, ou cache Numba propre à la validation. | Décision 👤. | [8](../reports/chantier08_2026-11-20/bilan.md) |

- **Hors-IA (👤)** : 5 PR Dependabot #10–#14 (41, GitHub) ; essais U13 (33, [protocole](../reports/refactor_corridors_2026-11-11/U13_protocole.md)) ; Zenodo `certus_re` & Tikhonravov 1996.
