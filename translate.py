import sys
import os

file_path = 'certus/ui/certus_field_ui.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    'Aucun calcul effectué.': 'No calculation performed.',
    'Configuration invalide': 'Invalid configuration',
    'Configuration sauvegardée avec succès.': 'Configuration saved successfully.',
    'Erreur lors de la sauvegarde': 'Error saving',
    'Configuration chargée.': 'Configuration loaded.',
    'Erreur lors du chargement': 'Error loading',
    "Aucune donnée à exporter. Lancez un calcul d'abord.": 'No data to export. Run a calculation first.',
    'Rapports Excel et HTML générés avec succès.': 'Excel and HTML reports generated successfully.',
    'Erreur HTML, Excel généré.': 'HTML error, Excel generated.',
    "Erreur lors de l'exportation": 'Export error',
    'Aucun graphique à capturer.': 'No plot to capture.',
    'Capture enregistrée :': 'Screenshot saved:',
    'Erreur de capture :': 'Screenshot error:',
    "Module d'optimisation du champ électrique CERTUS.": 'CERTUS Electric Field Optimization module.',
    'Design importé.': 'Design imported.',
    "Erreur d'importation": 'Import error',
    'QWOT invalide à la ligne': 'Invalid QWOT at row',
    "L'empilement est vide.": 'Stack is empty.',
    "La longueur d'onde de centrage doit être positive.": 'Center wavelength must be positive.',
    'Erreur :': 'Error:',
    'Aucun résultat à exporter.': 'No result to export.',
    'Profil de champ': 'Field Profile',
    'Export CSV/Excel vers': 'Exported CSV/Excel to',
    'Données exportées avec succès.': 'Data exported successfully.',
    "Erreur d'exportation :": 'Export error:',
    "Échec de l'exportation :": 'Export failed:',
    'Génération du rapport HTML:': 'Generating HTML report:',
    'Rapport HTML généré.': 'HTML report generated.',
    'Erreur de rapport HTML :': 'HTML report error:',
    'Échec de génération :': 'Generation failed:',
    'Erreur fatale:': 'Fatal error:',
    'Échec:': 'Failed:',
    'Aucune donnée à exporter.': 'No data to export.',
    'Importer Design': 'Import Design',
    'Exporter vers Excel': 'Export to Excel',
    'Rapport HTML': 'HTML Report'
}

for fr, en in replacements.items():
    content = content.replace(fr, en)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Translation complete.')
