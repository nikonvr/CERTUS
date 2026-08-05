# Audit Phase B — STRAT n'optimise pas la cible spectrale, et il ne le peut pas

Établi par lecture du code le 2026-08-05, après que le physicien a précisé :
**« le plus important est la cible spectrale respectée »** et confirmé que la source
d'erreur est bien un ΔT statistique sur la mesure.

---

## 1. Le fait

**STRAT classe les stratégies sur leur écart au spectre de l'empilement NOMINAL, pas à la
cible.**

- `certus/core/certus_strat_robustness.py:211` construit la référence :
  `_, T_nom = calculate_RT_vectorized_real_HL(wl_arr, nH_arr, nL_arr, nSub_arr, p_thick_nom_arr)`
  — c'est la transmission des **épaisseurs nominales**.
- `:597` `T_nom_aligned = T_clean_batch[0]`, même origine.
- `:706-712` ce `T_nom_aligned` part en argument `T_target` de `compute_batch_rmse`
  (`certus/physics/certus_strat_batch.py:215-265`), qui calcule
  `sqrt(mean((T_total − T_target)²))` **sans pondération, sur toute la plage, à pas constant**.

**Et STRAT n'a jamais reçu la cible.** `example/example_strat/JSON-strat-example.json` compte
69 clés, aucune n'est une cible spectrale. `grep -rn "targets"` sur tous les fichiers STRAT
rend **zéro occurrence** — ni dans `APP_CONTEXT`, ni dans le HUB.

DESIGN, lui, la porte :

```json
"targets": [{"on": true, "lmin": 400.0, "lmax": 1200.0, "tmin": 0.5, "tmax": 0.5, "w": 1.0}]
```

Des **zones** avec bornes spectrales, transmission min/max et **poids**.

> STRAT répond aujourd'hui à « quelle stratégie reproduit le mieux le spectre des épaisseurs
> conçues ? ». Le physicien demande « quelle stratégie respecte le mieux la cible ? ».
> Ce ne sont pas les mêmes questions, et le module n'a pas les données pour répondre à la
> seconde.

---

## 2. Pourquoi l'écart n'est pas académique

### 2.1 Le RMSE non pondéré est aveugle à la structure du cahier des charges

Sur le dichroïque de l'exemple, plage 400–700 nm au pas de 1 nm, soit 301 points :

| Domaine | Points | Spec | Un écart de 0,5 point de T y vaut |
|---|---|---|---|
| 400–540 nm, passante | ~141 | ≈ 95 % | 0,5 % en relatif — négligeable |
| 544–552 nm, front | ~9 | pente raide | critique |
| **555–700 nm, bloquée** | **~146** | **< 0,1 %** | **cinq fois hors spec** |

Le RMSE actuel pèse ces 301 points **à l'identique**. Un demi-point d'écart dans la bande
bloquée, où il fait exploser la spécification, compte exactement autant qu'un demi-point dans
la passante, où il ne se voit pas. **La moitié du spectre est donc sous-pondérée là où
l'exigence est la plus dure.**

### 2.2 La compensation est dirigée vers le nominal, pas vers la cible

Le nominal n'est qu'une approximation de la cible — il porte le résidu de l'optimiseur de
DESIGN. Si le nominal est légèrement hors cible dans une zone, une erreur de dépôt qui
**rapproche de la cible** est aujourd'hui **pénalisée**, puisqu'elle éloigne du nominal.

C'est l'inverse de ce qu'on veut d'un critère de robustesse.

### 2.3 Deux stratégies de même RMSE-au-nominal ne se valent pas

Minimiser l'écart au nominal n'ordonne pas les stratégies comme minimiser la violation de
spec : deux stratégies peuvent avoir le même RMSE global en distribuant leurs erreurs sur des
longueurs d'onde très différentes. Le classement actuel ne les distingue pas ; le cahier des
charges, si.

---

## 3. La distinction qu'il ne faut PAS rater

Il y a un argument sérieux **en faveur** du nominal, et il faut le préserver :

> En salle, les niveaux d'arrêt sont **calculés à l'avance sur le nominal et figés**. La
> machine ne peut viser que ça. C'est même le mécanisme de l'auto-compensation (Arsac §2.3,
> Zideluns *et al.*) : viser une cible périmée sur un empilement erroné engendre l'erreur de
> signe opposé qui compense.

Il faut donc séparer deux choses que le code confond :

| | Aujourd'hui | Doit devenir |
|---|---|---|
| **Le point visé pendant le dépôt** (niveaux de trigger, POEM) | nominal, figé | **nominal, figé — ne pas toucher.** C'est la physique. |
| **La figure de mérite qui CLASSE les stratégies** | écart au spectre nominal | **écart à la CIBLE, pondéré par zone** |

La simulation du dépôt reste inchangée. Seule l'**évaluation** change. C'est ce qui rend le
correctif réalisable sans toucher au noyau de croissance.

---

## 4. Ce qu'il faut faire

1. **Acheminer `targets` de DESIGN vers STRAT.** Les zones `{lmin, lmax, tmin, tmax, w}`
   doivent entrer dans la configuration STRAT. Aujourd'hui la plomberie n'existe pas —
   c'est le vrai travail.
2. **Remplacer `compute_batch_rmse(T, T_nom)` par la fonction de mérite contre la cible**,
   celle que l'optimiseur de DESIGN minimise déjà. Les deux modules deviennent alors
   cohérents : DESIGN cherche l'empilement qui atteint la cible, STRAT cherche la stratégie
   de dépôt qui la conserve. Aujourd'hui ils ne minimisent pas la même chose.
3. **Garder le nominal comme point de visée** du simulateur d'arrêt. Ne rien changer là.
4. **Repli documenté** : si aucune cible n'est fournie, retomber sur le spectre nominal —
   comportement actuel, donc zéro régression.

### Comment valider

Rejouer l'exemple avec les deux figures de mérite et comparer les **classements**, pas les
scores. Si l'ordre change, la question était réelle. Attendu : les stratégies qui protègent
la bande bloquée doivent remonter, puisque c'est là que la spec est la plus dure et que le
RMSE non pondéré les ignorait.

---

## 5. Le reste de l'audit

Les autres défauts établis par lecture directe, à recouper avec l'audit en six étapes :

- **Le coût d'un bloc est la somme brute des coûts de couche**
  (`certus/physics/certus_strat_dp.py:61`), et la DP additionne les blocs (`:118`).
  Fusionner deux blocs adjacents à la même λ ne change **rien** au coût : la DP est
  structurellement **aveugle au découpage**, sauf par la contrainte `n_blocks`. Les bonus SYM
  et les passes ELITE sont des rustines qui compensent cette cécité.
- **`cost_map` est à deux dimensions** `[couche][λ]`, alors que le coût de Phase A dépend du
  découpage supposé via `block_start_arr`. La DP réutilise ces coûts pour des structures de
  blocs qui ne sont pas celles pour lesquelles ils ont été calculés.
- **`min(10, bl_count)`** (`:117`) — la DP ne considère que les 10 meilleures λ par bloc,
  en dur, sur ~51 candidates. Troncature silencieuse.
- **Un bloc est invalide si une seule de ses couches a perdu la λ** (`:64-66`). Une
  élimination à 0,107 % de plantage sur une couche tue un bloc de six.
- **Le coût est en nanomètres d'épaisseur**, l'objectif est spectral. La sensibilité
  spectrale par couche existe déjà (`sensitivity_data` au step 0) mais n'entre pas dans le
  coût de la DP.
