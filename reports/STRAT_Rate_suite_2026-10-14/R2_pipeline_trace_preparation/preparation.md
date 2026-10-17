# R2 — préparation de l’observation native, 14 octobre 2026 à9 h43

Statut : observateur préparé, non raccordé, non exécuté. A2 utilise son code figé et continue.
Ce module n’importe pas CERTUS et ne réimplémente aucune formule. Les wrappers sont temporaires
dans un futur processus expérimental, avec restauration par `ExitStack`.

## Raccordement à préparer

Créer une nouvelle copie de l’adaptateur natif, sans modifier les sources périmées/actives.
Conserver HEAD et empreintes des sources scientifiques historiques, budget Rate240, six tours,
budget conjoint480, préfixe0 pour observer le cas natif déjà mesuré. Ce raccordement n’est pas
une nouvelle politique de sélection. Préparer une garde explicite, un tag unique et un dossier neuf.

Le wrapper `generate` doit porter `@functools.wraps(real_factory)` : l’observateur utilise la
signature de la factory pour enregistrer les arguments effectifs, y compris leurs défauts.
Installer ensuite le patch du générateur, puis `observe_pipeline(consensus, robustness)` autour
du probe. L’observateur voit ainsi la sortie complète de l’adaptateur, ses parents et sa grille,
et capture les imports différés du consensus avant l’exécution du probe.

À la fin, convertir la trace copiée en données JSON avec `json.dumps(..., default=json_default)`
du module d’observation, puis la sauver via le helper atomique existant. Une sauvegarde de trace
échouée doit être signalée dans l’état, avec artefact scientifique et logs conservés ; ne pas
perdre la mesure parce que son diagnostic a échoué. Le helper A2 actif reste inchangé.

## Vérifications requises quand la machine est libre

1. Délégation : chaque callable reçoit les mêmes objets/arguments et retourne le résultat original ;
   sortie, ordre, IDs et curseur de la factory identiques avec/sans observation.
2. Métadonnées copiées : une mutation NumPy tardive du résultat ne corrompt pas une trace déjà capturée.
3. Exceptions propagées et patches restaurés après exception, aucun état partagé laissé aux appels suivants.
4. NumPy scalaires/tableaux sérialisables ; valeur non prise en charge explicitement signalée, pas ignorée.
5. Parents/rounds/grid connus, seuil enregistré avant le log de round avec round inconnu explicite.
6. Profondeur physique lue dans les arguments de tâche ; cache de consensus distingué d’un appel réel.
7. Même scénario physique, mêmes mondes C2, sources et paramètres ; point fixe strict avant la trace scientifique.

Ruff ciblé et parsing AST passent. Les vérifications ci-dessus **n’ont pas été exécutées** pendant A2.
La mesure tracée ne démarre qu’après A2, ces vérifications et R0 ; au plus une trace de base selon le guide.

## Limites actuelles

Le contrat rejeté est observé ; les sorties privées de la closure avant contrat, notamment plafond
et dédoublonnage, ne le sont pas toutes. Ne pas déduire un motif non observé pour chaque candidat absent.
`retained_draw_count` mesure les tableaux encore présents dans la ligne, pas la profondeur physique
du consensus. L’événement de seuil précède le log du round : le joindre au suivant dans le même scope.
L’observation peut coûter du temps et de la mémoire ; aucun gain de performance ne peut lui être attribué.
