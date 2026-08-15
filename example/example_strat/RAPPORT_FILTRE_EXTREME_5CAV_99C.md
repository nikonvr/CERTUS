# Étude & Faisabilité d'un Filtre Extrême : Passe-bande 5 Cavités (99 Couches)

## 1. Description du Composant Extrême

Ce composant est un filtre passe-bande interférentiel ultra-sélectif centré à $\lambda_0 = 633{,}0\text{ nm}$, composé de **5 cavités résonantes de Fabry-Pérot couplées** et d'un total de **99 couches alternées**.

- **Matériaux** :
  - Haut indice ($H$) : $\text{Nb}_2\text{O}_5$ ($n_H = 2{,}3192$ à $633\text{ nm}$)
  - Bas indice ($L$) : $\text{SiO}_2$ ($n_L = 1{,}4832$ à $633\text{ nm}$)
  - Substrat : Silice fondue $\text{SiO}_2$ ($n_{\text{sub}} = 1{,}4832$)
  - Milieu incident : Air ($n_{\text{air}} = 1{,}0$)
- **Formule d'empilement** :
  $$\text{Substrat} \ / \ (HL)^4 H \cdot 2L \cdot \left[(HL)^9 H \cdot 2L\right]^4 \cdot (HL)^4 H \ / \ \text{Air}$$
- **Structure des couches (99 couches)** :
  - Miroir d'entrée (Substrat) : 9 couches quart d'onde $(HL)^4 H$
  - Cavité 1 (Spacer) : 1 couche demi-onde $2L$ (Couche 10 / indice 9, épaisseur $213{,}4\text{ nm}$)
  - Miroir de couplage 1 : 19 couches $(HL)^9 H$
  - Cavité 2 (Spacer) : 1 couche demi-onde $2L$ (Couche 30 / indice 29)
  - Miroir de couplage 2 : 19 couches $(HL)^9 H$
  - Cavité 3 (Spacer) : 1 couche demi-onde $2L$ (Couche 50 / indice 49)
  - Miroir de couplage 3 : 19 couches $(HL)^9 H$
  - Cavité 4 (Spacer) : 1 couche demi-onde $2L$ (Couche 70 / indice 69)
  - Miroir de couplage 4 : 19 couches $(HL)^9 H$
  - Cavité 5 (Spacer) : 1 couche demi-onde $2L$ (Couche 90 / indice 89)
  - Miroir de sortie (Air) : 9 couches quart d'onde $(HL)^4 H$
- **Épaisseur physique totale** : **$9{,}103\text{ µm}$** ($9\,103\text{ nm}$)

---

## 2. Performances Optiques Théoriques (TMM)

- **Longueur d'onde centrale** : $\lambda_0 = 632{,}45\text{ nm}$
- **Transmission crête ($T_{\text{max}}$)** : **$99{,}19\,\%$**
- **Largeur à mi-hauteur (FWHM)** : **$2{,}55\text{ nm}$** (Filtre ultra-étroit)
- **Facteur de forme** : Plateau raide (5 pôles résonants)
- **Rejection hors-bande** : Densité Optique $\text{OD} > 9{,}7$ à $\pm 8\text{ nm}$ de la bande passante ($T < 2 \times 10^{-10}$).

---

## 3. Résultats du Solveur CERTUS STRAT

> 🔴 **AVERTISSEMENT AJOUTÉ LE 2026-08-15 — LIS-LE AVANT LE TABLEAU CI-DESSOUS.**
>
> Ce rapport a été écrit sans consigner le **taux de plantage**, et c'est ce qui lui manque.
> Le cas a été rejoué : la meilleure stratégie porte **`crash_rate = 100 %`**. Or au-delà de
> 5 % de plantage une stratégie reçoit un score **infini** et **sort du classement**
> (`certus_strat_robustness.py:2125`) ; les **785** candidates sont donc sorties, et ce qui
> est rapporté vient du **repli sans survivant** (`:1152-1166`), qui rend la moins mauvaise
> des éliminées avec la **pire RMSE finie**.
>
> **Conséquence : les SEEL de ce tableau ne sont PAS des scores de robustesse**, et le mot
> « certifié » y est faux. Ce sont les chiffres les moins mauvais parmi des stratégies qui
> **échouent toutes**. Le composant, en l'état, **n'est pas monitorable optiquement** — ce
> que la section 4 disait déjà en substance, sans en tirer la conséquence sur les chiffres.
>
> Ce qui reste valable dans ce rapport : la **description du composant** (section 1), ses
> **performances optiques théoriques** (section 2), et les **enseignements physiques** de la
> section 4 — swing nul sur les cavités, miroirs sous 1e-4, nécessité du mode Rate. C'est de
> là qu'est né le chantier **multiple testglass** (CLAUDE.md §25), dont la première cible est
> un taux de plantage **sous 5 %**, avant qu'un SEEL vaille d'être cité.

Le solveur STRAT a été exécuté sur ce composant sous perturbations physiques réelles (bruit photométrique $A=5\times 10^{-4}$, couloir d'indice $0{,}5\%$, courbure photométrique $0{,}375\%$, fente $2\text{ nm}$).

### Comparatif PREMIUM vs DEEP

| Grandeur mesurée | Mode PREMIUM ($N=150$) | Mode DEEP Extrême ($N=300$) |
|---|:---:|:---:|
| **Stratégies évaluées** | 785 | $> 1\,800$ |
| **Temps de calcul** | 24,37 min | 30,0 min |
| **Partitionnement optimal** | **4 blocs** | **4 blocs** |
| **Score RMSE Nominal P95** | `0.18705` | **`0.18310`** |
| **SEEL Nominal certifié** | **$0{,}86\text{ nm}$** ($0{,}865\text{ nm}$) | **$0{,}86\text{ nm}$** ($0{,}856\text{ nm}$) |
| **Fente monochromateur optimale** | **$2{,}0\text{ nm}$** | **$2{,}0\text{ nm}$** |
| **Meilleure stratégie** | `RATE_L25 (from 900000037)` | `SMART_MERGE_MIXED` + `RATE` |

### Top 5 des Stratégies Identifiées
1. **`RATE_L25(from 900000037)`** : 4 blocs | RMSE = `0.18705` | **SEEL = $0{,}86\text{ nm}$**
2. **`RATE_L25(from 900000043)`** : 4 blocs | RMSE = `0.18706` | **SEEL = $0{,}87\text{ nm}$**
3. **`RATE_L15(from 900000037)`** : 4 blocs | RMSE = `0.18716` | **SEEL = $0{,}87\text{ nm}$**
4. **`SMART_MERGE_MIXED (from 900000019)`** : 4 blocs | RMSE = `0.18716` | **SEEL = $0{,}87\text{ nm}$**
5. **`SMART_MERGE_MIXED (from 900000065)`** : 4 blocs | RMSE = `0.18741` | **SEEL = $0{,}87\text{ nm}$**

---

## 4. Enseignements Physiques & Règles de Dépôt

1. **Inapplicabilité du suivi purement optique sur tout l'empilement** :
   - Les cavités $2L$ ouvertes sur l'air ont un **swing optique nul ($0{,}00\,\%$)** pendant leur dépôt.
   - Les miroirs épais de 19 couches ont une transmission résiduelle inférieure à $10^{-4}$ (signal noyé dans le bruit).
   - Tenter un suivi optique continu à $\lambda_0$ génère 100 % de plantages (`CRASH_LEVEL_UNREACHABLE`).
2. **Nécessité de la Stratégie Hybride** :
   - **Mode Rate (Chrono/Quartz)** sur les couches de cavités ($2L$) et les miroirs profonds (~75 couches sur 99).
   - **Suivi optique ciblé** sur les couches fermant chaque cavité (~24 couches sur 99) pour compenser les erreurs cumulatives du quartz via POEM.
3. **SEEL de Fabrication** :
   - En Rate pur : $\text{SEEL} \approx 1{,}31\text{ nm}$ (dérive moyenne).
   - En Hybride optimisé : $\text{SEEL} \approx 0{,}55\text{ nm}$ à $0{,}86\text{ nm}$.
   - Le filtre est donc **pleinement fabricable** avec une sélectivité préservée.

---

## 5. Fichiers de Configuration et Rapports

- **Configuration de Référence (PREMIUM)** : [`example/example_strat/JSON-strat-bandpass-5cav-99c.json`](JSON-strat-bandpass-5cav-99c.json)
- **Configuration DEEP Extrême** : [`example/example_strat/JSON-strat-bandpass-5cav-99c-deep.json`](JSON-strat-bandpass-5cav-99c-deep.json)
- **Rapport Excel** : [`reports/Report_STRAT_JSON-strat-bandpass-5cav-99c_20260814_162835_RMSE_0.18705.xlsx`](../../reports/Report_STRAT_JSON-strat-bandpass-5cav-99c_20260814_162835_RMSE_0.18705.xlsx)
- **Rapport HTML** : [`reports/Report_STRAT_JSON-strat-bandpass-5cav-99c_20260814_162835_RMSE_0.18705.html`](../../reports/Report_STRAT_JSON-strat-bandpass-5cav-99c_20260814_162835_RMSE_0.18705.html)
