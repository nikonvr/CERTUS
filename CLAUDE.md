# CERTUS — règles de travail

Suite scientifique de **couches minces optiques** (PyQt6 + NumPy/SciPy/Numba) : détermination
d'indice, design d'empilements, stratégie de dépôt. Le code calcule de la **physique réelle**
servant à fabriquer de vrais filtres : une erreur silencieuse ne plante pas, elle produit un
**résultat faux qui a l'air juste**, et quelqu'un fabrique une pièce avec.

**Deux documents vivants :** les règles ici ; l'état, les décisions et les défauts
dans [`docs/ETAT.md`](docs/ETAT.md). Lire sa section 0 avant de travailler et
la tenir à jour. Les rapports de `reports/` sont des mesures datées ; Git garde
l'historique des corrections. Les archives supprimées se lisent avec
`git show 7b08dc8:docs/archives/NOM.md`.
Les « CLAUDE.md §N » cités par le code, les tests et les scripts viennent de versions
successives de ce fichier : leur numéro peut désigner une autre section qu'ici. Chercher
la règle par son sujet, ou dans `git log -p CLAUDE.md`.

## 1. Démarrage — avant de toucher à quoi que ce soit

```bat
python scripts\preflight.py
```

Elle doit finir par `PREFLIGHT=GO`. Elle vérifie les deux **propriétés** qui comptent :
`import certus` résout **dans l'arbre où tu édites**, et l'interpréteur porte les dépendances
(PyQt6, numpy, scipy, numba) **et les importe sans erreur** (pydantic, PyQt6, pyqtgraph, matplotlib,
pandas, openpyxl, xlsxwriter, joblib : une version incompatible lève à l'import, ETAT D78). Aucun chemin d'interpréteur ni de racine n'est écrit en dur, et
c'est délibéré : les chemins se sont périmés à chaque déménagement. En cas de doute,
`python -c "import sys; print(sys.executable)"`.

🔴 **Le dépôt est PUBLIC** (`github.com/nikonvr/CERTUS`). Rien qui porte un secret (clé, mot de
passe, jeton), la donnée personnelle d'un **autre** que 👤 ou l'œuvre d'un tiers n'entre dans
l'index — métadonnées des classeurs Excel comprises. Les données de 👤 lui-même sont son choix :
il assume de tout publier. Committer ne publie **pas** par défaut : le hook
`.githooks/post-commit` ne s'arme que par `git config core.hooksPath .githooks`, réglage local
jamais hérité. Vérifie avec `git config --get core.hooksPath` et `git status -sb`, ne le
suppose pas. **Pousser publie : seulement sur ordre de 👤.**

## 2. Valider — seul critère : `0 failed`

```bat
python -m ruff check .
python -m pytest tests/oracle/ -q --no-cov
python -m pytest tests/unit/ -q --no-cov
python -m pytest tests/ui/ -q --no-cov
python -m pytest tests/ -q --no-cov --ignore=tests/oracle --ignore=tests/unit --ignore=tests/ui
python scripts\coherence_md.py
python scripts\check_claude_md.py
python scripts\check_docs.py
```

Pour itérer : `python -m pytest tests/unit/ -m "not slow" -q --no-cov`.
La liste des tests lents est dans `tests/slow_tests.json`. La validation finale
reste la suite entière. Si un test est rouge avant toute modification, arrête-toi
et signale-le. Pour un calcul optique, oracle avant et après ; pour un noyau,
`python scripts\c1_diff.py HEAD` avant commit (C1, §5).

Un échec au premier run dans un arbre neuf peut venir du cache Numba : relancer
une fois. Un échec persistant est réel. Un test Qt qui meurt sans traceback
peut signaler un worker encore actif ; relancer avec
`QT_FORCE_STDERR_LOGGING=1` et `-s`. Un test isolé vert mais rouge en suite
signale souvent un état partagé.

Mesures et cliquets : `python scripts\metrics.py` (architecture, lint, UI) ;
`scripts/measure_kernel_coverage.py`, `scripts/check_coverage_floors.py`,
`tests/architecture_debt.json`, `scripts/mutation_pilot.py`. Le calcul
doit rester importable sans Qt. Un nouveau module typé dans `domain`,
`physics` ou `core` doit suivre le registre d'annotations
`tests/architecture_debt.json`. `mypy` est lancé en CI sans bloquer.

Après modification du gel ou d'un point d'entrée que STRAT importe :
`powershell tools\build_frozen.ps1` et
`python tools\release_checks.py --check-frozen --check-frozen-run`.
Le gel produit `dist/` et `build/` : les retirer ensuite, sans toucher
aux résultats scientifiques de `reports/`.

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

## 6. Pièges d'exécution

- `params` peut être un DTO Pydantic : `get` et `[]` marchent,
  `setdefault` non. Un import de paquet exécute `__init__.py` ;
  depuis `certus/physics`, importer `certus_physics.X` peut créer un cycle.
- **Numba** met en cache le code machine de l'appelant, y compris un appelé
  d'un autre fichier et les tableaux de module. `numba_cache_key` dans
  `certus/core/certus_core.py` clé le cache par les sources ; les modules
  qui donnent une constante ou une façade aux noyaux doivent mentionner
  numba dans leur texte. Garde :
  `tests/unit/test_the_cache_key_covers_what_the_kernels_read.py`.
  Compare toujours C1 froid contre froid.
- Les tests partagent des caches de classe : les restaurer par fixture.
  Un test Qt prend la fixture `qapp`, jamais une `QApplication` locale.
  `tests/headless/test_design.py` et `test_strat.py` simulent le calcul :
  pour une mesure réelle, utiliser `scripts/bench_examples.py`.
- La Phase A se lit dans `reports/STRAT_observability_*.json`.
  Dans INDEX SPLINE, `d_lo`/`d_hi` désignent nominale/tolérance au widget,
  mais des bornes dans `SplineOptConfig` : vérifier le dialogue Smart Init.
- Un export passe par `atomic_open` (`certus/utils/certus_atomic_io.py`).
  Un `except` large journalise l'exception ou se restreint aux erreurs
  attendues ; les tests `test_exports_are_written_atomically.py` et
  `test_no_broad_exception_is_swallowed_in_silence.py` gardent ces règles.
- **Qt/thème** : une feuille locale de `create_styled_button` prime sur
  la feuille de l'application. Utiliser `CertusTheme.label_on` pour l'encre
  d'un bouton plein et les jetons `CertusTheme` dans les f-strings des
  feuilles ; `refresh_widget_sheets()` les actualise au changement de
  thème. Pour une transparence, `CertusTheme.tint(couleur, 0.18)`,
  jamais huit chiffres hexadécimaux ou une concaténation. Vérifier les
  pixels, pas seulement la feuille déclarée (`scripts/audit_ux_certus.py`).
- Le premier calcul compile Numba : chauffer avant un chronométrage.
  Ne pas citer dans le code le motif littéral qu'un garde-fou cherche
  (couleur, règle QSS), au risque de déclencher le garde-fou lui-même.

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

- **Un fait, un seul endroit** : état dans `docs/ETAT.md`, règle ici.
- **Cite une fonction, jamais un numéro de ligne** : les lignes bougent.
- Pas de récit dans les documents vivants (« cette ligne disait… ») : `git log` le garde.
- Contrôles : `python scripts\coherence_md.py` (un fait = une valeur dans tous les `.md`, archives
  exclues), `python scripts\check_claude_md.py`, `python scripts\check_docs.py`. « 0 point à
  instruire » ne veut pas dire « tout est cohérent » : ils ne lisent pas les phrases.
- `pages/*.html` sont des rapports scientifiques **en anglais**, fidèles à ce que le code fait, sans
  affirmation non étayée : chaque page doit répondre « oui » à *décrit-elle exactement ce que fait le
  code, sans enjolivement ?* Ordre de relecture : METAL, STRAT, INDEX et INDEX SPLINE, RE et DESIGN, le reste.
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
