# R3_h03 — confirmation indépendante du gagnant automatique

Les trois groupes pré-réservés sont terminés, codes de sortie0 ; six plans figés avant inspection,
72appels réels à300tirages, base et trois graines de consensus propres à chaque groupe. Plans,
fente2nm, bruit, objectifmean_std/0,35, profondeurs et sources vérifiés. Aucun nouveau candidat,
aucun rejeu ni incident de mesure. Les graines17510001..04/11..14/21..24 sont désormais consommées.

| Comparateur du gagnant98000284 | Groupe1 | Groupe2 | Groupe3 | Moyenne | Médiane | Victoires | Pire perte |
|---|---:|---:|---:|---:|---:|---:|---:|
| Contrôle propreh03,98500001 issu de900754638 | +5,5052% | +4,0078% | +6,1260% | **+5,2130%** | +5,5052% | **3/3** | 0% |
| Natif historique901054165 | +4,1899% | +5,5772% | +6,9459% | +5,5710% | +5,5772% | 3/3 | 0% |
| Meilleur local9900008 | −1,5158% | −1,8201% | −0,1158% | **−1,1506%** | −1,5158% | **0/3** | 1,8201% |
| Référence historique900951015 | +11,4021% | +13,3432% | +15,2935% | +13,3463% | +13,3432% | 3/3 | 0% |

Ces gains portent sur le SEEL apparié de chaque groupe, pas sur le scorebrut ni la moyenne des
scores. Aucun intervalle de confiance n’est déduit de ces trois groupes. Le meilleur local reste
supérieur sur les trois groupes ; le gain est celui d’une chaîne de découverte native expérimentale
par rapport à son propre contrôle, avec coût supplémentaire de raffinement déclaré.

Le gagnant a été fixé avant ces groupes, sans substitution après inspection. Critère principal3/3
favorable satisfait, gain minimum4,0078%, effet non petit : **pas de trois groupes supplémentaires
décidés**. La prochaine phase est R5, intégration minimale inactive par défaut, puis validation de
l’équivalence et du chemin désactivé. Aucune preuve de généralisation de la recherche hors graine101
ni de fonctionnement intégré de production n’est encore acquise. R6 reste conditionnel et borné.

Preuves : frozen_plans.json, seed_reservation.json, protocol.json, controller.json, tous groupes,
complete_audit_01.json et complete_audit_02.json. Le premier audit a passé ses vérifications mais
portait deux diagnosticsRuffRUF034 de conditionsredondantes issus de la copie ; sa source exécutée
est conservée dans audit_source_01_with_lint_findings.py.txt. Le second supprime ces deux conditions,
Ruff passe et les mêmes résultats sont revérifiés, sans aucun appel physique supplémentaire.

Aucun noyau physique modifié, aucun défaut scientifique activé, commit, push ou publication.
