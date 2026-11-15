# REPRISE — passation du 2026-11-13 (DESIGN, audits, polisseur Levenberg-Marquardt)

Pour l'IA qui reprend. Lire d'abord `CLAUDE.md`, `AGENTS.md`, `docs/ETAT.md` §0. Ce fichier dit où en est le travail
du 2026-11-13 ; la reprise générale du chantier reste `reports/refactor_corridors_2026-11-11/REPRISE.md`.

## 0. Point de reprise

La branche `claude/reprise-057fcd` porte les travaux du 13 novembre. La tête publiée de `master` était
`f30726ad` lors de la vérification du 2026-11-13. Les journaux et lanceurs locaux sont sous
`scratch/memetic_polisher_default/` dans le checkout principal.

## 1. Fait le 2026-11-13 (local)

| Sujet | Commits | État |
|---|---|---|
| U12 B, STRAT multi-graines : reprise seulement d'une graine de même fente, mêmes noyaux, même commit ; union au bit | `f0c8a99f` `6777f835` `ce9002fb` `332433f3` | fait |
| U13 partie machine : audit `--scale`, flèches d'onglets, logo sombre | `da40bdf1` `6d79a2b0` `6de96fc8` `b3cfd0b7` `eea26ff9` | fait ; reste à 👤 : `reports/refactor_corridors_2026-11-11/U13_protocole.md` |
| **DESIGN, nettoyage final automatique** (ordre de 👤, exception C1 décidée par 👤) : chaque couche sous `Min. Layer` (champ, 5 nm) retirée ou remontée, la meilleure après polissage, puis polissage ; repli règle des 5 nm en oblique ou `final_cleanup: false` | `7d7a1d91` `a3bd4cfd` `21f39b98` | fait ; mesuré une fois sur l'exemple (34 couches, rien à retirer, RMSE inchangé 0,000167) ; **pas mesuré sur un cas où il retire** |
| Audits co-conception, refactoring, dérivées, vitesse, convergence locale | `09c3f7a7` `978006cb` | `bilan.md` (ce dossier) |
| Polisseur Levenberg-Marquardt de Nielsen (`certus/core/certus_design_lm.py`) | `e828ff88` | fait, testé |
| Polisseur branché dans le mémétique | `e964749d` | fait, testé, C1 tenu au défaut `lbfgs` (§2) |

## 2. Première action — valider le défaut de DESIGN

Décision du 2026-11-13 : DESIGN doit utiliser L-BFGS-B puis Levenberg-Marquardt (`lbfgs_then_lm`) par défaut,
avec repli sur L-BFGS-B lorsque LM ne s'applique pas. L'utilisateur a décidé l'exception C1 pour cette bascule.

**Déjà fait.** Avant la bascule, `c1_diff` a comparé `e828ff88` à `e964749d` : `C1 TENU`, 9 092 tableaux identiques
au bit (`etape1.log`). La bascule est appliquée localement dans `certus/core/certus_design_workers_dto.py` et
`tests/unit/test_design_memetic_lm_polisher.py`. Ruff ciblé vert et 20 tests passés (`etape2.log`).
Les six essais 50/50 ont terminé. Résultats, limites et archives dans [le bilan](bilan.md#35-mesures-récupérées-après-la-coupure).

Le chemin de calcul est confirmé : sélection du worker `lbfgs_then_lm`, premier appel LM observé et
étape mémétique terminée sur l'essai court (graine 42, population et enfants à 4). La comparaison complète
sur les graines 42, 77 et 202 est au [bilan](bilan.md#36-comparaison-avec-graines-du-mémétique-appariées).
**Validation complète du 2026-11-13** sur `e2ee96b7` avec la bascule et les correctifs appliqués.
Ruff, oracle (1 202), unitaires (6 060), interface (1 589), reste (321) et performance (29). Deux tests
rouges sous charge sont verts seuls (chronométrage des noyaux et transmission du substrat). Les deux sondes
initialisent le cache Numba avant import des noyaux. Le nettoyage final a été déplacé à l'identique dans
`certus/ui/certus_design_ui_final_cleanup.py`. `VALIDATION=NO-GO` par le seul `coherence_md` connu, journal
identique à celui d'avant correction. La bascule est prête pour l'intégration locale.

**File de reprise, une action à la fois**

1. **RICL terminé.** Les huit couples manquants ont été ajoutés à la série. Voir le
   [bilan des 21 mesures](bilan.md#35-mesures-récupérées-après-la-coupure). Le lanceur local
   `ricl_lm_resume.py` reprend les couples manquants et écrit dans une sortie séparée.
2. **U13.** Faire les essais sur écran réel, avec le Narrateur et avec les utilisateurs selon le
   [protocole U13](../refactor_corridors_2026-11-11/U13_protocole.md).
3. **STRAT local-search.** Examiner l'unique commit propre à `wip/strat-local-search-ricl-2026-11-11`
   avant de le reporter sur la base validée.
4. **Reprise de calcul U12 B.** Après STRAT multi-graines, prendre STRAT robustesse en premier, puis traiter
   DESIGN PGLOBAL et INDEX SPLINE un par un, avec un essai d'interruption et de reprise au bit par moteur.
5. Reprendre les chantiers scientifiques du §4.

## 3. Mesures clés (détail : `bilan.md`)

- **Séparateur 50/50** (33 couches) : LM Nielsen atteint l'optimum local en 22 à 48 évaluations ; L-BFGS-B ne l'atteint
  jamais (s'arrête 20 à 60 % au-dessus). Épaisseur optique : rien de net. Accélération géodésique : pas avec Nielsen.
- **Tri-bande** (101 couches) : le record RICL vaut RMSE 1,28e-4 sur sa grille à 1 nm et **4,8e-3 sur 0,1 nm**
  (pics étroits non vus ; **non recoupé par l'oracle**). LM converge trop lentement à 101 couches, même sur grille fine.
  Grille à 0,1 nm + L-BFGS-B : 1,0e-4 résolu (×20 en temps). Longueurs d'onde complexes (`refine_resonances`) : 3,4e-4
  résolu au prix de la grille à 1 nm, mais refus de tous les départs à 5 % (« no isolated interior error maximum »).
- Tri-bande sur grille à 0,1 nm, 10 départs à 5 % (`local_convergence_threeline_fine_20261113_132038.json`, run arrivé
  après la passation) : L-BFGS-B 8/10 (1,03e-4), **L-BFGS-B puis LM 8/10 (1,03e-4)**, LM seul 0/10, LM puis L-BFGS-B 2/10 :
  l'hybride retenu ne perd rien face à L-BFGS-B, là où LM seul échoue.
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
