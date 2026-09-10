from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re
import shutil
import sys

ROOT = Path.cwd()
TARGET = ROOT / 'src' / 'iip' / 'harvest' / 'patria.py'
MARKER = '# PATCH V4 - Patria legacy years + MZIQ API + progress'


def die(message: str) -> None:
    print(f'ERRO: {message}')
    raise SystemExit(1)


def replace_function(text: str, name: str, new_code: str) -> str:
    pattern = re.compile(
        rf'(?ms)^def {re.escape(name)}\(.*?(?=^def |\Z)'
    )
    match = pattern.search(text)
    if not match:
        die(f'não encontrei a função {name} no patria.py')
    return text[:match.start()] + new_code.rstrip() + '\n\n' + text[match.end():]


def main() -> None:
    if not TARGET.exists():
        die(f'arquivo alvo não encontrado: {TARGET}')
    text = TARGET.read_text(encoding='utf-8')
    if MARKER in text:
        print('Patch V4 já aplicado; nada a fazer.')
        return

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = TARGET.with_name(f'patria.backup_v4_{stamp}.py')
    shutil.copy2(TARGET, backup)
    print(f'Backup criado: {backup.name}')

    # 1) Aceita os endpoints MZIQ antigos, que não têm .pdf no href.
    old_filter = '''if not any(ext in low for ext in (".pdf", ".xlsx", ".xls", ".csv", ".xml", ".doc", ".docx", ".zip")):\n            continue'''
    new_filter = '''if ("api.mziq.com/mzfilemanager/" not in low and\n                not any(ext in low for ext in (".pdf", ".xlsx", ".xls", ".csv", ".xml", ".doc", ".docx", ".zip"))):\n            continue'''
    if old_filter not in text:
        die('não encontrei o filtro de extensões esperado em _collect_links; não alterei o arquivo.')
    text = text.replace(old_filter, new_filter, 1)

    # 2) Se o ano antigo não estiver em <select>, procura controles visíveis
    #    que exibam exatamente o ano e clica neles. Isso cobre a versão antiga
    #    da Central de Documentos sem quebrar os anos 2025/2026.
    new_find = r'''def _find_year_select(page):
    selects = page.locator("select")
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            labels = [x.strip() for x in sel.locator("option").all_text_contents()]
            if any(re.fullmatch(r"(?:19|20)\d{2}", x) for x in labels):
                return sel
        except Exception:
            continue
    return None


def _visible_year_controls(page, year: int):
    wanted = str(year)
    candidates = page.get_by_text(wanted, exact=True)
    found = []
    for i in range(min(candidates.count(), 40)):
        try:
            item = candidates.nth(i)
            if item.is_visible(timeout=500):
                found.append(item)
        except Exception:
            continue
    return found
'''
    text = replace_function(text, '_find_year_select', new_find)

    new_select = r'''def _select_year(page, year: int) -> bool:
    wanted = str(year)

    # Caminho normal: <select><option>2019</option>...</select>
    sel = _find_year_select(page)
    if sel is not None:
        try:
            options = sel.locator("option").all()
            for option in options:
                text = option.inner_text().strip()
                value = option.get_attribute("value")
                if text == wanted or value == wanted:
                    sel.select_option(value=value if value is not None else text)
                    page.wait_for_timeout(1200)
                    return True
        except Exception:
            pass

    # Caminho legado: o controle pode ser um botão/div customizado.
    # Primeiro tenta abrir o seletor de ano e então clicar no ano exato.
    selectors = [
        '[aria-label*="ano" i]',
        '[aria-labelledby*="ano" i]',
        '[class*="year" i]',
        '[class*="ano" i]',
        'button',
        '[role="button"]',
    ]
    for css in selectors:
        try:
            controls = page.locator(css)
            for i in range(min(controls.count(), 80)):
                control = controls.nth(i)
                try:
                    if not control.is_visible(timeout=300):
                        continue
                    txt = (control.inner_text() or '').strip()
                    if wanted in txt and len(txt) <= 80:
                        control.click(timeout=2000)
                        page.wait_for_timeout(300)
                        for item in _visible_year_controls(page, year):
                            try:
                                item.click(timeout=2000)
                                page.wait_for_timeout(1200)
                                return True
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception:
            continue

    # Última tentativa: clicar diretamente no texto do ano.
    for item in _visible_year_controls(page, year):
        try:
            item.click(timeout=2000)
            page.wait_for_timeout(1200)
            return True
        except Exception:
            continue
    return False
'''
    text = replace_function(text, '_select_year', new_select)

    # 3) Adiciona um diagnóstico explícito quando um ano não for encontrado,
    #    sem fechar o browser imediatamente em modo --headed.
    old_print = 'print(f"Ano {year}: não disponível no site; pulando.", flush=True)'
    new_print = '''print(f"Ano {year}: não disponível no site; pulando.", flush=True)\n                if headed:\n                    print("  [DIAGNÓSTICO] O navegador permanece aberto por 3s para inspeção.", flush=True)\n                    page.wait_for_timeout(3000)'''
    if old_print in text:
        text = text.replace(old_print, new_print, 1)

    # 4) Progress pulse: se a versão atual já possui _ProgressPulse, ela será
    #    preservada. Se não possuir, não injetamos código estrutural arriscado.
    #    O loop de downloads já imprime [n/total] e flush=True.

    text = MARKER + '\n' + text
    try:
        compile(text, str(TARGET), 'exec')
    except SyntaxError as exc:
        shutil.copy2(backup, TARGET)
        die(f'o patch produziria SyntaxError na linha {exc.lineno}; restaurei o backup {backup.name}')

    TARGET.write_text(text, encoding='utf-8')
    print('Patch V4 aplicado com sucesso.')
    print(f'Arquivo atualizado: {TARGET}')
    print('Teste recomendado:')
    print(r'python ".\scripts\patria_harvester.py" --ticker PCI11 --years 2019 --headed')
    print(r'python ".\scripts\patria_harvester.py" --ticker PCI11 --years 2023 --headed')
    print(r'python ".\scripts\patria_harvester.py" --ticker PCI11 --years 2019-2026 --headed')


if __name__ == '__main__':
    main()
