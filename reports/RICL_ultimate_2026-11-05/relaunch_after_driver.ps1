# Audit 2026-11-07 (owner): wait for the running driver (PID 17656) to exit, then start a new 24 h driver.
# Launched itself through WMI (Win32_Process.Create) so that an app restart does not kill it.
$dir = 'D:\drivfl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\certus0310\reports\RICL_ultimate_2026-11-05'
$log = Join-Path $dir 'relaunch_after_driver.log'
Add-Content $log "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') waiting for PID 17656"
while (Get-Process -Id 17656 -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 60 }
$py = 'C:\Users\Fabien\AppData\Local\Programs\Python\Python315\python.exe'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = "`"$py`" orchestrate.py 24"; CurrentDirectory = $dir}
Add-Content $log "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') new driver started: pid $($r.ProcessId) rc $($r.ReturnValue)"
