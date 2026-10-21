# A10 — Préparation avant mesure, 21 octobre 2026

Aucune mesure A10 lancée ni constante du dépôt modifiée. Ordre conservé : A3, A5, A4, puis A10.
Source lue : `85a9e82f`, `certus_strat_local_search.py`, raccordement du worker et ancienne étude §7.

L'étage courant construit ses paramètres de recherche et de contrôle avec
`max(SEARCH_INDEX_CORRIDOR, index_corridor)`. Son classement final utilise les paramètres d'origine.
Le changement temporaire de la constante dans un enfant de campagne peut donc comparer les deux amplitudes
sans modifier le corridor de notation, qui doit être vérifié à ±0,005 à l'entrée du worker et à la notation finale.
Réutiliser le moteur et ses perturbations ; aucun nouveau calcul TMM.

Réserver 36 recherches : 75c, `r75x0.5`, `r75x2`, juge de paix ; banques 77, 101, 202 ; trois variantes :
recherche à ±0,005, recherche à ±0,010, enveloppe des deux amplitudes. Mode deep, paramètres identiques
dans chaque comparaison appariée. Les deux variantes simples conservent les deux passes et les graines
de recherche/contrôle dérivées du banc par les offsets courants. Vérifier les fichiers et fentes effectivement chargés.

Définition proposée, à figer avant lancement pour la troisième variante : appeler l'évaluateur natif aux
deux amplitudes avec les mêmes graines, nombres et indices de tirage. À chaque niveau de bruit et pour
chaque tirage, prendre le maximum des deux RMSE et l'union des arrêts, puis utiliser la recherche conjointe
existante sur cette enveloppe. Ce critère conservateur est le pire cas par tirage ; il ne sera pas présenté
comme le maximum des deux moyennes. Conserver aussi les deux évaluations séparées.
Avant usage : vérifier l'alignement des formes, les graines et l'identité lorsque les amplitudes sont égales,
l'union des arrêts et l'absence de mutation des paramètres. L'enveloppe reste un dispositif expérimental.

Banque de confirmation réservée ici avant toute observation A10 : **2100210001, 2100210002, 2100210003**,
1 000 tirages par graine et niveau de bruit. Aucun de ces tirages ne sera utilisé pour chercher ou accepter
un mouvement. Geler les 36 plans et leurs empreintes avant le premier dépouillement de cette banque.
Évaluer ensuite chaque plan à ±0,005 et ±0,010 sur les mêmes tirages, en conservant tableaux par tirage,
arrêts et empreintes. Les triplets de consensus du classement restent distincts de cette confirmation.

Règle de comparaison conservée : gain de RMSE² moyen apparié au bruit nominal à ±0,010 supérieur à deux
erreurs types, coût de SEEL à ±0,005 au plus 2 %, aucun arrêt ajouté aux deux amplitudes. Comparer chaque
variante à la recherche à ±0,005 ; donner les résultats par design et graine avant toute proposition de défaut.
Une variante refusée par son contrôle interne conserve le plan de départ : enregistrer ce refus, sans lui
attribuer le plan intermédiaire rejeté. Aucun plan absent ou de repli ne reçoit de SEEL valide.

L'ancien `outils/judge_ic.py.txt` est une preuve historique, pas un pilote à relancer : chemin de dépôt et
dossier temporaire y sont figés, et il supprime son fichier de sortie existant. Le nouveau pilote devra utiliser
des emplacements neufs, une garde d'échéance avant chaque lancement et conserver tous les essais.
Cette préparation ne valide ni le troisième dispositif ni un choix de corridor.
