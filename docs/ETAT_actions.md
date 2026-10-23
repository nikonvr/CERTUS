# CERTUS — actions à lancer et protocole de mesure

> Les actions ouvertes et le protocole de mesure. Ce contenu **fait autorité** ;
> `ETAT.md` n'en garde qu'un renvoi. **Un fait, un seul endroit** : corrige ici, ne recopie pas ailleurs, mets un lien.
> Les `§N` nus sont les sections de `ETAT.md`. Le vocabulaire (Rate, déposable, SEEL) et les acquis sont dans [`ETAT_acquis.md`](ETAT_acquis.md).

**Prochaines actions.** Lire dans l'ordre : [`CLAUDE.md`](../CLAUDE.md) (les règles et les onze interdits), la section 0 de [`ETAT.md`](ETAT.md), puis l'action choisie. Chaque action est
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

**A3 — Les repères à 99 couches, conformes à C2.** Six repères refaits (graine 42, `reports/STRAT_A3_reperes_reprise_2026-10-21/`) ;
l'assemblage des douze intervalles du 99 couches est écarté : croissance et notation n'y voient ni le même indice de bruit ni les mêmes domaines
de normalisation d'indice (`reports/STRAT_A3_C2_assemblage_2026-10-21/`). *Livrable* : un protocole qui garantit C2, prouvé par un test qui
échoue sur l'assemblage écarté, puis le repère dans la table §2 avec son rapport.

**A9 — 99 couches en une campagne** (demande de 👤 du 2026-10-16). Protocole prêt : `reports/STRAT_99c_A9_protocole_2026-10-17/` (`chain_A9.sh`,
graines réservées) ; il ne lance rien sans `GO_OWNER.txt` écrit par 👤. *Livrable* : sur plusieurs graines, plans déposables, plantages, SEEL de
consensus des plans figés, confirmation indépendante et coût, dans le dossier du protocole. *Ne pas* : lancer sans le GO.

**A13 — Rendre `strat_local_search` rapide en production** (👤 : « un code ultra performant »). 96 % du temps est dans deux noyaux
compilés ([profil](../reports/STRAT_A13_profil_2026-10-23/bilan.md)). Présélection des candidats codée, inactive : 75/3 et 150/5 refusées par
leurs règles ([bilan](../reports/STRAT_A13_preselection_2026-10-23/bilan.md)). *Reste* : accélérer un noyau (prouvé au bit par `c1_diff`).

**A5 — ELITE : six et dix tours, budgets 40 et 360** (≈ 4 h). Référence : `r75x0.5` deep graine 101, 3 tours, arrêt actif, budget 120,
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

**A15 — Reporter cinq observations du contre-audit ARGON** (`reports/ARGON_contre_audit_2026-10-16/pass02.json` : grille oblique non densifiée,
bornes et arrêt ignorés au raffinement final) dans `UXargon.md` et `designargon.md`, chacune vérifiée par un test avant correction.
