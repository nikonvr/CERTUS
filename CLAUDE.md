# CERTUS — document de référence

**C'est le document de référence du projet.** Tout le savoir est ici, et il n'y a rien
d'autre à lire pour comprendre.

Le code calcule de la **physique réelle** servant à fabriquer de vrais filtres optiques. Une
erreur silencieuse ne plante pas : elle produit un **résultat faux qui a l'air juste**, et
quelqu'un fabrique une pièce avec.

## 🔒 La règle des deux documents — lis-la avant de créer quoi que ce soit

Il existe **exactement deux** fichiers d'instructions, et ils n'ont pas le même rôle :

| Fichier | Rôle | Public |
|---|---|---|
| **`CLAUDE.md`** (celui-ci) | **Le savoir.** Physique, mesures, décisions, pièges, nuances. La seule source de vérité. | Toi, et tout agent capable de raisonner |
| **`GEMINI_TODO.md`** | **Un ordre de mission.** Uniquement des commandes à lancer et des sorties à coller. **Aucun fait, aucune explication, aucune nuance.** | Un exécutant à faible capacité |

**Les trois règles qui empêchent ce dépôt de retomber dans ses quatre-vingts documents
contradictoires :**

1. **`GEMINI_TODO.md` ne contient AUCUN fait.** Il ne fait que dériver de celui-ci des
   commandes. S'il énonce un chiffre, c'est comme valeur attendue d'une sortie, jamais comme
   connaissance.
2. **En cas de désaccord, `CLAUDE.md` gagne, toujours.** `GEMINI_TODO.md` se régénère depuis
   ce document, il ne se corrige pas.
3. **On ne crée pas un troisième document.** Ni rapport de session, ni note, ni journal.
   Un exécutant écrit dans `reports/RAPPORT_GEMINI.md`, et c'est une **sortie**, pas une
   instruction.

⚠️ **Pourquoi ce découpage existe.** Un exécutant faible n'échoue pas sur la compréhension,
il échoue sur l'**inférence** : il comble ce qui n'est pas écrit littéralement. Or ce
document est fait de nuance — « ce chiffre surestime », « c'est une dérivation, pas une
mesure », « sauf si ». Cette nuance est ce qui lui donne sa valeur ici, et c'est exactement
ce qui fait dériver un modèle faible. **Alourdir CLAUDE.md de garde-fous le dégraderait pour
tout le monde sans protéger personne.** Les garde-fous vont dans l'ordre de mission ; ici, on
garde la vérité.

`AGENTS.md` et `GEMINI.md` sont de simples renvois vers ce fichier. Ils ne contiennent rien.

---

## ⚡ DÉMARRAGE — fais ces 4 choses, dans cet ordre, avant tout le reste

**Une seule commande fait les trois premiers points, et elle est à jour :**

```bat
.venv\Scripts\python.exe scripts\preflight.py
```

Elle doit finir par `PREFLIGHT=GO`. Ce qui suit explique **ce qu'elle vérifie et pourquoi**,
à lire une fois.

**1. Vérifie que tu es dans le bon dossier.**

```bat
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

Le chemin affiché **doit être dans l'arbre où tu édites**.
Si ce n'est pas le cas → **ARRÊTE-TOI. Signale-le. Ne modifie rien.**

🔴 **Il n'y a PAS de racine attendue en dur, et c'est délibéré.** Ce document a longtemps
exigé `C:\dev\gemini` — **un dossier qui n'existe plus**, et la constante `EXPECTED_ROOT`
qui le portait dans `preflight.py` n'était lue par aucun contrôle. Une consigne qui
protégeait de l'erreur n°1 envoyait donc vers un dossier fantôme, en silence. Le projet vit
dans des snapshots datés copiés les uns depuis les autres (`0108`, `0807`, `1408`, …) : la
seule question qui survive à une copie est *« est-ce que `import certus` résout DANS l'arbre
courant ? »*

**2. Sais-tu si committer PUBLIE ?**

```bat
dir .git\hooks\post-commit*
git remote get-url origin
```

👤 a demandé le **2026-08-14** que le push soit **armé**. Donc `post-commit` sans suffixe est
l'état **voulu** : chaque commit pousse vers `github.com/nikonvr/CERTUS`, un dépôt **public**.
`--no-verify` ne l'arrête pas — il ne saute que `pre-commit` et `commit-msg`.

🔴 **Conséquence, et elle est permanente : commiter, c'est publier.** Rien qui porte une
donnée personnelle, un secret, ou l'œuvre d'un tiers ne doit entrer dans l'index. Le
2026-08-14 le dépôt portait encore un nom civil dans six fichiers Excel, un nom de session
dans 114 lignes de journaux, et le texte intégral d'une thèse tierce. Si 👤 demande un commit
**sans** pousser, désactive le hook **avant**, pas après.

**3. Vérifie que tout est vert avant de toucher à quoi que ce soit.**

```bat
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Attendu : `All checks passed!` puis `2450 passed, 5 skipped` (📏 2026-08-14, 7 min).
Si un test est rouge **avant** que tu n'aies rien touché → **ARRÊTE-TOI et signale.**
Ce n'est pas à toi de le réparer.

**4. Lis §12 et choisis UNE action. Une seule.**

---

## ⚡ LES 7 ERREURS QUI ANNULENT TON TRAVAIL

Chacune a déjà coûté au moins une session complète sur ce projet.

| # | L'erreur | La conséquence |
|---|---|---|
| 1 | Modifier un dossier et mesurer l'autre | Aucun message d'erreur. Tous tes résultats sont faux. |
| 2 | Écrire une conclusion avant d'avoir la mesure | Détectée à la relecture, ton travail est annulé. |
| 3 | Changer deux choses à la fois | Le résultat bouge, personne ne sait laquelle en est cause. |
| 4 | Croire un chiffre de bruit qui ne varie pas avec le bruit | C'est un artefact. Divise le bruit par 100 et remesure. |
| 5 | Lancer une mesure pendant qu'autre chose tourne | Le banc rend `RESULT=None`, ce qui ressemble à un résultat. |
| 6 | Vérifier une non-régression « aux tests près » | Les tests ne prouvent pas l'identité numérique. Il faut le bit. |
| 7 | Modifier `example/example_strat/JSON-strat-example.json` | Toutes les mesures suivantes deviennent nulles. |

**Si tu ne dois retenir qu'une phrase :**

> **Soit tu colles la sortie de la commande, soit tu écris « je n'ai pas mesuré ».**
> Il n'y a pas de troisième option. Pas de « cela devrait améliorer », pas de « le taux est
> probablement de ».

---

## ⚡ CARTE DU DOCUMENT — où aller selon ce que tu fais

| Tu veux… | Va en |
|---|---|
| **Commencer une action** | **la FEUILLE DE ROUTE**, en tête de ce document : ce qui est acquis, puis la suite immédiate |
| Savoir ce qui est interdit | §1 — les onze interdits |
| Savoir dans quoi tu vas tomber | §2 — les sept pièges |
| Savoir comment travailler | §3 — la boucle et la règle d'or |
| Toucher à du calcul optique | §6 — conventions physiques et oracle TMM |
| Comprendre la machine de dépôt | §9 — les spécifications du physicien |
| **Savoir ce qu'on suppose de la machine** | **§9bis — le modèle FIGÉ de la chaîne de lecture. Ne pas le rouvrir.** |
| **Le programme COURANT** | 🔴 **§25 — multiple testglass methodology.** C'est là que se fait le travail depuis le 2026-08-14 |
| Comparer un résultat | **§10 — quatre repères valides, tous fente 2 nm.** Ce qui les périme y est dit |
| Comprendre un mot du projet | §7 — vocabulaire |
| **Savoir ce qui est encore cassé** | **§17 — défauts ouverts et constats qui gouvernent. À lire avant toute action.** |
| ⚡ **Gagner du temps d'exécution** | **§18ter — la forme fermée de `T(d)`, ×1,20 mesuré. Trois pistes FERMÉES, et le vrai levier est ailleurs.** |
| 🔴 **Savoir ce qui est RÉELLEMENT implanté** | **§18bis — établi contre le CODE, jamais contre ce document. La moyenne de lecture reste causale, l'arrêt n'est pas quantifié.** |
| Comprendre le mode Rate | **§14, bloc « Le mode Rate (Quartz / Chrono) »** — noyau écrit **et génération de variantes active par défaut** depuis le 2026-08-12. ⚠️ Trois critères distincts s'y mélangent, démêlés dans l'encadré *« le rate est souvent réservé aux couches fines »* |
| **Les quatre composants d'essai** | §7 pour le dichroïque 48c, **§21 pour le passe-bande 3 cavités 35c**, **§25.1 pour le 99c 5 cavités**, **§25.4 pour le 75c ALÉATOIRE** — ce dernier n'a aucune structure, c'est lui qui teste la généralité d'une règle |
| **La grille des λ, 1 nm ou 2 nm** | §22 — enquête et critère de décision |
| Vérifier le travail d'un autre agent | §20 — protocole de re-vérification |
| **Choisir la profondeur Monte-Carlo** | **§23 — N = 300 et n_screen = 25, avec le critère qui n'est PAS celui qu'on croit** |
| **Savoir ce qui est MESURÉ mais NON CONSIGNÉ** | **§23bis — le correctif 2 : la campagne a tourné, les 6 runs sont FAILED, la traçabilité est à réparer AVANT de relancer** |
| **L'invariant recherche / notation** | **§23ter — `N` ne doit décider d'aucune candidate** |
| 💡 **Quand §25 sera fini** | **§24 — A25, A26, A27, prêtes à exécuter et en réserve. Plus les cinq choses à ne PAS faire** |

🔑 **La page qui compte, et 👤 l'a dit : `pages/CERTUS_STRAT.html`.**

> 👤 *« c'est strat.html le fichier ultra important. C'est lui qui convaincra les acheteurs
> potentiels du code ! »* (2026-08-14)

C'est une **vitrine commerciale et technique**, publiée sur un dépôt public. Elle ne contient
aucune instruction, et elle a un régime propre :

| | |
|---|---|
| **Une affirmation fausse y coûte plus qu'un manque** | Un évaluateur qui prend un chiffre en défaut cesse de croire le reste. Tout nombre doit être sourçable dans le code ou dans un artefact de `reports/`. |
| **La nuance juste convainc, le superlatif non** | « le meilleur partitionnement **mesuré** sur deux empilements » se défend ; « l'optimum universel » se réfute en une question. |
| **Elle doit montrer sa LIMITE** | §10.15 porte le 99 couches, dont **aucune stratégie ne survit** — plantage 100 %, et le 0,86 nm qui traîne est un **score de repli**. Un expert le trouverait de toute façon. |
| **Et ce qui lève la limite** | **§10.16 — multiple testglass**, ajoutée le 2026-08-15 : le même 99 couches devient fabricable, 0,760 nm à 0 % de plantage. Elle dit aussi les trois attentes que la mesure a **démenties**, et ce qui n'est **pas** revendiqué (borne supérieure, une seule graine). |
| **Vérifie la STRUCTURE après toute édition** | Le 2026-08-14 un `</ul>` supprimé faisait rendre 400 lignes à l'intérieur d'une liste, et avait emporté une puce entière. Passe `html.parser`, ne te fie pas à l'œil. |

Les autres pages de `pages/` (14 fichiers : DESIGN, INDEX, FIELD, HUB, RE, METAL, métrologie…)
et les rapports de `reports/*.html` existent aussi. ⚠️ Ceux de `reports/` **ne chargent aucun
moteur mathématique** : tout `$...$` y sort en texte brut.

---

## ⚡ TU NE DÉCIDES RIEN — toutes les valeurs sont déjà fixées

**Aucun choix ne t'est demandé.** Toutes les valeurs physiques, tous les seuils, tous les
paramètres ont été arrêtés avec le physicien le 2026-08-08 et sont dans le tableau ci-dessous.

> **Si tu te trouves en train de choisir une valeur, tu t'es trompé : la valeur existe
> déjà. Relis §9bis. Si elle n'y est vraiment pas, ARRÊTE-TOI et demande.**

### Toutes les constantes, en un seul endroit

| Paramètre | Valeur | Où c'est expliqué |
|---|---|---|
| Cadence d'échantillonnage machine | **4 Hz**, un point tous les **0,125 nm** | §9bis-1 |
| Amplitude du bruit de lecture | **±0,05 point**, soit `A = 5e-4` en unités T | §9bis-2 |
| `reading_smoothing_window` (`k`) | **8** lectures (2 s) — défaut 1 = inactif | §9bis-3 |
| `tp_hysteresis_factor` | **1,00** — **mesuré**, pas dérivé, à `k = 8` et `N = 800`. 🔴 **Ni 0,354 ni 1,66.** Le `1/√k` = 0,354 est **réfuté** : il laisse **100 %** de points tournants fabriqués. ⚠️ La valeur dépend de `N` autant que de `k` — si l'un bouge, **remesure** | §9bis-4, A1 |
| Retard de déclenchement | **aucun** — ne rien ajouter | §9bis-5 |
| `phase_a_level_margin_factor` | **1,66** actuel, **3,33** à évaluer | §9bis-6 |
| Quantification de l'arrêt | `U(0 ; 0,125 nm)` | §9bis-7 |
| `index_corridor` | **0,005**, unités d'indice **absolues**, demi-largeur — 👤 **ACTIF PAR DÉFAUT** | §12.3 |
| `photometric_curvature_amp` | **0,00375** ⇒ à `T = 0,5` la vraie valeur est dans `[0,4975 ; 0,5025]` à 2 σ. 👤 **ACTIF PAR DÉFAUT** | §12.1bis |
| `allow_rate` | **vrai** — 👤 *« c'est le cas général »* | §14 |
| `slit_bias_enabled` | **vrai**, fente nominale **2 nm** — 👤 *« réaliste, pas optimiste »* | §12.7 |
| `reading_smoothing_window` | **1 = INACTIF**, et il le reste — 👤 *« on ne sait pas trop les algos de smooth appliqués par Bühler »*. §9bis interdit d'ajouter une structure non mesurée | §9bis-3 |
| `affine_scale_amp` | **0,05** ⇒ `a ∈ [0,95 ; 1,05]` | §12.1 |
| `affine_offset_amp` | **0,02** ⇒ `b ∈ [−0,02 ; +0,02]` | §12.1 |
| Plafond du banc | `CERTUS_BENCH_TIMEOUT_S=5400` | §10 |
| Graine de référence | **42**, `scan_wl_step` **1.0** | §10 |
| `robustness_num_runs` | **300** — 👤 posé le 2026-08-13. ⚠️ **Ce n'est PAS un réglage de précision** : la profondeur commande la sensibilité du filtre de plantage, donc **quelles stratégies existent** | §23 |
| `n_screen_runs` | **25**, et 👤 a délégué le choix le 2026-08-13. 🔴 **NE LE DESCENDS PAS À 10** : `1/10 = 10 % ≥ 5 %`, donc **un seul plantage sur dix tue la stratégie** — et depuis le correctif 1 elle est aussi perdue comme **parent**. §17-27 avait mesuré « 10 ne perd rien » **avant** que le criblage ne choisisse les parents : la mesure ne couvre plus le rôle | §23ter |
| `sigma_rate` (mode Rate) | 🔑 **aucune valeur à poser** — grandeur DÉRIVÉE du simulateur | §14, dérivation |
| Résolution du monochromateur | **2 nm** nominal · choix dans {5 ; 2 ; 1 ; 0,5} · facteurs de bruit **÷1,5 · ×1 · ×2 · ×5** | §12.7 |

**Tout nouveau paramètre vaut sa valeur INACTIVE par défaut** (1 pour la fenêtre, 0 pour les
amplitudes et le corridor). Le chemin inactif doit rendre les mêmes bits qu'avant. Toujours.

---

## ⚡ FEUILLE DE ROUTE — ce qui est acquis, puis ce qui vient

**Établie le 2026-08-09**, après l'audit de §17. Elle **remplace** l'ancien tableau T0–T7, qui
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

Après **chaque** action : `pytest tests/oracle/ tests/unit/ -q --no-cov` → `2310 passed,
5 skipped` · `ruff check .` → `All checks passed!` · commit · et tu écris ce que tu as mesuré,
sortie collée. **Une action, un commit.**

### 🟢 Ce qui est déjà outillé — ne le réécris pas

| Outil | Ce qu'il fait | Remplace |
|---|---|---|
| `scripts\preflight.py` | Les 7 vérifications d'environnement en une commande, verdict `PREFLIGHT=GO` / `STOP` | §0 en entier |
| `scripts\probe_tp_fabrication.py` | **A1 et A2, faites.** Fabrication d'extrema et survie des vrais, avec le vrai détecteur et le vrai générateur de bruit | A1, A2 |
| `probe_anchor_noise_pipeline.py` | Écrit sa configuration effective dans `r["config"]`, dans le nom du fichier, **et l'annonce dans les 2 s** ; refuse une valeur illisible au lieu de retomber sur le défaut | le trou de traçabilité de §17-7, et §17-11 |
| `scripts\run_campaign.py` | **Une commande = toute une campagne.** Environnement construit en dictionnaire, aucun shell, chaque run vérifié contre la configuration demandée, reprenable | une nuit de commandes tapées à la main |

### ✅ CE QUI EST ACQUIS — ne le refais pas, et ne le redemande pas

Seuls les **faits qui gouvernent encore** figurent ici ; le déroulé est dans `git log`.

| | Ce qui en reste |
|---|---|
| **A1, A2** | Le seuil anti-fabrication vaut **1,00 A** à `k = 8`, `N = 800` — mesuré, pas dérivé. `0,354` est réfuté (§9bis). Les vrais extrema survivent au lissage. |
| **A6** | Le banc **est** déterministe à état compilé constant. C'est la **recompilation** qui décale les bits, de 2,819e-11, reproductiblement (§3). |
| **A8** | 🔴 **INACHEVÉE, et l'inverse de ce qui était écrit ici.** `machine_sampling_dd` existe, il est exposé dans l'interface (*« Machine grid (nm, 0=off) »*) et livré dans **9 configurations d'exemple** — mais **AUCUN des 27 sites d'appel du noyau ne le lui passe** (vérifié le 2026-08-15). Le noyau reçoit donc **toujours** son défaut `0.0`. Le réglage est **inatteignable** : ce n'est pas « 0 par défaut », c'est 0 quoi qu'on fasse. La grille fine ne s'active que par `smoothing_window > 1` — **la soudure de §17-2 n'est donc PAS défaite**, elle est seulement masquée par un bouton qui ne fait rien. |
| **A10, A14** | Le corridor atteint la notation. Courbe : `×1,23 · ×2,03 · ×2,41 · ×4,66`, exposant **0,545** (§17-29). |
| **A12** | POEM protège d'un facteur **×41,2** sous distorsion affine (§17-29). ⚠️ **Cite la protection, jamais le dommage résiduel** : +0,9 % sur une graine, +98 % sur une autre. |
| **A15** | La marge Phase A change ce qui est **offert**, jamais ce qui est **retenu** (§17-12). |
| **A17** | Le facteur de bruit par fente est une **table de 4 entrées** ; une fente absente **lève**. |
| **A20** | L'entonnoir Phase A → Phase B **ne fuit pas**, sur ce cas (§17-27). |
| **A23** | Étages 0, 2 et 3 faits. La marge prédit le plantage d'un facteur **22**, validée non circulairement (§17-41). |
| **Tri de §14** | `rank_key_seel_yield_margin` écrit et testé. Tourne **dans la sonde**, à côté de l'ordre du pipeline — SEEL vit à l'étape 0 de l'interface, l'en sortir reste à faire. |
| **Fente** | Biais = **profil** variant avec l'épaisseur, boxcar intégrée exactement, Phase A comprise (§18bis). |
| **Stratégies par Blocs** | **6 blocs est le meilleur compte MESURÉ sur 35c et 48c** : SEEL **0,583 → 0,482 nm** sur 35c et **0,269 → 0,173 nm** sur 48c, plantage 0,0 %, et **5 mouvements de monochromateur au lieu de 34 et 47** (§17-43). ⚠️ **Pas « optimum global »** : 8 à 34 blocs n'ont jamais été mesurés sur le 35c, et 6 n'y gagne qu'en DEEP — FAST et PREMIUM rendent 5. ⚠️ Les **+31,5 % / +58,7 %** qui circulent sont des gains de **RMSE** ; en SEEL, la seule unité qui compte, ils valent **+17,2 % et +35,7 %**. |
| **Modes FAST/PREMIUM/DEEP** | 3 profils en UI et solveur, $N = 50 / 150 / 300$ et `dp_top_k` = 20 / 40 / 100 (§17-46). ⚠️ Un `crash_rate` lu sous FAST n'est **pas publiable** : le criblage y est à 10 tirages, donc quantifié à 10 %, et un « 0,0 % » veut dire « sous 10 % ». Cite le SEEL sous FAST, le plantage sous PREMIUM ou DEEP. |
| **Phase A Block-Aware** | Bonus $C \leftarrow C_{\text{local}}/\sqrt{\text{streak}}$, seuil `streak >= 2`, dans `certus_strat_objectives.py:415` (§17-45). 🔴 **Il ÉCRASE le coût local en place**, sans copie — `cost_raw` contient déjà le coût bonifié. 🔴 **Et il court AVANT la normalisation**, dont la moyenne porte sur les coûts déjà bonifiés : les candidates **non** bonifiées voient donc leur coût normalisé **monter**. Ce n'est pas un ré-ordonnancement neutre. 🔑 La normalisation élevant au carré (`certus/core/certus_strat_objectives.py:456`), **ce que la DP voit est $C/\text{streak}$, pas $C/\sqrt{\text{streak}}$** — un bloc de 9 couches est favorisé d'un facteur 9, pas 3. |

### ⏳ EN COURS AU 2026-08-14 — lis ceci avant de lancer quoi que ce soit

| | |
|---|---|
| 🟢 **Correctif 1 VALIDÉ** | Deux runs, N = 50 et N = 500 : survivantes et héritage **identiques terme à terme** sur les 10 blocs, là où les deux derniers tombaient de `12, 9` à `2, 3`. §23ter |
| 🔴 **Correctif 2 : la campagne A TOURNÉ, et elle n'est PAS exploitable** | 6 runs sur 6 le 2026-08-14, **55 min 16 s** au total (`reports/probe_runs.tsv`, colonne `run_s` — et non ~3 h 30 comme annoncé). Mais `run_campaign.py` marque les **6 runs FAILED**, et il a raison. Voir ci-dessous. §23bis |
| ⚠️ **`N = 300` reste conditionné au correctif 2** | Le chiffre vient de la sensibilité du filtre actuel, et le correctif 2 n'est toujours pas mesuré **exploitablement**. Ne le remesure pas avant d'avoir réparé la traçabilité — §23 |

#### 🔴 Pourquoi les 6 runs de la porte sont FAILED, et ce qu'il faut réparer d'abord

**Cause racine, vérifiée dans le code :** `crash_gate_confidence` est dans `_OVERRIDES`
(`scripts/probe_anchor_noise_pipeline.py`) mais **absente de `TRACED_KEYS`**. La clé est donc
**appliquée** au run et **jamais consignée** dans `r["config"]`. `run_campaign.py` compare le
demandé à l'appliqué, ne trouve pas la clé, et déclare l'écart :
`crash_gate_confidence: asked 0.95, applied '<absent>'` — sur les 6 runs.

C'est le **point 7 de §17 qui se rouvre** : un run qui ne consigne pas sa configuration n'est
comparable à rien. Ajouter la clé aux **deux** listes, et au nom du fichier de sortie, avant
tout autre travail sur la porte.

**Et deux résultats de cette campagne demandent une explication avant d'être crus :**

| | |
|---|---|
| 🔴 **G1.off et G1.on rendent un score BIT-IDENTIQUE** | `0.006138704636203437` des deux côtés — porte OFF et porte armée à 95 % — avec des **gagnantes différentes** (900000127 contre 900000116). Une porte qui ne change pas le score au dernier bit peut être **inerte**. À trancher par un compte de rejets, pas par lecture du code (§20, contrôle 4). |
| 🔴 **Le témoin C1 n'a pas reproduit sa référence** | Attendu `0.006151532415266679` à ~1e-11 près, obtenu **`0.00611049163380679`** — écart 4,1e-5, soit **six ordres de grandeur** au-delà de l'enveloppe annoncée. Un témoin qui ne reproduit pas invalide la campagne qu'il devait garantir. |
| ⚠️ **Une propriété testée est peut-être violée** | `tests/unit/test_strat_crash_gate_confidence.py:125` pose que la porte armée **ne peut qu'AJOUTER** des stratégies, jamais en retirer. Vérifie `len(ranking)` entre les deux bras avant de conclure : si le bras armé en retire, c'est un **défaut**, et le test l'énonce déjà. |

⚠️ **Le « 1046 cas » de §24 est faux.** L'énumération réelle de la porte fait **127 cas** —
`for n_runs in (10, 25, 50, 150, 300, 500)` à pas sauté, `test_strat_crash_gate_confidence.py:127`.
Le nombre 1046 n'existe nulle part dans le dépôt.

### 🔴 LA SUITE IMMÉDIATE

**Si tu reprends ce dépôt et que tu ne sais pas par où commencer : §24.** Il porte
**A25, A26, A27**, écrites pour être exécutées — fichier, fonction, ligne d'ancrage, test
qui doit échouer sur le code d'avant, et pièges. **A25 d'abord** : c'est la seule action
du document qui puisse rendre STRAT *vrai* plutôt que simplement *cohérent*.

Ce qui suit reste ouvert et garde sa valeur, mais aucune de ces entrées n'est aussi prête
à être prise en main.


0. 🔑 **RÉTABLIR LE REPÈRE.** Le biais de fente est actif par défaut depuis le
   2026-08-11 : **tout chiffre mesuré avant cette date répond à une autre question**,
   celle d'une machine à fentes infiniment fines. §10 est périmé, et avec lui la courbe
   de corridor, le ×41,2 de POEM et la falaise. Un run neutre, et on repart.
1. **Trancher la grille** — §22, campagne de 8 runs, critère posé à l'avance.
2. **Sortir SEEL de l'interface** (§14, action 1), sans quoi le tri de §14 ne peut pas
   remplacer celui du pipeline.
3. **Comprendre l'effondrement de `n_ranked` avec le corridor** — 228 → 165 → 78
   (§17-30). Contrôle 4 de §20 : **compter les rejets**.
4. **§17-14 reste ouvert** — `dp_yield_weight` n'atteint pas le calcul (§17-33).

### PALIER 0 — Quatre sondes qui ne coûtent rien et qui décident du reste

Aucune ne demande le banc, ni le repère, ni une machine libre. **Minutes chacune.** Elles
peuvent toutes être faites aujourd'hui.

#### A4 — Compter ce que les filtres existants rejettent · *§20-contrôle 4*

> **Compte les rejets, ne lis pas le code.** Un filtre inerte ne produit aucune erreur — il
> produit un résultat plausible. C'est ainsi qu'une règle de proximité recevant une matrice
> de zéros n'a rien interdit sur 51 candidates × 48 couches, en silence.

| # | Filtre | Où | Attendu |
|---|---|---|---|
| 1 | `phase_a_level_margin_factor` | log `[MARGIN]`, `certus_strat_service.py:991` | **compter** les candidates rejetées, par couche |
| 2 | 🔴 **D'abord corriger le facteur √3** — la fente est rectangulaire, la formule est trop stricte de 1,73× (§12.7) | `_calculate_strategy_spectral_resolution:281` | `res_limit = test_bw * np.sqrt(3.0 * T_tolerance / curvature)` |
| 3 | `min_resolution`, **sur la formule corrigée** | idem | **combien de stratégies** seraient écartées à chacune des 4 résolutions |
| 4 | `tp_hysteresis` | sentinelles `CRASH_TP_MISCOUNT` vs `CRASH_LEVEL_UNREACHABLE` | les **séparer** dans le rapport (`int(val // 1e6)`) |
| 5 | Un filtre qui rejette **0** | — | **c'est un défaut**, pas un succès. Signale-le |

⚠️ L'étape 2 est un changement de formule, donc un commit à part, avec son test. Elle
**élargit** les fentes admissibles : compter les rejets avant la correction donnerait un
chiffre faux dans le sens sévère.

---

### PALIER 1 — Rendre le banc digne de confiance

#### A5 — Le harnais d'empreinte `float.hex()` · *le SEUL instrument de la règle d'or*

La règle d'or de §3 exige une non-régression **au bit**, et **aucun outil ne permet de la
vérifier**. Le banc ne peut pas servir : il a ~3e-11 de gigue irréductible (§3, §10).
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
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
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

🔑 **Ne confonds pas A7 avec les repères de §10 — ce sont deux objets différents.**

| | A7 | §10 |
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

⚠️ **Ne cherche pas l'identité au bit** — elle est impossible ici, voir §3. Un écart nul entre
deux runs serait une coïncidence, pas un critère.

---

### PALIER 2 — Rendre mesurable ce qui est déjà écrit

#### A8 — Dé-souder la grille du lissage · *ex-T3, §17-2*

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

#### A9 — Moyenne centrée au lieu de causale · *§17-3*

La moyenne actuelle porte sur `[i−k+1 … i]` : elle décale un extremum de `(k−1)/2`
échantillons, soit **0,44 nm à k = 8**. §9bis-5 pose « aucun retard » en postulat figé.

- **Où** : même fonction, boucle de lissage, ligne ~747.
- **Quoi** : fenêtre `[i−⌊k/2⌋ … i+⌊k/2⌋]`, bords traités par fenêtre rétrécie symétrique.

| # | Étape | Attendu |
|---|---|---|
| 1 | Signal propre **sinusoïdal** d'extremum connu, `k = 8` | position de l'extremum détecté **inchangée** à moins d'un échantillon |
| 2 | Même chose avec la moyenne causale | décalage de **≈ 3,5 échantillons** — c'est ce qu'on corrige |
| 3 | `k = 1` | empreinte identique au bit |
| 4 | Rejouer A1 avec la centrée | le chiffre de fabrication ne doit pas se dégrader |

#### A11 — Les tests qui manquent · *§17-5*

`f7a3d71`, `e0df0e1`, `162a0ff` n'ont ajouté **aucun** test, et aucun test ne mentionne les
nouveaux paramètres. Le contrôle 2 de §20 est donc inapplicable.

| # | Test à écrire | Doit échouer sur |
|---|---|---|
| 1 | `poem_enabled = False` force bien le repli absolu | `f7a3d71^` |
| 2 | `affine_scale ≠ 1` déplace l'arrêt du repli, **pas** celui de POEM | `76f7a8f^` |
| 3 | `reading_smoothing_window = 8` réduit la variance du signal de `√8` | `e0df0e1^` |
| 4 | `index_corridor > 0` fait diverger réel et nominal | `162a0ff^` |
| 5 | `index_corridor > 0` change le **score** | **HEAD** — c'est le test qui prouve A10 |
| 6 | Chaque nouveau paramètre à sa valeur neutre est **bit-identique** | — |

🔴 **Copie chaque test dans le worktree baseline et vérifie qu'il ÉCHOUE.** Un test qui passe
avant le correctif ne prouve rien. C'est le contrôle le plus rentable de §20.

---

### PALIER 3 — Les mesures qui devaient déjà exister

Toutes au banc, **une machine par run**, `CERTUS_BENCH_TIMEOUT_S=5400`, et le bloc `CONFIG=`
vérifié avant de lire le moindre chiffre.

#### A13 — La paire grille + lissage · *ex-T3 et T4*

**Ne conclus rien entre les deux.** Le taux de plantage n'a de sens qu'une fois les deux en
place.

🔴 **Le seuil à utiliser est `1,00`, pas `0,354`.** A1 a mesuré que 0,354 laisse **100 %** de
fabrication à `k = 8`, `N = 800` — voir §9bis. `1,00` est la borne **mesurée**, pas dérivée.

| # | Run | Attendu |
|---|---|---|
| 1 | `sampling_dd = 0,125`, `k = 1`, seuil 1,66 | le plantage **monte beaucoup**. **C'est attendu, pas un bug** |
| 2 | `sampling_dd = 0,125`, `k = 8`, seuil **1,00** | il doit **redescendre** |
| 3 | Si (2) ne redescend pas | **dis-le. Ne remonte pas le seuil** |
| 4 | Balayer `k ∈ {1, 4, 8, 16}` | ⚠️ **le seuil ne suit PAS `1/√k`** — cette loi est réfutée. **Remesure la borne avec `probe_tp_fabrication.py` pour chaque `k`**, puis utilise la valeur mesurée. **Piège 1** : si le plantage ne bouge pas avec `k`, le lissage n'atteint pas le calcul |

---

### PALIER 4 — Le neuf

#### A16 — Quantification de l'arrêt · *ex-T7, §12.5*

Quasi gratuit une fois A8 faite : s'arrêter au **premier point de grille au-delà du seuil**
au lieu d'interpoler, et `U(0 ; 0,125 nm)` apparaît d'elle-même, sans paramètre.
**Vérification** : Piège 1 — si doubler `Δd_sample` ne change rien, la mesure est un artefact.

#### A18 — Résolution : variable de stratégie en Phase B · *§12.7*

Conditionnée par A17-4. Une stratégie devient *(blocs, λ par bloc, résolution)*. **Phase B**,
pas Phase A, pas la DP — voir §12.7 pour le raisonnement.

#### A19 — Mode Rate · *§14*

`sigma_rate` est **dérivé**, pas posé — voir la dérivation du §14. Reste à obtenir les
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

§12.2 s'en sert déjà — *« le tirage étant borné à ±A, l'écart maximal du bruit seul vaut 2A »*.
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

#### A22 — La validation externe · *§15, le seul chemin restant*

Deux dépôts réels du dichroïque 48 couches, spectres mesurés. Le test est **ordinal** : STRAT
doit les classer dans le bon ordre. Rien de ce document n'est une validation physique tant que
cela n'existe pas.

---

**§12.6 (face arrière) : ne la fais pas.** Elle vaut 0,002 en absolu. Documentée pour mémoire,
pas pour être exécutée.

---

---

# PARTIE I — AVANT DE TOUCHER À QUOI QUE CE SOIT

## 0. Vérifier l'environnement — une minute, non négociable

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
dir .git\hooks\post-commit*
```

- Le chemin affiché **doit** commencer par `C:\dev\gemini`. **Plusieurs copies de ce dépôt
  coexistent sur la machine.** Si le chemin pointe ailleurs, tu modifies un dossier et tu en
  mesures un autre : tout ce que tu constateras sera faux, **sans le moindre message
  d'erreur**. C'est le piège n° 1 du projet et il est invisible. **Arrête-toi.**
- Le hook doit s'afficher `post-commit.DESACTIVE`. Sous ce nom il est inerte : committer ici
  **ne publie rien**. S'il apparaît sous le nom `post-commit` tout court, **ne committe
  pas** — il pousserait vers le dépôt **public** `nikonvr/CERTUS`, et `--no-verify` ne
  l'en empêche pas. **Ne le réactive jamais.**

### Commandes de référence

Toutes depuis `C:\dev\gemini`, toujours avec `.venv\Scripts\python.exe` — jamais `python`
nu, qui prendrait l'interpréteur système sans les dépendances.

| But | Commande | Durée |
|---|---|---|
| Tests du noyau | `.venv\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov` | ~4 min |
| Suite complète | `.venv\Scripts\python.exe -m pytest tests/ -q --no-cov` | ~1 h 45 |
| Lint | `.venv\Scripts\python.exe -m ruff check .` → `All checks passed!` | ~10 s |
| Run STRAT complet | `.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42` | ~25 min |
| Idem, seuil injecté | `... probe_anchor_noise_pipeline.py full 1.0 42 0 2.1` | ~25 min |
| Sonde noyau rapide | `.venv\Scripts\python.exe scripts\probe_anchor_noise.py` | ~1 min |
| Banc sur exemples réels | `.venv\Scripts\python.exe scripts\bench_examples.py <module> --auto-yes` | variable |

⚠️ **N'utilise pas `tests/headless/` pour mesurer** : `test_design.py` et `test_strat.py`
remplacent le calcul par un mock.

## 1. Les onze interdits absolus

Aucun n'admet d'exception. Si tu crois devoir en violer un, **arrête-toi et demande.**

1. **Jamais `ruff check --fix`.** 6 750 erreurs « auto-corrigeables », dont beaucoup sont des
   **ré-exports volontaires** : un import qui a l'air inutilisé rend en réalité un symbole
   disponible ailleurs. Corrige à la main, un fichier à la fois.
2. **Jamais agrandir `extend-ignore`** dans `pyproject.toml`. La liste masque déjà 68 règles
   et ne doit que rétrécir. `tests/oracle/test_lint_debt_ratchet.py` le surveille.
3. **Jamais supprimer `reports/`.** Résultats scientifiques de l'utilisateur : **226 fichiers**
   au 2026-08-09, classeurs Excel et rapports de mesures d'indice réelles.
   ⚠️ **Correction du 2026-08-09 : `reports/` n'est PAS gitignoré.** Seuls quatre
   sous-motifs le sont (`reports/exports/`, `release_dossier_*.zip`, `Report_*`,
   `STRAT_observability_*`). Mesuré : **33 fichiers suivis par git sur 226**. Les
   **193 autres ne sont donc protégés par rien** et sont **irrécupérables**.
4. **Ne modifie `example/example_strat/JSON-strat-example.json` que pour DURCIR.**
   Il s'est écarté des valeurs correctes **quatre fois**, toujours dans le sens
   **permissif**, et chaque fois cela a coûté une session de diagnostic. C'est le sens
   qui est interdit, pas l'écriture.
   ✅ **Amendé le 2026-08-12 sur instruction 👤** : *« tous les paramètres doivent être
   dans les JSON, celui du 48 couches et celui du 35 couches — les paramètres
   d'activation des différentes sources d'erreur, ainsi que le mode rate »*. Les deux
   fichiers portent donc désormais **explicitement** les onze réglages du modèle, au
   lieu de dépendre de défauts codés. Un fichier de configuration doit décrire la
   machine sur laquelle il tourne, sinon le run n'est comparable à rien (§17-7).
   ⚠️ Pour essayer autre chose, `scripts\probe_anchor_noise_pipeline.py` injecte les
   paramètres **après coup** — c'est toujours la voie à préférer.

5. **Jamais « corriger » `except A, B:`.** C'est la syntaxe PEP 758, valide depuis
   Python 3.14, utilisée volontairement dans 14 modules. Ajouter des parenthèses change le
   sens du code.
6. **Jamais inverser la convention `n̂ = n − ik`** (k ≥ 0). Avec la convention inverse les
   calculs donnent `R + T > 1` : de l'énergie créée à partir de rien.
7. **Jamais réimplémenter une formule TMM.** Source unique de vérité pour extraire R et T :
   `certus/physics/certus_opt_tmm.py::compute_RT_from_matrix`. Deux bugs de signe ont déjà
   été trouvés dans des réimplémentations, valant **46 et 82 points** de réflectance.
8. **Jamais découper `certus/core/_certus_physics_impl.py`.** Le fichier le dit lui-même :
   `DO NOT SPLIT`. Les noyaux compilés dépendent de la visibilité mutuelle dans un fichier.
9. **Jamais affirmer un résultat non mesuré.** Pas « cela devrait améliorer », pas « le taux
   est probablement de ». Soit tu colles la sortie, soit tu écris « je n'ai pas mesuré ».
10. **Jamais créer de rapport de session à la racine.** 103 fichiers y avaient été accumulés
    puis supprimés : des journaux contradictoires.
11. **Jamais réintroduire de français dans `certus/`.** L'anglais est strictement
    obligatoire pour tout commentaire, docstring ou message de log.
    ⚠️ **Trois catégories restent délibérément en français, et ce n'est pas une
    violation — ne les « corrige » pas** : les mots français utilisés comme
    **données** (`certus_re_helpers.py` — motifs de reconnaissance d'en-têtes
    français), les **clés JSON persistées** (`seuil1`/`seuil2` dans
    `certus_field_state_mixin.py`, qu'on ne peut pas renommer sans casser les
    configurations enregistrées), et les **libellés de widgets vus par
    l'utilisateur** (info-bulles, boutons, phases de progression). L'interdit porte
    sur commentaire / docstring / log — **pas sur la langue de l'interface**, qui
    est une question à poser au propriétaire du projet, pas à trancher seul.
    ⚠️ Pour vérifier, balaye les **282** fichiers avec `tokenize`, pas une liste
    codée en dur : c'est ainsi qu'une annonce de « nettoyage complet » a été faite
    sur la foi de 6 fichiers examinés.

## 2. Les sept pièges — chacun a déjà été rencontré

### Piège 1 🟢 — La règle de méthode, payée trois fois

> **Une grandeur de bruit qui ne varie pas avec le bruit est un artefact. Sans exception.**
> Divise le bruit par 100 et remesure. Si le chiffre ne bouge pas, ce n'est pas de la
> physique.

📏 En une journée, le même taux de plantage par couche a valu 28 %, puis 1,3 %, puis 1,47 %
à σ → 0. **Deux fois sur trois ce n'était pas de la physique.** Le balayage de σ coûte
quelques secondes et l'a montré chaque fois.

**Trois corollaires, chacun payé au moins une fois :**

1. **Vérifie sur quelle SOURCE un critère se prononce.** Les défauts les plus coûteux
   étaient de cette forme : le signal *propre* au lieu du signal bruité · la grille
   d'*affichage* au lieu de la grille de balayage · une matrice de *zéros* au lieu de
   l'empilement réel.
2. **Ne confonds jamais deux causes sous une même sentinelle.** Trois modes de défaillance
   rendaient la même valeur ; le diagnostic est devenu possible en **une** mesure une fois
   séparés.
3. **Une signature qui ne varie ni avec la profondeur, ni avec l'amplitude, ni avec la
   graine désigne l'algorithme, pas le phénomène.**

### Piège 2 — `params` n'est pas toujours un dictionnaire

Sur certains chemins c'est un objet pydantic (`StratParamsDTO`).
`params.get("cle")` ✅ · `params["cle"] = v` ✅ · **`params.setdefault(...)` ❌ `AttributeError`**.
Ce bug a tué le pipeline entier en 13 secondes, résultat vide, aucune explication. Écris :

```python
if params.get("cle") is None:
    params["cle"] = valeur
```

### Piège 3 — Importer un paquet déclenche son `__init__.py`

Importer `certus_physics.quoi_que_ce_soit` exécute d'abord `certus_physics/__init__.py`,
qui importe la moitié du projet. Depuis un module de `certus/physics/`, c'est un **import
circulaire**. Vérifier les imports du module ne suffit pas : vérifie ceux de son **paquet**.
Pour une simple annotation, utilise `if TYPE_CHECKING:`.

⚠️ Corollaire pour les scripts : `from certus.physics.X import Y` échoue en circulaire ;
passe par la façade `from certus_physics import Y`.

### Piège 4 — Les tests partagent des caches de classe

`SplineBasisCache._cache` et consorts. Symptôme : ton test passe seul, un autre échoue plus
tard. Sauvegarde et restaure le cache dans une fixture `autouse`.

### Piège 5 — Un test qui échoue n'a pas forcément tort… mais parfois si

**Cinq tests** vérifiaient un comportement **faux** et ont dû être retournés : qu'un
matériau introuvable renvoie de l'air (n=1) · que `to_complex()` produise `n + ik` · un test
préservant les variables d'env qu'il assérait absentes · une classe `CertusHubApp` qui n'a
jamais existé · un garde-fou `nogil` visant un kernel renommé.

Ne « répare » pas un test en changeant le nombre attendu. Comprends d'abord. Puis dis
laquelle des deux situations tu as trouvée — code faux, ou test faux — et si c'est le test,
explique pourquoi dans son docstring. Si tu ne sais pas trancher, **arrête-toi et demande.**

### Piège 6 — La Phase A ne dit rien de ce qu'elle fait

Deux systèmes de journalisation : l'un écrit sur la console, l'autre dans une file destinée
à l'interface graphique, que personne ne vide en ligne de commande. **Un silence ne prouve
rien.** Pour savoir ce que la Phase A a fait, lis le `reports/STRAT_observability_*.json` le
plus récent.

### Piège 7 — Le premier calcul est lent, et ce n'est pas une mesure

Numba compile au premier appel : +30 s sans que rien ne soit anormal. Chauffe une fois, puis
mesure. **Et donne la machine entière au run que tu mesures** — voir Règle 5 en §12.

## 3. La boucle de travail

Pour **chaque** action, dans cet ordre, sans en sauter :

1. **Lis l'action** en §9. Si quelque chose est ambigu, **arrête-toi et demande.** Un plan
   ambigu est un défaut du plan, pas une invitation à inventer.
2. **Fais la modification la plus petite possible.** Une seule chose à la fois : si tu
   changes deux choses et que le résultat bouge, personne ne saura laquelle en est cause.
3. **Tests** : `pytest tests/oracle/ tests/unit/ -q --no-cov`. Un échec ⇒ n'avance pas.
4. **Lint** : `ruff check .` doit dire exactement `All checks passed!`
5. **Non-régression bit-à-bit** si tu as ajouté un paramètre — voir la règle d'or ci-dessous.
6. **Mesure** avec la commande exacte, machine libre.
7. **Committe**, puis colle le hash dans ta réponse.

### 🔴 La règle d'or

> **Tout nouveau paramètre doit être inactif par défaut, et le chemin inactif doit donner
> exactement le même résultat qu'avant — au dernier bit.**

Et **pas « aux tests près »** : les tests ne couvrent pas assez de combinaisons pour prouver
une identité numérique. La méthode qui fait foi : capturer une empreinte `float.hex()` du
chemin par défaut sur une large batterie de configurations **avant** la modification, la
recapturer après, exiger **zéro** différence. La correction affine de §8 a été validée ainsi
sur **75 818 configurations**.

### 🟢 Le banc EST déterministe — mais la RECOMPILATION peut décaler les derniers chiffres

📏 **Mesuré le 2026-08-10**, campagne de 10 runs. Quatre runs de configuration neutre, lancés
à la suite, rendent **exactement le même bit** :

```
A12.1  0.002948627371309867
A6.1   0.002948627371309867
A6.2   0.002948627371309867
A6.3   0.002948627371309867
```

⚠️ **Une version antérieure de ce paragraphe affirmait le contraire** — que `parallel=True` +
`fastmath=True` rendaient le banc « non bit-reproductible par construction », avec une gigue
irréductible de 3e-11. **C'était faux, et fondé sur deux points seulement.** L'ordonnancement
des threads ne fait rien varier.

**La seule valeur différente**, `0.002948627371226749` (écart 2,8e-11), est celle du premier
run lancé **après la montée en Python 3.14.7** — donc le seul avec un cache numba **froid**.

> **La règle : à état compilé identique, le banc rend le même bit. C'est la RECOMPILATION qui
> est le facteur de risque, pas l'exécution.**

### 🔴 TRANCHÉ LE 2026-08-10 — la recompilation décale les bits, de façon reproductible

Mesure B0 : cache numba **vidé**, code **strictement inchangé**, configuration neutre.

```
cache chaud, 4 runs             0.002948627371309867
cache FROID, etape 2 (2026-08-09)  0.002948627371226749
cache FROID, B0    (2026-08-10)    0.002948627371226749   <- identique au precedent
```

**Une recompilation décale de 2,819e-11, et deux caches froids indépendants donnent
exactement le même chiffre.** Ce n'est pas du bruit : c'est un second état, reproductible.

**Les trois conséquences, et elles sont définitives :**

1. 🔴 **Le « bit-identique » de C1 est INATTEIGNABLE via le banc, précisément là où on en a
   besoin.** Ajouter un paramètre à un noyau numba change sa signature, donc force une
   recompilation, donc déplace le chiffre. **N'exige jamais l'égalité exacte d'un `RESULT` de
   part et d'autre d'un ajout de paramètre.**
2. ✅ **Le constat §17-1 est définitivement innocenté.** L'écart de 2,5e-11 que j'avais pris
   pour une violation de la règle d'or était T5 changeant la signature du noyau. Retiré par
   prudence hier, retiré par **preuve** aujourd'hui.
3. **A5 doit comparer à état compilé constant** — ou porter cette tolérance explicitement.
   Forcer le mono-thread ne sert à rien : l'ordonnancement n'est pas la cause.

## 4. Quand s'arrêter et demander

- une instruction est ambiguë ;
- un test échoue et tu ne sais pas si c'est le test ou le code qui a tort ;
- une mesure diffère nettement de ce qui était annoncé ;
- tu es tenté de violer un interdit ;
- tu envisages de modifier plus de trois fichiers pour une seule action ;
- **tu obtiens un résultat meilleur que prévu** — c'est très souvent le signe qu'on mesure
  la mauvaise chose.

**S'arrêter n'est jamais un échec. Inventer, si.**

---

# PARTIE II — LE PROJET

## 5. Ce qu'est CERTUS

Suite scientifique de **couches minces optiques** : détermination d'indice, design
d'empilements, stratégie de dépôt. Application **PyQt6** + noyau **NumPy/SciPy/Numba**.

- `certus-optical-suite 26.05.0` — licence propriétaire
- **Python 3.14.7** — 👤 la seule version retenue à partir du 2026-08-09. Le minimum
  syntaxique reste 3.14 (PEP 758 : `except A, B:` sans parenthèses, 14 modules).
  ⚠️ **Après un changement de version, les caches numba sont invalidés** : le premier appel
  est lent (Piège 7) **et les derniers chiffres d'un `RESULT` peuvent bouger**. Les repères
  de §10 ont été mesurés sous **3.14.6**. Toute mesure rapportée doit porter sa version
  d'interpréteur, sinon un écart de version sera attribué au code.
- Cible principale Windows, build gelé PyInstaller
- 183 600 lignes de source · 56 400 de tests · ~2 300 tests collectés

### Points d'entrée (racine)

| Fichier | Rôle |
|---------|------|
| `CERTUS_HUB.py` | Lanceur unifié — **doit rester une couche de composition pure** |
| `CERTUS_DESIGN.py` | Design d'empilements |
| `CERTUS_STRAT.py` | Stratégie de dépôt |
| `CERTUS_RE.py` | Rétro-ingénierie |
| `CERTUS_INDEX.py` / `CERTUS_INDEX_SPLINE.py` | Détermination d'indice |
| `CERTUS_METAL_SINGLE.py` / `CERTUS_METAL_BILAYER.py` | Métaux (mono/bicouche) |
| `CERTUS_FIELD.py` | Champ électrique |

### Architecture

```
certus/
├── physics/   26 fich.  12 703 l.  ← TMM, gradients, colorimétrie, optimiseurs
├── core/      40 fich.  20 615 l.  ← noyau métier, solveurs, config
├── domain/    12 fich.   1 006 l.  ← DDD (entities/events/services/value_objects)
├── spline/    31 fich.  31 010 l.  ← corridors, splines d'indice
├── workers/   27 fich.  11 956 l.  ← threads Qt, DTO
├── utils/     34 fich.  17 401 l.  ← helpers, export, badges
├── metal/      3 fich.   2 529 l.
└── ui/       109 fich.  60 747 l.  ← PyQt6
```

**Frontières à respecter**

- `certus.core`, `certus.physics`, `certus.domain` n'importent **jamais** PyQt6, QWidget, ni
  `certus.ui`.
- `certus.ui` et `CERTUS_HUB.py` ne contiennent **aucun algorithme de calcul**.
- Thématisation : toujours `apply_certus_theme()` et les constantes `CertusTheme`. Jamais de
  hex codé en dur.

**Violations connues — ne pas aggraver**

| Inversion | Nb | Détail |
|-----------|-----|--------|
| `utils` → `ui` | 12 | dont 3 au niveau module (`certus/utils/certus_curve_smoother.py:29-30`, `certus/utils/certus_export.py:13`) : importer ces modules charge PyQt6 |
| `core` → `workers` | 10 | DTO de workers importés par le noyau |
| `physics` ↔ `core` | 29/22 | cycle |

**Règle : ne jamais créer un nouvel import d'une couche basse vers une couche haute.** Si tu
en as besoin, c'est que le symbole doit descendre dans `domain/` ou `core/`.

**Packages implicites.** Seul `certus/domain/` a des `__init__.py` ; les 7 autres
sous-paquets fonctionnent en PEP 420. `pyproject.toml` déclare `packages = ["certus"]`, donc
un `pip install` ne récupérerait aucun sous-module : le projet n'est utilisable qu'en source.

### Pièges de fichiers

- 🔴 **`reports/` contient les résultats scientifiques de l'utilisateur** — classeurs Excel
  et rapports HTML de déterminations d'indice. **Non protégé** : seuls 4 sous-motifs sont
  gitignorés et 33 fichiers sur 226 sont suivis par git — voir interdit 3. Irrécupérable.
  Ne le supprime **jamais** dans un « nettoyage ».
- Les 3 fichiers `certus_*.py` restants à la racine (`certus_curve_smoother`,
  `certus_spectral_preproc`, `certus_substrate_index`) sont des **façades légitimes** de
  ré-export. Des tests font `import certus_spectral_preproc`. Ne les supprime pas.
- `CERTUS_METAL_SINGLE.py` et `CERTUS_METAL_BILAYER.py` sont restés à la racine alors que
  `certus/metal/` existe : migration à moitié faite.
- Le `.coverage` date du 13 juillet et pointe vers un autre snapshot — ne pas s'y fier.

## 6. 🔴 Conventions physiques — à ne pas casser

### Convention Macleod `n̂ = n − ik` (k ≥ 0)

Partout. Avec `n̂ = n + ik`, `compute_RT_from_matrix` produit `R + T > 1`.

### Chemins TMM — lequel utiliser

| Fonction | État | Usage |
|----------|------|-------|
| `compute_TMM_single_point_k0` / `_exact` | ✅ | multicouche |
| `compute_RT_from_matrix` | ✅ | extraction R/T — **toujours celle-ci** |
| `calculate_transmission_single` | ✅ | monocouche, **inclut la face arrière** (Standard Mode) |
| `calculate_reflection_array` → `_single` | ✅ | ajustement d'indice, chemin de production |
| `calculate_RT_single_layer_single` | ✅ | corrigé le 2026-08-02 (`phi_i = -k·n_film_imag·d`), écart ramené de 46 points à 4,4e-16 |

`calculate_transmission_single` inclut délibérément le terme de face arrière
(`DO NOT REMOVE THE BACKSIDE TERM`) : ses résultats diffèrent légitimement d'un TMM nu.

### Marqueurs `─── LOCKED ───`

Signalent du code validé par tests. Ne pas modifier sans relancer les tests cités.
⚠️ **Un marqueur LOCKED n'est pas une preuve** : le bug de signe monocouche portait
`LOCKED` **et** `Macleod convention (+1j, n-ik)` alors que la fonction était fausse.

### 🟢 L'oracle TMM — sers-t'en

`tests/oracle/tmm_reference.py` est une référence TMM **indépendante**, sans une ligne
partagée avec `certus.physics`, écrite depuis Macleod chap. 2 en matrices 2×2 explicites.
Lente et relisible face au livre — c'est volontaire.

```python
import sys; sys.path.insert(0, "tests/oracle")
from tmm_reference import rt_stack, rt_stack_oblique, r_single_layer_front, n_hat
```

**Ce qu'elle a démasqué** : deux bugs de convention de signe, à 46 et **82 points** de
réflectance, tous deux exacts à k=0 donc invisibles aux tests existants.

| Chemin validé | Écart à l'oracle |
|--------|------------------|
| `compute_TMM_generic` | 3,3e-16 |
| `calculate_RT_single_layer_single` | 4,4e-16 |
| `calculate_reflection_infinite_substrate_single` | 4,4e-16 |
| `_oblique_stack_rt_single` (5 angles × s/p × 3 k) | 7,8e-16 |

**Règle : avant de toucher au moindre calcul optique, lance `pytest tests/oracle/`** (237
tests, 2 s). Et quand tu corriges un bug, **vérifie que le test que tu ajoutes échoue sur le
code d'avant correctif** — sinon il ne prouve rien.

## 7. Vocabulaire

| Terme | Sens |
|---|---|
| **le juge de paix** | Le dichroïque 48 couches, `example/example_strat/JSON-strat-example.json`, passe-court, front à ~545 nm. **Le seul exemple valable.** |
| **λ de contrôle** | Longueur d'onde à laquelle la machine surveille le dépôt d'une couche. |
| **bloc** | Groupe de couches consécutives surveillées à la **même** λ. |
| **point tournant** *(turning point)* | 🔴 L'instant où **l'admittance du système entier devient réelle**, donc où `T` passe par un extremum pendant la croissance. Forme fermée : `tan 2δ = R/Q`. **Ce n'est PAS « la couche atteint 1 QWOT »** — voir la ligne suivante, c'est l'erreur la plus coûteuse du projet. |
| **QWOT** | L'épaisseur optique d'**une couche seule**, en quarts d'onde, `m = 4nd/λ`. 🔴 **QWOT ≠ point tournant.** La *période* entre deux points tournants vaut bien un quart d'onde à λ_mon, mais le *départ* est décalé d'une phase `½·arctan(R/Q)` fixée par **l'empilement du dessous**. Les deux ne coïncident que sur **la couche 1 d'un substrat nu** (où `R = 0` exactement, mesuré) ou sur un empilement **entièrement QWOT à λ_mon**. 📏 Se tromper coûte un **facteur 59** : sur le random75 ×0,5, le comptage naïf annonce 59 couches « sans point d'arrêt », le comptage exact en trouve **1**. 🔒 **Lis [`docs/QWOT_ET_TURNING_POINT.md`](docs/QWOT_ET_TURNING_POINT.md) avant d'écrire sur ce sujet** ; `scripts/check_claude_md.py` (contrôle E) refuse mécaniquement toute phrase qui les assimile. |
| **POEM** | Méthode d'arrêt visant un pourcentage de l'amplitude entre les deux derniers points tournants, au lieu d'un niveau absolu. |
| **plantage** | Le dépôt **ne se termine pas** : la machine attend un niveau qui ne vient jamais, ou compte le mauvais nombre de points tournants. Pas une perte de précision — un run perdu. |
| **rendement** | Pourcentage de dépôts qui se terminent. Objectif du physicien : **95 %**. |
| **Phase A** | Choix de la meilleure λ pour chaque couche, une couche à la fois. |
| **Phase B** | Regroupement en blocs et test statistique Monte-Carlo des stratégies. |

---

# PARTIE III — STRAT : LA PHYSIQUE ET LE TRAVAIL À VENIR

## 8. Le cadre — trois phrases du physicien qui gouvernent tout

> 👤 **La chaîne canonique.** *« 1. On simule un dépôt et la mesure de transmission bruitée.
> 2. On utilise le POEM comme méthode d'arrêt. 3. On teste statistiquement tout un ensemble
> de stratégies prometteuses. 4. On en déduit la meilleure stratégie. »*

> 👤 **Le juge.** *« Le juge de paix c'est toujours l'étude stochastique et statistique. Si
> 95 % des dépôts fonctionnent, c'est gagné. »*

> 👤 **L'objectif.** *« Le plus important est la cible spectrale respectée. »*

Cela définit **une grandeur unique** : la meilleure stratégie maximise `P(le filtre sorti
est conforme)`. Un dépôt qui plante et un filtre hors spec sont **le même échec**.
Conséquence : **la DP n'a plus à bien classer, elle doit bien couvrir** — le tri est fait
par la statistique.

## 9. 👤 La machine réelle — spécifications obtenues le 2026-08-08

Ces nombres gouvernent le modèle de monitoring.

| Grandeur | Valeur | Conséquence |
|---|---|---|
| Rotation du plateau | **240 tr/min** | période 250 ms |
| Plateau ~1 m, témoin 20 mm au bord | | vitesse tangentielle **12,6 m/s**, **transit 1,6 ms** |
| Positions par tour | **3** : témoin, noir, vide | `T = (S − D)/(V − D)`, auto-référencé à 4 Hz |
| Vitesse de dépôt | ~0,5 nm/s | |
| **Cadence** | **4 Hz**, une lecture témoin par tour | **un échantillon tous les 0,125 nm** |
| Bruit de lecture | ±0,05 point, largeur totale **0,10** | 👤 le tirage du modèle est **correct**, **à la résolution nominale de 2 nm** |
| **Résolution du monochromateur** | **2 nm** par défaut ; l'utilisateur peut choisir 5 / 1 / 0,5 nm | **figée pour tout le dépôt**. Change le bruit **et** déforme le signal — voir §12.7 |
| Le « 5 σ » du seuil | 👤 *« bien au-dessus du bruit »* | **pas une exigence physique** |

**La rotation moyenne le dépôt** — c'est sa raison d'être — **mais elle échantillonne la
mesure** : chaque point rapporté est un passage, rien ne se moyenne.

**Écart au modèle, mesuré :**

| | Machine | Modèle actuel | Facteur |
|---|---|---|---|
| Pas spatial | 0,125 nm | 4,76 nm (`NPTS=64` sur `3×d_nom`) | **38× trop grossier** |
| Points par couche de 100 nm | 800 | 21 | |
| Historique, par couche relue | 800 | 16 (`NPTS_PREV`) | **50× trop grossier** |

🔴 **Ne pas modéliser σ(T), la grenaille, ni le bruit multiplicatif.** Le modèle actuel — un
tirage borné à ±0,05 point, un seul nombre mesuré, aucun paramètre libre — est défendable. Y
ajouter une structure non mesurée remplacerait une constante mesurée par des paramètres
inventés. 👤 Tranché le 2026-08-08.

---

## 9bis. 🔒 LE MODÈLE DE LA CHAÎNE DE LECTURE — FIGÉ, NE PAS ROUVRIR

**L'OMS 5100 est breveté et son fonctionnement interne est opaque.** On ne saura pas
comment il filtre, ni comment il déclenche. Continuer à poser des questions sur ses entrailles
ne produirait que des paramètres libres, et un modèle à paramètres libres ne prouve rien.

👤 **Décision du 2026-08-08 : on pose une hypothèse raisonnable, on l'écrit, et on s'y
tient.** Ce qui suit est un **postulat de modélisation**, pas une spécification constructeur.
Il est **figé**. On ne le rouvre que si une mesure le contredit — pas parce qu'une autre
hypothèse semblerait plus élégante.

| # | Postulat | Statut |
|---|---|---|
| 1 | Une lecture témoin par tour, **4 Hz** ⇒ un échantillon tous les **0,125 nm** à 0,5 nm/s | 👤 déduit de specs données |
| 2 | Bruit **additif**, borné à **±0,05 point** (A = 5e-4 en unités T), σ = A/3, tirages indépendants entre lectures | 👤 confirmé |
| 3 | La chaîne de détection **moyenne sur 2 s**, soit une **moyenne glissante de `k = 8` lectures** | 🔒 hypothèse figée |
| 4 | ~~Le seuil vaut **3 σ du signal lissé**, soit `A/√k` = 0,354 A~~ → 🔴 **RÉFUTÉ le 2026-08-10.** La borne **mesurée** vaut **1,00 A** à `k = 8`, `N = 800`. Voir l'encadré rouge sous ce tableau. | ❌ **arithmétique fausse** |
| 5 | **Aucun retard** : le logiciel anticipe la valeur de trigger, et l'extremum enregistré est l'extremum lui-même | 🔒 hypothèse figée |
| 6 | Marge de sélection des λ : **5 σ du bruit brut** (1,66 A) aujourd'hui, **10 σ** (3,33 A) à évaluer | 👤 fourchette donnée |
| 7 | Quantification de l'arrêt : `U(0 ; 0,125 nm)`, strictement positive | 🔒 découle de 1 |

**Ce qui est explicitement HORS du modèle**, et le reste :

- σ dépendant de T ou de λ, grenaille, bruit multiplicatif ;
- bruit corrélé d'un tour à l'autre (voilage, faux-rond, gigue de déclenchement) — le modèle
  suppose des tirages **indépendants** ;
- toute forme de filtre autre que la moyenne glissante : exponentiel, médian, confirmation
  sur N lectures.

**Ce qui rouvrirait légitimement le postulat** : un run réel du dichroïque dont le taux de
plantage mesuré s'écarterait nettement du taux prédit. Rien d'autre. En particulier, pas un
raisonnement — ce projet a déjà payé trois fois pour avoir cru un raisonnement sur le bruit.

🔴 **Et c'est exactement ce qui est arrivé au postulat 4.** Il n'a pas été rouvert par un
raisonnement : il a été **réfuté par la mesure que §12.2 réclamait explicitement**, et qui
disait d'avance que 0,354 était *« une dérivation, pas une mesure »*. Le reste du postulat
tient — le lissage `k = 8` aide réellement, la borne passe de 1,66 A sur brut à 1,00 A sur
lissé. C'est **la loi en `1/√k`** qui est fausse, parce qu'elle applique un critère *par
échantillon* à un **extremum courant sur N échantillons**. La valeur 1,00 dépend donc de `N`
autant que de `k` : **c'est une mesure, pas une loi. Si l'un des deux change, remesure.**

### 🔴 MESURÉ LE 2026-08-09 — le postulat 4 ne fait pas ce pour quoi il a été dérivé

`scripts\probe_tp_fabrication.py`. Signal propre **plat**, bruit réel `A = 5e-4`, 20 000
tirages, `N = 800` échantillons (cadence machine), lissage **centré**, vrai
`detect_turning_points`, vrai `_seeded_noise_sample`.

```
  k=1, threshold 1.66 A, N=800  ->    99.955 %     (reference: 99.935 %)   <- ligne de controle
  k=8, threshold 0.354 A, N=800 ->   100.000 %     (12.2 predisait ~0 %)
  same, noise x0.01             ->     0.000 %     <- Piege 1 : c'est bien du bruit

      factor   in sigma_smoothed   fabrication
       0.354                3.00      100.000 %
       0.500                4.24       99.850 %
       0.707                6.00       20.960 %
       1.000                8.49        0.005 %
       1.250               10.61        0.000 %
       1.660               14.09        0.000 %
```

**Ce qui est réfuté, exactement** : pas le lissage (postulat 3, `k = 8` — il aide
réellement : la borne passe de 1,66 sur brut à **1,00** sur lissé). C'est **l'arithmétique du
postulat 4** qui ne tient pas. « 3 σ du signal lissé » est un critère **par échantillon**,
alors que `detect_turning_points` l'applique à un **extremum COURANT sur 800 échantillons**
(`certus_strat_growth.py:127-143` : il émet quand le signal recule de plus que le seuil depuis
le max courant). Sur ~100 fenêtres indépendantes, l'amplitude max−min du bruit vaut déjà
≈ 6 σ — ce que la ligne à 0,707 confirme à 20,96 %. Un seuil posé **à** 3 σ est franchi à tous
les coups.

**La borne mesurée est donc `1,00 A` à `k = 8` et `N = 800`**, soit **8,5 σ du signal lissé**
et non 3. ⚠️ Elle dépend de `N` autant que de `k` : **c'est une valeur mesurée, pas une loi.**
Si `k` ou la cadence changent, **remesure** — n'extrapole pas, et surtout n'écris pas de
formule en `ln N` pour boucher le trou.

⚠️ **`k` reste un paramètre du code**, avec 8 pour valeur retenue. Le figer dans la
documentation n'interdit pas de le **balayer pour vérifier** que les résultats en dépendent
(Piège 1) : un taux de plantage insensible à `k` signalerait que le lissage n'atteint pas le
calcul. Figé veut dire « on ne re-discute pas la valeur retenue », pas « on ne la teste pas ».

## 10. Points de référence — les quatre repères valides, et ce qui les périme

🟢 **LES REPÈRES EXISTENT DEPUIS LE 2026-08-15.** Voici les quatre, tous mesurés **fente
2 nm**, donc sous le modèle courant. Ce sont eux qu'on cite, et aucun autre.

| composant | couches | SEEL | plantage | condition |
|---|---|---|---|---|
| dichroïque `JSON-strat-example` | 48 | **0,173 nm** | 0 % | 6 blocs, une seule campagne |
| passe-bande 3 cavités `JSON-strat-bandpass-3cav` | 35 | **0,482 nm** | 0 % | 6 blocs, mode DEEP |
| **aléatoire** `JSON-strat-random75` | 75 | **0,272 nm** | 0 % | une seule campagne, 241/662 déposables |
| passe-bande 5 cavités `JSON-strat-bandpass-5cav-99c` | 99 | **0,760 nm** | 0 % par campagne | 🔴 **3 verres témoins** — 0-22 / 22-72 / 72-99 |
| le même, **en une seule campagne** | 99 | *aucun score valide* | **100 %** sur 487 stratégies | non fabricable — §25.8 |

🔑 **Lis la troisième et la quatrième ligne ensemble : 75 couches passent, 99 non.** Ce n'est
donc **pas la longueur** qui met le monitoring optique en échec, c'est la **structure**. Le
random75 n'a ni cavité ni miroir ; le 99c a cinq espaceurs à swing nul et des miroirs sous
10⁻⁴. Voir §25.4.

#### 🟠 CES QUATRE SEEL NE VIVENT PAS SUR LE MÊME DOMAINE SPECTRAL — constaté le 2026-08-15

👤 : *« on reste comme cela, mais c'est à noter dans un coin »*. C'est donc **un état de fait
assumé, pas un défaut à corriger** — mais il faut le savoir avant de lire le tableau ci-dessus
comme un classement de difficulté.

| composant | grille de notation | largeur | points |
|---|---|---|---|
| 48c dichroïque | 400 – 700 nm | **300 nm** | 301 |
| 75c aléatoire | 550 – 750 nm | **200 nm** | 201 |
| 35c passe-bande | 600 – 660 nm | **60 nm** | 61 |
| 99c passe-bande | 610 – 655 nm | **45 nm** | 91 (pas de 0,5 nm) |

**Les deux passe-bandes sont déjà notés en zone réduite** — leur configuration resserre la
plage autour de la bande. Les deux autres sont notés large. Donc l'ordre
`0,173 < 0,272 < 0,482 < 0,760` mélange **deux effets** : la difficulté intrinsèque du
composant, **et** la largeur de la fenêtre où l'erreur est regardée. Une bande étroite autour
d'une résonance concentre le score là où le filtre est le plus sensible ; une grille large
dilue la même erreur dans des zones plates.

🔑 **Ce qui reste parfaitement valide malgré ça** : toute comparaison **à composant fixé** —
c'est-à-dire tout ce que fait la campagne du 2026-08-15, où seule la position du changement de
témoin varie sur une grille inchangée. L'avertissement ne porte que sur les comparaisons
**d'un composant à l'autre**.

**Comment c'est calculé, exactement.** Deux grilles à ne pas confondre :

| paramètre | rôle |
|---|---|
| `wl_range_start` → `wl_range_end`, pas `wl_step` | la grille de **notation** : c'est sur elle que RMSE et SEEL sont calculés |
| `scan_wl_min` → `scan_wl_max` | la grille de **balayage** : les λ de contrôle candidates. Aucun effet sur le score |

La pondération spectrale **existe** (`compute_batch_rmse`, argument `weights`,
`certus_strat_batch.py:554`) : on déclare des zones via `params["targets"]`, chaque point reçoit
`poids utilisateur × quadrature en d ln λ`, et **un point hors de toute zone reçoit un poids
nul** — il ne compte même pas au dénominateur. 🔴 **Mais aucune des quatre configurations ne
définit `targets`**, donc le code retombe sur son repli documenté `rank_weights = None` :
**pondération UNIFORME sur toute la grille**. Le mécanisme est écrit et testé, il n'a
simplement jamais servi sur ces composants.

📌 **Si un jour on veut une zone (par exemple 550-650 nm)** : passer par `targets`, pas par
`wl_range`. Changer `wl_range` déplacerait aussi la cible nominale et rendrait tout
incomparable avec les mesures existantes ; `targets` pondère sans changer la grille.

⚠️ **Le 0,86 nm que l'on croise encore dans d'anciens rapports sur le 99c n'est pas une
performance** : c'est un **score de repli**, rendu quand aucune stratégie ne survit à la
porte de plantage. Comparer deux configurations sur des scores de repli revient à comparer
deux façons d'échouer. Voir §25.8.

🔴 **Ce qui PÉRIME un repère.** Le **biais de fente** est actif par défaut depuis le
2026-08-11 (§18bis). Tout `RESULT` mesuré **avant** cette date décrit une machine à fentes
**infiniment fines**, qui n'existe pas. Ce ne sont pas des chiffres faux : ce sont les
**réponses à une autre question**.

**Sont donc périmés, et il ne faut plus les citer** : l'ancien `D0.ref`
`0.0027329534107462224`, la courbe de corridor, la protection POEM ×41,2, la position de la
falaise, et toute statistique par bande antérieure.

⚠️ **`RESULT` agrège les trois niveaux de bruit** (0,5× / 1× / 2×). Il est donc comparable
aux **scores** du classement, et **jamais** aux statistiques **par bande**, qui sont au niveau
nominal seul. `RESULT` **est** le `robustness_score` de la gagnante.

🔴 **Et un `RESULT` seul ne départage rien.** §17-26 l'a mesuré : à N = 150, la dispersion
Monte-Carlo vaut σ ≈ 6 % et l'écart entre la 1ʳᵉ et la 2ᵉ vaut 0,8 σ. **Deux runs qui
diffèrent de moins de ~8 % sont indiscernables.** Ce qui compare deux configurations, c'est
la **classe d'équivalence SEEL** (§14), pas le score.

**Ce qu'il faut faire avant toute mesure au banc :**

```bat
set CERTUS_BENCH_TIMEOUT_S=5400
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

Le plafond était en dur ; il est désormais surchargeable par cette variable d'environnement,
défaut inchangé à 1800 s. **Mets 5400 et laisse finir.**

⚠️ **Le piège, et il a fonctionné deux fois** : au-delà du plafond le banc ne signale pas
d'erreur bruyamment. Il émet `RESULT=None` et un tableau de 12 stratégies au lieu de 345 —
**cela ressemble à un résultat**. Vérifie toujours `WAIT_EXIT` et le nombre de stratégies
avant de lire un `RESULT`.

⚠️ **Une mesure, une machine.** Ne lance rien d'autre pendant un run : ni tests, ni lint, ni
recherche récursive. Le pipeline sature tous les cœurs en `prange`.

**Suite de tests, mesurée sur cette copie le 2026-08-08** :

```
pytest tests/oracle/ tests/unit/ -q --no-cov  ->  2310 passed, 5 skipped in 109.62s
ruff check .                                  ->  All checks passed!
```

⚠️ Des documents supprimés annonçaient 2300 et 2301, avec la **même durée au centième**
(`87.60s`) dans cinq entrées différentes. Ces lignes n'avaient pas été mesurées.
**La référence est 2310** (mesurée le 2026-08-11 ; 2299 avant les tests du corridor).

## 11. Les quatre paramètres du modèle, et où les poser

Dans le JSON de configuration, à la racine. Lus par `collect_params`
(`certus/ui/certus_strat_ui_state.py`). **Tous valent 0 / faux par défaut**, et à 0 le
chemin de calcul est celui d'avant, au bit près.

| Clé JSON | Effet |
|---|---|
| `poem_anchor_noise` | Bruite le signal de monitoring **avant** détection des points tournants, lecture des ancres POEM et test d'atteignabilité. Phase A **et** B. |
| `tp_hysteresis_factor` | Seuil de détection d'un point tournant, en multiples de `A = trigger_tolerance/100`. Vaut **1,66** aujourd'hui. 🔴 **Valeur cible : 1,00**, **mesurée** à `k = 8`, `N = 800` (A1). L'ancienne cible **0,354** = `1/√k` est **RÉFUTÉE** : elle applique un critère *par échantillon* à un extremum courant sur `N` échantillons, et laisse **100 %** de points tournants fabriqués — §9bis-4. Injectable en 5ᵉ argument du script de sonde. |
| `reading_smoothing_window` | ⚠️ **Existe depuis `e0df0e1`**, défaut **1**. Fenêtre de moyenne glissante appliquée au signal de monitoring avant détection, **en lectures machine**. Valeur du modèle figé : **8** (2 s à 4 Hz). 🔴 **Dans l'implantation actuelle ce drapeau commande AUSSI la grille de §12.4** — voir §17. |
| `index_corridor` | ⚠️ **Existe depuis `162a0ff`**, défaut **0,0**. Demi-largeur du corridor d'incertitude d'indice, en **unités d'indice absolues**. Valeur du modèle : **0,005**. Jamais mesuré. |
| `affine_scale_amp` / `affine_offset_amp` | ⚠️ **Existent depuis `f7a3d71`**, défaut **0,0**. Amplitudes du tirage de dérive photométrique, une fois par run. Valeurs de mesure : **0,05** et **0,02** (§12.1). Jamais mesurées. |
| `poem_enabled` | ⚠️ **Existe depuis `f7a3d71`**, défaut **vrai**. Force le repli absolu quand il est faux. C'est le drapeau que §12.1 réclamait. Jamais mesuré. |
| `phase_a_level_margin_factor` | Marge exigée **en transmission** entre le niveau d'arrêt et les points tournants voisins. Active aussi la vraie matrice cumulée en Phase A. |
| `dp_yield_weight` | Poids du rendement dans l'objectif DP : `coût = coût_nm + w·(−log(1−p))`. |

## 12. Le travail à venir, dans l'ordre

> 🔴 **LIS CE TABLEAU AVANT LES 700 LIGNES QUI SUIVENT.** Cette section a été écrite comme
> une liste de travail à faire ; **l'essentiel est fait**, et ce qui suit est surtout la
> physique et les pièges qui restent, pas un ordre de mission. **Ne redémarre pas une action
> marquée ACQUISE.**

| | État au 2026-08-14 | Ce qui reste vraiment |
|---|---|---|
| **12.1** distorsion affine, épreuve de POEM | ✅ **ACQUISE et dépassée.** Protection ×15 à ×17,5 mesurée sur deux graines (A12). `poem_enabled` et les amplitudes affines **existent** dans les signatures. | Rien. ⚠️ Mais lis « la dérive n'est pas affine » ci-dessous : elle **requalifie** ce résultat. |
| **La forme de la dérive photométrique** | ✅ **TRANCHÉE le 2026-08-12** : $\delta T = 4\varepsilon T(1-T)$, pas affine. C'est le bloc le plus important de §12. | L'amplitude $\varepsilon$ reste une **spécification 👤**, pas une mesure. |
| **12.2** lissage de lecture | 🟠 modèle posé, **et son seuil dérivé est RÉFUTÉ** : `0,354` est faux, la mesure dit **`1,00 A`**. | Le lissage exige la grille de 12.4. `machine_sampling_dd` existe et vaut 0 (A8). |
| **12.3** méconnaissance d'indice | ✅ **ACQUISE.** ±0,005, corridor tranché le 2026-08-10, normalisation sur l'enveloppe. | Rien. |
| **12.4** grille à la cadence machine | 🟠 le paramètre existe, dé-soudé du lissage (A8), **et vaut 0 par défaut**. | Trancher 1 nm contre 2 nm — c'est §22, avec son critère posé d'avance. |
| **12.5** quantification du déclenchement | ✅ **ACQUISE.** `U(0 ; 0,125 nm)`, et elle apparaît toute seule dans l'arrondi du Rate. | Rien. |
| **12.7** résolution du monochromateur | 🟠 **le biais de fente est actif par défaut depuis le 2026-08-11** et la fente fait partie de la stratégie. | 🔴 **Le facteur √3 n'est pas corrigé** : la fente est rectangulaire, la formule en production est trop stricte de 1,73×. |
| **12.6** face arrière | ⚪ non fait, et il est écrit « en dernier, ou jamais ». | — |

> **Ce qui suit garde sa valeur pour deux raisons, et deux seulement** : la **physique** y est
> établie et ne se retrouve nulle part ailleurs, et les **pièges** y sont nommés. Le déroulé
> des délibérations, lui, est dans `git log`.

> **Les trois contraintes ci-dessous s'appliquent encore à toute action**, faite ou non.

### Les trois contraintes qui s'appliquent à TOUTES les actions

**C1 — Inactif par défaut, bit-identique.** Tout nouveau paramètre vaut sa valeur neutre par
défaut, et le chemin neutre doit rendre **exactement** les mêmes bits qu'avant. Vérifié par
empreinte `float.hex()` sur une large batterie de configurations, avant/après — pas « aux
tests près ». Voir §3.

**C2 — Nombres aléatoires communs.** Tout tirage aléatoire est une **fonction pure de
(graine, tirage, et un index physique)**. Jamais de la stratégie : ni la longueur d'onde, ni
le découpage en blocs, ni `block_start_layer`, ni une épaisseur *obtenue*. Deux stratégies
comparées sur le même (graine, tirage) doivent voir **exactement le même aléa**, sinon leur
écart de score n'est plus imputable à la stratégie. Le générateur à utiliser est
`_seeded_noise_sample(seed_base, group_idx, run_idx, elem_idx, gaussian)`
(`certus/physics/certus_strat_math.py:384`) — loi tronquée sur [−1, 1], σ = 1/3.

**C3 — Une seule chose à la fois.** Si deux choses changent et que le résultat bouge,
l'attribution est perdue — pour toi et pour tous ceux qui suivront.

---

### 12.1 ✅ L'épreuve de POEM — ACQUISE, et ce qu'il faut en retenir

C'était la seule action pouvant **invalider POEM**, le mécanisme central de STRAT. Elle a été
faite les 10 et 12 août. Trois choses en restent, et rien d'autre.

**1. La protection est réelle et reproductible : ×15 à ×17,5**, mesurée sur deux graines
(A12 du tableau des acquis). 🔴 **Cite la protection, jamais le dommage résiduel** : la
distorsion coûte +0,9 % à la graine 42 et +98 % à la graine 77 — la 42 était un tirage
chanceux, et « +0,87 % » ne doit pas ressortir.

**2. POEM protège même sans aucune distorsion : ×1,975.** Il ne compense donc pas seulement
la dérive photométrique, mais aussi **les erreurs d'épaisseur accumulées**. 🔑 C'est la part
de POEM qui **ne dépend d'aucune hypothèse photométrique**, donc la seule qui survive à la
requalification du bloc suivant. C'est elle qu'il faut citer par défaut.

**3. 🔑 Un mécanisme d'invariance peut s'auto-annuler, et ça ne se voit pas.** Le noyau
annulait son propre effet en **trois** endroits à la fois — inversion parabolique résolue en
unités mélangées, repli absolu qui rendait l'étalonnage perdu, test de swing mis à l'échelle
par le gain. Chacun rendait des nombres plausibles, et ensemble ils auraient fait conclure
**l'inverse de la vérité**. Avant de mesurer une invariance, vérifie que le code ne la
fabrique pas.

⚠️ Portée : `RESULT`, agrégat sur trois niveaux de bruit, sur le seul 48 couches. §15 reste
entier — banc de cohérence, pas validation physique.

#### 🔑 POEM ne réduit pas seulement l'erreur — il change OÙ elle tombe

📏 Profil par bande, `scripts\analyse_bands.py` (2026-08-10, sur les runs déjà au disque,
zéro temps de banc) :

| run | passante | front | **front/passante** |
|---|---|---|---|
| POEM actif, distorsion | 0,002205 | 0,005618 | **2,55** |
| **POEM coupé, distorsion** | **0,042351** | 0,003780 | **0,09** |
| POEM coupé, corridor 0,005 | 0,470535 | 0,378305 | 0,80 |

Avec POEM, l'erreur est **concentrée sur le front** — un décalage de bord. Sans POEM, elle
**inonde la bande passante**, où elle devient de l'ondulation. **Le mode de défaillance
change de nature, pas seulement d'amplitude.**

#### Pièges connus

- 🔴 **Il n'existe pas aujourd'hui de drapeau « désactiver POEM ».** `poem_ok` est décidé
  dans le noyau par `SWING_MIN` et le comptage d'ancres. Le critère de réussite exige de
  pouvoir forcer le repli absolu. Ajouter un paramètre `poem_enabled: bool = True` au noyau
  — inactif par défaut au sens de C1, puisque `True` est le comportement actuel.
- ⚠️ `tp_hysteresis` reste **asymétrique** sous distorsion : `Ts_r` est mis à l'échelle,
  `Ts_n` ne l'est pas, et les deux reçoivent le même seuil **absolu**. Une chute de gain
  rétrécit donc les ondulations réelles face à un seuil fixe et peut fabriquer des
  `CRASH_TP_MISCOUNT`. **Séparer les deux sentinelles dans le rapport** (`int(val // 1e6)`
  donne la cause) pour ne pas confondre cet effet avec le vrai.
- ⚠️ Le bruit `noise_val_precalc` est ajouté à `target_level`, qui est en unités mesurées
  dans la branche POEM et en unités vraies dans le repli. Effet du second ordre, non mesuré.

---

### 🔴 LA DÉRIVE PHOTOMÉTRIQUE N'EST PAS AFFINE — 👤 2026-08-12

> 👤 *« La dérive photométrique a-t-elle un sens sachant que le vide et le noir sont mesurés
> à chaque fois ? »* — puis *« à mon avis cette dérive est maximale si T est proche de 0,5,
> mais sûrement pas de 1 ou de 0. »*

#### Ce que l'auto-référencement retire, et il retire presque tout

`T = (S − D)/(V − D)`, refait **à chaque tour**, quatre fois par seconde (§9). Donc :

- un **gain** commun aux trois positions disparaît exactement :
  `(gS − gD)/(gV − gD) = (S − D)/(V − D)` ;
- un **offset d'obscurité** disparaît par la soustraction du noir ;
- tout ce qui est commun au chemin — lampe, détecteur, électronique — est annulé, et
  annulé **250 ms plus tard**, bien avant d'avoir dérivé.

Un dépôt dure des heures ; la référence se refait quatre fois par seconde. **Le modèle
affine — un gain et un offset tirés une fois par run — est donc très largement éliminé par
la machine elle-même.**

#### 🔑 Et ce qui reste est CLOUÉ AUX DEUX BOUTS

C'est le point, et il est imposé, pas choisi :

| | |
|---|---|
| `T = 0` ⟺ `S = D` | numérateur nul ⇒ `T = 0` **quelle que soit** la dérive multiplicative |
| `T = 1` ⟺ `S = V` | numérateur = dénominateur ⇒ `T = 1`, idem |

**Les deux extrémités de l'échelle sont les deux ancres de la mesure.** L'erreur résiduelle
y est donc nulle par construction, et libre entre les deux.

🔴 **`a·T + b` est la mauvaise forme** : il vaut `b` en 0 et `a + b` en 1, c'est-à-dire qu'il
met de l'erreur **exactement là où l'instrument est le plus exact**.

#### La forme retenue

$$\delta T \;=\; 4\,\varepsilon\,T\,(1-T)$$

nulle aux deux bouts, maximale à `T = 0,5` où elle vaut `ε`. Elle a un mécanisme :
une **non-linéarité du détecteur**, réponse `Φ + κΦ²`, survit au rapport de différences
précisément comme ce terme du second ordre.

🔒 **Amplitude** : à `T = 0,5` la vraie valeur est entre **0,4975 et 0,5025**, bornes à
2 σ. Le tirage borné du projet a `σ = A/3`, donc `2σ = 2A/3 = 2,5e-3` fixe
**`A = 3,75e-3`** — `PHOTOMETRIC_CURVATURE_AMP`.
⚠️ 👤 a **révisé cette valeur d'un facteur 2 vers le bas** le jour même : *« je pense que
j'ai surestimé d'un facteur 2 l'erreur en epsilon à T = 0,5 »*. Tous les chiffres cités
contre l'ancienne valeur ont été **remesurés**, jamais divisés par deux — la réponse
n'est pas linéaire en ε. Tirée **une fois par dépôt**, groupe 2 du
flux affine, distinct des groupes 0 et 1 : trois imperfections indépendantes ne partagent
pas un tirage.

#### 🔴 CE QUE ÇA CHANGE, ET C'EST ÉNORME

📏 Mesuré au noyau, arrêt d'une couche de 53,19 nm sous POEM avec ancres :

| perturbation | déplacement de l'arrêt |
|---|---|
| **affine**, gain 5 % | **−8,6e-12 nm** |
| **affine**, offset 0,02 | **−4,2e-11 nm** |
| **courbure**, ε = 0,00375 | **−0,667 nm** |
| courbure, ε = 0,0075 | −1,28 nm |
| courbure, ε = 0,05 | −6,11 nm |

**Facteur 1,6×10¹⁰ entre l'ancienne perturbation et la nouvelle.** 0,667 nm sur 53, soit
1,3 %, et **treize fois** le seuil de 0,05 nm sous lequel §16 interdit de conclure.

📏 Et sur les 48 couches à 544 nm, l'erreur de **niveau** qu'elle induit vaut **0,15 A en
médiane**, **1,89 A au pire** (couche 6) ; **4 couches sur 48** dépassent 1 A et **aucune**
ne dépasse 2 A. Le swing médian valant 0,140, l'effet est donc modeste sur la couche
typique — mais c'est un **biais**, qui ne s'annule pas sur les tirages, là où `A` est du
bruit qui s'annule.

La raison est le théorème de §12.1 : **POEM est rigoureusement invariant par transformation
affine.** La perturbation modélisée jusqu'ici était donc, très exactement, la seule forme
que le mécanisme absorbe gratuitement. `T(1−T)` n'est pas affine — POEM ne l'absorbe pas.

⚠️ **Le ×41,2 de POEM est donc à requalifier.** Il n'est pas faux : il mesure la protection
contre une perturbation qui, d'une part, est largement retirée par l'auto-référencement, et
d'autre part serait de toute façon absorbée. **Ce qui survit de POEM, et qui ne dépend
d'aucune hypothèse photométrique**, c'est le ×2,43 mesuré *sans aucune distorsion* : la
compensation des erreurs d'épaisseur accumulées.

#### 🔴 LE MOTIF, ET C'EST LA DEUXIÈME FOIS LE MÊME JOUR

Le matin, le biais de fente était modélisé comme **une constante par couche** — et une
constante est le `b` de l'affine, donc la forme que POEM absorbe. L'après-midi, la dérive
photométrique était modélisée comme **affine** — la forme que POEM absorbe.

> **Le défaut n'était pas dans les chiffres. Il était dans le CHOIX DE LA FORME de la
> perturbation, et à chaque fois on avait choisi celle contre laquelle le mécanisme est
> immunisé.**

C'est un piège de méthode à part entière, et il ne se voit pas : les deux modèles rendaient
des nombres parfaitement plausibles. **Quand on teste un mécanisme d'invariance, il faut
d'abord se demander si la perturbation choisie appartient au groupe qu'il annule.**

#### Ce qui reste ouvert

- **L'amplitude `ε` est une spécification 👤, pas une mesure.** Comme la table des facteurs
  de bruit de §12.7, toute conclusion qui en dépend doit survivre à son incertitude.
- **Le voilage des fenêtres** n'est pas couvert. S'il n'affecte que le trajet témoin, il ne
  s'annule pas et produit un vrai gain lentement variable — auquel cas l'affine retrouverait
  un sens **en plus** de la courbure. C'est une question de géométrie du bâti.
- **La non-linéarité du détecteur** est le mécanisme invoqué, pas un mécanisme mesuré.

⚠️ **L'affine reste dans le code, amplitudes à 0.** Ce n'est plus un modèle de la machine :
c'est **l'instrument qui teste le théorème d'invariance** de §12.1, et il garde cette
valeur-là.

---

### 12.2 🔴 Modéliser le LISSAGE de lecture — et surtout pas remonter le seuil

> **Cette action applique le modèle figé du §9bis.** Ne le rediscute pas : l'OMS est breveté,
> son fonctionnement interne restera opaque, et le postulat a été arrêté le 2026-08-08 pour
> clore la question. La fenêtre à utiliser est **`k = 8`**.
>
> 🔴 **NE PRENDS PAS LE SEUIL DE `0,354 A` ÉCRIT PLUS BAS. IL EST RÉFUTÉ.** C'était une
> **dérivation** — `3σ/A = 1/√k` — et elle suppose des échantillons indépendants, alors que
> deux moyennes glissantes voisines partagent 7 lectures sur 8. La borne **mesurée** vaut
> **`1,00 A`** à `k = 8`, `N = 800` (§9bis, postulat 4, 2026-08-10) : **un facteur 2,8
> au-dessus de la dérivation**. Le raisonnement qui suit est conservé parce qu'il explique
> *pourquoi* le seuil descend au lieu de monter — mais **son chiffre est faux**, et c'est le
> troisième cas de ce document où un raisonnement sur le bruit a été démenti par la mesure.

**2 s à 4 lectures/s ⇒ fenêtre de `k = 8` lectures**, soit 1 nm de dépôt à 0,5 nm/s.

#### Le constat qui a mené à ces réponses

Le modèle compare aujourd'hui des lectures **brutes**. Le docstring de
`detect_turning_points` énonce alors sa condition de suffisance : le tirage étant borné à
±A, l'écart maximal du bruit seul vaut 2A, donc `hysteresis ≥ 2·trigger_tolerance/100`
= 1,0e-3. Or `certus_strat_robustness.py:854` calcule `1,66 × 5e-4` = 8,3e-4.

📏 Mesuré — signal propre **plat**, bruit réel, 20 000 tirages, aucun TMM. Fraction des
couches où le bruit **fabrique** un point tournant :

```
hysteresis                      N=80 (modele actuel)      N=320      N=800 (cadence machine)
1.66 A  (configure = 5 sigma)                32.945%    92.995%                      99.935%
2.00 A  (borne, 6 sigma)                      0.480%     7.660%                      30.525%
2.40 A  (7.2 sigma)                           0.000%     0.000%                       0.000%

Controle Piege 1 : bruit x0.50 a N=800, seuil 1.66 A  ->  0.000%
```

Le résidu à 2,00 A n'est pas physique : c'est l'atome de probabilité à l'écrêtage ±1 du
tirage, où `maxv − v` vaut 2A à l'arrondi près et le `>` strict devient un pile ou face en
flottant. Prédiction du mécanisme à N=80 : 0,5 %. Mesuré : 0,48 %.

**Sur des lectures brutes, un seuil à 3 σ est intenable** : le tremblement fait 6 σ de large,
donc une lecture haute suivie d'une lecture basse le franchit à elle seule. **Mais la machine
ne lit pas brut.** C'est le modèle qui est infidèle, pas le seuil.

#### Le modèle correct, et le chiffre qu'il donne

Lisser le signal **avant** la détection, et garder 3 σ **du signal lissé**.

Le lissage agit sur deux fronts, et le second domine :

1. **Amplitude** — moyenner `k` lectures divise l'écart-type par `√k`. À `k = 8`, le
   tremblement passe de 0,10 à 0,035 point.
2. **Corrélation** — deux moyennes glissantes voisines partagent 7 lectures sur 8 et ne
   peuvent donc pas s'écarter brutalement. Fabriquer une fausse inversion exigerait un
   basculement **cohérent** du bruit sur toute la fenêtre, bien plus rare qu'une lecture
   haute suivie d'une lecture basse.

**Le seuil DESCEND, il ne monte pas.** En gardant `tp_hysteresis_factor` exprimé en multiples
de l'amplitude brute A, le critère « 3 σ du signal lissé » s'écrit :

$$\text{tp\_hysteresis\_factor} \;=\; \frac{3\,\sigma_{\text{lissé}}}{A} \;=\; \frac{3}{3\sqrt{k}} \;=\; \frac{1}{\sqrt{k}}
\qquad \Rightarrow \qquad k = 8 \;\Rightarrow\; \mathbf{0{,}354}$$

Contre 1,66 aujourd'hui : **4,7× plus bas**, sur un signal 2,8× plus calme. C'est meilleur
sur les deux tableaux — moins de faux points tournants **et** meilleure détection des vrais
extrema peu marqués, qui est la face du problème jamais mesurée.

🔴 **CE 0,354 A ÉTÉ MESURÉ, ET IL EST FAUX.** La dérivation supposait des échantillons
indépendants ; les moyennes glissantes voisines partagent 7 lectures sur 8. Mesuré le
2026-08-10 à `k = 8`, `N = 800` : la borne anti-fabrication vaut **`1,00 A`**, soit
**2,8 fois** la dérivation. **C'est `1,00` qu'on utilise** (§9bis, postulat 4, et A1/A2 du
tableau des acquis). Ce qui reste vrai du raisonnement ci-dessus : le seuil **descend** avec
le lissage au lieu de monter, et pour les deux raisons données. Seul le chiffre était faux.

#### Le retard : rien à ajouter, le noyau fait déjà bien

👤 Le logiciel anticipe la valeur de trigger, donc le lissage n'introduit pas de retard sur
l'arrêt. **Le noyau est déjà conforme, à deux endroits, et il ne faut pas le « corriger » :**

- l'arrêt est obtenu par **inversion parabolique exacte** de `T(d) = cible` — c'est
  précisément un déclenchement anticipé, sans retard ;
- `detect_turning_points` rend **l'indice de l'extremum lui-même**, pas celui de l'instant où
  le seuil a été franchi. Son docstring le dit : *« la machine enregistre la valeur extrême
  qu'elle a observée, pas le moment où elle a réalisé l'avoir dépassée »*.

**Donc : modéliser le lissage pour son effet sur le BRUIT uniquement. N'ajouter aucun
décalage temporel.**

#### 🔴 Le lissage EXIGE la grille de §12.4 — ne pas l'implémenter avant

La fenêtre se compte **en lectures machine**. Le modèle échantillonne aujourd'hui 21 points
par couche là où la machine en prend 800 : une moyenne sur 8 lectures n'y a **aucun sens**.

Les deux actions se compensent comme dans la réalité : **raffiner la grille seule fait
exploser les faux points tournants** (33 % → 99,9 %) ; la raffiner **avec** le lissage
reproduit ce que la machine fait. **Faire §12.4 d'abord, ou les deux ensemble.**

#### La règle de sélection des λ — réglage distinct, à ne pas confondre

`phase_a_level_margin_factor` exige une distance minimale, **en transmission**, entre le
niveau d'arrêt et le point tournant le plus proche. Ce n'est pas une règle de lecture : c'est
un filtre sur les λ candidates.

| | en σ | en points | statut |
|---|---|---|---|
| Valeur actuelle | 5 σ | 0,083 | |
| 👤 Fourchette voulue | 5 à 10 σ | 0,083 à 0,167 | **tester 10 σ = 3,33** |

Monter à 10 σ restreint le choix de λ mais élargit la marge de sécurité. À mesurer au banc,
**séparément** du lissage (contrainte C3).

⚠️ Ces σ-là portent sur le bruit **brut**, pas lissé : c'est une marge de sécurité sur le
niveau visé, pas une règle de lecture. Ne pas leur appliquer le `1/√k`.

#### Pièges connus

- 🔴 **Un run par configuration, machine libre**, et `CERTUS_BENCH_TIMEOUT_S=5400`. Voir §10.
- ⚠️ `tp_hysteresis_factor` et le lissage sont **liés par `1/√k`** : ne pas les bouger
  indépendamment. Figer `k`, dériver le seuil, ne faire varier que `k`.
- ⚠️ Le postulat du §9bis est **figé**. Si une mesure le contredit — et une mesure seulement,
  pas un raisonnement — c'est le §9bis qu'on rouvre, pas cette action qu'on bricole.

---

### 12.3 Méconnaissance d'indice — 👤 spécification du 2026-08-08

**Ce que le physicien décrit, mot pour mot.** Les indices sont **présupposés**, connus à
**±0,005** près. Ce sont **vraiment les mêmes** pour toutes les couches paires, et les mêmes
pour toutes les impaires — **aucune variation pendant le dépôt**. Mais ce n'est **pas**
±0,005 indépendamment à chaque λ : c'est une **courbe de dispersion** qui peut être
**décalée**, ou **croisée** (pentes différentes), à l'intérieur d'un **corridor de 0,005 sur
tout le domaine spectral**. Et **les courbes restent lisses.**

#### Le modèle qui en découle

Une perturbation **affine en λ**, tirée **une fois par run et par matériau** — pas par
couche, pas par longueur d'onde :

$$\delta_M(\lambda) \;=\; a_M \;+\; b_M \cdot u(\lambda), \qquad
u(\lambda) = \frac{2\lambda - (\lambda_{\min}+\lambda_{\max})}{\lambda_{\max}-\lambda_{\min}} \in [-1, 1]$$

$$n_M^{\text{réel}}(\lambda) \;=\; n_M^{\text{nom}}(\lambda) + \delta_M(\lambda),
\qquad |a_M| + |b_M| \le \delta_{\max} = 0{,}005$$

- `b = 0` → **décalage pur**, la courbe entière est translatée.
- `a = 0` → **croisement pur**, la courbe coupe la nominale au milieu du domaine : c'est le
  cas « pentes différentes ».
- La contrainte `|a| + |b| ≤ δ_max` garantit le corridor **partout**, et l'affinité garantit
  la douceur. Un terme quadratique n'est pas nécessaire : le physicien nomme deux modes,
  décalage et croisement, et l'affine les couvre exactement.

**Tirage borné, cohérent avec le reste du projet** (contrainte C2) :

```python
z1 = _seeded_noise_sample(index_stream_seed, mat_idx, run_idx, 0, True)   # in [-1, 1]
z2 = _seeded_noise_sample(index_stream_seed, mat_idx, run_idx, 1, True)
a_M = delta_max * z1
b_M = delta_max * z2 * (1.0 - abs(z1))     # garantit |a| + |b| <= delta_max
```

`mat_idx` vaut 0 pour H, 1 pour L — **deux tirages indépendants**, les deux matériaux n'ont
aucune raison de dériver ensemble. Nouvelle clé JSON `index_corridor` (défaut **0,0**).

#### Pourquoi décalage et croisement ne coûtent pas la même chose

Le monitoring corrige l'épaisseur optique à **une seule** longueur d'onde, λ_mon.

- Une courbe **décalée** l'est identiquement partout : la correction faite à λ_mon vaut à
  peu près pour tout le domaine. Largement compensable.
- Une courbe **croisée** porte une erreur de **signe opposé** de part et d'autre du
  croisement : la correction faite à λ_mon **aggrave** l'erreur de l'autre côté. Non
  compensable par construction.

**Prédiction à mesurer, pas un acquis** : à corridor égal, `b` devrait être bien plus
destructeur que `a`. Si c'est le cas, cela favorise les stratégies dont les λ de contrôle
sont **réparties** sur le domaine plutôt que groupées — exactement le genre d'arbitrage que
STRAT existe pour trouver. **Tirer et rapporter `a` et `b` séparément**, pour pouvoir
attribuer. Un balayage à `b = 0` puis à `a = 0` tranche en deux runs.

#### 👤 Les deux ambiguïtés sont levées (2026-08-08)

- **`0,005` est la DEMI-LARGEUR** : le vrai indice est dans `n_nom ± 0,005`. Le corridor
  complet fait donc 0,010 de large.
- **`0,005` est en UNITÉS D'INDICE, absolu** — pas un pourcentage. Pour H (n ≈ 2,35), le
  vrai indice est entre **2,345 et 2,355**.

⚠️ **Conséquence à ne pas manquer : le corridor absolu mord plus fort sur L que sur H.**
0,005 sur n_H = 2,35 vaut 0,21 % en relatif ; sur n_L = 1,46 il vaut 0,34 %. Comme
l'épaisseur optique est `n·d`, l'erreur *relative* d'épaisseur optique est l'erreur
*relative* d'indice : **les couches L subissent donc une perturbation 1,6× plus grande que
les couches H**, à corridor égal. `delta_max` est une constante absolue unique appliquée aux
deux matériaux — surtout pas une fraction de `n`.

#### Valeur à utiliser

`delta_max = 0.005`, en unités d'indice, demi-largeur, **identique pour H et L**. Clé JSON
`index_corridor`, défaut **0,0** (contrainte C1).

#### 🔴 TRANCHÉ LE 2026-08-10 — `u(λ)` se normalise sur l'ENVELOPPE grille ∪ monitoring

> 👤 *« L'erreur d'indice est donnée sur la grille spectrale du filtre, pas des monitoring. »*
> — *« C'est sur le max de la grille spectrale / monitoring. »*

**La règle exacte** : le domaine de normalisation est l'**intervalle englobant les deux** —

```python
lo = min(grille_spectrale.min(), lambdas_monitoring.min())
hi = max(grille_spectrale.max(), lambdas_monitoring.max())
```

En pratique la grille spectrale contient les λ de monitoring et l'union se réduit à la grille.
Mais **prendre l'enveloppe ne peut jamais être faux**, et §13 signale précisément que
`clues_at_wl` porte l'union des deux grilles **avec un débordement hors plage** : une λ de
monitoring peut donc sortir de la grille de notation. L'union est la formulation défensive.

**Le code fait aujourd'hui le contraire**, et c'est un défaut, pas un choix :
`corridor_wl_range()` normalise sur les **seules λ de monitoring**, bien plus étroites que la
grille sur laquelle le filtre est jugé.

**Conséquence chiffrée.** Avec un monitoring entre 480 et 620 nm et une grille descendant à
400 nm :

```
u(400 nm) = (2 x 400 - (480 + 620)) / (620 - 480) = -2,14        au lieu de |u| <= 1
delta(400 nm) = 0,005 x (-2,14) = -0,0107                        soit 2,1 x le corridor
```

Le modèle sort donc de la boîte qu'il est censé respecter — **et il en sort précisément là où
le mode croisé fait ses dégâts**, sur les bords, loin du point de contrôle.

🔴 **Toutes les mesures de corridor antérieures au 2026-08-10 sont donc INVALIDES**, y compris
la courbe ×1,98 / ×3,13 / ×5,79 et le croisement de régime qu'elle montrait. Elles ont mesuré
un corridor effectif plus large que 0,005, d'un facteur qui dépend de la stratégie. **Ne les
cite plus.**

⚠️ **La correction n'est pas neutre, et il faut savoir dans quel sens.** Une droite contrainte
à rester dans ±0,005 sur un **large** domaine a nécessairement une **pente plus faible** que la
même droite contrainte sur un domaine étroit. Corriger fait donc deux choses à la fois :
plafonner l'erreur aux bords (moins de dégâts) **et** réduire l'inclinaison vue par le
monitoring (moins de mode croisé). L'effet net est à mesurer, pas à prédire.

**Où intervenir** — les trois fonctions doivent recevoir la grille spectrale, pas la déduire :

| Fichier | Fonction | Ce qui change |
|---|---|---|
| `certus_strat_batch.py` | `corridor_wl_range` | prend **deux** jeux de λ et rend leur **enveloppe** |
| idem | `simulate_stack_robustness_batch` | recevoir la grille spectrale, au lieu de déduire de `layer_wavelengths` |
| idem | `validate_wavelengths_batch` | idem pour la Phase A, au lieu de `candidate_wls` |
| idem | `compute_batch_rmse` | déjà paramétré, il suffit de lui passer la même enveloppe |

🔴 **Un seul appelant doit calculer l'enveloppe, et la passer aux trois.** Si chacune la
recalcule, elles finiront par diverger — c'est exactement ce que `corridor_wl_range` a été
créée pour empêcher il y a deux heures, et le défaut qu'on corrige ici en est déjà une
récidive.

---

### 12.4 Grille d'échantillonnage à la cadence machine — **à faire AVANT 12.2**

> 🔴 **Ordre imposé.** Le lissage de §12.2 se compte en lectures machine : il n'a aucun sens
> tant que la grille n'est pas celle de la machine. Mais la grille seule fait exploser les
> faux points tournants (33 % → 99,9 %). **Donc : cette action d'abord, §12.2 immédiatement
> derrière, et on ne mesure le taux de plantage qu'une fois les deux en place.** Les mesurer
> séparément produirait deux chiffres également faux.

**Cible** : `Δd = v_dépôt / f_échantillonnage` = **0,125 nm**, soit ~800 points par couche de
100 nm contre 21 aujourd'hui. Ce n'est pas un raffinement numérique — **c'est une
caractéristique physique de la machine** (§9).

#### Pièges connus

- 🔴 **`NPTS_PREV = ceil(d_real_j)` casserait C2.** `d_real_j` est l'épaisseur **obtenue**,
  donc dépendante de la stratégie : le nombre de tirages de bruit par couche deviendrait
  fonction de la stratégie évaluée. **Indexer sur `p_thick_nominal[j]`**, qui ne l'est pas.
- 🔴 **Ne jamais raffiner sans 12.2.** À seuil inchangé, la fabrication passe de 33 % à
  99,9 %. Le taux de plantage exploserait et on l'attribuerait à la physique.
- ⚠️ `idx_nom_stop = n_hist + int(round((NPTS - 1) / D_SCAN))` vaut aujourd'hui exactement
  `n_hist + 21` parce que 63/3 est entier. Avec un `NPTS` variable, l'arrondi introduit un
  décalage sous-pas. Vérifier que l'indice d'arrêt tombe toujours sur `d_nom`.
- ⚠️ Le **point dupliqué** à la jonction historique / couche courante (`k == 0`, traité aux
  lignes ~633-638) doit rester un tirage unique. Avec un `NPTS_PREV` variable, l'indice de
  repli devient `NPTS_PREV(i_layer − 1) − 1`, pas la constante 16.

---

### 12.5 Quantification temporelle du déclenchement — `U(0, 0,125 nm)`

Le volet ne peut pas se déclencher avant le franchissement : la loi est **strictement
positive**, jamais centrée. Pas de double comptage avec `noise_val_precalc`, qui est un bruit
**photométrique** (en T) là où celui-ci est **spatial** (en d) — deux effets physiquement
indépendants.

**Quasi gratuit une fois 12.4 fait** : si la grille de balayage est celle de la machine, on
s'arrête au **premier point de grille au-delà du seuil** au lieu d'interpoler, et la
quantification apparaît d'elle-même, sans paramètre supplémentaire.

**Vérification** : Piège 1. Si le taux de plantage ne bouge pas quand on double
`Δd_sample`, la mesure est un artefact.

---

### 12.7 🔴 Résolution du monochromateur — 👤 spécification du 2026-08-09

> 👤 *« Le système de monitoring a une résolution donnée, en général 2 nm, correspondant au
> bruit nominal. Mais l'utilisateur peut choisir 5 nm (bruit divisé environ par 1,5) ou 1 nm
> (bruit × 2) ou 0,5 nm (bruit × 5). La résolution reste figée pendant tout le dépôt. Une
> résolution inadaptée peut fausser les signaux. Mais une résolution excellente augmente le
> bruit ! »*

**C'est le premier réglage du projet qui a un OPTIMUM**, et non un sens de progrès. Tous les
autres paramètres s'améliorent quand on les pousse dans une direction ; celui-ci se dégrade
des deux côtés. C'est ce qui le rend intéressant, et c'est aussi ce qui interdit de le régler
au jugé.

#### 🔑 Le mécanisme exact — 👤 précision du 2026-08-10

> 👤 *« À aucun moment l'OMS ne sait calculer des réponses spectrales avec problème de
> résolution, c'est toujours avec une résolution parfaite ! C'est pour cela qu'ouvrir trop les
> fentes peut être problématique : les niveaux attendus ne sont pas les bons. »*

**La machine compare deux grandeurs qui ne sont pas de même nature :**

| | |
|---|---|
| ce qu'elle **attend** | `T_théorique(λ_mon)` — **monochromatique, résolution parfaite** |
| ce qu'elle **lit** | `⟨T(λ)⟩` moyenné sur `[λ_mon − B/2 ; λ_mon + B/2]` |

Ce n'est donc **pas** une perte de dynamique. C'est un **biais systématique de niveau** :

$$\text{biais}(B) \;=\; \langle T\rangle_B - T(\lambda_{\text{mon}}) \;=\; \frac{T''(\lambda_{\text{mon}})\,B^2}{24}$$

🔴 **Et un biais n'est pas du bruit.** Il ne s'annule pas en moyenne, il ne se dilue pas dans
le Monte-Carlo, il pousse **tous** les tirages du même côté. La machine coupe systématiquement
trop tôt ou trop tard, **et elle n'a aucun moyen de s'en apercevoir** — sa seule référence est
sa propre théorie, qui est monochromatique.

⚠️ **Ne compare donc JAMAIS le biais de fente et le bruit de lecture comme deux termes
équivalents.** Une version antérieure de cette section parlait d'un rapport
`swing_effectif(B) / bruit(B)` à optimiser : **c'était faux.** Un biais de X points est
bien plus destructeur qu'un bruit de X points, parce que la statistique absorbe le second et
pas le premier.

| | Fente large (5 nm) | Fente étroite (0,5 nm) |
|---|---|---|
| **Bruit** | ÷1,5 | **×5** |
| Nature de la pénalité | **BIAIS systématique**, non absorbable | bruit aléatoire, absorbé par la statistique |
| Où c'est pire | là où `T(λ)` est le plus **courbé** — près du front, dans les ondulations | uniforme |

🟢 **Conséquence heureuse : `_calculate_strategy_spectral_resolution` calcule exactement la
bonne grandeur.** Il mesure la courbure spectrale et cherche la largeur à laquelle l'erreur de
convolution atteint la tolérance — c'est-à-dire **à quelle fente le biais atteint la taille du
bruit**. C'est la bonne question, et elle était déjà posée. Il lui manque seulement le facteur
√3 (ci-dessous) et d'être utilisée pour autre chose qu'un rapport.

🟢 **Conséquence pratique : modéliser la résolution est BEAUCOUP moins cher que prévu.**
Pas besoin de convoluer le signal de croissance sur plusieurs λ. Il suffit d'ajouter au
**niveau visé** de chaque couche le biais `T''(λ_mon)·B²/24`, et la courbure est déjà
calculée. **L'action se réduit à un terme additif par couche, plus le facteur de bruit.**

#### 🔒 Le facteur de bruit est une TABLE ESTIMÉE — statut à ne pas confondre

| Résolution | 5 nm | **2 nm** | 1 nm | 0,5 nm |
|---|---|---|---|---|
| Facteur sur `A` | **÷1,5** | **×1** (nominal) | **×2** | **×5** |

🔴 **Ces quatre valeurs ne sont PAS mesurées.** 👤 *« estimés par moi au feeling »*
(2026-08-09). Elles ont donc le statut d'un **postulat de modélisation**, comme §9bis — pas
celui d'une spécification constructeur. Ne les cite jamais comme une mesure.

**Ce que cela impose, et ce n'est pas négociable** : une conclusion tirée de ces chiffres
n'est un résultat physique **que si elle survit à leur incertitude**. Donc toute mesure de
résolution s'accompagne d'un **contrôle de sensibilité** :

> Refaire la comparaison avec les facteurs déplacés dans une fourchette plausible — par
> exemple ÷1,2 au lieu de ÷1,5, et ×3 au lieu de ×5. **Si la résolution gagnante ne change
> pas, la conclusion est robuste et on peut l'écrire. Si elle change, la conclusion dépend
> d'une estimation au feeling et il faut le dire dans la même phrase.**

C'est le même esprit que le Piège 1 : une conclusion qui repose sur un nombre non mesuré
n'est pas de la physique tant qu'on n'a pas montré qu'elle n'en dépend pas.

⚠️ **Ne cherche pas la loi de puissance.** Elle ne tient pas : entre 5 et 2 nm le
comportement est proche du photonique en `1/√B` (√(2/5) = 0,63, soit ÷1,58 contre ÷1,5
estimé), mais en dessous il se dégrade **plus vite** que `1/B` (×5 à 0,5 nm là où `1/B`
donnerait ×4). Ajuster une loi sur quatre estimations produirait un modèle inventé sur des
nombres inventés. Et surtout, une loi permettrait de proposer des résolutions **qui
n'existent pas sur la machine**. **Quatre réglages, quatre entrées de table.**

#### 🔴 La fente est RECTANGULAIRE — et la formule en production est trop stricte de √3

👤 *« rectangle »* (2026-08-09). Le signal mesuré est donc la moyenne **uniforme** de `T(λ)`
sur `[λ₀ − B/2 ; λ₀ + B/2]`, et son erreur au second ordre vaut

$$E_{\text{boxcar}}(B) \;=\; \frac{T''(\lambda_0)\,B^2}{24}$$

Or `_calculate_strategy_spectral_resolution` mesure une **seconde différence** sur
`± test_bw/2`, qui vaut `T''·test_bw²/8`, et en déduit
`res_limit = test_bw·√(tol/curvature)`. Ces deux quantités **ne sont pas la même chose** :

$$\frac{B_{\text{vrai}}}{B_{\text{code}}} \;=\; \sqrt{\frac{24}{8}} \;=\; \sqrt{3} \;\approx\; 1{,}732$$

📏 **Vérifié numériquement** (sonde autonome, intégration boxcar contre la formule de
production, `tol = 5e-4`) :

```
case                                code B_lim  true B_lim    ratio
--------------------------------------------------------------------
pure quadratic  T = 1e-4 lam^2          4.4721      7.7460   1.7321
gentle cosine   period 200 nm           2.8471      4.9320   1.7323
sharp cosine    period  20 nm           0.2850      0.4932   1.7305
sharp cosine    period  10 nm           0.1429      0.2466   1.7252
--------------------------------------------------------------------
sqrt(3) = 1.7321
```

**Le critère actuel est donc conservateur d'un facteur 1,73** : il déclare inutilisable une
largeur de fente qui passe encore. **Et c'est coûteux dans le bon sens** — corriger le
critère **élargit** les fentes admissibles, donc **rend accessible le bonus de bruit ÷1,5**
à des stratégies qui en sont aujourd'hui privées pour rien.

Correction, une ligne :

```python
res_limit = test_bw * np.sqrt(3.0 * T_tolerance / curvature)   # fente RECTANGULAIRE
```

⚠️ **La limite de cette correction, et il faut la connaître** : le √3 vient d'un
développement au **second ordre**. Le tableau ci-dessus le montre en train de se dégrader
quand la structure devient fine devant `B` — 1,7252 à période 10 nm contre 1,7321 sur la
quadratique pure, où le développement est exact. Or c'est précisément là que le critère
compte. **Si `min_resolution` devient un jour un couperet et non un diagnostic, valide-le
contre une intégration boxcar directe sur l'empilement réel**, pas contre le développement.

#### 🔑 La résolution FAIT PARTIE de la stratégie — 👤 2026-08-09

> 👤 *« Il faudra donc implanter la détermination de la résolution optimale pour une stratégie
> donnée… cette résolution fait partie intégrante de "la stratégie" à trouver. »*

Une stratégie n'est donc plus *(découpage en blocs, λ par bloc)* mais
**\*(découpage en blocs, λ par bloc, RÉSOLUTION)\***, avec une seule résolution pour tout le
dépôt.

**Où cette variable a sa place — et où elle ne l'a pas :**

| Étage | Verdict |
|---|---|
| **Phase A** | ❌ Impossible. La Phase A juge **une couche à la fois**, or le coût de la résolution est un compromis **sur tout le run** : la couche qui lie (`worst_layer`) n'est connue qu'une fois la stratégie entière formée. |
| **DP** | ❌ Inutile. La DP optimise une **somme de coûts par couche** ; la résolution est un choix **global unique** qui ne se décompose pas additivement. La mettre dans l'état de la DP multiplierait cet état par 4 sans rien apporter. |
| **Phase B** | ✅ **C'est là.** Chaque stratégie candidate est évaluée aux 4 résolutions. Coût : **×4** sur le criblage Monte-Carlo. Cher, mais honnête — et c'est le seul étage qui mesure la grandeur qui décide. |

🔴 **Contrainte C2, et elle est impérative ici** : le facteur de résolution doit multiplier
**l'échantillon**, jamais entrer dans la graine.

```python
noise = RESOLUTION_NOISE_FACTOR[B] * _seeded_noise_sample(seed, groupe, tirage, elem, True)
```

Sans cela les 4 résolutions voient 4 aléas différents, et l'écart entre elles n'est plus
imputable à la résolution. C'est **exactement** la faute que C2 existe pour empêcher, et elle
serait ici invisible : les quatre chiffres auraient l'air parfaitement plausibles.

**Comment ne pas payer le ×4 en entier.** `_calculate_strategy_spectral_resolution` rend déjà
`min_resolution`, la fente la plus large qu'une stratégie tolère. Les résolutions plus larges
sont *prédites* déformantes. Cela donne un ordre d'évaluation — commencer par les plus
prometteuses — et, **si et seulement si** on a d'abord compté ce qu'elle écarte réellement
(§20-contrôle 4), un pré-filtre. ⚠️ Tant que ce comptage n'est pas fait, c'est un
**diagnostic, pas un couperet** — même règle qu'en §14 pour les heuristiques de la
littérature.

**Et voici l'effet le plus intéressant, celui qu'on n'attendait pas :** la résolution
n'ajoute pas seulement un choix à 4 branches, elle **change quelles λ sont bonnes**. Une λ
posée dans une région spectralement lisse tolère la fente de 5 nm et **empoche le ÷1,5 de
bruit gratuitement** ; une λ posée près du front impose 1 nm et **paie le ×2**. La valeur
d'une λ dépend donc désormais de la douceur spectrale de son voisinage, et pas seulement de sa
dynamique. C'est un arbitrage neuf, il n'est écrit nulle part dans le code, et c'est
typiquement ce que STRAT existe pour trouver.

⚠️ **Le compromis n'est pas le même à toutes les couches, et c'est le nœud.** La finesse
spectrale de l'empilement **croît avec le nombre de couches** : une résolution confortable à
la couche 3 peut être trop grossière à la couche 40. Comme elle est **figée**, l'optimum est
un compromis sur tout le run — et c'est exactement ce que `worst_layer`, déjà rendu par la
fonction ci-dessus, désigne.

**Deux conséquences de tenue de dossier, à ne pas oublier** : la stratégie gagnante doit
**rapporter sa résolution** (sinon elle n'est pas exécutable en salle), et la sonde doit
l'écrire dans son JSON — même leçon que `f4ada2d`.

#### Les questions à poser

| # | Question | Pourquoi elle change le code |
|---|---|---|
| # | Question | Réponse |
|---|---|---|
| Q1 | Forme de la fonction de fente ? | ✅ 👤 **rectangulaire** (2026-08-09). Convolution = moyenne uniforme sur `B`. D'où la correction √3 ci-dessus. |

**Q3, reformulée** — la question portait sur une confusion d'unité dans le code et elle n'était
pas claire. Deux grandeurs différentes cohabitent :

- la **largeur de fente** `B` : la largeur du domaine spectral sur lequel la machine moyenne.
  C'est le sujet de toute cette section. Nominal **2 nm**.
- le **pas de réglage** de λ : la granularité avec laquelle on peut *positionner* le centre de
  la fente. Peut-on demander 545,0 · 545,3 · 545,7 nm indifféremment, ou seulement des
  multiples d'un pas — et lequel ?

`MachineModel` porte `monochromator_resolution_nm = 0.5`, alimenté par une constante nommée
`OMS5100_DEFAULT_MONOCHROMATOR_**STEP**_NM` et documentée « step / precision ». Le nom dit
*pas*, le champ dit *résolution*, et la valeur (0,5) ne correspond pas au nominal (2 nm).
**L'une des deux lectures est fausse et il faut savoir laquelle.**

⚠️ **Pourquoi ça compte pratiquement** : STRAT choisit ses λ de contrôle sur une grille à
**1 nm** (§13, décision tranchée). Si le pas machine vaut 0,5 nm, toute λ de la grille est
atteignable et il n'y a rien à faire. S'il vaut 2 nm, **la moitié des λ proposées ne sont pas
réglables sur la machine**, et §16 l'interdit explicitement : *« ne jamais proposer une λ hors
de la grille de balayage »*. La grille devrait alors s'aligner sur le pas machine.

---

### 12.6 Facteur de face arrière sur les seuils absolus — **en dernier, ou jamais**

`T_back = 4n/(n+1)² ≈ 0,957` pour BK7, soit 4,4 %. Le chemin de **notation** applique déjà la
face arrière complète avec réflexions multiples (`certus_strat_batch.py:310-316`) : l'écart
ne concerne que le signal de monitoring, et vaut **0,002 en absolu** sur `SWING_MIN`.

⚠️ Ne **pas** l'implémenter via `affine_scale` : ce paramètre modélise une dérive
d'étalonnage inconnue du contrôleur, alors que la face arrière est un facteur **connu et
constant**. Les confondre rendrait les deux mesures ininterprétables.

---

## 13. Décisions ouvertes et tranchées

### ✅ Tranchée — la marge de sécurité s'exprime en transmission, jamais en nanomètres

Dans `certus/utils/certus_strat_service.py::_select_candidates_phase_a`, la règle de proximité branche la vraie matrice d'empilement cumulée $M_{\text{before}}$ et remplace le critère fixe en épaisseur par le **critère en transmission** ($\Delta T \ge \text{margin\_factor} \times A$, avec `phase_a_level_margin_factor > 0`).

Près d'un point tournant $T \approx T_{\text{ext}} - c \cdot (d - d_0)^2$, une marge fixe en épaisseur correspond à une fraction d'amplitude non contrôlée ; seule la marge exprimée en transmission garantit un niveau de sécurité homogène et physiquement rigoureux face au bruit de la machine.

### 🔒 FIGÉE LE 2026-08-12 — la grille de balayage reste à 1 nm

👤 *« Enfin on va figer la grille à 1 nm. »* Après la campagne de §22, 8 runs sur les
deux composants et deux graines : **1 seule paire sur 4** satisfait le critère
d'équivalence. Trois fois sur quatre la grille fine gagne, de 19 à 42 %.

⚠️ **Et la quatrième fois la grossière gagne de moitié — ce n'est pas un argument pour
elle.** Le run à 1 nm n'avait tout simplement pas généré la famille gagnante (48 blocs).
C'est un symptôme de recherche non convergée, pas une vertu du pas de 2 nm. **Ne cite
jamais ce cas comme un point en faveur du 2 nm.**

### ✅ Tranchée — le pas d'échantillonnage du dépôt reste GROSSIER

👤 *« Évidemment qu'on ne fait pas un calcul tous les 4 Hz, c'est la base de ce code qui
doit être ultra rapide ! »* (2026-08-12)

`machine_sampling_dd` reste à **0**, soit ~21 points par couche là où la machine en lit
800. **La conséquence, et il faut la connaître** : §12.2 a mesuré que moins de tirages
signifie moins d'occasions pour le bruit de fabriquer un faux point tournant — 32,9 % à
80 points contre 99,9 % à 800, à seuil égal. **Le modèle est donc OPTIMISTE sur ce
mécanisme**, qui pèse 79 % des plantages mesurés (§17-36). C'est un arbitrage assumé
vitesse / fidélité, pas un oubli.

### 🪦 Historique — la mesure de 2026-08-08 qui avait déjà tranché dans le même sens

### ✅ Tranchée — la grille de balayage à 1 nm, ne la rouvre pas

`scan_wl_step` est le pas entre λ de contrôle candidates. Deux simulations complètes
indépendantes, plage identique, seul le pas changeant :

| graine | pas 1 nm | pas 2 nm | verdict |
|---|---|---|---|
| principale | **0,002898** | 0,005283 | 1 nm meilleur, ÷1,82 |
| 77 | **0,003553** | 0,008400 | 1 nm meilleur, ÷2,36 |

⚠️ **Ces quatre chiffres sont HISTORIQUES** — état du code de 2026-08-08, avant A10 et avant
la correction d'enveloppe. Ils ne se comparent qu'entre eux, jamais au repère `D0.ref` de
§10. **Ce qui est acquis, c'est le rapport, pas la valeur** : le pas de 1 nm gagne sur deux
graines indépendantes, d'un facteur ~2. Ne les cite pas comme des `RESULT` courants.

Le pas de **1 nm** est retenu. Il coûte +9 % de temps et rend une gagnante à **2 blocs au
lieu de 4** — moins de changements de λ à exécuter.

> ⚠️ **La prédiction inverse avait été avancée** — qu'une grille plus fine gaspillerait le
> budget en candidates redondantes. La mesure l'a réfutée. **On ne prédit pas un résultat de
> simulation, on le mesure.**

> ⚠️ **Effet de bord.** `wl_step` valant déjà 1 nm, les deux grilles coïncident. Le bug de
> confusion entre elles devient **invisible sans avoir disparu**. **Ne supprime pas
> `_resolve_monitoring_wavelength_grid`** au motif que les grilles sont identiques.

## 14. 👤 Les règles gravées

### L'admissibilité d'une longueur d'onde de contrôle

> *« Une longueur d'onde de contrôle de la couche i (i > 1) est **interdite** si, lorsque le
> signal est bruité, il y a un risque de mal comptabiliser le nombre de turning points ou de
> ne pas s'arrêter au niveau de transmission voulu. »* — *« Valable en phase A comme en
> phase B. »*

Un seul énoncé physique, donc **un seul drapeau pour les deux étages**. Et la marge de
sécurité s'exprime **en transmission, jamais en nanomètres** : près d'un point tournant
`T ≈ T_ext − c·(d−d₀)²`, donc une marge fixe en épaisseur correspond à une fraction
d'amplitude non contrôlée.

### Les λ de contrôle se choisissent sur la grille de balayage

En longueur d'onde, pas en épaisseur. La grille est
`arange_inclusive(scan_wl_min, scan_wl_max, scan_wl_step)`, servie par
`_resolve_monitoring_wavelength_grid` (`certus/core/certus_strat_ranking.py`).

🔴 **Ne JAMAIS la déduire des clés de `clues_at_wl`.** Ce dictionnaire porte l'**union** de
la grille de balayage et de la grille d'affichage, donc un pas plus fin sur tout le
recouvrement **et un débordement hors plage**.

### La cible spectrale reste NON PONDÉRÉE jusqu'à nouvel ordre

> *« La cible spectrale restera non pondérée jusqu'à nouvel ordre. »* (2026-08-06)

Le mécanisme existe et il est testé — `compute_batch_rmse` accepte un vecteur de poids — mais
il est **délibérément inutilisé**.

⚠️ **La conséquence, dite une fois.** 📏 Les deux bandes du juge de paix font **exactement la
même largeur, 141 points chacune sur 301**. Un RMSE uniforme est donc *littéralement
incapable* de distinguer une stratégie qui rate la bande bloquée d'une qui rate la bande
passante : les deux scores sont égaux **à la précision machine**, alors que l'exigence
diffère d'un facteur ~500. Et le score reste dominé par le **décalage du front**, que
personne n'a demandé. **C'est un choix assumé, pas un oubli.**

### Les heuristiques de la littérature sont des diagnostics, pas des filtres

> *« Le 4 %, pour moi, c'était au pif, pour être certain qu'on va y arriver. Alors que là,
> nous on travaille sur de vrais signaux simulés grâce au bruit introduit. »*

15–85 %, amplitude de départ ≥ 4 %, swing in / swing out : **colonnes explicatives**, jamais
couperets. ⚠️ Ne pas confondre avec `tp_hysteresis_factor`, qui ne présélectionne pas : il
décrit comment la machine **lit**, et se **dérive** du bruit mesuré.

### Le mode "Rate" (Quartz / Chrono) sur les couches à faible dynamique du signal

> *« Pour les couches où la dynamique du signal est trop pauvre (faible amplitude optique $\text{swing} < \text{SWING\_MIN}$, et non un critère absolu d'épaisseur), la machine passe en mode "Rate" (comptage de tours / chrono) sans contrôle photométrique POEM. Dans ce mode, **il n'y a aucune compensation d'erreur** et la précision sur l'épaisseur déposée vaut $\sigma_{\text{rate}} = 2\,\%$ de l'épaisseur nominale. »* — (2026-08-09)

1. **Critère de basculement non trivial** : Le basculement dépend de la pauvreté de la dynamique du signal optique effectif ($\text{swing} < \text{SWING\_MIN}$), et non d'un seuil fixe absolu en nanomètres (une couche de 30 nm à très faible contraste d'indice peut présenter une dynamique tout aussi pauvre qu'une couche ultrafine).
2. **Pas d'auto-compensation en mode Rate** : Les erreurs accumulées aux couches précédentes ne sont ni mesurées ni corrigées pendant une couche en mode Rate ; elles sont transmises en boucle ouverte à la couche suivante.
3. ⚠️ **Modèle de bruit d'épaisseur — PÉRIMÉ, voir la dérivation plus bas.** Il posait $d_{\text{réel}} = d_{\text{nom}} \cdot (1 + N(0, 0{,}02))$, c'est-à-dire un tirage indépendant de $\sigma = 2\,\%$. 👤 Abandonné le 2026-08-09 : l'erreur de rate **se calcule**, elle ne se tire pas.
4. **Transition avec POEM** : POEM se réactive dès la première couche présentant une amplitude optique suffisante ($\text{swing} \ge \text{SWING\_MIN}$).
5. **Influence de la dynamique forte sur la précision du Trigger (Piste d'optimisation)** : Le déclenchement d'arrêt (trigger) est d'autant plus précis et insensible au bruit que la dynamique du signal ($\text{swing}$) est forte et la pente raide ($\frac{dT}{dd} \gg 0$). Favoriser les longueurs d'onde offrant une forte dynamique optique est une piste clé pour maximiser la répétabilité du dépôt.

#### 🔵 « le rate est souvent réservé aux couches fines » — l'intuition, et les TROIS critères qu'elle mélange

> 👤 2026-08-15 : *« de même, le rate est souvent réservé aux couches fines »* — dit dans la
> même conversation que l'intuition sur le changement de témoin (§25.4), et de même valeur :
> **c'est ce que les expérimentateurs pressentent, ce n'est pas une mesure.**

Cette phrase est **juste en pratique et imprécise en physique**, et l'écart est instructif.
Il y a **trois critères distincts** dans ce projet, et « couche fine » n'est aucun des trois —
c'est un **proxy** du premier :

| | critère | où il vit |
|---|---|---|
| **1. quand le Rate est NÉCESSAIRE** | `swing < SWING_MIN` — 🔴 **pas** un seuil d'épaisseur. Point 1 ci-dessus le dit explicitement : *une couche de 30 nm à très faible contraste d'indice a une dynamique aussi pauvre qu'une ultrafine.* | implémenté |
| **2. l'intuition de 👤** | **couche fine.** Corrélée au critère 1 — une couche fine parcourt peu de chemin optique, donc produit peu de swing — mais **elle n'est pas équivalente** : le contraste d'indice et la λ de contrôle entrent aussi. | 🔵 non implémentée, et **elle n'a pas à l'être** : le code applique la grandeur exacte dont « fine » est l'approximation. |
| **3. où le solveur ESSAIE le Rate** | **la dernière couche de chaque bloc** (`_rate_candidate_layers`, `certus_strat_robustness.py:513`). Critère de **coût**, pas de nécessité : à une frontière de bloc, `block_start[i+1] = i+1`, donc les ancres sont perdues de toute façon — le Rate y est gratuit. | implémenté |

🔑 **Le point à ne pas manquer** : le critère 3 ne cherche **pas** les couches qui ont besoin
du Rate. Il cherche celles où le Rate **ne coûte rien**. Ce sont deux questions différentes et
le code ne répond aujourd'hui qu'à la seconde.

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
   **0,125 nm à 0,5 nm/s**. C'est **exactement le pas d'échantillonnage du §9bis-1**, et ce
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
    §12.1 a démontrée **non invariante** par distorsion affine, celle qui rend
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

- **Zéro paramètre libre.** C'est exactement ce que §9 exige : ne pas remplacer une constante
  mesurée par des paramètres inventés. Ici on ne pose même plus de constante.
- **La question « biais corrélé ou tirage indépendant ? » n'a plus lieu d'être** : ce n'est
  ni l'un ni l'autre, c'est une **égalité**.
- **Tout est déjà dans le noyau** : `prev_thicknesses_sim[j]` et `p_thick_nominal[j]`,
  utilisées côte à côte à `certus_strat_growth.py:570-571`. Rien à câbler de plus.
- 🟢 **Et c'est une occasion de validation EXTERNE, la première du projet.** `sigma_rate`
  devient une **prédiction** du modèle. Si le simulateur en rend une dispersion du même ordre
  que ce que la machine montre en salle, c'est la première corroboration que STRAT ait jamais
  eue (§15). S'il en rend 0,1 %, c'est que le modèle de bruit rate quelque chose. **Dans les
  deux cas on apprend, et cela ne coûte rien.**

⚠️ **La seule hypothèse que cela introduit** : $v$ est **constante pendant un run**. Si la
source dérive réellement (épuisement, température), un terme de dérive revient — mais alors
il faudra le **mesurer**, pas le poser. Ne pas le réintroduire par raisonnement (§9).

🔴 **Rien de tout cela n'est implémenté.** Aucune ligne de `certus/` ne contient de mode Rate
aujourd'hui — **revérifié le 2026-08-11 par balayage** : zéro occurrence de `sigma_rate` ou
`rate_mode`.

### 👤 A24 — LE PLAN RATE, et il ne part pas au hasard — 2026-08-11

> 👤 *« Sur les 10 meilleures stratégies, essayer de mettre une ou plusieurs couches fines
> en rate. »*

C'est **une passe d'amélioration locale sur un ensemble déjà choisi**, pas un degré de
liberté ajouté à la recherche. Quelques dizaines de variantes de stratégies connues, sans
refaire la Phase A. C'est exactement §14-8, et le coût n'a rien de commun avec celui
d'un Rate/POEM par couche plié dans la DP.

📏 **Trois faits mesurés sur la classe d'équivalence de la référence (10 stratégies) :**

1. 🔑 **Le Rate automatique ne se déclencherait JAMAIS ici.** Les dix ont
   `n_below_swing_min = 0` : aucune couche sous `SWING_MIN`. Le repli automatique est
   **inerte** sur cet empilement, donc l'introduction **délibérée** est le seul moyen de
   tester le Rate. Ce n'est plus une intuition, c'est un comptage.
2. ⚠️ **Le critère est le SWING, pas l'épaisseur** — §14-1 le dit déjà, et on peut
   désormais le mesurer : 7 stratégies sur 10 ont leur couche la plus pauvre en **L24**
   (swing 0,109, soit 2,7 × `SWING_MIN`), les 3 autres en **L47** (0,061, soit 1,5 ×).
3. 🔑 **L47 est le premier essai évident, et pour une raison structurelle.** §14-10
   établit que le coût dominant d'une couche Rate se paie **sur la couche SUIVANTE** —
   ancres vidées, repli sur le niveau absolu, la branche que §12.1 a démontrée non
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

Une couche Rate **recopie** l'erreur relative — §14 le démontre :
`d_réel_i / d_nom_i = d_réel_j / d_nom_j`. Elle n'en **ajoute aucune**. Une chaîne de
couches Rate porte donc toutes **la même** erreur : elle est **gelée, pas amplifiée**.
📏 Vérifié : 40 couches Rate enchaînées, étendue **0,000 %**.

Et c'était vrai **quelle que soit la réponse à Q4**. Ce n'est pas la moyenne qui sauve la
situation ; il n'y avait pas de situation à sauver. *Une inquiétude fondée sur un
raisonnement plutôt que sur un calcul, exactement ce que §9 interdit.*

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

🔑 **Et c'est là que tout converge.** §17-36 a mesuré que sur l'effondrement de la
graine 77, **rien ne plante avant la couche 35** et tout plante de **35 à 47**. Le swing
est aussi souvent le plus pauvre en fin d'empilement (L47 sur 3 des 10 finalistes).

**Trois faits indépendants désignent le même endroit** : c'est en fin d'empilement que
POEM est le plus fragile, que les plantages se concentrent, et que le Rate est le plus
précis. **Ce n'est plus une liste de candidates à balayer, c'est une région.**

⚠️ Ce qu'il faut quand même mesurer, et ne pas déduire : la contrepartie de §14-10 — la
couche **suivante** perd ses ancres — ne diminue pas, elle. Le bilan reste une
soustraction entre deux effets qui grandissent différemment, et c'est le banc qui la fait.

#### 🔑 La décision s'écrit comme une INÉGALITÉ, pas comme un essai

C'est ce qui sépare ce plan d'un balayage au hasard. Sur une couche donnée :

| | ce que ça coûte |
|---|---|
| **POEM** | il **corrige** l'erreur accumulée en amont, mais il paie son propre bruit de lecture **divisé par la pente** `dT/dd`. Sur un signal plat la pente est minuscule : la correction devient elle-même très bruitée. |
| **Rate** | **aucune correction**, mais **aucun bruit neuf** non plus : l'erreur relative est **recopiée** de la dernière couche POEM du même matériau (§14, dérivation). |

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

**Ce placement annule DEUX des trois coûts de §14-10 :**

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
Il se verra dans le régime fragile, celui de §17-36.

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
score. **C'est le contrôle 4 de §20 sous une autre forme : un critère qui n'ordonne rien
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

C'est le contrôle 5 de §20 — *les conclusions dépassent-elles les mesures ?* — et il m'a
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
  branche que §12.1 a démontrée non invariante par distorsion affine, et qui pèse **21 %**
  des plantages mesurés (§17-36).
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
| couche `i+1` | 🔴 **en ajoute un** : sans ancres, repli sur le niveau absolu — la branche que §12.1 a démontrée non invariante |

**La bonne candidate est donc à deux faces** : une couche dont la marge POEM est
**mauvaise** — elle est déjà près de lâcher — et dont la **suivante** a une marge
**large**, capable d'absorber le repli. `margin_level` et `margin_missed` par couche,
câblés le 2026-08-11, donnent exactement ces deux nombres.

#### 🔴 Statut de la formule : elle GÉNÈRE des candidates, elle ne DÉCIDE rien

Le raisonnement ci-dessus est en **nanomètres d'erreur d'épaisseur**. Or §16 est formel —
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
portant chacun ±6 % de bruit — illisible (§17-26). **Prédire puis mesurer teste la
compréhension, pas seulement la configuration** : c'est le contrôle 5 de §20, et c'est
la seule façon d'apprendre quelque chose de transférable à un autre empilement.

🔴 **Le piège de comparabilité, à traiter avant d'écrire la première ligne.** Si une
couche Rate consomme un nombre différent de tirages de bruit que la même couche sous
POEM, le flux aléatoire se décale et **deux variantes ne sont plus comparables** —
contrainte C2, et l'écart observé ne serait plus imputable au Rate. Une couche Rate doit
consommer **les mêmes indices de tirage**, quitte à les gaspiller.

🟢 **Et le dommage est désormais MESURABLE dès le premier run.** §14-10 dit que le Rate
déplace le risque vers le niveau absolu ; `margin_level` par couche (A23 étage 2, câblé
le 2026-08-11) lit exactement cet effondrement sur la couche d'après. Avant aujourd'hui
c'était une hypothèse ; c'est maintenant une grandeur. C'est une action à venir, à faire **après** que les mesures T2 / T5 / T6 aient
été obtenues (§17) — l'introduire avant ajouterait un degré de liberté à un modèle dont on
n'a pas encore mesuré les paramètres existants.

✅ **PLUS RIEN À DEMANDER — les quatre questions sont répondues le 2026-08-11.**
Q1 l'était depuis le 2026-08-09 sans que le tableau l'enregistre ; Q2, Q3 et Q4 le
sont désormais. Les réponses, et surtout **ce qu'elles impliquent**, sont dans A24
ci-dessus. **Le mode Rate n'a plus aucun paramètre libre : il ne reste qu'à
l'écrire.**

### 👤 SEEL — l'erreur équivalente par couche, et sa précision de 0,1 nm

> 👤 *« C'est pour caractériser la performance d'une stratégie donnée. On regarde quel tirage
> aléatoire donne une erreur spectrale du même niveau, et cela donne une erreur moyenne
> équivalente par couche. »* — *« SEEL doit être calculé ou donné avec une précision de
> 0,1 nm, c'est tout. »* (2026-08-10)

**Ce que c'est.** `calculate_seel_analysis` (`certus_strat_service.py:636`) perturbe chaque
couche du nominal par `N(0, σ)` pour `σ ∈ {0,05 ; 0,1 ; 0,3 ; 0,6 ; 1,2 ; 2,0}` nm, 3 lots de
50 tirages, et mesure la RMSE spectrale obtenue. On inverse la courbe : **toute RMSE se lit
alors en nanomètres d'erreur équivalente par couche.** C'est la seule grandeur du projet qu'un
opérateur de bâti comprenne immédiatement.

🔑 **La quantification à 0,1 nm n'est PAS une règle d'affichage — c'est ce qui fait de SEEL un
critère de classement distinct.**

L'ajustement actuel (`certus_strat_service.py:710`) vaut `fit_k = Σxy/Σx²` avec
**`fit_alpha = 1.0` figé en dur** : donc `SEEL = k · RMSE`, une simple constante. Trier sur la
valeur **continue** de SEEL rendrait donc **exactement** l'ordre de la RMSE — un tri qui ne
trie rien.

**Quantifiée à 0,1 nm, elle crée des paliers.** Deux stratégies séparées de moins de 0,1 nm
deviennent **ex æquo**, et il faut un **critère secondaire** pour les départager. Le classement
change réellement, et il change dans le bon sens : *on ne discrimine pas sur un écart qu'on ne
sait pas mesurer.* C'est déjà la règle du §16, qui interdit de conclure d'un écart d'épaisseur
sous 0,05 nm.

👤 **Le critère secondaire est le RENDEMENT** (2026-08-10). La règle de tri complète :

```
1. SEEL arrondi a 0,1 nm          croissant
2. rendement = 1 - taux de plantage   decroissant   <- departage les ex aequo
```

*À performance spectrale indiscernable, on prend la stratégie qui va au bout.* C'est
exactement §8 : *« si 95 % des dépôts fonctionnent, c'est gagné »*, et *« un dépôt qui plante
et un filtre hors spec sont le même échec »*.

⚠️ **L'arrondi se fait sur SEEL, pas sur la RMSE.** Arrondir la RMSE n'aurait aucun sens
physique — c'est un nombre sans unité interprétable. L'arrondi ne devient légitime qu'une fois
la grandeur exprimée en nanomètres, parce que 0,1 nm est une **limite de mesure**, pas une
convention d'affichage.

#### 🔴 Le pas de 0,1 nm est ABSOLU, le bruit statistique est RELATIF — mesuré le 2026-08-11

Le pas fixe appliqué à une grandeur dont l'incertitude est **proportionnelle** fait dériver la
largeur de la classe d'équivalence :

| SEEL de la gagnante | demi-largeur du bin | face au bruit de ±6 % (§17-26) |
|---|---|---|
| **0,3 nm** | **±19 %** | plus large ✅ regroupe correctement |
| 0,6 nm | ±7,8 % | limite — le rang 2 est à **+7,3 %**, indiscernable, et il tombe **hors classe** |
| 1,1 nm | **±4,4 %** | **plus étroit que le bruit** ❌ sépare ce qui n'est pas séparable |

La règle 👤 est donc juste **là où elle a été spécifiée** — près de 0,3 nm, la limite de
mesure — et devient trop fine quand le SEEL grandit. Le correctif n'en change pas l'intention,
il ajoute la seconde limite :

```
demi-largeur de la classe = max( 0,05 nm , 0,06 x SEEL )
```

*On ne distingue jamais en dessous de la limite de mesure, ni en dessous de la résolution
statistique.* Ce sont deux bornes de ce qu'on peut savoir : il faut retenir **la plus
grossière**. À 0,3 nm le 0,05 l'emporte et rien ne change ; à 1,1 nm la classe s'élargit
comme elle le doit.

⚠️ Le **0,06** vient de §17-26 et vaut pour `N = 150`. Il suit `1/√N` — mesuré exact entre
N = 32 et N = 128. **Si la profondeur change, remesure-le, ne l'extrapole pas de tête.**

#### 🔴 REVIREMENT DU 2026-08-14 — la quantification passe de 0,1 nm à 0,01 nm

> 👤 *« SEEL à 0,01 nm près partout »* (2026-08-14).

`SEEL_RESOLUTION_NM` vaut désormais **0.005** (`certus_strat_ranking.py:581`) et
`rank_key_seel_yield_margin` binne à **0,01 nm** (ligne 643). **Tout ce qui précède dans ce
§14 décrit l'état d'avant** : le pas de 0,1 nm et le `max(0,05 ; 0,06 × SEEL)` sont périmés en
tant que description du code.

🔴 **Et le prix du revirement n'est pas mesuré.** À SEEL 0,3 nm, un bin de 0,01 nm face à un
bruit statistique de ±6 % (soit ±0,018 nm) est **près de deux fois plus étroit que le bruit** —
c'est-à-dire exactement le régime que le tableau ci-dessus déclare fautif, « séparer ce qui
n'est pas séparable ». **En pratique : traite un écart d'un bin comme une égalité.**

🔴 **La seconde borne n'est PAS appliquée.** `seel_equivalence_half_width`
(`certus_strat_ranking.py:589`) l'implémente correctement et n'a **aucun appelant en
production** — seulement `tests/unit/test_strat_ranking_rule.py`. Et
`rank_key_seel_yield_margin` **reçoit** `score_resolution_rel` sans jamais s'en servir (corps
ligne 643, bin fixe à `2 × SEEL_RESOLUTION_NM`). La règle « il faut retenir la plus grossière »
est donc du **code testé et mort** : le classement ne connaît que le pas absolu. C'est le
premier chantier de §14, avant tout raffinement.

**Ce qu'il reste à faire :**

| # | Action | Note |
|---|---|---|
| 1 | **Sortir SEEL de l'interface.** Il n'existe qu'en mémoire (`APP_CONTEXT["seel_data"]`), calculé à l'étape 0, et sert à colorer trois colonnes. **Le banc ne le voit pas** — les 26 runs mesurés sont donc tous en unité abstraite. | Coût : ~1 s de calcul, 900 spectres vectorisés |
| 2 | L'écrire dans les rapports de sonde à côté de chaque `RESULT`, et dans `analyse_bands.py` | — |
| 3 | Quantifier à **0,1 nm** partout, affichage compris — le tableau montre aujourd'hui `.3f`, soit 100× la précision utile | 👤 spécifié |
| 4 | Sélecteur de tri : composite (actuel, dominé par le plantage) ou **SEEL quantifié + départage** | c'est le tri qui change vraiment l'ordre |
| 5 | **Vérifier que `alpha = 1` est vrai** et non affirmé | les données sont déjà là : 6 σ × 3 lots |

## 15. 🔴 La validation externe — elle n'a plus qu'un seul chemin

**Aujourd'hui STRAT n'est validé que contre lui-même.** Tout ce qui précède le rendra plus
cohérent ; **rien ne prouvera qu'il dit vrai.**

👤 Deux décisions du 2026-08-06 ferment les portes de substitution : *« seul le 48 couches
est un exemple valable »* et *« oublie aussi la séparatrice »*.

> **Il ne reste qu'un chemin : des dépôts réels du dichroïque 48 couches.** Au moins **deux**
> stratégies réellement déposées, avec leurs spectres mesurés. Deux suffisent, parce que le
> test décisif est **ordinal** — STRAT doit les classer dans le bon ordre. Bien moins
> exigeant qu'une correspondance absolue, et bien plus probant qu'un accord avec soi-même.

⚠️ **Tant qu'on ne les a pas, nommer les choses correctement** : le dichroïque est un **banc
de cohérence**, pas un juge externe. Aucun chiffre de ce document n'est une validation
physique.

## 16. Ce qu'il ne faut PAS faire

- **Chercher un coût prédictif par `sᵀΣs`** — réfuté : ni les sensibilités spectrales
  (+0,589 contre +0,590) ni la covariance (+0,643) n'apportent rien.
- **Réparer l'estimation du coût en nanomètres de la Phase A.** 👤 *« En partie B on se
  branle de l'erreur d'épaisseur, seul l'écart spectral final compte. »*
- **Rendre les « points tournants virtuels » utilisables comme ancres POEM.** Un point
  tournant virtuel est une extrapolation — **la machine ne l'a pas mesuré**.
- **Rétablir un front de Pareto** — `P(conforme)` est un scalaire.
- **Une recherche en faisceau avec *rollout*** — générer largement puis départager par la
  statistique suffit, à condition que la génération vise la couverture.
- **Toucher au cap de 10 λ par bloc** — traité par la séparation spectrale.
- **Activer SYM sans recalibrer `sym_weight`.**
- **Conclure d'un écart d'épaisseur sous 0,05 nm** (moins d'un atome), **d'un écart de λ sous
  le pas de grille**, ou **proposer une λ hors de la grille de balayage**.
- **Réintroduire un mode dégradé SANS le dire.** 👤 *« Interdit le mode fast, je veux un mode
  vraiment semblable à la réalité et j'ai tout mon temps »* (2026-08-05). 🔴 **Cette
  interdiction a été LEVÉE DANS LE CODE le 2026-08-14, et le revirement n'était écrit nulle
  part** — ni ici, ni dans la vitrine ; la décision ne survivait plus que dans un commentaire
  mort (`certus/utils/certus_strat_context.py:345`). FAST existe : combobox
  `certus_strat_ui_layout.py:867`, paramètres `certus_strat_ui_state.py:1288`. Il n'est pas
  le défaut (`setCurrentText("premium")`, ligne 868) et se choisit à la main.
  **Ce qui reste vrai de l'interdiction, et qui est le vrai contenu de la règle :** le taux de
  plantage est **binomial**, et le criblage de FAST est à 10 tirages, donc quantifié à **10 %**
  — un `crash_rate` lu à « 0,0 % » sous FAST signifie « sous 10 % », pas zéro.
  **Aucun taux de plantage lu sous FAST n'est publiable ; seul le SEEL l'est.** La raison
  admise du revirement est de cribler une architecture de blocs en 166 s au lieu de 431 s,
  **pas** de mesurer une robustesse.
  ⚠️ Et le rétablissement est **incomplet** : `fast_auto_blocks` est posé
  (`certus_strat_ui_state.py:1284`) et **journalisé** (`certus_strat_ui_worker.py:375`) alors
  qu'aucun code ne le lit — la branche qui élargissait la plage de blocs n'a pas été
  rétablie. Le journal annonce donc un effet qui n'existe pas. Le rebrancher ou le supprimer,
  mais ne pas le laisser dans le log.
  🔴 **À confirmer par 👤 :** est-ce bien la levée voulue, aux conditions ci-dessus ?
- **Citer les repères « 0,4 nm / 0,3 nm »** — absents de la thèse Zideluns.
- **Tirer une conclusion physique d'un empilement autre que le 48 couches.**
- **Raffiner la grille d'échantillonnage sans corriger le seuil** — voir §12.2.
- **Modéliser σ(T), la grenaille ou le bruit multiplicatif** — voir §9.

---

# PARTIE IV — DÉFAUTS OUVERTS ET AUTRES CHANTIERS

## 17. Défauts ouverts, et constats qui gouvernent

Trouvés en appliquant §20. **Ce qui a été vérifié et qui tient est sorti de ce document** —
`git log` le garde. Ne restent ici que les défauts **encore ouverts**, c'est-à-dire du
travail à faire.

🔴 **Portée de la vérification, pour ne pas s'y tromper** : tout ce qui suit vient de la
lecture des diffs, du code et des artefacts committés, plus `ruff` et la suite de tests.
**Aucune mesure au banc n'a été relancée** — ni T0, ni aucune non-régression. Les
constatations chiffrées ci-dessous portent sur des **artefacts existants**, pas sur des runs
neufs.

### 🔴 Ne tient pas

| # | Ce qui a été trouvé |
|---|---|
| 3 | **Le lissage est une moyenne CAUSALE** (fenêtre `[i−k+1 … i]`), qui décale un extremum de ≈ `(k−1)/2` échantillons, soit **0,44 nm à k = 8**. §12.2 écrit « n'ajouter aucun décalage temporel » et §9bis-5 pose « aucun retard » en postulat figé. Une moyenne **centrée** ne décalerait rien. |
| 4 | **T7 n'est pas implémenté** malgré le message de `162a0ff`. L'arrêt reste obtenu par inversion parabolique continue ; aucune loi `U(0 ; 0,125 nm)` n'existe. Par ailleurs T5, T6 et T7 dans un seul commit contredit **C3**. |
| 18 | 🔴 **Le chemin CONSENSUS ignore `robustness_num_runs`.** Trouvé au rodage du 2026-08-10 : un run demandant **20 tirages**, `CONFIG` à l'appui, rend `0.002948627371309867` — **exactement**, au dernier bit, la référence historique à **150** tirages. `_unpack_consensus_cfg` porte un `consensus_num_runs` distinct, que l'override n'atteint pas. **Toute mesure faite avec le consensus actif est donc à une profondeur autre que celle demandée, et n'est comparable à rien.** Exposer `consensus_num_runs` avant de s'en servir. |
| 15 | 🔴 **Deux configurations différentes rendent le MÊME `RESULT` au bit, alors que leurs bandes diffèrent.** Seuils 2,0 A et 2,4 A : `RESULT = 0.003192038110407474` pour les deux, mais `passante` vaut 0,003214 contre 0,004444 — **38 % d'écart**. Donc `RESULT` est **aveugle à un changement qui déplace visiblement le résultat**. Avant de continuer à s'en servir comme grandeur de tête, il faut savoir ce qu'il agrège exactement : §10 dit « le pire des trois niveaux de bruit », et personne n'a vérifié cette phrase dans le code. |
| 16 | 🟢 **La bande bloquée n'est jamais le mode de défaillance.** Sur les 25 runs au disque, elle est **~567× plus propre** que la passante, sans exception. §14 s'inquiète à juste titre qu'un RMSE uniforme ne puisse pas distinguer les deux bandes — mais **le filtre ne rate jamais son blocage, il rate son passage**. ⚠️ Cela ne clôt pas §14 : l'exigence est ~500× plus serrée en bande bloquée, et 567 ≈ 500 signifie que les deux bandes sont **également proches de leur spec**, pas que l'une est acquise. Il faut les tolérances réelles par bande pour trancher, et on ne les a pas. |
| 12 | 🟠 **La marge de Phase A agit, mais ne change jamais l'issue** — *constat corrigé le 2026-08-11, l'ancien était trop sévère.* Il disait « elle ne rejette RIEN », sur la seule foi d'un `RESULT` bit-identique. **C'était lire la mauvaise grandeur.** D5.marg de la campagne du 2026-08-11 : à 3,33 le classement porte **257** stratégies contre 228 à 1,66, et son **top-5 est différent**. La marge atteint donc bien le calcul et modifie la population de la Phase A. Mais la gagnante reste la **même stratégie physique** — `[544, 531]`, 2 blocs, origine SYM, sous l'id 2226 au lieu de 2228, l'id n'étant qu'un rang d'énumération — et le score est bit-identique. **Le bon énoncé : elle change ce qui est offert, jamais ce qui est retenu.** |
| 19 | 🟢 **La prédiction du §12.3 est CONFIRMÉE, et cette fois sans l'artefact.** Le nombre de blocs de la gagnante croît de façon monotone avec le corridor : **2 → 3 → 4 → 5 → 8**. §12.3 l'annonçait — *« cela favorise les stratégies dont les λ de contrôle sont réparties plutôt que groupées »*. 🔑 **Ce qui rend ce constat solide, c'est qu'il survit à la correction.** Le bug de normalisation poussait dans le **même sens** (il pénalisait les λ groupées d'un facteur allant jusqu'à 21) : tant qu'il était là, l'effet physique était indémontrable. L'artefact retiré, l'effet demeure. |
| 17 | 🔑 **POEM protège AUSSI contre l'erreur d'indice, et ce n'est pas le théorème qui le fait.** Sur le corridor corrigé (2026-08-10), à 0,005 : `SEEL 0,6 nm` avec POEM contre **`22,3 nm` et 29,3 % de plantage** sans — un rapport de **×34,8** sur le `RESULT`. Or POEM n'est invariant que par distorsion **affine**, et une erreur d'indice n'en est pas une. **L'explication est l'autre mécanisme** : POEM recale ses ancres sur les extrema réellement observés, donc il compense les erreurs d'épaisseur **accumulées**. ⚠️ Le facteur de protection propre (rapport des coûts) demande un run POEM-off à corridor 0 sur le code corrigé, **qui n'existe pas encore** — les valeurs ×7,6 puis ×6,85 citées plus tôt sont d'avant l'enveloppe. |
| 26 | 🔑 **LE RÉSULTAT DE LA CAMPAGNE DU 2026-08-11 : à N = 150, le classement départage du BRUIT.** Deux mesures indépendantes le disent, et elles concordent.<br>📏 **(1) Dispersion sur sous-paquets** du run N = 1200, `scripts\analyse_campagne.py`. `spread_relative` est une **étendue** (max−min)/médiane, pas un écart-type : divisée par `E[étendue]/σ` du nombre de paquets, elle donne `σ ≈ 6,28 %` à N = 128 (9 paquets, ÷2,97) et `6,73 %` à N = 256 (4 paquets, ÷2,06). La loi en `1/√N` est **exacte** entre N = 32 et N = 128 : 12,56 / 6,28 = **2,00** pour une profondeur ×4. Donc **σ ≈ 5 à 6 % au point de fonctionnement N = 150**.<br>📏 **(2) Écarts entre stratégies**, classement N = 150, corridor 0 : #1 `0.0027330` · #2 **+6,5 %** · #3 +9,9 % · #4 +11,0 % · #8 +16,6 %.<br>🔴 **L'écart #1→#2 vaut 6,5 %, et la différence de deux scores porte `σ√2 ≈ 8 %` : la gagnante et sa dauphine sont à 0,8 σ. Indiscernables.** Le top 8 entier tient dans ~2 σ.<br>✅ **Corroboré par le balayage D2, obtenu autrement** : le top-5 n'est stable à **aucun** passage de N, et la gagnante alterne 2228 / 2218 / 2228 / 2228 / 2228 / 2218.<br>🔑 **Et les huit lisent `SEEL = 0,3 nm`.** La règle de tri de §14 — SEEL quantifié à 0,1 nm, puis rendement — n'est donc **pas une commodité d'affichage : c'est le classement statistiquement correct**, et cette campagne démontre que le tri continu actuel départage du bruit.<br>💰 **Le coût de l'alternative, chiffré** : séparer 6,5 % à 3 σ demanderait `σ ≈ 1,5 %`, soit `N ≈ 150 × (5,5/1,5)² ≈ 2000` tirages par stratégie — **×13**. La bonne réponse n'est pas de les acheter, c'est de déclarer l'égalité. |
| 42 | 🔑 **LES DIX EX ÆQUO SONT IDENTIQUES SUR 42 COUCHES SUR 48 — et trois choses convergent sur les six dernières.** Mesuré le 2026-08-11 avec le masque de préfixe commun.<br>**Le préfixe commun vaut 42 couches.** Les dix surveillent les 42 premières à **544 nm**, à l'identique. Elles ne diffèrent que par **où** elles changent de λ — couche 42, 43, 44 ou 45 — et **vers quelle** λ (506 à 545 nm). Autrement dit, à l'intérieur de la classe d'équivalence, toute la recherche se réduit à **une seule décision prise dans les six dernières couches**.<br>🔑 **Et cette région est déjà connue pour deux autres raisons** : §17-36 a mesuré que **rien ne plante avant la couche 35** et que tout plante de 35 à 47 ; et le Rate y est le plus précis, puisqu'il y dispose du plus grand nombre de couches de référence (§A24, loi en `1/√n`).<br>**Trois faits indépendants désignent les couches 42 à 47.** Les candidates du placement Rate de 👤 — la dernière couche d'un bloc, celle où λ change à `i+1` — valent ici **41, 42, 43 et 44**. Elles tombent exactement dans cette région.<br>✅ **Le masque fait son travail** : **4** marges discriminantes distinctes au lieu de 2, et l'ordre change réellement. La nouvelle première (`900000208`, 3ᵉ au score) porte **3,32 A** là où l'ancienne première (`2228`) en porte **0,83 A** — quatre fois plus exposée. La plus exposée de la classe, `900000204`, tombe au 10ᵉ rang avec **0,208 A**.<br>⚠️ Quatre stratégies se retrouvent **à égalité au sommet**, marge écrêtée à 2 A : c'est voulu et c'est la règle d'A23 — *au-delà de 2 A, rien ne distingue une impossibilité d'une autre*. Leur ordre relatif reste celui du score, faute de mieux, et il ne faut pas le lire comme un classement. |
| 41 | 🟢 **A23 ÉTAGE 3 — LA MARGE EST VALIDÉE, et le test a été rendu NON CIRCULAIRE avant de l'être.** Mesuré le 2026-08-11 sur les 228 stratégies du repère, **aucun run supplémentaire** — les trois niveaux de bruit étaient déjà calculés.<br>🔴 **L'objection d'abord, parce qu'elle était fondée.** Marge et plantage sortent de la **même** simulation. Et `margin_level` **devient négative** exactement quand `CRASH_LEVEL_UNREACHABLE` se déclenche : marge < 0 ⟺ a planté. Sur 23 stratégies (jusqu'à **−1702 A**) la marge **constate**, elle ne prédit rien. Une corrélation calculée sur l'ensemble complet aurait été une tautologie déguisée en validation.<br>✅ **Le test propre, sur les 205 marges STRICTEMENT POSITIVES** — celles dont la couche critique n'a **jamais** échoué, où la marge dit seulement de combien on est passé près :<br>`0 – 0,3 A` → 21 stratégies, **14 plantent**, taux moyen **0,984 %** · `0,3 – 0,6 A` → 3, toutes plantent, 1,556 % · `0,6 – 0,9 A` → 181, **7 plantent**, taux moyen **0,044 %**.<br>🔑 **Sous 0,6 A : 17 sur 24 plantent (71 %). Au-dessus : 7 sur 181 (4 %). Un facteur 22 sur le taux, prédit depuis le SIGNAL seul.** Corrélation **−0,577** sur ce sous-ensemble.<br>**On peut donc croire la marge à 1× là où le comptage rend zéro** — ce qui était toute la condition d'A23 : *on n'extrapole jamais sans avoir validé l'extrapolation dans le régime où la mesure est possible.*<br>⚠️ **Trois réserves.** La tranche 0,3–0,6 A ne compte que **3** stratégies : elle ne pèse rien seule. **24 stratégies plantent malgré une marge positive** — elles plantent sur une **autre** couche que leur couche critique, ce qui est attendu (la critique est la plus exposée, pas la seule) mais borne la précision du modèle. Et **aucune stratégie n'atteint 2 A** : la règle « au-delà de 2 A, impossible » reste **non testée** sur cet empilement, où rien n'est prouvablement sûr. |
| 39 | 📏 **LA FALAISE, ENCADRÉE SUR 5 GRAINES — campagne G, 2026-08-11. Remplace le §17-35, qui n'avait que 3 graines.**<br>**Où la graine 77 casse exactement** : `0,005 → 0 %` · `0,006 → 0 %` · `0,0075 → 0 %` · `0,010 → 100 %`. **La falaise est entre 0,0075 et 0,010**, donc la marge sur la valeur du modèle vaut **×1,5 à ×2** — plus serré que ce que §17-35 laissait croire.<br>**Le taux d'échec sur 5 graines** : à la valeur du modèle **0,005 → 0 graine sur 5 en échec** (pire cas 0,7 %) · au double **0,010 → 2 graines sur 5** (77 à 100 %, 202 à 37,3 %).<br>🔑 **L'énoncé défendable** : *le design est confortable à l'incertitude d'indice spécifiée, et deux graines sur cinq ne survivent pas à son doublement.* C'est une marge, pas un gouffre — et c'est maintenant chiffré sur un échantillon, pas sur une anecdote.<br>⚠️ **Ne lis pas la non-monotonie de la graine 77 comme un signal** : SEEL 1,3 → 0,7 → 1,0 nm de 0,005 à 0,0075, avec une gagnante à 4, puis 3, puis 2 blocs. C'est §17-26 en action — le classement départage du bruit, et la gagnante est un tirage. Les trois valent « de l'ordre de 1 nm », rien de plus. |
| 40 | 🟢 **LE MONITORING COUCHE-PAR-COUCHE GAGNE SUR 2 GRAINES SUR 5 À LA VALEUR DU MODÈLE.** Rang de la première stratégie à 48 blocs, corridor 0,005 : `graine 42 → 153/165` · `77 → 2/78` · **`101 → 1/80`** · **`202 → 1/90`** · `303 → 98/116`. Les gagnantes des graines 101 et 202 sont **à 48 blocs**.<br>Ce n'est donc ni une anomalie ni un artefact de la graine 101 : **à l'incertitude d'indice réelle, se réancrer à chaque couche est la meilleure stratégie deux fois sur cinq.** Combiné à §17-34 (l'effet se referme au-delà) et à §10.3 de la page (48 blocs coûte ×171 à corridor **0**), le tableau complet est : *le monitoring par blocs gagne quand l'indice est connu, le monitoring par couche gagne quand il l'est mal, et le basculement tombe dans la plage réelle d'un atelier.*<br>⚠️ L'offre varie aussi : 30 stratégies à 48 blocs à la graine 101 contre 4 partout ailleurs. Non expliqué. |
| 37 | 🔴 **LA FALAISE N'EST PAS DE LA PHYSIQUE QUI DURCIT — C'EST LA PHASE A QUI N'A PLUS LE CHOIX, ET LE SYSTÈME NE LE DIT PAS.** Mesuré le 2026-08-11 par comptage des rejets (§20-contrôle 4), sur les `STRAT_observability_*.json` des deux runs effondrés :<br>`candidates offertes` **108** · `interdites pour plantage` **103** · `survivantes, médiane sur 48 couches` **1** · **32 couches sur 48 en repli « moins mauvais taux »** · tolérance de plantage **0,001**, taux minimal réellement observé **0,007** — **7× la tolérance**.<br>**La chaîne complète** : le corridor rend presque toutes les λ inadmissibles → la Phase A ne trouve **aucune** λ sous la tolérance sur 32 couches et garde la moins mauvaise → la stratégie n'est plus *choisie*, elle est **forcée** → la Phase B la trouve à 100 % de plantage.<br>🔴 **Et le résultat final ne porte aucune trace de tout cela.** Il annonce une gagnante, avec un score et un SEEL, exactement comme un run sain. C'est le motif que ce document décrit depuis le début : *ça ne produit pas d'erreur, ça produit un résultat plausible.* Le repli **est** journalisé par couche, mais rien ne remonte au classement.<br>✅ **Correctif à faire, et il est petit** : remonter `n_layers_forced` (le nombre de couches en repli) dans le résultat de stratégie et dans le classement. **Une stratégie bâtie sur 32 couches forcées n'est pas comparable à une stratégie librement choisie**, et aujourd'hui rien ne permet de les distinguer. |
| 38 | 🟠 **Un filtre de plus qui ne rejette RIEN : `forbidden_gain_negative` vaut 0 sur les 8 runs examinés**, à toutes les couches, corridor 0 comme corridor 0,020. Le critère de gain de compensation négatif n'a **jamais** écarté une seule candidate. Comme pour §17-12 et §17-33 : soit il n'atteint pas le calcul, soit ce qu'il écarterait n'existe pas. **Compter avant de conclure** — mais un filtre à zéro rejet sur toute la plage mesurée est un défaut, pas un succès. |
| 33 | ✅ **§17-14 EST TRANCHÉ : `dp_yield_weight` N'ATTEINT PAS LE CALCUL.** F1 du 2026-08-11 l'a porté à 200 sur le bras qui plante à **59,3 %** (POEM coupé + distorsion). Résultat **bit-identique** à `yw = 0`, `0.3279370792191264`, même gagnante `8800`, **même top-5 dans le même ordre**. Or le terme vaudrait `200 · (−log(1 − 0,593))` = **180**, un coût énorme. Ce n'est donc plus l'explication arithmétique de §17-14 : **le fil est coupé.**<br>⚠️ **La nuance qui reste, et il faut la dire** : le `p` de la DP est l'estimation **par couche de la Phase A**, pas le taux final de la Phase B. Il reste donc deux lectures — le paramètre n'atteint pas la DP, ou la DP voit encore `p = 0` même ici. **Pratiquement, c'est le même verdict : comme bouton, il ne fait rien.** Ce qui les départagerait : instrumenter le `p` que la DP reçoit réellement. |
| 34 | 🔴 **MA PRÉDICTION DE §17-30 EST RÉFUTÉE — le monitoring couche-par-couche gagne dans une FENÊTRE, pas de façon monotone.** J'avais posé que si le mécanisme était réel, élargir le corridor devait le pousser plus loin. F2 dit le contraire :<br>`graine 101, corr 0,005` → 30 stratégies à 48 blocs, **rangs 1 à 30** · `graine 101, corr 0,010` → **1 seule, rang 55 sur 68**, et la gagnante fait 3 blocs · `graine 77` → rang 2 puis rang 21.<br>🔑 Et le run qui réfute est **sain** (0 % de plantage, SEEL 1,3 nm), donc ce n'est pas un régime dégénéré qui parle. **Le constat §17-30 reste vrai — le gradient de pire à meilleur existe — mais il n'est pas monotone et je l'avais sur-extrapolé.** Il y a une bande d'incertitude d'indice où se réancrer à chaque couche paie, et elle se referme au-delà. |
| 36 | 🟢 **A23 ÉTAGE 0 REND SON PREMIER VRAI DIAGNOSTIC — impossible à obtenir avant le 2026-08-11.** Sur l'effondrement de la graine 77 à corridor 0,010, le profil par couche montre que **rien ne plante avant la couche 35**, puis tout plante de **35 à 47** — le dernier quart de l'empilement. Sur 1033 plantages par couche : **856 (79 %) sont des `tp_miscount`**, 222 (21 %) des `level_unreachable`.<br>**C'est l'histoire de l'erreur accumulée, lue directement** : l'erreur d'indice se compose le long de l'empilement, et dans le dernier quart l'écart d'épaisseur optique devient assez grand pour que la machine compte le **mauvais nombre d'extrema**. Ce n'est pas le niveau qui devient inatteignable, c'est le **comptage** qui décroche.<br>La gagnante porte en plus `worst_swing = 0,0334` à la couche 31 et **2 couches sous `SWING_MIN`** : la Phase A a retenu une stratégie qui a des couches sans signal exploitable. **Un taux agrégé de « 100 % » ne disait rien de tout cela.** |
| 29 | 🟢 **CAMPAGNE E, 2026-08-11 — les correctifs de cohérence passent la porte C1, et les deux résultats de tête TIENNENT.** 12/12 runs `OK`, code corrigé (§17-20, 23, 24, 25).<br>✅ **Porte C1** : `E0.ref = 0.0027329534106323534` contre `D0.ref = 0.0027329534107462224`, **écart relatif 4,2e-11** — l'ordre de la recompilation (2,8e-11, §3). Aucun correctif n'a fui dans le chemin neutre, donc la campagne est interprétable.<br>✅ **La courbe du corridor survit** : `×1,23 · ×2,03 · ×2,41 · ×4,66` contre `×1,24 · ×1,86 · ×2,46 · ×4,32` avant. Écarts de −0,7 % à +9 %, c'est-à-dire **dans le bruit statistique** (σ√2 ≈ 8 %, §17-26). Exposant **0,545** contre 0,525. **C'était le résultat phare et il est robuste au correctif.**<br>🔑 **POEM : la protection monte à ×41,2** (contre ×17,5). POEM actif ×1,198 sous distorsion, POEM coupé **×49,41**. Couper POEM sans aucune distorsion coûte déjà ×2,43 (contre ×1,975).<br>⚠️ **Le dommage résiduel avec POEM est de +19,8 % ici, pas +0,9 %.** §12.1 disait déjà que le +0,87 % de la graine 42 était un tirage chanceux. **Cite la protection, jamais le résiduel.** |
| 30 | 🔑 **LE MONITORING COUCHE-PAR-COUCHE PASSE DE PIRE À MEILLEUR QUAND LE CORRIDOR S'ÉLARGIT.** Gradient mesuré le 2026-08-11, et il est propre :<br>`corridor 0, graine 42` → 48 blocs au rang **228 sur 228** (dernier) · `0,005 graine 42` → rang 153/165 · `0,005 graine 77` → rang **2**/78 · `0,005 graine 101` → **rang 1, et les rangs 1 à 30**.<br>Le mécanisme est cohérent : les ancres POEM héritées du bloc ont été acquises sous un indice que la machine croit connaître et ne connaît pas. Plus l'erreur d'indice est grande, plus l'historique est **trompeur** — jusqu'au point où se réancrer à chaque couche devient gagnant. C'est le bout extrême de la tendance « λ réparties » du §17-19.<br>🔴 **MAIS ÇA NE CONTINUE PAS — voir §17-34, qui réfute l'extrapolation que j'avais faite ici.** L'effet vit dans une **fenêtre** d'incertitude d'indice et se referme au-delà. Le gradient ci-dessus est réel ; « plus le corridor est large, plus ça gagne » est faux.<br>🔴 **Ça ne contredit PAS le ×171 de §10.3 de la page** : celui-ci est mesuré à corridor **0**, où 48 blocs est effectivement catastrophique. Les deux énoncés portent sur deux régimes. **Ne cite jamais l'un sans son corridor.**<br>⚠️ Constat second, à ne pas perdre : `n_ranked` s'effondre avec le corridor — **228 → 165 → 78 → 80**. La Phase A élimine beaucoup plus de candidates quand l'indice est incertain. Non expliqué. |
| 31 | 🟠 **A23 fonctionne dès le premier usage, et il donne un chiffre honnête plutôt que le chiffre espéré.** Le profil de plantage par couche et le swing de la couche la pire remontent maintenant dans les rapports. Sur la gagnante de E4.101 : `worst_swing = 0,0874` à la **couche 39**, et l'unique plantage `level_unreachable` est **à la couche 39**. Coïncidence parfaite, sur les 10 premières lignes examinées.<br>🔴 **Puis la statistique complète corrige l'enthousiasme : 157 sur 561, soit 28 %.** À comparer à 1/48 ≈ 2 % par hasard : c'est un **enrichissement de 13×**, donc un vrai signal — mais la couche à plus faible swing n'est la couche défaillante que dans un cas sur quatre.<br>**Conclusion, et c'est exactement l'argument d'A23** : le swing est un **proxy**, pas la grandeur. Il faut la **marge** — étage 2 — qui est mesurée sur le signal réel au lieu d'être supposée. Ce 28 % est la meilleure justification qu'on ait pour faire l'étage 2 plutôt que de s'arrêter au swing. |
| 32 | 🔴 **E2 A ÉCHOUÉ, et c'est instructif : `dp_yield_weight` reste indécidable.** Le run devait trancher §17-14 en portant le poids là où il y a des plantages — corridor 0,005, qui plantait à 29,3 % sur le code d'avant. **Sur le code corrigé ce bras plante à 0,0 %**, donc le terme valait encore `w·(−log(1−0)) = 0` et E2 est revenu **bit-identique à E1.3**, même gagnante, même score. §17-14 est toujours ouvert. Le seul bras qui plante encore est E3.4 (POEM coupé + distorsion, **59,3 %**) → c'est là qu'il faut le mesurer, et c'est l'objet de F1. ⚠️ **Leçon de méthode** : une expérience conçue contre un régime que le correctif fait disparaître ne mesure rien. Vérifier que le régime existe **encore** avant de lancer. |
| 28 | 🔴 **AUCUN critère connu d'avance ne permet d'élaguer les 228 stratégies. Mesuré, et il détruit la règle évidente.** À corridor 0 la classe d'équivalence (`SEEL = 0,3 nm`) compte **10 membres, aux rangs 1 à 10, tous à 2 blocs, tous `ELITE` ou `SYM`** — une règle de tri superbe. **Elle ne survit à aucun changement de régime :**<br>`corr 0` → 2 blocs, ELITE+SYM · `0,001` → **3 blocs, `LOCAL_SEARCH` seul** · `0,0025` → 2 à 5 blocs, trois générateurs · `0,005` → **5 blocs, `LOCAL_SEARCH` seul** · `0,010` → **8 blocs, `LOCAL_SEARCH` seul** · graine 77 → 2-3 blocs, **les quatre générateurs** · 101 → LOCAL_SEARCH+SMART_MERGE · 202 → ELITE.<br>🔴 **`LOCAL_SEARCH` ne produit RIEN à corridor 0 et produit la gagnante, seule, à 0,001, 0,005 et 0,010.** La règle « il ne gagne jamais », que les données à corridor 0 justifiaient parfaitement, aurait **jeté la gagnante dans 4 configurations sur 8**. Idem pour « ne garder que les 2 blocs ».<br>**Chaque générateur mérite sa place dans au moins un régime, aucun dans tous.** C'est §13 en acte : *on ne prédit pas un résultat de simulation.*<br>✅ **Le levier qui marche est la PROFONDEUR, pas la population** (§17-27) : générer large, cribler peu (10 tirages, sans perte), approfondir étroit sur les ~10 finalistes. C'est une **réallocation**, pas une dépense en plus — ce qu'on cesse de payer à des stratégies à 3× la gagnante finance la profondeur là où elle décide. 📏 Coût mesuré : **~0,15 s par (stratégie × tirage)** au stade final, la Phase A (~730 s) n'ayant pas à être refaite. |
| 27 | 🟢 **L'entonnoir Phase A → Phase B NE FUIT PAS.** D3 du 2026-08-11, et le contrôle 4 de §20 est satisfait : le criblage **atteint** bien le calcul — `n_ranked` vaut **133 / 140 / 219 / 228 / 445** pour un criblage à 10 / 50 / 100 / 25 tirages et `keep30`. Malgré 445 stratégies classées contre 133, la gagnante est **toujours** `[544, 531]`, 2 blocs, SYM, et le score est bit-identique. **Cribler à 10 tirages ne perd rien, et garder 30 survivantes ne trouve rien de mieux.** ⚠️ C'est un résultat sur **une** graine et **un** empilement : il ferme A20 pour ce cas, pas en général. |
| 21 | ⚠️ **`MAX_LOOKBACK = 4` n'était documenté nulle part ici.** `certus_strat_growth.py:526`. L'historique de bloc rejoué par POEM est écrêté à **4 couches**, quelle que soit la longueur du bloc. C'est délibéré et testé (`tests/unit/test_strat_poem.py:169`), mais il faut le savoir pour lire tout résultat sur le nombre de blocs : **la valeur d'un bloc long est plafonnée par construction.** Un bloc de 24 couches ne rejoue que ses 4 dernières. |
| 22 | ⚠️ **L'historique est échantillonné 1,33× plus grossièrement que la couche courante**, et le commentaire du noyau annonce 4×. `NPTS_PREV = 16` par couche d'historique contre `NPTS = 64` sur `3 × d_nom`, soit 21,3 points par `d_nom` : le rapport de **densité** vaut 21,33/16 = **1,33**, pas 64/16 = 4 — les deux balayages ne couvrent pas la même longueur (`certus_strat_growth.py:511`). Conséquence réelle : un même point physique ne porte pas la même densité de bruit selon qu'il est lu comme historique ou comme couche courante. La grille cadence-machine corrige cela (ligne 652) mais elle est derrière `if smoothing_window > 1` — la soudure du §17-2. **Toutes les mesures faites à `reading_smoothing_window = 1` ont donc l'échantillonnage asymétrique.** |
| 43 | 🟢 **LA SURVEILLANCE PAR BLOCS SURPASSE LE MONOCOUCHE SUR LES DEUX EMPILEMENTS DE RÉFÉRENCE.** Les chiffres et leur artefact sont en **§17-43, en fin de document** (`reports/RAPPORT_SYNTHESE_STRATEGIES_BLOCS_35C_48C.md`) — n'en garde qu'une seule copie, ici le renvoi. 🔑 **5 changements de λ** en atelier au lieu de 34 et 47. 🔴 **La version antérieure de cette ligne citait `0.01824 / 0.00753 / 0.06391` et des SEEL de 0,9 et 0,7 nm : chiffres RÉFUTÉS.** Ils ne sont dans aucun artefact, et les deux SEEL du 35c sont **arithmétiquement impossibles** — $2\sqrt{0{,}08496} = 0{,}583$ nm et $2\sqrt{0{,}06391} = 0{,}506$ nm, pas 0,9 et 0,7. Ne les recopie pas. ⚠️ Le plantage nul est mesuré sur les blocs **présents dans le balayage** : 1 à 9 et 48 sur le 48c, 1 à 7 et 35 sur le 35c. Pas « de 2 à 9 » partout. |
| 44 | 🔑 **POURQUOI LES BLOCS BATTENT LE MONOCOUCHE (PHYSIQUE & POEM).** En monocouche, chaque couche réinitialise la phase et détruit la continuité du signal. Dans un bloc (5 à 8 couches), POEM s'appuie sur la continuité de $T(\lambda)$ et compense les dérives d'épaisseur passées (jusqu'à `MAX_LOOKBACK = 4`). De plus, l'interférence constructive transforme les couches individuelles à pente nulle ($\frac{dT}{de} \approx 0$) en fronts de déclenchement très raides. La **zone Goldilocks (4 à 7 blocs, optimum à 6)** évite à la fois l'aveuglement spectral ($\le 3$ blocs) et la perte de mémoire ($\ge 10$ blocs). |
| 45 | 🟠 **LE BONUS PHASE A BLOCK-AWARE DÉVERROUILLE L'ENTONNOIR, MAIS IL ALTÈRE BIEN LE CHAMP DE COÛT.** `certus_strat_objectives.py:415`, $C \leftarrow C_{\text{local}}/\sqrt{\text{streak}}$, seuil **`streak >= 2`**.<br>• Il fait franchir la troncature `dp_top_k` aux λ stables — **20 en FAST, 40 en PREMIUM, 100 en DEEP**, pas « 40 » : plus le `top_k` est large, moins le bonus change quoi que ce soit, et **aucune mesure ne l'a isolé mode par mode**.<br>• 🔴 **« sans altérer les coûts locaux » était FAUX** : le coût est **écrasé en place**, `cost_raw` (`certus/core/certus_strat_objectives.py:457`) contient déjà la valeur bonifiée, donc le coût d'avant n'est **plus récupérable**.<br>• 🔴 **Le bonus court AVANT `_normalize_phase_a_results`** (`certus_strat_pipeline.py:99`), dont la moyenne est calculée sur les coûts déjà bonifiés (`certus/core/certus_strat_objectives.py:438`) : la moyenne baisse, donc les candidates **non** bonifiées voient leur coût normalisé **monter**.<br>• 🔑 **La normalisation élève au carré** (`certus/core/certus_strat_objectives.py:456`) : ce que la DP de Phase B voit est $C/\text{streak}$, **pas** $C/\sqrt{\text{streak}}$. Un bloc de 9 couches est favorisé d'un facteur **9**, pas 3.<br>• ⚠️ Le seuil `streak >= 2` ne correspond **pas** aux blocs de 5 à 8 couches de la ligne 44 : deux couches consécutives suffisent à gagner un facteur 2, dans un régime qu'aucune mesure ne dit gagnant.<br>• 🔴 **Le « Cost Smoothing testé et réfuté à `0.37784` » n'a JAMAIS été mesuré.** Rien ne l'implémente (`grep cost_smoothing` → 0), il a été écarté par raisonnement. Et `0.37784` est le score de la stratégie **à 1 bloc** d'un run nominal 35c (`reports/campagne_N35_300.log:4309`, graine 42, N = 300). Il ne dit rien du lissage. |
| 9 | **`MachineModel` n'a toujours aucun consommateur en production.** Vérifié le 2026-08-09 : 5 occurrences en tout — la classe, deux ré-exports, un import, le test. Et `trigger_tolerance: float = 0.05` reste documenté « in T units (0..1) » alors que les consommateurs réels divisent par 100 : **piège ×100**. Manquent toujours vitesse de dépôt et cadence, qui sont pourtant en §9. |

**Le point 7 est refermé pour l'avenir** (`f4ada2d`) : la sonde écrit désormais sa
configuration effective dans `r["config"]` et dans le nom du fichier. Les deux artefacts déjà
produits, eux, restent inexploitables — **on ne peut pas les rattraper, il faut les
refaire.**

### ✅ Fermés — talons conservés parce que le code et ce document y renvoient

| # | Ce qu'il en reste |
|---|---|
| 1 | L'écart de 2,5e-11 n'était pas une violation de C1 : c'est la **recompilation** numba. Le seul instrument de C1 reste une empreinte `float.hex()`, qui n'existe pas (A5). |
| 2 | La grille machine était **soudée** au lissage. Dé-soudée : `machine_sampling_dd`, défaut 0. |
| 5 | Trois commits de fonctionnalité n'avaient **aucun** test. Comblé depuis. La règle demeure : **un test doit ÉCHOUER sur le code d'avant**, sinon il ne prouve rien. |
| 7 | 🔑 **Un run qui ne consigne pas sa configuration n'est comparable à rien.** Deux artefacts ont été perdus ainsi. La sonde écrit désormais sa configuration effective dans le résultat **et** dans le nom du fichier — et le nom porte aussi le **composant** (§21). |
| 11 | `CERTUS_POEM_ENABLED=0` était ignoré : `"0 "` avec une espace de fin passait le test d'appartenance. **Toute variable lue est `.strip()`, et une valeur inattendue lève.** |
| 14 | `dp_yield_weight` : tranché en §17-33, il **n'atteint pas le calcul**. |
| 20 | La Phase A recalculait le domaine de normalisation du corridor par couche. Corrigé : **un seul appelant calcule l'enveloppe et la passe aux trois étages.** |
| 23 | 🔑 **La propagation d'état de la Phase A laissait six paramètres à leur valeur neutre**, donc l'historique propagé vivait dans un monde plus propre que les candidates jugées dessus. Corrigé, et la **fente** en a été le septième (§18bis). C'est le motif à surveiller : *l'historique doit être simulé dans le monde où les candidates sont jugées.* |
| 25 | Un repli silencieux réinstallait la normalisation fautive du corridor. **Il lève désormais.** Règle générale : un paramètre manquant est une erreur de programmation, pas un défaut à combler en silence. |
| 35 | La falaise du corridor : périmé par §17-39, mesuré sur 5 graines au lieu de 3. |

## 18bis. 🔴 ÉTAT RÉEL DE L'IMPLANTATION — établi contre le CODE

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

---

## 18ter. ⚡ PERFORMANCE — ce qui a été mesuré, positif comme négatif

👤 *« Vois-tu un moyen de simplifier quelque chose dans STRAT pour gagner en temps
d'exécution, et que la perte de précision soit négligeable ? »*

📏 **Où passe le temps, mesuré** : part fixe **~730 s** (Phase A + DP), coût marginal
**~1,5 s par tirage** au stade final, soit **~0,15 s par (stratégie × tirage)**. La
Phase A représente donc **68 %** d'un run de référence, et elle est dominée par
`simulate_growth_kernel`. **C'est là qu'il faut chercher, et nulle part ailleurs.**

### 🟢 LA FORME FERMÉE — le gain le plus important, et il vient de 👤

> 👤 *« Est-ce que calculer une dérivée théorique permettrait de gagner du temps ? Je
> sais que c'est possible avec les calculs matriciels. »*

La question mène plus loin qu'une dérivée. Pour la couche en croissance sur un
empilement **déjà déposé**, le dénominateur de la transmission s'écrit
`denom = C·cos δ + i·S·sin δ` avec `C` et `S` **constants**, d'où

$$T(d) \;=\; \frac{4\,n_{\text{sub}}}{P + Q\cos 2\delta + R\sin 2\delta},
\qquad \delta = \frac{2\pi n d}{\lambda}$$

📏 **Vérifié numériquement : écart 5,4e-20**, et **1,2e-15 contre l'ORACLE TMM
INDÉPENDANT** sur 40 empilements de 2 à 20 couches — le même ordre que les chemins de
production. Ce n'est pas une approximation, c'est le même calcul écrit autrement.
`P`, `Q`, `R` se calculent **une fois** depuis la matrice de l'empilement.

🔴 **CORRECTION DU 2026-08-11 : le gain réel est ×1,20, pas ×3,6.** Le ×3,6 avait été
mesuré en **Python pur**, où chaque opération complexe passe par l'interpréteur. Le
noyau est **compilé par numba** : le produit matriciel y est déjà du code machine, et
remplacer huit multiplications complexes par deux appels trigonométriques ne change
presque rien. A/B propre à physique égale (`k = 1e-5` contre `k = 1e-3`) :
`0,276 s` contre `0,331 s`. **Un banc en Python ne prédit pas un noyau compilé** —
c'est le Piège 7 sous une autre forme.

**Et les dérivées suivent gratuitement** :

$$\frac{d^2 D}{d\delta^2} \;=\; -4\,(D - P)$$

🔑 **La dérivée seconde ne coûte aucune évaluation trigonométrique neuve** — elle se
déduit de `D` déjà calculée. Vérifié aux différences finies : exact à toutes les
décimales.

| ce que ça remplace | gain |
|---|---|
| 64 produits matriciels 2×2 complexes par couche | **×3,6** mesuré |
| chercher les points tournants **en balayant** | `tan 2δ = R/Q` — forme fermée |
| chercher l'arrêt **en balayant puis interpolant** | `√(Q²+R²)·cos(2δ−φ) = cste` — forme fermée |
| 3 TMM pour l'inversion parabolique | 1 évaluation + les deux dérivées exactes |
| la courbure du biais de fente (3 TMM par couche) | **analytique** |

#### 🔴 La limite, et la mesure qui la fixe — 👤 a tranché le seuil

La forme suppose `δ` réel, donc **`k = 0`**. 👤 *« Je te propose de limiter le code de
STRAT à des cas où `k < 1e-4`. »*

⚠️ **Mes deux premières mesures de cette limite étaient FAUSSES**, et il faut le dire :
j'utilisais des matrices d'empilement **aléatoires**, dont le dénominateur peut frôler
zéro. `T` explosait, et je mesurais l'erreur sur des valeurs non physiques. J'ai
successivement annoncé « faux dès `k = 1e-3` » puis « faux dès `k = 1e-6` ». Les deux
étaient des artefacts de montage.

📏 **Sur un vrai empilement de 24 couches, en ne retenant que les `T` physiques :**

| `k` | écart max sur `T` | en % du bruit de lecture |
|---|---|---|
| 0 | 5,4e-20 | 0,0 % |
| 1e-6 | 4,2e-10 | 0,0 % |
| **1e-4** | **4,2e-8** | **0,008 %** |
| 1e-3 | 4,1e-7 | 0,1 % |

L'erreur croît **linéairement en `k`** et reste **quatre décades sous le bruit** même à
`k = 1e-3`. **Le seuil de 1e-4 est donc bon, et même généreux** — on le garde pour
laisser une décade de marge, une garde devant protéger des cas qu'on n'a pas testés.

🔴 **Et la garde LÈVE, elle ne se rabat pas en silence** (leçon de §17-25). Quelqu'un qui
lance STRAT sur un métal doit l'apprendre, pas obtenir un chiffre plausible.

🔴 **À valider contre l'oracle TMM indépendant, pas contre le noyau.** L'interdit 7
existe parce que deux bugs de signe se sont cachés dans des réimplémentations, valant
**46 et 82 points** de réflectance — et tous deux étaient **exacts à k = 0**, donc
invisibles à un test qui ne regarde que des diélectriques. C'est exactement ce cas de
figure.

### 🔴 LA FENÊTRE DE BALAYAGE — résultat NÉGATIF, consigné comme tel

> 👤 *« Balayer de zéro à trois fois, cela me paraît énorme ! Aucune couche ne va se
> tromper de plus de 10 nm d'épaisseur, ou alors c'est bon à jeter. »*

📏 **Le constat est juste : 63 % du balayage porte sur des épaisseurs qu'aucune couche
n'atteindra sans être bonne à jeter.** Sur la couche de 253 nm, il balaie jusqu'à
**760 nm**.

🔑 **Et le défaut n'est pas que 3 soit trop grand, c'est la MISE À L'ÉCHELLE.** `D_SCAN`
est un **multiple de l'épaisseur**, alors que les deux besoins d'aller au-delà du
nominal sont **fixes en nanomètres** : l'erreur maximale (👤 10 nm) et la demi-période
optique `λ/4n` — **57,9 nm sur H, 93,2 nm sur L**, indépendantes de l'épaisseur de la
couche. Un multiple est donc trop généreux sur une couche épaisse et potentiellement
**trop court** sur une couche fine : le même paramètre faux dans les deux sens.

🔴 **MAIS LA FENÊTRE ADAPTATIVE NE MARCHE PAS, ET LE DRAPEAU RESTE ÉTEINT.**

| version | vitesse | verdicts de plantage |
|---|---|---|
| `nominal + max(marge, demi-période)` | ×1,9 | **cachait des plantages** |
| `nominal + marge + demi-période` | ×1,17 | **6,3 % discordants** sur 378 cas, écart max **1,4 nm** |

**Ma promesse « à densité constante, physique inchangée » était fausse.** La densité
d'échantillonnage est bien préservée — mais le **test d'atteignabilité** borne sa fenêtre
au **prochain extremum après l'arrêt**, et un balayage plus court n'en contient plus : il
retombe sur la fin du tableau, ce qui est **plus permissif**. Le balayage cachait des
plantages, le pire sens possible pour une erreur.

🔑 **Ce que l'échec apprend, et qui vaut le détour** : le balayage sert à **trois** choses,
pas une — trouver l'arrêt (fenêtre **courte**, échantillonnage **fin**), détecter les
points tournants et borner l'atteignabilité (fenêtre **longue**, densité **indifférente**).
Un balayage à **deux zones** les servirait toutes les trois. ⚠️ Mais c'est bloqué par A8 :
tant que la grille TMM **est** la grille de bruit, un échantillonnage non uniforme donne
une densité de tirages non uniforme, donc un taux de fabrication non uniforme.

### 🔴 TROIS MESURES NÉGATIVES — les pistes de dérivée analytique sont FERMÉES

Elles valent autant que les positives : quelqu'un reproposera chacune des trois.

#### 1. L'inversion parabolique est déjà exacte à 2,1e-10 nm

Le meilleur candidat sur le papier : **3 évaluations TMM par (tirage, couche)**, en pleine
boucle chaude, pour approximer une courbe qu'on connaît désormais exactement.

📏 **Écart maximal de la parabole à la solution exacte, sur 200 empilements aléatoires de
4 à 30 couches : `2,083e-10 nm`.** Le seuil sous lequel un écart d'épaisseur n'a aucun
sens physique est **0,05 nm** — moins d'un atome (§16). **La parabole est 240 millions de
fois sous ce seuil.**

🔑 **Et ça éclaire un chiffre du §12.1.** L'invariance de POEM y était mesurée à
**2,19e-10 nm** — le même ordre, exactement. **Ce n'était pas la limite de POEM qu'on
mesurait, c'était celle de la parabole.** Et elle est sans conséquence.

Gain en vitesse : 3 points sur ~130 par couche, soit **~2 %**. Gain en exactitude :
**nul en pratique**. ❌ Fermé.

#### 2. `dT/dd` analytique — hors de la boucle chaude, et déplacerait tous les chiffres

`compute_dT_dd_kernel` fait une différence centrée, 2 évaluations par couche, dans
`_compute_dT_dd_per_layer` — appelé **une fois par stratégie, pas par tirage**. Son erreur
est en `O(h²)`, négligeable devant le bruit qu'elle sert justement à dimensionner
(`signal_noise_scale = |dT_dd| · noise_val`).

La rendre analytique **changerait `signal_noise_scale`, donc tous les résultats**, pour un
gain nul des deux côtés. ❌ Fermé.

#### 3. 🔴 Les points tournants NE PEUVENT PAS être résolus analytiquement — et c'est structurel

C'est l'argument le plus important des trois, parce qu'il ne se voit pas.

Le bruit est ajouté à `Ts_r` (`certus_strat_growth.py:886` et `:996`), et
`detect_turning_points` opère **sur `Ts_r`**, donc sur des données **bruitées**. Ce n'est
pas un chercheur d'extremum : c'est une **machine à hystérésis** qui émet quand le signal
recule de plus qu'un seuil. Elle modélise ce que l'instrument **croit voir**, pas ce que
la courbe **est**.

> `tan 2δ = R/Q` donne l'extremum **mathématique de la courbe propre**.
> Le détecteur donne ce que **la machine voit dans un signal bruité**.
> **L'écart entre les deux EST le phénomène** que §12.2 a mis trois mesures à caractériser.

Le remplacer par une résolution analytique **supprimerait purement et simplement la
fabrication de faux points tournants** — le mécanisme de plantage dominant, **79 %** des
échecs mesurés en §17-36. ❌ Fermé, définitivement.

#### Ce qu'il faut retenir de l'ensemble

**La forme fermée est une belle découverte qui ne rapporte presque rien**, parce que le
code qu'elle remplacerait était déjà bon : la parabole est exacte à 2e-10, la différence
centrée est sous le bruit, et le détecteur est irremplaçable par construction du modèle.

Ce qui reste acquis : **×1,20** sur le noyau, une forme fermée validée à **1,2e-15**
contre l'oracle indépendant, et la restriction 👤 `k < 1e-4` mesurée et confirmée.

### ⚡ LÀ OÙ LE TEMPS SE GAGNE VRAIMENT — et c'est déjà mesuré

📏 **D3 de la campagne du 2026-08-11** : cribler à **10 tirages au lieu de 25** rend
`n_ranked = 133` au lieu de 228, **la même gagnante** `[544, 531]`, et un `RESULT`
**bit-identique**. Ouvrir à 100 tirages ou garder 30 survivantes ne trouve rien de mieux
non plus (§17-27).

**C'est 60 % de l'étage de criblage, sans toucher une ligne de physique, et avec une
preuve expérimentale plutôt qu'une estimation.** Plus que tout ce que le noyau peut rendre.

⚠️ **Mais je ne change pas le défaut, et c'est délibéré.** La mesure porte sur **une
graine, un empilement, une configuration**. §19-4 interdit de conclure d'une mesure sur un
autre composant, et un défaut vaut pour tous les cas à venir, pas seulement pour celui-là.
`n_screen_runs = 10` est **recommandé et documenté** ; le poser par défaut demande de
l'avoir vu tenir sur au moins une seconde graine.


### La simple précision — 👤 y est favorable, et l'ordre compte

> 👤 *« Je suis favorable à ce que les calculs les plus coûteux en temps soient
> spécifiquement faits en simple précision. »*

**Ce qui la rend défendable** : la grandeur porte un bruit de `A = 5e-4`. L'erreur
relative du `float32` est ~1e-7, soit **5e-8 en absolu** sur des `T ~ 0,5` — quatre
décades sous le bruit. Même accumulée sur 48 produits matriciels, on resterait vers 1e-6.

**Ce qu'elle coûte, et il faut le savoir** : la vérification **au bit** devient
impossible (C1 et §3 reposent sur `float.hex()`), et l'oracle TMM chute de **3,3e-16 à
~1e-7** — quatre décades de sensibilité en moins, sur l'instrument même qui a démasqué
les deux bugs de signe.

⚠️ **Recommandation : sur le chemin de MONITORING seulement**, jamais sur la notation ni
sur l'oracle. Et **après** la forme fermée, jamais en même temps : la forme fermée change
ce qui est le goulot, et deux changements simultanés rendraient l'attribution impossible
(contrainte C3). Une fois la forme fermée en place, le calcul n'est plus dominé par des
produits matriciels mais par de la trigonométrie, et il faudra **remesurer** où va le
### 17-43. Découverte & validation des stratégies par blocs (6 blocs universels sur 35c et 48c)

📏 **Mesuré le 2026-08-14** : le regroupement de la surveillance optique en **6 blocs** bat
invariablement la surveillance monocouche historique ($N$ longueurs d'onde pour $N$ couches)
sur les deux composants de référence, avec un **taux de plantage nul ($0{,}0\,\%$)** :

| Composant | Stratégie Monocouche ($N$ blocs) | Champion 6 Blocs | Gain Précision | Mouvements Monochromateur |
|---|:---:|:---:|:---:|:---:|
| **48c Dichroïque** | RMSE = `0.01803` ($\text{SEEL} = 0{,}27\text{ nm}$) | **RMSE = `0.00745` ($\text{SEEL} = 0{,}17\text{ nm}$)** | **$+58{,}7\,\%$** | $5$ au lieu de $47$ ($-89\,\%$) |
| **35c Passe-Bande** | RMSE = `0.08496` ($\text{SEEL} = 0{,}58\text{ nm}$) | **RMSE = `0.05819` ($\text{SEEL} = 0{,}48\text{ nm}$)** | **$+31{,}5\,\%$** | $5$ au lieu de $34$ ($-85\,\%$) |

**Mécanisme physique fondamental :**
1. **Mémoire de phase POEM** : le maintien de la même longueur d'onde sur 5 à 8 couches consécutives
   permet à POEM d'utiliser les extremums précédents comme repères absolus de phase pour corriger en
   direct les incertitudes d'indice et les dérives de vitesse sans discontinuité.
2. **Cumul des pentes** : les couches quart-d'onde à dérivée faible sont amplifiées par l'interférence
   globale du sous-empilement.

---

### 17-46. Benchmark consolidé des 3 Modes d'Exécution (FAST, PREMIUM, DEEP) & SEEL à 0,01 nm

📏 **Mesuré le 2026-08-14** sur le banc headless de référence :

```
================================================================================
TABLEAU RÉCAPITULATIF DES 3 MODES SUR 35C ET 48C (SEEL RÉSOLUTION 0,01 NM)
================================================================================
Composant          Mode       Budget MC & Largeur    Durée   Optimum   RMSE P95   SEEL (0,01nm)   Plantage   Total Stratégies
48c (Dichroïque)   FAST       N=50, top_k=20        371 s    6 blocs   0.00745       0,17 nm        0,0 %          384
48c (Dichroïque)   PREMIUM    N=150, top_k=40       570 s    6 blocs   0.00764       0,17 nm        0,0 %          650
48c (Dichroïque)   DEEP       N=300, top_k=100      965 s    6 blocs   0.00746       0,17 nm        0,0 %          848

35c (Passe-bande)  FAST       N=50, top_k=20        166 s    5 blocs   0.06893       0,53 nm        0,0 %          298
35c (Passe-bande)  PREMIUM    N=150, top_k=40       248 s    5 blocs   0.06201       0,50 nm        0,0 %          519
35c (Passe-bande)  DEEP       N=300, top_k=100      431 s    6 blocs   0.05819       0,48 nm        0,0 %         1007
```

**Règles de calcul du SEEL :**
- Formule : $\text{SEEL} = 2 \times \sqrt{\text{score}}$
- Résolution standard : **$0{,}01\text{ nm}$ près** (`SEEL_RESOLUTION_NM = 0.005` dans `certus_strat_ranking.py`).

---

## 18. Autres chantiers ouverts

- 🔵 **PROPOSÉ PAR 👤 le 2026-08-15 — compter en Phase A les λ qui offrent un point tournant.**

  > 👤 : *« en routine, le code pourrait ou même devrait, en Phase A, regarder pour une couche
  > i le nombre de λ permettant de passer un turning point avec le swing minimal »*.

  🔴 **Ce n'est pas ce que Phase A fait aujourd'hui, et l'écart est réel.** Le filtre actuel
  (`certus_strat_service.py:868`) retient une λ candidate sur **deux critères d'amplitude** :

  | | |
  |---|---|
  | `dynamics ≥ dynamics_threshold` (0,025) | le **swing** crête-à-crête `T_max − T_min` pendant la croissance |
  | `t_min ≥ min_transmission_floor` (0,10) | le signal ne plonge pas sous le plancher photométrique |

  ⚠️ **Aucun des deux ne teste l'EXISTENCE d'un point tournant.** Une couche dont `T` croît de
  façon monotone pendant toute sa croissance a un swing parfaitement acceptable et **aucun
  extremum sur lequel s'arrêter**. Elle passe le filtre et n'offre pourtant pas de point
  d'arrêt. C'est exactement la distinction de §7 (QWOT ≠ point tournant).

  🟢 **Et la donnée nécessaire est déjà là** — c'est ce qui rend l'action bon marché.
  `prepare_dynamics_data_kernel` (`certus_strat_growth.py:1760`) calcule déjà `M_before`,
  `n_layer` et `n_sub` pour **chaque couche × chaque λ candidate**. La forme fermée
  `layer_scan_coeffs` en tire `Q` et `R` en O(1), et le compte de points tournants s'écrit

      k1 - k0 + 1   avec   delta_TP = ½·arctan2(R, Q) + k·π/2   dans ]0, δ_final]

  C'est **une dizaine de lignes**, sans nouveau parcours de l'empilement. Prototype déjà
  écrit et validé : `scripts/probe_turning_points.py`.

  **Ce que ça donnerait** : une largeur de monitorabilité par couche — *combien de λ offrent
  au moins un point tournant ET un swing suffisant*. C'est un diagnostic que rien ne produit
  aujourd'hui, et un candidat naturel pour décider où changer de verre témoin (§25.4), là où
  `S(p−1)` a échoué.

  📏 Mesuré sur le random75, médiane des λ offrant un point tournant, par couche :
  **49/61 à ×0,5**, **61/61 à ×1, ×1,5 et ×2**.

  ##### 🔵 Et la « phase intermédiaire » proposée dans la foulée — elle existe déjà

  > 👤 : *« entre la phase A et la phase B il pourrait y avoir une phase intermédiaire qui
  > cherche à minimiser les changements de longueur d'onde pour les couches admissibles en
  > turning point et dynamique »*.

  🟢 **La moitié « minimiser les changements de λ » est déjà faite, et c'est la DP de Phase B.**
  `_find_k_best_groupings_dp_sequential` (`certus_strat_ranking.py:154`) reçoit
  `cost_map[couche][λ] → coût` et `_compute_valid_blocks_kernel` cherche les blocs où **une
  seule λ sert TOUTES les couches du bloc**. C'est exactement l'optimisation décrite, elle est
  exacte (programmation dynamique, pas une heuristique), et elle rend les `top_k` meilleurs
  groupements.

  🔴 **Ce qui manque n'est donc pas la phase, c'est le CRITÈRE D'ADMISSIBILITÉ qu'elle
  consomme.** `cost_map` est bâti sur les candidates de Phase A, filtrées sur le swing et le
  plancher photométrique — **jamais sur l'existence d'un point tournant**.

  🔑 **Les deux propositions de 👤 se réduisent donc à UN seul changement** : ajouter le
  comptage de points tournants au filtre de candidature. La DP existante minimisera alors les
  changements de λ **sur le bon ensemble**, sans qu'on écrive de phase nouvelle.

  ⚠️ **Mais pas en exclusion sèche, et voici pourquoi.** Une couche sans point tournant reste
  déposable : elle s'arrête sur un **niveau absolu**, ou en **Rate**. Ce qu'elle perd, c'est
  l'ancre de phase auto-référencée dont POEM a besoin. Le compte de points tournants doit donc
  entrer comme **coût**, pas comme couperet — sinon on interdit des stratégies qui marchent.
  🔴 Et il y a un second effet, dans l'autre sens : `CRASH_TP_MISCOUNT` sanctionne une
  stratégie qui attend *N* points tournants et en voit *N ± 1*. **Trop** de points tournants
  proches est donc aussi un risque, pas seulement trop peu. Le coût doit être **non
  monotone**, et c'est une raison de plus pour le mesurer avant de le poser.

- 🟢 **NON URGENT — la Phase A ignore qu'une couche Rate efface l'historique.**
  *Établi le 2026-08-15, chiffré, et délibérément repoussé.*

  La Phase A **suit** la continuation de bloc (`block_start_running`, passé aux candidates
  via `phase_a_block_start`, `certus_strat_objectives.py:287`) : elle sait donc qu'une λ
  inchangée conserve les ancres. **Mais elle ne connaît pas `rate_flags`.** Or une couche
  Rate efface l'historique **exactement comme un changement de λ** — le noyau l'applique
  (`certus_strat_batch.py`, frontière de bloc forcée), la Phase A ne le prévoit pas.

  **Conséquence, et elle est bornée à UNE couche** : la λ de la couche `i+1` a été choisie en
  supposant un historique hérité que la couche `i` en Rate a détruit. Les couches `i+2` et
  suivantes héritent normalement du nouveau bloc et ne sont pas concernées.

  ⚠️ **Le score, lui, reste honnête** : la simulation paie bien la pénalité de rupture de
  bloc. Ce n'est pas une erreur de mesure, seulement un choix de λ sous-optimal sur une
  couche. Et une seule couche Rate par variante, par construction — l'effet ne se cumule pas.

  📏 **L'empirique dit que ça ne bloque rien** : sur le 99c, la gagnante était
  `RATE_L25(from 900000037)`. Les variantes Rate gagnent **malgré** cette sous-optimalité.

  **Le correctif tient en deux lignes** : passer `rate_flags` à la Phase A et forcer
  `block_start_running = i_layer` après une couche Rate, même règle que pour un changement de
  λ. 👤 : *« relancer la Phase A ne changerait pas grand-chose, on est dans la subtilité »* —
  c'est exact, et c'est pourquoi ce point passe **après** tout chantier qui touche au SEEL.

  🔑 **Rappel de 👤 sur le Rate, à ne pas perdre** : le facteur est calculé sur les couches
  **de même nature déposées AVANT** la couche `i` (`certus_strat_growth.py:634`, boucle
  `range(i_layer-2, -1, -2)`). Donc **`rate(i)` et `rate(j)` ont des facteurs différents même
  sur un matériau identique.** Ce n'est pas une constante par matériau.

- **Isolation des tests** — une fuite `sys.modules` faisait échouer en sélection large des
  tests qui passent isolément. Cause racine corrigée, audit restant :
  [`docs/REPRISE_TESTS_ISOLATION.md`](docs/REPRISE_TESTS_ISOLATION.md).
- **Performance** — 📏 mesuré le 2026-08-04 : **il n'y a PAS de ×2 disponible** dans les
  pistes documentées. Seul gain acquis : −10 % sur STRAT. Le fossé machine va de ×1 à ×3,2
  selon les modules, pas ×7-10. [`docs/REPRISE_PERF.md`](docs/REPRISE_PERF.md) — ⚠️ ses
  **temps absolus** datent d'avant le déménagement hors Google Drive ; les *rapports* restent
  utiles, les secondes non.
- **Amélioration générale** — [`docs/PLAN_AMELIORATION.md`](docs/PLAN_AMELIORATION.md) : dette
  de lint, tests absents de la CI, six chantiers ordonnés.

### Dette de lint

```
ruff check .  (config projet)             ->  All checks passed!    (mesuré 2026-08-09)
ruff check .  (mêmes règles, sans ignore) ->  12 157 erreurs        (non remesuré)
```

**La dette est celle que masque `extend-ignore`, pas celle que `ruff` rapporte.**

Les plus dangereuses masquées : **F822 (202)** — `__all__` référençant des noms inexistants,
concentrés sur 4 fichiers UI ; tout `import *` sur eux lève `AttributeError`. **F821 (67)**,
dont 3 réels dans `certus/physics/gradient_analytic.py`. **F401 (5 473)** · **F403/F405
(80 / 3 161)**.

### CI

248 fichiers `.py` sous `tests/` (241 `test_*.py`), 2 299 tests collectés.
`release-windows.yml:93` lance `pytest tests/oracle/ tests/unit/`, `tests.yml` lance
`tests/oracle/` puis `tests/`. **`lint.yml` n'exécute aucun test** — c'est le chantier qui
reste.

🔴 La branche de travail `refactor-corridors-mixins` est très en avance sur `main` (dernier
commit `main` : 2026-04-27) : **ces commits n'ont jamais été validés par la CI sur `main`.**

## 19. Règles de tenue de ce document

1. **Toute affirmation chiffrée porte sa commande et sa sortie**, collée sans retouche.
2. **Si tu n'as pas fait, dis-le.** Une ligne « je n'ai pas réussi, voici l'erreur » vaut
   beaucoup plus qu'une invention : celui qui te relit la détectera en essayant de la
   reproduire, et perdra confiance dans **tout** le reste.
3. **« Ce dont je ne suis pas sûr : rien » est presque toujours faux.**
4. **Ne conclus jamais d'une mesure sur un autre composant** que le 48 couches.
5. **Un run mesuré doit avoir la machine pour lui seul.** Un banc lancé pendant qu'autre
   chose tourne rend `RESULT=None` au bout de 1800 s, ce qui ressemble à un résultat. C'est
   arrivé le 2026-08-08.
6. **Vérifie la non-régression au BIT, pas « aux tests près »** — voir §3.
7. **Ce document ne grossit pas indéfiniment.** Ce qui est fait en sort. Ce qui se contredit
   en sort. `git log` garde tout.

## 20. Protocole de re-vérification — comment auditer le travail d'un autre agent

**Un rapport est une déclaration, pas une preuve.** Ce protocole consiste à essayer de
**casser** chaque déclaration, pas à la confirmer. Appliqué deux fois, il a trouvé quatre
affirmations fausses la première fois et neuf la seconde (§17) — il fonctionne.

⚠️ **Il a ses limites, et il faut les dire.** Les deux passes ont vérifié des **diffs, du
code et des artefacts**. Aucune des deux n'a relancé une mesure au banc. Une déclaration
chiffrée n'est donc réfutée que lorsqu'un **artefact la contredit** ; celles qui n'ont
produit aucun artefact ne sont ni confirmées ni réfutées — elles sont **non vérifiées**, ce
qui est un troisième état qu'il ne faut pas confondre avec « tient ».

### Le repère git

L'état du dépôt avant l'intervention de la session précédente porte l'étiquette
**`depart-gemini`** (`f816767`, 2026-08-07). Elle est vivante — vérifiée le 2026-08-08, 36
commits depuis.

```bat
git log --oneline --stat depart-gemini..HEAD
```

**Ne la supprime pas et ne la déplace pas.** Si `git log depart-gemini..HEAD` répond
`unknown revision`, arrête-toi et signale-le : sans ce repère, personne ne peut plus séparer
le travail d'une session de ce qui existait avant.

Pour remesurer l'état de départ sans perdre l'état courant :

```bat
git worktree add C:\dev\gemini-baseline depart-gemini
:: ... mesures ...
git worktree remove C:\dev\gemini-baseline
```

### Les trois questions, dans cet ordre

1. **Le diff correspond-il à ce qui est déclaré ?** (git ne ment pas)
2. **La mesure citée se reproduit-elle ?** (relancer la commande)
3. **La conclusion suit-elle de la mesure ?** ← **c'est là que ça casse le plus souvent**

Une déclaration qui échoue à l'une des trois est **annulée**, pas retouchée. Reviens en
arrière, puis refais : un correctif posé sur une base non vérifiée hérite de son incertitude.

| Ce que tu trouves | Ce que ça veut dire |
|---|---|
| Un commit non déclaré | Suspect par défaut : lis son diff en entier avant toute autre chose. |
| Une déclaration sans commit | Le travail n'a pas été committé, ou n'a pas eu lieu. |
| Un commit qui touche plus de fichiers que déclaré | Le périmètre a débordé. Regarde ce qui a été emporté. |
| Un commit sur `pyproject.toml` | Vérifie **immédiatement** que `extend-ignore` n'a fait que rétrécir. |
| Un commit sur `JSON-strat-example.json` | **Toutes les mesures postérieures sont nulles** jusqu'à preuve du contraire. |

### Les cinq contrôles qui attrapent l'essentiel

1. **Tout nouveau paramètre est-il vraiment inerte par défaut ?** Égalité **exacte**, pas
   `allclose` — mais **sur l'empreinte du noyau en mono-thread (A5), jamais sur le `RESULT`
   du banc**, qui a ~3e-11 de gigue irréductible (§3). 🔴 **Une version antérieure de ce
   contrôle disait « au-delà de 1e-12, ce n'est pas numba » et faisait comparer des `RESULT`
   de banc. C'est ainsi que le constat §17-1 a été écrit puis retiré : il accusait le code
   d'un bruit de sommation parallèle.** Le seul chiffre exploitable ici est celui du harnais.
2. **Les tests ajoutés échouent-ils sur le code d'avant ?** Copie-les dans le worktree
   baseline et lance-les. Ils **doivent** échouer. C'est le contrôle le plus rentable de la
   liste.
3. **Les grandeurs de bruit varient-elles avec le bruit ?** Divise σ par 100 : le chiffre
   doit s'effondrer.
4. **Chaque règle rejette-t-elle effectivement quelque chose ?** **Compte les rejets, ne lis
   pas le code.** Un filtre inerte ne produit aucune erreur — il produit un résultat
   plausible. C'est ainsi qu'une règle de proximité recevant une matrice de zéros n'a rien
   interdit sur 51 candidates × 48 couches, en silence.
5. **Les conclusions dépassent-elles les mesures ?** Attrape en particulier : une conclusion
   physique tirée d'un empilement à 8 couches · une **attribution causale quand deux choses
   ont changé en même temps** · un résultat **meilleur que prévu** présenté comme un succès.

### Être juste dans le jugement

- **Un travail non fait mais déclaré comme non fait n'est pas une faute.** C'est ce qu'on
  demande. Une ligne « je n'ai pas réussi, voici l'erreur » vaut mieux qu'un contournement
  silencieux.
- **Un arrêt sur ambiguïté n'est pas une faute.** Le document ambigu est en tort.
- Une seule chose est réellement disqualifiante : **une affirmation chiffrée qui ne se
  reproduit pas.** Si tu en trouves une, cesse de faire confiance au reste et revérifie tout
  depuis git.

---

## 21. 👤 LE SECOND COMPOSANT D'ESSAI — passe-bande à trois cavités, 2026-08-11

> 👤 *« Tu vas implanter un deuxième filtre test. Ce sera un passe-bande à trois cavités, que
> l'on contrôle normalement en TPM mais qui là sera avec notre STRAT à nous ! Je propose un
> M5-2L-M5-L-M5-2L-M5-L-M5-2L-M5 centré à 632 nm et dont l'écart spectral sera mesuré sur
> 2× la bande passante environ. On garde les mêmes indices. »*
> — puis *« pour le passe-bande, le SEEL et l'écart spectral doivent être sur 600 – 660 nm »*

**Fichier** : `example/example_strat/JSON-strat-bandpass-3cav.json`

### Ce qu'il est

| | |
|---|---|
| Empilement | `M5 · 2L · M5 · L · M5 · 2L · M5 · L · M5 · 2L · M5` = **35 couches** |
| Alternance | `HLHLH…H`, parfaite — les trois cavités `2L` tombent aux indices **5, 17, 29**, tous impairs, donc **L**, ce qu'exige la convention de parité du noyau |
| Indices | **inchangés** : H 2,35 · L 1,46 · substrat 1,52 |
| `l0` | **631,93** |
| Centre à mi-hauteur | **632,00 nm** · bande **625,1 – 638,9 nm** (**13,7 nm**) |
| Pic | T = **0,9966** |
| Épaisseur totale | 3 356 nm |
| Cible spectrale et SEEL | 👤 **600 – 660 nm**, pas 1 nm — **61 points**, dont **13** dans la bande passante |
| Balayage de contrôle | **450 – 700 nm**, pas 1 nm |

🔑 **Le domaine de balayage est identique à celui du dichroïque, et ce n'est pas un détail** :
👤 *« les deux filtres sont monitorables sur le même domaine, non ? »* — oui, parce que
**c'est une propriété du monochromateur, pas du design**. Une première version portait
520 – 760 nm, calquée sur le filtre au lieu de la machine. Corrigé.

### 🔴 Le piège qui a fait rater le centrage du premier coup

Un trois-cavités a un sommet **plat et ondulé** : `T > 0,99` sur **10,4 nm**. `argmax` saute
donc d'une ondulation à l'autre selon le pas de la grille d'évaluation, et le centrage
calculé dessus est faux **sans qu'aucun contrôle ne le signale** :

```
  l0 = 632, grille 0,25 nm  ->  argmax a 637,0 nm
  l0 = 632, grille 0,05 nm  ->  argmax a 627,1 nm      <- 10 nm d'ecart, meme filtre
```

**La grandeur qui centre un passe-bande est le MILIEU DE LA BANDE À MI-HAUTEUR**, jamais
`argmax`. Sur ce critère la relation est monotone et la bissection converge :
`l0 = 631,93 → centre 632,00 nm`.

### Pourquoi ce composant apporte quelque chose que le dichroïque n'apporte pas

👤 *« que l'on contrôle normalement en TPM »* — le passe-bande est le cas d'école du
**monitoring par points tournants**, là où le dichroïque vit de niveaux intermédiaires. Les
couches `M5` sont des QWOT à λ₀ : leur signal de monitoring **passe par un extremum à
l'épaisseur visée**, ce qui est le régime où §14-5 dit que `dT/dd → 0` et où une erreur de
niveau se convertit en une grande erreur d'épaisseur.

⚠️ **La géométrie de la cible n'est PAS celle du juge de paix, et il faut le savoir avant de
comparer les deux scores.** §14 a mesuré que le dichroïque a **exactement 141 points par
bande sur 301**, d'où l'incapacité d'un RMSE uniforme à distinguer les deux bandes. Ici c'est
**13 points sur 61** dans la bande passante. **Les deux composants ne posent donc pas la même
question à la fonction objectif**, et un écart de score entre eux ne se lit pas comme un écart
de difficulté.

### 🔴 Ce que ce second composant ne change PAS

§15 reste **entier**. Deux bancs de cohérence ne font pas une validation physique : aucun des
deux n'a de dépôt réel en face. Et §19-4 continue de s'appliquer dans les deux sens — **on ne
conclut pas du passe-bande sur le dichroïque, ni l'inverse.** Ce que le second composant
permet, c'est de voir si une conclusion **survit** au changement de composant ; c'est un test
de robustesse de la conclusion, pas une corroboration de la physique.

---

### 🔴 POEM NE PEUT PAS S'ANCRER SUR LE PASSE-BANDE — et c'est structurel, 2026-08-12

> 👤 *« Je reste sur le cul pour le 35 couches. Il n'y a jamais de POEM ? »*

La gagnante du passe-bande a **35 blocs** — une λ de contrôle par couche, donc **aucun
historique hérité**. La question est légitime, et la réponse est : **POEM ne s'ancre que
sur 8 couches sur 34.** Sur les 26 autres, la machine tourne au **niveau absolu**.

#### Comment ça se mesure sans ambiguïté

Déposer la couche avec une erreur amont de 2 nm, `poem_enabled` vrai puis faux. **Si les
deux rendent la même épaisseur au bit, POEM n'a pas pu s'ancrer** — il est retombé sur le
repli. Aucune interprétation nécessaire.

```
35 couches, gagnante a 35 blocs (aucun historique)  ->  POEM s'ancre  8 / 34   (24 %)
48 couches, gagnante a  6 blocs (1er bloc = 29 couches) ->            42 / 47   (89 %)
```

#### Pourquoi — et ce n'est pas réparable sur ce composant

Sans historique, POEM doit trouver **deux points tournants dans la seule couche
courante**. `T(d)` étant un sinusoïde en `2δ` (§18ter), les extrema tombent tous les 90°,
et la phase à l'arrêt vaut

$$\delta_{\text{nom}} = \frac{2\pi n\,d_{\text{nom}}}{\lambda_{\text{mon}}}
= \frac{\pi}{2}\cdot\frac{\lambda_0}{\lambda_{\text{mon}}}
\qquad\text{pour une QWOT à }\lambda_0$$

📏 Les λ retenues donnent `λ₀/λ` entre **1,11 et 1,40** : entre **un et deux** extrema
franchis. **POEM est exactement à son seuil sur toutes les couches**, et de quel côté on
tombe est décidé par l'offset de phase du sous-empilement — d'où les 8 sur 34, sans loi
simple.

🔴 **Pour disposer de deux ancres il faudrait `λ ≤ λ₀/2 = 316 nm`. Le monochromateur ne
descend pas sous 450 nm.** C'est donc structurellement impossible, et cela explique
pourquoi ce type de filtre se contrôle normalement en **TPM** : on s'arrête *sur* le point
tournant, on ne cherche pas à en encadrer deux.

#### 🔴 Ma prédiction a échoué, et le motif de l'échec vaut d'être gardé

J'avais posé « POEM s'ancre ssi `λ₀/λ ≥ 2` ». Elle tombe juste sur **26 couches sur 34**
— et **c'est trompeur** : elle prédit « non » partout et a raison 26 fois par simple taux
de base, en se trompant sur les 8 couches qui portent toute l'information.

> **Un prédicteur constant qui a raison par taux de base n'a aucun pouvoir discriminant.**
> Lire son score global comme une validation est exactement l'auto-illusion que §20-5
> attrape. Ce qu'il faut regarder, c'est le taux sur la classe MINORITAIRE.

#### Ce qui a été écarté au passage

⚠️ **POEM n'est pas cassé.** À la couche 5 il rend `CRASH_TP_MISCOUNT`, ce qui avait l'air
d'un défaut. Vérification, à bruit nul, avec 2 nm d'erreur amont :

```
extrema geometriques avant l'arret :  reel [8, 15]      -> 2
                                   nominal [1, 8, 16]   -> 3
```

Le nominal porte un extremum **à l'indice 1**, à ~5 % de la couche ; le réel ne l'a pas.
Une erreur amont de 2 nm suffit à faire basculer un extremum qui tombe au tout début du
balayage. **Le détecteur compte juste ; ce sont les signaux qui diffèrent.** C'est une
fragilité physique réelle de POEM, pas un bug — et elle est spécifique aux couches dont le
signal démarre près d'un extremum.

#### ✅ LES TROIS LECTURES SONT TRANCHÉES — 2026-08-12

Trois explications étaient possibles et il fallait les séparer avant de croire quoi que
ce soit. Les trois tests, du moins cher au plus cher :

| lecture | verdict | ce qui l'a tranchée |
|---|---|---|
| **POEM est cassé** | ❌ | le détecteur compte juste — extrema réels `[8,15]` contre nominaux `[1,8,16]` — et POEM s'ancre sur **42/47** couches du dichroïque |
| **le repli absolu est favorisé par le retrait de l'affine** | ❌ | affine **rallumée** à 0,05/0,02 : **même gagnante à 35 blocs**, `RESULT` +0,5 % — et l'affine atteint bien le calcul, `n_ranked` tombe de 380 à 334 |
| **c'est structurel** | ✅ | `λ₀/λ ∈ [1,11 ; 1,40]` sur toutes les λ retenues, et la machine ne descend pas sous 450 nm |

🔑 **Donc c'est réel.** Sur un passe-bande à couches QWOT monitoré dans la plage de la
machine, POEM n'a **pas de prise**, et le contrôle couche par couche au niveau absolu est
la bonne réponse. Ce n'est pas la recherche qui contourne le mécanisme central : c'est le
mécanisme qui ne s'applique pas ici, et la recherche qui le trouve.

Et cela retombe sur ce que 👤 disait en posant le composant — *« un passe-bande, on le
contrôle normalement en TPM »*. On s'arrête **sur** le point tournant au lieu d'en
encadrer deux. **Le modèle l'a retrouvé seul, par une route indépendante**, ce qui est la
seule forme de corroboration dont ce projet dispose tant que §15 n'est pas fermée.

#### 🔑 Pourquoi c'est arrivé MAINTENANT

Deux changements du 2026-08-12 poussent dans le même sens :

1. **La distorsion affine est éteinte** (§12.1bis) — or c'était le handicap du repli
   absolu, la seule branche que §12.1 démontre non invariante. Il a cessé d'être pénalisé.
2. **Le biais de fente pénalise les ancres héritées** (§18bis) — chaque couche
   d'historique porte le biais de *sa* courbure, pas de celle de la couche en cours.

**La recherche a exploité les deux.** Ce n'est pas une anomalie : c'est le modèle qui,
devenu plus fidèle, désigne une autre stratégie de contrôle.

⚠️ **Ce que cela n'établit PAS.** Que le niveau absolu soit *bon* — seulement qu'il est
meilleur que POEM **dans ce modèle-ci, sur ce composant-ci**. Il n'a aucune
auto-compensation des erreurs accumulées, et il reste exposé à la courbure photométrique
qui, elle, n'est pas affine. §15 s'applique en entier : rien de ceci n'est validé contre un
dépôt réel.

---

### 🔑 D'OÙ VIENT L'ERREUR — le profil d'ablation, 2026-08-12

> 👤 *« Plein de défauts ou de biais font qu'on obtient un SEEL assez loin de 0. J'aimerais
> savoir, dans les deux cas, quel est le défaut le plus problématique. »* — puis *« pour
> chacune des 20 meilleures stratégies, faire un classement de l'influence de chaque source
> de défaut. Cela permettra à l'utilisateur de mieux comprendre d'où viennent les
> problèmes. »*

On éteint chaque source à tour de rôle et on relit le score. La contribution est
`1 − score_sans / score_avec`.

📏 **Mesuré sur les gagnantes des repères N = 300 :**

| on retire… | dichroïque 48c | passe-bande 35c |
|---|---|---|
| **le corridor d'indice** | **69 %** | 15 % |
| le biais de fente | 0 % | **16 %** |
| la courbure photométrique | 1 % | 3 % |
| le bruit de lecture | ~0 % | ~0 % |

🔑 **Le même modèle rend deux diagnostics OPPOSÉS selon le composant.** Sur le dichroïque
une source écrase tout ; sur le passe-bande fente et corridor se partagent la charge et
personne ne domine. **C'est pour ça que le profil est par stratégie et non global** : une
note générale du type « le corridor domine » serait fausse une fois sur deux.

🟢 **Et le bruit de lecture ne pèse rien nulle part**, ce qui est le contrôle du montage :
c'est du **bruit**, il s'annule sur les tirages, là où les trois autres sont des **biais**
qui poussent tous les tirages du même côté. **Une ablation où le bruit sortirait dominant
signalerait une erreur de montage, pas un résultat.**

#### 🔴 Ce que ces nombres NE SONT PAS

**Ils ne s'additionnent pas à 100 %.** Les sources interagissent — le corridor fausse
l'épaisseur **et** l'indice du filtre fini, la fente déplace l'ancre que POEM utilisera
ensuite — donc en éteindre deux ne retire pas la somme de leurs deux parts. Ce sont des
**dérivées**, pas un partage de gâteau.

⚠️ Et pour le corridor la part affichée est plutôt une **sous-estimation** : il agit deux
fois, alors que la métrique d'épaisseur ne voit que le premier des deux effets.

#### 🔑 LE CORRIDOR SATURE — et c'est ce qui répond vraiment à la question

> 👤 *« Ça m'embête de diminuer les erreurs sur les indices car je sais que cette valeur
> est plausible. »*

📏 Balayage sur la gagnante du dichroïque :

```
corridor    erreur d'epaisseur RMS
0,0000              1,443 nm
0,0025              4,179 nm     <- presque tout le dommage est deja la
0,0050              4,654 nm     +11 %
0,0100              4,594 nm     SATURE
```

**Quadrupler la perturbation de 0,0025 à 0,010 ne coûte que 10 %.** Donc **abaisser la
spécification à 0,0025 ne gagnerait que 10 %** : le scrupule de 👤 était fondé, et pour une
raison plus forte que celle avancée — ce n'est pas seulement que 0,005 est plausible, c'est
qu'**y toucher ne servirait à rien**.

Sur le passe-bande la réponse est régulière : `+1,6 % · +17 % · +23 %`, **pas de
saturation**.

> **Deux régimes.** Le dichroïque a un **seuil** : au-delà d'une petite incertitude
> d'indice la compensation POEM décroche, et ce qui suit ne change plus grand-chose. Le
> passe-bande se dégrade proportionnellement.

#### 🔴 Ce que je n'ai PAS mesuré, et qu'il ne faut pas croire mesuré

**L'asymétrie H / L.** §12.3 note que 0,005 en absolu vaut 0,21 % sur H et **0,34 % sur L**
— rapport 1,6. J'ai voulu la mesurer et **je n'ai pas pu** : le corridor perturbe les deux
matériaux ensemble et aucun paramètre ne les sépare. Le balayage ci-dessus mesure donc
l'**amplitude**, pas la **répartition**. La question reste ouverte, et elle demanderait un
tirage par matériau exposé séparément.

#### Ce que ça donne comme conseil, et il est actionnable

Sur le dichroïque, **69 % de l'erreur vient de l'incertitude d'indice**. Autrement dit :

> **Raffiner le monitoring sur ce composant ne rapportera presque rien. C'est la
> connaissance des indices qui limite** — et une campagne de détermination d'indice
> attaquerait les 69 %.

⚠️ **Et les 31 % restants ne sont attribués à RIEN — ne laisse personne les nommer.** Une
version antérieure de cette phrase disait *« là où POEM, la fente et le lissage se
partagent les 31 % restants »*, ce qui invente un partage deux fois : la fente mesure
**0 %** sur ce composant, et le lissage de lecture est **éteint** par décision, donc il ne
peut rien peser du tout. Les quatre ablations totalisent ~70 % ; ce qui reste est de
l'**interaction entre sources et des mécanismes qu'aucune ablation n'isole**. C'est le même
avertissement que ci-dessus — ce sont des dérivées, pas des parts — et il vaut aussi pour
le résidu.

C'est le genre de chose qu'un outil doit dire à son utilisateur, et STRAT ne le disait pas.

#### Comment c'est calculé

`_ablation_profile`, sur les **20 meilleures**, **après** le classement — jamais avant,
pour qu'un diagnostic ne puisse pas influencer l'ordre. À **64 tirages**, volontairement
moins que le classement : on mesure une contribution **relative**, pas un score. C'est
assez pour séparer une source à 60 % d'une source à 2 %, et ce ne serait pas assez pour
départager deux stratégies — ce qu'on ne fait pas ici.

Le résultat remonte dans le rapport de sonde sous `ablation`, et dans le tableau de
l'interface sous la colonne **« Dominant defect »**, l'info-bulle portant le classement
complet et les deux avertissements ci-dessus.

---

## 22. La grille des λ de contrôle — 1 nm contre 2 nm, enquête du 2026-08-12

> 👤 *« Si jamais on impose une grille de 2 nm, est-ce qu'on va réellement louper de
> meilleures stratégies ? Si les top meilleures stratégies sont quasi aussi bonnes, on
> pourra zapper la grille 1 nm au profit du 2 nm et gagner du temps. »*

⚠️ **§13 porte une décision « tranchée, ne la rouvre pas » en faveur du 1 nm.** Elle
s'appuie sur quatre chiffres de 2026-08-08, que §13 marque lui-même comme **historiques** :
antérieurs à A10, à la correction d'enveloppe du corridor, et surtout à la modélisation de
la fente. §9bis pose la règle de réouverture : *« on ne rouvre que si une MESURE la
contredit, pas un raisonnement »*. C'est bien une mesure qui la rouvre — le biais de fente.

### Ce qui est mesuré

📏 **La grille 2 nm est exactement l'ensemble des λ PAIRES** — `scan_wl_min = 450`, donc
126 candidates contre 251. Vérifié dans le code (`arange_inclusive`), pas supposé.

📏 **Le test qui compte, sur le run de référence.** La classe d'équivalence SEEL de la
gagnante (SEEL quantifié à 0,1 nm, demi-largeur `max(0,05 ; 0,06 × SEEL)`) contient
**9 stratégies, dont 3 entièrement PAIRES**, toutes à plantage 0,000 et SEEL 0,3 nm. Le
départage secondaire de §14, le rendement, ne les sépare pas non plus. **Une grille 2 nm
aurait trouvé un ex æquo au sens exact de la règle.**

📏 **Et sous la règle de tri de §14, la première est DÉJÀ paire** : `[544, 506]` sur le run
de référence, `[544, 462]` sur l'unique run portant le biais de fente. Ce critère n'a pas
été choisi après coup — il est écrit dans l'artefact par le code, sous `ranking_seel_rule`.

📏 **Contrôle du Piège 1 : POSITIF, et il faut le dire.** Le pas de 1 nm porte une
information **réelle**. L'écart entre `[544,531]` et `[544,532]` **converge** vers ~10 %
pour N ≥ 100 — il ne se dissout pas quand on approfondit — et vaut **3 σ à N = 1200**. Le
couple 452/453 est ordonné **dans le même sens sur trois graines indépendantes**.
🔑 **Mais cette information est plus fine que la limite de mesure** : 5 couples sur 6
tombent dans la même classe SEEL, l'écart valant 0,010 à 0,047 nm pour une demi-largeur de
0,050 nm. On mesure quelque chose de vrai que la règle de décision déclare, à juste titre,
indistinguable.

### 🔴 La limite qui domine tout le reste — ne pas conclure sans elle

**Le sous-ensemble pair d'un classement à 1 nm n'est PAS un run à 2 nm.** Mesuré dans le
code : la mutation ELITE porte sur l'**indice** de grille (`idx_wl = nearest + delta`), donc
un vrai run à 2 nm passerait **100 %** de son budget dans le sous-espace pair, alors que le
run à 1 nm n'y est passé qu'incidemment — **4,5 %** de ses stratégies classées sont
toutes-paires. Tout ce qui précède est donc une **borne PESSIMISTE**, jamais une estimation.
Et elle n'est solide qu'à **2 blocs** : dès 3 blocs le sous-espace pair est sous-échantillonné
d'un facteur 3, ce qui rend les régimes corridor > 0 **indécidables** par cette voie.

⚠️ **Zéro artefact pour le passe-bande.** Rien ici ne dit quoi que ce soit du second
composant — et c'est le plus exposé, sa période d'ondulation valant **5,0 nm** contre 7,2 pour
le dichroïque, donc une fente de 2 nm y moyenne une fraction plus grande d'ondulation.

⚠️ **Un seul artefact sur 64 porte le biais de fente**, à N = 12 contre 150, et il change
**deux choses à la fois** par rapport à la référence. Contrainte C3 : rien n'y est attribuable.

### Le coût, et ce qui n'est pas mesuré

| | |
|---|---|
| Candidates | **251 → 126**, exact |
| Profils de fente en Phase A | **12 048 → 6 048**, soit **65 s → 32 s** (comptage × 5,4 ms mesuré) |
| Part de la Phase A dans un run | ~68 % (§18ter) |
| **Rapport de temps réel de la Phase A** | 🔴 **NON MESURÉ.** Deux passes concurrentes ont rendu ×3,07 puis ×1,41 : machine occupée, chiffre inexploitable. Halver les candidates ne halve pas forcément un noyau `prange`, dont le remplissage se dégrade à faible charge. |

### 🔑 Le critère de décision, posé À L'AVANCE

> **On adopte 2 nm si et seulement si**, sur les **deux** composants et **au moins deux**
> graines, la gagnante du run à 2 nm tombe dans la **classe d'équivalence SEEL** de la
> gagnante du run à 1 nm, **et** que son rendement ne soit pas inférieur.

**8 runs** : 2 composants × 2 graines × 2 grilles, biais de fente actif, tout le reste neutre.
🔴 **Comparer deux `RESULT` bruts départagerait du bruit** — §17-26. C'est la classe qui décide.

---

## 23. 📏 LA PROFONDEUR MONTE-CARLO — campagne du 2026-08-12, et elle répond autre chose

> 👤 *« J'aimerais une courbe ou un tableau entre le nombre de samples (50, 150, 300, 500)
> et le temps d'exécution pour le 35c puis le 48c. Du coup, après, je choisirai
> définitivement le nombre d'échantillons. »*

**8 runs, `run_campaign.py n`, tous `OK`, tous sur le même état du code.** Les durées du
journal `probe_runs.tsv` n'ont **pas** été réutilisées : elles s'étalent sur plusieurs états
du code, et §17-7 vaut pour les secondes comme pour les résultats.

### Le coût

| N | 48 couches | 35 couches |
|---|---|---|
| 50 | 21,0 min | 7,6 min |
| **150** | **26,1 min** | **9,0 min** |
| 300 | 27,5 min | 10,5 min |
| 500 | 36,6 min | 15,1 min |

```
48 couches : part FIXE 19,8 min  +  1,94 s par tirage
35 couches : part FIXE  6,4 min  +  0,98 s par tirage
```

⚠️ **Lis la PENTE, jamais les totaux.** La dispersion run à run vaut ±1,9 min sur le
dichroïque : le pas 150→300 mesuré (+1,4 min) tient dedans alors que l'ajustement donne
+4,8 min. La part **fixe** — Phase A, DP, et l'ablation qui tourne à 64 tirages
constants — domine tout.

### 🔑 Et ce que la profondeur achète n'est pas ce qu'on croit

Sur un facteur **dix** de profondeur :

| | SEEL de la gagnante | identité de la gagnante | plantage |
|---|---|---|---|
| **48c** | 0,587 · 0,570 · 0,583 · 0,583 nm → **±1,5 %** | **change à chaque profondeur** | 0,000 partout |
| **35c** | 1,154 · 1,406 · 1,371 · 1,154 nm → ±9,8 % | 37172 · 35838 · 35838 · 37413 | 0,000 partout |

Entre N = 300 et N = 500, la classe d'équivalence SEEL ne partage que **2 membres sur 5**.

> **La profondeur achète de la précision sur un nombre déjà précis, et elle ne peut pas
> acheter ce qui bouge réellement.**

Ce n'est pas un défaut de la mesure, **c'est le résultat** : les stratégies de tête sont
réellement **interchangeables** — même SEEL, même rendement de 100 %. Il n'y a rien à
départager, et c'est précisément pourquoi §14 prescrit de déclarer l'égalité au lieu
d'acheter des tirages. §17-26 le disait sur les scores ; ceci le dit sur la **réponse**.

### 🔒 LA RECOMMANDATION — N = 300, posé le 2026-08-13

🔴 **Et le critère n'est PAS celui qu'on croit. Ne le rejuge pas sur la précision du
score.** Ma première recommandation était N = 150, sur ce critère-là, et elle était juste
sur ce critère : le SEEL est stable à ±1,5 % dès N = 50, donc la profondeur n'y sert à rien.

**Ce qui décide, c'est le filtre de plantage.**

⚠️ **Nuance ajoutée après validation du correctif 1, et elle affaiblit l'argument — ne la
saute pas.** Une version antérieure disait que le filtre gouverne *quelles stratégies
existent*. **Ce n'était vrai qu'avant le correctif 1.** Depuis, la population est fixée par
le criblage : le filtre de la passe complète ne gouverne plus que **ce qui figure au
classement final**, c'est-à-dire la liste dans laquelle l'utilisateur choisit. Une bonne
stratégie rejetée par malchance n'est plus perdue pour la recherche — seulement pour le
tableau. C'est moins grave, et cela reste un défaut.

| N | bonne à 3 % rejetée **à tort** | mauvaise à 7 % qui **passe** | repêchées au classement |
|---|---|---|---|
| 50 | **18,9 %** | **31,1 %** | **24 %** (83/343) |
| 150 | 8,3 % | 16,9 % | — |
| **300** | **3,9 %** | **6,5 %** | **8 %** (19/229) |
| 500 | 1,0 % | 2,8 % | 7 % (19/284) |

**Le genou est à 300.** 150 → 300 divise par deux les deux erreurs du filtre et fait tomber
le repêchage de 24 % à 8 %, pour **+7 min sur les deux composants réunis** (41 contre 33) —
la part fixe domine tellement que la profondeur est bon marché. 300 → 500 coûte +10 min de
plus et ne gagne presque rien.

⚠️ **Ce chiffre est conditionné au correctif 2 (§23bis), qui n'est PAS fait.** Une fois le
seuil porté sur une borne de confiance, une profondeur faible cessera de rejeter à tort et
deviendra seulement **permissive**. Le choix redeviendra une question de finesse, et 150
pourrait suffire de nouveau. **Ça se remesurera, ça ne se déduira pas.**

📏 Posé dans les deux JSON le 2026-08-13 : `robustness_num_runs = 300`.

### 🔴 POURQUOI LE NOMBRE DE STRATÉGIES CLASSÉES VARIE — élucidé le 2026-08-13

Il varie de **229 à 376** entre les quatre profondeurs. Le criblage, lui, est **rigoureusement
identique** : 905 stratégies criblées, même découpage bloc par bloc, aux quatre profondeurs.
Ce n'est donc pas le criblage. La chaîne est la suivante, et elle a trois maillons.

#### Maillon 1 — la passe COMPLÈTE alimente la recherche du nombre de blocs suivant

`certus_strat_workers.py:1292` : les résultats de la passe complète — celle qui tourne à
`N` — passent par `derive_strategies_exhaustive(..., top_k_parents=20)`, et deviennent les
**candidates héritées** du nombre de blocs suivant. **`N` atteint donc la population, par
héritage.** Ce n'est écrit nulle part et personne ne l'avait vu.

#### Maillon 2 — le filtre de plantage compare un taux ESTIMÉ à un seuil FIXE

`certus_strat_robustness.py:2018` :

```python
if crash_rate_max >= CRASH_RATE_TOLERANCE:   # 0,05
    final_score = float("inf")               # -> jetee par _filter_finite_scores
```

Le taux est estimé sur **`N` tirages**. Sa sensibilité dépend donc de `N` :

| vrai plantage | rejetée à N=50 | N=150 | N=300 | N=500 |
|---|---|---|---|---|
| 3 % — **bonne**, sous le seuil | **18,9 %** ❌ | 8,3 % | 3,9 % | 1,0 % |
| 7 % — mauvaise | **68,9 %** | 83,1 % | 93,5 % | **97,2 %** |
| 10 % — très mauvaise | **88,8 %** | 98,6 % | 99,9 % | 100 % |

🔴 **À N = 50, près d'un tiers des stratégies qui plantent réellement 7 % du temps passent le
filtre** — et deviennent parents héritées. Et une bonne sur cinq à 3 % est rejetée à tort.

📏 **La granularité l'explique** : à N = 50 le taux mesuré est quantifié par pas de **2 %**,
donc **aucune** stratégie ne peut se situer entre 0 et 2 %. Mesuré dans les classements :
`0 < p < 2 %` compte **0** stratégie à N = 50, contre 88 à 150 et 127 à 500. Il faut
**3 plantages sur 50** pour franchir un seuil de 5 %.

#### Maillon 3 — l'écart se compose le long de la chaîne des blocs

📏 Stratégies retenues par la passe complète, bloc par bloc :

```
N= 50 | 1:13  2:54  3:76  4:31  5:30 ...
N=150 | 1:16  2:50  3:61  4:26  5:59 ...
N=300 | 1: 9  2:10  3: 0  4:52  5:14 ...   <- ZERO au bloc 3
N=500 | 1: 9  2:10  3: 0  4:59  5:71 ...
```

Les deux premiers blocs perdent déjà 5 stratégies, le troisième s'effondre à **zéro**, et
l'écart se propage jusqu'aux deux derniers blocs où les survivantes tombent de `12, 9` à
`2, 3`.

#### 🔑 Ce qu'il faut en retenir, et c'est plus important que le décompte

> **Deux runs à profondeurs différentes ne comparent pas deux précisions sur la même
> recherche. Ils comparent DEUX RECHERCHES DIFFÉRENTES.**

Et le sens est celui-ci : **une profondeur faible propage des stratégies qui plantent
vraiment.** Ce n'est pas le filtre qui est cassé — c'est qu'à N = 50 il ne peut pas faire
son travail, et que le système ne le signale pas.

⚠️ **Conséquence sur la conclusion de la campagne** : j'avais laissé deux causes possibles à
l'instabilité de la gagnante. **Ce sont les deux**, et la seconde est identifiée. La stabilité
du SEEL à ±1,5 %, elle, n'est pas affectée : elle est mesurée sur la gagnante finale, dont le
plantage vaut 0,000 partout.

#### 🔴 Et un second constat, trouvé en chemin

**Des stratégies à 100 % de plantage figurent dans les classements**, aux quatre profondeurs.
C'est le repli obligatoire de `_filter_finite_scores` (ligne 1152) : quand **aucune** stratégie
d'un bloc ne survit au filtre, il les réinjecte toutes avec un score fini plutôt que de rendre
une liste vide. Le comportement est délibéré et documenté — mieux vaut la moins risquée que
`RESULT=None` — mais **rien dans le classement ne distingue une stratégie repêchée d'une
stratégie qui a réellement passé le filtre**. C'est le motif de §17-37 : le résultat a l'air
sain. Correctif à faire : remonter un drapeau `fallback_rescued` dans le résultat de
stratégie, comme `n_layers_forced`.

---

## 23bis. 🔴 LE CORRECTIF 2 — MESURÉ, MAIS NON CONSIGNÉ, DONC INEXPLOITABLE

🔴 **Il y a désormais TROIS états à distinguer, pas deux, et c'est tout l'objet de cette
section :** *écrit*, *mesuré*, et **mesuré-mais-non-consignable**. Le correctif 2 est dans le
troisième, qui est le plus traître, parce qu'il ressemble au second.

Le code existe et il est couvert par 37 tests unitaires. **La campagne `gate` A TOURNÉ le
2026-08-14** — 6 runs sur 6, 55 min 16 s, artefacts sur le disque. Et pourtant :

> **Rien ne dit encore que ce correctif améliore quoi que ce soit**, parce que les 6 runs sont
> sortis **FAILED** : `crash_gate_confidence` est dans `_OVERRIDES` mais **absente de
> `TRACED_KEYS`** (`scripts/probe_anchor_noise_pipeline.py`), donc la valeur a été **appliquée
> au run et jamais écrite dans `r["config"]`**. `run_campaign.py` ne peut pas vérifier que le
> run a fait ce qu'on lui demandait, et `analyse_gate.py` lit une clé absente : il est inerte.

**C'est le point 7 de §17 qui se rouvre** — *« un run qui ne consigne pas sa configuration
n'est comparable à rien »*. Répare la traçabilité **avant** de relancer : la clé dans les
**deux** listes, et dans le nom du fichier de sortie.

⚠️ **Et deux résultats de cette campagne sont à expliquer avant d'être crus** : les bras
porte-OFF et porte-armée rendent un score **bit-identique** (`0.006138704636203437`) avec des
gagnantes différentes, et le témoin C1 **n'a pas reproduit** sa référence
(`0.00611049163380679` contre `0.006151532415266679` attendu à ~1e-11). Détail et conduite à
tenir : bloc **EN COURS** en tête de document.

| | |
|---|---|
| **Le paramètre** | `crash_gate_confidence`, défaut **0,0 = inactif**. Lisible depuis le JSON, l'interface et `CERTUS_CRASH_GATE_CONF`. Valeur à armer : **0,95** |
| **Le code** | `_crash_gate_rejects` et `crash_rate_lower_bound`, dans `certus_strat_robustness.py` |
| **Les tests** | `tests/unit/test_strat_crash_gate_confidence.py`, **37 tests**, dont C1 sur quatre formes de valeur inactive |
| **La campagne** | `scripts\run_campaign.py gate` — **6 runs**, chaque bras avec son témoin. 📏 Mesurée le 2026-08-14 : **55 min 16 s**, et non ~3 h 30 (`reports/probe_runs.tsv`, colonne `run_s`). 🔴 **Les 6 runs sont sortis FAILED** pour un défaut de traçabilité : lis le bloc EN COURS en tête de document avant de la relancer. |
| **La lecture** | `scripts\analyse_gate.py` — imprime les quatre questions et **le test qui va avec chacune** |
| **L'ordre de mission** | `GEMINI_TODO.md`, réécrit pour cette campagne |

🔑 **Une propriété prouvée par test, et elle sert de garde-fou à la lecture** : la porte
armée est **toujours plus permissive**, jamais moins. La borne inférieure est sous
l'estimation ponctuelle, donc le correctif ne peut qu'**ajouter** des stratégies au
classement. **Si un bras en retire, c'est un défaut, pas un résultat.**

### Le défaut, en une ligne

`certus_strat_robustness.py:2018` compare une **estimation bruitée** à un **seuil dur** :

```python
if crash_rate_max >= CRASH_RATE_TOLERANCE:   # 0,05
    final_score = float("inf")               # -> jetee, et perdue comme parent
```

> **Un filtre dont le verdict change avec la profondeur n'est pas un filtre, c'est un
> échantillonneur.**

📏 Mesuré le 2026-08-13, probabilité de rejet selon le **vrai** taux de plantage :

| vrai taux | N=50 | N=150 | N=300 | N=500 |
|---|---|---|---|---|
| 3 % — **bonne**, sous le seuil | **18,9 %** ❌ | 8,3 % | 3,9 % | 1,0 % |
| 7 % — mauvaise | 68,9 % | 83,1 % | 93,5 % | 97,2 % |

Et au criblage, où c'est pire parce que la granularité est grossière :

| `n_screen` | plantages requis | rejet à tort à p=1 % | à p=3 % |
|---|---|---|---|
| **10** | **1 sur 10** | **9,6 %** | **26,3 %** |
| **25** (retenu) | 2 sur 25 | 2,6 % | 17,2 % |
| 50 | 3 sur 50 | 1,4 % | 18,9 % |

⚠️ **Note la colonne p = 3 % : elle ne s'améliore PAS avec la profondeur** — 26, 17, 19,
18 %. C'est inhérent au seuil dur : à 3 % on est trop près de 5 % pour qu'un comptage
tranche. **Seul le correctif 2 la traite.**

### Ce qu'il faut écrire

Ne rejeter que si l'on est **confiant** que le vrai taux dépasse la tolérance : borne
inférieure de Clopper-Pearson à 95 %. Conséquences, et elles sont toutes désirables :

- une bonne stratégie n'est **jamais** rejetée par malchance, à aucune profondeur ;
- à faible profondeur le filtre rejette peu — c'est **honnête**, on ne sait pas ;
- il se resserre tout seul quand la profondeur monte, **sans changer de règle**.

🔒 **Le seuil de 5 % ne bouge pas.** C'est le « 95 % des dépôts fonctionnent » de §8, une
spécification 👤. C'est l'**estimateur** qui est en cause, jamais la valeur.

### Les précautions

- 🔴 **Ça change tous les résultats. Ce n'est PAS un correctif C1**, et il ne faut pas
  exiger la bit-identité.
- 🔴 **Un run de validation à lui seul**, contrainte C3 — pas mélangé au correctif 1.
- ⚠️ **Le repli de `_filter_finite_scores` reste nécessaire** : la borne de confiance rejette
  moins, donc il se déclenchera moins, mais il ne devient pas inutile.
- 🔑 **Ce qu'il faut remesurer après** : le tableau de §23. Une borne de confiance rend une
  profondeur faible **sûre mais permissive** ; N = 300 pourrait redevenir surdimensionné.
  **Remesure, ne déduis pas.**

---

## 23ter. 🔒 LE CORRECTIF 1 — la recherche ne dépend plus de la profondeur de notation

**Fait le 2026-08-13.** L'invariant :

> **`N` (`robustness_num_runs`) est un réglage de MESURE. Il ne doit décider d'aucune
> candidate.**

### Ce qui a changé

`certus_strat_workers.py` : les **parents hérités** du nombre de blocs suivant sont dérivés
des **survivantes du criblage** (`screening_survivors`, à `n_screen` fixe) et non plus des
résultats de la passe complète (à `N`). Le contrat de blocs est revérifié au passage, parce
que `strategies_this_step` l'était et que ces survivantes-là ne l'étaient pas.

### 🔑 Le test qui le garde est une ÉGALITÉ

`tests/unit/test_strat_search_is_depth_independent.py`, 4 tests, dont **3 échouent sur le
code d'avant**. Ils vérifient que les parents ne viennent pas de la passe complète, que les
survivantes remontent, que le contrat est revérifié, et que **les deux appels de criblage
tournent toujours à `n_screen`** — cette dernière est un garde-fou contre une récidive par
une autre porte.

### 🔴 CE QU'IL FAUT COMPARER — et j'avais écrit la mauvaise grandeur

Une première version de cette section demandait de comparer les **stratégies retenues par
bloc**. **C'est faux, et ça aurait fait conclure à l'échec du correctif.** Ces retenues
sortent de la passe **complète**, donc elles dépendent de `N` — et c'est **normal** : le
filtre de plantage y est plus sévère à profondeur croissante. C'est de la **notation**.

| grandeur | doit-elle être N-indépendante ? | où la lire dans le log |
|---|---|---|
| **survivantes du criblage**, par bloc | ✅ **OUI** — c'est la recherche | `Full pass on N survivors` |
| **parents hérités**, par bloc | ✅ **OUI** — c'est la recherche | `Inheritance: X derived from Y` |
| stratégies **retenues**, par bloc | ❌ non, et ce serait un défaut qu'elles le soient | `Completed. N retained` |
| classement, scores, `RESULT` | ❌ non — c'est ce que `N` sert à mesurer | — |

📏 **Avant le correctif**, les survivantes divergeaient sur les deux derniers blocs :
`10 10 20 20 12 11 12 12 12 9` à N = 50 et 150, contre `... 12 12 2 3` à N = 300 et 500.

### 🟢 VALIDÉ LE 2026-08-13 — deux runs, facteur DIX de profondeur, égalité exacte

```
LA RECHERCHE — identique, et c'est une EGALITE, pas une concordance
  survivantes  N=50   [10, 10, 20, 20, 12, 11, 12, 12, 12, 9]
               N=500  [10, 10, 20, 20, 12, 11, 12, 12, 12, 9]
  heritage     identique sur les 10 blocs, au couple (derivees, parents) pres

LA NOTATION — depend de N, et ce serait un defaut sinon
  retenues     [5,12,41,31,45,42,78,0,27,19]  contre  [5,5,34,24,94,40,76,0,27,19]
  classees     300 contre 324          RESULT  +0,86 %
  SEEL         0,587 nm contre 0,582 nm    -> +/-0,4 %
```

**Avant le correctif, les deux derniers blocs tombaient de `12, 9` à `2, 3`.** Ils sont
maintenant identiques. Et `RESCUED` vaut **41 dans les deux runs** — le repêchage aussi est
devenu N-indépendant, puisqu'il dépend de la population, désormais fixe.

⚠️ **Ne lis pas les huit premiers blocs comme une confirmation** : ils étaient identiques
même avec le défaut. L'écart se **compose** le long de la chaîne d'héritage et n'apparaît
qu'aux derniers maillons. **Seuls les blocs 2 et 1 tranchent** — et c'est là que la mesure
compte.

### ⚠️ Ce que le correctif 1 a PÉRIMÉ

**§18ter recommandait `n_screen_runs = 10`, sur la foi de §17-27** — « cribler à 10 tirages
ne perd rien : 133 classées contre 228, même gagnante, `RESULT` bit-identique ». Cette
mesure a été faite quand le criblage ne choisissait que les survivantes de la passe
complète. **Il choisit désormais aussi les parents**, donc une stratégie tuée par malchance
au criblage est perdue pour tout le reste de la recherche. **La mesure ne couvre plus le
rôle. `n_screen` reste à 25** — voir le tableau de §23bis.

---

## 24. 💡 A25, A26, A27 — trois actions PRÊTES À EXÉCUTER, en attente

🔴 **CE N'EST PAS LE PROGRAMME COURANT.** Le programme courant est **§25, la multiple
testglass methodology**. Cette section était intitulée *« les trois actions suivantes »* et ne
l'était plus : requalifiée en **réserve** le 2026-08-15. Ces trois actions restent **valides,
utiles et entièrement spécifiées** — chacune donne son fichier, sa fonction, ce qu'il faut
écrire et le test qui doit échouer sur le code d'avant. Elles attendent, elles ne sont pas
périmées.

**Ce qui les motive, et qui n'a pas changé :** tout le travail des 12 et 13 août a rendu STRAT
plus **cohérent**. Rien ne l'a rendu plus **vrai**. §15 reste entier, et aucun correctif
interne n'y changera quoi que ce soit. **A25 est la seule action de ce document qui attaque
§15** — c'est ce qui lui garde sa priorité le jour où on quitte §25.

> **Chaque action donne : le fichier et la fonction exacts, ce qu'il faut écrire, le test
> qui doit ÉCHOUER sur le code d'avant, et les pièges connus.** Une seule action à la fois,
> un commit chacune — contrainte C3.

⚠️ **Ne les lance pas au banc sans avoir lu §0 et libéré la machine** (§19-5).

---

### 🔑 A25 — `sigma_rate` comme PRÉDICTION, la première grandeur vérifiable de l'extérieur

**Pourquoi en premier.** C'est la seule action de ce document qui attaque §15. Elle est
devenue possible le 2026-08-11, quand le noyau Rate a été écrit, **et personne ne l'a vu**.

Le noyau **refait le calcul de rate de la machine** au lieu de le remplacer par un tirage
(`certus_strat_growth.py:630`, `acc += d_nom_j / d_real_j` puis `a_est = acc / n_ref`).
Donc `sigma_rate` n'est plus un paramètre : c'est une **sortie**. Et 👤 a décrit ce que la
machine montre en salle — *« ±σ = 1 à 2 % »*.

#### Où, et ce qu'il faut écrire

| | |
|---|---|
| **Fichier** | `certus/core/certus_strat_robustness.py` |
| **Fonction** | `_test_strategy_robustness_task`, dans la boucle sur les niveaux de bruit |
| **Ancrage** | juste après `crashed_cells = sim_thick_batch > CRASH_SENTINEL_MIN` (~ligne 1946) |

Les deux grandeurs sont déjà là, côte à côte : `sim_thick_batch`, de forme
`(n_runs, n_layers)`, et `p_thick_nominal`. Pour chaque couche de `rate_layers`, sur les
runs **non plantés** :

```python
ratio = sim_thick_batch[ok_runs, i] / p_thick_nominal[i]   # ok_runs = ~any(crashed_cells)
sigma_rate = float(np.std(ratio))                          # dispersion RELATIVE
```

Remonter dans le résultat sous `sigma_rate_by_layer` et `sigma_rate_max`. La sonde
l'affiche à côté de `RESCUED=`.

#### Vérification

| # | Test | Attendu |
|---|---|---|
| 1 | Une stratégie **sans** couche Rate | `sigma_rate_max` **absent**, pas 0.0 — l'absence et le zéro ne disent pas la même chose |
| 2 | Piège 1 : bruit ÷100 | `sigma_rate` doit **s'effondrer**. S'il ne bouge pas, ce n'est pas de la physique |
| 3 | Exclure les runs plantés | un run planté porte une **sentinelle** à 1e18, pas une épaisseur. L'inclure rendrait un σ absurde et **plausible** |
| 4 | 40 couches Rate enchaînées | étendue ≈ **0 %** — §14 : le Rate **recopie** l'erreur, il n'en ajoute aucune |

#### 🔴 Comment RAPPORTER le chiffre, et c'est là que ça se joue

Le « 1 à 2 % » de 👤 est un **souvenir**, pas une mesure — *« c'est ce que j'avais en
tête »*. Même statut que la table de §12.7, *« estimés par moi au feeling »*. Donc :

- **0,1 % ou 10 %** → informatif : le modèle rate quelque chose, **ou** le souvenir est
  faux. **Demander laquelle des deux**, ne pas trancher seul.
- **1 à 2 %** → **corroboration FAIBLE**. Ne l'écris **jamais** comme une validation.
- Dans les deux cas, la question à poser à 👤 : *« as-tu un relevé machine de cette
  dispersion, plutôt qu'un souvenir ? »* **C'est ça, la vraie validation.**

---

### A26 — Un bloc de SANTÉ DE RUN, pour automatiser le contrôle 4 de §20

**Trois fois en deux jours, une grandeur était calculée et n'atteignait aucun œil :**

| grandeur | ce qu'elle disait, sans que personne l'entende |
|---|---|
| `crash_eliminated` | 83 repêchées sur 343 ; **un run où 87 sur 87** l'étaient — aucune stratégie n'avait passé le filtre |
| `n_layers_forced` | §17-37 : **32 couches sur 48** en repli, et le résultat annonçait une gagnante comme un run sain |
| `forbidden_gain_negative` | §17-38 : **zéro rejet** sur 8 runs, corridor 0 comme 0,020 |

§20-contrôle 4 prescrit déjà *« compte les rejets, ne lis pas le code »*. Personne ne le
fait à la main. **C'est exactement pour ça que ces trois-là ont dormi.**

#### Où, et ce qu'il faut écrire

| | |
|---|---|
| **Fichier** | `scripts/probe_anchor_noise_pipeline.py`, à côté du bloc `RESCUED=` déjà écrit |
| **Sources** | le résultat (`phase_a_forced`, `crash_eliminated`) et le `reports/STRAT_observability_*.json` le plus récent |

Une ligne `HEALTH=` par anomalie, et **`HEALTH=OK` quand il n'y en a aucune** — un bloc
silencieux ne se distingue pas d'un bloc absent.

```
HEALTH=RESCUED 41/300          -- score = pire RMSE finie, PAS un score de robustesse
HEALTH=FORCED 32/48 couches    -- lambda non CHOISIE mais IMPOSEE, cf 17-37
HEALTH=FILTRE_INERTE forbidden_gain_negative : 0 rejet sur 48 couches
```

🔴 **Un filtre qui rejette ZÉRO est un DÉFAUT, pas un succès.** Il ne produit aucune erreur,
il produit un résultat plausible — c'est le mode de défaillance qui gouverne ce dépôt.

#### Vérification

Rejouer le run où **87 sur 87** étaient repêchées : il doit désormais **crier**. Et un run
sain doit dire `HEALTH=OK`, pas rien.

---

### A27 — A5, le harnais d'empreinte `float.hex()`

Toujours inexistant, et c'est **le seul instrument de C1** (§3). La recette complète est en
**palier 1 de la feuille de route** — ne la réécris pas ici, suis-la.

🔑 **Pourquoi ça devient urgent** : le 2026-08-13 je m'en suis passé pour la porte de
plantage en énumérant **exhaustivement ses 127 cas** (⚠️ le nombre 1046 a circulé ici et n’existe nulle part dans le dépôt : l’énumération réelle est `for n_runs in (10, 25, 50, 150, 300, 500)` à pas sauté, `tests/unit/test_strat_crash_gate_confidence.py:127`) — possible parce que c'est une
fonction pure de deux entiers. **Un changement de noyau n'a pas ce luxe**, et la prochaine
fois personne n'aura d'instrument.

⚠️ Les étapes 3 et 4 du palier 1 sont les seules qui prouvent que le harnais **fonctionne**.
Ne les saute pas : un harnais qui a l'air de marcher sans rien prouver est le pire des trois
états.

---

### 🔴 Ce qu'il ne faut PAS faire, et pourquoi

| | |
|---|---|
| **Toucher à la fonction objectif** (A21) | 👤 l'a gelée. C'est le chantier le plus rentable, et ce n'est pas à toi de le dégeler |
| **Chasser l'asymétrie H / L** | **Non mesurable** : le corridor perturbe les deux matériaux ensemble et aucun paramètre ne les sépare |
| **La convolution spectrale complète** | La part systématique est capturée ; sa modulation tirage à tirage mettrait une intégration **dans la boucle chaude** |
| **Monter la profondeur** | §23 : elle achète de la précision sur un nombre déjà précis |
| **Rouvrir la grille, le lissage ou la cadence** | Tranchés par 👤 le 2026-08-12. Une **mesure** peut les rouvrir, jamais un raisonnement |

### L'ordre, et la raison

**A25 d'abord.** A26 et A27 rendent le dépôt plus sûr ; **seule A25 peut rendre STRAT
vrai** — et elle est à portée depuis deux jours sans que personne l'ait vue.

---

## 25. 🔴 MULTIPLE TESTGLASS METHODOLOGY — le programme annoncé le 2026-08-14

> 👤 *« comme tu le vois sur le 99c, il devient quasi impossible de faire du monitoring
> optique et du POEM sur des filtres à plus de 50 couches. Mon idée est la suivante :
> découper le filtre en deux parties, testglass 1 et testglass 2, en remettant un verre nu
> après une cinquantaine de couches. Les deux monitorings sont indépendants, mais le verre
> avec le dépôt total bénéficie des deux coatings successifs. »*

> 👤 *« pour savoir quand changer de témoin, je veux une méthode très générale, et qui fonctionne bien
> au-delà du cas particulier de ce 99c. Cela pourrait être basé sur un nombre de couches
> raisonnable, un SEEL qui se dégrade, ou autre, mais tout cela est à tester de manière
> systématisée et automatisée. On comprendra peut-être a posteriori ! »*

### 25.1. Le constat qui ouvre le chantier

🔴 **ÉTABLI LE 2026-08-15, ET C'EST PIRE QUE « MOINS BON » : SUR LE 99 COUCHES, RIEN NE
SURVIT.** La référence sans changement de témoin rend **`crash_rate = 100 %`**, en PREMIUM comme en FAST.
Or une stratégie dont le plantage dépasse 5 % reçoit un score **infini** et **sort du
classement** (`certus_strat_robustness.py:2125`). Les 785 candidates en sont donc sorties, et
ce qui revient vient du **repli sans survivant** (`:1152-1166`) : le solveur reclasse les
éliminées par risque croissant et rend la moins mauvaise avec la **pire RMSE finie**.

| | |
|---|---|
| 🔴 **`SEEL = 0,86 nm` n'est PAS un score de robustesse** | C'est le chiffre le moins mauvais parmi des stratégies qui **échouent toutes**. Ne le cite jamais comme une erreur par couche atteignable. |
| **Ce qui reste vrai, et c'est le vrai constat** | **Environ 75 couches sur 99 doivent passer en mode Rate** ; le suivi optique continu à λ₀ rend **100 % de plantages** (`CRASH_LEVEL_UNREACHABLE`). |
| **À comparer avec** | 48c : **0,17 nm à 0,0 % de plantage**. Là, le chiffre veut dire quelque chose. |

⚠️ **C'est le défaut qu'A26 annonce depuis le 2026-08-13** — *« score = pire RMSE finie, PAS
un score de robustesse »* — tombé sur le composant vitrine sans que personne le voie, parce
que le rapport d'origine **ne consignait pas le taux de plantage**. Tant qu'A26 n'est pas
faite : **lis le `crash_rate` avant tout score.**
Deux causes, toutes deux physiques et non contournables par un meilleur solveur :

- les **cavités demi-onde** ont un swing optique **nul** pendant leur dépôt ;
- les **miroirs de 19 couches** transmettent moins de 1e-4, donc le signal est noyé.

Un suivi optique continu à λ₀ sur tout l'empilement rend **100 % de plantages**
(`CRASH_LEVEL_UNREACHABLE`). Le monitoring optique ne meurt pas progressivement : il meurt.

### 25.2. Ce que le changement de témoin restaure, et ce qu'il coûte

**Elle restaure.** Chaque témoin ne porte jamais plus d'une cinquantaine de couches, donc `T`
reste mesurable, le swing `dT/de` reste exploitable, et POEM retrouve des extrema francs
comme repères de phase absolus.

🔴 **Elle coûte, et c'est le fait qui gouverne tout le chantier : LA COMPENSATION D'ERREUR NE
TRAVERSE PAS LE CHANGEMENT DE TÉMOIN.** Tout l'avantage du monitoring optique sur le contrôle au quartz
est qu'une erreur d'épaisseur sur la couche *k* est partiellement **auto-corrigée** : les
couches suivantes, lues sur le **même** verre, voient l'erreur accumulée et le point de
déclenchement se décale pour l'annuler en partie. Dès qu'on change de témoin, les couches
d'après sont lues sur un verre qui **ne contient pas** les erreurs d'avant. Le résidu de la
partie 1 est donc **gelé dans la pièce, définitivement incorrigible**, et le spectre final
porte erreur(partie 1) + erreur(partie 2) **sans terme croisé**.

🔑 **Et il faut être précis : ce sont DEUX mémoires distinctes qui tombent, pas une.**

| ce qui est perdu | portée |
|---|---|
| **La compensation globale** — le niveau de déclenchement est calculé sur la pile **nominale** et appliqué à la pile **réelle** ; l'écart entre les deux produit l'erreur de signe opposé (Macleod, Bousquet) | **toute la pile sous le changement de témoin**, non bornée |
| **Le rejeu d'ancres POEM** | borné à **4 couches** (`MAX_LOOKBACK_VAL`) |

C'est la première qui coûte cher, et elle n'est pas plafonnée. Ne dis pas « on ne perd que
4 couches d'historique » : c'est vrai pour POEM seul, et faux pour la compensation.

#### 👤 Ce que la machine impose, obtenu le 2026-08-14

| | |
|---|---|
| **Le changement se fait par carrousel SOUS VIDE** | Plusieurs témoins sont déjà en enceinte. **Ni remise à l'air, ni repompage, ni contamination.** ⚠️ Le nombre de changements de témoin est donc plafonné par le nombre de positions du carrousel. |
| **La fente garde le même réglage** | 👤 *« les fentes gardent le même setting »*. Une campagne ne peut pas choisir sa propre résolution : `monochromator_resolution_nm` reste **un scalaire pour tout le run**. |
| **Témoin et pièce reçoivent la même épaisseur** | À peu près identiques. Donc **aucun facteur d'uniformité à modéliser**, et le changement de témoin sépare la **mémoire optique**, rien d'autre. |

🔴 **Conséquence, et elle durcit le problème au lieu de l'adoucir : le changement de témoin est
OPÉRATIONNELLEMENT GRATUITE.** Pas de coût atelier à mettre en face du gain. L'arbitrage est
donc **purement informationnel** — on échange de la compensation contre du signal, et rien
d'autre ne vient trancher. Il n'y a aucun garde-fou économique pour dire « pas plus de deux
changements » : c'est la physique seule qui doit le dire.

### 25.3. 🔑 CE QUE LE CODE A DÉJÀ — le changement de témoin n'est pas une refonte

| | |
|---|---|
| **La vue témoin** | `certus/physics/certus_strat_batch.py:474` — `current_run_th_buffer[r, :i_layer]` est la pile accumulée que la lecture optique « voit ». **C'est là que le changement de témoin se joue** : changer de témoin à la couche *p* revient à passer la tranche `[r, p:i_layer]`. |
| **La pièce** | `sim_thick_batch`, épaisseurs réelles complètes `(n_runs, n_layers)`. Elle n'est **pas** tronquée : la pièce continue d'accumuler toutes les erreurs. C'est exactement la physique voulue. |
| **Le crochet POEM** | `certus/physics/certus_strat_batch.py:485` — `block_start[i_layer]` est **déjà** un tableau par couche disant au noyau où commence l'historique. Un changement de témoin est un `block_start` forcé, **plus** la troncature de la pile. |
| **L'écrêtage d'historique** | `certus/physics/certus_strat_growth.py:75` — `MAX_LOOKBACK_VAL = 4`, appliqué en `certus/physics/certus_strat_growth.py:904-908`. L'historique rejoué repart de zéro à le changement de témoin. |
| **Le seuil de swing** | `certus/physics/certus_strat_growth.py:883` — `SWING_MIN = 0.04`. **Un critère de mort du signal existe donc déjà, chiffré, dans le noyau.** |

🔴 **Vérifier ces cinq ancrages avant d'écrire une ligne.** Le document a déjà cité
`certus/core/certus_strat_growth.py` — **ce fichier n'existe pas**, le module est en
`certus/physics/`. Un plan bâti sur un chemin faux coûte une session.

### 25.4. 🔴 QUAND CHANGER DE VERRE TÉMOIN — le vrai problème, et il n'est PAS résolu

> 👤 *« on perd la compensation : oui, ça c'est évident, mais quand changer ? ça c'est
> l'enjeu majeur »* — *« savoir quand changer de testglass est un enjeu majeur et un problème
> de recherche à part entière et non résolu. Il va falloir explorer plein de pistes pour
> savoir à partir de quand on en tire bénéfice. Rien ne remplacera les tests simulés sur le
> 99c et peut-être le 48c. »* (2026-08-14)

**Ne confonds pas les deux.** Que le changement de témoin coûte la compensation est un fait acquis,
mécaniquement vrai, démontré par les tests de §25.5-T1 — et **ce n'est pas la question**.
La question est **à quelle couche changer de témoin**, et elle est ouverte.

#### 🔵 CE QUE LES EXPÉRIMENTATEURS PRESSENTENT — hypothèse consignée, PAS un résultat

> 👤 2026-08-15 : *« l'intuition veut qu'on change de verre témoin à proximité d'une zone non
> sensible, après au moins 20 couches et au max 60, et pour une épaisseur optique
> "raisonnable". Ça c'est ce que les expérimentateurs pressentent. »*

🔴 **C'est une intuition de praticien, à tester — elle n'a pas valeur de mesure.** Elle est
écrite ici parce qu'elle vient du terrain et qu'elle oriente la recherche, pas parce qu'elle
est établie. Chacun de ses trois critères a un statut de mesure **différent**, et il faut les
distinguer :

| critère de l'intuition | statut au 2026-08-15 |
|---|---|
| **changer près d'une zone peu sensible** | 🟠 **NON VALIDÉE, et le test conçu pour trancher a échoué à trancher.** Détail ci-dessous. |
| **au moins 20 couches, au plus 60** | 🟢 **déjà une contrainte dure du code**, posée par 👤 : `LO, HI = 20, 60` dans `campagne_intervalles.py`. Ce n'est pas une hypothèse testée, c'est le domaine dans lequel on cherche. C'est elle qui ramène les partitions à 441. |
| **épaisseur optique « raisonnable »** | 🔴 **RÉFUTÉE comme prédicteur** sur le 99c. L'épaisseur optique accumulée **ne prédit pas** où le changement doit avoir lieu. Réfutés avec elle : le vieillissement du témoin, le nombre d'espaceurs franchis, la position par rapport au dernier espaceur. |

#### 🔴 LA RÈGLE DE SENSIBILITÉ EST RÉFUTÉE — le test hors échantillon du 2026-08-15

La règle testée était : *« changer de verre témoin juste après une couche de FAIBLE
sensibilité, jamais après une couche sensible »*, où `S(p-1)` est la sensibilité de la couche
**gelée** par le changement.

🔴 **AVANT DE LIRE LE TABLEAU — `S` A DEUX DÉFINITIONS ET ELLES NE DONNENT PAS LE MÊME
CLASSEMENT.** §25.10 mesure `S(j)` par une perturbation de **1 nm ABSOLU**. Une perturbation
de **1 % RELATIF** pondère par l'épaisseur nominale : ce n'est **pas** la même grandeur. Sur le
random75 les deux ne corrèlent qu'à **+0,79** entre elles, et donnent des contrastes de
**11,3×** contre **19,8×**. **Seul le 1 nm absolu se compare aux trois repères existants.**
Une première version de ce paragraphe a mélangé les deux et concluait à tort ; les chiffres
ci-dessous sont tous en **1 nm absolu**.

| composant | structure | contraste de `S` | **Pearson r** |
|---|---|---|---|
| 99c passe-bande 5 cavités | 5 cavités + miroirs | **82×** | **+0,69** |
| 35c passe-bande 3 cavités | 3 cavités | 24× | +0,20 |
| 48c dichroïque | passe-haut | 14× | +0,25 |
| 🔑 **75c ALÉATOIRE** (graine 2026) | **aucune** | **11,3×** | **−0,19** (Spearman −0,15) |

#### Ce que ce test tranche, et ce qu'il ne tranche PAS

🔴 **Il ne tranche pas.** Et il faut le dire, parce que le random75 avait été construit **pour**
trancher. Les deux lectures du +0,69 étaient :

- *(a) la règle a besoin d'un fort contraste de sensibilité* ;
- *(b) le +0,69 tenait à la structure du 99c, pas à la sensibilité*.

Le random75 devait les séparer en offrant **une absence de structure avec un fort contraste**.
**Il n'a pas le fort contraste** : 11,3×, soit le **plus bas des quatre**, sept fois moins que
le 99c. Une corrélation faible y est donc **compatible avec (a) autant qu'avec (b)**.
L'expérience ne discrimine rien.

⚠️ **Et le −0,19 n'est pas un signe inversé, c'est du bruit.** Avec 18 points, il faut
`|r| ≥ 0,47` pour sortir de zéro au seuil de 5 % ; **11 des 18 positions sont à égalité**.
Lire une inversion là-dedans serait une surinterprétation.

🔑 **Ce qui reste néanmoins vrai sur les quatre composants** : contraste et corrélation vont
dans le même sens — 82× → +0,69, puis 24×, 14×, 11,3× → +0,20, +0,25, −0,19. Ce n'est **pas**
une validation : quatre points, et trois des quatre corrélations sont sous le seuil de
signification. **`S(p-1)` n'est pas un prédicteur validé.**

📌 **L'expérience qui trancherait, et elle reste à faire** : un empilement **sans structure**
et à **fort contraste de sensibilité** (~80×). Générer un random dont les multiplicateurs sont
tirés pour maximiser l'étendue de `S`, et non uniformément comme le random75.

#### 🟢 ET LE RÉSULTAT LE PLUS IMPORTANT DE LA JOURNÉE — la barrière n'est PAS le nombre de couches

Le 75 couches aléatoire a été mesuré **en une seule campagne**, sur verre nu, même protocole
(fast, fente 2 nm, graine 42) : **241 stratégies déposables sur 662, plantage minimal 0,0 %,
SEEL 0,272 nm**. Il n'a **aucun** besoin d'un changement de verre témoin.

| | couches | une seule campagne | structure |
|---|---|---|---|
| dichroïque 48c | 48 | 🟢 0 % — 0,173 nm | passe-haut |
| passe-bande 35c | 35 | 🟢 0 % — 0,482 nm | 3 cavités |
| 🔑 **aléatoire 75c** | **75** | 🟢 **0 % — 0,272 nm** | **aucune** |
| passe-bande 99c | 99 | 🔴 **100 % sur 487 stratégies** | **5 cavités + miroirs à 10⁻⁴** |

🔴 **75 couches passent, 99 ne passent pas. Ce n'est donc pas la longueur qui tue le
monitoring, c'est la STRUCTURE** — les espaceurs demi-onde à swing nul et les miroirs de 19
couches sous le plancher photométrique (§25.1). Le modèle « au-delà d'une cinquantaine de
couches le témoin devient optiquement mort » est **réfuté** : un empilement aléatoire de 75
couches se surveille d'un bout à l'autre sans difficulté.

⚠️ **Ce que ça ne dit pas** : que 99 couches aléatoires passeraient. Un seul empilement de 75,
une seule graine. Ce qui est établi est la **réfutation**, pas la loi inverse.

#### 🔴 ET LE CONTRÔLE NÉGATIF PASSE UNE TROISIÈME FOIS

Puisque le random75 est monitorable en une campagne, changer de témoin doit y **perdre**.
C'est le cas, et largement :

| composant monitorable | sans changement | avec changement | verdict |
|---|---|---|---|
| 48c | 0,173 nm | — | **+73 à +89 %** (11/11 partitions) |
| 35c | 0,482 nm | — | **+10 à +98 %** (12/12 partitions) |
| **75c aléatoire** | **0,272 nm** | **0,571 nm** (meilleure des 18) | 🔴 **+110 %** |

**Trois composants sur trois.** Là où le monitoring optique fonctionne, changer de verre
témoin **dégrade toujours**. C'est mécaniquement attendu — le changement *retire* de la
compensation sans rien restaurer — et c'est ce qui fait du multi-témoins un **outil de
faisabilité, jamais d'optimisation**.

⚠️ Le +110 % est mesuré contre une borne supérieure (sélection gloutonne par intervalle,
§25.9), donc le vrai écart est **au plus** celui-là. Le signe, lui, n'est pas en cause.

🔑 **Et un résultat qui, lui, se REPRODUIT** : *où* changer importe **peu**, sur les deux
composants et indépendamment de leur structure.

| | 99c (5 cavités) | 75c (aléatoire) |
|---|---|---|
| positions/partitions assemblées | 440 | 18 |
| étendue totale du SEEL | **+14,4 %** | **+15,4 %** |
| à égalité avec la première (δ = 5,1 %) | 136 | **11 sur 18** |

C'est **la seule régularité qui traverse une structure et une absence de structure**.
L'optimum est **plat**, ce qui explique à la fois pourquoi l'intuition des expérimentateurs
est difficile à prendre en défaut, et pourquoi elle est peu discriminante en pratique :
sur un plateau, presque toute position raisonnable convient.

📏 Reproduction : `scripts/assembler_r75.py`, sortie
`reports/controle_random75/ASSEMBLAGE_r75.json`, log `reports/assemblage_r75.log`.
Contrôle d'assemblage (nominales concaténées vs design complet) : écart **0,000e+00**.

**Ce que ça vaut opérationnellement** : l'intuition est un **bon filtre a priori** — elle
écarte les positions manifestement mauvaises sans calcul — mais elle ne remplace pas
l'assemblage, qui reste la seule mesure du SEEL de la pièce. 👤 : *« rien ne remplacera les
tests simulés »*.

#### 🎯 La cible, posée par 👤

> **SEEL global de l'ordre de 0,3 nm sur le 99c**, avec **2 ou 3 témoins**, sur la pièce
> complète qui les reçoit tous. On tâtonnera d'abord.

🔴 **MAIS LA PREMIÈRE CIBLE N'EST PAS LE SEEL.** Le point de départ n'est pas « 0,86 nm » :
c'est **100 % de plantage**, donc *aucune* stratégie exploitable (§25.1). **Tant que le
plantage n'est pas passé sous 5 %, aucun SEEL n'est publiable** — celui qui s'affichera sera
un score de repli, et comparer deux couches de changement sur des scores de repli revient à
**comparer deux façons d'échouer**.

| # | Cible | Pourquoi dans cet ordre |
|---|---|---|
| **1** | **`crash_rate < 5 %`** sur la pièce | Sans ça le composant n'est pas fabricable **du tout**, et rien d'autre ne se mesure. C'est ce seuil qui dira si le multi-témoins **marche**. |
| **2** | SEEL de l'ordre de **0,3 nm** | La cible de 👤. Elle ne devient une question qu'une fois la première franchie. |

Repère pour la cible 2 : à 3 témoins chaque campagne fait ~33 couches, soit la longueur du
35c (0,48 nm) et du 48c (0,17 nm) — **à 0,0 % de plantage tous les deux**. Une cible entre
les deux est donc cohérente avec ce que la machine sait faire sur des piles de cette taille,
à condition que les campagnes se combinent bien, ce que personne ne sait.

#### 🔴 LE SEEL GLOBAL N'EST PAS LA MOYENNE DES SEEL PARTIELS — ne fais jamais ce raccourci

> 👤 *« attention, SEEL global de 0,3 nm ne veut pas dire que les SEEL partiels (par
> testglass) seront à 0,3 ! »*

**Ce sont deux grandeurs différentes, mesurées sur deux objets différents.**

| | mesuré sur | ce que ça vaut |
|---|---|---|
| **SEEL global** | le **spectre de la pièce complète**, 99 couches, 5 cavités | 🔑 **la seule grandeur qui compte** — c'est le composant qu'on vend |
| **SEEL partiel** | une campagne prise seule, ~33 couches | un **diagnostic**, rien de plus |

**Pourquoi ils divergent, et fortement.** Un passe-bande à 5 cavités est un amplificateur
d'erreur : la même erreur physique par couche produit une erreur spectrale bien plus grande
sur le composant résonant complet que sur un sous-empilement mesuré isolément. Une campagne
qui « affiche 0,2 nm » toute seule peut donc contribuer beaucoup plus que 0,2 au chiffre
global. **Viser 0,3 global n'autorise pas à viser 0,3 par campagne** — il faudra
vraisemblablement bien mieux que ça sur chacune.

⚠️ Et cela **re-condamne** le raccourci déjà interdit en §25.6 : `SEEL = √(SEEL₁² + SEEL₂²)`
n'est pas seulement non mesuré, il compose des grandeurs qui **ne vivent pas sur le même
objet**. Ne rapporte que le SEEL de la pièce. Si tu affiches un SEEL partiel, dis en toutes
lettres qu'il est un diagnostic et **jamais** qu'il compose le global.

#### Pourquoi c'est difficile, et pas seulement long

Il faut l'écrire, sinon quelqu'un va croire qu'un seuil suffit.

| # | La difficulté | Pourquoi elle bloque une règle simple |
|---|---|---|
| 1 | **Bénéfice et coût varient en sens inverse le long de la pile** | Changer tôt garde un témoin vif mais gèle l'erreur tôt, et la compensation manque sur tout le reste. Changer tard garde la compensation mais les couches d'avant ont déjà été surveillées sur un témoin mourant. L'optimum est **au milieu de deux courbes qu'on ne sait pas tracer**. |
| 2 | 🔴 **La grandeur qui décide n'est pas locale** | Ce qui compte est le SEEL **à la fin**, pas la qualité du signal **à le changement de témoin**. Un changement de témoin qui paraît excellente localement peut être désastreuse si elle gèle l'erreur dans une couche à laquelle le spectre final est très sensible. **On ne peut donc pas choisir couche par couche** : le problème n'est pas séparable, et toute règle gloutonne est suspecte. |
| 3 | **Le changement de témoin n'est pas un axe indépendant** | Elle force une frontière de bloc, exactement comme un changement de λ ou une couche en Rate. Elle entre donc en **concurrence combinatoire** avec le partitionnement en blocs (§17-43) et avec le placement des couches Rate. L'optimum de changement dépend du plan de blocs, et réciproquement. Ce n'est pas un scalaire à régler. |
| 4 | ⚠️ **Le critère évident est probablement SYSTÉMATIQUEMENT EN RETARD** | `SWING_MIN = 0.04` dit où le monitoring **échoue**, pas quand changer de témoin **paie**. Quand le swing passe sous le seuil, le mal est déjà fait : le bon changement se place vraisemblablement **avant** la mort du signal, pas au moment où elle survient. Un seuil rendra donc une réponse trop tardive, et elle aura l'air raisonnable. |
| 5 | **Le coût opérationnel ne borne rien** | Le carrousel rend le changement de témoin gratuit (§25.2). Aucun garde-fou économique ne dira « pas plus de deux » : seule la physique le dira, et seul le nombre de positions du carrousel plafonne. |
| 6 | 🔴 **La décision peut être sous le bruit** | La résolution statistique d'un score est de ~6 % relatif à N = 150. Si deux couches de changement diffèrent de moins que ça, un balayage « trouvera » un optimum qui est du bruit. **Il faut fixer la profondeur avant de regarder les résultats**, et vérifier qu'un écart survit à un changement de graine. |

#### La méthode, et l'ordre n'est pas négociable

👤 a tranché : **on ne postule pas la règle, on la découvre.** Et : *« rien ne remplacera les
tests simulés »*. Donc, en trois temps :

1. **Deux prédicteurs GRATUITS**, sans aucun Monte-Carlo (T2, T3).
2. **Une vérité de terrain COÛTEUSE** : le balayage des couches de changement sur le 99c (T4).
3. **La corrélation entre les deux** — le « on comprendra a posteriori ». Si un prédicteur
   gratuit prédit la vérité coûteuse, on tient une **règle générale** ; sinon on a une carte,
   et on sait que la règle est ailleurs.

⚠️ **Ne pas inverser.** Écrire la règle d'abord puis chercher la mesure qui la confirme est
l'erreur n°2 du document. Le tâtonnement de 👤 est légitime **à condition d'être consigné
comme tâtonnement** : chaque essai, sa couche de changement, son SEEL, dans `probe_runs.tsv`.
Un tâtonnement noté est une carte ; un tâtonnement oublié est du bruit.

### 25.5. LA TODO LISTE, dans l'ordre

#### 🔴 T0 — Les CONTRÔLES NÉGATIFS, avant toute machinerie

**À faire en premier, et c'est contre-intuitif.** Sur le 35c et le 48c, le monitoring optique
marche : le SEEL y vaut 0,48 et 0,17 nm. Un changement de témoin y est donc **une perte sèche** — il
retire de la compensation sans rien restaurer, puisqu'il n'y avait rien à restaurer.

⚠️ Et le carrousel ne lui oppose **aucun coût** pour la retenir (§25.2) : si le modèle se
trompe, rien dans la simulation ne l'empêchera de couper à tort. C'est précisément pour ça
que ces contrôles négatifs sont le garde-fou du chantier.

**Le critère de recette du chantier entier :** si la machinerie finit par « améliorer » le 35c
ou le 48c en les coupant, **le modèle est faux** et rien de ce qui suit ne vaut. Écris cette
attente **avant** de mesurer, dans le test, pas dans le rapport.

| # | Ce qu'on mesure | Attendu |
|---|---|---|
| 1 | 48c, changement forcé en 24 | SEEL **dégradé** par rapport à 0,17 nm |
| 2 | 35c, changement forcé en 17 | SEEL **dégradé** par rapport à 0,48 nm |
| 3 | 99c, changement forcé vers le milieu | **plantage sous 5 %** — c'est l'hypothèse à réfuter. **Pas un SEEL** : sans survivant, tout SEEL affiché est un score de repli (§25.1) |

#### ✅ T1 — Le mécanisme de changement : **FAIT le 2026-08-14**

**Le champ à poser sur une stratégie : `witness_reset_layers`**, liste d'indices 0-based des
couches où un témoin **nu** entre dans le faisceau. Liste vide = comportement historique.
L'indice 0 est ignoré (la couche 0 pousse déjà sur du verre nu).

**Ce qui a été écrit, et c'est plus simple que prévu.** Le changement de témoin n'est pas une troncature
de tranche : c'est **l'index de départ de trois boucles** dans le noyau de croissance.

| où | ce qui change |
|---|---|
| `certus_strat_growth.py`, `simulate_growth_kernel` | nouveau paramètre `witness_base_layer` (défaut 0). **`M_before`** (pile réelle) et **`M_nom`** (pile nominale) partent de `witness_base_layer` au lieu de 0, ainsi que la pile sous la fenêtre POEM. Garde ajoutée : `j0` ne peut pas descendre sous la base, sinon la boucle tournerait à l'envers et rendrait vide **en silence**. |
| `certus_strat_batch.py` | `witness_reset_flags` → carte `witness_base[i]`, et **frontière de bloc forcée** à chaque changement : les ancres que POEM rejouerait ont été observées sur un verre qui n'est plus dans le faisceau. |
| `certus_strat_robustness.py` | lit `witness_reset_layers` sur la stratégie et construit les drapeaux. |

🔑 **Le coût de le changement de témoin n'est modélisé NULLE PART, et il ne doit pas l'être** — il tombe
de ces deux boucles. Le niveau de déclenchement est calculé sur la pile **nominale** et
appliqué à la **réelle** ; c'est cet écart qui produit l'erreur de signe opposé. Faire partir
les deux boucles au même `witness_base_layer` rend les erreurs d'en dessous invisibles aux
deux à la fois : elles ne peuvent plus être compensées, et restent gelées dans la pièce.
🔴 **N'en tronquer qu'une seule serait bien pire que faux** : on comparerait une cible
nominale à 99 couches contre une pile réelle de 20.

🔴 **Et la boucle du Rate n'est PAS coupée**, délibérément (`growth.py`, branche `is_rate`) :
l'estimation de vitesse est une propriété **de la machine** — le quartz, le chrono — pas du
verre que le faisceau regarde. Changer de témoin ne fait pas oublier sa calibration.

**Les tests, `tests/unit/test_strat_multiple_testglass.py` — 9 passent :**

| # | Test | Résultat |
|---|---|---|
| 1 | carte de changements de témoin toute vide = paramètre absent | ✅ bit-identiques : l'historique reste comparable |
| 2 | changement en *p*, erreur de 40 nm enfouie en *p−4* | ✅ **bit-identique** au cas sans erreur → le témoin ne voit vraiment plus sous le changement de témoin |
| 3 | 🔴 **le contrôle qui donne son sens au test 2** : même erreur, **sans** changement de témoin | ✅ **différent** → la compensation est bien vivante, donc le test 2 mesure quelque chose |
| 4 | 🔴 **la pièce garde ce que le témoin a oublié** | ✅ `results` rend les 12 couches, changement ou non. C'est le test qui attrape le défaut flatteur : tronquer la pièce **améliorerait** le score |
| 5 | couche de changement honorée, 4 positions | ✅ |

⚠️ **Ce que T1 ne dit PAS** : que couper soit bénéfique. Il rend le changement de témoin *possible et
correctement modélisée*. Tout le reste de §25 sert à savoir **où**.

#### T2 — Prédicteur gratuit n°1 : LA CARTE DE MORT DU SIGNAL

Pour chaque couche *i* et chaque λ candidate, calculer sur le témoin portant les couches
`[base..i)` le **swing disponible** — l'amplitude crête-à-crête de `T` pendant le dépôt de la
couche. Nominal, aucun tirage, coût négligeable.

La grandeur qui décide : **`swing_max(i) = max sur λ du swing`**. Le seuil existe déjà :
`SWING_MIN = 0.04` (`certus/physics/certus_strat_growth.py:883`). **Première règle générale candidate : changer de témoin juste
avant que `swing_max(i)` ne passe sous `SWING_MIN`.**

⚠️ Cette carte est à produire **par couche et par λ**, pas seulement par couche : une couche
aveugle à λ₀ peut être parfaitement lisible 40 nm plus loin. C'est tout l'objet du solveur.

#### T3 — Prédicteur gratuit n°2 : LA CARTE DE SENSIBILITÉ À L'ERREUR GELÉE

C'est le prédicteur du **coût** de le changement de témoin, et il tombe directement de la §25.2. Pour
chaque position candidate *p* : geler un champ d'erreur réaliste sur les couches `1..p`, puis
mesurer le **dommage spectral** sur le design final. TMM pur, aucun monitoring, aucun
Monte-Carlo de robustesse — donc peu coûteux.

Cela rend `sensibilite(p)`. La règle générale candidate devient le croisement des deux
courbes gratuites : **couper là où le signal est encore vivant et où l'erreur gelée coûte le
moins.**

⚠️ **Ne pas coder en dur « pas à l'intérieur d'une cavité ».** C'est l'attente — la résonance
dépend de l'épaisseur optique totale du spacer et des miroirs qui l'encadrent, donc une erreur
gelée là désaccorde toute la bande. Mais c'est au balayage de le montrer. Une carte qui
retrouve les spacers (couches 10, 30, 50, 70, 90) toute seule **valide la méthode** ; une
règle qui les impose ne prouve rien.

#### T4 — La VÉRITÉ DE TERRAIN : balayage exhaustif, automatisé

| | |
|---|---|
| **Script** | `scripts/campaign_testglass_cut_sweep.py`, sur le modèle de `scripts/run_campaign.py` — **une commande = toute la campagne**, chaque run vérifié contre la configuration demandée, reprenable |
| **Balayage** | *p* sur toutes les positions, ou un pas régulier si le coût l'impose |
| **Ce qu'on mesure** | le **SEEL de la pièce**, pas du témoin. Plus le taux de plantage, le nombre de couches en Rate, et le nombre de changements de λ |
| **Contrôles dans la même campagne** | (a) sans changement de témoin ; (b) **même nombre de couches en Rate, sans changement de témoin** — sans ce second contrôle, on ne saura pas si le gain vient de le changement de témoin ou du Rate |

🔴 **Consigner la configuration effective de chaque run**, et pas seulement celle demandée.
La campagne « gate » du 2026-08-14 a rendu ses 6 runs **FAILED** parce que
`crash_gate_confidence` était dans `_OVERRIDES` sans être dans `TRACED_KEYS` : appliquée au
run, jamais consignée. `witness_reset_layers` doit être dans **les deux**, et dans le nom du
fichier de sortie.

#### T5 — La CORRÉLATION, et la règle générale

Confronter T2 et T3 à T4 : lequel des prédicteurs gratuits classe correctement les positions
de changement ? Candidats à mettre en concurrence, **tous exprimés sans dimension** pour qu'ils
survivent au-delà du 99c :

| candidat | forme | ce qu'il vaut |
|---|---|---|
| nombre de couches | couper tous les *K* | le plus simple, **la référence à battre** |
| mort du signal | `swing_max(i) < SWING_MIN` | physiquement motivé, gratuit (T2) |
| erreur gelée | minimum de `sensibilite(p)` | cible le vrai coût, gratuit (T3) |
| SEEL marginal | la contribution par couche se dégrade | plus coûteux, demande l'attribution par couche |
| structure du design | frontières de sous-ensembles | gratuit, mais est-ce général ? |

**Une règle n'est retenue que si elle est validée hors échantillon** : autre graine **et**
autre empilement. Un changement de témoin est un degré de liberté de plus — une recherche qui l'a trouvera
**toujours** au moins aussi bon en échantillon. C'est le piège central de ce chantier.

#### T6 — Généraliser : l'échelle d'empilements

La règle doit tenir sur une échelle, pas sur un cas :

| empilement | rôle | attendu |
|---|---|---|
| 35c passe-bande | **contrôle négatif** | le changement de témoin **perd** |
| 48c dichroïque | **contrôle négatif** | le changement de témoin **perd** |
| 99c 5 cavités | le cas qui ouvre le chantier | le changement de témoin **gagne** |
| ≥ 150c synthétique | l'extrapolation | le changement de témoin gagne **beaucoup**, et 2 changements battent 1 |

### 25.6. 🔴 LES PIÈGES DE CE CHANTIER

| | |
|---|---|
| **Dériver le SEEL global** | On sera tenté d'écrire `SEEL = √(SEEL₁² + SEEL₂²)`. Ce n'est pas seulement une conjecture non mesurée : elle compose des grandeurs qui **ne vivent pas sur le même objet** (§25.4). **Ne rapporte que le SEEL de la pièce.** |
| **Confondre SEEL global et SEEL partiels** | 👤 : *« SEEL global de 0,3 nm ne veut pas dire que les SEEL partiels seront à 0,3 »*. Le partiel est un **diagnostic**, jamais un terme du global. |
| **Tronquer la pièce avec le témoin** | Le défaut qui rendrait tout le chantier faux **et plausible** : le score s'améliorerait parce que les erreurs d'avant le changement de témoin auraient disparu au lieu d'être gelées. Test 4 de T1, et il est écrit. |
| **Le degré de liberté gratuit** | Un changement de témoin ne peut qu'améliorer un résultat **en échantillon**. Validation hors échantillon obligatoire : autre graine **et** autre empilement. |
| **Le plantage à 0,0 %** | Zéro sur 300 tirages n'est pas zéro. C'est « moins de 1 % à 95 % de confiance ». |
| **Croire qu'un coût atelier freinera** | Il n'y en a pas : le carrousel rend le changement de témoin gratuit (§25.2). Rien hors de la physique ne limitera le nombre de changements de témoin — sauf le nombre de positions du carrousel. |
| **Changer « vers 50 »** | 50 est le souvenir de 👤 sur un cas, pas une mesure. Le balayage doit être libre de rendre 20, 30 ou 70. |
| 🔴 **Chercher la règle avant d'avoir les essais** | 👤, deux fois : *« ce sont les essais-erreur avec de nombreux batchs qui permettront une compréhension a posteriori »*. Une explication trouvée avant les mesures sera confirmée par elles, quoi qu'elles disent. |


---

### 25.7. 🔴 LE PLAN D'EXÉCUTION — et le problème qu'il doit résoudre AVANT tout le reste

> 👤 2026-08-15 : *« je veux un plan robuste, bien pensé, pour effectivement trouver
> l'endroit du changement de verre témoin et viser un SEEL amélioré sur le 99c avec deux ou
> trois verres témoins, sans que le raisonnement soit lié à la nature du filtre
> (passe-bande), mais avec des arguments très généraux. »*

#### 🔴 P0 — L'OBJECTIF EST SATURÉ, ET AUCUNE RECHERCHE NE FONCTIONNE SUR UN OBJECTIF PLAT

C'est le fait qui commande tout le plan, et il faut le regarder en face avant d'écrire une
ligne de balayage.

| grandeur | valeur sur le 99c | utilisable comme objectif ? |
|---|---|---|
| **SEEL** | score de **repli** (§25.1) | ❌ il classe des façons d'échouer |
| **`crash_rate`** | **1,000**, saturé | ❌ plat : aucune direction de recherche |

**Chercher la meilleure couche de changement en comparant des SEEL de repli reviendrait à
optimiser du bruit.** Il faut donc d'abord une grandeur qui ait un **gradient**. Deux voies,
et il faut les deux parce qu'elles se contrôlent mutuellement.

**Voie A — la MARGE, qui existe déjà et n'est pas saturée.** Le noyau rend par couche
`m_level`, `m_missed`, `m_fab` (`certus/physics/certus_strat_batch.py:393-395`), remontés en
profil (`certus/core/certus_strat_robustness.py:2243`). **A23 a mesuré que la marge prédit
le plantage d'un facteur 22, validée non circulairement.** Objectif de substitution pendant
la saturation : le **nombre de couches à marge insuffisante**, et la **pire marge**. Ces deux
nombres bougent quand le plantage ne bouge plus.

**Voie B — la CONTINUATION : desaturer, optimiser, puis remonter.** Réduire l'amplitude du
bruit (ou le corridor d'indice) d'un facteur jusqu'à ce que `crash_rate < 1`, chercher les
couches de changement dans ce régime, puis **remonter la difficulté par paliers** et vérifier
que les positions tiennent.

> 🔑 **Et ce test porte plus que la recherche : il dit si la règle est STRUCTURELLE.** Si la
> couche optimale ne bouge pas quand on change la difficulté, elle est dictée par
> l'empilement. Si elle se déplace, elle est dictée par le bruit — et il n'y a alors **aucune
> règle générale à trouver**, ce qui est un résultat en soi.

#### P1 — Les grandeurs qu'une règle GÉNÉRALE a le droit d'utiliser

👤 l'exige : *« sans que le raisonnement soit lié à la nature du filtre »*. La liste est donc
fermée, et elle se vérifie par un test simple — **une grandeur est admissible si elle se
calcule sur un empilement dont on ignore la famille.**

| ✅ Admissible | pourquoi |
|---|---|
| **Épaisseur optique accumulée depuis le dernier changement**, en unités de λ : $\sum n_j d_j / \lambda$ | **sans dimension**, donc transportable telle quelle d'un 48c à un 200c. C'est le meilleur candidat : il explique un « vers 50 couches » comme une *conséquence*, pas comme une règle |
| Nombre de couches depuis le dernier changement | la règle naïve, **la référence à battre** |
| Niveau de transmission du témoin `T(λ)` | dit quand le signal passe sous le plancher photométrique |
| Swing disponible, `SWING_MIN = 0.04` déjà codé | dit quand il n'y a plus d'extremum exploitable |
| Nombre de λ candidates viables pour la couche suivante | zéro ⟹ couche forcée |
| La marge (P0, voie A) | seule grandeur à gradient sous saturation |
| Dommage spectral d'une erreur gelée sur les couches `1..p` | le **coût** du changement, en TMM pur |

| ❌ Inadmissible | pourquoi |
|---|---|
| Position des cavités, des spacers, des miroirs | demande de savoir que c'est un passe-bande |
| « couper à la ie cavité » | ne survit pas au composant suivant |
| Toute constante ajustée sur le 99c seul | c'est la réponse d'un filtre, pas une règle |

#### P2 — Les deux cartes GRATUITES, sans un seul tirage Monte-Carlo

| carte | ce qu'elle donne | coût |
|---|---|---|
| **A — viabilité** | par couche et par λ, sur le témoin portant `[base..i)` : swing disponible, niveau `T`, nombre de λ viables. Dit **quand le témoin meurt** | minutes |
| **B — coût de l'erreur gelée** | par position `p` : geler un champ d'erreur réaliste sur `1..p`, mesurer le dommage spectral du design final. TMM pur | minutes |

La couche de changement candidate est au **croisement** : là où le signal est encore vivant
et où l'erreur gelée coûte le moins. ⚠️ Les deux cartes sont des **prédicteurs**, pas des
mesures : leur valeur se juge à leur corrélation avec P3, pas à leur élégance.

#### P3 — La recherche, et pourquoi elle n'est pas une force brute

Avec 49 positions admissibles (paires seulement, §25.5), il y a **1 176** couples et
**18 424** triplets. À ~15 min le run, l'énumération est exclue. L'ordre est donc :

1. **Un changement** — balayage grossier des positions (10 runs), sur le régime désaturé de
   P0. Compare la position gagnante aux cartes A et B : **c'est là que se joue la
   compréhension a posteriori.**
2. **Deux changements** — glouton : on fixe le meilleur premier, on balaie le second.
   🔴 **Puis on teste la séparabilité** : le meilleur couple est-il bien (meilleur seul,
   meilleur second) ? Si oui, le problème est quasi séparable et le glouton est justifié. Si
   non, **c'est un résultat**, et la recherche doit s'élargir.
3. **Trois changements** — idem, en partant du meilleur couple.
4. **Perturbation locale** autour de chaque optimum, ±2 et ±4 couches, pour distinguer un
   optimum **pointu** d'un plateau. Un optimum pointu à la résolution du score est suspect.

#### P4 — Les garde-fous, sans lesquels le plan se trompera lui-même

| # | Le piège | La parade, posée AVANT de mesurer |
|---|---|---|
| 1 | **Un changement est un degré de liberté gratuit** : 3 témoins font toujours ≥ 1 en échantillon | Le gagnant doit survivre à **une autre graine**. Écart requis : supérieur à la résolution statistique du score. |
| 2 | **Confusion avec la structure en blocs** : un changement force une frontière de bloc, donc modifie aussi le partitionnement | Rapporter le **nombre de blocs** à chaque ligne. Comparer à nombre de blocs égal quand c'est possible. |
| 3 | **Décision sous le bruit** | Fixer `N` **à l'avance**. Un écart inférieur à la résolution est une **égalité**, pas un classement. |
| 4 | **La règle est ajustée sur le 99c** | La **règle**, pas les positions, doit être appliquée au 48c et au 35c et y prédire **« ne pas changer »**. C'est la falsification, et elle n'est pas optionnelle. |
| 5 | **On confond desaturé et nominal** | Toute position trouvée en régime réduit doit être **rejouée au nominal**. Sinon elle décrit un autre problème. |

#### P5 — Ce que le plan doit pouvoir conclure, y compris contre lui-même

Un plan qui ne peut pas échouer n'est pas un plan. Les trois issues sont **toutes**
publiables :

| issue | ce qu'on écrit |
|---|---|
| 🟢 `crash < 5 %` atteint à 2 ou 3 témoins | Le SEEL devient mesurable. **Alors seulement** la cible de 0,3 nm devient une question. |
| 🟠 `crash` baisse sans passer sous 5 % | Le mécanisme agit dans le bon sens mais ne suffit pas. Dire de combien, et ce qu'il faudrait en plus. |
| 🔴 aucun arrangement ne fait baisser `crash` | **Résultat valable et important** : sur ce composant le changement de témoin n'est pas la réponse, et il faut chercher ailleurs. Ne pas le maquiller en « amélioration du SEEL » de repli. |

### 25.8. 🟢 MESURÉ LE 2026-08-15 — le multi-témoins rend le 99c FABRICABLE, pas plus précis

**C'est le premier résultat positif du chantier, et sa lecture est étroite.** Ne le résume
jamais par « le SEEL ne change pas » : les deux chiffres ci-dessous ne décrivent pas la même
chose.

| | RMSE P95 | SEEL | plantage |
|---|---|---|---|
| **pièce assemblée**, 3 témoins (0 / 32 / 66) | `0.184946` | **0,860 nm** | **0 %** sur chacune des 3 campagnes |
| référence monolithique | `0.187761` | 0,87 nm | **100 %** — score de **repli** (§25.1) |

🔑 **Le monolithique n'est pas atteignable.** Aucune des 487 stratégies ne survit, donc son
0,87 nm ne décrit aucun dépôt réalisable. L'assemblé, lui, sort de **trois campagnes
déposables** — 23, 54 et 156 stratégies valides au choix, chacune à 0 % de plantage.

> **Le multi-témoins ne fait pas gagner en précision spectrale. Il fait passer d'IMPOSSIBLE
> à POSSIBLE.**

⚠️ **La cible de 👤 n'est pas atteinte** : 0,86 nm contre 0,3 nm visés, facteur 2,9. Pour
situer : 48c **0,17 nm**, 35c **0,53 nm** — l'assemblage est moins bon que les deux.

⚠️ **Portée** : une graine, une partition (32/66 choisie en tiers égaux **avant** de savoir
que la longueur n'est pas le critère), un composant. Rien ne dit que cette partition soit la
bonne — c'est ce que le pavage doit chercher.

#### 🔑 LA MÉTHODE D'ASSEMBLAGE — validée, et à réutiliser telle quelle

`scripts/assemble_testglass.py`. Elle vaut plus que ce résultat, parce qu'elle mesure la
**pièce** sans dépendre de la Phase A.

| # | Règle | Pourquoi, et ce qu'elle évite |
|---|---|---|
| 1 | **Aucun tirage n'est refait** | On concatène les épaisseurs **réellement simulées** de chaque campagne. Refaire un tirage introduirait un aléa neuf et détruirait ce qu'on mesure : les erreurs *commises*, sans compensation croisée. |
| 2 | **Même graine pour les trois campagnes** | `index_seed` est une **fonction pure de la graine** (`certus_strat_robustness.py:1502`), donc les trois partagent la réalisation du corridor d'indice — la physique d'**un seul dépôt**, où seul le monitoring repart à zéro. 🔴 Trois graines indépendantes **moyenneraient** une erreur systématique commune aux 99 couches et rendraient un SEEL **trop beau**. |
| 3 | **On note avec le code de production** | `compute_batch_rmse` reçoit les épaisseurs concaténées : l'assemblage est jugé par la fonction qui juge toutes les stratégies du dépôt. Aucune physique réimplantée, aucune surface de bug nouvelle. ⚠️ Son 7ᵉ argument n'est **pas** un tableau de parité mais la **matrice des indices par couche et par λ**, et `nH`/`nL` s'y passent **vides** (`:2460-2467`). |
| 4 | **Faisabilité et spectre sont DEUX mesures** | La faisabilité s'établit **campagne par campagne** — chacune sous 5 % de plantage. Le spectre s'établit **sur l'assemblage**, qui ne porte aucun taux de plantage puisqu'aucun monitoring n'y tourne. Les confondre est l'erreur qui a coûté la journée du 2026-08-15. |
| 5 | **On prend la stratégie DÉPOSABLE, pas `strats[0]`** | Sur le sous-empilement B, la mieux notée plante à **98 %** alors que **54** ne plantent jamais. On retient la mieux notée **parmi celles sous 5 %** — ce qu'un opérateur choisirait. |

🔴 **LE CONTRÔLE QUI VALIDE L'ASSEMBLAGE, et il n'est pas optionnel.** Avant tout chiffre :
concaténer les épaisseurs **nominales** des trois parties et exiger qu'elles reproduisent
celles du 99c. Mesuré : **écart 0,000e+00 sur les épaisseurs ET sur le spectre.**

> ⚠️ Ce contrôle a d'abord été écrit comme `T(nom)` contre `T(nom.copy())` — une
> **tautologie**, qui ne pouvait que passer. **Un faux contrôle est pire que pas de
> contrôle** : il donne la confiance sans la vérification.

#### Ce que les sous-empilements ont appris, et qui réfute une hypothèse

| | couches | stratégies déposables | plantage retenu |
|---|---|---|---|
| A | 0-31 | 23 / 166 | 0 % |
| B | 32-65 | **54 / 126** | 0 % |
| C | 66-98 | **156 / 163** | 0 % |

🔑 **Ce n'est pas l'ÂGE du témoin qui gouverne.** C, le **dernier** tiers — celui où le 99c
complet n'a plus qu'**une** λ viable — est le **plus facile** des trois sur verre nu : 156
stratégies déposables sur 163. La monitorabilité est une propriété **du sous-empilement**,
pas du nombre de couches déjà portées.

#### 🔴 POURQUOI LE 99c AVEC CHANGEMENTS DIRECTS RESTE À ~100 % — l'implantation est à moitié faite

`witness_reset_layers` n'existe que dans **trois** fichiers : `certus_strat_robustness.py`,
`certus_strat_batch.py`, `certus_strat_growth.py`. **`certus_strat_objectives.py`, où la
Phase A fabrique les λ candidates, n'en sait rien** — `build_M_before_cache` construit ses
matrices depuis la **couche 0** sans notion de changement.

Les candidates sont donc choisies pour un témoin **mourant**, puis évaluées sur un témoin
**neuf**. Mesuré : 99c à 32/66 rend min 98 % et **11 blocs** contre 3, tandis que le témoin
déséquilibré 10/20 rend 100 % et 4 blocs — **le mécanisme agit et la qualité de la partition
compte**, mais les λ sont choisies sur le mauvais objet optique.

⚠️ **Donc « 98 % » ne réfute pas la méthode : il teste une demi-implantation.** L'assemblage
de §25.8 contourne le problème, il ne le corrige pas.

### 25.9. 🔴 CE QUE L'ANALYSE CONTRADICTOIRE A CORRIGÉ — parades adoptées

Une analyse contradictoire indépendante de §25 a été produite le 2026-08-15
(`reports/proposition.html`). Elle a **lu le code**, pas seulement le plan :
`certus_strat_batch.py:424` et `MAX_LOOKBACK_VAL = 4` sont cités exactement. Quatre de ses
attaques portent, et les parades ci-dessous sont **contraignantes**, pas indicatives.

| # | L'attaque, et elle est juste | La parade, obligatoire |
|---|---|---|
| **1** | 🔴 **Cinq prédicteurs sur ~10 points de mesure = sélection post-hoc.** §25.5-T5 listait cinq règles candidates à corréler **après** le balayage. *« Le plan trouvera une règle, forcément. »* | **UN SEUL prédicteur, déclaré par écrit AVANT de mesurer.** S'il échoue, on peut en essayer un second — mais en le déclarant **exploratoire**, jamais confirmatoire. Rapporter le meilleur de cinq est du p-hacking déguisé en physique. |
| **2** | 🔴 **T3 est circulaire.** « Geler un champ d'erreur réaliste » ne dit pas **lequel**. Or le seul champ qui ait un sens physique est celui que produit le Monte-Carlo — donc un prédicteur « gratuit » qui a besoin du Monte-Carlo pour être calibré **n'est pas gratuit**. | **Écrire le champ d'erreur AVANT de l'exécuter**, et assumer qu'un champ i.i.d. mesure un dépôt **sans monitoring**, ce que personne ne fait. Si le champ ne peut pas être justifié : **abandonner T3**, ne pas le maquiller. |
| **3** | **« Dommage spectral » n'est pas un scalaire.** RMSE, décalage de λ₀, élargissement de bande donnent **trois classements différents** des positions. | **Documenter la norme choisie avant de mesurer.** Une norme choisie après coup choisit son gagnant. |
| **4** | 🔴 **La marge peut être aussi plate que le plantage.** A23 a validé la marge comme prédicteur sur des empilements à plantage **faible**. À 100 %, les marges seront uniformément catastrophiques. | **Vérifier que la marge a un gradient AVANT de fonder P0 dessus.** Regarder la **pire marge**, pas le décompte des couches insuffisantes — le décompte saturera à 99. |
| **5** | **Le forçage de frontière de bloc détruit aussi les ancres POEM**, second mécanisme de perte jamais quantifié séparément du premier. | Borné à 4 couches (`MAX_LOOKBACK_VAL`) contre un coût de compensation **non borné** : acceptable en première approximation. ⚠️ Mais si la recherche rend un **plateau**, c'est ce terme-là qui départagera, et il n'est pas instrumenté. |
| **6** | **Le budget n'est chiffré nulle part.** Le balayage réel coûte 30 à 50 runs, soit 8 à 12 h, sans marge pour les reprises. | **Figer le nombre de runs avant de commencer.** 🟢 L'assemblage de §25.8 le divise par ~10 : trois runs de ~2 min au lieu d'un run de 15 min par position. |
| **7** | **Le nombre de positions du carrousel n'est écrit nulle part**, alors qu'il plafonne l'espace de recherche. Si le carrousel a 3 positions, tester 4 témoins est **physiquement impossible**. | 🔴 **Question ouverte à 👤.** Ne pas planifier de partition avant la réponse. |

#### Ce que la mesure du 2026-08-15 a rendu caduc dans cette analyse

Elle a lu §25 **avant** l'assemblage. Trois de ses attaques visent des étapes qu'on n'a plus
besoin de faire :

| son attaque | pourquoi elle tombe |
|---|---|
| *« le balayage mesure la coupure COMPOSÉE avec la réponse du solveur »* | Vise T4. L'assemblage (§25.8) résout chaque campagne **indépendamment sur son propre objet optique**, puis compose. Le confondage n'y est pas le même. |
| *« la désaturation (P0) est un pari sans procédure de repli »* | Par l'assemblage il **n'y a plus rien à désaturer** : chaque campagne est déjà à **0 %** de plantage, avec 23, 54 et 156 stratégies déposables. |
| *« 8 à 12 h de balayage »* | Facteur 10 en moins par l'assemblage. |

⚠️ **Mais ses attaques 1 à 4 ne visent pas T4 en particulier** — elles visent **toute recherche
de règle générale**, y compris celle qui reste à faire. Elles s'appliquent intégralement.

#### Deux objections au MODÈLE, pas à la méthode — et elles restent ouvertes

**Le changement de témoin est modélisé comme instantané.** La rotation du carrousel prend du
temps. Obturateur ouvert, la pièce reçoit de la matière non comptée ; obturateur fermé, la
source dérive thermiquement. Ni l'un ni l'autre n'est dans le noyau. **Non mesuré, non
modélisé.**

**« Témoin et pièce reçoivent la même épaisseur » n'est pas quantifié.** 👤 a répondu *« à peu
près identiques »* (§25.2), et j'en ai déduit qu'aucun facteur d'uniformité n'était à
modéliser. ⚠️ **Un rapport de 0,97 — courant sur un bâti à rotation planétaire — ferait dériver
la pièce d'environ 1,5 quart d'onde sur 50 couches**, et c'est un biais **systématique que le
monitoring ne corrige pas** : il corrige l'erreur du témoin, pas celle de la pièce. Il
s'ajouterait à l'erreur gelée. 🔴 **Question à 👤 : ce rapport est-il mesuré sur ta machine ?**

### 25.10. 🟢 SYNTHÈSE DU 2026-08-15 — ce que la journée a établi, réfuté, et laissé ouvert

**Lis cette section avant tout le reste de §25.** Elle remplace les conclusions provisoires
qui la précèdent quand elles divergent.

#### Ce qui est ÉTABLI par la mesure

| # | Fait | Preuve |
|---|---|---|
| 1 | **Le 99c n'est pas fabricable en une seule campagne.** Les **487** stratégies plantent à **100 %** — pas la retenue, **la meilleure**. Le « 0,86 nm » qui circulait est un **score de repli**, inatteignable. | distribution complète des taux de plantage |
| 2 | **Le multi-témoins le rend fabricable.** 3 campagnes à **0 %** de plantage chacune, assemblage à **0,760 nm**. 🔑 **Il ne fait pas gagner en précision — il fait passer d'IMPOSSIBLE à POSSIBLE.** | 386 partitions assemblées |
| 3 | **Le découpage ne gouverne presque rien.** Étendue **+14,4 %** sur 386 partitions, soit moins de 3 unités de résolution ; **110 partitions à égalité** avec la première. | résolution 5,1 % en SEEL à N=50 |
| 4 | **Le nombre de témoins ne compte pas.** 2 témoins 0,783 nm, 3 témoins 0,760 nm : **+3,0 %**, sous la résolution. **La vague à 4 témoins est abandonnée par la donnée**, pas par manque de temps. | idem |
| 5 | **Presque tout sous-empilement est monitorable sur verre nu** : **248 sur 249**. Un seul infaisable, `[22,78)`. | campagne des intervalles |
| 6 | 🔑 **Ce n'est PAS l'âge du témoin qui gouverne.** Le **dernier** tiers du 99c — là où, en campagne unique, il ne reste qu'**une** λ viable — est le **plus facile** des trois sur verre nu : 156 stratégies déposables sur 163. | A 23/166, B 54/126, C 156/163 |
| 7 | 🟢 **CONTRÔLE NÉGATIF PASSÉ, sur TROIS composants.** Là où le monitoring marche déjà, **toute** partition dégrade : **+73 à +89 %** sur le 48c (11/11), **+10 à +98 %** sur le 35c (12/12), **+110 %** sur le 75c aléatoire (0,272 → 0,571 nm). **Aucune ne gagne, même par chance.** | 40 sous-empilements |
| 8 | 🔑 **LA BARRIÈRE N'EST PAS LE NOMBRE DE COUCHES, C'EST LA STRUCTURE.** Un empilement **aléatoire de 75 couches** se surveille d'un bout à l'autre en **une seule campagne** : **241 stratégies déposables sur 662, plantage 0,0 %, SEEL 0,272 nm**. 75 passent, 99 non. Le modèle « au-delà d'une cinquantaine de couches le témoin meurt » est **réfuté**. | `reports/controle_random75/REFERENCE_0_75.json` |

Le point 7 est le plus important du lot : **si une seule de ces partitions avait gagné, tout
le reste tombait.** Le point 8 est celui qui recadre le chantier : ce qu'on combat n'est pas
une longueur, ce sont les **espaceurs à swing nul** et les **miroirs sous 10⁻⁴** (§25.1).

#### Ce qui est RÉFUTÉ

| hypothèse | verdict |
|---|---|
| « le témoin vieillit et meurt, donc changer vers 50 couches » | ❌ **deux fois** : le dernier tiers du 99c est le plus facile (point 6), **et** 75 couches aléatoires se surveillent en une campagne (point 8) |
| « c'est l'épaisseur optique accumulée qui décide » | ❌ elle **brouille** le signal : l'effondrement se voit à 54-56 **couches**, pas à 54-56 QWOT |
| « c'est le nombre d'espaceurs traversés » | ❌ 1, 2, 3 → 131, 160, 112 stratégies, sans tendance |
| « c'est la position de fin par rapport à un espaceur » | ❌ 11 % de fragiles dans la tranche, mais **82 intervalles sains** y finissent aussi |
| « c'est le nombre de couches » | 🟠 **localise sans déterminer** : les fragiles sont tous à 48-60 couches, mais seul **un tiers** des intervalles longs sont fragiles |

⚠️ **Quatre hypothèses testées après coup sur les mêmes données.** Chaque test de plus
augmente la chance qu'une colle par hasard. **Ne pas continuer à pêcher** — la suite demande
une grandeur nouvelle, pas une relecture.

#### Ce qui reste OUVERT

**La sensibilité par couche est le meilleur candidat, et il n'est pas validé.**
`S(j)` = dégât spectral d'une perturbation de 1 nm sur la couche *j*, en **TMM pur**, sans
Monte-Carlo et **sans rien savoir de la famille du filtre**. Le mécanisme est précis : changer
en `p` **gèle l'erreur de la couche `p−1`** sans compensation possible.

| composant | contraste de sensibilité | corrélation `S(p−1)` ↔ SEEL |
|---|---|---|
| 99c, 5 cavités | **82×** | **+0,69** (r² = 0,48) |
| 35c, 3 cavités | 24× | +0,20 |
| 48c, dichroïque | 14× | +0,25 |
| **75c aléatoire** (graine 2026, aucune structure) | **11,3×** *(mesuré)* | **−0,19** — dans le bruit |

🔴 **RÉSULTAT DU 2026-08-15, ET IL EST NÉGATIF AU SENS UTILE : le test n'a pas tranché.** Le
random75 avait été construit pour séparer « la règle a besoin d'un fort contraste » de « le
+0,69 tenait à la structure du 99c ». Il ne le peut pas : son contraste est de **11,3×**, le
**plus bas des quatre**, sept fois moins que le 99c. Une corrélation faible y est compatible
avec les deux lectures. Avec 18 points il faudrait `|r| ≥ 0,47` pour sortir de zéro à 5 %.
**Détail, définitions de `S`, et l'expérience qui trancherait : §25.4.**

🔑 **Et c'est bien `S(p−1)` qui compte** — la couche **gelée** — pas `S(p)` (r = +0,23) ni une
moyenne locale (r = +0,45). Le mécanisme prédit exactement ça.

⚠️ **La règle ne se transfère pas en l'état.** Deux lectures restent possibles et le 75c
aléatoire les départage : soit elle ne mord qu'à **fort contraste**, soit le +0,69 du 99c
était une **coïncidence** sur 13 points médians et confondus. Si les quatre points s'alignent
sur une relation monotone contraste ↔ pouvoir prédictif, la première devient une observation.

**Et le facteur limitant n'est pas là.** 0,760 nm contre **0,300** visés : facteur 2,5, avec
un écart meilleur/pire presque du bruit. Le levier pour la cible de 👤 **n'est pas le
découpage** — il est dans l'erreur intrinsèque de chaque campagne.

#### 🔴 Les cinq défauts d'INSTRUMENT trouvés dans la journée, et ils étaient tous silencieux

Aucun ne produisait d'erreur. Tous rendaient des nombres plausibles.

| défaut | comment il a été attrapé |
|---|---|
| `--mode fast` **jamais appliqué** — `run_workflow` rappelle `collect_params` et jette le dictionnaire modifié | la configuration **appliquée** consignée à côté de la demandée |
| le plan de changement et la fente figée, **même cause** | deux runs censés différer rendant un score **bit-identique** |
| ma vérification **relisait le dictionnaire jeté** — circulaire, elle validait tout | rien ne l'a attrapée : je l'ai vue en la relisant |
| `strats[0].crash_rate` lu comme « le plantage du run » — a produit un « B échoue à 98 % » **faux**, alors que 54 stratégies ne plantaient jamais | la **distribution** au lieu du premier élément |
| le contrôle d'assemblage écrit comme `T(nom)` contre `T(nom.copy())` — une **tautologie** | relecture avant de l'utiliser |

> 🔴 **Un faux contrôle est pire que pas de contrôle : il donne la confiance sans la
> vérification.** Et **une vérification qui relit sa propre entrée ne vérifie rien.**

⚠️ **Un défaut de PHYSIQUE, du même genre** : à graine commune — ce qu'il faut pour partager
la réalisation d'indice — le bruit de lecture des campagnes était **corrélé à 78 %**. Corrigé
en le traitant comme **un flux continu dont chaque campagne lit sa tranche** : **1 %**. Les
mesures d'avant ce correctif ne sont pas comparables à celles d'après.

#### T7 — Changements de témoin multiples

Une fois un changement de témoin comprise, récurrence : *n* campagnes de monitoring, chacune partitionnée
en blocs. La partition devient **à deux niveaux**, et elle se compose avec la recherche par
blocs déjà en place (§17-43). Ne pas ouvrir T7 avant que T5 ait rendu une règle.

---

### 25.11. 🔴 SOIRÉE DU 2026-08-15 — le mécanisme d'échec, et trois affirmations du projet réfutées

**Lis cette section avant §25.8 et §25.10 : elle les corrige là où elles divergent.**

#### Le mécanisme d'échec, décodé et non plus supposé

Cause des plantages, décodée depuis la sentinelle du noyau (`k × 1e6 + épaisseur nominale`,
`certus_strat_growth.py:82-89`) sur 282 couches-tirages du 99c :

| cause | part |
|---|---|
| **`TP_MISCOUNT`** | **83,0 %** |
| `LEVEL_UNREACHABLE` | 17,0 % |
| `NON_MONOTONIC` | 0,0 % |

🔴 **`strat.html` §10.15 affirme que le 99c plante en `CRASH_LEVEL_UNREACHABLE`. C'est faux.**

🔑 **Mais `TP_MISCOUNT` est le SYMPTÔME, pas la cause.** 👤 : *« ma machine de dépôt y arrive
très bien, même s'il y en a beaucoup ! C'est simplement la marge et les swing qui peuvent à la
rigueur poser problème. »* Il a raison, et c'est mesuré. Sur la série d'échelle du random75 :

| | sursauts émis | médiane / hystérésis | **sous 1,5× hyst** | **T_min médian** | verdict |
|---|---|---|---|---|---|
| ×0,5 | 217 | 29× | 🔴 **20,7 %** | 🔴 **0,029** | 0/375 |
| ×1 | 417 | 127× | 0,0 % | 0,162 | 🟢 241/662 |
| ×1,5 | 565 | 233× | 0,2 % | 0,230 | 1/440 |
| ×2 | **728** | 94× | 0,3 % | 🔴 **0,055** | 0/404 |

**Le ×2 a le PLUS d'extrema et le moins de sursauts marginaux, et il échoue.** Le nombre de
points tournants n'a aucun rapport avec la fragilité. Les deux causes réelles sont **la marge
du sursaut face à l'hystérésis** (×0,5) et **le plancher photométrique** (×0,5 et ×2).

📏 `scripts/serie_echelle_r75.py`, `reports/serie_echelle_r75/`.

#### Trois affirmations du projet, réfutées par la mesure

| affirmation | statut au 2026-08-15 |
|---|---|
| « les espaceurs demi-onde ont un swing optique nul, aucun extremum » | 🔴 **FAUX** — les 5 espaceurs du 99c offrent **65 à 133 λ utilisables** chacun. **Zéro couche muette sur 99**, médiane 79 λ. Le swing crête-à-crête d'une demi-onde n'est pas nul ; c'est son écart début-fin qui l'est. |
| « le 99c plante en `LEVEL_UNREACHABLE` » | 🔴 **FAUX** — 17 %, contre 83 % de `TP_MISCOUNT`. |
| « plus d'extrema ⟹ comptage plus fragile » *(écrit par moi le soir même)* | 🔴 **FAUX** — testé : à 64 points le comptage est **identique** à celui de la densité machine (0,125 nm) pour ×0,5 / ×1 / ×1,5 / ×2. Pas d'aliasing. |

⚠️ **La densité d'échantillonnage reste néanmoins 17 à 127 fois plus grossière que la
machine** — 0,10 à 0,38 point/nm contre 8,0 (0,125 nm par tour à 4 Hz, §9bis-1). Sans effet
mesuré sur le comptage, mais c'est un écart au réel non maîtrisé, et le paramètre prévu pour
le corriger, `machine_sampling_dd`, reste **inatteignable** (A8).

#### 🔴 `n_deposables` N'EST PAS UNE MESURE DE FAISABILITÉ — ne le lis plus comme telle

👤 a repéré l'incohérence : *« pourquoi [0,50) est plus élevé que [0,48) ? »* et
*« comment [0,68) peut-il être déposable 39 fois alors que [0,66) ne trouve aucun ? »*

**L'argument qui tranche, et il est logique, pas empirique** : la surveillance de la couche
`i` ne dépend que des couches `0..i`. Donc `[0,50)` contient exactement l'histoire de
`[0,48)`, et **aucune difficulté physique de [0,48) ne peut disparaître dans [0,50)**. Une
inversion est donc impossible sans défaut d'instrument.

**Le défaut** : `n_strats` est produit par la DP de Phase B, qui optimise un coût et ignore le
plantage. Il varie **d'un facteur 2** entre longueurs voisines — 205 à `[0,48)`, 412 à
`[0,52)`. Le dénominateur bouge autant que le numérateur.

🟢 **Ce qui reste valide : le TAUX, en tendance sur beaucoup de points.** Sur 270 intervalles,
`r = −0,869` entre la longueur et le taux, et l'effondrement est monotone :

| couches | 20-29 | 30-39 | 40-49 | 50-59 | 60-69 | 70-99 |
|---|---|---|---|---|---|---|
| taux moyen | **96,4 %** | 81,8 % | 57,3 % | 29,5 % | 2,7 % | **0,7 %** |

🔴 **Ne lis JAMAIS une cellule isolée, ni un écart entre deux longueurs voisines.**

#### 🔴 « AUCUNE_DEPOSABLE » NE VEUT PAS DIRE « INFAISABLE »

**Prouvé, logiquement puis expérimentalement.** `[0,66)` déclarait 0 déposable en fast alors
que `[0,68)`, `[0,70)`, `[0,72)` et `[0,74)` en avaient — or tronquer l'une d'elles après la
couche 65 donne une stratégie valide pour `[0,66)`. Vérification :

| mode | stratégies | déposables | plantage min |
|---|---|---|---|
| fast (campagne) | 319 | **0** | 100 % |
| **premium** | 488 | **1** | **0,0 %** — SEEL 0,658 nm |

⚠️ **Conséquence sur §25.8** : le « 248/249 déposables » et surtout le « seul sous-empilement
infaisable, `[22,78)` » ne sont **pas** des mesures de faisabilité. `[22,78)` est contredit
par `[22,99)` qui en a une. **5 intervalles sur 270 portent encore ce verdict** — tous à
revérifier en premium : `[0,66)` ✅ levé, `[0,76)`, `[0,78)`, `[22,78)`, `[34,99)`.

📏 `scripts/verif_66_vs_68.py`, `reports/verif_66_vs_68/`.

#### 🟢 Le résultat principal a été audité, et il tient

26 intervalles sur 270 contiennent des **tirages plantés** (2 à 4 %), qui se **cumulent** à
l'assemblage. Sur 440 partitions, **2 ont une P95 contaminée**. 🔑 **La gagnante
`0-22 / 22-72 / 72-99` est à 0,0 % de tirages plantés : le 0,760 nm n'est pas contaminé.**

⚠️ `classer_partitions.py` **ne vérifie pas** ce point. À ajouter avant tout nouveau classement.

#### 🔴 LE TROU ACTIONNABLE : la marge est calculée, exposée, et ne décide de rien

`turning_point_margins` (`certus_strat_growth.py:318`) rend deux marges par couche et par
tirage — `margin_missed` (un extremum à un cheveu de ne pas être vu) et `margin_fab` (à un
cheveu d'être inventé). Elles remontent en `all_m_missed` / `all_m_fab`
(`certus_strat_batch.py:542`), sont réduites en `margin_profile`
(`certus_strat_robustness.py:2036`) et exposées en `critical_layer` et `margin_by_layer`. Le
code porte ce commentaire :

> 🔴 **NEEDED FOR RANKING**

**Et aucun module de classement ne les lit** : zéro référence dans `certus_strat_ranking.py`,
`certus_strat_solvers.py`, `certus_strat_objectives.py`. La clé `rank_key_seel_yield_margin`
existe et est testée — elle ne tourne que dans `probe_anchor_noise_pipeline.py`.

🔑 **C'est la grandeur qui porte sur la cause réelle de 83 % des échecs.** Même classe de
défaut que `machine_sampling_dd` : calculée, documentée comme prédictive d'un facteur 22, et
sans effet sur aucune décision.

#### Ce qui a été testé et ne change rien

🟠 **Exiger un point tournant en Phase A : aucun effet.** `require_turning_point` implanté
(comptage O(1) par λ, désactivé par défaut), testé en **exclusion sèche** — le cas extrême :

| | OFF | ON |
|---|---|---|
| 48c | 0,1726 nm — 301/330 | **bit à bit identique** |
| 35c | 0,5251 nm — 248/254 | **bit à bit identique** |

Le paramètre atteint bien le calcul — vérifié par un test destructif (seuil 999 → pipeline
effondré en 2,4 s), donc ce n'est **pas** un `machine_sampling_dd`. Les candidates sans point
tournant sont sur des couches de **bord** (0 et 47), que le coût Monte-Carlo écartait déjà.
**Si l'exclusion sèche ne bouge rien, aucun coût doux ne le fera.** Réglé sur ces deux
composants ; **non testé** sur le 99c et sur les échelles extrêmes.

🟠 **La « phase intermédiaire entre A et B » proposée par 👤 existe déjà** : c'est la DP de
`_find_k_best_groupings_dp_sequential`, exacte et non heuristique. Rien à ajouter.

📏 `scripts/test_require_tp.py`, `scripts/probe_tp_admissibilite.py`,
`scripts/probe_turning_points.py`, `scripts/profil_monitorabilite.py`.
