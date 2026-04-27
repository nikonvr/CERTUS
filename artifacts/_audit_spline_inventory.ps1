$files = @(
    'CERTUS_INDEX_SPLINE.py',
    'certus_index_spline_core.py',
    'spline_pipeline.py',
    'spline_objective.py',
    'spline_finalize.py',
    'spline_nonlinear_alpha.py',
    'spline_smart_init.py',
    'spline_presets.py',
    'spline_workers.py',
    'spline_visual_utils.py',
    'spline_profile_corridors.py'
)
foreach ($f in $files) {
    Write-Output ('=== ' + $f + ' ===')
    Select-String -Path $f -Pattern '^(def|class|async def) [A-Za-z_]\w*' |
        ForEach-Object { '{0,5} {1}' -f $_.LineNumber, $_.Line.Trim() }
}
