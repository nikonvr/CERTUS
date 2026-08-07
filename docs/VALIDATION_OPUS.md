# Protocole de revalidation — à exécuter par Claude Opus, une semaine après

> **Ce document ne s'adresse pas à Gemini.** Il s'adresse au modèle qui reprendra le dépôt
> ensuite, et il décrit comment vérifier le travail fait entre-temps **sans faire confiance
> au journal**.
>
> Gemini peut le lire — c'est même souhaitable, qu'il sache à quoi son travail sera soumis.
> Mais il ne doit rien y modifier.

---

## Le principe

Un journal est une **déclaration**, pas une preuve. La revalidation consiste à reprendre
chaque déclaration et à essayer de la **casser**, pas à la confirmer.

Trois questions, dans cet ordre, pour chaque entrée du journal :

1. **Le diff correspond-il à ce qui est déclaré ?** (git ne ment pas)
2. **La mesure citée se reproduit-elle ?** (relancer la commande)
3. **La conclusion suit-elle de la mesure ?** (c'est là que ça casse le plus souvent)

Une entrée qui échoue à l'une des trois est **annulée**, pas corrigée.

---

## Étape 1 — Vérifier qu'on est au bon endroit

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

Doit commencer par `C:\dev\gemini`. Plusieurs copies du dépôt coexistent sur la machine.

---

## Étape 2 — Reconstituer la vérité git, indépendamment du journal

```bat
git log --oneline --stat depart-gemini..HEAD
```

`depart-gemini` est une **étiquette git** posée sur l'état du dépôt avant toute intervention.
Si elle a disparu, c'est en soi un signal : reconstitue le point de départ par la date, et
considère que l'historique a été manipulé.

**Compare cette liste avec les entrées du journal.**

| Ce que tu trouves | Ce que ça veut dire |
|---|---|
| Un commit **absent** du journal | Modification non déclarée. **Suspecte par défaut** : lis son diff en entier avant toute autre chose. |
| Une entrée du journal **sans commit** | Le travail n'a pas été committé, ou n'a pas eu lieu. Vérifie l'état réel du fichier concerné. |
| Un commit qui touche **plus de fichiers** que l'entrée ne le dit | Le périmètre a débordé. Regarde ce qui a été emporté au passage. |
| Un commit sans message explicite | Lis le diff ; ne te fie pas au titre. |

⚠️ **Un commit qui touche `pyproject.toml` mérite un examen immédiat** : c'est là que se
trouve `extend-ignore`, dont l'agrandissement transforme une dette visible en dette
invisible. Vérifie que la liste n'a fait que **rétrécir**.

⚠️ **Un commit qui touche `example/example_strat/JSON-strat-example.json` invalide toutes
les mesures postérieures.** C'est le fichier de référence ; il ne devait pas bouger. S'il a
bougé, `git diff` sur ce fichier d'abord, et considère toute comparaison chiffrée du journal
comme nulle jusqu'à preuve du contraire.

---

## Étape 3 — Remesurer l'état de départ, avant de juger quoi que ce soit

Reviens au commit de départ dans un worktree séparé, et relance la mesure de référence.
**Ne fais pas ça dans le dossier de travail** — tu perdrais l'état courant.

```bat
git worktree add C:\dev\gemini-baseline depart-gemini
```

Puis, dans ce worktree, la mesure du juge de paix. Si le chiffre obtenu ne correspond pas à
celui inscrit dans le journal comme « état de départ », **arrête tout** : ce n'est pas le
travail de Gemini qui est en cause, c'est la reproductibilité de l'environnement, et rien
ne peut être conclu tant que ce point n'est pas réglé.

Causes déjà rencontrées sur ce projet, par ordre de fréquence :

1. **Mauvaise copie du dépôt** — le code chargé n'est pas celui qu'on croit modifier.
2. **Cache numba froid** — le premier lancement compile ; ses temps ne sont pas comparables.
3. **Le fichier d'exemple a dérivé** des valeurs par défaut du code. C'est arrivé **quatre
   fois**, et chaque fois cela a coûté une session complète à chercher un bug inexistant.

Nettoyage une fois fini :

```bat
git worktree remove C:\dev\gemini-baseline
```

---

## Étape 4 — Les six vérifications qui attrapent l'essentiel

### 4.1 Tout nouveau paramètre est-il vraiment inerte par défaut ?

C'est **la** propriété qui rend les comparaisons valides. Pour chaque paramètre ajouté :

```python
avant = fonction(a, b)                      # sans le paramètre
apres = fonction(a, b, nouveau_param=0.0)   # avec, désactivé
assert avant == apres    # EXACT, pas np.allclose
```

Si l'égalité n'est qu'approximative, demande pourquoi. Sur ce projet, une réponse
légitime existe : **numba spécialise différemment `Omitted(None)` et `none`**, ce qui peut
produire un écart de l'ordre de 1e-16 à la **première** compilation. Au-delà de 1e-12,
ce n'est pas ça.

### 4.2 Les tests ajoutés échouent-ils sur le code d'avant ?

**Un test qui passe avant et après le correctif ne prouve rien.** C'est le contrôle le plus
rentable de toute cette liste.

Pour chaque test ajouté : copie-le dans le worktree baseline et lance-le. Il **doit**
échouer. S'il passe, soit il ne teste pas ce qu'il prétend, soit le correctif était inutile.

### 4.3 Les grandeurs de bruit varient-elles avec le bruit ?

> **Une grandeur de bruit qui ne varie pas avec le bruit est un artefact. Sans exception.**

Pour tout chiffre du journal qui dépend du bruit : divise σ par 100 et remesure. Le chiffre
doit s'effondrer. S'il reste stable, la mesure ne mesure pas ce qu'elle croit.

Sur ce projet, le même taux de plantage a valu **28 %, puis 1,3 %, puis 1,47 %** dans la
même journée. Deux fois sur trois ce n'était pas de la physique.

### 4.4 Chaque critère se prononce-t-il sur la bonne source ?

Les trois défauts les plus coûteux de ce projet étaient tous de cette forme :

- un critère lisait le signal **propre** au lieu du signal **bruité** ;
- une règle travaillait sur la grille d'**affichage** (1 nm) au lieu de la grille de
  **balayage** ;
- un filtre recevait une **matrice de zéros** au lieu de l'empilement réel — donc
  n'interdisait jamais rien, en silence.

Ce dernier est le plus vicieux : **un filtre inerte ne produit aucune erreur.** Il produit
un résultat plausible. Pour toute règle de sélection ajoutée, vérifie qu'elle **rejette
effectivement quelque chose**, en comptant les rejets, pas en lisant le code.

### 4.5 Les conclusions dépassent-elles les mesures ?

Relis chaque entrée en te demandant : *la phrase de conclusion est-elle impliquée par la
sortie collée juste au-dessus ?*

Attrape en particulier :

- une conclusion sur la **physique** tirée d'un empilement à 8 couches. Seul le dichroïque
  48 couches (`example/example_strat/JSON-strat-example.json`) est un exemple valable ;
- une **attribution causale** quand deux choses ont changé en même temps — un gain observé
  après avoir modifié A **et** B n'est attribuable ni à A ni à B. Cette erreur a déjà été
  commise sur ce projet, et la mesure isolante l'a **réfutée** ;
- un résultat **meilleur que prévu**, présenté comme un succès. C'est très souvent le signe
  qu'on mesure la mauvaise chose.

### 4.6 Le lint et les tests sont-ils réellement verts ?

```bat
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest tests/ -q --no-cov
```

Compare au nombre inscrit dans le journal. Un nombre de tests qui a **baissé** sans
justification veut dire que des tests ont été supprimés ou désactivés.

```bat
git log -p depart-gemini..HEAD -- tests/ | findstr /C:"@pytest.mark.skip" /C:"-def test_"
```

---

## Étape 5 — Le verdict

Pour chaque entrée du journal, tranche entre trois issues, et écris laquelle :

| Verdict | Critère | Suite |
|---|---|---|
| **Validée** | diff conforme, mesure reproduite, conclusion impliquée | rien à faire |
| **À remesurer** | diff conforme, mais la mesure ne se reproduit pas ou la conclusion dépasse | relancer la mesure soi-même, réécrire la conclusion |
| **Annulée** | diff non conforme au déclaré, ou test qui ne prouve rien, ou règle inerte | `git revert`, et noter pourquoi |

**Ne corrige pas une entrée annulée en la retouchant.** Reviens en arrière, puis refais.
Un correctif posé sur une base non vérifiée hérite de son incertitude.

---

## Ce qu'il ne faut pas reprocher à Gemini

Pour être juste dans le jugement :

- **Un travail non fait mais déclaré comme non fait** n'est pas une faute. C'est même ce
  qu'on lui a demandé. Une entrée « je n'ai pas réussi, voici l'erreur » vaut mieux qu'un
  contournement silencieux.
- **Un arrêt sur ambiguïté** n'est pas une faute. Le document ambigu est en tort.
- Une seule chose est réellement disqualifiante : **une affirmation chiffrée qui ne se
  reproduit pas**. Si tu en trouves une, cesse de faire confiance au reste du journal et
  revérifie tout depuis git.
