import os

replacements = {
    'tests/performance/test_re_headless_audit.py': [
        ("""sur le binaire ou python -m CERTUS_RE avec scénario utilisateur.""", """on the binary or python -m CERTUS_RE with user scenario.""")
    ],
    'tests/performance/test_strat_mc_synthetic_audit.py': [
        ("""Ne lance pas la GUI STRAT ni la DB ; utile pour suivre pic tracemalloc et coût GC.""", """Does not launch STRAT GUI or DB; useful to track tracemalloc peak and GC cost.""")
    ],
    'tests/property/test_energy_conservation.py': [
        ("""compute_TMM_generic doit donner R+T <= 1 for tout empilement.""", """compute_TMM_generic must yield R+T <= 1 for any stack."""),
        ("""compute_TMM_single_point_k0 doit donner R+T <= 1.""", """compute_TMM_single_point_k0 must yield R+T <= 1."""),
        ("""Pour un empilement sans absorption, R + T = 1 exactement.""", """For a stack without absorption, R + T = 1 exactly."""),
        ("""RÉGRESSION: la formule T doit donner R+T=1 for k=0.""", """REGRESSION: the T formula must yield R+T=1 for k=0.""")
    ],
    'tests/property/test_physics_invariants.py': [
        ("""correct pour des substrats absorbants). Passer un complex à la version float""", """correct for absorbing substrates). Passing a complex to the float version"""),
        ("""Fonctionnellement identique pour ces tests de propriétés.""", """Functionally identical for these property tests."""),
        ("""Voir docstring du module pour la justification.""", """See module docstring for justification.""")
    ],
    'tests/regression/README_REGRESSION_TESTS.md': [
        ("""Ce dossier contient la suite de tests de convergence et de non-régression de l'application CERTUS.""", """This folder contains the convergence and non-regression test suite of the CERTUS application."""),
        ("""Pour empêcher cela, nous avons extrait la meilleure erreur RMSE obtenue sur une série d'exemples robustes (les Golden Masters) conservés dans le fichier""", """To prevent this, we extracted the best RMSE error obtained on a series of robust examples (Golden Masters) stored in the file""")
    ],
    'tests/ui/test_spectrum_persistence_qsettings.py': [
        ("""Contrat QSettings pour la persistance session (INDEX SPLINE étape 3, INDEX classique wT/wR).""", """QSettings contract for session persistence (INDEX SPLINE step 3, classic INDEX wT/wR)."""),
        ("""Utilise un répertoire INI isolé (tmp_path) pour ne pas polluer le registre utilisateur.""", """Uses an isolated INI directory (tmp_path) to avoid polluting the user registry.""")
    ],
    'tests/unit/test_certus_core.py': [
        ("""Test get_resource_path for un fichier existant.""", """Test get_resource_path for an existing file."""),
        ("""Test get_resource_path for un fichier inexistant.""", """Test get_resource_path for a non-existent file."""),
        ("""Test la configuration du logging avec fichier.""", """Test logging configuration with a file."""),
        ("""Verify that le fichier contient des logs""", """Verify that the file contains logs"""),
        ("""Test avec un chemin invalide""", """Test with an invalid path"""),
        ("""Devrait continuer avec console logging uniquement""", """Should continue with console logging only"""),
        ("""Tests for la fonction bootstrap_app.""", """Tests for the bootstrap_app function."""),
        ("""Utiliser un fichier temporaire comme "app_file\"""", """Use a temporary file as "app_file\""""),
        ("""Test bootstrap_app avec nom de log.""", """Test bootstrap_app with log name."""),
        ("""Test avec une configuration invalide""", """Test with an invalid configuration"""),
        ("""Ne devrait pas lever d'exception""", """Should not raise an exception""")
    ],
    'tests/unit/test_certus_hub.py': [
        ("""Simuler l'appel dans le module""", """Simulate the call in the module"""),
        ("""Test avec un chemin relatif""", """Test with a relative path""")
    ],
    'tests/unit/test_certus_index_smoke.py': [
        ("""On importe le module principal pour vérifier que c'est une façade valide (ou le fichier original)""", """Import the main module to verify it is a valid facade (or the original file)""")
    ],
    'tests/unit/test_certus_measurement_excel_ui.py': [
        ("""Tests unitaires : choix de feuille « measurement » (sans dialogue fichier).""", """Unit tests: choice of "measurement" sheet (without file dialog).""")
    ],
    'tests/unit/test_certus_modules.py': [
        ("""Test la gestion d'errors dans les modules.""", """Test error handling in modules.""")
    ],
    'tests/unit/test_certus_reset_framework.py': [
        ("""Fabrique une fausse app pour les tests du manager.""", """Creates a fake app for manager tests."""),
        ("""Tests pour CertusResetManager.""", """Tests for CertusResetManager."""),
        ("""Tests pour create_reset_button.""", """Tests for create_reset_button.""")
    ],
    'tests/unit/test_certus_re_worker_utils.py': [
        ("""Tests pour certus_re_worker_utils (sans Qt).""", """Tests for certus_re_worker_utils (without Qt).""")
    ],
    'tests/unit/test_certus_services.py': [
        ("""Aucun service headless détecté dans certus_services""", """No headless service detected in certus_services"""),
        ("""Signature fit invalide pour""", """Invalid fit signature for""")
    ],
    'tests/unit/test_certus_strat_coherence.py': [
        ("""Validation des metriques theoriques par couche (sans bruit).""", """Validation of theoretical metrics per layer (without noise).""")
    ],
    'tests/unit/test_certus_strat_rmse_export.py': [
        ("""Une RMSE de 0.0 est physiquement impossible pour un signal de dépôt réel bruité""", """An RMSE of 0.0 is physically impossible for a real noisy deposition signal""")
    ],
    'tests/unit/test_certus_substrate_index.py': [
        ("""openpyxl requis pour lire sapphirenu.xlsx""", """openpyxl required to read sapphirenu.xlsx"""),
        ("""Fichier example manquant :""", """Missing example file :"""),
        ("""Colonne lambda invalide dans sapphirenu.xlsx""", """Invalid lambda column in sapphirenu.xlsx"""),
        ("""2. sqrt(max(n², 1e-9)) avec n² négatif : n ~ 3e-5 -> hors bande d’acceptation sur n.""", """2. sqrt(max(n², 1e-9)) with negative n²: n ~ 3e-5 -> outside n acceptance band."""),
        ("""Li < lambda_min(fit) requis pour lambda²-Li²>0 sur la fenêtre""", """Li < lambda_min(fit) required for lambda²-Li²>0 on the window""")
    ],
    'tests/unit/test_data_th_clipboard.py': [
        ("""1. TOUJOURS appeler  cb.clear()  AVANT d'écrire dans le clipboard,""", """1. ALWAYS call cb.clear() BEFORE writing to the clipboard,"""),
        ("""pour éviter les résidus d'un test antérieur.""", """to avoid residues from a previous test."""),
        ("""3. Ne pas dépendre de l'ORDRE d'exécution des tests pour ce test.""", """3. Do not depend on test execution ORDER for this test.""")
    ],
    'tests/unit/test_guide_consistency.py': [
        ("""Attention : Incident = Sub, Sortie = Air""", """Warning: Incident = Sub, Exit = Air"""),
        ("""Comparison avec Guide Valeurs Reference""", """Comparison with Guide Reference Values""")
    ],
    'tests/unit/test_gui_smoke.py': [
        ("""pour tester les imports GUI sans déclencher la compilation JIT (qui peut""", """to test GUI imports without triggering JIT compilation (which can"""),
        ("""module — cela contamine TOUS les tests suivants dans le processus,""", """module — this contaminates ALL subsequent tests in the process,"""),
        ("""3. Si un nouveau test de ce fichier échoue de manière non déterministe""", """3. If a new test in this file fails non-deterministically"""),
        ("""avec des erreurs Numba : vérifier si un autre module a importé""", """with Numba errors: check if another module imported"""),
        ("""Voir docstring du module pour les raisons.""", """See module docstring for reasons.""")
    ],
    'tests/unit/test_physics_cost_smoke.py': [
        ("""Cinq points valides, erreur^2=1 chacun ; seul poids nul en i1.""", """Five valid points, error^2=1 each; only zero weight at i1.""")
    ],
    'tests/unit/test_physics_fresnel.py': [
        ("""Les kernels Numba compilés avec  fastmath=True  ne garantissent PAS la""", """Numba kernels compiled with fastmath=True do NOT guarantee"""),
        ("""accepte donc SOIT NaN SOIT une valeur finie pour n_film=0.""", """therefore accepts EITHER NaN OR a finite value for n_film=0.""")
    ],
    'tests/unit/test_strict_material_substrate_boundary.py': [
        ("""Test écrit pour une ancienne API (substrate_data, get_material_index) absente de RobustMaterialDatabase — à réécrire""", """Test written for an old API (substrate_data, get_material_index) absent from RobustMaterialDatabase — to rewrite""")
    ],
    'tests/unit/test_tmm_inline.py': [
        ("""voir détails ci-dessus""", """see details above""")
    ]
}

for filepath, pairs in replacements.items():
    full_path = os.path.join('d:/1406/1406', filepath)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        for fr, en in pairs:
            if fr in content:
                content = content.replace(fr, en)
                modified = True
            else:
                pass # print(f"Warning: could not find in {filepath}")
        
        if modified:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {filepath}")
