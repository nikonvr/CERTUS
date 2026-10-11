# D100 — les interrupteurs de STRAT ne se chargent plus : sans Rate ni biais de fente depuis le 2026-09-08

Question de 👤 (2026-10-11) : *« instruit le rate »* — pourquoi aucun plan Rate dans la campagne `r75x2` du jour
(`reports/STRAT_r75x2_sept_graines_protocole_aout_2026-10-11.md`), alors que `allow_rate` vaut 1 ?

## Ce qui est mesuré

**Les artefacts.** Tous les artefacts de `scripts/probe_blocs_vs_plantage.py` jusqu'au 2026-08-22 (dernier : commit
`5377307`) portent de 427 à 2 554 variantes `RATE_*`. Les huit de la campagne du 2026-10-11 et la contre-épreuve du
99c (`212126d4`, `c3ff6477`) n'en portent aucune, ni aucun plan à couches Rate (`rate_layers`) ; les populations de
banc du 2026-10-04 et du 2026-10-05 (`reports/STRAT_bench_juge_de_paix_b60d80e2_*`, `reports/STRAT_bench_r75x2_deep_hysteresis_*`)
non plus. Aucune population datée entre les deux.

**Les journaux du jour.** Aucune ligne `[RATE]`, que `_expand_with_rate_variants` écrit dès qu'elle produit une
variante ou saute une stratégie, alors que la passe finale sur les survivants a lieu à chaque nombre de blocs
(« Full pass on 25 survivors »…) ; aucune ligne `[SLIT] slit bias active`, que `certus_strat_robustness.py` écrit
quand le biais de fente s'applique.

**À l'exécution** (2026-10-11, STRAT hors écran, configuration chargée comme le fait la sonde, puis `collect_params()`) :

| interrupteur | `cfg_x2.json` | `JSON-strat-example.json` | widget après chargement | `collect_params()` |
|---|---|---|---|---|
| `allow_rate` | 1 | 1 | 0 | False |
| `slit_bias_enabled` | 1 | 1 | 0 | False |
| `search_resolution` | faux | 1 | 0 | False |
| `sym_adaptive_same_wl` | 1 | 1 | 0 | False |
| `sym_prefer_on_tie` | 1 | 1 | 0 | False |
| `sym_allow_hybrid` | 0 | 0 | 0 | False |
| `sym_enable` | 1 | 1 | 1 | True |

Avant tout chargement, les mêmes widgets valent 0, sauf `sym_enable` : les valeurs par défaut de
`set_default_values` (`allow_rate`, `slit_bias_enabled`, `search_resolution` à 1, « the defaults are those of the real
machine ») ne les atteignent pas non plus.

## La cause

`populate_gui_from_config` (`certus/ui/certus_strat_ui_state.py`), par où passent le fichier chargé et les valeurs par
défaut, n'écrit que dans les `QLineEdit` :

```python
for key, widget in self.widgets.items():
    if isinstance(widget, QLineEdit) and key in config:
        widget.setText(str(config[key]))
```

Ces sept réglages sont des `CertusBooleanField` (`certus/ui/certus_ui_widgets_factory.py`), une case à cocher qui
garde le contrat `.text()` / `.setText()` en « 1 » / « 0 » mais hérite de `QCheckBox`, pas de `QLineEdit`. D'après
l'historique, ils le sont depuis `f006e7eb` (2026-09-08, « ux 4.3 : saisie et lecture — booléens… ») ; les artefacts
d'août portent des variantes Rate. `collect_params` lit le widget en premier : le calcul reçoit donc l'état de
construction du widget, quel que soit le fichier.

## Ce que cela touche

Tout calcul STRAT lancé depuis le 2026-09-08 par la fenêtre ou par un script qui passe par
`CertusStratApp.load_configuration` (`scripts/bench_examples.py` et 19 autres scripts de `scripts/`, dont
`probe_blocs_vs_plantage.py`, `probe_armement.py` et `probe_oms_sequentiel.py`) a tourné sans Rate, sans biais de
fente, sans recherche de fente et sans deux options de symétrie, sauf surcharge explicite. En particulier :

- le repère du juge de paix au modèle de `b60d80e2` (ETAT, section 2 : 0,175 nm, `RESULT` 0,007644641198073172) ;
- les mesures des arbitrages STRAT des 2026-10-04 et 2026-10-05 (ETAT, section 3) ;
- la campagne `r75x2` du 2026-10-11 : ses « 7 graines sur 7 » ne comparent pas le même modèle que les « 3 sur 7 »
  d'août, qui avaient le Rate et le biais de fente.

La contre-épreuve du 99c (`scripts\probe_blocs_vs_plantage.py 99c premium 0 0 2 0 42`, 11 min,
`reports/blocs_vs_plantage_99c_premium_s042_20261011_171344.json`) reste non fabricable : 0 déposable sur 205,
contre 0 sur 751 le 2026-08-17 (`reports/blocs_vs_plantage_99c_premium_s042.json`). Mais son plantage minimal tombe
de 100 % à 34 %, et la population est celle d'août moins ses 546 variantes Rate (mêmes effectifs : 178 fusions,
20 et 7 plans structurés) : le modèle sans biais de fente est plus clément.

Sur `r75x2`, les plans identiques d'une population à l'autre (6 à la graine 303, 17 à la graine 404) plantaient à
100 % en août et plantent de 92 à 100 % aujourd'hui : rien n'a été relâché plan par plan, mais ces plans sont parmi
les pires. La famille déposable du jour naît au stade à 75 blocs, où ELITE part des deux plans structurés ; je n'ai
pas mesuré ce qu'en font le Rate et le biais de fente.

## La correction proposée, non appliquée

Une ligne : écrire aussi dans les `CertusBooleanField` (`isinstance(widget, (QLineEdit, CertusBooleanField))`), avec un
test qui échoue sur le code d'aujourd'hui (fichier chargé à 1 → `collect_params()` rend vrai ; valeurs par défaut →
`allow_rate` et `slit_bias_enabled` vrais). Elle change tous les résultats STRAT depuis le 2026-09-08 et redonne aux
fichiers et aux valeurs par défaut leur effet ; il faut ensuite remesurer le repère du juge de paix, la campagne
`r75x2` et ce qui en dépend.

## Reproduire

```bat
python scripts\probe_blocs_vs_plantage.py 99c premium 0 0 2 0 42
```

Le diagnostic à l'exécution : instancier `CertusStratApp` hors écran (`QT_QPA_PLATFORM=offscreen`), appeler
`load_configuration` sur le fichier, puis lire `app.widgets[clé].text()` et `app.collect_params()[clé]` pour chaque
widget `CertusBooleanField`.
