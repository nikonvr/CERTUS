# Séparateur 50/50 — recherche DESIGN et dépôt simulé STRAT

## Protocole

Trois paires à 34 couches H/L, graines DESIGN 42, 77 et 202. Même budget de 1 000 enfants mémétiques par design.
La cible vaut 0,50 en transmission de 400 à 1 200 nm, avec la face arrière nue incluse dans les deux moteurs.
Indices constants H = 2,35, L = 1,45 et substrat = 1,52. La sélection mémétique compare un mérite nominal
à un mérite avec sensibilité à des erreurs d'épaisseur indépendantes de 1 nm. Le polissage final est nominal dans les deux cas.

Le premier essai à plancher de 5 nm a produit une couche 8 de 13,46 nm. Avec le plancher de transmission de
10 % et la marge de 1,66 fois le bruit, STRAT a écarté les 801 longueurs d'onde même après élargissement de la
présélection à toute la bande. Cette pile est conservée comme essai de faisabilité distinct. Les six empilements
comparés ont un plancher commun de 25 nm. La présélection de la campagne accepte tous les niveaux de dynamique.
Le plancher de transmission et la marge aux points tournants restent actifs.

STRAT charge les cibles et les multiplicateurs de DESIGN dans son pipeline complet en mode `fast`. La campagne
cherche les plans avec la graine 42 et le consensus configuré dans l'exemple. Elle coupe le raffinement local final
pour appliquer le même budget aux six plans. Le juge contrôle le transfert des épaisseurs à l'arrondi du tableau près,
les indices et les cibles. Le spectre nominal est recoupé entre les deux moteurs sur une grille commune de 1 nm.

Chaque plan est rejoué sur trois graines de notation distinctes (`2026111502` à `2026111504`), 400 essais par graine
et par facteur de bruit 0,5 / 1 / 2. La RMSE quadratique moyenne au bruit nominal est calculée sur les dépôts
terminés. Le P95 utilise toutes les valeurs rendues par STRAT. Le SEEL de classement vaut deux fois la racine carrée
du pire P95 des trois niveaux. Les arrêts sont comptés à chacun des trois niveaux.

Sur une quatrième graine (`2026111501`), les dépôts terminés donnent le biais d'épaisseur $b$ et la covariance
$\Sigma$. La prédiction au bruit nominal est $\sqrt{\lVert r+Jb\rVert^2 + \mathrm{tr}(J^\top J\Sigma)}$,
avec $r$ et $J$ pondérés sur les cibles au nominal. Elle résume les erreurs d'épaisseur à indices nominaux.
Le juge de dépôt calcule le spectre aux indices perturbés par le corridor et inclut les effets non linéaires.
L'estimation de vitesse du mode Rate suit le modèle de STRAT et n'ajoute ni dérive ni bruit de vitesse indépendant.

Le script de campagne se trouve dans [`scripts/bench_codesign.py`](../../scripts/bench_codesign.py).
Exécuter les deux étapes l'une après l'autre et utiliser un nouveau nom de sortie par pile.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:OPENBLAS_NUM_THREADS = '1'
$env:NUMBA_NUM_THREADS = '16'
python scripts/bench_codesign.py design --seed 42 --children 1000 --out artifacts/codesign/fixed_42.json
python scripts/bench_codesign.py strat --design artifacts/codesign/fixed_42.json --out artifacts/codesign/fixed_42-deposition.json
```

Ajouter `--robust` à l'étape DESIGN pour le bras robuste et choisir un autre préfixe. Les fichiers `.strat.json`
et `.plan.json` enregistrent le réglage STRAT effectivement chargé et le plan retenu avant la notation.

## Résultats du 14 novembre

RMSE en transmission absolue. La colonne « dépôt » donne la racine de la moyenne des RMSE au carré au bruit nominal.
Le score nominal et la prédiction de covariance sont calculés sur la pile chargée dans STRAT. Les six plans passent
le filtre de risque en recherche et totalisent chacun **0 arrêt / 1 200** à chacun des trois niveaux de bruit.

| Graine | Sélection | RMSE nominale | RMSE dépôt | RMSE covariance | SEEL (nm) | Couches Rate | Recherche STRAT (s) |
|---:|---|---:|---:|---:|---:|---:|---:|
| 42 | Nominale | 0,003453 | 0,004515 | 0,004092 | 0,15883 | 31 | 233 |
| 42 | Robuste | 0,006581 | 0,008203 | 0,008132 | 0,21062 | 31 | 144 |
| 77 | Nominale | 0,003590 | 0,004997 | 0,004566 | 0,16784 | 32 | 233 |
| 77 | Robuste | 0,008177 | 0,008807 | 0,008636 | 0,19976 | 32 | 589 |
| 202 | Nominale | 0,003453 | 0,004515 | 0,004091 | 0,15883 | 31 | 230 |
| 202 | Robuste | 0,006041 | 0,006860 | 0,006575 | 0,18534 | 31 | 242 |

Les écarts appariés de RMSE au carré sur 1 200 paires par graine (robuste moins nominal) sont `+4,69145e−5`,
`+5,26011e−5` et `+2,66759e−5`. La RMSE après dépôt augmente respectivement de **81,7 %, 76,3 % et 51,9 %**.
Les solutions nominales des graines 42 et 202 convergent vers la même pile à `7,2e−5 nm` par couche près.
La prédiction par covariance préserve l'ordre dans chaque paire et sous-estime le RMS observé de 0,9 à 9,4 %.
Le temps du bras robuste 77 inclut une recompilation à froid après D112, qui concerne le gradient d'INDEX.

Les simulations comparent un seul composant et des plans dont 31 à 32 couches sur 34 sont pilotées au taux de dépôt.
Pour cette configuration, le gain sous erreurs indépendantes observé dans DESIGN avec un autre protocole
ne se retrouve pas dans STRAT. Le cas à 5 nm montre un problème de pilotage que le mérite de sensibilité
spectrale seul ne décrit pas. Pour 24, le test à 1 nm ne justifie pas une activation générale. Pour 31 et 32,
un nouvel essai doit d'abord quantifier les variations de plans et de marges sous un modèle de vitesse et une
part de Rate représentatifs de la machine visée.

[Données des six piles, réglages, plans, tirages et covariances](results.json).
