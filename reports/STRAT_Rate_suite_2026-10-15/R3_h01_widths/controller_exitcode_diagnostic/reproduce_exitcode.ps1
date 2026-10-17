$ErrorActionPreference='Stop'
$rateR3Python=(Get-Command python).Source
$rateR3Cases=@()
foreach($rateR3KeepHandle in @($false,$true)) {
 $rateR3Probe=Start-Process -FilePath $rateR3Python -ArgumentList @('-c','"pass"') -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot ('case_'+$rateR3KeepHandle+'_out.log')) -RedirectStandardError (Join-Path $PSScriptRoot ('case_'+$rateR3KeepHandle+'_err.log'))
 if($rateR3KeepHandle){$rateR3Handle=$rateR3Probe.Handle}
 $rateR3Probe.WaitForExit()
 $rateR3Probe.Refresh()
 $rateR3Cases += [ordered]@{keep_handle=$rateR3KeepHandle;exit_code=$rateR3Probe.ExitCode;exit_code_is_null=($null -eq $rateR3Probe.ExitCode);old_condition_would_fail=($rateR3Probe.ExitCode -ne 0);has_exited=$rateR3Probe.HasExited}
}
$rateR3Record=[ordered]@{powershell=$PSVersionTable.PSVersion.ToString();observed_utc=(Get-Date).ToUniversalTime().ToString('o');cases=$rateR3Cases;physics_measured=$false}
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'windows_powershell_comparison.json'),($rateR3Record|ConvertTo-Json -Depth 6),[System.Text.UTF8Encoding]::new($false))
$rateR3Record|ConvertTo-Json -Depth 6
