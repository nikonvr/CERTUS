# A8 structurel — Préparation statique, 21 octobre 2026

Aucune reproduction ni correction structurelle exécutée ici. Sources inchangées pendant A3.
Reprendre après A5, A4, A10 et A9, avec une validation ou mesure à la fois.

D23 : les six collectes sont présentes dans `certus_strat_workers.py` et `certus_strat_workers_pipeline.py`.
La sonde `scripts/sonde_retenants_fenetre.py` ferme une fenêtre, efface sa référence et collecte dans le fil
principal : elle diagnostique les détenteurs de D11, mais ne démontre pas une destruction Qt dans un fil de calcul.
La lancer séparément pour RE puis STRAT, conserver les résultats ; pour D23, observer ensuite un parcours de
worker réel, le fil des collectes et celui des destructions. Une reproduction synthétique peut montrer un risque,
pas prouver un arrêt de CERTUS. Ne pas passer à `WA_DeleteOnClose` sans reproduction et rétention des QThread actifs.

D11 : comparer les détenteurs nommés avant/après un seul changement. La fermeture en processus séparé par
le hub est déjà le comportement de production ; ne pas présenter une réduction du nombre de widgets comme
un gain numérique. Le plafond des connexions lambda ne doit que diminuer après une réduction observée.

D50/D72 : le repli en fils du gel, le refus du multigraine et la taille du paquet sont des sujets distincts.
Un gel plus petit ne valide pas son démarrage ni les calculs. Mesurer d'abord les dépendances réellement chargées,
avec le même environnement de construction, puis un retrait à la fois et contrôle du binaire livré.

D82 : rendre les états clairs/sombres et examiner les images du logo ; terminer la résolution des couleurs
de palette héritées avant de publier une mesure de contraste. Aucun rendu ni contrôle visuel effectué ici.
D84 : en cas d'écart au dernier bit après une clé Numba neuve, conserver le rouge puis relancer une seule fois ;
si l'écart persiste, comparer noyaux froids et chauds avant tout changement du calcul.

Ces préparations ne ferment aucune dette. Les défauts et travaux scientifiques réservés au propriétaire,
notamment l'élagage DESIGN D107 sur sa branche dédiée, restent hors de ce correctif.
