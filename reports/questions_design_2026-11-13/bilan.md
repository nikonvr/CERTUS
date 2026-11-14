# Cinq questions sur DESIGN et sur la validation — 2026-11-13

Demandé par 👤 le 2026-11-13. Lecture du code de DESIGN, de `CLAUDE.md`, de `docs/` et des rapports récents
(`audits_2026-11-13`, `DESIGN_bs5050_2026-10-22`).

Les §0 à §7 sont l'analyse, écrite avant tout code ; le §8 dit ce qui a été fait ensuite, le même soir, sur ordre de 👤.

Trois provenances de chiffres, toujours dites :

- **rapport** : lu dans un rapport de `reports/` ;
- **fichier exécuté** : `certus/domain/spectral_weights.py` exécuté tel quel, hors de l'arbre ;
- **bac à sable** : mini-TMM indépendant (incidence normale, sans pertes, indices constants), écrit hors de l'arbre,
  sans une ligne de `certus.physics`. Ces chiffres ne valent pas mesure sur les noyaux de CERTUS : à refaire avec eux.

## 0. Synthèse

| Question | Verdict | Premier pas |
|---|---|---|
| Fourier pour DESIGN | non comme moteur de synthèse ; oui comme générateur de germes et estimateur | germes structurés dans la population mémétique |
| Deviner N ou la TOT | oui, trois estimateurs complémentaires | affichage seul, à côté de `max_layers` et `max_total_qwot` |
| Grille adaptative | oui : la grille est une quadrature, on contrôle son erreur | corriger d'abord les poids sur bandes disjointes |
| Robustesse à la synthèse | oui, trois niveaux de coût croissant | sélection robuste (gratuite) avant la descente robuste |
| Vérifications ciblées | oui : graphe d'imports statique et paliers de risque | prouver le sélecteur avant de s'y fier |

Deux défauts trouvés en chemin : les poids spectraux sur bandes disjointes (§3.1) et l'énoncé « exact au second ordre »
du critère robuste (§4.4).

## 1. Transformée de Fourier

### 1.1 Mesure (bac à sable)

Relation de Fourier au premier ordre, `R ≈ tanh²|Σ ρ_k exp(−4iπσx_k)|` avec `ρ_k = ½ ln(n_k/n_{k+1})`, contre le TMM
exact ; 200 empilements aléatoires par ligne, 400–1200 nm, substrat 1,52.

| Matériaux | Couches | Erreur RMS sur R (médiane) | Corrélation (médiane) |
|---|---:|---:|---:|
| 2,35 / 1,45 | 8 | 0,078 | 0,96 |
| 2,35 / 1,45 | 20 | 0,205 | 0,83 |
| 2,35 / 1,45 | 40 | 0,276 | 0,70 |
| 1,65 / 1,45 | 8 | 0,001 | 1,00 |
| 1,65 / 1,45 | 20 | 0,008 | 1,00 |
| 1,65 / 1,45 | 40 | 0,026 | 0,99 |

DESIGN travaille à 10⁻⁴–10⁻⁵ de RMSE : à fort contraste, Fourier ne peut être ni le juge ni la synthèse finale.

### 1.2 Raisons de fond

- La relation est du premier ordre en `ρ = ½ ln(nH/nL)`, qui vaut 0,24 pour 2,35/1,45 : réflexions multiples dominantes.
- La solution naturelle est un profil à gradient d'indice ; sa conversion en deux matériaux fabrique des couches fines,
  contre le plancher de 5 nm.
- Ni dispersion, ni absorption, ni incidence oblique, ni face arrière, que les noyaux de DESIGN traitent.
- Verly et Dobrowolski ont dû ajouter une correction itérative ; sans elle l'antireflet large bande restait hors de
  portée pratique de la méthode (Appl. Opt. 31, 3836, 1992).

### 1.3 Où elle sert

1. **Germes structurés** : `run_memetic` tire sa population uniformément dans `init_bounds`. Ajouter des germes dont les
   interfaces `x_k` (profondeur optique) ajustent `Σ (−1)^k ρ exp(−4iπσx_k)` sur `Q̂(σ) exp(iφ(σ))`,
   `Q̂ = atanh √R̂` ; la phase `φ`, libre, donne la diversité. Coût : des FFT, aucun TMM. À essayer sur le trois-raies
   et la cissoïde OIC 2016, les deux cas perdus de l'audit du 2026-10-28. **Non mesuré.**
2. **Estimateur** de N et de la TOT (§2).
3. **Grille** : limite de bande de `1/T` (§3).
4. **Diagnostic** : la FFT en σ du résidu a pour abscisse un chemin optique ; de l'énergie au-delà de `2·TOT` ne se
   corrige pas à TOT fixée. Piste, non mesurée.

## 2. Deviner le nombre de couches et la TOT

### 2.1 Estimateur de contraste

Dérivé de la loi de l'empilement quart d'onde, `R = tanh²(Nρ)`, et de sa largeur relative `≈ (4/π)ρ` : une interface
« fournit » une aire `(4/π)ρ²` de `Q̂` en `d ln σ`, et consomme `λ/4` d'épaisseur optique.

```
N₀   ≈ (π / 4ρ²)  ∫ atanh √R̂(σ) d ln σ
TOT₀ ≈ (π / 16ρ²) ∫ atanh √R̂(λ) dλ          ρ = ½ ln(nH / nL)
```

Séparatrice 50/50, 400–1200 nm, 2,35/1,45 : `N₀ = 13,0`, `TOT₀ = 2 375 nm = 19,0 QWOT` (à 500 nm). L'enveloppe du
2026-10-26 (rapport `envelope_free`) donne à N = 13 : 19,02 QWOT, RMSE 3,59·10⁻³.
🔴 Un cas : pas une loi. La dérivation est la mienne ; à éprouver sur les autres cibles déjà reproduites.

Pour un antireflet la formule rend 0 : utiliser les lois empiriques publiées (Willey, Appl. Opt. 32, 5447, 1993 ;
Amotchkina, Tikhonravov, Trubetskov, Proc. SPIE 7101, 2008 ; Amotchkina, Appl. Opt. 47, 3231, 2008).

### 2.2 Degrés de liberté

Pour des indices constants et sans pertes, `1/T` est un polynôme trigonométrique en σ limité à la fréquence `2·TOT`.
Bac à sable (16 couches, épaisseurs optiques commensurables) : part de l'énergie oscillante au-delà de `2·TOT` :
`1/T` 1,0·10⁻²⁷ ; `T` 5,8·10⁻².

Un empilement de TOT donnée contrôle donc environ `4·TOT·Δσ` valeurs indépendantes sur une bande `Δσ`
(Landau-Pollak-Slepian), d'où `N ≳ 4·TOT·Δσ`. Sur l'enveloppe libre du 50/50, N = 8 à 34 (rapport) :
`N / (4·TOT·Δσ)` médiane 1,19, de 0,69 à 1,37 ; épaisseur optique moyenne par couche 126 nm, pour une borne
`1/(4Δσ) = 150 nm`.

Un front de largeur `δσ` impose une TOT de l'ordre de `1/(4δσ)` : constante à étalonner sur EF1–EF10.

### 2.3 Loi de précision

Ajustement sur la même enveloppe, N = 8 à 34 :

```
ln RMSE*(N) ≈ −1,88 − 0,268 N
```

soit RMSE divisé par 1,31 par couche (3,7 couches par facteur e), écart type de `ln` 0,35. Les constantes dépendent de
la cible et des matériaux : trois N pilotes à budget réduit, un ajustement, une extrapolation au RMSE demandé.

Avec le résultat du `ROBUST_PLAN` (sensibilité `S ~ N^0,5`, donc pénalité `σ²s²N`) et `RMSE* = A·exp(−N/N_c)` :

```
N_robuste = (N_c / 2) ln( 2A² / (N_c σ² s²) )
```

`s` reste à mesurer.

### 2.4 Emploi

Une fonction pure dans `certus/core/` : cibles, nH, nL → (N₀, TOT₀, nombre de degrés de liberté). D'abord en affichage,
à côté de `max_layers` et `max_total_qwot` ; ensuite, sur décision de 👤, valeur par défaut de `memetic_qwot_max` et N de
départ de la croissance. Inactive par défaut (C1).

## 3. Grille adaptative de longueurs d'onde

### 3.1 Défaut : poids sur bandes disjointes (fichier exécuté)

`prepare_targets_vectorized` appelle `spectral_rmse_weights` sur l'union des grilles des cibles : au bord d'un trou, le
demi-intervalle du trapèze traverse le trou. Grille construite comme `_get_optim_wls` (108 points par cible, uniforme
en nombre d'onde) :

| Cibles | Poids des deux points de bord | Part du poids total |
|---|---|---:|
| 400–1200 nm | — (poids max 1,8 ; médian 0,91) | 3,3 % |
| 400–500 et 600–700 nm | 35,5 et 35,3 (médian 0,72) | 32,8 % |
| 400–500 et 1000–1100 nm | 74,2 et 74,0 (médian 0,40) | 68,6 % |

Tout problème à bandes séparées par une zone libre (passe-bande et ses réjections) est concerné. Non mesuré : l'effet
sur un design. Correctif : poids calculés par bande contiguë, puis normalisés ensemble. Il change les bits des cas à
bandes disjointes : décision de 👤. Accessoire : les deux points extrêmes reçoivent un intervalle entier au lieu d'un
demi.

### 3.2 Autres constats (lus dans le code et les rapports)

- `_get_optim_wls` et `maybe_upgrade_grid_tikhonravov` donnent le **même nombre de points à chaque cible**, quelle que
  soit sa largeur.
- La densification a lieu **une fois**, après l'étape globale, sans contrôle ; `N = 2·L·Δν·10`, soit 5 fois le compte
  `4·TOT·Δσ`, plafonné à 5 000.
- Rapport du 2026-11-13 : le record tri-bande vaut 1,28·10⁻⁴ sur la grille à 1 nm et 4,8·10⁻³ à 0,1 nm (×37). ALG-22
  décrit le même symptôme. ALG-03 (oblique) reste ouvert.

### 3.3 Proposition

Le coût est une quadrature de `∫ w (T − T̂)² d ln λ` : la grille est bonne quand l'erreur de quadrature est petite
devant le coût. Les poids étant déjà des poids de quadrature, changer la grille ne change pas le sens du mérite.

1. **Grille de base par bande** : `N = m·4·TOT·Δσ_bande`, uniforme en σ, `m` = 2 à 3. La TOT vient de
   `max_total_qwot` pendant l'étape globale, puis du design. Pour 400–1200 nm et 30 QWOT : `4·TOT·Δσ = 25`, soit 75
   points à `m = 3`.
2. **Contrôle a posteriori** : évaluer le résidu aux milieux ; raffiner les intervalles où `|Simpson − trapèze|`
   dépasse `tol·coût/n` ; arrêter quand la somme des écarts passe sous `tol·coût` (1 %). Les milieux évalués deviennent
   des nœuds.
3. **Boucle externe** : grille figée pendant un polissage (sinon le mérite bouge sous l'optimiseur), enrichie entre
   deux, jamais appauvrie. Grille commune à toute la population mémétique, réévaluée après enrichissement (30
   évaluations).
4. **Raies plus étroites que le pas** : un critère d'échantillonnage ne voit pas une raie tombée entre nœuds et
   milieux. Ajouter des nœuds aux pôles de `analyze_resonances` (`λ_p ± k·largeur`), dont le comptage par le principe
   de l'argument garantit qu'aucun n'est oublié.
5. Paramètre `adaptive_grid`, inactif par défaut ; chemin inactif au bit (C1).

### 3.4 Mesure (bac à sable)

Filtre à 3 cavités, 72 couches, TOT 10 312 nm, bande 450–700 nm (`4·TOT·Δσ = 33`), résidu `T²`, référence à 400 001
points.

| Grille | Points | Erreur sur le MSE |
|---|---:|---:|
| uniforme, 2 × Nyquist | 66 | −4,41 % |
| uniforme, 5 × | 164 | +3,19 % |
| uniforme, 10 × | 328 | −7,74 % |
| uniforme, 20 × | 655 | −3,40 % |
| uniforme, 50 × | 1 637 | −0,00 % |
| adaptative (départ 2 ×, 6 tours, tol 1 %) | 180 | −0,77 % |

L'erreur de la grille uniforme n'est pas monotone. La grille adaptative a des pas de 42 pm à 5,7 nm.

## 4. Robustesse aux erreurs dès la synthèse

Existant : `second_order_robust_rmse` (diagnostic, 2N résidus par valeur, sans gradient), `spectral_monte_carlo`,
« Robust N », le `ROBUST_PLAN` du 2026-10-27 (phase 4 : coût robuste en option, non faite), l'audit de co-conception
du 2026-11-13.

### 4.1 Niveau 0 — sélection robuste, sans noyau nouveau

Classer les membres du mémétique (`judge`) et le champion Pareto par `MSE + Σ α_i² |∂r/∂d_i|²`. Le polisseur
Levenberg-Marquardt calcule déjà le Jacobien : le critère est gratuit. Le polissage reste nominal. Gain attendu modeste
à N fixé (le `ROBUST_PLAN` trouve ±15 % entre designs équivalents) ; non mesuré.

### 4.2 Niveau 1 — descente robuste, gradient exact en trois passes

```
F_rob(d)      = Σ_j w_j Σ_i α_i² (∂T_j/∂d_i)²
∂F_rob/∂d_k   = 2 Σ_j w_j [ ∇T_j(d + h v_j) − ∇T_j(d − h v_j) ]_k / 2h ,   v_j = α² ∘ ∇T_j
```

La direction `v_j` dépend de la longueur d'onde, ce qui est permis parce que le noyau traite chaque longueur d'onde
séparément. Erreurs relatives `α_i = σ_rel d_i` : ajouter `2 σ_rel² d_k Σ_j w_j (∂_k T_j)²`.

Bac à sable (20 couches, 301 longueurs d'onde, `h·max|v| = 10⁻³ nm`) : écart relatif maximal de 2,5·10⁻⁸ avec les
différences finies brutes du critère.

Dans CERTUS : variante de `_res_jac_lossless_normal_kernel` acceptant une épaisseur par longueur d'onde, le corps par
longueur d'onde partagé en `inline="always"` (aucune formule TMM nouvelle, interdit 7), `c1_diff` avant et après.
Ce mérite n'a pas de Jacobien de moindres carrés : `build_memetic_lm_polisher` le refusera par son contrôle
`COST_AGREEMENT_RTOL` et gardera L-BFGS-B, ce qui est correct.

### 4.3 Niveau 2 — nuage (Pervak, Trubetskov, Tikhonravov, Opt. Express 19, 2371, 2011)

Résidus empilés `r(d + δ_k)/√K`, Jacobiens empilés : compatible avec Levenberg-Marquardt, exact à tout ordre. Tirages
fonction pure de (graine, couche), comme `spectral_monte_carlo` (C2) ; paires antithétiques `±δ` ; continuation en σ ;
finalistes confirmés sur des tirages neufs.

### 4.4 Imprécision à corriger

La docstring de `second_order_robust_rmse` et le `ROBUST_PLAN` disent le critère exact au second ordre. Le
développement complet est

```
E[MSE] = |r|² + Σ α_i² |∂_i r|² + Σ α_i² r·∂²r/∂d_i² + O(α⁴)
```

Le terme croisé `2 r·Jδ` et les termes hors diagonale s'annulent en espérance ; le terme de courbure diagonal, non :
il est négligé (approximation de Gauss-Newton), ce qui vaut quand le résidu est petit.

Bac à sable, erreurs de 1 nm, 20 000 tirages, rapport à Monte-Carlo de l'incrément `E[MSE] − MSE₀` :

| Design | RMSE nominal | Gauss-Newton | Second ordre complet |
|---|---:|---:|---:|
| meilleur de 40 départs | 1,5·10⁻² | ×1,015 | ×1,011 |
| minimum local médiocre | 5,1·10⁻² | ×1,127 | ×1,009 |

Cohérent avec le 0,99–1,02 du `ROBUST_PLAN` sur le 50/50 ; mais un optimiseur sous mérite robuste visite des designs à
résidu plus grand, où l'approximation se dégrade. Le nuage n'a pas ce défaut.

### 4.5 Critique de fond

- Des erreurs indépendantes sont un mauvais modèle d'un dépôt contrôlé optiquement : l'audit du 2026-11-13 mesure
  qu'1 % sur une couche déplace l'erreur de dépôt de −3,7 % à +24,6 %, à plan figé.
- Sous erreurs indépendantes, le levier est N et la TOT, pas la structure fine : choisir N sur le front
  nominal/robuste (§2.3) rapporte plus qu'une descente robuste à N fixé.
- Piste, **non mesurée** : remplacer `α²` par la covariance `Σ̂` des erreurs d'épaisseur issue des tirages de STRAT
  sous un plan de référence, soit `tr(Σ̂ JᵀJ)`, même machinerie ; itérer design → STRAT → `Σ̂` → design. Le plan non
  réaccordé reste la limite que l'audit signale.

### 4.6 Préalables

R3 de l'audit (contexte de coût unique pour le mémétique, le polissage final et le nettoyage), sinon plusieurs
endroits jugent avec des mérites différents (ALG-18). Tout paramètre inactif par défaut (C1).

## 5. Vérifications adaptatives et ciblées

### 5.1 Constat (lu dans le dépôt)

- Suite complète : environ 40 min en série, 17 min par `validate_parallel.py` (2026-10-18).
- `tests/slow_tests.json` : 286 fonctions, 2 093 s cumulées — `ui` 977 s (100), `unit` 795 s (169), `headless` 218 s
  (8), `regression` 72 s. Quatre tests de `tests/ui/test_ux_one_action_system.py` y figurent à 120,0 s chacun : à
  regarder en premier (coût partagé compté quatre fois, ou réel).
- `numba_cache_key` est global : modifier un fichier qui cite numba recompile tous les noyaux à froid.
- `docs/ETAT.md` : un sous-ensemble a déjà laissé passer une régression
  (`test_the_architecture_debt_only_shrinks.py`).

### 5.2 `scripts/verify_changed.py` — plan

1. **Fichiers modifiés** : `git diff --name-only HEAD` et fichiers non suivis non ignorés, dans l'arbre suivi
   (CLAUDE.md §4).
2. **Graphe d'imports statique** par `ast` sur `git ls-files '*.py'` : imports de module et de fonction, registre
   `certus_lazy_imports`, façade `certus_physics` résolue symbole par symbole. Tests sélectionnés : ceux dont la
   clôture d'imports croise la clôture inverse des fichiers modifiés, au grain du fichier.
   Pas `pytest-testmon` seul : la couverture ne voit pas le corps des noyaux compilés (d'où le marqueur `kernels` et
   `NUMBA_DISABLE_JIT=1`) ; le graphe statique, si.
3. **Dépendances sans import** :
   - tests qui lisent les sources (dette d'architecture, cliquet de lint, anglais, source unique TMM, clé de cache) :
     toujours joués ;
   - fichiers de données (`example/`, `data/`, JSON de `tests/`) : sélection par les chemins cités dans les tests ;
     donnée inconnue : suite complète.
4. **Paliers de risque** :

   | Modifié | Joué |
   |---|---|
   | `.md`, `pages/` | les trois contrôles documentaires |
   | `certus/ui/` seul | ruff sur les fichiers, tests touchés rapides puis lents, tests toujours joués |
   | `utils/`, `workers/` | idem, plus le test `headless` du module |
   | `core/` hors noyaux | idem, plus les tests d'oracle touchés |
   | `physics/` ou fichier citant numba | idem, plus `tests/oracle/` entier et `c1_diff.py HEAD` |
   | `pyproject.toml`, `conftest.py`, verrous, import non résolu, plus de 60 % de tests touchés | `validate_parallel.py` |

5. **Verdict distinct** : `VERIF_CIBLEE=GO (n tests sur N)`, jamais `VALIDATION=GO`.

### 5.3 Prouver le sélecteur avant de s'y fier

- Rejeu sur l'historique : pour chaque commit d'un échantillon, tout test dont l'issue change doit être dans la
  sélection ; zéro échappé.
- `scripts/mutation_pilot.py` : une faute posée dans un fichier est tuée par la sélection si et seulement si elle l'est
  par la suite entière.
- Un test de la suite : pour chaque fichier de test, la clôture statique contient les modules `certus.*` de
  `sys.modules` après son import.

### 5.4 Ce qui relève de 👤

CLAUDE.md §2 exige la suite complète avant de committer. Proposition : commit = vérification ciblée et tests toujours
joués ; suite complète avant de pousser et chaque nuit. Invalidation du cache Numba par clôture de noyau plutôt que
globale : gain réel seulement en éditant les noyaux, risque de code machine périmé ; à instruire, non recommandé en
premier.

## 6. Ordre proposé

1. Correctif des poids sur bandes disjointes (§3.1), seul, avec un test qui échoue sur le code d'avant.
2. `verify_changed.py` et sa preuve (§5).
3. Estimateur N / TOT en affichage (§2.4).
4. Grille adaptative sous drapeau (§3.3), mesurée sur le tri-bande.
5. Sélection robuste (§4.1), puis descente robuste ou nuage selon la mesure.
6. Germes de Fourier (§1.3), jugés sur le trois-raies et la cissoïde.

## 7. Références

- P. G. Verly, J. A. Dobrowolski, R. R. Willey, Appl. Opt. 31, 3836 (1992) ; P. G. Verly, J. A. Dobrowolski, Appl.
  Opt. 29, 3672 (1990).
- A. V. Tikhonravov et al., Appl. Opt. 33, 5142 (1994) : transformée de Fourier discrète, lien entre complexité de la
  cible et TOT.
- R. R. Willey, Appl. Opt. 32, 5447 (1993), doi:10.1364/AO.32.005447.
- T. V. Amotchkina, A. V. Tikhonravov, M. K. Trubetskov, Proc. SPIE 7101, 710104 (2008) ; T. V. Amotchkina, Appl.
  Opt. 47, 3231 (2008).
- V. Pervak, M. K. Trubetskov, A. V. Tikhonravov, Opt. Express 19, 2371 (2011).
- A. V. Tikhonravov et al., Proc. SPIE 4829, 1061 (2003).

Références citées d'après leurs résumés ou d'après le `ROBUST_PLAN` : à lire avant de les citer ailleurs.

## 8. Fait le 2026-11-13 au soir (ordre de 👤 : « code complet et opérationnel »)

Travail fait sur une copie Linux de l'arbre (le shell du poste ne démarrait pas), Python 3.15.2, dépendances de
`requirements.lock` ; fichiers écrits ensuite dans l'arbre, **non committés**.

| Sujet | Où | Défaut | Preuve |
|---|---|---|---|
| Poids spectraux par bande (ALG-31) | `spectral_rmse_weights_banded` (`certus/domain/spectral_weights.py`), lu par `prepare_targets_vectorized`, `calc_rmse` et les groupes obliques | **actif** (décision de 👤) ; une bande seule, des bandes contiguës ou une grille qui a des points dans le trou : mêmes bits | `test_design_weighs_separate_bands_by_their_own_width.py`, rouge sur le code d'avant |
| Grille qui trouve ses points (ALG-32) | `certus/core/certus_design_auto_grid.py` ; `maybe_refine_grid_auto` à la place de la densification de Tikhonravov ; case « Automatic wavelength grid » | inactif (`auto_wavelength_grid`) ; incidence normale seulement | `test_design_auto_grid_finds_its_own_points.py`, `tests/ui/test_design_automatic_wavelength_grid.py` |
| Estimateur N et TOT (§2.1) | `estimate_layers_and_tot`, en info-bulle du nombre de points quand la grille automatique est cochée | affichage seul | mêmes tests |
| Sélection robuste du mémétique (ALG-33) | `build_memetic_lm_polisher(robust_sigma_nm=…)` : la population est jugée sur le coût plus σ² ‖J‖² | inactif (`memetic_robust_sigma_nm` = 0) ; exige le polisseur LM | `test_design_memetic_robust_selection.py` |
| Vérification ciblée (§5) | `scripts/verify_changed.py` : graphe statique au grain du symbole, `--collect-only`, oracle entier si un noyau change ; `--audit-calls` compare au code réellement exécuté | — | audit d'exécution sur `tests/integration` : 0 trou |
| Nombre de tours de la recherche locale STRAT | six fichiers de la passation du 2026-11-13, intégrés tels quels | celui de la passation | ses tests ; validation ci-dessous |
| Journaux des modules sous `logs/` | `certus/core/certus_logging.py` : un nom nu (`certus_design.log`) va dans `logs/`, plus à la racine du dépôt | — | `test_the_module_logs_go_under_logs.py`, rouge sur le code d'avant |

Mesures Windows du tri-bande et du 50/50 dans les sections suivantes.

## 9. Validation Windows

Le 14 novembre, Python 3.15.2, depuis `6ff1bfb2` avec les changements appliqués. Ruff et les trois contrôles
documentaires passent. Oracle 1 203 passés, interface 1 593, reste 322, performance 30.
Unitaires : 6 095 passés et quatre échecs au premier passage. Les deux comparaisons STRAT et le test de
temporisation Qt passent au rejeu isolé. Le registre des tests lents est corrigé, son lot rejoué donne 16 passés.
La validation d'ensemble a rendu `NO-GO` avant ce dernier correctif. Les deux pages HTML passent le contrôle
de structure et d'ancres. Les journaux sont archivés hors dépôt dans `validation-windows-20261114/` et
`validation-windows-20261114-rejeu/`.

Le 13 novembre, [C1 sur le corpus des noyaux](c1_windows.json) donne 9 092 tableaux identiques au bit.
Le test de pondération couvre séparément le changement volontaire sur les bandes disjointes.

## 10. Grille automatique sur le tri-bande RICL

Le 14 novembre, sonde sur `tl101_A_best.csv`, 101 couches, TOT 14 171 nm. Polissage L-BFGS-B avec le noyau
de DESIGN et les cibles du moteur RICL. Jugement commun par quadrature trapézoïdale par bande à 0,01 nm.

| Départ | Grille 1 nm | Grille 0,1 nm | Grille automatique |
|---|---:|---:|---:|
| Record | 3,149e-3 (277 points, 0,8 s) | 5,326e-3 (2 707 points, 75,2 s) | 9,581e-5 (1 064 points, 24,3 s) |
| Épaisseurs perturbées à 5 %, graine 1 | 4,633e-3 (3,3 s) | 6,069e-3 (30,7 s) | 1,330e-4 (520 points, 31,0 s) |
| Épaisseurs perturbées à 5 %, graine 2 | 4,383e-3 (3,4 s) | 5,501e-3 (54,5 s) | 3,840e-4 (873 points, 94,4 s) |

Sur le départ record, l'oracle indépendant retrouve 9,581e-5 à 0,01 nm. À 0,001 nm, le polissage automatique
donne 9,579e-5 et le polissage à 0,1 nm donne 2,180e-3. Le record initial donne 3,511e-3 à ce pas. La base
automatique de 178 points manquait elle-même les pics du record. L'expérience compare le raffinement de la
quadrature associé à plusieurs polissages avec un polissage sur grille fixe.
[Mesures des trois départs](probe_auto_grid.json) · [rejeu et oracle](probe_auto_grid_crosscheck.json).

## 11. Grille et sélection robuste sur le 50/50

Le 14 novembre, workflow DESIGN sur `JSON-design-reference-tikhonravov-1996.json`, graines 42, 77 et 202,
sans relance automatique, 16 polissages concurrents. Chaque design final est jugé à 0,5 nm par le noyau et
l'oracle indépendant. Leurs transmissions diffèrent de moins de 2e-15. La grille fixe démarre avec 108 points,
l'automatique avec 78. La sélection robuste utilise `memetic_robust_sigma_nm=1.0` sur la grille fixe.

| Option | RMSE nominale médiane | Durée médiane | RMS sous erreurs | P95 sous erreurs |
|---|---:|---:|---:|---:|
| Grille fixe | 7,715e-5 | 271,5 s | 0,02344 | 0,03236 |
| Grille automatique | 7,757e-5 | 269,1 s | 0,02307 | 0,03221 |
| Sélection robuste | 4,134e-4 | 262,8 s | 0,01903 | 0,02750 |

Tolérance : 400 tirages gaussiens indépendants par couche, σ = 1 nm, graine 20261114, même grille de jugement
et mêmes flux de tirage par indice de couche. Les épaisseurs exportées sont arrondies à 1e-4 nm. Le calcul de
tolérance rapporte aussi leur RMSE nominale recalculée. Les colonnes sont les médianes des trois designs.

La sélection robuste réduit le RMS médian de 18,8 % et augmente la RMSE nominale médiane d'un facteur 5,36.
L'automatique reste proche du témoin en médiane, avec des écarts variables selon la graine. Les deux options
restent inactives par défaut. Ces trois graines sur un problème ne fondent aucune loi de performance.
[Résultats des neuf essais et du holdout](bench_50_50.json).

Le test de sélection finale a révélé un score conservé sur l'ancienne grille automatique, susceptible de faire
écarter le résultat du raffinement. Corrigé dans `20563e25`, test rouge avant, 39 tests ciblés verts après.
Les trois essais automatiques ont été rejoués. Les six témoins suivent le même chemin de calcul qu'avant ce
correctif. Les journaux et exports bruts sont dans l'archive hors dépôt, sous `mesures-design/`.
