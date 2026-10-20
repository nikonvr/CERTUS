# A7 — Passages de la vitrine à relire (2026-10-20)

Propositions seulement. Page examinée : `pages/CERTUS_STRAT.html`, identique à `96128ba5`, contrôle Git effectué le 2026-10-20.
Les lignes ci-dessous désignent cette version de la page ; les fonctions sont désignées par leur nom.
La page n'est pas modifiée. Une adoption reste une action séparée après accord du propriétaire.

## Sources et vérifications

- **S1** : [D106 et secours Rate, 12 octobre](STRAT_r75x2_D106_secours_Rate_2026-10-12.md), protocole, résultats et limites.
  Les deux JSON de production ont été relus dans le commit d'archive `c98bda64`, puis résumés par `scripts/resumer_artefact_sonde.py` ; aucune simulation nouvelle.
  Ils ont été retirés de l'arbre courant par `81040551` et restent accessibles dans Git.
- **S2** : [r75x0.5 et secours Rate, 12 octobre](STRAT_r75x0.5_secours_rate_2026-10-12.md), résultats et modèle physique.
- **S3** : `certus/physics/certus_strat_growth.py`, `_rate_layer_thickness` : moyenne des références optiques du même matériau ; les couches Rate sont exclues ; le dépôt par tours ne reçoit aucune dérive de source supplémentaire.
- **S4** : [leviers intégrés le 20 octobre](STRAT_r75_leviers_bonne_mere_2026-10-20/bilan.md), §6–§7 : nouvelle recherche locale et comparaison encore limitée des corridors.
- **S5** : [actions A3 et A10](../docs/ETAT_actions.md) : les repères actuels complets et le choix de corridor restent à mesurer.

Contrôle des deux artefacts de S1, nommés `blocs_vs_plantage_r75x2_deep_s101_production_dbf8025f.json` et `blocs_vs_plantage_r75x2_deep_s042_production_dbf8025f.json`, sous `reports/STRAT_r75x2_D106_secours_Rate_2026-10-12/` dans l'archive :

| graine | commit de calcul | stratégies / déposables | meilleur SEEL | familles déposables |
|---|---|---|---|---|
| 101 | `dbf8025f` | 4 175 / 4 175 | 0,5406 nm | 623 mixtes + 3 552 queues Rate |
| 42 | `dbf8025f` | 4 307 / 4 307 | 0,5678 nm | 821 mixtes + 3 486 queues Rate |

Les résumés de ces JSON confirment l'absence de plan optique pur dans leurs listes déposables. Ils ne confirment pas un résultat aux nouveaux défauts du 20 octobre.
Le critère de déposable est un plantage inférieur à 5 % ; le plantage observé du meilleur plan est nul, sans signifier que chaque plan de la liste a zéro arrêt.

## 1. Orientation du lecteur — lignes 97–103

**Actuel.** « the launch pads dropped — the same figure reached with nothing told to the code in advance » ; « three verdicts turned out to describe a realisation and not a stack ».

**Problème.** Le sommaire présente comme acquis actuels des conclusions tirées des évaluations d'août. D106 change précisément la notation des descendants qui les fondaient (S1). Les nouveaux défauts ont encore changé (S4–S5).

**Texte proposé, en anglais :**

> Sections 10.17–10.20 preserve historical search experiments. Their numerical results predate corrections to slit-bias scoring and later changes to the production search. They are not current benchmarks. The dated evidence and limitations below distinguish those experiments from corrected runs; the current production references are being remeasured.

## 2. Références Rate — lignes 1577–1609, §2.10

**Actuel.** « The relative error is not drawn — it is COPIED » ; « A rate layer reproduces the relative error of the last layer of the same material ».

**Problème.** La règle de la dernière référence ne décrit pas `_rate_layer_thickness`. Elle ne correspond qu'au cas particulier d'une unique référence optique. L'hypothèse de vitesse constante est déjà mentionnée aux lignes 1598–1601, mais doit accompagner les résultats Rate (S1–S3).

**Texte proposé :**

> The rate estimate averages the nominal-to-real thickness ratios of all preceding optically deposited layers of the same material. Rate layers add no new calibration measurement. Within a Rate-only tail, the estimate remains fixed and its calibration error remains correlated across layers. The simulator assumes a constant source rate: source drift and intrinsic rate fluctuations are not modelled. Results for Rate plans are conditional on that assumption and have not been validated against a drifting deposition source.

Supprimer ou limiter explicitement à une référence l'égalité et l'explication qui l'accompagnent ; ne pas remplacer une hypothèse de calcul par une affirmation de fidélité à la salle.

## 3. Profondeur de recherche et fente native — lignes 5385–5413, §10.17

**Actuel.** « What actually unlocks it is search depth » ; « Deep alone returns 277 at SEEL 0.625 ».

**Problème.** Le présent transforme une expérience antérieure aux corrections en justification du comportement courant. La configuration à fente native fait partie des repères à refaire dans A3 (S5). S1 ne remesure pas ce cas à fente native.

**Texte proposé :**

> These are historical results for the native-slit configuration, obtained before subsequent scoring corrections. They show what that implementation returned, and do not establish the behaviour of the corrected production pipeline. This configuration must be rebenchmarked before its yield or SEEL is quoted as a current reference.

Conserver les nombres dans une table clairement historique, avec leur provenance ; ne pas les remplacer par les mesures à une autre fente.

## 4. Configuration livrée avec rampes — lignes 5465–5484, §10.18

**Actuel.** « It is now manufacturable, on the production path » ; table donnant notamment 0.5676 nm ; « Three independent noise realisations span 0.55 % ».

**Problème.** S1 signale explicitement que la configuration livrée avec rampes n'a pas été remesurée après D106. Une dispersion entre tirages ne valide pas une formule de notation corrigée depuis. Le niveau statistique annoncé ne doit pas être étendu à d'autres composants ou protocoles.

**Texte proposé :**

> The following table is a historical measurement of the delivered configuration with injected launch pads. It predates the correction that applies slit-bias profiles to refined candidates. This configuration has not yet been remeasured after that correction, so the table is not a current manufacturability or SEEL guarantee. The reported spread concerns the historical calculations only.

La table et ses anciens nombres peuvent rester archivés sous cet avertissement ; ils ne doivent plus constituer le tableau courant des performances (S1, S5).

## 5. Faisabilité fournie par les rampes — lignes 5487–5531, §10.18

**Actuel.** « Why the search cannot get there by itself — measured, not assumed » ; « Launch pads ... supply feasibility ».

**Problème.** La nécessité des rampes et la faisabilité de leurs descendants dépendent de l'évaluation historique. S1 invalide l'usage des descendants notés sans biais de fente comme preuve de faisabilité corrigée. Il ne refait pas toutes les variantes d'août.

**Texte proposé :**

> In the historical implementation, injected plans supplied parents from which ELITE generated the reported candidates. This observation does not establish feasibility under corrected slit-bias scoring, nor does it prove that injection is necessary in the current search. Both claims require a controlled rerun of the delivered configuration and its uninjected counterpart.

Garder la provenance des rampes et leur caractère spécifique au composant. Les pourcentages de rétention de cette section restent historiques.

## 6. Découverte autonome et probabilité de succès — lignes 5544–5584, §10.19

**Actuel.** Titre « The launch pads are no longer needed » ; « That condition is now lifted » ; « Three seeds out of seven find » ; « four seeds give roughly 89 % odds ».

**Problème.** S1 retire ces résultats d'avant D106 des repères valides. Le rapport ne rejoue pas toutes ces graines : il serait aussi faux de remplacer les succès anciens par des échecs non mesurés. La probabilité annoncée ne s'applique pas à un autre pipeline.

**Titre proposé :**

> 10.19 Historical multi-realisation search, and the later scoring correction

**Texte proposé :**

> The August experiments combined plans found by separate search realisations. Their apparent success rate and SEEL predate the slit-bias correction and cannot be used to predict the corrected search. Only the later runs explicitly identified below have been checked after that correction. Unreplayed seeds remain unmeasured under the corrected model.

Supprimer la probabilité de succès du discours actuel ; la conserver seulement comme calcul historique conditionnel, sans recommandation de nombre de relances.

## 7. Tableau de l'union et gains annoncés — lignes 5587–5605, §10.19

**Actuel.** « autonomous union 404+505 », 0.5627 nm, 0.33 % ; comparaison avec 0.5676 nm et 1.67 %.

**Problème.** Les deux lignes sont antérieures à D106 ; leur comparaison n'établit ni le SEEL ni le rendement actuels. Les mesures corrigées de S1 ont d'autres conditions : aucun pourcentage de gain ne doit être calculé entre ces tables.

**Texte proposé pour une table séparée :**

> Corrected historical evidence, measured on 12 October 2026 at commit dbf8025f: r75x2, a 2 nm slit, deep search, no injected launch pads, and that commit's production stop and Rate-rescue settings. Search seed 101 returned 4,175 depositable candidates and a best SEEL of 0.5406 nm; seed 42 returned 4,307 and 0.5678 nm. Every depositable candidate in these two final lists used Rate. The best plan had no observed crash in either run. These are selected search winners, not independent confirmations, and the Rate model assumes a constant source rate. They do not benchmark the production defaults changed on 20 October.

Chaque nombre de ce paragraphe est confirmé par les deux artefacts résumés plus haut et S1. La date et le commit font partie du résultat ; A3 fournira les nouvelles références.

## 8. Série d'épaisseurs et cas ×0,5 — lignes 5621–5643, §10.20

**Actuel.** Table d'août ; « The SEEL is monotone in thickness again » ; « ×0.5 is a genuine open case ».

**Problème.** La ligne ×2 dépend de l'union invalidée comme référence actuelle ; la monotonie ne peut plus être revendiquée sur cette table. S2 décrit ensuite des plans déposables avec secours Rate pour ×0,5. Aucune mesure post-D106 de ×1,5 et ×1,75 n'est établie ici.

**Texte proposé :**

> This table records the August implementation. It does not establish the thickness ordering or manufacturability of the corrected production pipeline. Later Rate-rescue campaigns did find depositable candidates for the half-thickness design under the simulator's constant-rate assumption. The intermediate thickness variants have not been remeasured here under the later production settings. A homogeneous rerun is required before comparing the series.

Sources : S1 pour la ligne ×2 ; S2 pour ×0,5 ; S5 pour les remesures encore ouvertes. Ne pas combiner des lignes d'août et d'octobre pour construire une nouvelle tendance.

## 9. Rate « jamais choisi » — lignes 5647–5654, §10.20

**Actuel.** « zero out of 1510 — offered every time, never chosen » ; « That is the intended behaviour ».

**Problème.** Cette phrase ne décrit pas les deux listes de production corrigées vérifiées dans S1 : tous leurs plans déposables portent du Rate. La répartition demeure dépendante du design, du modèle et de la recherche. On ne peut extrapoler aux deux variantes intermédiaires non remesurées.

**Texte proposé :**

> The August observation that Rate was never selected is historical. In the corrected r75x2 production runs identified above, every depositable candidate used Rate. No updated claim is made here for the intermediate thickness variants. Rate use is an outcome of the stated search and model, not a general property of a thickness scale. Its reported performance remains conditional on a source rate without drift.

Sources : artefacts vérifiés de S1, modèle S3. Aucun nouveau pourcentage de recours au Rate n'est proposé pour les variantes non remesurées.

## Adoption et limites

A7 est une revue documentaire : aucune nouvelle campagne scientifique n'a été lancée pour ce rapport.
Les propositions séparent les expériences historiques, les mesures corrigées datées et les références actuelles encore à produire.
Les résultats des leviers S4 ne sont pas substitués aux bancs complets d'A3, ni à la comparaison multi-graine d'A10.
La limite de vitesse constante est conservée malgré le retrait d'A6 de la feuille de route.

Contrôle effectué : `git diff --exit-code 96128ba5 -- pages/CERTUS_STRAT.html` → code 0 (`PAGE_IDENTIQUE_A_96128BA5=GO`).
Après accord du propriétaire, une autre action pourra intégrer les textes retenus, vérifier les références courantes et exécuter `python scripts/verifier_html.py pages/CERTUS_STRAT.html`.
