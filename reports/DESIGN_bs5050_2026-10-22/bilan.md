# DESIGN plus performant — séparatrice 50/50 400–1200 nm (2026-10-22/23)

Contraintes de 👤 : H/L seulement, indices inchangés, ≤ 34 couches, ≤ 30 QWOT. RMSE de T sur grille fixe de 0,5 nm,
recoupé par l'oracle indépendant. Leviers, commandes et mesures : [`journal.md`](journal.md).

## Résultats

| | RMSE (grille fixe) | couches · QWOT | temps |
|---|---|---|---|
| DESIGN avant la campagne (PGLOBAL) | 0,0018 – 0,0042 | 21 – 27 · ~19 | 1,5 – 2,5 min |
| DESIGN par défaut, `JSON-design-example.json` tel quel | **0,000135** – 0,000165 | 32 – 34 · 26,2 – 26,6, couches ≥ 5 nm | 21 – 48 min (8 fils) |
| DESIGN, problème de Tikhonravov et al. 1996 (34 couches) | **8,6e-5** contre 1,77e-4 pour leur design | 34 · 26,4 contre 31,4 | 47 min |
| DESIGN, même problème, courbe de 1 à 34 couches | 0,229 (1 c.) → 0,0151 (10 c.) → **0,000090** (34 c.) ; sous leur design dès 28 couches | sans plafond de QWOT | 1 min – 2 h 16 par point |
| Enveloppe globale hors fenêtre (2026-10-26, HL + LH, N ± p, Gauss-Newton) | libre : **3,53e-5** (34 c.), 3,72e-5 (31 c.) ; d ≥ 5 nm : **4,03e-5** (31 c.), 7,98e-5 (28 c.) ; sous leur design dès 23 couches | 29,8 QWOT à 34 c. | scripts de `tikhonravov/envelope_free/` ([README](tikhonravov/envelope_free/README.md)) |

- Autres problèmes publiés de Tikhonravov et Trubetskov (trois raies, miroir chaud, EF, cissoïde ; 2026-10-26 → 29) :
  [`tikhonravov/envelope_v2/README.md`](tikhonravov/envelope_v2/README.md) et son audit.
- Face à la littérature : MF 8,53e-3 contre 1,2767e-2 publié, écart max 0,024 % contre 0,193 % ;
  [`tikhonravov/README.md`](tikhonravov/README.md), courbe RMSE = f(couches) dans `tikhonravov/curve/`.
- Tolérance : sous des erreurs d'épaisseur de 0,1 % + 0,2 nm à 2σ, le RMSE moyen est d'environ 0,003 (± 0,0015) quel
  que soit le nombre de couches : ces designs sont limités par la fabrication, pas par l'optimiseur
  ([`final_runs/rmse_vs_layers.png`](final_runs/rmse_vs_layers.png)).
- Plancher : mémétique, relances et sonde finissent tous vers 1,5e-4 à 34 couches et 30 QWOT.

## Réglage par défaut (décisions de 👤 du 2026-10-23)

Étape globale mémétique, 1000 enfants, population 30 (`certus/core/certus_design_memetic.py`) ; champion Pareto sans
couche < 5 nm ; relances depuis le meilleur design tant qu'il gagne plus de 1 % (5 au plus). Le fichier de design peut
fixer `max_layers` (rempli avant le global, peut dépasser 100), `max_total_qwot`, `min_layer_ot_nm`, `floor_at_end`.
`_memetic_children = 0` sur la fenêtre rend PGLOBAL ; le mode oblique garde PGLOBAL.

## Défauts de DESIGN trouvés

| défaut | état |
|---|---|
| l'export écrivait un meilleur résultat d'une autre structure dans le tableau | corrigé (`76349415`) |
| le bloc `optim` des fichiers d'exemple était ignoré | corrigé (`a813fa64`) |
| la session de décimation Pareto ne se refermait jamais | corrigé (`08f7e7e6`) |
| la règle finale des 5 nm retire des couches sans réoptimiser | corrigé (non commité, 2026-10-26) : repolissage au-dessus du plancher (ALG-19) |
| l'étape globale PGLOBAL borne chaque couche à 1,2 QWOT | inchangé ; le mémétique monte à 5 QWOT, avec fusion N+2 → N |
| un design pouvait être exporté sous le RMSE d'un autre (champion Pareto) | corrigé (`0f11743f`) |
| `floor_at_end` (plancher en toute fin) : des couches fines réapparaissent après les aiguilles | ouvert, option inactive |
| scan Needle avec face arrière sans cache | corrigé (`c034ffe2`), ×14 à ×39, suivi au banc des noyaux |

## Ce qui attend

- `floor_at_end` à rendre fonctionnel dans le workflow, puis à mesurer contre le plancher tout du long.
- Optimiser le RMSE attendu sous erreurs d'épaisseur plutôt que le RMSE nominal (piste, non lancée).
- Écart non expliqué entre le RMSE de la fenêtre et celui de la grille fixe, même à 420 points par cible.
- Six pistes de temps de calcul : `docs/AUDITS.md`, ALG-23 à ALG-28 ; ALG-07, ALG-08, ALG-25 et ALG-30 (indices k ≤ 1e-4 en réel) intégrés le 2026-10-26, exactitude testée, **gains à chronométrer** dans la fenêtre. Registre : ALG-14 à ALG-30.
- Relancer la courbe 1–34 dans la fenêtre DESIGN avec les correctifs du 2026-10-26, pour mesurer ce que DESIGN retrouve seul de l'enveloppe hors fenêtre.
- Bonne Mère : [`../BONNE_MERE_design_2026-10-23/README.md`](../BONNE_MERE_design_2026-10-23/README.md).
