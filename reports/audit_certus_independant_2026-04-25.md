# Audit CERTUS — Suivi opérationnel (reste à faire)

Version : 2026-04-25 (mise à jour continue)  
Périmètre : uniquement les sujets encore ouverts, non stabilisés, ou non couverts de bout en bout.

---

## 1. Objectif de ce document

Suivre les chantiers encore nécessaires pour atteindre un niveau **release-control métrologique**.  
Les sujets clos, stables et vérifiés ne sont plus détaillés ici.

---

## 2. Priorités ouvertes (ordre d’exécution recommandé)

1. **Traçabilité manifeste à 100% des exports**
  - État : partiellement généralisé, pas encore verrouillé sur tous les chemins secondaires.
  - À faire :**checks métier complémentaires**
    - imposer un point d’entrée unique pour injecter le manifeste,
    - couvrir les exports utilitaires et scripts annexes.
2. **Seed global garanti sur tous les flux stochastiques**
  - État : contrat CI seed généralisé à l’ensemble des modules de production (`CERTUS_*.py`, `certus_*.py`, `_certus_physics_impl.py`) ; base fermée.
  - À faire :
    - maintenir ce garde-fou lors de l’ajout de nouveaux modules/fichiers.
3. **Services headless par domaine (compléter la famille)**
  - État : services dédiés SUBSTRATE et RE branchés + contrat public harmonisé verrouillé par test automatique pour tout futur `*Service`.
  - À faire :
    - maintenir ce garde-fou à chaque nouveau service domaine ajouté.
4. **RE : désenclavement architecture**
  - État : désenclavement progressif en place (builder de payload + orchestration phases via contrats `REPhaseStep` + extraction d’état phase 2 dans `REPhaseStateService`), monolithe encore majoritaire.
  - À faire :
    - étendre le rôle de `REResultsBuilder` (construction structurée intermédiaire, pas seulement payload final),
    - approfondir l’isolation des phases worker avec services de phase dédiés (logique métier extraite hors worker).
5. **STRAT : hardening release**
  - État : partiellement préparé, non fermé.
  - À faire :
    - `P1-8` validation payload JSON,
    - `P1-9` indexation entière des longueurs d’onde,
    - `P1-10` ranking strictement déterministe + tests CI bloquants.
6. **Packaging/CI Windows industrialisé**
   - État : base industrialisée + contrôles release structurels et sémantiques en place (cohérence lockfile/pyproject, lock strictement figé, workflow attendu, smoke offscreen, spec/assets, garde artefact frozen + startup check + validation PE).
  - À faire :
    - ajouter les checks métier complémentaires de release (contenu fonctionnel/sémantique des artefacts).
7. **Incertitudes transverses (suite complète)**
  - État : avancé surtout en SPLINE.
  - À faire :
    - introduire `UncertaintyBudget` commun,
    - expliciter systématiquement « incertitude non calculée » quand applicable.
8. **Contrôle docs↔code global**
  - État : base API sécurisée, couverture documentaire partielle.
  - À faire :
    - étendre les tests d’alignement (MODULE_ID, versions, claims, pages release),
    - échouer en CI si divergence document/code.

---

## 3. Registre des risques actifs

1. **Risque de divergence de comportement entre chemins export**
  - Impact : rapports incomplets / non comparables.
  - Mitigation : API manifeste unique + tests snapshot des feuilles export.
2. **Risque de non-rejeu sur scénarios stochastiques complexes**
  - Impact : non-reproductibilité en audit.
  - Mitigation : seed contract test + logs de seed/run_id obligatoires.
3. **Risque de régression silencieuse en modules monolithiques**
  - Impact : défaut détecté tardivement en production.
  - Mitigation : jeux de référence par module + smoke release en gate CI.
4. **Risque d’hétérogénéité UX entre applications**
  - Impact : opérateur perd en lisibilité/fiabilité.
  - Mitigation : standardiser dashboard/stepper/status + checklists UI.

---

## 4. Plan de fermeture (jalons)

1. **Jalon A — Métrologie transverse complète**
  - Critère : manifeste + seed + statut validation présents sur tous les exports majeurs et secondaires.
2. **Jalon B — Headless testable par domaine**
  - Critère : chaque domaine principal dispose d’un service headless testé indépendamment de Qt.
3. **Jalon C — Release pipeline industrialisé**
  - Critère : CI Windows complète (lint/tests/smoke/build) + artefacts traçables.
4. **Jalon D — Dossier release défendable**
  - Critère : datasets de référence, replay déterministe, changelog scientifique, preuves automatiques.

---

## 5. Indicateurs de sortie (encore ouverts)

1. 100% des exports de production contiennent un manifeste exploitable (`run_id`, seed, versions, hashes, statut).
2. Rejeu déterministe prouvé en CI sur INDEX, INDEX_SPLINE, STRAT et RE.
3. Tous les modules majeurs disposent d’au moins un service headless testable.
4. CI Windows release verte avec smoke offscreen en prérequis bloquant.
5. Alignement docs↔code vérifié automatiquement sur API + métadonnées release.

---

## 6. Prochaine exécution immédiate

1. Poursuivre le désenclavement RE par services de phase dédiés (extraction de logique métier hors worker).
2. Maintenir les garde-fous seed/release/headless sur tout nouveau module/service introduit.
3. Ajouter encore des checks métier profonds sur contenu/sémantique des artefacts release si de nouveaux besoins apparaissent.

