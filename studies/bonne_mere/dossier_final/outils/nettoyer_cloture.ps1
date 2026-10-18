$ErrorActionPreference = 'Stop'
$studyRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $studyRoot '..\..')).Path
$finalRoot = Join-Path $studyRoot 'dossier_final'
$inventoryPath = Join-Path $finalRoot 'inventaire_avant_reduction.json'
$inventory = Get-Content -LiteralPath $inventoryPath -Raw | ConvertFrom-Json
$newArchive = Join-Path $studyRoot 'archives\Bonne_Mere_sources_finales.zip'
if ((Get-FileHash -LiteralPath $newArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inventory.archive_sha256) { throw 'Archive hash mismatch' }
foreach ($required in @('Bonne_Mere_Dossier_Complet.docx','Bonne_Mere_Dossier_Complet.pdf','donnees\strategie_retenue_452nm.json','donnees\preuves_appariees_452nm_3graines.npz')) {
    if (-not (Test-Path -LiteralPath (Join-Path $finalRoot $required) -PathType Leaf)) { throw "Missing preserved file $required" }
}
$removed = [System.Collections.Generic.List[object]]::new()
function Remove-Checked([string]$Target, [string]$Scope, [string]$Reason) {
    if (-not (Test-Path -LiteralPath $Target)) { return }
    $absoluteTarget = (Resolve-Path -LiteralPath $Target).Path
    $absoluteScope = (Resolve-Path -LiteralPath $Scope).Path.TrimEnd('\')
    if (-not $absoluteTarget.StartsWith($absoluteScope + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe cleanup path $absoluteTarget" }
    $item = Get-Item -LiteralPath $absoluteTarget -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing reparse point $absoluteTarget" }
    $bytes = if ($item.PSIsContainer) { (Get-ChildItem -LiteralPath $absoluteTarget -Recurse -Force -File | Measure-Object Length -Sum).Sum } else { $item.Length }
    Remove-Item -LiteralPath $absoluteTarget -Force -Recurse
    $removed.Add([pscustomobject]@{path=$absoluteTarget.Substring($projectRoot.Length+1);bytes=[long]$bytes;reason=$Reason})
}
# Validated final archive replaces the larger intermediate archive, all inside the project.
Remove-Checked (Join-Path $studyRoot 'archives\Bonne_Mere_sources_et_metadonnees.zip') $studyRoot 'superseded temporary archive'
Move-Item -LiteralPath $newArchive -Destination (Join-Path $studyRoot 'archives\Bonne_Mere_sources_et_metadonnees.zip')
foreach ($name in @('Bonne_Mere_archive_compacte.zip','sources_dedupliquees.tar.xz')) {
    Remove-Checked (Join-Path $studyRoot ('archives\' + $name)) $studyRoot 'temporary compression intermediate'
}
foreach ($name in @('cache_numba','code_certus','code_certus_7f3edea8.zip','design','materials','output','reports','runtime_ui_support','scripts','sources','target','tmp')) {
    Remove-Checked (Join-Path $studyRoot $name) $studyRoot 'authorized Bonne Mere research reduction; sources and text preserved in validated compact archive'
}
Remove-Checked $inventoryPath $finalRoot 'identical full inventory preserved in archives/Bonne_Mere_inventaire_avant_reduction.zip'
$cacheNames = @('__pycache__','.pytest_cache','.ruff_cache','.hypothesis')
$cachePaths = @(Get-ChildItem -LiteralPath $projectRoot -Recurse -Force -Directory | Where-Object { $_.Name -in $cacheNames } | Sort-Object { $_.FullName.Length } -Descending)
foreach ($cache in $cachePaths) { Remove-Checked $cache.FullName $projectRoot 'regenerable cache' }
foreach ($name in @('bonne_mere_document_qa','bonne_mere_document_qa_v2','bonne_mere_document_qa_final','bonne_mere_document_qa_delivery')) {
    Remove-Checked (Join-Path $projectRoot ('tmp\' + $name)) $projectRoot 'document visual QA intermediate'
}
$tracked = @(& git -C $projectRoot ls-files)
$generated = @(Get-ChildItem -LiteralPath $projectRoot -Force -File | Where-Object { $_.Name -in @('coverage.xml','.coverage') -or ($_.Name.StartsWith('certus_') -and $_.Extension -in @('.log','.jsonl')) })
foreach ($file in $generated) {
    if ($tracked -contains $file.Name) { throw "Refusing tracked file $($file.Name)" }
    Remove-Checked $file.FullName $projectRoot 'untracked generated application log or coverage output'
}
$total = [long](Get-ChildItem -LiteralPath $projectRoot -Recurse -Force -File | Measure-Object Length -Sum).Sum
$studyTotal = [long](Get-ChildItem -LiteralPath $studyRoot -Recurse -Force -File | Measure-Object Length -Sum).Sum
$report = [ordered]@{date='2026-10-18';authorization='Fabien: nettoyage et limite de 1 Go avec Bonne Mere inclus; supprimer maintenant';no_external_archive=$true;project_bytes_before=7847296824;project_bytes_after=$total;study_bytes_after=$studyTotal;limit_bytes=1000000000;under_limit=($total -lt 1000000000);production_sources_changed=$false;commit_or_push=$false;removed=$removed}
$report | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $finalRoot 'rapport_nettoyage.json') -Encoding utf8
Write-Output ($report | Select-Object project_bytes_after,study_bytes_after,limit_bytes,under_limit,no_external_archive | ConvertTo-Json -Compress)
if ($total -ge 1000000000) { throw 'Size limit not yet met' }
