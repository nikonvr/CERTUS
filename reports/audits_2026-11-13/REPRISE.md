# REPRISE — passation du 2026-11-13 (DESIGN, audits, polisseur Levenberg-Marquardt)

Pour l'IA qui reprend. Lire d'abord `CLAUDE.md`, `AGENTS.md`, `docs/ETAT.md` §0. Ce fichier dit où en est le travail
du 2026-11-13 ; le reprise général du chantier reste `reports/refactor_corridors_2026-11-11/REPRISE.md`.

## 0. Où est le code

- Branche **`claude/reprise-057fcd`**, worktree `.claude/worktrees/reprise-057fcd/`. Arbre propre au départ de la passation.
- `origin/master` = `f30726ad` (dernier poussé). **Tout ce qui suit est local, non poussé** : 21 commits, de `f0c8a99f`
  à `e964749d` (`git log --oneline origin/master..HEAD`). Pousser = publier (dépôt public) : seulement sur ordre de 👤.
- Dernière validation complète : sur `61656d33` (U12 B, U13), parallèle, seuls les rouges connus. **Non rejouée depuis**
  le nettoyage final de DESIGN ni le polisseur LM. Tests ciblés DESIGN : verts (438 + 11).

## 1. Fait le 2026-11-13 (local)

| Sujet | Commits | État |
|---|---|---|
| U12 B, STRAT multi-graines : reprise seulement d'une graine de même fente, mêmes noyaux, même commit ; union au bit | `f0c8a99f` `6777f835` `ce9002fb` `332433f3` | fait |
| U13 partie machine : audit `--scale`, flèches d'onglets, logo sombre | `da40bdf1` `6d79a2b0` `6de96fc8` `b3cfd0b7` `eea26ff9` | fait ; reste à 👤 : `reports/refactor_corridors_2026-11-11/U13_protocole.md` |
| **DESIGN, nettoyage final automatique** (ordre de 👤, exception C1 décidée par 👤) : chaque couche sous `Min. Layer` (champ, 5 nm) retirée ou remontée, la meilleure après polissage, puis polissage ; repli règle des 5 nm en oblique ou `final_cleanup: false` | `7d7a1d91` `a3bd4cfd` `21f39b98` | fait ; mesuré une fois sur l'exemple (34 couches, rien à retirer, RMSE inchangé 0,000167) ; **pas mesuré sur un cas où il retire** |
| Audits co-conception, refactoring, dérivées, vitesse, convergence locale | `09c3f7a7` `978006cb` | `bilan.md` (ce dossier) |
| Polisseur Levenberg-Marquardt de Nielsen (`certus/core/certus_design_lm.py`) | `e828ff88` | fait, testé |
| Branché dans le mémétique : `memetic_polisher` = `lbfgs` (défaut) / `lbfgs_then_lm` / `lm` | `e964749d` | fait, testé, **défaut encore `lbfgs`** ; `c1_diff` **non passé** (interrompu par la passation) |

## 2. Décision de 👤 en attente d'exécution — à faire en premier

👤 (2026-11-13) : « je n'aime pas les options, je veux quelque chose de clef en main qui fasse le mieux possible ».
Décidé avec 👤 : **le défaut du mémétique devient `lbfgs_then_lm`** (exception C1 assumée par 👤, comme le nettoyage
final). Pourquoi celui-là : seul enchaînement au moins aussi bon que L-BFGS-B sur les deux problèmes mesurés
(`bilan.md` §3.2), et il ne peut pas finir pire que L-BFGS-B (LM part de son résultat et n'accepte que des baisses).
Repli automatique sur L-BFGS-B seul quand LM ne s'applique pas (oblique, indices absorbants, plancher sous le seuil
d'absence) ; le journal dit pourquoi.

Étapes :
1. `python scripts\c1_diff.py HEAD~1` sur l'état `e964749d` (défaut `lbfgs`) : doit rendre C1 TENU (le code ajouté
   est inerte au défaut). Un écart = s'arrêter.
2. Basculer `DESIGN_OPTIONAL_STEPS["memetic_polisher"]` à `"lbfgs_then_lm"` (`certus/core/certus_design_workers_dto.py`),
   adapter `tests/unit/test_design_memetic_lm_polisher.py::test_the_default_keeps_lbfgs`, et le test
   `tests/unit/test_design_memetic_global_stage.py` qui vérifie que les étapes optionnelles n'atteignent le worker que si
   le fichier les nomme (le défaut ne passe pas par le fichier : vérifier qu'il reste vert).
3. **Mesurer avant d'annoncer** : `scripts/design_bench.py run --no-count --set _auto_restarts=0` sur le séparateur 50/50
   (fichier de problème : `example/example_design/JSON-design-reference-tikhonravov-1996.json`, cible T = 0,5 sur
   400-1200 nm), ancien (`--set '_design_optional_steps={"memetic_polisher":"lbfgs"}'`) contre nouveau, 3 exécutions
   chacun, une à la fois (PGLOBAL tire une graine différente à chaque run). Relever RMSE de grille, couches, durée.
   Si le nouveau est plus lent sans gain, le dire à 👤 avant de garder.
4. Consigner dans `bilan.md` §3, `docs/ETAT.md`, `docs/AUDITS.md` (ALG-05/06/07, ALG-19 fermé par le nettoyage final,
   UX-12 corrigé), le REPRISE général ; commit ; validation complète (`python scripts\validate_parallel.py`) ;
   demander à 👤 s'il faut pousser.

## 3. Mesures clés (détail : `bilan.md`)

- **Séparateur 50/50** (33 couches) : LM Nielsen atteint l'optimum local en 22 à 48 évaluations ; L-BFGS-B ne l'atteint
  jamais (s'arrête 20 à 60 % au-dessus). Épaisseur optique : rien de net. Accélération géodésique : pas avec Nielsen.
- **Tri-bande** (101 couches) : le record RICL vaut RMSE 1,28e-4 sur sa grille à 1 nm et **4,8e-3 sur 0,1 nm**
  (pics étroits non vus ; **non recoupé par l'oracle**). LM converge trop lentement à 101 couches, même sur grille fine.
  Grille à 0,1 nm + L-BFGS-B : 1,0e-4 résolu (×20 en temps). Longueurs d'onde complexes (`refine_resonances`) : 3,4e-4
  résolu au prix de la grille à 1 nm, mais refus de tous les départs à 5 % (« no isolated interior error maximum »).
- Noyaux : 8 fils accélèrent le gradient de ×2 seulement ; `memetic_workers` (polissages simultanés) non mesuré.
- Co-conception : à plan figé, ±1 % sur une couche déplace l'erreur de dépôt de −3,7 % à +24,6 % ; une évaluation
  coûte 0,27 s contre 1 036 s pour trouver le plan.

## 4. Second temps (décidé par 👤, non commencé)

Co-conception niveau A (`bilan.md` §1.4) ; factorisations R1 METAL et R2 amorçage Numba (§2.2) ; branchement des
gradients existants D2 INDEX infrarouge (après C13) et D3 METAL (§4) ; polissage final du tri-bande sur grille résolue
ou en longueurs d'onde complexes (§3.4 P2) ; mesure de `memetic_workers` et profil d'une optimisation.

## 5. Sondes (toutes dans `scripts/`, mesures dans ce dossier)

`probe_codesign_sensitivity.py` (STRAT, ~15 min), `probe_kernel_threads.py` (1 min), `probe_local_convergence.py`
(problèmes RICL importés de `reports/RICL_ultimate_2026-11-05/engine.py` ; `--problems`, `--methods`, `--starts` ; la
grille fine `threeline_fine` est lourde : 5 départs ≈ 20 min). Une mesure à la fois (CLAUDE.md §4).

## 6. Pièges rencontrés ce jour

- Heredoc de Git Bash : `\\` devient `\` ; écrire les scripts de modification avec l'outil d'écriture.
- Une couleur de palette dans une f-string s'annote (`#e2e8f0/*T:TEXT_MAIN*/`) : `str()` avant de l'écrire hors feuille Qt.
- Cliquet des hexadécimaux hors thème (217) : aucune couleur en dur dans `certus/`.
- `ecrire_json` exige un chemin absolu (`.resolve()`).
- Une tâche de fond peut mourir sans sortie : vérifier qu'un fichier de résultat apparaît.
