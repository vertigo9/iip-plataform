$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "0695.7 package installer"
Write-Host "Repository: $Repo"

$TargetSrc = Join-Path $Repo "src"
$TargetTests = Join-Path $Repo "tests"
$TargetScripts = Join-Path $Repo "scripts"
$TargetDocs = Join-Path $Repo "docs"

New-Item -ItemType Directory -Force $TargetSrc | Out-Null
New-Item -ItemType Directory -Force (Join-Path $TargetSrc "iip") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $TargetSrc "iip\intelligence") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $TargetTests "intelligence") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $TargetTests "integration") | Out-Null
New-Item -ItemType Directory -Force $TargetScripts | Out-Null
New-Item -ItemType Directory -Force $TargetDocs | Out-Null

$PackageRoot = $Repo

Write-Host ""
Write-Host "ATENCAO:"
Write-Host "Este instalador foi desenhado para os arquivos aditivos do pacote."
Write-Host "Ele NAO executa persistencia e NAO modifica o Vault."
Write-Host ""
Write-Host "Antes de usar, revise os arquivos do pacote."

Write-Host ""
Write-Host "Depois da copia, execute:"
Write-Host "python .\scripts\RUN_0695_7_CONTRACT_CHECK_R1.py"
Write-Host "python .\scripts\RUN_0695_7_SEMANTIC_PIPELINE_R1.py"
