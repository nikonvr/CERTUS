# Chantier 41 — tri des branches Dependabot (2026-11-15)

Lu dans les références `origin/dependabot/*` du dépôt local (dernier `fetch` antérieur à la session ; GitHub non
consulté) et comparé aux épingles de `.github/` et à `uv.lock` de la tête de travail. Rien n'est fusionné ni fermé sur
GitHub : c'est à 👤.

## À fermer : déjà dans le code

| branche | état dans `.github/` |
|---|---|
| `actions/checkout-7.0.1` | v7.0.1 épinglé |
| `actions/setup-python-7.0.0` | v7.0.0 épinglé |
| `actions/upload-artifact-7.0.1` | v7.0.1 épinglé, remplacé par 7.0.2 ci-dessous |
| `astral-sh/setup-uv-10.2.0` | v10.2.0 épinglé, remplacé par 10.3.2 ci-dessous |
| `github/codeql-action/autobuild-4.38.2` | v4.38.2 épinglé, remplacé par 4.38.3 ci-dessous |

## À fusionner : correctifs mineurs, épinglés par SHA

| branche | changement |
|---|---|
| `actions/upload-artifact-7.0.2` | 7.0.1 → 7.0.2, 2 fichiers |
| `astral-sh/setup-uv-10.3.0` | 10.2.0 → 10.3.2 |
| `github/codeql-action/{init,analyze,autobuild}-4.38.3` | 4.38.2 → 4.38.3, **les trois ensemble** (même SHA ; les trois actions CodeQL restent alignées) |
| `uv/setuptools-84.1.0` | 84.0.0 → 84.1.0, outil de construction seul |

Chaque diff garde la forme `uses: …@<SHA> # vX.Y.Z`. Je n'ai pas vérifié que chaque SHA correspond à l'étiquette
annoncée : cela demande GitHub.

## À éprouver avant de fusionner

`uv/pillow-13.0.0` : version majeure (12.3.0 → 13.0.0). Pillow n'est importé nulle part dans `certus/`, `scripts/` ni
`tests/` ; il arrive par matplotlib. Résultat de l'essai local : voir la section suivante.
