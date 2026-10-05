# Parité du RE avec le paquet publié `certus_re` — inventaire des capacités, 2026-10-05

Paquet publié : `publication_reverse/07_PAQUET_ZENODO/certus_re`, version locale `1.2.0.dev0` (DOI concept
10.5281/zenodo.22756244 ; l'archive publique 1.1.1 ne contient pas les filtres remesurés). Code courant : `certus0310`.

`certus_re` est une réécriture autonome (fichier d'étude JSON, inversion MAP), pas une copie du RE de CERTUS : la
comparaison se fait **capacité par capacité**, pas fonction par fonction. Les chiffres attribués au paquet viennent
de ses propres sorties, dont le chemin est donné ; ils n'ont pas été remesurés ici.

| capacité de `certus_re` | où | dans `certus0310` | statut |
|---|---|---|---|
| incertitude de chaque épaisseur, `s² (JᵀJ)⁺` sur les seuls résidus de données | `solve._covariance` | `certus_re_uncertainty` | porté, R135 |
| budget de paramètres : blocs libres et tenus, points par paramètre | `dof.count_free_parameters` | `certus_re_budget` | porté, R138 ; affiché, R139 |
| préréglage d'instrument, ouverture imposée (PHOTON RT, 2,0° au total, inactif sous 10°) | `instruments.PRESETS` | `re_beam_aperture_imposed_deg`, combo « Aperture » | porté, R140 |
| ouverture par bande, frontières aux bascules 2 530 et 3 700 nm | `model.Instrument.aperture_band_edges_nm` | quatre plateaux sur une grille régulière en λ | non porté : les études de référence du paquet imposent une ouverture unique |
| moyenne sur le cône par quadrature de Gauss-Legendre (`n_aperture_nodes` impair ≥ 3) | `physics.aperture_nodes` | deux rayons θ ± h | écarté par 👤 le 2026-10-05 : deux ou trois rayons suffisent. Dans `results/insitu_model_refinement.json` du paquet, 9 nœuds donnent une RMSE jointe de 0,4166 % contre 0,1481 % à deux rayons (ouverture imposée de 2°), et les études de référence gardent deux rayons |
| diaphonie des polariseurs (α, β) | `model.Instrument.crosstalk_*` | absente | non porté : même fichier, α = 0,00101 et β = 0 ajustés, RMSE jointe 0,1475 % contre 0,1481 % sans diaphonie |
| a priori procédé de 0,5 % sur l'épaisseur optique (MAP) | `solve.invert` | pénalité QWOT (poids α par phase) | non comparé |
| indices tabulés refusés hors de leur domaine déclaré | `dispersion.TabulatedIndex.extrapolation_report` | `TabularMaterial` : extrapolation constante aux bornes, sans message | non porté |
| convention n − ik des indices tabulés | `dispersion`, `physics.as_macleod` | `TabularMaterial.get_nk` rendait n + ik ; corrigé, R148 | corrigé (voir ci-dessous) |
| substrats silicium (Li 1980) et saphir (Malitson) | `dispersion.silicon_li1980`, `sapphire_malitson` | SiO₂ par Sellmeier de Malitson, silicium par table | non comparé |
| échantillon à revêtement sur les deux faces | `physics.assemble_plate` | le RE ne modélise pas de revêtement arrière | non porté |
| résidus rapportés par voie de mesure | `report.text_report` | RMSE globale | non porté |
| inversion conjointe de plusieurs échantillons | `solve.invert` | absente | écartée par 👤 le 2026-10-04 |

**La convention de signe, trouvée en faisant cet inventaire.** `TabularMaterial.get_nk`, qui porte les indices des
classeurs RE (couches et substrat), rendait n + ik avec le k positif du classeur, alors que les noyaux prennent n − ik.
En incidence normale le noyau du RE ne dépend pas du signe de k, ce qui cachait l'écart ; à 45°, pour une couche de
k = 0,05, T s'écartait de la référence indépendante (`tests/oracle/tmm_reference.py`) de 0,29 et R + T atteignait 1,12.
Corrigé par R148 ; la référence est retrouvée à 10⁻¹⁶.

**Le paquet publié le savait.** `certus_re` convertit une fois n + ik en n − ik (`physics.as_macleod`) ; son option
`legacy_gain_sign` (drapeau caché de la ligne de commande, `False` par défaut, activé seulement par ses tests et par
`tools/compare_with_reference.py`) reproduit « l'implémentation de référence », c'est-à-dire CERTUS. Mesuré le
2026-10-05 sur la même couche à 45° : par défaut, écart à la référence indépendante de 9·10⁻¹⁷ sur R et 7·10⁻¹⁶
sur T ; avec l'option, 0,051 et 0,289, R + T = 1,11 : exactement les écarts de certus0310 avant R148. Aucune
étude du paquet n'active l'option.
