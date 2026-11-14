# Audit des chantiers restants — 2026-11-14, 17 h

Base : `docs/CHANTIERS_RESTANTS.md` à `1d9977f6`, 15 lignes actives. Le code a été vérifié par recherche
(`rg`) et les sources A, Q, U12, U13, le contre-audit et la campagne A ont été relus. Aucune mesure n'a été
lancée : chaque durée citée vient d'une source nommée, les autres estimations sont des jugements.

## 1. Constats transverses

1. **27 commits sans validation complète.** La dernière `VALIDATION=GO` porte sur `de52e01c`. Depuis, Codex
   a fermé 01, 02, 04, 08, 10, 11, 12, 14, 15 et 22, avec des changements dans `certus/core` (contexte de coût
   DESIGN, gradients INDEX IR et FIELD). Aucun commit ne touche `certus/physics` ni
   `certus/core/_certus_physics_impl.py`. La validation finale du chantier 19 couvrira cette tête : ne rien
   bâtir de lourd avant qu'elle soit à `0 failed`.
2. **70 commits non poussés** sur master. Aucune copie hors de cette machine, sauf les bundles du dossier
   parent. Pousser publie et dépend de 👤 seul.
3. **Violation de §8 dans le code.** `certus/ui/certus_index_spline_smart_init.py:893` lance un
   `opt.minimize(..., "L-BFGS-B", maxfun=150)` sur le fil de l'interface, sous curseur d'attente. C'est un
   algorithme dans `certus.ui`, qui gèle aussi la fenêtre. C'est aussi l'un des trois sites du chantier 21.
4. **Préalable perdu.** A §4 cite « le gradient faux sur couches absorbantes (C20), à corriger avant
   d'étendre quoi que ce soit ». C20 n'a plus de définition dans `docs/` ni dans les sources relues. Le bilan
   FIELD dit que D113 ne concerne pas FIELD. Aucune trace d'une correction : à instruire avant tout nouveau
   gradient sur couches absorbantes.
5. **Machine unique.** Une seule mesure ou validation à la fois (AGENTS.md §5, CLAUDE.md §4). Le chantier 19
   occupe la machine pour une dizaine de suites complètes. Les sessions parallèles ne gagnent du temps que sur
   le code et la lecture, pas sur les mesures.

## 2. Chantier par chantier

Exécutable : **IA** = une IA peut le finir seule ; **👤** = une décision ou une action de 👤 le bloque.

| N° | État vérifié | Preuve dans le code ou les sources | Bloquant | Prochaine action | Exécutable |
|---:|---|---|---|---|---|
| 05 | Non fait. 6 ajustements sans Jacobien | `certus_substrate_sellmeier.py:242, 665, 843` ; `certus_substrate_index.py:1498` ; `certus_index_utils.py:576, 611`. Un seul a son Jacobien (`:690`, `_jac_polish_q`) | Gain annoncé faible (« déjà rapides », A §4) | Mesurer d'abord la part de temps de ces 6 sites sur un ajustement réel ; si elle est faible, retirer le chantier | IA |
| 07 | Partiel. 5 copies de `_warmup_numba_thread_runner` | `index_spline_eventsextras_mixin:84`, `index_ui_worker:115`, `metal_single_gui:240`, `metal_bilayer_gui:211`, `strat_ui_worker:104` | Aucun | Une implémentation au socle, une fenêtre par commit ; tests `ui` ; démarrage à froid des 5 fenêtres | IA |
| 16 | Non fait. 3 fenêtres détachées et 2 classes de graphes | `certus_curve_smoother.py:51`, `certus_ui_widgets_utils.py:657`, `certus_field_common.py:43` | Décision de 👤 sur le périmètre UI (A §2.3) | Après décision : une classe commune, STRAT protégé d'abord par ses tests | 👤 puis IA |
| 18 | Non fait | `CurveSmootherGUI(QMainWindow)`, `SubstrateIndexGUI(QMainWindow)` : hors `CertusBaseApp` | Décision de 👤 (A §2.3) | Après décision : migrer sur le socle, une fenêtre par commit | 👤 puis IA |
| 19 | En cours dans une session dédiée | `scripts/probe_test_selector.py` appelle `validation.run_plan`, absent de `validate_parallel.py` : le script n'a jamais tourné ; son `ok` compte un mutant non détecté comme succès | Machine occupée par ses mesures | Laisser finir ; sa validation de clôture couvre aussi le constat 1 | IA, en cours |
| 20 | Non fait. Témoin disponible : MF résolu 0,10983 % à TOT fixée | Q §10 | Aucun, mais lourd et P3 | Comparer au témoin, puis départs éloignés | IA |
| 21 | Non fait. 3 sites sans gradient et 1 repli | `spline_workers.py:545`, `spline_smart_init.py:959`, `certus_index_spline_smart_init.py:893` (UI, constat 3), repli `certus_corridor_utils.py:1046` (`jac=None`) | Constats 3 et 4 | (a) descendre l'optimisation du Smart Init dans `certus/spline/` ; (b) profiler ; (c) gradient des valeurs aux nœuds, puis des positions, différences finies aux cas limites | IA |
| 24 | Résultat négatif mesuré : la sélection robuste à 1 nm augmente la RMSE déposée de 51,9 à 81,7 % sur 3 paires | `reports/codesign_2026-11-14/bilan.md` | Pas de modèle de dépôt représentatif : 31–32 couches Rate sur 34 | 👤 fournit ou choisit le modèle de la machine visée (part de Rate, bruit de vitesse) ; sans lui, rien ne peut conclure | 👤 puis IA |
| 25 | Non fait. Aucun code Fourier dans `certus/` | `rg -i fourier certus` : rien | Piste non mesurée, P3 | Sonde hors noyau sur trois-raies et cissoïde ; décision écrite | IA |
| 27 | Non fait ; unité « tirage » mal choisie | Contre-audit A.5 : 300 tirages coûtent 0,27 s, le pipeline de plan 1 036 s | U12 §6 : « B plus tard », décision de 👤 | Respécifier par étape du pipeline ; tests U12 §5 rouges d'abord | 👤 puis IA |
| 28 | Non fait ; spécification en retard sur `run_memetic` | U12 §4, contre-audit A.5 | Idem | Respécifier : population, générateur, génération, ouvriers | 👤 puis IA |
| 29 | Non fait ; aucune durée de corridor mesurée | U12 §4 | Idem | Mesurer la durée d'un corridor réel avant tout code | IA (mesure) puis 👤 |
| 31 | Non fait ; `joint_local_search` varie longueur d'onde et mode, pas les épaisseurs | A §1.4 | Même modèle de dépôt que 24 | Candidat « épaisseur ±δ » et réaccord des voisines, jugé contre les cibles sur graines disjointes | 👤 puis IA |
| 32 | Non fait | A §1.4, campagne A | Même modèle | Après 31 : corrélation critère/SEEL | 👤 puis IA |
| 33 | Partie machine faite ; constats vides | `U13_protocole.md` §3 « (vide) » | Humains et écran réel | Une demi-journée de 👤 avec cinq utilisateurs | 👤 seul |

## 3. Retraits et regroupements proposés

- **05** : retirer si la mesure confirme « déjà rapides ». Un Jacobien change les derniers bits des références :
  un C1 complet pour un gain faible.
- **27, 28, 29** : une seule respécification « reprise B », puis réouverture moteur par moteur sur mesure.
  Tant que 👤 maintient « B plus tard », ces lignes ne peuvent pas avancer.
- **24, 31, 32** : un bloqueur commun, le modèle de dépôt ; à regrouper en « co-conception, phase 2 ».

## 4. Ordre le plus rapide

Une mesure à la fois sur la machine ; le code avance en parallèle dans des sessions séparées, sur des fichiers
disjoints.

1. **Maintenant, sans la machine** : 07 (UI seule) et 21 (a), qui descend le Smart Init dans `certus/spline/`.
   Fichiers disjoints : deux sessions en même temps ; leurs tests attendent la fin des mesures du 19.
2. **Décisions de 👤**, sans calcul : périmètre UI (16, 18) ; feu vert ou gel de la reprise B (27–29) ; modèle de
   dépôt (24, 31, 32) ; date des essais U13 (33).
3. **Après la validation du 19** : mesure de 05, profil de 21, puis 21 (b, c).
4. **Selon les décisions** : 16 puis 18 dans une même session (même socle UI) ; puis 31, puis 32 et 24.
5. **En dernier** : 20 et 25, pistes P3.

## 5. Suites le même soir

- `1d9977f6` était rouge : `test_the_architecture_debt_only_shrinks.py` donnait 4 échecs, laissés par les
  commits précédents. `bdd90b97` annote FIELD (C1 au bit sur 9 092 tableaux) et `76ed4870` abaisse les plafonds
  METAL. `f1e6d10a` relève deux plafonds sur décision de 👤 : `certus_index_objectives.py` passe de 1 933 à
  1 940 lignes et `certus_strat_service.py` de 1 613 à 1 616. Ce choix a été préféré au découpage.
- Le chantier 19 a corrigé son script dans `0f61340b`. Ses mesures sont dans `reports/selecteur_tests_2026-11-14/`.
- Les chantiers 07 et 21 (a) sont écrits sur leurs branches. Leurs tests attendent la fin des mesures du 19.
