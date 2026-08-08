# Recommandations techniques d'alignement physique : Simulation STRAT vs Machine Réelle

Document rédigé à l'attention de Claude et de l'équipe scientifique.

---

## 1. Analyse comparative : Machine Réelle vs. Kernel STRAT

La simulation du dépôt dans `certus_strat_growth.py` (`simulate_growth_kernel`) est **extrêmement performante et fidèle dans ses principes fondamentaux** (auto-compensation de Macleod, calcul POEM, bruit photométrique et bruit de volet).

Toutefois, une analyse physique et numérique approfondie révèle **4 écarts précis entre le contrôleur physique en laboratoire et le noyau de simulation** :

---

### Écart 1 — Méconnaissance d'indice a priori ($\delta_H, \delta_L \approx \pm 0,5\%$ constant par run)

* **Physique Machine (Constat de laboratoire)** :
  La méconnaissance d'indice sur les machines réelles est d'environ **$0,5\%$** ($\sigma_{\text{calib}} = 0,005$). 
  **Point clé de corrélation** : Cet écart d'indice n'est **PAS un bruit aléatoire indépendant couche par couche**, mais une **imprécision d'étalonnage globale constante pour chaque matériau** tout au long du run :
  - Toutes les couches de matériau H (couches 1, 3, 5, 7...) partagent le même décalage d'indice $\delta_H$.
  - Toutes les couches de matériau L (couches 2, 4, 6, 8...) partagent le même décalage d'indice $\delta_L$.
* **Kernel STRAT** :
  Dans la version actuelle, les indices $n_H(\lambda)$ et $n_L(\lambda)$ sont traités comme 100 % déterministes et égaux aux valeurs théoriques nominales de la base de données.
* **Impact physique** :
  Comme le décalage est **cohérent** sur les 48 couches (et non distribué aléatoirement), l'erreur d'indice de $0,5\%$ ne s'annule pas par moyenne statistique. Elle provoque un décalage spectral global ($\approx 2,5\text{ nm}$ à $500\text{ nm}$) que le suivi optique POEM / point tournant tente d'auto-compenser en ajustant dynamiquement les épaisseurs géométriques $d_k$ de chaque couche pendant le dépôt.
* **Solution préconisée pour Claude** :
  Modéliser l'incertitude d'étalonnage matériau au niveau du run (et non de la couche) dans `_prepare_robustness_inputs` :
  $$n_H^{\text{run}}(\lambda) = n_H^{\text{nom}}(\lambda) \cdot (1 + \delta_H), \quad \delta_H \sim \mathcal{N}(0, 0,005^2)$$
  $$n_L^{\text{run}}(\lambda) = n_L^{\text{nom}}(\lambda) \cdot (1 + \delta_L), \quad \delta_L \sim \mathcal{N}(0, 0,005^2)$$
  $\delta_H$ et $\delta_L$ sont tirés **une seule fois par run Monte-Carlo** et appliqués à toutes les couches H et L respectivement.

---

### Écart 2 — Sous-échantillonnage spatial sur les longs blocs monochromatiques

* **Physique Machine** : Le spectrophotomètre échantillonne le signal à temps fixe ($\Delta t = 100\text{ ms}$), soit un pas spatial constant $\Delta d = v \cdot \Delta t \approx 0,1\text{ nm}$ quelle que soit la longueur du bloc ou le nombre de couches.
* **Kernel STRAT** : `simulate_growth_kernel` évalue la grille de recherche d'extrema sur une taille fixe de **64 points répartis sur l'ensemble du bloc monochromatique** (ligne 436).
* **Le problème** :
  $$\Delta d_{\text{grille}} = \frac{\sum_{k \in \text{bloc}} d_k}{64}$$
  - Sur 1 couche de $40\text{ nm}$ : $\Delta d = 0,625\text{ nm}$ (très bon).
  - Sur un bloc de 10 couches ($600\text{ nm}$) : $\Delta d = 9,375\text{ nm}$ !
  Avec un pas de $9,375\text{ nm}$, deux points tournants proches (ex. séparés de $15\text{ nm}$) sont mal résolus. L'ajustement parabolique à 3 points (`fit_parabola_vertex_3points`) subit une distorsion et peut décaler le point tournant détecté de $1\text{ à } 2\text{ nm}$.
* **Solution préconisée pour Claude** :
  Rendre le nombre de points de grille adaptatif au nombre de couches du bloc :
  $$\text{GRID\_SIZE} = \max(64, 32 \times N_{\text{couches\_dans\_bloc}})$$
  Ceci garantit un pas spatial $\Delta d < 1,0\text{ nm}$ en toutes circonstances sans dégradation mesurable des performances.

---

### Écart 3 — Échelle du signal pour les seuils absolus ($T_{\text{front}}$ vs $T_{\text{mesuré}}$)

* **Physique Machine** : Le spectrophotomètre mesure la transmission totale à travers le substrat, incluant la réflexion de la face arrière :
  $$T_{\text{mesuré}} = \frac{T_{\text{front}} \cdot T_{\text{sub}}}{1 - R_{\text{prime}} \cdot R_{\text{back}}} \approx 0,92 \cdot T_{\text{front}}$$
* **Kernel STRAT** : `simulate_growth_kernel` calcule $T_{\text{front}}$ uniquement (sans face arrière) pour des raisons de vitesse heuristique.
* **Le problème** :
  Pour POEM ($p_{\text{poem}}$), l'invariance affine $a T + b$ garantit que $T_{\text{front}}$ donne l'arrêt exact au nanomètre près. En revanche, les **seuils photométriques absolus** comme `SWING_MIN = 0.04` (amplitude minimale de $4\%$) ou `tp_hysteresis` s'appliquent sur un signal $T_{\text{front}}$ surévalué d'environ $+4\%$ par rapport à ce que lit le contrôleur physique.
* **Solution préconisée pour Claude** :
  Appliquer le facteur d'échelle de transmission du substrat nu $T_{\text{sub\_bare}} = \frac{4 n_{\text{sub}}}{(n_{\text{sub}} + 1)^2}$ au signal heuristique avant l'évaluation de `SWING_MIN` et de `tp_hysteresis`.

---

### Écart 4 — Quantification d'échantillonnage temporel ($\pm \Delta d_{\text{sample}} / 2$)

* **Physique Machine** : La décision de fermeture du volet (*shutter*) par le contrôleur physique se fait lors de la réception d'une mesure discrète. Si la condition d'arrêt est franchie entre deux mesures (ex. à $t = 10,04\text{ s}$ alors que les mesures ont lieu à $10,00\text{ s}$ et $10,10\text{ s}$), le volet ne peut être déclenché qu'au point discret suivant, introduisant une incertitude de quantification d'au plus $\pm \frac{\Delta d}{2} \approx \pm 0,05\text{ nm}$.
* **Kernel STRAT** : STRAT calcule la racine continue exacte $d_{\text{stop\_exact}}$ par interpolation quadratique sans discrétisation.
* **Solution préconisée pour Claude** :
  Pour reproduire la quantification d'échantillonnage temporel de la machine réelle, ajouter un bruit uniforme de discrétisation $\delta d \sim U\left(-\frac{\Delta d_{\text{sample}}}{2}, +\frac{\Delta d_{\text{sample}}}{2}\right)$ avec $\Delta d_{\text{sample}} = 0,10\text{ nm}$ lors des tirages stochastiques de Phase B.

---

## Plan d'action synthétique pour la suite

1. **Modélisation de l'incertitude d'étalonnage matériau ($\delta_H, \delta_L \approx \pm 0,5\%$)** : Tirer $\delta_H, \delta_L \sim \mathcal{N}(0, 0,005^2)$ constants par run Monte-Carlo pour l'ensemble des couches H et L (Écart 1).
2. **Ajustement de la grille spatiale** : Rendre `GRID_SIZE` proportionnel à la longueur du bloc dans `simulate_growth_kernel` ($\Delta d < 1,0\text{ nm}$) (Écart 2).
3. **Étalonnage des seuils absolus** : Appliquer le facteur de transmission substrat $T_{\text{sub\_bare}}$ sur les tests d'amplitude `SWING_MIN` et `tp_hysteresis` (Écart 3).
4. **Bruit de discrétisation** : Injecter l'incertitude de quantification temporelle $\pm 0,05\text{ nm}$ dans les tirages Monte-Carlo (Écart 4).
