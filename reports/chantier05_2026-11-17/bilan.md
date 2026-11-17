# Chantier 05 — l'ajustement Sellmeier de SUBSTRATE : temps et convergence (2026-11-17)

Code `e859f1ca`, aucun fichier de `certus/` modifié. Fonction : `certus_substrate_sellmeier.py::_fit_model_sellmeier3poles`,
réglages par défaut, 361 points de 380 à 1100 nm. Deux candidats, le plus proche des données est retenu : la variante A
(`n² = A + Σ Bi λ²/(λ² − Li²)`, dénominateurs planchers à 1e-15) et la variante standard 3 termes (`n² = 1 + Σ Bi λ²/(λ² − Ci)`,
Ci ≤ (0,995 λmin)²).

## Où passe le temps

[`p05_sellmeier_time_split.py`](p05_sellmeier_time_split.py) ([sortie](p05_sellmeier_time_split.txt)), BK7 bruité à 2e-5, à
chaud : 2,11 s, dont

| s | appels | évaluations | appel |
|---:|---:|---:|---|
| 1,85 | 1 | 3 000 | `least_squares(_std_residuals)`, différences finies : **budget `max_nfev` épuisé** |
| 0,24 | 12 | 3 568 | `minimize(_mse_full_q, L-BFGS-B)`, différences finies |
| 0,02 | 1 | 26 | `least_squares(_res5_q)` (graine) |
| 0,00 | 1 | 2 | `least_squares(_residuals_polish_q)`, Jacobien analytique |

88 % du temps est la variante standard, sans Jacobien, qui s'arrête sur son budget et non sur un critère de convergence.

## Convergence

[`p05_sellmeier_convergence.py`](p05_sellmeier_convergence.py) ([sortie](p05_sellmeier_convergence.txt)) :

| données | bruit | retenu (standard), écart à la courbe vraie | variante A seule |
|---|---:|---:|---:|
| tirées de la variante A, trois pôles UV dans les bornes | 2e-5 / 2e-7 / 0 | 2,7e-6 / 2,8e-8 / 9,5e-9 | 6,6e-3 / 7,1e-3 / 6,2e-3 |
| BK7 (Schott) | 2e-5 / 2e-7 / 0 | 2,9e-4 / 2,9e-4 / 2,9e-4 | 2,1e-3 / 4,6e-3 / **0,43** |

- **La variante A ne converge pas, même sur ses propres données.** Cause, mesurée : les graines placent L2 = 0,61 µm et
  L3 = 1,52 µm (`max(0,35, 1,6 λmin)`, `max(1,2, 4 λmin)`), au-delà de λmin = 0,38 µm ; le plancher des dénominateurs y rend
  le terme démesuré, L-BFGS-B colle B2 = B3 = 0, et le polissage s'arrête en 2 évaluations (`xtol`, optimalité 3e28) :
  la variante A ajuste A plus **un seul pôle**. Le Jacobien analytique du polissage est juste (écart relatif aux
  différences finies ≤ 1e-8) ; parti de la vérité × 1,05, le polissage rend 6e-15 en 19 évaluations.
- Les bornes de L2 et L3 (jusqu'à 40 µm) et la docstring de `_sellmeier_2poles_param_bounds` (« capturer la courbure IR »)
  promettent un pôle IR que le plancher interdit : aux coefficients de BK7 (L3 = 10,18 µm), la variante A vaut 3,5e7.
- **BK7 à 2,9e-4 est la limite du modèle**, pas un défaut de convergence : l'écart ne bouge pas quand le bruit est divisé
  par 100 puis annulé. Aucune des deux variantes n'a de pôle IR ; la variante standard, seule à converger, sauve l'ajustement.

## Décision à prendre (👤)

Le chantier 05 visait la vitesse (Jacobiens analytiques). Les mesures montrent d'abord un défaut de modèle, dont la
correction change des indices de substrat ajustés, donc des résultats physiques : elle n'est pas faite.

1. **Pôle IR** : un dénominateur signé (sans plancher) et des bornes disjointes (L1, L2 sous 0,97 λmin ; L3 au-dessus de
   λmax / 0,97), le Sellmeier de catalogue ; BK7 deviendrait représentable. Ou, a minima, borner L2 et L3 sous λmin comme
   L1 et corriger les graines.
2. **Vitesse**, indépendante : un Jacobien analytique pour `_std_residuals` (six paramètres, forme fermée) supprimerait
   l'essentiel des 1,85 s ; le résultat changerait aussi, puisque l'ajustement s'arrête aujourd'hui sur son budget.
