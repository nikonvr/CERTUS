# Plan — amener STRAT au niveau d'un code éprouvé

Écrit le 2026-08-05, après la découverte que le blocage de STRAT venait d'un paramètre de
bruit dix fois trop grand dans le fichier d'exemple.

---

## 0. Le diagnostic qui commande tout le reste

Il ne faut pas se tromper sur ce qui s'est passé. Le bug n'était pas dur. Il était
**invisible**.

Un `trigger_tolerance` dix fois trop grand a traversé **deux sessions complètes d'analyse
experte** sans que rien ne le contredise. Il a produit un raisonnement entièrement cohérent
et entièrement faux : « le taux de plantage se compose sur 48 couches, donc le critère est
une falaise, donc le composant n'est pas monitorable, donc il faut modéliser le TPM ».
Chaque maillon était juste. L'entrée ne l'était pas.

Deux documents de reprise, des dizaines de mesures, une démonstration probabiliste correcte
— tout cela reposait sur un paramètre que personne n'avait confronté à un instrument réel.

> **Le vrai défaut de STRAT n'est aucun de ses bugs. C'est qu'il n'a pas de mécanisme qui
> hurle quand il est faux.**

Tout ce qui suit est ordonné par cette idée : rendre le modèle **réfutable**, puis le
**réfuter effectivement** contre le réel. La performance vient après, et elle vient loin
après.

---

## Phase 0 — Verrouiller l'acquis (≈ 1 h, à faire en premier)

| # | Action | Pourquoi |
|---|---|---|
| 0.1 | **Décider `trigger_tolerance` de l'exemple → `0.05`** | Décision physique, pas technique. Les trois lignes de mesure sont dans `REPRISE_STRAT_BLOCAGE.md` §2.1. Ne pas y ajouter de marge : le ×2 est déjà dans `robustness_noise_factors`. |
| 0.2 | **Lancer la suite complète (2240 tests)** | **Rien n'a été validé** depuis les correctifs §3 et mes modifications du banc. C'est le trou le plus béant du moment. |
| 0.3 | **Committer** | 11 fichiers modifiés non committés, dont 5 de `certus/`. ⚠️ Le hook `post-commit` pousse vers le dépôt **public**. |

---

## Phase 1 — Rendre le modèle réfutable

C'est la phase qui aurait évité les deux sessions perdues. Elle est peu coûteuse.

### 1.1 🔴 Test de calibration sur l'exemple réel — la pièce maîtresse

Un test qui, sur `JSON-strat-example.json` à `trigger_tolerance = 0.05`, exige :

```
au moins 20 stratégies avec crash_rate < 0,05 ET crash_eliminated == False
```

Coût : un run de STRAT. **Il aurait transformé deux sessions d'analyse en trente secondes de
diagnostic.** Aucun test existant ne regarde la *sortie physique* du module — ils vérifient
des contrats, des formes de tableaux, des signatures. Aucun ne dit « STRAT doit rendre des
stratégies utilisables sur un composant réaliste ».

C'est l'item à plus fort effet de tout ce document.

### 1.2 Table de provenance de chaque constante physique

Auditer **chaque** nombre de `reality_sim_params` et des défauts d'UI, et lui attribuer une
provenance : **mesuré** / **littérature** / **arbitraire**.

Les suspects connus, tous sans provenance documentée à ce jour :

| Constante | Valeur | Provenance |
|---|---|---|
| `trigger_tolerance` | 0,5 → **0,05** | ✅ mesuré (OMS 5100, 2026-08-05) |
| `sim_thickness_probe_offset_ratio` | 120 | ⚠️ examiné, borne basse ~30 connue, mais la valeur 120 elle-même ? |
| `extrema_exclusion_ratio` | 60 | ❓ |
| `non_monotonic_error_factor` | 2,0 | neutralisé — à supprimer plutôt qu'à laisser mort |
| `wavelength_change_penalty` | 1,0 | idem |
| `dynamics_threshold` | 0,025 | ❓ |
| `min_transmission_floor` | 0,10 | ❓ |
| `nucleation_degradation` | 1,4 | ❓ |
| `step0_sigma` | 2,0 | ❓ |
| `robustness_noise_factors` | [0,5 ; 1 ; 2] | ✅ c'est la marge de sécurité, à documenter comme telle |
| `CRASH_RATE_TOLERANCE` | 0,05 | ❓ 5 % de dépôts perdus, est-ce le budget réel d'un atelier ? |

**Chaque `❓` est un `trigger_tolerance` en puissance.**

### 1.3 Analyse de sensibilité globale

Balayer chaque paramètre sur sa plage plausible et mesurer l'effet **sur le classement**,
pas sur `RESULT` seul. Parallélisable, quelques heures de machine.

Objectif : produire la liste ordonnée des paramètres qui pilotent réellement la sortie. On a
découvert `trigger_tolerance` par accident ; un balayage systématique l'aurait sorti en tête
en une heure. Les autres têtes de liste sont les prochains pièges.

---

## Phase 2 — Confronter au réel

**C'est cette phase qui fait la différence entre un code plausible et un code éprouvé.**
Aucune quantité de tests unitaires ne la remplace.

### 2.1 🔴 Reproduire les repères expérimentaux publiés

La thèse Arsac et Zideluns *et al.* donnent des erreurs d'épaisseur moyennes **mesurées en
salle** :

- **0,4 nm** en monitoring PM sur **51 couches**
- **0,3 nm** en P-PM sur **75 couches**

Construire ces deux empilements, les faire tourner au bruit calibré, et vérifier que
l'erreur moyenne simulée tombe dans ces eaux.

- Si oui : **le modèle est validé contre l'expérience.** C'est l'argument qu'aucun
  raffinement interne ne peut fournir.
- Si non : on apprend exactement de combien et dans quel sens il dérive, ce qui est presque
  aussi précieux.

C'est le test d'acceptation du module. Tout le reste est du diagnostic.

### 2.2 Oracle indépendant du noyau de croissance

Le fit parabolique à 3 points qui inverse T → d n'a été vérifié qu'**en un point de
fonctionnement** (§3.5 : écart sous 0,05 nm au ratio 120). Le systématiser : comparer la
racine du fit à la racine **exacte** de T_réel(d) sur une grille (épaisseur de couche × λ ×
erreur amont), et exiger que le biais reste sous **0,05 nm** — le seuil sub-atomique du
projet.

Même logique que la skill `verif-tmm` fait pour le TMM. Le noyau de monitoring n'a pas son
équivalent.

### 2.3 Contrôle de sanité spectral, automatisé

`REPRISE_STRAT_BLOCAGE.md` proposait déjà : calculer le spectre nominal de l'empilement de
l'exemple et vérifier que c'est bien un dichroïque passe-court. « Le contrôle de sanité le
plus rapide », écrivait-il. **Il n'a jamais été automatisé.** Il attrape d'un coup une
mauvaise base d'indices, un mauvais parsing de l'empilement, une convention de signe
inversée.

---

## Phase 3 — Une instrumentation qui ne peut pas mentir

| # | Défaut | Effet |
|---|---|---|
| 3.1 | **Le logger de STRAT écrit dans `certus_certus_re.log`** | Les traces d'un module partent dans le fichier d'un autre. Le classement d'un run n'est nulle part sur le disque. C'est ce qui a rendu le diagnostic d'hier si laborieux. |
| 3.2 | **Cinq sites de levée avant l'unique `finished.emit`** | `RuntimeError("No strategies found.")`, l'assert base matériaux, `generate_excel_report`, `extract_best_rmse`, la validation pydantic du DTO. Tous indiscernables. Leur donner des codes d'erreur distincts. |
| 3.3 | **`extract_best_rmse` a deux pièges dans la même fonction** | Elle rend **0.0** sur liste vide (sentinelle muette qui ressemble à une mesure) et **lève** `PhysicsConvergenceError` si le score vaut exactement 0.0 — ce qui tue le pipeline depuis l'intérieur de la finalisation. |
| 3.4 | **`ab_compare.sh` ne filtre que `RUN_S|COST|RESULT`** | Les lignes `STRAT_RANK…`, `WAIT_EXIT`, `WARN` sont jetées. L'A/B lit un scalaire là où il faudrait comparer un classement. |

✅ Déjà fait le 2026-08-05 : `WAIT_EXIT` distingue les trois sorties du banc, la trace
complète des exceptions est imprimée, `dump_strat_ranking` sort le classement, `AB_WARMUP=1`
neutralise le biais du cache numba.

---

## Phase 4 — Performance, et seulement maintenant

1. **Refaire l'A/B du coût POEM** avec la liste à **cinq** fichiers et `AB_WARMUP=1`
   (commande exacte dans `REPRISE_STRAT_BLOCAGE.md` §4.2). La première campagne était nulle.
2. **La question a changé de nature.** Au bruit juste, `RUN_S` passe de 44 à **201 s** —
   parce que 43 stratégies traversent le Monte-Carlo complet au lieu de 4. C'est le coût
   honnête d'un module qui fonctionne. L'optimiser a maintenant un sens ; l'optimiser quand
   il ne rendait rien n'en avait aucun.
3. Rappel : le premier run d'une campagne n'est jamais comparable aux suivants.

---

## Phase 5 — Ce qui manque au modèle (contribution scientifique)

| # | Sujet | État |
|---|---|---|
| 5.1 | **Verres témoins multiples** | Zideluns *et al.* posent explicitement le problème ouvert : *« the exact definition of when to change the witness glass remains a challenge »*. **La DP sur les blocs est structurellement l'outil qui décide où couper.** C'est une contribution publiable, et elle est à portée. |
| 5.2 | **σ(λ)** | Le bruit OMS 5100 dépend de la longueur d'onde (fort vers 400 et 1100 nm) ; le modèle utilise un σ constant. Écart connu, non traité. Maintenant que σ est calibré, c'est le raffinement suivant. |
| 5.3 | **TPM** | Parqué par le physicien : booléen autorisant le TPM en plus du trigger, en attente parce que l'OMS 5100 ne sait pas basculer en cours de dépôt. Spécifier l'interface sans l'implémenter. |

---

## Ce que je ne ferais PAS

- **Chasser la version de référence `0807`.** Elle servait à comprendre une régression qui
  n'existait pas. Son intérêt s'est effondré avec le diagnostic.
- **Micro-optimiser.** `REPRISE_SESSION_2026-08-03.md` §0.2 a déjà établi qu'il n'y a pas de
  ×2 disponible. Le gain de 10 % sur STRAT est acquis, le reste coûte des nuits pour des
  pourcents.
- **Modéliser le TPM maintenant.** Le physicien l'a parqué, et le composant se monitore très
  bien en coupure de niveau une fois le bruit juste.

---

## Ordre recommandé

```
0.1  décider trigger_tolerance          ← bloque tout le reste
0.2  suite complète                      ← rien n'est validé aujourd'hui
1.1  test de calibration                 ← le meilleur rapport effet/coût du document
2.3  sanité spectrale automatisée        ← une heure, attrape des classes entières d'erreurs
2.1  repères expérimentaux               ← ce qui fait le niveau mondial
1.2  provenance des constantes           ← trouve les prochains trigger_tolerance
1.3  sensibilité globale                 ← les confirme et les ordonne
3.x  instrumentation
4.x  performance
5.x  recherche
```
