# CERTUS — document de référence

**C'est le point d'entrée du projet, et la carte de tout le reste.**

⚠️ **Il disait « tout le savoir est ici, il n'y a rien d'autre à lire » — c'est FAUX depuis
les extractions du 2026-08-16.** Le savoir vit dans **une trentaine de fichiers** — `git ls-files '*.md' | wc -l` en donne le compte du jour, 33 le 2026-09-08 : ce document porte les
**directives** et l'**état**, et les dossiers de `docs/` font **autorité** sur leur sujet
(§1). Le lire seul ne suffit pas ; le lire **en entier** ne sert à rien. **Passe par la carte
du §3.**

Le code calcule de la **physique réelle** servant à fabriquer de vrais filtres optiques. Une
erreur silencieuse ne plante pas : elle produit un **résultat faux qui a l'air juste**, et
quelqu'un fabrique une pièce avec.

# PARTIE I — AVANT DE TOUCHER À QUOI QUE CE SOIT

## 0. 🚀 TU ARRIVES SUR CE PROJET ?

| lis d'abord | pourquoi |
|---|---|
| **[`docs/REPRENDRE_ICI.md`](docs/REPRENDRE_ICI.md)** | 🔴 **où on s'est arrêté et la commande exacte pour repartir.** ⚠️ Ce renvoi annonçait « gelé le 2026-08-16 à 08:45 » : le dossier est **daté dans son en-tête**, et c'est lui qui fait foi — ne recopie pas sa date ici, elle se périme à chaque reprise |
| [`docs/MEMOIRE_PROJET.md`](docs/MEMOIRE_PROJET.md) | 🔴 **le savoir opérationnel qui ne suivait PAS le dépôt** : le hook qui publie, le venv qui charge un autre snapshot, les pièges du banc |

Tout le reste de ce fichier est du référentiel : lis-le **par la carte du §3**, pas
linéairement.

---

## 1. 🔒 La règle des documents — lis-la avant de créer quoi que ce soit

**Un seul document d'instructions : celui-ci.** `AGENTS.md` et `GEMINI.md` en sont de simples
renvois et ne contiennent aucun fait.

À côté, **`docs/` porte des dossiers thématiques**, chacun faisant **autorité sur son sujet**.
`CLAUDE.md` n'en garde qu'un renvoi qui dit *ce qu'il faut retenir sans ouvrir le dossier*.

### 🔑 La règle qui compte : UN FAIT, UN SEUL ENDROIT

C'est la cause racine des contradictions de ce dépôt, et elle est mesurée : le 2026-08-16,
corriger le SEEL du 99 couches a demandé **sept modifications à la main**, et une avait été
oubliée au premier passage. Chaque copie d'un fait est une occasion de le laisser périmer.

| ✅ autorisé | 🔴 interdit |
|---|---|
| un dossier **thématique** dans `docs/`, qui devient la source unique de son sujet | un document qui **duplique** un fait déjà écrit ailleurs |
| une **sortie** de campagne dans `reports/` | un **rapport de session** à la racine — 103 y avaient été accumulés |
| un **renvoi** depuis `CLAUDE.md` | recopier le contenu du dossier dans `CLAUDE.md` |

⚠️ **Historique utile, pour ne pas refaire le trajet à l'envers.** Ce dépôt a compté
**quatre-vingts documents contradictoires**, puis la règle est passée à *« exactement deux
fichiers »* — `CLAUDE.md` plus un ordre de mission `GEMINI_TODO.md` destiné à un exécutant à
faible capacité. **Les deux extrêmes étaient mauvais** : la prolifération périme, et le
document unique a atteint **5 413 lignes**, que plus personne ne lisait en entier.

`GEMINI_TODO.md` a été **supprimé le 2026-08-16** : sa campagne était close, et le besoin qui
l'avait fait naître a disparu — un agent d'aujourd'hui lit `CLAUDE.md` et les dossiers sans
qu'on ait à lui pré-mâcher des commandes. 📌 Si un exécutant très contraint revient un jour,
la bonne forme est un **ordre de mission daté dans `docs/`**, comme
`scripts/batch_nuit_2026-08-21.sh` : que des commandes, des sorties attendues, et
zéro fait qui ne soit pas déjà écrit ici.

### 🟢 La cohérence entre dossiers est vérifiée MÉCANIQUEMENT depuis le 2026-08-19

```bat
python scripts\coherence_md.py
```

`check_claude_md.py` vérifie **un** fichier ; celui-ci vérifie que **le même fait porte la
même valeur dans TOUS les `.md`** — c'est-à-dire la règle ci-dessus, appliquée par une machine.

| | |
|---|---|
| **la référence vient du CODE** quand elle existe | six constantes du Rate et de la photométrie sont lues par AST dans les sources : un document qui s'en écarte a tort **même si tous les autres le répètent** |
| **il porte un CONTRÔLE NÉGATIF** | il plante une contradiction volontaire et exige de la détecter. 🔑 *Un harnais dont tout passe toujours ne prouve rien* — et ce contrôle a immédiatement révélé que l'outil n'examinait que **2 lignes sur 9** pour le 48c |
| **il ne comprend pas le français** | une ligne qui **raconte** une correction est écartée par marqueur (« périmé », « non comparable », « score de repli »). Un signalement est **une phrase à lire**, pas une erreur |

📏 Au 2026-09-08 : **0 point à instruire** sur **33 fichiers**, contrôle négatif vert.

🔴 **ET SON PÉRIMÈTRE ÉTAIT PLUS ÉTROIT QUE LE CORPUS — corrigé le 2026-09-08.** Il ne balayait
que la racine et `docs/`, soit 26 fichiers sur 33. Il ne lisait donc pas
`tests/headless/README.md`, qui portait **sept commandes** citant le venv local d'origine —
le **premier** interpréteur mort du projet, jamais corrigé parce qu'aucun contrôle ne le
regardait. 🔑 *Un contrôle de cohérence dont le périmètre est plus étroit que le corpus rend
« 0 point à instruire » sans que cela veuille dire quoi que ce soit.*

⚠️ **Et le contrôle négatif a immédiatement pris ce correctif en défaut** : réduire la liste à
`git ls-files` rendait invisible le fichier que ce contrôle **plante lui-même**, puisqu'il
n'est pas suivi. Le périmètre est donc l'**union** des fichiers suivis et de ce qui traîne à la
racine et dans `docs/` — ce qui a l'autre mérite de vérifier un document **avant** qu'il soit
commité.

### ⚠️ N'ÉCRIS PAS L'ARTEFACT QUE TU DÉCRIS — il fait trébucher le contrôle que tu respectes

📏 **Le motif s'est produit TROIS FOIS dans la seule nuit du 2026-09-06 au 07**, sur trois
outils différents, et chaque fois il a coûté un aller-retour :

| ce qui a été écrit | ce que ça a cassé |
|---|---|
| un commentaire QSS **citant la règle supprimée** en syntaxe littérale | le commentaire vit dans une f-string, donc il est **recraché dans la feuille de style** — la vérification a lu le commentaire et cru que la règle était toujours là |
| une docstring citant `#0f62fe` pour raconter un défaut | `test_ux_design_system` compte les hex **au niveau du texte** : le cliquet est passé de 315 à 316 pour une phrase d'explication |
| un commentaire nommant la constante qu'il explique | l'assertion `"HUB_SUCCESS" not in source` a échoué sur son propre commentaire |

🔑 **La parade est de nommer, pas de citer** : *« la propriété d'image était forcée à la valeur
vide »* plutôt que la ligne QSS ; *« la couleur primaire »* plutôt que son hexadécimal.

⚠️ **Et quand la citation est vraiment utile, c'est au CONTRÔLE de s'adapter** — dépouiller les
commentaires avant de lire une feuille, ignorer les docstrings avant de chercher une URL. Un
contrôle qui interdit d'**expliquer** ce qu'on a corrigé pousse à corriger sans expliquer, ce
qui est pire que le défaut qu'il surveille.

| balayage | ce qu'il couvre |
|---|---|
| **A** — constantes du code | 6 constantes lues par AST, zéro document ne les contredit |
| **B** — grandeurs physiques | 10 faits (SEEL des 4 composants, cadence, bruit, fente, cible, rendement) : **valeur unique** partout. 🟢 **Étendu aux 15 pages HTML le 2026-09-08** — voir l'encadré de la vitrine plus bas |
| **C** — 🔑 **automatique** | **297 symboles numériques** découverts dans `certus/`, **18 cités** dans les `.md`. Tout `NOM = N` écrit dans un document est comparé au code. **Ce balayage grandit tout seul** quand un document cite un symbole de plus |
| **D** — profondeurs par mode | la table `fast/premium/deep` lue dans l'interface, et les **triplets** `50 / 150 / 300` que les documents écrivent |
| **E** — 🔴 **les commandes s'exécutent-elles** | **FATAL, pas « à instruire »** : tout interpréteur et tout script cité dans une commande doit exister, dans les `.md` **et dans les docstrings de `scripts/`**. 📏 103 scripts couverts. ⚠️ *Il ne regardait que l'interpréteur, dans les seuls `.md`, et ses échecs étaient noyés parmi les points à instruire — donc lus comme du bruit pendant des semaines.* Élargi et rendu fatal le 2026-09-08, **contrôle négatif vérifié** : un script inexistant rend `exit 1` |
| **H** — contrôle négatif | plante une contradiction et exige de la détecter |

🔑 **Ce qu'il a trouvé le jour de son écriture** : deux dossiers donnaient **2,5** et **2,7** pour la même grandeur, tous deux dérivés du `0,760 nm` **rétracté**. C'est exactement le genre de divergence qu'aucune relecture humaine n'attrape.
Et **trois défauts de l'outil lui-même**, tous révélés par le contrôle négatif ou par
l'instruction des signalements : comptage de motifs au lieu de composants, appariement croisé
de deux triplets sur une même ligne, et distance d'appariement non bornée.

⚠️ **Et la couverture, dite honnêtement** : les `.md` portent **~1 200 chiffres affirmés**.
Cet outil en vérifie une petite part — **celle qui porte une décision**. Il ne dit **rien** des
affirmations sans chiffre, et c'est là qu'était l'erreur de mécanisme du Rate du 2026-08-19 :
une phrase, aucun nombre, fausse. **« 0 point à instruire » ne veut pas dire « tout est
cohérent ».**

### Le budget, et il est vérifié mécaniquement

⚠️ **AVANT DE COURIR APRÈS LES SIGNALEMENTS DU CONTRÔLEUR, lis ceci.** `check_claude_md.py`
rend en permanence des « VALEURS DISCORDANTES », et elles ont été instruites une par une le
2026-08-19 : **ce sont des faux positifs**, le contrôle rapprochant un nom de paramètre du
premier nombre voisin. `index_corridor` attrape un **hash** · `machine_sampling_dd` des
**comptages** de phrase · `reading_smoothing_window` la **durée** de la fenêtre ·
`phase_a_level_margin_factor` porte **deux valeurs légitimes**, l'actuelle et celle à évaluer.

⚠️ **Vérifie les NOMS, pas les nombres — et ce paragraphe vient d'en donner la preuve.** Il
listait **cinq** noms et un plancher de 5 ; 📏 le 2026-09-09 le contrôle en rend **quatre**.
`dp_yield_weight` en est sorti tout seul, parce qu'une phrase voisine a changé — c'est
exactement ce que cet avertissement annonçait, arrivé à l'avertissement lui-même. **Ne recopie
donc pas le compte : lance le contrôle, et instruis tout nom qui n'est pas dans la liste
ci-dessus.**

🟢 **Et le contrôle B, lui, est à ZÉRO — il n'y est pas resté tout seul.** 📏 Sortir les
repères de mesure et les défauts ouverts vers leurs dossiers, le 2026-09-08, a laissé
**17 renvois internes pointant dans le vide**, la carte du document en tête. Tous corrigés le
lendemain. ⚠️ Le contrôle n'en signalait que **deux**, parce qu'il déduplique par numéro —
*un compte de signalements n'est pas un compte de défauts.*

⚠️ **Et ce paragraphe-ci a d'abord nommé les deux sections par leur numéro, donc il s'est
signalé lui-même.** C'est le motif que ce document décrit plus haut, la quatrième fois qu'il
frappe : **nommer, ne pas citer.**

🔑 **Le contrôle reste utile — il a trouvé la vraie contradiction du 2026-08-19**, deux lignes
du même paramètre dans la table de §19, l'une prescrivant 8 et l'autre 1. **Ne le désarme
pas ; sache seulement que son plancher n'est pas 0 sur le contrôle C.**

🔴 **`CLAUDE.md` N'EST PLUS PLAFONNÉ — la contrainte des 2 000 lignes est retirée le
2026-09-06, sur décision de 👤.** Le contrôle F subsiste, mais **informatif** : il rapporte la
taille et ne compte plus jamais comme une faute.

🔑 **Pourquoi c'est cohérent avec ce qui a motivé le plafond.** La cause racine désignée en
2026-08-16 n'a jamais été la longueur : c'était que **le même fait était énoncé à plusieurs
endroits**. Or cela, c'est `coherence_md.py` qui le mesure — sur tous les `.md` à la fois, et
avec un contrôle négatif qui prouve qu'il mord. Un nombre de lignes n'en est qu'un **proxy**,
et un proxy qui *échoue* pousse à extraire une section **pour tenir un chiffre**, pas parce
qu'elle mérite son dossier.

⚠️ **Ce qui ne change pas** : un fichier qui grossit reste un signal à lire, et la règle
« un fait, un seul endroit » reste la vraie contrainte. Quand une section mérite vraiment son
dossier, `scripts/extraire_section.py` le fait proprement — il laisse un renvoi à la place et
**refuse de résumer tout seul**, parce qu'un résumé mécanique dirait ce que la section
*contient* et non ce qu'un agent doit en *retenir*.

---

## 2. ⚡ DÉMARRAGE — fais ces 4 choses, dans cet ordre, avant tout le reste

**Une seule commande fait les trois premiers points, et elle est à jour :**

```bat
python scripts\preflight.py
```

Elle doit finir par `PREFLIGHT=GO`. Ce qui suit explique **ce qu'elle vérifie et pourquoi**,
à lire une fois.

**1. Vérifie que tu es dans le bon dossier.**

```bat
python -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

Le chemin affiché **doit être dans l'arbre où tu édites**.
Si ce n'est pas le cas → **ARRÊTE-TOI. Signale-le. Ne modifie rien.**

🔴 **CE DOCUMENT A PRESCRIT UN INTERPRÉTEUR MORT TROIS FOIS DE SUITE, ET C'EST LA MÊME ERREUR
À CHAQUE FOIS.** Les commandes de ce fichier disent maintenant `python`, sans chemin. Ce n'est
pas un relâchement : c'est la conclusion de trois échecs mesurés.

| ce que le document prescrivait | ce qui était vrai |
|---|---|
| `.venv\Scripts\python.exe` | corrigé le 2026-08-19 dans les `.md` — **47 commandes sur 10 fichiers** inexécutables, à commencer par la toute première de ce §2 |
| `C:\envs\certus\Scripts\python.exe` | corrigé le 2026-09-08, et ce dossier n'existe plus du tout sur la machine |
| *(plus aucun chemin)* | le projet tourne sur le **Python système**, sans venv |

📏 **Le nettoyage du 2026-09-08, et son enseignement.** 38 commandes dans les `.md`, puis 7 de
plus dans un README que rien ne balayait, puis **25 lignes d'usage** dans des docstrings de
`scripts/` — et une fois le contrôle E élargi à ces fichiers, **78 de plus, dans 57 fichiers**,
écrites avec des antislashs **doublés** que ma recherche manuelle ne voyait pas. Total :
**150 commandes mortes**, dont **deux dans du code exécuté** — le lanceur de la recherche
multi-graines échouait donc à chaque appel sans surcharge d'environnement.

🔑 **C'est l'argument entier pour un instrument plutôt qu'une relecture** : j'ai balayé à la
main, déclaré le nettoyage fini, et l'outil a immédiatement trouvé trois fois plus. *Une
recherche à la main ne connaît que les orthographes auxquelles on a pensé.*

🔑 **LA RÈGLE QUI REMPLACE LE CHEMIN : un document ne nomme pas l'interpréteur, il nomme la
PROPRIÉTÉ qu'il doit avoir.** Elles sont deux — `import certus` doit résoudre **dans l'arbre où
tu édites**, et l'interpréteur doit porter les dépendances — et `preflight.py` vérifie les
deux. Un chemin, lui, se périme au premier déménagement, et il l'a fait deux fois.

⚠️ **`preflight.py` s'est trompé trois fois, toujours de la même façon**, et c'est le meilleur
exemple du piège. Il a exigé `.venv` **dans le chemin**, puis un `pyvenv.cfg` **à côté** — deux
**proxys** de la vraie question. Or cette machine n'a aucun venv : le contrôle avertissait donc
**en permanence sur la seule configuration qui existe**, et un avertissement permanent apprend
à ignorer les avertissements. 📏 Corrigé le 2026-09-08 : il vérifie que `PyQt6`, `numpy`,
`scipy` et `numba` s'importent — *« cet interpréteur est-il équipé »*, qui est la propriété
cherchée depuis le début. Un venv n'en était qu'un proxy.

🔑 **Si tu doutes de l'interpréteur, demande-le à Python, pas à un document :**
`python -c "import sys; print(sys.executable)"`.

🔴 **Il n'y a PAS de racine attendue en dur, et c'est délibéré.** Ce document a longtemps
exigé `C:\dev\gemini` — **un dossier qui n'existe plus**, et la constante `EXPECTED_ROOT`
qui le portait dans `preflight.py` n'était lue par aucun contrôle. Une consigne qui
protégeait de l'erreur n°1 envoyait donc vers un dossier fantôme, en silence. Le projet vit
dans des snapshots datés copiés les uns depuis les autres (`0108`, `0807`, `1408`, …) : la
seule question qui survive à une copie est *« est-ce que `import certus` résout DANS l'arbre
courant ? »*

**2. Sais-tu si committer PUBLIE ?**

```bat
git config --get core.hooksPath
git remote get-url origin
```

🔴 **C'est `core.hooksPath` qu'il faut interroger, PAS `dir .git\hooks\`.** Ce document
prescrivait le second pendant des semaines, et **il peut répondre « rien » alors que le hook
est armé** : quand `core.hooksPath` pointe sur `.githooks`, git n'utilise plus `.git/hooks/`
du tout. Une commande qui rassure à tort sur une publication est pire que pas de commande.

👤 a demandé le **2026-08-14** que le push soit **armé**. Le hook vit dans
**`.githooks/post-commit`**, qui **est versionné**, et il ne s'arme que par
`git config core.hooksPath .githooks` — une configuration **locale**, donc **jamais héritée
d'un clone ni d'une copie de snapshot**. `--no-verify` ne l'arrêterait pas : il ne saute que
`pre-commit` et `commit-msg`.

⚠️ **Ce paragraphe a longtemps conclu « commiter, c'est publier ». C'est FAUX dès que
`core.hooksPath` n'est pas réglé, ce qui est le cas par défaut.** 📏 Mesuré le 2026-09-05 sur
ce snapshot : `core.hooksPath` **non défini**, `.git/hooks/` ne contient que des `.sample`, et
un commit est resté `[ahead 1]` jusqu'à un `git push` explicite. **Vérifie l'état, ne le
suppose pas :**

```bat
git config --get core.hooksPath
dir .githooks
```

🔴 **Ce qui reste vrai et permanent, et c'est le seul point qui compte : le dépôt est
PUBLIC.** Que la publication vienne du hook ou d'un `git push` à la main, rien qui porte une
donnée personnelle, un secret, ou l'œuvre d'un tiers ne doit entrer dans l'index. Le
2026-08-14 le dépôt portait encore un nom civil dans six fichiers Excel, un nom de session
dans 114 lignes de journaux, et le texte intégral d'une thèse tierce.

🔴 **ET CE N'EST PAS RÉGLÉ — le nettoyage du 2026-08-14 n'a nettoyé que l'ARBRE DE TRAVAIL.**
📏 Mesuré le 2026-08-17 :

```
41626b8  2026-08-07  ajoute  reports/_zideluns_text.json   377 498 octets
f4c05c6  2026-08-14  "fix(prive): le depot public ne porte plus de donnee personnelle"

encore lisibles a f4c05c6^ :
  377 498 o  reports/_zideluns_text.json   (206 blocs de prose indexes par page)
  155 648 o  .vs/slnx.sqlite
    8 192 o  .vs/1705/v17/.wsuo
      508 o  .vs/1705/v17/DocumentLayout.json
       73 o  .vs/VSWorkspaceState.json

41626b8 ancetre de HEAD : True      sur origin/refactor-corridors-mixins : True
```

`f4c05c6` a **supprimé** ces cinq fichiers et **modifié les six `.xls` en place** — tailles
identiques avant/après, donc le contenu a été corrigé sur place. Or **une suppression comme
une modification laissent la version antérieure dans l'historique.** Le texte de la thèse se
récupère du dépôt public en une commande, et les `.xls` d'avant correctif aussi.
`.gitignore:137` porte une règle dédiée à ce fichier : elle empêche une *future* addition,
elle ne touche pas au passé.

⚠️ **Ne prends donc pas ce commit pour un règlement.** Purger demande `git filter-repo` puis
un **force-push** : tous les SHA à partir du 2026-08-07 changent, donc **tous les hash cités
dans ce document et dans `docs/` deviennent faux**, ainsi que l'objet du tag `depart-gemini`.
GitHub conserve en plus les blobs devenus inatteignables jusqu'à ce qu'on lui demande de les
collecter. C'est une décision de 👤, pas une correction de routine.

📌 Sur la gravité, honnêtement : une thèse est en général publiquement accessible — l'enjeu
est la **rediffusion**, et il dépend de sa licence. Mais au regard de la règle écrite juste
au-dessus, la violation est **toujours active**.

**3. Vérifie que tout est vert avant de toucher à quoi que ce soit.**

```bat
python -m ruff check .
python -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Attendu : `All checks passed!` puis **zéro échec**.
Si un test est rouge **avant** que tu n'aies rien touché → **ARRÊTE-TOI et signale.**
Ce n'est pas à toi de le réparer.

🔴 **CETTE COMMANDE NE COUVRE PAS L'INTERFACE — ajoute `tests/ui/` si tu y touches.**
`tests/oracle/ + tests/unit/` ignore entièrement `tests/ui/`, qui porte les garde-fous
d'ergonomie. 📏 Le 2026-09-05, une journée de validations menées sur un périmètre trop étroit
a **publié un test cassé** sans que rien ne le signale — il vivait dans `tests/unit/`, exclu
d'un périmètre restreint à `tests/ui/`. **La leçon vaut dans les deux sens :**

```bat
python -m pytest tests/oracle/ -q --no-cov
python -m pytest tests/unit/ -q --no-cov
python -m pytest tests/ui/ -q --no-cov --deselect tests/ui/test_ux_re_stop_when_idle.py
python -m pytest tests/ui/test_ux_re_stop_when_idle.py -q --no-cov
```

🟢 **`tests/oracle/` d'abord, et il coûte 6,48 s** — 569 tests, mesuré le 2026-09-08. ⚠️ *Ce
bloc l'avait omis pendant une journée : c'est la référence TMM indépendante, elle couvre R, T,
l'incidence oblique **et les gradients analytiques**, et rien ne justifie de la sauter.*
📏 Le §16 annonçait `89,72 s` au 2026-08-17 : **14 fois plus lent**, à cache numba froid.

🔴 **EN TROIS COMMANDES, ET CE N'EST PAS UNE COMMODITÉ.** ⚠️ *Ce paragraphe annonçait une passe
unique « de 33 à 53 min » : sur la machine du 2026-09-08 elle **n'aboutit pas**, et deux
tentatives ont été tuées par leur propre plafond de 90 minutes.* 📏 Mesuré ce jour-là :

| commande | durée | pourquoi |
|---|---|---|
| `tests/unit/` | **2 min 58**, 2 456 tests | toute la lenteur est ailleurs |
| `tests/ui/` sans le fichier écarté | **> 50 min** | chaque test construit des fenêtres Qt en sous-processus |
| `tests/ui/test_ux_re_stop_when_idle.py` | **6,90 s seul** | 🔴 mais **~9 min PAR TEST** dans la suite complète — un facteur ~500, cause inconnue, reproduit sur deux passes |

🔑 **Et découper a un second mérite** : un arrêt natif dans une moitié ne détruit plus le
verdict de l'autre. Ce n'est pas une commande qu'on lance entre deux éditions — c'est celle qui
décide qu'un travail est fini.

⚠️ **Une passe qui enjambe une édition n'est pas un verdict** : les modules déjà importés
gardent l'ancien code, ceux qui restent prennent le nouveau, et le résultat ne décrit aucun
arbre existant. Deux passes ont dû être jetées le 2026-09-08 pour l'avoir oublié.

🔴 **NE COMPARE PAS LE NOMBRE DE TESTS À UN CHIFFRE ÉCRIT ICI — COMPTE-LE.** Ce document a
porté successivement 2 300, 2 301, 2 310 et 2 450 pour la même commande, et **aucun de ces
chiffres ne survit à l'ajout d'un test**, c'est-à-dire à une journée de travail normale.
📏 Mesuré le 2026-08-19 : **2 453 tests collectés** au commit `ba7e118~1`, **2 456** après
l'ajout de trois tests le même jour — l'écart de 3 est exactement celui des trois ajouts.

```bat
python -m pytest tests/oracle/ tests/unit/ -q --no-cov --collect-only
```

**Le seul critère qui vaut est `0 failed`.** Un compte qui bouge de +3 parce qu'on a fait son
travail n'est pas une régression ; un test rouge en est une. ⚠️ La répartition
`passed / skipped` n'est **pas** consignée ici, parce qu'elle n'a pas été remesurée depuis
l'ajout — et écrire un chiffre non mesuré est précisément l'interdit n° 9.

🔴 **UNE EXCEPTION, ET ELLE VA TE TOMBER DESSUS SI TU VIENS DE MONTER UN VENV.** Sur un
cache numba **froid**, la première passe rend **3 échecs** — et ils sont faux.

```
1re passe, venv neuf, cache FROID  ->  3 failed   (les trois nommes ci-dessous)
2e passe, cache CHAUD              ->  0 failed

meme motif reproduit le 2026-08-19 apres un changement de signature de noyau,
qui force la recompilation donc rend le cache froid : 3 failed puis 0 failed.
```

📏 Mesuré le 2026-08-17. Les trois sont `tests/unit/test_phase2_gradient.py::test_phase2_gradient_analytic_vs_fd`
et les deux `TestIRGlobalModelStrategy` de `tests/unit/workers/test_index_workers_ir_strat.py`.
**Ils passent isolément.** Cause dans **numba lui-même** — donc dans le venv, pas dans ce
dépôt : `ir_utils.py` (paquet `numba.core`) fait, ligne 1702, un `import numba.core.inline_closurecall`
**à l'intérieur** de `get_ir_of_code`. Un import de chemin pointé dans une fonction crée une
**locale** `numba`, résolue depuis `sys.modules` **à l'appel** — et non l'objet capturé par
l'`import numba` du haut du module. Ce chemin n'est
emprunté que pendant une **compilation réelle** : à cache chaud, la fonction est chargée et
le défaut ne peut pas se manifester. `tests/conftest.py:259` protège `os.environ` par une
fixture `autouse` — *« to prevent Numba env pollution »* — mais **rien ne protège
`sys.modules`**. C'est l'audit resté ouvert au §2.2 de
[`REPRISE_TESTS_ISOLATION.md`](docs/REPRISE_TESTS_ISOLATION.md).

**Donc : relance une seconde fois avant de signaler quoi que ce soit.** Le test fautif n'a
pas été identifié — `test_pure_imports.py` est écarté (il ne supprime que les modules dont le
nom contient `certus_core`).

⚠️ **Les durées ci-dessus appartiennent à une machine, pas au projet** : i5-8250U, 4 cœurs /
8 threads, 7,9 Go. La ligne précédente annonçait « 7 min » sans dire sur quoi. Ne compare
jamais une durée sans sa machine — c'est ce qui a failli coûter une campagne le 2026-08-17.

**4. Va à la CARTE DU §3, prends-y le programme courant, et choisis UNE action. Une seule.**

🔴 **Cette étape disait « Lis §29 », et elle envoyait au mauvais endroit.** Le §29 est *le
travail à venir sur le **modèle physique*** — un carnet de chantiers valides qui **n'est pas
le programme courant**. Un agent neuf qui exécutait les quatre étapes de démarrage dans
l'ordre atterrissait donc dans la file physique, pendant que la campagne réellement en cours
était ailleurs. ⚠️ **C'est la cinquième fois que ce document retarde sur « quel est le
programme courant »**, après la carte du §3, le titre du §23, la règle 4 du §11 et le
vocabulaire du §14 — et le §34 énonce précisément la parade : *quel EST le programme courant
se lit à **un seul endroit**, la carte du §3.* Trouvé le 2026-09-06.

⚠️ **Et « une seule action » n'est pas une formule de style** : c'est l'erreur n° 3 du §5.
Deux changements simultanés ne s'attribuent pas.

---

## 3. ⚡ CARTE DU DOCUMENT — où aller selon ce que tu fais

| Tu veux… | Va où |
|---|---|
| 🚀 **Arriver sur le projet** | **[`docs/REPRENDRE_ICI.md`](docs/REPRENDRE_ICI.md)** — l'**unique** document d'arrivée : où on s'est arrêté, les chiffres acquis, ce qui reste ouvert, et la première action avec sa règle de décision |
| Savoir ce qui est interdit | §6 — les onze interdits |
| Savoir dans quoi tu vas tomber | §7 — les sept pièges |
| Savoir comment travailler | §9 — la boucle et la règle d'or |
| Comprendre un mot du projet | **§14 — vocabulaire.** 🔴 Y lire **QWOT ≠ point tournant** avant d'écrire sur les points d'arrêt |
| Toucher à du calcul optique | §16 — conventions physiques et oracle TMM |
| Comprendre la machine de dépôt | §17 — les spécifications du physicien |
| **Ce qu'on suppose de la machine** | **§18 — le modèle FIGÉ de la chaîne de lecture. Ne pas le rouvrir.** |
| **Comparer un résultat** | **[`REPERES_MESURES.md`](docs/REPERES_MESURES.md) — les repères valides, tous fente 2 nm.** Ce qui les périme y est dit, et pourquoi ils ne se comparent pas entre composants |
| **Savoir ce qui est encore cassé** | **[`DEFAUTS_OUVERTS.md`](docs/DEFAUTS_OUVERTS.md) — défauts ouverts. À lire avant toute action.** |
| Comprendre le mode Rate | **§22, bloc « Le mode Rate »** — noyau écrit **et** variantes actives par défaut. ⚠️ Trois critères distincts s'y mélangent, démêlés dans l'encadré *« le rate est souvent réservé aux couches fines »* |
| Vérifier le travail d'un autre agent | §12 — protocole de re-vérification |
| **Quand §23 sera fini** | §34 — A25, A26, A27, en réserve, et les cinq choses à ne PAS faire |

### Les dossiers de `docs/` — extraits de ce fichier le 2026-08-16

🔑 **Un fait, un seul endroit.** Ces dossiers **font autorité** sur leur sujet ; ce fichier
n'en garde qu'un renvoi.

⚠️ **Les tailles en lignes citées plus bas sont INDICATIVES et se périment à chaque édition.**
Vérifiées le 2026-08-19 : toutes à moins de 3 % du réel sauf `CHANTIER_MULTITEMOINS.md`, qui
annonçait 954 pour **1 079**. Elles servent à dire *« c'est un gros dossier »*, jamais à être
citées comme un fait. Si tu corriges un chiffre, corrige-le **là-bas** et nulle part
ailleurs — c'est la règle qui empêche les contradictions de revenir.

| dossier | quand l'ouvrir |
|---|---|
| **[`REPRENDRE_ICI.md`](docs/REPRENDRE_ICI.md)** | 🚀 en arrivant, toujours — et c'est le **seul** document d'arrivée |
| [`CHANTIER_MULTITEMOINS.md`](docs/CHANTIER_MULTITEMOINS.md) | multi-témoins, 12 sous-sections. ⚠️ **Ce renvoi le disait « le programme courant » — il ne l'est plus depuis le 2026-08-19.** Le chantier vivant est [`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md) ; celui-ci est **acquis et consultable**, pas en cours |
| [`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md) | 🔑 **employer pleinement le Rate**, et mélanger POEM / niveau absolu / Rate. 📏 Son coût est une **pénalité de SEEL qui CROÎT avec la profondeur** — +1 % à 35 couches, +9 % à 48, +22 % à 75. ⚠️ Le « facteur 175 » d'une rédaction antérieure était un **paradoxe de Simpson**, retiré le 2026-08-19 |
| **[`CHANTIER_PREDICTIBILITE.md`](docs/CHANTIER_PREDICTIBILITE.md)** | 🔵 **ouvert par 👤 le 2026-08-17** — *prédire sans tout calculer si un design passe avec un seul verre témoin*. 🔑 À retenir sans l'ouvrir : **le 99c n'est PAS une référence valable** (tout QWOT ⇒ adverse à POEM par construction, réponse plate à 100 % qui ne discrimine rien) · **la série d'échelle du random75 ×0,5/×1/×1,5/×2 est la seule expérience CONTRÔLÉE du projet** · **quatre routes y sont déjà fermées par la mesure** · 🔴 **`search_resolution` était neutralisé dans toute la campagne des intervalles alors que 👤 l'a posé comme prérequis** · 🔴 **le mode `extreme` n'améliore le SEEL sur AUCUNE des configurations testées** (§4quater-bis, matrice arrêtée le 2026-08-19 sur décision de 👤 ; `deep` seul fait mieux à un cinquième du coût) |
| 🔴 **[`PLAN_PRODUCTION_2026-08-20.md`](docs/PLAN_PRODUCTION_2026-08-20.md)** | **LE PROGRAMME COURANT DU CALCUL.** Ses **§15 à §24** portent tout ce qui est récent : le multiseed au criblage, l'injection de plans, la fermeture de la voie ELITE, la diversité en λ |
| 🔴 **[`ORDRE_CLOUD_2026-09-25.md`](docs/ORDRE_CLOUD_2026-09-25.md)** | **LE TRAVAIL LANCÉ LE 2026-09-25**, quatre tâches cloud sur des branches `cloud/*` : cure documentaire (ce fichier doit passer sous 250 lignes), CI Linux, commentaires de `certus/` en anglais, substrat Si. Rien n'est fusionné sans relecture de 👤 |
| 🔴 **[`UX_PLAN.md`](docs/UX_PLAN.md)** | **LE PROGRAMME COURANT DE L'INTERFACE.** Son **§0** dit où on en est en une table. État au 2026-09-08 : **§3 et §4 entièrement clos**, 12 critères de fin sur 13 atteints et mesurés. 🔑 À retenir sans l'ouvrir : le périmètre de validation est **`tests/ui/ + tests/unit/`**, jamais `tests/ui/` seul — un test cassé a été publié pour l'avoir oublié · **mesure ce qui est RENDU, pas ce qui est déclaré** : trois garde-fous verts se sont révélés vérifier l'intention et non l'écran · **ce qui reste n'est pas du code** — une revue visuelle par 👤 et trois arbitrages |
| [`UX_DEMENTIS.md`](docs/UX_DEMENTIS.md) | 🆕 les affirmations du chantier d'interface **que la mesure a réfutées**, avec le mécanisme qui les rendait crédibles — « SUBSTRATE INDEX est cassé », « Clear/Reset ne fait rien », « la police est uniformisée »… ⚠️ **Ce n'est pas un plan** : aucune étape à faire, seulement des erreurs de jugement instruites. 📌 Extrait le 2026-09-08 de `GEMINI_UX_TOP1_2026-09-04.md`, **supprimé le même jour** : son propre en-tête déclarait ses tableaux d'état périmés pendant que ce renvoi l'appelait « programme courant ». Son prédécesseur `TODO_UX_2026-09-03.md` avait été supprimé de même le 2026-09-06 ; `git log` garde les deux |
| [`QWOT_ET_TURNING_POINT.md`](docs/QWOT_ET_TURNING_POINT.md) | 🔴 **obligatoire** avant d'écrire sur les points tournants |
| [`FEUILLE_DE_ROUTE.md`](docs/FEUILLE_DE_ROUTE.md) | ce qui est acquis (A1→A25), ce qui est outillé |
| [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) | les chantiers du modèle physique, 12.1 à 12.7 |
| [`SEEL.md`](docs/SEEL.md) | 🆕 extrait de §22 le 2026-08-19 : la définition, la règle de tri, le revirement 0,1 → 0,01 nm et son prix non mesuré, et le code mort de la seconde borne |
| [`CHANTIERS_OUVERTS.md`](docs/CHANTIERS_OUVERTS.md) | 🆕 extrait de §27 le 2026-08-19 : les deux propositions de 👤 non mesurées, isolation des tests, perf |
| [`ETAT_IMPLANTATION.md`](docs/ETAT_IMPLANTATION.md) | ce qui est **réellement** implanté, établi contre le CODE |
| [`COMPOSANTS.md`](docs/COMPOSANTS.md) | les composants d'essai, **et la série d'échelle du random75** dont `r75x2` est la variante ×2 |
| [`DECISIONS_TRANCHEES.md`](docs/DECISIONS_TRANCHEES.md) | grille des λ, profondeur Monte-Carlo, les deux correctifs |
| [`PERFORMANCE.md`](docs/PERFORMANCE.md) | ⚡ ce qui a été mesuré, **y compris les pistes fermées** |
| [`ENONCE_PROBLEME.md`](reports/ENONCE_PROBLEME.md) | énoncé autonome, pour poser le problème à un tiers |

#### 🔴 Les quatre documents que cette carte ne nommait pas — rattachés le 2026-09-08

📏 Le corpus compte **33 `.md` suivis, 17 323 lignes**. Quatre n'étaient cités **par aucun
autre fichier ET absents de cette carte** — donc invisibles à un agent qui suit les
instructions. **Aucun n'était vide de sens** : c'est le rattachement qui manquait, pas le
contenu. 🔑 *Et l'orphelinat coûte* : `tests/headless/README.md` a gardé **sept commandes
citant le tout premier interpréteur mort** parce qu'aucun contrôle ni aucune carte ne le
regardait.

| dossier | ce qu'il porte, et pourquoi il compte |
|---|---|
| [`PLAN_AMELIORATION.md`](docs/PLAN_AMELIORATION.md) | 🔴 **quatre chantiers OUVERTS** que rien n'annonçait ici : le cycle d'imports `physics ↔ core` (A6 / lot E), l'oracle étendu aux **gradients** (lot B) — *un gradient faux ne lève pas, il fait converger ailleurs* —, l'hygiène d'imports (lot C), et CI / property-based / contrats de signature (D2-D4) |
| [`README_REGRESSION_TESTS.md`](tests/regression/README_REGRESSION_TESTS.md) | la suite **Golden Master** de convergence, et sa règle *« toute modification de code DOIT passer cette suite »*. 🔴 Voir l'avertissement ci-dessous : elle ne tourne pas sous `pytest` |
| [`README_REFERENCE_CONFORMANCE.md`](pages/README_REFERENCE_CONFORMANCE.md) | les règles des pages HTML de `pages/`, **et une mesure ouverte** : 13 pages sur 15 déclarent `lang="en"`, deux non |
| [`RAPPORT_FILTRE_EXTREME_5CAV_99C.md`](example/example_strat/RAPPORT_FILTRE_EXTREME_5CAV_99C.md) | l'étude du passe-bande **99 couches** — formule, matériaux, performances TMM, règles de dépôt. ⚠️ [`COMPOSANTS.md`](docs/COMPOSANTS.md) ne couvre PAS ce composant : ce n'est pas un doublon |

🟢 **LA SUITE « OBLIGATOIRE » TOURNE DEPUIS LE 2026-09-08 — elle rendait `collected 0 items`.**
`test_convergence.py` porte un nom que `pytest` ramasse, mais c'est un **script**
(`main()` + `if __name__`). La règle *« passe obligatoire avant toute validation »*, affichée
par son lanceur, désignait donc une suite qui **n'existait pas dans la suite de tests** — un
zéro silencieux dans un vert. `test_convergence_guard.py` expose de vrais tests : il **appelle**
les fonctions du script au lieu de les copier. 📏 **8 tests, 4 min 10, tous verts.**

🔴 **Et deux de ses sept modules mesuraient un MOCK.** `tests/headless/test_design.py` et
`test_strat.py` remplacent le calcul — ce que le §4 dit depuis longtemps et que ce harnais
ignorait. Le mock de STRAT émet zéro stratégie, donc une RMSE infinie : **sa référence
`0,01706` était inatteignable par construction**, un fossile d'avant le mock qui produisait un
rouge que personne ne pouvait corriger. Retirée. *Une entrée qui ne peut pas passer apprend à
ignorer la suite.*

🟢 **INDEX est mesuré depuis le même jour** : son script cherchait un attribut `rmse_final`
que l'objet de résultats ne porte pas — il porte `final_mse` — et retombait donc en silence
sur l'infini. Corrigé, et la conversion n'est pas devinée : le code du projet calcule sa RMSE
par `sqrt(max(final_mse, 0))`. **MSE et RMSE sont deux grandeurs.** INDEX rend **0,00257**.

📌 **Couverture honnête : 5 modules sur 7.** La référence d'INDEX a été **capturée, pas
validée** — elle dit *« pas pire qu'aujourd'hui »*. Rendre DESIGN et STRAT mesurables demande
un script headless qui exécute vraiment le pipeline : c'est un chantier.

🔑 **La page qui compte, et 👤 l'a dit : `pages/CERTUS_STRAT.html`.**

> 👤 *« c'est strat.html le fichier ultra important. C'est lui qui convaincra les acheteurs
> potentiels du code ! »* (2026-08-14)

C'est une **vitrine commerciale et technique**, publiée sur un dépôt public. Elle ne contient
aucune instruction, et elle a un régime propre :

| | |
|---|---|
| **Une affirmation fausse y coûte plus qu'un manque** | Un évaluateur qui prend un chiffre en défaut cesse de croire le reste. Tout nombre doit être sourçable dans le code ou dans un artefact de `reports/`. |
| **La nuance juste convainc, le superlatif non** | « le meilleur partitionnement **mesuré** sur deux empilements » se défend ; « l'optimum universel » se réfute en une question. |
| **Elle doit montrer sa LIMITE** | Son §21.15, dans `CERTUS_STRAT.html`, porte le 99 couches, dont **aucune stratégie ne survit** — plantage 100 %, et le 0,86 nm qui traîne est un **score de repli**. Un expert le trouverait de toute façon. |
| **Et ce qui lève la limite** | **§21.16 de `CERTUS_STRAT.html` — multiple testglass**, ajoutée le 2026-08-15 : le même 99 couches devient fabricable, **0,81 nm** à 0 % de plantage. ⚠️ Le `0,782` était le plus **favorable de trois graines** (0,782 / 0,816 / 0,839) — corrigé le 17/08. Elle dit aussi les trois attentes que la mesure a **démenties**, et ce qui n'est **pas** revendiqué (borne supérieure, une seule graine). |
| **Vérifie la STRUCTURE après toute édition** | Le 2026-08-14 un `</ul>` supprimé faisait rendre 400 lignes à l'intérieur d'une liste, et avait emporté une puce entière. `python scripts/verifier_html.py pages/*.html` — 📏 **les 15 pages passent** au 2026-09-08. |

🟢 **ET SES CHIFFRES SONT ENFIN VÉRIFIÉS PAR UNE MACHINE — 2026-09-08.** Le contrôle B de
`coherence_md.py` ne lisait que les `.md` : **le document que 👤 juge le plus important était
hors de tout périmètre**, et pouvait affirmer une valeur que le corpus a rétractée sans que
rien ne le dise. Il balaye désormais aussi les 15 pages, balises retirées.

📏 **Et le verdict est bon** : sur les 10 grandeurs, **valeur unique partout** — la cadence
machine passe de 7 à **11 citations**, preuve que les pages sont bien lues. J'avais soupçonné
l'inverse : la vitrine cite `0,86 nm` **sept fois** et `0,782 nm` **six fois**, deux chiffres
rétractés. ⚠️ **Vérification faite, elle les cite AVEC leur rétractation** — *« it is NOT a
robustness score »*, *« the most favourable of three seeds »*. **Ma suspicion était fausse
deux fois.**

🔑 **Le défaut n'était donc pas son contenu, c'était qu'aucune machine ne le tenait.** Elle est
juste parce qu'on l'a maintenue ; elle le restera parce qu'un contrôle négatif le prouve — une
valeur contradictoire plantée dans une page **est détectée et nommée**.

Les autres pages de `pages/` (14 fichiers : DESIGN, INDEX, FIELD, HUB, RE, METAL, métrologie…)
et les rapports de `reports/*.html` existent aussi. ⚠️ Ceux de `reports/` **ne chargent aucun
moteur mathématique** : tout `$...$` y sort en texte brut.

---

## 4. Vérifier l'environnement — une minute, non négociable

```bat
python -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
git config --get core.hooksPath
```

- Le chemin affiché **doit** être dans le dépôt que tu as ouvert. 🔴 **Plusieurs copies de
  ce dépôt coexistent sur la machine.** Si le chemin pointe ailleurs, tu modifies un dossier
  et tu en mesures un autre : tout ce que tu constateras sera faux, **sans le moindre message
  d'erreur**. C'est le piège n° 1 du projet et il est invisible. **Arrête-toi.**
  ⚠️ Ce document a longtemps exigé `C:\dev\gemini` ; ce chemin **n'existe plus** et la
  consigne envoyait vers un dossier fantôme. **Aucune RACINE DE DÉPÔT n'est écrite en dur**,
  ici ni ailleurs — c'est délibéré, et `scripts/preflight.py` le vérifie par une propriété
  (*« `import certus` résout-il dans l'arbre courant ? »*), jamais par un chemin.
  🟢 **L'INTERPRÉTEUR SUIT DÉSORMAIS LA MÊME RÈGLE QUE LA RACINE : aucun chemin en dur.**
  ⚠️ *Ce point disait l'inverse jusqu'au 2026-09-08 — « l'interpréteur, lui, EST écrit en
  dur », au motif qu'une commande doit être copiable-collable. L'argument était bon et la
  conclusion mauvaise : le chemin s'est périmé **deux fois**, et la seconde fois le dossier
  avait purement disparu.* Les commandes disent `python` ; ce qui est vérifié est une
  **propriété**, au §2.
  🔑 **Et l'instrument le disait.** `coherence_md.py`, contrôle E, exige que tout interpréteur
  cité **existe** — il signalait donc ces 45 citations mortes à chaque passage, et ce
  signalement a été lu comme du bruit de fond pendant des semaines. *Un contrôle qu'on
  n'instruit pas ne sert à rien ; il coûte même, en habituant à passer outre.*
- 🔴 **Le hook `post-commit` est ARMABLE, pas armé — et la différence se MESURE, elle ne se
  suppose pas.** 👤 a demandé le 2026-08-14 que le push soit armé, et le hook vit depuis dans
  `.githooks/post-commit`, versionné. Mais il ne s'active que si `core.hooksPath` pointe sur
  ce dossier, et **c'est une configuration locale : ni un clone ni une copie de snapshot ne
  l'hérite**.
  📏 Mesuré le 2026-09-05 sur ce snapshot : `core.hooksPath` **non défini**, `.git/hooks/` ne
  contient que des `.sample`, et un commit est resté `[ahead 1]` jusqu'à un `git push`
  explicite. **Deux commandes tranchent, lance-les au lieu de croire ce paragraphe :**
  `git config --get core.hooksPath` et `git status -sb`.
  ⚠️ Ce paragraphe a successivement ordonné *« ne le réactive jamais »* (jusqu'au 2026-08-16)
  puis affirmé *« tout commit pousse »* (jusqu'au 2026-09-05). **Les deux ont décrit un état
  contraire au réel.** Le fait stable n'est pas l'état du hook, c'est que **le dépôt est
  public** : voir §2, point 2.

### Commandes de référence

Toutes depuis la racine du dépôt. ⚠️ *Ce paragraphe prescrivait un chemin d'interpréteur
absolu et interdisait `python` nu ; c'est l'inverse depuis le 2026-09-08 — voir §2.*

🔴 **Une durée sans sa machine ne vaut rien**, et ce tableau en a porté plusieurs. Chacune est
donc datée et attribuée. Le seul critère qui survive à un changement de machine est
`0 failed` ; les durées ne servent qu'à savoir si on lance la commande maintenant ou plus tard.

| But | Commande | Durée mesurée |
|---|---|---|
| Lint | `python -m ruff check .` → `All checks passed!` | ~10 s |
| Tests unitaires | `python -m pytest tests/unit/ -q --no-cov` | **178,88 s** — 2026-09-08, Python 3.14.7 système, cache chaud, `2456 passed, 10 skipped` |
| Tests d'interface | `python -m pytest tests/ui/ -q --no-cov --deselect tests/ui/test_ux_re_stop_when_idle.py` | **> 50 min** — 2026-09-08. 🔴 **Le fichier écarté coûte ~9 min PAR TEST en suite alors qu'il vaut 6,90 s isolé** ; laissé dedans, la passe n'aboutit pas. Lance-le à part |
| Tests du noyau | `python -m pytest tests/oracle/ tests/unit/ -q --no-cov` | 216,69 s le 2026-08-19 sur i5-8250U à cache chaud, 784 s à froid. ⚠️ **Non remesuré depuis** ; le compte de tests collectés est passé de 2 456 à **3 033** entre-temps |
| Run STRAT complet | `python scripts\probe_anchor_noise_pipeline.py full 1.0 42` | ~25 min |
| Idem, seuil injecté | `... probe_anchor_noise_pipeline.py full 1.0 42 0 2.1` | ~25 min |
| Sonde noyau rapide | `python scripts\probe_anchor_noise.py` | ~1 min |
| Banc sur exemples réels | `python scripts\bench_examples.py <module> --auto-yes` | variable |

⚠️ **N'utilise pas `tests/headless/` pour mesurer** : `test_design.py` et `test_strat.py`
remplacent le calcul par un mock.

---

## 5. ⚡ LES 7 ERREURS QUI ANNULENT TON TRAVAIL

Chacune a déjà coûté au moins une session complète sur ce projet.

| # | L'erreur | La conséquence |
|---|---|---|
| 1 | Modifier un dossier et mesurer l'autre | Aucun message d'erreur. Tous tes résultats sont faux. |
| 2 | Écrire une conclusion avant d'avoir la mesure | Détectée à la relecture, ton travail est annulé. |
| 3 | Changer deux choses à la fois | Le résultat bouge, personne ne sait laquelle en est cause. |
| 4 | Croire un chiffre de bruit qui ne varie pas avec le bruit | C'est un artefact. Divise le bruit par 100 et remesure. |
| 5 | Lancer une mesure pendant qu'autre chose tourne | Le banc rend `RESULT=None`, ce qui ressemble à un résultat. |
| 6 | Vérifier une non-régression « aux tests près » | Les tests ne prouvent pas l'identité numérique. Il faut le bit. |
| 7 | Modifier `example/example_strat/JSON-strat-example.json` | Toutes les mesures suivantes deviennent nulles. |

**Si tu ne dois retenir qu'une phrase :**

> **Soit tu colles la sortie de la commande, soit tu écris « je n'ai pas mesuré ».**
> Il n'y a pas de troisième option. Pas de « cela devrait améliorer », pas de « le taux est
> probablement de ».

---

## 6. Les onze interdits absolus

Aucun n'admet d'exception. Si tu crois devoir en violer un, **arrête-toi et demande.**

1. **Jamais `ruff check --fix`.** 📏 **6 918** erreurs « auto-corrigeables » (remesuré le
   2026-08-19 ; la ligne annonçait 6 750), dont beaucoup sont des
   **ré-exports volontaires** : un import qui a l'air inutilisé rend en réalité un symbole
   disponible ailleurs. Corrige à la main, un fichier à la fois.
2. **Jamais agrandir `extend-ignore`** dans `pyproject.toml`. La liste masque déjà 68 règles
   et ne doit que rétrécir. `tests/oracle/test_lint_debt_ratchet.py` le surveille.
3. **Jamais supprimer `reports/`.** Résultats scientifiques de 👤 : classeurs Excel et
   rapports de mesures d'indice réelles. `reports/` n'est **pas** gitignoré ; seuls quatre
   sous-motifs le sont (`reports/exports/`, `release_dossier_*.zip`, `Report_*`,
   `STRAT_observability_*`).
   📏 **Remesuré le 2026-09-08 : 2 141 fichiers, 2 141 suivis par git — il n'en reste AUCUN
   dehors.** (2 154 / 13 la veille, 199 le 2026-08-19.) ⚠️ **Le chiffre précédent était périmé d'un facteur 15**, et il faisait
   paraître le dossier bien plus menacé qu'il ne l'est. Les 13 sont des artefacts de runs du
   3 septembre (`Report_STRAT_*`, `STRAT_observability_*`), tous couverts par `.gitignore` et
   tous **régénérables** : plus rien d'irrécupérable ne traîne ici.
   🔑 **L'interdit tient quand même, et sa raison a changé** : ce n'est plus « des fichiers
   hors git seraient perdus », c'est que **2 141 fichiers versionnés de résultats
   scientifiques n'ont pas à être effacés dans un nettoyage**. 🔴 **Ne recopie aucun de ces
   nombres : recompte-les** (`git ls-files reports | wc -l`).
   📌 Ce qui est réellement hors git aujourd'hui est ailleurs — les PDF sélénium et
   `studies/` — et c'est consigné en tête de [`docs/REPRENDRE_ICI.md`](docs/REPRENDRE_ICI.md).
4. **Ne modifie `example/example_strat/JSON-strat-example.json` que pour DURCIR.**
   Il s'est écarté des valeurs correctes **quatre fois**, toujours dans le sens
   **permissif**, et chaque fois cela a coûté une session de diagnostic. C'est le sens
   qui est interdit, pas l'écriture.
   ✅ **Amendé le 2026-08-12 sur instruction 👤** : *« tous les paramètres doivent être
   dans les JSON, celui du 48 couches et celui du 35 couches — les paramètres
   d'activation des différentes sources d'erreur, ainsi que le mode rate »*. Les deux
   fichiers portent donc désormais **explicitement** les onze réglages du modèle, au
   lieu de dépendre de défauts codés. Un fichier de configuration doit décrire la
   machine sur laquelle il tourne, sinon le run n'est comparable à rien (`DEFAUTS_OUVERTS.md` §24-7).
   ⚠️ Pour essayer autre chose, `scripts\probe_anchor_noise_pipeline.py` injecte les
   paramètres **après coup** — c'est toujours la voie à préférer.

5. **Jamais « corriger » `except A, B:`.** C'est la syntaxe PEP 758, valide depuis
   Python 3.14, utilisée volontairement dans **28** modules (recompté par AST le 2026-09-08 ; la ligne disait 18 le 2026-08-19,
   la ligne disait 14 — et un `grep` ne suffit pas : il faut distinguer le tuple **sans**
   parenthèses de `except (A, B):`, qui est l'ancienne syntaxe et n'a rien à voir). Ajouter des parenthèses change le
   sens du code.
6. **Jamais inverser la convention `n̂ = n − ik`** (k ≥ 0). Avec la convention inverse les
   calculs donnent `R + T > 1` : de l'énergie créée à partir de rien.
7. **Jamais réimplémenter une formule TMM.** Source unique de vérité pour extraire R et T :
   `certus/physics/certus_opt_tmm.py::compute_RT_from_matrix`. Deux bugs de signe ont déjà
   été trouvés dans des réimplémentations, valant **46 et 82 points** de réflectance.
8. **Jamais découper `certus/core/_certus_physics_impl.py`.** Le fichier le dit lui-même :
   `DO NOT SPLIT`. Les noyaux compilés dépendent de la visibilité mutuelle dans un fichier.
9. **Jamais affirmer un résultat non mesuré.** Pas « cela devrait améliorer », pas « le taux
   est probablement de ». Soit tu colles la sortie, soit tu écris « je n'ai pas mesuré ».
10. **Jamais créer de rapport de session à la racine.** 103 fichiers y avaient été accumulés
    puis supprimés : des journaux contradictoires.
11. **Jamais réintroduire de français dans `certus/`.** L'anglais est strictement
    obligatoire pour tout commentaire, docstring ou message de log.
    ⚠️ **Trois catégories restent délibérément en français, et ce n'est pas une
    violation — ne les « corrige » pas** : les mots français utilisés comme
    **données** (`certus_re_helpers.py` — motifs de reconnaissance d'en-têtes
    français), les **clés JSON persistées** (`seuil1`/`seuil2` dans
    `certus_field_state_mixin.py`, qu'on ne peut pas renommer sans casser les
    configurations enregistrées), et les **libellés de widgets vus par
    l'utilisateur** (info-bulles, boutons, phases de progression). L'interdit porte
    sur commentaire / docstring / log — **pas sur la langue de l'interface**, qui
    est une question à poser au propriétaire du projet, pas à trancher seul.
    ⚠️ Pour vérifier, balaye les **282** fichiers avec `tokenize`, pas une liste
    codée en dur : c'est ainsi qu'une annonce de « nettoyage complet » a été faite
    sur la foi de 6 fichiers examinés.

---

## 7. Les sept pièges — chacun a déjà été rencontré

### Piège 1 🟢 — La règle de méthode, payée trois fois

> **Une grandeur de bruit qui ne varie pas avec le bruit est un artefact. Sans exception.**
> Divise le bruit par 100 et remesure. Si le chiffre ne bouge pas, ce n'est pas de la
> physique.

📏 En une journée, le même taux de plantage par couche a valu 28 %, puis 1,3 %, puis 1,47 %
à σ → 0. **Deux fois sur trois ce n'était pas de la physique.** Le balayage de σ coûte
quelques secondes et l'a montré chaque fois.

**Trois corollaires, chacun payé au moins une fois :**

1. **Vérifie sur quelle SOURCE un critère se prononce.** Les défauts les plus coûteux
   étaient de cette forme : le signal *propre* au lieu du signal bruité · la grille
   d'*affichage* au lieu de la grille de balayage · une matrice de *zéros* au lieu de
   l'empilement réel.
2. **Ne confonds jamais deux causes sous une même sentinelle.** Trois modes de défaillance
   rendaient la même valeur ; le diagnostic est devenu possible en **une** mesure une fois
   séparés.
3. **Une signature qui ne varie ni avec la profondeur, ni avec l'amplitude, ni avec la
   graine désigne l'algorithme, pas le phénomène.**

### Piège 2 — `params` n'est pas toujours un dictionnaire

Sur certains chemins c'est un objet pydantic (`StratParamsDTO`).
`params.get("cle")` ✅ · `params["cle"] = v` ✅ · **`params.setdefault(...)` ❌ `AttributeError`**.
Ce bug a tué le pipeline entier en 13 secondes, résultat vide, aucune explication. Écris :

```python
if params.get("cle") is None:
    params["cle"] = valeur
```

### Piège 3 — Importer un paquet déclenche son `__init__.py`

Importer `certus_physics.quoi_que_ce_soit` exécute d'abord `certus_physics/__init__.py`,
qui importe la moitié du projet. Depuis un module de `certus/physics/`, c'est un **import
circulaire**. Vérifier les imports du module ne suffit pas : vérifie ceux de son **paquet**.
Pour une simple annotation, utilise `if TYPE_CHECKING:`.

⚠️ Corollaire pour les scripts : `from certus.physics.X import Y` échoue en circulaire ;
passe par la façade `from certus_physics import Y`.

### Piège 4 — Les tests partagent des caches de classe

`SplineBasisCache._cache` et consorts. Symptôme : ton test passe seul, un autre échoue plus
tard. Sauvegarde et restaure le cache dans une fixture `autouse`.

### Piège 5 — Un test qui échoue n'a pas forcément tort… mais parfois si

**Cinq tests** vérifiaient un comportement **faux** et ont dû être retournés : qu'un
matériau introuvable renvoie de l'air (n=1) · que `to_complex()` produise `n + ik` · un test
préservant les variables d'env qu'il assérait absentes · une classe `CertusHubApp` qui n'a
jamais existé · un garde-fou `nogil` visant un kernel renommé.

Ne « répare » pas un test en changeant le nombre attendu. Comprends d'abord. Puis dis
laquelle des deux situations tu as trouvée — code faux, ou test faux — et si c'est le test,
explique pourquoi dans son docstring. Si tu ne sais pas trancher, **arrête-toi et demande.**

### Piège 6 — La Phase A ne dit rien de ce qu'elle fait

Deux systèmes de journalisation : l'un écrit sur la console, l'autre dans une file destinée
à l'interface graphique, que personne ne vide en ligne de commande. **Un silence ne prouve
rien.** Pour savoir ce que la Phase A a fait, lis le `reports/STRAT_observability_*.json` le
plus récent.

### Piège 7 — Le premier calcul est lent, et ce n'est pas une mesure

Numba compile au premier appel : +30 s sans que rien ne soit anormal. Chauffe une fois, puis
mesure. **Et donne la machine entière au run que tu mesures** — voir **règle 5 du §11**.
⚠️ *Ce renvoi disait « §29 », qui est le travail à venir sur le modèle physique et ne porte
aucune règle numérotée. Le contrôleur avait validé que §29 existe — il ne vérifie pas que la
section contienne ce qu'on lui prête.*

---

## 8. Ce qu'il ne faut PAS faire

- **Chercher un coût prédictif par `sᵀΣs`** — réfuté : ni les sensibilités spectrales
  (+0,589 contre +0,590) ni la covariance (+0,643) n'apportent rien.
- **Réparer l'estimation du coût en nanomètres de la Phase A.** 👤 *« En partie B on se
  branle de l'erreur d'épaisseur, seul l'écart spectral final compte. »*
- **Rendre les « points tournants virtuels » utilisables comme ancres POEM.** Un point
  tournant virtuel est une extrapolation — **la machine ne l'a pas mesuré**.
- **Rétablir un front de Pareto** — `P(conforme)` est un scalaire.
- **Une recherche en faisceau avec *rollout*** — générer largement puis départager par la
  statistique suffit, à condition que la génération vise la couverture.
- **Toucher au cap de 10 λ par bloc** — traité par la séparation spectrale.
- **Activer SYM sans recalibrer `sym_weight`.**
- **Conclure d'un écart d'épaisseur sous 0,05 nm** (moins d'un atome), **d'un écart de λ sous
  le pas de grille**, ou **proposer une λ hors de la grille de balayage**.
- **Réintroduire un mode dégradé SANS le dire.** ⚠️ **L'interdiction du mode FAST est
  CADUQUE — assouplie le 2026-08-16.** Elle disait *« interdit le mode fast »* (👤, 2026-08-05)
  et **toutes les campagnes depuis le 14 août tournent en fast**. Une règle violée en
  permanence ne protège plus rien : elle apprend seulement à ignorer les règles.
  **Ce qui la remplace, et qui est le vrai contenu :**
  | ce que FAST peut mesurer | ce qu'il ne peut PAS |
  |---|---|
  | le **SEEL**, et le criblage d'architectures de blocs | 🔴 le **taux de plantage** : le criblage est à 10 tirages, donc quantifié à **10 %**. Un « 0,0 % » lu sous FAST signifie « sous 10 % » |
  | une comparaison **à protocole fixé**, dans une même campagne | 🔴 un **minimum sur beaucoup de candidats** : c'est la malédiction du vainqueur, elle a coûté **+12,9 %** le 15/08 |
  🔑 **Un SEEL retenu sous FAST se rejoue en PREMIUM avant publication.** C'est la règle qui
  a de la valeur ; l'interdiction n'en avait plus.

  🟢 **ET IL Y A UN QUATRIÈME MODE DEPUIS LE 2026-08-18 : `extreme`.** 👤 : *« j'aime bien l'idée
  du mode spécifique si l'utilisateur a tout son temps »*. Il élargit ce qui est **généré et
  retenu** (`dp_top_k` 100, `mining_candidates_limit` 12 000, `phase_a_keep_limit` 200,
  `top_k_parents` 80) et **laisse la profondeur d'évaluation
  identique à `deep`** — un taux de plantage produit en `extreme` reste donc comparable à un run
  `deep`. Coût ≈ **5× deep**, mesuré 157 min sur 75 couches.
  🔴 **ET IL N'A AUCUNE JUSTIFICATION MESURÉE — contrôle rendu le 2026-08-18.** Sur le
  random75 ×2 à 1 nm : `fast` → **0** déposable · **`deep` seul → 277**, SEEL 0,625 ·
  `extreme` → 254, SEEL 0,629. **`deep` suffit, et fait marginalement mieux.** Les deux écarts
  sont dans le bruit statistique, ce qui est justement le verdict : l'élargissement n'apporte
  **rien de mesurable** et coûte plus cher. Ce qui a débloqué le ×2 est le passage de `fast` à
  `deep`, un mode qui existait déjà.
  🔑 **Le fichier prêt à lancer utilise donc `deep`** :
  `example/example_strat/JSON-strat-random75-x2-fabricable.json`.
  🟢 **ET LE CONTRÔLE QUI MANQUAIT EST TOMBÉ LE 2026-08-20 — sa justification ne tient pas.**
  Le mode a été bâti sur *« standard (`fast`) → 0 déposable, élargi (`deep` + profil) → 254 »* :
  **deux choses changées à la fois**, l'erreur n° 3 du §5. 📏 Contrôle sur `r75x2` @ 1 nm,
  graine 42 — le cas même qui l'a motivé :
  `deep` **seul** → **277 déposables**, SEEL **0,6248** · `deep` **+ élargi** → 254, SEEL 0,6292.
  **Élargir perd 8 % des déposables et ne gagne rien** (0,27 σ), pour ~5× le coût d'un `deep`.
  🔑 **C'est le MODE qui a tout fait, pas l'élargissement.** La docstring du mode disait
  l'inverse et a été corrigée ; `pages/CERTUS_STRAT.html` le disait déjà juste — **le code
  contredisait la page.** 📌 [`CHANTIER_PREDICTIBILITE.md`](docs/CHANTIER_PREDICTIBILITE.md)
  §4quater.
  🔴 **MATRICE `extreme` ARRÊTÉE LE 2026-08-19, sur décision de 👤 après un point d'étape :**
  cinq configurations testées (×2, 35c, 48c, ×0,5, 99c), **zéro amélioration mesurable sur
  aucune** — y compris les deux configurations barrières (`deep` trouve 0 déposable) où le mode
  aurait été le plus utile. Le mode reste dans le dépôt, **sans qu'on lui attribue rien**.
  📌 [`CHANTIER_PREDICTIBILITE.md`](docs/CHANTIER_PREDICTIBILITE.md) §4quater-bis.
  🔒 Les trois modes existants sont **inchangés au bit** — contrôlé paramètre par paramètre, et
  le défaut reste `premium`.
  ⚠️ Défaut d'implantation qui subsiste : `fast_auto_blocks` est posé et **journalisé**
  (`certus_strat_ui_worker.py:375`) alors qu'**aucun code ne le lit**. Le journal annonce donc
  un effet qui n'existe pas. Le rebrancher ou le supprimer, mais ne pas le laisser dans le log.
- **Citer les repères « 0,4 nm / 0,3 nm »** — absents de la thèse Zideluns.
- **Établir une règle sur un seul empilement structuré.** Une règle n'est acquise que si elle survit sur un empilement **sans structure** — ni cavité, ni miroir, ni périodicité. C'est ce test qui a réfuté « le témoin vieillit et meurt » et qui laisse `S(p−1)` **non validée**.
- **Raffiner la grille d'échantillonnage sans corriger le seuil** — voir [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.2.
- **Modéliser σ(T), la grenaille ou le bruit multiplicatif** — voir §17.

---

## 9. La boucle de travail

Pour **chaque** action, dans cet ordre, sans en sauter :

1. **Lis l'action dans son dossier** — [`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md) pour le
   chantier vivant **du calcul**, [`UX_PLAN.md`](docs/UX_PLAN.md)
   pour celui **de l'interface**, [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) pour le
   modèle physique, [`CHANTIERS_OUVERTS.md`](docs/CHANTIERS_OUVERTS.md) et
   [`RESERVE_A25_A27.md`](docs/RESERVE_A25_A27.md) pour le reste. Si quelque chose est ambigu,
   **arrête-toi et demande.** Un plan ambigu est un défaut du plan, pas une invitation à
   inventer. ⚠️ *Ce point renvoyait à « §17 », qui est la fiche de la machine réelle et n'a
   jamais porté d'action.*
2. **Fais la modification la plus petite possible.** Une seule chose à la fois : si tu
   changes deux choses et que le résultat bouge, personne ne saura laquelle en est cause.
3. **Tests** : `python -m pytest tests/oracle/ tests/unit/ -q --no-cov`. Un échec ⇒ n'avance pas.
4. **Lint** : `python -m ruff check .` doit dire exactement `All checks passed!`
5. **Non-régression bit-à-bit** si tu as ajouté un paramètre — voir la règle d'or ci-dessous.
6. **Mesure** avec la commande exacte, machine libre.
7. **Committe**, puis colle le hash dans ta réponse.

### 🔴 La règle d'or

> **Tout nouveau paramètre doit être inactif par défaut, et le chemin inactif doit donner
> exactement le même résultat qu'avant — au dernier bit.**

Et **pas « aux tests près »** : les tests ne couvrent pas assez de combinaisons pour prouver
une identité numérique. La méthode qui fait foi : capturer une empreinte `float.hex()` du
chemin par défaut sur une large batterie de configurations **avant** la modification, la
recapturer après, exiger **zéro** différence. La correction affine de §15 a été validée ainsi
sur **75 818 configurations**.

### 🟢 Le banc EST déterministe — mais la RECOMPILATION peut décaler les derniers chiffres

📏 **Mesuré le 2026-08-10**, campagne de 10 runs. Quatre runs de configuration neutre, lancés
à la suite, rendent **exactement le même bit** :

```
A12.1  0.002948627371309867
A6.1   0.002948627371309867
A6.2   0.002948627371309867
A6.3   0.002948627371309867
```

⚠️ **Une version antérieure de ce paragraphe affirmait le contraire** — que `parallel=True` +
`fastmath=True` rendaient le banc « non bit-reproductible par construction », avec une gigue
irréductible de 3e-11. **C'était faux, et fondé sur deux points seulement.** L'ordonnancement
des threads ne fait rien varier.

**La seule valeur différente**, `0.002948627371226749` (écart 2,8e-11), est celle du premier
run lancé **après la montée en Python 3.14.7** — donc le seul avec un cache numba **froid**.

> **La règle : à état compilé identique, le banc rend le même bit. C'est la RECOMPILATION qui
> est le facteur de risque, pas l'exécution.**

### 🔴 TRANCHÉ LE 2026-08-10 — la recompilation décale les bits, de façon reproductible

Mesure B0 : cache numba **vidé**, code **strictement inchangé**, configuration neutre.

```
cache chaud, 4 runs             0.002948627371309867
cache FROID, etape 2 (2026-08-09)  0.002948627371226749
cache FROID, B0    (2026-08-10)    0.002948627371226749   <- identique au precedent
```

**Une recompilation décale de 2,819e-11, et deux caches froids indépendants donnent
exactement le même chiffre.** Ce n'est pas du bruit : c'est un second état, reproductible.

**Les trois conséquences, et elles sont définitives :**

1. 🔴 **Le « bit-identique » de C1 est INATTEIGNABLE via le banc, précisément là où on en a
   besoin.** Ajouter un paramètre à un noyau numba change sa signature, donc force une
   recompilation, donc déplace le chiffre. **N'exige jamais l'égalité exacte d'un `RESULT` de
   part et d'autre d'un ajout de paramètre.**
2. ✅ **Le constat §24-1 de `DEFAUTS_OUVERTS.md` est définitivement innocenté.** L'écart de 2,5e-11 que j'avais pris
   pour une violation de la règle d'or était T5 changeant la signature du noyau. Retiré par
   prudence hier, retiré par **preuve** aujourd'hui.
3. **A5 doit comparer à état compilé constant** — ou porter cette tolérance explicitement.
   Forcer le mono-thread ne sert à rien : l'ordonnancement n'est pas la cause.

---

## 10. Quand s'arrêter et demander

- une instruction est ambiguë ;
- un test échoue et tu ne sais pas si c'est le test ou le code qui a tort ;
- une mesure diffère nettement de ce qui était annoncé ;
- tu es tenté de violer un interdit ;
- tu envisages de modifier plus de trois fichiers pour une seule action ;
- **tu obtiens un résultat meilleur que prévu** — c'est très souvent le signe qu'on mesure
  la mauvaise chose.

**S'arrêter n'est jamais un échec. Inventer, si.**

---

## 11. Règles de tenue de ce document

1. **Toute affirmation chiffrée porte sa commande et sa sortie**, collée sans retouche.
2. **Si tu n'as pas fait, dis-le.** Une ligne « je n'ai pas réussi, voici l'erreur » vaut
   beaucoup plus qu'une invention : celui qui te relit la détectera en essayant de la
   reproduire, et perdra confiance dans **tout** le reste.
3. **« Ce dont je ne suis pas sûr : rien » est presque toujours faux.**
4. 🔴 **CETTE RÈGLE ÉTAIT LA SUPPRESSION DU §8, RECOPIÉE ICI — ET ELLE Y AVAIT SURVÉCU.**
   Elle disait *« ne conclus jamais d'une mesure sur un autre composant que le 48 couches »*,
   alors que le §8 la **barre explicitement** depuis le 2026-08-16 : le projet a **quatre**
   composants d'essai, et le random75 existe précisément pour conclure en **général**.
   **Ce qui la remplace, et qui est la vraie règle** : une règle n'est établie que si elle
   survit sur un empilement **sans structure** — ni cavité, ni miroir, ni périodicité.
   ⚠️ *Trouvée le 2026-08-19 en relisant ligne à ligne. Aucun outil ne pouvait la voir : les
   deux formulations sont dans des sections différentes et ne partagent aucun nombre.*
5. **Un run mesuré doit avoir la machine pour lui seul.** Un banc lancé pendant qu'autre
   chose tourne rend `RESULT=None` au bout de 1800 s, ce qui ressemble à un résultat. C'est
   arrivé le 2026-08-08.
6. **Vérifie la non-régression au BIT, pas « aux tests près »** — voir §9.
7. **Ce document ne grossit pas indéfiniment.** Ce qui est fait en sort. Ce qui se contredit
   en sort. `git log` garde tout.

---

## 12. Protocole de re-vérification — comment auditer le travail d'un autre agent

**Un rapport est une déclaration, pas une preuve.** Ce protocole consiste à essayer de
**casser** chaque déclaration, pas à la confirmer. Appliqué deux fois, il a trouvé quatre
affirmations fausses la première fois et neuf la seconde (`DEFAUTS_OUVERTS.md`) — il fonctionne.

⚠️ **Il a ses limites, et il faut les dire.** Les deux passes ont vérifié des **diffs, du
code et des artefacts**. Aucune des deux n'a relancé une mesure au banc. Une déclaration
chiffrée n'est donc réfutée que lorsqu'un **artefact la contredit** ; celles qui n'ont
produit aucun artefact ne sont ni confirmées ni réfutées — elles sont **non vérifiées**, ce
qui est un troisième état qu'il ne faut pas confondre avec « tient ».

### Le repère git

L'état du dépôt avant l'intervention de la session précédente porte l'étiquette
**`depart-gemini`** (`f816767`, 2026-08-07). Elle est vivante — revérifiée le 2026-08-19,
**240** commits depuis. ⚠️ Ce compte croît chaque jour : ne le cite pas, recompte-le.
⚠️ Et `git rev-parse depart-gemini` rend le SHA de l'**objet-tag**, pas du commit — c'est
`git log -1 depart-gemini` qui donne `f816767`.

```bat
git log --oneline --stat depart-gemini..HEAD
```

**Ne la supprime pas et ne la déplace pas.** Si `git log depart-gemini..HEAD` répond
`unknown revision`, arrête-toi et signale-le : sans ce repère, personne ne peut plus séparer
le travail d'une session de ce qui existait avant.

Pour remesurer l'état de départ sans perdre l'état courant :

```bat
git worktree add ../certus-baseline depart-gemini
:: ... mesures ...
git worktree remove ../certus-baseline
```

### Les trois questions, dans cet ordre

1. **Le diff correspond-il à ce qui est déclaré ?** (git ne ment pas)
2. **La mesure citée se reproduit-elle ?** (relancer la commande)
3. **La conclusion suit-elle de la mesure ?** ← **c'est là que ça casse le plus souvent**

Une déclaration qui échoue à l'une des trois est **annulée**, pas retouchée. Reviens en
arrière, puis refais : un correctif posé sur une base non vérifiée hérite de son incertitude.

| Ce que tu trouves | Ce que ça veut dire |
|---|---|
| Un commit non déclaré | Suspect par défaut : lis son diff en entier avant toute autre chose. |
| Une déclaration sans commit | Le travail n'a pas été committé, ou n'a pas eu lieu. |
| Un commit qui touche plus de fichiers que déclaré | Le périmètre a débordé. Regarde ce qui a été emporté. |
| Un commit sur `pyproject.toml` | Vérifie **immédiatement** que `extend-ignore` n'a fait que rétrécir. |
| Un commit sur `JSON-strat-example.json` | **Toutes les mesures postérieures sont nulles** jusqu'à preuve du contraire. |

### Les cinq contrôles qui attrapent l'essentiel

1. **Tout nouveau paramètre est-il vraiment inerte par défaut ?** Égalité **exacte**, pas
   `allclose` — mais **sur l'empreinte du noyau en mono-thread (A5), jamais sur le `RESULT`
   du banc**, qui a ~3e-11 de gigue irréductible (§9). 🔴 **Une version antérieure de ce
   contrôle disait « au-delà de 1e-12, ce n'est pas numba » et faisait comparer des `RESULT`
   de banc. C'est ainsi que le constat §24-1 de `DEFAUTS_OUVERTS.md` a été écrit puis retiré : il accusait le code
   d'un bruit de sommation parallèle.** Le seul chiffre exploitable ici est celui du harnais.
2. **Les tests ajoutés échouent-ils sur le code d'avant ?** Copie-les dans le worktree
   baseline et lance-les. Ils **doivent** échouer. C'est le contrôle le plus rentable de la
   liste.
3. **Les grandeurs de bruit varient-elles avec le bruit ?** Divise σ par 100 : le chiffre
   doit s'effondrer.
4. **Chaque règle rejette-t-elle effectivement quelque chose ?** **Compte les rejets, ne lis
   pas le code.** Un filtre inerte ne produit aucune erreur — il produit un résultat
   plausible. C'est ainsi qu'une règle de proximité recevant une matrice de zéros n'a rien
   interdit sur 51 candidates × 48 couches, en silence.
5. **Les conclusions dépassent-elles les mesures ?** Attrape en particulier : une conclusion
   physique tirée d'un empilement à 8 couches · une **attribution causale quand deux choses
   ont changé en même temps** · un résultat **meilleur que prévu** présenté comme un succès.

### Être juste dans le jugement

- **Un travail non fait mais déclaré comme non fait n'est pas une faute.** C'est ce qu'on
  demande. Une ligne « je n'ai pas réussi, voici l'erreur » vaut mieux qu'un contournement
  silencieux.
- **Un arrêt sur ambiguïté n'est pas une faute.** Le document ambigu est en tort.
- Une seule chose est réellement disqualifiante : **une affirmation chiffrée qui ne se
  reproduit pas.** Si tu en trouves une, cesse de faire confiance au reste et revérifie tout
  depuis git.

---

# PARTIE II — LE SAVOIR

## 13. Ce qu'est CERTUS

Suite scientifique de **couches minces optiques** : détermination d'indice, design
d'empilements, stratégie de dépôt. Application **PyQt6** + noyau **NumPy/SciPy/Numba**.

- `certus-optical-suite 26.05.0` — licence propriétaire
- **Python 3.14.7** — 👤 la seule version retenue à partir du 2026-08-09. Le minimum
  syntaxique reste 3.14 (PEP 758 : `except A, B:` sans parenthèses — **le compte est à
  l'interdit n° 5, et nulle part ailleurs**). ⚠️ *Cette ligne portait « 14 modules », une
  COPIE du chiffre de l'interdit ; j'ai corrigé l'un à 18 le 2026-08-19 et pas l'autre. C'est
  la règle « un fait, un seul endroit » violée en direct, une heure après l'avoir invoquée.*
  ⚠️ **Après un changement de version, les caches numba sont invalidés** : le premier appel
  est lent (Piège 7) **et les derniers chiffres d'un `RESULT` peuvent bouger**. Les repères
  de `REPERES_MESURES.md` ont été mesurés sous **3.14.6**. Toute mesure rapportée doit porter sa version
  d'interpréteur, sinon un écart de version sera attribué au code.
- Cible principale Windows, build gelé PyInstaller
- 📏 **Mesuré le 2026-08-19**, et les trois chiffres qui figuraient ici étaient faux :
  🔴 **CE BLOC NE PORTE PLUS DE NOMBRES, ET C'EST DÉLIBÉRÉ.** Il en a porté quatre séries
  successives, **toutes fausses à leur tour** — non par négligence, mais parce qu'un compte de
  lignes ou de tests se périme dès qu'on travaille. Un document qui imprime un chiffre puis
  écrit « recompte-les » invite à recopier le chiffre. **Voici donc les commandes, pas les
  valeurs** :

```bat
git ls-files "certus/*.py" "certus/**/*.py" | xargs wc -l
git ls-files "tests/**/test_*.py" | wc -l
python -m pytest tests/oracle/ tests/unit/ -q --no-cov --collect-only
```

  📌 **Le seul fait stable est l'ordre de grandeur** : un noyau de l'ordre de **170 000 lignes**,
  et une suite de tests qui fait **environ 40 % de sa taille**. C'est cela qui dit à quoi on a
  affaire ; le chiffre exact ne dit rien de plus et se périme en une journée.
  ⚠️ L'ancien « 183 600 de source » ne correspondait à **aucun périmètre** : ni `certus/`
  seul (163 485), ni avec la racine (171 600), ni en ajoutant `scripts/` (193 287). Et le
  « ~2 300 tests » était faux par inclusion. 🔴 **Ces nombres se périment ; recompte-les**

### Points d'entrée (racine)

| Fichier | Rôle |
|---------|------|
| `CERTUS_HUB.py` | Lanceur unifié — **doit rester une couche de composition pure** |
| `CERTUS_DESIGN.py` | Design d'empilements |
| `CERTUS_STRAT.py` | Stratégie de dépôt |
| `CERTUS_RE.py` | Rétro-ingénierie |
| `CERTUS_INDEX.py` / `CERTUS_INDEX_SPLINE.py` | Détermination d'indice |
| `CERTUS_METAL_SINGLE.py` / `CERTUS_METAL_BILAYER.py` | Métaux (mono/bicouche) |
| `CERTUS_FIELD.py` | Champ électrique |

### Architecture

```
certus/                          <- remesure le 2026-08-19 ; les 8 comptes de FICHIERS
├── physics/   26 fich.  13 734 l.     etaient exacts, deux comptes de LIGNES avaient
├── core/      40 fich.  23 874 l.     derive : physics +8,1 %, core +15,8 %
├── domain/    12 fich.   1 017 l.
├── spline/    31 fich.  31 067 l.
├── workers/   27 fich.  12 050 l.
├── utils/     34 fich.  17 955 l.
├── metal/      3 fich.   2 529 l.
└── ui/       109 fich.  61 259 l.
```

⚠️ **Ces lignes se périment à chaque commit** — ne les cite pas, elles servent à donner
l'ordre de grandeur relatif des paquets. Le total mesuré est plus haut, dans la fiche.

**Frontières à respecter**

- `certus.core`, `certus.physics`, `certus.domain` n'importent **jamais** PyQt6, QWidget, ni
  `certus.ui`.
- `certus.ui` et `CERTUS_HUB.py` ne contiennent **aucun algorithme de calcul**.
- Thématisation : toujours `apply_certus_theme()` et les constantes `CertusTheme`. Jamais de
  hex codé en dur.

**Violations connues — ne pas aggraver**

| Inversion | Nb | Détail |
|-----------|-----|--------|
| `utils` → `ui` | **11** | dont 3 au niveau module (`certus/utils/certus_curve_smoother.py:29-30`, `certus/utils/certus_export.py:13`) : importer ces modules charge PyQt6. ⚠️ *annonçait 12* |
| `core` → `workers` | **10** | DTO de workers importés par le noyau. ✅ exact |
| `physics` → `core` | **23** | 🔴 *la ligne disait « `physics` ↔ `core` \| 29/22 » : les deux chiffres étaient faux ET l'ordre ambigu. Séparés et remesurés par AST le 2026-08-19* |
| `core` → `physics` | **29** | l'autre sens du cycle |

**Règle : ne jamais créer un nouvel import d'une couche basse vers une couche haute.** Si tu
en as besoin, c'est que le symbole doit descendre dans `domain/` ou `core/`.

**Packages implicites.** Seul `certus/domain/` a des `__init__.py` ; les 7 autres
sous-paquets fonctionnent en PEP 420. `pyproject.toml` déclare `packages = ["certus"]`, donc
un `pip install` ne récupérerait aucun sous-module : le projet n'est utilisable qu'en source.

### Pièges de fichiers

- 🔴 **`reports/` contient les résultats scientifiques de 👤** — classeurs Excel et rapports
  HTML de déterminations d'indice. 🔴 **Le compte est à l'interdit 3, et nulle part ailleurs.**
  ⚠️ *Cette ligne en portait une COPIE — « 199 fichiers sur 2 266 hors de git » — restée au
  2026-08-19 pendant que l'interdit 3 était remesuré deux fois. Les deux chiffres se
  contredisaient dans le même document, ce qui est exactement la faute que le §1 interdit.*
  Ne le supprime **jamais** dans un « nettoyage ».
- Les 3 fichiers `certus_*.py` restants à la racine (`certus_curve_smoother`,
  `certus_spectral_preproc`, `certus_substrate_index`) sont des **façades légitimes** de
  ré-export. Des tests font `import certus_spectral_preproc`. Ne les supprime pas.
- `CERTUS_METAL_SINGLE.py` et `CERTUS_METAL_BILAYER.py` sont restés à la racine alors que
  `certus/metal/` existe : migration à moitié faite.
- Le `.coverage` date du 13 juillet et pointe vers un autre snapshot — ne pas s'y fier.

---

## 14. Vocabulaire

| Terme | Sens |
|---|---|
| **le juge de paix** | Le dichroïque 48 couches, `example/example_strat/JSON-strat-example.json`, passe-court, front à ~545 nm. C'est le **repère de référence**, celui sur lequel le monitoring marche le mieux. ⚠️ *Cette ligne disait « le seul exemple valable » — troisième survivant de la règle que le §8 a **barrée** le 2026-08-16. Le projet a **quatre** composants d'essai, et le random75 existe pour conclure en général.* |
| **λ de contrôle** | Longueur d'onde à laquelle la machine surveille le dépôt d'une couche. |
| **bloc** | Groupe de couches consécutives surveillées à la **même** λ. |
| **point tournant** *(turning point)* | 🔴 L'instant où **l'admittance du système entier devient réelle**, donc où `T` passe par un extremum pendant la croissance. Forme fermée : `tan 2δ = R/Q`. **Ce n'est PAS « la couche atteint 1 QWOT »** — voir la ligne suivante, c'est l'erreur la plus coûteuse du projet. |
| **QWOT** | L'épaisseur optique d'**une couche seule**, en quarts d'onde, `m = 4nd/λ`. 🔴 **QWOT ≠ point tournant.** La *période* entre deux points tournants vaut bien un quart d'onde à λ_mon, mais le *départ* est décalé d'une phase `½·arctan(R/Q)` fixée par **l'empilement du dessous**. Les deux ne coïncident que sur **la couche 1 d'un substrat nu** (où `R = 0` exactement, mesuré) ou sur un empilement **entièrement QWOT à λ_mon**. 📏 Se tromper coûte un **facteur 59** : sur le random75 ×0,5, le comptage naïf annonce 59 couches « sans point d'arrêt », le comptage exact en trouve **1**. 🔒 **Lis [`docs/QWOT_ET_TURNING_POINT.md`](docs/QWOT_ET_TURNING_POINT.md) avant d'écrire sur ce sujet** ; `scripts/check_claude_md.py` (contrôle E) refuse mécaniquement toute phrase qui les assimile. |
| **POEM** | Méthode d'arrêt visant un pourcentage de l'amplitude entre les deux derniers points tournants, au lieu d'un niveau absolu. |
| **plantage** | Le dépôt **ne se termine pas** : la machine attend un niveau qui ne vient jamais, ou compte le mauvais nombre de points tournants. Pas une perte de précision — un run perdu. |
| **rendement** | Pourcentage de dépôts qui se terminent. Objectif du physicien : **95 %**. |
| **Phase A** | Choix de la meilleure λ pour chaque couche, une couche à la fois. |
| **Phase B** | Regroupement en blocs et test statistique Monte-Carlo des stratégies. |

---

## 15. Le cadre — trois phrases du physicien qui gouvernent tout

> 👤 **La chaîne canonique.** *« 1. On simule un dépôt et la mesure de transmission bruitée.
> 2. On utilise le POEM comme méthode d'arrêt. 3. On teste statistiquement tout un ensemble
> de stratégies prometteuses. 4. On en déduit la meilleure stratégie. »*

> 👤 **Le juge.** *« Le juge de paix c'est toujours l'étude stochastique et statistique. Si
> 95 % des dépôts fonctionnent, c'est gagné. »*

> 👤 **L'objectif.** *« Le plus important est la cible spectrale respectée. »*

Cela définit **une grandeur unique** : la meilleure stratégie maximise `P(le filtre sorti
est conforme)`. Un dépôt qui plante et un filtre hors spec sont **le même échec**.
Conséquence : **la DP n'a plus à bien classer, elle doit bien couvrir** — le tri est fait
par la statistique.

---

## 16. 🔴 Conventions physiques — à ne pas casser

### Convention Macleod `n̂ = n − ik` (k ≥ 0)

Partout. Avec `n̂ = n + ik`, `compute_RT_from_matrix` produit `R + T > 1`.

### Chemins TMM — lequel utiliser

| Fonction | État | Usage |
|----------|------|-------|
| `compute_TMM_single_point_k0` / `_exact` | ✅ | multicouche |
| `compute_RT_from_matrix` | ✅ | extraction R/T — **toujours celle-ci** |
| `calculate_transmission_single` | ✅ | monocouche, **inclut la face arrière** (Standard Mode) |
| `calculate_reflection_array` → `_single` | ✅ | ajustement d'indice, chemin de production |
| `calculate_RT_single_layer_single` | ✅ | corrigé le 2026-08-02 (`phi_i = -k·n_film_imag·d`), écart ramené de 46 points à 4,4e-16 |

`calculate_transmission_single` inclut délibérément le terme de face arrière
(`DO NOT REMOVE THE BACKSIDE TERM`) : ses résultats diffèrent légitimement d'un TMM nu.

### Marqueurs `─── LOCKED ───`

Signalent du code validé par tests. Ne pas modifier sans relancer les tests cités.
⚠️ **Un marqueur LOCKED n'est pas une preuve** : le bug de signe monocouche portait
`LOCKED` **et** `Macleod convention (+1j, n-ik)` alors que la fonction était fausse.

### 🟢 L'oracle TMM — sers-t'en

`tests/oracle/tmm_reference.py` est une référence TMM **indépendante**, sans une ligne
partagée avec `certus.physics`, écrite depuis Macleod chap. 2 en matrices 2×2 explicites.
Lente et relisible face au livre — c'est volontaire.

```python
import sys; sys.path.insert(0, "tests/oracle")
from tmm_reference import rt_stack, rt_stack_oblique, r_single_layer_front, n_hat
```

**Ce qu'elle a démasqué** : deux bugs de convention de signe, à 46 et **82 points** de
réflectance, tous deux exacts à k=0 donc invisibles aux tests existants.

| Chemin validé | Écart à l'oracle |
|--------|------------------|
| `compute_TMM_generic` | 3,3e-16 |
| `calculate_RT_single_layer_single` | 4,4e-16 |
| `calculate_reflection_infinite_substrate_single` | 4,4e-16 |
| `_oblique_stack_rt_single` (5 angles × s/p × 3 k) | 7,8e-16 |

**Règle : avant de toucher au moindre calcul optique, lance `pytest tests/oracle/`.**
📏 **563 passed en 89,72 s** (2026-08-17, i5-8250U, cache chaud). ⚠️ Cette ligne annonçait
*« 237 tests, 2 s »* — **faux, et d'un facteur 2,4 sur le compte** : la suite oracle a plus
que doublé depuis. Et quand tu corriges un bug, **vérifie que le test que tu ajoutes échoue
sur le code d'avant correctif** — sinon il ne prouve rien.

---

## 17. 👤 La machine réelle — spécifications obtenues le 2026-08-08

Ces nombres gouvernent le modèle de monitoring.

| Grandeur | Valeur | Conséquence |
|---|---|---|
| Rotation du plateau | **240 tr/min** | période 250 ms |
| Plateau ~1 m, témoin 20 mm au bord | | vitesse tangentielle **12,6 m/s**, **transit 1,6 ms** |
| Positions par tour | **3** : témoin, noir, vide | `T = (S − D)/(V − D)`, auto-référencé à 4 Hz |
| Vitesse de dépôt | ~0,5 nm/s | |
| **Cadence** | **4 Hz**, une lecture témoin par tour | **un échantillon tous les 0,125 nm** |
| Bruit de lecture | ±0,05 point, largeur totale **0,10** | 👤 le tirage du modèle est **correct**, **à la résolution nominale de 2 nm** |
| **Résolution du monochromateur** | **2 nm** par défaut ; l'utilisateur peut choisir 5 / 1 / 0,5 nm | **figée pour tout le dépôt**. Change le bruit **et** déforme le signal — voir [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.7 |
| Le « 5 σ » du seuil | 👤 *« bien au-dessus du bruit »* | **pas une exigence physique** |

**La rotation moyenne le dépôt** — c'est sa raison d'être — **mais elle échantillonne la
mesure** : chaque point rapporté est un passage, rien ne se moyenne.

**Écart au modèle, mesuré :**

| | Machine | Modèle actuel | Facteur |
|---|---|---|---|
| Pas spatial | 0,125 nm | 4,76 nm (`NPTS=64` sur `3×d_nom`) | **38× trop grossier** |
| Points par couche de 100 nm | 800 | 21 | |
| Historique, par couche relue | 800 | 16 (`NPTS_PREV`) | **50× trop grossier** |

🔴 **Ne pas modéliser σ(T), la grenaille, ni le bruit multiplicatif.** Le modèle actuel — un
tirage borné à ±0,05 point, un seul nombre mesuré, aucun paramètre libre — est défendable. Y
ajouter une structure non mesurée remplacerait une constante mesurée par des paramètres
inventés. 👤 Tranché le 2026-08-08.

---

## 18. 🔒 LE MODÈLE DE LA CHAÎNE DE LECTURE — FIGÉ, NE PAS ROUVRIR

**L'OMS 5100 est breveté et son fonctionnement interne est opaque.** On ne saura pas
comment il filtre, ni comment il déclenche. Continuer à poser des questions sur ses entrailles
ne produirait que des paramètres libres, et un modèle à paramètres libres ne prouve rien.

👤 **Décision du 2026-08-08 : on pose une hypothèse raisonnable, on l'écrit, et on s'y
tient.** Ce qui suit est un **postulat de modélisation**, pas une spécification constructeur.
Il est **figé**. On ne le rouvre que si une mesure le contredit — pas parce qu'une autre
hypothèse semblerait plus élégante.

| # | Postulat | Statut |
|---|---|---|
| 1 | Une lecture témoin par tour, **4 Hz** ⇒ un échantillon tous les **0,125 nm** à 0,5 nm/s | 👤 déduit de specs données |
| 2 | Bruit **additif**, borné à **±0,05 point** (A = 5e-4 en unités T), σ = A/3, tirages indépendants entre lectures | 👤 confirmé |
| 3 | La chaîne de détection **moyenne sur 2 s**, soit une **moyenne glissante de `k = 8` lectures** | 🔒 hypothèse figée |
| 4 | ~~Le seuil vaut **3 σ du signal lissé**, soit `A/√k` = 0,354 A~~ → 🔴 **RÉFUTÉ le 2026-08-10.** La borne **mesurée** vaut **1,00 A** à `k = 8`, `N = 800`. Voir l'encadré rouge sous ce tableau. | ❌ **arithmétique fausse** |
| 5 | **Aucun retard** : le logiciel anticipe la valeur de trigger, et l'extremum enregistré est l'extremum lui-même | 🔒 hypothèse figée |
| 6 | Marge de sélection des λ : **5 σ du bruit brut** (1,66 A) aujourd'hui, **10 σ** (3,33 A) à évaluer | 👤 fourchette donnée |
| 7 | Quantification de l'arrêt : `U(0 ; 0,125 nm)`, strictement positive | 🔒 découle de 1 |

**Ce qui est explicitement HORS du modèle**, et le reste :

- σ dépendant de T ou de λ, grenaille, bruit multiplicatif ;
- bruit corrélé d'un tour à l'autre (voilage, faux-rond, gigue de déclenchement) — le modèle
  suppose des tirages **indépendants** ;
- toute forme de filtre autre que la moyenne glissante : exponentiel, médian, confirmation
  sur N lectures.

**Ce qui rouvrirait légitimement le postulat** : un run réel du dichroïque dont le taux de
plantage mesuré s'écarterait nettement du taux prédit. Rien d'autre. En particulier, pas un
raisonnement — ce projet a déjà payé trois fois pour avoir cru un raisonnement sur le bruit.

🔴 **Et c'est exactement ce qui est arrivé au postulat 4.** Il n'a pas été rouvert par un
raisonnement : il a été **réfuté par la mesure que [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.2 réclamait explicitement**, et qui
disait d'avance que 0,354 était *« une dérivation, pas une mesure »*. Le reste du postulat
tient — le lissage `k = 8` aide réellement, la borne passe de 1,66 A sur brut à 1,00 A sur
lissé. C'est **la loi en `1/√k`** qui est fausse, parce qu'elle applique un critère *par
échantillon* à un **extremum courant sur N échantillons**. La valeur 1,00 dépend donc de `N`
autant que de `k` : **c'est une mesure, pas une loi. Si l'un des deux change, remesure.**

### 🔴 MESURÉ LE 2026-08-09 — le postulat 4 ne fait pas ce pour quoi il a été dérivé

`scripts\probe_tp_fabrication.py`. Signal propre **plat**, bruit réel `A = 5e-4`, 20 000
tirages, `N = 800` échantillons (cadence machine), lissage **centré**, vrai
`detect_turning_points`, vrai `_seeded_noise_sample`.

```
  k=1, threshold 1.66 A, N=800  ->    99.955 %     (reference: 99.935 %)   <- ligne de controle
  k=8, threshold 0.354 A, N=800 ->   100.000 %     (12.2 predisait ~0 %)
  same, noise x0.01             ->     0.000 %     <- Piege 1 : c'est bien du bruit

      factor   in sigma_smoothed   fabrication
       0.354                3.00      100.000 %
       0.500                4.24       99.850 %
       0.707                6.00       20.960 %
       1.000                8.49        0.005 %
       1.250               10.61        0.000 %
       1.660               14.09        0.000 %
```

**Ce qui est réfuté, exactement** : pas le lissage (postulat 3, `k = 8` — il aide
réellement : la borne passe de 1,66 sur brut à **1,00** sur lissé). C'est **l'arithmétique du
postulat 4** qui ne tient pas. « 3 σ du signal lissé » est un critère **par échantillon**,
alors que `detect_turning_points` l'applique à un **extremum COURANT sur 800 échantillons**
(`certus_strat_growth.py:127-143` : il émet quand le signal recule de plus que le seuil depuis
le max courant). Sur ~100 fenêtres indépendantes, l'amplitude max−min du bruit vaut déjà
≈ 6 σ — ce que la ligne à 0,707 confirme à 20,96 %. Un seuil posé **à** 3 σ est franchi à tous
les coups.

**La borne mesurée est donc `1,00 A` à `k = 8` et `N = 800`**, soit **8,5 σ du signal lissé**
et non 3. ⚠️ Elle dépend de `N` autant que de `k` : **c'est une valeur mesurée, pas une loi.**

⚠️ **ET ELLE A ÉTÉ MESURÉE AVEC UN LISSAGE CENTRÉ, alors que le code lisse de façon CAUSALE**
(`certus_strat_growth.py:1398`, fenêtre `[i−k+1 … i]` — c'est `DEFAUTS_OUVERTS.md` §24-3). 🟢 **Ce n'est pas
disqualifiant ici, et voici pourquoi** : le signal propre de cette sonde est **plat**, donc les
deux lissages rendent le même bruit lissé — même variance `σ/√k`, seule la phase diffère. Le
décalage de `(k−1)/2` que `DEFAUTS_OUVERTS.md` §24-3 dénonce ne mord que pour **localiser** un extremum sur un signal
**non plat**, ce que cette mesure ne fait pas. **Mais toute mesure de seuil sur un signal non
plat devra, elle, être refaite en causal.**

**Si `k` ou la cadence changent, remesure** — n'extrapole pas, et surtout n'écris pas de
formule en `ln N` pour boucher le trou.

⚠️ **`k` reste un paramètre du code**, avec 8 pour valeur retenue. Le figer dans la
documentation n'interdit pas de le **balayer pour vérifier** que les résultats en dépendent
(Piège 1) : un taux de plantage insensible à `k` signalerait que le lissage n'atteint pas le
calcul. Figé veut dire « on ne re-discute pas la valeur retenue », pas « on ne la teste pas ».

---

## 19. ⚡ TU NE DÉCIDES RIEN — toutes les valeurs sont déjà fixées

**Aucun choix ne t'est demandé.** Toutes les valeurs physiques, tous les seuils, tous les
paramètres ont été arrêtés avec le physicien le 2026-08-08 et sont dans le tableau ci-dessous.

> **Si tu te trouves en train de choisir une valeur, tu t'es trompé : la valeur existe
> déjà. Relis §18. Si elle n'y est vraiment pas, ARRÊTE-TOI et demande.**

### Toutes les constantes, en un seul endroit

| Paramètre | Valeur | Où c'est expliqué |
|---|---|---|
| Cadence d'échantillonnage machine | **4 Hz**, un point tous les **0,125 nm** | §18-1 |
| Amplitude du bruit de lecture | **±0,05 point**, soit `A = 5e-4` en unités T | §18-2 |
| `reading_smoothing_window` (`k`) | 🔴 **DEUX VALEURS, ET IL FAUT LES DISTINGUER.** **Valeur du MODÈLE figé : 8** lectures (2 s à 4 Hz, §18-3). **Valeur RETENUE en exploitation : 1, c'est-à-dire INACTIF**, et elle le reste — 👤 : *« on ne sait pas trop les algos de smooth appliqués par Bühler »*, et §18 interdit d'ajouter une structure non mesurée. ⚠️ **Ce document portait ces deux valeurs sur DEUX LIGNES SÉPARÉES de cette même table jusqu'au 2026-08-19** : lue dans l'ordre, elle prescrivait 8 puis 1. Fusionnées. | §18-3 |
| `tp_hysteresis_factor` | 🔴 **DEUX VALEURS, ET LA TABLE N'EN DONNAIT QU'UNE.** **Valeur EN USAGE : 1,66** — c'est ce que portent **les 14 configurations réelles**, vérifié le 2026-08-19. **Valeur CIBLE : 1,00**, mesurée à `k = 8` et `N = 800`. ⚠️ *Cette ligne annonçait « **1,00** — ni 0,354 ni 1,66 », donc elle prescrivait une valeur qu'aucune configuration n'utilise, en niant celle qui tourne réellement. Le §20, lui, disait correctement « vaut 1,66 aujourd'hui, cible 1,00 ».* Le `1/√k` = 0,354 reste **réfuté** (il laisse **100 %** de points tournants fabriqués). 🔴 **Et la cible n'est pas applicable telle quelle** : elle a été mesurée à `k = 8`, or les 14 configurations tournent à `k = 1`. La valeur dépend de `N` autant que de `k` — **remesure avant de l'appliquer**. 🔑 **Et depuis le 2026-08-24 il y a un CRITÈRE DE PLUS** : ce facteur porte aussi le **sens** de la variation du plantage avec le bruit — 1,66 l'inverse, 0,5 le rend physique, 0 rend le détecteur inutilisable. La cible 1,00 tombe entre les deux, donc **la choisir engage ce sens aussi**. Voir la ligne `tp_hysteresis_factor` du §20 | §18-4, A1 |
| Retard de déclenchement | **aucun** — ne rien ajouter | §18-5 |
| `phase_a_level_margin_factor` | **1,66** actuel, **3,33** à évaluer | §18-6 |
| Quantification de l'arrêt | `U(0 ; 0,125 nm)` | §18-7 |
| `index_corridor` | **0,005**, unités d'indice **absolues**, demi-largeur — 👤 **ACTIF PAR DÉFAUT** | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.3 |
| `photometric_curvature_amp` | **0,00375** ⇒ à `T = 0,5` la vraie valeur est dans `[0,4975 ; 0,5025]` à 2 σ. 👤 **ACTIF PAR DÉFAUT** | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1bis |
| `allow_rate` | **vrai** — 👤 *« c'est le cas général »* | §22 |
| `slit_bias_enabled` | **vrai**, fente nominale **2 nm** — 👤 *« réaliste, pas optimiste »* | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.7 |
| `affine_scale_amp` | **0,05** ⇒ `a ∈ [0,95 ; 1,05]` | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1 |
| `affine_offset_amp` | **0,02** ⇒ `b ∈ [−0,02 ; +0,02]` | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1 |
| Plafond du banc | `CERTUS_BENCH_TIMEOUT_S = max(5400, 4 × durée attendue)` — 🔴 **5400 est un PLANCHER, pas une valeur** : le prendre pour une valeur a détruit quatre mesures le 2026-08-22 | `REPERES_MESURES.md` |
| Graine de référence | **42**, `scan_wl_step` **1.0** | `REPERES_MESURES.md` |
| `robustness_num_runs` | **300** — 👤 posé le 2026-08-13. ⚠️ **Ce n'est PAS un réglage de précision** : la profondeur commande la sensibilité du filtre de plantage, donc **quelles stratégies existent** | [`DECISIONS_TRANCHEES.md`, enquete 23](docs/DECISIONS_TRANCHEES.md) |
| `n_screen_runs` | **25**, et 👤 a délégué le choix le 2026-08-13. 🔴 **NE LE DESCENDS PAS À 10** : `1/10 = 10 % ≥ 5 %`, donc **un seul plantage sur dix tue la stratégie** — et depuis le correctif 1 elle est aussi perdue comme **parent**. §24-27 avait mesuré « 10 ne perd rien » **avant** que le criblage ne choisisse les parents : la mesure ne couvre plus le rôle | [`DECISIONS_TRANCHEES.md`, enquete 23ter](docs/DECISIONS_TRANCHEES.md) |
| `sigma_rate` (mode Rate) | 🔑 **aucune valeur à poser** — grandeur DÉRIVÉE du simulateur | §22, dérivation |
| Résolution du monochromateur | **2 nm** nominal · choix dans {5 ; 2 ; 1 ; 0,5} · facteurs de bruit **÷1,5 · ×1 · ×2 · ×5** | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.7 |

**Tout nouveau paramètre vaut sa valeur INACTIVE par défaut** (1 pour la fenêtre, 0 pour les
amplitudes et le corridor). Le chemin inactif doit rendre les mêmes bits qu'avant. Toujours.

---

## 20. Les quatre paramètres du modèle, et où les poser

Dans le JSON de configuration, à la racine. Lus par `collect_params`
(`certus/ui/certus_strat_ui_state.py`). **Tous valent 0 / faux par défaut**, et à 0 le
chemin de calcul est celui d'avant, au bit près.

| Clé JSON | Effet |
|---|---|
| `poem_anchor_noise` | Bruite le signal de monitoring **avant** détection des points tournants, lecture des ancres POEM et test d'atteignabilité. Phase A **et** B. |
| `tp_hysteresis_factor` | Seuil de détection d'un point tournant, en multiples de `A = trigger_tolerance/100`. Vaut **1,66** aujourd'hui. 🔴 **Valeur cible : 1,00**, **mesurée** à `k = 8`, `N = 800` (A1). L'ancienne cible **0,354** = `1/√k` est **RÉFUTÉE** : elle applique un critère *par échantillon* à un extremum courant sur `N` échantillons, et laisse **100 %** de points tournants fabriqués — §18-4. Injectable en 5ᵉ argument du script de sonde. 🔑 **ET IL PORTE UN TROISIÈME EFFET, MESURÉ LE 2026-08-24 : le SENS de la variation du plantage avec le bruit.** Le seuil vaut `facteur × A × noise_val`, donc il **suit** le bruit. À **1,66** le plantage DÉCROÎT quand le bruit croît (1577 contre 402) ; à **0,5** il CROÎT, sens physique (2 contre 642). ⚠️ **La cible 1,00 tombe entre les deux** — la choisir engage donc aussi ce sens, ce que ni le §18-4 ni A1 n'avaient pris en compte. À **0** le détecteur est inutilisable : 2929 murs sur 2929, zéro déposable. Balayage : `scripts/enchainer_hysteresis.sh` |
| `reading_smoothing_window` | ⚠️ **Existe depuis `e0df0e1`**, défaut **1**. Fenêtre de moyenne glissante appliquée au signal de monitoring avant détection, **en lectures machine**. Valeur du modèle figé : **8** (2 s à 4 Hz). 🔴 **Dans l'implantation actuelle ce drapeau commande AUSSI la grille de [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.4** — voir §24. |
| `index_corridor` | ⚠️ **Existe depuis `162a0ff`**, défaut **0,0**. Demi-largeur du corridor d'incertitude d'indice, en **unités d'indice absolues**. Valeur du modèle : **0,005**. Jamais mesuré. |
| `affine_scale_amp` / `affine_offset_amp` | ⚠️ **Existent depuis `f7a3d71`**, défaut **0,0**. Amplitudes du tirage de dérive photométrique, une fois par run. Valeurs de mesure : **0,05** et **0,02** ([`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1). Jamais mesurées. |
| `poem_enabled` | ⚠️ **Existe depuis `f7a3d71`**, défaut **vrai**. Force le repli absolu quand il est faux. C'est le drapeau que [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1 réclamait. Jamais mesuré. |
| `phase_a_level_margin_factor` | Marge exigée **en transmission** entre le niveau d'arrêt et les points tournants voisins. Active aussi la vraie matrice cumulée en Phase A. |
| `dp_yield_weight` | Poids du rendement dans l'objectif DP : `coût = coût_nm + w·(−log(1−p))`. |

---

📌 **Les repères chiffrés sont dans [`REPERES_MESURES.md`](docs/REPERES_MESURES.md)** — extrait
d'ici le 2026-09-08. Ce sont des **mesures qu'on consulte**, pas une consigne qu'on lit au
démarrage.

**Ce qu'il faut retenir sans l'ouvrir, et qui gouverne toute comparaison :**

| | |
|---|---|
| 🔴 **les SEEL des composants ne se comparent PAS entre eux** | ils ne vivent pas sur le même domaine spectral — **300 / 200 / 60 / 45 nm**. L'ordre `0,173 < 0,272 < 0,482 < 0,81` mélange la difficulté du composant et la largeur de la fenêtre où l'erreur est regardée. 🔑 Toute comparaison **à composant fixé** reste parfaitement valide ; c'est le seul régime qui l'est |
| 🔴 **ce qui PÉRIME un repère** | le **biais de fente** est actif par défaut depuis le 2026-08-11. Tout `RESULT` antérieur décrit une machine à fentes infiniment fines. Ce ne sont pas des chiffres faux : ce sont **les réponses à une autre question** |
| 🔴 **un `RESULT` seul ne départage rien** | à N = 150 la dispersion Monte-Carlo vaut σ ≈ 6 %, et l'écart entre la 1ʳᵉ et la 2ᵉ vaut **0,8 σ**. **Deux runs qui diffèrent de moins de ~8 % sont indiscernables.** Ce qui compare deux configurations est la **classe d'équivalence SEEL**, pas le score |
| 🔴 **`CERTUS_BENCH_TIMEOUT_S` : 5400 est un PLANCHER, pas une valeur** | la règle est `max(5400, 4 × durée attendue)`. Le prendre pour une valeur a **détruit quatre mesures de 90 minutes** le 2026-08-22, tuées à 13-16 nombres de blocs sur 16 |
| ⚠️ **le banc ne crie pas quand il échoue** | au-delà du plafond il rend `RESULT=None` et un tableau de 12 stratégies au lieu de 345 — **cela ressemble à un résultat**. Cherche `WAIT_TIMEOUT=` dans le journal : c'est l'empreinte, et elle est sans ambiguïté |

🔑 **Et le fait physique que ces repères établissent** : le random75 passe à 0 % de plantage
quand le 99 couches plante à 100 % en une campagne. **Ce n'est donc pas la LONGUEUR qui met le
monitoring optique en échec, c'est la STRUCTURE** — le premier n'a ni cavité ni miroir, le
second a cinq cavités et des miroirs de 19 couches.

⚠️ **Une mesure, une machine.** Ne lance rien d'autre pendant un run : le pipeline sature tous
les cœurs. Et une durée sans sa machine ne vaut rien — ce document a porté un `101,24 s`
reproductible sur aucune machine connue du projet.

---

## 22. 👤 Les règles gravées

### L'admissibilité d'une longueur d'onde de contrôle

> *« Une longueur d'onde de contrôle de la couche i (i > 1) est **interdite** si, lorsque le
> signal est bruité, il y a un risque de mal comptabiliser le nombre de turning points ou de
> ne pas s'arrêter au niveau de transmission voulu. »* — *« Valable en phase A comme en
> phase B. »*

Un seul énoncé physique, donc **un seul drapeau pour les deux étages**. Et la marge de
sécurité s'exprime **en transmission, jamais en nanomètres** : près d'un point tournant
`T ≈ T_ext − c·(d−d₀)²`, donc une marge fixe en épaisseur correspond à une fraction
d'amplitude non contrôlée.

### Les λ de contrôle se choisissent sur la grille de balayage

En longueur d'onde, pas en épaisseur. La grille est
`arange_inclusive(scan_wl_min, scan_wl_max, scan_wl_step)`, servie par
`_resolve_monitoring_wavelength_grid` (`certus/core/certus_strat_ranking.py`).

🔴 **Ne JAMAIS la déduire des clés de `clues_at_wl`.** Ce dictionnaire porte l'**union** de
la grille de balayage et de la grille d'affichage, donc un pas plus fin sur tout le
recouvrement **et un débordement hors plage**.

### La cible spectrale reste NON PONDÉRÉE jusqu'à nouvel ordre

> *« La cible spectrale restera non pondérée jusqu'à nouvel ordre. »* (2026-08-06)

Le mécanisme existe et il est testé — `compute_batch_rmse` accepte un vecteur de poids — mais
il est **délibérément inutilisé**.

⚠️ **La conséquence, dite une fois.** 📏 Les deux bandes du juge de paix font **exactement la
même largeur, 141 points chacune sur 301**. Un RMSE uniforme est donc *littéralement
incapable* de distinguer une stratégie qui rate la bande bloquée d'une qui rate la bande
passante : les deux scores sont égaux **à la précision machine**, alors que l'exigence
diffère d'un facteur ~500. Et le score reste dominé par le **décalage du front**, que
personne n'a demandé. **C'est un choix assumé, pas un oubli.**

### Les heuristiques de la littérature sont des diagnostics, pas des filtres

> *« Le 4 %, pour moi, c'était au pif, pour être certain qu'on va y arriver. Alors que là,
> nous on travaille sur de vrais signaux simulés grâce au bruit introduit. »*

15–85 %, amplitude de départ ≥ 4 %, swing in / swing out : **colonnes explicatives**, jamais
couperets. ⚠️ Ne pas confondre avec `tp_hysteresis_factor`, qui ne présélectionne pas : il
décrit comment la machine **lit**, et se **dérive** du bruit mesuré.

### Le mode « Rate » (Quartz / Chrono)

📌 **Le chantier vivant DU CALCUL est [`docs/CHANTIER_RATE.md`](docs/CHANTIER_RATE.md)**, et
c'est lui qui fait autorité depuis le 2026-08-19. ⚠️ *« Le chantier vivant » tout court était
ambigu : celui de l'interface est ouvert depuis le 2026-09-03 et n'a rien à voir. Les deux
sont nommés dans la carte du §3.* Les quatre acquis du jour, sans ouvrir le
dossier :

| | |
|---|---|
| 🔑 **le mécanisme du Rate est la POSITION TERMINALE, pas la couverture** | expérience **appariée**, même parente, mêmes 127 mères : 11 couches Rate au **milieu** (couvrant 32/35/39) ne sauvent **rien** — l'échec recule simplement en aval — là où **17 en queue** suffisent. Une couche Rate supprime son propre plantage mais **lègue son erreur en boucle ouverte à tout ce qui la suit** ; la dernière n'a rien en aval |
| ⚠️ **ce que j'avais publié était FAUX** | *« la queue franchit la zone où la dérive tue l'optique »* — réfuté : la couche critique des déposables est **39**, toujours **avant** la coupure, donc restée optique |
| 📏 **le taux réel de l'hybride** | **~3 %** à N = 150 (4/150 et 5/150), sous la cible de 5 %. Le `4,00 %` de `fast` n'était que la granularité **2/50** |
| 🔴 **ET LA SECONDE GRAINE A TOUT RENVERSÉ, le soir même** | `deep` à 2 nm rend **0 déposable à la graine 42** et **547 à la graine 77** — la meilleure à **SEEL 0,569 en 9 blocs**, soit le **meilleur résultat jamais obtenu** sur ce composant, à la fente nominale et sans Rate. ⚠️ *J'avais écrit six heures plus tôt, sur la seule graine 42, que « la queue Rate est le seul moyen connu de rendre ce design fabricable à la fente nominale ». C'était vrai à graine 42, et ce n'était pas un fait sur le composant.*<br>🔑 **Ce qui SURVIT, et qui sort renforcé** : `2 nm` pur optique marche à 77 et pas à 42 · `1 nm` pur optique marche à 42 et pas à 77 · **la queue Rate marche aux DEUX** (5 déposables chacune). Elle rend moins bien — 0,689 contre 0,569 — mais **elle rend toujours**. 📌 [`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md) §14 |

📌 **Le dossier historique est dans [`docs/MODE_RATE.md`](docs/MODE_RATE.md)** — : comment la
machine obtient son rate, pourquoi `sigma_rate` est une grandeur **dérivée** et non un
paramètre, et le plan A24 en entier.

**Ce qu'il faut savoir sans ouvrir le dossier :**

| | |
|---|---|
| **quand le Rate est nécessaire** | un **swing trop faible**. 🔴 **PAS** un seuil d'épaisseur : une couche de 30 nm à faible contraste d'indice a une dynamique aussi pauvre qu'une ultrafine. ⚠️ **Et « SWING_MIN » n'existe PAS comme symbole — il y a DEUX seuils différents, et ce document n'en nommait qu'un** : `RATE_SWING_MIN_DEFAULT = 0,025` (`certus_strat_robustness.py:531`), qui est le seuil d'**admission d'une λ en Phase A**, et **0,04** codé en dur (`:385`, commenté `# SWING_MIN`), sous lequel POEM **abandonne** et retombe sur le niveau absolu. **Une couche entre les deux est admise puis perd POEM en silence.** Trouvé le 2026-08-19 |
| **l'intuition de 👤** | *« le rate est souvent réservé aux couches fines »* — c'est un **proxy** du critère ci-dessus, corrélé mais pas équivalent |
| **où le solveur ESSAIE le Rate** | la **dernière couche de chaque bloc** (`_rate_candidate_layers`, `certus_strat_robustness.py:643` au 2026-08-19). ⚠️ *Le renvoi disait `:513` — mes éditions du jour l'avaient décalé de 83 lignes. **Cite la FONCTION, le numéro n'est qu'un raccourci.*** Critère de **coût**, pas de nécessité : à une frontière de bloc les ancres sont perdues de toute façon |
| **il n'y a pas d'auto-compensation en mode Rate** | les erreurs passent en boucle ouverte à la couche suivante |
| **le facteur est par couche** | calculé sur les couches **de même nature déposées AVANT** la couche `i`. Donc **`rate(i)` ≠ `rate(j)` même sur un matériau identique** |
| **actif par défaut** depuis le 2026-08-12 | 👤 : *« le rate est toujours permis, c'est le cas général »*. Une variante Rate est une candidate de plus, jugée sur les mêmes statistiques |

#### 🔒 GRAVÉ DANS LE MARBRE — 👤, 2026-08-19 : où le Rate a le droit d'exister

> 👤 *« attention, rate est interdit sur les 2 premières couches ! mais absolument pas la
> dernière »* — *« ces interdictions pour rate aux 2 premières couches et autorisation
> ailleurs doivent être consignées et gravées dans le marbre »*

| couche | Rate | pourquoi |
|---|---|---|
| **0 et 1** | 🔴 **INTERDIT** | le facteur de rate se calcule sur les couches de **même parité déposées avant** (`certus_strat_growth.py:634`). Pour `i = 0` et `i = 1` la boucle est **vide** : la machine n'a rien déposé dont elle puisse tirer un rate. **La borne physique vaut exactement 2** |
| **2 … N−1**, dernière **comprise** | 🟢 **AUTORISÉ** | aucune raison ne justifie d'en exclure une, et surtout pas la dernière |

🔴 **Le code avait les deux bornes à l'envers, et c'est corrigé le 2026-08-19**
(`RATE_MIN_LAYER = 2`, `certus_strat_robustness.py`) :

| | ce qui se passait avant |
|---|---|
| **la dernière couche** était **exclue** (`< num_layers - 1`, deux sites) | 📏 **0 placement sur 24 581** artefacts, alors que **l'avant-dernière est la position la plus choisie de toutes** (2 530). L'exclusion retirait donc le voisin immédiat de l'optimum |
| **les couches 0 et 1** n'étaient **pas** refusées | le noyau retombait **silencieusement** sur POEM (garde `n_ref > 0`). 📏 La couche 1 a été proposée **2 fois** : deux résultats étiquetés `RATE_L1` avaient en réalité simulé du **POEM pur**. Une étiquette qui ment |

🔑 **Et la mesure du même jour dit pourquoi la dernière couche est le MEILLEUR emplacement** :
une couche Rate supprime son propre plantage mais lègue son erreur en boucle ouverte à **tout
ce qui la suit**. La dernière n'a **rien** en aval — c'est le placement le moins cher de
l'empilement. Voir [`docs/CHANTIER_RATE.md`](docs/CHANTIER_RATE.md).

#### 🔒 GRAVÉ AUSSI — 👤, 2026-08-19 : le rate ne se calcule QUE sur les couches optiques

> 👤 *« rate ne se calcule qu'avec les couches optiquement déposées »*

🔴 **Le noyau faisait l'inverse**, et son commentaire l'assumait : *« it CHAINS: the last
deposited layer is a reference, Rate ones included »*. Corrigé le 2026-08-19
(`prev_rate_flags`, `certus_strat_growth.py`).

**Pourquoi ce n'est pas cosmétique.** Une couche Rate sort à `d_réel = d_nom / A` **par
construction**, donc son propre ratio `d_nom/d_réel` vaut exactement `A` — la moyenne courante
elle-même. La reprendre en référence ne changeait pas `A` mais **incrémentait `n_ref`** : le
vivier grossissait d'entrées à **information nulle**, et toute précision annoncée via la loi
en `1/√n` était surestimée dès qu'une couche Rate y entrait.

⚠️ **La conséquence physique demeure, et elle est maintenant visible au lieu d'être masquée** :
dans une **queue** de couches Rate, l'estimation se **fige** à sa valeur d'entrée — plus aucune
couche optique de ce matériau n'est déposée ensuite. **Toutes les couches de la queue héritent
donc de la MÊME erreur relative, corrélée, qui ne se moyenne jamais.** Une longue queue est
ainsi pénalisée là où l'ancien code la créditait d'un `n_ref` fictif.

⚠️ **Et l'arrondi à 0,125 nm n'est PAS un argument** — 👤 : *« on ne tient pas compte du round,
c'est d'un ordre supérieur »*. 0,125 nm sur une couche de ~100 nm vaut 1,2e-3 en relatif,
contre 2e-2 de dispersion héritée à une seule référence. Le commentaire du noyau prétendait
qu'il *« EST la loi d'arrêt `U(0 ; 0,125 nm)` du §18-7, apparue sans paramètre à poser »* :
**c'était une surinterprétation**, retirée.

🟠 **C1, et l'avertissement a été MESURÉ le jour même — il était trop fort.** Le vivier change
réellement : sur `r75x2`, les placements natifs passent de **291 à 314**, la couche 74 de **0
à 112**, et elle évince la 71. **Mais l'effet sur les résultats est nul** : rejeu complet du
balayage de queue, écart maximal **0,03 %** sur cinq coupures, falaise inchangée. Les
campagnes de queue antérieures restent donc lisibles.

🔑 **Et c'est démontrable, pas seulement constaté.** Une couche Rate sort à `d_réel = d_nom/A`
par construction, donc son ratio vaut **exactement `A`** : l'inclure ou l'exclure laisse la
moyenne **invariante**, `A' = (n_opt·A + n_rate·A)/(n_opt+n_rate) = A`. Le correctif ne change
donc que `n_ref` — **la précision annoncée, jamais l'épaisseur simulée**. Le seul résidu est
l'arrondi, et les 0,03 % mesurés sont bien de cet ordre. ⚠️ **Il corrige une affirmation, pas
un chiffre** — ce qui ne le rend pas facultatif : `n_ref` mentait.

🔴 **Le critère 3 ne cherche pas les couches qui ont BESOIN du Rate, il cherche celles où il
ne COÛTE rien.** Ce sont deux questions différentes et le code ne répond qu'à la seconde.

⚠️ **Un classement par marge a été tenté et annulé le même jour (2026-08-12)** — l'hypothèse
est séduisante et sera reproposée. Mesuré : la profondeur ne porte aucun signal, la marge en
porte un **mais il change de signe** d'un empilement à l'autre. Le détail est dans le dossier.

### 👤 SEEL — l'erreur équivalente par couche

📌 **Le dossier est [`docs/SEEL.md`](docs/SEEL.md)** — extrait d'ici le 2026-08-19.

> 👤 *« C'est pour caractériser la performance d'une stratégie donnée. On regarde quel tirage
> aléatoire donne une erreur spectrale du même niveau, et cela donne une erreur moyenne
> équivalente par couche. »* (2026-08-10)

**Ce qu'il faut retenir sans l'ouvrir :**

| | |
|---|---|
| **la définition** | `SEEL = 2 × √(RMSE_P95)`, en **nanomètres d'erreur d'épaisseur par couche**. C'est la seule grandeur du projet qu'un opérateur de bâti comprenne immédiatement, et **la seule à rapporter** — jamais le RMSE brut |
| **la règle de tri de 👤** | SEEL **quantifié**, puis le **rendement** départage les ex æquo. *À performance spectrale indiscernable, on prend la stratégie qui va au bout* |
| 🔴 **le pas est passé de 0,1 à 0,01 nm** le 2026-08-14 sur instruction de 👤 | **et le prix n'est pas mesuré** : à SEEL 0,3 nm, un bin de 0,01 nm est **deux fois plus étroit que le bruit statistique**. **En pratique : traite un écart d'un bin comme une égalité** |
| 🔴 **la seconde borne est du code MORT** | `seel_equivalence_half_width` implémente correctement `max(0,05 ; 0,06 × SEEL)` et **n'a aucun appelant en production**. Le classement ne connaît que le pas absolu. C'est le premier chantier du dossier |
| 🔴 **SEEL n'atteint pas le banc** | il n'existe qu'en mémoire (`APP_CONTEXT["seel_data"]`), calculé à l'étape 0 de l'interface. Les runs mesurés sont donc tous en **unité abstraite**, et le tri de 👤 tourne **dans la sonde**, à côté |

## 23. MULTIPLE TESTGLASS METHODOLOGY — acquis, plus en cours

📌 **Le dossier complet est dans [`docs/CHANTIER_MULTITEMOINS.md`](docs/CHANTIER_MULTITEMOINS.md)** :
le concept, ce qu'il coûte, la méthode d'assemblage validée, les campagnes, les parades adoptées,
et les douze sous-sections de synthèse. **Lis-le avant de toucher au sujet.**

⚠️ **Ce titre disait « le chantier EN COURS » jusqu'au 2026-08-19** — il ne l'est plus. Le
chantier vivant du calcul est [`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md) ; celui-ci est
**acquis et consultable**. Deux sections du même document se déclaraient « courantes », ce que la carte du
§3 a corrigé le matin sans que ce titre-ci suive.

**Le chantier en dix lignes.** Au-delà d'une certaine difficulté, un seul verre témoin ne
suffit plus : sur le passe-bande 99 couches à 5 cavités, **les 487 stratégies plantent à
100 %** en une campagne. On fait donc entrer un **témoin NEUF** en cours de dépôt, par
carrousel sous vide. La pièce ne quitte pas le plateau et reçoit toutes les couches ; chaque
témoin ne voit que sa campagne.

🔴 **Ce que ça coûte, et c'est le cœur du problème** : la compensation d'erreur ne traverse
pas le changement. Le résidu de la campagne précédente est **gelé dans la pièce, définitivement
incorrigible**.

| ce qui est acquis | |
|---|---|
| **le multi-témoins rend le 99c fabricable** | **0,81 nm** à 4 témoins `0-22/22-42/42-76/76-99`, 0 % de plantage par campagne — contre 100 % en une seule |
| il ne rend **pas** plus précis | la comparaison honnête est *impossible → possible* |
| c'est un outil de **faisabilité**, jamais d'optimisation | contrôle négatif passé **3 fois sur 3** : +73/+89 % (48c), +10/+98 % (35c), +110 % (75c) |
| **où** changer, et **combien** de témoins, importent peu | étendue +11,6 % sur 436 partitions, **31 à égalité** ; 4 témoins 0,782 nm contre 3 témoins 0,784 nm, **à graine 42** — une comparaison à graine fixée reste valide, c'est la VALEUR ABSOLUE qui ne l'est pas |
| la barrière est **structurelle ET la longueur compte** | 75 couches aléatoires passent à 0 % ; le taux s'effondre pourtant avec la longueur, `r = −0,869` |
| le mécanisme d'échec est **la marge**, pas le comptage | 83 % `TP_MISCOUNT`, mais la cause est le sursaut trop proche de l'hystérésis et le plancher photométrique |

⚠️ **Deux chiffres périmés circulent encore** : le « 0,860 nm » et le « 0,760 nm ». Le premier
est un **score de repli** (100 % de plantage), le second était **biaisé vers le bas** par la
malédiction du vainqueur. Voir la §23.12 du dossier.

---

📌 **Le registre complet est dans [`DEFAUTS_OUVERTS.md`](docs/DEFAUTS_OUVERTS.md)** — extrait
d'ici le 2026-09-08 parce qu'il pesait **24 % de ce fichier à lui seul** (~10 700 tokens
avalés à chaque démarrage) alors qu'il se **consulte**, il ne se lit pas.

🔴 **Sa portée, et il faut la connaître avant d'y croire** : tout y vient de la lecture des
diffs, du code et des artefacts committés, plus `ruff` et la suite de tests. **Aucune mesure au
banc n'a été relancée.** Une déclaration chiffrée y est donc *réfutée* seulement si un artefact
la contredit ; celles qui n'ont produit aucun artefact ne sont ni confirmées ni réfutées —
elles sont **non vérifiées**, un troisième état qu'il ne faut pas confondre avec « tient ».

**Les cinq qui gouvernent, sans ouvrir le dossier :**

| | |
|---|---|
| 🔴 **`search_resolution` était neutralisé dans TOUTE la campagne des intervalles** | alors que 👤 l'a posé comme **prérequis** — « la fente est systématiquement cherchée ». Les 272 intervalles du cache premium ont donc tourné sur une machine où l'opérateur n'a pas le droit d'y toucher |
| 🔴 **le logger `ThinFilm` est MUET** | tout `logger.info` du classement est **perdu**. Un run de 50 min a été rendu ininterprétable faute de distinguer « la passe n'a pas tourné » de « chaque candidate était infaisable ». 🔑 *Un instrument dont la sortie n'atteint pas le résultat n'est pas un instrument* |
| 🔴 **restreindre la plage de blocs VIDE la DP** | à plage restreinte le solveur ne rend **aucun groupement** ; à plage complète le même bloc en mine 601. Toute mesure comparative de la RECHERCHE se fait à plage complète |
| 🔴 **un verdict d'intervalle n'est pas déterminé par une graine** | même intervalle, même code, `robustness_seed` seul change : `0/452` et 42 % de plantage contre `70/521` et 0 %. La graine décide là où l'intervalle est **marginal** |
| 🔴 **`strategy_id` n'est PAS unique** | 21 identifiants sur 79 portés par 2 ou 3 stratégies **différentes**. Tout appariement enfant/parente par `from {id}` est donc ambigu, et n'est légitime que là où l'unicité a été **vérifiée**, pas supposée |

⚠️ **Le motif qui les relie, et c'est lui qu'il faut retenir** : *un réglage visible qui n'agit
pas est pire qu'un réglage absent — il fournit une explication fausse pour un résultat, et
personne ne va la vérifier.* **Avant d'attribuer quoi que ce soit à un paramètre, vérifie qu'il
arrive.** Le dossier en recense plusieurs : `dp_yield_weight`, `machine_sampling_dd`,
`strategy_phase_timeout`, et dix clés sur onze qui n'atteignaient pas le calcul depuis le JSON.

---

## 25. Décisions ouvertes et tranchées

### ✅ Tranchée — la marge de sécurité s'exprime en transmission, jamais en nanomètres

Dans `certus/utils/certus_strat_service.py::_select_candidates_phase_a`, la règle de proximité branche la vraie matrice d'empilement cumulée $M_{\text{before}}$ et remplace le critère fixe en épaisseur par le **critère en transmission** ($\Delta T \ge \text{margin\_factor} \times A$, avec `phase_a_level_margin_factor > 0`).

Près d'un point tournant $T \approx T_{\text{ext}} - c \cdot (d - d_0)^2$, une marge fixe en épaisseur correspond à une fraction d'amplitude non contrôlée ; seule la marge exprimée en transmission garantit un niveau de sécurité homogène et physiquement rigoureux face au bruit de la machine.

### 🔒 FIGÉE LE 2026-08-12 — la grille de balayage reste à 1 nm

👤 *« Enfin on va figer la grille à 1 nm. »* Après la campagne de [`DECISIONS_TRANCHEES.md`, enquete 22](docs/DECISIONS_TRANCHEES.md), 8 runs sur les
deux composants et deux graines : **1 seule paire sur 4** satisfait le critère
d'équivalence. Trois fois sur quatre la grille fine gagne, de 19 à 42 %.

⚠️ **Et la quatrième fois la grossière gagne de moitié — ce n'est pas un argument pour
elle.** Le run à 1 nm n'avait tout simplement pas généré la famille gagnante (48 blocs).
C'est un symptôme de recherche non convergée, pas une vertu du pas de 2 nm. **Ne cite
jamais ce cas comme un point en faveur du 2 nm.**

### ✅ Tranchée — le pas d'échantillonnage du dépôt reste GROSSIER

👤 *« Évidemment qu'on ne fait pas un calcul tous les 4 Hz, c'est la base de ce code qui
doit être ultra rapide ! »* (2026-08-12)

`machine_sampling_dd` reste à **0**, soit ~21 points par couche là où la machine en lit
800. **La conséquence, et il faut la connaître** : [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.2 a mesuré que moins de tirages
signifie moins d'occasions pour le bruit de fabriquer un faux point tournant — 32,9 % à
80 points contre 99,9 % à 800, à seuil égal. **Le modèle est donc OPTIMISTE sur ce
mécanisme**, qui pèse 79 % des plantages mesurés (`DEFAUTS_OUVERTS.md` §24-36). C'est un arbitrage assumé
vitesse / fidélité, pas un oubli.

### 🔒 La grille de balayage est FIGÉE à 1 nm — ne la rouvre pas

👤 *« Enfin on va figer la grille à 1 nm. »* (2026-08-12). Deux campagnes indépendantes, sur deux graines, ont mesuré que le pas de 1 nm gagne d'un facteur ~2 ; le détail de ces mesures est dans `git log`, et il ne sert plus le codage — la décision est prise.

⚠️ **Effet de bord à connaître** : `wl_step` valant déjà 1 nm, la grille de balayage et la grille d'affichage coïncident, donc le bug de confusion entre elles devient **invisible sans avoir disparu**. **Ne supprime pas `_resolve_monitoring_wavelength_grid`** au motif que les deux grilles sont identiques.

---

## 26. 🔴 La validation externe — elle n'a plus qu'un seul chemin

**Aujourd'hui STRAT n'est validé que contre lui-même.** Tout ce qui précède le rendra plus
cohérent ; **rien ne prouvera qu'il dit vrai.**

👤 Deux décisions du 2026-08-06 : *« seul le 48 couches est un exemple valable »* et
*« oublie aussi la séparatrice »*.

⚠️ **La première est CADUQUE depuis le 2026-08-16** — le §8 la barre, le projet a **quatre**
composants d'essai, et le random75 existe pour conclure en général. C'est la **quatrième**
survivance de cette règle trouvée le 2026-08-19, après la règle 4 du §11, le vocabulaire du
§14 et le titre du §23. 🔑 **Mais l'argument de cette section n'en dépend pas** : ce qui
manque n'est pas un composant de plus en simulation, ce sont des **dépôts réels**. Un
cinquième empilement simulé ne validerait rien de plus que les quatre existants.

> **Il ne reste qu'un chemin : des dépôts réels du dichroïque 48 couches.** Au moins **deux**
> stratégies réellement déposées, avec leurs spectres mesurés. Deux suffisent, parce que le
> test décisif est **ordinal** — STRAT doit les classer dans le bon ordre. Bien moins
> exigeant qu'une correspondance absolue, et bien plus probant qu'un accord avec soi-même.

⚠️ **Tant qu'on ne les a pas, nommer les choses correctement** : le dichroïque est un **banc
de cohérence**, pas un juge externe. Aucun chiffre de ce document n'est une validation
physique.

---

## 27. Autres chantiers ouverts

📌 **Le dossier est [`docs/CHANTIERS_OUVERTS.md`](docs/CHANTIERS_OUVERTS.md)** — extrait
d'ici le 2026-08-19, quand ce fichier a touché 1 990 lignes sur 2 000.

**Ce qu'il faut retenir sans l'ouvrir :**

| chantier | l'essentiel |
|---|---|
| 🔵 **compter les λ qui offrent un point tournant**, proposé par 👤 le 15/08 | la Phase A filtre sur le **swing** et le **plancher photométrique**, **jamais sur l'existence d'un point tournant** — une couche à `T` monotone passe le filtre et n'offre aucun point d'arrêt. La donnée est déjà calculée, le correctif fait une dizaine de lignes. ⚠️ Mais en **coût**, pas en couperet, et le coût doit être **non monotone** : trop de points tournants proches déclenche `CRASH_TP_MISCOUNT` |
| 🔵 **la « phase intermédiaire »** proposée dans la foulée | elle **existe déjà** : c'est la DP de Phase B, qui minimise exactement les changements de λ. Ce qui manque n'est pas la phase, c'est le **critère d'admissibilité** qu'elle consomme |
| 🟢 **la Phase A ignore qu'une couche Rate efface l'historique** | établi, chiffré, **délibérément repoussé** — l'effet est borné à **une** couche, et le score reste honnête. Correctif en deux lignes |
| **isolation des tests** · **performance** · **plan d'amélioration** | trois renvois, aucun fait dupliqué ici |

### Dette de lint

```
ruff check .  (config projet)             ->  All checks passed!
ruff check .  (memes regles, sans ignore) ->  12 142 erreurs    <- REMESURE le 2026-08-19
```

**La dette est celle que masque `extend-ignore`, pas celle que `ruff` rapporte.** Les
**68 règles** de la liste sont exactes (comptées le 2026-08-19), et le « 12 157 » qui portait
la mention *(non remesuré)* est **confirmé à 0,1 % près** : **12 142**.

📏 **Le protocole, pour que ce soit reproductible** — vider `extend-ignore` dans une copie de
`pyproject.toml`, lancer `ruff check . --statistics`, restaurer. **Ne jamais mesurer avec
`--select ALL`** : cela active des règles que le projet n'a jamais choisies et rend
**58 449**, un chiffre qui ne veut rien dire ici.

🟢 **ET LA PARTIE LA PLUS ALARMANTE DE CE BLOC EST PÉRIMÉE — elle a été RÉPARÉE.** Il annonçait
*« les plus dangereuses masquées : **F822 (202)** — `__all__` référençant des noms inexistants,
tout `import *` sur eux lève `AttributeError` ; **F821 (67)**, dont 3 réels dans
`certus/physics/gradient_analytic.py` »*. 📏 `ruff check . --select F821,F822` rend désormais
**`All checks passed!`** — **zéro des deux**, sur tout le dépôt.

**Ce qui reste, mesuré** : `F401` **5 293** (imports inutilisés — dont beaucoup de ré-exports
volontaires, voir l'interdit n° 1) · `F405` **3 122** · `E402` **900** · `I001` **898** ·
`F403` **52**. Le gros de la dette est donc de l'**import**, pas du **nom indéfini** — deux
natures très différentes de risque, et c'est la seconde qui avait disparu.

### CI

Le compte de fichiers de test se lit par `git ls-files "tests/**/test_*.py" | wc -l`, pas ici :
il a valu 241 puis 334 en trois semaines, et chaque valeur écrite a été fausse le lendemain. ⚠️ **Le « 2 299 tests collectés » qui
figurait ici est faux par inclusion** : `tests/oracle/` + `tests/unit/` en rend à eux seuls
**2 456** au 2026-08-19, et `tests/` est un sur-ensemble. 🔴 **Ne recopie pas ce nombre : il
change dès qu'on ajoute un test** — compte-le avec `--collect-only` (§2). Le compte réel de
la suite complète n'est pas mesuré — elle coûte ~1 h 45.
### 🔴 LA CI NE TOURNAIT PAS, ET QUAND ELLE TOURNAIT ELLE ÉTAIT ROUGE — 2026-09-08

Quatre défauts distincts, tous mesurés, **tous corrigés**.

| # | ce qui était | état |
|---|---|---|
| 1 | `lint.yml` et `tests.yml` ne se déclenchaient que sur `main` et `refactor-corridors-mixins`. **La branche de travail n'y était pas** : aucun commit du jour n'aurait été vérifié | ✅ **filtre de branche supprimé** |
| 2 | `lint.yml` exigeait un formatage que **510 fichiers** ne respectent pas — alors que `pyproject.toml` dit noir sur blanc que le formatage **n'est pas appliqué** et attend une PR dédiée. La CI contredisait la politique du dépôt | ✅ **étape retirée**, à rétablir le jour de cette PR |
| 3 | l'audit des connexions anonymes exigeait **zéro** et en trouvait **cinq** | ✅ **zéro** |
| 4 | l'audit des symboles morts rendait **32 candidats** | ✅ **zéro non résolu** — voir ci-dessous |

🔑 **Le défaut n° 1 est EXACTEMENT celui du chemin d'interpréteur** : une **liste** se périme,
une **propriété** non. Le commentaire d'origine disait pourtant *« ne surveiller que `main`
revenait à ne rien surveiller »* — la leçon était bonne, la solution était d'ajouter un
deuxième nom à la liste, et elle s'est périmée à son tour.

📌 **Sur les cinq connexions anonymes** : **trois vivaient dans des branches inatteignables**
du câblage des raccourcis — les cinq entrées déclarées portent toutes un script, donc les
branches `Ctrl+Plus` / `Ctrl+Minus` / `Ctrl+0` et leur repli n'ont jamais pu s'exécuter.
Retirées. Une quatrième était **de moi**, écrite le matin même. Et l'audit en **rate** une
cinquième par construction : sa recherche exige que la connexion tienne sur une seule ligne.

🔴 **LE DÉFAUT N° 4 ÉTAIT DANS L'OUTIL, PAS DANS LE CODE — et cette section a d'abord conclu
l'inverse.** Elle disait *« je n'y touche pas, chacun des 32 demande un jugement »*. 📏 Mesuré
le 2026-09-08 : l'audit cherchait ses **références** dans le **même périmètre étroit** que ses
**candidats** — la racine plus le paquet de physique. Or **27 des 32 sont appelés depuis
`certus/`**, l'arbre qu'il n'ouvrait jamais. Ce n'étaient pas 32 jugements à rendre, c'était
**un** défaut de périmètre.

🔑 **Les deux périmètres ne sont pas le même objet, et les confondre était la faute.** Celui
des **candidats** est étroit *à dessein* — signaler les 109 fichiers d'interface noierait le
signal. Celui des **références** n'a aucune raison de l'être : **un appel compte d'où qu'il
vienne**. `tests/` reste dehors, lui aussi à dessein — un symbole que seul un test appelle est
mort en production, et le compter le masquerait.

📏 **32 → 5**, puis **0** une fois les sept candidats justifiés un par un. La liste
d'exemptions est passée de **64 entrées à 7** : les 57 autres dataient d'un périmètre plus
large et **ne pouvaient plus rien apparier**. Une exemption qui ne peut plus rien couvrir est
une promesse que personne ne vérifie — et elle couvrirait en silence un symbole qui meurt plus
tard. 📌 Les sept restants, et ce qu'il reste à en faire :
[`DEFAUTS_OUVERTS.md`](docs/DEFAUTS_OUVERTS.md) §55.

⚠️ **Ne crédite pas cet outil de plus qu'il ne fait** : il apparie par **nom nu**, pas par
symbole qualifié — une méthode passe pour vivante dès qu'une autre classe appelle un homonyme.
C'est pourquoi `CertusHub.closeEvent` est désormais résolu, et **pas** parce que l'outil aurait
appris ce qu'est une redéfinition Qt. Il **sous-signale**, ce qui est le bon sens d'erreur pour
une barrière — mais **un vert ne prouve pas l'absence de code mort**.

🟢 **Le verdict de la CI tombe désormais AUSSI en local**, pour les deux audits :
`tests/unit/test_ci_lambda_connect_audit.py` et `tests/unit/test_ci_dead_symbol_audit.py`
**exécutent** l'audit au lieu de le dupliquer, avec des contrôles négatifs dans les deux sens —
dont un qui interdit les exemptions fossiles, et qui **échoue exprès quand on répare quelque
chose** : la réparation faite, l'exemption doit partir avec. Un job rouge sur GitHub que
personne ne regarde ne protège rien.

---

# PARTIE IV — LES DOSSIERS DE `docs/`

## 28. ⚡ FEUILLE DE ROUTE — voir le dossier

📌 **[`docs/FEUILLE_DE_ROUTE.md`](docs/FEUILLE_DE_ROUTE.md)** — ce qui est
**acquis** action par action (A1 à A25), ce qui est **outillé** et ne doit pas être réécrit,
et les paliers suivants.

**Les trois règles qui fixent l'ordre :**

1. **Une sonde bon marché qui peut invalider un gros travail passe AVANT ce travail.**
2. **Rien de comparatif ENTRE DATES avant que le repère A7 soit rétabli.** ⚠️ Cela n'interdit
   **pas** de comparer des runs **à protocole fixé** dans une même campagne.
3. **Rien de mesuré avant d'être mesurable isolément** (contrainte C3).

**Après chaque action** : `pytest tests/oracle/ tests/unit/ -q --no-cov` → **0 failed** · `ruff check .` → propre · un commit, avec la sortie collée.

🔴 **Les deux défauts d'implantation à connaître avant tout** :

| | |
|---|---|
| **A8 — `machine_sampling_dd` reste INATTEIGNABLE EN PRATIQUE** | il existe, il est dans l'interface, il est dans 9 configurations d'exemple. 📏 **Recompté par AST le 2026-08-19 : 8 sites d'appel du noyau, dont 1 seul le passe — et il passe la valeur littérale `0.0`** (`certus_strat_batch.py:500`, ajoutée ce jour-là pour atteindre `prev_rate_flags` par position). ⚠️ *La ligne annonçait « aucun des 27 sites » : le compte était faux d'un facteur 3.* **Le noyau reçoit donc toujours `0.0`, et le paramètre de l'interface n'atteint toujours pas le calcul.** |
| **La marge de comptage ne décide de rien** | `turning_point_margins` la calcule, elle remonte jusqu'à `margin_by_layer` avec le commentaire *« NEEDED FOR RANKING »*, et le câblage n'a été fait que le 2026-08-16, `use_margin_ranking` **off par défaut**. |

---

## 29. Le travail à venir sur le MODÈLE PHYSIQUE

📌 **Le dossier complet est dans [`docs/TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md)** —
une sous-section par chantier, chacune avec le fichier et la fonction exacts, ce
qu'il faut écrire, et le test qui doit ÉCHOUER sur le code d'avant.

**Les trois contraintes qui s'appliquent à TOUTES ces actions** *(elles restent ici parce
qu'elles gouvernent aussi tout le reste du projet)* :

| | |
|---|---|
| **C1** | Un changement de modèle **change les chiffres**. Toute mesure antérieure devient incomparable, sauf si le nouveau comportement est **désactivé par défaut**. |
| **C2** | Les deux étages — croissance et notation — doivent voir **la même réalisation** de la perturbation. Sinon on mesure un filtre qui n'a jamais existé. |
| **C3** | **Une chose à la fois, un commit chacune.** Deux modifications simultanées ne s'attribuent pas. |

**Ce que contient le dossier :**

| | sujet | état |
|---|---|---|
| 12.1 | l'épreuve de POEM | ✅ **acquise** — et la dérive photométrique n'est **pas** affine |
| 12.2 | modéliser le lissage de lecture | ouvert — 🔴 surtout **pas** remonter le seuil |
| 12.3 | méconnaissance d'indice | spécifié par 👤, corridor de dispersion |
| 12.4 | grille d'échantillonnage à la cadence machine | ouvert — **à faire AVANT 12.2** |
| 12.5 | quantification temporelle du déclenchement `U(0 ; 0,125 nm)` | ouvert |
| 12.6 | facteur de face arrière | **en dernier, ou jamais** |
| 12.7 | résolution du monochromateur | spécifié par 👤 |

---

## 30. 🔴 ÉTAT RÉEL DE L'IMPLANTATION

📌 **[`docs/ETAT_IMPLANTATION.md`](docs/ETAT_IMPLANTATION.md)** — établi **contre
le CODE** et jamais contre ce document.

**Les points qui gouvernent, et qu'il faut connaître avant d'écrire quoi que ce soit :**

| | |
|---|---|
| **le biais de fente est actif par défaut** depuis le 2026-08-11 | tout `RESULT` antérieur décrit une machine à fentes infiniment fines. C'est ce qui périme les anciens repères (`REPERES_MESURES.md`) |
| **la moyenne de lecture reste causale** | elle ne regarde pas en avant |
| **l'arrêt n'est pas quantifié** | la loi `U(0 ; 0,125 nm)` de §18-7 n'est pas appliquée |
| 🔴 **`machine_sampling_dd` est inatteignable en pratique** | 8 sites d'appel, 1 le passe — et en dur à `0.0`. Le compte est en §28 |

---

## 31. ⚡ PERFORMANCE

📌 **[`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)** — résultats **positifs comme
négatifs**, et les négatifs comptent autant : trois pistes y sont **fermées par la mesure**.

| | |
|---|---|
| 📏 **Il n'y a PAS de ×2 disponible** dans les pistes documentées | mesuré le 2026-08-04 |
| seul gain acquis sur STRAT | **−10 %** |
| la forme fermée de `T(d)` | **×1,20 mesuré**, et elle est **exacte** — même calcul écrit autrement, vérifié à 5,4e-20 contre le noyau et 3,2e-15 contre l'oracle |
| le fossé entre machines | ×1 à ×3,2 selon les modules, **pas** ×7-10 |

⚠️ **Les mesures de performance antérieures au 2026-08-11 ne se citent plus** : elles précèdent le biais de fente, donc elles répondent à une autre question (`REPERES_MESURES.md`). Seuls les **rapports** de [`PERFORMANCE.md`](docs/PERFORMANCE.md) restent valides.

---

## 32. Les composants d'essai

📌 **Le dossier est dans [`docs/COMPOSANTS.md`](docs/COMPOSANTS.md)** — la formule, les
matériaux, la plage spectrale et l'histoire de chaque composant.

**Les cinq, et ce que chacun sert à tester** — les repères chiffrés sont dans `REPERES_MESURES.md` :

| composant | couches | ce qu'il apporte |
|---|---|---|
| **dichroïque** `JSON-strat-example` | 48 | le juge de paix. Passe-court, front à ~545 nm. Monitoring facile |
| **passe-bande 3 cavités** `JSON-strat-bandpass-3cav` | 35 | une résonance, une bande étroite. Notation sur 60 nm seulement |
| **aléatoire** `JSON-strat-random75` | 75 | 🔑 **ni cavité, ni miroir, ni périodicité** — le seul qui teste si une règle est **générale**. Graine 2026 |
| **passe-bande 5 cavités** `-5cav-99c` | 99 | le cas dur. **100 % de plantage** en une campagne |
| **aléatoire ×2** `-random75-x2-fabricable` | 75 | 🔑 **l'étalon depuis le 2026-08-20.** Le random75 aux épaisseurs **doublées**. Fente native **1 nm** — d'où le `-fabricable` de son nom. Tourné à **2 nm** il est à la moitié de sa résolution de conception, et c'est là que tout le travail se joue |

🔴 **Ils ne sont pas notés sur le même domaine spectral** — 300 / 200 / 60 / 45 nm. Comparer
leurs SEEL entre eux mélange la difficulté du composant et la largeur de la fenêtre. Les
comparaisons **à composant fixé** restent valides. Voir `REPERES_MESURES.md`.

---

## 33. Décisions tranchées — voir le dossier

📌 **[`docs/DECISIONS_TRANCHEES.md`](docs/DECISIONS_TRANCHEES.md)** — quatre enquêtes closes,
gardées **pour ne pas les refaire**, avec le critère qui a tranché à chaque fois.

| | sujet | ce qui a été décidé |
|---|---|---|
| 22 | **la grille des λ de contrôle**, 1 nm contre 2 nm | enquête du 2026-08-12 |
| 23 | **la profondeur Monte-Carlo** | **N = 300** et `n_screen = 25` — 🔑 *et le critère n'est pas celui qu'on croit* |
| 23bis | le correctif 2 | 🔴 **mesuré mais NON CONSIGNÉ, donc inexploitable** : la campagne a tourné, les 6 runs sont `FAILED`, la traçabilité est à réparer **avant** de relancer |
| 23ter | le correctif 1 | 🔒 **acquis** : la recherche ne dépend plus de la profondeur de notation. `N` ne doit décider d'aucune candidate |

🔑 **L'invariant à ne jamais casser** : `N`, la profondeur Monte-Carlo, sert à **noter**,
jamais à **choisir**. Une candidate écartée parce que `N` était petit est une candidate perdue
pour toujours.

---

## 34. 💡 A25, A26, A27 — la réserve

📌 **[`docs/RESERVE_A25_A27.md`](docs/RESERVE_A25_A27.md)** — pour chacune, le
fichier et la fonction exacts, ce qu'il faut écrire, le test qui doit **échouer** sur le code
d'avant, et les pièges connus.

🔴 **CE N'EST PAS LE PROGRAMME COURANT.** Ces trois actions sont **valides, utiles et
entièrement spécifiées**, et elles attendent.

🔑 **Quel EST le programme courant se lit à UN SEUL ENDROIT : la carte du §3.** Cette ligne
ne le nomme plus, et c'est délibéré. ⚠️ Elle a successivement désigné le multi-témoins (acquis
depuis le 2026-08-19) puis le Rate, et le 2026-09-06 elle ignorait encore la campagne
d'ergonomie ouverte trois jours plus tôt. **Un fait recopié est un fait qui se périme** :
c'était déjà le cinquième endroit du document à retarder, après la carte du §3, le titre du
§23, la règle 4 du §11 et le vocabulaire du §14. Le nommer ici une sixième fois n'aurait fait
que préparer le sixième retard.

| | | pourquoi elle compte |
|---|---|---|
| **A25** | `sigma_rate` comme **prédiction** | 🔑 la seule action du document qui attaque §26 — la première grandeur vérifiable **de l'extérieur**, contre ce que 👤 observe en salle (±1 à 2 %) |
| **A26** | un bloc de **santé de run** | automatise le contrôle 4 de §12 |
| **A27** | le harnais d'empreinte `float.hex()` | A5, la non-régression au bit près |

**Ce qui les motive, et qui n'a pas changé** : tout le travail des 12 et 13 août a rendu STRAT
plus **cohérent**. Rien ne l'a rendu plus **vrai**. §26 reste entier, et aucun correctif
interne n'y changera quoi que ce soit.
