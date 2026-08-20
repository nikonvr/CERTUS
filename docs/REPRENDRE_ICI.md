# 🔴 REPRENDRE ICI — état gelé le 2026-08-20 à 18:05

> Ce fichier dit **où on s'est arrêté** et **la commande exacte pour repartir**. Il est le
> premier à lire, avant `CLAUDE.md`.

---

## 0. ⚡ LA SITUATION EN CINQ LIGNES

👤 veut que **le code de production, à `robustness_seed = 42` définitivement**, trouve sur
`r75x2` à **2 nm** une stratégie au niveau de **SEEL 0,57** — le niveau que la graine 77
atteint. Aujourd'hui la graine 42 y rend **0 déposable sur 1617**, toutes à 100 % de plantage.

📌 Le plan complet est [`PLAN_PRODUCTION_2026-08-20.md`](PLAN_PRODUCTION_2026-08-20.md).
Le chantier Rate est [`CHANTIER_RATE.md`](CHANTIER_RATE.md).

---

## 1. 🔴 LA PREMIÈRE CHOSE À FAIRE — réparer `probe_renoter.py`

**La panne est localisée, la veille de l'arrêt, et elle n'est PAS réparée.**

```
full_dynamics_grid : dict, 0 λ  ->  GRILLE VIDE
```

`scripts/probe_renoter.py` capture le contexte de pré-calcul **au premier appel** de
`run_final_simulation_block` — celui du criblage — où `full_dynamics_grid` **n'est pas encore
rempli**. La simulation de croissance n'a donc aucune donnée, et **toute stratégie injectée
plante à 100 %**, quels que soient la graine, la résolution ou le corridor.

**Signature de la panne** : des résultats **identiques au millième** entre trois configurations
qui n'ont rien à voir. C'est ce qui a mis la puce à l'oreille.

**Pistes de réparation, non testées :**

| | |
|---|---|
| capturer à un appel **plus tardif** | le dernier, ou le premier où `full_dynamics_grid` est non vide |
| abandonner la capture | **recommandé** — voir §3 |

🔒 **Contrôle obligatoire avant de croire une seule sortie de cet outil** : re-noter les plans
de la graine 77 **à la graine 77 elle-même**. Attendu ~1 % de plantage. Tant qu'il rend 100 %,
l'outil ne mesure rien.

```bat
C:\envs\certus\Scripts\python.exe -u scripts\probe_renoter.py r75x2 ^
    reports\plans\plans_s077_vers_s042.json 77 fast ^
    monochromator_resolution_nm=2.0 robustness_num_runs=300
```

---

## 2. 🔴 CE QUI A ÉTÉ RETIRÉ — ne pas le recycler

Tout ce qui vient de `probe_renoter.py` **est faux** :

| affirmation | statut |
|---|---|
| « les 12 stratégies de la graine 77 plantent à la graine 42 » | 🔴 artefact |
| « le corridor d'indice n'est pas en cause » | 🔴 artefact |
| « le plantage est une propriété de la stratégie » (8/8 à 100 %) | 🔴 non informatif |
| « c'est / ce n'est pas un problème de recherche » | 🔴 **indécidé** |

⚠️ **Le contrôle du 35c, lui, réussissait** (`0 % → 0 %`, `2 % → 2 %`) — mais **sans surcharge
et sur un composant où le contexte se trouvait rempli**. Un contrôle qui ne couvre pas le régime
d'emploi ne protège pas de son régime d'emploi.

---

## 3. 🔵 CE QUE JE RECOMMANDE DE FAIRE PLUTÔT

**Abandonner la capture de contexte, et injecter par le CODE DE PRODUCTION.**

Le pipeline sait déjà injecter : `certus_strat_workers.py` gère des `inherited_strategies`, et
`_optical_prefix_variants` (`certus_strat_robustness.py:786`) montre le motif exact d'une clé de
paramètres qui injecte des variantes, **hoistée au-dessus du garde `allow_rate`**.

**Ajouter une clé `injected_strategies`** — inerte par défaut, routée depuis le JSON comme les
treize autres (§5) — qui verse une liste de plans dans la population. Les plans sont alors
évalués **par le chemin de production complet**, sans contexte reconstruit.

| | |
|---|---|
| le test devient fiable | même chemin que tout le reste |
| c'est le mécanisme dont on aura besoin de toute façon | injecter de bons plans comme parents d'ELITE est ce qu'il faudra pour que la production les redécouvre |

🔒 Règle d'or : inactif par défaut, chemin d'avant au bit, et **un test qui ÉCHOUE sur le code
d'avant**.

---

## 4. 📏 LES FAITS ÉTABLIS — tous issus de runs de production complets

```
r75x2 @ 2 nm, deep
  graine 42 : 1617 strategies,   0 deposable,  toutes a 100,00 %
  graine 77 : 2231 strategies, 547 deposables, meilleure SEEL 0,5692, crash 1,33 %, 9 blocs

  plans deposables de la graine 77 presents dans la population de la graine 42 : 0
  -> les deux recherches explorent des regions ENTIEREMENT DISJOINTES
```

**Diagnostic ELITE** (`journal_1_diagnostic_s042_20260820_120135.log`, 46 rounds) :

```
4226 candidates ENGENDREES (plafond de 120 atteint dans 30 rounds sur 46)
1327 evaluees en entier · 0 RETENUES
rejets : halving 1368 · RMSE 211 (16 %) · PLANTAGE 1116 (84 %)
```

🔑 **Le générateur n'est pas à sec. 84 % des candidates meurent de la porte de plantage.** ELITE
est une recherche **locale** (λ ± 1 nm autour des parents) qui rejette tout ce qui plante : elle
ne peut donc jamais **traverser** une vallée qui plante. Et `elite_stop_on_no_gain = True` coupe
après le premier round stérile — les rounds 2 et 3 de `deep` ne tournent **jamais**.

🔑 **ELITE est le SEUL générateur produisant des déposables sur ce composant** : hors ELITE,
1617 et 1488 stratégies aux deux graines, **zéro déposable**.

---

## 5. ✅ CE QUI A ÉTÉ PORTÉ DANS LE CODE DE PRODUCTION

| | commit |
|---|---|
| **13 clés** ne franchissaient pas le JSON, dont `robustness_seed` **câblée à 42** | `aad370a` |
| les **4 leviers ELITE** (`span`, `max_candidates`, `stop_on_no_gain`, `max_full_evals`) | `f9b71ba` |
| ELITE **compte ses rejets**, 3 sorties nommées | `3151f3a`, `9e23567` |
| la docstring du mode `extreme` disait le **contraire** de la mesure | `6ca495d` |

⚠️ `elite_num_runs` est **délibérément non routé** : son défaut noyau vaut `min(num_runs, 80)`,
donc le router avec un défaut de 0 donnerait `max(10, 0) = 10` — un huitième de la profondeur.
Il faudrait une sentinelle côté noyau.

---

## 6. 🔒 LES SEPT DÉFAUTS D'INSTRUMENT CORRIGÉS LE 2026-08-20

Tous de la même famille : **le calcul se fait, le résultat n'arrive pas — ou n'est pas celui
qu'on croit.**

1. les compteurs ELITE placés **après** la sortie du round → muets dans le cas attendu
2. les pilotes de batch jetaient **99 %** du journal (30 lignes sur 15 887)
3. la sonde écrasait l'artefact précédent **sans message** → `scripts/_artefact.py`, 7 tests
4. le résultat perdu au **démontage de Qt** → écrire avant d'afficher, `os._exit`
5. les plans éliminés par la porte de plantage **disparaissaient** de la sortie
6. la clé `wl` au lieu de `wavelength` → λ à `None` **de la bonne longueur**, donc invisible
7. six workflows **zombies** en parallèle → l'outil s'arrête dès son artefact écrit

🔒 **La règle que cette journée impose** : *un outil de comparaison se contrôle sur son POINT
FIXE, et dans son RÉGIME D'EMPLOI, avant de servir. Comparer A à B sans vérifier que B redonne
B, c'est mesurer l'outil.*

---

## 7. Les fichiers à connaître

| | |
|---|---|
| `reports/plans/plans_s077_vers_s042.json` | **les 12 meilleures stratégies de la graine 77**, avec leurs λ. Coût de production : 155 min |
| `reports/blocs_vs_plantage_r75x2_deep_s077_20260820_160340.json` | les 547 déposables, **avec λ** (les artefacts antérieurs ont des `None`) |
| `reports/blocs_vs_plantage_r75x2_deep_s042_20260820_120112.json` | le diagnostic, 1617 stratégies, contrôle C1 exact |
| `reports/journal_1_diagnostic_s042_*.log` | 15 887 lignes, les compteurs ELITE |

---

## 8. ⚡ Repartir

```bat
C:\envs\certus\Scripts\python.exe scripts\preflight.py
C:\envs\certus\Scripts\python.exe scripts\coherence_md.py
C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

⚠️ **L'interpréteur est `C:\envs\certus\Scripts\python.exe`.** Les vieux documents qui citent
un interpréteur local au dépôt sont faux — il n'y en a pas. `scripts/coherence_md.py` (contrôle E)
vérifie mécaniquement que tout interpréteur cité existe.
