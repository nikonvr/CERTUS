# Audit complet — CERTUS Optical Suite

**Date** : 1er août 2026
**Périmètre** : `D:\drivefl\couches minces 2026\CERTUS\0108`
**Branche analysée** : `refactor-corridors-mixins` (HEAD = `a0646df`)
**Version déclarée** : `certus-optical-suite 26.05.0`
**Axes demandés** : architecture & dette technique · santé du code · correction physique/numérique

---

## 0. Synthèse en une page

CERTUS est un projet scientifique sérieux et volumineux : 183 600 lignes de code source, 56 400 lignes de tests, un cœur TMM correct et documenté, une CI Windows avec build gelé et lockfile vérifié par hash. Le niveau d'ingénierie visé est réel — la structure DDD, les marqueurs `LOCKED`, la vérification des hashs du lockfile ne sont pas des choses qu'on trouve dans un projet amateur.

Trois problèmes dominent, par ordre d'urgence :

| # | Problème | Gravité | Effort |
|---|----------|---------|--------|
| 1 | **Clé API Anthropic exposée publiquement sur GitHub** depuis le 3 juillet 2026 | 🔴 Critique | 15 min |
| 2 | **3 semaines de travail non commité** (130 fichiers, ~12 000 lignes) sur une branche à 137 commits de `main` | 🔴 Critique | 2 h |
| 3 | **Bug de convention de signe** dans `calculate_RT_single_layer_single` — erreur jusqu'à 39 points de réflectance sur couches absorbantes, verrouillé par un test qui affirme le mauvais signe | 🟠 Élevé | 30 min |

Viennent ensuite : une dette de lint réelle de **12 157 violations** masquée derrière une liste `extend-ignore` de 73 règles, **aucune exécution du suite de tests en CI** (3 fichiers sur 226), et l'absence de `__init__.py` dans les 7 sous-packages principaux.

---

## 1. 🔴 CRITIQUE — Fuite de la clé API Anthropic

### Constat

Le fichier `.env` est **versionné et poussé** sur le dépôt public `github.com/nikonvr/CERTUS`.

```
Fichier          : .env  (à la racine, tracké par git)
Contenu          : ANTHROPIC_BASE_URL=… + ANTHROPIC_API_KEY=sk-3…
Commit d'ajout   : 35348c0 — 2026-07-03 08:40:33
Message          : "Fix UI OBJ NameError and resolve calc_spectrum_front import in oblique TMM"
Branche distante : origin/refactor-corridors-mixins  ← POUSSÉE
Visibilité dépôt : public (repository_public: true)
Exposition       : ~4 semaines
```

Vérifications effectuées :

- `git branch -r --contains 35348c0` → `origin/refactor-corridors-mixins`
- `git cat-file -e origin/refactor-corridors-mixins:.env` → le blob existe côté distant
- `.gitignore` ne contient **aucune** entrée `.env`

Les branches `main`, `master`, `fab` et `certus` ne contiennent pas le fichier — la fuite passe uniquement par la branche de travail, mais celle-ci est bien publique.

### Action immédiate

1. **Révoquer la clé** sur console.anthropic.com — à faire en premier, avant toute manipulation git. Une clé publiée 4 semaines sur GitHub doit être considérée comme compromise : les scrapers de secrets indexent les dépôts publics en quelques minutes.
2. Ajouter `.env` au `.gitignore`.
3. Purger l'historique distant (`git filter-repo --path .env --invert-paths`, puis push forcé) — **après** révocation, car la purge seule ne suffit jamais : le blob reste accessible via l'API GitHub et les forks/caches.
4. Vérifier l'usage de la clé dans la console (facturation, journaux d'appels) sur la période du 3 juillet au 1er août.

---

## 2. 🔴 CRITIQUE — État git : 3 semaines de travail en suspens

### Constat

```
Branche courante  : refactor-corridors-mixins
Dernier commit    : 2026-07-08 12:23  (il y a 3 semaines et 3 jours)
Non commité       : 130 fichiers, +6 730 / −5 339 lignes
                    (hors desktop.ini et logs campaign_18h)
Détail statut     : 195 modifiés · 97 non suivis · 37 supprimés
```

Divergence entre branches (commits d'avance de `refactor-corridors-mixins`) :

| Branche | Retard | Dernier commit |
|---------|--------|----------------|
| `main` | **137 commits** | 2026-04-27 |
| `audit-complet-suite-certus` | 137 commits | 2026-04-27 |
| `fab` | 81 commits | 2026-05-11 |
| `certus` | 51 commits | — |

Aucune branche n'est en avance sur `refactor-corridors-mixins` : tout le travail depuis avril y est concentré.

### Pourquoi c'est un risque réel

- Le dossier est dans `D:\drivefl\` — un répertoire synchronisé cloud. Une synchronisation qui déraille sur un `.git` de 66 Mo pendant une écriture peut corrompre le dépôt. Le travail non commité n'a alors **aucun filet**.
- La CI (`lint.yml`) ne se déclenche que sur `pull_request` et `push` vers `main`. Les **137 commits n'ont donc jamais été validés par la CI**. Le build Windows (`release-windows.yml`) cible `main`/`master` — la version qui serait releasée aujourd'hui date d'avril.
- Des fichiers sont supprimés sans commit : `certus/physics/certus_opt_gradients.py`, `certus_opt_gradients_compat.py`, `tests/unit/test_strict_material_substrate_boundary.py`. Un `git checkout` malencontreux les ressusciterait, ou pire, un `git stash` les perdrait.

### Pollution du dépôt

**69 fichiers `desktop.ini`** sont trackés par git (artefacts Windows/Drive), et 195 apparaissent comme modifiés à chaque `git status`. Ils cassent aussi les refs :

```
warning: ignoring broken ref refs/heads/desktop.ini
warning: ignoring broken ref refs/remotes/origin/desktop.ini
warning: ignoring broken ref refs/tags/desktop.ini
```

Ces refs cassées ne sont pas cosmétiques : elles font échouer silencieusement certaines commandes git (`git log --all -- .env` renvoie vide alors que le fichier est bien dans l'arbre — c'est ce qui a failli masquer la fuite du point 1).

### Actions

1. Ajouter `desktop.ini` et `.env` au `.gitignore`, puis `git rm --cached` sur les 69 `desktop.ini` trackés.
2. Supprimer les refs cassées : `git for-each-ref | grep desktop.ini` puis `git update-ref -d` sur chacune.
3. Committer le travail en cours en lots thématiques (physique / UI / tests), pas en un commit géant.
4. Fusionner vers `main` pour redonner un sens à la CI, ou faire pointer la CI sur la branche de travail.

---

## 3. 🟠 ÉLEVÉ — Bug de convention de signe dans le TMM monocouche

### Constat

`certus/physics/certus_tmm_matrix.py:19` — `compute_complex_phase_components(phi_r, phi_i)` calcule en réalité `cos(φr + i·φi)` et `sin(φr + i·φi)`, alors que sa docstring annonce la convention Macleod `n̂ = n − ik` (soit `φ = φr − i·φi`).

Vérifié numériquement :

| φr, φi | `sin` retourné | attendu (n−ik) | conj. (n+ik) |
|--------|----------------|----------------|--------------|
| 0,7 · 0,35 | 0,684080 **+** 0,273194j | 0,684080 − 0,273194j | 0,684080 + 0,273194j ✓ |
| 2,1 · 1,2 | 1,562975 **−** 0,762046j | 1,562975 + 0,762046j | 1,562975 − 0,762046j ✓ |

Le helper renvoie donc systématiquement le **conjugué** de ce que sa docstring promet.

### Deux appelants, deux conventions opposées

| Appelant | φi transmis | Résultat |
|----------|-------------|----------|
| `certus_tmm_oblique.py:160` et `:550` | `phi.imag` — partie imaginaire **signée** (négative) | ✅ correct, le signe se compense |
| `certus_tmm_single_layer.py:43` | `k·k_film·d` — grandeur **positive** | ❌ faux dès que k > 0 |

Dans le chemin monocouche, le conjugué de `sin(φ)` est ensuite combiné à `1/n̂` **non conjugué** : l'incohérence ne s'annule pas et se propage dans R.

### Impact mesuré

Transcription fidèle de `calculate_RT_single_layer_single` (lignes 23–94) comparée à une implémentation TMM de référence indépendante :

| Cas | CERTUS | Référence | Écart |
|-----|--------|-----------|-------|
| n=2,35 · k=0 (quart d'onde) | 0,323004795 | 0,323004795 | 5,6·10⁻¹⁷ ✅ |
| n=2,00 · k=0,05 · d=100 nm | 0,143167 | 0,132926 | **+1,0 pt** |
| n=1,50 · k=3,00 · d=60 nm | **1,000000** (saturé) | 0,608289 | **+39,2 pts** |
| n=0,15 · k=3,50 · d=40 nm (métal) | 0,934237 | 0,855078 | **+7,9 pts** |

Exact pour k = 0, faux pour tout matériau absorbant — et le clamp `min(1.0, R)` masque le débordement en le transformant en un R=1 physiquement plausible plutôt qu'en une valeur aberrante détectable.

### Correctif validé

Une seule ligne, `certus_tmm_single_layer.py:41` :

```python
# actuel
phi_i = k * n_film_imag * thickness_nm
# corrigé
phi_i = -k * n_film_imag * thickness_nm
```

Après correction, les 4 cas ci-dessus retombent sur la référence à la précision machine.

### Portée réelle : contenue, mais piégeuse

`calculate_RT_single_layer_single` **n'est pas dans le chemin de production**. La chaîne réellement utilisée pour l'ajustement d'indice est :

```
calculate_reflection_array → calculate_reflection_single → calculate_transmission_single
```

et `calculate_transmission_single` (ligne 136) utilise l'arithmétique complexe native avec `n_film = complex(n, -k)` — **correcte**. De même, `compute_TMM_single_point_k0` (multicouche) et `compute_RT_from_matrix` sont conformes à Macleod éq. 2.96, avec un garde-fou explicite `if n_c.imag > 0: n_c = conj(n_c)`.

Mais la fonction fautive est :

- exportée dans `certus/physics/certus_tmm_core.py:__all__` et dans `_certus_physics_impl.py` — surface d'API publique ;
- utilisée dans `tests/performance/test_kernel_benchmarks.py:82` avec **k = 0,018**, donc sur une valeur fausse ;
- annotée `─── LOCKED ─── Validated by test_tmm_coherence.py` et `Macleod convention (+1j, n-ik). DO NOT MODIFY` — l'annotation affirme précisément ce qui est faux.

`tests/property/test_physics_invariants.py:12` documente d'ailleurs qu'on l'évite délibérément (« On utilise `calculate_transmission_single` et NON `calculate_RT_single_layer_single` »), mais pour une raison de typage Numba, pas de justesse.

### Pourquoi les tests ne l'ont pas vu

`tests/core/test_certus_physics_tmm.py:34` teste le helper **uniquement à φr = π/2**, le seul point où `cos(φr) = 0` annule `sin_phi_imag`. La seule assertion sensible au signe est :

```python
assert cos2_i < 0.0   # "Negative imaginary part for Macleod convention"
```

Or la convention Macleod correcte donnerait ici `+sin(π/2)·sinh(1) = +1,175`, donc **positif**. Le test verrouille activement le mauvais signe, commentaire à l'appui.

`tests/unit/test_physics_fresnel.py:120` ne teste que φi = 0 — cas où les deux conventions coïncident.

**À corriger en même temps que la ligne**, sinon la suite de tests rejettera le correctif.

### Ce qui est confirmé sain

- `compute_RT_from_matrix` : conforme à Macleod éq. 2.96, garde `|Y| < 1e-14`, clamp `T ≥ 0`.
- `compute_TMM_single_point_k0` / `_exact` : matrice caractéristique correcte, ordre de multiplication cohérent avec la convention déclarée (index 0 = substrat), calcul du R arrière par produit inverse — correct.
- Conservation d'énergie : **0 violation** de `R + T ≤ 1` sur 2 000 empilements aléatoires (1 à 8 couches, n ∈ [1,3 ; 4,0], k ∈ [0 ; 0,6], λ ∈ [380 ; 1000] nm).
- `compute_complex_phase_components` : le clamp `φi ∈ [−700, 700]` évite bien l'overflow de `exp()` sur couches épaisses absorbantes.
- Jacobien Sellmeier (`certus_substrate_sellmeier.py:390`) : dérivées `∂n²/∂B` et `∂n²/∂L` analytiquement correctes, protection `np.maximum(λ²−L², 1e-15)` contre la singularité de pôle.

---

## 4. 🟠 ÉLEVÉ — Santé du code : la dette est masquée, pas absente

### Le chiffre affiché n'est pas le vrai chiffre

```
ruff check .  (config du projet)          →     62 erreurs
ruff check .  (mêmes règles, sans ignore) → 12 157 erreurs
```

Le `pyproject.toml` contient un `extend-ignore` de **73 règles**, présenté comme une « whitelist des violations existantes » avec nettoyage par lots. En pratique la liste ne se vide pas : elle absorbe la dette au lieu de la révéler. La CI passe au vert sur 62 erreurs pendant que 12 157 restent.

### Répartition réelle (certus/ + tests/ + racine, cible py3.14)

| Règle | Nombre | Nature |
|-------|--------|--------|
| F401 unused-import | **5 473** (dont 4 844 dans `certus/`) | imports morts |
| F405 undefined-local-with-import-star | 3 161 | usage via `import *` |
| E402 module-import-not-at-top | 782 | imports différés |
| I001 unsorted-imports | 764 | cosmétique |
| **F822 undefined-export** | **202** | `__all__` référence des noms inexistants |
| F811 redefined-while-unused | 114 | redéfinitions |
| **F403 wildcard imports** | **80** | |
| **F821 undefined-name** | **67** | risque de `NameError` |

Seules **22 catégories** sont auto-corrigeables : le reste demande une décision humaine.

### Les trois règles qui comptent vraiment

**F822 — `__all__` cassés (202 occurrences)**, concentrés sur 4 fichiers :

```
certus/ui/certus_ui_widgets_factory.py  : 71
certus/ui/certus_base_app.py            : 60
certus/ui/certus_ui_utils.py            : 54
certus/ui/certus_ui.py                  : 17
```

Exemple : `certus_base_app.py:50` exporte `apply_theme_to_plots`, `get_plot_style_config`, `CertusThemeToggle` — qui n'existent pas. Tout `from certus.ui.certus_base_app import *` lève un `AttributeError` à l'import. Ces `__all__` ont vraisemblablement été écrits avant un déplacement de symboles et jamais resynchronisés.

**F821 — noms indéfinis** : 3 dans `certus/physics/gradient_analytic.py` (`Target`, `Callable`, `cost_numba_fast` — probablement des imports perdus lors de l'extraction depuis `certus_opt_gradients.py`), 63 dans `compute_extracted.py` (script jetable). La règle est dans `extend-ignore` avec la justification « mostly false positives from delayed imports » — c'est vrai pour certains, mais pas pour `gradient_analytic.py`, qui est un module de production.

**F403/F405 — imports étoile** : `RAPPORT_SESSION_WILDCARD_IMPORTS.md` et le commentaire `"F403", "F405", # wildcard imports — #15 will eradicate` annoncent l'éradication. Il en reste 80 sites d'import et 3 161 usages, dont 17 dans `certus/core/_certus_physics_impl.py` (module physique central) et 8 dans `certus/ui/certus_base_app.py`.

### La suite de tests ne tourne pas en CI

226 fichiers de test, 56 373 lignes. Ce que la CI exécute :

```yaml
# release-windows.yml:93
python -m pytest tests/unit/test_seed_contract_global.py \
                 tests/unit/test_certus_services.py \
                 tests/unit/test_release_guardrails.py -q
```

**3 fichiers sur 226.** `lint.yml` n'exécute aucun test — uniquement ruff, un audit de symboles morts et un audit lambda-connect.

Un investissement de 56 000 lignes de tests qui ne protège rien en intégration continue : c'est probablement le meilleur rapport valeur/effort du projet à débloquer.

### Couverture : artefact périmé

Le `.coverage` date du **13 juillet** et pointe vers `D:\...\CERTUS\0807\` — un **autre dossier de travail**. Il mesure 268 fichiers pour 47 672 lignes exécutées. Les rapports parlent de « 100% test coverage » (commit `56accc4`) ; cette affirmation n'est vérifiable sur aucun artefact courant.

### Note d'environnement

Le projet exige Python ≥ 3.14.5 et utilise de la syntaxe 3.14 exclusive (PEP 758 — `except A, B:` sans parenthèses, présent dans 14 modules de `certus/`, dont `_certus_physics_impl.py`, `certus_core.py` et `certus_optimizers.py`). Les tests n'ont donc pas pu être exécutés dans l'environnement d'audit (Python 3.10, pas de PyQt6). **Toutes les conclusions physiques du §3 reposent sur une transcription fidèle du code et une vérification numérique indépendante, pas sur l'exécution du code du projet.** Ruff, lui, a bien analysé la totalité en cible py314 : **0 erreur de syntaxe**.

---

## 5. 🟡 MOYEN — Architecture

### Volumétrie

| Zone | Fichiers | Lignes |
|------|----------|--------|
| `certus/` | 281 | 156 488 |
| `tests/` | 226 | 56 373 |
| racine + `scripts/` | 79 | 27 126 |
| **Total source** | **360** | **183 614** |

Répartition interne de `certus/` :

| Package | Fichiers | Lignes | Part |
|---------|----------|--------|------|
| `ui` | 109 | 60 747 | 39 % |
| `spline` | 31 | 31 010 | 20 % |
| `core` | 40 | 20 615 | 13 % |
| `utils` | 34 | 17 401 | 11 % |
| `workers` | 27 | 11 956 | 8 % |
| `physics` | 25 | 11 224 | 7 % |
| `metal` | 3 | 2 529 | 2 % |
| `domain` | 12 | 1 006 | 0,6 % |

Le cœur scientifique (`physics`) représente 7 % du code ; l'UI, 39 %. Pour une application PyQt de métrologie c'est plausible, mais `certus/ui` mélange visiblement présentation et logique — `certus_re_excel_mixin.py` fait 2 301 lignes.

### Absence de `__init__.py`

Seul `certus/domain/` en possède. Les 7 autres sous-packages (`core`, `metal`, `physics`, `spline`, `ui`, `utils`, `workers`) fonctionnent en packages implicites (PEP 420). Conséquences :

- `pyproject.toml` déclare `packages = ["certus"]` — un `pip install` ne récupérerait aucun sous-module. Le projet n'est installable qu'en mode source.
- Aucun point d'ancrage pour une API publique par package ni pour un contrôle des imports.

Le contraste avec `certus/domain/` (structure DDD complète : `entities`, `events`, `services`, `value_objects`, tous avec `__init__.py`) suggère une migration DDD commencée puis interrompue — `domain/` ne pèse que 1 006 lignes, soit 0,6 % du code.

### Inversions de couches

Graphe de dépendances entre sous-packages (nombre d'imports) :

```
ui      → utils   244        utils → ui       12   ⚠️ cycle
ui      → core    115        core  → utils   109
core    → utils   109        utils → core     23   ⚠️ cycle
workers → utils   104        core  → workers  10   ⚠️ cycle
workers → core     97
spline  → utils    39        spline → ui      14
ui      → workers  39        utils  → spline   3   ⚠️ cycle
core    → physics  29        physics → core   22   ⚠️ cycle
```

Trois inversions problématiques :

1. **`utils` → `ui` (12 imports)** — une couche utilitaire qui dépend de la couche présentation. Dont `certus/utils/certus_curve_smoother.py:29-30` et `certus/utils/certus_export.py:13`, en import **direct** (non différé) : importer `certus.utils.certus_export` charge PyQt6. Les autres sont des imports différés dans des fonctions (`certus_badges.py`, `certus_progress_tracker.py`, `errors.py`) — contournement du cycle, pas résolution.
2. **`core` → `workers` (10 imports)** — le noyau dépend de la couche d'exécution : `certus_design_core.py`, `certus_re_solvers.py`, `certus_strat_config.py` importent des DTO de workers. Les DTO devraient vivre dans `core` ou `domain`.
3. **`physics` ↔ `core` (29/22)** — cycle entre calcul et noyau.

Le commit `ae6557e` (« keep metrology independent from PyQt runtime ») montre que le sujet est identifié ; le travail n'est pas terminé.

### Monolithes résiduels

| Fichier | Lignes |
|---------|--------|
| `certus_opt_kernels_old_utf8.py` (racine) | 4 605 |
| `certus/spline/certus_index_spline_corridors.py` | 3 129 |
| `CERTUS_METAL_BILAYER.py` (racine) | 2 850 |
| `CERTUS_METAL_SINGLE.py` (racine) | 2 721 |
| `certus/spline/spline_workers.py` | 2 523 |
| `certus/ui/certus_base_app.py` | 2 478 |
| `certus/ui/certus_re_excel_mixin.py` | 2 301 |

Les deux `CERTUS_METAL_*.py` sont à la racine alors que `certus/metal/` existe (3 fichiers, 2 529 lignes) — la migration est à moitié faite.

### Encombrement de la racine

**234 entrées** à la racine du projet, dont :

- **58 fichiers `.md`** de rapports de session (hors le présent audit) : `MARATHON_*` (10), `SESSION*` (12), `OPTION_*` (4), `PLAN_*` (4), `QUICK_WIN*` (3)…
- **29 scripts jetables** : `fix_imports.py`, `fix_core_imports.py`, `fix_excel_imports.py`, `fix_re_helpers_bulk.py`, `temp.py`, `temp_ast_checker.py`, `scratch_benchmark.py`, `old_ui.py`, `old_physics_impl.py`, `split_tmm.py`, `deduplicate.py`, `patch_presenter.py`…
- Un répertoire nommé `MagicMock` — créé par un test qui a écrit sur le disque via un mock mal isolé.
- Deux fichiers non décodables en UTF-8 : `old_physics_impl.py`, `old_ui.py`.

Ces 58 rapports décrivent un travail réel, mais leur accumulation à la racine rend le projet illisible pour un nouvel arrivant — et pour un assistant IA, qui les lira comme de la documentation courante alors qu'ils sont des journaux historiques souvent contradictoires entre eux.

---

## 6. Ce qui fonctionne bien

Il serait injuste de ne lister que les problèmes.

- **Le cœur TMM est correct.** Les chemins de production (`compute_TMM_single_point_k0`, `compute_RT_from_matrix`, `calculate_transmission_single`) sont conformes à Macleod, avec référence explicite à l'équation 2.96, garde-fous sur les indices (`if n_c.imag > 0: conj`), protections contre les divisions par zéro et clamps anti-overflow. La conservation d'énergie tient sur 2 000 empilements aléatoires.
- **`compute_RT_from_matrix` comme source unique de vérité** pour l'extraction R/T, avec délégation depuis toutes les variantes TMM : c'est exactement la bonne décision d'architecture pour du code physique.
- **Les marqueurs `LOCKED`** identifiant le code validé par tests sont une pratique excellente pour du calcul scientifique — à condition qu'ils disent vrai (cf. §3).
- **La CI de release est sérieuse** : vérification des hashs sha256 du lockfile, `compileall`, smoke test offscreen, build gelé PyInstaller, snapshot KPI.
- **Le domaine DDD** (`certus/domain/optical/`) est proprement structuré. C'est la bonne direction, juste inachevée.
- **La configuration ruff est documentée** : chaque règle ignorée renvoie à une action de nettoyage planifiée. L'intention est bonne, c'est l'exécution qui a décroché.

---

## 7. Plan d'action priorisé

### Aujourd'hui

| # | Action | Effort |
|---|--------|--------|
| 1 | **Révoquer la clé API Anthropic** sur console.anthropic.com | 5 min |
| 2 | `.gitignore` ← `.env`, `desktop.ini`, `*.log`, `*.jsonl`, `.coverage` | 10 min |
| 3 | `git rm --cached .env` + les 69 `desktop.ini` | 10 min |
| 4 | Purger `.env` de l'historique distant (`git filter-repo`) | 30 min |
| 5 | Committer les 130 fichiers en cours, par lots thématiques | 1–2 h |

### Cette semaine

| # | Action | Effort | Gain |
|---|--------|--------|------|
| 6 | Corriger le signe ligne 41 de `certus_tmm_single_layer.py` **et** l'assertion `cos2_i < 0.0` du test | 30 min | Justesse physique |
| 7 | Ajouter un test de non-régression : TMM monocouche absorbant vs référence analytique, k ∈ {0 ; 0,05 ; 3,0} | 1 h | Verrou réel |
| 8 | Activer `pytest tests/` complet dans `lint.yml` | 30 min | 226 fichiers de tests enfin utiles |
| 9 | Nettoyer les refs git cassées (`desktop.ini`) | 15 min | `git log --all` redevient fiable |
| 10 | Fusionner `refactor-corridors-mixins` → `main` | 1 h | CI reconnectée au code réel |

### Ce mois

| # | Action | Effort | Gain |
|---|--------|--------|------|
| 11 | Corriger les 202 `F822` sur les 4 fichiers UI, puis **retirer F822 de `extend-ignore`** | 3 h | Imports `*` fonctionnels |
| 12 | Corriger les 3 `F821` de `gradient_analytic.py` | 30 min | `NameError` évités |
| 13 | `ruff check --fix` sur F401/I001 par répertoire, avec revue de diff | 4 h | −6 200 violations |
| 14 | Ajouter les `__init__.py` manquants + `packages = find:` dans pyproject | 1 h | Projet installable |
| 15 | Archiver les 58 `.md` dans `docs/archive/` et les 29 scripts dans `scripts/legacy/` | 1 h | Racine lisible |
| 16 | Déplacer les DTO `workers` → `domain` pour casser le cycle `core` ↔ `workers` | 4 h | Couches respectées |
| 17 | Rendre `certus/utils/certus_export.py` et `certus_curve_smoother.py` indépendants de PyQt | 3 h | Cycle `utils` ↔ `ui` cassé |

### Recommandation de méthode

La règle la plus utile pour la suite : **`extend-ignore` ne doit jamais grandir.** Chaque nouvelle règle ajoutée transforme une dette visible en dette invisible. Mieux vaut un CI rouge honnête sur 12 157 violations qu'un CI vert sur 62 — parce que le vert actuel a laissé passer 202 `__all__` cassés et 67 noms indéfinis sans que personne ne soit alerté.

---

## Annexe — Méthode

**Outils** : ruff 0.16.1 (cible py314, règles `E,F,I,B,UP,RUF,PT,PERF`), git, analyse AST maison du graphe d'imports, coverage.py pour la lecture de `.coverage`, vérification numérique NumPy indépendante pour la physique.

**Limite** : l'environnement d'audit tourne sous Python 3.10 sans PyQt6 ni Numba ; le projet exige Python ≥ 3.14.5. La suite de tests n'a pas pu être exécutée. Les conclusions du §3 reposent sur (a) une transcription littérale des lignes 23–94 et 136–205 de `certus_tmm_single_layer.py` et des lignes 19–48 de `certus_tmm_matrix.py`, et (b) une comparaison avec une implémentation TMM de référence écrite indépendamment. Le correctif proposé a été validé numériquement sur cette transcription, mais **doit être confirmé par exécution réelle** avant intégration.

**Chiffres re-vérifiés** : volumétrie (`wc -l` sur listes de fichiers explicites), violations ruff (somme des `--statistics`), divergences git (`rev-list --left-right --count`), présence distante du `.env` (`git cat-file -e origin/…:.env` + `branch -r --contains`), visibilité du dépôt (métadonnée `repository_public` de la page GitHub).
