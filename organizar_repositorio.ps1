# organizar_repositorio.ps1
#
# Organiza a raiz do repositorio ANTES do commit de recuperacao.
# NAO faz nenhum commit, NAO apaga nada, NAO mexe em src/, tests/ ou vault/.
# So MOVE arquivos soltos para duas pastas novas:
#
#   archive/dev-history/        -> scripts de sessao antigos (RUN_, FIX_,
#                                   IMPLEMENT_, DIAG_, AUDIT_, README_ etc.)
#                                   preservados, so tirados da raiz.
#   _lixo_para_revisar/         -> coisas que parecem lixo (instaladores,
#                                   duplicatas "(1)", arquivos .bak, etc.)
#                                   Revise essa pasta e apague manualmente
#                                   o que confirmar que nao serve.
#
# Rode a partir da raiz do repositorio:
#   powershell -ExecutionPolicy Bypass -File organizar_repositorio.ps1

$ErrorActionPreference = "SilentlyContinue"

$archiveDir = "archive\dev-history"
$archiveScriptsDir = "archive\dev-history\src-iip-scripts"
$lixoDir = "_lixo_para_revisar"

New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null
New-Item -ItemType Directory -Force -Path $archiveScriptsDir | Out-Null
New-Item -ItemType Directory -Force -Path $lixoDir | Out-Null

# --- 1) Scripts de sessao soltos na raiz (nao mexe em pastas conhecidas) ---
$prefixosSessao = @(
    "RUN_", "RUN-", "FIX_", "IMPLEMENT_", "INSPECT_", "DIAG_", "DIAGNOSTIC_",
    "DEBUG_", "AUDIT_", "GATE_", "FIND_", "FINAL_", "RELEASE_", "ROLLBACK_",
    "RESTORE_", "INSTALL_", "MANIFEST", "README_", "D-OBSIDIAN-", "0693_",
    "0674_", "0673_", "0672_", "0671_", "GENERIC_", "TRACE_", "IIP_D-",
    "POST95_", "SHA256_"
)

$movidosSessao = 0
Get-ChildItem -Path . -File | Where-Object {
    $nome = $_.Name
    $prefixosSessao | Where-Object { $nome.StartsWith($_) }
} | ForEach-Object {
    Move-Item -Path $_.FullName -Destination $archiveDir -Force
    $movidosSessao++
}

# --- 2) Scripts de sessao que acabaram DENTRO do pacote (src/iip/scripts) ---
$movidosSrcScripts = 0
if (Test-Path "src\iip\scripts") {
    Get-ChildItem -Path "src\iip\scripts" -File -Filter "*.py" | ForEach-Object {
        Move-Item -Path $_.FullName -Destination $archiveScriptsDir -Force
        $movidosSrcScripts++
    }
}

# --- 3) Lixo obvio: instaladores, duplicatas, backups, arquivos malformados ---
$padroesLixo = @(
    "*Installer*.exe", "*.winmd", "* (1).*", "* (2).*",
    "*.bak", "*.bak1", "*.bak2", "*.bak-http-gate", "*.pre-fix",
    "*-v2-backup", "Sem t*tulo*.base"
)

$movidosLixo = 0
foreach ($padrao in $padroesLixo) {
    Get-ChildItem -Path . -File -Filter $padrao | ForEach-Object {
        Move-Item -Path $_.FullName -Destination $lixoDir -Force
        $movidosLixo++
    }
}

# --- 4) Projetos-satelite soltos (patria_*) -> arquivados junto, nao apagados ---
$satelites = @("patria_harvester_patch", "patria_harvester_patch_v4")
foreach ($pasta in $satelites) {
    if (Test-Path $pasta) {
        Move-Item -Path $pasta -Destination $archiveDir -Force
    }
}
Get-ChildItem -Path . -File -Filter "patria_*.txt" | ForEach-Object {
    Move-Item -Path $_.FullName -Destination $archiveDir -Force
}
Get-ChildItem -Path . -File -Filter "*patria*.txt" | ForEach-Object {
    Move-Item -Path $_.FullName -Destination $archiveDir -Force
}

Write-Host ""
Write-Host "===== RESUMO ====="
Write-Host "Scripts de sessao (raiz) movidos para $archiveDir : $movidosSessao"
Write-Host "Scripts movidos de src\iip\scripts : $movidosSrcScripts"
Write-Host "Arquivos suspeitos de lixo movidos para $lixoDir : $movidosLixo"
Write-Host ""
Write-Host "Nada foi apagado. Nada foi commitado."
Write-Host "Proximo passo: revise '$lixoDir' e apague manualmente o que confirmar que nao serve."
Write-Host "Depois, rode 'git status' para ver o quanto a raiz ficou mais limpa."
