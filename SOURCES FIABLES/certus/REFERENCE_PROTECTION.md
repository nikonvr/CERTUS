# Protection interne des modules CERTUS

Ce projet utilise une version de référence de travail stockée dans `3105 VERSION OLD OK`.

## Référence
- La version `OLD` est la version de référence courante.
- Elle doit être considérée comme la base stable pour les comparaisons.

## Portée
Cette règle concerne particulièrement :
- `CERTUS_METAL_SINGLE.py`
- `CERTUS_METAL_BILAYER.py`
- `CERTUS_STRAT.py`
- `CERTUS_INDEX.py`
- `CERTUS_INDEX_SPLINE.py`
- `CERTUS_RE.py`
- `CERTUS_DESIGN.py`

## Protection
- Conserver la compatibilité des points d'entrée.
- Préserver les dépendances de chaque module.
- Éviter de modifier la référence sans reproduire et vérifier le comportement.
