# Rate : essai natif du voisinage conjoint (2026-10-13)

Calcul natif lancé à 18 h 47 min 54 s, PID 47776, contrôleur 32804, après la fin du raffinement local.
Artefact scientifique sauvegardé à 19 h 29 min 25 s : **SEEL 0,3967147882 nm**, 4 092 plans déposables, meilleur identifiant 900951495.
Même géométrie, masque Rate et fente que la référence ; aucun gain observé. Score 0,03934565579798472.

L’essai cherche à vérifier si le pipeline complet retrouve un gain sans partir d’un plan gagnant injecté.
Budget séparé de 480 voisins conjoints des parents choisis par ELITE ; ordre/budget historiques conservés.
Le choix et la notation des candidats restent ceux de CERTUS, à leurs profondeurs et plafonds existants.
Les scripts expérimentaux sont conservés dans le dossier, leurs empreintes dans `prepared.json` et `controller.json`.

Les contrôles structurels et de routage ont passé entre les mesures : `NATIVE_ADAPTER_VERIFY=GO`.
Option inactive identique dans cinq contextes ; préfixe historique, identifiants, masques, fente/témoins et parents conservés.
La géométrie utile est proposée génériquement au budget 480. Preuve : `adapter_verification.json`.
Affinité 0xffff, Normal, 16 processeurs, 15 threads de bibliothèque ; aucun test pendant le calcul natif.
État du contrôleur : `STRAT_Rate_native_joint_2026-10-13/controller.json`.
État du calcul : `STRAT_Rate_native_joint_2026-10-13/joint_480_s101/etat.json`, réconcilié `complete` sans recalcul.

78 appels au générateur, 16 808 candidats conjoints proposés. Routage observé dans le journal ; la proposition d’un candidat
ne garantit pas sa sélection pour la notation complète (plafond 36 conservé).
SHA256 de l’artefact identique dans le worktree et la copie : `d8fcf45f8f9fbfcc8d237862f7af8ecfc51616d71dc27f9c0cfc3258138e60ae`.

L’export final de la trace a échoué : les dictionnaires retenus partageaient les objets de candidats auxquels le pipeline
avait ajouté un tableau NumPy `slit_profile`. La trace en mémoire de cette tentative est perdue ; les scores, paramètres,
empreintes, compteurs et journaux sont conservés. Preuve de récupération, états originaux et sources dans
`recovery_20261013_1930/`. Aucun arrêt de calcul scientifique, aucun résultat écrasé.
La correction expérimentale détache cette trace par copie profonde et sauvegarde l’état même si un export échoue.
Vérification runtime passée hors mesure : mutation tardive sans pollution de trace, sérialisation JSON et contrats de l’adaptateur.

Confirmation indépendante achevée, `STRAT_Rate_confirmation_native_2026-10-13/attempt_02/`, 7/7 OK.
Le plan natif équivaut exactement à la référence ; le meilleur plan local conserve un gain de 4,57 à 7,13 % sur six groupes.
La recherche native ne retrouve pas encore ce gain. Nouvelle comparaison préparée : Rate 240 à budget conjoint et tours inchangés.

Aucun nouveau défaut scientifique activé, aucun noyau modifié, aucun commit ni publication.
