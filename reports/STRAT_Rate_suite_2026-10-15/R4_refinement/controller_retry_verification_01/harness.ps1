$ErrorActionPreference='Stop'
$rateR4Root='D:\drivefl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\certus0310'
$rateR4Python='C:\Users\Lemarchand\AppData\Local\Programs\Python\Python314\python.exe'
$rateR4StatePath='D:\drivefl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\certus0310\reports\STRAT_Rate_suite_2026-10-15\R4_refinement\controller_retry_verification_01\state.json'
$rateR4State=[ordered]@{status='test';runs=@();current_pid=$null;persistence_retries=0}
function Save-RateR4State {
    $rateR4State['updated_utc'] = (Get-Date).ToUniversalTime().ToString('o')
    $rateR4Temp = $rateR4StatePath + '.tmp'
    for ($rateR4Retry=0; $rateR4Retry -lt 20; $rateR4Retry++) {
        try {
            [System.IO.File]::WriteAllText($rateR4Temp,($rateR4State | ConvertTo-Json -Depth 12),[System.Text.UTF8Encoding]::new($false))
            if (Test-Path -LiteralPath $rateR4StatePath) {
                [System.IO.File]::Replace($rateR4Temp,$rateR4StatePath,($rateR4StatePath + '.previous'))
            } else { [System.IO.File]::Move($rateR4Temp,$rateR4StatePath) }
            return
        } catch [System.IO.IOException] {
            if ($rateR4Retry -ge 19) { throw }
            $rateR4State['persistence_retries'] = 1 + [int]$rateR4State['persistence_retries']
            Start-Sleep -Milliseconds 100
        }
    }
}
function Invoke-RateR4Child($rateR4Arguments,$rateR4LogDirectory) {
    $rateR4Process = Start-Process -FilePath $rateR4Python -ArgumentList $rateR4Arguments -WorkingDirectory $rateR4Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $rateR4LogDirectory 'stdout.log') -RedirectStandardError (Join-Path $rateR4LogDirectory 'stderr.log')
    $rateR4Handle = $rateR4Process.Handle
    $rateR4Process.ProcessorAffinity = [IntPtr]16777215
    $rateR4Process.PriorityClass = 'Normal'
    $rateR4State['current_pid'] = $rateR4Process.Id
    Save-RateR4State
    $rateR4Process.WaitForExit()
    $rateR4Process.Refresh()
    if ($null -eq $rateR4Process.ExitCode -or $rateR4Process.ExitCode -ne 0) { throw ('Child failed: ' + $rateR4Process.Id + ', exit=' + $rateR4Process.ExitCode) }
    $rateR4State['runs'] += [ordered]@{pid=$rateR4Process.Id;exit_code=$rateR4Process.ExitCode;log_directory=$rateR4LogDirectory;ended_utc=(Get-Date).ToUniversalTime().ToString('o')}
    $rateR4State['current_pid']=$null
    Save-RateR4State
}function Save-OldRateR4State {
    $rateR4State['updated_utc'] = (Get-Date).ToUniversalTime().ToString('o')
    $rateR4Temp = $rateR4StatePath + '.tmp'
    [System.IO.File]::WriteAllText($rateR4Temp,($rateR4State | ConvertTo-Json -Depth 10),[System.Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $rateR4StatePath) {
        [System.IO.File]::Replace($rateR4Temp,$rateR4StatePath,($rateR4StatePath + '.previous'))
    } else { [System.IO.File]::Move($rateR4Temp,$rateR4StatePath) }
}

Save-RateR4State
$rateReaderProcess=Start-Process -FilePath 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -ArgumentList @('-NoProfile','-Command',('"'+'$rateReader=[IO.File]::Open(''D:\drivefl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\certus0310\reports\STRAT_Rate_suite_2026-10-15\R4_refinement\controller_retry_verification_01\state.json'',''Open'',''Read'',''Read''); try { [IO.File]::WriteAllText(''D:\drivefl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\certus0310\reports\STRAT_Rate_suite_2026-10-15\R4_refinement\controller_retry_verification_01\reader_ready'',''ready''); Start-Sleep -Milliseconds 900 } finally { $rateReader.Dispose() }'+'"')) -WindowStyle Hidden -PassThru
$rateReaderHandle=$rateReaderProcess.Handle
for($ratePoll=0;$ratePoll -lt 50 -and -not(Test-Path -LiteralPath 'D:\drivefl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\certus0310\reports\STRAT_Rate_suite_2026-10-15\R4_refinement\controller_retry_verification_01\reader_ready');$ratePoll++){Start-Sleep -Milliseconds 50}
if(-not(Test-Path -LiteralPath 'D:\drivefl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\certus0310\reports\STRAT_Rate_suite_2026-10-15\R4_refinement\controller_retry_verification_01\reader_ready')){throw 'Reader lock setup failed'}
$rateBeforeFailed=$false
try { Save-OldRateR4State } catch { $rateBeforeFailed=$true }
if(-not $rateBeforeFailed){throw 'Old save unexpectedly passed under denied-delete reader'}
Save-RateR4State
$rateReaderProcess.WaitForExit()
if($rateR4State.persistence_retries -lt 1){throw 'Retry was not exercised'}
Invoke-RateR4Child @('-c','"print(1)"') 'D:\drivefl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\CERTUS\certus0310\reports\STRAT_Rate_suite_2026-10-15\R4_refinement\controller_retry_verification_01'
$rateR4State['before_failed']=$rateBeforeFailed
Save-RateR4State
