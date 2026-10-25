# A5 — Tours et budgets ELITE, recherche locale coupée (2026-10-24)

**Verdict : aucun défaut à changer.** Plus de tours ou un budget Rate plus large ne gagnent que 2 à 4 %, dans la
résolution du classement (environ ±5 %, une seule graine). Le budget 40 dégrade nettement le résultat.

`r75x0.5`, deep, graine 101, fente fixe 2 nm, code `4b1514de`, `strat_local_search=false` dans chaque surcharge
([pilote](run_a5.py.txt), sonde `scripts/probe_blocs_vs_plantage.py`). Machine partagée avec deux autres calculs : les durées
sont indicatives. Aucun plan éliminé pour plantage, dans aucun cas.

| surcharge | SEEL du meilleur plan (nm) | écart | durée | couches Rate du meilleur | blocs | stratégies |
|---|---:|---:|---:|---:|---:|---:|
| référence : 3 tours, arrêt actif, budget 120 | 0,3967 | — | 50 min | 65 | 9 | 4 143 |
| 6 tours, sans arrêt | 0,3874 | −2,3 % | 80 min | 65 | 9 | 5 039 |
| 10 tours, sans arrêt | 0,3874 | −2,3 % | 80 min | 65 | 9 | 5 375 |
| budget 40 | 0,4795 | **+20,9 %** | 59 min | 68 | 15 | 3 812 |
| budget 360 | 0,3828 | −3,5 % | 42 min | 61 | 10 | 4 191 |

- La référence redonne le SEEL du 2026-10-21 (0,3967), qui avait la recherche locale active : sur ce cas, celle-ci n'apportait rien.
- 10 tours rendent le même meilleur plan que 6 : rien ne se gagne au-delà du 6ᵉ tour. Contre la référence, le nombre
  de tours et la règle d'arrêt changent ensemble, donc l'écart de −2,3 % ne s'attribue pas à l'un seul.
- Pour gagner aussi peu, il faudrait au moins une deuxième graine. Ces 2 à 4 % ne justifient ni le surcoût de 6 tours
  ni un changement de défaut.

Premier essai perdu : délai de 1 800 s de la sonde dépassé, `RESULT=None` (trace et journaux : [journaux.tar.gz](journaux.tar.gz)). Relancé avec
`CERTUS_BENCH_TIMEOUT_S=21600`.
