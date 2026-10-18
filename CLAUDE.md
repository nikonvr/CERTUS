# CERTUS — règles de travail

Suite scientifique de **couches minces optiques** (PyQt6 + NumPy/SciPy/Numba) : détermination
d'indice, design d'empilements, stratégie de dépôt. Le code calcule de la **physique réelle**
servant à fabriquer de vrais filtres : une erreur silencieuse ne plante pas, elle produit un
**résultat faux qui a l'air juste**, et quelqu'un fabrique une pièce avec.

**Trois documents vivants :** les règles qui annulent un travail, ici ; la référence, qu'on lit en touchant le sujet (pièges d'exécution,
vocabulaire, tenue de la documentation, revue d'un autre agent), dans [`docs/REGLES_reference.md`](docs/REGLES_reference.md) ; l'état, les décisions et les défauts
dans [`docs/ETAT.md`](docs/ETAT.md) (lire sa section 0 avant de travailler et la tenir à jour). Les sections gardent le même numéro des deux côtés.
Les rapports de `reports/` sont des mesures datées ; Git garde l'historique des corrections. Les « CLAUDE.md §N » cités par le code viennent de
versions successives de ce fichier : chercher la règle par son sujet.

Consignes de sobriété de lecture, valables pour toute IA : @AGENTS.md

## 1. Démarrage — avant de toucher à quoi que ce soit

```bat
python scripts\preflight.py
```

Elle doit finir par `PREFLIGHT=GO` : `import certus` résout **dans l'arbre où tu édites**, et
l'interpréteur importe sans erreur les dépendances. Aucun chemin d'interpréteur ni de racine
n'est écrit en dur, délibérément : ils se périmaient à chaque déménagement.

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
signale souvent un état partagé. Un nouveau module typé dans `domain`,
`physics` ou `core` suit le registre d'annotations `tests/architecture_debt.json`.

Après modification du gel ou d'un point d'entrée que STRAT importe :
`powershell tools\build_frozen.ps1` et
`python tools\release_checks.py --check-frozen --check-frozen-run`.
Le gel produit `dist/` et `build/` : les retirer ensuite, sans toucher
aux résultats scientifiques de `reports/`.

## 3. Les onze interdits — aucune exception

1. **Jamais `ruff check --fix`** : beaucoup d'imports « inutilisés » sont des ré-exports volontaires.
2. **Jamais agrandir `extend-ignore`** dans `pyproject.toml` ; un cliquet le surveille.
3. **Jamais supprimer `reports/`** : résultats scientifiques versionnés de 👤.
4. **`example/example_strat/JSON-strat-example.json` ne se modifie que pour DURCIR.** Pour
   essayer autre chose, injecter après coup (`scripts\probe_anchor_noise_pipeline.py`).
5. **Jamais « corriger » `except A, B:`** : syntaxe PEP 758 de Python 3.14, voulue.
6. **Jamais inverser `n̂ = n − ik`** (k ≥ 0) : l'inverse crée de l'énergie (`R + T > 1`).
7. **Jamais réimplémenter une formule TMM** : la source unique pour R et T est
   `certus/physics/certus_opt_tmm.py::compute_RT_from_matrix`. Garde-fou : le cliquet
   `tests/oracle/test_tmm_formula_has_one_source.py`.
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

- **C1** s'éprouve au bit, pas par le `RESULT` du banc : **une recompilation décale les derniers
  chiffres**. **`python scripts\c1_diff.py HEAD`** compare l'arbre de travail à un commit (corpus fixe,
  interpréteurs neufs, caches Numba vierges) ; à lancer avant de committer tout changement de noyau. Il ne
  prouve que ce que son corpus appelle. Compare **froid à froid** : un noyau relu du cache n'a pas toujours
  les bits du noyau compilé à l'instant (`fastmath`). **Couper un noyau `fastmath` déplace ses derniers
  bits** ; `inline="always"` sur le morceau extrait, boucles fusionnées gardées fusionnées, les préserve. Un
  corpus se valide contre lui-même : `python scripts\c1_diff.py X --tete X --sans-cache` doit rendre 0.
- **C2** — croissance et notation voient **la même réalisation** de chaque perturbation :
  tout tirage est une fonction pure de (graine, tirage, index physique), **jamais** de la
  stratégie (ni λ, ni découpage en blocs, ni épaisseur obtenue). Générateur :
  `certus/physics/certus_strat_math.py::_seeded_noise_sample`.
- **C3** — une chose à la fois, un commit chacune.
- Un test ajouté pour un correctif **doit échouer sur le code d'avant** — sinon il ne prouve rien.

## 6. Pièges d'exécution

→ [`docs/REGLES_reference.md`](docs/REGLES_reference.md) §6 — à lire en touchant : le DTO `params`, le cache Numba (`numba_cache_key`), les caches de classe et la fixture `qapp` des tests, les exports (`atomic_open`) et les `except` larges, le thème Qt (jamais un hexadécimal), le premier calcul qui compile Numba.

## 7. Conventions physiques

- Convention de Macleod `n̂ = n − ik`, k ≥ 0, partout.
- `calculate_transmission_single` inclut **délibérément** la face arrière
  (`DO NOT REMOVE THE BACKSIDE TERM`) : il diffère légitimement d'un TMM nu.
- `tests/oracle/tmm_reference.py` est une référence TMM **indépendante** (Macleod, chap. 2,
  matrices 2×2 explicites), sans une ligne partagée avec `certus.physics`. Sers-t'en.
- Un marqueur `LOCKED` n'est pas une preuve.
- 🔴 **QWOT ≠ point tournant.** Le QWOT est l'épaisseur optique d'**une couche**
  (`m = 4nd/λ`) ; le point tournant est l'instant où l'admittance du **système entier**
  devient réelle, `tan 2δ = R/Q`. Leur période commune vaut un quart d'onde à λ_mon, mais le
  **départ** est décalé de `½·arctan(R/Q)`, fixé par l'empilement du dessous. Les deux ne
  coïncident que sur la couche 1 d'un substrat nu, ou sur un empilement tout en QWOT à λ_mon.
  Compte les points tournants par la forme fermée (`scripts\probe_turning_points.py`), jamais
  par l'épaisseur.

## 8. Architecture — frontières à respecter

- `certus.core`, `certus.physics`, `certus.domain` n'importent **jamais** PyQt6 ni `certus.ui`.
- `certus.ui` et `CERTUS_HUB.py` ne contiennent **aucun** algorithme de calcul.
- Des inversions de couches existent déjà (`utils → ui`, `core → workers`, cycle
  `physics ↔ core`) : **n'en crée aucune nouvelle** ; si tu en as besoin, le symbole doit
  descendre dans `domain/` ou `core/`.
- Seul `certus/domain/` a un `__init__.py` (paquets PEP 420) : le projet s'utilise en source.
- Le gel (`certus_hub.spec`, point d'entrée `tools/frozen_entry.py`) et les points d'entrée de la racine : [`docs/REGLES_reference.md`](docs/REGLES_reference.md) §8.

## 9. Vocabulaire

→ [`docs/REGLES_reference.md`](docs/REGLES_reference.md) §9 — juge de paix, λ de contrôle, bloc, POEM, plantage, rendement, Phase A et B, SEEL. À retenir : le SEEL (en nm) est **la** grandeur qu'on rapporte, jamais le RMSE seul.

## 10. Tenir la documentation

→ [`docs/REGLES_reference.md`](docs/REGLES_reference.md) §10 — à lire avant de toucher un `.md` ou une page de `pages/` : un fait, un seul endroit ; une fonction, jamais un numéro de ligne ; pas de récit dans un document vivant ; les pages sont des rapports scientifiques en anglais ; la vitrine `pages/CERTUS_STRAT.html` a un régime strict.

## 11. Quand s'arrêter et demander

Une instruction ambiguë · un test dont tu ne sais pas s'il a tort · une mesure qui s'écarte
nettement de l'annoncé · la tentation de violer un interdit · plus de trois fichiers pour une
seule action · **un résultat meilleur que prévu** — le plus souvent, on mesure la mauvaise chose.
S'arrêter n'est jamais un échec ; inventer, si.

## 12. Vérifier le travail d'un autre agent

→ [`docs/REGLES_reference.md`](docs/REGLES_reference.md) §12 — à lire pour relire le travail d'un autre agent : un rapport est une déclaration, pas une preuve ; trois questions, cinq contrôles. Le repère d'origine est l'étiquette `depart-gemini` : ne la déplace pas.
