# Audit CERTUS par fichier — note sur 100

## Méthode
Notation orientée maintenance et robustesse, sur 5 axes :
- **Architecture / séparation des responsabilités**
- **Lisibilité / taille / complexité**
- **Robustesse / gestion d’erreurs**
- **Testabilité / isolation**
- **Risque de régression**

> Plus la note est basse, plus le fichier mérite une action rapide.

---

## Tableau de synthèse

| Fichier | Note /100 | Verdict |
|---|---:|---|
| `certus_core.py` | 74 | Bon socle, à verrouiller |
| `certus_ui.py` | 48 | Trop de responsabilités UI |
| `CERTUS_HUB.py` | 52 | Orchestrateur trop central |
| `CERTUS_INDEX.py` | 55 | Fonctionnel mais encore fragile |
| `CERTUS_INDEX_SPLINE.py` | 28 | Priorité critique |
| `CERTUS_STRAT.py` | 34 | Priorité critique |
| `CERTUS_RE.py` | 41 | Gros chantier |
| `CERTUS_DESIGN.py` | 43 | Gros chantier |
| `CERTUS_METAL_SINGLE.py` | 63 | Domaine clair, à factoriser |
| `CERTUS_METAL_BILAYER.py` | 61 | Domaine clair, à factoriser |
| `certus_services.py` | 67 | Bon potentiel, à découper |
| `certus_strat_context.py` | 78 | Très bon candidat à la structuration |
| `certus_strat_service.py` | 62 | Utile mais à formaliser |
| `certus_re_helpers.py` | 68 | Helpers utiles, à cadrer |
| `certus_re_workers.py` | 47 | Complexité élevée |
| `certus_spectral_workers.py` | 58 | Correct mais à clarifier |
| `certus_design_worker_utils.py` | 66 | Petit socle, bien contrôler |
| `certus_design_workers.py` | 57 | Asynchrone utile mais dense |
| `certus_index_utils.py` | 69 | Bon socle utilitaire |
| `certus_shortcuts_overlay.py` | 76 | UX utile, faible risque |
| `certus_skeleton.py` | 70 | Base d’exemple, à garder propre |
| `certus_toast_stack.py` | 73 | Bon composant UX |
| `certus_splash.py` | 80 | Petit module, bon niveau |
| `certus_spline_report.py` | 64 | Reporting à unifier |
| `tools/release_checks.py` | 81 | Bon outillage |
| `scripts/smoke/run_examples_headless.py` | 79 | Très utile pour les smoke tests |
| `tests/unit/test_certus_core.py` | 84 | Très bon rôle de garde-fou |
| `tests/unit/test_certus_index.py` | 82 | Très important |
| `tests/unit/test_certus_strat_service.py` | 85 | Très important |
| `tests/integration/test_example_pipelines.py` | 78 | Bon filet de sécurité |

---

## Lecture des scores

### 85–100 : excellent / très sain
- Peu urgent.
- À conserver comme référence.
- Améliorer surtout la documentation ou la couverture des cas limites.

### 70–84 : bon / à surveiller
- Base saine.
- Les améliorations sont surtout de la consolidation.

### 55–69 : moyen / structuration utile
- Le fichier fonctionne, mais il mérite un découpage ou des clarifications.
- Le gain principal vient de la lisibilité et de la testabilité.

### 40–54 : fragile
- Le fichier est encore exploitable, mais il concentre du risque.
- Refactor recommandé à court terme.

### < 40 : critique
- Candidat prioritaire de refactor.
- Risque élevé de régression et de dette technique.

---

## Top priorités

1. `CERTUS_INDEX_SPLINE.py` — **28/100**
2. `CERTUS_STRAT.py` — **34/100**
3. `CERTUS_RE.py` — **41/100**
4. `CERTUS_DESIGN.py` — **43/100**
5. `certus_re_workers.py` — **47/100**
6. `certus_ui.py` — **48/100**
7. `CERTUS_HUB.py` — **52/100**
8. `CERTUS_INDEX.py` — **55/100**

---

## Comment interpréter ces notes

Les fichiers les mieux notés ne sont pas forcément les plus “petits”, mais ceux qui ont :
- un périmètre clair,
- peu de logique cachée,
- une responsabilité unique,
- et une structure qui permet de les tester sans toute l’application.

Les fichiers les plus faibles sont ceux qui cumulent :
- orchestration,
- calcul,
- UI,
- export,
- gestion d’erreurs,
- et état global.
