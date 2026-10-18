# Audit de la suite CERTUS — 2026-10-18

> Mesure datée, pas un document vivant : l'état courant est dans `docs/ETAT.md`, les règles dans
> `CLAUDE.md`. Les défauts non corrigés ci-dessous sont à reporter dans `docs/ETAT.md` §4 par 👤
> (ce fichier est édité en parallèle par une autre session, je n'y ai pas touché).

**Code audité** : branche `claude/ecstatic-newton-3grmls`, HEAD `ccd67d59`. Entre le début et la fin de
l'audit, deux commits d'une autre session (12:05 et 12:06) ont ajouté `studies/bonne_mere/` et 7 lignes à
`docs/ETAT.md` ; **aucun fichier de code n'a changé** (vérifié par `git diff 6e546515 ccd67d59` sur
`certus/`, `scripts/`, `tools/`, `tests/`, `pyproject.toml`, `CLAUDE.md`). Le ruff et l'oracle série ont été
mesurés à `6e546515`, le reste à `ccd67d59`.

**Hors périmètre, à la demande de 👤** : `bonne mere/` (racine, vide), `studies/bonne_mere/`,
`tmp/bonne_mere_*`. Les balayages portent sur les fichiers **suivis** (`git ls-files` / `git grep -c
core.longpaths=true`), jamais sur `.claude/worktrees/`.

**Machine** : Windows 11, 16 cœurs, 31,3 Go. Validation lancée sur 16 workers `pytest-xdist` : CPU moyen
89 %, pic 100 %, RAM libre minimale 13,1 Go (le run a consommé environ 8 Go).

**Commits produits par l'audit** (locaux, rien n'est poussé) : ce rapport `e52194a7` ; A1 `f32734a9` ; A2
`8610e18d` ; A3 `f7edd4a6` ; A5 `f494b9e5` ; A6 `e1acab83` ; A19 `3a2b443f` ; A7 `36758165` ; correction de mon
propre test de A5 `3d64d326` ; la mise à jour de ce rapport `9f1b8ccb` ; A20, demandé ensuite par 👤, dans un
commit qui retrouve avec `git log -S"cache=False ON PURPOSE" --oneline`. A4 est un réglage Git local, sans commit.

## 1. Verdict

Le socle scientifique et l'ingénierie sont sains : lint, typage, audit de dépendances, oracle TMM, frontières
d'architecture et indicateurs de `ETAT.md` se confirment à la mesure. Je n'ai trouvé ni secret, ni donnée
personnelle d'un tiers, ni pièce de tiers dans l'index. Quatre sujets demandent une action :

1. **Deux défauts de production reproduits** : l'analyse Monte-Carlo colorimétrique de DESIGN
   (`ColorWorker`) échoue à chaque exécution (C01, corrigé) ; une entrée du cache Numba peut faire **planter
   l'interpréteur** à sa relecture, et votre cache réel en contient une (C18, parade appliquée : A20).
2. **La suite de tests n'est pas sûre en parallèle** : une course sur un répertoire de préférences partagé
   (C02, corrigé) et un audit d'ergonomie sensible à la charge (C03). En série, tout ce qui a échoué en
   parallèle passe.
3. **Des pièges d'outillage qui produisent de fausses alertes ou une fausse sécurité** : chemins longs de
   Windows (préflight, `git grep`), pointeur d'archive périmé, et une porte de CI qui ne lisait pas le
   paquet (C04, C05, C19 : corrigés).
4. **Des choix qui ne sont pas les miens** : comportement sur NaN et épaisseurs négatives (C06, C07), octets de
   référence des rapports, sort de `studies/bonne_mere` avant tout push (C09, C15).

## 2. Ce qui a été mesuré

| contrôle | résultat | condition |
|---|---|---|
| `ruff check .` | All checks passed | `6e546515` et `ccd67d59` |
| `tests/oracle/` | **1146 passed** en 14,57 s | série, `6e546515` |
| `tests/unit/` | 5503 passed, **1 failed**, 7 skipped, 5 min 42 | 16 workers, `loadfile`, `ccd67d59` |
| `tests/ui/` | 1322 passed, **2 failed**, 2 xfailed, **12 errors**, 5 min 43 | 16 workers |
| reste de `tests/` | 319 passed (16 workers, sans `performance`) + 40 passed (série, 25 s) = **359** | |
| `coherence_md.py`, `check_claude_md.py`, `check_docs.py` | 0 point chacun | |
| `mypy` (`domain`, `physics`, `core`) | Success, 95 fichiers | mypy 2.4.0 |
| `pip-audit -r requirements.lock --strict` | No known vulnerabilities found | pip-audit 2.10.1 |
| `dead_symbol_audit --ci`, `lambda_connect_audit --ci` | 4 004 définitions, 0 non résolu ; 0 site | |
| `verifier_html.py pages/CERTUS_STRAT.html` | 0 point | |
| `metrics.py --rapide` | 20 arêtes montantes, 1 cycle, 32 fonctions > 300 lignes, 12 de CC > 60, 18 fichiers > 1 500 lignes, 0 `except` large avalé, 0 test sans assertion | identique à `ETAT.md` |

Les totaux de collecte (oracle 1146, unité 5504 + 7 ignorés, UI 1324 + 2 xfail, reste 359) sont **exactement**
ceux de `docs/ETAT.md`. Chaque échec obtenu en parallèle a été rejoué seul, en série, sur machine au calme :
le test de préférences passe ; `test_ux_button_min_height` 12/12, `test_ux_skeleton` 11/11 et
`test_ux_tab_order` 12 ignorés (« no promotional or no synthesis tab », comme la référence).
**Non refait en série** : les suites `unit` et `ui` complètes (la référence de CLAUDE.md §2).

### Après les correctifs (code au commit `3d64d326`)

| contrôle | résultat | condition |
|---|---|---|
| `ruff check .`, `mypy` (95 fichiers) | All checks passed ; Success | |
| trois contrôles documentaires | 0 point chacun | |
| `tests/oracle/` | 1146 passed en 12,8 s | série |
| `tests/unit/` | **5 513 passed, 7 skipped, 0 failed** en 5 min 09 (un premier passage avait relevé un échec de mon propre test de A5, corrigé en `3d64d326` et rejoué ici) | 16 workers, `loadfile` |
| `tests/ui/` | 1324 passed, 12 skipped, 2 xfailed, **0 échec** (deux mesures : 289 s et 307 s) | **6 workers** |
| reste de `tests/` | 319 passed (16 workers) + 40 passed (série) = **359** | |

`unit` compte 5 513 tests au lieu de 5 504 : neuf tests ajoutés par les actions A1, A2, A5, A6, A7 (trois) et
A19 (deux). Le statut Git est identique avant et après chaque passage : les tests ne laissent rien. Pendant la
validation, CPU moyen 85 %, pic 100 %, RAM libre minimale 14,2 Go sur 31,3.

### Après A20 (`cache=False` sur trois appelants, demandé par 👤)

`scripts\c1_diff.py HEAD`, corpus complet, à froid contre à froid : **9 092 tableaux identiques au bit**
(dont 1 084 du nouveau corpus `appelants`). Pas de nouveau paramètre : seul le drapeau `cache` de trois
décorateurs change.

| passage | résultat | ce que c'était |
|---|---|---|
| 1er, cache froid (la clé de cache a bougé) | oracle 1 146 passed ; `ui` (6 workers) 1 324 passed, 12 skipped, 2 xfailed ; `perf` 40 passed ; `unit` **1 échec**, `rest` **1 échec** | `unit` : `test_c1_diff_sees_one_ulp.py` épinglait le tuple du corpus par défaut, que A20 élargit : test mis à jour, plus un test qui exige que le corpus `appelants` n'ait aucun refus. `rest` : `test_bare_substrate_transmission_bounds` (Hypothesis, limite de 1 s) a payé la première compilation de `calculate_bare_substrate_RT` à froid, 2,2 s, puis 64 ms ; vert 3 fois de suite à chaud |
| 2e, cache chaud | `rest` 319 passed ; `unit` **1 échec** | `test_the_real_kernels_run_and_a_real_slowdown_is_caught` (chronomètre un noyau à la microseconde) sous 16 workers ; vert 3 fois seul, et son fichier (29 tests) vert ; noyau non touché |
| 3e, cache chaud | `unit` **5 516 passed, 7 skipped, 1 xfailed, 0 échec** en 4 min 49 | l'`xfailed` est la sentinelle sur Numba ; Git identique avant et après |

`unit` compte 5 516 tests passés au lieu de 5 513 : les deux tests de `test_the_cached_callers_of_parallel_kernels_survive_a_reload.py`
(balayage, rejeu) et le test de corpus ajouté à `test_c1_diff_sees_one_ulp.py`, plus la sentinelle en `xfail`.

## 3. Constats

### Fonctionnels

**C01 — `ColorWorker.run()` lève `TypeError` à chaque exécution** *(élevée ; reproduit)*.
`certus/workers/certus_design_workers.py:376` appelle `ColorWorkerResult.success(..., run_context=...)` ;
`success(lab_nom, labs, trace=None)` n'a pas ce paramètre. L'exception arrive après tout le calcul Monte-Carlo,
sort de `run()` (le tuple rattrapé `NUMERICAL_FAULT_EXCEPTIONS` ne contient pas `TypeError`) et n'émet ni
`finished` ni `error`. Rejoué de bout en bout avec des matériaux factices : *« ColorWorkerResult.success() got
an unexpected keyword argument 'run_context' »*, aucun signal reçu. Introduit le 2026-06-22 (`70507446`),
jamais détecté : `tests/unit/test_certus_design_workers.py` ne teste que `__init__`, et
`test_design_runs_carry_their_run_id.py` remplace le worker par un bouchon. Cause probable : copie du mot-clé
de la ligne 244, où `run_context` alimente `get_structured_logger`. C'est **pylint** (`unexpected-keyword-arg`)
qui l'a révélé ; le tri de ses autres messages est au §4.

**C18 — Une entrée du cache Numba peut faire planter l'interpréteur à sa relecture** *(élevée ; reproduit,
mécanisme isolé)*. Découvert en voulant tester la correction de C01 : relu depuis le disque, `calc_spectrum_front`
(`certus_tmm_matrix.py`, appelé par le cœur de DESIGN, les workers spectraux et RE) termine en
*Windows fatal exception: access violation* (code 139), alors que le même code **compilé à froid**, **sans JIT**
(`NUMBA_DISABLE_JIT=1`) ou relu depuis un cache **neuf** fonctionne. Mécanisme isolé dans un répertoire de cache
vide, avec trois processus : P1 sauvegarde seul l'appelé parallèle `calculate_RT_no_backside` ; P2 compile
l'appelant `calc_spectrum_front` pendant que l'appelé est **relu du disque** (P2 tourne correctement et sauvegarde
l'appelant) ; P3 relit l'appelant : plantage, déterministe. Quand l'appelé est compilé dans le même processus que
l'appelant (écriture puis relecture par le même script), tout va bien. Les deux caches réels de cette machine
contiennent une entrée défectueuse : le cache à clé `%TEMP%\CERTUS_Numba_Cache8de25316185` (écrit le 16/10, celui
que lit `tests/conftest.py`) et le cache par défaut `certus/physics/__pycache__`. Numba 0.67.0, Python 3.14.8,
Windows.

*Ce n'est pas un défaut de CERTUS.* Un **cas minimal autonome de 20 lignes** (annexe : deux fonctions Numba, sans le
code du projet) plante de la même façon à P3 avec Numba **0.65.1, 0.66.0, 0.67.0 et 0.68.0** (la dernière), sous
Python **3.14.8 et 3.12.12**, avec la couche de threading `omp` (celle que force `configure_numba_env`) comme avec
`workqueue`. Une mise à jour de Numba n'est donc pas une parade. Linux non testé. Deux parades tiennent sur le cas
minimal : ne pas mettre l'**appelant** en cache (m1), ou ne pas mettre l'**appelé** parallèle en cache (m2).

*Portée dans le projet* (analyse syntaxique par noms, appels directs et indirects, donc approximative : elle ne voit ni
les alias ni les appels par attribut) : **7 fonctions en cache sur 148** appellent un noyau parallèle en cache, toutes
dans `certus/physics/` : `calc_spectrum_front`, `calc_spectrum_full` et `compute_batch_rmse` (appelants non
parallèles, le cas reproduit), puis `calc_spectrum_full_exact`, `_calculate_RT_HL_core`, `_compute_tlu_derivatives_kernel`
et `cost_numba_fast` (appelants eux-mêmes parallèles). Une variante du cas minimal dont l'appelant est
`parallel=True` et appelle `callee` dans une boucle `prange` **ne plante pas** à P3 : les **trois appelants non
parallèles** sont la cible probable, les quatre autres ne sont pas exposés dans cette variante (les fonctions du
projet n'ont pas été rejouées). Seul `calc_spectrum_front` a été vu planter avec le code du projet.

C'est le cousin brutal de D52/D84 (`ETAT.md` : « compilation sur place contre lecture du cache, cause
non prouvée » — là, des écarts au dernier bit). Une entrée défectueuse persiste tant que le cache n'est pas vidé
ou que la clé des sources ne change pas. **Exposition du produit non mesurée** : elle dépend des signatures
que l'application compile et de l'ordre dans lequel les noyaux se mettent en cache. Les runs parallèles de
`unit` et `ui` se sont faits avec le cache à clé en place sans planter : aucun test ne relit cette entrée.

*Parade appliquée (A20)* : `cache=False` sur les trois appelants non parallèles, `calc_spectrum_front`,
`calc_spectrum_full` et `compute_batch_rmse` ; trois décorateurs, seuls changements du code de production. Leur
entrée de cache n'est plus lue : les deux caches défectueux ne sont plus dangereux pour ces fonctions, et il n'est pas
nécessaire de les vider. **Coût mesuré** : ces enveloppeurs sont compilés à chaque lancement de processus, les noyaux
parallèles étant relus du cache : 0,43 s, 0,22 s et 0,33 s au premier appel (environ 1 s au total), appel en régime
établi inchangé (quelques dizaines de µs). **C1** : `scripts\c1_diff.py HEAD`, à froid contre à froid, **9 092 tableaux
identiques au bit**. Le harnais n'appelait aucune de ces trois fonctions : un corpus `appelants` (1 084 tableaux) a
été ajouté, `VERSION_CORPUS` est monté à 3, et ce corpus **rejette** un décalage d'un ulp posé dans les trois
fonctions (691 différences sur 1 084 tableaux, 12 points d'entrée sur 12 dénoncés). **Trois tests** : un balayage des
sources qui nommait exactement les trois fonctions avant la correction, le rejeu du défaut sur les vrais appelants en
trois processus (code `0xC0000005` au troisième avant, 0 après, mêmes bits d'un processus à l'autre), et une
sentinelle `xfail` strict sur Numba seul qui passera au rouge le jour où Numba corrige.

**C06 — Un NaN dans les nœuds de spline devient `n = k = 0` sans alerte, sur le chemin par défaut**
*(moyenne ; latent ; reproduit)*. `get_nk_from_spline(..., use_cache=True)` (`certus_optical_models.py`,
`_compute_nk_from_spline`) applique `np.nan_to_num(np.clip(...))` : un nœud NaN contamine toute la base et
rend `n = k = 0` partout, alors que `use_cache=False` lève `ValueError` (CubicSpline). Le TMM, devant une
couche d'indice 0, ne rend pas NaN mais **un spectre fini et plausible** (R ≈ 0,078, T ≈ 0,922, R + T = 1) :
`require_finite` ne peut pas le voir, le NaN est déjà devenu 0. Appelants du chemin par défaut : les fenêtres
METAL (tracés, évaluations directes) ; gradient et plusieurs évaluations passent `use_cache=False`. Exposition
réelle modeste, mais c'est exactement la classe « résultat faux qui a l'air juste ».

**C07 — Le TMM accepte une épaisseur négative** *(faible à moyenne ; reproduit)*. `calculate_RT_vectorized_real`
avec d = −50 nm sur une couche absorbante rend sans erreur R + T ∈ [1,647 ; 2,086] (énergie créée). Les
validateurs de `certus_inputs.py` (`require_finite`, `require_layers_below_overflow`) ne contrôlent pas le signe.
Aucun flux connu ne produit d'épaisseur négative (bornes ≥ 0,01 nm dans l'optimiseur, `np.maximum(…, 0)` dans le
worker couleur).

**C08 — `open_file_explorer` masque l'erreur réelle** *(faible ; reproduit)*. `certus/ui/certus_io_ui.py` :
`import subprocess` est local à trois branches, mais la clause `except (OSError, subprocess.SubprocessError)`
de la branche « dossier » (`os.startfile`) le cite sans qu'il y ait été importé. Si `os.startfile` échoue :
`UnboundLocalError: cannot access local variable 'subprocess'` au lieu de la journalisation prévue.

**C12 — D107 confirmé de façon indépendante** *(déjà au registre ; en attente de 👤)*. `Target` est un
`@dataclass(slots=True)` à champs `lmin, lmax, tmin, tmax, w, on` : `t.val` et `t.weight` lèvent
`AttributeError`, avalée en `inf` ; comme `inf < inf` est faux, `best_idx` reste `candidate_indices[0]`. L'élagage
se comporte comme le simple repli « supprimer la couche la plus fine » ; l'évaluation des candidats n'a jamais
d'effet. Résultat raisonnable mais non optimisé, conforme à la description d'`ETAT.md`.

**C13 — `dk5` non affecté quand `arg == 0`** *(information ; bénin aujourd'hui)*.
`_njit_ir_global_gradient_fused` (`certus_index_objectives.py:160-169`) donne un défaut `0.0` à `dk6`, `dk7`
mais pas à `dk5`. Numba 0.67.0 initialise à 0,0 (mesuré, même avec une pile « salie »), et 0 est mathématiquement
juste pour β > 1. Le comportement repose pourtant sur un détail non documenté de Numba. Une correction touche un
noyau : vérification C1 (`scripts\c1_diff.py HEAD`) obligatoire.

### Tests et outillage

**C02 — La suite n'est pas sûre sous `pytest-xdist`** *(moyenne ; cause mesurée)*. `tests/conftest.py:62` ne crée
un répertoire de préférences privé que si `CERTUS_CONFIG_DIR` est absent de l'environnement ; les workers
xdist héritent la variable du contrôleur. Mesure : **un seul répertoire** pour le contrôleur et tous les workers.
`test_certus_core.py::test_save_export_config` (et un second test, ligne ~484) écrit `auto_export_enabled = True`
dans ce fichier partagé ; `test_user_preferences_are_isolated.py::test_the_automatic_export_is_off_under_test`
le lit au mauvais moment. Passe seul en série.

**C03 — L'audit d'ergonomie est sensible à la charge** *(moyenne ; constaté)*. Sous 16 workers :
`AUDIT CRITICAL: CERTUS_DESIGN worker failed 3 times: skeleton was still building: 111 controls when it looked
settled, 118 after 1.5 s more` → 2 échecs et 12 erreurs (la référence en série : 12 ignorés). Le seuil de
stabilisation de 1,5 s ne tient pas quand le CPU est saturé.

**C04 — Le pointeur d'archive des 2 242 JSON retirés est périmé** *(moyenne ; reproduit)*.
`reports/STRAT_Rate_publication_2026-10-16/archive_location.json` et son README donnent
`D:\drivefl\…\Archives_CERTUS_20261016` ; ce dossier **n'existe pas**. L'archive est là, sous `D:\drivfl\…`
(7 825 fichiers, 8,2 Go) : la graphie `drivefl` figure dans des dizaines de rapports du 14 au 16/10, c'était
le nom du dossier parent à l'époque. Par défaut `scripts/restore_rate_evidence.py` plante en
`FileNotFoundError` avec une trace ; avec `--archive-root` vers le vrai chemin : **`EVIDENCE=GO files=1
restored=0 verify_only=True`** (l'archive est intègre). Ne pas réécrire ces pièces : corriger le restaurateur.
C'est l'**unique** copie de ces données hors Git ; elle n'a pas de seconde sauvegarde.

**C05 — Le préflight et `git grep` comptent faux sous Windows** *(moyenne ; mesuré)*. Sans
`core.longpaths`, `git status` rend 62 entrées suivies (39 « supprimées ») et 179 avertissements ; avec : **24**
(1 suppression réelle), 0 avertissement. Les 38 suppressions fantômes sont des chemins > 260 caractères de
`reports/`. `scripts/preflight.py` (l. 245 et 258) interroge git sans l'option : son alerte « 62 fichiers
modifiés » est en partie fausse, et `ETAT.md` §0 cite « 62 modifications suivies préexistantes ». `git grep`
sans l'option rend 168 erreurs « Filename too long » et **ne scanne pas** ces fichiers : un scan de secrets
lancé ainsi serait incomplet sans le dire.

**C19 — La porte de CI « `connect(lambda)` » ne lisait que les 10 lanceurs de la racine** *(moyenne ; reproduit)*.
`tools/lambda_connect_audit.py` appelait `root.glob("*.py")` : il annonçait « 0 site — clean » (et la CI le
tolérait au plafond 0) pour un dépôt qui en contient **44** dans `certus/` (`git grep` : 44 ; l'outil corrigé : 44).
Le risque gardé est D11 (une lambda qui capture `self` retient une fenêtre fermée) ; la ligne 984 de
`certus_strat_ui_layout.py`, qui connecte le bouton « Open reports » à une lambda, en est un exemple. Même
famille de défaut que C05 : un contrôle qui ne rejette rien parce qu'il ne regarde pas au bon endroit.
`test_ci_lambda_connect_audit.py` exigeait « sortie 0 pour `--max-count 0` », ce qui n'était vrai qu'à cause du
défaut.

**C09 — 19 rapports `reports/STRAT_*` apparaissent modifiés sans l'être** *(faible)*. `git ls-files --eol` :
`i/lf w/crlf attr/-text`. Le `.gitattributes` du 16/10 a ajouté `-text` sur `reports/STRAT_*` après un checkout
converti en CRLF ; plus aucune conversion, donc plus de 13 000 lignes de différence apparente sur 22 fichiers `reports/`
(`git diff --stat` : 13 457 insertions, 13 446 suppressions ; 19 d'entre eux ne diffèrent que par les fins de ligne). Quelle version est la
référence de provenance ? Les empreintes SHA-256 des deux versions de deux fichiers testés ne sont citées par
aucun fichier suivi : indécidable par ce moyen.

**C10 — Écarts CI / déclarations** *(faible)*. (a) Aucun workflow ni test n'exécute les trois contrôles
documentaires de CLAUDE.md §2. (b) `pytest-benchmark` n'est pas déclaré (extras `dev`) : `test_kernel_benchmarks.py` et
`test_kernel_benchmarks_minimal.py` commencent par `pytest.importorskip("pytest_benchmark")`, donc la CI les
saute (lecture du code, pas de journal de CI consulté), alors que l'en-tête de `tests.yml` affirme
« AUCUN TEST N'EST EXCLU ». (c) `pytest-xdist` non plus.
(d) La CI fait `uv sync --upgrade` (dernières versions à chaque run) : choix de 👤 documenté, non remis en cause.

**C11 — Français dans `certus/`** *(faible)*. Règle n° 11 respectée à quatre lignes près sur 321 fichiers :
`certus/ui/certus_strat_stack_progress_widget.py` L45 `Matériau`, L53 `Épaisseur`, L59 `Statut d'analyse`,
L182 `Nettoyage précédent`. Le garde-fou les laisse passer (il exige un mot-outil de sa liste, et ne regarde que
le premier docstring de chaque définition) ; il est volontairement indulgent.

### Dépôt et processus

**C14 — Racine et index** *(faible)*. `UXargon.md` (130 Ko) et `designargon.md` : rapports d'audit non suivis à
la racine (règle n° 10). Écarts à la règle « seul `certus/domain/` a un `__init__.py` » :
`certus_physics/__init__.py`, `tests/property/__init__.py`. Un fichier `.tmp` de 1,4 Mo est suivi
(`reports/STRAT_Rate_suite_2026-10-15/R4_refinement/checkpoint_repair_01/checkpoint.json.tmp`, le plus gros blob
du dépôt). `.git/objects` contient 18 fichiers `tmp_obj_*` orphelins (12,4 Mo). 69 fichiers suivis correspondent
aussi à une règle d'ignorance (`reports/Report_*`) et sont invisibles à ripgrep.

**C15 — HEAD a bougé pendant l'audit** *(information importante)*. Une autre session a commité à 12:05
(`47582952`) puis 12:06 (`ccd67d59`) : 36 fichiers de `studies/bonne_mere/` (dont un PDF de 1,1 Mo et un DOCX)
sont maintenant dans l'index. La branche est **en avance de 2 sur le distant, rien n'est poussé**. Le hook
`post-commit` n'est pas armé (`core.hooksPath` absent, `.git/hooks/` ne contient que des `.sample`) : committer
ne publie pas. **Pousser publierait ce dossier sur le dépôt public.**

**C16 — Historique public** *(information)*. 4 commits portent l'identité civile de 👤 (nom et adresse Gmail) ;
1 499 utilisent l'adresse `noreply` de GitHub et 33 celle d'Anthropic. Donnée de 👤, son choix (CLAUDE.md §1) ; consigné.

**C17 — Typage** *(information)*. Les occurrences de `Any` dans `certus/` sont passées de 1 510 (base du
2026-09-30) à 1 920 ; les fonctions annotées de 72 % à 76 %.

## 4. Vérifié, sans écart

- **Secrets / données personnelles / tiers** : 0 correspondance sur 8 245 fichiers texte suivis (motifs AWS,
  GitHub, Slack, clés PEM, `sk-`, `password|token|secret|api_key` en littéral) et 0 adresse e-mail, avec
  contrôles positifs du détecteur ; les 347 classeurs Excel (269 `.xlsx`/`.xlsm` lus par `zipfile`, 78 `.xls`
  lus par `olefile`, recoupés par un lecteur OLE2 indépendant) ne portent que `CERTUS`, `openpyxl`,
  `Lemarchand`, `Fabien` ; aucun PDF ou document de tiers n'est suivi (les deux PDF « Selenium » de la racine
  ne le sont pas).
- **Appels dangereux** : ni `eval`, `exec` natif, `pickle`, `marshal`, `yaml.load`, `os.system`, `shell=True`,
  `allow_pickle=True`. Les `subprocess` utilisent des listes d'arguments.
- **Interdits de CLAUDE.md §3** : n° 2 (`extend-ignore` est passé de 68 règles à 7 depuis
  `depart-gemini` ; aucune règle n'est entrée) ; n° 4 (par rapport à `depart-gemini`, le juge de paix n'a perdu aucune
  clé : 14 ajoutées, `robustness_num_runs` 150 → 300 — durcissement net ; seule la clé `allow_rate = 1` élargit
  l'espace de recherche) ; n° 7 (oracle indépendant : `tmm_reference.py` n'importe que NumPy) ; n° 8
  (marqueurs `DO NOT SPLIT` présents) ; n° 3 (les JSON retirés de `reports/` l'ont été à la demande de 👤 et sont
  archivés, intègres : voir C04).
- **Architecture (CLAUDE.md §8)** : aucun import de PyQt6 ni de `certus.ui` dans `core`, `physics`, `domain`.
- **Physique** : 28 scénarios de contrainte, production contre l'oracle indépendant `tests/oracle/tmm_reference.py`
  (et Fresnel pour les couches épaisses), tous à ≤ 2,3 × 10⁻¹⁴ : films métalliques k = 3,5, substrat absorbant,
  couches évanescentes (n = 0,5 à 60° et 75°), incidence rasante 89,9°, λ de 5 à 20 000 nm, épaisseur nulle, s et
  p, avec et sans face arrière. En incidence normale, une couche opaque (|Im φ| > 700) est **refusée
  explicitement** plutôt que rendue comme (0, 0).
- **Numérique** : sur 16 sites de suppression d'avertissements (`np.errstate`, `warnings.simplefilter`), les 4
  du cœur lus sont fondés (NaN explicite hors domaine, borne d'épaisseur contre le débordement, préchauffage
  JIT). Sur 12 usages de `nan_to_num`, 5 lus : 3 sans reproche, 2 lignes problématiques dans une même fonction (C06).
- **pylint 4.1.2** (variables non liées, arité, mots-clés, imports de noms, itérabilité ; racine du dépôt mise
  dans `sys.path` pour qu'il résolve `certus.*`, sinon 1 465 faux `import-error`). Triés un à un : `possibly-used-
  before-assignment` (10 : un vrai latent, C13 ; les autres sont des branches corrélées lues dans le code),
  `unexpected-keyword-arg` (14 : **un vrai, C01** ; 13 faux positifs — pydantic générique, `ignoreBounds` de
  pyqtgraph), `assignment-from-none` (3, méthodes-crochets redéfinies par les sous-classes),
  `function-redefined` (1, idiome `None` puis `def`), `no-name-in-module` (53 hors PyQt6, façade `certus_ui.py`
  et modules de `scripts/`), `not-an-iterable` (58, tous des `prange` de Numba). **Non lus** : les 7
  `not-callable` (noms de rappels optionnels : `open_manual_fn`, `study_fn`, `hook`…, non vérifiés un à un) et
  5 des 9 `unsubscriptable-object` (les 4 lus sont gardés ou limités par l'inférence).
- **CI** : les 18 usages d'actions sont épinglés par SHA, droits `contents: read`, `persist-credentials: false`,
  `pip-audit` + gitleaks + CodeQL, Dependabot hebdomadaire pour les actions.

## 5. Ce que je n'ai pas mesuré

Les suites `unit` et `ui` complètes **en série** ; la couverture de tests ; l'exécution du gel
(`tools\build_frozen.ps1`, `release_checks.py`) ; les autres pages `pages/*.html` (une seule a été vérifiée) ; `bandit` ; les 12 autres sites de suppression
d'avertissements numériques (ui, utils, workers, dont 4 filtres pyqtgraph identiques) et 7 des 12 usages de
`nan_to_num` ; le contenu de `studies/` (exclu). Pour les 69 `.xls` sans flux d'auteur, il n'y a rien à lire. La physique n'a pas été
éprouvée en polarisation mixte ni pour des milieux anisotropes.

**Sur C18 (cache Numba)** : le défaut n'a pas été cherché sous Linux ; les quatre appelants eux-mêmes parallèles
du projet (`calc_spectrum_full_exact`, `_calculate_RT_HL_core`, `_compute_tlu_derivatives_kernel`,
`cost_numba_fast`) n'ont pas été rejoués (une seule variante minimale à appelant parallèle, qui ne plante pas) ;
la parade m1 est vérifiée sur le cas minimal et sur le rejeu des vrais appelants (A20), pas dans l'application entière ; je ne sais pas si
l'application, avec ses propres signatures d'appel, compile et relit un jour une entrée défectueuse. Pour
l'étage `ui`, 8 à 12 workers ne sont pas essayés (6 est mesuré sûr, 16 ne l'est pas).

**Environnement modifié sur demande de 👤** (interpréteur global, site utilisateur) : `pytest-xdist 3.8.0`
(+ `execnet 2.1.2`), `olefile 0.47`, `pylint 4.1.2` (+ `astroid 4.3.3`), `mypy 2.4.0`, `pip-audit 2.10.1`
(+ leurs dépendances). Aucun fichier du dépôt n'a été modifié par ces installations. Quatre environnements virtuels
jetables ont servi à C18 (Numba 0.65.1, 0.66.0, 0.68.0 sous Python 3.14.8, et 0.68.0 sous Python 3.12.12 ; le 0.67.0 a été éprouvé dans l'interpréteur global), hors du
dépôt, dans le dossier temporaire.

**Un défaut de ma propre main, relevé par la validation finale** : la première version du test de A5 perdait des
enregistrements sous charge (écritures concurrentes dans un fichier unique, non atomiques sous Windows) et a échoué
une fois sur 5 513 ; corrigée au commit `3d64d326`.

## 6. Plan d'actions, du plus simple au plus complexe

Un commit par action (C3). Un test ajouté pour un correctif doit **échouer sur le code d'avant** (chacun l'a fait, vu
rouge avant la correction). Les commits sont sur `claude/ecstatic-newton-3grmls` ; la publication est consignée dans « Suites du 2026-10-18 ».

### N1 — immédiat : quelques lignes, sans décision scientifique

| # | action | constat | état |
|---|---|---|---|
| A1 | `ColorWorker` : retirer `run_context=` de l'appel `success(...)` + test de bout en bout | C01 | **fait** `f32734a9` |
| A2 | `open_file_explorer` : un seul `import subprocess` en tête de module + test | C08 | **fait** `8610e18d` |
| A3 | Traduire les 4 commentaires français de `certus_strat_stack_progress_widget.py` (arbre syntaxique identique) | C11 | **fait** `f7edd4a6` |
| A4 | `git config --local core.longpaths true` (réglage local, pas un commit) | C05 | **fait** : `git status` nu rend 24 entrées, 0 avertissement |

### N2 — petit, avec test

| # | action | constat | état |
|---|---|---|---|
| A5 | `tests/conftest.py` : un répertoire de préférences par worker xdist + test (3 workers, 3 répertoires) | C02 | **fait** `f494b9e5` |
| A6 | `scripts/preflight.py` : `git -c core.longpaths=true` (63 → 25 mesuré réglage retiré) ; la phrase « 62 » d'`ETAT.md` reste à corriger par 👤 | C05 | **fait** `e1acab83` (hors la phrase d'`ETAT.md`) |
| A7 | `restore_rate_evidence.py` : repli sur l'archive voisine du clone + message clair ; la commande du README rend `EVIDENCE=GO` | C04 | **fait** `36758165` |
| A8 | Audit UX : étage `ui` à nombre de workers borné | C03 | **mesuré, pas de code** : à 6 workers, `ui` rend 1 324 réussis, 12 ignorés, 2 xfail, **0 échec, 0 erreur** en 4 min 49 (à 16 workers : 2 échecs + 12 erreurs en 5 min 43). Consigne à formaliser par A21 ; 8 à 12 workers non essayés |
| A19 | `lambda_connect_audit` lit `certus/` et `certus_physics/` ; plafond de la CI à 44 ; test qui le rend serré | C19 | **fait** `3a2b443f` |

### N3 — décisions de 👤 (changent un comportement ou touchent des fichiers gardés)

| # | action | constat |
|---|---|---|
| A20 | **Cache Numba (C18) : FAIT sur ordre de 👤.** (b) `cache=False` sur `calc_spectrum_front`, `calc_spectrum_full` et `compute_batch_rmse` (parade m1, vérifiée sur le cas minimal puis sur le rejeu des vrais appelants) ; (c) un test `xfail` strict sur Numba seul, un balayage des sources et un rejeu du défaut ; C1 tenu à froid contre à froid (9 092 tableaux au bit), avec un corpus `appelants` ajouté à `c1_diff`. (a) vider les caches n'est plus nécessaire pour ces fonctions. **Reste** : (d) dire aux mainteneurs de Numba (le cas de l'annexe suffit) ; rejouer les 4 appelants eux-mêmes parallèles du projet, que la variante minimale donne non exposés ; changer de version de Numba ne sert à rien (testé 0.65.1 à 0.68.0) | C18 |
| A9 | `get_nk_from_spline` : lever `ValueError` sur un nœud non fini, comme le chemin sans cache | C06 |
| A10 | Valider épaisseur ≥ 0 aux entrées TMM (tolérance pour de minuscules négatifs numériques) | C07 |
| A11 | Déclarer `pytest-benchmark` et `pytest-xdist` dans `dev` (`pyproject.toml`, `uv.lock`, `requirements.lock`, fichiers gardés) ; ajouter les trois contrôles documentaires à `lint.yml` | C10 |
| A12 | Choisir les octets de référence des 19 rapports CRLF/LF, puis `git add` ou restaurer. **Fait tel que trouvé (CRLF), `178bdd36`** : identiques aux CR près, aucune empreinte citée ne tranche ; `git revert` restaure le LF | C09 |
| A13 | Déplacer `UXargon.md` et `designargon.md` hors de la racine ; décider du sort de `studies/bonne_mere` **avant tout push** (36 fichiers, un PDF et un DOCX, déjà commités par l'autre session). **Audits laissés à la racine, commités tels quels (`10914d78`)** : leurs 299 liens relatifs sont écrits depuis la racine et `documentation_checks.json` y épingle les empreintes d'un état antérieur (elles ne correspondent déjà plus). `studies/bonne_mere` : la publication a été ordonnée par 👤 le 2026-10-18 | C14, C15 |
| A14 | Seconde copie de l'archive de 8,2 Go (disque externe ou stockage distant) | C04 |
| A21 | Formaliser la validation parallèle (unit 16 workers `loadfile`, ui à nombre borné, performance en série, contrôles documentaires d'abord) dans un script ou dans CLAUDE.md §2. **Fait en script : `scripts/validate_parallel.py`, `f349576e`** (22 tests) ; sa première version a fait échouer `test_the_whitelist_carries_no_fossil_entry` (le nom nu `replay` démasquait `EventBus.replay`), corrigé en `rerun` ; CLAUDE.md §2 n'est pas modifié | C03 |

### N4 — chantiers

| # | action | constat |
|---|---|---|
| A15 | D107 : corriger l'évaluation des candidats d'élagage (session dédiée déjà prévue, attend 👤) | C12 |
| A16 | Aucun test n'exécute `run()` d'un worker de bout en bout (C01 en est la preuve) : mesurer la couverture des workers et en tester les chemins de résultat | C01 |
| A17 | `dk5 = 0.0` explicite dans le noyau, avec `scripts\c1_diff.py HEAD` | C13 |
| A18 | Réduire `Any` ; resserrer le garde-fou « français » (accents dans les commentaires). **Garde-fou fait, `bc09c35f`** (3 tests ; l'arbre ne compte aucune lettre accentuée dans sa prose) ; `Any` non traité | C17, C11 |
| A22 | Convertir les 44 `connect(lambda)` en slots nommés ou `functools.partial` (D11), puis ramener le plafond de la CI à 0 | C19 |

### Suites du 2026-10-18 : ménage et validation

- **Ménage de `reports/`** (ordre de 👤) : 215 entrées datées d'avant le 2026-10-04 et citées par rien sont retirées (338 fichiers, 32 Mo) ; la règle et
  la restauration sont dans le message du commit « chore(reports): remove 215 stale entries » ; les caches de scripts restent. Quatre sorties brutes du 99c
  (80 Mo) sont ignorées par chemin exact, non commitées.
- **Ménage des .md** : `docs/ETAT.md` 168 → 94 Ko (section 0 : 891 → 248 lignes), `docs/STRAT_Rate_suite_chantier.md` 81 → 24 Ko ; l'ancienne version reste
  dans `git show 9fc49269:<fichier>`. `CLAUDE.md` n'est pas touché.
- **Taille du dossier** : 980 Mo mesurés par `du -sb .` (limite de 1 Go), après le retrait de 12 Mo de fichiers `tmp_obj_*` orphelins de `.git` ;
  `.claude/worktrees/` pèse 381 Mo et porte du travail non commité d'autres sessions (non touché).
- **Validation de l'arbre final** par `scripts/validate_parallel.py` : voir `docs/ETAT.md` §0, « Dernière validation complète ».
- **Publication** : ordonnée par 👤 le 2026-10-18 (« push et commit tout ») ; `git status -sb` donne l'état du distant.

## Annexe — cas minimal du défaut de cache de Numba (C18)

Aucune dépendance au projet. `NUMBA_CACHE_DIR` désigne un dossier vide, et les trois commandes sont trois
processus distincts.

```python
# numba_cache_repro.py
import sys

import numpy as np
from numba import njit, prange


@njit(cache=True, parallel=True)
def callee(x):
    out = np.empty_like(x)
    for i in prange(x.size):
        out[i] = x[i] * 2.0
    return out


@njit(cache=True)
def caller(x):
    return callee(x).sum()


x = np.arange(10.0)
print(callee(x).sum() if sys.argv[1] == "callee" else caller(x))
```

| processus | exécution du script, avec l'argument | ce qui se passe |
|---|---|---|
| P1 | `callee` | compile et écrit le cache de `callee` ; imprime 90.0 |
| P2 | `caller` | relit `callee` du disque, compile et écrit `caller` ; imprime 90.0 |
| P3 | `caller` (de nouveau) | relit `caller` du disque : **Segmentation fault, code 139** |

Mesuré le 2026-10-18, Windows 11 x64 : P3 plante pour Numba 0.65.1 (llvmlite 0.47.0, NumPy 2.4.6), 0.66.0
(0.48.0, 2.4.6), 0.67.0 (0.49.0, 2.5.3) et 0.68.0 (0.50.0, 2.5.4) sous Python 3.14.8, et pour 0.68.0 sous
Python 3.12.12 ; avec `NUMBA_THREADING_LAYER=omp` comme avec `workqueue`. P3 réussit si `caller` est déclaré
`cache=False` (m1), ou si `callee` est déclaré `cache=False` (m2). Dans les deux cas P1 et P2 réussissent
aussi, comme si `caller` est lui-même `parallel=True` et appelle `callee` dans une boucle `prange`. Si un seul
processus compile `callee` et `caller` sur un cache vide (rien n'est relu du disque), les
processus suivants relisent les deux sans plantage : seul l'ordre « appelé relu, appelant compilé et sauvegardé »
produit l'entrée défectueuse.
