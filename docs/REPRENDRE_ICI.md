# 🔴 REPRENDRE ICI — état gelé le 2026-08-24 à 15:30

> ⏳ **UN RUN TOURNE** : `bash scripts/enchainer_hysteresis.sh hysteresis_2026-08-24 404`,
> lancé à **15:20**, fin vers **16:00**. Il tranche l'anomalie du §1ter — voir la fin du §0000.
> 🔑 Il mesure des **taux de plantage**, pas des durées : travailler sur la machine pendant
> qu'il tourne ne fausse **que son horloge**.
>
> 🟢 `pytest tests/oracle/ tests/unit/` : **2949 passed, 5 skipped, 0 échec** (15:19).
> `ruff` propre. `coherence_md.py` : **1 point**, le faux positif instruit.
>
> ⚠️ **Rien n'est commité** — les mesures des 23 et 24/08, les quatre nouveaux scripts et
> toutes les corrections de ce fichier vivent uniquement dans l'arbre de travail. Committer
> **publie** (`core.hooksPath` armé sur `.githooks`, dépôt public) : décision de 👤.

> Ce fichier dit **où on s'est arrêté** et **la commande exacte pour repartir**. Il est le
> premier à lire, avant `CLAUDE.md`.

---

## 0000. ⏳ CE QUI TOURNE EN CE MOMENT — lis ceci en premier

**Deux runs sont EN VOL**, lancés à **17:33**. Ils écrivent dans `reports/docp_2026-08-23/`.
🟢 **Relevés à 18:01 : vivants, au bloc 10, et la réponse est déjà tombée — voir plus bas.**

🔴 **`durees.log` n'est écrit QU'À LA FIN du run.** Il est vide pendant toute la mesure et cela
**ressemble à une panne**. L'avancement réel se lit dans les journaux :

```bat
findstr /C:"Best strategy ready" reports\docp_2026-08-23\journal_s404.log
```

| | |
|---|---|
| **ce qui tourne** | `probe_blocs_vs_plantage.py r75x2 deep 0 0 2 0 404` et `... 505`, en parallèle |
| **pourquoi** | mesurer ce que le **DOCP** rapporte, à une seule variable |
| **durée attendue** | ~60 min chacune → fin recalculée sur la cadence réelle : **~18:34** |
| **où** | journaux `reports/docp_2026-08-23/journal_s404.log` et `_s505.log`, durées dans `durees.log` |

### 📏 LE RUN SEUL A TOURNÉ — 1,23× de débit à deux runs, mesuré le 2026-08-23 à 19:17

```bat
bash scripts\mesure_solo_vs_parallele.sh solo_2026-08-23 404
```

Même graine, mêmes arguments que les runs en vol, **seul** sur la machine. Journal dans
`reports/solo_2026-08-23/`, contexte de concurrence dans son `CONTEXTE.txt`.

```
16 blocs, TOUS identiques au bit (RMSE et populations minees)

               a DEUX     SEUL      ecart
 cumul 75->1   57:46     35:36     -38,4 %

 debit a deux runs = 1,23x celui d'un run seul     (2,00 = parfait, 1,00 = nul)
 repere du 22/08 a 2133 MHz        = 1,29x
```

🔑 **LA MÉMOIRE EST ÉCARTÉE UNE SECONDE FOIS, ET PAR UN AUTRE CHEMIN.** Le passage à l'échelle
vaut **1,23×** à 3600 MHz contre **1,29×** à 2133 : la bande passante ne change pas davantage la
*concurrence* qu'elle ne changeait la *durée*. Deux mesures indépendantes, même verdict.

🔑 **Et le rapport des durées suffit à dire pourquoi** : si un run seul occupe une fraction `f`
de la machine, deux runs en demandent `2f` et ralentissent d'autant, donc
`f = (T_à_deux / T_seul) / 2 = 1,62 / 2 =` **81 %**.

> **Un seul run occupe déjà 81 % de la machine.** Le second n'a presque plus rien à prendre.

📌 **Il n'y a donc pas de goulot exotique à trouver — la machine est simplement PLEINE**, et le
repère indépendant du 22/08 (*« le CPU plafonne à 74 % en solo »*) dit la même chose à 7 points
près. Le levier est le **nombre de cœurs**, pas le cache.

### 🔴 ET LA PREMIÈRE VERSION DE `lire_solo_vs_parallele.py` CONCLUAIT LE CONTRAIRE

Elle lisait *« facteur bas → quelque chose de PARTAGÉ sature → le L3 de 16 Mo → acheter un CPU à
gros cache »*. **Elle sautait par-dessus l'explication la plus simple, qui suffit** : une machine
pleine produit ce facteur toute seule, sans aucune contention de cache.

⚠️ **C'est exactement la faute de *« le goulot est la bande passante mémoire »*** — nommer un
coupable sans avoir éliminé le trivial. Corrigée dans l'outil, qui déduit et affiche maintenant
l'occupation avant de désigner quoi que ce soit.

### 🔴 NE CONTRÔLE PAS LES ARTEFACTS PAR `sha256` — il crie pour rien

Les trois artefacts de la graine 404 (12:41 à 2133, 18:33 à 3600, 19:16 seul) ont **trois
empreintes différentes** pour une **taille identique à l'octet**. Comparés champ par champ :

```
seuls  stamp  et  instrument  different -- tout le contenu scientifique est IDENTIQUE
```

`instrument` vaut `656fbf6` pour le run de 12:41 et `e577221` pour les deux autres : du code de
production **a** changé entre les deux. Vérifié — c'est une chaîne `reserve=` de
`certus_strat_leviers.py`, du texte de documentation, inerte. 🔑 **Et les artefacts le
prouvent mieux que la lecture du diff** : à code « différent », résultats identiques.

📌 Le bon contrôle est donc **champ par champ en excluant `stamp` et `instrument`**, jamais un
hachage du fichier entier.

### 🔵 CE QUI RESTE NON MESURÉ, ET QUI DÉCIDERAIT UN ACHAT

| | |
|---|---|
| **le CPU % réellement consommé par un run seul** | l'occupation de 81 % est **déduite** des durées, pas observée. Si le CPU réel est nettement plus bas, l'écart est de la contention — et là seulement le cache redevient suspect |
| **la dispersion de run à run** | toujours `n = 1` dans chaque condition. C'est elle qui dit si les ±5 % du DOCP sont seulement lisibles |
| 🔒 **le prix caché** | ni les CPU à gros cache ni ceux à beaucoup de cœurs n'ont d'iGPU, et cette machine n'a **pas de carte graphique** (`Win32_VideoController` ne rend que le Radeon intégré). L'addition en comprend une |

### 🔴🔴 LE DOCP NE RAPPORTE RIEN — et le « ~5 % » qu'il semblait coûter est DANS LE BRUIT

> ⚠️ **Ce titre disait « IL COÛTE ~5 % » jusqu'au 2026-08-24.** La dispersion de run à run a
> été mesurée depuis : elle vaut **2,2 à 3,7 %**, du même ordre que l'écart attribué au DOCP.
> Le sous-titre de la sous-section suivante porte le compte. Ce qui reste vrai, et c'était la
> question posée : **aucun gain.**

Le **même protocole** a tourné aujourd'hui à **12:41**, **même code**, mêmes graines :
`reports/orchestre_r75x2_20260823_124146/`. **Seule la mémoire a changé entre les deux.**

```
AVANT   4 barrettes · 48 Go · 2133 MHz · DOUBLE canal
APRES   2 barrettes · 32 Go · 3600 MHz · DOUBLE canal

bande passante relative :  2133 x 2 = 4266   ->   3600 x 2 = 7200     +69 % ATTENDUS
mesure sur six blocs, deux graines                                    -4,7 % RENDUS
```

📏 **Durée par nombre de blocs** (`Mining found` → `Best strategy ready`) :

```
              seed 404                            seed 505
bloc     AVANT    APRES    ecart          bloc     AVANT    APRES    ecart
 75       22 s     22 s     0,0 %          75       22 s     21 s    -4,5 %
 15      3:04     3:12     +4,3 %          15      3:05     3:11    +3,2 %
 14      5:14     5:11     -1,0 %          14      5:16     5:22    +1,9 %
 13      5:08     5:11     +1,0 %          13      5:07     5:08    +0,3 %
 12      6:09     6:38     +7,9 %          12      5:48     6:32   +12,6 %
 11      5:56     6:31     +9,8 %          11      6:23     6:46    +6,0 %

cumul 15->11   25:50 -> 27:04   +4,8 %     cumul   26:04 -> 27:18   +4,7 %
```

**Les deux graines donnent +4,7 % et +4,8 %**, à la dixième de pour-cent près.

🔴 **ET J'AI D'ABORD PRÉSENTÉ CETTE CONCORDANCE COMME UNE CONFIRMATION. C'EST FAUX, et c'est
encore l'erreur de §001.** Les deux graines ont tourné **en même temps, sur la même machine, dans
le même état thermique, avec les mêmes processus voisins**. Elles ne sont pas deux répétitions de
la condition MATÉRIELLE : elles partagent tous ses facteurs. Leur accord démontre que **la charge
est reproductible**, pas que l'écart matériel est réel.

🔑 **Sur la question posée — 2133 contre 3600 — l'expérience compte n = 1, pas n = 2.** Le
protocole n'a tourné qu'**une fois** dans chaque configuration, et rien ne dit ce que deux runs
de configuration IDENTIQUE écarteraient entre eux. ⚠️ Tant que cette dispersion-là n'est pas
mesurée, **+4,7 % n'est pas distinguable du bruit de run à run**, et il ne justifie aucune
décision matérielle.

📌 Le contrôle qui trancherait est bon marché : **rejouer le même protocole une seconde fois dans
la configuration actuelle** (~1 h). Si deux runs identiques s'écartent déjà de ~5 %, l'écart
DOCP disparaît ; s'ils s'écartent de 0,5 %, il devient réel et il faut comprendre pourquoi.

🔑 **Et le DOCP est bien ACTIF — vérifié, pas supposé :**

```
DIMM_A2  Corsair CMK32GX4M2Z3600C18  16 Go  Speed 3600  ConfiguredClockSpeed 3600
DIMM_B2  Corsair CMK32GX4M2Z3600C18  16 Go  Speed 3600  ConfiguredClockSpeed 3600
Ryzen 7 5700G · 8 coeurs / 16 threads · 11,6 Go libres sur 31,3 -> aucun swap
```

```bat
powershell -NoProfile -Command "Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator,PartNumber,Speed,ConfiguredClockSpeed"
```

🔴 **DONC LA BANDE PASSANTE MÉMOIRE N'EST PAS LE GOULOT.** L'hypothèse portée par la dernière
ligne du tableau « ce qui reste ouvert » de §00 — *« le CPU plafonne à 74 % en solo : le goulot
est la bande passante mémoire »* — est **réfutée par la mesure**. Le DOCP était gratuit ; il est
fait ; il ne rend rien.

⚠️ **Deux réserves à citer avec le chiffre, sous peine de dire faux :**

- la config est passée de **4 barrettes à 2** en même temps que la fréquence montait : le nombre
  de **rangs** a été divisé par deux, et l'entrelacement de rangs travaillait pour l'ancienne.
  On ne mesure donc pas « 2133 contre 3600 », on mesure **« 4×2133 contre 2×3600 »** ;
- les blocs **12 et 11** portent l'essentiel de la perte (+6 à +12,6 %) alors que 15, 14 et 13
  sont à ±2 %. La perte n'est pas uniforme et **on ne sait pas pourquoi**.

📌 **Ce que cela dit du reste** : si la mémoire n'est pas le goulot, la piste qui reste pour
accélérer est celle du §0.2bis — `certus_strat_workers.py:1452` force `max_workers = 1` sur la
boucle des nombres de blocs. ⚠️ Et le commentaire qui l'accompagne dit ce qu'il évitait
(*oversubscription* Numba, blocages) : **ne pas le remonter sans comprendre.**

### 📏 LA DISPERSION EST MESURÉE — 2,2 à 3,7 %, et elle AVALE l'effet du DOCP

**Mesuré le 2026-08-24 à 15:16**, à la demande de 👤 : la **même paire** de runs, dans la
**même** configuration 3600 MHz, machine propre. `reports/docp_propre_2026-08-24/`. Les 16 blocs
sont identiques au bit à ceux de la veille — seule la journée change.

```
                                    s404      s505
 run complet                       +6,1 %    +6,4 %
 hors chauffe (blocs 14 a 1)       +3,7 %    +3,7 %
 hors chauffe ET hors bloc 8       +2,2 %    +2,2 %

 pour memoire, « l'effet DOCP »    +4,9 %    +5,0 %
```

🔑 **L'effet du DOCP vaut 1,3 à 2,3 fois la dispersion de la machine. Il n'en est pas séparé.**
Avec `n = 1` dans chaque configuration, on ne peut affirmer ni que le 3600 MHz est plus lent, ni
qu'il est plus rapide. 🔒 **Ce qui reste établi, et c'était la question : aucun gain.** La
question mémoire est **close** — rien à racheter, rien à remonter.

📌 Et elle ne se rouvrira pas : remesurer le 2133 MHz demanderait de redémonter la machine.

### 🔴 DEUX PIÈGES DE MÉTHODE, PAYÉS LE MÊME JOUR

**1. LE DÉMARRAGE À FROID.** Windows avait redémarré la veille à **19:38**, 21 min après la
dernière mesure. Le premier run du lendemain partait donc sur des caches de fichiers **froids** :

```
bloc 75   0:22  ->  1:07   +204 %        \
bloc 15   3:12  ->  3:57    +23 %         >  transitoire, il s'effondre
bloc 14   5:11  ->  5:31    +6,4 %       /
```

⚠️ **Les blocs 75 et 15 sortent de tout calcul de durée.** 🔑 Et il a fallu **déduire** la
chauffe d'une courbe décroissante, faute d'un champ qui la dise : `CONTEXTE.txt` porte
maintenant `demarrage_windows`. 📌 La mesure DOCP de la veille n'est **pas** touchée — les deux
runs comparés suivaient des heures d'activité, tous deux chauds.

**2. L'ÉCHANTILLONNEUR A DONNÉ UN FEU VERT FAUX.** `max_autres_python = 0` alors que la mesure
**était** polluée : des analyses lancées à la main pendant le run font sauter le **bloc 8** de
**+20,4 % et +21,4 %**, sur les deux graines, à la même minute. Le compteur relevait toutes les
120 s ; des commandes de quelques secondes passent entre les gouttes. Ramené à **20 s**, et le
champ est désormais étiqueté **PLANCHER**.

> 🔑 **Le vrai détecteur n'est pas le compteur, c'est la SIMULTANÉITÉ.** Une contamination
> extérieure frappe les deux graines à la même minute ; le bruit propre au calcul ne se
> synchronise pas. C'est le tableau des durées qui a trahi la pollution, pas l'instrument
> chargé de la voir.

🔒 **Et la règle qui en découle** : on ne fait **aucune analyse sur la machine qui mesure une
durée**. Une mesure de taux de plantage, elle, s'en moque — seule son horloge en souffre.

### 🟢 LE CONTRÔLE D'INTÉGRITÉ PASSE — six blocs, deux graines, identiques au bit

🔑 **Le contrôle qui vaut mieux que `pytest` pour la RAM** : à graine et code identiques, les
résultats **doivent être identiques au bit**. 📌 **Et il n'est pas nécessaire d'attendre
l'artefact de fin de run** — le journal le porte bloc par bloc, donc il se fait **pendant** :

```
                     AVANT (12:41)      APRES (17:33, 3600 MHz)
RMSE par bloc        identiques a la 5e decimale, s404 ET s505
Mining found         601 / 601 / 601 / 602 / 601      identiques
Screening results    601 / 601 / 601 / 666 / 601      identiques
Full pass survivors   16 /  35 /  36 /  37            identiques
```

**Aucun écart.** La mémoire est stable, aucune mesure de la journée n'est suspecte, et la
comparaison de durées ci-dessus porte bien sur **exactement le même travail**.

🟢 **Et la référence ne risque rien — vérifié dans le code, pas espéré.** Les deux runs en vol
produisent le nom `blocs_vs_plantage_r75x2_deep_s404.json`, qui est **exactement** celui de la
référence de 12:41. `probe_blocs_vs_plantage.py:756-761` voit la collision, **conserve
l'ancien** et horodate le **nouveau** :

```
reports/blocs_vs_plantage_r75x2_deep_s404.json                  <- REFERENCE 12:41, intacte
reports/blocs_vs_plantage_r75x2_deep_s404_20260823_1834xx.json  <- le run DOCP
```

📌 **Donc cherche l'artefact neuf sous le nom HORODATÉ**, pas sous le nom nu. Et la ligne
`🟠 ... EXISTE DEJA` en fin de journal dit lequel est lequel.

📌 `pytest tests/oracle/ tests/unit/` est passé à **2941, 0 échec** après le remontage.

### ✅ CE QUI ÉTAIT « NON COMMITÉ » L'EST — corrigé le 2026-08-23 à 18:05

⚠️ **Cette section annonçait `scripts/orchestre_multigraine.py` et son test comme non
commités. C'était vrai à 17:49 et faux une minute plus tard** : ils sont entrés dans `e577221`
à 17:50, dans le commit même qui écrivait cet avertissement. `git log origin/<branche>..HEAD`
est **vide** — rien en attente de push.

📌 ✅ `scripts/_toc.py`, patch **jetable** du 2026-08-23 à 14:48 dont le travail était déjà dans
`3a9e097`, a été **supprimé le 2026-08-24**.

🔑 **La leçon d'instrument** : un état écrit dans un document se périme **à la seconde où on le
committe**. Le seul état qui ne ment pas est celui que `git status` rend.

### ⚠️ `coherence_md.py` rend « 1 point à instruire » — INSTRUIT, et il faut le LAISSER

```
RATE_MAX_VARIANTS_PER_STRATEGY   code = 40 | 1 ecart : CHANTIER_RATE.md:117 dit 3
```

**Ce signalement est un FAUX POSITIF, et la phrase visée doit rester telle quelle.**
`CHANTIER_RATE.md:117` écrit *« `RATE_MAX_VARIANTS_PER_STRATEGY` **valait** 3 »* — c'est le
récit de la contradiction A, réparée le 22/08. L'outil rapproche un mot et un nombre, il ne sait
pas lire un **passé composé**. 🔴 **Ne « corrige » pas cette ligne** : on effacerait l'histoire
d'une réparation pour faire plaisir à un script.

📌 Donc l'attendu du §0.4 et du §6 n'est plus `0 point(s) a instruire` mais **`1 point`, celui-ci
et lui seul**. Tout point supplémentaire est neuf et se lit.

🔑 **ET L'OUTIL A MANQUÉ LE VRAI DÉFAUT — parce qu'il ne lit que les `.md`.** La même constante
était citée périmée **dans le code de production** :

```
certus/core/certus_strat_robustness.py:562   RATE_MAX_VARIANTS_PER_STRATEGY = 40
certus/core/certus_strat_leviers.py:128      defaut=40
certus/core/certus_strat_robustness.py:956   docstring : « default 3 »     <- FAUX
```

La docstring décrivait le paramètre au public alors que le `params.get(...)` juste en dessous
(`:988`) retombe sur la constante, donc **40**. 🟢 **Corrigé le 2026-08-23.** ⚠️ Et la leçon
porte plus loin que la ligne : **`coherence_md.py` ne contrôle que les documents, jamais les
docstrings** — une valeur périmée y survit sans qu'aucun garde ne bronche.

---

## 000. 🟢 LA NUIT DU 22 AU 23 — la série 75 couches en entier, code de production

⚠️ **Les sections `00` et `§8.2ter` plus bas sont antérieures.** Elles restent vraies sur leur
objet ; celle-ci les complète et corrige trois affirmations qui étaient fausses.

### Ce que la campagne a rendu

Six composants, `deep`, fente **2,0 nm**, plage complète, notation finale sur la graine **42**
disjointe. Contrôle de cohérence : **0 point à instruire** — même profondeur (50/300), même
fente, même mode. Journaux dans `reports/nuit75_2026-08-22/`.

```
composant     citable        deposables  plantage   Rate dans les gagnantes
  75c         SEEL 0,2407       1790       3,00 %    1031 / 1790   (58 %)
  r75x1.5     SEEL 0,4552        627       0,33 %       0 /  627
  r75x1.75    SEEL 0,4651        708       0,67 %       0 /  708
  r75x2-2nm   SEEL 0,5697        175       1,67 %       0 /  175
  r75x2       RIEN                 0        100 %        --
  r75x0.5     RIEN                 0        100 %        --
```

🔑 **Le SEEL redevient monotone avec l'épaisseur** — 0,2407 → 0,4552 → 0,4651 → 0,56 — et tout
reste **faisable** sauf les deux extrêmes. Le tableau de référence à une seule graine disait
`x1,5 → limite (1 déposable)` et `x2 → ÉCHOUE` : ces verdicts décrivaient une **réalisation**,
pas un empilement.

### 🔑 Le Rate travaille, et de façon très inégale

Armé par défaut le 22/08 (`rate_by_swing`, plafond 40 sur les 50 meilleures). Résultat :

```
75c   graine 303 :  1744 des 2473 deposables portent une couche Rate   (70 %)
75c   graine  42 :  1031 des 1790                                       (58 %)
r75x1.5 / r75x1.75 / r75x2-2nm :  0 sur 1510                            ( 0 %)
```

Sur le 75c le classement le retient massivement ; sur les trois autres, **jamais** — offert à
chaque fois, jamais choisi. C'est le comportement voulu : il entre comme **coût**, pas comme
couperet. ⚠️ Et le contraste n'est **pas expliqué** : le 75c est le composant le plus **fin** de
la série, donc celui dont les couches ont le plus de dynamique optique. Ce n'est pas l'intuition
qu'on aurait eue, et personne ne l'a instruit.

📏 Coût mesuré du Rate armé : **+30 à 50 %** sur la durée d'un run (blocs à 4-6 min contre 3 min 45).

### 📏 Le gain du travail Rate, mesuré à UNE SEULE VARIABLE

Mêmes graines, même composant, même fente — seul le code change :

```
                strategies   deposables       SEEL
  404   ancien       2016         372       0,5599
        nouveau     4454         403       0,5629   (+0,5 %, sous le bruit de 2,59 %)
  505   ancien       1995         311       0,6112
        nouveau     4551         349       0,6105   (-0,1 %)
```

🔑 **Le Rate n'améliore pas la PRÉCISION, il élargit le CHOIX** : +8 à +12 % de déposables à
qualité égale, le SEEL restant sous le bruit de 2,59 %. C'est ce qu'on attend d'un mécanisme
qui **AJOUTE** des candidates sans en retirer.

### 🔴 Et l'union EFFACE ce gain — mesuré le 2026-08-23 à 14:18

```
union 404+505, notee sur la graine 42 disjointe :

  ancien code    262 deposables   SEEL 0,5642   8 blocs   0,33 %
  nouveau code   235 deposables   SEEL 0,5627   7 blocs   0,33 %      -0,27 %
```

**Sur `r75x2` à 2 nm, le travail Rate du 22/08 coûte ~2× en calcul et ne rend rien** au niveau
du chiffre citable : −0,27 % est dix fois sous le bruit. Le vivier s'élargit en amont, l'union
prend les meilleurs plans de chaque graine et les renote — un vivier plus large ne sert que si
les nouveaux venus sont **meilleurs**, et ici ils ne le sont pas.

📌 Un seul chiffre bouge hors du bruit : la gagnante passe à **7 blocs au lieu de 8**, plus
simple à déposer à qualité et plantage identiques.

⚠️ **Ne pas généraliser** : le `75c` retient le Rate dans **58 %** de ses déposables. Le
mécanisme sert quelque part ; pas sur ce composant-ci.

📏 **Et l'écart provisoire → définitif vaut −0,03 %** — le canal de malédiction du vainqueur est
nul cette fois. Mesuré à **+12,9 %** le 15/08, **+0,55 %** le 22/08, **−0,03 %** aujourd'hui :
ce n'est décidément pas une constante, et c'est pourquoi on le remesure à chaque campagne.

⚠️ **Et voilà ce qu'il coûte** : la population minée **double** — 2016 → 4454 et 1995 → 4551,
soit +121 % et +128 % — pour +8 à +12 % de déposables. 📏 Sur la durée d'un run, cela se lit
**+30 à 50 %** (blocs à 4-6 min contre 3 min 45).

---

## 001. 🔴 LE MULTI-TÉMOIN NE PEUT RIEN POUR `r75x2` NI `r75x0.5` — et voici pourquoi

L'escalade a tourné pour la première fois (2, 3 puis 4 témoins) et n'a rien rendu. En cherchant
la cause, **sur plans APPARIÉS** :

```
29 plans communs mono / 2 temoins  ->  plantage INCHANGE sur 28, ameliore sur 1
26 plans communs mono / 3 temoins  ->  INCHANGE sur 25
25 plans communs mono / 4 temoins  ->  INCHANGE sur 24
amorce de defaillance : mediane 6-7 couches, INCHANGEE dans les 80 cas sur 80
```

**À plan identique, la coupure ne change rien.** Elle n'agit que sur ce qui vient après elle, et
la défaillance commence dès la couche **7** (médiane) quand la coupure la moins profonde
possible est à 19.

🔴 **ET LE PIÈGE QUI A COÛTÉ TROIS RUNS** : le champ `critical_layer` de l'artefact rapporte la
marge la **pire**, donc la plus profonde — médiane **57**. En le lisant, on croit le problème
profond et une coupure à 38 bien placée. La **première** marge négative est à la couche **7** en
médiane sur les 8030 stratégies des graines 101 et 202 — et **6** sur les plans appariés
mono/mt2. ⚠️ Deux ensembles différents, deux chiffres justes : ne pas citer l'un pour l'autre.

🟢 **Garde-fou posé** : `multitemoin_peut_agir` lit l'amorce dans les artefacts déjà écrits et
refuse l'escalade quand aucune partition ne peut l'atteindre. ⚠️ Il ne dit **pas** que le
composant est infaisable — `r75x2` rend 251 déposables dès qu'on injecte des plans connus.

### 🔴 Trois affirmations que j'ai faites ce jour-là et qui étaient FAUSSES

| affirmation | ce qu'il en est |
|---|---|
| « les coupures font remonter l'amorce de 23 à 6 » | ❌ je comparais deux **populations** (3966 contre 4049 stratégies), pas les mêmes plans |
| « le multi-témoin entame le mur, 100 % → 56 % » | ❌ **une** stratégie sur 4049 ; le mono est un mur parfait, zéro stratégie sous 100 % |
| « la coupure doit tomber sur une frontière de bloc » | ❌ testé : l'écart vaut 1 à 3 couches et **change de signe** selon le nombre de témoins |

**Les trois sont tombées dès que j'ai apparié les plans au lieu de comparer des médianes de
population.** C'est la leçon de méthode de la journée.

### 🔴 Et la partition régulière n'est PAS un choix mesuré

`partition_temoins` la justifiait en citant *« étendue +14,4 % / +15,4 %, l'optimum est PLAT »*.
Cette étendue porte sur le **SEEL de partitions DÉJÀ DÉPOSABLES** — `classer_partitions.py:178`
écarte celles qui plantent **avant** de calculer la RMSE — et côté 75c l'artefact ne porte
**aucun champ de plantage**, sur un composant à 0 % de plantage. Requalifié le 2026-08-23 aux
quatre endroits qui l'invoquaient. 📏 Indice contraire : **le 99c qui réussit coupe à 0/22/72,
ce qui n'est pas régulier.**

---

## 00. 🟢🟢 LE 2026-08-22 A RENVERSÉ LA CONCLUSION DE §8.2ter — lis ceci d'abord

⚠️ **Les sections §8.2ter et §8.2quater plus bas portent un raisonnement PÉRIMÉ.** Elles
concluaient que *« la graine 77 est l'exception »* sur la foi de quatre graines. Trois mesures
de plus l'ont réfuté.

### Sept graines NUES sur `r75x2` à 2 nm, plage complète, ZÉRO surcharge

```
graine   strategies  deposables   meilleur SEEL     strats - depos
   42        1617          0           --                1617
   77        2231        547        0,5692 nm            1684   ✅
  101        1630          0           --                1630
  202        1646          0           --                1646
  303        1680          0           --                1680
  404        2016        372        0,5599 nm            1644   ✅
  505        1995        311        0,6112 nm            1684   ✅
```

🔑 **`p` n'est plus supposé, il est mesuré : 3 succès sur 7.** Et la 404 rend **0,5599 nm sans
aucune rampe** — c'est la demande de 👤 satisfaite : *que le code trouve 0,57 à 2 nm sans
savoir a priori qu'il faut des rampes.*

⚠️ **Formulation qui tient** : 0,5599 contre 0,5676 pour la voie avec rampes, soit −1,4 %,
**sous le bruit de 2,59 %**. C'est une **égalité**, jamais une supériorité. Et cela vaut sur
`r75x2` à 2 nm, rien d'autre (§8.2bis).

### Il faut DEUX `p`, et c'est ce qui dimensionne `K`

```
p(un DEPOSABLE quelconque)   = 3/7 ~ 0,43     K=3 -> 81 %   K=4 -> 89 %
p(le NIVEAU 0,57)            = 2/7 ~ 0,29     K=4 -> 74 %   K=6 -> 87 %
```

La 505 trouve du **fabricable**, pas du 0,57 : son 0,6112 est à +7,7 % du 0,5676, bien au-delà
du bruit. S'arrêter au premier succès peut donc coûter **9,2 %** d'étendue.

### 🔴 La fausse piste, tuée d'avance

On est tenté de voir un prédicteur dans le nombre de stratégies (2016 et 2231 chez celles qui
trouvent, 1617 à 1680 chez les autres). **C'est le même fait compté deux fois** : en
retranchant les déposables, la bande est continue — 1617, 1630, 1644, 1646, 1680, 1684, 1684 —
et les trois succès y sont **intercalés**. Il n'existe aucun signal avant le criblage.

### 📏 Le criblage de graines à budget réduit : FIABLE et NON RENTABLE

Proposition de 👤 : cribler beaucoup de graines à peu de tirages, puis élargir sur les bonnes.
Mesuré sur les six graines dont on connaît la réponse (`n_screen_runs` 50→12,
`robustness_num_runs` 300→75, étiquette `mcreduit4x`) :

```
6/6 classifications correctes -- zero faux positif, zero faux negatif
   (42, 77, 101, 202, 303, 404 -- la 505 n'a PAS ete criblee a budget reduit)
MAIS le run n'est que 1,63x plus rapide (25-27 min contre 44)

cribler 7 graines puis rejouer les 3 gagnantes :  321 min
tout jouer plein                               :  308 min     -> le criblage COUTE
```

🔑 La raison est structurelle : le partage **criblage 47 % / ELITE 53 %** (§3 point 5) plafonne
tout gain à ~2×. ⚠️ **Et le résultat du run bon marché n'est pas utilisable** : la 404 y rend
0,6026 au lieu de 0,5599, à **7 blocs au lieu de 10** — une autre lignée. Élargir les tirages
veut dire **relancer la graine**, pas renoter les survivantes du run bon marché : les bons
plans n'y ont jamais été produits.

### 🟢 Ce qui a été CONSTRUIT le 2026-08-22

| | |
|---|---|
| **`scripts/orchestre_multigraine.py`** | K graines dans un **budget de temps**, union en tourniquet, notation sur graine **disjointe**. 42 tests |
| **onglet « Multi-realisation »** dans le GUI STRAT | `certus/ui/certus_strat_multigraine_ui.py`. Il **pilote** le script, ne le réimplémente pas. 32 tests |
| **`scripts/batch_mc_reduit.sh`** | le test de criblage ci-dessus |
| 🔴 **`scripts/preflight.py` §2 mentait** | il lisait `.git/hooks/post-commit` en dur ; sous `core.hooksPath` il imprimait `[OK] post-commit is disabled` pendant que le commit **publiait**. Il demande maintenant `git rev-parse --git-path hooks`. Garde : `tests/unit/test_preflight_voit_le_hook.py` |
| test orphelin retiré | `test_docs_api_examples.py` lisait un document supprimé par `395a3c8` |

### 🔵 Ce qui reste ouvert au 2026-08-22 à 18:00

| | |
|---|---|
| **la validation de bout en bout de l'orchestrateur** | lancée à 17:33, encore dans sa notation finale. L'événement `resultat` n'a **jamais** été émis par un vrai run |
| **le plafond `--max-plans=200`** | écarte **483 plans sur 683**. Signalé, mais à revoir |
| **`r75x2-2nm` livrée, graine 202** | toujours non mesurée. Non urgente |
| ~~**l'anomalie plantage/bruit**~~ | 🟢 **EXPLIQUÉE le 2026-08-24** — c'est le seuil d'hystérésis du détecteur, qui suit le niveau de bruit. Voir §1ter |
| ~~**la RAM tourne à 2133 MHz**~~ | 🔴 **CLOS ET RÉFUTÉ le 2026-08-23 — voir §0000.** Le kit G.Skill a été retiré, le DOCP est actif à **3600 MHz** vérifié dans `Win32_PhysicalMemory`… et le run est **4,7 % PLUS LENT**, sur six blocs et deux graines. La conclusion *« le goulot est la bande passante mémoire »* était **fausse** : elle déduisait un goulot d'un plafond de CPU sans jamais faire varier la mémoire. ⚠️ Le **+29 %** de débit à deux runs concurrents, lui, reste mesuré et inexpliqué |

---

## 0. 🔴 TU ARRIVES SUR UNE MACHINE NEUVE ? COMMENCE ICI

👤 a basculé de machine le **2026-08-22 à 14h15**, en cours de campagne. Le dépôt porte tout
l'état ; **ce qui suit est ce qui ne le porte PAS.**

### 0.0 🔴🔴 OÙ CLONER — et pourquoi PAS dans Google Drive

👤 a demandé le 2026-08-22 : *« me mettre sur le répertoire Drive ? »* **Non.** Et la question
touche le **piège n° 1** du projet, celui que `CLAUDE.md` §4 décrit comme *« invisible »*.

📏 **Mesuré ce jour-là sur la machine d'origine, où DEUX clones du même dépôt coexistaient :**

```
C:\Users\...\Google Drive\...\CERTUS\1408    git · origin = nikonvr/CERTUS · 174 COMMITS DE RETARD
C:\certus                                    git · origin = nikonvr/CERTUS · a jour
```

**174 commits d'écart, et les deux ressemblent au projet.** C'est littéralement le scénario du
piège : *« tu modifies un dossier et tu en mesures un autre — tout ce que tu constateras sera
faux, sans le moindre message d'erreur. »*

🔴 **Et Drive n'est pas seulement risqué, il est INUTILISABLE — mesuré** : un simple
`du -sh .git` sur la copie Drive **dépasse deux minutes** et se fait tuer. Un dépôt git y fait
des milliers de petits fichiers que le client de synchronisation relit sans cesse. S'y ajoute
que Drive peut créer des **copies de conflit à l'intérieur de `.git`** — et un `.git` avec des
doublons est un dépôt corrompu.

📌 Le déménagement hors Google Drive a **déjà eu lieu une fois** dans ce projet, et c'est
pourquoi les temps absolus des vieilles campagnes ne valent plus rien.

### ✅ Ce qu'il faut faire sur la machine neuve

```bat
:: un chemin LOCAL, court, hors de tout dossier synchronise
git clone https://github.com/nikonvr/CERTUS.git C:\certus
cd C:\certus
git checkout refactor-corridors-mixins
```

⚠️ **`refactor-corridors-mixins` est la branche de travail**, très en avance sur `main` — dont le
dernier commit date du **2026-04-27**. Rester sur `main` donnerait l'impression d'un projet figé
depuis des mois.

🔑 **Et le premier contrôle du §0.4 existe précisément pour attraper cette erreur** : il imprime
le chemin d'où `certus` est importé. **S'il affiche un chemin contenant `Google Drive`, ou un
chemin qui n'est pas celui que tu édites — ARRÊTE-TOI.**

### 0.1 ⚡ La commande unique pour reprendre la campagne

```bat
bash scripts\batch_r75x2_reprenable.sh
```

🔑 **Il SAUTE toute mesure dont l'artefact existe déjà avec `verdict = OK`.** On peut donc le
relancer sans réfléchir : il reprend où la campagne s'est arrêtée. Au moment de la bascule :

| mesure | état à la bascule du 2026-08-22 à 14h15 |
|---|---|
| `r75x2` nu, graine 101 | ✅ **faite** — 1630 stratégies, **0 déposable**, 91 min |
| `r75x2` nu, graine 202 | ✅ **faite** — 1646 stratégies, **0 déposable**, 97 min |
| `r75x2-2nm` livrée, graine 101 | ✅ **faite** — 1840 stratégies, **216 déposables**, meilleur **SEEL 0,5707 nm** au bloc 10, 115 min. 🔑 Confirme au bit ce que le journal d'hier donnait, mais **avec un artefact** : §7bis de [`CHANTIER_PREDICTIBILITE.md`](CHANTIER_PREDICTIBILITE.md) est satisfait |
| `r75x2-2nm` livrée, graine 202 | ⏳ **la seule qui reste**, ~95 min |

🔑 **Donc une seule mesure reste, et le script la trouvera tout seul.** Les trois autres portent
un artefact `verdict = OK` et seront sautées : `bash scripts/batch_r75x2_reprenable.sh` reprend
directement `livree_s202`.

📌 **Et depuis le 2026-08-22 à 18:00, il y a mieux que ce batch pour chercher** — voir §00 :

```bat
python scripts\orchestre_multigraine.py r75x2 --budget nuit --seel-cible 0.57 --objectif meilleur
```

Il rejoue la recherche sur K réalisations dans un **budget de temps**, saute ce qui porte déjà
un artefact, unit les plans en tourniquet et note sur une graine **disjointe**. Le même
mécanisme est dans le GUI STRAT, onglet **« Multi-realisation »**.

⚠️ **Et elle n'est pas urgente** : elle consolide le 0,5676 avec une quatrième réalisation, elle
ne peut pas le remettre en cause — trois graines convergent déjà à **0,55 %** d'étendue, sous le
bruit de 2,59 %.

🔑 **CE QUI EST URGENT, c'est l'action de §8.2quater** : `r75x2` NU aux graines **303, 404, 505**,
qui dimensionne `K` pour le multiseed de génération. C'est la seule voie qui réponde à la demande
de 👤 — *que le code trouve 0,57 à 2 nm sans savoir a priori qu'il faut des rampes*. ~91 min par
graine, et **une seule suffit pour un signal** : si elle trouve, c'est un second succès
indépendant et le mode se justifie.

### 0.2 🔴 CE QUI NE SUIT PAS LE DÉPÔT — quatre pièges, et un cinquième résolu

| # | ce qui ne traverse pas | ce qu'il faut faire |
|---|---|---|
| 1 | **le hook `post-commit`** — `.git/hooks/` n'est pas versionné | 🟢 **RÉSOLU le 2026-08-22.** Le hook vit désormais dans **`.githooks/post-commit`**, qui EST versionné. Une commande l'arme : `git config core.hooksPath .githooks`. ⚠️ L'armement reste **délibéré** — `core.hooksPath` est une config **locale**, donc un clone n'arme rien tout seul, et c'est voulu : **committer, c'est publier** sur un dépôt public |
| 2 | **le chemin de l'interpréteur** | l'ancienne machine avait `C:\envs\certus\Scripts\python.exe`, **pas** `.venv`. Le script accepte une surcharge : `CERTUS_PY=... bash scripts/batch_r75x2_reprenable.sh` |
| 3 | **le cache numba est FROID** | la **première** passe de `pytest tests/oracle/ tests/unit/` rendra **3 échecs FAUX** (`test_phase2_gradient_analytic_vs_fd` et les deux `TestIRGlobalModelStrategy`). Cause dans numba, pas dans le dépôt — voir `CLAUDE.md` §2. **Relance une seconde fois avant de signaler quoi que ce soit** |
| 4 | **le cache de profils de fente est froid** | la Phase A du premier run prendra ~30 min au lieu de ~10. Ce n'est pas une régression |
| 5 | 🔴 **les durées mesurées ne valent que sur leur machine** | et elles **diffèrent selon la famille de run** : un `r75x2` **nu** prend **91 à 97 min**, un `r75x2-2nm` **livré** prend **~115 min** — il porte plus de survivants au criblage. Repère : i5-8250U, 8 threads. Sur une machine plus puissante ce sera moins, mais **ne baisse PAS `CERTUS_BENCH_TIMEOUT_S` pour autant** |

### 0.2bis 🔑 CE QUE LA MACHINE PLUS PUISSANTE VA — ET NE VA PAS — ACCÉLÉRER

Vérifié dans le code, pas supposé :

| étage | comportement sur une machine plus large |
|---|---|
| **notation de robustesse** | 🟢 **s'adapte** — `max_workers = max(1, cpu_count() // 2)` (`certus_strat_robustness.py:1925`). 8 threads → 4 workers ; 32 threads → 16 |
| **boucle des nombres de blocs** | 🔴 **reste à 1, par conception.** `certus_strat_workers.py:1452` porte `max_workers = 1` avec le commentaire *« FIX: Force max_workers=1 to prevent Numba CPU oversubscription and deadlocks »*. **Ne le remonte pas** sans comprendre ce qu'il évitait |
| **noyaux numba** | 🟢 `prange` élargit avec les cœurs, à l'intérieur de chaque évaluation |

⚠️ **Donc n'attends PAS un gain linéaire en cœurs.** Le facteur viendra de trois sources
inégales — plus de workers de notation, un cœur plus rapide, un `prange` plus large — et une
partie du run reste sérialisée par choix.

🔑 **Et la conséquence pratique : MESURE la durée d'un run avant d'annoncer un ETA.** Les deux
repères d'ici, sur i5-8250U 8 threads : **91 à 97 min** pour un `r75x2` **nu**, **~115 min**
pour un `r75x2-2nm` **livré** — l'écart vient du nombre de survivants au criblage, pas de la
machine. Le premier run sur la machine neuve donne les nouveaux repères ; tout ce qui est
écrit ailleurs dans ce dossier porte les anciens.

📏 Et la cadence, si tu veux estimer en cours de route : **~9 min par nombre de blocs** sur
les blocs 15 à 9, puis une queue qui **accélère** — 8 min au bloc 8, 5 min au bloc 4, 3 min
au bloc 2, plus ~4 min d'ablation et de consensus final. La queue entière vaut **~51 min**.
⚠️ Extrapoler la cadence des gros blocs sur toute la queue donne un ETA **trop optimiste** —
je l'ai fait, et je me suis trompé de 17 minutes.

### 0.3 🔴 LE PIÈGE QUI A DÉTRUIT QUATRE MESURES, ET IL EST DANS LE PLAFOND

📏 Le 2026-08-22, `CERTUS_BENCH_TIMEOUT_S=5400` a coupé **quatre mesures de 91 minutes** à
**98,9 %** d'avancement. `wait_for` rend alors `None`, ce qui **ressemble à un résultat**.

```
empreinte a chercher dans un journal :  « WAIT_TIMEOUT=5400 s — aucune emission recue »
et le signe qui ne trompe pas : plusieurs mesures qui durent EXACTEMENT le plafond
```

🔑 **La règle est `max(5400, 4 × durée attendue)`**, jamais un nombre recopié. Le script porte
38400 s. **Un plafond trop grand ne coûte rien ; un plafond trop petit détruit la mesure à la
dernière minute** — donc en cas de doute sur une machine inconnue, on ne le baisse pas.

### 0.4 Les contrôles avant de toucher à quoi que ce soit

🔑 **Le plus simple est `preflight.py`, qui fait les deux premiers et le NOUVEAU contrôle
`2bis` :**

```bat
git fetch origin
C:\envs\certus\Scripts\python.exe scripts\preflight.py
```

Le contrôle **2bis** répond à la seule question qui fait perdre du travail : *y a-t-il ici des
commits que le distant n'a pas ?* Il est vrai **quel que soit** l'état du hook — c'est ce qui le
rend utile, parce que l'absence de hook est **silencieuse**.

```bat
C:\envs\certus\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
dir .git\hooks\post-commit*
C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
C:\envs\certus\Scripts\python.exe -m ruff check .
```

Attendus : le chemin **dans l'arbre que tu édites** · l'état du hook **connu** (piège 1) ·
`2800 passed, 5 skipped` à la **seconde** passe (piège 3) · `All checks passed!`

Et les deux contrôles de cohérence documentaire. ⚠️ **L'attendu n'est plus « zéro »** : depuis
le 2026-08-23 `coherence_md.py` rend **1 point, et c'est un faux positif instruit** — voir la
fin du §0000. Un **second** point serait neuf.

```bat
C:\envs\certus\Scripts\python.exe scripts\coherence_md.py
C:\envs\certus\Scripts\python.exe scripts\check_claude_md.py
```

---

## 0bis. 🔒 CLÔTURE DE LA JOURNÉE DU 2026-08-21

👤 a arrêté la campagne après le run à la graine 101. **Rien ne tourne, rien n'est en attente.**

### Ce qui est ACQUIS, et mesuré

```
r75x2 a 2 nm, config livree, plage COMPLETE, ZERO surcharge
  graine  42 (a choisi les rampes)  ->  SEEL 0,5676 nm   197 deposables / 1810
  graine  77 (source des rampes)    ->  SEEL 0,5692 nm   547 deposables / 2231
  graine 101 (NAIVE)                ->  SEEL 0,5707 nm   (bloc 10)

etendue sur trois graines : 0,55 %   face a un bruit de 2,59 % sur une DIFFERENCE de SEEL
avant la livraison        : 0 deposable sur 1617, 100 % de plantage
```

🔑 **La malédiction du vainqueur est bornée à +0,55 %**, là où le canal valait +12,9 % au 15/08.
C'était la seule réserve sérieuse sur le chiffre, et la graine 101 — qui n'a pas participé au
choix des rampes — la lève.

### Ce qui reste OUVERT, et ce qui l'a été laissé délibérément

| | |
|---|---|
| **graine 202 sur la config livrée** | non mesurée — arrêt demandé. Trois graines valent mieux que deux, quatre auraient valu mieux que trois |
| ✅ **`r75x2` NU aux graines 101 et 202** | **MESURÉES le 2026-08-22 : 0 déposable chacune.** Trois graines nues sur quatre rendent zéro — la **77 est l'exception**. La règle écrite d'avance a tranché sa troisième branche. Détail en §33 de [`PLAN_PRODUCTION_2026-08-20.md`](PLAN_PRODUCTION_2026-08-20.md) |
| **un second composant** | 🔒 écarté par 👤 — voir §8.2bis, qui dit ce que cela interdit d'affirmer |
| ~~**l'anomalie plantage/bruit**~~ | 8,72 contre 1 dans le mauvais sens. N'a jamais menacé la livraison (la porte prend le maximum, donc conservateur). 🟢 **Le mode d'échec est COMPRIS depuis le 2026-08-24** : le seuil d'hystérésis du détecteur suit le niveau de bruit — voir §1ter |
| ~~**les rampes vivent dans `reports/`**~~ | ✅ **FAIT, et depuis plus longtemps que ce tableau ne le croyait** — commit `b13694b` *« les rampes sortent de reports/ »*. `injected_strategies` pointe sur `example/example_strat/rampes_r75x2-2nm.json`, **suivi par git**. Constaté le 2026-08-24. ⚠️ La configuration cite encore `reports/…` dans son champ `_reproduit`, et **c'est légitime** : une note de provenance n'est pas une dépendance |

### 🟢 Ce qui a été CONSTRUIT aujourd'hui

| | |
|---|---|
| **`scripts/generer_rampes.py`** | la méthode qui a livré le résultat, devenue **une commande**. 33 tests. 10 rampes sur **7 structures de blocs**, contre 12 quasi-doublons assemblés à la main |
| **la couverture en λ** | forcer une λ admissible absente ; mécanisme mesuré (601 → 901 groupements, 0 infaisable aux blocs 13-15), **routée**, inerte par défaut, 36 tests. 🔴 **Elle n'est pas le levier de l'autonomie** — la DP ne produit rien sous 11 blocs |
| **les instruments** | 66 scripts protégés du cp1252 **+ garde-fou**, l'artefact écrit **avant** la synthèse, les compteurs de couverture sur un canal **lu** |
| **`scripts/probe_plantage_vs_sigma.py`** | le test du Piège 1, enfin fait |

### 🔴 Ce qui a été RÉFUTÉ ou CORRIGÉ — la partie la plus utile

Neuf affirmations retirées en une journée, dont **sept étaient les miennes** :

| affirmation | verdict |
|---|---|
| « ELITE ne compose jamais deux mouvements » | ❌ elle en compose deux **entre rondes** ; la gagnante est à 1 pas de λ + 1 pas de frontière |
| « l'inversion crash/bruit est du bruit de comptage » | ❌ **532 contre 61** — systématique |
| « la contrainte ne porte qu'une valeur » | ❌ 38 valeurs, mais aux blocs 10-15, **disjoints** des déposables |
| « la DP est vide aux blocs 9-10 » | ❌ trop étroit — **vide à 10 et en dessous** |
| « les 547 déposables de la graine 77 = une lignée » | ❌ **217 jeux de λ** ; le 1 venait d'un artefact sans plans |
| « restreindre la plage ne perd rien » | ❌ elle **vide la DP** |
| `use_margin_ranking` comme levier | ❌ marges **1 500×** hors du domaine validé |
| le garde `halving` comme coupable | ❌ même taux par ronde dans le run qui **réussit** |
| `SMART_MERGE` comme cible | ❌ **zéro `SMART_MERGE`** chez la graine qui réussit |

🔑 **Et le diagnostic qui remplace tout cela, appuyé sur une géométrie mesurée** : aux nombres de
blocs qui décident, la contrainte est **binaire** — 100 % de plantage aux trois niveaux de bruit,
ou déposable, rien entre les deux. **Le paysage n'est pas une colline sans pente, c'est une
falaise.** ELITE est un grimpeur : 0 candidate retenue sur 2472 sans rampes, 388 sur 6343 avec.
Les rampes n'apportent pas de la diversité, elles apportent de la **faisabilité** — elles
atterrissent de l'autre côté.

Cela **ferme toute la classe des correctifs de classement**, pour une raison géométrique et non
par essais successifs. Et il ne reste que trois voies, dont une seule est générale : **changer de
réalisation**, c'est-à-dire le multiseed de génération — union sur K graines, faisabilité exigée
sur **toutes**.

---

## 0ter. ⚡ LE RÉSULTAT ACQUIS, ET SA CONDITION

👤 voulait que le code de **production** trouve sur `r75x2` à **2 nm** des SEEL « de l'ordre de
0,57 ou moins ». À la graine 42 seule, il rendait **0 déposable sur 1617**, toutes à 100 % de
plantage.

### 🟢🟢 C'EST FAIT — test d'acceptation passé le 2026-08-21 à 12:58

```
composant  example/example_strat/JSON-strat-random75-x2-fabricable-2nm.json
fente 2 nm · graine 42 · mode deep · PLAGE DE BLOCS COMPLETE
config.overrides_tag = None          <- la preuve du ZERO surcharge

197 deposables sur 1810        (avant : 0 sur 1617)

 rg blocs   score    SEEL     crash   origine
  1     9  0,08053  0,5676   1,67 %   ELITE   <- id 900000044
  2     9  0,08113  0,5697   1,33 %   ELITE
  4     9  0,08161  0,5714   1,00 %   ELITE
  6     8  0,08166  0,5715   1,00 %   ELITE

deposables par nombre de blocs : {5: 13, 6: 46, 7: 46, 8: 49, 9: 43}
artefact : reports/blocs_vs_plantage_r75x2-2nm_deep_s042.json
```

**La gagnante, en clair** — et le bloc qui manquait y est :

```
 0-8  @ 450 nm       33-52 @ 685 nm   <- LA lambda absente des 1617 natives
 8-25 @ 610 nm       52-57 @ 647 nm
25-33 @ 616 nm       57-63 @ 700 nm · 63-65 @ 511 · 65-68 @ 687 · 68-75 @ 704
```

🔑 **LA CONDITION EST DANS LA MÊME PHRASE QUE LE CHIFFRE, ET ELLE Y RESTE.** Ce résultat vient
**avec les rampes de lancement** déclarées dans la configuration du composant
(`injected_strategies`). C'est bien de la production — la configuration est livrée, le run n'a
aucune surcharge — mais **ce n'est pas une découverte autonome** : l'information des rampes
descend de la graine 77. Qui citera « 0,5676 nm » sans cette condition dira faux.

⚠️ L'écart à la cible vaut 0,3 % et le bruit sur une différence de SEEL vaut 2,59 % : c'est une
**égalité**, jamais une supériorité.

### 🟠 IL EXISTE DÉJÀ UNE VOIE AUTONOME À 2 nm, ET ELLE COÛTE +18 %

🔴 **Cette ligne avait disparu du document le 2026-08-21, et c'est une régression que j'ai
introduite en réécrivant §0.** Elle est mesurée depuis le 2026-08-20 et vit dans
[`CHANTIER_RATE.md`](CHANTIER_RATE.md) §3bis :

```
2,0 nm  deep     pur optique     0 deposable  ·  100 % de plantage
2,0 nm  premium  queue Rate      3 deposables ·  SEEL 0,6717 · 2,67 %
2,0 nm  deep     queue Rate      3 deposables ·  SEEL 0,6859 · 2,67 %
2,0 nm  fast     queue Rate      2 deposables ·  SEEL 0,7014 · 4,00 %
```

**La queue Rate trouve seule, sans rampe.** Elle coûte **+18 %** de SEEL par rapport au 0,5676
des rampes, et elle rend **3** stratégies au lieu de 197 — mais elle n'a besoin d'aucune
information venue d'une autre graine.

🔑 **Donc la bonne formulation de ce qui manque n'est PAS « aucune voie autonome »** — elle
existe. C'est : *aucune voie autonome n'atteint le niveau de 0,57 ; la seule qui trouve
sans rampe plafonne à 0,67-0,69.*

⚠️ Et le pur optique à la résolution **native** de ce fichier (1 nm) rend **277 déposables à
SEEL 0,6248** : c'est de là que vient le `-fabricable` de son nom. Tout ce qui précède décrit
donc le composant tourné à **la moitié de la résolution pour laquelle il a été conçu**.

### 🔑 Le mécanisme, mesuré et non supposé

Les parents qu'ELITE reçoit au bloc 9 portent les bonnes λ et **plantent tous à 100 %**. La
gagnante est un **descendant**, à **deux mouvements** de sa rampe :

```
bloc 2 :  rampe (25, 33, 615)  ->  gagnante (25, 33, 616)     UN pas de λ
bloc 3 :  rampe (33, 53, 685)  ->  gagnante (33, 52, 685)     UN pas de frontiere

barre de selection : ronde 1  0,268856  ->  ronde 2  0,077943    (facteur 3,4)
```

Les rampes apportent les λ ; **ELITE compose deux pas à travers deux rondes**. ⚠️ Cela corrige
une phrase de §24.3 du plan qui disait qu'ELITE « ne compose jamais deux mouvements » — faux.
Ce qui ferme la voie native n'est pas l'impossibilité de composer, c'est que **chaque pas
intermédiaire plante**, donc rien n'est retenu pour bâtir dessus.

---

## 1. ✅ LA MALÉDICTION DU VAINQUEUR EST BORNÉE — action close le 2026-08-21

Cette section demandait de rejouer la configuration livrée à une graine **qui n'a pas servi à
choisir les rampes**. C'est fait, et le résultat est bon :

```
graine  42 (a CHOISI les rampes)  ->  SEEL 0,5676 nm
graine 101 (NAIVE)                ->  SEEL 0,5707 nm   ecart +0,55 %
```

Le canal de biais valait **+12,9 %** au 15/08 ; mesuré ici, il vaut **+0,55 %**, soit **cinq fois
sous** le bruit de 2,59 % qui pèse sur une différence de SEEL. **Le 0,5676 n'est pas gonflé par la
sélection.**

⚠️ **Ce chiffre vient d'un JOURNAL, pas d'un artefact** : le run a été arrêté avant d'écrire le
sien. C'est pourquoi la campagne en cours le **refait** (`livree_s101`) — un chiffre publié doit
être re-dérivable depuis un artefact (§7bis de [`CHANTIER_PREDICTIBILITE.md`](CHANTIER_PREDICTIBILITE.md)).

## 1bis. 🔵 LA VOIE AUTONOME — où elle en est

La **couverture en λ** est le premier levier qui ne cherche pas *autour* de ce qui existe : elle
**force** une λ admissible absente des `top_k` groupements en restreignant une couche de la
`cost_map` à cette seule λ, et laisse la DP **re-optimiser le reste du plan**. C'est la
différence avec une mutation ELITE, qui casse la cohérence du plan.

📌 Écrite, inerte par défaut (`enable_wl_coverage`), **routée** depuis un fichier de
configuration, gardée par **36 tests**. §25 de [`CLAUDE.md`](../CLAUDE.md) du plan porte le détail, dont le défaut de plan
d'identifiants qu'elle a fait trouver (offsets 0/100/200 saturés à `top_k = 100` en DEEP).

### 🟢 LE MÉCANISME EST CONFIRMÉ EN PRODUCTION — mesuré le 2026-08-21, run `couvfull`

Plage de blocs **complète**, composant `r75x2` (le fichier de base, **sans rampes**),
`enable_wl_coverage=1` pour seule surcharge. Le contrôle est le run à plage complète sans
couverture : **0 déposable sur 1617**.

```
bloc  15  140 λ deja employees,  763 absentes -> 300 ajoutees,   0 infaisable
bloc  14  109 λ deja employees,  794 absentes -> 300 ajoutees,   0 infaisable
bloc  13   66 λ deja employees,  837 absentes -> 300 ajoutees,   0 infaisable
bloc  12   59 λ deja employees,  844 absentes -> 270 ajoutees,  30 infaisables

bloc 15 : la population passe de 601 a 901 groupements  (+300, exactement les ajouts comptes)
```

| ce qui est établi | |
|---|---|
| **forcer une λ est faisable** | 0 infaisable sur 900 tentatives aux blocs 15, 14, 13 |
| **la passe atteint le calcul** | 601 → 901 groupements, soit **exactement** les 300 ajouts comptés |
| **ses produits sont compétitifs** | au bloc 14, `couvfull` rend **0,29479** contre **0,29482** pour le run d'acceptation : une stratégie **issue de la couverture** traverse le criblage et sort première de son nombre de blocs |
| **le coût est mesuré** | 300 appels DP en ~1 min 42 par nombre de blocs |

🔑 **Et une tendance qui joue en notre faveur** : le nombre de λ que le k-meilleurs emploie
s'effondre quand les blocs diminuent — 140, 109, 66, 59 — donc l'élargissement relatif **grandit**
en approchant du bloc 9, celui où vit la famille à SEEL 0,5676. ⚠️ En contrepartie les premières
infaisabilités apparaissent au bloc 12 : moins de blocs, plus de couches par bloc, contrainte
plus dure. Ce n'est pas un défaut de la passe, c'est la géométrie du problème.

🔴 **CE QUI N'EST PAS RÉPONDU.** Faire entrer une λ dans la population et produire une stratégie
**déposable** sont deux événements, et le second ne découle pas du premier. Les blocs 15 à 12
restent tous à **100 % de plantage**. Le nombre de blocs qui décide est **9**.

### ⚠️ Le premier essai a été perdu, et pour trois défauts d'instrument

| # | défaut | ce qu'il a coûté |
|---|---|---|
| 1 | le logger `ThinFilm` du mineur est **MUET** — sa ligne `info` inconditionnelle apparaît **zéro fois** dans les journaux, alors que le logger `W{n_blk}` du worker passe | impossible de distinguer « la passe n'a pas tourné » de « chaque λ forcée était infaisable ». Piège 6 |
| 2 | **troisième plantage cp1252**, dans `synthese()` | l'artefact d'un run de 50 min **jamais écrit** |
| 3 | les runs à **plage restreinte** minent 1 à 2 stratégies par nombre de blocs, contre 601 à plage complète | le contrôle négatif `ctrl911sansinj` est bien plus mince que ses « 63 stratégies » |

🟢 **Les trois sont réparés** (`8118721`) : 66 scripts protégés plus un garde-fou qui refuse tout
nouveau cas, l'artefact s'écrit **avant** la synthèse, et les compteurs de couverture remontent
par le logger du worker — avec un `logger.error` si le drapeau est armé et les compteurs vides.

> **Un instrument dont la sortie n'atteint pas le résultat n'est pas un instrument.**

---

## 1ter. 🟢 L'ANOMALIE EST EXPLIQUÉE le 2026-08-24 — c'est le détecteur, pas l'empilement

> **Ouverte le 2026-08-21, close le 2026-08-24.** Le taux de plantage décroît quand le bruit
> croît parce que le seuil d'hystérésis du détecteur de points tournants **suit le niveau de
> bruit** : plus de bruit → détecteur plus conservateur → moins de faux points tournants.
> Démontré en faisant varier le facteur, qui **inverse** le sens. Détail à la fin de la section.
> ⚠️ Ce qui suit décrit l'anomalie telle qu'elle a été trouvée, et reste vrai.

```
sur les 197 deposables   :  125 DECROISSANTES ·  61 croissantes ·   11 plates
sur les 1810 strategies  :  532 DECROISSANTES ·  61 croissantes · 1217 plates
```

**8,7 contre 1 dans le mauvais sens, donc systématique.** ⚠️ J'avais d'abord écarté cela par un
argument de Poisson (« 5 plantages contre 1 et 1 ») — **retiré** : c'était substituer un
raisonnement sur le bruit au test que le Piège 1 prescrit.

**Ce que ça change** : la porte prend le **maximum** des trois niveaux, donc le `1,67 %` publié
vient du bruit **le plus faible** — lecture conservatrice, le verdict « déposable » n'est pas
menacé. ~~**Ce que ça ne change pas** : on ne comprend plus le mode d'échec, et cela touche
toute mesure de plantage du projet, murs à 100 % compris. Le balayage σ→0 reste à faire.~~
🟢 **Le mode d'échec est compris depuis le 2026-08-24** — et par un balayage du **facteur
d'hystérésis**, pas de σ. Voir la fin de cette section.

### 📏 L'ANOMALIE EST BIEN PLUS NETTE QUE « 8,7 CONTRE 1 » — mesuré le 2026-08-24

Sur la graine **404** (`blocs_vs_plantage_r75x2_deep_s404.json`), en classant par le niveau de
plantage **de départ** au lieu de tout mélanger :

```
plantage de depart |   croit  DECROIT
             0-5 % |     402       86
            5-25 % |       0        1
           25-50 % |       0       28
           50-75 % |       0      623
           75-95 % |       0      337
          95-100 % |       0      502
```

🔑 **Au-dessus de 5 % de plantage de départ : 1491 décroissantes, ZÉRO croissante.** Le rapport
global de 3,92 masquait une séparation **parfaite**. Toutes les croissantes sont sous 5 %.

🔴 **Et l'explication paresseuse est RÉFUTÉE.** On pense d'abord à un effet de plafond — une
stratégie déjà à 90 % ne peut que descendre. Non : dans la bande **50-75 %**, où il y a toute la
place de monter, **623 sur 623 descendent**. Ce n'est pas de la régression vers la moyenne.

### ⏳ LE TEST QUI TRANCHE TOURNE — `tp_hysteresis_factor = 0`, lancé le 2026-08-24 à 15:20

```bat
bash scripts\enchainer_hysteresis.sh hysteresis_2026-08-24 404
```

🔑 **Le mécanisme candidat n'est pas supposé, il est DANS LE CODE** — `certus_strat_robustness.py:2489-2495` :

```
tp_hysteresis = tp_hysteresis_factor * A * noise_val
```

Le seuil du détecteur de points tournants **suit le niveau de bruit**. Plus de bruit → seuil plus
grand → détecteur plus **conservateur** → moins de faux points tournants → moins de
`TP_MISCOUNT`, qui pèse **79 %** des plantages. Cela produirait exactement le sens observé, et
seulement au-dessus du plancher — ce que le tableau ci-dessus montre.

📌 **Un seul point au lieu du balayage à trois** que demandait l'action 6 : le garde
`if tp_hysteresis_factor > 0.0` coupe **toute** la dépendance au bruit, donc l'extrême répond
dans les deux sens pour **36 min** au lieu de 1 h 50.

```
rapport ~ 1,0   ->  l'hysteresis EXPLIQUE l'anomalie, le §1ter est clos
rapport ~ 3,9   ->  elle n'y est pour RIEN, chercher ailleurs
entre les deux  ->  elle en explique une PART, et la seulement le balayage complet se justifie
```

⚠️ **Risque assumé** : sans hystérésis, le détecteur peut faire **saturer** les taux à 100 % et
la sonde n'aurait plus rien à classer. Ce serait un résultat aussi — il voudrait dire que
l'hystérésis ne biaise pas le détecteur, elle le rend **utilisable**. Le journal le dira par
l'explosion de la ligne « murs à 100 % écartés ».

### 🔴🔴 RÉSULTAT — c'est la branche « saturation », et elle dit plus que la question posée

**Mesuré le 2026-08-24 à 16:00.** `reports/blocs_vs_plantage_r75x2_deep_s404_hyst0.json` :

```
                    n_strats   murs a 100 %   deposables
 TEMOIN  hyst=1,66     4454         2475          403
 ESSAI   hyst=0        2929         2929            0
```

🔑 **À hystérésis nulle, les 2929 stratégies sont des murs à 100 %. AUCUNE n'est déposable.**

> **`tp_hysteresis_factor` n'est pas un réglage, c'est une pièce porteuse.** La notion même de
> « déposable » en dépend : 403 → 0. On croyait tester un biais du détecteur ; on a découvert
> qu'il ne fonctionne pas du tout sans lui.

🔵 **La question du §1ter reste ouverte** — il ne reste rien à classer, donc aucun rapport
DÉCROISSANT/croissant n'est calculable. C'était le risque écrit d'avance, et c'est la branche
qui a tiré.

🔑 **Mais le mécanisme candidat en sort RENFORCÉ, et par une chaîne monotone maintenant visible :**

```
hysteresis = 0     ->  100 % de plantage partout,  0 deposable
hysteresis = 1,66  ->  403 deposables

donc  plantage DECROIT quand l'hysteresis CROIT.
et    hysteresis  CROIT avec le bruit  (`certus_strat_robustness.py:2493`)
donc  plantage DECROIT quand le bruit CROIT      <- exactement l'anomalie observee
```

⚠️ **Deux points ne font pas une courbe, et le mécanisme n'est établi qu'en SENS, pas en
ampleur.** ⚠️ Et les populations diffèrent (4454 contre 2929) : quand tout plante, le criblage
ne retient pas les mêmes effectifs, donc ce n'est **pas** une comparaison appariée.

📌 **La suite, telle que la règle écrite d'avance la prescrit** : refaire à
`tp_hysteresis_factor = 0.5`, puis `1.0` si nécessaire. Un point intermédiaire où il reste des
déposables rendrait un rapport calculable **et** un troisième point de la courbe.

```bat
bash scripts\enchainer_hysteresis.sh hysteresis05_2026-08-24 404 0.5
```

🔑 **Le facteur est le troisième argument et il entre dans l'étiquette de l'artefact.** La
première version le codait en dur : il aurait fallu éditer le script avant chaque mesure — une
occasion de se tromper à chaque fois, et deux facteurs différents auraient rendu deux artefacts
au **même nom**.

#### ⏳ LANCÉE à 15:59, et voici la règle de lecture, ÉCRITE AVANT LE RÉSULTAT

| ce que rend `hyst=0.5` | ce qu'on en conclut |
|---|---|
| **des déposables et un rapport calculable** | 🟢 troisième point de la courbe. Si le rapport DÉCROISSANT/croissant **baisse** franchement sous les 3,92 du témoin, l'ampleur de l'anomalie suit le facteur et le §1ter est **expliqué**. S'il reste à ~3,9, l'hystérésis fixe le **niveau** de plantage sans porter la **direction** — et il faut chercher le sens ailleurs |
| **encore 100 % de murs, 0 déposable** | 🔵 le seuil d'utilisabilité est entre **0,5 et 1,66**. Refaire à `1.0`. On aura appris que la marge est étroite, ce qui est en soi un fait sur la robustesse du détecteur |

🔴 **Ce qu'aucun de ces résultats ne dira** : si le canal `TP_MISCOUNT` est bien celui qui
transporte l'effet. Les 79 % viennent d'un comptage antérieur, sur une autre population.

#### 🟢🟢 RÉSULTAT — le §1ter EST EXPLIQUÉ. L'anomalie ne faiblit pas, elle S'INVERSE

**Mesuré le 2026-08-24 à 16:42.** La règle ci-dessus prévoyait « si le rapport baisse
franchement, le §1ter est expliqué ». Il ne baisse pas : **il change de signe.**

```
 facteur    n_strats   murs 100%   deposables    DECROISSANT / croissant
   0          2929        2929          0        -- (rien a classer)
   0,5        4820        4176        642              2 / 642   =  0,003
   1,66       4454        2475        403           1577 / 402   =  3,92
```

🔑 **À 0,5 le sens est le sens PHYSIQUE** — plus de bruit, plus de plantage, 642 contre 2. À
1,66 il est inversé, 1577 contre 402. **C'est donc bien `tp_hysteresis_factor` qui porte la
direction**, et le mécanisme du code (`:2493`, le seuil suit `noise_val`) rend compte de
l'anomalie du §1ter dans son sens comme dans son existence.

> Le taux de plantage ne décroît pas parce que l'empilement résiste mieux au bruit. Il décroît
> parce que **le détecteur devient plus conservateur quand le bruit monte**, et qu'il rate alors
> moins de points tournants qu'il n'en fabriquait.

### 🔴 ET NON, ON N'A PAS TROUVÉ « PLUS DE DÉPOSABLES »

Le compte est **non monotone** — 0, puis **642**, puis 403 — et 642 à `0,5` est supérieur aux
403 du défaut. La tentation est de conclure qu'on tient un réglage rentable. **Non.**

🔒 **`tp_hysteresis_factor` est une SPÉCIFICATION MATÉRIELLE, pas un levier de solveur.**
`certus/physics/certus_strat_machine.py:16` — `OMS5100_DEFAULT_5_SIGMA_FACTOR = 1.66`, dans un
fichier dont l'en-tête dit *« Centralized hardware specifications […] Bühler Leybold Optics
OMS 5100 »*. Le baisser ne rend pas le procédé meilleur : cela **modélise un instrument qui
n'existe pas**. Les 642 déposables décrivent une machine que 👤 ne possède pas.

📌 **Ce que ça change en pratique : rien sur les chiffres publiés.** La porte prend toujours le
**maximum** des trois niveaux, donc la lecture reste conservatrice. Ce qui change, c'est qu'on
**comprend** enfin le mode d'échec — il était ouvert depuis le 2026-08-21.

⚠️ **Ce qui reste non prouvé, et qui était écrit d'avance** : que le canal soit précisément
`TP_MISCOUNT`. Les 79 % viennent d'un comptage antérieur sur une autre population, et je ne les
recycle pas comme une preuve.

⚠️ **Et les populations ne sont pas appariées** — 4820, 4454, 2929 stratégies minées. Quand le
détecteur change, le criblage ne retient pas les mêmes effectifs. Les rapports se comparent, les
comptes absolus beaucoup moins.

🟢 **Un acquis secondaire, sur la robustesse** : la falaise est entre **0 et 0,5**, pas près du
défaut. À 0,5 le détecteur est déjà pleinement fonctionnel. Le 1,66 livré n'est **pas** posé au
bord d'un précipice — ce n'était pas su.

---

## 2. ✅ CE QUI EST EN PRODUCTION DEPUIS CETTE NUIT

| | commit |
|---|---|
| **`screen_seed_list`** — K criblages, **union par signature de plan**, au point de divergence des graines | `44f352d` |
| **`injected_strategies`** — verser des plans donnés dans la population, par le canal de l'héritage | `43f7144` |
| **`[ELITE-WL]`** — la λ **et** la bande de plantage des candidates rejetées | `5105fc8` |
| **`[GATE]`** — combien de fois la borne de confiance change le verdict | `0117445` |
| surcharges génériques de la sonde, **étiquette obligatoire** | `1f39cdd` |
| `scripts/lire_multiseed.py` — et il **refuse de conclure** sur du partiel ou du dégénéré | `67c321b` |
| **`enable_wl_coverage`** — forcer une λ admissible absente des `top_k`, la DP re-optimise le reste. Routée, 36 tests | `9590be2` |
| **la livraison `r75x2-2nm`** — 197 déposables, SEEL 0,5676, zéro surcharge | `2bbab58` |
| **les instruments** — 66 scripts protégés du cp1252 + garde-fou, artefact écrit **avant** la synthèse, compteurs de couverture sur un canal **lu** | `8118721` |

🔒 **Tous inertes par défaut, chemin d'avant au bit.** Chacun a ses tests, et les symboles sont
absents du commit précédent — donc ils échouent tous sur le code d'avant.

### Comment essayer un levier sans écrire de fichier de configuration

```bat
set CERTUS_PROBE_OVERRIDES=injected_strategies=reports/plans/plans_s077_vers_s042.json
set CERTUS_PROBE_TAG=inject12s077
C:\envs\certus\Scripts\python.exe scripts\probe_blocs_vs_plantage.py r75x2 deep 0 0 2.0 0 42 0
```

🔴 **L'étiquette est obligatoire, la sonde refuse sans elle** : deux runs qui ne diffèrent que
par une surcharge rendraient sinon deux artefacts indiscernables. ⚠️ Le parseur découpe sur les
**virgules** — une liste de graines s'écrit donc `screen_seed_list=42;77;101`.

🔴 **NE RESSERRE PAS LA PLAGE DE BLOCS POUR ÉCONOMISER DU TEMPS.** Cette ligne disait
*« ce qui divise le coût sans rien perdre »* — **c'est faux, et mesuré le 2026-08-21** :

```
plage RESTREINTE  ->  Mining found 1 a 2 par nombre de blocs
                      compteur de couverture : « 0 λ deja employees »
                      donc AUCUN groupement rendu par la DP -- les 1 a 2 strategies
                      viennent des graines structurees
plage COMPLETE    ->  le meme bloc 9 en mine 601
```

**Restreindre la plage vide le solveur.** Toute la série de runs 9-11 du 21 août ne mesurait
donc pas la recherche. La cause exacte n'est pas établie : les libellés d'interface parlent de
**diviseurs de complexité** (*« divides the iteration count »*), pas de sélection de plage — et
le détournement fonctionne bien pour choisir les blocs (`75/8,3333 = 9`) tout en cassant la DP.

🔒 **Règle : toute mesure comparative de la RECHERCHE se fait à plage complète.** Une comparaison
à plage restreinte reste valide si elle est **à une seule variable** — c'est le cas du contrôle
injection oui/non — mais elle ne dit rien de la recherche. Consigné en §24-54 de `CLAUDE.md` et
§27 de [`CLAUDE.md`](../CLAUDE.md) du plan de production.

⚠️ Les blocs **1, 2 et 75 sont forcés** par le code, on ne peut pas les exclure.

---

## 3. 📏 CE QUI EST ÉTABLI — tout sur `r75x2` à 2 nm, `deep`

**1. 🔑 Hors ELITE, il n'y a rien — aux DEUX graines.** 0 déposable sur 1488 (graine 77) et
0 sur 1617 (graine 42), crash médiane 100 %. Toute la fabricabilité passe par ELITE.

**2. 🔑 La génération d'ELITE est DÉTERMINISTE.** `_generate_elite_candidate_strategies` énumère
un voisinage trié, parent par parent, et `return` au plafond. Donc « K graines de génération »
**ne peut pas** fonctionner : K graines rendraient les mêmes candidates. La diversité vit dans
les **parents**.

**3. 🔑 Le point de divergence des graines est le CRIBLAGE.** Par signature de plan exacte :

```
n_blocs      1      2-6     7-10    11-15
communes  46,7 %   7,4 %   ~1 %      0 %
```

**Aucun préfixe commun** : dès le bloc 1, où rien n'est encore hérité, la moitié de la
population diffère. Phase A est identique aux deux graines et la DP est déterministe — seul le
criblage Monte-Carlo l'est, et ses survivants deviennent les `inherited_strategies` du bloc
suivant **et** les parents d'ELITE.

**4. 🟢 Le multiseed est un mécanisme réel et il NE SATURE PAS.** Apport moyen en plans neufs
par rang de graine : **5,88 · 5,38 · 4,50 · 5,25 · 4,50**. La cinquième apporte autant que la
deuxième. Et l'effet est **localisé aux blocs 11-13**, là où la DP rend assez de groupements pour
que le criblage ait de quoi trancher.

**5. 📏 Le profil de coût par nombre de blocs**, et le partage **criblage 47 % / ELITE 53 %** :

```
bloc 75 : 1,1 min   ·   blocs 11-14 : 7,9 a 8,3   ·   blocs 3-10 : ~5,1   ·   bloc 1 : 2,8
facteur(K, cap) ~= 0,47.K + 0,53.(cap/120)
```

**6. 🔑 Le plafond de 120 laissait SEPT PARENTS SUR DIX inexplorés.** Un parent à 11 blocs coûte
~42 candidates (`n_blocs × 2` mutations de λ + `(n_blocs−1) × 2` frontières), donc `120/42 ≈ 2,9`
parents sur les 10 annoncés. À 480, mesuré : `generated=424 parents=10`.

**7. 🔵 La porte de plantage juge au PIRE DES TROIS NIVEAUX DE BRUIT**, dont un à **2× le bruit
mesuré** (`robustness_noise_factors = [0.5, 1.0, 2.0]`). La tolérance de 5 % de 👤 s'y applique,
et **aucun artefact ne porte le taux au bruit réel** — `crash_rate` **est** le max. Non mesuré :
c'est l'action 5 du §8.

---

## 4. 🔴 CE QUI EST RETIRÉ — ne pas le recycler

| affirmation | statut |
|---|---|
| « la panne de `probe_renoter` est localisée : `full_dynamics_grid` est vide » | 🔴 **FAUX.** La grandeur n'est déréférencée qu'à **un seul endroit** — `robustness.py:2513`, dans un bloc de **journalisation** gardé par `theory_dyn >= 0.0` — et la Phase B de **production** tourne toujours avec elle vide |
| « le plantage est une propriété de la stratégie » | 🔴 non informatif — vient de l'outil en panne |
| « `crash_gate_confidence` est le meilleur rapport valeur/risque du plan » | 🔴 **mesuré faux** : 0 déposable, compteurs identiques au chiffre près. **Une seule candidate sur 1116** est dans la bande où la borne agit — elle épargne jusqu'à ~7,3 % à `N = 300`, et les rejets sont à 25-99 % |
| « élargir `elite_wl_neighbor_span` aiderait » | 🔴 **réfuté** : `span = 2` porte le coût par parent de 42 à ~64, donc **aggrave** la troncature qu'il prétendait corriger |
| « le code de production reste à `robustness_seed = 42` définitivement » | 🔴 **levée par 👤 le 2026-08-21** — voir §7 |
| « forcer 685 nm » | 🔴 **inutile** : hors ELITE, 711 stratégies y plantent **toutes**, et 3 ELITE à 686 nm sont déposables. La λ n'est ni suffisante ni nécessaire — c'est un **effet de sélection**, ELITE s'est empilé là où ça marchait déjà |

### 🔴 La cause de la panne de `probe_renoter.py` reste NON LOCALISÉE

**Six candidates éliminées**, sans machine : la grille vide · l'unité de `crash_rate` (le noyau
la formate `:.1%`, c'est une fraction, le `100 ×` était correct) · des plans malformés (les blocs
pavent `[0,75)` exactement) · le chemin de **surcharge** de résolution (le config natif 2 nm rend
une marge **bit-identique**) · `expand_variants=False` (le garde ne couvre que la génération de
variantes) · une clé perdue sur `strategy`.

🟢 **`injected_strategies` le remplace et rend la réparation inutile** : les plans traversent le
code de production, sans contexte reconstruit. La docstring de la sonde porte l'avertissement.

### ⚠️ Deux défauts d'instrument, dits parce qu'ils fausseraient une lecture

- **Le compte d'une λ RARE n'est pas lisible dans le journal.** `_format_wl_histogram` n'affiche
  que les **14 λ les plus lourdes** ; 685 nm en porte 1 à 2 par ronde et tombe dans la queue
  masquée. **61 histogrammes tronqués** sur un seul run, et la preuve interne est là : 685 nm
  apparaît 5 fois en génération et **11 fois dans les rejets** — impossible sans troncature. Le
  compte est un **plancher**, et le contrôle du §18.4 du plan n'est ni confirmé ni réfuté.
- **Les graines de génération ne doivent pas contenir la graine de NOTATION.** Le run de la nuit
  a généré sur `42;77;101;202;303` et noté à **42** : canal de **malédiction du vainqueur**,
  mesurée à +12,9 % le 15/08. Générer sur `{77,101,202,303}`, noter sur une base disjointe.
  🟢 **Ce n'est plus une discipline mais un garde-fou depuis le 2026-08-24** — `[GRAINE DE
  NOTATION ... PRESENTE]` en `ERROR` dans le journal. ⚠️ Il **avertit** sans refuser : un run
  peut payer ce canal délibérément, il ne peut plus le payer sans le dire. 🔑 Le défaut n'était
  pas une ignorance mais un **silence** : le chevauchement du 21/08 a été trouvé des semaines
  plus tard en relisant une ligne de commande.

---

## 5. Les fichiers à connaître

| | |
|---|---|
| `reports/nuit_multiseed_20260821/journal_*.log` | les journaux **complets** de la nuit |
| `reports/BATCH_seed42_20260820_235821.md` | le rapport du batch : `base` (porte C1) et `cgc95` |
| `reports/blocs_vs_plantage_r75x2_deep_s042_20260820_120112.json` | la **référence** graine 42, 1617 stratégies |
| `reports/blocs_vs_plantage_r75x2_deep_s077_20260820_160340.json` | les 547 déposables de la graine 77, **avec λ** |
| `reports/plans/plans_s077_vers_s042.json` | les 12 plans injectés — 9, 10 et 11 blocs |

---

## 6. ⚡ Repartir

```bat
C:\envs\certus\Scripts\python.exe scripts\preflight.py
C:\envs\certus\Scripts\python.exe scripts\coherence_md.py
C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Attendu : `PREFLIGHT=GO` · **`1 point(s) a instruire`** (le faux positif instruit en fin de
§0000, et lui seul) · **`0 failed`**.

⚠️ **Ne cite jamais un compte de tests comme référence** — il se périme dès qu'on ajoute un test.
Il valait 2450 le 17/08 et plus de 2560 le 21/08. **Le seul critère est `0 failed`**, comme
c'est écrit plus haut dans ce document, qui est désormais le **seul** document d'arrivée.

⚠️ **L'interpréteur est `C:\envs\certus\Scripts\python.exe`.** Il n'y a **pas** de `.venv` dans
le dépôt ; tout document qui en cite un est faux.

---

## 7. 🔵 LA CONTRAINTE MONO-GRAINE EST LEVÉE — ce qui tombe, ce qui reste

👤, 2026-08-21 : *« même si le code en production est ralenti, ce sera un gain énorme d'inclure
des stratégies diverses venant de plusieurs seed »*.

| | |
|---|---|
| la **RECHERCHE** est multi-réalisation | ✅ tranché |
| la **NOTATION** finale reste-t-elle à une graine fixe ? | 🔴 **ouvert, et c'est une décision de 👤** |

Un score publié doit être **reproductible** — sinon deux lancements du même fichier rendent deux
SEEL. Et si la notation tourne sur les mêmes graines que la génération, on paie la malédiction du
vainqueur. 📌 **Proposition par défaut** : générer sur K graines, **noter sur une base fixe et
disjointe**.

🔒 **Et le mécanisme livré respecte déjà la règle d'or du multiseed** — *on ne s'en sert jamais
pour garder la graine qui marche* : l'union ne transporte que des **plans**, jamais des scores, et
la passe complète **renote tout** sur la réalisation du run. Un test l'épingle
(`test_the_multiseed_union_never_reranks_across_seeds`).

---

## 8. 🔵 CE QUI SUIT, PAR RENTABILITÉ — révisé le 2026-08-21 à 15:00

⚠️ **La version précédente de cette section est périmée** : trois de ses cinq actions sont
faites, et sa « voie B » a reçu sa réponse. Ce qui suit la remplace.

### 8.1 ✅ Ce qui est FAIT, et qu'il ne faut pas refaire

| action d'alors | ce qu'il en est |
|---|---|
| **1. toujours afficher la liste des λ** | ✅ la troncature du `[ELITE-WL]` est retirée (`8f7f14b`). Et la question qu'elle devait trancher — *où 685 nm disparaît-elle* — a sa réponse : **nulle part, elle n'entrait jamais**. Le k-meilleurs ne la sélectionne pas, et la couverture la **force** |
| **4. remonter `crash_rates_by_noise`** | ✅ dans l'artefact, et `scripts/probe_plantage_vs_sigma.py` l'exploite. Il a trouvé bien plus que prévu — voir §1ter |
| **5. rejouer l'injection en plage pleine** | ✅ c'est le **test d'acceptation** de §0 : 197 déposables, SEEL 0,5676, zéro surcharge |
| **2. compter par étage** | 🟠 **à moitié** : le minage se compte maintenant (compteurs de couverture), et cela a révélé que la DP est **vide** à plage restreinte. Le criblage et l'héritage ne se comptent toujours pas |

### 8.2 🔵 Ce qui reste, par rentabilité — **révisé à la reprise du 2026-08-22**

⚠️ La version d'hier listait des actions depuis faites, et n'y mettait **pas** la question de
fond. Voici l'état réel.

**✅ Ce qui est fait, et qu'il ne faut pas relancer :**

| action d'hier | ce qu'il en est |
|---|---|
| lire `couvfull` au bloc 9 | ✅ **tranché** : la DP est vide à **10 blocs et en dessous**, donc la couverture n'a rien à étendre là où les déposables vivent. §30 de [`CLAUDE.md`](../CLAUDE.md) et §31 de [`CLAUDE.md`](../CLAUDE.md) |
| rejouer la config livrée à la graine 101 | 🟠 **partiel** : blocs 15 à 8 lus dans le journal, meilleur **SEEL 0,5707 au bloc 10** (crash 0-2 %). Le run a été arrêté à la demande de 👤 et **n'a pas écrit d'artefact** — les chiffres sont donc dans le journal, pas dans un artefact citable |

**🔵 Ce qui reste :**

| # | action | coût | ce qu'elle décide |
|---|---|---|---|
| ~~**1**~~ | ✅ ~~`r75x2` NU aux graines 101 et 202~~ | fait | **0 déposable chacune.** La 77 est l'exception. Voir §8.2quater ci-dessous, qui remplace cette action |
| ~~**2**~~ | ✅ ~~déplacer les rampes de `reports/` vers `example/`~~ | fait | commit `b13694b`. Vérifié le 2026-08-24 : plus aucune dépendance vivante de `example/` vers `reports/`, seulement des notes `_reproduit` |
| **3** | porter le résultat du jour dans `pages/CERTUS_STRAT.html` | ~30 min, zéro CPU | c'est la vitrine, et 👤 la juge *« ultra importante »*. ⚠️ Avec la condition **dans la même phrase que le chiffre**, et vérification de structure par `html.parser` |
| **4** | terminer l'action 1 d'hier — graine **202** sur la config livrée | ~2 h | une quatrième réalisation. Moins urgent : trois convergent déjà à 0,55 % |
| ~~**5**~~ | ✅ ~~graines de génération **disjointes** de la notation~~ | fait le 2026-08-24 | 🟢 **Le garde-fou est posé, et il n'interdit rien** : `_screen_with_seeds` connaissait déjà les deux graines au même endroit (`certus_strat_workers.py:653`) et ne les comparait jamais. Il crie maintenant en `ERROR` quand la graine de **notation** figure dans les graines de **génération**. ⚠️ **Il avertit, il ne refuse pas** — refuser tuerait une mesure de plusieurs heures à son premier bloc, et le chevauchement est légitime quand on reproduit délibérément un vieux run. Ce qui n'est pas acceptable, c'est qu'il passe en **silence**. 4 tests, dont un qui vérifie qu'il **se tait** sur le cas correct et un qui vérifie qu'il ne **change rien** au résultat |
| **6** | balayer `tp_hysteresis_factor` à bruit fixé | 1 run | sépare les deux lectures de l'anomalie de §1ter |
| **7** | compter le criblage et l'héritage | ~1 h | à faire quand un étage sera suspect, pas avant |

🔑 **L'ordre qui économise le plus de temps** : lancer **1** d'abord (des heures), puis faire **2**
et **3** pendant qu'elle tourne — ils ne demandent aucun CPU.

### 8.2quater 🔑 LA PREMIÈRE ACTION, RÉVISÉE LE 2026-08-22 — dimensionner K

🔴 **Et elle repose sur une erreur de raisonnement que j'ai faite puis corrigée le même jour.**
J'avais conclu que *« le multiseed ne sauve pas ce cas : trois graines sur quatre rendent zéro,
donc l'union sur trois aurait rendu zéro »*. **Faux** — j'évaluais *l'union des trois qui ont
échoué* au lieu de *l'union de K graines tirées*. La graine 77 existe et trouve **547
déposables nativement**.

```
si p = 1/4    K=4 -> 68 %   K=6 -> 82 %   K=8 -> 90 %   qu'au moins une graine trouve
```

⚠️ `p` est estimé sur **quatre** graines dont une réussit : l'intervalle à 95 % va grossièrement
de **0,01 à 0,7**. C'est une arithmétique conditionnelle, pas une prédiction.

> 🔑 **Le multiseed de GÉNÉRATION est donc la réponse à la demande de 👤** — *que le code trouve
> 0,57 à 2 nm sans savoir a priori qu'il faut des rampes.* Aucune connaissance préalable : le
> code fait ce qu'il fait déjà, **K fois**, et garde l'union.

**L'action, et elle est bon marché :**

| # | action | coût | ce qu'elle décide |
|---|---|---|---|
| **1** | **`r75x2` NU aux graines 303, 404, 505** | ~4 h 30 | 🔑 **la valeur de `p`, donc K.** Au moins une qui trouve → K = 4 à 8, le mode est utilisable. Aucune → `p ≤ 1/7`, K ≈ 15-20, coûteux mais **toujours autonome** |
| **2** | spécifier le mode multiseed de génération | ~2 h, zéro CPU | union par signature, **arrêt au premier succès**, notation à une graine **disjointe** |

🔒 **Dans les deux cas la voie reste ouverte, seul le prix change.** Et la garde anti-triche est
mesurée : noter à une graine qui n'a pas servi à trouver coûte **+0,55 %**, cinq fois sous le
bruit.

📌 Les briques existent : `_strategy_signature` et l'union par signature (`44f352d`), plus la
surcharge de `robustness_seed`. C'est un **pilote**, pas un algorithme neuf.

### 8.2ter 🔒 LA RÈGLE DE DÉCISION DE L'ACTION 1 — écrite AVANT la mesure

Elle est écrite d'avance pour ne pas être réinterprétée selon le résultat.

| résultat de `r75x2` nu | décision |
|---|---|
| **101 et 202 trouvent** des déposables | la graine 42 est **malchanceuse** → le **multiseed de génération** est la réponse produit : union sur K graines, faisabilité exigée sur **toutes**. K peut être petit |
| **une seule** trouve | la recherche réussit ~1 fois sur 2 → même conclusion, K plus grand |
| **aucune** ne trouve | la graine **77 est chanceuse**. 🔴 **Ne conclus PAS « la découverte autonome est impossible »** — c'est ce que cette case disait, et c'était faux : la **queue Rate** trouve seule à 2 nm, à SEEL 0,67-0,69 (voir §0bis). La conclusion correcte est *aucune voie autonome n'atteint le niveau de 0,57 en pur optique*, et la réponse produit devient `scripts/generer_rampes.py` pour ce niveau, la queue Rate pour un niveau dégradé mais autonome. **Ce n'est pas un échec** |

🔴 **CE PARAGRAPHE A ÉTÉ ÉCRIT PUIS RÉFUTÉ LE MÊME JOUR — voir §00 en tête de fichier.** Il
disait : *« la règle a tiré le 2026-08-22, et c'est la troisième branche : les graines 101 et
202 nues rendent 0 déposable, la 77 est l'exception. »*

**Faux, et sur trois graines de plus.** Les graines **404 et 505 trouvent nativement** — 372 et
311 déposables, SEEL 0,5599 et 0,6112 nm. La branche qui a réellement tiré est la **première** :
*plusieurs graines trouvent → le multiseed de génération est la réponse produit, et `K` peut
être petit.*

🔑 **La leçon de méthode vaut plus que le résultat** : la règle avait été écrite d'avance pour
ne pas être réinterprétée selon le résultat, et c'est ce qui a marché — elle a été appliquée
telle quelle, puis **la mesure suivante l'a fait changer de branche**. Une règle écrite
d'avance ne protège pas d'un échantillon trop petit. **Quatre graines ne suffisaient pas.**

📌 Rappel du contexte : on n'a que **deux** graines mesurées nues sur `r75x2` à 2 nm — la 77
trouve 547 déposables, la 42 en trouve **zéro** sur 1617. Deux points ne permettent aucune
probabilité, et c'est précisément pourquoi cette mesure est la plus informative qui reste.

### 8.2bis 🔒 LE PÉRIMÈTRE EST FIXÉ À `r75x2` — et voici ce que cela interdit de dire

> 👤 *« non, on reste sur le 75cx2 »* (2026-08-21)

**La décision est légitime** : `r75x2` est l'étalon courant, et disperser l'effort sur un second
composant avant d'avoir consolidé celui-ci serait un mauvais arbitrage. Mais elle a une
conséquence qu'il faut écrire une fois pour ne pas la découvrir plus tard :

🔴 **Aucune affirmation de GÉNÉRALITÉ n'est permise.** Tant qu'un second composant n'a pas été
mesuré, tout ce qui est établi porte sur **un empilement, à une fente**. Les formulations
correctes :

| ✅ défendable | 🔴 interdit |
|---|---|
| « sur `r75x2` à 2 nm, la production trouve SEEL 0,57 » | « la production trouve SEEL 0,57 » |
| « la méthode des rampes a fonctionné sur `r75x2` » | « la méthode des rampes fonctionne » |
| « à trois graines, le résultat tient » | « le résultat est robuste » |

⚠️ Et le rappel de la règle du projet, qui n'est pas abrogée mais **suspendue par choix** :
*un correctif qui ne marche que sur `r75x2` à 2 nm n'est pas un correctif.* Le random75 reste le
seul composant sans cavité, sans miroir et sans périodicité — donc le seul qui puisse un jour
dire si une règle est générale. **La porte n'est pas fermée, elle n'est pas ouverte maintenant.**

📌 Corollaire pratique : `scripts/generer_rampes.py` est écrit pour n'importe quel composant de
`COMPOSANTS`, mais il n'a tourné que sur `r75x2`. Sa généralité est **une intention de
conception, pas une mesure**.

### 8.3 🔴 La circularité — ce qui a changé, et ce qui n'a pas changé

**Ce qui n'a pas changé** : la source des bons plans est un run à une **autre graine**. Pour un
produit, cela ne s'auto-amorce pas.

**Ce qui a changé** : la voie B n'est plus une question ouverte mais un **mécanisme écrit et
mesuré**. On sait *pourquoi* 685 nm n'entrait pas — le k-meilleurs prend les 100 groupements les
moins chers, et cette λ n'en fait jamais partie — et la couverture la fait entrer, avec la DP qui
re-optimise le reste du plan autour d'elle.

| voie | ce qu'elle vaut aujourd'hui |
|---|---|
| **A — bibliothèque de rampes** | 🟢 **livrée et mesurée.** Marche, mais spécifique au composant |
| **B — la couverture en λ** | 🟢 **mécanisme acquis**, 🔵 issue en cours de mesure. C'est la seule voie qui rende la production autonome **sur un composant neuf** |
| **C — beaucoup plus de graines** | 🟠 l'union ne sature pas à 5, mais rien ne borne le `K` nécessaire, et 5 lignées distinctes n'avaient produit aucune 685 nm |

⚠️ **Un arbitrage toujours assumé** : relâcher bruit et dérive **en génération** n'a pas été
essayé. Le levier est bien visé — il attaque les 84 % de rejets — mais tout ce qu'il trouverait
doit être **re-jugé au nominal**. `injected_strategies` lève l'obstacle qui l'empêchait : c'est à
rouvrir avec 👤 si la couverture échoue.
