# CERTUS — règles de travail

Suite de **couches minces optiques** (PyQt6, NumPy/SciPy, Numba) : physique réelle — une erreur silencieuse fausse les résultats sans planter.

- Règles ici ; détails par section dans [`docs/REGLES_reference.md`](docs/REGLES_reference.md) ; état dans [`docs/ETAT.md`](docs/ETAT.md) (lire §0 avant d'agir).
- Sobriété :
  - `python scripts\orient.py` : tête git, arbre, processus python actifs (une mesure parallèle rend `RESULT=None`), dernière validation et coût des docs (`--carte` ajoute les titres).
  - À la demande : `docs/CHANTIERS_RESTANTS.md`, `docs/ETAT_acquis.md`, `docs/REGLES_reference.md`.
  - Jamais en entier : `reports/`, `studies/` (cachés à ripgrep par `.rgignore`) ; chercher par id (`rg -n "RICL" docs/CHANTIERS_RESTANTS.md`) ou lire `bilan.md`/`README.md`.
  - Sortie sobre : `pytest -q --no-cov` (`-x`), jamais `--verbose` ; `git status -sb`, `git log --oneline -n 10`, `git diff --stat` avant `git diff`.
  - Lire ciblé (`offset`, `limit`) ; ne pas relire ce qu'on vient d'écrire ; préférer Read/Grep.
  - Une action, son résultat, la suivante : ni agents ni mesures en parallèle.
  - Écrire court : un fait, un seul endroit ; rapport de campagne dans `reports/`.

## 1. Démarrage

`python scripts\preflight.py` doit finir par `PREFLIGHT=GO` (`import certus` dans l'arbre édité).

🔴 **Répertoire unique obligatoire (👤 2026-11-19)** : travailler **exclusivement** dans le dépôt Drive `certus1111` (`D:\drivfl\...\CERTUS\certus1111`). **Jamais** cloner, déplacer ou travailler dans `C:\dev\` ni un autre clone hors de cet arbre.

🔴 **Dépôt PUBLIC** (`github.com/nikonvr/CERTUS`) : aucun secret, donnée tierce ni œuvre tierce (métadonnées Excel comprises). **Pousser publie : uniquement sur ordre de 👤.** Committer est local si `git config --get core.hooksPath` est vide (référence §1).

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

Itérer : `-m "not slow"` (`tests/slow_tests.json`) ou `python scripts\verify_changed.py` ; validation finale = suite entière (dont `tests/ui/`). Test déjà rouge : s'arrêter et signaler. Calcul optique : oracle avant/après + `python scripts\c1_diff.py HEAD` sur noyau (détails : référence §2).

## 3. Les onze interdits — aucune exception sans ordre de 👤

Aucune auto-exception (§11 ; pour 6, 7 et 9 : mesure obligatoire en plus).

1. **Jamais `ruff check --fix`** : des imports servent de ré-exports.
2. **Jamais agrandir `extend-ignore`** (`pyproject.toml`, surveillé par cliquet).
3. **Jamais supprimer `reports/`**.
4. **`example/example_strat/JSON-strat-example.json` ne se modifie que pour DURCIR** (sinon injecter via `scripts\probe_anchor_noise_pipeline.py`).
5. **Jamais « corriger » `except A, B:`** (PEP 758 Python 3.14+).
6. **Jamais inverser `n̂ = n − ik`** (`k >= 0` ; sinon gain `R + T > 1`).
7. **Jamais réimplémenter une formule TMM** : source unique `certus/physics/certus_opt_tmm.py::compute_RT_from_matrix` (`tests/oracle/test_tmm_formula_has_one_source.py`).
8. **Jamais découper `certus/core/_certus_physics_impl.py`** (`DO NOT SPLIT` : visibilité Numba).
9. **Jamais affirmer un résultat non mesuré** : coller la sortie réelle.
10. **Jamais de rapport à la racine** : campagnes dans `reports/`.
11. **Jamais de français dans commentaires, docstrings et journaux de `certus/`** (hors données `certus_re_helpers.py`, clés JSON persistées `seuil1`/`seuil2`, compteurs ELITE et libellés UI ; `tests/unit/test_certus_is_written_in_english.py`).

## 4. Les erreurs qui annulent un travail

| erreur | conséquence |
|---|---|
| modifier un arbre, en mesurer un autre | résultats faux ; balayer `git ls-files`, pas `.claude/worktrees/` |
| conclure avant mesure | annulé |
| changer deux choses à la fois | cause perdue (**C3**) |
| bruit constant quand le bruit varie | artefact (vérifier à bruit ÷ 100) |
| lancer deux mesures/processus ensemble | banc rend `RESULT=None` (`WAIT_TIMEOUT=`) |
| prouver une non-régression par simple tolérance | il faut le **bit** |
| attribuer un effet à un paramètre non câblé | vérifier d'abord qu'il atteint le calcul |

## 5. La règle d'or et les trois contraintes

> **Tout nouveau paramètre est inactif par défaut, et le chemin inactif rend exactement les mêmes bits qu'avant.** (C1)

- **C1** : prouver au bit via `python scripts\c1_diff.py HEAD` avant commit noyau (froid vs froid ; référence §5).
- **C2** : croissance et notation voient la même perturbation pure de `(graine, tirage, index physique)` (`certus/physics/certus_strat_math.py::_seeded_noise_sample`).
- **C3** : une chose par commit. Tout correctif commence par un **test rouge sur le code d'avant**.

## 6. Pièges d'exécution

→ Référence §6 : DTO `params`, cache Numba (`numba_cache_key`), caches de classe et `qapp`, `atomic_open` et `except`, thème `CertusTheme` (jamais d'hexadécimal), premier appel Numba à chauffer.

## 7. Conventions physiques

- Macleod `n̂ = n − ik`, `k >= 0`, partout.
- `calculate_transmission_single` inclut **délibérément** la face arrière (`DO NOT REMOVE THE BACKSIDE TERM`).
- `tests/oracle/tmm_reference.py` est l'oracle TMM indépendant ; un marqueur `LOCKED` ne prouve rien.
- 🔴 **QWOT ≠ point tournant** : compter par forme fermée (`scripts\probe_turning_points.py`), référence §7.

## 8. Architecture — frontières à respecter

- `certus.core`, `certus.physics`, `certus.domain` n'importent jamais PyQt6 ni `certus.ui`.
- `certus.ui` et `CERTUS_HUB.py` ne portent aucun algorithme de calcul.
- Inversions existantes (`utils → ui`, `core → workers`, cycle `physics ↔ core`) : n'en créer aucune nouvelle ; descendre le symbole dans `domain/` ou `core/`.
- Seul `certus/domain/` a `__init__.py` (PEP 420). Gel et points d'entrée : référence §8.

## 9. Vocabulaire

→ Référence §9. Le **SEEL** (nm) est la métrique rapportée, jamais le RMSE seul.

## 10. Tenir la documentation

→ Référence §10. Un fait, un seul endroit ; le moins de mots possible.

## 11. Quand s'arrêter et demander

S'arrêter sur : ambiguïté · test ambigu · écart fort aux prévisions · tentation d'interdit · > 3 fichiers pour 1 action · **résultat meilleur que prévu** (souvent mauvaise mesure).

Toute exception est accordée par 👤, datée et motivée dans [`docs/ETAT.md`](docs/ETAT.md) §3 (et ne s'étend pas).

## 12. Vérifier le travail d'un autre agent

→ Référence §12 : rapport ≠ preuve. Ne pas déplacer l'étiquette `depart-gemini`.
