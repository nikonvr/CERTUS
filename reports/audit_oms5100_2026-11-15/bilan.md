# Audit d'expertise — simulation du signal de transmission de l'OMS 5100 dans STRAT (2026-11-15)

Tête `b281ec95`. Audit **par lecture du code et calcul à la main** : aucune mesure n'a été lancée (une mesure longue
occupait la machine). Chaque constat porte son statut : **[lu]** dans le code, **[calcul]** analytique refait ici,
**[rapport]** chiffre d'un rapport existant, **[avis]** jugement d'expert non vérifiable sans la machine. Rien n'est
**mesuré** par cet audit ; les gains de vitesse sont des comptages d'opérations, à confirmer par un profil.

Code lu : `certus/physics/certus_strat_growth.py` (`simulate_growth_kernel`, `detect_turning_points`,
`_read_poem_anchors`, `_level_reachability`), `certus/physics/certus_strat_readings.py` (signal, grille machine,
inversion, ancres exactes, armement), `certus/physics/certus_strat_math.py` (`_seeded_noise_sample`),
`certus/core/certus_strat_robustness_task.py` et `certus_strat_robustness_slit.py`, `ETAT.md` section 3 (modèle de
lecture figé), `reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`.

## 1. Réponse courte

| question | réponse |
|---|---|
| Est-ce bien codé ? | **Oui pour la physique du signal** : la forme fermée `T(d) = 4 n_s / (P + Q cos 2δ + R sin 2δ)` est exacte (redémontrée, §2), le bruit est une fonction pure de (graine, couche, tirage, point), les causes de plantage sont séparées. **Deux faiblesses de structure** : le noyau reconstruit les matrices de l'empilement à chaque couche et à chaque tirage (coût en N²), et il recalcule pour chaque tirage tout ce qui est nominal, donc identique d'un tirage à l'autre (§5). |
| Les extrema sont-ils bien détectés ? | **Le détecteur à hystérésis est correct**, et c'est la même fonction pour le signal réel et le nominal. Cinq réserves (§3), dont deux de fond : le **début de fenêtre compté comme point tournant** sur la grille de production, et le **compte comparé à l'indice de l'arrêt nominal** au lieu de l'arrêt réel. |
| Le raisonnement tient-il ? | **Oui sur le cœur** : niveau figé sur le nominal, fraction POEM reportée sur les ancres lues, invariance affine, nombres aléatoires communs. **Trois points ne tiennent pas ou restent des paris** (§4) : le seuil `SWING_MIN = 0,04` contredit la règle gravée « jamais un couperet » ; l'« attente sans fin » (D98) est l'hypothèse la plus coûteuse du modèle et la moins étayée ; le modèle cumule une approximation optimiste (grille grossière) et une pessimiste (une seule lecture par ancre) dont le solde n'est écrit nulle part. |

## 2. Ce qui est juste

- **Forme fermée** [calcul]. Pour une couche d'indice `n` posée sur la matrice `M`, le dénominateur vaut
  `C cos δ + i S sin δ` avec `X = M00 + n_s M01`, `Y = M10 + n_s M11`, `C = X + Y`, `S = Y/n + nX`, d'où
  `|dén|² = (|C|²+|S|²)/2 + (|C|²−|S|²)/2 · cos 2δ + Im(C·S̄) · sin 2δ`. `layer_scan_coeffs` rend exactement ces trois
  coefficients. La garde `k < 1e-4` est explicite et le chemin matriciel prend le relais, sans repli silencieux [lu].
- **Loi du bruit** [lu]. Somme de 12 uniformes centrée, divisée par 3, bornée à ±1 : gaussienne σ = A/3 tronquée à 3 σ,
  conforme à `ETAT.md` section 3.
- **C2** [lu]. Les tirages sont indexés par la physique (couche, point), jamais par la stratégie ; le facteur de fente
  multiplie l'échantillon, pas la graine.
- **Niveau figé + POEM** [lu]. Le niveau vient du nominal, la fraction est reportée sur les ancres lues ; l'inversion se
  fait en unités mesurées (dérive, courbure, biais de fente appliqués aux deux membres qu'il faut). C'est le mécanisme
  d'auto-compensation, correctement écrit.
- **Biais de fente variable le long de la couche** [lu] : c'est bien la partie que POEM n'absorbe pas.

## 3. Détection des extrema : cinq réserves

1. **Le début de fenêtre est compté comme point tournant en production** [lu]. Sur la grille grossière,
   `direction_at_window_start` est faux, donc `start_dir = 0` hors couche 0 : le détecteur déclare l'indice 0 dès que
   le signal s'en écarte du seuil, et ce niveau devient une ancre POEM sur les deux signaux. Au début d'un **bloc**,
   c'est une vraie lecture (la première après le changement de λ) : ancre défendable, mais ce n'est pas un extremum,
   elle dépend au premier ordre des erreurs d'épaisseur d'amont. Au début de la **fenêtre de 4 couches** d'un bloc plus
   long, c'est un artefact de la troncature (`MAX_LOOKBACK_VAL`) : la machine, elle, garde son vrai dernier extremum.
   Fréquence et effet : non mesurés.
2. **Le compte est arrêté à l'indice de l'arrêt nominal** [lu]. `n_tp_real` et `n_tp_nom` comptent les extrema situés
   avant `idx_nom_stop` sur les deux signaux. Un extremum réel que les erreurs d'amont font passer de l'autre côté de
   cet indice donne `CRASH_TP_MISCOUNT`, alors qu'un contrôleur causal compte ses extrema puis attend son niveau : pour
   lui il n'y a pas d'erreur de compte, seulement un arrêt près d'un extremum. Sur la grille grossière l'indice vaut
   1/21 de couche (≈ 5 nm pour 100 nm). L'artefact recouvre en partie la zone d'armement (§4.2) ; sa part propre n'est
   pas mesurée.
3. **`turning_point_margins` ne suit pas la même règle que le compte** [lu]. Elle reproduit le détecteur sans
   `start_is_tp` ni `start_dir` : sur la couche 0, la marge est calculée par un détecteur qui ne sait pas dans quel sens
   part le signal. Or une marge critique entre dans le classement final (`ETAT.md`, règles gravées) ; je n'ai pas
   vérifié que c'est celle-ci.
4. **`_exact_poem_anchors` retrouve l'échantillon d'une ancre par égalité de valeur** [lu] (`sig[k] == vals[a]`,
   première occurrence). Deux échantillons de même valeur (signal nominal symétrique, cavité) désignent la mauvaise
   couche. `_read_poem_anchors` connaît les indices `tp_a` et `tp_b` : les rendre supprime le risque et une recherche
   linéaire par ancre.
5. **Cosmétique** [lu] : la règle historique (`hysteresis = 0`) garde à 1e-15 dans `detect_turning_points` et à 1e-12
   dans `next_turning_point_after`, alors que la docstring exige « la même règle ». Hors production (plancher 4,15e-4).
   Le commentaire POEM annonce l'usage de « points tournants virtuels » après l'arrêt ; le code ne les utilise jamais
   pour POEM (il faut deux extrema avant l'arrêt nominal, sinon niveau absolu).

Biais de sélection [calcul] : l'ancre exacte (D96) garde le bruit de l'échantillon élu comme maximum ; choisir le plus
grand de deux échantillons presque égaux biaise ce bruit de +0,56 σ au pire, soit ~1e-4 en T : négligeable.

## 4. Le raisonnement

### 4.1 `SWING_MIN = 0,04` est un couperet [lu]

`_read_poem_anchors` coupe POEM et passe au niveau absolu dès que l'écart entre les deux ancres est sous 4 % de T, soit
**80 fois** l'amplitude du bruit. `ETAT.md` (règles gravées) dit que les heuristiques de la littérature sont « des
colonnes explicatives, jamais des couperets », et la docstring de `detect_turning_points` refuse d'emprunter ce même
4 % pour le seuil de détection. À 3,9 % de swing, POEM est parfaitement conditionné (ancres à ±1 A sur 78 A) et le
noyau l'abandonne pour un arrêt absolu, sensible à la courbure photométrique et au biais de fente. La loi d'arrêt
change donc de nature à 4 %, ce qui crée une marche dans le score en fonction de λ. Un seuil dérivé du bruit
(k × A, à balayer) serait cohérent avec le reste du modèle. Effet non mesuré.

### 4.2 L'attente sans fin (D98) : l'hypothèse la plus chère, la moins étayée

- [calcul] Le niveau est « franchi avant l'armement » s'il est à moins de `h` du dernier extremum. Près d'un extremum
  `T'' = (ΔT/2)(4πn/λ)²`, donc la zone interdite après l'extremum vaut `d_h = √(2h/T'')` : **3,4 nm** pour un swing de
  10 %, n = 2,35, λ = 550 nm, h = 1,66 A = 8,3e-4. En fraction de la demi-période : `(2/π)√(h/ΔT)` = **5,8 %**,
  indépendante de l'indice ; 9,2 % à 4 % de swing, 3,3 % à 30 %.
- [calcul + rapport] Sur 48 couches aux phases quelconques, la probabilité de n'en avoir aucune dans la zone est
  0,942⁴⁸ ≈ **6 %**. Le rapport du 12 octobre mesure 6 plans déposables sur 120, soit 5 %. L'hécatombe est donc une
  conséquence géométrique directe de `h`, pas une subtilité du composant.
- [calcul] Changer de détecteur ne réduit pas `d_h` : pour *savoir* qu'un extremum est passé il faut un bras de levier.
  Un ajustement parabolique glissant sur 64 lectures ne le déclare que ~4 nm après. La zone est physique.
- [avis] En revanche **« attendre sans fin » suppose un déclenchement sur l'événement de franchissement**. Sur un signal
  échantillonné (une lecture tous les 0,125 nm), un contrôleur ne peut pas attendre l'égalité : il teste « le signal
  est-il passé de l'autre côté du niveau ? ». À l'instant où il s'arme, ce test est déjà vrai et il coupe : c'est
  l'**arrêt tardif** (`oms_arming = 1`), en retard de `d_h` au plus. Par ailleurs un automate industriel a un critère
  de secours (quartz, épaisseur maximale) : une couche ne dure jamais indéfiniment, elle finit fausse. L'attente sans
  fin est donc la **borne pessimiste**, l'arrêt tardif le comportement le plus plausible. Le rapport chiffre l'enjeu :
  0 plan optique pur déposable contre 101, et le Rate devient une nécessité.
- **Un essai en salle de trente minutes tranche** : une couche sur substrat nu, arrêt demandé juste après un point
  tournant (à moins de 0,08 % de T). Trois issues lisibles : arrêt juste, arrêt tardif de quelques nm, arrêt par le
  secours. C'est l'action de plus forte valeur de tout cet audit, et ce n'est pas du code.

### 4.3 Deux approximations de sens opposé, sans solde

`ETAT.md` l'écrit : la grille de production (≈ 21 points par couche) est **optimiste** sur les faux points tournants,
la machine lisant ~800 fois une couche de 100 nm. À l'inverse, chaque ancre et la lecture d'arrêt portent le bruit
d'**une** lecture, alors qu'à 4 Hz une cinquantaine de lectures entourent un extremum : un contrôleur qui lisse ou
ajuste connaît ses ancres 3 à 5 fois mieux [calcul : σ/√N sur la zone plate]. Le modèle est donc **pessimiste** sur le
bruit des ancres. `scripts/probe_oms_sequentiel.py` est la référence causale faite pour arbitrer ; je n'ai trouvé
aucun bilan de ses résultats dans `reports/` (seulement des chiffres dans des commentaires du 2026-10-10).

### 4.4 L'étalonnage du bruit [lu + avis]

La docstring part d'une observation « le signal fluctue de 45,5 à 45,55 % » et pose un tirage borné à **±0,05** point
avec σ = A/3. Si 0,05 point est l'excursion **crête à crête** observée, une gaussienne de σ = 0,0167 point donne
~0,083 point crête à crête sur 100 lectures : le modèle serait ~1,7 fois plus bruité que l'observation. Si c'est la
résolution de l'affichage, l'observation ne borne que par le haut. Mille lectures brutes sur un signal stable donnent
σ directement.

## 5. Levier 1 — aussi bien, plus vite

Comptage d'opérations sur le chemin de production (grille grossière, POEM, ancres et inversion exactes), couche `i` :

| poste | opérations par appel | remarque |
|---|---|---|
| matrices d'empilement | `_stack_matrix` réel (i couches) + nominal (i) + `_stack_matrix_pair` (≈ 2(i−4)) + `_exact_poem_anchors` (4 ancres × jusqu'à i) ≈ **8 i produits** à cos/sin complexes | croît avec la profondeur : ~190 produits à la couche 24, ~380 à la 48, ~790 sur un 99 couches |
| balayage du signal | (64 + 4×16) points × 2 signaux × 2 fonctions trigonométriques ≈ **512** | constant |
| bruit | 128 échantillons × 12 hachages ≈ **1 536** tours de hachage | le commentaire D94 note que le tirage coûte plus que les deux appels trigonométriques d'une lecture |
| inversion exacte | pas de recherche + **60** bissections × 2 fonctions trigonométriques | la bissection est stationnaire après ~46 pas |
| détection | 3 passes sur 128 points + la recherche linéaire des ancres | faible |

Leviers, du plus rentable au moins rentable (gains **non mesurés**) :

| | levier | bits | attendu |
|---|---|---|---|
| V1 | **Ne plus reconstruire les matrices** : table nominale par (λ, couche), calculée une fois par stratégie ; matrice réelle portée par tirage et mise à jour d'une couche à la suivante dans un bloc | mêmes produits dans le même ordre ; `c1_diff` dira si `fastmath` bouge les derniers bits | le poste dominant dès ~20 couches ; passe de N² à N |
| V2 | **Sortir le nominal de la boucle Monte-Carlo** : `Ts_n`, son compte d'extrema, ses ancres, `p_poem`, `target_nominal`, `start_dir` ne dépendent ni du tirage ni du bruit (le seuil ne dépend que du niveau de bruit : trois jeux) | identiques par construction | la moitié du balayage et une passe de détection sur trois |
| V3 | Rendre `tp_a`, `tp_b` au lieu de rechercher les ancres par valeur ; fusionner `turning_point_margins` dans la passe de détection | identiques | petit, et corrige les réserves 3 et 4 du §3 |
| V4 | Sortie anticipée de la bissection quand `mid` égale une borne | identiques (la suite est stationnaire) | ~25 % de l'inversion |
| V5 | Bruit en 1 hachage au lieu de 12 (somme de 4 uniformes de 16 bits, support ±3,46 σ, à peine plus large que la troncature à 3 σ) | **réalisations différentes** : inactif par défaut, validation statistique et non au bit | jusqu'au tiers du noyau si le commentaire D94 dit vrai |
| V6 | Récurrence d'angle pour cos/sin sur grille uniforme | derniers bits différents | utile seulement sur la grille machine (800 lectures) |

V1 à V4 ne changent pas le modèle : ce sont les candidats au « aussi bien, plus vite ». Protocole : un profil par poste
sur le juge de paix (sonde à écrire : aucune ne chronomètre le noyau STRAT par poste), puis V2 et V1 un commit chacun,
`python scripts/c1_diff.py HEAD --corpus strat` froid contre froid à chaque fois.

Levier de structure [avis] : sur la grille grossière, le bruit n'agit qu'en trois endroits (deux ancres, une lecture
d'arrêt) et dans deux tests (compte, atteignabilité). Les extrema d'une couche sont connus en forme fermée
(`tan 2δ = R/Q`) : un noyau **événementiel**, qui calcule les extrema au lieu de balayer 128 points, coûterait
O(nombre d'extrema), n'aurait plus d'artefact d'indice (réserve 2) et rendrait les ancres exactes sans D96. C'est un
autre modèle : à comparer à la référence séquentielle, pas à l'actuel au bit.

## 6. Levier 2 — coller à un OMS 5100 réel

Classé par effet attendu sur **ce que STRAT décide** (le choix des λ et des blocs). Tous inactifs par défaut (C1).

| | écart au réel | pourquoi il compte | ce qui le règle | coût |
|---|---|---|---|---|
| R1 | **Le bruit ne dépend pas de λ** (figé, `ETAT.md` section 3) | STRAT *choisit* λ. Lampe halogène, réseau et détecteur donnent un rapport signal sur bruit très inégal entre 400 et 1 000 nm ; un bruit plat rend toutes les λ équivalentes et autorise des λ qui seraient bruitées en salle | une courbe A(λ) : σ de 200 lectures sur substrat nu, tous les 50 nm. Table multiplicative, comme le facteur de fente (C2 conservée) | 10 min de machine, code faible |
| R2 | **D98** (§4.2) | décide si un plan optique pur est déposable | l'essai d'une couche | 30 min de machine, aucun code |
| R3 | **Fente en créneau** : `<T>_B` est intégré sur un rectangle de largeur B [lu] | un monochromateur à fentes égales a une fonction **triangulaire** de largeur à mi-hauteur B, de variance B²/6 contre B²/12 : le biais de fente, déjà mesuré à 62 A dans une couche, serait **doublé** au premier ordre [calcul] | la définition de la « résolution » dans la notice, ou le profil d'une raie ; puis des poids de quadrature | faible |
| R4 | **Face arrière du témoin absente** : le noyau lit `T_front` [lu] | l'instrument lit `T = T_f T_b / (T_b + R_b T_f)` ; les extrema ne bougent pas, mais le swing mesuré est réduit du facteur `T_b² / (T_b + R_b T_f)²` : 0,92 sur verre et **0,85 sur saphir** à haute transmission [calcul]. Bruit, hystérésis et `SWING_MIN` étant en unités mesurées, le modèle est optimiste de 9 à 17 % sur le rapport signal sur bruit | appliquer cette fonction aux deux signaux avant le bruit : une division par point | faible |
| R5 | **Étalonnage de A** (§4.4) | toute l'échelle du bruit | 1 000 lectures brutes | 5 min de machine |
| R6 | **Arrêt sans retard** (figé) | couper à la première lecture passée le niveau ajoute en moyenne dd/2 = 0,06 nm, plus la fermeture du cache : un excès **systématique**, de même signe sur toutes les couches optiques, que les couches suivantes ne compensent qu'en partie | le journal d'un dépôt : instant de consigne contre instant de coupure | une lecture de journal |
| R7 | **Vitesse unique** : `RATE_TURN_NM = 0,125` suppose 0,5 nm/s pour H et L [lu] | une silice déposée deux fois plus vite est lue deux fois moins dense, et sa quantification Rate double | une vitesse par matériau | faible |
| R8 | **Erreur de calage de λ** : aucune [lu] | un écart de ±0,2 nm à chaque changement de λ vaut une erreur d'échelle de 0,04 % sur tout le bloc, de signe tiré par bloc ; le corridor d'indice (±0,005) couvre l'ordre de grandeur mais reste constant sur le dépôt | un tirage par bloc | faible |
| R9 | **Même lecture, deux bruits** : un point lu comme couche courante puis rejoué en historique reçoit deux tirages (admis dans le code) | deux couches voisines qui partagent une ancre devraient partager son erreur | index physique commun aux deux grilles | moyen |

Hors d'atteinte sans la machine, et à y laisser comme l'écrit `ETAT.md` : bruit dépendant de T, grenaille, dérive lente
corrélée. La référence prise à chaque tour par le trou libre du plateau annule la dérive commune de la lampe et des
hublots [avis] ; je ne recommande pas de la modéliser sans un journal qui la montre.

## 7. Ordre proposé

1. **Trois mesures en salle, une heure en tout** : R2 (D98), R1 (A selon λ), R5 (σ sur 1 000 lectures). Elles fixent
   les trois paramètres qui pèsent le plus et qu'aucun code ne peut deviner.
2. **V2 puis V1** : plus vite, mêmes résultats, un commit chacun avec `c1_diff`.
3. **R4 et R3** : deux corrections de physique bon marché, chacune derrière un paramètre inactif, effet mesuré sur le
   juge de paix avant toute activation.
4. **§4.1** : remplacer `SWING_MIN` par un seuil en multiples de A, balayé.
5. **§3, réserves 1 et 2** : mesurer leur fréquence avec `probe_oms_sequentiel.py` avant de toucher au détecteur, et
   consigner enfin ses résultats dans un bilan.

## 8. Ce que cet audit ne dit pas

- Aucun chiffre de gain n'est mesuré ; le poste « matrices » domine d'après un comptage, pas d'après un profil.
- Je ne connais pas l'algorithme d'arrêt de l'OMS 5100 (breveté, `ETAT.md` le dit aussi) : §4.2 est un raisonnement
  d'automaticien, pas un fait sur la machine.
- R3 suppose des fentes d'entrée et de sortie égales ; R4 suppose des couches sans pertes (`R' = 1 − T`).
- La grille machine (`machine_sampling_dd`, lissage) n'est pas en production : je l'ai lue, pas auditée en détail.
