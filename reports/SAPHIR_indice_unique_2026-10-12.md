# L'indice du saphir de CERTUS : un seul, mesuré, avec son corridor (2026-10-12)

Mesuré le 2026-10-12 par `scripts/saphir_corridor.py` (sorties dans `reports/saphir_corridor_2026-10-12/`, une par étape,
`sortie_*.txt` et `saphir_*.json`). Les calculs sont à un thread.

## Réponse

- **L'indice de référence de CERTUS est le Sellmeier d'id 3** (rayon ordinaire, Malitson et Dodge), et c'est le seul.
- **Ce que les mesures de la base disent de son niveau : +0,0003 ± 0,0028** (1 σ) par rapport à lui, entre 1 et 3,3 µm.
  Corridor à 95 % : **[−0,0052, +0,0058]** autour de la référence (`saphir_corridor_indice.csv`, `.png`).
- **Cet indice est indiscernable de zéro : on ne corrige pas la référence.** La corriger de moins de 0,003 reviendrait à
  l'ajuster sur du bruit.
- **Conséquence sur les indices de films** déterminés à partir de spectres normalisés au substrat : n_f suit n_s un pour
  un (1,05 pour Nb₂O₅, Ta₂O₅, ZnS ; 1,4 à 1,5 pour SiO₂ et YF₃) et l'épaisseur varie de −0,14 % par +0,003 d'indice. Le
  corridor met donc ±0,003 sur n_f (±0,004 pour SiO₂), pas plus.

## Ce qui fixe le niveau : la photométrie absolue, et elle seule

Information de Fisher sur le niveau, films libres (spline n et ln k à la manière d'INDEX SPLINE), bruit de 0,1 %, faisceau
supposé non polarisé, 1000–3300 nm (`sortie_information.txt`) :

| données | σ du niveau |
|---|---|
| saphir nu, T et R | 0,00068 |
| saphir nu, T seul | 0,00097 |
| 3 films absolus, T **et** R | 0,00079 |
| 3 films absolus, T seul | 0,0069 |
| 3 films absolus, R seul | 0,0030 |
| tout (nu + 3 films, T et R) | 0,00052 |

Un film libre absorbe un décalage plat de T sans perdre un χ² (coût d'un décalage de −0,004 : 0,0 en T seul, 13,8 en R seul,
21,8 en T et R pour un film ; 47 pour le saphir nu en T seul). **Les 9 références certifiées normalisées au substrat n'ont ni
la photométrie absolue du saphir nu ni le R des films : leur niveau est indéterminé** (`sortie_rapport.txt` : gain de χ²
6,7 pour une dérive de +0,015, valeur propre d'information 12 contre 10⁵ pour la forme ; avec les 12 spectres de
l'application autonome et des épaisseurs libres à ±6 %, la dérive atteint +0,05, la borne, pour un gain de 2,3).

## Les mesures absolues de la séance 24-03

Saphir nu et films de Nb₂O₅ (≈ `h400`), Ta₂O₅ (≈ `pe-ta2`) et SiO₂ (≈ `h400-sio2`), T et R, 8°, 50 nm de pas. Modèle direct :
la lame oblique du dépôt (`calc_spectrum_oblique_backside_vectorized`), égale à Fresnel écrit à la main à 10⁻⁹ près en s et en p.

- Avec le Sellmeier d'id 3 et un faisceau non polarisé, les quatre échantillons s'ajustent à 0,08–0,15 % rms (χ² 467 pour 376 points).
- **Le déficit de fermeture 1 − T − R** vaut 0,15–0,33 % pour le saphir nu et 0,02–0,08 % pour les trois films de la même
  séance : il est propre à la mesure du saphir nu, et **c'est de lui que venait le faux indice** (l'inversion de R seul donne
  un indice plus bas de 0,006 à 0,011).
- **L'incertitude dominante est la polarisation du faisceau** : à 8°, R_s − R_p = 0,58 %. Une erreur df sur la fraction p
  décale le niveau de 0,023 à 0,027·df (données simulées). Avec f = 0,5 ± 0,15 (hypothèse, pas une mesure) : σ = 0,0025.
- **Robustesse** : 16 variantes (un film retiré, T seul, R seul, fenêtres, 3 ou 4 nœuds, densité des nœuds) : niveau +0,0003,
  écart-type 0,0013 (`sortie_absolu.txt`). Une variante est écartée : la fenêtre 800–3300, où le film de 3 µm est
  sous-échantillonné par le pas de 50 nm.
- σ total = √(0,0013² + 0,0025²) = 0,0028.

**Validation sur données simulées à vérité connue** (`sortie_synthese.txt`, 6 tirages à 0,1 %) : un niveau planté de 0, −0,004
ou −0,0075 est retrouvé à 0,0004 près, que la vérité soit une spline (même famille que le modèle) ou des films TLU (autre
famille). Une fraction p fausse de 0,15 décale le niveau de 0,0032 à 0,0037.

## MWIR (jusqu'à 5,2 µm)

Absorption lue sur le T du saphir nu (lame de 1 mm) : α = 0,05 cm⁻¹ à 4 µm, 0,2 à 4,5, 0,7 à 5, 1,1 à 5,2 (k de 1,5·10⁻⁶ à
4,5·10⁻⁵). **Un plancher d'absorption sous 3,9 µm fausse le niveau** (0,2 % de T ≈ 0,008 d'indice) : il est nul. Les
fenêtres 1000→4300, 5000 et 5200 donnent une correction de +0,001 à +0,002 aux nœuds longs (±0,0007) : la dispersion
infrarouge de la référence tient à ±0,003 jusqu'à 5,2 µm (`sortie_mwir.txt`). **INDEX traite le saphir comme transparent
(k = 0)** ; son absorption au-delà de 3,9 µm n'est pas modélisée (chantier, ETAT §6).

## Les faux indices de saphir, supprimés (un commit chacun)

| où | quoi | corrigé par |
|---|---|---|
| `certus/utils/certus_strat_db.py` | « Sapphire Fresnel » : un Sellmeier à part (n plus bas de 0,0077 à 1 µm), offert par les listes de FIELD et de METAL | `b9223b43` : alias du saphir d'id 3 |
| `certus/core/certus_substrate_db.py` | le libellé « Sapphire Fresnel » et ses alias ; **dans METAL, ce libellé n'avait pas d'id de Sellmeier et le substrat devenait N-BK7 sans un mot** | `b9223b43` |
| `example/sapphire fresnel.xlsx` | une table lue à l'import par INDEX et jamais utilisée (k forcé à 0, n pris au Sellmeier), à k 200 fois trop fort à 5 µm | `4a3bda20` : supprimée avec son chargeur |
| `example/database_index/sapphire_index.txt` et la copie de `example_index/` | une table n, k plus basse que la référence de 0,012 à 250 nm, 0,0043 à 1 µm, 0,002 à 3 µm | `4a3bda20` : supprimées |

Le garde `tests/unit/test_one_sapphire_index.py` (13 tests) échoue si un nom, un résolveur (noyau, INDEX, INDEX SPLINE,
outil de Sellmeier de substrat) ou le fichier de données donne un autre n. **Il a trouvé un écart restant : le JSON et le
code écrivent C1 et C3 avec des chiffres différents (C3 = 325,01883 contre 18,028251² = 325,01783) ; n diffère de 4,6·10⁻⁷
au plus (5 µm).** Non corrigé : l'aligner change le hash verrouillé du fichier et la copie de l'application autonome.

## Ce que je n'ai pas mesuré

- La polarisation du faisceau du spectrophotomètre. σ_f = 0,15 est une hypothèse ; avec 0,05 le corridor se resserre à
  σ = 0,0010, avec 0,5 il s'ouvre à 0,008.
- Le visible sous 1 µm : seul le T du saphir nu l'éclaire (n(T) − S = −0,0018 entre 500 et 1000 nm) ; les films de 3 µm y sont
  sous-échantillonnés.
- L'application autonome (`alone/`, hors dépôt) : elle utilise les mêmes coefficients que le JSON ; je n'y ai rien modifié.
- La validation complète du dépôt après ces trois commits (voir ETAT §0).

## Reproduire

```bat
python scripts\saphir_corridor.py absolu
python scripts\saphir_corridor.py corridor --sigma-f 0.15
python -m pytest tests\unit\test_one_sapphire_index.py tests\unit\test_saphir_corridor.py -q --no-cov
```
