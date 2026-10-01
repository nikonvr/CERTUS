# CERTUS — règles de travail

Suite scientifique de **couches minces optiques** (PyQt6 + NumPy/SciPy/Numba) : détermination
d'indice, design d'empilements, stratégie de dépôt. Le code calcule de la **physique réelle**
servant à fabriquer de vrais filtres : une erreur silencieuse ne plante pas, elle produit un
**résultat faux qui a l'air juste**, et quelqu'un fabrique une pièce avec.

**Deux documents, et deux seulement :** ce fichier porte les **règles** ; l'**état** du projet
(repères mesurés, décisions, défauts ouverts, chantiers) est dans [`docs/ETAT.md`](docs/ETAT.md),
dont la **section 0 est la reprise** : à lire en premier, et à tenir à jour au fil du travail.
`README.md` est la page d'accueil du dépôt public (quoi, lancer, licence) : il ne porte aucun fait qui change.
L'historique — campagnes, hypothèses réfutées, anciens plans — n'est plus dans l'arbre : **`git` le
garde**, sans autorité. Un renvoi du code, d'un test ou d'une page à un fichier de `docs/archives/`
désigne un fichier supprimé le 2026-09-30, qu'on lit par `git show 7b08dc8:docs/archives/NOM.md`.
Les numéros de section que citent le code et ces renvois désignent l'ancienne version de ce fichier
(`CLAUDE_2026-09-26.md`) ; ceux du registre des défauts, `DEFAUTS_OUVERTS.md`.

## 1. Démarrage — avant de toucher à quoi que ce soit

```bat
python scripts\preflight.py
```

Elle doit finir par `PREFLIGHT=GO`. Elle vérifie les deux **propriétés** qui comptent :
`import certus` résout **dans l'arbre où tu édites**, et l'interpréteur porte les dépendances
(PyQt6, numpy, scipy, numba). Aucun chemin d'interpréteur ni de racine n'est écrit en dur, et
c'est délibéré : les chemins se sont périmés à chaque déménagement. En cas de doute,
`python -c "import sys; print(sys.executable)"`.

🔴 **Le dépôt est PUBLIC** (`github.com/nikonvr/CERTUS`). Rien qui porte un secret (clé, mot de
passe, jeton), la donnée personnelle d'un **autre** que 👤 ou l'œuvre d'un tiers n'entre dans
l'index — métadonnées des classeurs Excel comprises. Les données de 👤 lui-même sont son choix :
il assume de tout publier. Committer ne publie **pas** par défaut : le hook
`.githooks/post-commit` ne s'arme que par `git config core.hooksPath .githooks`, réglage local
jamais hérité. Vérifie avec `git config --get core.hooksPath` et `git status -sb`, ne le
suppose pas. **Pousser publie : seulement sur ordre de 👤.**

## 2. Valider — le seul critère est `0 failed`

```bat
python -m ruff check .
python -m pytest tests/oracle/ -q --no-cov
python -m pytest tests/unit/ -q --no-cov
python -m pytest tests/ui/ -q --no-cov
python -m pytest tests/ -q --no-cov --ignore=tests/oracle --ignore=tests/unit --ignore=tests/ui
```

📏 Mesuré le 2026-09-30 (Windows 11, Ryzen 7 5700G 8 cœurs / 16 threads, 31 Go, Python 3.14.7,
cache Numba chaud) : oracle 8 s (53 s à froid) · unit 7 min 23 · ui 18 min 32 · le reste de
`tests/` 7 min 53. **Une durée sans sa machine ne vaut rien ; un compte de tests se périme au
premier test ajouté — ne recopie ni l'un ni l'autre.**

Les **indicateurs du plan** (dette de lint, cycles d'imports, tests sans assertion, contraste des boutons,
CI de HEAD…) : `python scripts\metrics.py` (1 min ; `--rapide` : 10 s, le statique seul). Un `n/a` y dit
qu'une mesure manque, jamais un zéro. La **couverture** se mesure sur toutes les suites (`pytest --cov=certus` avec `--cov-append`) et
sur les noyaux compilés à part (`NUMBA_DISABLE_JIT=1 pytest tests/oracle tests/core --cov=certus` : sans cela `physics` paraît à 20 %) ;
`python scripts\check_coverage_floors.py cov.json --noyaux cov_noyaux.json` refuse qu'un paquet passe sous son plancher.
La **dette d'architecture** (imports montants, cycles à l'exécution, fonctions de plus de 300 lignes ou de complexité
supérieure à 60, fichiers de plus de 1 500 lignes) est nommée dans `tests/architecture_debt.json` :
`tests/unit/test_the_architecture_debt_only_shrinks.py` refuse un élément nouveau ou qui grossit, et exige
qu'une dette payée, ou une mesure qui baisse, y soit corrigée dans le même commit (`python scripts\metrics.py --dette
tests\architecture_debt.json` réécrit le registre).
Les **types** : `python -m mypy` depuis la racine (réglages dans `[tool.mypy]` ; il parcourt `certus/domain`, `physics` et
`core`). mypy n'est pas une dépendance du projet : installe-le dans un environnement jetable (`pip install --only-binary=:all:
mypy`, et `--python-executable` vers le Python du projet s'il n'y est pas). Le même registre nomme les fonctions de ces trois
paquets sans annotation complète (`fonctions_non_annotees`) : une fonction nouvelle vient annotée, une fonction annotée sort du
registre dans le même commit. La CI lance mypy sans bloquer tant qu'elle ne l'a pas vu vert.
Les **tests qui gardent vraiment** : `python scripts\mutation_pilot.py certus/physics/certus_inputs.py` pose une faute à la fois
(`<` → `<=`, `raise` → `pass`, `max` → `min`, `.real` → `.imag`…) dans une copie du dépôt et compte celles que les tests voient
(mutmut 3 ne tourne pas sous Windows). Les tests tournent sans compilation (`NUMBA_DISABLE_JIT=1`) ; `--rerun mutation.json` rejoue
les survivants, `--baseline tests\mutation_baseline.json` sort 1 sur un survivant que la base n'a pas jugé équivalent. Trois modules
de physique sont joués (`certus_inputs`, `certus_substrate_absorption`, `certus_oblique_substrate`) ;
`tests/unit/test_the_mutation_baseline_describes_the_code_as_it_is.py` dit en une seconde si la base décrit encore leur code (sinon :
relancer le pilote et juger les nouveaux survivants, ne pas retoucher un chiffre).

| échec | ce que c'est |
|---|---|
| 3 tests à la **première** passe dans un arbre neuf (`test_phase2_gradient`, deux `TestIRGlobalModelStrategy`) | cache numba froid, vu après un changement de numba ou d'interpréteur, et le 2026-09-27 dans un worktree neuf (`AttributeError: module 'numba' has no attribute 'core'`). Relance une fois : s'ils passent, c'était le cache ; sinon, c'est un vrai échec |
| un test d'oracle ou d'unit qui échoue sur un code juste, juste après une mise à jour | cache Numba **de l'arbre** périmé (`certus/**/__pycache__/*.nbi` et `.nbc`) : un appelant y garde l'ancien appelé d'un autre fichier (2026-09-30 : `cost_numba_fast` ignorait la perte du substrat du nouveau noyau, 4 échecs à l'oracle). `tests/conftest.py` lit désormais le cache clé par les sources, la session de tests n'y touche plus ; un script qui importe les noyaux sans point d'entrée, si (ETAT D49). Supprime ces fichiers |
| un test d'interface qui meurt sans message | arrêt natif `0xC0000005` du worker Qt, mesuré 2 fois sur 120 lancements ; le harnais réessaie une fois |
| un processus qui meurt sans message Qt | sous Windows, Qt écrit dans `OutputDebugString` : relance avec `QT_FORCE_STDERR_LOGGING=1`, et `-s` pour que pytest ne capture pas (par exemple « QThread: Destroyed while thread … is still running », D23, ou « QObject: shared QObject was deleted directly ») |
| un test qui passe seul et échoue en suite | fuite d'état entre tests (caches de classe, `sys.modules`) : cherche le test précédent |

Si un test est rouge **avant** que tu aies touché quoi que ce soit : arrête-toi et signale.
Et `tests/oracle/` avant et après toute modification d'un calcul optique.

Le **gel** ne se valide pas par ces tests : la suite entière, verte, n'a pas vu qu'un script embarqué qui en
importait un autre, non embarqué, empêchait STRAT de démarrer dans l'exécutable (2026-09-30). Après
avoir touché `certus_hub.spec`, `tools/frozen_entry.py`, `CERTUS_HUB.py` ou un script de `scripts/`
que STRAT importe au démarrage : `pip install pyinstaller` (extra `freeze`), puis
`powershell tools\build_frozen.ps1` et `python tools\release_checks.py --check-frozen
--check-frozen-run`. Le build écrit `dist/` et `build/` dans le dépôt (≈ 450 Mo, ignorés par git,
mais **synchronisés par Drive**) : supprime-les ensuite.

## 3. Les onze interdits — aucune exception

1. **Jamais `ruff check --fix`** : beaucoup d'imports « inutilisés » sont des ré-exports volontaires.
2. **Jamais agrandir `extend-ignore`** dans `pyproject.toml` ; un cliquet le surveille.
3. **Jamais supprimer `reports/`** : résultats scientifiques versionnés de 👤.
4. **`example/example_strat/JSON-strat-example.json` ne se modifie que pour DURCIR** ; il a
   dérivé quatre fois vers le permissif. Pour essayer autre chose, injecter après coup
   (`scripts\probe_anchor_noise_pipeline.py`).
5. **Jamais « corriger » `except A, B:`** : syntaxe PEP 758 de Python 3.14, voulue.
6. **Jamais inverser `n̂ = n − ik`** (k ≥ 0) : l'inverse crée de l'énergie (`R + T > 1`).
7. **Jamais réimplémenter une formule TMM** : la source unique pour R et T est
   `certus/physics/certus_opt_tmm.py::compute_RT_from_matrix` (deux réimplémentations fausses,
   de 46 et 82 points de réflectance). Garde-fou : le cliquet `tests/oracle/test_tmm_formula_has_one_source.py`
   nomme les copies d'aujourd'hui ; aucune ne peut entrer.
8. **Jamais découper `certus/core/_certus_physics_impl.py`** (`DO NOT SPLIT` : visibilité
   mutuelle des noyaux compilés).
9. **Jamais affirmer un résultat non mesuré.** Soit tu colles la sortie de la commande, soit
   tu écris « je n'ai pas mesuré ». Il n'y a pas de troisième option.
10. **Jamais de rapport de session à la racine** ; une sortie de campagne va dans `reports/`.
11. **Jamais de français dans les commentaires, docstrings et journaux de `certus/`.** Restent
    en français, délibérément : les mots utilisés comme **données** (`certus_re_helpers.py`),
    les **clés JSON persistées** (`seuil1`/`seuil2`), les formats de journal que des scripts
    analysent (la ligne de compteurs ELITE) et les **libellés vus par l'utilisateur**.
    Garde-fou : `tests/unit/test_certus_is_written_in_english.py`.

## 4. Les erreurs qui annulent un travail

| erreur | conséquence |
|---|---|
| modifier un arbre et en mesurer un autre | aucun message, tout est faux. Les worktrees de `.claude/worktrees/` sont des **copies du dépôt dans le dépôt** : un balayage depuis la racine les lit. Balaye les fichiers **suivis** (`git ls-files`) |
| conclure avant la mesure | annulé à la relecture |
| changer deux choses à la fois | personne ne sait laquelle a agi (contrainte **C3** : une chose, un commit) |
| croire un chiffre de bruit qui ne varie pas avec le bruit | c'est un artefact : divise le bruit par 100 et remesure |
| lancer une mesure pendant qu'autre chose tourne | le banc rend `RESULT=None`, qui ressemble à un résultat ; cherche `WAIT_TIMEOUT=` |
| vérifier une non-régression « aux tests près » | les tests ne prouvent pas l'identité numérique : il faut le **bit** |
| un paramètre visible qui n'atteint pas le calcul | pire qu'absent : il fournit une fausse explication. **Avant d'attribuer un effet à un paramètre, vérifie qu'il arrive** |

## 5. La règle d'or et les trois contraintes

> **Tout nouveau paramètre est inactif par défaut, et le chemin inactif rend exactement les
> mêmes bits qu'avant.** (C1)

- **C1** s'éprouve par une empreinte `float.hex()` du noyau, pas par le `RESULT` du banc : à
  état compilé identique le banc est déterministe, mais **une recompilation décale les
  derniers chiffres** (2,8e-11, reproductible). **`python scripts\c1_diff.py HEAD`** (50 s) compare au bit
  l'arbre de travail à un commit : corpus fixe, interpréteurs neufs, caches Numba vierges ; à lancer
  avant de committer tout changement de noyau. Il ne prouve que ce que son corpus appelle. Un noyau relu du cache
  n'a pas toujours les bits du noyau compilé à l'instant (gradients, `fastmath`, ETAT D52) : compare **froid à froid**.
  **Couper un noyau `fastmath` déplace les derniers bits selon la forme de la coupe** (mesuré : 3 à 116 résultats de
  croissance sur 1 200, jusqu'à 14 592 ulp) ; `inline="always"` sur le morceau extrait, et les boucles fusionnées gardées
  fusionnées, ont rendu les mêmes bits (`certus_strat_growth.py`, ETAT D54). Un corpus se valide en comparant un arbre à
  lui-même : `python scripts\c1_diff.py X --tete X --sans-cache` doit rendre 0 (le 2026-09-30 il a trouvé un noyau qui ne se
  retrouvait pas lui-même).
- **C2** — croissance et notation voient **la même réalisation** de chaque perturbation :
  tout tirage est une fonction pure de (graine, tirage, index physique), **jamais** de la
  stratégie (ni λ, ni découpage en blocs, ni épaisseur obtenue). Générateur :
  `certus/physics/certus_strat_math.py::_seeded_noise_sample`.
- **C3** — une chose à la fois, un commit chacune.
- Un test ajouté pour un correctif **doit échouer sur le code d'avant** — sinon il ne prouve rien.

## 6. Pièges — chacun a déjà coûté une session

- **`params` n'est pas toujours un dict** (DTO pydantic sur certains chemins) : `get` et `[]`
  marchent, **`setdefault` lève**.
- **Importer un paquet exécute son `__init__.py`** : depuis `certus/physics/`, importer
  `certus_physics.X` est circulaire ; passe par la façade, et `TYPE_CHECKING` pour une annotation.
- **Numba ne relit un appelant que si SON fichier change**, et fige les tableaux de module à la
  compilation : avec `cache=True`, une fonction qui en appelle une autre d'un **autre** fichier garde
  l'ancien appelé dans son code machine, et une donnée modifiée sans toucher au `.py` reste servie
  périmée. Les applications et la session de tests lisent un répertoire de cache clé par les sources
  qui mentionnent numba (`numba_cache_key`, `ensure_numba_cache_dir` dans `certus/core/certus_core.py`) ;
  ce qui importe les noyaux sans point d'entrée lit encore le cache de l'arbre (ETAT D49).
  **Un module qui donne une valeur (constante, appelé, façade) à un noyau doit dire numba** dans son
  texte, sinon sa modification ne bouge pas la clé : `certus/domain/constants.py` (les constantes que
  lit la physique, `TWO_PI`…) et la façade `certus_tmm_core.py` le disent, et
  `tests/unit/test_the_cache_key_covers_what_the_kernels_read.py` refuse tout autre trou.
- **Les tests partagent des caches de classe** (`SplineBasisCache._cache`…) : sauve et
  restaure-les dans une fixture `autouse`.
- **Un test ne crée jamais sa `QApplication`, il prend `qapp`** : créée dans une variable
  locale, elle meurt avec le premier test Qt du processus, et tout ce qui suit tourne sur une
  Qt détruite. Un gardien l'impose (`tests/unit/test_tests_borrow_the_session_qapplication.py`).
- **Un test qui échoue n'a pas forcément tort — mais parfois si** : cinq tests vérifiaient un
  comportement faux. Comprends d'abord, dis lequel des deux est faux, et pourquoi.
- **La Phase A ne dit rien** : lis le `reports/STRAT_observability_*.json` le plus récent.
- **INDEX SPLINE : `d_lo` / `d_hi` du widget sont la NOMINALE et la TOLÉRANCE**, alors que les
  mêmes noms portent des **bornes** dans `SplineOptConfig`. Vérifie la ligne `[d min=…, d max=…]`
  du dialogue Smart Init avant d'exploiter un run.
- **`tests/headless/test_design.py` et `test_strat.py` remplacent le calcul par un mock** : ne
  mesure rien avec. Le banc sans mock est `scripts\bench_examples.py`.
- **Un export s'écrit par `atomic_open`** (`certus/utils/certus_atomic_io.py`), jamais par
  `open(chemin, "w")` : un écrivain qui meurt au milieu (disque plein, exception, processus tué)
  laissait un fichier tronqué sur la copie de l'utilisateur. `tests/unit/test_exports_are_written_atomically.py`
  refuse tout autre `open(..., "w")` dans `certus/`.
- **Un `except` large ne se tait pas** : `except Exception: pass` fait disparaître une erreur sans
  laisser de trace. Restreins-le aux exceptions attendues, ou écris
  `logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)` (rien ne coûte à
  un niveau supérieur). `tests/unit/test_no_broad_exception_is_swallowed_in_silence.py` refuse un nouveau.
- **Un bouton de `create_styled_button` porte sa propre feuille**, qui l'emporte sur celle de l'application quelle que soit la
  spécificité : une règle d'état posée ailleurs (`:focus`) ne l'atteint pas, elle va DANS `get_button_style`. Son libellé se dérive du
  fond (`CertusTheme.label_on`), jamais d'un jeton choisi pour un thème. Pour un état de focus, Qt garde la taille calculée avant
  le focus : le test de non-déplacement la lui fait recalculer (changer le texte). `test_ux_button_label_is_painted.py` et
  `test_ux_focus_ring.py` lisent les pixels ; un test qui lit la feuille déclarée ne voit pas ce qu'on peint.
- **Une couleur de la palette écrite dans une feuille suit le thème ; une copie ne le suit pas.** `CertusTheme.SURFACE` est un
  `_Token` : une chaîne ordinaire pour tout (Qt, JSON, `==`, `str()`, `%`, `+`) SAUF pour un f-string, qui l'écrit avec son nom
  (`#ffffff/*T:SURFACE*/`, un commentaire que Qt lit comme du blanc) ; `CertusTheme.refresh_widget_sheets()`, appelé par la bascule de
  thème, réécrit toute feuille posée sur un widget d'après ces noms. Écris donc `f"color: {CertusTheme.TEXT_MAIN}"`, jamais
  `str(CertusTheme.TEXT_MAIN)`, une concaténation ou un hexadécimal. Une couleur DÉRIVÉE d'un jeton (un survol, l'encre d'un fond)
  n'est pas un jeton : le style d'un bouton plein est entre deux marqueurs que `get_button_style` pose et que le rafraîchissement
  reconstruit. `test_ux_dark_toggle_reaches_the_widgets.py` et `python scripts\audit_ux_certus.py` comptent les feuilles restées
  claires après un clic sur la bascule. **Une transparence s'écrit `CertusTheme.tint(couleur, 0.18)`** (un `rgba()` qui garde le nom du
  jeton), jamais `f"{couleur}2e"` ni `couleur + "2e"` : Qt lit huit chiffres hexadécimaux à l'envers (`#aarrggbb`), et le commentaire du
  jeton tomberait dans le nombre (`test_ux_alpha_is_written_the_way_qt_reads_it.py` cherche les deux écritures dans tout le dépôt).
- **Le premier calcul est lent** (compilation numba, +30 s) : chauffe, puis mesure.
- **N'écris pas l'artefact que tu décris** : un hexadécimal cité dans un commentaire fait
  bouger le cliquet des couleurs, une règle QSS citée dans une f-string est recrachée dans la
  feuille. **Nomme, ne cite pas.**

## 7. Conventions physiques

- Convention de Macleod `n̂ = n − ik`, k ≥ 0, partout.
- `calculate_transmission_single` inclut **délibérément** la face arrière
  (`DO NOT REMOVE THE BACKSIDE TERM`) : il diffère légitimement d'un TMM nu.
- `tests/oracle/tmm_reference.py` est une référence TMM **indépendante** (Macleod, chap. 2,
  matrices 2×2 explicites), sans une ligne partagée avec `certus.physics`. Sers-t'en.
- Un marqueur `LOCKED` n'est pas une preuve : le bug de signe monocouche en portait un.
- 🔴 **QWOT ≠ point tournant.** Le QWOT est l'épaisseur optique d'**une couche**
  (`m = 4nd/λ`) ; le point tournant est l'instant où l'admittance du **système entier**
  devient réelle, `tan 2δ = R/Q`. Leur période commune vaut un quart d'onde à λ_mon, mais le
  **départ** est décalé de `½·arctan(R/Q)`, fixé par l'empilement du dessous. Les deux ne
  coïncident que sur la couche 1 d'un substrat nu, ou sur un empilement tout en QWOT à λ_mon.
  Le comptage naïf s'est trompé d'un **facteur 59**. Compte les points tournants par la forme
  fermée (`scripts\probe_turning_points.py`), jamais par l'épaisseur.

## 8. Architecture — frontières à respecter

- `certus.core`, `certus.physics`, `certus.domain` n'importent **jamais** PyQt6 ni `certus.ui`.
- `certus.ui` et `CERTUS_HUB.py` ne contiennent **aucun** algorithme de calcul.
- Thème : toujours `apply_certus_theme()` et les jetons `CertusTheme`, jamais un hexadécimal.
- Des inversions de couches existent déjà (`utils → ui`, `core → workers`, cycle
  `physics ↔ core`) : **n'en crée aucune nouvelle** ; si tu en as besoin, le symbole doit
  descendre dans `domain/` ou `core/`.
- Seul `certus/domain/` a un `__init__.py` (paquets PEP 420) : le projet s'utilise en source.
- Le gel (`certus_hub.spec`) est **un** exécutable : `CERTUS_HUB.exe` lance le hub, et
  `CERTUS_HUB.exe --run-module NOM [fichier]` un module. Son point d'entrée est `tools/frozen_entry.py`,
  **jamais** un fichier de `certus/core/` : PyInstaller cherche d'abord dans le dossier de son script
  d'entrée, qui masquerait `certus_substrate_index.py`. Un script de `scripts/` importé au démarrage doit
  être dans les `datas` du spec, avec ce qu'il importe (`test_the_frozen_spec_bundles_the_suite` le suit).
- `certus_curve_smoother.py` et `certus_substrate_index.py`, à la racine, sont des points d'entrée
  que le hub lance ; le second recopie aussi les globales de `certus.core.certus_substrate_index`.

## 9. Vocabulaire

| terme | sens |
|---|---|
| juge de paix | le dichroïque 48 couches, `example/example_strat/JSON-strat-example.json` — un repère, pas le seul composant |
| λ de contrôle, bloc | la longueur d'onde surveillée ; un bloc = des couches consécutives à la même λ |
| POEM | arrêt à un pourcentage de l'amplitude entre les deux derniers points tournants |
| plantage, rendement | un dépôt qui ne se termine pas ; la part de ceux qui se terminent (objectif 95 %) |
| Phase A, Phase B | choix d'une λ par couche ; regroupement en blocs et test Monte-Carlo |
| SEEL | erreur d'épaisseur équivalente par couche, en nm — **la** grandeur qu'on rapporte, jamais le RMSE seul |

## 10. Tenir la documentation

- **Un fait, un seul endroit** : un état dans `docs/ETAT.md`, une règle ici. Recopier un fait,
  c'est préparer sa péremption — ce dépôt a compté 80 documents contradictoires, puis un
  fichier unique de 5 413 lignes, puis 17 000 lignes réparties.
- **Cite une FONCTION, jamais un numéro de ligne** : 38 % des renvois `fichier.py:ligne`
  vérifiables étaient périmés le 2026-09-25.
- Pas de récit dans les documents vivants (« cette ligne disait… ») : `git log` le garde.
- Contrôles : `python scripts\coherence_md.py` (un fait = une valeur dans tous les `.md`, archives
  exclues), `python scripts\check_claude_md.py`, `python scripts\check_docs.py`. « 0 point à
  instruire » ne veut pas dire « tout est cohérent » : ils ne lisent pas les phrases.
- `pages/*.html` sont des rapports scientifiques **en anglais**, fidèles à ce que le code fait, sans
  affirmation non étayée : chaque page doit répondre « oui » à *décrit-elle exactement ce que fait le
  code, sans enjolivement ?* Deux pages sont en français à ce jour (`alternative_swanepoel.html`,
  `rapport_certus_complet.html`) : les traduire, ou déclarer l'exception — pas une règle que deux fichiers
  contredisent. Ordre de relecture : METAL, STRAT, INDEX et INDEX SPLINE, RE et DESIGN, le reste.
- La vitrine `pages/CERTUS_STRAT.html` a un régime strict : tout nombre sourçable dans le code
  ou dans `reports/`, la limite montrée, la structure revérifiée (`python scripts\verifier_html.py pages\CERTUS_STRAT.html`).

## 11. Quand s'arrêter et demander

Une instruction ambiguë · un test dont tu ne sais pas s'il a tort · une mesure qui s'écarte
nettement de l'annoncé · la tentation de violer un interdit · plus de trois fichiers pour une
seule action · **un résultat meilleur que prévu** — le plus souvent, on mesure la mauvaise chose.
S'arrêter n'est jamais un échec ; inventer, si.

## 12. Vérifier le travail d'un autre agent

Un rapport est une déclaration, pas une preuve : essaie de la **casser**. Trois questions, dans
l'ordre : le diff correspond-il à la déclaration ? la mesure se reproduit-elle ? la conclusion
suit-elle de la mesure ? Puis cinq contrôles : le nouveau paramètre est-il inerte au bit ? les
tests ajoutés échouent-ils sur le code d'avant ? les grandeurs de bruit suivent-elles le bruit ?
chaque filtre rejette-t-il réellement quelque chose (**compte les rejets**) ? les conclusions
dépassent-elles les mesures ? Le repère d'origine est l'étiquette `depart-gemini` : ne la
déplace pas.
