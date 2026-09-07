
$ErrorActionPreference = "Stop"

$runner = ".\RUN_0645_RELEASE_GATE_PROGRESS_ENGINE.ps1"
if (-not (Test-Path $runner)) { throw "Runner não encontrado: $runner" }

$backup = $runner + ".bak6"
Copy-Item $runner $backup -Force

$text = Get-Content -Raw -Path $runner
$start = $text.IndexOf('function Invoke-PythonTracked {')
$next = $text.IndexOf('$TotalSteps = 5')

if ($start -lt 0 -or $next -lt 0 -or $next -le $start) {
    throw "Bloco Invoke-PythonTracked esperado não encontrado."
}

$newFunction = @'
function Quote-CmdArgument {
    param([string]$Value)

    if ($Value -notmatch '[\s"&|<>^]') {
        return $Value
    }

    return '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

function Invoke-PythonTracked {
    param(
        [string]$StageName,
        [string[]]$PythonArguments
    )

    $id = $script:Step
    $work = Join-Path $env:TEMP ("iip_0645_{0}_{1}" -f $id, ([guid]::NewGuid().ToString("N")))
    New-Item -ItemType Directory -Path $work -Force | Out-Null

    $stdoutFile = Join-Path $work "stdout.txt"
    $stderrFile = Join-Path $work "stderr.txt"
    $exitFile = Join-Path $work "exit.txt"
    $cmdFile = Join-Path $work "run.cmd"

    $quotedArgs = $PythonArguments | ForEach-Object { Quote-CmdArgument $_ }
    $argString = ($quotedArgs -join " ")

    $cmdText = "@echo off`r`npython.exe $argString > `"$stdoutFile`" 2> `"$stderrFile`"`r`necho %ERRORLEVEL% > `"$exitFile`"`r`n"
    Set-Content -Path $cmdFile -Value $cmdText -Encoding ASCII

    $process = Start-Process -FilePath "cmd.exe" `
        -ArgumentList @("/c", $cmdFile) `
        -WorkingDirectory (Get-Location).Path `
        -WindowStyle Hidden `
        -PassThru

    Write-Status $script:Step $script:TotalSteps $StageName ("processo iniciado (PID=" + $process.Id + ")")

    $lastOut = 0
    $lastErr = 0
    $lastHeartbeat = Get-Date

    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 500

        $out = Get-Content $stdoutFile -Raw -ErrorAction SilentlyContinue
        $err = Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue
        if ($null -eq $out) { $out = "" }
        if ($null -eq $err) { $err = "" }

        if ($out.Length -gt $lastOut) {
            $delta = $out.Substring($lastOut)
            if ($delta.Trim().Length -gt 0) {
                Write-Host $delta.TrimEnd()
                Add-Content -Path $Report -Value $delta.TrimEnd() -Encoding ASCII
            }
            $lastOut = $out.Length
        }

        if ($err.Length -gt $lastErr) {
            $delta = $err.Substring($lastErr)
            if ($delta.Trim().Length -gt 0) {
                Write-Host ("[stderr] " + $delta.TrimEnd())
                Add-Content -Path $Report -Value ("[stderr] " + $delta.TrimEnd()) -Encoding ASCII
            }
            $lastErr = $err.Length
        }

        if (((Get-Date) - $lastHeartbeat).TotalSeconds -ge 5 -and -not $process.HasExited) {
            $elapsed = (Get-Date) - $Started
            $e = "{0:hh\:mm\:ss}" -f $elapsed
            Write-Host ("    ... ainda executando | etapa=" + $StageName + " | elapsed=" + $e + " | PID=" + $process.Id)
            Add-Content -Path $Report -Value ("    ... ainda executando | etapa=" + $StageName + " | elapsed=" + $e + " | PID=" + $process.Id) -Encoding ASCII
            $lastHeartbeat = Get-Date
        }
    }

    Start-Sleep -Milliseconds 250

    $out = Get-Content $stdoutFile -Raw -ErrorAction SilentlyContinue
    $err = Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue
    if ($null -eq $out) { $out = "" }
    if ($null -eq $err) { $err = "" }

    if ($out.Length -gt $lastOut) {
        $delta = $out.Substring($lastOut)
        if ($delta.Trim().Length -gt 0) {
            Write-Host $delta.TrimEnd()
            Add-Content -Path $Report -Value $delta.TrimEnd() -Encoding ASCII
        }
    }

    if ($err.Length -gt $lastErr) {
        $delta = $err.Substring($lastErr)
        if ($delta.Trim().Length -gt 0) {
            Write-Host ("[stderr] " + $delta.TrimEnd())
            Add-Content -Path $Report -Value ("[stderr] " + $delta.TrimEnd()) -Encoding ASCII
        }
    }

    if (-not (Test-Path $exitFile)) {
        throw "Arquivo de exit code não foi gerado: $exitFile"
    }

    $rawExit = (Get-Content $exitFile -Raw).Trim()
    if ($rawExit -notmatch '^\d+$') {
        throw "Exit code inválido no arquivo: '$rawExit'"
    }

    $code = [int]$rawExit

    Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue

    return $code
}

'@

$text = $text.Substring(0, $start) + $newFunction + $text.Substring($next)
Set-Content -Path $runner -Value $text -Encoding utf8

Write-Host "FIX6 aplicado com sucesso."
Write-Host "Exit code agora é obtido por arquivo gerado pelo cmd.exe."
Write-Host "Backup: $backup"
