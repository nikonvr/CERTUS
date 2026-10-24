# A3 — Repère 99 couches conforme à C2 (2026-10-23)

**Résultat : SEEL 0,415 / 0,549 / 0,590 nm (graines 101 / 202 / 42), médiane 0,549 nm, 0 % de plantage**, partition
0-22 / 22-42 / 42-76 / 76-99 (quatre verres témoins), mode `fast`, fente 2 nm. Cible du profil : 0,300 nm, non atteinte.

Protocole (commit `2bd41c0d`) : `index_corridor_fixed_domain` armé (**inactif par défaut**). L'erreur d'indice est normalisée
sur toute la plage de balayage, si bien que les quatre tranches et l'assembleur voient la même réalisation par
(graine, tirage). Le cache garde les épaisseurs du niveau de bruit **nominal** (l'ancien code gardait le niveau 2×).
`tests/unit/test_the_99c_assembly_sees_the_growth_realization.py` échoue sur le code d'avant. Les deux défauts sont
décrits dans [l'assemblage écarté](../STRAT_A3_C2_assemblage_2026-10-21/bilan.md).

| graine | tranches déposables (stratégies déposables / testées) | SEEL assemblé | plans déposables au minimum |
|---|---|---|---|
| 42 | 273/273, 271/271, 841/841, 193/193 | 0,590 nm | 193 |
| 101 | 284/284, 207/207, 804/804, 248/248 | 0,415 nm | 207 |
| 202 | 224/224, 259/259, 799/799, 240/240 | 0,549 nm | 224 |

Écart entre graines : 0,415 à 0,590 nm (±17 % autour de la médiane), soit plus que la résolution annoncée (±5,1 %). Il
faut rapporter la médiane et l'étendue, jamais la meilleure graine seule.

Limites :
- 🔴 Le domaine fixe adoucit le bruit d'indice dans la bande (610-655 nm normalisés sur 450-750 nm) : ce repère ne se compare pas aux autres lignes du §2 ([preuve](../STRAT_domaine_fixe_6bancs_2026-10-24/bilan.md)).
- Une seule partition est mesurée sous C2 (celle retenue en 2026-10-21), pas un nouveau classement des partitions.
- Le repère vaut pour le domaine fixe. L'effet de ce domaine sur les autres bancs n'est pas mesuré, et le défaut n'est
  pas changé (décision de 👤).

Sources : [pilote](run_a3_c2.py.txt), [sortie](sortie.txt), cache `reports/intervalles_99c_c2/`.
