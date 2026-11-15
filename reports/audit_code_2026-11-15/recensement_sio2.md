# Recensement — résultats STRAT touchés par le substrat « SiO2 » (C-L4)

2026-11-15. STRAT a calculé le substrat « SiO2 » avec n = 1,48625 à 550 nm (feuilles de couches SiO2 retenues par
`MergedMaterialDict.__contains__`) au lieu du Sellmeier de la silice fondue, 1,45991 (`preuves/p_substrat_sio2.*`).
Le `__contains__` approximatif est présent depuis la création de `certus/utils/certus_strat_db.py` (c2b10301,
2026-05-27) : **tout** résultat STRAT sur substrat « SiO2 » depuis au moins cette date est touché.

Recherche (fichiers suivis) : `git grep -l -E '"substrate(_choice)?"\s*:\s*"SiO2"'` et `git grep -l "JSON-strat-example"`.

## Le juge de paix

`example/example_strat/JSON-strat-example.json` déclare `"substrate_choice": "SiO2"`. Touchés : tous les bancs
`reports/STRAT_bench_juge_de_paix_*` (7 fichiers, 2026-10-04 → 10-12) et les dossiers qui le citent :
`audit_oms5100_2026-11-15`, `STRAT_Rate_suite_2026-10-14` et `-10-15`, `STRAT_domaine_fixe_6bancs_2026-10-24`,
`STRAT_A3_reperes_2026-10-21` et `_reprise`, `STRAT_modele_d_arret_2026-10-12` (+ `_D96_D98`), `STRAT_D100_…`,
`BONNE_MERE_strat_90c_2026-10-23`, `AUDIT_STRAT_top8_apparie_2026-11-10`, `RAPPORT_SYNTHESE_STRATEGIES_BLOCS_35C_48C.md`,
`benchmark_3_modes_results.json`.

## Autres configurations sur « SiO2 » (fichiers par dossier)

| dossier | fichiers |
|---|---|
| `intervalles_99c_premium` | 270 |
| `intervalles_99c` | 270 |
| `controle_random75` | 37 |
| `controle_35c` | 12 |
| `controle_48c` | 10 |
| `serie_echelle_r75` | 5 |
| `intervalles_99c_c2`, `_c2a` | 4 + 4 |
| `BONNE_MERE_strat_90c_2026-10-23` | 4 |
| `STRAT_A3_reperes_2026-10-21`, `_reprise`, `plans` | 1 + 1 + 1 |

## Portée

👤 (expérience) : effet réel mais pas catastrophique, les stratégies STRAT sont robustes à l'indice du substrat.
Gravité ramenée à **majeur** au bilan ; l'écart se chiffre par le juge de paix avant/après correction (SEEL, classement).

- **Faux en absolu** : RMSE, SEEL, épaisseurs, rendements de ces campagnes.
- **Comparaisons internes** (stratégie A contre B, même campagne) : même substrat faux des deux côtés ; l'ordre peut
  tenir quand les écarts sont grands. **Non mesuré** : à remesurer sur le juge de paix après correction.
- **Non touchés** : INDEX, RE, DESIGN, SPLINE (autre résolution du substrat) — à confirmer à la correction.
