# Audit Technique des Modules Spécifiques - CERTUS Suite (2026)

**Longueur du document : 192 lignes**

Cet audit résume l’état technique actuel de la suite CERTUS, avec un focus sur la qualité structurelle, les zones de duplication encore visibles, les récentes passes de refactoring DRY, et les points de vigilance liés aux flux UI sensibles.

---

## 1. Bilan global de la campagne DRY

### Taille de la suite CERTUS dans `OLD/`
- **Lignes de code (`OLD/`)** : 173 273 lignes sur 174 fichiers Python
- **Lignes de test (`OLD/tests/`)** : 53 078 lignes sur 172 fichiers Python

La campagne DRY a permis plusieurs factorisations utiles, mais certaines zones UI très couplées ont montré qu’il fallait avancer avec une prudence maximale.

### Résultats principaux
- Réduction de duplications dans les helpers de récents, de zoom UI et des services headless.
- Ajout de petits modules partagés pour éviter la répétition de logique transversale.
- Renforcement de l’architecture autour des services headless et des DTO.
- Relecture de plusieurs chemins sensibles du flux `mwir` / `sigma` pour éviter les régressions.

### État de sécurité
- Les refactors les plus sûrs sont conservés.
- Les zones sensibles ont été validées par des tests ciblés après corrections.
- La règle pratique retenue est maintenant claire : **DRY oui, mais uniquement par micro-passes conservatrices sur les chemins UI critiques**.

### Mesure qualitative
- Le projet est globalement plus lisible.
- Les points de duplication identifiés sont mieux isolés.
- La base reste saine à condition de ne pas généraliser trop vite les helpers sur les flux manuels complexes.

---

## 2. Synthèse des modules

| Module / Composant | État actuel | Risque principal | Axe de suivi |
| :--- | :--- | :--- | :--- |
| **SPLINE / Index / Corridors** | Stable mais complexe | Flux manuels `sigma` et corridors très couplés | Continuer en petites étapes, avec tests ciblés à chaque changement |
| **STRAT** | Stable | Duplications DTO et UI périphérique | Factorisations locales uniquement, sans toucher au cœur métier inutilement |
| **RE** | Stable | Sérialisation et chemins de compatibilité legacy | Maintenir les wrappers et helpers actuels, éviter les couplages physiques additionnels |
| **METAL** | Stable et volontairement découplé | Tentation d’introduire un modèle physique non souhaité | **Interdiction maintenue** d’introduire Kramers-Kronig / Drude-Lorentz / Tauc-Lorentz |
| **DESIGN** | Stable | Logique d’optimisation dense et parfois répétée | DRY possible, mais à faible granularité |
| **INDEX** | Stable | Branches UI / workflow d’insertion manuelle | Refactorer seulement après validation des tests sensibles |

---

## 3. Analyse détaillée par module

### A. Spline Index Profiler & Corridors
#### État actuel
- Le module reste le plus volumineux et le plus sensible du projet.
- L’architecture est fonctionnelle, mais la densité des responsabilités reste élevée.
- Les derniers essais de DRY ont montré qu’un helper trop généraliste pouvait fragiliser les flux manuels `sigma`.

#### Ce qui a été consolidé
- Certains chemins de préparation des récentes, des zooms UI, et des helpers partagés ont été structurés.
- Les flux de worker peuvent être réorganisés de manière plus cohérente.
- Les tests ciblés ont permis de retrouver rapidement un comportement sûr après correction.

#### Point de vigilance
- Le flux manuel d’insertion `sigma` doit rester prioritaire en terme de sécurité.
- Les chemins de repartition et de réinitialisation des workers sont sensibles aux abstractions trop agressives.

#### Recommandation
- Continuer les refactors uniquement sur des morceaux très isolés.
- Éviter toute fusion de logique qui mélangerait les étapes de préparation du worker, de calcul des cibles sigma et de wiring des signaux.

---

### B. Stratification & Suivi
#### État actuel
- Le module est stable.
- La structure des DTO STRAT est mieux organisée.
- La logique de type mapping a été factorisée avec prudence.

#### Ce qui ressort
- Les répétitions autour des DTO peuvent être réduites proprement.
- Les helpers `__getitem__`, `__iter__`, `__len__`, `get` et la comparaison aux dicts peuvent rester mutualisés.
- Le maintien d’une compatibilité legacy reste important.

#### Recommandation
- Poursuivre la consolidation des DTO et conserver des tests unitaires dédiés aux comportements de compatibilité.
- Ne pas toucher aux contrats publics tant que les consommateurs legacy existent.

---

### C. Reverse Engineering
#### État actuel
- Le module est structurellement plus propre qu’auparavant.
- Les services headless ont été simplifiés via une base commune.
- La sérialisation et le passage par les modèles Pydantic restent le bon point de contrôle.

#### Ce qui a été consolidé
- `BaseHeadlessService` centralise le pipeline de validation, conversion et création de manifeste.
- Les services `IndexFitService`, `SubstrateIndexService` et `REFitService` partagent désormais une base commune.
- Les types publics sont restés stables.

#### Recommandation
- Garder cette couche commune comme unique point de mutualisation.
- Éviter d’introduire trop d’abstraction supplémentaire tant que les signatures publiques sont exposées à des tests de contrat.

---

### D. Couches Métalliques
#### Décision architecturale maintenue
- **Il est interdit d’introduire Kramers-Kronig, Drude-Lorentz, Tauc-Lorentz ou tout autre modèle physique contraignant dans METAL.**
- Le module doit rester libre, mathématiquement découplé, et basé sur l’optimisation spline pure.

#### Recommandation
- Conserver ce firewall d’architecture.
- Toute modification future doit préserver l’indépendance du traitement `n(λ)` / `k(λ)`.

---

### E. Design
#### État actuel
- Le moteur de design reste stable.
- Les structures principales sont cohérentes.
- Les duplications existent encore mais sont moins critiques que dans les zones UI/spline.

#### Recommandation
- Les prochains DRY doivent rester localisés.
- Favoriser les helpers de bord plutôt que les refactors qui traverseraient plusieurs couches métier.

---

### F. Index
#### État actuel
- Le module est stable, mais ses chemins UI restent sensibles.
- Les flux d’insertion manuelle et de répartition nécessitent une validation systématique.

#### Recommandation
- Séparer strictement préparation des données, lancement des workers et mise à jour de l’UI.
- Ne pas introduire de mutualisation qui cacherait ces étapes dans une seule abstraction si cela complique les tests.

---

## 4. Duplications encore visibles et priorités raisonnables

L’analyse de duplication automatique montre encore plusieurs groupes dupliqués, mais beaucoup sont soit très spécialisés, soit liés à des classes/forks volontaires.

### Meilleurs candidats DRY à faible risque
1. **UI Index / UI Strat**
   - `zoom_in_ui`, `zoom_out_ui`, `reset_ui_zoom`
   - `_get_log_widget`
   - `_get_default_splitter_sizes`

2. **DTO STRAT**
   - `__getitem__`, `__iter__`, `__len__`, `get`, `__eq__`

3. **Services headless**
   - Mutualisation déjà mise en place, à conserver comme base commune unique

4. **Récents UI**
   - `certus_recent.py`
   - `certus_recent_strip.py`
   - Peut encore être nettoyé, mais sans élargir trop vite les responsabilités

### Candidats plus risqués
- `certus/ui/certus_index_spline_ui.py`
- `certus/spline/spline_pipeline.py`
- `certus/spline/spline_profile_corridors.py`
- `certus/workers/certus_design_workers.py`

Ces zones sont très sensibles : le moindre helper trop large peut impacter les tests de flux manuel.

---

## 5. Validation et niveau de confiance

### Ce qui a été validé
- Lint propre sur les fichiers récemment touchés.
- Les tests ciblés les plus sensibles autour du flux `mwir` ont été corrigés et repassés.
- Les services et les helpers introduits sont restés compatibles avec leurs contrats publics.

### Niveau de confiance actuel
- **Élevé pour les refactors locaux et les helpers de faible portée**.
- **Moyen pour les refactors transverses touchant `certus_index_spline_ui.py` et les workflows manuels**.

### Politique de sécurité recommandée
- Toute nouvelle extraction doit être accompagnée d’un test ciblé.
- Tout helper partagé doit rester simple et explicite.
- Si un refactor augmente la fragilité d’un flux testé, il faut le réduire ou le revert immédiatement.

---

## 6. Conclusion

La suite CERTUS a gagné en clarté et en factorisation, mais l’exercice a confirmé un principe important : **certaines zones UI / workers sont trop sensibles pour être DRYifiées agressivement**.

Le bon équilibre pour la suite est maintenant le suivant :
- continuer à éliminer les répétitions triviales,
- préserver les contrats publics,
- valider par des tests ciblés,
- et garder une approche conservatrice sur les chemins `sigma`, `corridors` et workers complexes.

En résumé : la base est meilleure qu’avant, mais la stratégie gagnante reste le **DRY prudent** plutôt que la mutualisation massive.
