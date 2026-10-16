# Contrôle indépendant du voisinage fenêtre/λ (2026-10-13)

Le plan conjoint `9600579` améliore le SEEL sur les quatre groupes indépendants.

| Groupe de consensus | Référence (nm) | Budget 240 (nm) | Fenêtre/λ (nm) | Gain contre référence |
|---|---:|---:|---:|---:|
| 41/42/43 | 0.396715 | 0.382810 | 0.365338 | -7.91 % |
| 202/203/204 | 0.396828 | 0.388957 | 0.378707 | -4.57 % |
| 303/304/305 | 0.399513 | 0.385017 | 0.371040 | -7.13 % |
| 404/405/406 | 0.399744 | 0.382936 | 0.371966 | -6.95 % |
| 505/506/507 | 0.399389 | 0.383116 | 0.371250 | -7.05 % |

Tous les points fixes sont reproduits avant les holdouts, tolérance inchangée ; chaque rejeu rend `OK`.
Les trois plans reçoivent les mêmes graines et profondeurs. Aucun plantage observé sur ces replays.
Le plan utilise optique L1–L6, L11–L14 à 451 nm, L33–L34 à 630 nm ; les autres couches sont Rate.

La recherche de 958 propositions conserve 300 tirages par candidat et trois consensus de 300 pour les admissibles.
Les groupes indépendants 202/203/204, 303/304/305, 404/405/406 et 505/506/507 ne choisissent pas les propositions.
Les deux premiers avaient déjà servi au contrôle du budget 240 ; les deux derniers sont annoncés avant le rejeu conjoint.

Limites : un seul composant, plan fixé issu d’une recherche locale autour d’un parent connu ; aucun gain de temps de code établi,
aucune validation générale ni mesure de stabilité réelle du Rate. Aucun changement de défaut scientifique ou de noyau.
Aucun commit ni publication. Une recherche native complète devra vérifier que le générateur retrouve ce voisinage.

Plans SHA256 : `30259645de7187f26e5fd19818454206a22a8129b7a2e86297022e43834b55a5`.
Rejeu SHA256 : `9bfe04e96215e11efce9be38a23463661386103e644fbf52af30430a175b9726`.
Source, paramètres, graines, masques, profondeur, transport d’indices et empreintes dans chaque JSON.

Le mouvement conjoint franchit un obstacle pour une recherche qui ne conserve que les améliorations séparées :

| Modification depuis le plan budget 240 | SEEL sur le consensus 41/42/43 |
|---|---:|
| Fenêtre L33–L34, λ conservée à 706 nm | 0.426482 nm |
| λ 630 nm, fenêtre conservée L32–L35 | 0.902766 nm |
| Fenêtre L33–L34 et λ 630 nm ensemble | 0.365338 nm |

Les deux mouvements isolés dégradent le parent (0,382810 nm) ; leur combinaison l’améliore.
Les 958 propositions ont 370 consensus complets, 581 scores de base non finis et 7 consensus incomplets ;
les 588 exclusions sont conservées. La meilleure fenêtre seule est à 0,391177 nm ; la meilleure λ seule à 0,381531 nm.
Cela étaye un voisinage conjoint ; cela ne prouve pas que les plafonds et filtres actuels d’ELITE le sélectionneront.
