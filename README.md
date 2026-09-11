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

### Atualizar a carteira inteira de uma vez

```powershell
python -m iip.cli.main refresh-portfolio
```

Busca automaticamente todas as posições de
`iip.portfolio.registry.PORTFOLIO_ASSETS` que já têm CNPJ verificado, uma
por uma (uma posição com erro não trava as outras), e salva um snapshot
JSON por ticker em `portfolio_snapshots/{data}/`.

Hoje só **BTLG11** e **LFTB11** têm CNPJ preenchido nesse registro — os
demais precisam do CNPJ adicionado manualmente em
`src/iip/portfolio/registry.py` antes de entrarem na atualização automática
(nunca adivinhe um CNPJ — um valor errado busca dado de outro fundo
silenciosamente).

### Automatizar isso todo dia (Windows)

```powershell
# uma vez só, como Administrador — ajuste o caminho do projeto e o horário
# dentro do arquivo antes de rodar
.\agendar_atualizacao_windows.ps1
```

Isso registra `executar_atualizacao_diaria.ps1` no Agendador de Tarefas do
Windows. Testar sem esperar o horário:

```powershell
Start-ScheduledTask -TaskName "IIP_AtualizacaoCarteiraDiaria"
Get-Content (Get-ChildItem logs_atualizacao\*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

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

- **Só FII, ETF e fundos regulados pela CVM (fixed_income) têm busca
  automática de dado.** Ação/Infra/Agro precisam
  de `analyze-template` + preenchimento manual completo.
- **~22 dos 27 campos de cada analisador são julgamento qualitativo**
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
- **`refresh-portfolio` cobre todas as posições com CNPJ verificado** no
  registro (hoje: todos os 22 fundos/ETF da carteira real, além de
  posições em ações — que não usam CNPJ pra automação).
- **O monitoramento de fontes (`health --sources`) só checa se o servidor
  responde**, não se o formato do dado mudou (ex: CVM trocar o nome de uma
  coluna não seria pego por esse check — só os testes automatizados
  pegariam isso, ao rodar).
- **`iip fetch-fii-template`** é uma implementação paralela mais antiga de
  `fetch-template --type fii` (mesma ideia, sourcing de preço diferente) —
  mantida por compatibilidade com testes existentes, não é a recomendada
  para uso novo.

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
