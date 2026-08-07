# JOURNAL — à remplir par Gemini, à vérifier par Opus une semaine plus tard

> **Ce fichier est ton livrable le plus important.** Plus important que le code.
>
> Dans une semaine, un modèle plus puissant (Claude Opus) relira **tout** ce que tu as
> fait et devra pouvoir le **re-vérifier lui-même**. S'il ne peut pas reproduire une de
> tes affirmations, il la considérera comme **fausse** et annulera la modification
> correspondante.
>
> Donc : **n'écris jamais « j'ai fait X ». Écris « j'ai fait X, voici la commande, voici
> sa sortie ».**

---

## RÈGLE 1 — Une entrée par action, dans l'ordre chronologique

N'efface **jamais** une entrée. Si tu t'es trompé, ajoute une nouvelle entrée qui dit que
tu t'es trompé. Un journal qui ne contient que des succès est un journal suspect.

## RÈGLE 2 — Toute affirmation chiffrée porte sa commande

Interdit : « le taux de plantage est de 1,3 % ».
Obligatoire :

```
Commande : .venv\Scripts\python.exe scripts\probe_anchor_noise.py
Sortie (extrait collé tel quel) :
     prof | lambda admissibles par couche : min  median  max | ...
        4 |    86     115   125   / 126      |   0 / 47          |   1.23%
```

## RÈGLE 3 — Un commit par action

Après chaque action terminée :

```bat
cd /d C:\dev\gemini
git add -A
git commit -m "<description courte de CE QUE TU AS CHANGE>"
git log -1 --format=%%H
```

Colle le hash dans le journal. **C'est ce hash qui permettra à Opus de voir ton diff
exact.** Sans lui, il ne peut rien vérifier.

> ✅ Le push automatique a été **désactivé** dans cette copie (`post-commit` renommé en
> `post-commit.DESACTIVE`). Committer ici ne publie **rien**. Ne le réactive pas.

## RÈGLE 4 — Si tu n'as pas fait, dis-le

Une entrée « je n'ai pas réussi, voici l'erreur » vaut **beaucoup plus** qu'une entrée
inventée. Le modèle qui te relit détectera l'invention en essayant de la reproduire, et il
perdra alors confiance dans **tout** le reste du journal.

## RÈGLE 5 — Ne conclus jamais d'une mesure sur un autre composant

Le **seul** exemple valable est le dichroïque 48 couches,
`example/example_strat/JSON-strat-example.json`. Les empilements à 8 couches présents dans
les tests servent à vérifier des mécanismes, **jamais** à conclure sur la physique.

---

## MODÈLE D'ENTRÉE — copie-colle et remplis

```markdown
### Entrée N° <numero> — <date AAAA-MM-JJ HH:MM> — <titre en une ligne>

**Ce que je devais faire** : <recopie l'action du plan, avec son numéro de §>

**Ce que j'ai changé**
| Fichier | Fonction | Nature du changement |
|---|---|---|
| `chemin/exact.py` | `nom_de_fonction` | <ajout / modification / suppression, en une phrase> |

**Pourquoi** : <une à trois phrases. Si tu ne sais pas pourquoi, ARRÊTE et demande.>

**Commande de vérification lancée**
```
<la commande, telle quelle>
```

**Sortie obtenue** (collée sans retouche, tronquée aux lignes utiles)
```
<coller ici>
```

**Résultat attendu par le plan** : <recopie ce que le plan annonçait>
**Résultat obtenu** : <identique / différent — et si différent, DIS-LE>

**Tests**
```
.venv\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```
Sortie : `<N> passed, <M> failed`
⚠️ Si `failed` > 0 : **ne passe pas à l'action suivante**, note l'échec et arrête.

**Lint**
```
.venv\Scripts\python.exe -m ruff check .
```
Sortie : `<coller>` — doit être exactement `All checks passed!`

**Commit** : `<hash git complet>`

**Ce dont je ne suis pas sûr** : <liste. Écrire « rien » est presque toujours une erreur.>
```

---

## POINT DE DÉPART — le repère `depart-gemini`

L'état du dépôt **avant que tu ne touches à quoi que ce soit** est marqué par une étiquette
git nommée `depart-gemini`. Tu n'as pas de hash à retenir : utilise ce nom.

```bat
git log --oneline --stat depart-gemini..HEAD
```

Cette commande liste **exactement** ce que tu as changé depuis le début. Lance-la de temps
en temps pour vérifier que tu n'as rien modifié sans t'en rendre compte.

Tout ce qui apparaît dans cette liste et n'a pas d'entrée correspondante dans ce journal
sera traité comme **une modification non déclarée**, donc suspecte.

**Ne supprime pas et ne déplace pas cette étiquette.** Si `git log depart-gemini..HEAD`
répond `unknown revision`, arrête-toi et signale-le : sans ce repère, personne ne pourra
plus séparer ton travail de ce qui existait avant.

Tout ce qui apparaît dans cette liste et n'a pas d'entrée correspondante dans ce journal
sera traité comme **une modification non déclarée**, donc suspecte.

### ⚠️ Un message d'erreur git que tu vas voir, et qui n'est PAS de ta faute

À certains commits, git affichera :

```
fatal: bad tree object f26d9e1a8fe29a9705111e6b7b80262871ff3d4b
error: failed to perform geometric repack
```

**Ton commit a quand même réussi.** Vérifie-le avec `git log -1`.

Cause : un vieux commit orphelin (`01047a1b`, du 2 juillet) a un arbre manquant dans la base
d'objets. Il n'est rattaché à **aucune branche**, il n'a donc aucun effet sur le code — il
fait seulement échouer le compactage automatique. Ce compactage a été désactivé dans cette
copie (`git config gc.auto 0`), tu ne devrais donc plus le voir.

**N'essaie pas de réparer la base d'objets git.** Ce n'est pas ton travail, et les commandes
de réparation git peuvent détruire de l'historique. Si le message revient, note-le dans le
journal et continue.

---

## ÉTAT DE DÉPART — mesuré le 2026-08-06, avant toute intervention de Gemini

Ces chiffres sont le **point de comparaison**. Toute mesure que tu feras doit leur être
comparée. Ils viennent de `scripts\probe_anchor_noise_pipeline.py full`, sur le dichroïque
48 couches.

```
Configuration : poem_anchor_noise = 1, tp_hysteresis_factor = 1.66,
                phase_a_level_margin_factor = 1.66, dp_yield_weight = 0,
                scan_wl_step = 1.0        <-- valeur RETENUE, voir ci-dessous

  RESULT                      0,002898268777962851
  RMSE global   med / p95     0,215 / 0,465   points de transmission
  bande passante p95          0,418
  front p95                   1,498
  plantage                    0,000     345 strategies rendues
  RUN_S                       ~1322 s
  gagnante                    2 blocs (544 et 531 nm)
```

### Pourquoi `scan_wl_step` vaut 1.0 — et pourquoi tu ne dois pas y toucher

C'est le **pas de la grille de longueurs d'onde de contrôle** : l'écart entre deux λ
candidates que l'algorithme a le droit de proposer. La machine de dépôt du physicien sait
se positionner au nanomètre, donc 1 nm est physiquement réalisable.

La question « 1 nm ou 2 nm ? » a été tranchée par **deux simulations complètes
indépendantes**, plage identique des deux côtés, seul le pas changeant :

| graine | pas 1 nm | pas 2 nm | écart |
|---|---|---|---|
| principale | **0,002898** | 0,005283 | 1 nm meilleur, ÷1,82 |
| 77 | **0,003553** | 0,008400 | 1 nm meilleur, ÷2,36 |

Deux graines, même sens. En prime, à 1 nm la stratégie gagnante n'a plus que **2 blocs au
lieu de 4** — donc moins de changements de λ à exécuter sur la machine.

**Ce paramètre est désormais fixe. Ne le modifie pas**, et ne le modifie surtout pas « pour
aller plus vite » : le run à 1 nm ne coûte que 9 % de temps en plus.

### ⚠️ Un piège créé par cette valeur, et il faut le connaître

Le fichier d'exemple a maintenant `wl_step = 1.0` (grille d'**affichage**) **et**
`scan_wl_step = 1.0` (grille de **balayage**). Les deux grilles coïncident donc.

Un bug ancien venait précisément de la confusion entre ces deux grilles : une fonction
rendait leur **union** au lieu de la grille de balayage seule, ce qui faisait proposer des
λ hors grille de contrôle. Il a été corrigé par `_resolve_monitoring_wavelength_grid`.

**Tant que les deux pas sont égaux, ce bug est invisible** — l'union de deux grilles
identiques est la même grille. Cela ne veut pas dire que le correctif est devenu inutile.

👉 **Ne supprime jamais `_resolve_monitoring_wavelength_grid` au motif que « les deux
grilles sont pareilles maintenant ».** Le jour où quelqu'un remettra un pas d'affichage
différent, le bug reviendra en silence.

**Suite de tests au départ** : `<A MESURER — voir ci-dessous>`
**Lint au départ** : `All checks passed!`

> ⚠️ Le nombre exact de tests est **en cours de mesure sur cette copie**. Tant que la ligne
> ci-dessus n'a pas été remplie, **ta toute première action est de la remplir toi-même** :
>
> ```bat
> cd /d C:\dev\gemini
> .venv\Scripts\python.exe -m pytest tests/ -q --no-cov
> ```
>
> Compte 1 h 45. Colle la dernière ligne de la sortie ici, telle quelle, puis committe.
> **Si le nombre d'échecs n'est pas zéro, arrête-toi et signale-le** : ce n'est pas à toi de
> réparer un test cassé avant d'avoir commencé, c'est le signe que l'environnement n'est pas
> celui attendu.
>
> Un chiffre approchant venu d'une autre copie du dépôt ne vaut rien ici : il inclurait des
> correctifs que cette copie n'a peut-être pas.

⚠️ Si tu ne retrouves **pas** ces chiffres avant d'avoir modifié quoi que ce soit,
**arrête-toi immédiatement** : ton environnement n'est pas celui-ci, et rien de ce que tu
mesureras ensuite n'aura de sens. Vérifie d'abord le §0 de `AGENTS.md`.

---

## LES ENTRÉES COMMENCENT ICI

<!-- Ajoute tes entrées en dessous, sans jamais effacer les précédentes. -->
