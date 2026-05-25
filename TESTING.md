# Guide de Validation et de Test (CERTUS)

Ce document décrit comment exécuter et exploiter la suite complète de tests de CERTUS de manière professionnelle et standardisée.

---

## 1. Démarrage Rapide

Un script orchestrateur unique centralise toutes les phases de tests. Vous pouvez le lancer à la racine du projet :

```bash
# Lancer l'intégralité des tests (unitaire + intégration + exemples headless + tests de fumée GUI)
python scripts/run_certus_tests.py
```

---

## 2. Options de l'Orchestrateur (CLI)

Le script de test propose des options pour cibler une phase spécifique ou générer des rapports de couverture :

```bash
# 1. Lancer uniquement la suite de tests Pytest (unitaires & intégration)
python scripts/run_certus_tests.py --pytest-only

# 2. Lancer uniquement la validation des exemples en mode headless
python scripts/run_certus_tests.py --headless-only

# 3. Lancer uniquement les tests de fumée des interfaces graphiques (GUI)
python scripts/run_certus_tests.py --gui-only

# 4. Forcer la génération et vérification des rapports de couverture de code
python scripts/run_certus_tests.py --pytest-only --coverage

# 5. Autoriser l'ouverture des fenêtres GUI (désactive le mode offscreen par défaut)
python scripts/run_certus_tests.py --gui-only --allow-gui
```

---

## 3. Gestion des Dépendances & Compatibilité Système

L'environnement Python de l'hôte (notamment sous Python 3.14.5+) peut manquer de certaines extensions C système standard (comme `_overlapped`, `_multiprocessing`, ou `select`). 

Pour que la suite de tests reste **totalement portable et indépendante**, un injecteur de mocks automatiques a été intégré :
- Le dossier `scripts/inject` contient un script [sitecustomize.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/1705/scripts/inject/sitecustomize.py).
- L'orchestrateur ajoute automatiquement ce dossier au `PYTHONPATH` de chaque processus de test lancé.
- Ce mécanisme simule les modules manquants, gère de façon transparente les context managers (comme les verrous de compilation parallèle de Numba) et permet l'exécution de 100% des tests unitaire et d'intégration sans aucune modification du code source.

---

## 4. Rapports et Résultats

À chaque exécution de l'orchestrateur :
1. **Rapport Console :** Un tableau de synthèse lisible indique le statut (PASSED/FAILED) et le temps d'exécution exact de chaque phase.
2. **Rapport Structuré JSON :** Un fichier complet de métadonnées est sauvegardé dans [logs/test_report.json](file:///c:/driveFL/couches%20minces%202026/CERTUS/1705/logs/test_report.json). Il est idéal pour le suivi d'intégration continue (CI/CD) :
   ```json
   {
     "timestamp": "2026-05-23T18:41:39Z",
     "global_success": true,
     "environment": {
       "os": "Windows",
       "python_version": "3.14.5"
     },
     "phases": [
       { "name": "Pytest Suite", "success": true, "exit_code": 0, "duration_s": 73.64 }
     ]
   }
   ```
3. **Couverture Pytest :** Si l'option `--coverage` ou `--pytest-only` est utilisée, un rapport détaillé HTML est généré dans le répertoire `htmlcov/` et un rapport XML dans `coverage.xml`.
