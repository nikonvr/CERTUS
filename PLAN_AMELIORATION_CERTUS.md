# Plan d'amélioration CERTUS — audit + actions prioritaires

## Résumé exécutif

L'audit confirme que CERTUS est une suite Python/PyQt6 conséquente d'optique couches minces, avec une base de tests importante et une architecture déjà orientée séparation `core` / `physics` / `ui` / `workers`. Les corrections de lint bloquantes ont été appliquées et validées : `python -m ruff check .` passe désormais sans erreur, et 15 tests ciblés passent.

Le risque principal n'est pas un défaut isolé, mais l'accumulation de dette structurelle : nombreux fichiers modifiés/non suivis, forte duplication dans les modules TMM/physics, frontières `core`/`ui` encore poreuses, et modules UI/workers très volumineux.

## État validé

- Ruff : `All checks passed!`
- Tests ciblés : `15 passed`
- Corrections déjà appliquées :
  - parenthésage explicite des chaînes `and/or` ambiguës ;
  - remplacement des `except:` nus par `except Exception` ;
  - correction d'assertions booléennes en tests ;
  - réparation de `fix_re_workers.py` ;
  - exclusion documentée de snapshots legacy UTF-16 non suivis (`old_physics_impl.py`, `old_ui.py`).

## Risques prioritaires

| Priorité | Zone | Risque | Action recommandée |
|---|---|---|---|
| P0 | Git / changements en cours | Nombreux fichiers modifiés/non suivis, risque de mélange de chantiers | Stabiliser par commits atomiques avant refactorings |
| P0 | Frontière architecture | Imports UI/PyQt6 dans `certus/core` | Extraire les dépendances UI vers `certus/ui` ou `workers` |
| P1 | Physics/TMM | Fichiers TMM très gros et très dupliqués | Cartographier les symboles puis extraire uniquement des kernels communs testés |
| P1 | UI | Modules UI/mixins volumineux avec logique de workflow | Déplacer la logique métier vers services/workers sans toucher au rendu |
| P1 | Tests | Couverture ciblée inégale sur hot paths physics/UI | Ajouter tests de non-régression autour des zones modifiées |
| P2 | Scripts legacy | Scripts racine de migration/fix peu maintenus | Ranger ou exclure les scripts obsolètes après validation |

## Plan d'action recommandé

### Phase 1 — Stabilisation immédiate

1. Conserver l'état Ruff vert.
2. Vérifier le diff actuel et séparer les changements par domaine : design, RE, physics, tests, scripts.
3. Committer séparément :
   - corrections lint ;
   - changements design/workers ;
   - changements tests ;
   - fichiers générés/logs à ignorer ou supprimer.
4. Ajouter/mettre à jour `.gitignore` pour les artefacts évidents : logs, runs batch, outputs locaux, snapshots temporaires.

### Phase 2 — Frontières architecturales

Objectif : respecter strictement la règle CERTUS : pas d'UI dans `certus.core` / `certus_physics` / `certus.physics`.

Actions conservatrices :

1. Inventorier les imports UI dans `certus/core`.
2. Classer chaque cas :
   - vraie logique core mal placée ;
   - orchestrateur Qt à déplacer ;
   - constantes UI à dupliquer sous forme neutre ou à injecter.
3. Déplacer un seul fichier/fonction à la fois.
4. Pour chaque déplacement : lancer `ruff` + test ciblé.

Cibles connues :

- `certus/core/certus_design_orchestrator.py` contient Qt et widgets.
- `certus/core/certus_design_core.py` importe des composants UI.
- `certus/core/certus_strat_core.py` et `certus/core/certus_strat_objectives.py` référencent `certus.ui.certus_ui`.
- `certus/core/certus_hub_config.py` dépend de `CertusTheme`.

### Phase 3 — Réduction du risque TMM/physics

Objectif : ne pas refactorer massivement les kernels, mais réduire le risque de duplication.

Actions :

1. Générer une carte des fonctions dupliquées entre :
   - `certus_tmm_matrix.py`
   - `certus_tmm_oblique.py`
   - `certus_tmm_single_layer.py`
   - `certus_tmm_hl.py`
   - `certus_tmm_backside.py`
2. Identifier les fonctions strictement identiques.
3. Ne déplacer que les fonctions sans état global et déjà couvertes par tests.
4. Créer des tests de parité avant extraction.
5. Éviter toute modification des conventions Macleod/backside sans tests dédiés.

### Phase 4 — Nettoyage UI/workers

Objectif : réduire les régressions UI en isolant les workflows.

Actions :

1. Garder les fichiers UI responsables du rendu et des signaux.
2. Déplacer calculs, décisions de workflow, scoring et ranking vers `certus/workers` ou `certus/utils`.
3. Introduire de petits DTO typés si nécessaire.
4. Tester les services sans instancier toute l'UI PyQt.

### Phase 5 — Qualité continue

1. Ajouter une commande rapide de vérification :
   - `python -m ruff check .`
   - tests unitaires ciblés par domaine.
2. Créer une matrice de tests de non-régression :
   - design workers ;
   - physics TMM ;
   - strat stability ;
   - RE phases ;
   - index spline roundtrip.
3. Éviter `ruff --fix` global sur legacy.
4. Maintenir les corrections atomiques et petites.

## Première action concrète proposée

La première action sûre après cet audit est :

> Nettoyer la frontière `core`/`ui` sur `certus/core/certus_hub_config.py`, car c'est probablement le cas le moins risqué : remplacer la dépendance directe à `CertusTheme` par des valeurs neutres ou déplacer la décoration visuelle côté UI.

Ensuite seulement : traiter `certus_design_orchestrator.py`, plus risqué car il utilise directement `QObject`, `QThread`, `QTimer`, `QMessageBox` et des widgets.
