# Fidélité physique du simulateur STRAT — état vérifié et travail à venir

> Ce document ne raconte rien. Il dit **ce qui est mesuré**, **ce qui reste à faire**, et
> **dans quel ordre**. Toute ligne chiffrée porte la commande qui la produit.
>
> Dernière vérification : 2026-08-08, sur `C:\dev\gemini`, branche `refactor-corridors-mixins`.

---

## 1. La machine réelle — spécifications obtenues du physicien

👤 Confirmé le 2026-08-08. Ce sont les nombres qui gouvernent tout le reste.

| Grandeur | Valeur | Conséquence |
|---|---|---|
| Rotation du plateau | **240 tr/min** | période 250 ms |
| Diamètre du plateau | ~1 m, témoin au bord | vitesse tangentielle **12,6 m/s** |
| Diamètre du témoin | 20 mm | **transit 1,6 ms**, rapport cyclique 0,64 % |
| Positions par tour | **3** : témoin, noir, vide | `T = (S − D)/(V − D)`, auto-référencé à 4 Hz |
| Vitesse de dépôt | ~0,5 nm/s | |
| **Cadence d'échantillonnage** | **4 Hz** | **un point tous les 0,125 nm** |
| Bruit de lecture | ±0,05 point, **largeur totale 0,10** | 👤 confirmé : le tirage du modèle est correct |
| Seuil « 5 σ » | 👤 *« bien au-dessus du bruit »* | **pas une contrainte physique** — voir §3.2 |

**Ce que la rotation implique.** Elle *moyenne* le dépôt — c'est sa raison d'être — mais
elle *échantillonne* la mesure : chaque point rapporté est un passage, rien ne se moyenne.
Trois positions par tour signifient que le noir et le vide sont relus toutes les 250 ms,
donc que la dérive d'étalonnage est **activement corrigée** par la machine.

---

## 2. Les quatre écarts identifiés — verdict

### Écart 1 — Méconnaissance d'indice δ_H, δ_L ≈ ±0,5 % — **priorité 1**

**Le diagnostic est juste.** L'incertitude d'indice n'est pas un bruit couche à couche :
c'est un **biais global constant par matériau** sur tout le run, donc il ne se moyenne pas.

📏 **Mesuré à l'oracle TMM indépendant** (6 couches QWOT, monitoring à niveau absolu,
610 nm, erreurs cumulées couche à couche) :

```
eps = +0.0050   erreur d'epaisseur physique max = 2.4578 nm
                erreur d'epaisseur OPTIQUE max  = 5.1173 nm
```

Le noyau actuel produit exactement **0**. L'effet est donc réel et du premier ordre.

🔴 **Mais la recette « pré-multiplier au site d'appel, sans changer la signature du
noyau » ne fonctionne pas.** Mesuré :

```
delta = 0.000 (reference)    max|d_achieved - d_nom| = 2.352e-10 nm
delta = +0.005               max|d_achieved - d_nom| = 3.293e-10 nm
delta = +0.050 (x10)         max|d_achieved - d_nom| = 1.923e-10 nm
```

Zéro machine, et **×10 sur la perturbation n'y change rien**. Cause : `n_H`/`n_L` pilotent
**à la fois** l'empilement réel (`M_before`) et l'empilement nominal (`M_nom`), ainsi que
`Ts_r` **et** `Ts_n`. Les mettre à l'échelle les décale ensemble — aucune divergence
réel/nominal, donc rien à compenser.

**Ce qu'il faut faire** : deux jeux d'indices dans la signature du noyau —
`n_H_real`/`n_L_real` pour l'empilement déposé, `n_H_nom`/`n_L_nom` pour le signal attendu
et le niveau de déclenchement. Plus une décision explicite sur l'indice qu'utilise
l'évaluation spectrale finale (`compute_batch_rmse`). **Effort : moyen, pas faible.**

### Écart 2 — Densité de grille — **bonne direction, cible à recalculer**

| | Machine | Modèle actuel | Proposition initiale |
|---|---|---|---|
| Pas spatial | **0,125 nm** | 4,76 nm | 1,0 nm |
| Points par couche de 100 nm | **800** | 21 | 100 |
| Historique, par couche relue | **800** | 16 | 100 |

Le modèle est **38× trop grossier** sur la couche courante, 50× sur l'historique. La cible
n'est pas un chiffre rond : c'est la cadence machine, `Δd = v_dépôt / f_échantillonnage`.

Deux réserves sur la mise en œuvre :

1. 🔴 `NPTS_PREV = ceil(d_real_j)` **casserait les nombres aléatoires communs** :
   `d_real_j` est l'épaisseur *obtenue*, donc dépendante de la stratégie. Le nombre de
   tirages de bruit par couche deviendrait fonction de la stratégie évaluée.
   **Correctif : indexer sur `p_thick_nominal[j]`**, indépendant de la stratégie.
2. 🔴 **Ne jamais raffiner la grille sans corriger le seuil d'hystérésis** — voir §3.2.
   À seuil inchangé, la fabrication de faux points tournants passe de 33 % à 99,9 %.

**Le coût, et sa parade.** 800 points sur 4 couches d'historique = 5 600 évaluations TMM
contre 128 aujourd'hui, soit ×44 — rédhibitoire. Parade : **découpler la grille physique de
la grille d'échantillonnage.** `T(d)` est lisse et parcourt moins d'une période sur tout le
balayage : on garde ~64 évaluations TMM exactes, on interpole sur les positions réelles, et
on tire **un bruit indépendant par position**. Le nombre de tirages — qui gouverne les
extrema parasites — devient fidèle à coût TMM inchangé.

### Écart 3 — Facteur de face arrière sur les seuils absolus — **négligeable, dernier**

Arithmétique correcte : `T_back = 4n/(n+1)² ≈ 0,957` pour BK7, soit 4,4 %. Deux compléments :

- Le chemin de **notation** applique déjà la face arrière complète avec réflexions
  multiples incohérentes (`certus_strat_batch.py:310-316`). L'écart ne concerne que le
  signal de monitoring.
- Il ne peut **pas** passer par `affine_scale` : `swing_min_thresh = affine_scale * SWING_MIN`
  annulait le facteur exactement — ligne supprimée le 2026-08-08.

**À faire en dernier, ou jamais.**

### Écart 4 — Quantification temporelle du déclenchement — **juste, petit, quasi gratuit**

La forme `U(0, Δd)` est la bonne : le volet ne peut pas se déclencher avant le
franchissement, donc la loi est strictement positive. Magnitude réelle :
**Δd = 0,125 nm**, contre 0,10 estimé initialement — juste à 25 % près.

L'argument de non-double-comptage avec `noise_val_precalc` tient : l'un est un bruit
**photométrique** (en T), l'autre est **spatial** (en d).

**Devient quasi gratuit une fois l'écart 2 fait** : si la grille de balayage est la grille
d'échantillonnage de la machine, on s'arrête au premier point au-delà du seuil au lieu
d'interpoler, et la quantification est automatique.

---

## 3. Deux défauts que le document initial ne voyait pas

### 3.1 La distorsion affine annulait son propre effet — ✅ **corrigé** (`76f7a8f`)

POEM est **exactement** invariant sous `T → a·T + b`. C'est l'argument qui justifie tout le
mécanisme. L'implémentation le brisait en trois endroits :

| Site | Défaut |
|---|---|
| Inversion parabolique | modèle **non distordu** résolu contre une cible **distordue** — unités mélangées |
| Repli absolu | `a·target_nominal + b` rendait au contrôleur l'étalonnage qu'il est censé avoir perdu |
| Test SWING | seuil mis à l'échelle par `a`, annulant le gain exactement |

📏 Avant : `a = 0,9574` déplaçait l'arrêt de **−6,60 nm**, écart attendu zéro.
📏 Après : invariance à **2,19e-10 nm**, et le repli absolu devient sensible — il rend
`CRASH_LEVEL_UNREACHABLE` sous une chute de gain de 4,3 % sur une couche à faible contraste.
C'est le contraste que le critère de réussite demandait.

🔴 **Reste à faire** : les paramètres ne sont atteignables depuis **aucun appelant**.
Ni `validate_wavelengths_batch` ni `simulate_stack_robustness_batch` ne les portent dans
leur signature. Le tirage `(a, b)` par run, en nombres aléatoires communs, n'existe pas.

### 3.2 🔴 Le seuil de détection est sous-dimensionné, et couplé à la grille

Le docstring de `detect_turning_points` énonce sa propre condition de suffisance : le
tirage étant borné à ±A, l'écart apparent maximal du bruit seul vaut 2A, donc
`hysteresis ≥ 2·trigger_tolerance/100` = **1,0e-3**.

Or `certus_strat_robustness.py:854` calcule `1,66 × 5e-4` = **8,3e-4**. **17 % sous la
borne que le code énonce.**

📏 Mesuré — signal propre **plat**, bruit réel, 20 000 tirages, aucun TMM. Fraction des
couches où le bruit **fabrique** un point tournant :

```
hysteresis                      N=80 (modele actuel)      N=320      N=800 (cadence machine)
1.66 A  (configure)                          32.945%    92.995%                      99.935%
2.00 A  (borne du docstring)                  0.480%     7.660%                      30.525%
2.40 A                                        0.000%     0.000%                       0.000%

Controle Piege 1 : bruit x0.50 a N=800, seuil 1.66 A  ->  0.000%
```

Trois lectures :

1. **1,66 A est insuffisant.** `Ts_n` n'étant pas bruité, tout point tournant fabriqué crée
   une divergence de comptage réel/nominal, donc un `CRASH_TP_MISCOUNT`.
2. **Le résidu à 2,00 A n'est pas physique** : c'est l'atome de probabilité à l'écrêtage
   ±1 du tirage, où `maxv − v` vaut 2A à l'arrondi près et le `>` strict devient un pile ou
   face en flottant. Prédiction du mécanisme à N=80 : 0,5 %. Mesuré : 0,48 %. **La borne
   « ≥ 2A » est juste en arithmétique exacte et marginale en flottant : il faut
   strictement plus.**
3. **Grille et seuil sont couplés.** Raffiner l'un sans l'autre fait exploser le taux de
   plantage, et on l'attribuerait à la physique.

**Réserve** : le signal plat est le pire cas. Un signal réel a une pente presque partout —
mais « presque partout » exclut le voisinage des vrais extrema, là où l'on compte.
👤 Le 5 σ n'étant pas une exigence physique, **la borne anti-fabrication gouverne**.

**Le réglage optimal est le plus BAS qui passe strictement au-dessus de 2A** : un seuil
trop haut aveugle le détecteur aux vrais extrema peu profonds. 2,1–2,2 A, pas 2,4.
Argument de marge : `SWING_MIN = 0,04` exclut déjà les extrema peu profonds du chemin POEM,
et 2,4 A = 1,2e-3 est **33× plus petit** que `SWING_MIN`. Reste à mesurer.

---

## 4. Ce qu'il reste à faire, dans l'ordre

| # | Action | Pourquoi ici |
|---|---|---|
| **1** | Câbler `(a, b)` par run dans les deux noyaux batch, en nombres aléatoires communs — fonction pure de (graine, tirage), **aucune entrée de stratégie**. Puis mesurer plantage et erreur spectrale **avec et sans POEM**. | Seule action pouvant **invalider POEM**, mécanisme central de STRAT. Tout le reste le suppose valide. La correction du noyau est faite, il manque l'accès. |
| **2** | Mesurer la **face droite** du seuil : à partir de quel facteur les *vrais* points tournants disparaissent. Puis balayer `tp_hysteresis_factor` ∈ {1,66 ; 2,1 ; 2,2} au banc. | Bon marché d'abord, cher ensuite. Injection par `probe_anchor_noise_pipeline.py <mode> <pas> <graine> <yw> <hyst>`. |
| **3** | Écart 1, avec **deux jeux d'indices** dans la signature du noyau. | Impact mesuré non nul, recette actuelle inerte. |
| **4** | Écart 2 **et** seuil définitif ensemble, avec le découplage grille physique / grille d'échantillonnage. | Ils se compensent : séparés, chacun produit un artefact. |
| **5** | Écart 4 — `U(0, 0,125 nm)`. | Quasi gratuit une fois 4 fait. |
| **6** | Écart 3, ou jamais. | 0,002 en absolu. |

**Règle sur chacune** : paramètre inactif par défaut, chemin inactif **bit-identique**.
Vérifié par empreinte `float.hex()`, pas « aux tests près » — la correction affine a été
validée ainsi sur 75 818 configurations du noyau.

---

## 5. Questions ouvertes

- **`phase_a_level_margin_factor`** partage aujourd'hui la valeur 1,66 avec
  `tp_hysteresis_factor` mais répond à un autre critère. Le 5 σ n'étant plus une contrainte,
  faut-il le rouvrir lui aussi ? Non traité, délibérément : une chose à la fois.
- **§4.2 de `PLAN_STRAT`** — brancher ou non la règle de proximité aux points tournants.
  Toujours ouverte, toujours un arbitrage de physique.

## 6. Ce qui n'est PAS à faire

- **Ne pas modéliser σ(T), la grenaille, ni le bruit multiplicatif.** Le modèle actuel — un
  tirage borné à ±0,05 point, un seul nombre mesuré, aucun paramètre libre — est
  défendable. Y ajouter une structure non mesurée remplacerait une constante mesurée par
  des paramètres inventés. 👤 Tranché le 2026-08-08.
- **Ne pas toucher `example/example_strat/JSON-strat-example.json`.** Injection par le
  script de sonde, qui accepte désormais `tp_hysteresis_factor` en 5ᵉ argument.
- **Ne pas raffiner la grille seule.** Voir §3.2.
