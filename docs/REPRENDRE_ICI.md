# 🔴 REPRENDRE ICI — état gelé le 2026-08-21 à 00:15

> Ce fichier dit **où on s'est arrêté** et **la commande exacte pour repartir**. Il est le
> premier à lire, avant `CLAUDE.md`.

---

## 0. ⚡ LA SITUATION EN CINQ LIGNES

👤 veut que **le code de production** trouve sur `r75x2` à **2 nm** une stratégie au niveau de
**SEEL 0,5692** — le niveau que la graine 77 atteint. À la graine 42 seule, il rend **0 déposable
sur 1617**, toutes à 100 % de plantage.

🔴 **LA CONTRAINTE MONO-GRAINE EST LEVÉE — 👤, 2026-08-21.** Elle disait *« le code de production
reste à `robustness_seed = 42`, définitivement »*, et elle a gouverné tout le plan jusqu'ici.
👤 : *« même si le code en production est ralenti, ce sera un gain énorme d'inclure des
stratégies diverses venant de plusieurs seed »*. **La recherche a donc le droit de tirer
plusieurs billets.** Ce qui reste à trancher, et qui n'est PAS la même question, est de savoir si
la **notation finale** reste à une graine fixe — voir §7.

🔴 **UN BATCH TOURNE EN CE MOMENT.** Lancé le 2026-08-20 à **23:58**, pour **9,5 h**, donc
**fin vers 09:30**. Ne lance rien d'autre : une mesure, une machine. Voir §1.

📌 Le plan est [`PLAN_PRODUCTION_2026-08-20.md`](PLAN_PRODUCTION_2026-08-20.md), dont le **§15**
est la synthèse la plus récente. Le chantier Rate est [`CHANTIER_RATE.md`](CHANTIER_RATE.md).

---

## 1. 🔴 LA PREMIÈRE CHOSE À FAIRE — lire le rapport du batch

```bat
dir reports\BATCH_seed42_*.md
```

Le rapport est **réécrit après chaque cellule**, donc lisible même si la nuit a été coupée.
Il porte lui-même sa lecture : la porte C1, la décision prise, un tableau par cellule, et ce
qui a été **sauté** avec son motif.

### La porte C1 — à vérifier AVANT de lire un seul chiffre

La cellule 1 tourne aux **réglages d'origine** et doit rendre **exactement** :

```
1617 strategies · 0 deposable · crash_min 100,00 % · ELITE 0 strategie
```

L'instrument `[ELITE-WL]` (commit `5105fc8`) est de la journalisation pure. 🔴 **Tout écart
signifie qu'il a fui dans le calcul, et toute la nuit est à jeter avant d'être lue.** Le batch
s'arrête de lui-même dans ce cas et l'écrit en tête du rapport.

### Les quatre cellules, et pourquoi celles-là

| cellule | ce qu'elle change | pourquoi elle est **honnête** |
|---|---|---|
| `base` | rien — la référence | c'est la porte C1 |
| `cgc95` | `crash_gate_confidence=0.95` | la porte compare une **borne de confiance** au lieu d'un taux estimé. La tolérance de 5 % de 👤 **ne bouge pas** : c'est l'estimateur qui était faux |
| `nogain` | `elite_stop_on_no_gain=false` | à 0 retenue, le round 1 coupait **tout** : les rounds 2 et 3 de `deep` ne tournaient jamais |
| `reach` | `elite_wl_neighbor_span=2` + `elite_max_candidates=240` | λ ± 2 nm au lieu de ± 1, plafond de 120 → 240. ⚠️ **deux réglages à la fois**, attribution impossible entre eux — assumé, ils forment une seule idée |

🔒 **Aucune ne relâche la physique.** C'est ce qui rend leurs résultats **déjà jugés au
nominal**, donc directement exploitables.

### 🔒 L'ARBITRAGE PRIS EN AUTONOMIE, ET C'EN EST UN

👤 proposait de **relâcher bruit et dérive** pour laisser passer plus de candidates dans ELITE.
**C'est la bonne cible** — les 84 %. **Cette cellule n'a PAS tourné, délibérément :**

> Relâcher change **le monde** où vivent les candidates. Tout ce qu'on y trouve doit donc être
> **re-jugé au nominal**. Or le juge au nominal, `probe_renoter.py`, est en panne et sa cause
> **n'est pas localisée** (§3). Un résultat de cette forme aurait été inexploitable au matin.

**C'est la première chose à rouvrir avec 👤**, et elle demande d'abord un juge au nominal.

---

## 2. 📏 CE QUI EST ÉTABLI — et tout est sur `r75x2` à 2 nm, `deep`

```
graine 42 : 1617 strategies,   0 deposable,  toutes a 100,00 %
graine 77 : 2231 strategies, 547 deposables, meilleure SEEL 0,5692, crash 1,33 %
```

**1. 🔑 Hors ELITE, il n'y a rien — aux DEUX graines.** 0 déposable sur 1488 (graine 77) et
0 sur 1617 (graine 42), crash médiane 100 % des deux côtés. Toute la fabricabilité de ce
composant passe par l'étage ELITE, et il n'existe **aucune** voie de contournement dans les
générateurs existants.

**2. 🔑 Les 84 % de rejets d'ELITE SONT la porte de plantage.** Chaînage établi :

```
_crash_gate_rejects (robustness.py:2693)  ->  final_score = float("inf")
                                          ->  robustness_score = inf
ELITE : not np.isfinite(full_score) (consensus.py:792)  ->  rej_score_non_fini
```

Sur 1327 candidates évaluées en entier : **1116 (84 %) meurent de la porte de plantage**,
**211 (16 %) du seuil de RMSE**. Donc `crash_gate_confidence` est le traitement **direct** de la
cause, et `elite_min_improvement` — écrêté par `max(0.0, …)`, il ne peut que **durcir** — ne
touche que les 211.

**3. ✅ L'export des 12 plans de la graine 77 est EXACT.** 12/12 appariés à la référence par
signature de blocs `(start, end, wavelength)`, un candidat unique chacun. Et les 547 déposables
sont **toutes `origine = ELITE`**, toutes `resolution_nm = 2.0` : aucune variante Rate, aucune
variante de fente.

**4. 🔴 La falaise à 685 nm existe et n'est PAS la cause.** 544 des 547 déposables surveillent
la couche 35 à 685 nm, et la graine 42 ne propose **jamais** cette λ, à aucune couche — elle
campe à 686 nm avec 1156 stratégies. **Mais ventilé par générateur** : 685 nm hors ELITE = 711
stratégies, **toutes à 100 %** ; 686 nm dans ELITE = 3 stratégies, **déposables à 100 %**. La λ
n'est ni suffisante ni nécessaire. C'est un **effet de sélection** — ELITE raffine autour de ses
parents, il s'est empilé là où ça marchait.

> 🔴 **« Forcer 685 nm » ne marcherait pas. Ne paye pas cette piste.**

---

## 3. 🔴 CE QUI EST RETIRÉ — ne pas le recycler

| affirmation | statut |
|---|---|
| « la panne de `probe_renoter` est localisée : `full_dynamics_grid` est vide » | 🔴 **FAUX.** La grandeur n'est déréférencée qu'à **un seul endroit** du dépôt — `robustness.py:2513`, dans un bloc de **journalisation** gardé par `theory_dyn >= 0.0` — et la **Phase B de production tourne toujours avec elle vide** : `minimized_context` (`certus_strat_workers_pipeline.py:146`) ne porte pas la clé. Le contexte que la sonde capture **est** celui de la production |
| « le plantage est une propriété de la stratégie » (8/8 à 100 %) | 🔴 non informatif — vient de l'outil en panne. Le §14 du plan est passé en **talon** |
| « les 12 stratégies de la graine 77 plantent à la graine 42 » | 🔴 artefact |
| « le corridor d'indice n'est pas en cause » | 🔴 artefact |
| « `elite_min_improvement` est l'action la plus rentable du plan » | 🔴 corrigé — il vise 16 % des rejets, pas 84 % |

### 🔴 La cause de la panne de `probe_renoter.py` reste NON LOCALISÉE

**Six candidates éliminées** le 2026-08-20 au soir, sans une seconde de machine :

| candidate | pourquoi elle tombe |
|---|---|
| `full_dynamics_grid` vide | inerte, voir ci-dessus |
| unité de `crash_rate` | le noyau la formate en `:.1%`, c'est une fraction ; le `100 ×` de la sonde est correct |
| plans malformés | les 9 à 11 blocs pavent `[0,75)` exactement, 0 trou, 0 chevauchement, `end` exclusif comme le noyau le lit |
| chemin de **surcharge** de résolution | `config_r75x2_natif_2nm.json` écrit 2 nm **dans la configuration** : marge **bit-identique** aux runs surchargés |
| `expand_variants=False` | le garde ne couvre que la **génération** de variantes ; la base reste « bit-identical to a no-search run » |
| une clé perdue sur `strategy` | le noyau n'y lit que `blocks`, `strategy_id`, `monochromator_resolution_nm`, `rate_layers`, `slit_profile`, `witness_reset_layers`, `l0` ; les deux dernières manquent et se replient sans effet |

🔑 **La grandeur qui trancherait n'existe nulle part** : le `params` effectif **complet** des
deux chemins. La référence consigne 11 clés de `config`, les re-notations 11 clés de
`parametres_de_notation`. **Poser cet instrument est la seule action légitime** — c'est la règle
du projet, et elle s'applique littéralement ici.

⚠️ **Deux lectures à ne pas refaire** : la marge identique au seizième chiffre entre les 12 plans
n'a rien d'impossible — comportement **documenté** à `robustness.py:2805`, les 12 partageant leur
préfixe donc la physique de la couche 35. Et `n_layers_below_2A = 153` somme sur **trois causes**,
ce n'est pas un index de couche.

---

## 4. ✅ CE QUI A ÉTÉ PORTÉ DANS LE CODE

| | commit |
|---|---|
| **13 clés** ne franchissaient pas le JSON, dont `robustness_seed` câblée à 42 | `aad370a` |
| les **4 leviers ELITE** (`span`, `max_candidates`, `stop_on_no_gain`, `max_full_evals`) | `f9b71ba` |
| ELITE **compte ses rejets**, 3 sorties nommées | `3151f3a`, `9e23567` |
| 🟢 **l'instrument `[ELITE-WL]`** — la **λ** et le **taux** des candidates rejetées. 34 tests, qui échouent sur le code d'avant | `5105fc8` |
| le plan corrigé : §14 retiré, la panne mal localisée, §15 neuve | `214959e` |
| surcharges génériques de la sonde (**étiquette obligatoire**) + le pilote de nuit | `1f39cdd` |
| `coherence_md.py` ne plante plus en console cp1252 | (ce commit) |

⚠️ `elite_num_runs` reste **délibérément non routé** : son défaut noyau vaut
`min(num_runs, 80)`, donc le router avec un défaut de 0 donnerait `max(10, 0) = 10` — un
huitième de la profondeur. Il faudrait une sentinelle côté noyau.

### Comment essayer un levier sans écrire de fichier de configuration

```bat
set CERTUS_PROBE_OVERRIDES=crash_gate_confidence=0.95
set CERTUS_PROBE_TAG=cgc95
C:\envs\certus\Scripts\python.exe scripts\probe_blocs_vs_plantage.py r75x2 deep 0 0 2.0 0 42 0
```

🔴 **L'étiquette est obligatoire et la sonde refuse de tourner sans elle** : deux runs qui ne
diffèrent que par une surcharge rendraient sinon deux artefacts indiscernables sur le fond. La
surcharge **et** l'étiquette entrent dans le bloc `config` de l'artefact et dans le nom du
fichier.

---

## 5. Les fichiers à connaître

| | |
|---|---|
| `reports/BATCH_seed42_*.md` | 🔴 **le rapport de la nuit** — à lire en premier |
| `reports/batch_seed42_*/journal_*.log` | les journaux **complets** de chaque cellule, non tronqués |
| `reports/blocs_vs_plantage_r75x2_deep_s042_20260820_120112.json` | la **référence** graine 42, 1617 stratégies — sert au contrôle C1 |
| `reports/blocs_vs_plantage_r75x2_deep_s077_20260820_160340.json` | les 547 déposables de la graine 77, **avec λ** |
| `reports/plans/plans_s077_vers_s042.json` | les 12 meilleures de la graine 77, avec leurs λ |
| `reports/plans/config_r75x2_natif_2nm.json` | 2 nm **écrit** dans la config, sans surcharge |

---

## 6. ⚡ Repartir

```bat
C:\envs\certus\Scripts\python.exe scripts\preflight.py
C:\envs\certus\Scripts\python.exe scripts\coherence_md.py
C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Attendu : `PREFLIGHT=GO` · `0 point(s) a instruire` · **`2520 passed, 5 skipped`**.

⚠️ **L'interpréteur est `C:\envs\certus\Scripts\python.exe`.** Il n'y a **pas** de `.venv` dans
le dépôt ; tout document qui en cite un est faux. `scripts/coherence_md.py` (contrôle E) vérifie
mécaniquement que tout interpréteur cité existe.

⚠️ **Le compte de tests se périme dès qu'on ajoute un test.** Il valait 2450 le 17/08, 2486 le
20/08, **2520** depuis l'instrument. Ne t'arrête pas sur l'écart : vérifie qu'il n'y a **aucun
échec**.

🔴 **Et si le batch tourne encore, ne lance pas la suite de tests** — elle sature les cœurs et
la règle du projet est *une mesure, une machine*.


---

## 7. 🔵 LA CONTRAINTE MONO-GRAINE EST LEVÉE — ce qui tombe, ce qui reste

👤, le 2026-08-21 : *« même si le code en production est ralenti, ce sera un gain énorme
d'inclure des stratégies diverses venant de plusieurs seed »*, et *« enlève des fichiers md la
contrainte que le code sera restreint forcément à un seed 42 »*.

### Ce qui tombe

> ~~« Le code de production reste à `robustness_seed = 42`, définitivement. »~~

Elle gouvernait tout le plan et **elle est retirée**. La recherche a le droit de tirer plusieurs
billets, et le ralentissement est accepté d'avance.

### 🔴 Ce qui reste à trancher, et ce n'est PAS la même question

| | |
|---|---|
| la **RECHERCHE** est multi-réalisation | ✅ **tranché** — c'est la décision du 21 |
| la **NOTATION** finale reste-t-elle à une graine fixe ? | 🔴 **ouvert**, et c'est une décision de 👤 |

Pourquoi ça compte : le score publié doit être **reproductible**, sinon deux lancements du même
fichier rendent deux SEEL. Et si la notation tourne sur les mêmes graines que la génération, on
paie la **malédiction du vainqueur** — mesurée à **+12,9 %** le 2026-08-15.

📌 **Ce que je propose par défaut, en attendant** : générer sur K graines, **noter sur une base
fixe et disjointe**. C'est le compromis qui donne la diversité sans le biais, et il ne coûte rien
de plus.

### 🔑 Où le multiseed doit entrer — mesuré, pas supposé

📏 Le 2026-08-21, comparaison des deux populations par **signature de plan exacte**, par nombre
de blocs :

```
n_blocs      1      2-6     7-10    11-15
communes  46,7 %   7,4 %   ~1 %      0 %
```

**Il n'y a aucun préfixe commun** : dès le bloc 1, où il n'existe pourtant **aucun héritage**, la
moitié de la population diffère déjà. Puis ça s'effondre à zéro.

⇒ Le point de divergence est le **criblage Monte-Carlo** (`n_screen = 50`), appliqué dès le
premier nombre de blocs. Ses survivants deviennent les `inherited_strategies` du bloc suivant, et
l'écart **se compose** jusqu'à ce que les deux recherches n'aient plus rien en commun. Les parents
d'ELITE héritent de toute cette dérive.

🔑 **C'est donc là que le multiseed va** — pas dans la génération ELITE, qui est **déterministe**
(§18.1). Le détail de la conception est au **§19 du plan**.
