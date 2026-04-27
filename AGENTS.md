# Project-wide rules (cross tools)

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
