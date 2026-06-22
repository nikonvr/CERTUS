# CERTUS-STRAT diagnostic d’audit

## Objet

Ce document synthétise un audit de cohérence scientifique et d’alignement doc/code pour CERTUS-STRAT, avec un focus sur les biais de raisonnement possibles avant dépôt machine.

L’objectif n’est pas seulement de vérifier que le code fonctionne, mais de répondre à une question plus exigeante :

> La stratégie produite est-elle réellement la meilleure stratégie possible pour la machine réelle, ou bien une stratégie très convaincante mais légèrement biaisée par ses propres hypothèses internes ?

---

## Périmètre relu

### Documentation HTML
- `pages/CERTUS_STRAT.html`

### Code STRAT critique
- `certus/utils/certus_strat_service.py`
- `certus/utils/certus_strat_context.py`
- `certus/core/certus_strat_pipeline.py`
- `certus/core/certus_strat_solvers.py`
- `certus/workers/certus_strat_workers.py`

### Contexte de recherche
- `certus/physics/certus_strat_*`
- pages et widgets UI STRAT repérés via le workspace

---

## Verdict exécutif

CERTUS-STRAT apparaît comme une architecture scientifique sérieuse, riche, et très bien outillée pour la robustesse. Cependant, plusieurs biais de raisonnement restent plausibles.

Le risque principal n’est probablement pas un bug isolé. Le risque principal est un **biais systémique de stratégie** :
- sélection spectrale trop orientée par la grille discrétisée,
- filtration des candidats trop influente,
- score final trop monocritère,
- circularité entre génération, filtrage, validation et scoring,
- documentation plus idéale que l’implémentation réelle.

En bref : STRAT semble très avancé, mais il n’est pas encore démontré qu’il est **désintoxiqué de tout biais caché**.

---

## Ce qui est déjà solide

### 1. Architecture modulaire
Le découpage entre service, contexte, pipeline et workers est bon.

### 2. Validation structurée
Le service STRAT valide :
- la structure du payload,
- le schéma JSON,
- les DTO,
- une partie des règles métier,
- la couverture des matériaux.

### 3. Volonté de robustesse
Le pipeline intègre :
- Monte Carlo,
- propagation cumulée,
- stratégie par couches,
- regroupement par blocs,
- re-scoring final,
- consensus multi-seed.

### 4. Intention scientifique forte
La logique n’est pas une heuristique opportuniste : elle essaie réellement de modéliser les effets de dépôt, de signal optique et d’erreur cumulative.

---

## Biais de raisonnement probables

### A. Biais de sélection des longueurs d’onde

#### Risque
La grille candidate peut favoriser certaines zones spectrales et en sous-représenter d’autres.

#### Pourquoi c’est critique
Si la solution optimale se trouve entre deux pas de discrétisation, elle peut ne jamais être évaluée.

#### Symptôme typique
Une stratégie semble excellente avec le maillage courant, mais sa qualité se dégrade si l’on modifie légèrement la fenêtre ou le pas.

#### Action recommandée
Faire une analyse de sensibilité sur :
- `scan_wl_step`,
- `scan_wl_min`, `scan_wl_max`,
- la densité de candidats,
- les règles de sélection des extrema.

---

### B. Biais de filtration des candidats

#### Risque
Des filtres successifs peuvent éliminer des stratégies utiles avant qu’elles ne soient correctement évaluées.

#### Où cela peut se produire
- proximité des extrema,
- seuils de dynamique,
- transmission minimale,
- disponibilité matériau,
- robustesse de validation batch.

#### Symptôme typique
Le moteur devient trop conservateur ou trop restrictif.

#### Action recommandée
Comparer :
- version filtrée actuelle,
- version moins stricte,
- version quasi brute,
- version avec seuils perturbés.

---

### C. Biais de propagation d’erreur

#### Risque
La simulation d’erreur cumulative peut ne pas représenter fidèlement la machine réelle.

#### Deux dérives possibles
1. **Trop optimiste** : les erreurs réelles sont corrélées, systématiques ou non gaussiennes.
2. **Trop pessimiste** : le bruit simulé pénalise trop les candidats réellement exploitables.

#### Action recommandée
Tester des perturbations réalistes :
- dérive systématique,
- bruit corrélé,
- bruit non gaussien,
- erreurs de calibration,
- défauts de dépôt dépendants de la couche.

---

### D. Biais du score final

#### Risque
Si le score final dépend trop d’une métrique unique, la stratégie peut être trop optimisée pour ce score et pas assez pour la réalité.

#### Exemple
Minimiser un worst-case RMSE P95 peut pousser vers une stratégie très prudente mais moins utile à l’exploitation.

#### Action recommandée
Passer à un suivi multi-objectif :
- RMSE worst-case,
- stabilité cross-seed,
- marge spectrale,
- robustesse process,
- exploitabilité opérateur,
- complexité de mise en œuvre.

---

### E. Biais de circularité

#### Risque
Génération, filtration, scoring et validation peuvent partager trop d’hypothèses internes.

#### Pourquoi c’est dangereux
On optimise alors le système sur lui-même, pas sur la machine.

#### Symptôme typique
Les résultats sont excellents en simulation, mais ne se généralisent pas aussi bien en conditions réelles.

#### Action recommandée
Introduire des baselines indépendantes :
- stratégie conservatrice,
- stratégie mono-signal simple,
- stratégie bloc homogène,
- stratégie locale sans DP complexe,
- stratégie hybride minimale.

---

## Conformité doc/code

### Ce que la page HTML fait bien
`CERTUS_STRAT.html` a le mérite de formaliser une vision très détaillée du pipeline.

### Point de vigilance
Elle peut être **plus idéale que le code réel**.

### Vérifications nécessaires
Il faut s’assurer que la page reflète strictement :
- les étapes réellement exécutées,
- l’ordre réel,
- les filtres réellement appliqués,
- les critères de score réels,
- les limites connues,
- les hypothèses physiques exactes.

### Pourquoi c’est important
Une doc plus “parfaite” que le code crée un biais de confiance documentaire.

---

## Diagnostic de risque scientifique

### Ce qui semble probable
- STRAT est techniquement sérieux.
- La structure est ambitieuse et bien pensée.
- Le système peut réellement produire des stratégies robustes.

### Ce qui reste non prouvé
- la meilleure stratégie en simulation est-elle aussi la meilleure stratégie machine ?
- la logique de filtrage est-elle neutre ?
- le score final capture-t-il tout ce qui compte ?
- le pipeline est-il trop sensible à ses hypothèses internes ?

### Conclusion de fond
Le risque principal n’est pas un défaut de codage. Le risque principal est un **biais de stratégie scientifique**.

---

## Recommandations prioritaires

### P0 — Conformité stricte doc/code
Aligner `CERTUS_STRAT.html` sur l’implémentation réelle.

#### Livrable attendu
Une documentation qui décrit exactement ce que le code fait, sans sur-promesse.

---

### P1 — Audit de sensibilité
Mesurer la stabilité de STRAT quand on perturbe :
- la grille spectrale,
- les seuils de filtrage,
- le bruit,
- les seeds,
- le maillage,
- les fenêtres d’extrema.

#### Objectif
Détecter si les résultats dépendent trop d’un choix technique arbitraire.

---

### P2 — Baselines de comparaison
Comparer STRAT à plusieurs approches simples indépendantes.

#### But
S’assurer que la sophistication apporte réellement un gain et n’introduit pas une fausse impression d’optimalité.

---

### P3 — Score multi-objectif
Ne pas laisser un seul KPI décider.

#### À suivre en parallèle
- performance statistique,
- robustesse,
- stabilité,
- facilité machine,
- lisibilité opérateur,
- sensibilité aux dérives.

---

### P4 — Validation machine-realistic
Tester avec des hypothèses de terrain plus réalistes :
- dérive de calibration,
- bruit corrélé,
- erreurs systématiques,
- matériaux limites,
- couverture partielle,
- variations de dépôt.

---

## Protocole de validation recommandé avant dépôt machine

### Phase 1 — Robustesse algorithmique
- seeds multiples
- sous-échantillonnage des candidats
- perturbation des seuils
- perturbation de la grille spectrale

### Phase 2 — Robustesse physique
- bruit non gaussien
- corrélation entre couches
- dérive de deposition rate
- décalage d’index matériau

### Phase 3 — Robustesse opératoire
- stratégie lisible et expliquant pourquoi elle gagne
- vérification des cas limites
- comparaison avec stratégies simples

### Phase 4 — Go/no-go
Ne retenir une stratégie que si elle reste bonne sur plusieurs critères, pas un seul.

---

## Conclusion finale

CERTUS-STRAT est un système crédible, avancé et scientifiquement ambitieux. Mais la complexité même de son pipeline impose une discipline particulière : il ne faut pas seulement vérifier qu’il fonctionne, il faut vérifier qu’il ne **raisonne pas de travers**.

### Mon jugement actuel
- **Oui**, STRAT est potentiellement très fort.
- **Oui**, il est possible qu’il contienne encore des biais subtils.
- **Non**, je ne dirais pas encore que la logique est prouvée parfaite.
- **Oui**, il existe une voie très claire pour durcir le système avant dépôt machine.

### Le prochain bon pas
Réaliser un audit de sensibilité + conformité doc/code + comparaison à des baselines simples.

Cela donnera la meilleure chance de choisir une stratégie réellement optimale, et pas seulement optimale dans son propre cadre interne.
