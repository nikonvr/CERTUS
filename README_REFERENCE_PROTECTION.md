# Protection de la version de référence

Ce projet conserve une version de référence complète dans le dossier `3105 VERSION OLD OK`.

## Usage
Cette version doit être utilisée comme point d'appui pour :
- comparer les évolutions
- restaurer un comportement connu comme bon
- vérifier la cohérence globale après modification

## Ce qu'il faut retenir
- La version `OLD` n'est pas un simple ancien état : c'est la **référence de travail**.
- Les modifications doivent être validées par rapport à cette base.
- Les fichiers sources principaux et leurs dépendances sont conservés dans cette copie.

## Bonnes pratiques
- Toujours vérifier les imports et les dépendances avant de toucher un module.
- Toujours tester les points d'entrée après une refonte.
- Conserver des copies fonctionnelles lorsque l'UX ou l'architecture évoluent.
