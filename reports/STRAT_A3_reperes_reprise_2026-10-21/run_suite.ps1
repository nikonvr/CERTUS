param(
    [string]$CampaignFolder = 'reports/STRAT_A3_reperes_reprise_2026-10-21'
)

$ErrorActionPreference = 'Stop'
$taskDeadline = [DateTimeOffset]::Parse('2026-10-21T08:00:00+00:00')
if ([DateTimeOffset]::UtcNow -ge $taskDeadline) {
    Write-Output 'A3_SUITE=DEADLINE_NO_LAUNCH'
    exit 0
}

$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
Set-Location -LiteralPath $taskRoot
if ((git branch --show-current) -ne 'codex/actions-prudentes-2026-10-20') {
    throw 'The campaign must use its designated branch'
}
if (Get-CimInstance Win32_Process -Filter "name = 'python.exe'") {
    throw 'Inspect existing Python processes before starting this suite'
}

Write-Output 'A3_SUITE=OFFICIAL_BENCHES'
& python (Join-Path $CampaignFolder 'run_A3_official_benches.py.txt') --outdir $CampaignFolder
$taskCode = $LASTEXITCODE
if ($taskCode -ne 0) { exit $taskCode }
$taskState = Get-Content -LiteralPath (Join-Path $CampaignFolder 'etat.json') -Raw | ConvertFrom-Json
if ($taskState.status -ne 'complete') {
    Write-Output ('A3_SUITE=STOPPED_AFTER_' + $taskState.status)
    exit 0
}
if ([DateTimeOffset]::UtcNow -ge $taskDeadline) {
    Write-Output 'A3_SUITE=INTERVALS_NOT_STARTED_DEADLINE'
    exit 0
}

Write-Output 'A3_SUITE=RETAINED_INTERVALS'
& python (Join-Path $CampaignFolder 'run_A3_retained_intervals.py.txt') --outdir $CampaignFolder
$taskCode = $LASTEXITCODE
Write-Output ('A3_SUITE=EXIT_' + $taskCode)
exit $taskCode
