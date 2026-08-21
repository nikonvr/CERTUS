# SEEL — l'erreur équivalente par couche

> Ce dossier **fait autorité** sur SEEL : sa définition, sa quantification, la règle de tri
> qu'il commande, et ce qui reste à faire. `CLAUDE.md` n'en garde qu'un renvoi.

🔑 **Pourquoi ce dossier existe.** Extrait de `CLAUDE.md` §22 le 2026-08-19, quand le fichier
a touché **1 989 lignes sur 2 000** pour la seconde fois de la journée. §22 en pesait 251, dont
**106 pour SEEL seul** — dont l'essentiel est un **journal de révisions** (la quantification
passée de 0,1 nm à 0,01 nm le 14/08, les tableaux de largeur de classe, le code testé et mort)
qui n'a pas à être relu à chaque session.

⚠️ **Rien n'a été résumé ni réécrit** : le contenu ci-dessous est celui de §22, déplacé tel quel.

---

### 👤 SEEL — l'erreur équivalente par couche, et sa précision de 0,1 nm

> 👤 *« C'est pour caractériser la performance d'une stratégie donnée. On regarde quel tirage
> aléatoire donne une erreur spectrale du même niveau, et cela donne une erreur moyenne
> équivalente par couche. »* — *« SEEL doit être calculé ou donné avec une précision de
> 0,1 nm, c'est tout. »* (2026-08-10)

**Ce que c'est.** `calculate_seel_analysis` (`certus_strat_service.py:654`) perturbe chaque
couche du nominal par `N(0, σ)` pour `σ ∈ {0,05 ; 0,1 ; 0,3 ; 0,6 ; 1,2 ; 2,0}` nm, 3 lots de
50 tirages, et mesure la RMSE spectrale obtenue. On inverse la courbe : **toute RMSE se lit
alors en nanomètres d'erreur équivalente par couche.** C'est la seule grandeur du projet qu'un
opérateur de bâti comprenne immédiatement.

🔑 **La quantification à 0,1 nm n'est PAS une règle d'affichage — c'est ce qui fait de SEEL un
critère de classement distinct.**

L'ajustement actuel (`certus_strat_service.py:710`) vaut `fit_k = Σxy/Σx²` avec
**`fit_alpha = 1.0` figé en dur** : donc `SEEL = k · RMSE`, une simple constante. Trier sur la
valeur **continue** de SEEL rendrait donc **exactement** l'ordre de la RMSE — un tri qui ne
trie rien.

**Quantifiée à 0,1 nm, elle crée des paliers.** Deux stratégies séparées de moins de 0,1 nm
deviennent **ex æquo**, et il faut un **critère secondaire** pour les départager. Le classement
change réellement, et il change dans le bon sens : *on ne discrimine pas sur un écart qu'on ne
sait pas mesurer.* C'est déjà la règle du §8, qui interdit de conclure d'un écart d'épaisseur
sous 0,05 nm.

👤 **Le critère secondaire est le RENDEMENT** (2026-08-10). La règle de tri complète :

```
1. SEEL arrondi a 0,1 nm          croissant
2. rendement = 1 - taux de plantage   decroissant   <- departage les ex aequo
```

*À performance spectrale indiscernable, on prend la stratégie qui va au bout.* C'est
exactement §15 : *« si 95 % des dépôts fonctionnent, c'est gagné »*, et *« un dépôt qui plante
et un filtre hors spec sont le même échec »*.

⚠️ **L'arrondi se fait sur SEEL, pas sur la RMSE.** Arrondir la RMSE n'aurait aucun sens
physique — c'est un nombre sans unité interprétable. L'arrondi ne devient légitime qu'une fois
la grandeur exprimée en nanomètres, parce que 0,1 nm est une **limite de mesure**, pas une
convention d'affichage.

#### 🔴 Le pas de 0,1 nm est ABSOLU, le bruit statistique est RELATIF — mesuré le 2026-08-11

Le pas fixe appliqué à une grandeur dont l'incertitude est **proportionnelle** fait dériver la
largeur de la classe d'équivalence :

| SEEL de la gagnante | demi-largeur du bin | face au bruit de ±6 % (§24-26) |
|---|---|---|
| **0,3 nm** | **±19 %** | plus large ✅ regroupe correctement |
| 0,6 nm | ±7,8 % | limite — le rang 2 est à **+7,3 %**, indiscernable, et il tombe **hors classe** |
| 1,1 nm | **±4,4 %** | **plus étroit que le bruit** ❌ sépare ce qui n'est pas séparable |

La règle 👤 est donc juste **là où elle a été spécifiée** — près de 0,3 nm, la limite de
mesure — et devient trop fine quand le SEEL grandit. Le correctif n'en change pas l'intention,
il ajoute la seconde limite :

```
demi-largeur de la classe = max( 0,05 nm , 0,06 x SEEL )
```

*On ne distingue jamais en dessous de la limite de mesure, ni en dessous de la résolution
statistique.* Ce sont deux bornes de ce qu'on peut savoir : il faut retenir **la plus
grossière**. À 0,3 nm le 0,05 l'emporte et rien ne change ; à 1,1 nm la classe s'élargit
comme elle le doit.

⚠️ Le **0,06** vient de §24-26 et vaut pour `N = 150`. Il suit `1/√N` — mesuré exact entre
N = 32 et N = 128. **Si la profondeur change, remesure-le, ne l'extrapole pas de tête.**

#### 🔴 REVIREMENT DU 2026-08-14 — la quantification passe de 0,1 nm à 0,01 nm

> 👤 *« SEEL à 0,01 nm près partout »* (2026-08-14).

`SEEL_RESOLUTION_NM` vaut désormais **0.005** (`certus_strat_ranking.py:734`) et
`rank_key_seel_yield_margin` binne à **0,01 nm** (ligne 643). **Tout ce qui précède dans ce
§22 décrit l'état d'avant** : le pas de 0,1 nm et le `max(0,05 ; 0,06 × SEEL)` sont périmés en
tant que description du code.

🔴 **Et le prix du revirement n'est pas mesuré.** À SEEL 0,3 nm, un bin de 0,01 nm face à un
bruit statistique de ±6 % (soit ±0,018 nm) est **près de deux fois plus étroit que le bruit** —
c'est-à-dire exactement le régime que le tableau ci-dessus déclare fautif, « séparer ce qui
n'est pas séparable ». **En pratique : traite un écart d'un bin comme une égalité.**

🔴 **La seconde borne n'est PAS appliquée.** `seel_equivalence_half_width`
(`certus_strat_ranking.py:742`) l'implémente correctement et n'a **aucun appelant en
production** — seulement `tests/unit/test_strat_ranking_rule.py`. Et
`rank_key_seel_yield_margin` **reçoit** `score_resolution_rel` sans jamais s'en servir (corps
ligne 643, bin fixe à `2 × SEEL_RESOLUTION_NM`). La règle « il faut retenir la plus grossière »
est donc du **code testé et mort** : le classement ne connaît que le pas absolu. C'est le
premier chantier de §22, avant tout raffinement.

**Ce qu'il reste à faire :**

| # | Action | Note |
|---|---|---|
| 1 | **Sortir SEEL de l'interface.** Il n'existe qu'en mémoire (`APP_CONTEXT["seel_data"]`), calculé à l'étape 0, et sert à colorer trois colonnes. **Le banc ne le voit pas** — les 26 runs mesurés sont donc tous en unité abstraite. | Coût : ~1 s de calcul, 900 spectres vectorisés |
| 2 | L'écrire dans les rapports de sonde à côté de chaque `RESULT`, et dans `analyse_bands.py` | — |
| 3 | Quantifier à **0,1 nm** partout, affichage compris — le tableau montre aujourd'hui `.3f`, soit 100× la précision utile | 👤 spécifié |
| 4 | Sélecteur de tri : composite (actuel, dominé par le plantage) ou **SEEL quantifié + départage** | c'est le tri qui change vraiment l'ordre |
| 5 | **Vérifier que `alpha = 1` est vrai** et non affirmé | les données sont déjà là : 6 σ × 3 lots |

---

# PARTIE III — L'ÉTAT DU PROJET
