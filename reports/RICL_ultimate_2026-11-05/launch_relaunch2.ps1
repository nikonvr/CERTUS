$d = 'D:\drivfl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\certus0310\reports\RICL_ultimate_2026-11-05'
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$cmd = "`"$ps`" -NoProfile -ExecutionPolicy Bypass -File `"$d\relaunch_after_driver2.ps1`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $cmd; CurrentDirectory = $d}
"pid $($r.ProcessId) rc $($r.ReturnValue)"
