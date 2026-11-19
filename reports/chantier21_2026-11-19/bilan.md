# Chantier 21 : polissage mixte (2026-11-19)

**Question.** Un polissage mixte garde-t-il la vitesse du gradient analytique sans la perte sur TOTAL
([chantier 21 du 17](../chantier21_2026-11-17/bilan.md)) ? Une sonde seule, sans changement de `certus/`
([sonde](p21_mixed_polish.py)). Sur chacun des deux exemples, toutes les variantes partent du même point, celui du
polissage de la fenêtre (f = 1,069·10⁻², d = 1700,00 sur TOTAL). Elles ont le même coût et les mêmes bornes, `ftol`
1e-12, et un budget total de 10 000 évaluations.

**Conditions.** Machine chargée par `rescore_plan.py` (chantier 49), avec l'accord de 👤. Les f, d et comptes
d'évaluations ne dépendent pas de la charge ; **les durées, si**, et sont à rechronométrer sur une machine libre.
Un calcul par cas.

| variante | TOTAL : RMSE | d (nm) | coûts | TSIO2 : RMSE | d (nm) | coûts |
|---|---:|---:|---:|---:|---:|---:|
| DF (défaut actuel) | 0,0528398 | 1700,40 | 10 020 | 0,0028304 | 1699,43 | 10 020 |
| AN (option allumée) | 0,0549209 | 1752,84 | 968 | 0,0019482 | 1667,49 | 2 545 |
| AN puis DF | 0,0549209 | 1752,84 | 1 028 | 0,0019482 | 1667,49 | 2 605 |
| AN, cinq d de départ | 0,0509985 | 1799,59 | 8 218 | 0,0019603 | 1666,31 | 9 027 |
| AN, cinq d + départ | 0,0509992 | 1796,62 | 8 589 | 0,0019514 | 1668,29 | 10 001 |
| DF 1 000 puis AN | 0,0552267 | 1800,00 | 1 948 | 0,0019177 | 1667,82 | 3 800 |
| DF 2 000 puis AN | 0,0516511 | 1769,25 | 3 991 | 0,0019202 | 1665,69 | 4 329 |
| DF 3 000 puis AN | 0,0512780 | 1729,79 | 4 709 | 0,0019472 | 1667,66 | 5 551 |
| DF 5 000 puis AN | 0,0512779 | 1731,32 | 7 248 | 0,0019593 | 1667,24 | 6 669 |
| DF 7 000 puis AN | 0,0512783 | 1730,54 | 9 256 | 0,0019553 | 1669,81 | 9 037 |

Sorties : [six variantes](p21_mixed_polish_charge.txt), [balayage du préfixe DF](p21_prefix_scan_charge.txt).

- **AN puis DF ne sert à rien** : les différences finies ne sortent pas du minimum local de AN (déjà vu le 18).
- **DF puis AN, à partir de 3 000 évaluations de DF, bat le défaut actuel sur les deux exemples.**
  - Sur TOTAL : RMSE 0,05128 contre 0,05284.
  - Sur TSIO2 : 0,00195 contre 0,00283.
  - Dans les deux cas, avec moins d'évaluations (4 709 et 5 551 contre 10 020).
  - Avec 1 000 évaluations de DF, TOTAL finit plus mal que le défaut, avec d en butée à 1800. Avec 2 000, le résultat
    tombe entre les deux. Le seuil n'est mesuré que sur ces deux exemples.
- **Plusieurs départs en d** donnent le meilleur RMSE sur TOTAL (0,05100), mais d s'arrête contre la borne haute, 1800 nm,
  pour presque tout le budget.
- **Sur TOTAL, d est mal déterminé** : des RMSE à 0,0513 ± 0,0003 se trouvent entre d = 1730 et 1800 nm. TOTAL ajuste à
  0,05, vingt fois plus mal que TSIO2. Le meilleur RMSE n'y désigne pas une épaisseur sûre.
- Anomalie : « DF 5 000 puis AN » a pris 353,6 s sur TOTAL, contre 5 à 7 s pour ses voisins. Cause non mesurée ;
  probablement la charge de la machine.

**Limites.** Deux exemples, un calcul chacun, en mode local. Les durées sont à refaire sur une machine libre.
