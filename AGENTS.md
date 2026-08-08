# AGENTS.md — renvoi

Tout est dans **[`CLAUDE.md`](CLAUDE.md)**, à la racine. C'est le document unique du projet :
vérification d'environnement, onze interdits absolus, sept pièges, boucle de travail,
conventions physiques, spécifications de la machine, point de référence mesuré, état vérifié
et travail à venir.

**Lis-le en entier avant de toucher à quoi que ce soit.**

Ce fichier ne contient volontairement rien d'autre : deux documents qui se contredisent
coûtent plus qu'ils n'apportent, et ce projet en a déjà supprimé quatre-vingts.

Trois choses à connaître avant même d'ouvrir `CLAUDE.md`, parce qu'elles invalident tout le
reste si elles sont fausses :

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
dir .git\hooks\post-commit*
```

1. Le chemin affiché **doit** commencer par `C:\dev\gemini`. Plusieurs copies de ce dépôt
   coexistent sur la machine ; si tu modifies l'une et mesures l'autre, rien ne te le dira.
2. Le hook doit s'afficher `post-commit.DESACTIVE`. Sous son nom court il pousse chaque
   commit vers le dépôt **public**, et `--no-verify` ne l'en empêche pas.
3. Le code calcule de la physique réelle. Une erreur silencieuse ne plante pas : elle produit
   un résultat faux qui a l'air juste, et quelqu'un fabrique une pièce avec.
