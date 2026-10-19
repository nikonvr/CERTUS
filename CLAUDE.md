# CERTUS — règles de travail

Suite de **couches minces optiques** (PyQt6, NumPy/SciPy, Numba) : indice, design, stratégie de dépôt. Le code calcule
de la **physique réelle** qui sert à fabriquer des filtres : une erreur silencieuse ne plante pas, elle donne un
**résultat faux qui a l'air juste**, et quelqu'un fabrique une pièce avec.

**Trois documents vivants**, mêmes numéros de section : les règles qui annulent un travail, ici ; la référence, lue en
touchant le sujet, [`docs/REGLES_reference.md`](docs/REGLES_reference.md) ; l'état, [`docs/ETAT.md`](docs/ETAT.md) (lire
sa section 0 avant de travailler et la tenir à jour). `reports/` : mesures datées. Un « CLAUDE.md §N » cité par le code
peut venir d'une ancienne version : chercher la règle par son sujet.

Sobriété de lecture, pour toute IA : @AGENTS.md

## 1. Démarrage

`python scripts\preflight.py` doit finir par `PREFLIGHT=GO` : `import certus` résout **dans l'arbre où tu édites**.

🔴 **Le dépôt est PUBLIC** (`github.com/nikonvr/CERTUS`) : ni secret (clé, mot de passe, jeton), ni donnée personnelle
d'un **autre** que 👤, ni œuvre d'un tiers dans l'index, métadonnées des classeurs Excel comprises. **Pousser publie :
seulement sur ordre de 👤.** Committer ne publie pas si `git config --get core.hooksPath` est vide (référence §1).

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

Itérer : `-m "not slow"` (liste dans `tests/slow_tests.json`) ; la validation finale reste la suite entière. Un test
rouge avant toute modification : arrête-toi et signale-le. Calcul optique : oracle avant et après ; noyau :
`python scripts\c1_diff.py HEAD` avant commit. Échecs ambigus, annotations, gel : référence §2.

## 3. Les onze interdits — aucune exception

1. **Jamais `ruff check --fix`** : beaucoup d'imports « inutilisés » sont des ré-exports volontaires.
2. **Jamais agrandir `extend-ignore`** dans `pyproject.toml` ; un cliquet le surveille.
3. **Jamais supprimer `reports/`** : résultats scientifiques versionnés de 👤.
4. **`example/example_strat/JSON-strat-example.json` ne se modifie que pour DURCIR** ; pour essayer autre chose,
   injecter après coup (`scripts\probe_anchor_noise_pipeline.py`).
5. **Jamais « corriger » `except A, B:`** : syntaxe PEP 758 de Python 3.14, voulue.
6. **Jamais inverser `n̂ = n − ik`** (k ≥ 0) : l'inverse crée de l'énergie (`R + T > 1`).
7. **Jamais réimplémenter une formule TMM** : source unique `certus/physics/certus_opt_tmm.py::compute_RT_from_matrix`
   (cliquet `tests/oracle/test_tmm_formula_has_one_source.py`).
8. **Jamais découper `certus/core/_certus_physics_impl.py`** (`DO NOT SPLIT` : visibilité mutuelle des noyaux compilés).
9. **Jamais affirmer un résultat non mesuré** : tu colles la sortie de la commande, ou tu écris « je n'ai pas mesuré ».
10. **Jamais de rapport de session à la racine** ; une sortie de campagne va dans `reports/`.
11. **Jamais de français dans les commentaires, docstrings et journaux de `certus/`**, sauf les mots utilisés comme
    données (`certus_re_helpers.py`), les clés JSON persistées (`seuil1`/`seuil2`), les formats de journal que des
    scripts analysent (compteurs ELITE) et les libellés vus par l'utilisateur
    (garde-fou `tests/unit/test_certus_is_written_in_english.py`).

## 4. Les erreurs qui annulent un travail

| erreur | conséquence |
|---|---|
| modifier un arbre et en mesurer un autre | tout est faux, sans message ; `.claude/worktrees/` sont des copies du dépôt dans le dépôt : balaye les fichiers **suivis** (`git ls-files`) |
| conclure avant la mesure | annulé à la relecture |
| changer deux choses à la fois | personne ne sait laquelle a agi (**C3**) |
| croire un chiffre de bruit qui ne varie pas avec le bruit | artefact : divise le bruit par 100 et remesure |
| lancer une mesure pendant qu'autre chose tourne | le banc rend `RESULT=None`, qui ressemble à un résultat ; cherche `WAIT_TIMEOUT=` |
| vérifier une non-régression « aux tests près » | les tests ne prouvent pas l'identité numérique : il faut le **bit** |
| un paramètre visible qui n'atteint pas le calcul | une fausse explication : **vérifie qu'il arrive avant de lui attribuer un effet** |

## 5. La règle d'or et les trois contraintes

> **Tout nouveau paramètre est inactif par défaut, et le chemin inactif rend exactement les mêmes bits qu'avant.** (C1)

- **C1** s'éprouve au bit, pas par le `RESULT` du banc : `python scripts\c1_diff.py HEAD` avant de committer un
  changement de noyau, froid contre froid (mode d'emploi : référence §5).
- **C2** — croissance et notation voient **la même réalisation** de chaque perturbation : tout tirage est une fonction
  pure de (graine, tirage, index physique), **jamais** de la stratégie
  (`certus/physics/certus_strat_math.py::_seeded_noise_sample`).
- **C3** — une chose à la fois, un commit chacune.
- Un test ajouté pour un correctif **doit échouer sur le code d'avant**.

## 6. Pièges d'exécution

→ Référence §6 : DTO `params`, cache Numba (`numba_cache_key`), caches de classe et fixture `qapp`, `atomic_open` et
`except` larges, thème Qt (jamais un hexadécimal), premier calcul qui compile Numba.

## 7. Conventions physiques

- Convention de Macleod `n̂ = n − ik`, k ≥ 0, partout.
- `calculate_transmission_single` inclut **délibérément** la face arrière (`DO NOT REMOVE THE BACKSIDE TERM`).
- `tests/oracle/tmm_reference.py` est une référence TMM **indépendante** (Macleod, chap. 2), sans une ligne partagée
  avec `certus.physics` : sers-t'en. Un marqueur `LOCKED` n'est pas une preuve.
- 🔴 **QWOT ≠ point tournant** : compte les points tournants par la forme fermée (`scripts\probe_turning_points.py`),
  jamais par l'épaisseur (référence §7).

## 8. Architecture — frontières à respecter

- `certus.core`, `certus.physics`, `certus.domain` n'importent **jamais** PyQt6 ni `certus.ui`.
- `certus.ui` et `CERTUS_HUB.py` ne contiennent **aucun** algorithme de calcul.
- Les inversions existantes (`utils → ui`, `core → workers`, cycle `physics ↔ core`) : **n'en crée aucune nouvelle** ;
  le symbole doit descendre dans `domain/` ou `core/`.
- Seul `certus/domain/` a un `__init__.py` (paquets PEP 420) : le projet s'utilise en source. Gel et points d'entrée :
  référence §8.

## 9. Vocabulaire

→ Référence §9. Le SEEL (en nm) est **la** grandeur qu'on rapporte, jamais le RMSE seul.

## 10. Tenir la documentation

→ Référence §10, avant de toucher un `.md` ou une page de `pages/`. Un fait, un seul endroit ; le moins de mots possible.

## 11. Quand s'arrêter et demander

Une instruction ambiguë · un test dont tu ne sais pas s'il a tort · une mesure qui s'écarte nettement de l'annoncé · la
tentation de violer un interdit · plus de trois fichiers pour une seule action · **un résultat meilleur que prévu** — le
plus souvent, on mesure la mauvaise chose. S'arrêter n'est jamais un échec ; inventer, si.

## 12. Vérifier le travail d'un autre agent

→ Référence §12 : un rapport est une déclaration, pas une preuve. Ne déplace pas l'étiquette `depart-gemini`.
