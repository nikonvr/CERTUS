# Recoupement des audits avec le code — 2026-10-20

Portée : [`UXargon.md`](../UXargon.md) (§1 à §13), [`ARGON_contre_audit_Claude_2026-10-17.md`](ARGON_contre_audit_Claude_2026-10-17.md)
(volet UX) et l'outil [`scripts/audit_ux_certus.py`](../scripts/audit_ux_certus.py), contre `certus/ui/`, `certus/metal/`,
`certus/spline/` et `CERTUS_HUB.py` à `4c10ce44`. Lecture du code seulement (grep, fonctions) : aucun programme lancé, aucun
code modifié. Les tableaux du §1.1 (harnais du 2026-10-16) n'ont pas été remesurés : une autre session mesurait STRAT.

## Amendé en place dans `UXargon.md`

| § | Marque | Raison |
|---|---|---|
| 1.3 U01, D08, U08 ; 4.3-1 ; 11.2-1 ; 13 ligne 1 | `[CORRIGÉ]` / `[PARTIELLEMENT CORRIGÉ]` | `868db8c9` (`_collect_config` pur), `bdcae9ed` (couches fixes), `8c6d951b` (axe λ). Reste : `ExportManager.export_excel` appelle `smart_cleanup()`. |
| 4.3-4 | `[PARTIELLEMENT CORRIGÉ]` | `7f3edea8` : le journal dit « shown -> applied » ; plafonds dans `_capped_global_budgets`, pas `run_optim`. |
| 2.3 | `[AMENDÉ]` | Messages réels du validateur cités ; l'info-bulle tombe dès l'attachement (`_validate()` initial). |
| 2.4 | `[AMENDÉ]` | 7 tours, FIELD en a un (dès `0c7c1e2e`) ; INDEX, INDEX_SPLINE et METAL sans aucune cible ; l'étape 3 de RE est ciblée. |
| 3.1, 3.2 | `[AMENDÉ]` | `CertusHub(CertusDialogMixin, QMainWindow)` ; pas de 3 sections ni de 2 colonnes (`hub_grid_columns` → 5) ; `GroupedApplicationCard` jamais instanciée. |
| 4.1, 4.3-9 | texte corrigé | Onglets réels de `plot_tabs` ; `"Couche"` et `"Épaisseur (nm)"` introuvables. |
| 6.2-1 | `[AMENDÉ]` | Cinq `setCurrentIndex(0)`, dont `_display_results`. |
| 6.2-3, 6.3 | `[AMENDÉ]` | `export_results` obéit à l'auto-export du Hub et écrit, horodaté, dans `reports/` : pas d'écrasement ni d'écriture près des données ; le vrai défaut est l'absence d'export manuel. |
| 7.2-2, 7.3 | `[AMENDÉ]` | Smart Init ouvre 2 fenêtres, pas 4 (`aux_dlg` et l'éditeur à la demande) ; tailles et position `+15` introuvables ; `LiveIndexMonitor` fait `550x700` ; fonctions dans `certus_index_spline_mixins_ui.py`. |
| 7.2-3, 7.2-5 | localisation | `n?, k?` : info-bulle de `_build_tab_data` ; `sigma2` : `_build_smart_init_main_plot` ; libellés français dans `eventsextras` et `corridorui` ; `DepositDatabaseDialog` a déjà un filtre (dès `0c7c1e2e`), seul le tri manque. |
| 8.2-3 | `[AMENDÉ]` | DESIGN n'offre plus `Avg` (`1487a7f9`) ; RE l'offre encore. |
| 9.2-4, 10.2-2 | texte corrigé | Toast FIELD réel ; BILAYER a `Dielectric`, pas `n, k`. |
| 12.2 | `[AMENDÉ]` | Pas de `differential_evolution` (ajustements `least_squares`/`minimize`) ; `IndexTableDialog` sans réglages `"SFL"` ; noms réels de ses boutons. |

Les autres constats se retrouvent tels quels dans le code. Le contre-audit du 2026-10-17 reçoit deux notes datées :
`UXargon.md` et `designargon.md` sont suivis, et les sondes de Codex sont en `.py.txt` (`10914d78`).

## Les autres audits, même recoupement

Seuls STRAT (`1eb35535`, `4c10ce44`) et `pyproject.toml` ont changé dans le code depuis le 2026-10-18 au soir.

| audit | amendement |
|---|---|
| [`designargon.md`](../designargon.md) | ALG-01 à ALG-11 tiennent. `[CORRIGÉ bdcae9ed]` sur D08 et la suppression de couches fixes (§7.1) ; `CFG.MIN_THICKNESS` vaut 0,01 nm, pas zéro (§3.2.A) ; citation d'ALG-02 rendue exacte. |
| [`AUDIT_SUITE_CERTUS_2026-10-18.md`](AUDIT_SUITE_CERTUS_2026-10-18.md) | Note datée : l'état de chaque constat est le §4 de la deuxième passe ; audits de la racine et `studies/bonne_mere/` publiés sur `origin`. Numéros de ligne remplacés par des fonctions (REGLES §10). |
| [`AUDIT_SUITE_CERTUS_2e_passe_2026-10-18.md`](AUDIT_SUITE_CERTUS_2e_passe_2026-10-18.md) | C20 à C32 et les ouverts tiennent (D107 à D109, C10, C13, C23 à C26, A23 à A35 non faits). Numéros de ligne remplacés par des fonctions. |
| [`AUDIT_ARGON_code_2026-10-19.md`](AUDIT_ARGON_code_2026-10-19.md) | Note datée : rien des phases 1, 2, 4, 5 n'est fait ; P3.1 et P3.2 non codés ; P3.0 mesuré le 2026-10-20 (deux règles de Bonne Mère perdent sur les trois designs, la recherche locale gagne et entre comme `strat_local_search`, inactive). |
| [`STRAT_audit_declenchement_OMS_2026-10-10.md`](STRAT_audit_declenchement_OMS_2026-10-10.md) | Note datée : D96 à D98 sont le modèle par défaut depuis `8d9ced13` (le rapport les dit options) ; D99 jugé non-défaut ; plancher `tp_hysteresis_floor` ajouté. |

## À savoir

- **`audit_ux_certus.py` ne lit pas de pixels** : `low_contrast_sheets` et `frozen_light_sheets` analysent les feuilles QSS
  déclarées (`sheet_contrast_pairs`), sans `grab()`. Ce que dit déjà §2.1 d'`UXargon.md` ; une mesure de pixels reste à écrire.
- Pistes repérées en passant, non mesurées, hors des audits : `CertusIndexWorkerMixin._on_finished` lance `fit_sellmeier_global`
  (`differential_evolution`) sur le fil GUI ; dans `CertusMetalSingleApp.on_beam_finished`, le commentaire « Auto-select n & k » sélectionne l'index 1 (`Reflectance`).
