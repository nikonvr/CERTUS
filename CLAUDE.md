# CLAUDE.md — CERTUS Optical Suite

Contexte projet pour Claude Code. Lis ce fichier avant toute modification.

## 🔴 PAR OÙ COMMENCER — état au 2026-08-08

Quatre documents, et rien d'autre. **Les journaux de session sont supprimés dès qu'ils
cessent d'aider à décider** — 58 en août 2026, puis 21 entrées le 2026-08-08. Ils se
contredisaient et pointaient vers du code qui n'existe plus. `git log` les retrouve.

| Document | Ce qu'il contient |
|---|---|
| [`AGENTS.md`](AGENTS.md) | **À lire en premier.** Vérification d'environnement, onze interdits absolus, sept pièges documentés, boucle de travail. |
| [`docs/PLAN_STRAT.md`](docs/PLAN_STRAT.md) | **STRAT — ce qu'il reste à faire, et rien d'autre.** Point de référence mesuré, décisions bloquantes, six actions ordonnées, règles gravées, et ce qu'il ne faut pas refaire. |
| [`docs/PROPOSITIONS_CLAUDE.md`](docs/PROPOSITIONS_CLAUDE.md) | **Fidélité physique du simulateur.** Les spécifications mesurées de la machine de dépôt, les quatre écarts au réel, et le verdict chiffré sur chacun. |
| [`docs/JOURNAL_GEMINI.md`](docs/JOURNAL_GEMINI.md) | **État vérifié** — ce qui tient, ce qui ne tient pas — et les règles de tenue du journal, avec le modèle d'entrée. |

Et la doc technique destinée à la communauté :
[`pages/CERTUS_STRAT.html`](pages/CERTUS_STRAT.html) — algorithmes, équations, et la
**méthode** (§2.1quinquies).

### 👤 Ce que le physicien a tranché le 2026-08-08

Ces nombres gouvernent le modèle de monitoring. Détail dans `docs/PROPOSITIONS_CLAUDE.md` §1.

- Plateau **240 tr/min**, ~1 m de diamètre, témoin de 20 mm au bord ⇒ **transit 1,6 ms**.
- **Trois positions par tour** : témoin, noir, vide ⇒ `T = (S−D)/(V−D)`, auto-référencé à 4 Hz.
- Dépôt ~0,5 nm/s ⇒ **un échantillon tous les 0,125 nm**. Le modèle en prend un tous les
  4,76 nm : **38× trop grossier**.
- Bruit de lecture ±0,05 point, largeur totale 0,10 — **le tirage du modèle est correct**.
- Le « 5 σ » du seuil de détection signifiait *« bien au-dessus du bruit »*, **pas** une
  exigence physique. Le seuil est donc à recalibrer sur la borne anti-fabrication.
- 🔴 **Ne pas modéliser σ(T), la grenaille ni le bruit multiplicatif.** Un modèle simple et
  mesuré vaut mieux qu'un modèle riche et inventé.

### Vérifier l'environnement — une minute, et ce n'est pas optionnel

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
dir .git\hooks\post-commit*
```

Le chemin affiché doit être sous `C:\dev\gemini` — sinon tu mesures un autre snapshot (§5.5).
**Plusieurs copies de ce dépôt coexistent sur la machine** : c'est la copie `C:\dev\gemini`
qui fait foi ici, et aucune autre.

Le hook `post-commit` a été **désactivé dans cette copie** (renommé `post-commit.DESACTIVE`).
Committer ici ne publie donc rien. Dans les autres copies il est **ACTIF** et pousse chaque
commit vers le dépôt **public** `nikonvr/CERTUS` — `--no-verify` ne le neutralise pas.
**Ne le réactive pas.**

### 🟢 La règle de méthode, et elle a été payée trois fois

> **Une grandeur de bruit qui ne varie pas avec le bruit est un artefact. Sans exception.**

📏 En une journée, le même taux de plantage par couche a valu 28 %, puis 1,3 %, puis 1,47 % à
σ → 0. **Deux fois sur trois ce n'était pas de la physique**, et c'est le balayage de σ — quelques
secondes — qui l'a montré chaque fois. Corollaire : **vérifie sur quelle SOURCE un critère se
prononce.** Les trois défauts les plus coûteux étaient de cette forme — le signal propre au lieu du
signal bruité, la grille d'affichage (1 nm) au lieu de la grille de balayage (2 nm), et une matrice
de zéros au lieu de l'empilement réel. Détail dans `pages/CERTUS_STRAT.html` §2.1quinquies.

### Ce qui reste ouvert, en une ligne chacun

- **Isolation des tests** — une fuite `sys.modules` faisait échouer en sélection large des tests
  qui passent isolément. Cause racine corrigée, audit restant :
  [`docs/REPRISE_TESTS_ISOLATION.md`](docs/REPRISE_TESTS_ISOLATION.md).
- **Performance** — 📏 mesuré le 2026-08-04 : **il n'y a PAS de ×2 disponible** dans les pistes
  documentées. Le seul gain réel acquis est −10 % sur STRAT. Le fossé machine va de ×1 à ×3,2
  selon les modules, pas ×7-10. Référence : [`docs/REPRISE_PERF.md`](docs/REPRISE_PERF.md), dont
  les temps absolus datent d'avant le déménagement hors Google Drive.
- **Amélioration générale** — [`docs/PLAN_AMELIORATION.md`](docs/PLAN_AMELIORATION.md) : dette de
  lint, tests absents de la CI, six chantiers ordonnés.

---

## 1. Ce qu'est CERTUS

Suite scientifique de **couches minces optiques** : détermination d'indice, design d'empilements, stratégie de dépôt. Application de bureau **PyQt6** + noyau de calcul **NumPy/SciPy/Numba**.

- `certus-optical-suite 26.05.0` — licence propriétaire
- **Python ≥ 3.14.5 obligatoire** (utilise PEP 758 : `except A, B:` sans parenthèses, dans 14 modules)
- Cible principale : Windows. Build gelé PyInstaller.
- 183 600 lignes de source · 56 400 lignes de tests · 2 240 tests collectés

### Points d'entrée (racine)

| Fichier | Rôle |
|---------|------|
| `CERTUS_HUB.py` | Lanceur unifié — **doit rester une couche de composition pure** |
| `CERTUS_DESIGN.py` | Design d'empilements |
| `CERTUS_STRAT.py` | Stratégie de dépôt |
| `CERTUS_RE.py` | Rétro-ingénierie |
| `CERTUS_INDEX.py` / `CERTUS_INDEX_SPLINE.py` | Détermination d'indice |
| `CERTUS_METAL_SINGLE.py` / `CERTUS_METAL_BILAYER.py` | Métaux (mono/bicouche) |
| `CERTUS_FIELD.py` | Champ électrique |

---

## 2. Architecture

```
certus/
├── physics/   25 fich.  11 224 l.  ← TMM, gradients, colorimétrie, optimiseurs
├── core/      40 fich.  20 615 l.  ← noyau métier, solveurs, config
├── domain/    12 fich.   1 006 l.  ← DDD (entities/events/services/value_objects)
├── spline/    31 fich.  31 010 l.  ← corridors, splines d'indice
├── workers/   27 fich.  11 956 l.  ← threads Qt, DTO
├── utils/     34 fich.  17 401 l.  ← helpers, export, badges
├── metal/      3 fich.   2 529 l.
└── ui/       109 fich.  60 747 l.  ← PyQt6
```

### Frontières à respecter

- **`certus.core`, `certus.physics`, `certus.domain` n'importent JAMAIS** `PyQt6`, `QWidget`, ni `certus.ui`.
- **`certus.ui` et `CERTUS_HUB.py`** ne contiennent pas d'algorithme de calcul — ils appellent les API du noyau.
- Thématisation : toujours `certus.ui.certus_ui.apply_certus_theme()` et les constantes `CertusTheme`. Jamais de hex codé en dur.

### Violations connues (à ne pas aggraver)

| Inversion | Nb | Détail |
|-----------|-----|--------|
| `utils` → `ui` | 12 | dont 3 **au niveau module** : `certus_curve_smoother.py:29-30`, `certus_export.py:13` — importer ces modules charge PyQt6 |
| `core` → `workers` | 10 | DTO de workers importés par le noyau (`certus_design_core.py`, `certus_re_solvers.py`, `certus_strat_config.py`) |
| `physics` ↔ `core` | 29/22 | cycle |

**Règle : ne jamais créer un nouvel import d'une couche basse vers une couche haute.** Si tu en as besoin, c'est que le symbole doit descendre dans `domain/` ou `core/`.

### Packages implicites

Seul `certus/domain/` a des `__init__.py`. Les 7 autres sous-packages fonctionnent en PEP 420. Conséquence : `pyproject.toml` déclare `packages = ["certus"]` et **un `pip install` ne récupérerait aucun sous-module**. Le projet n'est utilisable qu'en mode source.

---

## 3. 🔴 Conventions physiques — À NE PAS CASSER

### Convention Macleod `n̂ = n − ik` (k ≥ 0)

C'est la convention du projet, **partout**. Avec `n̂ = n + ik`, `compute_RT_from_matrix` produit `R + T > 1` (gain non physique).

**Source unique de vérité pour l'extraction R/T** : `certus/physics/certus_opt_tmm.py::compute_RT_from_matrix` (Macleod 4e éd., éq. 2.96). Toute nouvelle variante TMM doit lui déléguer — ne réimplémente jamais la formule.

### Marqueurs `─── LOCKED ───`

Signalent du code validé par tests. Ne pas modifier sans relancer les tests cités dans le commentaire. **Attention : un marqueur LOCKED n'est pas une preuve** — voir le bug §5.1, dont la fonction porte `LOCKED` et `Macleod convention (+1j, n-ik)` alors qu'elle est fausse.

### Chemins TMM — lequel utiliser

| Fonction | État | Usage |
|----------|------|-------|
| `compute_TMM_single_point_k0` / `_exact` | ✅ correct | multicouche |
| `compute_RT_from_matrix` | ✅ correct | extraction R/T — **à utiliser toujours** |
| `calculate_transmission_single` | ✅ correct | monocouche, **inclut la réflexion arrière** (Standard Mode) |
| `calculate_reflection_array` → `_single` | ✅ correct | ajustement d'indice — chemin de production |
| `calculate_RT_single_layer_single` | ❌ **FAUX si k>0** | ne pas utiliser — voir §5.1 |

Note : `calculate_transmission_single` inclut délibérément le terme de face arrière (`DO NOT REMOVE THE BACKSIDE TERM`). Ses résultats diffèrent donc légitimement d'un TMM nu.

---

## 4. Commandes

### Sur la machine (Windows, venv du projet)

```bat
make test           :: scripts/run_certus_tests.py
make test-changed   :: tests des fichiers modifiés
make test-failed    :: --lf
make lint           :: ruff check .
make format         :: ruff format .
```

Le venv est `.venv\Scripts\python.exe`.

### Environnement Linux reproductible (validé le 2026-08-01)

Utile pour la CI ou pour lancer les tests hors Windows. PyQt6 fonctionne en mode offscreen.

```bash
uv python install 3.14
uv venv --python 3.14 .venv-linux
uv pip install "numpy>=2.4" scipy pandas numba matplotlib openpyxl \
               pydantic XlsxWriter joblib PyQt6 pyqtgraph \
               pytest pytest-cov pytest-benchmark hypothesis

# libs système requises par PyQt6 (sans root : dpkg-deb -x dans un préfixe local)
#   libegl1 libgl1 libglvnd0 libglx0 libgles2 libopengl0 libxkbcommon0
#   libdbus-1-3 libfontconfig1 libfreetype6 libxcb-cursor0 libxcb-* libx11-xcb1

export QT_QPA_PLATFORM=offscreen
export LD_LIBRARY_PATH=<prefixe>/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
python -m pytest tests/ -q --no-cov
```

Versions confirmées fonctionnelles : Python 3.14.5 · numpy 2.4.6 · scipy 1.18.0 · pandas 3.0.5 · **numba 0.66.0** (njit OK) · **PyQt6 6.11.0 / Qt 6.11.0** · pyqtgraph 0.14.0.

---

## 5. 🔴 Problèmes ouverts — lire avant de travailler

Audit complet : **`AUDIT_CERTUS_2026-08-01.md`**.

### 5.1 Bug de signe TMM monocouche — ✅ CORRIGÉ le 2026-08-02

**Corrigé** (`certus_tmm_single_layer.py:41`, `phi_i = -k * n_film_imag * thickness_nm`).
Écart ramené de **46 points à 4,4e-16** contre l'oracle, sur 21 cas dont métaux et k élevés.

⚠️ **Une affirmation de cette section était fausse** et a fait perdre du temps : elle
annonçait que `tests/core/test_certus_physics_tmm.py:56` (`assert cos2_i < 0.0`)
« rejetterait le correctif » et devait être corrigée en même temps. **C'est faux.** Cette
assertion ne bloque que si l'on corrige la *fonction* ; le correctif recommandé ici porte
sur l'*appelant* et laisse `compute_complex_phase_components` intacte. Les 3 tests passent
sans modification. Ne touche pas à cette assertion.

Le diagnostic d'origine, conservé pour mémoire :

Vérifié à l'exécution (`φr=2.1, φi=1.2`) : renvoie `1.562975 − 0.762046j`, alors que `sin(2.1 − 1.2j) = 1.562975 + 0.762046j`.

Deux appelants, deux conventions :

- `certus_tmm_oblique.py:160` et `:550` passent `phi.imag` (**signé**) → se compense, **correct**
- `certus_tmm_single_layer.py:41` passe `k·k_film·d` (**positif**) → **faux dès k > 0**

Erreur mesurée sur `calculate_RT_single_layer_single` : +1,0 pt (k=0,05), **+39,2 pts** (k=3,0, saturé à R=1 par le clamp), +7,9 pts (métal). Exact à k=0.

**Correctif** (validé numériquement) — `certus_tmm_single_layer.py:41` :

```python
phi_i = -k * n_film_imag * thickness_nm   # au lieu de +k * ...
```

**À corriger en même temps**, sinon le correctif est rejeté par les tests :
`tests/core/test_certus_physics_tmm.py:56` → `assert cos2_i < 0.0` verrouille le mauvais signe (la convention correcte donne `+sin(π/2)·sinh(1) = +1,175`, donc positif).

Portée : la fonction n'est **pas** dans le chemin de production, mais elle est exportée dans `certus/physics/certus_tmm_core.py:__all__` et dans `_certus_physics_impl.py`, et benchmarkée avec k=0,018 dans `tests/performance/test_kernel_benchmarks.py:82`.

### 5.2 Dette de lint masquée

```
ruff check .  (config projet)          →     62 erreurs
ruff check .  (mêmes règles, sans ignore) → 12 157 erreurs
```

`pyproject.toml` contient un `extend-ignore` de **73 règles**. Les plus dangereuses masquées :

- **F822 (202)** — `__all__` référençant des noms inexistants, concentrés sur 4 fichiers UI (`certus_ui_widgets_factory.py` 71, `certus_base_app.py` 60, `certus_ui_utils.py` 54, `certus_ui.py` 17). Tout `import *` sur ces modules lève `AttributeError`.
- **F821 (67)** — dont 3 réels dans `certus/physics/gradient_analytic.py` (`Target`, `Callable`, `cost_numba_fast`, probablement perdus lors de l'extraction depuis `certus_opt_gradients.py`).
- **F401 (5 473)** · **F403/F405 (80 / 3 161)** imports étoile.

**Règle : `extend-ignore` ne doit jamais grandir.** Ajouter une règle transforme une dette visible en dette invisible.

### 5.3 Tests absents de la CI

226 fichiers de tests, 2 240 tests — la CI en exécute **3 fichiers** (`release-windows.yml:93`). `lint.yml` n'exécute aucun test.

### 5.4 État git — mis à jour le 2026-08-02

- Branche de travail `refactor-corridors-mixins`, **137 commits d'avance sur `main`** (dernier commit `main` : 2026-04-27). La CI ne surveille que `main` → aucun de ces commits n'a été validé.
- ✅ **desktop.ini : réglé.** Il n'y en avait pas 69 mais **270 dans `.git/`** (252 dans les répertoires d'objets, 5 refs, 2 refs de worktrees), tous des fichiers d'icône Google Drive byte-identiques. `git log --all` ne renvoyait pas « parfois vide » : il était **totalement mort** (`fatal: bad object refs/desktop.ini`, 0 commit). Il rend maintenant 141 commits et `git fsck` est propre.
  ⚠️ `git update-ref -d` **ne peut pas** supprimer ces refs (`cannot lock ref: reference broken`) — il faut supprimer les fichiers.
- ⚠️ `.env` toujours committé (`35348c0`) et poussé sur le dépôt **public** `nikonvr/CERTUS`. Clé à révoquer. **`.gitignore` ne suffit pas** : le fichier est *suivi*, donc `.gitignore` n'a aucun effet sur lui. Il faudra `git rm --cached .env` **en plus** de la réécriture d'historique.
- 🔴 **Hook `post-commit` d'auto-push.** `.git/hooks/post-commit` pousse chaque commit vers le dépôt **public**, en arrière-plan. `git commit --no-verify` **ne le neutralise pas** (`--no-verify` ne saute que `pre-commit` et `commit-msg`). **Vérifié ACTIF le 2026-08-05** : `.git/hooks/post-commit` existe et est exécutable. Vérifie son état avant tout commit que tu ne veux pas publier — cette ligne a déjà affirmé le contraire, ne lui fais pas confiance sans un `ls .git/hooks/post-commit*`.
- Un commit orphelin `01047a1b` (2 juillet) a un arbre manquant : injoignable depuis toute ref, sans effet, mais il fait **échouer `git gc`** (`fatal: bad tree object`).
- Worktrees : `audit-complet-suite-certus` (Antigravity) est un **ancêtre strict** de la branche de travail, 0 commit propre. Un worktree `0807` est `prunable`.

### 5.5 🔴 Le venv charge un AUTRE snapshot

`.venv/Lib/site-packages/__editable__.certus_optical_suite-26.5.0.pth` résolvait `certus`
vers **`CERTUS/0807/`** — un dépôt git distinct figé au 13 juillet. Tout `python -c "import
certus..."` chargeait donc du code vieux de trois semaines ; un correctif appliqué ici
restait invisible. **Le `.pth` a été supprimé le 2026-08-02.**

Sous pytest le problème ne se voyait pas (`tests/conftest.py` insère la racine). Pour
vérifier ce qui est réellement importé :

```bash
python -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

---

## 6. Conventions de travail

Politique **zéro régression** :

1. **Changements conservateurs** — modifie uniquement les lignes nécessaires. Pas de réécriture de blocs « pour la propreté » sans demande explicite.
2. **Une chose à la fois** — un fichier ou une fonction par tâche.
3. **Pas de nouvelle dépendance** externe sans validation.
4. **Types** — annote les nouvelles fonctions (arguments et retour).
5. **Tests** — toute modification de logique impose de lancer `pytest` avant de rendre.
6. **Format** — `ruff` ; ne change pas arbitrairement les guillemets ou l'indentation.

### Pièges spécifiques

- ✅ **Racine nettoyée le 2026-08-02** : 103 → 15 fichiers. Les 58 rapports `.md` de sessions (`MARATHON_*`, `SESSION*`, `OPTION_*`…) et les 42 scripts jetables ont été supprimés — ils étaient des journaux contradictoires, pas de la documentation. Récupérables via `git log`. Ne recrée pas de rapport de session à la racine.
- Il reste 3 fichiers `certus_*.py` à la racine (`certus_curve_smoother`, `certus_spectral_preproc`, `certus_substrate_index`) : ce sont des **façades légitimes** de ré-export, pas des doublons. Des tests font `import certus_spectral_preproc`. Ne les supprime pas.
- `CERTUS_METAL_SINGLE.py` (2 721 l.) et `CERTUS_METAL_BILAYER.py` (2 850 l.) sont restés à la racine alors que `certus/metal/` existe : migration à moitié faite.
- 🔴 **`reports/` contient les RÉSULTATS SCIENTIFIQUES de l'utilisateur** — 87 classeurs Excel + 87 rapports HTML de déterminations d'indice (`Report_INDEX_..._RMSE_0.00411.xlsx`). C'est gitignoré, donc git ne protestera pas si tu l'effaces, et c'est **irrécupérable**. Ne le supprime jamais dans un « nettoyage ».
- Le `.coverage` date du 13 juillet et pointe vers `CERTUS\0807\` — ne pas s'y fier (voir §5.5).

---

## 6bis. 📋 Les documents vivants

Tout le reste — journaux de session, audits datés, plans supersédés — est **supprimé dès
qu'il cesse d'aider à décider** : des documents qui se contredisent coûtent plus qu'ils
n'apportent. `git log` les retrouve si nécessaire.

| Document | Portée |
|---|---|
| [`AGENTS.md`](AGENTS.md) | **Le cadre de travail.** Vérification d'environnement, interdits, pièges, boucle. |
| [`docs/PLAN_STRAT.md`](docs/PLAN_STRAT.md) | **STRAT — le travail à venir.** Point de référence mesuré, décisions bloquantes, six actions ordonnées, règles gravées. Tout ce qui est fait en est retiré. |
| [`docs/PROPOSITIONS_CLAUDE.md`](docs/PROPOSITIONS_CLAUDE.md) | **Fidélité physique.** Spécifications mesurées de la machine, quatre écarts au réel, verdict chiffré sur chacun. |
| [`docs/JOURNAL_GEMINI.md`](docs/JOURNAL_GEMINI.md) | **État vérifié et règles de tenue** du journal, avec le modèle d'entrée. |
| [`docs/REPRISE_PERF.md`](docs/REPRISE_PERF.md) | **Performance.** Référence mesurée par module et pièges de mesure. ⚠️ Ses **temps absolus** datent d'avant le déménagement hors Google Drive et la remontée de numba — les *rapports* restent utiles, les secondes non. Verdict acquis : **pas de ×2 disponible**. |
| [`docs/PLAN_AMELIORATION.md`](docs/PLAN_AMELIORATION.md) | **Projet.** Dette de lint, tests absents de la CI, six chantiers ordonnés. |

Et la doc technique destinée à la communauté : [`pages/CERTUS_STRAT.html`](pages/CERTUS_STRAT.html),
qui explique les algorithmes, les équations, et la **méthode** (§2.1quinquies).

### Banc de mesure

```bat
.venv\Scripts\python.exe scripts\bench_examples.py <module> --auto-yes [--sample]
```

Pilote les vrais exemples de `example/` sans mock. **N'utilise pas `tests/headless/`
pour mesurer** : `test_design.py` et `test_strat.py` remplacent le calcul par un mock.

---

## 7. 🟢 L'oracle TMM — sers-t'en

`tests/oracle/tmm_reference.py` est une référence TMM **indépendante**, sans aucune ligne
partagée avec `certus.physics`, écrite depuis Macleod chap. 2 en matrices 2×2 numpy
explicites. Lente et relisible face au livre, c'est volontaire.

Auto-validée sur quatre identités analytiques : Fresnel exact à 7e-18, lame demi-onde
absente, antireflet quart-onde à 1,7e-34, énergie conservée à tout k.

```python
import sys; sys.path.insert(0, "tests/oracle")
from tmm_reference import rt_stack, rt_stack_oblique, r_single_layer_front, n_hat
```

**Ce qu'elle a déjà démasqué** : deux bugs de convention de signe, à 46 et **82 points**
de réflectance, tous deux exacts à k=0 et donc invisibles aux tests existants.

**Ce qu'elle valide** (concordance mesurée, incidence normale et oblique, s et p) :

| Chemin | Écart à l'oracle |
|--------|------------------|
| `compute_TMM_generic` | 3,3e-16 |
| `calculate_RT_single_layer_single` | 4,4e-16 |
| `calculate_reflection_infinite_substrate_single` | 4,4e-16 |
| `_oblique_stack_rt_single` (5 angles × s/p × 3 k) | 7,8e-16 |

**Règle : avant de toucher au moindre calcul optique, lance `pytest tests/oracle/`** (237
tests, 2 s). Et quand tu corriges un bug, vérifie que le test que tu ajoutes **échoue**
sur le code d'avant correctif — sinon il ne prouve rien.

### Tests qui verrouillaient un défaut

Cinq assertions codifiaient un comportement faux et ont été retournées le 2026-08-02.
Méfie-toi d'un test qui semble « protéger » quelque chose d'absurde :

| Test | Ce qu'il exigeait |
|------|-------------------|
| `test_strat_refactoring_guardrails` | qu'un matériau introuvable renvoie de l'air (n=1) |
| `test_optical_value_objects:206` | que `to_complex()` produise `n + ik` |
| `test_coverage_boost_96` | préservait les variables d'env qu'il assérait absentes |
| `test_suite_ui_instantiation` | une classe `CertusHubApp` qui n'a jamais existé |
| `test_architecture_guard` | le garde-fou `nogil` visait un kernel renommé |
