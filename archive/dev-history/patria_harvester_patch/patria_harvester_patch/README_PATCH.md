# Patria Harvester — patch 2

Este patch corrige o ponto que travou a execução anterior no PCIP11.

## Correções principais

1. **Não usa mais `page.locator(f\'a[href="{doc.url}"]\')` com URL absoluta.** A página pode manter `href` relativo, enquanto o manifesto guarda a URL absoluta.
2. **Download direto pelo `BrowserContext.request` como caminho principal**, usando os cookies da sessão do Chromium.
3. **Fallback de download pelo navegador**, procurando o `<a>` pela URL resolvida e usando timeout curto de 8 s.
4. **Ano inexistente não derruba a execução.** Se o site não oferecer um ano solicitado, ele é pulado. Isso é importante para `2019-2026` se o seletor continuar terminando em 2025.
5. **Mais feedback no console** para sabermos exatamente onde está o processamento.

## Substituição

A partir da raiz `iip_obsidian_integration_v1`, substitua estes dois arquivos:

```powershell
Copy-Item -Force .\patria_harvester_patch\src\iip\harvest\patria.py .\src\iip\harvest\patria.py
Copy-Item -Force .\patria_harvester_patch\scripts\patria_harvester.py .\scripts\patria_harvester.py
```

## Teste recomendado

Primeiro: `python .\scripts\patria_harvester.py --ticker PCIP11 --years 2025 --headed`

Depois: `python .\scripts\patria_harvester.py --ticker PCIP11 --years 2019-2026 --headed`


## v3 — progresso visual
Durante cada requisição/download, o console mostra um spinner e o tempo decorrido, evitando a aparência de travamento. Também informa o contador [atual/total] por documento.
