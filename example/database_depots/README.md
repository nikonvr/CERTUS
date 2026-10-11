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
sur la même grille forment une seule entrée ; autrement, chaque voie a la sienne. Les `.csv` et `.res` du même nom
qu'un classeur en sont des exports : gardés dans `bruts/`, ils ne sont pas lus une seconde fois.

**La voie se lit dans la géométrie, pas dans la déclaration.** En mode manuel, le Photon RT écrit « Transmittance »
quel que soit le détecteur : un détecteur à 180° voit le faisceau transmis, un détecteur à deux fois l'angle du
porte-échantillon (16° pour 8°) le faisceau réfléchi. Treize colonnes de cette source sont des réflexions déclarées
« Transmittance » ; `mode_declare` garde la déclaration du fichier. Une transmission et une réflexion du même
échantillon nommées différemment par l'opérateur (`NbT3` et `NbR3`, `H800-NbT` et `H800-NbR`) restent deux entrées :
rien ne les apparie d'après leur nom.

## Une entrée du catalogue

| clé | sens |
|---|---|
| `id`, `fichier`, `brut` | identifiant, mesure normalisée, fichier d'origine |
| `echantillon` | le nom que porte la colonne dans le classeur |
| `voies` | pour chaque voie : `mode` (T ou R), `mode_declare` (ce que le classeur déclare), `detecteur_deg` et `angle_deg` (angles du détecteur et du porte-échantillon), `polarisation` (`--` : non polarisée), `debut` (date de la mesure) |
| `lambda_nm`, `points` | domaine spectral et nombre de points |
| `parametres` | réglages d'acquisition relevés dans la feuille `Parameters` (moyennage, pas, fente, taille du spot) ; `Sample thickness, mm` et `Refractive index n` sont des réglages du banc, pas une description du substrat |
| `materiau`, `substrat` | **seulement ce que le nom du fichier ou de l'échantillon dit** (`"source": "nom"`), sinon `null` : « Nb » et « Ta » désignent les oxydes déposés (Nb₂O₅, Ta₂O₅), « si » seul reste sans attribution (silicium ou silice) ; rien n'est déduit du spectre |

## Reconstruire la base

```bat
python scripts\importer_base_depots.py <dossier de fichiers Photon RT>
```

Le script copie les fichiers du dossier dans `bruts/`, écrit leurs mesures dans `mesures/` et réécrit `catalogue.json`
à partir de ce seul dossier : pour reconstruire la base, vider d'abord `example/database_depots/` (ce README et
`references_index.json` exceptés).
Il lui faut `xlrd` pour les `.xls`. `tests/unit/test_the_deposit_database_holds_together.py` vérifie que chaque entrée
se charge comme le catalogue l'annonce.

## Les références d'INDEX et le banc

`references_index.json` relève les ajustements certifiés de l'application CERTUS INDEX autonome
(`CERTIFIED_FRESNEL_CONFIGS`) dont le spectre embarqué est un dépôt de cette base, rapproché sur les données : onze
sur vingt-sept. Pour chacun : les dépôts (T, ou T et R que l'ajustement réunit), le substrat, la normalisation, la bande
d'ajustement, les sept paramètres du modèle de Tauc-Lorentz-Urbach, l'épaisseur et n(633). **Ce sont des sorties
d'ajustement, pas des mesures indépendantes** ; avec les fonctions d'INDEX, les paramètres redonnent le n(633) de
l'application à 10⁻⁹ près (le test le vérifie).

```bat
python scriptsench_base_depots.py
```

Le banc charge chaque référence dans la fenêtre INDEX comme un utilisateur, avec son substrat, sa normalisation et
sa bande, et dit si INDEX retrouve l'épaisseur et n(633). Quand la bande dépasse 2500 nm et commence sous 2200 nm,
INDEX ajuste le modèle jusqu'à 2200 nm puis fige épaisseur et indice avant l'extension IR, quand l'application
autonome ajuste toute la bande : le banc l'écrit sur chaque ligne. INDEX n'étant pas reproductible, chaque référence
tourne trois fois.
