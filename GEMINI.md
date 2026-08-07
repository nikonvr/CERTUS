# → Va lire `AGENTS.md`, en entier, avant toute action

Ce fichier ne contient pas d'instructions. Il existe seulement pour t'orienter, quel que
soit le nom de fichier que ton outil cherche en premier.

**Tout est dans [`AGENTS.md`](AGENTS.md).** Lis-le en entier avant de toucher au moindre
fichier — il commence par une vérification d'environnement qui prend une minute et sans
laquelle tout ce que tu mesureras sera faux.

Ensuite, dans cet ordre :

| Ordre | Fichier | Pourquoi |
|---|---|---|
| 1 | [`AGENTS.md`](AGENTS.md) | Environnement, les dix interdits, les sept pièges connus. **Obligatoire.** |
| 2 | [`docs/PLAN_STRAT.md`](docs/PLAN_STRAT.md) | Les actions à mener, une par une, avec commande et résultat attendu. |
| 3 | [`docs/JOURNAL_GEMINI.md`](docs/JOURNAL_GEMINI.md) | À remplir au fur et à mesure. **C'est ton livrable principal**, plus important que le code. |
| 4 | [`pages/CERTUS_STRAT.html`](pages/CERTUS_STRAT.html) | Quand tu veux comprendre *pourquoi* le code fait ce qu'il fait. |

Les trois choses à ne pas oublier, si tu ne devais en retenir que trois :

1. **Le dossier de travail est `C:\dev\gemini`, et lui seul.** Plusieurs copies de ce dépôt
   existent sur la machine. Modifier l'une et mesurer l'autre ne déclenche aucune erreur —
   seulement des résultats faux.
2. **Fais tourner toute la suite de tests avant ta première modification** (1 h 45), et note
   le résultat. Sans ce point de comparaison, tu ne sauras jamais si un test rouge vient de
   toi.
3. **N'affirme jamais un chiffre que tu n'as pas mesuré.** Un modèle plus puissant relira
   tout dans une semaine et tentera de reproduire chaque affirmation. Une entrée « je n'ai
   pas réussi » vaut beaucoup mieux qu'une invention.
