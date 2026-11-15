# Reprise — session autonome du 2026-11-14 soir (worktree `claude-code-suije-bf4f1f`)

Non commité. Mandat de 👤 (2026-11-14, ~20 h) : plus de 12 h d'autonomie, décisions et arbitrages pris seul ; 👤
autorise à braver un interdit « s'il le faut ». Gardés quoi qu'il arrive : jamais `git push`, interdits 3, 6, 7, 9.
Toute entorse : raison dans le commit et ici.

## Fait

- `2b91d166` bilan de l'audit général ; `ceac0080` chantiers 34–42 dans la liste.
- `reports/selecteur_tests_2026-11-14/REPRISE.md` corrigé ici (la copie de `certus1111` est l'ancienne).

- `runs/unit_numba1.log` : INVALIDE. Un ouvrier xdist meurt sur
  `test_strat_multigraine_ui.py::test_le_pilotage_par_QProcess_remplit_reellement_le_tableau` (INTERNALERROR,
  ~960 tests non joués). Le fichier seul passe à 1 et 16 fils : instable sous charge → noter au chantier 34.
- 36 : le registre `docs/AUDITS.md` (état 2026-10-26, ~60 entrées « ouvert ») a été supprimé par `b6fb1939` ;
  relire par `git show b6fb1939^:docs/AUDITS.md`. C13/D112 corrigé (`dk5 = 0` au centre). C18/D111 : parade
  `cache=False` en place, cause ouverte. C20/D113 : probablement corrigé (oracle FD absorbant passe) → rejouer
  `reports/AUDIT_2e_passe_2026-10-18/probe_c20_conj.py.txt`.
- 35 : ALG-03 présent à la lecture (configs obliques densifiées construites puis jetées dans
  `maybe_upgrade_grid_tikhonravov`). Sonde écrite : `reports/alg03_grille_oblique_2026-11-14/probe_alg03.py`.

- Vitesse `unit`, `-n 16 --dist loadfile`, cache chaud : 1 fil Numba 299 s (3 échecs), 16 fils 512 s (1 échec).
  Échecs rejoués seuls : `test_neutral_parameters_are_bit_identical_to_the_legacy_call` et
  `test_a_quiet_run_still_ends_on_the_summary_line` passent (instables sous charge) ; POEM
  `test_without_the_flag_the_kernel_keeps_the_coarse_samples_bit_for_bit` ÉCHOUE SEUL aux deux réglages.
- POEM : passe sur cache vierge (2 fois), échoue sur le cache partagé `6ef1064d5729/physics_a6ac…`. Coupable isolé
  par dichotomie : `simulate_growth_kernel-1055.py315.36.nbc` (20:19:14), même signature qu'un objet compilé à neuf
  mais 444 Ko contre 333 Ko de code machine, trois spécialisations de `detect_turning_points` liées : compilé dans
  un processus à long historique. Preuve copiée dans `%TEMP%\certus_evidence_cache_2026-11-14\` (42 Mo).
  `test_strat_multigraine_ui.py` seul ne l'empoisonne pas.

- Reproduit : cache vierge + `unit` complet à 1 fil (408 s à froid) → POEM échoue dans le passage, puis seul.

- 16 fils, cache vierge : session tuée (EXIT=3) par le même test QProcess. Cause : `qt_lifecycle` attend le
  préchauffage STRAT (95 s à froid seul) et appelle `pytest.exit` après 180 s ; xdist le lit comme un crash.
  Corrigé `b6d392bb` (fichier : 100 s → 3,8 s à froid).
- POEM : l'objet fautif lie deux versions de plus de `complex_mul`/`complex_div` internes de Numba (compilées tôt
  dans le processus). Bits = f(historique de compilation). Pas de correction du noyau (C1 partout).
  `f350044d` : le validateur rejoue ses échecs sur un cache Numba vierge (règle d'ETAT §0 automatisée).
- `376baef1` : chantier 43, fils Numba = cœurs ÷ ouvriers pour les étapes xdist (sauf valeur posée).

- Validation complète `376baef1` : GO, 20:41 (unit 4:18, ui 10:29). `ui` à 16 fils 10:11, à 2 fils 10:31, BLAS=1 10:44.
- Commits doc : `bdeb53fe` ETAT §0, `ce101cd8` bilan §5–7, `ebe789ac` chantiers 34/36/43.

- `ui` depuis C: : 10:23 → le disque n'explique pas le 7:45 du témoin du 19 (inexpliqué, piste close).
- C20 CONFIRMÉ ET CORRIGÉ `78515573` : chemin face avant de `compute_gradient_all_layers_analytic` (couches
  absorbantes n − ik, substrat sans perte, sans face arrière) → noyau juste seulement en n + ik, coût +343 %.
  conj à la frontière. c1_diff : 136/9092 tableaux changent, tous `normal.gradall0/1` (voulu). Nombres changés.
- ALG-03 reproduit (2 points au lieu de 135 ; RMSE rapporté 0,026, dense 0,175). Correction écrite dans
  `certus_design_workers.py` (configs obliques reconstruites + coût réévalué), test
  `tests/unit/test_design_oblique_refinement_sees_the_dense_grid.py` rouge avant, vert après ; sonde après :
  RMSE rapporté = dense = 0,17197.

- ALG-03 commité `4d634756` ; doc `4b539941`, `3e047e5f` ; validation 2 sur `3e047e5f` : GO, 0 échec, 21:32 ;
  `20b979d9` l'enregistre.

- 36 : tri `4836a6cb` (`registre_tri.md`), ligne réduite `b84808b0`.
- 19, premier essai sur `20b979d9` : témoin tué (worker mort sur `test_strat_disconnected_settings`, même
  mécanisme : join 180 s de `qt_lifecycle` sur cache froid). `ddd29cc4` : join porté à 600 s.
- ALG-13 : `should_stop` (inactif par défaut) dans `run_coord_descent_5cycles`, le worker passe
  `self._stop_event.is_set` ; test `tests/unit/test_design_final_refinement_honours_stop.py` 2 rouges avant, 3 verts
  après. NON COMMITÉ à l'écriture.

- ALG-13 commité `df36593f` (oracle 1209, c1_diff tenu).

## En cours

- Chantier 19 sur `df36593f` → `reports/selecteur_tests_2026-11-14/runs_df36593f/` (témoin puis 8 cas, ~4 h 30,
  début ~23 h 35). `runs_20b979d9/` = essai au témoin tué, gardé comme preuve.

- Chantier 38 ÉCRIT, NON TESTÉ, NON COMMITÉ : `lbfgsb_polish` dans `certus/core/certus_design_final_cleanup.py`, les
  deux `minimize` de `certus/ui/certus_design_ui_optimization.py` l'appellent ; test d'identité au bit
  `tests/unit/test_design_window_polish_moved_to_core.py`. À jouer après la mesure du 19 (rien ne charge la machine
  pendant).

## Ensuite

1. Bilan du 19 ; chantiers 19/36/43 ; bilan général §8 (ALG-13), §7 (join 600 s) ; validation finale.
2. Pendant la mesure, rien qui charge la machine : lecture et rédaction seulement.

- 2026-11-15 ~02 h : décisions de 👤 consignées (commit ci-dessus) : 18 thème+session, 16 retiré, modèle = JSON exemple, reprise B mesurer d abord, 39/40/41 en local. Seul 33 bloqué.
- 02:03 : 42 clos (b281ec95). 37 ÉCRIT NON TESTÉ : scripts/check_publication.py + tests/unit/test_check_publication.py (sur origin/master..HEAD : 114 commits, PUBLICATION=GO). Tester après la mesure, puis commit.
- 02:06 : 41 bilan ÉCRIT (reports/dependabot_2026-11-15/bilan.md, reste : essai pillow 13). 40 sonde ÉCRITE (reports/tmm_tiers_2026-11-15/probe_tmm_tiers.py ; tmm 0.2.0 installé dans %LOCALAPPDATA%\Temp\certus_tmm_tiers, convention n+ik vérifiée dans son code) — à lancer après la mesure.
  File d'attente après la mesure du 19 : bilan 19 → tests+commit 38 → tests+commit 37 → sonde 40 + bilan → pillow 13 + commit 41 → validation finale → 18, 39, mesures 27-29, ALG-20 (mesurer si la borne 1,2 QWOT de PGLOBAL mord).
- 08:20 : INCIDENT. Cas spectral_width (mutation de spectral_weights.py) bloqué de 02:40 à 08:25 : le worker de tests/ui/test_ux_no_horizontal_scroll.py (DESIGN 1366x768) affiche la boîte modale « Unsaved configuration » à `win.close()` et `run_ux_worker` (tests/ui/_ux_worker.py) n'a AUCUN délai → attente infinie. Parade : surveillant PowerShell (%TEMP%\c19_watch.ps1, tâche bfhi6pn2b) qui tue tout worker UX de l'arbre mesuré âgé de plus de 240 s, journal runs_df36593f/watcher_kills.txt. Durées du cas spectral_width : invalides (6 h d'attente). À corriger après la mesure : délai dans run_ux_worker (test rouge d'abord) + empêcher la boîte modale à la fermeture d'un worker.
- 08:26 : contrôle de santé toutes les 15 min (cron 121449c2, session seulement, xx:04/19/34/49) : %TEMP%\c19_health.ps1 → STATE=OK|MODAL|STALL|PROBE_ENDED (MODAL = fenêtre visible d'un python ; STALL = aucun journal écrit depuis 15 min). Correctif du délai écrit dans tests/ui/_ux_worker.py (timeout_s=600, échec immédiat sans nouvel essai), NON TESTÉ, NON COMMITÉ.
- 08:41 : audit OMS 5100 (lecture seule) commité : reports/audit_oms5100_2026-11-15/bilan.md. Suites possibles : profil du noyau STRAT par poste, V2 puis V1 (après la mesure du 19).
- 08:49 : audit OMS révisé sans salle (cb059d97), chantier 44 ajouté. Étapes 1 à 3 du plan (profil, V2/V1, sonde de sensibilité) prêtes à partir après la mesure du 19.

## PASSATION (2026-11-15, ~09:10) — changement de compte, contexte de conversation perdu

Branche `claude/claude-code-suije-bf4f1f`, worktree `.claude/worktrees/claude-code-suije-bf4f1f`. Rien n'est poussé (ne jamais pousser).
Derniers commits : 0fd86dbf (fente 4 valeurs), 2051821b (HELIOS 800 à 240 tr/min), c27b7903 (chantier 44), cb059d97 (audit OMS révisé).

**Mesure du 19** : témoin vert ; infrared_center, empty_phase_a, qwot_signal_state, angle_boundary = OK ; **spectral_width = ESCAPED**
(cas bloqué 6 h par la boîte modale, worker tué à 08:22 : vérifier si l'échappé vient de cet artefact avant de conclure) ; restaient
thickness_units (en cours), field_chain, overflow_boundary. Si la session a coupé la mesure : `git -C %LOCALAPPDATA%\Temp\certus_c19_df36593f
checkout -- .` puis relancer `python scripts/probe_test_selector.py --root <wt> --out reports/selecteur_tests_2026-11-14/runs_df36593f
--workers 16 --cases` (les cas faits sont repris). Le surveillant (%TEMP%\c19_watch.ps1) et le contrôle de 15 min (cron) meurent avec
la session : relancer le surveillant avant la mesure.

**Non commité, à tester puis commiter un par un** (aucun test lancé pendant la mesure) :
1. Chantier 38 : certus/core/certus_design_final_cleanup.py (lbfgsb_polish), certus/ui/certus_design_ui_optimization.py,
   tests/unit/test_design_window_polish_moved_to_core.py. Tester + oracle.
2. Délai UX : tests/ui/_ux_worker.py (timeout_s=600, échec sans nouvel essai). Écrire un test qui échoue sur l'ancien code
   (commande qui dort, timeout_s=1).
3. Chantier 37 : scripts/check_publication.py + tests/unit/test_check_publication.py.
4. Chantier 40 : reports/tmm_tiers_2026-11-15/probe_tmm_tiers.py (tmm 0.2.0 dans %LOCALAPPDATA%\Temp\certus_tmm_tiers) : lancer, bilan.
5. Chantier 41 : reports/dependabot_2026-11-15/bilan.md (reste l'essai pillow 13).
6. Bilan du 19 (REPRISE de reports/selecteur_tests_2026-11-14 §5), puis validation finale validate_parallel --out .../validation_3.
7. Chantier 44 étapes 1-3 (accord de 👤 : enchaîner après la mesure) : sonde de profil du noyau STRAT, V2 puis V1 (c1_diff au bit),
   sonde de sensibilité (probe_modele_lecture.py).
PDF OMS5100_sources_resume.pdf : non commité (générateur %TEMP%\make_oms_pdf.py).

## Reprise après passation (2026-11-15 ~09:10, nouveau compte)

- Mesure du 19 toujours en cours (pid 17436, cas thickness_units) ; surveillant c19_watch vivant (pid 32536) ; le cron de 15 min est mort.
- spectral_width ESCAPED = RÉEL, pas l'artefact modal (lu dans le code + JSON) : échappé `tests/regression/test_convergence_guard.py[SPLINE]`,
  persistant au rejeu série, SPLINE hors STOCHASTIQUES ; le garde lance `test_spline.py` en sous-processus → dépendance à
  `certus/domain/spectral_weights.py` (via certus_index_utils) invisible au graphe d'imports. La boîte modale n'a touché que la durée
  de la sélection (22 081 s), pas la liste des élus (calculée avant). À écrire au bilan du 19 comme trou structurel du sélecteur.
- 09:07 : la sonde du 19 est MORTE au cas thickness_units : palier ui 223 échecs + 61 erreurs (`native abort, exit status 0xc0000142`
  = DLL_INIT_FAILED, plus aucun processus créable), puis rest vide → RuntimeError. Contemporain du changement de compte → artefact
  d'environnement. Arbre mesuré propre (finally). Dossier gardé : runs_df36593f/thickness_units_invalide_0xc0000142_0907/.
- 09:12 : relance `--cases` (5 cas repris), pid 22068 ; surveillant relancé pid 22276 (journal en chemin Windows). Restent
  thickness_units, field_chain, overflow_boundary (~1 h 30). Si une coupure recommence : même relance (cf. PASSATION).
- 09:25 : bilan du 19 ÉBAUCHÉ (reports/selecteur_tests_2026-11-14/bilan.md, 5 cas, 3 « à venir »). Test du délai UX ÉCRIT, NON JOUÉ :
  tests/ui/test_ux_worker_harness.py::test_a_worker_that_never_ends_is_killed_and_fails_without_a_retry (doit échouer sur
  l'ancien _ux_worker.py : `git stash`-free → copier l'ancien via `git show HEAD:tests/ui/_ux_worker.py`).
- 09:15 : 👤 demande de vérifier régulièrement que la sonde vit : Monitor bxblgbxx0 (30 min, à réarmer) signale CASE/COMPARISON/erreurs,
  STALL (rien écrit depuis 25 min) et PROBE_DEAD (pid 22068). Relecture du 38 faite (lecture seule) : floor 0,01 =
  KERNEL_MIN_THICKNESS_NM, cas du candidat élagué équivalent (var_idx = tout), aucun test ne patche le gradient côté fenêtre.
- ~10:15 : thickness_units OK. field_chain ESCAPED, mais probablement artefact : 45 échecs unit > MAX_REPLAY=40 → aucun rejeu ;
  les 2 « échappés » sont des instables connus (slit_profile = chantier 34, ARTEFACT du témoin ; scheduled_task pareto =
  « previous evaluation still running », échoué puis vert au rejeu dans spectral_width). À FAIRE après la mesure : sur l'arbre
  mesuré, injecter la mutation field_chain à la main, jouer ces 2 tests seuls, puis `git checkout -- .`.
- ~10:50 : 👤 « enchaîner le chantier 44 asap » → NOUVEL ORDRE après la mesure : contre-épreuve field_chain (2 tests) → sonde 44
  étape 1 → V2 (commit, c1_diff --corpus strat) → V1 → étape 3 (sensibilité) ; puis le reste de la file (bilan 19, 38, UX, 37...).
  Sonde ÉCRITE, ruff vert, NON LANCÉE : scripts/probe_strat_kernel_profile.py (sortie reports/audit_oms5100_2026-11-15/profil_noyau/).
- overflow_boundary : sélection ARTEFACT (4 échecs verts au rejeu seul, 21 min 35) ; suite complète en cours.
- Risque V2 relevé (lu dans le code) : `_stack_matrix_pair` calcule réel et nominal dans UNE boucle « on purpose: two loops moved
  the last bits ». Sortir le nominal de la boucle MC n'est donc pas « identique par construction » (audit §5) : c1_diff tranche ;
  si des bits bougent, arrêt et écart en ulp (plan §8 2b).
- overflow_boundary : les 4 échecs de la sélection = UX DESIGN instables (verts au rejeu) → la sélection n'a PAS vu la mutation.
- ~10:58 : DÉCISION de 👤 (mot pour mot : « moi je valide, je me fiche d'une precision a 10 -16 !!! ») : pour V1/V2 du 44, un
  écart au dernier bit est ACCEPTÉ. Garde-fou gardé : écart max en ulp + décisions basculées (crash, compte d'extrema, arrêt)
  sur le corpus c1_diff, RAPPORTÉS (non bloquants). Bloquant seulement un écart au-delà du bruit d'arrondi (relatif > 1e-12) :
  signe de bug, pas d'arrondi. Changement de bits = un commit à part, raison dans ETAT.md, nouvelle référence c1_diff.
- 11:05 : MESURE DU 19 FINIE. OK : infrared_center, empty_phase_a, qwot_signal_state, angle_boundary, thickness_units.
  ESCAPED : spectral_width (RÉEL, garde SPLINE en sous-processus), field_chain (ARTEFACT prouvé : sur l'arbre muté, 43 échecs
  field_peak et les 2 « échappés » VERTS seuls, ~11:06 ; arbre restauré), overflow_boundary (survivant connu : seul échoue le garde
  de la base de mutation, la sélection n'avait que 4 UX DESIGN instables). Surveillant fini avec la sonde.
- ~11:07 : sonde 44 étape 1 LANCÉE → reports/audit_oms5100_2026-11-15/profil_noyau/{console.txt,profil.json}.
- 0173ce8b : bilan du 19 commité (bilan.md + runs). Reste du 19 : CHANTIERS_RESTANTS (retirer 07, ligne 19), ETAT §0.
- 4e62c1bf : 44 étape 1 commitée (profil : matrices ~60 % dès la couche 24 ; batch 8,27 µs/appel sur 1 fil).
- 38ee417b : le batch de production entre au corpus C1 (strat.batch, 16 cas, VERSION_CORPUS 4). Auto-contrôle HEAD contre HEAD
  lancé (sortie portage_matrices/c1_corpus_auto.txt).
- ~11:15 : PORTAGE DES MATRICES ÉCRIT, NON TESTÉ, NON COMMITÉ : `stack_mats` (noyau, None = avant) et `stack_carry` (batch,
  False = avant) ; nominal par couche hors des tirages, réel porté dans le bloc (`_advance_matrix`). Suite : c1_diff HEAD
  --corpus strat (doit être identique), oracle, commit ; puis compare_carry.py (écart + gain), activer dans
  certus_strat_robustness_task.py:531, commit à part.
- c96a570a (test du corpus C1 : strat.batch attendu), df090075 (PORTAGE DES MATRICES COMMITÉ, inactif : c1 tenu 2583/2583,
  oracle 1209, tests strat 1799 verts). MESURÉ sur plan ELITE réel (48c_premium_s42 jobs[0], 0 % crash) : x1,02 à x1,15
  seulement ; écart ≤ 6,6e-12 relatif, 0 décision basculée. Le « 60 % matrices » de l'étape 1 était un majorant (postes isolés).
  Plan synthétique 550/600 : 100 % crash, gain x1,45 artefact (sin/cos d'épaisseurs sentinelles énormes). NON ACTIVÉ en production.
- ~12:05 : profil d'une recherche STRAT complète lancé (bench_examples.py strat --auto-yes --sample) →
  reports/audit_oms5100_2026-11-15/profil_strat_complet/ ; ~26 min. Décider ensuite quoi accélérer.
- Capture DESIGN : reports/captures_2026-11-15/certus_design.png (hors écran : QT_QPA_FONTDIR=C:/Windows/Fonts obligatoire).
- 12:13 : CHANTIERS_RESTANTS mis à jour (ordre validé par 👤 : 44, 38, 37, 40, 34 ; 24/31 en session dédiée ; 07 retiré), contrôles doc à 0.
- 12:18 : PROFIL STRAT COMPLET (avant) : RUN_S=1338.759, RESULT=0.005861922892702524 (profil_strat_complet/bench.txt).
  Phases : A 2 min 47 (12 %), phase 3 10 min 30 (47 %), recherche locale 9 min (40 %). Calcul : croissance 39 %, score
  (compute_batch_rmse) 38 %, matrices phase A 14 %, RT nominal 8 % ; consensus ≈ 35 % de la robustesse.
- Levier trouvé : parallélisme imbriqué (8 fils Python × 16 fils OMP). probe_threads.py : 2 fils internes ×1,1 à ×1,6, bits
  identiques. ÉCRIT, NON COMMITÉ : certus_core.numba_thread_pool + pools de certus_strat_robustness (3) et
  certus_strat_consensus (3). ~12:35 : recherche STRAT complète relancée (bench_pools.txt) : RESULT doit être identique au bit.
- 12:37 : 👤 « suivons les recommandations » (1 fils par pool, 2 TBB, 3 algorithmique ; consensus = décision de 👤 sur chiffres).
  tbb 2023.2.0 installé (pip, wheel PyPI) dans Python315 ; DLL dans Python315\Library\bin, hors du chemin : il faut
  os.add_dll_directory + PATH avant numba (fait dans probe_threads.py si NUMBA_THREADING_LAYER=tbb). À lancer APRÈS la
  recherche de contrôle : NUMBA_THREADING_LAYER=tbb python .../probe_threads.py --tasks 128 --inner 16,2,16,2.
- Préfixe en recherche locale (lu) : un candidat qui change la couche i laisse les couches < i identiques au bit (C2, blocs
  causaux) → réutiliser la croissance du plan courant. Gain estimé ~10 % du total (croissance ≈ moitié de la recherche locale).
- 12:53 : RÉGLAGE DES POOLS RETIRÉ (git checkout des 3 fichiers). Recherche de contrôle : RUN_S=1783 (contre 1339), classement
  identique, RESULT …702714 (= audit du 10/11 ; la 1re de ce matin …702524 : variation d'une recherche à l'autre, chantier 34).
  Cause : 2 tâches → 2 fils Numba chacune au lieu de 16 (étape 48 blocs 25 s → 5 min 56) ; à 240 tâches aucun gain (blocs 9→5).
  Phase A non touchée : 2 min 47 → 3 min 34 : bruit machine ~25 %, une recherche seule ne mesure pas 10 %.
- 12:55 : TBB : sonde 128 tâches tbb 1,55-1,66 s contre omp 1,74-2,02 s ; empreinte sha256 IDENTIQUE omp/tbb (fcca8d613b8db8e0).
  Recherche STRAT complète sous TBB lancée (bench_tbb.txt, console_tbb.txt ; DLL ajoutées par runpy). Comparer à 1339 s (omp).
  Production : CERTUS force omp seulement si NUMBA_THREADING_LAYER est absent (certus_core) ; tbb n'est pas dans requirements.lock.
- 13:13 : RECHERCHE STRAT SOUS TBB : RUN_S=1074 (omp : 1339), classement identique, RESULT …702511 (variation chantier 34).
  Phases : A 23 s (omp 2 min 47 / 3 min 34) ; bloc 48 18 s (25 s) ; blocs 9→5 55 s/bloc (73 s) ; recherche locale ~9 min 27
  (9 min 00 : pas de gain, une stratégie à la fois). → TBB proposé à 👤 : dépendance tbb (requirements.lock), add_dll_directory
  dans certus_core, défaut tbb si présent sinon omp, exécutable gelé (39). Décision de 👤 attendue.
- 13:20 : 👤 « Oui, adopter TBB ». ÉCRIT, NON COMMITÉ : certus_core.numba_threading_layer (« threadsafe » + add_dll_directory
  de <prefix>/Library/bin ou _MEIPASS), 3 endroits « omp » remplacés ; tbb>=2023.2.0 (win32) dans pyproject/uv.lock/
  requirements.lock (+ tcmlib 1.6.0, installé) ; certus_hub.spec embarque tbb12/tbbmalloc/tcm/libhwloc ; test_certus_core
  attend « threadsafe ». Vérifié : processus neuf → couche tbb, 15 fils. En cours : ouvrier c1 omp contre tbb à froid
  (%TEMP%\c1_couches_HHMM) ; NE PAS toucher certus/ pendant. Puis tests ciblés, oracle, commit, ETAT.
- 13:45 : TBB généralisé = TBB POUR STRAT SEUL. Mesuré : TBB non déterministe pour coût/gradient DESIGN (53/2985 d'un lancement
  TBB à l'autre ; OpenMP 0/2985) ; STRAT/oblique/appelants 0/6187. Commits 0cab1afc (STRAT sur TBB : STRAT_THREADING_LAYER,
  register_tbb_runtime, tbb dans les dépendances, spec ; test_strat_runs_on_tbb rouge sur l'ancien code) et suivant (bilan,
  ETAT, chantiers). Oracle 1209, 519 tests ciblés, ruff et doc à 0.
- 14:14 : 👤 « Oui, mesurer » INDEX et RE sous TBB : bench_examples index/re × omp/tbb en série → reports/audit_oms5100_2026-11-15/tbb_index_re/. Couche explicite (NUMBA_THREADING_LAYER) : pas de repli silencieux.
- 14:21 : INDEX/RE sous TBB mesurés et commités : RE −38 % (×1,6), INDEX sans gain. Adoption pour RE = décision de 👤.
- 14:30 : 👤 « Oui, RE sur TBB » : commit 5a3b0171 (TBB_THREADING_LAYER, CERTUS_RE.py ; tests 1342 + oracle 1209 + ruff + doc verts).
- 14:40 : 👤 « oui un audit complet stp ». reports/audit_code_2026-11-15/ : metriques.py + metriques.json FAITS (4 720 fonctions,
  médiane 14 l, p90 83, max 804 ; 355 > 100 l ; 137 > 10 args ; inversions utils→ui 8, workers→ui 1, physics→core 2).
  Revue qualitative par lots, agents UN À LA FOIS (AGENTS.md) : lot1 physique+domaine+metal LANCÉ (sortie lot1_physique_domaine.md),
  puis lot2 core, lot3 spline+workers, lot4 utils+racine, lot5/6 ui (deux moitiés), puis bilan.md consolidé avec notes.
- 14:51 : lot1 FINI (lot1_physique_domaine.md : 0 critique, 1 majeur VÉRIFIÉ par moi — epsilon1_TL_analytic plafonne ε1 à 1 (max(val, 1.0)), pas le gradient — 6 mineurs). lot2 core LANCÉ.
- 14:55 : validation_3 palier unit FAIL, 3 persistants : (1) fichiers_longs : certus_strat_growth.py 1825→1840 (portage
  df090075) → REVERT du portage (inactif, gain 2-15 %) ; (2) licence tbb = « Intel Simplified Software License /
  Proprietary » interdite par test_the_project_is_licensed_under_the_gpl → tbb OPTIONNEL : retirer de pyproject/uv.lock/
  requirements.lock et du spec ; le code garde register_tbb_runtime (TBB si installé, sinon omp) ; oneTBB Apache-2.0
  (conda-forge) pour l'exe = décision de 👤 ; (3) REGLES_reference.md 8977 > 8600 octets (b281ec95, chantier 42) → condenser.
  À faire APRÈS la fin de validation_3 (elle lit l'arbre).
- 15:01 : 3 correctifs commités : ac1a639c (revert portage), 002146a7 (TBB optionnel, licence Intel), 3374b380 (REGLES ≤ 8600). Les 3 gardes passent ; validation_4 lancée.
- 15:03 : lot2 core FINI (lot2_core.md : 0 critique, 1 majeur VÉRIFIÉ par moi — consensus : _store_and_consume_consensus_score n'ajoute que les scores finis, une graine rejetée disparaît de mean/std/worst ; 6 mineurs ; notes exact 6 tests 7 archi 5 lisib 5 robust 6 perf 7 repro 8). lot3 spline+workers LANCÉ.
- 15:18 : lot3 spline+workers FINI (lot3_spline_workers.md : 1 CRITIQUE VÉRIFIÉ par moi — spline_objective._njit_single_layer_mse_fused en mode ratio divise T mais compare R mesuré (ratio) à R théorique absolu, alors que le code corridor utilise _reflectance_ratio_theoretical_from_nk ; 3 majeurs ; 7 mineurs ; notes 5/4/4/4/4/6/6). lot4 utils+entrées LANCÉ.
- 15:21 : 👤 demande une DOUBLE VÉRIFICATION des critiques et majeurs : (1) relevé du lot, (2) ma lecture, (3) agent contre-vérificateur indépendant (emplacement + question neutre, sans la conclusion), (4) preuve par la mesure si possible (servira de test rouge). Verdict CONFIRMÉ / PLAUSIBLE / RÉFUTÉ au bilan. Après les lots, un agent à la fois.
- 15:29 : validation_4 = VALIDATION=GO sur 3374b380 (+ 38, UX, 37 non commités à ce moment). Puis commits b679e5d9 (délai UX,
  test rouge sur l'ancien harnais prouvé), b0c87ee5 (38), 5968e733 (37 ; PUBLICATION=GO sur 134 commits). À faire : ETAT §0
  (dernière validation), CHANTIERS (37, 38 sortent).
- 15:34 : lot4 FINI (1 critique, 4 majeurs, 7 mineurs). C1 lot4 CONFIRMÉ PAR MESURE : substrat 'SiO2' de STRAT = 1,48625 à 550 nm (mélange de couches via MergedMaterialDict.__contains__ approximatif) au lieu du Sellmeier 1,45991 (preuves/p_substrat_sio2.*). 38, UX, 37 commités ; validation_4 GO.
- 15:57 : lot5 ui_a FINI (0 crit, 7 maj). Preuves faites (preuves/) : C-L3, M-L1, M-L2, M-L3a, M-L4a/b/c CONFIRMÉS par mesure ; M-L5c mécanisme. lot6 ui_b en cours. Suivant : contre-vérificateur(s) sur les non mesurés + lot6.
- 16:33 : session précédente coupée (limite 5 h de l'API) ; agent lot6 ui_b mort SANS sortie. Reprise par la session du worktree claude-code-question-0aa978, qui travaille ICI (chemins absolus) ; ne pas relancer l'ancienne session en parallèle. Suivant : relancer lot6 (69 fichiers, 39 029 l, de certus_index_ui_workers* à mixins/), puis contre-vérificateur sur les « à faire » de a_verifier.md, puis bilan.md.
- 16:35 : l'app interdit d'écrire dans un autre worktree → la COPIE ACTIVE de l'audit est désormais dans le worktree claude-code-question-0aa978 (branche avancée en ff sur e8d1147f ; audit_code_2026-11-15/ et ce REPRISE copiés). Celle de suije est figée (sa ligne 16:33 est périmée). Preflight STOP ici : ruff I001 sur preuves/p_spline_ratio_R.py (ordre d'imports) → corrigé à la main, sortie de la preuve identique, PREFLIGHT=GO. M-L3b CONFIRMÉ par mesure (preuves/p_generic_worker_signaux.*). lot6 relancé (sortie lot6_ui_b.md ici). Suivant : ma lecture M-L3c, puis contre-vérificateur, puis bilan.md.
- 16:37 : M-L3c mécanisme confirmé en lecture (effet sur corridor non mesuré). M-L5g CONFIRMÉ par mesure (preuves/p_epaisseur_fft_indice.* : SiO2/Si → bornes excluent la vraie épaisseur). lot6 toujours en cours. Suivant : M-L5a (appel), puis contre-vérificateur sur M-L4d, M-L5b..f + majeurs du lot6.
- 16:38 : M-L5a CONFIRMÉ par mesure (preuves/p_ksub_desaligne.* : max |ΔT| 0,50). Suivant : attendre lot6, puis contre-vérificateur (M-L4d, M-L5b..f + majeurs lot6), puis bilan.md.
- 16:40 : ma lecture : M-L5d CONFIRMÉ (lecture), M-L5c mécanisme confirmé, chemin non mesuré. lot6 toujours en cours (agent en arrière-plan, sortie lot6_ui_b.md ICI). Restent au contre-vérificateur : M-L4d, M-L5b, M-L5c (chemin), M-L5e, M-L5f + majeurs lot6.
- 16:42 : DÉCISIONS de 👤 pour les corrections (APRÈS le bilan, ordre critiques → majeurs physiques → majeurs UI, un commit chacune, test rouge d'abord) : (1) substrat « SiO2 » de STRAT → Sellmeier partout, recenser les mesures/rapports invalidés dans docs/ETAT_acquis.md, remesurer la référence du juge de paix ; (2) consensus STRAT : une graine rejetée → score infini, stratégie rejetée ; (3) FFT INDEX : diviser par le n initial du film (550 nm), bornes [0,5 ; 2] d̂ inchangées.
