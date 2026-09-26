# CERTUS — règles de travail

Suite scientifique de **couches minces optiques** (PyQt6 + NumPy/SciPy/Numba) : détermination
d'indice, design d'empilements, stratégie de dépôt. Le code calcule de la **physique réelle**
servant à fabriquer de vrais filtres : une erreur silencieuse ne plante pas, elle produit un
**résultat faux qui a l'air juste**, et quelqu'un fabrique une pièce avec.

**Deux documents, et deux seulement :** ce fichier porte les **règles** ; l'**état** du projet
(repères mesurés, décisions, défauts ouverts, chantiers) est dans [`docs/ETAT.md`](docs/ETAT.md),
dont la **section 0 est la reprise** : à lire en premier, et à tenir à jour au fil du travail.
L'historique — campagnes, hypothèses réfutées — est dans [`docs/archives/`](docs/archives/) et
**ne fait pas autorité**. Les numéros de section que citent le code et les archives désignent
l'ancienne version de ce fichier, archivée sous
[`docs/archives/CLAUDE_2026-09-26.md`](docs/archives/CLAUDE_2026-09-26.md) ; ceux du registre
des défauts renvoient à [`docs/archives/DEFAUTS_OUVERTS.md`](docs/archives/DEFAUTS_OUVERTS.md).

## 1. Démarrage — avant de toucher à quoi que ce soit

```bat
python scripts\preflight.py
```

Elle doit finir par `PREFLIGHT=GO`. Elle vérifie les deux **propriétés** qui comptent :
`import certus` résout **dans l'arbre où tu édites**, et l'interpréteur porte les dépendances
(PyQt6, numpy, scipy, numba). Aucun chemin d'interpréteur ni de racine n'est écrit en dur, et
c'est délibéré : les chemins se sont périmés à chaque déménagement. En cas de doute,
`python -c "import sys; print(sys.executable)"`.

🔴 **Le dépôt est PUBLIC** (`github.com/nikonvr/CERTUS`). Rien qui porte une donnée
personnelle, un secret ou l'œuvre d'un tiers n'entre dans l'index — métadonnées des classeurs
Excel comprises. Committer ne publie **pas** par défaut : le hook `.githooks/post-commit` ne
s'arme que par `git config core.hooksPath .githooks`, réglage local jamais hérité. Vérifie avec
`git config --get core.hooksPath` et `git status -sb`, ne le suppose pas.

## 2. Valider — le seul critère est `0 failed`

```bat
python -m ruff check .
python -m pytest tests/oracle/ -q --no-cov
python -m pytest tests/unit/ -q --no-cov
python -m pytest tests/ui/ -q --no-cov
python -m pytest tests/ -q --no-cov --ignore=tests/oracle --ignore=tests/unit --ignore=tests/ui
```

📏 Mesuré du 2026-09-25 au 27 (Windows 11, Ryzen 7 5700G 8 cœurs / 16 threads, 31 Go,
Python 3.14.7, cache chaud) : oracle 6 à 20 s · unit 3 à 4 min · ui 20 min · le reste,
mesuré par dossier, ~9 min dont headless 3 min 24 et régression ~3 min.
**Une durée sans sa machine ne vaut rien ; un compte de tests se périme au premier test
ajouté — ne recopie ni l'un ni l'autre.**

| échec | ce que c'est |
|---|---|
| 3 tests à la **première** passe après un changement de numba ou d'interpréteur (`test_phase2_gradient`, deux `TestIRGlobalModelStrategy`) | faux échecs de cache numba froid : **relance avant de signaler** |
| un test d'interface qui meurt sans message | arrêt natif `0xC0000005` du worker Qt, mesuré 2 fois sur 120 lancements ; le harnais réessaie une fois |
| un processus qui meurt sans message Qt | sous Windows, Qt écrit dans `OutputDebugString` : relance avec `QT_FORCE_STDERR_LOGGING=1`, et `-s` pour que pytest ne capture pas (souvent « QThread: Destroyed while thread … is still running », D23) |
| un test qui passe seul et échoue en suite | fuite d'état entre tests (caches de classe, `sys.modules`) : cherche le test précédent |

Si un test est rouge **avant** que tu aies touché quoi que ce soit : arrête-toi et signale.
Et `tests/oracle/` avant et après toute modification d'un calcul optique.

## 3. Les onze interdits — aucune exception

1. **Jamais `ruff check --fix`** : beaucoup d'imports « inutilisés » sont des ré-exports volontaires.
2. **Jamais agrandir `extend-ignore`** dans `pyproject.toml` ; un cliquet le surveille.
3. **Jamais supprimer `reports/`** : résultats scientifiques versionnés de 👤.
4. **`example/example_strat/JSON-strat-example.json` ne se modifie que pour DURCIR** ; il a
   dérivé quatre fois vers le permissif. Pour essayer autre chose, injecter après coup
   (`scripts\probe_anchor_noise_pipeline.py`).
5. **Jamais « corriger » `except A, B:`** : syntaxe PEP 758 de Python 3.14, voulue.
6. **Jamais inverser `n̂ = n − ik`** (k ≥ 0) : l'inverse crée de l'énergie (`R + T > 1`).
7. **Jamais réimplémenter une formule TMM** : la source unique pour R et T est
   `certus/physics/certus_opt_tmm.py::compute_RT_from_matrix` (deux réimplémentations fausses,
   de 46 et 82 points de réflectance).
8. **Jamais découper `certus/core/_certus_physics_impl.py`** (`DO NOT SPLIT` : visibilité
   mutuelle des noyaux compilés).
9. **Jamais affirmer un résultat non mesuré.** Soit tu colles la sortie de la commande, soit
   tu écris « je n'ai pas mesuré ». Il n'y a pas de troisième option.
10. **Jamais de rapport de session à la racine** ; une sortie de campagne va dans `reports/`.
11. **Jamais de français dans les commentaires, docstrings et journaux de `certus/`.** Restent
    en français, délibérément : les mots utilisés comme **données** (`certus_re_helpers.py`),
    les **clés JSON persistées** (`seuil1`/`seuil2`), les formats de journal que des scripts
    analysent (la ligne de compteurs ELITE) et les **libellés vus par l'utilisateur**.
    Garde-fou : `tests/unit/test_certus_is_written_in_english.py`.

## 4. Les erreurs qui annulent un travail

| erreur | conséquence |
|---|---|
| modifier un arbre et en mesurer un autre | aucun message, tout est faux. Les worktrees de `.claude/worktrees/` sont des **copies du dépôt dans le dépôt** : un balayage depuis la racine les lit. Balaye les fichiers **suivis** (`git ls-files`) |
| conclure avant la mesure | annulé à la relecture |
| changer deux choses à la fois | personne ne sait laquelle a agi (contrainte **C3** : une chose, un commit) |
| croire un chiffre de bruit qui ne varie pas avec le bruit | c'est un artefact : divise le bruit par 100 et remesure |
| lancer une mesure pendant qu'autre chose tourne | le banc rend `RESULT=None`, qui ressemble à un résultat ; cherche `WAIT_TIMEOUT=` |
| vérifier une non-régression « aux tests près » | les tests ne prouvent pas l'identité numérique : il faut le **bit** |
| un paramètre visible qui n'atteint pas le calcul | pire qu'absent : il fournit une fausse explication. **Avant d'attribuer un effet à un paramètre, vérifie qu'il arrive** |

## 5. La règle d'or et les trois contraintes

> **Tout nouveau paramètre est inactif par défaut, et le chemin inactif rend exactement les
> mêmes bits qu'avant.** (C1)

- **C1** s'éprouve par une empreinte `float.hex()` du noyau, pas par le `RESULT` du banc : à
  état compilé identique le banc est déterministe, mais **une recompilation décale les
  derniers chiffres** (2,8e-11, reproductible). Ce harnais n'existe pas encore (voir ETAT).
- **C2** — croissance et notation voient **la même réalisation** de chaque perturbation :
  tout tirage est une fonction pure de (graine, tirage, index physique), **jamais** de la
  stratégie (ni λ, ni découpage en blocs, ni épaisseur obtenue). Générateur :
  `certus/physics/certus_strat_math.py::_seeded_noise_sample`.
- **C3** — une chose à la fois, un commit chacune.
- Un test ajouté pour un correctif **doit échouer sur le code d'avant** — sinon il ne prouve rien.

## 6. Pièges — chacun a déjà coûté une session

- **`params` n'est pas toujours un dict** (DTO pydantic sur certains chemins) : `get` et `[]`
  marchent, **`setdefault` lève**.
- **Importer un paquet exécute son `__init__.py`** : depuis `certus/physics/`, importer
  `certus_physics.X` est circulaire ; passe par la façade, et `TYPE_CHECKING` pour une annotation.
- **Numba fige les tableaux de module** à la compilation : avec `cache=True`, une donnée
  modifiée sans toucher au `.py` reste servie périmée.
- **Les tests partagent des caches de classe** (`SplineBasisCache._cache`…) : sauve et
  restaure-les dans une fixture `autouse`.
- **Un test qui échoue n'a pas forcément tort — mais parfois si** : cinq tests vérifiaient un
  comportement faux. Comprends d'abord, dis lequel des deux est faux, et pourquoi.
- **La Phase A ne dit rien** : lis le `reports/STRAT_observability_*.json` le plus récent.
- **INDEX SPLINE : `d_lo` / `d_hi` du widget sont la NOMINALE et la TOLÉRANCE**, alors que les
  mêmes noms portent des **bornes** dans `SplineOptConfig`. Vérifie la ligne `[d min=…, d max=…]`
  du dialogue Smart Init avant d'exploiter un run.
- **`tests/headless/test_design.py` et `test_strat.py` remplacent le calcul par un mock** : ne
  mesure rien avec. Le banc sans mock est `scripts\bench_examples.py`.
- **Le premier calcul est lent** (compilation numba, +30 s) : chauffe, puis mesure.
- **N'écris pas l'artefact que tu décris** : un hexadécimal cité dans un commentaire fait
  bouger le cliquet des couleurs, une règle QSS citée dans une f-string est recrachée dans la
  feuille. **Nomme, ne cite pas.**

## 7. Conventions physiques

- Convention de Macleod `n̂ = n − ik`, k ≥ 0, partout.
- `calculate_transmission_single` inclut **délibérément** la face arrière
  (`DO NOT REMOVE THE BACKSIDE TERM`) : il diffère légitimement d'un TMM nu.
- `tests/oracle/tmm_reference.py` est une référence TMM **indépendante** (Macleod, chap. 2,
  matrices 2×2 explicites), sans une ligne partagée avec `certus.physics`. Sers-t'en.
- Un marqueur `LOCKED` n'est pas une preuve : le bug de signe monocouche en portait un.
- 🔴 **QWOT ≠ point tournant.** Le QWOT est l'épaisseur optique d'**une couche**
  (`m = 4nd/λ`) ; le point tournant est l'instant où l'admittance du **système entier**
  devient réelle, `tan 2δ = R/Q`. Leur période commune vaut un quart d'onde à λ_mon, mais le
  **départ** est décalé de `½·arctan(R/Q)`, fixé par l'empilement du dessous. Les deux ne
  coïncident que sur la couche 1 d'un substrat nu, ou sur un empilement tout en QWOT à λ_mon.
  Le comptage naïf s'est trompé d'un **facteur 59**. Compte les points tournants par la forme
  fermée (`scripts\probe_turning_points.py`), jamais par l'épaisseur.

## 8. Architecture — frontières à respecter

- `certus.core`, `certus.physics`, `certus.domain` n'importent **jamais** PyQt6 ni `certus.ui`.
- `certus.ui` et `CERTUS_HUB.py` ne contiennent **aucun** algorithme de calcul.
- Thème : toujours `apply_certus_theme()` et les jetons `CertusTheme`, jamais un hexadécimal.
- Des inversions de couches existent déjà (`utils → ui`, `core → workers`, cycle
  `physics ↔ core`) : **n'en crée aucune nouvelle** ; si tu en as besoin, le symbole doit
  descendre dans `domain/` ou `core/`.
- Seul `certus/domain/` a un `__init__.py` (paquets PEP 420) : le projet s'utilise en source.
- Les trois `certus_*.py` de la racine sont des façades de ré-export que des tests importent.

## 9. Vocabulaire

| terme | sens |
|---|---|
| juge de paix | le dichroïque 48 couches, `example/example_strat/JSON-strat-example.json` — un repère, pas le seul composant |
| λ de contrôle, bloc | la longueur d'onde surveillée ; un bloc = des couches consécutives à la même λ |
| POEM | arrêt à un pourcentage de l'amplitude entre les deux derniers points tournants |
| plantage, rendement | un dépôt qui ne se termine pas ; la part de ceux qui se terminent (objectif 95 %) |
| Phase A, Phase B | choix d'une λ par couche ; regroupement en blocs et test Monte-Carlo |
| SEEL | erreur d'épaisseur équivalente par couche, en nm — **la** grandeur qu'on rapporte, jamais le RMSE seul |

## 10. Tenir la documentation

- **Un fait, un seul endroit** : un état dans `docs/ETAT.md`, une règle ici. Recopier un fait,
  c'est préparer sa péremption — ce dépôt a compté 80 documents contradictoires, puis un
  fichier unique de 5 413 lignes, puis 17 000 lignes réparties.
- **Cite une FONCTION, jamais un numéro de ligne** : 38 % des renvois `fichier.py:ligne`
  vérifiables étaient périmés le 2026-09-25.
- Pas de récit dans les documents vivants (« cette ligne disait… ») : `git log` le garde.
- Contrôles : `python scripts\coherence_md.py` (un fait = une valeur dans tous les `.md`, archives
  exclues), `python scripts\check_claude_md.py`, `python scripts\check_docs.py`. « 0 point à
  instruire » ne veut pas dire « tout est cohérent » : ils ne lisent pas les phrases.
- La vitrine `pages/CERTUS_STRAT.html` a un régime strict : tout nombre sourçable dans le code
  ou dans `reports/`, la limite montrée, la structure revérifiée (`python scripts\verifier_html.py pages\CERTUS_STRAT.html`).

## 11. Quand s'arrêter et demander

Une instruction ambiguë · un test dont tu ne sais pas s'il a tort · une mesure qui s'écarte
nettement de l'annoncé · la tentation de violer un interdit · plus de trois fichiers pour une
seule action · **un résultat meilleur que prévu** — le plus souvent, on mesure la mauvaise chose.
S'arrêter n'est jamais un échec ; inventer, si.

## 12. Vérifier le travail d'un autre agent

Un rapport est une déclaration, pas une preuve : essaie de la **casser**. Trois questions, dans
l'ordre : le diff correspond-il à la déclaration ? la mesure se reproduit-elle ? la conclusion
suit-elle de la mesure ? Puis cinq contrôles : le nouveau paramètre est-il inerte au bit ? les
tests ajoutés échouent-ils sur le code d'avant ? les grandeurs de bruit suivent-elles le bruit ?
chaque filtre rejette-t-il réellement quelque chose (**compte les rejets**) ? les conclusions
dépassent-elles les mesures ? Le repère d'origine est l'étiquette `depart-gemini` : ne la
déplace pas.
