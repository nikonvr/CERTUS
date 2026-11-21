# Grille automatique de DESIGN dimensionnée par la TOT max ou le N max — 2026-11-21

Demandé par 👤 (article JOSS). Script : `mesure.py` ; sortie brute : `mesure.txt`.

## Règle

Avec la case **Automatic wavelength grid** cochée, la grille de base prend `3 · 4 · TOT · Δσ` intervalles par bande, avec
TOT = max(TOT de l'empilement, plafond). Le plafond vaut :

- la **Max TOT** (`max_total_qwot`, QWOT à l0), si elle est donnée ;
- sinon, avec un **Max layers** N (`max_layers`) : `N / (4 · 0,69 · ΣΔσ)` sur les bandes fusionnées
  (`certus.core.certus_design_auto_grid.layers_tot_ceiling_nm`). 0,69 est le plus petit rapport `N / (4 · TOT · ΣΔσ)` de
  l'enveloppe libre de la séparatrice 50/50, N = 8 à 34 (`questions_design_2026-11-13/bilan.md` §2.2). C'est une
  estimation empirique, pas une borne ;
- sinon, aucun plafond.

Les deux champs sont dans la fenêtre (0 = aucune limite) ; un fichier sans ces clés n'en a pas. Case décochée : rien ne
change. Sous la case, la fenêtre affiche la TOT retenue, sa source et les points par cible.

## Mesure

Fichiers `JSON-design-reference-tikhonravov-1996*.json` : 34 couches, 400–1200 nm, T = 0,5, `max_layers = 34`, sans
`max_total_qwot`. RMSE de DESIGN (poids du coût : cible × Δ ln λ), référence sur 40 001 points uniformes en nombre d'onde.

| design | grille | TOT (QWOT), source | points | écart sur le RMSE |
|---|---|---|---|---|
| publié | Points / Target 108 (fichier) | — | 108 | 4,38 % |
| publié | auto, sans limite | 31,4, empilement | 80 | 11,12 % |
| publié | auto, max layers 34 | 59,1, max layers | 149 | 1,65 % |
| publié | auto, max layers 34, affinée (3 tours) | 59,1, max layers | 420 | 0,01 % |
| départ | Points / Target 108 | — | 108 | 0,01 % |
| départ | auto, max layers 34 | 59,1, max layers | 149 | 0,22 % |

Le design publié a son propre rapport `N / (4 · TOT · Δσ)` = 34 / (4 · 3 924 · 1/600) = 1,30, dans la plage de
l'enveloppe (0,69 à 1,37). Un seul cas.
