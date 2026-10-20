# Audit UX Complet & Pistes d'Amélioration — Suite CERTUS (`UXargon`)

> **Date de l'audit** : 2026-10-16 (commit `0c7c1e2e`, branche `claude/ecstatic-newton-3grmls`)
> **Périmètre** : Socle transversal (`CertusTheme`, `CertusBaseApp`, mixins UI, graphes `CertusScientificPlot`, accessibilité, onboarding, palette de commandes, notifications, états vides) + les **11 modules graphiques** de la suite CERTUS + boîtes de dialogue partagées.
> **Méthode** :
> 1. **Mesure instrumentée hors-écran** via [`scripts/audit_ux_certus.py`](scripts/audit_ux_certus.py), aux résolutions `1920x1080` et `1366x768`. La suite [`tests/ui/`](tests/ui/) n'a pas été réexécutée pour ce contre-audit.
> 2. **Audit statique et ergonomique du code source** de chaque composant et sous-programme (parcours utilisateur, charge cognitive, cohérence inter-modules, gestion des erreurs, retours visuels, raccourcis, accessibilité).

> **Contre-audit Codex, 2026-10-16** : code de production inchangé à `0c7c1e2e` ; 22 démarrages GUI rejoués, 20 observations ciblées communes aux deux audits, sans erreur du lanceur de sondes. [Sorties, observations et empreintes des sources](reports/ARGON_contre_audit_2026-10-16/evidence.json) ; [sondes reproductibles](reports/ARGON_contre_audit_2026-10-16/probe.py.txt). Préflight `STOP` : lancement Ruff défaillant et 60 fichiers suivis déjà modifiés ; périmètre documentaire demandé par 👤. Aucune validation globale du logiciel ni mesure de performance.

> **Recoupement avec le code, 2026-10-20** : constats corrigés, faux ou mal localisés amendés en place (marques `[CORRIGÉ]`, `[PARTIELLEMENT CORRIGÉ]`, `[AMENDÉ]`) ; [bilan](reports/AUDIT_UX_recoupement_2026-10-20.md).

**Lecture des statuts.** Sans sonde identifiée, un constat reste statique ; ses conséquences exactes doivent être vérifiées dans le parcours concerné. Les sélections forcées d'onglet INDEX, les contrôles FIELD masqués, le clic récent du Hub limité au journal et l'attente RE de 300 s sont visibles dans le code. Les durées réellement ressenties, les problèmes de focus/modalité et les pertes de thème résiduelles demandent une reproduction interactive. Les déclarations initiales « harnais limité au clair », « thème non persisté » et « styles inline tous figés » étaient contredites par les mécanismes existants ; elles sont corrigées ci-dessous. L'ordre révisé du §13 prévaut sur les sévérités initiales des fiches de modules. Les changements de calcul liés à `Avg`, aux budgets STRAT et aux valeurs physiques par défaut ne sont pas de simples retouches visuelles ; voir aussi [designargon.md](designargon.md).

---

## 1. Synthèse exécutive & Mesures de référence (`audit_ux_certus.py`)

### 1.1 Relevé instrumenté sur les 11 fenêtres (`2026-10-16`)

Rejeu du 2026-10-16 : 11 modules × 2 résolutions via `python -B scripts\audit_ux_certus.py --worker MODULE --width W --height H`, séquentiellement. Les 22 workers sortent avec le code 0 ; application de `_verdicts` : 0 cas avec défaut mécanique détecté. Les valeurs ci-dessous sont reproduites dans les sorties conservées. **`tables` signifie tables triables / total, pas couverture des états vides.** L'ordre des couches est une donnée : ne pas activer le tri d'une pile d'entrée pour améliorer cette métrique.

#### Résolution `1920x1080` (Full HD — poste de travail)

| Module | Part graphe (`plot%`) | Panneau gauche (`px`) | `minWidth` panneau (`px`) | Raccourcis installés (`keys`) | Tables triables / total (`tables`) | Statut harnais |
|---|---:|---:|---:|---:|---:|---|
| `CERTUS_HUB` | n/a | `None` | `None` | 11 | `0/0` | `OK` |
| `CERTUS_DESIGN` | `73.9%` | `500` | `351` | 21 | `0/3` | `OK` |
| `CERTUS_STRAT` | `71.0%` | `556` | `426` | 20 | `1/2` | `OK` |
| `CERTUS_RE` | `73.9%` | `500` | `315` | 20 | `0/2` | `OK` |
| `CERTUS_INDEX` | `71.5%` | `545` | `307` | 16 | `2/2` | `OK` |
| `CERTUS_INDEX_SPLINE` | `72.4%` | `523` | `280` | 17 | `3/3` | `OK` |
| `CERTUS_FIELD` | `79.1%` | `400` | `296` | 17 | `2/4` | `OK` |
| `CERTUS_SMOOTHER` | n/a | `None` | `None` | 6 | `0/0` | `OK` |
| `CERTUS_SUBSTRATE_INDEX` | n/a | `None` | `None` | 6 | `0/0` | `OK` |
| `CERTUS_METAL_SINGLE` | `71.1%` | `554` | `409` | 17 | `0/0` | `OK` |
| `CERTUS_METAL_BILAYER` | `71.1%` | `554` | `387` | 17 | `0/0` | `OK` |

#### Résolution `1366x768` (portable de salle blanche / banc de dépôt)

| Module | Part graphe (`plot%`) | Panneau gauche (`px`) | `minWidth` panneau (`px`) | Raccourcis installés (`keys`) | Tables triables / total (`tables`) | Statut harnais |
|---|---:|---:|---:|---:|---:|---|
| `CERTUS_HUB` | n/a | `None` | `None` | 11 | `0/0` | `OK` |
| `CERTUS_DESIGN` | `66.0%` | `462` | `351` | 21 | `0/3` | `OK` |
| `CERTUS_STRAT` | `67.2%` | `446` | `426` | 20 | `1/2` | `OK` |
| `CERTUS_RE` | `66.0%` | `462` | `315` | 20 | `0/2` | `OK` |
| `CERTUS_INDEX` | `66.0%` | `462` | `307` | 16 | `2/2` | `OK` |
| `CERTUS_INDEX_SPLINE` | `72.5%` | `370` | `280` | 17 | `3/3` | `OK` |
| `CERTUS_FIELD` | `70.6%` | `400` | `296` | 17 | `2/4` | `OK` |
| `CERTUS_SMOOTHER` | n/a | `None` | `None` | 6 | `0/0` | `OK` |
| `CERTUS_SUBSTRATE_INDEX` | n/a | `None` | `None` | 6 | `0/0` | `OK` |
| `CERTUS_METAL_SINGLE` | `71.0%` | `394` | `387` | 17 | `0/0` | `OK` |
| `CERTUS_METAL_BILAYER` | `71.0%` | `394` | `387` | 17 | `0/0` | `OK` |

### 1.2 Portée du harnais et angles morts

Le résultat 0/22 porte sur les critères de `_verdicts`, à l'ouverture hors écran, sur les widgets que le harnais observe. Il ne couvre pas tous les états, les gestes clavier réels, les dialogues après calcul, les DPI réels ni le rendu de l'exécutable gelé. Part d'écran des graphes mesurée : au moins `66%` en `1366x768` et `71%` en `1920x1080` sur les 8 modules à `QSplitter`.

Cependant, l'analyse approfondie du code et des parcours interactifs met en évidence **6 angles morts majeurs du harnais automatique** et **plusieurs ruptures d'expérience utilisateur** :
1. **Couverture des interactions encore partielle** : le harnais bascule déjà le thème via `CertusThemeToggle.toggle()` et renseigne `dark_stale`, `low_contrast_light` et `low_contrast_dark`. Les angles morts à traiter concernent notamment zoom, dialogues, validation numérique, détachement et fin de calcul ; le thème sombre n'est pas une capacité entièrement absente.
2. **Thème et zoom : défauts résiduels à isoler** : les caches de palette du réticule peuvent conserver des valeurs initiales, tandis que `update_global_plot_config` remet déjà à jour fonds et axes existants. Le zoom remplace la feuille de fenêtre et doit être testé avec les styles locaux et les unités `px`/`pt` ; aucun défaut universel de tous les graphes n'est établi.
3. **Fonctionnalités de façade ("Placebo UX") ou trompeuses** : bandeau de fichiers récents du Hub qui ne fait que journaliser le clic sans ouvrir le fichier (`_on_recent_config_selected`), visite guidée (`certus_tours_catalog.py`) de `CERTUS-STRAT` qui décrit un tout autre logiciel (ajustement de spectre Excel/CSV au lieu de la simulation Monte-Carlo de contrôle de dépôt), raccourcis de zoom du menu Aide du Hub qui ne font rien.
4. **Frictions dans les flux de travail quotidiens** : popups modales `QMessageBox.information` bloquantes à chaque copie presse-papiers d'un graphe (`Ctrl+Shift+C`), perte des info-bulles originales après validation numérique (`attach_numeric_validator`), perte du suivi de courbes (`_tracked_curves`) lors du détachement d'un graphe (`clone_plot_widget`).
5. **États vides à tester en interaction** : `CertusEmptyStateMixin._auto_install_empty_states` installe déjà des overlays riches sur les tables nommées et les autres tables persistables. La colonne `tables` ne permet aucune conclusion sur leur couverture (§2.3).
6. **Services transversaux hétérogènes** : inventorier les capacités réellement manquantes de HUB, SMOOTHER et SUBSTRATE_INDEX. L'absence d'héritage `CertusBaseApp` ou de `QSplitter` ne prouve pas à elle seule l'absence de thème, de persistance ou de notifications ; une composition ciblée peut éviter une migration complète.

### 1.3 Preuves ciblées et limites

Les identifiants renvoient au JSON et au script liés en tête. Les sondes exécutent les corps de méthodes extraits à l'AST, avec dépendances contrôlées explicites ; les décorateurs Numba sont retirés. Elles **ne valident pas le JIT, une session complète ni les performances**. « Observation vérifiée » peut signifier qu'un défaut a été reproduit.

| Observation | Résultat vérifié | Limite |
|---|---|---|
| U01 — snapshot DESIGN | **[CORRIGÉ `868db8c9`]** 2 couches → 1 ; la couche supprimée est fixe ; snapshot JSON produit. | Table et dépendances UI contrôlées ; sauvegarde/export/fermeture complets à couvrir. |
| D08 — filtre final DESIGN | **[CORRIGÉ `bdcae9ed`]** Couche fixe de 2 nm supprimée par `_apply_5nm_minimum`, couche de 5 nm conservée. | Dépendances UI contrôlées ; mérite optique final à remesurer après réparation. |
| U02/U03 — SPLINE | Deux installations Ctrl+O donnent un seul raccourci ; commande `file.load_config` découverte et callback exécuté. | Signal Qt émis directement ; aucun aller-retour JSON complet. |
| U04/U05 — aide et palette | Info-bulle d'origine effacée ; palette du réticule inchangée jusqu'à vidage du cache. | Aucun défaut universel de propagation du thème démontré. |
| U06/U10 — progression | `ProgressDialog` lit `info_label` absent ; handler RE + vrai `EnhancedProgressWidget` lève `AttributeError` sur méthode absente. | Pas de calcul RE complet ; comportement du gestionnaire global d'exceptions Qt à vérifier. |
| U07 — détachement | Courbe et nom copiés ; métadonnées de suivi et formateur personnalisés absents du clone. | Fabrique de clone contrôlée ; pas de preuve générale de perte des unités d'axes ou des légendes. |
| U08 — SMOOTHER | **[CORRIGÉ `8c6d951b`]** `[500.0123, 500.0437, 501.0789]` devient `[500.0, 500.0, 501.1]`. | Lecteur réel, fournisseur Excel contrôlé ; fichier original inchangé par la sonde. |
| U09 — états vides | Dispatch automatique vers 3 tables Qt, dont 2 avec CTA. | Attachement simulé ; visibilité et fonctionnement de l'overlay à tester. |
| U11 — contraste | Ratios des deux couleurs sur `#f8f9fa` : 2,24 et 3,23. | Fond supposé, pas relevé de pixels ni certification WCAG. |

Les 22 squelettes GUI contiennent un bouton `Help`, y compris SPLINE, METAL et les deux utilitaires. La bascule sombre a été exercée dans 18 cas ; elle est absente dans les 4 cas SMOOTHER/SUBSTRATE_INDEX. Les vérifications clair/sombre du harnais restent partielles.

---

## 2. Audit du Socle Transversal & Système de Design (`certus/ui/`)

### 2.1 Thème, Typographie, Contraste & Zoom UI
**Fichiers examinés** : [`certus/ui/certus_theme.py`](certus/ui/certus_theme.py), [`certus/ui/mixins/certus_base_core_mixins.py`](certus/ui/mixins/certus_base_core_mixins.py), [`certus/ui/certus_plot.py`](certus/ui/certus_plot.py), [`certus/ui/certus_ui_utils.py`](certus/ui/certus_ui_utils.py).

#### Constats & Défauts identifiés
- **[À REPRODUIRE] Palettes mises en cache dans les graphes** :
  `get_plot_style_config()` et `get_plot_theme_palette()` portent bien un cache sans argument dans [`certus_plot.py`](certus/ui/certus_plot.py). Cependant, la bascule active est `CertusThemeToggle.toggle` dans [`certus_ui_widgets_utils.py`](certus/ui/certus_ui_widgets_utils.py) : elle sauvegarde la préférence, configure la palette et appelle `update_global_plot_config`, qui met à jour les fonds et axes existants. Le diagnostic « les graphes ne changent jamais » était donc trop large. Reproduire séparément fond, axes, courbes et bulle du réticule après clair → sombre → clair ; les chaînes de palette mises en cache restent suspectes.
- **[CONSTAT STATIQUE] Le zoom remplace la feuille de fenêtre** :
  `CertusZoomMixin._apply_ui_zoom` appelle `self.setStyleSheet(get_standard_stylesheet())`, tandis que `apply_certus_theme` compose initialement cette feuille avec `build_premium_overrides()` et les overrides de l'appelant. Ces ajouts ne sont pas explicitement réinjectés par le zoom. Les styles locaux en pixels peuvent aussi limiter la mise à l'échelle. Le rendu, la taille effective et la portée du défaut restent à mesurer ; les comptages typographiques initiaux ne sont pas utilisés comme preuve.
- **[MAJEUR] Logo sombre peu lisible en mode Dark (Défaut ouvert D82 dans `docs/ETAT.md §4`)** :
  `create_header_logo_widget` ([`certus/ui/certus_ui_widgets_factory.py`](certus/ui/certus_ui_widgets_factory.py)) charge [`certus.svg`](certus.svg) tel quel en mode clair comme en mode sombre. De plus, le détecteur `low_contrast_sheets` de [`scripts/audit_ux_certus.py`](scripts/audit_ux_certus.py) ne contrôle que les règles QSS locales déclarant *simultanément* `color` et `background-color` dans le même bloc, laissant passer tout widget dont la couleur de texte hérite de la palette sur un fond sombre hérité du parent.
- **[À REPRODUIRE] Styles locaux échappant au rafraîchissement existant** :
  [`CertusTheme.refresh_widget_sheets`](certus/ui/certus_theme.py) réécrit déjà les couleurs annotées par leur jeton ; `CertusThemeToggle.toggle` l'appelle et invoque les méthodes `refresh_theme` des descendants. Une f-string locale n'est donc pas, à elle seule, une preuve de couleur figée. Identifier les styles qui échappent réellement à ces mécanismes avant toute migration de sélecteurs.

#### Pistes d'amélioration (Thème, Typographie & Zoom)
1. **Cache de palette : correctif après reproduction** : supprimer le cache inutile ou le faire dépendre du thème, puis tester les deux allers-retours de thème et le réticule. Brancher le correctif sur le chemin actif `CertusThemeToggle.toggle`, en préservant les appels existants ; ne pas supposer l'existence de `CertusTheme.set_dark_mode` ni ajouter un cycle d'import thème/graphe.
2. **Préservation complète du QSS lors du Zoom UI** : Dans `CertusZoomMixin._apply_ui_zoom`, appeler `apply_certus_theme(self, overrides=getattr(self, "_certus_theme_overrides", None))` (en mémorisant `overrides` lors de l'application initiale dans `apply_certus_theme`) au lieu de `self.setStyleSheet(CertusTheme.get_standard_stylesheet())`.
3. **Typographie et zoom à valider au rendu** : utiliser des jetons cohérents et une mise à l'échelle explicite. Ne pas remplacer globalement `px` par `pt` sans conversion ni contrôle : 11 px et 11 pt ne sont pas équivalents, les styles locaux peuvent primer et changer d'unité ne garantit pas que le zoom les atteigne. Préserver la lisibilité, la géométrie et les préférences aux DPI représentatifs.
4. **Sélecteurs partagés : simplification optionnelle** : les styles locaux à jetons sont déjà rafraîchis. Ne les déplacer vers des sélecteurs que si cela simplifie une duplication ou corrige un défaut reproduit ; conserver les variantes locales et vérifier les pixels dans les deux thèmes.
5. **Variante Dark du logo (`D82`)** : Générer ou recolorer dynamiquement les chemins sombres de [`certus.svg`](certus.svg) (à l'instar de [`certus/ui/certus_icons.py`](certus/ui/certus_icons.py)) lorsque `CertusTheme.DARK_MODE` est actif.

---

### 2.2 Graphes Scientifiques (`CertusScientificPlot`) & Fenêtres Détachées
**Fichiers examinés** : [`certus/ui/certus_plot.py`](certus/ui/certus_plot.py), [`certus/ui/certus_base_app_plot_mixin.py`](certus/ui/certus_base_app_plot_mixin.py), [`certus/ui/certus_ui_widgets_utils.py`](certus/ui/certus_ui_widgets_utils.py).

#### Constats & Défauts identifiés
- **[MAJEUR] Popups modales bloquantes `QMessageBox.information` à chaque copie dans le presse-papiers** :
  Dans `CertusScientificPlot._copy_excel_tsv` et `_copy_publication_tsv` ([`certus/ui/certus_plot.py`](certus/ui/certus_plot.py)), presser `Ctrl+Shift+C` ou `Ctrl+Shift+B` (ou cliquer sur `Copy data` / `Pub copy`) ouvre une boîte de dialogue modale `QMessageBox.information` qui bloque tout le flux de travail jusqu'à ce que l'opérateur clique sur « OK » ou presse Entrée. De même pour `_export_png`, `_export_svg`, `_export_csv`, `_export_tsv`. Alors que la suite dispose d'un système de notifications non bloquantes `show_toast_stack` ([`certus/ui/certus_toast_stack.py`](certus/ui/certus_toast_stack.py)), il n'est pas utilisé ici.
- **[REPRODUIT SUR SONDE] Métadonnées de suivi absentes du clone (`clone_plot_widget`)** :
  [`clone_plot_widget`](certus/ui/certus_plot.py) copie les courbes avec leurs options et noms, les étiquettes d'axes et plusieurs réglages visuels. U07 vérifie que `_tracked_curves`, `_certus_crosshair_label_fn` et `_certus_crosshair_vertical_only` ne sont pas transférés. La perte du formateur métier est établie ; le comportement du survol, les unités et la reconstruction des légendes doivent être contrôlés sur chaque type de graphe. Aucun échec de l'API `getLabel` n'a été reproduit avec le pyqtgraph installé.
- **[MODÉRÉ] Deux mécanismes de détachement concurrents dans `CertusAppPlotMixin`** :
  [`certus/ui/certus_base_app_plot_mixin.py`](certus/ui/certus_base_app_plot_mixin.py) définit à la fois `open_detached_certus_plot(source_plot)` (qui indexe `self.detached_plot_windows` par `f"certus_detach_{id(source_plot)}"` et produit un clone **statique** qui n'est jamais rafraîchi quand un calcul tourne) et `detach_current_plot()` (qui indexe par `plot_name` logique comme `"spectrum"` ou `"convergence"`, utilisé par `_get_plot_targets` pour les mises à jour temps réel). Cliquer sur « Detach » dans la barre d'outils d'un graphe appelle `open_detached_certus_plot` (`certus_detach_<id>`), de sorte que le graphe détaché **ne se met pas à jour pendant l'optimisation** !
- **[MINEUR] Redondance de la barre d'outils des graphes (`get_toolbar`)** :
  La barre au-dessus de chaque graphe aligne 6 boutons (`Reset`, `Detach`, `Copy data`, `Pub copy`, `CSV`, `Export ▾`), chacun forcé à `minWidth = 64 px` (`ClickTarget.MIN_WIDTH`), soit ~430 px minimum. Or `Copy data`, `Pub copy` et `CSV` figurent déjà dans le menu `Export ▾` et dans le menu contextuel du clic droit. Sur un écran `1366x768` ou lorsque deux graphes sont côte à côte, cette barre de 6 boutons crée une surcharge visuelle inutile.
- **[MINEUR] Docstring erronée sur le raccourci de détachement** :
  La docstring de `CertusScientificPlot` indique `Detach to new window (Ctrl+D)` alors que le raccourci réel est `Ctrl+Shift+D` (`Ctrl+D` étant utilisé dans le Hub pour lancer DESIGN).

#### Pistes d'amélioration (Graphes & Fenêtres détachées)
1. **Remplacer les `QMessageBox.information` de succès d'export/copie par des Toasts (`show_toast`)** : Lors d'un `Ctrl+Shift+C` / `Ctrl+Shift+B` ou d'un export fichier réussi, afficher un toast `success` de 2,5 s (`"Copied to clipboard (Excel TSV)"` ou `"Exported plot.svg"`) et réserver `QMessageBox.warning` aux seuls cas d'erreur.
2. **Enrichir `clone_plot_widget` et unifier les clés de `detached_plot_windows`** : Copier `_certus_crosshair_label_fn`, `_certus_crosshair_vertical_only`, et reconstruire `_tracked_curves` dans le graphe cloné en associant chaque courbe clonée par son nom. Unifier `open_detached_certus_plot` et `_get_plot_targets` pour que tout graphe détaché reçoive les mises à jour en direct.
3. **Alléger la barre d'outils `get_toolbar`** : Garder 4 actions directes (`Reset`, `Detach`, `Copy data`, `Export ▾`) et regrouper `Pub copy` et `CSV` dans le menu `Export ▾` (tout en conservant leurs raccourcis clavier `Ctrl+Shift+B` et le clic droit).

---

### 2.3 Validation Numérique, Accessibilité (`certus_a11y`) & États Vides (`certus_empty_state`)
**Fichiers examinés** : [`certus/ui/certus_ui_utils.py`](certus/ui/certus_ui_utils.py), [`certus/ui/certus_a11y.py`](certus/ui/certus_a11y.py), [`certus/ui/certus_empty_state.py`](certus/ui/certus_empty_state.py).

#### Constats & Défauts identifiés
- **[MAJEUR] `attach_numeric_validator` écrase définitivement l'info-bulle d'aide du champ (`setToolTip("")`)** :
  **[AMENDÉ]** Dans `attach_numeric_validator` ([`certus/ui/certus_ui_utils.py`](certus/ui/certus_ui_utils.py)), la fonction interne `_validate()` exécute `line_edit.setToolTip("")` quand le texte est vide ou valide, et pose `"Invalid {kind} value"`, `"Value must be >= {minimum}"` ou `"Value must be <= {maximum}"` sinon. Elle ne sauvegarde jamais le `line_edit.toolTip()` d'origine, et `_validate()` s'exécute dès l'attachement : **une info-bulle posée avant l'attachement disparaît aussitôt** ; une info-bulle posée après disparaît à la première frappe.
- **[CAPACITÉ EXISTANTE] Installation automatique des états vides riches** :
  `install_common_affordances` appelle `CertusEmptyStateMixin._auto_install_empty_states` dans [certus_base_core_mixins.py](certus/ui/mixins/certus_base_core_mixins.py). Ce dernier utilise `attach_empty_state_to`, avec icône, texte et CTA lorsqu'un callback existe, puis parcourt les autres tables persistables. U09 reproduit ce dispatch. L'absence d'un appel local nommé `attach_empty_table_hint` ne prouve donc pas l'absence d'overlay. Les chiffres 8/16 déduits de `tables` mesuraient le tri ; aucune couverture d'états vides n'a été mesurée par cette colonne.
- **[À TESTER] Visibilité et action des overlays** :
  Certaines erreurs d'attachement sont absorbées. Tester chaque table réellement vide, son remplissage puis son retour à vide, le CTA, le focus et l'accès aux cellules. La présence du mécanisme ne prouve pas son bon fonctionnement dans chaque état.

#### Pistes d'amélioration (Validation, Accessibilité & États vides)
1. **Sauvegarder l'info-bulle originale dans `attach_numeric_validator`** : Mémoriser `orig_tip = line_edit.toolTip()` avant d'attacher le validateur (ou à la volée si non vide et ne commençant pas par `"Expected "`), et restaurer `line_edit.setToolTip(orig_tip)` lorsque la saisie redevient valide. En cas d'erreur, combiner `f"⚠ Expected value in [{lo}, {hi}]\n\n{orig_tip}"`.
2. **Mesurer la couverture réelle des overlays existants** : inventaire des tables et transitions vide → rempli → vide, activation du CTA et contrôle du viewport. Corriger les seuls manques reproduits ; conserver une métrique distincte du tri des tableaux.

---

### 2.4 Onboarding (`certus_onboarding.py` & `certus_tours_catalog.py`)
**Fichiers examinés** : [`certus/ui/certus_onboarding.py`](certus/ui/certus_onboarding.py), [`certus/ui/certus_tours_catalog.py`](certus/ui/certus_tours_catalog.py).

#### Constats & Défauts identifiés
- **[CRITIQUE] Le tour guidé de `CERTUS-STRAT` (`_steps_strat`) décrit un mauvais programme** :
  Dans [`certus/ui/certus_tours_catalog.py`](certus/ui/certus_tours_catalog.py), `_steps_strat()` affiche :
  - Step 1 : *"Welcome to CERTUS-STRAT — Stratified fits across strategies - choose the approach that best fits your data."*
  - Step 2 : *"Pick a strategy & input — Load your measurement file (Excel or CSV) - samples are available in samples/spectrum/."* en ciblant `target_attr="measurement_table"` (attribut qui n'existe pas dans `CERTUS-STRAT`).
  Or `CERTUS-STRAT` n'est **pas** un outil d'ajustement de spectre mesuré Excel/CSV : c'est le simulateur Monte-Carlo et optimiseur de stratégies de contrôle optique/quartz (OMS / Rate) pour le dépôt de couches minces multicouches ! Ce texte induit gravement en erreur un nouvel utilisateur qui lance `Help -> Show welcome tour` dans `CERTUS-STRAT`.
- **[MAJEUR] Étapes d'onboarding sans cible (`target_attr=None`) ou avec attributs introuvables** :
  **[AMENDÉ]** `certus_tours_catalog.py` définit 7 visites (`DESIGN`, `INDEX`, `STRAT`, `INDEX_SPLINE`, `FIELD`, `METAL`, `RE`). Celles d'`INDEX`, d'`INDEX_SPLINE` et de `METAL` n'ont **aucune** étape ciblée (`target_attr` omis, donc `None`) ; `DESIGN` en cible 3, `FIELD` 3, `RE` 1, `STRAT` 1 (inexistante, ci-dessus). Les étapes générales (`target_attr=None`) sont centrées. Les cibles absentes sont retirées par `filter_resolvable_steps`, et non transformées en carte centrée ; une visite peut donc perdre une instruction. Les cibles d’onglets masqués demandent un contrôle de visibilité. Aucun tour n'existe pour `CERTUS_HUB`, `CERTUS_SMOOTHER` ou `CERTUS_SUBSTRATE_INDEX`.
- **[MODÉRÉ] Absence de navigation clavier et case « Ne plus afficher » morte dans `_OnboardingOverlay`** :
  Dans [`certus/ui/certus_onboarding.py`](certus/ui/certus_onboarding.py) :
  - `self._dont_show` est initialisé à `None`, mais aucune checkbox n’est construite. Les actions Skip et Finish marquent déjà le tour comme terminé via `_on_skip`/`_on_next` ; la décision de proposer un contrôle « Ne plus afficher » reste ergonomique, pas une case visible cassée.
  - `_OnboardingOverlay` n'implémente pas `keyPressEvent` : appuyer sur `Échap` (`Esc`) ne ferme pas la visite guidée, et les flèches `Droite`/`Gauche` ou `Entrée` ne permettent pas d'avancer ou reculer dans les étapes.

#### Pistes d'amélioration (Onboarding)
1. **Réécrire `_steps_strat()` dans `certus_tours_catalog.py`** pour refléter le vrai flux de travail de `CERTUS-STRAT` : (1) Chargement du design JSON multicouche (`load_json_btn` / onglet Welcome), (2) Paramétrage des bruits de dépôt et du contrôle optique/quartz (OMS / témoins / Rate), (3) Lancement de l'évaluation Monte-Carlo ou de la recherche de stratégies (`F5`), (4) Analyse du classement SEEL, du taux de plantage et des heatmaps d'erreur.
2. **Relier chaque étape de `certus_tours_catalog.py` à un `target_attr` réel** (et sélectionner l’onglet parent avant de calculer `_spotlight_rect()`).
3. **Ajouter le support clavier (`Esc`, `Left`, `Right`, `Enter`) dans `_OnboardingOverlay.keyPressEvent`** et ajouter le tour manquant de `CERTUS_HUB`.

---

### 2.5 Palette de Commandes (`Ctrl+K`), Cheatsheet Raccourcis (`F1`) & Barres de Progression
**Fichiers examinés** : [`certus/ui/mixins/certus_base_core_mixins.py`](certus/ui/mixins/certus_base_core_mixins.py), [`certus/ui/certus_shortcuts_overlay.py`](certus/ui/certus_shortcuts_overlay.py), [`certus/ui/certus_ui_widgets_progress.py`](certus/ui/certus_ui_widgets_progress.py).

#### Constats & Défauts identifiés
- **[MAJEUR] Bug latent (`AttributeError`) dans `ProgressDialog.apply_progress_snapshot`** :
  Dans [`certus/ui/certus_ui_widgets_progress.py`](certus/ui/certus_ui_widgets_progress.py), la méthode `ProgressDialog.apply_progress_snapshot` tente d'accéder à `self.info_label`, `self.stage_header`, `self._stage_value_label`, `self._overall_value_label` et `self._display_progress` — des attributs qui appartiennent à `DualStageProgressWidget` et **n'existent pas** sur `ProgressDialog` (qui possède uniquement `title_label`, `progress_bar`, `status_label`, `cancel_btn`, `detail_label`).
- **[REPRODUIT SUR SONDE, P1] Contrat de progression RE incompatible** :
  `CertusRELayoutMixin` construit un `EnhancedProgressWidget` (alias de `DualStageProgressWidget`) qui ne possède pas `apply_progress_snapshot`. `_on_re_worker_progress_snapshot` l'appelle pourtant ; U10 reproduit l'`AttributeError` avec les vrais objets Qt. `NUMERICAL_FAULT_EXCEPTIONS` n'inclut pas cette exception. Le signal est connecté dans `launch_re` et émis par `REWorker.run` ; l'effet exact sur une session et le gestionnaire global Qt reste à vérifier. Corriger seulement `ProgressDialog` ne répare pas ce contrat.
- **[MODÉRÉ] Incohérence d'affichage dans `DualStageProgressWidget.stop()` et `reset()`** :
  - Dans `DualStageProgressWidget.stop()`, lorsqu'un calcul se termine normalement (`not self._is_canceled`), le bouton d'annulation `self.cancel_btn` (stylé en rouge `CertusTheme.get_button_style("danger")`) voit son texte remplacé par `"Done"` tout en restant visible et rouge/désactivé, ce qui donne l'impression visuelle d'une alerte rouge « Done ».
  - Dans `DualStageProgressWidget.reset()`, `self.detail_label` reçoit `self._build_detail_status(status="idle", next_action="start run")` qui affiche une chaîne brute `status=idle • next_action=start run`, alors que `_setup_ui()`, `start()`, `update()` et `stop()` utilisent `_format_progress_status(...)` (`Status: Idle • Next: start run`).
- **[MODÉRÉ] Discordance entre `Ctrl+R` (Palette de commandes) et `F5` (Raccourci standard) pour lancer le calcul** :
  Dans `CertusCommandPaletteMixin._default_commands` ([`certus/ui/mixins/certus_base_core_mixins.py`](certus/ui/mixins/certus_base_core_mixins.py)), l'action `run.optimize` déclare `shortcut="Ctrl+R"`. Or le raccourci vital installé partout par `install_standard_shortcuts` est `F5` (`Ctrl+R` est absent de `_STANDARD_LABELS` dans [`certus/ui/certus_shortcuts_overlay.py`](certus/ui/certus_shortcuts_overlay.py) et donc filtré si non lié comme `QShortcut`).
- **[MINEUR] `CertusAppUndoMixin` (`Ctrl+Z`) limité aux seules tables `front_table` de `DESIGN` et `RE`** :
  [`certus/ui/certus_base_app_undo_mixin.py`](certus/ui/certus_base_app_undo_mixin.py) ne gère que la pile `undo_stack` de `front_table` sans pile `redo_stack` (`Ctrl+Y` / `Ctrl+Shift+Z`), et sans support des modifications de `back_table` ou `target_table`.

#### Pistes d'amélioration (Palette, Raccourcis & Progression)
1. **Réparer les deux contrats de progression** : fournir l'application de snapshot sur `DualStageProgressWidget`/`EnhancedProgressWidget`, et adapter celle de `ProgressDialog` à ses propres widgets. Tester un vrai snapshot du worker RE, les ratios indéterminés, phases et ETA. Harmoniser séparément `reset()` et l'état visuel de fin ; déplacer aveuglément une méthode ne prouve pas la compatibilité des deux classes.
2. **Aligner `run.optimize` sur `shortcut="F5"`** dans `CertusCommandPaletteMixin._default_commands`.
3. **Ajouter une pile `redo_stack` (`Ctrl+Y` / `Ctrl+Shift+Z`)** dans `CertusAppUndoMixin` et étendre les snapshots d'annulation à l'ensemble de l'empilement (`front_table`, `back_table`, `target_table`).

---

## 3. Audit du Lanceur Central : `CERTUS_HUB`

**Fichiers examinés** : [`CERTUS_HUB.py`](CERTUS_HUB.py), [`certus/ui/certus_hub_widgets.py`](certus/ui/certus_hub_widgets.py), [`certus/ui/certus_recent_strip.py`](certus/ui/certus_recent_strip.py).

### 3.1 Architecture & Cohérence avec la Suite
- **`CertusHub` n'hérite pas de `CertusBaseApp`** (`class CertusHub(CertusDialogMixin, QMainWindow)` dans [`CERTUS_HUB.py`](CERTUS_HUB.py)) :
  Il réimplémente manuellement la gestion du thème (`_apply_theme` et bouton de bascule), de la géométrie (restauration dans `__init__`), des logs (`_log_message`) et des menus, ce qui crée plusieurs divergences d'expérience :
  - **Pas de palette de commandes `Ctrl+K` / `Ctrl+Shift+P`** sur le Hub, alors que le Hub est justement le point d'entrée idéal pour taper `Ctrl+K` puis le nom d'un module, d'un fichier récent ou d'un outil !
  - **Actions de Zoom factices dans le menu Help** : Dans `_install_help_menu()` ([`CERTUS_HUB.py`](CERTUS_HUB.py)), les actions `Zoom In (Ctrl++)`, `Zoom Out (Ctrl+-)` et `Reset Zoom (Ctrl+0)` sont reliées à `lambda: self._log_message("Zoom in is handled in child windows")`. L'utilisateur qui clique sur `Help -> Zoom In` dans le Hub ne voit aucun changement visuel (et si le panneau System Log est replié, il n'a strictement aucun retour).

### 3.2 Défauts UX & Frictions identifiés dans `CERTUS_HUB`
- **[CRITIQUE] Cliquer sur un fichier récent dans le bandeau du Hub ne fait rien (`_on_recent_config_selected`)** :
  Dans [`CERTUS_HUB.py`](CERTUS_HUB.py), `attach_recent_files_strip()` instancie `build_recent_files_strip(self, category=RecentCategories.CONFIG, limit=5, title="Recent:", on_open=self._on_recent_config_selected)`. Or la méthode `_on_recent_config_selected(self, path: str)` contient uniquement :
  ```python
  self._log_message(f"Recent file selected: {path}", "INFO")
  ```
  **Aucune ouverture de fichier ni lancement du sous-programme correspondant n'est effectué !** L'utilisateur clique sur une pilule « Recent: » en haut du Hub, rien ne se passe à l'écran (le log étant replié par défaut).
- **[MODÉRÉ] Raccourcis clavier de lancement partiels (5 modules sur 10)** :
  `_setup_shortcuts()` dans [`CERTUS_HUB.py`](CERTUS_HUB.py) définit uniquement `Ctrl+D` (`DESIGN`), `Ctrl+Shift+S` (`STRAT`), `Ctrl+I` (`INDEX`), `Ctrl+M` (`METAL_SINGLE`) et `Ctrl+F` (`FIELD`). Les 5 autres applications (`RE`, `INDEX_SPLINE`, `METAL_BILAYER`, `SMOOTHER`, `SUBSTRATE_INDEX`) n'ont ni raccourci clavier, ni mention de raccourci sur leur carte.
- **[MODÉRÉ, AMENDÉ] Grille de cartes sans recherche ni filtrage rapide** :
  Le Hub affiche 10 `ApplicationCard` sans sections, sur une grille dont `hub_grid_columns` ([`certus/core/certus_hub_config.py`](certus/core/certus_hub_config.py)) tire 5 colonnes, + un panneau de paramètres d'export + un journal système, le tout dans un `QScrollArea`. Le défilement nécessaire en `1366x768` n'est pas mesuré. Il n'existe ni barre de filtre rapide ni lancement par numéro (`1`..`9` ou `Ctrl+K`).
- **[MINEUR] Coquille dans l'info-bulle d'export automatique** :
  Dans `CertusHub.__init__` ([`CERTUS_HUB.py`](CERTUS_HUB.py)), l'info-bulle de `self.chk_export` contient `"Automatically generate Excel/HTML reports after calculationation."` (`calculationation`).
- **[MINEUR, AMENDÉ] `GroupedApplicationCard` inachevée dans `certus_hub_widgets.py`** :
  Dans [`certus/ui/certus_hub_widgets.py`](certus/ui/certus_hub_widgets.py), `GroupedApplicationCard.__init__` ne lance que `sub_apps[0]["script"]` : tout sous-programme d'indice `>= 1` serait inaccessible. Aucune entrée de `_build_hub_apps_catalog` n'a `"type": "group"` : la classe n'est pas instanciée aujourd'hui.

### 3.3 Pistes d'amélioration pour `CERTUS_HUB`
1. **Rendre le bandeau « Recent: » réellement fonctionnel (`_on_recent_config_selected`)** : Inspecter le fichier JSON sélectionné (ou associer chaque entrée récente au module qui l'a enregistrée via `RecentCategories` / métadonnées du JSON) et lancer le sous-programme correspondant en lui passant le chemin du fichier à charger automatiquement à l'ouverture (ou l'ouvrir dans l'instance déjà active de `self.child_windows`).
2. **Brancher la Palette de Commandes (`Ctrl+K`) et le vrai Zoom UI sur `CertusHub`** : Permettre d'ouvrir n'importe lequel des 10 sous-programmes, de basculer le thème, d'ouvrir un fichier récent ou de régler les options d'export depuis `Ctrl+K`, et relier `Ctrl++`/`Ctrl+-`/`Ctrl+0` au vrai zoom typographique au lieu d'un message de log.
3. **Afficher un badge de raccourci (`CertusKbd`) sur chaque `ApplicationCard`** et compléter les raccourcis pour les 10 modules (ex. `Ctrl+R` pour `RE`, `Ctrl+Shift+I` pour `INDEX_SPLINE`, `Ctrl+Shift+M` pour `METAL_BILAYER`).
4. **Corriger la coquille `"calculationation"` -> `"calculation"`** dans `CertusHub.__init__`.

---

## 4. Audit de `CERTUS_DESIGN` (`CertusDesignApp`)

### 4.1 Architecture et rôle dans le workflow

Le module [`certus_design_ui.py`](certus/ui/certus_design_ui.py) (assemblant [`certus_design_ui_core.py`](certus/ui/certus_design_ui_core.py), [`certus_design_ui_layout.py`](certus/ui/certus_design_ui_layout.py), [`certus_design_ui_events.py`](certus/ui/certus_design_ui_events.py), [`certus_design_ui_plot.py`](certus/ui/certus_design_ui_plot.py), [`certus_design_ui_optimization.py`](certus/ui/certus_design_ui_optimization.py), [`certus_design_ui_export.py`](certus/ui/certus_design_ui_export.py), [`certus_design_ui_state.py`](certus/ui/certus_design_ui_state.py) et [`certus_design_ui_worker.py`](certus/ui/certus_design_ui_worker.py)) est l'atelier de synthèse et d'optimisation d'empilements multicouches (Needle profond, polissage local, PGLOBAL, front de Pareto).

L'interface repose sur un `QSplitter` horizontal :
- **Panneau gauche** (`minimumWidth = 351 px`, dans un `QScrollArea`) : un `QTabWidget` (`left_tabs`) à 3 onglets (`Structure`, `Targets`, `Optimization`) surmontant une carte `Actions` épinglée en bas (`Evaluate`, `Polish local`, `PGLOBAL`, `Drop thinnest layer`, `Colorimetric analysis`, `Stack info`).
- **Panneau droit** : un `QTabWidget` (`plot_tabs`) à 6 onglets (`✦ Synthesis`, `Spectrum (T)`, `Profile`, `n(λ)`, `Color`, `Convergence`), complété par une barre d'état locale dotée d'un `DualStageProgressWidget` et d'un bouton `STOP`.

### 4.2 Points forts observés

- **Séparation claire entre configuration par onglets et actions permanentes** : la carte `Actions` reste accessible quel que soit l'onglet actif (`Structure`, `Targets`, `Optimization`).
- **Validation pré-vol explicite avant optimisation** : `WorkerManager.run_optim` prépare les cibles actives avec `valid()` et crée `OptimWorker`. Une méthode `_preflight_optim` et une classe `UnifiedOptimWorker` ne sont pas présentes dans cette version ; ne pas leur attribuer une validation exhaustive.
- **Feedback temps réel durant l'optimisation** : `DualStageProgressWidget` distingue la progression globale (cycles PGLOBAL / Needle) de la progression locale (itérations L-BFGS-B), tandis que `PlotManager.update_optim_live_plot` rafraîchit le spectre en direct avec limitation de cadence (`_live_plot_min_interval_s = 0.08 s`).
- **Persistance géométrique du splitter et de la fenêtre** via `CertusAppStateMixin` (`certus_design`).

### 4.3 Problèmes UX et fonctionnels identifiés

1. **[PARTIELLEMENT CORRIGÉ] Effet de bord destructeur lors de la lecture de l'état (`StateManager._collect_config` et `ExportManager.export_excel`)** :
   - Corrigé : `StateManager._collect_config` est pur et `save_config` ne nettoie qu'une fois (`868db8c9`) ; `smart_cleanup` et le filtre 5 nm épargnent les couches fixes (`bdcae9ed`).
   - Reste : `ExportManager.export_excel` ([`certus_design_ui_export.py`](certus/ui/certus_design_ui_export.py)) exécute `smart_cleanup()`, qui **modifie en place `front_table`** (suppression des couches sous le seuil, fusion des voisines de même matériau), lors d'un simple export Excel.
2. **[MAJEUR] Fenêtre détachée du profil d'indice (`Profile`) vide (`PlotManager._plot_profile_actual`)** :
   - Dans [`certus_design_ui_plot.py`](certus/ui/certus_design_ui_plot.py), la méthode `PlotManager._plot_profile_actual` itère sur `for plot_widget in self.ui._get_plot_targets("profile", self.ui.profile_plot):`, appelle `plot_widget.plotItem.clear()`, mais trace ensuite la courbe sur `self.ui.profile_plot` (`plot_widget_plot_finite(self.ui.profile_plot, ...)`) au lieu de `plot_widget`.
   - Pour un graphe détaché enregistré sous la clé logique `profile`, la boucle efface cette cible puis retrace sur le widget principal. Le clone générique créé par la barre d’outils utilise une autre clé (§2.2) : son absence de mise à jour est un chemin distinct. Reproduire les deux modes avant de conclure que tout bouton Detach produit une fenêtre vide.
3. **[MAJEUR] Labels d'ordonnées codés en noir (`color="black"`), illisibles en mode sombre (`PlotManager`)** :
   - Dans [`certus_design_ui_plot.py`](certus/ui/certus_design_ui_plot.py), `PlotManager._update_optim_live_plot_normal_mode` et `PlotManager._finalize_oblique_live_plot` configurent l'axe gauche via `self.ui.spectrum_plot.plotItem.setLabel("left", ..., color="black", size="12pt")`.
   - En thème sombre (`#0f172a` / `#1e293b`), le titre de l'axe Y devient noir sur fond sombre dès le premier lancement d'une optimisation.
4. **[MAJEUR] Écrasement silencieux des paramètres PGLOBAL lorsque « Topology growth (deep Needle) » est coché (`WorkerManager.run_optim`)** :
   - Dans [`certus_design_ui_layout.py`](certus/ui/certus_design_ui_layout.py), la case `allow_growth_check` (« Topology growth (deep Needle) ») est cochée par défaut (`setChecked(True)`), tandis que les spinboxes affichent `N100 = 6000`, `Max clusters = 40` et `Global cycles = 50`.
   - Or, dans [`certus_design_ui_worker.py`](certus/ui/certus_design_ui_worker.py), `WorkerManager._capped_global_budgets` plafonne ces valeurs lorsque `allow_growth` est actif (N100 ≤ 1500, cycles ≤ 8, clusters ≤ 5) sans mettre à jour ni griser les spinboxes. L'utilisateur voit `6000 / 40 / 50` à l'écran mais le moteur exécute `1500 / 5 / 8`.
   - **[PARTIELLEMENT CORRIGÉ `7f3edea8`]** Le journal dit `Global+Needle caps (shown -> applied)` ; les spinboxes restent non plafonnées. Le plafonnement est une décision de 👤 (2026-09-29), seul l'affichage est en cause.
5. **[MAJEUR] Conflit de raccourci clavier sur `Ctrl+E` (Evaluate vs Export)** :
   - `EventsManager._setup_shortcuts` (dans [`certus_design_ui_events.py`](certus/ui/certus_design_ui_events.py)) associe `Ctrl+E` à `self.ui.evaluate_stack` (et le bouton affiche `Evaluate (Ctrl+E)`).
   - En parallèle, `CertusBaseApp` et `certus_shortcuts_overlay.py` référencent `Ctrl+E` comme le raccourci standard d'exportation (`Export`) dans l'aide `F1`, tandis que l'export Excel de `CERTUS_DESIGN` est relégué à `Ctrl+Shift+E`.
6. **[MODÉRÉ] Nivellement de la hiérarchie visuelle par abus de `OBJ.PRIMARY_BUTTON` (`LayoutManager`)** :
   - Dans [`certus_design_ui_layout.py`](certus/ui/certus_design_ui_layout.py), **9 boutons** reçoivent l'identifiant `OBJ.PRIMARY_BUTTON` (les 6 boutons de la carte `Actions` : `Evaluate`, `Polish local`, `PGLOBAL`, `Drop thinnest layer`, `Colorimetric analysis`, `Stack info`, ainsi que `Detach`, `Open Pareto Front` et `Logs`).
   - Une hiérarchie d’actions plus sélective est une proposition ergonomique, pas une règle de `CLAUDE.md §6` ; ici, des actions d'inspection secondaire (`Stack info`, `Colorimetric analysis`, `Logs`) ont le même poids visuel que `Evaluate` ou `PGLOBAL`.
7. **[MODÉRÉ] Colonne `Preset` inutile dans la carte `Materials` (`LayoutManager._build_materials_group`)** :
   - Les 6 lignes de matériaux (`H`, `L`, `M1`..`M4`) comportent chacune une liste déroulante `Preset` (`mat_preset_combos`) qui ne contient qu'un seul élément statique : `["Custom"]`. Ces 6 `QComboBox` occupent de la largeur dans un panneau gauche déjà contraint (`351 px`) sans offrir aucune option.
8. **[MODÉRÉ] Ouverture par défaut sur l'onglet `✦ Synthesis` plutôt que sur `Spectrum (T)` (`LayoutManager._build_right_panel`)** :
   - Au lancement, `StateManager._load_defaults` évalue l'empilement initial à 4 couches, mais l'onglet actif de `plot_tabs` est l'index `0` (`✦ Synthesis`), qui n'affiche que 5 cartes KPI au-dessus d'un grand espace vide (`addStretch(1)`), obligeant l'utilisateur à cliquer sur `Spectrum (T)` pour voir la courbe spectrale calculée.
9. **[MINEUR] Fenêtre Pareto orpheline, mélange français/anglais et couleurs codées en dur (`PlotManager`)** :
   - Dans `PlotManager._ensure_pareto_ui` ([`certus_design_ui_plot.py`](certus/ui/certus_design_ui_plot.py)), `parent = self if isinstance(self, QWidget) else None` teste `self` (`PlotManager`, qui n'est pas un `QWidget`) au lieu de `self.ui` (`CertusDesignApp`), de sorte que `pareto_window` est systématiquement créée avec `parent=None`.
   - Le menu contextuel du front de Pareto (`_show_pareto_context_menu` et `_show_catalog_dialog`) est en français (`"Voir le catalogue..."`, `"Charger la configuration"`) au milieu d'une interface intégralement en anglais.
   - `_populate_pareto_table_row` utilise `Qt.GlobalColor.red`, `Qt.GlobalColor.darkGreen` et `Qt.GlobalColor.gray` au lieu des jetons sémantiques de `CertusTheme`.
   - Les états vides des tables sont installés par le socle commun ; leur couverture doit être testée selon §2.3.

### 4.4 Pistes d'améliorations pour `CERTUS_DESIGN`

- **[P0 — Intégrité des données] Rendre l'export Excel non destructif** (`_collect_config` : fait, `868db8c9`) :
  - Retirer l'appel `smart_cleanup()` de `ExportManager.export_excel`.
  - Si un nettoyage automatique avant sauvegarde est souhaité, le proposer via une case à cocher explicite ou une action dédiée avec point d'annulation (en utilisant le mécanisme d’annulation existant ou en l’étendant après vérification), et ne jamais muter `front_table` lors d'un snapshot de comparaison (`_config_snapshot`).
- **[P0 — Graphe détaché & Thème] Corriger la cible de tracé dans `_plot_profile_actual` et la couleur d'axe dans `PlotManager`** :
  - Remplacer `self.ui.profile_plot` par la variable de boucle `plot_widget` dans `PlotManager._plot_profile_actual`.
  - Remplacer `color="black"` par `color=CertusTheme.TEXT_MAIN` dans `_update_optim_live_plot_normal_mode` et `_finalize_oblique_live_plot`.
  - Corriger `parent = self.ui if isinstance(self.ui, QWidget) else None` dans `_ensure_pareto_ui`.
- **[P1 — Transparence des paramètres PGLOBAL] Synchroniser l'UI avec le plafonnement « Topology growth »** :
  - Lorsque `allow_growth_check` est coché, afficher clairement les plafonds effectifs (`1500 / 5 / 8`) dans les spinboxes (en sauvegardant les valeurs manuelles pour les restaurer au décochage) ou afficher un badge d'avertissement inline sous la case à cocher.
- **[P1 — Hiérarchie visuelle & Layout]** :
  - Réserver `OBJ.FEATURED_BUTTON` à `PGLOBAL` et `OBJ.PRIMARY_BUTTON` à `Evaluate` ; passer `Polish local`, `Drop thinnest layer`, `Colorimetric analysis`, `Stack info`, `Detach` et `Logs` en style secondaire (`variant="secondary"`).
  - Supprimer la colonne `Preset` inutilisée dans `Materials` (ou la peupler avec les matériaux fréquents `TiO2`, `SiO2`, `Ta2O5`, `Al2O3`, `HfO2`) pour élargir la colonne `File / Value`.
  - Ouvrir `plot_tabs` sur `Spectrum (T)` par défaut (ou intégrer un mini-aperçu spectral dans l'onglet `✦ Synthesis`).

---

## 5. Audit de `CERTUS_STRAT` (`CertusStratApp`)

### 5.1 Architecture et rôle dans le workflow

Le module [`certus_strat_ui.py`](certus/ui/certus_strat_ui.py) (assemblant [`certus_strat_ui_layout.py`](certus/ui/certus_strat_ui_layout.py), [`certus_strat_ui_events.py`](certus/ui/certus_strat_ui_events.py), [`certus_strat_ui_plot.py`](certus/ui/certus_strat_ui_plot.py), [`certus_strat_ui_state.py`](certus/ui/certus_strat_ui_state.py), [`certus_strat_ui_worker.py`](certus/ui/certus_strat_ui_worker.py), [`certus_strat_multigraine_ui.py`](certus/ui/certus_strat_multigraine_ui.py) et [`certus_strat_table_ui.py`](certus/ui/certus_strat_table_ui.py)) pilote la recherche et la validation Monte Carlo des stratégies de contrôle optique monochromatique (et hybride vitesse/temps `Rate`) pour le dépôt en salle blanche.

L'interface s'articule autour d'un `QSplitter` horizontal :
- **Panneau gauche** (`minimumWidth = 340 px`) : 4 onglets (`General`, `Optimization`, `Advanced`, `Multi-seed`) dans un `QScrollArea`, au-dessus d'un bloc permanent d'exécution (`Step 1 (Nominal)`, `Step 2 (Opti)`, `Step 3 (Rob)`, `RUN FULL WORKFLOW`, `STOP WORKFLOW`, `Sim. Strat.`).
- **Panneau droit** : une barre d'actions supérieures (navigation de couches `◀ Layer` / `Layer ▶`, `Save Graph`, `Interactive Heatmap`, `Interactive Indices`, `View Strategies Table`, `View Loaded JSON`), un afficheur d'image statique (`main_plot_widget`) dans un `QScrollArea`, et une console de logs (`log_text`) dans un `QSplitter` vertical.

### 5.2 Points forts observés

- **Bannière d'état du modèle machine en temps réel (`_refresh_machine_status`)** : recalculée à chaque frappe clavier dans la carte `Machine model — error sources`, elle distingue immédiatement les sources actives, inactives et illisibles (`?`) avec un code couleur sémantique (`SUCCESS`, `WARNING`, `DANGER`).
- **Validation pré-vol exhaustive (`CertusStratStateMixin.input_problems`)** : vérifie la lisibilité de chaque champ numérique, l'existence de l'empilement, l'ordre des bornes spectrales, la stricte positivité des pas spectraux et la conformité de la largeur de fente (`5 / 2 / 1 / 0.5 nm`) avant tout lancement, avec mise en évidence directe du premier champ fautif dans `refuse_to_run`.
- **Table de comparaison des stratégies riche en explications physiques (`StrategiesTableWindow`)** : les colonnes `Yield %`, `Slit (nm)`, `Rate layers`, `Critical layer` et `Dominant defect` rendent les stratégies directement exécutables en salle blanche et signalent explicitement les stratégies « repêchées » (`⚠` `crash_eliminated`).
- **Architecture pure et testable de l'onglet `Multi-seed` (`EtatMultigraine`)** : séparation rigoureuse entre l'automate d'état pur et la vue Qt, distinction explicite entre le SEEL provisoire (biaisé par la malédiction du gagnant) et le résultat citable réévalué sur graine disjointe.

### 5.3 Problèmes UX et fonctionnels identifiés

1. **[CRITIQUE] Écrasement silencieux de 7 champs de l'interface par `Execution Mode` (`_MODE_BUDGETS` dans `CertusStratStateMixin.collect_params`)** :
   - Dans [`certus_strat_ui_state.py`](certus/ui/certus_strat_ui_state.py), la fin de `collect_params` applique inconditionnellement le dictionnaire `_MODE_BUDGETS[mode]` (`fast`, `premium`, `deep`, `extreme`) en écrasant 7 paramètres : `robustness_num_runs`, `consensus_num_runs`, `n_screen_runs`, `elite_rounds`, `dp_top_k`, `k_keep_survivors` et `mining_candidates_limit`.
   - Or, 4 de ces paramètres (`robustness_num_runs`, `mining_candidates_limit`, `n_screen_runs`, `k_keep_survivors`) sont des **champs `QLineEdit` actifs et éditables** dans le même onglet `Advanced` !
   - Lorsqu'un utilisateur modifie `Number of Runs (Validation)` ou `Screening Runs (Phase B)` à l'écran (ou charge un fichier JSON contenant ces clés), son réglage est silencieusement ignoré au profit du budget fixe de `execution_mode` (avec une simple ligne `[MODE] ... overridden` noyée dans la console de logs), et changer `execution_mode` dans la liste déroulante ne met pas non plus à jour les valeurs affichées dans ces 4 champs.
2. **[MAJEUR] Rendu graphique principal sous forme d'image PNG statique (`QLabel`) au lieu d'un graphe interactif (`CertusStratPlotMixin`)** :
   - Contrairement à tous les autres modules CERTUS qui utilisent `CertusScientificPlot` (`PyQtGraph`), la zone centrale de `CERTUS_STRAT` (`main_plot_widget` dans [`certus_strat_ui_layout.py`](certus/ui/certus_strat_ui_layout.py) et [`certus_strat_ui_plot.py`](certus/ui/certus_strat_ui_plot.py)) est un simple `QLabel` affichant un bitmap PNG généré en tâche de fond par `PlotRenderWorker` (`Matplotlib`).
   - Conséquences UX : aucun zoom/pan à la souris, aucun réticule de lecture de coordonnées, aucune barre d'outils `CertusPlotToolbar`, et un flou de mise à l'échelle lors du redimensionnement de la fenêtre (`resizeEvent` ne relance pas `update_main_plot(force_render=True)`).
3. **[MAJEUR] Prolifération de fenêtres flottantes satellites (jusqu'à 8 fenêtres simultanées) et triple popup au clic dans `StrategiesTableWindow`** :
   - `CERTUS_STRAT` ouvre des fenêtres indépendantes pour presque chaque action :
     - Charger un fichier JSON (`load_configuration_from_path`) ouvre simultanément une fenêtre flottante non-modale `JsonViewerWindow` **et** une boîte de dialogue modale `show_load_summary_dialog` (`STRAT Load Summary`).
     - Cliquer sur n'importe quelle cellule d'une ligne dans `StrategiesTableWindow` (`on_cell_clicked` dans [`certus_strat_table_ui.py`](certus/ui/certus_strat_table_ui.py)) déclenche **3 fenêtres flottantes d'un coup** : `TransmissionVsThicknessWindow` (positionnée en dur à `(100, 100)`), `StrategySpectralPerformanceWindow` (positionnée en dur à `(150, 150)`), **et** une boîte de dialogue non-modale `Extrema Proximity - Strategy ...` (`QDialog`). Si l'utilisateur clique successivement sur 5 lignes pour les comparer, 5 boîtes `Extrema Proximity` s'empilent à l'écran (`self._details_dialogs`).
4. **[MAJEUR] Corruption de la géométrie de `stack_table` après détachement/rattachement (`CertusStratEventsMixin.reattach_stack_window`)** :
   - À l'initialisation (`_create_design_tab` dans [`certus_strat_ui_layout.py`](certus/ui/certus_strat_ui_layout.py)), `stack_table` possède une politique `QSizePolicy.Policy.Expanding` et `minimumHeight = 200`.
   - Lorsqu'on détache puis rattache la table via `detach_stack_window` / `reattach_stack_window` (dans [`certus_strat_ui_events.py`](certus/ui/certus_strat_ui_events.py)), `reattach_stack_window` impose en dur `table.setFixedWidth(230)`, `table.setMinimumHeight(115)`, `table.setMaximumHeight(150)` et `QSizePolicy.Policy.Fixed`, écrasant définitivement la géométrie initiale de la table des couches.
5. **[MAJEUR] Déconnexion entre l'onglet `Multi-seed` et la configuration en mémoire de l'interface (`CertusStratMultigraineMixin`)** :
   - Dans [`certus_strat_multigraine_ui.py`](certus/ui/certus_strat_multigraine_ui.py), la liste déroulante `Component` (`_mg_composant`) n'accepte que les clés codées en dur dans `scripts/probe_blocs_vs_plantage.py::COMPOSANTS`. Si l'utilisateur ouvre un empilement personnel (ou modifie les couches, la longueur d'onde de référence, la fente ou le modèle machine dans les onglets `General` / `Optimization` / `Advanced`), l'onglet `Multi-seed` refuse de démarrer ou ignore toutes les modifications faites dans l'interface en relançant le script externe sur le fichier disque de référence avec `mode="deep"` et `resolution=2.0` figés.
   - En outre, le processus `QProcess` (`_mg_proc`) n'est pas enregistré auprès de `self.worker_manager` ni de `self._active_workers`, de sorte que fermer la fenêtre `CERTUS_STRAT` pendant une campagne multi-graines de plusieurs heures ne déclenche aucun avertissement de confirmation.
6. **[MODÉRÉ] Colonne `"Next"` mal nommée et induisant l'utilisateur en erreur dans `StrategiesTableWindow` (`certus_strat_table_ui.py`)** :
   - Dans `BASE_HEADERS` ([`certus_strat_table_ui.py`](certus/ui/certus_strat_table_ui.py)), la colonne d'indice 13 s'intitule `"Next"`, avec l'infobulle `"Button to inspect this strategy in detail (spectral performance, layer-by-layer profile, extrema proximity)."`.
   - Or, `_populate_table_row` y injecte en réalité `_fill_extrema_cell(row, strat)`, qui affiche le nombre médian d'extrema théoriques par couche (`ext_p50`, ex. `1.0`) et non un bouton !
7. **[MODÉRÉ] Numérotation incohérente des étapes du workflow (`Step 0` vs `Step 1`) et raccourci `F5` partiel** :
   - Les boutons affichent `Step 1 (Nominal)`, `Step 2 (Opti)` et `Step 3 (Rob)`, mais l'infobulle de `Step 1 (Nominal)` indique `"Step 0: Computes the basic optical response..."`, le code interne l'appelle `run_step0_btn` / `StratTask.STEP_0_NOMINAL` (sans `Step 1` interne), et le moniteur live affiche `"PHASE B : ... BLOCS | Score de robustesse (RMSE): ..."`.
   - De plus, `F5` et `Ctrl+R` lancent uniquement `Step 2 (Opti)` (`run_workflow(2)`) au lieu de `RUN FULL WORKFLOW` (`run_workflow(23)`), alors que `RUN FULL WORKFLOW` est le bouton d'action principal (`OBJ.FEATURED_BUTTON`).
8. **[MINEUR] Mélange linguistique français/anglais et problèmes de contraste dans `StrategiesTableWindow`** :
   - La bannière `machine_status` (`"FENTE 2 nm | ACTIF : biais de fente..."`), l'infobulle de `execution_mode` et l'infobulle de la colonne `Dominant defect` (`_fill_ablation_cell` : `"Contribution de chaque source, mesuree en l'ETEIGNANT..."`) sont en français dans une interface en anglais.
   - Dans `_populate_table_row`, les origines standards reçoivent `origin_item.setForeground(QColor(80, 80, 80))`, quasi illisible en thème sombre (contraste `1.85:1` sur `#1e293b`), et `_fill_seel_cells` comporte deux branches conditionnelles identiques (`elif seel_val < 1.0: WARNING_BG` et `elif seel_val < 2.0: WARNING_BG`).

### 5.4 Pistes d'améliorations pour `CERTUS_STRAT`

- **[P0 — Cohérence `Execution Mode` / Champs UI]** :
  - Synchroniser les valeurs visibles avec les budgets effectifs, ou rendre les champs imposés non éditables avec une explication. Le mode conserve sa priorité actuelle par défaut (D1). Un mode `custom` exige un contrat explicite pour tous les budgets, leur validation et la compatibilité JSON ; ne pas l'activer automatiquement sans cette décision.
- **[P1 — Consolidation des fenêtres flottantes et du tableau des stratégies]** :
  - Dans `StrategiesTableWindow` : renommer l'en-tête `"Next"` en `"Med. Extrema"`, remplacer `QColor(80, 80, 80)` par `QColor(CertusTheme.TEXT_SUB)`, et ne plus ouvrir automatiquement la popup `Extrema Proximity` à chaque clic sur une ligne (la déclencher uniquement au double-clic sur la cellule `Med. Extrema` ou via un bouton dédié / panneau latéral).
  - Regrouper `TransmissionVsThicknessWindow` et `StrategySpectralPerformanceWindow` dans une seule fenêtre d'inspection à onglets (ou un tiroir ancré) réutilisée d'une sélection à l'autre au lieu d'empiler des fenêtres à `(100, 100)` et `(150, 150)`.
  - Lors du chargement d'un JSON (`load_configuration_from_path`), supprimer l'ouverture automatique simultanée de `JsonViewerWindow` et de la boîte modale `STRAT Load Summary` : afficher un toast non-bloquant et laisser le bouton `View Loaded JSON` ouvrir l'inspecteur à la demande.
- **[P1 — Correction du détachement de `stack_table` et de l'intégration `Multi-seed`]** :
  - Dans `reattach_stack_window`, restaurer `QSizePolicy.Policy.Expanding`, `setMinimumWidth(0)`, `setMaximumWidth(16777215)`, `setMinimumHeight(200)` et `setMaximumHeight(16777215)`.
  - Enregistrer `_mg_proc` dans le mécanisme de confirmation de fermeture de `CertusStratApp` (`confirm_close_during_run`) et afficher un compteur de temps écoulé en direct pour les graines à l'état `"running"`.
- **[P2 — Modernisation du graphe principal]** :
  - Remplacer progressivement le `QLabel` PNG statique (`main_plot_widget`) par des onglets `CertusScientificPlot` (Spectre nominal, Croissance $T(d)$ par couche, Carte de candidats DP) dotés du zoom/pan et de `CertusPlotToolbar`, en conservant l'export Matplotlib haute résolution pour les rapports HTML/Excel.
## 6. Audit de `CERTUS_INDEX` — Extraction d'Indice Monocouche Tauc-Lorentz & Urbach ([certus/ui/certus_index_ui.py](certus/ui/certus_index_ui.py))

Le module `CERTUS_INDEX` ([certus/ui/certus_index_ui.py](certus/ui/certus_index_ui.py), décomposé en [certus/ui/certus_index_ui_layout.py](certus/ui/certus_index_ui_layout.py), [certus/ui/certus_index_ui_events.py](certus/ui/certus_index_ui_events.py), [certus/ui/certus_index_ui_plot.py](certus/ui/certus_index_ui_plot.py), [certus/ui/certus_index_ui_state.py](certus/ui/certus_index_ui_state.py), [certus/ui/certus_index_ui_worker.py](certus/ui/certus_index_ui_worker.py) et [certus/ui/certus_index_ui_export.py](certus/ui/certus_index_ui_export.py)) extrait les constantes optiques $(n(\lambda), k(\lambda))$ et l'épaisseur physique $d$ d'une couche mince unique par ajustement multi-oscillateurs Tauc-Lorentz + queue d'Urbach (+ Drude/Lorentz IR optionnel au-delà de $2500\text{ nm}$).

### 6.1 Points forts observés
- **Intégration directe de la base de dépôts** : La carte « 1. Experimental Data » propose côte à côte le chargement d'un fichier brut (`Load File...`) et l'accès direct au sélecteur de dépôts qualifiés (`Deposit database…` via `DepositDatabaseDialog` dans [certus/ui/certus_depots_dialog.py](certus/ui/certus_depots_dialog.py)), pré-remplissant automatiquement l'épaisseur estimée et le substrat lorsque les métadonnées sont disponibles.
- **Adaptation contextuelle au substrat Silicium** : Lorsque l'utilisateur sélectionne un substrat `Silicon`, `CertusIndexEventsMixin.on_sub_type_changed` adapte automatiquement les bornes spectrales par défaut ($1000\text{–}3200\text{ nm}$ au lieu de $250\text{–}2000\text{ nm}$), évitant de lancer une inversion dans le visible où le silicium est opaque en transmission.
- **Rapport HTML d'équations analytiques avec copie LaTeX / Presse-papiers** : L'onglet « Final Equations » génère un récapitulatif mathématique complet des paramètres Tauc-Lorentz/Urbach/Cauchy/Drude avec boutons dédiés `Copy Equations (Text)` et `Save Report (HTML)`.

### 6.2 Problèmes UX identifiés

1. **[CRITIQUE] Détournement forcé de l'onglet actif vers le tableau `Data` (`self.tabs.setCurrentIndex(0)`) pendant le chargement et toutes les 2 secondes pendant l'optimisation (`CertusIndexEventsMixin.load_file`, `CertusIndexExportMixin._apply_index_live_plot_payload`)** :
   - Dans `CertusIndexLayoutMixin._build_ui` ([certus/ui/certus_index_ui_layout.py](certus/ui/certus_index_ui_layout.py)), la méthode `_add_main_control_buttons` insère l'onglet `"Data"` en toute première position (`index 0`) de `self.tabs`, **avant** `"✦ Synthesis"` (`index 1`), `"Spectrum"` (`index 2`), `"n, k"` (`index 3`), `"Convergence ↘"` (`index 4`) et `"Final Equations"` (`index 5`).
   - Bien que la fin de `_build_ui` recherche explicitement l'onglet `"Spectrum"` par son titre (`if "spectrum" in self.tabs.tabText(_i).lower(): self.tabs.setCurrentIndex(_i)`) pour contourner ce décalage d'index, **[AMENDÉ] cinq autres méthodes du module codent encore en dur `self.tabs.setCurrentIndex(0)`** (les quatre ci-dessous et `CertusIndexExportMixin._display_results`) en supposant que l'index `0` est l'onglet `"Spectrum"` :
     1. **`CertusIndexEventsMixin.load_file`** ([certus/ui/certus_index_ui_events.py](certus/ui/certus_index_ui_events.py)) : juste après avoir tracé le spectre expérimental chargé sur `self.plot_spectrum`, `load_file` appelle `self.tabs.setCurrentIndex(0)` — ce qui bascule l'utilisateur sur l'onglet `"Data"` (tableau encore vide !). Pire : immédiatement après, `_apply_dynamic_ir_smoothing` superpose la courbe brute et la courbe lissée sur `self.plot_spectrum` et ouvre la boîte de dialogue modale `_ask_keep_raw_or_smoothed` demandant à l'utilisateur de choisir entre les deux courbes, alors que l'utilisateur a sous les yeux le tableau `"Data"` vide et ne peut pas voir le graphique `"Spectrum"` !
     2. **`CertusIndexWorkerMixin.run_optimization`** ([certus/ui/certus_index_ui_worker.py](certus/ui/certus_index_ui_worker.py)) : au clic sur `Run Optimization`, `self.tabs.setCurrentIndex(0)` bascule l'utilisateur sur le tableau `"Data"` au lieu du graphique `"Spectrum"`.
     3. **`CertusIndexExportMixin._apply_index_live_plot_payload`** ([certus/ui/certus_index_ui_export.py](certus/ui/certus_index_ui_export.py)) : à chaque émission d'un aperçu temps réel par le worker (toutes les 2 secondes), `_apply_index_live_plot_payload` exécute `self.tabs.setCurrentIndex(0)` ! Concrètement, si l'utilisateur clique sur `"Spectrum"`, `"n, k"` ou `"Convergence ↘"` pendant que l'optimisation tourne pour observer les courbes, l'interface **le ramène de force sur le tableau `"Data"` toutes les 2 secondes**.
     4. **`CertusIndexStateMixin._load_defaults`** ([certus/ui/certus_index_ui_state.py](certus/ui/certus_index_ui_state.py)) : réinitialise également sur `setCurrentIndex(0)`.

2. **[MAJEUR] Boîtes de dialogue modales à fermeture et décision automatiques en 5 secondes (`_ask_keep_raw_or_smoothed` & `_on_tlu_constrained_finished`)** :
   - Dans `CertusIndexEventsMixin._ask_keep_raw_or_smoothed` ([certus/ui/certus_index_ui_events.py](certus/ui/certus_index_ui_events.py)), un `QTimer` de 5 secondes décrémente le texte du bouton `"Keep Smoothed (5s)"` et valide automatiquement le lissage (`msg.accept()`) si l'utilisateur ne clique pas dans les 5 secondes. Combiné au fait que le graphique est masqué derrière l'onglet `"Data"` et qu'une première boîte modale (`show_load_summary_dialog`) vient tout juste de se fermer, l'utilisateur n'a ni le temps ni la visibilité pour inspecter les franges d'interférence avant que ses données soient modifiées.
   - Dans `CertusIndexWorkerMixin._on_tlu_constrained_finished` ([certus/ui/certus_index_ui_worker.py](certus/ui/certus_index_ui_worker.py)), lorsque le spectre dépasse $2500\text{ nm}$, une boîte de dialogue `QMessageBox` demande : *« Phase 1 (Constrained TLU) is complete. Launch Global IR Model (> 2500 nm)? »*, mais programme simultanément `QTimer.singleShot(5000, yes_btn.click)`. Si l'utilisateur a détourné le regard pendant la Phase 1 (qui dure plusieurs dizaines de secondes), la Phase 2 (optimisation globale IR lourde) démarre toute seule au bout de 5 secondes et écrase les résultats de la Phase 1 sans consentement explicite.

3. **[MAJEUR, AMENDÉ] Aucun export manuel ; l'export n'existe que s'il est automatique (`CertusIndexWorkerMixin._on_finished`)** :
   - Dans `CertusIndexLayoutMixin._add_main_control_buttons`, `create_top_actions_bar` est appelé avec `export_func=None` (commentaire : *« Export button removed - auto-export is active »*).
   - `CertusIndexWorkerMixin._on_finished` appelle `self.export_results()` à chaque fin d'optimisation. `CertusIndexExportMixin.export_results` ([certus/ui/certus_index_ui_export.py](certus/ui/certus_index_ui_export.py)) retourne si l'export automatique du Hub (`get_export_config()`) est désactivé ; sinon il écrit `Report_INDEX_<source>_<horodatage>_RMSE_<…>.xlsx/.html` dans `reports/` (pas d'écrasement ; captures d'onglets par `generate_html_report`).
   - Auto-export désactivé, l'utilisateur n'a donc **aucun moyen d'exporter** un résultat d'INDEX ; activé, chaque essai écrit sans confirmation.

4. **[MAJEUR] Reconstruction synchrone ligne par ligne de `table_res` sur le thread GUI toutes les 2 secondes (`CertusIndexWorkerMixin._on_progress`)** :
   - Pendant l'optimisation, `_on_progress` ([certus/ui/certus_index_ui_worker.py](certus/ui/certus_index_ui_worker.py)) vide et reconstruit intégralement `self.table_res` toutes les 2 secondes via une boucle Python `for i in range(len(wls)): self.table_res.setItem(...)` (5 colonnes $\times N_\lambda$ lignes, soit jusqu'à $10\,000$ objets `QTableWidgetItem` alloués à chaque tick), suivie de `self.table_res.resizeColumnsToContents()`.
   - Le temps de cette opération sur le thread principal n’a pas été mesuré alors même que les valeurs numériques intermédiaires n'ont besoin d'être tabulées qu'à la fin de l'optimisation (`_on_finished`).

5. **[MODÉRÉ] Duplication des indicateurs KPI (`ResultRecapWidget` vs `CertusKpiBanner`) et onglet `"✦ Synthesis"` redondant / code mort (`self.perf_tab`)** :
   - Dans `CertusIndexLayoutMixin._build_ui` ([certus/ui/certus_index_ui_layout.py](certus/ui/certus_index_ui_layout.py)), quatre cartes `FlashyCard` (`c1..c4`) et un widget `self.perf_tab` sont instanciés mais ne sont jamais ajoutés à aucun layout ni onglet (fuite de widgets orphelins).
   - Juste après, l'onglet `"✦ Synthesis"` est créé avec uniquement une bannière `CertusKpiBanner` de 4 métriques (`Thickness`, `RMSE`, `Bandgap Eg`, `Eps Inf`) et un grand espace vide (`addStretch(1)`), alors que la barre latérale gauche affiche déjà en permanence `ResultRecapWidget` contenant exactement les 4 mêmes cartes (`Thickness`, `Final RMSE`, `Bandgap Eg`, `Eps Inf`) !

6. **[MINEUR] Libellé contradictoire sur l'absorption du substrat (`chk_absorbing_sub`) et double popup au chargement** :
   - La case à cocher `self.chk_absorbing_sub` est intitulée `"Absorbent substrate (k = 0)"`, ce qui est un oxymore physique (un substrat absorbant a $k > 0$, tandis qu'un substrat transparent a $k = 0$).
   - Lors d'un `load_file`, l'application affiche successivement `show_load_summary_dialog` (popup modale de résumé de colonnes) puis `_ask_keep_raw_or_smoothed` (seconde popup modale avec compte à rebours), interrompant deux fois le flux de travail.

### 6.3 Pistes d'améliorations pour `CERTUS_INDEX`

| Priorité | Piste d'amélioration | Cible technique |
| :--- | :--- | :--- |
| **P0** | **Restaurer la sélection d'onglet par référence de widget et supprimer le détournement en direct** : (1) Déplacer l'onglet `"Data"` après `"Spectrum"`, `"n, k"` et `"Convergence ↘"` ; (2) Dans `load_file` et `run_optimization`, activer explicitement l'onglet `"Spectrum"` (`self.tabs.setCurrentWidget(self.tab_spec)`) ; (3) Dans `_apply_index_live_plot_payload`, **supprimer complètement** `self.tabs.setCurrentIndex(...)` pour laisser l'utilisateur libre de naviguer entre `"Spectrum"`, `"n, k"` et `"Convergence ↘"` pendant l'optimisation. | [certus/ui/certus_index_ui_layout.py](certus/ui/certus_index_ui_layout.py), [certus/ui/certus_index_ui_events.py](certus/ui/certus_index_ui_events.py), [certus/ui/certus_index_ui_worker.py](certus/ui/certus_index_ui_worker.py), [certus/ui/certus_index_ui_export.py](certus/ui/certus_index_ui_export.py) |
| **P1** | **Supprimer les comptes à rebours de 5 secondes sur les choix scientifiques critiques** : (1) Remplacer `_ask_keep_raw_or_smoothed` par une case à cocher non modale `"IR Dynamic Smoothing"` dans la carte `"1. Experimental Data"` (ou un bandeau d'action intégré au-dessus de `plot_spectrum`) permettant de basculer à tout moment entre spectre brut et spectre lissé ; (2) Remplacer la popup de 5 secondes de la Phase 2 IR (`_on_tlu_constrained_finished`) par une option explicite `"Auto-chain Global IR Model (> 2500 nm)"` dans la carte `"3. Model & Fit Options"`. | [certus/ui/certus_index_ui_events.py](certus/ui/certus_index_ui_events.py), [certus/ui/certus_index_ui_worker.py](certus/ui/certus_index_ui_worker.py) |
| **P1** | **Rétablir un bouton `Export` explicite** : relier à `create_top_actions_bar` (et `Ctrl+E`) une action qui exporte même quand `get_export_config()` est faux (`export_results` retourne alors sans rien écrire), et nommer dans un toast le fichier écrit par l'auto-export. | [certus/ui/certus_index_ui_layout.py](certus/ui/certus_index_ui_layout.py), [certus/ui/certus_index_ui_worker.py](certus/ui/certus_index_ui_worker.py) |
| **P1** | **Différer le remplissage de `table_res` à la fin de l'optimisation** : Dans `_on_progress`, ne mettre à jour `self.table_res` que si l'onglet `"Data"` est effectivement visible à l'écran (`self.tabs.currentWidget() is self.tab_data`), et effectuer le remplissage complet une seule fois dans `_on_finished`. | [certus/ui/certus_index_ui_worker.py](certus/ui/certus_index_ui_worker.py) |
| **P2** | **Supprimer le code mort `self.perf_tab` et fusionner l'onglet `"✦ Synthesis"`** : Retirer les `FlashyCard` inutilisées, intégrer `CertusKpiBanner` directement en haut de l'onglet `"Final Equations"` (ou au-dessus des graphiques), et renommer `chk_absorbing_sub` en `"Absorbing substrate (use substrate k(λ) > 0)"`. | [certus/ui/certus_index_ui_layout.py](certus/ui/certus_index_ui_layout.py) |

---

## 7. Audit de `CERTUS_INDEX_SPLINE` & Dialogues Associés ([certus/ui/certus_index_spline_ui.py](certus/ui/certus_index_spline_ui.py), [certus/spline/certus_index_spline_rendering.py](certus/spline/certus_index_spline_rendering.py))

Le module `CERTUS_INDEX_SPLINE` ([certus/ui/certus_index_spline_ui.py](certus/ui/certus_index_spline_ui.py), appuyé sur [certus/spline/certus_index_spline_rendering.py](certus/spline/certus_index_spline_rendering.py) et les mixins `certus_index_spline_*_mixin.py`) détermine simultanément l'épaisseur $d$ et les profils $(n(\lambda), k(\lambda))$ d'une couche mince par splines cubiques (PCHIP / Akima / B-spline en $\lambda$, $\sigma=1/\lambda$ ou $\sigma^2=1/\lambda^2$) et balayage de corridors d'épaisseur $d$. Il mobilise également trois dialogues spécialisés : `ManualSigmaKnotDialog` ([certus/ui/certus_manual_sigma_knot_dialog.py](certus/ui/certus_manual_sigma_knot_dialog.py)), `SmartInitNKCurveEditorDialog` ([certus/ui/certus_smart_init_curve_editor.py](certus/ui/certus_smart_init_curve_editor.py)) et `DepositDatabaseDialog` ([certus/ui/certus_depots_dialog.py](certus/ui/certus_depots_dialog.py)).

### 7.1 Points forts observés
- **Architecture de visualisation analytique très riche (7 onglets spécialisés)** : Les onglets `Spectrum (R / T)`, `n(λ) & k(λ)`, `Thickness Scan`, `Data (λ, n, k, R, T)`, `Corridor Data`, `Envelope & Init` et `Diagnostics` offrent une transparence mathématique exemplaire sur le paysage d'optimisation (profil $\text{RMSE}(d)$, courbure locale $a$, intervalles de confiance $\Delta d$, nœuds splines sur les courbes $n(\lambda)$ et $k(\lambda)$).
- **Éditeur interactif de courbe initiale (`SmartInitNKCurveEditorDialog`)** : Permet de déplacer les valeurs des ancres $(n,k)$ à la souris avec callbacks de recalcul et rafraîchissement. Les gestes d’ajout/suppression, raccourcis et la latence du recalcul doivent être vérifiés ; la méthode `_recompute_rt_rmse` citée initialement n’est pas définie dans cet éditeur.
- **Diagnostic automatique des nœuds manuels (`ManualSigmaKnotDialog`)** : Détecte automatiquement les zones de sous-échantillonnage spectral (extrema non résolus en queue UV) et propose des nœuds correctifs en $\lambda$, $\sigma$ et $\sigma^2$.

### 7.2 Problèmes UX identifiés

1. **[P1 — DÉCOUVERTE DES ACTIONS] Barre standard absente et Ctrl+O affecté au spectre** :
   - `_UIBuilderMixin._build_ui` ne construit pas `create_top_actions_bar`. Cela réduit la visibilité de Save/Load/Export ; le bouton **Help existe** via `create_header_logo_widget`, et F1 est installé.
   - `Ctrl+O` est affecté à `_on_load` (import de spectre). Les deux appels à `install_standard_shortcuts` passent par `install_unique_shortcut` : U02 montre un seul raccourci, dont le premier callback est conservé. Ce n'est pas un double QShortcut ambigu.
   - `_finalize_init` installe les services communs, dont la palette `Ctrl+K`. La commande `file.load_config` y appelle le chargeur JSON hérité ; `_apply_config` restaure l'état SPLINE. U03 vérifie la découverte et l'appel de cette commande avec dépendances contrôlées. **Le chargement JSON a un chemin UI existant** ; son aller-retour complet reste à tester.
   - Ajouter des actions directes et clarifier la différence projet/spectre. Pour changer Ctrl+O, remplacer explicitement son binding initial : une seconde installation est ignorée par la déduplication.

2. **[MAJEUR, AMENDÉ] Cascade de 2 à 4 fenêtres flottantes lors du Smart Init et de l'édition des nœuds (`_SmartInitDialogMixin` & `ManualSigmaKnotDialog`)** :
   - `_SmartInitDialogMixin._show_smart_init_preview_dialog` ([certus/ui/certus_index_spline_mixins_ui.py](certus/ui/certus_index_spline_mixins_ui.py)) ouvre **deux** fenêtres à la fois, puis jusqu'à deux autres à la demande :
     1. La fenêtre modale `SmartInitPreviewManager.dlg` ([certus/spline/certus_index_spline_smart_init.py](certus/spline/certus_index_spline_smart_init.py)) ;
     2. `LiveIndexMonitor` (`_open_live_nk_monitor`, `550x700`), placée à `next_to.x() + next_to.width() + 10`, à droite du dialogue : hors écran possible, non mesuré ;
     3. À la demande (bouton `Show n(λ) / k(λ) profiles window`), `aux_dlg` (`"Optical Profiles — n(λ) and ln k(λ)"`, au moins `500x500`) ;
     4. À la demande (`NK Editor...`), `SmartInitNKCurveEditorDialog`.
   - De même, l'ouverture de `ManualSigmaKnotDialog` ([certus/ui/certus_manual_sigma_knot_dialog.py](certus/ui/certus_manual_sigma_knot_dialog.py)) instancie immédiatement dans son `__init__` une **seconde fenêtre flottante indépendante** (`self._preview_popup = QDialog(self)` avec `Qt.WindowType.Window`, `980x540`, via `self._show_preview_popup()`) pour afficher le graphique `self.plot`, au lieu d'intégrer ce graphique dans un `QSplitter` à l'intérieur même de la boîte de dialogue (`1180x780`). Sur un écran portable, ces deux fenêtres géantes se recouvrent mutuellement dès l'ouverture.

3. **[MAJEUR] Caractères corrompus (`?` remplaçant `—`, `≈`, `⁻`, `₁`) dans les titres de graphiques, axes et boutons (`certus_index_spline_rendering.py`, `certus_index_spline_eventsextras_mixin.py`, `certus_index_spline_mixins_ui.py`)** :
   - Plusieurs chaînes affichées directement à l'utilisateur contiennent des points d'interrogation littéraux issus d'une perte d'encodage Unicode antérieure :
     - Dans `_PlotMixin._plot_corridor_rmse_tab` et `_draw_corridor_curvature_label` ([certus/spline/certus_index_spline_rendering.py](certus/spline/certus_index_spline_rendering.py)) : `"Corridor profile RMSE(d) ? best d* = ..."` (au lieu de `—`), `"Curvature a = ... nm?^2"` (au lieu de `nm⁻²`), `"Deltad code ? [...]"` et `"interval ? [...]"` (au lieu de `≈`).
     - Dans `_UIBuilderMixin._build_tab_data` ([certus/spline/certus_index_spline_rendering.py](certus/spline/certus_index_spline_rendering.py)) : l'info-bulle de `btn_copy_nk`, `"All columns (λ, n?, k?) - Excel paste"`, affiche `n?` et `k?`.
     - Dans `CertusIndexSplineEventsExtrasMixin._start_curve_minimum_deep_refit` ([certus/ui/certus_index_spline_eventsextras_mixin.py](certus/ui/certus_index_spline_eventsextras_mixin.py)) : `"Grid minimum? Deep L-BFGS-B polish"`.
     - Dans `_SmartInitDialogMixin._build_smart_init_main_plot` ([certus/ui/certus_index_spline_mixins_ui.py](certus/ui/certus_index_spline_mixins_ui.py)) : l'axe X affiche `"sigma2 = 1/lambda2 (nm?2)"`.

4. **[MAJEUR] Défauts de contraste WCAG AA en thème clair et styles sombres codés en dur dans `ManualSigmaKnotDialog` ([certus/ui/certus_manual_sigma_knot_dialog.py](certus/ui/certus_manual_sigma_knot_dialog.py))** :
   - Les couleurs `#d4a100` et `#c97800` sont notamment utilisées pour du texte de nœud. U11 calcule **2,24:1** et **3,23:1** si le fond est `#f8f9fa` ; les ratios initiaux étaient inexacts pour ce fond. Vérifier le fond rendu et la taille réelle : le [critère WCAG de contraste du texte](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) demande 4,5:1 pour le texte courant et 3:1 pour le grand texte. Le [contraste non textuel](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) pertinent pour certains marqueurs/contrôles est de 3:1, avec ses conditions et exceptions. Ces rôles ne partagent pas automatiquement le seuil 4,5:1.
   - Dans `_build_ui` de `ManualSigmaKnotDialog`, trois panneaux utilisent des couleurs explicites et forcent un style terminal noir/vert (« Matrix ») en dur même lorsque l'application est en thème clair : `lbl_preview_log` (`background-color: #141414; color: #d6f0ff`), `lbl_runtime_metrics` (`background-color: #1e1e1e; color: #a5d6ff`) et `txt_runtime_log` (`background-color: #121212; color: #00ff00`).

5. **[MODÉRÉ] Absence d'accès à la base de dépôts (`DepositDatabaseDialog`) et mélange Français / Anglais dans `CERTUS_INDEX_SPLINE`** :
   - Alors que `CERTUS_INDEX` et `CERTUS_INDEX_SPLINE` traitent exactement le même problème physique (extraction de $n, k, d$ d'un dépôt monocouche), la carte `"1 — Spectrum"` de `CERTUS_INDEX_SPLINE` ne propose que `"Load spectrum…"` (fichier disque) et omet le bouton `"Deposit database…"` (`DepositDatabaseDialog`).
   - Par ailleurs, plusieurs libellés français subsistent au milieu de l'interface anglaise de `CERTUS_INDEX_SPLINE` : `"Mode Axe X :"` et `"Nombre d'onde sigma = 1/λ (nm-1)"` dans `_build_tab_spectrum` ([certus_index_spline_eventsextras_mixin.py](certus/ui/certus_index_spline_eventsextras_mixin.py)), `"Copier tableau Corridors"` dans `_build_tab_data_corridor` ([certus_index_spline_corridorui_mixin.py](certus/ui/certus_index_spline_corridorui_mixin.py)), `"RMSE(d) reprise cassure"`, `"Fallback objectif"`, `"Fallback urgence"` dans `_plot_the_reversal_and_fallback_points`, ou encore `"Colonnes: λ, n, k, d, ns, Tth, Rth."` dans `_build_tab_data_th`.
   - **[AMENDÉ]** Dans `DepositDatabaseDialog` ([certus/ui/certus_depots_dialog.py](certus/ui/certus_depots_dialog.py)), le tableau `self.table` n'active pas le tri par colonne (`setSortingEnabled(True)`) ; le filtre rapide (`self.filter`, échantillon, matériau, substrat, voie) existe déjà.

### 7.3 Pistes d'améliorations pour `CERTUS_INDEX_SPLINE` & Dialogues

| Priorité | Piste d'amélioration | Cible technique |
| :--- | :--- | :--- |
| **P1** | **Rendre Save/Load/Export visibles et clarifier Ctrl+O** : conserver Help/F1 et la palette existants ; si Ctrl+O devient Load Config, remplacer son premier binding et prévoir une action distincte pour le spectre. Le double appel est dédupliqué ; le simplifier est du rangement. Tester souris, clavier et aller-retour JSON. | [certus/spline/certus_index_spline_rendering.py](certus/spline/certus_index_spline_rendering.py), [certus/ui/certus_index_spline_ui.py](certus/ui/certus_index_spline_ui.py) |
| **P1** | **Éliminer les fenêtres satellites flottantes (`_preview_popup`, `aux_dlg`, `LiveIndexMonitor`) au profit de panneaux ancrés (`QSplitter`)** : (1) Dans `ManualSigmaKnotDialog`, intégrer `self.plot` directement dans le `QSplitter` horizontal de la boîte de dialogue au lieu d'ouvrir `self._preview_popup` ; (2) Dans `SmartInitPreviewManager`, intégrer les courbes $n(\lambda)$ et $\ln k(\lambda)$ dans un second onglet ou un `QSplitter` côte à côte avec le spectre R/T au lieu de créer `aux_dlg` et `LiveIndexMonitor`. | [certus/ui/certus_manual_sigma_knot_dialog.py](certus/ui/certus_manual_sigma_knot_dialog.py), [certus/ui/certus_index_spline_mixins_ui.py](certus/ui/certus_index_spline_mixins_ui.py), [certus/spline/certus_index_spline_smart_init.py](certus/spline/certus_index_spline_smart_init.py) |
| **P1** | **Corriger les chaînes dont les symboles sont perdus et harmoniser la langue** : remplacer les occurrences identifiées après vérification de leur sens, en conservant les vrais points d’interrogation ; rétablir les symboles Unicode (`—`, `≈`, `⁻¹`, `⁻²`) et traduire les libellés français restants (`Mode Axe X`, `Copier tableau Corridors`, légendes de `_plot_the_reversal_and_fallback_points`). | [certus/spline/certus_index_spline_rendering.py](certus/spline/certus_index_spline_rendering.py), [certus/ui/certus_index_spline_eventsextras_mixin.py](certus/ui/certus_index_spline_eventsextras_mixin.py), [certus/ui/certus_index_spline_mixins_ui.py](certus/ui/certus_index_spline_mixins_ui.py) |
| **P1** | **Corriger les contrastes selon le rôle visuel** : mesurer le texte sur le fond rendu, distinguer marqueurs/lignes, choisir des jetons `CertusTheme` existants et vérifier les états clair/sombre. Une palette suggérée ne certifie pas la conformité AA de tout le dialogue. | [certus/ui/certus_manual_sigma_knot_dialog.py](certus/ui/certus_manual_sigma_knot_dialog.py) |
| **P2** | **Ajouter le bouton `Deposit database…` dans `CERTUS_INDEX_SPLINE` et enrichir `DepositDatabaseDialog`** : Ajouter l'accès direct à `DepositDatabaseDialog` dans la carte `"1 — Spectrum"` de `CERTUS_INDEX_SPLINE`, et activer `setSortingEnabled(True)` dans `DepositDatabaseDialog`. | [certus/spline/certus_index_spline_rendering.py](certus/spline/certus_index_spline_rendering.py), [certus/ui/certus_depots_dialog.py](certus/ui/certus_depots_dialog.py) |

---

## 8. Audit de `CERTUS_RE` — Rétro-Ingénierie & Correction de Dérive ([CERTUS_RE.py](CERTUS_RE.py), [certus/ui/certus_re_layout_mixin.py](certus/ui/certus_re_layout_mixin.py), [certus/ui/certus_re_ui.py](certus/ui/certus_re_ui.py))

Le module `CERTUS_RE` ([CERTUS_RE.py](CERTUS_RE.py) et ses six mixins [certus/ui/certus_re_layout_mixin.py](certus/ui/certus_re_layout_mixin.py), [certus/ui/certus_re_state_mixin.py](certus/ui/certus_re_state_mixin.py), [certus/ui/certus_re_table_mixin.py](certus/ui/certus_re_table_mixin.py), [certus/ui/certus_re_plot_mixin.py](certus/ui/certus_re_plot_mixin.py), [certus/ui/certus_re_excel_mixin.py](certus/ui/certus_re_excel_mixin.py), [certus/ui/certus_re_workers_mixin.py](certus/ui/certus_re_workers_mixin.py), ainsi que [certus/ui/certus_re_ui.py](certus/ui/certus_re_ui.py) et le moteur d'évaluation partagé [certus/ui/certus_spectrum_eval_ui.py](certus/ui/certus_spectrum_eval_ui.py)) réalise l'inversion post-dépôt d'empilements multicouches à partir d'un classeur Excel à 3 feuilles (`measurement`, `design`, `index`), en optimisant successivement les épaisseurs (Phase 1), les splines de dérive d'indice $\Delta\text{Re}(n_H, n_L)$ et le substrat Cauchy (Phase 2), les secousses stochastiques (Phase 3) et l'ouverture angulaire du faisceau $ap(\lambda)$ (Phase 4).

### 8.1 Points forts observés
- **Tolérance et auto-diagnostic à l'import Excel (`_re_automap_three_sheet_workbook`, `_re_build_load_summary_text`)** : Le parseur détecte automatiquement les permutations de feuilles, la présence d'unités en pourcentage vs fraction, les colonnes d'angles/polarisations/face arrière (`parse_re_column_header`) et la résolution du substrat (modèles analytiques Sellmeier $\text{SiO}_2$/$\text{Si}$ ou recherche hiérarchique dans `indices.xlsx`).
- **Protection contre les crashs `QThread` d'évaluations concurrentes (`_retain_until_finished`)** : Dans [certus/ui/certus_spectrum_eval_ui.py](certus/ui/certus_spectrum_eval_ui.py), les workers `EvalWorker` remplacés par une nouvelle évaluation sont conservés dans `_ORPHAN_EVAL_WORKERS` jusqu'à leur signal natif `finished`, évitant tout `qFatal` Qt lors de modifications rapides des spinboxes.
- **Incertitudes d'épaisseur $\sigma(d)$ par couche (`_append_sigma_column`)** : Le tableau de résultats final (`CertusREResultsDialog` dans [certus/ui/certus_re_ui.py](certus/ui/certus_re_ui.py)) expose l'écart-type conditionnel $\sigma(d)$ en nanomètres issu du Jacobien pour chaque couche de l'empilement, ainsi qu'un code couleur immédiat sur $\Delta\text{QWOT}$ (vert $<0.02$, ambre $<0.08$, rouge $\ge 0.08$).

### 8.2 Problèmes UX identifiés

1. **[P1 — NAVIGATION] L’onglet `"✦ Synthesis"` masque le graphique `"Spectrum (T)"` au démarrage, après chargement Excel et pendant `Run RE` (`CertusRELayoutMixin._build_right_panel`)** :
   - Dans `_build_right_panel` ([certus/ui/certus_re_layout_mixin.py](certus/ui/certus_re_layout_mixin.py)), l'onglet `"✦ Synthesis"` (`build_synthesis_tab(self.kpi_banner, ...)`) est inséré à l'`index 0` de `self.plot_tabs`, avant `"Spectrum (T)"` (`index 1`), `"Index profile"` (`index 2`) et `"n(λ)"` (`index 3`).
   - Le choix de l'onglet initial et les transitions au chargement doivent être reproduits. Les courbes peuvent être tracées dans un onglet non sélectionné ; privilégier une référence de widget et préserver la sélection de l'utilisateur pendant le calcul.
   - En conséquence, lorsqu'un utilisateur ouvre `CERTUS_RE`, charge un fichier Excel et lance l'évaluation ou l'inversion `Run RE`, la zone graphique principale affiche uniquement les 4 cartes KPI sur fond vide (`"✦ Synthesis"`), tandis que les courbes spectrales et les cibles expérimentales sont tracées de manière invisible dans l'onglet `"Spectrum (T)"` en arrière-plan.
   - De plus, comme dans `CERTUS_INDEX`, `_build_right_panel` construit quatre `FlashyCard` (`c1..c4`) et `self.perf_tab = create_flashy_grid([c1, c2, c3, c4])` sans jamais attacher `self.perf_tab` au moindre layout (widgets orphelins).

2. **[MAJEUR] Fausses affordances dans le tableau `Spectral targets` : 6 colonnes sur 7 sont éditables mais totalement ignorées par le moteur (`CertusRETableMixin._get_oblique_tgts` & `load_reverse_engineering_from_path`)** :
   - Lors du chargement d'un classeur RE (`load_reverse_engineering_from_path` dans [certus/ui/certus_re_excel_mixin.py](certus/ui/certus_re_excel_mixin.py)), `self.target_table` crée une ligne par canal spectral avec des widgets interactifs (`QDoubleSpinBox` et `QComboBox`) pour `Angle()`, `Pol`, `Type`, `lambdamin`, `lambdamax` et `Weight`.
   - Toutefois, `CertusRETableMixin._get_oblique_tgts` ([certus/ui/certus_re_table_mixin.py](certus/ui/certus_re_table_mixin.py)) court-circuite intégralement la lecture de `self.target_table` dès qu'un fichier RE est chargé :
     ```python
     if getattr(self, "_re_loaded", False) and self._re_targets:
         return self._re_filter_targets_by_fit_window([t for t in self._re_targets if t.on])
     ```
   - Seule la case à cocher `Active` (colonne 0) est reliée à `_on_target_group_toggled` pour activer/désactiver les points de `self._re_targets`. Les 6 autres colonnes (`Angle`, `Pol`, `Type`, `lambdamin`, `lambdamax`, `Weight`) restent éditables à la souris et déclenchent même `self._schedule_eval` lorsqu'on les modifie, **mais leurs modifications n'ont strictement aucun effet** sur le calcul ni sur l'optimisation !

3. **[MAJEUR] Crash par `AssertionError` sur la polarisation `"Avg"` et titre d'axe Y noir sur fond sombre dans `certus_spectrum_eval_ui.py`** :
   - Dans `CertusRETableMixin.add_target` ([certus/ui/certus_re_table_mixin.py](certus/ui/certus_re_table_mixin.py)), la liste déroulante de polarisation propose `pol_combo.addItems(["s", "p", "Avg"])` ; **[AMENDÉ]** DESIGN ne propose plus que `s`/`p` (`1487a7f9`).
   - `spectrum_eval_plot_curves` n'accepte que s/p, et `is_s_polarization` rejette Avg dans le calcul. L'UI expose donc une option non prise en charge ; l'étape exacte de l'échec doit être reproduite selon le parcours. Étendre seulement l'assertion ne suffit pas : il faut calculer la moyenne s/p complète, ou désactiver l'option en attendant.
   - Dans ce même fichier, `spectrum_eval_apply_axes_legend_scale` exécute à chaque fin d'évaluation `app.spectrum_plot.plotItem.setLabel("left", "R / T", color="black", size="12pt")` (et `"Transmission"` avec `color="black"`), écrasant la couleur du thème actif et rendant le titre de l'axe Y illisible en thème sombre (`Dark Mode`).

4. **[MAJEUR] Gel synchrone du thread GUI jusqu'à 5 minutes (`rw.wait(300000)`) lors d'un clic sur `STOP` (`CertusREWorkersMixin.stop_optim`)** :
   - Dans `stop_optim` ([certus/ui/certus_re_workers_mixin.py](certus/ui/certus_re_workers_mixin.py)), après avoir demandé l'arrêt coopératif (`rw.request_stop()`), le thread principal exécute `re_joined_ok = rw.wait(300000)`.
   - Pendant qu'une étape de différences finies du solveur SciPy TRF se termine en arrière-plan, la boucle d'événements Qt est bloquée de façon synchrone (fenêtre « Ne répond pas » sous Windows) au lieu d'afficher un état `"Stopping…"` asynchrone piloté par le signal `finished` du worker.

5. **[MAJEUR] Absence des boutons `Save` et `Load` dans la barre d'actions supérieure (`CertusRELayoutMixin._build_left_panel`)** :
   - Dans `_build_left_panel` ([certus/ui/certus_re_layout_mixin.py](certus/ui/certus_re_layout_mixin.py)), `create_top_actions_bar(self, None, None, self.export_excel, self.open_help)` est appelé avec `save_func=None` et `load_func=None`.
   - Pourtant, `CertusREStateMixin` ([certus/ui/certus_re_state_mixin.py](certus/ui/certus_re_state_mixin.py)) implémente complètement `_collect_config` (`save_config`) et `load_config` (qui accepte aussi bien un fichier `.json` qu'un classeur `.xlsx`). L'absence des boutons `Save` et `Load` prive l'utilisateur d'un accès visuel à la sauvegarde/restauration de session RE.

6. **[MODÉRÉ] Conflit de modalité (`WindowStaysOnTopHint` + `ApplicationModal`) et débordement horizontal dans `CertusREResultsDialog` ([certus/ui/certus_re_ui.py](certus/ui/certus_re_ui.py))** :
   - `CertusREResultsDialog.__init__` active simultanément `Qt.WindowModality.ApplicationModal` et `Qt.WindowType.WindowStaysOnTopHint`. Lorsque l'utilisateur clique sur le bouton `"Re indices (before / after correction)"` (`open_idx`), celui-ci ouvre `_show_re_drifted_indices_window` via un simple `dlg.show()` non modal sans `WindowStaysOnTopHint` : la fenêtre d'indices s'ouvre alors **derrière** la fenêtre modale `CertusREResultsDialog` épinglée au premier plan et ne peut pas être manipulée !
   - De plus, `_build_button_row` dans `CertusREResultsDialog` aligne **8 boutons à libellés longs sur une seule ligne horizontale** (`Export cibles vs calcul (Excel)`, `Re indices (before / after correction)`, `Overlay plot (targets vs theory)`, `Index plot (before/after)`, `Plot DeltaQWOT`, `Beam ap(λ)`, `Copy to Clipboard`, `Close`), imposant une largeur minimale excessive sur écran $1366\times 768$ et mélangeant français et anglais.

7. **[MINEUR] Symboles tronqués, coquilles et logs de débogage visibles par l'utilisateur** :
   - Dans `CertusREResultsDialog` ([certus/ui/certus_re_ui.py](certus/ui/certus_re_ui.py)) : le symbole $\alpha$ a disparu dans `"√(RMSE_sp2 + _refRMS(DeltaQ)2)"` et `"_ref=..."` (affichant `_ref` au lieu de `α_ref`).
   - Dans `_update_target_table_headers` ([certus/ui/certus_re_layout_mixin.py](certus/ui/certus_re_layout_mixin.py)) : l'en-tête affiche `"Angle()"` au lieu de `"Angle (°)"` et dans `load_reverse_engineering_from_path`, le log affiche `"=0.0"` au lieu de `"θ=0.0°"`.
   - Dans `_show_re_drifted_indices_window` ([certus/ui/certus_re_excel_mixin.py](certus/ui/certus_re_excel_mixin.py)) : l'en-tête affiche la coquille `"Loade"` au lieu de `"Loaded"`.
   - Dans `launch_re` ([certus/ui/certus_re_workers_mixin.py](certus/ui/certus_re_workers_mixin.py)) : quatre messages techniques `[DBG-UI] Creating REWorker...` sont envoyés dans le journal utilisateur (`self.log`) au lieu de `logging.debug`.

### 8.3 Pistes d'améliorations pour `CERTUS_RE`

| Priorité | Piste d'amélioration | Cible technique |
| :--- | :--- | :--- |
| **P1** | **Navigation et polarisation** : sélectionner le spectre par référence de widget au chargement, préserver le choix pendant le calcul et retirer les widgets réellement inutilisés. Pour Avg, désactiver l'option non prise en charge ou implémenter les deux polarisations et leur moyenne ; ne pas se limiter à élargir une assertion. Corriger les axes noirs après contrôle dans les deux thèmes. | [certus_re_layout_mixin.py](certus/ui/certus_re_layout_mixin.py), [certus_spectrum_eval_ui.py](certus/ui/certus_spectrum_eval_ui.py) |
| **P1** | **Verrouiller ou synchroniser les colonnes de `target_table` en mode RE Excel** : Lorsqu'un fichier RE est chargé (`_re_loaded=True`), rendre les cellules `Angle (°)`, `Pol` et `Type` en lecture seule (étiquettes claires du canal issu d'Excel), et relier effectivement `lambdamin`, `lambdamax` et `Weight` de chaque ligne au groupe `self._re_target_col_groups[i_col]` afin que toute modification par canal soit réellement prise en compte par `_get_oblique_tgts`. | [certus/ui/certus_re_excel_mixin.py](certus/ui/certus_re_excel_mixin.py), [certus/ui/certus_re_table_mixin.py](certus/ui/certus_re_table_mixin.py) |
| **P1** | **Arrêt asynchrone complet** : demander l'arrêt coopératif, afficher Stopping, garder les références jusqu'à `QThread.finished` et finaliser aussi le résultat métier. Empêcher les redémarrages concurrents et tester fermeture/annulation ; le seul signal métier `rw.signals.finished` ne prouve pas la fin native. | [certus_re_workers_mixin.py](certus/ui/certus_re_workers_mixin.py) |
| **P1** | **Activer `Save` et `Load` dans `create_top_actions_bar` et corriger la modalité de `CertusREResultsDialog`** : Passer `self.save_config` et `self.load_config` à `create_top_actions_bar` ; retirer `WindowStaysOnTopHint` de `CertusREResultsDialog`, organiser ses 8 boutons d'action sur une grille $2\times 4$ (ou un menu `Export / Plots`) et traduire `"Export cibles vs calcul (Excel)"` en `"Export targets vs theory (Excel)"`. | [certus/ui/certus_re_layout_mixin.py](certus/ui/certus_re_layout_mixin.py), [certus/ui/certus_re_ui.py](certus/ui/certus_re_ui.py) |
| **P2** | **Intégrer `_re_show_load_summary_dialog` dans un tiroir / onglet d'inspection et nettoyer les coquilles** : Remplacer l'ouverture automatique de la grande fenêtre `RE Load Summary` (`920x640`) à chaque chargement par un bouton `"Workbook Summary…"` dans la carte `"3 Excel data"` (en n'ouvrant la boîte automatiquement qu'en présence d'avertissements `!!`), et corriger `"Angle (°)"`, `"Loaded"`, `"α_ref"` et les logs `[DBG-UI]`. | [certus/ui/certus_re_excel_mixin.py](certus/ui/certus_re_excel_mixin.py), [certus/ui/certus_re_ui.py](certus/ui/certus_re_ui.py), [certus/ui/certus_re_workers_mixin.py](certus/ui/certus_re_workers_mixin.py) |

---

## 9. Audit de `CERTUS_FIELD` — Optimisation de Champ Électrique & Tenue au Flux Laser (LIDT)

**Fichiers analysés** :
- Application principale : [certus/ui/certus_field_ui.py](certus/ui/certus_field_ui.py) (`CertusFieldApp`)
- Mixins d'interface, d'événements, de tracés, de workers et d'état : [certus/ui/certus_field_layout_mixin.py](certus/ui/certus_field_layout_mixin.py) (`CertusFieldLayoutMixin`), [certus/ui/certus_field_events_mixin.py](certus/ui/certus_field_events_mixin.py) (`CertusFieldEventsMixin`), [certus/ui/certus_field_plot_mixin.py](certus/ui/certus_field_plot_mixin.py) (`CertusFieldPlotMixin`), [certus/ui/certus_field_workers_mixin.py](certus/ui/certus_field_workers_mixin.py) (`CertusFieldWorkersMixin`), [certus/ui/certus_field_state_mixin.py](certus/ui/certus_field_state_mixin.py) (`CertusFieldStateMixin`)
- Panneaux, fenêtres secondaires et tracés : [certus/ui/certus_field_common.py](certus/ui/certus_field_common.py) (`StackPanelWidget`, `FloatingStackDialog`, `OptimizationPanelWidget`, `ParetoExplorerDialog`), [certus/ui/certus_field_plot.py](certus/ui/certus_field_plot.py) (`FieldPlotCanvas`)

### 9.1 Points forts

- **Architecture visuelle d'analyse de champ très complète (`FieldPlotCanvas`)** : L'onglet `"Overview"` ([certus/ui/certus_field_plot.py](certus/ui/certus_field_plot.py)) combine dans une grille $2\times 2$ synchronisée la distribution spatiale du champ normalisé $|E(z)/E_0|^2$ avec coloration par couche et lignes de seuils d'endommagement (`Threshold H` et `Threshold L`), le spectre de réflectance $R(\lambda)$, les profils de dispersion $n(\lambda), k(\lambda)$ et un panneau de métriques synthétiques, tandis que 6 onglets dédiés (`"Field"`, `"Spectrum"`, `"Index"`, `"Field Result"`, `"Spectral Result"`, `"Design Result"`) offrent l'inspection plein écran et tabulaire.
- **Explorateur de Front de Pareto interactif (`ParetoExplorerDialog`)** : En synthèse multicouche à nombre de couches variable (`Authorize change of number layer`), `ParetoExplorerDialog` ([certus/ui/certus_field_common.py](certus/ui/certus_field_common.py)) trace le compromis $\text{Max } |E/E_0|^2_H$ en fonction du nombre de couches $N$, permet d'inspecter chaque architecture candidate par simple clic sur un point ou une ligne du tableau, et d'appliquer l'empilement retenu (`"✅ Apply Selected Design to Main App"`) sans perdre le reste du front.
- **Recalcul temps réel décorrélé (debounce 300 ms)** : Toute modification des longueurs d'onde ($\lambda_0$, $\lambda_{\text{calc}}$), de l'angle, des matériaux ou d'une épaisseur dans `table_layers` déclenche `trigger_auto_calc` (`auto_calc_timer` à $300\text{ ms}$) qui rafraîchit l'évaluation électromagnétique en arrière-plan.

### 9.2 Problèmes et irritants UX identifiés

1. **[CRITIQUE] Boutons d'édition de l'empilement (`+ H`, `+ L`, `- Last`, `Clear`, `Load JSON`, `🏆 Open Pareto Front`) totalement masqués lorsque le panneau Stack est ancré (`StackPanelWidget._build_ui`)** :
   - Dans `StackPanelWidget._build_ui` ([certus/ui/certus_field_common.py](certus/ui/certus_field_common.py)), le conteneur regroupant les 6 boutons d'action de la pile est explicitement masqué à la construction : `self.btn_container.setVisible(False)`.
   - La méthode `self.stack_panel.set_controls_visible(True)` n'est appelée que dans `CertusFieldStateMixin.toggle_detach_stack` ([certus/ui/certus_field_state_mixin.py](certus/ui/certus_field_state_mixin.py)) lorsque l'utilisateur clique sur `"⬡ Detach Stack"` pour détacher la pile dans une fenêtre flottante (`FloatingStackDialog`) — et `reattach_stack` rappelle immédiatement `self.stack_panel.set_controls_visible(False)` à la fermeture de la fenêtre flottante !
   - **Conséquence directe** : Dans la disposition normale (ancrée), l'utilisateur ne dispose **d'aucun bouton visible** pour ajouter une couche (`+ H`, `+ L`), supprimer la dernière couche (`- Last`), vider la pile (`Clear`), charger un empilement JSON (`Load JSON`) ou ouvrir l'explorateur de Front de Pareto (`🏆 Open Pareto Front`), à moins de deviner qu'il faut d'abord détacher le panneau !

2. **[MAJEUR] Absence totale de bouton `STOP` dans l'interface de `CERTUS_FIELD` et blocage du curseur en sablier (`OptimizationPanelWidget._build_ui` & `CertusFieldApp.request_stop`)** :
   - La docstring de `CertusFieldApp.request_stop` ([certus/ui/certus_field_ui.py](certus/ui/certus_field_ui.py)) documente elle-même cette lacune : *« Stop the running calculation once the operator has confirmed (Esc: this window has no Stop button). »*
   - Lorsqu'une optimisation globale (`Global Optimization`), une synthèse Needle jusqu'à 100 couches (`Authorize change of number layer`) ou une analyse Monte-Carlo (`Sensitivity (MC)`) est lancée dans `CertusFieldWorkersMixin` ([certus/ui/certus_field_workers_mixin.py](certus/ui/certus_field_workers_mixin.py)), les trois boutons `Calculate (F5)`, `Run Optimization` et `Sensitivity (MC)` sont désactivés (`setEnabled(False)`) et `QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)` transforme le curseur en sablier sur toute l'application.
   - L'utilisateur à la souris n'a aucun bouton d'arrêt à l'écran (seule la touche `Esc` au clavier fonctionne).

3. **[MAJEUR] Retour forcé systématique sur l'onglet `0` (`"Overview"`) à chaque calcul ou recalcul automatique (`CertusFieldPlotMixin._refresh_result_views`)** :
   - La méthode `_refresh_result_views` ([certus/ui/certus_field_plot_mixin.py](certus/ui/certus_field_plot_mixin.py)) se termine systématiquement par `self.tab_widget.setCurrentIndex(0)`.
   - Comme chaque modification de longueur d'onde, d'angle, de matériau ou d'épaisseur dans `table_layers` déclenche `trigger_auto_calc` ($300\text{ ms}$) $\to$ `run_auto_calc` $\to$ `on_worker_finished` $\to$ `_refresh_result_views`, un utilisateur qui inspecte l'onglet `"Field"` plein écran, `"Spectrum"` ou `"Field Result"` et ajuste une épaisseur de couche dans le panneau gauche est **arraché de son onglet actif $300\text{ ms}$ plus tard** et renvoyé de force sur `"Overview"`.

4. **[MODÉRÉ] Deux actions Help incohérentes et destination d’export peu visible (`export_data`, `export_png`)** :
   - Dans `CertusFieldStateMixin.open_help` ([certus/ui/certus_field_state_mixin.py](certus/ui/certus_field_state_mixin.py)), l’action Help de la barre d’actions appelle un toast éphémère `show_toast(self, "CERTUS Electric Field Optimization module.", "info")` au lieu d'appeler `open_documentation("CERTUS_FIELD")`. Le bouton Help de l’en-tête appelle déjà `open_documentation("CERTUS_FIELD")` via la fabrique ; F1 est installé par le socle pour l’aide clavier. L’absence de `help=` dans un installateur local ne prouve pas que F1 est absent.
   - Dans `CertusFieldEventsMixin.export_data` ([certus/ui/certus_field_events_mixin.py](certus/ui/certus_field_events_mixin.py)), un clic sur le bouton `Export` (ou `Ctrl+E`) écrit directement dans `reports/Report_FIELD_<timestamp>.xlsx` sans proposer de `QFileDialog.getSaveFileName` et affiche un toast générique `"Excel and HTML reports generated successfully."` qui ne mentionne pas le chemin du fichier créé.
   - Dans `CertusFieldStateMixin._apply_config`, les valeurs de repli pour `seuil1` et `seuil2` lors du chargement d'un JSON incomplet sont codées à `0.5` au lieu de `(3.0, 25.0)` utilisées dans `_load_defaults`.

### 9.3 Pistes d'améliorations pour `CERTUS_FIELD`

| Priorité | Piste d'amélioration | Cible technique |
| :--- | :--- | :--- |
| **P1** | **Rendre les boutons d'édition de la pile visibles en permanence dans `StackPanelWidget`** : Passer `self.btn_container.setVisible(True)` dans `StackPanelWidget._build_ui` et supprimer les appels `self.stack_panel.set_controls_visible(False)` dans `reattach_stack`, afin que `+ H`, `+ L`, `- Last`, `Clear`, `Load JSON` et `🏆 Open Pareto Front` soient utilisables sans devoir détacher le panneau. | [certus/ui/certus_field_common.py](certus/ui/certus_field_common.py), [certus/ui/certus_field_state_mixin.py](certus/ui/certus_field_state_mixin.py) |
| **P1** | **Ajouter un bouton `Stop (Esc)` visible dans `OptimizationPanelWidget`** : relier son signal à `CertusFieldApp.request_stop` (le panneau n'est pas l'application), synchroniser son activation et tester annulation/fermeture. Le sablier ne bloque pas à lui seul les entrées ; évaluer son utilité séparément de l'état des contrôles. | [certus/ui/certus_field_common.py](certus/ui/certus_field_common.py), [certus/ui/certus_field_workers_mixin.py](certus/ui/certus_field_workers_mixin.py) |
| **P1** | **Préserver l'onglet actif lors des calculs et recalculs automatiques** : Supprimer `self.tab_widget.setCurrentIndex(0)` à la fin de `_refresh_result_views` (et sélectionner `"Overview"` uniquement une seule fois à l'initialisation dans `_setup_ui`). | [certus/ui/certus_field_plot_mixin.py](certus/ui/certus_field_plot_mixin.py) |
| **P2** | **Unifier les actions Help et enrichir le retour d’export** : remplacer le toast de `open_help` par la documentation déjà accessible via l’en-tête, conserver l’aide clavier F1 existante et tester sa destination ; afficher le chemin complet du rapport dans le toast de `export_data` (ou proposer un dialogue d'enregistrement quand l'export automatique du Hub est désactivé) et examiner séparément les valeurs physiques de repli dans `_apply_config`, avec décision et validation de leur compatibilité JSON. | [certus/ui/certus_field_state_mixin.py](certus/ui/certus_field_state_mixin.py), [certus/ui/certus_field_events_mixin.py](certus/ui/certus_field_events_mixin.py), [certus/ui/certus_field_ui.py](certus/ui/certus_field_ui.py) |

---

## 10. Audit de `CERTUS_METAL_SINGLE` & `CERTUS_METAL_BILAYER` — Constantes Optiques Métalliques

**Fichiers analysés** :
- Points d'entrée : [CERTUS_METAL_SINGLE.py](CERTUS_METAL_SINGLE.py), [CERTUS_METAL_BILAYER.py](CERTUS_METAL_BILAYER.py)
- Socle UI et workers partagés : [certus/metal/certus_metal_common.py](certus/metal/certus_metal_common.py) (`MetalBaseApp`, `MetalOptimizationWorker`)
- Applications spécialisées : [certus/metal/certus_metal_single_app.py](certus/metal/certus_metal_single_app.py) (`CertusMetalSingleApp`, `OptimizationWorker`), [certus/metal/certus_metal_bilayer_app.py](certus/metal/certus_metal_bilayer_app.py) (`CertusMetalBilayerApp`, `OptimizationWorker`)

### 10.1 Points forts

- **Factorisation exemplaire via `MetalBaseApp` ([certus/metal/certus_metal_common.py](certus/metal/certus_metal_common.py))** : Les deux modules partagent une architecture propre et homogène (gestion du cycle de vie du worker multistart, barre d'état compacte avec chrono et progression, sauvegarde/chargement JSON via `_collect_config` / `_apply_config`).
- **Suivi visuel temps réel du multistart** : Au fil des départs aléatoires (`Total MS`), dès qu'un candidat améliore le meilleur RMSE (`best_solution`), les courbes de réflectance, de dispersion $n(\lambda), k(\lambda)$ (avec affichage explicite des nœuds B-Spline sous forme de marqueurs) et d'historique de convergence sont rafraîchies en direct.

### 10.2 Problèmes et irritants UX identifiés

1. **[P1 — ACTIONS ET EXPORT] Save/Load peu visibles et export manuel à définir** :
   - `MetalBaseApp._create_header` ne construit pas la barre standard Save/Load/Export, mais fournit **Help** via `create_header_logo_widget(module_name=...)`. F1 est déjà installé, et le socle peut l’affecter à l’aide clavier. Les quatre squelettes METAL confirment le bouton Help ; ils ne prouvent pas l’ouverture de son contenu. Ctrl+S/Ctrl+O et les commandes de configuration du socle restent disponibles.
   - Aucun bouton direct d'export des résultats n'est construit dans ces vues, et aucun callback `export=` n'est fourni à `install_standard_shortcuts`. La palette autodécouvre `export_excel`/`export_csv`/rapports, pas `export_results` ; vérifier les actions effectivement publiées avant d'en ajouter.
   - Dans la branche des résultats ordinaires, `MetalBaseApp.export_results` consulte le **booléen** `get_export_config()` et retourne lorsque l'auto-export est désactivé. Ajouter seulement un bouton vers cette méthode ne rendrait donc pas l'export manuel indépendant. La branche `beam_stats` suit un autre chemin, à tester séparément.
   - Le champ `excel_filename` de la carte Output n'est pas utilisé pour le nom construit par `_do_export_results`, qui produit `Report_METAL_SINGLE_...` ou `Report_METAL_BILAYER_...` dans `reports/`. Rendre le nom et la destination effectifs visibles ; définir une action manuelle qui exporte les résultats présents sans modifier la préférence d'auto-export.

2. **[P1 — NAVIGATION] L’onglet `"✦ Synthesis"` à l'index `0` masque le graphique `"Reflectance"` au chargement d'un spectre comme pendant l'optimisation (`_setup_plots` & `_load_defaults`)** :
   - Dans `CertusMetalSingleApp._setup_plots` ([certus/metal/certus_metal_single_app.py](certus/metal/certus_metal_single_app.py)) et `CertusMetalBilayerApp._setup_plots` ([certus/metal/certus_metal_bilayer_app.py](certus/metal/certus_metal_bilayer_app.py)), l'onglet `"✦ Synthesis"` est ajouté en première position (`index 0`) avant `"Reflectance"` (`index 1`), un onglet d'indice (`index 2` ; `"Dielectric"` dans BILAYER) et `"Convergence"`. De surcroît, `CertusMetalBilayerApp._load_defaults` force explicitement `self.tabs.setCurrentIndex(0)`.
   - Lorsque l'utilisateur clique sur `"Load Reflectance"` et choisit un fichier expérimental, `_plot_target_data` (ou `on_file_loaded`) trace le spectre dans `self.ax_refl` (onglet `"Reflectance"`, index `1`), **mais `self.tabs` reste figé sur l'onglet `"✦ Synthesis"` (`index 0`) qui affiche quatre cartes vides (`—`)** ! Même après un clic sur `"▶ Run"`, les courbes temps réel sont tracées en arrière-plan sans jamais être montrées à l'utilisateur s'il ne change pas manuellement d'onglet.
   - Par ailleurs, les deux méthodes `_setup_plots` instancient quatre `FlashyCard` et `self.perf_tab = create_flashy_grid([c1, c2, c3, c4])` sans jamais les attacher à aucun layout (widgets orphelins).

3. **[MAJEUR] Utilisation généralisée de `QLineEdit` bruts sans validateurs numériques au lieu de `QDoubleSpinBox` / `QSpinBox` (`_create_physical_params_group`, `_create_material_params_group`)** :
   - Tous les paramètres physiques et B-Spline des deux modules (`lmin_filter`, `lmax_filter`, `eM_min`, `eM_max`, `eL_nominal`, `eL_variation`, `n_infini_min`, `n_infini_max`, `A_diel_min`, `A_diel_max`, `num_knots`, `nk_min`, `nk_max`, `min_knot_dist`) sont construits avec de simples `QLineEdit` (`setFixedHeight(24)`) dépourvus de `QDoubleValidator` / `QIntValidator`, de bornes, de pas d'incrémentation et de suffixes d'unité.
   - Toute saisie d'une virgule décimale française (ex. `1,45`) ou d'un champ vide provoque une `ValueError` à l'exécution lors du `float(self.widgets[...].text())`.
   - Dans `CertusMetalSingleApp._build_single_optimization_params`, si l'utilisateur saisit `num_knots > 5`, le code écrase silencieusement sa saisie par `"5"` au moment du clic sur `Run` au lieu d'utiliser un `QSpinBox` borné à `[2, 5]`.

4. **[MODÉRÉ] Doublon du bouton `CertusThemeToggle`, compteurs de barre d'état muets et libellé d'export erroné (`"Drude-Lorentz"`)** :
   - `MetalBaseApp._create_header` ([certus/metal/certus_metal_common.py](certus/metal/certus_metal_common.py)) crée un premier bouton `self.btn_theme = CertusThemeToggle(header)` en haut à droite du panneau gauche, puis `MetalBaseApp._create_status_bar` crée **un second bouton `self.btn_theme = CertusThemeToggle(self)`** en bas à droite dans la barre de statut (écrasant la référence `self.btn_theme`).
   - Dans `_create_status_bar`, le compteur d'avancement affiche `self.stats_label = QLabel(" 0  |  0  |   0")` sans aucun préfixe textuel (`MS: 0 | MCS: 0 | SP: 0`), ce qui oblige à survoler l'infobulle pour comprendre la signification des trois nombres.
   - Dans `CertusMetalBilayerApp._do_export_results` ([certus/metal/certus_metal_bilayer_app.py](certus/metal/certus_metal_bilayer_app.py)), la feuille Excel et la section HTML exportées sont intitulées `"Drude-Lorentz Parameters"` (`sheet_name="Drude-Lorentz"`), alors que le modèle physique résolu est un modèle **B-Spline Métal + Cauchy $\text{SiO}_2$** (`eM`, `eL`, `n_inf`, `A_diel`) !

### 10.3 Pistes d'améliorations pour `CERTUS_METAL_SINGLE` & `CERTUS_METAL_BILAYER`

| Priorité | Piste d'amélioration | Cible technique |
| :--- | :--- | :--- |
| **P1** | **Ajouter Save/Load et un export manuel des résultats présents** : conserver Help/F1 existants, créer un callback manuel explicite indépendant du booléen d’auto-export et le relier au bouton ainsi qu’à Ctrl+E. `export_results_manual` est une API proposée, pas existante ; tester résultat absent, résultat disponible, branche beam et destination choisie. | [certus/metal/certus_metal_common.py](certus/metal/certus_metal_common.py), [certus/metal/certus_metal_single_app.py](certus/metal/certus_metal_single_app.py), [certus/metal/certus_metal_bilayer_app.py](certus/metal/certus_metal_bilayer_app.py) |
| **P1** | **Sélectionner l’onglet `"Reflectance"` par défaut et lors du chargement d'un spectre** : Positionner `self.tabs` sur `"Reflectance"` (`index 1`) dans `_setup_plots`, `_load_defaults` et à la fin de `load_target_file`, et supprimer l'instanciation orpheline `self.perf_tab` dans les deux applications. | [certus/metal/certus_metal_single_app.py](certus/metal/certus_metal_single_app.py), [certus/metal/certus_metal_bilayer_app.py](certus/metal/certus_metal_bilayer_app.py), [certus/metal/certus_metal_common.py](certus/metal/certus_metal_common.py) |
| **P1** | **Remplacer les `QLineEdit` numériques par des `QDoubleSpinBox` / `QSpinBox` typés avec unités** : Utiliser `QSpinBox` pour `num_knots` (borné à `[2, 5]` dans `SINGLE` et `[2, 15]` dans `BILAYER`) et `QDoubleSpinBox` (avec suffixes `nm`, `µm²`, décimales adaptées et hauteur standard `28–30 px`) pour les bornes spectrales, épaisseurs et paramètres Cauchy/Spline. | [certus/metal/certus_metal_single_app.py](certus/metal/certus_metal_single_app.py), [certus/metal/certus_metal_bilayer_app.py](certus/metal/certus_metal_bilayer_app.py) |
| **P2** | **Supprimer le `CertusThemeToggle` en doublon, expliciter `stats_label` et corriger le titre `"Drude-Lorentz"`** : Conserver un seul `CertusThemeToggle` (dans l'en-tête), formater `stats_label` en `"MS: 0 | MCS: 0 | SP: 0"`, et renommer `"Drude-Lorentz Parameters"` en `"Bilayer & Dielectric Parameters"` dans `CertusMetalBilayerApp._do_export_results`. | [certus/metal/certus_metal_common.py](certus/metal/certus_metal_common.py), [certus/metal/certus_metal_bilayer_app.py](certus/metal/certus_metal_bilayer_app.py) |

---

## 11. Audit de `CERTUS_SMOOTHER` — Lissage Spectral (`CurveSmootherGUI`)

**Fichiers analysés** :
- Application de lissage : [certus/utils/certus_curve_smoother.py](certus/utils/certus_curve_smoother.py) (`CurveSmootherGUI`, `smooth_spectrum_auto`, `smooth_dataframe_auto`)
- Sélecteur de colonnes Excel partagé : [certus/ui/certus_measurement_excel_ui.py](certus/ui/certus_measurement_excel_ui.py) (`MeasurementColumnSelectDialog`, `open_measurement_excel_interactive`)

### 11.1 Points forts

- **Lissage adaptatif sans hyperparamètres manuels (`smooth_spectrum_auto`)** : Le pipeline Savitzky-Golay multi-échelle avec estimation robuste du bruit (MAD sur différences secondes) et préservation des pentes raides (fronts de filtres interférentiels) fournit un lissage immédiat dès l'ouverture du fichier.
- **Dialogue de sélection de colonnes Excel bien pensé (`MeasurementColumnSelectDialog`)** : L'heuristique `suggest_wavelength_column` pré-identifie la colonne $\lambda$, exclut automatiquement celle-ci de la liste des courbes à cochage multiple (`Select All` / `Select None`) et gère proprement les en-têtes multi-lignes.

### 11.2 Problèmes et irritants UX identifiés

1. **[CORRIGÉ `8c6d951b`] Altération destructive de la précision des longueurs d'onde (`round_wavelength_decimals=1`) lors de l'export (`CurveSmootherGUI.load_file` & `save_file`)** : `read_measurement_excel` n'arrondit plus l'axe que si rien n'est perdu (bruit de virgule flottante) ; le constat d'origine :
   - Dans `CurveSmootherGUI.load_file` ([certus/utils/certus_curve_smoother.py](certus/utils/certus_curve_smoother.py)), `open_measurement_excel_interactive` est appelé avec `round_wavelength_decimals=1`, ce qui exécute `df[x_col] = np.round(pd.to_numeric(df[x_col], errors="coerce"), 1)` **directement sur `self.df`** !
   - Lorsque l'utilisateur clique ensuite sur `"Save Clean Data (Excel)"` (`save_file`), le classeur exporté contient des longueurs d'onde tronquées à $0,1\text{ nm}$ près, détruisant définitivement la grille spectrale haute résolution originale du spectrophotomètre.

2. **[CAPACITÉS À COMPLÉTER] Services partagés dans l'utilitaire SMOOTHER** :
   - Le module hérite de `QMainWindow`, applique le thème et possède déjà Help/F1, Ctrl+S/Ctrl+O et des réglages `certus_settings("CERTUS_SUITE", "CurveSmoother")`. L'héritage ne permet pas d'en déduire l'absence d'aide ou de persistance.
   - Le harnais ne trouve pas de bascule de thème dans cette fenêtre. Le zoom UI, la palette, les fichiers récents, le glisser-déposer et la restauration de géométrie demandent un inventaire de capacités précis avant migration. Ajouter les services utiles par composition ou héritage après comparaison du coût de maintenance.

3. **[MODÉRÉ] Recalcul complet redondant du lissage à chaque bascule de `"Show Raw Traces"` et lors de la sauvegarde (`update_plot` & `save_file`)** :
   - `self.chk_raw.stateChanged.connect(self.update_plot)` relance `self._smooth_y(x, y_raw[i])` sur toutes les colonnes sélectionnées à chaque fois que l'utilisateur coche ou décoche `"Show Raw Traces"`, et `save_file` recalcule une troisième fois `smooth_dataframe_auto` sur le thread GUI au lieu de mettre en cache le `DataFrame` lissé lors du chargement.
   - L'état vide (`_show_empty_notice`) utilise un `pg.TextItem` brut positionné en `(0.5, 0.5)` sur un repère vide `[0..1]` au lieu du composant standard `CertusEmptyState`.
   - Aucun indicateur quantitatif (écart-type du bruit retiré $\sigma_{\text{noise}}$, RMSE brut vs lissé par courbe, ou curseur de force de lissage optionnel) n'est affiché à l'opérateur pour valider que le lissage n'a pas écrêté un pic étroit.

### 11.3 Pistes d'améliorations pour `CERTUS_SMOOTHER`

| Priorité | Piste d'amélioration | Cible technique |
| :--- | :--- | :--- |
| **P0 — fait (`8c6d951b`)** | **Préserver la précision originale des longueurs d'onde (`round_wavelength_decimals=None`)** : Ne jamais arrondir la colonne $\lambda$ dans `CurveSmootherGUI.load_file` (`round_wavelength_decimals=None`), ou limiter l'arrondi au seul formatage d'affichage dans les infobulles sans modifier `self.df`. | [certus/utils/certus_curve_smoother.py](certus/utils/certus_curve_smoother.py) |
| **P1** | **Compléter les services utiles et mettre en cache le DataFrame lissé** : choisir composition ou héritage après inventaire, définir le callback de chargement si le glisser-déposer est ajouté, calculer `self._smoothed_df` une seule fois au chargement (avec affichage de $\sigma_{\text{noise}}$ par courbe et tracé optionnel du résidu $y_{\text{raw}} - y_{\text{smooth}}$), et réutiliser `self._smoothed_df` dans `update_plot` et `save_file`. | [certus/utils/certus_curve_smoother.py](certus/utils/certus_curve_smoother.py) |

---

## 12. Audit de `CERTUS_SUBSTRATE_INDEX` — Indice de Substrat Nu (`SubstrateIndexGUI` & `IndexTableDialog`)

**Fichiers analysés** :
- Fenêtre principale et vue MVP : [certus/ui/certus_substrate_ui.py](certus/ui/certus_substrate_ui.py) (`SubstrateIndexGUI`, `EnhancedProgressWidget`, `StepHeader`)
- Dialogue de résultats et d'export : [certus/ui/certus_substrate_index_dialog.py](certus/ui/certus_substrate_index_dialog.py) (`IndexTableDialog`)

### 12.1 Points forts

- **Guidage séquentiel clair en 3 étapes (`StepHeader`)** : La colonne de gauche structure le flux opérateur en étapes numérotées (`Step 1 — Load Transmittance File`, `Step 2 — Calculation Settings`, `Step 3 — Run Calculation`) avec un retour immédiat sur le nombre de points valides dans la fenêtre spectrale (`_update_range_info` : `"✓ 451 pts in [300, 1100] nm"`).
- **Double visualisation physique (indice point par point vs lissage analytique Sellmeier 1 terme + absorption de queue d'Urbach)** : L'onglet `"Output"` superpose les points $n(\lambda)$ inversés directement depuis $T(\lambda)$ et la courbe analytique Sellmeier ajustée, permettant de détecter immédiatement les artefacts de mesure ou la limite de transparence UV.

### 12.2 Problèmes et irritants UX identifiés

1. **[MAJEUR — DURÉE NON MESURÉE] Calcul synchrone sur le thread GUI et annulation à éprouver (`SubstrateIndexGUI.calculate_index`)** :
   - Dans `SubstrateIndexGUI.calculate_index` ([certus/ui/certus_substrate_ui.py](certus/ui/certus_substrate_ui.py)), l'appel `self.presenter.calculate_index(self.df, fit_range, sellmeier_settings)` s'exécute **de façon synchrone sur le thread principal Qt** !
   - Bien que `self.progress_widget.enable_cancel(True)` affiche un bouton `"Cancel"` dans `EnhancedProgressWidget`, la boucle d'événements Qt est bloquée pendant les ajustements `least_squares`/`minimize` de [certus/core/certus_substrate_sellmeier.py](certus/core/certus_substrate_sellmeier.py) (**[AMENDÉ]** pas de `differential_evolution` sur ce chemin), de sorte que les clics sur `"Cancel"` ne sont pas traités en temps réel.

2. **[MAJEUR] Héritage de `QMainWindow` au lieu de `CertusBaseApp` et organisation `QSettings` isolée (`"SFL"` au lieu de `"CERTUS_SUITE"`)** :
   - Comme `CERTUS_SMOOTHER`, `SubstrateIndexGUI` hérite directement de `QMainWindow` et n’utilise pas automatiquement les mixins du socle. Help/F1, Ctrl+S/Ctrl+O et l’application du thème existent déjà ; le harnais ne trouve pas de bascule de thème. Inventorier séparément zoom UI, palette et glisser-déposer, sans déduire leur absence du seul héritage.
   - `SubstrateIndexGUI.__init__` appelle `certus_settings("SFL", "CERTUS_SUBSTRATE_INDEX")` (**[AMENDÉ]** `IndexTableDialog` n'ouvre aucun réglage). Vérifier les clés effectivement partagées : une même organisation `CERTUS_SUITE` ne suffit pas à partager `last_dir` entre des noms d'application différents. Une migration doit conserver les préférences existantes et définir un espace commun explicite si ce partage est voulu.

3. **[MODÉRÉ] Redondance entre les onglets `"Output"` / `"Output tables"` et `IndexTableDialog`, et utilisation d'un `QTableWidget` brut** :
   - Dans `_refresh_output_tables` ([certus/ui/certus_substrate_ui.py](certus/ui/certus_substrate_ui.py)), le tableau des résultats utilise un `QTableWidget` standard (sans menu contextuel de copie vers Excel, sans export CSV rapide) au lieu du composant maison `ExcelTableWidget` utilisé dans `IndexTableDialog` ([certus/ui/certus_substrate_index_dialog.py](certus/ui/certus_substrate_index_dialog.py)).
   - **[AMENDÉ]** Les actions de `IndexTableDialog` (`Copy to Clipboard`, `Export summary`, `Law parameters (Poly., Sellmeier, Spline)`) sont absentes de la barre supérieure ou des onglets `"Output"` / `"Output tables"` de `SubstrateIndexGUI` si l'utilisateur ferme `IndexTableDialog`.

### 12.3 Pistes d'améliorations pour `CERTUS_SUBSTRATE_INDEX`

| Priorité | Piste d'amélioration | Cible technique |
| :--- | :--- | :--- |
| **P1** | **Déporter `presenter.calculate_index` dans un `QThread` avec annulation coopérative réelle** : Exécuter l'inversion Sellmeier/Urbach dans un worker `QThread` afin que l'interface reste fluide et que le bouton `"Cancel"` de `EnhancedProgressWidget` demande un arrêt coopératif à `differential_evolution` via son callback ; mesurer la latence aux frontières d'évaluation. | [certus/ui/certus_substrate_ui.py](certus/ui/certus_substrate_ui.py) |
| **P1** | **Compléter les services et les exports accessibles** : choisir composition ou héritage, définir une migration des réglages sans perdre les préférences ; remplacer `QTableWidget` par `ExcelTableWidget` dans `_refresh_output_tables`, et ajouter les actions `Copy to Clipboard` et `Export summary` d'`IndexTableDialog` dans la barre d'outils de l'onglet `"Output tables"` (ainsi que dans `create_top_actions_bar`). | [certus/ui/certus_substrate_ui.py](certus/ui/certus_substrate_ui.py), [certus/ui/certus_substrate_index_dialog.py](certus/ui/certus_substrate_index_dialog.py) |

---

## 13. Revue critique, ordre corrigé et preuves attendues

**Priorité = intégrité des données, fidélité des commandes, capacité d'arrêter, puis confort et apparence.** Le choix d'un onglet par défaut n'a pas la même gravité qu'une collecte de configuration qui modifie la pile. Les constats statiques ne sont pas tous des incidents reproduits ; les temps de blocage annoncés sans trace chronométrée restent à mesurer. Les résultats `0/22` du rejeu ne prouvent ni une UX sans défaut ni une couverture de tous les états.

| Ordre / priorité | Action | Preuve ou condition de fin |
|---|---|---|
| 1 / P0 — données | Rendre l’export Excel DESIGN non destructif. Faits : `_collect_config` pur (`868db8c9`), couches fixes protégées (`bdcae9ed`), précision lambda du SMOOTHER (`8c6d951b`). | Comparer pile et données avant/après snapshot, vérification des modifications, sauvegarde, export et fermeture annulée. Cas avec couche fine et grille lambda sub-décimale ; tests rouges avant correctif. Le nettoyage reste une action explicite et annulable. |
| 2 / P1 — commandes effectives | Afficher les budgets réellement appliqués dans STRAT/DESIGN ; rendre les colonnes RE cohérentes avec le calcul ; offrir les actions FIELD et les exports manuels accessibles. | Parcours souris et clavier, paramètres envoyés au worker observés. Préserver les budgets actuels par défaut ; un mode `custom` est une évolution du contrat de calcul, à décider et valider séparément. |
| 3 / P1 — navigation scientifique | Préserver l'onglet actif pendant les mises à jour INDEX/FIELD ; rendre le spectre accessible au chargement ; retirer les décisions scientifiques automatiques à 5 s ou les rendre explicitement configurables. | Sélection par référence de widget, puis plusieurs mises à jour sans déplacement forcé. INDEX a `Data` à l'index 0 et sélectionne initialement Spectrum par son titre : la synthèse initiale qui généralisait Synthesis à l'index 0 était fausse. Ne pas remplacer partout par `setCurrentIndex(1)`. |
| 4 / P1 — arrêt et durée de vie | Réparer le contrat de snapshot RE ; retirer les attentes GUI bloquantes et déporter l’inversion de substrat ; rendre Stop FIELD visible. | État Stopping jusqu'à la fin native du thread, interface réactive, références conservées, redémarrage contrôlé et fermeture sans destruction de worker actif. Un signal métier `finished` peut précéder `QThread.finished` ; tester les deux événements. L'annulation est coopérative, pas instantanée par garantie. |
| 5 / P1 — harnais d'interactions | Étendre les contrôles existants aux parcours à risque : snapshot/export, onglets après progression, zoom, détachement, dialogues, fin et annulation. | Le harnais teste déjà la bascule sombre et certains contrastes. Ajouter des témoins ciblés et des captures, sans déclarer toute fenêtre `parent() is None` comme fuite : les fenêtres de premier niveau sont légitimes. Tester leur fermeture et durée de vie. |
| 6 / P2 — thème et lisibilité | Reproduire les défauts résiduels de palette/réticule, préserver le QSS au zoom, corriger les contrastes réellement insuffisants et les libellés faux. | Clair → sombre → clair, zoom et résolutions/DPI représentatifs ; contrôles de pixels et de lisibilité. Le thème est déjà sauvegardé via `save_theme_config` et les styles à jetons rafraîchis. Ne pas créer une seconde préférence `QSettings` concurrente. |
| 7 / P2 — flux quotidien | Rendre le clic récent du Hub effectif, corriger le tour STRAT, restaurer les info-bulles, unifier les raccourcis et alléger les confirmations de succès. | Action observable, cible du tour existante, texte métier conservé après erreur puis correction. Garder les confirmations nécessaires aux choix scientifiques ou destructifs. |
| 8 / P3 — architecture et disposition | Évaluer la composition de services pour les utilitaires, les panneaux ancrés et les variantes de hiérarchie visuelle. | Bénéfice sur des tâches utilisateur observées ; migration `CertusBaseApp` seulement si elle simplifie le cycle de vie et la maintenance. Les fenêtres satellites et étapes sans projecteur ne sont pas des défauts par leur seule existence. |

**Garde spécifique Avg.** Le retrait de l'assertion d'affichage n'implémente pas la lumière non polarisée. En attendant une moyenne s/p complète (intensités et gradients, avant le résidu), retirer ou désactiver l'option proposée par l'UI avec une explication. Tester ensuite une cible oblique où s et p diffèrent ; voir ALG-08 dans [designargon.md](designargon.md).

**Garde sur les widgets numériques.** Avant de remplacer tous les `QLineEdit`, préserver précision, notation scientifique, locale, unités, bornes persistées et chargement des anciens JSON. Une migration vers `QDoubleSpinBox` peut arrondir ou borner les valeurs ; ce n'est pas automatiquement un changement purement visuel.

**Garde documentaire.** Un défaut doit porter fonction concernée, exposition, reproduction et test attendu. Les propositions de cette revue ne sont pas des correctifs exécutés. L’analyse et les sondes ne permettent pas de garantir 100 % de justesse ou d’exhaustivité ; les critères de fin décrivent les validations encore nécessaires. Réviser les priorités après reproduction ; les mesures et décisions restent dans `docs/ETAT.md` et `reports/`, sans recopier l'historique dans cet audit.

