# Audit général du projet — 2026-11-14, 20 h

Demandé par 👤. Objet : chercher des améliorations absentes de [la liste des chantiers](../../docs/CHANTIERS_RESTANTS.md),
après l'audit contradictoire de la reprise du chantier 19 et de cette liste.

Méthode : lecture et recherches (`git grep`, `git log`) sur `ac191592`, plus la relecture des résultats déjà produits
par le chantier 19 (`reports/selecteur_tests_2026-11-14/runs/`, non suivis à cette date). **Aucun test ni aucune mesure
de calcul n'a été lancé.** Un compte ci-dessous est le résultat d'une recherche ; « non vérifié » veut dire que je n'ai
pas regardé.

## 1. Ce qui est sain

| Point | Constat |
|---|---|
| Frontières de §8 | 0 import de PyQt6 et 0 import de `certus.ui` dans `certus/core`, `certus/physics`, `certus/domain` |
| Exceptions | 0 `except:` nu ; 226 `except Exception` dans `certus/` (138 dans `ui`, 4 dans `physics`), gardés par `tests/unit/test_no_broad_exception_is_swallowed_in_silence.py` |
| Dette visible | 0 `TODO`/`FIXME` dans `certus/` ; 16 `# noqa` ; 28 `type: ignore` |
| Tests | 668 fichiers de test, 115 738 lignes pour 177 000 lignes de `certus/` environ ; témoin du 19 : 9 327 tests passés |
| Chantier 07 | une seule définition de `_warmup_numba_thread_runner` ; démarrage à froid identique sur les cinq fenêtres |

## 2. Constats qui appellent un chantier

1. **Un test C1 échoue par intermittence (→ 34).** `test_the_slit_profile_is_inert_when_absent_or_zero` compare au
   bit (`np.array_equal`) deux appels de `update_run_states_kernel`, profil de fente absent et nul. Il échoue au
   premier passage sous charge et passe au rejeu isolé, à la validation de `de52e01c` comme au témoin du 19 sur
   `ac191592` ; il n'a pas échoué dans la suite complète du cas `infrared_center`. Le validateur le classe
   `ARTEFACT`. Cause non mesurée. Tant qu'elle est inconnue, « identique au bit » n'est pas établi sous charge, et les
   reprises 27 à 29 reposent sur cette identité.
2. **ALG-03 est ouvert et sans chantier (→ 35).** `docs/ETAT.md` §1 : « le mode oblique calcule sur 2 points au lieu
   de 135 ». Le bilan Q du 13 novembre le dit encore ouvert : la grille densifiée par
   `maybe_upgrade_grid_tikhonravov` ne reconstruit pas le précalcul câblé dans
   `_initialize_runtime_state_for_optimization`. Les deux fonctions existent ; je n'ai pas vérifié que le défaut se
   produit encore. C'est la classe d'erreur que CLAUDE.md redoute : un résultat faux qui a l'air juste.
3. **Le registre des défauts a disparu (→ 36).** D84, D111, D112, D113 et D116 sont cités « ouverts » par les audits
   du 14 novembre et par la liste (gel du 26). Aucun n'a de définition dans `docs/`, `certus/`, `tests/` ni
   `scripts/` ; ils ne vivent que dans d'anciens rapports. Il en va de même de C20, « gradient faux sur couches
   absorbantes, à corriger avant d'étendre quoi que ce soit » (A §4). Personne ne peut dire lesquels sont corrigés.
4. **Rien ne contrôle une publication avant qu'elle parte (→ 37).** `gitleaks` et `pip-audit` ne tournent qu'en CI.
   `master` a 93 commits d'avance sur `origin/master` : aucun n'est passé par la CI, ni sous Linux. Aucun script
   local ne vérifie secrets, métadonnées des classeurs et œuvres de tiers.
5. **Il reste des algorithmes dans `certus.ui` (→ 38).** Deux `scipy.optimize.minimize` avec leur fonction de coût
   et de gradient dans `certus/ui/certus_design_ui_optimization.py`. Même violation de §8 que celle levée par 21 (a).
6. **L'exécutable gelé a 657 commits de retard (→ 39).** Construit à `dbec2fc1` (2026-10-06). `pyproject.toml` porte
   la version `26.05.0`. Non vérifié : que les exports portent une version qui distingue l'état du code.
7. **Aucun recoupement par un code tiers (→ 40).** `tests/oracle/tmm_reference.py` est indépendant de
   `certus.physics`, mais écrit dans ce projet. Aucun test ne compare à un code externe, et `docs/ETAT.md` §1 note
   « validation externe : aucune ».
8. **Douze branches Dependabot en attente (→ 41)**, la plus ancienne du 2026-09-30, dont `pillow-13.0.0` et
   `setuptools-84.1.0`.
9. **30 scripts sur 106 ne sont cités nulle part hors `reports/` (→ 42).** Parmi eux, des outils qui appliquent une
   règle de CLAUDE.md : `check_inert_params.py` (C1), `check_param_effect.py` (§4, paramètre qui n'atteint pas le
   calcul), `probe_kernel_threads.py`, `narrow_broad_except.py`. Un outil que personne ne trouve ne sert pas.

## 3. Constats sans chantier nouveau

- **`docs/ETAT.md` §6** disait encore que les P1 concernent la co-conception ; corrigé avec la liste.
- **CI** : mypy et `bench_kernels` non bloquants, contrôles documentaires absents de `lint.yml` : déjà chez 👤
  (`docs/ETAT.md` §5, D110).
- **Couverture** : jamais mesurée (`--no-cov` partout, CI comprise). `scripts/mutation_pilot.py` existe et mesurerait
  mieux la force des tests ; coût machine élevé, non proposé tant que 34 à 36 sont ouverts.
- **107 marqueurs `skip`** dans `tests/` : non triés ; à regarder si un jour la suite doit prouver davantage.
- **Poids de l'interface** : 78 737 lignes sur 177 000, soit 44 % du code ; les chantiers 16 et 18 le traitent.

## 4. Ordre proposé

1. **34, 35, 36** : fiabilité du calcul ; une IA peut les mener seule, un à la fois (34 occupe la machine).
2. **37** avant la prochaine poussée, quelle qu'en soit la date.
3. **38**, puis le reste de la liste selon les décisions de 👤.
4. **39 à 42** : décisions de 👤 d'abord.
