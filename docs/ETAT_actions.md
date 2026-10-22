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

**Répartition** (👤, 2026-10-21) : chaque action porte l'IA qui la prend. **Gemini** : exécution d'un protocole écrit ; **ChatGPT** : code ou
campagne bien spécifiés ; **Claude** : conception, piège de reproductibilité, interprétation. Chaque action se fait sur sa propre branche
(`git worktree add`), commits locaux, **jamais de `git push`** ; la branche est relue avant fusion (référence §12). Depuis le 2026-10-20, l'étage
`strat_local_search` est actif par défaut (+ 20 min par banc) : le dire dans chaque rapport. Outils de jugement :
`reports/STRAT_r75_leviers_bonne_mere_2026-10-20/outils/`.

**Enchaînement** : Gemini, puis ChatGPT, puis Claude. Gemini travaille sur `gemini/<date>` et finit par `reports/RELAIS_gemini_<date>.md` ; ChatGPT part de cette branche (`chatgpt/<date>`), la relit d'abord (commandes rejouées, `config` des artefacts, tests) puis fait ses actions et finit par `reports/RELAIS_chatgpt_<date>.md` ; Claude relit les deux branches, interprète et propose la fusion à 👤. Un relais tient en une page : branche, tête, verdict de `python scripts\validate_parallel.py`, ce qui est fait, ce qui a échoué, questions ouvertes, première commande de l'IA suivante. Celle-ci vérifie, elle ne croit pas.

### Gemini

**A5 — ELITE : six et dix tours, budgets 40 et 360** (≈ 4 h). Référence faite par Codex : `r75x0.5` deep graine 101, 3 tours, arrêt actif, budget 120,
SEEL 0,3967 nm (branche `codex/actions-prudentes-2026-10-20`, `reports/STRAT_A5_tours_budgets_2026-10-21/`). *Faire* : quatre bancs, un à la fois,
`strat_local_search=false` dans chaque surcharge pour isoler ELITE : `elite_rounds=6,elite_stop_on_no_gain=false` ; `elite_rounds=10,elite_stop_on_no_gain=false` ;
`elite_rate_max_candidates=40` ; `elite_rate_max_candidates=360`, plus la référence refaite avec `strat_local_search=false`. *Livrable* :
`reports/STRAT_A5_tours_budgets_suite_<date>/bilan.md`, un tableau de cinq lignes (surcharge, SEEL du meilleur plan, durée, paquets Rate du meilleur
plan, commit) et les cinq artefacts ; chaque ligne cite la valeur lue dans `config` de son artefact. *Fini quand* : les cinq lignes existent.
*Ne pas* : changer un défaut, conclure (l'interprétation revient à Claude).

**A8a — Dette de lint E402, module par module** (une heure par module). *Faire* : mesure officielle
`python -m ruff check . --isolated --select E402 --line-length 120 --target-version py314 --statistics` ; pour un module, déplacer les imports
en tête sans rien changer d'autre, photos avant/après (`scripts/lint_ns_snapshot.py`). *Livrable* : un commit par module, message avec le nombre
E402 avant/après et la ligne `VALIDATION=GO` de `python scripts\validate_parallel.py`. *Fini quand* : E402 baisse et la validation passe.
*Ne pas* : `ruff check --fix`, agrandir `extend-ignore`, lancer `scripts\metrics.py --dette` pour faire passer un test.

**A14 — [Gemini] Valider l'étage sur tout le panel** (≈ 7 h ; à faire avant A10). Mesuré seulement sur 75c, `r75x0.5`, `r75x2`. *Faire* : `python -X utf8 reports/STRAT_etage_defauts_2026-10-21/run_etage_panel.py.txt A14` (`48c` premium avec recherche de fente, `35c`, `r75x1.5`, `r75x1.75`, `r75x2-2nm`, 75c graine 101). *Livrable* : `reports/STRAT_etage_A14_<date>/` tel qu'écrit, commité. *Critère*, pour l'interprétation par Claude, écrit d'avance : jamais de SEEL dégradé ni d'arrêt ajouté, gain sur la majorité des designs, tenue à ±0,010.

**A10 — [Gemini] Confirmer l'étage à ±0,010 sur d'autres graines** (≈ 5 h). 👤 a choisi ±0,010. *Faire* : depuis la racine, arbre suivi propre, `python -X utf8 reports/STRAT_etage_defauts_2026-10-21/run_etage_panel.py.txt A10` (75c graine 202, `r75x0.5` 202, `r75x2` 101 et 202 ; reprend là où il s'est arrêté). *Livrable* : le dossier `reports/STRAT_etage_A10_<date>/` qu'il écrit (`bilan.md`, `cas.json`, artefacts), commité tel quel. *Fini quand* : quatre lignes. *Ne pas* : interpréter, changer `SEARCH_INDEX_CORRIDOR` ou `index_corridor`.

### ChatGPT

**A4 — Garantir des parents optiques purs à ELITE** (conception 2 h, mesure 2 h). *Pourquoi* : au juge de paix, les plans optiques purs déposables
sont passés de 487 à 50 depuis le secours Rate (`reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`, mesure 4). *Faire* : levier
`elite_optical_parents` (entier, 0 = chemin d'avant), qui garantit au moins M parents sans couche Rate, logique dans
`certus/core/certus_strat_robustness_rate.py` (`certus_strat_consensus.py` est à son plafond de taille). *Livrable* : le levier, une entrée du
registre `certus_strat_leviers.py`, un test qui prouve le chemin à 0 identique au bit (modèle : `tests/unit/test_strat_elite_rate_moves.py`),
`python scripts\c1_diff.py HEAD` = « C1 TENU », puis `reports/STRAT_A4_parents_optiques_<date>/bilan.md` : M = 0, 2, 4 au juge de paix (graine 42) et
à `r75x0.5` (graine 101), meilleur SEEL global, meilleur SEEL optique pur, nombre de déposables optiques purs. *Ne pas* : l'armer par défaut.

A4 livré le 2026-10-22 : levier à 0 par défaut, code validé en série et C1 tenu, [six bancs](../reports/STRAT_A4_parents_optiques_2026-10-22/bilan.md). 👤 demande à Claude de refaire l'analyse Gemini/GPT ; [relais](../reports/RELAIS_chatgpt_2026-10-22.md). A8b non entamé, différé pour cette passation.

**A8b — Imports montants (D26)** : 20 arêtes (§4) ; descendre un symbole dans `certus/domain/` ou `certus/core/`. *Livrable* : un commit par arête,
`python scripts\metrics.py --dette tests\architecture_debt.json` après chaque dette payée (il ne fait que rétrécir), validation complète.

**A9 — 99 couches en une campagne** (demande de 👤 du 2026-10-16). Protocole prêt : `reports/STRAT_99c_A9_protocole_2026-10-17/` (`chain_A9.sh`,
graines réservées) ; il ne lance rien sans `GO_OWNER.txt` écrit par 👤, que 👤 donnera après A14 (décision du 2026-10-21). *Livrable* : sur plusieurs graines, plans déposables, plantages, SEEL de
consensus des plans figés, confirmation indépendante et coût, dans le dossier du protocole. *Ne pas* : lancer sans le GO.

### Claude

**A3 — Les repères à 99 couches, conformes à C2.** Codex a refait six repères (graine 42, `reports/STRAT_A3_reperes_reprise_2026-10-21/`, sa branche)
et écarté l'assemblage des douze intervalles du 99 couches : croissance et notation n'y voient ni le même indice de bruit ni les mêmes domaines
de normalisation d'indice (`reports/STRAT_A3_C2_assemblage_2026-10-21/`). *Livrable* : un protocole qui garantit C2, prouvé par un test qui
échoue sur l'assemblage écarté, puis le repère dans la table §2 avec son rapport.

**A11 — Afficher la sensibilité de chaque stratégie à l'erreur d'indice.** *Pourquoi* : le but de STRAT est une stratégie peu sensible à l'indice
(👤) ; la part d'indice se mesure (même plan, mêmes tirages, corridor actif puis nul : `outils/index_share.py.txt`). *Livrable* : un paramètre
inactif par défaut qui la calcule pour les K premières stratégies, une colonne dans les résultats et l'export Excel, un test, `c1_diff` tenu, et
un rapport sur les trois 75 couches.

**A12 — Guider la recherche locale par la sensibilité à l'indice.** Concentrer les candidats de `strat_local_search` sur les couches qui
transmettent le plus l'erreur d'indice ; essayer des mouvements de deux ou trois couches voisines. *Livrable* : une option inactive par défaut,
mesurée contre l'étage actuel sur les trois 75 couches × deux graines, règle écrite avant la mesure, rapport.

**A13 — Rendre `strat_local_search` rapide en production** (👤 : « un code ultra performant »). L'étage coûte 2 300 à 3 900 évaluations de
300 tirages, environ 20 min par calcul. *Livrable* : un profil (`cProfile`) d'une évaluation qui sépare noyau compilé et préparation Python ; les
gains qui gardent les bits (préparation hors boucle, réutilisation des tableaux) prouvés identiques par un test ; les gains qui changent la
recherche (présélection à moins de tirages) mesurés contre l'étage actuel avec une règle écrite d'avance ; un rapport avec la durée avant/après.
