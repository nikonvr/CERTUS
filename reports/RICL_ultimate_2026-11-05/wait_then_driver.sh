cd "D:/drivfl/01_Recherche_Enseignement/02_Couches_Minces_Optique/couches minces 2026/CERTUS/certus0310/reports/RICL_ultimate_2026-11-05"
until grep -q "driver end" orchestrate.log; do sleep 60; done
/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w /tmp/launch3.ps1)" >> wait_then_driver.log 2>&1
