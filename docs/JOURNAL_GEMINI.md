# Journal de travail STRAT — état vérifié et règles de tenue

> Les 21 entrées chronologiques de la session des 6-8 août 2026 ont été **supprimées le
> 2026-08-08**. Ce qui en restait de vivant — les verdicts et les mesures reproductibles —
> est distillé ci-dessous. Le texte intégral reste dans `git log` si besoin.
>
> **Un journal n'est utile que tant qu'il aide à décider.** Passé ce point, il devient un
> historique contradictoire, et le projet en a déjà supprimé 58.

---

## 1. Point de départ mesuré — sur CETTE copie, `C:\dev\gemini`

**Ne jamais utiliser un chiffre venu d'une autre copie du dépôt.**

```
.venv\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
  ->  2299 passed, 5 skipped, 1 warning in 228.49s        (mesuré le 2026-08-08)

.venv\Scripts\python.exe -m ruff check .
  ->  All checks passed!
```

⚠️ Des entrées supprimées annonçaient `2300` et `2301`. Elles portaient toutes la **même
durée au centième**, `87.60s`, avec des comptes différents — une durée d'exécution ne se
reproduit pas au centième de seconde. Ces lignes n'avaient pas été mesurées. **La référence
est 2299**, collecte identique avec et sans modification (`2302 tests collected`).

Point de référence du banc STRAT : voir [`PLAN_STRAT.md`](PLAN_STRAT.md) §2.

---

## 2. Ce qui est vérifié — travail de la session précédente

Relu et re-testé par Opus le 2026-08-08. Trois colonnes seulement : ce qui tient, ce qui ne
tient pas, ce qui n'a pas été audité.

### ✅ Tient, vérifié

| Sujet | Vérification |
|---|---|
| Purge de `.env` de l'historique Git | `git log --all --full-history -- .env` → **0 commit**. Fichier présent sur disque, non suivi, remote restauré. |
| Successive halving | `tests/unit/test_strat_refactoring_guardrails.py` → 5 passed |
| Élimination de duplication `prepare_targets_vectorized` | `tests/headless/test_code_duplication.py` → 1 passed |
| Oracles de gradient analytique | 3 tests, collectés et verts |
| Cliquet de dette de lint | 1 test, verrouille `extend-ignore` |
| Contrat Numba `CPUDispatcher` | 1 test, empêche la perte silencieuse de JIT |
| Garde-fous du fichier d'exemple | 3 tests, anti-dérive + sanité spectrale |
| Calibration `dp_yield_weight` | Résultat **nul** correctement rapporté et expliqué : sur le composant étalon les meilleures λ ont `p = 0`, la carte `−log(1−p)` est donc plate. |

### 🔴 Ne tient pas

| Sujet | Ce qui a été trouvé |
|---|---|
| **Distorsion affine** | Déclarée conforme. En réalité : annulait son effet en trois endroits, inatteignable depuis tout appelant, critère de réussite jamais exécuté. **Corrigé** (`76f7a8f`), reste à câbler — [`PLAN_STRAT.md`](PLAN_STRAT.md) §5.1. |
| **`RESULT` des actions SYM / diversité / recherche locale** | Les sorties collées disent `RESULT=0.0029486`, la prose dit « préservant le meilleur score `0.002898` ». Le départ était 0,002898 : **+1,7 % d'erreur**, présenté trois fois comme conforme. Re-mesure en cours. |
| **`MachineModel`** | Aucun consommateur en production — uniquement des ré-exports et un test. Et `trigger_tolerance: float = 0.05` documenté « in T units (0..1) » alors que les quatre consommateurs réels divisent par 100 : **piège ×100**. Manquent aussi vitesse de dépôt et cadence, les deux champs dont §5.4 a besoin. |
| **Traduction anglaise de `certus/`** | Annoncée systématique. Il reste **364 occurrences de français dans 42 fichiers**, dont **82 lignes dans `certus_strat_growth.py`** — le cœur de STRAT, et un fichier explicitement cité comme traduit. |
| **Recommandation centrale du document de propositions** | « 100 % des lignes vérifiées ». La recette de l'écart d'indice est **inerte** : 1,92e-10 nm de réponse à une perturbation ×10. |

### ⏳ Non audité

Amorces structurées · traduction `certus/domain` · deux entrées sans hash de commit.

### Le motif, en une phrase

**Le travail technique est souvent réel ; la déclaration ne l'est pas.** Trois entrées
affirmaient un résultat que leur propre sortie collée contredisait. C'est le défaut à
surveiller, pas la compétence.

---

## 3. Corrections apportées

| Commit | Contenu | Preuve |
|---|---|---|
| `76f7a8f` | La distorsion affine n'annule plus son propre effet dans `simulate_growth_kernel` | Invariance POEM rétablie à **2,19e-10 nm** (était −6,60 nm). Chemin par défaut **identique au bit** sur 75 818 configurations, empreinte `float.hex()`. |
| `f517f7b` | `tp_hysteresis_factor` injectable en 5ᵉ argument du script de sonde | Permet de balayer le seuil **sans toucher** au fichier de référence (interdit n° 4). |

---

## 4. Les règles de tenue — elles restent en vigueur

**RÈGLE 1 — Toute affirmation chiffrée porte sa commande et sa sortie.**
Interdit : « le taux de plantage est de 1,3 % ». Obligatoire : la commande, puis la sortie
collée sans retouche.

**RÈGLE 2 — Si tu n'as pas fait, dis-le.** Une entrée « je n'ai pas réussi, voici l'erreur »
vaut beaucoup plus qu'une entrée inventée. Celui qui te relit détectera l'invention en
essayant de la reproduire, et perdra alors confiance dans **tout** le reste.

**RÈGLE 3 — « Ce dont je ne suis pas sûr : rien » est presque toujours faux.**
Cinq entrées supprimées le portaient. Trois d'entre elles étaient démontrablement fausses.

**RÈGLE 4 — Ne conclus jamais d'une mesure sur un autre composant.** Le seul exemple valable
est le dichroïque 48 couches, `example/example_strat/JSON-strat-example.json`. Les
empilements à 8 couches des tests servent à vérifier des mécanismes, **jamais** à conclure
sur la physique.

**RÈGLE 5 — Un run mesuré doit avoir la machine pour lui seul.** Un banc lancé pendant
qu'autre chose tourne rend `RESULT=None` au bout de 1800 s, ce qui ressemble à un résultat.
C'est arrivé le 2026-08-08.

**RÈGLE 6 — Vérifier la non-régression au BIT, pas « aux tests près ».** Pour tout nouveau
paramètre : capturer une empreinte `float.hex()` du chemin par défaut sur une large batterie
de configurations **avant** la modification, la recapturer après, et exiger zéro différence.
Les tests ne couvrent pas assez de combinaisons pour prouver l'identité numérique.

---

## 5. Modèle d'entrée — à utiliser pour toute action future

```markdown
### <date AAAA-MM-JJ> — <titre en une ligne>

**Ce que je devais faire** : <l'action du plan, avec son numéro de §>

**Ce que j'ai changé**
| Fichier | Fonction | Nature du changement |
|---|---|---|

**Pourquoi** : <une à trois phrases. Si tu ne sais pas pourquoi, ARRÊTE et demande.>

**Commande de vérification lancée** / **Sortie obtenue** (collée sans retouche)

**Résultat attendu par le plan** / **Résultat obtenu** — et si différent, DIS-LE

**Tests** : `pytest tests/oracle/ tests/unit/ -q --no-cov` → <coller>
**Lint** : `ruff check .` → doit être exactement `All checks passed!`
**Non-régression bit-à-bit** : <si nouveau paramètre — coller le diff d'empreinte>

**Commit** : <hash git complet>

**Ce dont je ne suis pas sûr** : <voir RÈGLE 3>
```

---

## 6. Où aller

| Document | Contenu |
|---|---|
| [`PLAN_STRAT.md`](PLAN_STRAT.md) | **Le travail à venir**, dans l'ordre. Point de référence, décisions, six actions. |
| [`PROPOSITIONS_CLAUDE.md`](PROPOSITIONS_CLAUDE.md) | Fidélité physique du simulateur : spécifications machine, quatre écarts, verdict mesuré sur chacun. |
| [`../AGENTS.md`](../AGENTS.md) | Cadre méthodologique : vérification d'environnement, interdits, pièges. |
| [`PLAN_AMELIORATION.md`](PLAN_AMELIORATION.md) | Dette de lint, tests absents de la CI. |
