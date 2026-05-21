
## Statut
### Déjà fait
- Alignement Python 3.14.5+ confirmé dans les documents et workflows visibles.
- Backlog P0/P1 créé.
- Audit des modules principaux réalisé.
- Les priorités socle / services / UI / hub / gros modules sont identifiées.
- Refactoring incrémental et validation de `spline_profile_corridors.py` (Phase 3 et Bonus) finalisés.
- Validation des configurations de release et des entrypoints métier critiques.
- Modernisation des exceptions, décoration `@safe_ui_action` (config/RE), configuration headless et boost de couverture à 60.73% complétés.

### Il reste
- Finaliser les optimisations fines de l'architecture.
- Continuer à renforcer la couverture de tests spécifiques au besoin. # Project-wide rules (cross tools)

## Style de code
- Suivre la configuration actuelle (formatters, linters, conventions de noms).
- Ne pas imposer un nouveau style global sans demande explicite.

## Organisation
- Préserver l’architecture actuelle (modules, packages) sauf refactor ciblé validé.
- Préférer déplacer ou extraire progressivement plutôt que restructurer tout un module.

## Communication
- Toujours mentionner le périmètre exact des fichiers modifiés.
- Documenter uniquement ce qui est nécessaire à la relecture (changements, impact, tests).
- Ne pas changer la configuration CI / tooling sans validation explicite.


## État actuel
### Fait
- Alignement Python 3.14.5+ confirmé dans la documentation visible et les workflows déjà inspectés.
- Plan P0/P1 créé.
- Backlog maître créé.
- Audit des modules principaux réalisé.
- Refactoring incrémental de `spline_profile_corridors.py` (Phase 3 et Bonus) finalisé.
- Validation des configurations de release et des entrypoints critiques.
- Modernisation des exceptions, décoration `@safe_ui_action` (config/RE), configuration headless et boost de couverture à 60.73% complétés.

### Reste
- Finaliser les optimisations fines de l'architecture.
- Continuer à renforcer la couverture de tests spécifiques au besoin.