# ORDRE DE MISSION — porter les 10 modules CERTUS au premier centile mondial

**Daté du 2026-09-04. Destiné à un exécutant contraint (Gemini).**
**Auteur de l'audit : session Claude du 2026-09-03/04. Aucune ligne de code n'a été modifiée.**

---

## ⚠️ LIS CECI EN PREMIER, C'EST LA RAISON D'ÊTRE DE CE DOCUMENT

Une mission précédente — [`docs/TODO_UX_2026-09-03.md`](TODO_UX_2026-09-03.md) — a été
déclarée « MISSION ACCOMPLIE (T1 à T12 terminés) » avec un tableau de mesures à l'appui.

🔴 **Ces mesures sont fausses, et elles le sont par construction.** Le harnais qui les a
produites, `scripts/audit_ux_certus.py`, épingle `QT_QPA_PLATFORM=offscreen`. Sur cette
machine, le plugin offscreen ne résout **aucune police** : tout glyphe rend en boîte
« tofu », dont la largeur d'avance n'est pas celle d'un vrai caractère.

📏 Mesuré le 2026-09-04, même commande, même machine, `minimumSizeHint().width()` du panneau
de contrôle :

```
module                offscreen   plateforme reelle   ecart
CERTUS_STRAT                622                 446   -176   (-28 %)
CERTUS_METAL_BILAYER        559                 455   -104   (-19 %)
CERTUS_INDEX                521                 405   -116   (-22 %)
CERTUS_FIELD                479                 380    -99   (-21 %)
CERTUS_RE                   492                 416    -76   (-15 %)
CERTUS_METAL_SINGLE         559                 509    -50    (-9 %)
CERTUS_DESIGN               499                 451    -48   (-10 %)
CERTUS_INDEX_SPLINE         280                 280      0
```

Contrôle direct de la cause, sur la chaîne `"Enable QWOT penalty"` :

```
offscreen, sans police            228 px    <- tofu
offscreen + QT_QPA_FONTDIR         78 px    <- polices chargees, mais famille par defaut
plateforme windows reelle         115 px    <- la verite
```

**Conséquence : tu ne dois croire aucun chiffre de `TODO_UX_2026-09-03.md`, et tu ne dois
lancer aucune mesure avant d'avoir réparé le juge.** C'est l'objet de la phase 0, et elle est
non négociable.

🟢 **La bonne nouvelle : le correctif est mesuré et il est simple.** `offscreen` +
`QT_QPA_FONTDIR=C:\Windows\Fonts` + police épinglée reproduit la plateforme réelle à **1 à
2 px près** :

```
offscreen + FONTDIR + Segoe UI  9 pt  ->  114 px     (reel : 115 px)
offscreen + FONTDIR + Segoe UI 10 pt  ->  127 px     (reel : 125 px)
```

Le harnais peut donc être **headless, déterministe et exact en même temps**.

🟢 **C'est fait depuis le 2026-09-04 après-midi** — voir le §0bis ci-dessous.

---

## 0bis. ÉTAT AU 2026-09-04 SOIR — après la passe d'exécution, et ce qu'elle a vraiment donné

**Vérifié par mesure, pas sur déclaration.** Une passe d'exécution a appliqué les phases 0 et 1
et une partie de la phase 2. Voici ce qui tient, ce qui a été perdu, et ce qui a l'air corrigé
sans l'être.

---

## 0ter. 🔴 LA RESTAURATION A ROUVERT LE TROU DU §2.9 — constaté et refermé le 2026-09-04 en soirée

⚠️ **Le §0bis ci-dessous décrit l'état de 16:01. Les fichiers ont continué d'être modifiés
jusqu'à 16:59, et ce bloc-ci est postérieur aux deux.** Il le corrige sur un point : les trois
fichiers déclarés « perdus » **ont bien été restaurés**, mais la restauration a violé
l'avertissement du §2.9.

📏 Mesuré : `certus_design_ui_layout.py`, `certus_design_ui_events.py` et
`certus_ui_widgets_utils.py` ne sont **plus** identiques à `HEAD` (`git diff --numstat` rend
`35+/8-`, `9+/7-`, `68+/1-`). `ExcelTableWidget.__init__` est revenu, amélioré même : un
attribut de classe `CERTUS_ALLOW_SORTING` remplace l'appel manuel.

🔴 **Mais les verrous n'ont pas suivi.** Le §2.9 écrit noir sur blanc :

> *« Ne restaure pas le tri sans les verrous dans le même geste. Entre les deux, la suite serait
> dans l'état exact que cette étape existe pour empêcher. »*

C'est exactement ce qui s'est produit. `certus_lock_row_order()` avait **0 appelant** dans tout
le dépôt, et les quatre tables d'empilement étaient redevenues triables. Mesuré en processus
dédiés (règle 0.14), plateforme réelle :

```
CERTUS_RE     front_table       ExcelTableWidget  sortable=True
              ['#', 'Mat', 'n@lambda0', 'QWOT', 'Thick(nm)']
CERTUS_STRAT  stack_table       ExcelTableWidget  sortable=True
              ['#', 'Mat.', 'Mult.']
CERTUS_FIELD  table_design_res  ExcelTableWidget  sortable=True
CERTUS_RE     target_table      ExcelTableWidget  sortable=True

CERTUS_FIELD  table_layers      QTableWidget      sortable=False   <- sain
CERTUS_DESIGN front_table       QTableWidget      sortable=False   <- sain
CERTUS_DESIGN back_table        QTableWidget      sortable=False   <- sain
CERTUS_DESIGN target_table      QTableWidget      sortable=False   <- sain
```

🔑 **Ce que ça coûtait, et c'est le pire cas du dépôt** : les lecteurs sont **positionnels**.
`certus_strat_ui_state.py:1051` construit la chaîne d'empilement envoyée au moteur par
`range(rowCount())`, et `:559` persiste `config["stack_multipliers"]` de la même façon. Trier la
colonne « Mult. » de STRAT faisait donc **calculer un autre filtre que celui affiché**, et
**enregistrer l'empilement mélangé dans le JSON**. Sur le module dont un run dure 2 h 39.

🟢 **UNE TROUVAILLE QUE LE §2.7 AVAIT MAL LOCALISÉE.** Il place le défaut des cellules-widgets
sur `target_table` de **DESIGN**, ligne 956. Cette ligne **n'existe plus** et DESIGN mesure
`sortable=False` : l'étape 2.7 est sans objet en l'état. En revanche `target_table` de **RE**
porte exactement ce défaut et n'était nommée nulle part — six colonnes entièrement peuplées par
`setCellWidget` (`certus_re_table_mixin.py:474-578`), que Qt ne déplace pas au tri.

### Ce qui a été fait

| fichier | geste |
|---|---|
| `certus/ui/certus_re_layout_mixin.py` | `certus_lock_row_order()` sur `front_table` **et** `target_table` |
| `certus/ui/certus_strat_ui_layout.py` | idem sur `widgets["stack_table"]` |
| `certus/ui/certus_field_layout_mixin.py` | idem sur `table_design_res` |
| `tests/ui/test_ux_sorting_never_corrupts_data.py` | **neuf** — garde-fou exhaustif, 8 cas |

Le garde-fou couvre les **deux** familles que le §2.9 confondait : *l'ordre de ligne est la
physique* et *les cellules sont des widgets*. Il inclut les quatre tables saines, pour qu'une
conversion future en `ExcelTableWidget` ne rouvre pas le trou en silence.

📏 **Preuve d'utilité, faite dans l'ordre du §6** — garde-fou écrit d'abord, lancé sur le code
d'avant correctif :

```
tests\ui\test_ux_stack_tables_never_sortable.py FF...
E   AssertionError: CertusREApp.front_table (ExcelTableWidget) is sortable
E   AssertionError: CertusStratApp.widgets:stack_table (ExcelTableWidget) is sortable
======================== 2 failed, 3 passed in 43.88s =========================
```

puis après correctif, périmètre complet :

```
tests\ui\test_ux_sorting_never_corrupts_data.py ........
======================== 8 passed in 67.53s (0:01:07) =========================
```

### ⚠️ Deux points laissés ouverts, dits explicitement

1. **L'étape 2.10 redevient active.** Le tri est de nouveau en service sur les tables de
   résultats, donc le défaut « les nombres sont triés comme du texte » n'est plus en sommeil.
   Le §2.10 dit de le traiter *« dans la foulée de 2.9 »* — **je ne l'ai pas fait.**
2. **`certus_lock_row_order()` reste la seule voie, et rien n'oblige à l'emprunter.** Une table
   d'empilement créée demain sera triable par défaut ; seul le garde-fou la rattrapera, et
   seulement si quelqu'un l'ajoute à `STACK_TABLES`. L'inverser — `CERTUS_ALLOW_SORTING = False`
   par défaut, à ouvrir explicitement — serait plus sûr, et ce n'est pas fait.

### 🔴 LE SQUELETTE ÉCHOUAIT AU HASARD, ET LES DEUX EXPLICATIONS PRÉCÉDENTES ÉTAIENT FAUSSES

📏 `test_ux_skeleton[CERTUS_DESIGN]` échoue dans la suite complète (trois runs sur trois) et
**passe seul** (11/11). Le §0bis l'impute à la perte de code de 12:43. **C'est faux** : le
squelette courant est identique à la référence, `114 contre 114, zéro écart`.

J'ai ensuite accusé `test_certus_ux_battery` par bissection — **faux aussi**. Une fois la
machine chaude, la même paire passe 2 fois sur 2, en 9,7 s au lieu de 16 à 30 s.

🔑 **Le vrai mécanisme, et il est mesurable** : le harnais déclare la fenêtre construite après
**trois lectures identiques**, soit **150 ms**. Or les timers différés de la suite vont
jusqu'à **600 ms** (1200 ms pour le splash du HUB), et surtout **une fenêtre bloquée dans une
compilation Numba rend un compte parfaitement constant tant qu'elle est bloquée**. *Stable*
est exactement ce à quoi ressemble une fenêtre à moitié construite.

```
DESIGN, premier worker d'une serie froide  ->  84 controles, stable=True, settle=1.53 s
le meme code, une fois chaud               ->  86 controles
charge CPU pure (8 process)                ->  86 controles, 3 essais sur 3   <- ce n'est PAS la contention
```

**Correctif** : le compte est **relu après une pause de 1,5 s** (`_CONFIRM_S`) qui dépasse ces
timers ; tout mouvement vaut `ERROR`, donc `_run_worker` réessaie — et la reprise tourne à
chaud. Champs neufs : `skeleton_stable`, `skeleton_settle_s`, `skeleton_confirm_delta`.
Contrôlé sur les 11 modules : `stable=True`, `delta=0`, aucune `ERROR`, `settle ≈ 3,0 s`.

⚠️ **Ce que je n'ai PAS prouvé** : la garde n'a pas été vue se déclencher sur un run réellement
froid — vider le cache numba perturbe toute la suite et provoque par ailleurs 3 faux échecs
connus (`CLAUDE.md` §2). Elle est validée sur le chemin chaud et **construite sur le phénomène
mesuré**, pas observée en action.

### 🔴 LE CLIQUET EST ANCRÉ SOUS L'ÉTAT COURANT — règle 0.15, toujours active

📏 `tests/ui/ux_baseline.json` est daté du **2026-09-04 13:09:18**, soit 26 min après la perte,
et **n'a pas été régénéré depuis la restauration de 16 h**. Il fige donc :

```
tables_sortable = 0        sur les ONZE modules
CERTUS_DESIGN : has_synthesis=False  has_kpi_banner=False  marketing_tabs=1  input_no_tooltip=24
```

alors que DESIGN porte de nouveau l'onglet `✦ Synthesis` et son `kpi_banner` (mesuré).
**Le cliquet ne verrait pas cette restauration disparaître une seconde fois.**
🔴 **À régénérer, en collant le diff des métriques — c'est la règle 0.15, et c'est due.**
(`ux_skeleton.json`, lui, est du 16:43 : à jour.)

### ✅ 2.14 EST FAUX — SUBSTRATE INDEX N'EST PAS CASSÉ

📏 Vérifié **par exécution**, pas par lecture :

```
_set_busy(True)   OK     _set_busy(False)  OK     last_run_manifest  OK -> None
current_window    OK 15  current_poly      OK 2   current_heavy      OK -> False
```

L'étape affirme *« quatre attributs lus, jamais assignés, le module ne fonctionne pas »*. En
réalité `current_window/poly/heavy` sont assignés **lignes 824-826** sous forme annotée
(`self.current_window: int = 15`), et `last_run_manifest` est une **`@property`** (`:837`)
adossée au présenteur via `getattr(..., None)` — elle ne peut pas lever.

🔑 **La cause de l'erreur est le `grep` du dossier** : `self\.<nom>\s*=` ne voit ni
l'annotation de type, ni une property. ⚠️ *Non vérifié* : le chargement d'un vrai classeur,
qui demande un fichier d'exemple. Seuls les chemins nommément accusés ont été exercés.

### ✅ 2.15 EST COMPLET — et la moitié manquante était le CHARGEMENT

L'écriture était déjà corrigée : dialogue de destination, comparaison à la source,
confirmation nommant le fichier, et `except (*NUMERICAL_FAULT_EXCEPTIONS, OSError)` (`:409`).

🔴 **Mais le chargement (`:283`) ne captait que `NUMERICAL_FAULT_EXCEPTIONS`** — un tuple de
six fautes **numériques**, sans `OSError` (`certus/core/certus_core.py:993`). Le cas le plus
fréquent de tous — le classeur encore ouvert dans Excel, donc `PermissionError` — sortait en
**trace Python brute**. Corrigé, garde-fou `tests/ui/test_ux_smoother_load_errors.py`
(3 cas : `PermissionError`, `FileNotFoundError`, `OSError`), **3 failed → 3 passed**.

### 🟠 2.5 — LA MOITIÉ FAITE, ET L'AUTRE EST BLOQUÉE PAR UNE RÈGLE

✅ **La bascule de thème n'est plus un cercle vide.** `certus_ui_widgets_utils.py:175` portait
`setText("" if mode == "light" else "")` — **les deux branches vides**. Remplacé par
`◐`/`◑` (U+25D0/U+25D1, dans le BMP), plus l'info-bulle qui manquait. Garde-fou
`tests/ui/test_ux_theme_toggle.py`, **2 failed → 2 passed**, dont un contrôle que les glyphes
restent dans le BMP.

🔴 **L'application de la préférence au démarrage n'est PAS faite, et je me suis arrêté.**
`load_theme_config()` n'alimente que le cadre de fenêtre (`certus_ui_utils.py:324`) et les
graphes (`:937`) ; aucun `CertusTheme.configure(mode)`. Deux raisons de ne pas le faire seul :

1. **Le placer dans `apply_certus_theme` écraserait le mode clair que le harnais force**
   (`audit_ux_certus.py:198`) : `load_theme_config()` lit un **fichier**, que l'isolation des
   `QSettings` ne couvre pas. Le cliquet comparerait alors deux thèmes — exactement le risque
   que l'étape annonce.
2. **Le placer au démarrage demande de toucher les ~10 points d'entrée**, chacun créant son
   propre `QApplication` (`CERTUS_DESIGN.py:107`, `CERTUS_HUB.py:1204`, …), et
   `bootstrap_app` vit dans `certus/core`, **qui n'a pas le droit d'importer PyQt6**.
   Au-delà de la limite de trois fichiers pour une action.

### ✅ 2.18 EST FAIT — et c'était bien le meilleur rapport résultat/effort

📏 La mesure du dossier est **confirmée**, un processus par module :

```
module   Ctrl+K   menu Help   champs avec nom accessible
DESIGN     non       non              0 / 58
STRAT      non       non              0 / 59
RE         non       non              0 /  6
INDEX      oui       oui             18 / 18
FIELD      oui       oui             21 / 21
```

Les trois modules sautent `_finalize_init` **délibérément** — ils gèrent leurs propres timers
et leur préchauffage, et chacun le dit en commentaire (`certus_design_ui.py:197`,
`certus_strat_ui.py:165`, `CERTUS_RE.py:454`). Ils perdaient donc tout le **reste** en silence.

**Correctif** : `CertusBaseApp.install_common_affordances()`, extraite de `_finalize_init`
(qui l'appelle désormais), puis appelée explicitement depuis les trois modules après leur
`_qs_restore()`. Elle est **idempotente** — `install_unique_shortcut` saute une séquence déjà
prise, le menu Help se cherche lui-même — donc sans risque pour les cinq autres.
Garde-fou `tests/ui/test_ux_common_affordances.py` : **6 failed → 16 passed**.

🔑 **Effet de bord heureux : le §2.19 se referme en partie.** Il annonce
`len(_OVERLAYS) == 0` dans les onze fenêtres, la cause étant que les deux seuls modules
portant les noms de tables connus (DESIGN, RE) sont **précisément ceux qui n'appelaient pas
`_finalize_init`**. Le croisement est rompu : RE installe maintenant son état vide, et le
squelette y gagne le bouton `Add target`.

⚠️ **Et le cliquet a attrapé la contrepartie**, ce qui est exactement son rôle :
`CERTUS_RE btn_no_tooltip 0 → 1 [PIRE]` — le bouton d'état vide n'avait pas d'info-bulle.
**Corrigé à la source** (`certus_empty_state.py`, l'info-bulle reprend la description), pas en
régénérant par-dessus. Diff final : **que des améliorations**, `n_shortcuts +3` sur les trois.

### ✅ LES DEUX TESTS DE POLICE MESURENT ENFIN LE CODE

Le §0bis demandait de les réécrire *« dans un processus dédié »*. Fait. Ils lisaient
`QApplication.font()`, un **global de processus**, après avoir construit deux applications
dans le même interpréteur — donc ils mesuraient l'**ordre d'exécution** (règle 0.14) :

```
le test seul       -> 1 xfailed   (echoue correctement)
son fichier        -> 2 xfailed   (echoue correctement)
toute la suite ui  -> XPASS(strict) -> compte FAILED
```

Le second était pire : `assert "Open Sans" in QFontDatabase.families()` testait **la machine**,
pas le code — installer la police l'aurait rendu vert sans qu'une ligne change. Il assère
désormais qu'**aucun module ne demande une famille que Qt doit remplacer en silence**, ce qui
est une propriété du code. Les deux restent `xfail(strict)` — les défauts sont réels et
relèvent de l'étape 3.2 — mais ils échouent maintenant **de façon déterministe**.

🟢 **Conséquence : `tests/ui/` est passée à `0 failed` pour la première fois.**
`2 failed, 344 passed, 3 xfailed` → **`0 failed, 366 passed, 4 xfailed`**.

### ✅ 2.17 EST FAUX — le bouton Clear / Reset FONCTIONNE

📏 L'étape le déclare mort sur la foi de *« 4 lignes avant le clic, 4 lignes après »*.
**Cette mesure ne peut pas soutenir cette conclusion** : le reset **recharge les défauts
d'usine**, et l'empilement d'usine de DESIGN fait justement 4 lignes. Un reset qui marche et
un reset mort rendent donc **le même chiffre**.

```
defaut                    : 4 lignes
apres setRowCount(9)      : 9
apres reset               : 4      -> le reset a bien recharge les defauts
```

🔑 **Il faut perturber AVANT de mesurer.** C'est le corollaire 1 du piège 1 du `CLAUDE.md` —
*vérifie sur quelle source un critère se prononce* — appliqué à une action d'interface.
⚠️ *J'ai écrit un premier garde-fou qui reproduisait exactement la même erreur, et il échouait.
Je ne l'ai vu qu'en refusant de « corriger » le code sur la foi de cet échec.*

Les deux moitiés du correctif que l'étape prescrit sont **déjà dans l'arbre** :
`create_reset_button(self.ui, …)` (`certus_design_ui_layout.py:602`) et le `TypeError` levé
d'entrée si l'instance n'est pas un `QWidget` (`certus_reset_framework.py:477`). Verrouillées
par `tests/ui/test_ux_design_reset.py`, **2 passed**. Le §2.6 (raccourcis morts de DESIGN) est
appliqué de la même façon — `getattr(self.ui, …)` partout.

### ✅ 2.4 ET 2.5 — les deux sont clos

**2.4.** `PRIMARY` était déjà tokenisé (`PRIMARY_TEXT` passe à `#0f172a` en sombre, 7,02:1).
🔴 **Le défaut vivait sur `DANGER`**, laissé en dur : `color: #ffffff` sur un fond qui devient
`#f87171` en sombre. Ratios calculés, pas estimés :

```
clair   #ffffff sur DANGER #dc2626  =  4.83:1   OK
sombre  #ffffff sur DANGER #f87171  =  2.77:1   ECHEC AA (exige 4.5)
sombre  #0f172a sur DANGER #f87171  =  6.45:1   retenu
```

⚠️ **`DANGER_TEXT` existait déjà et ne pouvait PAS servir** : c'est le texte d'un badge sur
fond clair `DANGER_BG` (`#b91c1c` sur `#fee2e2`), pas un libellé sur aplat. D'où un jeton
distinct, `DANGER_LABEL` / `DANGER_HOVER`. Garde-fou `tests/ui/test_ux_button_contrast.py`,
**3 failed → 7 passed**, qui **calcule** les ratios et vérifie d'abord son propre calculateur
sur une paire connue.

**2.5.** La préférence persistée atteint enfin l'interface :
`CertusTheme.configure(load_theme_config())` dans `apply_certus_theme`, le point de passage
unique de toute la thématisation. 🔑 **Ce qui a levé le blocage que j'avais signalé**, c'est
que le harnais neutralise désormais `load_theme_config` : la mesure ne dépend plus de la
préférence de l'opérateur. La préférence n'est plus lue qu'**une fois** par appel (elle
l'était deux fois, sans garantie d'accord). **2 failed → 2 passed.**

### ✅ 2.3 — de six modules sous 65 % à UN SEUL

📏 Relevé dans les références régénérées : **1920 → 0 module** sous 65 %, **1366 → 1**
(`CERTUS_STRAT`, 59,6 %). L'étape en annonçait six.

### ✅ LE DERNIER CORRECTIF DE LA PHASE 0, ET LE §2.16 QU'IL A RÉVÉLÉ

Le garde-fou hscroll testait `hbar.isVisible()`. Corrigé en `maximum() > 0` **dans le test et
dans le harnais**, avec un second critère que le §0bis réclamait déjà : **ignorer une zone de
défilement non visible**, sinon une page jamais affichée garde la géométrie Qt par défaut
640×480 et rapporte un débordement qu'elle n'a pas — c'est ce qui créditait `INDEX_SPLINE` de
143 px fantômes.

📏 Une fois corrigé, à 1366×768, `QSettings` isolées :

```
CERTUS_METAL_SINGLE    143 px coupes   ScrollBarAlwaysOff
CERTUS_METAL_BILAYER    24 px coupes   ScrollBarAlwaysOff
tous les autres          0
```

⚠️ **Un écart à savoir lire** : sans isolation des `QSettings`, STRAT affiche 217 px de barre
horizontale à 1366. Ce n'est **pas** un défaut du code — c'est la disposition que
l'utilisateur a persistée. Le garde-fou mesure la disposition **par défaut** ; il ne dit rien
de ce que l'opérateur s'est lui-même infligé en tirant le splitter.

🔑 **Cause du débordement** : les cartes de paramètres sont disposées sur **deux colonnes**
(Physique | Matériau, Sortie | Live). Deux colonnes tiennent dans les 554 px du panneau à
1920 et **pas** dans les 384 px de 1366. **Correctif : reflux à une colonne**, piloté par le
**débordement réellement mesuré** (`hbar.maximum()`) et non par un seuil choisi ; la largeur à
laquelle deux colonnes redeviennent possibles est **retenue depuis la mesure** (527 px pour
SINGLE, 408 pour BILAYER). `test_ux_no_horizontal_scroll` : **2 failed → 16 passed.**

⚠️ **Trois choses m'ont fait échouer avant d'y arriver, et elles se reproduiront** :
1. comparer à `params_widget.width()` — inutile, la zone de défilement laisse son contenu
   prendre la largeur qu'il demande, donc ce chiffre **est** la demande ;
2. chercher la grille dans les sous-*layouts* seulement — BILAYER enveloppe la sienne dans un
   `QWidget` ; 3. comparer au minimum de la grille — sur BILAYER elle « tient » (350 dans 384)
   alors que les marges de la carte poussent le panneau 24 px dehors.

🟢 **Et un bug latent réveillé au passage, corrigé** : `CertusBaseApp.eventFilter` lisait
`self.front_table` sans garde. Aucune fenêtre METAL n'en a. Installer un filtre d'événements
sur elles pour la première fois a produit une `AttributeError` **à chaque redimensionnement**,
remontée en `uncaught_exception`. `getattr(self, "front_table", None)` désormais.

### ✅ 2.22 — FIELD n'enregistre plus un point de Pareto bâti sur un empilement INVENTÉ

`certus_field_state_mixin.py` répondait à l'échec en fabriquant la physique :

```python
except Exception:
    layer_types = [i % 2 for i in range(len(emp_factors))]
```

`layer_types` dit quelle couche est haut indice et laquelle est bas indice. Inventer une
alternance H/L parfaite produit un **coût calculé sur un empilement qui n'existe pas**, le
range dans `pareto_history` et l'affiche à côté des points réels, **sans rien qui le
distingue**. C'est l'interdit n° 9 du `CLAUDE.md` réalisé dans l'interface.

⚠️ **Et la moitié la plus sournoise ne demandait aucune exception** : le même bloc fabriquait
aussi sur simple **désaccord de longueur**. 📏 Mesuré : quatre épaisseurs contre deux
matériaux rendaient un enregistrement portant `type_rmse [0, 1, 0, 1]` et `dmin 53,19 nm`,
tout inventé.

**Correctif** : refuser le point et journaliser — un dénouement que la fonction a déjà trois
fois (pas de facteurs, coût non fini, coût hors bornes). Le second `except` du même pas est
conservé (`dmin = 0.0` s'affiche « - », donc rien d'inventé n'atteint l'opérateur) mais il
**cesse d'être muet** : exceptions nommées et avertissement journalisé.
Garde-fou `tests/ui/test_ux_field_pareto_honesty.py`, **2 failed → 2 passed**.

### ✅ 2.20 — (a), (b), (e) et (f) sont clos ; (c) et (d) restent

**(a) et (b) étaient déjà appliqués**, vérifié dans le code : `close_all_auxiliary_windows`
est passé sur `Ctrl+W` et `stop=self.request_stop_optimization` est bien fourni, donc **`Esc`
stoppe STRAT** ; l'optimisation locale de DESIGN est sur `Ctrl+Shift+G` et `load=` est fourni,
donc **`Ctrl+O` charge une configuration**.

**(f).** 📏 Mesuré avec Qt 6.11 :

```
QKeySequence("Ctrl+Plus").toString()   ->  ''        ne se resout a RIEN
QKeySequence("Ctrl+Minus").toString()  ->  ''        ne se resout a RIEN
QKeySequence("Ctrl++").toString()      ->  'Ctrl++'
QKeySequence("Ctrl+-").toString()      ->  'Ctrl+-'
```

La palette annonçait `Ctrl+Plus` / `Ctrl+Minus` et les imprimait **tels quels** : un raccourci
que l'opérateur ne peut pas taper. 🔑 **Le menu Help voisin utilisait déjà les bonnes
séquences et portait même un commentaire expliquant pourquoi** — la palette n'avait jamais
suivi. Garde-fou général posé (*toute séquence annoncée doit se résoudre*) :
**3 failed → 3 passed.**

**(e) — l'aide dérive maintenant du RÉEL.** 📏 Mesuré, annoncé contre réellement lié :

```
CERTUS_DESIGN         20 annonces / 21 lies    fantomes : Ctrl+R, Ctrl+W
CERTUS_STRAT          17 annonces / 20 lies    fantomes : aucun
CERTUS_METAL_SINGLE   16 annonces / 15 lies    fantomes : Ctrl+O "Load configuration...",
                                                          Ctrl+S "Save configuration...",
                                                          Ctrl+R, Ctrl+W
```

`collect_window_shortcuts` écarte désormais toute entrée dont `shortcut_owner(window, seq)`
rend `None`. Garde-fou `tests/ui/test_ux_help_matches_reality.py` : **6 failed → 7 passed**.

⚠️ **Un test existant encodait l'ANCIEN contrat et a dû être retourné** — c'est le piège 5 du
`CLAUDE.md`, pas un ajustement de complaisance. `test_u4_collect_window_shortcuts_uses_commands`
utilisait une fenêtre factice dont `findChildren()` rendait `[]` — donc une fenêtre ne
possédant **aucun** raccourci — et exigeait quand même que l'aide annonce `F5` et `Ctrl+S`.
**C'est exactement le défaut que (e) corrige.** La fenêtre y **lie** désormais ce qu'elle
annonce, et le docstring dit pourquoi le contrat a changé.

### ✅ LE DIALOGUE D'ARRÊT ARRÊTAIT SUR **TROIS** FORMES D'INACTION — le dossier n'en voyait que deux

`confirm_stop_with_timeout` garde **tous** les chemins d'arrêt de la suite : DESIGN, INDEX,
RE, STRAT et les deux METAL. 📏 Mesuré le 2026-09-05, il arrêtait le calcul sur :

```
msg.setDefaultButton(btn_stop)   le bouton destructeur avait le FOCUS
btn_stop.animateClick()          le compte a rebours le cliquait apres 10 s
return True                      le repli : fermer par Echap ou par la croix ne
                                 clique RIEN, donc clickedButton() vaut None --
                                 et l'ancien code lisait ca comme "arreter"
```

🔑 **La troisième n'était pas dans le §2.20, et c'est la pire** : elle ne demande aucune
attente. Et elle compose avec le §2.20(a) que ce même dossier prescrit — **`Esc` est
désormais lié à l'arrêt dans tous les modules, or `Esc` est une touche réflexe**. Un premier
`Esc` involontaire ouvre le dialogue, un second le referme : le run de 2 h 39 est perdu **en
deux réflexes**, sans qu'aucune décision n'ait été prise.

**Règle appliquée : l'inaction ne détruit jamais.** `True` n'est rendu que si l'opérateur a
**cliqué** « Stop Now ». Le bouton par défaut devient « Keep running », le compte à rebours
**referme sans cliquer**, et le libellé dit la vérité (*« Resuming in N seconds… Doing nothing
keeps the optimization running »*). Garde-fou `tests/ui/test_ux_stop_confirmation.py` :
**4 failed → 4 passed.**

⚠️ **Cela change le comportement de cinq modules à la fois, et c'est annoncé** — le §2.20 le
demandait. Vérifié qu'aucun test existant ne s'appuyait sur l'ancienne sémantique.

### ✅ 2.20 (c) — fermer pendant un run demande enfin quelque chose

📏 Mesuré le 2026-09-05 : `CertusBaseApp.closeEvent` appelait `_stop_all_workers()` **sans
rien demander**, et STRAT — qui **ne chaîne jamais** vers la classe de base, son propre
commentaire le dit — finissait par `finally: event.accept()`. Cliquer la croix pendant un run
de 2 h 39 le jetait, sans question et sans retour.

`confirm_close_during_run` demande désormais, dans les deux chemins, et `confirm_destructive`
a déjà « annuler » pour bouton par défaut. Garde-fou `tests/ui/test_ux_close_during_run.py` :
**2 failed → 4 passed**, avec un test dans **chaque sens** — refuser doit laisser la fenêtre
ouverte, **et** ne rien avoir en cours ne doit poser aucune question.

🔴 **ET MA PREMIÈRE IMPLANTATION A FAIT PLANTER L'INTERPRÉTEUR — à consigner, parce que
l'erreur est tentante.** Pour être précis plutôt que prudent, je comptais les threads en vie
en balayant **aussi** `self.findChildren(QThread)`. Cette traversée atteint, pendant la
destruction, des objets dont le **côté C++ est déjà libéré** :

```
sans mon changement : 5 passed in 4.07s   (deux essais)
avec findChildren   : Windows fatal exception: access violation
apres retrait       : 5 passed in 4.10s   (deux essais)
```

🔑 **Aucune clause `except` ne rattrape ça** : ce n'est pas une exception Python, c'est le
processus qui meurt. La garde ne consulte donc plus que les inscriptions du
`worker_manager`. ⚠️ **Et c'est le test le plus banal de la suite qui l'a attrapé**, pas un
test d'ergonomie : `tests/unit/test_gui_apps_smoke.py`, qui se contente d'ouvrir et de fermer
les fenêtres.

### ✅ 2.20 (d) — l'export de RE n'avait AUCUN accès clavier, et rien ne le disait

`install_standard_shortcuts` définit la convention de la suite : `"export" → Ctrl+E`. Or RE
lie `Ctrl+E` à *évaluer* **avant** l'appel, puis demande `export=self.export_excel`.
`install_unique_shortcut` **décline une séquence déjà prise** — à raison : lier deux fois la
même fait émettre `activatedAmbiguously` à Qt, qui n'exécute **ni l'un ni l'autre**. Mais il
déclinait **en silence**, donc l'export Excel de RE n'était joignable par aucune touche.

🔑 **Le correctif qui compte n'est pas le déplacement, c'est la fin du silence.** Un binding
demandé et non installé produit désormais un avertissement nommant la séquence, l'action, et
**qui détient déjà la touche**. L'export de RE passe sur `Ctrl+Shift+E`, et le §2.20(e) fait
que l'aide affiche cette touche-là et non une promesse.

🔴 **ET LE MÊME FICHIER PORTAIT LA SÉQUENCE MORTE DU (f), UTILISÉE COMME VRAI BINDING.** La
table principale déclarait `"zoom_in": ("Ctrl+Plus", …)` et `"zoom_out": ("Ctrl+Minus", …)` —
les deux séquences que Qt 6 résout à **vide**. Ces entrées ne liaient donc **rien** ; le zoom
ne fonctionnait que par l'`alias_map` posée dix lignes plus bas, qui installe `Ctrl++` et
`Ctrl+-`. Corrigées à la source. Garde-fou `tests/ui/test_ux_standard_shortcuts.py`,
**3 failed → 3 passed**, dont un contrôle qui balaie **toute** la table et refuse n'importe
quelle séquence non résoluble.

⚠️ *Mon premier test échouait pour une mauvaise raison : il lisait `record.message`, qui
contient le gabarit `"%s … %r"` et non le texte interpolé — le journal formate paresseusement.
`getMessage()` corrige. C'était mon test qui avait tort, pas le code.*

### 🟠 Et un piège de mesure trouvé au passage, sans rapport avec le tri

📏 **597 fichiers `.pyc` du dépôt portent le chemin `D:\certus0309`**, qui **n'existe pas sur
cette machine**. Conséquence visible dans toute trace d'échec :

```
D:\certus0309\tests\ui\test_ux_skeleton.py:39: in test_no_interactive_control...
    ???
```

Le `???` est pytest qui ne trouve pas le source à l'emplacement inscrit dans le bytecode. Le
code exécuté est le bon — Python valide le `.pyc` par mtime et taille — mais **toute trace
d'erreur est illisible**, dans un dépôt dont l'erreur n° 1 est précisément de confondre deux
arbres. Purger les `__pycache__` est sans risque (ils se régénèrent) et **n'a pas été fait**,
pour ne pas mêler deux changements dans la même vérification.

---

### ✅ Ce qui est fait et que j'ai vérifié

| étape | preuve |
|---|---|
| **Phase 0 entière** | le harnais épingle Segoe UI 10 pt via `QT_QPA_FONTDIR`, couvre **11 fenêtres**, ne compte plus les tables en double (`n_tables` divisé par deux partout), détecte `panel_hscroll_px`, mesure aux deux résolutions, transforme les info-bulles en verdict, et sort en erreur après 3 tentatives |
| **Phase 1** | `tests/ui/test_ux_ratchet.py` (22 tests), `test_ux_skeleton.py` (11), `test_ux_design_system.py` (5), `test_ux_harness_integrity.py` |
| **2.1 — STRAT ne cache plus rien** | `test_ux_no_horizontal_scroll.py -k STRAT` → **2 passed**. Contre-mesuré en processus dédié : `viewport 536 / contenu 536`, `hbar_max = 0`. `plot%` 67,5 → **71,0**. La barre visible sur la capture d'avant a disparu de la capture d'après |
| **2.2 — SPLINE ne cache plus rien** | mesuré `viewport 511 / contenu 511`. ⚠️ *Une sonde annonçait encore 325 px de débordement : c'est un faux positif. La zone en cause a `visible=0`, son contenu aussi, et son parent est un `QStackedWidget` resté à la géométrie Qt par défaut 640×480 — une page jamais affichée* |
| **le garde-fou 0.7 mord vraiment** | `test_ux_skeleton.py` a **détecté** la régression décrite ci-dessous, en la nommant |

### 🔴 Ce qui a été PERDU — trois fichiers sont revenus à `HEAD`

📏 Mesuré : `certus/ui/certus_design_ui_layout.py`, `certus/ui/certus_design_ui_events.py` et
`certus/ui/certus_ui_widgets_utils.py` sont **identiques à `HEAD`**, tous trois horodatés
**2026-09-04 12:43:15** — la même seconde, donc une opération groupée.

Ils portaient le travail de la mission précédente. Conséquences mesurées sur DESIGN :

```
metrique              avant   apres
tables_sortable           2       0
has_synthesis          True   False
has_kpi_banner         True   False
marketing_tabs            0       1
input_no_tooltip          0      24
```

Et dans `certus_ui_widgets_utils.py`, ont disparu :

- l'`__init__` d'`ExcelTableWidget` qui activait tri et redimensionnement → **plus aucune
  table triable dans toute la suite** (`0/3`, `0/2`, `0/4`… partout) ;
- 🔴 **la méthode `certus_lock_row_order()`**, qui interdisait de trier une table d'empilement ;
- la bascule de thème est revenue à son ternaire dégénéré, `certus_ui_widgets_utils.py:174`.

🔑 **Le squelette de l'étape 1.2 a fait exactement son travail** — il échoue et nomme le
coupable :

```
Missing control(s) detected in CERTUS_DESIGN skeleton:
    - QTabWidget|✦ Synthesis/Spectrum (T)/Profile/n(lambda)/Color
```

⚠️ **Il n'a simplement jamais été relancé après 12:43.**

### 🔴 Et le cliquet a FIGÉ la régression

`tests/ui/ux_baseline.json` a été régénéré à **13:09:18**, soit 26 minutes **après** la perte.
Il enregistre donc comme plancher `tables_sortable = 0`, `has_synthesis = False`,
`marketing_tabs = 1`, `input_no_tooltip = 24`.

🔑 **La leçon, et elle vaut pour toute la suite du plan : régénérer une référence de cliquet
sans lire ce qui a bougé transforme le garde-fou en garde-du-corps de la régression.** La
règle de l'étape 1.1 — *« régénérer dans le même changement, et l'écrire dans le compte
rendu »* — n'est pas une formalité.

### 🟠 Deux corrections qui n'en sont pas

**1. La police n'est PAS uniformisée.** Le harnais annonce `Segoe UI @ 10 pt` pour les onze
fenêtres — mais **c'est l'épinglage du correctif 0.1 qu'il mesure, pas l'application**.
📏 Remesuré sans épinglage, sur la plateforme réelle :

```
CERTUS_DESIGN   Open Sans @10.0  disponible=NON     <- inchange
CERTUS_RE       Open Sans @10.0  disponible=NON     <- inchange
HUB · STRAT · SMOOTHER · SUBSTRATE      @ 9.0 pt
les cinq autres                          @ 10.0 pt
```

🔴 **Et le test censé le garder est non déterministe.** `test_font_point_size_is_uniform_across_the_suite`
instancie deux applications dans le même interpréteur et lit `QApplication.font()`, qui est un
**global de processus**. Résultat, pour le même code :

```
le test seul       -> 1 xfailed   (echoue correctement)
son fichier        -> 2 xfailed   (echoue correctement)
toute la suite ui  -> XPASS(strict) -> compte FAILED
```

Il ne mesure pas le code, il mesure l'ordre d'exécution. **À réécrire : lire la police
demandée par chaque module dans un processus dédié, avant tout épinglage.**

⚠️ Son voisin `test_every_module_requests_an_installed_font` est mal spécifié aussi : il
assère `"Open Sans" in QFontDatabase.families()`, donc **il teste la machine, pas le code** —
installer la police le ferait passer sans qu'une ligne change.

**2. L'étape 2.3 a créé un défaut en corrigeant une métrique.** Le panneau des deux METAL est
passé de 570 à **394 px** à 1366, sous la largeur de son propre contenu. 📏 Mesuré en
processus dédiés, 4 s de stabilisation :

```
METAL SINGLE  @1366   viewport 384   contenu 525   hbar_max 141   policy ScrollBarAlwaysOff
METAL BILAYER @1366   viewport 384   contenu 407   hbar_max  23   policy ScrollBarAlwaysOff
```

`hbar_max` est **non nul** : le contenu dépasse réellement. Mais la politique est
`ScrollBarAlwaysOff` — préexistante dans `HEAD`, `certus/metal/certus_metal_common.py:1087` —
donc **141 px et 23 px du panneau sont coupés sans aucun moyen de les atteindre.**

🔴 **Et le garde-fou ne peut pas le voir**, parce qu'il n'accumule `maximum()` que si la barre
est visible :

```python
# tests/ui/test_ux_no_horizontal_scroll.py:72 — le trou
if hbar is not None and hbar.isVisible():
    hscroll_px = max(hscroll_px, int(hbar.maximum()))
```

**Correctif du garde-fou, à faire avant tout autre travail de mise en page :**

```python
# A panel can hide content two ways: a visible scrollbar, or ScrollBarAlwaysOff
# with content wider than the viewport. The second is worse — nothing on screen
# says the content exists. Measured 2026-09-04: METAL SINGLE @1366 clipped 141 px
# while this guard reported 0.
if hbar is not None and hbar.maximum() > 0:
    hscroll_px = max(hscroll_px, int(hbar.maximum()))
```

### 📊 Suite de tests, mesurée

```
avant la passe :  281 passed,   0 failed
apres la passe :  334 passed,   5 failed,  3 xfailed
```

Les cinq échecs, et leur cause :

| test | cause |
|---|---|
| `test_ux_skeleton[CERTUS_DESIGN]` | la perte de 12:43 — **c'est le garde-fou qui fonctionne** |
| `test_certus_ux_battery::test_design_and_re_splitter_persistence` | la même perte |
| `test_ux_design_system::test_font_point_size_is_uniform` | `XPASS(strict)` non déterministe, décrit ci-dessus |
| `test_certus_shortcut_uniqueness[CERTUS_HUB]` | 🔴 **Ce n'est PAS une régression : c'est un défaut préexistant que le test neuf révèle.** `F1` et `Ctrl+0` sont chacun liés **deux fois** au niveau fenêtre — `CERTUS_HUB.py:809` (boucle `QShortcut` brute) contre `:898` et `:911` (`QAction.setShortcut`). Qt n'exécute alors **ni l'un ni l'autre**. Mesuré au clavier réel : `F1 → activated=[] ambiguous=['F1']`. **Sur la première fenêtre que voit un évaluateur, F1 n'ouvre rien.** Correctif : passer les trois sites par `install_unique_shortcut` / `claim_shortcut_for_action` (`certus/ui/certus_ui_utils.py:452` et `:472`), qui existent exactement pour ça |
| `test_certus_ux_drag_and_drop::test_hub_shortcuts_and_drag_drop` | 🔴 **Cause exacte, une ligne** : `class CertusHub(QMainWindow)` — `CERTUS_HUB.py:182`. Le HUB est la **seule fenêtre qui n'hérite pas de `CertusBaseApp`**, or `dragEnterEvent`/`dropEvent` ne sont définis que là (`certus/ui/certus_base_app.py:2266` et `:2275`, seules définitions du dépôt). ⚠️ La première assertion du test, `assert hub.acceptDrops() is True`, **passe pour n'importe quel `QMainWindow`** : elle ne teste rien |

### ➡️ L'ordre de marche

🔴 **D'abord ce qui est CASSÉ, pas ce qui est laid.** L'audit des onze fenêtres est terminé et
il a révélé trois défauts **fonctionnels**, qu'aucune considération d'ergonomie ne précède :

| # | quoi | étape |
|---|---|---|
| **1** | **SUBSTRATE INDEX lève `AttributeError`** au chargement d'un classeur et au lancement d'un calcul. Quatre attributs lus, jamais assignés. Le module ne fonctionne pas | **2.14** |
| **2** | **SMOOTHER réécrit le classeur source de l'opérateur** sans confirmation ni sauvegarde | **2.15** |
| **3** | **Les deux METAL : le bouton « Run » est hors écran** (469 px sous le bas à 1366) et 13 champs sur 15 ne se peignent pas | **2.16** |
| **4** | **DESIGN : le bouton « Clear / Reset » ne fait rien**, en silence — reproduit : 4 lignes avant, 4 après | **2.17** |
| **5** | **`Esc` ne stoppe pas STRAT** (le seul module à 2 h 39 de run) et **`Ctrl+O` lance une optimisation dans DESIGN** alors que l'aide annonce « Load configuration » | **2.20 a et b** |
| **6** | **Fermer la fenêtre pendant un run tue le calcul sans une question**, dans tous les modules | **2.20 c** |
| **7** | **Deux `except` fabriquent un empilement optique faux** au lieu de signaler l'erreur (`certus_field_state_mixin.py:995` et `:1015`) — l'interdit n° 9 réalisé dans l'interface | **2.22** |

🔑 **Puis l'action au meilleur rapport résultat/effort de tout le plan** : rebrancher
`_finalize_init` sur **DESIGN, STRAT et RE**, qui le court-circuitent tous les trois. Un seul
geste rend la palette de commandes, l'overlay des raccourcis, le menu Help, **163 noms
accessibles** et les états vides à ces trois modules. **Étape 2.18.**

**Ensuite, remettre la base d'aplomb :**

4. **Restaurer les trois fichiers perdus** depuis l'état d'avant 12:43, ou refaire leur
   travail — en particulier `certus_lock_row_order()`. Sans cela, tout se bâtit sur une base
   amputée.
5. **Régénérer les baselines** *après* la restauration, et **coller le diff** des métriques
   dans le compte rendu (règle 0.15).
6. **Corriger le garde-fou hscroll** (`maximum() > 0` au lieu de `isVisible()`), puis traiter
   les 141 px et 23 px des METAL à 1366.
7. **Réécrire les deux tests de police** pour qu'ils mesurent le code, et non la machine ni
   l'ordre d'exécution.
8. **Instruire les deux échecs du HUB** dans `certus_ui_utils.py` et
   `mixins/certus_base_core_mixins.py`, seuls fichiers modifiés du chemin.

**Puis seulement** les phases 3 à 6, dans l'ordre du plan.

---

## 0. RÈGLES ABSOLUES — aucune exception

| # | Règle | Pourquoi |
|---|---|---|
| 0.1 | 🔴 **Jamais `git commit`.** | Le hook `post-commit` **pousse automatiquement** vers `github.com/nikonvr/CERTUS`, qui est **public**. Committer, c'est publier. Laisse le travail dans l'arbre et signale que c'est prêt. |
| 0.2 | 🔴 **Jamais `ruff check --fix`.** | Le dépôt contient des ré-exports volontaires ; la correction automatique casse des imports utilisés ailleurs. |
| 0.3 | 🔴 **Ne touche pas `pyproject.toml`**, en particulier `extend-ignore`. | Surveillé par `tests/oracle/test_lint_debt_ratchet.py`. |
| 0.4 | 🔴 **Ne modifie rien dans `example/` ni `reports/`.** | Données scientifiques de référence. |
| 0.5 | 🔴 **Dans `certus/` : commentaires, docstrings et logs en ANGLAIS.** | Règle du projet. Les **libellés vus par l'utilisateur** peuvent être en français, mais **correctement accentués**. |
| 0.6 | 🔴 **`certus.core`, `certus.physics`, `certus.domain` n'importent JAMAIS PyQt6.** | Frontière d'architecture. |
| 0.7 | 🔴 **Aucune couleur hexadécimale codée en dur.** Toujours `CertusTheme` et `apply_certus_theme()`. | Sinon le mode sombre et la cohérence sont perdus. |
| 0.8 | 🔴 **NE RENDS JAMAIS TRIABLE une table qui décrit un empilement optique.** L'ordre des couches **est** la physique. | Trier `front_table`, `back_table` ou `table_layers` produit un empilement faux. |
| 0.9 | **Une étape à la fois.** Termine, vérifie, puis passe à la suivante. | Deux changements simultanés ⇒ personne ne sait lequel a causé quoi. |
| 0.10 | 🔴 **Ne modifie jamais un test pour le faire passer.** | Si un test casse, c'est ton changement qui est en cause. **Sauf** quand une étape te dit explicitement quel test mettre à jour et pourquoi — il y en a, ils sont nommés. |
| 0.11 | 🔴 **Si tu n'as pas mesuré, écris « je n'ai pas mesuré ».** | Ne rapporte jamais un résultat que tu n'as pas obtenu par une commande, sortie collée. |
| 0.12 | 🔴 **Si une sortie ne correspond pas à ce que ce document annonce : ARRÊTE-TOI et signale.** N'invente pas de contournement. | Un contournement silencieux est la seule faute réellement disqualifiante. |
| 0.13 | 🔴 **Ne « corrige » JAMAIS `except A, B:` en `except (A, B):`.** | C'est la syntaxe **PEP 758**, valide depuis Python 3.14 et utilisée volontairement dans **18 modules** — interdit n° 5 de `CLAUDE.md`. Ajouter les parenthèses **change le sens du code**. ⚠️ *Un document de passation l'a qualifiée de « vestige Python 2 » : c'est faux, et y toucher casserait le dépôt.* |
| 0.14 | 🔴 **Ne mesure jamais deux applications dans le même interpréteur Python.** Un processus par fenêtre, toujours. | Les largeurs dépendent alors de l'ordre des imports, et `QApplication.font()` est un **global de processus** que chaque instanciation écrase. 📏 C'est ce qui rend `test_font_point_size_is_uniform_across_the_suite` non déterministe : seul, il échoue ; dans la suite complète, il passe. |
| 0.15 | 🔴 **Après avoir régénéré une baseline de cliquet, COLLE le diff des métriques.** | 📏 Le 2026-09-04, une baseline régénérée 26 min après une perte de code a figé quatre métriques dégradées de DESIGN. Un cliquet dont on renouvelle la référence sans la lire protège la régression au lieu de la signaler. |

---

## 1. ENVIRONNEMENT

L'interpréteur est le **Python système**. Le venv `C:\envs\certus` cité dans `CLAUDE.md`
**n'existe pas sur cette machine** — vérifié le 2026-09-04.

```bash
python -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

**Sortie attendue** : un chemin commençant par `D:\drivefl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\0409\certus\`.
Sinon → **arrête-toi** : tu modifierais un dossier et en mesurerais un autre.

Version : Python **3.14.7**, PyQt6, Qt **6.11.0**, pyqtgraph, numba, pytest.

### Ligne de base, mesurée le 2026-09-04 avant toute modification

```
python -m ruff check .                      ->  All checks passed!
python -m pytest tests/ui/ -q --no-cov      ->  281 passed in 74.14s
```

**Ces deux sorties sont ton point zéro. À la fin de CHAQUE étape, elles doivent rester
vertes** (le nombre de tests, lui, augmentera : c'est normal, tu en ajoutes).

---

## 2. LE PÉRIMÈTRE : DIX MODULES, PAS HUIT

Le HUB lance **dix** modules — table déclarative `HUB_APP_CATALOG`,
[`certus/core/certus_hub_config.py`](../certus/core/certus_hub_config.py) :

| # | module | script | audité avant 2026-09-04 ? |
|---|---|---|---|
| 1 | DESIGN | `CERTUS_DESIGN.py` | oui |
| 2 | RE | `CERTUS_RE.py` | oui |
| 3 | STRAT | `CERTUS_STRAT.py` | oui |
| 4 | INDEX | `CERTUS_INDEX.py` | oui |
| 5 | INDEX SPLINE | `CERTUS_INDEX_SPLINE.py` | oui |
| 6 | FIELD | `CERTUS_FIELD.py` | oui |
| 7 | **SMOOTHER** | `certus_curve_smoother.py` | 🔴 **JAMAIS** |
| 8 | **SUBSTRATE INDEX** | `certus_substrate_index.py` | 🔴 **JAMAIS** |
| 9 | METAL BILAYER | `CERTUS_METAL_BILAYER.py` | oui |
| 10 | METAL SINGLE | `CERTUS_METAL_SINGLE.py` | oui |

Plus la fenêtre du **HUB** lui-même : **onze fenêtres au total**.

🔴 **`SMOOTHER` et `SUBSTRATE INDEX` sont absents du harnais** (`MODULES`,
`scripts/audit_ux_certus.py:35`) **et du garde-fou** (`APPS_REGISTRY`,
`tests/ui/test_certus_suite_gui_guardrails.py:15`). Ils n'ont donc reçu **aucun** des
correctifs T1→T12. C'est vérifiable dans leurs mesures : ils sont les deux seuls modules à
porter un bouton de **20 px de haut** (`Copy Logs`), alors que le plancher de 24 px est
censé être appliqué partout depuis T8.

---

## 3. LES SIX DÉFAUTS DU JUGE — à corriger avant de toucher à l'interface

Chacun est mesuré. Chacun rend une conclusion de `TODO_UX_2026-09-03.md` inexploitable.

| # | Défaut | Preuve | Ce que ça a faussé |
|---|---|---|---|
| J1 | **Mesure une machine sans police** (`QT_QPA_PLATFORM=offscreen`, 0 famille chargée) | tableau du préambule ; `QFontDatabase.families()` rend **0** en offscreen nu, **344** en réel | toute la colonne `min`, donc le diagnostic « panneau qui déborde » et la cible « min ≤ 520 » de T3 |
| J2 | **Compte chaque table deux fois** — `findChildren(QTableWidget) + findChildren(QTableView)`, or `QTableWidget` **hérite** de `QTableView` | `audit_ux_certus.py:167` ; `issubclass(QTableWidget, QTableView)` → `True` | « 32 tables, 22 triables » est en réalité **16 tables, 11 triables** |
| J3 | **`left_min_px` est pris sur le `QScrollArea`, pas sur son contenu** | STRAT : le harnais annonce `min=446` alors que l'enfant le plus large du panneau réclame **886 px** | le verdict « control panel overflows » ne peut **jamais** se déclencher : les 8 panneaux sont dans un `QScrollArea` |
| J4 | **Ne mesure qu'à 1920×1080** | à 1366×768, **6 modules sur 8** tombent sous le seuil de 65 % : DESIGN 63,2 · RE 63,2 · INDEX 59,9 · FIELD 64,7 · METAL_SINGLE 58,1 · METAL_BILAYER 58,1 | le `setStretchFactor(0,0)` de T1 optimise 1920 et **dégrade 1366** |
| J5 | **Mesure les info-bulles mais n'en tire aucun verdict** | `input_no_tooltip` et `btn_no_tooltip` sont calculés (`:159`, `:164`) et n'apparaissent dans **aucune** branche de `_verdicts()` | le critère d'acceptation de T9 n'était vérifié par rien |
| J6 | **Un `ERROR` transitoire ressemble à une ligne de résultat** | sur 5 passes complètes, une a rendu `ERROR: no output` sur `CERTUS_RE`, **malgré les deux tentatives internes** ; les passes 2 à 5 sont identiques au bit | une régression et un aléa sont indiscernables |

### Et le garde-fou principal est inerte

`tests/ui/test_certus_suite_gui_guardrails.py` enveloppe **chaque** instanciation de fenêtre
dans :

```python
try:
    w = win_factory()
    assert w is not None
except Exception as e:
    assert not isinstance(e, NameError)
```

**Toute exception autre que `NameError` fait PASSER le test.** Démonstration :

```bash
python -c "
try:
    raise TypeError('la fenetre a explose')
except Exception as e:
    assert not isinstance(e, NameError)
print('le test passe alors que la fenetre a leve TypeError')
"
```

Et `tests/ui/test_a11y.py::test_w45_wcag_aa_contrast_pairs_light_and_dark` teste 5 paires
« en clair **et en sombre** » : **4 des 5 paires ont leurs deux jetons identiques dans les
deux modes** (`SUCCESS_BG`, `SUCCESS_TEXT`, `WARNING_*`, `DANGER_*`, `INFO_*` ne changent pas
avec `configure('dark')`). L'itération « dark » reteste les valeurs claires.

---

## 4. ÉTAT DE DÉPART — mesuré le 2026-09-04, plateforme réelle

### 4.1 Géométrie

⚠️ **Ce tableau est l'état du MATIN du 2026-09-04, avant la passe d'exécution.** Il est
conservé parce que les étapes ci-dessous s'y réfèrent. **L'état courant est au §0bis.**

```
etat du MATIN (perime, conserve pour la trace)
MODULE                  plot@1920  plot@1366  panneau  contenu reel  barre H  cache
CERTUS_HUB                    n/a        n/a      n/a           n/a      n/a    n/a
CERTUS_DESIGN                73.9       63.2      500           451      non      -
CERTUS_STRAT                 71.0       67.2      556           886      OUI  340 px
CERTUS_RE                    73.9       63.2      500           490      non      -
CERTUS_INDEX                 71.5       59.9      545           405      non      -
CERTUS_INDEX_SPLINE          72.4       72.5      523           872      OUI  444 px
CERTUS_FIELD                 74.9       64.7      480           380      non      -
CERTUS_METAL_SINGLE          70.2       58.1      570           525      non      -
CERTUS_METAL_BILAYER         70.2       58.1      570           455      non      -
```

📏 **Et l'état du SOIR, après la passe** — c'est celui-ci qu'il faut comparer :

```
MODULE                  plot@1920   panneau  min   contenu coupe @1366
CERTUS_DESIGN                73.9       500  450   -
CERTUS_STRAT                 71.0       556  446   -            <- corrige (etait 340 px)
CERTUS_RE                    73.9       500  412   -
CERTUS_INDEX                 71.5       545  406   -
CERTUS_INDEX_SPLINE          72.4       523  280   -            <- corrige (etait 444 px)
CERTUS_FIELD                 79.1       400  379   -
CERTUS_METAL_SINGLE          71.1       554  508   141 px       <- NOUVEAU, cree par 2.3
CERTUS_METAL_BILAYER         71.1       554  453    23 px       <- NOUVEAU, cree par 2.3
```

Hauteur minimale : les onze fenêtres tiennent en 768 px. ✅

🔴 **Deux modules cachent une partie de leur panneau derrière une barre de défilement
horizontale, dès l'ouverture, à 1920×1080** — et le harnais déclare les deux « OK ».
À 1366×768 c'est pire : STRAT cache 450 px, SPLINE 597 px.

### 4.2 Typographie

```
module                 police demandee   disponible   taille
CERTUS_HUB             Segoe UI          oui           9 pt
CERTUS_DESIGN          Open Sans         🔴 NON       10 pt
CERTUS_STRAT           Segoe UI          oui           9 pt
CERTUS_RE              Open Sans         🔴 NON       10 pt
CERTUS_INDEX           Segoe UI          oui          10 pt
CERTUS_INDEX_SPLINE    Segoe UI          oui          10 pt
CERTUS_FIELD           Segoe UI          oui          10 pt
CERTUS_METAL_SINGLE    Segoe UI          oui          10 pt
CERTUS_METAL_BILAYER   Segoe UI          oui          10 pt
CERTUS_SMOOTHER        Segoe UI          oui           9 pt
CERTUS_SUBSTRATE_INDEX Segoe UI          oui           9 pt
```

**Deux modules demandent une police absente** (Qt substitue en silence) et **la taille de
base varie de 9 à 10 pt selon le module**.

### 4.3 Dette du système visuel

```
couleurs hexadecimales codees en dur hors du theme   314   dans 44 fichiers
appels setStyleSheet( disperses                      314
tailles de police codees en dur                      170   occurrences
tailles de police DISTINCTES                          23   px ET pt melanges
emoji dans des appels visibles par l'utilisateur       36   dans 15 fichiers
regles QPushButton:focus dans toute la suite            0
appels setBuddy( dans tout certus/ui/                   0
```

Les 23 tailles : `11px`(58) `9pt`(19) `10px`(17) `14px`(14) `12px`(11) `13px`(9) `10pt`(9)
`9px`(5) `11pt`(5) `8pt`(4) `28px`(3) `20px`(3) `16px`(3) `8px`(2) `14pt`(2) `48px` `39px`
`34px` `17px` `15pt` `13pt` `12pt`.

Le thème possède une échelle d'espacement (`SPACING_XS/SM/MD/LG/XL` = 2/4/8/16/24), une
échelle de rayons, des graisses, et des jetons sémantiques (`SUCCESS`/`WARNING`/`DANGER`/
`INFO` avec variantes `_BG`/`_TEXT`). **Il n'a aucune échelle typographique** : seulement
`FONT_SIZE_BASE = 10`. D'où les 23 tailles ad hoc.

Il n'a pas non plus de jeton de marque pour RE, FIELD, SMOOTHER ni SUBSTRATE : le HUB peint
donc **RE avec la couleur de STRAT** et **FIELD avec celle de DESIGN**
(`certus_hub_config.py:45` et `:93`).

### 4.4 Accessibilité — ratios WCAG calculés, pas estimés

Mode clair : **1 échec réel**.

```
BORDER sur SURFACE (bordure de champ)   1.35 : 1   exige 3.0   ECHEC  #d7dfe8 / #ffffff
```

(`TEXT_DISABLED` rend 2,56 : 1, mais WCAG 2.1 SC 1.4.3 **exempte** explicitement les
composants inactifs. Ce n'est pas un échec de conformité ; c'est une question de lisibilité.)

Mode sombre réel, via `CertusTheme.configure('dark')` : **2 échecs**.

```
BORDER sur SURFACE                      1.48 : 1   exige 3.0   ECHEC  #2d3748 / #111827
blanc sur PRIMARY (tout bouton primaire) 2.54 : 1  exige 4.5   ECHEC  #ffffff / #60a5fa
```

Le second vient de `certus/ui/certus_theme.py:110-112` :
`background-color: {CertusTheme.PRIMARY}` avec `color: #ffffff` **codé en dur**. En sombre
`PRIMARY` devient `#60a5fa` et le libellé devient illisible. La règle `:hover` du même bloc
est figée à `#0353e9`, ce qui **inverse la luminosité** au survol en mode sombre.

Les jetons statiques `DARK_SURFACE`, `DARK_BACKGROUND`, `DARK_BORDER`, `DARK_CARD`,
`DARK_TEXT_*` sont **du code mort** : 0 usage hors du thème.

### 4.5 Le thème persisté n'est pas appliqué au démarrage

```bash
python -c "import sys; sys.path.insert(0,'.'); from certus.ui.certus_ui_widgets_utils import load_theme_config; print(load_theme_config())"
```

rend **`dark`** — et les onze fenêtres s'ouvrent en **clair**.

Cause : `load_theme_config()` n'est consulté au lancement que par
`certus/ui/certus_ui_utils.py:321`, et **uniquement** pour `apply_os_window_effects` (le
cadre OS de la fenêtre). Aucun chemin de démarrage n'appelle
`CertusTheme.configure(load_theme_config())`. Seul `_toggle_theme`
(`certus/ui/mixins/certus_base_core_mixins.py:426`) le fait, à l'action de l'utilisateur.

**Résultat visible : l'opérateur qui choisit le sombre rouvre l'application avec une barre de
titre sombre et une interface claire**, et la bascule affiche l'info-bulle « Switch to light
theme » alors que tout est clair.

Et cette bascule est un **cercle vide dans les onze fenêtres** :

```python
# certus/ui/certus_ui_widgets_utils.py:179
self.setText("" if mode == "light" else "")   # les DEUX branches sont vides
```

---

## 5. NOTES D'EXCELLENCE — état au 2026-09-04 et cible

Barème : **10 = éditeur scientifique du premier centile mondial** (Zemax OpticStudio, Ansys
Lumerical, Igor Pro, JetBrains). **5 = fonctionnel mais quelconque.**

Axes : **A1** première impression et occupation de l'espace · **A2** hiérarchie de
l'information · **A3** système visuel · **A4** interaction et clavier · **A5** retour d'état
· **A6** accessibilité · **A7** ergonomie métier · **A8** robustesse de mise en page ·
**A9** cohérence de suite.

| module | A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 | A9 | moy. | confiance |
|---|---|---|---|---|---|---|---|---|---|---|---|
| INDEX | 3 | 4 | 3 | 4 | 4 | 3 | 4 | 3 | 3 | **3,4** | audit détaillé, 18 constats |
| RE | 3 | 3 | 3 | 2 | 3 | 3 | 4 | 3 | 4 | **3,1** | audit détaillé, 17 constats |
| STRAT | 2 | 3 | 3 | 4 | 4 | 2 | 4 | 2 | 3 | **3,0** | audit détaillé, 16 constats |
| FIELD | 3 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 4 | **3,0** | audit détaillé, 18 constats |
| DESIGN | 3 | 3 | 3 | 2 | 3 | 2 | 3 | 3 | 4 | **2,9** | audit détaillé, 17 constats |
| INDEX SPLINE | 3 | 2,5 | 2,4 | 2,5 | 2,6 | 2,2 | 3,2 | 2,3 | 2,4 | **2,6** | audit détaillé, 17 constats |
| **HUB** | 1,5 | 2 | 2 | 3,2 | 1,8 | 1,5 | 3,3 | 3 | 2,8 | **2,3** | audit détaillé, 16 constats |
| METAL SINGLE | 2 | 2,5 | 3 | 2,8 | 2,6 | 2,5 | 2,7 | 1,8 | 2,6 | **2,5** | audit détaillé, 17 constats |
| SMOOTHER | 2,5 | 2,5 | 2 | 1,5 | 2 | 1,5 | 2,5 | 3,5 | 1,8 | **2,2** | audit détaillé, 17 constats |
| METAL BILAYER | 1,8 | 2,2 | 2,3 | 2,1 | 2,3 | 1,7 | 2,5 | 1,4 | 2,4 | **2,1** | audit détaillé, 17 constats |
| 🔴 **SUBSTRATE INDEX** | 1,8 | 2 | 1,8 | 1,5 | 1,7 | 1,6 | 1,5 | 1,4 | 1,7 | **1,7** | audit détaillé, 17 constats |

**Les onze fenêtres sont désormais auditées en détail. Aucune n'atteint 4 sur 10.** La
meilleure est INDEX à 3,4, la pire **SUBSTRATE INDEX à 1,7** — et ce sont les deux modules
que personne n'avait jamais regardés qui ferment la marche.

🔴 **SUBSTRATE INDEX n'est pas seulement mal noté : il est cassé.** Voir l'étape 2.14.

🔴 **Le HUB est l'avant-dernier, à 2,3 — et c'est la PREMIÈRE fenêtre que voit un
évaluateur.** ⚠️ Une revue visuelle rapide lui avait donné 3,3 ; l'audit ligne à ligne
descend à 2,3. **C'est la mesure de ce que vaut une note obtenue sans lire le code.**

🔴 **`n. m.` = non mesuré.** Ces trois modules n'ont pas reçu de revue détaillée. **Ne recopie
pas une note que tu n'as pas établie** : la première chose à faire pour eux est l'étape 2.0.

⚠️ **La note de SMOOTHER vient d'une revue visuelle et des mesures, pas d'un audit ligne à
ligne** : traite-la comme un ordre de grandeur, et attends-toi à ce qu'elle baisse — c'est ce
qui est arrivé au HUB (3,3 → 2,3) et à INDEX SPLINE (2,8 → 2,6) une fois le code lu.

**Cible de la mission : ≥ 8 sur les neuf axes, pour les onze fenêtres.**
Un 8 signifie « meilleur que la plupart des logiciels commerciaux du domaine ». Un 10 se
mérite et ne se décrète pas.

---

## 6. FORMAT DE CHAQUE ÉTAPE — c'est le cœur de l'anti-régression

**Toute étape que tu exécutes suit ce cycle, sans en sauter une case :**

```
1. LIS l'étape en entier.
2. ÉCRIS D'ABORD LE GARDE-FOU (le test), avant le correctif.
3. LANCE le garde-fou sur le code ACTUEL. Il DOIT ÉCHOUER.
   S'il passe, ton test ne teste rien : recommence-le. Ne passe pas à la suite.
4. APPLIQUE le correctif, et lui seul.
5. LANCE le garde-fou. Il doit passer.
6. LANCE la vérification de non-régression complète (§6.1).
7. COLLE les sorties dans ton compte rendu.
8. Si une sortie ne correspond pas : ARRÊTE-TOI. Ne contourne pas.
```

🔑 **Le point 3 est le seul qui distingue un garde-fou d'une décoration.** Un test qui passe
avant le correctif ne prouve rien — c'est exactement le défaut du garde-fou actuel de la
suite (§3).

### 6.1 La vérification de non-régression, après CHAQUE étape

```bash
python -m ruff check .
python -m pytest tests/ui/ tests/unit/test_gui_apps_smoke.py -q --no-cov
python scripts/audit_ux_certus.py
```

**Attendu** : `All checks passed!` · `0 failed` · aucune ligne du harnais dégradée par
rapport au cliquet (§8).

⚠️ **Le nombre de tests n'est pas un critère** : il augmente à chaque garde-fou que tu
ajoutes. **Seul `0 failed` compte.**

---

## PHASE 0 — RÉPARER LE JUGE

# ✅ FAITE ET VÉRIFIÉE LE 2026-09-04 — NE LA REFAIS PAS

Les huit étapes 0.1 à 0.8 sont appliquées et contrôlées (§0bis). **Ce qui suit est conservé
pour la trace : les mesures qui justifiaient chaque correctif sont citées ailleurs dans le
document.** Lis-les si tu as besoin du *pourquoi* ; n'exécute rien.

⚠️ **Un seul correctif de la phase 0 reste à faire, et il est né de l'usage** : le garde-fou
hscroll teste `hbar.isVisible()` au lieu de `hbar.maximum() > 0`, et laisse donc passer un
panneau tronqué dont la barre est désactivée par politique. Le correctif exact est au §0bis.

---

**Aucun pixel d'interface ne change dans cette phase.** Elle ne touche que
`scripts/audit_ux_certus.py` et `tests/ui/`.

🔴 **Tu ne dois exécuter AUCUNE étape des phases 1 et suivantes avant que la phase 0 soit
terminée et verte.** Mesurer avec un instrument faux, c'est produire des conclusions fausses
qui auront l'air justes.

---

### Étape 0.1 — Le harnais mesure une machine avec des polices

**Axe** A8 · **Fichier** `scripts/audit_ux_certus.py` · **Effort** S

**Pourquoi.** Voir le préambule : jusqu'à 28 % d'erreur sur les largeurs.

**Ce qu'il faut écrire.** Dans `_measure` et `_run_worker` :

1. Remplacer `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` par un réglage qui
   charge les polices **et** épingle la famille :

```python
# The offscreen plugin resolves NO font unless QT_QPA_FONTDIR points at a font
# directory: every glyph then renders as the missing-glyph box, whose advance
# width is not a real one. Measured 2026-09-04 on "Enable QWOT penalty":
#   offscreen bare            228 px
#   offscreen + FONTDIR       78 px  (default family, still wrong)
#   offscreen + FONTDIR + pinned Segoe UI 9pt   114 px
#   real windows platform                       115 px
# Pinning the family is what makes the measurement both headless and true.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
```

2. Juste après la création du `QApplication`, épingler la police **et le vérifier** :

```python
from PyQt6.QtGui import QFont, QFontDatabase

_PINNED_FAMILY = "Segoe UI"
if _PINNED_FAMILY not in QFontDatabase.families():
    raise SystemExit(
        f"AUDIT ABORTED: font '{_PINNED_FAMILY}' did not resolve. "
        "Every width would be measured on a machine that does not exist."
    )
app.setFont(QFont(_PINNED_FAMILY, 10))
```

3. Faire figurer dans **chaque** ligne de sortie JSON la configuration effective :

```python
out["qpa_platform"] = os.environ.get("QT_QPA_PLATFORM", "default")
out["font_family"] = QApplication.font().family()
out["font_point"] = QApplication.font().pointSizeF()
out["font_resolved"] = QApplication.font().family() in QFontDatabase.families()
```

🔑 **Le point 3 n'est pas décoratif.** C'est la règle du dépôt : *un run qui ne consigne pas
sa configuration n'est comparable à rien.* Deux mesures dont les `font_*` diffèrent ne se
comparent pas.

**Garde-fou — `tests/ui/test_ux_harness_integrity.py`, à créer :**

```python
def test_harness_pins_a_resolved_font() -> None:
    """The audit harness must never measure a machine without fonts.

    Measured 2026-09-04: with the bare offscreen plugin, QFontDatabase.families()
    returns 0 and the panel widths are wrong by up to 28 %.
    """
    src = Path("scripts/audit_ux_certus.py").read_text(encoding="utf-8")
    assert "QT_QPA_FONTDIR" in src
    assert "QFontDatabase.families()" in src
    assert '"font_family"' in src and '"qpa_platform"' in src
```

**Preuve d'utilité** — sur le code actuel :

```bash
python -m pytest tests/ui/test_ux_harness_integrity.py -q --no-cov
```
**Attendu : ÉCHEC** (les trois chaînes sont absentes).

**Vérification après correctif :**

```bash
python scripts/audit_ux_certus.py --json | python -c "import json,sys; r=json.load(sys.stdin); print([ (x['app'], x.get('font_family'), x.get('font_resolved')) for x in r ])"
```
**Attendu** : `font_resolved` vaut `True` pour les onze modules.

**Risque de régression.** Les largeurs vont **toutes bouger** — c'est le but. Toute valeur de
`TODO_UX_2026-09-03.md` devient caduque à cet instant. Ne compare rien à l'ancien.
⚠️ `QT_QPA_FONTDIR` est un chemin Windows : si la CI tourne ailleurs, le contrôle du point 2
doit lever plutôt que mesurer faux. **C'est voulu : mieux vaut pas de mesure qu'une fausse.**

---

### Étape 0.2 — Le harnais couvre les onze fenêtres

**Axe** A9 · **Fichiers** `scripts/audit_ux_certus.py`, `tests/ui/test_certus_suite_gui_guardrails.py` · **Effort** XS

**Pourquoi.** SMOOTHER et SUBSTRATE INDEX n'ont jamais été audités ni testés (§2), et ce sont
les deux seuls modules dont un bouton fait 20 px de haut.

**Ce qu'il faut écrire.** Dans `MODULES` (`audit_ux_certus.py:35`), ajouter :

```python
    "CERTUS_SMOOTHER": ("certus.utils.certus_curve_smoother", "CurveSmootherGUI"),
    "CERTUS_SUBSTRATE_INDEX": ("certus.ui.certus_substrate_ui", "SubstrateIndexGUI"),
```

Et les mêmes deux entrées dans `APPS_REGISTRY`
(`tests/ui/test_certus_suite_gui_guardrails.py:15`), en corrigeant la docstring qui annonce
« les 9 applications » : c'est **11 fenêtres pour 10 modules**.

**Garde-fou** — dans `tests/ui/test_ux_harness_integrity.py` :

```python
def test_harness_covers_every_module_the_hub_can_launch() -> None:
    """A module the HUB launches but the audit ignores receives no fix.

    Measured 2026-09-04: SMOOTHER and SUBSTRATE INDEX were missing, and they are
    the only two modules still carrying a 20 px-high button after T8.
    """
    from certus.core.certus_hub_config import HUB_APP_CATALOG
    import importlib.util
    spec = importlib.util.spec_from_file_location("_audit", "scripts/audit_ux_certus.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

    audited = {k.removeprefix("CERTUS_").replace("_", " ") for k in mod.MODULES}
    launched = {item["title"] for item in HUB_APP_CATALOG}
    assert not (launched - audited), f"modules lances mais jamais audites : {launched - audited}"
```

**Preuve d'utilité :** sur le code actuel, **ÉCHEC** avec
`{'SMOOTHER', 'SUBSTRATE INDEX'}`.

**Vérification :** `python scripts/audit_ux_certus.py` liste **11 lignes**.

**Risque de régression.** Deux modules jamais mesurés vont apparaître avec des défauts. **Ce
ne sont pas des régressions : ce sont des découvertes.** Ne les corrige pas ici — ils font
l'objet de la phase 4.

---

### Étape 0.3 — Ne plus compter chaque table deux fois

**Axe** A7 · **Fichier** `scripts/audit_ux_certus.py:167` · **Effort** XS

**Pourquoi.** `QTableWidget` hérite de `QTableView` ; l'addition des deux `findChildren`
double le compte. Le « 22/32 » publié vaut en réalité **11/16**.

**Ce qu'il faut écrire :**

```python
# QTableWidget IS-A QTableView: findChildren(QTableView) already returns every
# QTableWidget. Adding the two lists counted every table twice, which is why the
# suite was reported as having 32 tables when it has 16.
tables = win.findChildren(QTableView)
```

**Garde-fou :**

```python
def test_harness_does_not_double_count_tables() -> None:
    src = Path("scripts/audit_ux_certus.py").read_text(encoding="utf-8")
    assert "findChildren(QTableWidget) + findChildren(QTableView)" not in src.replace("win.", "")
```

**Preuve d'utilité :** **ÉCHEC** sur le code actuel.

**Vérification :** la colonne `tables` doit être **divisée par deux** :
DESIGN `?/3`, STRAT `?/2`, RE `?/2`, INDEX `?/2`, SPLINE `?/3`, FIELD `?/4`.

**Risque de régression.** La cible « ≥ 20/32 » de `TODO_UX` devient sans objet. La nouvelle
cible est **« aucune table de résultats non triable, aucune table d'empilement triable »**,
qui se vérifie table par table et non par un total.

---

### Étape 0.4 — Détecter le vrai débordement, celui que le `QScrollArea` masque

**Axe** A8 · **Fichier** `scripts/audit_ux_certus.py` · **Effort** S

**Pourquoi.** Défaut J3. STRAT cache **340 px** de son panneau et SPLINE **444 px** derrière
une barre horizontale, à 1920×1080, et le harnais déclare les deux « OK ».

**Ce qu'il faut écrire.** Dans `_measure`, après la section du splitter :

```python
# A vertical scrollbar in a control panel is normal. A HORIZONTAL one means part
# of the interface is simply unreachable without scrolling sideways.
# left.minimumSizeHint() cannot see this: the QScrollArea absorbs its content's
# width. Measured 2026-09-04, CERTUS_STRAT: minimumSizeHint says 446 px while the
# scroll area's content demands 886 px in a 556 px viewport.
from PyQt6.QtWidgets import QScrollArea

out["panel_hscroll_px"] = 0
if split is not None and split.widget(0) is not None:
    for area in split.widget(0).findChildren(QScrollArea):
        bar = area.horizontalScrollBar()
        if bar is not None and bar.isVisible():
            out["panel_hscroll_px"] = max(out["panel_hscroll_px"], int(bar.maximum()))
```

Et dans `_verdicts` :

```python
    if row.get("panel_hscroll_px"):
        bad.append(f"control panel hides {row['panel_hscroll_px']} px behind a horizontal scrollbar")
```

**Garde-fou — `tests/ui/test_ux_no_horizontal_scroll.py`, à créer :**

```python
@pytest.mark.parametrize("mod_path,cls_name", [...les 8 modules a splitter...])
@pytest.mark.parametrize("size", [(1920, 1080), (1366, 768)])
def test_control_panel_never_scrolls_sideways(qapp, mod_path, cls_name, size) -> None:
    """Part of a control panel must never be unreachable without scrolling sideways."""
    ...construire la fenetre, WA_DontShowOnScreen, resize(size), vider la file 1,5 s...
    for area in left.findChildren(QScrollArea):
        bar = area.horizontalScrollBar()
        assert not (bar and bar.isVisible()), (
            f"{cls_name} @ {size}: {bar.maximum()} px du panneau sont hors champ"
        )
```

**Preuve d'utilité :** **ÉCHEC sur STRAT et INDEX_SPLINE**, aux deux tailles. C'est
exactement ce qu'on veut : quatre échecs qui décrivent quatre défauts réels.

⚠️ **Ce test doit être marqué `xfail(strict=True)` pour STRAT et SPLINE jusqu'à ce que les
étapes 2.1 et 2.2 les corrigent** — puis le `xfail` est retiré dans la même étape que le
correctif. Un `xfail` non strict masquerait une correction accidentelle.

**Risque de régression.** Aucun : le harnais ne fait qu'observer.

---

### Étape 0.5 — Mesurer aux deux résolutions

**Axe** A8 · **Fichier** `scripts/audit_ux_certus.py` · **Effort** S

**Pourquoi.** Défaut J4 : à 1366×768, **6 modules sur 8** sont sous le seuil de 65 %, et le
harnais ne l'a jamais vu parce qu'il ne mesure qu'à 1920.

**Ce qu'il faut écrire.** Ajouter `--width` / `--height` (défaut 1920×1080), les propager au
worker, et les inscrire dans la sortie (`out["window"] = f"{w}x{h}"`). Puis ajouter une
option `--both` qui lance les deux passes et **échoue si l'une des deux échoue**.

**Vérification :**

```bash
python scripts/audit_ux_certus.py --width 1366 --height 768
```
**Attendu aujourd'hui** : 6 modules signalés sous 65 %. **C'est le point de départ, pas une
régression.**

**Risque de régression.** Le harnais va désormais signaler des défauts qui existaient déjà.
Ne « corrige » pas en remontant le seuil.

---

### Étape 0.6 — Un `ERROR` n'est plus un résultat, et les info-bulles deviennent un verdict

**Axe** A5/A9 · **Fichier** `scripts/audit_ux_certus.py` · **Effort** XS

**Ce qu'il faut écrire.**

1. `_run_worker` : porter les tentatives de 2 à **3**, et si les trois échouent, **sortir en
   code d'erreur avec un message explicite** plutôt que de rendre une ligne `ERROR` au milieu
   d'un tableau. 📏 Mesuré : sur 5 passes complètes, 1 a rendu un `ERROR` transitoire sur
   `CERTUS_RE` malgré les deux tentatives ; les passes 2 à 5 sont identiques au bit.

2. `_verdicts` : transformer les compteurs déjà mesurés en verdicts.

```python
    if row.get("input_no_tooltip"):
        bad.append(f"{row['input_no_tooltip']} inputs without a tooltip")
    if row.get("btn_no_tooltip"):
        bad.append(f"{row['btn_no_tooltip']} buttons without a tooltip")
```

**Vérification :** `python scripts/audit_ux_certus.py` signale désormais INDEX (8 champs),
SPLINE (4 champs, 4 boutons), SMOOTHER (3 champs, 5 boutons), SUBSTRATE (4 champs,
3 boutons).

**Risque de régression.** Aucun.

---

### Étape 0.7 — Réparer le garde-fou inerte

**Axe** A9 · **Fichier** `tests/ui/test_certus_suite_gui_guardrails.py` · **Effort** S

**Pourquoi.** §3 : toute exception autre que `NameError` fait passer le test.

**Ce qu'il faut écrire.** Supprimer les `try/except` et laisser l'exception remonter :

```python
    for win_factory in [...]:
        w = win_factory()          # any exception must fail the test, not only NameError
        assert w is not None
        w.deleteLater()
```

**Preuve d'utilité.** Avant de corriger, prouve que le test actuel ne teste rien :

```bash
python -c "
try:
    raise TypeError('boom')
except Exception as e:
    assert not isinstance(e, NameError)
print('motif inerte confirme')
"
```

Après correctif, `python -m pytest tests/ui/test_certus_suite_gui_guardrails.py -q --no-cov`
**doit rester vert**. 🔴 **S'il devient rouge, tu viens de découvrir une fenêtre réellement
cassée qui était masquée depuis toujours : NE la contourne pas, signale-la** et traite-la
comme une étape à part entière.

---

### Étape 0.8 — Rendre le test de contraste réel

**Axe** A6 · **Fichier** `tests/ui/test_a11y.py` · **Effort** S

**Pourquoi.** §3 : 4 des 5 paires testées ont leurs deux jetons identiques en clair et en
sombre, donc l'itération « dark » reteste les valeurs claires.

**Ce qu'il faut écrire.** Trois tests, pas un :

```python
def test_dark_mode_actually_changes_the_semantic_tokens() -> None:
    """Guards the reason the previous test proved nothing.

    Measured 2026-09-04: SUCCESS_BG/TEXT, WARNING_BG/TEXT, DANGER_BG/TEXT and
    INFO_BG/TEXT were identical in both modes, so 4 of the 5 pairs the contrast
    test iterated over in "dark" were in fact re-testing the light values.
    """
    CertusTheme.configure("light"); light = _snapshot()
    CertusTheme.configure("dark");  dark = _snapshot()
    CertusTheme.configure("light")
    unchanged = {k for k in light if light[k] == dark[k]}
    assert not unchanged, f"jetons identiques en clair et en sombre : {sorted(unchanged)}"


def test_wcag_aa_on_every_text_pair_in_both_modes() -> None:
    ...toutes les paires texte/fond, seuil 4.5...


def test_wcag_non_text_contrast_on_borders_in_both_modes() -> None:
    ...BORDER sur SURFACE, seuil 3.0...
```

**Preuve d'utilité.** Sur le code actuel, les trois **ÉCHOUENT** :
8 jetons identiques · `blanc sur PRIMARY` à 2,54 en sombre · `BORDER sur SURFACE` à 1,35
(clair) et 1,48 (sombre).

⚠️ **Ces trois tests resteront rouges jusqu'aux étapes 3.3 et 3.4.** Marque-les
`xfail(strict=True)` avec un commentaire pointant l'étape qui les lèvera, et **retire le
`xfail` dans cette étape-là**.

---

## PHASE 1 — POSER LE CLIQUET

# ✅ OUTILLAGE EN PLACE — 🔴 MAIS LA RÉFÉRENCE EST À REFAIRE

`tests/ui/test_ux_ratchet.py` (22), `test_ux_skeleton.py` (11), `test_ux_design_system.py` (5)
et `test_ux_harness_integrity.py` existent et fonctionnent — le squelette a **prouvé** son
utilité en détectant la perte du 2026-09-04 12:43.

🔴 **Mais `ux_baseline.json` a été régénéré à 13:09, après la perte : il fige quatre métriques
dégradées de DESIGN.** Il faut le refaire une fois les trois fichiers restaurés, et coller le
diff dans le compte rendu. Détail au §0bis.

---

**Une seule idée, et c'est la protection la plus forte du plan :** figer l'état mesuré, et
interdire mécaniquement qu'une métrique se dégrade. Le dépôt a déjà ce motif —
`tests/oracle/test_lint_debt_ratchet.py`.

---

### Étape 1.1 — Le cliquet UX

**Fichiers** `tests/ui/ux_baseline.json` (à créer), `tests/ui/test_ux_ratchet.py` (à créer)

**Ce qu'il faut écrire.**

1. Une fois la phase 0 terminée et verte, générer la référence :

```bash
python scripts/audit_ux_certus.py --json > tests/ui/ux_baseline.json
python scripts/audit_ux_certus.py --json --width 1366 --height 768 > tests/ui/ux_baseline_1366.json
```

2. Un test qui, pour chaque module et chaque métrique, **n'autorise que l'amélioration** :

```python
LOWER_IS_BETTER = (
    "btn_narrow", "btn_short", "btn_no_tooltip", "input_no_tooltip",
    "n_long_labels", "marketing_tabs", "panel_hscroll_px", "left_min_px",
)
HIGHER_IS_BETTER = ("tables_sortable", "tables_resizable", "n_shortcuts", "plot_pct")

def test_no_ux_metric_ever_gets_worse(metric_row, baseline_row) -> None:
    """A UX ratchet: metrics may improve, never degrade.

    To improve a figure, regenerate the baseline IN THE SAME CHANGE and say so.
    An unexplained baseline update is the thing this test exists to prevent.
    """
```

3. 🔴 **Le test doit aussi vérifier que la référence a été produite par la même
   configuration** :

```python
    assert current["font_family"] == baseline["font_family"]
    assert current["qpa_platform"] == baseline["qpa_platform"]
    assert current["window"] == baseline["window"]
```

Sans cela, quelqu'un régénérera la référence sur une autre machine et le cliquet se
désarmera en silence — exactement le défaut J1 qui a coûté la mission précédente.

**Preuve d'utilité.** Dégrade volontairement une métrique (par exemple retire un
`setSortingEnabled(True)`), lance le test : il **doit** échouer en nommant le module et la
métrique. **Puis remets la ligne.** Ne laisse pas la dégradation.

**Risque de régression.** Le cliquet peut devenir pénible s'il verrouille une métrique que
tu vas légitimement changer. **C'est le but.** La procédure est : régénérer la référence
**dans le même changement**, et l'écrire dans le compte rendu.

---

### Étape 1.2 — Le squelette d'interface

**Fichiers** `tests/ui/ux_skeleton.json` (à créer), `tests/ui/test_ux_skeleton.py` (à créer)

**Pourquoi.** Le cliquet surveille des nombres. Il ne verrait pas la **disparition d'un
contrôle**. Un refactor de mise en page peut faire perdre un bouton sans qu'aucun compteur
ne bouge.

**Ce qu'il faut écrire.** Pour chaque fenêtre, l'empreinte ordonnée des contrôles. 🟢 **Cette
version a été écrite et éprouvée le 2026-09-04, ne la réinvente pas :**

```python
def skeleton(win) -> list[str]:
    """One line per interactive control, in traversal order.

    A QTabWidget contributes its tab titles, so losing or renaming a tab shows up
    here too. Measured 2026-09-04 on three modules, two consecutive runs each:
    identical every time (DESIGN 118 controls, FIELD 52, METAL_SINGLE 33).
    """
    out = []
    for w in win.findChildren((QPushButton, QToolButton, QCheckBox, QRadioButton,
                               QComboBox, QLineEdit, QAbstractSpinBox, QTabWidget)):
        if not w.isVisible():
            continue
        if isinstance(w, QTabWidget):
            label = "/".join(w.tabText(i).replace("&", "").strip() for i in range(w.count()))
        else:
            label = (w.text() if hasattr(w, "text") else "") or ""
        out.append(f"{type(w).__name__}|{(label or w.objectName())[:48]}")
    return out
```

📏 **Contrôle de stabilité, obligatoire avant de figer la référence.** Un squelette qui varie
d'une exécution à l'autre produirait de **fausses régressions**, ce qui est pire qu'aucun
garde-fou. Lance-le deux fois et exige l'identité :

```
CERTUS_DESIGN           118 controles   passe 1 == passe 2 : OUI
CERTUS_FIELD             52 controles   passe 1 == passe 2 : OUI
CERTUS_METAL_SINGLE      33 controles   passe 1 == passe 2 : OUI
```

⚠️ **Génère la référence avec les mêmes précautions que le harnais** : un processus par
application, `QSettings` redirigés vers un INI jetable, `WA_DontShowOnScreen`, et 1,5 s de
vidage de la file d'événements. Sans l'isolation des `QSettings`, la référence porterait la
géométrie laissée par une session précédente.

Le test compare à la référence et **exige qu'aucune entrée ne DISPARAISSE**. Les ajouts sont
autorisés (on améliore), les suppressions demandent une mise à jour explicite de la référence
**dans le même changement**.

**Preuve d'utilité.** Commente la création d'un bouton, lance le test : il doit nommer le
bouton disparu. **Puis décommente.**

---

### Étape 1.3 — Verrouiller les invariants du système visuel

**Fichier** `tests/ui/test_ux_design_system.py` (à créer)

Ces contrôles sont **statiques** (lecture des sources) donc indépendants de la police et de
la plateforme. Ils ne peuvent pas mentir.

```python
def test_no_new_hardcoded_hex_outside_the_theme() -> None:
    """Ratchet. Measured 2026-09-04: 314 occurrences in 44 files."""
    assert count_hex_outside_theme() <= 314

def test_no_new_hardcoded_font_size() -> None:
    """Ratchet. Measured 2026-09-04: 170 occurrences, 23 distinct sizes, px and pt mixed."""
    assert count_hardcoded_font_sizes() <= 170

def test_no_emoji_in_user_facing_labels() -> None:
    """Ratchet. Measured 2026-09-04: 36 occurrences in 15 files."""
    assert count_user_facing_emoji() <= 36

def test_font_point_size_is_uniform_across_the_suite() -> None:
    """Measured 2026-09-04: HUB/STRAT/SMOOTHER/SUBSTRATE at 9 pt, the six others at 10 pt."""

def test_every_module_requests_an_installed_font() -> None:
    """Measured 2026-09-04: DESIGN and RE request 'Open Sans', absent from the machine."""
```

🔑 **Chaque seuil est le chiffre mesuré aujourd'hui, et il ne peut que descendre.** Un
correctif qui en ajoute un est refusé. Un correctif qui en retire dix met à jour le seuil
dans le même changement.

---

## PHASE 2 — LES DÉFAUTS BLOQUANTS

Ordre imposé : chacun est visible en dix secondes par un évaluateur.

---

### Étape 2.0 — Compléter l'audit des cinq modules non mesurés

**Modules** RE, INDEX, METAL SINGLE, METAL BILAYER, SUBSTRATE INDEX · **Effort** M

🔴 **Ces cinq modules portent `n. m.` dans la table du §5.** Avant de les corriger, il faut
les regarder. Produis pour chacun la même grille que le §5, en te fondant sur :

```bash
# les captures, avec de vraies polices et sans fenetre visible
#   (le script d'instrumentation est decrit en annexe A)
python shot_ux.py --only CERTUS_RE --out <dossier>
```

**Rends** : les 9 notes, leur justification en une ligne chacune, et 10 à 18 constats au
format du §6. **Ne corrige rien à cette étape.**

---

### Étape 2.1 — STRAT : le panneau cache 340 px de lui-même

# ✅ FAITE ET VÉRIFIÉE — `plot%` 67,5 → 71,0 · `viewport 536 / contenu 536` · `hbar_max = 0`

**Axe** A8 · **Note visée** 2 → 8 · **Effort** M
**Fichier** `certus/ui/certus_strat_ui_layout.py`

**Pourquoi.** Sonde Qt, plateforme réelle : à 1920×1080, `viewport 556 px / contenu 886 px /
barre horizontale visible, maximum 340`. À 1366×768 : 436 / 886, **450 px cachés**. Visible
sur la capture : « Low-Index (L… », « Custom ( », « Center lam… » sont coupés net.

**Cause racine, mesurée.** L'onglet « Design » impose un minimum de **844 px** à lui seul, et
il le doit à **une seule ligne horizontale** de la carte « Material Refractive Indices »
(834 px) : le libellé « Material File: » et sa combo sont sur la **même** `QHBoxLayout` que
le bouton radio et le champ `n (real)`.

**Ce qu'il faut faire, dans cet ordre.**

1. Dans `_create_material_group`, sortir « Material File: » + la combo de `combined_layout`
   et les poser sur une **seconde** `QHBoxLayout` ajoutée à la suite. Poser sur la combo
   `setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)` et
   un `setMinimumContentsLength(12)`.
2. Seulement ensuite, dans `apply_default_layout`, remplacer
   `floor = left_panel.minimumSizeHint().width()` par
   `floor = max(left_panel.minimumSizeHint().width(), left_panel.sizeHint().width())`.

🔴 **L'ordre compte.** Faire (2) sans (1) élargit le panneau à 612 px et fait tomber la zone
graphique à 748 px sur un écran 1366. Faire (1) d'abord ramène le `sizeHint` sous 560.

**Garde-fou.** Le test de l'étape 0.4, dont on **retire le `xfail`** pour STRAT.

**Vérification :**

```bash
python -m pytest tests/ui/test_ux_no_horizontal_scroll.py -q --no-cov -k STRAT
python scripts/audit_ux_certus.py --only CERTUS_STRAT
python scripts/audit_ux_certus.py --only CERTUS_STRAT --width 1366 --height 768
```
**Attendu** : plus de ligne `control panel hides ... px`, `plot%` ≥ 65 aux deux tailles.

**Risque de régression.** La carte matériaux gagne ~60 px de hauteur (deux rangées au lieu
d'une, ×2 matériaux) dans un viewport de 723 px : plus de défilement **vertical**, ce qui est
acceptable. Le cliquet vérifiera que `plot_pct` ne descend pas.

---

### Étape 2.2 — INDEX SPLINE : le panneau cache 444 px

# ✅ FAITE ET VÉRIFIÉE — `viewport 511 / contenu 511`, plus de barre horizontale

⚠️ Si une sonde te signale encore ~325 px de débordement sur SPLINE, **c'est un faux
positif** : la zone en cause a `visible=0` et son parent est un `QStackedWidget` resté à la
géométrie Qt par défaut 640×480. Une page jamais affichée n'est pas un débordement.

**Axe** A8 · **Note visée** 2 → 8 · **Effort** M
**Fichiers** `certus/ui/certus_index_spline_common.py`, `certus_index_spline_managers_ui.py`

**Pourquoi.** Même sonde : `viewport 511 / contenu 872 / barre visible, maximum 444`. À
1366 : **597 px cachés**. Confirmé visuellement — le curseur de la barre horizontale couvre
~57 % de la largeur du panneau.

⚠️ **Un chiffre à ne pas reprendre.** Un `minimumSizeHint` de **3860 px** apparaît sur un
`QTabWidget` du panneau. **Ce n'est pas un débordement** : son widget de contenu ne fait que
513 px et aucune barre n'apparaît pour lui. Un `QTabWidget` propage le minimum de sa page la
plus large même quand elle n'est pas affichée. Le débordement réel est de **444 px**, pas
3347.

**Ce qu'il faut faire.** Identifier la page d'onglet qui porte le minimum de 872 px (une
table à 9 colonnes est la première suspecte) et lui donner un `QScrollArea` **propre**, ou
réduire ses colonnes. **Mesure avant de corriger** : la sonde de l'annexe A donne la
décomposition carte par carte.

**Garde-fou.** Retrait du `xfail` SPLINE de l'étape 0.4.

---

### Étape 2.3 — Six modules sous 65 % de zone graphique à 1366×768

# 🟠 ENGAGÉE, ET ELLE A CRÉÉ UN DÉFAUT — à reprendre avec le garde-fou corrigé

Le panneau des deux METAL est descendu de 570 à **394 px** à 1366, c'est-à-dire **sous la
largeur de son propre contenu**. Résultat mesuré : `METAL SINGLE` coupe **141 px** et
`METAL BILAYER` **23 px**, sans barre pour y accéder (`ScrollBarAlwaysOff`). Détail et
correctif du garde-fou au §0bis.

🔑 **C'est exactement l'avertissement écrit plus bas dans cette étape** — *« ne descends pas
sous le minimum réel du contenu »*. Il a été franchi parce que le garde-fou ne pouvait pas le
signaler. **Corrige d'abord le garde-fou, puis reprends la mise en page.**

**Axe** A8 · **Note visée** 3 → 8 · **Effort** M
**Modules** DESIGN, RE, INDEX, FIELD, METAL SINGLE, METAL BILAYER

**Pourquoi.** Mesuré : le `left_px` reste **figé** quand la fenêtre rétrécit (DESIGN 500 à
1920 comme à 1366 ; INDEX 545 ; METAL 570), alors que STRAT et SPLINE, eux, cèdent du terrain
(622→446, 523→370). C'est le `setStretchFactor(0, 0)` de T1 : il donne tout le surplus au
graphe quand la fenêtre est large, et **empêche le panneau de rendre de la place** quand elle
est étroite.

**Ce qu'il faut écrire.** Le facteur d'étirement ne suffit pas : il faut une **largeur
maximale relative**. Dans le `resizeEvent` de la classe de base (ou via un
`eventFilter` sur le splitter), borner le panneau à **35 % de la largeur de la fenêtre** :

```python
# setStretchFactor(0, 0) keeps the panel at its requested width, which is right
# when the window is wide and wrong when it is narrow: measured 2026-09-04, six
# modules fall under 65 % of plot area at 1366x768 while staying above 70 % at
# 1920x1080. Cap the panel at a share of the window instead.
cap = int(self.width() * 0.35)
sizes = main_splitter.sizes()
if sizes and sizes[0] > cap:
    main_splitter.setSizes([cap, self.width() - cap])
```

⚠️ **Ne descends pas sous le minimum réel du contenu** : cela recréerait le défaut de
l'étape 2.1. Le plancher est `left_panel.sizeHint().width()` **après** les corrections des
étapes 2.1 et 2.2.

**Garde-fou :**

```python
@pytest.mark.parametrize("size", [(1920, 1080), (1366, 768)])
def test_plot_area_is_at_least_65_percent(qapp, mod_path, cls_name, size) -> None:
    """Measured 2026-09-04: six modules were under 65 % at 1366x768 while all
    eight were above 70 % at 1920x1080. Measuring one size hid the defect."""
```

**Preuve d'utilité :** **6 échecs** à 1366 sur le code actuel, 0 à 1920.

---

### Étape 2.4 — Le mode sombre rend les boutons primaires illisibles

**Axe** A6 · **Note visée** 2 → 9 · **Effort** S
**Fichier** `certus/ui/certus_theme.py:110-128`

**Pourquoi.** `color: #ffffff` codé en dur sur `background-color: {CertusTheme.PRIMARY}`.
En sombre `PRIMARY` = `#60a5fa` ⇒ **2,54 : 1**, échec AA. Et `:hover` figé à `#0353e9`
**inverse la luminosité** en sombre.

**Ce qu'il faut écrire.** Introduire deux jetons dans `CertusTheme`, différenciés par mode :

```python
PRIMARY_TEXT = "#ffffff"       # light: white on #0f62fe -> 5.00:1
PRIMARY_HOVER = "#0353e9"
# dark: PRIMARY becomes #60a5fa, so the label must go dark, not white
# (measured 2026-09-04: white on #60a5fa = 2.54:1, fails AA 4.5:1)
```

et les faire basculer dans `configure()`. Remplacer les deux littéraux du bloc par les
jetons.

**Garde-fou.** Retrait du `xfail` de `test_wcag_aa_on_every_text_pair_in_both_modes`
(étape 0.8).

**Vérification.** Le test de contraste passe dans les deux modes, seuil 4,5.

**Risque de régression.** `get_primary_button_stylesheet` est marquée `DEPRECATED` mais reste
appelée. **Cherche tous les appelants avant** : `grep -rn get_primary_button_stylesheet certus/`.

---

### Étape 2.5 — La préférence de thème n'est pas appliquée au démarrage

**Axe** A5/A9 · **Note visée** 3 → 9 · **Effort** S
**Fichiers** `certus/ui/certus_ui_utils.py`, `certus/ui/certus_ui_widgets_utils.py:179`

**Pourquoi.** §4.5 : `load_theme_config()` rend `dark` et les onze fenêtres s'ouvrent en
clair. La bascule affiche « Switch to light theme » alors que tout est clair.

**Ce qu'il faut écrire.**

1. Au démarrage, avant la construction de la fenêtre, appliquer la préférence :

```python
# The persisted preference reached only apply_os_window_effects, so a user who
# chose dark reopened the app with a dark title bar and a light interface.
mode = load_theme_config()
CertusTheme.configure(mode)
CertusTheme.apply_to_app(QApplication.instance(), mode == "dark")
update_global_plot_config(mode == "dark")
```

2. Corriger le ternaire dégénéré :

```python
# Both branches were the empty string, so the 32x32 toggle rendered as an empty
# circle in all eleven windows.
self.setText("\u25d0" if mode == "light" else "\u25d1")
```

⚠️ **N'utilise pas d'emoji hors du plan multilingue de base** : ils rendent en tofu selon la
police. `◐` / `◑` (U+25D0/U+25D1) sont sûrs.

**Garde-fou :**

```python
def test_startup_applies_the_persisted_theme(monkeypatch) -> None:
    """Measured 2026-09-04: load_theme_config() returned 'dark' while every one of
    the eleven windows opened in light."""

def test_theme_toggle_is_not_empty() -> None:
    src = Path("certus/ui/certus_ui_widgets_utils.py").read_text(encoding="utf-8")
    assert 'setText("" if mode == "light" else "")' not in src
```

**Preuve d'utilité :** les deux **ÉCHOUENT** aujourd'hui.

**Risque de régression.** 🔴 **Toutes les captures de référence changent si la préférence
persistée est `dark`.** Le harnais doit **forcer le mode clair** pour mesurer
(`CertusTheme.configure("light")` après l'isolation des `QSettings`), sinon le cliquet
comparera deux thèmes. **Fais ce réglage dans la même étape.**

---

### Étape 2.6 — DESIGN : quatre raccourcis morts

**Axe** A4 · **Note visée** 2 → 8 · **Effort** XS
**Fichier** `certus/ui/certus_design_ui_events.py:25-28`

**Pourquoi.** `zoom_in=getattr(self, "zoom_in_ui", None)` — `self` est le délégué
`EventsManager`, pas la fenêtre. Les quatre `getattr` rendent `None`. **`Ctrl+0`, `Ctrl++`,
`Ctrl+-` et `Ctrl+L` ne font rien.**

**Ce qu'il faut écrire.** Remplacer les quatre `getattr(self, ...)` par
`getattr(self.ui, ...)`.

**Garde-fou :**

```python
def test_design_zoom_shortcuts_are_bound_to_a_callable() -> None:
    """Measured 2026-09-04: the four getattr() targeted the EventsManager delegate
    instead of the window, so Ctrl+0 / Ctrl++ / Ctrl+- / Ctrl+L were silently dead."""
```

**Risque de régression.** ⚠️ `Ctrl+0` figure dans `WINDOW_LEVEL_SEQUENCES`,
`tests/ui/test_certus_shortcut_uniqueness.py:34`, qui exige **exactement une** liaison par
fenêtre. Lance ce test après.

---

### Étape 2.7 — DESIGN : trier la table des cibles désaligne les valeurs

**Axe** A7 · **Sévérité BLOQUANT** · **Effort** XS
**Fichier** `certus/ui/certus_design_ui_layout.py:956`

**Pourquoi.** `target_table.setSortingEnabled(True)` alors que la table est peuplée par
`setCellWidget` (`certus_design_ui_events.py:495`). **Qt ne déplace pas les cell widgets au
tri** : cliquer sur un en-tête associe les widgets d'une ligne aux données d'une autre.
C'est une cible spectrale fausse, silencieusement.

**Ce qu'il faut écrire.** Supprimer la ligne 956 et laisser le `setSectionResizeMode(Interactive)`
déjà présent. Ajouter le commentaire expliquant pourquoi, comme pour `front_table`.

**Garde-fou :**

```python
def test_tables_holding_cell_widgets_are_not_sortable() -> None:
    """Qt does not move cell widgets when sorting: a sort would pair one row's
    widgets with another row's data. Measured 2026-09-04 on DESIGN target_table."""
```

**Risque de régression.** Aucun test n'assère `setSortingEnabled` (0 occurrence dans
`tests/`). ⚠️ `_qs_restore_table_headers` (`certus_base_app.py:650`) restaure l'état
d'en-tête persisté : vérifie qu'il ne réactive pas le tri.

---

### Étape 2.8 — STRAT : le tableau multi-graines est peuplé le tri actif

**Axe** A7 · **Sévérité MAJEUR** · **Effort** XS
**Fichier** `certus/ui/certus_strat_multigraine_ui.py:550-568`

**Pourquoi.** `setSortingEnabled(True)` (`:394`) n'est jamais désactivé pendant le
remplissage. C'est le piège documenté dans `TODO_UX` T2 — et il a été laissé ici.

**Ce qu'il faut écrire :**

```python
        etait = self._mg_table.isSortingEnabled()
        self._mg_table.setSortingEnabled(False)
        # ... setRowCount + boucle de remplissage ...
        self._mg_table.setSortingEnabled(etait)
```

**Garde-fou.** Un test qui remplit la table avec trois graines et vérifie que la ligne 0
porte bien les chiffres de la graine 0.

---

### Étape 2.9 — 🔴 FIELD : trier « Design Result » décrit un filtre physiquement faux

# ⚠️ CETTE ÉTAPE A CHANGÉ DE NATURE LE 2026-09-04 — LIS CE CADRE AVANT LE RESTE

📏 Mesuré : `certus/ui/certus_ui_widgets_utils.py` est **revenu à `HEAD`** (§0bis). Il en
résulte que :

- **plus aucune table de la suite n'est triable** — le défaut décrit ci-dessous **n'est donc
  plus reproductible en l'état** ;
- **`certus_lock_row_order()` n'existe plus**, ni `CERTUS_ALLOW_SORTING` : le texte ci-dessous
  qui dit *« le mécanisme de protection existe déjà et fonctionne »* est **périmé** ;
- le tri des tables de résultats, qui était un acquis, est perdu avec lui.

🔑 **Ce qu'il faut faire à la place, et l'ordre compte :**

1. **Restaurer** l'`__init__` d'`ExcelTableWidget` *et* `certus_lock_row_order()` depuis
   l'état d'avant 12:43.
2. **Dans le même changement**, appeler `certus_lock_row_order()` sur les **quatre** tables
   d'empilement — `front_table` (RE), `stack_table` (STRAT), `table_design_res` (FIELD),
   `table_layers` (FIELD) — et non plus trois. C'était l'oubli d'origine.
3. Poser le garde-fou exhaustif décrit plus bas, qui vaut pour toute table future.

🔴 **Ne restaure pas le tri sans les verrous dans le même geste.** Entre les deux, la suite
serait dans l'état exact que cette étape existe pour empêcher.

---

**Axe** A7 · **Sévérité BLOQUANT — c'est le constat le plus grave de l'audit** · **Effort** XS
**Fichier** `certus/ui/certus_field_layout_mixin.py:288`

**Pourquoi.** `certus/ui/certus_field_plot_mixin.py:174-199` remplit cette table avec, dans
l'ordre : `"0 (Superstrate)"`, puis les couches **dans l'ordre de dépôt**, puis
`"N+1 (Substrate)"`. C'est **l'empilement optique lui-même**. Or elle est créée par
`ExcelTableWidget()`, dont `CERTUS_ALLOW_SORTING` vaut `True` par défaut
(`certus_ui_widgets_utils.py:368`).

Un clic sur l'en-tête « Layer » trie **en texte** et rend :
`0 (Superstrate)` · `1` · `10 (Substrate)` · `2` · `3` … — **le substrat se retrouve entre la
couche 1 et la couche 2.** L'opérateur lit alors une description de filtre qui n'existe pas,
et rien ne le signale.

🟢 **Le mécanisme de protection existe déjà et fonctionne** :
`ExcelTableWidget.certus_lock_row_order()` (`certus_ui_widgets_utils.py:407-414`), dont la
docstring dit exactement *« Call it on any table holding an optical STACK »*. Il est appelé
sur `front_table` (`certus_re_layout_mixin.py:937`) et sur `stack_table`
(`certus_strat_ui_layout.py:645`). **Il a été oublié sur la troisième.**

**Ce qu'il faut écrire.** Après la ligne 288 :

```python
        self.table_design_res.certus_lock_row_order()
```

**Garde-fou — le contrôle doit être EXHAUSTIF, pas ponctuel :**

```python
STACK_TABLES = {
    ("certus.ui.certus_re_layout_mixin", "front_table"),
    ("certus.ui.certus_strat_ui_layout", "stack_table"),
    ("certus.ui.certus_field_layout_mixin", "table_design_res"),
    ("certus.ui.certus_field_common", "table_layers"),
}

def test_no_table_holding_an_optical_stack_is_sortable() -> None:
    """Row order IS the physics: sorting a stack table describes another filter.

    Measured 2026-09-04: table_design_res was sortable and its first column reads
    "0 (Superstrate)", "1", ... "N+1 (Substrate)". A text sort puts the substrate
    between layer 1 and layer 2.
    """
    for win in every_window():
        for name in stack_table_names(win):
            assert not getattr(win, name).isSortingEnabled(), (
                f"{name} decrit un empilement et est triable"
            )
```

**Preuve d'utilité :** **ÉCHEC** sur `table_design_res` aujourd'hui.

**Risque de régression.** Nul : `certus_lock_row_order()` ne fait que désactiver le tri.
⚠️ **Vérifie qu'aucune autre table d'empilement n'a été oubliée** : `grep -rn "= ExcelTableWidget()" certus/`
rend 16 instances ; passe-les toutes en revue et complète `STACK_TABLES`.

---

### Étape 2.10 — Les tables de résultats trient les nombres comme du texte

# ⚠️ SUSPENDUE JUSQU'À LA RESTAURATION DE L'ÉTAPE 2.9

Sans tri, ce défaut est en sommeil. **Il reviendra dès que tu restaureras l'`__init__`
d'`ExcelTableWidget`** — traite donc 2.10 dans la foulée de 2.9, pas plus tard. Le correctif
ci-dessous reste valable et il est **testé** ; c'est le moment de l'appliquer qui change.

---

**Axe** A7 · **Sévérité MAJEUR** · **Effort** S
**Fichier** `certus/ui/certus_ui_widgets_utils.py`

**Pourquoi.** `ExcelTableWidget` active le tri par défaut, et les cellules sont peuplées avec
des `QTableWidgetItem` portant du texte. Le tri de Qt compare alors des chaînes :
**λ = 1000,0 se classe avant λ = 300,0.** Une colonne de longueurs d'onde triée est donc dans
un ordre faux — et elle a l'air triée.

### 🔴 Le correctif évident NE MARCHE PAS — je l'ai essayé pour toi

La solution que tout le monde écrit d'abord est de poser la valeur en
`Qt.ItemDataRole.EditRole`. 📏 **Mesuré le 2026-09-04, elle échoue deux fois :**

```
valeurs inserees        ['300.0', '1000.0', '450.0', '-12,5', 'n/a']
avec setData(EditRole)  ['1000.0', '-12.5', '300.0', '450.0', 'n/a']
                                     ^^^^^ l'affichage a ete CORROMPU
```

1. **Elle ne trie toujours pas** : `QTableWidgetItem.__lt__` compare le `DisplayRole`.
2. **Elle corrompt l'affichage** : sur un `QTableWidgetItem`, Qt traite `EditRole` et
   `DisplayRole` comme la **même** valeur. `-12,5` est devenu `-12.5` — la virgule décimale
   française a disparu de l'écran.

**Ce qu'il faut écrire — testé, celui-là.** Dans `certus/ui/certus_ui_widgets_utils.py`, à
côté d'`ExcelTableWidget` :

```python
class NumericAwareItem(QTableWidgetItem):
    """Sorts numerically when both cells hold a number, alphabetically otherwise.

    Overriding __lt__ is the only approach that works: QTableWidgetItem compares
    the DisplayRole, and on this class Qt treats EditRole and DisplayRole as the
    same value, so writing a float into EditRole would silently rewrite what the
    operator sees (measured 2026-09-04: "-12,5" was displayed as "-12.5").
    """

    def __lt__(self, other) -> bool:
        try:
            return float(self.text().replace(",", ".")) < float(other.text().replace(",", "."))
        except (ValueError, AttributeError):
            return super().__lt__(other)
```

puis utiliser `NumericAwareItem` à la place de `QTableWidgetItem` dans le remplisseur commun
(`set_data`).

📏 **Résultat mesuré avec ce correctif :**

```
['-12,5', '300.0', '450.0', '1000.0', '1e3', 'n/a']
affichage preserve au caractere pres : True
```

La virgule décimale est conservée, la notation scientifique est comprise, et une cellule non
numérique (`n/a`) retombe proprement sur le tri alphabétique.

**Garde-fou :**

```python
def test_numeric_columns_sort_numerically_without_altering_the_display() -> None:
    """Measured 2026-09-04: text sorting put 1000.0 before 300.0, and the obvious
    EditRole fix rewrote "-12,5" as "-12.5" on screen."""
    t = ExcelTableWidget()
    t.set_data(["lambda"], [["300.0"], ["1000.0"], ["450.0"], ["-12,5"]])
    t.sortItems(0, Qt.SortOrder.AscendingOrder)
    shown = [t.item(r, 0).text() for r in range(4)]
    assert shown == ["-12,5", "300.0", "450.0", "1000.0"]
```

**Preuve d'utilité :** **ÉCHEC** — l'ordre rendu aujourd'hui est
`['1000.0', '-12,5', '300.0', '450.0']`.

**Risque de régression.** Faible : `__lt__` n'est consulté que pendant un tri, et l'affichage
n'est jamais réécrit. ⚠️ **Vérifie que le remplisseur commun est bien le seul chemin** :
`grep -rn "QTableWidgetItem(" certus/ | wc -l` — chaque site qui construit un item à la main
continuera de trier en texte.

---

### Étape 2.11 — 🔴 INDEX : « Detach Plot » détache le mauvais graphe

**Axe** A4 · **Sévérité BLOQUANT** · **Effort** S
**Fichier** `certus/ui/certus_index_ui_events.py:1001`

**Pourquoi.** Le bouton est câblé sur des **index d'onglets en dur**
(`if current_index == 0:` → « spectrum », etc.) qui ne correspondent plus à l'ordre réel.
`certus_index_ui_layout.py:332` appelle `_add_main_control_buttons()`, qui fait
`self.tabs.addTab(data_tab, "Data")` à la ligne 619 — donc **avant** les `addTab` des lignes
353/361/365/394/430.

📏 **Ordre réellement construit, mesuré le 2026-09-04 sur la fenêtre instanciée :**

```
index 0 -> 'Data'            index 3 -> 'n & k'
index 1 -> 'Synthesis'       index 4 -> 'Convergence'
index 2 -> 'Spectrum'        index 5 -> 'Final Equations'
onglet actif au demarrage : index 0 = 'Data'
```

Le gestionnaire suppose `index 0 = Spectrum`. **Le décalage est de deux crans, pas un** :
chaque branche détache le graphe d'un autre onglet, et « Detach Plot » sur l'onglet *Data*
détache le spectre.

🔑 **Le même décalage explique un second défaut** : `certus_index_ui_layout.py:502` porte le
commentaire *« Spectrum Tab (0): visible by default »* suivi de `setCurrentIndex(0)`. Le
module s'ouvre donc sur **Data**, un onglet vide, alors que le code déclare vouloir ouvrir sur
le spectre. **Une seule correction éteint les deux.**

**Ce qu'il faut écrire.** Ne jamais adresser un onglet par son index. Résoudre par le widget
courant :

```python
        # Tab indices are assigned in construction order, and _add_main_control_buttons
        # inserts "Data" before the plot tabs: any hard-coded index is stale the moment
        # a tab is added. Resolve the plot from the current widget instead.
        current = self.tabs.currentWidget()
        plot = current.findChild(CertusScientificPlot) if current is not None else None
```

**Garde-fou :** pour chaque onglet, activer l'onglet puis vérifier que le graphe détaché est
bien un enfant de **cet** onglet.

**Preuve d'utilité :** **ÉCHEC** sur au moins trois onglets.

---

### Étape 2.12 — 🔴 RE : une fenêtre de rétractation déguisée en confirmation

**Axe** A4 · **Sévérité BLOQUANT** · **Effort** S
**Fichiers** `certus/ui/certus_re_workers_mixin.py:563`, `certus/ui/certus_ui_utils.py:1117-1146`

**Pourquoi.** ⚠️ **Sois juste sur ce constat : le mécanisme n'est pas absurde, il est mal
nommé et mal placé.** `confirm_stop_with_timeout` est en réalité une **fenêtre de
rétractation** — l'opérateur a demandé l'arrêt, on lui laisse 10 s pour se raviser, sinon on
arrête. C'est un motif défendable. La docstring le dit :

```
Stops automatically after timeout if no action is taken.
Returns: True: Stop confirmed (timeout or 'Stop Now' clicked).
```

**Trois défauts s'y greffent, et ceux-là sont réels :**

1. 🔴 **Elle est appelée avant tout test d'exécution.** `stop_optim()`
   (`certus_re_workers_mixin.py:563`) commence par `if not confirm_stop_with_timeout(self)`.
   Appuyer sur Échap **alors que rien ne tourne** ouvre donc une boîte qui décompte l'arrêt
   de rien, et se répond toute seule. Le bouton STOP n'est jamais désactivé non plus.
2. 🔴 **Elle est habillée en question** — titre « Stop Confirmation », icône
   `QMessageBox.Icon.Question`, bouton par défaut « Stop Now ». Un opérateur lit une
   confirmation, pas un compte à rebours. Les deux métaphores sont mélangées.
3. **Faute de langue dans un texte visible** : *« Click 'Cancel' to continuous
   optimization. »* — lire « to continue the optimization ».

**Ce qu'il faut écrire.**

1. Garder le mécanisme, mais **ne l'ouvrir que si un calcul tourne** :
   `if self._re_worker is None or not self._re_worker.isRunning(): return`, **avant** l'appel.
2. Désactiver le bouton STOP au repos.
3. Renommer et réhabiller : titre « Stopping… », icône `Information`, texte
   « L'arrêt aura lieu dans N s. Le meilleur résultat courant sera conservé. », bouton
   principal « Reprendre » (annule l'arrêt) et bouton secondaire « Arrêter maintenant ».
   L'intitulé doit dire ce qui va se passer tout seul.
4. Corriger la phrase du point 3 ci-dessus.

🔴 **Ne transforme PAS le délai en refus sans demander.** C'est un choix de comportement qui
appartient au propriétaire du projet : arrêter un calcul de plusieurs heures parce que
l'opérateur s'est absenté, et ne PAS l'arrêter alors qu'il l'a demandé, sont deux mauvaises
surprises différentes. **Signale la question, applique 1, 2, 3 et 4, et laisse le sens du
délai inchangé.**

**Garde-fou :** un test qui appelle `stop_optim()` au repos et assère qu'**aucun dialogue
n'est créé** ; un test qui assère que le bouton STOP est désactivé tant qu'aucun worker ne
tourne.

---

### Étape 2.13 — 🔴 L'annulation : quel module câbler, lequel nettoyer

# ⚠️ CETTE ÉTAPE VISAIT FIELD — C'ÉTAIT LE MAUVAIS MODULE

📏 Mesuré le 2026-09-04 par audit transversal. `self.undo_stack = deque(...)` est créé
**inconditionnellement** pour toute sous-classe de `CertusBaseApp`
(`certus/ui/certus_base_app.py:471`) : les six modules l'ont **par héritage, sans l'avoir
demandé**. `undo_btn` n'existe que dans 2 fichiers, `Ctrl+Z` que dans 2 autres.

| module | remplit le stack ? | le consomme ? | `len` au démarrage | verdict |
|---|---|---|---|---|
| **RE** | non — le seul écrivain atteignable sort à `certus_base_app.py:1741` faute d'`undo_btn` | **oui, et c'est complet** : `front_table` (`certus_re_layout_mixin.py:920`), `_add_front_row` (`certus_re_table_mixin.py:391`), `_get_front_stack` (`:422`) et même le crochet `_trigger_post_undo_action` (`certus_re_state_mixin.py:663`) | 0 | 🟢 **CÂBLER** — la machinerie est là, **une seule garde la neutralise** |
| INDEX | non (0 occurrence de `undo` dans ses fichiers) | non | 0 | **SUPPRIMER l'attribut** |
| **FIELD** | non | non — et FIELD **n'a pas de `front_table`** (sa table est `table_layers`, `certus_field_common.py:235`) | 0 | **SUPPRIMER** |
| METAL SINGLE / BILAYER | non | non | 0 | **SUPPRIMER** |
| INDEX SPLINE | **oui** (`certus_index_spline_eventsextras_mixin.py:438-457`, appelé depuis `certus/spline/certus_index_spline_execution.py:541`) | **non, jamais** | 0 | 🟠 **choix éditorial** : écrire le consommateur, ou retirer l'écrivain. Dans les deux cas **corriger la docstring `:439`, qui promet un `Ctrl+Z` inexistant** |

🔴 **Ce que disait cette étape était faux et dangereux.** J'écrivais *« FIELD a le stack mais
pas le bouton, donc l'annulation est inatteignable »* — sous-entendu : câbler `Ctrl+Z`.
**Câbler `Ctrl+Z` sur FIELD lèverait `AttributeError: front_table` au premier appui.** La
description exacte s'applique à **RE**, pas à FIELD.

⚠️ **Et STRAT, déjà câblé, mérite un regard** : son stack propre fait `maxlen=5`
(`certus_strat_ui.py:125`), il est **déjà saturé au démarrage** (mesuré), il est réécrit à
**chaque édition de cellule** (`certus_strat_ui_events.py:207`) — donc cinq frappes purgent
l'historique — et `_undo_stack_table` (`certus_strat_ui_state.py:300`) ne restaure que la
**colonne du multiplicateur**, pas les matériaux.

---

**Axe** A4 · **Sévérité BLOQUANT** · **Effort** S
**Fichiers** `certus/ui/certus_base_app.py:1741`, `certus/ui/certus_field_common.py:248`

**Pourquoi.** `certus_base_app.py:1741` fait
`if not hasattr(self, "undo_stack") or not hasattr(self, "undo_btn"): return`. FIELD possède
`undo_stack` mais **pas** `undo_btn` : toute la mécanique d'annulation sort immédiatement.
Or l'empilement de FIELD **est réordonnable et effaçable** — et `safe_clear`
(`certus_field_common.py:290-297`) fait `setRowCount(0)` **sans confirmation ni sauvegarde**.

**Ce qu'il faut écrire.** Soit doter FIELD d'un `undo_btn` et câbler `Ctrl+Z`, soit — plus
propre — remplacer la garde par une garde sur la **capacité**, pas sur la présence d'un
bouton :

```python
        # Guarding on the presence of a BUTTON made undo unreachable in FIELD,
        # which has the stack but no button. Guard on the stack itself.
        if not hasattr(self, "undo_stack"):
            return
```

et rendre le bouton facultatif dans le reste de la méthode.

⚠️ **Six modules exposent `undo_stack` sans `Ctrl+Z`.** Avant de câbler quoi que ce soit,
**vérifie pour chacun qu'une méthode d'annulation existe et fait quelque chose** : un
raccourci qui pointe vers rien est pire qu'un raccourci absent. C'est l'objet de la lentille
transversale de l'étape 2.0.

---

### Étape 2.14 — 🔴 SUBSTRATE INDEX est CASSÉ, pas seulement mal noté

**Axe** A8 · **Sévérité BLOQUANT · fonctionnel** · **Effort** S
**Fichier** `certus/ui/certus_substrate_ui.py`

**Pourquoi.** Quatre attributs sont **lus** et **jamais assignés**. 📏 Mesuré le 2026-09-04 :
`grep -c "self\.<nom>\s*="` rend **0** pour les quatre.

```
self.last_run_manifest   lu aux lignes 878, 900, 901, 902, 903, 904, 973   assigne 0 fois
self.current_window      lu aux lignes 1540, 1586                          assigne 0 fois
self.current_poly        lu aux lignes 1540, 1586                          assigne 0 fois
self.current_heavy       lu aux lignes 1540, 1586                          assigne 0 fois
```

Conséquences : **charger un classeur lève `AttributeError`** (`:1540`), et **tout changement
d'état d'occupation aussi** (`:973`, dans `_set_busy`, qui s'exécute au lancement du calcul).

🔑 **C'est le module que ni le harnais ni le garde-fou ne couvraient avant le 2026-09-04.**
Personne ne l'avait ouvert. Il ne fonctionne pas.

**Ce qu'il faut faire.** Les trois `current_*` sont manifestement les paramètres de lissage
lus depuis l'interface, et `last_run_manifest` vit sur le **présenteur**, pas sur la vue.
🔴 **N'invente pas leur source** : remonte à l'appelant et branche-les sur le présenteur, ou
initialise-les explicitement dans `__init__`. Si tu ne trouves pas la valeur juste, **arrête
et signale** — un mauvais paramètre de lissage produit un indice de substrat faux, et
quelqu'un fabriquera une pièce avec.

**Garde-fou.** Un test qui instancie `SubstrateIndexGUI`, appelle le chemin de chargement avec
un classeur d'exemple et exige qu'aucune exception ne remonte. ⚠️ Il doit **échouer**
aujourd'hui.

---

### Étape 2.15 — 🔴 SMOOTHER réécrit le classeur source de l'utilisateur

**Axe** A4 · **Sévérité BLOQUANT · perte de données** · **Effort** S
**Fichier** `certus/utils/certus_curve_smoother.py:370-372`

**Pourquoi.** « Save Clean Data » écrit **dans le fichier d'origine** :

```python
save_path = self.file_path
with pd.ExcelWriter(save_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
    df_clean.to_excel(writer, sheet_name="clean_measurements", index=False)
```

`mode="a"` + `if_sheet_exists="replace"` sur `self.file_path` : la feuille
`clean_measurements` du classeur **de mesures de l'opérateur** est remplacée, **sans
confirmation, sans sauvegarde, sans possibilité d'annuler**. Le message de succès arrive
après.

**Ce qu'il faut faire.** Proposer par défaut un fichier **à côté** (`<nom>_clean.xlsx`) via un
`QFileDialog.getSaveFileName`, et n'écrire dans la source que sur confirmation explicite
nommant le fichier.

⚠️ **Second défaut au même endroit** : `except NUMERICAL_FAULT_EXCEPTIONS` ne couvre pas
`OSError`. Un classeur ouvert dans Excel — le cas le plus fréquent — sort donc en trace
Python au lieu d'un message. Ajoute `OSError` au tuple capturé.

---

### Étape 2.16 — 🔴 Les deux METAL : le bouton « Run » est hors de l'écran

**Axe** A8 · **Sévérité BLOQUANT** · **Effort** M
**Fichiers** `certus/metal/certus_metal_common.py:1145-1153`, `CERTUS_METAL_BILAYER.py:1358`

**Pourquoi.** Deux constats indépendants, tous deux sur le chemin de l'action principale :

1. Le bouton **« ▶ Run » est sous le bas de la fenêtre** au lancement — mesuré **469 px
   en dessous** à 1366×768 sur BILAYER. L'action principale du module n'est pas atteignable
   sans faire défiler un panneau dont rien n'indique qu'il défile.
2. **Les quatre cartes de paramètres ne se peignent pas** au lancement sur BILAYER : 640 px de
   blanc, **13 des 15 champs invisibles**. Sur SINGLE, la carte « Parameters » est
   entièrement vide au premier affichage (`certus/ui/certus_ui_widgets_cards.py:140`).

⚠️ **Traite ces deux modules ensemble** : ils partagent `certus/metal/certus_metal_common.py`,
et les 141 px / 23 px coupés à 1366 (§0bis) ont la même origine.

---

### Étape 2.17 — 🔴 DESIGN : le bouton « Clear / Reset » ne fait RIEN, en silence

**Axe** A4 · **Sévérité BLOQUANT** · **Effort** XS
**Fichier** `certus/ui/certus_design_ui_layout.py:596`

**Pourquoi.** 📏 Reproduit le 2026-09-04, sortie collée :

```
lignes avant : 4
w.clear_btn.click()   (QMessageBox.question force a Yes)
lignes apres : 4
```

**Cause.** `create_reset_button(self, use_app_reset=True)` reçoit `self` = un **`LayoutManager`**
(`certus/ui/certus_design_ui_layout.py:5`), un objet Python ordinaire — **pas la fenêtre**.
`CertusResetManager._confirm_reset` fait alors
`QMessageBox.question(self.app, …)` (`certus/utils/certus_reset_framework.py:161`) avec un
non-`QWidget` en parent → `TypeError`, absorbée par le slot Qt. **Rien n'est journalisé, rien
n'est affiché, la table n'est pas vidée.**

🔑 **C'est la même cause racine que l'étape 2.6** (les quatre raccourcis morts de DESIGN,
`certus_design_ui_events.py:25-28`, `getattr` sur le délégué au lieu de la fenêtre).
**Traite les deux d'un bloc** : partout où un délégué est passé là où un `QWidget` est
attendu, remplacer par `self.ui`.

**Ce qu'il faut écrire.**

```python
# certus/ui/certus_design_ui_layout.py:596
self.ui.clear_btn = create_reset_button(self.ui, use_app_reset=True)
```

Et pour que la classe d'erreur ne revienne pas, lever d'entrée dans `create_reset_button`
(`certus/utils/certus_reset_framework.py:466`) si `app_instance` n'est pas un `QWidget`.

**Garde-fou.** Le test doit **échouer** aujourd'hui :

```python
def test_design_clear_button_actually_clears() -> None:
    """Measured 2026-09-04: the button silently did nothing — its reset manager was
    built on the LayoutManager delegate, so QMessageBox.question raised TypeError
    into a Qt slot, where it was swallowed."""
```

**Risque.** `tests/unit/test_certus_reset_framework.py` existe — lis-le avant de durcir
`create_reset_button`. ⚠️ Il assère `btn.text() == "🔄  Clear / Reset"` : si tu retires
l'emoji (étape 3.5), mets à jour test et code dans le même changement.

---

### Étape 2.18 — 🔑 UNE SEULE ACTION REFERME LA MOITIÉ DES TROUS TRANSVERSAUX

**Axes** A4/A6/A9 · **Effort** S · **C'est le meilleur rapport résultat/effort de tout le plan.**
**Fichiers** `certus/ui/certus_design_ui.py:197`, `certus/ui/certus_strat_ui.py:165`, `CERTUS_RE.py:454`

**Pourquoi.** 📏 Mesuré : **DESIGN, STRAT et RE n'exécutent jamais `_finalize_init`** — et les
trois fichiers **le documentent en commentaire**. Or `CertusBaseApp._finalize_init`
(`certus/ui/certus_base_app.py:500`) installe d'un coup : `Ctrl+K` / `Ctrl+Shift+P` / `F1` /
`Shift+?` (`:522-530`), les raccourcis de zoom (`:535`), **le menu Help** (`:551-557`),
**`_auto_install_empty_states()`** (`:562`), **`_apply_accessibility_defaults()`** (`:565`) et
`setAcceptDrops(True)` (`:569`).

```
module   _finalize_init   palette   menu Help   champs avec accessibleName
DESIGN        non            0        non              0 / 83
STRAT         oui            0        non              0 / 68
RE            non            0        non              0 / 12
INDEX         oui            4        oui             24 / 24
SPLINE        oui            3        oui             98 / 98
FIELD         oui            4        oui             29 / 29
```

**Dans les trois modules les plus utilisés de la suite**, la palette de commandes et l'overlay
des raccourcis sont **inatteignables au clavier**, il n'y a **aucun menu Help**, et **aucun
des 163 champs cumulés ne porte de nom accessible**.

**Ce qu'il faut écrire.** Extraire de `certus_base_app.py:500-530` une méthode
`_install_common_shortcuts()` et l'appeler explicitement depuis les trois points d'entrée qui
court-circuitent `_finalize_init`. Faire de même pour `_auto_install_empty_states()` et
`_apply_accessibility_defaults()`.

**Garde-fou.** `assert shortcut_owner(win, "Ctrl+K") is not None` pour les 9 modules à base
commune, et `accessibleName()` non vide sur au moins 90 % des champs.

---

### Étape 2.19 — 🔴 Le dispositif d'états vides est mort dans les 11 fenêtres

**Axe** A5 · **Effort** M · **Fichiers** `certus/ui/certus_empty_state.py`, `certus/ui/mixins/certus_base_core_mixins.py:663`

**Pourquoi.** 📏 `len(certus_empty_state._OVERLAYS)` vaut **0** dans les onze fenêtres.
La cause est un croisement parfait :

- `_EMPTY_STATE_HINTS` (`:663`) ne connaît que six noms — `front_table`, `back_table`,
  `target_table`, `spectra_table`, `measurement_table`, `results_table` ;
- **les deux seuls modules qui portent ces noms sont DESIGN et RE**, et ce sont
  précisément **les deux qui n'appellent jamais `_finalize_init`** (étape 2.18) ;
- **les modules qui l'appellent n'ont aucune table portant un de ces noms** : INDEX a
  `table_res`/`table_params`, SPLINE `table_nk`/`table_data_th`/`table_corridor`, FIELD
  `table_layers`/`table_field_res`/…, STRAT `_mg_table`.

Conséquence visible : **RE et INDEX affichent chacun deux tables vides, sans un mot.**

🔴 **Et même correctement installé, l'overlay ne suivrait pas le modèle.** Il ne se
resynchronise que sur `QEvent.Type.Resize` (`certus/ui/certus_empty_state.py:284`).
Mesuré dans les deux sens :

```
attache (0 ligne)      -> overlay visible = True
setRowCount(5)         -> overlay visible = True    <- il MASQUE les donnees
redimensionnement      -> overlay visible = False
setRowCount(0)         -> overlay visible = False   <- il devrait revenir
```

**Ce qu'il faut écrire.** Dans `_Watcher.__init__`, se connecter à `model.rowsInserted`,
`model.rowsRemoved` et `model.modelReset`, chacun appelant `self._sync()`. Puis remplacer le
registre par nom d'attribut par un balayage de `_iter_persistable_tables()`
(`certus/ui/certus_base_app.py:616`, déjà écrit), le registre ne servant plus qu'à
**surcharger** le libellé — c'est ce qui empêchera la liste de re-périmer au prochain
renommage.

**Garde-fou.** Le test doit rendre ≥ 2 overlays sur INDEX ; il rend **0** aujourd'hui.

---

### Étape 2.20 — Les raccourcis qui font autre chose que ce qu'ils annoncent

**Axe** A4 · **Effort** S chacun · **Tous mesurés le 2026-09-04**

| # | défaut | preuve | correctif |
|---|---|---|---|
| **a** | 🔴 **`Esc` ne stoppe pas STRAT** : il ferme les fenêtres auxiliaires (`certus/ui/certus_strat_ui_events.py:21`). Dans les 7 autres modules, `Esc` est passé en `stop=`. **C'est le seul module dont un run dure 2 h 39** — et son overlay F1 affiche pourtant, mot pour mot, `Esc → Stop / cancel` | code + overlay | **retirer** la ligne `:21` (sinon `install_unique_shortcut` refusera la séquence) et passer `stop=self.request_stop_optimization` à `:23` ; déplacer `close_all_auxiliary_windows` sur `Ctrl+W`, annoncé partout et installé nulle part |
| **b** | 🔴 **`Ctrl+O` lance une optimisation dans DESIGN** — `run_optim("local")`, `certus/ui/certus_design_ui_events.py:12` — pendant que l'overlay affiche `Ctrl+O → Load configuration`. Un opérateur qui croit ouvrir un fichier **réécrit l'empilement courant** | code + overlay | déplacer l'optimisation locale sur `Ctrl+Shift+G` (le global est déjà sur `Ctrl+G`) et passer `load=` à `install_standard_shortcuts` |
| **c** | 🔴 **Fermer la fenêtre pendant un run tue le calcul sans une question.** `certus/ui/certus_strat_ui_events.py:272-273` fait `event.accept()` dans un `finally:` ; `CertusBaseApp.closeEvent` (`certus/ui/certus_base_app.py:2250`) ne teste jamais si un calcul tourne | code | garde en tête de `closeEvent` : si un worker tourne, `confirm_destructive(...)` puis `event.ignore()`. ⚠️ vérifier que `tests/unit/test_gui_apps_smoke.py` ferme bien avec des workers à l'arrêt |
| **d** | **`Ctrl+E` veut dire « évaluer » dans DESIGN et RE**, « exporter » ailleurs. Dans RE il est posé **avant** `install_standard_shortcuts(..., export=...)` : l'export est donc **abandonné en silence** (`certus/ui/certus_ui_utils.py:458-465`) alors que l'overlay l'annonce | code | trancher une convention unique pour la suite |
| **e** | **3 à 6 raccourcis annoncés et non installés par module.** `CommandAction.shortcut` est **purement décoratif** (`certus/utils/certus_command_palette.py:52`). `Ctrl+W` est annoncé dans les 9 modules à palette et installé dans **zéro**. Sur METAL×2, l'aide promet `Ctrl+S` et `Ctrl+O`, qui n'existent pas | code | dans `collect_window_shortcuts` (`certus/ui/certus_shortcuts_overlay.py:82`), écarter toute entrée dont `shortcut_owner(window, seq)` rend `None`. **Rendre l'aide dérivée du réel, pas d'une déclaration** |
| **f** | **`Ctrl+Plus` / `Ctrl+Minus` ne se résolvent à AUCUNE séquence en Qt6** (`QKeySequence("Ctrl+Plus").toString() == ""`) et sont pourtant affichés dans l'aide de tous les modules (`certus/ui/mixins/certus_base_core_mixins.py:205` et `:216`). Les vraies touches sont `Ctrl++` et `Ctrl+-` | code | corriger les libellés |

🔴 **Et le dialogue d'arrêt est à l'envers.** `confirm_stop_with_timeout`
(`certus/ui/certus_ui_utils.py:1060`) a **« Stop Now » pour bouton par défaut** (`:1091`) *et*
**clique tout seul sur Stop au bout de 10 s** (`:1102`). Ce n'est pas une confirmation
d'arrêt : c'est une fenêtre de 10 secondes pour **annuler l'arrêt**. Sur un run de 2 h 39, un
opérateur qui s'éloigne perd le run. ⚠️ Le corriger change le comportement de **RE, DESIGN,
INDEX, STRAT et METAL en même temps** — c'est voulu, mais annonce-le.

---

### Étape 2.21 — Les garde-fous d'ergonomie qui existent et que personne n'appelle

**Axe** A4/A5 · **Effort** M

🔑 **`confirm_destructive` (`certus/ui/mixins/certus_base_core_mixins.py:769`) et
`confirm_and_stop` (`certus/ui/certus_ui_utils.py:1204`) n'ont AUCUN appelant en production.**
Seules références : des tests. C'est le motif `fast_auto_blocks` / `strategy_phase_timeout` du
`CLAUDE.md` §24-50, transposé à l'ergonomie — *la facilité existe, on l'a testée, personne ne
s'en sert.*

📏 Balayage AST des méthodes destructrices qui mutent réellement quelque chose, sur
`certus/ui`, `certus/metal`, `certus/spline`, `certus/utils` et les points d'entrée :
**24 méthodes, 0 confirmation.** La seule action correctement gardée de toute la suite est le
bouton « Clear / Reset » partagé — **et il est inopérant dans DESIGN** (étape 2.17).

Trois cas à traiter en priorité, tous sans confirmation ni annulation possible :

- **RE — coller depuis Excel vide toute la table** si aucune ligne n'est sélectionnée
  (`certus/ui/certus_re_table_mixin.py:797`), et le stack d'annulation de RE n'est jamais
  rempli (étape 2.13) ;
- **RE — fusionner les couches adjacentes** (`certus/ui/certus_re_table_mixin.py:268`) ;
- **FIELD — `safe_clear`** (`certus/ui/certus_field_common.py:290`).

---

### Étape 2.22 — Un `except` sur deux est muet, et deux d'entre eux fabriquent de la physique

**Axe** A5 · **Sévérité MAJEUR** · **Effort** L

📏 Analyse AST de 112 fichiers de `certus/ui/` :

```
gestionnaires except            : 595
  l'utilisateur le voit         :  74   (12 %)
  journal seulement             : 212   (36 %)
  MUETS                         : 298   (50 %)   dont 125 « pass » nus
```

🔴 **Les deux plus graves ne se contentent pas de taire une erreur : ils inventent une
donnée physique.**

| | |
|---|---|
| `certus/ui/certus_field_state_mixin.py:995` | `except Exception: layer_types = [i % 2 for i in range(len(emp_factors))]` — **fabrique un empilement H/L alternant** quand la lecture des types échoue |
| `certus/ui/certus_field_state_mixin.py:1015` | `except Exception: dmin = 0.0 ; ep_physical = np.array([])` — épaisseur minimale rapportée à 0 nm sans le dire |

🔑 **C'est l'interdit n° 9 du `CLAUDE.md` réalisé dans l'interface** : *une erreur silencieuse
ne plante pas, elle produit un résultat faux qui a l'air juste.* **Traite ces deux-là en
premier, avant les 296 autres.**

⚠️ Trois autres sont sur le chemin critique.

`certus/ui/certus_worker_manager.py:44` et `:49` — l'arrêt des workers échoue en silence sous
un `except Exception: pass`. C'est le chemin qu'empruntent l'`Esc` de FIELD et la fermeture de
toutes les fenêtres : si l'arrêt échoue, l'interface se réactive comme si tout allait bien.

`certus/ui/certus_strat_ui_worker.py:677` et `:685` — deux `pass` nus qui avalent la mise à
jour du panneau de progression, Phase A puis Phase B. C'est le **seul** retour visuel d'un run
de 2 h 39 : une exception et il se fige, rendant un calcul planté indiscernable d'un affichage
gelé.

---

### Étape 2.23 — Aucune fenêtre n'a de bouton par défaut, et le focus part sur « Help »

**Axe** A6 · **Effort** S

📏 Mesuré sur les 11 fenêtres **affichées** (sans `WA_DontShowOnScreen`, qui rend
`focusWidget()` inutilisable) :

```
premier widget focalise a l'ouverture : QToolButton "Help"  ->  11 fenetres sur 11
bouton par defaut (setDefault)        : aucun               ->  11 sur 11
autoDefault                           : 0 partout
```

**Entrée ne valide rien, nulle part**, et à l'ouverture `Espace` déclenche l'aide. La chaîne
de tabulation commence systématiquement par l'aide, le basculeur de thème et la barre
d'outils avant d'atteindre le premier champ métier.

**Correctif** : `setDefault(True)` sur l'action principale de chaque fenêtre,
`setFocusPolicy(Qt.FocusPolicy.NoFocus)` sur le bouton d'aide et le basculeur de thème de
`create_header_logo_widget`, et un `setFocus()` explicite sur le premier champ métier.

---

## PHASE 3 — LE SYSTÈME VISUEL

C'est la phase qui fait passer de « propre » à « premier centile ». Elle est **entièrement
mécanisable et entièrement verrouillable** par les tests statiques de l'étape 1.3.

---

### Étape 3.0 — 🔑 UNE SEULE CAUSE RACINE EXPLIQUE UNE DIZAINE DE DÉFAUTS VISIBLES

**Axes** A3/A7 · **Effort** M · **Fais-la en premier : elle éteint plusieurs symptômes d'un coup.**

**Le constat.** Une passe a **effacé les caractères non-ASCII** des chaînes visibles du code,
sans les remplacer. Elle a laissé trois signatures, toutes mesurées le 2026-09-04 :

| signature | compte | exemples |
|---|---|---|
| **double espace interne** là où un séparateur a été retiré | **30 chaînes, 11 fichiers** | `'1␣␣Materials'` · `'2-4␣␣Parameters'` · `'CERTUS␣␣Index Spline Optimization'` · `'Optical Profiles␣␣n(lambda) and ln k(lambda)'` · `'Smart Init␣␣PWL n and k (…)'` |
| **`lambda` écrit en toutes lettres** au lieu de `λ` | **38 chaînes, 13 fichiers** | `"lambda (nm)"` · `"n(lambda)"` · `"Min. Deltalambda/lambda step (sigma mesh) :"` — c'est `Δλ/λ` désarticulé |
| **caractère remplacé par `?`** | plusieurs | `certus_index_spline_managers_ui.py:265` — `addItem("Heuristic (alpha?RMSE_opt)", "alpha")` : le `?` occupe la place d'un opérateur |
| **ternaire dégénéré** dont les deux branches sont devenues vides | 1, mais visible dans les **11 fenêtres** | `certus_ui_widgets_utils.py:179` — le basculeur de thème est un cercle vide (traité en 2.5) |

### 🔴 ATTENTION — UNE PARTIE DES DOUBLES ESPACES A UNE AUTRE CAUSE, ET UN AUTRE CORRECTIF

⚠️ **Ne traite pas les 30 chaînes de la même façon. Certaines ne sont pas mutilées du tout :
c'est Qt qui mange leur esperluette.** Dans un `QPushButton`, un `QCheckBox`, un
`QRadioButton` ou un `QLabel` doté d'un *buddy*, `&` est le préfixe **mnémonique** : il
disparaît du rendu et crée un raccourci sur le caractère suivant.

📏 **Mesuré le 2026-09-04** sur la chaîne `"Substrate (n) & layer thickness"` :

```
QCheckBox.shortcut()   -> Alt+Space
QPushButton.shortcut() -> Alt+Space
```

Le caractère qui suit le `&` étant une **espace**, Qt fabrique un raccourci `Alt+Space` —
qui est le raccourci système Windows du menu de fenêtre — et retire le `&` de l'affichage.
D'où « Substrate (n)␣␣layer thickness » à l'écran alors que `grep` trouve bien le `&` dans
la source.

🔑 **Comment distinguer les deux cas, mécaniquement** : si la source porte un `&` à
l'emplacement du trou, c'est un mnémonique ; sinon, c'est un séparateur effacé.

**Deux correctifs différents :**

| cas | correctif |
|---|---|
| `&` mangé par Qt | **doubler l'esperluette** : `"Substrate (n) && layer thickness"`. Ou remplacer par « et » / « · » si l'esperluette n'apporte rien |
| séparateur effacé | rétablir le séparateur choisi à l'étape 3.0 (`·` ou `—`) |

**Garde-fou supplémentaire :**

```python
def test_no_label_creates_an_accidental_mnemonic() -> None:
    """A lone '&' in a button or checkbox caption is swallowed by Qt and registers
    a shortcut on the next character. Measured 2026-09-04: "Substrate (n) & layer
    thickness" registered Alt+Space, which is the Windows window-menu shortcut."""
    for w in every_button_and_checkbox():
        assert not w.shortcut().toString().endswith("Space"), w.text()
```

🔑 **Ce n'est pas une question de goût.** **27 fichiers du dépôt écrivent correctement `λ`** :
FIELD affiche « Center λ » pendant que SPLINE affiche « n(lambda) ». La suite est donc
incohérente **avec elle-même**, et c'est visible en une capture d'écran.

**Ce qu'il faut faire.**

1. Rétablir `λ` dans les 38 chaînes visibles. ⚠️ **Seulement dans les chaînes vues par
   l'utilisateur** — pas dans les noms de variables, pas dans les clés JSON persistées, pas
   dans les `lambda:` du langage Python.
2. Pour les 30 doubles espaces, décider d'un séparateur **unique** pour toute la suite
   (`·` en U+00B7, ou `—` en U+2014) et l'appliquer. Ne te contente pas de supprimer
   l'espace en trop : le séparateur portait une information de structure.
3. Vérifier que les fichiers sont bien lus et écrits en UTF-8 explicite.

**Garde-fou :**

```python
def test_no_user_facing_string_carries_a_stripped_separator() -> None:
    """A double space inside a visible label is the scar of a removed non-ASCII
    separator. Measured 2026-09-04: 30 such strings across 11 files."""
    assert count_double_spaced_labels() == 0

def test_user_facing_strings_use_the_greek_letter_not_its_name() -> None:
    """Measured 2026-09-04: 38 visible strings wrote 'lambda' while 27 files
    already used the Greek letter. The suite contradicted itself on screen."""
    assert count_spelled_out_lambda() == 0
```

**Preuve d'utilité :** **ÉCHEC** — 30 et 38 aujourd'hui.

**Risque de régression.** 🔴 **Le plus élevé de tout le plan, et il faut le prendre au
sérieux.** Des tests assèrent des libellés au caractère près — `tests/unit/test_certus_reset_framework.py:164`
assère `btn.text() == "🔄  Clear / Reset"`, et `tests/unit/test_strat_multigraine_ui.py:195`
assère des sous-chaînes de `resumer()`. **Cherche systématiquement** avant de toucher une
chaîne :

```bash
grep -rn "<la chaine exacte>" tests/
```

⚠️ **C'est le seul endroit du plan où tu es autorisé à modifier un test** — parce que le test
verrouille précisément la chaîne que l'étape corrige. Mets à jour test et code **dans le même
changement**, et dis-le dans ton compte rendu.

⚠️ **N'introduis aucun caractère hors du plan multilingue de base.** Les emoji rendent en
tofu selon la police installée — c'est ce que l'audit a mesuré sur la plateforme offscreen, et
c'est ce qui arrivera sur une machine dépourvue de police à emoji.

---

| étape | objet | mesure de départ |
|---|---|---|
| 3.1 | **Échelle typographique** : ajouter `FONT_SIZE_XS/SM/BASE/LG/XL/DISPLAY` à `CertusTheme` et router les 170 tailles codées en dur | 23 tailles distinctes, px et pt mélangés |
| 3.2 | **Police unique et installée** : une seule famille, une seule taille de base pour les 11 fenêtres ; refuser au démarrage une famille absente. 🔴 **NON FAITE, malgré les apparences** — le harnais annonce `Segoe UI @10 pt` partout parce qu'il **épingle** cette police depuis le correctif 0.1. Remesuré sans épinglage : rien n'a changé. Et les deux tests censés le garder sont inexploitables — l'un dépend de l'ordre d'exécution, l'autre teste la machine. Détail au §0bis | DESIGN et RE demandent « Open Sans », absente ; base 9 pt vs 10 pt — **inchangé au 2026-09-04 soir** |
| 3.3 | **Bordures visibles** : porter `BORDER` à ≥ 3:1 sur `SURFACE` dans les deux modes | 1,35 (clair) et 1,48 (sombre), exigé 3,0 |
| 3.4 | **Palette sombre complète** : donner des variantes sombres aux 8 jetons sémantiques identiques dans les deux modes ; supprimer les jetons morts `DARK_*` | 8 jetons identiques, 6 jetons morts |
| 3.5 | **Iconographie** : remplacer les 36 emoji visibles par le jeu d'icônes déjà présent (`certus/ui/certus_icons.py`) ; donner une icône distincte à METAL SINGLE et METAL BILAYER, qui partagent le même bouclier | 36 occurrences, 15 fichiers, 2 doublons |
| 3.6 | **Indicateur de focus** : ajouter `QPushButton:focus` — il n'en existe **aucune** dans les deux couches QSS | 0 règle |
| 3.7 | **Cases à cocher** : 14 px et état coché par la couleur seule, sans coche | échec WCAG 1.4.1 |
| 3.8 | **Chevron des combos** : `image: none` (`certus_theme.py:655`) efface la flèche sans rien mettre à la place — les sélecteurs ressemblent à des champs de saisie | 6 combos dans DESIGN seul |
| 3.9 | **Couleurs de marque** : ajouter un jeton pour RE, FIELD, SMOOTHER, SUBSTRATE et faire suivre la couleur des tuiles du HUB à `category`, pas à un module voisin | RE peint avec la couleur de STRAT, FIELD avec celle de DESIGN |
| 3.10 | **Les 314 hexadécimaux et 314 `setStyleSheet`** : campagne de réduction, fichier par fichier, cliquet à chaque passe | 314 / 314 |

🔴 **Règle pour toute la phase 3 : une étape = un jeton ou une famille de jetons.** Ne
regroupe pas. Le cliquet de l'étape 1.3 est ton filet.

---

## PHASE 4 — LES DEUX MODULES ORPHELINS

**SMOOTHER** et **SUBSTRATE INDEX** n'ont jamais rien reçu. Ils sont notés 2,2 et non mesuré.

### Ce qui est déjà établi sur SMOOTHER

| constat | preuve |
|---|---|
| **Français dans une interface anglaise** | « Filtering Mode: **Moyen** » et « [ **Niveau**: Moyen ] » sur la capture |
| **Deux boutons « Help » dans la même fenêtre** | le rond de l'en-tête partagé, plus un pilulier **noir** dans la barre d'outils, hors thème |
| **Boutons de 20 px de haut** | `Copy Logs` mesuré à 20 px, sous le plancher de 24 px appliqué partout ailleurs depuis T8 |
| **Barre d'outils de 27 px** | `Reset` `Detach` `CSV` `Export` mesurés 46×27, 55×27, 39×27, 55×27 |
| **5 boutons sans info-bulle sur 5** | `Load Data (.xlsx/.xls)`, `❓ Help`, `View Isolated`, `Save Clean Data`, `Export` |
| **État vide trompeur** | axe « Wavelength (nm) » gradué **de 0 à 1**, axe « Amplitude » de 0 à 1, aucun message |
| **Ne suit pas le modèle de la suite** | ni splitter, ni panneau de contrôle : barre d'outils + graphe + journal |
| **Le journal occupe ~25 % de la fenêtre au repos** | pour afficher une ligne : « UI log bridge attached (INFO+). » |
| **Détail d'implémentation dans un libellé** | « Load Data (**.xlsx/.xls**) » |

`SUBSTRATE INDEX` partage la même coquille (mêmes boutons `Reset`/`Detach`/`CSV`/`Export` à
27 px, même `Copy Logs` à 20 px, 3 boutons et 4 champs sans info-bulle).

**Ordre de travail :** 4.1 les faire entrer dans le harnais et le garde-fou (fait en 0.2) ·
4.2 aligner la langue · 4.3 supprimer le second bouton Help · 4.4 plancher de 24 px ·
4.5 info-bulles · 4.6 états vides · 4.7 aligner sur le modèle de fenêtre de la suite.

---

## PHASE 5 — ERGONOMIE MÉTIER

C'est la phase où une erreur coûte le plus cher : **ne devine jamais la signification
physique d'un paramètre.** Si tu ne la trouves pas dans le code, laisse le champ sans
info-bulle et signale-le. Une info-bulle fausse est bien pire qu'une absente : elle sera crue.

| étape | objet | preuve |
|---|---|---|
| 5.1 | **STRAT affiche le mauvais indicateur de tête.** Le bandeau KPI montre `ROBUSTNESS SCORE` (`certus_strat_ui_layout.py:256`), alors que `CLAUDE.md` §22 pose le **SEEL** comme « la seule grandeur à rapporter — jamais le RMSE brut ». Le SEEL est calculé dans `APP_CONTEXT["seel_data"]` à l'étape 0 de l'interface | code + `CLAUDE.md` §22 |
| 5.2 | **Identifiants techniques exposés.** `CertusCard("substrate_Base Wavelength")` (`certus_strat_ui_layout.py:367`) · en-têtes `lambdamin` / `lambdamax` sans unité (`certus_base_app.py:2045`) · `n(lambda)` en titre d'onglet DESIGN alors que FIELD écrit « Center λ » | captures + code |
| 5.3 | **Booléens en champs texte libres.** « Slit bias (0/1) », « Search the slit (0/1) », « Allow Rate mode (0/1) », « Enable SYM (0/1) »… — sept clés (`certus_strat_ui_layout.py:979-987`, `:1115-1122`) | code |
| 5.4 | **59 champs numériques sur 59 sans validateur**, dont deux livrés vides (`thickness_tolerance_nm`, `mse_tolerance_limit_pct`) | sonde Qt |
| 5.5 | **Précisions numériques incohérentes** dans une même vue DESIGN : RMSE 6 décimales, épaisseur 1, indice 3, QWOT 5, poids 1 | capture |
| 5.6 | **La vue scientifique principale de STRAT est un `QLabel`** avec `setScaledContents(True)` (`certus_strat_ui_layout.py:228-234`) : image matricielle **étirée**, ni zoom, ni curseur, ni lecture de valeur | code |
| 5.7 | **Info-bulles manquantes** : INDEX 8 champs, SPLINE 4 champs + 4 boutons, SMOOTHER 3 + 5, SUBSTRATE 4 + 3 | harnais |
| 5.8 | **Onglet Multi-realisation entièrement en français non accentué** avec un décompte grammaticalement faux (`certus_strat_multigraine_ui.py:398`, `:574`) | capture + code |
| 5.9 | 🔴 **Tous les en-têtes de table sont forcés en MAJUSCULES, et en optique la casse est une grandeur.** `certus/utils/certus_ux.py:524` — `text-transform: uppercase;` sur `QHeaderView::section`, pour toute la suite. Conséquence : la colonne `n` s'affiche **`N`**, or `CLAUDE.md` §16 pose `n̂ = n − ik` — **`N` désigne l'indice COMPLEXE**, pas l'indice réel. Idem `k`→`K`, `T`→`T`/`t`, `R`→`r`. Une colonne devient ambiguë avec une autre grandeur physique. Et le rendu tronque : `"_AMBDA (NM"` au lieu de `λ (nm)` | code + capture SPLINE `tab0_05_Data` |

⚠️ **5.9 est le seul point de la phase 5 qui touche une règle gravée du projet.** Le correctif
est d'une ligne — retirer `text-transform: uppercase` — mais il **change l'apparence de toutes
les tables des 11 fenêtres d'un coup**. Fais-le seul, et remets à jour la référence du
squelette (étape 1.2) dans le même changement.

⚠️ **5.6 est la plus lourde et la plus payante.** Pour un logiciel de métrologie, un graphe
sans curseur de lecture ni zoom n'est pas un graphe. Traite-la en deux paliers : d'abord
`setScaledContents(False)` (une ligne, supprime la déformation), ensuite le passage à
pyqtgraph.

---

## PHASE 6 — FINITION

| étape | objet | preuve |
|---|---|---|
| 6.1 | **HUB : grille figée à 3 colonnes pour 10 modules.** `CERTUS_HUB.py:360` — `MAX_COLS = 3  # 3x3 Grid (9 modules)` : **le commentaire dit 9, le catalogue en compte 10.** D'où la dixième tuile orpheline et ~60 % de la fenêtre vide à 1920 | code + capture |
| 6.2 | **HUB : le préfixe technique `[n]` fuit dans les libellés, et le 10ᵉ module n'a ni numéro ni raccourci.** `CERTUS_HUB.py:376` — `card_title = f"[{idx + 1}] {title}" if idx < 9 else title` | code + capture |
| 6.3 | 🔑 **HUB : le catalogue porte `sub`, `badge` et `category` pour chaque module, et RIEN n'est rendu.** `ModuleBadge` est **défini** (`certus_hub_widgets.py:6`) et **importé** (`CERTUS_HUB.py:185`) — et **jamais instancié** : deux occurrences dans tout le dépôt. `badge_text` est un paramètre d'`ApplicationCard` (`:60`), transmis (`:151`), jamais affiché. ⚠️ *Une rédaction antérieure de cette ligne dénonçait une « taxonomie de badges incohérente ». C'est hors sujet : les badges ne sont pas affichés du tout. Le vrai défaut est que la moitié des métadonnées du catalogue n'atteint jamais l'écran.* | code |
| 6.3bis | 🔴 **HUB : les dix lanceurs ne sont pas des boutons.** `certus_hub_widgets.py:43` — `class BaseApplicationCard(QFrame)`, et ni `setFocusPolicy`, ni `keyPressEvent`, ni `setAccessibleName` n'apparaissent dans le fichier : **aucun focus clavier, aucune activation par Entrée, aucun nom pour un lecteur d'écran.** Et `CERTUS_HUB.py:390` remplace `mousePressEvent` par un lambda qui **ignore `e`** : n'importe quel bouton de souris lance le module, **à l'appui** et non au relâchement | code |
| 6.3ter | 🔴 **HUB : deux commandes ne font rien de visible.** « Scientific Documentation » (`CERTUS_HUB.py:409`) rend **blanc sur blanc** — seul l'arc du bord supérieur subsiste. « Show Details » ne peut **jamais** afficher les journaux : le `CertusLogPanel` est construit `visible=False` (`:499`) et le bouton bascule autre chose (`:794`). **Sévérité bloquante : ce sont deux promesses non tenues sur la fenêtre d'accueil.** | code + capture |
| 6.3quater | **HUB : la bande des fichiers récents est inerte.** `CERTUS_HUB.py:959-962` — `_on_recent_config_selected` ne fait qu'un `_log_message(...)`, dans un panneau lui-même inatteignable (6.3ter). Cliquer un fichier récent n'ouvre rien | code |
| 6.3quinquies | **HUB : le sélecteur de police propose « Open Sans », absente du poste**, sans validation ni chevron (`CERTUS_HUB.py:301-302`). C'est la source du défaut §4.2 sur DESIGN et RE | code + mesure |
| 6.4 | **DESIGN : quatre toasts empilés dont deux identiques**, recouvrant le bouton « Remove » de la table des cibles | capture |
| 6.5 | **Les toasts se posent par-dessus la barre d'état**, donc par-dessus l'indicateur de progression (`certus_toast_stack.py:314`) | code + sonde |
| 6.6 | **Onglets Synthèse vides.** DESIGN : 800 px de blanc sous cinq chiffres. STRAT : 71 % de la fenêtre pour « Welcome to CERTUS », alors qu'un guide d'accueil de 356 lignes existe et **n'est jamais instancié** | captures + code |
| 6.7 | **En-têtes de table tronqués** : `THICK(NM`, `/AF`, `DEL` — colonnes de `front_table` en `Fixed` à 55/70/80/40/40 px, `certus/ui/certus_design_ui_layout.py:797-800`. ⚠️ *Ce renvoi disait `:837` ; le fichier étant revenu à `HEAD` le 2026-09-04, le code a reculé de 40 lignes. **Cite la fonction, pas le numéro** — c'est `_build_front_table_widget`* | capture + code |
| 6.8 | **Doubles espaces dans les libellés** de SPLINE : « Substrate (n)␣␣layer thickness », « Mesh␣␣optimizer », « Corridors␣␣RMSE(d) » — un séparateur a été retiré et a laissé un trou | capture |
| 6.9 | **Cartes à hauteur fixe qui coupent leur dernière rangée** : FIELD (« Detach Stack » coupé en deux), SPLINE (première rangée de la carte « 2 Substrate… ») | captures |
| 6.10 | **Styles de table incohérents** : lignes alternées sur DESIGN, RE et FIELD ; absentes sur STRAT, INDEX et SPLINE | harnais |
| 6.11 | **Le splitter vertical de DESIGN n'est pas persisté** : variable locale jamais affectée à `self.ui` (`certus_design_ui_layout.py:625`) | code |
| 6.12 | **Six boutons primaires dans la même pile d'actions** DESIGN : aucune action n'est mise en avant | code |
| 6.13 | **`0 setBuddy` dans tout `certus/ui/`** : un lecteur d'écran annonce des champs anonymes | grep |

---

## 7. VÉRIFICATION FINALE

```bash
python -m ruff check .
```
**Attendu** : `All checks passed!`

```bash
python -m pytest tests/ui/ tests/unit/test_gui_apps_smoke.py tests/unit/test_gui_apps_reset_lifecycle.py tests/unit/test_crash_watchdog.py tests/unit/test_example_json_integrity.py tests/unit/test_export_utf8_encoding_guardrail.py -q --no-cov
```
**Attendu** : `0 failed`. **Le nombre de tests n'est pas un critère.**

```bash
python scripts/audit_ux_certus.py
python scripts/audit_ux_certus.py --width 1366 --height 768
```

### Objectif final

⚠️ **La colonne « départ » est celle du MATIN du 2026-09-04.** Ce qui a bougé depuis est au
§0bis ; ne recopie pas ces chiffres comme s'ils décrivaient l'état courant.

| critère | départ 2026-09-04 matin | cible |
|---|---|---|
| **modules qui lèvent une exception à l'usage** | **1** (SUBSTRATE INDEX) | **0** |
| **modules qui écrasent un fichier utilisateur sans confirmation** | **1** (SMOOTHER) | **0** |
| **modules dont l'action principale est hors écran** | **2** (les METAL) | **0** |
| fenêtres auditées en détail | 0 / 11 | **11 / 11** ✅ *fait* |
| panneaux cachant du contenu derrière une barre horizontale | 2 (340 px, 444 px) | **0** |
| modules sous 65 % de zone graphique à **1920** | 0 / 8 | **0** |
| modules sous 65 % de zone graphique à **1366** | **6 / 8** | **0** |
| paires WCAG en échec, mode clair | 1 | **0** |
| paires WCAG en échec, mode sombre | 2 | **0** |
| jetons sémantiques identiques en clair et en sombre | 8 | **0** |
| modules demandant une police absente | 2 | **0** |
| tailles de police distinctes codées en dur | 23 | **≤ 6** (l'échelle) |
| couleurs hexadécimales hors du thème | 314 | **≤ 50** |
| emoji dans des libellés utilisateur | 36 | **0** |
| règles `QPushButton:focus` | 0 | **≥ 1** |
| boutons de moins de 24 px de haut | 2 | **0** |
| champs sans info-bulle | 19 | **0** |
| tables d'empilement triables | 1 (DESIGN `target_table`) | **0** |
| raccourcis morts | 4 (DESIGN) | **0** |
| note moyenne, chaque fenêtre | 2,2 à 3,6 | **≥ 8 sur les 9 axes** |

---

## 8. CE QUE TU DOIS RENDRE

Pour **chaque** étape exécutée :

1. **Fait / partiellement fait / pas fait.**
2. Les fichiers modifiés.
3. **La sortie collée** de la preuve d'utilité du garde-fou (il devait ÉCHOUER avant).
4. **La sortie collée** de la vérification après correctif.
5. **La sortie collée** de la non-régression du §6.1.
6. Ce qui t'a bloqué, s'il y a lieu.

🔴 **Rappels, une dernière fois :**

- **Aucun `git commit`** — le hook publie sur un dépôt public.
- Une étape non faite mais **déclarée non faite** n'est pas une faute. Un contournement
  silencieux en est une.
- **Un garde-fou qui ne casse pas sur le code d'avant ne prouve rien.** C'est le point 3 du
  §6, et c'est la seule chose qui sépare ce plan d'une liste de vœux.
- Si une mesure ne correspond pas à ce document, **dis-le** plutôt que d'ajuster ton
  résultat.

---

## Annexe A — l'instrumentation d'audit

Trois scripts ont servi à établir les chiffres de ce document. Ils vivent **hors du dépôt**
(`%TEMP%\certus_ux\`) parce que ce sont des instruments, pas des livrables. Leur principe :

| script | ce qu'il fait |
|---|---|
| `measure_ux.py` | mesure les 11 fenêtres sous une plateforme au choix ; ajoute au harnais la police effective, le `sizeHint` du panneau, les 14 widgets les plus larges, le détail table par table |
| `shot_ux.py` | capture la fenêtre, le panneau seul et chaque onglet, avec de **vraies polices**, sans jamais afficher de fenêtre (`WA_DontShowOnScreen`) |
| `probe_hscroll.py` | interroge Qt sur la visibilité de la barre horizontale et l'écart contenu/viewport |

Les trois partagent le même contrat d'isolation que `scripts/audit_ux_certus.py` :
**un processus par application** et **`QSettings` redirigés vers un INI jetable**.

🔑 **Le geste qui rend tout cela possible sans déranger l'opérateur :**

```python
win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
win.resize(width, height)
win.show()      # la fenetre se dispose et se rend, sans jamais s'afficher
```

C'est ce qui permet de mesurer avec de vraies polices **et** de rester headless. Reprends-le
dans `scripts/audit_ux_certus.py` si tu préfères la plateforme réelle à l'option
`QT_QPA_FONTDIR` de l'étape 0.1 — les deux donnent le même résultat à 2 px près.

---

## Annexe B — les 70 captures de référence

70 images en 1920×1080, avec de vraies polices, dans `%TEMP%\certus_ux\real_1920\` :
`<MODULE>__1920x1080__00_window.png`, `__01_panel.png`, `__tab<n>_<i>_<titre>.png`.

⚠️ **Un second jeu existe dans `shots_1920/` et `shots_1366/` : il a été pris en `offscreen`
nu, donc tout le texte y est en boîtes tofu.** Il ne sert qu'à la géométrie. **Ne juge aucune
typographie dessus.**
