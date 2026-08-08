# Recommandations techniques d'alignement physique : Simulation STRAT vs Machine Réelle

Document rédigé à l'attention de Claude et de l'équipe scientifique.

---

## 1. Analyse comparative : Machine Réelle vs. Kernel STRAT

La simulation du dépôt dans `certus_strat_growth.py` (`simulate_growth_kernel`) est **extrêmement performante et fidèle dans ses principes fondamentaux** (auto-compensation de Macleod, calcul POEM, bruit photométrique et bruit de volet).

Toutefois, une relecture critique et approfondie de la physique du procédé révèle **4 écarts précis entre le contrôleur physique en laboratoire et le noyau de simulation** :

---

### Écart 1 — Méconnaissance d'indice a priori ($\delta_H, \delta_L \approx \pm 0,5\%$ constant par run)

* **Physique Machine (Constat de laboratoire)** :
  La méconnaissance d'indice sur les machines réelles est d'environ **$0,5\%$** ($\sigma_{\text{calib}} = 0,005$). 
  **Point clé de corrélation** : Cet écart d'indice n'est **PAS un bruit aléatoire indépendant couche par couche**, mais une **imprécision d'étalonnage globale constante pour chaque matériau** tout au long du run :
  - Toutes les couches de matériau H partagent le même décalage d'indice $\delta_H$.
  - Toutes les couches de matériau L partagent le même décalage d'indice $\delta_L$.
* **Kernel STRAT** :
  Dans la version actuelle, les indices sont traités comme 100 % déterministes.
* **Impact physique** :
  L'erreur étant cohérente sur tout le run, elle provoque un décalage spectral global que le suivi optique (point tournant/POEM) auto-compense dynamiquement. Ne pas le simuler, c'est surestimer la robustesse nominale.
* **Solution préconisée pour Claude** :
  Modéliser l'incertitude d'étalonnage matériau au niveau du run (tiré une seule fois par exécution de Phase B) :
  $$n_H^{\text{run}}(\lambda) = n_H^{\text{nom}}(\lambda) \cdot (1 + \delta_H), \quad \delta_H \sim \mathcal{N}(0, 0,005^2)$$
  $$n_L^{\text{run}}(\lambda) = n_L^{\text{nom}}(\lambda) \cdot (1 + \delta_L), \quad \delta_L \sim \mathcal{N}(0, 0,005^2)$$

---

### Écart 2 — Sous-échantillonnage spatial (Critique de la densité de grille)

* **Le problème actuel** :
  La grille de recherche d'extrema utilise une taille fixe de **64 points répartis sur l'ensemble du bloc monochromatique**.
  La proposition initiale de lier la grille au *nombre de couches* (`32 * N_couches`) était **naïve et fausse**. Si une seule couche d'espacement (ex. cavité Fabry-Perot) fait $500\text{ nm}$, on aurait 64 points pour $500\text{ nm}$, soit un pas de $7,8\text{ nm}$. Deux extrema proches seraient toujours sous-échantillonnés.
* **Solution corrigée et robuste pour Claude** :
  Le pas spatial maximal de la grille doit être garanti par l'**épaisseur physique totale du bloc** ($D_{\text{bloc}}$) et non par le nombre de couches.
  Pour garantir une résolution spatiale $\Delta d \le 1,0\text{ nm}$ :
  $$\text{GRID\_SIZE} = \max(64, \lceil D_{\text{bloc}} / 1,0 \rceil)$$
  Ainsi, un bloc de $600\text{ nm}$ aura $600$ points, garantissant une détection des extrema et un ajustement parabolique parfaits sans impacter drastiquement la performance globale (l'évaluation TMM vectorisée de 600 points reste sub-milliseconde).

---

### Écart 3 — Échelle du signal pour les seuils absolus ($T_{\text{front}}$ vs $T_{\text{mesuré}}$)

* **Le problème actuel** :
  Le noyau calcule $T_{\text{front}}$ (sans face arrière du substrat) pour des raisons de vitesse. Bien que cela n'affecte pas le suivi relatif (POEM), les **seuils absolus** (comme le filtre `SWING_MIN = 0.04` ou `tp_hysteresis`) sont évalués sur $T_{\text{front}}$, qui est physiquement $\approx 8\%$ plus grand que ce que le spectromètre mesure réellement (une amplitude de $4,2\%$ sur $T_{\text{front}}$ donnerait $3,8\%$ en machine et serait rejetée).
* **Solution préconisée pour Claude** :
  Multiplier le signal heuristique $T_{\text{front}}$ par le facteur de transmission du substrat nu :
  $$T_{\text{sub\_bare}} = \frac{4 n_{\text{sub}}}{(n_{\text{sub}} + 1)^2}$$
  avant de le comparer aux seuils absolus `SWING_MIN` et `tp_hysteresis`.

---

### Écart 4 — Bruit de quantification temporelle (Causalité du déclenchement)

* **Le problème actuel** :
  Il avait été proposé d'ajouter un bruit uniforme centré $\pm 0,05\text{ nm}$ pour modéliser l'échantillonnage de la machine (ex. mesure tous les $100\text{ ms}$). Or, **physiquement, un seuil numérique est causal** : si la cible est franchie à $t = 10,04\text{ s}$, la machine ne la détectera qu'à la mesure suivante à $t = 10,10\text{ s}$.
  Le volet ne se ferme donc **jamais en avance** par rapport au franchissement continu, il est toujours en retard (overshoot).
* **Solution corrigée pour Claude** :
  Le bruit de discrétisation n'est pas $U(-0.05, 0.05)$, mais **strictement positif** :
  $$\delta d_{\text{quantification}} \sim U(0, \Delta d_{\text{sample}})$$
  où $\Delta d_{\text{sample}}$ est l'épaisseur déposée entre deux mesures du spectrophotomètre ($\approx 0,10\text{ nm}$). Ce retard systématique s'ajoute au retard mécanique pur du volet.

---

## Plan d'action synthétique pour Claude

1. **Incertitude matériau** : Tirer $\delta_H, \delta_L \sim \mathcal{N}(0, 0,005^2)$ par run.
2. **Grille spatiale** : $\text{GRID\_SIZE} = \max(64, \lceil D_{\text{bloc}} \rceil)$.
3. **Étalonnage absolu** : Évaluer `SWING_MIN` sur $T_{\text{front}} \times T_{\text{sub\_bare}}$.
4. **Sur-épaisseur de quantification** : Injecter une erreur causale positive $U(0, 0.10\text{ nm})$.
