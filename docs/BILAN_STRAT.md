# Bilan complet de STRAT — état vérifié au 2026-08-06

Ce document remplace la lecture éparpillée des reprises précédentes. Il dit, étage par étage,
**ce qui est établi par mesure, ce qui est conforme à la littérature, ce qui ne l'est pas, et
ce qui est dormant.** Chaque affirmation porte sa source : `📏` mesuré ici, `📖` vérifié dans
la thèse, `👤` réponse du physicien, `❓` non vérifié.

Sources de référence, lues et citées textuellement :
- **Zideluns, thèse (206 p.)** — `C:\Users\Fabien\Downloads\Zideluns_Thesis_final.pdf`,
  co-encadrée par Fabien Lemarchand. Chapitres 2 (méthodes), 4 (contrôle polychromatique).
- **Trubetskov *et al.*** — définitions d'amplitude et de swing, reprises par Zideluns §4.
- **Arsac, thèse 2025** — POEM, éq. 2.2. *Non relue ici : le PDF n'a pas été fourni.*

> 📖 **Arsac et Zideluns décrivent bien le même mécanisme.** Zideluns p. 60 :
> *« the percentage of optical extrema monitoring (POEM) [50] or what is sometimes referred
> to monitoring by swing values [35] »*. La question était ouverte, elle est close.

---

## 1. L'objectif, et l'étalon de tout jugement

👤 *« Coller au mieux à ce qu'il se fait en dépôt, avec comme source d'erreur un ΔT
statistique. Trouver la stratégie la plus robuste au bruit et qui conduira à la meilleure
réponse spectrale d'un point de vue statistique. »*
👤 *« Le plus important est la cible spectrale respectée. »*
👤 *« Mon code doit avant tout être fiable, même au détriment du temps. Augmenter N n'est pas
un problème. »*
👤 *« D'une manière générale, interdit le mode fast. »*

Trois exigences, et **chaque étage du pipeline se juge à elles** :
**(a)** fidélité au dépôt réel · **(b)** la source d'erreur est un ΔT de mesure ·
**(c)** l'objectif est la distribution de l'écart **à la cible spectrale**.

---

## 2. La chaîne, étage par étage

### 2.1 Le noyau de croissance — `certus_strat_growth.py`

| | Statut |
|---|---|
| Bruit injecté | ✅ 📏 C'est bien un **ΔT ajouté au niveau de déclenchement**, pas une perturbation d'épaisseur postulée. Conforme à (b). |
| Cible figée sur le nominal | ✅ Le niveau est calculé avant dépôt sur la conception nominale et ne bouge plus. C'est ce qui engendre l'erreur de signe opposé, donc la compensation. |
| Formule POEM | ✅ 📖 **Conforme à l'éq. 2-4.** Le code calcule `p = (T_trig − T_prev)/(T_last − T_prev)` ; la thèse définit `S = (T_trig − T_last)/(T_last − T_prev)`. Comme `p = S + 1`, les deux reconstructions donnent **le même niveau** — même interpolation affine, point de référence différent. |
| Historique de bloc | ✅ 📖 Conforme. Zideluns p. 61 : *« The turning point for the swing calculation does not have to be in the same layer, the turning point of the previous layer can be used **if the same wavelength is used for both layers** »*. |
| Détection sur le signal **réel** | ✅ Correct : la fraction vient du nominal, les ancres sont comptées sur le réel. Détecter les ancres sur le nominal doterait la machine d'une connaissance qu'elle n'a pas. |
| Point tournant du substrat nu | ✅ 📏 📖 **Corrigé** (`19ffb6d`). La détection commençait à `k = 1` : l'extremum de bord en `d = 0` était invisible. Or 📖 Trubetskov/Zideluns p. 104 : *« Of course, the **S_in for first layer will be 0 %** »* — swing initial nul = le signal démarre **sur** un extremum. 📏 Vérifié : pente en `d = 0` de −8,0·10⁻⁴/nm contre −7,9·10⁻³/nm au milieu du quart d'onde. C'est aussi l'ancre la plus fiable qui soit : en `d = 0`, réel et nominal sont **le même objet**, le substrat nu. ⚠️ **Effet mesuré sur l'exemple : nul** — voir §5. |
| **Points tournants virtuels** | 🔴 **NON CONFORME.** Voir §3.1. |
| **Seuil d'amplitude `SWING_MIN`** | 🔴 **NON CONFORME.** Voir §3.2. |

### 2.2 Phase A — choix de λ couche par couche

`validate_wavelengths_batch` rend **(n_cands, 4)** : `P95(|Δd|)` · écart-type · taux de
plantage · gain de compensation.

- Coût = `P95 + w·gain·ε_amont`, deux termes en nanomètres, sans constante d'ajustement.
- Le taux de plantage **n'entre pas** dans le coût : il **élimine**, seuil
  `1 − (1 − 0,05)^(1/N)` = 0,107 % pour N = 48.
- 📏 Sur l'exemple, la Phase A réduit **126 λ scannées à 8–126 survivantes** selon la couche.
- 🔴 **La règle des 15–85 % n'est pas implémentée.** Voir §3.3.

### 2.3 Phase B — la programmation dynamique

| | Statut |
|---|---|
| Algorithme | ✅ *k*-meilleurs chemins **exacts**, pas une recherche en faisceau. Irréprochable. |
| **Objectif** | 🔴 `Σ_couches coût(couche, λ_de_son_bloc)`. 📏 **ρ de Spearman avec le vrai critère = −0,04** sur 240 stratégies. Voir §4. |
| Coût d'un bloc | 🔴 Somme brute des coûts de couche. Fusionner deux blocs adjacents à la même λ ne change **rien** : la DP est **aveugle au découpage**. |
| `n_blocks` | 🔴 Compte des **coupures**, pas des blocs monochromatiques : deux blocs adjacents à même λ comptent pour deux alors qu'en salle c'est un seul. |
| `cost_map` 2D | 🔴 `[couche][λ]` alors que le coût dépend du **début de bloc**. Calculé sous hypothèse gloutonne, réutilisé pour tous les découpages. |
| Cap de 10 λ par bloc | ✅ **Corrigé** (`78bf7d9`) par une séparation spectrale minimale. Voir §5. |
| Validité d'un bloc | Un bloc n'existe que si **toutes** ses couches ont la λ. Une élimination sur une couche tue le bloc entier. |

### 2.4 Évaluation de robustesse — le seul étage qui mesure la bonne grandeur

| | Statut |
|---|---|
| Nombres aléatoires communs | ✅ 📏 **En place.** Le bruit ne dépend que de `(robustness_seed, noise_idx, num_runs, num_layers)`, servi par un cache ; `_strat_idx` est délibérément inutilisé. La comparaison entre stratégies est donc **appariée**. |
| Fonctionnelle de classement | ✅ **CVaR95** remplace le P95 depuis cette session. Un P95 est décidé par 1 point à N = 6, 1-2 à N = 25, ~7 à N = 150 ; la CVaR moyenne la queue. |
| **Référence du RMSE** | 🔴 **Le NOMINAL, pas la cible.** Voir §3.4. |
| Pondération spectrale | 🔴 Aucune. Sur le dichroïque, la bande bloquée pèse 146 points sur 301 avec une exigence 500× plus dure, et compte autant que la passante. |

---

## 3. 🔴 Les non-conformités à la littérature

### 3.1 Les points tournants virtuels sont calculés puis rendus inatteignables

📖 Trubetskov/Zideluns p. 104 : *« In case of thin layers, **the virtual increase in thickness
is used to locate the missing turning points** »*, et *« If there is no turning point in
layer, as it is typically the case for thin layers, the theoretical increase in thickness is
calculated to find the extremum values »*.

Le code **calcule** ce prolongement — balayage à 64 points sur 3× l'épaisseur nominale, et le
commentaire le revendique explicitement. Mais la sélection des ancres l'annule :

```python
if k <= idx_nom_stop or tp_b < 0:
    tp_a = tp_b
    tp_b = k
```

Un extremum au-delà de l'arrêt n'est retenu que si aucun n'a été trouvé, et il laisse alors
`tp_a = −1`, ce qui fait échouer la garde `if tp_a >= 0`. **Un point tournant virtuel ne peut
jamais servir d'ancre.**

Conséquence : sur une couche mince sans deux extrema avant son terme — le cas que Trubetskov
et Zideluns désignent explicitement — POEM est **désactivé** et l'on retombe sur la cible
absolue, **sans compensation**. On paie le coût du balayage (64 évaluations au lieu de ~21 par
couche et par run) sans en tirer le bénéfice.

### 3.2 Le seuil de 4 % porte sur la mauvaise amplitude

📖 Zideluns p. 112 : *« for this monochromatic optical monitoring setup (OMS5100), a **start
amplitude** of at least 4 % is needed »*, avec la légende de la figure 4-7 :
*« A — total amplitude — difference between turning points ; **B — start amplitude —
difference between start transmittance and first turning point** ; C — final amplitude »*.

Le code applique `SWING_MIN = 0.04` à **A** :

```python
amp_nom = T_last_nom - T_prev_nom      # c'est A
```

Or **A ≥ B toujours**. Le code est donc **plus permissif que la machine ne le permet** : il
autorise POEM sur des longueurs d'onde dont l'amplitude de départ est sous les 4 % que
l'OMS 5100 exige pour distinguer le signal du bruit.

Et 📖 la thèse en fait un critère de **sélection de longueur d'onde** — *« we cannot adapt the
swing in but rather use the start amplitude to determine whether or not we can use a given
wavelength for monitoring »* — alors que le code n'en fait qu'un **repli de POEM**. Ce critère
devrait vivre en Phase A.

### 3.3 La règle des 15–85 % n'est pas implémentée

📖 Zideluns p. 113 : *« the trigger point in the range **15-85 % of the full amplitude**
between turning points appears to be the most efficient region. And this range is consistent
with that reported by other authors. This constrain prohibits the trigger point from being
close to a turning point. However, we added an **exception when the trigger point is an actual
turning point**. »*

Le code utilise `check_extrema_proximity`, qui travaille en **espace des épaisseurs** : une
marge `exclusion_width` en nanomètres autour de l'extremum, dérivée du ratio magique
`extrema_exclusion_ratio = 60`. Près d'un extremum, `T` varie **quadratiquement** avec `d` :
une marge fixe en épaisseur correspond donc à une fraction d'amplitude minuscule et
non contrôlée. **Le critère physique — le rapport signal sur bruit sur le niveau — n'est pas
celui qui est appliqué.**

✅ En revanche l'**asymétrie 3×/1×** du code (zone interdite trois fois plus large *avant* un
point tournant qu'*après*) est physiquement fondée et cohérente avec la thèse : s'arrêter après
un extremum est sûr, l'extremum est compté et le signal s'en éloigne monotonement.

📖 **À noter pour la question du TPM** : Zideluns ajoute une exception quand le trigger **est**
un point tournant, et conclut : *« the combination of turning point monitoring and level cut
monitoring in the same monitoring sequence should be considered because **both monitoring
methods are readily available with the OMS5100** »*. 👤 Le physicien a parqué le TPM en
indiquant que son OMS 5100 ne sait pas basculer d'un contrôle à l'autre. Les deux affirmations
ne sont pas nécessairement contradictoires — « disponibles » n'est pas « commutables en cours
de dépôt » — mais **le point mérite d'être retranché.**

### 3.4 STRAT ne connaît pas la cible spectrale

📏 `certus_strat_robustness.py:211` construit `T_nom` depuis les épaisseurs nominales, et c'est
lui qui part en `T_target` de `compute_batch_rmse`. Et **zéro occurrence de `targets` dans tout
le module** — DESIGN la porte pourtant, sous forme de zones `{lmin, lmax, tmin, tmax, w}`.

STRAT répond donc à *« quelle stratégie reproduit le mieux le spectre des épaisseurs
conçues ? »*, et non 👤 *« laquelle respecte le mieux la cible ? »*.

⚠️ **Distinction à préserver** : le point *visé* pendant le dépôt doit rester le nominal figé —
c'est le mécanisme même de l'auto-compensation. Seule la **figure de mérite qui classe** doit
passer à la cible pondérée.

---

## 4. 🔴 Le résultat central : la DP optimise une grandeur non prédictive

📏 `scripts/probe_dp_vs_truth.py`, population complète avant toute coupe, budget premium :

| `n_blocks` | n | étendue `total_cost` | étendue du vrai score | ρ Spearman | top-10 |
|---|---|---|---|---|---|
| **7** | **240** | ×1,33 | **×7,3** | **−0,042** | **0/10** |
| 9 | 47 | ×2,20 | ×2,5 | +0,109 | 3/10 |

Le coût varie de 33 %, la vérité d'un facteur 7,3, **et les deux sont décorrélés**. Des dix
stratégies que la DP garderait par coût, **zéro** figure dans les dix réellement meilleures.

Ce n'est pas un artefact : le même protocole à 6 tirages donnait ρ = +0,29, et **quadrupler la
précision a fait descendre ρ à zéro**, ce qui écarte l'atténuation par erreur de mesure.

📏 **Et ce n'est pas la FORME du coût qui est en cause** (`probe_cost_decomposition.py`) :

| | ρ avec le vrai score |
|---|---|
| `cost_dp` — la **prédiction** de la Phase A | **−0,41** |
| `cout_0 = Σ P95(|Δd|)` — la même formule, **mesurée** | **+0,59** |
| `cout_1` — **+ pondération par la sensibilité** | +0,59 *(aucun gain)* |
| `cout_2` — **+ covariance**, modèle linéaire complet | +0,64 *(marginal)* |

> **La formule est un bon proxy. C'est son estimation par la Phase A qui est
> anti-corrélée.** Le mécanisme est identifié : `cost_map` est 2D alors que le coût dépend du
> début de bloc, et il est calculé sous une hypothèse de découpage gloutonne réutilisée pour
> tous les découpages.

Cela **annule** le chantier « coût prédictif `sᵀΣs` » : ni les sensibilités spectrales ni la
covariance n'apportent quoi que ce soit. Le correctif est ailleurs — rendre `cost_map`
tridimensionnelle `[couche][λ][début de bloc]`, ce qui avec `MAX_LOOKBACK = 4` multiplie la
carte par cinq au plus.

---

## 5. Ce qui a été corrigé et mesuré dans cette session

| Correctif | Effet mesuré |
|---|---|
| **Bruit `trigger_tolerance` 0,5 → 0,05** 👤 | 4 stratégies toutes repêchées → **43 dont 25 saines**. Cause unique du blocage « STRAT ne rend rien ». |
| **`execution_mode` fast → premium**, puis **mode fast SUPPRIMÉ** 👤 | Budgets ÷4 rétablis. À 6 tirages, un P95 est **le maximum de six** et le taux de plantage a une résolution de 17 % pour un seuil à 5 %. |
| **`scan_wl_step` 5 → 2 nm** 👤 | 51 → **126** λ candidates. |
| **Séparation spectrale minimale, 10 nm** | Régions distinctes par bloc : min **1 → 3**, moyenne **2,41 → 4,58**. Repêchées : **6/194 → 0/191**, plantage médian **nul**. |
| **CVaR95 remplace le P95** | Variance de l'estimateur réduite à N égal, même sémantique de risque. |
| **Point tournant du substrat nu** | ⚠️ **Aucun effet mesurable** — voir ci-dessous. |
| **Banc : `WAIT_EXIT` + trace complète** | Les cinq sites de levée pré-émission ne se confondent plus en un `None` muet. |
| **Banc : `dump_strat_ranking`** | Le classement sort, pas seulement `RESULT`. |
| **`AB_WARMUP=1`** | Neutralise le biais du cache numba : 145,3 s à froid contre 37,7 s à chaud, soit 72 % du `RUN_S`. |

### Pourquoi le correctif du point tournant est dormant

📏 La Phase A produit **126 candidates validées sur 126** pour la couche 0, mais la DP n'en
reçoit qu'**une**. La réduction vient de `apply_nucleation_constraint`
(`certus_strat_ranking.py:29-47`), qui **épingle délibérément** les premières couches sur la
longueur d'onde de nucléation :

```python
cost_map_in[i] = {n_wl: val}
```

La couche 0 n'a donc aucun choix de λ à faire, et l'état de POEM sur elle ne change aucun
classement. Le repli `force_monolayer` est dormant pour la même famille de raison : il est
gardé par `not smart_nucl_active`.

**Le correctif est conservé** parce qu'il est physiquement juste et référencé (§2.1), et qu'il
vaudra sur tout empilement dont la première couche n'est pas épinglée. Mais il n'est **pas
démontré ici**.

---

## 6. Mes erreurs de méthode dans cette session

Je les liste parce que la régularité compte plus que chaque cas.

1. **`score > 0` classé « bug vérifié »** — c'est une garde délibérée, documentée dans sa
   docstring, et **spécifiée par deux tests**. Un `grep` dans `tests/` avant de conclure aurait
   suffi.
2. **`force_monolayer` classé « bug vérifié »** — le constat tient, mais le repli est gardé par
   `not smart_nucl_active` : il ne se déclenche jamais ici. Symptôme, pas maladie.
3. **Chaîne « POEM → élimination »** — inventée. `poem_ok = False` dégrade la compensation, il
   ne provoque **aucune** élimination.
4. **« Les ancres doivent encadrer le point d'arrêt »** — faux. L'éq. 2-4 les place **toutes
   deux avant** le trigger. La thèse a tranché contre moi.
5. **« Il manque les sensibilités / la covariance »** — réfuté par la mesure : +0,589 contre
   +0,590, et +0,643. Une théorie élégante et fausse.
6. **Ma sonde a cassé la production deux fois** — signature figée, puis `NameError` avec le
   drapeau `captured` posé avant le corps. Elle est désormais sous garde intégrale.

> Le défaut est constant : **je prends un comportement surprenant pour un défaut sans chercher
> l'intention ni la cause amont.** Les six fois, c'est une confrontation extérieure qui a
> corrigé — un `grep`, une phrase du physicien, un rapport d'observabilité, une thèse.

---

## 7. Les constantes, et leur provenance

### ✅ Ont une provenance

| Constante | Valeur | Source |
|---|---|---|
| `trigger_tolerance` | **0,05** | 👤 OMS 5100, signal fluctuant de 45,5 à 45,55 % de T |
| `CRASH_RATE_TOLERANCE` | **0,05** | 👤 *« 5 % de dépôt perdu, c'est parfait »* |
| `scan_wl_step` | **2,0 nm** | 👤 *« par expérience, il vaut mieux un pas de 2 nm »* |
| `SWING_MIN` | 0,04 | 📖 p. 112 — mais **appliqué à la mauvaise amplitude** (§3.2) |
| `robustness_noise_factors` | [0,5 ; 1 ; 2] | La marge de sécurité ×2 — **ne pas l'appliquer une seconde fois sur la base** |
| `DP_MIN_WL_SEPARATION_NM` | 10,0 | 📏 raisonné et mesuré (§5), mais **non optimisé** — 5 et 20 nm non essayés |

### ❓ N'en ont aucune

`sym_weight = 0,35` · `sym_same_wl_bonus = 0,15` · `sym_continuity_weight = 0,25` ·
`sym_extrema_window = 12,0 OT` · `SYM_MISSING_DISTANCE = 999,0` · la pénalité `× 2.0` de
`ranking.py:137` · `min(10, bl_count)` · `consensus_std_weight = 0,35` ·
**`extrema_exclusion_ratio = 60`** (et il remplace la règle des 15–85 %, §3.3) ·
`dynamics_threshold = 0,025` · `nucleation_degradation = 1,4` · `step0_sigma = 2,0`.

### 🔴 Le fichier d'exemple était pire que les défauts du code — trois fois

| Paramètre | Exemple | Défaut du code | Effet |
|---|---|---|---|
| `trigger_tolerance` | 0,5 | 0,1 | bruit ×10 → **zéro stratégie utilisable** |
| `execution_mode` | `fast` | `premium` | budgets ÷4 |
| `scan_wl_step` | 5,0 | **2,0** | 51 λ au lieu de 126 |

C'est un mode de défaillance à part entière : **le fichier de référence sur lequel tout le
monde diagnostique est celui qui dégrade le plus le résultat.** Un test devrait interdire à
l'exemple de s'écarter d'un défaut du code sans justification écrite.

---

## 8. Le chemin vers « la meilleure stratégie »

Par ordre d'effet sur l'objectif, pas de facilité.

| # | Action | Pourquoi elle fait converger |
|---|---|---|
| **1** | **Rendre `cost_map` tridimensionnelle** `[couche][λ][début de bloc]` | 📏 C'est **la** cause du ρ = −0,04 : la Phase A estime le coût sous une hypothèse de découpage que la DP n'évalue pas. La formule est bonne (+0,59), l'estimation est anti-corrélée (−0,41). |
| **2** | **Acheminer `targets` et pondérer le RMSE par zone** | 👤 C'est l'objectif déclaré. Aujourd'hui STRAT optimise autre chose. |
| **3** | **Rendre les points tournants virtuels utilisables** (§3.1) | Rétablit POEM sur les couches minces — le cas que la littérature désigne — et rentabilise un balayage déjà payé. |
| **4** | **Déplacer le critère d'amplitude de départ en Phase A**, sur **B** et non A (§3.2) | 📖 C'est le critère par lequel la thèse décide si une λ est utilisable. Il manque là où il compte. |
| **5** | **Implémenter les 15–85 % en amplitude** (§3.3) | Remplace un proxy en épaisseur par le critère physique de rapport signal/bruit. |
| **6** | **Déduplication en λ à l'étage ELITE** | 📏 Le top 5 reste `551, 552, 553, 554` — des perturbations **sous le pas de grille**. Quatre cinquièmes du budget Monte-Carlo final sont dépensés sur la même stratégie. |
| **7** | **Successive halving** + règle « pas d'élimination sous-résolue » | 📏 240 × 25 tirages à plat ; le taux de plantage est binomial, son écart-type à 5 % vaut 8,9 % à N = 6 et 1,8 % à N = 150. |
| **8** | **Réparer les clés SYM** (`dist_*` ↔ `ext_*`) | Un tiers du budget de minage recalcule THICKNESS. ⚠️ Activera un terme jamais calibré. |
| **9** | **Afficher `crash_rate` à l'opérateur** | Le seul critère qui parle à un fabricant est calculé, sert de couperet, puis disparaît. |

**Ce qu'il ne faut PAS faire** : chercher un coût prédictif par `sᵀΣs` (réfuté, §4) · toucher
au cap de 10 λ (traité par la séparation) · activer SYM sans recalibrer · conclure d'un écart
d'épaisseur sous 0,05 nm ou d'un écart de λ sous le pas de grille.

---

## 9. Questions ouvertes pour le physicien

1. **TPM** — 📖 Zideluns écrit que la combinaison point tournant + coupure de niveau
   *« should be considered because both monitoring methods are readily available with the
   OMS5100 »* (p. 113). 👤 Tu l'as parqué en indiquant que ta machine ne sait pas basculer.
   Est-ce une limite de **commutation en cours de dépôt**, ou la thèse est-elle trop optimiste ?
2. **`extrema_exclusion_ratio = 60`** — veux-tu qu'on le remplace par la règle 15–85 % en
   amplitude, ou qu'on garde le proxy en épaisseur en le calibrant ?
3. **Précision contre rendement** — une stratégie unique, ou un **front de Pareto**
   précision × taux de plantage ?
