# CERTUS — état du projet

> Ce document porte l'**état** : où en sont les programmes, les repères mesurés, ce que 👤 a
> décidé, les défauts ouverts et les chantiers. Les **règles** sont dans
> [`CLAUDE.md`](../CLAUDE.md). Il se tient **en place** : un fait change, on corrige sa ligne,
> on ne raconte pas la correction (`git log` s'en charge). Toute mesure porte sa date.
> Le détail et l'historique sont dans `git`, sans autorité (CLAUDE.md, en-tête).
> Mis à jour le 2026-10-06 au soir (les 19 réponses de 👤 appliquées ; D92 trouvé et corrigé).

## 0. Reprise — à lire en premier, à tenir à jour

> Mettre à jour cette section avec le travail : « en cours » dès le début, mesure et commit
> à la fin. Les règles de validation sont dans les sections 2, 4 et 12 de
> [CLAUDE.md](../CLAUDE.md) ; les décisions scientifiques appartiennent à 👤 (§5).

**Dernière action (Claude, 2026-10-06 au soir, sur les 19 réponses de 👤, §3).** Un commit et un test par
correction ; chaque test échoue sur le code d'avant.
- **D10** (`d83c39c7`) : huit départs aléatoires au lieu de deux. Sur 41 perturbations d'un ulp des données du
  saphir, la RMSE reste entre 0,000946 et 0,000964 (avant : 0,00095 à 0,00097 quarante fois, 0,00796 une fois),
  pour 2,15 s par ajustement au lieu de 1,44.
- **D76** (`ca3e269c`) : le gradient de l'analyse du faisceau de METAL SINGLE porte la dérivée de la pénalité de
  lissage. Le banc METAL SINGLE ne lance pas cette analyse : son résultat ne bouge pas (0,0061003457).
- **D56** (`36dde65c`) : D263T eco prend les coefficients du catalogue Zemax de SCHOTT (2017-01-20b), à 2,1e-4 de
  la fiche ; pour B270i, dont SCHOTT ne publie pas de Sellmeier, B1 et C1 sont ajustés aux huit raies de la fiche
  (436 à 656 nm, résidu de 4,4e-5 au plus) et les quatre autres termes gardés : au-delà de 656 nm, l'indice repose
  sur eux. Oracle : 1 123 passed.
- **D41** (`a8c013fa`) : fermer INDEX, INDEX SPLINE, RE, METAL ou DESIGN pendant un calcul pose la question avant
  d'arrêter quoi que ce soit. **D58** (`49584fd7`, le bouton de remise à zéro passe de 9 à 11 pt), **D65**
  (`bfc8e298`), **D66** (`4a4a6a81`).
- **Deux fenêtres rebranchées** (`f20fd40c`) : l'accueil propre de STRAT, et le moniteur n, k d'INDEX SPLINE ouvert
  à côté de l'aperçu Smart Init. **Couleurs de la branche du 2026-09-07 portées** (`dc0c1c60` : 257 → 217
  couleurs hexadécimales hors thème), puis la branche supprimée, comme `wip-d75-gradient-lame`.
- **Poste et sauvegardes** : le venv `C:\envs\certus` est supprimé (envoyé à la corbeille) et quatre scripts shell
  prennent le Python du système (`2e197935`) ; les fichiers hors git (les deux PDF Selenium et `studies/`) sont
  archivés à côté des bundles, `../CERTUS_hors_git_2026-10-06.zip` (24 entrées).
- **CI** : les actions étaient déjà épinglées par SHA ; les cinq mises à jour proposées par Dependabot sont
  appliquées sur la branche, une par commit (`fcce99e7`, `6c7faa3d`, `1321c206`, `2d83a2df`, `c6b7e4bf`) ; les
  gardes des workflows passent (41 passed). Aucune fusion dans `master`.
- **Avis de tiers** : brouillon `THIRD_PARTY_NOTICES.md` (`30fb39c0`, `52bd04a9`) ; ce que le dépôt n'établit pas y
  est marqué « à confirmer par toi ».
- **D92, trouvé en écrivant les avis et corrigé** (`79b26a95`) : les fonctions colorimétriques x̄, ȳ, z̄ n'étaient
  pas celles de la CIE depuis le commit initial (ȳ culminait à 490 nm au lieu de 555) ; un réflecteur parfait
  sortait en L\*a\*b\* = (100 ; 60,4 ; −113,1), et l'analyse couleur Monte-Carlo de DESIGN avec lui. Elles sont
  maintenant les lignes 380 à 780 nm, au pas de 5 nm, de la table de la CIE (`CIE_xyz_1931_2deg.csv`, DOI
  10.25039/CIE.DS.xvudnb9b, CC BY-SA 4.0), téléchargée avec l'accord de 👤 et contrôlée par sa somme SHA-256
  publiée : le réflecteur parfait donne (100 ; −0,007 ; 0,002). D65, inchangé au bit, rend avec elle le blanc
  (95,043 ; 100 ; 108,880) pour (95,047 ; 100 ; 108,883) publié. La page DESIGN (8.2) décrit maintenant cette
  analyse, et non une optimisation vers une couleur cible que DESIGN ne fait pas (`1834349b`).
- **Une validation complète à `e855bffa`** a trouvé trois suites de mes corrections, toutes corrigées. (1) Unit :
  1 failed, 4 923 passed — l'attribut annoté que D41 avait ajouté à un mixin de la fenêtre de base donnait à ce
  mixin, sous Python 3.14, un `__annotate_func__` masqué (`d81252e3`). (2) UI : la suite s'est figée dans
  `test_ux_re_stop_when_idle.py`, dont la fixture fermait RE avec un faux calcul en cours ; depuis D41 la
  fermeture le demande, dans une boîte que personne ne fermait (`e4e0941d`). (3) UI : le cliquet UX a vu le
  panneau gauche de METAL passer de 389 à 403 px de largeur minimale, effet du bouton de remise à zéro à 11 pt
  (D58), plus que les 394 px que ce panneau reçoit à 1366×768 ; 👤 a choisi un padding horizontal de 8 px au lieu
  de 16 (`7dbe4ae9`, mesuré : 387 px). Validation complète de `29240ee7` verte (ci-dessous), puis la branche poussée,
  sans fusion dans `master`.
- **CI de la PR #5 sur `dbec2fc1`** : `pytest (ubuntu)` rouge sur un seul test, `test_a_complete_frozen_folder_is_accepted`.
  Le contrôle d'artefact de D87 cherchait `vcomp140.dll` par un motif sensible à la casse sous Linux, et le gel
  écrit `VCOMP140.DLL` ; il est insensible à la casse depuis `d8a0ef42` (poussé). La PR se fusionne dès que toute sa
  CI est verte (§3).
- **Licences dans le gel** (`04a67083`, `93127c2e`, locaux, pour la PR suivante) : `licenses/` reçoit `LICENSE`,
  `THIRD_PARTY_NOTICES.md` et les fichiers de licence de chaque distribution embarquée (`tools/frozen_licences.py`) ;
  le contrôle d'artefact les exige. Construit le 2026-10-06 (même contenu, avant le rebasage sur `d8a0ef42`) : 91
  fichiers, 885 Ko, 55 distributions dans le gel local ; artefact et démarrage contrôlés.

**Plus tôt le 2026-10-06.** Un audit complet (`c2b47f11`) a trouvé D87 à D91. Corrigés depuis : D87 (`31745571`,
`1aa32a1d` : le gel calcule sur la couche OpenMP ; construit, démarrage et artefact contrôlés), D88 (`a49fe502`,
`330f592d`, `c2e0db04`), D89 (`f65f191d`), D90 (`a5a50fc8`), D91 (`f61e40a0`), D85 (`55f7e9da`), D55 (`601b2489`)
et D54 (`7a958dec`, `39990246` : le chemin par défaut garde ses bits, le juge de paix sa population au bit), D72
en partie (`5ccaa210`, 442 → 411 Mo). **D87 confirmé par 👤 dans l'exécutable** construit au commit poussé
`dbec2fc1` (`%TEMP%\CERTUS_HUB_test_dbec2fc1\CERTUS_HUB.exe`, hors du dépôt) : « l'exécutable fonctionne »
(2026-10-06) ; le `release-windows` de la CI l'a aussi construit et démarré sur ce commit.

**Point de départ.** `certus0310`, branche `refactor-corridors-mixins`,
[PR #5](https://github.com/nikonvr/CERTUS/pull/5). La branche est poussée sur `origin` le 2026-10-06 au soir, sur
l'autorisation de 👤 donnée pour une validation complète à 0 échec, sans fusion dans `master` ; sa CI se lit sur la
PR. `python scripts\preflight.py` → `PREFLIGHT=GO` le 2026-10-06. Sauvegarde
après chaque lot : `../CERTUS_certus0310_<date>_<commit>.bundle`. Les entrées `.git/worktrees/certus0310` et
`.git/worktrees/profwt`, incomplètes (Drive en refuse la suppression), déclenchent un avertissement à chaque
commit sans l'empêcher.

**Dernière validation complète (2026-10-06, Windows 11, Python 3.14.8, Ryzen 7 5700G, code au commit `29240ee7`, arbre neuf hors de Drive) :** Ruff 0 ; oracle 1 123 passed ; unit 4 934 passed, 5 skipped en 9 min 44 (premier passage, froid après le changement de clé du cache Numba : 1 failed, D84) ; UI 1 312 passed, 12 skipped, 2 xfailed en 18 min 42 ; autres tests 347 passed, 2 skipped en 10 min 42 ; trois contrôles documentaires : 0 défaut. Les quatre pages HTML RE, DESIGN, INDEX SPLINE et STRAT rendent leurs logigrammes Mermaid dans Chrome (8/8, 6/6, 5/5 et 6/6, mesuré le 2026-10-04).

**Ordre conseillé des prochains lots.** Priorité à ce qui rend un résultat faux ou empêche de calculer,
puis aux dépendances techniques ; chaque changement reste un commit distinct (C3). Une mesure en cours
n'autorise pas à modifier son arbre témoin.

| rang | action et critère de fin | raison / condition |
|---|---|---|
| 3 — établir la parité publiée | Inventaires (`reports/PARITE_ZENODO_*_2026-10-05.md`) et lecture des écarts courts de l'INDEX SPLINE (`reports/PARITE_ZENODO_SPLINE_LECTURE_2026-10-06.md` : remaniements, trois retouches heuristiques du corridor, une correction) faits. Reste à lire les écarts longs (gradient analytique, nettoyage des nœuds, décalage de Δn, polissage du maillage) et à comparer les capacités du RE marquées « non comparé » (a priori MAP, substrats, échantillons à deux faces, résidus par voie). | Nécessaire avant d'affirmer que les améliorations publiées sont intégrées. RE local 1.2.0.dev0 diffère de l'archive 1.1.1 ; l'inversion conjointe de plusieurs échantillons est écartée par 👤. |
| 4 — traiter la chaîne de mesure | Spécifier puis mesurer la cadence machine (§6, 12.4), ensuite seulement le lissage (12.2). D54 et D55 sont corrigés. | La grille de la machine est inactive par défaut. Tout changement de noyau passe C1 froid contre froid et l'oracle. |
| 5 — stabiliser interface et gel | Reproduire D23 (les six `gc.collect()` des threads de calcul STRAT et les `QThread`) avant D11 et `WA_DeleteOnClose` ; poursuivre la réduction du gel (D72) après sa fiabilité. | D11 n'a pas d'effet dans le lancement actuel par processus ; libérer une fenêtre avant ses threads serait plus grave. |
| 6 — réduire la dette | Élucider les effets d'import de D42 avant E402/I001 (D25), puis traiter D26 et les défauts visuels selon §4–5. | Chantier utile, mais moins urgent que la justesse scientifique ; l'ordre des imports peut changer l'exécution. |

**Après les deux PR en cours, le rang 3** (choix de 👤 du 2026-10-06). Les autres
choix réservés à 👤 restent en §5.

## 1. Où en sont les programmes

| programme | état | prochaine action |
|---|---|---|
| **Calcul (STRAT)** | composant étalon : l'aléatoire ×2 (`r75x2`) à la fente de 2 nm. Fabricable avec les rampes de la configuration livrée ; sans rampes, 3 graines sur 7 trouvent des déposables. Toute la fabricabilité passe par le générateur ELITE | rangs 2 et 4 ci-dessus |
| **RE** | indices tabulés lus en n − ik depuis R148 (2026-10-05) : tout RE antérieur fait sur des indices absorbants en incidence oblique est à refaire ; un indice demandé hors de sa table est prolongé par une constante, avec un avertissement (ex-D86, `dec73219`, 2026-10-05) ; préchauffage incomplet (D85) | rang 3 |
| **Exécutable gelé** | sur la couche OpenMP depuis `31745571` (D87), sans les outils de développement depuis `5ccaa210` (411 Mo) ; construit à `dbec2fc1` le 2026-10-06, hub et modules contrôlés au démarrage, et 👤 y a calculé : « l'exécutable fonctionne ». Les licences de ce qu'il embarque le suivent (`licenses/`, PR suivante) | rang 5 (D72) |
| **Interface** | plan clos le 2026-09-08 : 12 critères de fin sur 13 atteints et mesurés, le treizième démontré inatteignable (`xfail` strict) | rang 5 et choix de 👤 (§5) |
| **Qualité** | CI : calcul sous Linux, interface sous Windows, gel construit et démarré sous Windows, audit de sécurité (`pip-audit`, `gitleaks`) ; tests isolés des préférences de 👤 ; l'audit du code mort couvre tout `certus/` (D24 clos le 2026-10-05 : 3 928 définitions, 73 candidats justifiés un par un). Indicateurs du plan le 2026-10-06 (`scripts\metrics.py`) : tous dans leur cible, sauf la couverture et la taille du gel, non remesurées ce jour | rangs 5 et 6 |
| **Documentation** | règles dans `CLAUDE.md`, état ici ; 15 rapports HTML, 34 schémas Mermaid et 2 SVG validés le 2026-10-03 ; anciens dossiers lisibles dans Git | tenir « un fait, un seul endroit » |
| **Validation externe** | 🔴 **aucune** : STRAT n'est validé que contre lui-même, et c'est assumé (décision de 👤 du 2026-10-06 : les deux dépôts réels du dichroïque ne sont plus prévus) | — |

## 2. Repères mesurés — fente 2 nm, modèle courant

| composant | SEEL | plantage | condition |
|---|---|---|---|
| dichroïque 48 couches, `JSON-strat-example` | **0,173 nm** | 0 % | 6 blocs, une campagne |
| le même, modèle de `b60d80e2` (après R130) | **0,175 nm** | 0 % | 4 blocs (λ 544, 471, 467, 474 nm), 370 stratégies, aucune éliminée ; `scripts\bench_examples.py strat`, caches Numba vierges, 2026-10-04 (`reports/STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json`). Même population au bit (identifiants, scores, plantage par niveau de bruit) et même `RESULT` 0,007644641198073172 avec le code de `e6c66b4b`, le 2026-10-05 |
| passe-bande 3 cavités, 35 couches | **0,482 nm** | 0 % | 6 blocs, mode `deep` |
| aléatoire `JSON-strat-random75`, 75 couches | **0,272 nm** | 0 % | une campagne, 241 déposables sur 662 |
| passe-bande 5 cavités, 99 couches | **0,81 nm** | 0 % par campagne | 4 verres témoins, partition 0-22 / 22-42 / 42-76 / 76-99 |
| le même en une seule campagne | aucun score valide | 100 % | 487 stratégies, toutes plantent : non fabricable |
| aléatoire ×2 `r75x2`, fente native 1 nm | **0,6248 nm** | 0 % | `deep`, pur optique, 277 déposables |
| `r75x2` à 2 nm, configuration livrée | **0,5676 nm** | 1,67 % | avec `example/example_strat/rampes_r75x2-2nm.json` ; étendue 0,55 % sur 3 graines |
| `r75x2` à 2 nm, sans rampes | **0,5599 nm** | — | graine 404 ; 3 graines sur 7 trouvent (77, 404, 505). Égalité avec la voie à rampes, pas supériorité |

Le passe-bande de 99 couches est chiffré en moyenne de trois graines, jamais par la meilleure.

**Lire ces chiffres :**

- 🔴 **Les SEEL ne se comparent pas d'un composant à l'autre** : ils sont notés sur des
  domaines de largeur différente (section 7). Toute comparaison **à composant fixé** est valide.
- 🔴 **Un score seul ne départage rien.** À N = 150 tirages, la dispersion Monte-Carlo vaut
  σ ≈ 6 % ; deux runs à moins de ~8 % sont indiscernables. On compare des **classes
  d'équivalence SEEL**. Sur `r75x2`, σ ≈ 1,8 % mesuré en changeant le triplet de graines de
  consensus : un bruit emprunté à un autre composant ne vaut rien.
- Ces repères comprennent le **biais de fente** ; une mesure sans ce biais ne leur est pas comparable.
- Le banc `scripts\bench_examples.py strat` lit sa configuration dans `CERTUS_DESIGN_JSON` ; par défaut le juge de
  paix standard (`JSON-strat-example.json`). Les mesures `fast` de D5, D73, D20, D70 et D17 prenaient
  `JSON-strat-example-fast.json` (194 stratégies), celles de D14 et D15 le standard (370) : les deux ne se comparent pas.
- Les repères du tableau, sauf la ligne du modèle de `b60d80e2`, sont antérieurs à R130 : depuis, la gagnante est prise dans la classe du meilleur SEEL
  (à un pas de 0,01 nm près) par rendement puis marge ; son SEEL dépasse le meilleur d'au plus un pas.
- La longueur seule ne met pas le monitoring optique en échec, la **structure** si :
  75 couches aléatoires passent, 99 couches à cavités et miroirs non. Sur un empilement
  structuré, la longueur pèse ensuite : sur 270 sous-intervalles du passe-bande de 99 couches,
  la part de déposables s'effondre avec elle (r = −0,869).
- Un taux de 100 % obtenu en `fast` ne conclut rien (la recherche peut n'avoir rien proposé) ;
  un 100 % qui tient jusqu'à `deep` est un constat sur le composant et sa fente.
- Au banc : `CERTUS_BENCH_TIMEOUT_S = max(5400, 4 × durée attendue)`. Au-delà du plafond le
  banc rend `RESULT=None` avec une poignée de stratégies : cherche `WAIT_TIMEOUT=` dans le journal.

## 3. Ce que 👤 a décidé — ne pas rouvrir sans mesure qui le contredise

### Réglages

| réglage | valeur |
|---|---|
| cadence machine | 4 Hz, une lecture témoin par tour |
| pas d'échantillonnage machine | un point tous les 0,125 nm à 0,5 nm/s |
| bruit de lecture | ±0,05 point, soit `A = 5e-4` en unités T |
| `reading_smoothing_window` | 1 (inactif) en exploitation ; 8 lectures dans le modèle figé |
| `tp_hysteresis_factor` | 1,66 en usage. Cible 1,00, mesurée à k = 8 et N = 800 : à remesurer avant de l'appliquer, les configurations tournant à k = 1. Il porte aussi le **sens** de variation du plantage avec le bruit — physique à 0,5, inversé à 1,66 |
| `phase_a_level_margin_factor` | 1,66 ; 3,33 à évaluer |
| `index_corridor` | 0,005 en indice absolu, actif |
| `photometric_curvature_amp` | **0,00375**, actif |
| `affine_scale_amp`, `affine_offset_amp` | 0,05 et 0,02 |
| `allow_rate` | vrai — « le cas général » |
| `slit_bias_enabled` | vrai, fente nominale 2 nm |
| choix de fente de l'opérateur | 5, 1 ou 0,5 nm en plus du nominal ; facteurs de bruit ÷1,5, ×2, ×5 |
| `robustness_num_runs` | 300, décidé le 2026-08-13 : il commande la sensibilité du filtre de plantage, donc **quelles stratégies existent**. 🔴 Le mode d'exécution l'emporte sur le fichier (150 en `premium`), et la ligne `[MODE]` du journal le dit |
| `n_screen_runs` | 25 ; à 10, un seul plantage tue une stratégie **et** la perd comme parent |
| profondeurs par mode | `robustness_num_runs` 50 / 150 / 300, `n_screen_runs` 10 / 25 / 50, `dp_top_k` 20 / 40 / 100 pour fast / premium / deep ; `extreme` = `deep` avec une génération élargie |
| graine de référence | 42, avec `scan_wl_step` à 1,0 |
| grille des λ de contrôle | figée à 1 nm |
| `machine_sampling_dd` | 0, figé dans le noyau (ce n'est plus un réglage depuis le 2026-09-27) : pas grossier (~21 points par couche au lieu de 800), par choix de vitesse. Le modèle est donc optimiste sur les faux points tournants |
| cible spectrale | non pondérée jusqu'à nouvel ordre |
| mode par défaut | `premium` |

### Le modèle de la chaîne de lecture (OMS 5100) — figé le 2026-08-08

1. Une lecture témoin par tour à 4 Hz, soit un échantillon tous les 0,125 nm.
2. Bruit additif borné à ±0,05 point, σ = A/3, tirages indépendants d'une lecture à l'autre.
3. Moyenne glissante de k = 8 lectures (2 s) dans le modèle, inactive en exploitation.
4. Seuil de point tournant : la borne **mesurée** vaut 1,00 A à k = 8 et N = 800 ; la loi en
   1/√k est réfutée (elle laisse 100 % de points tournants fabriqués). Une mesure, pas une loi.
5. Aucun retard de déclenchement.
6. Marge de sélection des λ : 5 σ du bruit brut (1,66 A) ; 10 σ (3,33 A) à évaluer.
7. Quantification de l'arrêt `U(0 ; 0,125 nm)` — non implantée (§3, STRAT, D13).

Hors du modèle, et à y laisser : σ dépendant de T ou de λ, grenaille, bruit multiplicatif,
bruit corrélé d'un tour à l'autre, tout filtre autre que la moyenne glissante. Seul un run réel
du dichroïque dont le plantage s'écarterait nettement du prédit rouvrirait ce modèle.

### Logiciel — décidé le 2026-09-27 et le 2026-10-03

- **CERTUS tourne toujours sur un poste à jour** : les bornes minimales de `pyproject.toml` ne comptent pas ; la CI ré-résout vers les dernières versions stables à chaque run (`uv sync --upgrade`), `uv.lock` n'est qu'un point de départ (`uv lock --upgrade`). Pas de pré-version : pydantic ≥ 2.13.4 stable, plus 2.14 bêta.
- **La non-reproductibilité est acceptée** : INDEX, RE et METAL_BILAYER ne rendent pas deux fois la même RMSE — leurs générateurs ne sont pas amorcés, et on ne les amorce pas. Mesuré le 2026-09-27 : INDEX de 0,002546 à 0,002691 sur dix exécutions, et 0,0067 (2,6 fois la référence) environ une fois sur huit ; RE 0,05 % ; METAL_BILAYER 1 %. La garde de convergence retient pour eux la meilleure de quatre exécutions au plus (`tests/regression/test_convergence_guard.py`).
- **Fastmath conservé dans tous les noyaux JIT — décidé le 2026-10-03** : 👤 arbitre « on garde fastmath » (D52/D67). Les gains de vitesse (7 à 19 %) sont conservés ; la non-reproductibilité froide vs chaude (jusqu'à 424 ulp sur les gradients, 1e-13 en relatif) est acceptée. Le harnais C1 maintient ses comparaisons froid à froid.

### Licence et comportement par défaut — décidé le 2026-09-29

- **Le projet est publié sous GPL-3.0** : c'est ce que PyQt6 exige de l'exécutable gelé (R36).
- **Quatre changements du comportement par défaut de DESIGN, acceptés** (R29) : la porte de stagnation et les seuils de gain prédit du Needle sont ceux réglés sur la fenêtre ; la phase globale est plafonnée quand la croissance topologique est cochée ; les graphiques prennent le fond du thème compact ; le substrat complexe est lu en oblique.
- **La sauvegarde des commits locaux** est un bundle Git hors dépôt, à actualiser après chaque lot non poussé ; pousser requiert ton ordre.

### Publication — décidé le 2026-09-30

- **Rien à cacher côté public** (« je n'ai aucune crainte de tout mettre en espace public, c'est mon choix ») : l'historique n'est pas purgé — ni le nom porté par les métadonnées de 44 classeurs anciens, ni l'adresse personnelle de quatre commits — et `git filter-repo` n'est pas au programme. Les 269 classeurs `.xlsx` suivis aujourd'hui ne portent comme auteur que « CERTUS » ou « openpyxl », les 8 `.xls` que « CERTUS » ou aucun (vérifié le 2026-10-06).
- **Les œuvres de tiers restent à leurs auteurs** : la GPL-3.0 ne les couvre pas (le texte de thèse de l'historique, les PDF d'articles). Elles vont dans les avis de tiers, pas dans une purge.

### Interface — décidé le 2026-09-28

- **INDEX : les réglages d'absorption du substrat ne s'affichent que pour le silicium**, le seul
  substrat dont le calcul lit l'absorption ; pour tous les autres, le worker force k = 0 (D43).

### Règles gravées

- **Une λ de contrôle est interdite** si, signal bruité, elle risque de mal compter les points
  tournants ou de ne pas s'arrêter au niveau voulu — en Phase A comme en Phase B. La marge se
  compte **en transmission, jamais en nanomètres**.
- Les λ se choisissent sur la **grille de balayage** (`_resolve_monitoring_wavelength_grid`),
  jamais d'après les clés de `clues_at_wl`, qui mêlent grille de balayage et d'affichage.
- Les heuristiques de la littérature (15-85 %, amplitude de départ, swing) sont des
  **colonnes explicatives**, jamais des couperets.
- **Rate interdit sur les couches 0 et 1, autorisé partout ailleurs, dernière comprise**
  (`RATE_MIN_LAYER = 2`) : avant la couche 2, aucune couche de même nature n'a été déposée
  dont tirer un rate. Le rate ne se calcule **que sur les couches déposées optiquement**.
  Son mécanisme est la **position terminale** : une couche Rate lègue son erreur en boucle
  ouverte à tout ce qui la suit, la dernière n'a rien en aval.
- **SEEL** est la seule grandeur à rapporter : `SEEL = 2 × √score` (`_apply_strategy_ranking`),
  en nanomètres d'erreur d'épaisseur par couche. Tri : SEEL quantifié au pas de 0,01 nm, puis
  rendement, puis marge de la couche critique. Un écart d'un pas est une égalité (classement final, R130).
- **`fast` crible, il ne publie pas** : il est quantifié à 10 % sur le plantage, et un SEEL
  retenu en `fast` se rejoue en `premium`. **`extreme` n'a aucune justification mesurée** —
  zéro amélioration sur cinq configurations, `deep` seul fait aussi bien pour un cinquième du coût.
- **La profondeur Monte-Carlo sert à noter, jamais à choisir** : une candidate écartée parce
  que N était petit est perdue pour toujours.
- **Le multi-témoins est un outil de faisabilité**, pas d'optimisation : il rend le passe-bande
  de 99 couches fabricable et dégrade tout composant qui s'en passait (contrôle négatif 3 sur 3).

### STRAT — arbitrages délégués par 👤 le 2026-10-04

- **D73, point tournant sous l'arrêt : corrigé.** La marge se mesure en
  transmission au sommet interpolé, même si la pente change de signe sur
  l'échantillon d'arrêt. Sur 20 000 empilements aléatoires, 1 617 marges
  ont baissé ; le juge de paix `fast` a gardé ses 194 stratégies et son
  `RESULT` au bit.
- **D20, classement final : corrigé.** Dans la classe à 0,01 nm du meilleur
  SEEL, trier par rendement, marge critique, puis score brut. Le juge
  `fast` conserve 194 stratégies mais change 147 positions ; la
  recherche interne garde son tri propre.
- **D70, critère en épaisseur : retiré.** Son réglage était inerte ; la
  marge valable est en transmission. L'ancienne clé est ignorée au
  chargement avec journal. C1 : 8 008/8 008 tableaux identiques au bit.
- **D17, gain négatif : conservé.** Il détecte une fragilité que la porte
  de plantage peut manquer. Sur le juge `fast`, 159 candidates ont un
  gain négatif, dont 13 sont écartées par ce seul critère ; le journal
  les compte toutes.
- **D15, historique POEM : quatre couches conservées.** Douze couches
  rendent les mêmes 370 stratégies, leur ordre et leurs taux de
  plantage sur le juge standard ; 303 scores ne diffèrent que dans
  les derniers bits (≤ 6,7·10⁻¹¹ en relatif).
- **D14, densité de l'historique : 16 points conservés ; la densité relève de la cadence machine (rang 4).**
  L'écart de densité (16 points par couche rejouée contre 21 par épaisseur nominale pour la couche courante)
  n'existe que sur le balayage grossier : sur la grille de la machine (`machine_sampling_dd > 0`),
  `_resample_on_machine_grid` lit l'historique et la couche courante à la même cadence, chaque lecture avec
  son tirage. Porter l'historique à 21 points changerait tous les résultats pour une densité aussi
  arbitraire que 16 : sur le juge standard (2026-10-04), 8 plans sur 370 survivent, le plantage moyen au bruit
  ×2 passe de 0,0012 à 0,0069. La sensibilité mesurée dit que la densité de lecture compte ; elle se règle par
  la cadence de la machine, pas par ce paramètre numérique.
- **Hystérésis : le seuil suit le niveau de bruit, comme aujourd'hui.** Le seuil vaut 1,66 × le bruit
  du niveau simulé (0,5×, 1×, 2×). L'autre lecture, un seul seuil réglé sur le bruit nominal, a été mesurée
  sur `r75x2` en `deep` (graine 42, `306559d3`, caches vierges, 2026-10-05 ; une trace a vérifié que la clé
  atteint le calcul) : sur les 300 plans communs aux deux runs, le plantage à 1× est identique pour 300,
  à 0,5× il baisse pour 7 et monte pour 2, à 2× il monte pour 4 et baisse pour 5, et aucun plan ne gagne ni
  ne perd le statut de déposable ; meilleur SEEL déposable 0,5566 contre 0,5560 nm, gagnante 0,5605 contre
  0,5592 nm, sous le σ ≈ 1,8 % de ce composant. Les populations diffèrent (783 contre 662 stratégies, 691
  contre 515 déposables) parce que la recherche bifurque, pas par un effet plan par plan. L'anomalie qui
  motivait la question a disparu du code actuel : 684 stratégies dont le plantage croît avec le bruit contre
  33 où il décroît (en août : 61 contre 532). Raison de garder : aucun gain mesuré pour un changement de toutes
  les populations. `scripts\probe_plantage_vs_sigma.py` rouvrira la question si l'anomalie revient. Sorties :
  `reports/STRAT_bench_r75x2_deep_hysteresis_{noise_level,nominal}_306559d3_2026-10-05.json`.
- **D6, réglages du consensus : vérifiés, aucun écart à corriger.** `collect_params` applique toujours un mode
  d'exécution (inconnu → `premium`) et chaque mode fixe ensemble `robustness_num_runs` et `consensus_num_runs`
  (50, 150, 300, 300) ; la ligne `[MODE]` nomme toute valeur du fichier qu'il remplace. Le cas de 2026-08-10
  (20 tirages demandés, 150 obtenus en silence) ne peut plus se produire par l'application. Les graines du
  consensus viennent de `consensus_seed_list` quand elle est renseignée, de `robustness_seed` sinon
  (`_resolve_consensus_seeds`) : un triplet fixe rend les scores de consensus comparables d'un run à l'autre, et
  chaque journal l'imprime (`Consensus ranking enabled (…, seeds=[41, 42, 43], …, runs=300)`, vu le
  2026-10-05 sur `r75x2`). Pour mesurer la dispersion d'un run à l'autre, changer le triplet, pas
  `robustness_seed` ; le consensus ne réécrit que le score, jamais le taux de plantage.
- **D7, ce que `RESULT` agrège : établi dans le code.** `RESULT` est le `robustness_score` de la première
  stratégie classée (`extract_best_rmse`) : le P95 du RMSE des tirages, au pire des trois niveaux de bruit
  (`_test_strategy_robustness_task`), remplacé pour les `consensus_top_k` par la moyenne plus
  `consensus_std_weight` écarts-types de ce même score sur les graines du consensus. Il ne dit rien du reste de
  la population : un réglage qui change les autres stratégies sans toucher la gagnante le laisse identique au
  bit. C'était le cas de 2026-08-10 : à `tp_hysteresis_factor` 2,0 et 2,4 (au moins 2 A), le bruit seul ne
  fabrique aucun point tournant (`detect_turning_points`), la gagnante est simulée à l'identique, et l'écart de
  38 % était celui d'une statistique de bande sur la population. Comparer deux runs se fait sur le classement
  (`dump_strat_ranking`) ou sur les vidages par stratégie, comme les rapports `STRAT_bench_*` de `reports/`.
- **D9, la plage de blocs ne vide pas la DP : un seuil de faisabilité, dit désormais dans le journal** (R147).
  Mesuré sur le juge de paix standard (`ca99bc8c`, caches vierges, 2026-10-05) : la DP trouve 241, 242 et 241
  groupements à 9, 8 et 7 blocs, aucun de 6 à 1, avec la plage livrée comme avec une plage réduite à
  {48, 9, 8, 2, 1} ; une sonde autour du mineur compte 7 blocs contigus au moins pour qu'une même λ soit
  admissible dans toutes les couches de chaque bloc. Sous ce nombre, le mineur ne rend que les graines
  structurées (« Mining found 2 strategies »), ce qui se lisait comme une recherche vidée ; à 48 blocs aussi, la
  première couche devant partager le bloc de la deuxième (`force_first_layer_same_wl`). L'héritage depuis le
  nombre de blocs supérieur y ajoute ensuite ses stratégies dérivées, et elles comptent : sur `r75x2`, de 5 à 9
  blocs, 188 stratégies déposables, et la gagnante du juge de paix standard a 4 blocs. Sauter ces nombres de blocs
  pour gagner du temps (environ 11 min des 30 d'un run `deep` de `r75x2`) les perdrait. Sur `r75x2` le même seuil tombe
  entre 9 et 10 blocs (601 groupements de 15 à 10, graines seules de 9 à 1, 2026-10-05). Le mineur écrit
  maintenant `[MINING] n_blocks=…: the DP found no grouping; the fewest contiguous blocks … is N` ; aucun
  résultat ne change. Sorties : `reports/STRAT_bench_juge_de_paix_ca99bc8c_D9_*_2026-10-05.*`.
- **D8, intervalles du 99c avec recherche de fente : les verdicts tiennent.** Les quatre intervalles de la
  partition retenue ([0,22), [22,42), [42,76), [76,99)) remesurés comme le fait
  `scripts\campagne_intervalles.py` (`fast`, graine 42, verre nu, tranche du bruit des 99 couches, `ca99bc8c`,
  2026-10-05), fente cherchée ou non : déposables tous les quatre dans les deux bras, plantage minimal 0 %,
  meilleur score déposable à −2,6 %, −0,8 %, 0 % et +1,8 % (la recherche de fente place dans la population des
  fentes de 0,5 à 5 nm). La partition reste fabricable avec la recherche de fente. Les autres intervalles
  du cache ont servi à choisir cette partition ; les refaire ne servirait qu'à la rechoisir, ce qui n'est pas fait. Le SEEL assemblé (§2, 0,81 nm
  sur trois graines) n'est pas remesuré. Sorties :
  `reports/STRAT_99c_intervalles_retenus_fente_{off,on}_ca99bc8c_2026-10-05.json`.
- **Sans changement de code :** D16 (THICKNESS² conserve l'ordre DP),
  D18 (seuils 0,025 et 0,04 appliqués à deux grandeurs), D19 (le
  comptage des points tournants est déjà dans le noyau Phase A), D22
  (effet borné à une couche et Rate simulé en Phase B), D12 (lissage
  causal inactif à `k=1`), D13 (quantification temporelle à reporter
  jusqu'à une mesure réelle). Une mesure contradictoire les rouvrira.

### DESIGN — tranchés par Claude sur l'ordre de 👤, 2026-10-04

D45 et D46 attendaient la décision de 👤 ; son « go » du 2026-10-04 à la résolution des
actions complexes, donné sur une liste qui les disait bloquées par lui, a été lu comme cette
décision. Chaque correctif est un commit (R136 `c738a130`, R137 `83661fd4`) qu'un `git revert`
annule seul.

- **D45, gradient avec pile arrière : corrigé.** Le coût et son gradient
  utilisent désormais la même somme des poids. C1 : 93 des 8 008
  tableaux changent, tous dans ce gradient ; la différence finie
  confirme le nouveau gradient à 10⁻⁵.
- **D46, opacité : bornes d'épaisseur limitées.** Les modes global,
  local et healing restent à 1 % sous l'épaisseur où `|Im φ|=700`.
  Une couche non absorbante garde ses bornes au bit ; un métal
  infrarouge n'envoie plus l'optimiseur dans la zone où le noyau
  répond (R, T) = (0, 0). Les noyaux restent inchangés.

### Arbitrages de 👤 du 2026-10-05 (soir)

- **Polarisation « Avg » de DESIGN (ex-D47) : retirée officiellement.** Le tableau des cibles n'offre que s et p ; une configuration ancienne « Avg » se charge en s avec un avertissement. Rien à calculer.
- **Threads Numba d'une tâche de robustesse STRAT : adaptatif** (`task_numba_threads`) : 4 sur une machine de 16 cœurs logiques ou plus, 2 sinon, jamais au-dessus de la limite de Numba. Mesuré sur le juge de paix standard (mode `premium`, caches froids, Ryzen 7 5700G, 16 threads, 2026-10-05) : à 2 threads 521, 476 et 472 s, à 4 threads 452, 421 et 418 s, soit 11 à 13 % de moins, et les six populations (370 stratégies, scores, plantage par niveau de bruit) sont identiques au bit, ce que la construction garantit : chaque tirage des noyaux parallèles écrit sa propre case. Le code livré rend 421 s et la même population. Les machines de moins de 16 cœurs gardent 2 faute de mesure. Profil par échantillonnage du même run : 74 % de la durée dans la robustesse Monte-Carlo (dont 29 % de consensus), 17 % d'attente du consommateur de statistiques, 6 % dans `build_M_before_cache`.
- **D54 : supprimer `adaptive_scan`** (code mort) : fait le 2026-10-06 (`7a958dec`), sous la tolérance de 👤 du même jour (ci-dessous).
- **D86 : garder l'avertissement**, ne pas refuser l'extrapolation.

### Arbitrages de 👤 du 2026-10-06

- **Un matériau absent de la base refuse le calcul** (D88), plutôt que de seulement prévenir.
- **Le gel passe sur la couche OpenMP** (D87) : construire, contrôler le démarrage ; le calcul réel dans
  l'exécutable revient à 👤.
- **D48 : le substrat reste non absorbant**, sans champ d'épaisseur. DESIGN construit ses matériaux, substrat
  compris, par un modèle de Cauchy réel à deux indices (n à 400 et 700 nm, `Material`) et STRAT ne lit que la
  partie réelle de l'indice du substrat : l'épaisseur du substrat n'entre dans aucun de leurs calculs. La lame
  absorbante reste dans la physique (`certus_substrate_absorption`), avec son épaisseur par défaut de 1 mm.
- **Tolérance de C1 pour retirer du code mort d'un noyau : 10⁻¹⁰ en relatif** (D54). Le retrait de
  `adaptive_scan` en est resté à 2,3·10⁻¹³.

### Réponses de 👤 du 2026-10-06 au soir, une question à la fois

- **Calcul** : D10, fiabiliser l'ajustement du saphir ; D76, ajouter la dérivée de la pénalité ; D56, remplacer
  les coefficients si les fiches du fabricant diffèrent. Faits (§0).
- **Données Nb2O5 « Syrus » : laissées telles quelles.** Dans les feuilles `Nb2O5-Syrus` et `IR-Syrus-Nb2O5` de
  `example/database_index/indices.xlsx`, n tombe de 2,09 à 4,0 µm à 1,19 à 4,7 µm puis remonte à 1,78 à 5 µm,
  quand les feuilles H400 et H800 restent entre 2,07 et 2,13 ; un creux de cette taille avec k ≤ 0,018 n'est pas
  physique. Un résultat fondé sur ces feuilles au-delà de 4 µm en hérite.
- **Stop pendant l'étage IR d'INDEX : le résultat raffiné est gardé**, comme aujourd'hui ; rien à changer.
- **Interface** : D41, demander avant de fermer pendant un calcul, partout ; D65, retirer les branches mortes ;
  D66, créer la légende avant les courbes ; D58, appliquer `BODY_LG` — puis, son effet sur le panneau de METAL
  mesuré, réduire le padding horizontal du bouton à 8 px plutôt qu'accepter 403 px ou revenir à 9 pt ;
  rebrancher les deux fenêtres ; évaluer puis intégrer la branche de couleurs. Faits (§0).
- **Poste** : supprimer `wip-d75-gradient-lame` et le venv `C:\envs\certus` ; archiver les fichiers hors git à
  côté des bundles. Faits ; l'archive est à refaire si ces fichiers changent. **Le dépôt reste dans Google Drive.**
- **GitHub** : tester puis fusionner les mises à jour de Dependabot — appliquées sur la branche, et toute fusion
  dans `master` se redemande à 👤 ; `master` exigera une CI verte et des actions épinglées par SHA — l'épinglage
  est en place, la protection de branche est un réglage de sécurité de GitHub, appliqué par 👤 ; pousser
  la branche après une validation complète verte, sans fusion dans `master`.
- **Avis de tiers : un brouillon**, ce que le dépôt n'établit pas marqué « à confirmer par toi ». Fait
  (`THIRD_PARTY_NOTICES.md`).

### Réponses de 👤 du 2026-10-06, seconde série

- **La PR #5 se fusionne dans `master` dès que toute sa CI est verte**, sans attendre le test de l'exécutable ; la
  correction automatique de la CI est active sur elle. Une autre fusion dans `master` se redemande.
- **Protection de `master` : rien à ajouter** aux contrôles exigés (ruff, pytest, interface) ; pas d'épinglage SHA
  obligatoire (les actions sont épinglées de toute façon).
- **PR Dependabot #1 à #4 et #6 : laissées à Dependabot**, qui les ferme quand `master` a leurs versions.
- **Le gel embarque toutes les licences** : `LICENSE`, `THIRD_PARTY_NOTICES.md` et les fichiers de licence de chaque
  distribution embarquée, dans `licenses/`.
- **Données et logo de 👤** : `BSCNES_*` et le reste de `example/` et `samples/`, la table du silicium sous 1200 nm,
  `sapphire_index.txt`, les préréglages de Cauchy, le logo. `certus_re` (Zenodo) est publié sous CC BY 4.0. Les quatre
  termes de B270i autres que B1 et C1 sont d'origine inconnue.
- **La table D65 de la CIE peut être téléchargée** pour vérifier celle du code : identique au bit (`e8be1315`).

### Réponses de 👤 du 2026-10-06, troisième série

- **La PR qui suit la #5** (licences du gel, avis, ETAT) **se fusionne aussi dès que toute sa CI est verte.** La
  session n'est plus archivée automatiquement à la fusion d'une PR.
- **DLL Microsoft du gel** : une licence Visual Studio de 👤 n'est pas établie ; la ligne reste « à confirmer
  par toi » dans `THIRD_PARTY_NOTICES.md`.
- **Un gel local se construit dans un environnement jetable installé depuis `requirements.lock`**, comme celui de la
  CI, et supprimé ensuite : l'exécutable local n'embarque plus ce que porte le Python du poste.
- **Le prochain chantier est la parité Zenodo** (rang 3 de §0).
- **La validation externe de STRAT n'est plus prévue** : STRAT reste validé contre lui-même (§1).

### RE — décidé par 👤 le 2026-10-05

- **Divergence du faisceau : deux ou trois rayons suffisent.** 👤 : « définitivement, la prise en compte de
  la divergence faisceau se fait avec 2 ou 3 rayons, c'est suffisant ». Le RE en emploie deux (θ ± h,
  `_re_p4_effective_half_width_deg`) ; la quadrature de Gauss-Legendre à neuf nœuds du paquet Zenodo n'est pas
  portée (dans ses propres sorties, elle ajustait moins bien : RMSE jointe 0,4166 % contre 0,1481 % à deux
  rayons, ouverture imposée de 2°, `results/insitu_model_refinement.json`).

## 4. Défauts ouverts

Numérotés ici ; un défaut corrigé sort de la liste et son numéro n'est pas réattribué. Les
numéros de l'ancien registre sont entre parenthèses
(`git show 7b08dc8:docs/archives/DEFAUTS_OUVERTS.md`). Tous revérifiés contre le code le 2026-10-06.

**Ils faussent un résultat, trompent l'utilisateur ou empêchent de calculer**

| # | défaut | piste |
|---|---|---|

**Le modèle physique — connus, non corrigés**

| # | défaut |
|---|---|
| D21 | `MachineModel` n'a aucun consommateur de production trouvé ; sa docstring donne désormais la bonne unité de `trigger_tolerance` (pourcentage de T, R146). La façade `certus_physics` continue de l'exporter et ses tests de contrat restent actifs |
| D51 | INDEX garde sa propre lame de Beer-Lambert pour le substrat (`_calculate_RT_absorbing_sub_single`) : elle s'accorde avec le modèle commun `certus_substrate_absorption` à 1e-12 (k de 1e-7 à 1e-3, à 450 et 800 nm, testé, interface avant comprise depuis R117), mais c'est une seconde formule à tenir à jour |

**Le code, les tests et la documentation**

| # | défaut |
|---|---|
| D11 | **Une fenêtre de module fermée n'est pas détruite** : des lambdas et des `functools.partial` branchés sur les signaux de ses propres widgets la capturent, et la connexion les tient du côté C++ de PyQt, où le ramasse-miettes ne voit pas le cycle (`scripts/sonde_retenants_fenetre.py`, 2026-09-27 : `CertusREApp` retenue par quatre méthodes liées, cinq fermetures et deux attributs de `CertusToast` / `CertusToastStack`). **Sans effet en production** : le hub lance chaque module dans son propre processus (`QProcess`), et fermer la fenêtre finit le processus. Les tests détruisent désormais leurs fenêtres (R5). Coûterait dans tout processus qui construirait plusieurs fenêtres. Piste : `WA_DeleteOnClose` sur `CertusBaseApp`, à condition de retenir d'abord ses `QThread` encore actifs : sans cela, libérer la fenêtre libère un thread en cours (D23) |
| D23 | R114 a corrigé le préchauffage qui lisait hors de trois tableaux ; R121 a supprimé l'arrêt natif de finalisation des huit workers UI Windows (CI verte le 2026-10-04). Restent à instruire : six `gc.collect()` exécutés dans les threads de calcul STRAT (deux dans `_parallel_block_worker`, un dans `_run_segment`, un dans `_execute_nucleation_and_cost_mapping`, deux dans l'exécuteur du pipeline) peuvent libérer des objets Qt hors du thread GUI, sans arrêt observé ; les tests n'isolent pas `sys.modules`. L'arrêt pendant l'étage IR d'INDEX garde le résultat raffiné, décidé par 👤 (§3). Reproduire avant de changer le cycle de vie ; traiter avec D11 |
| D25 | Dette de lint masquée par `extend-ignore` : **15 règles**, E501 compris, et 1 479 violations à la mesure du plan (`scripts\metrics.py`, 2026-10-06 : `ruff --isolated`, E501 exclue ; 32 règles et 3 319 violations à sa base du 2026-09-30) ; plus aucun import étoile, et les noms indéfinis (F821, F822) sont à zéro. Par règle, avec la configuration du projet et ses exceptions par fichier (`ruff check --select` de la liste, 2026-10-06, 1 445 hors E501) : F401 590, gardés exprès pour la plupart (R9) ; E402 508 ; confusables RUF001 à RUF003 186 (des µ, × et – voulus) ; RUF100 62 ; PERF401 47 ; PT011 19 ; PT017 12 ; RUF005 10 ; RUF022, UP042 et UP046 3 chacune ; UP040 2 ; E501 en compte 2 623. Le cliquet `tests/oracle/test_lint_debt_ratchet.py` nomme les règles restantes : aucune ne peut entrer, et une règle sortie doit quitter sa liste. RUF022 (trier `__all__`) reste ignorée à dessein |
| D26 | Imports montants entre couches, mesurés le 2026-10-06 (`scripts\metrics.py`) : 20 arêtes, `certus.spline → certus.ui` (8), `certus.metal → certus.ui` (6), `certus.utils → certus.ui` (3), `certus.utils → certus.spline` (3) ; un cycle d'imports à l'exécution (le cœur de STRAT). Mesuré le 2026-09-29, module par module dans un interpréteur neuf : 72 des 73 modules de `certus/core`, `certus/physics` et `certus/domain` se chargent sans Qt, et tous ensemble n'en chargent aucun (garde-fou `test_computation_imports_no_qt`) ; le dernier, `certus.physics.gradient_analytic`, ne s'importe pas seul (cycle avec `gradient_utils`) |
| D40 | METAL BILAYER : l'analyse de faisceau minimise la MSE de réflectance seule, l'optimisation globale y ajoute une pénalité de lissage — deux objectifs, dont les RMSE ne se comparent pas |
| D42 | Neuf modules de bibliothèque appellent `create_module_environment(__file__)` à l'import : chacun reconfigure le journal CERTUS, dont la destination dépend alors de l'ordre des imports ; leur `script_dir`, leur propre dossier, ne sert presque jamais. L'insertion dans `sys.path` (R21) et le fil de préchauffage (R24) sont corrigés |
| D50 | Gelé, `loky` ne marche pas (repli sur des fils) et le multigraine reste refusé, le message le dit. La couche Numba du gel est D87, sa taille D72. Le job `release-windows` l'a construit et démarré sur un poste neuf le 2026-09-30 (R42) |
| D68 | Deux conséquences de R74 que 👤 peut défaire ou compléter. **(1)** Le hub ne lance plus l'échauffement JIT : il ne calcule rien, et ce fil de fond lui faisait charger numba, scipy et la physique. Sur un cache Numba vide (première installation), le premier module lancé compile donc seul ses noyaux, sans que le hub l'ait amorcé ; chaque module garde son propre échauffement. Revenir en arrière : retirer `jit_warmup=False` de l'appel du hub (le test de R74 le dira). Une voie qui garde le hub léger et amorce le cache : un processus fils à basse priorité lancé après l'affichage du hub — **non fait**, c'est un choix de conception. **(2)** La physique lit le silicium (`SI_*`, feuille `Si-substrate` de `indices.xlsx`) À L'IMPORT, par pandas et openpyxl (mesuré sur la fenêtre DESIGN, machine chargée : 0,53 s pour `materials_data`, dont 0,42 s d'import d'openpyxl) ; les rendre paresseux demande que les tableaux existent avant la première compilation de `get_nk_si` (numba les fige), donc toucher le chargement de la physique — **non fait** |
| D69 | Deux définitions d'indicateurs ont changé en route, et 👤 doit le savoir. **(1)** « Couverture des noyaux, compilation coupée » : le plan la mesurait par `oracle` + `core` (base 45,9 %, cible ≥ 70 %) ; elle se mesure maintenant par ces deux répertoires, `property` et les tests de `unit` marqués `kernels` (R78 : 74,0 %). La base de l'audit reste celle de l'ancienne définition ; avec l'ancienne, l'indicateur serait à 46,0 % le 2026-10-01 (non atteint). Je tiens la nouvelle pour la bonne (les tests des noyaux de STRAT ont été écrits pour cela), mais c'est un changement de critère. **(2)** « Modules à moins de 15 % de couverture » (13, cible ≤ 8) : `metrics.py` prend déjà la meilleure couverture de chaque fichier parmi les JSON donnés ; remesuré le 2026-10-01 avec la mesure de toutes les suites (1b67dd95) et celle des noyaux (f94523a5) : **6 modules** (R87), cible atteinte |
| D71 | Deux observations sur Tauc-Lorentz-Urbach (`gradient_analytic.py`), non corrigées. **(1)** k est calculé par √((|ε| − ε₁)/2), qui s'annule par différence là où ε₂ ≪ ε₁ : sous ε₂ ≈ 1e-7 (loin sous le gap) k revient à 0 ou à quelques pour mille près, soit moins de 2e-7 sur 2nk ; une différence finie de n ou de k y est fausse, la dérivée analytique est juste ; sans effet sur un empilement. **(2)** ε₂ saute en E = Eg : la queue d'Urbach, utilisée pour E ≤ Eg, vaut 1,9e-4 pour l'oxyde de l'exemple, l'absorption de bande (E > Eg) vaut 0 et monte jusqu'à l'ancre de la queue, posée à Eg + 0,01 eV ; le saut est de 2e-5 du maximum, sans effet sur un empilement, mais le modèle n'est pas continu là pour un ajustement qui passerait au bord du gap |
| D72 | **Taille du gel (S7.2) : objectif ≤ 300 Mo non atteint.** 411 Mo le 2026-10-06 (442 avant `5ccaa210`, qui laisse dehors IPython, pytest, hypothesis, coverage, astroid, pylint, black, mypy, ruff, sphinx, jedi, parso, notebook, jupyter et ipykernel ; hub et modules démarrent, artefact contrôlé). Le reste : llvmlite 115 Mo (Numba, indispensable), Qt 77 Mo (dont le rendu OpenGL logiciel), scipy 68 Mo avec ses bibliothèques, numpy 28, matplotlib 15, Pillow 13, pandas 13, lxml 7, OpenSSL 8. Étape suivante : mesurer ce que l'application charge vraiment (sous-modules de scipy, plugins Qt, ssl, lxml) avant d'autres exclusions. Un gel local embarque ce que porte l'interpréteur qui le construit : celui du 2026-10-06 contient aussi lxml, psutil, pywin32, PyYAML, certifi, charset_normalizer, MarkupSafe et cffi, absents de `requirements.lock`, d'où part le gel de la CI |
| D82 | **Thème sombre : logo et mesure de contraste à terminer.** Les textes et états vides suivent désormais le thème (R102). Le logo foncé reste peu visible en thème sombre, constat visuel sans mesure ; le harnais ne résout pas encore une encre de palette sur fond hérité. |
| D84 | **Validation locale intermittente.** Des écarts au dernier bit sur des tests STRAT apparaissent au premier passage après un changement de clé du cache Numba, puis disparaissent à la relance (deux fois le 2026-10-03 ; le 2026-10-06, `test_neutral_parameters_are_bit_identical_to_the_legacy_call` dans la validation de `29240ee7`, après la modification de `certus_colorimetry.py` : rouge à froid, vert à la relance, 0 ulp mesuré entre les deux appels du noyau). Signature compatible avec D52 : compilation sur place contre lecture du cache, cause non prouvée. Si l'écart persiste à la relance, comparer les noyaux froids et chauds avant de modifier le calcul. |

## 5. Ce qui attend une décision de 👤

Ces sujets demandent un jugement de physicien ou de propriétaire du produit. Les choix déjà faits figurent en section 3.

| sujet | ce qui est en jeu |
|---|---|
| **avis de tiers** | une ligne reste « à confirmer par toi » dans `THIRD_PARTY_NOTICES.md` : les DLL du runtime Visual C++ (`VCRUNTIME140*.dll`, `VCOMP140.DLL`) se redistribuent avec un programme, mais Microsoft réserve ce droit aux utilisateurs de Visual Studio sous licence |
| **interface** | Revoir visuellement les onze fenêtres et choisir les teintes de marque, la bande des fichiers récents et les bornes des champs numériques. |

D10, D41, D48, D54, D55, D56, D58, D65, D66, D76, D86, D87, D88 et D92 sont tranchés (§3) ou corrigés.

## 6. Chantiers spécifiés, en attente

**Calcul** (détail : `git show 7b08dc8:docs/archives/REPRENDRE_ICI.md`) —
dimensionner K, le nombre de graines à lancer : p ≈ 3/7 pour trouver un déposable, 2/7 pour
atteindre le niveau 0,57 · balayer `tp_hysteresis_factor` à bruit fixé · compter le criblage et
l'héritage quand un étage deviendra suspect · porter le résultat de `r75x2` dans la vitrine,
avec sa condition dans la même phrase que le chiffre · accélérer à résultat identique au bit : reste
l'attente du consommateur de statistiques (17 % du profil). `build_M_before_cache` est écarté : 10 151 appels pour
4 070 entrées distinctes sur le juge de paix, mais s'en souvenir ne fait rien gagner (2026-10-06, caches froids,
machine au repos : 434,9 et 431,5 s sans, 432,0 et 431,1 s avec, populations identiques au bit) ; ses 6 % venaient
d'un profil pris pendant une autre charge.

**Modèle physique** (détail : `git show 7b08dc8:docs/archives/TRAVAUX_A_VENIR.md`) :

| | sujet | état |
|---|---|---|
| 12.2 | modéliser le lissage de lecture | ouvert — surtout ne pas remonter le seuil |
| 12.3 | méconnaissance d'indice | spécifié : corridor de dispersion |
| 12.4 | grille d'échantillonnage à la cadence machine | ouvert, à faire avant 12.2 |
| 12.5 | quantification temporelle du déclenchement | ouvert |
| 12.6 | facteur de face arrière | en dernier, ou jamais |
| 12.7 | résolution du monochromateur | spécifié |

**Réserve** (détail : `git show 7b08dc8:docs/archives/RESERVE_A25_A27.md`) —
**A25** `sigma_rate` comme prédiction : la seule grandeur vérifiable de l'extérieur, contre les
±1 à 2 % que 👤 observe en salle · **A26** un bloc de santé de run (A27, le harnais C1, est fait : R45).

**Architecture** (détail : `git show 7b08dc8:docs/archives/PLAN_AMELIORATION.md`) —
reste un cycle à l'exécution (le cœur de STRAT), 20 arêtes montantes et les points chauds
de taille (32 fonctions de plus de 300 lignes, 12 de complexité supérieure à 60, 18 fichiers de plus
de 1 500 lignes le 2026-10-06), nommés dans `tests/architecture_debt.json` ; l'hygiène des imports (D25).

**Lint à effet possible (D25).** F401 est traité pour les imports sans rôle ; restent
E402/I001 et les petites règles, un cas à la fois.

| règle | ce qui peut changer un comportement | démarche proposée |
|---|---|---|
| F401 | un import « inutilisé » peut être un ré-export (y compris dans un import sur plusieurs lignes, ou un nom déclaré par `__all__.extend`), un effet de bord (enregistrement, sous-module `import a.b`, configuration numba avant un `@njit`), ou servi par une façade `CertusFacadeModule` | **fait** par lots (R9) : un nom ne part que si l'import est au niveau du module, hors `try`, sans accès dynamique du module à ses globales, et si aucun fichier suivi, aucune façade, aucun test qui charge le fichier par son chemin ni aucun code lancé depuis une chaîne ne le prend ; le reste est listé, pas retiré |
| I001, E402 | l'ordre des imports compte : cycle `physics ↔ core`, `configure_numba_env()` avant tout `@njit`, `QT_QPA_PLATFORM` avant la première `QApplication` | réordonner seulement les fichiers sans import à effet, jamais les façades ni `certus_core` ; E402 cas par cas |
| E741 | renommer `l`, `O`, `I` : sans effet, mais 89 cas dont des noyaux numba | après recompilation, `python scripts\c1_diff.py HEAD` (C1) |
| RUF046, RUF005, RUF015 | équivalences qui dépendent du type : `round(x)` d'un scalaire numpy rend bien un `int`, mais `round(x, n)` et `np.round(x)` rendent un `float64` (mesuré, numpy 2.5.2) ; `a + b` et `[*a, *b]` diffèrent si `a` est un tableau numpy | cas par cas, avec le type réel de l'argument |
| UP040, UP042, UP046 | changent l'objet à l'exécution (`TypeAliasType`, sous-classe de `str`, génériques PEP 695) | restent ignorées (arbitrage du 2026-09-27) |

**Contrôles du chantier lint** : ruff ; oracle ; unit ; `tests/ui/` ; le reste de `tests/` ; trois
photos avant/après — l'espace de noms final de chaque module touché (`scripts/lint_ns_snapshot.py`),
les modules que charge chaque script d'entrée une fois son fil de préchauffage fini, et les noms
que sert chaque façade `CertusFacadeModule`. Un nom qui disparaît ne doit être ni utilisé ni
demandé par personne.
**Ordre** : E402/I001, puis les petites règles.

**Prédictibilité** (détail : `git show 7b08dc8:docs/archives/CHANTIER_PREDICTIBILITE.md`) —
prédire sans tout calculer si un design passe avec un seul verre témoin ; quatre routes déjà
fermées par la mesure.

## 7. Les composants d'essai

| composant | fichier (`example/example_strat/`) | couches | notation | rôle |
|---|---|---|---|---|
| dichroïque | `JSON-strat-example.json` | 48 | 400-700 nm | le juge de paix : passe-court, front vers 545 nm |
| passe-bande 3 cavités | `JSON-strat-bandpass-3cav.json` | 35 | 600-660 nm | une résonance, une bande étroite |
| aléatoire | `JSON-strat-random75.json` | 75 | 550-750 nm | ni cavité, ni miroir, ni périodicité : teste si une règle est **générale** |
| passe-bande 5 cavités | `JSON-strat-bandpass-5cav-99c.json` | 99 | 610-655 nm | le cas dur |
| aléatoire ×2 | `JSON-strat-random75-x2-fabricable.json` | 75 | 550-750 nm | l'étalon depuis le 2026-08-20 : épaisseurs doublées, fente native 1 nm |

Une règle n'est acquise que si elle survit sur un empilement **sans structure**.
