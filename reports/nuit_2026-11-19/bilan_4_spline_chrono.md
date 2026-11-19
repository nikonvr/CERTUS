# Lot 4 — chronométrage de Smart Init et des nœuds libres de SPLINE (2026-11-20)

Règle (`docs/CHANTIERS_RESTANTS.md`, chantier 21) : dérivées analytiques pour un étage qui dépasse **20 %** du temps et
**5 s** ; sinon archiver 21. [Sonde](p4_spline_chrono.py) ([sortie](p4_spline_chrono.txt)), machine libre, configuration de
la fenêtre, défauts actuels, une chauffe puis trois tours, médianes.

| classeur | run principal | Smart Init (Swanepoel) | passe 2 Auto-Best (nœuds libres) | RMSE principal → passe 2 |
|---|---:|---:|---:|---|
| TOTAL | 2,92 s | 0,001 s (0,0 %) | **6,99 s (70,5 %)** | 0,0512780 → 0,0512778 |
| TSIO2 | 2,79 s | 0,001 s (0,0 %) | **34,15 s (92,4 %)** | 0,0019472 → 0,0019174 |

- **Smart Init** : négligeable, sous le seuil.
- **Nœuds libres** : l'étage historique du pipeline a été retiré (`[03/09]`) ; il ne tourne plus qu'en passe 2 d'Auto-Best
  (`worker_auto_best_split_knot_refinement`). **Il plantait à chaque passe** (`IndexError` dans `phase_progress_bounds`)
  depuis le découpage `0b7f4f0d` : le contexte gardait `phase_maxfun_list=[]`. Corrigé (test rouge
  `test_auto_best_pass_two_gets_its_phase_budgets.py`). Une fois réparée, la passe 2 franchit le seuil sur les deux
  exemples, pour un gain de RMSE nul sur TOTAL et de −1,5 % sur TSIO2.

**Suite** : la règle désigne les dérivées analytiques de la passe 2 (nœuds σ libres pour n et ln k).
