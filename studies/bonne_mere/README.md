# Bonne Mère — sujet clos le 18 octobre 2026

## Stratégie conservée

**96 couches H800 sur saphir, un témoin, deux précoatings, 70 couches optiques et 26 Rate. Longueur d’onde commune de 452 nm sur les deux précoatings et les deux premières couches pièce.**

Les épaisseurs et le monitoring des couches pièce 3 à 96 restent ceux du plan 70 POEM retenu. C’est le choix explicite de Fabien comme solution la plus prometteuse.

## Documents à ouvrir

- [Dossier complet de 25 pages en PDF](dossier_final/Bonne_Mere_Dossier_Complet.pdf)
- [Version Word modifiable](dossier_final/Bonne_Mere_Dossier_Complet.docx)
- [Passation pour une reprise ultérieure](PASSATION.md)
- [Plan complet des 98 opérations](dossier_final/donnees/monitoring_retenu_98operations.csv)
- [Sélection courante et chemins des données](selection_retenue.json)
- [Bilan du nettoyage](dossier_final/rapport_nettoyage.json)

## Résultat et limite à conserver

Confirmation sur trois graines indépendantes, 1 000 tirages par bruit et graine : au bruit 0,05, RMSE moyen **1,667858 point**, contre **1,691515** pour la référence 70 appariée ; P95 RMSE **1,870153**, SEEL P95 **0,833795 nm**. Arrêts aux bruits 0,025 / 0,05 / 0,10 : **0 / 0 / 1 sur 3 000**. Aucun holdout indépendant final du candidat 452 nm : le critère strict zéro arrêt n’était pas satisfait. Pas de qualification expérimentale ni de preuve d’optimum global.

## Rangement

Les sources, scripts, protocoles, journaux textuels, plans et audits sont conservés dans `archives/Bonne_Mere_sources_et_metadonnees.zip`. Une compression interne TAR/XZ déduplique les contenus ; `archive_index.json` conserve tous les chemins d’origine. Les six cohortes appariées du candidat 452 nm et de sa référence restent accessibles dans `dossier_final/donnees` sous forme de tableaux sans perte.

Les autres sorties brutes volumineuses et les caches ont été supprimés sur demande, pour maintenir **CERTUS entier, Bonne Mère inclus, sous 1 000 000 000 octets**. Il n’existe pas d’archive extérieure. Les anciens audits ne sont pas tous rejouables sans recalculer les sorties éliminées.

Aucun calcul actif ; suivi automatique suspendu. La reprise nécessite une nouvelle demande humaine.
