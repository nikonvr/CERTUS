# ⚡ FEUILLE DE ROUTE — ce qui est acquis, puis ce qui vient

> Extrait de `CLAUDE.md` le 2026-08-16. Ce contenu **fait autorite** ;
> `CLAUDE.md` n'en garde qu'un renvoi. 🔑 **Un fait, un seul endroit** — si tu corriges
> quelque chose ici, ne le recopie pas ailleurs, mets un lien.

---


**Établie le 2026-08-09**, après l'audit de §24. Elle **remplace** l'ancien tableau T0–T7, qui
présentait comme à faire du code déjà écrit et comme faites des mesures qui ne l'étaient pas.
La correspondance avec les anciens numéros est donnée en colonne.

### Les trois règles qui fixent cet ordre

1. **Une sonde bon marché qui peut invalider un gros travail passe AVANT ce travail.** Le
   palier 0 coûte des minutes et décide de plusieurs jours.
2. **Rien de comparatif ENTRE DATES avant que le repère soit rétabli.** Tant que A7 n'est pas
   faite, un `RESULT` ne se compare pas à un `RESULT` d'une autre date ou d'un autre réglage
   du modèle. ⚠️ Cela **n'interdit pas** de comparer des runs **à protocole fixé** dans une
   même campagne — voir la précision sous A7.
3. **Rien de mesuré avant d'être mesurable isolément** (contrainte C3). C'est pourquoi le
   palier 2 précède le palier 3.

Après **chaque** action : `pytest tests/oracle/ tests/unit/ -q --no-cov` → `0 failed` (🔴 **ne compare pas à un COMPTE** : il change dès qu'on ajoute un test — 2 453 puis 2 456 dans la seule journée du 2026-08-19. Voir `CLAUDE.md` §2) `#
5 skipped` · `ruff check .` → `All checks passed!` · commit · et tu écris ce que tu as mesuré,
sortie collée. **Une action, un commit.**

### 🟢 Ce qui est déjà outillé — ne le réécris pas

| Outil | Ce qu'il fait | Remplace |
|---|---|---|
| `scripts\preflight.py` | Les 7 vérifications d'environnement en une commande, verdict `PREFLIGHT=GO` / `STOP` | §4 en entier |
| `scripts\probe_tp_fabrication.py` | **A1 et A2, faites.** Fabrication d'extrema et survie des vrais, avec le vrai détecteur et le vrai générateur de bruit | A1, A2 |
| `probe_anchor_noise_pipeline.py` | Écrit sa configuration effective dans `r["config"]`, dans le nom du fichier, **et l'annonce dans les 2 s** ; refuse une valeur illisible au lieu de retomber sur le défaut | le trou de traçabilité de §24-7, et §24-11 |
| `scripts\run_campaign.py` | **Une commande = toute une campagne.** Environnement construit en dictionnaire, aucun shell, chaque run vérifié contre la configuration demandée, reprenable | une nuit de commandes tapées à la main |

### ✅ CE QUI EST ACQUIS — ne le refais pas, et ne le redemande pas

Seuls les **faits qui gouvernent encore** figurent ici ; le déroulé est dans `git log`.

| | Ce qui en reste |
|---|---|
| **A1, A2** | Le seuil anti-fabrication vaut **1,00 A** à `k = 8`, `N = 800` — mesuré, pas dérivé. `0,354` est réfuté (§18). Les vrais extrema survivent au lissage. |
| **A6** | Le banc **est** déterministe à état compilé constant. C'est la **recompilation** qui décale les bits, de 2,819e-11, reproductiblement (§9). |
| **A8** | 🔴 **INACHEVÉE, et l'inverse de ce qui était écrit ici.** `machine_sampling_dd` existe, il est exposé dans l'interface (*« Machine grid (nm, 0=off) »*) et livré dans **9 configurations d'exemple** — mais **AUCUN des 27 sites d'appel du noyau ne le lui passe** (vérifié le 2026-08-15). Le noyau reçoit donc **toujours** son défaut `0.0`. Le réglage est **inatteignable** : ce n'est pas « 0 par défaut », c'est 0 quoi qu'on fasse. La grille fine ne s'active que par `smoothing_window > 1` — **la soudure de §24-2 n'est donc PAS défaite**, elle est seulement masquée par un bouton qui ne fait rien. |
| **A10, A14** | Le corridor atteint la notation. Courbe : `×1,23 · ×2,03 · ×2,41 · ×4,66`, exposant **0,545** (§24-29). |
| **A12** | POEM protège d'un facteur **×41,2** sous distorsion affine (§24-29). ⚠️ **Cite la protection, jamais le dommage résiduel** : +0,9 % sur une graine, +98 % sur une autre. |
| **A15** | La marge Phase A change ce qui est **offert**, jamais ce qui est **retenu** (§24-12). |
| **A17** | Le facteur de bruit par fente est une **table de 4 entrées** ; une fente absente **lève**. |
| **A20** | L'entonnoir Phase A → Phase B **ne fuit pas**, sur ce cas (§24-27). |
| **A23** | Étages 0, 2 et 3 faits. La marge prédit le plantage d'un facteur **22**, validée non circulairement (§24-41). |
| **Tri de §22** | `rank_key_seel_yield_margin` écrit et testé. Tourne **dans la sonde**, à côté de l'ordre du pipeline — SEEL vit à l'étape 0 de l'interface, l'en sortir reste à faire. |
| **Fente** | Biais = **profil** variant avec l'épaisseur, boxcar intégrée exactement, Phase A comprise (§30). |
| **Stratégies par Blocs** | **6 blocs est le meilleur compte MESURÉ sur 35c et 48c** : SEEL **0,583 → 0,482 nm** sur 35c et **0,269 → 0,173 nm** sur 48c, plantage 0,0 %, et **5 mouvements de monochromateur au lieu de 34 et 47** (§24-43). ⚠️ **Pas « optimum global »** : 8 à 34 blocs n'ont jamais été mesurés sur le 35c, et 6 n'y gagne qu'en DEEP — FAST et PREMIUM rendent 5. ⚠️ Les **+31,5 % / +58,7 %** qui circulent sont des gains de **RMSE** ; en SEEL, la seule unité qui compte, ils valent **+17,2 % et +35,7 %**. |
| **Modes FAST/PREMIUM/DEEP** | 3 profils en UI et solveur, $N = 50 / 150 / 300$ et `dp_top_k` = 20 / 40 / 100 (§24-46). ⚠️ Un `crash_rate` lu sous FAST n'est **pas publiable** : le criblage y est à 10 tirages, donc quantifié à 10 %, et un « 0,0 % » veut dire « sous 10 % ». Cite le SEEL sous FAST, le plantage sous PREMIUM ou DEEP. |
| **Phase A Block-Aware** | Bonus $C \leftarrow C_{\text{local}}/\sqrt{\text{streak}}$, seuil `streak >= 2`, dans `certus_strat_objectives.py:415` (§24-45). 🔴 **Il ÉCRASE le coût local en place**, sans copie — `cost_raw` contient déjà le coût bonifié. 🔴 **Et il court AVANT la normalisation**, dont la moyenne porte sur les coûts déjà bonifiés : les candidates **non** bonifiées voient donc leur coût normalisé **monter**. Ce n'est pas un ré-ordonnancement neutre. 🔑 La normalisation élevant au carré (`certus/core/certus_strat_objectives.py:456`), **ce que la DP voit est $C/\text{streak}$, pas $C/\sqrt{\text{streak}}$** — un bloc de 9 couches est favorisé d'un facteur 9, pas 3. |

### ⏳ EN COURS AU 2026-08-14 — lis ceci avant de lancer quoi que ce soit

| | |
|---|---|
| 🟢 **Correctif 1 VALIDÉ** | Deux runs, N = 50 et N = 500 : survivantes et héritage **identiques terme à terme** sur les 10 blocs, là où les deux derniers tombaient de `12, 9` à `2, 3`. §33 |
| 🔴 **Correctif 2 : la campagne A TOURNÉ, et elle n'est PAS exploitable** | 6 runs sur 6 le 2026-08-14, **55 min 16 s** au total (`reports/probe_runs.tsv`, colonne `run_s` — et non ~3 h 30 comme annoncé). Mais `run_campaign.py` marque les **6 runs FAILED**, et il a raison. Voir ci-dessous. §33 |
| ⚠️ **`N = 300` reste conditionné au correctif 2** | Le chiffre vient de la sensibilité du filtre actuel, et le correctif 2 n'est toujours pas mesuré **exploitablement**. Ne le remesure pas avant d'avoir réparé la traçabilité — §33 |

#### 🔴 Pourquoi les 6 runs de la porte sont FAILED, et ce qu'il faut réparer d'abord

**Cause racine, vérifiée dans le code :** `crash_gate_confidence` est dans `_OVERRIDES`
(`scripts/probe_anchor_noise_pipeline.py`) mais **absente de `TRACED_KEYS`**. La clé est donc
**appliquée** au run et **jamais consignée** dans `r["config"]`. `run_campaign.py` compare le
demandé à l'appliqué, ne trouve pas la clé, et déclare l'écart :
`crash_gate_confidence: asked 0.95, applied '<absent>'` — sur les 6 runs.

C'est le **point 7 de §24 qui se rouvre** : un run qui ne consigne pas sa configuration n'est
comparable à rien. Ajouter la clé aux **deux** listes, et au nom du fichier de sortie, avant
tout autre travail sur la porte.

**Et deux résultats de cette campagne demandent une explication avant d'être crus :**

| | |
|---|---|
| 🔴 **G1.off et G1.on rendent un score BIT-IDENTIQUE** | `0.006138704636203437` des deux côtés — porte OFF et porte armée à 95 % — avec des **gagnantes différentes** (900000127 contre 900000116). Une porte qui ne change pas le score au dernier bit peut être **inerte**. À trancher par un compte de rejets, pas par lecture du code (§12, contrôle 4). |
| 🔴 **Le témoin C1 n'a pas reproduit sa référence** | Attendu `0.006151532415266679` à ~1e-11 près, obtenu **`0.00611049163380679`** — écart 4,1e-5, soit **six ordres de grandeur** au-delà de l'enveloppe annoncée. Un témoin qui ne reproduit pas invalide la campagne qu'il devait garantir. |
| ⚠️ **Une propriété testée est peut-être violée** | `tests/unit/test_strat_crash_gate_confidence.py:125` pose que la porte armée **ne peut qu'AJOUTER** des stratégies, jamais en retirer. Vérifie `len(ranking)` entre les deux bras avant de conclure : si le bras armé en retire, c'est un **défaut**, et le test l'énonce déjà. |

⚠️ **Le « 1046 cas » de §34 est faux.** L'énumération réelle de la porte fait **127 cas** —
`for n_runs in (10, 25, 50, 150, 300, 500)` à pas sauté, `test_strat_crash_gate_confidence.py:127`.
Le nombre 1046 n'existe nulle part dans le dépôt.

### 🔴 LA SUITE IMMÉDIATE

**Si tu reprends ce dépôt et que tu ne sais pas par où commencer : §34.** Il porte
**A25, A26, A27**, écrites pour être exécutées — fichier, fonction, ligne d'ancrage, test
qui doit échouer sur le code d'avant, et pièges. **A25 d'abord** : c'est la seule action
du document qui puisse rendre STRAT *vrai* plutôt que simplement *cohérent*.

Ce qui suit reste ouvert et garde sa valeur, mais aucune de ces entrées n'est aussi prête
à être prise en main.


0. 🔑 **RÉTABLIR LE REPÈRE.** Le biais de fente est actif par défaut depuis le
   2026-08-11 : **tout chiffre mesuré avant cette date répond à une autre question**,
   celle d'une machine à fentes infiniment fines. §21 est périmé, et avec lui la courbe
   de corridor, le ×41,2 de POEM et la falaise. Un run neutre, et on repart.
1. **Trancher la grille** — §33, campagne de 8 runs, critère posé à l'avance.
2. **Sortir SEEL de l'interface** (§22, action 1), sans quoi le tri de §22 ne peut pas
   remplacer celui du pipeline.
3. **Comprendre l'effondrement de `n_ranked` avec le corridor** — 228 → 165 → 78
   (§24-30). Contrôle 4 de §12 : **compter les rejets**.
4. **§24-14 reste ouvert** — `dp_yield_weight` n'atteint pas le calcul (§24-33).

### PALIER 0 — Quatre sondes qui ne coûtent rien et qui décident du reste

Aucune ne demande le banc, ni le repère, ni une machine libre. **Minutes chacune.** Elles
peuvent toutes être faites aujourd'hui.

#### A4 — Compter ce que les filtres existants rejettent · *§12-contrôle 4*

> **Compte les rejets, ne lis pas le code.** Un filtre inerte ne produit aucune erreur — il
> produit un résultat plausible. C'est ainsi qu'une règle de proximité recevant une matrice
> de zéros n'a rien interdit sur 51 candidates × 48 couches, en silence.

| # | Filtre | Où | Attendu |
|---|---|---|---|
| 1 | `phase_a_level_margin_factor` | log `[MARGIN]`, `certus_strat_service.py:1037` | **compter** les candidates rejetées, par couche |
| 2 | 🔴 **D'abord corriger le facteur √3** — la fente est rectangulaire, la formule est trop stricte de 1,73× ([`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.7) | `_calculate_strategy_spectral_resolution:281` | `res_limit = test_bw * np.sqrt(3.0 * T_tolerance / curvature)` |
| 3 | `min_resolution`, **sur la formule corrigée** | idem | **combien de stratégies** seraient écartées à chacune des 4 résolutions |
| 4 | `tp_hysteresis` | sentinelles `CRASH_TP_MISCOUNT` vs `CRASH_LEVEL_UNREACHABLE` | les **séparer** dans le rapport (`int(val // 1e6)`) |
| 5 | Un filtre qui rejette **0** | — | **c'est un défaut**, pas un succès. Signale-le |

⚠️ L'étape 2 est un changement de formule, donc un commit à part, avec son test. Elle
**élargit** les fentes admissibles : compter les rejets avant la correction donnerait un
chiffre faux dans le sens sévère.

---

### PALIER 1 — Rendre le banc digne de confiance

#### A5 — Le harnais d'empreinte `float.hex()` · *le SEUL instrument de la règle d'or*

La règle d'or de §9 exige une non-régression **au bit**, et **aucun outil ne permet de la
vérifier**. Le banc ne peut pas servir : il a ~3e-11 de gigue irréductible (§9, §21).
**A5 n'est donc pas un confort, c'est le seul moyen de vérifier C1.** Tant qu'il n'existe pas,
aucune des actions du palier 2 ne peut être validée.

- **Où** : `tests/oracle/` — c'est un oracle, pas un test unitaire.
- **Quoi** : balayer une large batterie de configurations de `simulate_growth_kernel`
  (couches, λ, épaisseurs, graines), capturer `float.hex()` de chaque sortie, écrire une
  empreinte. Un mode `--compare` qui exige **zéro** différence.

🔴 **Le harnais force `NUMBA_NUM_THREADS=1`**, avant tout import de numba. Sans cela il
mesure la gigue du banc au lieu du calcul, **et il a l'air de fonctionner tout en ne prouvant
rien** — le pire des trois états.

| # | Étape | Attendu |
|---|---|---|
| 1 | Capturer l'empreinte sur `HEAD` | fichier d'empreinte, ≥ 10 000 configurations |
| 2 | Relancer sans rien changer | **zéro** différence |
| 3 | Relancer avec `NUMBA_NUM_THREADS=4` | **zéro** différence aussi — sinon le mono-thread n'est pas réellement forcé |
| 4 | Changer un chiffre du noyau exprès | l'empreinte **doit** bouger |
| 5 | Remettre en état | zéro différence |

⚠️ Les étapes 3 et 4 sont les seules qui prouvent que le harnais fonctionne. Ne les saute pas.

#### A7 — Rétablir le repère · *ex-T0*

```bat
set CERTUS_BENCH_TIMEOUT_S=5400
C:\envs\certus\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

| # | Étape | Attendu |
|---|---|---|
| 1 | Machine **libre**. Ni tests, ni lint, ni recherche récursive | — |
| 2 | Vérifier `WAIT_EXIT` **avant** de lire `RESULT` | pas `timeout` |
| 3 | Vérifier le nombre de stratégies | si le run n'a pas abouti, **ne lis pas le RESULT** |
| 4 | Vérifier le bloc `CONFIG=` de la sortie | tous les paramètres à leur valeur neutre |
| 5 | **Relancer une seconde fois, identique** | 🔴 **jette le premier** : après une recompilation numba il sort systématiquement du lot |
| 6 | Comparer les deux | l'écart doit tenir dans l'enveloppe de A6, **pas être nul** |
| 7 | 🔴 **TOUJOURS À REFAIRE au 2026-08-15.** Le repère du 2026-08-10 décrit une machine sans fente | — |

🔑 **Ne confonds pas A7 avec les repères de §21 — ce sont deux objets différents.**

| | A7 | §21 |
|---|---|---|
| l'objet | un `RESULT` de `probe_anchor_noise_pipeline.py` | le **SEEL** de composants entiers |
| son usage | ancrer des mesures **entre dates** et entre configurations du modèle | dire ce que la méthode **atteint** sur un composant |
| état | 🔴 **absent** | 🟢 **quatre repères valides, fente 2 nm** |

**Ce que l'absence de A7 interdit, et ce qu'elle n'interdit pas.** Elle interdit de comparer un
`RESULT` d'aujourd'hui à un `RESULT` d'une autre date ou d'un autre réglage du modèle. Elle
**n'interdit pas** les comparaisons faites **à protocole fixé** — c'est ce que fait toute la
campagne du 2026-08-15 (fast, fente 2 nm, graine 42, N = 50), où seule la position du
changement de témoin varie. Ces comparaisons sont valides **entre elles** et ne prétendent à
rien au-delà.

⚠️ **Ne cherche pas l'identité au bit** — elle est impossible ici, voir §9. Un écart nul entre
deux runs serait une coïncidence, pas un critère.

---

### PALIER 2 — Rendre mesurable ce qui est déjà écrit

#### A8 — Dé-souder la grille du lissage · *ex-T3, §24-2*

`SAMPLE_DD = 0.125` n'existe qu'à l'intérieur de `if smoothing_window > 1:`. La configuration
« grille fine, fenêtre à 1 » — celle que T3 impose d'observer — **n'est pas exprimable**.

- **Où** : `certus/physics/certus_strat_growth.py`, `simulate_growth_kernel`, ligne ~652.
- **Quoi** : une clé JSON `machine_sampling_dd` (défaut **0,0 = inactif = grille actuelle**),
  indépendante de `reading_smoothing_window`.

| # | Étape | Attendu |
|---|---|---|
| 1 | Empreinte A5 avant | référence |
| 2 | `machine_sampling_dd = 0` et `k = 1` | empreinte **identique au bit** |
| 3 | `machine_sampling_dd = 0,125`, `k = 1` | **doit devenir exprimable** — c'est le but |
| 4 | `machine_sampling_dd = 0`, `k = 8` | doit rester exprimable aussi |
| 5 | Les 4 combinaisons donnent 4 résultats **distincts** | sinon un des deux drapeaux n'atteint pas le calcul |

#### A9 — Moyenne centrée au lieu de causale · *§24-3*

La moyenne actuelle porte sur `[i−k+1 … i]` : elle décale un extremum de `(k−1)/2`
échantillons, soit **0,44 nm à k = 8**. §18-5 pose « aucun retard » en postulat figé.

- **Où** : même fonction, boucle de lissage, ligne ~747.
- **Quoi** : fenêtre `[i−⌊k/2⌋ … i+⌊k/2⌋]`, bords traités par fenêtre rétrécie symétrique.

| # | Étape | Attendu |
|---|---|---|
| 1 | Signal propre **sinusoïdal** d'extremum connu, `k = 8` | position de l'extremum détecté **inchangée** à moins d'un échantillon |
| 2 | Même chose avec la moyenne causale | décalage de **≈ 3,5 échantillons** — c'est ce qu'on corrige |
| 3 | `k = 1` | empreinte identique au bit |
| 4 | Rejouer A1 avec la centrée | le chiffre de fabrication ne doit pas se dégrader |

#### A11 — Les tests qui manquent · *§24-5*

`f7a3d71`, `e0df0e1`, `162a0ff` n'ont ajouté **aucun** test, et aucun test ne mentionne les
nouveaux paramètres. Le contrôle 2 de §12 est donc inapplicable.

| # | Test à écrire | Doit échouer sur |
|---|---|---|
| 1 | `poem_enabled = False` force bien le repli absolu | `f7a3d71^` |
| 2 | `affine_scale ≠ 1` déplace l'arrêt du repli, **pas** celui de POEM | `76f7a8f^` |
| 3 | `reading_smoothing_window = 8` réduit la variance du signal de `√8` | `e0df0e1^` |
| 4 | `index_corridor > 0` fait diverger réel et nominal | `162a0ff^` |
| 5 | `index_corridor > 0` change le **score** | **HEAD** — c'est le test qui prouve A10 |
| 6 | Chaque nouveau paramètre à sa valeur neutre est **bit-identique** | — |

🔴 **Copie chaque test dans le worktree baseline et vérifie qu'il ÉCHOUE.** Un test qui passe
avant le correctif ne prouve rien. C'est le contrôle le plus rentable de §12.

---

### PALIER 3 — Les mesures qui devaient déjà exister

Toutes au banc, **une machine par run**, `CERTUS_BENCH_TIMEOUT_S=5400`, et le bloc `CONFIG=`
vérifié avant de lire le moindre chiffre.

#### A13 — La paire grille + lissage · *ex-T3 et T4*

**Ne conclus rien entre les deux.** Le taux de plantage n'a de sens qu'une fois les deux en
place.

🔴 **Le seuil à utiliser est `1,00`, pas `0,354`.** A1 a mesuré que 0,354 laisse **100 %** de
fabrication à `k = 8`, `N = 800` — voir §18. `1,00` est la borne **mesurée**, pas dérivée.

| # | Run | Attendu |
|---|---|---|
| 1 | `sampling_dd = 0,125`, `k = 1`, seuil 1,66 | le plantage **monte beaucoup**. **C'est attendu, pas un bug** |
| 2 | `sampling_dd = 0,125`, `k = 8`, seuil **1,00** | il doit **redescendre** |
| 3 | Si (2) ne redescend pas | **dis-le. Ne remonte pas le seuil** |
| 4 | Balayer `k ∈ {1, 4, 8, 16}` | ⚠️ **le seuil ne suit PAS `1/√k`** — cette loi est réfutée. **Remesure la borne avec `probe_tp_fabrication.py` pour chaque `k`**, puis utilise la valeur mesurée. **Piège 1** : si le plantage ne bouge pas avec `k`, le lissage n'atteint pas le calcul |

---

### PALIER 4 — Le neuf

#### A16 — Quantification de l'arrêt · *ex-T7, [`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.5*

Quasi gratuit une fois A8 faite : s'arrêter au **premier point de grille au-delà du seuil**
au lieu d'interpoler, et `U(0 ; 0,125 nm)` apparaît d'elle-même, sans paramètre.
**Vérification** : Piège 1 — si doubler `Δd_sample` ne change rien, la mesure est un artefact.

#### A18 — Résolution : variable de stratégie en Phase B · *[`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.7*

Conditionnée par A17-4. Une stratégie devient *(blocs, λ par bloc, résolution)*. **Phase B**,
pas Phase A, pas la DP — voir [`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.7 pour le raisonnement.

#### A19 — Mode Rate · *§22*

`sigma_rate` est **dérivé**, pas posé — voir la dérivation du §22. Reste à obtenir les
réponses Q1 à Q4 avant d'écrire une ligne.

---

### PALIER 5 — Les questions de fond, celles qui décident de l'architecture

#### A23 — 👤 La couche critique, et comment mesurer un risque qui vaut zéro

> 👤 *« Ce serait bien pour chaque stratégie de mentionner la couche la plus critique, celle
> où il y a le plus de risque de plantage. Si les stats sont à zéro niveau plantage, il
> faudrait du coup augmenter les bruits ou dérive d'indice d'un facteur que je ne maîtrise
> pas. »* (2026-08-10)

**Le problème porte un nom : estimation d'événements rares.** À 150 tirages et zéro plantage,
on sait `p < 2 %` et rien de plus. Résoudre `p = 0,1 %` demanderait ~3000 tirages par
stratégie. Et amplifier le bruit — le réflexe naturel — est **le piège que ce projet a payé
trois fois** (Piège 1), parce que la compensation POEM n'est pas linéaire : le taux mesuré à
2× ne se ramène pas simplement à 1×.

##### 🟢 Étage 0 — l'information par couche existe DÉJÀ et elle est jetée

```python
crashed_cells = sim_thick_batch > CRASH_SENTINEL_MIN     # (n_runs, n_layers)
n_crash_run = np.count_nonzero(np.any(crashed_cells, axis=1))   # <- ecrase les couches
```

`certus_strat_robustness.py:946-948`. Le tableau est **par (run, couche)**, et `np.any` sur
l'axe 1 le réduit avant qu'on l'ait regardé. `crashed_cells.sum(axis=0)` donne le nombre de
plantages **par couche**. Quelques lignes, aucun run supplémentaire.

⚠️ **Mais « où ça plante » n'est pas « qui est responsable ».** La sentinelle est écrite là où
le dépôt s'arrête. Une couche amont mal déposée peut faire échouer une couche aval par
propagation — c'est même tout le sujet de la chaîne de compensation. Rapporter les deux, ne
jamais les confondre.

##### 🔑 Étage 1 — LA propriété qui change la réponse : les tirages sont BORNÉS

La fiabilité classique répondrait « indice de Hasofer-Lind, `β = marge/σ`, `p ≈ Φ(−β)` ».
**Ce serait faux ici, et faux dans une direction connue.**

Presque toutes les perturbations de ce modèle sont **bornées** : le bruit de lecture est tiré
dans `±A`, le corridor respecte `|a| + |b| ≤ δ_max`, les amplitudes affines sont bornées.

> **Si la marge dépasse la perturbation maximale possible, la probabilité n'est pas petite :
> elle est EXACTEMENT nulle.**

[`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.2 s'en sert déjà — *« le tirage étant borné à ±A, l'écart maximal du bruit seul vaut 2A »*.
Un `β` gaussien extrapolerait une probabilité faible **là où la vérité est zéro**, et il le
ferait **toujours dans le sens pessimiste**. Le premier test n'est donc pas probabiliste, il
est **déterministe** :

```
marge(couche, cause)  >  perturbation maximale possible   ->  p = 0, exactement
                      <=                                   ->  p > 0, et on passe a l'etage 2
```

##### Étage 2 — la marge, pas l'événement

Pour les couches qui *peuvent* échouer, on cesse de compter des plantages et on mesure une
**fonction d'état limite** : à quelle distance était-on du franchissement ? C'est continu,
toujours défini, et informatif **à zéro plantage**.

| Sentinelle | Marge | Signe |
|---|---|---|
| `CRASH_LEVEL_UNREACHABLE` | `T_visé − T_extremum atteignable`, en unités de T | le swing rétrécit ⇒ la cible sort |
| `CRASH_TP_MISCOUNT`, extremum **manqué** | `swing − hysteresis` | ondulation trop faible |
| `CRASH_TP_MISCOUNT`, extremum **fabriqué** | `hysteresis − excursion du bruit` | c'est la grandeur que A1 a mesurée |

🔴 **Une seule marge par couche est trop grossière.** Il en faut une **par couche ET par
cause** : les trois n'ont ni les mêmes unités, ni la même physique, ni le même remède. C'est
le corollaire 2 du Piège 1 — *ne jamais confondre deux causes sous une même sentinelle*.

**La couche critique est celle de plus petite marge normalisée**, et elle est désignée même
quand aucun run n'a planté.

##### Étage 3 — calibrer l'extrapolation là où l'on sait compter

C'est le geste qui sépare le sérieux de l'astuce, et **il ne coûte aucun run** : les trois
niveaux `0,5× / 1× / 2×` existent déjà.

1. À **2×**, les plantages apparaissent : on les **compte**.
2. Le modèle de marge prédit un `p` à 2× : on **compare**.
3. S'ils concordent, le modèle est validé **sur cet empilement**, et on peut le croire à 1×
   où le comptage rend zéro. Sinon, on ne le croit pas — et c'est un résultat aussi.

> **On n'extrapole jamais sans avoir validé l'extrapolation dans le régime où la mesure est
> possible.**

##### Pourquoi c'est un MEILLEUR test du Piège 1 que le taux de plantage

La marge doit varier en `1/σ`. Si elle n'y varie pas, elle n'est pas gouvernée par le bruit et
on a trouvé un artefact. C'est un test **continu**, donc bien plus sensible qu'un taux de
plantage qui saute de 0 à 1/N — lequel, à N=150, ne voit rien en dessous de 0,7 %.

##### 👤 La sortie : couche critique, cause, marge — arrêté le 2026-08-10

La couche critique va dans le tableau de classement, **à côté de SEEL et du rendement**. Les
trois répondent à trois questions distinctes : *elle est bonne comment* · *elle va au bout* ·
**qu'est-ce qui va lâcher, et pourquoi**.

```
couche critique | cause                                | marge
L37             | ondulation trop faible pour etre vue |  0,6 A   PEUT ECHOUER
L12             | niveau d'arret hors d'atteinte       |  3,1 A   impossible
L23             | point tournant fabrique par le bruit |  1,4 A   PEUT ECHOUER
```

**Trois règles de présentation, et la deuxième n'est pas négociable :**

1. **La marge s'exprime en multiples de `A`.** C'est la seule unité **comparable entre les
   trois causes** — un niveau est en points de T, une ondulation aussi mais ailleurs, une
   fabrication est une excursion. Ramenées à `A`, elles se lisent sur la même échelle. C'est
   aussi la condition de la règle 2.
2. 🔴 **Au-delà de `2 A`, on écrit « impossible », jamais une probabilité.** Les deux autres
   règles relèvent de l'ergonomie ; **celle-ci relève de la vérité.** Le tirage étant borné,
   la marge dépasse la perturbation maximale et l'événement **ne peut pas** se produire.
   Écrire « 0,1 % » là serait une affirmation fausse — et fausse dans le sens qui fait
   renoncer à une bonne stratégie.
3. **Signaler la multiplicité.** Une couche seule à 0,6 A n'est pas le même profil que douze
   couches sous 1 A : `L37 (+11 autres sous 1 A)`.

⚠️ **La cause se nomme en mots physiques, jamais par sa sentinelle.** `CRASH_TP_MISCOUNT` ne
dit pas à un opérateur de bâti ce qu'il doit surveiller ; « ondulation trop faible pour être
vue » le dit.

##### Ce que ça demande

| Étage | Travail | Runs |
|---|---|---|
| 0 | ne plus écraser `crashed_cells` sur l'axe des couches | **aucun** |
| 1 | comparer marge et borne du tirage, par couche et par cause | aucun |
| 2 | **enregistrer la marge par (run, couche, cause)** dans `simulate_growth_kernel` | aucun — c'est le vrai travail de code |
| 3 | valider le modèle contre le niveau 2× | aucun |

**Aucun run supplémentaire n'est nécessaire.** Toute cette action se paie en code, pas en
temps de calcul — et elle répond à une question à laquelle *aucun* nombre de tirages ne
répondrait, puisqu'un taux nul reste nul quel qu'il soit.

#### A21 — La fonction objectif · *le chantier le plus rentable, et il est gelé*

📏 Les deux bandes du juge de paix font **exactement 141 points chacune sur 301**. Un RMSE
uniforme est donc *littéralement incapable* de distinguer une stratégie qui rate la bande
bloquée d'une qui rate la passante, alors que l'exigence diffère d'un facteur ~500.
👤 *« La cible spectrale restera non pondérée jusqu'à nouvel ordre. »*

🔴 **Ne la dégèle pas de toi-même.** Mais sache que tout ce qui précède optimise un score qui
ne sait pas distinguer un succès d'un échec sur la moitié du spectre.

#### A22 — La validation externe · *§26, le seul chemin restant*

Deux dépôts réels du dichroïque 48 couches, spectres mesurés. Le test est **ordinal** : STRAT
doit les classer dans le bon ordre. Rien de ce document n'est une validation physique tant que
cela n'existe pas.

---

**[`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.6 (face arrière) : ne la fais pas.** Elle vaut 0,002 en absolu. Documentée pour mémoire,
pas pour être exécutée.

---

---

# PARTIE I — AVANT DE TOUCHER À QUOI QUE CE SOIT
