@echo off
echo =======================================================================
echo     LANCEMENT DES TESTS DE NON-REGRESSION CERTUS (GOLDEN MASTER)
echo =======================================================================
echo.
echo ATTENTION : Ce script valide que vos modifications n'ont pas degrade
echo la convergence algorithmique des 7 modules principaux de CERTUS.
echo.
echo Ce test est OBLIGATOIRE avant toute validation de code ou de refactoring.
echo.
pause
echo.

set PYTHONPATH=%~dp0
python tests\regression\test_convergence.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!!!] ECHEC DES TESTS DE CONVERGENCE [!!!]
    echo Vos dernieres modifications ont degrade les performances de CERTUS.
    echo Veuillez annuler ou corriger vos changements.
    pause
    exit /b %ERRORLEVEL%
) else (
    echo.
    echo [OK] TESTS PASSES AVEC SUCCES [OK]
    echo La stabilite numerique est confirmee.
    pause
)
