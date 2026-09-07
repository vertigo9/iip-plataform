
$ErrorActionPreference = "Stop"

$path = ".\RUN_0644_INTEGRATED_PROGRESS_FIX_PLUS.ps1"
if (-not (Test-Path $path)) {
    throw "Arquivo não encontrado: $path"
}

$backup = $path + ".bak2"
Copy-Item $path $backup -Force

$text = Get-Content -Raw -Path $path

$bad = '        Tee-Object -FilePath "$env:TEMP\iip_0644_"$name"_fixplus.txt" |'
$good = '        Tee-Object -FilePath (Join-Path $env:TEMP ("iip_0644_{0}_fixplus.txt" -f $name)) |'

if (-not $text.Contains($bad)) {
    throw "Linha problemática não encontrada no executor."
}

$text = $text.Replace($bad, $good)
Set-Content -Path $path -Value $text -Encoding utf8

Write-Host "FIX2 aplicado com sucesso."
Write-Host "Correção: construção do FilePath do Tee-Object."
Write-Host "Backup: $backup"
