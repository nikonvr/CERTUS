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
