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
