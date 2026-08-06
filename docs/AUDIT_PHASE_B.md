# Audit de la Phase B de STRAT — étape par étape

Audit du 2026-08-05, six étapes instruites en parallèle contre l'objectif énoncé par le
physicien :

> « coller au mieux à ce qu'il se fait en dépôt, avec comme source d'erreur un ΔT
> statistique. Trouver la stratégie la plus robuste au bruit et qui conduira à la meilleure
> réponse spectrale d'un point de vue statistique. »

**Statut de vérification.** Les constats marqués ✅ ont été vérifiés ligne à ligne par moi.
Les autres viennent des six audits ; leur réfutation adversariale n'a pas pu être menée
(limite de session), donc **ils sont à confirmer avant d'agir**. Le journal complet est dans
`docs/audits/phase_b_audit_20260805_journal.jsonl`.

---

## 0. Le verdict

La Phase B est algorithmiquement propre — la DP est bien un *k*-meilleurs chemins **exact**,
pas une recherche en faisceau — mais **elle optimise la mauvaise grandeur**, et plusieurs de
ses mécanismes correctifs sont morts ou tournent à vide.

Il n'y a **qu'un seul endroit** de tout le pipeline où la réponse spectrale est réellement
évaluée : l'évaluation de robustesse. Tout ce qui est éliminé avant l'est sur un proxy en
nanomètres dont la corrélation au vrai critère **n'a jamais été mesurée**.

---

## 1. ✅ Ce que j'ai vérifié moi-même

### 1.1 🔴 Le terme de symétrie SYM est MORT

Désaccord de nom entre producteur et consommateur :

| | Clés |
|---|---|
| **Producteur** `certus/core/certus_strat_objectives.py:565-568` | `dist_prev_start`, `dist_next_start`, `dist_prev_end`, `dist_next_end` |
| **Consommateur** `certus/utils/certus_strat_context.py:285-291` | `ext_prev_start`, `ext_next_start`, `ext_prev_end`, `ext_next_end` |
| **Pont supposé** `certus/utils/certus_strat_service.py:1030` | `_EXT_KEYS = ("ext_prev_start", …)` — recopie des clés `ext_*` |

`grep` sur tout le dépôt : les seules occurrences de `ext_prev_start` sont **le consommateur
et `_EXT_KEYS` lui-même**. Rien ne les écrit jamais. Donc `if k in src` est toujours faux,
et `cand.get("ext_prev_start", SYM_MISSING_DISTANCE)` rend **999.0 pour tout candidat**.

Le score de symétrie est donc **la même constante partout**. Il ne discrimine rien.

**Conséquences en cascade :**
- La passe de minage SYM calcule un coût qui ne diffère de THICKNESS que d'une constante →
  **même classement** → des stratégies **dupliquées**. Environ **un tiers du budget de minage
  et de screening** recalcule THICKNESS.
- Cela explique une observation de la session : à `trigger_tolerance = 0.5`, les quatre
  finalistes portaient toutes `origin=SYM`. C'étaient des doublons.

**Correctif : renommer.** Soit le producteur émet `ext_*`, soit `_EXT_KEYS` et le
consommateur lisent `dist_*`. ⚠️ Une fois le pont rétabli, le terme **s'activera pour la
première fois** : le comportement du classement changera, et `sym_weight = 0.5` n'a jamais
été calibré sur un terme vivant. À poser derrière une mesure, pas en aveugle.

### 1.2 ✅ `force_monolayer` contourne le filtre anti-plantage

`certus/core/certus_strat_ranking.py:127-149`. Quand un premier bloc d'une seule couche est
interdit et qu'aucun bloc `[0,2)` n'existe, le code fabrique une arête `[0,2)` à partir des
**dix meilleures λ de la couche 1**, avec une pénalité `np.mean(l1_costs) * 2.0`.

Il ne vérifie **jamais** que la couche 0 a cette λ parmi ses survivantes de Phase A. Une λ
éliminée pour cause de plantage sur la couche 0 peut donc rentrer dans la DP, **facturée en
nanomètres** au lieu d'être exclue. Or l'élimination sur plantage est justement le mécanisme
qui refuse de convertir un run perdu en pénalité continue.

Le `* 2.0` de la ligne 134 est un nombre magique sans provenance.

### 1.3 ✅ Le RMSE est mesuré contre le NOMINAL, pas contre la cible

Établi et documenté séparément dans
[`AUDIT_PHASE_B_CIBLE_SPECTRALE.md`](AUDIT_PHASE_B_CIBLE_SPECTRALE.md), committé en `e769fc4`.
`certus/core/certus_strat_robustness.py:211` construit `T_nom` depuis les épaisseurs
nominales ; c'est lui qui part en `T_target` de `compute_batch_rmse` (`:706-712`). Et STRAT
n'a jamais reçu la cible : **zéro occurrence de `targets` dans tout le module**.

### 1.4 ✅ La DP est aveugle au découpage

`certus/physics/certus_strat_dp.py:61` — le coût d'un bloc est la **somme brute** des coûts de
couche ; `:118` — la DP additionne les blocs. Fusionner deux blocs adjacents à la même λ ne
change **rien** au coût.

Conséquence relevée par l'audit et cohérente avec cette lecture : **`n_blocks` est un compte
fictif.** Deux blocs adjacents à la même λ sont comptés comme deux alors qu'en salle c'est
**un seul** bloc — le signal n'est pas interrompu. Le nombre de blocs affiché à l'opérateur ne
correspond donc pas au nombre de blocs monochromatiques réels.

### 1.5 ❌ CORRECTION — ce n'est PAS un bug, c'est un garde-fou délibéré et testé

**Une version antérieure de ce document classait ceci en « bug vérifié ». C'était faux, et
l'erreur est de moi.** Je l'ai laissée visible plutôt que de la réécrire en silence.

Le constat de départ est exact : `certus/utils/certus_strat_service.py:1172` teste
`if np.isfinite(score) and score > 0`, donc une stratégie de score exactement 0 est sautée ;
et `extract_best_rmse` (`:1194-1199`) **lève** `PhysicsConvergenceError` si le score tombe
dans `[0, 1e-7)`.

**Mais les deux sont intentionnels, documentés et couverts par des tests :**

- Le `> 0` a une raison écrite dans la docstring : *« older or partially populated payloads
  may keep placeholder zeros at the top »*. Il **saute les zéros de remplissage**. Le
  remplacer par `>= 0` réintroduirait précisément le bug qu'il corrige.
- La levée est **spécifiée par deux tests** :
  `tests/unit/test_strat_service.py:346-352` et
  `tests/unit/test_certus_strat_rmse_export.py:51-59`, tous deux en
  `pytest.raises(PhysicsConvergenceError, match="abnormally low/null value")`.
  Et elle est physiquement défendable : avec σ = 0,05 point de T, un RMSE spectral sous
  10⁻⁷ est impossible — c'est bien le signe d'une défaillance de convergence.

**Ce qui reste discutable n'est pas la garde, c'est son EMPLACEMENT.** `extract_best_rmse`
est appelée à l'intérieur de `_finalize_and_export_pipeline_results`
(`certus_strat_workers.py:1465`), **avant** le `return` et avant l'émission de `finished`.
Une levée y détruit donc tout le run au lieu de le signaler : le pipeline meurt, `finished`
n'est jamais émis, et le banc rend `RESULT=None`. C'est le cinquième site de levée
pré-émission du §3.2.

**Décision : parqué, pas corrigé.** Déplacer une garde spécifiée par deux tests relève d'un
choix de conception — signaler sans tuer, ou tuer pour forcer l'attention — et cette décision
appartient au physicien, pas à un agent. La lacune réelle du §3.2 (cinq sites de levée
indiscernables) reste valable et se traite par des codes d'erreur distincts, sans toucher aux
gardes elles-mêmes.

> Leçon de méthode : « le code fait X, or X est mauvais » n'est un bug que si personne n'a
> voulu X. Un `grep` dans `tests/` avant de conclure aurait évité cette erreur.

---

## 2. Constats de l'audit — à confirmer avant d'agir

Non vérifiés par moi. La réfutation adversariale n'a pas eu lieu.

### 2.1 ❌ RÉFUTÉ PAR LA MESURE — les dix λ ne sont PAS dix fois la même

**Hypothèse testée.** `certus/physics/certus_strat_dp.py:117` garde les 10 λ de coût le plus
bas, sans contrainte de séparation spectrale. Si `coût(λ)` était lisse à minimum unique, ces
dix seraient dix points voisins du même minimum — on échantillonnerait dix fois la même
stratégie avant de dépenser dessus le budget Monte-Carlo.

**Mesure.** `scripts/probe_block_wls.py` intercepte `_compute_valid_blocks_kernel` au premier
appel, sans rien changer au calcul. Sortie complète : `reports/probe_block_wls.json`.

```
BLOCS_VALIDES=211   AVEC_10_CANDIDATS=140
SPAN_NM      min=50   p25=75   median=95   p75=245   max=250
REGIONS_20NM min=3    median=4  max=5      mean=4.09
```

**Les dix λ s'étalent sur 95 nm en médiane** — jusqu'à 250 nm, toute la plage — et forment
**3 à 5 régions distinctes**. L'hypothèse est fausse.

**Ce que la mesure établit en revanche :**

| Fait | Chiffre |
|---|---|
| Le cap de 10 **mord** | 38 blocs sur 40 échantillonnés |
| Candidats jetés quand il mord | **8** en médiane, sur 18 disponibles |
| Coût du 10ᵉ retenu / coût du 1ᵉʳ | médiane **×2,21**, max ×4,94 |
| Minima locaux de `coût(λ)` par couche | **2 à 5** (couche 24 : 465, 485, 500, 515 nm) |
| Régions couvertes par les 10 retenus | **4** en médiane |
| λ survivantes à la Phase A, par couche | **1 à 27** sur ~51 scannées |

Deux conclusions :

1. **Ce que le cap jette est la queue**, pas de la diversité : des candidats déjà 2 à 5 fois
   plus chers localement, dans des régions déjà représentées. Les 10 retenus couvrent
   4 régions alors qu'il n'existe que 2 à 5 minima locaux — **la structure est déjà capturée**.
2. **Le vrai élagueur n'est pas le cap, c'est la Phase A.** Le filtre de plantage réduit
   51 λ scannées à 1–27 survivantes par couche, bien avant la DP. Les couches 0 et 1 n'ont
   qu'**une seule** survivante (550 nm), effet de `force_first_layer_same_wl`.

**Conséquence pour la sélection par intervalles** (proposition du physicien : découper la
plage en 10 intervalles et prendre le meilleur de chacun, plutôt que les 10 meilleurs points).
L'idée est structurellement supérieure à une séparation minimale gloutonne — elle est
déterministe et couvre par construction, là où le glouton dépend de l'ordre des coûts. Mais
son gain sur ce composant est **faible** : on passerait d'environ 4 régions effectives à
jusqu'à 10, alors que la fonction de coût n'en a que 2 à 5 qui aient un sens. Des intervalles
de largeur fixe sur 450–700 nm seraient d'ailleurs **contre-productifs** : la Phase A ne
retient rien au-dessus de 495 nm, donc 6 ou 7 intervalles sur 10 tomberaient dans une zone
morte.

**La bonne variante, si on la fait un jour**, n'est pas l'intervalle en λ mais le **minimum
local** : chaque minimum de `coût(λ)` est un choix de monitoring réellement distinct, et il y
en a précisément 2 à 5. Une sélection « les N meilleurs minima locaux » donnerait la même
couverture que les 10 actuels en coûtant **deux fois moins d'arêtes à la DP**.

⚠️ **Mais cette question ne se tranche pas avant celle du §3.** Tout ceci raisonne sur le
coût *local*, dont la valeur prédictive n'a jamais été mesurée. Si le ρ de Spearman est
faible, « garder les 10 moins chers » est une mauvaise règle **quelle que soit** leur
répartition spectrale — et c'est alors la règle qu'il faut changer, pas son échantillonnage.

### 2.2 Le consensus tourne pendant le screening

`certus/workers/certus_strat_workers.py:628,635` et `certus/core/certus_strat_consensus.py:339`
— le consensus complet (3 × 150 tirages) s'exécuterait **pendant** le screening à 25 tirages,
et seulement sur la moitié des candidats. Si c'est exact, l'ordonnancement du budget est
inversé.

### 2.3 `moyenne + 0,35 × écart-type` pénalise le bruit d'estimation

`certus/core/certus_strat_consensus.py:60-62, 256-269`. L'écart-type entre graines mesure
l'**incertitude d'estimation**, pas le **risque de fabrication**. Les pénaliser ensemble
revient à préférer une stratégie mal estimée mais stable à une bien estimée et variable.

### 2.4 Le second étage ELITE a des budgets décroissants

`certus/core/certus_strat_consensus.py:558-563, 604-610` — un *successive halving* dont les
budgets **diminuent** n'apporte aucune information au second étage.

### 2.5 Le score est le max des P95 sur trois niveaux de bruit

`certus/core/certus_strat_robustness.py:703, 732` — si le max tombe presque toujours sur le
niveau 2×, alors **deux tiers du budget Monte-Carlo ne classent rien**.

### 2.6 Le RMSE spectral n'est pas pondéré

`certus/physics/certus_strat_batch.py:263-264`. Cohérent avec §1.3 : sur le dichroïque, la
bande bloquée pèse 146 points sur 301 et son exigence est 500× plus dure, mais elle compte
autant que la passante.

### 2.7 Le taux de plantage n'est jamais montré à l'opérateur

`certus/ui/certus_strat_table_ui.py:217-300` affiche résolution, `n_blocks`, changements, λ
uniques, score, symétrie — **pas le taux de plantage**. Le seul critère qui parle vraiment à
un fabricant sert de couperet binaire puis disparaît.

### 2.8 Le carré change l'objectif

`certus/core/certus_strat_objectives.py:369-373` — `raw_results_sq` élève les coûts au carré.
Le carré d'une somme n'a pas le même optimum que la somme : c'est un **changement
d'objectif**, pas une mise à l'échelle, et il est fouillé **en concurrence** avec la variante
linéaire.

---

## 2bis. 🔴 MESURÉ — le coût de la DP ne prédit pas la réponse spectrale

C'est le résultat central de l'audit. `scripts/probe_dp_vs_truth.py` intercepte
`run_final_simulation_block`, qui rend le `robustness_score` de **chaque** stratégie minée —
avant toute coupe au top-*k*, donc sans troncature de sélection. Le ρ est calculé **par
`n_blocks`**, `total_cost` n'étant pas comparable d'un compte de blocs à l'autre.

### Résultat, budget `premium` (25 tirages au screening, 150 à la passe complète)

| `n_blocks` | n | `total_cost` (DP) | `robustness_score` (vérité) | ρ Spearman | τ Kendall | top-10 |
|---|---|---|---|---|---|---|
| **7** | **240** | 92,9 → 123,7 (**×1,33**) | 0,063 → 0,46 (**×7,3**) | **−0,042** | −0,021 | **0/10** |
| 9 | 47 | 23,8 → 52,3 (×2,20) | 0,016 → 0,040 (×2,5) | +0,109 | +0,066 | 3/10 |
| 8 | 10 | 32,9 → 60,2 (×1,83) | 0,034 → 0,052 (×1,5) | −0,326 | −0,325 | — |
| | | | | **ρ pondéré = −0,028** | | |

> **Le coût de la DP varie de 33 %. La vérité varie d'un facteur 7,3. Les deux sont
> décorrélés.** La DP discrimine — elle discrimine sur quelque chose qui n'a aucun rapport
> avec le résultat.

Et le chiffre opérationnel est sans appel : **des dix stratégies que la DP garde par coût,
zéro figure dans les dix réellement meilleures.**

### Pourquoi ce n'est pas un artefact de mesure

Le même protocole en budget `fast` (6 tirages) donnait ρ = +0,29. On pouvait alors soupçonner
une **atténuation par erreur de mesure** : à 6 tirages, un P95 est le maximum d'un échantillon
de six, et une vérité bruitée déprime mécaniquement toute corrélation.

**Quadrupler la précision a fait DESCENDRE ρ à zéro, pas monter.** Si le proxy était bon mais
mal mesuré, ρ aurait augmenté. L'hypothèse d'atténuation est donc écartée.

Et l'explication triviale — « le coût ne varie pas assez pour discriminer » — est écartée
aussi : il varie de 33 % sur 240 stratégies.

### Ce que cela implique

La Phase B élimine la quasi-totalité de l'espace sur `total_cost`. Ce tri est **sans valeur
prédictive**. Trois conséquences :

1. **La DP ne doit pas être un CLASSEUR.** Elle est algorithmiquement irréprochable —
   *k*-meilleurs chemins exacts — mais pour un objectif qui ne prédit pas la sortie. Elle doit
   devenir un **générateur de diversité**, et le tri revenir au Monte-Carlo, seul à mesurer la
   réponse spectrale.
2. **Les refontes de la fonction de coût deviennent prioritaires, pas secondaires.** Coût
   dépendant de la longueur du bloc, pondération par la sensibilité spectrale, écart à la
   cible plutôt qu'au nominal : ce ne sont plus des raffinements, ce sont les candidats pour
   remplacer un critère dont on vient de prouver qu'il ne prédit rien.
3. **Toute optimisation de la Phase A qui vise à mieux estimer ce coût est du temps perdu**
   tant que le coût lui-même n'est pas relié à l'objectif.

### Le budget réel : `execution_mode = "fast"` divise tout par quatre

Découvert en instrumentant. `certus/ui/certus_strat_ui_state.py:1034-1062` :

| Paramètre | Configuré | Réellement utilisé en `fast` |
|---|---|---|
| `n_screen_runs` | 25 | **6** |
| `robustness_num_runs` | 150 | **40** |
| `consensus_num_runs` | 150 | **40** |
| `consensus_num_seeds` | 3 | **2** |
| `elite_rounds` | 2 | **1** |

Le défaut du dépôt est `premium` (`ui_state.py:96`, `ui_layout.py:869`) ; c'est **le fichier
d'exemple** qui imposait `fast`. Même schéma que `trigger_tolerance`. Toutes les mesures de
la session antérieures à ce constat — dont le tableau de calibration du bruit — ont été
faites à un quart du budget.

⚠️ Conséquence statistique, et c'est elle qui compte : **à 6 tirages, un P95 est le maximum
de six**. L'élimination de 230 stratégies sur 240 se décidait donc sur **une seule
réalisation Monte-Carlo par stratégie**. Et le taux de plantage, binomial, avait une
résolution de 1/6 = **17 %** pour un seuil à **5 %**.

### Correctif posé : CVaR95 remplace P95 comme fonctionnelle de classement

`certus/core/certus_strat_robustness.py`. Un quantile est la fonctionnelle la moins efficace
d'un échantillon — le nombre de points qui décident réellement d'un P95 vaut 1 à N=6, 1-2 à
N=25, ~7 à N=150. La **CVaR95** (moyenne des 5 % pires, *expected shortfall*) garde la même
sémantique de risque mais **moyenne** la queue au lieu d'en piocher un point.

`rmse_cvar95` est calculée à côté de `rmse_p95`, qui reste en place — 32 références dans le
dépôt. `robustness_score_functional = "p95"` restitue le comportement antérieur, pour
comparer les deux classements sur un même run.

⚠️ CVaR95 ≥ P95 par construction : **les scores changent d'échelle et les classements
produits par les deux ne sont pas comparables.**

---

## 3. La mesure suivante

Une seule, et elle décide de tout le reste :

> **Le ρ de Spearman entre `total_cost` (la sortie de la DP) et `robustness_score` (le vrai
> critère), sur les stratégies que le pipeline évalue déjà.**

Les deux grandeurs sont **côte à côte dans chaque ligne** de `strategies_results`
(`certus/core/certus_strat_ranking.py:386-393` les lit toutes les deux). Une dizaine de
lignes, zéro physique nouvelle, aucun run supplémentaire.

- **ρ élevé** → l'élagage à 10 est inoffensif, et les refontes de la fonction de coût sont du
  bruit. On se concentre sur les bugs (§1.1, §1.2, §1.5).
- **ρ faible** → **la conception même de la DP comme filtre est fausse**, et aucun réglage
  interne ne la sauvera. Il faut alors la traiter comme un générateur de diversité et déplacer
  le tri vers le Monte-Carlo.

**Tout ce qui se décide avant ce chiffre se décide à l'aveugle.**

---

## 4. Ordre recommandé

| # | Action | Coût | Pourquoi maintenant |
|---|---|---|---|
| 1 | **Mesurer ρ(total_cost, robustness_score)** | ~10 lignes | Décide de tout le reste |
| 2 | **Imprimer `block_wls[j,i,0:10]`** | 1 ligne | Confirme ou infirme §2.1, le correctif le moins cher du document |
| 3 | **Réparer le nom des clés SYM** (§1.1) | faible | Un tiers du budget de minage est gaspillé. ⚠️ recalibrer `sym_weight` derrière une mesure |
| 4 | **`force_monolayer` : vérifier la validité sur la couche 0** (§1.2) | faible | Contourne le filtre anti-plantage |
| 5 | **`score > 0` → `score >= 0`** (§1.5) | trivial | Rejette le résultat parfait |
| 6 | **Acheminer `targets` et pondérer le RMSE** (§1.3, §2.6) | moyen | C'est l'objectif du physicien |
| 7 | **Afficher `crash_rate` dans la table opérateur** (§2.7) | faible | Le critère qui parle au fabricant |

Les refontes de fond — coût de bloc dépendant de la longueur, DP à état d'erreur, front de
Pareto précision × rendement — ne se décident qu'**après** la mesure du §3.

---

## 5. Constantes sans provenance rencontrées

`sym_weight=0,5` · `sym_same_wl_bonus=0,2` · `sym_continuity_weight=0,1` ·
`sym_extrema_window=5,0` · `SYM_MISSING_DISTANCE=999,0` · la pénalité `* 2.0` de
`ranking.py:134` · `min(10, bl_count)` de `dp.py:117` · `consensus_std_weight=0,35` ·
`CRASH_RATE_TOLERANCE=0,05`.

Le dépôt vient de perdre deux sessions sur un paramètre non calibré (`trigger_tolerance`).
C'est exactement le même risque, neuf fois.
