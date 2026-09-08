# CERTUS — Plan UX

**Ce fichier est le plan actif, et il est le seul.** Il a d'abord remplacé la partie « plan »
de `GEMINI_UX_TOP1_2026-09-04.md`, laissé en place comme journal de preuves —
**puis ce journal a été supprimé le 2026-09-08.** Ce qu'il avait d'irremplaçable, les
affirmations que la mesure a réfutées, est extrait dans [`UX_DEMENTIS.md`](UX_DEMENTIS.md) ;
ses conclusions d'étape vivent dans les docstrings des garde-fous, qui est l'endroit où un
agent les lira. `git log` garde le reste.

> Rédigé le 2026-09-07, sur `06aedd8`. L'ancien plan faisait 3692 lignes et son en-tête
> annonçait encore « phases 3 à 6 entières » alors que neuf étapes de la phase 3 étaient
> faites. Un plan qu'il faut lire à cinq endroits pour connaître l'état d'une étape n'est plus
> un plan. Celui-ci tient en une page et dit **une** chose par ligne.

---

## 0. Où en est-on — au 2026-09-08

| section | état |
|---|---|
| §3 — le préalable de reproductibilité | 🟢 **clos.** 14 passes rendent un verdict unique. Deux causes racines restent ouvertes et sont nommées au §3 |
| §4.1 — corrections de sens | ✅ close |
| §4.2 — promesses de la fenêtre d'accueil | ✅ close |
| §4.3 — saisie et lecture | ✅ close |
| §4.4 — les deux modules jamais audités | ✅ close |
| §4.5 — campagne « pas de valeur en dur » | ✅ close |
| §4.6 — ergonomie métier (ex-phase 5) | ✅ close. Un point annoncé en a révélé **quatre**, dont un qui empêchait l'export automatique après chaque run |
| §4.7 — le mode sombre figé | ✅ close. 🔴 **Le plus gros défaut trouvé de la journée** : quatre appels écrasaient la préférence de l'opérateur par un défaut d'argument, et 34 feuilles de style sur 93 peignaient en clair sur une fenêtre sombre |
| campagne typographique | ✅ close, cliquet 173 → 52 |
| **§6 — critères de fin** | **12 sur 13 atteints et mesurés.** Le treizième est une cible démontrée inatteignable, consignée en `xfail(strict=True)` |

📏 **Validation du 2026-09-08, en trois commandes** (voir §2 pour pourquoi trois) :
`ruff check .` → **All checks passed!** · `tests/unit/` → **2 456 passed, 10 skipped, 0 failed**
· `tests/ui/` → **0 échec** sur la totalité des fichiers.

⚠️ **Et un échec réel a été trouvé là, pas ailleurs.** `test_certus_ui_ux_boost::test_log_panel_widget`
était cassé depuis le matin par le correctif du panneau de journaux (§4.2) : Qt marque comme
**caché** tout enfant ajouté à un parent **déjà visible**, et l'appel à `setVisible()` précédait
l'ajout du widget de texte. Corrigé en le déplaçant en dernier. 🔑 *C'est le §3 en acte : le
défaut n'était visible que dans la moitié `tests/unit/`, celle que je n'avais pas rejouée
depuis ce correctif.*

🔴 **Ce qui n'est PAS fait, et qu'aucune ligne ci-dessus ne remplace :**

1. **Personne n'a regardé les onze fenêtres.** Tout ce qui précède est mesuré par des
   garde-fous en mode *offscreen*. Un garde-fou dit qu'un contraste tient, pas qu'une fenêtre
   est agréable. **Une revue visuelle reste le seul juge du « top 1 % ».**
   🔵 **👤 a décidé le 2026-09-08 de ne pas la faire pour l'instant et de ne rien bloquer
   dessus.** C'est une décision, pas un oubli — et elle ne change rien au fait : *la revue
   n'a pas eu lieu, et aucune ligne de ce document ne dit le contraire.*
2. **Trois arbitrages appartiennent à 👤** et ne sont pas des correctifs : les teintes de
   marque, le comportement de la bande des fichiers récents, et les plages des champs
   numériques (aucune borne n'existe dans le code — les poser est une décision métier).
   🔵 **Laissés en l'état le 2026-09-08, sur décision de 👤.**
3. **La cause racine de l'abort natif** et **`skeleton[CERTUS_DESIGN]`** restent ouverts (§3).

🔑 **Et la leçon du 2026-09-08, qui vaut pour tout ce qui suit** : trois garde-fous verts se
sont révélés mesurer **l'intention et non le rendu** — les jetons de couleur au lieu de la
feuille livrée, un compte d'info-bulles périmé de 19 à 12, une carte de lancement dont les
tests passaient parce qu'elle ne faisait rien du tout. *Un critère à zéro ne vaut que par la
définition de ce qu'il compte.*

🔑 **Corollaire du même jour, et il est plus utile encore** : **quatre étapes sur six ont rendu
davantage que ce qu'elles annonçaient.** « Le bouton de documentation est illisible » cachait
une règle de style fautive dans **toute** la suite ; « le bandeau montre le mauvais indicateur »
cachait une exception qui **empêchait l'export automatique après chaque run**. *Instruire un
symptôme jusqu'à son mécanisme coûte une heure et en rapporte trois.*

---

## 1. Ce qui ne se discute pas

| # | règle | pourquoi |
|---|---|---|
| R1 | **Jamais `git commit`.** | Le hook `post-commit` pousse vers un dépôt **public**. Laisse le travail dans l'arbre et signale-le. |
| R2 | **Jamais `ruff check --fix`.** | Des ré-exports volontaires sautent. |
| R3 | **Ne touche pas `pyproject.toml`**, ni `example/`, ni `reports/`. | Verrouillé par un test ; données scientifiques de référence. |
| R4 | **Dans `certus/` : commentaires, docstrings et logs en anglais.** | `docs/` et `scripts/` sont en français. |
| R5 | **`certus.core`, `certus.physics`, `certus.domain` n'importent jamais PyQt6.** | Frontière d'architecture. |
| R6 | **Aucune couleur ni taille codée en dur** dans une feuille de style. | Sinon le mode sombre décroche. |
| R7 | **Ne rends jamais triable une table qui décrit un empilement.** | L'ordre des couches **est** la physique. |
| R8 | **Ne « corrige » pas `except A, B:`.** | Syntaxe PEP 758 volontaire, valide en 3.14. Les parenthèses changent le sens. |
| R9 | **Un processus par fenêtre pour toute mesure Qt.** | `QApplication.font()` est un global de processus. |
| R10 | **Si tu n'as pas mesuré, écris-le.** Si une sortie contredit ce document, **arrête-toi et signale.** | Un contournement silencieux est la seule faute disqualifiante. |
| R11 | **Ne modifie pas un test pour le faire passer**, sauf si l'étape le nomme et dit pourquoi. | |
| R12 | **Après avoir régénéré une baseline, colle le diff des métriques.** | Sinon le cliquet protège la régression au lieu de la signaler. |
| R13 | **Mesure ce qui est RENDU, pas ce qui est déclaré.** | 📏 `test_ux_button_contrast` était vert alors que la feuille livrée peignait 2,54:1 : il assérait la paire de **jetons**, que rien n'obligeait la feuille à employer. Quand la propriété est visuelle, peins le widget et relis les pixels. |
| R14 | **Un garde-fou d'interface ne déclenche jamais l'action qu'il vérifie.** | Un test d'activation a lancé de vrais modules CERTUS et bloqué la suite dix minutes. Construis un widget isolé, ou inspecte sans émettre. |

**Environnement** : Python système 3.14.7, PyQt6 / Qt 6.11. Le venv `C:\envs\certus` cité dans
`CLAUDE.md` **n'existe pas**. Vérifie avant de mesurer :

```bash
python -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

**Périmètre** : dix modules plus le HUB — **onze fenêtres**.

---

## 2. Comment on valide

```bash
python -m ruff check .
python -m pytest tests/unit/ -q --no-cov
python -m pytest tests/ui/ -q --no-cov --deselect tests/ui/test_ux_re_stop_when_idle.py
python -m pytest tests/ui/test_ux_re_stop_when_idle.py -q --no-cov
```

🔑 **En TROIS commandes, et ce n'est pas une commodité.** 📏 Mesuré le 2026-09-08 :
`tests/unit/` rend **2 456 passed en 2 min 58** — toute la lenteur est du côté interface. Et
`test_ux_re_stop_when_idle` coûte **~9 min par test dans la suite complète contre 6,9 s pour
ses six tests isolés** ; laissé dedans, il empêche la passe d'aboutir dans son plafond (§3).
Séparer les moitiés a un second mérite : **un arrêt natif dans l'une ne détruit plus le verdict
de l'autre**.

`0 failed` est le seul critère. **Le nombre de tests n'en est pas un** : il se périme dès qu'on
travaille. Le périmètre est `tests/ui/ + tests/unit/`, **jamais `tests/ui/` seul** — c'est le
périmètre restreint qui a laissé publier un test cassé.

⚠️ La moitié interface dure **~50 min**. Ce n'est pas une commande qu'on lance entre deux
éditions : c'est celle qui décide qu'une étape est finie. ⚠️ Et **elle exige la machine pour
elle seule** — voir le piège 4 du §7.

🔴 **Une passe qui enjambe une édition n'est pas un verdict.** Deux ont dû être jetées le
2026-09-08 pour l'avoir oublié : les modules déjà importés gardent l'ancien code, ceux qui
restent prennent le nouveau, et le résultat ne décrit aucun arbre existant.

**Format d'une étape livrée** : fait / partiellement fait / pas fait · fichiers touchés ·
sortie collée du garde-fou **échouant sur le code d'avant** · sortie collée après correctif ·
ce qui a bloqué. Un garde-fou qui ne casse pas sur le code d'avant ne prouve rien.

---

## 3. Le préalable — 🟢 le verdict est redevenu fiable, la cause racine reste ouverte

**Constat de départ** : 3 échecs distincts sur 5 passes complètes, chacun passant isolément.
Le seul critère du projet — `0 failed` — n'était donc pas reproductible, dans les deux sens.

### Ce qui a été mesuré, le 2026-09-07

Le worker d'un test UX a été relancé en boucle, seul, sur `CERTUS_RE` :

```
[25] NO MARKER  returncode=3221225477 (hex 0xc0000005)  stderr=EMPTY
```

📏 **`0xC0000005` est une violation d'accès**, et **stderr est vide** : le processus meurt sans
dérouler Python, donc aucune exception n'est levée ni écrite. Sur **120 lancements, 2 ont
échoué ainsi** (1,7 %), avec le même statut et le même stderr vide. Une passe complète en
enchaîne quelque deux cents — ce qui prédit environ trois crashs par passe, et **rend compte
exactement des trois échecs observés sur cinq passes**.

⚠️ **L'hypothèse de tête du dossier — le rendu SVG — n'explique pas ces crashs** : sur cette
plateforme, `is_svg_icon_rendering_disabled()` rend déjà `True`, donc aucun SVG n'est peint.
Le **mode** de défaillance est bien celui que ce garde-fou décrit, mais la **cause** est
ailleurs et **n'est pas identifiée**.

### Ce qui a été corrigé

Le vrai défaut n'était pas le crash, c'était son **déguisement**. Les huit modules qui lancent
un worker lisaient stdout seul et **aucun ne consultait `returncode`** : un arrêt natif rendait
`assert []` avec un stderr vide, indiscernable d'une régression d'interface.

Ils passent désormais tous par `tests/ui/_ux_worker.py`, qui :

- n'accepte qu'une ligne de marqueur comme résultat ;
- **réessaie une fois**, puisque l'arrêt est transitoire — et **signale la reprise par un
  warning**, jamais en silence ;
- en cas d'échec des deux tentatives, **nomme le statut de sortie**, de sorte qu'un arrêt natif
  ne puisse plus jamais ressembler à une assertion vide.

Avec deux tentatives, la probabilité qu'un test tombe sur l'aléa passe de ~1,7 % à ~0,03 %.
Un crash **systématique**, lui, échoue toujours : la reprise ne peut pas masquer un défaut réel.

Le garde-fou est `tests/ui/test_ux_worker_harness.py` : il provoque l'arrêt natif à la demande
(`os.abort()`, même signature — statut anormal, stderr vide) au lieu de l'attendre, et vérifie
les trois comportements ci-dessus.

### ✅ Vérifié par répétition — 5 passes, le 2026-09-07

Relevé complet : [`MESURE_REPRODUCTIBILITE_2026-09-07.md`](MESURE_REPRODUCTIBILITE_2026-09-07.md).

| | départ | après correctif |
|---|---|---|
| tests **différents** en échec sur 5 passes | **3** | **1** |
| échecs imprévisibles | 3 | **0** |
| échecs lisibles sans relance | aucun | **tous** |

5 aléas de worker ont été absorbés par la reprise ; un seul est passé au travers, en
s'annonçant lui-même comme une violation d'accès. **Sans le correctif, ces 5 passes auraient
compté 6 échecs de worker.**

### 🔴 UN FICHIER REND LA PASSE COMPLÈTE IMPRATICABLE — mesuré le 2026-09-08

`tests/ui/test_ux_re_stop_when_idle.py` : **6 tests, 6,90 s** lancé seul, durées détaillées à
l'appui (le plus lent, 2,02 s). **Dans la suite complète, il consomme ~9 minutes PAR TEST** —
un facteur de l'ordre de **500**. Six tests, donc ~54 min pour un fichier qui en vaut sept
secondes ; c'est à lui seul la raison pour laquelle la passe n'aboutit pas dans son plafond de
90 minutes.

📏 **Observé sur DEUX passes indépendantes du même jour**, l'une lancée avant les correctifs de
thème et l'autre après : ce n'est ni un hasard ni une régression de la journée.

⚠️ **Et j'ai diagnostiqué faux deux fois avant de le mesurer.** J'ai d'abord dit « bloquée »,
puis « contention avec mes propres sondes » — les deux étaient faux : la passe **progresse**,
elle est seulement très lente, et elle l'est aussi machine libre. *Un silence de dix minutes
sur une sortie `pytest -q` n'est pas un blocage : plusieurs fichiers lancent des dizaines de
processus Qt et n'écrivent rien entre-temps.*

🔑 **Parade en attendant la cause** : `--deselect tests/ui/test_ux_re_stop_when_idle.py`, et
lancer ce fichier séparément — il passe en 7 s. La cause n'est pas établie ; le fichier porte
sur l'arrêt de workers RE, et l'hypothèse la plus simple est qu'un état laissé par un test
antérieur lui fait épuiser ses attentes.

### Ce qui reste ouvert

🔴 **`skeleton[CERTUS_DESIGN]` — le seul obstacle restant à `0 failed`.** Il échoue **5 fois sur
5** dans la suite complète, toujours au même compte exact (`84/92`, les sept onglets et le
bouton de détachement), et **passe seul en 7,5 s**. Défaut **préexistant**, déjà relevé « trois
runs sur trois » par le chantier précédent, dont **deux explications successives ont été
réfutées** — voir [`UX_DEMENTIS.md`](UX_DEMENTIS.md) ; la garde de confirmation censée l'avoir
réglé ne le rattrape pas. **Sans rapport avec ce chantier — c'est la prochaine étape à ouvrir.**

🔴 **La cause racine de la violation d'accès.** La suite est fiable *malgré* elle, elle n'en est
pas débarrassée. Deux modes distincts ont été observés — abort natif `0xC0000005`, et sortie
propre sans marqueur — voir l'anomalie A3 du relevé.

---

## 4. Le travail — ✅ **entièrement clos le 2026-09-08**

Les cinq sous-sections sont closes. Elles restent ici **avec leurs mesures**, parce que le prix
d'une étape n'est pas le correctif : c'est ce qu'il a fallu écarter avant de le poser. Cinq
affirmations du dossier d'origine ont été démenties par la mesure, et **deux de plus l'ont été
ici** — le préfixe technique dans les libellés (sans objet) et le compte d'info-bulles
manquantes (19 annoncé, **12** mesuré).

### 4.1 — Corrections de sens (une chaîne affichée est fausse)

| quoi | où | coût |
|---|---|---|
| Une consigne d'unité affichée est amputée et ne veut plus rien dire | `certus/metal/certus_metal_common.py`, message de plage d'entrée | 1 ligne |
| Les en-têtes de table sont forcés en capitales, or en optique la casse **est** une grandeur : la colonne de l'indice réel s'affiche comme le symbole de l'indice complexe, idem pour le coefficient d'extinction, la transmission et la réflexion | `certus/utils/certus_ux.py`, règle `QHeaderView::section` de `build_premium_overrides` | 1 ligne |

C'est le meilleur rapport valeur/effort du dossier : deux lignes, et l'une corrige une
**ambiguïté scientifique** sur un logiciel de métrologie.

📏 **Trois points vérifiés avant d'appliquer, le 2026-09-07 — le risque annoncé n'existe pas :**

1. **Qt honore bien `text-transform`**, alors que la propriété ne figure pas dans la liste QSS
   documentée. Rendu du même en-tête avec et sans la règle : **images différentes**. Le défaut
   est donc réel, et le correctif a un effet.
2. **La règle vit dans la seconde couche seulement.** La feuille du thème n'a jamais forcé les
   capitales ; ce sont les overrides appliqués par-dessus. Même motif que 3.7 et 3.10 — *le
   défaut vit dans la seconde feuille, et le contrôle lit la première.* Le garde-fou lit donc
   les deux couches.
3. 🔑 **Aucune référence n'est à régénérer, contrairement à ce que ce plan disait et à
   l'avertissement du §5.9 du dossier.** `text-transform` est un effet de rendu :
   `headerItem().text()` ne change pas. Mesuré — le squelette ne contient **aucune** entrée
   `QHeaderView` ni `QTableWidget`, le cliquet non plus, et les deux tests qui lisent un en-tête
   lisent le texte du modèle. **Ce n'est donc pas une étape à isoler.**

Garde-fou : `tests/ui/test_ux_table_header_case.py`, avec son contrôle négatif. Vérifié
échouant sur le code d'avant, sur la couche `premium overrides` uniquement.

### 4.2 — Promesses non tenues sur la fenêtre d'accueil

Le HUB est la première impression, et il porte les défauts les plus visibles du dossier.

| quoi | où |
|---|---|
| ✅ **« Show Details » ouvre vraiment le panneau** — fait le 2026-09-08 | `CERTUS_HUB.py` |
| ✅ **Les dix lanceurs sont atteignables au clavier** — fait le 2026-09-08 | `certus_hub_widgets.py`, `CERTUS_HUB.py` |
| ✅ **Une carte se comporte comme un bouton sous la souris** — fait le 2026-09-08 | `certus_hub_widgets.py`, `CERTUS_HUB.py` |
| ✅ **« Scientific Documentation » est lisible** — fait le 2026-09-08 | `CERTUS_HUB.py`, `certus_ux.py` |

**Le §4.2 est clos.**

#### ✅ Lanceurs accessibles au clavier — 2026-09-08

`BaseApplicationCard` reçoit une politique de focus, un signal `activated` et un
`keyPressEvent` qui l'émet sur Entrée / Retour / Espace ; `ApplicationCard` porte désormais un
nom et une description accessibles. Côté `CERTUS_HUB`, le signal est connecté au lancement —
**c'était nécessaire** : la ligne qui remplace `mousePressEvent` par une lambda coupait toute
autre voie vers `launch_module`.

Garde-fou : `tests/ui/test_ux_hub_launcher_accessibility.py`, 7 tests, avec contrôle négatif
(une touche quelconque ne doit pas activer). Vérifié **échouant sur le code d'avant** :
`5 failed, 1 passed` — seul le contrôle « le HUB montre bien 10 lanceurs » passait. Après
correctif : `7 passed`, et `26 passed` sur le périmètre HUB élargi.

⚠️ **Piège rencontré, consigné pour ne pas le refaire** : la première version du garde-fou
émettait `activated` sur les cartes **de la vraie fenêtre**, désormais câblées à
`launch_module` — elle a donc lancé de vrais modules CERTUS et bloqué la suite dix minutes.
Le test d'activation construit maintenant une carte **isolée**. *Un garde-fou d'interface ne
doit jamais déclencher l'action qu'il vérifie.*

#### ✅ Une carte se comporte enfin comme un bouton — 2026-09-08

`CERTUS_HUB` remplaçait le `mousePressEvent` de chaque carte par une lambda qui **ignorait son
événement**. Trois conséquences, toutes réelles : n'importe quel bouton de souris lançait un
module — un clic droit destiné à un menu contextuel démarrait un processus CERTUS ; le
lancement se faisait **à l'appui**, donc sans retour possible ; et l'affectation masquait la
méthode de classe, ce qui avait obligé à dupliquer le chemin pour le clavier.

`BaseApplicationCard` porte maintenant les deux moitiés du geste : `mousePressEvent` **arme**
sur le bouton gauche seulement, `mouseReleaseEvent` n'émet `activated` que si le relâchement
tombe **dans** la carte. C'est l'échappatoire qu'a tout bouton : appuyer, glisser à côté,
relâcher, et rien ne se produit. `GroupedApplicationCard` perd son propre `mousePressEvent` —
son `script_name` **est** déjà le script du premier sous-module, donc les deux voies menaient
au même endroit, ce qui a été vérifié avant de supprimer l'une des deux.

Garde-fou : `tests/ui/test_ux_hub_mouse_activation.py`, 8 tests. Vérifié **échouant sur le code
d'avant** : `2 failed, 6 passed`. 🔑 **Les six qui passaient le faisaient à vide** — une carte
isolée n'avait alors aucun comportement du tout — et c'est exactement ce que le contrôle
négatif (« un clic gauche active bien la carte ») empêche de prendre pour un succès. Après
correctif : `8 passed`, et `36 passed` sur le périmètre HUB.

⚠️ La vraie fenêtre est **inspectée, jamais activée** : le test lit `vars(carte)` pour vérifier
qu'aucun gestionnaire n'est masqué. Émettre `activated` là-bas lance de vrais modules.

#### ✅ « Scientific Documentation » : le reproche était fondé — 2026-09-08

Le dossier notait ce bouton comme rendant *blanc sur blanc*. Le diagnostic a d'abord écarté la
piste évidente : `open_documentation` passe sa page au **navigateur système**, donc le reproche
ne pouvait porter que sur le bouton lui-même. Or un widget stylé en QSS ne rapporte pas ses
couleurs par sa palette. La seule mesure honnête est de **le peindre et de relire les pixels** —
`scripts/sonde_bouton_documentation.py`.

📏 Avant correctif, **dans les deux thèmes** : `#ffffff` sur 97,6 % de la surface, le reste
étant sa bordure, et **aucune encre**. Le bouton était littéralement illisible.

**Deux causes indépendantes, et la seconde ne se serait jamais vue sans la première :**

| # | cause | portée |
|---|---|---|
| 1 | la barre du bas portait une feuille de style **sans sélecteur**. En Qt, cela s'applique au widget **et à tous ses enfants** : son fond atteignait donc le bouton et, venant d'un ancêtre plus proche, l'emportait sur la règle `QPushButton#CertusPrimaryBtn` — dont la couleur de texte, elle, s'appliquait toujours | le HUB |
| 2 | cette règle codait `color` en **blanc littéral** au lieu du jeton de libellé | **tous** les boutons primaires et danger de la suite |

📏 Cause 2, mesurée : en sombre, blanc sur la couleur primaire donne **2,54:1**, et sur la
couleur danger **2,77:1** — les deux sous le seuil AA. Avec les jetons : **7,02:1** et
**6,45:1**. En clair, les deux valeurs sont **identiques** au blanc littéral (5,00:1 et
4,83:1) : le correctif ne déplace rien là où il n'y avait rien à corriger.

🔴 **Et c'est le point de méthode le plus important de la journée.**
`tests/ui/test_ux_button_contrast.py` était **vert depuis le début** — et sa propre docstring
énonce le chiffre 2,77:1 comme un défaut. Il assère la paire de **jetons**, que rien n'oblige
la feuille livrée à employer. *Un garde-fou qui vérifie l'intention plutôt que le rendu peut
rester vert pendant que le défaut qu'il décrit est à l'écran.*

📏 Après correctif, mesuré au pixel : clair **5,00:1**, sombre **7,02:1**, lisibles.

Garde-fou : `tests/ui/test_ux_button_label_is_painted.py`, 8 tests, qui mesure ce qui est
**peint**. Vérifié **échouant sur le code d'avant** : `4 failed, 4 passed`. Il porte deux
contrôles négatifs en sens inverse — un bouton blanc sur blanc délibéré doit être condamné, et
du noir sur blanc doit passer.

🔑 **Le second contrôle a immédiatement pris mon propre instrument en défaut** : il notait du
noir sur blanc à **2,52:1**, parce que je prenais pour encre la couleur la plus *fréquente*
après le fond — c'est-à-dire le halo d'anticrénelage, pas le cœur du glyphe. L'encre est
désormais la couleur la **plus éloignée** du fond, et les 3 pixels de bordure sont écartés du
comptage (une bordure sombre sur un fond pâle se lirait sinon comme une lisibilité parfaite).

⚠️ **Défaut voisin laissé ouvert, et il faut le dire** : la feuille de la barre du bas est une
f-string évaluée **pendant la construction**, donc figée sur les jetons du mode clair. En
sombre la barre reste blanche. Le bouton, lui, est désormais lisible dans les deux modes —
c'est un défaut d'**ordre d'initialisation** (`_build_ui` court avant l'application du thème),
d'une autre nature et d'une autre portée que celui-ci.

⚠️ **Piège de mesure payé en route** : deux fenêtres construites dans un même processus ne se
comparent pas — la seconde hérite d'un état de thème que la première a laissé. J'ai conclu
« lisible en sombre » sur cette base, puis retiré la conclusion après remesure en processus
séparés. Le garde-fou construit donc **une fenêtre par mode**, et pose la préférence
persistée sans appeler `configure()` d'abord : c'est le chemin réel de lancement, et
pré-configurer la palette mesurerait un état que l'application n'atteint jamais.

#### ✅ Grille du HUB adaptée au catalogue — 2026-09-08

Le nombre de colonnes était écrit `MAX_COLS = 3  # 3x3 Grid (9 modules)` alors que le
catalogue en compte **dix** : le commentaire décrivait un catalogue qui n'existait plus.
📏 Mesuré avant correctif, distribution des tuiles par rangée : **`{0: 3, 1: 3, 2: 3, 3: 1}`** —
la dixième seule sur une quatrième rangée.

`hub_grid_columns()` (dans `certus/core/certus_hub_config.py`, fonction pure, aucune
dépendance Qt) dérive désormais le nombre de colonnes du catalogue, sous une règle
**objective et non esthétique** : *aucune rangée ne porte une tuile seule pendant que les
autres sont pleines*. Dix modules donnent 2 rangées de 5.

Garde-fou : `tests/ui/test_ux_hub_grid.py`, 17 tests — la règle pure balayée de 2 à 16 modules,
plus la distribution réellement rendue par la fenêtre. Vérifié **échouant sur le code
d'avant** : `17 failed`. Après : `17 passed`, et `43 passed` sur le périmètre HUB.

🔑 **Le compte de colonnes n'est plus une valeur à maintenir** : ajouter un onzième module ne
peut plus rouvrir le défaut.

#### ✅ Les panneaux de journaux repliables — 2026-09-08

⚠️ **Le dossier se trompait sur la cause, et la mesure a trouvé autre chose.** Il annonçait que
« Show Details » basculait *un autre widget* ; en réalité il basculait le bon. Le défaut réel :
`CertusLogPanel(visible=False)` **n'appliquait le drapeau qu'au widget de texte interne**, pas
au panneau. Le HUB affichait donc en permanence un en-tête « PROCESS LAUNCH LOGS » vide, avec
son bouton de bascule décoché.

**Deux correctifs, et le second est né d'une régression que j'ai introduite :**

1. `CertusLogPanel` applique désormais `visible` à lui-même.
2. 🔴 **Cela a cassé STRAT**, dont la bascule ne rendait visible que `log_text` : un parent
   masqué garde ses enfants masqués, donc plus rien ne s'ouvrait. `on_toggle_details` bascule
   maintenant le panneau. **Le garde-fou a attrapé la régression avant qu'elle ne sorte** —
   c'est exactement ce pour quoi il existe.

Les cinq autres modules construisent leur panneau en `visible=True` : **inchangés**, vérifié.

Garde-fou : `tests/ui/test_ux_hub_commands_do_something.py`, 4 tests (HUB + STRAT). Vérifié
échouant avant : `1 failed, 2 passed`, puis `1 failed, 3 passed` sur la régression STRAT.
Après : `4 passed`.

📏 **Référence du squelette mise à jour, avec son diff (règle R12)** — retrait chirurgical, pas
de régénération globale qui aurait pu figer un état dégradé :

```
CERTUS_HUB     7 -> 6 controles   (retire : 'QPushButton|Copy Logs')
CERTUS_STRAT  34 -> 33 controles  (retire : 'QPushButton|Copy Logs')
les 9 autres modules            : inchanges
```

C'est légitime : le bouton n'a pas disparu du code, il est derrière une bascule qui
fonctionne. **Les 11 squelettes passent** (`11 passed in 81 s`).

#### ✅ Le préfixe technique dans les libellés — sans objet, 2026-09-08

Le dossier accusait `card_title = f"[{idx + 1}] {title}" if idx < 9 else title`. 📏 Vérifié :
**cette ligne n'existe plus**, et aucun libellé de tuile ne porte de préfixe d'index. Le HUB
n'installe par ailleurs aucun raccourci de lancement numéroté, donc le grief « le 10ᵉ module
n'a ni numéro ni raccourci » n'a plus d'objet non plus. **Rien à corriger.**

#### 🔵 La bande des fichiers récents — arbitrage à rendre, pas un correctif

📏 Constat confirmé : `_on_recent_config_selected` ne fait qu'un `_log_message`. Cliquer un
fichier récent n'ouvre rien — et depuis que le panneau de journaux est honnêtement masqué,
le message lui-même est invisible.

🔴 **Mais la correction évidente n'est pas déterminable, et je ne l'invente pas.** Les récents
sont classés par **type de fichier** (`file.config`, `file.spectrum`, `file.substrate`…), pas
par module d'origine — or DESIGN, STRAT et RE produisent tous des configurations JSON. Rien
dans le registre ne dit quel module doit rouvrir un `file.config` donné.

**Trois voies possibles, toutes des décisions de conception :**

1. enregistrer le module d'origine à l'écriture du récent, et rouvrir avec lui ;
2. proposer un choix au clic (petit menu « ouvrir avec… ») ;
3. retirer la bande du HUB et la laisser aux modules, qui savent ce qu'ils ouvrent.

👤 **À trancher.** En l'état, la bande promet plus qu'elle ne tient ; je la laisse telle
quelle plutôt que de câbler une heuristique qui ouvrirait parfois le mauvais module — sur un
logiciel de métrologie, c'est le genre de « presque juste » qui coûte cher.
| ✅ **Grille adaptée au catalogue** — fait le 2026-09-08 | `CERTUS_HUB.py`, `certus_hub_config.py` |
| ✅ **Le préfixe technique n'existe plus** — vérifié le 2026-09-08, affirmation périmée | `CERTUS_HUB.py` |
| 🔵 **La bande des fichiers récents demande un arbitrage** — voir ci-dessous | `CERTUS_HUB.py` |

### 4.3 — Saisie et lecture des grandeurs

| quoi | détail |
|---|---|
| ✅ **Validateurs posés** — fait le 2026-09-08, voir ci-dessous | |
| ✅ **Booléens en cases à cocher** — fait le 2026-09-08, voir ci-dessous | |
| ✅ **Identifiants techniques retirés des libellés** — fait le 2026-09-08, voir ci-dessous | |
| ✅ **La vue scientifique de STRAT n'est plus déformée** — palier 1 fait le 2026-09-08. Le passage à pyqtgraph (zoom, curseur, lecture de valeur) reste hors plan | voir ci-dessous |
| ✅ **Plus un seul contrôle muet dans la suite** — fait le 2026-09-08, voir ci-dessous | |

**Le §4.3 est clos.** 🔵 Un seul point reste ouvert et il n'est **pas** un correctif : les
*plages* des champs numériques. Aucune borne n'existe dans le code, donc les poser serait
inventer une contrainte métier — c'est un arbitrage de 👤.

#### ✅ Un graphe vide dit qu'il est vide — 2026-09-08

Ouvert sans données, SMOOTHER montrait un axe « Wavelength (nm) » gradué **de 0 à 1** et un axe
« Amplitude » de 0 à 1, sans un mot. Ces graduations sont la plage par défaut de Qt, pas une
mesure — mais elles **se lisent** comme une mesure : la fenêtre paraît afficher des données
alors qu'elle n'en affiche aucune.

`update_plot` sortait immédiatement quand rien n'était chargé, laissant le graphe muet. Il
affiche désormais une note centrée, retirée dès qu'une courbe réelle est tracée.

📌 **Le composant d'état vide du projet ne convenait pas ici** : `attach_empty_state_to` cible
les vues à modèle (tables), pas un graphe pyqtgraph. La note est donc un `TextItem`, dans le
graphe lui-même.

Garde-fou : `tests/ui/test_ux_smoother_empty_state.py`, 3 tests — dont un contrôle négatif
(la fenêtre s'ouvre bien sans données) et, surtout, un test que **la note disparaît** une fois
des données tracées : une note d'état vide laissée par-dessus une vraie courbe serait pire que
son absence. Avant : `2 failed, 1 passed`. Après : `3 passed`, puis `17 passed` sur SMOOTHER.

#### ✅ Onze contrôles muets ont retrouvé la parole — 2026-09-08

📏 Mesuré : **SMOOTHER 7 contrôles sans info-bulle**, **SUBSTRATE INDEX 4**. Chaque texte est
**déduit de ce que le widget fait réellement** — le slot auquel il est connecté, la plage qu'il
déclare — et non de ce qu'il semble faire. Les bornes citées pour les deux champs de longueur
d'onde (100 à 20000 nm) sont lues dans leur `setRange`, pas estimées.

*Une info-bulle seulement plausible est pire qu'absente : elle sera crue.* Aucun rôle n'est
resté obscur ici, donc aucun contrôle n'a été laissé de côté.

Garde-fou : `tests/ui/test_ux_orphan_modules_tooltips.py`, 4 tests, avec contrôle négatif. Il
exclut le champ interne des boîtes à flèches — Qt le crée, l'opérateur voit la boîte, et Qt y
affiche déjà l'info-bulle du parent. Avant : `2 failed` avec les 11 contrôles nommés. Après :
`4 passed`.

#### ✅ Deux boutons ne se disputent plus le mot « Help » — 2026-09-08

⚠️ **Le dossier ne voyait qu'un module ; la mesure en trouve six.** DESIGN, STRAT, RE, INDEX,
FIELD **et** SMOOTHER affichaient deux boutons libellés « Help ».

🔑 **Et ce ne sont pas deux fois le même cas** — les traiter pareil aurait détruit du contenu :

| cas | constat | geste |
|---|---|---|
| DESIGN, STRAT, RE, INDEX, FIELD | le bouton de la barre d'actions ouvre **la même** documentation que le chrome de fenêtre, joignable par F1 | **vrai doublon → retiré** |
| SMOOTHER | son bouton affiche un **court guide d'usage**, pas la documentation | **renommé « Quick guide »**, rien n'est perdu |

Le renommage retire au passage un pictogramme d'un libellé utilisateur.

Garde-fou : `tests/ui/test_ux_no_duplicate_help.py`, sur **les onze fenêtres**, avec contrôle
négatif ; il neutralise les pictogrammes avant de comparer, pour que « ❓ Help » et « Help » ne
paraissent pas distincts. Avant : `6 failed, 16 passed`. Après : `22 passed`.

📏 **Référence du squelette (règle R12)** :

```
CERTUS_DESIGN  120 -> 119   CERTUS_STRAT  33 -> 32   CERTUS_RE  36 -> 35
CERTUS_INDEX    51 ->  50   CERTUS_FIELD  58 -> 57
CERTUS_SMOOTHER 15 ->  15   (bouton renomme, aucun controle perdu)
```

**Les 11 squelettes passent**, cliquets inclus (`18 passed, 2 xfailed`).

#### ✅ SMOOTHER ne mélange plus deux langues — 2026-09-08

Les niveaux de filtrage s'offraient en français dans une interface anglaise
(« Filtering Mode: Moyen »), et le choix était renvoyé en « [ Niveau: … ] ». Deux langues dans
une même fenêtre est un défaut de cohérence, pas de traduction : l'opérateur ne peut pas savoir
si les mots français désignent un réglage différent.

🔴 **Le piège, et il a failli coûter cher.** Cette valeur n'est **pas** qu'un libellé : elle est
passée telle quelle à `smooth_spectrum_auto(level=…)`. La renommer à l'aveugle aurait changé
les paramètres de lissage retenus par le moteur — un résultat différent, sans un mot.

📏 **Vérifié avant de toucher quoi que ce soit** : `_choose_params` accepte **déjà les deux
orthographes** — `{"faible", "low"}`, `{"moyen", "medium"}`, `{"fort", "high"}`. Le renommage
est donc sans effet sur le calcul, **et le garde-fou le démontre** au lieu de le supposer : il
compare les paramètres rendus pour chaque paire de noms, et vérifie que **tout niveau proposé
par la liste déroulante est reconnu par le moteur** — sinon il retomberait sur son défaut.

Garde-fou : `tests/ui/test_ux_smoother_language.py`, 9 tests, avec contrôle négatif. Vérifié
échouant avant : `4 failed, 5 passed` — et les 5 qui passaient étaient précisément ceux qui
prouvaient l'innocuité du renommage. Après : `9 passed`, puis `22 passed` avec le squelette.

#### ✅ Le plancher de 24 px s'applique enfin partout — 2026-09-08

📏 **Mesuré, et le dossier se trompait sur l'ampleur.** Il annonçait « 5 boutons sans info-bulle
sur 5 » et des boutons de 20 px un peu partout dans ces deux modules. En réalité, sur les onze
fenêtres, il ne restait **que deux boutons** sous le plancher — un par module, tous deux
`Copy Logs`, à **21 px** et non 20.

Ils viennent du même endroit : `CertusLogPanel`, un composant partagé **antérieur au harnais qui
mesure le plancher**. Corrigé à la source, donc pour tout module qui l'utilisera.

Garde-fou : `tests/ui/test_ux_button_min_height.py`, sur **les onze fenêtres**, avec un
contrôle négatif sur le plancher lui-même. Il lit `BUTTON_MIN_H` **dans le harnais**, si bien
qu'il ne peut pas diverger de la valeur que l'audit rapporte. Vérifié échouant avant :
`2 failed, 10 passed` — exactement les deux modules jamais audités. Après : `12 passed`.

#### ✅ Plus d'identifiant technique dans un libellé — 2026-09-08

Un en-tête de colonne, un titre d'onglet ou de carte est lu par un opérateur, pas par le
programme. Six fuites corrigées, de trois natures :

| ce qui s'affichait | ce qui s'affiche | nature |
|---|---|---|
| un préfixe interne devant le titre d'une carte | le titre seul | clé interne visible |
| les bornes de longueur d'onde, sans unité, sous leur nom de variable | `λ min (nm)` / `λ max (nm)` | clé interne **et** unité manquante |
| le symbole de longueur d'onde écrit en toutes lettres, 4 fois | `λ`, comme FIELD l'écrit déjà | même grandeur, deux noms selon la fenêtre |
| un en-tête d'angle aux parenthèses vides | `Angle (°)` | symbole perdu, même famille que « 01 scale » |

🔑 **Vérifié avant de renommer** : ces chaînes sont passées à `setHorizontalHeaderLabels`, donc
purement d'affichage — le code lit ses colonnes **par index**. Un renommage ne casse rien.

Garde-fou : `tests/ui/test_ux_no_technical_identifiers.py`, 6 tests, **statique** — il lit les
libellés remis à Qt dans les sources, ce qui est exhaustif et ne coûte aucune construction de
fenêtre, là où parcourir les onze fenêtres coûterait des minutes et manquerait les onglets
construits paresseusement. Avec contrôle négatif et un test « y a-t-il seulement des libellés à
inspecter ». Vérifié échouant avant : `3 failed, 3 passed`. Après : `6 passed`.

📏 **Référence du squelette : renommage, aucun contrôle retiré** (règle R12) :

```
CERTUS_DESIGN  120 controles, inchange -- l'onglet est renomme
CERTUS_RE       36 controles, inchange -- l'onglet est renomme
```

**Les 11 squelettes passent** (`11 passed in 80 s`).

#### ✅ Les champs numériques refusent ce qui n'est pas un nombre — 2026-09-08

📏 **Mesuré avant : 48 champs de saisie sans aucun validateur.** Le lecteur les parse avec
`float(text)` et, en cas d'échec, retombe sur une valeur par défaut **en silence** : l'écran
montre ce que l'opérateur a tapé, le moteur utilise autre chose.

🔑 **Le tranchant, c'est la virgule décimale.** Sur un clavier français, `1,5` est la façon
naturelle d'écrire un et demi — et `float("1,5")` lève. La valeur était donc abandonnée sans un
mot. Le validateur est posé en **locale C**, ce qui rend la saisie de la virgule impossible au
lieu de la laisser produire un run faux.

⚠️ **Ce qui n'est PAS fait, et pourquoi.** Les **plages** numériques ne sont pas posées. J'ai
cherché : **aucune borne n'existe dans le code** — ni contrainte pydantic sur ces réglages, ni
`setRange`, ni validation côté moteur. Les inventer sur des paramètres physiques serait pire
que leur absence. Le contrat vérifié est celui que le code énonce réellement : *tout ce que le
champ accepte, son lecteur doit savoir le lire.*

Une exception nommée : `robustness_noise_factors` contient une **liste** (« 0.5,1,2 ») ; un
validateur numérique y aurait interdit une saisie valide. Elle est déclarée dans
`LIST_VALUED_SETTINGS`, et le garde-fou vérifie qu'elle accepte toujours sa liste.

Garde-fou : `tests/ui/test_ux_numeric_field_validators.py`, 8 tests — dont un contrôle négatif
(assez de champs pour que le test ne soit pas vide) et un test que le validateur **n'interdit
pas** une valeur valide. Vérifié échouant avant : `1 failed, 7 passed`, avec les 48 champs
nommés. Après : `8 passed`, puis `62 passed` sur le périmètre STRAT.

📌 Quatre champs échappaient à la fabrique commune (`l0`, `nH_r`, `nL_r`, `nSub_custom`) : la
pose du validateur est factorisée dans `_as_numeric_field()` plutôt que recopiée quatre fois.

#### ✅ Plus un seul contrôle muet dans toute la suite — 2026-09-08

Ce plan portait **« 19 champs sans info-bulle »**. Le chiffre était périmé et personne ne
l'avait recompté. 📏 Mesure réelle, `scripts/sonde_controles_muets.py`, sur les onze fenêtres :

```
CERTUS_HUB               0 mute /   6      CERTUS_INDEX_SPLINE    0 mute /  46
CERTUS_DESIGN           12 mute /  81  <-  CERTUS_FIELD           0 mute /  37
CERTUS_STRAT             0 mute /  24      CERTUS_SMOOTHER        0 mute /  15
CERTUS_RE                0 mute /  25      CERTUS_SUBSTRATE_INDEX 0 mute /  15
CERTUS_INDEX             0 mute /  31      CERTUS_METAL_SINGLE    0 mute /  28
                                           CERTUS_METAL_BILAYER   0 mute /  38

TOTAL  12 mute control(s) out of 346
```

**12, pas 19 — et toutes dans une seule fenêtre, toutes le même widget** : les douze champs
d'indice de la carte *Materials* de DESIGN, six matériaux × deux longueurs d'onde. Tout le
reste était déjà à zéro. Un chiffre agrégé faisait croire à un travail dispersé sur toute la
suite ; le détail montre une famille unique et un correctif unique.

🔑 **L'info-bulle n'est pas rédigée, elle est dérivée** — la longueur d'onde vient de l'en-tête
de colonne du tableau, les bornes sont relues sur le widget lui-même. Ni l'une ni l'autre ne
peut donc contredire ce que l'opérateur voit ou ce que le champ accepte réellement. C'est la
règle du §4.4 poussée d'un cran : *une info-bulle seulement plausible est pire que pas
d'info-bulle, parce qu'on la croira.*

Garde-fou : `tests/ui/test_ux_no_mute_controls.py`, 22 tests — la même question posée aux onze
fenêtres, avec un contrôle négatif par fenêtre. Vérifié échouant avant : `1 failed, 21 passed`,
les douze champs nommés. Après : `26 passed` avec le garde-fou des modules orphelins.

📌 Il **subsume** `test_ux_orphan_modules_tooltips` sans le remplacer : celui-ci porte
l'histoire des deux modules jamais audités et sa propre exclusion documentée du champ interne
des compteurs.

#### ✅ Les sept booléens sont des cases à cocher — 2026-09-08

Sept réglages de STRAT étaient des interrupteurs tapés dans un champ texte libellé « (0/1) » :
biais de fente, recherche de fente, mode Rate et les quatre drapeaux SYM. Rien n'empêchait de
saisir `2`, `oui` ou rien du tout — et rien ne disait ce qui se passait alors.

🔑 **Le remplacement ne pouvait pas être un simple changement de classe.** Toute la couche de
réglages lit les widgets par `.text()` (`_get_float_safe`), et une `QCheckBox` y renvoie son
**libellé**. Un échange naïf aurait donc envoyé au moteur une valeur par défaut pendant que
l'écran affichait le choix de l'opérateur — *un résultat faux qui a l'air juste*, exactement ce
que ce dépôt traque.

`CertusBooleanField` (dans `certus_ui_widgets_factory.py`) préserve donc le contrat complet.
**Trois exigences implicites ont été découvertes une par une, chacune par un échec du
garde-fou** — et non par lecture du code :

| exigence | découverte par |
|---|---|
| `.text()` / `.setText()` en « 1 » / « 0 » | conçu d'emblée |
| signal `textChanged` | `AttributeError` à la construction de la fenêtre |
| `setReadOnly()` | `AttributeError` sur `sym_enable`, forcé actif |

**La détection est faite sur le libellé** : `"(0/1)" in label_text`. Ce libellé *est* la
déclaration qu'un réglage est un interrupteur — ajouter un booléen ne peut donc pas
réintroduire un champ texte par omission. Le « (0/1) » est retiré de l'étiquette affichée,
devenu inutile, et le nom accessible est posé.

Garde-fou : `tests/ui/test_ux_boolean_fields.py`, 29 tests (type, contrat de lecture, réaction
au clic, libellé). Vérifié échouant avant : `14 failed, 15 passed`. Après : `29 passed`, puis
`54 passed` sur le périmètre STRAT (squelette, fumée, cliquet UX).

📏 **Aucune référence à mettre à jour** : les sept champs ne figuraient pas dans le squelette de
STRAT — vérifié, `skeleton[CERTUS_STRAT]` passe inchangé.

#### ✅ La vue scientifique de STRAT — palier 1, 2026-09-08

Le graphe principal de STRAT est un `QLabel` nourri d'un pixmap, construit avec
`setScaledContents(True)` : l'image était **étirée pour remplir le widget, sans conserver le
rapport d'aspect**. Sur un logiciel de métrologie ce n'est pas cosmétique — une courbe déformée
représente mal les grandeurs qu'elle existe pour montrer, et la déformation **change avec la
taille de la fenêtre**, donc deux captures du même run se contredisent.

🔴 **Le drapeau était réappliqué à chaque rafraîchissement** (`_apply_pixmap`) : le défaut
revenait après chaque mise à jour du graphe. Corriger la seule construction n'aurait rien donné.

⚠️ **Et « une ligne » n'aurait pas suffi.** Passer le drapeau à `False` seul **rogne** un plot
plus grand que le widget — on troquait un défaut contre un pire. Le correctif ajuste donc
l'image à la taille du label **en conservant le ratio** avant de l'appliquer.

Garde-fou : `tests/ui/test_ux_strat_plot_not_stretched.py`, 4 tests avec contrôle négatif.
Vérifié échouant avant : `3 failed, 1 passed`. Après : `4 passed`, puis `22 passed, 1 xfailed`
sur le périmètre STRAT (squelette, part de zone graphique, fumée).

📌 **Un de mes tests ne prouvait rien au départ** : il vérifiait le ratio du pixmap *stocké*,
que `setScaledContents` ne modifie pas — il passait donc avant comme après. Remplacé par un
test qui vérifie qu'un plot surdimensionné est **ajusté sans rognage ni distorsion**.

### 4.4 — Les deux modules jamais audités

SMOOTHER et SUBSTRATE INDEX n'ont reçu aucun correctif de la suite. Retenu :

- ✅ **langue alignée** — fait le 2026-09-08, voir ci-dessous ;
- ✅ **ambiguïté des boutons d'aide levée** — fait le 2026-09-08, voir ci-dessous ;
- ✅ **plancher de 24 px sur les boutons** — fait le 2026-09-08, voir ci-dessous ;
- ✅ **info-bulles** — fait le 2026-09-08, voir ci-dessous ;
- ✅ **état vide** — fait le 2026-09-08, voir ci-dessous.

**Le §4.4 est clos.**

### ✅ 4.5 — campagne « pas de valeur en dur » : close par la mesure, 2026-09-08

📏 **État mesuré** : **310 hexadécimaux** hors du thème, sur 44 fichiers, et **157 tailles de
police** — les deux exactement au niveau de leur cliquet (`test_ux_design_system`).

🔑 **La question n'était pas « combien en reste-t-il » mais « lesquels font du mal ».**
`scripts/sonde_contraste_en_dur.py` (posée ce jour) cherche les feuilles qui écrivent **un
fond et un texte tous deux en dur** et calcule leur contraste — le critère objectif qu'avait
utilisé la première passe de 3.10.

```
=== Couleurs en dur dont la paire fond/texte tombe sous WCAG AA ===
    seuil 4.5:1 · controle negatif : 🟢 il mord

  aucune paire en defaut.
```

**Aucune.** Les 310 restants sont des couleurs de **données** (marqueurs de courbe, codes de
statut), des consoles à fond sombre au contraste excellent, et des accents. Les router vers le
thème serait un refactor mécanique **sans gain mesurable** — et, sur les couleurs de courbes,
une erreur : une couleur de donnée n'est pas un jeton d'interface.

⚠️ **Angle mort assumé, écrit dans la sortie de la sonde** : seules les paires posées sur une
même ligne sont vues. Un fond et un texte séparés lui échappent.

**Ce qui resterait, si on y revient un jour** : la cohérence de thème pure — trois consoles de
`certus_manual_sigma_knot_dialog.py` restent sombres en mode clair. C'est de l'esthétique, donc
hors du périmètre retenu (renoncement n° 6).

### 🔵 Unification des unités typographiques — en cours depuis le 2026-09-08

👤 **Arbitrage rendu : unifier en points, sur l'échelle du thème.**

📏 **Le défaut, mesuré** : 157 tailles en dur, dont **127 en pixels** et 30 en points, alors que
le thème raisonne en points (base 10 pt = **13,3 px** à 96 dpi). Conséquence : `font-size: 11px`
se lit « un peu plus de 10 » et vaut en réalité **0,82× la base**. Cette valeur revient
**56 fois**. La majorité des libellés de la suite sont donc plus petits que la base sans que
personne l'ait décidé.

⚠️ **Correction d'un chiffre que j'avais annoncé** : j'ai dit « environ +20 % ». Router `11px`
vers `BODY_LG` (11 pt) porte le rendu de 11 à 14,7 px, soit **+33 %**. C'est plus, et c'est
pourquoi la conversion se fait par tranches avec mesure géométrique à chaque fois.

**Règle appliquée** : seules les valeurs qui **ont un jeton** dans l'échelle sont routées
(8, 9, 10, 11, 12, 14, 18, 24). `16px`, `28px`, `48px` n'en ont pas — l'échelle s'arrête à
24 pt — et les convertir serait une invention : **laissées telles quelles**.

**Tranche 1 — `certus_ui_widgets_cards.py`** (composant partagé, donc effet visible dans
plusieurs fenêtres) : 6 tailles routées vers `Typography`. 📏 Contrôle géométrique après
conversion — c'est le risque réel de cette étape :

```
test_ux_no_horizontal_scroll · test_ux_plot_area_share · test_ux_design_system
34 passed, 3 xfailed in 267.37s
```

**Aucun débordement, aucune perte de zone graphique.** Cliquet resserré du nombre exact,
**157 → 151**, pour qu'une valeur retirée ne donne pas du mou aux autres.

**Tranche 2 — `certus_ui_widgets_progress.py` + `certus_re_layout_mixin.py`** : 18 tailles
routées (10, 11, 12, 14 px), une chaîne passée en f-string. Contrôle géométrique élargi au
squelette de RE :

```
test_ux_no_horizontal_scroll · test_ux_plot_area_share · test_ux_design_system · skeleton[RE]
35 passed, 3 xfailed in 286.74s
```

Cliquet resserré **151 → 133**.

📌 Au passage, cette passe a produit un `worker produced no result on attempt 1 [...] succeeded
on attempt 2` : **le correctif de reprise du §3 travaille en conditions réelles**, et un aléa
qui aurait fait échouer la mesure a été absorbé sans bruit.

**Tranche 3 — 5 fichiers** (`certus_index_spline_common`, `certus_base_app`,
`certus_strat_welcome_ui`, `certus_index_spline_rendering`, `certus_index_ui_layout`) :
31 tailles routées. `34 passed, 3 xfailed`. Cliquet **133 → 102**.

**Tranche 4 — 7 fichiers** (widgets partagés, `certus_overview_tab`, `certus_substrate_ui`,
SPLINE, `certus_strat_ui_layout`) : 26 tailles routées. Contrôle élargi aux garde-fous
d'instanciation : `52 passed, 3 xfailed`. Cliquet **102 → 76**.

⚠️ **Deux incidents pendant ces tranches, tous deux instructifs :**

1. **Mon utilitaire a cassé un fichier.** Son ancre d'import a matché
   `from certus.core.certus_core import (` — un import **multi-ligne** — et l'insertion a coupé
   la parenthèse : `certus_substrate_ui.py` ne compilait plus. `ruff check` l'a signalé
   immédiatement (`invalid-syntax`), le fichier a été réparé et l'ancre corrigée pour refuser
   toute ligne d'import se terminant par `(`.
2. **Un contrôle a été tué par un arrêt natif** (sortie tronquée sur `Thread 0x`) : c'est
   l'anomalie A4 du relevé de reproductibilité, pas une régression. Relancé : `52 passed`.

**Tranche 5 — 17 fichiers, 24 tailles** : tout le reliquat, dispersé à raison de 1 à 2 par
fichier. Contrôle élargi : `52 passed, 3 xfailed`.

### ✅ Campagne typographique CLOSE — 2026-09-08

| | valeur |
|---|---|
| cliquet | **173 → 157 → 151 → 133 → 102 → 76 → 52** |
| tailles encore routables | **0** |
| tailles **hors échelle** (13, 16, 17, 20, 28, 39, 48…) | 22 — *délibérément laissées* |
| tailles déjà en points | 30 |

🔑 **52 est le plancher, et il est atteint.** Ce n'est pas zéro, et ce ne doit pas l'être :
22 valeurs n'ont aucun jeton dans l'échelle, 30 étaient déjà correctes. Descendre plus bas
exigerait **d'étendre l'échelle elle-même** — une décision de conception, pas un nettoyage.

**Ce que la campagne a réellement corrigé** : `font-size: 11px` se lisait « un peu plus de 10 »
et valait 0,82× la base. Les libellés de la suite étaient donc plus petits que la base sans
que personne l'ait décidé. Ils suivent maintenant l'échelle, et **un seul endroit** la définit.

📏 **Aucune régression géométrique sur les cinq tranches** — c'était le risque réel, puisque le
rendu de ces libellés augmente de ~33 % : `test_ux_no_horizontal_scroll`,
`test_ux_plot_area_share` et les garde-fous d'instanciation sont restés verts à chaque passe.

⚠️ **Reste à faire, et cela vous revient** : *regarder les onze fenêtres à l'écran*. Les tests
prouvent qu'aucun contrôle ne déborde ; ils ne disent rien de l'équilibre visuel. Le dossier
avait raison sur ce point — « ça se décide les yeux sur un écran ».

---

### 4.6 — Ergonomie métier : les deux points que le §4 n'avait pas absorbés

L'ancienne phase 5 du dossier comptait neuf points. **Six étaient déjà traités** par les
sections ci-dessus — identifiants techniques, booléens, validateurs, vue STRAT palier 1,
info-bulles, en-têtes en capitales — et un septième (précisions numériques hétérogènes) est
rangé en cosmétique au §5. Restaient les deux ci-dessous, et le premier n'était pas ce qu'il
annonçait.

#### ✅ Le bandeau de tête de STRAT — un point annoncé, quatre défauts trouvés — 2026-09-08

Le dossier reprochait au bandeau d'afficher `ROBUSTNESS SCORE` là où `CLAUDE.md` §22 pose le
**SEEL** comme *« la seule grandeur à rapporter — jamais le RMSE brut »*. En lisant
`_refresh_synthesis_kpis` **contre la forme que le solveur émet réellement**
(`_finalize_robustness_results`), trois autres défauts sont apparus dans les mêmes neuf lignes.

| # | défaut | portée |
|---|---|---|
| 1 | 🔴 `PLACEHOLDER` **n'était pas importé** dans le module — qui l'emploie trois fois. Le module est servi par un `import *` qui ne le ré-exporte pas | `NameError` à **chaque** fin de run |
| 2 | `n_blocks` lu à la racine du résultat, où il n'existe pas : il vit dans `["strategy"]` | toujours `None`, donc c'est **ce chemin qui déclenchait le n° 1** |
| 3 | la gagnante prise comme `strategies[0]`, court-circuitant `select_best_strat_result` — l'aide écrite précisément parce qu'*« un payload partiellement rempli peut garder un zéro de remplissage en tête »* | le bandeau pouvait titrer sur une stratégie qui n'a pas gagné |
| 4 | pas de SEEL | on lisait un score de classement à six décimales, pas une erreur en nanomètres |

🔴 **Le n° 1 ne s'arrête pas à l'affichage, et c'est le vrai coût de cette étape.** `NameError`
n'est pas dans la clause `except` de la fonction : l'exception **remonte** et interrompt
`on_workflow_finished` avant sa ligne 584 — **l'export automatique Excel + HTML**. Après un run
qui dure de 25 min à 2 h 39. Le bandeau affichait donc le score et le taux de plantage, puis
s'arrêtait net : ni le nombre de blocs, ni le nombre de stratégies classées, ni même
« Run complete ».

🔑 **Le SEEL est DÉRIVÉ, pas recalculé.** Exactement comme le fait déjà le tableau des
résultats : le facteur et l'exposant viennent de l'ajustement que l'étape 0 laisse dans le
contexte applicatif, appliqués à l'erreur au niveau de bruit **nominal**. Sans cet étalonnage
le champ **reste vide** — un chiffre de tête inventé à partir d'un étalonnage absent est
précisément le mode d'échec que ce dépôt traque.

⚠️ *La docstring de la fonction affirmait que l'absence du SEEL était « délibérée : il
n'atteint jamais ces résultats ». C'était vrai de la première moitié de la phrase et faux de
la conclusion — le tableau des résultats le dérivait depuis toujours, dix lignes plus loin dans
le même paquet.*

Garde-fou : `tests/ui/test_ux_strat_headline_number.py`, 6 tests, dont deux contrôles négatifs
et un test que le SEEL **reste vide** sans étalonnage. Vérifié échouant sur le code d'avant :
`5 failed, 1 passed`. Après : `6 passed`.

#### ✅ Une grandeur, une précision — 2026-09-08

Ce point était **rangé en cosmétique au §5**, sur la foi du constat du dossier : *« précisions
numériques incohérentes dans une même vue DESIGN : RMSE 6 décimales, épaisseur 1, indice 3,
QWOT 5, poids 1 »*. 👤 a demandé de le traiter, et la mesure a montré que **le constat visait
la mauvaise chose**.

🔑 **Sept formats différents ne sont PAS un défaut.** Une épaisseur en nanomètres et un indice
de réfraction n'ont aucune raison de partager un nombre de décimales ; les y forcer serait pire.
📏 Le vrai défaut, mesuré sur les 79 sites de formatage de DESIGN, est **une même grandeur
rendue de deux façons** :

```
RMSE, 14 sites :  10 a .6f   ·   4 a .5f
  certus_design_ui_plot.py:133/135/137   .6f   best_rmse, best_mc, best_fab   <- le rapport texte
  certus_design_ui_plot.py:326/339/355   .5f   les MEMES trois champs         <- le tableau
```

Ce sont **les trois mêmes champs du même enregistrement**, dans **le même module**, rendus à
six décimales dans le rapport et à cinq dans le tableau construit à partir de lui. L'opérateur
lit `0.002733` d'un côté et `0.00273` de l'autre, sans rien qui dise que c'est le même nombre.
Le quatrième site est un export qui écrit la même grandeur **deux fois, de deux façons**, à
88 lignes d'intervalle.

Unifié sur `.6f`, la précision déjà employée par le bandeau, l'étiquette de tête, le journal
et le rapport — 10 sites contre 4.

⚠️ **Ce qui n'est PAS tranché ici, et qui ne m'appartient pas** : *combien* de décimales un
RMSE mérite. `CLAUDE.md` §24-26 a mesuré une dispersion Monte-Carlo de **~6 %** ; six décimales
la surestiment de plusieurs ordres de grandeur, et le bon affichage serait sans doute en
chiffres significatifs. **C'est une question scientifique, pour 👤.** Le garde-fou n'assère que
l'unicité de la réponse, jamais sa valeur.

Garde-fou : `tests/ui/test_ux_numeric_precision_is_consistent.py`, 5 tests, **statique** — il
lit les sources, donc il ne peut ni être lent ni dépendre de Qt. Vérifié échouant sur le code
d'avant : `1 failed, 4 passed`, avec les 14 sites nommés. 🔑 **Et l'épaisseur minimale passait
déjà** : c'est le contrôle positif, il prouve que le détecteur sait aussi dire « cohérent »
plutôt que de condamner tout ce qu'il regarde.

📌 Deux contextes sont **exclus délibérément** : les **noms de fichiers** d'artefacts, dont le
renommage porte hors de l'interface, et `rmse_per_n × 1000`, qui est une autre grandeur sur une
autre échelle.

#### ✅ L'onglet multi-graines ne mélange plus deux langues — 2026-09-08

L'onglet était écrit en français — et en français **sans accents**, donc ni du français correct
ni de l'anglais : « realisation », « Duree », « deja mesuree ». Son bandeau annonçait
*« 1 realisation(s) **ont** trouve sur 4 »* : un verbe au pluriel sur un compte qui vaut très
souvent 1, et c'est **le chiffre le plus regardé de l'onglet**.

🔑 **Deux choses y ressemblent à des libellés et n'en sont pas** — c'est le piège du §4.4,
rencontré deux fois de plus :

| ce que ça a l'air d'être | ce que c'est |
|---|---|
| les deux entrées du menu « Objectif » | des **jetons de ligne de commande**. Le drapeau `--objectif` du script d'orchestration ne les accepte que sous leur forme française ; les renommer aurait fait rejeter la commande par `argparse` |
| le mot-clé de durée « nuit » | une **valeur acceptée** par l'analyseur de durée du script. Il est donc cité tel quel, et l'info-bulle dit que c'en est un |
| les états affichés dans le tableau | des **jetons internes** d'une machine à états pure, épinglés **par valeur** par `tests/unit/test_strat_multigraine_ui.py` |

La parade est la même dans les trois cas : **séparer le libellé de la valeur**. Le menu porte
un libellé anglais et garde le jeton français en donnée ; les états sont traduits **à
l'affichage** par une table, la machine à états et ses tests restant intacts.

⚠️ **Cinq assertions de `tests/unit/test_strat_multigraine_ui.py` épinglaient un MOT français**
pour une propriété qui, elle, tient toujours. Elles ont été mises à jour — le mot change, la
propriété vérifiée est la même — et chacune le dit désormais dans sa docstring. C'est
l'exception que la règle R11 prévoit : l'étape le nomme et dit pourquoi.

📌 **Ce qui n'est PAS fait, et c'est délibéré** : les identifiants, les commentaires et les
docstrings de ce module restent en français. Les renommer serait une refonte de 600 lignes, et
l'interdit n° 11 de `CLAUDE.md` vise le code, pas la langue de l'interface — laquelle est
« une question à poser au propriétaire du projet ». Seul l'**écran** a changé.

📌 **Trouvé au passage** : le paragraphe explicatif du bandeau était écrit à la construction
puis **écrasé aussitôt** par le premier rafraîchissement — il n'a jamais été vu. Il sert
maintenant d'**état vide**, ce qui lui donne enfin un emploi.

⚠️ **Piège d'outillage payé ici, et il faut le retenir** : éditer ce fichier avec l'éditeur
déclenche `ruff format`, qui a fait **deux** choses interdites — basculer tout le fichier de
CRLF en LF, et réécrire `except (A, B):` en `except A, B:`, une conversion que l'interdit n° 5
prohibe **explicitement**. Le fichier a été **remis à `HEAD` et refait entièrement par script**.
Diff final : 102 insertions / 62 suppressions, contre 139 / 83 avec le reformatage parasite.

Garde-fou : `tests/ui/test_ux_multiseed_tab_language.py`, 26 tests — les mots français
recherchés avec des **frontières de mot** (sinon « blocs » se déclencherait sur « Blocks »),
plus un test que le menu envoie toujours au script le jeton qu'il accepte, plus la grammaire du
décompte à 0, 1 et 3. Vérifié échouant avant : `19 failed, 7 passed`. Après : `121 passed` avec
les deux suites unitaires du module.

📌 **La référence du squelette a changé d'une ligne** — le titre de l'onglet. Retrait
chirurgical, aucune régénération : le compte de contrôles reste **28/28**, c'était un
renommage et pas une perte.

### 4.7 — 🔴 Le mode sombre était partiellement cassé, et personne ne l'avait vu

Trouvé le 2026-09-08 en instruisant la barre du bas du HUB (§4.2). Ce n'était pas un cas isolé.

📏 **Mesuré avec une préférence sombre**, `scripts/sonde_feuilles_figees.py` :

```
CERTUS_HUB       9 feuilles de widget sur 59 peignant des couleurs CLAIRES
CERTUS_DESIGN   34 sur 93
```

Parmi elles : la bande d'en-tête, la barre du bas, le panneau de journaux, les cartes de
valeurs, le bandeau d'indicateurs — et **`CertusThemeToggle`, le bouton qui bascule le thème.**

#### Le mécanisme, en deux temps

Une feuille de style posée sur un widget est une **f-string évaluée une seule fois**, pendant
sa construction. Il suffit donc que la palette soit fausse à cet instant pour que la couleur
soit figée à vie.

🔴 **Et la palette était remise au clair, par un défaut d'argument.**
`CertusTheme.apply_to_app(app, dark_mode=False)` — `False` **par défaut** — appelle
`configure("dark" if dark_mode else "light")`. **Quatre appelants ne passaient rien**, dont
`init_certus_app`, le bootstrap partagé, et `CERTUS_DESIGN.py` qui passait `False`
explicitement. Chacun **écrasait la préférence de l'opérateur** sans rien dire.

🔑 **Ma première hypothèse — « le thème est appliqué trop tard » — était vraie mais
insuffisante.** J'ai posé `configure_theme_from_preference()` au début de la construction ;
le HUB est passé de 7 à 0, **DESIGN est resté à 21**. C'est l'instrumentation qui a tranché :
les cartes se construisaient avec `SURFACE=#ffffff` *après* que la base eut posé `#111827`.
Quelque chose la réinitialisait entre les deux — le défaut d'argument. *Une hypothèse qui
explique la moitié des cas n'est pas la cause racine.*

#### ⚠️ Deux défauts se compensaient, et corriger l'un seul aggravait

La valeur d'une carte de statistiques est peinte avec `CertusTheme.TEXT` — **le seul jeton de
texte identique dans les deux modes**, un bleu nuit. Sur une carte figée en blanc, cela se lit
très bien. Dégeler la carte **sans** toucher au texte aurait donné du bleu nuit sur fond
sombre : **1,01:1, invisible**. La carte emploie désormais `TEXT_MAIN`, qui suit le thème —
comme le faisaient déjà son titre et son unité, sur `TEXT_SUB`.

📌 C'est le contre-exemple le plus net de la journée à *« un correctif ne peut pas empirer les
choses »*.

#### Résultat mesuré

```
                avant    apres
CERTUS_HUB          9        0
CERTUS_DESIGN      34        1
```

Le dernier site de DESIGN est un `#ffffff` employé comme **couleur de libellé** sur un bouton
coloré, ce qui est légitime : le garde-fou ne vise que `background-color`.

Garde-fou : `tests/ui/test_ux_dark_mode_is_not_frozen.py`, 6 tests, avec **deux contrôles en
sens inverse** — un widget peignant délibérément du blanc doit être vu, et un libellé blanc
sur fond sombre ne doit **pas** déclencher. Vérifié échouant sur le code d'avant :
`2 failed, 4 passed`, avec 7 et 21 widgets nommés. Après : `6 passed`, et `96 passed` sur les
dix garde-fous de thème et de palette.

⚠️ **Limite, et elle est réelle** : rien de tout cela ne fait suivre ces feuilles lors d'une
bascule de thème **à chaud**. Elles restent figées sur la palette du moment de la construction ;
seule une reconstruction les rafraîchit. C'est une limite préexistante, elle est inchangée, et
elle est maintenant écrite.

---

## 5. Ce qu'on abandonne, et pourquoi

C'est la partie qui rend ce plan tenable. **Chaque ligne est un renoncement assumé, pas un
oubli.** Si tu en refuses un, dis-le : il redevient une étape.

| abandonné | pourquoi |
|---|---|
| **La cible « premier centile mondial »** et la note « ≥ 8 sur 9 axes par fenêtre » | Une note d'ergonomie sur 10 n'est pas mesurable ; elle ne peut ni échouer ni réussir. Elle est remplacée par les critères binaires du §6. |
| **La chasse aux emoji dans les libellés** (une soixantaine) | Purement esthétique, et le coût est le pire du dossier : ~14 % du cliquet du squelette à régénérer, sur onze fenêtres, pendant que rien ne protège d'une faute de frappe. |
| **La normalisation exhaustive des libellés** (~73 littéraux) | Même mécanisme, même coût. On garde uniquement les chaînes qui **disent quelque chose de faux** (§4.1). |
| **Réaligner SMOOTHER et SUBSTRATE sur le modèle de fenêtre de la suite** | C'est une refonte, pas une correction. Leurs défauts bloquants sont couverts en §4.4. |
| **Le passage de la vue STRAT à pyqtgraph** | Palier 1 retenu, palier 2 hors plan : c'est un chantier, à décider séparément. |
| **La finition cosmétique** : styles de table incohérents, cartes qui coupent leur dernière rangée, en-têtes tronqués, onglets de synthèse vides, doubles espaces | Réel mais sans conséquence d'usage. À reprendre si le reste est fait. |
| ~~Les précisions numériques hétérogènes~~ | 🔴 **RETIRÉ de cette liste le 2026-09-08, sur demande de 👤 — et il avait raison de le sortir.** Une fois mesuré, ce n'était pas de la cosmétique : la **même** grandeur était rendue à cinq et à six décimales dans deux vues adjacentes du même module. Voir §4.6. *Le constat d'origine visait la diversité des formats, qui est légitime ; c'est pour cela qu'il avait été classé cosmétique.* |
| **La cible « 0 module sous 65 % de zone graphique en 1366 »** | 📏 Démontrée inatteignable par redimensionnement : plafonner le panneau de STRAT pousse 93 px de contrôles hors du viewport. **Des contrôles atteignables valent mieux qu'un graphe plus grand.** La cible honnête est **1**, et l'état est consigné en `xfail(strict=True)`. |

---

## 6. Ce qui vaut « fini »

Des critères binaires, vérifiables par une commande, sans jugement de goût.

| critère | cible | état au 2026-09-08 |
|---|---|---|
| passe complète reproductible sur 5 exécutions | oui | ✅ **14 passes sur 14**, §3 |
| **`0 failed` sur `tests/ui/ + tests/unit/`** | oui | ✅ **0 échec**, mesuré le 2026-09-08 — mais **en trois commandes, pas une** : `tests/unit/` **2 456 passed** en 2 min 58 · `tests/ui/` **92 % exécuté, zéro échec** puis tué par son plafond de 90 min · les 11 fichiers restants **51 passed** en 1 min 26. 🔑 **Tout a été exécuté et rien n'a échoué** ; ce qui manque est la capacité à l'obtenir d'un seul coup, et la cause est nommée juste au-dessus |
| en-têtes de table altérant un symbole physique | 0 | ✅ **0** — capitales retirées |
| lanceurs de l'accueil sans focus clavier ni nom accessible | 0 | ✅ **0** — §4.2 |
| commandes de l'accueil sans effet visible | 0 | ✅ **0** — « Scientific Documentation » est lisible, mesuré au pixel |
| paires WCAG en échec, en clair **et** en sombre | 0 | ✅ **0** — 🔑 mais le critère a **changé de sens** : il ne comptait que les paires **en dur dans le source**, et rendait 0 pendant que deux règles de la feuille livrée peignaient 2,54:1 et 2,77:1 en sombre. Il compte désormais les paires **peintes** |
| modules levant une exception à l'usage | 0 | ✅ **0** — recontrôlé le 2026-09-08 : `135 passed` sur `test_certus_suite_gui_guardrails` + `test_ui_module_imports` + `test_ux_close_during_run` + `test_ux_destructive_confirmations` |
| modules écrasant un fichier utilisateur sans confirmation | 0 | ✅ **0** — recontrôlé le 2026-09-08, `test_ux_destructive_confirmations` (dans la passe ci-dessus) |
| actions principales hors écran | 0 | ✅ **0** — recontrôlé le 2026-09-08 : `52 passed` sur `test_ux_no_horizontal_scroll` + `test_ux_skeleton` |
| tables d'empilement triables | 0 | ✅ **0** — recontrôlé le 2026-09-08, `test_ux_numeric_sorting` + `test_ux_sorting_never_corrupts_data` (dans la passe ci-dessus) |
| raccourcis morts | 0 | ✅ **0** — recontrôlé le 2026-09-08, `test_ux_declared_shortcuts_resolve` + `test_certus_shortcut_uniqueness` + `test_ux_standard_shortcuts` (idem) |
| champs numériques sans validateur | 0 | ✅ **0** — 48 corrigés ; les *plages* restent un arbitrage de 👤 (aucune borne dans le code) |
| boutons sous 24 px | 0 | ✅ **0** — vérifié sur les **onze** fenêtres. ⚠️ *Ce plan écrivait « 12 » à deux endroits : le périmètre est de **onze** modules, comptés dans `audit_ux_certus.MODULES`* |
| champs sans info-bulle | 0 | ✅ **0** — 🔑 le plan annonçait **19** ; la mesure en donnait **12**, toutes dans DESIGN. Corrigées |
| **feuilles de widget peignant la mauvaise palette** | 0 | ✅ **0** sur le HUB, **1** sur DESIGN, et ce dernier est un libellé blanc légitime. 🆕 Critère **ajouté le 2026-09-08** : il n'existait pas, et le défaut qu'il attrape était présent depuis le début (9 et 34) |
| **une grandeur, une précision** | 0 discordance | ✅ **0** — le RMSE était rendu à 5 et à 6 décimales dans deux vues adjacentes |
| modules sous 65 % de zone graphique en 1366 | 0 | 🟠 **1** — cible **démontrée inatteignable** : plafonner le panneau de STRAT pousse 93 px de contrôles hors du viewport. Consigné en `xfail(strict=True)`, la cible honnête est 1 (§5) |

**12 critères sur 13 atteints et mesurés. Le treizième est un renoncement argumenté, pas une
dette.**

🟢 **Les cinq critères « hérités » ne le sont plus.** Ils venaient du dossier d'origine, dont
cinq affirmations avaient déjà été démenties par la mesure ; les recopier sans les rejouer
aurait été le sixième démenti en attente. Chacun a son garde-fou dans le dépôt, donc les
recontrôler consistait simplement à les **exécuter** : `135 passed` puis `52 passed`, le
2026-09-08.

🔴 **Ce que ce tableau ne dit pas, et qu'il ne faut pas lui faire dire.** Treize critères
binaires ne font pas une interface du premier centile ; ils écartent ce qui la disqualifierait.
Il n'y a **aucun critère de goût** ici — densité, rythme, hiérarchie visuelle, cohérence des
formulations — et c'est délibéré (§5). **Le juge de ces questions est 👤 devant l'écran**, et
cette revue n'a pas eu lieu.

⚠️ **Deux critères ont changé de définition en cours de route, et c'est le fait le plus utile
du tableau :**

| critère | ancienne définition | ce qu'elle laissait passer |
|---|---|---|
| paires WCAG en échec | les paires écrites **en dur dans le source** | deux règles de la feuille livrée à 2,54:1 et 2,77:1 en sombre, parce qu'elles employaient un blanc littéral au lieu de leur jeton |
| commandes sans effet | un gestionnaire **branché** | un bouton parfaitement branché, mais peint **blanc sur blanc** |

🔑 **Dans les deux cas le compte affichait zéro et le défaut était à l'écran.** C'est la
règle R13 : *mesure ce qui est rendu, pas ce qui est déclaré.*

---

## 7. Où sont les preuves

- **Les affirmations que la mesure a réfutées**, et le mécanisme qui les rendait crédibles :
  [`UX_DEMENTIS.md`](UX_DEMENTIS.md). 🔑 **C'est le dossier le plus utile de ce chantier** :
  chacune de ces erreurs venait d'une mesure qui ne pouvait pas soutenir sa conclusion.
- **Le détail d'une étape close** : la **docstring de son garde-fou**. Elles portent ce qui a
  été mesuré, ce qui a été écarté et pourquoi — et elles ne peuvent pas se périmer sans que le
  test tombe, ce qu'aucun document ne garantit.
- **La reproductibilité de la passe complète, 15 passes** :
  [`MESURE_REPRODUCTIBILITE_2026-09-07.md`](MESURE_REPRODUCTIBILITE_2026-09-07.md).
- **Où on s'est arrêté, et la commande pour repartir** : [`REPRENDRE_ICI.md`](REPRENDRE_ICI.md).
- **Instruments** :

  | script | ce qu'il mesure |
  |---|---|
  | `scripts/audit_ux_certus.py` | le squelette des onze fenêtres. ⚠️ ne compte que les widgets **visibles** |
  | `scripts/sonde_libelles_visibles.py` | les libellés réellement affichés |
  | `scripts/sonde_couleurs_en_dur.py` | les couleurs échappant au thème |
  | `scripts/sonde_contraste_en_dur.py` | les paires fond/texte **écrites en dur** sous AA |
  | `scripts/sonde_bouton_documentation.py` | 🆕 ce qu'un bouton **peint réellement** : couleurs dominantes et contraste encre/papier |
  | `scripts/sonde_controles_muets.py` | 🆕 les contrôles sans info-bulle, par fenêtre |
  | `scripts/sonde_feuilles_figees.py` | 🆕 les feuilles de style de widget **figées sur la mauvaise palette** — un mode par processus |

⚠️ **Cinq pièges de mesure établis, qui coûtent une journée chacun si on les oublie :**

1. Le harnais **épingle** une police depuis un correctif antérieur. Il ne peut donc rien dire
   de la typographie : l'instrument masque le défaut qu'il mesure. Une grandeur qui ne varie
   pas avec ce qui devrait la faire varier est un artefact.
2. Un jeu de captures a été pris sans polices résolues : tout le texte y est en boîtes.
   Il ne sert qu'à la géométrie — **n'y juge aucune typographie**.
3. 🆕 **Deux fenêtres construites dans un même processus ne se comparent pas.** Une fenêtre
   fige des jetons de thème dans des feuilles de style au moment où elle se construit ; la
   seconde hérite de l'état que la première a laissé. J'ai conclu « lisible en sombre » sur
   cette base, puis retiré la conclusion après remesure en **processus séparés**. Et ne pose
   pas le thème par `configure()` avant de construire : le chemin réel passe par la
   **préférence persistée**, et pré-configurer mesure un état que l'application n'atteint
   jamais.
4. 🆕 **La passe complète exige la machine pour elle seule.** 📏 Le 2026-09-08, une passe
   lancée pendant que des sondes Qt tournaient à côté a **calé à 20 % pendant 6 minutes** sur
   `test_ux_re_stop_when_idle` — un fichier qui passe en **6,9 s isolé**. Ce n'est pas une
   régression, c'est de la contention, et le §3 en avait déjà décrit la forme extrême
   (l'anomalie A4, pytest lui-même tué). **C'est la règle « une mesure, une machine » de
   `CLAUDE.md`, qui vaut aussi pour les tests** — et je l'ai enfreinte plusieurs fois ce
   jour-là. Corollaire : *une passe qui enjambe une édition n'est pas un verdict* ; deux ont
   dû être jetées.
5. 🆕 **L'encre d'un texte n'est pas sa couleur la plus fréquente.** L'anticrénelage rend le
   halo plus fréquent que le cœur du glyphe : mesuré ainsi, du noir sur blanc sort à **2,52:1**.
   L'encre est la couleur la **plus éloignée** du fond, et il faut écarter les pixels de
   bordure — une bordure sombre sur un fond pâle se lit sinon comme une lisibilité parfaite.
   *Ce défaut d'instrument a été trouvé par un contrôle positif, pas par un contrôle négatif :
   les deux sens sont nécessaires.*
