# LIS CECI EN ENTIER AVANT DE TOUCHER À QUOI QUE CE SOIT

Tu travailles sur **CERTUS**, une suite scientifique de couches minces optiques. Le code
calcule de la **physique réelle** utilisée pour fabriquer de vrais filtres optiques. Une
erreur silencieuse ici ne produit pas un plantage : elle produit un **résultat faux qui a
l'air juste**, et quelqu'un fabrique une pièce avec.

**Un modèle plus puissant relira tout ce que tu fais dans une semaine.** Tout ce que tu
affirmes sans preuve reproductible sera annulé.

---

# ÉTAPE 0 — VÉRIFIE OÙ TU ES (obligatoire, 1 minute)

Il existe **plusieurs copies de ce dépôt sur cette machine**. Ce projet a déjà perdu des
journées entières parce qu'un correctif était appliqué dans un dossier et mesuré dans un
autre. **C'est le piège n° 1 et il est invisible.**

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```

**Le chemin affiché DOIT commencer par `C:\dev\gemini`.**

- ✅ Il commence par `C:\dev\gemini` → continue.
- ❌ Il commence par autre chose (par exemple `C:\dev\CERTUS\0108`) → **ARRÊTE-TOI.**
  Ne modifie rien. Signale-le. Tout ce que tu mesurerais serait faux.

Puis vérifie que le lint est propre :

```bat
.venv\Scripts\python.exe -m ruff check .
```
Doit afficher exactement : `All checks passed!`

---

# ÉTAPE 0 bis — FAIS TOURNER TOUTE LA SUITE DE TESTS **AVANT** DE MODIFIER QUOI QUE CE SOIT

**C'est ta toute première action de travail. Pas la deuxième.**

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe -m pytest tests/ -q --no-cov
```

**Compte 1 h 45.** Lance-la, laisse-la finir, ne l'interromps pas. C'est long, c'est normal,
et ce n'est pas négociable.

### Pourquoi c'est indispensable

Sans ce chiffre de départ, le jour où un test deviendra rouge tu n'auras **aucun moyen de
savoir si c'est toi qui l'as cassé** ou s'il l'était déjà. Tu passeras des heures à chercher
un bug que tu n'as pas introduit — ou pire, tu « répareras » un test qui allait très bien.

Ce chiffre sert aussi à vérifier que **le code compile réellement**. Beaucoup d'erreurs de
ce projet ne se voient ni au lint ni à la lecture : un import circulaire, une syntaxe
Python 3.14 mal interprétée, un module qui ne se charge pas. Seule l'exécution les révèle.

### Ce que tu dois en faire

1. Colle la **dernière ligne** de la sortie (celle du style
   `2851 passed, 8 skipped in 6300s`) dans `docs/JOURNAL_GEMINI.md`, section
   **« État de départ »**, à la place du `<A MESURER>`.
2. Committe cette ligne. Elle est ton point de comparaison pour tout le reste du travail.

### Si le résultat n'est pas zéro échec

**ARRÊTE-TOI et signale-le.** N'essaie pas de réparer.

Un test rouge avant que tu n'aies touché à quoi que ce soit ne veut pas dire qu'il y a un
bug à corriger : cela veut dire que **ton environnement n'est pas celui sur lequel les
mesures de référence ont été faites**. Corriger le test masquerait le vrai problème.

⚠️ **N'utilise jamais un nombre de tests venu d'ailleurs** — d'une autre copie du dépôt,
d'un ancien document, ou de ta mémoire. Seul le nombre que **tu** as mesuré sur **cette**
copie a une valeur.

---

# ÉTAPE 1 — LES INTERDITS ABSOLUS

Ces règles ne se discutent pas. Aucune n'admet d'exception, même si tu penses avoir une
bonne raison. Si tu crois qu'il faut en violer une, **arrête-toi et demande**.

## 🚫 1. Ne lance JAMAIS `ruff check --fix`

Il y a **6 750 erreurs « auto-corrigeables »** dans ce dépôt. Beaucoup sont des
**ré-exports volontaires** : un import qui a l'air inutilisé sert en réalité à rendre un
symbole disponible pour d'autres modules. Les supprimer casse le projet en silence.

Corrige **à la main**, un fichier à la fois, en vérifiant après chaque fichier.

## 🚫 2. N'ajoute JAMAIS de règle à `extend-ignore` dans `pyproject.toml`

Cette liste masque déjà **68 règles**. Elle ne doit que **rétrécir**. Un test la surveille
(`tests/oracle/test_lint_debt_ratchet.py`) et échouera si tu l'agrandis.

Si une règle te gêne, c'est le **code** qu'il faut corriger, pas la configuration.

## 🚫 3. Ne supprime JAMAIS le dossier `reports/`

Il contient les **résultats scientifiques de l'utilisateur** : 171 fichiers, des classeurs
Excel et des rapports de mesures d'indice réelles. Il est dans `.gitignore`, donc **git ne
te protégera pas** et la suppression est **irréversible**.

## 🚫 4. Ne modifie JAMAIS `example/example_strat/JSON-strat-example.json`

C'est le fichier de référence sur lequel toutes les mesures sont faites. Il s'est écarté
des valeurs correctes **quatre fois**, et chaque fois cela a coûté une session complète de
diagnostic à chercher un bug qui n'existait pas.

Pour tester une autre configuration, utilise
`scripts\probe_anchor_noise_pipeline.py`, qui injecte les paramètres **après coup** sans
toucher au fichier.

## 🚫 5. Ne « corrige » JAMAIS la syntaxe `except A, B:`

Tu verras dans **14 modules** du code comme :

```python
except KeyError, TypeError:
```

**Ce n'est PAS une erreur.** C'est la syntaxe PEP 758, valide à partir de Python 3.14, que
ce projet utilise volontairement. Si tu ajoutes des parenthèses, tu changes le sens du
code. **Laisse tel quel.**

## 🚫 6. N'inverse JAMAIS la convention d'indice `n̂ = n − ik`

Partout dans ce projet, l'indice complexe s'écrit `complex(n, -k)` avec `k ≥ 0`. Avec la
convention inverse, les calculs donnent `R + T > 1`, c'est-à-dire de l'énergie créée à
partir de rien. Physiquement impossible.

## 🚫 7. Ne réimplémente JAMAIS une formule TMM

Il existe **une seule source de vérité** pour extraire R et T :
`certus/physics/certus_opt_tmm.py::compute_RT_from_matrix`. Toute nouvelle variante doit
l'appeler. Deux bugs de signe ont déjà été trouvés dans des réimplémentations, valant 46 et
82 points de réflectance.

## 🚫 8. Ne découpe JAMAIS `certus/core/_certus_physics_impl.py`

Le fichier le dit lui-même en en-tête : `DO NOT SPLIT`. Les noyaux compilés dépendent de
la visibilité mutuelle dans un seul fichier.

## 🚫 9. N'affirme JAMAIS un résultat que tu n'as pas mesuré

Pas « cela devrait améliorer », pas « le taux est probablement de ». Soit tu as lancé la
commande et tu colles sa sortie, soit tu écris « je n'ai pas mesuré ».

## 🚫 10. Ne crée JAMAIS de rapport de session à la racine

103 fichiers y avaient été accumulés puis supprimés : c'étaient des journaux qui se
contredisaient. Ton unique journal est `docs/JOURNAL_GEMINI.md`.

## 🚫 11. Ne réintroduis JAMAIS de français dans le code

L'anglais est **strictement obligatoire** dans l'ensemble de la suite CERTUS (`certus/`). Tout commentaire, docstring, message de log ou documentation interne ajouté doit être rédigé **exclusivement en anglais**.

---

# ÉTAPE 2 — LES SEPT PIÈGES QUI T'ATTENDENT

Ce ne sont pas des hypothèses. **Chacun a été rencontré dans ce projet**, la plupart le
même jour. Lis-les : tu vas tomber dedans sinon.

## Piège 1 — Une mesure de bruit qui ne varie pas avec le bruit est FAUSSE

C'est la règle de méthode la plus importante du projet.

> **Si tu mesures une grandeur qui dépend du bruit, divise le bruit par 100 et remesure.
> Si le chiffre ne bouge pas, ta mesure est un artefact — pas de la physique.**

Le même taux de plantage a valu 28 %, puis 1,3 %, puis 1,47 % dans la même journée. **Deux
fois sur trois, ce n'était pas de la physique.** Le balayage du bruit coûte quelques
secondes et l'a montré à chaque fois.

## Piège 2 — `params` n'est pas toujours un dictionnaire

Sur certains chemins, `params` est un objet **pydantic** (`StratParamsDTO`) qui ressemble à
un dictionnaire mais **n'a pas toutes ses méthodes**.

- ✅ `params.get("cle")` fonctionne
- ✅ `params["cle"] = valeur` fonctionne
- ❌ **`params.setdefault(...)` N'EXISTE PAS** et lève `AttributeError`

Ce bug a tué le pipeline entier en 13 secondes, avec un résultat vide et aucune explication
claire. Écris plutôt :

```python
if params.get("cle") is None:
    params["cle"] = valeur
```

## Piège 3 — Importer un paquet déclenche son `__init__.py`

Tu voudras peut-être importer un symbole depuis `certus_physics`. **Attention** :
importer `certus_physics.quoi_que_ce_soit` exécute d'abord `certus_physics/__init__.py`,
qui importe la moitié du projet. Si tu fais ça **depuis** un module de `certus/physics/`,
tu crées un **import circulaire** et le projet ne démarre plus.

Vérifier les imports du module ne suffit pas : **il faut vérifier ceux de son paquet.**

Si le symbole ne sert que dans une annotation de type, utilise :

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from certus_physics.structures import Target
```

## Piège 4 — Les tests partagent des caches de classe

Certains objets gardent un cache **au niveau de la classe** (par exemple
`SplineBasisCache._cache`). Si ton test y ajoute des entrées, un **autre** test, exécuté
plus tard, peut échouer — alors qu'il n'a rien à voir avec le tien.

Symptôme : ton test passe seul, mais la suite complète échoue ailleurs.

Solution : dans ton fichier de test, sauvegarde et restaure le cache.

```python
@pytest.fixture(autouse=True)
def _isolate_cache():
    snapshot = SplineBasisCache._cache.copy()
    try:
        yield
    finally:
        SplineBasisCache._cache.clear()
        SplineBasisCache._cache.update(snapshot)
```

## Piège 5 — Un test qui échoue n'a pas forcément tort… mais parfois si

**Cinq tests** de ce projet vérifiaient un comportement **faux** et ont dû être retournés.
Un test exigeait par exemple `len(cache) < 500` sur un cache **plafonné à 512** après y
avoir mis 510 entrées : il ne pouvait plus réussir, quoi qu'on fasse.

**Ce que tu dois faire** : si un test échoue, ne le « répare » pas en changeant le nombre
attendu pour faire passer. **Comprends d'abord ce qu'il teste.** Puis, dans le journal,
écris laquelle des deux situations tu as trouvée :

- le code est faux → corrige le code ;
- le test est faux → corrige le test **et explique pourquoi dans son docstring**.

Si tu ne sais pas trancher, **arrête-toi et demande**.

## Piège 6 — La Phase A ne dit rien de ce qu'elle fait

Il existe **deux systèmes de journalisation** dans STRAT. L'un écrit sur la console, l'autre
écrit **dans une file d'attente destinée à l'interface graphique** — que personne ne vide
quand tu lances en ligne de commande.

**Conséquence : un silence ne prouve rien.** Ce n'est pas parce que tu ne vois pas de
message qu'un filtre n'a rien fait. Pour savoir ce que la Phase A a réellement fait, lis le
fichier `reports/STRAT_observability_*.json` le plus récent.

## Piège 7 — Le premier calcul est lent, et ce n'est pas une mesure

Ce projet utilise **numba**, qui compile le code au premier appel. Le premier lancement
peut prendre 30 secondes de plus **sans que rien ne soit anormal**.

**Ne compare jamais un temps de calcul entre un premier lancement et un second.** Lance
toujours une fois pour chauffer, puis mesure.

---

# ÉTAPE 3 — LA BOUCLE DE TRAVAIL

Pour **chaque** action du plan, dans cet ordre, sans en sauter :

1. **Lis l'action** dans `docs/PLAN_STRAT.md`. Elle donne le fichier, la fonction, ce
   qu'il faut écrire, et la commande de vérification.
2. **Si quelque chose n'est pas clair, ARRÊTE-TOI et demande.** Ne devine pas. Un plan
   ambigu est un défaut du plan, pas une invitation à inventer.
3. **Fais la modification**, la plus petite possible.
4. **Lance les tests** :
   ```bat
   .venv\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
   ```
   Si un test échoue : **n'avance pas**. Reviens en arrière ou corrige, puis relance.
5. **Lance le lint** :
   ```bat
   .venv\Scripts\python.exe -m ruff check .
   ```
   Doit dire `All checks passed!`
6. **Mesure**, si l'action le demande, avec la commande exacte du plan.
7. **Committe** :
   ```bat
   git add -A
   git commit -m "<ce que tu as changé>"
   git log -1 --format=%%H
   ```
8. **Écris l'entrée dans `docs/JOURNAL_GEMINI.md`**, au format donné là-bas, avec le hash
   et les sorties collées.

⚠️ **Ne fais jamais deux actions à la fois.** Si tu changes deux choses et que le résultat
bouge, tu ne sauras pas laquelle en est responsable — et personne ne le saura après toi.

---

# ÉTAPE 4 — RÈGLE D'OR SUR LES MODIFICATIONS

**Tout nouveau paramètre doit être inactif par défaut, et le chemin inactif doit donner
exactement le même résultat qu'avant, au dernier chiffre près.**

C'est ce qui permet de comparer. Si tu ajoutes une option et que le résultat change alors
qu'elle est désactivée, tu as cassé quelque chose — même si les tests passent.

Vérification type à écrire pour tout nouveau paramètre :

```python
def test_le_defaut_ne_change_rien():
    avant = fonction(a, b)                      # sans le nouveau paramètre
    apres = fonction(a, b, nouveau_param=0.0)   # avec, mais désactivé
    assert avant == apres      # égalité EXACTE, pas approximative
```

---

# ÉTAPE 5 — LE VOCABULAIRE DU PROJET

| Terme | Ce que ça veut dire |
|---|---|
| **le juge de paix** | Le dichroïque 48 couches, `example/example_strat/JSON-strat-example.json`. **Le seul exemple valable.** |
| **λ de contrôle** | La longueur d'onde à laquelle la machine surveille le dépôt d'une couche. |
| **bloc** | Un groupe de couches consécutives surveillées à la **même** λ. |
| **point tournant** (turning point) | Un maximum ou un minimum du signal de transmission pendant la croissance. |
| **POEM** | Méthode d'arrêt : on vise un pourcentage de l'amplitude entre les deux derniers points tournants, au lieu d'un niveau absolu. |
| **plantage** (crash) | Le dépôt **ne se termine pas** : la machine attend un niveau qui ne vient jamais, ou compte le mauvais nombre de points tournants. Ce n'est pas une perte de précision, c'est un run perdu. |
| **rendement** (yield) | Le pourcentage de dépôts qui se terminent. L'objectif du physicien : **95 %**. |
| **Phase A** | Choix de la meilleure λ pour chaque couche, une couche à la fois. |
| **Phase B** | Regroupement en blocs et test statistique Monte-Carlo des stratégies. |

---

# ÉTAPE 6 — QUAND ARRÊTER ET DEMANDER

Arrête-toi et demande **à chaque fois** que :

- une instruction du plan est ambiguë ;
- un test échoue et tu ne sais pas si c'est le test ou le code qui a tort ;
- une mesure donne un résultat très différent de celui annoncé par le plan ;
- tu es tenté de violer un des dix interdits ;
- tu envisages de modifier plus de trois fichiers pour une seule action ;
- tu obtiens un résultat **meilleur que prévu** — c'est très souvent le signe qu'on mesure
  la mauvaise chose.

**S'arrêter n'est jamais un échec. Inventer, si.**

---

# OÙ ALLER MAINTENANT

| Fichier | Quand le lire |
|---|---|
| `docs/PLAN_STRAT.md` | **Maintenant.** C'est la liste des actions, avec pour chacune le fichier, la commande et le résultat attendu. |
| `docs/JOURNAL_GEMINI.md` | **À chaque action.** C'est ton livrable principal. |
| `pages/CERTUS_STRAT.html` | Quand tu veux comprendre **pourquoi** le code fait ce qu'il fait. C'est la documentation de référence, avec les équations. |
| `CLAUDE.md` | Contexte général du projet : architecture, conventions, commandes. |
