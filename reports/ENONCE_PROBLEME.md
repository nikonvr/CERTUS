# Où changer de verre témoin pendant le dépôt d'un filtre optique de 99 couches ?

Énoncé autonome. Aucune connaissance préalable du projet n'est requise.

---

## 1. Le contexte physique

On dépose un **filtre interférentiel** par évaporation sous vide : un empilement de couches
minces alternées haut indice / bas indice sur un substrat.

- Composant : **passe-bande à 5 cavités Fabry-Pérot couplées**, centré à 633 nm, **99 couches**
- Matériaux : H = Nb₂O₅ (n = 2,3192), L = SiO₂ (n = 1,4832), substrat SiO₂ (n = 1,4832)
- Formule : `Sub / (HL)⁴H · 2L · [(HL)⁹H · 2L]⁴ · (HL)⁴H / Air`
- Les cinq espaceurs demi-onde `2L` sont aux couches 9, 29, 49, 69, 89 (indices 0-based)
- Convention de parité : **indice pair = H, indice impair = L**

### Le contrôle optique

Pendant qu'une couche pousse, on mesure en continu la **transmission d'un verre témoin**
placé dans l'enceinte, à une **longueur d'onde de contrôle** choisie par couche. On arrête
le dépôt quand un extremum de `T` est atteint. Le témoin reçoit exactement les mêmes couches
que la pièce (rapport d'épaisseur **1,00**, vérifié).

**La propriété qui fait tout l'intérêt du contrôle optique** : une erreur d'épaisseur sur la
couche *k* est **partiellement auto-corrigée**. Les couches suivantes, lues sur le **même**
verre, voient l'erreur accumulée, et le point de déclenchement se décale pour l'annuler en
partie. C'est la compensation de Macleod-Bousquet.

### Le problème

Au-delà d'une cinquantaine de couches, le témoin devient **optiquement mort** :

- les espaceurs demi-onde ont un **swing optique nul** pendant leur dépôt — aucun extremum
  sur lequel s'arrêter ;
- les miroirs de 19 couches transmettent **moins de 10⁻⁴** — le signal passe sous le plancher
  photométrique.

**Mesure** : sur les 99 couches en une seule campagne, **les 487 stratégies évaluées plantent
à 100 %** (« plantage » = le dépôt ne peut pas se terminer, niveau d'arrêt inatteignable ou
comptage d'extrema faux). Le composant **n'est pas fabricable** sous contrôle optique continu.

---

## 2. La solution étudiée : plusieurs verres témoins

On fait entrer un **verre témoin NEUF** en cours de dépôt, via un carrousel sous vide (coût
opérationnel nul : ni remise à l'air, ni contamination, ni repompage).

- **La pièce ne quitte pas le plateau** et reçoit les 99 couches d'affilée.
- **Chaque témoin ne voit que sa campagne**, déposée sur verre nu.

### Ce que ça coûte, et c'est le cœur du problème

**La compensation d'erreur ne traverse pas le changement.** Les couches d'après sont lues sur
un verre qui **ne contient pas** les erreurs d'avant. Le résidu de la campagne précédente est
donc **gelé dans la pièce, définitivement incorrigible**. Le spectre final porte
`erreur(campagne 1) + erreur(campagne 2) + …` **sans terme croisé**.

### Contraintes

- **Entre 20 et 60 couches par verre témoin** (contrainte de l'expérimentateur).
- **La position de changement doit être PAIRE.** Une campagne doit ouvrir sur une couche H :
  le L est du SiO₂ **adapté en indice** au substrat de SiO₂, donc une couche L sur verre nu
  ne produit **aucun signal**. Un témoin qui ouvrirait sur une L serait aveugle dès sa
  première couche.
- Ces contraintes donnent **441 partitions admissibles** : 11 à 2 témoins, 210 à 3, 220 à 4.
  **5 témoins est impossible** (5 × 20 = 100 > 99).

---

## 3. La métrique

**SEEL** = erreur d'épaisseur équivalente par couche, en nanomètres.
`SEEL = 2 × √(RMSE_P95)`, où le RMSE est l'écart spectral entre le filtre simulé sous
perturbations et le filtre nominal, au 95ᵉ centile sur N tirages Monte-Carlo.

- Repères sur d'autres composants : dichroïque 48 couches → **0,17 nm** ; passe-bande 35
  couches → **0,53 nm**. ⚠️ Ces composants n'amplifient pas l'erreur de la même façon qu'un
  5 cavités : la comparaison n'est **pas** un jugement de méthode.
- **Cible visée : 0,30 nm.**
- **Résolution de la mesure** : la résolution statistique relative d'un score vaut 6 % à
  N = 150 et suit `1/√N`. À N = 50, elle vaut 10,4 % sur le RMSE, soit **5,1 % sur le SEEL**.
  Deux valeurs séparées de moins que ça sont **à égalité**, pas classées.

---

## 4. Ce qui a été mesuré

### Les sous-empilements pris isolément sont monitorables

Chaque intervalle `[a, b)` du design, **déposé sur verre nu**, est évalué comme un composant
à part entière. Sur **236 intervalles** mesurés (20 à 60 couches, bornes paires) :

- **235 sont déposables** — au moins une stratégie à moins de 5 % de plantage, souvent
  des centaines ;
- **1 seul ne l'est pas** : `[22, 78)`, 56 couches, meilleur plantage 56 % sur 259 stratégies ;
- les plus fragiles (1 ou 2 stratégies déposables) font tous **48 à 60 couches**.

🔑 **Résultat contre-intuitif** : ce n'est **pas la longueur** qui gouverne. `[48, 99)` fait
**51 couches** et rend **293** stratégies déposables ; `[0, 32)` en fait 32 et n'en rend que
180. Le **dernier** tiers du design — là où, en campagne unique, il ne reste plus qu'**une
seule** longueur d'onde viable — est le **plus facile** des trois sur verre nu. Le modèle
« le témoin vieillit et meurt » est donc **réfuté par la mesure**.

### Un premier assemblage complet

Partition en trois témoins aux couches 0 / 32 / 66 :

| | RMSE P95 | SEEL | plantage |
|---|---|---|---|
| pièce assemblée, 3 témoins | 0,184946 | **0,860 nm** | **0 %** sur chacune des 3 campagnes |
| référence en campagne unique | 0,187761 | 0,87 nm | **100 %** — score de repli, inatteignable |

**Le multi-témoins ne fait pas gagner en précision. Il fait passer d'impossible à possible.**
La cible de 0,30 nm n'est pas atteinte (facteur 2,9).

---

## 5. La méthode d'assemblage

Pour noter la **pièce** à partir de campagnes indépendantes :

1. **Aucun tirage n'est refait.** On concatène les épaisseurs **réellement simulées** de
   chaque campagne, tirage par tirage. Refaire un tirage introduirait un aléa neuf et
   détruirait ce qu'on mesure : les erreurs *commises*, sans compensation croisée.
2. **Même graine pour toutes les campagnes**, afin qu'elles partagent la **réalisation du
   corridor d'indice** — les matériaux sont les mêmes dans la machine, c'est un seul dépôt.
3. **Mais le bruit de lecture doit rester indépendant.** Il est modélisé comme **un processus
   continu sur les 99 couches**, dont chaque campagne lit **sa tranche**. Sans cela, trois
   campagnes à la même graine ont un bruit corrélé à **78 %** au lieu de **1 %**.
4. **Faisabilité et spectre sont deux mesures distinctes** : la faisabilité s'établit campagne
   par campagne (chacune sous 5 % de plantage), le spectre sur l'assemblage — qui ne porte
   aucun taux de plantage.
5. **Contrôle obligatoire** : concaténer les épaisseurs **nominales** des parties doit
   reproduire le design complet. Mesuré : **écart 0,000e+00** sur les épaisseurs et sur le
   spectre.

**Économie du calcul** : les 441 partitions ne partagent que ~251 intervalles distincts. On
mesure les **intervalles** une fois chacun, puis toute partition s'assemble **à coût nul**.

---

## 6. Les questions ouvertes

### Q1 — La sélection gloutonne par campagne est-elle rédhibitoire ?

Chaque intervalle a jusqu'à **306** stratégies déposables. On en retient **une seule** : la
mieux notée **contre le spectre du sous-empilement isolé**, qui n'est pas le spectre du
produit final.

Rien ne garantit que la meilleure stratégie de la campagne 2 *prise seule* soit celle qui
minimise l'erreur **assemblée**. L'optimum global demanderait d'explorer les combinaisons —
306³ pour trois campagnes.

**Faut-il lire ce lot comme une borne supérieure honnête, ou la sélection gloutonne
invalide-t-elle la comparaison entre partitions ?**

### Q2 — L'assemblage est-il physiquement correct ?

On compose des campagnes indépendantes en concaténant leurs épaisseurs simulées, avec
réalisation d'indice partagée et bruit de lecture en tranches. **Qu'est-ce qui manque ?**

Points connus comme non modélisés : le temps de rotation du carrousel (obturateur ouvert, la
pièce reçoit de la matière non comptée ; fermé, la source dérive thermiquement) ; et
l'estimation de vitesse au quartz, qui **n'est délibérément pas coupée** au changement de
témoin — donc un sous-empilement mesuré isolément part sans historique de vitesse, alors
qu'en séquence réelle il en hériterait. Cette dernière approximation est **pessimiste**.

### Q3 — Existe-t-il une meilleure formulation du problème ?

Le problème est posé comme un **pavage** : quels intervalles sont déposables, et quel
enchaînement d'intervalles minimise le SEEL de la pièce. Le nombre minimal de témoins devient
un **plus court chemin** dans un graphe dont les arêtes sont les intervalles déposables.

**Y a-t-il une formulation plus juste, ou une grandeur qu'on ne mesure pas et qui gouverne ?**

⚠️ Contrainte explicite : la règle cherchée doit être **générale**, valable au-delà de ce
filtre particulier. Une règle qui a besoin de savoir où sont les cavités n'est pas une règle —
c'est la réponse d'un seul composant. Les grandeurs admissibles sont celles qui se calculent
sur un empilement **dont on ignore la famille**.

### Q4 — Le risque statistique est-il correctement traité ?

221 partitions sont classées sur **une seule graine**. Le meilleur sera sélectionné parmi
elles, donc **systématiquement le plus chanceux** (malédiction du vainqueur). Les parades
prévues : écart supérieur à la résolution de 5,1 % ; intervalle le plus faible ayant au moins
10 stratégies déposables ; et maintien dans le premier décile sur une seconde graine.

**Est-ce suffisant, et le prédicteur à engager avant la mesure est-il le bon ?** Celui retenu
est *le nombre de stratégies déposables de l'intervalle le plus faible de la partition*.
