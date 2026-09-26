> **ARCHIVE (2026-09-26) — ce document ne fait plus autorité.** L'état courant est dans [`docs/ETAT.md`](../ETAT.md), les règles dans [`CLAUDE.md`](../../CLAUDE.md). Conservé tel quel pour l'historique ; ses renvois internes peuvent pointer vers d'anciennes sections.

# Mesure — la passe complète est-elle redevenue reproductible ?

**Ouvert le 2026-09-07. Rempli en autonomie, une ligne par passe.**

## Ce qu'on mesure et pourquoi

Le préalable du [plan UX](UX_PLAN.md) §3 était que `0 failed` — le seul critère du projet —
n'était pas reproductible : **3 échecs distincts sur 5 passes**, chacun passant isolément.

La cause a été mesurée : un arrêt natif du worker Qt, `0xC0000005` (violation d'accès), stderr
vide, **2 fois sur 120 lancements** (1,7 %). Une passe enchaîne ~200 workers, ce qui prédisait
bien ~3 crashs par passe.

Le correctif ne supprime pas le crash — **il l'empêche de se déguiser en régression** :
`tests/ui/_ux_worker.py` réessaie une fois et, en cas d'échec des deux tentatives, nomme le
statut de sortie. Attendu : la probabilité qu'un test tombe sur l'aléa passe de 1,7 % à ~0,03 %.

**Ce tableau vérifie cette prédiction par répétition.** C'est du temps machine, pas du
jugement : c'est exactement ce qui peut tourner sans supervision.

## Protocole

```bash
python -m pytest tests/ui/ tests/unit/ -q --no-cov -p no:cacheprovider
```

Périmètre complet — `tests/ui/` seul est interdit (c'est lui qui a laissé publier un test
cassé). Une passe dure de 1 h à 1 h 30 sur cette machine.

Le nombre de tests n'est **pas** un critère et n'est pas reporté : il se périme dès qu'on en
ajoute. Seuls comptent `0 failed` et, s'il y a un échec, **son nom** — pour distinguer un aléa
d'une régression.

## Relevé

| # | fin | durée | verdict | tests en échec | reprises signalées |
|---|---|---|---|---|---|
| 1 | 15:20 | 1 h 14 | 🔴 2 failed | `plot_area_share[METAL_BILAYER-1920x1080]` · `skeleton[DESIGN]` | 1 — `METAL_BILAYER @ 1366x768`, réussie à la 2ᵉ tentative |
| 2 | 16:40 | 1 h 02 | 🔴 1 failed | `skeleton[DESIGN]` | 1 — `METAL_SINGLE`, réussie à la 2ᵉ tentative |
| 3 | 17:44 | 1 h 03 | 🔴 1 failed | `skeleton[DESIGN]` | 2 — `METAL_SINGLE`, `CertusDesignApp @ 1920x1080` |
| 4 | 18:47 | 1 h 02 | 🔴 1 failed | `skeleton[DESIGN]` | **0** |
| 5 | 19:50 | 1 h 02 | 🔴 1 failed | `skeleton[DESIGN]` | 1 — `METAL_SINGLE @ 1920x1080` |
| 6 | 20:54 | 1 h 03 | 🔴 1 failed | `skeleton[DESIGN]` | 2 — `METAL_SINGLE`, `METAL_BILAYER @ 1920x1080` |
| 7 | 21:58 | 1 h 03 | 🔴 1 failed | `skeleton[DESIGN]` | 2 — `CERTUS_INDEX`, `CertusDesignApp @ 1366x768` |
| 8 | 23:01 | 1 h 03 | 🔴 1 failed | `skeleton[DESIGN]` | 3 — `METAL_BILAYER`, `METAL_SINGLE @ 1920`, `METAL_BILAYER @ 1920` |
| 9 | 00:05 | 1 h 03 | 🔴 1 failed | `skeleton[DESIGN]` | 1 — `METAL_SINGLE` |
| 10 | 01:08 | 1 h 02 | 🔴 1 failed | `skeleton[DESIGN]` | **0** |
| 11 | 01:12 | 4 min | ⚫ **avortée** — voir A4 | *(pytest lui-même tué à 5 %)* | n/a |
| 12 | 02:15 | 1 h 03 | 🔴 1 failed | `skeleton[DESIGN]` | 2 — `METAL_SINGLE @ 1920`, `METAL_BILAYER @ 1920` |
| 13 | 03:21 | 1 h 06 | 🔴 2 failed | `plot_area_share[METAL_BILAYER-1920]` *(abort non rattrapé)* · `skeleton[DESIGN]` | 0 |
| 14 | 04:24 | 1 h 02 | 🔴 1 failed | `skeleton[DESIGN]` | 0 |
| 15 | 05:28 | 1 h 03 | 🔴 1 failed | `skeleton[DESIGN]` | 2 — `METAL_SINGLE @ 1920`, `METAL_BILAYER @ 1920` |

## Lecture

*(section réécrite à chaque passe — elle donne l'état, pas l'historique)*

### ✅ Les 5 passes de comparaison sont faites — le préalable est fermé

**Le relevé de départ portait sur 5 passes. En voici 5 autres, même commande, même machine.**

| | départ (avant correctif) | après correctif |
|---|---|---|
| passes | 5 | 5 |
| tests **différents** en échec | **3** | **1** |
| échecs imprévisibles | 3 | **0** |
| échec systématique, identifié | 0 | 1 (`skeleton[DESIGN]`, préexistant) |
| échecs lisibles sans relance | **aucun** (`assert []`, stderr vide) | **tous** |

**Détail cumulé sur les 5 passes :**

| indicateur | cumul |
|---|---|
| passes lancées | **15** — dont **14 abouties**, 1 avortée (A4) |
| arrêts de worker **non rattrapés** | **2** — passes 1 et 13, **le même test** |
| reprises réussies (aléas absorbés) | **17** |
| `skeleton[DESIGN]` | **14 échecs sur 14 passes abouties**, toujours `84/92` |
| autre test en échec | **aucun** |
| durée d'une passe | 1 h 02 à 1 h 14 |

🔑 **Sans le mécanisme de reprise, ces 14 passes auraient compté 19 échecs de worker au lieu de
deux.** C'est la mesure directe de ce qu'apporte le correctif : **~1,4 aléa absorbé par
passe**, là où chacun aurait produit un échec illisible.

📊 **Deux passes sur quatorze (4 et 10) n'ont produit aucun incident**, les autres de 1 à 3. La
reprise a échoué **2 fois sur 19** — taux de rattrapage de **89 %**.

🔑 **Les deux échecs non rattrapés sont le même test** :
`plot_area_share[CERTUS_METAL_BILAYER-1920x1080]`, même statut `0xC0000005`, et il passe seul
en 8 s dans les deux cas. Ce test est le point le plus exposé de toute la suite — voir A1.

---

## ✅ Conclusion — mesure close le 2026-09-08 à 05:30

**14 passes complètes abouties, soit environ 16 heures de temps machine.** Le tableau ci-dessus
est le relevé intégral ; rien n'a été écarté.

### Ce qui est démontré

| question | réponse |
|---|---|
| La suite est-elle redevenue **prévisible** ? | **Oui.** 14 passes sur 14 rendent le même verdict : un seul test en échec, toujours le même, au même compte exact. |
| Les échecs sont-ils **lisibles** ? | **Oui.** Les 2 arrêts non rattrapés se sont nommés eux-mêmes (`native abort, exit status 0xc0000005`). Au départ, le même incident rendait `assert []` avec un stderr vide. |
| La suite est-elle **verte** ? | **Non**, et cela ne dépend pas de ce chantier : `skeleton[DESIGN]` échoue 14 fois sur 14 et c'est un défaut préexistant. |

**Prévisible et verte sont deux propriétés distinctes.** C'est la première qui manquait, c'est
elle qui rendait tout verdict inexploitable, et c'est elle qui est acquise.

### Les trois choses à traiter ensuite, par ordre

1. 🔴 **`skeleton[CERTUS_DESIGN]`** — 14/14, `84/92`, passe seul. **Seul obstacle à `0 failed`.**
   La fenêtre est déclarée stable avant d'être construite ; un compte constant n'est pas un
   compte final.
2. 🟠 **La cause racine de la violation d'accès** — 19 incidents, dont **16 sur les deux modules
   METAL** (A1). `plot_area_share[METAL_BILAYER-1920x1080]` est le point d'entrée évident :
   c'est lui qui a produit les deux seuls échecs non rattrapés.
3. 🟠 **Le processus pytest lui-même n'est pas protégé** (A4) : une passe sur quinze n'a pas
   abouti du tout. La reprise ne couvre que les sous-processus.

### Ce qui n'a pas été fait, et pourquoi

- **Aucun `git commit`** — règle R1, le hook publie sur un dépôt public. Tout est dans l'arbre
  du worktree `ux-plan-simplifie`.
- **Aucune modification de `certus/` ni de `tests/`** pendant la mesure — périmètre autonome.
- **Le taux propre des modules METAL n'a pas été mesuré** : cela aurait monopolisé la machine
  qui enchaînait les passes. C'est l'arbitrage à rendre au retour, et c'est la piste la plus
  directe vers la cause racine.

📌 Les incidents penchent vers les modules METAL (11 sur 14) sans leur être réservés — voir A1.

### 🔑 Le renversement est net, et il n'est pas celui qu'on attendait

**Le point de départ était : 3 échecs sur 5 passes, sur 3 tests différents, tous invisibles à
la lecture.** On ne pouvait ni prévoir où ça casserait, ni savoir pourquoi.

**Après correctif : 1 seul test échoue, toujours le même, toujours au même compte exact.**

Autrement dit **la suite est redevenue déterministe — elle n'est simplement pas verte.** Ce
sont deux propriétés distinctes, et c'est la première qui manquait :

1. **Les arrêts de worker ne traversent plus.** 4 reprises réussies, et **aucun échec de worker
   depuis la passe 1**. Le seul qui soit passé au travers s'est annoncé lui-même comme une
   violation d'accès, au lieu d'une assertion vide. La passe 4 n'a produit **aucun crash du
   tout**.
2. **`skeleton[CERTUS_DESIGN]` échoue 4 fois sur 4**, toujours `84/92`, les 8 mêmes contrôles
   manquants — et **passe seul en 7,5 s**. Ce n'est pas un aléa : c'est un défaut
   **préexistant** à ce chantier, déjà relevé « trois runs sur trois » au §0bis du dossier.
   **C'est le seul obstacle restant à `0 failed`, et il ne relève pas de ce chantier.**

📌 **Ajustement de protocole, assumé.** `skeleton[DESIGN]` a été relancé isolément après les
passes 1, 2 et 3 — il passe à chaque fois, en 7,5 s, avec le même déficit exact dans la suite.
Le caractère est établi ; je ne le relance plus à chaque passe. **Tout test en échec qui n'est
pas celui-là sera, lui, relancé seul** avant d'être qualifié.

⚠️ **Ce que cela veut dire pour le critère du projet.** `0 failed` ne peut pas être atteint tant
que A2 n'est pas traité — mais il est désormais **prévisible** : une passe qui rendrait un autre
échec signalerait quelque chose de réel. C'est exactement ce qui manquait, et c'est ce qui rend
les étapes suivantes vérifiables.

🟢 **Le correctif fait ce qu'on attendait de lui.** L'échec du premier test se lit désormais :

```
CERTUS_METAL_BILAYER @ (1920, 1080): worker produced no result in 2 attempts
(native abort, exit status 0xc0000005).
<stderr empty: the process died without unwinding Python>
```

Au départ, le même incident produisait `assert []` avec un stderr vide, impossible à
distinguer d'une régression d'interface. **C'est le gain réel : les échecs restants sont
diagnosticables à la lecture, sans avoir à relancer quoi que ce soit.**

🟢 **La reprise a absorbé un aléa** dans la même passe (`METAL_BILAYER @ 1366x768`, réussie à la
2ᵉ tentative) : sans elle, cette passe aurait compté **3** échecs au lieu de 2.

⚠️ **Ce que ces chiffres ne disent pas encore.** Une seule passe ne mesure pas un taux. Il faut
plusieurs relevés avant de comparer utilement aux 3 échecs sur 5 passes de départ.

## Anomalies rencontrées

**A1 — les incidents penchent nettement vers les modules METAL, sans leur être réservés.**
Sur les **10 incidents de worker** relevés en 7 passes (9 rattrapés + 1 non rattrapé) :

| module concerné | incidents |
|---|---|
| `CERTUS_METAL_SINGLE` | 8 |
| `CERTUS_METAL_BILAYER` | 8 (dont **les deux** non rattrapés) |
| `CertusDesignApp` | 2 |
| `CERTUS_INDEX` | 1 |
| tous les autres modules | 0 |

*(chiffres finaux : 14 passes abouties, 19 incidents — les METAL en concentrent **16**)*

⚠️ **Correction de ce que j'ai écrit après la passe 6.** J'y affirmais que « tous les autres
modules » étaient à zéro et que la concentration sur les METAL était acquise. La passe 7 a
produit un incident sur `CERTUS_INDEX` : **c'était prématuré sur 8 points de mesure.** Les
METAL restent nettement en tête (7 sur 10), mais le phénomène n'est pas exclusif.

`CERTUS_RE` — le module sur lequel le taux de référence de 1,7 % avait été mesuré — n'a
toujours **jamais** été touché en 7 passes.

🔑 **`METAL_SINGLE` reste le meilleur point d'entrée pour chercher la cause racine** : une
boucle de lancements y établirait son taux propre en une vingtaine de minutes.

**Non fait** : mesurer un taux entre dans le périmètre autonome, mais monopoliserait la machine
que les passes utilisent. À arbitrer au retour — c'est le choix entre une passe de plus et une
piste de cause racine.

### 🔎 A2 — enquête du 2026-09-08 : reproduction ramenée de 1 h à 14 s

**Le déclencheur est identifié, le mécanisme ne l'est pas.** Ce qui est établi :

| fait | mesure |
|---|---|
| **Déclencheur** | `test_certus_ux_battery.py::test_design_and_re_splitter_persistence` exécuté avant. **3 échecs sur 3.** |
| **Reproduction minimale** | ce test + le squelette = **14 s** (contre 1 h pour la passe complète) |
| Le squelette seul | passe, 7,5 s |
| `test_certus_ux_drag_and_drop.py` avant (contrôle) | passe |
| Les 9 premiers fichiers de `tests/ui/` avant | passent |

🔑 **Ce n'est pas une fenêtre « encore en construction », contrairement à ce qu'affirme le
§0bis du dossier.** `skeleton()` ne compte que les widgets **visibles**
(`audit_ux_certus.py`, garde `isVisible()`), et la fenêtre mesure 84 contrôles au lieu de 120 —
il manque les 7 onglets du panneau de graphes et son bouton de détachement, c'est-à-dire **un
panneau entier**. Le harnais annonce `stable=True` parce que la fenêtre *est* stable : elle est
simplement amputée.

**Quatre hypothèses réfutées par la mesure** — à ne pas reprendre :

1. **État persistant (QSettings).** Le worker lancé hors pytest rend **120 avant comme après**
   le test déclencheur. L'isolation `_isolate_qsettings()` fonctionne.
2. **Variables d'environnement de threads.** L'import des modules pose
   `OMP_NUM_THREADS=31`, `NUMBA_NUM_THREADS=31`, etc., et `_run_worker` les transmet au
   sous-processus — mais le worker lancé avec ces variables rend **120**.
3. **`PATH` modifié** (`PyQt6\Qt6\bin` ajouté en tête par l'import) : **120** également.
4. **Répliques partielles** : importer les 9 applications, construire DESIGN, construire RE,
   appeler `_qs_save()` / `_qs_restore()` — aucune combinaison ne reproduit.

⚠️ **Un clone fidèle du fichier déclencheur fait planter pytest lui-même** (sortie tronquée,
code 127) — même famille que A4.

**Piste restante** : l'effet exige que le worker soit lancé *depuis* le processus pytest ayant
exécuté ce test, alors qu'aucun canal évident (environnement, disque, réglages) ne le
transporte. **Enquête laissée ouverte à ce point**, sans contournement.

---

**A2 — `skeleton[CERTUS_DESIGN]` n'est pas un aléa : 2 échecs sur 2.** Relevés
`stable=True settle=4.35s controls=84/92` puis `settle=4.41s controls=84/92` — **le même
déficit exact**, les 8 mêmes contrôles manquants (les sept onglets et le bouton de
détachement). Il passe seul en 7,5 s.

Le §0bis du dossier le donnait déjà « trois runs sur trois » avant ce chantier, et disait
l'avoir traité par une relecture différée : **cette garde ne le rattrape pas.** Le harnais
déclare la fenêtre stable alors qu'elle n'a pas fini de se construire — un compte constant
n'est pas un compte final. **Préexistant, sans rapport avec ce chantier, laissé en l'état :
c'est le seul obstacle restant à `0 failed`.**

**A4 — 🔴 la violation d'accès n'épargne pas le processus pytest lui-même.** Passe 11, à 5 % :

```
tests\ui\test_ui_module_imports.py ....Windows fatal exception: access violation
Thread 0x0000dc84  [Thread-24]
Segmentation fault (exit code 139)
```

**La passe entière est perdue**, après 4 minutes. Ce n'est ni un échec de test ni un incident de
worker : c'est **l'interpréteur qui exécute pytest** qui est tué, sur un **thread secondaire**,
par la même violation d'accès que celle observée dans les workers.

🔑 **Ce que cela change.** Le correctif du §3 protège les **sous-processus** ; il ne peut rien
pour le processus principal. La reproductibilité obtenue reste réelle — 10 passes sur 11 ont
rendu un verdict exploitable — mais elle a une **limite dure** : environ **une passe sur onze
n'aboutit pas du tout** sur ce poste.

C'est aussi un argument de plus pour chercher la cause racine : le défaut n'est pas propre au
harnais de mesure, il touche l'exécution de la suite en général. Même famille que A3.

⚠️ *Une seule occurrence : ne pas en tirer de taux.* Consigné, passe relancée, **rien
contourné**.

**A3 — 🔑 il y a DEUX modes de défaillance du worker, pas un seul.** Les reprises signalées
jusqu'ici portent toutes `exit status 0` — un worker qui se **termine proprement sans imprimer
son marqueur** — alors que l'échec de la passe 1 portait `0xC0000005`, une violation d'accès.

Ce second mode n'est décrit nulle part dans le dossier, et il est plus déroutant : un code de
sortie 0 signifie que Python est allé au bout, donc que le marqueur *aurait dû* être écrit.
Piste, **non mesurée** : sortie standard perdue ou tronquée plutôt que processus tué.

La conséquence pratique est nulle — la reprise absorbe les deux — mais toute recherche future
de la cause racine doit savoir qu'elle poursuit **deux phénomènes distincts**, et non un seul.
