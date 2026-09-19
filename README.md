# IIP — Institutional Investment Platform

Plataforma de análise de investimentos que busca dados reais (CVM, BACEN,
IBGE, B3, Receita Federal, RI de empresas) e gera uma análise fundamentalista
estruturada por classe de ativo (ação, FII, ETF, FI-Infra, FI-Agro), com
histórico gravado num vault Obsidian.

> **Estado atual**: `0.1.0-alpha`. Cobertura de dados e o pipeline
> busca→análise→persistência funcionam de ponta a ponta para **FII** e
> **ETF** (parcialmente). Ação/Infra/Agro têm analisador pronto, mas ainda
> sem busca automática de dado — ver [Limitações conhecidas](#limitações-conhecidas).

## Requisitos

- Python 3.12 ou mais recente
- Windows (os scripts de agendamento são específicos do Agendador de Tarefas
  do Windows; o resto do projeto é multiplataforma)
- Contas gratuitas opcionais em [bolsai](https://usebolsai.com) e
  [brapi.dev](https://brapi.dev) — necessárias só para buscar **preço**
  automaticamente (o resto dos dados não precisa de credencial nenhuma)

## Instalação

```powershell
git clone <url-do-repositorio>
cd iip_obsidian_integration_v1
pip install -e ".[dev]"
```

Isso instala o pacote em modo editável, mais as dependências de
desenvolvimento (pytest, ruff, black, mypy).

## Configuração

Copia `.env.example` para `.env` e ajusta o que precisar:

```powershell
Copy-Item .env.example .env
notepad .env
```

Variáveis principais:

| Variável | Obrigatória? | Para quê |
|---|---|---|
| `IIP_OBSIDIAN_VAULT` | Não (padrão: `./vault`) | Onde o vault Obsidian fica — é onde `analyze --persist` grava as notas |
| `IIP_BOLSAI_API_KEY` | Não | Preço de ações/FIIs via bolsai (`fetch-template --type fii`) |
| `IIP_BRAPI_TOKEN` | Não | Preço de ações/FIIs/BDRs via brapi.dev (`fetch-template --type etf`, cobertura de BDR) |
| `IIP_ENVIRONMENT` | Não (padrão: `development`) | `development`/`testing`/`production` |

Sem as duas credenciais de preço, tudo continua funcionando — só os campos
que dependem de preço de mercado (`price`, `market_cap`,
`reit_premium_discount`) ficam vazios, com aviso explícito no terminal.

Confere o que está configurado (nunca mostra o valor, só se está presente):

```powershell
python -m iip.cli.main config
```

## Uso — do dado real ao relatório

O fluxo pensado para uso diário, usando um FII como exemplo:

```powershell
# 1. Busca dado real da CVM (+ preço via bolsai, se configurado) e monta um template
python -m iip.cli.main fetch-template BTLG11 --cnpj "11.839.593/0001-09" -o btlg11.json

# 2. Edita btlg11.json: preenche sector/industry e os campos de julgamento
#    (ocupação, governança, histórico do gestor etc.) que nenhuma API fornece
notepad btlg11.json

# 3. Gera o relatório e grava no vault Obsidian
python -m iip.cli.main analyze BTLG11 --type fii --data-file btlg11.json --persist
```

O passo 3 sem `--persist` só mostra o relatório na tela, sem gravar nada.

Para ETF, o fluxo é o mesmo, trocando `--type fii` por `--type etf` no passo 3
e usando `--type etf` no passo 1 (que aí busca via CVM Informe Diário, não
CVM FII).

### Do relatório à decisão de verdade

`iip analyze` sozinho só produz um `AnalysisReport` — nunca gerava uma
`Decision` de verdade (achado real de uma auditoria: `analysis` e
`decision` nunca foram conectados em código nenhum, apesar de terem
formatos compatíveis). Isso agora existe:

```powershell
# 4. Registra uma evidência real (obrigatório citar pra poder decidir)
python -m iip.cli.main persist-evidence "EV-BTLG11-2026-08" --ticker BTLG11 --source-type cvm_fii --fact "Dividend yield 0.94% no mês, ocupação 85%"

# 5. Gera e persiste uma decisão de verdade, citando essa evidência
python -m iip.cli.main analyze BTLG11 --type fii --data-file btlg11.json --decide --evidence-id "EV-BTLG11-2026-08" --thesis-signal "Reforço" --persist
```

`--decide` nunca fabrica evidência — se o `--evidence-id` citado não
existir de verdade no vault, a persistência da decisão falha
honestamente (mesmo contrato de auditoria que já existia via
`DecisionAuditor`), em vez de inventar uma pra "passar". `persist-evidence`
é append-only — o mesmo `EVIDENCE_ID` não pode ser reescrito, só criado
uma vez.

`--valuation-score` (0-10) é opcional — nenhum dos 5 analisadores calcula
valor intrínseco, preço-alvo ou margem de segurança de verdade (também
achado de auditoria: sem DCF/Graham/Bazin no projeto), então sem essa nota
explícita a decisão usa um valor neutro (5.0) com aviso, nunca emprestado
de outro pilar disfarçado de valuation.

### Atualizar a carteira inteira de uma vez

```powershell
python -m iip.cli.main refresh-portfolio
```

Busca automaticamente todas as posições de
`iip.portfolio.registry.PORTFOLIO_ASSETS` que já têm CNPJ verificado (hoje:
todos os 22 fundos/ETF da carteira real) mais todas as ações (buscadas por
ticker, não precisam de CNPJ) — uma por uma, uma posição com erro não trava
as outras — e salva um snapshot JSON por ticker em
`portfolio_snapshots/{data}/`.

### Analisar e persistir a carteira inteira de uma vez

```powershell
python -m iip.cli.main analyze-portfolio
```

Busca dado real, roda o analisador certo, e grava no vault — uma posição
por vez, sem `Decision` nenhuma (isso continua exigindo evidência real e
julgamento por ativo, um de cada vez, via `iip analyze --decide`).

Só analisa posições com `sector`/`industry` **reais** disponíveis no
registro — nunca fabrica um placeholder pra "funcionar" com todas.
Preencha `PortfolioAsset.sector`/`.industry` (ações) ou
`.structure`/`.segment` (fundos, geralmente já preenchido) antes de rodar;
o que não tiver isso aparece como "pulado" com o motivo exato, nunca como
"ok" com dado inventado.

### Automatizar isso todo dia (Windows)

```powershell
# uma vez só, como Administrador — ajuste o caminho do projeto e o horário
# dentro do arquivo antes de rodar
.\agendar_atualizacao_windows.ps1
```

Isso registra `executar_atualizacao_diaria.ps1` no Agendador de Tarefas do
Windows. Cada execução faz, em ordem: `health --sources`, `refresh-portfolio`
e `value-portfolio --report` (veja a próxima seção), e sai com código 1 se
qualquer um dos três falhar. Testar sem esperar o horário:

```powershell
Start-ScheduledTask -TaskName "IIP_AtualizacaoCarteiraDiaria"
Get-Content (Get-ChildItem logs_atualizacao\*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

### Valuation da carteira

```powershell
python -m iip.cli.main value-portfolio --report
```

Avalia cada posição por **todos** os métodos que cabem nela, lado a lado,
com valor justo/teto e margem de segurança contra o preço atual:

| Classe | Métodos |
|---|---|
| Ação | Graham; Bazin (taxa exigida = yield real da NTN-B longa, nunca 6% fixos) — Bazin lidera em setores movidos a dividendo (elétricas, bancos, seguros) |
| FII | NAV (P/VP); Yield (renda 12m capitalizada sobre a NTN-B real + prêmio de risco de 3 p.p. — só FII de tijolo) |

`--report` grava `vault/02_Portfolio/Valuation.md` (todas as posições, motivo de
cada método sem valor) e o Dashboard mostra os destaques lendo essa nota. Se
nenhuma posição for avaliada (ex.: cota do bolsai esgotada), a nota anterior é
mantida. `--persist` grava no vault o primeiro método que produziu valor.

Posições sem método implementado aparecem como "puladas" com o motivo —
hoje: fundos `fixed_income` (o fetch nunca busca preço de propósito: alguns,
como AXIA3, são rótulos de fundos que não negociam), CRAA11 (fora do dataset
FIAGRO da CVM, sem NAV) e LFTB11 (ETF: o CNPJ consta no cadastro da CVM como
FIIM, mas o Informe Diário que usamos não traz a cota dele, então não há NAV — verificado em 19/09/2026). Valor justo
não é recomendação de compra.

### Coletar documentos de RI e gestoras

Cada comando lista e baixa documentos reais e grava evidência no vault
(`--sem-evidencia` só lista/baixa; `--limite N` serve para prévia):

| Comando | Cobre |
|---|---|
| `collect-equity-documents --ticker T` | 10 ações na plataforma MZIQ (ABCB4, BBSE3, CXSE3, SAUD3, ALOS3, VBBR3, KLBN4, FESA4, LEVE3, PASS3) |
| `collect-solutions-ir-documents --ticker T` | BTCI11 e CSUD3 (plataforma Solutions IR) |
| `collect-static-documents --ticker T` | TRXF11, VGIP11, CPTI11, MANA11, RBVA11, HGBS11, KNRI11 e as ações ISAE4 e CMIG4 (`--anos-historico`) |
| `collect-cpfl-documents` | CPFE3 (RI legado da CPFL) |
| `collect-patria-documents`, `collect-btg-documents`, `collect-sparta-history` | Fundos Pátria, BTG (BTLG11) e Sparta |

As 14 ações da carteira têm coletor. Áudio e vídeo são pulados por padrão
(`--incluir-midia` para baixar).

## Fontes de dados

| Fonte | Cobre | Credencial | Módulo |
|---|---|---|---|
| CVM (Informe Mensal FII) | Dividend yield, patrimônio, balanço de FIIs | Não | `iip.sources.cvm_fii` |
| CVM (Informe Mensal FIAGRO) | Idem, para FIAGRO | Não | `iip.sources.cvm_fiagro` |
| CVM (Informe Diário / Perfil Mensal) | NAV diário e perfil de risco de fundos ICVM 555 (inclui ETF) | Não | `iip.sources.cvm_renda_fixa` |
| bolsai | Cotação e fundamentos de ações/FIIs | `IIP_BOLSAI_API_KEY` | `iip.sources.b3_bolsai` |
| brapi.dev | Cotação de ações/FIIs/**BDR** | `IIP_BRAPI_TOKEN` | `iip.sources.b3_brapi` |
| BrasilAPI | Dados cadastrais de CNPJ | Não | `iip.sources.receita_federal` |
| BACEN (SGS) | SELIC, CDI, IPCA | Não | `iip.sources.bacen` |
| IBGE (Agregados) | Qualquer tabela do SIDRA (genérico) | Não | `iip.sources.ibge` |
| MZIQ | Documentos de RI (relatórios, apresentações) de empresas na plataforma MZIQ | Não | `iip.sources.mziq` |

Cada módulo tem sua própria docstring explicando limitações e achados
específicos (ex: por que dois provedores de B3 coexistem, por que o FNET foi
descartado a favor da CVM). Vale ler antes de mexer.

## Estrutura do projeto

```
src/iip/
  analysis/       # Analisadores por classe de ativo (Equity, FII, ETF, Infra, Agro)
  cli/            # Comandos (fetch-template, analyze, refresh-portfolio, ...)
  sources/        # Um módulo por fonte de dado externa (target+parser, sem I/O)
  *_harvester.py  # Transporte HTTP de cada fonte (separado do parsing)
  knowledge/      # Vault Obsidian — modelos, projeção, sincronização idempotente
  portfolio/      # Registro real da carteira (PORTFOLIO_ASSETS) + refresh em lote
  providers/      # Sistema de plugins (registro + fábrica com injeção de credencial)
```

O restante de `src/iip/` (dezenas de outros pacotes — `decision/`,
`orchestration/`, `enterprise/`, `production/` etc.) é infraestrutura mais
antiga do projeto, com cobertura de teste alta mas, em vários casos, sem
nenhum uso real fora dos próprios testes — isso está documentado
módulo a módulo nas docstrings onde foi encontrado durante esta sessão de
trabalho (buscar por "audit finding" no código).

## Limitações conhecidas

- **FII, ETF, fundos regulados pela CVM (fixed_income), FIAGRO (agro) e
  ação têm busca automática de dado e analisador dedicado.** Infra ainda
  precisa de `analyze-template` + preenchimento manual completo.
- **FIAGRO (ex: CRAA11) busca `dividend_yield_pct` via CVM e `price` via
  brapi.dev** (o ZIP da CVM é mensal: se o mês corrente ainda não saiu, o
  fetch recua até 2 meses e avisa qual usou) — correção real: a suposição inicial de que esses fundos não
  negociam na B3 estava errada (confirmado com cotação real de várias
  fontes públicas). O que continua sem explicação: o CNPJ do CRAA11
  (confirmado correto em 6 fontes independentes) genuinamente não aparece
  no Informe Mensal FIAGRO da CVM para 2026 — não é atraso de publicação
  (o arquivo de agosto/2026 baixa normalmente), é uma lacuna específica
  desse fundo nesse dataset que não foi possível explicar. `AgroAnalyzer`
  não tem campo de patrimônio, então isso não afeta a análise além do
  `dividend_yield_pct`.
- **A automação de ação é bem mais limitada que a de FII/ETF** — só
  `price`, `market_cap` e `dividend_yield` (3 de 29 campos). O bolsai só
  fornece razões já calculadas (ROE, ROIC, margens), não os valores
  absolutos (receita, lucro líquido, patrimônio, capital investido) que
  o `EquityAnalyzer` precisa pra calcular essas razões por conta própria
  — um valor e a razão dele não são intercambiáveis, então esses campos
  nunca são adivinhados a partir da razão.
- **~22-26 dos campos de cada analisador são julgamento qualitativo**
  (ocupação, governança, tracking error, poder de precificação etc.) — não
  existe fonte gratuita estruturada para isso; vem de leitura de relatório
  gerencial em PDF.
- **BDR não tem fundamentos**, só cotação (via brapi.dev) — o emissor
  reporta no exterior, não à CVM.
- **CDB (renda fixa bancária) não tem fonte de dado pública/gratuita** —
  não é uma lacuna nossa, é como o mercado funciona: CDB é dívida bilateral
  banco↔investidor, não um valor mobiliário com cotação pública (nem o
  CETIP NET, plataforma de negociação entre instituições financeiras, tem
  API pública). `refresh-portfolio` não tenta buscar esses ativos.
- **`refresh-portfolio` cobre todas as 23 posições de fundo/ETF com CNPJ
  verificado** (incluindo FI-Infra e FI-Agro agora, cada um no dataset
  CVM certo) **mais todas as posições em ação** (buscadas por ticker via
  bolsai/brapi, não precisam de CNPJ) — 37 posições ativas ao todo.
- **O monitoramento de fontes (`health --sources`) só checa se o servidor
  responde**, não se o formato do dado mudou (ex: CVM trocar o nome de uma
  coluna não seria pego por esse check — só os testes automatizados
  pegariam isso, ao rodar).

### Monitoramento

```powershell
python -m iip.cli.main health --sources
```

Sem `--sources`, `health` só verifica coisas locais (config, versão do
Python, etc.) — rápido, mas não diz nada sobre as fontes de dado externas.
Com `--sources`, testa conectividade real (CVM, BACEN, IBGE, bolsai,
brapi.dev, BrasilAPI, MZIQ) via HEAD request com timeout curto — não baixa
dado nenhum, só confirma que o servidor está no ar.

`executar_atualizacao_diaria.ps1` já roda esse check automaticamente antes
de atualizar a carteira, e mostra uma **notificação real do Windows**
(balão no canto da tela) se alguma fonte estiver inacessível ou se alguma
posição falhar ao atualizar — não precisa mais abrir o log manualmente
para descobrir que algo quebrou.

## Testes

```powershell
python -m pytest tests\ --no-cov          # rápido, sem relatório de cobertura
python -m pytest tests\ --cov=iip --cov-report=term-missing   # com cobertura
```

Suíte com mais de 1100 testes, cobertura geral acima de 95%. Os harvesters
usam um `opener`/callable injetável em vez de mockar bibliotecas HTTP
diretamente — ao adicionar uma fonte nova, siga esse mesmo padrão (veja
qualquer `*_harvester.py` existente como modelo).

## Integração contínua

`.github/workflows/ci.yml` roda em todo push e pull request: instalação
limpa (`pip install -e ".[dev]"`), `ruff check` (bloqueante), checagem de
compilação (bloqueante), e a suíte completa de testes (bloqueante). A
checagem de formatação do `black` também roda, mas **não bloqueia** —
70 arquivos ainda não seguem o padrão dele (nunca foi aplicado no
projeto); vira tarefa deliberada de formatação em lote quando fizer
sentido, do mesmo jeito que o Ruff foi tratado (por regra, com testes a
cada lote, não tudo de uma vez). `mypy` também não está no CI ainda —
mesmo um arquivo escrito com cuidado nesta sessão acusou 4 erros de
tipagem dinâmica normal, então adicionar isso como bloqueante hoje
seria ruído, não sinal.

## Descobrir → reutilizar → estender → criar

Esse projeto já passou por várias rodadas de descoberta de código duplicado
(a mesma ideia implementada duas ou três vezes em módulos diferentes, sem
que uma soubesse da outra). Antes de escrever algo novo:

1. Procure por nomes parecidos em `src/iip/` — `grep -rl` pelo conceito, não
   só pelo nome exato.
2. Se achar algo parecido, leia a docstring do módulo antes de decidir se é
   duplicata de verdade ou um conceito genuinamente diferente (nem tudo que
   parece igual é igual — veja `iip.orchestration.portfolio_cycle` vs.
   `iip.system.pipeline` como exemplo real de "parecido mas não é").
3. Se for duplicata, não apague o mais antigo sem checar se algum teste
   trava o comportamento dele — documente a relação entre os dois em vez de
   forçar a fusão.
