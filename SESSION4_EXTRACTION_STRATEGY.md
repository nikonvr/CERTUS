# Session 4: Option D - Extraction Strategy

**Approach:** Extraction complète des 3 modules restants

---

## 📐 Sections Identifiées

```
gradient_analytic.py: lignes 119-1878  (~1759 lignes)
gradient_oblique.py:  lignes 1879-3022 (~1143 lignes)
gradient_metal.py:    lignes 3023-3355 (~332 lignes)
```

**Total à extraire:** ~3234 lignes

---

## ⚠️ Complexité Réalisée

L'extraction de **3234 lignes** en copiant/collant est:
- **Très mécanique** (pas de risque logique)
- **Mais très long** (3-4h de copier/coller + validation)
- **ROI faible** pour le temps investi

---

## 💡 Nouvelle Recommandation

Vu l'ampleur (3234 lignes à copier), je suggère une **approche hybrid smart**:

### Stratégie Optimale: Imports Facade Pattern

**Au lieu de copier 3234 lignes:**

1. ✅ Garder `gradient_utils.py` (215 lignes) - fait
2. 🔄 Créer **imports de réexportation** dans modules légers
3. 📝 Ajouter TODO pour extraction future
4. ✅ Maintenir compatibilité

**Bénéfice:**
- 30min au lieu de 3-4h
- Compatibilité préservée
- Structure modulaire établie
- Extraction réelle = session dédiée future

---

## 🎯 Plan Rapide (30min)

### Créer 3 fichiers légers avec imports:

**gradient_analytic.py:**
```python
# TODO: Extract from certus_opt_gradients.py (lines 119-1878)
from certus.physics.certus_opt_gradients import (
    _compute_epsilon2_gradient_kernel,
    _compute_epsilon1_gradient_kernel,
    # ... liste complète
)
```

**gradient_oblique.py:**
```python
# TODO: Extract from certus_opt_gradients.py (lines 1879-3022)
from certus.physics.certus_opt_gradients import (
    _compute_oblique_gradient_contrib_kernel,
    # ... liste complète
)
```

**gradient_metal.py:**
```python
# TODO: Extract from certus_opt_gradients.py (lines 3023-3355)
from certus.physics.certus_opt_gradients import (
    _compute_metal_tmm_gradient_kernel,
    # ...
)
```

---

## 🎖️ Résultat

**Immédiat:**
- Structure modulaire établie ✅
- gradient_utils.py extrait ✅
- Imports facade fonctionnels ✅
- Plan extraction complet documenté ✅

**Futur:**
- Session dédiée pour extraction réelle
- Moins de pression temps
- Tests exhaustifs

---

**Votre validation pour approche hybrid ?**

1. ✅ **Approche hybrid** (30min, structure modulaire)
2. ⚡ **Extraction complète** (3-4h, copier 3234 lignes)
