# 🔴 QWOT ≠ TURNING POINT — lis ceci avant d'écrire une ligne sur les points d'arrêt

> 👤 2026-08-15 : *« la notion de QWOT est différente de turning point, attention ! »* —
> *« le TP c'est lorsque l'admittance devient réelle, et cela n'a rien à voir avec une couche
> QWOT »* — *« il ne faut plus faire la confusion et empêcher toute IA moins intelligente de
> faire la confusion »*.

Ce document existe parce que la confusion a été commise, dans ce dépôt, le 2026-08-15. Elle
n'était pas visible : elle produisait un nombre plausible et un raisonnement qui se tenait.

---

## 1. Les deux notions, en une phrase chacune

| | définition | dépend de |
|---|---|---|
| **QWOT** | l'épaisseur optique d'**une couche**, comptée en quarts d'onde : `m = 4·n·d/λ` | la couche seule, **et la λ choisie pour compter** |
| **Turning point** | l'instant, pendant la croissance, où **l'admittance du système entier devient réelle** — donc où `T` passe par un extremum | **tout l'empilement déjà déposé**, plus la couche qui pousse, à λ_mon |

Le QWOT est une propriété **locale**. Le turning point est une propriété **du système**.

---

## 2. Ce que dit la formule fermée du noyau

`certus/physics/certus_strat_growth.py:269`, `layer_scan_coeffs`. Pour la couche qui pousse
sur un empilement déjà déposé de matrice `M` :

$$T(d) = \frac{4 n_{sub}}{P + Q\cos 2\delta + R\sin 2\delta}, \qquad \delta = \frac{2\pi n d}{\lambda}$$

Un extremum annule la dérivée, d'où la forme fermée que le code exploite :

$$\boxed{\tan 2\delta = R/Q} \qquad\Longrightarrow\qquad \delta_{TP} = \tfrac{1}{2}\arctan\frac{R}{Q} \;+\; k\,\frac{\pi}{2}$$

avec `R = Im(C·conj(S))`, `C = X + Y`, `S = Y/n + n·X`, `X = M₀₀ + n_sub·M₀₁`,
`Y = M₁₀ + n_sub·M₁₁`.

**Il y a deux choses là-dedans, et les confondre est l'erreur :**

| | |
|---|---|
| ✅ **La PÉRIODE** entre deux turning points consécutifs vaut exactement `π/2` en `δ`, soit **un quart d'onde à λ_mon**. C'est vrai, toujours, et c'est l'origine de la confusion. |
| 🔴 **LE DÉPART** est décalé de `½·arctan(R/Q)`, une phase fixée par **l'empilement du dessous**. Elle n'est nulle que si l'admittance est déjà réelle à `δ = 0`. |

**Conséquence directe** : une couche de **0,6 QWOT peut** traverser un turning point, et une
couche de **1,3 QWOT peut n'en traverser qu'un**. Le compte de QWOT d'une couche **ne
détermine pas** son compte de turning points.

---

## 3. Le seul cas où les deux coïncident — et il se démontre

👤 : *« uniquement sur la première couche d'un substrat nu ça coïncide ! »*

Sur substrat nu, `M = I`, donc :

```
X = 1 + n_sub·0 = 1              Y = 0 + n_sub·1 = n_sub
C = X + Y = 1 + n_sub            S = Y/n + n·X = n_sub/n + n
```

Pour un diélectrique sans pertes, `n_sub` et `n` sont **réels**, donc `C` et `S` sont réels,
donc :

$$R = \operatorname{Im}(C\,\overline{S}) = C_{im}S_{re} - C_{re}S_{im} = 0$$

d'où `tan 2δ = 0`, soit `δ = k·π/2` : **les extrema tombent exactement aux multiples du quart
d'onde.**

📏 **Vérifié numériquement**, `scripts/probe_turning_points.py`, contrôle 1, sur 61 longueurs
d'onde de 450 à 750 nm : **|R| max = 0.00e+00**. Exactement zéro, pas « petit ».

🔴 **Et dès la couche 2 c'est perdu** : après une seule couche non-QWOT, le déphasage médian
mesuré vaut **0,109 rad (6,2°)**, maximum 0,207 rad (11,9°).

**L'autre cas de coïncidence** est celui que 👤 cite en premier : un empilement **entièrement
en QWOT à λ_mon**. L'admittance y est réelle à chaque frontière de couche, donc le décalage
retombe à zéro. C'est le cas des miroirs quart d'onde — et de personne d'autre.

---

## 4. Le second piège, indépendant du premier : à quelle λ compte-t-on ?

`stack_multipliers` est en QWOT à **λ₀**. Le turning point se produit à **λ_mon**, que le
solveur choisit librement dans `scan_wl_min .. scan_wl_max`.

> Une couche de **0,5 QWOT à 633 nm** en fait **0,70 à 450 nm**.

Donc même dans le cas où la coïncidence est valide, elle porte sur **le quart d'onde à la
longueur d'onde de contrôle**, jamais à λ₀. Compter les QWOT à λ₀ pour prédire des points
d'arrêt est faux deux fois.

---

## 5. 📏 De combien on se trompe — la mesure

Empilement aléatoire de 75 couches, quatre échelles, 61 λ candidates
(`reports/turning_points_vs_qwot.json`) :

| échelle | QWOT min à λ₀ | comptage **NAÏF** « couches sous 1 QWOT » | comptage **JUSTE** « couches sans aucun TP » | λ offrant un TP par couche (médiane) |
|---|---|---|---|---|
| ×0,5 | 0,252 | **59 / 75** | **1 / 75** | 49 / 61 |
| ×1 | 0,504 | 11 / 75 | **0 / 75** | 61 / 61 |
| ×1,5 | 0,756 | 3 / 75 | **0 / 75** | 61 / 61 |
| ×2 | 1,008 | 0 / 75 | **0 / 75** | 61 / 61 |

🔴 **Facteur 59 sur le cas le plus mince.** Le comptage naïf annonçait un composant
essentiellement aveugle ; il est en réalité servi sur 49 des 61 longueurs d'onde candidates.

---

## 6. Les règles à appliquer

1. **N'écris jamais « couche sous 1 QWOT » comme synonyme de « pas de point d'arrêt ».**
   C'est faux sauf sur la couche 1 d'un substrat nu, et encore, à λ_mon.
2. **Pour compter des points d'arrêt, utilise `tan 2δ = R/Q`**, pas l'épaisseur de la couche.
   La sonde `scripts/probe_turning_points.py` le fait déjà.
3. **Le vrai critère de basculement en mode Rate n'est pas une épaisseur** : c'est
   `swing < SWING_MIN`. C'est écrit dans [`MODE_RATE.md`](MODE_RATE.md) depuis le 2026-08-09, et une couche de
   30 nm à faible contraste d'indice peut être aussi pauvre qu'une ultrafine.
4. **« Le témoin est en QWOT » n'est pas une hypothèse gratuite** : elle est vraie pour un
   miroir quart d'onde, fausse pour un design quelconque. Un raisonnement qui la suppose
   doit le dire.

🔒 Un garde mécanique existe : `scripts/check_claude_md.py` refuse désormais toute phrase de
la documentation qui assimile les deux notions. Ne le contourne pas — corrige la phrase.
