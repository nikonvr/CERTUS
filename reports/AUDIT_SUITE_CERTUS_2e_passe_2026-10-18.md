# Audit de la suite CERTUS, deuxième passe — 2026-10-18

Demande de 👤 : « refais un audit complet ». Même périmètre que le premier ([rapport](AUDIT_SUITE_CERTUS_2026-10-18.md)) : toute la suite **hors
`studies/bonne_mere/`**. Menée seul, sans sous-agent, une étape à la fois. Tête auditée : `4cdc3938` (branche `claude/ecstatic-newton-3grmls`,
arbre propre, synchronisée avec le distant, `PREFLIGHT=GO`). **Aucun fichier de code n'a été modifié par cette passe** : elle ajoute ce rapport et le
dossier [`AUDIT_2e_passe_2026-10-18/`](AUDIT_2e_passe_2026-10-18/) (scripts en `.py.txt`, sorties en `.sortie.txt`, rejouables depuis la racine avec
`python -X utf8 reports/AUDIT_2e_passe_2026-10-18/<nom>.py.txt` ; les scripts écrivent leurs résultats bruts dans `%TEMP%\audit_certus\`, à créer).

Le premier audit avait listé ce qu'il n'avait pas mesuré ; cette passe vise ces trous et ajoute des angles neufs : sonde aléatoire contre l'oracle,
gradients, mutation des formules, scan de tout l'historique, `bandit`, CI distante.

## 1. Verdict

La suite est saine là où la physique s'exécute, et les défauts nouveaux sont dans ses **marges** : entrées invalides acceptées en silence, un noyau de
gradient hérité faux pour les couches absorbantes, des trous de tests.

- **Validée** : `validate_parallel.py` rend `VALIDATION=GO` (16 min), la CI distante est verte sur la même tête (tests en série sur Ubuntu et Windows,
  gel construit, lint, sécurité), C1 tient au bit contre le commit d'avant ce jour (9 092 tableaux), 63 000 cas aléatoires de TMM s'accordent à l'oracle
  indépendant à 6·10⁻¹⁴, aucun secret ni adresse personnelle dans les 1 575 commits.
- **Nouveaux constats (C20 à C32)** : un défaut numérique latent et mesuré (**C20**, gradient hérité faux de 340 % sur la configuration d'un test existant),
  deux familles d'entrées invalides qui rendent du fini plausible (**C21**, **C22**), quatre mutations de formules que toute la suite laisse passer (**C29**),
  et des faibles (caches modifiables, flux de bruit, reproductibilité, CI).
- **Rien du premier audit n'a régressé** ; l'état de C01 à C19 est au §4.

## 2. Ce qui a été mesuré

| mesure | résultat |
|---|---|
| Validation parallèle sur `4cdc3938` (`scripts/validate_parallel.py`) | ruff et 3 contrôles documentaires 0 ; oracle 1 146 ; unité **5 545 réussis**, 7 ignorés, 1 xfail (5:24) ; ui 1 324 / 12 ignorés / 2 xfail (4:51, 6 workers) ; reste 319 ; performance 40 ; `GO` en 16 min, aucun artefact de charge |
| CI distante, même tête ([run des tests](https://github.com/nikonvr/CERTUS/actions/runs/39143920414)) | lint, security, release-windows, tests : succès. **En série** : oracle 1 146 ; unité Ubuntu 5 542 réussis + 11 ignorés (24:52) ; reste 348 + 2 ignorés ; UI Windows 1 324 / 12 / 2 (23:45) |
| TMM de production contre l'oracle indépendant (`fuzz_tmm`, graine 20261018) | normal 30 000 (R,T), oblique s/p 24 000 (0 à 89°), plaque incohérente avec pile arrière et substrat absorbant 9 000 : **écart max 5,9·10⁻¹⁴ / 5,2·10⁻¹⁴ / 2,9·10⁻¹⁴**, 0 hors [0,1], 0 refus. Couches de k jusqu'à 6, n de 0,05 à 4,5, jusqu'à 30 couches de 0,5 à 1 500 nm |
| Gradient oblique contre différences finies de l'oracle (`fuzz_grad`) | 3 984 dérivées, écart max 1,6·10⁻⁵ de l'échelle 1/λ, aucune au-delà de 10⁻⁴ |
| Gradient normal contre le coût de production (`fuzz_grad2`, 400 cas, 16 configurations) | 350 cas sur 350 accordés ; **50 sur 50 faux** dans « sans pile arrière, couches absorbantes, substrat non absorbant » (C20) |
| Mutation de 22 formules physiques, dans des copies hors dépôt (`mutate`) | **18 tuées, 4 survivantes** (C29) ; 16 par l'oracle, 2 par les tests unitaires |
| C1 contre `6e546515` (tête distante avant le push de cet après-midi), cold contre cold | **C1 TENU : 9 092 tableaux identiques au bit** |
| Historique entier (`scan_range --all`) : 1 575 commits, 29 763 objets, 17 539 blobs (1,9 Go bruts) | 0 secret, 0 adresse dans le contenu hors trailers ; 124 blobs de plus de 2 Mo (le plus gros : 36 Mo) |
| `bandit` 1.9.4, 425 fichiers de code livré | 78 constats : 1 HIGH (SHA1, C31), 1 MEDIUM (`xml.etree` sur un `coverage.xml` local), 76 LOW (`subprocess` sans shell) |
| Balayage AST de risques (`hazards`) | aucun `eval`/`exec`/`pickle`/`yaml.load`/`shell=True`/`allow_pickle`/réseau ; 9 `except Exception` qui avalent (5 dans `certus/`, gardés par le cliquet) ; 12 `nan_to_num` inventoriés, le contexte de 8 relu (les 4 autres, au §6) |
| Frontières de couches et signe de k (`layers_sign`) | 0 import de `core`/`physics`/`domain` vers PyQt6 ou `certus.ui` ; 15 lignes `±1j·k`, **toutes `-1j·k`** |
| Complexité (`radon`) | moyenne B (5,6) sur 4 396 blocs ; **87 fonctions de rang E ou F** (CC > 30), dont `compute_regular_grid_rmse_profile` 97, `_corridor_profile_walk_side` 79, `_test_strategy_robustness_task` 74 |
| Tests par analyse statique | 577 fichiers, 4 808 fonctions ; 32 sans assertion visible (faux positifs probables : `check()` de `test_gradient_vs_fd.py` lève, vérifié) ; 354 n'ont que des assertions faibles ; 0 `assert True` |
| Pages `pages/*.html` | les 15 passent `scripts/verifier_html.py` (0 point) ; **structure seulement**, pas les affirmations |
| Dépendances | `pip check` propre ; `requirements.lock` (47 paquets) et `uv.lock` concordent ; 6 écarts de version de patch entre le verrou et l'interpréteur local |
| Intégrité Git | `git fsck --no-dangling` : rien |
| Colorimétrie | blanc parfait → Lab (100 ; −0,007 ; 0,002) ; 6 valeurs des tables CIE 1931 à 5·10⁻⁵ ; 10 paires de Sharma pour ΔE2000 à 4·10⁻⁵ |
| Matériaux (`probe_materiaux`) | silice fondue, N-BK7 et saphir (Sellmeier du dépôt) contre la littérature : écarts 3,8·10⁻⁶, 1,1·10⁻⁷ et 1,2·10⁻⁴ ; `epsilon_to_nk` : n² − k² = ε₁ à 10⁻¹², k ≥ 0 sur 20 000 cas |

## 3. Constats nouveaux

### Fonctionnels

**C20 — Le noyau de gradient hérité de DESIGN donne un coût et une pente faux dès que les couches absorbent** *(moyenne ; latent ; reproduit)*.
`compute_gradient_all_layers_analytic` (`gradient_oblique.py`), appelé par l'optimiseur de DESIGN, par le moteur et par le polissage d'élagage, envoie
le cas « sans pile arrière, substrat réel » au noyau `_compute_gradient_analytic_kernel`. Celui-ci lit la partie imaginaire dans la convention
**n + ik** : avec `n − ik` (la convention du projet) l'absorption devient du gain. En passant `conj(n)`, la valeur et le gradient redeviennent ceux de
l'oracle (6·10⁻⁹ près). Écart au coût de l'oracle indépendant, une couche n = 2,1 de 120 nm, cible T = 0,5 : k = 10⁻⁴ **+0,3 %** (pente 0,6 %) ; 10⁻³ **+2,6 %**
(6 %) ; 10⁻² **+29 %** (84 %) ; 0,1 **×14,5**, pente de signe opposé ; argent 25 nm +10 % ; filtre à 4 couches TiO₂ (k = 0,002)/SiO₂ +9,3 %, pente jusqu'à 17 %.
Sur la configuration du test existant `test_design_gradient_all_absorbing` (k = 0,03 / 0,01 / 0,05) : coût du noyau 0,1228 contre 0,0277 (**+343 %**), pente
5 à 15 fois trop grande.
**Pourquoi rien ne le voit** : ce test compare le gradient aux différences finies du coût *du même noyau* (auto-cohérence), donc les deux sont faux ensemble ;
le correctif du 2026-09-30 n'a traité que le substrat absorbant (le commentaire attribue l'écart au « T vu du côté substrat », ce qui n'explique pas le cas des couches).
**Portée** : DESIGN n'utilise que des matériaux de Cauchy réels (`Material.get_nk` rend n réel ; exemples `n4`/`n7`) : inaccessible aujourd'hui depuis DESIGN. La
fonction est publique (`certus_physics`). Les 15 autres configurations (pile arrière, substrat absorbant) passent par les noyaux obliques, justes.
`probe_abs_grad`, `probe_c20_conj`, `fuzz_grad2`.

**C21 — La validation des entrées diffère d'un point d'entrée à l'autre, et un NaN devient un spectre nul plausible** *(moyenne ; reproduit)*. NaN, +∞, −∞ injectés
dans chacune des quatre entrées (λ, épaisseurs, indices des couches, indice du substrat) :

| point d'entrée | refuse | rend du fini |
|---|---|---|
| `calculate_RT_vectorized_real` (avec ou sans face arrière) | 12 sur 12 | 0 |
| `calc_spectrum_oblique_vectorized` (0° et 30°), `…_backside_vectorized` | 9 sur 12 | **3** : les indices des couches ne sont pas contrôlés (choix commenté : 0,15 ms sur 1,5 ms) |
| `calc_spectrum_full_oblique_exact` | 1 sur 12 | **11** |
| `calc_spectrum_full_exact` | 2 sur 12 | **10** |
| `cost_numba_fast` | 0 sur 12 | **12** |

Le noyau compilé en `fastmath` rend (R, T) = (0, 0) pour un NaN au lieu d'un NaN ; le filtre `np.isfinite` de `compute_mse_vectorized` ne le voit donc pas.
Mesuré (9 longueurs d'onde, coût de référence 0,1817) : une épaisseur NaN ou infinie → coût **0,25** (T = 0 partout) ; un NaN dans une seule cellule d'indice → 0,1947 ;
6 cellules sur 9 → 0,239. Un optimiseur qui produirait un NaN verrait un coût ordinaire. Autre seuil caché : sous **5 points valides** le coût vaut la sentinelle 10¹² (3 ou 4
longueurs d'onde), sans que la docstring le dise. `probe_cout_nan`. C'est la suite de **C06** (spline) et **C07** (épaisseur négative). Les
indices sont préparés une fois (`optim_prepare_stack_nk_back`) : un seul contrôle `isfinite` y suffirait, sans le coût par évaluation. `fuzz_tmm`, `probe_invalid`.

**C22 — Des valeurs physiquement invalides sont corrigées ou absorbées sans le dire** *(faible à moyenne ; reproduit)*. (a) **k négatif** (gain, `n = 1,5 + 0,01j`) :
`compute_TMM_generic` *et* le noyau vectorisé rendent exactement le résultat de k = +0,01 (R + T = 0,896) ; l'oracle rend R + T = 1,116. Le garde-fou « n − ik » retourne le
signe de la partie imaginaire au lieu de refuser ou de ramener à 0 : une table n,k à k légèrement négatif (bruit de mesure) devient absorbante de |k|. Les tables livrées
n'ont pas de k < 0 (3 colonnes `k` de `indices.xlsx` relues, `probe_materiaux`). (b) **Indice de couche nul** : la couche disparaît (résultat du substrat nu : R = 0,0426, T = 0,9574 ; l'oracle rend NaN),
ce qui aggrave C06 (un NaN de spline devient n = 0, donc une couche absente). (c) **Substrat d'indice < 10⁻¹²** : R = 1, T = 0 (miroir parfait) dans le noyau et dans la plaque.
(d) λ = 0 ou NaN passé au noyau brut : (0, 0). `probe_invalid`, `fuzz_tmm`.

**C23 — Deux caches rendent le même tableau modifiable à chaque appel** *(faible ; reproduit)*. `get_n_substrate_array_by_id` (clé : empreinte 64 bits des octets) et
`get_nk_from_spline` (`lru_cache`) rendent *le même objet*, `flags.writeable` vrai : écrire `n[0] = 99` dans un appelant fausse tous les appels suivants (mesuré : n[0] = 99 au
deuxième appel). Aucune écriture en place sur ces résultats n'a été trouvée par lecture (`certus_index_ui_utils.py` copie d'abord) ; rien ne l'interdit. `probe_caches`.

**C24 — Le cache de la matrice de base de la spline RE arrondit les longueurs d'onde à 1 nm** *(faible ; mesuré)*. `re_compute_spline_basis_matrix` (clé : nœuds à 0,1 nm,
λ à l'entier) rend la matrice d'une autre grille décalée de 0,4 nm : erreur d'un élément de la matrice 6,7·10⁻³, soit 3·10⁻⁴ sur un indice qui varie de 7,5·10⁻⁴/nm. Le commentaire
(« tolérer le bruit des flottants ») est plus large que ce qu'il tolère. `probe_caches`.

**C25 — Le Monte-Carlo de FIELD et ses départs multiples ne sont pas reproductibles** *(faible)*. `certus_field_workers.py:288` (`np.random.normal`) et `:740`
(`np.random.uniform`) utilisent le RNG global hérité, sans graine ni paramètre : deux exécutions des mêmes entrées donnent des statistiques différentes, et deux dessins ne se
comparent pas à bruit commun. La règle C2 vise STRAT ; FIELD n'est pas couvert.

**C26 — `_seeded_noise_sample` est un mauvais mélangeur pour des graines voisines** *(faible ; latent ; mesuré)*. Deux graines brutes consécutives (42 et 43) donnent des
bruits corrélés à **+0,196** (distance 2 : 0,098 ; 3 : 0,091 ; 5 : 0,079 ; 10 et plus : < 0,002). Les trois flux de production (signal, affine, indice) dérivent leurs graines
par un mélange multiplicatif : sur 45 flux et 990 paires, le pire |r| est 0,0078 pour un seuil de 0,0089 ; ils sont indépendants. Reste la **nucléation**, qui reçoit `robustness_seed`
brut (`certus_strat_workers.py:191` et `:228`) : deux exécutions STRAT à graines consécutives y partagent un bruit corrélé. Dans une graine : moyenne, écart type, kurtosis et
corrélations entre couches et entre tirages voisins sont conformes. Corriger change les tirages (donc les résultats) : décision de 👤. `probe_noise`, `probe_noise2`.

**C27 — Le coût `cost_numba_fast` dépend du nombre de fils Numba au dernier bit** *(information ; mesuré)*. Pour 1, 2, 4, 8, 16 fils : coûts 0,11459713964256443 / …47 / …43 / …49 / …45
(écarts de 1 à 5·10⁻¹⁷, réduction `prange`). Les spectres R, T (normal et oblique), le gradient et sa valeur sont identiques au bit. C1 fixe déjà 4 fils.

**C28 — `xyz_from_spectrum` prolonge un spectre trop court par ses valeurs de bord et se trompe sur un ordre décroissant** *(information ; mesuré)*. R = 0,8 sur 450–650 nm
rend Y = 80,0 comme sur 380–780 nm (`np.interp` constant hors plage, sans avertissement) ; les mêmes données en λ décroissantes donnent XYZ = (9,5 ; 10,0 ; 10,9) au lieu de
(45,0 ; 45,4 ; 27,4). Le seul appelant (le worker couleur de DESIGN) passe une grille croissante. `probe_color`.

### Tests et outillage

**C29 — Quatre mutations de formules survivent à toute la suite** *(moyenne ; mesuré)*. 22 mutants (signe, facteur ou terme d'une formule), appliqués un à un dans des copies de
travail et rejoués contre `tests/oracle` puis, pour les survivants, contre les fichiers de `tests/unit` qui citent le symbole : 16 tués par l'oracle, 2 par les tests unitaires
(`compute_mse_vectorized` : seuil 5 → 1 ; garde d'angle 90 → 91), **4 survivants** :

| mutant | ce que la suite ne fixe pas |
|---|---|
| `a* = 500·(fx − fy)` → `200·(…)` (`xyz_to_lab`) | le coefficient de a* : une couleur fausse de 2,5× sur a*, 25 tests de colorimétrie verts |
| `25⁷` → `25⁶` dans `delta_e_2000` | la constante de ΔE2000 : 24 tests verts ; la fonction est pourtant juste (paires de Sharma, §2) |
| garde-fou du signe de k, jusqu'à 1,0 (`compute_TMM_generic`) | le comportement « gain retourné en absorption » (C22) : 369 tests verts, 7 min |
| même garde-fou dans le noyau vectorisé | idem |

Le test `test_design_gradient_all_absorbing` illustre l'autre faiblesse : une auto-cohérence ne détecte pas un modèle faux (C20).

**C30 — CI : deux étapes « non bloquantes » sont vertes ; les contrôles documentaires n'y sont toujours pas** *(faible)*. `tests.yml` marque `continue-on-error: true` l'étape
mypy sur `domain`/`physics`/`core` et l'étape « Coût des noyaux en références NumPy » ; leur commentaire les dit bloquantes dès qu'une exécution de la CI les aura vues vertes. Elles
le sont (`success`) dans le run de `82e51021` (les autres steps du job aussi) ; `mypy` rend « no issues found in 95 source files » en local. Les 11 tests de `pytest-benchmark` restent sautés en CI (348 + 2 ignorés contre 359
en local) ; l'étape `bench_kernels.py` les remplace. Aucun workflow ne lance `coherence_md`, `check_claude_md`, `check_docs` (C10a persiste). Les 4 workflows : `permissions: contents: read`,
pas de `pull_request_target`, 0 action non épinglée par SHA, un seul secret (`GITHUB_TOKEN`).

**C31 — Divers d'outillage** *(information)*. `scripts/lint_ns_snapshot.py:32` : `hashlib.sha1` (HIGH de `bandit`, même motif que l'alerte CodeQL déjà corrigée dans
`probe_blocs_vs_plantage.py`). Dette de lint officielle (D25) : **1 491** (1 416 le 2026-10-12), dont RUF001 147 contre 77 : 63 des +70 viennent de `.py` de campagne rangés dans `reports/`. Typage :
75,4 % des fonctions entièrement annotées, 1 737 occurrences de `Any` (mesure par AST, non comparable à celle du premier audit). Local contre verrou : coverage 7.16.2/7.16.1,
fonttools, hypothesis, pyinstaller-hooks-contrib, ruff 0.16.10/0.16.9, tzdata. 15 des 47 paquets du verrou ne sont pas nommés dans `THIRD_PARTY_NOTICES.md` (outils de test et de
construction : pytest, coverage, hypothesis, ruff, pluggy, pefile, altgraph, macholib…), non vérifié s'ils sont embarqués dans le gel. Les essais laissent des journaux à la racine
(`certus_*.log`, `*.jsonl`, ignorés). `.git/worktrees/` compte 11 entrées : 4 de Codex (`gitdir` présent, dossier absent) et **7 coquilles** (`buildwt`, `certus0310`, `jovial-mayer-391b05`,
`profwt`, `ratewt`, `ratewt2`, `valwt` : un `ORIG_HEAD` de 41 octets ou rien, pas de `gitdir`) ; elles causent le bruit « failed to delete » et se retirent par `rm -rf`, que `git` refuse ici.
Règle 11 : 7 lignes de prose de `certus/` portent un mot français de contenu que le détecteur ne voit pas (`french_words`) : 2 sont la ligne ELITE autorisée ; **2× `# ── GARDE-FOU n-ik ──`**
(`certus_tmm_matrix.py:93` et `:174`), 1× `# -- tableau vivant` (`certus_strat_multigraine_ui.py:397`), 2 messages de journal (`certus_strat_service.py:841` : « seuil … retirees » ;
`spline_pipeline_utils.py:543` : « substrat »). `epsilon_to_nk` borne n à 10⁻⁶ pour ε₁ ≪ 0 (2nk − ε₂ jusqu'à 5,7·10⁻⁶ en absolu) : sans effet physique.

**C32 — Historique public** *(information)*. 124 blobs de plus de 2 Mo (36 Mo pour `blocs_vs_plantage_r75x2_deep_s101_rr.json`), 1 252 blobs binaires ; paquet de 185 Mio. Quatre commits
portent l'identité civile de 👤 (déjà au premier audit, C16). Aucune réécriture n'est proposée.

## 4. Constats du premier audit, état au 2026-10-18

| # | état |
|---|---|
| C01 `ColorWorker` | corrigé (`f32734a9`), test de bout en bout vert |
| C02 xdist | corrigé ; la validation parallèle passe sans artefact |
| C03 audit UX sous charge | consigne formalisée dans `validate_parallel.py` (`ui` à 6) ; mesuré vert |
| C04 pointeur d'archive | corrigé ; archive toujours en **une seule copie** |
| C05 chemins longs | corrigé |
| C06 NaN de spline → n = 0 | **ouvert** (D108) ; aggravé par C22 (b) |
| C07 épaisseur négative | **ouvert** (D109) ; reproduit : R + T = 1,9987 |
| C08 `open_file_explorer` | corrigé |
| C09 19 rapports CRLF/LF | commités tels que trouvés (`178bdd36`), réversible |
| C10 CI / déclarations | (a) **persiste**, (b) précisé : 348 + 2 contre 359 ; `bench_kernels` vert |
| C11 français dans `certus/` | corrigé et gardé ; un `GARDE-FOU` échappe au détecteur (C31) |
| C12 D107 | **ouvert** sur `main` ; correctif non validé sur la branche locale `claude/alg02-prune-evaluator-0d2a8d` |
| C13 `dk5` | ouvert, inchangé |
| C14 audits à la racine | inchangé, justifié (liens à la racine) |
| C15 `studies/bonne_mere` | publié sur ordre de 👤 |
| C16 identités | inchangé |
| C17 typage | 75,4 %, 1 737 `Any` (méthode différente) |
| C18 cache Numba | parade `cache=False` en place ; test de rejeu vert ; Numba non prévenu |
| C19 `connect(lambda)` | corrigé ; plafond de la CI à 44 |

## 5. Vérifié, sans écart

TMM normal, oblique s/p et plaque incohérente contre l'oracle (C1 et ces 63 000 cas) ; gradients obliques contre différences finies de l'oracle ; frontières de couches (0 inversion de
plus) ; convention `n − ik` (15 lignes sur 15) ; Sellmeier de la silice, du BK7 et du saphir ; tables CIE, D65, ΔE2000 de Sharma ; formules de `epsilon_to_nk` (k ≥ 0) ;
absence de `pickle`, `eval`, `shell=True`, réseau dans le code livré ; durcissement des workflows ; verrous concordants ; historique sans secret ; intégrité Git ; pages HTML sans point de structure ; 
flux de bruit de production indépendants entre eux ; spectres et gradients identiques au bit pour 1 à 16 fils.

## 6. Ce que je n'ai pas mesuré

La suite complète **en série en local** (la CI la fait sur Ubuntu et pour l'UI sur Windows, sur la même tête) ; la couverture de tests ; l'exécution du gel autrement que par la CI ;
les modèles directs d'INDEX, de RE et de METAL contre l'oracle (seuls leurs noyaux de gradient sont couverts par les tests existants, relus ici seulement pour DESIGN) ; la polarisation mixte
et les milieux anisotropes ; Numba sous Linux (C18) ; 4 des 12 `nan_to_num` dont le contexte n'a pas été relu (`certus_metal_single_physics.py:448`, `certus_optical_models.py:423`, `certus_strat_heatmap_ui.py:80`,
`certus_index_workers_opt_strat.py:371`) ; pour la normalisation IR d'INDEX (`certus_index_core.py:572`, `…ir_strat.py:690-692`, NaN → 0), je n'ai pas vérifié que le côté mesuré reçoit le même traitement que le côté calculé ;
l'optimisation DESIGN de bout en bout ; `studies/bonne_mere/` (exclu).
**Mes sondes ont leurs limites** : l'analyse statique des tests ne voit pas une assertion portée par un assistant (32 faux positifs probables) ; la mutation ne couvre que 22 formules choisies par moi ;
l'oracle et la production partagent mes conventions d'appel (ordre des couches, `n − ik`).
**Environnement modifié sur demande de 👤** : `bandit 1.9.4` (+ `stevedore 5.9.1`) et `radon 6.0.1` installés dans l'interpréteur global (avec les outils déjà installés lors du premier audit).

## 7. Plan d'actions, du plus simple au plus complexe

| # | action | constat | décision de 👤 ? |
|---|---|---|---|
| A23 | Retirer `continue-on-error` de l'étape mypy et de l'étape `bench_kernels` (vertes) ; ajouter les 3 contrôles documentaires à `lint.yml` | C30 | non (le plan l'annonçait) ; touche un fichier de CI |
| A24 | `rm -rf` des 7 coquilles de `.git/worktrees/` (et des 4 entrées de Codex dont le dossier est absent) ; `git worktree prune` refuse ici | C31 | non |
| A25 | `usedforsecurity=False` (ou sha256) dans `lint_ns_snapshot.py` | C31 | non |
| A26 | Tests de référence, sans toucher au code : XYZ→Lab (valeurs connues), 10 paires de Sharma pour ΔE2000 | C29 | non |
| A27 | **Corriger C20** : conjuguer `n_layers_T` avant le noyau hérité (ou router vers le noyau oblique à 0°), avec un test contre l'**oracle** sur couches absorbantes (rouge avant) ; `scripts\c1_diff.py HEAD` : l'indice réel doit rester identique au bit | C20 | non (comportement inchangé en indice réel) |
| A28 | Contrôle `isfinite` des indices **une fois** à la préparation (`optim_prepare_stack_nk_back`) et des épaisseurs à chaque coût | C21 | non |
| A29 | Politique de k < 0 (refuser, ramener à 0 ou retourner), d'indice nul et de substrat nul, puis un test (tue M06/M09) | C22, C29 | **oui** |
| A30 | Rendre les tableaux des deux caches non modifiables (`setflags(write=False)`) ou rendre des copies ; rejouer la suite | C23 | oui (peut casser un appelant non testé) |
| A31 | Clé du cache de base RE à 3 décimales, ou clé en octets | C24 | non |
| A32 | Graine optionnelle (inactive par défaut = comportement actuel) pour le Monte-Carlo et les départs de FIELD | C25 | oui |
| A33 | Dire dans la docstring de `_seeded_noise_sample` « graines brutes à ≥ 10 d'écart » ; mélanger `robustness_seed` à la nucléation changerait les tirages | C26 | **oui** |
| A34 | Documenter C27 et C28 (nombre de fils ; plage 380–780 nm et ordre croissant, avec un refus dans `xyz_from_spectrum`) | C27, C28 | non |
| A35 | Reprendre A9 à A14 du premier audit (NaN de spline, épaisseur négative, déclarations de développement, seconde copie de l'archive) | C06, C07, C10 | oui |

## Annexe — reproduction

Depuis la racine, `%TEMP%\audit_certus\` créé. `fuzz_tmm 6000 6000 3000` (18 s), `fuzz_grad 300 200`, `fuzz_grad2`, `probe_abs_grad`, `probe_invalid`, `probe_color`, `probe_noise`,
`probe_noise2`, `probe_threads` (10 s), `probe_caches`, `probe_c20_conj`, `probe_cout_nan`, `probe_materiaux`, `hazards`, `layers_sign`, `tests_quality`, `lockcheck`, `french_words` :
une commande chacun, `python -X utf8 reports/AUDIT_2e_passe_2026-10-18/<nom>.py.txt`.
`mutate.py.txt 1` (20 mutants, 4 copies de travail, 7 min) puis `mutate.py.txt 2 M06 M09 M16 M17 M19 M20` ; `scan_range.py.txt --all` (7 min). C1 : `python scripts\c1_diff.py 6e546515`.
Les sorties de cette passe sont dans le même dossier (`*.sortie.txt`, `c1_contre_6e546515.json`).
