# Rate : essai natif rate240 (2026-10-13)

Lancé à 19 h 47 min 35 s (Paris), contrôleur 46404, calcul 12568. Budget conjoint 480, budget Rate 240, raffinements par défaut.
Terminé à 20 h 30 min 28 s, 42 min 52 s : **SEEL 0,3828099733 nm**, 4 129 déposables, meilleur 900852003.
Score exactement égal au budget 240 seul (0,03663586891447066), blocs, masque Rate et fente identiques.
Gain contre la référence 3,505 %, aucun gain supplémentaire apporté par le voisinage conjoint.
Une seule modification par rapport à la comparaison consignée dans `prepared.json`. Ordre historique, profondeurs et plafonds conservés.
Sources figées dans `sources/`, SHA256, paramètres et limite de ressources dans `prepared.json`.
`NATIVE_ADAPTER_VERIFY=GO` avant lancement scientifique ; surcharges effectives constatées dans `measurement.log`.
États complets dans `controller.json` et `joint_480_rate240_roundsdefault_s101/etat.json`.
78 appels, 17 770 candidats conjoints ; trace sauvegardée, export corrigé confirmé par cette mesure.
SHA256 de l’artefact : `f91d16af4e54d4f8874c7753596ea5610153191d92a5ad8a30c3db0292fe444b`.
SHA256 de la trace : `1bc10bfc108dbc8cd5fb6a596ebbc410508ffbb99f5afea38f84a2fc051057ee`.
Résumé, comparaison exacte et lecture de trace dans `summary.json`, `budget240_comparison.json`, `trace_analysis.json`.

Le vainqueur apparaît après le troisième tour à huit blocs, sans devenir parent d’un appel observé.
Le meilleur conjoint local exact n’apparaît pas dans les propositions. Cela motive l’essai à six tours ;
ce n’est pas une preuve que le nombre de tours est la seule limite. Le choix des candidats pour la notation complète reste à examiner.
Le plan retrouvé a déjà été vérifié avec les graines indépendantes du contrôle budget 240 ; aucun nouveau gain à confirmer ici.

Une seule mesure à la fois ; arrêt des nouveaux lancements à 9 h Paris, calcul engagé conservé. A2 reste sauvegardée à 3/24.
Aucun défaut scientifique activé, aucun noyau modifié, aucun commit ni publication.
