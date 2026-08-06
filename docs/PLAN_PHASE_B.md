# Plan d'action — Phase B de STRAT

Écrit le 2026-08-05, après l'audit en six étapes et quatre campagnes de mesure.
Objectif énoncé par le physicien :

> « Coller au mieux à ce qu'il se fait en dépôt, avec comme source d'erreur un ΔT
> statistique. Trouver la stratégie la plus robuste au bruit et qui conduira à la meilleure
> réponse spectrale d'un point de vue statistique. »
> — et, ajouté le même jour : **« mon code doit avant tout être fiable, même au détriment du
> temps. Augmenter N n'est pas un problème. »**

---

## 0. Le diagnostic, en une page

### 🔴 Ce qui est MESURÉ

**Le coût de la DP ne prédit pas la réponse spectrale.** `scripts/probe_dp_vs_truth.py`,
population complète avant toute coupe, budget `premium` :

| `n_blocks` | n | étendue `total_cost` | étendue du vrai score | ρ Spearman | top-10 |
|---|---|---|---|---|---|
| **7** | **240** | ×1,33 | **×7,3** | **−0,042** | **0/10** |
| 9 | 47 | ×2,20 | ×2,5 | +0,109 | 3/10 |

Le coût varie de 33 %, la vérité d'un facteur 7,3, et les deux sont **décorrélés**. Le même
protocole à 6 tirages donnait ρ = +0,29 : **quadrupler la précision a fait descendre ρ à
zéro**, ce qui écarte l'atténuation par erreur de mesure.

**Les nombres aléatoires communs sont en place** (`_get_cached_sobol_noise`,
`certus_strat_robustness.py:482-510` ; `_strat_idx` est délibérément inutilisé, `:524`). La
comparaison entre stratégies est donc **appariée** — ce qui rend le ρ nul d'autant plus
significatif.

### La raison est structurelle, pas un réglage

L'erreur spectrale vaut, au premier ordre, `δT(λ) = Σᵢ Sᵢ(λ)·δdᵢ`, donc

```
Var[δT(λ)] = Σᵢ Σⱼ Sᵢ(λ) Sⱼ(λ) Cov[δdᵢ, δdⱼ]
```

Le coût de la DP vaut `Σᵢ P95(|δdᵢ|)`. Il jette **deux** choses :

1. **les sensibilités `Sᵢ(λ)`** — un nanomètre sur une couche sensible et un nanomètre sur
   une couche inerte comptent pareil, alors qu'elles s'étalent sur des ordres de grandeur ;
2. **tous les termes croisés `Cov[δdᵢ, δdⱼ]`** — et c'est le point décisif :
   **l'auto-compensation EST une covariance négative entre couches d'un même bloc.** Une somme
   de valeurs absolues jette les signes, donc les corrélations, donc précisément le mécanisme
   qui distingue une bonne stratégie d'une mauvaise.

> Le coût n'utilise que la **diagonale**, en valeur absolue, sans pondération spectrale.
> ρ = 0 n'est pas une anomalie : c'est la conséquence.

### Le pistolet fumant

Les cinq premières stratégies du classement, dernier run :

```
RANK00  ELITE      wl=[550,485,460,455,465,460,475,495]
RANK01  ELITE      wl=[550,485,460,454,465,460,475,495]   455→454
RANK02  ELITE      wl=[550,485,460,455,465,459,475,495]   460→459
RANK03  ELITE      wl=[549,485,460,455,465,460,475,495]   550→549
RANK04  THICKNESS  wl=[550,485,460,455,465,460,475,495]   IDENTIQUE à RANK00
```

**Le top 5 d'une recherche sur 240 stratégies est une seule stratégie** : trois perturbations
à ±1 nm et un doublon exact. Or le pas de balayage vaut 5 nm et le gain de compensation varie
à l'échelle de plusieurs dizaines de nm. **Un écart de 1 nm sur une longueur d'onde de
monitoring n'a pas de sens physique** — c'est la faute que le dépôt s'interdit déjà pour les
épaisseurs (règle des 0,05 nm), jamais transposée à λ.

### ✅ Ce qui est déjà corrigé (2026-08-05)

- **CVaR95 remplace P95** comme fonctionnelle de classement. Un P95 est décidé par 1 point à
  N=6, 1-2 à N=25, ~7 à N=150 ; la CVaR moyenne la queue. `rmse_p95` reste en place
  (32 références), `robustness_score_functional="p95"` restitue l'ancien comportement.
- **`execution_mode` de l'exemple passé de `fast` à `premium`.** `fast` divisait tous les
  budgets par 4 (`ui_state.py:1034-1062`) : `n_screen` 25→**6**, `robustness_num_runs`
  150→40, consensus 150→40 et 3→2 graines, `elite_rounds` 2→1. **À 6 tirages, un P95 est le
  maximum de six** et le taux de plantage a une résolution de 17 % pour un seuil à 5 %.
- **La page HTML** dit désormais ce que la DP peut voir et ce qu'elle ne peut pas, et sa
  description du bruit de Phase B — qui annonçait une graine par stratégie — est corrigée.

---

## 1. Actions immédiates — bugs vérifiés, coût faible

| # | Action | Fichier | Pourquoi |
|---|---|---|---|
| 1.1 | **Réparer le nom des clés SYM** | `certus_strat_objectives.py:565-568` ↔ `certus_strat_context.py:285-291` ↔ `certus_strat_service.py:1030` | Le producteur émet `dist_*`, le consommateur lit `ext_*`, et `_EXT_KEYS` recopie `ext_*`. **Rien n'écrit jamais ces clés** : le score de symétrie vaut 999,0 partout et ne discrimine rien. La passe SYM produit donc des doublons de THICKNESS — un tiers du budget de minage gaspillé. |
| 1.2 | **`force_monolayer` : vérifier la validité sur la couche 0** | `certus_strat_ranking.py:127-149` | Fabrique une arête `[0,2)` depuis les 10 meilleures λ de la **couche 1**, sans vérifier que la couche 0 a cette λ. Une λ éliminée pour plantage rentre dans la DP, **facturée en nanomètres** au lieu d'être exclue. La pénalité `* 2.0` ligne 134 est magique. |
| 1.3 | ~~`score > 0` → `score >= 0`~~ **ANNULÉ** | `certus_strat_service.py:1172, 1194` | ❌ **Ce n'était pas un bug — erreur de ma part.** Le `> 0` saute les zéros de remplissage (raison écrite dans la docstring) et la levée est **spécifiée par deux tests** (`test_strat_service.py:346`, `test_certus_strat_rmse_export.py:51`). Reste discutable : l'**emplacement** de la garde, qui tue le run au lieu de le signaler. Décision de conception → parquée pour le physicien. |
| 1.4 | **Afficher `crash_rate` dans la table opérateur** | `certus_strat_table_ui.py:217-300` | Le seul critère qui parle à un fabricant est calculé, sert de couperet, puis n'est jamais montré. |

⚠️ **1.1 activera le terme SYM pour la première fois.** `sym_weight = 0,35` n'a jamais été
calibré sur un terme vivant. À poser **derrière une mesure**, pas en aveugle.

---

## 2. 🔴 La résolution sur λ — le meilleur rapport effet/coût du plan

**Deux stratégies dont les longueurs d'onde diffèrent de moins de δλ_min sont la même
stratégie.** Déduplication **avant** de dépenser le moindre tirage Monte-Carlo.

**δλ_min = un pas de balayage, soit 2 nm.** Réponse du physicien, 2026-08-05 : *« par
expérience, il vaut mieux un pas de balayage de 2 nm »*. Cela fixe l'échelle : ce qui est plus
fin qu'un pas de grille est **sous la résolution de la recherche elle-même**, donc dénué de
sens. Ma proposition initiale de 20 nm était trop agressive — elle aurait écarté des λ que le
physicien considère comme distinctes.

- **Où** : à la sortie du minage et dans la génération ELITE, qui est la source des
  perturbations à ±1 nm — c'est-à-dire **sous le pas de grille**.
- **Effet attendu** : le budget Monte-Carlo cesse d'être dépensé quatre à cinq fois sur la
  même stratégie. Rappel du constat : le top 5 est une seule stratégie, trois perturbations à
  ±1 nm et un doublon exact.

> C'est la règle des 0,05 nm du dépôt, transposée à λ. Elle manque.

**Validation** : recompter les stratégies réellement distinctes du classement final avant et
après. Attendu : le top 10 doit contenir 10 stratégies différentes, pas 2 ou 3.

### ⚠️ Conséquence à ne pas rater : le cap de 10 λ doit être re-mesuré

Le pas de balayage de l'exemple est passé de 5 à **2 nm** (`scan_wl_step`), soit **126 λ
candidates au lieu de 51** sur 450–700 nm. Or ma réfutation de l'hypothèse « les 10 λ retenues
par bloc sont dix fois la même » a été mesurée **à 5 nm** : elles s'étalaient sur 95 nm en
médiane et couvraient 4 régions.

**À 2 nm, la densité de candidates est multipliée par 2,5, et les 10 moins chères ont
mécaniquement plus de chances de se regrouper.** L'hypothèse peut revenir. `§7 — ne pas
toucher au cap` est donc **suspendu** jusqu'à une nouvelle passe de
`scripts/probe_block_wls.py` au nouveau pas.

---

## 3. La DP doit générer pour la couverture, pas pour le coût

Ses *k* meilleurs chemins sont des quasi-doublons **par construction** : ce sont les *k*
moins chers d'une fonction lisse. Puisque le coût ne prédit rien, prendre les 240 moins chers
ne vaut pas mieux que 240 au hasard — et c'est **pire que 240 divers**.

- Sélectionner les chemins par **signature de découpage distincte**, pas par coût croissant.
- Conserver le coût comme **filtre de plausibilité** (écarter les absurdes), pas comme
  critère de tri.

⚠️ **Ne PAS toucher au cap `min(10, bl_count)`** (`certus_strat_dp.py:117`). Mesuré
(`scripts/probe_block_wls.py`) : les 10 λ retenues s'étalent sur **95 nm en médiane** et
couvrent **4 régions** alors que `coût(λ)` n'a que **2 à 5 minima locaux**. La structure est
déjà capturée, et le vrai élagueur est la Phase A, qui réduit ~51 λ scannées à 1–27
survivantes par couche. **Cette piste a été instruite et réfutée.**

**Validation** : nombre de signatures de découpage distinctes parmi les 240 minées, avant et
après.

---

## 4. Allocation du budget — successive halving

240 × 25 = **6000 simulations dépensées à plat**, alors que la plupart des candidats sont
départageables avec bien moins.

Le même budget en escalier — 240×8 → garder 120 ; 120×16 → 60 ; 60×32 → 30 ; … — finit à
~15 stratégies évaluées à ~200 tirages. **Même coût total, décision infiniment mieux fondée.**

Et puisque *« augmenter N n'est pas un problème »*, ce n'est même pas un arbitrage : on peut
faire les deux.

🔴 **Règle à inscrire en dur : on n'élimine jamais irréversiblement à une résolution plus
grossière que le seuil qu'on prétend mesurer.** Le taux de plantage est binomial : son
écart-type à p = 5 % vaut `√(0,05·0,95/N)`, soit **8,9 % à N=6** et 1,8 % à N=150. Pour un
seuil à 5 %, il faut **N ≥ 100 environ**. Aujourd'hui l'élimination se prononçait à N=6.

Piste complémentaire : remplacer le seuil ponctuel par une **borne de confiance binomiale** —
n'éliminer que si les données établissent que le taux dépasse la tolérance. Conservateur dans
le bon sens : en cas de preuve insuffisante, la stratégie survit au screening et sera jugée
proprement à la passe complète.

**Validation** : à budget total égal, le meilleur trouvé par successive halving doit être au
moins aussi bon que celui trouvé par l'allocation plate — sur plusieurs graines.

---

## 5. Chantier de fond — un coût réellement prédictif

Le remplaçant naturel de `Σ|δd|` est

```
J = Σ_λ w(λ) · sᵀ(λ) Σ_d s(λ)
```

où `s(λ)` est le vecteur des sensibilités `∂T(λ)/∂dᵢ` et `Σ_d` la covariance des erreurs
d'épaisseur sous la stratégie. Ce coût voit les sensibilités **et** les termes croisés, donc
l'auto-compensation.

### 🔴 La mesure préalable, à faire AVANT d'écrire une ligne dans la DP

`Σ_d` est **déjà produite** par le Monte-Carlo (`thicknesses_all`), et les sensibilités
existent au step 0 (`sensitivity_data`). On peut donc calculer `J` **hors ligne, sur les runs
déjà faits**, et mesurer son ρ avec le vrai score.

- **ρ élevé** → on tient le remplaçant, et on peut alors chercher une forme séparable
  approchée pour la DP.
- **ρ faible** → aucun coût analytique ne marchera, et il faut assumer la DP comme pur
  générateur (§3).

Coût : quelques dizaines de lignes, zéro simulation. **C'est la prochaine mesure à faire.**

### Forme séparable, si la mesure est concluante

Dans un bloc, si `εᵢ = gᵢ·εᵢ₋₁ + σᵢ`, l'erreur en sortie a une forme fermée et sa variance
aussi. Le coût d'un **bloc** — et non d'une couche — dépendrait alors de sa **longueur**,
ce qui rendrait enfin la DP sensible au découpage. Un coût de bloc est trivialement séparable
au sens de Bellman, c'est exactement la structure qu'offre `_compute_valid_blocks_kernel`.

⚠️ Attention aux hypothèses : linéarité de la propagation, et surtout **indépendance entre
couches — qui est fausse dans un même bloc**, puisqu'elles partagent l'historique de points
tournants. À instruire, pas à supposer.

---

## 6. La cible spectrale

Détaillé dans [`AUDIT_PHASE_B_CIBLE_SPECTRALE.md`](AUDIT_PHASE_B_CIBLE_SPECTRALE.md).

STRAT classe sur l'écart au spectre **nominal** (`certus_strat_robustness.py:211`, `:706-712`)
et **n'a jamais reçu la cible** : zéro occurrence de `targets` dans tout le module, alors que
DESIGN la porte sous forme de zones `{lmin, lmax, tmin, tmax, w}`.

Sur le dichroïque, la bande bloquée pèse **146 points sur 301** avec une exigence
500 fois plus dure, et compte exactement autant que la passante.

**La distinction à préserver** : le point *visé* pendant le dépôt reste le nominal figé —
c'est le mécanisme de l'auto-compensation. Seule la **figure de mérite qui classe** doit
passer à la cible pondérée.

**Repli** : sans cible fournie, retomber sur le nominal — comportement actuel, zéro régression.

---

## 7. Ce qu'il ne faut PAS faire

- **Toucher au cap de 10 λ par bloc** — instruit et réfuté (§3).
- **Optimiser la Phase A pour mieux estimer le coût actuel** — tant que ce coût n'est pas
  relié à l'objectif, c'est du temps perdu.
- **Activer SYM sans recalibrer `sym_weight`** — le terme n'a jamais tourné.
- **Comparer un classement CVaR95 à un classement P95** — CVaR ≥ P95 par construction, les
  échelles diffèrent.
- **Conclure d'un écart d'épaisseur sous 0,05 nm, ou d'un écart de λ sous le pas de
  balayage.**

---

## 8. Constantes sans provenance — à calibrer ou à supprimer

`sym_weight=0,35` · `sym_same_wl_bonus=0,15` · `sym_continuity_weight=0,25` ·
`sym_extrema_window=12,0 OT` · `SYM_MISSING_DISTANCE=999,0` · la pénalité `* 2.0` de
`ranking.py:134` · `min(10, bl_count)` de `dp.py:117` · `consensus_std_weight=0,35` ·
`extrema_exclusion_ratio=60` · `dynamics_threshold=0,025` ·
`nucleation_degradation=1,4` · `step0_sigma=2,0`.

Le dépôt a perdu deux sessions sur un paramètre non calibré (`trigger_tolerance`). C'est le
même risque, douze fois.

### ✅ Constantes qui ont désormais une provenance

| Constante | Valeur | Source |
|---|---|---|
| `trigger_tolerance` | **0,05** | mesuré — OMS 5100, signal fluctuant de 45,5 à 45,55 % de T (physicien, 2026-08-05) |
| `CRASH_RATE_TOLERANCE` | **0,05** | ✅ **validé par le physicien : « 5 % de dépôt perdu, c'est parfait »** (2026-08-05) |
| `scan_wl_step` | **2,0 nm** | ✅ **expérience du physicien : « par expérience, il vaut mieux un pas de balayage de 2 nm »** (2026-08-05) |
| `robustness_noise_factors` | [0,5 ; 1 ; 2] | c'est la marge de sécurité ×2 — ne pas l'appliquer une seconde fois sur la base |

---

## 8bis. 🔴 Le fichier d'exemple est systématiquement pire que les défauts du code

Trois fois, et à chaque fois le défaut du dépôt était correct :

| Paramètre | Exemple | Défaut du code | Effet du mauvais réglage |
|---|---|---|---|
| `trigger_tolerance` | 0,5 | 0,1 (juste : 0,05) | bruit ×10 → **zéro stratégie utilisable** |
| `execution_mode` | `fast` | `premium` | tous les budgets Monte-Carlo **÷4** ; P95 sur 6 tirages = le maximum de six |
| `scan_wl_step` | 5,0 | **2,0** | 51 λ candidates au lieu de 126 |

C'est un mode de défaillance à part entière : **le fichier de référence sur lequel tout le
monde diagnostique est celui qui dégrade le plus le résultat.** Les trois sont corrigés.
Un test devrait vérifier que l'exemple ne s'écarte d'un défaut du code que là où c'est
intentionnel et documenté.

---

## 9. Ordre recommandé

```
5.bis  mesurer rho(J = s'Σs, robustness_score) hors ligne   <- décide du §5, zéro simulation
2      resolution sur lambda (deduplication)                <- meilleur effet/cout
1.1    reparer les cles SYM (+ recalibrer sym_weight)
1.2    force_monolayer : validite sur la couche 0
1.3    score > 0  ->  score >= 0
4      successive halving + regle « pas d'elimination sous-resolue »
1.4    afficher crash_rate a l'operateur
6      acheminer targets, ponderer le RMSE par zone
3      DP generatrice de diversite
5      cout predictif dans la DP, si 5.bis est concluant
```

---

## 10. Questions ouvertes pour le physicien

1. **δλ_min** — en dessous de quel écart de longueur d'onde deux stratégies de monitoring
   sont-elles, pour toi, la même stratégie ? Le pas de balayage vaut 5 nm ; le gain varie sur
   quelques dizaines de nm. 5, 10 ou 20 nm ?
2. **`CRASH_RATE_TOLERANCE = 5 %`** — est-ce le budget réel d'un atelier ? Combien de dépôts
   perdus acceptes-tu sur une série ?
3. **Précision contre rendement** — préfères-tu qu'on te rende *une* stratégie, ou un **front
   de Pareto** précision × taux de plantage, à toi de trancher en salle ?
