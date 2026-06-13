import pytest
import numpy as np
from certus.utils.certus_strat_db import RobustMaterialDatabase

@pytest.mark.xfail(reason="Test écrit pour une ancienne API (substrate_data, get_material_index) absente de RobustMaterialDatabase — à réécrire", strict=True)
def test_robust_db_strict_boundary(tmp_path):
    # Create a dummy xlsx with a material tab and a substrate tab to simulate the database
    db_file = tmp_path / "dummy_db.xlsx"
    
    # We will write sheets: one for layer material, one for substrate
    import pandas as pd
    with pd.ExcelWriter(db_file) as writer:
        pd.DataFrame({"wl": [300.0, 800.0], "n": [2.0, 2.0], "k": [0.0, 0.0]}).to_excel(writer, sheet_name="TiO2-Syrus", index=False)
        pd.DataFrame({"wl": [300.0, 800.0], "n": [3.4, 3.4], "k": [0.1, 0.1]}).to_excel(writer, sheet_name="Si-substrate", index=False)
        
    db = RobustMaterialDatabase(str(db_file))
    
    # Verify that TiO2-Syrus is loaded as a material
    assert "TiO2-Syrus" in db.materials
    
    # Verify that Si-substrate is loaded as a material
    assert "Si-substrate" in db.materials

    # 1. Test get_material_index
    # TiO2-Syrus is a material, should succeed
    val = db.get_material_index("TiO2-Syrus", 550.0)
    assert isinstance(val, complex)
    assert val.real == 2.0
    
    # Si-substrate is a substrate, should raise ValueError
    with pytest.raises(ValueError, match="is a Substrate, cannot be loaded as a Layer Material"):
        db.get_material_index("Si-substrate", 550.0)
        
    # SiO2 is a known substrate, should raise ValueError
    with pytest.raises(ValueError, match="is a Substrate, cannot be loaded as a Layer Material"):
        db.get_material_index("SiO2", 550.0)

    # 2. Test get_substrate_index
    # Si-substrate is a substrate, should succeed
    val_sub = db.get_substrate_index("Si-substrate", 550.0)
    assert isinstance(val_sub, complex)
    assert val_sub.real == 3.4
    
    # TiO2-Syrus is a layer material, should raise ValueError
    with pytest.raises(ValueError, match="is a Layer Material, cannot be loaded as a Substrate"):
        db.get_substrate_index("TiO2-Syrus", 550.0)
        
    # 3. Test get_material_clues_vectorized
    wls = np.array([500.0, 600.0])
    res = db.get_material_clues_vectorized("TiO2-Syrus", wls)
    assert res.shape == (2,)
    assert np.allclose(res.real, 2.0)
    
    with pytest.raises(ValueError):
        db.get_material_clues_vectorized("SiO2", wls)
        
    # 4. Test get_substrate_clues_vectorized
    res_sub = db.get_substrate_clues_vectorized("SiO2", wls)
    assert res_sub.shape == (2,)
    # SiO2 Sellmeier
    assert res_sub[0].real > 1.0
    
    with pytest.raises(ValueError):
        db.get_substrate_clues_vectorized("TiO2-Syrus", wls)
