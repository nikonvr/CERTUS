# A9 — Préparation statique, 21 octobre 2026

Aucune campagne A9 lancée. A3, A5, A4 et A10 restent prioritaires. Aucun fichier historique modifié.
La demande d'autonomie couvre la préparation et les essais de cette action ; aucun faux `GO_OWNER.txt` ne sera créé.

Le dossier du 17 octobre contient seulement `chain_A9.sh`, la réservation de graines et les empreintes.
Le protocole cité est absent. La chaîne attend un GO écrit, utilise un ancien gel et peut démarrer sous charge
après expiration de son attente : elle ne sera pas relancée. Ses graines réservées et ses fichiers restent intacts.

Protocole proposé, à vérifier et figer avant toute mesure : 99 couches natives, mode premium à 150 tirages,
fente 2 nm, notation à ±0,005, autres paramètres courants identiques. Le choix premium reprend le mode du protocole
historique ; il n'autorise aucune comparaison avec une profondeur différente. Vérifier le chargement réel,
la totalité des 99 couches, les matériaux, les offsets de bruit, le consensus et tous les leviers à l'entrée du moteur.

Réservation avant observation de cette nouvelle étude : recherches **2100211001, 2100211011, 2100211021**.
Confirmation indépendante : G1 = base **2100212001**, consensus **2100212002/2003/2004** ;
G2 = base **2100212011**, consensus **2100212012/2013/2014** ;
G3 = base **2100212021**, consensus **2100212022/2023/2024**. Aucun groupe supplémentaire prévu.
La banque de recherche reste le consensus explicite 41/42/43 ; elle n'est pas une confirmation indépendante.

Pour chaque graine, distinguer cinq étapes, afin de ne pas attribuer un ensemble de changements à un seul levier :

| étape | Rate natif | parents injectés | recherche conjointe Rate | post-raffinement |
|---|---|---|---:|---|
| O | non | aucun | 0 | non |
| R0 | oui | aucun | 0 | non |
| RI | oui | dérivés des parents O natifs de cette graine | 0 | non |
| RIJ | oui | mêmes plans que RI | 480 | non |
| RIJP | oui | mêmes plans que RI | 480 | oui |

O doit fournir des plans complets natifs 99 couches, jamais des plans 75 couches. Geler leurs identités et
empreintes avant de produire les injections. Utiliser les générateurs de paquets Rate existants avec un budget
fixé dans le protocole définitif ; contrôler les 99 couches après conversion. Le nombre de parents et ce budget
restent à arrêter après lecture des contrats du générateur, sans observer de résultat A9.
R0 contre RI isole l'injection ; RI contre RIJ la recherche conjointe ; RIJ contre RIJP le post-raffinement.
Ce dernier conserve faisceau 2, deux passes au plus, 300 propositions par passe et 600 au total, arrêt sans gain.
Les autres étapes doivent porter les mêmes bornes inactives, sans modifier les défauts du dépôt.

Avant confirmation, geler les meilleurs plans complets déposables de chaque étape et leurs empreintes.
Le re-score aux paramètres de recherche doit d'abord reproduire la provenance native ; conserver tout écart.
Puis confirmer les plans figés avec les trois groupes indépendants, même profondeur et même réalisation
de perturbation dans chaque comparaison. Conserver plans, populations, rejets, scores base/consensus,
banques, arrêts par bruit, durées et limites. Un classement de repli n'est ni une référence valide ni un succès.
L'absence de plan déposable donne un constat négatif à SEEL absent, sans réutiliser le repère 99 couches à plusieurs témoins.

Un nouveau pilote devra refuser toute mesure concurrente, chaque emplacement déjà utilisé et chaque lancement
après l'échéance. Les contrôles de raccordement et les bornes ne sont pas encore validés par cette préparation.
