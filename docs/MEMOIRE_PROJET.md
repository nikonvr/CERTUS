# Mémoire du projet — versée dans le dépôt le 2026-08-16

> 🔴 **Pourquoi ce fichier existe.** Ce savoir vivait dans la **mémoire de compte** de l'agent
> (`<.claude>/projects/<projet>/memory/`), qui est **par compte et par machine** et **ne suit
> pas un `git clone`**. Sur un autre PC ou un autre compte, il était perdu.
> Il est maintenant **dans le dépôt**, donc il voyage avec le code.
>
> 👤 : *« le plus important pour moi est d'avoir la possibilité sur un autre compte et un
> autre PC de reprendre sans perte d'information. »*

**Ce qui suit n'est PAS dans le reste de la documentation** — c'est du savoir opérationnel
accumulé, qui a coûté du temps à chaque fois qu'il a manqué.

---

## 1. 🔴 Le hook d'auto-push — tout commit est une PUBLICATION

Le dépôt contient un hook `.git/hooks/post-commit` qui lance `git push` en arrière-plan après
**chaque** commit, vers **`github.com/nikonvr/CERTUS`, un dépôt PUBLIC**. Il journalise dans
`logs/git_auto_push.log`.

⚠️ **`git commit --no-verify` ne le neutralise PAS** : cette option ne saute que `pre-commit`
et `commit-msg`, jamais `post-commit`.

**État** : 🔴 **ACTIF**, à la demande de 👤 le 2026-08-14. Il avait été désactivé le
2026-08-01 (renommé `post-commit.DESACTIVE`) après avoir poussé un commit alors que 👤 avait
demandé de ne rien pousser. La copie inerte est conservée à côté.

**À appliquer avant tout commit :**

```bash
ls .git/hooks/post-commit
```

S'il est actif — **ne jamais committer** de données personnelles, de chemins contenant un nom
d'utilisateur, d'adresses e-mail, ni de binaires. ⚠️ Le `.gitignore` ne couvre qu'`/python-*-amd64.exe` :
tout autre exécutable déposé à la racine **partirait**.

📌 Si 👤 demande un commit **sans** pousser : désactiver le hook **avant** de committer.

---

## 2. 🔴 Vérifier quel code est réellement importé — l'erreur n° 1 du projet

Le projet vit dans des **snapshots datés** (`0108`, `0807`, `1408`, …) copiés les uns depuis
les autres. **Le venv d'un snapshot peut charger le code d'un AUTRE**, silencieusement, sauf
sous pytest. Toute mesure faite ainsi décrit un code différent de celui qu'on vient de
modifier — **sans le moindre message d'erreur**.

```bash
C:/envs/certus/Scripts/python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

Le chemin affiché **doit** être dans le snapshot où tu édites. Vérifié résolu le 2026-08-14,
**mais la vérification reste obligatoire après toute copie de snapshot.**

⚠️ Aucune racine n'est écrite en dur nulle part, et c'est délibéré : l'ancienne consigne
exigeait un chemin qui n'existe plus, ce qui envoyait vers un dossier fantôme.

---

## 3. Les pièges du banc headless

| piège | conséquence |
|---|---|
| **Mesurer avec `tests/headless/`** | `test_design.py` et `test_strat.py` **remplacent le calcul par un mock**. On mesure le mock. |
| **QApplication ramassée par le GC** | garder une référence vivante, sinon l'application meurt en cours de run |
| **stdout détourné** | les sorties du solveur n'arrivent pas dans le log qu'on lit |
| **Dialogues modales** | bloquent indéfiniment en headless — `Bx.autoanswer_dialogs(True)` |
| **`_is_busy` mort** | ne pas s'y fier pour savoir si un run est fini ; utiliser `Bx.wait_for(app.worker)` |
| **A/B en séquence** | 🔴 la machine **dérive de ±25 % en deux heures**. Un A/B séquentiel attribue la dérive au changement. **Alterner les versions.** |

L'outil correct est **`scripts/bench_examples.py`**, qui pilote les vrais exemples de
`example/` sans mock.

---

## 4. Ce que 👤 attend dans un rapport

**Le SEEL, en nanomètres, jamais le RMSE seul.** 👤 : *« la performance, j'aime bien la
mesurer en SEEL »*. `SEEL = 2·√(score)`. C'est une **erreur d'épaisseur équivalente par
couche**, donc lisible directement en salle ; le RMSE est un nombre sans unité physique.

Dans tout tableau, le SEEL en colonne principale, le RMSE en secondaire.

⚠️ **Les repères que 👤 a en tête ont bougé.** Il jugeait le 99c *« un peu moins performant »*
à ~0,8 nm ; ce chiffre était un **score de repli** (100 % de plantage). Les repères à jour
sont au §21 de `CLAUDE.md`.

---

## 5. ⚠️ `d_lo` et `d_hi` dans INDEX SPLINE — une nominale et une tolérance

Dans `CertusIndexSplineApp`, les widgets `d_lo` et `d_hi` ne sont **pas** une borne basse et
une borne haute : `d_lo` porte l'**épaisseur nominale**, `d_hi` la **tolérance**. La
conversion se fait dans `certus/ui/certus_index_spline_eventsextras_mixin.py`.

🔴 **Le champ `d_lo`/`d_hi` de `SplineOptConfig`, lui, contient bien des bornes.** Les deux
niveaux portent les **mêmes noms avec des sens opposés**.

Saisir 1600 et 1800 signifie donc *« nominale 1600 nm, tolérance ± 1800 nm »*, ce qui laisse
le solveur atteindre 931 nm sur un dépôt de 1700. Le bon réglage pour les données de
l'article 0607 est **1700 et 100**.

📌 **Cette confusion a invalidé plusieurs heures de conclusions**, dont un rapport affirmant à
tort que les RMSE publiées n'étaient pas reproductibles. **Vérifier la ligne
`[d min=…, d max=…]`** affichée par le dialogue Smart Init avant d'exploiter un run.

---

## 6. Performance — ce qui est acquis, et où est la suite

Gains mesurés sur les exemples réels, branche `refactor-corridors-mixins` :

| objet | gain |
|---|---|
| STRAT : dispatch njit, cache de matrices dupliqué | **−61 %** |
| PGLOBAL : sur-souscription de threads numba | −29 % par évaluation |
| RE : `slice` au lieu de copies de blocs | −11 % |
| DESIGN : course sur `_ep_buffer` | correction — 278 évaluations fausses sur 48 000 |
| cache spline LRU | **0 s** — le plan surestimait |

🔴 **Il n'y a PAS de ×2 disponible** dans les pistes documentées. Le fossé entre machines va
de ×1 à ×3,2 selon les modules, **pas** ×7-10. Détail dans
[`PERFORMANCE.md`](PERFORMANCE.md).

⚠️ `docs/PLAN_OPTIMISATION.md` est cité par d'anciennes notes comme contenant trois
affirmations fausses — **ce fichier n'existe plus**.

---

## 7. Comment régénérer la mémoire de compte à partir d'ici

La mémoire de compte reste utile : elle est chargée automatiquement, alors que ce fichier
doit être ouvert. Sur une nouvelle machine, en recréer une entrée par section ci-dessus dans
`<.claude>/projects/<projet>/memory/`, avec un `MEMORY.md` d'index d'une ligne par fichier.

🔑 **Mais la source de vérité est ici**, dans le dépôt. Si les deux divergent, **ce fichier
gagne** — c'est lui qui est versionné, relu et vérifié par `scripts/check_docs.py`.
