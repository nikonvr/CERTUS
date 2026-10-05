# CERTUS — état du projet

> Ce document porte l'**état** : où en sont les programmes, les repères mesurés, ce que 👤 a
> décidé, les défauts ouverts et les chantiers. Les **règles** sont dans
> [`CLAUDE.md`](../CLAUDE.md). Il se tient **en place** : un fait change, on corrige sa ligne,
> on ne raconte pas la correction (`git log` s'en charge). Toute mesure porte sa date.
> Le détail et l'historique sont dans `git`, sans autorité (CLAUDE.md, en-tête).
> Mis à jour le 2026-10-05.

## 0. Reprise — à lire en premier, à tenir à jour

> Mettre à jour cette section avec le travail : « en cours » dès le début, mesure et commit
> à la fin. Les règles de validation sont dans les sections 2, 4 et 12 de
> [CLAUDE.md](../CLAUDE.md) ; les décisions scientifiques appartiennent à 👤 (§5).

**En cours (Codex, 2026-10-05).** D24 : l'audit couvre la racine,
`certus_physics` et les paquets `certus/metal`, `spline`, `core`,
`domain`, `physics` et `workers` : 1 791 définitions, 41 candidats
explicitement motivés dans la liste blanche, aucun candidat non résolu.
Sept symboles sans appel de production ont été retirés de CORE et UTILS,
dont un alias de résultat ; l'audit reconnaît
les imports renommés utilisés et les validateurs Pydantic. Il reste à
instruire les candidats exploratoires de `certus/utils` (15) et
`certus/ui` (26), puis à étendre le portail CI à tout `certus/` et
rejouer la validation complète. Les nombres exploratoires ne prouvent pas
qu'un symbole est mort.

**Point de départ.** `certus0310`, branche `refactor-corridors-mixins`,
[PR #5](https://github.com/nikonvr/CERTUS/pull/5), commits locaux non
poussés ; pousser attend l'ordre de 👤. `python scripts\preflight.py` →
`PREFLIGHT=GO` le 2026-10-05. Sauvegarde après chaque lot :
`../CERTUS_certus0310_<date>_<commit>.bundle`.
Une entrée Git `.git/worktrees/certus0310` incomplète déclenche un
avertissement de nettoyage à chaque commit, sans empêcher le commit.
L'arbre jetable `hyst2` contient le réglage d'hystérésis STRAT non commité ;
ne pas le retirer.

**Dernière validation complète (2026-10-05, Windows 11, Python 3.14.8,
commit `98f972d8`) :** Ruff 0 ; oracle 1 119 passed ; unit
4 897 passed, 5 skipped, 2 xfailed ; UI 1 297 passed, 12 skipped,
2 xfailed ; autres tests 350 passed, 2 skipped ; trois contrôles
documentaires 0 défaut. Les quatre retraits de CORE ont chacun passé C1
froid contre froid (8 008/8 008 tableaux identiques au bit) et l'oracle.
La validation complète des commits D24 ultérieurs reste à faire.
Les quatre pages HTML RE, DESIGN, INDEX SPLINE et STRAT rendent leurs
logigrammes Mermaid dans Chrome (8/8, 6/6, 5/5 et 6/6, mesuré le
2026-10-04).

**À faire après D24 :**

| chantier | prochaine action |
|---|---|
| STRAT : hystérésis, D14, D54, D55 | Arbitrages délégués à Claude par 👤. `hyst2` contient les deux configurations à comparer sur `r75x2` en `deep` ; mesurer les taux de plantage par niveau de bruit, les déposables et le meilleur SEEL. D14 est chiffré en §4 ; départager les extrema parasites de l'historique à densité égale. |
| Parité Zenodo SPLINE et RE | Comparer fonction par fonction les sources locales de `optics continuum/05_CODE_ET_ZENODO` et `publication_reverse/07_PAQUET_ZENODO` avec le code courant ; mesurer les écarts utiles. Le paquet RE local 1.2.0.dev0 et l'archive publique 1.1.1 diffèrent ; l'inversion conjointe de plusieurs échantillons est écartée par 👤. |
| D11 / D23, Qt | Rejouer `scripts/sonde_retenants_fenetre.py`, examiner les cinq `gc.collect()` des workers STRAT et les `QThread` retenus avant de toucher à `WA_DeleteOnClose`. |
| D77 | Seulement si la CI release devient rouge : lire stderr et l'artefact watchdog du premier job rouge. |

## 1. Où en sont les programmes

| programme | état | prochaine action |
|---|---|---|
| **Calcul (STRAT)** | composant étalon : l'aléatoire ×2 (`r75x2`) à la fente de 2 nm. Fabricable avec les rampes de la configuration livrée ; sans rampes, 3 graines sur 7 trouvent des déposables. Toute la fabricabilité passe par le générateur ELITE | voir la section 6 |
| **Interface** | plan clos le 2026-09-08 : 12 critères de fin sur 13 atteints et mesurés, le treizième démontré inatteignable (`xfail` strict) | la revue visuelle et trois arbitrages de 👤 (section 5) ; la fuite des fenêtres (défaut D11) |
| **Qualité** | CI : calcul sous Linux, interface sous Windows ; tests isolés des préférences de 👤 ; dette de lint de 14 règles masquées (D25) | E402/I001, D11 et défauts de la section 4 |
| **Documentation** | règles dans `CLAUDE.md`, état ici ; 15 rapports HTML, 34 schémas Mermaid et 2 SVG validés le 2026-10-03 ; anciens dossiers lisibles dans Git | tenir « un fait, un seul endroit » |
| **Validation externe** | 🔴 **aucune** : STRAT n'est validé que contre lui-même | deux dépôts réels du dichroïque (section 5) |

## 2. Repères mesurés — fente 2 nm, modèle courant

| composant | SEEL | plantage | condition |
|---|---|---|---|
| dichroïque 48 couches, `JSON-strat-example` | **0,173 nm** | 0 % | 6 blocs, une campagne |
| le même, modèle de `b60d80e2` (après R130) | **0,175 nm** | 0 % | 4 blocs (λ 544, 471, 467, 474 nm), 370 stratégies, aucune éliminée ; `scripts\bench_examples.py strat`, caches Numba vierges, 2026-10-04 (`reports/STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json`) ; depuis, sous `certus/physics` seul `gradient_oblique.py` a changé (DESIGN, D45) |
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
- Les repères du tableau, sauf la ligne datée du 2026-10-04, sont antérieurs à R130 : depuis, la gagnante est prise dans la classe du meilleur SEEL
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

- **Rien à cacher côté public** (« je n'ai aucune crainte de tout mettre en espace public, c'est mon choix ») : l'historique n'est pas purgé — ni le nom porté par les métadonnées de 44 classeurs anciens, ni l'adresse personnelle de quatre commits — et `git filter-repo` n'est pas au programme.
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

### STRAT — tranché par Claude sur délégation de 👤, 2026-10-04

👤 : « je ne me souviens plus trop de strat, je te propose de trancher les questionnements au plus
logique ». Chaque ligne donne la décision, sa raison et sa mesure ; une mesure qui la contredit la rouvre.

- **D73, la marge en transmission voit le point tournant sous l'arrêt** (R129). Quand la pente change
  de signe à l'échantillon d'arrêt, le sommet de la parabole des trois échantillons situe le point
  tournant dans le pas et donne son niveau ; la marge de son côté est l'écart en T à ce niveau. Raison :
  le critère existe pour interdire l'arrêt sur un point tournant, et il l'admettait (marges
  `(MARGIN_NONE ; 0,28)` à ±1,25 nm d'un quart d'onde). Mesuré sur 20 000 empilements aléatoires,
  noyaux compilés à froid : 18 383 réponses identiques au bit, les 1 617 autres changent d'un seul côté
  et toujours vers le bas, 1 148 passent sous le seuil `1,66 × A`. Sur le juge de paix en `fast`, la
  Phase A refuse 241 candidates sur 24 couches au lieu de 96 sur 21, et les 194 stratégies finales, leur
  ordre, leurs scores et `RESULT` sont identiques au bit : ces λ mouraient plus tard au Monte-Carlo.
- **D20, le classement montré et exporté suit la règle gravée** (R130) : les stratégies à moins d'un pas
  (0,01 nm) du meilleur SEEL restant forment une classe, ordonnée par plantage, puis marge de la couche
  critique, puis score brut (`order_by_the_ranking_rule`). Raison : la règle « un écart d'un pas est une
  égalité » n'atteignait aucun tableau — le run final triait par score brut, et les cases fixes de
  `rank_key_seel_yield_margin` séparent deux SEEL distants de 0,005 nm. La recherche interne (parents
  d'ELITE, diversité, consensus) garde son tri ; `use_margin_ranking` reste inactif. Mesuré sur le juge
  de paix en `fast` : même population de 194 stratégies, 147 positions changent, et la gagnante passe de
  la fusion à un bloc (SEEL 0,1843 nm, 2 % de plantage) à la stratégie ELITE à huit blocs (0,1892 nm, 0 %) ;
  `RESULT` passe de 0,008495 à 0,008950.
- **D70, le critère en épaisseur est retiré** (R131). `check_extrema_proximity` n'était appelé par la
  Phase A qu'avec des matrices nulles quand `phase_a_level_margin_factor` vaut 0, et ne refusait alors
  rien ; au-dessus, il n'était pas appelé. Le réglage « Extrema Exclusion Ratio » n'atteignait donc aucun
  calcul, et arrivait de surcroît dans le noyau comme une largeur en nm. Raison : la marge se compte en
  transmission (règle gravée). Le réglage rejoint `_RETIRED_CONFIG_KEYS` (un fichier ancien se charge et
  le dit), l'appel inerte disparaît, la fonction reste testée pour elle-même ; sa docstring, le commentaire
  du noyau de croissance et la page STRAT décrivent ce que fait le code (2 largeurs avant un point
  tournant, une demi après, et non 3 et 1). La page annonçait aussi un journal `[SURVIVAL]` qui n'existe
  pas : elle cite `[MARGIN]` et `[ADMISSIBILITY]`. Mesuré :
  C1 froid contre froid, 8 008/8 008 tableaux identiques au bit ; sur le juge de paix en `fast`, le run
  avec D70 et un cache Numba vierge est identique au bit au run D20 (194 stratégies, IDs, ordre, scores) ;
  sept cas du test des réglages retirés échouent sur le code d'avant. Un premier run avait relu des noyaux
  mis en cache par les tests : sept scores différaient au dernier bit, l'écart froid/chaud de D52.
- **D17, le critère du gain négatif est gardé ; le défaut est réfuté** (R132). Le gain négatif signale une
  couche qui ne se termine pas, sans bruit, après 1 nm d'erreur amont : une fragilité que la porte de
  plantage ne voit pas toujours. Le recensement compte désormais chaque gain négatif, même quand la porte de
  plantage a déjà écarté la candidate (`gain_negative_any`, et « of N with gain<0 » dans la ligne
  `[ADMISSIBILITY]`). Mesuré sur le juge de paix en `fast` : 159 candidates à gain négatif sur 48 couches,
  dont 146 déjà écartées pour plantage et 13 par ce seul critère ; les runs d'avant comptaient déjà ces 13.
  Le constat « n'a jamais rejeté une candidate » (n° 38) ne tient pas sur ce composant.
- **Hystérésis du détecteur, non tranché faute de mesure décisive.** Le seuil vaut `tp_hysteresis_factor ×
  bruit` du niveau Monte-Carlo (0,5×, 1×, 2×) en Phase B, et du bruit nominal en Phase A : à 0,5× et 2× les deux
  phases ne simulent pas la même machine. Principe retenu : un seul réglage, celui du bruit nominal de la fente.
  Mesuré sur le juge de paix en `fast` avec ce seuil fixe (clé `tp_hysteresis_reference`, arbre jetable, trace qui
  prouve que la clé atteint le calcul) : aucun durcissement — le plantage au bruit ×2 baisse pour 8 stratégies
  communes et ne monte pour aucune — et ce composant ne montre presque pas l'anomalie (26 croissantes, 167 plates,
  1 décroissante). Le test décisif est `r75x2`, où l'anomalie a été mesurée (8,7 contre 1) ; rien n'est activé avant.
- **D15, POEM garde quatre couches d'historique : mesuré sans effet.** Sur le juge de paix standard
  (`JSON-strat-example.json`, caches Numba vierges, 2026-10-04), rejouer douze couches au lieu de quatre rend les mêmes 370 stratégies,
  dans le même ordre, avec les mêmes taux de plantage à chaque niveau de bruit ; 303 scores diffèrent d'au plus 6,7·10⁻¹¹ en
  relatif (derniers bits). Le plafond « par construction » n'agit pas sur ce composant ; on garde quatre couches
  (`MAX_LOOKBACK_VAL`, inchangé), moins coûteux. Une
  mesure sur un composant à blocs plus longs qui montrerait un écart rouvrirait D15.
- **Clos sans changement de code** (raisonnement sur le code, sans mesure nouvelle) :
  - **D16** : la carte THICKNESS² est le carré du coût boosté, par construction (un bonus en 1/√s y
    devient 1/s), et la normalisation par la moyenne est un facteur commun, qui ne change aucun ordre de
    la DP.
  - **D18** : 0,025 (dynamique de la couche pendant son dépôt, filtre de candidates et besoin de Rate) et
    0,04 (écart entre les deux ancres POEM, règle de l'opérateur qui n'emploie pas POEM sur un swing trop
    faible) mesurent deux grandeurs. Une couche entre les deux est simulée en cible absolue, avec le bruit
    des ancres et la dérive photométrique : son erreur entre dans le score, la sélection la voit.
  - **D19** : la Phase A note chaque λ avec le noyau de croissance complet (comptage des points
    tournants, ancres POEM, atteignabilité du niveau) ; un terme de comptage en plus compterait deux fois
    la même chose.
  - **D22** : effet borné à une couche ; la Phase B simule le Rate exactement.
  - **D12** : sans exposition, `k = 1` dans toutes les configurations. Une moyenne en temps réel est
    causale par nature ; les ancres POEM, lues après coup, pourraient l'être sans retard : à revoir avec 12.2.
  - **D13** : la quantification `U(0 ; 0,125 nm)` a la même loi pour toutes les stratégies ; son
    écart-type (0,036 nm) est environ trois fois sous l'erreur de déclenchement due au bruit (~0,1 nm),
    à laquelle elle s'ajoute en quadrature (calcul, non mesuré). La compensation par la couche suivante
    dépend de la stratégie : à implanter si une mesure réelle le demande, pas avant.

### DESIGN — D45 et D46, tranchés par Claude sur l'ordre de 👤, 2026-10-04

👤 : « go et lance-toi dans la résolution des actions complexes », en réponse à la liste qui disait ces deux-là
bloquées par sa décision. Chaque correctif est un commit qu'un `git revert` annule seul.

- **D45, le gradient de DESIGN avec pile arrière est la dérivée de son coût** (R136). Il divisait par le nombre de
  points valides là où le coût divise par la somme de leurs poids : trop grand du poids moyen, de 1,07 à 1,94 sur les
  cas mesurés le 2026-09-30. Raison : l'optimiseur doit recevoir la dérivée de la fonction qu'il rapporte ; la valeur
  du coût et la direction du gradient étaient justes, pas son échelle. Mesuré : C1 froid contre froid, 7 915 tableaux
  sur 8 008 identiques au bit, dont les 240 du gradient sans pile arrière (`normal.gradall0`) ; les 93 autres sont le
  gradient avec pile arrière (`normal.gradall1`), qui change de 26 à 62 %. Oracle `1117 passed` ; le nouveau test
  (poids 1 et 3, points hors cible, k = 0 et 10⁻⁶) échoue sur le code d'avant et colle après aux différences finies
  à 10⁻⁵. Avec l'ancien gradient, L-BFGS-B atteignait les mêmes coûts finaux en jusqu'à 25 % d'évaluations de plus
  (2026-09-30) ; l'effet du correctif sur un design réel n'est pas mesuré.
- **D46, les bornes d'épaisseur de DESIGN s'arrêtent avant l'opacité** (R137). Au-delà de |Im φ| = 700 sur la
  grille (`PHASE_IMAG_OVERFLOW`), les noyaux rendent (R, T) = (0, 0) au lieu de l'absorbeur semi-infini ; or la borne
  haute du mode global, 1,2 × max(quart d'onde à λ₀, départ), vaut des centaines de micromètres pour un métal dans
  l'infrarouge, dont la partie réelle est minuscule. Les trois modes (global, local, healing) arrêtent désormais la
  borne haute à 1 % sous l'épaisseur d'opacité de la couche (`optim_opaque_thickness_limits`), où sa réponse ne bouge
  plus avec d. Raison : borner la phase dans les noyaux changeait les derniers bits (1e-15) des chemins à substrat
  réel ; borner les épaisseurs ne touche aucun noyau. Mesuré : une couche qui n'absorbe pas garde ses bornes au bit
  dans les trois modes ; pour un métal infrarouge (n = 0,02 − 60i, de 8 à 12 µm), la borne globale passait de plus
  de 100 µm à une épaisseur que `require_layers_below_overflow` accepte, et 2 % au-delà est refusé. Les noyaux
  répondent toujours (0, 0) au-delà ; les optimisations de DESIGN ne le leur demandent plus.

## 4. Défauts ouverts

Numérotés ici ; un défaut corrigé sort de la liste et son numéro n'est pas réattribué. Les
numéros de l'ancien registre sont entre parenthèses
(`git show 7b08dc8:docs/archives/DEFAUTS_OUVERTS.md`).

**Ils faussent un résultat ou trompent l'utilisateur**

| # | défaut | piste |
|---|---|---|
| D6 | Le consensus ignore `robustness_num_runs`, et `robustness_seed` dès que `consensus_seed_list` est renseignée (n° 18, 47) | exposer `consensus_num_runs` |
| D7 | Deux configurations rendent le même `RESULT` au bit alors qu'une bande diffère de 38 % (n° 15) | vérifier dans le code ce que `RESULT` agrège |
| D8 | `scripts/campagne_intervalles.py` forçait `search_resolution` à faux alors que 👤 en a fait un prérequis : les campagnes d'intervalles ont tourné sans recherche de fente (n° 49) | refaire les intervalles utiles avec la fente cherchée |
| D9 | Restreindre la plage de blocs vide la DP ; cause non établie (n° 54) | mesurer la recherche à plage complète |
| D10 | **L'ajustement Sellmeier 3 pôles est chaotique sur le saphir** : un ulp sur les données change le minimum atteint (RMSE de 0,00126 à 0,00208 sur 41 essais, 2026-09-26) ; deux machines rendent deux indices pour les mêmes données. SiO2 et BK7 sont stables | élargir le multistart ou reconditionner — change les résultats, décision de 👤 |
| D47 | DESIGN n'a pas de polarisation moyenne « Avg » : le tableau des cibles n'offre que s et p, et une configuration ancienne « Avg » se charge en s avec un avertissement (elle était calculée en p) | la calculer demande les deux ondes, chacune avec son gradient : décision de 👤 |
| D48 | L'épaisseur du substrat (1 mm par défaut, `DEFAULT_SUBSTRATE_THICKNESS_NM`) n'est un champ ni de DESIGN ni de STRAT : un substrat qui absorbe perd du flux selon cette épaisseur | exposer le champ : décision de 👤 (section 5) |

**Le modèle physique — connus, non corrigés**

| # | défaut |
|---|---|
| D14 | L'historique est échantillonné 1,33× plus grossièrement que la couche courante (`NPTS_PREV = 16` contre `NPTS = 64` sur trois épaisseurs nominales) (n° 22). **Mesuré le 2026-10-04** sur le juge de paix standard, caches Numba vierges, arbre `b60d80e2`, avec 21 points d'historique (`SCAN_NPTS_HISTORY`, la densité de la couche courante) : la population change presque entière — 363 stratégies contre 370, dont **8 plans en commun** (mêmes blocs, couches Rate et fente ; les 64 identifiants communs ne désignent pas les mêmes plans) ; sur ces 8, le score bouge de −3,3 % à +2,0 %. `RESULT` 0,007433 contre 0,007645 (−2,8 %, sous les ~8 % où deux runs sont indiscernables, §2) ; la gagnante devient 4 blocs λ 543/471/453/474 (SEEL 0,1724 nm contre 0,1749). Plantage moyen au bruit ×2 : 0,0069 contre 0,0012 ; stratégies dont le plantage croît avec le bruit : 122 contre 41 (239 plates, 2 décroissantes, contre 329 et 0). L'historique plus dense fabrique plus d'extrema parasites, ce qui est le sens attendu. À trancher : une densité unique, plus fidèle au balayage de la couche courante, contre le changement de tous les résultats ; le coût n'est pas mesuré (la machine n'était pas au repos). Sorties : `reports/STRAT_bench_juge_de_paix_b60d80e2_{temoin,d14_historique21}_2026-10-04.json` |
| D21 | `MachineModel` n'a aucun consommateur de production trouvé ; sa docstring donne désormais la bonne unité de `trigger_tolerance` (pourcentage de T, R146). La façade `certus_physics` continue de l'exporter et ses tests de contrat restent actifs |
| D51 | INDEX garde sa propre lame de Beer-Lambert pour le substrat (`_calculate_RT_absorbing_sub_single`) : elle s'accorde avec le modèle commun `certus_substrate_absorption` à 1e-12 (k de 1e-7 à 1e-3, à 450 et 800 nm, testé, interface avant comprise depuis R117), mais c'est une seconde formule à tenir à jour |
| D54 | `simulate_growth_kernel` avec `adaptive_scan=True` **et** la grille fine (`smoothing_window > 1` ou `machine_sampling_dd > 0`) lit hors du balayage grossier : le re-échantillonnage suppose 64 points sur trois fois l'épaisseur, le balayage adaptatif en a moins sur une autre fenêtre. La `margin_missed` rendue diffère d'un lancement à l'autre (mesuré le 2026-09-30 avec le corpus élargi de `c1_diff` : 6 cas sur 87 combinaisons, jusqu'à 20 % d'écart ; l'arbre de 421ab8f comparé à lui-même ne se retrouvait pas). **Exposition : nulle aujourd'hui** — aucun appelant, test, script ni page ne passe `adaptive_scan` (`git grep`) : l'option est morte. Le corpus de `c1_diff` évite la combinaison, faute de quoi il ne prouverait plus rien. **Même famille, même exposition nulle** : `machine_sampling_dd > 0` avec `smoothing_window == 1` prend la grille fine et **saute la dérive photométrique** (affine et courbure), qui n'est appliquée que dans la branche grossière ou dans celle du lissage ; `machine_sampling_dd` reste à 0,0 pour tous les appelants (`certus_strat_batch.py`). **À décider par 👤** : supprimer `adaptive_scan` (elle alourdit le dimensionnement de la fenêtre du noyau) et garder `machine_sampling_dd` seulement si on lui rend la dérive, ou réparer les deux |
| D55 | Sur la grille fine de la machine, une couche **rejouée** de l'historique est lue avec un pas grossier de retard : son balayage grossier commence à 1/16 de l'épaisseur (le point 0 est le dernier de la couche du dessous), l'indice d'interpolation commence à 0. Mesuré le 2026-09-30 sur `_resample_on_machine_grid` : une rampe en profondeur revient décalée de d/16 (6,25 % de l'épaisseur, 3 nm sur 50) puis plate sur le dernier seizième ; la couche courante, elle, est lue à sa vraie profondeur. **Exposition** : seulement quand la grille fine est active (`smoothing_window > 1` ou `machine_sampling_dd > 0`) ; l'effet sur les extrema rejoués n'est pas mesuré. **À décider par 👤** (le modèle de la chaîne de lecture est figé depuis le 2026-08-08). Le test est un `xfail` strict : il passera quand la lecture sera corrigée |
| D56 | Les jeux de coefficients de Sellmeier de D263T eco (n° 2) et de B270i (n° 4) de `certus/core/certus_substrate_db.py` donnent n_d = 1,5201 et 1,5257 à 587,56 nm. De mémoire, et **sans l'avoir vérifié**, les fiches du fabricant disent 1,5230 pour les deux ; la provenance de ces deux jeux n'est écrite nulle part. Les trois autres verres retrouvent leur indice publié à 1e-4 (silice fondue 1,45846, N-BK7 1,51680, saphir ordinaire 1,76820), et le noyau de production calcule l'indice de ces coefficients à 1e-12 près. Un écart de 3e-3 sur l'indice du substrat déplace la réflexion d'une face nue d'environ 4e-4 (calcul, pas mesure). Le test épingle les deux valeurs comme **mesurées, non validées** (R64) : changer ces nombres doit être une décision, donc casser un test |

**Le code et les tests**

| # | défaut |
|---|---|
| D11 | **Une fenêtre de module fermée n'est pas détruite** : des lambdas et des `functools.partial` branchés sur les signaux de ses propres widgets la capturent, et la connexion les tient du côté C++ de PyQt, où le ramasse-miettes ne voit pas le cycle (`scripts/sonde_retenants_fenetre.py`, 2026-09-27 : `CertusREApp` retenue par quatre méthodes liées, cinq fermetures et deux attributs de `CertusToast` / `CertusToastStack`). **Sans effet en production** : le hub lance chaque module dans son propre processus (`QProcess`), et fermer la fenêtre finit le processus. Les tests détruisent désormais leurs fenêtres (R5). Coûterait dans tout processus qui construirait plusieurs fenêtres. Piste : `WA_DeleteOnClose` sur `CertusBaseApp`, à condition de retenir d'abord ses `QThread` encore actifs : sans cela, libérer la fenêtre libère un thread en cours (D23) |
| D23 | R114 a corrigé le préchauffage qui lisait hors de trois tableaux ; R121 a supprimé l'arrêt natif de finalisation des huit workers UI Windows (CI verte le 2026-10-04). Restent à instruire : cinq `gc.collect()` exécutés dans les threads de calcul STRAT peuvent libérer des objets Qt hors du thread GUI, sans arrêt observé ; les tests n'isolent pas `sys.modules`. L'arrêt des raffinements IR après PGLOBAL d'INDEX relève du choix de 👤 en §5. | Reproduire avant de changer le cycle de vie ; traiter avec D11. |
| D24 | Code mort : l'audit (`tools/dead_symbol_audit.py`) couvre la racine, `certus_physics`, `certus/metal`, `spline`, `core`, `domain`, `physics` et `workers` : 1 791 définitions, 41 candidats exemptés avec raison, 0 non résolu (2026-10-05). Il reconnaît les imports renommés utilisés et les validateurs Pydantic. Restent `certus/utils` (15 candidats exploratoires) et `certus/ui` (26), puis l'extension du portail CI à tout `certus/`. L'appariement par nom nu sous-signale le code mort ; la liste blanche doit conserver une raison vérifiable pour chaque exception. |
| D25 | Dette de lint masquée par `extend-ignore` : **14 règles** (31 au départ de S5.5) et 1 464 violations à la mesure du plan (3 455 au départ) ; plus aucun import étoile, et les noms indéfinis (F821, F822) sont à zéro. F401 : 629 signalements, 590 hors tests gardés exprès pour la plupart (R9) ; restent surtout E402 (548) et les confusables RUF001 à RUF003 (188, des µ, × et – voulus). Le détail est en R69. Le cliquet `tests/oracle/test_lint_debt_ratchet.py` nomme les règles restantes : aucune ne peut entrer, et une règle sortie doit quitter sa liste. RUF022 et RUF023 (trier `__all__`, `__slots__`) restent ignorées à dessein |
| D26 | Inversions de couches, comptées le 2026-08-19 : `utils → ui` (11), `core → workers` (10), cycle `physics ↔ core` (23 et 29 imports). Mesuré le 2026-09-29, module par module dans un interpréteur neuf : 72 des 73 modules de `certus/core`, `certus/physics` et `certus/domain` se chargent sans Qt, et tous ensemble n'en chargent aucun (garde-fou `test_computation_imports_no_qt`) ; le dernier, `certus.physics.gradient_analytic`, ne s'importe pas seul (cycle avec `gradient_utils`) |
| D40 | METAL BILAYER : l'analyse de faisceau minimise la MSE de réflectance seule, l'optimisation globale y ajoute une pénalité de lissage — deux objectifs, dont les RMSE ne se comparent pas |
| D41 | INDEX, INDEX SPLINE, RE, METAL et DESIGN arrêtent leurs workers dans leur propre `closeEvent` avant d'appeler celui de base : la question « un calcul tourne, fermer quand même ? » ne peut pas s'y poser. La leur donner, c'est demander avant d'arrêter, comme STRAT — un changement de comportement à la fermeture |
| D42 | Neuf modules de bibliothèque appellent `create_module_environment(__file__)` à l'import : chacun reconfigure le journal CERTUS, dont la destination dépend alors de l'ordre des imports ; leur `script_dir`, leur propre dossier, ne sert presque jamais. L'insertion dans `sys.path` (R21) et le fil de préchauffage (R24) sont corrigés |
| D50 | Le dossier gelé (`dist/CERTUS_HUB/`, 443 Mo, mesuré le 2026-09-30) embarque les bibliothèques de développement que tirent pandas et Numba (IPython, pytest, hypothesis, coverage, astroid…) ; `loky` ne marche pas gelé (repli sur des fils) ; Numba gelé n'a qu'un fil (`workqueue`), par conception ; le multigraine reste refusé dans l'exécutable gelé, le message le dit. Le job `release-windows` l'a construit et démarré sur un poste neuf le 2026-09-30 (R42) |
| D58 | `certus/utils/certus_reset_framework.py` (le bouton de remise à zéro) : la feuille de style est une chaîne ordinaire, pas un f-string, donc `font-size: {Typography.BODY_LG}pt;` est écrit tel quel et Qt ignore la déclaration : le bouton garde la police par défaut au lieu de celle que son auteur voulait. Observé le 2026-10-01 en cherchant les `color: white` ; **non changé** : le réparer change l'aspect d'un bouton, et c'est au propriétaire de dire quelle taille il veut |
| D65 | `_update_data_table` (`certus/ui/certus_index_ui_export.py`) lit encore `n_fit_R_only` (six fois), la colonne que D62 a fait retirer du tracé : aucune sortie d'optimiseur ne l'écrit (la stratégie IR n'écrit que `n_fit_T_only` / `k_fit_T_only`, `delta_n`, `delta_k`). Branches mortes du même genre ; **non changé** : le retrait est une décision de 👤, comme D62 |
| D66 | La légende de gauche du tracé n / k d'INDEX (`_update_nk_plot`) est créée par `addLegend` APRÈS le tracé des courbes n : pyqtgraph ne liste que les courbes ajoutées après elle, donc elle est vide au premier tracé d'une fenêtre et remplie aux suivants (la légende de k, construite à la main, est complète). Vu en écrivant le test du tracé (R73) ; **non changé** : créer la légende avant les courbes change l'aspect du premier tracé |
| D68 | Deux conséquences de R74 que 👤 peut défaire ou compléter. **(1)** Le hub ne lance plus l'échauffement JIT : il ne calcule rien, et ce fil de fond lui faisait charger numba, scipy et la physique. Sur un cache Numba vide (première installation), le premier module lancé compile donc seul ses noyaux, sans que le hub l'ait amorcé ; chaque module garde son propre échauffement. Revenir en arrière : retirer `jit_warmup=False` de l'appel du hub (le test de R74 le dira). Une voie qui garde le hub léger et amorce le cache : un processus fils à basse priorité lancé après l'affichage du hub — **non fait**, c'est un choix de conception. **(2)** La physique lit le silicium (`SI_*`, feuille `Si-substrate` de `indices.xlsx`) À L'IMPORT, par pandas et openpyxl (mesuré sur la fenêtre DESIGN, machine chargée : 0,53 s pour `materials_data`, dont 0,42 s d'import d'openpyxl) ; les rendre paresseux demande que les tableaux existent avant la première compilation de `get_nk_si` (numba les fige), donc toucher le chargement de la physique — **non fait** |
| D69 | Deux définitions d'indicateurs ont changé en route, et 👤 doit le savoir. **(1)** « Couverture des noyaux, compilation coupée » : le plan la mesurait par `oracle` + `core` (base 45,9 %, cible ≥ 70 %) ; elle se mesure maintenant par ces deux répertoires, `property` et les tests de `unit` marqués `kernels` (R78 : 74,0 %). La base de l'audit reste celle de l'ancienne définition ; avec l'ancienne, l'indicateur serait à 46,0 % le 2026-10-01 (non atteint). Je tiens la nouvelle pour la bonne (les tests des noyaux de STRAT ont été écrits pour cela), mais c'est un changement de critère. **(2)** « Modules à moins de 15 % de couverture » (13, cible ≤ 8) : `metrics.py` prend déjà la meilleure couverture de chaque fichier parmi les JSON donnés ; remesuré le 2026-10-01 avec la mesure de toutes les suites (1b67dd95) et celle des noyaux (f94523a5) : **6 modules** (R87), cible atteinte |
| D71 | Deux observations sur Tauc-Lorentz-Urbach (`gradient_analytic.py`), non corrigées. **(1)** k est calculé par √((|ε| − ε₁)/2), qui s'annule par différence là où ε₂ ≪ ε₁ : sous ε₂ ≈ 1e-7 (loin sous le gap) k revient à 0 ou à quelques pour mille près, soit moins de 2e-7 sur 2nk ; une différence finie de n ou de k y est fausse, la dérivée analytique est juste ; sans effet sur un empilement. **(2)** ε₂ saute en E = Eg : la queue d'Urbach, utilisée pour E ≤ Eg, vaut 1,9e-4 pour l'oxyde de l'exemple, l'absorption de bande (E > Eg) vaut 0 et monte jusqu'à l'ancre de la queue, posée à Eg + 0,01 eV ; le saut est de 2e-5 du maximum, sans effet sur un empilement, mais le modèle n'est pas continu là pour un ajustement qui passerait au bord du gap |
| D72 | **Taille du gel (S7.2) : objectif ≤ 300 Mo non atteint.** Reconstruit le 2026-10-03 avec PyInstaller 6.22.3 dans un dossier temporaire, `PATH` assaini : 447 675 580 octets, 7 307 fichiers ; hub et dix modules passent `release_checks.py --check-frozen --check-frozen-run`. Aucun `excludes` n'a été essayé (`certus_hub.spec` a `excludes=[]`). L'application (`certus/`, `certus_physics/`, les `CERTUS_*.py`) n'importe aucune des bibliothèques de développement que le gel embarque (D50) — balayage AST : IPython, pytest, hypothesis, coverage, astroid, pylint, black, mypy, ruff, sphinx, jedi, parso, notebook, jupyter, ipykernel : 0 import ; setuptools, pip, wheel, tkinter aussi, à essayer avec prudence (numba en a un usage optionnel). Étape suivante : exclure les douze premières dans une copie et mesurer taille et démarrage de tous les modules ; inspecter plugins Qt et sous-modules de scipy avant d'autres exclusions |
| D76 | **METAL SINGLE, analyse du faisceau : objectif et gradient différents.** `gradient_function_fixed_eM` donne la dérivée de la partie données à 2e-10 près, mais `objective_function_fixed_eM` ajoute une pénalité de lissage 1e-2 sans sa dérivée : écart relatif au gradient du coût complet de 1,7e-3 (nœuds lisses) à 1,9e-2 (rugueux). Décision de 👤 : ajouter la dérivée ou retirer la pénalité. Le point distinct sur les nœuds internes METAL BILAYER est corrigé en R113. |
| D82 | **Thème sombre : logo et mesure de contraste à terminer.** Les textes et états vides suivent désormais le thème (R102). Le logo foncé reste peu visible en thème sombre, constat visuel sans mesure ; le harnais ne résout pas encore une encre de palette sur fond hérité. |
| D84 | **Validation locale intermittente, partiellement instruite.** Sur une copie propre de `HEAD`, `test_uniform_weights_reproduce_the_unweighted_functional` avait rendu un écart de 5,55e-17 (Numba 0.68.0 installé alors pour 0.67.0 au verrou) ; un test du workflow échouait sur une modification locale aujourd'hui absente ; la limite du test de concurrence était dépassée sur une passe Windows. Le benchmark de croissance attendait deux valeurs quand le noyau en rend cinq : corrigé par R103 et rejoué avec `pytest-benchmark 5.3.0` dans un dossier temporaire (`1 passed in 1.46s`, puis `6 passed in 5.77s` pour le fichier). Le 2026-10-02, sur l'arbre courant avec Numba 0.67.0 : les deux tests unitaires ciblés passent (`2 passed in 6.21s`), le test de concurrence ciblé passe (`1 passed in 3.94s`), puis la suite unit entière passe (`4830 passed, 5 skipped, 6 xfailed in 972.14s`) et le reste de `tests/` passe (`347 passed, 2 skipped in 579.07s`). Ces passes ne prouvent pas que les écarts intermittents ont disparu. Le 2026-10-03, juste après un changement de la clé du cache (R114) : `test_neutral_parameters_are_bit_identical_to_the_legacy_call` et `test_the_slit_profile_is_inert_when_absent_or_zero` (`test_strat_phase_a_state_coherence.py`) en échec au bit à la première passe d'unit, verts à trois relances (`11 passed`) et à la passe complète suivante ; de nouveau après R117, le premier des deux seul, vert à la passe complète suivante. Deux fois sur deux après un changement de clé, aucune sur les passes à cache chaud du même jour : la signature de D52, un noyau compilé sur place contre un noyau relu du cache, que l'enquête D52/D67 doit trancher. | Établir la cause de l'écart au bit s'il revient en suite complète. |
| D85 | **Le préchauffage RE ne va jamais au bout.** `_warmup_re_physics`, lancé au démarrage de chaque application par `_bg_warmup`, lève `IndexError: index 2 is out of bounds for axis 0 with size 2` dans `_global_evaluate_oblique_physics` (`n_lay_full[pos_all, :]`), que son `except Exception` avale (mesuré le 2026-10-03, compilé et interprété) : les noyaux RE qui suivent ne sont pas préchauffés, le premier calcul RE les compile. Sans risque mémoire, numpy contrôle cet indice. **Non corrigé** : un préchauffage RE qui irait au bout ferait tourner plus longtemps des noyaux parallèles en fond, et le gel (couche `workqueue`) ne tolère pas deux appels parallèles concurrents (D77, R107) ; à mesurer dans le gel avant d'y toucher. |

## 5. Ce qui attend une décision de 👤

Ces sujets demandent un jugement de physicien ou de propriétaire du produit. Les choix déjà faits figurent en section 3.

| sujet | ce qui est en jeu |
|---|---|
| **le dépôt dans Google Drive** | un dépôt git synchronisé par Drive est lent et exposé aux copies de conflit dans `.git` ; ce dossier est en plus partagé par deux PC sous deux chemins différents. Recommandé : un clone hors Drive par machine. Non fait : déplacer l'arbre de travail pendant qu'on y travaille n'est pas une opération sûre |
| **données Nb2O5 « Syrus »** | dans les feuilles `Nb2O5-Syrus` et `IR-Syrus-Nb2O5` de `example/database_index/indices.xlsx`, n tombe de 2,09 à 4,0 µm à 1,19 à 4,7 µm puis remonte à 1,78 à 5 µm, quand les feuilles H400 et H800 restent entre 2,07 et 2,13. Un creux de cette taille avec k ≤ 0,018 n'est pas physique |
| **défaut D10** | fiabiliser l'ajustement Sellmeier du saphir : **change des résultats de production** |
| **interface** | Revoir visuellement les onze fenêtres et choisir les teintes de marque, la bande des fichiers récents et les bornes des champs numériques. La branche locale `claude/charming-wright-43077a` contient des couleurs à évaluer avant intégration. |
| **Stop pendant l'étage IR d'INDEX** | interrompre aussi les raffinements qui suivent PGLOBAL, ou garder le résultat raffiné livré aujourd'hui (détail : D23) — change ce que voit l'utilisateur |
| **validation externe** | deux stratégies réellement déposées du dichroïque, avec leurs spectres mesurés. Le test est **ordinal** : STRAT doit les classer dans le bon ordre |
| **fichiers hors git** | `Selenium_Optical_Constants*.pdf` (œuvre d'un tiers) et `studies/selenium_bk7/` (recherche non publiée, dont des scripts sources) : ignorés désormais, donc dans aucun clone. **À sauvegarder à la main avant tout changement de machine**, ou à commiter si tu le décides |
| **poste de travail** | le venv `C:\envs\certus` (numba 0.66) est inutilisé depuis le passage au Python système : à supprimer si tu le confirmes |
| **deux fenêtres débranchées** | STRAT montre l’accueil générique alors que `certus_strat_welcome_ui.py` existe ; le moniteur d’indices d’INDEX SPLINE (`certus_index_spline_monitor_ui.py`) n’est plus appelé que par un test. Rebrancher ou retirer ces fenêtres ? Recommandé : les rebrancher. |
| **protection de `master` et Dependabot** | Décider si l’épinglage des actions par SHA devient obligatoire, si une relecture ou `release-windows` devient un contrôle requis (après D77), et quoi faire des PR Dependabot #1 à #4. |
| **avis de tiers** | Écrire `THIRD_PARTY_NOTICES` pour les éléments redistribués sous licence propre (icônes Lucide, données d’indices, textes tiers). |
| **le substrat qui absorbe (D48)** | Confirmer l’épaisseur par défaut de 1 mm, ou en faire un champ de DESIGN et STRAT ; elle décide de la perte de flux. |
| **la polarisation « Avg » (D47)** | la retirer du tableau des cibles de DESIGN, comme aujourd'hui, ou la calculer : les deux ondes, leur moyenne et leurs gradients |

D54 et D55 ne sont plus en attente de 👤 : délégués à Claude le 2026-10-04 avec les autres questions STRAT (ligne 1 du §0).

## 6. Chantiers spécifiés, en attente

**Calcul** (détail : `git show 7b08dc8:docs/archives/REPRENDRE_ICI.md`) —
dimensionner K, le nombre de graines à lancer : p ≈ 3/7 pour trouver un déposable, 2/7 pour
atteindre le niveau 0,57 · balayer `tp_hysteresis_factor` à bruit fixé · compter le criblage et
l'héritage quand un étage deviendra suspect · porter le résultat de `r75x2` dans la vitrine,
avec sa condition dans la même phrase que le chiffre.

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
de taille, nommés dans `tests/architecture_debt.json` ; l'hygiène des imports (D25).

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
