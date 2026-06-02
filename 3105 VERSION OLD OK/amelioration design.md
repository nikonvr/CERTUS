# CERTUS_DESIGN — Brief de reprise pour une autre IA

> Ce document est un **mode d’emploi de reprise**.  
> L’IA qui arrive après toi doit pouvoir continuer sans redéduire l’architecture, sans réinterpréter le plan, et sans se demander quoi faire ensuite.

---

## 1. État actuel du dossier

Le module `certus_design` est déjà partiellement modernisé. Il ne faut pas repartir d’une page blanche.

### Ce qui existe déjà et doit être conservé

- `certus/workers/certus_design_engine.py`
  - moteur physique central pour l’objectif / gradient / oblique.
- `certus/utils/certus_design_services.py`
  - service headless déjà en place.
- `certus/workers/certus_design_workers_dto.py`
  - DTOs de frontière des workers.
- `certus/workers/certus_design_worker_utils.py`
  - helpers testables sans UI.
- `certus/workers/certus_design_workers.py`
  - workers PyQt legacy encore présents et à conserver pendant la migration.

### Tests déjà présents

- `tests/unit/test_certus_design_engine.py`
- `tests/unit/test_certus_design_services.py`
- `tests/unit/test_certus_design_workers_dto.py`
- `tests/unit/test_certus_design_worker_utils.py`
- `tests/unit/test_certus_design_config_hooks.py`
- `tests/unit/test_certus_design.py`

### Conséquence importante

L’IA de reprise ne doit pas :

- recréer le moteur physique,
- recréer le service headless,
- recréer les DTOs,
- réécrire le monolithe d’un coup,
- changer la science sans test.

Elle doit **poursuivre la consolidation**.

---

## 2. Ce qui a déjà été fait récemment

Pour éviter les doublons, voici l’état utile à connaître.

### Déjà fait

- le plan du fichier a déjà été réécrit pour être exécutable,
- le service headless a été légèrement durci pour accepter aussi des payloads `cfg` legacy,
- un doublon de test dans `tests/unit/test_certus_design_services.py` a été supprimé,
- `build_needle_scan_mask(...)` accepte maintenant aussi les layers sous forme de dict,
- la résolution du substrat a été centralisée dans `_substrate_key(...)`,
- `OptimWorker` a reçu deux helpers simples et testés :
  - `_clip_min_thickness(...)`
  - `_rmse_from_cost(...)`,
- plusieurs usages de `substrate/Substrate` ont été remplacés par le helper central,
- le lint du workspace est propre sur les fichiers touchés.

### Implication

La prochaine IA ne doit pas repasser par ces mêmes points.  
Elle doit aller directement sur la prochaine micro-étape utile dans les workers ou les helpers.

---

## 3. Ce qu’il reste à faire

### À faire encore

- réduire davantage la densité de `certus_design_workers.py`,
- extraire ou simplifier un petit bloc de logique pure restant dans `OptimWorker`,
- ajouter des tests ciblés si une nouvelle extraction est faite,
- continuer à lisser `NeedleWorker` seulement si une micro-extraction sûre apparaît,
- vérifier que le contrat legacy reste intact sur tout ce qui a été touché.

### À ne pas faire maintenant

- réécrire le worker complet,
- lancer une grosse migration du flux UI,
- toucher à la performance avant la stabilisation finale,
- retirer brutalement les chemins historiques.

---

## 4. Objectif final du module

Le but n’est pas de supprimer les workers legacy immédiatement.  
Le but est de faire évoluer l’architecture vers ce schéma :

```text
UI PyQt
  -> Workers legacy minces
    -> Services headless
      -> DesignPhysicsBridge
        -> certus_physics
```

### Règle absolue

- le worker ne doit plus contenir la logique métier lourde,
- le service doit porter l’orchestration,
- le bridge doit porter la physique centralisée,
- les DTOs doivent rester la frontière d’entrée/sortie.

---

## 5. Règles de travail pour l’IA qui reprend

1. **Toujours commencer par le test le plus proche du code touché.**
2. **Toujours faire une micro-modification à la fois.**
3. **Toujours vérifier qu’on n’a pas cassé le legacy.**
4. **Ne jamais supprimer un chemin historique sans couverture suffisante.**
5. **Ne pas optimiser avant d’avoir stabilisé les contrats.**
6. **Ne pas mélanger extraction structurelle et changement fonctionnel.**

---

## 6. Priorité actuelle exacte

La prochaine IA doit travailler dans cet ordre.

### Priorité 1 — alléger `certus_design_workers.py`

Le fichier reste trop dense.  
Il faut déplacer ou simplifier une seule portion à la fois.

#### Cibles recommandées

- `OptimWorker.run()`
- les helpers de préparation de données
- la séquence d’orchestration finale
- les transitions entre préparation / optimisation / refinement

#### Déjà pris en charge

- le clip minimum de thickness,
- le calcul de RMSE,
- la résolution du substrat via helper,
- la robustification needle dict/layer.

#### Ce qu’il faut éviter

- tout réécrire d’un coup,
- déplacer la science dans un autre module sans test,
- casser les signaux UI.

---

### Priorité 2 — renforcer encore le contrat legacy / DTO

Même si les DTO existent déjà, il faut s’assurer que la compatibilité est bien explicite.

#### Vérifications à faire

- chaque worker accepte toujours un dict legacy,
- la conversion vers DTO reste stable,
- les résultats retournés gardent le format attendu par l’IHM.

#### Fichiers à surveiller

- `certus/workers/certus_design_workers_dto.py`
- `certus/utils/certus_design_services.py`
- `tests/unit/test_certus_design_workers_dto.py`
- `tests/unit/test_certus_design_services.py`

---

### Priorité 3 — extraire seulement les helpers purs restants

Il faut continuer à sortir du worker ce qui peut vivre ailleurs.

#### Candidats naturels

- préparation de données,
- configuration de bornes,
- normalisation de paramètres,
- helpers de post-traitement purement fonctionnels.

#### Candidats à ne pas déplacer sans prudence

- logique qui dépend directement des signaux,
- logique de fallback UI,
- logique où l’ordre des appels peut être observé par les tests.

---

### Priorité 4 — conserver et valider les chemins critiques

Les chemins suivants sont sensibles et doivent rester stables :

- optimisation globale standard,
- mode oblique,
- refinement final,
- needle cached,
- needle fallback,
- color Monte Carlo.

---

## 7. Plan d’action concret, sans ambiguïté

## Étape A — choisir un seul bloc à simplifier dans `OptimWorker`

### Recommandation

Le meilleur prochain pas est de prendre un seul bloc de `OptimWorker.run()` et de le remplacer par un appel plus simple vers un helper ou un service.

### Format attendu

1. lire le test qui couvre le chemin,
2. faire une extraction minimale,
3. conserver exactement le même comportement,
4. relancer les tests ciblés,
5. si tout passe, passer au bloc suivant.

### Exemple de zones possibles

- préparation du runtime,
- build des configurations PGlobal,
- branche finale de refinement,
- branch oblique / normal.

---

## Étape B — garder le bridge comme source canonique

`DesignPhysicsBridge` existe déjà et doit rester la seule implémentation canonique de l’objectif et du gradient design.

### Ce qu’il faut vérifier

- le worker ne redéfinit pas de logique parallèle inutile,
- les tests du bridge couvrent les cas sensibles,
- les chemins obliques passent bien par lui.

---

## Étape C — n’extraire que du code pur

Si une logique ne dépend ni de PyQt, ni de signaux, ni d’état UI, elle peut sortir.

### Règle de sortie

Si un bloc peut être testé avec un simple appel de fonction, il est candidat à extraction.

Si un bloc dépend du timing, de l’ordre des signaux ou de `QThread`, il reste dans le worker.

---

## Étape D — ne pas toucher à la performance maintenant

Le warmup / AOT / optimisation de compilation n’est **pas** la prochaine étape.

### À faire seulement plus tard

- mesurer,
- confirmer la stabilité,
- puis optimiser.

---

## 8. Ce qu’une IA ne doit surtout pas faire maintenant

- ne pas réécrire `certus_design_workers.py` entièrement,
- ne pas supprimer le support legacy dict,
- ne pas casser les signaux PyQt,
- ne pas déplacer de logique scientifique sans test,
- ne pas lancer une phase performance prématurée,
- ne pas ignorer les tests déjà présents pour repartir de zéro.

---

## 9. Check-list d’exécution pour la prochaine IA

Avant chaque modification, répondre oui/non à ces questions :

- Est-ce que j’ai identifié le test qui couvre ce code ?
- Est-ce que je change une seule responsabilité ?
- Est-ce que le legacy reste compatible ?
- Est-ce que je peux vérifier immédiatement le résultat ?
- Est-ce que je laisse la physique inchangée ?

Si une réponse est non, réduire le changement.

---

## 10. Séquence de travail recommandée

La prochaine IA doit suivre exactement cette séquence :

1. ouvrir le test le plus proche du bloc à modifier,
2. identifier la plus petite extraction possible,
3. faire la modification minimale,
4. vérifier lint + tests ciblés,
5. corriger si besoin,
6. seulement ensuite choisir le bloc suivant.

---

## 11. Résumé ultra court pour l’IA qui reprend

**Tu n’as pas à réfléchir à l’architecture.**  
Elle est déjà définie.

**Tu dois faire uniquement ceci :**

1. conserver ce qui existe,
2. prendre un bloc minuscule dans `OptimWorker` ou un helper pur,
3. l’extraire ou le simplifier sans changer le comportement,
4. vérifier les tests,
5. recommencer.

**Ne touche pas à la performance avant la stabilité.**

---

## 12. Recommandation pratique finale

Si la prochaine IA hésite, elle doit commencer par :

- `tests/unit/test_certus_design_engine.py`
- `tests/unit/test_certus_design_services.py`
- `certus/workers/certus_design_workers.py`

et choisir **un seul petit point** à améliorer, pas plus.
