# Audit intégral de CERTUS_STRAT.html — 31 octobre 2026

**Verdict sur la version initialement auditée : la page n'était pas conforme au code.** Lecture des 5 997 lignes et des 110 titres, suivie du rapprochement avec les fonctions appelées en production. **28 constats** sont détaillés ci-dessous ; un constat peut regrouper plusieurs occurrences d'un même problème. Ce nombre ne constitue pas un pourcentage de conformité.

## État après les corrections demandées

Les 28 constats ont donné lieu à des corrections dans la page : texte, formules, schémas, noms d'API, portée des contrôles et séparation des réglages de profil et des replis de l'interface. Les résultats historiques restent datés ; les chiffres non reproduits ou incohérents ne sont pas présentés comme des validations actuelles. La distinction entre SEEL de classement et SEEL calibré dans l'interface est explicite. Le code de calcul n'a pas été modifié.

Les empreintes et résultats des contrôles de cette correction sont consignés séparément dans la section `correction` de `preuves.json`. Le périmètre et les constats ci-dessous décrivent l'instantané initial ; son empreinte est conservée pour identifier exactement ce qui a été audité.

## Périmètre et preuve

- Page auditée : [CERTUS_STRAT.html](../../pages/CERTUS_STRAT.html), dans son état de travail, déjà modifié avant l'audit.
- Référence Git : `master`, tête `6a5a7296`. Comparaison avec les fichiers présents, pas avec une ancienne révision décrite dans les campagnes.
- Empreinte SHA-256 de la page : `480f3f309958d9ed1fe5c92442eed6e493863ebd18934f400f34863ea4bac2ab` ; 479 853 octets.
- Préparation du dépôt : `preflight.py` a donné `PREFLIGHT=GO` ; `orient.py` consulté.
- Contrôle formel déjà exécuté : `python scripts/verifier_html.py pages/CERTUS_STRAT.html`, code de sortie 0 ; 26 ancres, 25 renvois internes, 0 point signalé. Les destinations locales des liens HTML explicites existent. Cela vérifie la structure, pas les affirmations scientifiques.
- Les tests existants ont été consultés pour leur portée, **pas relancés** : une validation extérieure à cet audit exécute déjà `pytest tests/unit/`. La règle du dépôt interdit une seconde validation simultanée. Aucun résultat de cette exécution en cours n'est attribué à l'audit.
- Aucune campagne Monte-Carlo ni mesure de performance historique n'a été reproduite. Les chiffres dont la source locale manque restent non vérifiés.
- Aucun code ni aucune page HTML modifiés par cet audit. Inventaire de lecture et limites dans [preuves.json](preuves.json).

Priorités : **P1** = description erronée du modèle, du score ou d'une garantie d'acceptation ; **P2** = paramétrage, algorithme secondaire, architecture ou présentation à corriger. Ce sont des écarts documentaires ; ils ne désignent pas tous un défaut du programme.

## Écarts P1

### A03 — Le modèle d'arrêt livré et une cause de crash manquent

§2.6 ne décrit que trois causes de crash ; §11.1 présente le remplacement de l'inversion parabolique comme une piste écartée. Or [`stop_model_flags`](../../certus/physics/certus_strat_readings.py) choisit par défaut `exact_inversion=True`, `exact_anchors=True`, `oms_arming=2`. Les appels de production transmettent ces valeurs au noyau, dont les valeurs par défaut de signature restent historiques. Le niveau franchi avant déclaration du dernier extremum produit `CRASH_NOT_ARMED`, quatrième cause, exposée comme `p_not_armed` dans [`_test_strategy_robustness_task`](../../certus/core/certus_strat_robustness_task.py). **Correction :** décrire le chemin de production actuel et borner les conclusions anciennes à leur modèle d'arrêt.

### A04 — Rate ne copie pas seulement la dernière couche de même matériau

§2.10 donne une égalité des erreurs relatives entre la couche Rate et la dernière référence de même matériau. [`_rate_layer_thickness`](../../certus/physics/certus_strat_growth.py) moyenne `d_nom/d_real` sur **toutes les couches antérieures optiquement déposées de même parité**, exclut les références Rate, puis arrondit le dépôt à un nombre entier de tours de 0,125 nm. Avec cette moyenne `a`, l'épaisseur vaut `max(1, round(d_nom/(a*0.125)))*0.125`. Sans référence, le noyau revient au contrôle optique. **Correction :** remplacer la relation de copie et son explication.

### A05 — Les équations d'erreur d'épaisseur décrivent un autre modèle

§2.13 attribue au `probe_offset` un biais physique de vibration ou de dérive ; §2.14 écrit `δd = d_nom*ε + δ_probe`. [`compute_probe_offset_nm_from_ratio`](../../certus/utils/certus_strat_service.py) fournit une distance d'échantillonnage pour les sondes numériques. [`simulate_growth_kernel`](../../certus/physics/certus_strat_growth.py) perturbe le niveau photométrique puis inverse le signal pour obtenir l'épaisseur ; il n'ajoute pas ce décalage numérique comme biais physique. `non_monotonic_error_factor` n'y multiplie plus l'erreur. **Correction :** réécrire les deux sections et les unités, tout en conservant la propagation TMM des épaisseurs réellement obtenues.

### A07 — Un filtre spectral fictif est placé en Phase A

§3.2 et les schémas annoncent un rejet des candidats dont la résolution est inférieure à 1 nm. [`_select_candidates_phase_a`](../../certus/utils/certus_strat_service.py) ne calcule ni ne filtre cette résolution : il traite dynamique, transmission, conditions d'extremum, marge et repli à λ₀. La courbure intervient ailleurs, sur les variantes de fente. **Correction :** retirer ce filtre du parcours Phase A ; voir A15 pour son emplacement réel.

### A08 — Le rejet pour crash n'est pas irrévocable en Phase A

§3.4 et §4.1 affirment que les candidats éliminés pour crash ne parviennent jamais à la programmation dynamique. [`_apply_the_admissibility_rule`](../../certus/utils/certus_strat_service.py) réintroduit, lorsqu'il ne reste aucun survivant, tous les candidats éliminés ex æquo au taux de crash minimal, avec avertissement et `fallback_on_min_crash=True`. **Correction :** documenter ce repli et distinguer admissibilité nominale et conservation du candidat le moins mauvais.

### A09 — Le score livré est P95, pas CVaR95

L'encadré du §4.5 annonce « CVaR95 replaces P95 » et un paramètre permettant de revenir à P95. [`_test_strategy_robustness_task`](../../certus/core/certus_strat_robustness_task.py) calcule `rmse_p95` et classe sur le maximum de ces P95 aux niveaux de bruit ; le code indique explicitement que CVaR a été essayé puis retiré. **Correction :** présenter CVaR comme une expérience historique et décrire P95 comme la fonctionnelle native actuelle, avant les éventuels traitements de consensus/classement.

### A10 — La probabilité de conformité n'est pas le scalaire effectivement optimisé

§10.1 affirme que tous les compromis découlent de `P(part conforms)`, sans pondération ni classement multicritère. Le score natif est celui d'A09, généralement l'écart au spectre nominal ; [`order_by_the_ranking_rule`](../../certus/core/certus_strat_ranking.py) forme des classes puis utilise taux de crash, marge et score. Le code ne calcule pas cette probabilité de conformité comme objectif unique. **Correction :** distinguer l'objectif industriel souhaité de la métrique et de la règle de décision implémentées.

### A11 — Des cibles hors grille ne donnent pas systématiquement +∞

§4.5 promet `+∞` lorsque les zones ne couvrent pas la grille. Au niveau de [`_test_strategy_robustness_task`](../../certus/core/certus_strat_robustness_task.py), des poids de somme nulle déclenchent un avertissement et un **retour au spectre nominal**, avec `rank_weights=None`. La fonction RMSE de bas niveau peut rendre +∞ avec des poids nuls, mais ce n'est pas le chemin de cette orchestration. **Correction :** expliquer le repli réellement exécuté et la différence entre les deux niveaux d'API.

### A12 — SEEL désigne deux conversions différentes dans le programme

La page alterne `2*sqrt(score)` et une calibration linéaire. [`order_by_the_ranking_rule`](../../certus/core/certus_strat_ranking.py) utilise la première ; [`StrategiesTableWindow.update_data`, helper `_rmse_to_seel`](../../certus/ui/certus_strat_table_ui.py) utilise `fit_k*rmse**fit_alpha`, ou l'interpolation de la calibration. [`calculate_seel_analysis`](../../certus/utils/certus_strat_service.py) fixe actuellement `fit_alpha=1`. **Correction :** identifier explicitement la conversion de chaque tableau, campagne et classement ; une équation universelle serait infidèle à ce code lui-même hétérogène.

### A13 — La règle de classement annoncée n'est pas universelle à la sortie

§10.6.1 décrit correctement `rank_final_results` isolément, mais promet que cette règle et l'unicité des identifiants régissent toute sortie. [`run_local_search` et `rank_refined_first`](../../certus/workers/certus_strat_workers_local_search.py) placent le plan affiné retenu en tête, indépendamment du classement natif des autres plans. Par défaut `strat_local_search_fresh_id=False` : ce plan peut conserver l'identifiant de son parent ; le contrôle d'unicité globale n'est alors pas appliqué. [`certus_strat_workers_pipeline`](../../certus/workers/certus_strat_workers_pipeline.py) transmet ce classeur de remplacement à la finalisation. **Correction :** documenter l'exception de recherche locale et le contrôle conditionnel des identifiants.

### A14 — Le contrôle final de transmission n'a pas la portée garantie

§1.5 et §4.7 promettent un minimum vérifié sur toute la croissance de chaque couche, suivi d'un rejet strict. [`_validate_strategy_min_transmission_floor`](../../certus/core/certus_strat_robustness_results.py) évalue seulement la transmission **à l'épaisseur nominale finale** ; en l'absence de longueur d'onde dans le cache, il emploie `T=1`. Son appel conditionnel se trouve dans [`_prepare_block_strategy_phase_b`](../../certus/core/certus_strat_pipeline.py). Le parcours GUI complet prépare Phase A avec `phase_a_only=True`, puis orchestre Phase B dans les workers sans cet appel. **Correction :** ne pas présenter ce contrôle comme un certificat de minimum sur la croissance, ni comme un passage obligatoire de toute sortie GUI.

## Écarts P2

### A01 — Le tableau des réglages mélange profil de campagne et valeurs par défaut

Le tableau initial annonce bruit ±0,05 point, pas de 1 nm, hystérésis 1,66 et marge 1,66 comme « Current operating defaults ». [`default_settings`](../../certus/ui/certus_strat_defaults.py) fournit `trigger_tolerance="0.1"` et `scan_wl_step="2.0"`. [`collect_params`](../../certus/ui/certus_strat_ui_state.py) lit les deux facteurs dans le profil, avec repli à 0 ; le plancher d'hystérésis est distinct. **Correction :** nommer le profil précis auquel se rapporte le tableau et séparer ses valeurs des replis de l'interface et des budgets imposés par le mode.

### A02 — Nom de garde incorrect et recherche finale insuffisamment décrite

Le tableau initial nomme `final_local_search_guard`. [`guard_is_armed`](../../certus/core/certus_strat_local_search.py) lit `strat_local_search_guard`, activé par défaut ; `is_armed` active aussi `strat_local_search` par défaut. Le schéma général et les conclusions sur les leviers encore absents doivent intégrer cette recherche conjointe mode/longueur d'onde. **Correction :** employer la clé réellement lue et compléter l'enchaînement jusqu'à la finalisation.

### A06 — Un facteur d'hystérésis nul ne suffit plus à restaurer le détecteur ancien

§2.5 présente le facteur 0 comme le régime historique sans seuil. [`reading_hysteresis`](../../certus/core/certus_strat_robustness_task.py) prend aussi en compte le plancher `tp_hysteresis_floor`. Avec un plancher positif, facteur 0 ne signifie pas hystérésis nulle. **Correction :** donner l'expression avec le maximum et les deux réglages nécessaires à un seuil nul.

### A15 — La recherche de fente et son filtre sont décrits contradictoirement

§2.11 dit que la fente n'est pas cherchée et que `min_resolution_nm` ne rejette jamais ; §10.10 décrit une recherche. [`_expand_with_resolution_variants`](../../certus/core/certus_strat_robustness.py), activé par défaut sauf désactivation configurée, génère des variantes de fente et écarte celles plus larges que la résolution calculée. **La stratégie de base est conservée.** **Correction :** harmoniser les sections et borner précisément la portée du filtre aux variantes générées.

### A16 — Il manque un facteur 3 dans la formule de résolution

§7.1 donne `Δλ*sqrt(T_tol/κ)`. [`_calculate_strategy_spectral_resolution`](../../certus/core/certus_strat_robustness_slit.py) calcule `Δλ*sqrt(3*T_tol/κ)`, comme l'explique déjà une autre partie de la page. **Correction :** rétablir le facteur 3 sous la racine ; les deux expressions diffèrent d'un facteur √3.

### A17 — La fonction de mérite de nucléation est fausse

§5 donne `block_size*(1-RMSE)`. [`find_robust_nucleation_wavelength_adaptive`](../../certus/workers/certus_strat_workers.py), helper `score_block`, utilise `size**1.5/(rmse+eps)`, avec epsilon adapté à la médiane des RMSE positifs et borné entre `1e-4` et `0.1`. **Correction :** remplacer la formule et expliquer la régularisation du dénominateur.

### A18 — Les analyses de sensibilité et SEEL ne sont pas seulement des vestiges

§7.4–7.5 les qualifient de « Legacy » et les disent intégrées au classement Phase B plutôt qu'exécutées séparément. [`StratStrategyService.run_step_0`](../../certus/utils/certus_strat_service.py) appelle encore `calculate_sensitivity_matrix` et `calculate_seel_analysis` ; la calibration alimente l'affichage. **Correction :** décrire ce rôle actif en Step 0, distinct de la simulation de robustesse.

### A19 — L'explication du bonus de bloc perd le carré et généralise une seule carte

§10.14C affirme que Phase B voit `Cost/streak` et que le coût local n'est conservé nulle part. [`_apply_block_aware_bonus`](../../certus/core/certus_strat_objectives.py) divise par √streak ; seule la carte normalisée THICKNESS² élève ensuite au carré, donnant un terme proportionnel à `Cost_local²/streak`, avec sa normalisation. Les autres cartes ne suivent pas cette transformation au carré. `_apply_the_admissibility_rule` conserve aussi `cost_local` dans les résultats bruts, avant leur réduction en carte normalisée. **Correction :** distinguer les cartes et les étapes de conservation des métadonnées.

### A20 — Le plafond de 120 candidats ELITE n'est pas un plafond par exécution

§4.2 annonce au plus 120 stratégies supplémentaires par run. [`_resolve_elite_refinement_cfg` et `_apply_elite_refinement_if_enabled`](../../certus/core/certus_strat_consensus.py) définissent un budget configurable, utilisé dans une boucle de tours de raffinement. Les appels de Phase B peuvent eux-mêmes porter sur plusieurs nombres de blocs. **Correction :** préciser le périmètre du plafond par génération et les autres budgets, sans promettre 120 pour toute l'exécution.

### A21 — Les trois passes DP ne sont pas simultanées

§4.1 et §8.2 annoncent trois passes concurrentes. [`mine_strategies_for_block_count`](../../certus/core/certus_strat_ranking.py) soumet THICKNESS et THICKNESS², attend leurs résultats, puis soumet SYM si activé. La mention « up to five top-k strategies » ne correspond pas non plus à une limite fixe de cinq : la conversion parcourt les solutions retournées selon le budget DP. **Correction :** décrire les deux premières passes concurrentes, la troisième conditionnelle, et le budget réel.

### A22 — Les responsabilités de la base matériaux et les noms d'API sont confondus

§6.2 attribue à `RobustMaterialDatabase` un repli contexte → global → constantes. [`RobustMaterialDatabase.get_refractive_index`](../../certus/utils/certus_strat_db.py) consulte sa base et lève une erreur pour un matériau inconnu. Les priorités d'injection appartiennent aux fonctions `smart_get_*` de [`certus_strat_utils`](../../certus/core/certus_strat_utils.py) ; les constantes de repli citées sont dans `_resolve_clues_at_wavelength` de [`certus_strat_config`](../../certus/core/certus_strat_config.py). Les API vectorisées actuelles portent le nom `*_clues_vectorized`, non `*_indices_vectorized`. **Correction :** attribuer chaque comportement à sa fonction réelle.

### A23 — Cache et fichiers d'implémentation portent des noms périmés

§6.1 appelle `indices_cache` le champ désormais nommé `clues_cache` de [`StratContext`](../../certus/utils/certus_strat_context.py). §8.3 attribue encore l'essentiel de l'implémentation aux anciennes façades `CERTUS_STRAT.py` et `_certus_physics_impl.py`, alors que les fonctions sont réparties entre `certus/core`, `certus/physics`, `certus/utils`, `certus/ui` et `certus/workers`. **Correction :** distinguer façades de compatibilité et lieux d'implémentation ; remplacer les références fragiles à des numéros de ligne par des noms de fonctions.

### A24 — Les garanties de parallélisme et de mémoire sont trop larges

§8.2 affirme que tous les noyaux utilisent `prange` : plusieurs fonctions scalaires, dont `simulate_growth_kernel`, n'ont pas ce modèle de parallélisation. La taille du pool de robustesse est calculée directement avec `max(1, cpu_count()//2)`, alors que la page lui attribue `get_safe_worker_count`. §8.1 transforme une estimation en plafond ferme : [`_prepare_precompute_wavelength_grid`](../../certus/core/certus_strat_config.py) coarsit la grille de scan mais ajoute ensuite la grille d'affichage et λ₀, sans vérification finale de la taille de leur union. **Correction :** limiter chaque affirmation à son site d'application et parler d'estimation mémoire.

### A25 — Les onglets et le déverrouillage JIT ne correspondent plus à l'interface

§9.1 annonce Design / Optimization / Advanced / Why CERTUS. [`certus_strat_ui_layout`](../../certus/ui/certus_strat_ui_layout.py) construit Design / Strategy Loop / Advanced et l'onglet Multi-seed, avec retrait de Why CERTUS. §9.3 annonce un déverrouillage uniquement après compilation via `invokeMethod` ; [`certus_strat_ui_worker`](../../certus/ui/certus_strat_ui_worker.py) utilise `sig_numba_ready` et dispose d'un déverrouillage de secours temporisé dans `_on_jit_fallback_timeout`. **Correction :** mettre à jour le parcours visible et le mécanisme effectif.

### A26 — Le refus annoncé des indices absorbants n'est pas exécuté ainsi

§11.1 exige que la garde de la forme fermée lève une erreur plutôt que de revenir silencieusement à un autre chemin. [`_fill_history_signal` et `_fill_current_signal`](../../certus/physics/certus_strat_readings.py) choisissent la forme fermée sous le seuil d'absorption et le calcul TMM complexe au-delà. `_invert_thickness_exact` dispose également d'un retour aux sondes pour le cas absorbant. **Correction :** distinguer une prescription de validation souhaitée du branchement réellement livré.

### A27 — La fenêtre adaptative n'est plus un commutateur dormant

§11.2 dit que le drapeau reste désactivé. [`_scan_window`](../../certus/physics/certus_strat_growth.py) ne propose plus ce chemin adaptatif : il a été supprimé ; le balayage courant utilise ses constantes de portée et de taille. **Correction :** conserver éventuellement le bilan de l'expérience, en indiquant la suppression de l'option.

### A28 — Plusieurs affirmations numériques sont incohérentes

- §2.1 : 45,50 à 45,55 % représente une largeur de **0,05 point**, pas 0,10 ; cela ne justifie pas l'amplitude ±0,05 annoncée à partir de ces seules bornes.
- §4.5 : zéro crash observé sur dix tirages ne démontre pas un taux réel inférieur à 10 %. `1/N` décrit la granularité de la fréquence observée, pas une borne probabiliste. À titre de comparaison théorique seulement, dix essais Bernoulli indépendants sans échec donnent une borne supérieure unilatérale exacte à 95 % de `1-0.05**(1/10) ≈ 25,9 %` ; ce calcul ne certifie pas la séquence de tirages du simulateur.
- §10.3 : 856 + 222 = **1 078**, pas 1 033 ; les sous-totaux et le total de crashes cités ne peuvent être simultanément corrects.
- §10.19 : environ 0,9 % est près de **2,9 fois** inférieur à 2,59 %, pas dix fois.

**Correction :** reprendre les bornes, dénominateurs et qualificatifs statistiques depuis les sources, sans modifier une donnée historique au jugé.

## Éléments concordants et archives

Les grandes briques TMM, POEM, propagation couche par couche, groupements contigus et simulation à plusieurs niveaux de bruit sont présentes. Les budgets imposés par les modes sont bien 50/150/300 tirages finaux, 10/25/50 de screening et 20/40/100 pour `dp_top_k`. La table des fentes 5/2/1/0,5 nm et des multiplicateurs de bruit 1/1,5 ; 1 ; 2 ; 5 correspond à l'implémentation.

Les scores et SEEL des six références A3 en ouverture concordent avec le [bilan du 21 octobre](../STRAT_A3_reperes_reprise_2026-10-21/bilan.md), à l'arrondi affiché. Les SEEL 0,575/0,597/0,670 et la médiane 0,597 de la référence 99 couches concordent avec le [bilan du 24 octobre](../STRAT_A3_99c_grille_2026-10-24/bilan.md). Le diagnostic de faux turning points à faible bruit est documenté dans le [bilan d'analyse du 22 octobre](../ANALYSE_claude_2026-10-22/bilan.md). **Concordance de transcription ne signifie pas reproduction de ces expériences sur la tête actuelle.**

Trois chemins cités en texte ne sont pas présents dans ce checkout ni retrouvés par `git ls-files` : `reports/blocs_vs_plantage_r75x2-2nm_deep_s042.json`, `reports/blocs_vs_plantage_r75x2_deep_s042_res1_large.json`, `reports/campagne_N35_300.log`. Des motifs génériques et des sources externes sont également cités. Leur absence locale ne démontre pas que les résultats sont faux ; elle empêche leur certification à partir de cet environnement. Les nombres de performance, les séries historiques détaillées et les caractéristiques de la machine n'ont pas tous une preuve reproductible vérifiée ici.

## Couverture de la lecture

| Partie de la page | Résultat principal du rapprochement |
|---|---|
| Réglages et références en ouverture | A01–A03 ; transcription des références A3 contrôlée |
| §0 — Vue générale | Étapes finales à compléter, A02 et A13 |
| §1 — Modèle physique | Grandes briques présentes ; garantie finale à corriger, A14 |
| §2 — Simulation optique | A03–A06, A15 et A28 |
| §3 — Phase A | A07–A08 |
| §4 — Phase B | A08–A09, A11, A13–A14, A20–A21, A28 |
| §5 — Nucléation | A17 |
| §6 — Architecture et injection | A22–A23 |
| §7 — Analyses | A12, A16, A18 |
| §8 — Implémentation et performance | A21, A23–A24 ; débits historiques non remesurés |
| §9 — Interface et modes | A25 ; principaux budgets concordants |
| §10 — Stratégies et campagnes | A10, A12–A13, A15, A19, A28 ; archives distinguées du comportement livré |
| §11 — Accélérations | A03, A26–A27 ; anciennes mesures non reproduites |

L'inventaire des 110 titres est conservé dans `preuves.json`. La totalité du document a été lue ; une conformité à 100 % est réfutée par les écarts ci-dessus. L'audit ne prétend pas avoir démontré chaque affirmation empirique restante ni validé expérimentalement tout le programme.
