import sys
import glob

replacements = {
    "Intensité normalisée |E|²": "Normalized Intensity |E|²",
    "Pour le tracé on renvoie le champ S par défaut pour simplifier, ou on pourrait interpoler.": "For plotting we return the S field by default for simplicity, or we could interpolate.",
    "Détails du Champ": "Field Details",
    "Ce rapport contient la distribution spatiale de l'intensité du champ électrique à l'intérieur de l'empilement optique.": "This report contains the spatial distribution of the electric field intensity inside the optical stack.",
    "Rapports générés dans :": "Reports generated in :",
    "Paramètres haute qualité": "High quality parameters",
    "Terminé.": "Finished."
}

files = [
    'certus/core/certus_field_core.py',
    'certus/ui/certus_field_plot.py',
    'certus/ui/certus_field_services.py'
]

for file_path in files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for fr, en in replacements.items():
            content = content.replace(fr, en)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Translated {file_path}')
    except Exception as e:
        print(f"Failed {file_path}: {e}")
