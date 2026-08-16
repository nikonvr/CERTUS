# 25. 🔴 MULTIPLE TESTGLASS METHODOLOGY — le programme annoncé le 2026-08-14

> Extrait de `CLAUDE.md` le 2026-08-16. Ce contenu **fait autorite** ;
> `CLAUDE.md` n'en garde qu'un renvoi. 🔑 **Un fait, un seul endroit** — si tu corriges
> quelque chose ici, ne le recopie pas ailleurs, mets un lien.

---


> 👤 *« comme tu le vois sur le 99c, il devient quasi impossible de faire du monitoring
> optique et du POEM sur des filtres à plus de 50 couches. Mon idée est la suivante :
> découper le filtre en deux parties, testglass 1 et testglass 2, en remettant un verre nu
> après une cinquantaine de couches. Les deux monitorings sont indépendants, mais le verre
> avec le dépôt total bénéficie des deux coatings successifs. »*

> 👤 *« pour savoir quand changer de témoin, je veux une méthode très générale, et qui fonctionne bien
> au-delà du cas particulier de ce 99c. Cela pourrait être basé sur un nombre de couches
> raisonnable, un SEEL qui se dégrade, ou autre, mais tout cela est à tester de manière
> systématisée et automatisée. On comprendra peut-être a posteriori ! »*

### 25.1. Le constat qui ouvre le chantier

🔴 **ÉTABLI LE 2026-08-15, ET C'EST PIRE QUE « MOINS BON » : SUR LE 99 COUCHES, RIEN NE
SURVIT.** La référence sans changement de témoin rend **`crash_rate = 100 %`**, en PREMIUM comme en FAST.
Or une stratégie dont le plantage dépasse 5 % reçoit un score **infini** et **sort du
classement** (`certus_strat_robustness.py:2125`). Les 785 candidates en sont donc sorties, et
ce qui revient vient du **repli sans survivant** (`:1152-1166`) : le solveur reclasse les
éliminées par risque croissant et rend la moins mauvaise avec la **pire RMSE finie**.

| | |
|---|---|
| 🔴 **`SEEL = 0,86 nm` n'est PAS un score de robustesse** | C'est le chiffre le moins mauvais parmi des stratégies qui **échouent toutes**. Ne le cite jamais comme une erreur par couche atteignable. |
| **Ce qui reste vrai, et c'est le vrai constat** | **Environ 75 couches sur 99 doivent passer en mode Rate** ; le suivi optique continu à λ₀ rend **100 % de plantages** (`CRASH_LEVEL_UNREACHABLE`). |
| **À comparer avec** | 48c : **0,17 nm à 0,0 % de plantage**. Là, le chiffre veut dire quelque chose. |

⚠️ **C'est le défaut qu'A26 annonce depuis le 2026-08-13** — *« score = pire RMSE finie, PAS
un score de robustesse »* — tombé sur le composant vitrine sans que personne le voie, parce
que le rapport d'origine **ne consignait pas le taux de plantage**. Tant qu'A26 n'est pas
faite : **lis le `crash_rate` avant tout score.**
Deux causes, toutes deux physiques et non contournables par un meilleur solveur :

- les **cavités demi-onde** ont un swing optique **nul** pendant leur dépôt ;
- les **miroirs de 19 couches** transmettent moins de 1e-4, donc le signal est noyé.

Un suivi optique continu à λ₀ sur tout l'empilement rend **100 % de plantages**
(`CRASH_LEVEL_UNREACHABLE`). Le monitoring optique ne meurt pas progressivement : il meurt.

### 25.2. Ce que le changement de témoin restaure, et ce qu'il coûte

**Elle restaure.** Chaque témoin ne porte jamais plus d'une cinquantaine de couches, donc `T`
reste mesurable, le swing `dT/de` reste exploitable, et POEM retrouve des extrema francs
comme repères de phase absolus.

🔴 **Elle coûte, et c'est le fait qui gouverne tout le chantier : LA COMPENSATION D'ERREUR NE
TRAVERSE PAS LE CHANGEMENT DE TÉMOIN.** Tout l'avantage du monitoring optique sur le contrôle au quartz
est qu'une erreur d'épaisseur sur la couche *k* est partiellement **auto-corrigée** : les
couches suivantes, lues sur le **même** verre, voient l'erreur accumulée et le point de
déclenchement se décale pour l'annuler en partie. Dès qu'on change de témoin, les couches
d'après sont lues sur un verre qui **ne contient pas** les erreurs d'avant. Le résidu de la
partie 1 est donc **gelé dans la pièce, définitivement incorrigible**, et le spectre final
porte erreur(partie 1) + erreur(partie 2) **sans terme croisé**.

🔑 **Et il faut être précis : ce sont DEUX mémoires distinctes qui tombent, pas une.**

| ce qui est perdu | portée |
|---|---|
| **La compensation globale** — le niveau de déclenchement est calculé sur la pile **nominale** et appliqué à la pile **réelle** ; l'écart entre les deux produit l'erreur de signe opposé (Macleod, Bousquet) | **toute la pile sous le changement de témoin**, non bornée |
| **Le rejeu d'ancres POEM** | borné à **4 couches** (`MAX_LOOKBACK_VAL`) |

C'est la première qui coûte cher, et elle n'est pas plafonnée. Ne dis pas « on ne perd que
4 couches d'historique » : c'est vrai pour POEM seul, et faux pour la compensation.

#### 👤 Ce que la machine impose, obtenu le 2026-08-14

| | |
|---|---|
| **Le changement se fait par carrousel SOUS VIDE** | Plusieurs témoins sont déjà en enceinte. **Ni remise à l'air, ni repompage, ni contamination.** ⚠️ Le nombre de changements de témoin est donc plafonné par le nombre de positions du carrousel. |
| **La fente garde le même réglage** | 👤 *« les fentes gardent le même setting »*. Une campagne ne peut pas choisir sa propre résolution : `monochromator_resolution_nm` reste **un scalaire pour tout le run**. |
| **Témoin et pièce reçoivent la même épaisseur** | À peu près identiques. Donc **aucun facteur d'uniformité à modéliser**, et le changement de témoin sépare la **mémoire optique**, rien d'autre. |

🔴 **Conséquence, et elle durcit le problème au lieu de l'adoucir : le changement de témoin est
OPÉRATIONNELLEMENT GRATUITE.** Pas de coût atelier à mettre en face du gain. L'arbitrage est
donc **purement informationnel** — on échange de la compensation contre du signal, et rien
d'autre ne vient trancher. Il n'y a aucun garde-fou économique pour dire « pas plus de deux
changements » : c'est la physique seule qui doit le dire.

### 25.3. 🔑 CE QUE LE CODE A DÉJÀ — le changement de témoin n'est pas une refonte

| | |
|---|---|
| **La vue témoin** | `certus/physics/certus_strat_batch.py:474` — `current_run_th_buffer[r, :i_layer]` est la pile accumulée que la lecture optique « voit ». **C'est là que le changement de témoin se joue** : changer de témoin à la couche *p* revient à passer la tranche `[r, p:i_layer]`. |
| **La pièce** | `sim_thick_batch`, épaisseurs réelles complètes `(n_runs, n_layers)`. Elle n'est **pas** tronquée : la pièce continue d'accumuler toutes les erreurs. C'est exactement la physique voulue. |
| **Le crochet POEM** | `certus/physics/certus_strat_batch.py:485` — `block_start[i_layer]` est **déjà** un tableau par couche disant au noyau où commence l'historique. Un changement de témoin est un `block_start` forcé, **plus** la troncature de la pile. |
| **L'écrêtage d'historique** | `certus/physics/certus_strat_growth.py:75` — `MAX_LOOKBACK_VAL = 4`, appliqué en `certus/physics/certus_strat_growth.py:904-908`. L'historique rejoué repart de zéro à le changement de témoin. |
| **Le seuil de swing** | `certus/physics/certus_strat_growth.py:883` — `SWING_MIN = 0.04`. **Un critère de mort du signal existe donc déjà, chiffré, dans le noyau.** |

🔴 **Vérifier ces cinq ancrages avant d'écrire une ligne.** Le document a déjà cité
`certus/core/certus_strat_growth.py` — **ce fichier n'existe pas**, le module est en
`certus/physics/`. Un plan bâti sur un chemin faux coûte une session.

### 25.4. 🔴 QUAND CHANGER DE VERRE TÉMOIN — le vrai problème, et il n'est PAS résolu

> 👤 *« on perd la compensation : oui, ça c'est évident, mais quand changer ? ça c'est
> l'enjeu majeur »* — *« savoir quand changer de testglass est un enjeu majeur et un problème
> de recherche à part entière et non résolu. Il va falloir explorer plein de pistes pour
> savoir à partir de quand on en tire bénéfice. Rien ne remplacera les tests simulés sur le
> 99c et peut-être le 48c. »* (2026-08-14)

**Ne confonds pas les deux.** Que le changement de témoin coûte la compensation est un fait acquis,
mécaniquement vrai, démontré par les tests de §23.5-T1 — et **ce n'est pas la question**.
La question est **à quelle couche changer de témoin**, et elle est ouverte.

#### 🔵 CE QUE LES EXPÉRIMENTATEURS PRESSENTENT — hypothèse consignée, PAS un résultat

> 👤 2026-08-15 : *« l'intuition veut qu'on change de verre témoin à proximité d'une zone non
> sensible, après au moins 20 couches et au max 60, et pour une épaisseur optique
> "raisonnable". Ça c'est ce que les expérimentateurs pressentent. »*

🔴 **C'est une intuition de praticien, à tester — elle n'a pas valeur de mesure.** Elle est
écrite ici parce qu'elle vient du terrain et qu'elle oriente la recherche, pas parce qu'elle
est établie. Chacun de ses trois critères a un statut de mesure **différent**, et il faut les
distinguer :

| critère de l'intuition | statut au 2026-08-15 |
|---|---|
| **changer près d'une zone peu sensible** | 🟠 **NON VALIDÉE, et le test conçu pour trancher a échoué à trancher.** Détail ci-dessous. |
| **au moins 20 couches, au plus 60** | 🟢 **déjà une contrainte dure du code**, posée par 👤 : `LO, HI = 20, 60` dans `campagne_intervalles.py`. Ce n'est pas une hypothèse testée, c'est le domaine dans lequel on cherche. C'est elle qui ramène les partitions à 441. |
| **épaisseur optique « raisonnable »** | 🔴 **RÉFUTÉE comme prédicteur** sur le 99c. L'épaisseur optique accumulée **ne prédit pas** où le changement doit avoir lieu. Réfutés avec elle : le vieillissement du témoin, le nombre d'espaceurs franchis, la position par rapport au dernier espaceur. |

#### 🔴 LA RÈGLE DE SENSIBILITÉ EST RÉFUTÉE — le test hors échantillon du 2026-08-15

La règle testée était : *« changer de verre témoin juste après une couche de FAIBLE
sensibilité, jamais après une couche sensible »*, où `S(p-1)` est la sensibilité de la couche
**gelée** par le changement.

🔴 **AVANT DE LIRE LE TABLEAU — `S` A DEUX DÉFINITIONS ET ELLES NE DONNENT PAS LE MÊME
CLASSEMENT.** §23.10 mesure `S(j)` par une perturbation de **1 nm ABSOLU**. Une perturbation
de **1 % RELATIF** pondère par l'épaisseur nominale : ce n'est **pas** la même grandeur. Sur le
random75 les deux ne corrèlent qu'à **+0,79** entre elles, et donnent des contrastes de
**11,3×** contre **19,8×**. **Seul le 1 nm absolu se compare aux trois repères existants.**
Une première version de ce paragraphe a mélangé les deux et concluait à tort ; les chiffres
ci-dessous sont tous en **1 nm absolu**.

| composant | structure | contraste de `S` | **Pearson r** |
|---|---|---|---|
| 99c passe-bande 5 cavités | 5 cavités + miroirs | **82×** | **+0,69** |
| 35c passe-bande 3 cavités | 3 cavités | 24× | +0,20 |
| 48c dichroïque | passe-haut | 14× | +0,25 |
| 🔑 **75c ALÉATOIRE** (graine 2026) | **aucune** | **11,3×** | **−0,19** (Spearman −0,15) |

#### Ce que ce test tranche, et ce qu'il ne tranche PAS

🔴 **Il ne tranche pas.** Et il faut le dire, parce que le random75 avait été construit **pour**
trancher. Les deux lectures du +0,69 étaient :

- *(a) la règle a besoin d'un fort contraste de sensibilité* ;
- *(b) le +0,69 tenait à la structure du 99c, pas à la sensibilité*.

Le random75 devait les séparer en offrant **une absence de structure avec un fort contraste**.
**Il n'a pas le fort contraste** : 11,3×, soit le **plus bas des quatre**, sept fois moins que
le 99c. Une corrélation faible y est donc **compatible avec (a) autant qu'avec (b)**.
L'expérience ne discrimine rien.

⚠️ **Et le −0,19 n'est pas un signe inversé, c'est du bruit.** Avec 18 points, il faut
`|r| ≥ 0,47` pour sortir de zéro au seuil de 5 % ; **11 des 18 positions sont à égalité**.
Lire une inversion là-dedans serait une surinterprétation.

🔑 **Ce qui reste néanmoins vrai sur les quatre composants** : contraste et corrélation vont
dans le même sens — 82× → +0,69, puis 24×, 14×, 11,3× → +0,20, +0,25, −0,19. Ce n'est **pas**
une validation : quatre points, et trois des quatre corrélations sont sous le seuil de
signification. **`S(p-1)` n'est pas un prédicteur validé.**

📌 **L'expérience qui trancherait, et elle reste à faire** : un empilement **sans structure**
et à **fort contraste de sensibilité** (~80×). Générer un random dont les multiplicateurs sont
tirés pour maximiser l'étendue de `S`, et non uniformément comme le random75.

#### 🟢 ET LE RÉSULTAT LE PLUS IMPORTANT DE LA JOURNÉE — la barrière n'est PAS le nombre de couches

Le 75 couches aléatoire a été mesuré **en une seule campagne**, sur verre nu, même protocole
(fast, fente 2 nm, graine 42) : **241 stratégies déposables sur 662, plantage minimal 0,0 %,
SEEL 0,272 nm**. Il n'a **aucun** besoin d'un changement de verre témoin.

| | couches | une seule campagne | structure |
|---|---|---|---|
| dichroïque 48c | 48 | 🟢 0 % — 0,173 nm | passe-haut |
| passe-bande 35c | 35 | 🟢 0 % — 0,482 nm | 3 cavités |
| 🔑 **aléatoire 75c** | **75** | 🟢 **0 % — 0,272 nm** | **aucune** |
| passe-bande 99c | 99 | 🔴 **100 % sur 487 stratégies** | **5 cavités + miroirs à 10⁻⁴** |

🔴 **75 couches passent, 99 ne passent pas. Ce n'est donc pas la longueur qui tue le
monitoring, c'est la STRUCTURE** — les espaceurs demi-onde à swing nul et les miroirs de 19
couches sous le plancher photométrique (§23.1). Le modèle « au-delà d'une cinquantaine de
couches le témoin devient optiquement mort » est **réfuté** : un empilement aléatoire de 75
couches se surveille d'un bout à l'autre sans difficulté.

⚠️ **Ce que ça ne dit pas** : que 99 couches aléatoires passeraient. Un seul empilement de 75,
une seule graine. Ce qui est établi est la **réfutation**, pas la loi inverse.

#### 🔴 ET LE CONTRÔLE NÉGATIF PASSE UNE TROISIÈME FOIS

Puisque le random75 est monitorable en une campagne, changer de témoin doit y **perdre**.
C'est le cas, et largement :

| composant monitorable | sans changement | avec changement | verdict |
|---|---|---|---|
| 48c | 0,173 nm | — | **+73 à +89 %** (11/11 partitions) |
| 35c | 0,482 nm | — | **+10 à +98 %** (12/12 partitions) |
| **75c aléatoire** | **0,272 nm** | **0,571 nm** (meilleure des 18) | 🔴 **+110 %** |

**Trois composants sur trois.** Là où le monitoring optique fonctionne, changer de verre
témoin **dégrade toujours**. C'est mécaniquement attendu — le changement *retire* de la
compensation sans rien restaurer — et c'est ce qui fait du multi-témoins un **outil de
faisabilité, jamais d'optimisation**.

⚠️ Le +110 % est mesuré contre une borne supérieure (sélection gloutonne par intervalle,
§23.9), donc le vrai écart est **au plus** celui-là. Le signe, lui, n'est pas en cause.

🔑 **Et un résultat qui, lui, se REPRODUIT** : *où* changer importe **peu**, sur les deux
composants et indépendamment de leur structure.

| | 99c (5 cavités) | 75c (aléatoire) |
|---|---|---|
| positions/partitions assemblées | 440 | 18 |
| étendue totale du SEEL | **+14,4 %** | **+15,4 %** |
| à égalité avec la première (δ = 5,1 %) | 136 | **11 sur 18** |

C'est **la seule régularité qui traverse une structure et une absence de structure**.
L'optimum est **plat**, ce qui explique à la fois pourquoi l'intuition des expérimentateurs
est difficile à prendre en défaut, et pourquoi elle est peu discriminante en pratique :
sur un plateau, presque toute position raisonnable convient.

📏 Reproduction : `scripts/assembler_r75.py`, sortie
`reports/controle_random75/ASSEMBLAGE_r75.json`, log `reports/assemblage_r75.log`.
Contrôle d'assemblage (nominales concaténées vs design complet) : écart **0,000e+00**.

**Ce que ça vaut opérationnellement** : l'intuition est un **bon filtre a priori** — elle
écarte les positions manifestement mauvaises sans calcul — mais elle ne remplace pas
l'assemblage, qui reste la seule mesure du SEEL de la pièce. 👤 : *« rien ne remplacera les
tests simulés »*.

#### 🎯 La cible, posée par 👤

> **SEEL global de l'ordre de 0,3 nm sur le 99c**, avec **2 ou 3 témoins**, sur la pièce
> complète qui les reçoit tous. On tâtonnera d'abord.

🔴 **MAIS LA PREMIÈRE CIBLE N'EST PAS LE SEEL.** Le point de départ n'est pas « 0,86 nm » :
c'est **100 % de plantage**, donc *aucune* stratégie exploitable (§23.1). **Tant que le
plantage n'est pas passé sous 5 %, aucun SEEL n'est publiable** — celui qui s'affichera sera
un score de repli, et comparer deux couches de changement sur des scores de repli revient à
**comparer deux façons d'échouer**.

| # | Cible | Pourquoi dans cet ordre |
|---|---|---|
| **1** | **`crash_rate < 5 %`** sur la pièce | Sans ça le composant n'est pas fabricable **du tout**, et rien d'autre ne se mesure. C'est ce seuil qui dira si le multi-témoins **marche**. |
| **2** | SEEL de l'ordre de **0,3 nm** | La cible de 👤. Elle ne devient une question qu'une fois la première franchie. |

Repère pour la cible 2 : à 3 témoins chaque campagne fait ~33 couches, soit la longueur du
35c (0,48 nm) et du 48c (0,17 nm) — **à 0,0 % de plantage tous les deux**. Une cible entre
les deux est donc cohérente avec ce que la machine sait faire sur des piles de cette taille,
à condition que les campagnes se combinent bien, ce que personne ne sait.

#### 🔴 LE SEEL GLOBAL N'EST PAS LA MOYENNE DES SEEL PARTIELS — ne fais jamais ce raccourci

> 👤 *« attention, SEEL global de 0,3 nm ne veut pas dire que les SEEL partiels (par
> testglass) seront à 0,3 ! »*

**Ce sont deux grandeurs différentes, mesurées sur deux objets différents.**

| | mesuré sur | ce que ça vaut |
|---|---|---|
| **SEEL global** | le **spectre de la pièce complète**, 99 couches, 5 cavités | 🔑 **la seule grandeur qui compte** — c'est le composant qu'on vend |
| **SEEL partiel** | une campagne prise seule, ~33 couches | un **diagnostic**, rien de plus |

**Pourquoi ils divergent, et fortement.** Un passe-bande à 5 cavités est un amplificateur
d'erreur : la même erreur physique par couche produit une erreur spectrale bien plus grande
sur le composant résonant complet que sur un sous-empilement mesuré isolément. Une campagne
qui « affiche 0,2 nm » toute seule peut donc contribuer beaucoup plus que 0,2 au chiffre
global. **Viser 0,3 global n'autorise pas à viser 0,3 par campagne** — il faudra
vraisemblablement bien mieux que ça sur chacune.

⚠️ Et cela **re-condamne** le raccourci déjà interdit en §23.6 : `SEEL = √(SEEL₁² + SEEL₂²)`
n'est pas seulement non mesuré, il compose des grandeurs qui **ne vivent pas sur le même
objet**. Ne rapporte que le SEEL de la pièce. Si tu affiches un SEEL partiel, dis en toutes
lettres qu'il est un diagnostic et **jamais** qu'il compose le global.

#### Pourquoi c'est difficile, et pas seulement long

Il faut l'écrire, sinon quelqu'un va croire qu'un seuil suffit.

| # | La difficulté | Pourquoi elle bloque une règle simple |
|---|---|---|
| 1 | **Bénéfice et coût varient en sens inverse le long de la pile** | Changer tôt garde un témoin vif mais gèle l'erreur tôt, et la compensation manque sur tout le reste. Changer tard garde la compensation mais les couches d'avant ont déjà été surveillées sur un témoin mourant. L'optimum est **au milieu de deux courbes qu'on ne sait pas tracer**. |
| 2 | 🔴 **La grandeur qui décide n'est pas locale** | Ce qui compte est le SEEL **à la fin**, pas la qualité du signal **à le changement de témoin**. Un changement de témoin qui paraît excellente localement peut être désastreuse si elle gèle l'erreur dans une couche à laquelle le spectre final est très sensible. **On ne peut donc pas choisir couche par couche** : le problème n'est pas séparable, et toute règle gloutonne est suspecte. |
| 3 | **Le changement de témoin n'est pas un axe indépendant** | Elle force une frontière de bloc, exactement comme un changement de λ ou une couche en Rate. Elle entre donc en **concurrence combinatoire** avec le partitionnement en blocs (§24-43) et avec le placement des couches Rate. L'optimum de changement dépend du plan de blocs, et réciproquement. Ce n'est pas un scalaire à régler. |
| 4 | ⚠️ **Le critère évident est probablement SYSTÉMATIQUEMENT EN RETARD** | `SWING_MIN = 0.04` dit où le monitoring **échoue**, pas quand changer de témoin **paie**. Quand le swing passe sous le seuil, le mal est déjà fait : le bon changement se place vraisemblablement **avant** la mort du signal, pas au moment où elle survient. Un seuil rendra donc une réponse trop tardive, et elle aura l'air raisonnable. |
| 5 | **Le coût opérationnel ne borne rien** | Le carrousel rend le changement de témoin gratuit (§23.2). Aucun garde-fou économique ne dira « pas plus de deux » : seule la physique le dira, et seul le nombre de positions du carrousel plafonne. |
| 6 | 🔴 **La décision peut être sous le bruit** | La résolution statistique d'un score est de ~6 % relatif à N = 150. Si deux couches de changement diffèrent de moins que ça, un balayage « trouvera » un optimum qui est du bruit. **Il faut fixer la profondeur avant de regarder les résultats**, et vérifier qu'un écart survit à un changement de graine. |

#### La méthode, et l'ordre n'est pas négociable

👤 a tranché : **on ne postule pas la règle, on la découvre.** Et : *« rien ne remplacera les
tests simulés »*. Donc, en trois temps :

1. **Deux prédicteurs GRATUITS**, sans aucun Monte-Carlo (T2, T3).
2. **Une vérité de terrain COÛTEUSE** : le balayage des couches de changement sur le 99c (T4).
3. **La corrélation entre les deux** — le « on comprendra a posteriori ». Si un prédicteur
   gratuit prédit la vérité coûteuse, on tient une **règle générale** ; sinon on a une carte,
   et on sait que la règle est ailleurs.

⚠️ **Ne pas inverser.** Écrire la règle d'abord puis chercher la mesure qui la confirme est
l'erreur n°2 du document. Le tâtonnement de 👤 est légitime **à condition d'être consigné
comme tâtonnement** : chaque essai, sa couche de changement, son SEEL, dans `probe_runs.tsv`.
Un tâtonnement noté est une carte ; un tâtonnement oublié est du bruit.

### 25.5. LA TODO LISTE, dans l'ordre

#### 🔴 T0 — Les CONTRÔLES NÉGATIFS, avant toute machinerie

**À faire en premier, et c'est contre-intuitif.** Sur le 35c et le 48c, le monitoring optique
marche : le SEEL y vaut 0,48 et 0,17 nm. Un changement de témoin y est donc **une perte sèche** — il
retire de la compensation sans rien restaurer, puisqu'il n'y avait rien à restaurer.

⚠️ Et le carrousel ne lui oppose **aucun coût** pour la retenir (§23.2) : si le modèle se
trompe, rien dans la simulation ne l'empêchera de couper à tort. C'est précisément pour ça
que ces contrôles négatifs sont le garde-fou du chantier.

**Le critère de recette du chantier entier :** si la machinerie finit par « améliorer » le 35c
ou le 48c en les coupant, **le modèle est faux** et rien de ce qui suit ne vaut. Écris cette
attente **avant** de mesurer, dans le test, pas dans le rapport.

| # | Ce qu'on mesure | Attendu |
|---|---|---|
| 1 | 48c, changement forcé en 24 | SEEL **dégradé** par rapport à 0,17 nm |
| 2 | 35c, changement forcé en 17 | SEEL **dégradé** par rapport à 0,48 nm |
| 3 | 99c, changement forcé vers le milieu | **plantage sous 5 %** — c'est l'hypothèse à réfuter. **Pas un SEEL** : sans survivant, tout SEEL affiché est un score de repli (§23.1) |

#### ✅ T1 — Le mécanisme de changement : **FAIT le 2026-08-14**

**Le champ à poser sur une stratégie : `witness_reset_layers`**, liste d'indices 0-based des
couches où un témoin **nu** entre dans le faisceau. Liste vide = comportement historique.
L'indice 0 est ignoré (la couche 0 pousse déjà sur du verre nu).

**Ce qui a été écrit, et c'est plus simple que prévu.** Le changement de témoin n'est pas une troncature
de tranche : c'est **l'index de départ de trois boucles** dans le noyau de croissance.

| où | ce qui change |
|---|---|
| `certus_strat_growth.py`, `simulate_growth_kernel` | nouveau paramètre `witness_base_layer` (défaut 0). **`M_before`** (pile réelle) et **`M_nom`** (pile nominale) partent de `witness_base_layer` au lieu de 0, ainsi que la pile sous la fenêtre POEM. Garde ajoutée : `j0` ne peut pas descendre sous la base, sinon la boucle tournerait à l'envers et rendrait vide **en silence**. |
| `certus_strat_batch.py` | `witness_reset_flags` → carte `witness_base[i]`, et **frontière de bloc forcée** à chaque changement : les ancres que POEM rejouerait ont été observées sur un verre qui n'est plus dans le faisceau. |
| `certus_strat_robustness.py` | lit `witness_reset_layers` sur la stratégie et construit les drapeaux. |

🔑 **Le coût de le changement de témoin n'est modélisé NULLE PART, et il ne doit pas l'être** — il tombe
de ces deux boucles. Le niveau de déclenchement est calculé sur la pile **nominale** et
appliqué à la **réelle** ; c'est cet écart qui produit l'erreur de signe opposé. Faire partir
les deux boucles au même `witness_base_layer` rend les erreurs d'en dessous invisibles aux
deux à la fois : elles ne peuvent plus être compensées, et restent gelées dans la pièce.
🔴 **N'en tronquer qu'une seule serait bien pire que faux** : on comparerait une cible
nominale à 99 couches contre une pile réelle de 20.

🔴 **Et la boucle du Rate n'est PAS coupée**, délibérément (`growth.py`, branche `is_rate`) :
l'estimation de vitesse est une propriété **de la machine** — le quartz, le chrono — pas du
verre que le faisceau regarde. Changer de témoin ne fait pas oublier sa calibration.

**Les tests, `tests/unit/test_strat_multiple_testglass.py` — 9 passent :**

| # | Test | Résultat |
|---|---|---|
| 1 | carte de changements de témoin toute vide = paramètre absent | ✅ bit-identiques : l'historique reste comparable |
| 2 | changement en *p*, erreur de 40 nm enfouie en *p−4* | ✅ **bit-identique** au cas sans erreur → le témoin ne voit vraiment plus sous le changement de témoin |
| 3 | 🔴 **le contrôle qui donne son sens au test 2** : même erreur, **sans** changement de témoin | ✅ **différent** → la compensation est bien vivante, donc le test 2 mesure quelque chose |
| 4 | 🔴 **la pièce garde ce que le témoin a oublié** | ✅ `results` rend les 12 couches, changement ou non. C'est le test qui attrape le défaut flatteur : tronquer la pièce **améliorerait** le score |
| 5 | couche de changement honorée, 4 positions | ✅ |

⚠️ **Ce que T1 ne dit PAS** : que couper soit bénéfique. Il rend le changement de témoin *possible et
correctement modélisée*. Tout le reste de §23 sert à savoir **où**.

#### T2 — Prédicteur gratuit n°1 : LA CARTE DE MORT DU SIGNAL

Pour chaque couche *i* et chaque λ candidate, calculer sur le témoin portant les couches
`[base..i)` le **swing disponible** — l'amplitude crête-à-crête de `T` pendant le dépôt de la
couche. Nominal, aucun tirage, coût négligeable.

La grandeur qui décide : **`swing_max(i) = max sur λ du swing`**. Le seuil existe déjà :
`SWING_MIN = 0.04` (`certus/physics/certus_strat_growth.py:883`). **Première règle générale candidate : changer de témoin juste
avant que `swing_max(i)` ne passe sous `SWING_MIN`.**

⚠️ Cette carte est à produire **par couche et par λ**, pas seulement par couche : une couche
aveugle à λ₀ peut être parfaitement lisible 40 nm plus loin. C'est tout l'objet du solveur.

#### T3 — Prédicteur gratuit n°2 : LA CARTE DE SENSIBILITÉ À L'ERREUR GELÉE

C'est le prédicteur du **coût** de le changement de témoin, et il tombe directement de la §23.2. Pour
chaque position candidate *p* : geler un champ d'erreur réaliste sur les couches `1..p`, puis
mesurer le **dommage spectral** sur le design final. TMM pur, aucun monitoring, aucun
Monte-Carlo de robustesse — donc peu coûteux.

Cela rend `sensibilite(p)`. La règle générale candidate devient le croisement des deux
courbes gratuites : **couper là où le signal est encore vivant et où l'erreur gelée coûte le
moins.**

⚠️ **Ne pas coder en dur « pas à l'intérieur d'une cavité ».** C'est l'attente — la résonance
dépend de l'épaisseur optique totale du spacer et des miroirs qui l'encadrent, donc une erreur
gelée là désaccorde toute la bande. Mais c'est au balayage de le montrer. Une carte qui
retrouve les spacers (couches 10, 30, 50, 70, 90) toute seule **valide la méthode** ; une
règle qui les impose ne prouve rien.

#### T4 — La VÉRITÉ DE TERRAIN : balayage exhaustif, automatisé

| | |
|---|---|
| **Script** | ⚠️ **Ce nom était un projet, il n'a jamais existé.** Ce qui a été construit à la place : `scripts/campagne_intervalles.py` — même exigence, une commande pour toute la campagne, chaque run vérifié, reprenable, plus le partage d'intervalles qui rend la recherche traitable |
| **Balayage** | *p* sur toutes les positions, ou un pas régulier si le coût l'impose |
| **Ce qu'on mesure** | le **SEEL de la pièce**, pas du témoin. Plus le taux de plantage, le nombre de couches en Rate, et le nombre de changements de λ |
| **Contrôles dans la même campagne** | (a) sans changement de témoin ; (b) **même nombre de couches en Rate, sans changement de témoin** — sans ce second contrôle, on ne saura pas si le gain vient de le changement de témoin ou du Rate |

🔴 **Consigner la configuration effective de chaque run**, et pas seulement celle demandée.
La campagne « gate » du 2026-08-14 a rendu ses 6 runs **FAILED** parce que
`crash_gate_confidence` était dans `_OVERRIDES` sans être dans `TRACED_KEYS` : appliquée au
run, jamais consignée. `witness_reset_layers` doit être dans **les deux**, et dans le nom du
fichier de sortie.

#### T5 — La CORRÉLATION, et la règle générale

Confronter T2 et T3 à T4 : lequel des prédicteurs gratuits classe correctement les positions
de changement ? Candidats à mettre en concurrence, **tous exprimés sans dimension** pour qu'ils
survivent au-delà du 99c :

| candidat | forme | ce qu'il vaut |
|---|---|---|
| nombre de couches | couper tous les *K* | le plus simple, **la référence à battre** |
| mort du signal | `swing_max(i) < SWING_MIN` | physiquement motivé, gratuit (T2) |
| erreur gelée | minimum de `sensibilite(p)` | cible le vrai coût, gratuit (T3) |
| SEEL marginal | la contribution par couche se dégrade | plus coûteux, demande l'attribution par couche |
| structure du design | frontières de sous-ensembles | gratuit, mais est-ce général ? |

**Une règle n'est retenue que si elle est validée hors échantillon** : autre graine **et**
autre empilement. Un changement de témoin est un degré de liberté de plus — une recherche qui l'a trouvera
**toujours** au moins aussi bon en échantillon. C'est le piège central de ce chantier.

#### T6 — Généraliser : l'échelle d'empilements

La règle doit tenir sur une échelle, pas sur un cas :

| empilement | rôle | attendu |
|---|---|---|
| 35c passe-bande | **contrôle négatif** | le changement de témoin **perd** |
| 48c dichroïque | **contrôle négatif** | le changement de témoin **perd** |
| 99c 5 cavités | le cas qui ouvre le chantier | le changement de témoin **gagne** |
| ≥ 150c synthétique | l'extrapolation | le changement de témoin gagne **beaucoup**, et 2 changements battent 1 |

### 25.6. 🔴 LES PIÈGES DE CE CHANTIER

| | |
|---|---|
| **Dériver le SEEL global** | On sera tenté d'écrire `SEEL = √(SEEL₁² + SEEL₂²)`. Ce n'est pas seulement une conjecture non mesurée : elle compose des grandeurs qui **ne vivent pas sur le même objet** (§23.4). **Ne rapporte que le SEEL de la pièce.** |
| **Confondre SEEL global et SEEL partiels** | 👤 : *« SEEL global de 0,3 nm ne veut pas dire que les SEEL partiels seront à 0,3 »*. Le partiel est un **diagnostic**, jamais un terme du global. |
| **Tronquer la pièce avec le témoin** | Le défaut qui rendrait tout le chantier faux **et plausible** : le score s'améliorerait parce que les erreurs d'avant le changement de témoin auraient disparu au lieu d'être gelées. Test 4 de T1, et il est écrit. |
| **Le degré de liberté gratuit** | Un changement de témoin ne peut qu'améliorer un résultat **en échantillon**. Validation hors échantillon obligatoire : autre graine **et** autre empilement. |
| **Le plantage à 0,0 %** | Zéro sur 300 tirages n'est pas zéro. C'est « moins de 1 % à 95 % de confiance ». |
| **Croire qu'un coût atelier freinera** | Il n'y en a pas : le carrousel rend le changement de témoin gratuit (§23.2). Rien hors de la physique ne limitera le nombre de changements de témoin — sauf le nombre de positions du carrousel. |
| **Changer « vers 50 »** | 50 est le souvenir de 👤 sur un cas, pas une mesure. Le balayage doit être libre de rendre 20, 30 ou 70. |
| 🔴 **Chercher la règle avant d'avoir les essais** | 👤, deux fois : *« ce sont les essais-erreur avec de nombreux batchs qui permettront une compréhension a posteriori »*. Une explication trouvée avant les mesures sera confirmée par elles, quoi qu'elles disent. |


---

### 25.7. 🔴 LE PLAN D'EXÉCUTION — et le problème qu'il doit résoudre AVANT tout le reste

> 👤 2026-08-15 : *« je veux un plan robuste, bien pensé, pour effectivement trouver
> l'endroit du changement de verre témoin et viser un SEEL amélioré sur le 99c avec deux ou
> trois verres témoins, sans que le raisonnement soit lié à la nature du filtre
> (passe-bande), mais avec des arguments très généraux. »*

#### 🔴 P0 — L'OBJECTIF EST SATURÉ, ET AUCUNE RECHERCHE NE FONCTIONNE SUR UN OBJECTIF PLAT

C'est le fait qui commande tout le plan, et il faut le regarder en face avant d'écrire une
ligne de balayage.

| grandeur | valeur sur le 99c | utilisable comme objectif ? |
|---|---|---|
| **SEEL** | score de **repli** (§23.1) | ❌ il classe des façons d'échouer |
| **`crash_rate`** | **1,000**, saturé | ❌ plat : aucune direction de recherche |

**Chercher la meilleure couche de changement en comparant des SEEL de repli reviendrait à
optimiser du bruit.** Il faut donc d'abord une grandeur qui ait un **gradient**. Deux voies,
et il faut les deux parce qu'elles se contrôlent mutuellement.

**Voie A — la MARGE, qui existe déjà et n'est pas saturée.** Le noyau rend par couche
`m_level`, `m_missed`, `m_fab` (`certus/physics/certus_strat_batch.py:393-395`), remontés en
profil (`certus/core/certus_strat_robustness.py:2243`). **A23 a mesuré que la marge prédit
le plantage d'un facteur 22, validée non circulairement.** Objectif de substitution pendant
la saturation : le **nombre de couches à marge insuffisante**, et la **pire marge**. Ces deux
nombres bougent quand le plantage ne bouge plus.

**Voie B — la CONTINUATION : desaturer, optimiser, puis remonter.** Réduire l'amplitude du
bruit (ou le corridor d'indice) d'un facteur jusqu'à ce que `crash_rate < 1`, chercher les
couches de changement dans ce régime, puis **remonter la difficulté par paliers** et vérifier
que les positions tiennent.

> 🔑 **Et ce test porte plus que la recherche : il dit si la règle est STRUCTURELLE.** Si la
> couche optimale ne bouge pas quand on change la difficulté, elle est dictée par
> l'empilement. Si elle se déplace, elle est dictée par le bruit — et il n'y a alors **aucune
> règle générale à trouver**, ce qui est un résultat en soi.

#### P1 — Les grandeurs qu'une règle GÉNÉRALE a le droit d'utiliser

👤 l'exige : *« sans que le raisonnement soit lié à la nature du filtre »*. La liste est donc
fermée, et elle se vérifie par un test simple — **une grandeur est admissible si elle se
calcule sur un empilement dont on ignore la famille.**

| ✅ Admissible | pourquoi |
|---|---|
| **Épaisseur optique accumulée depuis le dernier changement**, en unités de λ : $\sum n_j d_j / \lambda$ | **sans dimension**, donc transportable telle quelle d'un 48c à un 200c. C'est le meilleur candidat : il explique un « vers 50 couches » comme une *conséquence*, pas comme une règle |
| Nombre de couches depuis le dernier changement | la règle naïve, **la référence à battre** |
| Niveau de transmission du témoin `T(λ)` | dit quand le signal passe sous le plancher photométrique |
| Swing disponible, `SWING_MIN = 0.04` déjà codé | dit quand il n'y a plus d'extremum exploitable |
| Nombre de λ candidates viables pour la couche suivante | zéro ⟹ couche forcée |
| La marge (P0, voie A) | seule grandeur à gradient sous saturation |
| Dommage spectral d'une erreur gelée sur les couches `1..p` | le **coût** du changement, en TMM pur |

| ❌ Inadmissible | pourquoi |
|---|---|
| Position des cavités, des spacers, des miroirs | demande de savoir que c'est un passe-bande |
| « couper à la ie cavité » | ne survit pas au composant suivant |
| Toute constante ajustée sur le 99c seul | c'est la réponse d'un filtre, pas une règle |

#### P2 — Les deux cartes GRATUITES, sans un seul tirage Monte-Carlo

| carte | ce qu'elle donne | coût |
|---|---|---|
| **A — viabilité** | par couche et par λ, sur le témoin portant `[base..i)` : swing disponible, niveau `T`, nombre de λ viables. Dit **quand le témoin meurt** | minutes |
| **B — coût de l'erreur gelée** | par position `p` : geler un champ d'erreur réaliste sur `1..p`, mesurer le dommage spectral du design final. TMM pur | minutes |

La couche de changement candidate est au **croisement** : là où le signal est encore vivant
et où l'erreur gelée coûte le moins. ⚠️ Les deux cartes sont des **prédicteurs**, pas des
mesures : leur valeur se juge à leur corrélation avec P3, pas à leur élégance.

#### P3 — La recherche, et pourquoi elle n'est pas une force brute

Avec 49 positions admissibles (paires seulement, §23.5), il y a **1 176** couples et
**18 424** triplets. À ~15 min le run, l'énumération est exclue. L'ordre est donc :

1. **Un changement** — balayage grossier des positions (10 runs), sur le régime désaturé de
   P0. Compare la position gagnante aux cartes A et B : **c'est là que se joue la
   compréhension a posteriori.**
2. **Deux changements** — glouton : on fixe le meilleur premier, on balaie le second.
   🔴 **Puis on teste la séparabilité** : le meilleur couple est-il bien (meilleur seul,
   meilleur second) ? Si oui, le problème est quasi séparable et le glouton est justifié. Si
   non, **c'est un résultat**, et la recherche doit s'élargir.
3. **Trois changements** — idem, en partant du meilleur couple.
4. **Perturbation locale** autour de chaque optimum, ±2 et ±4 couches, pour distinguer un
   optimum **pointu** d'un plateau. Un optimum pointu à la résolution du score est suspect.

#### P4 — Les garde-fous, sans lesquels le plan se trompera lui-même

| # | Le piège | La parade, posée AVANT de mesurer |
|---|---|---|
| 1 | **Un changement est un degré de liberté gratuit** : 3 témoins font toujours ≥ 1 en échantillon | Le gagnant doit survivre à **une autre graine**. Écart requis : supérieur à la résolution statistique du score. |
| 2 | **Confusion avec la structure en blocs** : un changement force une frontière de bloc, donc modifie aussi le partitionnement | Rapporter le **nombre de blocs** à chaque ligne. Comparer à nombre de blocs égal quand c'est possible. |
| 3 | **Décision sous le bruit** | Fixer `N` **à l'avance**. Un écart inférieur à la résolution est une **égalité**, pas un classement. |
| 4 | **La règle est ajustée sur le 99c** | La **règle**, pas les positions, doit être appliquée au 48c et au 35c et y prédire **« ne pas changer »**. C'est la falsification, et elle n'est pas optionnelle. |
| 5 | **On confond desaturé et nominal** | Toute position trouvée en régime réduit doit être **rejouée au nominal**. Sinon elle décrit un autre problème. |

#### P5 — Ce que le plan doit pouvoir conclure, y compris contre lui-même

Un plan qui ne peut pas échouer n'est pas un plan. Les trois issues sont **toutes**
publiables :

| issue | ce qu'on écrit |
|---|---|
| 🟢 `crash < 5 %` atteint à 2 ou 3 témoins | Le SEEL devient mesurable. **Alors seulement** la cible de 0,3 nm devient une question. |
| 🟠 `crash` baisse sans passer sous 5 % | Le mécanisme agit dans le bon sens mais ne suffit pas. Dire de combien, et ce qu'il faudrait en plus. |
| 🔴 aucun arrangement ne fait baisser `crash` | **Résultat valable et important** : sur ce composant le changement de témoin n'est pas la réponse, et il faut chercher ailleurs. Ne pas le maquiller en « amélioration du SEEL » de repli. |

### 25.8. 🟢 MESURÉ LE 2026-08-15 — le multi-témoins rend le 99c FABRICABLE, pas plus précis

**C'est le premier résultat positif du chantier, et sa lecture est étroite.** Ne le résume
jamais par « le SEEL ne change pas » : les deux chiffres ci-dessous ne décrivent pas la même
chose.

| | RMSE P95 | SEEL | plantage |
|---|---|---|---|
| **pièce assemblée**, 3 témoins (0 / 32 / 66) | `0.184946` | **0,860 nm** *(périmé — voir §25.12)* | **0 %** sur chacune des 3 campagnes |
| référence monolithique | `0.187761` | 0,87 nm | **100 %** — score de **repli** (§23.1) |

🔑 **Le monolithique n'est pas atteignable.** Aucune des 487 stratégies ne survit, donc son
0,87 nm ne décrit aucun dépôt réalisable. L'assemblé, lui, sort de **trois campagnes
déposables** — 23, 54 et 156 stratégies valides au choix, chacune à 0 % de plantage.

> **Le multi-témoins ne fait pas gagner en précision spectrale. Il fait passer d'IMPOSSIBLE
> à POSSIBLE.**

⚠️ **La cible de 👤 n'est pas atteinte** : 0,86 nm contre 0,3 nm visés, facteur 2,9. Pour
situer : 48c **0,17 nm**, 35c **0,53 nm** — l'assemblage est moins bon que les deux.

⚠️ **Portée** : une graine, une partition (32/66 choisie en tiers égaux **avant** de savoir
que la longueur n'est pas le critère), un composant. Rien ne dit que cette partition soit la
bonne — c'est ce que le pavage doit chercher.

#### 🔑 LA MÉTHODE D'ASSEMBLAGE — validée, et à réutiliser telle quelle

`scripts/assemble_testglass.py`. Elle vaut plus que ce résultat, parce qu'elle mesure la
**pièce** sans dépendre de la Phase A.

| # | Règle | Pourquoi, et ce qu'elle évite |
|---|---|---|
| 1 | **Aucun tirage n'est refait** | On concatène les épaisseurs **réellement simulées** de chaque campagne. Refaire un tirage introduirait un aléa neuf et détruirait ce qu'on mesure : les erreurs *commises*, sans compensation croisée. |
| 2 | **Même graine pour les trois campagnes** | `index_seed` est une **fonction pure de la graine** (`certus_strat_robustness.py:1502`), donc les trois partagent la réalisation du corridor d'indice — la physique d'**un seul dépôt**, où seul le monitoring repart à zéro. 🔴 Trois graines indépendantes **moyenneraient** une erreur systématique commune aux 99 couches et rendraient un SEEL **trop beau**. |
| 3 | **On note avec le code de production** | `compute_batch_rmse` reçoit les épaisseurs concaténées : l'assemblage est jugé par la fonction qui juge toutes les stratégies du dépôt. Aucune physique réimplantée, aucune surface de bug nouvelle. ⚠️ Son 7ᵉ argument n'est **pas** un tableau de parité mais la **matrice des indices par couche et par λ**, et `nH`/`nL` s'y passent **vides** (`:2460-2467`). |
| 4 | **Faisabilité et spectre sont DEUX mesures** | La faisabilité s'établit **campagne par campagne** — chacune sous 5 % de plantage. Le spectre s'établit **sur l'assemblage**, qui ne porte aucun taux de plantage puisqu'aucun monitoring n'y tourne. Les confondre est l'erreur qui a coûté la journée du 2026-08-15. |
| 5 | **On prend la stratégie DÉPOSABLE, pas `strats[0]`** | Sur le sous-empilement B, la mieux notée plante à **98 %** alors que **54** ne plantent jamais. On retient la mieux notée **parmi celles sous 5 %** — ce qu'un opérateur choisirait. |

🔴 **LE CONTRÔLE QUI VALIDE L'ASSEMBLAGE, et il n'est pas optionnel.** Avant tout chiffre :
concaténer les épaisseurs **nominales** des trois parties et exiger qu'elles reproduisent
celles du 99c. Mesuré : **écart 0,000e+00 sur les épaisseurs ET sur le spectre.**

> ⚠️ Ce contrôle a d'abord été écrit comme `T(nom)` contre `T(nom.copy())` — une
> **tautologie**, qui ne pouvait que passer. **Un faux contrôle est pire que pas de
> contrôle** : il donne la confiance sans la vérification.

#### Ce que les sous-empilements ont appris, et qui réfute une hypothèse

| | couches | stratégies déposables | plantage retenu |
|---|---|---|---|
| A | 0-31 | 23 / 166 | 0 % |
| B | 32-65 | **54 / 126** | 0 % |
| C | 66-98 | **156 / 163** | 0 % |

🔑 **Ce n'est pas l'ÂGE du témoin qui gouverne.** C, le **dernier** tiers — celui où le 99c
complet n'a plus qu'**une** λ viable — est le **plus facile** des trois sur verre nu : 156
stratégies déposables sur 163. La monitorabilité est une propriété **du sous-empilement**,
pas du nombre de couches déjà portées.

#### 🔴 POURQUOI LE 99c AVEC CHANGEMENTS DIRECTS RESTE À ~100 % — l'implantation est à moitié faite

`witness_reset_layers` n'existe que dans **trois** fichiers : `certus_strat_robustness.py`,
`certus_strat_batch.py`, `certus_strat_growth.py`. **`certus_strat_objectives.py`, où la
Phase A fabrique les λ candidates, n'en sait rien** — `build_M_before_cache` construit ses
matrices depuis la **couche 0** sans notion de changement.

Les candidates sont donc choisies pour un témoin **mourant**, puis évaluées sur un témoin
**neuf**. Mesuré : 99c à 32/66 rend min 98 % et **11 blocs** contre 3, tandis que le témoin
déséquilibré 10/20 rend 100 % et 4 blocs — **le mécanisme agit et la qualité de la partition
compte**, mais les λ sont choisies sur le mauvais objet optique.

⚠️ **Donc « 98 % » ne réfute pas la méthode : il teste une demi-implantation.** L'assemblage
de §23.8 contourne le problème, il ne le corrige pas.

### 25.9. 🔴 CE QUE L'ANALYSE CONTRADICTOIRE A CORRIGÉ — parades adoptées

Une analyse contradictoire indépendante de §23 a été produite le 2026-08-15
(`reports/proposition.html`). Elle a **lu le code**, pas seulement le plan :
`certus_strat_batch.py:424` et `MAX_LOOKBACK_VAL = 4` sont cités exactement. Quatre de ses
attaques portent, et les parades ci-dessous sont **contraignantes**, pas indicatives.

| # | L'attaque, et elle est juste | La parade, obligatoire |
|---|---|---|
| **1** | 🔴 **Cinq prédicteurs sur ~10 points de mesure = sélection post-hoc.** §23.5-T5 listait cinq règles candidates à corréler **après** le balayage. *« Le plan trouvera une règle, forcément. »* | **UN SEUL prédicteur, déclaré par écrit AVANT de mesurer.** S'il échoue, on peut en essayer un second — mais en le déclarant **exploratoire**, jamais confirmatoire. Rapporter le meilleur de cinq est du p-hacking déguisé en physique. |
| **2** | 🔴 **T3 est circulaire.** « Geler un champ d'erreur réaliste » ne dit pas **lequel**. Or le seul champ qui ait un sens physique est celui que produit le Monte-Carlo — donc un prédicteur « gratuit » qui a besoin du Monte-Carlo pour être calibré **n'est pas gratuit**. | **Écrire le champ d'erreur AVANT de l'exécuter**, et assumer qu'un champ i.i.d. mesure un dépôt **sans monitoring**, ce que personne ne fait. Si le champ ne peut pas être justifié : **abandonner T3**, ne pas le maquiller. |
| **3** | **« Dommage spectral » n'est pas un scalaire.** RMSE, décalage de λ₀, élargissement de bande donnent **trois classements différents** des positions. | **Documenter la norme choisie avant de mesurer.** Une norme choisie après coup choisit son gagnant. |
| **4** | 🔴 **La marge peut être aussi plate que le plantage.** A23 a validé la marge comme prédicteur sur des empilements à plantage **faible**. À 100 %, les marges seront uniformément catastrophiques. | **Vérifier que la marge a un gradient AVANT de fonder P0 dessus.** Regarder la **pire marge**, pas le décompte des couches insuffisantes — le décompte saturera à 99. |
| **5** | **Le forçage de frontière de bloc détruit aussi les ancres POEM**, second mécanisme de perte jamais quantifié séparément du premier. | Borné à 4 couches (`MAX_LOOKBACK_VAL`) contre un coût de compensation **non borné** : acceptable en première approximation. ⚠️ Mais si la recherche rend un **plateau**, c'est ce terme-là qui départagera, et il n'est pas instrumenté. |
| **6** | **Le budget n'est chiffré nulle part.** Le balayage réel coûte 30 à 50 runs, soit 8 à 12 h, sans marge pour les reprises. | **Figer le nombre de runs avant de commencer.** 🟢 L'assemblage de §23.8 le divise par ~10 : trois runs de ~2 min au lieu d'un run de 15 min par position. |
| **7** | **Le nombre de positions du carrousel n'est écrit nulle part**, alors qu'il plafonne l'espace de recherche. Si le carrousel a 3 positions, tester 4 témoins est **physiquement impossible**. | 🔴 **Question ouverte à 👤.** Ne pas planifier de partition avant la réponse. |

#### Ce que la mesure du 2026-08-15 a rendu caduc dans cette analyse

Elle a lu §23 **avant** l'assemblage. Trois de ses attaques visent des étapes qu'on n'a plus
besoin de faire :

| son attaque | pourquoi elle tombe |
|---|---|
| *« le balayage mesure la coupure COMPOSÉE avec la réponse du solveur »* | Vise T4. L'assemblage (§23.8) résout chaque campagne **indépendamment sur son propre objet optique**, puis compose. Le confondage n'y est pas le même. |
| *« la désaturation (P0) est un pari sans procédure de repli »* | Par l'assemblage il **n'y a plus rien à désaturer** : chaque campagne est déjà à **0 %** de plantage, avec 23, 54 et 156 stratégies déposables. |
| *« 8 à 12 h de balayage »* | Facteur 10 en moins par l'assemblage. |

⚠️ **Mais ses attaques 1 à 4 ne visent pas T4 en particulier** — elles visent **toute recherche
de règle générale**, y compris celle qui reste à faire. Elles s'appliquent intégralement.

#### Deux objections au MODÈLE, pas à la méthode — et elles restent ouvertes

**Le changement de témoin est modélisé comme instantané.** La rotation du carrousel prend du
temps. Obturateur ouvert, la pièce reçoit de la matière non comptée ; obturateur fermé, la
source dérive thermiquement. Ni l'un ni l'autre n'est dans le noyau. **Non mesuré, non
modélisé.**

**« Témoin et pièce reçoivent la même épaisseur » n'est pas quantifié.** 👤 a répondu *« à peu
près identiques »* (§23.2), et j'en ai déduit qu'aucun facteur d'uniformité n'était à
modéliser. ⚠️ **Un rapport de 0,97 — courant sur un bâti à rotation planétaire — ferait dériver
la pièce d'environ 1,5 quart d'onde sur 50 couches**, et c'est un biais **systématique que le
monitoring ne corrige pas** : il corrige l'erreur du témoin, pas celle de la pièce. Il
s'ajouterait à l'erreur gelée. 🔴 **Question à 👤 : ce rapport est-il mesuré sur ta machine ?**

### 25.10. 🟢 SYNTHÈSE DU 2026-08-15 — ce que la journée a établi, réfuté, et laissé ouvert

**Lis cette section avant tout le reste de §23.** Elle remplace les conclusions provisoires
qui la précèdent quand elles divergent.

#### Ce qui est ÉTABLI par la mesure

| # | Fait | Preuve |
|---|---|---|
| 1 | **Le 99c n'est pas fabricable en une seule campagne.** Les **487** stratégies plantent à **100 %** — pas la retenue, **la meilleure**. Le « 0,86 nm » qui circulait est un **score de repli**, inatteignable. | distribution complète des taux de plantage |
| 2 | **Le multi-témoins le rend fabricable.** Campagnes à **0 %** de plantage chacune, assemblage à **0,782 nm** *(0,760 nm annoncé le 15/08, corrigé le 16/08 — §23.12)*. 🔑 **Il ne fait pas gagner en précision — il fait passer d'IMPOSSIBLE à POSSIBLE.** | 386 partitions assemblées |
| 3 | **Le découpage ne gouverne presque rien.** Étendue **+14,4 %** sur 386 partitions, soit moins de 3 unités de résolution ; **110 partitions à égalité** avec la première. | résolution 5,1 % en SEEL à N=50 |
| 4 | **Le nombre de témoins ne compte pas.** ⚠️ **Revu le 16/08** : en premium la meilleure est à **4 témoins** (0,782 nm), la meilleure à 3 témoins suit à 0,784 nm — **+0,2 %**, sous la résolution de 3,0 %. Toujours une égalité, mais l'abandon de la vague à 4 témoins n'était **pas** fondé. | §23.12 |
| 5 | **Presque tout sous-empilement est monitorable sur verre nu** : **248 sur 249**. Un seul infaisable, `[22,78)`. | campagne des intervalles |
| 6 | 🔑 **Ce n'est PAS l'âge du témoin qui gouverne.** Le **dernier** tiers du 99c — là où, en campagne unique, il ne reste qu'**une** λ viable — est le **plus facile** des trois sur verre nu : 156 stratégies déposables sur 163. | A 23/166, B 54/126, C 156/163 |
| 7 | 🟢 **CONTRÔLE NÉGATIF PASSÉ, sur TROIS composants.** Là où le monitoring marche déjà, **toute** partition dégrade : **+73 à +89 %** sur le 48c (11/11), **+10 à +98 %** sur le 35c (12/12), **+110 %** sur le 75c aléatoire (0,272 → 0,571 nm). **Aucune ne gagne, même par chance.** | 40 sous-empilements |
| 8 | 🔑 **LA BARRIÈRE N'EST PAS LE NOMBRE DE COUCHES, C'EST LA STRUCTURE.** Un empilement **aléatoire de 75 couches** se surveille d'un bout à l'autre en **une seule campagne** : **241 stratégies déposables sur 662, plantage 0,0 %, SEEL 0,272 nm**. 75 passent, 99 non. Le modèle « au-delà d'une cinquantaine de couches le témoin meurt » est **réfuté**. | `reports/controle_random75/REFERENCE_0_75.json` |

Le point 7 est le plus important du lot : **si une seule de ces partitions avait gagné, tout
le reste tombait.** Le point 8 est celui qui recadre le chantier : ce qu'on combat n'est pas
une longueur, ce sont les **espaceurs à swing nul** et les **miroirs sous 10⁻⁴** (§23.1).

#### Ce qui est RÉFUTÉ

| hypothèse | verdict |
|---|---|
| « le témoin vieillit et meurt, donc changer vers 50 couches » | ❌ **deux fois** : le dernier tiers du 99c est le plus facile (point 6), **et** 75 couches aléatoires se surveillent en une campagne (point 8) |
| « c'est l'épaisseur optique accumulée qui décide » | ❌ elle **brouille** le signal : l'effondrement se voit à 54-56 **couches**, pas à 54-56 QWOT |
| « c'est le nombre d'espaceurs traversés » | ❌ 1, 2, 3 → 131, 160, 112 stratégies, sans tendance |
| « c'est la position de fin par rapport à un espaceur » | ❌ 11 % de fragiles dans la tranche, mais **82 intervalles sains** y finissent aussi |
| « c'est le nombre de couches » | 🟠 **localise sans déterminer** : les fragiles sont tous à 48-60 couches, mais seul **un tiers** des intervalles longs sont fragiles |

⚠️ **Quatre hypothèses testées après coup sur les mêmes données.** Chaque test de plus
augmente la chance qu'une colle par hasard. **Ne pas continuer à pêcher** — la suite demande
une grandeur nouvelle, pas une relecture.

#### Ce qui reste OUVERT

**La sensibilité par couche est le meilleur candidat, et il n'est pas validé.**
`S(j)` = dégât spectral d'une perturbation de 1 nm sur la couche *j*, en **TMM pur**, sans
Monte-Carlo et **sans rien savoir de la famille du filtre**. Le mécanisme est précis : changer
en `p` **gèle l'erreur de la couche `p−1`** sans compensation possible.

| composant | contraste de sensibilité | corrélation `S(p−1)` ↔ SEEL |
|---|---|---|
| 99c, 5 cavités | **82×** | **+0,69** (r² = 0,48) |
| 35c, 3 cavités | 24× | +0,20 |
| 48c, dichroïque | 14× | +0,25 |
| **75c aléatoire** (graine 2026, aucune structure) | **11,3×** *(mesuré)* | **−0,19** — dans le bruit |

🔴 **RÉSULTAT DU 2026-08-15, ET IL EST NÉGATIF AU SENS UTILE : le test n'a pas tranché.** Le
random75 avait été construit pour séparer « la règle a besoin d'un fort contraste » de « le
+0,69 tenait à la structure du 99c ». Il ne le peut pas : son contraste est de **11,3×**, le
**plus bas des quatre**, sept fois moins que le 99c. Une corrélation faible y est compatible
avec les deux lectures. Avec 18 points il faudrait `|r| ≥ 0,47` pour sortir de zéro à 5 %.
**Détail, définitions de `S`, et l'expérience qui trancherait : §23.4.**

🔑 **Et c'est bien `S(p−1)` qui compte** — la couche **gelée** — pas `S(p)` (r = +0,23) ni une
moyenne locale (r = +0,45). Le mécanisme prédit exactement ça.

⚠️ **La règle ne se transfère pas en l'état.** Deux lectures restent possibles et le 75c
aléatoire les départage : soit elle ne mord qu'à **fort contraste**, soit le +0,69 du 99c
était une **coïncidence** sur 13 points médians et confondus. Si les quatre points s'alignent
sur une relation monotone contraste ↔ pouvoir prédictif, la première devient une observation.

**Et le facteur limitant n'est pas là.** 0,782 nm contre **0,300** visés : facteur 2,6, avec
un écart meilleur/pire presque du bruit. Le levier pour la cible de 👤 **n'est pas le
découpage** — il est dans l'erreur intrinsèque de chaque campagne.

#### 🔴 Les cinq défauts d'INSTRUMENT trouvés dans la journée, et ils étaient tous silencieux

Aucun ne produisait d'erreur. Tous rendaient des nombres plausibles.

| défaut | comment il a été attrapé |
|---|---|
| `--mode fast` **jamais appliqué** — `run_workflow` rappelle `collect_params` et jette le dictionnaire modifié | la configuration **appliquée** consignée à côté de la demandée |
| le plan de changement et la fente figée, **même cause** | deux runs censés différer rendant un score **bit-identique** |
| ma vérification **relisait le dictionnaire jeté** — circulaire, elle validait tout | rien ne l'a attrapée : je l'ai vue en la relisant |
| `strats[0].crash_rate` lu comme « le plantage du run » — a produit un « B échoue à 98 % » **faux**, alors que 54 stratégies ne plantaient jamais | la **distribution** au lieu du premier élément |
| le contrôle d'assemblage écrit comme `T(nom)` contre `T(nom.copy())` — une **tautologie** | relecture avant de l'utiliser |

> 🔴 **Un faux contrôle est pire que pas de contrôle : il donne la confiance sans la
> vérification.** Et **une vérification qui relit sa propre entrée ne vérifie rien.**

⚠️ **Un défaut de PHYSIQUE, du même genre** : à graine commune — ce qu'il faut pour partager
la réalisation d'indice — le bruit de lecture des campagnes était **corrélé à 78 %**. Corrigé
en le traitant comme **un flux continu dont chaque campagne lit sa tranche** : **1 %**. Les
mesures d'avant ce correctif ne sont pas comparables à celles d'après.

#### T7 — Changements de témoin multiples

Une fois un changement de témoin comprise, récurrence : *n* campagnes de monitoring, chacune partitionnée
en blocs. La partition devient **à deux niveaux**, et elle se compose avec la recherche par
blocs déjà en place (§24-43). Ne pas ouvrir T7 avant que T5 ait rendu une règle.

---

### 25.11. 🔴 SOIRÉE DU 2026-08-15 — le mécanisme d'échec, et trois affirmations du projet réfutées

**Lis cette section avant §23.8 et §23.10 : elle les corrige là où elles divergent.**

#### Le mécanisme d'échec, décodé et non plus supposé

Cause des plantages, décodée depuis la sentinelle du noyau (`k × 1e6 + épaisseur nominale`,
`certus_strat_growth.py:82-89`) sur 282 couches-tirages du 99c :

| cause | part |
|---|---|
| **`TP_MISCOUNT`** | **83,0 %** |
| `LEVEL_UNREACHABLE` | 17,0 % |
| `NON_MONOTONIC` | 0,0 % |

🔴 **`strat.html` §21.15 affirme que le 99c plante en `CRASH_LEVEL_UNREACHABLE`. C'est faux.**

🔑 **Mais `TP_MISCOUNT` est le SYMPTÔME, pas la cause.** 👤 : *« ma machine de dépôt y arrive
très bien, même s'il y en a beaucoup ! C'est simplement la marge et les swing qui peuvent à la
rigueur poser problème. »* Il a raison, et c'est mesuré. Sur la série d'échelle du random75 :

| | sursauts émis | médiane / hystérésis | **sous 1,5× hyst** | **T_min médian** | verdict |
|---|---|---|---|---|---|
| ×0,5 | 217 | 29× | 🔴 **20,7 %** | 🔴 **0,029** | 0/375 |
| ×1 | 417 | 127× | 0,0 % | 0,162 | 🟢 241/662 |
| ×1,5 | 565 | 233× | 0,2 % | 0,230 | 1/440 |
| ×2 | **728** | 94× | 0,3 % | 🔴 **0,055** | 0/404 |

**Le ×2 a le PLUS d'extrema et le moins de sursauts marginaux, et il échoue.** Le nombre de
points tournants n'a aucun rapport avec la fragilité. Les deux causes réelles sont **la marge
du sursaut face à l'hystérésis** (×0,5) et **le plancher photométrique** (×0,5 et ×2).

📏 `scripts/serie_echelle_r75.py`, `reports/serie_echelle_r75/`.

#### Trois affirmations du projet, réfutées par la mesure

| affirmation | statut au 2026-08-15 |
|---|---|
| « les espaceurs demi-onde ont un swing optique nul, aucun extremum » | 🔴 **FAUX** — les 5 espaceurs du 99c offrent **65 à 133 λ utilisables** chacun. **Zéro couche muette sur 99**, médiane 79 λ. Le swing crête-à-crête d'une demi-onde n'est pas nul ; c'est son écart début-fin qui l'est. |
| « le 99c plante en `LEVEL_UNREACHABLE` » | 🔴 **FAUX** — 17 %, contre 83 % de `TP_MISCOUNT`. |
| « plus d'extrema ⟹ comptage plus fragile » *(écrit par moi le soir même)* | 🔴 **FAUX** — testé : à 64 points le comptage est **identique** à celui de la densité machine (0,125 nm) pour ×0,5 / ×1 / ×1,5 / ×2. Pas d'aliasing. |

⚠️ **La densité d'échantillonnage reste néanmoins 17 à 127 fois plus grossière que la
machine** — 0,10 à 0,38 point/nm contre 8,0 (0,125 nm par tour à 4 Hz, §18-1). Sans effet
mesuré sur le comptage, mais c'est un écart au réel non maîtrisé, et le paramètre prévu pour
le corriger, `machine_sampling_dd`, reste **inatteignable** (A8).

#### 🔴 `n_deposables` N'EST PAS UNE MESURE DE FAISABILITÉ — ne le lis plus comme telle

👤 a repéré l'incohérence : *« pourquoi [0,50) est plus élevé que [0,48) ? »* et
*« comment [0,68) peut-il être déposable 39 fois alors que [0,66) ne trouve aucun ? »*

**L'argument qui tranche, et il est logique, pas empirique** : la surveillance de la couche
`i` ne dépend que des couches `0..i`. Donc `[0,50)` contient exactement l'histoire de
`[0,48)`, et **aucune difficulté physique de [0,48) ne peut disparaître dans [0,50)**. Une
inversion est donc impossible sans défaut d'instrument.

**Le défaut** : `n_strats` est produit par la DP de Phase B, qui optimise un coût et ignore le
plantage. Il varie **d'un facteur 2** entre longueurs voisines — 205 à `[0,48)`, 412 à
`[0,52)`. Le dénominateur bouge autant que le numérateur.

🟢 **Ce qui reste valide : le TAUX, en tendance sur beaucoup de points.** Sur 270 intervalles,
`r = −0,869` entre la longueur et le taux, et l'effondrement est monotone :

| couches | 20-29 | 30-39 | 40-49 | 50-59 | 60-69 | 70-99 |
|---|---|---|---|---|---|---|
| taux moyen | **96,4 %** | 81,8 % | 57,3 % | 29,5 % | 2,7 % | **0,7 %** |

🔴 **Ne lis JAMAIS une cellule isolée, ni un écart entre deux longueurs voisines.**

#### 🔴 « AUCUNE_DEPOSABLE » NE VEUT PAS DIRE « INFAISABLE »

**Prouvé, logiquement puis expérimentalement.** `[0,66)` déclarait 0 déposable en fast alors
que `[0,68)`, `[0,70)`, `[0,72)` et `[0,74)` en avaient — or tronquer l'une d'elles après la
couche 65 donne une stratégie valide pour `[0,66)`. Vérification :

| mode | stratégies | déposables | plantage min |
|---|---|---|---|
| fast (campagne) | 319 | **0** | 100 % |
| **premium** | 488 | **1** | **0,0 %** — SEEL 0,658 nm |

⚠️ **Conséquence sur §23.8** : le « 248/249 déposables » et surtout le « seul sous-empilement
infaisable, `[22,78)` » ne sont **pas** des mesures de faisabilité. `[22,78)` est contredit
par `[22,99)` qui en a une. **5 intervalles sur 270 portent encore ce verdict** — tous à
revérifier en premium : `[0,66)` ✅ levé, `[0,76)`, `[0,78)`, `[22,78)`, `[34,99)`.

📏 `scripts/verif_66_vs_68.py`, `reports/verif_66_vs_68/`.

#### 🟢 Le résultat principal a été audité, et il tient

26 intervalles sur 270 contiennent des **tirages plantés** (2 à 4 %), qui se **cumulent** à
l'assemblage. Sur 440 partitions, **2 ont une P95 contaminée**. 🔑 **La gagnante
`0-22 / 22-72 / 72-99` est à 0,0 % de tirages plantés : son 0,760 nm n'était pas contaminé.** ⚠️ Il était en revanche **biaisé vers le bas par l'estimateur** — voir §23.12.

⚠️ `classer_partitions.py` **ne vérifie pas** ce point. À ajouter avant tout nouveau classement.

#### 🔴 LE TROU ACTIONNABLE : la marge est calculée, exposée, et ne décide de rien

`turning_point_margins` (`certus_strat_growth.py:318`) rend deux marges par couche et par
tirage — `margin_missed` (un extremum à un cheveu de ne pas être vu) et `margin_fab` (à un
cheveu d'être inventé). Elles remontent en `all_m_missed` / `all_m_fab`
(`certus_strat_batch.py:542`), sont réduites en `margin_profile`
(`certus_strat_robustness.py:2036`) et exposées en `critical_layer` et `margin_by_layer`. Le
code porte ce commentaire :

> 🔴 **NEEDED FOR RANKING**

**Et aucun module de classement ne les lit** : zéro référence dans `certus_strat_ranking.py`,
`certus_strat_solvers.py`, `certus_strat_objectives.py`. La clé `rank_key_seel_yield_margin`
existe et est testée — elle ne tourne que dans `probe_anchor_noise_pipeline.py`.

🔑 **C'est la grandeur qui porte sur la cause réelle de 83 % des échecs.** Même classe de
défaut que `machine_sampling_dd` : calculée, documentée comme prédictive d'un facteur 22, et
sans effet sur aucune décision.

#### Ce qui a été testé et ne change rien

🟠 **Exiger un point tournant en Phase A : aucun effet.** `require_turning_point` implanté
(comptage O(1) par λ, désactivé par défaut), testé en **exclusion sèche** — le cas extrême :

| | OFF | ON |
|---|---|---|
| 48c | 0,1726 nm — 301/330 | **bit à bit identique** |
| 35c | 0,5251 nm — 248/254 | **bit à bit identique** |

Le paramètre atteint bien le calcul — vérifié par un test destructif (seuil 999 → pipeline
effondré en 2,4 s), donc ce n'est **pas** un `machine_sampling_dd`. Les candidates sans point
tournant sont sur des couches de **bord** (0 et 47), que le coût Monte-Carlo écartait déjà.
**Si l'exclusion sèche ne bouge rien, aucun coût doux ne le fera.** Réglé sur ces deux
composants ; **non testé** sur le 99c et sur les échelles extrêmes.

🟠 **La « phase intermédiaire entre A et B » proposée par 👤 existe déjà** : c'est la DP de
`_find_k_best_groupings_dp_sequential`, exacte et non heuristique. Rien à ajouter.

📏 `scripts/test_require_tp.py`, `scripts/probe_tp_admissibilite.py`,
`scripts/probe_turning_points.py`, `scripts/profil_monitorabilite.py`.

---

### 25.12. 🔴 LE CLASSEMENT DU 15/08 ÉTAIT BIAISÉ — campagne premium du 2026-08-16

#### 🔴 CORRIGÉ LE 2026-08-16 — le 0,760 nm était biaisé vers le bas, et la championne a changé

La campagne premium (N = 150, `dp_top_k` = 40, 250 intervalles, 38,2 h cumulées sur 6 shards)
rejoue le classement. **La malédiction du vainqueur annoncée en §23.9 s'est matérialisée**, et
son ampleur se mesure sur **la même partition** passée dans les deux caches :

| partition | fast (N = 50) | premium (N = 150) |
|---|---|---|
| `0-22 / 22-72 / 72-99` — championne du 15/08 | 0,760 nm | 🔴 **0,858 nm** (+12,9 %) |
| `0-22 / 22-42 / 42-76 / 76-99` — **championne premium** | 0,803 nm | 🟢 **0,782 nm** |

🔑 **Le chiffre à citer est désormais 0,782 nm**, à **4 témoins**, partition
`0-22 / 22-42 / 42-76 / 76-99`. 436 partitions assemblées, **31 à égalité** (δ = 3,0 % à
N = 150), étendue +11,6 %, 2 partitions rejetées pour plantages cumulés > 5 %.

**Pourquoi le fast surestimait.** À N = 50 la P95 est la 47,5ᵉ statistique d'ordre : mal
estimée. Prendre le **minimum sur 440 partitions** avec un estimateur bruité biaise vers le
bas. Ce n'est pas une erreur de calcul, c'est une propriété de la sélection.

⚠️ **La comparaison mélange deux effets** et on ne les a pas séparés : davantage de tirages
(meilleure P95) **et** une stratégie différente retenue par intervalle en premium. La
conclusion tient dans les deux cas — le 0,760 n'est pas reproductible sous un protocole
meilleur — mais l'attribution reste **non mesurée**.

🔴 **Règle qui en découle, et elle vaut pour tout ce document** : un SEEL issu d'un
**minimum sur un grand nombre de candidats** évalués à N = 50 n'est pas publiable. Il faut le
rejouer à N = 150 sur le candidat retenu.

📏 `reports/intervalles_99c_premium/`, `scripts/classer_partitions.py --mode premium`.
