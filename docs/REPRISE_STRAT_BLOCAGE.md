# Reprise — STRAT sur l'exemple réel

Écrit le 2026-08-05, **révisé le 2026-08-05 après mesure et après réponse du physicien.**
Autonome : chaque chiffre a été mesuré, la commande est donnée.

> 🔴 **Lance Claude Code depuis `C:\dev\CERTUS\0108`.**
> À lire avec [`REPRISE_SESSION_2026-08-03.md`](REPRISE_SESSION_2026-08-03.md) §0 pour
> l'environnement et les pièges de mesure.

---

## 0. L'état en une phrase

Le blocage de STRAT sur `example/example_strat/JSON-strat-example.json` — 240 stratégies
minées, 240 éliminées, `RESULT=None` — **n'était pas un défaut de code. C'était le
`trigger_tolerance = 0.5` du fichier d'exemple, cinq fois trop grand.** Corrigé à `0.05`,
STRAT rend 43 stratégies dont **25 sûres à 0–2,5 % de plantage**, en blocs de six couches.

---

## 1. Le composant

`JSON-strat-example.json` : dichroïque passe-court, 48 couches Nb₂O₅ / SiO₂ sur SiO₂,
l₀ = 550 nm. Bande passante 400–540 nm à ≈ 95 % ; front raide 544–552 ; bande bloquée
555–800 nm à moins de 0,1 %.

Le monitoring balaie 450–700 nm, donc plus de la moitié de la plage tombe dans la bande
bloquée. **Ce n'est pas un problème** — voir §2.2.

---

## 2. Ce qui est tranché

### 2.1 🔴 Le bruit de mesure — LE point qui bloquait tout

`trigger_tolerance` s'applique en **% de transmission** (`valeur / 100`, donc `0.5` →
σ = 0,5 point de T absolu).

**Réponse du physicien, 2026-08-05 :** sur OMS 5100, le signal fluctue typiquement de
**45,5 % à 45,55 %**, soit **0,05 point**. Le `0.5` de l'exemple est donc **dix fois trop
fort**.

⚠️ **Le défaut du dépôt n'est PAS correct non plus.** Une version antérieure de cette page
l'affirmait — c'est faux, et la ligne suivante le démontre. `0.1`
(`certus/ui/certus_strat_ui_state.py:90` et `:943`) vaut **deux fois** le bruit réel, donc
**quatre fois** une fois passé au facteur 2 du modèle. Il est seulement *moins* faux que le
`0.5` de l'exemple. **La valeur juste est `0.05` aux deux endroits** : le fichier d'exemple
**et** le défaut de l'interface.

**⚠️ La marge de sécurité ×2 est DÉJÀ dans le modèle, ne l'applique pas deux fois.**
`_resolve_robustness_noise_levels` (`certus/core/certus_strat_robustness.py:152-163`) rend
`[base × 0,5 ; base × 1,0 ; base × 2,0]`, et `crash_rate_max` est le **maximum sur ces trois
niveaux** (`:703`), c'est lui qui décide de l'élimination (`:743`). Régler la base à `0.1`
pour « prendre une marge » fait tester à σ = 0,2, soit **quatre fois** le bruit réel.

Mesuré, machine au repos, un run par ligne :

| `trigger_tolerance` | stratégies | repêchées | crash min / médian | `nblocks` du 1ᵉʳ | `RESULT` | `RUN_S` |
|---|---|---|---|---|---|---|
| **0,5** — exemple actuel | 4 | **4/4** | 0,700 / 0,800 | 19 | 0,4704 *(repêchage)* | 44 s |
| **0,1** — marge ×2 en trop | 37 | **36/37** | 0,025 / 0,225 | 12 | 0,0677 *(repêchage)* | 105 s |
| **0,05** — ✅ valeur juste | 43 | 18/43 | **0,000 / 0,025** | **8** | **0,0178** *(vrai score)* | 201 s |

À `0.05` : `RANK00 id=8202 origin=ELITE score=0.017793 crash=0.0250 elim=False nblocks=8
wl=[550,485,460,455,465,460,475,495]`.

✅ **Fait.** `example/example_strat/JSON-strat-example.json:78` porte `"trigger_tolerance": "0.05"`
depuis le commit `0551b60` — celui-là même qui a écrit ce document en annonçant l'inverse.
Une version antérieure de cette section disait « reste à faire, non fait » : c'était faux,
la correction était dans le même commit. Vérifier par
`git show HEAD:example/example_strat/JSON-strat-example.json | grep trigger_tolerance`.

⚠️ **Reste à faire, en revanche : le défaut de l'interface.** Il vaut encore `0.1`
(`certus/ui/certus_strat_ui_state.py:90` et `:943`), soit deux fois le bruit réel — donc
quatre fois après le facteur 2 du modèle. Tout utilisateur qui part d'une configuration
neuve, sans charger l'exemple, hérite de cette valeur.

### 2.2 La plage de balayage — on ne la borne pas

**Réponse du physicien :** « ce filtre est un exemple particulier, on laisse la bande
entière ». Question close.

Confirmé par la mesure : à `trigger_tolerance = 0.05`, la Phase A ne retient **aucune
longueur d'onde au-dessus de 495 nm** alors que le balayage monte à 700. Elle écarte la
bande bloquée d'elle-même, via le critère de plantage du §3.3. Rien à coder.

### 2.3 Le TPM — parqué, pas abandonné

**Réponse du physicien :** option future d'un **booléen autorisant le TPM en plus du
trigger**. En attente, parce que l'OMS 5100 ne sait pas basculer d'un contrôle à l'autre en
cours de dépôt. Ne pas implémenter.

Le fait physique reste vrai et vaut d'être retenu : un empilement quart d'onde monitoré à sa
propre longueur de centrage plante à 100 %, parce qu'à QWOT exact l'arrêt tombe sur le point
tournant où dT/dd = 0. Aucun réglage de seuil ne changera cela.

### 2.4 L'ancrage `RESULT` du banc — il n'a jamais été cassé

`RESULT=None` sur STRAT n'était **pas** un défaut d'extraction. La chaîne est :
liste vide → `raise RuntimeError("No strategies found.")`
(`certus/workers/certus_strat_workers.py:1370`) → remontée au `except Exception` de
`WorkerThread.run()` (`:1011`) → `signals.error.emit` → **`finished` jamais émis** →
`wait_for` rend `None`.

L'ancrage avait déjà été réparé le 3 août (`REPRISE_SESSION_2026-08-03.md` §11.2) et
`scripts/bench_examples.py` n'a pas changé depuis `d38e969` — la version même qui a rendu
`RESULT = 0,02519543055680181` sur 8 runs consécutifs.

Ce qui manquait vraiment, et qui est fait : STRAT compte **cinq** sites de levée avant son
unique `finished.emit`, et le banc les confondait tous en un `None` muet. `wait_for` distingue
désormais ses trois sorties (`WAIT_EXIT=finished|error|timeout`), crie son `WAIT_TIMEOUT`, et
imprime la **trace complète** de l'exception.

Reproductibilité vérifiée : deux runs chauds rendent `RESULT` identique au bit près et le
même classement, mêmes identifiants, même ordre.

---

## 3. Les mécanismes du modèle — acquis, ne pas y revenir

| # | Mécanisme | Commit | Effet mesuré |
|---|---|---|---|
| 1 | Cible figée sur le nominal | `b58e7aa` | la compensation d'erreur existe enfin |
| 2 | POEM (Arsac eq. 2.2) | `4b8b3c5` | gain 1,15-2,30 → 0,73-0,78 |
| 3 | Historique du bloc | `87bb056` | facteur 3,6 sur couches minces |
| 4 | Détection de plantage | `932c744` | repli muet 6,68 % → 0,04 % |
| 5 | Élimination sur crash ≥ 5 % | `457be8a` | `rmse_p95` y était aveugle |

### 3.1 Le filtre de robustesse ne peut plus rendre une liste vide
`certus/core/certus_strat_robustness.py::_filter_finite_robustness_scores` — s'il éliminerait
tout, il reclasse par risque croissant, rend un score fini, marque `crash_eliminated = True`
et le dit en `logger.error`.

⚠️ **Un `robustness_score` marqué `crash_eliminated` n'est PAS un score de robustesse** :
c'est `_worst_finite_rmse`. Deux runs dont l'un a repêché et l'autre non **ne sont pas
comparables**. Le banc l'affiche désormais (`STRAT_CRASH_ELIMINATED=n/N`).

Ce repli reste utile — mais à `trigger_tolerance = 0.05` il ne concerne plus que 18 des 43
stratégies, au lieu de la totalité. Il est redevenu un filet de sécurité au lieu d'être la
sortie du module.

### 3.2 Le seuil de la Phase A se déduit de la hauteur de l'empilement
`certus/utils/certus_strat_service.py::_validate_candidates_phase_a` :
`crash_tol = 1 − (1 − 0,05)^(1/N)`, soit 0,107 % pour N = 48 — quarante-sept fois plus strict
que 5 %. Surchargeable par `params["phase_a_crash_tolerance"]`.

L'arithmétique du taux qui se compose sur 48 couches est **juste**. Elle n'était simplement
pas la cause du blocage : appliquée au bon bruit, elle laisse passer 25 stratégies.

### 3.3 Les trois critères de la Phase A
`validate_wavelengths_batch` rend **(n_cands, 4)** : `P95(|Δd|)` · écart-type ·
**taux de plantage** · **gain de compensation**.

- Coût : `P95 + w · gain · erreur_amont`, deux termes en nanomètres, aucune constante
  d'ajustement. `erreur_amont` (`phase_a_prev_error_nm`) est un P95 sur les états Monte-Carlo
  réellement propagés — mesuré, pas postulé. Sous **0,05 nm** il est mis à zéro.
- **Le taux de plantage n'entre PAS dans le coût** : une stratégie qui ne se termine pas
  n'est pas médiocre, elle est inutilisable. Elle est **éliminée** (`crash ≥ crash_tol`, ou
  `gain < 0` = non mesurable).
- Le gain coûte **deux évaluations à bruit nul**, aucun Monte-Carlo. Couche 25 : 0,257 à
  550 nm contre 4,35 à 475 nm, un facteur 17 que le seul P95 classait à l'envers.
- `block_start_arr` par candidate : un candidat qui reprend la λ précédente prolonge le bloc
  et hérite de son historique de points tournants. Effet mesuré : jusqu'à 2,5× sur le gain.

### 3.4 La détection de plantage n'est plus conditionnée à `poem_ok`
`certus/physics/certus_strat_growth.py`. La garde `if poem_ok` désactivait la détection
précisément quand POEM est mal conditionné. Mesuré, 48 couches × 51 λ, erreur amont +2 nm :
repli muet sur le sommet de la parabole **6,68 % → 0,04 %** ; non-terminabilité signalée
**0,21 % → 7,26 %**. Indépendant de `probe_offset` (6,63 % à 0,5 nm, 6,88 % à 10 nm) : ce
n'était pas un artefact du fit.

### 3.5 `probe_offset` — examiné, exonéré
Ce n'est pas un décalage de sonde : c'est la demi-largeur du fit parabolique à 3 points qui
inverse T → d. À la valeur configurée (ratio 120 → 2,384 nm), l'écart à la racine exacte est
**sous 0,05 nm partout** sauf près d'un extremum. Biais en ~δ² : −3,9 nm à δ = 20 nm.
**`sim_thickness_probe_offset_ratio` est un DIVISEUR** — le baisser sous ~30 rend le fit faux.

---

## 4. 🔴 Protocole de mesure — deux pièges découverts le 5 août

### 4.1 Le cache numba fausse tout A/B qui bascule un fichier à noyaux `@njit`

Numba tient un cache sur disque (`certus/*/__pycache__/*.nbi`) dont la clé est l'empreinte
`(mtime, taille)` du source. `ab_compare.sh::switch_to` recopie par `cp -f`, ce qui **remet
le mtime à maintenant** : le run qui suit recompile tout.

Mesuré sur STRAT, machine au repos : **145,3 s à froid contre 44,1 et 37,7 s à chaud.** La
compilation pèse ~105 s, soit **72 % du `RUN_S` à froid**.

Et ce n'est pas du bruit, c'est un **biais orienté** : le bras qui contient le plus de code à
compiler paie la recompilation la plus longue, et l'A/B attribue l'écart à son coût
d'exécution. Sur le balayage POEM le faux positif tombe exactement dans le sens attendu.

✅ **Correctif posé** : `AB_WARMUP=1` insère un run jeté après chaque bascule.

```bash
AB_WARMUP=1 bash scripts/ab_compare.sh "<liste>" "<commit>^" strat 4 --auto-yes
```

### 4.2 La liste de fichiers de l'A/B STRAT était incomplète

La campagne prescrite portait sur trois fichiers. **Cinq** fichiers de `certus/` portent les
correctifs : il manquait `certus/utils/certus_strat_service.py` et
`certus/core/certus_strat_objectives.py`. Résultat mesuré, quatre paires sur quatre :

```
paire N  SANS : RUN_S=3,6 s   RESULT=None      <- le pipeline meurt avant de calculer
paire N  AVEC : RUN_S=45 s    RESULT=0,4704
```

C'est le piège que l'en-tête d'`ab_compare.sh` documente déjà : signatures incompatibles,
exception avalée, bras SANS faussement rapide. **Cette campagne est nulle et non avenue.**

Commande corrigée (les cinq fichiers existent bien à `b58e7aa^`) :

```bash
AB_WARMUP=1 bash scripts/ab_compare.sh \
  "certus/physics/certus_strat_growth.py,certus/physics/certus_strat_batch.py,certus/core/certus_strat_robustness.py,certus/utils/certus_strat_service.py,certus/core/certus_strat_objectives.py" \
  "b58e7aa^" strat 4 --auto-yes
```

⚠️ Le bras SANS est antérieur à la cible figée : ses scores ne sont pas comparables aux
nôtres. `RESULT` ne peut donc pas jouer son rôle habituel de preuve que le résultat n'a pas
bougé — il sert seulement à vérifier que **chaque bras est stable sur ses quatre runs**.

⚠️ **`ab_compare.sh` réécrit l'arbre de travail.** Son `trap` restaure sur EXIT/INT/TERM,
mais pas sur `SIGKILL`. Committe ou stashe avant de le lancer.

---

## 5. Ce qui reste à faire

1. **Décider du `trigger_tolerance` de l'exemple** (§2.1). Trois lignes de mesure sont
   au-dessus, la décision est physique, pas technique.
2. **Relancer l'A/B du coût POEM** avec la commande corrigée du §4.2. Non mesuré : la
   première campagne était invalide.
3. **Refaire le tableau des deux critères orthogonaux** de
   [`REPRISE_STRAT_MONITORING.md`](REPRISE_STRAT_MONITORING.md) §2 et de
   `pages/CERTUS_STRAT.html`. Il est faux **deux fois** : établi avant le correctif du §3.4
   (plantages sous-comptés d'un facteur ~30) **et** à `trigger_tolerance = 0.5`, soit cinq
   fois trop de bruit. Les deux pages portent l'avertissement ; les chiffres restent à
   refaire.
4. **Le logger de STRAT écrit dans `certus_certus_re.log`** — les traces d'un module partent
   dans le fichier d'un autre, et seules les lignes de JIT-WARMUP y arrivent. Le classement
   d'un run n'est nulle part sur le disque. C'est pour cela que le banc l'imprime désormais
   lui-même (`STRAT_RANK00…`).
5. **La version de référence `G:\Mon Drive\couches minces 2026\CERTUS\0807`** (13 juillet,
   `a0646df`) : non confirmée. Import réussi, mais le processus meurt sans trace dans
   `warmup_physics()` ou la construction de `CertusStratApp` depuis le disque G:.
   `certus_strat_ranking.py` y fait exactement 564 lignes, comme ici — la chaîne DP/mining
   est donc inchangée depuis le 13 juillet, ce qui désigne la Phase B comme seule différence.
   Piste : copier `0807` sur un disque local, le cache numba sur Google Drive étant un
   suspect connu.
6. **`trigger_tolerance` est décrit comme « % of thickness »** dans l'infobulle
   (`certus/ui/certus_strat_ui_layout.py:807`) alors que le code l'applique en **% de
   transmission**. Deux grandeurs différentes sous un même nom.

---

## 6. Garde-fous

- 🔴 **Une différence d'épaisseur inférieure à 0,05 nm est NULLE** : moins d'un atome. Ne
  conclus rien d'un écart sous ce seuil et n'en fabrique pas un critère.
- 🔴 **Le hook `post-commit` est ACTIF** (`.git/hooks/post-commit`, exécutable) et pousse
  chaque commit vers le dépôt **public** `nikonvr/CERTUS`. `--no-verify` ne le neutralise
  pas. ⚠️ `CLAUDE.md` §5.4 affirme le contraire — **`CLAUDE.md` a tort sur ce point.**
- 🔴 **Ne jamais mesurer avec autre chose en vol** : facteur 6,6 constaté. Et le premier run
  d'une campagne n'est pas comparable aux suivants (§4.1).
- Les scores de robustesse ne sont comparables ni à ceux d'avant `b58e7aa`, ni entre un run
  qui a repêché et un run qui ne l'a pas fait (§3.1).
- ⚠️ **`[Block 48] Mining returned 0 strategies` n'est PAS un symptôme.** C'est normal :
  `force_first_layer_same_wl=True` interdit un premier bloc d'une seule couche, donc 48 blocs
  pour 48 couches est impossible par construction. Le mining fonctionne.
- Valider par `pytest tests/oracle/ -q --no-cov` (552) **et** `tests/unit/test_strat_poem.py`
  (21) **et** `tests/unit/test_certus_strat_coherence.py`.
- Éditer avec un outil à ancre exacte, **pas** un script de recherche-remplacement.
