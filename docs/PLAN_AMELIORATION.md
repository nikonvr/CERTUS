# Plan d'amélioration CERTUS

Document de reprise, écrit le 2026-08-02. Destiné à un agent qui prend la suite.
À lire **après** `CLAUDE.md`, qui donne le contexte projet et les conventions.

Les chantiers sont ordonnés : **chacun rend le suivant sûr**. Ne les prends pas dans le
désordre, en particulier ne commence pas par le lot C.

---

## 0. Règles de travail — non négociables

### 0.1 L'oracle avant toute chose

`tests/oracle/` contient une référence TMM **indépendante** de `certus.physics`, validée
sur quatre identités analytiques. Elle a déjà démasqué deux bugs de convention de signe
valant **46 et 82 points** de réflectance, tous deux exacts à k=0 donc invisibles à la
suite de tests d'alors.

```bash
.venv/Scripts/python.exe -m pytest tests/oracle/ -q --no-cov    # 237 tests, ~2 s
```

Avant de toucher au moindre calcul optique, lance-le. Après aussi.

### 0.2 Un test qui ne peut pas échouer n'est pas un test

Quand tu corriges un bug, **vérifie que le test que tu ajoutes échoue sur le code d'avant
correctif**. Réintroduis le défaut, lance le test, constate l'échec, remets le correctif.
Sans cette étape tu n'as rien prouvé.

Cinq assertions de ce dépôt codifiaient un comportement faux (voir CLAUDE.md §7). Méfie-toi
d'un test qui semble protéger quelque chose d'absurde : il protège peut-être le bug.

### 0.3 Vérifie un constat d'audit avant de l'appliquer

Sur 13 constats d'audit vérifiés par contre-expertise, **3 étaient sans objet** — dont un
classé « bloquant » et un « élevé » :

| Constat | Pourquoi il était faux |
|---|---|
| « le noyau gradient calcule un milieu à gain » | `phi_img = phi_base * ni` avec `ni` négatif donne bien `δ = φ_base·n̂` |
| « gradient face arrière mal normalisé » | il coïncide avec les différences finies de son propre coût à 3e-8 |
| « écrêtage `eps1` incohérent avec le gradient » | aucun noyau de gradient n'opère sur `eps1` |

**Reproduis par exécution avant de corriger.** Un constat plausible et bien rédigé n'est
pas un constat vrai.

### 0.4 Les marqueurs `LOCKED` ne prouvent rien

Un bug avéré en portait un, avec une docstring affirmant précisément l'inverse de ce que
le code faisait. Lis le code.

### 0.5 Trois pièges qui mordent

- **Hook d'auto-push.** `.git/hooks/post-commit` pousse chaque commit vers le dépôt
  **public**. `--no-verify` ne le neutralise pas. Actuellement renommé `.disabled` —
  vérifie son état avant tout commit que tu ne veux pas publier.
- **`reports/`** contient les **résultats scientifiques** de l'utilisateur. C'est
  gitignoré, donc git ne protestera pas si tu l'effaces, et c'est irrécupérable.
- **`git gc` échoue** (`fatal: bad tree object f26d9e1a`) à cause d'un commit orphelin
  packé. Sans conséquence sur les commits, mais le recompactage automatique ne passe pas.

---

## 1. État de départ

| | |
|---|---|
| Tests | **2373 passent**, 0 échec |
| Branche | `refactor-corridors-mixins`, 138 commits d'avance sur `main` |
| Lint visible (config projet) | 2 erreurs |
| Lint réel (sans `extend-ignore`) | voir lot C |
| Racine | 15 fichiers |

Quatorze défauts produisant des **résultats faux silencieux** ont été corrigés (voir
`git log`). Le motif dominant, à garder en tête pendant les revues : **une valeur calculée
correctement puis perdue** — une garde jamais relue, un mode résolu puis écrasé, un
contexte importé puis remplacé par un dict vide, un maillage décodé puis écrasé par le
suivant.

---

## 2. Les chantiers

### Lot A — Les 6 constats d'audit restants

Aucun ne produit de résultat faux : performance et validité statistique.
Traite-les dans cet ordre.

**A1. Graines Sobol corrélées** — `certus/core/certus_strat_robustness.py:414`
`local_seed = base_seed + noise_idx` fait collisionner les graines entre tirages de
consensus : deux configurations différentes peuvent recevoir le même bruit, ce qui biaise
l'estimation de robustesse. Utiliser un hachage combinant les deux indices.
*Vérifier* : générer les tirages de deux configurations voisines, mesurer la corrélation
croisée des bruits — elle doit être nulle.

**A2. `SplineBasisCache` avec des nœuds variables** — ✅ **CLOS le 2026-08-06, par la mesure.**

📏 **Ni « le cache manque systématiquement » ni « il rend une base périmée ».** Les positions de
nœuds **sont** dans la clé de `SplineBasisCache.get` — donc aucune base périmée n'est rendue par
omission. Mais cette clé est **arrondie à 1e-6 µm**, ce que le constat n'avait pas prévu, et c'est
la troisième situation :

- `compute_metal_bilayer_gradient_analytic` consulte le cache **directement**
  (`gradient_metal.py:319`), donc ni `use_cache=False` ni `--force-cache` ne le gouvernent ;
- mais cette base ne sert qu'au gradient par rapport aux **valeurs** de nœuds. Tout ce qui dépend
  de leurs **positions** passe par les deux chemins non mémoïsés (lignes 270 et 342) ;
- 📏 vérifié : un déplacement de nœud de **1e-9 µm** — mille fois sous l'arrondi — fait bouger le
  gradient de 2,1e-9. L'optimiseur n'est donc **pas** aveugle.

Il subsiste une péremption d'ordre `(dB/dλ) × 1e-6` sur les seules composantes de valeur :
**bornée et négligeable.** A2 ne passe donc **pas** en priorité absolue.

⚠️ **Ce que la mesure a corrigé chez moi** : j'avais d'abord écrit un test exigeant *zéro*
consultation du cache par le gradient. Il échouait — et il avait tort, pas le code. Le garde-fou
n'est pas un compte d'appels, c'est la **réponse du gradient** à un déplacement sous l'arrondi.
Verrouillé par `tests/oracle/test_spline_basis_cache_key.py` (4 tests).

**A3. Clés `lru_cache` par `tuple()`** — ✅ **FAIT.** La clé est construite par `.tobytes()`, et
le commentaire sur place documente la mesure : 35,9 µs par appel sur une grille de 601 points, soit
85 % du coût du chemin chaud, passés à fabriquer la clé.

**A4. Base spline reconstruite nœud par nœud** — `certus/physics/gradient_metal.py:291`
`num_knots` constructions de `CubicSpline` au lieu d'une seule sur toute la base.

**A5. Précision mixte f32/c64 sans effet** — `certus/core/certus_core.py:666`
La politique annonce un gain SIMD que les accumulateurs TMM annulent. Soit la retirer,
soit la documenter comme inopérante. Mesurer avant de trancher.

**A6. Cycle d'import `physics ↔ core`** — `certus/physics/certus_opt_kernels.py:3`
Voir lot E, dont c'est un cas particulier.

---

### Lot B — Étendre l'oracle aux gradients

**Pourquoi maintenant.** L'oracle couvre R et T, incidence normale et oblique. Il ne
couvre **pas** les gradients analytiques — or un gradient faux ne produit pas d'erreur :
il fait converger l'optimiseur vers un mauvais optimum, silencieusement. Deux des défauts
corrigés cette session étaient exactement de cette nature.

**Quoi faire.** Un harnais systématique gradient-analytique contre différences finies
centrées, sur un corpus figé, pour chaque fonction exportant un gradient :

- `compute_gradient_all_layers_analytic` (déjà vérifié ponctuellement, à figer)
- `compute_oblique_gradient_contrib_analytic`
- `compute_metal_bilayer_gradient_analytic`
- `_compute_gradient_analytic_kernel`
- le gradient spline de `spline_objective.py::_compute_analytic_gradient`

**Méthode.** Le test doit comparer le gradient au FD **du coût que la fonction retourne
elle-même**, pas à un coût reconstruit — c'est ce qui rend le test décisif. Avec des poids
**non uniformes** : plusieurs bugs de normalisation ne se voient qu'ainsi. Tolérance
relative 1e-6 pour un pas central de 1e-6.

**Risque** : nul, purement additif.

---

### Lot C — Éradiquer les `import *`

**Ne commence pas par là.** Ce lot n'est sûr qu'une fois le lot B en place.

**L'ampleur, mesurée le 2026-08-02** :

| Règle | Occurrences | Ce que ça veut dire |
|---|---|---|
| F401 | **5 261** | imports inutilisés |
| F405 | **3 156** | symbole venant d'un `import *`, origine intraçable |
| F822 | **202** | `__all__` listant des noms **inexistants** |
| F403 | 75 | les `import *` eux-mêmes |
| F821 | 29 | noms non définis |

**Pourquoi c'est la racine du mal.** Tant qu'un symbole peut « venir de nulle part »,
toute extraction de module est un pari — c'est précisément ainsi que l'extraction de
`certus_opt_gradients.py` a perdu deux décorateurs `@njit` et permuté une signature
publique sans que rien ne le signale.

**Ordre de traitement** :

1. **F822 d'abord** — les 202 `__all__` mensongers, concentrés sur 4 fichiers UI
   (`certus_ui_widgets_factory.py`, `certus_base_app.py`, `certus_ui_utils.py`,
   `certus_ui.py`). Ce sont des noms qui n'existent pas : tout `import *` sur ces modules
   lève `AttributeError`. Correction mécanique et sans risque : retirer les noms morts.
2. **F403/F405 ensuite**, module par module, jamais en masse. Pour chaque `import *`,
   lister les symboles réellement utilisés (`ruff --select F405` les donne) et les
   importer nommément.
3. **F401 en dernier**, et **jamais avec `--fix` global** : certains imports « inutilisés »
   sont des ré-exports volontaires ou des effets de bord d'enregistrement.

**Après chaque module** : `pytest tests/oracle/ tests/core/ tests/unit/ -q`.

**Risque** : élevé si fait en masse, faible module par module avec l'oracle en place.

---

### Lot D — Le cliquet

**D1. `extend-ignore` ne peut que rétrécir.** `pyproject.toml` masque 73 règles. Ajouter
un test qui lit la liste et échoue si elle grandit. Une dette qu'on ne peut plus augmenter
finit par disparaître.

**D2. La CI exécute la vraie suite.** `lint.yml` ne surveille que `main`, qui a 138 commits
de retard, et n'exécute aucun test. `release-windows.yml` en exécute 3 fichiers sur 226.
- déclencher aussi sur `refactor-corridors-mixins` ;
- exécuter `pytest tests/ -q --no-cov` sur `ubuntu-latest` — la recette Linux validée est
  dans CLAUDE.md §4 (Python 3.14.5, PyQt6 offscreen, numba 0.66) et tourne bien plus vite
  que `windows-latest` ;
- ne PAS toucher à `release-windows.yml` : le build gelé et la vérification des hashs du
  lockfile sont corrects.

**D3. Les invariants en property-based.** Hypothesis est déjà une dépendance. Quatre
propriétés couvrent une classe entière de bugs qu'aucun test d'exemple n'attrape :
`R+T <= 1` sur tout empilement passif, `k >= 0`, réciprocité, accord gradient/FD.

**D4. Contrats plutôt qu'exemples.** Le contrat `isinstance(f, CPUDispatcher)` existe déjà
pour 6 noyaux (`tests/oracle/test_tmm_oracle.py`). L'étendre aux signatures publiques :
une signature permutée est passée inaperçue parce que tous les tests appelaient par
mots-clés.

---

### Lot E — Architecture

À faire seulement après C : les cycles se cassent beaucoup plus facilement quand les
imports sont explicites.

- **Frontières de couches.** CLAUDE.md recense 12 inversions `utils → ui`, 10
  `core → workers`, et un cycle `physics ↔ core` (29/22). Les 3 inversions **au niveau
  module** sont les plus nuisibles : importer un module de calcul charge PyQt6.
- **DTO de `workers` vers `domain`** : c'est ce qui casse le cycle `core ↔ workers`.
- **Duplication divergente.** `prepare_targets_vectorized` et `make_cost_function` existent
  en double dans `gradient_utils.py` et `gradient_analytic.py`, avec des implémentations
  **différentes** — la copie de `gradient_utils` lit un attribut `.val` que `Target` n'a
  pas. Le garde-fou anti-duplication a été mis en liste blanche pour laisser passer ça
  (`tests/headless/test_code_duplication.py:75`, « Tolérance temporaire »). À résoudre,
  puis retirer la liste blanche.
- **Migration `certus/metal/` inachevée** : `CERTUS_METAL_SINGLE.py` (2 721 l.) et
  `CERTUS_METAL_BILAYER.py` (2 850 l.) sont restés à la racine.

---

### Lot F — Purge de l'historique `.env`

**Prérequis absolu : révoquer la clé sur console.anthropic.com.** Tant que ce n'est pas
fait, le reste est cosmétique — la clé est publique depuis le commit `35348c0` du
3 juillet.

`.env` n'est plus suivi depuis le commit `8bb51b2`, donc il ne repartira pas. Reste la
réécriture d'historique (`git filter-repo`), qui exige un force-push et invalide tous les
clones. À faire en une fois, en coordination avec l'utilisateur.

---

## 3. Ce qu'il ne faut pas faire

- **Ne pas lancer `ruff --fix` globalement.** Certains imports « inutilisés » sont des
  ré-exports volontaires.
- **Ne pas supprimer les trois `certus_*.py` de la racine** — ce sont des façades de
  ré-export que des tests importent par nom nu.
- **Ne pas recréer de rapport de session à la racine.** 58 y avaient été accumulés, tous
  contradictoires entre eux. `git log` est le journal.
- **Ne pas modifier `calculate_transmission_single`** pour « corriger » son écart avec un
  TMM nu : elle inclut délibérément la réflexion de face arrière.
- **Ne pas se fier à `.coverage`** : il date du 13 juillet et pointe vers un autre dossier.
- **Ne pas appliquer un constat d'audit sans l'avoir reproduit.** Voir §0.3.

---

## 4. Vérification, à chaque étape

```bash
# rapide, avant/après toute modification de calcul optique
.venv/Scripts/python.exe -m pytest tests/oracle/ -q --no-cov

# large, avant de committer
.venv/Scripts/python.exe -m pytest tests/core/ tests/unit/ tests/oracle/ \
    tests/domain/ tests/property/ -q --no-cov

# complète — compter ~12 min, la lancer en deux moitiés évite les délais d'attente
.venv/Scripts/python.exe -m pytest tests/integration/ tests/headless/ \
    tests/ui/ tests/performance/ tests/regression/ tests/utils/ -q --no-cov
```

Vérifier ce que Python importe réellement, en cas de doute :

```bash
.venv/Scripts/python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```
