# AGENTS.md — renvoi

Tout est dans **[`CLAUDE.md`](CLAUDE.md)**, à la racine. C'est le document unique du projet :
vérification d'environnement, onze interdits absolus, sept pièges, boucle de travail,
conventions physiques, spécifications de la machine, point de référence mesuré, état vérifié
et travail à venir.

🔴 **Ne le lis PAS linéairement** — il fait ~1 900 lignes et sa section « CARTE DU DOCUMENT »
(§3) dit où aller selon ce que tu fais. ⚠️ *Cette ligne disait « lis-le en entier » : c'était
vrai quand le fichier en faisait 500, plus depuis.*

Ce fichier ne contient volontairement rien d'autre : deux documents qui se contredisent
coûtent plus qu'ils n'apportent, et ce projet en a déjà supprimé quatre-vingts.

Trois choses à connaître avant même d'ouvrir `CLAUDE.md`, parce qu'elles invalident tout le
reste si elles sont fausses :

```bat
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
dir .git\hooks\post-commit*
```

1. Le chemin affiché **doit** être dans le dépôt que tu as ouvert. Plusieurs copies de ce dépôt
   coexistent sur la machine ; si tu modifies l'une et mesures l'autre, rien ne te le dira.
2. 🔴 **Le hook `post-commit` est ARMÉ, et c'est l'état VOULU.** 👤 l'a demandé le
   2026-08-14 : **chaque commit pousse vers le dépôt public** `github.com/nikonvr/CERTUS`,
   et `--no-verify` ne l'en empêche pas. **Commiter, c'est publier** — rien qui porte une
   donnée personnelle, un secret ou l'œuvre d'un tiers ne doit entrer dans l'index.
   ⚠️ *Cette ligne disait l'INVERSE — « le hook doit s'afficher `post-commit.DESACTIVE` » —
   jusqu'au 2026-08-19. Un agent qui l'aurait suivie aurait désarmé ce que 👤 a demandé.
   `post-commit.DESACTIVE` est l'ancienne version inerte, gardée à côté.*
3. Le code calcule de la physique réelle. Une erreur silencieuse ne plante pas : elle produit
   un résultat faux qui a l'air juste, et quelqu'un fabrique une pièce avec.
