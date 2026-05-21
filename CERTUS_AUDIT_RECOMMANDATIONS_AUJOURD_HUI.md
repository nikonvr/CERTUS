# CERTUS — Recommandations consolidées des audits du jour

## Objectif
Synthétiser les recommandations issues des audits réalisés aujourd’hui et les transformer en plan d’action concret, sans régression.

> Règle centrale : **zéro régression fonctionnelle, scientifique et UX**.

---

## 1. Messages clés communs à tous les audits

### A. Le hub doit rester une couche de lancement cohérente
- `CERTUS_HUB.py` doit rester un routeur / launcher.
- Il ne doit pas porter la science métier.
- Il doit imposer des **catégories** et **contrats** de lancement explicites.
- Les modules appelés doivent rester compatibles avec ces contrats.

### B. Les matériaux doivent être distingués correctement
- **Substrat** = support physique.
- **Couche mince** = couche déposée / modélisée.
- Ces notions ne doivent pas être fusionnées.
- Les alias de compatibilité ne doivent pas changer le sens métier.

### C. Les métriques doivent rester séparées
- **RMSE** = erreur.
- **Score** = classement / coût décisionnel.
- **Robustesse** = comportement sous perturbations.
- Les exports et logs doivent refléter cette séparation.

### D. Les configs anciennes doivent continuer à fonctionner
- Les JSON historiques doivent rester lisibles.
- Les presets et anciens champs doivent être tolérés.
- Les alias ne doivent servir qu’à la migration, pas à la réinterprétation.

### E. Aucun refactor ne doit casser la science
- Même entrée, même sortie.
- Même config, même comportement.
- Même workflow, même résultat scientifique à tolérance égale.
- Toute modification doit rester testée et réversible.

---

## 2. Recommandations prioritaires consolidées

### P0 — Verrouillage immédiat

#### 1. `CERTUS_HUB.py`
- Garder le hub strictement comme routeur.
- Maintenir les catégories de modules dans le catalogue.
- Propager le contrat de lancement dans les logs.
- Distinguer clairement les familles :
  - `core_workflow`
  - `materials_specialized`
  - `support_tool`
- Ne pas mélanger le vocabulaire métier du lancement avec la science interne.

#### 2. `CERTUS_STRAT.py`
- Séparer clairement `RMSE`, `robustness_score`, `rmse_p95`, `rmse_mean`.
- Garantir que le RMSE des exports est une vraie erreur, pas un score.
- Corriger le choix du meilleur résultat pour éviter les placeholders `0.0`.
- Conserver le post-check `T_min` comme garde-fou métier.

#### 3. `CERTUS_INDEX.py`
- Maintenir une normalisation de config qui distingue bien :
  - substrat
  - couches minces
- Ne jamais déduire un champ de film à partir d’un champ de substrat.
- Garder la compatibilité des JSON anciens.
- Stabiliser les exports et premiers lancements.

#### 4. `CERTUS_RE.py`
- Conserver la séparation entre substrat, stack et données RE.
- Garder les alias de compatibilité strictement sémantiques.
- Ne pas mélanger paramètres de reconstruction et données d’affichage.

---

### P1 — Consolider les modules métier lourds

#### 5. `CERTUS_INDEX_SPLINE.py`
- Garder le substrat nominal comme base de calcul.
- Maintenir les offsets comme corrections explicites, pas comme matériaux.
- Conserver la traçabilité entre contexte, correction et résultat.
- Éviter de fusionner calcul, optimisation et export dans des chemins confus.

#### 6. `CERTUS_DESIGN.py`
- Garder les matériaux bien alignés avec le design réel.
- Stabiliser l’ordre des couches et les métadonnées d’export.
- Vérifier que le design exporté reflète exactement la pile modélisée.

#### 7. `CERTUS_METAL_SINGLE.py`
- Conserver le substrat transparent comme support.
- Conserver la couche métal comme couche mince.
- Maintenir la séparation physique dans les configs et exports.

#### 8. `CERTUS_METAL_BILAYER.py`
- Conserver la hiérarchie physique : substrat / couche métal / couche intermédiaire.
- Ne pas renommer les couches intermédiaires comme substrat.
- Garder les paramètres physiques et matériau séparés.

---

### P2 — Harmonisation et stabilité

#### 9. `certus_services.py`, `certus_index_utils.py`, `certus_re_helpers.py`, `certus_design_worker_utils.py`
- Cadrer le périmètre de chaque utilitaire.
- Garder des fonctions pures et testables.
- Éviter le repli en mini-god-modules.

#### 10. `certus_strat_context.py`, `certus_strat_service.py`, `certus_re_workers.py`, `certus_spectral_workers.py`, `certus_design_workers.py`
- Clarifier les contrats de contexte et de worker.
- Séparer calcul pur et coordination.
- Limiter l’état implicite.

#### 11. `certus_shortcuts_overlay.py`, `certus_toast_stack.py`, `certus_splash.py`, `certus_skeleton.py`
- Standardiser les comportements UX secondaires.
- Garder un vocabulaire homogène.
- Éviter la duplication visuelle et textuelle.

---

## 3. Recommandations sur les exports et logs

### À maintenir partout
- Les noms de fichiers doivent refléter la bonne métrique.
- Les titres de rapports doivent parler le langage du module.
- Les colonnes d’export doivent garder un sens non ambigu.
- Les logs doivent distinguer clairement :
  - calcul
  - score
  - robustesse
  - RMSE
  - substrat
  - couche mince

### À éviter
- appeler une robustesse “RMSE”
- appeler un support physique “material” de façon générique quand cela brouille le sens
- faire apparaître un champ de compatibilité comme une nouvelle vérité métier

---

## 4. Recommandations sur les configs anciennes

### Principe
Les anciens fichiers doivent continuer à se charger, mais sans modifier la sémantique.

### Autorisé
- alias de migration
- normalisation de nom
- fallback raisonnable de lecture

### Interdit
- changer le sens d’un champ historique
- fusionner substrat et couche mince
- surcharger un alias pour produire un autre modèle métier

---

## 5. Plan d’action consolidé

### Étape 1 — Stabilisation immédiate
1. figer les contrats du hub,
2. verrouiller la distinction RMSE / score / robustesse,
3. verrouiller substrat / couche mince,
4. conserver la compatibilité des configs anciennes.

### Étape 2 — Contrôles de sortie
5. auditer les noms de fichiers exportés,
6. auditer les titres de rapports,
7. auditer les colonnes et logs,
8. corriger les formulations ambiguës.

### Étape 3 — Tests de non-régression
9. lancer les cas de premier lancement,
10. lancer les vieux JSON / presets,
11. comparer les exports avant / après,
12. valider la stabilité scientifique.

---

## 6. Verdict final consolidé

### La suite CERTUS est globalement solide sur le fond scientifique
Mais elle doit encore être renforcée sur :
- la cohérence inter-modules,
- la lisibilité métier,
- la compatibilité des formats anciens,
- la séparation stricte des concepts,
- la surface visible des exports et logs.

### Priorité de la suite
- **P0** : hub, STRAT, INDEX, RE
- **P1** : INDEX_SPLINE, DESIGN, METAL_SINGLE, METAL_BILAYER
- **P2** : services, workers, utils, UX secondaire

### Règle finale
Toute amélioration doit être faite **avec zéro régression**, c’est-à-dire :
- mêmes résultats,
- mêmes fichiers attendus,
- mêmes contrats,
- mêmes significations métiers,
- même compatibilité descendante.
