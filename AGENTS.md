# AGENTS.md — point d'entrée pour tout agent de code

Ce fichier est un **panneau indicateur**, pas de la documentation. Il existe
parce que chaque outil charge automatiquement un fichier différent : Claude Code
lit `CLAUDE.md`, d'autres cherchent `AGENTS.md`. Le contenu, lui, ne vit qu'à un
seul endroit — ici on ne fait qu'y renvoyer, pour qu'il n'y ait jamais deux
versions divergentes.

## À lire, dans cet ordre

1. **`CLAUDE.md`** — contexte du projet : conventions physiques à ne pas casser
   (Macleod `n̂ = n − ik`), architecture et frontières entre couches, problèmes
   ouverts, pièges connus. **Valable quel que soit l'outil**, malgré son nom.
2. **`docs/REPRISE_PERF.md`** — pour toute question de performance : démarrage
   rapide, référence mesurée de chaque module, ce qui est fait, ce qui reste,
   profils bruts, et les tests déjà rouges qu'il ne faut pas chasser.
3. **`docs/REPRISE_TESTS_ISOLATION.md`** — fuites d'état entre tests : pourquoi un test
   peut passer seul et échouer en sélection large, la cause racine déjà corrigée, et ce
   qui reste à auditer.
4. **`docs/PLAN_AMELIORATION.md`** — chantiers d'amélioration ordonnés.

## Les quatre choses à savoir avant de toucher au code

- **Python ≥ 3.14.5 obligatoire** (PEP 758 : `except A, B:` sans parenthèses).
  Le venv est `.venv\Scripts\python.exe`.
- **Avant toute modification de calcul optique** :
  `.venv\Scripts\python.exe -m pytest tests\oracle\ -q --no-cov` (552 tests, 8 s).
  `tests/oracle/tmm_reference.py` est une référence TMM indépendante ; elle a déjà
  démasqué deux bugs de signe invisibles aux autres tests.
- **Pour mesurer, ne pas utiliser `tests/headless/`** : `test_design.py` et
  `test_strat.py` remplacent le calcul par un mock. Le banc est
  `scripts/bench_examples.py`, qui pilote les vrais exemples de `example/`.
- 🔴 **`.git/hooks/post-commit` pousse chaque commit vers un dépôt PUBLIC.**
  Actuellement renommé `post-commit.disabled`. `git commit --no-verify` ne le
  neutralise pas. Vérifier son état avant tout commit qu'on ne veut pas publier.

## Deux répertoires à ne jamais nettoyer

- **`reports/`** — 87 classeurs Excel de déterminations d'indice. Ce sont les
  résultats scientifiques de l'utilisateur, gitignorés donc non récupérables.
- **`example/`** — les jeux de données réels sur lesquels tout est mesuré.
