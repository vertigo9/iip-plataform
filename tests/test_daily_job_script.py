import re
from pathlib import Path

SCRIPT = Path("executar_atualizacao_diaria.ps1")

# System.Windows.Forms.ToolTipIcon tem só estes membros; "Information" NÃO existe nele (existe
# em System.Drawing.SystemIcons), e o nome errado vira $null e faz o ShowBalloonTip falhar
TOOLTIP_ICON_MEMBERS = {"None", "Info", "Warning", "Error"}
SYSTEM_ICON_MEMBERS = {"Information", "Warning", "Error"}


def _icons_used() -> set[str]:
    text = SCRIPT.read_text(encoding="utf-8")
    return set(
        re.findall(r'Notificar-Windows\s.*?"(\w+)"\s*$', text, flags=re.MULTILINE)
    )


def test_the_notification_icon_names_the_script_uses_are_known():
    icons = _icons_used()

    assert {"Information", "Warning", "Error"} <= icons
    assert icons <= SYSTEM_ICON_MEMBERS


def test_the_balloon_uses_a_tooltip_icon_name_that_exists_for_every_icon():
    text = SCRIPT.read_text(encoding="utf-8")

    # o nome do ícone do balão passa por um mapeamento; nunca o nome cru de SystemIcons
    assert "[System.Windows.Forms.ToolTipIcon]::$TipoBalao" in text
    assert "[System.Windows.Forms.ToolTipIcon]::$Icone" not in text
    assert 'if ($Icone -eq "Information") { $TipoBalao = "Info" }' in text
    mapped = {"Info" if icon == "Information" else icon for icon in _icons_used()}
    assert mapped <= TOOLTIP_ICON_MEMBERS


def test_every_notification_call_in_the_script_passes_an_icon():
    text = SCRIPT.read_text(encoding="utf-8")
    calls = re.findall(r"^\s*Notificar-Windows\s.*$", text, flags=re.MULTILINE)

    assert calls
    # o ícone é um literal ("Warning") ou a variável $Icone (que só recebe Information/Warning)
    assert all(re.search(r'("\w+"|\$Icone)\s*$', call) for call in calls), calls


# --- the layers note is part of the daily job ---------------------------------------------


def _script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_the_job_runs_the_layers_note_after_the_exposure_and_before_the_dashboard():
    text = _script()

    exposure = text.index("portfolio-exposure --report")
    layers = text.index("portfolio-layers --report")
    dashboard = text.index("cli.main dashboard")
    assert exposure < layers < dashboard
    assert "--- Camadas do patrimonio ---" in text


def test_the_layers_exit_code_is_logged_notified_and_part_of_the_job_result():
    text = _script()

    assert "$LayersExitCode = $LASTEXITCODE" in text
    assert "camadas: $LayersExitCode" in text  # a linha final do log
    assert "if ($LayersExitCode -ne 0)" in text  # a notificação de falha
    assert "$LayersExitCode -eq 0" in text  # o código de saída do job


def test_the_layers_step_only_reads_it_never_touches_the_policy():
    text = _script()
    step = text[
        text.index("--- Camadas do patrimonio ---") : text.index(
            "$LayersExitCode = $LASTEXITCODE"
        )
    ]

    assert "--init" not in step and "target-policy" not in step
    assert "SO LEITURA" in text and "nao define alvo nem limite" in text
    assert "target-policy" not in text  # a política continua fora do job
