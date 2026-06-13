import sys

file_path = 'certus/workers/certus_field_workers.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    "Fonction coût pour l'optimisation, évaluée sur toutes les longueurs d'onde.": "Cost function for optimization, evaluated on all wavelengths.",
    "Worker asynchrone pour les calculs et l'optimisation du champ électrique.": "Asynchronous worker for electric field calculations and optimization.",
    "Paramètre incohérent:": "Inconsistent parameter:",
    "contient": "contains",
    "valeur(s) pour": "value(s) for",
    "longueur(s) d'onde": "wavelength(s)",
    "Démarrage de _run_calculate. Nombre de couches:": "Starting _run_calculate. Number of layers:",
    "Calcul analytique Numba terminé en": "Numba analytical calculation finished in",
    "Points générés:": "Points generated:",
    "Calcul terminé.": "Calculation finished.",
    "Calcul réussi.": "Calculation successful.",
    "Démarrage de _run_tolerate avec erreur": "Starting _run_tolerate with error",
    "itérations terminé en": "iterations finished in",
    "Calcul Monte-Carlo terminé.": "Monte-Carlo calculation finished.",
    "Tolérancement": "Tolerancing",
    "terminé.": "finished.",
    "scipy n'est pas installé. Optimisation impossible.": "scipy is not installed. Optimization impossible.",
    "Démarrage de l'optimisation L-BFGS-B. Seuils (H=": "Starting L-BFGS-B optimization. Thresholds (H=",
    "Préparation de l'optimisation...": "Preparing optimization...",
    "Optimisation annulée par l'utilisateur.": "Optimization cancelled by user.",
    "Aucune solution d'optimisation exploitable n'a été trouvée.": "No usable optimization solution found.",
    "Multi-Start terminé en": "Multi-Start finished in",
    "Évaluations:": "Evaluations:",
    "Meilleur coût:": "Best cost:",
    "Génération des métriques finales...": "Generating final metrics...",
    "Métriques finales:": "Final metrics:",
    "Optimisation terminée avec succès.": "Optimization finished successfully.",
    "Paramètre manquant:": "Missing parameter:",
    "Paramètre vide:": "Empty parameter:",
    "Action inconnue:": "Unknown action:",
    "Calcul du champ...": "Calculating field...",
    "Lancement du Monte-Carlo...": "Starting Monte-Carlo...",
    "Monte-Carlo": "Monte-Carlo",
    "Optimisation interrompue par l'utilisateur": "Optimization interrupted by user",
    "Optimisation en cours": "Optimization running"
}

for fr, en in replacements.items():
    content = content.replace(fr, en)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Translation complete for certus_field_workers.py.')
