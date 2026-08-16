# 18bis. 🔴 ÉTAT RÉEL DE L'IMPLANTATION — établi contre le CODE

> Extrait de `CLAUDE.md` le 2026-08-16. Ce contenu **fait autorite** ;
> `CLAUDE.md` n'en garde qu'un renvoi. 🔑 **Un fait, un seul endroit** — si tu corriges
> quelque chose ici, ne le recopie pas ailleurs, mets un lien.

---


👤 *« Je suis persuadé que tout était implanté, même la résolution. »* **Ce n'est pas le
cas**, et ce tableau existe pour que la question ne se repose jamais. Il est établi en
lisant le **code**, pas ce document.

⚠️ **Pourquoi la confusion est légitime.** Ce document et
[`pages/CERTUS_STRAT.html`](pages/CERTUS_STRAT.html) décrivent longuement des mécanismes
— la résolution du monochromateur y a une section entière — **sans jamais dire s'ils
sont câblés**. Une spécification bien écrite se lit comme une description. C'est le
défaut de tenue le plus coûteux de ce dépôt, et ce tableau est le correctif.

| Spécifié en | Quoi | État réel |
|---|---|---|
| **§12.7** | **Résolution du monochromateur** | 🟢 **facteur de bruit, √3 et biais de fente FAITS le 2026-08-11.** Reste A18, la fente comme variable de recherche. Détail ci-dessous. |
| **§12.4 / A8** | Grille d'échantillonnage machine à 0,125 nm, découplée | 🔴 **NON.** `machine_sampling_dd` n'existe pas. `SAMPLE_DD` vit **à l'intérieur** de `if smoothing_window > 1` — la soudure de §17-2, toujours ouverte. |
| **A9** | Moyenne glissante **centrée** | 🔴 **NON, elle est CAUSALE.** Vérifié : la fenêtre court sur `[i−k+1 … i]` (`certus_strat_growth.py`, boucle `idx_w`). Décalage de `(k−1)/2` échantillons, soit **0,44 nm à k = 8**, alors que §9bis-5 pose « aucun retard » en postulat. §17-3 reste ouvert. |
| **§12.5 / A16** | Quantification de l'arrêt en `U(0 ; 0,125 nm)` | 🔴 **NON.** L'arrêt reste une **inversion parabolique continue**. La constante existe depuis aujourd'hui (`RATE_TURN_NM`) mais pour le Rate seulement. |
| **§14** | **Mode Rate** | 🟠 **NOYAU ÉCRIT LE 2026-08-11, PAS ENCORE UTILISABLE.** Le calcul d'épaisseur, l'effacement d'historique et la remontée `rate_layers` sont câblés. Manquent : le **drapeau utilisateur**, la **génération de variantes** et l'affichage. |
| **§14, action 1** | SEEL dans le pipeline | 🔴 **NON.** SEEL est calculé à l'**étape 0 de l'interface** (`calculate_seel_analysis`) et n'atteint jamais le classement. Le tri de §14 tourne donc **dans la sonde**, à côté. |
| **§17-18** | `consensus_num_runs` surchargeable | 🟠 Il **existe** (défaut 150, `certus_strat_ui_state.py:1150`) mais **aucune surcharge ne l'atteint**. Toute mesure avec consensus actif tourne donc à 150 tirages quoi qu'on demande. |
| **§17-9** | `MachineModel` consommé en production | 🔴 **NON.** Toujours aucun consommateur réel. |
| **A23** | Couche critique, marge | ✅ **FAIT le 2026-08-11**, étages 0, 2 et 3, validé §17-41. |
| **A10** | Corridor côté notation | ✅ fait |
| **§12.1** | Distorsion affine, drapeau POEM | ✅ fait, mesuré ×41,2 |

### 🟢 La résolution, en détail — état vérifié dans le code le 2026-08-11 au soir

⚠️ **Ce tableau disait « rien n'est implanté » le matin même. Il a été refait ligne par
ligne contre le code, pas contre ce document** — c'est précisément le défaut de tenue que
§18bis existe pour corriger, et il s'y reprenait lui-même.

| ce que §12.7 demande | état |
|---|---|
| Le **facteur de bruit** ÷1,5 / ×1 / ×2 / ×5 selon la fente | ✅ `RESOLUTION_NOISE_FACTOR`, `certus_strat_robustness.py:173`. Une **table de 4 entrées**, et une fente absente de la table **lève** au lieu d'interpoler — §12.7 interdit la loi de puissance, qui autoriserait des réglages que la machine n'a pas. |
| La **correction √3** (fente rectangulaire) | ✅ `res_limit = test_bw * np.sqrt(3.0 * T_tolerance / curvature)`, ligne 637. |
| Le **biais de niveau** appliqué au signal lu | ✅ et c'est un **profil variant avec l'épaisseur**, pas une constante — voir l'encadré ci-dessous, c'est le fond du sujet. |
| La fente **rendue** à l'utilisateur | ✅ `monochromator_resolution_nm` est dans le résultat (ligne 1697) et surchargeable par `CERTUS_RESOLUTION_NM`. |
| La fente comme **variable de recherche** (A18) | ❌ **non.** Elle est un **réglage** qu'on impose au run, pas une dimension que la Phase B explore. Les 4 résolutions ne sont pas mises en concurrence. |
| `min_resolution` comme **critère** | 🟠 calculée, sert de **départage dans le tri** (`certus_strat_ranking.py:665`), mais **elle ne rejette rien** — §20-contrôle 4 : compter les rejets avant de la câbler. |
| La **convolution complète** du signal | ❌ non, et c'est assumé : le biais est un terme additif par couche et par épaisseur, pas une intégration spectrale dans la boucle chaude. |

### 🔑 Et la conséquence que 👤 souligne, qui est le cœur du problème

> 👤 *« Le calculateur OMS d'arrêt des couches ne tient pas compte de la largeur des
> fentes et se trompera sur la valeur du niveau à atteindre. »*

C'est exactement le mécanisme de §12.7, et il impose une **asymétrie qu'il ne faudra pas
inverser** :

```
ce que la machine ATTEND :  T_theorique(lambda_mon)   monochromatique, resolution PARFAITE
ce que la machine LIT     :  <T(lambda)> moyenne sur la fente
biais = <T>_B - T(lambda_mon) = T''(lambda_mon) . B^2 / 24
```

🟢 **C'est implanté depuis le 2026-08-11**, et dans le bon sens : le biais va sur le
**signal lu** (`Ts_r`), la **cible reste au calcul parfait** (`Ts_n`, `target_nominal`).
Biaiser les deux annulerait exactement l'effet — c'est le mode de défaillance que §12.1 a
déjà rencontré trois fois sur la distorsion affine.

👤 *« Je ne veux pas être optimiste sur les fentes mais réaliste »* (2026-08-11) : le biais
est donc **actif par défaut**, à la fente nominale de 2 nm.

### 🔴 LE BIAIS DE FENTE EST UN PROFIL, PAS UNE CONSTANTE — 2026-08-11

> 👤 *« Essaie de modéliser plus fidèlement les fentes, sans pour autant exploser le budget
> temps. »*

#### Ce qui n'allait pas, et c'est plus grave qu'une imprécision

Le biais valait **un nombre par couche**, ajouté identiquement à toutes ses lectures. Or

> **une constante ajoutée au signal lu est exactement le `b` de `T → a·T + b`, et §12.1 a
> démontré POEM rigoureusement invariant par cette transformation.**

📏 **Mesuré au noyau, arrêt d'une couche sous POEM :**

```
  biais constant = 1e-4   ->  deplacement de l'arret  -3,11e-11 nm
  biais constant = 1e-3   ->                          -1,61e-11 nm
  biais constant = 1e-2   ->                          -1,80e-11 nm
```

**Une constante de 1e-2, soit vingt fois l'amplitude du bruit de lecture, déplace l'arrêt de
1,8e-11 nm** — neuf décades sous les 0,05 nm en dessous desquels §16 interdit de conclure
quoi que ce soit.

🔑 **L'ancien modèle donnait donc à POEM la seule forme qu'il absorbe gratuitement**, et ne
modélisait rien de celle qu'il ne peut pas absorber. §12.7 l'avait pourtant écrit d'avance :
le biais *« dépend de la courbure locale, donc il diffère à chaque ancre et au point de
déclenchement »*.

⚠️ **Ne pas surinterpréter : l'ancien modèle n'était pas inerte partout.** Il mordait par les
chemins **non** invariants — comptage des points tournants (`Ts_n` n'est pas biaisé),
atteignabilité, repli absolu — d'où les plantages qu'il faisait apparaître. Il était inerte
sur **l'épaisseur d'arrêt sous POEM**, ce qui n'est pas la même chose.

#### De combien le biais varie-t-il vraiment pendant une couche

📏 Juge de paix, λ = 544 nm — **la λ qu'utilisent les vingt meilleures stratégies** — fente
B = 2 nm, biais échantillonné à `d = 0`, `d_nom/2` et `d_nom` :

| couche | variation dans la couche | \|biais\| moyen |
|---|---|---|
| 10 | 0,07 A | 0,04 A |
| 20 | 0,84 A | 0,93 A |
| 30 | 1,52 A | 2,96 A |
| 40 | 21,8 A | 15,96 A |
| 44 | 44,4 A | 30,93 A |
| **46** | **62,2 A** | 34,96 A |

**Le biais bouge de 62 fois l'amplitude du bruit à l'intérieur d'une seule couche.** C'est
cette variation qui décale les deux ancres de POEM de quantités différentes, et le niveau de
déclenchement d'une troisième.

#### Ce qui remplace la constante

Un **profil de 17 nœuds** sur l'axe `u = d / d_nominal ∈ [0 ; D_SCAN]`, lu par interpolation
linéaire (`slit_bias_at`). Trois propriétés, chacune un défaut corrigé :

1. **Le biais suit l'épaisseur.** C'est le point.
2. **Chaque couche d'historique porte SON profil.** L'historique de bloc rejoué est fait de
   lectures prises à travers la même fente mais sur des sous-empilements différents, donc à
   des courbures différentes. Appliquer le biais de la couche `i` au rejeu de la couche `j`
   fabriquait les ancres que POEM lit ensuite.
3. **Les trois points de l'inversion parabolique portent chacun le biais de SA position.**
   Une constante commune sort de la courbure de la parabole et n'en décale que l'ordonnée ;
   ce sont les biais **différents** qui l'inclinent, et c'est l'inclinaison qui déplace la
   racine.

#### La boxcar est INTÉGRÉE, plus développée

`⟨T⟩_B − T(λ)` est évalué par **Gauss-Legendre à 3 nœuds** au lieu d'être tronqué à
`T''·B²/24`. Trois nœuds intègrent exactement un polynôme de degré 5, et les ordres impairs
s'annulent par symétrie : **on gagne deux ordres, pas un.**

📏 Contre une référence Gauss-Legendre à 15 nœuds, erreur en % de la référence :

| filtre | B | couche | GL3 (retenu) | 2ᵉ ordre (ancien) |
|---|---|---|---|---|
| dichroïque 48c | 2 nm | 46 | **0,04 %** | 9,38 % |
| dichroïque 48c | 5 nm | 40 | **0,97 %** | 8,72 % |
| dichroïque 48c | 5 nm | **46** | **8,86 %** | **330,07 %** |
| passe-bande 3cav | 2 nm | 33 | **0,02 %** | 1,21 % |
| passe-bande 3cav | 5 nm | 28 | **0,99 %** | 13,19 % |
| passe-bande 3cav | 5 nm | 33 | **0,64 %** | 17,27 % |

🔑 **À la fente nominale de 2 nm le développement était acceptable ; à 5 nm il s'effondre.**
Et 5 nm est exactement la fente qui décide du bonus de bruit ÷1,5 de §12.7. **Le
développement se trompait le plus là où la décision se prend.**

#### Le coût, et pourquoi il ne fait pas exploser le budget

Le profil est calculé **une fois par (couche, λ), hors de la boucle Monte-Carlo**, et le cache
est **partagé entre toutes les stratégies** — elles diffèrent par leur découpage en blocs,
bien moins par les λ qu'elles emploient. Dans la boucle chaude, le surcoût est une
interpolation linéaire au lieu d'une addition scalaire.

⚠️ **L'approximation qui reste, et elle est assumée** : le profil est bâti sur l'empilement
**nominal**. À chaque tirage le sous-empilement réel diffère de quelques nm, donc la courbure
vraie aussi. Modéliser cette modulation-là mettrait une intégration spectrale **dans** la
boucle chaude — précisément le coût que §12.7 signalait. La part systématique, qui est tout
l'effet au premier ordre, est capturée ; sa modulation tirage à tirage ne l'est pas.

#### Vérifications

| # | Contrôle | Résultat |
|---|---|---|
| 1 | C1 : profil absent ≡ profil nul | **bit-identique** (`float.hex()`) |
| 2 | Piège 1 : le profil atteint-il le calcul ? | amplitude ×10 ⇒ déplacement ×10, sur trois décades |
| 3 | Une constante est-elle absorbée ? | oui, à 1,8e-11 nm pour 20 A |
| 4 | L'axe du profil est-il celui du balayage ? | `D_SCAN_VAL` est **un seul objet**, partagé |
| 5 | Bords | **bornés, jamais extrapolés** |

🔴 **Le test 3 ne peut pas échouer sur l'ancien code — il ne peut même pas y être écrit**,
puisqu'un biais scalaire n'a aucune autre forme à quoi être comparé. C'est bien le sujet : le
défaut n'était pas un mauvais chiffre, c'était **un degré de liberté manquant**.

### 🔴 LA PHASE A VOIT ENFIN LA FENTE — le septième paramètre de §17-23

§17-23 recensait **six** paramètres de modèle que la Phase A laissait à leur valeur neutre.
La fente était le **septième**, et c'est celui qui change **quelle λ est retenue**.

Le mécanisme, et il n'a rien de subtil : la Phase A classe les candidates à la dynamique du
signal ; la meilleure dynamique est au **bord de bande** ; et c'est précisément là que
l'ondulation spectrale est la plus fine — **7,2 nm de période à 48 couches pour une fente de
2 nm**. Juger en aveugle, c'est choisir exactement les λ que l'instrument réel ne peut pas
exploiter.

📏 **Vérifié par comptage** (§20-contrôle 4), couche 40, 21 candidates de 500 à 600 nm :
la **seule** candidate dont le verdict change est **540 nm** — le bord de bande — qui passe
de **0 % à 100 % de plantage** dès que la Phase A reçoit le profil. Toutes les autres sont
inchangées. Un filtre qui rejette exactement ce qu'il doit rejeter, et rien d'autre.

**Les deux points d'appel, et il fallait les deux :**

| | où | ce qui manquait |
|---|---|---|
| jugement des candidates | `certus_strat_batch.py`, `validate_wavelengths_batch` | l'appel s'arrêtait à `nL_real` |
| propagation d'état | `certus_strat_growth.py`, `update_run_states_kernel` | 16 arguments à un noyau qui en compte 22 |

Le second n'est pas un détail : le docstring du noyau énonce lui-même la règle violée —
*« les états propagés ici deviennent l'historique sur lequel la couche suivante sera jugée »*.
Propager sans la fente pendant que les candidates sont jugées avec elle rendrait la Phase A
**incohérente avec elle-même**, une couche plus loin.

⚠️ **Le profil est indexé PAR CANDIDATE**, forme `(n_candidates, n_couches, nœuds)`. Le biais
dépend de la λ de monitoring, et c'est exactement ce que cet étage fait varier : une matrice
unique par couche donnerait à toutes les candidates la courbure de la sortante — le filtre
inerte de §20-contrôle 4.

🔑 **Et l'absorption par POEM est CONDITIONNELLE — mon premier test l'a énoncée comme
générale et il a eu raison d'échouer.** Sans historique de bloc, POEM n'a pas d'ancres et
retombe sur le **niveau absolu**, la branche que §12.1 a démontrée non invariante :
📏 une constante de 1e-4 y déplace l'arrêt de **0,0388 nm**. Avec des ancres, la même
constante ne déplace rien. Les deux faces sont désormais épinglées par un test chacune.

📏 **Coût mesuré** : 5,4 ms par profil, cache partagé entre appels et entre stratégies —
`(couche, λ, sous-empilement)` comme clé, parce que deux designs partagent le processus.
Sur la Phase A : 12 048 profils distincts, **65 s**. ⚠️ Le cache **doit** vivre plus
longtemps qu'un appel : à cache par appel, la mesure du 2026-08-11 donnait **28 appels,
64,1 s, 8,8 % du run** pour un travail qui en vaut 1,4 s.

### 👤 Ce qu'une stratégie doit rendre, et ce qu'elle rend

> 👤 *« Trouver une stratégie, c'est trouver les λ de contrôle ou les couches de rate, et
> donner à l'utilisateur une valeur des fentes. »*

| | rendu aujourd'hui |
|---|---|
| λ de contrôle par bloc | ✅ |
| couches en Rate | 🟠 le champ `rate_layers` existe depuis le 2026-08-11, la génération non |
### 🔴 SURVEILLANCE PAR BLOCS DU 35 COUCHES : LE RAYON D'ACTION x20 DÉVERROUILLE LES BLOCS COMPACTS (4 À 6 BLOCS) — 2026-08-14

> 👤 *« Y a-t-il moyen d'augmenter d'un facteur 20 le nombre de stratégies testées par le code nominal sur le 35c ? Peut-être qu'en augmentant le rayon d'action on trouvera des stratégies avec des blocs. »*

#### Le constat et la cause racine de l'aveuglement antérieur
Sur le passe-bande résonant 35 couches (3 cavités Fabry-Pérot à 633 nm), le solveur standard ne proposait que des stratégies à 35 longueurs d'onde différentes (1 bloc/couche).
L'exploration exhaustive combinatoire ($48\,000$ évaluations) et le run nominal élargi ont prouvé que **l'entonnoir de programmation dynamique à `top_k = 40` était un goulet d'étranglement combinatoire** :
- À `top_k = 40`, les partitions de couches en blocs multi-couches étaient éliminées dès le filtrage statique initial de Phase A.
- En ouvrant l'entonnoir à **`top_k = 800` ($\times 20$)**, `k_keep_survivors = 200` et `mining_candidates_limit = 60000`, le solveur a découvert des **stratégies à 4, 5 et 6 blocs à 0,0 % de plantage qui égalent ou battent la référence historique à 35 longueurs d'onde** :

| Nombre de Blocs | Stratégie Gagnante | Type de Générateur | Taux de Plantage | Score RMSE P95 ($N=300$) | vs Réf Historique 35-$\lambda$ ($0{,}06085$) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **35 blocs** | **ID 36009** | ELITE | **0,0 %** | **`0.04931`** | **$-19{,}0\,\%$ (Nouveau record absolu)** |
| **7 blocs** | **ID 900000016** | ELITE | **0,0 %** | **`0.06105`** | **Quasi identique** ($+0{,}3\,\%$) |
| **6 blocs** | **ID 900000000** | ELITE | **0,0 %** | **`0.05957`** | **$-2{,}1\,\%$ (BATTUE à 6 blocs !)** 🏆 |
| **5 blocs** | **ID 990000379** | RATE_L15 | **0,0 %** | **`0.06117`** | **Quasi identique** ($+0{,}5\,\%$) |
| **4 blocs** | **ID 990000254** | RATE_L11 | **0,0 %** | **`0.06062`** | **$-0{,}4\,\%$ (BATTUE à 4 blocs !)** 🏆 |
| **3 blocs** | **ID 900000170** | ELITE | **0,0 %** | **`0.06720`** | $+10{,}4\,\%$ |

#### Règle d'allocation d'échantillonnage ($N=150$ vs $N=300$)
Les mesures comparatives sur les campagnes globales (G1/G2) et sur le 35c démontrent que le SEEL ($0{,}6\text{ nm}$) et le classement des stratégies sont **rigoureusement stables dès $N=150$ tirages**.
Pousser à $N=300$ ou $500$ double le temps de calcul pour échantillonner du bruit statistique sans modifier la décision machine. La règle est claire : **fixer la profondeur finale à $N=150$ et allouer le budget temps à la largeur de recherche (`top_k = 400` à `800`)**.
