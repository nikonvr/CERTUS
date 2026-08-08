# Plan STRAT — ce qu'il reste à faire

> **Comment lire ce document.** Il est écrit pour être exécuté **sans rien deviner**.
> Chaque action donne : le **fichier et la fonction exacts**, ce qu'il faut **écrire**,
> la **commande de vérification** avec le résultat attendu, et les **pièges connus**.
> Si une instruction te paraît ambiguë, c'est un défaut de ce document — ne comble pas
> par une hypothèse, arrête-toi et demande.
>
> Il ne contient **que du travail à venir**. Ce qui est fait a été retiré : l'état du code
> se lit dans le code, et les mesures qui ont conduit aux correctifs sont dans
> `pages/CERTUS_STRAT.html`, la doc destinée à la communauté.

---

## 0. Avant toute chose — vérifier l'environnement (1 minute, obligatoire)

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
dir .git\hooks\post-commit*
```

- Le chemin affiché **doit** commencer par `C:\dev\gemini`. **Plusieurs copies de ce dépôt
  coexistent sur la machine.** Si le chemin pointe ailleurs, tu modifies un dossier et tu
  en mesures un autre : tout ce que tu constateras sera faux, sans le moindre message
  d'erreur. **Arrête-toi.**
- Le hook doit s'afficher comme `post-commit.DESACTIVE`. Sous ce nom il est inerte, donc
  committer ici **ne publie rien**. S'il apparaît sous le nom `post-commit` tout court,
  **ne committe pas** : il pousserait automatiquement vers le dépôt **public**
  `nikonvr/CERTUS`, et `git commit --no-verify` ne l'en empêche pas.

### Puis, avant la moindre modification : faire tourner la suite complète

C'est le **point de comparaison**. Sans lui, tu ne sauras jamais si un test rouge vient de
toi ou existait déjà.

```bat
.venv\Scripts\python.exe -m pytest tests/ -q --no-cov
```

Compte **1 h 45**. Lance-la et laisse-la finir — ne l'interromps pas, ne conclus pas d'un
résultat partiel. Le nombre attendu est celui inscrit dans **`docs/JOURNAL_GEMINI.md`,
section « État de départ »** : c'est le seul chiffre qui fasse foi, parce qu'il a été
mesuré sur cette copie-ci.

- ✅ 0 échec → note le chiffre dans `docs/JOURNAL_GEMINI.md` et continue.
- ❌ un ou plusieurs échecs **avant** que tu n'aies rien touché → **ARRÊTE-TOI et signale.**
  Ce n'est pas à toi de le réparer : cela veut dire que l'environnement n'est pas celui sur
  lequel les mesures de référence ont été faites.

**Commandes de référence** utilisées partout dans ce document :

| But | Commande |
|---|---|
| Tests rapides du noyau | `.venv\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov` |
| Suite complète (~1 h 45) | `.venv\Scripts\python.exe -m pytest tests/ -q --no-cov` |
| Lint | `.venv\Scripts\python.exe -m ruff check .` → doit dire `All checks passed!` |
| Run STRAT complet (~25 min) | `.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full` |
| Sonde noyau rapide (~1 min) | `.venv\Scripts\python.exe scripts\probe_anchor_noise.py` |

Toutes ces commandes se lancent depuis `C:\dev\gemini`, et **jamais** depuis un autre
dossier. Elles utilisent `.venv\Scripts\python.exe`, **jamais** `python` tout court : un
`python` nu prendrait l'interpréteur du système, qui n'a pas les dépendances.

---

## 1. Le cadre — trois phrases du physicien, qui gouvernent tout

> 👤 **La chaîne canonique.** *« 1. On simule un dépôt et la mesure de transmission
> bruitée. 2. On utilise le POEM comme méthode d'arrêt. 3. On teste statistiquement tout
> un ensemble de stratégies prometteuses. 4. On en déduit la meilleure stratégie. »*

> 👤 **Le juge.** *« Le juge de paix c'est toujours l'étude stochastique et statistique.
> Si 95 % des dépôts fonctionnent, c'est gagné. »*

> 👤 **L'objectif.** *« Le plus important est la cible spectrale respectée. »*

Cela définit **une grandeur unique** : la meilleure stratégie maximise
`P(le filtre sorti est conforme à la cible)`. Un dépôt qui plante et un filtre hors spec
sont **le même échec**. Conséquence : **la DP n'a plus à bien classer, elle doit bien
couvrir** — le tri est fait par la statistique.

**Le composant de référence, et le seul :** `example/example_strat/JSON-strat-example.json`,
un dichroïque passe-court de 48 couches, front à ~545 nm.

---

## 2. Point de référence — tout se compare à lui

Sans ce repère, aucune action ci-dessous n'est vérifiable. Obtenu par
`scripts\probe_anchor_noise_pipeline.py full`.

```
Configuration : poem_anchor_noise = 1, tp_hysteresis_factor = 1.66,
                phase_a_level_margin_factor = 1.66, dp_yield_weight = 0,
                scan_wl_step = 1.0

  RESULT                      0,002898
  RMSE global   med / p95     0,215 / 0,465   points de transmission
  bande passante p95          0,418
  front p95                   1,498
  plantage                    0,000     345 strategies rendues
  RUN_S                       ~1322 s
  gagnante                    2 blocs (544 et 531 nm)
```

⚠️ **Ce repère est celui du pas de 1 nm.** Une version antérieure de cette section citait
`RESULT = 0,005283` / 305 stratégies : c'était le run à **2 nm**, périmé par la décision du
§5bis. Ne pas comparer un chiffre de l'un à un chiffre de l'autre.

⚠️ **Le plafond du banc est à 1800 s en dur** (`scripts/bench_examples.py:155`,
`timeout_ms: int = 1_800_000`), non paramétrable. Au-delà, le banc ne signale pas d'erreur :
il rend **`RESULT=None`**, ce qui ressemble à un résultat. Les `RUN_S` ont monté de 1113 à
**1510 s** au fil des ajouts au pipeline — soit déjà 84 % du plafond. À surveiller avant
d'ajouter quoi que ce soit.

⚠️ **`RESULT` est le PIRE des trois niveaux de bruit** (0,5× / 1× / 2×), alors que les
lignes en dessous sont au niveau **nominal**. **Ne jamais comparer l'un à l'autre.**

⚠️ Ce classement juge l'écart au spectre **nominal, non pondéré** — décision du
physicien, §7.

---

## 3. Les quatre paramètres du modèle, et où les poser

Ils se posent **dans le fichier JSON de configuration**, à la racine de l'objet. Ils sont
lus par `collect_params` (`certus/ui/certus_strat_ui_state.py`) et acheminés jusqu'au
noyau. **Tous valent 0 / faux par défaut**, et à 0 le chemin de calcul est celui d'avant,
au bit près.

| Clé JSON | Type | Effet |
|---|---|---|
| `poem_anchor_noise` | `"1"` / `"0"` | Bruite le signal de monitoring **avant** la détection des points tournants, la lecture des ancres POEM et le test d'atteignabilité. Phase A **et** Phase B. |
| `tp_hysteresis_factor` | réel | Seuil de détection d'un point tournant, en **multiple de l'amplitude de bruit** `A = trigger_tolerance/100`. Vaut **1,66** aujourd'hui. 🔴 **Sous-dimensionné** : la borne anti-fabrication est 2A, et 👤 le « 5 σ » d'origine signifiait seulement « bien au-dessus du bruit », pas une exigence physique. Voir §5.2. Injectable au banc en 5ᵉ argument du script de sonde. |
| `phase_a_level_margin_factor` | réel | Marge exigée **en transmission** entre le niveau d'arrêt et les points tournants voisins, en multiple de `A`. Active aussi la vraie matrice cumulée en Phase A. |
| `dp_yield_weight` | réel | Poids du rendement dans l'objectif de la DP : `coût = coût_nm + w·(−log(1−p))`. |

**Exemple complet à coller dans le JSON :**

```json
"poem_anchor_noise": "1",
"tp_hysteresis_factor": "1.66",
"phase_a_level_margin_factor": "1.66",
"dp_yield_weight": "0"
```

⚠️ **Ne modifie PAS `example/example_strat/JSON-strat-example.json` pour faire un essai.**
Ce fichier s'est écarté des défauts du code **quatre fois**, toujours dans le sens
permissif, et chaque fois cela a coûté une session de diagnostic. Pour un essai, utilise
`scripts\probe_anchor_noise_pipeline.py`, qui injecte les paramètres **après coup** sans
toucher au fichier.

---

## 4. Les décisions qui bloquaient — une réglée, une ouverte

### 4.1 La cadence de lecture de l'OMS 5100 — ✅ **RÉPONDUE le 2026-08-08**

👤 Spécifications obtenues du physicien :

| Grandeur | Valeur | Conséquence |
|---|---|---|
| Rotation du plateau | **240 tr/min** | période 250 ms |
| Plateau ~1 m, témoin 20 mm au bord | | vitesse tangentielle **12,6 m/s**, **transit 1,6 ms** |
| Positions par tour | **3** : témoin, noir, vide | `T = (S − D)/(V − D)`, auto-référencé à 4 Hz |
| Vitesse de dépôt | ~0,5 nm/s | |
| **Cadence** | **4 Hz** — une lecture témoin par tour | **un échantillon tous les 0,125 nm** |
| Bruit de lecture | ±0,05 point, largeur totale 0,10 | 👤 le tirage du modèle est **correct**, ne pas y toucher |
| Le « 5 σ » | 👤 *« bien au-dessus du bruit »* | **pas une exigence physique** — voir 5.2 |

**Ce que ça donne, mesuré contre le modèle :**

| | Machine | Modèle actuel | Facteur |
|---|---|---|---|
| Pas spatial | 0,125 nm | 4,76 nm (`NPTS=64` sur `3×d_nom`) | **38× trop grossier** |
| Points par couche de 100 nm | 800 | 21 | |
| Historique, par couche relue | 800 | 16 (`NPTS_PREV`) | **50× trop grossier** |

La rotation **moyenne le dépôt** — c'est sa raison d'être — mais elle **échantillonne la
mesure** : chaque point rapporté est un passage, rien ne se moyenne.

🔴 **La grille ne peut PAS être raffinée seule** — voir 5.2. À seuil de détection inchangé,
la fabrication de faux points tournants passe de 33 % à 99,9 %.

### 4.2 Brancher ou non la règle de proximité aux points tournants — **toujours ouverte**

**L'état actuel** : dans `certus/utils/certus_strat_service.py`, fonction
`_select_candidates_phase_a`, le filtre `check_extrema_proximity_batch` reçoit
`M_befores = np.zeros((n_check, 2, 2))` — un placeholder. 📏 **Conséquence mesurée : la
règle interdit 0 candidate sur 51, sur les 48 couches.** Avec une matrice nulle tous les
dénominateurs du noyau tombent sous 1e-9, donc tous les `T` valent 0, donc aucune pente,
donc aucun test ne se déclenche.

**Le chemin correct existe** : mettre `phase_a_level_margin_factor > 0` branche la vraie
matrice cumulée (`nominal_matrix_cache`) **et** remplace le critère en épaisseur par le
critère en transmission.

**Pourquoi ça bloque** : cela change massivement la sélection de longueurs d'onde. C'est
un **arbitrage de physique**, pas une correction de code — le physicien doit trancher.

---

## 5. Ce qu'il reste à faire, dans l'ordre

> Les neuf actions précédentes (calibration `dp_yield_weight`, recherche locale, diversité,
> amorces structurées, successive halving, clés SYM, distorsion affine, `MachineModel`,
> σ(λ)) sont **exécutées**. Ce qu'il en reste d'ouvert est repris ci-dessous. Analyse
> détaillée de la fidélité physique : [`PROPOSITIONS_CLAUDE.md`](PROPOSITIONS_CLAUDE.md).

**Règle sur chacune** : paramètre inactif par défaut, chemin inactif **bit-identique** —
vérifié par empreinte `float.hex()`, pas « aux tests près ».

### 5.1 🔴 Rendre la distorsion affine atteignable, puis éprouver POEM

**Où on en est.** Le noyau est corrigé (`76f7a8f`) : il annulait son propre effet en trois
endroits, ce qui aurait fait conclure l'inverse de la vérité. 📏 Avant correction, `a = 0,9574`
déplaçait l'arrêt de **−6,60 nm** là où la théorie exige zéro ; après, l'invariance POEM
tient à **2,19e-10 nm** et le repli absolu devient sensible, rendant
`CRASH_LEVEL_UNREACHABLE` sous une chute de gain de 4,3 %.

**Ce qui manque.** Les paramètres ne sont dans la signature d'**aucun** appelant — ni
`validate_wavelengths_batch`, ni `simulate_stack_robustness_batch`. Le tirage n'existe pas.

**Ce qu'il faut faire.** Tirer `(a, b)` **une fois par run**, jamais par couche, en nombres
aléatoires communs : fonction pure de (graine, tirage), **sans aucune entrée de stratégie**.

**Critère de réussite** : mesurer plantage et erreur spectrale **avec et sans POEM** sous
distorsion. Si POEM tient sa promesse, l'écart doit être spectaculaire. Sinon, l'argument
central du mécanisme tombe et **il faut le dire**.

**Pourquoi en premier** : c'est la seule action qui peut **invalider POEM**. Tout le reste
le suppose valide.

### 5.2 🔴 Le seuil de détection est sous-dimensionné — et couplé à la grille

**Le constat.** Le docstring de `detect_turning_points` énonce sa propre condition de
suffisance : le tirage étant borné à ±A, l'écart maximal du bruit seul vaut 2A, donc
`hysteresis ≥ 2·trigger_tolerance/100` = **1,0e-3**. Or `certus_strat_robustness.py:854`
calcule `1,66 × 5e-4` = **8,3e-4**. **17 % sous la borne que le code énonce.**

📏 Mesuré — signal propre **plat**, bruit réel, 20 000 tirages, aucun TMM. Fraction des
couches où le bruit **fabrique** un point tournant :

```
hysteresis                      N=80 (modele actuel)      N=320      N=800 (cadence machine)
1.66 A  (configure)                          32.945%    92.995%                      99.935%
2.00 A  (borne du docstring)                  0.480%     7.660%                      30.525%
2.40 A                                        0.000%     0.000%                       0.000%

Controle Piege 1 : bruit x0.50 a N=800, seuil 1.66 A  ->  0.000%
```

Le résidu à 2,00 A **n'est pas physique** : c'est l'atome de probabilité à l'écrêtage ±1 du
tirage, où `maxv − v` vaut 2A à l'arrondi près et le `>` strict devient un pile ou face en
flottant. Prédiction du mécanisme à N=80 : 0,5 %. Mesuré : 0,48 %. **La borne « ≥ 2A » est
juste en arithmétique exacte et marginale en flottant : il faut strictement plus.**

**Le problème est à deux faces.** Trop bas, le bruit fabrique des extrema ; trop haut, le
détecteur rate les vrais extrema peu profonds. Seule la face gauche est chiffrée.

**Ce qu'il faut faire, dans cet ordre :**

1. Mesurer la face droite — à partir de quel facteur les *vrais* points tournants
   disparaissent. Bon marché, pas de pipeline.
2. Balayer `tp_hysteresis_factor` ∈ {1,66 ; 2,1 ; 2,2} au banc, **sans toucher au JSON** :

   ```bat
   .venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42 0 2.1
   ```

   Le 5ᵉ argument injecte le facteur après coup (ajouté le 2026-08-08, sur le modèle de
   `yield_weight`).

**Viser le plus BAS qui passe strictement au-dessus de 2A**, pas le plus haut.
`SWING_MIN = 0,04` exclut déjà les extrema peu profonds du chemin POEM, et 2,4 A = 1,2e-3
est 33× plus petit que `SWING_MIN` — la marge semble large, mais elle n'est pas mesurée.

⚠️ `phase_a_level_margin_factor` partage aujourd'hui la valeur 1,66 mais répond à un **autre
critère**. Ne pas le changer en même temps.

### 5.3 Méconnaissance d'indice δ_H, δ_L ≈ ±0,5 %

Biais **global constant par matériau** sur tout le run, pas un bruit couche à couche : il ne
se moyenne pas sur 48 couches.

📏 À l'oracle TMM indépendant, 6 couches, monitoring à niveau absolu : `eps = +0,005` produit
jusqu'à **2,4578 nm** d'erreur d'épaisseur. Le noyau actuel produit exactement **0**.

🔴 **Ne pas se contenter de pré-multiplier `n_H`/`n_L` au site d'appel.** Mesuré : 3,29e-10 nm
à δ=0,005, et **1,92e-10 nm à δ=0,05** — ×10 sur la perturbation ne change rien. Le même jeu
d'indices pilote l'empilement réel **et** l'empilement nominal ; les décaler ensemble ne crée
aucune divergence.

**Ce qu'il faut faire** : deux jeux d'indices dans la signature du noyau —
`n_*_real` pour l'empilement déposé, `n_*_nom` pour le signal attendu et le niveau figé.
Plus une décision explicite sur l'indice qu'utilise `compute_batch_rmse`.

### 5.4 Grille d'échantillonnage à la cadence machine — **avec 5.2, jamais seule**

Cible : `Δd = v_dépôt / f_échantillonnage` = 0,125 nm, soit ~800 points par couche de
100 nm contre 21 aujourd'hui.

🔴 **Deux pièges :**

1. `NPTS_PREV = ceil(d_real_j)` **casserait les nombres aléatoires communs** — `d_real_j`
   est l'épaisseur *obtenue*, donc dépendante de la stratégie. Indexer sur
   `p_thick_nominal[j]`, qui ne l'est pas.
2. Coût brut ×44 en évaluations TMM — rédhibitoire quand `REPRISE_PERF` conclut qu'il n'y a
   pas de ×2 disponible.

**La parade** : découpler la grille physique de la grille d'échantillonnage. `T(d)` est
lisse et parcourt moins d'une période sur tout le balayage — garder ~64 évaluations TMM
exactes, interpoler sur les positions réelles, et tirer **un bruit indépendant par
position**. Le nombre de tirages, qui gouverne les extrema parasites, devient fidèle à coût
TMM inchangé.

### 5.5 Quantification temporelle du déclenchement — `U(0, 0,125 nm)`

Le volet ne peut pas se déclencher avant le franchissement : la loi est **strictement
positive**, jamais centrée. Pas de double comptage avec `noise_val_precalc`, qui est un
bruit **photométrique** (en T) là où celui-ci est **spatial** (en d).

**Quasi gratuit une fois 5.4 fait** : si la grille de balayage est celle de la machine, on
s'arrête au premier point au-delà du seuil au lieu d'interpoler, et la quantification est
automatique.

### 5.6 Facteur de face arrière sur les seuils absolus — **en dernier, ou jamais**

`T_back = 4n/(n+1)² ≈ 0,957` pour BK7, soit 4,4 %. Le chemin de **notation** applique déjà
la face arrière complète avec réflexions multiples (`certus_strat_batch.py:310-316`) :
l'écart ne concerne que le signal de monitoring, et vaut 0,002 en absolu sur `SWING_MIN`.

---

## 6. 🔴 La validation externe — elle n'a plus qu'un seul chemin

**Aujourd'hui STRAT n'est validé que contre lui-même.** Tout ce qui précède le rendra plus
cohérent ; **rien ne prouvera qu'il dit vrai.**

👤 **Deux décisions du 2026-08-06 ferment les portes de substitution** : *« seul le
48 couches est un exemple valable »* et *« oublie aussi la séparatrice, ce n'est pas
pertinent »*. Le témoin publié envisagé — une séparatrice 8 couches déposée quatre fois,
au classement connu — est **retiré**.

> **Il ne reste qu'un chemin : des dépôts réels du dichroïque 48 couches.**
> Au moins **deux** stratégies réellement déposées, avec leurs spectres mesurés. Deux
> suffisent, parce que le test décisif est **ordinal** — STRAT doit les classer dans le
> bon ordre. C'est bien moins exigeant qu'une correspondance absolue, et bien plus probant
> qu'un accord avec soi-même.

⚠️ **Tant qu'on ne les a pas, nommer les choses correctement** : le dichroïque est un
**banc de cohérence**, pas un juge externe. Aucun chiffre de ce document ne doit être
présenté comme une validation physique.

### 6.1 Les garde-fous automatiques — ✅ **en place**

`tests/oracle/test_example_strat_guardrails.py` (3 tests) verrouille l'anti-dérive du
fichier de référence et la sanité spectrale du dichroïque ;
`tests/oracle/test_lint_debt_ratchet.py` interdit d'agrandir `extend-ignore` ;
`tests/oracle/test_numba_contract_oracle.py` empêche la perte silencieuse de compilation
JIT ; `tests/oracle/test_gradient_analytic_oracle.py` (3 tests) compare les gradients
analytiques aux différences finies.

Valeurs verrouillées dans le fichier de référence — **quatre fois** il s'en est écarté,
toujours dans le sens permissif :

| Clé | Valeur | Pourquoi |
|---|---|---|
| `scan_wl_step` | `"1.0"` | tranché par deux simulations complètes — voir §5bis |
| `wl_step` | `"1.0"` | grille d'affichage |
| `trigger_tolerance` | `"0.05"` | au-delà, le bruit injecté est ×10 |
| `execution_mode` | `"premium"` | `fast` divise les budgets par 4 |
| `wavelength_change_penalty` | `"1.2"` | |

⚠️ **Ce qui manque encore** : un oracle du noyau de croissance, comparant la racine du fit
parabolique (`_solve_quadratic_target`) à la racine **exacte** de `T(d)` obtenue par
balayage fin, seuil 0,05 nm. `tests/oracle/` le fait pour le TMM ; le monitoring n'a pas
son équivalent.

---

## 5bis. La grille de balayage — **question tranchée, ne la rouvre pas**

`scan_wl_step` est le pas entre deux longueurs d'onde de contrôle candidates. La machine du
physicien sait se positionner au nanomètre, donc 1 nm est réalisable.

Deux simulations complètes indépendantes, **plage identique des deux côtés**, seul le pas
changeant :

| graine | pas 1 nm | pas 2 nm | verdict |
|---|---|---|---|
| principale | **0,002898** | 0,005283 | 1 nm meilleur, ÷1,82 |
| 77 | **0,003553** | 0,008400 | 1 nm meilleur, ÷2,36 |

Deux graines, même sens, marge plus large à la seconde. Le pas de **1 nm** est retenu et
inscrit dans le fichier de référence. Il coûte **+9 % de temps** et rend une stratégie
gagnante à **2 blocs au lieu de 4** — donc moins de changements de λ à exécuter.

> ⚠️ **La prédiction inverse avait été avancée** — qu'une grille plus fine gaspillerait le
> budget en candidates redondantes. La mesure l'a réfutée. C'est un rappel de la règle du
> §7 : **on ne prédit pas un résultat de simulation, on le mesure.**

> ⚠️ **Effet de bord.** `wl_step` valant déjà 1 nm, les deux grilles coïncident maintenant.
> Le bug de confusion entre elles devient **invisible** sans avoir disparu. **Ne supprime
> pas `_resolve_monitoring_wavelength_grid`** au motif que les grilles sont identiques.

---

## 7. Les règles gravées — elles gouvernent tout ce qui précède

### 👤 L'admissibilité d'une longueur d'onde de contrôle

> *« Une longueur d'onde de contrôle de la couche i (i > 1) est **interdite** si, lorsque
> le signal est bruité, il y a un risque de mal comptabiliser le nombre de turning points
> ou de ne pas s'arrêter au niveau de transmission voulu. Cela crée une erreur d'arrêt de
> couche. »* — *« Tout cela est valable **en phase A comme en phase B**. »*

**Un seul énoncé physique, donc un seul drapeau pour les deux étages.** Et la marge de
sécurité qui en découle s'exprime **en transmission**, jamais en nanomètres : près d'un
point tournant `T ≈ T_ext − c·(d−d₀)²`, donc une marge fixe en épaisseur correspond à une
fraction d'amplitude non contrôlée.

### 👤 Les longueurs d'onde de contrôle se choisissent sur la grille de balayage — **aujourd'hui au pas de 1 nm**

**En longueur d'onde, pas en épaisseur.** La grille est
`arange_inclusive(scan_wl_min, scan_wl_max, scan_wl_step)`, servie par
`_resolve_monitoring_wavelength_grid` (`certus/core/certus_strat_ranking.py`).

Ce qui est **gravé**, c'est que les λ candidates doivent tomber sur une grille régulière
que la machine sait réellement atteindre — jamais sur une grille d'affichage, jamais sur
une grille implicite. La **valeur** du pas, elle, se mesure : elle a valu 2 nm, puis
👤 *« la machine sait positionner 1 nm »*, et la simulation a confirmé que 1 nm est
meilleur (§5bis). Elle vaut donc **1 nm** et n'a plus vocation à bouger.

🔴 **Ne JAMAIS la déduire des clés de `clues_at_wl`.** Ce dictionnaire porte l'**union**
de la grille de balayage et de la grille d'affichage (`wl_range` / `wl_step`), donc un pas
plus fin sur tout le recouvrement **et un débordement hors de la plage de balayage**.

⚠️ Les deux pas valant aujourd'hui 1 nm, cette union est devenue indistinguable de la
grille de balayage — **le défaut est masqué, pas corrigé**. C'est exactement le genre de
situation où l'on supprime un correctif « devenu inutile » et où le bug revient un an plus
tard. `_resolve_monitoring_wavelength_grid` **reste nécessaire**.

### 👤 La cible spectrale reste NON PONDÉRÉE jusqu'à nouvel ordre

> *« La cible spectrale restera non pondérée jusqu'à nouvel ordre. »* (2026-08-06)

Le mécanisme existe et il est testé : `compute_batch_rmse` accepte un vecteur de poids, et
la Phase B sait construire cible et poids depuis des zones `{lmin, lmax, tmin, tmax, w}`
via `prepare_targets_vectorized` — la fonctionnelle que DESIGN minimise déjà. **Il est
délibérément inutilisé.** Sans clé `targets`, le classement porte sur l'écart au spectre
**nominal**, non pondéré, chemin de calcul identique au bit près.

⚠️ **La conséquence, dite une fois et sans y revenir.** 📏 Les deux bandes du juge de paix
font **exactement la même largeur — 141 points chacune sur 301**. Un RMSE uniforme est donc
*littéralement incapable* de distinguer une stratégie qui rate la bande bloquée d'une
stratégie qui rate la bande passante : les deux scores sont égaux **à la précision
machine**. Ce n'est pas un manque de sensibilité, c'est une **indifférence exacte**, alors
que l'exigence diffère d'un facteur ~500. Et le score reste dominé par le **décalage du
front**, que personne n'a demandé.

**C'est un choix assumé, pas un oubli.** Le jour où il change : ajouter les zones dans le
JSON, aucun code à écrire, aucun drapeau à lever.

### 👤 Les heuristiques de la littérature sont des diagnostics, pas des filtres

> *« Le 4 %, pour moi, c'était au pif, pour être certain qu'on va y arriver. Alors que là,
> nous on travaille sur de vrais signaux simulés grâce au bruit introduit. »*

15–85 %, amplitude de départ ≥ 4 %, swing in / swing out : **à conserver comme colonnes
explicatives**, jamais comme couperets.

⚠️ **Ne pas confondre avec la règle de détection** (`tp_hysteresis_factor`) : celle-ci ne
présélectionne pas, elle décrit comment la machine **lit**, et son seuil se **dérive** du
bruit mesuré au lieu de se deviner.

### 🟢 La règle de méthode, payée trois fois

> **Une grandeur de bruit qui ne varie pas avec le bruit est un artefact. Sans exception.**

La question à poser d'abord n'est pas *« quel est le chiffre ? »* mais *« ce chiffre
dépend-il de ce dont il devrait dépendre ? »* Balayer σ sur quatre ordres de grandeur
coûte quelques secondes.

**Trois corollaires, chacun payé au moins une fois :**

1. **Vérifier sur quelle SOURCE un critère se prononce.** Les défauts les plus coûteux
   étaient de cette forme : le signal *propre* au lieu du signal bruité · la grille
   d'*affichage* au lieu de la grille de balayage · une matrice de *zéros* au lieu de
   l'empilement réel.
2. **Ne jamais confondre deux causes sous une même sentinelle.** Trois modes de
   défaillance rendaient la même valeur ; le diagnostic était impossible jusqu'à ce qu'on
   les sépare — et il a alors tenu en **une** mesure.
3. **Une signature qui ne varie pas avec la profondeur, l'amplitude ou la graine désigne
   l'algorithme, pas le phénomène.**

---

## 8. Ce qu'il ne faut PAS faire

- **Chercher un coût prédictif par `sᵀΣs`** — réfuté par la mesure : ni les sensibilités
  spectrales (+0,589 contre +0,590) ni la covariance (+0,643) n'apportent rien.
- **Réparer l'estimation du coût en nanomètres de la Phase A.** 👤 *« En partie B on se
  branle de l'erreur d'épaisseur, seul l'écart spectral final compte. »*
- **Rendre les « points tournants virtuels » utilisables comme ancres POEM.** Un point
  tournant virtuel est une extrapolation — **la machine ne l'a pas mesuré**, elle ne peut
  pas s'y recaler.
- **Rétablir un front de Pareto** — `P(conforme)` est un scalaire.
- **Une recherche en faisceau avec *rollout*** — générer largement puis départager par la
  statistique suffit, à condition que la génération vise la couverture.
- **Toucher au cap de 10 λ par bloc** — traité par la séparation spectrale.
- **Activer SYM sans recalibrer `sym_weight`** — le terme n'a jamais tourné.
- **Conclure d'un écart d'épaisseur sous 0,05 nm** (c'est moins d'un atome), **d'un écart
  de λ sous le pas de grille**, ou **proposer une λ de contrôle hors de la grille de
  balayage**.
- **Réintroduire un mode dégradé.** 👤 *« Interdit le mode fast. »*
- **Citer les repères « 0,4 nm / 0,3 nm »** — absents de la thèse Zideluns.
- **Tirer une conclusion physique d'un empilement autre que le 48 couches.** Les
  empilements jouets des tests servent aux mécanismes, pas à la physique.
- **Traiter une note de reprise comme une mesure sans la refaire ici.** Le dépôt a
  plusieurs snapshots ; une note écrite depuis un autre arbre peut décrire du code qui
  n'existe pas dans celui-ci.
