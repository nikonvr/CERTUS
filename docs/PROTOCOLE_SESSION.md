# Protocole de session — comment ne pas brûler une session pour rien

Écrit le 2026-08-05, après une session qui a consommé ~2,5 M de tokens d'agents pour
un diagnostic qu'une phrase du physicien a tranché.

---

## La leçon principale

Le blocage de STRAT a occupé **deux sessions complètes d'analyse**. Deux documents de
reprise, des dizaines de mesures, une démonstration probabiliste correcte sur la
composition du taux de plantage, deux audits parallèles à onze agents.

La réponse tenait en une phrase du physicien :

> « en général, je vois que le bruit fluctue de 45.5 % à 45.55 % par exemple »

**Coût de la question : une ligne. Coût de ne pas l'avoir posée : deux sessions.**

> 🔴 **Avant d'analyser un comportement physique surprenant, demande la valeur réelle du
> paramètre à celui qui a l'instrument.** Le code ne sait pas ce que vaut le bruit d'un
> OMS 5100. Le physicien, si.

---

## Règles pratiques

### 1. Ne pas lancer d'audit multi-agents pour comprendre du code

Un audit à onze agents coûte **≈ 1,2 M de tokens**. Lire directement les six fichiers qui
comptent en coûte ~50 k, et donne une meilleure compréhension parce qu'elle est continue au
lieu d'être recousue à partir de rapports.

L'audit parallèle se justifie quand il faut **couvrir** — balayer 226 fichiers de tests,
auditer 40 constantes, chercher une classe d'erreurs partout à la fois. Pas pour comprendre
une chaîne d'appels.

### 2. Committer tôt, committer souvent

C'est la seule chose qui survit à une limite de tokens. Un commit intermédiaire imparfait
vaut infiniment mieux qu'un travail parfait perdu.

⚠️ Le hook `post-commit` pousse vers le dépôt **public** `nikonvr/CERTUS`.

### 3. Écrire au fil de l'eau, pas à la fin

Chaque fait mesuré va dans un fichier **au moment où il est mesuré**. Un chiffre qui n'existe
que dans le fil de conversation est déjà perdu.

### 4. Mesurer plutôt que raisonner

Un run de banc coûte **zéro token** — c'est du temps machine, pas du crédit. Une heure de
raisonnement sur ce qui *pourrait* se passer coûte cher et conclut moins bien qu'un run de
40 secondes.

Cette session : trois runs de STRAT à des bruits différents ont tranché en cinq minutes une
question que deux sessions d'analyse n'avaient pas résolue.

### 5. Poser les questions tôt et toutes ensemble

Les trois questions du §5 attendaient depuis la veille. Posées, elles ont été répondues en
une minute — et l'une des trois a retourné tout le diagnostic. Ne pas les garder pour la fin.

---

## Ce qui, à l'inverse, valait son coût

- **Les mesures.** Trois runs du banc, la campagne A/B, les deux runs de calibration. Gratuit
  en crédits, décisif.
- **Le réfutateur.** Sur le premier audit, c'est lui qui a trouvé que `bench_examples.py`
  n'avait pas changé depuis `d38e969` — donc que l'ancrage `RESULT` n'était pas cassé. Un
  `git log` d'une seconde aurait suffi, mais personne ne l'avait fait pendant deux sessions.
  **Le réflexe à garder n'est pas l'agent : c'est le `git log`.**
- **Écrire les documents.** Ils sont committés, ils survivent, et la prochaine session
  démarre dessus.
