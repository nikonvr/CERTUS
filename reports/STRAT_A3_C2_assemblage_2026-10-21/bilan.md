# A3 — Limite C2 de l'assemblage, repère 99 couches ouvert

Les six bancs officiels restent valides. Les premiers assemblages 99 couches ont terminé numériquement,
mais leurs scores ne sont pas retenus comme repères scientifiques : la vérification finale révèle un décalage de flux d'indice.
Les archives, états et résultats antérieurs restent intacts, incidents et anciens scores inclus.

Preuves de lecture : `campagne_intervalles._epaisseurs` retient le `noise_level` le plus proche de 1,0.
Le profil livré porte `trigger_tolerance=0.05` ; le vrai chargeur, relu sans croissance au même code,
donne les niveaux 0,025 / 0,05 / 0,1. Le cache retient donc le troisième niveau, à deux fois le bruit nominal,
indice 2. La croissance utilise `_index_stream_seed(base_seed, noise_idx)` ; l'assembleur demande l'indice 1.
Ces deux flux sont différents. [Relecture du profil](noise_readout.txt), [source du contrôle](noise_readout_source.py.txt).
Cette relecture après mesure n'est pas une nouvelle capture du worker ; les configurations figées et le code sont conservés.

Le [protocole de diagnostic](protocole.json) conserve les douze fichiers d'épaisseurs déjà mesurés,
copiés sans modification dans trois caches neufs et vérifiés par SHA-256. Aucun intervalle ni plan n'est recherché à nouveau.
Le [prototype expérimental](run_A3_C2_assembly.py.txt), non exécuté numériquement et désormais bloqué, prévoyait le même `classer_partitions.main` et le même TMM.
Il aurait routé, dans le seul enfant d'assemblage, la demande d'indice 1 vers l'indice 2 de ces épaisseurs,
en vérifiant la graine de base et l'appel unique. Ce raccordement n'a pas été exécuté ; il ne résout pas le second défaut ci-dessous.
L'algorithme de génération de graine reste celui du logiciel. Aucun fichier du moteur ni défaut livré n'est changé.

La vérification géométrique a ensuite échoué : la bande spectrale est 610–655 nm, mais les longueurs d'onde
de surveillance la débordent. La croissance normalise l'erreur d'indice sur l'enveloppe du spectre et du plan ;
l'assembleur prend seulement la bande spectrale. Les enveloppes diffèrent même entre les quatre tranches d'une graine.
[Les douze choix, domaines et offsets sont conservés](geometry_readout.json), avec le source du contrôle.
Corriger seulement l'indice du niveau de bruit ne rétablit donc pas C2. Aucun des trois nouveaux re-scores envisagés n'a été lancé.

La partition mesurée reste 0-22 / 22-42 / 42-76 / 76-99, fast, fente 2 nm, 50 tirages par graine 42/101/202.
Le consensus 41/42/43 de la recherche est distinct de la notation spectrale et n'est pas une confirmation indépendante.
La correction demande un protocole qui assure un domaine d'indice commun pendant croissance et notation, ou une
notation capable de reconstruire exactement chaque réalisation par tranche. Le pilote scalaire actuel ne le garantit pas.
Aucun défaut scientifique n'a été changé et aucun score 99 couches courant n'est déclaré valide.

Le prototype conservé refuse désormais son lancement avant tout calcul :

```text
python "reports/STRAT_A3_C2_assemblage_2026-10-21/run_A3_C2_assembly.py.txt"
```

Les sources et configurations du diagnostic restent conservées ; A3 demeure ouverte pour le 99 couches.
La suite indépendante autorisée est A5. Aucun lancement après 10 h.
