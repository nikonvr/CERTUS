# CERTUS — document de référence

**C'est le point d'entrée du projet, et la carte de tout le reste.**

⚠️ **Il disait « tout le savoir est ici, il n'y a rien d'autre à lire » — c'est FAUX depuis
les extractions du 2026-08-16.** Le savoir vit dans **25 fichiers** : ce document porte les
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
| [`docs/REPRISE.md`](docs/REPRISE.md) | les chiffres de référence, les cinq pièges, et **ce qui est faux dans les vieux documents** — sa table de correction est la première chose à lire avant de citer un nombre |
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
[`PLAN_2026-08-16.md`](docs/PLAN_2026-08-16.md) : que des commandes, des sorties attendues, et
zéro fait qui ne soit pas déjà écrit ici.

### 🟢 La cohérence entre dossiers est vérifiée MÉCANIQUEMENT depuis le 2026-08-19

```bat
C:\envs\certus\Scripts\python.exe scripts\coherence_md.py
```

`check_claude_md.py` vérifie **un** fichier ; celui-ci vérifie que **le même fait porte la
même valeur dans les 25 `.md`** — c'est-à-dire la règle ci-dessus, appliquée par une machine.

| | |
|---|---|
| **la référence vient du CODE** quand elle existe | six constantes du Rate et de la photométrie sont lues par AST dans les sources : un document qui s'en écarte a tort **même si tous les autres le répètent** |
| **il porte un CONTRÔLE NÉGATIF** | il plante une contradiction volontaire et exige de la détecter. 🔑 *Un harnais dont tout passe toujours ne prouve rien* — et ce contrôle a immédiatement révélé que l'outil n'examinait que **2 lignes sur 9** pour le 48c |
| **il ne comprend pas le français** | une ligne qui **raconte** une correction est écartée par marqueur (« périmé », « non comparable », « score de repli »). Un signalement est **une phrase à lire**, pas une erreur |

📏 Au 2026-08-19 : **0 point à instruire** sur **cinq balayages**, contrôle négatif vert.

| balayage | ce qu'il couvre |
|---|---|
| **A** — constantes du code | 6 constantes lues par AST, zéro document ne les contredit |
| **B** — grandeurs physiques | 10 faits (SEEL des 4 composants, cadence, bruit, fente, cible, rendement) : **valeur unique** partout |
| **C** — 🔑 **automatique** | **297 symboles numériques** découverts dans `certus/`, **18 cités** dans les `.md`. Tout `NOM = N` écrit dans un document est comparé au code. **Ce balayage grandit tout seul** quand un document cite un symbole de plus |
| **D** — profondeurs par mode | la table `fast/premium/deep` lue dans l'interface, et les **triplets** `50 / 150 / 300` que les documents écrivent |
| **E** — contrôle négatif | plante une contradiction et exige de la détecter |

🔑 **Ce qu'il a trouvé le jour de son écriture** : le `facteur 2,5` de `PLAN_2026-08-16.md` —
dérivé du `0,760 nm` **rétracté** — quand `REPRISE.md` disait **2,7** pour la même grandeur.
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
rend en permanence **5 « VALEURS DISCORDANTES »**, et les cinq ont été instruites une par une
le 2026-08-19 : **ce sont des faux positifs**, le contrôle rapprochant un nom de paramètre du
premier nombre voisin. `index_corridor : 162` vient du hash `162a0ff` · `dp_yield_weight :
2026` d'une date · `machine_sampling_dd : 21 / 27 / 9` de comptages (« 21 points », « 27 sites
d'appel », « 9 configurations ») · `reading_smoothing_window : 2` du « 2 s » de la fenêtre ·
`phase_a_level_margin_factor : 1,66 / 3,33` sont **les deux valeurs légitimes** (actuelle et à
évaluer). 🔑 **Le contrôle reste utile — il a trouvé la vraie contradiction du même jour**,
deux lignes du même paramètre dans la table de §19, l'une prescrivant 8 et l'autre 1. **Ne le
désarme pas ; sache seulement que son plancher est 5, pas 0.**

`CLAUDE.md` est plafonné à **2 000 lignes**, contrôle F de `scripts/check_claude_md.py`. Un
dépassement n'est pas une faute : c'est le signal qu'une section mérite son propre dossier.
L'outil pour le faire proprement est `scripts/extraire_section.py` — il laisse un renvoi à la
place et **refuse de résumer tout seul**, parce qu'un résumé mécanique dirait ce que la
section *contient* et non ce qu'un agent doit en *retenir*.

---

## 2. ⚡ DÉMARRAGE — fais ces 4 choses, dans cet ordre, avant tout le reste

**Une seule commande fait les trois premiers points, et elle est à jour :**

```bat
C:\envs\certus\Scripts\python.exe scripts\preflight.py
```

Elle doit finir par `PREFLIGHT=GO`. Ce qui suit explique **ce qu'elle vérifie et pourquoi**,
à lire une fois.

**1. Vérifie que tu es dans le bon dossier.**

```bat
C:\envs\certus\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

Le chemin affiché **doit être dans l'arbre où tu édites**.
Si ce n'est pas le cas → **ARRÊTE-TOI. Signale-le. Ne modifie rien.**

🔴 **L'INTERPRÉTEUR N'EST PAS DANS LE DÉPÔT, ET CE DOCUMENT A PRESCRIT PENDANT DES JOURS UNE
COMMANDE QUI NE S'EXÉCUTE PAS.** 📏 Trouvé le 2026-08-19 en relisant ce fichier ligne à ligne :
`.venv\Scripts\python.exe` n'existe **pas** — le venv vit à `C:\envs\certus` depuis le
déménagement hors de Google Drive. **47 commandes réparties sur 10 fichiers** étaient donc
inexécutables, **à commencer par la toute première de ce §2**. Un agent neuf échouait à son
premier geste sans savoir pourquoi.

⚠️ **Et `preflight.py` aggravait le cas** : son contrôle exigeait `.venv` **dans le chemin**
de l'interpréteur, donc il rendait `[BAD]` pour le **seul** interpréteur correct. C'est la
même faute que `EXPECTED_ROOT` juste en dessous — coder en dur un **chemin** au lieu de
vérifier une **propriété**. Il teste désormais la présence d'un `pyvenv.cfg` à côté de
l'interpréteur, ce qui reste vrai où qu'on le pose.

🔑 **Si le venv bouge encore**, ne cherche pas un chemin dans un document : demande-le à
Python. `python -c "import sys; print(sys.executable)"` depuis l'environnement actif, ou
`preflight.py` qui le dit et le vérifie.

🔴 **Il n'y a PAS de racine attendue en dur, et c'est délibéré.** Ce document a longtemps
exigé `C:\dev\gemini` — **un dossier qui n'existe plus**, et la constante `EXPECTED_ROOT`
qui le portait dans `preflight.py` n'était lue par aucun contrôle. Une consigne qui
protégeait de l'erreur n°1 envoyait donc vers un dossier fantôme, en silence. Le projet vit
dans des snapshots datés copiés les uns depuis les autres (`0108`, `0807`, `1408`, …) : la
seule question qui survive à une copie est *« est-ce que `import certus` résout DANS l'arbre
courant ? »*

**2. Sais-tu si committer PUBLIE ?**

```bat
dir .git\hooks\post-commit*
git remote get-url origin
```

👤 a demandé le **2026-08-14** que le push soit **armé**. Donc `post-commit` sans suffixe est
l'état **voulu** : chaque commit pousse vers `github.com/nikonvr/CERTUS`, un dépôt **public**.
`--no-verify` ne l'arrête pas — il ne saute que `pre-commit` et `commit-msg`.

🔴 **Conséquence, et elle est permanente : commiter, c'est publier.** Rien qui porte une
donnée personnelle, un secret, ou l'œuvre d'un tiers ne doit entrer dans l'index. Le
2026-08-14 le dépôt portait encore un nom civil dans six fichiers Excel, un nom de session
dans 114 lignes de journaux, et le texte intégral d'une thèse tierce. Si 👤 demande un commit
**sans** pousser, désactive le hook **avant**, pas après.

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
C:\envs\certus\Scripts\python.exe -m ruff check .
C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Attendu : `All checks passed!` puis **zéro échec**.
Si un test est rouge **avant** que tu n'aies rien touché → **ARRÊTE-TOI et signale.**
Ce n'est pas à toi de le réparer.

🔴 **NE COMPARE PAS LE NOMBRE DE TESTS À UN CHIFFRE ÉCRIT ICI — COMPTE-LE.** Ce document a
porté successivement 2 300, 2 301, 2 310 et 2 450 pour la même commande, et **aucun de ces
chiffres ne survit à l'ajout d'un test**, c'est-à-dire à une journée de travail normale.
📏 Mesuré le 2026-08-19 : **2 453 tests collectés** au commit `ba7e118~1`, **2 456** après
l'ajout de trois tests le même jour — l'écart de 3 est exactement celui des trois ajouts.

```bat
C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov --collect-only
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

**4. Lis §29 et choisis UNE action. Une seule.**

---

## 3. ⚡ CARTE DU DOCUMENT — où aller selon ce que tu fais

| Tu veux… | Va où |
|---|---|
| 🚀 **Arriver sur le projet** | **[`docs/REPRISE.md`](docs/REPRISE.md)** — une page : les chiffres de référence, ce qui tourne, les cinq pièges, ce qui est faux dans les vieux documents |
| Savoir ce qui est interdit | §6 — les onze interdits |
| Savoir dans quoi tu vas tomber | §7 — les sept pièges |
| Savoir comment travailler | §9 — la boucle et la règle d'or |
| Comprendre un mot du projet | **§14 — vocabulaire.** 🔴 Y lire **QWOT ≠ point tournant** avant d'écrire sur les points d'arrêt |
| Toucher à du calcul optique | §16 — conventions physiques et oracle TMM |
| Comprendre la machine de dépôt | §17 — les spécifications du physicien |
| **Ce qu'on suppose de la machine** | **§18 — le modèle FIGÉ de la chaîne de lecture. Ne pas le rouvrir.** |
| **Comparer un résultat** | **§21 — les repères valides, tous fente 2 nm.** Ce qui les périme y est dit, et pourquoi ils ne se comparent pas entre composants |
| **Savoir ce qui est encore cassé** | **§24 — défauts ouverts. À lire avant toute action.** |
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
| **[`REPRISE.md`](docs/REPRISE.md)** | 🚀 en arrivant, toujours |
| [`CHANTIER_MULTITEMOINS.md`](docs/CHANTIER_MULTITEMOINS.md) | multi-témoins, 12 sous-sections. ⚠️ **Ce renvoi le disait « le programme courant » — il ne l'est plus depuis le 2026-08-19.** Le chantier vivant est [`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md) ; celui-ci est **acquis et consultable**, pas en cours |
| [`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md) | 🔑 **employer pleinement le Rate**, et mélanger POEM / niveau absolu / Rate. 📏 Son coût est une **pénalité de SEEL qui CROÎT avec la profondeur** — +1 % à 35 couches, +9 % à 48, +22 % à 75. ⚠️ Le « facteur 175 » d'une rédaction antérieure était un **paradoxe de Simpson**, retiré le 2026-08-19 |
| **[`CHANTIER_PREDICTIBILITE.md`](docs/CHANTIER_PREDICTIBILITE.md)** | 🔵 **ouvert par 👤 le 2026-08-17** — *prédire sans tout calculer si un design passe avec un seul verre témoin*. 🔑 À retenir sans l'ouvrir : **le 99c n'est PAS une référence valable** (tout QWOT ⇒ adverse à POEM par construction, réponse plate à 100 % qui ne discrimine rien) · **la série d'échelle du random75 ×0,5/×1/×1,5/×2 est la seule expérience CONTRÔLÉE du projet** · **quatre routes y sont déjà fermées par la mesure** · 🔴 **`search_resolution` était neutralisé dans toute la campagne des intervalles alors que 👤 l'a posé comme prérequis** · 🔴 **le mode `extreme` n'améliore le SEEL sur AUCUNE des configurations testées** (§4quater-bis, matrice arrêtée le 2026-08-19 sur décision de 👤 ; `deep` seul fait mieux à un cinquième du coût) |
| 🔴 **[`PLAN_PRODUCTION_2026-08-20.md`](docs/PLAN_PRODUCTION_2026-08-20.md)** | **LE PROGRAMME COURANT**, et il n'était cité nulle part dans ce fichier jusqu'au 2026-08-21. Ses **§15 à §24** portent tout ce qui est récent : le multiseed au criblage, l'injection de plans, la fermeture de la voie ELITE, la diversité en λ |
| ~~[`PLAN_2026-08-16.md`](docs/PLAN_2026-08-16.md)~~ | 🪦 **ARCHIVE.** Ce renvoi le disait « en cours d'exécution » — **faux depuis le 2026-08-20**. Sa campagne multi-témoins est close et le chantier est acquis. Gardé pour ses cinq pièges du 15 août |
| [`QWOT_ET_TURNING_POINT.md`](docs/QWOT_ET_TURNING_POINT.md) | 🔴 **obligatoire** avant d'écrire sur les points tournants |
| [`FEUILLE_DE_ROUTE.md`](docs/FEUILLE_DE_ROUTE.md) | ce qui est acquis (A1→A25), ce qui est outillé |
| [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) | les chantiers du modèle physique, 12.1 à 12.7 |
| [`SEEL.md`](docs/SEEL.md) | 🆕 extrait de §22 le 2026-08-19 : la définition, la règle de tri, le revirement 0,1 → 0,01 nm et son prix non mesuré, et le code mort de la seconde borne |
| [`CHANTIERS_OUVERTS.md`](docs/CHANTIERS_OUVERTS.md) | 🆕 extrait de §27 le 2026-08-19 : les deux propositions de 👤 non mesurées, isolation des tests, perf |
| [`ETAT_IMPLANTATION.md`](docs/ETAT_IMPLANTATION.md) | ce qui est **réellement** implanté, établi contre le CODE |
| [`COMPOSANTS.md`](docs/COMPOSANTS.md) | les quatre composants d'essai |
| [`DECISIONS_TRANCHEES.md`](docs/DECISIONS_TRANCHEES.md) | grille des λ, profondeur Monte-Carlo, les deux correctifs |
| [`PERFORMANCE.md`](docs/PERFORMANCE.md) | ⚡ ce qui a été mesuré, **y compris les pistes fermées** |
| [`ENONCE_PROBLEME.md`](reports/ENONCE_PROBLEME.md) | énoncé autonome, pour poser le problème à un tiers |

🔑 **La page qui compte, et 👤 l'a dit : `pages/CERTUS_STRAT.html`.**

> 👤 *« c'est strat.html le fichier ultra important. C'est lui qui convaincra les acheteurs
> potentiels du code ! »* (2026-08-14)

C'est une **vitrine commerciale et technique**, publiée sur un dépôt public. Elle ne contient
aucune instruction, et elle a un régime propre :

| | |
|---|---|
| **Une affirmation fausse y coûte plus qu'un manque** | Un évaluateur qui prend un chiffre en défaut cesse de croire le reste. Tout nombre doit être sourçable dans le code ou dans un artefact de `reports/`. |
| **La nuance juste convainc, le superlatif non** | « le meilleur partitionnement **mesuré** sur deux empilements » se défend ; « l'optimum universel » se réfute en une question. |
| **Elle doit montrer sa LIMITE** | §21.15 porte le 99 couches, dont **aucune stratégie ne survit** — plantage 100 %, et le 0,86 nm qui traîne est un **score de repli**. Un expert le trouverait de toute façon. |
| **Et ce qui lève la limite** | **§21.16 — multiple testglass**, ajoutée le 2026-08-15 : le même 99 couches devient fabricable, **0,81 nm** à 0 % de plantage. ⚠️ Le `0,782` était le plus **favorable de trois graines** (0,782 / 0,816 / 0,839) — corrigé le 17/08. Elle dit aussi les trois attentes que la mesure a **démenties**, et ce qui n'est **pas** revendiqué (borne supérieure, une seule graine). |
| **Vérifie la STRUCTURE après toute édition** | Le 2026-08-14 un `</ul>` supprimé faisait rendre 400 lignes à l'intérieur d'une liste, et avait emporté une puce entière. Passe `html.parser`, ne te fie pas à l'œil. |

Les autres pages de `pages/` (14 fichiers : DESIGN, INDEX, FIELD, HUB, RE, METAL, métrologie…)
et les rapports de `reports/*.html` existent aussi. ⚠️ Ceux de `reports/` **ne chargent aucun
moteur mathématique** : tout `$...$` y sort en texte brut.

---

## 4. Vérifier l'environnement — une minute, non négociable

```bat
C:\envs\certus\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
dir .git\hooks\post-commit*
```

- Le chemin affiché **doit** être dans le dépôt que tu as ouvert. 🔴 **Plusieurs copies de
  ce dépôt coexistent sur la machine.** Si le chemin pointe ailleurs, tu modifies un dossier
  et tu en mesures un autre : tout ce que tu constateras sera faux, **sans le moindre message
  d'erreur**. C'est le piège n° 1 du projet et il est invisible. **Arrête-toi.**
  ⚠️ Ce document a longtemps exigé `C:\dev\gemini` ; ce chemin **n'existe plus** et la
  consigne envoyait vers un dossier fantôme. **Aucune RACINE DE DÉPÔT n'est écrite en dur**,
  ici ni ailleurs — c'est délibéré, et `scripts/preflight.py` le vérifie par une propriété
  (*« `import certus` résout-il dans l'arbre courant ? »*), jamais par un chemin.
  🔴 **Ne confonds pas avec l'INTERPRÉTEUR, qui lui EST écrit en dur** — `C:\envs\certus`,
  depuis le 2026-08-19. Ce n'est pas un oubli : une commande doit être **copiable-collable**,
  et le venv vit hors du dépôt donc aucun chemin relatif ne le désigne. Les deux régimes
  diffèrent parce que la racine **change à chaque snapshot** alors que le venv est **unique
  sur la machine**. ⚠️ S'il déménage à son tour, `coherence_md.py` le dira au premier
  passage : son contrôle E exige que tout interpréteur cité **existe**.
- 🔴 **Le hook `post-commit` est ARMÉ, et c'est voulu.** 👤 l'a demandé le 2026-08-14.
  **Tout commit pousse vers le dépôt PUBLIC `nikonvr/CERTUS`**, et `--no-verify` ne l'en
  empêche pas. Ce n'est pas un accident : c'est le mode de travail choisi. ⚠️ Vérifie-le
  avant de committer quoi que ce soit de sensible.
  Le fichier `post-commit.DESACTIVE` est l'ancienne version inerte, gardée à côté.
  ⚠️ Ce paragraphe ordonnait l'inverse — *« ne le réactive jamais »* — jusqu'au 2026-08-16 :
  il décrivait un état contraire au réel depuis deux jours.

### Commandes de référence

Toutes depuis la racine du dépôt, toujours avec `C:\envs\certus\Scripts\python.exe` — jamais `python`
nu, qui prendrait l'interpréteur système sans les dépendances.

| But | Commande | Durée |
|---|---|---|
| Tests du noyau | `C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov` | **216,69 s** mesuré le 2026-08-19 à 15:16, i5-8250U, cache **chaud** — `2451 passed, 5 skipped` à cet instant, soit **deux tests avant l'état actuel**. À cache **froid**, 784 s |
| Suite complète | `C:\envs\certus\Scripts\python.exe -m pytest tests/ -q --no-cov` | ~1 h 45 |
| Lint | `C:\envs\certus\Scripts\python.exe -m ruff check .` → `All checks passed!` | ~10 s |
| Run STRAT complet | `C:\envs\certus\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42` | ~25 min |
| Idem, seuil injecté | `... probe_anchor_noise_pipeline.py full 1.0 42 0 2.1` | ~25 min |
| Sonde noyau rapide | `C:\envs\certus\Scripts\python.exe scripts\probe_anchor_noise.py` | ~1 min |
| Banc sur exemples réels | `C:\envs\certus\Scripts\python.exe scripts\bench_examples.py <module> --auto-yes` | variable |

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
   📏 **Remesuré le 2026-08-19, et le tableau s'est INVERSÉ** : **2 266 fichiers**, dont
   **2 067 suivis par git**. La ligne d'avant disait *« 33 suivis sur 226, les 193 autres
   irrécupérables »* — le dossier a été **multiplié par dix** et l'essentiel est désormais
   versionné. ⚠️ **L'interdit tient quand même** : **199 fichiers restent hors de git**, un
   nombre à peu près inchangé (193 → 199). Ce sont eux qui sont irrécupérables, pas le
   dossier entier. 🔴 **Ne recopie aucun de ces quatre nombres : recompte-les**
   (`git ls-files reports | wc -l`).
4. **Ne modifie `example/example_strat/JSON-strat-example.json` que pour DURCIR.**
   Il s'est écarté des valeurs correctes **quatre fois**, toujours dans le sens
   **permissif**, et chaque fois cela a coûté une session de diagnostic. C'est le sens
   qui est interdit, pas l'écriture.
   ✅ **Amendé le 2026-08-12 sur instruction 👤** : *« tous les paramètres doivent être
   dans les JSON, celui du 48 couches et celui du 35 couches — les paramètres
   d'activation des différentes sources d'erreur, ainsi que le mode rate »*. Les deux
   fichiers portent donc désormais **explicitement** les onze réglages du modèle, au
   lieu de dépendre de défauts codés. Un fichier de configuration doit décrire la
   machine sur laquelle il tourne, sinon le run n'est comparable à rien (§24-7).
   ⚠️ Pour essayer autre chose, `scripts\probe_anchor_noise_pipeline.py` injecte les
   paramètres **après coup** — c'est toujours la voie à préférer.

5. **Jamais « corriger » `except A, B:`.** C'est la syntaxe PEP 758, valide depuis
   Python 3.14, utilisée volontairement dans **18** modules (compté par AST le 2026-08-19,
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
- ~~**Tirer une conclusion physique d'un empilement autre que le 48 couches.**~~
  🔴 **SUPPRIMÉE le 2026-08-16.** Le projet a **quatre** composants d'essai et le random75
  existe précisément pour tirer des conclusions **générales**. La règle était violée par
  construction. **Ce qui la remplace :** une règle n'est établie que si elle survit sur un
  empilement **sans structure** — ni cavité, ni miroir, ni périodicité. C'est ce test qui a
  réfuté « le témoin vieillit et meurt » et qui laisse `S(p−1)` **non validée**.
- **Raffiner la grille d'échantillonnage sans corriger le seuil** — voir [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.2.
- **Modéliser σ(T), la grenaille ou le bruit multiplicatif** — voir §17.

---

## 9. La boucle de travail

Pour **chaque** action, dans cet ordre, sans en sauter :

1. **Lis l'action dans son dossier** — [`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md) pour le
   chantier vivant, [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) pour le modèle physique,
   [`CHANTIERS_OUVERTS.md`](docs/CHANTIERS_OUVERTS.md) et
   [`RESERVE_A25_A27.md`](docs/RESERVE_A25_A27.md) pour le reste. Si quelque chose est ambigu,
   **arrête-toi et demande.** Un plan ambigu est un défaut du plan, pas une invitation à
   inventer. ⚠️ *Ce point renvoyait à « §17 », qui est la fiche de la machine réelle et n'a
   jamais porté d'action.*
2. **Fais la modification la plus petite possible.** Une seule chose à la fois : si tu
   changes deux choses et que le résultat bouge, personne ne saura laquelle en est cause.
3. **Tests** : `C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov`. Un échec ⇒ n'avance pas.
4. **Lint** : `C:\envs\certus\Scripts\python.exe -m ruff check .` doit dire exactement `All checks passed!`
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
2. ✅ **Le constat §24-1 est définitivement innocenté.** L'écart de 2,5e-11 que j'avais pris
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
affirmations fausses la première fois et neuf la seconde (§24) — il fonctionne.

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
   de banc. C'est ainsi que le constat §24-1 a été écrit puis retiré : il accusait le code
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
  de §21 ont été mesurés sous **3.14.6**. Toute mesure rapportée doit porter sa version
  d'interpréteur, sinon un écart de version sera attribué au code.
- Cible principale Windows, build gelé PyInstaller
- 📏 **Mesuré le 2026-08-19**, et les trois chiffres qui figuraient ici étaient faux :
  **171 600** lignes de source (`certus/` + les 12 fichiers de la racine, 294 fichiers) ·
  **62 146** de tests (261 fichiers) · **21 687** de scripts (97 fichiers) ·
  **2 456** tests collectés sur `tests/oracle/ + tests/unit/`.
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
  HTML de déterminations d'indice. **199 fichiers sur 2 266 sont hors de git** (mesuré le
  2026-08-19) et sont irrécupérables — voir interdit 3, qui porte les chiffres.
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
(`certus_strat_growth.py:1398`, fenêtre `[i−k+1 … i]` — c'est §24-3). 🟢 **Ce n'est pas
disqualifiant ici, et voici pourquoi** : le signal propre de cette sonde est **plat**, donc les
deux lissages rendent le même bruit lissé — même variance `σ/√k`, seule la phase diffère. Le
décalage de `(k−1)/2` que §24-3 dénonce ne mord que pour **localiser** un extremum sur un signal
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
| `tp_hysteresis_factor` | 🔴 **DEUX VALEURS, ET LA TABLE N'EN DONNAIT QU'UNE.** **Valeur EN USAGE : 1,66** — c'est ce que portent **les 14 configurations réelles**, vérifié le 2026-08-19. **Valeur CIBLE : 1,00**, mesurée à `k = 8` et `N = 800`. ⚠️ *Cette ligne annonçait « **1,00** — ni 0,354 ni 1,66 », donc elle prescrivait une valeur qu'aucune configuration n'utilise, en niant celle qui tourne réellement. Le §20, lui, disait correctement « vaut 1,66 aujourd'hui, cible 1,00 ».* Le `1/√k` = 0,354 reste **réfuté** (il laisse **100 %** de points tournants fabriqués). 🔴 **Et la cible n'est pas applicable telle quelle** : elle a été mesurée à `k = 8`, or les 14 configurations tournent à `k = 1`. La valeur dépend de `N` autant que de `k` — **remesure avant de l'appliquer** | §18-4, A1 |
| Retard de déclenchement | **aucun** — ne rien ajouter | §18-5 |
| `phase_a_level_margin_factor` | **1,66** actuel, **3,33** à évaluer | §18-6 |
| Quantification de l'arrêt | `U(0 ; 0,125 nm)` | §18-7 |
| `index_corridor` | **0,005**, unités d'indice **absolues**, demi-largeur — 👤 **ACTIF PAR DÉFAUT** | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.3 |
| `photometric_curvature_amp` | **0,00375** ⇒ à `T = 0,5` la vraie valeur est dans `[0,4975 ; 0,5025]` à 2 σ. 👤 **ACTIF PAR DÉFAUT** | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1bis |
| `allow_rate` | **vrai** — 👤 *« c'est le cas général »* | §22 |
| `slit_bias_enabled` | **vrai**, fente nominale **2 nm** — 👤 *« réaliste, pas optimiste »* | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.7 |
| `affine_scale_amp` | **0,05** ⇒ `a ∈ [0,95 ; 1,05]` | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1 |
| `affine_offset_amp` | **0,02** ⇒ `b ∈ [−0,02 ; +0,02]` | [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1 |
| Plafond du banc | `CERTUS_BENCH_TIMEOUT_S=5400` | §21 |
| Graine de référence | **42**, `scan_wl_step` **1.0** | §21 |
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
| `tp_hysteresis_factor` | Seuil de détection d'un point tournant, en multiples de `A = trigger_tolerance/100`. Vaut **1,66** aujourd'hui. 🔴 **Valeur cible : 1,00**, **mesurée** à `k = 8`, `N = 800` (A1). L'ancienne cible **0,354** = `1/√k` est **RÉFUTÉE** : elle applique un critère *par échantillon* à un extremum courant sur `N` échantillons, et laisse **100 %** de points tournants fabriqués — §18-4. Injectable en 5ᵉ argument du script de sonde. |
| `reading_smoothing_window` | ⚠️ **Existe depuis `e0df0e1`**, défaut **1**. Fenêtre de moyenne glissante appliquée au signal de monitoring avant détection, **en lectures machine**. Valeur du modèle figé : **8** (2 s à 4 Hz). 🔴 **Dans l'implantation actuelle ce drapeau commande AUSSI la grille de [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.4** — voir §24. |
| `index_corridor` | ⚠️ **Existe depuis `162a0ff`**, défaut **0,0**. Demi-largeur du corridor d'incertitude d'indice, en **unités d'indice absolues**. Valeur du modèle : **0,005**. Jamais mesuré. |
| `affine_scale_amp` / `affine_offset_amp` | ⚠️ **Existent depuis `f7a3d71`**, défaut **0,0**. Amplitudes du tirage de dérive photométrique, une fois par run. Valeurs de mesure : **0,05** et **0,02** ([`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1). Jamais mesurées. |
| `poem_enabled` | ⚠️ **Existe depuis `f7a3d71`**, défaut **vrai**. Force le repli absolu quand il est faux. C'est le drapeau que [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1 réclamait. Jamais mesuré. |
| `phase_a_level_margin_factor` | Marge exigée **en transmission** entre le niveau d'arrêt et les points tournants voisins. Active aussi la vraie matrice cumulée en Phase A. |
| `dp_yield_weight` | Poids du rendement dans l'objectif DP : `coût = coût_nm + w·(−log(1−p))`. |

---

## 21. Points de référence — les quatre repères valides, et ce qui les périme

🟢 **LES REPÈRES EXISTENT DEPUIS LE 2026-08-15.** Voici les quatre, tous mesurés **fente
2 nm**, donc sous le modèle courant. Ce sont eux qu'on cite, et aucun autre.

| composant | couches | SEEL | plantage | condition |
|---|---|---|---|---|
| dichroïque `JSON-strat-example` | 48 | **0,173 nm** | 0 % | 6 blocs, une seule campagne |
| passe-bande 3 cavités `JSON-strat-bandpass-3cav` | 35 | **0,482 nm** | 0 % | 6 blocs, mode DEEP |
| **aléatoire** `JSON-strat-random75` | 75 | **0,272 nm** | 0 % | une seule campagne, 241/662 déposables |
| passe-bande 5 cavités `JSON-strat-bandpass-5cav-99c` | 99 | **0,81 nm** | 0 % par campagne | 🔴 **4 verres témoins** — 0-22 / 22-42 / 42-76 / 76-99 · ⚠️ moyenne de **trois graines** (0,782 / 0,816 / 0,839) ; ne cite jamais le 0,782 seul |
| le même, **en une seule campagne** | 99 | *aucun score valide* | **100 %** sur 487 stratégies | non fabricable — §23.8 |

🔑 **Lis la troisième et la quatrième ligne ensemble : 75 couches passent, 99 non.** Ce n'est
donc **pas la longueur** qui met le monitoring optique en échec, c'est la **structure**. Le
random75 n'a ni cavité ni miroir, le 99c a cinq cavités et des miroirs de 19 couches.
Voir §23.4.

⚠️ **Cette ligne disait « cinq espaceurs à swing nul et des miroirs sous 10⁻⁴ » — c'est
réfuté.** Mesuré le 2026-08-15 : les cinq espaceurs offrent **65 à 133 λ utilisables** chacun,
et **aucune des 99 couches n'est muette**. Le swing crête-à-crête d'une demi-onde n'est pas
nul ; c'est son écart début-fin qui l'est, et ce n'est pas la même grandeur. Ce qui met le
99c en échec est la **marge** du sursaut face à l'hystérésis, pas l'absence de signal.

#### 🔴🔴 LA SÉRIE D'ÉCHELLE DU RANDOM75 MESURAIT LA RECHERCHE, PAS LA PHYSIQUE — 2026-08-18

📌 **Le dossier fait autorité : [`CHANTIER_PREDICTIBILITE.md`](docs/CHANTIER_PREDICTIBILITE.md)
§4quater et §4quinquies.** Ce qu'il faut retenir sans l'ouvrir :

| Σ QWOT | variante | offertes | déposables | `crash_min` | SEEL |
|---|---|---|---|---|---|
| 57,4 | ×0,5 | 375 | 0 | 48 % | — |
| 114,9 | ×1 | 662 | 241 | 0 % | 0,272 nm |
| 172,3 | ×1,5 | 440 | 1 | 0 % | 0,633 nm |
| 201,1 | **×1,75** | 746 | **282** | 0 % | **0,528 nm** |
| 229,8 | ×2 | 404 | 0 | **100 %** | — |
| 229,8 | ×2 **en `deep`, fente 1 nm** | 1 986 | **277** | **1,0 %** | **0,625 nm** |
| 229,8 | le même **en `extreme`** | 2 945 | 254 | 1,0 % | 0,629 nm ⚠️ *ce tableau ne portait QUE cette ligne, et créditait donc `extreme` d'un déblocage que **`deep` seul fait mieux, à un cinquième du coût*** |

🔑 **Deux faits, et ils changent la lecture de tout ce chantier :**

1. **`×1,75` est PLUS ÉPAIS que `×1,5` et rend 282 déposables contre 1.** Il n'y a pas de loi
   « plus c'est épais, plus c'est dur ».
2. 📏 Sur les cinq points au **même protocole**, la corrélation de rang avec le nombre de
   déposables vaut **+0,103 pour Σ QWOT** — la propriété du design — et **+0,975 pour le nombre
   de stratégies OFFERTES** par la recherche. Et la flèche causale est établie : **même design,
   même graine, même fente**, seule la largeur de recherche change, et ×2 passe de **0/404** à
   **254/2 945**.

🔴 **Donc un `crash_min = 100 %` ne dit PAS, à lui seul, « ce composant n'est pas
monitorable ».** Il peut dire « ma recherche n'a pas proposé ce qui marche », et **rien dans la
sortie ne distingue les deux**. C'est le défaut §24-37 dans l'autre sens, et il a fait croire
trois jours durant que ×2 était impossible.

🔑 **MAIS LA RÉCIPROQUE EST FAUSSE AUSSI, et elle a été mesurée le 2026-08-19 au soir.** Un
`100 %` qui **résiste à la profondeur** dit, lui, quelque chose de réel : sur `r75x2` à 2 nm,
`fast` (404), `premium` (651) et `deep` (**1 617** stratégies) rendent **tous les trois 0
déposable et 100 %**. **À cette fente, ce n'est plus la recherche qui manque.** La bonne règle
est donc : *un `100 %` en `fast` ne conclut rien ; un `100 %` qui tient jusqu'à `deep` est un
constat sur le composant et sa fente.*

⚠️ **L'offre ne suffit pas pour autant, et la mesure du 2026-08-19 au soir le tranche.**
Cette ligne disait *« il a fallu la fente fine ET l'élargissement »* : **c'est l'élargissement
qui est de trop**. 📏 À **2 nm**, la recherche a été poussée jusqu'à `deep` — **1 617
stratégies, 0 déposable, 100 % de plantage** — donc quadrupler l'offre (404 → 1 617) ne change
**rien**. Et à **1 nm**, `deep` **seul** rend 277 déposables. **Il a donc fallu la FENTE FINE
et la PROFONDEUR**, pas l'élargissement.

#### 🟠 CES QUATRE SEEL NE VIVENT PAS SUR LE MÊME DOMAINE SPECTRAL — constaté le 2026-08-15

👤 : *« on reste comme cela, mais c'est à noter dans un coin »*. C'est donc **un état de fait
assumé, pas un défaut à corriger** — mais il faut le savoir avant de lire le tableau ci-dessus
comme un classement de difficulté.

| composant | grille de notation | largeur | points |
|---|---|---|---|
| 48c dichroïque | 400 – 700 nm | **300 nm** | 301 |
| 75c aléatoire | 550 – 750 nm | **200 nm** | 201 |
| 35c passe-bande | 600 – 660 nm | **60 nm** | 61 |
| 99c passe-bande | 610 – 655 nm | **45 nm** | 91 (pas de 0,5 nm) |

**Les deux passe-bandes sont déjà notés en zone réduite** — leur configuration resserre la
plage autour de la bande. Les deux autres sont notés large. Donc l'ordre
`0,173 < 0,272 < 0,482 < 0,81` mélange **deux effets** : la difficulté intrinsèque du
composant, **et** la largeur de la fenêtre où l'erreur est regardée. Une bande étroite autour
d'une résonance concentre le score là où le filtre est le plus sensible ; une grille large
dilue la même erreur dans des zones plates.

🔑 **Ce qui reste parfaitement valide malgré ça** : toute comparaison **à composant fixé** —
c'est-à-dire tout ce que fait la campagne du 2026-08-15, où seule la position du changement de
témoin varie sur une grille inchangée. L'avertissement ne porte que sur les comparaisons
**d'un composant à l'autre**.

**Comment c'est calculé, exactement.** Deux grilles à ne pas confondre :

| paramètre | rôle |
|---|---|
| `wl_range_start` → `wl_range_end`, pas `wl_step` | la grille de **notation** : c'est sur elle que RMSE et SEEL sont calculés |
| `scan_wl_min` → `scan_wl_max` | la grille de **balayage** : les λ de contrôle candidates. Aucun effet sur le score |

La pondération spectrale **existe** (`compute_batch_rmse`, argument `weights`,
`certus_strat_batch.py:554`) : on déclare des zones via `params["targets"]`, chaque point reçoit
`poids utilisateur × quadrature en d ln λ`, et **un point hors de toute zone reçoit un poids
nul** — il ne compte même pas au dénominateur. 🔴 **Mais aucune des quatre configurations ne
définit `targets`**, donc le code retombe sur son repli documenté `rank_weights = None` :
**pondération UNIFORME sur toute la grille**. Le mécanisme est écrit et testé, il n'a
simplement jamais servi sur ces composants.

📌 **Si un jour on veut une zone (par exemple 550-650 nm)** : passer par `targets`, pas par
`wl_range`. Changer `wl_range` déplacerait aussi la cible nominale et rendrait tout
incomparable avec les mesures existantes ; `targets` pondère sans changer la grille.

⚠️ **Le 0,86 nm des anciens rapports sur le 99c est un score de repli, pas une performance**
— il est rendu quand aucune stratégie ne survit à la porte de plantage. Comparer deux configurations sur des scores de repli revient à comparer
deux façons d'échouer. Voir §23.8.

🔴 **Ce qui PÉRIME un repère.** Le **biais de fente** est actif par défaut depuis le
2026-08-11 (§30). Tout `RESULT` mesuré **avant** cette date décrit une machine à fentes
**infiniment fines**, qui n'existe pas. Ce ne sont pas des chiffres faux : ce sont les
**réponses à une autre question**.

**Sont donc périmés, et il ne faut plus les citer** : l'ancien `D0.ref`
`0.0027329534107462224`, la courbe de corridor, la protection POEM ×41,2, la position de la
falaise, et toute statistique par bande antérieure.

⚠️ **`RESULT` agrège les trois niveaux de bruit** (0,5× / 1× / 2×). Il est donc comparable
aux **scores** du classement, et **jamais** aux statistiques **par bande**, qui sont au niveau
nominal seul. `RESULT` **est** le `robustness_score` de la gagnante.

🔴 **Et un `RESULT` seul ne départage rien.** §24-26 l'a mesuré : à N = 150, la dispersion
Monte-Carlo vaut σ ≈ 6 % et l'écart entre la 1ʳᵉ et la 2ᵉ vaut 0,8 σ. **Deux runs qui
diffèrent de moins de ~8 % sont indiscernables.** Ce qui compare deux configurations, c'est
la **classe d'équivalence SEEL** (§22), pas le score.

**Ce qu'il faut faire avant toute mesure au banc :**

```bat
set CERTUS_BENCH_TIMEOUT_S=5400
C:\envs\certus\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

Le plafond était en dur ; il est désormais surchargeable par cette variable d'environnement,
défaut inchangé à 1800 s. **Mets 5400 et laisse finir.**

⚠️ **Le piège, et il a fonctionné deux fois** : au-delà du plafond le banc ne signale pas
d'erreur bruyamment. Il émet `RESULT=None` et un tableau de 12 stratégies au lieu de 345 —
**cela ressemble à un résultat**. Vérifie toujours `WAIT_EXIT` et le nombre de stratégies
avant de lire un `RESULT`.

⚠️ **Une mesure, une machine.** Ne lance rien d'autre pendant un run : ni tests, ni lint, ni
recherche récursive. Le pipeline sature tous les cœurs en `prange`.

**Suite de tests, mesurée sur cette copie le 2026-08-08** :

```
pytest tests/oracle/ tests/unit/ -q --no-cov  ->  0 failed
ruff check .                                  ->  All checks passed!
```

⚠️ Des documents supprimés annonçaient 2300 et 2301, avec la **même durée au centième**
(`87.60s`) dans cinq entrées différentes. Ces lignes n'avaient pas été mesurées.

🔴 **Et la phrase qui suivait était fausse : elle disait « la référence est 2310 », six
lignes après un bloc annonçant 2450 pour la même commande.** Deux chiffres contradictoires
dans la même section.

🔑 **La leçon a été tirée le 2026-08-19, et elle est plus forte que la correction** : ce
document a porté **2 300, 2 301, 2 310 puis 2 450** pour la même commande, et **chacun a été
faux à son tour**. Ce n'est pas une suite d'inattentions — c'est qu'**un compte de tests se
périme dès qu'on ajoute un test**, donc dès qu'on travaille. 📏 Le 2026-08-19 il valait
**2 453** puis **2 456** dans la même journée. **Le chiffre est retiré au profit du seul
critère qui survive : `0 failed`.** Voir §2.

⚠️ **Une durée sans sa machine ne vaut rien.** Le bloc ci-dessus portait un `101.24s` qui
n'est reproductible **sur aucune machine connue du projet** : la même commande rend **216,69 s**
sur i5-8250U à cache chaud (mesuré le 2026-08-19) et **784 s** à cache froid. La durée a été
retirée du bloc plutôt que corrigée — c'est le critère `0 failed` qui compte, et une durée
n'a de sens qu'accompagnée du processeur, du cache et de la charge.

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

📌 **Le chantier VIVANT est [`docs/CHANTIER_RATE.md`](docs/CHANTIER_RATE.md)**, et
c'est lui qui fait autorité depuis le 2026-08-19. Les quatre acquis du jour, sans ouvrir le
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
| **où le solveur ESSAIE le Rate** | la **dernière couche de chaque bloc** (`_rate_candidate_layers`, `certus_strat_robustness.py:596` au 2026-08-19). ⚠️ *Le renvoi disait `:513` — mes éditions du jour l'avaient décalé de 83 lignes. **Cite la FONCTION, le numéro n'est qu'un raccourci.*** Critère de **coût**, pas de nécessité : à une frontière de bloc les ancres sont perdues de toute façon |
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
chantier vivant est [`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md) ; celui-ci est **acquis et
consultable**. Deux sections du même document se déclaraient « courantes », ce que la carte du
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

## 24. Défauts ouverts, et constats qui gouvernent

Trouvés en appliquant §12. **Ce qui a été vérifié et qui tient est sorti de ce document** —
`git log` le garde. Ne restent ici que les défauts **encore ouverts**, c'est-à-dire du
travail à faire.

🔴 **Portée de la vérification, pour ne pas s'y tromper** : tout ce qui suit vient de la
lecture des diffs, du code et des artefacts committés, plus `ruff` et la suite de tests.
**Aucune mesure au banc n'a été relancée** — ni T0, ni aucune non-régression. Les
constatations chiffrées ci-dessous portent sur des **artefacts existants**, pas sur des runs
neufs.

### 🔴 Ne tient pas

| # | Ce qui a été trouvé |
|---|---|
| 49 | 🔴 **`search_resolution` ÉTAIT NEUTRALISÉ DANS TOUTE LA CAMPAGNE DES INTERVALLES, alors que 👤 l'a posé comme PRÉREQUIS.** `certus_strat_robustness.py:868` : *« ON BY DEFAULT since 2026-08-12 — 👤 "the slit is systematically searched, it is a **PREREQUISITE**". A strategy that does not carry its own slit is not executable in the chamber […] **the historical path is `search_resolution: false`** »*.<br>Or `mesurer()` de `scripts/campagne_intervalles.py` force `search_resolution: False` et épingle **2 nm** — et `JSON-strat-bandpass-5cav-99c.json` porte pourtant `search_resolution = 1`. **Les 272 intervalles du cache premium et les 751 stratégies du 2026-08-17 ont donc tourné sur une machine où l'opérateur n'a pas le droit de toucher à la fente**, c'est-à-dire le régime que 👤 avait écarté comme non exécutable en salle.<br>📏 Mesure du 2026-08-12 citée dans le même docstring : la règle `slit <= res_limit` rejette **31 % des paires (couche, λ) à 5 nm, 14 % à 2 nm, 2 % à 1 nm, 0,5 % à 0,5 nm** — passer de 2 à 1 nm **divise le rejet par 7**.<br>🔑 Et l'effet n'est pas le choix à quatre valeurs : *« the slit changes WHICH WAVELENGTHS ARE GOOD »*. Une λ en zone lisse tolère 5 nm et encaisse le bonus de bruit **÷1,5** ; une λ de bord de bande exige 1 nm et paie le **×2**. **C'est un arbitrage, pas un gain gratuit.**<br>⚠️ **Et aucune sonde statique n'applique la fente** — `profil_monitorabilite.py` et `probe_distance_extremum.py` tournent à résolution **infinie**. Elles surestiment donc le swing, et le plus fortement sur les empilements **épais**. 📌 Détail et plan de test dans [`CHANTIER_PREDICTIBILITE.md`](docs/CHANTIER_PREDICTIBILITE.md) §5. |
| 53 | 🔴 **LE LOGGER `ThinFilm` EST MUET — donc tout `logger.info` de `certus_strat_ranking.py` est PERDU.** 📏 Mesuré le 2026-08-21 : sa ligne inconditionnelle `Mining: n_blocks=...` apparaît **zéro fois** dans les journaux de campagne, alors que le logger `W{n_blk}` du worker passe. Un run de 50 min a été rendu **ininterprétable** faute de pouvoir distinguer « la passe n'a pas tourné » de « chaque candidate était infaisable ». Même motif que §24-37. 🔑 **Règle : un instrument dont la sortie n'atteint pas le RÉSULTAT n'est pas un instrument** — journalise depuis le worker, ou remonte des compteurs. Détail en §27 de [`PLAN_PRODUCTION_2026-08-20.md`](docs/PLAN_PRODUCTION_2026-08-20.md). |
| 54 | 🔴 **RESTREINDRE LA PLAGE DE BLOCS PAR `iter_divider_start/end` VIDE LA DP.** 📏 Mesuré le 2026-08-21 sur `r75x2` : à plage restreinte, `Mining found` vaut **1 à 2** par nombre de blocs et le compteur de couverture rend `0 λ déjà employées` — donc **aucun groupement rendu par le solveur** ; les 1 à 2 stratégies viennent des graines structurées. À plage **complète**, le même bloc 9 en mine **601**. ⚠️ **Conséquence : toute mesure comparative de la RECHERCHE se fait à plage complète.** Restreindre économise du temps en détruisant l'objet mesuré — et cela affaiblit les contrôles négatifs faits ainsi (§27 du plan de production). La cause exacte n'est **pas** établie : les libellés parlent de diviseurs de complexité, pas de sélection de plage. |
| 46 | 🔴 **UN VERDICT D'INTERVALLE N'EST PAS DÉTERMINÉ PAR UNE GRAINE, et le basculement est CATÉGORIEL.** 📏 Mesuré le 2026-08-17 sur le 99c, même intervalle, même machine, `robustness_seed` seul change :<br>`[38,99)` 61c **graine 42** → `AUCUNE_DEPOSABLE`, **0/452**, `crash_min` **42,0 %**, meilleure RMSE `0.18817`<br>`[38,99)` 61c **graine 77** → `DEPOSABLE`, **70/521**, `crash_min` **0,0 %**, meilleure RMSE `0.18777`<br>✅ **Contrôle 1 de §12 passé** : à graine 42, deux commits différents (`7564c78`, `817bc76`) rendent **les mêmes nombres**, RMSE comprise. Le basculement vient de la graine, pas du code.<br>🔑 **L'effet se compose** : la graine change le bruit → les choix de Phase A → **la population de stratégies elle-même** (452 contre 521). Ce ne sont pas les mêmes stratégies notées autrement. Même classe que l'invariant de [`DECISIONS_TRANCHEES.md`](docs/DECISIONS_TRANCHEES.md) — *la réalisation ne doit pas décider quelles candidates existent* — mais sur l'axe de la graine.<br>⚠️ **Portée** : les 263 entrées du cache premium sont toutes à `robustness_seed = 42`, et le **0,782 nm à 4 témoins** en descend. Cela ne le rend pas faux — cela veut dire qu'**une graine ne l'établit pas**. `--graine` est exposée (`4906252`) et écrit **à côté** (suffixe `_sNNN`), donc le contrôle coûte quelques heures et zéro risque.<br>🟢 **Nuance mesurée le même jour** : sur des intervalles **confortables** (`[0,22)`, `[22,42)`, 100 % de déposables aux deux graines) le verdict ne bouge pas et le score se tient à ~12 %. **La graine décide là où l'intervalle est marginal, pas partout.** |
| 47 | 🔴 **LE CONSENSUS EST DÉCOUPLÉ DE `robustness_seed` DÈS QUE `consensus_seed_list` EST RENSEIGNÉE — donc un balayage de graine n'est que PARTIEL.** `_resolve_consensus_seeds` (`certus/core/certus_strat_consensus.py:111`) : la liste explicite gagne, et `base_seed` n'est consulté qu'en son absence. Le 99c porte `consensus_seed_list = 41,42,43,44,45` avec `consensus_num_seeds = 3` → le consensus tourne sur **`[41, 42, 43]`**, identiques dans le run à graine 42 **et** dans celui à graine 77. Il n'a jamais vu 77.<br>✅ **Et il n'aurait rien stabilisé de toute façon** : le code le dit lui-même (`certus_strat_robustness.py:2162`) — *« consensus rescoring … only reads `robustness_score` »*. Il réécrit le score des `consensus_top_k`, **jamais `crash_rate`**. Donc `n_deposables` et `crash_min` sont **mono-graine par construction**.<br>Même famille que §24-18 : le chemin consensus porte une configuration que les surcharges n'atteignent pas. ⚠️ §24-18 ne mord pas sur cette configuration, où `consensus_num_runs` et `robustness_num_runs` valent tous deux **150** — la coïncidence masque le piège, elle ne le désarme pas.<br>🔴 **CONFIRMÉ SUR UN SECOND COMPOSANT LE 2026-08-19, et la signature est nette.** Sur `r75x2`, même configuration, `robustness_seed` 42 contre 77 : le **plantage** bouge (4,00 % ↔ 2,00 %) et la couche critique aussi (39 ↔ 32), mais les **scores** sont identiques à **3,2e-11** — l'ordre de la gigue de recompilation, c'est-à-dire rien. ⚠️ **Le piège de lecture est là** : des SEEL identiques sur deux graines ressemblent à une confirmation de robustesse. **C'est l'erreur n° 4 du §5** — un chiffre qui ne varie pas avec ce qui devrait le faire varier. 🔑 **Ce qui sonde vraiment la dispersion est un changement de TRIPLET de graines de consensus, pas de `robustness_seed`.**<br>✅ **FAIT dans la nuit du 2026-08-19 au 20, et c'est la première mesure du bruit du SEEL sur ce composant.** Trois runs identiques en tout sauf le triplet : `41,42,43` → **0,6885** · `51,52,53` → **0,6679** · `61,62,63` → **0,6774**. Étendue **3,10 %**, soit σ ≈ 1,83 % (E[étendue]/σ = 1,693 à n = 3), donc **2,59 % sur une différence de deux SEEL**.<br>🔴 **Conséquence immédiate, et elle va dans le sens inverse de la prudence attendue** : le σ que l'on empruntait à §24-26 (mesuré sur le **48 couches**) valait 7,3 % sur une différence — **trop grand d'un facteur 2,8**. Il faisait déclarer « indiscernables » des coupures qui le sont à 3,53 σ et 2,58 σ. **Un bruit emprunté à un autre composant ne vaut rien, ni pour affirmer ni pour refuser.**<br>🟢 **Et ce qui ne bouge d'aucun triplet à l'autre** : le plantage (`4,00 %` dans les trois) et l'identité de la gagnante (**75 blocs** dans les trois). Le rescorage de consensus déplace le **score**, jamais le **verdict de fabricabilité** ni le **choix de la stratégie** — ce qui rend le résultat du chantier insensible à toute cette discussion. 📌 Détail et verdict coupure par coupure : [`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md) §3bis |
| 51 | 🔴 **`strategy_id` N'EST PAS UNIQUE — donc TOUT appariement enfant/parente par `from {id}` est ambigu.** 📏 Mesuré le 2026-08-19 sur `r75x2` : **21 identifiants sur 79** sont portés par 2 ou 3 stratégies **réellement différentes** — `n_blocks` différents, scores différents, λ différentes. Exemple : l'id `900000008` désigne à la fois une stratégie à 14 blocs, une à 10 et une à 1.<br>🔑 **Ce que ça casse** : l'`origin` d'une variante porte `RATE_L29(from 900000285)`, et c'est le seul lien vers sa parente. Avec des ids non uniques, **on ne sait pas de laquelle**. L'analyse appariée — le test le plus fort dont on dispose, celui qui a tranché le mécanisme du Rate — n'est donc légitime que là où l'id **se trouve** être unique, ce qu'il faut **vérifier à chaque fois** au lieu de le supposer.<br>⚠️ **Portée mesurée** : sur les 41 artefacts de balayage, **4 seulement** portent des ids exploitables (le champ valait `None` avant le correctif du 2026-08-19) ; les 37 autres ne supportent aucun appariement. 🟢 L'appariement du mécanisme Rate tient parce que la parente `75800` est unique dans ses artefacts — **vérifié**, pas supposé. |
| 48 | 🔴 **§24-37 N'EST PAS UNIVERSEL : l'échec peut naître à l'ASSEMBLAGE alors que la Phase A est parfaitement saine.** §24-37 explique la falaise du corridor par une Phase A acculée au « moins mauvais taux ». 📏 Le 2026-08-17, `[38,99)` en donne le contre-exemple, et la corrélation va **à l'envers** :<br>`a=36` → 6/446 déposables, `crash_min` 0 %, **4 couches en repli**, min 1 λ survivante<br>**`a=38`** → **0/452**, `crash_min` **42 %**, **0 couche en repli**, jamais moins de **4** survivantes, `crash_rate_min_observed` = **0,0000 partout**<br>`a=20` → 80/654, `crash_min` 0 %, **4 couches en repli**, min 1 survivante<br>🔑 **Le cas qui échoue a la Phase A la plus SAINE des trois.** Chaque couche est individuellement excellente, l'estimation par couche annonce zéro plantage, et la meilleure des 452 stratégies **assemblées** plante 42 % du temps.<br>✅ **Et cela donne à §24-33 le contre-exemple qu'il réclamait.** Il demandait d'*« instrumenter le `p` que la DP reçoit réellement »* : le voici mesuré, **`p_PhaseA` = 0,0000 contre 42 % réels**. L'écart n'est pas marginal, il est total. |
| 50 | 🔴 **`strategy_phase_timeout` EST INERTE — quatrième cas du motif, après `fast_auto_blocks`, `machine_sampling_dd` et `dp_yield_weight`.** 📏 Mesuré le 2026-08-18 : `grep -rn strategy_phase_timeout certus/core certus/workers` rend **0**. Il est collecté par `collect_params` (`certus_strat_ui_state.py:1033`), **exposé à l'utilisateur** dans un widget *« Max Time per Iteration (sec) »* dont l'info-bulle promet que *« the engine cancels the current pass if exceeded »*, enregistré dans les JSON — et **aucune ligne de calcul ne le lit**. 🔴 **C'est donc une promesse faite à l'utilisateur qui n'est pas tenue**, ce qui est pire qu'un simple paramètre mort.<br>⚠️ **J'avais bâti quatre affirmations dessus le 2026-08-18** — dans la sonde, le mode `extreme`, `CLAUDE.md` et un encadré entier de `CERTUS_STRAT.html` — toutes disant qu'il empêchait une troncature silencieuse. Corrigées le jour même.<br>**Les deux vrais bornages, tous deux CODÉS EN DUR :** `timeout=30.0` passé à `_find_k_best_groupings_dp_sequential` (`certus_strat_ranking.py:296`) — 🟢 **inerte lui aussi**, la fonction déclare `timeout` et `start_time` et ne les lit jamais ; et `concurrent.futures.wait(futures, timeout=600)` (`certus_strat_workers.py:1402`) — 🟠 il n'ampute pas les résultats (`shutdown(wait=True)` attend) mais **cesse de journaliser les exceptions** des segments au-delà de 600 s. **Sur un run de 157 min, une erreur tardive est muette.** |
| 3 | **Le lissage est une moyenne CAUSALE** (fenêtre `[i−k+1 … i]`), qui décale un extremum de ≈ `(k−1)/2` échantillons, soit **0,44 nm à k = 8**. [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.2 écrit « n'ajouter aucun décalage temporel » et §18-5 pose « aucun retard » en postulat figé. Une moyenne **centrée** ne décalerait rien. |
| 4 | **T7 n'est pas implémenté** malgré le message de `162a0ff`. L'arrêt reste obtenu par inversion parabolique continue ; aucune loi `U(0 ; 0,125 nm)` n'existe. Par ailleurs T5, T6 et T7 dans un seul commit contredit **C3**. |
| 18 | 🔴 **Le chemin CONSENSUS ignore `robustness_num_runs`.** Trouvé au rodage du 2026-08-10 : un run demandant **20 tirages**, `CONFIG` à l'appui, rend `0.002948627371309867` — **exactement**, au dernier bit, la référence historique à **150** tirages. `_unpack_consensus_cfg` porte un `consensus_num_runs` distinct, que l'override n'atteint pas. **Toute mesure faite avec le consensus actif est donc à une profondeur autre que celle demandée, et n'est comparable à rien.** Exposer `consensus_num_runs` avant de s'en servir. |
| 15 | 🔴 **Deux configurations différentes rendent le MÊME `RESULT` au bit, alors que leurs bandes diffèrent.** Seuils 2,0 A et 2,4 A : `RESULT = 0.003192038110407474` pour les deux, mais `passante` vaut 0,003214 contre 0,004444 — **38 % d'écart**. Donc `RESULT` est **aveugle à un changement qui déplace visiblement le résultat**. Avant de continuer à s'en servir comme grandeur de tête, il faut savoir ce qu'il agrège exactement : §21 dit « le pire des trois niveaux de bruit », et personne n'a vérifié cette phrase dans le code. |
| 16 | 🟢 **La bande bloquée n'est jamais le mode de défaillance.** Sur les 25 runs au disque, elle est **~567× plus propre** que la passante, sans exception. §22 s'inquiète à juste titre qu'un RMSE uniforme ne puisse pas distinguer les deux bandes — mais **le filtre ne rate jamais son blocage, il rate son passage**. ⚠️ Cela ne clôt pas §22 : l'exigence est ~500× plus serrée en bande bloquée, et 567 ≈ 500 signifie que les deux bandes sont **également proches de leur spec**, pas que l'une est acquise. Il faut les tolérances réelles par bande pour trancher, et on ne les a pas. |
| 12 | 🟠 **La marge de Phase A agit, mais ne change jamais l'issue** — *constat corrigé le 2026-08-11, l'ancien était trop sévère.* Il disait « elle ne rejette RIEN », sur la seule foi d'un `RESULT` bit-identique. **C'était lire la mauvaise grandeur.** D5.marg de la campagne du 2026-08-11 : à 3,33 le classement porte **257** stratégies contre 228 à 1,66, et son **top-5 est différent**. La marge atteint donc bien le calcul et modifie la population de la Phase A. Mais la gagnante reste la **même stratégie physique** — `[544, 531]`, 2 blocs, origine SYM, sous l'id 2226 au lieu de 2228, l'id n'étant qu'un rang d'énumération — et le score est bit-identique. **Le bon énoncé : elle change ce qui est offert, jamais ce qui est retenu.** |
| 19 | 🟢 **La prédiction du [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.3 est CONFIRMÉE, et cette fois sans l'artefact.** Le nombre de blocs de la gagnante croît de façon monotone avec le corridor : **2 → 3 → 4 → 5 → 8**. [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.3 l'annonçait — *« cela favorise les stratégies dont les λ de contrôle sont réparties plutôt que groupées »*. 🔑 **Ce qui rend ce constat solide, c'est qu'il survit à la correction.** Le bug de normalisation poussait dans le **même sens** (il pénalisait les λ groupées d'un facteur allant jusqu'à 21) : tant qu'il était là, l'effet physique était indémontrable. L'artefact retiré, l'effet demeure. |
| 17 | 🔑 **POEM protège AUSSI contre l'erreur d'indice, et ce n'est pas le théorème qui le fait.** Sur le corridor corrigé (2026-08-10), à 0,005 : `SEEL 0,6 nm` avec POEM contre **`22,3 nm` et 29,3 % de plantage** sans — un rapport de **×34,8** sur le `RESULT`. Or POEM n'est invariant que par distorsion **affine**, et une erreur d'indice n'en est pas une. **L'explication est l'autre mécanisme** : POEM recale ses ancres sur les extrema réellement observés, donc il compense les erreurs d'épaisseur **accumulées**. ⚠️ Le facteur de protection propre (rapport des coûts) demande un run POEM-off à corridor 0 sur le code corrigé, **qui n'existe pas encore** — les valeurs ×7,6 puis ×6,85 citées plus tôt sont d'avant l'enveloppe. |
| 26 | 🔑 **LE RÉSULTAT DE LA CAMPAGNE DU 2026-08-11 : à N = 150, le classement départage du BRUIT.** Deux mesures indépendantes le disent, et elles concordent.<br>📏 **(1) Dispersion sur sous-paquets** du run N = 1200, `scripts\analyse_campagne.py`. `spread_relative` est une **étendue** (max−min)/médiane, pas un écart-type : divisée par `E[étendue]/σ` du nombre de paquets, elle donne `σ ≈ 6,28 %` à N = 128 (9 paquets, ÷2,97) et `6,73 %` à N = 256 (4 paquets, ÷2,06). La loi en `1/√N` est **exacte** entre N = 32 et N = 128 : 12,56 / 6,28 = **2,00** pour une profondeur ×4. Donc **σ ≈ 5 à 6 % au point de fonctionnement N = 150**.<br>📏 **(2) Écarts entre stratégies**, classement N = 150, corridor 0 : #1 `0.0027330` · #2 **+6,5 %** · #3 +9,9 % · #4 +11,0 % · #8 +16,6 %.<br>🔴 **L'écart #1→#2 vaut 6,5 %, et la différence de deux scores porte `σ√2 ≈ 8 %` : la gagnante et sa dauphine sont à 0,8 σ. Indiscernables.** Le top 8 entier tient dans ~2 σ.<br>✅ **Corroboré par le balayage D2, obtenu autrement** : le top-5 n'est stable à **aucun** passage de N, et la gagnante alterne 2228 / 2218 / 2228 / 2228 / 2228 / 2218.<br>🔑 **Et les huit lisent `SEEL = 0,3 nm`.** La règle de tri de §22 — SEEL quantifié à 0,1 nm, puis rendement — n'est donc **pas une commodité d'affichage : c'est le classement statistiquement correct**, et cette campagne démontre que le tri continu actuel départage du bruit.<br>💰 **Le coût de l'alternative, chiffré** : séparer 6,5 % à 3 σ demanderait `σ ≈ 1,5 %`, soit `N ≈ 150 × (5,5/1,5)² ≈ 2000` tirages par stratégie — **×13**. La bonne réponse n'est pas de les acheter, c'est de déclarer l'égalité. |
| 42 | 🔑 **LES DIX EX ÆQUO SONT IDENTIQUES SUR 42 COUCHES SUR 48 — et trois choses convergent sur les six dernières.** Mesuré le 2026-08-11 avec le masque de préfixe commun.<br>**Le préfixe commun vaut 42 couches.** Les dix surveillent les 42 premières à **544 nm**, à l'identique. Elles ne diffèrent que par **où** elles changent de λ — couche 42, 43, 44 ou 45 — et **vers quelle** λ (506 à 545 nm). Autrement dit, à l'intérieur de la classe d'équivalence, toute la recherche se réduit à **une seule décision prise dans les six dernières couches**.<br>🔑 **Et cette région est déjà connue pour deux autres raisons** : §24-36 a mesuré que **rien ne plante avant la couche 35** et que tout plante de 35 à 47 ; et le Rate y est le plus précis, puisqu'il y dispose du plus grand nombre de couches de référence (§A24, loi en `1/√n`).<br>**Trois faits indépendants désignent les couches 42 à 47.** Les candidates du placement Rate de 👤 — la dernière couche d'un bloc, celle où λ change à `i+1` — valent ici **41, 42, 43 et 44**. Elles tombent exactement dans cette région.<br>✅ **Le masque fait son travail** : **4** marges discriminantes distinctes au lieu de 2, et l'ordre change réellement. La nouvelle première (`900000208`, 3ᵉ au score) porte **3,32 A** là où l'ancienne première (`2228`) en porte **0,83 A** — quatre fois plus exposée. La plus exposée de la classe, `900000204`, tombe au 10ᵉ rang avec **0,208 A**.<br>⚠️ Quatre stratégies se retrouvent **à égalité au sommet**, marge écrêtée à 2 A : c'est voulu et c'est la règle d'A23 — *au-delà de 2 A, rien ne distingue une impossibilité d'une autre*. Leur ordre relatif reste celui du score, faute de mieux, et il ne faut pas le lire comme un classement. |
| 41 | 🟢 **A23 ÉTAGE 3 — LA MARGE EST VALIDÉE, et le test a été rendu NON CIRCULAIRE avant de l'être.** Mesuré le 2026-08-11 sur les 228 stratégies du repère, **aucun run supplémentaire** — les trois niveaux de bruit étaient déjà calculés.<br>🔴 **L'objection d'abord, parce qu'elle était fondée.** Marge et plantage sortent de la **même** simulation. Et `margin_level` **devient négative** exactement quand `CRASH_LEVEL_UNREACHABLE` se déclenche : marge < 0 ⟺ a planté. Sur 23 stratégies (jusqu'à **−1702 A**) la marge **constate**, elle ne prédit rien. Une corrélation calculée sur l'ensemble complet aurait été une tautologie déguisée en validation.<br>✅ **Le test propre, sur les 205 marges STRICTEMENT POSITIVES** — celles dont la couche critique n'a **jamais** échoué, où la marge dit seulement de combien on est passé près :<br>`0 – 0,3 A` → 21 stratégies, **14 plantent**, taux moyen **0,984 %** · `0,3 – 0,6 A` → 3, toutes plantent, 1,556 % · `0,6 – 0,9 A` → 181, **7 plantent**, taux moyen **0,044 %**.<br>🔑 **Sous 0,6 A : 17 sur 24 plantent (71 %). Au-dessus : 7 sur 181 (4 %). Un facteur 22 sur le taux, prédit depuis le SIGNAL seul.** Corrélation **−0,577** sur ce sous-ensemble.<br>**On peut donc croire la marge à 1× là où le comptage rend zéro** — ce qui était toute la condition d'A23 : *on n'extrapole jamais sans avoir validé l'extrapolation dans le régime où la mesure est possible.*<br>⚠️ **Trois réserves.** La tranche 0,3–0,6 A ne compte que **3** stratégies : elle ne pèse rien seule. **24 stratégies plantent malgré une marge positive** — elles plantent sur une **autre** couche que leur couche critique, ce qui est attendu (la critique est la plus exposée, pas la seule) mais borne la précision du modèle. Et **aucune stratégie n'atteint 2 A** : la règle « au-delà de 2 A, impossible » reste **non testée** sur cet empilement, où rien n'est prouvablement sûr. |
| 39 | 📏 **LA FALAISE, ENCADRÉE SUR 5 GRAINES — campagne G, 2026-08-11. Remplace le §24-35, qui n'avait que 3 graines.**<br>**Où la graine 77 casse exactement** : `0,005 → 0 %` · `0,006 → 0 %` · `0,0075 → 0 %` · `0,010 → 100 %`. **La falaise est entre 0,0075 et 0,010**, donc la marge sur la valeur du modèle vaut **×1,5 à ×2** — plus serré que ce que §24-35 laissait croire.<br>**Le taux d'échec sur 5 graines** : à la valeur du modèle **0,005 → 0 graine sur 5 en échec** (pire cas 0,7 %) · au double **0,010 → 2 graines sur 5** (77 à 100 %, 202 à 37,3 %).<br>🔑 **L'énoncé défendable** : *le design est confortable à l'incertitude d'indice spécifiée, et deux graines sur cinq ne survivent pas à son doublement.* C'est une marge, pas un gouffre — et c'est maintenant chiffré sur un échantillon, pas sur une anecdote.<br>⚠️ **Ne lis pas la non-monotonie de la graine 77 comme un signal** : SEEL 1,3 → 0,7 → 1,0 nm de 0,005 à 0,0075, avec une gagnante à 4, puis 3, puis 2 blocs. C'est §24-26 en action — le classement départage du bruit, et la gagnante est un tirage. Les trois valent « de l'ordre de 1 nm », rien de plus. |
| 40 | 🟢 **LE MONITORING COUCHE-PAR-COUCHE GAGNE SUR 2 GRAINES SUR 5 À LA VALEUR DU MODÈLE.** Rang de la première stratégie à 48 blocs, corridor 0,005 : `graine 42 → 153/165` · `77 → 2/78` · **`101 → 1/80`** · **`202 → 1/90`** · `303 → 98/116`. Les gagnantes des graines 101 et 202 sont **à 48 blocs**.<br>Ce n'est donc ni une anomalie ni un artefact de la graine 101 : **à l'incertitude d'indice réelle, se réancrer à chaque couche est la meilleure stratégie deux fois sur cinq.** Combiné à §24-34 (l'effet se referme au-delà) et à §21.3 de la page (48 blocs coûte ×171 à corridor **0**), le tableau complet est : *le monitoring par blocs gagne quand l'indice est connu, le monitoring par couche gagne quand il l'est mal, et le basculement tombe dans la plage réelle d'un atelier.*<br>⚠️ L'offre varie aussi : 30 stratégies à 48 blocs à la graine 101 contre 4 partout ailleurs. Non expliqué. |
| 37 | 🔴 **LA FALAISE N'EST PAS DE LA PHYSIQUE QUI DURCIT — C'EST LA PHASE A QUI N'A PLUS LE CHOIX, ET LE SYSTÈME NE LE DIT PAS.** Mesuré le 2026-08-11 par comptage des rejets (§12-contrôle 4), sur les `STRAT_observability_*.json` des deux runs effondrés :<br>`candidates offertes` **108** · `interdites pour plantage` **103** · `survivantes, médiane sur 48 couches` **1** · **32 couches sur 48 en repli « moins mauvais taux »** · tolérance de plantage **0,001**, taux minimal réellement observé **0,007** — **7× la tolérance**.<br>**La chaîne complète** : le corridor rend presque toutes les λ inadmissibles → la Phase A ne trouve **aucune** λ sous la tolérance sur 32 couches et garde la moins mauvaise → la stratégie n'est plus *choisie*, elle est **forcée** → la Phase B la trouve à 100 % de plantage.<br>🔴 **Et le résultat final ne porte aucune trace de tout cela.** Il annonce une gagnante, avec un score et un SEEL, exactement comme un run sain. C'est le motif que ce document décrit depuis le début : *ça ne produit pas d'erreur, ça produit un résultat plausible.* Le repli **est** journalisé par couche, mais rien ne remonte au classement.<br>✅ **Correctif à faire, et il est petit** : remonter `n_layers_forced` (le nombre de couches en repli) dans le résultat de stratégie et dans le classement. **Une stratégie bâtie sur 32 couches forcées n'est pas comparable à une stratégie librement choisie**, et aujourd'hui rien ne permet de les distinguer. |
| 38 | 🟠 **Un filtre de plus qui ne rejette RIEN : `forbidden_gain_negative` vaut 0 sur les 8 runs examinés**, à toutes les couches, corridor 0 comme corridor 0,020. Le critère de gain de compensation négatif n'a **jamais** écarté une seule candidate. Comme pour §24-12 et §24-33 : soit il n'atteint pas le calcul, soit ce qu'il écarterait n'existe pas. **Compter avant de conclure** — mais un filtre à zéro rejet sur toute la plage mesurée est un défaut, pas un succès. |
| 33 | ✅ **§24-14 EST TRANCHÉ : `dp_yield_weight` N'ATTEINT PAS LE CALCUL.** F1 du 2026-08-11 l'a porté à 200 sur le bras qui plante à **59,3 %** (POEM coupé + distorsion). Résultat **bit-identique** à `yw = 0`, `0.3279370792191264`, même gagnante `8800`, **même top-5 dans le même ordre**. Or le terme vaudrait `200 · (−log(1 − 0,593))` = **180**, un coût énorme. Ce n'est donc plus l'explication arithmétique de §24-14 : **le fil est coupé.**<br>⚠️ **La nuance qui reste, et il faut la dire** : le `p` de la DP est l'estimation **par couche de la Phase A**, pas le taux final de la Phase B. Il reste donc deux lectures — le paramètre n'atteint pas la DP, ou la DP voit encore `p = 0` même ici. **Pratiquement, c'est le même verdict : comme bouton, il ne fait rien.** Ce qui les départagerait : instrumenter le `p` que la DP reçoit réellement. |
| 34 | 🔴 **MA PRÉDICTION DE §24-30 EST RÉFUTÉE — le monitoring couche-par-couche gagne dans une FENÊTRE, pas de façon monotone.** J'avais posé que si le mécanisme était réel, élargir le corridor devait le pousser plus loin. F2 dit le contraire :<br>`graine 101, corr 0,005` → 30 stratégies à 48 blocs, **rangs 1 à 30** · `graine 101, corr 0,010` → **1 seule, rang 55 sur 68**, et la gagnante fait 3 blocs · `graine 77` → rang 2 puis rang 21.<br>🔑 Et le run qui réfute est **sain** (0 % de plantage, SEEL 1,3 nm), donc ce n'est pas un régime cas limite qui parle. **Le constat §24-30 reste vrai — le gradient de pire à meilleur existe — mais il n'est pas monotone et je l'avais sur-extrapolé.** Il y a une bande d'incertitude d'indice où se réancrer à chaque couche paie, et elle se referme au-delà. |
| 36 | 🟢 **A23 ÉTAGE 0 REND SON PREMIER VRAI DIAGNOSTIC — impossible à obtenir avant le 2026-08-11.** Sur l'effondrement de la graine 77 à corridor 0,010, le profil par couche montre que **rien ne plante avant la couche 35**, puis tout plante de **35 à 47** — le dernier quart de l'empilement. Sur 1033 plantages par couche : **856 (79 %) sont des `tp_miscount`**, 222 (21 %) des `level_unreachable`.<br>**C'est l'histoire de l'erreur accumulée, lue directement** : l'erreur d'indice se compose le long de l'empilement, et dans le dernier quart l'écart d'épaisseur optique devient assez grand pour que la machine compte le **mauvais nombre d'extrema**. Ce n'est pas le niveau qui devient inatteignable, c'est le **comptage** qui décroche.<br>La gagnante porte en plus `worst_swing = 0,0334` à la couche 31 et **2 couches sous `SWING_MIN`** : la Phase A a retenu une stratégie qui a des couches sans signal exploitable. **Un taux agrégé de « 100 % » ne disait rien de tout cela.** |
| 29 | 🟢 **CAMPAGNE E, 2026-08-11 — les correctifs de cohérence passent la porte C1, et les deux résultats de tête TIENNENT.** 12/12 runs `OK`, code corrigé (§24-20, 23, 24, 25).<br>✅ **Porte C1** : `E0.ref = 0.0027329534106323534` contre `D0.ref = 0.0027329534107462224`, **écart relatif 4,2e-11** — l'ordre de la recompilation (2,8e-11, §9). Aucun correctif n'a fui dans le chemin neutre, donc la campagne est interprétable.<br>✅ **La courbe du corridor survit** : `×1,23 · ×2,03 · ×2,41 · ×4,66` contre `×1,24 · ×1,86 · ×2,46 · ×4,32` avant. Écarts de −0,7 % à +9 %, c'est-à-dire **dans le bruit statistique** (σ√2 ≈ 8 %, §24-26). Exposant **0,545** contre 0,525. **C'était le résultat phare et il est robuste au correctif.**<br>🔑 **POEM : la protection monte à ×41,2** (contre ×17,5). POEM actif ×1,198 sous distorsion, POEM coupé **×49,41**. Couper POEM sans aucune distorsion coûte déjà ×2,43 (contre ×1,975).<br>⚠️ **Le dommage résiduel avec POEM est de +19,8 % ici, pas +0,9 %.** [`TRAVAUX_A_VENIR.md`](docs/TRAVAUX_A_VENIR.md) §12.1 disait déjà que le +0,87 % de la graine 42 était un tirage chanceux. **Cite la protection, jamais le résiduel.** |
| 30 | 🔑 **LE MONITORING COUCHE-PAR-COUCHE PASSE DE PIRE À MEILLEUR QUAND LE CORRIDOR S'ÉLARGIT.** Gradient mesuré le 2026-08-11, et il est propre :<br>`corridor 0, graine 42` → 48 blocs au rang **228 sur 228** (dernier) · `0,005 graine 42` → rang 153/165 · `0,005 graine 77` → rang **2**/78 · `0,005 graine 101` → **rang 1, et les rangs 1 à 30**.<br>Le mécanisme est cohérent : les ancres POEM héritées du bloc ont été acquises sous un indice que la machine croit connaître et ne connaît pas. Plus l'erreur d'indice est grande, plus l'historique est **trompeur** — jusqu'au point où se réancrer à chaque couche devient gagnant. C'est le bout extrême de la tendance « λ réparties » du §24-19.<br>🔴 **MAIS ÇA NE CONTINUE PAS — voir §24-34, qui réfute l'extrapolation que j'avais faite ici.** L'effet vit dans une **fenêtre** d'incertitude d'indice et se referme au-delà. Le gradient ci-dessus est réel ; « plus le corridor est large, plus ça gagne » est faux.<br>🔴 **Ça ne contredit PAS le ×171 de §21.3 de la page** : celui-ci est mesuré à corridor **0**, où 48 blocs est effectivement catastrophique. Les deux énoncés portent sur deux régimes. **Ne cite jamais l'un sans son corridor.**<br>⚠️ Constat second, à ne pas perdre : `n_ranked` s'effondre avec le corridor — **228 → 165 → 78 → 80**. La Phase A élimine beaucoup plus de candidates quand l'indice est incertain. Non expliqué. |
| 31 | 🟠 **A23 fonctionne dès le premier usage, et il donne un chiffre honnête plutôt que le chiffre espéré.** Le profil de plantage par couche et le swing de la couche la pire remontent maintenant dans les rapports. Sur la gagnante de E4.101 : `worst_swing = 0,0874` à la **couche 39**, et l'unique plantage `level_unreachable` est **à la couche 39**. Coïncidence parfaite, sur les 10 premières lignes examinées.<br>🔴 **Puis la statistique complète corrige l'enthousiasme : 157 sur 561, soit 28 %.** À comparer à 1/48 ≈ 2 % par hasard : c'est un **enrichissement de 13×**, donc un vrai signal — mais la couche à plus faible swing n'est la couche défaillante que dans un cas sur quatre.<br>**Conclusion, et c'est exactement l'argument d'A23** : le swing est un **proxy**, pas la grandeur. Il faut la **marge** — étage 2 — qui est mesurée sur le signal réel au lieu d'être supposée. Ce 28 % est la meilleure justification qu'on ait pour faire l'étage 2 plutôt que de s'arrêter au swing. |
| 32 | 🔴 **E2 A ÉCHOUÉ, et c'est instructif : `dp_yield_weight` reste indécidable.** Le run devait trancher §24-14 en portant le poids là où il y a des plantages — corridor 0,005, qui plantait à 29,3 % sur le code d'avant. **Sur le code corrigé ce bras plante à 0,0 %**, donc le terme valait encore `w·(−log(1−0)) = 0` et E2 est revenu **bit-identique à E1.3**, même gagnante, même score. §24-14 est toujours ouvert. Le seul bras qui plante encore est E3.4 (POEM coupé + distorsion, **59,3 %**) → c'est là qu'il faut le mesurer, et c'est l'objet de F1. ⚠️ **Leçon de méthode** : une expérience conçue contre un régime que le correctif fait disparaître ne mesure rien. Vérifier que le régime existe **encore** avant de lancer. |
| 28 | 🔴 **AUCUN critère connu d'avance ne permet d'élaguer les 228 stratégies. Mesuré, et il détruit la règle évidente.** À corridor 0 la classe d'équivalence (`SEEL = 0,3 nm`) compte **10 membres, aux rangs 1 à 10, tous à 2 blocs, tous `ELITE` ou `SYM`** — une règle de tri superbe. **Elle ne survit à aucun changement de régime :**<br>`corr 0` → 2 blocs, ELITE+SYM · `0,001` → **3 blocs, `LOCAL_SEARCH` seul** · `0,0025` → 2 à 5 blocs, trois générateurs · `0,005` → **5 blocs, `LOCAL_SEARCH` seul** · `0,010` → **8 blocs, `LOCAL_SEARCH` seul** · graine 77 → 2-3 blocs, **les quatre générateurs** · 101 → LOCAL_SEARCH+SMART_MERGE · 202 → ELITE.<br>🔴 **`LOCAL_SEARCH` ne produit RIEN à corridor 0 et produit la gagnante, seule, à 0,001, 0,005 et 0,010.** La règle « il ne gagne jamais », que les données à corridor 0 justifiaient parfaitement, aurait **jeté la gagnante dans 4 configurations sur 8**. Idem pour « ne garder que les 2 blocs ».<br>**Chaque générateur mérite sa place dans au moins un régime, aucun dans tous.** C'est §25 en acte : *on ne prédit pas un résultat de simulation.*<br>✅ **Le levier qui marche est la PROFONDEUR, pas la population** (§24-27) : générer large, cribler peu (10 tirages, sans perte), approfondir étroit sur les ~10 finalistes. C'est une **réallocation**, pas une dépense en plus — ce qu'on cesse de payer à des stratégies à 3× la gagnante finance la profondeur là où elle décide. 📏 Coût mesuré : **~0,15 s par (stratégie × tirage)** au stade final, la Phase A (~730 s) n'ayant pas à être refaite. |
| 27 | 🟢 **L'entonnoir Phase A → Phase B NE FUIT PAS.** D3 du 2026-08-11, et le contrôle 4 de §12 est satisfait : le criblage **atteint** bien le calcul — `n_ranked` vaut **133 / 140 / 219 / 228 / 445** pour un criblage à 10 / 50 / 100 / 25 tirages et `keep30`. Malgré 445 stratégies classées contre 133, la gagnante est **toujours** `[544, 531]`, 2 blocs, SYM, et le score est bit-identique. **Cribler à 10 tirages ne perd rien, et garder 30 survivantes ne trouve rien de mieux.** ⚠️ C'est un résultat sur **une** graine et **un** empilement : il ferme A20 pour ce cas, pas en général. |
| 21 | ⚠️ **`MAX_LOOKBACK = 4` n'était documenté nulle part ici.** `MAX_LOOKBACK = MAX_LOOKBACK_VAL` (`certus_strat_growth.py:939`), la constante valant `MAX_LOOKBACK_VAL = 4` (`:75`). ⚠️ *Le renvoi disait `:526`, qui ne porte rien de tel.* L'historique de bloc rejoué par POEM est écrêté à **4 couches**, quelle que soit la longueur du bloc. C'est délibéré et testé (`tests/unit/test_strat_poem.py:169`), mais il faut le savoir pour lire tout résultat sur le nombre de blocs : **la valeur d'un bloc long est plafonnée par construction.** Un bloc de 24 couches ne rejoue que ses 4 dernières. |
| 22 | ⚠️ **L'historique est échantillonné 1,33× plus grossièrement que la couche courante**, et le commentaire du noyau annonce 4×. `NPTS_PREV = 16` par couche d'historique contre `NPTS = 64` sur `3 × d_nom`, soit 21,3 points par `d_nom` : le rapport de **densité** vaut 21,33/16 = **1,33**, pas 64/16 = 4 — les deux balayages ne couvrent pas la même longueur (`certus_strat_growth.py:511`). Conséquence réelle : un même point physique ne porte pas la même densité de bruit selon qu'il est lu comme historique ou comme couche courante. La grille cadence-machine corrige cela (ligne 652) mais elle est derrière `if smoothing_window > 1` — la soudure du §24-2. **Toutes les mesures faites à `reading_smoothing_window = 1` ont donc l'échantillonnage asymétrique.** |
| 43 | 🟢 **LA SURVEILLANCE PAR BLOCS SURPASSE LE MONOCOUCHE SUR LES DEUX EMPILEMENTS DE RÉFÉRENCE.** Les chiffres et leur artefact sont en **§24-43, en fin de document** (`reports/RAPPORT_SYNTHESE_STRATEGIES_BLOCS_35C_48C.md`) — n'en garde qu'une seule copie, ici le renvoi. 🔑 **5 changements de λ** en atelier au lieu de 34 et 47. 🔴 **La version antérieure de cette ligne citait `0.01824 / 0.00753 / 0.06391` et des SEEL de 0,9 et 0,7 nm : chiffres RÉFUTÉS.** Ils ne sont dans aucun artefact, et les deux SEEL du 35c sont **arithmétiquement impossibles** — $2\sqrt{0{,}08496} = 0{,}583$ nm et $2\sqrt{0{,}06391} = 0{,}506$ nm, pas 0,9 et 0,7. Ne les recopie pas. ⚠️ Le plantage nul est mesuré sur les blocs **présents dans le balayage** : 1 à 9 et 48 sur le 48c, 1 à 7 et 35 sur le 35c. Pas « de 2 à 9 » partout. |
| 44 | 🔑 **POURQUOI LES BLOCS BATTENT LE MONOCOUCHE (PHYSIQUE & POEM).** En monocouche, chaque couche réinitialise la phase et détruit la continuité du signal. Dans un bloc (5 à 8 couches), POEM s'appuie sur la continuité de $T(\lambda)$ et compense les dérives d'épaisseur passées (jusqu'à `MAX_LOOKBACK = 4`). De plus, l'interférence constructive transforme les couches individuelles à pente nulle ($\frac{dT}{de} \approx 0$) en fronts de déclenchement très raides. La **zone Goldilocks (4 à 7 blocs, optimum à 6)** évite à la fois l'aveuglement spectral ($\le 3$ blocs) et la perte de mémoire ($\ge 10$ blocs). |
| 45 | 🟠 **LE BONUS PHASE A BLOCK-AWARE DÉVERROUILLE L'ENTONNOIR, MAIS IL ALTÈRE BIEN LE CHAMP DE COÛT.** `certus_strat_objectives.py:415`, $C \leftarrow C_{\text{local}}/\sqrt{\text{streak}}$, seuil **`streak >= 2`**.<br>• Il fait franchir la troncature `dp_top_k` aux λ stables — **20 en FAST, 40 en PREMIUM, 100 en DEEP**, pas « 40 » : plus le `top_k` est large, moins le bonus change quoi que ce soit, et **aucune mesure ne l'a isolé mode par mode**.<br>• 🔴 **« sans altérer les coûts locaux » était FAUX** : le coût est **écrasé en place**, `cost_raw` (`certus/core/certus_strat_objectives.py:457`) contient déjà la valeur bonifiée, donc le coût d'avant n'est **plus récupérable**.<br>• 🔴 **Le bonus court AVANT `_normalize_phase_a_results`** (`certus_strat_pipeline.py:99`), dont la moyenne est calculée sur les coûts déjà bonifiés (`certus/core/certus_strat_objectives.py:438`) : la moyenne baisse, donc les candidates **non** bonifiées voient leur coût normalisé **monter**.<br>• 🔑 **La normalisation élève au carré** (`certus/core/certus_strat_objectives.py:456`) : ce que la DP de Phase B voit est $C/\text{streak}$, **pas** $C/\sqrt{\text{streak}}$. Un bloc de 9 couches est favorisé d'un facteur **9**, pas 3.<br>• ⚠️ Le seuil `streak >= 2` ne correspond **pas** aux blocs de 5 à 8 couches de la ligne 44 : deux couches consécutives suffisent à gagner un facteur 2, dans un régime qu'aucune mesure ne dit gagnant.<br>• 🔴 **Le « Cost Smoothing testé et réfuté à `0.37784` » n'a JAMAIS été mesuré.** Rien ne l'implémente (`grep cost_smoothing` → 0), il a été écarté par raisonnement. Et `0.37784` est le score de la stratégie **à 1 bloc** d'un run nominal 35c (`reports/campagne_N35_300.log:4309`, graine 42, N = 300). Il ne dit rien du lissage. |
| 9 | **`MachineModel` n'a toujours aucun consommateur en production.** Vérifié le 2026-08-09 : 5 occurrences en tout — la classe, deux ré-exports, un import, le test. Et `trigger_tolerance: float = 0.05` reste documenté « in T units (0..1) » alors que les consommateurs réels divisent par 100 : **piège ×100**. Manquent toujours vitesse de dépôt et cadence, qui sont pourtant en §17. |

**Le point 7 est refermé pour l'avenir** (`f4ada2d`) : la sonde écrit désormais sa
configuration effective dans `r["config"]` et dans le nom du fichier. Les deux artefacts déjà
produits, eux, restent inexploitables — **on ne peut pas les rattraper, il faut les
refaire.**

### ✅ Fermés — talons conservés parce que le code et ce document y renvoient

| # | Ce qu'il en reste |
|---|---|
| 52 | 🔑 **DIX CLÉS SUR ONZE N'ATTEIGNAIENT PAS LE CALCUL DEPUIS LE JSON — corrigé le 2026-08-20 (`aad370a`).** 📏 On charge une configuration portant onze leviers de recherche, on lit `collect_params`, dix ressortent à `None` : `rate_tail_sweep`, `rate_by_swing`, `rate_tail_keep_optical`, `rate_layer_sets`, `require_turning_point`, `optical_prefix_sweep`, `elite_min_improvement`, `elite_rounds`, `phase_a_seed`, `robustness_seed`. **Ils n'existaient que par surcharge de sonde**, donc tout le savoir des campagnes était inaccessible depuis l'application.<br>🔴 **Le cas le plus coûteux : `robustness_seed` valait TOUJOURS 42.** `_get_float_safe` interroge un widget de ce nom, et **il n'en existe aucun** — 0 déclaration dans tout `certus/ui/`. La meilleure configuration connue de `r75x2` (SEEL 0,5692, graine 77) était donc **structurellement hors de portée** de la production.<br>🔑 **La famille du défaut, et c'est elle qu'il faut retenir** : `dp_yield_weight` (§24-33) et `machine_sampling_dd` (§28-A8) sont le même motif — *un réglage visible qui n'agit pas est pire qu'un réglage absent : il fournit une explication fausse pour un résultat, et personne ne va la vérifier.* **Avant d'attribuer quoi que ce soit à un paramètre, vérifier qu'il arrive.**<br>✅ 26 tests posés, dont **24 échouent sur le code d'avant** (`tests/unit/test_strat_config_routing.py`). |

| # | Ce qu'il en reste |
|---|---|
| 1 | L'écart de 2,5e-11 n'était pas une violation de C1 : c'est la **recompilation** numba. Le seul instrument de C1 reste une empreinte `float.hex()`, qui n'existe pas (A5). |
| 2 | La grille machine était **soudée** au lissage. Dé-soudée : `machine_sampling_dd`, défaut 0. |
| 5 | Trois commits de fonctionnalité n'avaient **aucun** test. Comblé depuis. La règle demeure : **un test doit ÉCHOUER sur le code d'avant**, sinon il ne prouve rien. |
| 7 | 🔑 **Un run qui ne consigne pas sa configuration n'est comparable à rien.** Deux artefacts ont été perdus ainsi. La sonde écrit désormais sa configuration effective dans le résultat **et** dans le nom du fichier — et le nom porte aussi le **composant** (§32). |
| 11 | `CERTUS_POEM_ENABLED=0` était ignoré : `"0 "` avec une espace de fin passait le test d'appartenance. **Toute variable lue est `.strip()`, et une valeur inattendue lève.** |
| 14 | `dp_yield_weight` : tranché en §24-33, il **n'atteint pas le calcul**. |
| 20 | La Phase A recalculait le domaine de normalisation du corridor par couche. Corrigé : **un seul appelant calcule l'enveloppe et la passe aux trois étages.** |
| 23 | 🔑 **La propagation d'état de la Phase A laissait six paramètres à leur valeur neutre**, donc l'historique propagé vivait dans un monde plus propre que les candidates jugées dessus. Corrigé, et la **fente** en a été le septième (§30). C'est le motif à surveiller : *l'historique doit être simulé dans le monde où les candidates sont jugées.* |
| 25 | Un repli silencieux réinstallait la normalisation fautive du corridor. **Il lève désormais.** Règle générale : un paramètre manquant est une erreur de programmation, pas un défaut à combler en silence. |
| 35 | La falaise du corridor : périmé par §24-39, mesuré sur 5 graines au lieu de 3. |

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
mécanisme**, qui pèse 79 % des plantages mesurés (§24-36). C'est un arbitrage assumé
vitesse / fidélité, pas un oubli.

#### 🪦 La mesure de 2026-08-08 qui avait déjà tranché dans le même sens

⚠️ *Ce bloc portait un titre de section **vide** suivi d'un second titre « Tranchée — la
grille de balayage à 1 nm », c'est-à-dire **deux sections pour la même décision** dont l'une
sans contenu. Fusionnés le 2026-08-19 : ceci est l'**antécédent historique** de la décision
figée ci-dessus, pas une décision de plus.*

`scan_wl_step` est le pas entre λ de contrôle candidates. Deux simulations complètes
indépendantes, plage identique, seul le pas changeant :

| graine | pas 1 nm | pas 2 nm | verdict |
|---|---|---|---|
| principale | **0,002898** | 0,005283 | 1 nm meilleur, ÷1,82 |
| 77 | **0,003553** | 0,008400 | 1 nm meilleur, ÷2,36 |

⚠️ **Ces quatre chiffres sont HISTORIQUES** — état du code de 2026-08-08, avant A10 et avant
la correction d'enveloppe. Ils ne se comparent qu'entre eux, jamais au repère `D0.ref` de
§21. **Ce qui est acquis, c'est le rapport, pas la valeur** : le pas de 1 nm gagne sur deux
graines indépendantes, d'un facteur ~2. Ne les cite pas comme des `RESULT` courants.

Le pas de **1 nm** est retenu. Il coûte +9 % de temps et rend une gagnante à **2 blocs au
lieu de 4** — moins de changements de λ à exécuter.

> ⚠️ **La prédiction inverse avait été avancée** — qu'une grille plus fine gaspillerait le
> budget en candidates redondantes. La mesure l'a réfutée. **On ne prédit pas un résultat de
> simulation, on le mesure.**

> ⚠️ **Effet de bord.** `wl_step` valant déjà 1 nm, les deux grilles coïncident. Le bug de
> confusion entre elles devient **invisible sans avoir disparu**. **Ne supprime pas
> `_resolve_monitoring_wavelength_grid`** au motif que les grilles sont identiques.

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

248 fichiers `.py` sous `tests/` (241 `test_*.py`). ⚠️ **Le « 2 299 tests collectés » qui
figurait ici est faux par inclusion** : `tests/oracle/` + `tests/unit/` en rend à eux seuls
**2 456** au 2026-08-19, et `tests/` est un sur-ensemble. 🔴 **Ne recopie pas ce nombre : il
change dès qu'on ajoute un test** — compte-le avec `--collect-only` (§2). Le compte réel de
la suite complète n'est pas mesuré — elle coûte ~1 h 45.
`release-windows.yml:93` lance `pytest tests/oracle/ tests/unit/`, `tests.yml` lance
`tests/oracle/` puis `tests/`. **`lint.yml` n'exécute aucun test** — c'est le chantier qui
reste.

🔴 La branche de travail `refactor-corridors-mixins` est très en avance sur `main` (dernier
commit `main` : 2026-04-27) : **ces commits n'ont jamais été validés par la CI sur `main`.**

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
| **le biais de fente est actif par défaut** depuis le 2026-08-11 | tout `RESULT` antérieur décrit une machine à fentes infiniment fines. C'est ce qui périme les anciens repères (§21) |
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

⚠️ Les **temps absolus** de [`docs/REPRISE_PERF.md`](docs/REPRISE_PERF.md) datent d'avant le
déménagement hors Google Drive ; les **rapports** restent valides.

---

## 32. Les composants d'essai

📌 **Le dossier est dans [`docs/COMPOSANTS.md`](docs/COMPOSANTS.md)** — la formule, les
matériaux, la plage spectrale et l'histoire de chaque composant.

**Les quatre, et ce que chacun sert à tester** — les repères chiffrés sont en §21 :

| composant | couches | ce qu'il apporte |
|---|---|---|
| **dichroïque** `JSON-strat-example` | 48 | le juge de paix. Passe-court, front à ~545 nm. Monitoring facile |
| **passe-bande 3 cavités** `JSON-strat-bandpass-3cav` | 35 | une résonance, une bande étroite. Notation sur 60 nm seulement |
| **aléatoire** `JSON-strat-random75` | 75 | 🔑 **ni cavité, ni miroir, ni périodicité** — le seul qui teste si une règle est **générale**. Graine 2026 |
| **passe-bande 5 cavités** `-5cav-99c` | 99 | le cas dur. **100 % de plantage** en une campagne |

🔴 **Ils ne sont pas notés sur le même domaine spectral** — 300 / 200 / 60 / 45 nm. Comparer
leurs SEEL entre eux mélange la difficulté du composant et la largeur de la fenêtre. Les
comparaisons **à composant fixé** restent valides. Voir §21.

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

🔴 **CE N'EST PAS LE PROGRAMME COURANT** — celui-ci est le **Rate**
([`CHANTIER_RATE.md`](docs/CHANTIER_RATE.md)). Ces trois actions sont **valides, utiles et
entièrement spécifiées**, et elles attendent. ⚠️ *Cette ligne désignait le multi-témoins, qui
est **acquis** depuis le 2026-08-19 — cinquième endroit du document où le programme courant
n'avait pas été mis à jour, après la carte du §3, le titre du §23, la règle 4 du §11 et le
vocabulaire du §14.*

| | | pourquoi elle compte |
|---|---|---|
| **A25** | `sigma_rate` comme **prédiction** | 🔑 la seule action du document qui attaque §26 — la première grandeur vérifiable **de l'extérieur**, contre ce que 👤 observe en salle (±1 à 2 %) |
| **A26** | un bloc de **santé de run** | automatise le contrôle 4 de §12 |
| **A27** | le harnais d'empreinte `float.hex()` | A5, la non-régression au bit près |

**Ce qui les motive, et qui n'a pas changé** : tout le travail des 12 et 13 août a rendu STRAT
plus **cohérent**. Rien ne l'a rendu plus **vrai**. §26 reste entier, et aucun correctif
interne n'y changera quoi que ce soit.
