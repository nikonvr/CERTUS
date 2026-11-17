# Recherche locale finale : les deux règles de classement au juge de paix (2026-11-17)

Commande : `python scripts/bench_examples.py strat --auto-yes` ; code : `e6fdac67`. Journal complet (non versionné) :
`juge_de_paix_HEAD.log`.

```
WAIT_EXIT=finished
STRAT_N_STRATEGIES=2560
STRAT_CRASH_ELIMINATED=0/2560
STRAT_RANK00 id=900450739 origin=LOCAL_SEARCH score=0.007257 nblocks=9 wl=[544,604,544,604,574,544,485,453,473]
STRAT_RANK01 id=900450739 origin=ELITE score=0.007300 nblocks=4 wl=[544,485,453,473]
RUN_S=1234.156
RESULT=0.007256533920244745
```

- Règle actuelle (`rank_refined_first` : le plan raffiné premier) : gagnant LOCAL_SEARCH, 0.007257 (SEEL 0.1704 nm).
- Règle « score final » : le plan raffiné (0.007257) bat le meilleur autre (0.007300) : **même gagnant, même résultat**.
- Au banc `73b4835d` : `RESULT=0.007256533920244814`, écart 7e-17.
- Le seul cas mesuré où les deux règles divergent est le banc après C-L4 (plan raffiné 0.007340 contre son parent 0.007335,
  +0,07 %, code d'avant M-L2 et les mineurs) ; ce code n'est plus celui de HEAD.

Conclusion : au juge de paix à HEAD, le choix de la règle ne change rien. Décision de 👤 à éclairer par d'autres exemples si
elle doit être prise ; la règle actuelle reste en place.
