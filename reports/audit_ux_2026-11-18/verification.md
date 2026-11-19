# Contre-vérification de l’audit UX CERTUS · 18 novembre 2026

La priorité haute de STRAT est confirmée sur ses deux chemins d’export. Le second peut annoncer une sauvegarde alors que le dossier est vide. Le dépôt multiple et le routage METAL du HUB sont reproduits avec des fichiers locaux. Le constat sur les aides de champ METAL est corrigé ci-dessous.

## STRAT · statut vérifié dans la fenêtre

Essai sur une fenêtre Qt réelle, avec la configuration initiale collectée par STRAT, un résultat synthétique et un dossier temporaire vide par essai. Le chemin « signal Excel » reçoit un classeur en mémoire. Le chemin « automatique » est celui que la fin de calcul programme lorsque l’export est activé. Le contrôle du manifeste et le générateur HTML d’origine ont été utilisés. La lecture du statut a lieu à la sortie de chaque gestionnaire.

| Chemin | Condition provoquée | Fichiers effectivement créés | Statut de la fenêtre |
|---|---|---|---|
| Signal Excel | Témoin, écritures autorisées | XLSX, JSON, HTML | ✓ Saved |
| Signal Excel | Écriture du manifeste JSON en échec (`OSError`) | XLSX, HTML | ✓ Saved |
| Signal Excel | Écriture HTML en échec (`ValueError`) | XLSX, JSON | ✓ Saved |
| Automatique | Écriture HTML en échec (`ValueError`) | XLSX, JSON | ✓ Saved |
| Automatique | Production Excel et écriture HTML en échec (`ValueError` chacune) | Aucun | ✓ Saved |

Le générateur HTML intercepte la `ValueError` et retourne un échec. Le chemin automatique peut aussi intercepter une erreur de production Excel, poursuivre vers le HTML puis publier le même statut. L’essai porte sur les branches d’erreur injectées ; il ne mesure pas leur fréquence en atelier. La recette de correction doit couvrir ces cinq cas. Le statut final doit énumérer les fichiers réellement disponibles et désigner ceux à régénérer. [Gestionnaires d’export](../../certus/ui/certus_strat_ui_export.py) · [Déclenchement en fin de calcul](../../certus/ui/certus_strat_ui_worker.py)

## HUB · dépôt et routage

Deux fichiers CSV locaux ont été transmis au véritable gestionnaire de dépôt via un événement Qt avec deux URL. Seul le lancement du processus enfant a été intercepté. Le témoin à un fichier transmet bien son chemin. Avec deux fichiers, le HUB accepte l’événement, déclenche un seul lancement et transmet uniquement `lot-0.csv`. L’importation du second fichier dans une autre fenêtre demanderait une action supplémentaire.

Pour le routage METAL, trois fichiers contenaient le même objet JSON doté des clés `physical_params` et `material_params`. Seul le nom variait. Le choix interactif a été intercepté au moment où il aurait été présenté.

| Nom du fichier | Décision du HUB |
|---|---|
| `lot.json` | Demande à l’opérateur |
| `metal_lot.json` | Ouvre METAL SINGLE sans demander |
| `metal_bilayer_lot.json` | Ouvre METAL BILAYER sans demander |

La présence du mot générique « metal » suffit donc à modifier l’aiguillage d’une configuration ambiguë. L’essai vérifie la sélection du module ; il ne conclut pas sur la compatibilité physique du fichier après ouverture. [Routage du HUB](../../CERTUS_HUB.py) · [Signatures de configuration](../../certus/core/certus_hub_config.py)

## METAL · précision sur les « ? »

L’audit initial parlait d’un petit bouton d’aide par module. À 1366 × 768, la fenêtre SINGLE contient **7 aides de champ de 16 × 44 px** et BILAYER **12 de 20 × 46 px**. Ces 19 widgets ont une infobulle métier, prennent le focus clavier et déclarent zéro récepteur du signal `clicked`. Leur largeur est confirmée. L’aide existe aussi sur le libellé et le champ associé. La difficulté porte sur la promesse d’interaction lorsque le clavier atteint le « ? ». Une recette pertinente consiste à accéder par Tab à l’aide sur l’épaisseur, à l’ouvrir au clavier et à retrouver le champ. La documentation générale F1 constitue une commande distincte. [Composition dans SINGLE](../../certus/ui/certus_metal_base_app.py) · [Composition dans BILAYER](../../certus/ui/certus_metal_bilayer_gui.py)

## Reproductibilité et limites

La vérification a commencé sur le clone actif à la révision `5f2f3bbb`. Le prévol final a relevé `fb6af461`. Le diff entre les deux révisions porte sur deux fichiers du noyau substrat et la référence de dette architecturale. SUBSTRATE INDEX a été remesuré aux trois réglages sur cette dernière révision, avec trois sorties « modules with at least one issue: 0/1 ». [Contrôle du substrat](substrat_fb6af461.txt) Le script de sondes livré avec le premier audit introduisait trois erreurs Ruff de classement des imports. Sa correction manuelle rétablit `PREFLIGHT=GO`. La sonde historique a également été rejouée.

Les 11 fenêtres ont été rouvertes aux trois réglages du premier audit. Les 33 fenêtres stabilisées rendent le même verdict sans alerte. Pour chacune, les neuf indicateurs comparés coïncident avec les fichiers de l’audit initial : fraction horizontale de la vue de droite, contrôles interactifs, entrées, onglets, textes serrés, textes coupés, débordement du panneau, raccourcis vitaux manquants et notifications de démarrage. Le facteur déclaré par Qt est 1,5 pour les onze essais à 1280 × 720 logiques. Le décompte des contrôles couvre une liste de classes Qt. Il exclut notamment les tuiles personnalisées du HUB. La mesure de la fraction horizontale décrit un séparateur, pas la surface effectivement occupée par les courbes. [Comparaison des 33 mesures](comparaison_verifiee.jsonl) · [Observations des fenêtres et des fichiers produits](scenarios_verifies.jsonl)

Les messages techniques de démarrage et les dépendances CDN des guides sont confirmés, respectivement par le relevé Qt et la lecture des pages. Le rendu des guides dans un navigateur hors connexion, l’accessibilité avec lecteur d’écran natif et la difficulté du transfert DESIGN → STRAT pour un opérateur demeurent non mesurés.


Les neuf fichiers de tests de parcours du premier audit ont été rejoués en série. Sortie : **74 passed in 154.37s (0:02:34)**. Ces résultats incluent les protections de fermeture, la reprise de configuration, les commandes du HUB et les retours d’import. [Sortie pytest](parcours_verifies.txt)
