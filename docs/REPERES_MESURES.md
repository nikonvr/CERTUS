# 21. Points de référence — les repères valides, et ce qui les périme

> Extrait de `CLAUDE.md` le 2026-09-08. Ce contenu **fait autorite** ;
> `CLAUDE.md` n'en garde qu'un renvoi. 🔑 **Un fait, un seul endroit** — si tu corriges
> quelque chose ici, ne le recopie pas ailleurs, mets un lien.

---


🟢 **LES REPÈRES EXISTENT DEPUIS LE 2026-08-15.** Les voici, tous mesurés **fente
2 nm**, donc sous le modèle courant. Ce sont eux qu'on cite, et aucun autre.

| composant | couches | SEEL | plantage | condition |
|---|---|---|---|---|
| dichroïque `JSON-strat-example` | 48 | **0,173 nm** | 0 % | 6 blocs, une seule campagne |
| passe-bande 3 cavités `JSON-strat-bandpass-3cav` | 35 | **0,482 nm** | 0 % | 6 blocs, mode DEEP |
| **aléatoire** `JSON-strat-random75` | 75 | **0,272 nm** | 0 % | une seule campagne, 241/662 déposables |
| passe-bande 5 cavités `JSON-strat-bandpass-5cav-99c` | 99 | **0,81 nm** | 0 % par campagne | 🔴 **4 verres témoins** — 0-22 / 22-42 / 42-76 / 76-99 · ⚠️ moyenne de **trois graines** (0,782 / 0,816 / 0,839) ; ne cite jamais le 0,782 seul |
| le même, **en une seule campagne** | 99 | *aucun score valide* | **100 %** sur 487 stratégies | non fabricable — §23.8 |
| **aléatoire ×2** `JSON-strat-random75-x2-fabricable` | 75 | **0,6248 nm** | 0 % | épaisseurs **doublées**, fente **native 1 nm**, pur optique, 277 déposables |
| le même **à 2 nm**, config livrée | 75 | **0,5676 nm** | 1,67 % | 🔴 **AVEC les rampes** de `example/example_strat/rampes_r75x2-2nm.json`. 3 graines : 0,5676 / 0,5692 / 0,5707, étendue 0,55 %. Ce n'est **pas** une découverte autonome |
| le même **à 2 nm, SANS rampes** | 75 | *aucun score valide* | **100 %** | 🔴 **3 graines nues sur 4 rendent ZÉRO** (42, 101, 202) ; seule la 77 trouve, 547 déposables. §33 de [`PLAN_PRODUCTION_2026-08-20.md`](docs/PLAN_PRODUCTION_2026-08-20.md) |

🔑 **Lis la troisième et la quatrième ligne ensemble : 75 couches passent, 99 non.** Ce n'est
donc **pas la longueur** qui met le monitoring optique en échec, c'est la **structure**. Le
random75 n'a ni cavité ni miroir, le 99c a cinq cavités et des miroirs de 19 couches.
Voir §23.4.

⚠️ **Cette ligne disait « cinq espaceurs à swing nul et des miroirs sous 10⁻⁴ » — c'est
réfuté.** Mesuré le 2026-08-15 : les cinq espaceurs offrent **65 à 133 λ utilisables** chacun,
et **aucune des 99 couches n'est muette**. Le swing crête-à-crête d'une demi-onde n'est pas
nul ; c'est son écart début-fin qui l'est, et ce n'est pas la même grandeur. Ce qui met le
99c en échec est la **marge** du sursaut face à l'hystérésis, pas l'absence de signal.

#### 🔴🔴 LA SÉRIE D'ÉCHELLE DU RANDOM75 MESURAIT LA RECHERCHE, PAS LA PHYSIQUE — 2026-08-18

📌 **Le dossier fait autorité : [`CHANTIER_PREDICTIBILITE.md`](docs/CHANTIER_PREDICTIBILITE.md)
§4quater et §4quinquies.** Ce qu'il faut retenir sans l'ouvrir :

| Σ QWOT | variante | offertes | déposables | `crash_min` | SEEL |
|---|---|---|---|---|---|
| 57,4 | ×0,5 | 375 | 0 | 48 % | — |
| 114,9 | ×1 | 662 | 241 | 0 % | 0,272 nm |
| 172,3 | ×1,5 | 440 | 1 | 0 % | 0,633 nm |
| 201,1 | **×1,75** | 746 | **282** | 0 % | **0,528 nm** |
| 229,8 | ×2 | 404 | 0 | **100 %** | — |
| 229,8 | ×2 **en `deep`, fente 1 nm** | 1 986 | **277** | **1,0 %** | **0,625 nm** |
| 229,8 | le même **en `extreme`** | 2 945 | 254 | 1,0 % | 0,629 nm ⚠️ *ce tableau ne portait QUE cette ligne, et créditait donc `extreme` d'un déblocage que **`deep` seul fait mieux, à un cinquième du coût*** |

🔑 **Deux faits, et ils changent la lecture de tout ce chantier :**

1. **`×1,75` est PLUS ÉPAIS que `×1,5` et rend 282 déposables contre 1.** Il n'y a pas de loi
   « plus c'est épais, plus c'est dur ».
2. 📏 Sur les cinq points au **même protocole**, la corrélation de rang avec le nombre de
   déposables vaut **+0,103 pour Σ QWOT** — la propriété du design — et **+0,975 pour le nombre
   de stratégies OFFERTES** par la recherche. Et la flèche causale est établie : **même design,
   même graine, même fente**, seule la largeur de recherche change, et ×2 passe de **0/404** à
   **254/2 945**.

🔴 **Donc un `crash_min = 100 %` ne dit PAS, à lui seul, « ce composant n'est pas
monitorable ».** Il peut dire « ma recherche n'a pas proposé ce qui marche », et **rien dans la
sortie ne distingue les deux**. C'est le défaut §24-37 dans l'autre sens, et il a fait croire
trois jours durant que ×2 était impossible.

🔑 **MAIS LA RÉCIPROQUE EST FAUSSE AUSSI, et elle a été mesurée le 2026-08-19 au soir.** Un
`100 %` qui **résiste à la profondeur** dit, lui, quelque chose de réel : sur `r75x2` à 2 nm,
`fast` (404), `premium` (651) et `deep` (**1 617** stratégies) rendent **tous les trois 0
déposable et 100 %**. **À cette fente, ce n'est plus la recherche qui manque.** La bonne règle
est donc : *un `100 %` en `fast` ne conclut rien ; un `100 %` qui tient jusqu'à `deep` est un
constat sur le composant et sa fente.*

⚠️ **L'offre ne suffit pas pour autant, et la mesure du 2026-08-19 au soir le tranche.**
Cette ligne disait *« il a fallu la fente fine ET l'élargissement »* : **c'est l'élargissement
qui est de trop**. 📏 À **2 nm**, la recherche a été poussée jusqu'à `deep` — **1 617
stratégies, 0 déposable, 100 % de plantage** — donc quadrupler l'offre (404 → 1 617) ne change
**rien**. Et à **1 nm**, `deep` **seul** rend 277 déposables. **Il a donc fallu la FENTE FINE
et la PROFONDEUR**, pas l'élargissement.

#### 🟠 CES QUATRE SEEL NE VIVENT PAS SUR LE MÊME DOMAINE SPECTRAL — constaté le 2026-08-15

👤 : *« on reste comme cela, mais c'est à noter dans un coin »*. C'est donc **un état de fait
assumé, pas un défaut à corriger** — mais il faut le savoir avant de lire le tableau ci-dessus
comme un classement de difficulté.

| composant | grille de notation | largeur | points |
|---|---|---|---|
| 48c dichroïque | 400 – 700 nm | **300 nm** | 301 |
| 75c aléatoire | 550 – 750 nm | **200 nm** | 201 |
| 35c passe-bande | 600 – 660 nm | **60 nm** | 61 |
| 99c passe-bande | 610 – 655 nm | **45 nm** | 91 (pas de 0,5 nm) |

**Les deux passe-bandes sont déjà notés en zone réduite** — leur configuration resserre la
plage autour de la bande. Les deux autres sont notés large. Donc l'ordre
`0,173 < 0,272 < 0,482 < 0,81` mélange **deux effets** : la difficulté intrinsèque du
composant, **et** la largeur de la fenêtre où l'erreur est regardée. Une bande étroite autour
d'une résonance concentre le score là où le filtre est le plus sensible ; une grille large
dilue la même erreur dans des zones plates.

🔑 **Ce qui reste parfaitement valide malgré ça** : toute comparaison **à composant fixé** —
c'est-à-dire tout ce que fait la campagne du 2026-08-15, où seule la position du changement de
témoin varie sur une grille inchangée. L'avertissement ne porte que sur les comparaisons
**d'un composant à l'autre**.

**Comment c'est calculé, exactement.** Deux grilles à ne pas confondre :

| paramètre | rôle |
|---|---|
| `wl_range_start` → `wl_range_end`, pas `wl_step` | la grille de **notation** : c'est sur elle que RMSE et SEEL sont calculés |
| `scan_wl_min` → `scan_wl_max` | la grille de **balayage** : les λ de contrôle candidates. Aucun effet sur le score |

La pondération spectrale **existe** (`compute_batch_rmse`, argument `weights`,
`certus_strat_batch.py:554`) : on déclare des zones via `params["targets"]`, chaque point reçoit
`poids utilisateur × quadrature en d ln λ`, et **un point hors de toute zone reçoit un poids
nul** — il ne compte même pas au dénominateur. 🔴 **Mais aucune des quatre configurations ne
définit `targets`**, donc le code retombe sur son repli documenté `rank_weights = None` :
**pondération UNIFORME sur toute la grille**. Le mécanisme est écrit et testé, il n'a
simplement jamais servi sur ces composants.

📌 **Si un jour on veut une zone (par exemple 550-650 nm)** : passer par `targets`, pas par
`wl_range`. Changer `wl_range` déplacerait aussi la cible nominale et rendrait tout
incomparable avec les mesures existantes ; `targets` pondère sans changer la grille.

⚠️ **Le 0,86 nm des anciens rapports sur le 99c est un score de repli, pas une performance**
— il est rendu quand aucune stratégie ne survit à la porte de plantage. Comparer deux configurations sur des scores de repli revient à comparer
deux façons d'échouer. Voir §23.8.

🔴 **Ce qui PÉRIME un repère.** Le **biais de fente** est actif par défaut depuis le
2026-08-11 (§30). Tout `RESULT` mesuré **avant** cette date décrit une machine à fentes
**infiniment fines**, qui n'existe pas. Ce ne sont pas des chiffres faux : ce sont les
**réponses à une autre question**.

**Sont donc périmés, et il ne faut plus les citer** : l'ancien `D0.ref`
`0.0027329534107462224`, la courbe de corridor, la protection POEM ×41,2, la position de la
falaise, et toute statistique par bande antérieure.

⚠️ **`RESULT` agrège les trois niveaux de bruit** (0,5× / 1× / 2×). Il est donc comparable
aux **scores** du classement, et **jamais** aux statistiques **par bande**, qui sont au niveau
nominal seul. `RESULT` **est** le `robustness_score` de la gagnante.

🔴 **Et un `RESULT` seul ne départage rien.** §24-26 l'a mesuré : à N = 150, la dispersion
Monte-Carlo vaut σ ≈ 6 % et l'écart entre la 1ʳᵉ et la 2ᵉ vaut 0,8 σ. **Deux runs qui
diffèrent de moins de ~8 % sont indiscernables.** Ce qui compare deux configurations, c'est
la **classe d'équivalence SEEL** (§22), pas le score.

**Ce qu'il faut faire avant toute mesure au banc :**

```bat
set CERTUS_BENCH_TIMEOUT_S=38400
python scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

Le plafond était en dur ; il est surchargeable par cette variable, **défaut 1800 s**
(`scripts/bench_examples.py:171` — `DEFAULT_TIMEOUT_MS = CERTUS_BENCH_TIMEOUT_S × 1000`).

### 🔴 5400 EST UN PLANCHER, PAS UNE VALEUR — et cette ligne a coûté une nuit entière

⚠️ **Ce paragraphe disait « Mets 5400 et laisse finir », sans dire sur QUELLE CHARGE.** C'était
une durée sans sa machine ni son composant, ce que §11-1 interdit — et le 2026-08-22 elle a
détruit **quatre mesures de 90 minutes** :

```
nu_s101  91 min · nu_s202  91 min · livree_s101  90 min · livree_s202  90 min
         ^^^^^^ quatre fois EXACTEMENT 5400 s

verdicts : SURCHARGES_NON_APPLIQUEES x3 · ECHEC_RESULT_NONE x1
empreinte : « WAIT_TIMEOUT=5400 s — aucune emission recue »
```

📏 Elles avaient pourtant fait **13 à 16 nombres de blocs sur 16** : le travail était presque
fini quand le plafond l'a tranché. Un run pleine plage sur `r75x2` à 2 nm prend **2 h 39 =
9540 s** (mesuré le 2026-08-21).

🔑 **LA RÈGLE, celle que les pilotes du dépôt appliquent depuis toujours** —
`batch_nuit_2026-08-19.py:115`, `batch_nuit_2026-08-20.py:137`, `batch_diagnostic_elite.py:164` :

```
CERTUS_BENCH_TIMEOUT_S = max(5400, 4 x duree_attendue_en_secondes)
```

**Quatre fois la durée attendue, avec 5400 pour plancher.** Le facteur 4 n'est pas décoratif :
une graine défavorable peut doubler le nombre de survivants au criblage, donc la durée.

### ⚠️ Le piège, et il a maintenant fonctionné trois fois

Au-delà du plafond le banc ne signale pas d'erreur bruyamment. Il émet `RESULT=None` et un
tableau de 12 stratégies au lieu de 345 — **cela ressemble à un résultat**. Vérifie toujours
`WAIT_EXIT` et le nombre de stratégies avant de lire un `RESULT`.

🔑 **Et cherche `WAIT_TIMEOUT=` dans le journal : c'est l'empreinte, elle est sans ambiguïté.**
Une durée qui vaut *exactement* le plafond pour plusieurs mesures d'affilée l'est aussi — une
coïncidence à la seconde près n'existe pas.

⚠️ **Une mesure, une machine.** Ne lance rien d'autre pendant un run : ni tests, ni lint, ni
recherche récursive. Le pipeline sature tous les cœurs en `prange`.

**Suite de tests, mesurée sur cette copie le 2026-08-08** :

```
pytest tests/oracle/ tests/unit/ -q --no-cov  ->  0 failed
ruff check .                                  ->  All checks passed!
```

⚠️ Des documents supprimés annonçaient 2300 et 2301, avec la **même durée au centième**
(`87.60s`) dans cinq entrées différentes. Ces lignes n'avaient pas été mesurées.

🔴 **Et la phrase qui suivait était fausse : elle disait « la référence est 2310 », six
lignes après un bloc annonçant 2450 pour la même commande.** Deux chiffres contradictoires
dans la même section.

🔑 **La leçon a été tirée le 2026-08-19, et elle est plus forte que la correction** : ce
document a porté **2 300, 2 301, 2 310 puis 2 450** pour la même commande, et **chacun a été
faux à son tour**. Ce n'est pas une suite d'inattentions — c'est qu'**un compte de tests se
périme dès qu'on ajoute un test**, donc dès qu'on travaille. 📏 Le 2026-08-19 il valait
**2 453** puis **2 456** dans la même journée. **Le chiffre est retiré au profit du seul
critère qui survive : `0 failed`.** Voir §2.

⚠️ **Une durée sans sa machine ne vaut rien.** Le bloc ci-dessus portait un `101.24s` qui
n'est reproductible **sur aucune machine connue du projet** : la même commande rend **216,69 s**
sur i5-8250U à cache chaud (mesuré le 2026-08-19) et **784 s** à cache froid. La durée a été
retirée du bloc plutôt que corrigée — c'est le critère `0 failed` qui compte, et une durée
n'a de sens qu'accompagnée du processeur, du cache et de la charge.
