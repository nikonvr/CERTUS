# Chantiers restants — 19 novembre 2026

Ouverts seuls (archivés : **31**, **32**, **26** ; bilans : `reports/`). Dépendances d'abord ; C3 (`CLAUDE.md §5`) ; valider entre lots. Décisions 👤 (19/11) : `ValueError` stricte (D108/D109/D114), retrait `ε1 ≥ 1`, `strat_local_search_fresh_id` actif, P3 écartés, **rester dans le dépôt Drive `certus1111`**.

| Lot | Prio | Chantier | Contenu et garde-fous | Fin ou arrêt | Src |
|---|---|---|---|---|---|
| **1a** | P1 | CI (D110) | Ajouter `pytest-benchmark`, `pytest-xdist`, `mypy` (`pyproject.toml` `dev`) + `uv.lock`/`requirements.lock` ; 3 scripts doc (`lint.yml`) ; `mypy` bloquant (`tests.yml`), `bench_kernels` non bloquant. | CI verte PR/push. | G |
| **1b** | P1 | Entrées (D108/D109/D114) | `ValueError` sur `NaN`/`Inf` (`get_nk_from_spline`), `d < 0`, `k < 0`, `n_sub <= 0` en amont Python des noyaux `fastmath` (`optim_prepare_stack_nk_back`, `xyz_from_spectrum`, TMM) ; tests rouges + `c1_diff.py HEAD`. | Invalides refusés ; optimiseurs + 0 bit OK. | G |
| **2a** | P2 | Plancher `ε1 ≥ 1` | Retirer `max(val, 1.0)` dans `epsilon1_TL_analytic` et `_compute_epsilon1_gradient_kernel` ; MAJ tests plancher + vérif `epsilon_to_nk` et 4 ex. | KK + gradient exacts. | — |
| **2b** | P2 | `strat_local_search_fresh_id` | Activer par défaut (exception C1 dans `ETAT.md` §3 au commit) : `strategy_id` unique. | Identifiants uniques ; tests verts. | — |
| **2c** | P2 | SUBSTRATE (05 réduit) | Valider `sellmeier_ir_pole` sur `example/exemple_substrate_index/exemple_substrate_index.xlsx` et `example/database_index/indices RT substrats.xlsx` (Jacobien std écarté). | Bilan dans `reports/`. | [05](../reports/chantier05_2026-11-18/bilan.md) |
| **2d** | P2 | Base dépôts | Apparier T/R ; option TLU pleine plage `> 2200 nm` (C1 off) ; dépôt dans RE (`load_reverse_engineering_from_path`). | `bench_base_depots.py` + tests verts. | [db](../example/database_depots/README.md) |
| **3** | P2 | Repères & gel | Remesurer 6 bancs + 99c (`ETAT.md` §2), puis gel (`tools\build_frozen.ps1` + `release_checks.py`). | `ETAT.md` §2 à jour + gel vert. | — |
| **4** | P3 | SPLINE (21) | Chronométrer nœuds libres + Smart Init (`TOTAL`, `TSIO2`) ; seuil > 20 % et > 5 s. | Dérivées si seuil franchi, sinon archiver 21. | [21](../reports/chantier21_2026-11-19/bilan.md) |

- **Hors-IA (👤)** : 5 PR Dependabot #10–#14 (41, GitHub) ; essais U13 (33, [protocole](../reports/refactor_corridors_2026-11-11/U13_protocole.md)) ; Zenodo `certus_re` & Tikhonravov 1996.

## Sources

- **G** : [audit général 14/11](../reports/audit_general_2026-11-14/bilan.md) · [audit 13/11](../reports/audits_2026-11-13/bilan.md) · [bilan 49](../reports/chantier49_2026-11-18/bilan.md).
