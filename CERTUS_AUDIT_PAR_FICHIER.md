# Audit CERTUS par fichier

## Objectif
Produire une lecture **fichier par fichier** des modules les plus importants de la suite CERTUS, avec pour chacun :
- le rôle réel du fichier,
- les risques techniques,
- les problèmes d’architecture,
- les risques UX / robustesse / testabilité,
- les améliorations concrètes à prioriser.

> Cet audit est volontairement orienté action. Il vise à dire **quoi corriger, où, et pourquoi**.

---

## Synthèse exécutive

La suite CERTUS présente une qualité scientifique et algorithmique très élevée sur plusieurs noyaux métier, mais la base souffre encore de trois défauts structurels majeurs :

1. **God modules** très volumineux, surtout côté UI / orchestration.
2. **Mélange des responsabilités** entre UI, calcul, persistance, export et workflow.
3. **Fragilité de certains chemins de démarrage et d’export**, notamment lorsque les données de configuration ne sont pas exactement dans le format attendu.

Le résultat est un code puissant mais coûteux à maintenir, à auditer et à faire évoluer.

---

## Grille de lecture

Pour chaque fichier, je donne :
- **Rôle** : ce que le fichier fait réellement.
- **Forces** : points déjà bons.
- **Risques** : ce qui peut casser, ralentir ou brouiller la maintenance.
- **Améliorations prioritaires** : actions concrètes.
- **Priorité** : P0, P1 ou P2.

---

## 1. `certus_core.py`

### Rôle
Socle applicatif partagé : bootstrap, conventions communes, services transverses, initialisation, helpers de base.

### Forces
- C’est le bon endroit pour centraliser les règles partagées.
- Le noyau commun réduit la duplication quand il est utilisé correctement.
- C’est un levier important pour stabiliser le démarrage global.

### Risques
- Si le noyau devient un fourre-tout, il finit par devenir un second God module.
- Le socle peut masquer des dépendances implicites entre modules d’entrée.
- Les erreurs de bootstrap peuvent contaminer plusieurs applications à la fois.

### Améliorations prioritaires
- Verrouiller les contrats publics du module.
- Distinguer clairement : bootstrap, config, logging, services, outils purs.
- Déplacer toute logique métier spécialisée hors du noyau.
- Ajouter des tests de non-régression sur les chemins de démarrage.

### Priorité
**P0**

---

## 2. `certus_ui.py`

### Rôle
Couche UI commune et composants de présentation transverses.

### Forces
- Peut servir de base de mutualisation si les responsabilités restent strictes.
- Réduit la duplication visuelle et comportementale.

### Risques
- Forte probabilité de mélange UI / logique métier.
- Gros risque de signaux, slots, callbacks et états internes difficiles à suivre.
- Les erreurs de refresh ou de timing peuvent être invisibles à la lecture.

### Améliorations prioritaires
- Séparer les widgets purement visuels des contrôleurs de flux.
- Extraire les helpers de rendu, d’état vide, d’erreur et de loading.
- Standardiser les messages d’état et les actions utilisateur.
- Réduire les closures et callbacks anonymes quand c’est possible.

### Priorité
**P0**

---

## 3. `CERTUS_HUB.py`

### Rôle
Point d’entrée / hub central de navigation entre les sous-outils CERTUS.

### Forces
- Bon candidat pour centraliser le routing applicatif.
- Peut simplifier le lancement de plusieurs sous-modules.

### Risques
- Le hub devient souvent un “méga orchestrateur” qui connaît tout.
- Risque élevé de dépendances croisées avec les fenêtres métiers.
- Si le hub contient trop de logique, il devient difficile à tester.

### Améliorations prioritaires
- Transformer le hub en couche d’orchestration minimale.
- Externaliser les données de navigation et les mappings de modules.
- Ajouter un modèle explicite des sections / outils / actions.
- Supprimer les règles métier du hub.

### Priorité
**P0**

---

## 4. `CERTUS_INDEX.py`

### Rôle
Application de caractérisation d’indice : chargement de données, configuration, calculs, exports et UI associée.

### Forces
- Domaine scientifique bien défini.
- Déjà plusieurs garde-fous introduits côté configuration.
- Bon potentiel de standardisation autour des chargements et exports.

### Risques
- Le fichier reste très sensible aux configurations incomplètes ou anciennes.
- Les chemins d’export peuvent refléter un RMSE non représentatif si la sélection du résultat n’est pas correcte.
- Les widgets et les paramètres de calcul sont proches les uns des autres.

### Améliorations prioritaires
- Séparer chargement config, initialisation des widgets, logique métier et export.
- Harmoniser le calcul du RMSE affiché dans les noms de fichiers de sortie.
- Créer un adaptateur de config robuste pour anciens JSON / exemples.
- Ajouter des tests sur : premier lancement, chargement JSON, export, fallback.

### Priorité
**P0**

---

## 5. `CERTUS_INDEX_SPLINE.py`

### Rôle
Version spline / UI la plus lourde de l’écosystème index, avec orchestration de l’interface, calculs, workers et rendu.

### Forces
- Fonctionnalité très riche.
- Très fort niveau de sophistication algorithmique.
- Intègre plusieurs parcours utilisateurs réels.

### Risques
- Fichier extrêmement volumineux, donc très coûteux à relire et faire évoluer.
- Présence probable de nombreuses responsabilités mélangées.
- Forte densité de callbacks et de logique d’interface.
- Grande surface de régression à chaque modification.

### Améliorations prioritaires
- Découper par sous-domaines : construction UI, workers, plots, config, export.
- Extraire des dataclasses de contexte pour les appels lourds.
- Remplacer les callbacks inline par des méthodes nommées quand possible.
- Réduire la taille des fonctions critiques les plus longues.

### Priorité
**P0**

---

## 6. `CERTUS_STRAT.py`

### Rôle
Moteur stratégique d’exploration / sélection / optimisation des stratégies multicritères.

### Forces
- Très utile pour l’exploration avancée.
- Le pipeline d’évaluation semble riche et pensé pour la robustesse.
- La logique d’optimisation est au cœur de la valeur métier.

### Risques
- Risque de confusion entre score, RMSE, robustesse et critères de sélection.
- Les exports peuvent refléter un score erroné si la hiérarchie des résultats est mal lue.
- Le fichier semble fortement exposé aux duplications de logique.

### Améliorations prioritaires
- Isoler clairement les notions de `score`, `rmse`, `rmse_mean`, `rmse_p95`, `robustness_score`.
- Formaliser une fonction unique de sélection du “meilleur résultat”.
- Sortir les règles d’export dans un module dédié.
- Ajouter des tests sur le cas “RMSE affiché à 0.0” pour empêcher les régressions.

### Priorité
**P0**

---

## 7. `CERTUS_RE.py`

### Rôle
Application / moteur de reconstruction et d’exploitation des résultats de réflectance ou de requêtes associées.

### Forces
- Base métier utile pour la partie inverse / reconstruction.
- Peut être un bon point d’entrée pour les traitements spécialisés.

### Risques
- Comme les autres gros entrypoints, risque de mélange UI / calcul / persistance.
- Difficulté à isoler les chemins critiques sans forte découpe.
- L’accès aux workers et à l’état interne peut devenir opaque.

### Améliorations prioritaires
- Découper les responsabilités autour des flux “charger”, “analyser”, “exporter”, “réinitialiser”.
- Introduire des objets de contexte métier pour les appels worker.
- Réduire les blocs d’erreur trop larges.
- Mettre des tests sur les sorties d’export et les états intermédiaires.

### Priorité
**P1**

---

## 8. `CERTUS_DESIGN.py`

### Rôle
Conception / design de structure, paramétrage et export de résultats design.

### Forces
- Domaine bien défini.
- Potentiel de réutilisation avec STRAT / INDEX si le format de contexte est harmonisé.

### Risques
- Glissement vers un fichier “pipeline + UI + export + validation”.
- Forte duplication possible avec les autres entrypoints.
- Les erreurs de modèle ou de paramétrage peuvent être difficiles à diagnostiquer.

### Améliorations prioritaires
- Extraire les calculs communs vers des helpers partagés.
- Harmoniser la structure des configurations et des résultats.
- Isoler les exports HTML / Excel.
- Documenter précisément les conventions de paramètres.

### Priorité
**P1**

---

## 9. `CERTUS_METAL_SINGLE.py`

### Rôle
Cas métier métal simple, probablement centré sur un modèle ou un flux spécifique.

### Forces
- Fichier spécialisé, donc potentiellement plus facile à tester par scénario.
- Peut servir de référence de design si le cœur métier est propre.

### Risques
- Le domaine métal peut accumuler ses propres variantes et exceptions.
- Répétitions de logique avec bilayer ou autres modules matériaux.
- Un module “single” peut devenir aussi complexe qu’un module généraliste si les variantes s’accumulent.

### Améliorations prioritaires
- Extraire les constantes et règles matériau dans un module commun.
- Séparer les calculs du rendu et des exports.
- Harmoniser les signatures avec `CERTUS_METAL_BILAYER.py`.

### Priorité
**P1**

---

## 10. `CERTUS_METAL_BILAYER.py`

### Rôle
Version bilayer des calculs / workflows métal.

### Forces
- Complément naturel du module single.
- Possibilité de mutualiser une large base commune avec le module single.

### Risques
- Duplication entre single et bilayer.
- Risque d’alignement incomplet des hypothèses physiques.
- Complexité supplémentaire dans les transitions de couches et de paramètres.

### Améliorations prioritaires
- Factoriser le socle métal commun.
- Séparer la définition du modèle bilayer du moteur d’optimisation.
- Vérifier les invariants physiques avec des tests dédiés.

### Priorité
**P1**

---

## 11. `certus_design_worker_utils.py`

### Rôle
Utilitaires pour workers de design.

### Forces
- Bonne direction si le module reste petit et ciblé.
- Permet de mutualiser des manipulations répétitives.

### Risques
- Devient vite un fourre-tout si plusieurs workers y déposent chacun leurs propres conventions.
- Les utilitaires peuvent dupliquer des validations déjà présentes ailleurs.

### Améliorations prioritaires
- Définir un périmètre strict : conversion, validation, formatting, bridges UI.
- Éviter les dépendances vers la fenêtre principale.
- Ajouter des tests unitaires très ciblés.

### Priorité
**P2**

---

## 12. `certus_design_workers.py`

### Rôle
Définition des workers asynchrones pour les scénarios design.

### Forces
- Bonne séparation potentielle entre UI et exécution.
- Les workers se prêtent bien au test isolé.

### Risques
- Si les workers portent trop d’état global, ils deviennent difficiles à rejouer.
- Les signaux peuvent être dispersés et peu lisibles.

### Améliorations prioritaires
- Rendre les entrées/sorties explicites via dataclasses.
- Éviter les accès directs aux widgets.
- Standardiser le cycle de vie des workers.

### Priorité
**P2**

---

## 13. `certus_re_helpers.py`

### Rôle
Helpers pour la partie reconstruction.

### Forces
- Le bon emplacement pour réduire la duplication.
- Peut devenir une boîte à outils stable pour les flux RE.

### Risques
- Les helpers peuvent devenir un sous-socle caché sans contrat clair.
- Risque de duplication silencieuse avec les helpers des autres modules métier.

### Améliorations prioritaires
- Publier des fonctions pures avec signatures stables.
- Regrouper la normalisation des entrées dans un seul endroit.
- Créer des tests de non-régression sur les formats de données.

### Priorité
**P2**

---

## 14. `certus_re_workers.py`

### Rôle
Workers asynchrones pour les workflows reconstruction.

### Forces
- Découplage calcul/UI utile.
- Permet des traitements longs sans bloquer l’interface.

### Risques
- Fichier potentiellement très lourd et procédural.
- Forte probabilité de fonctions géantes si chaque phase est codée de bout en bout.
- Difficile à maintenir si chaque étape du workflow est imbriquée.

### Améliorations prioritaires
- Découper le pipeline par phases claires.
- Introduire un contexte de run immuable.
- Séparer les calculs, validations, logs et agrégations.

### Priorité
**P1**

---

## 15. `certus_index_utils.py`

### Rôle
Utilitaires partagés pour les traitements index.

### Forces
- Potentiel de mutualisation fort.
- Aide à sortir des détails répétitifs des fichiers lourds.

### Risques
- Devient un rassembleur de petits hacks si le contrat n’est pas défini.
- Peut accumuler des conversions de type ad hoc et des fallback peu lisibles.

### Améliorations prioritaires
- Distinguer helpers de conversion, validation, parsing et export.
- Ajouter des annotations de type fortes.
- Introduire des tests unitaires exhaustifs.

### Priorité
**P2**

---

## 16. `certus_spectral_workers.py`

### Rôle
Workers de calcul spectral / analyses associées.

### Forces
- C’est un bon endroit pour isoler les lourdeurs de calcul.
- Potentiel de parallélisation et de batch processing.

### Risques
- Si les workers manipulent à la fois les données, le cache et l’UI, le découplage devient faible.
- Les erreurs numériques peuvent être noyées dans la logique d’orchestration.

### Améliorations prioritaires
- Séparer pure computation et coordination.
- Rendre la gestion du cache explicite.
- Stabiliser les contrats d’entrée/sortie.

### Priorité
**P2**

---

## 17. `certus_services.py`

### Rôle
Services transverses applicatifs.

### Forces
- Très bon candidat pour une architecture propre.
- Peut centraliser logging, persistence, settings, I/O, tasks utilitaires.

### Risques
- Peut devenir un nouveau “fourre-tout de services”.
- Les dépendances croisées peuvent y entrer par facilité.

### Améliorations prioritaires
- Scinder les sous-services par domaine.
- Éviter les appels UI depuis les services.
- Documenter les contrats et les effets de bord.

### Priorité
**P1**

---

## 18. `certus_shortcuts_overlay.py`

### Rôle
Overlay des raccourcis clavier et de l’aide utilisateur.

### Forces
- Bon module UX s’il reste indépendant.
- Peut fortement améliorer la découvrabilité.

### Risques
- Le overlay peut devenir obsolète si les actions évoluent mais pas le texte.
- Duplications possibles avec menus, tooltips et documentation.

### Améliorations prioritaires
- Lier les raccourcis à une source unique.
- Éviter le texte durcodé si possible.
- Tester l’accessibilité et la cohérence des libellés.

### Priorité
**P2**

---

## 19. `certus_skeleton.py`

### Rôle
Base / squelette d’architecture ou de composants.

### Forces
- Peut servir d’exemple ou de base de création rapide.
- Utile pour standardiser les nouveaux modules.

### Risques
- Peut devenir un prototype figé ou une copie non maintenue.
- Si le squelette diverge des vrais modules, il devient trompeur.

### Améliorations prioritaires
- Garder le squelette strictement aligné avec les conventions actuelles.
- S’assurer qu’il n’introduit pas de logique fantôme.

### Priorité
**P2**

---

## 20. `certus_toast_stack.py`

### Rôle
Gestion des toasts / notifications UI.

### Forces
- Bon levier UX pour feedback non bloquant.
- Peut réduire l’usage abusif des boîtes de dialogue modales.

### Risques
- Peut accumuler état, file d’attente et timers délicats.
- Risque de duplication de styles et de comportements.

### Améliorations prioritaires
- Centraliser le style des notifications.
- Définir des niveaux de sévérité clairs.
- Ajouter des tests sur le cycle d’apparition/disparition.

### Priorité
**P2**

---

## 21. `certus_splash.py`

### Rôle
Splash screen et chargement initial.

### Forces
- Très utile pour l’expérience de démarrage.
- Bon endroit pour uniformiser le feedback du bootstrap.

### Risques
- Code dupliqué entre entrypoints.
- Peut contenir une logique de démarrage trop spécifique à un module.

### Améliorations prioritaires
- Standardiser l’appel du splash.
- Réduire les variantes visuelles non nécessaires.
- Éviter les divergences entre entrypoints.

### Priorité
**P2**

---

## 22. `certus_strat_context.py`

### Rôle
Contexte métier des stratégies, probablement dataclasses / objets de run.

### Forces
- Si bien fait, c’est un excellent stabilisateur d’architecture.
- Permet de remplacer des appels à paramètres positionnels.

### Risques
- Peut devenir un agrégateur de tout si le contexte est trop large.
- Si les champs ne sont pas strictement documentés, il perd son intérêt.

### Améliorations prioritaires
- Rendre le contexte immuable si possible.
- Séparer paramètres de run, métriques et metadata.
- Ajouter des validations de cohérence.

### Priorité
**P1**

---

## 23. `certus_strat_service.py`

### Rôle
Service métier autour des stratégies.

### Forces
- Très bon endroit pour sortir de la logique depuis l’UI.
- Peut devenir le socle d’un workflow propre et testable.

### Risques
- Si le service englobe trop de phases, il devient aussi dur à lire que le monolithe d’origine.
- Risque de couplage fort avec les structures d’export.

### Améliorations prioritaires
- Découper les méthodes par phase métier.
- Rendre les entrées explicites via types stables.
- Ajouter des tests sur les scénarios de sélection de stratégie.

### Priorité
**P1**

---

## 24. `certus_spline_report.py`

### Rôle
Rapports, export et mise en forme des résultats spline.

### Forces
- Sépare potentiellement la présentation des calculs.
- Bon levier pour améliorer la lisibilité des sorties.

### Risques
- Le reporting peut refléter des hypothèses métier mal contrôlées.
- HTML, Excel et console peuvent diverger si la logique est dupliquée.

### Améliorations prioritaires
- Centraliser le calcul des métriques rapportées.
- Éviter les formats de sortie générés séparément à partir de logiques différentes.
- Ajouter des tests de cohérence des rapports.

### Priorité
**P2**

---

## 25. `tools/release_checks.py`

### Rôle
Vérifications de release.

### Forces
- Très bon signe de maturité projet.
- Peut éviter des releases cassées ou partielles.

### Risques
- Les checks peuvent vieillir si les règles de release changent.
- Un script trop permissif donne un faux sentiment de sécurité.

### Améliorations prioritaires
- Documenter précisément les critères de réussite.
- Élargir les checks aux artefacts réellement livrés.
- Ajouter une sortie lisible et actionnable.

### Priorité
**P1**

---

## 26. `scripts/smoke/run_examples_headless.py`

### Rôle
Smoke tests headless sur des exemples.

### Forces
- Très utile pour valider les scénarios de bout en bout.
- Réduit le risque de régression au démarrage.

### Risques
- Les smoke tests sont souvent fragiles si les exemples changent sans contrat stable.
- Peut masquer des échecs s’il ne vérifie pas les bons signaux.

### Améliorations prioritaires
- Définir des assertions minimales obligatoires.
- Rendre les sorties de smoke lisibles.
- Couvrir au moins un cas nominal par grande famille de modules.

### Priorité
**P1**

---

## 27. `tests/unit/test_certus_core.py`

### Rôle
Tests du socle commun.

### Forces
- Excellent point d’ancrage pour éviter les régressions globales.
- Doit protéger les contrats de base.

### Risques
- Si les tests sont trop liés aux détails internes, ils cassent pour de mauvaises raisons.
- Si la couverture est seulement superficielle, ils ne protègent pas le bootstrap réel.

### Améliorations prioritaires
- Tester les invariants publics, pas les détails d’implémentation.
- Ajouter des cas de démarrage minimal.
- Vérifier les erreurs attendues.

### Priorité
**P0**

---

## 28. `tests/unit/test_certus_strat_service.py`

### Rôle
Tests du service stratégie.

### Forces
- Très bon fichier pour verrouiller les règles de sélection.
- Doit servir de garde-fou sur les scores et la hiérarchie des résultats.

### Risques
- Peut être insuffisant si les résultats sont complexes et multi-phases.
- Les tests doivent refléter le modèle de décision réel.

### Améliorations prioritaires
- Couvrir les cas de RMSE nul, placeholder, et score robuste.
- Tester le tri, l’agrégation et les fallbacks.

### Priorité
**P0**

---

## 29. `tests/unit/test_certus_index.py` et tests voisins

### Rôle
Tests du flux index.

### Forces
- Essentiels pour valider les chemins de chargement, calcul et export.
- Très utiles pour les bugs de configuration.

### Risques
- Les scénarios “premier lancement” et “JSON ancien” sont souvent oubliés.
- Les tests peuvent manquer les erreurs d’alignement entre la config et les widgets.

### Améliorations prioritaires
- Cas de premier lancement.
- Cas JSON ancien / partiel.
- Cas export et nommage des fichiers.
- Cas absence de fichier de données.

### Priorité
**P0**

---

## 30. `tests/integration/test_example_pipelines.py`

### Rôle
Validation de bout en bout des pipelines exemple.

### Forces
- Très utile pour capturer les vrais parcours.
- Réduit les régressions entre modules.

### Risques
- Peut devenir lent ou trop dépendant des fichiers locaux.
- Si les exemples changent souvent, les tests deviennent instables.

### Améliorations prioritaires
- Stabiliser les fixtures d’exemple.
- Définir des critères de succès simples et mesurables.
- Éviter les comparaisons trop fragiles.

### Priorité
**P1**

---

## Priorités transverses par famille de fichiers

### A. Entrypoints lourds à découper en premier
- `CERTUS_INDEX_SPLINE.py`
- `CERTUS_STRAT.py`
- `CERTUS_RE.py`
- `CERTUS_DESIGN.py`
- `CERTUS_INDEX.py`
- `CERTUS_HUB.py`
- `certus_ui.py`
- `certus_core.py`

### B. Modules de services / helpers à stabiliser
- `certus_services.py`
- `certus_index_utils.py`
- `certus_re_helpers.py`
- `certus_design_worker_utils.py`
- `certus_spectral_workers.py`
- `certus_strat_service.py`
- `certus_strat_context.py`

### C. Tests à renforcer en priorité
- `tests/unit/test_certus_core.py`
- `tests/unit/test_certus_index.py`
- `tests/unit/test_certus_strat_service.py`
- `tests/integration/test_example_pipelines.py`

---

## Plan d’action recommandé

### P0
1. Verrouiller les contrats de `certus_core.py`.
2. Corriger les chemins critiques de `CERTUS_INDEX.py`.
3. Formaliser la sélection du meilleur résultat dans `CERTUS_STRAT.py`.
4. Couvrir les cas de premier lancement et de JSON ancien.

### P1
5. Découper `CERTUS_INDEX_SPLINE.py`, `CERTUS_RE.py`, `CERTUS_DESIGN.py`.
6. Extraire les services communs hors de l’UI.
7. Harmoniser les contextes métier.
8. Ajouter des tests d’intégration sur les pipelines exemples.

### P2
9. Nettoyer les helpers secondaires.
10. Réduire les duplications de reporting.
11. Uniformiser les overlays, toasts et splash screens.

---

## Conclusion

L’audit par fichier montre une suite CERTUS qui possède un **noyau scientifique solide**, mais qui doit encore franchir une étape importante de **structuration logicielle**.

Les gains les plus rentables viennent de trois chantiers :
- **isoler le métier de l’UI**,
- **réduire les fichiers géants**,
- **renforcer les tests sur les contrats réels**.

Si tu veux, je peux maintenant faire la version suivante sous forme de tableau hiérarchisé dans un autre fichier Markdown :
- **audit détaillé de chaque fichier avec note /100**, ou
- **plan de refactor fichier par fichier**, avec ordre exact d’exécution.
