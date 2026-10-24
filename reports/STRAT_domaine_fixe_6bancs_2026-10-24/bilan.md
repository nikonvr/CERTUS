# Domaine d'indice fixe sur les six bancs officiels (2026-10-24)

**Verdict : ne pas armer `index_corridor_fixed_domain` par défaut.** Les SEEL baissent, mais parce que le domaine fixe
**adoucit le bruit d'indice**, pas parce qu'il trouve de meilleurs plans.

Code `0c759aa2`, graine 42, banc officiel `scripts/bench_examples.py strat` ([pilote](bench_fixed_domain.py.txt)),
un bras sans puis un bras avec le paramètre. Machine partagée avec deux autres calculs : les durées sont gonflées.

| banc | SEEL sans (nm) | SEEL avec (nm) | écart | plantages |
|---|---:|---:|---:|---|
| 48 premium | 0,1531 | 0,1531 | identique au bit | 0 / 0 |
| 75 fast livré | 0,2225 | 0,2116 | −4,9 % | 0 / 0 |
| vrai 35 deep | 0,4643 | 0,2823 | −39,2 % | 0 / 0 |
| 36 deep livré | 0,3238 | 0,2890 | −10,8 % | 0 / 0 |
| r75x2 natif 1 nm | 0,5833 | 0,5160 | −11,5 % | 0 / 0 |
| r75x2 rampes 2 nm | 0,5092 | 0,4999 | −1,8 % | 0 / 0 |

Le paramètre atteint bien le calcul : `FIXED_DOMAIN_PARAM=True` apparaît dans les journaux du bras « avec », et les
résultats changent. Les bras sans le paramètre redonnent au bit les repères §2 de 75c, 36c et des deux r75x2. Ceux de 48c (0,1531 contre 0,1721) et de 35c (0,4643 contre 0,4907) changent depuis `85a9e82f` : la garde de recherche locale est armée, cause probable mais non isolée. Journaux bruts : [journaux_bruts.tar.gz](journaux_bruts.tar.gz) (415 Mo décompressés).

**Pourquoi les deux bras ne se comparent pas.** `corridor_wl_range` (`certus/physics/certus_strat_batch.py`) écrit
δ(λ) = a + b·u(λ), avec u ramené à [−1, 1] sur le domaine. Le domaine fixe, c'est-à-dire toute la plage de balayage (450-700 ou 750 nm),
élargit ce domaine : la partie dispersive de l'erreur d'indice est plus faible dans la bande du filtre. Le bruit noté est donc
plus doux. Signe concordant : sur 35c et 36c, le bras « avec » place en tête d'ELITE des plans à **un seul bloc** (587 / 586 nm)
mieux notés que les meilleurs plans à 5 blocs du bras « sans ». Je n'ai pas mesuré directement l'amplitude, car
l'essai de notation apparié ([sortie](judge_sortie.txt)) s'arrête sur tous ses tirages, faute de reproduire le réglage du banc. Il ne prouve rien.

**Conséquence pour le repère 99 couches** ([A3](../STRAT_A3_C2_99c_2026-10-23/bilan.md)). Il respecte C2, mais il est mesuré
sous ce bruit adouci : la bande de 610-655 nm est normalisée sur 450-750 nm. On ne peut donc pas le comparer aux autres lignes du §2.

**Décision de 👤.** Il faut un domaine qui ne dépende pas du plan **et** qui garde l'amplitude spécifiée dans la bande :
- (a) la grille spectrale seule, au plus près de la décision du 2026-08-10 ; le corridor est alors dépassé aux longueurs d'onde de suivi
  qui sortent de la grille ;
- (b) la plage de balayage, l'état actuel du paramètre, avec un bruit plus doux ;
- (c) la plage de balayage avec un corridor rehaussé pour garder la même amplitude dans la bande.
