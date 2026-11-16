# Plan des corrections des mineurs (décidé par 👤 le 2026-11-16)

Source : `mineurs_synthese.md`. Méthode du plan des majeurs : par groupe, tests rouges, corrections, tests ciblés
(+ oracle et `c1_diff` si calcul), ruff, un commit par défaut ; une ligne dans `REPRISE.md` par groupe ; validation
complète à la fin ; rien de poussé. Une seule mesure à la fois (banc, validation).

| groupe | mineurs | décision |
|---|---|---|
| G1 STRAT | L2-m1, L2-m2, L2-m3, L2-m6, L3-m7, L4-m4, L6-m1, L6-m2 | L3-m7 : marquer le classement incomplet ; L4-m4 : transmettre k (mesure au juge de paix avant/après) |
| G2 SPLINE | L3-m1, L3-m2, L3-m3, L3-m4, L4-m5 | L3-m3 : mesurer l'écart du corridor |
| G3 entrées, exports, règles | L4-m1, L4-m2, L4-m3, L4-m6 + L5-m4, L4-m7, L1-m1, L3-m5 | L3-m5 : gestionnaire racine |
| G4 DESIGN | L1-m2, L1-m3, L1-m4, L1-m5, L5-m1, L5-m7 | L1-m3 avertir ; L1-m4 réglage inactif par défaut ; L1-m5 graine + ordre fixe ; L5-m1 ne jamais nettoyer |
| G5 FIELD | L3-m6, L5-m3, L5-m5, L5-m8 | L3-m6 graine |
| G6 RE, INDEX, METAL, SUBSTRATE | L6-m3, L6-m4, L6-m5, L6-m6, L5-m6, L1-m6 | L6-m4 le classeur fait foi + avertissement ; L5-m6 pas de lissage auto ; L1-m6 D71 (mesure INDEX avant/après) |
| hors groupe | plancher ε1 d'INDEX | mesurer seulement (décision 👤 ensuite) |

## Fait

G1 `83f0b7c6` `6ee16a4c` `cda58825` `196cb101` · G2 `05aa20dd` `8912a0f6` `7cb9b85d` · G3 `12926141` `0b857568` `015b1788` `df60ad0c` · G4 `4a0d00da` `085411a3` (L1-m4 reporté, chantier 47) · G5 `5e799503` `396efea0` (L5-m5 par la branche des configurations, fusion `e2f15e48`) · G6 `6da29b4e` `12146a9c` `02583592` `0c2791ad`.
