# A3 — Reprise de l'assemblage 99 couches

Les [six bancs officiels et le premier essai d'intervalles](../STRAT_A3_reperes_reprise_2026-10-21/bilan.md)
restent conservés au code `85a9e82f`. Les quatre intervalles de la graine 42 ont réellement terminé.
L'assemblage s'est arrêté avant calcul : `orchestre_multigraine` appelle `sys.stdout.reconfigure` à l'import,
alors que le pilote avait déjà remplacé la console par `io.StringIO`.

Le moteur scientifique et `classer_partitions.py` sont inchangés. Le nouveau pilote termine l'import de
`CERTUS_STRAT` avant la capture de console. [Test de frontière réel](verify_console_import.py.txt) :
[sans préchargement, échec attendu](import_red.txt) ; [avec préchargement, réussite](import_green.txt).
Ce test ne lance pas d'assemblage numérique. [Empreintes originales et normalisées](import_hashes.json).
Ruff E9/F passe sur les pilotes et ce test. Aucun nouveau test du moteur n'est nécessaire pour ce changement du seul pilote.

[Protocole figé](intervalles_protocole.json), [pilote](run_A3_retained_intervals.py.txt),
[empreintes des sources](sources_sha256.json), [provenance de la réutilisation](reuse_provenance.json).
Les quatre emplacements déjà mesurés sont copiés octet pour octet et vérifiés par empreinte ; aucune mesure répétée.
Le source de l'outil de copie/adoption est conservé dans `prepare_reuse_source.py.txt` pour audit.
Après commit, l'adoption contrôle à nouveau toutes les copies et les 337 sources avant de créer l'état vivant.
Les données reprises restent attribuées à leur tête de mesure d'origine ; la nouvelle tête ne change que les documents et pilotes.

La suite reprend l'assemblage 42 dans un emplacement neuf, puis les quatre intervalles et l'assemblage des
graines 101 et 202. Même partition, mode fast, fente fixe 2 nm, offsets et total 99 ; aucune nouvelle partition.
Le consensus explicite 41/42/43 reste distinct de la banque de croissance et de notation de l'assemblage.
Le P95 assemblé est imprimé à 0,001 nm ; ces recherches ne sont pas une confirmation indépendante de plans figés.

Après contrôle d'absence de Python et adoption de l'état au commit courant :

```text
python "reports/STRAT_A3_intervalles_reprise_2026-10-21/run_A3_retained_intervals.py.txt" --outdir reports/STRAT_A3_intervalles_reprise_2026-10-21 --resume-interrupted
```

État vivant : `intervalles_etat.json`. Ne pas lancer l'ancienne chaîne PowerShell ni l'ancien pilote.
Pendant cette reprise, conserver tête et fichiers suivis fixes. Aucun lancement après 10 h Europe/Paris.
Un résultat absent, un repli ou une erreur ne devient pas un succès ; conserver les constats négatifs sans SEEL.
L'assemblage et les deux autres graines restent à mesurer au moment de ce protocole.
