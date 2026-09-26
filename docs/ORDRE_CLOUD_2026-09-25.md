# ORDRE DE MISSION CLOUD — 2026-09-25

> Écrit à la demande de 👤, qui finance ces sessions sur un crédit de 100 $. **Une tâche par
> session, dans l'ordre.** Chaque session travaille sur une branche `cloud/<tâche>` partie de
> `refactor-corridors-mixins`, pousse cette branche, et **ne fusionne rien** : 👤 relit.
> Ce fichier sera archivé par la tâche 1 une fois les quatre tâches faites.

## Règles communes — non négociables

- Environnement : Linux, **Python 3.14** (`uv python install 3.14` si absent), dépendances de
  `pyproject.toml`. Vérifie : `python -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"`
  doit pointer dans ton clone.
- Validation de toute tâche : `python -m ruff check .` → `All checks passed!` et
  `python -m pytest tests/oracle/ tests/unit/ -q --no-cov` → `0 failed`. `tests/ui/` n'est
  **pas** exigé en cloud (calibré sur les polices Windows).
- ⚠️ **À cache numba froid, trois tests échouent faussement** : `test_phase2_gradient_analytic_vs_fd`
  et les deux `TestIRGlobalModelStrategy`. Relance-les une seconde fois avant de conclure
  (`CLAUDE.md` §2) ; ils passent à cache chaud.
- État de départ, mesuré le 2026-09-26 sur `f0b30b3` (Windows, Ryzen 7 5700G, Python 3.14.7
  système, numba 0.67.0, cache chaud) : `ruff` propre · `tests/oracle/` 569 passed ·
  `tests/unit/` 2 504 passed, 5 skipped · `tests/regression/` 8 passed · `tests/ui/`
  785 passed, 10 skipped, 3 xfailed · `test_ux_re_stop_when_idle.py` 6 passed. **0 failed.**
- Interdits (détail dans `CLAUDE.md` §6) : jamais `ruff --fix`, jamais agrandir
  `extend-ignore`, ne pas toucher `example/example_strat/JSON-strat-example.json`, ne pas
  supprimer `reports/`, **aucune campagne physique** (runs de 25 min à 2 h 39 qui dépendent de
  la machine), aucun résultat affirmé sans sa sortie collée.
- Commits petits, messages en français sans accents comme l'historique, terminés par la
  ligne `Co-Authored-By` habituelle.
- 🔴 **Les quatre tâches tournent EN PARALLÈLE, sur quatre branches.** Pour qu'elles fusionnent
  sans conflit : **seule la tâche 1 modifie des `.md`** — les tâches 2 à 4 consignent leurs
  résultats dans leurs messages de commit ; et **la tâche 1 ne modifie aucun `.py` de
  `certus/`**, qui appartient aux tâches 3 et 4.

## Tâche 1 — Cure documentaire radicale (priorité : elle rend toutes les suivantes moins chères)

👤, 2026-09-25 : *« les milliers de lignes des fichiers md sont totalement contre-productives »*.
Mesuré : `CLAUDE.md` coûte **~58 000 tokens à chaque session** ; le corpus fait ~17 000 lignes.

**Cible** :
- `CLAUDE.md` **≤ 250 lignes** : mission (3 lignes), environnement et `preflight.py`, commandes
  de validation, les onze interdits (une ligne + une ligne de raison), les erreurs qui annulent
  un travail, la règle d'or C1, le protocole de mesure, et la carte vers `docs/ETAT.md`.
  **Aucun récit** (« cette ligne disait… », « trouvé le… ») : `git log` le garde.
- `docs/ETAT.md` **≤ 300 lignes** : seulement ce qui est vrai AUJOURD'HUI, chaque fait avec sa
  source (commit, artefact ou fonction) — repères mesurés, défauts ouverts, décisions gravées
  de 👤, paramètres du modèle, programme courant, chantiers ouverts avec leur état.
- Tout le reste de `docs/` → `docs/archives/` par `git mv` **sans modification du contenu**,
  plus une première ligne : « ARCHIVE — ne fait pas autorité ; l'état courant est dans
  `docs/ETAT.md` ». `AGENTS.md` et `GEMINI.md` : cinq lignes de renvoi.
- Réparer `tests/headless/README.md` (liste des fichiers, `python`, avertissement : `test_design`
  et `test_strat` mesurent un mock) et `tests/regression/README_REGRESSION_TESTS.md` (espaces
  supprimées dans le texte).
- Adapter `scripts/coherence_md.py`, `scripts/check_claude_md.py` et tout test ou script qui
  lit un chemin de `docs/` (`grep -rn "docs/" scripts tests`).

**Contradictions déjà tranchées dans le code le 2026-09-25 — à écrire juste dans ETAT.md :**

| sujet | ce qui est vrai |
|---|---|
| correction √3 de la fente | **faite** (`certus_strat_robustness.py`, `res_limit = test_bw * np.sqrt(3.0 * T_tolerance / curvature)`) |
| `machine_sampling_dd` | existe et **découplé** du lissage dans le noyau (`use_fine_grid`), mais les appelants passent `0.0` : **inatteignable** |
| arrêt quantifié `U(0 ; 0,125 nm)` | **non appliqué** (l'arrondi du Rate n'en est pas une preuve) |
| `n_screen_runs` | **25** ; ne pas descendre à 10 depuis le correctif 1 |
| `robustness_num_runs` | **300** (décision 👤 du 2026-08-13), pas 150 |
| POEM ×41,2 | mesuré **avant** le biais de fente : **périmé**, ne plus le citer comme acquis |
| mode Rate | **implanté** ; le rate ne se calcule que sur les couches **optiques** ; Rate interdit sur les couches 0 et 1 |
| SEEL | quantifié à **0,01 nm** ; la seconde borne `max(0,05 ; 0,06·SEEL)` est du code mort |
| `strategy_phase_timeout` | **inerte** (aucun code de calcul ne le lit) — le README des exemples STRAT le décrit comme actif |

Règle nouvelle à écrire dans `CLAUDE.md` : **citer une FONCTION, jamais un numéro de ligne**
(38 % des renvois `fichier.py:ligne` vérifiables étaient périmés le 2026-09-25).

**Acceptation** : `wc -l CLAUDE.md` ≤ 250 · `wc -l docs/ETAT.md` ≤ 300 · aucun fichier supprimé
(seulement déplacés) · `python scripts/coherence_md.py` sans point à instruire et contrôle négatif
vert · `python scripts/check_claude_md.py` sans référence morte · validation commune verte.

## Tâche 2 — CI Linux qui exécute vraiment les tests

`.github/workflows/tests.yml` doit lancer `tests/oracle/` puis `tests/unit/` sur `ubuntu-latest`
en Python 3.14. Corriger ce qui échoue **pour raison de plateforme** (chemins Windows, polices,
encodage) sans toucher à la physique ; un test intrinsèquement Windows devient `skipif` avec sa
raison écrite. **Acceptation** : un run GitHub Actions vert sur la branche, lien dans le message
final ; aucun test désactivé sans raison.

## Tâche 3 — Commentaires de `certus/` en anglais (interdit n° 11)

~450 lignes de commentaires, docstrings et 7 messages de journal en français, dans ~24 fichiers
(la moitié dans `core/certus_strat_robustness.py`). **Garde mécanique obligatoire** : pour chaque
fichier, l'AST avec docstrings retirées doit être identique avant/après ; seules les chaînes des 7
`logger.*` changent, étiquettes conservées (`[RATE]`, `[SLIT]`, `[WL-COUVERTURE]`… — un test lit
cette dernière). Ne pas traduire les libellés d'interface (autorisés en français). Ne pas écrire
d'hexadécimal dans un commentaire (un cliquet compte au niveau du texte). Ajouter
`tests/unit/test_certus_comments_in_english.py` : cliquet à zéro, avec un contrôle négatif qui
prouve qu'il détecte un commentaire français planté.

## Tâche 4 — Le substrat silicium lit une table de secours

`certus_physics/materials_data.py` cherche `material_constants.xlsx` puis `clues.xlsx` à la racine :
**aucun des deux n'a jamais été dans le dépôt**, donc INDEX (`_get_silicon_n_on_grid`) et RE (le
substrat « silicon », priorité 1 de `_re_resolve_substrate_material`) utilisent **en silence** la
table de secours à 15 points. Écart de réflectance air/Si contre la feuille `Si-substrate`
(566 points) de `example/database_index/indices.xlsx` : **−11 points à 400 nm, +0,9 point vers
900 nm**, nul au-delà de 1 200 nm. À faire : lire cette feuille versionnée en priorité, garder la
table en dernier recours avec un **WARNING** ; corriger la docstring (les valeurs IR sont celles de
Salzberg & Villa 1957, pas de Li 1980). Test qui **échoue sur le code d'avant**. ⚠️ Cela change les
résultats INDEX et RE sur silicium : ce n'est **pas** un changement C1, dis-le dans le commit.

## Hors cloud — à garder pour 👤

- Nb2O5 Syrus : n chute de 2,09 à 1,19 entre 4,0 et 4,7 µm avec k ≤ 0,018 — incompatible avec
  Kramers-Kronig, à revoir avant tout design MWIR.
- Le dépôt vit dans un dossier **Google Drive partagé par deux PC** : risque de corruption de `.git`.
  Les worktrees de `.claude/worktrees/` (~2 Go de copies) et les branches `claude/*` sans commit
  propre sont à supprimer par 👤 ; le travail utile de `claude/ux-plan-simplifie` est intégré.
- Le nom civil est retiré de l'arbre (40 classeurs, 2026-09-25) mais reste lisible dans
  l'**historique** public : la purge (`git filter-repo` + force-push) est une décision de 👤.
