# CERTUS — actions à lancer et protocole de mesure

> Extrait de la section 0 de [`ETAT.md`](ETAT.md) le 2026-10-18, pour que la reprise tienne en peu de lignes. Ce contenu **fait autorité** ;
> `ETAT.md` n'en garde qu'un renvoi. **Un fait, un seul endroit** : corrige ici, ne recopie pas ailleurs, mets un lien.
> Les `§N` nus sont les sections de `ETAT.md`. Le vocabulaire (Rate, déposable, SEEL) et les acquis sont dans [`ETAT_acquis.md`](ETAT_acquis.md).

**Prochaines actions — à lancer avec une autre IA.** Lire dans l'ordre : [`CLAUDE.md`](../CLAUDE.md) (les règles et les onze interdits), la section 0 de [`ETAT.md`](ETAT.md), puis l'action choisie. Chaque action est
**autonome** : pourquoi, quoi lancer (commandes exactes), quand elle est finie, ce qu'il ne faut pas faire. Les actions sont indépendantes les unes des autres, par priorité décroissante.
Une action peut donner plusieurs commits, chacun d'une seule chose (C3). **Jamais de `git push` ni de fusion de PR sans l'ordre de 👤.**

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

*Faits tirés de A1 et A2, terminées.* A1 (CI de la PR #9, contrôlée le 2026-10-13 sur la tête `bee0d3c5`) : tout vert sauf le contrôle des alertes CodeQL (SHA1 dans le suffixe de
`scripts/probe_blocs_vs_plantage.py`, faux positif probable) ; SHA256 l'a remplacé ; l'alerte distante n'a pas été rejouée. A2 : voir « Acquis du Rate » dans `ETAT_acquis.md`.

**A3 — Repères refaits en partie (21 octobre 2026), 99 couches encore ouvert.** Six bancs officiels aux paramètres livrés, code `85a9e82f`, graine 42 :
juge de paix, random75 fast, vrai 35 deep, livré 36 deep, `r75x2` natif 1 nm et rampes 2 nm. Résultats, dix rangs et preuves dans
[`STRAT_A3_reperes_reprise_2026-10-21`](../reports/STRAT_A3_reperes_reprise_2026-10-21/bilan.md), table §2 actualisée.
Les douze intervalles de la partition historique 99 couches ont terminé, mais les scores assemblés ont été écartés : croissance et notation
n'utilisent ni le même indice de bruit ni les mêmes domaines de normalisation d'indice. [Diagnostic C2, données et prototype bloqué](../reports/STRAT_A3_C2_assemblage_2026-10-21/bilan.md).
Reprendre avec un protocole garantissant C2, sans réutiliser ces scores comme repère ; conserver les données et défauts scientifiques.
Les autres actions indépendantes restent autorisées. Aucun exemple livré modifié.

**A4 — Le Rate évince-t-il l'optique pure ?** (conception 2 h, mesure 2 h). *Pourquoi* : au juge de paix, les plans optiques purs déposables sont passés de
487 à 50 (ancien modèle d'arrêt), le meilleur plan optique pur de 0,178 à 0,193 nm ; l'hypothèse, non mesurée, est qu'ELITE, dont les parents sont
maintenant en majorité des plans Rate, raffine moins la lignée optique pure (`reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`, mesure 4). *Faire* : un
levier `elite_optical_parents` (entier, `0` = le chemin d'avant, **bit pour bit** : le prouver comme `tests/unit/test_strat_elite_rate_moves.py` le fait
pour `rate_moves=False`) qui garantit, parmi les parents d'ELITE, au moins M plans sans aucune couche Rate quand la liste en contient ; le mesurer au
juge de paix (graine 42) avec M = 0, 2, 4, puis à `r75x0.5` (graine 101). *Fini quand* : pour chaque M, le meilleur SEEL optique pur, le meilleur SEEL
global et le nombre de plans optiques purs déposables, dans un rapport. **Le contrat de taille** : `certus/core/certus_strat_consensus.py` est à 1 498
lignes (plafond 1 500) et `_apply_elite_refinement_if_enabled` à 299 (plafond 300) : ne rien y ajouter qui ne soit pas compensé, mettre la logique dans
`certus/core/certus_strat_robustness_rate.py` comme `_elite_rate_candidates`. *Ne pas* : l'armer par défaut (c'est à 👤).

**A5 — ELITE : plus de tours, autre budget pour les mouvements sur les couches Rate** (≈ 4 h). *État au 21 octobre* : référence neuve terminée, SEEL 0,3967147882 nm ; six tours interrompus pour extinction du PC, dix tours et budgets 40/360 non lancés. [Résultats conservés et reprise](../reports/STRAT_A5_tours_budgets_2026-10-21/bilan.md). Action ouverte. *Pourquoi* : ELITE fait 3 tours en `deep` et s'arrête
quand rien ne progresse ; la recherche des paquets est une escalade qui n'a peut-être pas fini. *Faire* (`r75x0.5`, graine 101, référence : 0,3967 nm) :
`elite_rounds=6,elite_stop_on_no_gain=false`, puis `elite_rounds=10,elite_stop_on_no_gain=false` ; puis, à 3 tours, `elite_rate_max_candidates=40` et
`elite_rate_max_candidates=360`. Une surcharge à la fois, avec son étiquette. *Fini quand* : un tableau tours et budget → meilleur SEEL, durée, nombre de
paquets de Rate du meilleur plan. Si les largeurs de fenêtre (`ELITE_RATE_WINDOWS`) ou le pas (`ELITE_RATE_STEP`) méritent un balayage, en faire des
paramètres **inactifs par défaut** (chemin d'avant identique) avant de les mesurer. *Ne pas* : changer un défaut sans 👤.

**A7 — Corrections de la vitrine : propositions remises (2026-10-20).** Neuf passages relus, textes proposés en anglais et nombres sourcés dans [`STRAT_vitrine_passages_a_relire`](../reports/STRAT_vitrine_passages_a_relire_2026-10-20.md). La page reste identique à `96128ba5`. Après accord explicite du propriétaire, une action séparée pourra intégrer les passages retenus et vérifier le HTML.

**A8 — Dette technique** (§4 et §6) : un défaut par tâche, un commit par changement, jamais `ruff check --fix`, jamais agrandir `extend-ignore`.
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

**A9 — Tenter le99c en une seule campagne avec injection et derniers raffinements Rate** (demande de 👤 du2026-10-16 ; à préparer, non exécuté).
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

**A10 — Chercher à ±0,010 ou à ±0,005 : trancher par le calcul** (demande de 👤 du 2026-10-20 ; ≈ 4 h). *Pourquoi* : l'étage
`strat_local_search` cherche à ±0,010 d'incertitude d'indice (`SEARCH_INDEX_CORRIDOR`, `certus/core/certus_strat_local_search.py`),
sur une règle écrite d'avance qui a préféré ±0,010 sur 2 designs de 3 (`reports/STRAT_r75_leviers_bonne_mere_2026-10-20/bilan.md`,
section 7 : arrêts à ±0,010 de 175 à 0 sur 75c, coût à ±0,005 de +1,0 %, −3,5 % et +11,4 %). Une graine, trois designs : ce
n'est pas tranché. *Faire* : sur 75c, r75x0.5, r75x2 et le juge de paix, graines de banc 77, 101 et 202, banc deep avec l'étage
cherchant à ±0,010 puis à ±0,005 (constante surchargée), et un troisième essai jugé au pire des deux amplitudes ; juger les plans
finaux à ±0,005 et ±0,010 sur graines neuves, même règle (gain à ±0,010 au-delà de deux erreurs types, coût à ±0,005 ≤ 2 %,
aucun arrêt ajouté). *Fini quand* : un rapport dans `reports/` donne le choix par design et un défaut proposé à 👤. *Ne pas* :
changer `index_corridor` de la configuration (la notation reste à ±0,005) ni le défaut sans l'accord de 👤.
