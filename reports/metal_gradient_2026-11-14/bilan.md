# Polissages locaux dans METAL PGLOBAL

Le [script de mesure](../../scripts/probe_metal_polish.py) exécute les exemples depuis les fenêtres METAL.
Il impose la graine PGLOBAL, chronomètre les deux séries de polissages finaux de l'adaptateur et conserve
les départs et les coûts. Les budgets et les paramètres des exemples sont conservés.

## Profil et couverture

Sur la graine 42, la monocouche passe 3,03 s dans les neuf polissages, soit 6,3 % des 47,70 s du calcul.
Le gradient disponible `gradient_function_fixed_eM` couvre le balayage en réflexion à épaisseur fixée.
PGLOBAL ajuste aussi l'épaisseur, les positions des nœuds et, selon le fichier, R/T/Rback. Ce gradient
partiel ne couvre donc pas cette recherche. Le traitement monocouche garde les différences finies.

La bicouche passe 11,05 s dans les neuf polissages, soit 21,7 % des 50,89 s du calcul. Son gradient existant
`compute_metal_bilayer_gradient_analytic` couvre les épaisseurs, les paramètres de Cauchy, les valeurs
et les positions internes des nœuds. Il inclut la pénalité de régularité des splines.

## Comparaison appariée

Pour chaque départ réel du worker, une seconde descente est lancée avec les mêmes bornes, tolérances et
budget. Le parcours principal garde la descente en différences finies, ce qui apparie les neuf départs.
Avant comparaison, le coût du gradient est recoupé avec l'objectif scalaire et toutes les composantes
du gradient avec des différences finies centrales. Les écarts relatifs maximaux sont 1,6e−5, 1,3e−4 et
4,1e−5 selon la graine. Le coût concorde à moins de 3e−18.

| Graine | Différences finies (s) | Gradient (s) | Accélération locale |
|---:|---:|---:|---:|
| 42 | 10,94 | 3,53 | ×3,10 |
| 77 | 7,35 | 2,05 | ×3,59 |
| 202 | 11,12 | 3,26 | ×3,41 |

Les 27 descentes avec gradient aboutissent. L'écart absolu relatif de coût entre les deux descentes
reste sous 0,56 %. Il s'agit d'un autre trajet local, avec des résultats proches et des durées plus courtes.

## Activation

La configuration bicouche accepte `optimization.analytic_polish`, booléen faux par défaut.
Le worker fournit alors `gradient_fn` à l'adaptateur pour ses deux séries de polissages. Le gradient est
nul sur le plateau constant de rejet. Le champ se conserve dans la configuration et Reset le remet à faux.
La sonde en mode `--analytic` passe par le chargement de la fenêtre, vérifie la présence du Jacobien à
chaque appel de polissage et mesure trois parcours complets.

Les 172 tests ciblés de METAL et de visibilité de ses paramètres passent.
L'oracle passe avec 1 204 tests après raccordement, comme avant celui-ci.
Les trois parcours complets avec gradient ont les résultats suivants, comparés au parcours de référence
à la même graine. Le temps cumulé des polissages y est de 3,09 à 4,47 s.

| Graine | RMSE de référence | RMSE avec gradient | Variation | Calcul complet avec gradient (s) |
|---:|---:|---:|---:|---:|
| 42 | 0,00216133 | 0,00218777 | +1,22 % | 60,44 |
| 77 | 0,00218361 | 0,00216689 | −0,77 % | 51,95 |
| 202 | 0,00221739 | 0,00221650 | −0,04 % | 42,48 |

Le gain local ne démontre pas un gain uniforme sur la durée complète. Le profil initial à la graine 42
terminait en 50,89 s et le résultat de cette graine se dégrade de 1,22 % à l'activation. Le branchement
reste une option de recherche. La monocouche reste en différences finies, son gradient complet étant
absent et le plafond de gain mesuré de ses polissages limité à 6,3 % de ce cas.

[Mesures individuelles et parcours complets](results.json).
