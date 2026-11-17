# Chantier 44, étapes 3 et 7 — sensibilité du classement STRAT aux hypothèses non mesurables, 2026-11-17

Sonde `scripts/probe_modele_lecture.py` (variantes ajoutées : `livre_corrige_niveau`, `livre_corrige_attente_echelle1`),
juge de paix (`example/example_strat/JSON-strat-example.json`), 120 premiers plans du banc
`STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json`, 300 tirages, pire des trois niveaux de bruit, porte de
plantage 5 % ; sur `a6761fa7`, 72 s. Sortie complète : [txt](sonde_120_plans.txt), [json](sonde_120_plans.json).
Référence : le modèle de production (`livre_corrige_attente` : ancres et arrêt exacts, attente sans fin).

| variante | plans déposables / 120 | Spearman avec la production | rapport médian des scores | meilleur plan |
|---|---|---|---|---|
| production | 106 | — | — | rang 11, 0,007421 |
| R2 : arrêt au niveau (`arming` 0) | 120 | 1,000 | 1,000 | rang 11, 0,007421 |
| R2 : arrêt tardif (`arming` 1) | 120 | 1,000 | 1,000 | rang 11, 0,007421 |
| R10 : étalonnage photométrique ±1 % (`affine_scale_amp` 0,01) | 106 | 0,992 | 1,000 | rang 11, 0,007422 |
| ancien modèle (`livre`) | 120 | 0,915 | 0,991 | rang 11, 0,007477 |

- **R2** ne change ni l'ordre ni les scores des plans déposables ; l'attente sans fin élimine 14 plans que les deux
  autres arrêts gardent. **R10** à 1 % : classement quasi inchangé, même gagnant.
- Non sondés, faute de paramètre dans le noyau (« noyau intact » de l'étape 3) : `SWING_MIN` en multiples de A, bruit
  proportionnel à T ; ni les options physiques des étapes 4 à 6 (R3, R4, R6, R7, R8).
- Le 2026-10-12, le même banc ne donnait que 6 plans déposables sous l'attente sans fin, contre 106 ici : les noyaux
  ont changé depuis ; écart non expliqué ici.
- La notation réduite de la sonde met l'échelle et le décalage affines à 0 hors R10 ; le juge de paix porte
  `affine_scale_amp` = `affine_offset_amp` = 0, alors qu'`ETAT.md` §3 écrit 0,05 et 0,02 : non tranché ici.

**Décision de l'étape 7** (déléguée par 👤 le 2026-11-17) : rien ne s'active. Le modèle de production reste l'attente
sans fin, l'hypothèse la plus pessimiste des trois, sans effet sur l'ordre des plans déposables ; l'étalonnage reste
supposé parfait (sensibilité de l'ordre à 1 % : Spearman 0,992). Les étapes 4 à 6 ne sont pas codées : leur
justification était de savoir quels leviers méritent le code, et les deux hypothèses mesurables ne déplacent pas le
classement. Aucun noyau touché (C1).
