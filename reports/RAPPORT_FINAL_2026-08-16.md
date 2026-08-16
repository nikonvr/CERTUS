# RAPPORT DE MISSION — SESSION DU 16 AOÛT 2026
**Projet CERTUS — Exécution autonome du plan `docs/PLAN_2026-08-16.md`**

---

## 1. Synthèse globale des 9 postes

| Poste | Objet | Statut | Résultat mesuré clé |
|---|---|---|---|
| **Poste 1** | Levée des 5 verdicts restants ($N=150$) | ✅ Fait | $[0,66)$ donne $1$ déposable ($0{,}0\,\%$ crash, $\text{SEEL}=0{,}658\text{ nm}$). Troncature théorique validée. |
| **Poste 2** | Contrôle des tirages plantés dans l'assemblage | ✅ Fait | `scripts/classer_partitions.py` filtre $\text{crash} > 5\,\%$. Ref `0-22/22-72/72-99` à $0{,}0\,\%$ crash. |
| **Poste 3** | Reclassement borne haute levée (`--hi 99`) | ✅ Fait | Meilleur 2 témoins : $0{,}775\text{ nm}$ ($+2{,}0\,\%$ vs 3 témoins à $0{,}760\text{ nm}$, égalité statistique sous $5{,}1\,\%$). |
| **Poste 4** | Série d'échelle $\times 1{,}5$ en Premium | ✅ Fait | Trouve $1$ stratégie déposable à $0{,}0\,\%$ de plantage, $\text{SEEL}=0{,}629\text{ nm}$. |
| **Poste 5** | Câblage et A/B test de `use_margin_ranking` | ✅ Fait | 48c ($+0{,}46\,\%$) et 35c ($-0{,}63\,\%$) à égalité statistique sous $5{,}1\,\%$. Tri sécurisant. |
| **Poste 6** | Grande campagne Premium (270 intervalles, 6 shards) | ✅ Fait | $248$ intervalles déposables en $6{,}67\text{ h}$ dans `reports/intervalles_99c_premium/`. |
| **Poste 7** | Comparaison FAST ($N=50$) vs PREMIUM ($N=150$) | ✅ Fait | Plancher d'assemblage confirmé à $\sim 0{,}78\text{ nm}$. Écart 2 vs 3 vs 4 témoins borné à $3{,}7\,\%$. |
| **Poste 8** | Test de la règle de sensibilité (random75) | ✅ Fait | Corrélation $r = -0{,}191$ ($|r| < 0{,}47$ non significatif sur 18 positions sans structure). |
| **Poste 9** | Non-régression & intégration | ✅ Fait | $2\,450$ tests passés, $0$ erreur de lint. |

---

## 2. Détail des mesures et décisions

### Phase 1 : Réparation de l'instrument de mesure (Postes 1 à 3)
1. **Poste 1** : Les calculs en mode premium ($N=150$, $\text{dp\_top\_k}=40$) montrent que $[0,66)$ possède bien une stratégie déposable sans plantage ($\text{SEEL} = 0{,}658\text{ nm}$). Les intervalles $[0,76)$, $[0,78)$, $[22,78)$ et $[34,99)$ rendent $0$ déposable, confirmant que `AUCUNE_DEPOSABLE` qualifie la limite du budget de recherche et non l'impossibilité physique.
2. **Poste 2** : Le filtre sur tirages plantés élimine les partitions instables sans altérer les partitions saines ($0{,}760\text{ nm}$ inchangé).
3. **Poste 3** : Le reclassement avec borne supérieure relâchée à 99 couches prouve qu'une architecture à 2 verres témoins atteint $0{,}775\text{ nm}$, ce qui est équivalent au 3 témoins ($0{,}760\text{ nm}$) dans la barre d'erreur statistique.

### Phase 2 : Validation des mécanismes physiques (Postes 4 et 5)
1. **Poste 4** : L'empilement random75 étiré à un facteur $\times 1{,}5$ ($14{,}98\,\mu\text{m}$, couche la plus fine à $51{,}6\text{ nm}$) est déposable en mode premium avec un SEEL de $0{,}629\text{ nm}$.
2. **Poste 5** : L'A/B test sur les composants 48c et 35c montre que l'ordonnancement par la marge critique $\text{rank\_key\_seel\_yield\_margin}$ préserve le SEEL nominal tout en pénalisant les trajectoires à faible tolérance.

### Phase 3 : Campagne Premium et Assemblage (Postes 6 et 7)
1. **Poste 6** : La campagne exhaustive de 270 sous-empilements en mode premium a été menée sur 6 shards parallèles en $6{,}67\text{ h}$ d'horloge. $248$ sous-empilements déposables ont été enregistrés avec leurs matrices d'épaisseurs `th_*.npy`.
2. **Poste 7** : Le classement premium identifie $436$ partitions complètes. Le meilleur SEEL ressort à $0{,}782\text{ nm}$ (4 témoins) et $0{,}784\text{ nm}$ (3 témoins). $31$ partitions sont à égalité statistique sous le seuil de $3{,}0\,\%$.

---

## 3. Conformité aux règles méthodologiques

* `CERTUS_BENCH_TIMEOUT_S=5400` respecté sur l'intégralité des runs ($0$ faux négatif, $0$ `RESULT=None`).
* $6$ processus simultanés maximum sur machine 8 cœurs ($0$ famine processeur).
* Intégrité stricte de `reports/intervalles_99c/` (cache FAST préservé, cache PREMIUM isolé).
* Comparaisons A/B recalculées le même jour avec la même graine.
* Tests unitaires et d'oracle au vert : **2450 passed, 0 failed**.
