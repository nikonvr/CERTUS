# REPRENDRE ICI — état gelé au 2026-08-16, 08:45

## 🔴 2026-08-17 — LIS CECI AVANT LE RESTE DU FICHIER : deux choses y sont périmées

### 1. Un verdict d'intervalle n'est PAS déterminé par une graine

Mesuré ce jour, même intervalle, même machine, seul `robustness_seed` change :

```
[38,99)  61c  graine 42  ->  AUCUNE_DEPOSABLE    0/452  crash_min 42,0 %  RMSE 0.18817
[38,99)  61c  graine 77  ->  DEPOSABLE          70/521  crash_min  0,0 %  RMSE 0.18777
```

Contrôle §12-1 passé : à graine 42, deux commits différents (`7564c78`, `817bc76`) rendent
**les mêmes nombres**, RMSE comprise. Le basculement vient de la graine, pas du code.

🔑 Ce n'est pas une gigue de quelques pour cent, c'est **catégoriel** — « impossible » contre
« 13 % viable ». Et l'effet se compose : la graine change le bruit, donc les choix de Phase A,
donc **la population de stratégies elle-même** (452 contre 521). Même classe de problème que
l'invariant de [`DECISIONS_TRANCHEES.md`](DECISIONS_TRANCHEES.md) — *la réalisation ne doit pas
décider quelles candidates existent* — appliquée à la graine au lieu de la profondeur.

⚠️ Le consensus **était actif** (`enable_consensus_ranking = 1`, 3 graines) et ne l'a pas
empêché : il porte sur le classement des `consensus_top_k`, alors que `n_deposables` et
`crash_min` se calculent sur **toutes** les stratégies.

🔴 **Le contrôle a été fait le même jour, et il déplace le chiffre publié : `0,782 → 0,81 nm`.**
La même partition gagnante rejouée à trois graines rend **0,782 / 0,816 / 0,839 nm**, soit une
étendue de **+7,3 %** pour un seuil d'équivalence de 3,0 %. La fabricabilité, elle, ne bouge
pas : les quatre intervalles restent déposables aux trois graines.

📌 **Le dossier qui fait autorité est [`CHANTIER_MULTITEMOINS.md`](CHANTIER_MULTITEMOINS.md),
§ « CORRIGÉ LE 2026-08-17 »** — chiffres, mécanisme, et ce qui reste valide y sont écrits une
seule fois. Ne les recopie pas ici.

### 2. Les durées de ce fichier et du cache appartiennent à une AUTRE machine

Le §2 annonce « 8,9 h cumulées, ~55 min d'horloge sur 10 shards ». Ces durées viennent de la
machine précédente. Mesuré sur celle d'aujourd'hui — **i5-8250U, 4 cœurs / 8 threads, 7,9 Go**,
1 shard seul, mode premium :

| intervalle | couches | durée | verdict |
|---|---|---|---|
| `[38,99)` | 61 | 1256 s | AUCUNE_DEPOSABLE (graine 42) |
| `[36,99)` | 63 | 1302 s | DEPOSABLE 6/446 |
| `[20,99)` | 79 | **2116 s** | DEPOSABLE 80/654 |

Le plafond `CERTUS_BENCH_TIMEOUT_S=5400` n'était donc pas en danger pour un shard **solo**. Le
débit à 10 shards concurrents sur 4 cœurs, lui, **n'a pas été mesuré** — la campagne a été
arrêtée avant, sans rien écrire.

🔴 `run_s` ne portait aucune trace de la machine. Corrigé (`7564c78`) : chaque entrée consigne
désormais `machine` à côté de `instrument`. **Les 263 entrées antérieures n'en ont pas** — leurs
durées ne sont comparables ni entre elles ni aux nouvelles.

⚠️ **Et une affirmation que j'ai écrite ce matin puis réfutée moi-même** : *« au-delà de
60 couches le monitoring optique cesse de fonctionner »*. Faux — `[20,99)`, **79 couches**, le
plus long des dix, rend 80 déposables à 0 % de plantage. Conclu sur un point, réfuté par le
suivant. Le tableau du §3.2 ci-dessous doit être lu avec ça en tête.

---

> **Lis ce fichier en premier, puis [`REPRISE.md`](REPRISE.md).**
> Celui-ci dit **exactement où on s'est arrêté et comment repartir**. L'autre dit ce que le
> projet sait. Les deux sont dans le dépôt, donc ils suivent un `git clone` : **aucune
> information ne dépend de la machine sur laquelle ils ont été écrits.**

---

## 1. Ce qui tournait, et pourquoi ça s'est arrêté

Le PC devait être éteint à 09:00. Les 10 derniers intervalles de la **vague 2 premium** ont
été **tués volontairement à 08:45**, alors qu'ils tournaient depuis 08:11-08:28 et auraient
fini vers **09:21**.

🟢 **Rien n'est perdu.** La campagne est **reprenable par construction** : un intervalle déjà
mesuré n'est **jamais** recalculé, le cache fait foi. Le coût de la reprise est le temps de
calcul de ces dix-là, et rien d'autre.

---

## 2. La commande de reprise — une seule, à copier telle quelle

```bash
export CERTUS_BENCH_TIMEOUT_S=5400
for i in $(seq 0 9); do
  CERTUS_BENCH_TIMEOUT_S=5400 nohup .venv/Scripts/python.exe scripts/campagne_intervalles.py \
      --vague 2 --hi 99 --mode premium --shard $i/10 > reports/prem_v2_$i.log 2>&1 &
done
```

| | |
|---|---|
| **ce qu'il reste** | **10 intervalles**, tous des suffixes `[a,99)` |
| lesquels | `[20,99)` `[22,99)` `[24,99)` `[26,99)` `[28,99)` `[30,99)` `[32,99)` `[34,99)` `[36,99)` `[38,99)` |
| longueurs | 61 à 79 couches — **les plus lourds de toute la campagne** |
| coût | **8,9 h cumulées**, soit **~55 min d'horloge** sur 10 shards |
| déjà en cache | **50 / 60** pour la vague 2 · **260** intervalles premium au total |

⚠️ **Ne change ni `--hi 99` ni `--mode premium`.** Avec d'autres valeurs le script demanderait
d'autres intervalles et le cache ne correspondrait plus.

**Surveiller :**

```bash
.venv/Scripts/python.exe scripts/campagne_intervalles.py --etat
```

---

## 3. Ce qu'il faut faire QUAND la reprise est finie

### 3.1. Le classement à 2 témoins — c'est la question qui a motivé cette campagne

```bash
.venv/Scripts/python.exe scripts/classer_partitions.py --mode premium --lo 20 --hi 99
```

**La question, et la réponse à battre** : une architecture à **2 témoins** avec de longues
campagnes bat-elle **0,782 nm à 4 témoins** ? Les intervalles longs n'existaient pas dans le
classement précédent — la vague 3 n'en a pas besoin, puisque trois parts de ≥ 20 couches sur
99 plafonnent chacune à 59.

**Ce qui est déjà connu, et qui sert de repère :**

| configuration | SEEL | source |
|---|---|---|
| **4 témoins** `0-22 / 22-42 / 42-76 / 76-99` | **0,782 nm** | premium, 436 partitions, 31 à égalité |
| 3 témoins, meilleure | 0,784 nm | +0,2 %, **égalité** (δ = 3,0 %) |
| 2 témoins, sous l'ancienne borne de 60 couches | 0,775 nm | fast, à re-mesurer en premium |

### 3.2. Ce que les longs intervalles disent déjà

Six des dix suffixes ont été mesurés avant l'arrêt, et le tableau est net :

| déposables / évaluées | plantage min |
|---|---|
| 41 / 571 | 0,0 % |
| 10 / 495 | 0,0 % |
| 8 / 538 | 0,0 % |
| 1 / 530 | 0,0 % |
| **0 / 575** | 14,67 % |
| **0 / 575** | 97,33 % |

🔑 **Au-delà de 60 couches, une campagne unique est faisable mais fragile** : 1 à 41 stratégies
sur ~500. À comparer aux **96,4 %** de taux de réussite sous 30 couches. Cohérent avec
`r = −0,869` entre longueur et taux, mesuré sur 270 intervalles.

---

## 4. Les deux autres chantiers, et leur état exact

### 4.1. 🟢 TERMINÉ — l'A/B du tri par marge en premium

| composant | OFF | ON | écart | verdict |
|---|---|---|---|---|
| 35c | 0,4980 nm — 501/507 | **0,4851 nm** — 461/467 | **−2,6 %** | égalité (δ = 3,0 %) |
| 48c | 0,1748 nm — 582/625 | 0,1754 nm — 554/623 | +0,3 % | égalité |

**Ce qui est acquis** : `use_margin_ranking` **atteint le calcul** — les `n_strats` changent
aussi (507→467, 625→623), donc l'ordre modifie les parents retenus en aval. Ce n'est **pas**
un paramètre inerte.

**Ce qui reste ouvert** : le **−2,6 % du 35c frôle le seuil** et va dans le bon sens. Une
troisième graine trancherait. 📌 Le paramètre reste **désactivé par défaut**, et il doit le
rester tant que ce n'est pas tranché.

```bash
# pour trancher : rejouer le 35c sur deux graines de plus
for s in 77 101; do for m in off on; do
  CERTUS_BENCH_TIMEOUT_S=5400 .venv/Scripts/python.exe scripts/test_margin_ranking.py \
      --composant 35c --mode $m --exec premium &
done; done; wait
```
⚠️ Le script fixe `SEED = 42` en dur — il faut l'exposer en option avant de lancer ceci.

### 4.2. 🟠 NON TESTÉ — `require_turning_point` sur le 99c

Le critère a été implanté et testé en **exclusion sèche** sur 48c et 35c : résultats **bit à
bit identiques**, aucun effet. Les candidates sans point tournant y sont sur des couches de
**bord** (0 et 47), déjà écartées par le coût Monte-Carlo.

**Non testé sur le 99c**, qui est dans un régime différent : 126 candidates douteuses, dont
une à **swing 0,467**.

---

## 5. Ce qui a changé dans la documentation ce matin — à savoir avant de la lire

| | |
|---|---|
| **CLAUDE.md est passé de 5 413 à ~1 700 lignes** | neuf dossiers extraits vers `docs/`, chacun faisant **autorité** sur son sujet |
| **les sections ont été renumérotées** | quatre parties, le chantier courant en tête. Les 468 renvois `§N` ont été propagés mécaniquement |
| **`GEMINI_TODO.md` a été supprimé** | ordre de mission d'une campagne close |
| **trois règles violées en permanence ont été assouplies** | l'interdiction du mode fast, « conclusions seulement sur le 48 couches », « pas de troisième document » |
| **le chiffre du 99c est passé de 0,760 à 0,782 nm** | le premier était biaisé vers le bas — malédiction du vainqueur, +12,9 % sur la même partition rejouée |

🔴 **Deux affirmations réfutées peuvent encore traîner dans de vieux textes** : *« les
espaceurs demi-onde ont un swing nul »* et *« le 99c plante en `LEVEL_UNREACHABLE` »*. La
liste complète est au §5 de [`REPRISE.md`](REPRISE.md).

---

## 6. Vérifier que l'environnement est sain — avant toute mesure

```bash
.venv/Scripts/python.exe scripts/preflight.py          # verdict GO / STOP
.venv/Scripts/python.exe scripts/check_claude_md.py    # coherence de CLAUDE.md
.venv/Scripts/python.exe scripts/check_docs.py         # tous les md et html
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

**Références au 2026-08-16** : `2450 passed, 5 skipped` · `ruff` propre ·
`check_claude_md` 5 défauts *(tous des faux positifs de regex sur des années et des numéros
de ligne)* · `check_docs` 5 défauts *(cellules de tableau dont l'avertissement est hors de la
fenêtre de ±3 lignes)*.

---

## 7. 🔴 Ce qui ne suit PAS le dépôt — à emporter à la main

| | |
|---|---|
| ~~la mémoire de compte~~ | ✅ **RÉSOLU le 2026-08-16** : son contenu durable est versé dans [`MEMOIRE_PROJET.md`](MEMOIRE_PROJET.md), qui est **dans le dépôt**. Plus rien d'essentiel n'y dépend de la machine |
| **le `.venv`** | à reconstruire. 📌 Piège documenté : un venv de snapshot peut charger le code d'**un autre** snapshot — vérifier avant toute mesure |
| **le hook d'auto-push** | `.claude/` n'est pas versionné. Sur cette machine **tout commit publie** vers `nikonvr/CERTUS` ; ailleurs, ce ne sera pas le cas |

**Tout le reste est dans git**, y compris les 260 intervalles premium, les 270 fast, les
contrôles négatifs et la série d'échelle.
