# → Va lire `CLAUDE.md` avant toute action — mais PAS en entier

Ce fichier ne contient pas d'instructions. Il existe seulement pour t'orienter, quel que
soit le nom de fichier que ton outil cherche en premier.

**Tout est dans [`CLAUDE.md`](CLAUDE.md)** — c'est le document unique du projet, à la
racine. Il commence par une vérification d'environnement qui prend une minute et sans
laquelle tout ce que tu mesureras sera faux.

⚠️ **Ce titre disait « en entier », et c'était le contraire de la consigne.** L'en-tête de
`CLAUDE.md` dit lui-même que *« le lire en entier ne sert à rien »* et renvoie à la **carte du
§3**, qui dit où aller selon ce que tu fais ; `AGENTS.md` disait déjà « ne le lis PAS
linéairement ». Les deux renvois se contredisaient donc sur le seul sujet qu'ils traitent.
Corrigé le 2026-09-06.

Les trois choses à ne pas oublier, si tu ne devais en retenir que trois :

1. **Travaille dans le dépôt que tu as ouvert, et lui seul.** Plusieurs copies existent sur
   la machine. Modifier l'une et mesurer l'autre ne déclenche aucune erreur — seulement des
   résultats faux. ⚠️ Ce fichier annonçait `C:\dev\gemini` ; ce chemin est **périmé**.
   `scripts/preflight.py` vérifie que l'environnement est cohérent, lance-le d'abord.
2. **N'affirme jamais un résultat que tu n'as pas mesuré.** Soit tu colles la sortie de la
   commande, soit tu écris « je n'ai pas mesuré ». Une conclusion écrite avant la mesure
   sera détectée et annulée.
3. **Le code calcule de la physique réelle.** Une erreur silencieuse ne plante pas : elle
   produit un résultat faux qui a l'air juste, et quelqu'un fabrique une pièce avec.
