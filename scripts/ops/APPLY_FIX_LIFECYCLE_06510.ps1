
$ErrorActionPreference = "Stop"

$active = ".\src\iip\knowledge\event_adapter.py"
$backup = $active + ".bak-lifecycle"

if (-not (Test-Path $active)) {
    throw "Active adapter não encontrado: $active"
}

Copy-Item $active $backup -Force

$text = Get-Content -Raw -Path $active

if ($text -match 'def register\(self\)') {
    Write-Host "Adapter já possui register(); nenhuma alteração necessária."
    exit 0
}

$needle = "    def __init__(self, bridge)"
$idx = $text.IndexOf($needle)

if ($idx -lt 0) {
    throw "Não foi possível localizar __init__ no adapter ativo."
}

$insert = @'
    def register(self) -> None:
        """Register this adapter on the IIP EventBus."""
        from iip.events import EventBus

        EventBus.subscribe("iip.decision.created.v1", self.on_decision)
        EventBus.subscribe("iip.portfolio.snapshot_created.v1", self.on_snapshot)
        EventBus.subscribe("atlas.document.processed.v1", self.on_document)

    def unregister(self) -> None:
        """Remove this adapter from the IIP EventBus."""
        from iip.events import EventBus

        EventBus.unsubscribe("iip.decision.created.v1", self.on_decision)
        EventBus.unsubscribe("iip.portfolio.snapshot_created.v1", self.on_snapshot)
        EventBus.unsubscribe("atlas.document.processed.v1", self.on_document)

'@

$text = $text.Substring(0, $idx) + $insert + $text.Substring($idx)

Set-Content -Path $active -Value $text -Encoding utf8

Write-Host "Minimal lifecycle fix aplicado com sucesso."
Write-Host "Adicionados: register()/unregister() no adapter ativo."
Write-Host "Backup: $backup"
