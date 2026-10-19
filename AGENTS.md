# AGENTS.md — point d'entrée de toute IA

Chaque octet lu ou imprimé est un coût. Règles : [`CLAUDE.md`](CLAUDE.md) ; état : section 0 de [`docs/ETAT.md`](docs/ETAT.md).

```bat
python scripts\preflight.py
python scripts\orient.py
```

La première doit finir par `PREFLIGHT=GO`. `orient.py` donne la tête git, l'arbre, les autres processus python (une mesure
lancée pendant qu'une autre tourne rend `RESULT=None`), la dernière validation et le coût de chaque document ; `--carte`
ajoute leurs titres et lignes.

1. **À la demande seulement** : `docs/ETAT_actions.md`, `docs/ETAT_acquis.md`, `docs/REGLES_reference.md`.
2. **Jamais en entier** : `reports/`, `studies/`, `UXargon.md`, `designargon.md` ; cherche par identifiant
   (`grep -n "ALG-02" designargon.md`), ouvre le `bilan.md` ou le `README.md` d'un dossier. `.rgignore` les cache à ripgrep.
3. **Une sortie de commande se paie** : `pytest -q --no-cov` (`-x` pour s'arrêter au premier échec), jamais `--verbose` ;
   `git status -sb`, `git log --oneline -n 10`, `git diff --stat` avant `git diff` ; au-delà d'une page, un fichier dont tu
   lis la fin.
4. **Lis ce dont tu as besoin** (`offset`, `limit`) ; ne relis pas ce que tu viens d'écrire ; Read et Grep plutôt que
   `cat`, `find`, `grep -r`.
5. **Une action, son résultat, la suivante** : ni agents ni processus en parallèle pour explorer ; une seule mesure ou
   validation à la fois.
6. **Écris court** : un fait, un seul endroit ; le rapport d'une campagne va dans `reports/`.
