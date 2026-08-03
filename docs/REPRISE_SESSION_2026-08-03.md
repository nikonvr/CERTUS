# Reprise — session du 2026-08-03

Écrit pour l'agent (ou l'humain) qui prend la suite, y compris sous un autre
compte ou sur une autre machine. **Tout chiffre marqué « mesuré » l'a été ici** ;
tout le reste est signalé comme hypothèse.

À lire avec `docs/REPRISE_PERF.md`, que ce document **corrige sur plusieurs
points** — voir §5. Ne pars pas des chiffres du §2 de ce document-là sans avoir
lu le §2 de celui-ci.

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

### Bancs rapides : chiffres POLLUÉS, à refaire

Mesurés pendant qu'un robocopy vers Drive et des agents de lecture tournaient.
**Inexploitables**, conservés seulement pour l'ordre de grandeur.

| Module | Réf. doc | `RUN_S` ici (chaud) | Rapport |
|---|---|---|---|
| FIELD | 0,06 s | 0,216 | ×3,6 |
| INDEX_SPLINE | 1,6 s | 12,188 | ×7,6 |
| INDEX | 6,5 s | 81,521 | ×12,5 |

La contamination est **prouvée par la série elle-même** : sur INDEX_SPLINE,
`RUN_S` descend de 17,898 à 12,188 s pendant que le wall-clock monte de 26,65 à
33,74 s. Le calcul accélère et le processus ralentit : c'est une interférence
externe, pas du bruit.

**À refaire machine au repos**, un seul processus à la fois.

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

Les signaux `finished` des workers d'INDEX portent bien une charge utile —
`certus/workers/certus_index_workers.py:358` et `:757` émettent `pyqtSignal(object)`,
`:1178` émet `pyqtSignal(list)`. Donc `res` n'est pas nul, mais il n'a **ni
l'attribut `rmse_final`, ni la forme d'un dict**. Le cas `list` est le candidat
le plus probable.

**À faire :** identifier lequel des trois workers `app.run_optimization()`
emploie réellement, puis extraire la grandeur comme le font les autres runners
(`run_design` lit `getattr(app, "_workflow_best_rmse", None)`).

**Tant que ce n'est pas corrigé, toute optimisation des noyaux d'INDEX — donc
toute la piste §4.2 — se ferait sans filet.** C'est exactement la classe de
problème que `tests/oracle/test_silent_wrong_results.py` existe pour attraper.

---

## 4. Ambiguïté à trancher dans REPRISE_PERF.md

Le §2 donne INDEX à **6,5 s**. Le §6 titre « INDEX (6,5 s, avec `--auto-yes`) »,
mais explique dans le même paragraphe que le « No » par défaut fait sauter la
phase IR et fait tomber le run **de 12,8 s à 6,5 s**.

Les deux lectures sont incompatibles : soit 6,5 s est la mesure `--auto-yes`,
soit c'est celle sans. **Le facteur machine d'INDEX en dépend du simple au
double.** À trancher avant de reconstruire le tableau du §2.

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
4. **`2572f46` est suspect sur cette machine.** Il règle une sur-souscription de
   threads numba, réglage calibré par nature sur le nombre de cœurs. Le profil
   DESIGN à 873 % suggère un pool d'une dizaine de threads : sur 8 processeurs
   logiques ce serait déjà de la sur-souscription. **Non vérifié.**

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

## 8. Ce qui reste à faire, par ordre

1. **Refaire les bancs rapides machine au repos** — FIELD, INDEX_SPLINE, INDEX,
   deux passes, rien d'autre en vol. C'est ce qui tranche l'hypothèse
   « régression numba 0.66 » et la question `_path_stat` du §4.3, pour quelques
   minutes de calcul.
2. **Corriger l'extraction de `RESULT` du banc INDEX** (§3 ci-dessus).
3. **Trancher l'ambiguïté 6,5 s / 12,8 s** (§4).
4. **Vérifier les réglages de threads pour 4 cœurs** — le gain le moins cher s'ils
   sont en dur.
5. Puis seulement les bancs lourds : RE, METAL_SINGLE, METAL_BILAYER, et enfin
   STRAT et DESIGN, dont la dispersion naturelle impose plusieurs runs chacun.
   Sur cette machine c'est une campagne de fond, pas une mesure interactive.

🔴 **Rappel non négociable** : une seule session de calcul à la fois. Deux
processus numba concurrents se bloquent mutuellement (verrou du cache, §0 de
`REPRISE_PERF.md`), et sur 4 cœurs toute charge parallèle fausse la mesure.
