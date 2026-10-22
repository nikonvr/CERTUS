# Garde de l'étage au corridor configuré : confirmation sur les dix cas A14/A10 (Claude, 2026-10-22)

Code `7b175249` (`claude/2026-10-22`), surcharge `strat_local_search=true,strat_local_search_guard=true`, lanceur
`run_garde_panel.py.txt` dérivé de celui d'A14/A10, mêmes bancs et mêmes graines de jugement. Le lanceur s'arrête si le rapport
de l'étage n'a pas `guard_index_corridor` : la garde a atteint le calcul dans les dix cas. Tables brutes :
[A14](../STRAT_garde_A14_2026-10-22/bilan.md), [A10](../STRAT_garde_A10_2026-10-22/bilan.md). Analyse sans garde :
[réanalyse](../ANALYSE_claude_2026-10-22/bilan.md).

| cas | sans garde | avec garde |
|---|---|---|
| r75x2 s101 | accepté : ±0,005 0,5383 → 0,5959 nm (+10,7 %), ±0,010 −1,7 %, arrêts 0 → 2 | **repli (28 changements)** : ±0,005 0,5383 → 0,4787 nm (**−11,1 %**), ±0,010 0,6854 → 0,6256 nm (−8,7 %), arrêts 0 → 0 |
| neuf autres | — | statut, SEEL et arrêts identiques aux résultats sans garde |

Au corridor configuré, la garde a refusé le plan final de r75x2 s101 (P95 0,0707 → 0,0879) et accepté le repli
(confirmation : 0,0705 → 0,0566, 0 arrêt). **Avec la garde, le critère écrit d'avance (aucun SEEL dégradé, aucun arrêt
ajouté, gain sur la majorité, tenue à ±0,010) est tenu sur les dix cas.** Coût : deux évaluations de contrôle de plus par
plan jugé, négligeable devant la recherche. Limites : une graine de banc par cas ; le seuil des points tournants à bas
bruit (cause du cas corrigé) n'est pas changé.

Décision de 👤 : armer `strat_local_search_guard` par défaut (changement de défaut, C1 rompu volontairement pour l'étage).
