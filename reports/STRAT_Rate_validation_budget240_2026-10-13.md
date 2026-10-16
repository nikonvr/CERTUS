# Rate : contrôle indépendant du budget 240 (2026-10-13)

Le plan trouvé à budget Rate 240 sur `r75x0.5 deep`, graine de recherche 101, reste meilleur que le plan de référence
sur les deux consensus indépendants préparés avant son résultat. Ce contrôle porte sur **deux plans fixés de cet exemple**,
pas sur une nouvelle recherche ni sur une validation générale de STRAT. Aucun réglage par défaut modifié, aucun commit.

| notation des plans fixes | référence SEEL nm | budget 240 SEEL nm | écart | plantage au bruit de base / doublé |
|---|---:|---:|---:|---|
| contrôle 101, consensus 41/42/43 | 0,396715 | 0,382810 | −3,50 % | 0 / 0 pour les deux plans |
| 202, consensus 202/203/204 | 0,396828 | 0,388957 | −1,98 % | 0 / 0 pour les deux plans |
| 303, consensus 303/304/305 | 0,399513 | 0,385017 | −3,63 % | 0 / 0 pour les deux plans |

Chaque notation conserve 300 tirages par niveau de bruit, un consensus de trois graines à 300 tirages,
la fente de 2 nm, les perturbations de production et les mêmes réalisations pour les deux plans (C2).
Les niveaux sont 0,025 / 0,05 / 0,1 point de transmission. Les scores, moyennes, écarts types et graines réellement
résolues sont dans [le point de reprise complet](STRAT_Rate_validation_budget240_2026-10-13/attempt_02/etat.json).
Chaque consensus contient les trois échantillons attendus. Les comptes de plantage n'établissent pas une probabilité nulle.

## Plans et méthode

Référence `900951015` : optique L1–L6, L11–L12 à 451 nm, L35–L36 à 706 nm ; Rate L7–L10, L13–L34, L37–L75.
Nouveau plan `900851523` : optique L1–L6, L11–L14 à 451 nm, L32–L35 à 706 nm ; Rate L7–L10, L15–L31, L36–L75.
Les partitions complètes, identifiants, scores attendus et empreintes des artefacts source sont dans
[la paire fixée](STRAT_Rate_expertise_2026-10-13/plans_reference_vs_budget240.json).

L'outil appelle `ExternalEvaluationStrategy` avec les paramètres de l'application et son préalable nominal.
La notation physique et son consensus restent ceux du code de production. L'expansion Rate/fente, le secours Rate,
la génération ELITE et le diagnostic d'ablation sont désactivés dans ce seul processus de rejeu : les deux plans restent fixés.
Le transport d'indices réutilise **`SharedIndicesManager` et `SharedIndicesWorker`**, comme les workers du batch.
Sources identiques au A/B : base `da1af082`, deux fichiers expérimentaux figés, cache Numba `caf88a3320c7`.
16 processeurs logiques, affinité `0xffff`, priorité normale, 15 threads de bibliothèque ; une mesure à la fois.

## Premier échec conservé et reprise

Le premier contrôle, à 17 h 04, utilise les indices directement. Il donne 0,03934489424322656 et 0,03663501788493102,
au lieu des scores attendus 0,039345655797984144 et 0,03663586891447066. Il échoue au seuil strict fixé avant mesure
(`rel_tol=1e-7`, `abs_tol=1e-10`) : [artefact conservé](STRAT_Rate_validation_budget240_2026-10-13/control.json),
requête et journaux dans le même dossier. Les graines indépendantes ne sont pas lancées par ce contrôleur.

Cause lue puis éprouvée : `SharedIndicesManager` convertit les indices en `float32` pour les workers du batch ;
l'entrée externe directe gardait leur précision initiale. Le rejeu reprend le **même transport existant**, sans modifier
le code physique ni augmenter la tolérance. La seconde tentative, sauvegardée à 17 h 08 dans `attempt_02`, reproduit
le score du nouveau plan exactement et celui de référence à 5,8·10⁻¹⁶ près. Les masques, blocs, fente et témoins sont contrôlés.
Les trois rejeux terminent avec verdict `OK`, environ 7,5 s par processus ; ils ne font pas la recherche du batch de 40 min.

Script corrigé conservé : [replay_source.py](STRAT_Rate_validation_budget240_2026-10-13/attempt_02/replay_source.py),
SHA256 `144c358b4a57a1de23ac8e97ad7cb6e688c5f93ae23a87211ec27f6eafbd0aaf`.
Les deux tentatives, paramètres, sources, requêtes et résultats sont conservés. Ruff et syntaxe passent ; le contrôle
numérique réel vérifie cette voie de rejeu. Il ne remplace pas une preuve C1 au bit ou la validation complète du code expérimental.

## Limites et suite

Le gain est modeste, inférieur à la marge historique de discrimination d'une recherche isolée. Il se maintient ici
sur les deux consensus distincts ; aucun intervalle de confiance global ni résultat sur d'autres composants mesuré.
La machine réelle, sa stabilité de vitesse entre dépôts et une dérive intradépôt ne sont pas modélisées par ces essais.
Les temps de recherche incluent des états de cache différents et ne prouvent aucune accélération due au code.
Essai suivant : ordre actuel à budget 360, une seule variable supplémentaire, puis étude conjointe fenêtre/longueur d'onde.
