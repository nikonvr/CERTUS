# REPRENDRE ICI — état au 2026-08-19, **soir**

> ⚠️ **Tout ce qui suit le premier bloc est ANTÉRIEUR.** Les §1 à §5 décrivent le gel du
> 2026-08-16, et le bloc « ARRÊT DU MATIN » décrit une journée qui a repris depuis. **Lis
> le bloc ci-dessous d'abord ; il corrige les deux.**

## 🔴 OÙ ON EN EST LE 2026-08-19 AU SOIR

**Un batch TOURNE** — `scripts/batch_voie_de_garage.py`, lancé à 17:47, trois cellules,
fin estimée vers **00:47**. ⚠️ Estimation extrapolée du `premium`, jamais mesurée : `deep`
à 2 nm n'avait jamais tourné sur ce composant.

| # | cellule | ce qu'elle tranche |
|---|---|---|
| 1 | `r75x2 deep @ 2 nm`, graine 42 | **la case manquante de l'analyse contradictoire** |
| 2 | idem, graine 77 | une graine ne fait pas un verdict (§24-46) |
| 3 | la **courbe SEEL(n)**, `n` = 2 → 75 | la sonde de 👤 : `n` couches optiques, le reste à épaisseur **parfaite** |

### Les cinq acquis de la journée, et deux sont des CORRECTIONS de mes propres écrits

| | |
|---|---|
| 🔑 **le mécanisme du Rate est la POSITION TERMINALE** | expérience **appariée** : 11 couches Rate au milieu ne sauvent rien, 17 en queue suffisent. Une couche Rate lègue son erreur en boucle ouverte à **tout ce qui la suit** ; la dernière n'a rien en aval |
| 🔴 **le mécanisme que j'avais publié était FAUX** | *« la queue franchit la zone où la dérive tue l'optique »* — la couche critique des déposables est 39, **avant** la coupure. Réfuté par les artefacts eux-mêmes |
| 🔒 **deux règles gravées par 👤** | Rate **interdit** sur les couches 0 et 1 (le facteur n'a aucune référence : `n_ref = 0`), **autorisé partout ailleurs, dernière comprise** — elle ne l'avait jamais été, **0 placement sur 24 581**. Et le rate ne se calcule **que sur les couches optiquement déposées** |
| 📏 **le taux réel de l'hybride est ~3 %** | sous la cible de 5 %. Le `4,00 %` de `fast` n'était que la granularité **2/50** |
| 🔴 **l'analyse contradictoire du soir** | l'hybride est **dominée sur tous les axes** par le pur optique à 1 nm — 277 déposables contre 1, **6 blocs contre 75**. Mais cette solution bascule à **0** sur la graine 77, et `deep` à 2 nm n'avait **jamais** été lancé. C'est ce que le batch tranche |

🔑 **Le diagnostic qui gouverne la suite** : `r75x2` est assis **exactement sur la frontière
de fabricabilité**, où tout verdict bascule avec la graine. **Bâtir une méthode dessus, c'est
bâtir sur du sable.** Si la cellule 1 rend des déposables en pur optique, la queue Rate sur
ce composant est une **voie de garage** et il faudra l'écrire.

📌 **Tout le détail est dans [`CHANTIER_RATE.md`](CHANTIER_RATE.md) §9 à §12**, avec les
artefacts et les commandes. **Deux lecteurs sont prêts avant les données** — c'est délibéré :
`scripts/lire_batch_rate.py` (rend chaque écart **en σ** et refuse de désigner un optimum que
le bruit ne permet pas) et `scripts/lire_courbe_prefixe.py` (refuse d'afficher un SEEL là où
ça plante — un score de repli n'est pas une performance).

⚠️ **Ce qu'il ne faut PAS refaire** : le chiffre *« le Rate fait 64 % de l'offre et 0,15 % des
déposables, facteur 175 »* cité plus bas dans ce fichier est **retiré** — paradoxe de Simpson,
l'analyse stratifiée rend **0,99×**. Voir `CHANTIER_RATE.md` §1.

---

## 🛑 ARRÊT DU 2026-08-19 MATIN — journée depuis REPRISE, bloc conservé pour l'historique

Toute la nuit du 17 au 19 a fait tourner des campagnes de mesure sur le chantier prédictibilité
(§ suivante) et sur la matrice `extreme` (§ ci-dessous). **Les deux sont désormais arrêtées, à la
demande explicite de 👤**, machine libre, dépôt propre, rien en vol.

| chantier | verdict à l'arrêt |
|---|---|
| **prédictibilité à un témoin** | trois régimes distincts établis (×2 débloqué par une recherche plus profonde, ×0,5 barrière réelle, ×1,5 singularité insensible à l'offre). 🔴 Le 254 déposables de ×2 **ne tient pas** à la graine 77 — voir §4quater-bis du dossier |
| **mode `extreme`** | 🔴 **arrêté après 5 configurations, zéro amélioration mesurable sur aucune.** `docs/CHANTIER_PREDICTIBILITE.md` §4quater-bis en donne le détail et dit explicitement ce qui n'a **pas** été testé (48 cellules multifentes, jamais lancées) |

**Rien à relancer ce matin sans une raison neuve.** Les deux questions posées ont reçu leur
réponse, ou ont été arrêtées en connaissance de cause sur un rendement jugé trop faible.

🟢 **Une raison neuve existe déjà, posée par 👤 le 2026-08-19 : reprendre sur les idées du
Rate.** [`docs/CHANTIER_RATE.md`](CHANTIER_RATE.md) est écrit et attend — quatre contradictions
relevées, un plan en quatre actions ordonnées par valeur, et le chiffre qui en est le point de
départ : le Rate fait **64 % de l'offre** et **0,15 %** des déposables, facteur 175 contre
l'optique. **Action 1 du plan** : placer le Rate par `swing` (besoin) plutôt que par frontière de
bloc (coût), testée sur `75c à 1 nm` — la seule cellule sur 27 où le Rate gagne déjà.

---

## 🚀🚀 OÙ ON EN EST LE 2026-08-18 — le résultat qui change la lecture de tout le reste

> 🔴 **Un `crash_min = 100 %` ne veut PAS dire « ce composant n'est pas monitorable ». Il veut
> dire « ma recherche n'a pas proposé ce qui marche », et rien dans la sortie ne distingue les
> deux.**

📏 **La preuve, par intervention.** Le random75 ×2 rendait **0 stratégie déposable sur 404** et
**100 % de plantage**, à plat, sur tous les nombres de blocs — il était déclaré impossible depuis
trois jours. Même design, même graine, avec la fente à **1 nm** et une recherche **élargie ×5** :
**2 945 stratégies dont 254 déposables**, la meilleure plantant **4 fois sur 300**, **SEEL
0,629 nm**. C'est le premier SEEL valide jamais mesuré sur ce composant.

📏 **Et la corrélation le confirme.** Sur les cinq points de la série d'échelle mesurés au même
protocole, le rang du nombre de stratégies déposables corrèle à **+0,103** avec l'épaisseur
optique — la propriété du design — et à **+0,975** avec le **nombre de stratégies offertes** par
la recherche. 📌 [`CHANTIER_PREDICTIBILITE.md`](CHANTIER_PREDICTIBILITE.md) §4quater et
§4quinquies.

| ce qui en découle | |
|---|---|
| 🟢 **un mode `extreme`** | quatrième mode à côté de `fast` / `premium` / `deep`. Élargit ce qui est **généré**, laisse la profondeur d'**évaluation** identique à `deep`. Coût ≈ 5× deep |
| 🟢 **un fichier prêt à lancer** | `example/example_strat/JSON-strat-random75-x2-fabricable.json` — on charge, on lance, rien d'autre à régler. ≈ 2 h 40 |
| 🔴 **la série d'échelle est requalifiée** | son tableau *« échoue / passe / limite / échoue »* mesurait la recherche. `×1,75`, **plus épais** que `×1,5`, rend **282** déposables contre **1** |
| 🔴 **la fente fine est un REMÈDE** | 1 nm aide `×0,5` (48 → 28 %) et `×2` (100 → 38 %) — les deux qui **échouent** à 2 nm — et **nuit** aux deux qui réussissent déjà. Effet de plafond, pas préférence spectrale |

**Ce qui tourne au moment où j'écris** : la campagne **élargie**, deux tests falsifiables dont les
critères sont écrits d'avance — `×0,5` et `×1,5` en recherche élargie. S'ils confirment, il n'y a
pas de « barrière d'épaisseur optique » à prédire : il y a une **recherche à dimensionner**.

---

## 🚀 OÙ ON EN EST LE 2026-08-17 AU SOIR

| | |
|---|---|
| **le dépôt a déménagé** | `C:\certus`, hors Google Drive. Venv `C:\envs\certus`. **Toutes les commandes de ce fichier changent** — voir §6 |
| **le chiffre du 99c est passé de `0,782` à `0,81 nm`** | il était le plus favorable de trois graines. Détail dans [`CHANTIER_MULTITEMOINS.md`](CHANTIER_MULTITEMOINS.md), § *« CORRIGÉ LE 2026-08-17 »* |
| 🔵 **un chantier neuf, défini par 👤** | *prédire si un design passe avec un seul verre témoin*. Dossier : **[`CHANTIER_PREDICTIBILITE.md`](CHANTIER_PREDICTIBILITE.md)** |
| 🔴 **un défaut qui fausse la campagne des intervalles** | `search_resolution` était forcé à `False` alors que 👤 l'a posé comme **prérequis**. Voir le §5 du dossier ci-dessus |
| **ce qui tournait à la coupure** | `probe_blocs_vs_plantage.py` sur `r75x2` en premium, contrôle sans fente puis test avec — la thèse de 👤 sur la résolution spectrale |

🔑 **La campagne des 10 intervalles restants n'a PAS été reprise, et ce n'est plus la priorité.**
Le contrôle de graine (§ ci-dessous) a montré qu'un verdict d'intervalle bascule avec la graine :
mesurer 7 intervalles de plus à graine unique n'établirait rien. Le contrôle qui compte est
ailleurs — dans le nouveau dossier.

---

## 🔴 2026-08-17 — CE QUI EST PÉRIMÉ DANS LES §1 À §5 CI-DESSOUS

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
| **4 témoins** `0-22 / 22-42 / 42-76 / 76-99` | **0,782 nm** ⚠️ *graine 42 seule ; le chiffre à citer est **0,81 nm**, moyenne de trois graines — voir le bloc du 17/08 plus haut* | premium, 436 partitions, 31 à égalité |
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
| **CLAUDE.md est passé de 5 413 à 1 899 lignes** *(le « ~1 700 » écrit ici était l'état du 16/08 ; recompté le 19/08)* | neuf dossiers extraits vers `docs/`, chacun faisant **autorité** sur son sujet |
| **les sections ont été renumérotées** | quatre parties, le chantier courant en tête. Les 468 renvois `§N` ont été propagés mécaniquement |
| **`GEMINI_TODO.md` a été supprimé** | ordre de mission d'une campagne close |
| **trois règles violées en permanence ont été assouplies** | l'interdiction du mode fast, « conclusions seulement sur le 48 couches », « pas de troisième document » |
| **le chiffre du 99c est passé de 0,760 à 0,782 nm** ⚠️ *puis à **0,81** le 17/08 — cette ligne est historique* | le premier était biaisé vers le bas — malédiction du vainqueur, +12,9 % sur la même partition rejouée |

🔴 **Deux affirmations réfutées peuvent encore traîner dans de vieux textes** : *« les
espaceurs demi-onde ont un swing nul »* et *« le 99c plante en `LEVEL_UNREACHABLE` »*. La
liste complète est au §5 de [`REPRISE.md`](REPRISE.md).

---

## 6. Vérifier que l'environnement est sain — avant toute mesure

🔴 **Les chemins ont changé le 2026-08-17.** Le dépôt de travail est sorti de Google Drive, et
l'interpréteur n'est plus dans l'arbre. Substitue partout dans ce fichier :

| avant | maintenant |
|---|---|
| dépôt dans `…/Google Drive/…/CERTUS/1408` | **`C:\certus`** |
| `.venv/Scripts/python.exe` | **`C:\envs\certus\Scripts\python.exe`** |

```bash
C:\envs\certus\Scripts\python.exe scripts\preflight.py
```

```bash
C:\envs\certus\Scripts\python.exe scripts\check_claude_md.py
```

```bash
C:\envs\certus\Scripts\python.exe scripts\check_docs.py
```

```bash
C:\envs\certus\Scripts\python.exe -m ruff check .
```

```bash
C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

**Références, remesurées le 2026-08-17 sur i5-8250U** : `PREFLIGHT=GO` · ⚠️ le compte de tests qui suivait est **retiré**, il se périme à chaque ajout (`CLAUDE.md` §2) ; le critère est `0 failed`. `#
5 skipped` en **346,76 s** · `ruff` propre · `check_claude_md` **5** défauts · `check_docs`
**5** défauts *(les mêmes faux positifs qu'au 16/08 — regex sur des années, et cellules de
tableau dont l'avertissement est hors de la fenêtre de ±3 lignes)*.

🔴 **UN VENV NEUF MONTRE 3 ÉCHECS À LA PREMIÈRE PASSE, ET ILS SONT FAUX.** Cache numba froid :
`3 failed` en 850 s. Deuxième passe, cache chaud : **`0 failed`**. **Relance avant
de signaler quoi que ce soit** — détail du mécanisme en §2 de `CLAUDE.md`.

⚠️ Le `[BAD] running the venv interpreter` du préflight est un simple test de chaîne
(`"\.venv\" in sys.executable`, `preflight.py:125`), non fatal. Il vérifie le *nom* du chemin,
pas la validité de l'interpréteur.

---

## 7. Ce qui ne suit PAS le dépôt — presque plus rien

| | |
|---|---|
| ~~la mémoire de compte~~ | ✅ **RÉSOLU le 2026-08-16** : versée dans [`MEMOIRE_PROJET.md`](MEMOIRE_PROJET.md), donc dans le dépôt |
| ~~le piège du venv de snapshot~~ | ✅ **RÉSOLU le 2026-08-17** : il n'y a plus de snapshots datés à confondre. Un seul dépôt de travail, `C:\certus`, un seul venv, `C:\envs\certus`, et `preflight.py` contrôle que `import certus` résout bien dedans |
| **le venv** | à reconstruire sur chaque machine — 2 min : `uv venv --python 3.14.7 C:\envs\certus` puis `uv pip install --python C:\envs\certus\Scripts\python.exe -r requirements.lock` |
| **le hook d'auto-push** | vit dans `.git/hooks/`, **qu'un clone ne copie jamais**. Sur une machine neuve, commiter ne publiera pas : il faut `git push` à la main, ou recopier le hook |
| **l'identité git** | pas clonée non plus. `git config user.name CERTUS` et `user.email nikonvr@users.noreply.github.com` |

### 🔑 Passer d'un PC à l'autre — git est le transport, Drive est l'archive

```bash
git clone https://github.com/nikonvr/CERTUS.git --branch refactor-corridors-mixins C:\certus
```

Puis `git pull` en arrivant, `git push` en partant. **Le cache de campagne entier est suivi par
git** — 272 intervalles premium, 267 tirages `.npy`, 270 fast, 74 rapports de mesures réelles :
un clone ramène tout, **zéro recalcul**.

⚠️ **Ne remets pas le dépôt dans un dossier synchronisé.** Mesuré le 2026-08-17 : Drive avait
fait reculer `.git/refs/heads/refactor-corridors-mixins` de **8 jours** (137 commits invisibles,
`git status` annonçant 2 414 changements fantômes), laissé **208 fichiers absents** de l'arbre —
dont tous les `.py` de `certus/domain/optical/` et 7 fichiers de tests — et écrit **13
`desktop.ini` DANS `.git`**, dont 2 que git lisait comme des branches. **Aucune de ces pannes ne
produit d'erreur** : un arbre à moitié synchronisé *ressemble* à un dépôt complet.

📌 Repère posé avant le déménagement : le tag **`snapshot-1408`** marque l'état exact du dossier
Drive. Les ~520 Mo non suivis (dont 314 Mo de journaux de campagne) y restent, et c'est leur
place.
