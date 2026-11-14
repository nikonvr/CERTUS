# REPRISE — réaménagement complet du dépôt (2026-11-13, soir)

Pour l'IA ou la personne qui reprend. Lire d'abord [`CLAUDE.md`](../../CLAUDE.md), [`AGENTS.md`](../../AGENTS.md), puis
la section 0 de [`docs/ETAT.md`](../../docs/ETAT.md). Ce fichier dit **où en est l'arbre** au soir du 2026-11-13 et
**comment rendre `certus1111` entièrement propre et cohérent** : un dépôt sans secours ni voie détournée, sans fichier
qui traîne, sans lien ni commande morts.

## Nuit du 13 au 14 novembre — ordre d'exécution

Enchaîner les lots à partir de la validation Windows déjà lancée. Les créneaux sont indicatifs. Une seule
validation ou mesure tourne à la fois. En cas d'échec, conserver le journal, isoler le cas et le rejouer seul.

| Créneau (Paris) | Lot | Critère de fin |
|---|---|---|
| 21 h 40–23 h 30 | Validation Windows, reproduction des rouges et C1 des poids spectraux | Toutes les suites passent ; les seuls écarts numériques sont ceux du correctif sur bandes disjointes |
| 23 h 30–1 h 30 | Nettoyage de la racine et des sous-dossiers, revue des branches et consolidation des Markdown | Copies et brouillons archivés hors du dépôt, résultats conservés, un seul point de reprise, liens et commandes vérifiés |
| 1 h 30–5 h 30 | Mesures DESIGN en série : tri-bande RICL, puis 50/50 avec grille fixe, grille automatique et sélection robuste, sur graines appariées | RMSE sur grille commune, durée et nombre de points consignés ; décisions sur les défauts fondées sur les mesures |
| 5 h 30–7 h 30 | Validation finale sur l'arbre nettoyé, commits par sujet et mise à jour de l'état | `VALIDATION=GO`, arbre Git propre, résultats et éventuels points ouverts datés |

Si ces lots terminent en avance, reprendre U12 B dans l'ordre STRAT robustesse, DESIGN PGLOBAL, INDEX SPLINE.
Chaque moteur exige un essai d'interruption et de reprise identique au bit. Les essais U13 sur écran réel, avec
le Narrateur et les participants suivent le [protocole U13](../refactor_corridors_2026-11-11/U13_protocole.md).

## 0. État du 14 novembre

Le code et les guides DESIGN et STRAT sont committés par sujet. Les résultats de la validation Windows et du
contrôle C1 sont dans le [bilan](bilan.md#9-validation-windows). Les mesures tri-bande et 50/50 sont le lot actif.

Il reste un worktree. Les sauvegardes, journaux et 401 exports ignorés sont dans l'archive hors dépôt du
2026-11-13. La branche Rate sur les fenêtres admissibles reste disponible pour une mesure appariée.

## 1. Contrôles après les mesures

Relire les résultats sur la grille de référence et sur les tirages de tolérance indépendants. Reporter dans le
bilan les échecs, les limites et les réglages retenus. Rejouer la validation après les dernières modifications
et vérifier que l'arbre est propre.


## 2. Réaménagement : ce qu'il faut retirer, ranger ou réparer

Chaque point dit le constat, le geste, et quand c'est fini. Aucun ne touche `reports/` (interdit 3), sauf mention.

### 2.1 Racine du dépôt — le nettoyage scripté

[`nettoyer_certus1111.ps1`](nettoyer_certus1111.ps1) fait les gestes ci-dessous ; sans `-Apply` il ne fait que les
montrer. Il ne touche à rien de suivi par git, et **déplace** hors du dépôt (`..\certus1111_hors_depot\2026-11-13\`)
ce qui n'est pas jetable.

| Constat | Geste |
|---|---|
| Anciens journaux à la racine | déplacés hors du dépôt ; les nouveaux journaux vont sous `logs/` |
| Dossiers vides `tmp`, `snom`, `bonne mere`, `invalid_dir` | effacés |
| `CLAUDE.md.bak` et deux copies de sauvegarde des résonances | déplacées hors du dépôt |
| Trois documents du concours OIC 2016 (PDF, XLS) : œuvres de tiers, jamais dans un dépôt public (CLAUDE.md §1) | déplacés hors du dépôt ; la cissoïde reste décrite dans les rapports |
| `scratch/` (lanceurs et journaux de session du 2026-11-13, préférences A9) | déplacé hors du dépôt |
| Worktree `.claude/worktrees/reprise-057fcd` | retiré après comparaison des six fichiers et archivage de ses journaux |
| Entrées mortes de `.git/worktrees/` (11 au registre C31) | `git worktree prune` |

```powershell
.\reports\questions_design_2026-11-13\nettoyer_certus1111.ps1
.\reports\questions_design_2026-11-13\nettoyer_certus1111.ps1 -Apply
```

*Fini quand* : `git status --short` ne montre que le travail à committer, `git worktree list` une seule ligne.

### 2.2 Branches et travaux en suspens

Les branches locales d'origine sont conservées dans `branches/branches-locales.bundle` dans l'archive hors dépôt.
Les branches déjà intégrées ont été retirées après contrôle de leur ascendance.

| Commit | Suite |
|---|---|
| `f81bb45d` | Les tours STRAT sont déjà intégrés à l'arbre de travail. Conserver les sorties RICL propres à la branche dans l'archive. |
| `46261901` | D107 est couvert par `68d926e3` et son test d'élagage. Archiver le prototype. |
| `cc3fe134` | Garder la piste Rate sur les fenêtres admissibles pour une mesure appariée. |
| `3f2564b4` | Archiver le protocole A5. |
| `71679373` | Correctif D104 repris avec son test : l'aperçu Tauc–Lorentz–Urbach utilise `eps_inf` pour la partie réelle de la permittivité. |
| `979ac2d1` | Archiver le prototype de résonances cachées. Le module natif `design_resonances` est intégré. |

### 2.3 Documents vivants — un fait, un seul endroit

- `docs/ETAT.md` §0 accumule des paragraphes datés (RICL du 2026-11-05, résonances, reprise du 2026-10-30, celui-ci) :
  le réécrire en **état présent** seulement, l'historique allant aux rapports qu'il cite déjà. Garder sous le plafond de
  `tests/unit/test_the_ai_entry_points_stay_small.py`.
- Trois fichiers de reprise coexistent : celui-ci, [`audits_2026-11-13/REPRISE.md`](../audits_2026-11-13/REPRISE.md) et
  [`refactor_corridors_2026-11-11/REPRISE.md`](../refactor_corridors_2026-11-11/REPRISE.md). Après le §1, n'en garder
  qu'un comme **point d'entrée** cité par `docs/ETAT.md` §0 ; les autres deviennent des rapports clos (une ligne en tête :
  « clos le …, suite dans … »).
- `docs/AUDITS.md` : retirer les lignes corrigées (règle du registre : un défaut corrigé sort de la liste), après le
  commit qui les corrige (ALG-31 sortira ainsi).

### 2.4 Liens et commandes morts — zéro

```bat
python scripts\check_docs.py
python scripts\coherence_md.py
```

Les contrôles Windows passent. Le contrôle de cohérence compte 113 scripts cités, zéro commande morte et zéro
renvoi de code signalé. Le contrôle des chemins de liens locaux couvre aussi les Markdown des rapports.
Les références à des exports scientifiques hors dépôt indiquent leur nom dans le texte.

### 2.5 Code — ni secours ni voie détournée

- Rien dans `certus/` ne doit dépendre d'un fichier de `scratch/` ou d'un worktree : vérifié pour le travail du
  2026-11-13 (les six fichiers STRAT sont du code ordinaire de l'arbre).
- Replis restants, connus et documentés : `cache=False` des trois appelants (C18, cause Numba ouverte), repli
  L-BFGS-B du polisseur LM quand il ne s'applique pas (voulu). Les autres défauts ouverts sont au §4 de `docs/ETAT.md`.
- Le travail en cours se vérifie vite avec `python scripts\verify_changed.py` (`--list` dit pourquoi un test est
  joué) ; la validation complète reste la règle avant de committer.

## 3. Mesures à faire ensuite (une à la fois, machine libre)

1. Tri-bande RICL : `python scripts\probe_auto_grid.py` (juge le record sur 1 nm, 0,1 nm, grille automatique et
   référence à 0,01 nm, puis polit sur chacune) ; résultat dans `probe_auto_grid.json` de ce dossier.
2. 50/50 apparié, grille fixe contre grille automatique, graines 42, 77, 202 (protocole du
   [bilan des audits, §3.6](../audits_2026-11-13/bilan.md#36-comparaison-avec-graines-du-mémétique-appariées)) :

```bat
python scripts\design_bench.py run --config example\example_design\JSON-design-reference-tikhonravov-1996.json --kw memetic_seed=42 --set _auto_restarts=0 --label fixe_42 --out reports\questions_design_2026-11-13\bench_50_50.jsonl
python scripts\design_bench.py run --config example\example_design\JSON-design-reference-tikhonravov-1996.json --kw memetic_seed=42 --set _auto_restarts=0 --set "_design_optional_steps={\"auto_wavelength_grid\": true}" --label auto_42 --out reports\questions_design_2026-11-13\bench_50_50.jsonl
```

   puis graines 77 et 202 ; la sélection robuste de même avec `{"memetic_robust_sigma_nm": 1.0}`. Rapporter la RMSE
   jugée à 0,5 nm (`rmse_grid`), la durée et le nombre de points, dans le bilan de ce dossier.
3. Seulement si la mesure le justifie : proposer à 👤 d'activer la grille automatique par défaut (exception C1).
