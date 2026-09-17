
function Add-ContextMatches(
    [System.IO.FileInfo]$File,
    [string[]]$Patterns,
    [int]$Before = 5,
    [int]$After = 8
) {
    $Content = @(Get-Content -LiteralPath $File.FullName)

    if ($Content.Length -eq 0) {
        return
    }

    $MatchedLines = @()

    for ($i = 0; $i -lt $Content.Length; $i++) {
        foreach ($Pattern in $Patterns) {
            if ($Content[$i] -match $Pattern) {
                $MatchedLines += $i
                break
            }
        }
    }

    if ($MatchedLines.Length -eq 0) {
        return
    }

    Add-Section "REFERÊNCIAS / CONTEXTO: $($File.FullName)"

    foreach ($Hit in $MatchedLines) {
        $Start = [Math]::Max(0, $Hit - $Before)
        $End = [Math]::Min($Content.Length - 1, $Hit + $After)

        $Lines.Add("--- Ocorrência na linha $($Hit + 1); contexto $($Start + 1)-$($End + 1) ---")

        for ($j = $Start; $j -le $End; $j++) {
            $Lines.Add(("{0,5}: {1}" -f ($j + 1), $Content[$j]))
        }
    }
}