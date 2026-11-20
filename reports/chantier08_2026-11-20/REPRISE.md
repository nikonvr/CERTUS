# Chantier 8 — reprise

Ordre de 👤 (2026-11-20, ~12 h 35) : « continue le chantier 8 » — pourquoi la population de STRAT varie d'un run à
l'autre au même code (36c graine 42 : 1 436, 1 446, 1 435 stratégies, même premier plan, RESULT à 3e-14 près).
Worktree `sad-perlman-32940e`, branche `claude/busy-visvesvaraya-1d8b72` avancée sur `master` (`ec5603a5`).

- [x] Les deux journaux du 36c au même code (`a059cf47`, chantier 7) : première divergence = `[ELITE-PARENTS] Round 1`,
      SEEL des parents SYM #04–#06 (mêmes id, mêmes longueurs d'onde [522, 450, 481, 461, 471, 461, 469]) :
      0,4639/0,4656/0,4664 contre 0,4648/0,4664/0,4672 ; parents THICKNESS² identiques ; avant : blocs 1 à 36,
      minage (601), criblage, 218 éliminés, consensus (12/383) identiques en texte. Le 35c, lui, est reproductible.
- Lu sans mesure : `_strategy_signature` (clé du cache de consensus) ignore les couches Rate (`_plan_signature` les
  prend) → collision de clé, mais relecture dans l'ordre de soumission : déterministe. L'étage `[LOCAL_SEARCH]`
  d'ELITE (`certus_strat_consensus.py` ~1285) collecte en `as_completed` puis `min` : à égalité de score, choix selon
  l'ordre de fin des threads. Cache Sobol et cache des profils de fente : pas d'écriture en place.
- [x] Deux 36c identiques sur machine libre (`run_deux_36c.sh`, 12:34–12:54, 0 autre python) : A et B rendent
      1 436 stratégies et RESULT 0,03289847734767073, au bit, comme le 20/11 ; journaux identiques pour tout le calcul
      (seules diffèrent des lignes d'ordre d'événements Qt).
- [x] 36c sous charge provoquée (12 processus actifs, `run_sous_charge.sh`, 12:55–13:29, 2 019 s) : **identique au bit**
      aux runs libres (1 436, RESULT …073) → la charge CPU seule n'explique pas l'écart.
- Piste : le cache Numba (`%TEMP%\CERTUS_Numba_Cache\9dcee14023fe`) : `simulate_growth_kernel` compilé à 07:25–07:30
      (dans le banc témoin du matin, la clé ayant changé avec `a059cf47`) puis à 12:08–12:13 (validation, 16 processus) ;
      les runs libres A, B, C ont relu le second. Phénomène connu
      (`reports/refactor_corridors_2026-11-11/cache_numba_arbre_neuf.md`).
- [x] 36c sur cache vierge (`run_cache_vierge.sh`, 13:30–13:47) : **1 446 stratégies, RESULT …969 = le témoin du matin** →
      cause mesurée : le contenu du cache Numba ([bilan](bilan.md)). Docs : CHANTIERS (8 → décision 👤), ETAT §5.
- Bloquant signalé : `coherence_md` rouge sur `master` (`ec5603a5`, poussé) à cause de
  `reports/relecture_html_2026-11-20/bilan.md:19` (« §15 », « §17 » sans nommer la page) ; fusion du chantier 8 en attente.
