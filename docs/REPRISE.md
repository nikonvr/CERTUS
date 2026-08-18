# REPRISE — lis ce fichier en premier, il fait une page

> Point d'entrée du projet CERTUS pour un agent qui arrive sans contexte.
> Écrit le **2026-08-16 à 07:45**. `CLAUDE.md` fait 5 400 lignes ; ce fichier dit **quoi y
> lire et dans quel ordre**, ce qui est **acquis**, ce qui est **faux dans les vieux
> documents**, et ce qui tourne en ce moment.

🔴 **Si tu reprends un travail interrompu, lis d'abord [`REPRENDRE_ICI.md`](REPRENDRE_ICI.md)** : commande exacte de reprise et état gelé au
2026-08-16 08:45.

---

## 1. Le projet en cinq lignes

CERTUS simule le **contrôle optique du dépôt de filtres interférentiels**. Pendant qu'une
couche pousse, la machine mesure la transmission d'un **verre témoin** à une longueur d'onde
de contrôle et arrête le dépôt à un niveau visé. Le module **STRAT** cherche, pour un
empilement donné, la **stratégie de surveillance** — quelle λ pour quelle couche, groupées en
**blocs** — qui minimise l'erreur d'épaisseur.

Le chantier en cours est la **multiple testglass methodology** : introduire un verre témoin
**neuf** en cours de dépôt pour rendre surveillables des empilements qui ne le sont pas.

---

## 2. Les six chiffres à connaître

| composant | couches | SEEL | condition |
|---|---|---|---|
| dichroïque `JSON-strat-example` | 48 | **0,173 nm** | 6 blocs, une campagne, 0 % de plantage |
| passe-bande 3 cavités `JSON-strat-bandpass-3cav` | 35 | **0,482 nm** | 6 blocs, DEEP, 0 % |
| aléatoire `JSON-strat-random75` | 75 | **0,272 nm** | une campagne, 0 %, 241/662 déposables |
| passe-bande 5 cavités `-5cav-99c` | 99 | **0,81 nm** | 🔴 **4 verres témoins** `0-22/22-42/42-76/76-99` · ⚠️ le `0,782 nm` était le plus **favorable de trois graines** (0,782 / 0,816 / 0,839), corrigé le 17/08 |
| le même, **une seule campagne** | 99 | *aucun score valide* | **100 % de plantage** — sur **751** stratégies remesurées le 17/08, de 1 à 99 blocs |
| **cible posée par 👤** | | **0,300 nm** | facteur **2,7** restant sur le 99c |
| 🟢 **random75 ×2**, mode `extreme` | 75 | **0,629 nm** | 🔴 **NOUVEAU 18/08** — le même empilement rendait **0 déposable et 100 % de plantage** en recherche standard. Fente 1 nm + mode `extreme` : **254 déposables sur 2 945** |

🔴🔴 **LE RÉSULTAT DU 2026-08-18, ET IL CHANGE LA LECTURE DE TOUT LE RESTE.** Un
`crash_min = 100 %` ne veut **pas** dire *« ce composant n'est pas monitorable »*. Il veut dire
*« ma recherche n'a pas proposé ce qui marche »*, et **rien dans la sortie ne distingue les
deux**. 📏 Sur les cinq points de la série d'échelle mesurés au même protocole, la corrélation de
rang avec le nombre de stratégies déposables vaut **+0,103 pour l'épaisseur optique** — la
propriété du design — et **+0,975 pour le nombre de stratégies OFFERTES** par la recherche. Et
l'intervention le confirme : même design, même graine, même fente, recherche élargie, ×2 passe de
**0/404** à **254/2 945**. 📌 [`CHANTIER_PREDICTIBILITE.md`](CHANTIER_PREDICTIBILITE.md)
§4quinquies.

🟢 **Ce qui en découle, et c'est un livrable utilisable tout de suite** : un quatrième mode
d'exécution **`extreme`** (à côté de `fast` / `premium` / `deep`) et un fichier prêt à lancer,
`example/example_strat/JSON-strat-random75-x2-extreme.json`. On le charge, on lance, il n'y a rien
d'autre à régler. Compter **≈ 2 h 40**.

⚠️ **Et le 99c n'est PAS une référence valable pour généraliser** — 👤, 2026-08-17 : *« il est
rare de déposer un empilement tout 1/4 d'onde, surtout en trigger POEM »*. Ses multiplicateurs
valent exactement 1 et 2, donc chaque couche finit **pile sur un extremum** : il est adverse à
POEM par construction. 📌 Ce qui le remplace comme instrument est la **série d'échelle du
random75** — voir [`CHANTIER_PREDICTIBILITE.md`](CHANTIER_PREDICTIBILITE.md).

**SEEL** = `2 × √(RMSE_P95)`, erreur d'épaisseur équivalente par couche, en nm. **C'est la
seule métrique à rapporter.** Jamais le RMSE brut.

⚠️ Les quatre composants **ne sont pas notés sur le même domaine spectral** (300 / 200 / 60 /
45 nm). Les comparer entre eux mélange la difficulté et la largeur de fenêtre. **À composant
fixé, les comparaisons sont valides.**

---

## 3. Quoi lire, dans quel ordre

| ordre | fichier | pourquoi |
|---|---|---|
| 1 | **ce fichier** | l'état du jour |
| 2 | [`CHANTIER_MULTITEMOINS.md`](CHANTIER_MULTITEMOINS.md) §25.12 puis §25.11 | les corrections les plus récentes — elles **priment** sur ce qui précède |
| 3 | le même dossier, §25.10 et §25.8 | la synthèse du chantier ⚠️ **partiellement périmée**, voir §5 ci-dessous |
| 4 | `docs/QWOT_ET_TURNING_POINT.md` | **obligatoire** avant d'écrire sur les points tournants |
| 5 | `CLAUDE.md` §6, §7, §14 | interdits, pièges, vocabulaire |
| 6 | `docs/PLAN_2026-08-16.md` | le plan en cours d'exécution |
| — | `reports/ENONCE_PROBLEME.md` | énoncé autonome, utile pour poser le problème à un tiers |

🔴 **Ne lis pas `CLAUDE.md` linéairement.** Sa section « CARTE DU DOCUMENT », en tête, dit où
aller selon la tâche.

---

## 4. Les cinq pièges qui ont coûté du temps — chacun a déjà frappé

| piège | symptôme | parade |
|---|---|---|
| **Le banc rend `RESULT=None` sous charge** | ça **ressemble** à « aucune stratégie ». Deux mesures perdues à 1800,7 s pile | `export CERTUS_BENCH_TIMEOUT_S=5400` **toujours** ; vérifier `WAIT_EXIT` |
| **Les surcharges de `collect_params` ne s'appliquent pas** | `run_workflow` **rappelle** `collect_params()` en interne ; régler le widget ne suffit pas | envelopper la méthode **et** compter les appels : `vus["n"] < 2` ⟹ mesure invalide |
| **Un paramètre qui n'atteint pas le calcul** | résultat **bit à bit identique** entre deux réglages | prouver par un **réglage destructif** qui doit faire échouer le pipeline. `machine_sampling_dd` est inatteignable depuis des semaines |
| **`AUCUNE_DEPOSABLE` ≠ infaisable** | en fast `[0,66)` rendait 0 ; en premium il rend 1 à **0,0 %** de plantage | ne jamais conclure à l'infaisabilité depuis un run fast |
| **`n_deposables` n'est pas une mesure de faisabilité** | son dénominateur `n_strats` est produit par la DP et varie **d'un facteur 2** entre longueurs voisines | ne lire que le **taux**, et seulement **en tendance sur beaucoup de points** |

**Deux règles de lecture qui découlent de tout ça :**

- **La résolution est une unité de décision.** 5,1 % en SEEL à N = 50, ~3,0 % à N = 150. En
  dessous, c'est une **égalité**, jamais un classement.
- **Un SEEL issu d'un minimum sur beaucoup de candidats évalués à N = 50 n'est pas
  publiable** — c'est la malédiction du vainqueur, et elle a coûté 12,9 % le 15/08 (`CHANTIER_MULTITEMOINS.md` §25.12).

---

## 5. 🔴 CE QUI EST FAUX DANS LES DOCUMENTS PLUS ANCIENS

Corrigé, mais des formulations peuvent traîner. **Ne les reprends pas.**

| affirmation | statut |
|---|---|
| « le 99c à 3 témoins donne **0,760 nm** » | 🔴 **périmé** — biaisé vers le bas. La même partition rejouée à N = 150 donne **0,858 nm**. Le chiffre est **0,782 nm** à 4 témoins |
| « la vague à 4 témoins est abandonnée par la donnée » | 🔴 **faux** — en premium c'est une partition à **4 témoins** qui gagne |
| « au-delà d'une cinquantaine de couches le témoin devient optiquement mort » | 🔴 **réfuté** — 75 couches aléatoires se surveillent à 0 % de plantage |
| « les espaceurs demi-onde ont un swing optique nul » | 🔴 **réfuté** — ils offrent **65 à 133 λ utilisables** chacun ; **zéro couche muette** sur 99 |
| « le 99c plante en `LEVEL_UNREACHABLE` » *(`strat.html` §10.15)* | 🔴 **faux** — c'est **17 %**. La cause majoritaire est `TP_MISCOUNT` à **83 %** |
| « `[22,78)` est le seul sous-empilement infaisable » | 🔴 **faux** — contredit par `[22,99)` qui a une stratégie déposable |
| « plus d'extrema ⟹ comptage plus fragile » | 🔴 **réfuté** — le comptage à 64 points est identique à celui de la densité machine |
| « QWOT = turning point » | 🔴 **faux sauf** couche 1 sur substrat nu, où `R = 0` exactement |

---

## 6. Ce que la mesure a établi sur le chantier multi-témoins

**1. Ça rend fabricable, ça ne rend pas plus précis.** La comparaison honnête est
*impossible → possible*, pas 0,86 → 0,78.

**2. La barrière est structurelle ET la longueur compte — les deux se cumulent.** Un
empilement aléatoire de 75 couches passe à 0 % ; le 99c à 5 cavités échoue. Mais sur 270
intervalles, le taux de stratégies déposables s'effondre monotonement avec la longueur,
**r = −0,869** :

| couches | 20-29 | 30-39 | 40-49 | 50-59 | 60-69 | 70-99 |
|---|---|---|---|---|---|---|
| taux | **96,4 %** | 81,8 % | 57,3 % | 29,5 % | 2,7 % | **0,7 %** |

**3. Le mécanisme d'échec est la MARGE, pas le comptage.** 👤 : *« ma machine de dépôt compte
très bien les turning points, même s'il y en a beaucoup ; c'est simplement la marge et les
swing qui peuvent poser problème. »* Mesuré, il a raison : le ×2 du random75 a **728** extrema,
**0,3 %** de sursauts marginaux, et il échoue par **plancher photométrique** (`T_min` médian
0,055). Le ×0,5 échoue par **marge** (20,7 % de sursauts sous 1,5× l'hystérésis).

**4. Changer de témoin est un outil de faisabilité, jamais d'optimisation.** Contrôle négatif
passé **3 fois sur 3** : +73/+89 % (48c), +10/+98 % (35c), **+110 %** (75c).

**5. Où changer, et combien de témoins, importent peu.** Étendue +11,6 % sur 436 partitions,
**31 à égalité**. 4 témoins 0,782 nm contre 3 témoins 0,784 nm : **+0,2 %**.

---

## 7. 🔴 LE TROU ACTIONNABLE PRINCIPAL

`turning_point_margins` (`certus_strat_growth.py:318`) calcule **deux marges par couche et par
tirage** — `margin_missed` et `margin_fab`. Elles remontent en `all_m_missed`/`all_m_fab`
(`certus_strat_batch.py:542`), sont réduites en `margin_profile`
(`certus_strat_robustness.py:2036`), exposées en `critical_layer` et `margin_by_layer`, avec
ce commentaire dans le code :

> 🔴 **NEEDED FOR RANKING**

**Elles portent sur la cause réelle de 83 % des échecs.** Le câblage dans le tri
(`use_margin_ranking`, off par défaut) a été fait le 16/08 ; le premier A/B en premium donne
**−2,6 % sur le 35c** — juste sous la résolution de 3,0 %, dans le bon sens, **non conclusif**.

---

## 8. ÉTAT AU 2026-08-18 — ce qui tourne

| batch | état |
|---|---|
| A/B `use_margin_ranking` en premium | **2 / 4 rendus**. 35c : OFF 0,498 → ON **0,4851 nm** (−2,6 %). 48c en cours |
| vague 2 en premium (`--vague 2 --hi 99`) | 20 intervalles de 60 à 79 couches, 10 shards. **Fin ~08:45** |

**La question ouverte que la vague 2 tranchera** : une architecture à **2 témoins** avec de
longues campagnes bat-elle les 0,782 nm à 4 témoins ? En vague 3, trois parts de ≥ 20 couches
sur 99 plafonnent à 59 chacune — les intervalles longs ne servent qu'aux partitions à
2 témoins, d'où cette campagne séparée.

**Caches de mesures :**

| dossier | contenu |
|---|---|
| `reports/intervalles_99c/` | **270** intervalles en **fast** — 🔴 **ne jamais écraser**, c'est la référence |
| `reports/intervalles_99c_premium/` | **250** en premium (+20 en cours) |
| `reports/controle_48c/`, `_35c/`, `_random75/` | contrôles négatifs |
| `reports/serie_echelle_r75/` | la série ×0,5 / ×1 / ×1,5 / ×2 |

---

## 9. Environnement — ce qui ne suit pas le dépôt

- **La mémoire de compte** (`<.claude>/projects/<projet>/memory/`, 9 fichiers) est **par
  compte et par machine**. Elle porte des pièges absents du dépôt.
- **Le `.venv`** est à reconstruire. 📌 Piège documenté : un venv de snapshot peut charger le
  code d'un **autre** snapshot. À vérifier avant toute mesure.
- **Le hook d'auto-push** vers le dépôt public n'est pas versionné : il n'existera pas
  ailleurs. Sur cette machine, **tout commit publie**.

**Avant toute mesure :**

```bash
export CERTUS_BENCH_TIMEOUT_S=5400
.venv/Scripts/python.exe scripts/preflight.py          # verdict GO / STOP
.venv/Scripts/python.exe scripts/check_claude_md.py    # coherence de la doc
```

**Après toute modification de code :**

```bash
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Référence au 16/08 : **2450 passed, 5 skipped**, `ruff` propre.

---

## 10. Comment 👤 veut qu'on travaille

- **Langage scientifique et rigoureux.** Pas de métaphore, pas d'anthropomorphisme, pas de
  rhétorique. **Observation et interprétation séparées.** Ce qui n'est pas mesuré s'écrit
  « non mesuré ».
- **« Rien ne remplacera les tests simulés. »** Toute proposition se valide par l'expérience
  numérique, jamais par l'argument seul.
- **Dire « changement de verre témoin »**, pas « coupure » — c'est plus précis, et c'est une
  correction explicite de 👤.
- **Un commit par action**, message détaillé qui porte le raisonnement et pas seulement le
  diff.
- **Quand une mesure contredit un document du projet, corriger le document** dans le même
  mouvement, en disant ce qui était faux.
