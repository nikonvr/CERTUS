# CERTUS — actions à lancer et protocole de mesure

> Extrait de la section 0 de [`ETAT.md`](ETAT.md) le 2026-10-18, pour que la reprise tienne en peu de lignes. Ce contenu **fait autorité** ;
> `ETAT.md` n'en garde qu'un renvoi. **Un fait, un seul endroit** : corrige ici, ne recopie pas ailleurs, mets un lien.
> Les `§N` nus sont les sections de `ETAT.md`. Le vocabulaire (Rate, déposable, SEEL) et les acquis sont dans [`ETAT_acquis.md`](ETAT_acquis.md).

**Prochaines actions — à lancer avec une autre IA.** Lire dans l'ordre : [`CLAUDE.md`](../CLAUDE.md) (les règles et les onze interdits), la section 0 de [`ETAT.md`](ETAT.md), puis l'action choisie. Chaque action est
**autonome** : pourquoi, quoi lancer (commandes exactes), quand elle est finie, ce qu'il ne faut pas faire. Les actions sont indépendantes les unes des autres, par priorité décroissante.
Une action peut donner plusieurs commits, chacun d'une seule chose (C3). **Jamais de `git push` ni de fusion de PR sans l'ordre de 👤.**

**À qui confier l'action** (👤, 2026-10-21) : **[Gemini]** exécution d'un protocole écrit, les garde-fous (tests, cliquets, `c1_diff`, validation) attrapent l'erreur ; **[ChatGPT]** code ou campagne bien spécifiés ; **[Claude]** ce qui demande de l'intelligence : conception, piège de reproductibilité, interprétation. Toute branche est relue avant fusion (référence §12).

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

**A3 — [Claude] Refaire les repères d'avant D106 et d'avant D96-D98** (§2 ; ≈ 6 h). *Pourquoi* : ces nombres datent d'avant D106 (qui coûte 8 % au juge de paix et retire tous les déposables optiques de `r75x2`)
et d'avant le secours Rate : leur population n'est plus celle de la production. *Faire* : le juge de paix au banc officiel, aux défauts : `python scripts\bench_examples.py strat
--auto-yes --out reports\STRAT_bench_juge_de_paix_<commit>_defauts_<date>.txt` (33 min ; `RESULT` et `STRAT_RANK00..09` sont les chiffres à reporter) ;
puis, avec la variable `CERTUS_DESIGN_JSON` pointant le fichier de `example/example_strat/` (`set CERTUS_DESIGN_JSON=example\example_strat\JSON-strat-bandpass-3cav-deep.json`,
à changer à chaque composant) la même commande pour le passe-bande de 35 couches (`JSON-strat-bandpass-3cav-deep.json`), l'aléatoire de 75 couches (`JSON-strat-random75.json`),
`r75x2` à fente native (`JSON-strat-random75-x2-fabricable.json`) et la configuration livrée avec rampes (`JSON-strat-random75-x2-fabricable-2nm.json`) ;
le passe-bande de 99 couches à verres témoins multiples se refait par intervalles (`python scripts\campagne_intervalles.py --etat` puis ses vagues : lire sa
docstring, c'est long). *Fini quand* : chaque ligne concernée de la table du §2 porte le nombre refait, sa condition (commit, mode, graine) et son
rapport ; les anciens nombres sont retirés (un fait, un seul endroit). *Ne pas* : modifier `example/example_strat/JSON-strat-example.json` (interdit 4).

**A4 — [ChatGPT] Le Rate évince-t-il l'optique pure ?** (conception 2 h, mesure 2 h). *Pourquoi* : au juge de paix, les plans optiques purs déposables sont passés de
487 à 50 (ancien modèle d'arrêt), le meilleur plan optique pur de 0,178 à 0,193 nm ; l'hypothèse, non mesurée, est qu'ELITE, dont les parents sont
maintenant en majorité des plans Rate, raffine moins la lignée optique pure (`reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`, mesure 4). *Faire* : un
levier `elite_optical_parents` (entier, `0` = le chemin d'avant, **bit pour bit** : le prouver comme `tests/unit/test_strat_elite_rate_moves.py` le fait
pour `rate_moves=False`) qui garantit, parmi les parents d'ELITE, au moins M plans sans aucune couche Rate quand la liste en contient ; le mesurer au
juge de paix (graine 42) avec M = 0, 2, 4, puis à `r75x0.5` (graine 101). *Fini quand* : pour chaque M, le meilleur SEEL optique pur, le meilleur SEEL
global et le nombre de plans optiques purs déposables, dans un rapport. **Le contrat de taille** : `certus/core/certus_strat_consensus.py` est à 1 498
lignes (plafond 1 500) et `_apply_elite_refinement_if_enabled` à 299 (plafond 300) : ne rien y ajouter qui ne soit pas compensé, mettre la logique dans
`certus/core/certus_strat_robustness_rate.py` comme `_elite_rate_candidates`. *Ne pas* : l'armer par défaut (c'est à 👤).

**A5 — [Gemini] ELITE : plus de tours, autre budget pour les mouvements sur les couches Rate** (≈ 4 h). *Pourquoi* : ELITE fait 3 tours en `deep` et s'arrête
quand rien ne progresse ; la recherche des paquets est une escalade qui n'a peut-être pas fini. *Faire* (`r75x0.5`, graine 101, référence : 0,3967 nm) :
`elite_rounds=6,elite_stop_on_no_gain=false`, puis `elite_rounds=10,elite_stop_on_no_gain=false` ; puis, à 3 tours, `elite_rate_max_candidates=40` et
`elite_rate_max_candidates=360`. Une surcharge à la fois, avec son étiquette. *Fini quand* : un tableau tours et budget → meilleur SEEL, durée, nombre de
paquets de Rate du meilleur plan. Si les largeurs de fenêtre (`ELITE_RATE_WINDOWS`) ou le pas (`ELITE_RATE_STEP`) méritent un balayage, en faire des
paramètres **inactifs par défaut** (chemin d'avant identique) avant de les mesurer. *Ne pas* : changer un défaut sans 👤.

**A6 — [Claude] Le modèle de Rate sans dérive de la source** (le sujet scientifique central ; **ne pas commencer sans la valeur de 👤**). *Pourquoi* : tous les SEEL
des plans Rate supposent une vitesse constante pendant le dépôt (`certus/physics/certus_strat_growth.py`, « RATE MODE ») ; 👤 observe en salle ±1 à 2 %
(§6, A25) et de bons plans en paquets alternés. Le modèle ne peut ni confirmer ni infirmer ce qui vient de la salle. *Faire* : (1) **demander à 👤** la
dérive ou l'instabilité de la vitesse pendant un dépôt (relative, par couche ou par run, et comment elle a été observée) ; ne pas l'inventer ; (2) ajouter un
paramètre **inactif par défaut** qui perturbe l'épaisseur des couches Rate (tirage fonction pure de la graine, du tirage et de l'indice physique,
`_seeded_noise_sample` de `certus/physics/certus_strat_math.py`, jamais de la stratégie : C2), sur le modèle de `stop_model_flags`
(`certus/physics/certus_strat_readings.py`) et de `tests/unit/test_strat_stop_model_is_the_decided_one.py` ; `python scripts\c1_diff.py HEAD` doit rendre « C1 TENU »
avant de committer ; (3) refaire `r75x0.5` (graine 101), le juge de paix et `r75x2` (graine 101) avec la dérive de 👤 divisée par 3, telle quelle et multipliée par 3,
et comparer la forme du meilleur plan (queue, paquets alternés, optique pur). *Fini quand* : le tableau, le rapport, le §6 mis à jour. *Ne pas* : activer par
défaut ; conclure sur une seule graine.

**A8 — [Gemini] Dette technique** (§4 et §6) : un défaut par tâche, un commit par changement, jamais `ruff check --fix`, jamais agrandir `extend-ignore`.
- *D25, lint* : mesure officielle `python -m ruff check . --isolated --select "E,F,I,B,UP,RUF,PT,PERF" --ignore E501 --line-length 120 --target-version py314 --statistics`
  (1 416 violations le 2026-10-12 : F401 659, E402 555, RUF001 77, RUF003 59, RUF002 51, RUF100 10, RUF022 3, F811 2). Une règle ne quitte `extend-ignore`
  qu'à zéro violation, dans le commit qui met à jour la liste de `tests/oracle/test_lint_debt_ratchet.py`. Commencer par E402, module par module, avec les trois
  photos avant/après du §6 (`scripts/lint_ns_snapshot.py`). RUF001 touche des chaînes dont des libellés vus de l'utilisateur : ne pas les réécrire sans 👤.
- *D26, imports montants* : 20 arêtes (§4) ; commencer par celles qui ne demandent qu'un symbole à descendre dans `certus/domain/` ou `certus/core/` ; après chaque
  dette payée, `python scripts\metrics.py --dette tests\architecture_debt.json` réécrit le registre depuis les sources (il ne fait que rétrécir) ; **ne jamais le lancer
  pour faire passer `tests/unit/test_the_architecture_debt_only_shrinks.py`** : il y inscrirait la régression au lieu de la signaler.
- *D23 puis D11, D50, D72* : reproduire D23 avant tout (`scripts/sonde_retenants_fenetre.py`) ; ne pas toucher `WA_DeleteOnClose` avant (§4). D72 (taille du gel) après la
  fiabilité du gel.
- *D82* (logo du thème sombre) demande des yeux ; *D84* (écart au dernier bit au premier passage après un changement de clé du cache Numba) : relancer une fois avant de
  conclure à une régression ; *D68* (silicium lu à l'import) est optionnel.

**A9 — [ChatGPT] Tenter le99c en une seule campagne avec injection et derniers raffinements Rate** (demande de 👤 du2026-10-16 ; à préparer, non exécuté).
*Objectif* : chercher un plan déposable pour le passe-bande5cavités/99couches, en injectant des couches
ou paquets Rate et en appliquant les derniers raffinements intégrés : recherche conjointe fenêtres/λ
(`elite_rate_joint_candidates=480`) et post-raffinement final (`rate_post_refinement=True`, faisceau2,
au plus2passes/300propositions par passe/600au total, arrêt sans gain). Les parents doivent provenir
de la recherche native propre au99c ; aucun gagnant historique75c injecté.
*Faire* : préparer un protocole borné distinct, avec sources et paramètres physiques figés, puis
comparer l'optique pure, l'injection de Rate sans ce post-raffinement, et le Rate avec les derniers
raffinements. Garder les mêmes réglages dans chaque comparaison appariée et distinguer le gain
de l'injection de celui du raffinement. Vérifier le raccordement réel au99c et aux99couches avant
mesure ; utiliser de nouveaux slots et réserver les graines de confirmation avant inspection.
*Fini quand* : un rapport donne, sur plusieurs graines, le nombre de plans déposables, les plantages,
les SEEL de consensus homogènes des plans complets figés, leur confirmation indépendante et le coût réel.
L'absence de plan déposable reste un échec explicite, sans SEEL valide. Le résultat historique à4verres
témoins est un repère séparé, pas un succès en une seule campagne. Conserver plans, rejets, sources/SHA
et paramètres ; aucun défaut activé ni ancienne campagne relancée par cette tâche.
*État au 2026-10-18.* Protocole préparé dans `reports/STRAT_99c_A9_protocole_2026-10-17/` (chaîne `chain_A9.sh`, graines fraîches réservées avant toute mesure, SHA-256 de 428 sources) ;
`chain_A9.sh` ne lance rien sans le GO écrit de 👤 (`GO_OWNER.txt`) et n'a jamais été lancé ; le `protocole_A9.md` qu'il cite n'est pas dans le dossier.

**A10 — [Gemini] Chercher à ±0,010 ou à ±0,005 : trancher par le calcul** (demande de 👤 du 2026-10-20 ; ≈ 4 h). *Pourquoi* : l'étage
`strat_local_search` cherche à ±0,010 d'incertitude d'indice (`SEARCH_INDEX_CORRIDOR`, `certus/core/certus_strat_local_search.py`),
sur une règle écrite d'avance qui a préféré ±0,010 sur 2 designs de 3 (`reports/STRAT_r75_leviers_bonne_mere_2026-10-20/bilan.md`,
section 7 : arrêts à ±0,010 de 175 à 0 sur 75c, coût à ±0,005 de +1,0 %, −3,5 % et +11,4 %). Une graine, trois designs : ce
n'est pas tranché. *Faire* : sur 75c, r75x0.5, r75x2 et le juge de paix, graines de banc 77, 101 et 202, banc deep avec l'étage
cherchant à ±0,010 puis à ±0,005 (constante surchargée), et un troisième essai jugé au pire des deux amplitudes ; juger les plans
finaux à ±0,005 et ±0,010 sur graines neuves, même règle (gain à ±0,010 au-delà de deux erreurs types, coût à ±0,005 ≤ 2 %,
aucun arrêt ajouté). *Fini quand* : un rapport dans `reports/` donne le choix par design et un défaut proposé à 👤. *Ne pas* :
changer `index_corridor` de la configuration (la notation reste à ±0,005) ni le défaut sans l'accord de 👤.
