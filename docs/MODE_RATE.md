# Le mode Rate — contrôle au quartz et au chronomètre

> Extrait de `CLAUDE.md` §22 le 2026-08-16. Ce dossier **fait autorité**.
> 🔑 **Un fait, un seul endroit** — corrige ici, ne recopie pas ailleurs.

🔴 **Avant de lire : `swing < SWING_MIN` n'est pas un critère d'épaisseur, et un point
tournant n'est pas un QWOT.** Voir [`QWOT_ET_TURNING_POINT.md`](QWOT_ET_TURNING_POINT.md).

---

### Le mode "Rate" (Quartz / Chrono) sur les couches à faible dynamique du signal

> *« Pour les couches où la dynamique du signal est trop pauvre (faible amplitude optique $\text{swing} < \text{SWING\_MIN}$, et non un critère absolu d'épaisseur), la machine passe en mode "Rate" (comptage de tours / chrono) sans contrôle photométrique POEM. Dans ce mode, **il n'y a aucune compensation d'erreur** et la précision sur l'épaisseur déposée vaut $\sigma_{\text{rate}} = 2\,\%$ de l'épaisseur nominale. »* — (2026-08-09)

1. **Critère de basculement non trivial** : Le basculement dépend de la pauvreté de la dynamique du signal optique effectif ($\text{swing} < \text{SWING\_MIN}$), et non d'un seuil fixe absolu en nanomètres (une couche de 30 nm à très faible contraste d'indice peut présenter une dynamique tout aussi pauvre qu'une couche ultrafine).
2. **Pas d'auto-compensation en mode Rate** : Les erreurs accumulées aux couches précédentes ne sont ni mesurées ni corrigées pendant une couche en mode Rate ; elles sont transmises en boucle ouverte à la couche suivante.
3. ⚠️ **Modèle de bruit d'épaisseur — PÉRIMÉ, voir la dérivation plus bas.** Il posait $d_{\text{réel}} = d_{\text{nom}} \cdot (1 + N(0, 0{,}02))$, c'est-à-dire un tirage indépendant de $\sigma = 2\,\%$. 👤 Abandonné le 2026-08-09 : l'erreur de rate **se calcule**, elle ne se tire pas.
4. **Transition avec POEM** : POEM se réactive dès la première couche présentant une amplitude optique suffisante ($\text{swing} \ge \text{SWING\_MIN}$).
5. **Influence de la dynamique forte sur la précision du Trigger (Piste d'optimisation)** : Le déclenchement d'arrêt (trigger) est d'autant plus précis et insensible au bruit que la dynamique du signal ($\text{swing}$) est forte et la pente raide ($\frac{dT}{dd} \gg 0$). Favoriser les longueurs d'onde offrant une forte dynamique optique est une piste clé pour maximiser la répétabilité du dépôt.

#### 🔵 « le rate est souvent réservé aux couches fines » — l'intuition, et les TROIS critères qu'elle mélange

> 👤 2026-08-15 : *« de même, le rate est souvent réservé aux couches fines »* — dit dans la
> même conversation que l'intuition sur le changement de témoin (§23.4), et de même valeur :
> **c'est ce que les expérimentateurs pressentent, ce n'est pas une mesure.**

Cette phrase est **juste en pratique et imprécise en physique**, et l'écart est instructif.
Il y a **trois critères distincts** dans ce projet, et « couche fine » n'est aucun des trois —
c'est un **proxy** du premier :

| | critère | où il vit |
|---|---|---|
| **1. quand le Rate est NÉCESSAIRE** | `swing < SWING_MIN` — 🔴 **pas** un seuil d'épaisseur. Point 1 ci-dessus le dit explicitement : *une couche de 30 nm à très faible contraste d'indice a une dynamique aussi pauvre qu'une ultrafine.* | implémenté |
| **2. l'intuition de 👤** | **couche fine.** Corrélée au critère 1 — une couche fine parcourt peu de chemin optique, donc produit peu de swing — mais **elle n'est pas équivalente** : le contraste d'indice et la λ de contrôle entrent aussi. | 🔵 non implémentée, et **elle n'a pas à l'être** : le code applique la grandeur exacte dont « fine » est l'approximation. |
| **3. où le solveur ESSAIE le Rate** | **la dernière couche de chaque bloc** (`_rate_candidate_layers`, `certus_strat_robustness.py:643`). Critère de **coût**, pas de nécessité : à une frontière de bloc, `block_start[i+1] = i+1`, donc les ancres sont perdues de toute façon — le Rate y est gratuit. | implémenté |

🔑 **Le point à ne pas manquer** : le critère 3 ne cherche **pas** les couches qui ont besoin
du Rate. Il cherche celles où le Rate **ne coûte rien**. Ce sont deux questions différentes.

🟢 **ET LE CODE RÉPOND DÉSORMAIS AUX DEUX — depuis le 2026-08-22.** Cette phrase disait *« le
code ne répond aujourd'hui qu'à la seconde »*, et c'était vrai pendant trois mois.
`rate_by_swing` est **armé par défaut** : `_rate_swing_candidates` ajoute les couches dont le
swing de croissance passe sous `dynamics_threshold`, et **les deux critères se PARTAGENT le
plafond au lieu de s'évincer** — moitié au besoin, moitié au coût, le reliquat revenant à
l'autre.

⚠️ **Ce qui rend ce défaut sûr, et il faut le comprendre avant de toucher au réglage** : une
variante Rate entre comme **COÛT, jamais comme COUPERET**. Elle **s'ajoute** à un classement
qui contient déjà les stratégies pur optique — elle ne peut donc pas dégrader le choix final.
Le seul canal par lequel elle le pourrait était le plafond partagé, réparé le même jour
(contradiction A, plafond porté de 3 à 40 sur les 50 meilleures).

📏 **Ce que l'armement a rendu**, mesuré à une seule variable sur `r75x2` à 2 nm — mêmes
graines, seul le code change : **+8 à +12 % de déposables** (372 → 403 et 311 → 349) pour un
SEEL **inchangé** (+0,5 % et −0,1 %, tous deux sous le bruit de 2,59 %). ⚠️ Coût : **+30 à 50 %**
sur la durée d'un run.

🔑 **Le Rate n'améliore donc pas la PRÉCISION, il élargit le CHOIX.** Et le classement en fait
un usage très inégal selon le composant : sur le `75c`, **1031 des 1790 déposables** portent une
couche Rate (58 %, jusqu'à 70 % sur une autre graine) ; sur `r75x1.5`, `r75x1.75` et
`r75x2-2nm`, **zéro sur 1510** — offert à chaque fois, jamais retenu. ⚠️ Ce contraste **n'est
pas expliqué** : le 75c est le composant le plus FIN de la série, donc celui dont les couches
ont le plus de dynamique optique. Ce n'est pas l'intuition qu'on aurait eue, et personne ne l'a
instruit.

⚠️ **Un classement par marge a déjà été tenté et annulé le même jour (2026-08-12)** —
l'hypothèse est séduisante et sera reproposée. Mesuré sur les deux références N=300, gain de
la variante Rate contre son parent : marge du parent PETITE **+0,7 % / +0,2 %**, marge GRANDE
**−0,9 % / −0,1 %** ; couche profonde **+0,6 % / −0,0 %**, couche précoce **+0,5 % / +0,2 %**.
La profondeur ne porte pas de signal, la marge en porte un **mais il change de signe** d'un
empilement à l'autre. 🔴 **Avant de proposer « trier les candidats Rate par épaisseur », lis
ce paragraphe** : c'est exactement la forme d'hypothèse qui a déjà échoué une fois.

**Le test qui manque, s'il est fait un jour** : comparer, à budget de variantes égal, les
candidats « dernière couche de bloc » aux candidats « swing le plus faible ». C'est la seule
façon de savoir si le critère 3 laisse passer des couches que le critère 1 réclame. Personne
ne l'a mesuré.

#### 👤 Comment la machine obtient son rate — précision du 2026-08-09

> *« L'OMS 5100 propose un mode rate avec un contrôle au temps, en comptant le nombre de
> rotations du porte-substrat. Dans ce cas, la vitesse de dépôt est estimée sur les couches
> précédentes (paires ou impaires), en étudiant le nombre de tours observés par rapport aux
> épaisseurs théoriques. En général il y a une dispersion de rate d'environ ±σ = 1 à 2 %, ce
> qui permet derrière de calculer le nombre de tours de dépôt si l'utilisateur a utilisé le
> mode rate. »*

> *« Il pourrait être intéressant d'introduire du rate pour les stratégies les plus
> prometteuses sur les couches fines ou pour lesquelles la dynamique du signal est faible. Le
> problème du rate, c'est qu'on perd l'info de l'historique POEM pour la couche suivante, et
> qu'on repart classiquement. »*

Ce que cela ajoute aux cinq points ci-dessus, et qui change le modèle :

6. 🔑 **Le rate n'est pas une constante, c'est une ESTIMATION construite en cours de dépôt —
   et cette estimation, LE SIMULATEUR PEUT LA CALCULER.** Elle se fait **par matériau** —
   couches paires d'un côté, impaires de l'autre — en comparant le **nombre de tours
   observés** aux **épaisseurs théoriques**. Or ces deux grandeurs sont déjà dans le noyau :
   `prev_thicknesses_sim[j]` (réelle) et `p_thick_nominal[j]` (nominale), utilisées côte à
   côte à `certus_strat_growth.py:570-571`. **`sigma_rate` ne doit donc PAS être un paramètre
   libre. C'est une grandeur DÉRIVÉE.** Voir la dérivation ci-dessous.
7. **L'unité de contrôle est le TOUR**, pas la seconde : 240 tr/min ⇒ 1 tour = 250 ms ⇒
   **0,125 nm à 0,5 nm/s**. C'est **exactement le pas d'échantillonnage du §18-1**, et ce
   n'est pas une coïncidence : les deux viennent de la même rotation. L'épaisseur déposée en
   mode Rate est donc **quantifiée en nombre entier de tours**, et cette quantification
   **tombe toute seule** — aucun paramètre à poser.
8. **Le Rate est un CHOIX DE STRATÉGIE, pas seulement un repli automatique.** L'idée est de
   l'introduire délibérément, sur les stratégies déjà prometteuses, pour les couches fines ou
   à faible dynamique. Cela ajoute donc un **degré de liberté par couche** à la recherche
   (POEM ou Rate), et non un simple garde-fou déclenché par `swing < SWING_MIN`.
   ⚠️ Ce degré de liberté a sa place **dans la DP existante**, pas dans une phase nouvelle :
   son coût est une propriété **de bloc**, exactement ce que la DP sait déjà arbitrer.
9. **Le coût du Rate n'est pas du bruit en plus — c'est le GEL de l'erreur existante.** Voir
   la dérivation : une couche Rate **recopie** l'erreur relative de la dernière couche du même
   matériau, là où POEM l'aurait corrigée.
10. 👤 **Ce que « on repart classiquement » veut dire exactement** (précision du 2026-08-09) :
    *« la machine ne garde pas l'historique du passage des extremums s'ils existent après un
    rate »*. Pendant une couche Rate la machine **ne surveille pas le signal** : tout extremum
    qui passe n'est **pas enregistré**. Et les ancres acquises **avant** ne valent plus rien
    non plus, puisqu'elles sont désormais séparées du signal courant par une portion non
    surveillée pendant laquelle des extrema ont pu passer sans être vus.
    **C'est le COMPTAGE qui casse — et POEM est une méthode fondée sur un comptage.**

    🔴 **La conséquence, et c'est la plus importante de toute cette section : le coût d'une
    couche Rate se paie surtout sur la couche SUIVANTE, pas sur elle-même.** Sans ancres, la
    couche d'après retombe sur le **niveau absolu** — c'est-à-dire précisément la branche que
    [`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.1 a démontrée **non invariante** par distorsion affine, celle qui rend
    `CRASH_LEVEL_UNREACHABLE`. Le Rate déplace donc le risque du photométrique vers la branche
    fragile. Il faut deux nouveaux points tournants observés pour que POEM redevienne
    utilisable.

    ⚠️ **Le bloc, lui, n'est PAS rompu** : la λ de contrôle ne change pas, c'est seulement
    l'historique d'ancres qui est vidé. Une couche Rate peut donc vivre **à l'intérieur** d'un
    bloc. Second effet à ne pas oublier : un extremum manqué pendant le Rate peut aussi faire
    diverger le comptage total et déclencher un `CRASH_TP_MISCOUNT` plus loin.

### 🔑 `sigma_rate` n'est PAS un paramètre — c'est une grandeur DÉRIVÉE

👤 *« Oublie le 1 à 2 %, c'est ce que j'avais en tête, mais ça tombe à l'eau. »* (2026-08-09)

Le simulateur connaît les deux grandeurs que la machine compare, donc il peut **refaire son
calcul de rate à sa place**, au lieu de le remplacer par un tirage.

Soit $v$ la vitesse de dépôt vraie et $t_{\text{tour}} = 0{,}25$ s, donc un tour dépose
$q = v\,t_{\text{tour}} = 0{,}125$ nm.

- Couche $j$ du matériau $M$, déposée **sous POEM** : épaisseur réelle $d^{\text{réel}}_j$, la
  machine a donc compté $n_j = d^{\text{réel}}_j / q$ tours. **Mais elle croit avoir déposé
  $d^{\text{nom}}_j$** — c'est la cible qu'elle visait, et rien ne lui dit le contraire.
- Son estimation de rate vaut donc
  $$\widehat{v}_M \;=\; \frac{d^{\text{nom}}_j}{n_j\,t_{\text{tour}}} \;=\; v\cdot\frac{d^{\text{nom}}_j}{d^{\text{réel}}_j}$$
- Couche $i$ **en mode Rate** : la machine commande
  $n_i = \operatorname{round}\!\bigl(d^{\text{nom}}_i / (\widehat{v}_M\,t_{\text{tour}})\bigr)$
  tours, et dépose donc $d^{\text{réel}}_i = n_i\,q$, soit

$$\boxed{\;\frac{d^{\text{réel}}_i}{d^{\text{nom}}_i} \;=\; \frac{d^{\text{réel}}_j}{d^{\text{nom}}_j}\;}$$

**L'erreur relative n'est pas tirée, elle est RECOPIÉE.** Ce qui en découle :

- **Zéro paramètre libre.** C'est exactement ce que §17 exige : ne pas remplacer une constante
  mesurée par des paramètres inventés. Ici on ne pose même plus de constante.
- **La question « biais corrélé ou tirage indépendant ? » n'a plus lieu d'être** : ce n'est
  ni l'un ni l'autre, c'est une **égalité**.
- **Tout est déjà dans le noyau** : `prev_thicknesses_sim[j]` et `p_thick_nominal[j]`,
  utilisées côte à côte à `certus_strat_growth.py:570-571`. Rien à câbler de plus.
- 🟢 **Et c'est une occasion de validation EXTERNE, la première du projet.** `sigma_rate`
  devient une **prédiction** du modèle. Si le simulateur en rend une dispersion du même ordre
  que ce que la machine montre en salle, c'est la première corroboration que STRAT ait jamais
  eue (§26). S'il en rend 0,1 %, c'est que le modèle de bruit rate quelque chose. **Dans les
  deux cas on apprend, et cela ne coûte rien.**

⚠️ **La seule hypothèse que cela introduit** : $v$ est **constante pendant un run**. Si la
source dérive réellement (épuisement, température), un terme de dérive revient — mais alors
il faudra le **mesurer**, pas le poser. Ne pas le réintroduire par raisonnement (§17).

🔴 **Rien de tout cela n'est implémenté.** Aucune ligne de `certus/` ne contient de mode Rate
aujourd'hui — **revérifié le 2026-08-11 par balayage** : zéro occurrence de `sigma_rate` ou
`rate_mode`.

### 👤 A24 — LE PLAN RATE, et il ne part pas au hasard — 2026-08-11

> 👤 *« Sur les 10 meilleures stratégies, essayer de mettre une ou plusieurs couches fines
> en rate. »*

C'est **une passe d'amélioration locale sur un ensemble déjà choisi**, pas un degré de
liberté ajouté à la recherche. Quelques dizaines de variantes de stratégies connues, sans
refaire la Phase A. C'est exactement §22-8, et le coût n'a rien de commun avec celui
d'un Rate/POEM par couche plié dans la DP.

📏 **Trois faits mesurés sur la classe d'équivalence de la référence (10 stratégies) :**

1. 🔑 **Le Rate automatique ne se déclencherait JAMAIS ici.** Les dix ont
   `n_below_swing_min = 0` : aucune couche sous `SWING_MIN`. Le repli automatique est
   **inerte** sur cet empilement, donc l'introduction **délibérée** est le seul moyen de
   tester le Rate. Ce n'est plus une intuition, c'est un comptage.
2. ⚠️ **Le critère est le SWING, pas l'épaisseur** — §22-1 le dit déjà, et on peut
   désormais le mesurer : 7 stratégies sur 10 ont leur couche la plus pauvre en **L24**
   (swing 0,109, soit 2,7 × `SWING_MIN`), les 3 autres en **L47** (0,061, soit 1,5 ×).
3. 🔑 **L47 est le premier essai évident, et pour une raison structurelle.** §22-10
   établit que le coût dominant d'une couche Rate se paie **sur la couche SUIVANTE** —
   ancres vidées, repli sur le niveau absolu, la branche que [`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.1 a démontrée non
   invariante. **L47 est la dernière couche : il n'y a pas de suivante.** Le terme
   dominant disparaît, il ne reste que le gel de l'erreur sur la couche elle-même. Et
   c'est aussi la couche au plus faible swing sur 3 des 10.

#### ✅ Q2, Q3, Q4 — RÉPONDUES le 2026-08-11. Le mode Rate n'a plus de paramètre ouvert.

| | 👤 réponse | ce que ça impose |
|---|---|---|
| **Q2** — que fait la machine quand aucune couche du matériau n'a encore été déposée sous POEM ? | **Rate interdit tant qu'il n'y a pas de référence mesurée** | Les deux premières couches (le premier H, le premier L) sont **obligatoirement photométriques**. C'est une contrainte dure sur l'espace de recherche — et elle **élague**, donc elle aide. |
| **Q3** — la machine chaîne-t-elle deux Rate consécutifs ? | **Oui, elle chaîne** : la dernière couche déposée fait référence, Rate compris | Aucun garde-fou côté machine. Voir ci-dessous : ce n'est **pas** dangereux, contrairement à ce que j'avais annoncé. |
| **Q4** — sur quoi porte l'estimation de vitesse ? | **Une moyenne de toutes les couches précédentes du matériau** | C'est la réponse qui a le plus de conséquences, et elles sont **favorables**. |

#### 🔴 Ma crainte de DIVERGENCE était fausse — corrigée par la mesure

J'avais écrit que Q3 « chaîne » ouvrait un régime instable où l'erreur se recopie sans
jamais être corrigée et **peut diverger**. **C'est faux, et la simulation le montre en
trois lignes.**

Une couche Rate **recopie** l'erreur relative — §22 le démontre :
`d_réel_i / d_nom_i = d_réel_j / d_nom_j`. Elle n'en **ajoute aucune**. Une chaîne de
couches Rate porte donc toutes **la même** erreur : elle est **gelée, pas amplifiée**.
📏 Vérifié : 40 couches Rate enchaînées, étendue **0,000 %**.

Et c'était vrai **quelle que soit la réponse à Q4**. Ce n'est pas la moyenne qui sauve la
situation ; il n'y avait pas de situation à sauver. *Une inquiétude fondée sur un
raisonnement plutôt que sur un calcul, exactement ce que §17 interdit.*

#### 🔑 Ce que Q4 change VRAIMENT — et c'est le point qui redessine le plan

Moyenner sur toutes les couches passées ne stabilise pas (il n'y avait rien à
stabiliser) : cela **réduit la taille de l'erreur gelée**.

📏 Dispersion relative héritée par une couche Rate, pour une dispersion de 2 % par couche
POEM (20 000 tirages) :

| couches du matériau déjà en POEM | 1 | 2 | 4 | 8 | 16 | 24 |
|---|---|---|---|---|---|---|
| **dernière seule** | 1,99 % | 2,00 % | 2,01 % | 2,00 % | 2,00 % | 1,99 % |
| **moyenne de toutes** 👤 | 1,99 % | 1,41 % | 0,99 % | 0,71 % | **0,50 %** | **0,41 %** |

La loi est en `1/√n`, exactement. À la couche 40 il y a ~20 couches de chaque matériau :
**le Rate y hérite d'une erreur ~4,5 fois plus petite** qu'avec la dernière couche seule.

> **Le Rate devient de plus en plus précis à mesure qu'on s'enfonce dans l'empilement.**

🔑 **Et c'est là que tout converge.** §24-36 a mesuré que sur l'effondrement de la
graine 77, **rien ne plante avant la couche 35** et tout plante de **35 à 47**. Le swing
est aussi souvent le plus pauvre en fin d'empilement (L47 sur 3 des 10 finalistes).

**Trois faits indépendants désignent le même endroit** : c'est en fin d'empilement que
POEM est le plus fragile, que les plantages se concentrent, et que le Rate est le plus
précis. **Ce n'est plus une liste de candidates à balayer, c'est une région.**

⚠️ Ce qu'il faut quand même mesurer, et ne pas déduire : la contrepartie de §22-10 — la
couche **suivante** perd ses ancres — ne diminue pas, elle. Le bilan reste une
soustraction entre deux effets qui grandissent différemment, et c'est le banc qui la fait.

#### 🔑 La décision s'écrit comme une INÉGALITÉ, pas comme un essai

C'est ce qui sépare ce plan d'un balayage au hasard. Sur une couche donnée :

| | ce que ça coûte |
|---|---|
| **POEM** | il **corrige** l'erreur accumulée en amont, mais il paie son propre bruit de lecture **divisé par la pente** `dT/dd`. Sur un signal plat la pente est minuscule : la correction devient elle-même très bruitée. |
| **Rate** | **aucune correction**, mais **aucun bruit neuf** non plus : l'erreur relative est **recopiée** de la dernière couche POEM du même matériau (§22, dérivation). |

$$\varepsilon_{\text{POEM}}(i) \;\approx\; \frac{\sigma\sqrt{1+(1-p)^2+p^2}}{\left|dT/dd\right|_i}
\qquad\text{contre}\qquad
\varepsilon_{\text{Rate}}(i) \;\approx\; \left|\varepsilon_{\text{rel}}(j)\right|\cdot d^{\text{nom}}_i$$

> **Le Rate gagne là où la correction de POEM est plus bruitée que l'erreur qu'elle enlève.**

🟢 **Et les quatre termes existent déjà dans le noyau.** Le facteur
`sqrt(1+(1-p)^2+p^2)` est écrit en commentaire à `certus_strat_growth.py:601`
(×1,22 à p = 0,5, jusqu'à ×1,41 quand le déclenchement tombe sur une ancre) ; la pente
sort de l'inversion parabolique ; `eps_rel(j)` se lit sur `prev_thicknesses_sim[j]`
contre `p_thick_nominal[j]`, déjà côte à côte ; `d_nom_i` est donné.
**La liste des couches candidates se CALCULE, elle ne se devine pas.**

#### 🔑 👤 LE PLACEMENT ÉVIDENT : aux FRONTIÈRES DE BLOC — 2026-08-11

> 👤 *« Il peut être intéressant de tester le rate aux couches i dont la longueur d'onde
> de contrôle change à la couche i+1, car il n'y aura pas de POEM à la couche suivante de
> toute façon ! »*

**Vérifié au code, et c'est exact.** `certus_strat_batch.py` pose `block_start[i] = i`
dès que λ change, et le noyau en tire `j0 = block_start_layer = i`, donc
`n_hist = (i − i) × NPTS_PREV = **0**`. La première couche d'un nouveau bloc démarre
**sans aucun historique hérité** — elle n'a pas d'ancres POEM, que la couche d'avant ait
été en POEM ou en Rate.

**Ce placement annule DEUX des trois coûts de §22-10 :**

| coût d'une couche Rate | à une frontière de bloc |
|---|---|
| la couche suivante perd ses ancres → repli sur le niveau absolu | ✅ **déjà payé** — elle n'en avait pas |
| un extremum manqué peut faire diverger le comptage plus loin | ✅ **déjà payé** — `detect_turning_points` ne voit que `Ts_r` de longueur `n_tot = 0 + NPTS`, le comptage repart de zéro |
| l'erreur accumulée n'est pas corrigée sur la couche `i` | ❌ **reste** — c'est le coût irréductible |

> **Le terme dominant disparaît. Le bilan à trois termes devient un bilan à un terme.**

C'est nettement supérieur à l'idée L47, qui demandait de mettre en balance « pas de
couche suivante » contre « dernière occasion de corriger » — deux effets opposés dont
aucun n'était calculé.

⚠️ **La réserve, et elle est réelle.** La couche `i` est la **dernière de son bloc**,
donc celle qui a le **plus d'historique derrière elle** (jusqu'à `MAX_LOOKBACK = 4`) :
c'est là que POEM est le **mieux ancré**, et on renoncerait à sa meilleure correction.
Mais c'est exactement ce que l'inégalité ci-dessus calcule, avec le terme aval mis à
zéro. **À vérifier au banc, pas à trancher au raisonnement.**

#### 🔑 CE QUE LE RATE FAIT VRAIMENT — mesuré le 2026-08-12, et ce n'est pas ce qu'on cherchait

> 👤 *« Ça ne te paraît pas bizarre que le Rate ne soit appelé quasiment jamais alors que
> ça semble hyper robuste ? »*

**Zéro run.** Le pipeline avait déjà classé les variantes Rate à côté de leurs parents ; il
suffisait de les **apparier**. C'est le seul montage qui vaille ici : la variante et son
parent partagent la graine, les tirages et la stratégie, donc leur écart est imputable au
seul Rate (contrainte C2).

| | dichroïque, 40 paires | passe-bande, 89 paires |
|---|---|---|
| Rate **meilleur** que son parent | 14 | 21 |
| Rate **pire** | 13 | 21 |
| égal | 13 | 47 |
| écart médian | **−0,3 %** | **−0,0 %** |
| plantage | **10 baissent**, 3 montent | **6 baissent**, 1 monte |
| meilleur cas | L42 : SEEL 1,462 → 1,362 | L16 : SEEL **11,5 → 1,7** (−85 %) |

🔑 **L'intuition de 👤 est juste, et l'observation aussi — elles ne se contredisent pas.**
Le Rate **est** robuste : le plantage baisse trois à six fois plus souvent qu'il ne monte,
ce qui est exactement attendu puisqu'une couche au chrono ne peut ni mal compter un point
tournant, ni manquer un niveau. Et il n'est **pas** rare : il est proposé partout, et c'est
un pile ou face.

> **Le Rate supprime un mode de défaillance. Sur une stratégie qui ne défaille pas,
> supprimer un mode de défaillance ne rapporte rien.**

Les gagnantes de ces deux repères sont à **plantage 0**. Il n'y a rien à sauver, et le Rate
leur retire une correction photométrique sans leur rendre de sécurité. **Le Rate n'est pas
un outil pour améliorer une bonne stratégie, c'est un outil pour en rattraper une
mauvaise** — le cas à −85 % ramène un SEEL de 11,5 nm à 1,7 nm.

⚠️ **Et un sauvetage à 1,7 nm ne change pas le classement quand la gagnante est à 0,5 nm.**
C'est pourquoi le Rate est invisible en tête **par construction** sur ces deux composants.
Il se verra dans le régime fragile, celui de §24-36.

#### 🔴 J'AI CHANGÉ LA CLEF DE TRI, PUIS JE L'AI REMISE — le 2026-08-12, en trois heures

**Garde ce récit : l'hypothèse est séduisante et quelqu'un la reproposera.**

Même appariement, en regardant cette fois **où** le Rate a été posé :

| | dichroïque | passe-bande |
|---|---|---|
| Rate **sur la couche critique** du parent | +1,5 % (7 cas) | +4,2 % (1 cas) |
| Rate **ailleurs** | +0,2 % (33 cas) | +0,0 % (88 cas) |
| parent à **marge faible** | **+0,7 %**, 8/20 améliorent | **+0,2 %**, 14/44 |
| parent à **marge large** | **−0,9 %**, 6/20 | **−0,1 %**, 7/45 |
| couche **profonde** | +0,6 % | −0,0 % |
| couche **précoce** | +0,5 % | +0,2 % |

🔴 **La profondeur ne trie rien** — +0,6 contre +0,5 d'un côté, l'inverse de l'autre. Or
c'était la clef du code, justifiée par la loi en `1/√n` d'A24. Cette loi est vraie, mais
elle gouverne l'**erreur propre du Rate**, et cette erreur n'est pas ce qui atteint le
score. **C'est le contrôle 4 de §12 sous une autre forme : un critère qui n'ordonne rien
ne produit pas d'erreur, il produit un ordre plausible.**

🟢 **La marge, elle, trie — et elle CHANGE DE SIGNE.** Marge faible : le Rate aide. Marge
large : il nuit. Sur deux empilements très différents, dans le même sens, avec deux fois
plus de cas améliorés côté marge faible. C'est cette concordance qui rend le constat
crédible, pas l'amplitude, qui reste petite.

**Ce que j'en ai tiré** : trier les frontières par **marge croissante**, au lieu de par
profondeur. Écrit, testé — trois tests échouant bien sur le code d'avant —, et validé par
un run complet à N = 300, configuration identique au repère.

#### 🔴 ET LE RUN DE VALIDATION A DIT L'INVERSE

```
gain median             : -1,13 %   (avant le changement : -0,3 %)
ameliorent / degradent  :  5 / 9    (avant : 14 / 13)
marge faible -> gain    : -2,08 %   <- le signe s'est INVERSE
```

`RESULT = 0.006151532` contre `0.006110492`, soit +0,67 % — indiscernable, comme prévu sur
une gagnante à plantage nul. **Mais le placement, lui, s'est dégradé.** Revenu en arrière
le jour même : `_rate_candidate_layers` retrie par profondeur, le câblage est retiré,
les quatre tests aussi.

#### 🔑 L'ERREUR, ET C'EST UNE ERREUR DE MÉTHODE, PAS D'ARITHMÉTIQUE

La grandeur mesurée est `critical_layer.margin_in_A` — **une propriété de la stratégie
ENTIÈRE**, un nombre par candidate. La règle que j'en ai tirée ordonne **les COUCHES à
l'intérieur** d'une stratégie. Ce sont deux grandeurs différentes, et la mesure n'a jamais
rien dit de la seconde.

> **La mesure disait : « une couche Rate aide les stratégies dont la couche critique est
> près de lâcher. » J'ai écrit : « pose la couche Rate là où la marge est faible. » Ce
> n'est pas la même phrase.**

C'est le contrôle 5 de §12 — *les conclusions dépassent-elles les mesures ?* — et il m'a
attrapé sur mon propre travail, trois heures après l'avoir écrit. Ce qui rend le cas
instructif, c'est que **rien n'avait l'air faux** : le signal était réel, reproduit sur deux
composants, avec un changement de signe propre, et la règle en découlait « évidemment ».

⚠️ **Les deux hypothèses restent ouvertes, et aucune ne s'implante depuis ces chiffres :**

1. **Choisir QUELLES STRATÉGIES étendre** selon la marge de leur couche critique — c'est ce
   que la mesure dit réellement. Elle demande son propre run.
2. **Poser le Rate sur la couche critique même hors frontière de bloc** — 7,5× dans le
   tableau, mais sur **7 cas**, et une couche en milieu de bloc paie le coût aval en entier.

🟢 **Ce qui est acquis et qui ne bouge pas** : la profondeur ne trie rien (+0,6 contre
+0,5), et le Rate est un **sauvetage**, pas une optimisation. Ces deux-là ont survécu.

#### La variante symétrique, à tester aussi : la PREMIÈRE couche du nouveau bloc

Plutôt que la dernière couche du bloc sortant, la **première du bloc entrant** — celle
qui n'a pas d'ancres :

- **POEM y est à son plus faible.** Sans historique, il doit trouver deux points tournants
  dans la seule couche courante, faute de quoi il retombe sur le **niveau absolu** — la
  branche que [`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.1 a démontrée non invariante par distorsion affine, et qui pèse **21 %**
  des plantages mesurés (§24-36).
- Le Rate y **remplacerait un arrêt fragile par un comptage de tours déterministe**.
- ⚠️ **Mais le coût aval ne disparaît pas ici** : la couche `i+2` est dans le même bloc et
  aurait hérité de l'historique de `i+1`. La fragilité se propage d'un cran.

**Les deux placements sont de premier choix et ils s'opposent proprement** :

| | coût aval | ce qu'on sacrifie |
|---|---|---|
| **dernière couche du bloc** 👤 | **nul** | la correction POEM la mieux ancrée |
| première couche du bloc suivant | non nul | rien — POEM y est déjà en repli fragile |

🟢 **Et la liste est courte.** Une stratégie à 2 blocs n'a **qu'une seule** frontière ;
la gagnante à corridor 0,005 en a quatre. Sur les 10 finalistes, cela fait **une dizaine
de couples (stratégie, couche)** — pas 480. C'est exactement l'échelle où l'on peut
prédire puis mesurer.

#### 🔴 La correction que je dois à L47 — mon premier raisonnement était à moitié faux

J'avais écrit que L47 était l'essai évident, au motif que le coût dominant tombe sur la
couche suivante et qu'il n'y en a pas. **C'est vrai, et ce n'est que la moitié du bilan.**

La dernière couche est aussi **la dernière occasion de corriger tout ce qui s'est
accumulé depuis la couche 1**. La mettre en Rate, c'est renoncer à la correction la plus
précieuse du dépôt entier. Les deux effets tirent **en sens opposé**, et il faut donc
calculer l'inégalité au lieu de l'affirmer. **Ne cite pas « L47 est le moins cher » sans
cette réserve.**

#### ⚠️ Le canal PLANTAGE va lui aussi en sens inverse, et il compte autant

| | effet sur le plantage |
|---|---|
| couche `i` en Rate | 🟢 **supprime deux modes** : sans déclenchement, ni `CRASH_LEVEL_UNREACHABLE` ni `CRASH_TP_MISCOUNT` ne peuvent s'y produire |
| couche `i+1` | 🔴 **en ajoute un** : sans ancres, repli sur le niveau absolu — la branche que [`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.1 a démontrée non invariante |

**La bonne candidate est donc à deux faces** : une couche dont la marge POEM est
**mauvaise** — elle est déjà près de lâcher — et dont la **suivante** a une marge
**large**, capable d'absorber le repli. `margin_level` et `margin_missed` par couche,
câblés le 2026-08-11, donnent exactement ces deux nombres.

#### 🔴 Statut de la formule : elle GÉNÈRE des candidates, elle ne DÉCIDE rien

Le raisonnement ci-dessus est en **nanomètres d'erreur d'épaisseur**. Or §8 est formel —
👤 *« en partie B on se branle de l'erreur d'épaisseur, seul l'écart spectral final
compte »*. La formule a donc exactement le statut des heuristiques de la littérature :
**un diagnostic pour choisir quoi essayer, jamais un couperet**. Ce qui tranche reste le
banc.

#### L'expérience minimale, et pourquoi elle vaut mieux qu'un balayage

```
etage 0   calculer l'inegalite sur 48 couches x 10 strategies    ZERO run
          -> liste courte (~5 couples strategie/couche), chacun avec sa PREDICTION
etage 1   mesurer les 2 ou 3 meilleures candidates               2-3 runs
          -> la prediction EST le test
etage 2   la formule tient     -> on peut s'en servir dans la recherche
          elle ne tient pas    -> on comprend pourquoi AVANT de continuer
etage 3   seulement alors, plier le choix Rate/POEM dans la DP
```

🔑 **Pourquoi c'est mieux que « essayer et voir ».** Un balayage rendrait 480 nombres
portant chacun ±6 % de bruit — illisible (§24-26). **Prédire puis mesurer teste la
compréhension, pas seulement la configuration** : c'est le contrôle 5 de §12, et c'est
la seule façon d'apprendre quelque chose de transférable à un autre empilement.

🔴 **Le piège de comparabilité, à traiter avant d'écrire la première ligne.** Si une
couche Rate consomme un nombre différent de tirages de bruit que la même couche sous
POEM, le flux aléatoire se décale et **deux variantes ne sont plus comparables** —
contrainte C2, et l'écart observé ne serait plus imputable au Rate. Une couche Rate doit
consommer **les mêmes indices de tirage**, quitte à les gaspiller.

🟢 **Et le dommage est désormais MESURABLE dès le premier run.** §22-10 dit que le Rate
déplace le risque vers le niveau absolu ; `margin_level` par couche (A23 étage 2, câblé
le 2026-08-11) lit exactement cet effondrement sur la couche d'après. Avant aujourd'hui
c'était une hypothèse ; c'est maintenant une grandeur. C'est une action à venir, à faire **après** que les mesures T2 / T5 / T6 aient
été obtenues (§24) — l'introduire avant ajouterait un degré de liberté à un modèle dont on
n'a pas encore mesuré les paramètres existants.

✅ **PLUS RIEN À DEMANDER — les quatre questions sont répondues le 2026-08-11.**
Q1 l'était depuis le 2026-08-09 sans que le tableau l'enregistre ; Q2, Q3 et Q4 le
sont désormais. Les réponses, et surtout **ce qu'elles impliquent**, sont dans A24
ci-dessus. **Le mode Rate n'a plus aucun paramètre libre : il ne reste qu'à
l'écrire.**
