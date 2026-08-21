# 🔴 REPRENDRE ICI — état gelé le 2026-08-21 à 07:25

> Ce fichier dit **où on s'est arrêté** et **la commande exacte pour repartir**. Il est le
> premier à lire, avant `CLAUDE.md`.

---

## 0. ⚡ LA SITUATION EN CINQ LIGNES

👤 veut que le code de production trouve sur `r75x2` à **2 nm** une stratégie au niveau de
**SEEL 0,5692** — celui que la graine 77 atteint. À la graine 42 seule, il rend **0 déposable
sur 1617**.

### 🟢🟢 LA CIBLE EST ATTEINTE — mesuré le 2026-08-21 à 07:35

```
r75x2 @ 2 nm deep, graine 42, plage 9-11, avec les 12 plans de la graine 77 injectes
    295 strategies · 72 DEPOSABLES · crash_min 0,33 %
    MEILLEUR SEEL 0,5697   (cible 0,5692, ecart +0,1 % = INDISCERNABLE)

controle d'attribution, meme plage SANS injection : 63 strategies, 0 deposable, 100 %
```

🔒 **Une seule chose diffère entre les deux runs.** L'injection est donc la cause, et
l'attribution est faite.

🔑 **Les deux gagnantes diffèrent de DEUX NANOMÈTRES** — et celle de la graine 42 plante **moins** :

```
graine 77            450 610 616 685 647 700 511 688 704   SEEL 0,5692  crash 1,33 %
graine 42, injectee  450 610 615 685 647 700 511 687 704   SEEL 0,5697  crash 1,00 %
                             ^^^                 ^^^
```

📌 **Le livrable est au disque** : `reports/plans/plans_s042_gagnantes_injectees.json`, les 12
meilleures avec leurs λ par bloc.

🔴 **MAIS LA PRODUCTION NE SAIT TOUJOURS PAS Y ALLER SEULE**, et c'est ce qui reste à faire :

```
plafond ELITE porte a 480 (10 parents sur 10 explores)  ->  0 deposable
union de CINQ criblages a graines differentes           ->  0 deposable
porte de plantage a borne de confiance (0,95)           ->  0 deposable
queue Rate (mesuree les jours precedents)               ->  1 deposable, SEEL 0,686 (+20 %)
```

**Quatre leviers de recherche, quatre zéros.** Ce qui a marché est une **rampe de lancement**
venue d'un run à une autre graine — circulaire pour un produit. Voir §8.

📌 Le plan est [`PLAN_PRODUCTION_2026-08-20.md`](PLAN_PRODUCTION_2026-08-20.md) — ses **§15 à
§22** portent tout ce qui est récent. Le chantier Rate est [`CHANTIER_RATE.md`](CHANTIER_RATE.md).

---

## 1. 🔴 LA PREMIÈRE CHOSE À FAIRE — compter où 685 nm disparaît

C'est la seule voie qui rende la production **autonome**, et elle est bon marché.

📏 **Le fait qui la commande** : les 72 déposables surveillent **toutes** la couche 35 à
**685 nm**, et cette λ est **absente des 1617 stratégies de la graine 42**, à toutes les couches.
Elle est en revanche présente dans **711 stratégies non-ELITE de la graine 77**. Or la **Phase A
est identique aux deux graines** et la **DP est déterministe**.

⇒ **685 nm est offerte en Phase A et perdue plus loin.** Il suffit de compter, étage par étage,
combien de candidates la portent : minage → DP → criblage → héritage. **Un compteur par étage,
aucune physique touchée.**

⚠️ **L'artefact d'observabilité ne suffit pas** : `reports/STRAT_observability_*.json` donne des
**comptes** (couche 36 : `offered 185, forbidden_crash 92, survivors 93`, meilleur à **470 nm**)
mais **pas la liste des λ survivantes**. C'est le même instrument manquant que celui du §22.3 du
plan — **une liste de λ à toujours afficher** — et il sert les deux besoins.

### 🔑 Ce que les 12 plans injectés ont vraiment fait

Ils sont **absents de l'artefact** : ils ont été **éliminés**. Ce ne sont donc pas eux qui
réussissent, ce sont leurs **descendants ELITE**, à 9 et 10 blocs.

> **Les stratégies de la graine 77 ne sont pas des solutions transférables : ce sont des RAMPES
> DE LANCEMENT.** Elles plantent, et elles sont assez près d'une région saine pour qu'ELITE, en
> partant d'elles, l'atteigne en **deux nanomètres**.

C'est exactement le mécanisme du §18 du plan : la mutation d'ELITE est **déterministe, locale et
non dirigée**. Tout dépend d'**où on la fait partir** — pas de sa portée, ni de son plafond, ni du
nombre de graines.

---

## 2. ✅ CE QUI EST EN PRODUCTION DEPUIS CETTE NUIT

| | commit |
|---|---|
| **`screen_seed_list`** — K criblages, **union par signature de plan**, au point de divergence des graines | `44f352d` |
| **`injected_strategies`** — verser des plans donnés dans la population, par le canal de l'héritage | `43f7144` |
| **`[ELITE-WL]`** — la λ **et** la bande de plantage des candidates rejetées | `5105fc8` |
| **`[GATE]`** — combien de fois la borne de confiance change le verdict | `0117445` |
| surcharges génériques de la sonde, **étiquette obligatoire** | `1f39cdd` |
| `scripts/lire_multiseed.py` — et il **refuse de conclure** sur du partiel ou du dégénéré | `67c321b` |

🔒 **Tous inertes par défaut, chemin d'avant au bit.** Chacun a ses tests, et les symboles sont
absents du commit précédent — donc ils échouent tous sur le code d'avant.

### Comment essayer un levier sans écrire de fichier de configuration

```bat
set CERTUS_PROBE_OVERRIDES=injected_strategies=reports/plans/plans_s077_vers_s042.json
set CERTUS_PROBE_TAG=inject12s077
C:\envs\certus\Scripts\python.exe scripts\probe_blocs_vs_plantage.py r75x2 deep 0 0 2.0 0 42 0
```

🔴 **L'étiquette est obligatoire, la sonde refuse sans elle** : deux runs qui ne diffèrent que
par une surcharge rendraient sinon deux artefacts indiscernables. ⚠️ Le parseur découpe sur les
**virgules** — une liste de graines s'écrit donc `screen_seed_list=42;77;101`.

📌 Et la plage de blocs se resserre par les deux diviseurs, ce qui divise le coût sans rien
perdre : `iter_divider_start = 75/min_blocs`, `iter_divider_end = 75/max_blocs`. ⚠️ Les blocs
**1, 2 et 75 sont forcés** par le code, on ne peut pas les exclure.

---

## 3. 📏 CE QUI EST ÉTABLI — tout sur `r75x2` à 2 nm, `deep`

**1. 🔑 Hors ELITE, il n'y a rien — aux DEUX graines.** 0 déposable sur 1488 (graine 77) et
0 sur 1617 (graine 42), crash médiane 100 %. Toute la fabricabilité passe par ELITE.

**2. 🔑 La génération d'ELITE est DÉTERMINISTE.** `_generate_elite_candidate_strategies` énumère
un voisinage trié, parent par parent, et `return` au plafond. Donc « K graines de génération »
**ne peut pas** fonctionner : K graines rendraient les mêmes candidates. La diversité vit dans
les **parents**.

**3. 🔑 Le point de divergence des graines est le CRIBLAGE.** Par signature de plan exacte :

```
n_blocs      1      2-6     7-10    11-15
communes  46,7 %   7,4 %   ~1 %      0 %
```

**Aucun préfixe commun** : dès le bloc 1, où rien n'est encore hérité, la moitié de la
population diffère. Phase A est identique aux deux graines et la DP est déterministe — seul le
criblage Monte-Carlo l'est, et ses survivants deviennent les `inherited_strategies` du bloc
suivant **et** les parents d'ELITE.

**4. 🟢 Le multiseed est un mécanisme réel et il NE SATURE PAS.** Apport moyen en plans neufs
par rang de graine : **5,88 · 5,38 · 4,50 · 5,25 · 4,50**. La cinquième apporte autant que la
deuxième. Et l'effet est **localisé aux blocs 11-13**, là où la DP rend assez de groupements pour
que le criblage ait de quoi trancher.

**5. 📏 Le profil de coût par nombre de blocs**, et le partage **criblage 47 % / ELITE 53 %** :

```
bloc 75 : 1,1 min   ·   blocs 11-14 : 7,9 a 8,3   ·   blocs 3-10 : ~5,1   ·   bloc 1 : 2,8
facteur(K, cap) ~= 0,47.K + 0,53.(cap/120)
```

**6. 🔑 Le plafond de 120 laissait SEPT PARENTS SUR DIX inexplorés.** Un parent à 11 blocs coûte
~42 candidates (`n_blocs × 2` mutations de λ + `(n_blocs−1) × 2` frontières), donc `120/42 ≈ 2,9`
parents sur les 10 annoncés. À 480, mesuré : `generated=424 parents=10`.

**7. 🔵 La porte de plantage juge au PIRE DES TROIS NIVEAUX DE BRUIT**, dont un à **2× le bruit
mesuré** (`robustness_noise_factors = [0.5, 1.0, 2.0]`). La tolérance de 5 % de 👤 s'y applique,
et **aucun artefact ne porte le taux au bruit réel** — `crash_rate` **est** le max. Non mesuré :
c'est l'action 5 du §8.

---

## 4. 🔴 CE QUI EST RETIRÉ — ne pas le recycler

| affirmation | statut |
|---|---|
| « la panne de `probe_renoter` est localisée : `full_dynamics_grid` est vide » | 🔴 **FAUX.** La grandeur n'est déréférencée qu'à **un seul endroit** — `robustness.py:2513`, dans un bloc de **journalisation** gardé par `theory_dyn >= 0.0` — et la Phase B de **production** tourne toujours avec elle vide |
| « le plantage est une propriété de la stratégie » | 🔴 non informatif — vient de l'outil en panne |
| « `crash_gate_confidence` est le meilleur rapport valeur/risque du plan » | 🔴 **mesuré faux** : 0 déposable, compteurs identiques au chiffre près. **Une seule candidate sur 1116** est dans la bande où la borne agit — elle épargne jusqu'à ~7,3 % à `N = 300`, et les rejets sont à 25-99 % |
| « élargir `elite_wl_neighbor_span` aiderait » | 🔴 **réfuté** : `span = 2` porte le coût par parent de 42 à ~64, donc **aggrave** la troncature qu'il prétendait corriger |
| « le code de production reste à `robustness_seed = 42` définitivement » | 🔴 **levée par 👤 le 2026-08-21** — voir §7 |
| « forcer 685 nm » | 🔴 **inutile** : hors ELITE, 711 stratégies y plantent **toutes**, et 3 ELITE à 686 nm sont déposables. La λ n'est ni suffisante ni nécessaire — c'est un **effet de sélection**, ELITE s'est empilé là où ça marchait déjà |

### 🔴 La cause de la panne de `probe_renoter.py` reste NON LOCALISÉE

**Six candidates éliminées**, sans machine : la grille vide · l'unité de `crash_rate` (le noyau
la formate `:.1%`, c'est une fraction, le `100 ×` était correct) · des plans malformés (les blocs
pavent `[0,75)` exactement) · le chemin de **surcharge** de résolution (le config natif 2 nm rend
une marge **bit-identique**) · `expand_variants=False` (le garde ne couvre que la génération de
variantes) · une clé perdue sur `strategy`.

🟢 **`injected_strategies` le remplace et rend la réparation inutile** : les plans traversent le
code de production, sans contexte reconstruit. La docstring de la sonde porte l'avertissement.

### ⚠️ Deux défauts d'instrument, dits parce qu'ils fausseraient une lecture

- **Le compte d'une λ RARE n'est pas lisible dans le journal.** `_format_wl_histogram` n'affiche
  que les **14 λ les plus lourdes** ; 685 nm en porte 1 à 2 par ronde et tombe dans la queue
  masquée. **61 histogrammes tronqués** sur un seul run, et la preuve interne est là : 685 nm
  apparaît 5 fois en génération et **11 fois dans les rejets** — impossible sans troncature. Le
  compte est un **plancher**, et le contrôle du §18.4 du plan n'est ni confirmé ni réfuté.
- **Les graines de génération ne doivent pas contenir la graine de NOTATION.** Le run de la nuit
  a généré sur `42;77;101;202;303` et noté à **42** : canal de **malédiction du vainqueur**,
  mesurée à +12,9 % le 15/08. Générer sur `{77,101,202,303}`, noter sur une base disjointe.

---

## 5. Les fichiers à connaître

| | |
|---|---|
| `reports/nuit_multiseed_20260821/journal_*.log` | les journaux **complets** de la nuit |
| `reports/BATCH_seed42_20260820_235821.md` | le rapport du batch : `base` (porte C1) et `cgc95` |
| `reports/blocs_vs_plantage_r75x2_deep_s042_20260820_120112.json` | la **référence** graine 42, 1617 stratégies |
| `reports/blocs_vs_plantage_r75x2_deep_s077_20260820_160340.json` | les 547 déposables de la graine 77, **avec λ** |
| `reports/plans/plans_s077_vers_s042.json` | les 12 plans injectés — 9, 10 et 11 blocs |

---

## 6. ⚡ Repartir

```bat
C:\envs\certus\Scripts\python.exe scripts\preflight.py
C:\envs\certus\Scripts\python.exe scripts\coherence_md.py
C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Attendu : `PREFLIGHT=GO` · `0 point(s) a instruire` · **`0 failed`**.

⚠️ **Ne cite jamais un compte de tests comme référence** — il se périme dès qu'on ajoute un test.
Il valait 2450 le 17/08 et plus de 2560 le 21/08. **Le seul critère est `0 failed`**, comme
[`REPRISE.md`](REPRISE.md) le dit déjà.

⚠️ **L'interpréteur est `C:\envs\certus\Scripts\python.exe`.** Il n'y a **pas** de `.venv` dans
le dépôt ; tout document qui en cite un est faux.

---

## 7. 🔵 LA CONTRAINTE MONO-GRAINE EST LEVÉE — ce qui tombe, ce qui reste

👤, 2026-08-21 : *« même si le code en production est ralenti, ce sera un gain énorme d'inclure
des stratégies diverses venant de plusieurs seed »*.

| | |
|---|---|
| la **RECHERCHE** est multi-réalisation | ✅ tranché |
| la **NOTATION** finale reste-t-elle à une graine fixe ? | 🔴 **ouvert, et c'est une décision de 👤** |

Un score publié doit être **reproductible** — sinon deux lancements du même fichier rendent deux
SEEL. Et si la notation tourne sur les mêmes graines que la génération, on paie la malédiction du
vainqueur. 📌 **Proposition par défaut** : générer sur K graines, **noter sur une base fixe et
disjointe**.

🔒 **Et le mécanisme livré respecte déjà la règle d'or du multiseed** — *on ne s'en sert jamais
pour garder la graine qui marche* : l'union ne transporte que des **plans**, jamais des scores, et
la passe complète **renote tout** sur la réalisation du run. Un test l'épingle
(`test_the_multiseed_union_never_reranks_across_seeds`).

---

## 8. 🔵 CE QUI SUIT, PAR RENTABILITÉ

| # | action | coût | ce qu'elle décide |
|---|---|---|---|
| **1** | **la liste de λ à toujours afficher** (`_format_wl_histogram`) + le même dans l'observabilité de Phase A | ~1 h | 🔑 **où 685 nm disparaît-elle ?** C'est la seule voie vers une production **autonome** |
| **2** | compter par étage : minage → DP → criblage → héritage | 1 run | l'étage à réparer, sans plus rien deviner |
| **3** | graines de génération **disjointes** de la notation | gratuit | ferme le canal de malédiction du vainqueur (mon run a généré ET noté sur 42) |
| **4** | remonter `crash_rates_by_noise` à côté de `crash_rate` | ~30 min | la porte juge au **pire des trois niveaux**, dont un à **2× le bruit réel**, et rien ne dit le taux au bruit **mesuré** |
| **5** | rejouer l'injection en **plage pleine** (1-15 + 75) | ~2 h | confirme le résultat dans les conditions de production, sans restriction |

🔴 **La circularité qu'il faut casser, et c'est le vrai sujet** : l'injection marche, mais sa
source de bons plans est aujourd'hui **un run à une autre graine**. Pour un produit, ça ne
s'auto-amorce pas. Trois voies, et elles ne se valent pas :

| voie | ce qu'elle vaut |
|---|---|
| **A — bibliothèque de rampes** | 🟢 marche, mesuré. Mais il faut d'où venir |
| **B — comprendre pourquoi 685 nm est inatteignable** | 🔑 la seule qui rende la production autonome. C'est l'action 1 |
| **C — beaucoup plus de graines** | 🟠 l'union ne sature pas à 5, donc c'est plausible — mais rien ne dit que 685 nm soit à portée de tirage |

⚠️ **Ce qui n'a PAS tourné, et c'est un arbitrage assumé** : relâcher bruit et dérive en
génération. Le levier est bien visé — il attaque les 84 % de rejets — mais tout ce qu'il trouve
doit être **re-jugé au nominal**, et le juge au nominal était en panne. `injected_strategies` lève
maintenant cet obstacle : **c'est la première chose à rouvrir avec 👤.**
