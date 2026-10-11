# Base de dépôts — monocouches mesurées au Photon RT

Mesures réelles de couches minces déjà déposées, pour la détermination d'indice (INDEX) et la rétro-ingénierie (RE).
Source : les monocouches « certaines » mesurées au spectrophotomètre Essent Optics Photon RT
(`Fichiers_PhotonRT/Certain_Monocouche` de l'application web CERTUS INDEX autonome), importées le 2026-10-11 par
`scripts/importer_base_depots.py`.

## Ce que contient le dossier

| élément | contenu |
|---|---|
| `bruts/` | chaque fichier de mesure tel qu'il est sorti du banc, sans modification (`.xls`, `.xlsx`, `.csv`, `.res`) |
| `mesures/<id>.csv` | une mesure par échantillon : `wavelength_nm,T[,R]`, en pourcents, longueurs d'onde croissantes ; c'est le format qu'INDEX lit |
| `catalogue.json` | une entrée par échantillon (`depots`), les fichiers écartés comme doublons (`doublons`) et ceux qui n'ont pas pu être lus (`refus`) |

Un classeur Photon RT (`.xls`, `.xlsx`) porte deux feuilles : `Parameters`, une colonne par mesure (nom, dates, mode,
angle, polarisation, réglages), et `Measurement`, les longueurs d'onde puis une colonne par mesure. Un classeur peut
donc contenir plusieurs échantillons : chacun devient une entrée. La transmission et la réflexion d'un même échantillon
sur la même grille forment une seule entrée ; autrement, chaque voie a la sienne. Les `.csv` et `.res` du même nom que
un classeur en sont des exports : gardés dans `bruts/`, ils ne sont pas lus une seconde fois.

## Une entrée du catalogue

| clé | sens |
|---|---|
| `id`, `fichier`, `brut` | identifiant, mesure normalisée, fichier d'origine |
| `echantillon` | le nom que porte la colonne dans le classeur |
| `voies` | pour chaque voie : `mode` (T ou R), `angle_deg` (angle du porte-échantillon), `polarisation` (`--` : non polarisée), `debut` (date de la mesure) |
| `lambda_nm`, `points` | domaine spectral et nombre de points |
| `parametres` | réglages d'acquisition relevés dans la feuille `Parameters` (moyennage, pas, fente, taille du spot) ; `Sample thickness, mm` et `Refractive index n` sont des réglages du banc, pas une description du substrat |
| `materiau`, `substrat` | **seulement ce que le nom du fichier ou de l'échantillon dit** (`"source": "nom"`), sinon `null` : « Nb » et « Ta » désignent les oxydes déposés (Nb₂O₅, Ta₂O₅), « si » seul reste sans attribution (silicium ou silice) ; rien n'est déduit du spectre |

## Reconstruire la base

```bat
python scripts\importer_base_depots.py <dossier de fichiers Photon RT>
```

Le script copie les fichiers du dossier dans `bruts/`, écrit leurs mesures dans `mesures/` et réécrit `catalogue.json`
à partir de ce seul dossier : pour reconstruire la base, vider d'abord `example/database_depots/` (ce README excepté).
Il lui faut `xlrd` pour les `.xls`. `tests/unit/test_the_deposit_database_holds_together.py` vérifie que chaque entrée
se charge comme le catalogue l'annonce.
