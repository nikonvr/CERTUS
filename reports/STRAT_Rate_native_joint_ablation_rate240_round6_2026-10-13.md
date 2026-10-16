# Rate : ablation du voisinage conjoint, Rate 240 / six tours (2026-10-13)

Lancée à 21 h 32 min 22 s (Paris), contrôleur 49780, calcul 1368. Seule différence avec le profil natif gagnant : budget conjoint 480 → 0.
Terminée à 22 h 18 : SEEL exporté **0,3654948110 nm**, 5 240 déposables, environ 45 min 46 s, aucun candidat conjoint.
Artefact SHA256 `d601d1e118e31773347586161c325a0c754e9ee41c43a1e6b09685f705dbfa5a`.
Ordre historique, budget Rate 240, six tours, profondeurs 300/50/100/300 et plafonds inchangés.
Le gain combiné de 9,24 % ne sera pas attribué au nouveau générateur avant cette comparaison.
L’écart apparent de 1,49 % est ensuite **invalidé comme comparaison à même profondeur effective** : le point fixe de
l’ablation ne reproduit que le score de base 101 (0,03339661422533983), tandis que trois consensus complets donnent
0,03517507293183044. La référence, le meilleur local et le natif conjoint passent leur point fixe.
Verdict strict `FAILED_REPLAY`, sans changement de tolérance ; résultat, simulations, paramètres et journaux préservés dans
`STRAT_Rate_validation_ablation_2026-10-13/`, diagnostic `diagnosis.json`.
Renotation complète des 5 240 plans sauvegardés dans `STRAT_Rate_ablation_consensus_all_2026-10-13/` pour comparer des scores homogènes.
Sources, paramètres et empreintes conservés dans ce dossier. Une seule mesure, 16 processeurs, affinité 0xffff, Normal, 15 threads.
Vérification de l’adaptateur passée avant la mesure ; surcharges effectives et ressources constatées.
État du contrôleur `controller.json`, mesure `joint_0_rate240_rounds6_s101/etat.json`.
Aucun nouveau défaut activé, aucun noyau modifié, aucun commit.
