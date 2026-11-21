# REPRISE — grille automatique de DESIGN dimensionnée par la TOT max ou le N max (2026-11-21)

Demande : article JOSS, fonction distinctive de DESIGN. Pousser : jamais sans ordre de 👤.

Règle retenue (👤 2026-11-21) : TOT plafond = N_max / (4 · 0,69 · ΣΔσ) (degrés de liberté, rapport
`questions_design_2026-11-13/bilan.md` §2.2), r = `LAYERS_PER_NYQUIST_MIN`. Si la TOT max est donnée, elle l'emporte
(confirmé par 👤). Jamais sous la TOT de l'empilement. Ruff : le dossier non suivi `reports/RICL_campagne24h_2026-11-20/`
est exclu de la validation (accord de 👤). Commits : trois commits locaux après `VALIDATION=GO` (ordre de 👤), sans pousser.

## Fait

- [x] Cœur `certus/core/certus_design_auto_grid.py` : `LAYERS_PER_NYQUIST_MIN`, `layers_tot_ceiling_nm`,
      `points_in_bands`, `auto_grid_tot_nm(..., max_layers=, bands=)` ; tests unitaires rouges puis verts (20 passed).
- [x] Fenêtre : champs Max layers / Max TOT (QWOT), table déclarative, libellé de la grille ; tests ui rouges puis verts
      (26 passed avec l'aller-retour et les limites du fichier).
- [x] Mesure sur `JSON-design-reference-tikhonravov-1996*.json` (`mesure.py`, `mesure.txt`, `bilan.md`).
- [x] `pages/CERTUS_DESIGN.html` (#design-options, limites) et `docs/ETAT.md` §0 ; trois contrôles doc : code 0.
- [x] Tests légers pendant la campagne : 40 fichiers unit qui lisent les sources changées, 595 passed.
- [x] Tests ui DESIGN (15 fichiers) et 4 contrôles d'ergonomie, en série : 159 passed, 2 xfailed (29 min).

- [x] Validation complète (12:35-13:05, `validation.txt`) : `VALIDATION=GO` (un artefact de charge en unit, STRAT, vert
      seul en série) ; ruff vert hors dossier de campagne ; `c1_diff.py HEAD` : 9 172 tableaux identiques au bit.
- [x] Trois commits locaux, sans pousser (ordre de 👤) : cœur `8a331749`, fenêtre `c42e83e5`, docs (ce dossier).

## À faire

- [ ] Pousser : seulement sur ordre de 👤.
