# REPRISE — fuites d'état entre tests (isolation)

**Session du 2026-08-02.** Pendant : `docs/REPRISE_PERF.md` (performance).
Ce document couvre **l'isolation des tests**, pas la performance.

> ✅ **Ce travail résout deux lignes du tableau « Ce qui est déjà rouge » de
> `docs/REPRISE_PERF.md`** (`TestREAppSkeletonLoaders` et les 4 échecs de
> `tests/unit/test_certus_ui.py`). Ce tableau a été mis à jour en conséquence.

---

## 0. État en reprenant

✅ **Le correctif est appliqué et commité** sur `refactor-corridors-mixins`
(2 fichiers de **test** uniquement, aucun code de production) :
`tests/ui/test_ui_module_imports.py` et `tests/unit/test_manual_rmse_grid_integration.py`.
**Rien à appliquer** — attaquer directement le « reste à faire » en §2.

Pour vérifier que tout est en place :

```bash
.venv\Scripts\python.exe -m pytest tests/ -q --no-cov -k "re_ or reverse or objectives" -p no:cacheprovider
```

Attendu : **637 passed, 4 skipped**.

Le worktree `.claude/worktrees/admiring-proskuriakova-b242cf` a servi à ce travail ; il est
resté sur `f6f9102` et **n'est plus nécessaire** — supprimable
(`git worktree remove --force .claude/worktrees/admiring-proskuriakova-b242cf`).

---

## 1. Ce qui est fait

### 1.1 La fuite d'état principale

`tests/unit/test_certus_re.py::TestREAppSkeletonLoaders::test_re_app_skeletons_methods`
échouait avec `ValueError: not enough values to unpack (expected 2, got 0)` en sélection
large, et passait isolément.

**Coupable :** `tests/ui/test_ui_module_imports.py::test_ui_module_importable[certus.ui.certus_re_state_mixin]`

**Mécanisme complet :**

1. `tests/headless/test_re.py` importe `CERTUS_RE`. `CertusREApp` hérite du mixin défini
   dans l'objet-module **M1** de `certus.ui.certus_re_state_mixin` ; donc
   `CertusREApp._remove_re_skeletons.__globals__` **est** `M1.__dict__`.
2. `test_ui_module_importable` faisait `sys.modules.pop(name)` puis ré-importait, pour
   forcer une exécution fraîche du module. Résultat : un **second** objet-module **M2**
   remplace M1 dans `sys.modules`, et n'était jamais restauré.
3. Le test RE fait
   `monkeypatch.setattr("certus.ui.certus_re_state_mixin.remove_skeleton_loader", mock)`
   → il patche **M2**, alors que la méthode vivante lit dans **M1**.
4. Le vrai `remove_skeleton_loader` s'exécute donc sur un `MagicMock`.
   `getattr(mock, "_certus_skeleton", None)` renvoie un MagicMock (non-`None`), et
   `loader, filt = data` dépaquette un MagicMock dont `__iter__` est vide → `ValueError`.

C'est aussi la cause des **4 échecs de `tests/unit/test_certus_ui.py`** : même patron de
`monkeypatch.setattr("<module>.<nom>", …)` sur un module devenu orphelin.

Repro minimale (échouait avant, passe après) :

```bash
.venv\Scripts\python.exe -m pytest tests/headless/test_re.py "tests/ui/test_ui_module_imports.py::test_ui_module_importable[certus.ui.certus_re_state_mixin]" "tests/unit/test_certus_re.py::TestREAppSkeletonLoaders" -q --no-cov -p no:cacheprovider
```

**Correctif** — `tests/ui/test_ui_module_imports.py` : fonction `_restore_module()` + bloc
`finally` qui remet l'objet-module d'origine dans `sys.modules` **et** réaffecte l'attribut
sur le package parent (`import_module` le rebinde aussi). Si le module n'était pas encore
importé, on ne restaure rien — l'import frais est alors l'état normal. Le test garde tout
son pouvoir de détection (il exécute bien le module) ; aucune dépendance d'ordre ajoutée.

### 1.2 Second bug, indépendant, corrigé au passage

`tests/unit/test_manual_rmse_grid_integration.py` →
`AttributeError: 'function' object has no attribute 'get_call_template'`.

Le test posait `NUMBA_DISABLE_JIT=1` **après** l'import des modules. Les kernels déjà
décorés restent des `Dispatcher` : la variable ne les « dé-jitte » pas, elle ne s'applique
qu'aux compilations **suivantes** — y compris celles que Numba déclenche en interne pour
ses propres `@overload` (`np.empty_like`). Sur cache Numba **froid**, `clip_to_bounds` doit
encore être compilé et l'overload retombe sur une fonction Python nue → crash.

Masqué par un `__pycache__` chaud, donc invisible sur une machine rodée et fatal sur une
machine neuve ou en CI. Reproductible à volonté :

```bash
NUMBA_CACHE_DIR="$(mktemp -d)" .venv/Scripts/python.exe -m pytest tests/unit/test_manual_rmse_grid_integration.py -q --no-cov -p no:cacheprovider
```

**Correctif :** suppression des 4 lignes `monkeypatch.*env("NUMBA_DISABLE_*")`, remplacées
par un commentaire expliquant pourquoi il ne faut pas les remettre. Vérifié en cache froid
**et** chaud.

### 1.3 Vérifications passées

| Vérification | Résultat |
|---|---|
| `pytest tests/ -k "re_ or reverse or objectives"` (commande officielle) | **637 passed, 4 skipped** ✅ |
| Test cible isolément | ✅ |
| `tests/ui/test_ui_module_imports.py` (108 tests) | ✅ |
| `test_ui_module_imports + test_certus_ui + test_certus_re` | **245 passed** ✅ |
| Suite complète `pytest tests/ -q --no-cov` **avec** correctif | 2774 passed, 8 skipped, **1 failed** (→ §2.1) |

---

## 2. Reste à faire

### 2.1 [P1] `test_spline_basis_cache_eviction_and_lock` — test périmé

`tests/unit/test_metal_optimizations.py:201` — **seul échec restant** de la suite complète.

```
assert len(SplineBasisCache._cache) < 500
AssertionError: assert 510 < 500
```

**Ce n'est pas une fuite d'ordre : il échoue de façon déterministe, même isolément.**
Le test est en retard sur un refactor volontaire du code de production :

- `certus/physics/certus_optical_models.py:371` → `_MAX_ENTRIES = 512`
- `certus/physics/certus_optical_models.py:485` → vrai LRU :
  `while len(cls._cache) > cls._MAX_ENTRIES: cls._cache.popitem(last=False)`
- Le commentaire ligne 476 documente explicitement l'abandon de l'ancien garde-fou
  `if len(_cache) > 500: _cache.clear()`.

Le test insère 510 clés uniques après `clear()`. Avec un plafond à 512, aucune éviction
n'a lieu et la taille finale est 510 : l'assertion encode l'**ancien** comportement.

Correctif proposé, à valider :

```python
# Le cache est borné par un LRU, il n'est plus vidé entièrement.
assert len(SplineBasisCache._cache) <= SplineBasisCache._MAX_ENTRIES
```

Et pour tester réellement l'éviction, boucler sur `_MAX_ENTRIES + 50` clés (510 < 512 ne
déclenche jamais `popitem`), puis vérifier que la clé la plus ancienne a disparu.
**Question ouverte : ce test doit-il vérifier l'éviction LRU, ou seulement le bornage ?**

### 2.2 [P2] Auditer les autres manipulations de `sys.modules`

Même classe de bug, non traitée :

- `tests/unit/test_pure_imports.py:19-21` et `:43-45` — `del sys.modules[mod]` pour tout
  module contenant `"certus_core"`, **sans restauration**. Inoffensif aujourd'hui
  (ce fichier passe après ses victimes potentielles dans l'ordre alphabétique), mais tout
  renommage de fichier peut inverser l'ordre. → même patron `_restore_module()`.
- `tests/unit/test_materials_data.py:39,56` — `importlib.reload(md)` sans restauration.
- `tests/unit/test_certus_core_coverage_boost.py:372-379` — remplace
  `sys.modules["PyQt6.QtSvgWidgets"]` par `None` ; la restauration existe, à revérifier.

Envisager un fixture partagé dans `tests/conftest.py` (`sys_modules_sandbox`) plutôt que
de dupliquer `_restore_module` dans chaque fichier.

### 2.3 [P3] Garde-fou anti-régression

Rien n'empêche de réintroduire une fuite. Piste : fixture `autouse` comparant l'identité
(`id()`) des objets-modules `certus.*` avant/après chaque module de test, et échouant si
un objet a été remplacé. À peser : coût en temps d'exécution vs bénéfice.

### 2.4 [P4] Crash natif intermittent — à surveiller seulement

Lors d'un run de suite complète : `Windows fatal exception: access violation` dans un
thread `_bg_warmup` (`certus/core/_certus_physics_impl.py:1444`), vers
`tests/unit/test_certus_metal_single_smoke.py`. **Non reproduit** au run suivant (la suite
est ensuite allée au bout). Probable course entre le warmup Numba en arrière-plan et Qt.
À ne traiter que si ça revient.

### 2.5 Décisions en attente

- **Committer / pousser ?** Rien n'est commité. Le remote `origin` est
  `https://github.com/nikonvr/CERTUS.git` (**public**) et le hook d'auto-push est
  désactivé — cf. l'avertissement d'`AGENTS.md`.
- **Où appliquer ?** Porter le patch sur `refactor-corridors-mixins`, ou garder une
  branche dédiée ?
- Le run de suite complète **sans** correctif (référence chiffrée) a été interrompu à
  71 % ; la comparaison avant/après sur la suite entière n'est donc pas bouclée. La
  comparaison ciblée (245 tests) l'est.

---

## 3. Pièges rencontrés (à ne pas refaire)

- Le worktree créé par l'outil était issu du **tout premier commit** (`38ffb68`, avril),
  soit 170 commits de retard — il ne contenait même pas le test en cause. Vérifier
  `git log --oneline -1` dans un worktree avant de conclure quoi que ce soit.
- Le cache Numba chaud **masque** des bugs de compilation. Pour un audit honnête :
  `NUMBA_CACHE_DIR="$(mktemp -d)"`.
- Confirmé : ne pas lancer deux sessions pytest en parallèle sur ce dépôt
  (cf. `docs/REPRISE_PERF.md`).
