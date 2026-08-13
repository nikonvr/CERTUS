# ORDRE DE MISSION — campagne GATE

Tu exécutes des commandes et tu colles des sorties. **Tu ne modifies aucun fichier.**
**Tu ne conclus rien.** Si une étape ne donne pas l'attendu, tu **t'arrêtes** et tu le
signales.

Écris tes sorties dans `reports/RAPPORT_GEMINI.md`. Ne crée aucun autre fichier.

---

## 0. Vérifications — obligatoires, dans cet ordre

```bat
cd /d C:\dev\gemini
.venv\Scripts\python.exe scripts\preflight.py
```

Attendu : la dernière ligne est `PREFLIGHT=GO`.
Si c'est `PREFLIGHT=STOP` → **ARRÊTE. Colle la sortie. Ne fais rien d'autre.**

```bat
dir .git\hooks\post-commit*
```

Attendu : `post-commit.DESACTIVE`.
Si c'est `post-commit` tout court → **ARRÊTE. Ne committe rien.**

```bat
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Attendu : `All checks passed!` puis `2435 passed, 5 skipped`.
Un test rouge ici → **ARRÊTE. Colle la sortie.** Ce n'est pas à toi de le réparer.

---

## 1. Libère la machine

Ferme tout : navigateurs, éditeurs, autres terminaux. Aucune autre commande ne doit
tourner pendant la partie 2. Vérifie :

```bat
tasklist | findstr python
```

Attendu : **aucune ligne**, ou seulement celle de ta propre commande.

---

## 2. La campagne — une seule commande, environ 3 h 30

```bat
.venv\Scripts\python.exe scripts\run_campaign.py gate
```

**Ne la relance pas, ne l'interromps pas, ne lance rien d'autre pendant ce temps.**

Attendu, sur la dernière ligne : `DONE -- 6/6 runs OK.`

Si tu lis autre chose que `6/6 runs OK` → colle la ligne `DONE` et le résumé
`reports\CAMPAGNE_RESUME.md`, puis passe à la partie 4 sans faire la partie 3.

---

## 3. Les sorties à coller

### 3.1 Le tableau de campagne

```bat
type reports\CAMPAGNE_RESUME.md
```

Colle la sortie **entière**, sans retouche.

### 3.2 Le journal des runs

```bat
.venv\Scripts\python.exe -c "print(open('reports/probe_runs.tsv',encoding='utf-8').read()[-4000:])"
```

Colle la sortie entière.

### 3.3 Le tableau de comparaison

```bat
.venv\Scripts\python.exe scripts\analyse_gate.py
```

Colle la sortie entière.

---

## 4. Ce que tu écris dans `reports/RAPPORT_GEMINI.md`

Exactement ces cinq sections, dans cet ordre, et **rien d'autre** :

```
## 0. Verifications
<la sortie de preflight.py>
<la sortie de dir .git\hooks\post-commit*>
<la sortie de ruff>
<la derniere ligne de pytest>

## 1. Machine libre
<la sortie de tasklist | findstr python>

## 2. Campagne
<la derniere ligne, celle qui commence par DONE>

## 3.1 CAMPAGNE_RESUME.md
<la sortie entiere>

## 3.2 probe_runs.tsv
<la sortie entiere>

## 3.3 analyse_gate.py
<la sortie entiere>
```

🔴 **N'ajoute aucun commentaire, aucune interprétation, aucune conclusion.**
🔴 **Ne remplis aucune valeur que tu n'as pas lue dans une sortie.** Si une commande
échoue, écris `ECHEC` et colle le message d'erreur tel quel.
🔴 **Ne committe pas.** Ne modifie aucun fichier hors `reports/RAPPORT_GEMINI.md`.

---

## 5. Les cinq façons de rater cette mission

1. Lancer la campagne pendant qu'autre chose tourne → les résultats sont faux et rien ne
   le signale.
2. Relancer un run parce qu'il « a l'air bizarre » → tu écrases le précédent.
3. Écrire une valeur attendue au lieu de la valeur lue.
4. Interpréter. Ce n'est pas ta tâche.
5. Modifier un fichier pour « corriger » quelque chose.
