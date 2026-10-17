# R2 — lecture des traces natives conservées, 14 octobre 2026

Analyse sans import de CERTUS, sans simulation et sans test pendant A2. Le script figé et
`static_trace_analysis.json` sont dans ce dossier, avec SHA256 des cinq fichiers de données lus.
La première version de comptage est conservée dans `../R2_static_trace/` ; cette version vérifie
aussi les plans derrière les IDs exportés, la chronologie des parents et l’absence de réemploi d’ID.

| Campagne / famille supplémentaire | Propositions tracées | ID et plan présents dans l’export final | ID observé comme parent lors d’un appel ultérieur |
|---|---:|---:|---:|
| Natif conjoint Rate240 / six tours, conjoints | 38410 | 387 | 75 |
| Natif préfixe720 + conjoint480, conjoints | 36358 | 226 | 33 |
| Même campagne, préfixes | 47615 | 491 | 43 |

Les IDs proposés ne sont pas réemployés entre les appels de ces traces. L’export final contient
5412 lignes pour la première campagne,5119 pour la seconde ; aucune ne conserve
`robustness_consensus_meta`. Les nombres « exportés » ne prouvent donc pas une notation pleine
ou un consensus complet. Les candidats historiques ne sont pas tous enregistrés dans ces traces.

Le couple utile **L35–L37 à688 nm** n’apparaît dans aucune des trois familles tracées.
Le préfixe **L1–L5 à613 nm** non plus ; aucune λ de bloc613 n’est présente dans ces propositions.
L1–L5 à600 existe dans3 propositions conjointes de la première campagne,5 de la seconde,
et319 propositions de préfixe. Ce comptage ne dit pas qu’elles ont les autres fenêtres du bon plan.

La fenêtre L35–L37 existe avec d’autres λ dans200 propositions de la première campagne.
Elle peut être héritée du parent tandis qu’un autre segment change : cela ne prouve pas que le
générateur2/4/6 sait créer directement une fenêtre de longueur3. Les neuf plans complets
de comparaison ne sont pas reproduits exactement dans les propositions supplémentaires tracées ;
le test exact inclut partition et λ de tous les blocs, même les blocs au Rate. Une proximité physique
demanderait une analyse supplémentaire, pas une assimilation automatique de signatures distinctes.

Le gagnant brut901054165 de la première campagne n’est jamais parent dans un appel ultérieur de
la trace. Le gagnant brut901457827 de la seconde non plus. Le second n’est pas le gagnant de la
renotation homogène : son point fixe avait échoué ; le pool5119 renoté retient901454694.
Ne pas réhabiliter un gagnant muet à partir de son scalaire exporté.

## Ce que ces données permettent de décider

L’absence des deux couples utiles parmi les propositions enregistrées est mesurée. Ajouter encore
des candidats de la même recette ne démontre pas qu’elle puisse offrir ces couples dans le budget.
La priorité est d’enregistrer **la grille reçue et les λ proposées, les parents complets et les étapes
d’admission**. On pourra alors distinguer une λ absente de la grille, une λ légale jamais proposée,
un bon plan généré mais écarté, et un bon parent sélectionné trop tard.

Les données actuelles ne permettent pas de choisir un quota de sélection comme remède éprouvé.
Un quota et des largeurs impaires restent des hypothèses différentes ; R3 devra en choisir une
après la trace complète. Aucun nouveau gain scientifique ne résulte de cette seule analyse.

## Limites du comptage

- Familles supplémentaires seulement ; chemin historique non exhaustivement tracé.
- Correspondance export sur ID **et** plan structurel ; statut plein/consensus absent.
- Parents enregistrés par ID, pas avec tous leurs champs dans chaque appel.
- Grille native `available_wls`, profondeur réelle, scores de halving et motifs de sortie absents.
- Les fenêtres sont comptées à l’intérieur des frontières de bloc ; ce n’est pas une équivalence
  physique entre deux partitions ni une preuve de causalité.

Prochaine action : préparer une nouvelle copie d’adaptateur de trace, conserver les sources actives,
la vérifier quand la machine est libre, puis une mesure de base tracée au maximum avant R3.
