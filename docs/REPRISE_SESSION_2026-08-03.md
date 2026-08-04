# Reprise — session du 2026-08-03

Écrit pour l'agent (ou l'humain) qui prend la suite, y compris sous un autre
compte ou sur une autre machine. **Tout chiffre marqué « mesuré » l'a été ici** ;
tout le reste est signalé comme hypothèse.

À lire avec `docs/REPRISE_PERF.md`, que ce document **corrige sur plusieurs
points** — voir §5. Ne pars pas des chiffres du §2 de ce document-là sans avoir
lu le §2 de celui-ci.

---

# 0. PAR OÙ COMMENCER

*Si tu ne lis qu'une section, c'est celle-ci. Le reste est la justification.*

## 0.1 Vérifier l'environnement — 1 minute

```bat
cd /d C:\dev\CERTUS\0108
uv sync --extra dev --extra freeze
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
dir .git\hooks\post-commit*
```

Le chemin affiché doit être sous `C:\dev\CERTUS\0108`. Le hook `post-commit` est
**ACTIF** : chaque commit part automatiquement vers le dépôt **public**
`nikonvr/CERTUS` (§7).

## 0.2 L'OBJECTIF : un facteur 2 sur un module. Rien d'autre.

> Le but n'est **pas** d'optimiser CERTUS en général. C'est de savoir s'il existe
> un **×2** sur l'un des modules. Tout ce qui vise moins de ×1,5 ne mérite pas le
> temps de mesure qu'il coûte sur cette machine — et une mesure coûte cher ici :
> STRAT, c'est 130 s le run, donc 20 min la campagne A/B.

### 🔴 RÉPONSE : il n'y a PAS de ×2 disponible dans CERTUS en l'état

Les deux seules pistes crédibles ont été mesurées le 2026-08-04. **Les deux sont
tranchées.**

| Piste | Verdict mesuré |
|---|---|
| **METAL — `use_cache=True`** | 🔴 **CLOSE. Le gain EST l'erreur.** Le ×2,06 se reproduit (154,6 → 75,2 s) mais avec une clé de cache **exacte** le résultat redevient juste et le gain disparaît : **×1,03**, taux de succès effondré de 88,1 % à 18,8 %. Les 88 % de hits étaient des géométries distinctes écrasées par l'arrondi — précisément les perturbations de gradient. Détail complet dans `REPRISE_PERF.md` §4.5. |
| **STRAT — `compute_layer_profile`** | ✅ **GAIN RÉEL de −9 à −10 %**, 4 paires sur 4, `RESULT` identique aux 8 runs. Acquis et conservé. Mais ce n'est pas un ×2. |

**Conclusion honnête : le seul gain réel de la session est de 10 % sur STRAT.**
Aucun facteur 2 n'existe dans les pistes documentées. Chercher plus loin coûterait
des nuits de calcul pour des gains de quelques pourcents.

Ce qui a aussi été établi, et qui vaut mieux qu'un ×2 hypothétique : **le fossé
machine est bien plus faible que le document ne le laisse craindre** — de ×1 à ×3,2
selon les modules, pas ×7-10. Une partie de ce que le plan attribuait au code venait
du cache numba qui traînait dans Google Drive, et le déménagement l'a réglé
gratuitement.

### Facteurs machine — les 8 modules, tous mesurés

| Module | Réf. doc (16 c) | Ici `RUN_S` | Facteur |
|---|---|---|---|
| INDEX | 12,8 s | 12,4 | **×0,97** |
| Oracle | 8 s | 11,7 | ×1,46 |
| FIELD | 0,06 s | 0,119 | ×2,0 |
| STRAT | 47-64 s | 113-152 | ×2,4-3,2 |
| METAL_SINGLE | 52-68 s | 154,6 | ×2,3-3,0 |
| RE | 29-30 s | 91,8 | ×3,1 |
| METAL_BILAYER | 67 s | 212,5 | ×3,2 |
| DESIGN | 43-93 s | 115,2 | ×1,2-2,7 |
| INDEX_SPLINE | 1,6 s | 9,43 | ×5,9 ⚠️ |

✅ **Les 8 modules ont désormais un ancrage `RESULT` valide** (§11.2).

### Où le ×2 n'existe PAS — ne pas y perdre de temps

| Module | Plafond réaliste | Raison |
|---|---|---|
| INDEX | 20-30 % | JIT pendant le run ~15 %, float32 en double compilation autant. |
| FIELD | ~0 | 0,119 s. Le doc dit « rien à gagner », il a raison. |
| DESIGN | — | PGLOBAL ne pèse que **1,5 %** du profil. Le §4.1 vise la *qualité* d'optimum à budget égal, **pas le temps**, et son protocole coûte des nuits ici. |
| RE | — | Déjà traité par `f6f9102` (−11 %). Aucun gisement identifié. |
| INDEX_SPLINE | — | Son ×5,9 est un écart **machine**, pas un gisement algorithmique. |

### Le seul travail non-performance qui reste justifié

**Contrôler l'ancrage `RESULT` de `metal_single`, `metal_bilayer`, `re`, `design`**
— ~5 min. Ce n'est pas de l'optimisation, c'est un garde-fou : 2 des 4 modules
déjà vérifiés rendaient `None` en silence (§11.2). Et `metal_single` est
précisément le module de la piste n°1.

**Commandes utiles :**

```bat
:: un banc, machine au repos
.venv\Scripts\python.exe scripts\bench_examples.py <module> --auto-yes
```

```bash
# A/B alterne — depuis Git Bash, chemins en /, liste de fichiers entre guillemets
bash scripts/ab_compare.sh "fichier1.py,fichier2.py" "<commit>^" strat 4 --auto-yes
```

## 0.3 🔴 Ne PAS faire — pièges tous vérifiés dans cette session

| Piège | Ce qu'il coûte |
|---|---|
| **Mesurer avec autre chose en vol** | INDEX : `RUN_S` **81,5 s** chargé contre **12,4 s** au repos. Facteur **6,6**, pas quelques pourcents (§2). |
| **Moyenner au lieu de compter les paires gagnantes** | STRAT dérive de **17 %** entre runs identiques (§12). Une moyenne noierait un gain réel de 10 %. |
| **Alterner UN fichier d'un changement qui en touche plusieurs** | Ancienne signature + appelant non basculé → candidats **silencieusement écartés** et bras « SANS » faussement rapide (§11.1). |
| **Croire un `RESULT` sans avoir lu le `WARN`** | 2 modules sur 8 rendaient `None` en silence (§11.2). |
| **Basculer `use_cache=True`** | **Non sûr**, mécanisme établi : la clé de cache arrondit à 1e-6 nm quand le pas de gradient vaut 1e-8 (§10.3). |
| **`uv pip compile` pour régénérer `requirements.lock`** | `pydantic>=2.14.0a1` fait basculer tout le graphe en préversions → tire `numba 0.67.0rc1` (§6). Utiliser `uv export`. |
| **Recopier le `.venv` vers Google Drive** | `os error 433`, le volume disparaît en cours d'écriture (§1). |

**En revanche, paralléliser est SÛR pour les validations** : deux sessions pytest
simultanées à cache chaud coûtent **+7 %** et font gagner **37 %** de wall-clock.
Le 🔴 du §0 de `REPRISE_PERF.md` est démenti. Jamais pour les mesures.

## 0.4 Ce qui est prouvé, et ce qui ne l'est pas

| Affirmation | Statut |
|---|---|
| Facteurs machine : oracle ×1,46 · FIELD ×2,0 · INDEX ×0,97 · INDEX_SPLINE ×5,9 · STRAT ×2,4-3,2 | ✅ **mesuré** |
| Le cache numba n'est pas dans `%TEMP%` mais dans les `__pycache__` | ✅ **artefact** (78 `.nbi`) |
| Le warmup colorimétrie était mort | ✅ **artefact** (`.nbi` absents puis apparus) |
| INDEX et STRAT n'avaient aucun ancrage de correction | ✅ **corrigé et vérifié** |
| Parallélisme des validations sans blocage | ✅ **mesuré** |
| **Gain de `compute_layer_profile` (`190a37d`)** | ❌ **NON MESURÉ** — mécanisme vérifié, volume non |
| **Sur-souscription (`e9221b8`)** | 🔴 **MESURÉ — c'est une RÉGRESSION de 5 à 7 % sur STRAT**, 4 paires sur 4 (§14) |
| Le mécanisme du §4.5 (`use_cache` non sûr) | ⚠️ **non recoupé** — issu d'un agent dont les vérificateurs sont tombés |
| Les constats du §10 sans ✅ | ⚠️ **non vérifiés** |

---

## 1. Ce qui a changé dans l'environnement

Trois variables ont bougé **en même temps**. Aucune comparaison avant/après ne
peut enjamber cette session.

| | Avant | Maintenant |
|---|---|---|
| Emplacement | `G:\Mon Drive\...\CERTUS\0108` (Google Drive) | **`C:\dev\CERTUS\0108`** (disque local) |
| Machine | 16 cœurs | **i5-8250U, 4 cœurs / 8 threads, 15 W, 8 Go** |
| numba / llvmlite | 0.65.1 / 0.47.0 | **0.66.0 / 0.48.0** |
| scipy | 1.17.1 | **1.18.0** |
| Python | 3.14.6 | 3.14.6 (inchangé, c'est la dernière stable) |
| uv | 0.10.6 et 0.11.14 | **0.12.1** |

### Pourquoi le projet a déménagé

Le venv ne peut **pas** vivre dans Google Drive File Stream. Mesuré :

- `uv pip install` a échoué sur `os error 433` — le volume `G:` a disparu en
  cours d'écriture, emportant l'interpréteur.
- uv signale `Failed to hardlink files; falling back to full copy` : le cache uv
  est sur `C:`, la cible était sur `G:`. Chaque fichier était recopié en entier.
- Débit d'écriture mesuré : **24,4 Mo/min vers Drive contre 99,7 Mo/min en
  local**, sur un arbre de milliers de petits fichiers.
- L'ancien `.venv` était de toute façon mort : son interpréteur de base
  `C:\Python314` n'existe plus (trampoline cassé).

Drive reste la sauvegarde : instantané `G:\Mon Drive\couches minces 2026\CERTUS\0308`,
6 894 fichiers, dépôt git valide, **sans `.venv`** — ne jamais l'y recopier.

### Reconstruire l'environnement

```bat
cd /d C:\dev\CERTUS\0108
uv sync --extra dev --extra freeze
```

`uv sync` et **pas** `uv pip install -r requirements.lock` : ce dernier
n'installe pas le projet lui-même, et le check n°1 du §0 de `REPRISE_PERF.md`
échoue alors silencieusement.

---

## 2. Facteur machine — mesuré, partiellement

Le seul chiffre **propre** est celui de l'oracle, mesuré machine au repos :

| | Réf. doc (16 cœurs) | Ici | Facteur |
|---|---|---|---|
| `pytest tests/oracle/ -q --no-cov`, cache chaud | 8 s | **11,71 s** | **×1,46** |
| idem, cache numba froid | — | 104,60 s | — |

⚠️ **Ne généralise pas ce ×1,46.** L'oracle est court et essentiellement
mono-thread. Il ne dit rien de DESIGN (873 % de CPU) ni de STRAT (691 %), qui
exploitent réellement 16 cœurs sur la machine d'origine.

### Bancs rapides — mesure PROPRE, machine au repos

Deux passes par module, `--auto-yes`, aucun autre processus (vérifié : 0 python
actif au départ). Valeur retenue = seconde passe, cache chaud.

| Module | Réf. doc | `RUN_S` ici | Facteur |
|---|---|---|---|
| FIELD | 0,06 s | **0,119** | ×2,0 |
| INDEX_SPLINE | 1,6 s | **9,431** | **×5,9** ⚠️ |
| INDEX | 12,8 s (voir §4) | **12,425** | **×0,97** |

**Sur INDEX, cette machine est à parité avec la 16 cœurs.** Ce qui s'explique :
le cache `.nbi` de la machine d'origine vivait dans le dossier Google Drive
(§10.1), son INDEX était donc ralenti par les I/O Drive autant que le nôtre l'est
par un CPU plus lent.

⚠️ **INDEX_SPLINE à ×5,9 est désormais le seul vrai écart, et il est inexpliqué.**
C'est la prochaine question à instruire, et elle est peu coûteuse : le module
tourne en ~10 s.

### Pourquoi la série précédente était fausse — à titre d'avertissement

Une première passe, lancée pendant qu'un robocopy vers Drive et des agents de
lecture tournaient, donnait FIELD 0,216 · INDEX_SPLINE 12,188 · **INDEX 81,521**.
Soit un facteur **6,6** sur INDEX par rapport à la mesure propre.

La contamination était détectable dans la série elle-même : `RUN_S` d'INDEX_SPLINE
descendait de 17,898 à 12,188 s pendant que le wall-clock **montait** de 26,65 à
33,74 s. Calcul qui accélère et processus qui ralentit = interférence externe.

🔴 **Ne jamais mesurer avec quoi que ce soit d'autre en vol.** Sur 4 cœurs, l'écart
n'est pas de quelques pourcents, il est d'un ordre de grandeur.

### Coût fixe par processus

Le wall-clock dépasse toujours `SETUP_S + RUN_S` de **7 à 8 s** même à cache
chaud : c'est Qt et les imports, hors des compteurs du banc. À froid ce surcoût
monte à ~33 s (FIELD : 42,59 s de wall pour 2,0 s comptés). Toute campagne doit
en tenir compte : un banc de 10 s coûte 18 s de processus.

### Le JIT est plus cher qu'avant

Mesuré sur l'oracle : compilation à froid **60,6 s → 104,6 s** (+73 %) entre
numba 0.65.1 et 0.66.0. Conséquence directe : la piste **§4.2** de
`REPRISE_PERF.md` (noyaux non couverts par `warmup_physics()`) a **gagné** en
rentabilité, elle n'en a pas perdu.

Hypothèse **non vérifiée** à tester en priorité : si les ratios ×7 à ×12
ci-dessus survivent à une mesure propre, ils sont trop grands pour un simple
écart 4 cœurs contre 16 sur du mono-thread. Suspect n°1 : un `cache=True`
devenu inopérant sur les décorateurs numba après la montée de version, qui
ferait recompiler à chaque run.

---

## 3. 🔴 Le banc INDEX n'a aucun ancrage de correction

`scripts/bench_examples.py` sort `RESULT`, défini dans sa docstring comme la
grandeur physique permettant de vérifier qu'une optimisation n'a pas changé le
résultat. **Sur INDEX, `RESULT` vaut `None`.**

Ce n'est pas un échec de run : le code de sortie est 0, aucune trace, et
`RUN_S` vaut bien 81 s — le worker a tourné et rendu quelque chose.

La chaîne fautive, dans `scripts/bench_examples.py:455`:

```python
worker = getattr(app, "worker", None) or getattr(app, "_worker", None)
res = wait_for(worker) if worker else None
val = getattr(res, "rmse_final", None) if res is not None else None
if val is None and isinstance(res, dict):
    val = res.get("rmse")
```

✅ **CORRIGÉ.** Ma première hypothèse (une charge `list`) était fausse. La cause
réelle : `run_optimization` emploie `OptimizationWorker`
(`certus/ui/certus_index_ui_worker.py:264`), dont le signal `finished` émet un
**`OptimizationResults`** (`certus/core/certus_index_config.py:261`). Or cette
classe expose **`final_mse`**, pas `rmse_final` — et elle porte `__slots__`, donc
elle n'a pas de `__dict__` et le repli `isinstance(res, dict)` ne pouvait pas
aboutir non plus. **Les deux branches d'extraction échouaient.**

Le banc lit désormais `final_mse` et prend la racine, conformément à
`calculate_index_rmse` (`certus/utils/certus_index_utils.py:1109`) et à la
convention des autres runners (`float(r.fun) ** 0.5`).

### 3.1 🔴 Ce que la réparation a révélé : INDEX est DISPERSIF

Deux passes consécutives, exemple identique, machine au repos :

| Passe | `RESULT` | `RUN_S` |
|---|---|---|
| 1 | 0,002568007655588442 | 11,095 s |
| 2 | 0,0027806293789642065 | 8,068 s |

**8 % d'écart sur le RMSE, 27 % sur le temps.** La règle 2 du §1 de
`REPRISE_PERF.md` ne met en garde que sur DESIGN et STRAT : **elle s'applique
aussi à INDEX**. Personne ne pouvait le savoir tant que le banc rendait `None`.

⚠️ **Conséquence** : `RESULT` est un ancrage **statistique**, pas une égalité
exacte. Valider la piste §10.6 (float32 → float64) en comparant deux runs isolés
donnerait un verdict au hasard.

### 3.2 ✅ `random_seed` était inopérant sur deux échantillonneurs sur quatre

`certus/core/certus_index_solvers.py` : Sobol reçoit bien
`seed=... self.random_seed ...` (`:245`) et le repli `uniform` utilise `self._rng`
correctement initialisé (`:319`). Mais **`Halton` (`:296`) et `LatinHypercube`
(`:309`) ne recevaient aucune graine** — `random_seed` y était silencieusement
ignoré. Corrigé : les quatre chemins l'honorent désormais.

Ce n'est pas nécessairement *la* cause de la dispersion ci-dessus (le chemin
emprunté dépend de `method`), mais **il était impossible de rendre INDEX
reproductible même en fixant la graine**.

### 3.3 Ce qui manque encore

Le banc **n'expose pas** de `--seed`. La configuration étant construite à
l'intérieur de l'interface, l'ajouter touche les huit modules. C'est le chaînon
manquant pour rendre INDEX comparable d'un run à l'autre, et donc la piste §10.6
réellement vérifiable.

---

## 4. ✅ TRANCHÉ — la référence INDEX du document est fausse d'un facteur 2

Le §2 de `REPRISE_PERF.md` donne INDEX à **6,5 s** et le §6 titre
« INDEX (6,5 s, avec `--auto-yes`) ». Mais le corps du même §6 explique que le
« No » par défaut fait sauter la phase IR et fait tomber le run **de 12,8 s à
6,5 s**. Les deux lectures étaient incompatibles.

**La mesure tranche : `--auto-yes` donne 12,425 s ici.** C'est donc le corps du
texte qui a raison — 12,8 s est la mesure `--auto-yes`, 6,5 s celle sans.

Conséquences :

1. **Le titre du §6 est faux** : ce n'est pas « 6,5 s avec `--auto-yes` ».
2. **La ligne INDEX du tableau du §2 mesure le demi-pipeline**, exactement ce que
   le §6 dénonce trois pages plus loin (« on mesurait la moitié du pipeline »).
   La bonne référence est **12,8 s**.
3. Le facteur machine d'INDEX n'est donc pas ×1,9 mais **×0,97 — la parité**.

---

## 5. Corrections à REPRISE_PERF.md

1. **§4.3, « le dépôt vit dans un dossier Google Drive » — obsolète.** Le dépôt
   est sur disque local. L'hypothèse Drive pour expliquer les 18,6 % de
   `_path_stat` d'INDEX et les 23 % d'INDEX_SPLINE doit être **re-testée**, pas
   supposée. Si les pourcentages s'effondrent, la piste est close sans écrire une
   ligne ; s'ils tiennent, les imports tardifs sont bien en cause.
2. **§0, « warning: ignoring broken ref refs/heads/desktop.ini » — disparu.** La
   ref cassée n'a pas survécu au rapatriement. Le commit orphelin `01047a1b`
   reste, lui : `fatal: bad tree object` continue de s'afficher à chaque commit,
   qui réussit quand même.
3. **§3, tous les gains mesurés (`33af845` −61 %, `2572f46` −29 %, `f6f9102`
   −11 %) datent de numba 0.65.1 et de 16 cœurs.** Ils ne sont pas invalidés,
   mais ils ne sont plus reproductibles ici en l'état.
4. ~~**`2572f46` est suspect sur cette machine.**~~ ❌ **J'avais tort — voir §10.4.**
   La lecture du code montre que son réglage (`certus/physics/certus_optimizers.py:892`)
   est **adaptatif**, pas en dur, et reste pertinent sur 4 cœurs. La
   sur-souscription réelle est ailleurs, et elle est bien plus large que ce
   commit.

---

## 6. Verrous de dépendances — piège à connaître

`pyproject.toml` épingle `pydantic>=2.14.0a1`, une **préversion**. Conséquence :

- `uv pip compile` bascule en mode préversions pour **tout le graphe** et tire
  `numba 0.67.0rc1`, `llvmlite 0.49.0rc1`, `numpy 2.5.1` — jamais testés.
- Or `.github/workflows/release-windows.yml:31` fait
  `pip install -r requirements.lock` : une release aurait été construite dessus.

**`requirements.lock` est désormais généré par `uv export`**, pas par
`uv pip compile` :

```bat
uv export --extra dev --extra freeze --no-emit-project -o requirements.lock
```

Il reflète ainsi exactement `uv.lock`, c'est-à-dire ce qui est installé et ce que
l'oracle a validé. **N'utilise plus la commande inscrite dans l'ancien en-tête du
fichier.**

Effet de bord favorable : `uv export` produit les hashes. Le fichier en compte
441, là où il n'en avait **aucun** — ce qui faisait échouer l'étape
« Verify lockfile hashes » de `release-windows.yml` pour la totalité des paquets.
Ce job était rouge, il ne devrait plus l'être.

---

## 7. État git et auto-push

- Branche `refactor-corridors-mixins`, alignée sur `origin`.
- `fdb3a74` — verse 67 fichiers de travail non commité (moteur rust, audit, rapports).
- `726403d` — remontée des dépendances et réparation des hashes.
- 🔴 **`.git/hooks/post-commit` est RÉARMÉ.** Chaque commit pousse
  automatiquement vers le dépôt **public** `nikonvr/CERTUS`, en arrière-plan.
  Le log est dans `logs/git_auto_push.log`.
- Le hook lance le push avec `&` : **un échec est silencieux**. Il a d'ailleurs
  échoué une fois ici (`could not read Username`, pas de terminal interactif).
  Vérifier `git status -sb` et le log, ne pas se fier au message du hook.
- `.env` est bien ignoré (`.gitignore:26`) et non suivi.

---

## 8. Ce qui reste à faire

✅ **Faits** : bancs rapides remesurés au repos (§2) · extraction `RESULT` réparée
sur INDEX **et** STRAT (§3, §11.2) · ambiguïté 6,5 / 12,8 s tranchée (§4) ·
sur-souscription corrigée (§11.3) · `ab_compare.sh` étendu au multi-fichiers (§11.1).

**Restent, par ordre :**

1. 🔴 **Prouver les deux changements de performance non mesurés** —
   `compute_layer_profile` (`190a37d`) et la sur-souscription (`e9221b8`). Aucun
   des deux n'a de gain démontré. C'est une dette, pas un acquis.
2. **Contrôler l'ancrage `RESULT` des quatre modules non vérifiés** :
   `metal_single`, `metal_bilayer`, `re`, `design`. Deux modules sur les quatre
   déjà contrôlés étaient cassés — la probabilité que les autres le soient n'est
   pas faible. Le `WARN` du banc (§11.2) le signale désormais au premier run.
3. **INDEX_SPLINE à ×5,9**, seul écart machine encore inexpliqué (§2).
4. **§4.2 — le float32 de `certus_index_solvers.py:255`**, à ne tenter qu'après
   avoir exposé une graine dans le banc : INDEX est dispersif à 8 % (§3.1).
5. **§4.1 — le tirage PGLOBAL**, dont le protocole coûte des nuits ici.

⚠️ **Ne PAS faire** : basculer `use_cache=True` (§10.3, non sûr, mécanisme établi).

### Règle de mesure — corrigée le 2026-08-04

~~🔴 Une seule session de calcul à la fois.~~ **Mesuré, c'est plus subtil :**

- **Paralléliser des VALIDATIONS** (oracle, tests unitaires, lint) : ✅ sûr.
  Deux sessions pytest simultanées à cache chaud coûtent **+7 %** et font gagner
  **37 %** de wall-clock. Le 🔴 du §0 de `REPRISE_PERF.md` était faux, et sa cause
  invoquée — le verrou du cache numba via `configure_numba_env` — ne pouvait pas
  l'être puisque cette fonction ne pose jamais `NUMBA_CACHE_DIR` (§10.1).
- **Paralléliser des MESURES** : ❌ jamais. INDEX affichait `RUN_S` **81,5 s** en
  environnement chargé contre **12,4 s** au repos. Sur 4 cœurs, la charge
  concurrente n'ajoute pas du bruit, elle invente un résultat.

---

## 9. Analyse statique du §4.4 — la prémisse du document est fausse

Issu d'une analyse parallèle dont **16 agents sur 17 ont été tués par une limite
de quota**. Un seul a abouti, sur le §4.4, et ses dix vérificateurs sont morts
avec les autres.

⚠️ **Statut : NON VÉRIFIÉ**, sauf les trois lignes contrôlées à la main et
marquées ✅ ci-dessous. Tout le reste est à recouper avant d'agir.

### 9.1 Le gisement n'est pas là où le document le dit

Le §4.4 de `REPRISE_PERF.md` désigne la liste réfléchie numba
(`extrema_d = []`, `certus/physics/certus_strat_math.py`) comme le problème.
La lecture du code dit autre chose : cette liste ne représente que **2 des 6
allocations NRT** par appel et ne contient en pratique que **0 à 2 éléments**.
Le coût réel de la fonction, ce sont les **56 à 88 évaluations** de
`_calc_T_added_layer`, chacune avec `cos`/`sin` sur argument complexe.

Le vrai gisement est ailleurs, et il est bien plus gros. Le bloc de profil
théorique de `certus/core/certus_strat_robustness.py:624-658` est **calculé puis
jeté** par deux des trois familles d'appelants :

- rescoring consensus (`robustness.py:951`) ne lit que `robustness_score` ;
- successive halving ELITE (`certus_strat_consensus.py:570`) ne lit que
  `results_per_noise[].rmse_p95`.

✅ Vérifié à la main : `final_score` est calculé en `:622`, **avant** le bloc, qui
démarre en `:624` par `extrema_dist_info = []` et boucle
`for i_layer in range(num_layers)`.

Or c'est exactement là que vivent **les deux lignes les plus chères** du profil
post-`33af845` du document : `certus_strat_objectives.py:489`
(`compute_T_front_profile`, 107,2 %) et `:497` (`calculate_extrema_distances`,
106,7 %). Volume estimé : **~500 tâches × 48 couches ≈ 25 000 appels inutiles**
par run, sur chacune des deux fonctions.

**Action proposée** — ajouter `compute_layer_profile: bool = True` à
`_test_strategy_robustness_task` (`robustness.py:448`), englober les lignes
624-658 dans `if compute_layer_profile:`, et passer `False` aux **deux seuls**
sites qui jettent le résultat : `robustness.py:951` et `consensus.py:570`.
Surtout **pas** en `consensus.py:621` (évaluation complète, dont
`full_res['strategy']` est réutilisé en `:648`) ni dans
`_execute_robustness_tasks`. Le défaut `True` préserve tout appelant non modifié.

### 9.2 ✅ Sur-souscription de threads confirmée — à corriger AVANT toute mesure

Vérifié à la main dans `certus/core/certus_strat_robustness.py` :

- `:314` → `max_workers = max(1, multiprocessing.cpu_count() // 2)`
- `:466` → `numba.set_num_threads(2)` en tête de **chaque** tâche

Sur l'i5-8250U, `cpu_count()` renvoie 8 (SMT), donc `max_workers = 4`, soit
**4 × 2 = 8 threads numba pour 4 cœurs physiques à 15 W**. Le réglage `2` a été
choisi sur une machine 16 cœurs.

🔴 **C'est un prérequis, pas une optimisation.** Une sur-souscription ×2 sur un
15 W se paie en throttling thermique, ce qui **bruite toutes les mesures A/B**.
Le corriger après avoir lancé les campagnes invaliderait les campagnes.
Piste : baser `max_workers` sur les cœurs **physiques** plutôt que sur
`cpu_count()`. Vérifier aussi `get_safe_worker_count()` (`:944`), autre chemin.

### 9.3 Le `.tolist()` du §4.4 exige un commit préalable défensif

Retirer les `.tolist()` (`robustness.py:595` et `:614`) casserait **quatre**
tests de véracité, dont **deux silencieusement** — `if thicknesses_all:` sur un
ndarray 2D lève `ValueError`, avalée par le `except` englobant :

| Site | Effet |
|---|---|
| `certus/ui/certus_strat_thickness_ui.py:402` | 🔇 silencieux — stats par couche vides |
| `certus/ui/certus_strat_table_ui.py:164` | 🔇 silencieux — colonne en erreur tronquée |
| `certus/core/certus_strat_robustness.py:1081` | échec franc |
| `certus/utils/certus_strat_service.py:1220` | échec franc |

C'est le mode de défaillance de `bc2042a` (§3 du document : 278 évaluations
fausses sur 48 000, sans erreur visible). **Faire d'abord un commit séparé et
neutre** remplaçant les 4 tests par `is None or len(...) == 0`, puis seulement
basculer le producteur. Gain CPU estimé faible (~1-3 %), mais ~4× en mémoire —
ce qui compte sur 8 Go.

### 9.4 Deux pièges signalés

- **Docstring fausse**, `certus_strat_math.py:121` : elle annonce 200 nm de
  portée, le code balaie ±16 nm de **chemin optique**, soit ±16/|n| nm physiques
  (±6,96 nm pour Nb₂O₅, ±10,96 nm pour SiO₂). Erreur d'un facteur 12 à 29.
- **Ne pas réduire `scan_ot`** (`certus_strat_math.py:129`, valeur 16.0) en
  croyant faire une optimisation iso-résultat. Le terme `balance` de
  `_compute_local_extrema_symmetry_score`
  (`certus/utils/certus_strat_context.py:264-265`) utilise les distances brutes,
  pas saturées : tronquer le scan **change le classement des stratégies**.

---

## 10. Analyse statique — 5 pistes restantes

Seconde vague de fan-out. Les 5 analyses ont abouti ; **les 4 vérificateurs et la
synthèse ont été tués par le quota**. Statut par défaut : **NON VÉRIFIÉ**, sauf
✅ = contrôlé à la main dans cette session.

### 10.1 ✅ Le cache numba n'a JAMAIS été dans `%TEMP%` — le §4.3 dit le contraire

`REPRISE_PERF.md` §4.3 affirme, en gras et avec un ⚠️, que `configure_numba_env`
place déjà le cache dans `%TEMP%\CERTUS_Numba_Cache`, hors du dossier synchronisé,
et conclut « ne repars pas sur cette piste ».

**C'est faux, et l'instruction de ne pas creuser était donc infondée.**

`configure_numba_env` ne pose `NUMBA_CACHE_DIR` qu'en `certus/core/certus_core.py:359-361`,
mais la branche de `:334` (`if "numba" in sys.modules ...`) **retourne en `:352`
avant d'y arriver**. Or `scripts/bench_examples.py:443` fait `import certus_physics`
— qui importe numba — **avant** la ligne `:444` qui importe `CERTUS_INDEX`, seul
endroit appelant `_configure_numba_env()`. La branche est donc toujours prise.
`tests/conftest.py` ne pose rien non plus.

Aggravant, lu dans numba 0.66 installé : le locator de cache est figé **à la
décoration**, pas à la compilation (`numba/core/caching.py:414-420`). Poser la
variable après le premier import `@njit` est sans effet de toute façon.

✅ **Vérifié à la main :**

| Contrôle | Résultat |
|---|---|
| `%TEMP%\CERTUS_Numba_Cache` | **n'existe pas** |
| `.nbi` dans les `__pycache__` du dépôt | **58 fichiers** |

Le cache JIT vit donc **à côté des sources** — c'est-à-dire, avant le
rapatriement, **dans le dossier Google Drive**. Les 18,6 % / 23 % de `_path_stat`
du §4.3 étaient très probablement ce cache lu à travers Drive.

⚠️ **Conséquence de mesure** : le banc et l'application n'utilisent pas le même
répertoire de cache. Un « cache chaud » mesuré par `bench_examples.py` ne dit
rien du cache de `python CERTUS_INDEX.py`, qui n'a jamais été peuplé ici.

### 10.2 §4.3 — la mesure elle-même est l'artefact

`scripts/bench_examples.py:687` : **la fenêtre d'échantillonnage englobe l'import
de l'application**. Les 18,6 % et 23 % de `_path_stat` ne sont donc **pas du temps
de calcul** — c'est le chargement des modules, compté dans le profil.

La piste « remonter les imports tardifs » ne peut pas rapporter ce que le §4.3
espère. Ce qui reste, plus modeste mais réel :

- `certus/spline/spline_workers.py:789` — **4 à 5 imports par évaluation
  L-BFGS-B**, tous redondants avec le bloc d'en-tête. Supprimables sans risque.
- `certus/core/certus_index_solvers.py:240` — le seul import tardif d'INDEX
  capable de produire un vrai `_path_stat` pendant le run.
- `certus/workers/certus_index_workers.py` — les 11 imports tardifs sont **NON
  déplaçables**, cycle d'import prouvé. Ne pas y toucher.

### 10.3 §4.5 RÉSOLU — `use_cache=True` n'est PAS sûr, et on sait pourquoi

La question ouverte du document trouve sa réponse, et **ce ne sont pas les
1,78e-15 de réassociation flottante**. C'est une **perte d'information dans la clé
de cache**.

`SplineBasisCache.get` arrondit les positions de nœuds à **6 décimales** pour
construire sa clé (`certus/physics/certus_optical_models.py:419`). Les longueurs
d'onde de METAL sont en **nanomètres** (`CERTUS_METAL_SINGLE.py:1256` :
`knot_l = np.array([400.0, 800.0])`). Le quantum de la clé vaut donc **1e-6 nm**,
soit **100× le pas de différence finie de L-BFGS-B (1e-8)**.

**La perturbation du gradient est exactement annulée par l'arrondi de la clé.**
L'optimiseur calcule des dérivées sur un objectif devenu localement constant.

Trois corollaires, tous ancrés :

- `certus_optical_models.py:453` — la matrice stockée n'est pas reconstruite à
  partir de la clé : l'objectif devient **dépendant de l'historique du cache**,
  donc non reproductible d'un run à l'autre.
- `tests/oracle/test_spline_basis_cache.py:46` — le garde-fou censé attraper
  exactement ce bug **ne peut pas le voir** : il déplace les nœuds de 1e-4, soit
  100× le quantum de la clé.
- `scripts/bench_examples.py:307` — **le 55,9 s → 24,7 s ne mesure pas ce que le
  §4.5 propose** : `--force-cache` patche globalement, y compris des sites que le
  plan ne prévoit pas de basculer. Le gain annoncé n'est pas celui de l'action.

Même pathologie ailleurs, en pire : `certus/utils/certus_re_math.py:396` arrondit
les nœuds à 0,1 nm et la grille à 1 nm — quantum **100 000× plus grossier**.

**Conclusion : ne pas basculer `use_cache=True` en l'état.** Les sites où les
positions de nœuds sont figées sont immunisés ; ceux où elles varient ne le sont
pas.

### 10.4 La sur-souscription est systémique, pas locale

> **AUCUN endroit du dépôt ne connaît la notion de cœur physique.** Pas de
> `psutil`, pas de `cpu_count(logical=False)`. 100 % des décisions de
> parallélisme dérivent de `os.cpu_count()` / `multiprocessing.cpu_count()`, qui
> vaut **8** ici. Le facteur 2 du SMT est donc **systématique**.

| Fichier:ligne | Constat |
|---|---|
| `certus/core/certus_core.py:226` | `get_safe_worker_count()` rend **7 workers** pour 4 cœurs physiques ; `_RESERVED_CORES_FOR_WORKERS` a son adaptativité **inversée** |
| `certus/core/certus_core.py:379` | `NUMBA_NUM_THREADS` = logiques − 1 = **7 threads OMP par noyau** |
| `certus/core/certus_strat_consensus.py:525` | **Trois autres sites** du type de `:314`, et pires : 7 workers × 2 threads numba |
| `certus/core/certus_index_solvers.py:511` | Le garde-fou anti-sur-souscription de PGlobal est posé **sur le mauvais thread** — `set_num_threads` avant création du pool, le masque n'atteint aucun worker : **inerte** |
| `certus/core/certus_re_solvers.py:174` | RE : **deux pools imbriqués à 8 threads chacun**, aucun bridage numba sur tout le chemin |
| `certus/workers/certus_field_workers.py:308` | Deux pools non bornés, et un noyau défini en double |
| `certus/physics/certus_optimizers.py:892` | ✅ `2572f46` est **adaptatif** et reste pertinent — **corrige le §5.4 ci-dessus, où j'avais tort** |

### 10.5 ✅ Le bloc colorimétrie de `warmup_physics` est mort depuis des années

`certus/core/_certus_physics_impl.py` : `:1419` construit `wls` sur **50 points**,
`:1490` construit `R_test` sur **10 points**, et `:1492` fait
`np.interp(CIE_LAMBDA, wls, R_test)` → `ValueError`, avalée par le
`except RuntimeError, ValueError:` de `:1502`. Tout ce qui suit dans le bloc n'est
jamais compilé.

✅ **Vérifié par artefact disque** — les `.nbi` présents sont exactement ceux des
appels situés **avant** la ligne 1492 (`_lab_f`, `_lab_f_inv`,
`_gamma_correct_scalar`), et il n'existe **aucun** `.nbi` pour
`_xyz_from_spectrum_kernel` ni `delta_e_2000`. La coupure sur disque tombe
précisément au point de rupture.

Correctif : `R_test = np.full(len(wls), 0.5, dtype=np.float64)`. Gain nul sur
INDEX (la colorimétrie n'est pas sur le chemin chaud) — l'intérêt est
méthodologique : **un bloc de warmup peut mourir sans le moindre bruit**, et la
présence du `.nbi` est un contrôle qui ne coûte aucun calcul.

### 10.6 §4.2 — l'hypothèse prioritaire est infirmée, la vraie cause est ailleurs

Un balayage AST des **111 fonctions `@njit`/`@jit`** du paquet `certus` montre
qu'**elles portent toutes `cache=True`**, sans exception. Aucun cache n'a été
perdu avec numba 0.66 : mon hypothèse était fausse.

La vraie cause du JIT pendant le run est ✅ `certus/core/certus_index_solvers.py:255` :
`X = np.empty((n, self.dim), dtype=np.float32)`. Les échantillons partent en
**float32** vers `TLUObjective.__call__` (`certus_index_objectives.py:1755`, les
54 % du profil), tandis que la phase locale scipy repasse en **float64**. numba
compile donc **deux signatures** du chemin chaud, et `warmup_physics` — qui ne
passe que des float Python — n'en couvre qu'une. Une **troisième** variante
`readonly` existe, produite par l'idiome `np.frombuffer(clé_en_octets)` des caches
lru (`certus_optical_models.py:534-536`, `spline_objective.py:33`).

Corroboré par `pickletools` sur les `.nbi` : 2 à 3 `.nbc` par fonction
(`epsilon2_TLU_array`, `epsilon1_TL_analytic`, `calculate_RT_single_layer_backside_array`).

> **Ce ne sont pas des noyaux oubliés, ce sont des SIGNATURES oubliées sur des
> noyaux déjà réchauffés.**

⚠️ Passer `:255` en float64 change le pas d'échantillonnage, donc la trajectoire
de l'optimiseur. **À ne tenter qu'après réparation de l'extraction `RESULT` du
banc INDEX (§3)** — sinon c'est un changement numérique sans filet.


---

## 11. L'outillage de mesure était cassé sur trois points

C'est le résultat le plus important de la session, et il n'était pas cherché.
**Avant de mesurer quoi que ce soit sur ce dépôt, vérifie l'instrument.**

### 11.1 `ab_compare.sh` n'alternait qu'UN fichier

Le script ne prenait qu'un `$FILE`. Or `compute_layer_profile` (`190a37d`) en
touche deux, et la sur-souscription (`e9221b8`) en touche sept.

🔴 **Le piège n'était pas théorique.** En basculant `certus_strat_robustness.py`
seul vers la référence, l'ancienne signature n'accepte pas le mot-clé mais
`certus_strat_consensus.py` continue de le passer : soit un `TypeError`, soit —
bien pire — des candidats **silencieusement écartés** par le `except` englobant et
un bras « SANS » artificiellement rapide. On aurait mesuré un gain spectaculaire
et entièrement faux.

Le premier argument accepte désormais une liste séparée par des virgules.
**Deux défauts latents ont été trouvés en chemin :**

1. La restauration passait par `git checkout HEAD -- "$FILE"`, alors que l'en-tête
   documente `<ref-git> = HEAD` pour un changement encore dans l'arbre de travail.
   Dans ce cas le bras « AVEC » **détruisait le changement à mesurer**.
2. `git show "$REF:$FILE" > "$FILE"` **tronquait le fichier avant** que git ne
   s'exécute : un `show` en échec laissait un fichier vide dans le dépôt.

Le trap couvre maintenant les N fichiers — vérifié par SIGINT (sortie 130) et
SIGTERM (sortie 143), fichiers restaurés, `git status` propre.

### 11.2 🔴 Deux modules sur huit n'avaient AUCUN ancrage de correction

`RESULT` valait `None` sur **INDEX** et sur **STRAT** — précisément les deux plus
gros chantiers du §4 de `REPRISE_PERF.md`. Le banc sortait la ligne sans rien
signaler. **N'importe qui pouvait « optimiser » ces modules, constater un gain, et
publier un résultat faux sans qu'aucun garde-fou ne bronche.**

| Module | Cause réelle |
|---|---|
| INDEX | `OptimizationResults` expose `final_mse`, pas `rmse_final`, et porte `__slots__` — donc le repli `isinstance(res, dict)` ne pouvait pas aboutir non plus. Les **deux** branches d'extraction échouaient. |
| STRAT | La charge utile est le `to_legacy_dict()` d'un `WorkerThreadResult` : un dict à deux clés, `final_results` et `opti_results`. Le RMSE n'y figure pas — la clé `"rmse"` appartient à `metadata`, qui part vers un **autre signal**, `excel_ready`. Il se dérive de `final_results["all_strategies_results"]` via `extract_best_rmse`. |

✅ **Le correctif qui compte le plus** : le banc émet désormais un `WARN` explicite
quand `RESULT` est `None`, disant que le module n'a aucun ancrage et qu'il ne faut
rien conclure d'un A/B sur lui.

> Un outil de mesure qui rend silencieusement une valeur vide est pire qu'un outil
> qui plante : il donne l'illusion d'une vérification.

⚠️ **`metal_single`, `metal_bilayer`, `re` et `design` n'ont PAS été contrôlés.**
Deux des quatre modules vérifiés étaient cassés. Le `WARN` le dira au premier run.

### 11.3 La sur-souscription était systémique

**Aucun endroit du dépôt ne connaissait la notion de cœur physique** : 100 % des
décisions de parallélisme dérivaient de `cpu_count()`, qui compte les processeurs
**logiques**. Sur une puce SMT, le facteur 2 était donc systématique.

Threads réels, pour `cpu_count() = 8` et 4 cœurs physiques :

| Site | Avant | Après |
|---|---|---|
| `NUMBA_NUM_THREADS` | 7 | **3** |
| STRAT `robustness.py:314` | 4 × 2 = **8** | **4** |
| STRAT `consensus.py:525` (2 pools) | 7 × 2 = **14** | **4** |
| STRAT `robustness.py:962` | 7 × 2 = **14** | **4** |
| PGlobal INDEX | 7 × 7 = **jusqu'à 49** | 7 × 1 = **7** |
| RE phases 1 et 2a | 8 chacune | **4** |
| FIELD, deux pools | 12 chacun | **4** |

`get_physical_core_count()` a été ajoutée dans `certus/core/certus_core.py`, **sans
nouvelle dépendance** (`kernel32` via `ctypes` sous Windows, `thread_siblings_list`
sous Linux). Repli documenté : en cas d'échec elle rend le compte **logique**,
c'est-à-dire exactement l'ancien comportement.

**Deux constats de l'analyse ont été RÉFUTÉS par la lecture, et non appliqués :**

- `get_safe_worker_count()` n'a pas son adaptativité « inversée » : la réserve vaut
  12,5 % dans les deux cas. Sa valeur n'a pas été changée car `self.n_workers`
  alimente `n_dispatch = min(len(cand_y), n_workers)` dans PGlobal INDEX : c'est un
  paramètre **algorithmique**, qui décide combien de candidats reçoivent un
  raffinement L-BFGS-B. Le modifier changerait la trajectoire de recherche.
- Les deux pools de RE ne sont **pas imbriqués mais séquentiels**.

⚠️ **Risque numérique assumé.** Un balayage AST trouve exactement deux noyaux
`@njit(parallel=True)` portant une réduction inter-`prange`, seule construction
dont le résultat dépend du nombre de threads : `compute_mse_vectorized` (chemin
chaud d'INDEX) et `_compute_metal_tmm_gradient_kernel`. Les changements de nombre
de threads **numba** peuvent les déplacer de quelques ulps. Jugé acceptable : cette
valeur était déjà dépendante de la machine (15 sur la 16 cœurs), des résultats
identiques au bit près entre machines n'ont jamais été une propriété de ce code, et
l'oracle passe. Les changements de nombre de **workers** sont du pur ordonnancement
et ne peuvent rien déplacer.

**Non traités, signalés** : `certus/core/certus_runtime.py:24` (pose OMP/OPENBLAS/MKL
depuis `cpu_count()` — toucher aux threads BLAS déplacerait les réductions BLAS) et
`certus/physics/certus_optimizers.py:687` (dérive encore 6 workers de `cpu_count()`).

---

## 12. STRAT — première mesure sur cette machine

| Réf. doc (16 cœurs) | Ici (`RUN_S`) | Facteur |
|---|---|---|
| 47–64 s | **126,3 à 152,5 s** | **×2,4 à ×3,2** |

Six runs consécutifs, machine au repos : 152,5 · 126,3 · 140,5 · 131,2 · 129,6 ·
130,7 s. **Dispersion ≈ 17 %**, cohérente avec les 47–64 s du document.

Conséquence directe : **compter les paires gagnantes, jamais moyenner.** Une
moyenne sur quatre runs ne distinguerait pas un gain réel de 10 % du bruit.

Coût de campagne : 4 paires ≈ **20 minutes**. C'est tenable, contrairement à ce que
je craignais.

`RESULT` de référence après réparation : **0,02519543055680181**.

---

## 13. Leçon de méthode — mesurer aussi le diagnostic

Le document d'origine martèle « ne jamais annoncer un gain sans l'avoir mesuré ».
Cette session montre que **la même règle vaut pour le diagnostic**.

Sur le `RESULT=None` de STRAT, j'ai enchaîné **trois hypothèses fausses**, chacune
payée d'un run de 130 s :

1. un double-envoi du signal `finished` — plausible, écrit dans le code avec un
   commentaire affirmatif **avant** d'être démontré ;
2. la clé `rmse` dans `final_results` — déduite d'un `awk` qui ne montrait pas dans
   quel dictionnaire la clé atterrissait ;
3. l'accès par attribut alors que la charge utile est un dict.

Ce qui a tranché en un seul run : **quinze lignes d'instrumentation** sortant
`DIAG_TYPE` et `DIAG_KEYS`, puis la lecture du bloc complet autour du `return`.
Deux gestes gratuits qui auraient dû venir en premier.

À l'inverse, ce qui a été établi vite et solidement l'a été **par artefact** :

- le warmup colorimétrie mort, prouvé par l'**absence** des `.nbi` correspondants,
  puis confirmé par leur **apparition** après correctif ;
- le cache numba hors de `%TEMP%`, prouvé par 78 `.nbi` dans les `__pycache__` et
  un répertoire `%TEMP%\CERTUS_Numba_Cache` inexistant.

> **Un contrôle par artefact coûte une seconde et conclut. Une déduction coûte un
> run et se trompe.** Sur ce dépôt, chercher le fichier produit — `.nbi`, `RESULT`,
> `git status` — bat la lecture de code à chaque fois.


---

## 14. 🔴 La sur-souscription "corrigée" est une RÉGRESSION sur STRAT

Première campagne A/B de la session, et elle réfute le correctif `e9221b8`.

Protocole : `ab_compare.sh` sur les **7 fichiers** du commit contre `e9221b8^`,
4 paires alternées, module `strat`, machine au repos.

| Paire | SANS (avant) | AVEC (après) | Écart |
|---|---|---|---|
| 1 | 128,739 s | 135,356 s | **+5,1 %** |
| 2 | 129,211 s | 137,236 s | **+6,2 %** |
| 3 | 131,183 s | 140,766 s | **+7,3 %** |
| 4 | 142,203 s | 149,043 s | **+4,8 %** |

**4 paires sur 4 dans le même sens.** Le critère du §1 de `REPRISE_PERF.md` est
sans appel : réduire le parallélisme de 14 threads à 4 **ralentit STRAT**.

L'hypothèse de départ — « 8 threads numba pour 4 cœurs physiques sur une puce
15 W se paient en throttling thermique » — est donc **fausse pour ce module**.
L'explication la plus plausible, **non vérifiée** : les tâches STRAT alternent
calcul et synchronisation, et le SMT masque cette latence ; brider à 4 threads
laisse les unités d'exécution inoccupées.

### Ce que la campagne valide au passage

- ✅ **`RESULT` identique aux 8 runs** (`0,02519543055680181`). L'ancrage réparé
  au §11.2 fonctionne et **est déterministe sur STRAT** — seul le temps disperse.
- ✅ Le changement de threads **n'a rien déplacé numériquement** : le risque
  d'ulps du §11.3 ne s'est pas matérialisé ici.
- ✅ Le trap multi-fichiers du §11.1 a restauré les 7 fichiers, arbre propre.

### Le suspect à isoler avant de décider

`e9221b8` regroupe plusieurs sites. Le plus probable coupable n'est pas le nombre
de *workers* mais **`NUMBA_NUM_THREADS`, passé de 7 à 3** dans
`certus/core/certus_core.py` — c'est un réglage **global**, qui bride toutes les
régions parallèles numba du processus, pas seulement celles de STRAT.

**Prochaine expérience, une seule ligne à alterner :**

```bash
bash scripts/ab_compare.sh certus/core/certus_core.py "e9221b8^" strat 4 --auto-yes
```

Si la régression suit `certus_core.py` seul, c'est `NUMBA_NUM_THREADS` : on peut
alors garder les comptes de *workers* sur les cœurs physiques et laisser le
plafond numba sur les logiques. Sinon, ce sont les comptes de workers, et le
commit est à annuler.

⚠️ **Rien ne dit que ce correctif soit néfaste ailleurs** : il touche aussi INDEX,
RE et FIELD, **aucun mesuré**. Ne pas généraliser ce résultat STRAT aux autres
modules — c'est exactement l'erreur que ce document reproche au §2 d'origine.
