# Reprendre Bonne Mère plus tard

Le sujet est clos à la demande de Fabien le 18 octobre 2026. Aucun calcul à poursuivre automatiquement. Le STRAT classique et ses validations prévues sont annulés.

1. Lire `README.md`, le dossier complet et `selection_retenue.json`.
2. Employer les JSON/CSV de pleine précision de `dossier_final/donnees`, jamais les tableaux imprimés arrondis.
3. Conserver la recette 96 saphir et la cible 601 points, les précoatings 130,21137747209175 / 183,994693878125 nm, les 70 optiques / 26 Rate et 452 nm sur les quatre premières opérations physiques. Insérer la pièce après les deux précoatings, sans reset du témoin.
4. Relire le bilan 0 / 0 / 1 arrêts sur 3 000. Le candidat n’a pas de validation indépendante finale ; la confirmation utilise 20261012101 / 20261012102 / 20261012103. Les références finales 20261012201–03 ne qualifient pas le candidat.
5. Si une reprise est décidée, préciser le critère de rendement, diagnostiquer éventuellement le tirage 888 à bruit 0,10 et figer un protocole avec de nouvelles graines avant résultats. Le budget humain le plus récent est 1 000 tirages par bruit et graine, trois graines.

## Vérifier sans calcul optique

Depuis la racine CERTUS :

```powershell
python studies/bonne_mere/dossier_final/outils/verifier_cloture.py
```

Cet outil lit uniquement les empreintes et les tableaux conservés. Il requiert NumPy et ne lance aucun moteur optique.

## Retrouver les sources anciennes

L’archive ZIP contient un TAR/XZ de sources dédupliquées et un index reliant chaque ancien chemin à ses octets d’origine. Restaurer seulement la branche souhaitée dans un dossier choisi, sur demande explicite :

```powershell
python studies/bonne_mere/dossier_final/outils/restaurer_archive.py --destination chemin_de_reprise --prefix reports/strat70_lambda4_2026-10-18/
```

Sans `--prefix`, tous les textes, sources et documents préservés sont restitués. Aucun fichier différent n’est écrasé et aucun lanceur n’est exécuté. La restauration augmente le volume : recontrôler la limite de 1 Go avant de la conserver.

Le moteur figé historique, les indices, paramètres, sources initiales Word/PowerPoint/Excel, plans et audits sont archivés. Le commit scientifique est 7f3edea879ab150eb9bee50b3b9f5d1675bb3869 ; ne pas confondre son instantané avec le futur code courant de CERTUS. Les données brutes des autres candidats ont été supprimées. Le script `build_dossier.py` est une trace de génération à partir des anciennes archives complètes ; utiliser le Word pour une révision documentaire après nettoyage.

## Règles scientifiques à garder

96 couches H800-Nb2O5 / H800-SiO2, cible finale 400–728,849591640315 nm, un témoin saphir, 98 couches témoin / 96 pièce, dix premières couches pièce optiques, Rate ≤ 70 %, monochromateur 430–900 nm et fente 2 nm. Corridor réel additif ±0,005 sur 400–900 nm ; mêmes réalisations pour croissance, notation et plans, absorption complète, SEEL calibrée sur la pièce. Rate sans dérive de vitesse ni erreur d’outillage. L’histoire passée peut aider les couches suivantes, aucune donnée future ne corrige rétroactivement un arrêt.

Le préfixe physique 66 identique à la référence est inapplicable à cette branche : les quatre monitoring initiaux changent. Contrôler les invariants de recette/modes et le monitoring après l’opération 4. Les moyennes et P95 sont conditionnels aux dépôts terminés ; publier les arrêts séparément. Les moyennes de graines différentes ne se classent pas directement.

## Après Bonne Mère

Fabien souhaite revenir au codage de CERTUS. Lire `CLAUDE.md`, exécuter le préflight puis lire `docs/ETAT.md` §0. Aucun changement de source de production n’a été fait pour cette clôture.

## Conservation Git et taille

Le commit de clôture conserve les documents, plans et tableaux de recette. Les deux archives compactes et le NPZ des trajectoires restent locaux, hors Git, afin de ne pas les dupliquer dans `.git` et dépasser 1 Go. Une copie Git seule ne contient donc pas toutes les preuves locales ; conserver le dossier Bonne Mère avec ses archives pour une reprise complète.
