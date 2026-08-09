# ORDRE DE MISSION — à exécuter tel quel

## LIS CES SIX RÈGLES. ELLES PRIMENT SUR TOUT.

**RÈGLE 1 — Tu ne modifies AUCUN fichier de code.**
Pas un `.py`, pas un `.json`, pas un `.toml`. Ta seule écriture autorisée est d'ajouter du
texte à la fin de `reports/RAPPORT_GEMINI.md`.
**Si une étape te semble demander de modifier du code, tu t'arrêtes et tu le signales.**

**RÈGLE 2 — Une étape à la fois, dans l'ordre, sans en sauter.**
Tu ne lis pas l'étape suivante avant d'avoir écrit le rapport de l'étape courante.

**RÈGLE 3 — Tu colles la sortie, tu ne la résumes jamais.**
Copier-coller intégral du terminal. Pas de reformulation, pas d'extrait, pas de « en gros ».

**RÈGLE 4 — Si tu n'as pas de sortie, tu écris exactement : `JE N'AI PAS MESURÉ`.**
C'est une réponse acceptable. Inventer un chiffre ne l'est pas. Une seule phrase inventée
annule toute la mission.

**RÈGLE 5 — Une mesure, une machine.**
Pendant qu'une commande de mesure tourne, tu ne lances **rien d'autre**. Ni test, ni
recherche, ni autre terminal. Tu attends qu'elle se termine.

**RÈGLE 6 — En cas de doute, tu t'arrêtes.**
Tu n'improvises jamais. Tu écris ce que tu as vu, et tu attends des instructions.
**S'arrêter n'est jamais une faute. Inventer, si.**

---

## AVANT TOUT — le bon terminal, et lui seul

🔴 **Tu dois utiliser l'INVITE DE COMMANDES (`cmd.exe`). PAS PowerShell.**

C'est impératif. Les étapes 3, 4 et 5 règlent des variables avec `set VAR=valeur`, qui est de
la syntaxe `cmd.exe`. Dans PowerShell, `set` fait autre chose : **la variable n'arriverait pas
au calcul**, le run tournerait avec les valeurs par défaut, et te rendrait un chiffre
parfaitement crédible et **faux**. Rien ne te préviendrait.

**Comment ouvrir le bon terminal** : touche Windows, tape `cmd`, ouvre « Invite de
commandes ». La fenêtre doit afficher une ligne du genre `C:\Users\...>`.
Si elle affiche `PS C:\Users\...>`, **tu es dans PowerShell : ferme et recommence.**

**Vérifie que tu es au bon endroit, dans le bon terminal :**

```bat
cd /d C:\dev\gemini
```

```bat
set CERTUS_TEST_SHELL=cmd_ok
```

```bat
echo %CERTUS_TEST_SHELL%
```

- Si ça affiche `cmd_ok` → **c'est bon, continue.**
- Si ça affiche `%CERTUS_TEST_SHELL%` ou autre chose → **tu n'es pas dans `cmd.exe`.
  ARRÊTE**, ouvre une Invite de commandes, et recommence.

Toutes les commandes ci-dessous se lancent depuis ce dossier, **dans cette même fenêtre**, et
**toujours** avec `.venv\Scripts\python.exe`. **Jamais `python` tout court.**

⚠️ **Ne ferme pas la fenêtre entre deux étapes.** Les variables réglées avec `set` sont
perdues à la fermeture, et les étapes suivantes tourneraient avec les mauvaises valeurs.

---

# ÉTAPE 0 — Vérification d'environnement

**Commande, à copier telle quelle :**

```bat
.venv\Scripts\python.exe scripts\preflight.py
```

**Ce que tu dois faire de la sortie :**

- Si la dernière ligne est exactement `PREFLIGHT=GO` → tu peux continuer à l'étape 1.
- Si la dernière ligne est `PREFLIGHT=STOP` → **ARRÊTE TOUT.** Colle la sortie dans le
  rapport, écris `MISSION INTERROMPUE A L'ETAPE 0`, et n'exécute plus rien.

**Rapport de l'étape 0** — ajoute ceci à `reports/RAPPORT_GEMINI.md` :

```
## ETAPE 0 — preflight
Commande : .venv\Scripts\python.exe scripts\preflight.py
Sortie :
<colle ici la sortie complete>
Verdict lu : GO ou STOP
```

---

# ÉTAPE 1 — Reproduire les sondes A1 et A2

Objectif : vérifier que ta machine donne les mêmes chiffres que ceux déjà mesurés.
**Durée : environ 3 minutes.** Aucune modification, la sonde ne fait que calculer.

**Commande :**

```bat
.venv\Scripts\python.exe scripts\probe_tp_fabrication.py
```

**Les trois chiffres à vérifier dans la sortie**, dans cet ordre :

| Ligne à chercher | Valeur attendue | Tolérance |
|---|---|---|
| `k=1, threshold 1.66 A, N=800` | `99.955 %` | entre 99,0 et 100,0 |
| `k=8, threshold 0.354 A, N=800` | `100.000 %` | exactement 100,000 |
| `same, noise x0.01` | `0.000 %` | exactement 0,000 |

**Arrêts durs :**

- Si la sortie contient `STEP1=FAILED` → **ARRÊTE.** Écris `MISSION INTERROMPUE A L'ETAPE 1`.
- Si l'un des trois chiffres sort de sa tolérance → **ARRÊTE**, colle la sortie, signale-le.
- La ligne `A1=FAIL` est **NORMALE et ATTENDUE**. Ce n'est pas une erreur de ta part. C'est le
  résultat scientifique déjà connu. **Ne cherche pas à la corriger.**

**Rapport de l'étape 1 :**

```
## ETAPE 1 — sondes A1 et A2
Commande : .venv\Scripts\python.exe scripts\probe_tp_fabrication.py
Sortie :
<colle ici la sortie complete>
Les trois chiffres attendus sont-ils dans leur tolerance ? OUI / NON
```

---

# ÉTAPE 2 — Le point de référence

Objectif : vérifier que le banc rend deux fois le même chiffre.
**Durée : environ 25 minutes.** Ne lance rien d'autre pendant ce temps.

**Les deux commandes, dans l'ordre, dans le MÊME terminal :**

```bat
set CERTUS_BENCH_TIMEOUT_S=5400
```

```bat
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

**Ce que tu dois lire dans la sortie, dans cet ordre. Ne saute aucune vérification :**

1. Cherche `WAIT_EXIT`. **S'il vaut `timeout` → le run n'a pas abouti. NE LIS PAS `RESULT`.**
   Relance une fois avec `set CERTUS_BENCH_TIMEOUT_S=7200`. Si ça recommence, arrête.
2. Cherche la ligne qui commence par `CONFIG=`. **Colle-la dans le rapport.** Elle dit avec
   quels paramètres le calcul a tourné.
3. Cherche `RESULT=`. **Recopie-le dans le rapport.** Ce chiffre devient **ta référence** :
   c'est à lui que tu compareras les étapes 3, 4 et 5.

**Un seul arrêt dur : `RESULT=None`, ou `WAIT_EXIT=timeout`.**
Le run n'a pas abouti, ce n'est pas un résultat. Relance **une fois** avec
`set CERTUS_BENCH_TIMEOUT_S=7200`. Si ça recommence, arrête et signale.

**Le chiffre de référence connu est `0.00294862737122675`**, mesuré sous **Python 3.14.6**.

- S'il est identique → note `IDENTIQUE` et continue.
- **S'il diffère, ce n'est PAS une erreur et tu ne t'arrêtes PAS.** Note `DIFFERENT`, recopie
  la version de Python de l'étape 0, et **continue normalement**. Une cause parfaitement
  légitime existe : l'interpréteur a changé. Les étapes suivantes se comparent à **ton**
  chiffre, pas à l'ancien.
- **Ne relance jamais un run en espérant un autre chiffre.** Le chiffre que tu obtiens est
  le résultat.

**Rapport de l'étape 2 :**

```
## ETAPE 2 — point de reference
Version de python (relevee a l'ETAPE 0) :
Commandes :
  set CERTUS_BENCH_TIMEOUT_S=5400
  .venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
WAIT_EXIT lu :
Ligne CONFIG= :
RESULT lu (= MA REFERENCE pour les etapes 3, 4 et 5) :
Chiffre connu : 0.00294862737122675   (mesure sous Python 3.14.6)
IDENTIQUE / DIFFERENT :
Sortie complete :
<colle ici>
```

---

# ÉTAPE 3 — POEM sous distorsion : quatre mesures

Objectif : la mesure la plus importante du projet. Elle dit si le mécanisme central
fonctionne.
**Durée : environ 100 minutes** (4 runs de 25 min). Rien d'autre pendant ce temps.

**Tu vas lancer QUATRE runs.** Pour chacun : tu tapes d'abord les lignes `set`, **puis** la
ligne de calcul, **dans le même terminal**. Tu attends la fin avant de passer au suivant.

### Run 3.1 — POEM actif, distorsion absente

```bat
set CERTUS_BENCH_TIMEOUT_S=5400
set CERTUS_POEM_ENABLED=1
set CERTUS_AFFINE_SCALE_AMP=0.0
set CERTUS_AFFINE_OFFSET_AMP=0.0
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

### Run 3.2 — POEM actif, distorsion présente

```bat
set CERTUS_POEM_ENABLED=1
set CERTUS_AFFINE_SCALE_AMP=0.05
set CERTUS_AFFINE_OFFSET_AMP=0.02
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

### Run 3.3 — POEM inactif, distorsion absente

```bat
set CERTUS_POEM_ENABLED=0
set CERTUS_AFFINE_SCALE_AMP=0.0
set CERTUS_AFFINE_OFFSET_AMP=0.0
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

### Run 3.4 — POEM inactif, distorsion présente

```bat
set CERTUS_POEM_ENABLED=0
set CERTUS_AFFINE_SCALE_AMP=0.05
set CERTUS_AFFINE_OFFSET_AMP=0.02
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

**Pour chacun des quatre : vérifie `WAIT_EXIT`, colle la ligne `CONFIG=`, relève `RESULT`.**

🔴 **Tu ne tires AUCUNE conclusion.** Tu ne dis pas « POEM fonctionne » ni « POEM ne
fonctionne pas ». Tu remplis le tableau, c'est tout. L'interprétation ne t'appartient pas.

**Rapport de l'étape 3 :**

```
## ETAPE 3 — POEM sous distorsion
| run | POEM | distorsion | WAIT_EXIT | RESULT |
|-----|------|------------|-----------|--------|
| 3.1 | on   | non        |           |        |
| 3.2 | on   | oui        |           |        |
| 3.3 | off  | non        |           |        |
| 3.4 | off  | oui        |           |        |

Lignes CONFIG= des quatre runs :
<colle les 4>

Sorties completes :
<colle les 4>
```

---

# ÉTAPE 4 — Balayage du corridor d'indice

**Durée : environ 75 minutes** (3 runs). Rien d'autre pendant ce temps.

⚠️ **D'abord, remets les variables de l'étape 3 à zéro**, sinon tu mesures deux choses en même
temps et le résultat ne veut plus rien dire :

```bat
set CERTUS_POEM_ENABLED=1
set CERTUS_AFFINE_SCALE_AMP=0.0
set CERTUS_AFFINE_OFFSET_AMP=0.0
```

### Run 4.1 — corridor nul

```bat
set CERTUS_INDEX_CORRIDOR=0.0
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

### Run 4.2 — corridor moitié

```bat
set CERTUS_INDEX_CORRIDOR=0.0025
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

### Run 4.3 — corridor plein

```bat
set CERTUS_INDEX_CORRIDOR=0.005
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

**Vérification mécanique, sans jugement :** le `RESULT` du run 4.1 doit être **identique** à
celui de l'étape 2. Si ce n'est pas le cas, **signale-le** — n'essaie pas de comprendre
pourquoi.

**Rapport de l'étape 4 :**

```
## ETAPE 4 — corridor d'indice
| run | corridor | WAIT_EXIT | RESULT |
|-----|----------|-----------|--------|
| 4.1 | 0.0      |           |        |
| 4.2 | 0.0025   |           |        |
| 4.3 | 0.005    |           |        |

RESULT du run 4.1 identique a celui de l'ETAPE 2 ? OUI / NON
Lignes CONFIG= des trois runs :
<colle les 3>
Sorties completes :
<colle les 3>
```

---

# ÉTAPE 5 — Marge de sélection des longueurs d'onde

**Durée : environ 25 minutes.**

⚠️ **Remets d'abord le corridor à zéro :**

```bat
set CERTUS_INDEX_CORRIDOR=0.0
```

Puis :

```bat
set CERTUS_PHASE_A_MARGIN=3.33
.venv\Scripts\python.exe scripts\probe_anchor_noise_pipeline.py full 1.0 42
```

**Rapport de l'étape 5 :**

```
## ETAPE 5 — marge Phase A a 3.33
WAIT_EXIT lu :
Ligne CONFIG= :
RESULT lu :
RESULT de l'ETAPE 2 (marge 1.66, pour comparaison) :
Sortie complete :
<colle ici>
```

---

# FIN DE MISSION

Quand les cinq étapes sont faites, ajoute à la fin du rapport :

```
## FIN DE MISSION
Etapes terminees : 0 / 1 / 2 / 3 / 4 / 5   (barre celles qui ne sont pas faites)
Etapes interrompues et pourquoi :
Ce que je n'ai pas mesure :
Fichiers que j'ai modifies : AUCUN   (si ce n'est pas AUCUN, dis lesquels et pourquoi)
```

---

## CE QUE TU NE FAIS JAMAIS

| Interdit | Pourquoi |
|---|---|
| Modifier un fichier `.py`, `.json` ou `.toml` | Règle 1. Ta mission est de **mesurer**, pas de corriger. |
| Modifier `example/example_strat/JSON-strat-example.json` | Toutes les mesures suivantes deviendraient nulles. |
| Lancer `ruff check --fix` | Cassserait des ré-exports volontaires dans tout le projet. |
| Supprimer quoi que ce soit dans `reports/` | Ce sont les résultats scientifiques de l'utilisateur. Irrécupérables. |
| Lire un `RESULT` sans avoir vérifié `WAIT_EXIT` | Un run qui n'a pas fini **ressemble** à un résultat. |
| Relancer un run parce que le chiffre te surprend | Le chiffre surprenant **est** l'information. |
| Écrire une conclusion, une interprétation, un « donc » | Tu mesures. Tu n'interprètes pas. |
| Lancer deux commandes en parallèle | Le banc sature tous les cœurs. Les deux mesures seraient fausses. |
| Continuer après un arrêt dur | Tout ce qui suivrait serait invalide. |

**Si tu hésites entre deux façons de faire, c'est que l'instruction est mauvaise. Arrête-toi
et signale-le.** C'est le document qui est en tort, pas toi.
