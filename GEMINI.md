# → Va lire `CLAUDE.md`, en entier, avant toute action

Ce fichier ne contient pas d'instructions. Il existe seulement pour t'orienter, quel que
soit le nom de fichier que ton outil cherche en premier.

**Tout est dans [`CLAUDE.md`](CLAUDE.md)** — c'est le document unique du projet, à la
racine. Il commence par une vérification d'environnement qui prend une minute et sans
laquelle tout ce que tu mesureras sera faux.

Les trois choses à ne pas oublier, si tu ne devais en retenir que trois :

1. **Le dossier de travail est `C:\dev\gemini`, et lui seul.** Plusieurs copies de ce dépôt
   existent sur la machine. Modifier l'une et mesurer l'autre ne déclenche aucune erreur —
   seulement des résultats faux.
2. **N'affirme jamais un résultat que tu n'as pas mesuré.** Soit tu colles la sortie de la
   commande, soit tu écris « je n'ai pas mesuré ». Une conclusion écrite avant la mesure
   sera détectée et annulée.
3. **Le code calcule de la physique réelle.** Une erreur silencieuse ne plante pas : elle
   produit un résultat faux qui a l'air juste, et quelqu'un fabrique une pièce avec.
