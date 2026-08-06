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

### 1.5 ✅ `_select_best_strat_result` rejette le résultat parfait

`certus/utils/certus_strat_service.py:1157-1175` : `if np.isfinite(score) and score > 0`.
Une stratégie de score **exactement 0** — le meilleur possible — est **sautée**. Et
`extract_best_rmse` (`:1194-1199`) **lève** `PhysicsConvergenceError` si le score tombe dans
`[0, 1e-7)`. Deux pièges dans la même fonction, sur la même valeur.

---

## 2. Constats de l'audit — à confirmer avant d'agir

Non vérifiés par moi. La réfutation adversariale n'a pas eu lieu.

### 2.1 Les dix λ retenues par bloc sont probablement dix fois la même

`certus/physics/certus_strat_dp.py:117` garde les **10 λ de coût le plus bas**, sans aucune
contrainte de **séparation spectrale**. Le coût est une fonction lisse de λ et le pas de scan
est fin. Les dix « meilleures » d'un bloc sont donc vraisemblablement dix points voisins du
**même minimum local**.

> On ne garde pas dix stratégies, **on échantillonne dix fois la même** — puis on dépense
> dessus le budget Monte-Carlo, qui est la seule étape à mesurer la bonne grandeur.

**Vérification en une ligne** : imprimer `block_wls[j, i, 0:10]` pour quelques blocs.
**Correctif si confirmé** : n'accepter un candidat que si `|λ_b − λ_retenue| ≥ δ_min` pour
toutes les retenues. Ordre de grandeur de `δ_min` : le gain varie d'un facteur 17 entre 475 et
550 nm, donc à l'échelle de quelques dizaines de nm — **δ_min ≈ 20 nm** comme point de départ.
Coût : une boucle de rejet, zéro simulation supplémentaire.

C'est un renversement de perspective : **la DP ne doit pas être un classeur, mais un
générateur de diversité.** Le tri appartient au Monte-Carlo, seul à mesurer la réponse
spectrale.

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

## 3. 🔴 La mesure à faire AVANT toute décision

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
