# AGENTS.md — point d'entrée de toute IA

Règles : [`CLAUDE.md`](CLAUDE.md) ; état : [`docs/ETAT.md`](docs/ETAT.md) §0.

```bat
python scripts\preflight.py
python scripts\orient.py
```

`preflight.py` doit finir par `PREFLIGHT=GO`. `orient.py` donne tête git, arbre, processus python actifs (une mesure parallèle rend `RESULT=None`), dernière validation et coût des docs (`--carte` ajoute les titres).

1. **À la demande** : `docs/CHANTIERS_RESTANTS.md`, `docs/ETAT_acquis.md`, `docs/REGLES_reference.md`.
2. **Jamais en entier** : `reports/`, `studies/` (cachés à ripgrep par `.rgignore`) ; chercher par id (`rg -n "RICL" docs/CHANTIERS_RESTANTS.md`) ou lire `bilan.md`/`README.md`.
3. **Sortie sobre** : `pytest -q --no-cov` (`-x`), jamais `--verbose` ; `git status -sb`, `git log --oneline -n 10`, `git diff --stat` avant `git diff`.
4. **Lire ciblé** (`offset`, `limit`) ; ne pas relire ce qu'on vient d'écrire ; préférer Read/Grep.
5. **Une action, son résultat, la suivante** : ni agents ni mesures en parallèle.
6. **Écrire court** : un fait, un seul endroit ; rapport de campagne dans `reports/`.
