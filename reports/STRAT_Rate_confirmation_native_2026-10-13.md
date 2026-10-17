# Rate : confirmation native et du meilleur plan local (2026-10-13)

Nouvelle tentative `attempt_02` terminée : 7/7 verdicts OK, point fixe puis six groupes de graines indépendants, profondeur conservée.
Le vainqueur natif a exactement les blocs, couches Rate et fente de la référence ; la paire de plans est donc référence/meilleur local, sans duplication.

| Groupe | Référence (nm) | Conjoint local (nm) | Gain |
|---|---:|---:|---:|
| control | 0.3967147882 | 0.3653381945 | 7.909 % |
| holdout_202 | 0.3968275691 | 0.3787066495 | 4.566 % |
| holdout_303 | 0.3995131221 | 0.3710397323 | 7.127 % |
| holdout_404 | 0.3997442250 | 0.3719660540 | 6.949 % |
| holdout_505 | 0.3993888246 | 0.3712496806 | 7.046 % |
| holdout_606 | 0.3928222059 | 0.3711503087 | 5.517 % |
| holdout_707 | 0.3972990867 | 0.3696404409 | 6.962 % |

Aucun plantage observé dans les appels physiques enregistrés de chaque groupe. Les distributions par bruit et consensus sont dans les JSON de chaque rejeu.
Protocole fixé avant inspection du vainqueur natif ; deux groupes nouveaux 606/607/608 et 707/708/709.
Les anciens échecs, scripts et états sont conservés ; `summary.json` porte les valeurs et empreinte de l’état.

Limites : un composant, plans fixes, pas d’intervalle de confiance formel ni de validation générale ou machine. La recherche native n’a pas retrouvé le gain avec Rate 120. Aucun défaut activé, aucun commit.
