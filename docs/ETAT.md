# CERTUS — état du projet

> Ce document porte l'**état** : où en sont les programmes, les repères mesurés, ce que 👤 a
> décidé, les défauts ouverts et les chantiers. Les **règles** sont dans
> [`CLAUDE.md`](../CLAUDE.md). Il se tient **en place** : un fait change, on corrige sa ligne,
> on ne raconte pas la correction (`git log` s'en charge). Toute mesure porte sa date.
> Le détail et l'historique sont dans `git`, sans autorité (CLAUDE.md, en-tête).
> Mis à jour le 2026-10-12.

## 0. Reprise — à lire en premier, à tenir à jour

> Mettre à jour cette section avec le travail : « en cours » dès le début, mesure et commit
> à la fin. Les règles de validation sont dans les sections 2, 4 et 12 de
> [CLAUDE.md](../CLAUDE.md) ; les décisions scientifiques appartiennent à 👤 (§5).

**Point de départ.** `certus0310`, branche `claude/ecstatic-newton-3grmls` : `master` (`80dd7d3c`), plus
`parite-zenodo` (PR [#8](https://github.com/nikonvr/CERTUS/pull/8)) et l'audit de l'arrêt de STRAT face à un OMS
(`reports/STRAT_audit_declenchement_OMS_2026-10-10.md`) ; PR [#9](https://github.com/nikonvr/CERTUS/pull/9) en
brouillon vers `master`. Les entrées `.git/worktrees/certus0310`, `profwt`, `buildwt`, `valwt`, `ratewt` et `ratewt2`, incomplètes (Drive en
refuse la suppression), déclenchent un avertissement à chaque commit sans l'empêcher.

**Dernière validation complète** (2026-10-13, Windows 11, Python 3.14.8, Ryzen 7 5700G, `631c4830` ; depuis, seuls des rapports,
ce document et le texte de mesure d'un levier du registre ont changé) : Ruff 0 ;
oracle 1 143 passed en 54 s ; unit 5 406 passed, 7 skipped en 24 min 35 ; UI 1 324 passed, 12 skipped, 2 xfailed en
22 min 24 ; autres tests 348 passed, 2 skipped en 10 min 20 ; trois contrôles documentaires : 0. Un premier passage de l'unit, à
`978b8f04`, avait rendu deux rouges (`test_the_architecture_debt_only_shrinks` : `certus_strat_consensus.py` à 1 529 lignes et
`_apply_elite_refinement_if_enabled` à 307) ; `631c4830` les ramène sous les plafonds, avec les mêmes candidats. C1 : aucun fichier de
noyau n'a changé depuis `dbf8025f`, mesuré contre `master` (196 s) : 299 tableaux sur 8 008 diffèrent (`strat.growth` 295,
`strat.states` 4), tous sur la grille machine (pas > 0 ou lissage > 1), que la branche corrige (D93 à D95) ; les 171 cas de
croissance sans grille machine sont identiques au bit. Contre `212126d4`, où ces 299 écarts avaient été mesurés : les 8 008
tableaux sont identiques au bit.

**Un seul indice de saphir** (2026-10-12, `reports/SAPHIR_indice_unique_2026-10-12.md`). La référence est le Sellmeier d'id 3
(rayon ordinaire, Malitson et Dodge) ; les mesures absolues de la séance 24-03 en donnent le niveau à +0,0003 ± 0,0028, donc on ne
la corrige pas. « Sapphire Fresnel » (un second Sellmeier, n plus bas de 0,0077 ; dans METAL, un substrat N-BK7 sans un mot) est un
alias de l'id 3 (`b9223b43`) ; les tables mortes `sapphire fresnel.xlsx` et `sapphire_index.txt` sont supprimées (`925b3788`) ;
`tests/unit/test_one_sapphire_index.py` garde l'unicité. Reste : C1 et C3 diffèrent entre le JSON et le code (n : 4,6·10⁻⁷ au plus),
non alignés pour ne pas changer le hash verrouillé du JSON. Validé en entier avec le reste à `631c4830` (validation ci-dessus).

**D103, trouvé le 2026-10-11, corrigé par `de9a2025`** (`reports/STRAT_D103_identifiants_en_double_2026-10-11.md`). En
`deep` et `extreme`, la DP rend jusqu'à 2 × `top_k` groupements par carte de coût, numérotés dans des plages de cent :
les rangs 100 à 199 d'une carte prenaient les numéros de la suivante, et le consensus, qui range ses scores par
identifiant, donnait aux deux homonymes le score d'un seul. Présent depuis le premier commit ; `fast` et `premium` (au
plus 40 et 80 groupements par carte) n'en sont pas touchés. Les cent premiers groupements de chaque carte gardent leur
numéro, les suivants ont leur propre plage. Mesuré le 2026-10-12 sur `r75x2` : les graines 42, 404 et 505, que le
garde-fou d'unicité retenait, vont au bout ; les graines 101 et 202 sont identiques champ par champ, et les graines 77
et 303 portent les mêmes plans, scores, plantages et marges (18 et 41 plans renumérotés). Les résultats `deep`
antérieurs à la correction (campagnes d'août, repères de la section 2 hors `r75x2` sans rampes) ont pu choisir leurs
parents ELITE sur des scores mélangés.

**D100 corrigé le 2026-10-11** (`2cba90f4`) : les interrupteurs de STRAT reçoivent de nouveau le fichier chargé. Du
2026-09-08 au 2026-10-11, tout résultat STRAT a tourné sans Rate, sans biais de fente et sans recherche de fente, sauf
surcharge explicite (`reports/STRAT_D100_interrupteurs_non_charges_2026-10-11.md`).

**L'optique reprend après le Rate** (2026-10-12 ; `reports/STRAT_ELITE_couches_Rate_paquets_2026-10-12.md`). 👤 observe en salle de bonnes
stratégies qui alternent des paquets d'optique à une λ et des paquets de Rate (« purement empirique »). Le noyau le permettait ; la recherche ne le
proposait pas. ELITE déplace maintenant les couches Rate de ses parents (`elite_rate_moves`, actif par défaut depuis `978b8f04` ; `allow_rate`
faux l'éteint) : `r75x0.5` (graines 42 / 101 / 202) 0,5031 / 0,4981 / 0,5000 → **0,4347 / 0,3967 / 0,3967 nm** (le meilleur plan des graines 101 et 202 : trois
paquets de Rate et deux fenêtres d'optique de deux couches, la première à 451 nm), juge de paix 0,1849 → **0,1721 nm**, `r75x2` (graines 101 / 42) 0,5406 / 0,5678
→ 0,5358 / 0,5477 nm ; le meilleur SEEL baisse dans les six exécutions, toutes les listes sont déposables, au modèle de Rate de STRAT (sans dérive de la source).

**Modèle d'arrêt de production et Rate dans tous les scénarios** (2026-10-12 ;
`reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`, `reports/STRAT_r75x0.5_secours_rate_2026-10-12.md`). D96, D97 et D98 sont le
modèle d'arrêt par défaut (`8d9ced13`, décision de 👤, §3) : l'attente sans fin retire 95 % des plans que l'ancien modèle jugeait
fabricables (6 sur 120 au rejeu) et la recherche du juge de paix n'en garde que 2 sur 1 112. Le Rate entre dans chaque design : le
secours Rate (`0fc7c5f2`, `40642146`) pose au temps la queue des plans dont le contrôle optique cède, et les enfants d'ELITE gardent
les couches Rate de leur parent (`4a4e1f0d`). Avec eux, `r75x0.5` et un seul verre témoin, que la recherche ne savait pas fabriquer
(0 déposable sur 8 687 plans), rend 3 383, 3 701 et 3 279 plans déposables aux graines 42, 101 et 202 (meilleur SEEL 0,5031 / 0,4981 /
0,5000 nm) ; le juge de paix, 0,1849 nm. Ces SEEL sont ceux du modèle de Rate de STRAT (§7), dont la stabilité de la vitesse n'est pas
mesurée. D106 (les enfants d'ELITE étaient notés sans biais de fente) est corrigé par `6fcdd56a`, et son effet est mesuré par un A/B :
à `r75x2` sans rampes (graine 101, ancien modèle d'arrêt, sans secours Rate, même code), **706 déposables sur 6 042** stratégies sans la
correction, **0 sur 4 821** avec elle ; la graine 42 : 0 sur 4 561. Les déposables optiques de `r75x2` d'avant la correction (« six
graines sur sept » ci-dessous) étaient des enfants d'ELITE sans biais de fente : **sans rampes, `r75x2` n'est pas fabricable en optique
pure**. Avec les défauts de production, tous les plans de la liste le sont (4 175 et 4 307 plans aux graines 101 et 42, meilleur SEEL
0,5406 et 0,5678 nm), avec du Rate (`reports/STRAT_r75x2_D106_secours_Rate_2026-10-12.md`). Au juge de paix (ancien modèle d'arrêt, sans
secours, graine 42), D106 fait passer le meilleur SEEL de 0,1776 à 0,1927 nm (+8,5 %) : les repères du juge de paix d'avant la correction
sont optimistes d'autant.

**Mesure d'avant D106 (2026-10-12), D100 et D103 corrigés**
(`reports/STRAT_r75x2_sept_graines_D100_D103_corriges_2026-10-12.md`, code `411e6eb5`). `r75x2` en `deep`, sans
rampes, protocole d'août, sept graines : **six trouvent des déposables** (42, 77, 101, 202, 404, 505 ; août : trois),
la 303 n'en trouve aucun ; meilleurs SEEL de 0,5323 à 0,6354 nm, médiane 0,5563 nm. Tous les déposables sont des plans
ELITE. L'ELITE « tour à tour » sur les six graines (`reports/STRAT_ELITE_tour_a_tour_six_graines_2026-10-12.md`) :
meilleur SEEL médian +0,7 % (mieux une fois, de 14,7 %), pas de gain net démontré. Les déposables de `r75x2` de cette mesure sont des
enfants d'ELITE sans biais de fente : D106 les invalide (ci-dessus). Mesures du
2026-10-11 (`reports/STRAT_remesure_D100_2026-10-11.md`, `782972bf`) : juge de paix **0,178 nm** (`premium`, ancien modèle d'arrêt, même
`RESULT` au bit après D103) ; le passe-bande de 99 couches en une campagne reste non fabricable (0 déposable sur
2 139, plantage minimal 82,7 %) ; `r75x0.5` avec un seul verre témoin : aucun déposable aux graines 42, 101 et 202
avant le secours Rate, plantage minimal 8,3 % à la graine 101 (§7).

**Prochaines actions — à lancer avec une autre IA.** Lire dans l'ordre : [`CLAUDE.md`](../CLAUDE.md) (les règles et les onze interdits),
ce §0, puis l'action choisie. Chaque action est **autonome** : pourquoi, quoi lancer (commandes exactes), quand elle est finie, ce qu'il ne
faut pas faire. Faire A1 d'abord ; les autres sont indépendantes les unes des autres, par priorité décroissante. Une action peut donner
plusieurs commits, chacun d'une seule chose (C3). **Jamais de `git push`, jamais de fusion de la PR #9 : l'un et l'autre sont à 👤.** La
branche a été poussée à `bee0d3c5` le 2026-10-13, sur l'ordre de 👤 ; les commits locaux qui suivent restent à pousser sur son ordre.

**Vocabulaire.**
*Rate* : couche posée pour un temps, à la vitesse estimée sur les couches du même matériau contrôlées optiquement (ce n'est pas un quartz).
*Paquet de Rate* : couches consécutives au Rate. *Fenêtre d'optique* : couches contrôlées optiquement entre deux paquets. *Queue* : le Rate va
d'une coupure à la dernière couche. *Plan mixte* : de l'optique après du Rate. *Plan optique pur* : aucune couche au Rate. *Déposable* :
plantage inférieur à 5 % au pire des trois niveaux de bruit (0,5×, 1×, 2×). *SEEL* = 2·√score, en nm, toujours rapporté avec la graine et le
mode. Les indices de couche des artefacts commencent à 0 ; l'interface et les rapports numérotent à partir de 1 (« L18-L75 » = indices 17 à 74).

**En vigueur au 2026-10-13** (ne pas le remettre en cause sans mesure) : D96, D97 et D98 (attente sans fin) ; le secours Rate (`rate_rescue`) ;
`rate_by_swing` ; ELITE déplace les couches Rate de ses parents (`elite_rate_moves`) ; les enfants d'ELITE portent le biais de fente (D106) et
gardent les couches Rate de leur parent. Dernière validation complète : `631c4830` (ci-dessus). Les preuves sont dans `reports/STRAT_*_2026-10-12*`.

**Avant toute action.**
1. `python scripts\preflight.py` doit finir par `PREFLIGHT=GO` (l'arbre où l'on édite est celui qu'`import certus` résout).
2. `git status -sb` propre ; noter `git log -1` : c'est le point de départ de l'action.
3. Lancer la validation de CLAUDE.md §2 **en entier** avant de committer du code : un sous-ensemble de tests a déjà laissé passer une régression
   (le garde-fou `tests/unit/test_the_architecture_debt_only_shrinks.py` ne tourne pas avec les tests voisins).

**Mesurer, une fois pour toutes** (toutes les actions de mesure suivent ce protocole ; il a produit tous les rapports du 2026-10-12).
```bat
rem depuis la racine du dépôt ; l'arbre jetable pèse plusieurs Go : le supprimer en fin de mesure
git worktree add --detach "%TEMP%\mesure_wt" HEAD
cd /d "%TEMP%\mesure_wt"
set CERTUS_BENCH_TIMEOUT_S=21600
python scripts\probe_blocs_vs_plantage.py r75x0.5 deep 0 0 2 0 101 0
python scripts\resumer_artefact_sonde.py reports\blocs_vs_plantage_r75x0.5_deep_s101.json
```
- Les 8 arguments : composant (`48c` juge de paix, `35c`, `75c`, `99c`, `r75x0.5`, `r75x1.5`, `r75x1.75`, `r75x2`, `r75x2-2nm`), mode (`fast`,
  `premium`, `deep`), recherche de fente (1 pour le juge de paix, 0 ailleurs), `require_turning_point` (0), résolution du monochromateur en nm (2),
  élargissement (0), graine, réglages de production (0 = rien n'est forcé). Les rapports du 2026-10-12 utilisent `48c premium 1 0 2 0 <graine> 0`,
  `r75x0.5 deep 0 0 2 0 <graine> 0` et `r75x2 deep 0 0 2 0 <graine> 0`.
- Pour changer un réglage sans toucher au code : `set CERTUS_PROBE_OVERRIDES=cle=valeur,cle2=valeur2` **et** `set CERTUS_PROBE_TAG=etiquette`
  (l'étiquette est obligatoire avec une surcharge ; elle entre dans le nom de l'artefact). Les valeurs `true` et `false`, les entiers et les flottants
  sont reconnus. Vider les deux variables après l'essai.
- L'artefact est écrit dans `reports\` **de l'arbre jetable** : `blocs_vs_plantage_<composant>_<mode>_s<graine sur trois chiffres>[_<etiquette>][_fente].json`.
  Si le nom existe déjà, un horodatage s'ajoute : prendre le plus récent par date de modification. Il porte le commit, `git_dirty` (doit être faux, sauf
  A/B voulu), les surcharges et les réglages Rate effectifs (`config`).
- **Une seule mesure à la fois sur la machine** (sinon `RESULT=None` ou dépassement du délai) ; pas de test lancé pendant une mesure. Ordres de grandeur,
  machine seule (Ryzen 7 5700G, 16 threads) : juge de paix `premium` 9 min ; `r75x0.5 deep` 44 min ; `r75x2 deep` 44 à 52 min.
- **Lire un écart avec prudence** : à 150 tirages la dispersion d'un meilleur SEEL est de l'ordre de 6 % (§2) ; deux exécutions à moins de 8 % ne se
  distinguent pas. Le SEEL d'un gagnant est le minimum de plusieurs milliers de plans. Un résultat meilleur que prévu se vérifie avant de le croire
  (rejeu de la graine de base, `rmse_par_bruit` dans l'artefact).
- **Vérifier qu'un réglage arrive au calcul** avant de lui attribuer un effet : sa valeur dans `config` de l'artefact et sa ligne de journal
  (`[ELITE-RATE]`, `[RATE-RESCUE]`, `[RATE]`).
- Fin : copier les artefacts utiles dans un dossier de `reports\` (pour une exécution sans déposable, retirer `margin_by_layer`, `lambdas` et
  `rmse_par_bruit` de chaque stratégie : voir `reports/STRAT_r75x2_D106_secours_Rate_2026-10-12/`), écrire un rapport en français dans `reports\` (protocole,
  tableau, ce qui n'est pas mesuré), mettre à jour ce document, `git worktree remove --force "%TEMP%\mesure_wt"`. Aucun chemin personnel dans un
  fichier versionné. Les entrées `.git/worktrees/*` que Drive refuse de supprimer sont normales.

**A1 — Vérifier la CI de la PR #9** (30 min, d'abord). *Pourquoi* : 105 commits ont été poussés le 2026-10-13 ; la CI calcule sous Linux et teste
l'interface et le gel sous Windows. *Faire* : `gh pr checks 9` ; pour un job rouge, `gh run view <identifiant> --log-failed`, corriger la cause (un
commit par cause), rejouer la validation locale. *Fini quand* : `lint`, `security`, `tests` et `release-windows` sont verts sur le dernier commit
poussé, ou chaque rouge est expliqué dans ce §0 avec sa cause. *Ne pas* : pousser, fusionner la PR, supprimer ou assouplir un test, agrandir
`extend-ignore`.

**A2 — Confirmer `elite_rate_moves` sur les composants et les graines non mesurés** (≈ 8 à 15 h de machine, par cellules indépendantes).
*Pourquoi* : l'option est active par défaut depuis `978b8f04` sur six exécutions (`r75x0.5` aux graines 42, 101, 202, le juge de paix à la graine 42,
`r75x2` aux graines 101 et 42) : le meilleur SEEL baisse dans les six (de 0,9 à 20,7 %). *Faire* : pour chaque cellule du tableau, deux exécutions au même
commit, la première aux défauts, la seconde avec `set CERTUS_PROBE_OVERRIDES=elite_rate_moves=false` et `set CERTUS_PROBE_TAG=sans_mouvements`.

| composant (arguments 1 à 3) | graines | durée d'une exécution |
|---|---|---|
| `r75x1.5 deep 0`, `r75x1.75 deep 0` | 42 et 101 | non mesurée (compter 45 min) |
| `35c deep 0`, `75c deep 0` | 42 | non mesurée (la mesurer à la première) |
| `48c premium 1` (juge de paix) | 77, 101, 202 | 9 min |
| `r75x0.5 deep 0`, `r75x2 deep 0` | 77 ; 202 et 77 | 44 min ; 45 à 52 min |

(Les arguments 4 à 8 sont toujours `0 2 0 <graine> 0`.) *Fini quand* : un rapport « STRAT_ELITE_couches_Rate_autres_composants » (date du jour) donne, par
cellule, le meilleur SEEL sans et avec, l'écart, les nombres de plans déposables, la classe et la forme du meilleur plan (`resumer_artefact_sonde.py`), et
conclut en une phrase : « le défaut reste » (le meilleur SEEL baisse ou reste dans la dispersion partout, aucune liste ne perd ses déposables) ou « à
signaler à 👤 » (une dégradation de plus de 8 % ou une liste qui perd ses déposables). *Ne pas* : changer le défaut ; `elite_rate_moves=false` n'est
qu'une surcharge de mesure.

**A3 — Refaire les repères d'avant D106 et d'avant D96-D98** (§2 ; ≈ 6 h). *Pourquoi* : ces nombres datent d'avant D106 (qui coûte 8 % au juge de paix et retire tous les déposables optiques de `r75x2`)
et d'avant le secours Rate : leur population n'est plus celle de la production. *Faire* : le juge de paix au banc officiel, aux défauts : `python scripts\bench_examples.py strat
--auto-yes --out reports\STRAT_bench_juge_de_paix_<commit>_defauts_<date>.txt` (33 min ; `RESULT` et `STRAT_RANK00..09` sont les chiffres à reporter) ;
puis, avec la variable `CERTUS_DESIGN_JSON` pointant le fichier de `example/example_strat/` (`set CERTUS_DESIGN_JSON=example\example_strat\JSON-strat-bandpass-3cav-deep.json`,
à changer à chaque composant) la même commande pour le passe-bande de 35 couches (`JSON-strat-bandpass-3cav-deep.json`), l'aléatoire de 75 couches (`JSON-strat-random75.json`),
`r75x2` à fente native (`JSON-strat-random75-x2-fabricable.json`) et la configuration livrée avec rampes (`JSON-strat-random75-x2-fabricable-2nm.json`) ;
le passe-bande de 99 couches à verres témoins multiples se refait par intervalles (`python scripts\campagne_intervalles.py --etat` puis ses vagues : lire sa
docstring, c'est long). *Fini quand* : chaque ligne concernée de la table du §2 porte le nombre refait, sa condition (commit, mode, graine) et son
rapport ; les anciens nombres sont retirés (un fait, un seul endroit). *Ne pas* : modifier `example/example_strat/JSON-strat-example.json` (interdit 4).

**A4 — Le Rate évince-t-il l'optique pure ?** (conception 2 h, mesure 2 h). *Pourquoi* : au juge de paix, les plans optiques purs déposables sont passés de
487 à 50 (ancien modèle d'arrêt), le meilleur plan optique pur de 0,178 à 0,193 nm ; l'hypothèse, non mesurée, est qu'ELITE, dont les parents sont
maintenant en majorité des plans Rate, raffine moins la lignée optique pure (`reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`, mesure 4). *Faire* : un
levier `elite_optical_parents` (entier, `0` = le chemin d'avant, **bit pour bit** : le prouver comme `tests/unit/test_strat_elite_rate_moves.py` le fait
pour `rate_moves=False`) qui garantit, parmi les parents d'ELITE, au moins M plans sans aucune couche Rate quand la liste en contient ; le mesurer au
juge de paix (graine 42) avec M = 0, 2, 4, puis à `r75x0.5` (graine 101). *Fini quand* : pour chaque M, le meilleur SEEL optique pur, le meilleur SEEL
global et le nombre de plans optiques purs déposables, dans un rapport. **Le contrat de taille** : `certus/core/certus_strat_consensus.py` est à 1 498
lignes (plafond 1 500) et `_apply_elite_refinement_if_enabled` à 299 (plafond 300) : ne rien y ajouter qui ne soit pas compensé, mettre la logique dans
`certus/core/certus_strat_robustness_rate.py` comme `_elite_rate_candidates`. *Ne pas* : l'armer par défaut (c'est à 👤).

**A5 — ELITE : plus de tours, autre budget pour les mouvements sur les couches Rate** (≈ 4 h). *Pourquoi* : ELITE fait 3 tours en `deep` et s'arrête
quand rien ne progresse ; la recherche des paquets est une escalade qui n'a peut-être pas fini. *Faire* (`r75x0.5`, graine 101, référence : 0,3967 nm) :
`elite_rounds=6,elite_stop_on_no_gain=false`, puis `elite_rounds=10,elite_stop_on_no_gain=false` ; puis, à 3 tours, `elite_rate_max_candidates=40` et
`elite_rate_max_candidates=360`. Une surcharge à la fois, avec son étiquette. *Fini quand* : un tableau tours et budget → meilleur SEEL, durée, nombre de
paquets de Rate du meilleur plan. Si les largeurs de fenêtre (`ELITE_RATE_WINDOWS`) ou le pas (`ELITE_RATE_STEP`) méritent un balayage, en faire des
paramètres **inactifs par défaut** (chemin d'avant identique) avant de les mesurer. *Ne pas* : changer un défaut sans 👤.

**A6 — Le modèle de Rate sans dérive de la source** (le sujet scientifique central ; **ne pas commencer sans la valeur de 👤**). *Pourquoi* : tous les SEEL
des plans Rate supposent une vitesse constante pendant le dépôt (`certus/physics/certus_strat_growth.py`, « RATE MODE ») ; 👤 observe en salle ±1 à 2 %
(§6, A25) et de bons plans en paquets alternés. Le modèle ne peut ni confirmer ni infirmer ce qui vient de la salle. *Faire* : (1) **demander à 👤** la
dérive ou l'instabilité de la vitesse pendant un dépôt (relative, par couche ou par run, et comment elle a été observée) ; ne pas l'inventer ; (2) ajouter un
paramètre **inactif par défaut** qui perturbe l'épaisseur des couches Rate (tirage fonction pure de la graine, du tirage et de l'indice physique,
`_seeded_noise_sample` de `certus/physics/certus_strat_math.py`, jamais de la stratégie : C2), sur le modèle de `stop_model_flags`
(`certus/physics/certus_strat_readings.py`) et de `tests/unit/test_strat_stop_model_is_the_decided_one.py` ; `python scripts\c1_diff.py HEAD` doit rendre « C1 TENU »
avant de committer ; (3) refaire `r75x0.5` (graine 101), le juge de paix et `r75x2` (graine 101) avec la dérive de 👤 divisée par 3, telle quelle et multipliée par 3,
et comparer la forme du meilleur plan (queue, paquets alternés, optique pur). *Fini quand* : le tableau, le rapport, le §6 mis à jour. *Ne pas* : activer par
défaut ; conclure sur une seule graine.

**A7 — Proposer les corrections de la vitrine `pages/CERTUS_STRAT.html`, sans l'éditer** (2 h). *Pourquoi* : la vitrine suit un régime strict (CLAUDE.md §10) : 👤
la relit avant qu'on la touche. Ses §10.18 et §10.19 citent les chiffres d'août ; ses déposables de `r75x2` sans rampes sont invalidés par D106 ; elle dit que le Rate
est « offert mais jamais choisi » à ×1,5, ×1,75 et ×2 (« zero out of 1510 »), ce qui n'est plus vrai à `r75x2` aux défauts de production (tous les plans
déposables portent du Rate ; ×1,5 et ×1,75 ne sont pas mesurés aux défauts). *Faire* : écrire un fichier
« STRAT_vitrine_passages_a_relire » (date du jour) dans `reports\` : pour chaque passage, la ligne, le texte actuel, ce qui est faux, le texte proposé (en anglais,
chaque nombre sourcé dans un rapport, la limite montrée : le modèle de Rate n'a pas de dérive). *Fini quand* : le fichier est écrit ; **la page n'est pas modifiée**.
Après accord explicite de 👤, une action séparée l'édite puis lance `python scripts\verifier_html.py pages\CERTUS_STRAT.html` (0 point à instruire).

**A8 — Dette technique** (§4 et §6) : un défaut par tâche, un commit par changement, jamais `ruff check --fix`, jamais agrandir `extend-ignore`.
- *D25, lint* : mesure officielle `python -m ruff check . --isolated --select "E,F,I,B,UP,RUF,PT,PERF" --ignore E501 --line-length 120 --target-version py314 --statistics`
  (1 416 violations le 2026-10-12 : F401 659, E402 555, RUF001 77, RUF003 59, RUF002 51, RUF100 10, RUF022 3, F811 2). Une règle ne quitte `extend-ignore`
  qu'à zéro violation, dans le commit qui met à jour la liste de `tests/oracle/test_lint_debt_ratchet.py`. Commencer par E402, module par module, avec les trois
  photos avant/après du §6 (`scripts/lint_ns_snapshot.py`). RUF001 touche des chaînes dont des libellés vus de l'utilisateur : ne pas les réécrire sans 👤.
- *D26, imports montants* : 20 arêtes (§4) ; commencer par celles qui ne demandent qu'un symbole à descendre dans `certus/domain/` ou `certus/core/` ; après chaque
  correction `python scripts\metrics.py --dette tests\architecture_debt.json` met le registre à jour (il ne fait que rétrécir).
- *D23 puis D11, D50, D72* : reproduire D23 avant tout (`scripts/sonde_retenants_fenetre.py`) ; ne pas toucher `WA_DeleteOnClose` avant (§4). D72 (taille du gel) après la
  fiabilité du gel.
- *D82* (logo du thème sombre) demande des yeux ; *D84* (écart au dernier bit au premier passage après un changement de clé du cache Numba) : relancer une fois avant de
  conclure à une régression ; *D68* (silicium lu à l'import) est optionnel.

**Décisions qui n'appartiennent qu'à 👤 — une IA ne les tranche pas, elle rapporte les mesures.**
1. D98 : l'attente sans fin (défaut) ou l'arrêt tardif (`oms_arming=1`) — chiffres au §3 et dans `reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`.
2. `elite_rate_moves` : garder actif (défaut actuel) ou le désarmer (`False`, ou `git revert 978b8f04`) — A2 apporte les mesures.
3. `rate_rescue_hard` : inactif, mesuré sans gain (35 plans déposables sur 410) — le garder ou le retirer.
4. Le Rate et l'optique pure (§5, A4) ; la valeur de la dérive du Rate (A6) ; D71 (2) ; l'information D69 (changement de définition d'un indicateur).
5. Toute poussée (`git push`), toute fusion de la PR #9, toute modification de la vitrine.

## 1. Où en sont les programmes

| programme | état | prochaine action |
|---|---|---|
| **Calcul (STRAT)** | composant étalon : l'aléatoire ×2 (`r75x2`) à la fente de 2 nm. Sans rampes, aucun plan optique pur n'est déposable une fois D106 corrigé (graines 101 et 42, 2026-10-12) ; avec les défauts de production (secours Rate), tous les plans de la liste le sont, au modèle de Rate de STRAT (§2). La voie à rampes de la configuration livrée (mesurée avant D106) est à refaire | A2 à A6 (§0) |
| **RE** | indices tabulés lus en n − ik depuis R148 (2026-10-05) : tout RE antérieur fait sur des indices absorbants en incidence oblique est à refaire ; un indice demandé hors de sa table est prolongé par une constante, avec un avertissement (ex-D86, `dec73219`, 2026-10-05) | — |
| **Base de dépôts** | 140 monocouches mesurées au Photon RT (`example/database_depots/`, importées le 2026-10-11 par `scripts\importer_base_depots.py`) ; la voie (T ou R) se lit dans la géométrie du détecteur, le mode manuel déclarant « Transmittance » quoi qu'il mesure. INDEX les charge par « Deposit database… ». Onze ajustements certifiés de l'application autonome, dont le spectre est un dépôt de la base, servent de références (`references_index.json`) ; `scripts\bench_base_depots.py` y confronte INDEX. Banc du 2026-10-12 (11 références × 3 exécutions, `reports/BASE_DEPOTS_banc_INDEX_2026-10-12.md`) : neuf références sur onze à moins de 2,0 % d'épaisseur de la référence, deux non retrouvées (`mesures-c1b-sio2`, −49 %, et `sb2s3-silice`, −3,85 %), cause non cherchée. RE ne la lit pas : il lui faut un classeur complet | instruire les deux échecs ; choix de 👤 (§5) |
| **Exécutable gelé** | sur la couche OpenMP depuis `31745571` (D87), sans les outils de développement depuis `5ccaa210` (411 Mo) ; construit à `dbec2fc1` le 2026-10-06, hub et modules contrôlés au démarrage, et 👤 y a calculé : « l'exécutable fonctionne ». Les licences de ce qu'il embarque le suivent (`licenses/`) | A8 (D72, §0) |
| **Interface** | plan clos le 2026-09-08 : 12 critères de fin sur 13 atteints et mesurés, le treizième démontré inatteignable (`xfail` strict) | A8 (§0) et choix de 👤 (§5) |
| **Qualité** | CI : calcul sous Linux, interface sous Windows, gel construit et démarré sous Windows, audit de sécurité (`pip-audit`, `gitleaks`) ; tests isolés des préférences de 👤 ; l'audit du code mort couvre tout `certus/`. Indicateurs du plan le 2026-10-06 (`scripts\metrics.py`) : tous dans leur cible, sauf la couverture et la taille du gel, non remesurées ce jour | rangs 5 et 6 |
| **Documentation** | règles dans `CLAUDE.md`, état ici ; 15 rapports HTML, 34 schémas Mermaid et 2 SVG validés le 2026-10-03 ; anciens dossiers lisibles dans Git | tenir « un fait, un seul endroit » |
| **Validation externe** | 🔴 **aucune** : STRAT n'est validé que contre lui-même, et c'est assumé (décision de 👤 du 2026-10-06 : les deux dépôts réels du dichroïque ne sont plus prévus) | — |

## 2. Repères mesurés — fente 2 nm, modèle courant

| composant | SEEL | plantage | condition |
|---|---|---|---|
| dichroïque 48 couches, `JSON-strat-example` | **0,173 nm** | 0 % | 6 blocs, une campagne |
| le même, D100 corrigé (`782972bf`) | **0,178 nm** | 0 % | 5 blocs (λ 544, 471, 466, 467, 462 nm), 823 stratégies dont 154 éliminées, `RESULT` 0,007917103726810235 ; `scripts\bench_examples.py strat` (`premium`), caches de l'arbre, 2026-10-11 (`reports/STRAT_bench_juge_de_paix_782972bf_D100_2026-10-11.txt`). Sous D100 (`b60d80e2`) : 0,175 nm |
| le même, défauts du 2026-10-13 (D96 à D98, secours Rate, ELITE déplace les couches Rate) | **0,1721 nm** | 0 % | 2 blocs, 2 652 stratégies, toutes déposables, toutes avec du Rate ; `scripts/probe_blocs_vs_plantage.py 48c premium 1 0 2 0 42 0`, `cea0db66`, 2026-10-12. Sans les mouvements sur les couches Rate : **0,1849 nm** (1 bloc, 2 260 stratégies dont aucune éliminée, `RESULT` 0,00854267382381426 ; `scripts\bench_examples.py strat` (`premium`), caches de l'arbre, `03990e9a` ; `reports/STRAT_bench_juge_de_paix_03990e9a_D96-D98_secours_Rate_2026-10-12.txt`). Les cinq combinaisons du modèle d'arrêt au code final, sans ces mouvements : de 0,1759 à 0,1854 nm (`reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`). Sans le secours (`8d9ced13`) : 0,2000 nm, 2 plans déposables sur 1 112 |
| passe-bande 3 cavités, 35 couches | **0,482 nm** | 0 % | 6 blocs, mode `deep` |
| aléatoire `JSON-strat-random75`, 75 couches | **0,272 nm** | 0 % | une campagne, 241 déposables sur 662 |
| passe-bande 5 cavités, 99 couches | **0,81 nm** | 0 % par campagne | 4 verres témoins, partition 0-22 / 22-42 / 42-76 / 76-99 |
| le même en une seule campagne | aucun score valide | 100 % | 487 stratégies, toutes plantent : non fabricable |
| aléatoire ×2 `r75x2`, fente native 1 nm | **0,6248 nm** | 0 % | `deep`, pur optique, 277 déposables ; mesuré avant D106 : à refaire |
| `r75x2` à 2 nm, configuration livrée | **0,5676 nm** | 1,67 % | avec `example/example_strat/rampes_r75x2-2nm.json` ; étendue 0,55 % sur 3 graines ; mesuré avant D106 : à refaire |
| `r75x2` à 2 nm, sans rampes, défauts de production du 2026-10-12 | **0,5406 nm** (graine 101), 0,5678 nm (graine 42) | 0 % | `deep`, `dbf8025f` : tous les plans de la liste déposables (4 175 et 4 307), aucun optique pur, du Rate (61 et 23 couches) ; l'optique pur sans secours Rate : 0 déposable aux deux graines (D106 corrigé). Avec ELITE qui déplace les couches Rate (`cea0db66`, graine 101) : 0,5358 nm ; graine 42 (`5da02db9`) : 0,5477 nm. `reports/STRAT_r75x2_D106_secours_Rate_2026-10-12.md` |

Le passe-bande de 99 couches est chiffré en moyenne de trois graines, jamais par la meilleure.

**Lire ces chiffres :**

- 🔴 **Les SEEL ne se comparent pas d'un composant à l'autre** : ils sont notés sur des
  domaines de largeur différente (section 7). Toute comparaison **à composant fixé** est valide.
- 🔴 **Un score seul ne départage rien.** À N = 150 tirages, la dispersion Monte-Carlo vaut
  σ ≈ 6 % ; deux runs à moins de ~8 % sont indiscernables. On compare des **classes
  d'équivalence SEEL**. Sur `r75x2`, σ ≈ 1,8 % mesuré en changeant le triplet de graines de
  consensus : un bruit emprunté à un autre composant ne vaut rien.
- Ces repères comprennent le **biais de fente** ; une mesure sans ce biais ne leur est pas comparable.
- 🔴 Les repères où des enfants d'ELITE comptent, mesurés avant la correction de D106 (2026-10-12), les notent sans biais de fente : `r75x2` sans rampes perd tous ses déposables optiques à la correction (§0). Les repères du juge de paix en sont aussi touchés.
- 🔴 Les repères mesurés en `deep` avant la correction de D103 (passe-bande de 35 couches, `r75x2` à fente native de
  1 nm, `r75x2` avec rampes) ont pu choisir leurs parents ELITE sur des scores de consensus mélangés entre homonymes
  (§0).
- Le banc `scripts\bench_examples.py strat` lit sa configuration dans `CERTUS_DESIGN_JSON` ; par défaut le juge de
  paix standard (`JSON-strat-example.json`). Les mesures `fast` de D5, D73, D20, D70 et D17 prenaient
  `JSON-strat-example-fast.json` (194 stratégies), celles de D14 et D15 le standard (370) : les deux ne se comparent pas.
- Les repères du tableau, sauf les deux lignes du juge de paix au modèle de `782972bf` et de `03990e9a`, sont antérieurs à R130 et
  à D96 à D98 par défaut (2026-10-12) : à refaire. Depuis R130, la gagnante est prise dans la classe du meilleur SEEL
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
| `tp_hysteresis_factor` | 1,66 en usage. Cible 1,00, mesurée à k = 8 et N = 800 : à remesurer avant de l'appliquer, les configurations tournant à k = 1. |
| `phase_a_level_margin_factor` | 1,66 ; 3,33 à évaluer |
| `index_corridor` | 0,005 en indice absolu, actif |
| `photometric_curvature_amp` | **0,00375**, actif |
| `affine_scale_amp`, `affine_offset_amp` | 0,05 et 0,02 |
| `allow_rate` | vrai — « le cas général » |
| `rate_by_swing` | vrai, dans l'application comme dans le noyau (2026-10-12) : des variantes Rate aux couches dont la dynamique est sous 0,025 |
| `rate_rescue`, `rate_rescue_few` | vrai, 10 (2026-10-12) : le secours Rate pose en Rate la queue des plans qui plantent ; 30 plans × 8 coupures quand aucun plan ne se termine, 3 × 2 à partir de 10 plans déposables, linéaire entre les deux |
| `elite_rate_moves`, `elite_rate_max_candidates` | vrai, 120 (2026-10-13) : ELITE déplace les couches Rate de ses parents (optique, paquet de Rate, optique à une autre λ) ; `allow_rate` faux l'éteint |
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

- **CERTUS tourne toujours sur un poste à jour** : les bornes minimales de `pyproject.toml` ne comptent pas ; la CI ré-résout vers les dernières versions stables à chaque run (`uv sync --upgrade`), `uv.lock` n'est qu'un point de départ (`uv lock --upgrade`). Pas de pré-version.
- **La non-reproductibilité est acceptée** : INDEX, RE et METAL_BILAYER ne rendent pas deux fois la même RMSE — leurs générateurs ne sont pas amorcés, et on ne les amorce pas. Mesuré le 2026-09-27 : INDEX de 0,002546 à 0,002691 sur dix exécutions, et 0,0067 (2,6 fois la référence) environ une fois sur huit ; RE 0,05 % ; METAL_BILAYER 1 %. La garde de convergence retient pour eux la meilleure de quatre exécutions au plus (`tests/regression/test_convergence_guard.py`).
- **Fastmath conservé dans tous les noyaux JIT — décidé le 2026-10-03** : 👤 arbitre « on garde fastmath » (D52/D67). Les gains de vitesse (7 à 19 %) sont conservés ; la non-reproductibilité froide vs chaude (jusqu'à 424 ulp sur les gradients, 1e-13 en relatif) est acceptée. Le harnais C1 maintient ses comparaisons froid à froid.

### Licence et comportement par défaut — décidé le 2026-09-29

- **Le projet est publié sous GPL-3.0** : c'est ce que PyQt6 exige de l'exécutable gelé (R36).
- **Quatre changements du comportement par défaut de DESIGN, acceptés** (R29) : la porte de stagnation et les seuils de gain prédit du Needle sont ceux réglés sur la fenêtre ; la phase globale est plafonnée quand la croissance topologique est cochée ; les graphiques prennent le fond du thème compact ; le substrat complexe est lu en oblique.
- **La sauvegarde des commits locaux** est un bundle Git hors dépôt (`../CERTUS_certus0310_<date>_<commit>.bundle`), à actualiser après chaque lot non poussé ; pousser requiert ton ordre.

### Publication — décidé le 2026-09-30

- **Rien à cacher côté public** (« je n'ai aucune crainte de tout mettre en espace public, c'est mon choix ») : l'historique n'est pas purgé — ni le nom porté par les métadonnées de 44 classeurs anciens, ni l'adresse personnelle de quatre commits — et `git filter-repo` n'est pas au programme.
- **Les œuvres de tiers restent à leurs auteurs** : la GPL-3.0 ne les couvre pas (le texte de thèse de l'historique, les PDF d'articles). Elles vont dans les avis de tiers, pas dans une purge.

### Interface — décidé le 2026-09-28

- **INDEX : les réglages d'absorption du substrat ne s'affichent que pour le silicium**, le seul
  substrat dont le calcul lit l'absorption ; pour tous les autres, le worker force k = 0 (D43).

### Indice du saphir — décidé le 2026-10-12

- **Un seul indice de saphir dans CERTUS** : le Sellmeier d'id 3, partout (noyaux, INDEX, INDEX SPLINE, STRAT, FIELD, METAL).
  Aucune table de saphir, aucun second Sellmeier. Les libellés « Sapphire Fresnel » et « Sapphire (FR) » restent des alias pour
  qu'un composant enregistré se charge encore.

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
  Il se règle dans la fenêtre STRAT depuis le 2026-10-11, sur demande de 👤 : champ « New test glass at layers: »
  de la carte « Machine model — error sources » (`witness_reset_layers`), vide par défaut, donc un seul verre témoin.

### STRAT — arbitrages délégués par 👤 le 2026-10-04

🔴 Les mesures de cette sous-section (2026-10-04 et 2026-10-05) ont tourné sous D100 : sans biais de fente, sans Rate,
sans recherche de fente. Leurs décisions tiennent jusqu'à leur remesure sous le modèle voulu : le juge de paix et `r75x2` l'ont été les 2026-10-11 et
2026-10-12 (§0), pas ces mesures-là.

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
- **D14, densité de l'historique : 16 points conservés ; la densité relève de la cadence machine (12.4, §6).**
  Sur le balayage grossier, l'historique rejoue 16 points par couche contre 21 par épaisseur nominale pour la couche
  courante ; sur la grille de la machine, `_machine_grid_signal` lit les deux à la même cadence. Porter l'historique
  à 21 points changerait tous les résultats pour une densité aussi arbitraire que 16 (juge standard, 2026-10-04 :
  8 plans sur 370 survivent, plantage moyen au bruit ×2 de 0,0012 à 0,0069).
- **Hystérésis : le seuil suit le niveau de bruit, comme aujourd'hui** (1,66 × le bruit du niveau simulé : 0,5×, 1×,
  2×). Un seul seuil réglé sur le bruit nominal, mesuré sur `r75x2` en `deep` (graine 42, `306559d3`, caches vierges,
  2026-10-05) : aucun des 300 plans communs aux deux runs ne gagne ni ne perd le statut de déposable ; meilleur SEEL
  déposable 0,5566 contre 0,5560 nm, sous le σ ≈ 1,8 % de ce composant. Aucun gain mesuré, donc pas de changement de
  toutes les populations. Le plantage y croît avec le bruit pour 684 stratégies et décroît pour 33 (en août : 61 contre
  532) ; `scripts\probe_plantage_vs_sigma.py` rouvrira la question s'il recommence à décroître. Sorties : `reports/STRAT_bench_r75x2_deep_hysteresis_{noise_level,nominal}_306559d3_2026-10-05.json`.
- **D6, réglages du consensus : vérifiés, aucun écart à corriger.** Chaque mode d'exécution fixe ensemble
  `robustness_num_runs` et `consensus_num_runs` (50, 150, 300, 300 ; mode inconnu → `premium`), et la ligne `[MODE]`
  nomme toute valeur du fichier qu'il remplace. Les graines du consensus viennent de `consensus_seed_list` quand elle
  est renseignée, de `robustness_seed` sinon (`_resolve_consensus_seeds`), et chaque journal les imprime. Pour mesurer
  la dispersion d'un run à l'autre, changer le triplet, pas `robustness_seed` ; le consensus ne réécrit que le score,
  jamais le taux de plantage.
- **D7, ce que `RESULT` agrège : établi dans le code.** `RESULT` est le `robustness_score` de la première stratégie
  classée (`extract_best_rmse`) : le P95 du RMSE des tirages, au pire des trois niveaux de bruit
  (`_test_strategy_robustness_task`), remplacé pour les `consensus_top_k` par la moyenne plus `consensus_std_weight`
  écarts-types de ce même score sur les graines du consensus. **Les tirages plantés comptent dans ce P95** : au-delà
  de 5 % de plantés, il est celui d'un tirage planté (r75x0.5, graine 101, niveau 2×, 25 plantés sur 300 : SEEL
  0,960 nm sur tous les tirages, 0,644 nm sur ceux qui aboutissent,
  `reports/STRAT_r75x0.5_graine101_plan_de_repli_par_bruit_2026-10-12.md`). **La moyenne du consensus ne garde que les
  scores finis** (`_store_and_consume_consensus_score`) : un plan rejeté par la porte de plantage à une graine n'y
  compte pas. Il ne dit rien du reste de la population : comparer deux runs se fait sur le classement
  (`dump_strat_ranking`) ou sur les vidages par stratégie, comme les rapports `STRAT_bench_*` de `reports/`.
- **D9, la plage de blocs ne vide pas la DP : un seuil de faisabilité, dit dans le journal** (R147). Sous un nombre
  minimal de blocs contigus (7 sur le juge de paix standard, entre 9 et 10 sur `r75x2`, 2026-10-05), aucune λ n'est
  admissible dans toutes les couches de chaque bloc : le mineur ne rend que les graines structurées et l'écrit
  (`[MINING] n_blocks=…: the DP found no grouping; the fewest contiguous blocks … is N`). L'héritage depuis le nombre
  de blocs supérieur y ajoute ses stratégies dérivées, et elles comptent (sur `r75x2`, de 5 à 9 blocs, 188 stratégies
  déposables ; la gagnante du juge de paix standard a 4 blocs) : sauter ces nombres de blocs les perdrait. Sorties :
  `reports/STRAT_bench_juge_de_paix_ca99bc8c_D9_*_2026-10-05.*`.
- **D8, intervalles du 99c avec recherche de fente : les verdicts tiennent.** Les quatre intervalles de la
  partition retenue ([0,22), [22,42), [42,76), [76,99)), remesurés comme le fait `scripts\campagne_intervalles.py`
  (`fast`, graine 42, `ca99bc8c`, 2026-10-05), sont déposables avec et sans recherche de fente (plantage minimal 0 %,
  meilleur score déposable à −2,6 %, −0,8 %, 0 % et +1,8 %). Le SEEL assemblé (§2, 0,81 nm sur trois graines) n'est
  pas remesuré. Sorties : `reports/STRAT_99c_intervalles_retenus_fente_{off,on}_ca99bc8c_2026-10-05.json`.
- **Sans changement de code :** D16 (THICKNESS² conserve l'ordre DP),
  D18 (seuils 0,025 et 0,04 appliqués à deux grandeurs), D19 (le
  comptage des points tournants est déjà dans le noyau Phase A), D22
  (effet borné à une couche et Rate simulé en Phase B), D12 (lissage
  causal inactif à `k=1`), D13 (quantification temporelle à reporter
  jusqu'à une mesure réelle). Une mesure contradictoire les rouvrira.

### DESIGN — tranchés par Claude sur l'ordre de 👤, 2026-10-04

Chaque correctif est un commit (R136 `c738a130`, R137 `83661fd4`) qu'un `git revert` annule seul.

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
- **Threads Numba d'une tâche de robustesse STRAT : adaptatif** (`task_numba_threads`) : 4 sur une machine de 16 cœurs logiques ou plus, 2 sinon, jamais au-dessus de la limite de Numba. Sur le juge de paix standard (mode `premium`, caches froids, Ryzen 7 5700G, 16 threads, 2026-10-05), 4 threads prennent 11 à 13 % de moins que 2, populations identiques au bit (chaque tirage des noyaux parallèles écrit sa propre case). Les machines de moins de 16 cœurs gardent 2 faute de mesure.
- **D86 : garder l'avertissement**, ne pas refuser l'extrapolation.

### Arbitrages de 👤 du 2026-10-06

- **Un matériau absent de la base refuse le calcul** (D88), plutôt que de seulement prévenir.
- **Le gel passe sur la couche OpenMP** (D87).
- **D48 : le substrat reste non absorbant**, sans champ d'épaisseur. DESIGN construit ses matériaux, substrat
  compris, par un modèle de Cauchy réel à deux indices (n à 400 et 700 nm, `Material`) et STRAT ne lit que la
  partie réelle de l'indice du substrat : l'épaisseur du substrat n'entre dans aucun de leurs calculs. La lame
  absorbante reste dans la physique (`certus_substrate_absorption`), avec son épaisseur par défaut de 1 mm.
- **Tolérance de C1 pour retirer du code mort d'un noyau : 10⁻¹⁰ en relatif** (D54).

### Réponses de 👤 du 2026-10-06

- **Données Nb2O5 « Syrus » : laissées telles quelles.** Dans les feuilles `Nb2O5-Syrus` et `IR-Syrus-Nb2O5` de
  `example/database_index/indices.xlsx`, n tombe de 2,09 à 4,0 µm à 1,19 à 4,7 µm puis remonte à 1,78 à 5 µm,
  quand les feuilles H400 et H800 restent entre 2,07 et 2,13 ; un creux de cette taille avec k ≤ 0,018 n'est pas
  physique. Un résultat fondé sur ces feuilles au-delà de 4 µm en hérite.
- **Stop pendant l'étage IR d'INDEX : le résultat raffiné est gardé**, comme aujourd'hui ; rien à changer.
- **Le dépôt reste dans Google Drive.** Les fichiers hors git sont archivés à côté des bundles ; l'archive est à
  refaire si ces fichiers changent.
- **Toute fusion dans `master` se redemande à 👤**, sauf la PR de la parité (`parite-zenodo`), qui se fusionne dès que
  sa CI est verte. La protection de `master` est un réglage de sécurité de GitHub, appliqué par 👤 : rien à ajouter
  aux contrôles exigés (ruff, pytest, interface), pas d'épinglage SHA obligatoire (les actions sont épinglées de
  toute façon).
- **Le gel embarque toutes les licences** : `LICENSE`, `THIRD_PARTY_NOTICES.md` et les fichiers de licence de chaque
  distribution embarquée, dans `licenses/`.
- **Un gel local se construit dans un environnement jetable installé depuis `requirements.lock`**, comme celui de la
  CI, et supprimé ensuite : l'exécutable local n'embarque pas ce que porte le Python du poste.
- **Données et logo de 👤** : `BSCNES_*` et le reste de `example/` et `samples/`, la table du silicium sous 1200 nm,
  les préréglages de Cauchy, le logo. `certus_re` (Zenodo) est publié sous CC BY 4.0. Les quatre
  termes de B270i autres que B1 et C1 sont d'origine inconnue.
- **Le RE garde sa pénalité QWOT** : l'a priori MAP de `certus_re` n'est pas porté.

### Arbitrages de 👤 du 2026-10-12

- **D99 n'est pas un défaut** : la lecture d'arrêt est **une lecture brute** (un tirage par couche), pas une moyenne sur 8
  lectures. Le modèle figé reste tel quel ; `fige_arret_lisse` de `scripts/probe_modele_lecture.py` documente l'hypothèse écartée
  (notes plus basses de 8 à 21 %, classement à 0,92).
- **D96 et D97 : activer par défaut** l'ancre exacte et l'inversion exacte de l'arrêt POEM (l'arrêt sans bruit retombe sur POEM
  exact). Les scores STRAT changent : les références mesurées sont à refaire. Actifs par défaut depuis `8d9ced13`.
- **D98 : l'OMS attend sans fin** quand le niveau d'arrêt est plus proche de l'extremum que le seuil d'hystérésis : la couche est
  plantée (pas d'arrêt tardif). Actif par défaut depuis `8d9ced13` (`oms_arming` = 2). Effet mesuré à ce commit sur le juge de paix
  (`premium`, graine 42, `scripts/probe_blocs_vs_plantage.py 48c premium 1 0 2 0 42 0`, une recherche complète par ligne, avant le
  secours Rate et D106) : ancien modèle 669 plans déposables sur 823 (487 optiques purs, meilleur 0,1780 nm) ; D96 et D97 seuls 550
  sur 632, 0,1787 nm ; D98 seul 323 sur 489, 0,1689 nm ; les trois avec l'arrêt tardif 381 sur 1 034, 0,1904 nm ; les trois avec
  l'attente sans fin (la production) 2 sur 1 112, 0,2000 nm. Sur les 120 premiers plans du banc du 2026-10-04
  (`reports/STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json`), notés de nouveau avec 300 tirages (sans biais de fente ni
  Rate, `scripts/probe_modele_lecture.py`) : 120 déposables à l'ancien modèle, 6 à l'attente sans fin, avec ou sans D96 et D97.
  L'attente sans fin retire donc 95 % des plans que l'ancien modèle jugeait fabricables. Au code final (secours Rate, `rate_by_swing`,
  D106 ; mêmes lignes, une exécution chacune), toutes les listes sont déposables et le meilleur SEEL est le même à la dispersion près
  sous les cinq combinaisons (de 0,1759 à 0,1854 nm) ; ce qui change est le nombre de plans optiques purs déposables, 50 à l'ancien
  modèle, 107 avec D96 et D97, 101 avec l'arrêt tardif, 4 avec D98 seul et **0 à l'attente sans fin complète**, et le meilleur plan
  est un plan Rate sous chacune (de 1 à 28 couches au Rate). Rapport : `reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`.
- **D68 (1) : le hub ne lance pas l'échauffement JIT** ; chaque module garde le sien.
- **Rate dans tous les scénarios.** Le Rate est une couche posée **au temps, à la vitesse estimée** sur les couches du même
  matériau contrôlées optiquement (`_rate_layer_thickness`), pas un quartz ni un chrono. 👤 : il doit être intégré à chaque
  design, quel que soit le filtre ; favorisé sur les couches difficiles à contrôler optiquement ; renforcé quand peu de plans
  se terminent ; `r75x0.5` avec un seul verre témoin est le test, et il doit finir par trouver des plans, « quitte à tout
  finir au rate ». Traduit en trois changements : `rate_by_swing` actif par défaut **dans l'application** (elle lisait Faux
  depuis le 2026-08-22, le noyau et le registre disaient Vrai), le **secours Rate** (`rate_rescue`, `rate_rescue_few`, actifs par
  défaut) qui pose en Rate la queue des plans qui plantent, et des enfants d'ELITE et de la recherche locale qui **gardent les
  couches Rate**, la fente et les échanges de verre de leur parent (ils les perdaient : ELITE ne pouvait jamais affiner un plan
  Rate). Mesuré à `r75x0.5` : §7. Le secours sait aussi poser le Rate là où les tirages plantent d'abord, quelques couches de plus
  à chaque tour (`rate_rescue_hard`) : inactif par défaut ; à `r75x0.5` (graine 101) il ajoute 35 plans déposables sur 410 et ne change
  pas le meilleur SEEL (§7). **L'optique reprend après du Rate** : le noyau le permet (une couche optique est arrêtée sur son propre
  signal, quelle que soit la façon dont les précédentes ont été posées ; `tests/unit/test_strat_optics_after_rate.py`) et 👤 observe en
  salle de bonnes stratégies en paquets (optique à un λ, Rate, optique à un autre λ), ce qui reste empirique. La recherche ne le
  proposait presque pas : les plans déposables du 2026-10-12 avec de l'optique après du Rate ont exactement deux paquets de Rate, une
  couche puis la queue, et ELITE rendait à ses enfants les couches Rate du parent sans les changer. ELITE sait maintenant les déplacer
  (`elite_rate_moves`, `elite_rate_max_candidates`) : étendre ou raccourcir un paquet, fermer un trou, ouvrir une fenêtre d'optique
  dans une queue, poser un paquet de Rate dans l'optique. Actif par défaut depuis `978b8f04`, après mesure (§7).

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

**Ils faussent un résultat, trompent l'utilisateur ou empêchent de calculer, et le modèle physique — connus, non corrigés**

Aucun. D96 à D98 (le modèle d'arrêt) sont décidés et actifs depuis le 2026-10-12 : §3.

**Le code, les tests et la documentation**

| # | défaut |
|---|---|
| D11 | **Une fenêtre de module fermée n'est pas détruite** : des lambdas et des `functools.partial` branchés sur les signaux de ses propres widgets la capturent, et la connexion les tient du côté C++ de PyQt, où le ramasse-miettes ne voit pas le cycle (`scripts/sonde_retenants_fenetre.py`, 2026-09-27 : `CertusREApp` retenue par quatre méthodes liées, cinq fermetures et deux attributs de `CertusToast` / `CertusToastStack`). **Sans effet en production** : le hub lance chaque module dans son propre processus (`QProcess`), et fermer la fenêtre finit le processus. Les tests détruisent désormais leurs fenêtres (R5). Coûterait dans tout processus qui construirait plusieurs fenêtres. Piste : `WA_DeleteOnClose` sur `CertusBaseApp`, à condition de retenir d'abord ses `QThread` encore actifs : sans cela, libérer la fenêtre libère un thread en cours (D23) |
| D23 | À instruire : six `gc.collect()` exécutés dans les threads de calcul STRAT (deux dans `_parallel_block_worker`, un dans `_run_segment`, un dans `_execute_nucleation_and_cost_mapping`, deux dans l'exécuteur du pipeline) peuvent libérer des objets Qt hors du thread GUI, sans arrêt observé ; les tests n'isolent pas `sys.modules`. L'arrêt pendant l'étage IR d'INDEX garde le résultat raffiné, décidé par 👤 (§3). Reproduire avant de changer le cycle de vie ; traiter avec D11 |
| D25 | Dette de lint masquée par `extend-ignore` : **8 règles**, E501 compris, et 1 416 violations à la mesure du plan (`scripts\metrics.py`, 2026-10-12, E501 exclue : F401 659, E402 555, RUF001 77, RUF003 59, RUF002 51, RUF100 10, RUF022 3, F811 2, ce dernier écarté des tests par `per-file-ignores`) ; plus aucun import étoile, et les noms indéfinis (F821, F822) sont à zéro. Le cliquet `tests/oracle/test_lint_debt_ratchet.py` nomme les règles restantes : aucune ne peut entrer, et une règle sortie doit quitter sa liste. RUF022 (trier `__all__`) reste ignorée à dessein |
| D26 | Imports montants entre couches, mesurés le 2026-10-06 (`scripts\metrics.py`) : 20 arêtes, `certus.spline → certus.ui` (8), `certus.metal → certus.ui` (6), `certus.utils → certus.ui` (3), `certus.utils → certus.spline` (3) ; un cycle d'imports à l'exécution (le cœur de STRAT) ; `certus.physics.gradient_analytic` ne s'importe pas seul (cycle avec `gradient_utils`) |
| D50 | Gelé, `loky` ne marche pas (repli sur des fils) et le multigraine reste refusé, le message le dit. La couche Numba du gel est D87, sa taille D72. Le job `release-windows` l'a construit et démarré sur un poste neuf le 2026-09-30 (R42) |
| D68 | **La physique lit le silicium (`SI_*`, feuille `Si-substrate` de `indices.xlsx`) À L'IMPORT**, par pandas et openpyxl (mesuré sur la fenêtre DESIGN, machine chargée : 0,53 s pour `materials_data`, dont 0,42 s d'import d'openpyxl) ; les rendre paresseux demande que les tableaux existent avant la première compilation de `get_nk_si` (numba les fige), donc toucher le chargement de la physique. (L'échauffement JIT du hub est tranché : il ne le lance pas, §3.) |
| D69 | Une définition d'indicateur a changé en route, et 👤 doit le savoir. « Couverture des noyaux, compilation coupée » : le plan la mesurait par `oracle` + `core` (base 45,9 %, cible ≥ 70 %) ; elle se mesure maintenant par ces deux répertoires, `property` et les tests de `unit` marqués `kernels` (R78 : 74,0 %). La base de l'audit reste celle de l'ancienne définition ; avec l'ancienne, l'indicateur serait à 46,0 % le 2026-10-01 (non atteint). Je tiens la nouvelle pour la bonne (les tests des noyaux de STRAT ont été écrits pour cela), mais c'est un changement de critère. |
| D71 | **Tauc-Lorentz-Urbach n'est pas continu en E = Eg** (`certus_optical_models.py`, `gradient_analytic.py`). ε₂ saute là : la queue d'Urbach, utilisée pour E ≤ Eg, vaut 1,9e-4 pour l'oxyde de l'exemple, l'absorption de bande (E > Eg) vaut 0 et monte jusqu'à l'ancre de la queue, posée à Eg + 0,01 eV ; le saut est de 2e-5 du maximum, sans effet sur un empilement, mais le modèle n'est pas continu là pour un ajustement qui passerait au bord du gap. Le raccorder change le modèle des références certifiées (leurs paramètres ont été ajustés sur lui) : à trancher avant de le toucher. (La première observation, k par différence qui s'annule sous ε₂ ≈ 1e-7, est corrigée : `extinction_from_epsilon`, k = ε₂/(2n).) |
| D72 | **Taille du gel (S7.2) : objectif ≤ 300 Mo non atteint.** 411 Mo le 2026-10-06 (442 avant `5ccaa210`, qui laisse dehors les outils de développement). Le reste : llvmlite 115 Mo (Numba, indispensable), Qt 77 Mo (dont le rendu OpenGL logiciel), scipy 68 Mo avec ses bibliothèques, numpy 28, matplotlib 15, Pillow 13, pandas 13, lxml 7, OpenSSL 8. Étape suivante : mesurer ce que l'application charge vraiment (sous-modules de scipy, plugins Qt, ssl, lxml) avant d'autres exclusions. Un gel local embarque ce que porte l'interpréteur qui le construit : celui du 2026-10-06 contient aussi lxml, psutil, pywin32, PyYAML, certifi, charset_normalizer, MarkupSafe et cffi, absents de `requirements.lock`, d'où part le gel de la CI. Le spec embarque tout `example/`, base de dépôts comprise (11 Mo sur disque, 2026-10-11) |
| D82 | **Thème sombre : logo et mesure de contraste à terminer.** Les textes et états vides suivent désormais le thème (R102). Le logo foncé reste peu visible en thème sombre, constat visuel sans mesure ; le harnais ne résout pas encore une encre de palette sur fond hérité. |
| D84 | **Validation locale intermittente.** Des écarts au dernier bit sur des tests STRAT apparaissent au premier passage après un changement de clé du cache Numba, puis disparaissent à la relance (deux fois le 2026-10-03 ; le 2026-10-06, `test_neutral_parameters_are_bit_identical_to_the_legacy_call` dans la validation de `29240ee7`, après la modification de `certus_colorimetry.py` : rouge à froid, vert à la relance, 0 ulp mesuré entre les deux appels du noyau). Signature compatible avec D52 : compilation sur place contre lecture du cache, cause non prouvée. Si l'écart persiste à la relance, comparer les noyaux froids et chauds avant de modifier le calcul. |

## 5. Ce qui attend une décision de 👤

Ces sujets demandent un jugement de physicien ou de propriétaire du produit. Les choix déjà faits figurent en section 3.

| sujet | ce qui est en jeu |
|---|---|
| **avis de tiers** | une ligne reste « à confirmer par toi » dans `THIRD_PARTY_NOTICES.md` : les DLL du runtime Visual C++ (`VCRUNTIME140*.dll`, `VCOMP140.DLL`) se redistribuent avec un programme, mais Microsoft réserve ce droit aux utilisateurs de Visual Studio sous licence |
| **paquet `certus_re`** | la correction de la citation du saphir (Malitson et Dodge, 1972) attend d'être commitée par 👤 dans ce dépôt-là, qui contient ses modifications en cours, puis publiée avec la prochaine version Zenodo |
| **interface** | Revoir visuellement les onze fenêtres et choisir les teintes de marque, la bande des fichiers récents et les bornes des champs numériques. |
| **base de dépôts** | RE : remplacer la seule mesure d'un classeur RE déjà chargé par celle d'un dépôt (il faudrait découper `load_reverse_engineering_from_path`) ? Apparier dans la base la T et la R d'un même échantillon que l'opérateur a nommées différemment (`NbT3` et `NbR3`) ? INDEX : en phase 2, la fenêtre λ de l'utilisateur est remplacée par toute l'étendue des données (`_on_tlu_constrained_finished`), est-ce voulu ? |
| **ELITE « tour à tour »** | `elite_round_robin`, six graines, D100 et D103 corrigés, avant D106 (2026-10-12) : mieux à la graine 42 (0,5420 contre 0,6354 nm), équivalent à la 404, moins bien aux 77, 101 et 505 (de +0,7 à +2,8 %), la 303 sans déposable des deux côtés ; médiane +0,7 %. L'option est inactive et le reste tant que 👤 ne dit pas de l'armer ; ce qui manque pour trancher est le bruit d'une même graine rejouée |
| **arrêt de STRAT** | D96 à D98 sont le modèle par défaut (§3). L'attente sans fin de D98 retire 95 % des plans que l'ancien modèle jugeait fabricables (§3) ; ce que l'OMS fait à un niveau franchi avant que son contrôleur soit armé n'est pas connu. À secours Rate égal (juge de paix, code final), l'arrêt tardif rend un meilleur SEEL du même ordre (0,1792 contre 0,1849 nm) et garde 101 plans optiques purs déposables, que l'attente sans fin ne garde pas : avec elle le Rate est une nécessité pour ce composant, avec l'arrêt tardif une option. À confirmer, ou à remplacer. Reste aussi : noter ou non au modèle figé, au moins pour départager la tête du classement (rapport du 2026-10-10, sections 4 et 6) |
| **le Rate et l'optique pure** | Au juge de paix (code final), le meilleur plan porte du Rate sous les cinq modèles d'arrêt (de 1 à 28 couches) et le meilleur plan optique pur est de 4 à 37 % moins bon ; les plans optiques purs déposables sont 50 à l'ancien modèle, contre 487 avant le secours Rate (mesure d'avant D106). Le modèle de Rate de STRAT n'a ni dérive de la source ni bruit propre de la vitesse (§7), ce qui le favorise, et ELITE refine maintenant des parents Rate (et déplace leurs couches Rate : §3) : l'hypothèse, non mesurée, est que la lignée optique pure y perd des tours. Faut-il réserver à ELITE des parents optiques purs, ou ne laisser le Rate que là où l'optique ne suffit pas ? La réponse dépend de la stabilité réelle de la vitesse (A25, §6) |

## 6. Chantiers spécifiés, en attente

**Saphir** — INDEX traite le saphir comme transparent (k = 0) : son absorption au-delà de 3,9 µm (α de 0,05 cm⁻¹ à 4 µm à 1,1 cm⁻¹ à
5,2 µm, lue sur le saphir nu de la séance 24-03) n'est pas modélisée, ce qui biaise les films mesurés au MWIR ; à brancher comme
nouveau paramètre inactif par défaut (C1) · mesurer la polarisation du faisceau du spectrophotomètre : elle domine l'incertitude
du niveau (0,025 d'indice par unité de fraction p).

**Calcul** (détail : `git show 7b08dc8:docs/archives/REPRENDRE_ICI.md`) —
dimensionner K, le nombre de graines à lancer : à refaire au code final (`r75x2`, avec D106 corrigé : deux graines sur deux trouvent des
déposables avec le secours Rate, aucune sans ; avant D106, 6/7 puis 3/7 en août) · balayer `tp_hysteresis_factor` à bruit fixé sur la grille machine : sur la grille
grossière, il est presque inerte (juge de paix, 370 plans, 2026-10-11 : de 1,0 à 2,0 A, 358 à 362 notes identiques au
bit à celles de 1,66 A, même meilleur plan ; rapport de l'audit du 2026-10-10, section 4) · compter le criblage et
l'héritage quand un étage deviendra suspect · porter le résultat de `r75x2` dans la vitrine,
avec sa condition dans la même phrase que le chiffre · accélérer à résultat identique au bit : aucune piste ouverte
(les 17 % d'« attente du consommateur de statistiques » d'un profil par échantillonnage sont un artefact de
l'échantillonneur de `scripts/bench_examples.py`, `scripts/probe_sampler_idle_thread.py`, 2026-10-11 ; mémoriser
`build_M_before_cache` ne fait rien gagner, populations identiques au bit, 2026-10-06) · mesurer `elite_rate_moves` (actif) sur
d'autres composants (×1,5, ×1,75, 35 et 99 couches), d'autres graines (une seule au juge de paix, deux à `r75x2`) et avec plus de tours d'ELITE.

**Modèle physique** (détail : `git show 7b08dc8:docs/archives/TRAVAUX_A_VENIR.md`) :

| | sujet | état |
|---|---|---|
| 12.2 | modéliser le lissage de lecture | fait sur la grille machine : lecture du T exact à chaque pas, lissage sur 8 lectures au seuil de 1,00 A ; D54, D55, D93, D94 et D95 sont corrigés et ce chemin reproduit une machine indépendante rejouée lecture par lecture (rapport du 2026-10-10, section 2) — surtout ne pas remonter le seuil |
| 12.3 | méconnaissance d'indice | spécifié : corridor de dispersion |
| 12.4 | grille d'échantillonnage à la cadence machine | fait : voir 12.2 ; inactive par défaut (§3) |
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
E402 et les petites règles (RUF001 à RUF003, RUF022, RUF100), un cas à la fois.

| règle | ce qui peut changer un comportement | démarche proposée |
|---|---|---|
| F401 | un import « inutilisé » peut être un ré-export (y compris dans un import sur plusieurs lignes, ou un nom déclaré par `__all__.extend`), un effet de bord (enregistrement, sous-module `import a.b`, configuration numba avant un `@njit`), ou servi par une façade `CertusFacadeModule` | **fait** par lots (R9) : un nom ne part que si l'import est au niveau du module, hors `try`, sans accès dynamique du module à ses globales, et si aucun fichier suivi, aucune façade, aucun test qui charge le fichier par son chemin ni aucun code lancé depuis une chaîne ne le prend ; le reste est listé, pas retiré |
| E402 | l'ordre des imports compte : cycle `physics ↔ core`, `configure_numba_env()` avant tout `@njit`, `QT_QPA_PLATFORM` avant la première `QApplication` | réordonner seulement les fichiers sans import à effet, jamais les façades ni `certus_core` ; E402 cas par cas |

**Contrôles du chantier lint** : ruff ; oracle ; unit ; `tests/ui/` ; le reste de `tests/` ; trois
photos avant/après — l'espace de noms final de chaque module touché (`scripts/lint_ns_snapshot.py`),
les modules que charge chaque script d'entrée une fois son fil de préchauffage fini, et les noms
que sert chaque façade `CertusFacadeModule`. Un nom qui disparaît ne doit être ni utilisé ni
demandé par personne.
**Ordre** : E402, puis les petites règles.

**Prédictibilité** (détail : `git show 7b08dc8:docs/archives/CHANTIER_PREDICTIBILITE.md`) —
prédire sans tout calculer si un design passe avec un seul verre témoin ; quatre routes déjà
fermées par la mesure.

## 7. Les composants d'essai

| composant | fichier (`example/example_strat/`, sauf mention) | couches | notation | rôle |
|---|---|---|---|---|
| dichroïque | `JSON-strat-example.json` | 48 | 400-700 nm | le juge de paix : passe-court, front vers 545 nm |
| passe-bande 3 cavités | `JSON-strat-bandpass-3cav.json` | 35 | 600-660 nm | une résonance, une bande étroite |
| aléatoire | `JSON-strat-random75.json` | 75 | 550-750 nm | ni cavité, ni miroir, ni périodicité : teste si une règle est **générale** |
| passe-bande 5 cavités | `JSON-strat-bandpass-5cav-99c.json` | 99 | 610-655 nm | le cas dur |
| aléatoire ×0,5 | `reports/serie_echelle_r75/cfg_x0.5.json` (`r75x0.5` des sondes) | 75 | 550-750 nm | le côté mince de la série d'échelle ; fabricable avec un seul verre témoin grâce au secours Rate (ci-dessous) |
| aléatoire ×2 | `JSON-strat-random75-x2-fabricable.json` (fente 1 nm) ; `JSON-strat-random75-x2-fabricable-2nm.json` (fente 2 nm, rampes injectées de `rampes_r75x2-2nm.json`) | 75 | 550-750 nm | l'étalon depuis le 2026-08-20 : épaisseurs doublées |

Une règle n'est acquise que si elle survit sur un empilement **sans structure**.

**La série d'échelle de l'aléatoire** (`reports/serie_echelle_r75/`, 2026-08-15) : même empilement, mêmes matériaux
(H800-Nb2O5 sur H800-SiO2, substrat SiO2, λ₀ 633 nm), seule l'épaisseur est multipliée ; c'est la seule expérience
contrôlée du projet. Somme des QWOT (QWOT par couche ; couches sous 1 QWOT) : ×0,5 57,4 (0,25-1,24 ; 59) · ×1 114,9
(0,50-2,48 ; 11) · ×1,5 172,3 (0,76-3,72 ; 3) · ×1,75 201,1 (0,88-4,34 ; 2) · ×2 229,8 (1,01-4,96 ; 0). Optique et
mécanique y sont proportionnelles : une conclusion en micromètres ne se généraliserait pas à d'autres matériaux.

**×0,5 avec un seul verre témoin, avant le secours Rate** (2026-10-11, `782972bf`, D100 corrigé, `deep`, fente 2 nm,
`reports/blocs_vs_plantage_r75x0.5_deep_s{042,101,202}.json`) : aucun déposable aux graines 42, 101 et 202 (0 sur
2 895, 2 897 et 2 895 stratégies), plantage minimal 69,0 %, 8,3 % et 62,3 % (août : 68,7 % pour la graine 42 avec le
profil élargi, 70,0 % et 67,0 %), et la cause de plantage dominante est « niveau d'arrêt hors d'atteinte » pour toutes
les stratégies des trois graines. D103 ne la touche pas (aucun identifiant en double dans les trois journaux). Quand
rien ne passe, le repli garde le plan au plantage le plus bas : celui de la graine 101, qui plante dans
1,7 / 1,7 / 8,3 % des tirages aux bruits 0,5× / 1× / 2×, seul le 2× dépassant 5 % ; 5 blocs aux λ de contrôle 636,
686, 737, 747 et 734 nm, variante `RATE_L31`. Son SEEL affiché est 0,673 nm (score de consensus, D7). Rejoué niveau
par niveau (`reports/STRAT_r75x0.5_graine101_plan_de_repli_par_bruit_2026-10-12.md`) : 0,655 / 0,660 / 0,960 nm sur
tous les tirages, **0,633 / 0,636 / 0,644 nm sur les tirages qui aboutissent**.

**×0,5 avec un seul verre témoin, avec le secours Rate** (2026-10-12, `40642146`, `deep`, fente 2 nm,
`reports/STRAT_secours_rate_2026-10-12/`, `reports/STRAT_r75x0.5_secours_rate_2026-10-12.md`) : tous les plans de la liste finale
sont déposables aux trois graines (3 383, 3 701 et 3 279 plans), aucun n'est un plan optique pur, plantage maximal de 2,67 %,
4,67 % et 2,00 %. Meilleur SEEL 0,5031 / 0,4981 / 0,5000 nm (graines 42 / 101 / 202), 12 blocs, 0 % de plantage aux trois bruits,
Rate des couches 18 à 75 (indices 17 à 74). Les queues Rate seules (`21d1b1c3`, graine 101, avant l'héritage d'ELITE) donnaient
0,555 nm (coupure à l'indice 16 : 522 plans sur 547 se terminent) et 0,563 nm (coupure 14 : 2 272 plans sur 2 272) ; des
ensembles fixes de couches critiques (indices 22, 25, 28, puis 46, 51, 62, 69, 72) n'en rendent aucun (0 sur 4 614, plantage
minimal de 52 % pour les ensembles) : les couches qui cèdent se déplacent quand les précédentes passent au Rate. **Le modèle de
Rate de STRAT** (`certus_strat_growth.py`, « RATE MODE ») fige l'estimation de la vitesse à l'entrée de la queue : toutes ses
couches héritent de la même erreur relative, corrélée, et la source ne dérive pas pendant le dépôt (non modélisé, non mesuré) :
ces SEEL sont ceux de ce modèle. Le Rate posé aux seules couches où les tirages plantent d'abord (`rate_rescue_hard`, inactif par
défaut) ajoute 35 plans déposables sur 410 essayés et laisse le meilleur SEEL à 0,4981 nm (graine 101, `dbf8025f`). **Avec ELITE qui déplace
les couches Rate** (`reports/STRAT_ELITE_couches_Rate_2026-10-12/`) : **0,4347 / 0,3967 / 0,3967 nm** aux graines 42 / 101 / 202 (`5da02db9`, `cea0db66`,
`5da02db9`), toutes les listes déposables ; le meilleur plan des graines 101 et 202, le même, alterne optique (couches 1 à 6), Rate 7 à 10, optique 11 et 12
(λ 451 nm), Rate 13 à 34, optique 35 et 36, Rate 37 à 75. Le cas à plusieurs
verres témoins n'est pas mesuré.
