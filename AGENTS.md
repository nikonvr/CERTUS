# AGENTS.md — point d'entrée de toute IA

Ce fichier ne porte que la **sobriété de lecture** : chaque octet lu ou imprimé est un coût, et il se joue dans les premières minutes. Les règles qui
annulent un travail sont dans [`CLAUDE.md`](CLAUDE.md), la référence dans [`docs/REGLES_reference.md`](docs/REGLES_reference.md), l'état dans
[`docs/ETAT.md`](docs/ETAT.md) : lis la section 0 de ce dernier et **tiens-la à jour**, selon la consigne qu'elle porte.

Premières commandes (la première doit finir par `PREFLIGHT=GO`) :

```bat
python scripts\preflight.py
python scripts\orient.py
```

`orient.py` rend en une quarantaine de lignes la tête git, l'état de l'arbre, les autres processus python en cours (une mesure lancée pendant qu'une autre
tourne rend `RESULT=None`), la dernière validation et le coût de lecture de chaque document ; `--carte` y ajoute les titres de chaque document avec leurs
lignes, pour ne lire qu'une section (`Read` avec `offset` et `limit`).

## Lire peu

1. **Lis** `CLAUDE.md`, puis la section 0 de `docs/ETAT.md`. **À la demande seulement** : `docs/ETAT_actions.md`, `docs/ETAT_acquis.md`, `docs/REGLES_reference.md`.
2. **Jamais en entier** : `reports/` (84 % des fichiers suivis), `studies/`, `UXargon.md`, `designargon.md`, `ideeargon.md`. Cherche par identifiant
   (`grep -n "ALG-02" designargon.md`) ; dans `reports/`, ouvre le `bilan.md` ou le `README.md` d'un dossier. `.rgignore` les cache aux recherches de contenu
   fondées sur ripgrep ; un chemin explicite les rouvre.
3. **Une sortie de commande est du texte que tu paies.** `pytest` est silencieux par défaut : n'ajoute pas `--verbose` ; ajoute `-q --no-cov`, et `-x` pour
   t'arrêter au premier échec. `git status -sb`, `git log --oneline -n 10` et `git diff --stat` avant tout `git diff`. Ce qui dépasse une page va dans un
   fichier : lis-en la fin.
4. **Lis ce dont tu as besoin** (`offset`, `limit`), pas le fichier ; ne relis pas ce que tu viens d'écrire ; Read et Grep valent mieux que `cat`, `find` et `grep -r`.
5. **Une action, son résultat, la suivante** : n'ouvre ni agents ni processus en parallèle pour explorer. La validation complète et les mesures occupent la
   machine : une seule à la fois.
6. **Écris court** : un document vivant se tient en place (un fait, un seul endroit) ; le rapport d'une campagne va dans `reports/`, jamais à la racine.
