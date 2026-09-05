# AGENTS.md — renvoi

Tout est dans **[`CLAUDE.md`](CLAUDE.md)**, à la racine. C'est le document unique du projet :
vérification d'environnement, onze interdits absolus, sept pièges, boucle de travail,
conventions physiques, spécifications de la machine, point de référence mesuré, état vérifié
et travail à venir.

🔴 **Ne le lis PAS linéairement** — sa section « CARTE DU DOCUMENT » (§3) dit où aller selon
ce que tu fais. ⚠️ *Cette ligne disait « lis-le en entier » : c'était vrai quand le fichier en
faisait 500, plus depuis. Elle annonçait aussi une taille en lignes — retirée le 2026-09-06,
parce qu'un nombre recopié ici se périme au premier commit sur `CLAUDE.md`.*

Ce fichier ne contient volontairement **aucun fait** : deux documents qui se contredisent
coûtent plus qu'ils n'apportent, et ce projet en a déjà supprimé quatre-vingts.

🔴 **Et il l'a violé, jusqu'au 2026-09-06.** Il portait trois faits recopiés, dont **deux
étaient devenus faux** : il prescrivait `dir .git\hooks\post-commit*`, que `CLAUDE.md` §2
désigne désormais comme **la mauvaise commande** — elle peut répondre « rien » alors que le
hook est armé — et il déclarait le hook **ARMÉ** alors que la mesure du 2026-09-05 sur ce
snapshot rend `core.hooksPath` **non défini** et aucun `post-commit` dans `.git/hooks/`.
C'est exactement le mécanisme que la ligne au-dessus décrit : *un fait recopié se périme dans
sa copie*. **Ne rétablis pas ces lignes ; va les lire dans `CLAUDE.md`.**

**La première action est une seule commande**, et elle vérifie l'environnement mieux que
n'importe quelle liste :

```bat
C:\envs\certus\Scripts\python.exe scripts\preflight.py
```

Elle doit finir par `PREFLIGHT=GO`. Le reste — quelle commande interroge le hook, ce que
publier veut dire ici, pourquoi plusieurs copies du dépôt coexistent — est en §2 de
`CLAUDE.md`, **et nulle part ailleurs**.

La seule chose que ce fichier redit, parce qu'elle gouverne tout le reste : le code calcule de
la physique réelle. **Une erreur silencieuse ne plante pas** — elle produit un résultat faux
qui a l'air juste, et quelqu'un fabrique une pièce avec.
