# Chantier 50 — recoupement tiers de la face arrière et de la plaque (2026-11-17)

Code tiers : `tmm` 0.2.0, `inc_tmm` (couches incohérentes), installé hors du dépôt comme au chantier 40
(`%TEMP%\certus_tmm_tiers`). Oracle : `tests/oracle/tmm_reference.py::rt_plate_incoherent`, indépendant de `certus.physics`.
Code `a4f544cf`, aucun fichier de `certus/` modifié.

## Mesures

[`p50_back_oblique.py`](p50_back_oblique.py) ([sortie](p50_back_oblique.txt)) : `calc_spectrum_full_oblique_exact`, pile avant
de trois couches dont une absorbante, pile arrière de deux couches, substrat de 1 mm, 0°, 30°, 60°, s et p, 4 longueurs d'onde.

- **Substrat non absorbant (k = 0)** : CERTUS, l'oracle et `tmm` concordent à **1,2e-15** au plus, R et T, dans les douze cas.
  La face arrière incohérente, la pile arrière et l'oblique sont recoupées par un code tiers.
- **Substrat absorbant (k = 4,4e-6)** : CERTUS = oracle à 5,6e-16 ; CERTUS − `tmm` vaut 1,3e-7 à 1,2e-6.

[`p50_interfaces.py`](p50_interfaces.py) ([sortie](p50_interfaces.txt)) et la seconde partie de `p50_back_oblique.py` : le même
assemblage que l'oracle, mais avec les interfaces vues de l'intérieur du substrat à l'indice **complexe** (ce que fait `tmm`),
rejoint `tmm` :

| cas, 0° | k | CERTUS − `tmm` | variante à n complexe − `tmm` |
|---|---|---:|---:|
| face arrière nue | 4,4e-6 | 2,1e-8 | 7,1e-12 |
| face arrière nue | 2e-5 | 3,2e-8 | 1,2e-10 |
| pile arrière | 4,4e-6 | 9,8e-7 | 4,7e-12 |
| pile arrière | 2e-5 | 2,5e-6 | 6,7e-11 |

## Conclusion

L'écart avec `tmm` sur un substrat absorbant est **le choix de l'indice aux interfaces vues de l'intérieur** : CERTUS et l'oracle
prennent Re(n) (modèle documenté dans `certus_substrate_absorption.py` et `calc_spectrum_full_exact`), `tmm` le n complexe.
Ce n'est pas un défaut : à ces k, l'écart (≤ 2,5e-6 en T) est sous la précision d'une mesure spectrophotométrique, et le
flux dans un milieu absorbant n'a pas de normalisation unique. Reste non expliqué : à k = 1e-4 (face nue), la variante complexe
s'écarte encore de `tmm` de 9,6e-10 pour 1,3e-9 d'écart total, quand T ne vaut plus que 0,08 ; hypothèse non mesurée, la
normalisation du flux de `tmm` dans un milieu absorbant.

Hors de ce recoupement : les gradients (le chantier 40 les laissait aussi).
