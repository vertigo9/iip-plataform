from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from iip import __version__
from iip.analysis import (
    AgroAnalyzer,
    AssetData,
    EquityAnalyzer,
    ETFAnalyzer,
    FIIAnalyzer,
    FixedIncomeAnalyzer,
    InfraAnalyzer,
)
from iip.config import get_settings
from iip.core import Runtime
from iip.export import ReportExporter
from iip.health import (
    ModuleCountHealthCheck,
    PythonVersionHealthCheck,
    ReplicationStatusHealthCheck,
    SynchronizationHealthCheck,
    VersionCompatibilityHealthCheck,
)
from iip.metrics import MetricsEngine
from iip.registry import ModuleRegistry
from iip.replication import ReplicationEngine
from iip.versioning import VersionManager

console = Console()


def _unwrap_secret(value: Any) -> str | None:
    """Unwrap a SecretStr setting to its raw string, or pass through
    None/plain strings unchanged. Centralizes this so credential
    handling stays consistent everywhere it's read from IIPSettings."""
    if value is None:
        return None
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value()
    return value

ANALYZERS: dict[str, type] = {
    "equity": EquityAnalyzer,
    "fii": FIIAnalyzer,
    "infra": InfraAnalyzer,
    "agro": AgroAnalyzer,
    "etf": ETFAnalyzer,
    "fixed_income": FixedIncomeAnalyzer,
}


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """IIP Platform CLI — Institutional Investment Platform."""
    if ctx.invoked_subcommand is None:
        click.echo(cli.get_help(ctx))


@cli.command()
def version():
    """Show version."""
    console.print(f"[bold green]IIP Platform[/] [cyan]{__version__}[/]")


@cli.command("knowledge-status")
def knowledge_status() -> None:
    """Show the configured Obsidian knowledge vault and its record counts."""
    settings = get_settings()
    vault = settings.obsidian_vault
    counts = {
        "decisions": len(list((vault / "03_Decisions").glob("*.md")))
        if vault.exists()
        else 0,
        "evidence": len(list((vault / "04_Evidence").glob("*.md")))
        if vault.exists()
        else 0,
        "snapshots": len(list((vault / "02_Portfolio" / "Snapshots").glob("*.md")))
        if vault.exists()
        else 0,
        "exposures": len(list((vault / "06_Exposures").glob("*.md")))
        if vault.exists()
        else 0,
    }
    console.print(
        json.dumps({"vault": str(vault), "exists": vault.exists(), **counts}, indent=2),
        soft_wrap=True,
    )


@cli.command()
@click.option(
    "--sources",
    is_flag=True,
    default=False,
    help="Também testa conectividade real com as fontes de dado externas "
    "(CVM, BACEN, IBGE, bolsai, brapi.dev, BrasilAPI, MZIQ). Mais lento "
    "que o health check padrão, que só verifica coisas locais.",
)
def health(sources: bool) -> None:
    """Run all health checks."""
    Runtime.start()
    ctx = Runtime.get_context()

    if ctx is None:
        console.print("[red]Runtime not initialized[/]")
        raise SystemExit(1)

    ctx.health_engine.register(PythonVersionHealthCheck())
    ctx.health_engine.register(ModuleCountHealthCheck())
    ctx.health_engine.register(VersionCompatibilityHealthCheck())
    ctx.health_engine.register(ReplicationStatusHealthCheck())
    ctx.health_engine.register(SynchronizationHealthCheck())

    if sources:
        from iip.health import default_data_source_checks

        console.print("[dim]Testando conectividade com fontes de dado externas...[/]")
        for check in default_data_source_checks():
            ctx.health_engine.register(check)

    hs = ctx.health_engine.run_all()

    table = Table(title="Health Checks")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Message")

    for c in hs.checks:
        s = "[green]OK[/]" if c.healthy else "[red]FAIL[/]"
        table.add_row(c.name, s, c.message)

    console.print(table)
    overall = "[bold green]HEALTHY[/]" if hs.healthy else "[bold red]UNHEALTHY[/]"
    console.print(f"\nOverall: {overall}")

    if not hs.healthy:
        raise SystemExit(1)


@cli.command()
def status():
    """Show platform status."""
    Runtime.start()
    ctx = Runtime.get_context()

    if ctx is None:
        console.print("[red]Runtime not initialized[/]")
        raise SystemExit(1)

    info = {
        "app": ctx.settings.app_name,
        "version": ctx.settings.version,
        "env": ctx.settings.environment.value,
        "started": ctx.started,
        "platform_version": VersionManager.current().__str__(),
    }
    console.print(json.dumps(info, indent=2), soft_wrap=True)


@cli.command()
def modules():
    """List registered modules."""
    status = ModuleRegistry.status()

    table = Table(title="Module Registry")
    table.add_column("Module", style="cyan")
    table.add_column("Version", style="yellow")
    table.add_column("Enabled", style="green")
    table.add_column("Loaded", style="blue")

    for name, mod in status.get("modules", {}).items():
        enabled = "[green]Yes[/]" if mod.get("enabled") else "[red]No[/]"
        loaded = "[green]Yes[/]" if mod.get("loaded") else "[red]No[/]"
        table.add_row(name, mod.get("version", "?"), enabled, loaded)

    console.print(table)
    console.print(
        f"\nTotal: {status.get('total', 0)}, Enabled: {status.get('enabled', 0)}, Loaded: {status.get('loaded', 0)}"
    )


@cli.command()
def metrics():
    """Show platform metrics."""
    Runtime.start()
    settings = get_settings()
    summary = MetricsEngine.summary(settings)
    console.print(json.dumps(summary, indent=2), soft_wrap=True)


@cli.command()
def replication():
    """Show replication status."""
    status = ReplicationEngine.status()
    console.print(json.dumps(status, indent=2), soft_wrap=True)


@cli.command()
def config():
    """Show active configuration."""
    Runtime.start()
    ctx = Runtime.get_context()
    if ctx:
        info = {
            "environment": ctx.settings.environment.value,
            "debug": ctx.settings.debug,
            "app_name": ctx.settings.app_name,
            "log_level": ctx.settings.log_level,
            "base_dir": str(ctx.settings.base_dir),
            "credentials": {
                "bolsai_api_key": "configurada"
                if ctx.settings.bolsai_api_key
                else "não configurada",
                "brapi_token": "configurada"
                if ctx.settings.brapi_token
                else "não configurada",
            },
        }
        console.print(json.dumps(info, indent=2, ensure_ascii=False), soft_wrap=True)


class _FieldRecorder(dict):
    """Dict that records every key/default pair fetched via .get().

    Used to auto-generate data-file templates straight from the analyzer
    code, so the list of expected fields can never drift out of sync with
    what the analyzer actually reads.
    """

    def get(self, key: str, default: Any = None) -> Any:
        self[key] = default
        return default


def _template_financials(analyzer_cls: type) -> dict[str, Any]:
    recorder = _FieldRecorder()
    probe = AssetData(
        symbol="TEMPLATE", sector="TEMPLATE", industry="TEMPLATE", financials=recorder
    )
    try:
        analyzer_cls().analyze(probe)
    except Exception:  # noqa: BLE001, S110 — probe é best-effort por design (ver comentário abaixo)
        # Some fields may only be touched deep down a branch; a failed
        # probe run still leaves us with whatever was recorded so far.
        pass
    return dict(sorted(recorder.items()))


@cli.command("analyze-template")
@click.option(
    "--type",
    "asset_type",
    type=click.Choice(sorted(ANALYZERS)),
    required=True,
    help="Asset type to generate a template for.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Where to save the template JSON. Prints to stdout if omitted.",
)
def analyze_template(asset_type: str, output: str | None) -> None:
    """Generate a data-file template (JSON) for `iip analyze --data-file`."""
    analyzer_cls = ANALYZERS[asset_type]
    template = {
        "symbol": "TICKER11",
        "sector": "REPLACE_WITH_SECTOR",
        "industry": "REPLACE_WITH_INDUSTRY",
        "market_cap": None,
        "price": None,
        "financials": _template_financials(analyzer_cls),
    }
    payload = json.dumps(template, indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(payload, encoding="utf-8")
        console.print(f"[green]Template written to {output}[/]")
    else:
        console.print(payload)
        console.print(
            f"\n[dim]Tip: save this to a file and edit the values, then run:\n  iip analyze <SYMBOL> --type {asset_type} --data-file <file>.json[/]"
        )


@cli.command("fetch-template")
@click.argument("symbol")
@click.option(
    "--type",
    "asset_type",
    type=click.Choice(["fii", "etf", "equity", "fixed_income", "agro"]),
    default="fii",
    help="Asset type. FII, ETF, equity, fixed_income and agro are wired to "
    "real data fetching (agro busca no dataset CVM FIAGRO) — infra ainda "
    "precisa de `iip analyze-template` + preenchimento manual.",
)
@click.option(
    "--cnpj",
    default=None,
    help="CNPJ do fundo (formato livre, com ou sem pontuação). Obrigatório "
    "para --type fii/etf/fixed_income/agro; não usado para --type equity (busca por ticker).",
)
@click.option(
    "--ano", type=int, default=None, help="Ano de referência CVM (padrão: ano atual)."
)
@click.option(
    "--mes",
    type=int,
    default=None,
    help="Mês de referência CVM, 1-12 (para --type etf/fixed_income/agro; padrão: mês atual).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Onde salvar o template preenchido. Imprime no console se omitido.",
)
def fetch_template(
    symbol: str,
    asset_type: str,
    cnpj: str | None,
    ano: int | None,
    mes: int | None,
    output: str | None,
) -> None:
    """Busca dados reais (CVM + bolsai/brapi) e pré-preenche um template
    de análise — em vez de partir de `analyze-template` em branco.

    FII: preenche dividend_yield, patrimônio, prêmio/desconto sobre VP,
    preço, market cap (via CVM FII + bolsai).

    ETF: preenche patrimônio e market cap estimado a partir de um único
    mês de Informe Diário (via CVM Fundos ICVM 555 + brapi) — mais
    conservador que FII, já que campos como crescimento de AUM em 3
    anos ou captação YTD não podem ser honestamente derivados de um
    mês só.

    Equity: preenche só price, market_cap e dividend_yield (via
    bolsai/brapi) — bem mais limitado que FII/ETF, porque bolsai só
    fornece razões já calculadas (ROE, ROIC, margens), não os valores
    absolutos (receita, lucro líquido, patrimônio) que o EquityAnalyzer
    precisa pra calcular essas razões por conta própria.

    fixed_income: preenche só patrimônio (via CVM Informe Diário) —
    nunca busca preço de mercado, mesmo se configurado, porque o
    ticker de referência desses fundos (ex: AXIA3) pode não corresponder
    a um ticker de mercado real do próprio fundo.

    agro: preenche só dividend_yield_pct (via CVM FIAGRO — dataset
    dedicado, diferente do de FII/Informe Diário) — AgroAnalyzer não
    tem campo de patrimônio, e fundos FIAGRO como CRAA11 também não
    têm ticker negociado na B3.

    Em todos os casos, os campos de julgamento qualitativo (ocupação,
    governança, tracking error, taxa de administração, liquidez,
    poder de precificação etc.) continuam com os valores-padrão do
    analisador — sem isso, editar à mão.
    """
    import datetime as _dt

    from iip.cli.fetch_template import (
        fetch_equity_template_live,
        fetch_etf_template_live,
        fetch_fiagro_template_live,
        fetch_fii_template_live,
        fetch_fixed_income_template_live,
    )

    if asset_type in ("fii", "etf", "fixed_income", "agro") and not cnpj:
        console.print(f"[bold red]--cnpj é obrigatório para --type {asset_type}[/]")
        raise SystemExit(1)

    hoje = _dt.date.today()  # noqa: DTZ011 — data de calendário (ano/mês de competência CVM), não timestamp; timezone não se aplica
    ano_efetivo = ano or hoje.year

    if asset_type == "fii":
        console.print(f"[dim]Buscando dados CVM FII para {ano_efetivo}...[/]")
        bolsai_key = _unwrap_secret(get_settings().bolsai_api_key)
        if not bolsai_key:
            console.print(
                "[dim]IIP_BOLSAI_API_KEY não definida — pulando busca de preço "
                "(reit_premium_discount e market_cap ficam vazios).[/]"
            )
        try:
            template, resultado = fetch_fii_template_live(
                symbol, cnpj, ano_efetivo, bolsai_key
            )
        except Exception as exc:
            console.print(f"[bold red]Erro ao buscar dados da CVM:[/] {exc}")
            raise SystemExit(1) from exc

    elif asset_type == "etf":
        mes_efetivo = mes or hoje.month
        console.print(
            f"[dim]Buscando dados CVM Informe Diário para {ano_efetivo}-{mes_efetivo:02d}...[/]"
        )
        brapi_token = _unwrap_secret(get_settings().brapi_token)
        if not brapi_token:
            console.print(
                "[dim]IIP_BRAPI_TOKEN não definida — pulando busca de preço "
                "(market_cap fica vazio).[/]"
            )
        try:
            template, resultado = fetch_etf_template_live(
                symbol, cnpj, ano_efetivo, mes_efetivo, brapi_token
            )
        except Exception as exc:
            console.print(f"[bold red]Erro ao buscar Informe Diário da CVM:[/] {exc}")
            raise SystemExit(1) from exc

    elif asset_type == "fixed_income":
        mes_efetivo = mes or hoje.month
        console.print(
            f"[dim]Buscando dados CVM Informe Diário para {ano_efetivo}-{mes_efetivo:02d}...[/]"
        )
        try:
            template, resultado = fetch_fixed_income_template_live(
                symbol, cnpj, ano_efetivo, mes_efetivo
            )
        except Exception as exc:
            console.print(f"[bold red]Erro ao buscar Informe Diário da CVM:[/] {exc}")
            raise SystemExit(1) from exc

    elif asset_type == "agro":
        mes_efetivo = mes or hoje.month
        console.print(
            f"[dim]Buscando dados CVM FIAGRO para {ano_efetivo}-{mes_efetivo:02d}...[/]"
        )
        brapi_token = _unwrap_secret(get_settings().brapi_token)
        if not brapi_token:
            console.print(
                "[dim]IIP_BRAPI_TOKEN não definida — pulando busca de preço.[/]"
            )
        try:
            template, resultado = fetch_fiagro_template_live(
                symbol, cnpj, ano_efetivo, mes_efetivo, brapi_token
            )
        except Exception as exc:
            console.print(f"[bold red]Erro ao buscar dados CVM FIAGRO:[/] {exc}")
            raise SystemExit(1) from exc

    else:  # equity
        bolsai_key = _unwrap_secret(get_settings().bolsai_api_key)
        brapi_token = _unwrap_secret(get_settings().brapi_token)
        console.print(f"[dim]Buscando dados de {symbol.upper()} via bolsai/brapi...[/]")
        template, resultado = fetch_equity_template_live(symbol, bolsai_key, brapi_token)

    console.print(f"\n[bold]Campos preenchidos com dado real:[/] {', '.join(resultado.fetched_fields) or '(nenhum)'}")
    for warning in resultado.warnings:
        console.print(f"[yellow]Aviso: {warning}[/]")

    payload = json.dumps(template, indent=2, ensure_ascii=False)
    if output:
        Path(output).write_text(payload, encoding="utf-8")
        console.print(f"\n[green]Template salvo em {output}[/]")
        console.print(
            f"[dim]Edite os campos de julgamento (ocupação, governança, etc.) e rode:\n"
            f"  iip analyze {symbol.upper()} --type {asset_type} --data-file {output}[/]"
        )
    else:
        console.print(payload)


@cli.command("refresh-portfolio")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="portfolio_snapshots",
    help="Diretório onde salvar os snapshots (um subdiretório por data).",
)
@click.option(
    "--ano", type=int, default=None, help="Ano de referência CVM (padrão: ano atual)."
)
@click.option(
    "--mes",
    type=int,
    default=None,
    help="Mês de referência CVM para ETFs, 1-12 (padrão: mês atual).",
)
def refresh_portfolio_command(
    output_dir: str, ano: int | None, mes: int | None
) -> None:
    """Atualiza de uma vez só todas as posições da carteira real
    (``iip.portfolio.registry.PORTFOLIO_ASSETS``) que já têm CNPJ
    verificado ou são ação — hoje FII, ETF, fixed_income, FIAGRO e
    ação têm fetch automático; CDB bancário não (não tem fonte de
    dado pública/gratuita — não é uma limitação nossa, é como o
    mercado de CDB funciona).

    Só busca dado, não analisa nem persiste — para isso, ver
    ``iip analyze-portfolio``.

    Pensado para ser chamado por um agendador (Agendador de Tarefas do
    Windows, cron) — não é um serviço contínuo, é um comando que roda
    uma vez, busca tudo, e termina. Ver `agendar_atualizacao_windows.ps1`
    para registrar isso como tarefa agendada diária.
    """
    from iip.portfolio.refresh import refresh_portfolio

    bolsai_key = _unwrap_secret(get_settings().bolsai_api_key)
    brapi_token = _unwrap_secret(get_settings().brapi_token)

    if not bolsai_key:
        console.print(
            "[dim]IIP_BOLSAI_API_KEY não definida — posições FII vão sem preço.[/]"
        )
    if not brapi_token:
        console.print(
            "[dim]IIP_BRAPI_TOKEN não definida — posições ETF vão sem preço.[/]"
        )

    console.print(f"[dim]Atualizando carteira em {output_dir}...[/]\n")

    resultado = refresh_portfolio(
        Path(output_dir),
        bolsai_api_key=bolsai_key,
        brapi_token=brapi_token,
        ano=ano,
        mes=mes,
    )

    table = Table(title=f"Atualização da carteira — {resultado.run_date}")
    table.add_column("Ticker")
    table.add_column("Status")
    table.add_column("Detalhe")

    for outcome in resultado.outcomes:
        cor = {"ok": "green", "erro": "red", "pulado": "yellow"}[outcome.status]
        table.add_row(
            outcome.ticker, f"[{cor}]{outcome.status}[/]", outcome.detail[:80]
        )

    console.print(table)
    console.print(
        f"\n[bold]Resumo:[/] {len(resultado.succeeded)} ok, "
        f"{len(resultado.failed)} erro, {len(resultado.skipped)} pulado"
    )

    if resultado.failed:
        raise SystemExit(1)


@cli.command("analyze-portfolio")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--ano", type=int, default=None, help="Ano de referência CVM (padrão: ano atual)."
)
@click.option(
    "--mes",
    type=int,
    default=None,
    help="Mês de referência CVM, 1-12 (padrão: mês atual).",
)
def analyze_portfolio_command(
    vault: str | None, ano: int | None, mes: int | None
) -> None:
    """Busca dado real, roda o analisador certo, e persiste a análise
    de TODA a carteira de uma vez — uma posição por vez, uma falha não
    trava as outras.

    Só analisa posições com ``sector``/``industry`` reais disponíveis
    no registro (``PortfolioAsset.sector``/``.industry`` para ações,
    ``.structure``/``.segment`` para fundos) — nunca fabrica um
    placeholder pra "funcionar" com todas. O que não tiver isso
    preenchido aparece como "pulado" com o motivo exato, nunca como
    "ok" com dado inventado.

    Não gera nem persiste nenhuma ``Decision`` — isso continua
    exigindo evidência real e julgamento por ativo, ver
    ``iip analyze --decide`` um de cada vez.
    """
    from iip.portfolio.batch_analyze import analyze_portfolio

    bolsai_key = _unwrap_secret(get_settings().bolsai_api_key)
    brapi_token = _unwrap_secret(get_settings().brapi_token)
    vault_path = vault or str(get_settings().obsidian_vault)

    console.print(f"[dim]Analisando carteira em {vault_path}...[/]\n")

    resultado = analyze_portfolio(
        bolsai_api_key=bolsai_key,
        brapi_token=brapi_token,
        vault_path=vault_path,
        ano=ano,
        mes=mes,
    )

    table = Table(title="Análise da carteira")
    table.add_column("Ticker")
    table.add_column("Status")
    table.add_column("Detalhe")

    for outcome in resultado.outcomes:
        cor = {"ok": "green", "erro": "red", "pulado": "yellow"}[outcome.status]
        table.add_row(
            outcome.ticker, f"[{cor}]{outcome.status}[/]", outcome.detail[:80]
        )

    console.print(table)
    console.print(
        f"\n[bold]Resumo:[/] {len(resultado.succeeded)} ok, "
        f"{len(resultado.failed)} erro, {len(resultado.skipped)} pulado"
    )

    if resultado.failed:
        raise SystemExit(1)


@cli.command()
@click.argument("symbol")
@click.option(
    "--type",
    "asset_type",
    type=click.Choice(sorted(ANALYZERS)),
    required=True,
    help="Asset type: equity, fii, infra, or agro.",
)
@click.option(
    "--data-file",
    "-f",
    type=click.Path(exists=True),
    required=True,
    help="JSON file with sector/industry/financials (see `iip analyze-template`).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "html", "csv"]),
    default="table",
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Write the report to this path instead of printing to the console.",
)
@click.option(
    "--persist",
    is_flag=True,
    default=False,
    help="Salva o resultado na nota canônica do vault Obsidian "
    "(IIP_OBSIDIAN_VAULT), na seção 'IIP:analysis' de "
    "'{symbol} - Score e Ranking.md'.",
)
@click.option(
    "--decide",
    "gerar_decisao",
    is_flag=True,
    default=False,
    help="Gera uma Decision de verdade (decision_engine.decide()) a partir "
    "desta análise, via iip.decision.analysis_bridge — fecha o ciclo "
    "analisar->decidir que antes não existia em código nenhum. Requer "
    "pelo menos um --evidence-id.",
)
@click.option(
    "--thesis-signal",
    type=click.Choice(["Reforço", "Neutro", "Ponto de atenção", "Mudança de tese"]),
    default="Neutro",
    help="Sinal de tese pra decisão (só usado com --decide).",
)
@click.option(
    "--evidence-id",
    "evidence_ids",
    multiple=True,
    help="ID de evidência real já existente no vault (repita a opção pra mais "
    "de uma). Obrigatório com --decide — nunca inventado automaticamente. "
    "Se --persist também for usado e a evidência não existir de verdade no "
    "vault, a persistência da decisão falha honestamente (contrato de "
    "auditoria), em vez de fabricar evidência pra passar.",
)
@click.option(
    "--valuation-score",
    type=float,
    default=None,
    help="Nota de valuation de 0 a 10, se você tiver uma de verdade (preço-alvo, "
    "margem de segurança calculada à mão). Sem isso, fica neutro (5.0) com "
    "aviso — nenhum dos 5 analisadores calcula valuation de verdade hoje.",
)
def analyze(
    symbol: str,
    asset_type: str,
    data_file: str,
    output_format: str,
    output: str | None,
    persist: bool,
    gerar_decisao: bool,
    thesis_signal: str,
    evidence_ids: tuple[str, ...],
    valuation_score: float | None,
) -> None:
    """Run an IIP framework analysis on SYMBOL using data from --data-file."""
    try:
        raw = json.loads(Path(data_file).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        console.print(f"[bold red]Invalid JSON in {data_file}:[/] {exc}")
        raise SystemExit(1) from exc

    missing = [f for f in ("sector", "industry") if not raw.get(f)]
    if missing:
        console.print(
            f"[bold red]Missing required field(s) in {data_file}:[/] {', '.join(missing)}"
        )
        raise SystemExit(1)

    data = AssetData(
        symbol=symbol.upper(),
        sector=raw["sector"],
        industry=raw["industry"],
        market_cap=raw.get("market_cap"),
        price=raw.get("price"),
        financials=raw.get("financials", {}),
    )

    report = ANALYZERS[asset_type]().analyze(data)

    if persist:
        from iip.knowledge.bridge import KnowledgeBridge

        vault_path = str(get_settings().obsidian_vault)
        try:
            resultado_persist = KnowledgeBridge(vault_path).sync_analysis_projection(
                report, symbol, asset_type
            )
            console.print(
                f"[dim]Vault: {resultado_persist.status.value} — {resultado_persist.path}[/]"
            )
        except Exception as exc:  # noqa: BLE001 — falha ao gravar no vault não deve impedir a análise em si de ser exibida
            console.print(f"[yellow]Aviso: não consegui salvar no vault: {exc}[/]")

    if gerar_decisao:
        if not evidence_ids:
            console.print(
                "[bold red]--decide precisa de pelo menos um --evidence-id[/] "
                "(nunca inventado automaticamente — veja --help)."
            )
            raise SystemExit(1)

        import datetime as _dt

        from iip.decision.analysis_bridge import analysis_to_intelligence_input
        from iip.decision.decision_engine import decide as _decide
        from iip.decision.models import EvidenceRef

        intelligence_input, bridge_warnings = analysis_to_intelligence_input(
            report,
            thesis_signal=thesis_signal,
            evidence=tuple(EvidenceRef(eid) for eid in evidence_ids),
            valuation_score=valuation_score,
        )
        for w in bridge_warnings:
            console.print(f"[yellow]Aviso: {w}[/]")

        decision = _decide(intelligence_input)
        verdict_color = {
            "COMPRAR": "bold green",
            "MANTER": "green",
            "AGUARDAR": "yellow",
            "REDUZIR": "red",
            "VENDER": "bold red",
        }.get(decision.verdict.value, "white")
        console.print(
            f"\n[bold]Decision:[/] [{verdict_color}]{decision.verdict.value}[/] "
            f"(score={decision.score:.2f}/10, confidence={decision.confidence:.2f})"
        )
        for reason in decision.reasons:
            console.print(f"[dim]  {reason}[/]")

        if persist:
            from iip.decision.knowledge_bridge import to_knowledge_decision
            from iip.knowledge.bridge import KnowledgeBridge as _KnowledgeBridge

            knowledge_decision = to_knowledge_decision(
                decision,
                decision_id=f"DEC-{symbol.upper()}-{_dt.date.today().isoformat()}",  # noqa: DTZ011 — data de calendário (data da decisão), não timestamp
                date=_dt.date.today(),  # noqa: DTZ011 — mesma razão
            )
            try:
                _KnowledgeBridge(str(get_settings().obsidian_vault)).persist_decision(
                    knowledge_decision
                )
                console.print(
                    f"[dim]Decision persistida: {knowledge_decision.decision_id}[/]"
                )
            except ValueError as exc:
                console.print(
                    f"[yellow]Aviso: não consegui persistir a decisão: {exc}[/]\n"
                    "[dim]A evidência citada precisa já existir no vault antes da "
                    "decisão — não é fabricada automaticamente aqui.[/]"
                )

    if output_format == "table":
        table = Table(title=f"{report.asset_symbol} — {asset_type.upper()} Analysis")
        table.add_column("Pillar", style="cyan")
        table.add_column("Score", justify="right", style="yellow")
        table.add_column("Weight", justify="right")
        table.add_column("Weighted", justify="right", style="magenta")

        for p in report.pillar_scores:
            table.add_row(
                p.pillar.value,
                f"{p.score:.1f}",
                f"{p.weight:.0%}",
                f"{p.weighted_score():.1f}",
            )

        console.print(table)
        rec_color = {
            "Strong Buy": "bold green",
            "Buy": "green",
            "Hold": "yellow",
            "Reduce": "red",
            "Sell": "bold red",
        }.get(report.recommendation, "white")
        console.print(f"\nOverall score: [bold]{report.overall_score:.1f}[/]/100")
        console.print(
            f"Recommendation: [{rec_color}]{report.recommendation}[/] (risk: {report.risk_level})"
        )
        if report.notes:
            console.print(f"[dim]{report.notes}[/]")
        if output:
            Path(output).write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            console.print(f"\n[green]Also saved as JSON to {output}[/]")
        return

    exporters = {
        "json": ReportExporter.to_json,
        "html": ReportExporter.to_html,
        "csv": ReportExporter.to_csv,
    }
    content = exporters[output_format](report, output)
    if output:
        console.print(f"[green]Report saved to {output}[/]")
    else:
        console.print(content)


@cli.command("persist-evidence")
@click.argument("evidence_id")
@click.option("--ticker", required=True, help="Ticker do ativo que essa evidência sustenta.")
@click.option(
    "--source-type",
    required=True,
    help="De onde vem essa evidência (ex: cvm_fii, mziq, relatorio_gerencial, manual).",
)
@click.option(
    "--date",
    "data_referencia",
    default=None,
    help="Data da evidência, formato YYYY-MM-DD (padrão: hoje).",
)
@click.option("--source-url", default=None, help="URL da fonte, se houver.")
@click.option("--title", default=None, help="Título/descrição curta do documento.")
@click.option(
    "--fact",
    "relevant_facts",
    multiple=True,
    help="Um fato relevante que essa evidência sustenta (repita a opção pra mais de um).",
)
def persist_evidence(
    evidence_id: str,
    ticker: str,
    source_type: str,
    data_referencia: str | None,
    source_url: str | None,
    title: str | None,
    relevant_facts: tuple[str, ...],
) -> None:
    """Persiste uma evidência real no vault Obsidian (IIP_OBSIDIAN_VAULT).

    É append-only — persistir o mesmo EVIDENCE_ID de novo falha
    (evidência já registrada não pode ser reescrita, só uma nova pode
    ser criada com outro id). Essa evidência precisa existir aqui
    ANTES de `iip analyze --decide --persist` conseguir persistir uma
    decisão que a cite — é o mesmo contrato de auditoria que
    `DecisionAuditor` já impunha, agora com um jeito de satisfazê-lo
    sem cair pro Python direto.

    Não fabrica fato nenhum sozinho — ``--fact`` é o que você
    realmente observou (do relatório, do documento, da fonte citada
    em ``--source-type``), não um resumo gerado automaticamente.
    """
    import datetime as _dt

    from iip.knowledge.bridge import KnowledgeBridge
    from iip.knowledge.models import Evidence

    if data_referencia:
        try:
            data_evidencia = _dt.date.fromisoformat(data_referencia)
        except ValueError as exc:
            console.print(
                f"[bold red]--date precisa ser YYYY-MM-DD, recebi: {data_referencia}[/]"
            )
            raise SystemExit(1) from exc
    else:
        data_evidencia = _dt.date.today()  # noqa: DTZ011 — data de calendário (data da evidência), não timestamp

    evidence = Evidence(
        evidence_id=evidence_id,
        ticker=ticker.upper(),
        date=data_evidencia,
        source_type=source_type,
        source_url=source_url,
        title=title,
        relevant_facts=tuple(relevant_facts),
    )

    vault_path = str(get_settings().obsidian_vault)
    try:
        path = KnowledgeBridge(vault_path).persist_evidence(evidence)
    except FileExistsError as exc:
        console.print(f"[bold red]Evidência já existe:[/] {exc}")
        console.print(
            "[dim]Append-only — use um evidence_id diferente pra registrar uma "
            "nova evidência, não reescreva a existente.[/]"
        )
        raise SystemExit(1) from exc

    console.print(f"[green]Evidência persistida:[/] {path}")
    console.print(
        f"[dim]Agora `iip analyze {ticker.upper()} ... --decide --evidence-id "
        f'"{evidence_id}" --persist` consegue citar essa evidência de verdade.[/]'
    )


if __name__ == "__main__":
    cli()
