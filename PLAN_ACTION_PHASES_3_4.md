# CERTUS - Plan d Action Phases 3 et 4
## Extension du Plan Prochaine Session

Date: 2026-07-08
Complement de: PLAN_ACTION_PROCHAINE_SESSION.md
Duree phases 3+4: 50-70h

---

## PHASE 3: VALIDATION SECURITE ENTREES (30-40h)

Objectif: P0 #2 - Securiser toutes les entrees utilisateur

### Tache 3.1: Creer module validation (8-10h)
- Fichier: certus/utils/certus_validation.py
- Classes: PathValidator, NumericValidator, StringValidator
- Protection contre: path traversal, injections, overflow

### Tache 3.2: Integrer validation dans UI (15-20h)
- 5 file dialogs (export/import)
- 8 numeric inputs (wavelength, thickness)
- 3 text inputs (names, comments)

### Tache 3.3: Tests securite (5-8h)
- 30+ tests attaque
- Path traversal, overflow, injection

### Tache 3.4: Audit et commit (2-4h)

Impact: Score Securite 7.0 -> 9.0 (+2.0)

---

## PHASE 4: AUDIT EXCEPTIONS (20-30h)

Objectif: Ameliorer 1379 try/except blocks

### Tache 4.1: Analyse automatique (5-7h)
- Script analyze_exceptions.py
- Detection bare except, silent pass

### Tache 4.2: Corriger HIGH priority (10-15h)
- 47 bare except
- 52 silent pass critiques

### Tache 4.3: Guidelines et commit (5-8h)
- Documentation EXCEPTION_HANDLING_GUIDELINES.md

Impact: Score Maintenabilite 7.5 -> 8.5 (+1.0)

---

## METRIQUES PHASES 1-4

Score Architecture:      7.0 -> 7.4 (+0.4)
Score Performance:       8.0 -> 8.3 (+0.3)
Score Securite:          7.0 -> 9.0 (+2.0)
Score Maintenabilite:    7.5 -> 8.5 (+1.0)
Score Global:            7.2 -> 8.3 (+1.1)

Temps total phases 1-4:  77-108h

---

PLANNING INTEGRE:
- Semaines 1-2: Phases 1+2 (27-38h)
- Semaines 3-5: Phase 3 (30-40h)
- Semaines 6-8: Phase 4 (20-30h)

Total: 10-14 jours travail effectif
