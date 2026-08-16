# REPRENDRE ICI — état gelé au 2026-08-16, 08:45

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
| **la mémoire de compte** | `<.claude>/projects/<projet>/memory/`, 9 fichiers, 17 Ko. **Par compte et par machine.** Elle porte des pièges absents du dépôt |
| **le `.venv`** | à reconstruire. 📌 Piège documenté : un venv de snapshot peut charger le code d'**un autre** snapshot — vérifier avant toute mesure |
| **le hook d'auto-push** | `.claude/` n'est pas versionné. Sur cette machine **tout commit publie** vers `nikonvr/CERTUS` ; ailleurs, ce ne sera pas le cas |

**Tout le reste est dans git**, y compris les 260 intervalles premium, les 270 fast, les
contrôles négatifs et la série d'échelle.
