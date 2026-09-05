# 24. 💡 A25, A26, A27 — trois actions PRÊTES À EXÉCUTER, en attente

> Extrait de `CLAUDE.md` le 2026-08-16. Ce contenu **fait autorite** ;
> `CLAUDE.md` n'en garde qu'un renvoi. 🔑 **Un fait, un seul endroit** — si tu corriges
> quelque chose ici, ne le recopie pas ailleurs, mets un lien.

---


🔴 **CE N'EST PAS LE PROGRAMME COURANT.** 🔑 **Lequel l'est se lit dans la carte du §3 de
[`CLAUDE.md`](../CLAUDE.md), et nulle part ailleurs.** ⚠️ *Cette ligne annonçait « §23, la
multiple testglass methodology », **acquise depuis le 2026-08-19** — elle avait donc plus de
deux semaines de retard le 2026-09-06. C'est exactement pourquoi le nom du programme courant
ne se recopie plus.* Cette section était intitulée *« les trois actions suivantes »* et ne
l'était plus : requalifiée en **réserve** le 2026-08-15. Ces trois actions restent **valides,
utiles et entièrement spécifiées** — chacune donne son fichier, sa fonction, ce qu'il faut
écrire et le test qui doit échouer sur le code d'avant. Elles attendent, elles ne sont pas
périmées.

**Ce qui les motive, et qui n'a pas changé :** tout le travail des 12 et 13 août a rendu STRAT
plus **cohérent**. Rien ne l'a rendu plus **vrai**. §26 reste entier, et aucun correctif
interne n'y changera quoi que ce soit. **A25 est la seule action de ce document qui attaque
§26** — c'est ce qui lui garde sa priorité le jour où on quitte §23.

> **Chaque action donne : le fichier et la fonction exacts, ce qu'il faut écrire, le test
> qui doit ÉCHOUER sur le code d'avant, et les pièges connus.** Une seule action à la fois,
> un commit chacune — contrainte C3.

⚠️ **Ne les lance pas au banc sans avoir lu §4 et libéré la machine** (§11-5).

---

### 🔑 A25 — `sigma_rate` comme PRÉDICTION, la première grandeur vérifiable de l'extérieur

**Pourquoi en premier.** C'est la seule action de ce document qui attaque §26. Elle est
devenue possible le 2026-08-11, quand le noyau Rate a été écrit, **et personne ne l'a vu**.

Le noyau **refait le calcul de rate de la machine** au lieu de le remplacer par un tirage
(`certus_strat_growth.py:630`, `acc += d_nom_j / d_real_j` puis `a_est = acc / n_ref`).
Donc `sigma_rate` n'est plus un paramètre : c'est une **sortie**. Et 👤 a décrit ce que la
machine montre en salle — *« ±σ = 1 à 2 % »*.

#### Où, et ce qu'il faut écrire

| | |
|---|---|
| **Fichier** | `certus/core/certus_strat_robustness.py` |
| **Fonction** | `_test_strategy_robustness_task`, dans la boucle sur les niveaux de bruit |
| **Ancrage** | juste après `crashed_cells = sim_thick_batch > CRASH_SENTINEL_MIN` (~ligne 1946) |

Les deux grandeurs sont déjà là, côte à côte : `sim_thick_batch`, de forme
`(n_runs, n_layers)`, et `p_thick_nominal`. Pour chaque couche de `rate_layers`, sur les
runs **non plantés** :

```python
ratio = sim_thick_batch[ok_runs, i] / p_thick_nominal[i]   # ok_runs = ~any(crashed_cells)
sigma_rate = float(np.std(ratio))                          # dispersion RELATIVE
```

Remonter dans le résultat sous `sigma_rate_by_layer` et `sigma_rate_max`. La sonde
l'affiche à côté de `RESCUED=`.

#### Vérification

| # | Test | Attendu |
|---|---|---|
| 1 | Une stratégie **sans** couche Rate | `sigma_rate_max` **absent**, pas 0.0 — l'absence et le zéro ne disent pas la même chose |
| 2 | Piège 1 : bruit ÷100 | `sigma_rate` doit **s'effondrer**. S'il ne bouge pas, ce n'est pas de la physique |
| 3 | Exclure les runs plantés | un run planté porte une **sentinelle** à 1e18, pas une épaisseur. L'inclure rendrait un σ absurde et **plausible** |
| 4 | 40 couches Rate enchaînées | étendue ≈ **0 %** — §22 : le Rate **recopie** l'erreur, il n'en ajoute aucune |

#### 🔴 Comment RAPPORTER le chiffre, et c'est là que ça se joue

Le « 1 à 2 % » de 👤 est un **souvenir**, pas une mesure — *« c'est ce que j'avais en
tête »*. Même statut que la table de [`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.7, *« estimés par moi au feeling »*. Donc :

- **0,1 % ou 10 %** → informatif : le modèle rate quelque chose, **ou** le souvenir est
  faux. **Demander laquelle des deux**, ne pas trancher seul.
- **1 à 2 %** → **corroboration FAIBLE**. Ne l'écris **jamais** comme une validation.
- Dans les deux cas, la question à poser à 👤 : *« as-tu un relevé machine de cette
  dispersion, plutôt qu'un souvenir ? »* **C'est ça, la vraie validation.**

---

### A26 — Un bloc de SANTÉ DE RUN, pour automatiser le contrôle 4 de §12

**Trois fois en deux jours, une grandeur était calculée et n'atteignait aucun œil :**

| grandeur | ce qu'elle disait, sans que personne l'entende |
|---|---|
| `crash_eliminated` | 83 repêchées sur 343 ; **un run où 87 sur 87** l'étaient — aucune stratégie n'avait passé le filtre |
| `n_layers_forced` | §24-37 : **32 couches sur 48** en repli, et le résultat annonçait une gagnante comme un run sain |
| `forbidden_gain_negative` | §24-38 : **zéro rejet** sur 8 runs, corridor 0 comme 0,020 |

§12-contrôle 4 prescrit déjà *« compte les rejets, ne lis pas le code »*. Personne ne le
fait à la main. **C'est exactement pour ça que ces trois-là ont dormi.**

#### Où, et ce qu'il faut écrire

| | |
|---|---|
| **Fichier** | `scripts/probe_anchor_noise_pipeline.py`, à côté du bloc `RESCUED=` déjà écrit |
| **Sources** | le résultat (`phase_a_forced`, `crash_eliminated`) et le `reports/STRAT_observability_*.json` le plus récent |

Une ligne `HEALTH=` par anomalie, et **`HEALTH=OK` quand il n'y en a aucune** — un bloc
silencieux ne se distingue pas d'un bloc absent.

```
HEALTH=RESCUED 41/300          -- score = pire RMSE finie, PAS un score de robustesse
HEALTH=FORCED 32/48 couches    -- lambda non CHOISIE mais IMPOSEE, cf 17-37
HEALTH=FILTRE_INERTE forbidden_gain_negative : 0 rejet sur 48 couches
```

🔴 **Un filtre qui rejette ZÉRO est un DÉFAUT, pas un succès.** Il ne produit aucune erreur,
il produit un résultat plausible — c'est le mode de défaillance qui gouverne ce dépôt.

#### Vérification

Rejouer le run où **87 sur 87** étaient repêchées : il doit désormais **crier**. Et un run
sain doit dire `HEALTH=OK`, pas rien.

---

### A27 — A5, le harnais d'empreinte `float.hex()`

Toujours inexistant, et c'est **le seul instrument de C1** (§9). La recette complète est en
**palier 1 de la feuille de route** — ne la réécris pas ici, suis-la.

🔑 **Pourquoi ça devient urgent** : le 2026-08-13 je m'en suis passé pour la porte de
plantage en énumérant **exhaustivement ses 127 cas** (⚠️ le nombre 1046 a circulé ici et n’existe nulle part dans le dépôt : l’énumération réelle est `for n_runs in (10, 25, 50, 150, 300, 500)` à pas sauté, `tests/unit/test_strat_crash_gate_confidence.py:127`) — possible parce que c'est une
fonction pure de deux entiers. **Un changement de noyau n'a pas ce luxe**, et la prochaine
fois personne n'aura d'instrument.

⚠️ Les étapes 3 et 4 du palier 1 sont les seules qui prouvent que le harnais **fonctionne**.
Ne les saute pas : un harnais qui a l'air de marcher sans rien prouver est le pire des trois
états.

---

### 🔴 Ce qu'il ne faut PAS faire, et pourquoi

| | |
|---|---|
| **Toucher à la fonction objectif** (A21) | 👤 l'a gelée. C'est le chantier le plus rentable, et ce n'est pas à toi de le dégeler |
| **Chasser l'asymétrie H / L** | **Non mesurable** : le corridor perturbe les deux matériaux ensemble et aucun paramètre ne les sépare |
| **La convolution spectrale complète** | La part systématique est capturée ; sa modulation tirage à tirage mettrait une intégration **dans la boucle chaude** |
| **Monter la profondeur** | [`DECISIONS_TRANCHEES.md`, enquete 23](DECISIONS_TRANCHEES.md) : elle achète de la précision sur un nombre déjà précis |
| **Rouvrir la grille, le lissage ou la cadence** | Tranchés par 👤 le 2026-08-12. Une **mesure** peut les rouvrir, jamais un raisonnement |

### L'ordre, et la raison

**A25 d'abord.** A26 et A27 rendent le dépôt plus sûr ; **seule A25 peut rendre STRAT
vrai** — et elle est à portée depuis deux jours sans que personne l'ait vue.
