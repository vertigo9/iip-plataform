
$ErrorActionPreference = "Stop"

$path = ".\RUN_0645_RELEASE_GATE_PROGRESS_ENGINE.ps1"
if (-not (Test-Path $path)) { throw "Executor não encontrado: $path" }

$backup = $path + ".bak2"
Copy-Item $path $backup -Force

$text = Get-Content -Raw -Path $path

$start = $text.IndexOf('function Invoke-PythonTracked {')
$next = $text.IndexOf('$TotalSteps = 5')

if ($start -lt 0 -or $next -lt 0 -or $next -le $start) {
    throw "Bloco Invoke-PythonTracked esperado não encontrado."
}

$newFunction = @'
function Invoke-PythonTracked {
    param(
        [string[]]$PythonArguments,
        [string]$StageName
    )

    # Event-driven output avoids ReadLine() blocking on a long-running pytest
    # process. This is compatible with Windows PowerShell 5.1.
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "python"
    $psi.WorkingDirectory = (Get-Location).Path
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $quoted = foreach ($arg in $PythonArguments) {
        if ($arg -match '[\s"]') {
            '"' + ($arg -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
        } else {
            $arg
        }
    }
    $psi.Arguments = ($quoted -join ' ')

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $lineCount = 0
    $lastHeartbeat = Get-Date

    $outputHandler = [System.Diagnostics.DataReceivedEventHandler]{
        param($sender, $event)
        if ($null -ne $event.Data) {
            $script:TrackedLineCount++
            Write-Host ("    " + $event.Data)
            Add-Content -Path $script:TrackedReport -Value $event.Data -Encoding ASCII
        }
    }

    $errorHandler = [System.Diagnostics.DataReceivedEventHandler]{
        param($sender, $event)
        if ($null -ne $event.Data) {
            Write-Host ("    [stderr] " + $event.Data)
            Add-Content -Path $script:TrackedReport -Value ("[stderr] " + $event.Data) -Encoding ASCII
        }
    }

    $script:TrackedLineCount = 0
    $script:TrackedReport = $Report

    $process.add_OutputDataReceived($outputHandler)
    $process.add_ErrorDataReceived($errorHandler)

    if (-not $process.Start()) {
        throw "Não foi possível iniciar Python."
    }

    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()

    Write-Status $script:CurrentStep $script:TotalSteps $StageName "processo iniciado (PID=$($process.Id))"

    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 500

        if (((Get-Date) - $lastHeartbeat).TotalSeconds -ge 5) {
            $elapsed = (Get-Date) - $Started
            $elapsedText = "{0:hh\:mm\:ss}" -f $elapsed
            Write-Host ("    ... ainda executando | etapa=$StageName | elapsed=$elapsedText | linhas=$script:TrackedLineCount")
            Add-Content -Path $Report -Value ("    ... ainda executando | etapa=$StageName | elapsed=$elapsedText | linhas=$script:TrackedLineCount") -Encoding ASCII
            $lastHeartbeat = Get-Date
        }
    }

    # Allow asynchronous output events to drain.
    Start-Sleep -Milliseconds 250

    $code = $process.ExitCode
    $process.remove_OutputDataReceived($outputHandler)
    $process.remove_ErrorDataReceived($errorHandler)
    $process.Dispose()

    return @{
        ExitCode = $code
        Lines = $script:TrackedLineCount
    }
}

'@

$text = $text.Substring(0, $start) + $newFunction + $text.Substring($next)
Set-Content -Path $path -Value $text -Encoding utf8

Write-Host "FIX2 Progress Engine aplicado com sucesso."
Write-Host "Correção: leitura assíncrona por eventos; heartbeat não bloqueante."
Write-Host "Backup: $backup"
