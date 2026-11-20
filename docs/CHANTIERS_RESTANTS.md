# Chantiers restants — 20 novembre 2026

Ouverts seuls (archivés : **31**, **32**, **26** ; lots 1a, 1b, 2a, 2b, 2c, 2d et 3 faits la nuit du 19 au 20 :
[reprise](../reports/nuit_2026-11-19/REPRISE.md)). Dépendances d'abord ; C3 (`CLAUDE.md §5`) ; valider entre lots.

| Lot | Prio | Chantier | Contenu et garde-fous | Fin ou arrêt | Src |
|---|---|---|---|---|---|
| **5** | P2 | DYN-ALERT et `avg_dynamics` | La sentinelle `dyn = −1` (couche Rate non surveillée) entre dans `avg_dynamics` (`certus_strat_batch.py`) et dans la comparaison `[DYN-ALERT]` (`certus_strat_robustness_task.py`) : fausses alertes (425 Mo de journaux par série de bancs) et `_worst_layer_swing` désigne une couche Rate. Moyenner les seuls tirages surveillés, ne pas alerter sur la sentinelle ; diagnostic et export seulement, test rouge + `c1_diff.py HEAD`. | Alertes vraies seules ; RESULT au bit. | [lot 3](../reports/nuit_2026-11-19/lot3/bilan.md) |
| **6** | P2 | Écarts 35c / 36c | Repères du 20/11 : vrai 35c deep −29 %, 36c deep livré +12 % contre le 21/10 (au-delà de σ ≈ 6 %). Isoler la cause (recherche locale, consensus, arrêt tardif, correctifs du 19/11) avant de les adopter. | Cause mesurée. | [lot 3](../reports/nuit_2026-11-19/lot3/bilan.md) |
| **4** | P3 | SPLINE (21) | Passe 2 d'Auto-Best (nœuds libres) réparée ; 70 % (TOTAL) et 92 % (TSIO2) du temps, gain RMSE 0 et −1,5 % : seuil franchi. Décision 👤 : jac hybride (d et valeurs analytiques, σ par DF), budgets réduits, ou statu quo. | Décision 👤. | [21](../reports/nuit_2026-11-19/bilan_4_spline_chrono.md) |

- **Décisions 👤** : dénormaliser une référence normalisée (T/T_sub) pour RE (10 références sur 11 ; `certus_depots_re.py` les refuse) ; lot 4.
- **Hors-IA (👤)** : 5 PR Dependabot #10–#14 (41, GitHub) ; essais U13 (33, [protocole](../reports/refactor_corridors_2026-11-11/U13_protocole.md)) ; Zenodo `certus_re` & Tikhonravov 1996.

## Sources

- **Nuit du 19 au 20** : [reprise](../reports/nuit_2026-11-19/REPRISE.md) · [2c](../reports/nuit_2026-11-19/bilan_2c_sellmeier_ir_pole.md) · [lot 3](../reports/nuit_2026-11-19/lot3/bilan.md) · [gel](../reports/nuit_2026-11-19/gel/bilan.md).
