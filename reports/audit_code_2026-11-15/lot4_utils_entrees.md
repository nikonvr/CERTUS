# Lot 4 : `certus/utils/` et points d'entrée, revue indépendante (2026-11-15)

Lecture seule : rien n'a été exécuté, aucune amplitude n'a été mesurée.

## 1. Périmètre lu

- **En entier** : `certus_export`, `certus_atomic_io`, `certus_strat_db`, `certus_db_helpers`, `certus_depots_db`, `certus_validation`, `certus_dto`, `tools/frozen_entry.py`, `certus_curve_smoother.py`, `certus_substrate_index.py`.
- **En partie** : `certus_data` (~75 %), `certus_index_utils` (~50 %), `certus_re_helpers` (~30 %, en-têtes Excel), `certus_strat_service` (~25 %), `certus_spectral_preproc`, `certus_re_math`, `certus_reports`, `CERTUS_RE.py`, `CERTUS_HUB.py::launch_module`, `CERTUS_STRAT.py`.
- **Grep seulement** : les ~20 autres modules et `CERTUS_INDEX/DESIGN/FIELD/METAL_*`.
- **Estimation : ~24 %** (~4 500 lignes sur ~19 000).

## 2. Notes

| axe | note | preuves | confiance |
|---|---|---|---|
| Exactitude | 5 | `certus_db_helpers::find_matching_sheets` (C1) ; `certus_re_helpers::parse_re_column_header` (M1) ; `certus_data::load_spectrum_columns` (M3) ; en bien, `RobustMaterialDatabase.get_refractive_index` refuse l'air | moyenne |
| Tests | 5 | `test_certus_re.py::test_parse_headers` : ni `R45p` ni accent ; `test_coverage_boost_96.py::test_to_numeric_exception_handling` vérifie seulement `df is not None` ; `TestPercentNormalisation` sans cas à faible % ; `test_material_merge.py` ne cherche jamais `"SiO2"` | moyenne |
| Architecture | 5 | `certus_material_db.py::MaterialDatabase.__init__` importe `certus.utils` : inversion **physics → utils** non recensée, invisible au cliquet `architecture_debt.json` (import différé) ; `certus_data` remplace `pd.DataFrame.to_excel` globalement ; `build_report_sections` existe deux fois avec des signatures différentes | moyenne |
| Lisibilité | 6 | `certus_atomic_io` exemplaire ; code mort (`NumericValidator`, `StringValidator`, `certus_sample_data`) ; une purge des accents a changé le comportement (`arri[eee]res?`) | moyenne |
| Robustesse | 5 | `read_csv_robust` : le dernier repli perd les `kwargs` ; `validate_material_coverage` ne lève une erreur que si aucun matériau ne couvre la plage ; `SharedIndicesManager._serialize` prend 1.0 par défaut | moyenne |
| Sécurité | 8 | ni `eval`, ni `pickle`, ni `yaml` ; `launch_module` passe une liste d'arguments à `QProcess`, sans shell ; `PathValidator.validate_path` (`commonpath`) ; HTML non échappé (local) ; aucun secret vu | moyenne |
| Reproductibilité | 7 | `calculate_seel_analysis` : générateur graine fixée ; `wavelength_to_index` : clés entières ; à l'inverse, `_THICK_BUF` global (m5) | moyenne |

## 3. Défauts

### Critique (1)

**C1** `find_matching_sheets` et `MergedMaterialDict.__contains__` : par sous-chaîne, `"SiO2"` désigne les 5 feuilles de **couches** SiO2 d'`indices.xlsx` (H400, Syrus, H800, Helios), mélangées par `merge_multiple_curves`. Or `certus_strat_ui_state` nomme le substrat silice `"SiO2"`, `CERTUS_STRAT.py` place `RobustMaterialDatabase` dans `APP_CONTEXT`, `_certus_physics_impl::get_refractive_clues_vectorized` consulte cette base d'abord, et elle teste `in self.materials` avant le Sellmeier. STRAT, SEEL compris, calcule donc avec un substrat fait d'un mélange de couches, sans message. **VÉRIFIÉ en lecture** sur toute la chaîne ; amplitude non mesurée (un appel suffit).

### Majeurs (4)

- **M1** `parse_re_column_header` : avec l'en-tête collé `R45p`, le premier jeton n'est lu que pour R/T. Résultat : 0°, polarisation s, **sans note**, alors que la docstring annonce `R45s1f`. VÉRIFIÉ.
- **M2** `_re_header_normalize_for_tokens` : la regex `arri[eee]res?` passe avant le retrait des accents. « sans arrière » est donc modélisé **avec** face arrière ; seule une note « Unrecognized » le signale. VÉRIFIÉ.
- **M3** La décision % ou fraction se prend par colonne : seuil 1.5 dans `load_spectrum_columns` (INDEX, METAL_SINGLE), 1.25 dans `_re_measurement_values_are_percent` (RE). Un R d'antireflet ≤ 1.25 % ou un T de métal opaque en % est lu ×100, et T et R peuvent être mis à l'échelle différemment. VÉRIFIÉ.
- **M4** `certus_export::iter_plot_data_series` utilise `getData()`, qui renvoie les données « after mapping and data reduction » (pyqtgraph). Un graphe STRAT zoomé (`setClipToView(True)`) n'exporte que les points visibles ; en mode logarithmique, l'export contient log10(y). Mécanisme VÉRIFIÉ ; graphes touchés SOUPÇONNÉS.

### Mineurs

- **m1** `read_csv_robust` : pour un fichier français à 2 colonnes sans en-tête, le séparateur choisi est `,` (l'erreur apparaît plus loin). VÉRIFIÉ.
- **m2** `load_spectrum_columns` : `dropna()` sur toutes les colonnes tronque T à la plage de R. VÉRIFIÉ.
- **m3** `_standardize_dataframe` ne contrôle pas l'unité : une feuille en µm, bornée par `np.interp`, donne un indice constant. SOUPÇONNÉ.
- **m4** `SharedIndicesManager._serialize` jette Im(n) et prend l'air pour une clé absente. SOUPÇONNÉ.
- **m5** `_ratio_theoretical_from_nk` écrit dans `_THICK_BUF`, global, avec des noyaux `nogil` appelés depuis des threads. L'appelant actuel utilise un `d` fixe. SOUPÇONNÉ.
- **m6** Les exports Excel ne sont pas atomiques, contrairement au HTML. VÉRIFIÉ.
- **m7** `generate_html_report` n'émet pas de `<meta charset>` : λ et µ risquent d'être mal affichés. VÉRIFIÉ.

## 4. Bien fait

- `atomic_open` : fichier temporaire voisin, `fsync`, `os.replace`, nettoyage ; utilisé dans 14 fichiers.
- `RobustMaterialDatabase.get_refractive_index` lève `KeyError` au lieu de renvoyer l'air, raison écrite.
- `_match_root` : la frontière non alphabétique évite `theta` → T, et le défaut corrigé est documenté.
- `parse_re_column_header` refuse les indications de face arrière contradictoires.
- `tools/frozen_entry.py` documente le piège de PyInstaller.

## 5. Recommandations

1. **Matériaux** (½ j et une mesure) : nom exact, puis Sellmeier, puis correspondance floue sur option ; test « `SiO2` donne le Sellmeier ». Les bits changent : décision de 👤.
2. **Unités** (1 j) : une seule décision % par fichier, éclairée par les jetons `%` ; un journal dans les deux cas ; un refus entre 1 et 1.5 ; des tests pour un antireflet et un métal.
3. **En-têtes RE et export** (3 h) : découper `^([RT])(\d+)?([sp])?`, retirer les accents avant les regex ; tester `R45p` et « sans arrière » ; lire `getOriginalDataset()`.
