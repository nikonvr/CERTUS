# INDEX et RE sous TBB (2026-11-15)

`python scripts/bench_examples.py {index,re} --auto-yes`, exemples réels de `example/`, couche imposée par
`NUMBA_THREADING_LAYER` (omp ou tbb ; sans repli silencieux), sur `f8ffda2f` + modifications non commitées hors calcul
(chantier 38, délai UX). Une passe d'amorce (`bench_*`), puis trois paires alternées (`rep_*`, `repetitions.txt`).

| module | amorce omp / tbb | OpenMP, 3 essais | TBB, 3 essais |
|---|---|---|---|
| INDEX | 28,5 / 6,0 s | 5,8 / 5,6 / 7,1 s | 5,5 / 5,9 / 5,3 s |
| RE | 28,2 / 18,8 s | 28,0 / 28,9 / 27,7 s | 18,1 / 16,7 / 17,9 s |

- **RE : −38 % (×1,6)**, régulier sur les trois paires.
- **INDEX : aucun gain mesurable** ; les 28,5 s de l'amorce OpenMP étaient la compilation à froid, payée par la
  première passe.
- `RESULT` varie d'un lancement à l'autre sous les deux couches, avec le même étalement (RE : 0,014395 à 0,014407
  sous OpenMP, 0,014397 à 0,014407 sous TBB ; INDEX : 0,002548 à 0,002681) : la non-reproductibilité d'INDEX et de RE
  est déjà acceptée (ETAT §5), TBB ne l'élargit pas sur ces trois essais.
- Non mesuré : l'identité au bit des noyaux de RE sous les deux couches (aucun point d'entrée RE dans le corpus C1).
