# CERTUS Hub → Module Contract Standard

## Objectif
Définir un contrat unique de lancement et de cohérence pour tous les modules lancés depuis `CERTUS_HUB`, sans casser les comportements existants.

> Règle absolue : **zéro régression fonctionnelle, scientifique et UX**.

---

## 1. Principe général

Le hub ne doit pas seulement exécuter un script.
Il doit lancer un module identifié par :
- une **catégorie métier**,
- un **rôle fonctionnel**,
- un **niveau de criticité**,
- un **contrat d’entrée**,
- un **contrat de sortie**.

Le hub reste une couche de composition et de navigation.
Il ne doit pas contenir la logique scientifique des modules appelés.

---

## 2. Catégories de modules

### A. Modules cœur métier
Modules qui portent un workflow scientifique complet.

Exemples :
- `CERTUS_DESIGN.py`
- `CERTUS_RE.py`
- `CERTUS_STRAT.py`
- `CERTUS_INDEX.py`
- `CERTUS_INDEX_SPLINE.py`

**Attentes :**
- paramètres structurés,
- logging complet,
- exports,
- compatibilité avec les configurations existantes,
- tolérances numériques stables.

### B. Modules spécialisés matériau
Modules centrés sur des cas physiques spécifiques.

Exemples :
- `CERTUS_METAL_SINGLE.py`
- `CERTUS_METAL_BILAYER.py`

**Attentes :**
- distinction stricte entre substrat et couche mince,
- conventions matériau stables,
- résultats physiquement cohérents,
- pas de mélange sémantique des champs.

### C. Outils secondaires
Modules utilitaires ou de support.

Exemples :
- `certus_curve_smoother.py`
- `certus_substrate_index.py`

**Attentes :**
- contrat plus léger,
- dépendances minimales,
- comportement clair et isolé,
- pas de dépendance implicite aux gros workflows métier.

---

## 3. Contrat d’entrée standard

Chaque module lancé par le hub doit recevoir une entrée cohérente selon sa catégorie.

### Champs obligatoires recommandés
- `module_name`
- `module_category`
- `launch_origin`
- `working_directory`
- `config_path` si applicable
- `source_file` si applicable
- `last_used_parameters` si disponibles
- `safe_mode` ou équivalent si le module le supporte

### Règles
- un module cœur métier peut recevoir une configuration complète,
- un outil secondaire peut recevoir une configuration simplifiée,
- un module matériau doit recevoir des champs explicitement séparés pour substrat et couches minces,
- aucun module ne doit supposer qu’un champ ambigu signifie la même chose partout.

---

## 4. Contrat de sortie standard

Le hub doit pouvoir interpréter les sorties de manière homogène.

### Champs recommandés
- `status`
- `exit_code`
- `module_name`
- `module_category`
- `duration`
- `warnings`
- `errors`
- `artifacts`
- `report_paths`

### Règles
- un code de sortie ne doit pas être sur-interprété,
- une erreur métier doit être distinguée d’un arrêt utilisateur,
- un export réussi doit remonter clairement ses artefacts,
- les messages doivent rester lisibles et stables.

---

## 5. Distinctions métier obligatoires

### A. Substrat vs couche mince
C’est une règle de base.

- `substrat` = support physique
- `couche mince` = couche déposée / modélisée

Ils ne doivent pas être fusionnés sous un même concept générique si cela crée une ambiguïté.

### B. Score vs RMSE vs robustesse
- `RMSE` = métrique d’erreur
- `score` = valeur de classement / décision
- `robustesse` = comportement sous perturbations

Ces notions ne doivent pas être échangées entre elles dans les exports ou les logs.

### C. Config vs résultat
- une configuration décrit l’intention de calcul,
- un résultat décrit ce qui a été obtenu.

Le hub et les modules doivent les distinguer clairement.

---

## 6. Comportement de lancement attendu

### Obligatoire
- vérification de l’existence du script,
- message de lancement clair,
- gestion propre des erreurs de démarrage,
- tracking des processus actifs,
- nettoyage correct à la fin.

### Recommandé
- journaliser le début et la fin de lancement,
- catégoriser l’application dans le message,
- conserver un comportement uniforme pour tous les modules.

---

## 7. Zéro régression

La cohérence ne doit pas modifier le sens scientifique ou fonctionnel.

### Interdictions
- changer les valeurs par défaut sans raison validée,
- réinterpréter un champ historique,
- fusionner des concepts métier distincts,
- modifier les exports attendus sans versionnage,
- casser les fichiers de configuration existants.

### Vérifications minimales
- même module lancé, même résultat,
- même config, même état final,
- même entrée, même export,
- même stratégie, même classement,
- même substrat, même interprétation.

---

## 8. Priorités d’implémentation

### P0
- ajouter une catégorie par module dans le catalogue hub,
- faire passer cette catégorie dans le lancement,
- standardiser les logs et erreurs,
- verrouiller substrat vs couche mince.

### P1
- formaliser les contrats de sortie,
- documenter les modules cœur métier,
- différencier les outils secondaires.

### P2
- enrichir les métadonnées,
- harmoniser les descriptions,
- améliorer les raccourcis et l’affichage.

---

## 9. Conclusion

`CERTUS_HUB` doit rester un **launcher cohérent**, pas un second moteur métier.

La bonne stratégie consiste à :
- déclarer explicitement la famille de chaque module,
- imposer un contrat minimal commun,
- préserver les spécificités métier,
- et vérifier chaque modification avec une exigence stricte de **zéro régression**.
