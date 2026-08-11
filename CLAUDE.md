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

**1. Vérifie que tu es dans le bon dossier.**

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

Le chemin affiché **doit** commencer par `C:\dev\gemini`.
Si ce n'est pas le cas → **ARRÊTE-TOI. Signale-le. Ne modifie rien.**

**2. Vérifie que committer ne publie rien.**

```bat
dir .git\hooks\post-commit*
```

Doit afficher `post-commit.DESACTIVE`.
Si c'est `post-commit` tout court → **NE COMMITTE PAS.** Il pousse vers un dépôt **public**.

**3. Vérifie que tout est vert avant de toucher à quoi que ce soit.**

```bat
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Attendu : `All checks passed!` puis `2310 passed, 5 skipped`.
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
| **Commencer une action** | **§12** — les 6 actions, avec fichier, fonction, code, commande et résultat attendu |
| Savoir ce qui est interdit | §1 — les onze interdits |
| Savoir dans quoi tu vas tomber | §2 — les sept pièges |
| Savoir comment travailler | §3 — la boucle et la règle d'or |
| Toucher à du calcul optique | §6 — conventions physiques et oracle TMM |
| Comprendre la machine de dépôt | §9 — les spécifications du physicien |
| **Savoir ce qu'on suppose de la machine** | **§9bis — le modèle FIGÉ de la chaîne de lecture. Ne pas le rouvrir.** |
| Comparer un résultat | §10 — le point de référence |
| Comprendre un mot du projet | §7 — vocabulaire |
| **Savoir où en est réellement T1…T7** | **§17 — audit du 2026-08-09. À lire avant toute action de §12.** |
| Comprendre le mode Rate | §14, dernier bloc — spécification 👤, non implémentée |
| Vérifier le travail d'un autre agent | §20 — protocole de re-vérification |

Une seule autre page existe, destinée à la communauté :
[`pages/CERTUS_STRAT.html`](pages/CERTUS_STRAT.html) — algorithmes, équations, méthode.
Elle ne contient aucune instruction.

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
| `tp_hysteresis_factor` | **0,354** = `1/√8` — jamais 1,66, jamais 3 | §9bis-4 |
| Retard de déclenchement | **aucun** — ne rien ajouter | §9bis-5 |
| `phase_a_level_margin_factor` | **1,66** actuel, **3,33** à évaluer | §9bis-6 |
| Quantification de l'arrêt | `U(0 ; 0,125 nm)` | §9bis-7 |
| `index_corridor` | **0,005**, unités d'indice **absolues**, demi-largeur | §12.3 |
| `affine_scale_amp` | **0,05** ⇒ `a ∈ [0,95 ; 1,05]` | §12.1 |
| `affine_offset_amp` | **0,02** ⇒ `b ∈ [−0,02 ; +0,02]` | §12.1 |
| Plafond du banc | `CERTUS_BENCH_TIMEOUT_S=5400` | §10 |
| Graine de référence | **42**, `scan_wl_step` **1.0** | §10 |
| `sigma_rate` (mode Rate) | 🔑 **aucune valeur à poser** — grandeur DÉRIVÉE du simulateur | §14, dérivation |
| Résolution du monochromateur | **2 nm** nominal · choix dans {5 ; 2 ; 1 ; 0,5} · facteurs de bruit **÷1,5 · ×1 · ×2 · ×5** | §12.7 |

**Tout nouveau paramètre vaut sa valeur INACTIVE par défaut** (1 pour la fenêtre, 0 pour les
amplitudes et le corridor). Le chemin inactif doit rendre les mêmes bits qu'avant. Toujours.

---

## ⚡ FEUILLE DE ROUTE — 22 actions, dans cet ordre, une par une

**Établie le 2026-08-09**, après l'audit de §17. Elle **remplace** l'ancien tableau T0–T7, qui
présentait comme à faire du code déjà écrit et comme faites des mesures qui ne l'étaient pas.
La correspondance avec les anciens numéros est donnée en colonne.

### Les trois règles qui fixent cet ordre

1. **Une sonde bon marché qui peut invalider un gros travail passe AVANT ce travail.** Le
   palier 0 coûte des minutes et décide de plusieurs jours.
2. **Rien de comparatif avant que le repère soit rétabli.** Tant que A7 n'est pas faite,
   aucun `RESULT` ne se compare à aucun autre.
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

### ✅ État au 2026-08-10 — ce qui est FAIT, ne le refais pas

| Action | État | Ce que ça a donné |
|---|---|---|
| **A1, A2** | ✅ `e3a4c72` | A1 **réfute** le seuil dérivé de §9bis. **A13 doit utiliser `1,00`, pas `0,354`.** A2 passe. |
| **A7 (ex-T0)** | ✅ **repère rétabli** | `D0.ref` du 2026-08-10 : **`0.0027329534107462224`**, SEEL **0,3 nm**, gagnante 2 blocs. `0,002898` est définitivement écarté. |
| **A12** | 🟢 **FAITE — POEM validé ×17,5** | §12.1. Le critère de réussite posé à l'avance est atteint. |
| **A15** | ✅ faite | La marge 3,33 rend un résultat **bit-identique** à 1,66 : **elle ne rejette rien** (§17-12). |
| **A14** | ✅ **FAITE** | Courbe corrigée du 2026-08-10 : ×1,24 / ×1,86 / **×2,46** / ×4,32, exposant **0,525**. Les chiffres d'avant étaient gonflés de 1,6 à 2,1× par la normalisation fautive. |
| **A6** | ⚠️ requalifiée | Le banc **est** déterministe. Reste à savoir si une **recompilation** décale les bits — voir §3. |
| **A10** | ✅ **FAITE** | Le corridor atteint la notation. Courbe corrigée en §17-13. |
| **A20** | 🟢 **FERMÉE pour ce cas** | L'entonnoir **ne fuit pas** — §17-27. |
| **Campagne `full`** | ✅ **22/22 OK, 2026-08-11** | `reports/CAMPAGNE_RESUME.md`. Le résultat de tête est §17-26. |

### ✅ Fait le 2026-08-11 — ne le refais pas

| | |
|---|---|
| **§17-20, 23, 24, 25** | ✅ corrigés — `2b5d7a6`, `c8ac1fd`, `4cead53`. Tests contre-vérifiés sur worktree baseline. |
| **A23 étage 0** | ✅ le plantage **par couche et par cause** et le swing de la couche la pire remontent dans les rapports. Premier résultat : §17-31. |
| **Campagne E** | ✅ 12/12 — porte C1 franchie, corridor et POEM confirmés (§17-29, 30, 31, 32). |

### ✅ Fait le 2026-08-11, seconde session

| | |
|---|---|
| **§17-37 outillé** | `n_layers_forced` remonte dans le résultat, le JSON de sonde et une **colonne** du résumé de campagne. Vérifié de bout en bout : graine 77, corridor 0,02 → **18 couches forcées sur 48**, 58 % de plantage. Une stratégie subie n'est plus indiscernable d'une stratégie libre. |
| **A23 étage 2** | ✅ **câblé** — le noyau rend `margin_level`, `margin_missed`, `margin_fab` par (tirage, couche) ; la robustesse en tire `critical_layer` avec sa cause en mots physiques et son verdict. Vérifié sur un vrai batch : marges de niveau **4,87 / 17,94 / 18,35 / 47,00 A** par couche, verdict **« impossible »** à 4,87 A puisque > 2 A. |
| **Tri de §14** | ✅ **écrit comme fonction pure et testé** — `rank_key_seel_yield_margin`, demi-largeur `max(0,05 nm ; 0,06 × SEEL)`. Appliqué dans la **sonde**, sous `ranking_seel_rule`, **à côté** de l'ordre du pipeline et non à sa place : SEEL vit à l'étape 0 de l'interface, l'en sortir est l'action 1 de §14. Les deux ordres sont donc comparables sur un même run avant qu'on ne bascule. |

> 🔴 **Une correction en cours de route qui vaut d'être retenue.** J'avais fusionné les
> deux causes de comptage en `min(manque, fabrication)`. Mesure : le nombre saute de
> **0,15 A à 505 A** entre deux niveaux de bruit — facteur 3000 — uniquement parce que
> la **cause qui lie bascule**. Physiquement réel, et illisible. §A23 l'écrivait déjà :
> *une marge par couche ET par cause*, parce qu'une ondulation faible se soigne en
> déplaçant la λ et un extremum inventé en montant le seuil. J'ai suivi le document
> plutôt que mon raccourci.

> 🔴 **La leçon de méthode de cette session, et elle vaut pour tout instrument.**
> `turning_point_margins` a été **fausse quatre fois**, et chaque version rendait des
> nombres parfaitement plausibles en ne mesurant rien : un segment terminal lu comme
> quasi-fabrication (marge **négative**, donc impossible) · les extrêmes à demi
> réinitialisés du détecteur réutilisés (**sentinelle sur toute entrée**) · l'ondulation
> mesurée au moment de l'émission, où elle vaut le seuil **par construction** (marge ~0
> que l'ondulation fasse 1,2× ou 100× le seuil) · et un garde unique qui tuait le cas de
> fabrication le plus intéressant.
> **Aucune des quatre n'a été attrapée par une valeur suspecte. Les quatre l'ont été en
> BALAYANT la grandeur que la marge est censée suivre.** C'est le Piège 1 appliqué à un
> **instrument** au lieu d'un résultat — et un instrument faux est pire qu'un résultat
> faux, parce qu'il contamine tout ce qu'on mesurera ensuite avec.

### 🔴 La suite immédiate

0. 🔑 **LA QUESTION QUI DÉCIDE SI TOUT CECI SERT : la marge sépare-t-elle les dix
   ex æquo à `SEEL = 0,3 nm` ?** §17-26 les a mesurées à moins de 2 σ les unes des
   autres, toutes à 0/150 plantages. **Si la marge les sépare, on a un classement
   là où il n'y en avait pas. Si elle ne les sépare pas, l'étage 2 est un bel objet
   sans usage, et il faut l'écrire — pas le contourner.** Un run suffit.
1. **A23 étage 3 — calibrer la marge contre le niveau 2×.** ⚠️ **Zéro run** : les trois
   niveaux 0,5× / 1× / 2× sont déjà calculés dans chacun. À 2× les plantages sont
   comptables ; si le modèle de marge les prédit, on peut le croire à 1× où le comptage
   rend zéro. *On n'extrapole jamais sans avoir validé l'extrapolation là où la mesure
   est possible.* Sans cette étape, la couche critique est une opinion bien présentée.
2. **Basculer le classement sur la règle de §14**, une fois le point 0 tranché. La
   fonction existe et est testée ; ce qui manque est de **sortir SEEL de l'interface**
   (§14, action 1) pour que le pipeline puisse s'en servir. ⚠️ Ne bascule pas avant
   d'avoir comparé les deux ordres sur un même run — `ranking_seel_rule` est écrit à
   côté exactement pour ça.
3. **Comprendre l'effondrement de `n_ranked` avec le corridor** — 228 → 165 → 78 (§17-30).
   La Phase A élimine massivement quand l'indice est incertain, et personne ne sait sur quel
   critère. C'est le contrôle 4 de §20 : **compter les rejets**.
4. **§17-14 reste ouvert** — E2 a échoué faute de régime (§17-32).

---

### PALIER 0 — Quatre sondes qui ne coûtent rien et qui décident du reste

Aucune ne demande le banc, ni le repère, ni une machine libre. **Minutes chacune.** Elles
peuvent toutes être faites aujourd'hui.

#### A1 — La fabrication d'extrema sous lissage · *décide du sort de §9bis*

C'est **la** mesure qui valide ou détruit le modèle figé. Si elle échoue, ce n'est pas
l'action qu'on bricole, c'est §9bis qu'on rouvre.

- **Où** : script autonome dans `scripts/`, **aucun TMM**. Modèle : la sonde qui a déjà produit
  le tableau 32,9 % / 92,9 % / 99,9 % de §12.2.
- **Quoi** : signal propre **plat**, bruit réel `A = 5e-4`, **20 000 tirages**, `N = 800`
  échantillons, moyenne glissante **centrée** de `k` lectures, seuil `f·A`. Compter la
  fraction de couches où le bruit **fabrique** un point tournant.

| # | Étape | Attendu |
|---|---|---|
| 1 | **Reproduire d'abord une ligne connue** : `k = 1`, `f = 1,66`, `N = 800` | **99,935 %** |
| 2 | Si ce n'est pas ça → **la sonde est fausse, arrête-toi.** Ne va pas plus loin | — |
| 3 | `k = 8`, `f = 0,354`, `N = 800` | **~0 %** |
| 4 | Piège 1 : bruit ×0,01 à la config 3 | doit s'effondrer à 0 |
| 5 | Balayer `k ∈ {1, 2, 4, 8, 16}` avec `f = 1/√k` | courbe **monotone** en `k` |

🔴 **Condition d'arrêt** : si l'étape 3 ne rend pas ~0 %, **colle le chiffre et arrête-toi.**
**Ne remonte pas le seuil.** §12.2 le dit, et c'est le piège que ce projet a payé trois fois.

#### A2 — Les vrais extrema survivent-ils au lissage ? · *l'autre face, jamais mesurée*

Le lissage supprime les faux extrema. Rien ne prouve qu'il préserve les vrais.

- **Où** : même sonde, signal **propre sans bruit**, sur le juge de paix.
- **Quoi** : compter les points tournants détectés avec et sans lissage.

| # | Étape | Attendu |
|---|---|---|
| 1 | Signal propre, `k = 1` | `n_tp` de référence |
| 2 | Signal propre, `k = 8` | **`n_tp` identique** |
| 3 | Si (2) est inférieur | la fenêtre arrondit de vrais extrema → **elle est trop large, dis-le** |
| 4 | Balayer `k ∈ {8, 16, 32}` | trouver à partir de quel `k` un vrai extremum tombe |

#### A3 — La chute de swing sous fente de 5 nm · *tranche entre 1 h et plusieurs jours*

🔴 **Cette sonde a changé d'objet le 2026-08-10.** Elle mesurait « de combien le swing
baisse ». **Ce n'était pas le bon mécanisme** : l'OMS calcule ses niveaux attendus en
résolution parfaite, donc l'effet est un **biais de niveau**, pas une perte de dynamique.

- **Où** : script autonome, TMM nominal, juge de paix, **pas de Monte-Carlo**.
- **Quoi** : pour chaque couche et chaque λ_mon candidate, calculer
  `biais = ⟨T⟩_B − T(λ_mon)`, la fente étant **rectangulaire** (👤), pour `B ∈ {0,5 ; 1 ; 2 ; 5}` nm.

| # | Étape | Ce que ça décide |
|---|---|---|
| 1 | Comparer le biais à `A = 5e-4`, l'amplitude du bruit | c'est la seule échelle qui a un sens : le biais n'est pas absorbé par la statistique, le bruit si |
| 2 | Biais **≪ A** à 5 nm | la résolution ne coûte rien en fidélité ⇒ **prendre la fente la plus large**, et empocher le ÷1,5 de bruit |
| 3 | Biais **≫ A** dès 2 nm | le nominal lui-même est déjà biaisé, et **c'est un défaut du modèle actuel**, pas seulement un réglage |
| 4 | Rapporter la **couche la pire**, pas la médiane | c'est elle qui lie, cf. `worst_layer` |
| 5 | Vérifier que le biais varie en **`B²`** | c'est la signature du second ordre. S'il varie autrement, le développement ne tient pas à cette largeur |

⚠️ **Le signe compte.** `T'' > 0` près d'un minimum, `< 0` près d'un maximum : le biais pousse
donc toujours **vers l'intérieur de la courbe**. Près d'un point tournant, il déplace le niveau
dans une direction **connue** — ce qui le rend, en principe, corrigeable.

#### 🔴 Pourquoi c'est CRITIQUE, et pas un réglage de confort — 👤 confirmé le 2026-08-10

Le biais est proportionnel à la **courbure** `T''`. Or la courbure est **maximale en un point
tournant**, où `T' = 0` par définition. **Et un point tournant, c'est exactement ce que POEM
prend pour ancre.**

Trois conséquences qui s'enchaînent :

1. **Une fente large fausse les deux ancres sur lesquelles repose toute la méthode**, et elle
   les fausse **vers l'intérieur** — `T''` pointe vers le creux de la courbe de part et
   d'autre d'un extremum. Le swing mesuré `|T_last − T_prev|` **rétrécit**, et POEM applique
   sa fraction figée à une amplitude trop petite.
2. 🔴 **Ça casse le théorème d'invariance.** §12.1 démontre POEM exactement immune à
   `T → a·T + b` — une transformation **affine**, la même partout. Le biais de fente vaut
   `T → T + T''(λ)·B²/24` : il dépend de la **courbure locale**, donc il **diffère à chaque
   ancre et au point de déclenchement**. C'est précisément le type de distorsion que POEM
   **ne peut pas** absorber, contrairement à la dérive photométrique qu'il bat ×17,5.
3. Enfin, près d'un point tournant `dT/dd → 0` : une erreur de niveau s'y convertit en une
   **grande erreur d'épaisseur** — le régime dont §14-5 dit qu'il faut le fuir.

**Le biais, la pente la plus faible et les ancres du mécanisme se rencontrent tous au même
endroit.** C'est pour ça que la résolution n'est pas un réglage de second ordre.

⚠️ **Conséquence pour la mesure** : le contraste POEM actif / inactif ne dira **rien** de ce
défaut-là. POEM protège de l'affine ; ici il est complice, parce que ses ancres sont le point
d'application du biais. **Ne pas conclure de A12 que la résolution est couverte.**

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

#### A6 — Quantifier l'enveloppe de gigue du banc

*Remplace l'ancienne action « localiser l'écart de 2,5e-11 », **annulée** : cet écart était la
gigue elle-même. Bisecter l'aurait fait chercher une cause à du bruit.*

On ne peut plus dire « le chiffre a changé donc quelque chose est cassé » tant qu'on ne sait
pas de combien il bouge tout seul.

| # | Étape | Attendu |
|---|---|---|
| 1 | Rassembler les runs déjà faits à configuration **neutre** | `CONFIG=` identiques, vérifiés un par un |
| 2 | Calculer l'écart max relatif entre eux | c'est l'enveloppe |
| 3 | L'écrire dans §10, avec les valeurs brutes | — |
| 4 | Si un écart dépasse **1e-9** | ce n'est plus de la gigue de sommation. **Arrête-toi et signale.** |

📏 **Trois points déjà acquis** (2026-08-09, `CONFIG=` vérifiés identiques) :
`0.002948627371226749` · `0.002948627371309867` · `0.002948627371309867`.
Écart max relatif **2,8e-11**. Motif observé : le premier run après une invalidation des
caches numba sort du lot, les suivants s'accordent. **Trois points ne font pas une
enveloppe** — il en faut plus avant d'écrire un seuil.

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
| 7 | ✅ **fait le 2026-08-10** : §10 porte `D0.ref`, et `0,002898` est écarté | — |

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

#### A10 — Compléter T5 : perturber la NOTATION · *§17-10*

Le corridor atteint la croissance mais pas le score. Le mode **croisé**, celui que le
physicien décrit comme non compensable, est donc quasi invisible.

- **Où** : `certus/physics/certus_strat_batch.py`, `compute_batch_rmse` (~ligne 355), et son
  appelant `certus/core/certus_strat_robustness.py:954`.
- **Quoi** : passer `(a_H, b_H, a_L, b_L)` **par tirage** + la grille λ, et reconstruire
  l'indice à la volée — comme le fait déjà `simulate_growth_kernel`. **Pas** une matrice
  d'indices par tirage : trop de mémoire.

| # | Étape | Attendu |
|---|---|---|
| 1 | `index_corridor = 0` | empreinte **identique au bit** |
| 2 | `index_corridor = 0,005`, `b = 0` (décalage pur) | `RESULT` se dégrade **un peu** |
| 3 | `index_corridor = 0,005`, `a = 0` (croisement pur) | `RESULT` se dégrade **beaucoup plus** |
| 4 | Si (3) ≈ (2) | la prédiction du §12.3 est réfutée — **dis-le**, c'est un résultat |
| 5 | Si ni (2) ni (3) ne bouge | **Piège 1** : la perturbation n'atteint toujours pas le calcul |

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

#### A12 — POEM sous distorsion, 4 runs · *ex-T2, la seule action qui peut INVALIDER POEM*

`affine_scale_amp = 0.05`, `affine_offset_amp = 0.02`. Ces valeurs sont figées, n'en choisis
pas d'autres.

| # | Run | Variables |
|---|---|---|
| 1 | POEM on, distorsion off | `CERTUS_POEM_ENABLED=1`, amplitudes à 0 |
| 2 | POEM on, distorsion on | `CERTUS_POEM_ENABLED=1`, `CERTUS_AFFINE_SCALE_AMP=0.05 CERTUS_AFFINE_OFFSET_AMP=0.02` |
| 3 | POEM off, distorsion off | `CERTUS_POEM_ENABLED=0`, amplitudes à 0 |
| 4 | POEM off, distorsion on | `CERTUS_POEM_ENABLED=0`, amplitudes non nulles |

**Critère** : l'écart (2)−(1) doit être **beaucoup plus petit** que (4)−(3). C'est toute la
promesse de POEM. **Si ce n'est pas le cas, l'argument central du mécanisme tombe et il faut
l'écrire.** Séparer `CRASH_TP_MISCOUNT` et `CRASH_LEVEL_UNREACHABLE` dans le rapport —
l'asymétrie de `tp_hysteresis` sous distorsion peut fabriquer le premier.

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

#### A14 — Balayage du corridor d'indice · *ex-T5*

🔴 **Si A14 est lancée AVANT A10, elle mesure une moitié de l'effet, et il faut le savoir en
lisant le chiffre.** Le corridor atteint aujourd'hui la croissance mais pas la notation
(§17-10) : la dégradation observée ne viendra donc que des **épaisseurs faussées**, pas de
l'indice erroné du filtre fini. Le chiffre sera **sous-estimé**, et le mode croisé quasi
invisible. ⚠️ Ce n'est pas une raison de ne pas la faire : refaire A14 **après** A10 et
prendre la différence donne exactement la contribution du chemin de notation. Mais ne
présente jamais un A14 pré-A10 comme « l'effet du corridor ».

| # | Run | Attendu |
|---|---|---|
| 1 | corridor 0 | identique à A7 |
| 2 | corridor 0,0025 | dégradation |
| 3 | corridor 0,005 | dégradation plus forte |
| 4 | corridor 0,005, `b = 0` | décalage pur |
| 5 | corridor 0,005, `a = 0` | croisement pur — **attendu bien pire que (4)** |

#### A15 — Marge Phase A, 1,66 → 3,33 · *ex-T6*

Un run chacun. **Séparément du lissage** (C3). Rapporter aussi le **nombre de λ écartées** à
chaque marge — c'est A4-1 qui donne l'instrument.

---

### PALIER 4 — Le neuf

#### A16 — Quantification de l'arrêt · *ex-T7, §12.5*

Quasi gratuit une fois A8 faite : s'arrêter au **premier point de grille au-delà du seuil**
au lieu d'interpoler, et `U(0 ; 0,125 nm)` apparaît d'elle-même, sans paramètre.
**Vérification** : Piège 1 — si doubler `Δd_sample` ne change rien, la mesure est un artefact.

#### A17 — Résolution : le facteur de bruit · *§12.7, la partie triviale*

Table de 4 entrées, **jamais une loi**. 🔴 Le facteur multiplie **l'échantillon**, jamais la
graine — sinon les 4 résolutions voient 4 aléas différents et l'écart n'est plus imputable.

| # | Étape | Attendu |
|---|---|---|
| 1 | Résolution = 2 nm (nominal) | empreinte **identique au bit** |
| 2 | Les 4 résolutions, même graine | les tirages **normalisés** doivent être identiques ; seule l'amplitude change |
| 3 | 4 runs au banc | comparer plantage et erreur spectrale |
| 4 | 🔴 **Contrôle de sensibilité, obligatoire** : refaire (3) avec ÷1,2 et ×3 au lieu de ÷1,5 et ×5 | **la résolution gagnante doit être la même**. Les facteurs sont 👤 *estimés au feeling*, pas mesurés — une conclusion qui change avec eux n'est pas un résultat |
| 5 | Si les 4 se tiennent à moins que la dispersion Monte-Carlo | **la résolution ne mérite pas d'entrer dans la recherche** — fige-la à 2 nm et saute A18 |

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

#### A20 — La fuite de l'entonnoir Phase A → Phase B

**La question jamais posée** : la Phase A écarte-t-elle jamais une stratégie que la Phase B
aurait couronnée ? §8 exige d'elle exactement une chose — *« elle doit bien couvrir »* — et
personne ne l'a vérifié.

| # | Étape | Attendu |
|---|---|---|
| 1 | Relever la gagnante de A7 | référence |
| 2 | Construire des stratégies à partir de λ **rejetées ou mal classées** par la Phase A | échantillon |
| 3 | Les passer en Phase B | si l'une bat la gagnante, **l'entonnoir fuit** |
| 4 | Si aucune ne bat | la question est close, on n'en reparle plus |

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
4. **Jamais modifier `example/example_strat/JSON-strat-example.json`.** Il s'est écarté des
   valeurs correctes **quatre fois**, toujours dans le sens permissif, et chaque fois cela a
   coûté une session de diagnostic. Pour essayer autre chose, utilise
   `scripts\probe_anchor_noise_pipeline.py`, qui injecte les paramètres **après coup**.
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
| `utils` → `ui` | 12 | dont 3 au niveau module (`certus_curve_smoother.py:29-30`, `certus_export.py:13`) : importer ces modules charge PyQt6 |
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
| **point tournant** | Maximum ou minimum du signal de transmission pendant la croissance. |
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

## 10. Point de référence — tout se compare à lui

Obtenu par `scripts\probe_anchor_noise_pipeline.py full 1.0 42`.

```
Configuration : poem_anchor_noise = 1, tp_hysteresis_factor = 1.66,
                phase_a_level_margin_factor = 1.66, dp_yield_weight = 0,
                scan_wl_step = 1.0, index_corridor = 0, N = 150, screening = 25

  RESULT       0.0027329534107462224
  SEEL                           0,3 nm     erreur equivalente par couche
  gagnante            id 2228, 2 blocs
  plantage                     0,000
  RUN_S                       ~1071 s
```

**C'est le repère `D0.ref` de la campagne du 2026-08-10**, sur le code corrigé — corridor
côté notation (A10) et normalisation sur l'enveloppe. `RESULT` **est le `robustness_score`
de la gagnante**, vérifié au bit sur huit runs (§17-15 est close).

⚠️ **`RESULT` agrège les trois niveaux de bruit** (0,5× / 1× / 2×). Il est donc comparable
aux **scores** du classement, et **jamais** aux statistiques **par bande**, qui sont au niveau
nominal seul.

⚠️ **Tout repère mesuré avant le 2026-08-10 est périmé** — A10 et l'enveloppe ont changé le
calcul, et le changement de signature force en plus une recompilation (§3). Ne compare pas au
travers de cette date.

#### 🪦 Ce que remplace ce repère — pour mémoire, ne le cite plus

Ce document a longtemps cité **`RESULT = 0,002898`** avec « 345 stratégies rendues ».
**Aucun artefact ne l'a jamais porté** : les valeurs committées pour cette configuration
valaient `0.00294862737130071` puis `0.00294862737122675`, soit **+1,7 %** d'écart, et le
compteur de la sonde est plafonné à 12 par construction — 345 n'a jamais pu en sortir.

Le chiffre a servi de référence à des dizaines de comparaisons sans que personne n'ait pu le
reproduire. **Il est écarté définitivement.** Si tu le vois cité quelque part, c'est une
survivance.

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
| `tp_hysteresis_factor` | Seuil de détection d'un point tournant, en multiples de `A = trigger_tolerance/100`. Vaut **1,66** aujourd'hui. 🔒 **Valeur cible du modèle figé : 0,354** = `1/√k` avec `k = 8`, parce qu'elle s'applique au signal **lissé** — voir §9bis et §12.2. Injectable en 5ᵉ argument du script de sonde. |
| `reading_smoothing_window` | ⚠️ **Existe depuis `e0df0e1`**, défaut **1**. Fenêtre de moyenne glissante appliquée au signal de monitoring avant détection, **en lectures machine**. Valeur du modèle figé : **8** (2 s à 4 Hz). 🔴 **Dans l'implantation actuelle ce drapeau commande AUSSI la grille de §12.4** — voir §17. |
| `index_corridor` | ⚠️ **Existe depuis `162a0ff`**, défaut **0,0**. Demi-largeur du corridor d'incertitude d'indice, en **unités d'indice absolues**. Valeur du modèle : **0,005**. Jamais mesuré. |
| `affine_scale_amp` / `affine_offset_amp` | ⚠️ **Existent depuis `f7a3d71`**, défaut **0,0**. Amplitudes du tirage de dérive photométrique, une fois par run. Valeurs de mesure : **0,05** et **0,02** (§12.1). Jamais mesurées. |
| `poem_enabled` | ⚠️ **Existe depuis `f7a3d71`**, défaut **vrai**. Force le repli absolu quand il est faux. C'est le drapeau que §12.1 réclamait. Jamais mesuré. |
| `phase_a_level_margin_factor` | Marge exigée **en transmission** entre le niveau d'arrêt et les points tournants voisins. Active aussi la vraie matrice cumulée en Phase A. |
| `dp_yield_weight` | Poids du rendement dans l'objectif DP : `coût = coût_nm + w·(−log(1−p))`. |

## 12. Le travail à venir, dans l'ordre

> 🔴 **AVERTISSEMENT DU 2026-08-09 — lis §17 avant de reprendre une action de §12.**
> Le code de T1, T3, T4 et T5 **existe déjà**, mais **aucune** des mesures qui devaient le
> valider n'a été faite, la non-régression bit-à-bit ne tient pas, T3 est soudée à T4, et T7
> n'est pas écrit. Les descriptions ci-dessous restent exactes sur **ce qu'il faut obtenir** ;
> elles ne décrivent plus l'état du dépôt.

> **Chaque action donne : le fichier et la fonction exacts, ce qu'il faut écrire, la commande
> de vérification avec son résultat attendu, et les pièges connus.** Si une instruction te
> paraît ambiguë, c'est un défaut de ce document — ne comble pas par une hypothèse,
> arrête-toi et demande.

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

### 12.1 🔴 Rendre la distorsion affine atteignable, puis éprouver POEM

**Pourquoi en premier** : seule action pouvant **invalider POEM**, le mécanisme central de
STRAT. Tout le reste le suppose valide.

**Où on en est.** Le noyau est corrigé (`76f7a8f`) : il annulait son propre effet en trois
endroits, ce qui aurait fait conclure l'inverse de la vérité.

| Site | Défaut corrigé |
|---|---|
| Inversion parabolique | modèle **non distordu** résolu contre une cible **distordue** — unités mélangées |
| Repli absolu | `a·target_nominal + b` rendait au contrôleur l'étalonnage qu'il est censé avoir perdu |
| Test SWING | seuil mis à l'échelle par `a`, annulant le gain exactement |

📏 Avant : `a = 0,9574` déplaçait l'arrêt de **−6,60 nm** là où la théorie exige zéro.
📏 Après : invariance POEM à **2,19e-10 nm**, et le repli absolu devient sensible — il rend
`CRASH_LEVEL_UNREACHABLE` sous une chute de gain de 4,3 % sur une couche à faible contraste.

**Ce qui manque** : `affine_scale` et `affine_offset` ne sont dans la signature d'**aucun**
appelant. Le tirage n'existe pas.

#### Où, exactement

| Fichier | Fonction | Ce qu'il faut écrire |
|---|---|---|
| `certus/physics/certus_strat_batch.py` | `simulate_stack_robustness_batch` | Ajouter `affine_scale: float = 1.0, affine_offset: float = 0.0` en fin de signature, les passer au noyau. |
| idem | `validate_wavelengths_batch` | Idem. Phase A doit voir la même distorsion que Phase B, sinon les deux étages ne modélisent pas la même machine. |
| `certus/core/certus_strat_robustness.py` | `_execute_robustness_tasks` (~ligne 814-857, à côté du calcul de `tp_hysteresis`) | Tirer `(a, b)` **une fois par tirage** et les passer au batch. |

#### Le tirage

```python
# UNE FOIS PAR RUN, jamais par couche. Contrainte C2 : aucune entree de strategie.
z_a = _seeded_noise_sample(affine_stream_seed, 0, run_idx, 0, True)   # in [-1, 1]
z_b = _seeded_noise_sample(affine_stream_seed, 1, run_idx, 0, True)
affine_scale  = 1.0 + affine_scale_amp  * z_a     # amp par defaut 0.0 -> a = 1.0
affine_offset =       affine_offset_amp * z_b     # amp par defaut 0.0 -> b = 0.0
```

Deux nouvelles clés JSON, **0,0 par défaut** : `affine_scale_amp`, `affine_offset_amp`.

🔒 **Valeurs à utiliser pour la mesure T2, ne pas en choisir d'autres** :
`affine_scale_amp = 0.05` (donc `a ∈ [0,95 ; 1,05]`) et `affine_offset_amp = 0.02` (donc
`b ∈ [−0,02 ; +0,02]`). Ce sont les plages arrêtées de longue date pour cette action.

`affine_stream_seed` se dérive de la graine de tirage comme `_signal_noise_stream_seed`
(`certus_strat_robustness.py:840`) — **groupes distincts** (`0` et `1`) pour que gain et
offset soient indépendants, et un `seed_base` distinct de celui du bruit de lecture pour ne
pas corréler les deux phénomènes.

#### Vérification

```bat
:: 1. non-regression : amplitudes a 0, le RESULT doit etre IDENTIQUE au repere §10
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
:: attendu : le repere de 10 -- et PAS a travers le 2026-08-10, ou A10 et
::           l'enveloppe ont change le calcul (voir 3, recompilation)

:: 2. le critere de reussite : avec et sans POEM, sous distorsion
::    (necessite d'exposer un drapeau de desactivation de POEM, cf. piege ci-dessous)
```

**Critère de réussite** : mesurer **plantage** et **erreur spectrale** dans les quatre cas
— POEM actif / inactif × distorsion active / inactive. Si POEM tient sa promesse, l'écart
doit être **spectaculaire**. Sinon, l'argument central du mécanisme tombe et **il faut le
dire**.

#### 🟢 MESURÉ LE 2026-08-10 — POEM tient sa promesse, facteur 17,5

Campagne `scripts\run_campaign.py`, 4 bras, `amp_scale = 0.05`, `amp_offset = 0.02`,
graine 42, pas 1 nm. Les 4 runs `OK`, `CONFIG=` vérifiée bras par bras, **aucun écart entre
la configuration demandée et celle appliquée**.

| | distorsion absente | distorsion présente | **coût de la distorsion** |
|---|---|---|---|
| **POEM actif** | `0.002948627371309867` | `0.0029742829447752268` | **×1,0087** (+0,87 %) |
| **POEM inactif** | `0.005824599272270286` | `0.10256954814393225` | **×17,61** (+1661 %) |

$$\textbf{Facteur de protection de POEM} = \frac{17{,}61}{1{,}0087} = \mathbf{17{,}5}$$

**Le critère de réussite posé à l'avance était : « l'écart doit être spectaculaire, sinon
l'argument central du mécanisme tombe ». Il est de trois ordres de grandeur.**

Deux constats supplémentaires que personne n'avait demandés :

- **POEM inactif SANS aucune distorsion coûte déjà ×1,975.** Il ne protège donc pas seulement
  de la dérive photométrique : il compense aussi les erreurs d'épaisseur accumulées.
- Le pire cas complet — POEM inactif sous distorsion — vaut **×34,8** le meilleur cas.

#### 🟢 Confirmé sur une SECONDE graine le 2026-08-10 — avec une nuance à ne pas cacher

| graine | distorsion avec POEM | sans POEM | **protection** |
|---|---|---|---|
| **42** | ×1,009 | ×17,61 | **×17,5** |
| **77** | ×1,983 | ×30,18 | **×15,2** |

**La protection est reproductible : ×15 à ×17,5.** C'est le résultat, et il tient.

🔴 **Mais le dommage RÉSIDUEL dépend fortement de la graine.** À la graine 42 la distorsion ne
coûtait que **+0,9 %** avec POEM ; à la 77 elle coûte **+98 %**. **La graine 42 était un
tirage chanceux.** Ne cite jamais « +0,87 % » comme le coût de la distorsion — cite la
protection, qui est ce qui se reproduit.

🔴 **Ce que ces mesures ne disent PAS.** Elles portent sur `RESULT`, l'agrégat sur les trois
niveaux de bruit, sur le seul 48 couches. §15 reste entier : banc de cohérence, pas
validation physique.

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

### 12.2 🔴 Modéliser le LISSAGE de lecture — et surtout pas remonter le seuil

> **Cette action applique le modèle figé du §9bis.** Ne le rediscute pas : l'OMS est breveté,
> son fonctionnement interne restera opaque, et le postulat a été arrêté le 2026-08-08 pour
> clore la question. Les valeurs à utiliser sont `k = 8` et seuil `0,354 A`.

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

⚠️ **Ce 0,354 est une dérivation, pas une mesure.** La borne anti-fabrication d'un signal
lissé n'est pas calculable simplement : les échantillons voisins sont corrélés. **Il faut la
mesurer** — voir la vérification 2.

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

#### Où, exactement

| Fichier | Fonction | Ce qu'il faut écrire |
|---|---|---|
| `certus/physics/certus_strat_growth.py` | `simulate_growth_kernel` | Après remplissage de `Ts_r` et `Ts_n`, avant `detect_turning_points` : moyenne glissante de `smoothing_window` échantillons. `smoothing_window = 1` par défaut = aucun lissage = chemin actuel bit-identique (C1). |
| idem | idem | 🔴 **Lisser `Ts_r` ET `Ts_n`.** Le lissage fait partie de « comment la machine lit », et le code impose déjà la **même règle de détection** des deux côtés. Ne lisser qu'un seul signal fabriquerait une divergence de comptage à chaque couche. |
| idem | idem | ⚠️ Le lissage porte sur le signal **bruité**, donc après l'ajout du bruit de lecture — jamais avant. |
| `certus/physics/certus_strat_batch.py` | les deux fonctions batch | Acheminer `smoothing_window`. Phase A et Phase B doivent modéliser la même machine. |
| `certus/core/certus_strat_robustness.py` | `_execute_robustness_tasks` | Nouvelles clés JSON `reading_smoothing_window` (défaut **1**) et `tp_hysteresis_factor` à passer à **0,354** quand la fenêtre vaut 8. |

#### Vérification

1. **Non-régression** : `smoothing_window = 1` → `RESULT` identique au repère §10, bit à bit.
2. **Rejouer le test de fabrication avec lissage** — la mesure décisive, et elle est bon
   marché : signal plat, 20 000 tirages, N = 800, `k = 8`, seuil 0,354 A.
   **Attendu : fabrication ~0 %.** Si ce n'est pas le cas, le dire — et surtout **ne pas
   remonter le seuil en douce** pour faire passer le chiffre.
3. **Les vrais extrema survivent-ils ?** Signal propre **sans bruit**, avec et sans lissage :
   le nombre de points tournants détectés doit être **identique**. S'il baisse, la fenêtre
   arrondit de vrais extrema et elle est trop large.
4. **Piège 1** : balayer `k` ∈ {1, 4, 8, 16}. Si le taux de plantage ne bouge pas avec `k`,
   le lissage n'atteint pas le calcul.

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

#### Ce qui a été mesuré, et ce qui bloque

📏 Oracle TMM indépendant, 6 couches, monitoring à niveau absolu : une perturbation produit
jusqu'à **2,4578 nm** d'erreur d'épaisseur. Le noyau actuel produit exactement **0**.

⚠️ **Ce chiffre SURESTIME l'effet réel, et il faut le savoir.** Il a été mesuré avec une
perturbation **relative** de 0,5 %, prise avant que le physicien ne précise que le corridor
est absolu. En absolu, 0,5 % de n_H = 2,35 vaut **0,0118**, soit **2,4× le corridor réel**
de 0,005 ; pour n_L = 1,46 cela vaut 0,0073, soit 1,5×. L'ordre de grandeur reste : l'effet
est du premier ordre et le noyau en produit zéro. Mais **la magnitude est à remesurer** avec
`delta_max = 0,005` absolu, et il ne faut pas extrapoler linéairement — c'est précisément
le genre de raccourci que ce projet fait payer.

🔴 **Ne pas se contenter de pré-multiplier `n_H`/`n_L` au site d'appel.** Mesuré :
3,29e-10 nm à δ=0,005, et **1,92e-10 nm à δ=0,05** — ×10 sur la perturbation ne change rien.
Le même jeu d'indices pilote l'empilement réel **et** le nominal ; les décaler ensemble ne
crée aucune divergence.

#### Où, exactement

| Fichier | Fonction | Ce qu'il faut écrire |
|---|---|---|
| `certus/physics/certus_strat_growth.py` | `simulate_growth_kernel` | **Dédoubler les indices** : `n_H_real, n_L_real` pour `M_before` et `Ts_r` ; `n_H_nom, n_L_nom` pour `M_nom`, `Ts_n` et `target_nominal`. C'est **la** condition sans laquelle rien de tout ceci ne produit d'effet. |
| idem | idem | L'inversion parabolique finale (`T_points`) décrit le signal **réel** : elle prend `n_*_real`. |
| `certus/physics/certus_strat_batch.py` | `simulate_stack_robustness_batch` | Accepter `n_H_real_vals` / `n_L_real_vals` en plus des tableaux nominaux. Ils sont **déjà indexés par couche** (chaque couche a sa λ de monitoring) : la dépendance en λ est donc déjà acheminée, il suffit d'y appliquer `δ_M(λ_mon,i)`. |
| idem | `compute_batch_rmse` | 🔴 **PAS FAIT — c'est ce qui reste de T5, et c'est le morceau qui compte.** `n_layers_flattened` est sur la grille spectrale : le filtre physique a **réellement** l'indice perturbé, donc son spectre doit être évalué avec `n_réel(λ)`. **C'est là que l'inclinaison non compensée se paie.** Vérifié le 2026-08-09 : la fonction n'a aucun paramètre de corridor et reçoit une matrice bâtie sur les indices nominaux. ⚠️ Le corridor étant tiré **par tirage**, il faut soit une matrice d'indices par tirage, soit passer `(a_H, b_H, a_L, b_L)` et reconstruire l'indice à la volée dans le noyau — comme le fait déjà `simulate_growth_kernel`. La seconde voie est la moins coûteuse. |

#### Vérification

```bat
:: 1. non-regression : index_corridor = 0, RESULT identique au repere §10
:: 2. balayage : corridor 0 / 0,0025 / 0,005, puis a seul (b=0) et b seul (a=0)
```

Attendu : `RESULT` se dégrade avec le corridor, **et plus vite pour `b` que pour `a`**. Si le
chiffre ne bouge pas quand le corridor grandit, c'est le Piège 1 — la perturbation n'atteint
pas le calcul, exactement comme la recette pré-multiplicative ci-dessus.

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

#### Où, exactement

`certus/physics/certus_strat_growth.py`, `simulate_growth_kernel`, constantes en tête du bloc
de balayage : `NPTS = 64`, `NPTS_PREV = 16`, `D_SCAN = 3.0`.

#### La parade au coût — découpler les deux grilles

Coût brut d'un passage à 800 points : 4 couches d'historique × 800 + 2 400 = **5 600
évaluations TMM** contre 128, soit **×44**. Rédhibitoire quand `REPRISE_PERF` conclut qu'il
n'y a pas de ×2 disponible.

**`T(d)` est lisse** et parcourt moins d'une période sur tout le balayage. Donc : garder les
évaluations TMM exactes telles quelles, **interpoler** sur les positions d'échantillonnage
réelles, et tirer **un bruit indépendant par position réelle**.

Le nombre de tirages — qui est ce qui gouverne la fabrication d'extrema parasites — devient
fidèle **à coût TMM inchangé**. C'est le nombre de tirages qui compte, pas le nombre
d'évaluations TMM.

🔒 **La formule, à écrire telle quelle :**

```python
SAMPLE_DD = 0.125        # nm entre deux lectures machine (§9bis-1)

# --- grille TMM : INCHANGEE, 64 points sur 3 x d_nom, 16 par couche d'historique
NPTS      = 64           # ne pas toucher
NPTS_PREV = 16           # ne pas toucher

# --- grille d'ECHANTILLONNAGE, nouvelle, en lectures machine
#     Basee sur l'epaisseur NOMINALE, JAMAIS sur l'epaisseur obtenue :
#     p_thick_nominal[j] ne depend pas de la strategie, d_real_j si (contrainte C2).
M_cur    = int(np.ceil(D_SCAN * nominal_th / SAMPLE_DD)) + 1     # couche courante
M_prev_j = int(np.ceil(p_thick_nominal[j] / SAMPLE_DD))          # couche j de l'historique
```

Pour une couche de 100 nm : `M_cur = 2401`, `M_prev_j = 800`. Le signal propre est obtenu par
**interpolation linéaire** des points TMM sur ces positions, puis on ajoute
`signal_noise_scale * _seeded_noise_sample(seed, groupe, tirage, indice_echantillon, True)`
à chacune, puis on lisse (§12.2), puis on détecte.

**Indices de bruit** : `(group=j, elem=m)` pour l'historique de la couche j,
`(group=i_layer, elem=M_prev_max + m)` pour la couche courante, avec `M_prev_max` une
**constante** assez grande (par ex. 4096) et non `M_prev_j`, qui varie d'une couche à
l'autre. Sans cela les plages se chevauchent.

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

#### Ce qui existe déjà dans le code, et ce qui manque

🟢 **La moitié « trop grossier » est déjà écrite** :
`_calculate_strategy_spectral_resolution` (`certus_strat_robustness.py:249-289`) estime, pour
chaque couche, la largeur de bande à partir de laquelle l'erreur de convolution atteindrait la
tolérance, via la **courbure spectrale** de `T(λ)` mesurée en seconde différence sur 1 nm :

```python
curvature = abs((T_vals[0] + T_vals[2]) / 2.0 - T_vals[1])
res_limit = test_bw * np.sqrt(T_tolerance / curvature)
```

C'est un développement au second ordre correct, et la fonction rend déjà **la couche la
pire** — c'est-à-dire la contrainte qui lie.

🔴 **Ce qui manque, dans l'ordre d'importance :**

1. **Le facteur de bruit n'existe nulle part.** Aucun lien entre résolution et
   `signal_noise_scale`. C'est la partie **triviale à écrire** et celle qui a l'effet le plus
   direct : une multiplication.
2. **`min_resolution` est un rapport, pas un critère.** Elle est calculée puis rangée dans
   `res["min_resolution"]` et affichée. Elle ne sélectionne rien. ⚠️ §20-contrôle 4 : *« compte
   les rejets, ne lis pas le code »* — vérifie d'abord si cette valeur écarterait quoi que ce
   soit avant de la câbler.
3. **La déformation n'est pas appliquée au signal simulé**, seulement estimée. La modéliser
   vraiment demande d'évaluer `T` sur **plusieurs λ** autour de λ_mon et de pondérer par la
   fonction de fente — donc ×3 à ×5 sur le coût TMM du chemin de monitoring.
4. `MachineModel.monochromator_resolution_nm` vaut **0,5**, alimenté par une constante nommée
   `OMS5100_DEFAULT_MONOCHROMATOR_STEP_NM` et documentée « Monochromator step / precision ».
   **`step` et `résolution` ne sont pas la même grandeur** — l'un est le pas de réglage de
   λ_mon, l'autre la largeur de bande. Le nominal que le physicien donne est **2 nm**. C'est
   le même genre de confusion d'unité que le piège ×100 de `trigger_tolerance` (§17-9). Voir
   la question Q3.

#### 🟢 Comment mesurer AVANT de construire

**Ne pas écrire la convolution en premier.** Mesurer d'abord si elle compte, avec une sonde
qui ne coûte rien — même esprit que la sonde « signal plat, 20 000 tirages » de §12.2 :

> Sur le juge de paix nominal, couche par couche, calculer `T(λ)` autour de chaque λ_mon
> candidate, convoluer par une fente de 5 nm, et regarder de **combien le swing baisse**.

- Si la baisse est de l'ordre du pour cent → la déformation est du second ordre, **seul le
  facteur de bruit compte**, et l'action se réduit au point 1. Une multiplication.
- Si elle est de 20 % → elle est du premier ordre et il faut la convolution complète.

**Cette sonde tranche entre une action d'une heure et une action de plusieurs jours.** Elle
passe avant.

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

#### La mesure au banc, une fois le point 1 câblé

Quatre runs, un par résolution, à configuration égale par ailleurs, et on compare **taux de
plantage** et **erreur spectrale**. C'est la mesure qui dit si le ×4 de Phase B est justifié :
si les quatre chiffres se tiennent à moins que la dispersion Monte-Carlo, la résolution ne
mérite pas d'entrer dans la recherche et on la fige à 2 nm.

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
  utilisées côte à côte à `certus_strat_growth.py:570-571`. Aucune plomberie à ajouter.
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
- **Réintroduire un mode dégradé.** 👤 *« Interdit le mode fast. »*
- **Citer les repères « 0,4 nm / 0,3 nm »** — absents de la thèse Zideluns.
- **Tirer une conclusion physique d'un empilement autre que le 48 couches.**
- **Raffiner la grille d'échantillonnage sans corriger le seuil** — voir §12.2.
- **Modéliser σ(T), la grenaille ou le bruit multiplicatif** — voir §9.

---

# PARTIE IV — DÉFAUTS OUVERTS ET AUTRES CHANTIERS

## 17. Les défauts ouverts hérités des sessions précédentes

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
| 1 | ~~La règle d'or n'est pas tenue~~ — 🔴 **CONSTAT RETIRÉ LE 2026-08-09, il était faux.** J'avais relevé un écart de 2,5e-11 entre l'artefact pré-T1 et l'artefact post-T5, à configuration neutre, et j'en avais conclu une violation de C1 « 25× au-dessus du seuil ». **C'était mesurer la mauvaise chose.** Deux runs de configuration **strictement identique** (`CONFIG=` identiques, vérifié) donnent `0.002948627371226749` et `0.002948627371309867` — **2,8e-11**, la même grandeur. Le banc **n'est pas bit-reproductible par construction** : voir l'encadré de §10. Il ne reste de ce constat qu'une chose, et elle tient toujours : **aucune empreinte `float.hex()` n'existe**, donc C1 n'est vérifiée par rien. C'est l'objet de A5. |
| 2 | **T3 est soudée à T4 et donc inexécutable seule.** `SAMPLE_DD = 0.125` n'existe qu'à l'intérieur de `if smoothing_window > 1:` (`certus_strat_growth.py:652`). La configuration « grille fine, fenêtre à 1 » — celle que la condition d'arrêt de T3 impose d'observer — **n'est pas exprimable**. Et le chemin par défaut garde la grille 38× trop grossière, alors que §12.4 la qualifie de caractéristique physique, pas d'option. |
| 3 | **Le lissage est une moyenne CAUSALE** (fenêtre `[i−k+1 … i]`), qui décale un extremum de ≈ `(k−1)/2` échantillons, soit **0,44 nm à k = 8**. §12.2 écrit « n'ajouter aucun décalage temporel » et §9bis-5 pose « aucun retard » en postulat figé. Une moyenne **centrée** ne décalerait rien. |
| 4 | **T7 n'est pas implémenté** malgré le message de `162a0ff`. L'arrêt reste obtenu par inversion parabolique continue ; aucune loi `U(0 ; 0,125 nm)` n'existe. Par ailleurs T5, T6 et T7 dans un seul commit contredit **C3**. |
| 5 | **Aucun test n'accompagne les trois commits de feature.** `f7a3d71`, `e0df0e1`, `162a0ff` ne touchent aucun fichier de `tests/`, et aucun test ne mentionne les nouveaux paramètres. Le contrôle 2 de §20 est donc inapplicable. |
| 6 | **Les mesures qui SONT le critère de réussite n'ont pas été faites.** T2 (4 runs POEM×distorsion), le balayage de corridor de T5, et T6 : aucun artefact, aucun run. |
| 7 | **Les deux seuls runs de modèle ne sont pas exploitables.** `..._yw1_hyst0p354.json` (plantage 0,76) et `..._yw1_hyst0p707.json` (plantage 0,45) sont à `dp_yield_weight = 1`, donc **incomparables** au repère §10 qui est à 0. Et **ni l'un ni l'autre n'enregistre `reading_smoothing_window`** : le script lit `CERTUS_SMOOTHING_WINDOW` dans l'environnement (`probe_anchor_noise_pipeline.py:95`) et ne l'écrit nulle part. **On ne sait pas avec quel `k` ces deux chiffres ont été obtenus.** |
| 8 | **Un artefact de mesure a été emporté dans le commit « traduction »** `cc90a94` : `reports/probe_anchor_noise_pipeline_full_step1_seed42.json`, celui-là même qui porte le chiffre changé du point 1. |
| 10 | 🔴 **T5 (corridor d'indice) n'atteint QUE la moitié du calcul.** Le tirage est conforme au §12.3 au mot près — un `(a, b)` par matériau et par tirage, `\|a\|+\|b\| ≤ δ_max`, affine en λ, appliqué à la λ de monitoring de chaque couche (`certus_strat_batch.py:115-131` et `290-306`), et il respecte bien « mêmes indices pour toutes les paires, mêmes pour toutes les impaires ». Il atteint le chemin de **croissance** : l'empilement réel est bâti avec `n_*_real` pendant que le nominal reste nominal, donc les épaisseurs sortent fausses. **Mais il n'atteint PAS la notation.** `compute_batch_rmse` n'a **aucun** paramètre de corridor (`certus_strat_batch.py:355-364`), et `n_layers_matrix` est construite par parité à partir des tableaux **nominaux** seuls (`certus_strat_robustness.py:757-764`). Le spectre du filtre fini est donc évalué comme si les indices étaient exactement nominaux. §12.3 l'avait écrit d'avance : *« c'est là que l'inclinaison non compensée se paie — l'omettre annulerait tout l'intérêt de l'action »*. **Le mode CROISÉ, celui que le physicien décrit comme non compensable, est précisément celui qui ne se voit que dans le spectre final — il est donc quasi invisible dans l'état actuel.** ⚠️ Ce n'est pas une correction d'une ligne : le corridor est tiré **par tirage** alors que `compute_batch_rmse` reçoit **une seule** matrice d'indices pour tous les tirages. |
| 18 | 🔴 **Le chemin CONSENSUS ignore `robustness_num_runs`.** Trouvé au rodage du 2026-08-10 : un run demandant **20 tirages**, `CONFIG` à l'appui, rend `0.002948627371309867` — **exactement**, au dernier bit, la référence historique à **150** tirages. `_unpack_consensus_cfg` porte un `consensus_num_runs` distinct, que l'override n'atteint pas. **Toute mesure faite avec le consensus actif est donc à une profondeur autre que celle demandée, et n'est comparable à rien.** Exposer `consensus_num_runs` avant de s'en servir. |
| 14 | 🟠 **`dp_yield_weight` est nul, mais peut-être ARITHMÉTIQUEMENT et non par panne de câblage** — *constat corrigé le 2026-08-11.* Il est bien inerte : `yw0`, `yw50`, `yw200`, `yw1000` donnent des profils par bande **rigoureusement identiques**, et D5.yw200 du 2026-08-11 rend en plus un **top-5 identique dans le même ordre**. J'en concluais « il n'atteint pas le calcul ». 🔴 **Cette conclusion n'est pas établie**, et il y a une explication plus simple que je n'avais pas cherchée : le coût vaut `w·(−log(1−p))`, et **toutes** les stratégies du classement ont `p = 0`. Le terme vaut donc `w·0 = 0` quel que soit `w` — un zéro exact, pas un fil coupé. **L'expérience qui tranche existe et coûte un run** : relancer `dp_yield_weight` à un corridor où il y a des plantages — D1.5 en a 29,3 %. S'il reste nul là, c'est un défaut de câblage ; s'il agit, il n'y avait rien à réparer. **Ne pas « corriger » ce paramètre avant d'avoir fait ce run.** |
| 15 | 🔴 **Deux configurations différentes rendent le MÊME `RESULT` au bit, alors que leurs bandes diffèrent.** Seuils 2,0 A et 2,4 A : `RESULT = 0.003192038110407474` pour les deux, mais `passante` vaut 0,003214 contre 0,004444 — **38 % d'écart**. Donc `RESULT` est **aveugle à un changement qui déplace visiblement le résultat**. Avant de continuer à s'en servir comme grandeur de tête, il faut savoir ce qu'il agrège exactement : §10 dit « le pire des trois niveaux de bruit », et personne n'a vérifié cette phrase dans le code. |
| 16 | 🟢 **La bande bloquée n'est jamais le mode de défaillance.** Sur les 25 runs au disque, elle est **~567× plus propre** que la passante, sans exception. §14 s'inquiète à juste titre qu'un RMSE uniforme ne puisse pas distinguer les deux bandes — mais **le filtre ne rate jamais son blocage, il rate son passage**. ⚠️ Cela ne clôt pas §14 : l'exigence est ~500× plus serrée en bande bloquée, et 567 ≈ 500 signifie que les deux bandes sont **également proches de leur spec**, pas que l'une est acquise. Il faut les tolérances réelles par bande pour trancher, et on ne les a pas. |
| 12 | 🟠 **La marge de Phase A agit, mais ne change jamais l'issue** — *constat corrigé le 2026-08-11, l'ancien était trop sévère.* Il disait « elle ne rejette RIEN », sur la seule foi d'un `RESULT` bit-identique. **C'était lire la mauvaise grandeur.** D5.marg de la campagne du 2026-08-11 : à 3,33 le classement porte **257** stratégies contre 228 à 1,66, et son **top-5 est différent**. La marge atteint donc bien le calcul et modifie la population de la Phase A. Mais la gagnante reste la **même stratégie physique** — `[544, 531]`, 2 blocs, origine SYM, sous l'id 2226 au lieu de 2228, l'id n'étant qu'un rang d'énumération — et le score est bit-identique. **Le bon énoncé : elle change ce qui est offert, jamais ce qui est retenu.** |
| 13 | 🟢 **Le corridor d'indice, courbe CORRIGÉE du 2026-08-10.** Notation perturbée (A10) **et** normalisation sur l'enveloppe : `0,001 → ×1,24` · `0,0025 → ×1,86` · **`0,005 → ×2,46`** · `0,010 → ×4,32`. En SEEL : **0,3 → 0,6 nm à la valeur du modèle**, l'erreur équivalente **double**. Exposant log-log **0,525**, remarquablement proche d'une racine carrée. ⚠️ Les chiffres d'avant (×1,98 / ×3,35 / ×5,16 / ×8,19, exposant 0,616) étaient **gonflés de 1,6 à 2,1×** par la normalisation fautive. **Ne les cite plus.** |
| 19 | 🟢 **La prédiction du §12.3 est CONFIRMÉE, et cette fois sans l'artefact.** Le nombre de blocs de la gagnante croît de façon monotone avec le corridor : **2 → 3 → 4 → 5 → 8**. §12.3 l'annonçait — *« cela favorise les stratégies dont les λ de contrôle sont réparties plutôt que groupées »*. 🔑 **Ce qui rend ce constat solide, c'est qu'il survit à la correction.** Le bug de normalisation poussait dans le **même sens** (il pénalisait les λ groupées d'un facteur allant jusqu'à 21) : tant qu'il était là, l'effet physique était indémontrable. L'artefact retiré, l'effet demeure. |
| 17 | 🔑 **POEM protège AUSSI contre l'erreur d'indice, et ce n'est pas le théorème qui le fait.** Sur le corridor corrigé (2026-08-10), à 0,005 : `SEEL 0,6 nm` avec POEM contre **`22,3 nm` et 29,3 % de plantage** sans — un rapport de **×34,8** sur le `RESULT`. Or POEM n'est invariant que par distorsion **affine**, et une erreur d'indice n'en est pas une. **L'explication est l'autre mécanisme** : POEM recale ses ancres sur les extrema réellement observés, donc il compense les erreurs d'épaisseur **accumulées**. ⚠️ Le facteur de protection propre (rapport des coûts) demande un run POEM-off à corridor 0 sur le code corrigé, **qui n'existe pas encore** — les valeurs ×7,6 puis ×6,85 citées plus tôt sont d'avant l'enveloppe. |
| 26 | 🔑 **LE RÉSULTAT DE LA CAMPAGNE DU 2026-08-11 : à N = 150, le classement départage du BRUIT.** Deux mesures indépendantes le disent, et elles concordent.<br>📏 **(1) Dispersion sur sous-paquets** du run N = 1200, `scripts\analyse_campagne.py`. `spread_relative` est une **étendue** (max−min)/médiane, pas un écart-type : divisée par `E[étendue]/σ` du nombre de paquets, elle donne `σ ≈ 6,28 %` à N = 128 (9 paquets, ÷2,97) et `6,73 %` à N = 256 (4 paquets, ÷2,06). La loi en `1/√N` est **exacte** entre N = 32 et N = 128 : 12,56 / 6,28 = **2,00** pour une profondeur ×4. Donc **σ ≈ 5 à 6 % au point de fonctionnement N = 150**.<br>📏 **(2) Écarts entre stratégies**, classement N = 150, corridor 0 : #1 `0.0027330` · #2 **+6,5 %** · #3 +9,9 % · #4 +11,0 % · #8 +16,6 %.<br>🔴 **L'écart #1→#2 vaut 6,5 %, et la différence de deux scores porte `σ√2 ≈ 8 %` : la gagnante et sa dauphine sont à 0,8 σ. Indiscernables.** Le top 8 entier tient dans ~2 σ.<br>✅ **Corroboré par le balayage D2, obtenu autrement** : le top-5 n'est stable à **aucun** passage de N, et la gagnante alterne 2228 / 2218 / 2228 / 2228 / 2228 / 2218.<br>🔑 **Et les huit lisent `SEEL = 0,3 nm`.** La règle de tri de §14 — SEEL quantifié à 0,1 nm, puis rendement — n'est donc **pas une commodité d'affichage : c'est le classement statistiquement correct**, et cette campagne démontre que le tri continu actuel départage du bruit.<br>💰 **Le coût de l'alternative, chiffré** : séparer 6,5 % à 3 σ demanderait `σ ≈ 1,5 %`, soit `N ≈ 150 × (5,5/1,5)² ≈ 2000` tirages par stratégie — **×13**. La bonne réponse n'est pas de les acheter, c'est de déclarer l'égalité. |
| 39 | 📏 **LA FALAISE, ENCADRÉE SUR 5 GRAINES — campagne G, 2026-08-11. Remplace le §17-35, qui n'avait que 3 graines.**<br>**Où la graine 77 casse exactement** : `0,005 → 0 %` · `0,006 → 0 %` · `0,0075 → 0 %` · `0,010 → 100 %`. **La falaise est entre 0,0075 et 0,010**, donc la marge sur la valeur du modèle vaut **×1,5 à ×2** — plus serré que ce que §17-35 laissait croire.<br>**Le taux d'échec sur 5 graines** : à la valeur du modèle **0,005 → 0 graine sur 5 en échec** (pire cas 0,7 %) · au double **0,010 → 2 graines sur 5** (77 à 100 %, 202 à 37,3 %).<br>🔑 **L'énoncé défendable** : *le design est confortable à l'incertitude d'indice spécifiée, et deux graines sur cinq ne survivent pas à son doublement.* C'est une marge, pas un gouffre — et c'est maintenant chiffré sur un échantillon, pas sur une anecdote.<br>⚠️ **Ne lis pas la non-monotonie de la graine 77 comme un signal** : SEEL 1,3 → 0,7 → 1,0 nm de 0,005 à 0,0075, avec une gagnante à 4, puis 3, puis 2 blocs. C'est §17-26 en action — le classement départage du bruit, et la gagnante est un tirage. Les trois valent « de l'ordre de 1 nm », rien de plus. |
| 40 | 🟢 **LE MONITORING COUCHE-PAR-COUCHE GAGNE SUR 2 GRAINES SUR 5 À LA VALEUR DU MODÈLE.** Rang de la première stratégie à 48 blocs, corridor 0,005 : `graine 42 → 153/165` · `77 → 2/78` · **`101 → 1/80`** · **`202 → 1/90`** · `303 → 98/116`. Les gagnantes des graines 101 et 202 sont **à 48 blocs**.<br>Ce n'est donc ni une anomalie ni un artefact de la graine 101 : **à l'incertitude d'indice réelle, se réancrer à chaque couche est la meilleure stratégie deux fois sur cinq.** Combiné à §17-34 (l'effet se referme au-delà) et à §10.3 de la page (48 blocs coûte ×171 à corridor **0**), le tableau complet est : *le monitoring par blocs gagne quand l'indice est connu, le monitoring par couche gagne quand il l'est mal, et le basculement tombe dans la plage réelle d'un atelier.*<br>⚠️ L'offre varie aussi : 30 stratégies à 48 blocs à la graine 101 contre 4 partout ailleurs. Non expliqué. |
| 37 | 🔴 **LA FALAISE N'EST PAS DE LA PHYSIQUE QUI DURCIT — C'EST LA PHASE A QUI N'A PLUS LE CHOIX, ET LE SYSTÈME NE LE DIT PAS.** Mesuré le 2026-08-11 par comptage des rejets (§20-contrôle 4), sur les `STRAT_observability_*.json` des deux runs effondrés :<br>`candidates offertes` **108** · `interdites pour plantage` **103** · `survivantes, médiane sur 48 couches` **1** · **32 couches sur 48 en repli « moins mauvais taux »** · tolérance de plantage **0,001**, taux minimal réellement observé **0,007** — **7× la tolérance**.<br>**La chaîne complète** : le corridor rend presque toutes les λ inadmissibles → la Phase A ne trouve **aucune** λ sous la tolérance sur 32 couches et garde la moins mauvaise → la stratégie n'est plus *choisie*, elle est **forcée** → la Phase B la trouve à 100 % de plantage.<br>🔴 **Et le résultat final ne porte aucune trace de tout cela.** Il annonce une gagnante, avec un score et un SEEL, exactement comme un run sain. C'est le motif que ce document décrit depuis le début : *ça ne produit pas d'erreur, ça produit un résultat plausible.* Le repli **est** journalisé par couche, mais rien ne remonte au classement.<br>✅ **Correctif à faire, et il est petit** : remonter `n_layers_forced` (le nombre de couches en repli) dans le résultat de stratégie et dans le classement. **Une stratégie bâtie sur 32 couches forcées n'est pas comparable à une stratégie librement choisie**, et aujourd'hui rien ne permet de les distinguer. |
| 38 | 🟠 **Un filtre de plus qui ne rejette RIEN : `forbidden_gain_negative` vaut 0 sur les 8 runs examinés**, à toutes les couches, corridor 0 comme corridor 0,020. Le critère de gain de compensation négatif n'a **jamais** écarté une seule candidate. Comme pour §17-12 et §17-33 : soit il n'atteint pas le calcul, soit ce qu'il écarterait n'existe pas. **Compter avant de conclure** — mais un filtre à zéro rejet sur toute la plage mesurée est un défaut, pas un succès. |
| 33 | ✅ **§17-14 EST TRANCHÉ : `dp_yield_weight` N'ATTEINT PAS LE CALCUL.** F1 du 2026-08-11 l'a porté à 200 sur le bras qui plante à **59,3 %** (POEM coupé + distorsion). Résultat **bit-identique** à `yw = 0`, `0.3279370792191264`, même gagnante `8800`, **même top-5 dans le même ordre**. Or le terme vaudrait `200 · (−log(1 − 0,593))` = **180**, un coût énorme. Ce n'est donc plus l'explication arithmétique de §17-14 : **le fil est coupé.**<br>⚠️ **La nuance qui reste, et il faut la dire** : le `p` de la DP est l'estimation **par couche de la Phase A**, pas le taux final de la Phase B. Il reste donc deux lectures — le paramètre n'atteint pas la DP, ou la DP voit encore `p = 0` même ici. **Pratiquement, c'est le même verdict : comme bouton, il ne fait rien.** Ce qui les départagerait : instrumenter le `p` que la DP reçoit réellement. |
| 34 | 🔴 **MA PRÉDICTION DE §17-30 EST RÉFUTÉE — le monitoring couche-par-couche gagne dans une FENÊTRE, pas de façon monotone.** J'avais posé que si le mécanisme était réel, élargir le corridor devait le pousser plus loin. F2 dit le contraire :<br>`graine 101, corr 0,005` → 30 stratégies à 48 blocs, **rangs 1 à 30** · `graine 101, corr 0,010` → **1 seule, rang 55 sur 68**, et la gagnante fait 3 blocs · `graine 77` → rang 2 puis rang 21.<br>🔑 Et le run qui réfute est **sain** (0 % de plantage, SEEL 1,3 nm), donc ce n'est pas un régime dégénéré qui parle. **Le constat §17-30 reste vrai — le gradient de pire à meilleur existe — mais il n'est pas monotone et je l'avais sur-extrapolé.** Il y a une bande d'incertitude d'indice où se réancrer à chaque couche paie, et elle se referme au-delà. |
| 35 | 🔴 **IL Y A UNE FALAISE, ET SA POSITION DÉPEND DE LA GRAINE D'UN FACTEUR ≥ 2.** Plantage de la gagnante :<br>`graine 42` → 0 % jusqu'à corridor **0,010**, puis **99,3 %** à 0,020 · `graine 77` → 0 % à 0,005, **100 %** à 0,010 · `graine 101` → 0 % à 0,005 **et** à 0,010.<br>Ce n'est pas une dégradation continue, c'est un mur : on passe de `SEEL 1,2 nm` à `SEEL 30–37 nm` et de 0 % à ~100 % de plantage en doublant le corridor.<br>🔑 **La conséquence pratique, et elle est sérieuse** : à la valeur du modèle (0,005) les trois graines vont bien, mais **la marge jusqu'à la catastrophe est inférieure à un facteur 2 sur la graine 77**. Ce n'est pas un confort. ⚠️ À vérifier avant d'en faire une règle : trois graines ne font pas une distribution. |
| 36 | 🟢 **A23 ÉTAGE 0 REND SON PREMIER VRAI DIAGNOSTIC — impossible à obtenir avant le 2026-08-11.** Sur l'effondrement de la graine 77 à corridor 0,010, le profil par couche montre que **rien ne plante avant la couche 35**, puis tout plante de **35 à 47** — le dernier quart de l'empilement. Sur 1033 plantages par couche : **856 (79 %) sont des `tp_miscount`**, 222 (21 %) des `level_unreachable`.<br>**C'est l'histoire de l'erreur accumulée, lue directement** : l'erreur d'indice se compose le long de l'empilement, et dans le dernier quart l'écart d'épaisseur optique devient assez grand pour que la machine compte le **mauvais nombre d'extrema**. Ce n'est pas le niveau qui devient inatteignable, c'est le **comptage** qui décroche.<br>La gagnante porte en plus `worst_swing = 0,0334` à la couche 31 et **2 couches sous `SWING_MIN`** : la Phase A a retenu une stratégie qui a des couches sans signal exploitable. **Un taux agrégé de « 100 % » ne disait rien de tout cela.** |
| 29 | 🟢 **CAMPAGNE E, 2026-08-11 — les correctifs de cohérence passent la porte C1, et les deux résultats de tête TIENNENT.** 12/12 runs `OK`, code corrigé (§17-20, 23, 24, 25).<br>✅ **Porte C1** : `E0.ref = 0.0027329534106323534` contre `D0.ref = 0.0027329534107462224`, **écart relatif 4,2e-11** — l'ordre de la recompilation (2,8e-11, §3). Aucun correctif n'a fui dans le chemin neutre, donc la campagne est interprétable.<br>✅ **La courbe du corridor survit** : `×1,23 · ×2,03 · ×2,41 · ×4,66` contre `×1,24 · ×1,86 · ×2,46 · ×4,32` avant. Écarts de −0,7 % à +9 %, c'est-à-dire **dans le bruit statistique** (σ√2 ≈ 8 %, §17-26). Exposant **0,545** contre 0,525. **C'était le résultat phare et il est robuste au correctif.**<br>🔑 **POEM : la protection monte à ×41,2** (contre ×17,5). POEM actif ×1,198 sous distorsion, POEM coupé **×49,41**. Couper POEM sans aucune distorsion coûte déjà ×2,43 (contre ×1,975).<br>⚠️ **Le dommage résiduel avec POEM est de +19,8 % ici, pas +0,9 %.** §12.1 disait déjà que le +0,87 % de la graine 42 était un tirage chanceux. **Cite la protection, jamais le résiduel.** |
| 30 | 🔑 **LE MONITORING COUCHE-PAR-COUCHE PASSE DE PIRE À MEILLEUR QUAND LE CORRIDOR S'ÉLARGIT.** Gradient mesuré le 2026-08-11, et il est propre :<br>`corridor 0, graine 42` → 48 blocs au rang **228 sur 228** (dernier) · `0,005 graine 42` → rang 153/165 · `0,005 graine 77` → rang **2**/78 · `0,005 graine 101` → **rang 1, et les rangs 1 à 30**.<br>Le mécanisme est cohérent : les ancres POEM héritées du bloc ont été acquises sous un indice que la machine croit connaître et ne connaît pas. Plus l'erreur d'indice est grande, plus l'historique est **trompeur** — jusqu'au point où se réancrer à chaque couche devient gagnant. C'est le bout extrême de la tendance « λ réparties » du §17-19.<br>🔴 **MAIS ÇA NE CONTINUE PAS — voir §17-34, qui réfute l'extrapolation que j'avais faite ici.** L'effet vit dans une **fenêtre** d'incertitude d'indice et se referme au-delà. Le gradient ci-dessus est réel ; « plus le corridor est large, plus ça gagne » est faux.<br>🔴 **Ça ne contredit PAS le ×171 de §10.3 de la page** : celui-ci est mesuré à corridor **0**, où 48 blocs est effectivement catastrophique. Les deux énoncés portent sur deux régimes. **Ne cite jamais l'un sans son corridor.**<br>⚠️ Constat second, à ne pas perdre : `n_ranked` s'effondre avec le corridor — **228 → 165 → 78 → 80**. La Phase A élimine beaucoup plus de candidates quand l'indice est incertain. Non expliqué. |
| 31 | 🟠 **A23 fonctionne dès le premier usage, et il donne un chiffre honnête plutôt que le chiffre espéré.** Le profil de plantage par couche et le swing de la couche la pire remontent maintenant dans les rapports. Sur la gagnante de E4.101 : `worst_swing = 0,0874` à la **couche 39**, et l'unique plantage `level_unreachable` est **à la couche 39**. Coïncidence parfaite, sur les 10 premières lignes examinées.<br>🔴 **Puis la statistique complète corrige l'enthousiasme : 157 sur 561, soit 28 %.** À comparer à 1/48 ≈ 2 % par hasard : c'est un **enrichissement de 13×**, donc un vrai signal — mais la couche à plus faible swing n'est la couche défaillante que dans un cas sur quatre.<br>**Conclusion, et c'est exactement l'argument d'A23** : le swing est un **proxy**, pas la grandeur. Il faut la **marge** — étage 2 — qui est mesurée sur le signal réel au lieu d'être supposée. Ce 28 % est la meilleure justification qu'on ait pour faire l'étage 2 plutôt que de s'arrêter au swing. |
| 32 | 🔴 **E2 A ÉCHOUÉ, et c'est instructif : `dp_yield_weight` reste indécidable.** Le run devait trancher §17-14 en portant le poids là où il y a des plantages — corridor 0,005, qui plantait à 29,3 % sur le code d'avant. **Sur le code corrigé ce bras plante à 0,0 %**, donc le terme valait encore `w·(−log(1−0)) = 0` et E2 est revenu **bit-identique à E1.3**, même gagnante, même score. §17-14 est toujours ouvert. Le seul bras qui plante encore est E3.4 (POEM coupé + distorsion, **59,3 %**) → c'est là qu'il faut le mesurer, et c'est l'objet de F1. ⚠️ **Leçon de méthode** : une expérience conçue contre un régime que le correctif fait disparaître ne mesure rien. Vérifier que le régime existe **encore** avant de lancer. |
| 28 | 🔴 **AUCUN critère connu d'avance ne permet d'élaguer les 228 stratégies. Mesuré, et il détruit la règle évidente.** À corridor 0 la classe d'équivalence (`SEEL = 0,3 nm`) compte **10 membres, aux rangs 1 à 10, tous à 2 blocs, tous `ELITE` ou `SYM`** — une règle de tri superbe. **Elle ne survit à aucun changement de régime :**<br>`corr 0` → 2 blocs, ELITE+SYM · `0,001` → **3 blocs, `LOCAL_SEARCH` seul** · `0,0025` → 2 à 5 blocs, trois générateurs · `0,005` → **5 blocs, `LOCAL_SEARCH` seul** · `0,010` → **8 blocs, `LOCAL_SEARCH` seul** · graine 77 → 2-3 blocs, **les quatre générateurs** · 101 → LOCAL_SEARCH+SMART_MERGE · 202 → ELITE.<br>🔴 **`LOCAL_SEARCH` ne produit RIEN à corridor 0 et produit la gagnante, seule, à 0,001, 0,005 et 0,010.** La règle « il ne gagne jamais », que les données à corridor 0 justifiaient parfaitement, aurait **jeté la gagnante dans 4 configurations sur 8**. Idem pour « ne garder que les 2 blocs ».<br>**Chaque générateur mérite sa place dans au moins un régime, aucun dans tous.** C'est §13 en acte : *on ne prédit pas un résultat de simulation.*<br>✅ **Le levier qui marche est la PROFONDEUR, pas la population** (§17-27) : générer large, cribler peu (10 tirages, sans perte), approfondir étroit sur les ~10 finalistes. C'est une **réallocation**, pas une dépense en plus — ce qu'on cesse de payer à des stratégies à 3× la gagnante finance la profondeur là où elle décide. 📏 Coût mesuré : **~0,15 s par (stratégie × tirage)** au stade final, la Phase A (~730 s) n'ayant pas à être refaite. |
| 27 | 🟢 **L'entonnoir Phase A → Phase B NE FUIT PAS.** D3 du 2026-08-11, et le contrôle 4 de §20 est satisfait : le criblage **atteint** bien le calcul — `n_ranked` vaut **133 / 140 / 219 / 228 / 445** pour un criblage à 10 / 50 / 100 / 25 tirages et `keep30`. Malgré 445 stratégies classées contre 133, la gagnante est **toujours** `[544, 531]`, 2 blocs, SYM, et le score est bit-identique. **Cribler à 10 tirages ne perd rien, et garder 30 survivantes ne trouve rien de mieux.** ⚠️ C'est un résultat sur **une** graine et **un** empilement : il ferme A20 pour ce cas, pas en général. |
| 23 | 🔴 **La propagation d'état de la Phase A laisse SIX paramètres de modèle à leur valeur neutre.** Trouvé le 2026-08-11 par balayage AST de tous les appels aux noyaux. `certus_strat_growth.py:1245` passe **16 arguments à un noyau qui en compte 22** : `affine_scale` (1.0), `affine_offset` (0.0), `poem_enabled` (**True**), `smoothing_window` (1), `n_H_real` / `n_L_real` (le corridor) restent donc aux défauts. **Conséquence** : en Phase A, l'historique propagé de couche en couche est simulé **sans dérive photométrique, sans corridor d'indice, POEM forcé actif et sans lissage**, pendant que les candidates de la couche suivante sont jugées **avec** les quatre. L'historique de la Phase A est donc systématiquement plus propre que le monde où vivent ses candidates. 🔑 **Et le docstring du noyau énonce exactement le principe violé** (`:1231`) : *« The states propagated here become the history on which the next layer will be judged: evaluating them without the block history while the candidates were evaluated with it would produce a Phase A inconsistent with itself. »* Même argument, quatre paramètres de plus. ⚠️ Touche **toutes** les mesures corridor, **toutes** les mesures affines (le ×17,5 de §12.1) et les bras POEM-off, où la Phase A a propagé **avec** POEM. |
| 24 | 🟠 **Le gain de compensation de la Phase A est mesuré AVEC la distorsion affine mais SANS le corridor.** `certus_strat_batch.py:229` et `:237` passent `aff_s_0`/`aff_o_0` et laissent `n_H_real`/`n_L_real` au défaut. Les deux appels sont volontairement à bruit nul — c'est une dérivée, pas une simulation, et c'est écrit — mais alors il faut être cohérent : **soit les deux perturbations, soit aucune.** |
| 25 | 🔴 **Un repli silencieux réinstalle le bug qu'on vient de corriger.** `certus_strat_batch.py:323` : `if wl_max <= wl_min: wl_min, wl_max = corridor_wl_range(layer_wavelengths, layer_wavelengths)`. Un appelant qui oublie la paire `corridor_lo/hi` retombe donc **sans le moindre message** sur la normalisation par les seules λ de monitoring — le défaut du 2026-08-10, celui qui a invalidé toutes les mesures de corridor antérieures. Contrôle 4 de §20 dans sa forme la plus pure : *ça ne produit pas d'erreur, ça produit un résultat plausible.* **Doit lever, pas se rabattre.** |
| 20 | 🔴 **La Phase A ne reçoit PAS l'enveloppe du corridor, et un docstring affirme le contraire.** Trouvé le 2026-08-10. `corridor_wl_range` (`certus_strat_batch.py:45`) écrit : *« ONE caller computes this and passes it to the growth batch, **the Phase A batch** and the scoring kernel »*. C'est faux. `validate_wavelengths_batch` n'a **aucun** paramètre `corridor_lo`/`corridor_hi` et recalcule aux lignes 128-131 : `wl_min = np.min(candidate_wls)`, `wl_max = np.max(candidate_wls)`. Or `candidate_wls` est la liste **filtrée par couche** (`certus_strat_service.py:1060`), donc le domaine de normalisation **change à chaque couche** et peut être très étroit. La grille spectrale vaut `wl_range 400–700`, le balayage `scan_wl 450–700` : même au mieux, `u(400) = −1,4` sort de ±1. **C'est le bug corrigé côté Phase B, resté entier côté Phase A** — et §12.3 le demandait explicitement. ⚠️ Correction = signature de noyau = recompilation : **ne pas la faire pendant une campagne**. |
| 21 | ⚠️ **`MAX_LOOKBACK = 4` n'était documenté nulle part ici.** `certus_strat_growth.py:526`. L'historique de bloc rejoué par POEM est écrêté à **4 couches**, quelle que soit la longueur du bloc. C'est délibéré et testé (`tests/unit/test_strat_poem.py:169`), mais il faut le savoir pour lire tout résultat sur le nombre de blocs : **la valeur d'un bloc long est plafonnée par construction.** Un bloc de 24 couches ne rejoue que ses 4 dernières. |
| 22 | ⚠️ **L'historique est échantillonné 1,33× plus grossièrement que la couche courante**, et le commentaire du noyau annonce 4×. `NPTS_PREV = 16` par couche d'historique contre `NPTS = 64` sur `3 × d_nom`, soit 21,3 points par `d_nom` : le rapport de **densité** vaut 21,33/16 = **1,33**, pas 64/16 = 4 — les deux balayages ne couvrent pas la même longueur (`certus_strat_growth.py:511`). Conséquence réelle : un même point physique ne porte pas la même densité de bruit selon qu'il est lu comme historique ou comme couche courante. La grille cadence-machine corrige cela (ligne 652) mais elle est derrière `if smoothing_window > 1` — la soudure du §17-2. **Toutes les mesures faites à `reading_smoothing_window = 1` ont donc l'échantillonnage asymétrique.** |
| 11 | 🔴 **`poem_enabled` ne peut pas être désactivé par l'environnement.** Mesuré le 2026-08-09 : deux runs lancés avec `CERTUS_POEM_ENABLED=0` ont rendu `CONFIG={"poem_enabled": true}` et des `RESULT` **bit-identiques** aux runs POEM actif. Cause : `probe_anchor_noise_pipeline.py:94` teste `os.environ.get(...) not in {"0", "false", "False"}` — une valeur `"0 "` avec un espace de fin, que `set VAR=0 ` produit sans le montrer, rend **True**. Les amplitudes affines y survivent parce que `float("0.05 ")` avale l'espace ; le test d'appartenance non. **Correctif : `.strip()` sur toutes les variables lues**, et une valeur inattendue doit lever, pas retomber silencieusement sur le défaut. ⚠️ **A12 est inexécutable tant que ce n'est pas corrigé** — et elle rendra des chiffres parfaitement crédibles. |
| 9 | **`MachineModel` n'a toujours aucun consommateur en production.** Vérifié le 2026-08-09 : 5 occurrences en tout — la classe, deux ré-exports, un import, le test. Et `trigger_tolerance: float = 0.05` reste documenté « in T units (0..1) » alors que les consommateurs réels divisent par 100 : **piège ×100**. Manquent toujours vitesse de dépôt et cadence, qui sont pourtant en §9. |

**Le point 7 est refermé pour l'avenir** (`f4ada2d`) : la sonde écrit désormais sa
configuration effective dans `r["config"]` et dans le nom du fichier. Les deux artefacts déjà
produits, eux, restent inexploitables — **on ne peut pas les rattraper, il faut les
refaire.**

## 18. Autres chantiers ouverts

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
