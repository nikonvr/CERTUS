# Stratégies par blocs : simulations sur 35 et 48 couches

**Date :** 14 août 2026  
**Auteur :** Antigravity (CERTUS Engineering)  
**Machine / Environnement :** CERTUS Headless Solver (8 cœurs, Python 3.14, Windows)  
**Composants de test :** 
1. `example/example_strat/JSON-strat-bandpass-3cav.json` (35 couches $H/\text{SiO}_2$ et $L/\text{Ta}_2\text{O}_5$, 3 cavités Fabry-Pérot résonantes, $\lambda_0 = 633\text{ nm}$).
2. `example/example_strat/JSON-strat-example.json` (48 couches $H/\text{Nb}_2\text{O}_5$ et $L/\text{SiO}_2$, filtre dichroïque passe-haut, $\lambda_0 = 550\text{ nm}$).

---

## 1. Portée

Les tableaux ci-dessous sont des résultats de simulation sur deux composants et trois
modes de recherche. « Meilleur » désigne la meilleure stratégie observée dans ces runs,
pas un optimum global démontré. Les taux de plantage sont ceux du modèle, pas une
mesure de dépôts en atelier. Le SEEL ne se compare qu'à composant fixé.

---

## 2. Benchmark Comparatif des 3 Modes d'Exécution (FAST / PREMIUM / DEEP)

| Composant | Mode d'Exécution | Budget MC & Largeur | Durée | Blocs de la meilleure stratégie | Score RMSE P95 | SEEL ($0{,}01\text{ nm}$) | SEEL Continu | Taux de Plantage simulé | Stratégies Évaluées |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **48c (Dichroïque)** | ⚡ **FAST** | $N=50$, $\text{top\_k}=20$ | $371\text{ s}$ | **6 blocs** | `0.00745` | **$0{,}17\text{ nm}$** | $0{,}173\text{ nm}$ | **$0{,}0\,\%$** | 384 |
| **48c (Dichroïque)** | 💎 **PREMIUM** | $N=150$, $\text{top\_k}=40$ | $570\text{ s}$ | **6 blocs** | `0.00764` | **$0{,}17\text{ nm}$** | $0{,}175\text{ nm}$ | **$0{,}0\,\%$** | 650 |
| **48c (Dichroïque)** | 🔬 **DEEP** | $N=300$, $\text{top\_k}=100$ | $965\text{ s}$ | **6 blocs** | `0.00746` | **$0{,}17\text{ nm}$** | $0{,}173\text{ nm}$ | **$0{,}0\,\%$** | 848 |
| | | | | | | | | | |
| **35c (Passe-bande)** | ⚡ **FAST** | $N=50$, $\text{top\_k}=20$ | $166\text{ s}$ | **5 blocs** | `0.06893` | **$0{,}53\text{ nm}$** | $0{,}525\text{ nm}$ | **$0{,}0\,\%$** | 298 |
| **35c (Passe-bande)** | 💎 **PREMIUM** | $N=150$, $\text{top\_k}=40$ | $248\text{ s}$ | **5 blocs** | `0.06201` | **$0{,}50\text{ nm}$** | $0{,}498\text{ nm}$ | **$0{,}0\,\%$** | 519 |
| **35c (Passe-bande)** | 🔬 **DEEP** | $N=300$, $\text{top\_k}=100$ | $431\text{ s}$ | **6 blocs** | **`0.05819`** | **$0{,}48\text{ nm}$** | $0{,}482\text{ nm}$ | **$0{,}0\,\%$** | 1007 |

---

## 3. Tableaux Détaillés des Performances par Nombre de Blocs

### A. Empilement 48 Couches (Dichroïque)
*Conditions de simulation nominales : corridor d'indice $0{,}005$, fente $2\text{ nm}$, bruit d'ancrage POEM.*

| Architecture | Meilleure stratégie observée | Type Générateur | Score RMSE P95 | SEEL ($0{,}01\text{ nm}$) | SEEL continu | Plantage simulé | Réduction du RMSE P95 vs 48 blocs |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **48 blocs (monocouche)** | `ID 900000044` | ELITE | `0.01803` | **$0{,}27\text{ nm}$** | $0{,}268\text{ nm}$ | $0{,}0\,\%$ | *Référence monocouche* |
| **9 blocs** | `ID 900000029` | ELITE | `0.01066` | **$0{,}21\text{ nm}$** | $0{,}206\text{ nm}$ | $0{,}0\,\%$ | $+40{,}9\,\%$ |
| **8 blocs** | `ID 900000010` | ELITE | `0.01136` | **$0{,}21\text{ nm}$** | $0{,}213\text{ nm}$ | $0{,}0\,\%$ | $+37{,}0\,\%$ |
| **7 blocs** | `ID 900000000` | ELITE | `0.00783` | **$0{,}18\text{ nm}$** | $0{,}177\text{ nm}$ | $0{,}0\,\%$ | $+56{,}6\,\%$ |
| **6 blocs (meilleur observé)** | `ID 900000024` | ELITE | **`0.00745`** | **$0{,}17\text{ nm}$** | **$0{,}173\text{ nm}$** | **$0{,}0\,\%$** | **$+58{,}7\,\%$** |
| **5 blocs** | `ID 900000054` | ELITE | `0.00768` | **$0{,}18\text{ nm}$** | $0{,}175\text{ nm}$ | $0{,}0\,\%$ | $+57{,}4\,\%$ |
| **4 blocs** | `ID 900000019` | ELITE | `0.00806` | **$0{,}18\text{ nm}$** | $0{,}180\text{ nm}$ | $0{,}0\,\%$ | $+55{,}3\,\%$ |
| **3 blocs** | `ID 900000031` | ELITE | `0.00874` | **$0{,}19\text{ nm}$** | $0{,}187\text{ nm}$ | $0{,}0\,\%$ | $+51{,}5\,\%$ |
| **2 blocs** | `ID 900000016` | ELITE | `0.00914` | **$0{,}19\text{ nm}$** | $0{,}191\text{ nm}$ | $0{,}0\,\%$ | $+49{,}3\,\%$ |
| **1 bloc (mono-$\lambda$)** | `ID 900000002` | SMART_MERGE | `0.25738` | $1{,}01\text{ nm}$ | $1{,}015\text{ nm}$ | $0{,}0\,\%$ | $-1327\,\%$ (Aveuglement optique) |

---

### B. Empilement 35 Couches (Passe-Bande 3 Cavités)
*Conditions de simulation nominales : bande $600-660\text{ nm}$ (61 points), corridor d'indice $0{,}005$, fente $2\text{ nm}$, bruit d'ancrage POEM.*

| Architecture | Meilleure stratégie observée | Type Générateur | Score RMSE P95 | SEEL ($0{,}01\text{ nm}$) | SEEL continu | Plantage simulé | Réduction du RMSE P95 vs 35 blocs |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **35 blocs (monocouche)** | `ID 35961` | ELITE | `0.08496` | **$0{,}58\text{ nm}$** | $0{,}583\text{ nm}$ | $0{,}0\,\%$ | *Référence monocouche* |
| **7 blocs** | `ID 900000023` | ELITE | `0.06005` | **$0{,}49\text{ nm}$** | $0{,}490\text{ nm}$ | $0{,}0\,\%$ | $+29{,}3\,\%$ |
| **6 blocs (meilleur observé)** | `ID 900000040` | ELITE | **`0.05819`** | **$0{,}48\text{ nm}$** | **$0{,}482\text{ nm}$** | **$0{,}0\,\%$** | **$+31{,}5\,\%$** |
| **5 blocs** | `ID 900000000` | ELITE | `0.06201` | **$0{,}50\text{ nm}$** | $0{,}498\text{ nm}$ | $0{,}0\,\%$ | $+27{,}0\,\%$ |
| **4 blocs** | `ID 900000013` | RATE_L11 | `0.06431` | **$0{,}51\text{ nm}$** | $0{,}507\text{ nm}$ | $0{,}0\,\%$ | $+24{,}3\,\%$ |
| **3 blocs** | `ID 900000039` | ELITE | `0.07087` | **$0{,}53\text{ nm}$** | $0{,}532\text{ nm}$ | $0{,}0\,\%$ | $+16{,}6\,\%$ |
| **2 blocs** | `ID 990000002` | ELITE | `0.08026` | **$0{,}57\text{ nm}$** | $0{,}567\text{ nm}$ | $0{,}0\,\%$ | $+5{,}5\,\%$ |
| **1 bloc (mono-$\lambda$)** | `ID 900000002` | SMART_MERGE | `0.37429` | $1{,}22\text{ nm}$ | $1{,}224\text{ nm}$ | $0{,}0\,\%$ | $-340\,\%$ (Aveuglement optique) |

---
