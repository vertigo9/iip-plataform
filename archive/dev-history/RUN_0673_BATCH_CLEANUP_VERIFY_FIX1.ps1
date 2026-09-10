$ErrorActionPreference = "Stop"

$Base = (Get-Location).Path
$Report = Join-Path $Base "D-OBSIDIAN-06.7_BATCH_CLEANUP_VERIFY_FIX1.txt"
Remove-Item $Report -Force -ErrorAction SilentlyContinue

function W([string]$x) {
    Write-Host $x
    Add-Content $Report $x -Encoding ASCII
}

W "D-OBSIDIAN-06.7 BATCH CLEANUP VERIFY FIX1"
W "No source files will be moved or deleted."
W ""

W "=== PACKAGE SOURCE CHECK ==="
$init = Join-Path $Base "src\iip\__init__.py"
$pyproject = Join-Path $Base "pyproject.toml"

W ("src\iip\__init__.py exists: " + (Test-Path $init))
W ("pyproject.toml exists: " + (Test-Path $pyproject))

W ""
W "=== INSTALLED PACKAGE CHECK ==="
python -m pip show iip-platform 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0673_pip_show_fix1.txt") |
    Tee-Object $Report -Append

W ""
W "=== PYTHON PATH BEFORE OVERRIDE ==="
python -c "import sys; print('`n'.join(sys.path))" 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0673_path_before.txt") |
    Tee-Object $Report -Append

W ""
W "=== TEMPORARY SOURCE PATH VALIDATION ==="
$oldPyPath = $env:PYTHONPATH
$srcPath = Join-Path $Base "src"
if ($oldPyPath) {
    $env:PYTHONPATH = "$srcPath;$oldPyPath"
} else {
    $env:PYTHONPATH = $srcPath
}

python -c "import iip; import iip.knowledge; print('iip=', iip.__file__); print('knowledge=', iip.knowledge.__file__)" 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0673_import_fix1.txt") |
    Tee-Object $Report -Append

if ($LASTEXITCODE -ne 0) {
    W "STATUS: SOURCE IMPORT STILL FAILS"
    exit $LASTEXITCODE
}

W ""
W "=== FULL REGRESSION WITH EXPLICIT SOURCE PATH ==="
python -m pytest --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0673_regression_fix1.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    W ("STATUS: REGRESSION FAIL exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

W ""
W "STATUS: CLEANUP VERIFY FIX1 PASS"
W "The post-cleanup environment requires explicit src path resolution."
W "No files were moved/deleted by this verify script."
Write-Host ""
Write-Host "Relatorio: $Report"
