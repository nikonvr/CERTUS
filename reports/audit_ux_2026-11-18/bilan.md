# Audit UX de la suite CERTUS · 18 novembre 2026

[Contre-vérification](verification.md) du 18 novembre 2026. Elle confirme le double échec d’export dans STRAT et précise le rôle des aides de champ METAL.

**Priorité de correction : fiabiliser la confirmation d’export de STRAT.** Un opérateur peut quitter le poste en croyant le rapport HTML enregistré. La deuxième priorité concerne le dépôt de plusieurs fichiers dans le HUB. Ces deux situations surviennent au cours d’une tâche et échappent aux contrôles de la fenêtre initiale.

## Résultats par outil

Relevé sur fenêtre Qt à 1366 × 768. Le nombre de commandes inclut les cellules éditables que le banc recense comme interactives. La part droite est la fraction de largeur du séparateur principal, qui peut contenir plusieurs vues. Un tiret indique une géométrie à laquelle cette mesure ne s’applique pas.

| Outil | Tâche de l’opérateur | Commandes recensées | Part droite | Observation |
|---|---|---:|---:|---|
| HUB | Choisir un outil, ouvrir une mesure | 7 | — | Les tuiles précisent la tâche. Le dépôt multiple perd les fichiers suivants. Les tuiles ont un test d’accessibilité dédié. |
| DESIGN | Définir les cibles et les couches, optimiser puis exporter | 90 | 66,0 % | 60 entrées et 10 onglets recensés. Les cellules répétées expliquent une partie de la densité. Six en-têtes utilisent leur marge intérieure. |
| STRAT | Préparer le suivi de dépôt et transmettre un rapport | 29 | 67,2 % | L’accueil propose « Open the example ». Le message de sauvegarde peut masquer un export partiel. |
| RE | Retrouver les paramètres du dépôt à partir du spectre | 31 | 66,0 % | Reprise de configuration exercée. Le démarrage peut annoncer « Waiting for JIT compilation... ». |
| INDEX | Extraire l’indice du film avec un modèle de dispersion | 36 | 66,0 % | Le HUB y dirige par défaut un spectre générique. Cette décision mérite d’être visible pour qui voulait le lisser. |
| INDEX SPLINE | Extraire n et k sans modèle de dispersion imposé | 50 | 72,5 % | 12 intitulés d’onglet recensés, dont « Data », « Data (theory) » et « Data Corridor ». Le premier parcours mérite un essai de repérage. |
| FIELD | Examiner le champ et optimiser la tenue au flux | 40 | 70,6 % | Les tests distinguent convergence, plafond de couches et paramètre refusé. La colonne « Thickness (nm) » dispose de 111 px pour 123 souhaités. |
| SMOOTHER | Lisser une mesure avant son exploitation | 15 | — | Le parcours d’erreur sur un classeur illisible est testé. |
| SUBSTRATE INDEX | Caractériser le substrat nu | 15 | — | Le HUB précise « bare-substrate spectra », distinction importante avec la mesure d’un film. |
| METAL SINGLE | Caractériser un film sur substrat transparent | 31 | 71,0 % | Le bouton « ? » mesure 16 px de large à cette résolution. |
| METAL BILAYER | Caractériser un film sur substrat opaque | 41 | 71,0 % | Le bouton « ? » mesure 20 px. Un fichier de configuration peut avoir la même signature que celui de SINGLE. |

## Corrections proposées et critères de recette

1. **Priorité haute · STRAT, export partiel annoncé comme sauvegardé.** Après l’écriture Excel, le booléen renvoyé par le générateur HTML détermine le drapeau interne de succès. Le libellé « ✓ Saved » est ensuite affiché dans les deux cas. L’échec de l’écriture du manifeste JSON peut aussi rester dans le journal. Afficher le résultat par fichier, son emplacement et une action pour réessayer le fichier manquant. **Recette :** provoquer un échec HTML après un Excel valide. L’écran doit nommer le fichier disponible et celui qui reste à produire. Vérifier aussi le succès total et l’échec du manifeste. Voir `certus/ui/certus_strat_ui_export.py:320–326, 388–396` et `certus/utils/certus_data.py:881–884`.
2. **Priorité moyenne · HUB, dépôt multiple accepté partiellement.** Déposer deux classeurs autorisés. Le gestionnaire accepte l’événement, choisit `paths[0]` puis lance un module avec ce seul chemin. La personne qui dépose deux mesures pour les rapprocher peut ignorer que la seconde a été écartée. Afficher le nombre retenu et permettre un choix explicite si l’outil ouvre un seul fichier. **Recette :** vérifier un fichier, deux fichiers valides et un lot mixte, avec un retour explicite sur chaque fichier écarté. Voir `CERTUS_HUB.py:1118–1150`.
3. **Priorité moyenne · HUB, choix du module METAL.** Quand la signature JSON est commune aux deux modules, le nom de fichier peut trancher. Le simple fragment « metal » désigne SINGLE. Si le nom ne tranche pas, le sélecteur montre les noms des modules seuls. Un fichier de provenance incertaine peut donc être aiguillé sans que l’opérateur confirme le type de substrat. Réserver le choix automatique aux indices spécifiques et proposer « substrat transparent » ou « substrat opaque » dans le sélecteur. **Recette :** déposer le même contenu ambigu sous `lot.json`, `metal_lot.json` et un nom explicite incluant `bilayer`. Voir `certus/core/certus_hub_config.py:219–255` et `CERTUS_HUB.py:1096–1117`.
4. **Priorité moyenne · aide de METAL, petite cible de pointage.** Les deux boutons « ? » mesurent 16 et 20 px de large. Le contrôle de largeur minimal du banc examine les légendes d’au moins trois caractères, d’où le verdict global vert. Agrandir la surface active en gardant le symbole. **Recette :** contrôler le rectangle cliquable, le focus clavier et l’absence de chevauchement sur le portable. Voir `scripts/audit_ux_certus.py:890–895`.
5. **Priorité basse · démarrage, message technique.** DESIGN et RE affichent « Waiting for JIT compilation... » dans la mesure initiale. INDEX SPLINE affiche « System ready. JIT Warmup complete. ». Dire quelle action est disponible pendant la préparation, puis quand le calcul peut démarrer. **Recette :** lancer sur cache froid et lire le message du point de vue d’une personne qui souhaite charger sa mesure.
6. **Priorité conditionnelle · documentation hors connexion.** Les guides locaux du HUB, d’INDEX et de STRAT chargent MathJax et Mermaid depuis jsDelivr. Le guide du HUB signale la limite. Si l’atelier utilise des postes isolés, fournir les schémas critiques en local et une représentation lisible des équations. **Recette :** ouvrir les guides dans un navigateur au cache vide, réseau coupé, et suivre une procédure à partir de son schéma. Voir `pages/CERTUS_HUB.html:13–14, 72–73`.

## Parcours à éprouver auprès des utilisateurs

- **Première conception.** Confier une cible simple à une personne qui découvre DESIGN. Observer si elle repère les unités QWOT et nm, trouve la synthèse et sait quelle configuration sauvegarder. Les 90 commandes recensées constituent un motif de test. Elles ne mesurent pas la difficulté ressentie.
- **Passage DESIGN → STRAT.** Le guide DESIGN demande de conserver le design natif et de transmettre épaisseurs physiques et séquence des matériaux. Faire reprendre un exemple par une deuxième personne, puis lui faire vérifier l’ordre, les unités, le substrat et la plage avant lancement. Relever toute ressaisie et tout écart. Voir `pages/CERTUS_DESIGN.html:983–995`.
- **Caractérisation.** Présenter un spectre de film, un spectre de substrat nu et une mesure sur substrat opaque. Relever le premier module choisi, les retours au HUB et la capacité à expliquer le résultat. Dans INDEX SPLINE, demander de retrouver la mesure, la courbe théorique et le corridor. 
- **Accessibilité en situation.** Avec clavier seul puis lecteur d’écran Windows, préparer deux couches dans DESIGN et choisir les milieux haut et bas dans STRAT. Plusieurs contrôles recensés portent respectivement « Select material » et « n (real) ». Vérifier que le contexte de ligne ou de groupe est effectivement annoncé avant de modifier un champ.

## Périmètre et force des preuves

Clone actif `C:\dev\certus1111`, révision initiale `5f2f3bbb`, prévol `PREFLIGHT=GO`. Exécution séquentielle, fenêtres Qt hors écran, police Segoe UI, préférences isolées. Les mesures portent sur la fenêtre initiale stabilisée, les contrôles visibles et les styles détectables lors du changement de thème. Un nom accessible détecté par Qt ne garantit pas à lui seul qu’un lecteur d’écran restitue le contexte métier.

À 1920 × 1080 et 1366 × 768, le banc termine avec le code 0 sur les onze fenêtres à chaque taille. Aucun texte visible détecté comme coupé, aucun raccourci vital manquant et aucun débordement horizontal relevé dans le panneau contrôlé. Les en-têtes serrés sont distingués des textes coupés. À 1366 × 768, DESIGN compte notamment « Weight » à 62 px pour 74 souhaités et « Thick(nm) » à 80 px pour 92 souhaités.

Une sélection de neuf fichiers de tests couvre dix situations complémentaires : commande du HUB, accessibilité des tuiles, clavier, retour d’import, erreur de lecture, fin de synthèse, arrêt pendant calcul, protection des modifications, annulation de fermeture et reprise. Sortie pytest : **74 passed in 84.60s (0:01:24)**. Les tests isolent certains dialogues et calculs. Les essais utilisateurs, le lecteur d’écran natif, le paquet installé, l’impression des rapports et la comparaison scientifique de bout en bout restent à vérifier. Aucun temps de tâche, taux d’erreur utilisateur ou score de satisfaction n’a été mesuré.


## Vérifications complémentaires

À 1280 × 720 pixels logiques, les onze fenêtres rapportent chacune un facteur Qt de 1,50. Le banc retourne 0. Pour chacune, `clipped=[]` et `panel_hscroll_px=0`. Cela porte à 33 le nombre de couples fenêtre–configuration contrôlés. Rejouer avec `python scripts/audit_ux_certus.py --both --json`, puis `python scripts/audit_ux_certus.py --width 1280 --height 720 --scale 1.5 --json`.

Les deux incidents prioritaires ont été reproduits au niveau du gestionnaire réellement appelé. Pour le dépôt, deux chemins valides sont fournis et le lancement du processus est intercepté. Pour STRAT, le classeur est écrit dans un dossier temporaire, le manifeste est simulé et le générateur HTML renvoie un échec. Sortie des sondes :

```text
accepted: True launch: call('CERTUS_INDEX.py', files=['first.xlsx'])
html attempted: True files: ['.json', '.xlsx'] status: call('✓ Saved: Report_STRAT_20261118_085411_RMSE_1.00000')
```

Le premier cas confirme que le second chemin disparaît à la transmission. Le second confirme que le statut de succès est envoyé alors que seuls le JSON et le classeur existent. Les sujets de densité visuelle et d’orientation restent des hypothèses à éprouver avec les opérateurs.
