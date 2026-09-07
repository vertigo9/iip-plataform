
$ErrorActionPreference = "Stop"

$path = ".\RUN_0645_RELEASE_GATE_PROGRESS_ENGINE.ps1"
if (-not (Test-Path $path)) { throw "Executor não encontrado: $path" }

$backup = $path + ".bak3"
Copy-Item $path $backup -Force

$text = Get-Content -Raw -Path $path

$start = $text.IndexOf('function Invoke-PythonTracked {')
$next = $text.IndexOf('$Harness =')

if ($start -lt 0 -or $next -lt 0 -or $next -le $start) {
    throw "Bloco Invoke-PythonTracked esperado não encontrado."
}

$newFunction = @'
function Invoke-PythonTracked {
    param(
        [string[]]$PythonArguments,
        [string]$StageName
    )

    $stdoutFile = Join-Path $env:TEMP ("iip_0645_{0}_stdout.txt" -f $script:CurrentStep)
    $stderrFile = Join-Path $env:TEMP ("iip_0645_{0}_stderr.txt" -f $script:CurrentStep)

    Remove-Item $stdoutFile,$stderrFile -Force -ErrorAction SilentlyContinue
    New-Item -ItemType File -Path $stdoutFile -Force | Out-Null
    New-Item -ItemType File -Path $stderrFile -Force | Out-Null

    $argumentList = @("-m") + @($PythonArguments[1..($PythonArguments.Count - 1)])
    $process = Start-Process -FilePath "python" `
        -ArgumentList $argumentList `
        -WorkingDirectory (Get-Location).Path `
        -RedirectStandardOutput $stdoutFile `
        -RedirectStandardError $stderrFile `
        -NoNewWindow `
        -PassThru

    Write-Status $script:CurrentStep $script:TotalSteps $StageName "processo iniciado (PID=$($process.Id))"

    $seenOut = 0
    $seenErr = 0
    $lastHeartbeat = Get-Date

    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 500

        $outText = Get-Content $stdoutFile -Raw -ErrorAction SilentlyContinue
        $errText = Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue

        if ($null -ne $outText -and $outText.Length -gt $seenOut) {
            $delta = $outText.Substring($seenOut)
            if ($delta.Trim().Length -gt 0) {
                Write-Host $delta.TrimEnd()
                Add-Content -Path $Report -Value $delta.TrimEnd() -Encoding ASCII
            }
            $seenOut = $outText.Length
        }

        if ($null -ne $errText -and $errText.Length -gt $seenErr) {
            $delta = $errText.Substring($seenErr)
            if ($delta.Trim().Length -gt 0) {
                Write-Host ("[stderr] " + $delta.TrimEnd())
                Add-Content -Path $Report -Value ("[stderr] " + $delta.TrimEnd()) -Encoding ASCII
            }
            $seenErr = $errText.Length
        }

        if (((Get-Date) - $lastHeartbeat).TotalSeconds -ge 5) {
            $elapsed = (Get-Date) - $Started
            $elapsedText = "{0:hh\:mm\:ss}" -f $elapsed
            Write-Host ("    ... ainda executando | etapa=$StageName | elapsed=$elapsedText | PID=$($process.Id)")
            Add-Content -Path $Report -Value ("    ... ainda executando | etapa=$StageName | elapsed=$elapsedText | PID=$($process.Id)") -Encoding ASCII
            $lastHeartbeat = Get-Date
        }

        $process.Refresh()
    }

    # Final drain after process exit.
    Start-Sleep -Milliseconds 250

    $outText = Get-Content $stdoutFile -Raw -ErrorAction SilentlyContinue
    $errText = Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue

    if ($null -ne $outText -and $outText.Length -gt $seenOut) {
        $delta = $outText.Substring($seenOut)
        if ($delta.Trim().Length -gt 0) {
            Write-Host $delta.TrimEnd()
            Add-Content -Path $Report -Value $delta.TrimEnd() -Encoding ASCII
        }
    }

    if ($null -ne $errText -and $errText.Length -gt $seenErr) {
        $delta = $errText.Substring($seenErr)
        if ($delta.Trim().Length -gt 0) {
            Write-Host ("[stderr] " + $delta.TrimEnd())
            Add-Content -Path $Report -Value ("[stderr] " + $delta.TrimEnd()) -Encoding ASCII
        }
    }

    $code = $process.ExitCode

    Remove-Item $stdoutFile,$stderrFile -Force -ErrorAction SilentlyContinue

    return @{
        ExitCode = $code
        Lines = (($outText + "`n" + $errText) -split "`r?`n").Count
    }
}

'@

$text = $text.Substring(0, $start) + $newFunction + $text.Substring($next)
Set-Content -Path $path -Value $text -Encoding utf8

Write-Host "FIX3 Progress Engine aplicado com sucesso."
Write-Host "Correção: monitoramento por arquivos redirecionados + polling."
Write-Host "Backup: $backup"
