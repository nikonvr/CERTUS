# Chantier 05 — option pôle infrarouge de l'ajustement Sellmeier de SUBSTRATE (2026-11-18)

Décision de 👤 du 17 : pôle infrarouge de catalogue derrière une option inactive par défaut. Diagnostic : [bilan du 17](../chantier05_2026-11-17/bilan.md).

## Ce qui change

`certus_substrate_sellmeier.py` : `sellmeier_ir_pole_eval` (n² = A + Σ Bi λ²/(λ² − Li²), dénominateurs **signés**) et
`_fit_sellmeier_ir_pole` : L1, L2 sous 0,97 λmin, L3 au-delà de λmax / 0,97 (jusqu'à 40 µm), bornes prises sur toute la plage
évaluée, donc aucun pôle dans la courbe rendue ; graines par moindres carrés non négatifs sur une grille de pôles (n² linéaire
en A, Bi à pôles fixés), puis polissage borné à Jacobien analytique des trois meilleures. Avec `sellmeier_ir_pole=True`
(`_fit_model_sellmeier3poles`, `IndexCore.fit_sellmeier`, `IndexCore.get_smoothed_and_fits`), ce candidat
`analytic-sellmeier-3poles-ir` rejoint les deux autres ; le plus proche des données est retenu, comme avant. Loi et
coefficients affichés pour la nouvelle source. L'interface ne l'expose pas.

## C1

[`p05_c1_default_path.py`](p05_c1_default_path.py) : 20 tableaux (courbes, sources, coefficients, `IndexCore.fit_sellmeier`)
sur BK7 et sur des données de la variante A, bruit 2e-5 et 0, code d'avant (`git stash`) contre code d'après : **0 différent
au bit** ([sortie](p05_c1_default_path.txt)).

## Mesure

[`p05_ir_pole_on_off.py`](p05_ir_pole_on_off.py) ([sortie](p05_ir_pole_on_off.txt)), écart rms à la courbe vraie, à chaud :

| cas | défaut, σ = 2e-5 / 2e-7 / 0 | option, σ = 2e-5 / 2e-7 / 0 | durée défaut → option |
|---|---|---|---|
| SiO2, BK7, D263, saphir, B270 (380–1100 nm) | 2,5e-4 à 4,3e-4, sans suivre le bruit | **2,8e-6 / 2,8e-8 / ≤ 6e-9** | 0,9–2,7 s → 1,1–5,6 s |
| saphir 2500–4000 nm | 9,6e-4 / 3,6e-3 / 9,5e-4 | **2,8e-6 / 7,6e-8 / 4,5e-8** | 1,1–2,4 s → 1,5–3,0 s |
| données de la variante A, pôles UV | 2,7e-6 / 2,8e-8 / 9,5e-9 | 2,8e-6 / 2,8e-8 / 4,2e-9 | 0,4–2,2 s → 1,4–3,5 s |

Avec l'option, l'écart suit le bruit sur les six cas de catalogue (il était fixé par le modèle) ; sur des données sans pôle
IR, rien ne se perd. Coût : +0,1 à +3,5 s par ajustement.

Limite : courbes de catalogue synthétiques, de la même forme que le candidat. Pas encore de mesure sur un indice mesuré.

## Reste

Activer par défaut, et exposer l'option dans la fenêtre SUBSTRATE : décision de 👤 (change les indices ajustés). Le Jacobien
analytique de la variante standard (88 % du temps par défaut) reste à faire. La variante A, inchangée, ne converge toujours pas
seule.
