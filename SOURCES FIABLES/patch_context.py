import re

filepath = r'certus\utils\certus_strat_context.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

replacement1 = """    def get_refractive_index(self, mat_id: str, wl: float) -> complex:
        \"\"\"Get refractive index for material at wavelength.\"\"\"
        from certus_physics import get_refractive_index as physics_get_ri
        return physics_get_ri(mat_id, wl, self.material_db)
"""

pattern1 = r'^[ \t]{4}def get_refractive_index\(self, mat_id: str, wl: float\) -> complex:\n(?:[ \t]+.*?\n)*?(?=[ \t]{4}def |\Z)'
content = re.sub(pattern1, replacement1 + '\n', content, flags=re.MULTILINE)

replacement2 = """    def get_refractive_clues_vectorized(self, mat_id: str, wls: np.ndarray) -> np.ndarray:
        \"\"\"Get refractive clues for material at multiple wavelengths.\"\"\"
        from certus_physics import get_refractive_clues_vectorized as physics_get_clues
        return physics_get_clues(mat_id, wls, self.material_db)
"""

pattern2 = r'^[ \t]{4}def get_refractive_clues_vectorized\(self, mat_id: str, wls: np\.ndarray\) -> np\.ndarray:\n(?:[ \t]+.*?\n)*?(?=[ \t]{4}def |\Z)'
content = re.sub(pattern2, replacement2 + '\n', content, flags=re.MULTILINE)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched certus_strat_context.py')
