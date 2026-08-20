# PLAN — porter le savoir des campagnes dans le CODE DE PRODUCTION

> 👤 (2026-08-20) : *« mon but désormais est de transférer tout le savoir acquis ces derniers
> jours vers le code de production. Il faut que le code de production sache trouver les
> meilleures configs avec les meilleurs SEEL. »*

**Ce document est un ordre de mission daté**, dans la forme prescrite par `CLAUDE.md` §1 : des
actions, des commandes, ce que chaque résultat décide. Il ne recopie aucun fait — chaque ligne
renvoie à la mesure qui la fonde.

---

## 0. 🔴 LE CONSTAT QUI COMMANDE TOUT LE PLAN

📏 **Mesuré le 2026-08-20**, en chargeant le JSON livré et en lisant `collect_params` :

```
JSON modifie : robustness_seed = 77, monochromator_resolution_nm = 2.0

  robustness_seed              = 42       🔴 IGNORE (le JSON demandait 77)
  phase_a_seed                 = 42       🔴 idem, il suit robustness_seed
  monochromator_resolution_nm  = 2.0      🟢 honore
  execution_mode               = 'deep'   🟢 honore
```

**Cause** : `certus_strat_ui_state.py:1253` lit la graine par
`self._get_float_safe("robustness_seed", 42)`, et **aucun widget ne porte ce nom** —
vérifié : 0 déclaration dans tout `certus/ui/`. `_get_float_safe` (ligne 1395) rend alors son
défaut. Le `_loaded_config` est pourtant conservé et sert à **onze** autres clés
(`tp_hysteresis_factor`, `poem_enabled`, `monochromator_resolution_nm`…). La graine est la
grande absente.

### 🔑 Pourquoi c'est structurel et non cosmétique

`CLAUDE.md` §24-46 et §24-47 mesurent que **la graine ne change pas seulement les scores : elle
change QUELLES STRATÉGIES EXISTENT** — 452 candidates contre 521 sur le même intervalle. La
réalisation traverse le bruit → les choix de Phase A → la population entière.

📏 **Et le prix est chiffré sur `r75x2` à 2 nm, en `deep`** :

| graine | déposables | meilleur SEEL |
|---|---|---|
| **42** — *la seule que la production sache atteindre* | **0** | *aucun* |
| **77** | **547** | **0,5692** — le meilleur jamais mesuré sur ce composant |

> **La production, aujourd'hui, ne peut pas trouver la meilleure configuration connue de son
> propre composant d'essai. Non parce qu'elle cherche mal, mais parce qu'elle ne tire qu'un
> seul billet de loterie, et que le billet est soudé.**

C'est le pivot du plan : **tout le reste est du raffinement à côté de ça.**

### ✅ CORRIGÉ LE 2026-08-20 — et le trou était dix fois plus large que ce §0 ne le disait

📏 En cherchant à réparer la graine, la même mesure appliquée à **onze** leviers a montré que
**dix** n'atteignaient pas le calcul :

```
rate_tail_sweep · rate_by_swing · rate_tail_keep_optical · rate_layer_sets
require_turning_point · optical_prefix_sweep · elite_min_improvement
elite_rounds · phase_a_seed · robustness_seed        ->  tous PERDUS
```

🔑 **Ils n'existaient que par surcharge de sonde.** Tout le savoir des campagnes était donc
inaccessible depuis l'application — dont `rate_tail_sweep`, **la seule voie connue pour rendre
`r75x2` déposable à 2 nm**.

✅ **Réparé** (`aad370a`) : les neuf leviers se replient sur `_loaded_config`, comme le
faisaient déjà onze autres clés. Deux aides ajoutées pour les listes. 🔒 Règle d'or vérifiée —
sans clé JSON, chacun retrouve sa valeur inactive. **26 tests, dont 24 échouent sur le code
d'avant.** ⚠️ `elite_rounds` reste fixé par le **mode** et n'est volontairement pas routé :
le laisser surcharger casserait le contrat des modes.

### ⚠️ ET LE §0 CI-DESSUS DOIT ÊTRE LU AVEC UNE CORRECTION IMPORTANTE

Il dit *« la production ne peut pas trouver la meilleure configuration connue de son propre
composant »*. 📏 **C'est vrai à 2 nm, et FAUX à 1 nm** — qui est la résolution **native** du
fichier livré :

```
r75x2, graine 42, PUR OPTIQUE
   1,0 nm + deep   ->  277 deposables   SEEL 0.6248   crash 1,00 %   ✅ PASSE
   1,0 nm + fast   ->    0
   2,0 nm + tout   ->    0
```

**Le fichier livré, chargé tel quel, fonctionne** — c'est le sens de son nom `-fabricable`. Ce
qui ne passe pas à la graine 42 est le **2 nm en pur optique**, et là seule la queue Rate rend
(SEEL 0,672 en `premium`, plantage 2,67 %). 👤 vise **le niveau de 0,569**, que rien n'atteint
aujourd'hui à cette graine.

---

## 1. Les cinq axes, par valeur décroissante

| # | axe | ce qu'il répare | fondé sur |
|---|---|---|---|
| **A** | **la recherche devient MULTI-RÉALISATION** | la production ne voit qu'une population sur N possibles | §0, §24-46, §24-47 |
| **B** | **le SEEL devient la monnaie du classement, de bout en bout** | il n'existe qu'en mémoire d'interface ; le banc ne le voit pas | `CLAUDE.md` §22 |
| **C** | **le LIVRABLE sort** | on sait dire le SEEL d'une stratégie, pas à quelles λ surveiller | §2b ci-dessous |
| **D** | **les leviers MORTS sont retirés ou rebranchés** | ils produisent de la fausse confiance | §24-33, §28, `CLAUDE.md` §8 |
| **E** | **la queue Rate devient un repli AUTOMATIQUE, jamais un défaut** | mesuré : elle sauve là où l'optique échoue, elle coûte ailleurs | `CHANTIER_RATE.md` §16, §20 |

---

## 2. AXE A — la recherche multi-réalisation

### 🔑 LA GRAINE N'ENTRE PAS PAR UNE PORTE, MAIS PAR TROIS

Poser « plusieurs graines » sans les distinguer reviendrait à payer le prix fort pour n'en
réparer qu'une.

| porte | ce que la réalisation y décide | état |
|---|---|---|
| **1. génération** — Phase A choisit **une** λ par couche, par argmin sur un signal bruité | *quelles candidates naissent* | 🔴 à faire, c'est A2 |
| **2. élimination** — la porte de plantage compare un taux **estimé** à un seuil **fixe** | *lesquelles survivent* | 🟢 **déjà codé, éteint partout** — c'est A0 |
| **3. troncature** — la DP garde `dp_top_k` (20 `fast` · 40 `premium` · 100 `deep`) | *lesquelles sont notées* | 🟠 se referme sous A2 |

### A0. 🟢 ARMER LA PORTE DE PLANTAGE À CONFIANCE — une ligne par configuration

`_crash_gate_rejects` (`certus_strat_robustness.py:1744`) porte **déjà** le correctif, avec sa
mesure du 2026-08-13 dans sa propre docstring :

```
probabilite qu'une strategie soit REJETEE, selon son VRAI taux
              N=50     N=150    N=300    N=500
 3 % (bonne) 18,9 %    8,3 %    3,9 %    1,0 %   <- rejetee A TORT
 7 % (mauvaise) 68,9 % 83,1 %   93,5 %   97,2 %
```

> *« Un filtre dont le verdict change avec la profondeur n'est pas un filtre, c'est un
> échantillonneur. »* — le code, ligne 1765.

Le correctif ne rejette que lorsque la **borne de confiance basse** dépasse la tolérance. Trois
conséquences, toutes voulues : une bonne stratégie n'est jamais éliminée par malchance ; un run
court rejette peu, ce qui est **honnête** ; la porte se resserre d'elle-même avec la profondeur,
sans changer de règle. 🔒 **La tolérance de 5 % ne bouge pas** — c'est l'estimateur qui était
faux, jamais la valeur de 👤.

📏 **Vérifié le 2026-08-20 : `crash_gate_confidence` est ABSENT des 20 JSON livrés.** Il vaut
donc 0, c'est-à-dire la comparaison historique. Et contrairement à `robustness_seed`, **cette
clé est bien lue depuis le JSON** (`certus_strat_ui_state.py:1229`).

**Action** : `"crash_gate_confidence": 0.95` dans les configurations. Coût : une ligne. C'est le
meilleur rapport valeur/risque de tout le plan, et il passe **avant** A1.

⚠️ **C1 s'applique** : la porte change de comportement, donc **toute mesure antérieure devient
incomparable**. Armer et remesurer, jamais armer au milieu d'une campagne.

### A2bis. 🔴 Les deux détails qui décident du succès de l'union

**(a) Les graines de GÉNÉRATION doivent être disjointes des graines de NOTATION.** Le consensus
tourne sur `[41,42,43]`. Une stratégie engendrée sous 42 **et** notée sous 42 est avantagée par
sa propre chance — c'est la malédiction du vainqueur, mesurée à **+12,9 %**. Générer sur
`{77, 101, 202, 303, 404}`, noter sur `[41,42,43]`.

🔑 **Et le « défaut » §24-47 devient l'outil** : le consensus étant découplé de `robustness_seed`,
toutes les populations sont **déjà** notées sur la même base. Le socle commun dont l'union a
besoin existe — il suffit de l'écrire au lieu de le subir.

**(b) `dp_top_k` ne tronque pas sur le coût qu'on croit.** §24-45 : le bonus block-aware
**écrase** le coût en place (`certus_strat_objectives.py:457`, `cost_raw` contient déjà la
valeur bonifiée) et court **avant** la normalisation. La troncature porte donc sur un coût
bonifié, au carré. À savoir avant d'interpréter tout élargissement de `top_k`.

### ⚖️ L'alternative écartée, et pourquoi elle n'est pas écartée gratuitement

On pourrait rendre la **décision** stable au lieu de mettre en commun des décisions : moyenner
le coût de Phase A sur `m` réalisations avant l'argmin. Bien moins cher.

📏 **Mais §24-28 a mesuré qu'aucun critère connu d'avance ne sélectionne la gagnante** :
`LOCAL_SEARCH` ne produit **rien** à corridor 0 et produit la gagnante **seule** à 0,001, 0,005
et 0,010. Moyenner rendrait **une** stratégie de compromis là où c'est la **diversité** qui paie.

📌 **Cela reste une hypothèse, pas une mesure.** L'expérience est courte : Phase A à coût moyenné
sur `m = 5`, population comparée à l'union des 5. **À mesurer avant de trancher**, pas à décréter.

### A2ter. Combien de graines ? — ne pas poser la valeur

`K = 1 … 8` sur `r75x2 @ 2 nm`, et on trace la **courbe de saturation de l'union** : le `K` utile
est là où elle plafonne. `CLAUDE.md` §19 — *si tu te trouves en train de choisir une valeur, tu
t'es trompé.*

### A1. 🔴 Exposer la graine, et d'abord la RÉPARER (30 min, aucun risque)

Deux lignes dans `certus_strat_ui_state.py:1253-1254` : replier sur `_loaded_config` comme le
font déjà les onze autres clés.

```python
"robustness_seed": int(self._get_float_safe("robustness_seed", 0)
                       or _config_float(getattr(self, "_loaded_config", {}),
                                        "robustness_seed") or 42),
```

🔒 **Règle d'or** : sans clé dans le JSON et sans widget, la valeur reste **42** — chemin
d'avant, au bit. Le test doit **échouer** sur le code d'avant : charger un JSON portant
`robustness_seed = 77` et exiger `collect_params()["robustness_seed"] == 77`.

⚠️ **A1 ne suffit pas et ne doit pas être vendu comme une solution.** Il rend la graine
*réglable*, pas la recherche *robuste*. Un opérateur ne saura pas plus quelle graine choisir
que nous ne le savons.

### A2. 🔑 LE CŒUR — un balayage de réalisations, et une union de candidates

**Le principe, et il découle directement de la mesure** : puisque la réalisation décide quelles
stratégies existent, il faut **plusieurs réalisations en génération**, puis **une notation
commune** de leur union.

```
pour g dans {g1 … gK}      : Phase A + Phase B a la graine g  ->  population P(g)
union                       : P = ∪ P(g), dedupliquee par SIGNATURE de plan (pas par id)
notation commune            : chaque s de P renote sur le MEME jeu de graines de consensus
classement                  : SEEL quantifie, puis rendement (`CLAUDE.md` §22)
```

🔴 **Trois pièges à désamorcer d'avance, tous déjà payés :**

| piège | pourquoi il mord ici | la parade |
|---|---|---|
| **la malédiction du vainqueur** | prendre le min sur K populations biaise le score vers le bas — **+12,9 % mesurés le 15/08** | la notation finale doit être **indépendante** des graines de génération, et le score publié vient d'elle seule |
| **`strategy_id` n'est pas unique** | §24-51 : 21 ids sur 79 portent 2-3 stratégies **différentes**. Dédupliquer par id **fusionnerait des plans distincts** | dédupliquer par la **signature du plan** (la liste des λ par couche), jamais par id |
| **le consensus est découplé** | §24-47 : `consensus_seed_list` gagne sur `base_seed`, donc les K runs rescorent tous sur `[41,42,43]` et **se ressemblent artificiellement** | c'est ici une **vertu** : elle donne gratuitement la notation commune de l'union. Mais il faut l'**écrire** et ne pas la subir |

🔵 **Prédiction à poser avant de coder** : `K = 5` graines de génération doit rendre, sur
`r75x2 @ 2 nm`, **au moins une population non vide** — puisque 77 en donne 547. **Ce qui la
réfuterait** : une union vide, qui voudrait dire que le balayage n'atteint pas la génération.

💰 **Coût** : K × le temps d'un run. À `deep` sur `r75x2`, 114 min × 5 ≈ **9 h 30**. C'est
pourquoi A3 existe.

### A3. Le budget se réalloue, il ne s'ajoute pas

📏 §24-27 et §24-28 l'ont mesuré : **cribler à 10 tirages ne perd rien**, et le levier utile est
la **profondeur sur les finalistes**, pas la population. Donc :

```
generation   K graines x criblage COURT   (n_screen bas, la ou ca ne coute rien)
notation     profonde, sur l'union DEDUPLIQUEE seule
```

⚠️ §24-27 vaut sur **une** graine et **un** empilement, et `n_screen_runs = 25` ne doit **pas**
redescendre à 10 (`CLAUDE.md` §19 : `1/10 = 10 % ≥ 5 %` tue une stratégie sur un seul plantage,
et depuis le correctif 1 elle est aussi perdue comme parent). **À remesurer avant de s'en
servir comme d'un acquis.**

---

## 3. AXE B — le SEEL, monnaie du classement

### B1. Sortir SEEL de l'interface

`CLAUDE.md` §22 : il n'existe que dans `APP_CONTEXT["seel_data"]`, calculé à l'étape 0, et sert
à colorer trois colonnes. **Le banc ne le voit pas** — toutes les mesures de banc sont donc en
unité abstraite, et c'est nous qui recalculons `2·√score` à la main dans chaque sonde. Coût
annoncé : ~1 s, 900 spectres vectorisés.

### B2. 🔴 Appliquer la SECONDE borne, qui est du code mort

`seel_equivalence_half_width` (`certus_strat_ranking.py:589`) implémente
`max(0,05 nm ; 0,06 × SEEL)` — **et n'a aucun appelant en production**, seulement un test.
`rank_key_seel_yield_margin` **reçoit** `score_resolution_rel` et ne s'en sert pas.

📏 **Et on a maintenant le bon chiffre pour la calibrer** : la demi-largeur relative n'est plus
à emprunter au 48 couches. Elle vaut **σ mesuré**, soit **2,59 % sur une différence** à `fast`
sur `r75x2` (`CHANTIER_RATE.md` §3bis). ⚠️ Ce chiffre est **par composant et par profondeur** —
le brancher signifie **le mesurer là où on classe**, pas le recopier.

### B3. Le classement rend sa classe d'équivalence, pas un vainqueur

📏 §24-26 : à N = 150 le top-8 tient dans ~2 σ, et la gagnante alterne d'un run à l'autre.
L'interface doit donc afficher **la classe** — « ces 6 stratégies sont indiscernables, voici
celle qui va le plus souvent au bout » — au lieu d'un premier rang qui est un tirage.

---

## 4. AXE C — faire sortir le livrable

### C1. 🔴 Le plan de surveillance doit être exportable

📏 Trouvé le 2026-08-20 en répondant à *« quelle est la meilleure stratégie ? »* : on savait son
SEEL, son plantage et son nombre de blocs, et **on ne pouvait pas dire à quelles λ surveiller**.
La sonde lisait `b.get("wl")` là où le noyau écrit `block["wavelength"]`
(`certus_strat_robustness.py:2855`), et le champ sortait `[None, …]` **de la bonne longueur** —
donc l'artefact avait l'air complet. Corrigé côté sonde (`2b2901c`).

**Ce qui reste à faire en production** : un export « ordre de fabrication » — par couche, la λ
de contrôle, le mode d'arrêt (POEM / niveau / Rate), et la marge en unités de `A`. C'est le
seul artefact qu'un opérateur de bâti utilise réellement.

### C2. Chaque résultat porte sa configuration effective

Déjà fait côté sondes (§24-7). À porter en production : un run dont on ne sait pas relire les
paramètres n'est comparable à rien, et deux artefacts ont déjà été perdus ainsi.

---

## 5. AXE D — retirer ce qui ment

| levier | état mesuré | action |
|---|---|---|
| `dp_yield_weight` | **n'atteint pas le calcul** — §24-33, bit-identique à `w = 200` sur un bras qui plante à 59,3 % | rebrancher **ou** retirer de l'interface. Pas le laisser |
| `machine_sampling_dd` | **0 des 27 sites d'appel du noyau ne le passe** — `CLAUDE.md` §28 | idem |
| `fast_auto_blocks` | **posé et journalisé, lu par personne** (`certus_strat_ui_worker.py:375`) | le journal annonce un effet inexistant : retirer la ligne de log ou rebrancher |
| `seel_equivalence_half_width` | code testé et **mort** | c'est B2 |

🔑 **La règle générale, et elle vaut plus que la liste** : *un réglage visible qui n'agit pas est
pire qu'un réglage absent.* Il crée une explication fausse pour un résultat, et personne ne va
la vérifier.

---

## 6. AXE E — la queue Rate en repli automatique

📏 Mesuré sur deux composants (`CHANTIER_RATE.md` §16, §20) :

```
r75x2 @ 2 nm  optique seule -> 0 deposable      queue Rate -> fabricable, SEEL 0.686 (deep)
75c   @ 1 nm  optique seule -> 15 deposables    queue Rate -> +19 %, soit 7,4 sigma de COUT
```

> **La queue Rate achète de la faisabilité et la paie en précision. Là où il n'y a rien à
> acheter, il ne reste que la facture.**

**Donc la règle de production** : n'essayer la queue **que** si la population pur optique est
vide ou hors cible de rendement. Jamais par défaut. Et le rapport doit **dire** qu'il est passé
en repli, avec le prix.

⚠️ **Ce qu'il ne faut PAS coder** : un nombre de couches Rate « gratuites ». 📏 Le coude se
déplace de **12 couches** d'une graine à l'autre sur le `75c` (§22 du dossier). La longueur de
queue doit se **chercher**, pas se poser.

🔴 **Et la règle d'exception de 👤 — garder en optique les couches à deux points tournants —
est MESURÉE COMME NUISIBLE** : +8,0 %, soit 3,1 σ, et elle ne gagne nulle part
(`CHANTIER_RATE.md` §21). Ne pas la coder par défaut.

---

## 7. L'ordre d'exécution, et ce que chaque étape décide

| # | action | durée | ce qu'elle décide |
|---|---|---|---|
| **1** | **A1** — réparer la graine | 30 min | 🔴 **bloquant** : sans elle, rien du reste n'est mesurable en production |
| **2** | **C1** — exporter le plan de surveillance | 2 h | le livrable existe. Permet enfin de **vérifier** qu'une stratégie trouvée est celle qu'on croit |
| **3** | **D** — retirer les quatre leviers morts | 3 h | supprime quatre explications fausses avant qu'on ne bâtisse dessus |
| **4** | **B1 + B2** — SEEL dans le banc, seconde borne branchée | 4 h | le classement cesse de départager du bruit |
| **5** | **A2** — le multi-réalisation | 2 j | 🔑 **le cœur**. Rend atteignable la famille que la production ne voit pas |
| **6** | **E** — repli Rate automatique | 1 j | ferme le chantier Rate en le mettant dans le produit |
| **7** | **B3** — l'interface rend la classe | 1 j | ce que l'utilisateur lit cesse d'être un tirage |

🔑 **La règle d'ordre de `CLAUDE.md` §28 s'applique** : *une sonde bon marché qui peut invalider
un gros travail passe avant ce travail.* A1 et C1 coûtent 2 h 30 et conditionnent tout A2.

---

## 8. ⚠️ Ce que ce plan NE prétend PAS

- **Il ne rend pas STRAT plus VRAI.** `CLAUDE.md` §26 reste entier : STRAT n'est validé que
  contre lui-même, et seuls des dépôts réels du dichroïque 48 couches y changeront quelque
  chose. Tout ce plan le rend plus **cohérent** et plus **utilisable**, pas plus juste.
- **Il ne promet pas que le multi-réalisation trouvera toujours mieux.** Il promet de cesser de
  **rater par construction** ce qui existe. Sur `r75x2 @ 2 nm` la différence mesurée est
  *aucune solution* contre *547* — mais c'est un composant, une résolution, deux graines.
- **Il ne fixe aucune valeur nouvelle.** `CLAUDE.md` §19 : si l'on se trouve en train de
  choisir une valeur, c'est qu'on s'est trompé. Les seuls chiffres neufs de ce plan — `K`, la
  demi-largeur relative — sont explicitement **à mesurer**, pas à poser.

---

## 9. 🔒 Les invariants à ne casser sous aucun prétexte

1. **Tout nouveau paramètre est inactif par défaut, et le chemin inactif rend les mêmes bits.**
   Pas « aux tests près » — `CLAUDE.md` §9.
2. **`N` sert à NOTER, jamais à CHOISIR.** Une candidate écartée parce que `N` était petit est
   perdue pour toujours — `DECISIONS_TRANCHEES.md`, enquête 23ter.
3. **Un test ajouté doit ÉCHOUER sur le code d'avant**, sinon il ne prouve rien.
4. **Une chose à la fois, un commit chacune.** Deux modifications simultanées ne s'attribuent
   pas — contrainte C3.
5. **Aucune conclusion sur une seule graine**, sur un composant marginal —
   `CHANTIER_RATE.md` §14.

---

## 10. 🔴🔴 RÉVISION DU 2026-08-20 — LA PORTE N'EST PAS OÙ JE L'AVAIS MISE

👤 avait une intuition : *« seed 77 passe là où seed 42 ne passe pas car ça doit se jouer à
rien. Il y a des paramètres de contraintes par couche, par POEM, par dispersion d'indice. Si on
les diminue un chouia avec seed 42, seed 42 va enfin être débloqué. »*

**L'intuition est juste — il y a bien un seuil binaire, et il décide tout. Mais il n'est pas
dans les contraintes physiques, et la mesure a corrigé trois choses que j'avais écrites.**

### 📏 Ce qui a été mesuré, dans l'ordre

**(1) Ça ne se joue PAS à rien, au niveau du plantage.**

```
graine 42 : 1617 strategies, LE PLUS BAS plantage = 100,00 %
            p05 100 %  mediane 100 %  p95 100 %   sous 20 % : 0 strategie
graine 77 : 2231 strategies, le plus bas = 0,33 %  ·  p05 1,0 %  ·  sous 20 % : 547
```

Desserrer la tolérance de 5 % à 20 % ne débloquerait **rien** : il n'y a aucune stratégie entre
les deux à la graine 42.

**(2) La Phase A est IDENTIQUE aux deux graines.**

```
75 couches — lambda differentes : 0 / 75      couts differents : 0 / 75
cout couche 0 : 0.049995809580197205 dans les DEUX
candidates offertes 152 · interdites 64 · survivantes 86 · min 2
COUCHES ACCULEES : 0 / 75      best_crash_rate par couche : 0,000 % partout
```

🔴 **Cause** : `probe_blocs_vs_plantage.py:287` surcharge `robustness_seed` et **jamais
`phase_a_seed`**, que `collect_params` laisse à 42 faute de widget (§0). **Toutes les
comparaisons de graines du projet sur `r75x2` n'ont donc fait varier que la Phase B.**

✅ Et cela referme une question : la Phase A n'est pas acculée. §24-37 ne s'applique pas ici,
c'est §24-48 — *l'échec naît à l'assemblage alors que la Phase A est parfaitement saine* —
**confirmé sur un second composant.**

**(3) Le plantage d'une stratégie donnée ne dépend pas de la graine.**
122 stratégies sont présentes dans les deux runs : **les 122 ont un plantage identique.**

**(4) 🔑 TOUT L'ÉCART TIENT À UN SEUL GÉNÉRATEUR.**

```
                    total   deposables
graine 42  ELITE        0            0
graine 77  ELITE      743          547
   (aucune autre famille ne rend une seule deposable, aux DEUX graines)
```

### 🔑 LE SEUIL, ET IL NE PEUT PAS ÊTRE DESSERRÉ

`_resolve_elite_nominal_and_target_threshold` (`certus_strat_ranking.py:825`) :

```python
nominal_threshold = RMSE_p95 de la strategie de RANG 10
target_threshold  = nominal_threshold - elite_min_improvement
```

Une candidate n'entre dans le raffinement que si elle **bat la 10ᵉ**. C'est le *« ça se joue à
rien »* de 👤 — situé à l'admission dans ELITE, pas dans les contraintes par couche.

🔴 **Et le réglage est écrêté** (`certus_strat_consensus.py:208`) :

```python
elite_min_improvement = max(0.0, float(params.get("elite_min_improvement", 0.0)))
```

**Le `max(0.0, …)` interdit toute valeur négative : ce paramètre ne peut que DURCIR la porte,
jamais la desserrer.** Il n'existe aujourd'hui aucun moyen d'essayer ce que 👤 propose.

### ✅ CE QUE CETTE MESURE CHANGE DANS LE PLAN — un ordre de grandeur

| avant | après |
|---|---|
| A2 = **K Phases A complètes** (~730 s chacune) puis union | 🟢 **UNE Phase A, partagée**, puis **K passes ELITE** |

La Phase A est déterministe et ne dépend pas de la graine : la diversité vit **entièrement**
dans les rounds ELITE de Phase B. Le coût du multi-réalisation s'effondre.

### 🔵 A0bis — LEVER L'ÉCRÊTAGE, ET MESURER

> ⚠️ **Le titre disait « l'action la plus rentable du plan ». C'est corrigé** : `elite_min_improvement`
> agit sur le seuil de **RMSE**, donc sur **211 rejets (16 %)**, là où la porte de plantage en
> pèse **1116 (84 %)**. A0bis passe **après** A0. Voir le chaînage au §13.


**Ce qu'il faut écrire** : autoriser une porte ELITE **relâchée** — soit `elite_min_improvement`
négatif, soit un `elite_accept_ratio` acceptant une candidate à `k × nominal_threshold` avec
`k > 1`. 🔒 **Inactif par défaut** : à la valeur d'aujourd'hui, chemin d'avant au bit.

🔵 **Prédiction, posée d'avance** : desserrer la porte ELITE à la graine 42 rend **au moins une
stratégie déposable** sur `r75x2 @ 2 nm`, là où le pipeline entier en rend zéro sur 1617.

**Ce qui la réfuterait** : toujours zéro déposable. Cela voudrait dire qu'ELITE, à la graine 42,
ne **génère** pas les bonnes candidates — et non qu'il les rejette. Le diagnostic basculerait
alors du **filtre** vers le **générateur**, et c'est une autre réparation.

⚠️ **Non mesuré à ce jour.** L'hypothèse est désormais précise et testable ; elle ne l'était pas
il y a une heure. Elle ne doit pas être écrite comme un acquis.

### ⚠️ Les trois affirmations que cette section CORRIGE

| ce qui avait été écrit plus haut dans ce plan | ce que la mesure dit |
|---|---|
| « la graine change les choix de Phase A » | 🔴 **faux sur `r75x2`** — `phase_a_seed` y est resté à 42. Vrai sur le 99c (§24-46), pas ici |
| la porte **1** est en Phase A (génération) | elle est en **Phase B**, dans ELITE |
| A2 exige K Phases A | **une seule suffit** |

---

## 11. 🔴 ENQUÊTE ELITE DU 2026-08-20 MATIN — trois hypothèses, trois réfutations

👤 : *« reprends les investigations sur ELITE et SEED »*. Ce qui suit est le compte rendu
honnête : **l'enquête a produit plus de réfutations que d'acquis**, et le §10 ci-dessus doit
être lu avec ces corrections.

### 📏 Ce qui reste ÉTABLI, et seulement cela

```
Phase A                 identique aux 2 graines : 0 lambda differente sur 75, 0 cout different
strategies communes     🔴 RETIRE -- voir l'encadre sous ce bloc, la comparaison etait vide
familles hors ELITE     0 deposable AUX DEUX graines (RATE_L*, SMART_MERGE, SYM, THICKNESS²)
ELITE                   0 strategie (gr.42)  contre  743 dont 547 deposables (gr.77)
graine 42               les 1617 strategies plantent a 100,00 % -- p05, mediane et p95 a 100 %
`origin: "ELITE"`       pose a UN SEUL endroit du code (certus_strat_consensus.py:1017)
```

### 🔴 UNE QUATRIÈME RÉFUTATION, ET CELLE-CI EST DE MA MAIN

> *« les 122 stratégies communes aux deux runs ont un plantage identique au chiffre près »*

📏 **Vérifié le 2026-08-20 : cette comparaison ne compare rien.**

```
paires « communes » par (origine, n_blocs)     : 122
dont les DEUX cotes sont a 100 % de plantage   : 122   (100 %)
paires reellement informatives                 :   0
une « paire » regroupe jusqu'a 12 strategies DIFFERENTES sous une seule cle
```

Les 122 confrontaient **100 % à 100 %**. La clé d'appariement — `(origine, n_blocs)` — est
faible, et la population est saturée. 🔴 **Il n'a donc JAMAIS été montré que le plantage d'une
stratégie est indépendant de la graine.**

✅ **Et l'attente est même l'inverse**, vérifié dans le code : `base_seed`
(`certus_strat_robustness.py:2282`) alimente `_get_cached_sobol_noise`,
`_signal_noise_stream_seed`, `_affine_stream_seed` et `_index_stream_seed`. **La graine pilote
réellement les tirages.**

⚠️ **La cause est la même que pour les trois précédentes** : j'ai lu une grandeur qui ne portait
pas l'information cherchée. Ici la faute est plus grave, parce que l'artefact **portait** ce
qu'il fallait — c'est ma clé d'appariement qui l'a détruit. 🔒 *Un appariement doit être vérifié
sur son pouvoir discriminant AVANT d'être exploité : compter les paires informatives, pas les
paires.*

### 🔴 Les trois hypothèses formulées puis abattues, dans l'ordre

| # | hypothèse | ce qui l'a tuée |
|---|---|---|
| 1 | *la graine change les choix de Phase A* | 📏 Phase A **identique** — `probe_blocs_vs_plantage.py:287` surcharge `robustness_seed` et **jamais `phase_a_seed`**, que `collect_params` fige à 42 faute de widget |
| 2 | *ELITE engendre puis rejette, et le journal le dit* | 🔴 **le journal était TRONQUÉ** : les pilotes de batch capturent tout (`capture_output=True`) et n'en impriment que les 30 dernières lignes. Je lisais une queue et j'ai failli en tirer un mécanisme |
| 3 | *la porte 3 tue les candidates* (`if not isfinite(full_score): continue`) | 📏 **les 1617 scores de la graine 42 sont FINIS**, malgré 100 % de plantage. Le classement remplace l'infini par un repli (`_worst_finite_rmse`), donc un artefact ne porte **que** des scores finis même quand tout plante |

⚠️ **Corollaire du point 3, et il est général** : *un artefact de ce projet ne permet pas de savoir
si la porte de plantage a mordu.* Le « meilleur » score de la graine 42 vaut **SEEL 0,9233** — un
**score de repli**, que `CLAUDE.md` §21 interdit précisément de citer comme une performance.

### ✅ Les deux instruments posés en réponse

**(a) Les pilotes gardent leur journal.** `batch_nuit_2026-08-20.py` écrit désormais la sortie
**complète** dans `reports/journal_<cellule>_<horodatage>.log` avant d'en imprimer la queue.
🔴 Sans cela, toute analyse de journal sur un run de batch porte sur 30 lignes sur des milliers,
**sans que rien ne le signale**.

**(b) ELITE compte ses rejets, porte par porte.** `certus_strat_consensus.py` : trois compteurs
et une ligne de journal par round —

```
[ELITE] Round N: rejets -- halving=A full_rmse=B score_non_fini=C | retenues=D sur E engendrees
```

C'est le **contrôle 4 du §12** de `CLAUDE.md` — *« compte les rejets, ne lis pas le code »* — que
j'ai enfreint trois fois de suite ce matin. 🔒 **Instrumentation pure** : aucun chemin de calcul
ne change, `ruff` propre, 10 tests de cohérence STRAT passent.

### 🔵 La mesure qui tranchera, et elle est bon marché

Rejouer `r75x2 @ 2 nm` en `deep` aux graines **42 et 77** avec l'instrument, et lire les trois
compteurs. **Trois issues, trois diagnostics différents :**

| lecture | ce que ça veut dire | ce qu'il faut réparer |
|---|---|---|
| `engendrees = 0` à la graine 42 | ELITE **ne génère pas** — ses parents ne mènent nulle part | le **générateur**, pas le filtre |
| `engendrees > 0`, `halving` ou `full_rmse` élevé | il génère et **rejette sur le RMSE** | le **seuil**, et l'écrêtage `max(0.0, …)` de la ligne 208 devient le levier |
| `score_non_fini` élevé | il rejette sur le **plantage** | ni l'un ni l'autre : c'est le composant qui ne passe pas à cette graine |

🔴 **Tant que ce compte n'est pas fait, on ne sait pas laquelle de ces trois réparations est la
bonne — et §10 ne doit pas être lu comme si on le savait.**

### 🔒 La règle de méthode que cette matinée impose

📏 Le 2026-08-19, trois conclusions tirées d'une seule graine ont été renversées dans la journée.
Le 2026-08-20, trois hypothèses sur ELITE ont été réfutées en une heure. **La cause commune n'est
pas l'imprudence : c'est d'avoir raisonné sur des artefacts qui ne portaient pas la grandeur en
question.** Phase A n'était pas dans l'artefact, le journal était tronqué, le score était un repli.

> **Avant de formuler un mécanisme, vérifier que la grandeur qui le prouverait EXISTE quelque
> part. Si elle n'existe pas, poser l'instrument est la seule action légitime.**

---

## 12. 🔴 PASSE CONTRADICTOIRE SUR LE PLAN D'ACTION — 2026-08-20

👤 : *« refais une passe contradictoire pour être certain que ton plan d'action est le
meilleur possible »*. Quatre attaques, et deux ont changé le plan.

### ✅ Attaque 1 — « ELITE n'est pas la cause, c'est une conséquence »

**L'objection** : à la graine 42 tout plante à 100 % ; une candidate ELITE planterait aussi.
ELITE à zéro ne serait alors qu'un symptôme, et le viser serait soigner la fièvre.

📏 **Réfutée par le comptage par famille :**

```
graine 42   ELITE          0 strategies      0 deposables   plantage min 100,00 %
            hors ELITE  1617                 0              100,00 %
graine 77   ELITE        743               547                0,33 %
            hors ELITE  1488                 0              100,00 %
```

🔑 **Aux DEUX graines, la population hors ELITE est ENTIÈREMENT à 100 %** — 1617 et 1488
stratégies, pas une en dessous. À la graine 77, ELITE a donc **créé** 547 déposables à partir
d'un vivier intégralement mort. Ce n'est pas un symptôme : **c'est le seul étage qui produise
quoi que ce soit de viable sur ce composant à 2 nm.**

> **Toute la fabricabilité de `r75x2` à 2 nm repose sur l'étage de raffinement ELITE.** La
> recherche ordinaire — DP, minage, `SYM`, `SMART_MERGE`, `RATE_L` — n'y contribue rien.

### 🔄 Attaque 2 — « le diagnostic coûte 120 min, `premium` en coûterait 60 »

**Fondée en partie.** À `premium` la graine 42 rend aussi 0 déposable à 2 nm, donc le phénomène
se reproduit, et `elite_rounds = 2` suffit à rendre `stop_on_no_gain` testable.

🔴 **Mais elle est écartée** : la référence à laquelle on compare — les 518 déposables de la
graine 77 — n'existe qu'en `deep`. Diagnostiquer à `premium` et comparer à `deep` ferait varier
deux choses. **Une heure économisée contre une comparaison boiteuse : mauvais marché.**

### 🔄 Attaque 3 — « le test de transfert repose sur un outil qui n'existe pas »

> 🔴 **ET L'OUTIL CONSTRUIT EN RÉPONSE EST EN PANNE, AVEC UNE PANNE MAL LOCALISÉE.**
> `REPRENDRE_ICI.md` §1 l'attribue à une `full_dynamics_grid` vide. 📏 Réfuté le 2026-08-20 au
> soir, par le code : la grandeur n'est déréférencée qu'à **un seul endroit de tout le dépôt**,
> `certus/core/certus_strat_robustness.py:2513`, dans un bloc de **journalisation** gardé par
> `theory_dyn >= 0.0` — grille vide ⇒ `-1.0` ⇒ aucune des deux branches. Et la **Phase B de
> production tourne toujours avec elle vide** : `minimized_context`
> (`certus/workers/certus_strat_workers_pipeline.py:146`) ne porte pas la clé, elle part
> séparément en `dyn_grid=` et n'est jamais transmise à `_parallel_block_worker`. Le contexte que
> la sonde capture **est** celui de la production. La cause de la panne reste donc **non
> localisée** — voir §15.


**Fondée, et elle réordonne le plan.** Le run à la graine 77 vaut surtout pour les **plans de
surveillance** des 518 déposables — mais les exploiter demande un outil de **re-notation** qui
n'est pas écrit. Le construire après coup, c'est risquer de découvrir qu'il est difficile alors
que 3 h de machine sont déjà dépensées.

✅ **Correctif** : l'outil se construit **pendant** que le diagnostic tourne. Il ne demande pas
la machine, et le point d'injection existe déjà (`run_final_simulation_block` reçoit
`opti_results["all_strategies"]`, ce dont le worker se sert pour les `inherited_strategies`).

### 🔄 Attaque 4 — « pourquoi mettre 5 h de machine en file avant d'avoir lu la première ? »

**Fondée.** Le batch prévoyait deux cellules enchaînées, 300 min. Or la seconde n'a de sens que
selon ce que dit la première : si les compteurs désignent le récit B, ce sont les paramètres de
bruit qu'il faut relâcher, et les plans de la graine 77 attendront.

✅ **Correctif : le batch tombe à UNE cellule.** On lit, puis on décide.

### 🔵 LE PLAN D'ACTION RÉVISÉ

| # | action | machine | ce qu'elle décide |
|---|---|---|---|
| **1** | `r75x2 @ 2 nm deep s042`, **réglages d'origine**, instrumenté | ~120 min | **où ELITE meurt** — la seule chose qui départage les récits A et B |
| **2** | *pendant le run* : écrire l'outil de **re-notation** d'un plan sous des paramètres donnés | aucune | rend exploitables les plans, et le test de transfert possible |
| **3** | selon les compteurs : élargir ELITE **ou** relâcher bruit et corridor **en génération** | ~120 min | la première tentative de traitement |
| **4** | juger au **nominal** ce que la génération relâchée a trouvé | ~15 min | 🔒 la garde qui rend l'exercice honnête |

🔒 **La garde, et elle ne se négocie pas** : relâcher le bruit ou le corridor est légitime pour
**ENGENDRER**, jamais pour **NOTER**. Sinon on obtient un SEEL flatteur qui ne décrit aucune
machine. C'est la forme exacte de l'invariant `N` sert à noter, jamais à choisir.

### 🔴 DERNIÈRE PASSE — deux défauts trouvés DANS L'INSTRUMENT, avant de dépenser 120 min

👤 : *« une dernière passe sur les diagnostics et plan révisé ? »*. Elle a payé.

**(a) Les compteurs n'auraient rien émis dans le cas le plus probable.** La ligne de journal
était placée **après** l'évaluation complète. Or si toutes les candidates sont rejetées au
*successive halving*, le round sort **avant**, sur `if not candidates_to_eval` — et c'est
précisément le scénario attendu à la graine 42. ✅ Les **trois** sorties du round sont désormais
instrumentées, et chacune se nomme : `skipped` · `sortie=HALVING` · `sortie=COMPLETE`.

**(b) `rej_halving` compte des rejets qui n'éliminent pas toujours.** Si un étage rejette
**tout**, la boucle sort sur `break` sans réassigner `candidates_to_eval`, qui garde donc
l'ensemble de l'étage précédent — et ces candidates passent quand même en évaluation complète.
C'est un filet de sécurité du code existant, pas un défaut, **mais il faut le savoir pour lire
le compteur** : un `halving` élevé ne signifie pas « autant de candidates perdues ». Consigné
dans le code.

**(c) Une erreur de vocabulaire dans le batch, corrigée.** Il annonçait *« `par_swing = 0` →
pur optique, aucune variante Rate »*. 📏 Faux : l'artefact de référence porte **27 familles
`RATE_*` et 1198 stratégies sur 1617**, parce que `allow_rate` vaut `True` dans le JSON du
composant. `par_swing = 0` ne désactive que le balayage de **queue**, le placement par swing et
les jeux de couches.

### 🔒 Le contrôle C1 est intégré au batch

Trois fichiers ont changé depuis le run de référence : les compteurs (instrumentation pure), le
routage des treize clés (inerte sans clé JSON), et la clé `wavelength` de la sonde (artefact
seulement). **Aucun ne doit toucher un chiffre.** Le run doit donc rendre exactement :

```
1617 strategies · 0 deposable · plantage minimal 100,00 % · ELITE 0 strategie
```

🔴 **Tout écart signifie qu'une de ces modifications a fui dans le calcul, et le diagnostic est
à jeter avant même d'être lu.**

### 🔬 PASSE ULTRA-PRÉCISE — quatre moyens croisés, trois défauts de plus

👤 : *« c'est le genre de bug qu'il faut absolument éviter »*. Quatre contrôles indépendants.

| moyen | ce qu'il a donné |
|---|---|
| **1. énumération AST des sorties** de la boucle `elite_round` | **6 sorties**, toutes instrumentées et nommées |
| **2. analyse de dominance** — un compteur peut-il être lu avant d'être créé ? | 🟢 aucun ; et le remise à zéro est bien **par round**, pas cumulée |
| **3. exécution réelle** sur le 35c en `fast` | **10 lignes de compteurs émises**, gates distingués. `generated` y vaut **120** (le plafond) dans 6 rounds sur 10, jamais 9 |
| **4. inventaire des écritures** dans `reports/` | 🔴 **13 sondes sur 15 sans garde d'écrasement** |

### 🔴 LE DÉFAUT LE PLUS GRAVE — le run allait DÉTRUIRE sa propre référence

Le diagnostic prévu produisait exactement `blocs_vs_plantage_r75x2_deep_s042.json` — **le nom de
la référence de 8,26 Mo servant au contrôle C1**. Il l'aurait écrasée **en silence**, détruisant
la mesure à laquelle on voulait comparer. `reports/` n'est protégé par rien : 193 fichiers sur
226 sont irrécupérables, et ce dépôt a déjà perdu des artefacts ainsi (*« les coupures 28-52 ont
été perdues »*).

⚠️ **Et le contrôle 3 a failli le refaire dans la même heure** : le run de vérification sur le
35c a été lancé **avant** que la garde ne soit posée, et allait écraser **215 Ko** du 19 août.
Sauvé à la main, de justesse.

✅ **Correctif systémique** : `scripts/_artefact.py`, une aide partagée qui **renomme plutôt que
d'écraser** — un run de deux heures qui aboutit ne doit pas perdre son résultat parce qu'un
homonyme existe — et qui **dit** la collision au lieu de la taire. **7 tests**, qui échouent sur
le code d'avant (le module n'existait pas).

### 🔑 ET LE DIAGNOSTIC EST DEVENU AUTO-INTERPRÉTABLE

En cherchant à exercer la branche `sortie=HALVING`, l'analyse du flot a établi qu'elle a un sens
**exact** : `candidates_to_eval` part avec toutes les candidates ; soit `stage_results` est vide
et on sort **sans réassigner**, soit `keep_count ≥ 1` et la tranche est **non vide**. Donc
`candidates_to_eval` est vide **si et seulement si** `elite_candidates` l'était.

```
sortie=HALVING   ... sur 0 engendrees   ->  le GENERATEUR est a sec       (recit A)
sortie=COMPLETE   score_non_fini eleve  ->  les candidates PLANTENT       (recit B)
sortie=COMPLETE   full_rmse eleve       ->  le SEUIL rejette              (recit A)
skipped                                 ->  seuil non fini, autre cause
```

**Les quatre lectures mènent à quatre réparations différentes, et aucune n'est ambiguë.**

⚠️ **Réserve honnête** : la branche `sortie=HALVING` est vérifiée **statiquement** et par analyse
de flot, **pas dynamiquement** — le contrôle sur le 35c ne l'a pas exercée, puisqu'elle demande
un générateur à sec. Elle le sera par le diagnostic lui-même.

### ⚠️ Ce que cette passe n'a PAS pu attaquer

Le récit A et le récit B restent **tous deux vivants**. Le comptage par famille montre qu'ELITE
est le bon endroit où regarder ; il ne dit pas s'il échoue faute d'engendrer ou faute d'accepter.
**Aucune des deux réparations ne doit être écrite comme probable avant les compteurs.**

---

## 13. 🟢🟢 LE DIAGNOSTIC A TRANCHÉ — 84 % des candidates meurent du PLANTAGE

`reports/journal_1_diagnostic_s042_20260820_120135.log`, **107,4 min**, 15 887 lignes.
`r75x2 @ 2 nm`, `deep`, graine 42, **réglages d'origine**.

### ✅ Le contrôle C1 passe exactement

```
REFERENCE 19/08     1617 strategies · 0 deposable · crash_min 100,00 % · ELITE 0
DIAGNOSTIC 20/08    1617 strategies · 0 deposable · crash_min 100,00 % · ELITE 0
```

Les **treize clés routées**, les compteurs et le correctif `wavelength` sont donc **inertes**,
comme la règle d'or l'exige. Et la garde anti-écrasement a fonctionné : le nouvel artefact a
pris un suffixe horodaté, **la référence de 8,26 Mo est intacte**.

### 📏 Les compteurs

```
46 rounds ELITE, tous `sortie=COMPLETE`
  4226 candidates ENGENDREES (92 par round ; plafond de 120 atteint dans 30 rounds sur 46)
  1327 evaluees en entier
     0 RETENUES

  rejets au halving        1368
  rejets sur le RMSE        211   (16 % des evaluees)
  rejets sur le PLANTAGE   1116   (84 % des evaluees)
```

### 🔴 LE RÉCIT A EST RÉFUTÉ

> *« ELITE est trop timide : `span = 1`, et un round stérile arrête tout. »*

**Le générateur n'est pas à sec.** Il atteint son plafond de 120 dans **30 rounds sur 46**, et
la sortie `HALVING` — qui signalerait un générateur vide — **n'a jamais été empruntée**.
Élargir `elite_wl_neighbor_span` ou `elite_max_candidates` ne servirait à rien.

⚠️ **Le `generated=9` qui fondait ce récit était un artefact du journal tronqué** : c'était la
dernière ronde du dernier compteur de blocs, lue dans une queue de 30 lignes. C'est la
cinquième fois de la journée qu'une conclusion vient d'une grandeur mal lue, et la deuxième
fois que la troncature du journal en est la cause.

### 🟢 LE RÉCIT B EST CONFIRMÉ — et c'est l'hypothèse de 👤

> 👤 : *« il faut peut-être relâcher des paramètres de contrôle optique (bruit, variation
> d'indice) pour récupérer les strats de seed 77 »*

📏 **84 % des candidates évaluées en entier sont tuées par le PLANTAGE**, contre 16 % par le
RMSE. Elles sont **trouvées**, elles sont **spectralement bonnes**, et la porte de plantage les
élimine.

### 🔑🔑 LES 84 % **SONT** LA PORTE DE PLANTAGE — chaînage établi le 2026-08-20 au soir

Le diagnostic disait « le plantage » sans nommer le code. Il est nommé, et il change la structure
du plan :

```
_crash_gate_rejects   (certus_strat_robustness.py:2693)  ->  final_score = float("inf")
                                                        ->  robustness_score = inf
ELITE : not np.isfinite(full_score)  (certus_strat_consensus.py:792)  ->  rej_score_non_fini
```

🔑 **Donc §13 et A0 ne sont pas deux actions, c'est la même.** A0 cesse d'être « le meilleur
rapport valeur/risque du plan » pour devenir **le traitement direct de la cause diagnostiquée** :
`crash_gate_confidence` remplace exactement la comparaison qui pose cet infini.

📏 **Et le poids des deux portes est mesuré** : sur 1327 candidates évaluées en entier,
**1116 (84 %) meurent de la porte de plantage** et **211 (16 %) du seuil de RMSE**. Or
`elite_min_improvement` — l'objet d'A0bis — agit sur `target_threshold`, donc sur les **211**.
**A0 passe avant A0bis, par le poids mesuré.**

🔴 **Ce qui manque encore pour choisir, et l'instrument est posé** : à quel **taux** plantent ces
1116 ? Si elles sont juste au-dessus de la tolérance de 5 %, une borne de confiance les récupère
**sans relâcher aucune physique**. Si elles sont à 100 %, aucun réglage de porte ne les sauve et
le relâchement est la seule voie. La grandeur était **dans `full_res` et jetée** — voir §15.

### 🔑 LE MÉCANISME, ET IL EXPLIQUE POURQUOI RELÂCHER PEUT MARCHER

ELITE est une recherche **locale** : λ ± 1 nm autour de ses parents. Toute candidate qui plante
est rejetée (`if not np.isfinite(full_score): continue`), donc **la recherche ne peut jamais
TRAVERSER une vallée qui plante pour atteindre une région saine au-delà**. À la graine 42 elle
est enfermée dans une région où tout plante.

📌 Détail confirmant : les 46 lignes disent toutes `Round 1`. Avec zéro retenue,
`elite_stop_on_no_gain` coupe après le premier round **à chaque fois** — les rounds 2 et 3 de
`deep` ne tournent jamais. Ce n'est pas la cause, mais cela **aggrave** l'enfermement.

> **La porte de plantage n'est pas seulement un filtre de sortie : à l'intérieur d'ELITE, elle
> est un MUR qui empêche la recherche de se déplacer.**

### 🔵 CE QUI SUIT, ET LA GARDE QUI LE REND HONNÊTE

Relâcher `index_corridor` et `poem_anchor_noise` **pendant la recherche** doit permettre à ELITE
d'accepter des candidates intermédiaires et de se déplacer. 🔒 **Puis on juge au NOMINAL** —
avec `probe_renoter.py`, écrit pour cela.

🔴 **Et il faut dire d'avance ce qui ferait échouer cette voie** : si les stratégies trouvées
sous relâchement plantent **toutes** une fois rejugées au nominal, alors la région saine
n'existe pas à cette graine, et le relâchement n'aura fait que déplacer le mur. **Ce n'est pas
un détail de protocole : c'est le résultat possible le plus probable après celui qu'on espère.**

---

## 14. 🔴 RETIRÉ — « LE PLANTAGE EST UNE PROPRIÉTÉ DE LA STRATÉGIE » (talon conservé)

> 🔴 **CETTE SECTION EST RETIRÉE COMME CONCLUSION, et conservée comme talon.** Elle repose
> entièrement sur `probe_renoter.py`, dont [`REPRENDRE_ICI.md`](REPRENDRE_ICI.md) §2 invalide
> **toutes** les sorties : l'outil ne reproduit pas son propre point fixe. Le 8/8 à 100 %
> n'est donc pas informatif, et **il n'a jamais été montré qu'un taux de plantage soit une
> propriété de la stratégie**.
>
> ⚠️ **La contradiction a vécu deux jours entre deux documents**, et
> `scripts/coherence_md.py` ne pouvait pas la voir : il rapproche un mot et un nombre, il ne
> compare pas deux thèses. C'est la limite exacte de son pouvoir de détection, et il faut la
> connaître avant de s'appuyer sur son « 0 point à instruire ».
>
> 🟢 **Ce qui reste vrai et vaut d'être gardé** : la leçon de méthode du faux départ — le champ
> `parametres_de_notation`, ajouté le matin même, a démasqué une comparaison à trois variables
> changées, le jour de sa pose. Et le §15 établit par ailleurs que **l'export des 12 plans est
> exact**, donc la prémisse matérielle de ce test était saine ; c'est l'instrument qui ne l'était
> pas.

### Le texte d'origine — LE PLANTAGE EST UNE PROPRIÉTÉ DE LA STRATÉGIE, PAS DU TIRAGE

`reports/renotation_r75x2_s077_plans_transfert_s042_20260820_131529.json`.

Tout l'espoir de récupérer, à la graine 42, les stratégies que la graine 77 trouve reposait sur
**une prémisse jamais vérifiée** : que le taux de plantage soit une propriété de la stratégie.
Elle l'est.

### 📏 Le test, et il est bon marché

On prend les **8 meilleures stratégies pur optique de la graine 42** — toutes à 100 % de
plantage — et on les rejoue **sous la graine 77**, à conditions appariées.

```
graine 77 · N = 300 · resolution 2,0 nm · corridor 0,005

  les 8 mesurees a 100,00 % sous la graine 42
  ->  100,00 % sous la graine 77.  Les huit. Exactement.
```

⚠️ Les SEEL affichés (0,91 à 1,10) sont des **scores de repli** : ces stratégies plantent. §21
interdit de les citer comme des performances.

🔑 **Conséquence** : les 518 stratégies déposables de la graine 77 doivent rester déposables
sous la graine 42. **Elles ne manquent pas à l'espace de recherche — elles manquent à la
RECHERCHE.** C'est un problème de recherche, pas de physique, et un problème de recherche se
répare.

### 🔴 LE FAUX DÉPART, ET CE QU'IL A COÛTÉ D'ÉVITER

Le premier essai de ce test a rendu `38 % · 40 % · 40 % · 64 % · 74 % · 98 % · 100 % · 100 %` —
c'est-à-dire l'exact contraire, et un renversement majeur.

**Il était faux.** L'outil chargeait le JSON du composant tel quel, et `r75x2` est **nativement à
1 nm**. On comparait donc une référence mesurée à **2 nm, N = 300** à une re-notation faite à
**1 nm, N = 50** — trois variables changées à la fois, sur le composant même dont la résolution
décide de tout (277 déposables à 1 nm, **zéro** à 2 nm).

🟢 **C'est le champ `parametres_de_notation` qui l'a démasqué**, ajouté le matin même au nom de
§24-7 — *« un run qui ne consigne pas sa configuration n'est comparable à rien »*. Il portait
`monochromator_resolution_nm = 1.0` en toutes lettres.

> **La discipline de consigner la configuration a payé son coût le jour même où elle a été
> posée.** Sans elle, une conclusion majeure et fausse partait dans les documents.

L'outil accepte désormais des surcharges `clé=valeur`, avec ce récit dans sa docstring.

### ⚠️ CE QUI EST PROUVÉ, ET CE QUI RESTE INFÉRÉ

| | |
|---|---|
| 🟢 **prouvé** | une stratégie qui plante **totalement** à une graine plante totalement à l'autre |
| 🟠 **inféré** | qu'une stratégie **bonne** reste bonne. Un seul sens a été testé |

L'asymétrie est réelle : une stratégie à 100 % est robustement mauvaise, c'est le cas facile.
Une stratégie à 1 % plante 3 fois sur 300, c'est plus délicat. L'arithmétique tient — pour
passer de 3 plantages à 300 il faudrait que le vrai taux soit à la fois 1 % et 100 % — mais
c'est un raisonnement, pas une mesure.

### 🔑 UNE DISTINCTION À NE PAS PERDRE

Même réussi, le transfert donne **deux choses différentes** :

| | |
|---|---|
| 🟢 **des stratégies qui marchent à la graine 42** | avec leurs λ par bloc, exploitables en atelier |
| 🟠 **une production qui sait les TROUVER** | ce n'est pas la même chose, et c'est le but réel de 👤 |

Le transfert livre les premières. La seconde reste un chantier — mais **avec une cible connue** :
on pourra mesurer pourquoi ELITE les rate à la graine 42, et les lui injecter comme parents pour
vérifier qu'il sait alors les raffiner.

🔴 **Le scénario défavorable qui subsiste** : les stratégies tiennent, mais **rien dans le code
exposé ne permet de les atteindre** à la graine 42 — le tirage des parents d'ELITE étant
arbitraire quand tout plante. On aurait alors les stratégies sans le moyen de les redécouvrir,
et il faudrait **ajouter** un mécanisme d'injection. Ce ne serait pas un échec, mais un
développement, pas un réglage.

---

## 15. 🟢 CE QUE LA LECTURE D'ARTEFACTS DU 2026-08-20 AU SOIR ÉTABLIT — sans une seconde de machine

**Portée : `r75x2` exclusivement**, à 2 nm, `deep`. C'est l'étalon courant. Tout ci-dessous vient
de la lecture du **code** et des **artefacts déjà au disque** — aucun run, aucune mesure neuve.

### 15.1 🔑 Hors ELITE, il n'y a rien — et c'est vrai AUX DEUX GRAINES

```
graine 77   hors ELITE  1488 strategies   0 deposable   crash mediane 100,00 %
            ELITE        743 strategies  547 deposables
graine 42   hors ELITE  1617 strategies   0 deposable   crash mediane 100,00 %
            ELITE          0 strategie     0
```

L'attaque 1 du §12 concluait cela pour la graine 42 par comptage de familles ; c'est désormais
établi **des deux côtés**. Toute la fabricabilité de ce composant à 2 nm passe par l'étage ELITE,
et il n'y a aucune voie de contournement dans les générateurs existants.

### 15.2 ✅ L'export des 12 plans est EXACT — la prémisse du §14 était saine

Appariement de `reports/plans/plans_s077_vers_s042.json` à
`reports/blocs_vs_plantage_r75x2_deep_s077_20260820_160340.json` par **signature exacte de blocs**
`(start, end, wavelength)` :

```
12 plans -> 12 apparies, un candidat UNIQUE chacun, 0 introuvable
crash et SEEL de la reference retrouves exactement, ceux que le NOM du plan porte
    0,67 % a 1,33 %  ·  SEEL 0,5692 a 0,5731
```

Et les **547 déposables sont toutes `origine = ELITE`**, toutes `resolution_nm = 2.0`,
`resolution_noise_factor = 1.0` : **aucune variante Rate, aucune variante de fente**. L'export n'a
donc perdu **aucun** drapeau — l'hypothèse « l'export a écrit les blocs d'un parent optique » est
**réfutée**.

### 15.3 🔴 LA FALAISE À 685 nm EXISTE, ET CE N'EST PAS LA CAUSE — piste à ne PAS payer

Les 12 gagnantes partagent le préfixe `(0,8)@450 · (8,25)@610 · (25,33)@616`, et surveillent
toutes la couche 35 à **685 nm**. 📏 Or la graine 42 ne propose **jamais** 685 nm, à **aucune
couche** de ses 1617 stratégies : elle campe à **686 nm**, avec 1156 stratégies. Un pas de grille.

🔴 **Et pourtant « forcer 685 nm » ne marcherait pas.** Ventilé par générateur, graine 77,
couche 35 :

| λ | générateur | n | crash min | médiane | déposables |
|---|---|---|---|---|---|
| **685** | ELITE | 740 | 0,33 % | 1,33 % | **544 (73,5 %)** |
| **685** | non-ELITE | 711 | **100 %** | 100 % | **0** |
| 686 | ELITE | 3 | 1,00 % | 1,67 % | **3 (100 %)** |
| 686 | non-ELITE | 228 | 100 % | 100 % | 0 |

**685 nm n'est ni suffisante** — 711 stratégies y plantent toutes — **ni nécessaire** : les 3 ELITE
à 686 nm sont déposables. La concentration à 685 nm est un **effet de sélection** : ELITE raffine
autour de ses parents, il s'est donc empilé là où ça marchait déjà. Le discriminant est **le
générateur, pas la longueur d'onde**, et retourner cette flèche est l'erreur que ce dépôt paie
depuis le §4quinquies de [`CHANTIER_PREDICTIBILITE.md`](CHANTIER_PREDICTIBILITE.md).

### 15.4 ✅ SIX causes candidates de la panne de `probe_renoter.py`, ÉLIMINÉES

| candidate | verdict |
|---|---|
| `full_dynamics_grid` vide | 🔴 **inerte** — un seul déréférencement, `robustness.py:2513`, journalisation gardée par `theory_dyn >= 0.0`. La production tourne avec elle vide |
| erreur d'unité sur `crash_rate` | ✅ non — le noyau la formate en `:.1%`, c'est une fraction ; le `100 ×` de la sonde est correct |
| plans malformés | ✅ non — les 9 à 11 blocs pavent `[0,75)` exactement, 0 trou, 0 chevauchement, `end` exclusif comme le noyau le lit |
| chemin de **surcharge** de résolution | ✅ non — `reports/plans/config_r75x2_natif_2nm.json` écrit 2 nm **dans la configuration**, donc Phase A et contexte entiers à 2 nm : marge **bit-identique** aux runs surchargés (`-1752,8038794937806`) |
| `expand_variants=False` | ✅ non — le garde ne couvre que la **génération** de variantes ; la base reste, dit le code, « bit-identical to a no-search run » |
| une clé perdue sur l'objet `strategy` | ✅ non — le noyau n'y lit que `blocks`, `strategy_id`, `monochromator_resolution_nm`, `rate_layers`, `slit_profile`, `witness_reset_layers`, `l0`. Seules les deux dernières manquent à l'injection, et se replient sans effet puisque les plans pavent tout l'empilement |

⚠️ **Deux lectures de la session précédente sont retirées, et deux des miennes aussi** : la marge
identique au seizième chiffre entre les 12 n'a rien d'impossible — c'est le comportement
**documenté** à `robustness.py:2805`, les 12 partageant leur préfixe et donc la physique de la
couche 35 ; et `n_layers_below_2A = 153` somme sur **trois causes**, ce n'est pas un index de
couche sur un empilement de 75.

🔴 **La cause de la panne reste donc NON LOCALISÉE.** Et la grandeur qui la trancherait — le
`params` effectif **complet** des deux chemins — n'est dans aucun artefact : la référence consigne
11 clés de `config`, les re-notations 11 clés de `parametres_de_notation`.

### 15.5 ✅ L'INSTRUMENT POSÉ — `[ELITE-WL]`, deux lectures pour un seul run

`certus/core/certus_strat_consensus.py`. **Instrumentation pure** : aucun chemin de calcul ne
change. Chaque round ELITE journalise désormais, à **toutes** ses sorties :

```
[ELITE-WL] Round N exit=... generated                 685:12 686:340 ...
[ELITE-WL] Round N exit=... rejected_halving          ...
[ELITE-WL] Round N exit=... rejected_full_rmse        ...
[ELITE-WL] Round N exit=... rejected_score_non_fini   ...
[ELITE-WL] Round N exit=... reject_crash_bands        score_non_fini/100%:1116 score_non_fini/5-10%:7 ...
```

**Ce que chaque lecture décide, et il n'y a pas d'ambiguïté :**

| lecture | ce que ça veut dire | ce qu'il faut réparer |
|---|---|---|
| la λ gagnante **absente** des engendrées | ELITE ne regarde jamais là | les **parents** |
| la λ **présente** et dans un rejet | ELITE regarde et jette | la **porte** |
| bandes de plantage **juste au-dessus de 5 %** | 🟢 `crash_gate_confidence` les récupère, **sans relâcher aucune physique** | la **règle de décision** |
| bandes **à 100 %** | 🔴 aucun réglage de porte ne les sauve | seul le relâchement, et le **juge au nominal** doit exister d'abord |

⚠️ **Règle de comptage, à connaître pour lire le journal** : une candidate compte **une fois par λ
distincte** de ses blocs, donc les comptes somment à **plus** que le nombre de candidates. Un
compte dit « combien de candidates ont utilisé cette λ », jamais « combien de blocs ».

🔒 **34 tests**, qui échouent sur le code d'avant — `git show HEAD:...` puis `grep -c` rend **0**
pour les trois symboles. Suite complète **`2520 passed, 5 skipped`**, `ruff` propre.

### 15.6 🔵 L'ORDRE RÉVISÉ — il remplace celui du §7 et celui du §12

Le §7 précède les §10 à §13 et ne connaît donc pas le diagnostic. **Cet ordre-ci fait foi.**

| # | action | machine | ce qu'elle décide |
|---|---|---|---|
| **0** | ✅ l'instrument `[ELITE-WL]` — **fait** | 0 | — |
| **1** | `r75x2 @ 2 nm deep s042`, réglages d'origine, **instrumenté** | ~115 min | 🔑 **porte à confiance, ou relâchement ?** La seule chose qui départage, et elle départage sans ambiguïté |
| **2** | si les bandes le permettent : `crash_gate_confidence = 0.95` — **une ligne de JSON**, zéro code | ~115 min | le seul levier qui n'exige **aucun** re-jugement au nominal |
| **3** | sinon : relâcher bruit et corridor **en génération seule** (👤) | ~115 min | 🔒 mais le **juge au nominal** doit exister avant, sinon la mesure ne vaut rien |
| **4** | `elite_stop_on_no_gain = false` — routé, gratuit | ~115 min | à 0 retenue, le round 1 coupe tout : les rounds 2-3 de `deep` ne tournent **jamais**. Espérance faible, coût nul |
| **5** | A0bis — l'écrêtage `max(0.0, …)` de `elite_min_improvement` levé | ~115 min | les **211 rejets de RMSE (16 %)**, après les 1116 (84 %) |

🔒 **La garde ne se négocie pas** : relâcher est légitime pour **ENGENDRER**, jamais pour **NOTER**.
Sinon on obtient un SEEL flatteur qui ne décrit aucune machine.

🔴 **Et ce qu'il faut dire d'avance sur l'étape 3** : si les stratégies trouvées sous relâchement
plantent **toutes** une fois rejugées au nominal, la région saine n'existe pas à cette graine et le
relâchement n'aura fait que déplacer le mur. **C'est le résultat le plus probable après celui
qu'on espère.**

### 15.7 ⚠️ Ce que cette session N'a PAS établi

- **La cause de la panne de `probe_renoter.py`.** Six candidates éliminées, aucune trouvée.
- **Pourquoi la graine 42 ne propose jamais 685 nm.** La Phase A est identique aux deux graines
  (§10) et la DP est déterministe ; l'écart naît donc en aval, dans le criblage stochastique et la
  cascade de parents hérités. **Non mesuré.**
- **Si les 1116 rejets sont marginaux ou totaux.** C'est l'objet de l'étape 1.
- **Rien sur un autre composant.** Tout ci-dessus est `r75x2` à 2 nm, `deep`.
