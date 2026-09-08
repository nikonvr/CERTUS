# UX — ce que la mesure a démenti

**Extrait le 2026-09-08 de `GEMINI_UX_TOP1_2026-09-04.md`, qui a été supprimé le même jour.**
Ce dossier-ci garde la seule chose que ce document avait d'irremplaçable : **les affirmations
qu'il portait et que la mesure a réfutées**, avec le mécanisme qui les rendait crédibles.

> Le plan actif est [`UX_PLAN.md`](UX_PLAN.md). **Ce dossier n'est pas un plan** : il ne
> contient aucune étape à faire, seulement des erreurs de jugement instruites, pour ne pas les
> refaire. Le parent supprimé faisait **3 475 lignes**, dont 992 de journal d'exécution ; ses
> conclusions vivent aujourd'hui dans les garde-fous eux-mêmes et dans `UX_PLAN.md`.
> `git log` garde le tout, comme il garde son propre prédécesseur `TODO_UX_2026-09-03.md`,
> supprimé le 2026-09-06.

---

## 1. Les affirmations réfutées

🔑 **Ce qui compte n'est pas qu'elles aient été fausses, c'est POURQUOI elles étaient
crédibles.** Chacune vient d'une mesure qui ne pouvait pas soutenir sa conclusion.

### « SUBSTRATE INDEX est cassé » — FAUX

Le dossier affirmait : *« quatre attributs lus, jamais assignés, le module ne fonctionne
pas »*. 📏 Vérifié **par exécution**, pas par lecture — `_set_busy(True)`, `_set_busy(False)`,
`last_run_manifest`, `current_window`, `current_poly`, `current_heavy` répondent tous
normalement.

🔴 **La cause de l'erreur est le `grep` qui a produit le constat** : le motif `self\.<nom>\s*=`
ne voit **ni une affectation annotée** (`self.current_window: int = 15`) **ni une
`@property`**. Deux formes parfaitement ordinaires, invisibles à une recherche textuelle.

⚠️ *Non vérifié à l'époque* : le chargement d'un vrai classeur. Seuls les chemins nommément
accusés ont été exercés.

### « Le bouton Clear / Reset ne fait rien » — FAUX

Le dossier le déclarait mort sur la foi de *« 4 lignes avant le clic, 4 lignes après »*.

🔑 **Cette mesure ne peut pas soutenir cette conclusion** : le reset **recharge les défauts
d'usine**, et l'empilement d'usine de DESIGN fait justement 4 lignes. **Un reset qui marche et
un reset mort rendent le même chiffre.**

```
defaut                    : 4 lignes
apres setRowCount(9)      : 9
apres reset               : 4      -> le reset a bien recharge les defauts
```

**Il faut perturber AVANT de mesurer.** C'est le corollaire 1 du piège 1 de `CLAUDE.md` —
*vérifie sur quelle source un critère se prononce* — appliqué à une action d'interface.

⚠️ *Et l'auteur du démenti a d'abord écrit un garde-fou qui reproduisait exactement la même
erreur. Il ne l'a vu qu'en refusant de « corriger » le code sur la foi de cet échec.*

### « Le squelette échoue à cause de la perte de code » — FAUX, deux fois

`test_ux_skeleton[CERTUS_DESIGN]` échouait dans la suite complète et passait seul.

| explication successive | ce que la mesure a dit |
|---|---|
| « c'est la perte de code de 12:43 » | le squelette courant est **identique** à la référence, `114 contre 114, zéro écart` |
| « c'est `test_certus_ux_battery` », trouvé par bissection | une fois la machine chaude, la même paire passe **2 fois sur 2**, en 9,7 s au lieu de 16 à 30 s |

🔑 **Le vrai mécanisme, et il est général** : le harnais déclarait la fenêtre construite après
**trois lectures identiques**, soit 150 ms. Or les timers différés vont jusqu'à 600 ms, et
surtout **une fenêtre bloquée dans une compilation Numba rend un compte parfaitement constant
tant qu'elle est bloquée**. *Stable* est exactement ce à quoi ressemble une fenêtre à moitié
construite.

```
DESIGN, premier worker d'une serie froide  ->  84 controles, stable=True, settle=1.53 s
le meme code, une fois chaud               ->  86 controles
charge CPU pure (8 process)                ->  86 controles, 3 essais sur 3   <- ce n'est PAS la contention
```

⚠️ **Ce qui n'a jamais été prouvé** : la garde de confirmation n'a pas été vue se déclencher
sur un run réellement froid. Elle est validée sur le chemin chaud et **construite sur le
phénomène mesuré**, pas observée en action. 📌 L'enquête de 2026-09-07 est dans
[`MESURE_REPRODUCTIBILITE_2026-09-07.md`](MESURE_REPRODUCTIBILITE_2026-09-07.md) ; elle a
réfuté quatre hypothèses de plus sans trouver la cause racine.

### « La police est uniformisée » — FAUX, et l'instrument en était la cause

Le harnais annonçait `Segoe UI @ 10 pt` sur les onze fenêtres. 🔴 **C'est son propre épinglage
qu'il mesurait, pas l'application.** Remesuré sans épinglage, sur la plateforme réelle :

```
CERTUS_DESIGN   Open Sans @10.0  disponible=NON     <- inchange
CERTUS_RE       Open Sans @10.0  disponible=NON     <- inchange
HUB · STRAT · SMOOTHER · SUBSTRATE      @ 9.0 pt
les cinq autres                          @ 10.0 pt
```

🔑 **Une grandeur qui ne varie pas avec ce qui devrait la faire varier est un artefact** —
piège 1 de `CLAUDE.md`, ici retourné contre l'instrument lui-même.

⚠️ Et le test censé garder cette propriété était **non déterministe** : il instanciait deux
applications dans le même interpréteur et lisait `QApplication.font()`, **un global de
processus**. Même code, trois verdicts :

```
le test seul       -> 1 xfailed   (echoue correctement)
son fichier        -> 2 xfailed   (echoue correctement)
toute la suite ui  -> XPASS(strict) -> compte FAILED
```

Son voisin était mal spécifié aussi : il assérait `"Open Sans" in QFontDatabase.families()`,
donc **il testait la machine, pas le code** — installer la police l'aurait fait passer sans
qu'une ligne change. 📌 D'où la règle R9 de [`UX_PLAN.md`](UX_PLAN.md) : *un processus par
fenêtre pour toute mesure Qt*.

### « Corriger la part du graphe de STRAT » — la correction était PIRE que le défaut

Plafonner la largeur du panneau à 450 px porte bien le graphe de 59,6 % à 66,9 %… et pousse
**93 px de contrôles hors du viewport** :

```
avant plafond : plot 59.6 %   panel_hscroll_px = 0
apres plafond : plot 66.9 %   panel_hscroll_px = 93   [PIRE]
```

🔑 **Des contrôles cachés valent moins qu'un graphe plus petit**, et c'est exactement ce que le
garde-fou de débordement horizontal existe pour interdire — la correction l'aurait contourné
par une autre porte. Annulée, et l'état consigné en `xfail(strict=True)` : la limite ne peut
ni être oubliée, ni se « réparer » en silence.

⚠️ La tentative a exposé autre chose : `minimumSizeHint()` répond **446 px** pour un contenu
qui en veut **~543**, parce que le `QScrollArea` absorbe la largeur de son enfant. **STRAT
atteindra 65 % à 1366 en RÉORGANISANT son panneau, pas en le redimensionnant.**

### « Une métrique corrigée est un défaut corrigé » — FAUX

L'étape qui a rendu de la place aux graphes des deux METAL a ramené leur panneau de 570 à
394 px, **sous la largeur de son propre contenu** :

```
METAL SINGLE  @1366   viewport 384   contenu 525   hbar_max 141   policy ScrollBarAlwaysOff
METAL BILAYER @1366   viewport 384   contenu 407   hbar_max  23   policy ScrollBarAlwaysOff
```

🔴 **Et le garde-fou ne pouvait pas le voir**, parce qu'il n'accumulait le débordement que si
la barre de défilement était **visible**. Or la politique était `ScrollBarAlwaysOff` : 141 px
et 23 px de panneau coupés, **sans rien à l'écran qui dise que ce contenu existe**.
🟢 **Corrigé** — le garde-fou teste désormais `maximum() > 0`, indépendamment de la visibilité.

---

## 2. Les pièges de méthode, et ce qu'ils ont coûté

| piège | ce qu'il a coûté |
|---|---|
| 🔴 **Un périmètre de validation trop étroit** | toutes les validations portaient sur `tests/ui/` plus deux fichiers de `tests/unit/`. La première passe sur `tests/unit/` **en entier** a rendu `1 failed, 2851 passed` — **un test cassé avait été publié**. Le périmètre est depuis `tests/ui/ + tests/unit/`, jamais l'un seul |
| 🔴 **Régénérer un cliquet sans lire ce qui a bougé** | `ux_baseline.json` a été régénéré **26 minutes après** une perte de code, enregistrant la régression comme plancher : `tables_sortable = 0`, `has_synthesis = False`, `input_no_tooltip = 24`. *Un garde-fou dont on régénère la référence à l'aveugle devient le garde-du-corps de la régression.* D'où la règle R12 : coller le diff des métriques |
| 🔴 **Remiser des fichiers non suivis pour instruire une question** | `git stash push --include-untracked` a emporté puis supprimé deux PDF d'étude et 22 fichiers de `studies/`, avant d'échouer sur une permission et de laisser l'arbre à moitié défait. Tout a été récupéré depuis `stash@{0}^3`. **La bonne réponse ne demandait aucun stash** : un `grep` répondait en une seconde |
| 🟠 **Un `.pyc` qui porte le chemin d'un autre arbre** | 597 fichiers portaient `D:\certus0309`, absent de la machine. Le code exécuté était bon, mais **toute trace d'échec devenait illisible** (`???` à la place du source) — dans un dépôt dont l'erreur n° 1 est de confondre deux arbres. 🟢 **Plus aucun aujourd'hui** |
| 🟠 **Une assertion qui passe pour n'importe quoi** | `assert hub.acceptDrops() is True` est vrai de **tout** `QMainWindow` : le test ne testait rien |
| 🟠 **Deux liaisons pour un même raccourci** | `F1` et `Ctrl+0` étaient liés deux fois au niveau fenêtre, une fois par `QShortcut` et une fois par `QAction`. Qt n'exécute alors **ni l'un ni l'autre** : `F1 → activated=[] ambiguous=['F1']`. **Sur la première fenêtre que voit un évaluateur, F1 n'ouvrait rien** |
| 🟠 **Compter deux fois la même chose** | `QTableWidget` **est un** `QTableView` : additionner les deux listes annonçait 32 tables là où il y en a 16 |

---

## 3. Ce qui reste vrai de ce dossier, et où c'est passé

| ce qu'il portait | où c'est aujourd'hui |
|---|---|
| l'ordre de mission et les phases 0 à 6 | [`UX_PLAN.md`](UX_PLAN.md), resserré et à jour |
| les règles de travail | §1 de `UX_PLAN.md`, R1 à R14 |
| les seuils du harnais | `scripts/audit_ux_certus.py`, qui les porte en constantes |
| le détail de chaque étape close | la **docstring du garde-fou** qui la verrouille — c'est là qu'un agent la lira |
| les pièges de mesure | §7 de `UX_PLAN.md`, et le tableau ci-dessus |

🔑 **La raison de la suppression, dite honnêtement** : ce n'était pas sa taille. C'était que
son en-tête déclarait lui-même ses tableaux d'état **périmés**, tout en restant nommé
« programme courant de l'interface » dans `CLAUDE.md`. *Un document qui dit de ne pas le croire
est un document qu'il faut retirer, pas annoter.*
