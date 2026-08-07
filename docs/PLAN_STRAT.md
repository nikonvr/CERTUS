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
                phase_a_level_margin_factor = 1.66, dp_yield_weight = 0

  RESULT                      0,005283
  RMSE global   med / p95     0,235 / 0,481   points de transmission
  bande passante p95          0,570
  front p95                   1,025
  bande bloquee p95           0,0006
  decalage du front p95       0,00 nm  (sous le pas de grille de 1 nm)
  plantage                    0,000     305 strategies rendues, 0 repechee
  RUN_S                       ~1430 s
```

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
| `tp_hysteresis_factor` | réel | Seuil de détection d'un point tournant, en **multiple de l'amplitude de bruit** `A = trigger_tolerance/100`. 👤 « environ 5 sigmas » ⇒ **1,66** (car σ = 0,332·A). |
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

## 4. 🔴 Les deux décisions qui bloquent — elles ne sont pas du code

**Ne code rien qui en dépende avant d'avoir la réponse du physicien.**

### 4.1 La cadence de lecture de l'OMS 5100

**Ce qui est acquis** : 👤 le seuil de détection est *« un seuil d'amplitude, à environ
5 sigmas du bruit »*.

**Ce qui manque** : combien de mesures la machine prend-elle pendant le dépôt d'**une
couche** ? Une par seconde ? par dixième de seconde ? combien de secondes par couche ?

**Pourquoi ça bloque** : le modèle échantillonne le signal sur **64 points répartis sur
3× l'épaisseur nominale** (`certus/physics/certus_strat_growth.py`, constantes `NPTS` et
`D_SCAN` dans `simulate_growth_kernel`), soit ~21 points par épaisseur nominale. **C'est
un choix numérique, pas la machine.** Le nombre d'extrema parasites qu'un bruit fabrique
dépend directement de cette densité. Tant qu'elle n'est pas calée sur la vraie cadence,
tout taux de plantage garde un paramètre libre.

### 4.2 Brancher ou non la règle de proximité aux points tournants

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

### 5.1 Calibrer `dp_yield_weight` — balayage, ~4 runs

**Ce qui existe déjà.** `certus/core/certus_strat_ranking.py` fournit
`build_yield_cost_map(raw_results)` qui rend `{couche: {λ: −log(1−p)}}`, et
`combine_cost_and_yield(cost_map, yield_map, w)` qui rend `coût_nm + w·(−log(1−p))`. Le
branchement est dans `certus/workers/certus_strat_workers_pipeline.py`, juste après la
construction de `cost_map_sq_clean`.

**Ce qu'il faut faire.**

1. Lancer un run par valeur de `w` ∈ {0, 50, 200, 1000}. Pour chacun :
   ```bat
   .venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full
   ```
   en ayant d'abord ajouté `params["dp_yield_weight"] = <w>` dans la fonction `patched`
   de `scripts\probe_anchor_noise_pipeline.py` (fonction `patch_flag`), ou en passant par
   une clé JSON dans une **copie** de la configuration.
2. Relever pour chaque `w` : `RESULT`, le RMSE médian et p95, le plantage médian, et le
   nombre de stratégies rendues.
3. Rendre un tableau `w → (RESULT, plantage, RMSE)`.

**Repère de calibration.** À la tolérance de 0,107 % par couche, `−log(1−p)` vaut
1,07·10⁻³ nat. Pour que ce plantage pèse autant que 0,2 nm — l'ordre de grandeur du coût
médian mesuré — il faut `w ≈ 200`. **C'est un repère, pas une réponse : la mesure
tranche.**

**Critère de réussite** : une valeur de `w` pour laquelle `RESULT` ne se dégrade pas et
le plantage médian baisse, ou bien la démonstration que le rendement n'apporte rien à ce
composant.

**Piège n° 1.** 📏 Sur le juge de paix, la **meilleure λ de chacune des 47 couches a un
taux de plantage NUL**. La carte de rendement est donc **plate sur les meilleurs
chemins** : n'attends pas un grand effet, et si `RESULT` ne bouge pas, c'est un résultat,
pas un échec.

**Piège n° 2.** `p` est estimé sur `num_runs` tirages, donc le plus petit taux non nul
mesurable vaut `1/num_runs`. En dessous, la carte vaut exactement 0.

**Réserve à instruire, pas à supposer** : l'indépendance entre couches est approximative —
celles d'un même bloc partagent l'historique de points tournants. À mesurer.

---

### 5.2 🔴 La recherche locale sur `P(conforme)` — le vrai levier, entièrement absent

👤 *« J'ai tout mon temps. »* Le Monte-Carlo est le juge et le budget n'est pas contraint :
**le meilleur générateur n'est pas un générateur, c'est une recherche locale.**

**Où l'écrire.** `certus/core/certus_strat_consensus.py`, à côté de
`_apply_elite_refinement_if_enabled`. Ne pas toucher à la DP.

**Algorithme, précisément.**

1. Partir des `k` meilleures stratégies du classement courant (`strategies_results[:k]`).
2. Pour chacune, engendrer les perturbations suivantes — **une seule modification à la
   fois** :
   - déplacer une frontière de bloc de ±1 couche ;
   - remplacer la λ d'un bloc par une λ voisine **de la grille de balayage** (obtenue par
     `_resolve_monitoring_wavelength_grid`, jamais par les clés de `clues_at_wl`) ;
   - fusionner deux blocs adjacents ;
   - scinder un bloc en deux.
3. Évaluer **chaque** perturbation par le Monte-Carlo complet
   (`_test_strategy_robustness_task`), pas par un coût approché.
4. Garder la meilleure ; recommencer tant qu'une perturbation améliore.
5. S'arrêter sur : plus aucune amélioration, ou budget épuisé.

**Ce qui la distingue d'`ELITE`** : ELITE mute puis **classe sur le mauvais critère**, et
son budget est réparti à l'avance. Ici, chaque perturbation est jugée sur la grandeur
finale, et le budget suit le gradient.

**Critère de réussite** : sur le juge de paix, un `RESULT` strictement meilleur que
0,005283 à configuration de modèle identique.

**Piège.** Le coût est le Monte-Carlo complet : ~2 s par stratégie à 150 tirages.
Une passe de 10 parents × 20 perturbations = 200 évaluations ≈ 7 min. **C'est acceptable,
mais compte-le avant de lancer 5 tours.**

---

### 5.3 De la diversité explicite dans la génération

**Le problème** : les `k` meilleurs chemins d'une DP sont des **quasi-doublons par
construction** — ils partagent presque tout leur découpage.

**Ce qui existe** : une séparation spectrale minimale entre λ, dans
`certus/physics/certus_strat_dp.py::_compute_valid_blocks_kernel`, paramètre
`min_wl_sep`. **Il manque l'équivalent au niveau des BLOCS.**

**Ce qu'il faut faire** : dans `certus/core/certus_strat_consensus.py`, à la sélection des
candidates, calculer une **signature de découpage** — la liste des frontières de blocs.
La fonction existe déjà : `_blocks_signature`, définie dans
`certus/utils/certus_strat_context.py` et déjà importée par `certus_strat_consensus.py`.
N'en retenir qu'un représentant par signature, ou imposer une distance minimale entre
signatures (nombre de frontières qui diffèrent).

**Critère de réussite** : sur le juge de paix, le top 10 doit contenir **10 découpages
différents**, pas 2 ou 3.

---

### 5.4 Des amorces structurées

**Ce qu'il faut ajouter** au jeu de stratégies évaluées, avant tout tri :

1. **Mono-λ** : tout l'empilement à une seule longueur d'onde, une amorce par λ de la
   grille de balayage.
2. **Un bloc par couche** : 48 blocs, chacun avec sa meilleure λ de Phase A.
3. **Découpages humains** : les partitions régulières (2, 3, 4, 6, 8, 12 blocs de tailles
   égales).

**Pourquoi** : elles **ancrent** l'ensemble, servent de **témoins** (si une amorce triviale
bat la DP, la DP a un problème), et coûtent une poignée d'évaluations.

**Où** : `certus/core/certus_strat_ranking.py`, à la sortie du minage, avant le criblage.

---

### 5.5 Allocation statistique du budget

👤 *« Augmenter N n'est pas un problème »* — alors autant le dépenser où il décide.

1. **Successive halving.** L'ossature existe : `certus/core/certus_strat_consensus.py`,
   variable `halving_budgets` (~ligne 569). Aujourd'hui deux étages seulement. Le porter à
   un vrai escalier : beaucoup de stratégies à peu de tirages, puis de moins en moins de
   stratégies à de plus en plus de tirages. Cible : finir à ~15 stratégies évaluées à
   ~200 tirages, pour le même budget total.
2. **Règle dure : jamais d'élimination irréversible à une résolution plus grossière que le
   seuil.** Le taux de plantage est binomial : écart-type à p = 5 % de **8,9 % à N = 6** et
   **1,8 % à N = 150**. Pour un seuil à 5 %, il faut **N ≥ 100**.
3. **Borne de confiance plutôt que seuil ponctuel** : n'éliminer que si les données
   **établissent** que le taux dépasse la tolérance. En cas de preuve insuffisante, la
   stratégie survit et sera jugée à la passe complète.

⚠️ **Conséquence immédiate en Phase A, à traiter dans la foulée** : avec `num_runs`
tirages, le plus petit taux non nul mesurable vaut `1/num_runs`, soit **0,67 % à 150** —
six fois la tolérance de 0,107 %. **Un seul run planté suffit donc à interdire une
longueur d'onde.** Le budget gouverne aujourd'hui la sévérité du filtre ; ce couplage
n'est pas voulu et doit disparaître avec le point 3.

---

### 5.6 Réparer les clés SYM

**Le défaut, exactement** :

| Rôle | Fichier | Clés écrites / lues |
|---|---|---|
| Producteur | `certus/core/certus_strat_objectives.py:590` | écrit `dist_prev_start`, `dist_next_start`, `dist_prev_end`, `dist_next_end` |
| Consommateur | `certus/utils/certus_strat_context.py:285` | lit `ext_prev_start`, … |
| Consommateur | `certus/utils/certus_strat_service.py:1178` | `_EXT_KEYS = ("ext_prev_start", …)` |

**Rien n'écrit jamais les clés `ext_*`.** Le score de symétrie vaut donc `999.0` partout,
et la passe de minage SYM ne diffère de la passe THICKNESS **que d'une constante** :
environ **un tiers du budget de minage recalcule THICKNESS**.

**Ce qu'il faut faire** : aligner les noms — le plus sûr est de faire écrire `ext_*` au
producteur, puisque deux consommateurs les attendent.

⚠️ **Attention, ce n'est pas une correction anodine** : réparer le nom **activera ce terme
pour la première fois**, et `sym_weight` (0,35 par défaut) n'a **jamais** été calibré sur
un terme vivant. **Poser la réparation derrière une mesure** : un run avant, un run après,
et si le classement se dégrade, recalibrer `sym_weight` avant de conclure.

---

### 5.7 Les autres sources d'erreur — la seule modélisée est le bruit de lecture

| Source | Effet réel | Modélisée ? |
|---|---|---|
| Bruit de lecture ΔT | erreur d'arrêt | ✅ |
| **Erreur d'indice run-à-run** | décale tout le signal | ❌ |
| **Dérive de calibration** | distorsion affine `T → a·T + b` | ❌ |
| Instabilité source / détecteur | dérive lente pendant le dépôt | ❌ |
| Vitesse de dépôt, inertie de l'obturateur | dépassement à l'arrêt | ❌ |

🔴 **L'ironie est nette, et c'est l'action la plus intéressante de cette liste.** Le
commentaire qui justifie POEM dans `certus/physics/certus_strat_growth.py` dit : *« si le
signal réel subit une distorsion affine `T_réel = a·T_nom + b`, les deux ancrages la
subissent identiquement »*. **Le code affirme que POEM absorbe les erreurs d'indice et de
calibration, et ne l'éprouve jamais — parce qu'il n'en injecte aucune.** L'argument
central du mécanisme est **non testé**.

**Ce qu'il faut faire, précisément** : dans `simulate_growth_kernel`, appliquer au signal
**réel** `Ts_r` une transformation `a·T + b` où `a` et `b` sont tirés **une fois par run**
(pas par couche), avec les mêmes exigences de nombres aléatoires communs que le bruit de
lecture — fonction pure de (graine, tirage), **sans aucune entrée de stratégie**.

**Critère de réussite** : mesurer le taux de plantage et l'erreur spectrale **avec et
sans POEM** sous distorsion affine. Si POEM tient sa promesse, l'écart doit être
**spectaculaire** ; s'il ne l'est pas, l'argument central du mécanisme tombe et il faut le
dire.

---

### 5.8 Extraire un objet `MachineModel`

Les caractéristiques de l'OMS 5100 sont dispersées en constantes dans le noyau :
`trigger_tolerance`, `SWING_MIN`, `extrema_exclusion_ratio`,
`sim_thickness_probe_offset_ratio`, `min_spectral_resolution`, `tp_hysteresis_factor`,
`NPTS`, `D_SCAN`. **Elles décrivent une machine** et devraient former un objet unique,
calibrable une fois et **daté**.

**Bénéfice** : la calibration devient un **acte traçable** au lieu d'une chasse aux
constantes. Deux sessions ont été perdues sur un `trigger_tolerance` mal réglé.

**Contenu naturel** : σ(λ) · cadence et temps d'intégration · résolution du
monochromateur · plage de λ accessible · règle de détection · modes de contrôle
disponibles.

---

### 5.9 σ dépend de la longueur d'onde

Le modèle utilise un σ **constant** (`_resolve_robustness_noise_levels`,
`certus/core/certus_strat_robustness.py`). Le bruit de l'OMS 5100 est plus fort vers 400
et 1100 nm. Une fois `MachineModel` en place, σ(λ) est une **table**, pas une refonte.

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

### 6.1 Les garde-fous automatiques qui manquent

1. **Test de calibration sur l'exemple réel** : « au moins N stratégies non repêchées à
   `crash_rate < 5 %` ». Un run. Il aurait transformé deux sessions d'analyse en trente
   secondes de diagnostic.
2. **Contrôle de sanité spectral** : vérifier que l'empilement de l'exemple **est** un
   dichroïque — T > 90 % sous 540 nm, T < 0,1 % au-dessus de 560 nm. Attrape d'un coup une
   mauvaise base d'indices ou une convention de signe inversée.
3. **Oracle du noyau de croissance** : comparer la racine du fit parabolique
   (`_solve_quadratic_target`) à la racine **exacte** de `T(d)` obtenue par balayage fin,
   seuil 0,05 nm. C'est ce que `tests/oracle/` fait pour le TMM ; le monitoring n'a pas
   son équivalent.
4. **Test anti-dérive du fichier d'exemple** : lui interdire de s'écarter d'un défaut du
   code sans justification écrite. **Quatre fois** il a été le plus mauvais réglage —
   `trigger_tolerance` 0,5 au lieu de 0,05 (bruit ×10), `execution_mode` `fast` au lieu de
   `premium` (budgets ÷4), `scan_wl_step` 5 au lieu de 2 nm, et
   `wavelength_change_penalty` 1,0 au lieu de 1,2.

   Valeurs attendues aujourd'hui, à verrouiller par ce test :

   | Clé | Valeur | Pourquoi |
   |---|---|---|
   | `scan_wl_step` | `"1.0"` | tranché par deux simulations complètes — voir §5bis |
   | `wl_step` | `"1.0"` | grille d'affichage |
   | `trigger_tolerance` | `"0.05"` | au-delà, le bruit injecté est ×10 |
   | `execution_mode` | `"premium"` | `fast` divise les budgets par 4 |
   | `wavelength_change_penalty` | `"1.2"` | |

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
