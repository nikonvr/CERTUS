# Rate : confirmation du vainqueur natif après six raffinements (2026-10-13)

Terminé : **9/9 verdicts OK**, point fixe des trois plans puis huit groupes de graines indépendants.
Le vainqueur natif diffère du meilleur local, et reçoit l’identifiant de rejeu 9900000 ; son score de recherche est reproduit.
Profondeurs conservées : 300 tirages complets et trois consensus à 300, mêmes réalisations pour les plans comparés (C2).
Les appels physiques et résultats par bruit sont enregistrés ; aucun plantage observé.

| Groupe | Référence (nm) | Local (nm) | Natif (nm) | Gain natif / référence |
|---|---:|---:|---:|---:|
| control | 0.3967147882 | 0.3653381945 | 0.3600608863 | 9.239 % |
| holdout_202 | 0.3968275691 | 0.3787066495 | 0.3608717921 | 9.061 % |
| holdout_303 | 0.3995131221 | 0.3710397323 | 0.3653610083 | 8.548 % |
| holdout_404 | 0.3997442250 | 0.3719660540 | 0.3663274424 | 8.360 % |
| holdout_505 | 0.3993888246 | 0.3712496806 | 0.3687252866 | 7.678 % |
| holdout_606 | 0.3928222059 | 0.3711503087 | 0.3626817120 | 7.673 % |
| holdout_707 | 0.3972990867 | 0.3696404409 | 0.3721442669 | 6.331 % |
| holdout_808 | 0.3961320607 | 0.3754632919 | 0.3632205049 | 8.308 % |
| holdout_909 | 0.4045376306 | 0.3671169164 | 0.3620838320 | 10.494 % |

Les groupes 808/809/810 et 909/910/911 ont été fixés pendant le calcul natif avant inspection de son vainqueur final.
Les six groupes antérieurs sont conservés. Aucun groupe indépendant ne sert à classer les candidats pendant la recherche.
Le natif améliore le meilleur local sur sept groupes, mais le dégrade de 0,677 % sur 707/708/709.
`summary.json` conserve les comparaisons et les empreintes de l’état, du protocole et du rejeu ; chaque run a son JSON et journal.

Limites : un seul composant, plans fixes sélectionnés, aucun intervalle de confiance formel ni validation machine ou générale.
Le gain du profil combiné n’est pas encore attribué au nouveau générateur : ablation identique à budget conjoint nul en cours.
Aucun nouveau défaut scientifique activé, aucun commit ni publication.
