# Référence de travail et protection de la base

Ce dépôt utilise désormais `3105 VERSION OLD OK` comme **version de référence de travail**.

## Ce que cela signifie
- La version `OLD` est la base de comparaison principale.
- Elle représente l'état actuellement considéré comme fiable et fonctionnel.
- Les évolutions futures doivent être comparées à cette référence.

## Règles de protection
- Ne pas écraser la référence sans validation explicite.
- Conserver une copie complète de la suite CERTUS dans `3105 VERSION OLD OK`.
- Vérifier les points d'entrée, dépendances et fichiers de support avant toute refonte.
- Préserver les versions fonctionnelles des modules METAL, STRAT, INDEX, SPLINE, RE et DESIGN.

## Fichiers clés sauvegardés
- `CERTUS_METAL_SINGLE.py`
- `CERTUS_METAL_BILAYER.py`
- `certus/metal/certus_metal_common.py`
- `certus/metal/certus_metal_orchestrator.py`
- et, plus largement, la suite CERTUS dans le répertoire `3105 VERSION OLD OK`

## Objectif
Cette protection sert à garder une base stable, documentée et réutilisable pour les développements futurs.
