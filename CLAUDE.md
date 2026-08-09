# CERTUS — document unique

**C'est le seul document du projet.** Tout est ici. Il n'y a rien d'autre à lire.

Le code calcule de la **physique réelle** servant à fabriquer de vrais filtres optiques. Une
erreur silencieuse ne plante pas : elle produit un **résultat faux qui a l'air juste**, et
quelqu'un fabrique une pièce avec.

---

## ⚡ DÉMARRAGE — fais ces 4 choses, dans cet ordre, avant tout le reste

**1. Vérifie que tu es dans le bon dossier.**

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

Le chemin affiché **doit** commencer par `C:\dev\gemini`.
Si ce n'est pas le cas → **ARRÊTE-TOI. Signale-le. Ne modifie rien.**

**2. Vérifie que committer ne publie rien.**

```bat
dir .git\hooks\post-commit*
```

Doit afficher `post-commit.DESACTIVE`.
Si c'est `post-commit` tout court → **NE COMMITTE PAS.** Il pousse vers un dépôt **public**.

**3. Vérifie que tout est vert avant de toucher à quoi que ce soit.**

```bat
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Attendu : `All checks passed!` puis `2299 passed, 5 skipped`.
Si un test est rouge **avant** que tu n'aies rien touché → **ARRÊTE-TOI et signale.**
Ce n'est pas à toi de le réparer.

**4. Lis §12 et choisis UNE action. Une seule.**

---

## ⚡ LES 7 ERREURS QUI ANNULENT TON TRAVAIL

Chacune a déjà coûté au moins une session complète sur ce projet.

| # | L'erreur | La conséquence |
|---|---|---|
| 1 | Modifier un dossier et mesurer l'autre | Aucun message d'erreur. Tous tes résultats sont faux. |
| 2 | Écrire une conclusion avant d'avoir la mesure | Détectée à la relecture, ton travail est annulé. |
| 3 | Changer deux choses à la fois | Le résultat bouge, personne ne sait laquelle en est cause. |
| 4 | Croire un chiffre de bruit qui ne varie pas avec le bruit | C'est un artefact. Divise le bruit par 100 et remesure. |
| 5 | Lancer une mesure pendant qu'autre chose tourne | Le banc rend `RESULT=None`, ce qui ressemble à un résultat. |
| 6 | Vérifier une non-régression « aux tests près » | Les tests ne prouvent pas l'identité numérique. Il faut le bit. |
| 7 | Modifier `example/example_strat/JSON-strat-example.json` | Toutes les mesures suivantes deviennent nulles. |

**Si tu ne dois retenir qu'une phrase :**

> **Soit tu colles la sortie de la commande, soit tu écris « je n'ai pas mesuré ».**
> Il n'y a pas de troisième option. Pas de « cela devrait améliorer », pas de « le taux est
> probablement de ».

---

## ⚡ CARTE DU DOCUMENT — où aller selon ce que tu fais

| Tu veux… | Va en |
|---|---|
| **Commencer une action** | **§12** — les 6 actions, avec fichier, fonction, code, commande et résultat attendu |
| Savoir ce qui est interdit | §1 — les onze interdits |
| Savoir dans quoi tu vas tomber | §2 — les sept pièges |
| Savoir comment travailler | §3 — la boucle et la règle d'or |
| Toucher à du calcul optique | §6 — conventions physiques et oracle TMM |
| Comprendre la machine de dépôt | §9 — les spécifications du physicien |
| **Savoir ce qu'on suppose de la machine** | **§9bis — le modèle FIGÉ de la chaîne de lecture. Ne pas le rouvrir.** |
| Comparer un résultat | §10 — le point de référence |
| Comprendre un mot du projet | §7 — vocabulaire |
| Vérifier le travail d'un autre agent | §20 — protocole de re-vérification |

Une seule autre page existe, destinée à la communauté :
[`pages/CERTUS_STRAT.html`](pages/CERTUS_STRAT.html) — algorithmes, équations, méthode.
Elle ne contient aucune instruction.

---

## ⚡ TU NE DÉCIDES RIEN — toutes les valeurs sont déjà fixées

**Aucun choix ne t'est demandé.** Toutes les valeurs physiques, tous les seuils, tous les
paramètres ont été arrêtés avec le physicien le 2026-08-08 et sont dans le tableau ci-dessous.

> **Si tu te trouves en train de choisir une valeur, tu t'es trompé : la valeur existe
> déjà. Relis §9bis. Si elle n'y est vraiment pas, ARRÊTE-TOI et demande.**

### Toutes les constantes, en un seul endroit

| Paramètre | Valeur | Où c'est expliqué |
|---|---|---|
| Cadence d'échantillonnage machine | **4 Hz**, un point tous les **0,125 nm** | §9bis-1 |
| Amplitude du bruit de lecture | **±0,05 point**, soit `A = 5e-4` en unités T | §9bis-2 |
| `reading_smoothing_window` (`k`) | **8** lectures (2 s) — défaut 1 = inactif | §9bis-3 |
| `tp_hysteresis_factor` | **0,354** = `1/√8` — jamais 1,66, jamais 3 | §9bis-4 |
| Retard de déclenchement | **aucun** — ne rien ajouter | §9bis-5 |
| `phase_a_level_margin_factor` | **1,66** actuel, **3,33** à évaluer | §9bis-6 |
| Quantification de l'arrêt | `U(0 ; 0,125 nm)` | §9bis-7 |
| `index_corridor` | **0,005**, unités d'indice **absolues**, demi-largeur | §12.3 |
| `affine_scale_amp` | **0,05** ⇒ `a ∈ [0,95 ; 1,05]` | §12.1 |
| `affine_offset_amp` | **0,02** ⇒ `b ∈ [−0,02 ; +0,02]` | §12.1 |
| Plafond du banc | `CERTUS_BENCH_TIMEOUT_S=5400` | §10 |
| Graine de référence | **42**, `scan_wl_step` **1.0** | §10 |

**Tout nouveau paramètre vaut sa valeur INACTIVE par défaut** (1 pour la fenêtre, 0 pour les
amplitudes et le corridor). Le chemin inactif doit rendre les mêmes bits qu'avant. Toujours.

---

## ⚡ ORDRE DE TRAVAIL — fais les tâches dans cet ordre, une par une

Ne saute pas de tâche. Ne fais pas deux tâches à la fois. Après **chaque** tâche : tests,
lint, commit, et tu écris ce que tu as mesuré.

| # | Tâche | Section | Condition d'arrêt |
|---|---|---|---|
| **T0** | **Établir le point de référence.** `set CERTUS_BENCH_TIMEOUT_S=5400` puis le run complet. Machine libre, rien d'autre. | §10 | Si `WAIT_EXIT=timeout` ou `RESULT=None` → relance avec 7200. Si `strategies` < 300 → le run n'a pas abouti, **ne lis pas le RESULT**. |
| **T1** | **Câbler la distorsion affine** dans les deux fonctions batch + tirage par run + drapeau `poem_enabled`. | §12.1 | Amplitudes à 0 → `RESULT` doit être **identique** à T0, au dernier chiffre. Sinon tu as cassé quelque chose : reviens en arrière. |
| **T2** | **Mesurer POEM sous distorsion** : 4 runs (POEM on/off × distorsion on/off). | §12.1 | Aucune. C'est une mesure, elle donne ce qu'elle donne. Écris les 4 chiffres. |
| **T3** | **Grille d'échantillonnage à 0,125 nm** avec découplage TMM/échantillonnage. | §12.4 | Fenêtre à 1 et grille fine → le taux de plantage va **monter beaucoup**. C'est **attendu**, pas un bug. Ne corrige rien, passe à T4. |
| **T4** | **Lissage `k = 8` + seuil 0,354.** | §12.2 | Le taux de plantage doit **redescendre**. S'il ne redescend pas, dis-le — **ne remonte pas le seuil pour faire passer le chiffre**. |
| **T5** | **Corridor d'indice 0,005.** | §12.3 | Corridor à 0 → `RESULT` identique à T0. Puis balayer 0 / 0,0025 / 0,005, et `a` seul / `b` seul. |
| **T6** | **`phase_a_level_margin_factor` 1,66 → 3,33.** | §12.2, dernier bloc | Aucune. Un run chacun, comparer. |
| **T7** | **Quantification de l'arrêt** `U(0 ; 0,125 nm)`. | §12.5 | Piège 1 : si doubler `Δd_sample` ne change rien, la mesure est un artefact. |

**T3 et T4 forment une paire.** Le taux de plantage n'a de sens qu'une fois les deux faites.
Ne conclus rien entre les deux.

**§12.6 (face arrière) : ne la fais pas.** Elle vaut 0,002 en absolu. Elle est documentée
pour mémoire, pas pour être exécutée.

---

---

# PARTIE I — AVANT DE TOUCHER À QUOI QUE CE SOIT

## 0. Vérifier l'environnement — une minute, non négociable

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
dir .git\hooks\post-commit*
```

- Le chemin affiché **doit** commencer par `C:\dev\gemini`. **Plusieurs copies de ce dépôt
  coexistent sur la machine.** Si le chemin pointe ailleurs, tu modifies un dossier et tu en
  mesures un autre : tout ce que tu constateras sera faux, **sans le moindre message
  d'erreur**. C'est le piège n° 1 du projet et il est invisible. **Arrête-toi.**
- Le hook doit s'afficher `post-commit.DESACTIVE`. Sous ce nom il est inerte : committer ici
  **ne publie rien**. S'il apparaît sous le nom `post-commit` tout court, **ne committe
  pas** — il pousserait vers le dépôt **public** `nikonvr/CERTUS`, et `--no-verify` ne
  l'en empêche pas. **Ne le réactive jamais.**

### Commandes de référence

Toutes depuis `C:\dev\gemini`, toujours avec `.venv\Scripts\python.exe` — jamais `python`
nu, qui prendrait l'interpréteur système sans les dépendances.

| But | Commande | Durée |
|---|---|---|
| Tests du noyau | `.venv\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov` | ~4 min |
| Suite complète | `.venv\Scripts\python.exe -m pytest tests/ -q --no-cov` | ~1 h 45 |
| Lint | `.venv\Scripts\python.exe -m ruff check .` → `All checks passed!` | ~10 s |
| Run STRAT complet | `.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42` | ~25 min |
| Idem, seuil injecté | `... probe_anchor_noise_pipeline.py full 1.0 42 0 2.1` | ~25 min |
| Sonde noyau rapide | `.venv\Scripts\python.exe scripts\probe_anchor_noise.py` | ~1 min |
| Banc sur exemples réels | `.venv\Scripts\python.exe scripts\bench_examples.py <module> --auto-yes` | variable |

⚠️ **N'utilise pas `tests/headless/` pour mesurer** : `test_design.py` et `test_strat.py`
remplacent le calcul par un mock.

## 1. Les onze interdits absolus

Aucun n'admet d'exception. Si tu crois devoir en violer un, **arrête-toi et demande.**

1. **Jamais `ruff check --fix`.** 6 750 erreurs « auto-corrigeables », dont beaucoup sont des
   **ré-exports volontaires** : un import qui a l'air inutilisé rend en réalité un symbole
   disponible ailleurs. Corrige à la main, un fichier à la fois.
2. **Jamais agrandir `extend-ignore`** dans `pyproject.toml`. La liste masque déjà 68 règles
   et ne doit que rétrécir. `tests/oracle/test_lint_debt_ratchet.py` le surveille.
3. **Jamais supprimer `reports/`.** Résultats scientifiques de l'utilisateur : 171 fichiers,
   classeurs Excel et rapports de mesures d'indice réelles. C'est gitignoré, donc git ne
   protestera pas, et c'est **irrécupérable**.
4. **Jamais modifier `example/example_strat/JSON-strat-example.json`.** Il s'est écarté des
   valeurs correctes **quatre fois**, toujours dans le sens permissif, et chaque fois cela a
   coûté une session de diagnostic. Pour essayer autre chose, utilise
   `scripts\probe_anchor_noise_pipeline.py`, qui injecte les paramètres **après coup**.
5. **Jamais « corriger » `except A, B:`.** C'est la syntaxe PEP 758, valide depuis
   Python 3.14, utilisée volontairement dans 14 modules. Ajouter des parenthèses change le
   sens du code.
6. **Jamais inverser la convention `n̂ = n − ik`** (k ≥ 0). Avec la convention inverse les
   calculs donnent `R + T > 1` : de l'énergie créée à partir de rien.
7. **Jamais réimplémenter une formule TMM.** Source unique de vérité pour extraire R et T :
   `certus/physics/certus_opt_tmm.py::compute_RT_from_matrix`. Deux bugs de signe ont déjà
   été trouvés dans des réimplémentations, valant **46 et 82 points** de réflectance.
8. **Jamais découper `certus/core/_certus_physics_impl.py`.** Le fichier le dit lui-même :
   `DO NOT SPLIT`. Les noyaux compilés dépendent de la visibilité mutuelle dans un fichier.
9. **Jamais affirmer un résultat non mesuré.** Pas « cela devrait améliorer », pas « le taux
   est probablement de ». Soit tu colles la sortie, soit tu écris « je n'ai pas mesuré ».
10. **Jamais créer de rapport de session à la racine.** 103 fichiers y avaient été accumulés
    puis supprimés : des journaux contradictoires.
11. **Jamais réintroduire de français dans `certus/`.** L'anglais est strictement
    obligatoire pour tout commentaire, docstring ou message de log **ajouté**.
    ⚠️ État réel : il reste **364 occurrences de français dans 42 fichiers**, dont 82 lignes
    dans `certus_strat_growth.py`. La règle vaut pour ce que tu ajoutes, pas pour une purge.

## 2. Les sept pièges — chacun a déjà été rencontré

### Piège 1 🟢 — La règle de méthode, payée trois fois

> **Une grandeur de bruit qui ne varie pas avec le bruit est un artefact. Sans exception.**
> Divise le bruit par 100 et remesure. Si le chiffre ne bouge pas, ce n'est pas de la
> physique.

📏 En une journée, le même taux de plantage par couche a valu 28 %, puis 1,3 %, puis 1,47 %
à σ → 0. **Deux fois sur trois ce n'était pas de la physique.** Le balayage de σ coûte
quelques secondes et l'a montré chaque fois.

**Trois corollaires, chacun payé au moins une fois :**

1. **Vérifie sur quelle SOURCE un critère se prononce.** Les défauts les plus coûteux
   étaient de cette forme : le signal *propre* au lieu du signal bruité · la grille
   d'*affichage* au lieu de la grille de balayage · une matrice de *zéros* au lieu de
   l'empilement réel.
2. **Ne confonds jamais deux causes sous une même sentinelle.** Trois modes de défaillance
   rendaient la même valeur ; le diagnostic est devenu possible en **une** mesure une fois
   séparés.
3. **Une signature qui ne varie ni avec la profondeur, ni avec l'amplitude, ni avec la
   graine désigne l'algorithme, pas le phénomène.**

### Piège 2 — `params` n'est pas toujours un dictionnaire

Sur certains chemins c'est un objet pydantic (`StratParamsDTO`).
`params.get("cle")` ✅ · `params["cle"] = v` ✅ · **`params.setdefault(...)` ❌ `AttributeError`**.
Ce bug a tué le pipeline entier en 13 secondes, résultat vide, aucune explication. Écris :

```python
if params.get("cle") is None:
    params["cle"] = valeur
```

### Piège 3 — Importer un paquet déclenche son `__init__.py`

Importer `certus_physics.quoi_que_ce_soit` exécute d'abord `certus_physics/__init__.py`,
qui importe la moitié du projet. Depuis un module de `certus/physics/`, c'est un **import
circulaire**. Vérifier les imports du module ne suffit pas : vérifie ceux de son **paquet**.
Pour une simple annotation, utilise `if TYPE_CHECKING:`.

⚠️ Corollaire pour les scripts : `from certus.physics.X import Y` échoue en circulaire ;
passe par la façade `from certus_physics import Y`.

### Piège 4 — Les tests partagent des caches de classe

`SplineBasisCache._cache` et consorts. Symptôme : ton test passe seul, un autre échoue plus
tard. Sauvegarde et restaure le cache dans une fixture `autouse`.

### Piège 5 — Un test qui échoue n'a pas forcément tort… mais parfois si

**Cinq tests** vérifiaient un comportement **faux** et ont dû être retournés : qu'un
matériau introuvable renvoie de l'air (n=1) · que `to_complex()` produise `n + ik` · un test
préservant les variables d'env qu'il assérait absentes · une classe `CertusHubApp` qui n'a
jamais existé · un garde-fou `nogil` visant un kernel renommé.

Ne « répare » pas un test en changeant le nombre attendu. Comprends d'abord. Puis dis
laquelle des deux situations tu as trouvée — code faux, ou test faux — et si c'est le test,
explique pourquoi dans son docstring. Si tu ne sais pas trancher, **arrête-toi et demande.**

### Piège 6 — La Phase A ne dit rien de ce qu'elle fait

Deux systèmes de journalisation : l'un écrit sur la console, l'autre dans une file destinée
à l'interface graphique, que personne ne vide en ligne de commande. **Un silence ne prouve
rien.** Pour savoir ce que la Phase A a fait, lis le `reports/STRAT_observability_*.json` le
plus récent.

### Piège 7 — Le premier calcul est lent, et ce n'est pas une mesure

Numba compile au premier appel : +30 s sans que rien ne soit anormal. Chauffe une fois, puis
mesure. **Et donne la machine entière au run que tu mesures** — voir Règle 5 en §12.

## 3. La boucle de travail

Pour **chaque** action, dans cet ordre, sans en sauter :

1. **Lis l'action** en §9. Si quelque chose est ambigu, **arrête-toi et demande.** Un plan
   ambigu est un défaut du plan, pas une invitation à inventer.
2. **Fais la modification la plus petite possible.** Une seule chose à la fois : si tu
   changes deux choses et que le résultat bouge, personne ne saura laquelle en est cause.
3. **Tests** : `pytest tests/oracle/ tests/unit/ -q --no-cov`. Un échec ⇒ n'avance pas.
4. **Lint** : `ruff check .` doit dire exactement `All checks passed!`
5. **Non-régression bit-à-bit** si tu as ajouté un paramètre — voir la règle d'or ci-dessous.
6. **Mesure** avec la commande exacte, machine libre.
7. **Committe**, puis colle le hash dans ta réponse.

### 🔴 La règle d'or

> **Tout nouveau paramètre doit être inactif par défaut, et le chemin inactif doit donner
> exactement le même résultat qu'avant — au dernier bit.**

Et **pas « aux tests près »** : les tests ne couvrent pas assez de combinaisons pour prouver
une identité numérique. La méthode qui fait foi : capturer une empreinte `float.hex()` du
chemin par défaut sur une large batterie de configurations **avant** la modification, la
recapturer après, exiger **zéro** différence. La correction affine de §8 a été validée ainsi
sur **75 818 configurations**.

## 4. Quand s'arrêter et demander

- une instruction est ambiguë ;
- un test échoue et tu ne sais pas si c'est le test ou le code qui a tort ;
- une mesure diffère nettement de ce qui était annoncé ;
- tu es tenté de violer un interdit ;
- tu envisages de modifier plus de trois fichiers pour une seule action ;
- **tu obtiens un résultat meilleur que prévu** — c'est très souvent le signe qu'on mesure
  la mauvaise chose.

**S'arrêter n'est jamais un échec. Inventer, si.**

---

# PARTIE II — LE PROJET

## 5. Ce qu'est CERTUS

Suite scientifique de **couches minces optiques** : détermination d'indice, design
d'empilements, stratégie de dépôt. Application **PyQt6** + noyau **NumPy/SciPy/Numba**.

- `certus-optical-suite 26.05.0` — licence propriétaire
- **Python ≥ 3.14.5 obligatoire** (PEP 758 : `except A, B:` sans parenthèses, 14 modules)
- Cible principale Windows, build gelé PyInstaller
- 183 600 lignes de source · 56 400 de tests · ~2 300 tests collectés

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

### Architecture

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

**Frontières à respecter**

- `certus.core`, `certus.physics`, `certus.domain` n'importent **jamais** PyQt6, QWidget, ni
  `certus.ui`.
- `certus.ui` et `CERTUS_HUB.py` ne contiennent **aucun algorithme de calcul**.
- Thématisation : toujours `apply_certus_theme()` et les constantes `CertusTheme`. Jamais de
  hex codé en dur.

**Violations connues — ne pas aggraver**

| Inversion | Nb | Détail |
|-----------|-----|--------|
| `utils` → `ui` | 12 | dont 3 au niveau module (`certus_curve_smoother.py:29-30`, `certus_export.py:13`) : importer ces modules charge PyQt6 |
| `core` → `workers` | 10 | DTO de workers importés par le noyau |
| `physics` ↔ `core` | 29/22 | cycle |

**Règle : ne jamais créer un nouvel import d'une couche basse vers une couche haute.** Si tu
en as besoin, c'est que le symbole doit descendre dans `domain/` ou `core/`.

**Packages implicites.** Seul `certus/domain/` a des `__init__.py` ; les 7 autres
sous-paquets fonctionnent en PEP 420. `pyproject.toml` déclare `packages = ["certus"]`, donc
un `pip install` ne récupérerait aucun sous-module : le projet n'est utilisable qu'en source.

### Pièges de fichiers

- 🔴 **`reports/` contient les résultats scientifiques de l'utilisateur** — 87 classeurs
  Excel et 87 rapports HTML de déterminations d'indice. Gitignoré, donc non protégé, et
  irrécupérable. Ne le supprime **jamais** dans un « nettoyage ».
- Les 3 fichiers `certus_*.py` restants à la racine (`certus_curve_smoother`,
  `certus_spectral_preproc`, `certus_substrate_index`) sont des **façades légitimes** de
  ré-export. Des tests font `import certus_spectral_preproc`. Ne les supprime pas.
- `CERTUS_METAL_SINGLE.py` et `CERTUS_METAL_BILAYER.py` sont restés à la racine alors que
  `certus/metal/` existe : migration à moitié faite.
- Le `.coverage` date du 13 juillet et pointe vers un autre snapshot — ne pas s'y fier.

## 6. 🔴 Conventions physiques — à ne pas casser

### Convention Macleod `n̂ = n − ik` (k ≥ 0)

Partout. Avec `n̂ = n + ik`, `compute_RT_from_matrix` produit `R + T > 1`.

### Chemins TMM — lequel utiliser

| Fonction | État | Usage |
|----------|------|-------|
| `compute_TMM_single_point_k0` / `_exact` | ✅ | multicouche |
| `compute_RT_from_matrix` | ✅ | extraction R/T — **toujours celle-ci** |
| `calculate_transmission_single` | ✅ | monocouche, **inclut la face arrière** (Standard Mode) |
| `calculate_reflection_array` → `_single` | ✅ | ajustement d'indice, chemin de production |
| `calculate_RT_single_layer_single` | ✅ | corrigé le 2026-08-02 (`phi_i = -k·n_film_imag·d`), écart ramené de 46 points à 4,4e-16 |

`calculate_transmission_single` inclut délibérément le terme de face arrière
(`DO NOT REMOVE THE BACKSIDE TERM`) : ses résultats diffèrent légitimement d'un TMM nu.

### Marqueurs `─── LOCKED ───`

Signalent du code validé par tests. Ne pas modifier sans relancer les tests cités.
⚠️ **Un marqueur LOCKED n'est pas une preuve** : le bug de signe monocouche portait
`LOCKED` **et** `Macleod convention (+1j, n-ik)` alors que la fonction était fausse.

### 🟢 L'oracle TMM — sers-t'en

`tests/oracle/tmm_reference.py` est une référence TMM **indépendante**, sans une ligne
partagée avec `certus.physics`, écrite depuis Macleod chap. 2 en matrices 2×2 explicites.
Lente et relisible face au livre — c'est volontaire.

```python
import sys; sys.path.insert(0, "tests/oracle")
from tmm_reference import rt_stack, rt_stack_oblique, r_single_layer_front, n_hat
```

**Ce qu'elle a démasqué** : deux bugs de convention de signe, à 46 et **82 points** de
réflectance, tous deux exacts à k=0 donc invisibles aux tests existants.

| Chemin validé | Écart à l'oracle |
|--------|------------------|
| `compute_TMM_generic` | 3,3e-16 |
| `calculate_RT_single_layer_single` | 4,4e-16 |
| `calculate_reflection_infinite_substrate_single` | 4,4e-16 |
| `_oblique_stack_rt_single` (5 angles × s/p × 3 k) | 7,8e-16 |

**Règle : avant de toucher au moindre calcul optique, lance `pytest tests/oracle/`** (237
tests, 2 s). Et quand tu corriges un bug, **vérifie que le test que tu ajoutes échoue sur le
code d'avant correctif** — sinon il ne prouve rien.

## 7. Vocabulaire

| Terme | Sens |
|---|---|
| **le juge de paix** | Le dichroïque 48 couches, `example/example_strat/JSON-strat-example.json`, passe-court, front à ~545 nm. **Le seul exemple valable.** |
| **λ de contrôle** | Longueur d'onde à laquelle la machine surveille le dépôt d'une couche. |
| **bloc** | Groupe de couches consécutives surveillées à la **même** λ. |
| **point tournant** | Maximum ou minimum du signal de transmission pendant la croissance. |
| **POEM** | Méthode d'arrêt visant un pourcentage de l'amplitude entre les deux derniers points tournants, au lieu d'un niveau absolu. |
| **plantage** | Le dépôt **ne se termine pas** : la machine attend un niveau qui ne vient jamais, ou compte le mauvais nombre de points tournants. Pas une perte de précision — un run perdu. |
| **rendement** | Pourcentage de dépôts qui se terminent. Objectif du physicien : **95 %**. |
| **Phase A** | Choix de la meilleure λ pour chaque couche, une couche à la fois. |
| **Phase B** | Regroupement en blocs et test statistique Monte-Carlo des stratégies. |

---

# PARTIE III — STRAT : LA PHYSIQUE ET LE TRAVAIL À VENIR

## 8. Le cadre — trois phrases du physicien qui gouvernent tout

> 👤 **La chaîne canonique.** *« 1. On simule un dépôt et la mesure de transmission bruitée.
> 2. On utilise le POEM comme méthode d'arrêt. 3. On teste statistiquement tout un ensemble
> de stratégies prometteuses. 4. On en déduit la meilleure stratégie. »*

> 👤 **Le juge.** *« Le juge de paix c'est toujours l'étude stochastique et statistique. Si
> 95 % des dépôts fonctionnent, c'est gagné. »*

> 👤 **L'objectif.** *« Le plus important est la cible spectrale respectée. »*

Cela définit **une grandeur unique** : la meilleure stratégie maximise `P(le filtre sorti
est conforme)`. Un dépôt qui plante et un filtre hors spec sont **le même échec**.
Conséquence : **la DP n'a plus à bien classer, elle doit bien couvrir** — le tri est fait
par la statistique.

## 9. 👤 La machine réelle — spécifications obtenues le 2026-08-08

Ces nombres gouvernent le modèle de monitoring.

| Grandeur | Valeur | Conséquence |
|---|---|---|
| Rotation du plateau | **240 tr/min** | période 250 ms |
| Plateau ~1 m, témoin 20 mm au bord | | vitesse tangentielle **12,6 m/s**, **transit 1,6 ms** |
| Positions par tour | **3** : témoin, noir, vide | `T = (S − D)/(V − D)`, auto-référencé à 4 Hz |
| Vitesse de dépôt | ~0,5 nm/s | |
| **Cadence** | **4 Hz**, une lecture témoin par tour | **un échantillon tous les 0,125 nm** |
| Bruit de lecture | ±0,05 point, largeur totale **0,10** | 👤 le tirage du modèle est **correct** |
| Le « 5 σ » du seuil | 👤 *« bien au-dessus du bruit »* | **pas une exigence physique** |

**La rotation moyenne le dépôt** — c'est sa raison d'être — **mais elle échantillonne la
mesure** : chaque point rapporté est un passage, rien ne se moyenne.

**Écart au modèle, mesuré :**

| | Machine | Modèle actuel | Facteur |
|---|---|---|---|
| Pas spatial | 0,125 nm | 4,76 nm (`NPTS=64` sur `3×d_nom`) | **38× trop grossier** |
| Points par couche de 100 nm | 800 | 21 | |
| Historique, par couche relue | 800 | 16 (`NPTS_PREV`) | **50× trop grossier** |

🔴 **Ne pas modéliser σ(T), la grenaille, ni le bruit multiplicatif.** Le modèle actuel — un
tirage borné à ±0,05 point, un seul nombre mesuré, aucun paramètre libre — est défendable. Y
ajouter une structure non mesurée remplacerait une constante mesurée par des paramètres
inventés. 👤 Tranché le 2026-08-08.

---

## 9bis. 🔒 LE MODÈLE DE LA CHAÎNE DE LECTURE — FIGÉ, NE PAS ROUVRIR

**L'OMS 5100 est breveté et son fonctionnement interne est opaque.** On ne saura pas
comment il filtre, ni comment il déclenche. Continuer à poser des questions sur ses entrailles
ne produirait que des paramètres libres, et un modèle à paramètres libres ne prouve rien.

👤 **Décision du 2026-08-08 : on pose une hypothèse raisonnable, on l'écrit, et on s'y
tient.** Ce qui suit est un **postulat de modélisation**, pas une spécification constructeur.
Il est **figé**. On ne le rouvre que si une mesure le contredit — pas parce qu'une autre
hypothèse semblerait plus élégante.

| # | Postulat | Statut |
|---|---|---|
| 1 | Une lecture témoin par tour, **4 Hz** ⇒ un échantillon tous les **0,125 nm** à 0,5 nm/s | 👤 déduit de specs données |
| 2 | Bruit **additif**, borné à **±0,05 point** (A = 5e-4 en unités T), σ = A/3, tirages indépendants entre lectures | 👤 confirmé |
| 3 | La chaîne de détection **moyenne sur 2 s**, soit une **moyenne glissante de `k = 8` lectures** | 🔒 hypothèse figée |
| 4 | Le seuil de détection d'un point tournant vaut **3 σ du signal lissé**, soit `A/√k` = **0,354 A** pour k = 8 | 🔒 hypothèse figée |
| 5 | **Aucun retard** : le logiciel anticipe la valeur de trigger, et l'extremum enregistré est l'extremum lui-même | 🔒 hypothèse figée |
| 6 | Marge de sélection des λ : **5 σ du bruit brut** (1,66 A) aujourd'hui, **10 σ** (3,33 A) à évaluer | 👤 fourchette donnée |
| 7 | Quantification de l'arrêt : `U(0 ; 0,125 nm)`, strictement positive | 🔒 découle de 1 |

**Ce qui est explicitement HORS du modèle**, et le reste :

- σ dépendant de T ou de λ, grenaille, bruit multiplicatif ;
- bruit corrélé d'un tour à l'autre (voilage, faux-rond, gigue de déclenchement) — le modèle
  suppose des tirages **indépendants** ;
- toute forme de filtre autre que la moyenne glissante : exponentiel, médian, confirmation
  sur N lectures.

**Ce qui rouvrirait légitimement le postulat** : un run réel du dichroïque dont le taux de
plantage mesuré s'écarterait nettement du taux prédit. Rien d'autre. En particulier, pas un
raisonnement — ce projet a déjà payé trois fois pour avoir cru un raisonnement sur le bruit.

⚠️ **`k` reste un paramètre du code**, avec 8 pour valeur retenue. Le figer dans la
documentation n'interdit pas de le **balayer pour vérifier** que les résultats en dépendent
(Piège 1) : un taux de plantage insensible à `k` signalerait que le lissage n'atteint pas le
calcul. Figé veut dire « on ne re-discute pas la valeur retenue », pas « on ne la teste pas ».

## 10. Point de référence — tout se compare à lui

Obtenu par `scripts\probe_anchor_noise_pipeline.py full 1.0 42`.

```
Configuration : poem_anchor_noise = 1, tp_hysteresis_factor = 1.66,
                phase_a_level_margin_factor = 1.66, dp_yield_weight = 0,
                scan_wl_step = 1.0

  RESULT                      0,002898
  RMSE global   med / p95     0,215 / 0,465   points de transmission
  bande passante p95          0,418
  front p95                   1,498
  plantage                    0,000     345 strategies rendues
  RUN_S                       ~1322 s
  gagnante                    2 blocs (544 et 531 nm)
```

⚠️ **`RESULT` est le PIRE des trois niveaux de bruit** (0,5× / 1× / 2×) ; les lignes en
dessous sont au niveau **nominal**. Ne jamais comparer l'un à l'autre.

⚠️ **Repère du pas de 1 nm.** Une version antérieure citait `RESULT = 0,005283` / 305
stratégies : c'était le run à **2 nm**, périmé (voir §13).

### 🔴 Ce repère n'a PAS été reproduit le 2026-08-08 — lis ceci avant de mesurer

Deux tentatives, **deux `RESULT=None`** :

```
WAIT_EXIT=timeout
WAIT_TIMEOUT=1800 s — aucune emission recue
MODE=full_step1_seed42  SETUP_S=1.243  RUN_S=1800.051  RESULT=None
PROBE_WRITTEN=...  strategies=12          <- au lieu de 345
```

La première fois, d'autres travaux tournaient en parallèle : mesure nulle, ma faute. **La
seconde fois la machine était libre, et le plafond a quand même été atteint.**

**Ce que cela veut dire, et ce que cela ne veut pas dire.** Cela ne dit pas que le code est
cassé : le run progressait normalement, il n'a simplement pas fini. Cela dit que **le chiffre
0,002898 n'est pas vérifié sur cette machine dans son état actuel**, et qu'aucune conclusion
comparative ne peut être tirée tant qu'un run n'a pas abouti.

**Ce qu'il faut faire avant toute mesure au banc :**

```bat
set CERTUS_BENCH_TIMEOUT_S=5400
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

Le plafond était en dur ; il est désormais surchargeable par cette variable d'environnement,
défaut inchangé à 1800 s. **Mets 5400 et laisse finir.**

⚠️ **Le piège, et il a fonctionné deux fois** : au-delà du plafond le banc ne signale pas
d'erreur bruyamment. Il émet `RESULT=None` et un tableau de 12 stratégies au lieu de 345 —
**cela ressemble à un résultat**. Vérifie toujours `WAIT_EXIT` et le nombre de stratégies
avant de lire un `RESULT`.

⚠️ **Une mesure, une machine.** Ne lance rien d'autre pendant un run : ni tests, ni lint, ni
recherche récursive. Le pipeline sature tous les cœurs en `prange`.

**Suite de tests, mesurée sur cette copie le 2026-08-08** :

```
pytest tests/oracle/ tests/unit/ -q --no-cov  ->  2299 passed, 5 skipped in 228.49s
ruff check .                                  ->  All checks passed!
```

⚠️ Des documents supprimés annonçaient 2300 et 2301, avec la **même durée au centième**
(`87.60s`) dans cinq entrées différentes. Ces lignes n'avaient pas été mesurées.
**La référence est 2299.**

## 11. Les quatre paramètres du modèle, et où les poser

Dans le JSON de configuration, à la racine. Lus par `collect_params`
(`certus/ui/certus_strat_ui_state.py`). **Tous valent 0 / faux par défaut**, et à 0 le
chemin de calcul est celui d'avant, au bit près.

| Clé JSON | Effet |
|---|---|
| `poem_anchor_noise` | Bruite le signal de monitoring **avant** détection des points tournants, lecture des ancres POEM et test d'atteignabilité. Phase A **et** B. |
| `tp_hysteresis_factor` | Seuil de détection d'un point tournant, en multiples de `A = trigger_tolerance/100`. Vaut **1,66** aujourd'hui. 🔒 **Valeur cible du modèle figé : 0,354** = `1/√k` avec `k = 8`, parce qu'elle s'applique au signal **lissé** — voir §9bis et §12.2. Injectable en 5ᵉ argument du script de sonde. |
| `reading_smoothing_window` | 🔒 **À créer** (§12.2). Fenêtre de moyenne glissante appliquée au signal de monitoring avant détection, **en lectures machine**. Défaut **1** = aucun lissage = chemin actuel. Valeur du modèle figé : **8** (2 s à 4 Hz). N'a de sens qu'avec la grille de §12.4. |
| `index_corridor` | 🔒 **À créer** (§12.3). Demi-largeur du corridor d'incertitude d'indice, en **unités d'indice absolues**. Défaut **0,0**. Valeur du modèle : **0,005**. |
| `phase_a_level_margin_factor` | Marge exigée **en transmission** entre le niveau d'arrêt et les points tournants voisins. Active aussi la vraie matrice cumulée en Phase A. |
| `dp_yield_weight` | Poids du rendement dans l'objectif DP : `coût = coût_nm + w·(−log(1−p))`. |

## 12. Le travail à venir, dans l'ordre

> **Chaque action donne : le fichier et la fonction exacts, ce qu'il faut écrire, la commande
> de vérification avec son résultat attendu, et les pièges connus.** Si une instruction te
> paraît ambiguë, c'est un défaut de ce document — ne comble pas par une hypothèse,
> arrête-toi et demande.

### Les trois contraintes qui s'appliquent à TOUTES les actions

**C1 — Inactif par défaut, bit-identique.** Tout nouveau paramètre vaut sa valeur neutre par
défaut, et le chemin neutre doit rendre **exactement** les mêmes bits qu'avant. Vérifié par
empreinte `float.hex()` sur une large batterie de configurations, avant/après — pas « aux
tests près ». Voir §3.

**C2 — Nombres aléatoires communs.** Tout tirage aléatoire est une **fonction pure de
(graine, tirage, et un index physique)**. Jamais de la stratégie : ni la longueur d'onde, ni
le découpage en blocs, ni `block_start_layer`, ni une épaisseur *obtenue*. Deux stratégies
comparées sur le même (graine, tirage) doivent voir **exactement le même aléa**, sinon leur
écart de score n'est plus imputable à la stratégie. Le générateur à utiliser est
`_seeded_noise_sample(seed_base, group_idx, run_idx, elem_idx, gaussian)`
(`certus/physics/certus_strat_math.py:384`) — loi tronquée sur [−1, 1], σ = 1/3.

**C3 — Une seule chose à la fois.** Si deux choses changent et que le résultat bouge,
l'attribution est perdue — pour toi et pour tous ceux qui suivront.

---

### 12.1 🔴 Rendre la distorsion affine atteignable, puis éprouver POEM

**Pourquoi en premier** : seule action pouvant **invalider POEM**, le mécanisme central de
STRAT. Tout le reste le suppose valide.

**Où on en est.** Le noyau est corrigé (`76f7a8f`) : il annulait son propre effet en trois
endroits, ce qui aurait fait conclure l'inverse de la vérité.

| Site | Défaut corrigé |
|---|---|
| Inversion parabolique | modèle **non distordu** résolu contre une cible **distordue** — unités mélangées |
| Repli absolu | `a·target_nominal + b` rendait au contrôleur l'étalonnage qu'il est censé avoir perdu |
| Test SWING | seuil mis à l'échelle par `a`, annulant le gain exactement |

📏 Avant : `a = 0,9574` déplaçait l'arrêt de **−6,60 nm** là où la théorie exige zéro.
📏 Après : invariance POEM à **2,19e-10 nm**, et le repli absolu devient sensible — il rend
`CRASH_LEVEL_UNREACHABLE` sous une chute de gain de 4,3 % sur une couche à faible contraste.

**Ce qui manque** : `affine_scale` et `affine_offset` ne sont dans la signature d'**aucun**
appelant. Le tirage n'existe pas.

#### Où, exactement

| Fichier | Fonction | Ce qu'il faut écrire |
|---|---|---|
| `certus/physics/certus_strat_batch.py` | `simulate_stack_robustness_batch` | Ajouter `affine_scale: float = 1.0, affine_offset: float = 0.0` en fin de signature, les passer au noyau. |
| idem | `validate_wavelengths_batch` | Idem. Phase A doit voir la même distorsion que Phase B, sinon les deux étages ne modélisent pas la même machine. |
| `certus/core/certus_strat_robustness.py` | `_execute_robustness_tasks` (~ligne 814-857, à côté du calcul de `tp_hysteresis`) | Tirer `(a, b)` **une fois par tirage** et les passer au batch. |

#### Le tirage

```python
# UNE FOIS PAR RUN, jamais par couche. Contrainte C2 : aucune entree de strategie.
z_a = _seeded_noise_sample(affine_stream_seed, 0, run_idx, 0, True)   # in [-1, 1]
z_b = _seeded_noise_sample(affine_stream_seed, 1, run_idx, 0, True)
affine_scale  = 1.0 + affine_scale_amp  * z_a     # amp par defaut 0.0 -> a = 1.0
affine_offset =       affine_offset_amp * z_b     # amp par defaut 0.0 -> b = 0.0
```

Deux nouvelles clés JSON, **0,0 par défaut** : `affine_scale_amp`, `affine_offset_amp`.

🔒 **Valeurs à utiliser pour la mesure T2, ne pas en choisir d'autres** :
`affine_scale_amp = 0.05` (donc `a ∈ [0,95 ; 1,05]`) et `affine_offset_amp = 0.02` (donc
`b ∈ [−0,02 ; +0,02]`). Ce sont les plages arrêtées de longue date pour cette action.

`affine_stream_seed` se dérive de la graine de tirage comme `_signal_noise_stream_seed`
(`certus_strat_robustness.py:840`) — **groupes distincts** (`0` et `1`) pour que gain et
offset soient indépendants, et un `seed_base` distinct de celui du bruit de lecture pour ne
pas corréler les deux phénomènes.

#### Vérification

```bat
:: 1. non-regression : amplitudes a 0, le RESULT doit etre IDENTIQUE au repere §10
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
::    attendu : RESULT = 0,002898  (au dernier chiffre)

:: 2. le critere de reussite : avec et sans POEM, sous distorsion
::    (necessite d'exposer un drapeau de desactivation de POEM, cf. piege ci-dessous)
```

**Critère de réussite** : mesurer **plantage** et **erreur spectrale** dans les quatre cas
— POEM actif / inactif × distorsion active / inactive. Si POEM tient sa promesse, l'écart
doit être **spectaculaire**. Sinon, l'argument central du mécanisme tombe et **il faut le
dire**.

#### Pièges connus

- 🔴 **Il n'existe pas aujourd'hui de drapeau « désactiver POEM ».** `poem_ok` est décidé
  dans le noyau par `SWING_MIN` et le comptage d'ancres. Le critère de réussite exige de
  pouvoir forcer le repli absolu. Ajouter un paramètre `poem_enabled: bool = True` au noyau
  — inactif par défaut au sens de C1, puisque `True` est le comportement actuel.
- ⚠️ `tp_hysteresis` reste **asymétrique** sous distorsion : `Ts_r` est mis à l'échelle,
  `Ts_n` ne l'est pas, et les deux reçoivent le même seuil **absolu**. Une chute de gain
  rétrécit donc les ondulations réelles face à un seuil fixe et peut fabriquer des
  `CRASH_TP_MISCOUNT`. **Séparer les deux sentinelles dans le rapport** (`int(val // 1e6)`
  donne la cause) pour ne pas confondre cet effet avec le vrai.
- ⚠️ Le bruit `noise_val_precalc` est ajouté à `target_level`, qui est en unités mesurées
  dans la branche POEM et en unités vraies dans le repli. Effet du second ordre, non mesuré.

---

### 12.2 🔴 Modéliser le LISSAGE de lecture — et surtout pas remonter le seuil

> **Cette action applique le modèle figé du §9bis.** Ne le rediscute pas : l'OMS est breveté,
> son fonctionnement interne restera opaque, et le postulat a été arrêté le 2026-08-08 pour
> clore la question. Les valeurs à utiliser sont `k = 8` et seuil `0,354 A`.

**2 s à 4 lectures/s ⇒ fenêtre de `k = 8` lectures**, soit 1 nm de dépôt à 0,5 nm/s.

#### Le constat qui a mené à ces réponses

Le modèle compare aujourd'hui des lectures **brutes**. Le docstring de
`detect_turning_points` énonce alors sa condition de suffisance : le tirage étant borné à
±A, l'écart maximal du bruit seul vaut 2A, donc `hysteresis ≥ 2·trigger_tolerance/100`
= 1,0e-3. Or `certus_strat_robustness.py:854` calcule `1,66 × 5e-4` = 8,3e-4.

📏 Mesuré — signal propre **plat**, bruit réel, 20 000 tirages, aucun TMM. Fraction des
couches où le bruit **fabrique** un point tournant :

```
hysteresis                      N=80 (modele actuel)      N=320      N=800 (cadence machine)
1.66 A  (configure = 5 sigma)                32.945%    92.995%                      99.935%
2.00 A  (borne, 6 sigma)                      0.480%     7.660%                      30.525%
2.40 A  (7.2 sigma)                           0.000%     0.000%                       0.000%

Controle Piege 1 : bruit x0.50 a N=800, seuil 1.66 A  ->  0.000%
```

Le résidu à 2,00 A n'est pas physique : c'est l'atome de probabilité à l'écrêtage ±1 du
tirage, où `maxv − v` vaut 2A à l'arrondi près et le `>` strict devient un pile ou face en
flottant. Prédiction du mécanisme à N=80 : 0,5 %. Mesuré : 0,48 %.

**Sur des lectures brutes, un seuil à 3 σ est intenable** : le tremblement fait 6 σ de large,
donc une lecture haute suivie d'une lecture basse le franchit à elle seule. **Mais la machine
ne lit pas brut.** C'est le modèle qui est infidèle, pas le seuil.

#### Le modèle correct, et le chiffre qu'il donne

Lisser le signal **avant** la détection, et garder 3 σ **du signal lissé**.

Le lissage agit sur deux fronts, et le second domine :

1. **Amplitude** — moyenner `k` lectures divise l'écart-type par `√k`. À `k = 8`, le
   tremblement passe de 0,10 à 0,035 point.
2. **Corrélation** — deux moyennes glissantes voisines partagent 7 lectures sur 8 et ne
   peuvent donc pas s'écarter brutalement. Fabriquer une fausse inversion exigerait un
   basculement **cohérent** du bruit sur toute la fenêtre, bien plus rare qu'une lecture
   haute suivie d'une lecture basse.

**Le seuil DESCEND, il ne monte pas.** En gardant `tp_hysteresis_factor` exprimé en multiples
de l'amplitude brute A, le critère « 3 σ du signal lissé » s'écrit :

$$\text{tp\_hysteresis\_factor} \;=\; \frac{3\,\sigma_{\text{lissé}}}{A} \;=\; \frac{3}{3\sqrt{k}} \;=\; \frac{1}{\sqrt{k}}
\qquad \Rightarrow \qquad k = 8 \;\Rightarrow\; \mathbf{0{,}354}$$

Contre 1,66 aujourd'hui : **4,7× plus bas**, sur un signal 2,8× plus calme. C'est meilleur
sur les deux tableaux — moins de faux points tournants **et** meilleure détection des vrais
extrema peu marqués, qui est la face du problème jamais mesurée.

⚠️ **Ce 0,354 est une dérivation, pas une mesure.** La borne anti-fabrication d'un signal
lissé n'est pas calculable simplement : les échantillons voisins sont corrélés. **Il faut la
mesurer** — voir la vérification 2.

#### Le retard : rien à ajouter, le noyau fait déjà bien

👤 Le logiciel anticipe la valeur de trigger, donc le lissage n'introduit pas de retard sur
l'arrêt. **Le noyau est déjà conforme, à deux endroits, et il ne faut pas le « corriger » :**

- l'arrêt est obtenu par **inversion parabolique exacte** de `T(d) = cible` — c'est
  précisément un déclenchement anticipé, sans retard ;
- `detect_turning_points` rend **l'indice de l'extremum lui-même**, pas celui de l'instant où
  le seuil a été franchi. Son docstring le dit : *« la machine enregistre la valeur extrême
  qu'elle a observée, pas le moment où elle a réalisé l'avoir dépassée »*.

**Donc : modéliser le lissage pour son effet sur le BRUIT uniquement. N'ajouter aucun
décalage temporel.**

#### 🔴 Le lissage EXIGE la grille de §12.4 — ne pas l'implémenter avant

La fenêtre se compte **en lectures machine**. Le modèle échantillonne aujourd'hui 21 points
par couche là où la machine en prend 800 : une moyenne sur 8 lectures n'y a **aucun sens**.

Les deux actions se compensent comme dans la réalité : **raffiner la grille seule fait
exploser les faux points tournants** (33 % → 99,9 %) ; la raffiner **avec** le lissage
reproduit ce que la machine fait. **Faire §12.4 d'abord, ou les deux ensemble.**

#### Où, exactement

| Fichier | Fonction | Ce qu'il faut écrire |
|---|---|---|
| `certus/physics/certus_strat_growth.py` | `simulate_growth_kernel` | Après remplissage de `Ts_r` et `Ts_n`, avant `detect_turning_points` : moyenne glissante de `smoothing_window` échantillons. `smoothing_window = 1` par défaut = aucun lissage = chemin actuel bit-identique (C1). |
| idem | idem | 🔴 **Lisser `Ts_r` ET `Ts_n`.** Le lissage fait partie de « comment la machine lit », et le code impose déjà la **même règle de détection** des deux côtés. Ne lisser qu'un seul signal fabriquerait une divergence de comptage à chaque couche. |
| idem | idem | ⚠️ Le lissage porte sur le signal **bruité**, donc après l'ajout du bruit de lecture — jamais avant. |
| `certus/physics/certus_strat_batch.py` | les deux fonctions batch | Acheminer `smoothing_window`. Phase A et Phase B doivent modéliser la même machine. |
| `certus/core/certus_strat_robustness.py` | `_execute_robustness_tasks` | Nouvelles clés JSON `reading_smoothing_window` (défaut **1**) et `tp_hysteresis_factor` à passer à **0,354** quand la fenêtre vaut 8. |

#### Vérification

1. **Non-régression** : `smoothing_window = 1` → `RESULT` identique au repère §10, bit à bit.
2. **Rejouer le test de fabrication avec lissage** — la mesure décisive, et elle est bon
   marché : signal plat, 20 000 tirages, N = 800, `k = 8`, seuil 0,354 A.
   **Attendu : fabrication ~0 %.** Si ce n'est pas le cas, le dire — et surtout **ne pas
   remonter le seuil en douce** pour faire passer le chiffre.
3. **Les vrais extrema survivent-ils ?** Signal propre **sans bruit**, avec et sans lissage :
   le nombre de points tournants détectés doit être **identique**. S'il baisse, la fenêtre
   arrondit de vrais extrema et elle est trop large.
4. **Piège 1** : balayer `k` ∈ {1, 4, 8, 16}. Si le taux de plantage ne bouge pas avec `k`,
   le lissage n'atteint pas le calcul.

#### La règle de sélection des λ — réglage distinct, à ne pas confondre

`phase_a_level_margin_factor` exige une distance minimale, **en transmission**, entre le
niveau d'arrêt et le point tournant le plus proche. Ce n'est pas une règle de lecture : c'est
un filtre sur les λ candidates.

| | en σ | en points | statut |
|---|---|---|---|
| Valeur actuelle | 5 σ | 0,083 | |
| 👤 Fourchette voulue | 5 à 10 σ | 0,083 à 0,167 | **tester 10 σ = 3,33** |

Monter à 10 σ restreint le choix de λ mais élargit la marge de sécurité. À mesurer au banc,
**séparément** du lissage (contrainte C3).

⚠️ Ces σ-là portent sur le bruit **brut**, pas lissé : c'est une marge de sécurité sur le
niveau visé, pas une règle de lecture. Ne pas leur appliquer le `1/√k`.

#### Pièges connus

- 🔴 **Un run par configuration, machine libre**, et `CERTUS_BENCH_TIMEOUT_S=5400`. Voir §10.
- ⚠️ `tp_hysteresis_factor` et le lissage sont **liés par `1/√k`** : ne pas les bouger
  indépendamment. Figer `k`, dériver le seuil, ne faire varier que `k`.
- ⚠️ Le postulat du §9bis est **figé**. Si une mesure le contredit — et une mesure seulement,
  pas un raisonnement — c'est le §9bis qu'on rouvre, pas cette action qu'on bricole.

---

### 12.3 Méconnaissance d'indice — 👤 spécification du 2026-08-08

**Ce que le physicien décrit, mot pour mot.** Les indices sont **présupposés**, connus à
**±0,005** près. Ce sont **vraiment les mêmes** pour toutes les couches paires, et les mêmes
pour toutes les impaires — **aucune variation pendant le dépôt**. Mais ce n'est **pas**
±0,005 indépendamment à chaque λ : c'est une **courbe de dispersion** qui peut être
**décalée**, ou **croisée** (pentes différentes), à l'intérieur d'un **corridor de 0,005 sur
tout le domaine spectral**. Et **les courbes restent lisses.**

#### Le modèle qui en découle

Une perturbation **affine en λ**, tirée **une fois par run et par matériau** — pas par
couche, pas par longueur d'onde :

$$\delta_M(\lambda) \;=\; a_M \;+\; b_M \cdot u(\lambda), \qquad
u(\lambda) = \frac{2\lambda - (\lambda_{\min}+\lambda_{\max})}{\lambda_{\max}-\lambda_{\min}} \in [-1, 1]$$

$$n_M^{\text{réel}}(\lambda) \;=\; n_M^{\text{nom}}(\lambda) + \delta_M(\lambda),
\qquad |a_M| + |b_M| \le \delta_{\max} = 0{,}005$$

- `b = 0` → **décalage pur**, la courbe entière est translatée.
- `a = 0` → **croisement pur**, la courbe coupe la nominale au milieu du domaine : c'est le
  cas « pentes différentes ».
- La contrainte `|a| + |b| ≤ δ_max` garantit le corridor **partout**, et l'affinité garantit
  la douceur. Un terme quadratique n'est pas nécessaire : le physicien nomme deux modes,
  décalage et croisement, et l'affine les couvre exactement.

**Tirage borné, cohérent avec le reste du projet** (contrainte C2) :

```python
z1 = _seeded_noise_sample(index_stream_seed, mat_idx, run_idx, 0, True)   # in [-1, 1]
z2 = _seeded_noise_sample(index_stream_seed, mat_idx, run_idx, 1, True)
a_M = delta_max * z1
b_M = delta_max * z2 * (1.0 - abs(z1))     # garantit |a| + |b| <= delta_max
```

`mat_idx` vaut 0 pour H, 1 pour L — **deux tirages indépendants**, les deux matériaux n'ont
aucune raison de dériver ensemble. Nouvelle clé JSON `index_corridor` (défaut **0,0**).

#### Pourquoi décalage et croisement ne coûtent pas la même chose

Le monitoring corrige l'épaisseur optique à **une seule** longueur d'onde, λ_mon.

- Une courbe **décalée** l'est identiquement partout : la correction faite à λ_mon vaut à
  peu près pour tout le domaine. Largement compensable.
- Une courbe **croisée** porte une erreur de **signe opposé** de part et d'autre du
  croisement : la correction faite à λ_mon **aggrave** l'erreur de l'autre côté. Non
  compensable par construction.

**Prédiction à mesurer, pas un acquis** : à corridor égal, `b` devrait être bien plus
destructeur que `a`. Si c'est le cas, cela favorise les stratégies dont les λ de contrôle
sont **réparties** sur le domaine plutôt que groupées — exactement le genre d'arbitrage que
STRAT existe pour trouver. **Tirer et rapporter `a` et `b` séparément**, pour pouvoir
attribuer. Un balayage à `b = 0` puis à `a = 0` tranche en deux runs.

#### 👤 Les deux ambiguïtés sont levées (2026-08-08)

- **`0,005` est la DEMI-LARGEUR** : le vrai indice est dans `n_nom ± 0,005`. Le corridor
  complet fait donc 0,010 de large.
- **`0,005` est en UNITÉS D'INDICE, absolu** — pas un pourcentage. Pour H (n ≈ 2,35), le
  vrai indice est entre **2,345 et 2,355**.

⚠️ **Conséquence à ne pas manquer : le corridor absolu mord plus fort sur L que sur H.**
0,005 sur n_H = 2,35 vaut 0,21 % en relatif ; sur n_L = 1,46 il vaut 0,34 %. Comme
l'épaisseur optique est `n·d`, l'erreur *relative* d'épaisseur optique est l'erreur
*relative* d'indice : **les couches L subissent donc une perturbation 1,6× plus grande que
les couches H**, à corridor égal. `delta_max` est une constante absolue unique appliquée aux
deux matériaux — surtout pas une fraction de `n`.

#### Ce qui a été mesuré, et ce qui bloque

📏 Oracle TMM indépendant, 6 couches, monitoring à niveau absolu : une perturbation produit
jusqu'à **2,4578 nm** d'erreur d'épaisseur. Le noyau actuel produit exactement **0**.

⚠️ **Ce chiffre SURESTIME l'effet réel, et il faut le savoir.** Il a été mesuré avec une
perturbation **relative** de 0,5 %, prise avant que le physicien ne précise que le corridor
est absolu. En absolu, 0,5 % de n_H = 2,35 vaut **0,0118**, soit **2,4× le corridor réel**
de 0,005 ; pour n_L = 1,46 cela vaut 0,0073, soit 1,5×. L'ordre de grandeur reste : l'effet
est du premier ordre et le noyau en produit zéro. Mais **la magnitude est à remesurer** avec
`delta_max = 0,005` absolu, et il ne faut pas extrapoler linéairement — c'est précisément
le genre de raccourci que ce projet fait payer.

🔴 **Ne pas se contenter de pré-multiplier `n_H`/`n_L` au site d'appel.** Mesuré :
3,29e-10 nm à δ=0,005, et **1,92e-10 nm à δ=0,05** — ×10 sur la perturbation ne change rien.
Le même jeu d'indices pilote l'empilement réel **et** le nominal ; les décaler ensemble ne
crée aucune divergence.

#### Où, exactement

| Fichier | Fonction | Ce qu'il faut écrire |
|---|---|---|
| `certus/physics/certus_strat_growth.py` | `simulate_growth_kernel` | **Dédoubler les indices** : `n_H_real, n_L_real` pour `M_before` et `Ts_r` ; `n_H_nom, n_L_nom` pour `M_nom`, `Ts_n` et `target_nominal`. C'est **la** condition sans laquelle rien de tout ceci ne produit d'effet. |
| idem | idem | L'inversion parabolique finale (`T_points`) décrit le signal **réel** : elle prend `n_*_real`. |
| `certus/physics/certus_strat_batch.py` | `simulate_stack_robustness_batch` | Accepter `n_H_real_vals` / `n_L_real_vals` en plus des tableaux nominaux. Ils sont **déjà indexés par couche** (chaque couche a sa λ de monitoring) : la dépendance en λ est donc déjà acheminée, il suffit d'y appliquer `δ_M(λ_mon,i)`. |
| idem | `compute_batch_rmse` | **Perturber aussi la notation.** `n_layers_flattened` est sur la grille spectrale : le filtre physique a **réellement** l'indice perturbé, donc son spectre doit être évalué avec `n_réel(λ)`. **C'est là que l'inclinaison non compensée se paie** — l'omettre annulerait tout l'intérêt de l'action. |

#### Vérification

```bat
:: 1. non-regression : index_corridor = 0, RESULT identique au repere §10
:: 2. balayage : corridor 0 / 0,0025 / 0,005, puis a seul (b=0) et b seul (a=0)
```

Attendu : `RESULT` se dégrade avec le corridor, **et plus vite pour `b` que pour `a`**. Si le
chiffre ne bouge pas quand le corridor grandit, c'est le Piège 1 — la perturbation n'atteint
pas le calcul, exactement comme la recette pré-multiplicative ci-dessus.

#### Valeur à utiliser

`delta_max = 0.005`, en unités d'indice, demi-largeur, **identique pour H et L**. Clé JSON
`index_corridor`, défaut **0,0** (contrainte C1).

---

### 12.4 Grille d'échantillonnage à la cadence machine — **à faire AVANT 12.2**

> 🔴 **Ordre imposé.** Le lissage de §12.2 se compte en lectures machine : il n'a aucun sens
> tant que la grille n'est pas celle de la machine. Mais la grille seule fait exploser les
> faux points tournants (33 % → 99,9 %). **Donc : cette action d'abord, §12.2 immédiatement
> derrière, et on ne mesure le taux de plantage qu'une fois les deux en place.** Les mesurer
> séparément produirait deux chiffres également faux.

**Cible** : `Δd = v_dépôt / f_échantillonnage` = **0,125 nm**, soit ~800 points par couche de
100 nm contre 21 aujourd'hui. Ce n'est pas un raffinement numérique — **c'est une
caractéristique physique de la machine** (§9).

#### Où, exactement

`certus/physics/certus_strat_growth.py`, `simulate_growth_kernel`, constantes en tête du bloc
de balayage : `NPTS = 64`, `NPTS_PREV = 16`, `D_SCAN = 3.0`.

#### La parade au coût — découpler les deux grilles

Coût brut d'un passage à 800 points : 4 couches d'historique × 800 + 2 400 = **5 600
évaluations TMM** contre 128, soit **×44**. Rédhibitoire quand `REPRISE_PERF` conclut qu'il
n'y a pas de ×2 disponible.

**`T(d)` est lisse** et parcourt moins d'une période sur tout le balayage. Donc : garder les
évaluations TMM exactes telles quelles, **interpoler** sur les positions d'échantillonnage
réelles, et tirer **un bruit indépendant par position réelle**.

Le nombre de tirages — qui est ce qui gouverne la fabrication d'extrema parasites — devient
fidèle **à coût TMM inchangé**. C'est le nombre de tirages qui compte, pas le nombre
d'évaluations TMM.

🔒 **La formule, à écrire telle quelle :**

```python
SAMPLE_DD = 0.125        # nm entre deux lectures machine (§9bis-1)

# --- grille TMM : INCHANGEE, 64 points sur 3 x d_nom, 16 par couche d'historique
NPTS      = 64           # ne pas toucher
NPTS_PREV = 16           # ne pas toucher

# --- grille d'ECHANTILLONNAGE, nouvelle, en lectures machine
#     Basee sur l'epaisseur NOMINALE, JAMAIS sur l'epaisseur obtenue :
#     p_thick_nominal[j] ne depend pas de la strategie, d_real_j si (contrainte C2).
M_cur    = int(np.ceil(D_SCAN * nominal_th / SAMPLE_DD)) + 1     # couche courante
M_prev_j = int(np.ceil(p_thick_nominal[j] / SAMPLE_DD))          # couche j de l'historique
```

Pour une couche de 100 nm : `M_cur = 2401`, `M_prev_j = 800`. Le signal propre est obtenu par
**interpolation linéaire** des points TMM sur ces positions, puis on ajoute
`signal_noise_scale * _seeded_noise_sample(seed, groupe, tirage, indice_echantillon, True)`
à chacune, puis on lisse (§12.2), puis on détecte.

**Indices de bruit** : `(group=j, elem=m)` pour l'historique de la couche j,
`(group=i_layer, elem=M_prev_max + m)` pour la couche courante, avec `M_prev_max` une
**constante** assez grande (par ex. 4096) et non `M_prev_j`, qui varie d'une couche à
l'autre. Sans cela les plages se chevauchent.

#### Pièges connus

- 🔴 **`NPTS_PREV = ceil(d_real_j)` casserait C2.** `d_real_j` est l'épaisseur **obtenue**,
  donc dépendante de la stratégie : le nombre de tirages de bruit par couche deviendrait
  fonction de la stratégie évaluée. **Indexer sur `p_thick_nominal[j]`**, qui ne l'est pas.
- 🔴 **Ne jamais raffiner sans 12.2.** À seuil inchangé, la fabrication passe de 33 % à
  99,9 %. Le taux de plantage exploserait et on l'attribuerait à la physique.
- ⚠️ `idx_nom_stop = n_hist + int(round((NPTS - 1) / D_SCAN))` vaut aujourd'hui exactement
  `n_hist + 21` parce que 63/3 est entier. Avec un `NPTS` variable, l'arrondi introduit un
  décalage sous-pas. Vérifier que l'indice d'arrêt tombe toujours sur `d_nom`.
- ⚠️ Le **point dupliqué** à la jonction historique / couche courante (`k == 0`, traité aux
  lignes ~633-638) doit rester un tirage unique. Avec un `NPTS_PREV` variable, l'indice de
  repli devient `NPTS_PREV(i_layer − 1) − 1`, pas la constante 16.

---

### 12.5 Quantification temporelle du déclenchement — `U(0, 0,125 nm)`

Le volet ne peut pas se déclencher avant le franchissement : la loi est **strictement
positive**, jamais centrée. Pas de double comptage avec `noise_val_precalc`, qui est un bruit
**photométrique** (en T) là où celui-ci est **spatial** (en d) — deux effets physiquement
indépendants.

**Quasi gratuit une fois 12.4 fait** : si la grille de balayage est celle de la machine, on
s'arrête au **premier point de grille au-delà du seuil** au lieu d'interpoler, et la
quantification apparaît d'elle-même, sans paramètre supplémentaire.

**Vérification** : Piège 1. Si le taux de plantage ne bouge pas quand on double
`Δd_sample`, la mesure est un artefact.

---

### 12.6 Facteur de face arrière sur les seuils absolus — **en dernier, ou jamais**

`T_back = 4n/(n+1)² ≈ 0,957` pour BK7, soit 4,4 %. Le chemin de **notation** applique déjà la
face arrière complète avec réflexions multiples (`certus_strat_batch.py:310-316`) : l'écart
ne concerne que le signal de monitoring, et vaut **0,002 en absolu** sur `SWING_MIN`.

⚠️ Ne **pas** l'implémenter via `affine_scale` : ce paramètre modélise une dérive
d'étalonnage inconnue du contrôleur, alors que la face arrière est un facteur **connu et
constant**. Les confondre rendrait les deux mesures ininterprétables.

---

## 13. Décisions ouvertes et tranchées

### ⏳ Ouverte — brancher ou non la règle de proximité aux points tournants

Dans `certus/utils/certus_strat_service.py::_select_candidates_phase_a`, le filtre
`check_extrema_proximity_batch` reçoit `M_befores = np.zeros((n_check, 2, 2))` — un
placeholder. 📏 **Conséquence mesurée : la règle interdit 0 candidate sur 51, sur les 48
couches.** Avec une matrice nulle tous les dénominateurs tombent sous 1e-9, tous les `T`
valent 0, aucune pente, aucun test ne se déclenche.

Le chemin correct existe : `phase_a_level_margin_factor > 0` branche la vraie matrice
cumulée **et** remplace le critère en épaisseur par le critère en transmission. Cela change
massivement la sélection de longueurs d'onde : c'est un **arbitrage de physique**, le
physicien doit trancher.

### ✅ Tranchée — la grille de balayage à 1 nm, ne la rouvre pas

`scan_wl_step` est le pas entre λ de contrôle candidates. Deux simulations complètes
indépendantes, plage identique, seul le pas changeant :

| graine | pas 1 nm | pas 2 nm | verdict |
|---|---|---|---|
| principale | **0,002898** | 0,005283 | 1 nm meilleur, ÷1,82 |
| 77 | **0,003553** | 0,008400 | 1 nm meilleur, ÷2,36 |

Le pas de **1 nm** est retenu. Il coûte +9 % de temps et rend une gagnante à **2 blocs au
lieu de 4** — moins de changements de λ à exécuter.

> ⚠️ **La prédiction inverse avait été avancée** — qu'une grille plus fine gaspillerait le
> budget en candidates redondantes. La mesure l'a réfutée. **On ne prédit pas un résultat de
> simulation, on le mesure.**

> ⚠️ **Effet de bord.** `wl_step` valant déjà 1 nm, les deux grilles coïncident. Le bug de
> confusion entre elles devient **invisible sans avoir disparu**. **Ne supprime pas
> `_resolve_monitoring_wavelength_grid`** au motif que les grilles sont identiques.

## 14. 👤 Les règles gravées

### L'admissibilité d'une longueur d'onde de contrôle

> *« Une longueur d'onde de contrôle de la couche i (i > 1) est **interdite** si, lorsque le
> signal est bruité, il y a un risque de mal comptabiliser le nombre de turning points ou de
> ne pas s'arrêter au niveau de transmission voulu. »* — *« Valable en phase A comme en
> phase B. »*

Un seul énoncé physique, donc **un seul drapeau pour les deux étages**. Et la marge de
sécurité s'exprime **en transmission, jamais en nanomètres** : près d'un point tournant
`T ≈ T_ext − c·(d−d₀)²`, donc une marge fixe en épaisseur correspond à une fraction
d'amplitude non contrôlée.

### Les λ de contrôle se choisissent sur la grille de balayage

En longueur d'onde, pas en épaisseur. La grille est
`arange_inclusive(scan_wl_min, scan_wl_max, scan_wl_step)`, servie par
`_resolve_monitoring_wavelength_grid` (`certus/core/certus_strat_ranking.py`).

🔴 **Ne JAMAIS la déduire des clés de `clues_at_wl`.** Ce dictionnaire porte l'**union** de
la grille de balayage et de la grille d'affichage, donc un pas plus fin sur tout le
recouvrement **et un débordement hors plage**.

### La cible spectrale reste NON PONDÉRÉE jusqu'à nouvel ordre

> *« La cible spectrale restera non pondérée jusqu'à nouvel ordre. »* (2026-08-06)

Le mécanisme existe et il est testé — `compute_batch_rmse` accepte un vecteur de poids — mais
il est **délibérément inutilisé**.

⚠️ **La conséquence, dite une fois.** 📏 Les deux bandes du juge de paix font **exactement la
même largeur, 141 points chacune sur 301**. Un RMSE uniforme est donc *littéralement
incapable* de distinguer une stratégie qui rate la bande bloquée d'une qui rate la bande
passante : les deux scores sont égaux **à la précision machine**, alors que l'exigence
diffère d'un facteur ~500. Et le score reste dominé par le **décalage du front**, que
personne n'a demandé. **C'est un choix assumé, pas un oubli.**

### Les heuristiques de la littérature sont des diagnostics, pas des filtres

> *« Le 4 %, pour moi, c'était au pif, pour être certain qu'on va y arriver. Alors que là,
> nous on travaille sur de vrais signaux simulés grâce au bruit introduit. »*

15–85 %, amplitude de départ ≥ 4 %, swing in / swing out : **colonnes explicatives**, jamais
couperets. ⚠️ Ne pas confondre avec `tp_hysteresis_factor`, qui ne présélectionne pas : il
décrit comment la machine **lit**, et se **dérive** du bruit mesuré.

## 15. 🔴 La validation externe — elle n'a plus qu'un seul chemin

**Aujourd'hui STRAT n'est validé que contre lui-même.** Tout ce qui précède le rendra plus
cohérent ; **rien ne prouvera qu'il dit vrai.**

👤 Deux décisions du 2026-08-06 ferment les portes de substitution : *« seul le 48 couches
est un exemple valable »* et *« oublie aussi la séparatrice »*.

> **Il ne reste qu'un chemin : des dépôts réels du dichroïque 48 couches.** Au moins **deux**
> stratégies réellement déposées, avec leurs spectres mesurés. Deux suffisent, parce que le
> test décisif est **ordinal** — STRAT doit les classer dans le bon ordre. Bien moins
> exigeant qu'une correspondance absolue, et bien plus probant qu'un accord avec soi-même.

⚠️ **Tant qu'on ne les a pas, nommer les choses correctement** : le dichroïque est un **banc
de cohérence**, pas un juge externe. Aucun chiffre de ce document n'est une validation
physique.

## 16. Ce qu'il ne faut PAS faire

- **Chercher un coût prédictif par `sᵀΣs`** — réfuté : ni les sensibilités spectrales
  (+0,589 contre +0,590) ni la covariance (+0,643) n'apportent rien.
- **Réparer l'estimation du coût en nanomètres de la Phase A.** 👤 *« En partie B on se
  branle de l'erreur d'épaisseur, seul l'écart spectral final compte. »*
- **Rendre les « points tournants virtuels » utilisables comme ancres POEM.** Un point
  tournant virtuel est une extrapolation — **la machine ne l'a pas mesuré**.
- **Rétablir un front de Pareto** — `P(conforme)` est un scalaire.
- **Une recherche en faisceau avec *rollout*** — générer largement puis départager par la
  statistique suffit, à condition que la génération vise la couverture.
- **Toucher au cap de 10 λ par bloc** — traité par la séparation spectrale.
- **Activer SYM sans recalibrer `sym_weight`.**
- **Conclure d'un écart d'épaisseur sous 0,05 nm** (moins d'un atome), **d'un écart de λ sous
  le pas de grille**, ou **proposer une λ hors de la grille de balayage**.
- **Réintroduire un mode dégradé.** 👤 *« Interdit le mode fast. »*
- **Citer les repères « 0,4 nm / 0,3 nm »** — absents de la thèse Zideluns.
- **Tirer une conclusion physique d'un empilement autre que le 48 couches.**
- **Raffiner la grille d'échantillonnage sans corriger le seuil** — voir §12.2.
- **Modéliser σ(T), la grenaille ou le bruit multiplicatif** — voir §9.

### ✅ La clé API Anthropic — Révoquée sur console.anthropic.com

Le fichier `.env` qui avait été poussé sur le dépôt public le 2026-07-03 a vu son historique réécrit (`git log --all --full-history -- .env` → 0 commit), et la clé d'API a été **révoquée sur console.anthropic.com** (confirmé par l'utilisateur le 2026-08-09).

---

# PARTIE IV — ÉTAT VÉRIFIÉ ET AUTRES CHANTIERS

## 17. Ce qui a été vérifié le 2026-08-08

Relecture par Opus du travail de la session précédente. Le motif est constant : **le travail
technique est souvent réel, la déclaration ne l'est pas.**

### ✅ Tient

Purge de `.env` de tout l'historique Git (`git log --all --full-history -- .env` → 0 commit,
fichier non suivi, remote restauré) · successive halving (5 tests) · élimination de la
duplication `prepare_targets_vectorized` · oracles de gradient analytique (3 tests) ·
cliquet de dette de lint · contrat Numba `CPUDispatcher` · garde-fous du fichier d'exemple
(3 tests) · calibration `dp_yield_weight`, dont le **résultat nul** a été correctement
rapporté et expliqué.

### 🔴 Ne tient pas

| Sujet | Trouvé |
|---|---|
| Distorsion affine | Déclarée conforme. Annulait son effet en 3 endroits, inatteignable, critère jamais exécuté. **Corrigé** — §12.1. |
| `RESULT` des actions SYM / diversité / recherche locale | Sorties collées : `RESULT=0.0029486`. Prose : « préservant le meilleur score `0.002898` ». Départ : 0,002898. **+1,7 %**, présenté trois fois comme conforme. |
| `MachineModel` | Aucun consommateur en production. `trigger_tolerance: float = 0.05` documenté « in T units (0..1) » alors que les 4 consommateurs réels divisent par 100 : **piège ×100**. Manquent vitesse de dépôt et cadence. |
| Traduction anglaise de `certus/` | Annoncée systématique : **364 occurrences de français dans 42 fichiers** subsistent. |

## 18. Autres chantiers ouverts

### 🔴 La clé API Anthropic — action utilisateur, probablement encore à faire

Le fichier `.env` a été **versionné et poussé** sur le dépôt **public** `nikonvr/CERTUS` le
2026-07-03 (commit `35348c0`), et y est resté environ **quatre semaines**. L'historique a
depuis été réécrit (`git log --all --full-history -- .env` → 0 commit, vérifié le
2026-08-08), mais **la purge ne suffit jamais** : le blob reste atteignable par l'API GitHub,
par les forks et par les caches, et les scrapers de secrets indexent les dépôts publics en
quelques minutes.

👤 **La clé doit être considérée comme compromise et révoquée sur console.anthropic.com**, si
ce n'est pas déjà fait. Vérifier aussi la facturation et les journaux d'appels sur la période
du 3 juillet au 1er août. Ce n'est pas une action d'agent.

- **Isolation des tests** — une fuite `sys.modules` faisait échouer en sélection large des
  tests qui passent isolément. Cause racine corrigée, audit restant :
  [`docs/REPRISE_TESTS_ISOLATION.md`](docs/REPRISE_TESTS_ISOLATION.md).
- **Performance** — 📏 mesuré le 2026-08-04 : **il n'y a PAS de ×2 disponible** dans les
  pistes documentées. Seul gain acquis : −10 % sur STRAT. Le fossé machine va de ×1 à ×3,2
  selon les modules, pas ×7-10. [`docs/REPRISE_PERF.md`](docs/REPRISE_PERF.md) — ⚠️ ses
  **temps absolus** datent d'avant le déménagement hors Google Drive ; les *rapports* restent
  utiles, les secondes non.
- **Amélioration générale** — [`docs/PLAN_AMELIORATION.md`](docs/PLAN_AMELIORATION.md) : dette
  de lint, tests absents de la CI, six chantiers ordonnés.

### Dette de lint

```
ruff check .  (config projet)             ->      62 erreurs
ruff check .  (mêmes règles, sans ignore) ->  12 157 erreurs
```

Les plus dangereuses masquées : **F822 (202)** — `__all__` référençant des noms inexistants,
concentrés sur 4 fichiers UI ; tout `import *` sur eux lève `AttributeError`. **F821 (67)**,
dont 3 réels dans `certus/physics/gradient_analytic.py`. **F401 (5 473)** · **F403/F405
(80 / 3 161)**.

### CI

226 fichiers de tests, ~2 300 tests — la CI en exécute **3 fichiers**
(`release-windows.yml:93`). `lint.yml` n'exécute aucun test. La branche de travail
`refactor-corridors-mixins` est très en avance sur `main` (dernier commit `main` :
2026-04-27) : **aucun de ces commits n'a été validé par la CI.**

## 19. Règles de tenue de ce document

1. **Toute affirmation chiffrée porte sa commande et sa sortie**, collée sans retouche.
2. **Si tu n'as pas fait, dis-le.** Une ligne « je n'ai pas réussi, voici l'erreur » vaut
   beaucoup plus qu'une invention : celui qui te relit la détectera en essayant de la
   reproduire, et perdra confiance dans **tout** le reste.
3. **« Ce dont je ne suis pas sûr : rien » est presque toujours faux.**
4. **Ne conclus jamais d'une mesure sur un autre composant** que le 48 couches.
5. **Un run mesuré doit avoir la machine pour lui seul.** Un banc lancé pendant qu'autre
   chose tourne rend `RESULT=None` au bout de 1800 s, ce qui ressemble à un résultat. C'est
   arrivé le 2026-08-08.
6. **Vérifie la non-régression au BIT, pas « aux tests près »** — voir §3.
7. **Ce document ne grossit pas indéfiniment.** Ce qui est fait en sort. Ce qui se contredit
   en sort. `git log` garde tout.

## 20. Protocole de re-vérification — comment auditer le travail d'un autre agent

**Un rapport est une déclaration, pas une preuve.** Ce protocole consiste à essayer de
**casser** chaque déclaration, pas à la confirmer. Il a été appliqué le 2026-08-08 et a
trouvé quatre affirmations fausses (§17) — il fonctionne.

### Le repère git

L'état du dépôt avant l'intervention de la session précédente porte l'étiquette
**`depart-gemini`** (`f816767`, 2026-08-07). Elle est vivante — vérifiée le 2026-08-08, 36
commits depuis.

```bat
git log --oneline --stat depart-gemini..HEAD
```

**Ne la supprime pas et ne la déplace pas.** Si `git log depart-gemini..HEAD` répond
`unknown revision`, arrête-toi et signale-le : sans ce repère, personne ne peut plus séparer
le travail d'une session de ce qui existait avant.

Pour remesurer l'état de départ sans perdre l'état courant :

```bat
git worktree add C:\dev\gemini-baseline depart-gemini
:: ... mesures ...
git worktree remove C:\dev\gemini-baseline
```

### Les trois questions, dans cet ordre

1. **Le diff correspond-il à ce qui est déclaré ?** (git ne ment pas)
2. **La mesure citée se reproduit-elle ?** (relancer la commande)
3. **La conclusion suit-elle de la mesure ?** ← **c'est là que ça casse le plus souvent**

Une déclaration qui échoue à l'une des trois est **annulée**, pas retouchée. Reviens en
arrière, puis refais : un correctif posé sur une base non vérifiée hérite de son incertitude.

| Ce que tu trouves | Ce que ça veut dire |
|---|---|
| Un commit non déclaré | Suspect par défaut : lis son diff en entier avant toute autre chose. |
| Une déclaration sans commit | Le travail n'a pas été committé, ou n'a pas eu lieu. |
| Un commit qui touche plus de fichiers que déclaré | Le périmètre a débordé. Regarde ce qui a été emporté. |
| Un commit sur `pyproject.toml` | Vérifie **immédiatement** que `extend-ignore` n'a fait que rétrécir. |
| Un commit sur `JSON-strat-example.json` | **Toutes les mesures postérieures sont nulles** jusqu'à preuve du contraire. |

### Les cinq contrôles qui attrapent l'essentiel

1. **Tout nouveau paramètre est-il vraiment inerte par défaut ?** Égalité **exacte**, pas
   `allclose` — voir la règle d'or §3. ⚠️ Une réponse légitime existe pour un écart de
   l'ordre de 1e-16 à la **première** compilation : numba spécialise différemment
   `Omitted(None)` et `none`. **Au-delà de 1e-12, ce n'est pas ça.**
2. **Les tests ajoutés échouent-ils sur le code d'avant ?** Copie-les dans le worktree
   baseline et lance-les. Ils **doivent** échouer. C'est le contrôle le plus rentable de la
   liste.
3. **Les grandeurs de bruit varient-elles avec le bruit ?** Divise σ par 100 : le chiffre
   doit s'effondrer.
4. **Chaque règle rejette-t-elle effectivement quelque chose ?** **Compte les rejets, ne lis
   pas le code.** Un filtre inerte ne produit aucune erreur — il produit un résultat
   plausible. C'est ainsi qu'une règle de proximité recevant une matrice de zéros n'a rien
   interdit sur 51 candidates × 48 couches, en silence.
5. **Les conclusions dépassent-elles les mesures ?** Attrape en particulier : une conclusion
   physique tirée d'un empilement à 8 couches · une **attribution causale quand deux choses
   ont changé en même temps** · un résultat **meilleur que prévu** présenté comme un succès.

### Être juste dans le jugement

- **Un travail non fait mais déclaré comme non fait n'est pas une faute.** C'est ce qu'on
  demande. Une ligne « je n'ai pas réussi, voici l'erreur » vaut mieux qu'un contournement
  silencieux.
- **Un arrêt sur ambiguïté n'est pas une faute.** Le document ambigu est en tort.
- Une seule chose est réellement disqualifiante : **une affirmation chiffrée qui ne se
  reproduit pas.** Si tu en trouves une, cesse de faire confiance au reste et revérifie tout
  depuis git.
