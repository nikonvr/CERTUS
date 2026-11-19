# Chantier 49 — reprise

État au 2026-11-18, 22:10. Décision de 👤 : graine 42 seulement, sans plafond.

- [x] Banc : configuration de fenêtre du 23 octobre, multiplicateurs identiques au bit pour le design nominal (5f2f3bbb).
- [x] Graine 42, STRAT sans plafond (master b217c138) : nominal 13 415 s, robuste 11 895 s ; plans consignés
      (`runs/*_s42.plan.json`), rapports de STRAT dans `runs/strat_reports/` (P95 de la phase 4, graine 42 :
      nominal 0,005855 / 0,006025 / 0,006720 ; robuste 0,005057 / 0,005543 / 0,006947 aux bruits 0,025 / 0,05 / 0,1 %).
- [x] Notation sur graines disjointes refusée à tort par le banc : la table de couches de STRAT relit six décimales de
      QWOT, écart d'épaisseur ~1e-5 nm, tolérance relative 1e-9 trop stricte. Corrigé (tolérance de `bench_codesign`).
      L'aller-retour design → multiplicateur → épaisseur hors fenêtre est exact (écart relatif max 2e-16).
- [ ] `rescore_plan.py` sur les deux plans (lancé en fond, attend la fin de la suite UI d'une autre session) :
      rejeu graines 41/42/43 à 300 tirages, doit retrouver les P95 ci-dessus ; puis holdout. Sorties `runs/*.rescore.*`.
- [-] Graines 101 et 202 : abandonnées (👤, 18 novembre : graine 42 seulement).
- [ ] `bilan.md` : SEEL nominal / robuste, part de Rate, blocs, arrêts ; lignes 49, 24, 32 de `docs/CHANTIERS_RESTANTS.md`.
- [ ] Ne pas committer les `runs/*.log` (380 et 430 Mo).

Écarts vus : `export_excel=False` du fichier de fenêtre n'arrive pas au worker (`certus_strat_ui_state.py:1119` le met
à True), d'où les rapports écrits dans `reports/` à la racine, déplacés dans `runs/strat_reports/`.

Premier essai (perdu, 2 160 s) : la fenêtre a reçu un vidage des paramètres du worker ; `wl_range` n'est pas arrivé (grille
1200-1700 nm par défaut) et l'attente de 1 800 s du banc a coupé STRAT. À l'arrêt de l'interprète, le bloc 7 a aussi
journalisé `'StratParamsDTO' object has no attribute 'setdefault'` : chemin d'erreur, origine non trouvée ; à revoir s'il
réapparaît dans un run qui finit.
