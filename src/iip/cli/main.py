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
    PluginsHealthCheck,
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


def _load_plugins_or_warn() -> None:
    """Load the provider plugins named in IIP_PLUGINS (env or .env). Silent when none
    are configured or all load; a plugin that fails is reported on stderr (so
    ``--format json`` output on stdout stays clean) and the command still runs."""
    from iip.providers.registry import load_plugins

    for failure in load_plugins().failures:
        click.echo(
            f"aviso: plugin {failure.module!r} não carregou ({failure.reason})",
            err=True,
        )


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """IIP Platform CLI — Institutional Investment Platform."""
    if ctx.invoked_subcommand is None:
        click.echo(cli.get_help(ctx))
        return
    _load_plugins_or_warn()


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
        "decisions": (
            len(list((vault / "03_Decisions").glob("*.md"))) if vault.exists() else 0
        ),
        "evidence": (
            len(list((vault / "04_Evidence").glob("*.md"))) if vault.exists() else 0
        ),
        "snapshots": (
            len(list((vault / "02_Portfolio" / "Snapshots").glob("*.md")))
            if vault.exists()
            else 0
        ),
        "exposures": (
            len(list((vault / "06_Exposures").glob("*.md"))) if vault.exists() else 0
        ),
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

    ctx.health_engine.register(PluginsHealthCheck())
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
                "bolsai_api_key": (
                    "configurada" if ctx.settings.bolsai_api_key else "não configurada"
                ),
                "brapi_token": (
                    "configurada" if ctx.settings.brapi_token else "não configurada"
                ),
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
    # probe é best-effort por design (ver comentário abaixo)
    except Exception:  # noqa: BLE001, S110
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
    "--preco-mercado",
    "market_price",
    is_flag=True,
    default=False,
    help="Só para --type fixed_income: busca o preço de mercado (brapi). Use APENAS "
    "quando o símbolo é o ticker B3 do próprio fundo (FI-Infra listado: CDII11, "
    "JURO11, CPTI11) — em outros (ex.: AXIA3, um FMP-FGTS sem ticker) o símbolo "
    "pode ser de outro ativo e o preço seria de outra empresa.",
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
    market_price: bool,
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

    Equity: preenche price/market_cap/dividend_yield (via bolsai/brapi)
    e, desde 18/09/2026, também equity/net_income/revenue/ebit/
    invested_capital/crescimento 3y a partir da DFP real da CVM (ver
    ``iip.sources.cvm_dfp``) — ebit e invested_capital ficam vazios
    para bancos/instituições financeiras (sem linha equivalente na
    DFP), e debt_to_equity continua no valor-padrão de propósito (ver
    docstring de ``fetch_equity_template_live``).

    fixed_income: preenche patrimônio e cota (nav_per_share) via CVM
    Informe Diário — só busca preço de mercado com --preco-mercado,
    porque o ticker de referência de alguns desses fundos (ex: AXIA3)
    pode não corresponder a um ticker de mercado real do próprio fundo.

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

    if asset_type in ("fii", "etf", "fixed_income", "agro", "equity") and not cnpj:
        console.print(f"[bold red]--cnpj é obrigatório para --type {asset_type}[/]")
        raise SystemExit(1)

    # data de calendário (ano/mês de competência CVM), não timestamp; timezone não se aplica
    hoje = _dt.date.today()  # noqa: DTZ011
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
        brapi_token = None
        if market_price:
            brapi_token = _unwrap_secret(get_settings().brapi_token)
            if not brapi_token:
                console.print(
                    "[dim]IIP_BRAPI_TOKEN não definida — pulando busca de preço.[/]"
                )
        try:
            template, resultado = fetch_fixed_income_template_live(
                symbol, cnpj, ano_efetivo, mes_efetivo, brapi_token
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
                symbol,
                cnpj,
                ano_efetivo,
                mes_efetivo,
                brapi_token,
                bolsai_api_key=_unwrap_secret(get_settings().bolsai_api_key),
            )
        except Exception as exc:
            console.print(f"[bold red]Erro ao buscar dados CVM FIAGRO:[/] {exc}")
            raise SystemExit(1) from exc

    else:  # equity
        # DFP de um ano fiscal só fica disponível meses depois do fim
        # desse ano -- ano_efetivo (padrão hoje.year) apontaria pro ano
        # corrente, ainda sem DFP nenhuma; o ano fiscal mais recente com
        # dado real é sempre o anterior, salvo --ano explícito.
        ano_dfp_efetivo = ano or (hoje.year - 1)
        bolsai_key = _unwrap_secret(get_settings().bolsai_api_key)
        brapi_token = _unwrap_secret(get_settings().brapi_token)
        console.print(
            f"[dim]Buscando dados de {symbol.upper()} via bolsai/brapi + "
            f"DFP CVM {ano_dfp_efetivo}...[/]"
        )
        try:
            template, resultado = fetch_equity_template_live(
                symbol, cnpj, ano_dfp_efetivo, bolsai_key, brapi_token
            )
        except Exception as exc:
            console.print(f"[bold red]Erro ao buscar DFP da CVM:[/] {exc}")
            raise SystemExit(1) from exc

    console.print(
        f"\n[bold]Campos preenchidos com dado real:[/] {', '.join(resultado.fetched_fields) or '(nenhum)'}"
    )
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


def _load_valuation_exceptions(vault_path: str):
    """As exceções metodológicas de valuation do vault (vazias se não há arquivo). Um arquivo
    inválido para o comando com o motivo: nunca cai em silêncio para "sem exceções"."""
    from iip.portfolio_data.valuation_exceptions import exceptions_for

    try:
        exceptions = exceptions_for(vault_path)
    except ValueError as exc:
        console.print(
            f"[bold red]Exceções metodológicas de valuation inválidas:[/] {exc}"
        )
        raise SystemExit(1) from exc
    if exceptions.items:
        console.print(
            f"[dim]Exceções metodológicas de valuation: {len(exceptions.items)} "
            f"(hash {exceptions.content_hash}).[/]"
        )
    return exceptions


# ``analyze --type`` value -> valuation catalog class, where they differ. fixed_income
# maps to fi_infra (NAV only): a fund WITHOUT a market price (AXIA3) still gets no
# score, because the catalog reports the missing price instead of inventing a margin.
_AUTO_VALUATION_CLASS = {"agro": "fiagro", "fixed_income": "fi_infra"}


def _auto_valuation_score(
    symbol: str, asset_type: str, raw: dict, price: float | None, financials: dict
) -> float | None:
    """Valuation score for ``analyze --decide --auto-valuation`` (see
    ``iip.decision.catalog_valuation``). ``None`` keeps the neutral default."""
    from iip.decision.catalog_valuation import catalog_valuation_for_decision
    from iip.portfolio.batch_value import _default_fetch_rate

    exceptions = _load_valuation_exceptions(str(get_settings().obsidian_vault))
    rate = None
    try:
        found = _default_fetch_rate()
        rate = found.real_yield if found else None
        if found:
            console.print(
                f"[dim]NTN-B longa (venc. {found.maturity:%d/%m/%Y}, ref. "
                f"{found.reference_date:%d/%m/%Y}): IPCA + {found.real_yield:.2%}[/]"
            )
    # a taxa é consulta de mercado opcional; sem ela o Bazin fica sem valor, a decisão segue
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]Aviso: não consegui buscar a taxa da NTN-B: {exc}[/]")

    result = catalog_valuation_for_decision(
        ticker=symbol,
        asset_class=_AUTO_VALUATION_CLASS.get(asset_type, asset_type),
        sector=raw["sector"],
        industry=raw["industry"],
        price=price,
        financials=financials,
        ntnb_real_yield=rate,
        exceptions=exceptions,
    )
    if result.score is None:
        console.print(
            f"[yellow]Aviso: valuation automático sem valor — {result.explanation}[/]"
        )
        return None
    console.print(f"[dim]Valuation automático: {result.explanation}[/]")
    return result.score


def _format_snapshot(snapshot) -> str:
    if snapshot.margin_of_safety is None:
        return f"{snapshot.fair_value:.2f}"
    return f"{snapshot.fair_value:.2f} ({snapshot.margin_of_safety:+.0%})"


def _lead_and_others(attempts) -> tuple[str, str, str]:
    """(lead method, its value and margin, the other methods that also gave a
    value) -- the lead is the first in the sector's order."""
    snapshots = [a.snapshot for a in attempts if a.snapshot is not None]
    if not snapshots:
        return "—", "—", "—"
    lead, *others = snapshots
    return (
        lead.method.value,
        _format_snapshot(lead),
        "; ".join(f"{s.method.value} {_format_snapshot(s)}" for s in others) or "—",
    )


@cli.command("portfolio-exposure")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--file",
    "snapshot_file",
    type=click.Path(),
    default=None,
    help="Snapshot das posições (padrão: <vault>/02_Portfolio/Current.md).",
)
@click.option(
    "--limite-grupo",
    type=float,
    default=0.20,
    show_default=True,
    help="Alerta de atenção para um grupo (classe, gestora, setor...) acima desta fração.",
)
@click.option(
    "--limite-posicao",
    type=float,
    default=0.10,
    show_default=True,
    help="Alerta de atenção para uma posição acima desta fração.",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 02_Portfolio/Exposicao.md (sobrescrita a cada execução).",
)
def portfolio_exposure_command(
    vault: str | None,
    snapshot_file: str | None,
    limite_grupo: float,
    limite_posicao: float,
    report: bool,
) -> None:
    """Exposição e concentração da carteira (classe, gestora, setor/segmento, risco).

    Lê o snapshot das posições do vault; não usa rede. Os limites são de ATENÇÃO, não
    política de alocação. Diz a idade do snapshot e o que ficou fora dele."""
    import datetime as _dt

    from iip.portfolio.exposure import (
        SEM_CLASSIFICACAO,
        STALE_AFTER_DAYS,
        build_exposure,
    )
    from iip.portfolio.vault_snapshot import parse_current_snapshot

    vault_path = vault or str(get_settings().obsidian_vault)
    path = (
        Path(snapshot_file)
        if snapshot_file
        else Path(vault_path) / "02_Portfolio" / "Current.md"
    )
    if not path.is_file():
        console.print(f"[bold red]Snapshot das posições não encontrado: {path}[/]")
        raise SystemExit(1)

    try:
        result = build_exposure(
            parse_current_snapshot(path),
            # data de calendário (idade do snapshot), não timestamp
            today=_dt.date.today(),  # noqa: DTZ011
            group_limit=limite_grupo,
            position_limit=limite_posicao,
        )
    except ValueError as exc:
        console.print(f"[bold red]Não consegui ler o snapshot:[/] {exc}")
        raise SystemExit(1) from exc

    if result.as_of is not None:
        aviso = (
            " [yellow](defasado: os pesos já andaram com os preços)[/]"
            if result.stale
            else ""
        )
        console.print(
            f"[dim]Snapshot de {result.as_of:%d/%m/%Y} ({result.age_days} dias; mais de "
            f"{STALE_AFTER_DAYS} é defasado){aviso}[/]"
        )
    console.print(
        f"[bold]{result.position_count} posições, R$ {result.total_value:,.2f}[/]"
    )
    if result.missing_from_snapshot:
        console.print(
            "[yellow]Fora do snapshot (estão no registro): "
            f"{', '.join(result.missing_from_snapshot)} — a carteira está incompleta.[/]"
        )
    for closed_ticker, closed_on in result.closed_in_snapshot:
        console.print(
            f"[yellow]{closed_ticker} voltou ao snapshot, mas está encerrado no registro "
            f"(desde {closed_on}): o job não o atualiza. Para reativar, apague `closed_on` "
            "dele em portfolio/registry.py.[/]"
        )

    for dimension in result.dimensions:
        table = Table(
            title=f"{dimension.name} (classificado: {dimension.classified_weight:.0%})"
        )
        table.add_column("Grupo")
        table.add_column("Peso", justify="right")
        table.add_column("Pos.", justify="right")
        for row in dimension.rows[:10]:
            table.add_row(row.label, f"{row.weight:.1%}", str(row.count))
        if len(dimension.rows) > 10:
            table.add_row(f"... e mais {len(dimension.rows) - 10}", "", "")
        console.print(table)
        if dimension.low_coverage:
            console.print(
                f"[yellow]Cobertura baixa em {dimension.name}: o registro não classifica "
                f"({SEM_CLASSIFICACAO}) a maior parte.[/]"
            )

    if result.flags:
        console.print("\n[bold]Alertas de concentração[/] (limites de atenção)")
        for flag in result.flags:
            console.print(
                f"  {flag.kind} · {flag.dimension}: [bold]{flag.label}[/] "
                f"{flag.weight:.1%} (limite {flag.limit:.0%})"
            )
    else:
        console.print("\nNenhum grupo ou posição acima dos limites de atenção.")

    if report:
        from iip.obsidian.exposure_report import write_exposure_report

        console.print(
            f"[dim]Relatório de exposição: {write_exposure_report(vault_path, result)}[/]"
        )


@cli.command("collect-fii-history")
@click.option(
    "--ticker",
    "tickers",
    multiple=True,
    help="Atualiza só estes FIIs (repita a opção). Padrão: todos os FIIs da carteira.",
)
@click.option(
    "--desde-ano",
    type=int,
    default=2021,
    show_default=True,
    help="Primeiro ano da série (a coleta refaz a série inteira desde este ano).",
)
@click.option(
    "--min-age-days",
    type=int,
    default=None,
    help="Só atualiza a série cuja última atualização tem mais de N dias (ou nunca foi "
    "atualizada). É como o agendador roda toda noite e baixa só uma vez por semana.",
)
@click.option(
    "--alert-file",
    type=click.Path(),
    default=None,
    help="Grava uma linha por série que MUDOU para pior (ausente, defasada, zerada, "
    "irregular); sem mudança, apaga o arquivo da rodada anterior.",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 02_Portfolio/Series.md (estado de cada série).",
)
@click.option(
    "--vault",
    type=click.Path(),
    default=None,
    help="Caminho do vault Obsidian (padrão: IIP_OBSIDIAN_VAULT).",
)
@click.option(
    "--sem-evidencia",
    is_flag=True,
    default=False,
    help="Não persiste evidência Atlas no vault, só a série em 02_Portfolio/Historical.",
)
def collect_fii_history_command(
    tickers: tuple[str, ...],
    desde_ano: int,
    min_age_days: int | None,
    alert_file: str | None,
    report: bool,
    vault: str | None,
    sem_evidencia: bool,
) -> None:
    """Atualiza a série mensal da CVM (Informe Mensal de FII) de cada FII da carteira.

    Sem isto a série guardada em 02_Portfolio/Historical não muda mais, e a renda projetada
    e o painel de distribuições ficam velhos. Um zip por ano cobre todos os fundos (baixado
    uma vez). A série guardada só é substituída se a coleta não trouxer menos meses. Depois
    da coleta grava o estado de cada série (situação, última competência, data da
    atualização) e avisa o que mudou para pior."""
    import datetime as _dt

    from iip.knowledge.bridge import KnowledgeBridge
    from iip.portfolio.fii_history_refresh import fii_positions, refresh_fii_histories
    from iip.portfolio.historical_series import HistoricalSeriesStore
    from iip.portfolio.registry import PORTFOLIO_ASSETS
    from iip.portfolio.series_state import (
        SeriesState,
        compute_state,
        load_state_file,
        save_state_file,
        series_alerts,
        write_alert_file,
    )

    positions = fii_positions(PORTFOLIO_ASSETS)
    if tickers:
        wanted = {t.strip().upper() for t in tickers}
        positions = tuple(p for p in positions if p.ticker in wanted)
        unknown = wanted - {p.ticker for p in positions}
        if unknown:
            console.print(
                f"[bold red]Não são FIIs da carteira: {', '.join(sorted(unknown))}[/]"
            )
            raise SystemExit(1)

    # data de calendário (último ano a buscar e idade das séries), não timestamp
    hoje = _dt.date.today()  # noqa: DTZ011
    if desde_ano > hoje.year:
        console.print("[bold red]--desde-ano não pode ser depois do ano corrente.[/]")
        raise SystemExit(1)

    vault_path = vault or str(get_settings().obsidian_vault)
    previous = load_state_file(vault_path)

    due = positions
    if min_age_days is not None:

        def _age(ticker: str) -> int | None:
            stamp = (previous.get(ticker) or {}).get("refreshed_at")
            try:
                return (hoje - _dt.date.fromisoformat(stamp)).days if stamp else None
            except ValueError:
                return None

        due = tuple(
            p
            for p in positions
            if _age(p.ticker) is None or _age(p.ticker) > min_age_days
        )
        if not due:
            console.print(
                f"[dim]Séries em dia: todas atualizadas há {min_age_days} dias ou menos; "
                "nada a baixar.[/]"
            )
            if report:
                # sem baixar, a nota ainda reflete o estado atual das séries guardadas
                from iip.obsidian.series_report import write_series_report

                current = tuple(
                    compute_state(
                        p.ticker,
                        HistoricalSeriesStore(vault_path),
                        today=hoje,
                        refreshed_at=(previous.get(p.ticker) or {}).get("refreshed_at"),
                    )
                    for p in positions
                )
                console.print(
                    "[dim]Estado das séries: "
                    f"{write_series_report(vault_path, current, (), today_iso=hoje.isoformat())}[/]"
                )
            return

    console.print(
        f"[dim]Atualizando {len(due)} série(s) da CVM ({desde_ano} a {hoje.year})...[/]\n"
    )
    store = HistoricalSeriesStore(vault_path)
    outcomes = refresh_fii_histories(
        due,
        store=store,
        years=range(desde_ano, hoje.year + 1),
        bridge=None if sem_evidencia else KnowledgeBridge(vault_path),
    )

    table = Table(title="Séries mensais da CVM")
    table.add_column("Ticker")
    table.add_column("Meses", justify="right")
    table.add_column("Novos", justify="right")
    table.add_column("Última competência")
    table.add_column("Status")
    for outcome in outcomes:
        cor = {"ok": "green", "erro": "red", "pulado": "yellow"}[outcome.status]
        table.add_row(
            outcome.ticker,
            str(outcome.observations) if outcome.observations else "—",
            f"+{outcome.added}" if outcome.status == "ok" else "—",
            outcome.last_period or "—",
            f"[{cor}]{outcome.status}[/]",
        )
    console.print(table)
    for outcome in outcomes:
        if outcome.status != "ok":
            console.print(
                f"[dim]{outcome.ticker} · {outcome.status}: {outcome.detail}[/]"
            )

    refreshed_ok = {o.ticker for o in outcomes if o.status == "ok"}
    states = tuple(
        compute_state(
            p.ticker,
            store,
            today=hoje,
            refreshed_at=(
                hoje.isoformat()
                if p.ticker in refreshed_ok
                else (previous.get(p.ticker) or {}).get("refreshed_at")
            ),
        )
        for p in positions
    )
    alerts = series_alerts(previous, states)
    # o estado dos que não foram pedidos agora continua como estava
    kept = tuple(
        SeriesState.from_dict(t, d)
        for t, d in previous.items()
        if t not in {s.ticker for s in states}
    )
    save_state_file(vault_path, (*states, *kept))

    problems = [s for s in states if s.code != "regular" or s.stale]
    console.print(
        f"\n[bold]Resumo:[/] {sum(o.status == 'ok' for o in outcomes)} ok, "
        f"{sum(o.status == 'erro' for o in outcomes)} erro, "
        f"{sum(o.status == 'pulado' for o in outcomes)} pulado; "
        f"{len(problems)} série(s) com problema"
    )
    for alert in alerts:
        console.print(f"[yellow]{alert.line()}[/]")
    if alert_file:
        write_alert_file(alert_file, alerts)
    if report:
        from iip.obsidian.series_report import write_series_report

        console.print(
            "[dim]Estado das séries: "
            f"{write_series_report(vault_path, (*states, *kept), alerts, today_iso=hoje.isoformat())}[/]"
        )
    if any(o.status == "erro" for o in outcomes):
        raise SystemExit(1)


@cli.command("validate-income")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--min-age-days",
    type=int,
    default=None,
    help="Só refaz a validação se a última tem mais de N dias (os relatórios são mensais).",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 02_Portfolio/Validacao_Renda.md (sobrescrita a cada execução).",
)
def validate_income_command(
    vault: str | None, min_age_days: int | None, report: bool
) -> None:
    """Confere a distribuição por cota da CVM (base da renda projetada) com a que a gestora
    escreve no relatório mais recente. Só registra: não altera a renda projetada."""
    import datetime as _dt

    from iip.portfolio.fii_history_refresh import fii_positions
    from iip.portfolio.historical_series import HistoricalSeriesStore
    from iip.portfolio.income_cross_check import (
        load_validation,
        run_cross_checks,
        save_validation,
    )
    from iip.portfolio.registry import PORTFOLIO_ASSETS
    from iip.sources.fii_distribution_harvester import (
        PATRIA_SHEET_TICKERS,
        FiiDistributionHTTPHarvester,
    )

    vault_path = vault or str(get_settings().obsidian_vault)
    # data de calendário (idade da última validação), não timestamp
    hoje = _dt.date.today()  # noqa: DTZ011
    tickers = tuple(sorted(p.ticker for p in fii_positions(PORTFOLIO_ASSETS)))

    if min_age_days is not None:
        previous = load_validation(vault_path)
        stamps = [c.checked_at for c in previous.values()]
        try:
            age = (hoje - _dt.date.fromisoformat(min(stamps))).days if stamps else None
        except ValueError:
            age = None
        if age is not None and age <= min_age_days:
            console.print(
                f"[dim]Validação em dia (última há {age} dias, limite {min_age_days}).[/]"
            )
            if report:
                from iip.obsidian.income_validation_report import (
                    write_validation_report,
                )

                console.print(
                    f"[dim]{write_validation_report(vault_path, tuple(previous.values()))}[/]"
                )
            return

    harvester = FiiDistributionHTTPHarvester()

    def fetch(ticker: str):
        if ticker in PATRIA_SHEET_TICKERS:
            return harvester.fetch_patria_sheet(ticker)
        return harvester.fetch_distribution(ticker)

    console.print(
        f"[dim]Conferindo {len(tickers)} FIIs com os relatórios dos gestores...[/]\n"
    )
    checks = run_cross_checks(
        tickers, HistoricalSeriesStore(vault_path), fetch, today=hoje
    )
    save_validation(vault_path, checks)

    table = Table(title="Renda: CVM contra o gestor")
    table.add_column("Ticker")
    table.add_column("Situação")
    table.add_column("Gestor", justify="right")
    table.add_column("CVM", justify="right")
    table.add_column("Diferença", justify="right")
    cor = {
        "confere": "green",
        "mudanca_recente": "cyan",
        "diverge": "red",
        "so_gestor": "yellow",
    }
    for c in checks:
        table.add_row(
            c.ticker,
            f"[{cor.get(c.status, 'dim')}]{c.label}[/]",
            f"{c.declared:.4f}" if c.declared is not None else "—",
            f"{c.cvm_projection:.4f}" if c.cvm_projection is not None else "—",
            f"{c.diff_projection:+.1%}" if c.diff_projection is not None else "—",
        )
    console.print(table)
    conferem = sum(c.status == "confere" for c in checks)
    console.print(
        f"\n[bold]Resumo:[/] {conferem} conferem, "
        f"{sum(c.status == 'mudanca_recente' for c in checks)} só com o mês recente, "
        f"{sum(c.status == 'diverge' for c in checks)} divergem, "
        f"{sum(c.status == 'so_gestor' for c in checks)} só com número do gestor, "
        f"{sum(c.status in ('sem_gestor', 'leitura_falhou') for c in checks)} sem como conferir"
    )
    if report:
        from iip.obsidian.income_validation_report import write_validation_report

        console.print(f"[dim]{write_validation_report(vault_path, checks)}[/]")


@cli.command("portfolio-income")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--file",
    "snapshot_file",
    type=click.Path(),
    default=None,
    help="Snapshot das posições (padrão: <vault>/02_Portfolio/Current.md).",
)
@click.option(
    "--janela",
    type=int,
    default=6,
    show_default=True,
    help="Quantos meses entram na mediana da distribuição por cota (mínimo 3).",
)
@click.option(
    "--somente-cvm",
    is_flag=True,
    default=False,
    help="Ignora os valores do gestor (iip validate-income) e mostra só a projeção da CVM.",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 02_Portfolio/Renda.md (sobrescrita a cada execução).",
)
def portfolio_income_command(
    vault: str | None,
    snapshot_file: str | None,
    janela: int,
    somente_cvm: bool,
    report: bool,
) -> None:
    """Renda mensal projetada: mediana da distribuição por cota (série da CVM) x quantidade.

    Não usa rede. Só projeta o fundo cuja série é regular; o resto aparece com o motivo
    (rendimento zero/negativo na CVM, série irregular, sem série). É renda bruta estimada,
    não promessa."""
    import datetime as _dt

    from iip.portfolio.historical_series import HistoricalSeriesStore
    from iip.portfolio.income import SOURCE_LABELS, build_income
    from iip.portfolio.income_cross_check import load_validation
    from iip.portfolio.vault_snapshot import parse_current_snapshot

    vault_path = vault or str(get_settings().obsidian_vault)
    path = (
        Path(snapshot_file)
        if snapshot_file
        else Path(vault_path) / "02_Portfolio" / "Current.md"
    )
    if not path.is_file():
        console.print(f"[bold red]Snapshot das posições não encontrado: {path}[/]")
        raise SystemExit(1)

    try:
        result = build_income(
            parse_current_snapshot(path),
            HistoricalSeriesStore(vault_path),
            # data de calendário (idade da série), não timestamp
            today=_dt.date.today(),  # noqa: DTZ011
            window=janela,
            checks=None if somente_cvm else load_validation(vault_path),
        )
    except ValueError as exc:
        console.print(f"[bold red]Não consegui projetar:[/] {exc}")
        raise SystemExit(1) from exc

    hibrida = " (estimativa HÍBRIDA)" if result.is_hybrid else ""
    console.print(
        f"[bold]Renda mensal projetada: R$ {result.monthly_income:,.2f}{hibrida}[/] "
        f"({len(result.effective_lines)} posições, {result.covered_share:.1%} do valor da "
        "carteira)"
    )
    if result.is_hybrid:
        console.print(
            f"[dim]Só a CVM: R$ {result.cvm_monthly_income:,.2f}. A diferença vem de "
            "valores declarados pelo gestor, identificados abaixo.[/]"
        )
    table = Table(title="Entram no total (mediana da distribuição por cota)")
    table.add_column("Ticker")
    table.add_column("Qtd", justify="right")
    table.add_column("CVM", justify="right")
    table.add_column("Gestor", justify="right")
    table.add_column("Efetiva", justify="right")
    table.add_column("R$/mês", justify="right")
    table.add_column("Fonte")
    for line in result.effective_lines:
        table.add_row(
            line.ticker,
            f"{line.quantity:.0f}",
            (
                f"{line.cvm_estimate:.4f}"
                if line.cvm_estimate is not None
                else "sem projeção"
            ),
            (
                f"{line.manager_reported_distribution:.4f}"
                if line.manager_reported_distribution is not None
                else "—"
            ),
            f"{line.effective_estimate:.4f}",
            f"{line.effective_income:,.2f}",
            SOURCE_LABELS.get(line.estimate_source, line.estimate_source)
            + ("" if line.estimate_source == "cvm" else " *"),
        )
    console.print(table)
    for line in result.adjustments:
        console.print(f"[yellow]* {line.ticker}:[/] {line.override_reason}")
    for line in result.excluded:
        if line.last_period:
            console.print(f"[yellow]{line.ticker} sem projeção:[/] {line.reason}")
    sem_serie = [ln.ticker for ln in result.excluded if not ln.last_period]
    console.print(
        f"[dim]Sem série mensal de distribuição por cota ({len(sem_serie)} posições): "
        "ações, FI-Infra, FI-Agro, ETF, FMP-FGTS e renda fixa bancária.[/]"
    )
    if result.stale_series:
        console.print(
            "[yellow]Série defasada: "
            f"{', '.join(ln.ticker for ln in result.stale_series)} — rode "
            "`iip collect-fii-history`.[/]"
        )
    console.print(
        "[dim]Renda bruta estimada; não é promessa. O gestor pode cortar ou aumentar.[/]"
    )

    if report:
        from iip.obsidian.income_report import write_income_report

        console.print(
            f"[dim]Relatório de renda: {write_income_report(vault_path, result)}[/]"
        )


@cli.command("dashboard")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
def dashboard_command(vault: str | None) -> None:
    """Gera 02_Portfolio/Dashboard.md, o painel que junta valuation, decisões, exposição,
    renda e séries. Só monta os blocos; cada um lê o cabeçalho da nota que o comando
    correspondente grava (--report), então rode este depois deles."""
    from iip.obsidian.dashboard import generate_portfolio_dashboard

    vault_path = vault or str(get_settings().obsidian_vault)
    console.print(f"[dim]Dashboard: {generate_portfolio_dashboard(vault_path)}[/]")


@cli.command("collect-macro")
@click.option(
    "--indicator",
    "indicators",
    multiple=True,
    help="Coleta só estes indicadores (id do catálogo; repita a opção). Padrão: todos.",
)
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
def collect_macro_command(indicators: tuple[str, ...], vault: str | None) -> None:
    """Coleta os indicadores macro (BACEN SGS e IBGE SIDRA) e guarda em 07_Research/Macro.

    Cada valor é gravado com a data da coleta; um valor que a fonte revisou é guardado como
    nova versão, sem apagar a anterior. Macro é contexto: não decide aporte nem peso."""
    import datetime as _dt

    from iip.macro.collector import collect_macro
    from iip.macro.contract import INDICATORS
    from iip.macro.store import MacroStore

    unknown = [i for i in indicators if i not in INDICATORS]
    if unknown:
        console.print(
            f"[bold red]Indicador fora do catálogo: {', '.join(unknown)}[/] "
            f"(catálogo: {', '.join(sorted(INDICATORS))})"
        )
        raise SystemExit(1)

    vault_path = vault or str(get_settings().obsidian_vault)
    # data de calendário (data da coleta), não timestamp
    hoje = _dt.date.today()  # noqa: DTZ011
    outcomes = collect_macro(
        tuple(indicators) or None, MacroStore(vault_path), today=hoje
    )

    table = Table(title=f"Coleta macro — {hoje:%d/%m/%Y}")
    table.add_column("Indicador")
    table.add_column("Novos", justify="right")
    table.add_column("Revisados", justify="right")
    table.add_column("Última competência")
    table.add_column("Status")
    for outcome in outcomes:
        cor = "green" if outcome.status == "ok" else "red"
        table.add_row(
            outcome.indicator_id,
            str(outcome.result.new) if outcome.result else "—",
            str(outcome.result.revised) if outcome.result else "—",
            outcome.last_reference or "—",
            f"[{cor}]{outcome.status}[/]",
        )
    console.print(table)
    for outcome in outcomes:
        if outcome.status != "ok":
            console.print(f"[dim]{outcome.indicator_id}: {outcome.detail}[/]")
    revised = sum(o.result.revised for o in outcomes if o.result)
    if revised:
        console.print(
            f"[yellow]{revised} valor(es) revisado(s) pela fonte desde a última coleta.[/]"
        )
    console.print(
        f"\n[bold]Resumo:[/] {sum(o.status == 'ok' for o in outcomes)} ok, "
        f"{sum(o.status == 'erro' for o in outcomes)} erro"
    )
    if any(o.status == "erro" for o in outcomes):
        raise SystemExit(1)


@cli.command("macro-scenarios")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--init",
    is_flag=True,
    default=False,
    help="Cria 07_Research/Macro/cenarios.json a partir do conjunto-padrão, se ainda não "
    "existir (nunca sobrescreve um arquivo editado).",
)
def macro_scenarios_command(vault: str | None, init: bool) -> None:
    """Mostra os cenários de juros e inflação (versão, hash e choques).

    Os choques vivem no arquivo do vault, versionados; o conjunto-padrão é um ponto de partida
    editável, não uma previsão."""
    from iip.macro.scenarios import (
        DEFAULT_SCENARIOS,
        SCENARIOS_RELATIVE_PATH,
        TRANSMISSION_RULE,
        load_scenarios,
        save_scenarios,
    )

    vault_path = vault or str(get_settings().obsidian_vault)
    try:
        current = load_scenarios(vault_path)
    except ValueError as exc:
        console.print(f"[bold red]Cenários inválidos:[/] {exc}")
        raise SystemExit(1) from exc

    if current is None:
        if not init:
            console.print(
                "[yellow]Sem arquivo de cenários. Rode com --init para criar a partir do "
                "conjunto-padrão (editável).[/]"
            )
            raise SystemExit(1)
        console.print(
            f"[dim]Criado: {save_scenarios(vault_path, DEFAULT_SCENARIOS)}[/]"
        )
        current = DEFAULT_SCENARIOS

    console.print(
        f"[bold]Cenários {current.version}[/] (hash {current.content_hash}) — "
        f"{SCENARIOS_RELATIVE_PATH.as_posix()}"
    )
    console.print(f"[dim]{current.origin}[/]")
    table = Table(title="Choques (p.p.)")
    table.add_column("Cenário")
    table.add_column("Juros nominais", justify="right")
    table.add_column("Inflação esperada", justify="right")
    table.add_column("Taxa real direta", justify="right")
    table.add_column("Desloc. da taxa real", justify="right")
    for sc in current.scenarios:
        table.add_row(
            sc.id,
            f"{sc.nominal_rate_shock_pp:+.2f}",
            f"{sc.inflation_shock_pp:+.2f}",
            f"{sc.real_yield_shock_pp:+.2f}",
            f"{sc.real_yield_shift_pp:+.2f}",
        )
    console.print(table)
    console.print(f"[dim]Regra: {TRANSMISSION_RULE}[/]")


@cli.command("macro-sensitivity")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 07_Research/Macro/Sensibilidade.md (sobrescrita a cada execução).",
)
def macro_sensitivity_command(vault: str | None, report: bool) -> None:
    """Reavalia o Bazin e o Yield com a taxa real da NTN-B deslocada por cada cenário.

    Usa os insumos da última rodada de `value-portfolio --report` (não busca nada). É
    sensibilidade das premissas: não é recomendação e não altera aporte, peso-alvo nem
    rebalanceamento."""
    import datetime as _dt

    from iip.macro.scenarios import load_scenarios
    from iip.macro.sensitivity import run_sensitivity
    from iip.macro.store import MacroStore
    from iip.portfolio.valuation_inputs import load_valuation_inputs

    vault_path = vault or str(get_settings().obsidian_vault)
    try:
        scenario_set = load_scenarios(vault_path)
    except ValueError as exc:
        console.print(f"[bold red]Cenários inválidos:[/] {exc}")
        raise SystemExit(1) from exc
    if scenario_set is None:
        console.print(
            "[yellow]Sem cenários: rode `iip macro-scenarios --init` e, se quiser, edite o "
            "arquivo.[/]"
        )
        raise SystemExit(1)
    inputs = load_valuation_inputs(vault_path)
    if inputs is None:
        console.print(
            "[yellow]Sem insumos de valuation: rode `iip value-portfolio --report` primeiro "
            "(ele guarda os insumos que esta sensibilidade reusa).[/]"
        )
        raise SystemExit(1)

    # data de calendário (idade dos insumos), não timestamp
    result = run_sensitivity(
        inputs,
        scenario_set,
        store=MacroStore(vault_path),
        today=_dt.date.today(),  # noqa: DTZ011
        exceptions=_load_valuation_exceptions(vault_path),
    )

    if result.base_rate is not None:
        console.print(
            f"[bold]Taxa observada:[/] IPCA + {result.base_rate.real_yield:.2%} "
            f"(NTN-B {result.base_rate.maturity}, ref. {result.base_rate.reference_date}); "
            f"insumos de {result.inputs_run_date}."
        )
    for warning in result.warnings:
        console.print(f"[yellow]Aviso:[/] {warning}")

    sensitive = [a for a in result.assets if a.sensitive_methods]
    table = Table(title="Sensibilidade do valor justo (variação sobre a base)")
    table.add_column("Ativo")
    table.add_column("Modelo")
    table.add_column("Base", justify="right")
    for scenario_id, _, shift in result.scenarios:
        table.add_column(f"{scenario_id} ({shift:+.2f})", justify="right")
    for asset in sensitive:
        for index, base in enumerate(asset.base):
            if base.method not in asset.sensitive_methods:
                continue
            cells = []
            for outcome in asset.scenarios:
                other = outcome.methods[index]
                if other.fair_value is None or not base.fair_value:
                    cells.append("sem valor")
                else:
                    cells.append(
                        f"{(other.fair_value / base.fair_value - 1) * 100:+.0f}%"
                    )
            table.add_row(
                asset.ticker,
                base.method,
                f"{base.fair_value:.2f}" if base.fair_value is not None else "—",
                *cells,
            )
    console.print(table)
    console.print(
        f"[dim]{len(sensitive)} de {len(result.assets)} ativos sensíveis; os demais não usam "
        "a taxa. Sensibilidade das premissas, não recomendação; não altera aporte nem peso "
        f"(cenários {result.scenario_version}, hash {result.scenario_hash}).[/]"
    )
    if report:
        from iip.obsidian.sensitivity_report import write_sensitivity_report

        console.print(
            f"[dim]{write_sensitivity_report(vault_path, result, scenario_set)}[/]"
        )


@cli.command("macro-context")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 07_Research/Macro/Contexto_Macro.md (sobrescrita a cada execução).",
)
def macro_context_command(vault: str | None, report: bool) -> None:
    """Mostra o contexto macro guardado: último valor, comparação com 12 meses antes, frescor
    e conferência entre fontes. Não usa rede; só descreve, não recomenda."""
    import datetime as _dt

    from iip.macro.context import build_context
    from iip.macro.store import MacroStore

    vault_path = vault or str(get_settings().obsidian_vault)
    # data de calendário (idade do dado), não timestamp
    context = build_context(MacroStore(vault_path), _dt.date.today())  # noqa: DTZ011

    if len(context.missing) == len(context.readings):
        console.print(
            "[yellow]Nenhum dado macro guardado ainda: rode `iip collect-macro`.[/]"
        )
        raise SystemExit(1)

    table = Table(title="Contexto macro (dado guardado)")
    table.add_column("Indicador")
    table.add_column("Último", justify="right")
    table.add_column("Competência")
    table.add_column("Variação 12m", justify="right")
    table.add_column("Situação")
    for reading in context.readings:
        if reading.missing:
            table.add_row(reading.indicator.name, "—", "—", "—", "[red]sem dados[/]")
            continue
        change = "—" if reading.change is None else f"{reading.change:+.2f}"
        situacao = (
            "[yellow]defasado[/]"
            if reading.stale
            else ("parcial" if reading.latest.provisional else "em dia")
        )
        table.add_row(
            reading.indicator.name,
            f"{reading.latest.value:g}",
            reading.latest.reference,
            change,
            situacao,
        )
    console.print(table)
    for check in context.source_checks:
        if check.compared:
            verdict = "concordam" if check.agrees else "[red]divergem[/]"
            console.print(
                f"[dim]{check.a} x {check.b}: {verdict} em {check.compared} "
                f"competências (maior diferença {check.max_difference:.2f})[/]"
            )
    console.print(
        "[dim]Contexto, não recomendação. Só vale como conhecido em tal data a partir da "
        f"primeira coleta ({context.first_collected_at}).[/]"
    )
    if report:
        from iip.obsidian.macro_report import write_macro_report

        console.print(f"[dim]{write_macro_report(vault_path, context)}[/]")


@cli.command("macro-alerts")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--init",
    is_flag=True,
    default=False,
    help="Cria 07_Research/Macro/alertas_macro.json a partir do conjunto-padrão, se ainda "
    "não existir (nunca sobrescreve um arquivo editado).",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 07_Research/Macro/Alertas_Macro.md (sobrescrita a cada execução).",
)
@click.option(
    "--alert-file",
    default=None,
    help="Arquivo de texto com uma linha por alerta de Atenção NOVO (o agendador o lê para "
    "a notificação do Windows). Sem alerta novo, o arquivo é apagado.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Avalia e mostra, sem gravar estado, nota nem arquivo de alerta.",
)
def macro_alerts_command(
    vault: str | None,
    init: bool,
    report: bool,
    alert_file: str | None,
    dry_run: bool,
) -> None:
    """Avalia as regras de alerta macro sobre o dado guardado (sem rede).

    Alertas são informativos: dizem o que mudou no ambiente e não decidem, sugerem nem
    alteram aporte, peso-alvo ou rebalanceamento. Um alerta ativo não faz o comando falhar;
    regra ou estado inválido, sim, com o motivo."""
    import datetime as _dt

    from iip.macro.alerts import (
        DEFAULT_RULES,
        RULES_RELATIVE_PATH,
        load_rules,
        load_state,
        run_alerts,
        save_rules,
        save_state,
        write_alert_file,
    )
    from iip.macro.store import MacroStore
    from iip.portfolio.valuation_inputs import load_valuation_inputs

    vault_path = vault or str(get_settings().obsidian_vault)
    try:
        rule_set = load_rules(vault_path)
        state = load_state(vault_path)
    except ValueError as exc:
        console.print(f"[bold red]Configuração dos alertas inválida:[/] {exc}")
        raise SystemExit(1) from exc

    if rule_set is None:
        if not init:
            console.print(
                "[yellow]Sem arquivo de regras. Rode com --init para criar a partir do "
                "conjunto-padrão (editável).[/]"
            )
            raise SystemExit(1)
        if dry_run:
            rule_set = DEFAULT_RULES
        else:
            console.print(f"[dim]Criado: {save_rules(vault_path, DEFAULT_RULES)}[/]")
            rule_set = DEFAULT_RULES

    store = MacroStore(vault_path)
    # data de calendário (idade do dado e janela dos eventos), não timestamp
    hoje = _dt.date.today()  # noqa: DTZ011
    run = run_alerts(
        store, rule_set, state, hoje, inputs=load_valuation_inputs(vault_path)
    )

    console.print(
        f"[bold]Regras {rule_set.version}[/] (hash {rule_set.content_hash}) — "
        f"{RULES_RELATIVE_PATH.as_posix()}"
    )
    table = Table(title=f"Regras de alerta macro — {hoje:%d/%m/%Y}")
    table.add_column("Regra")
    table.add_column("Severidade")
    table.add_column("Situação")
    table.add_column("Medida atual")
    from iip.obsidian.macro_alerts_report import STATUS_LABELS, current_measure

    for ev in run.evaluations:
        cor = "red" if ev.status == "ativo" else "dim"
        table.add_row(
            ev.rule.id,
            ev.rule.severity,
            f"[{cor}]{STATUS_LABELS[ev.status].replace('**', '')}[/]",
            current_measure(ev),
        )
    console.print(table)

    for alert in run.active:
        marca = " [cyan](novo)[/]" if alert.is_new else ""
        console.print(f"[bold]{alert.severity.upper()}[/]{marca} {alert.message}")
        for line in alert.impact:
            console.print(f"  [dim]{line}[/]")
    for alert in run.data_alerts:
        console.print(f"[yellow]DADO[/] {alert.message}")
    for watching in run.watching:
        console.print(
            f"[dim]Em observação: {watching.rule_id} (emitido, ainda não rearmou).[/]"
        )
    if not run.active and not run.data_alerts:
        console.print("[green]Nenhum alerta ativo.[/]")
    console.print(
        f"\n[bold]Resumo:[/] {len(run.active)} ativo(s) ({len(run.new_alerts)} novo(s)), "
        f"{len(run.data_alerts)} aviso(s) de dado, {len(run.watching)} em observação."
    )

    if dry_run:
        console.print("[dim]--dry-run: nada foi gravado.[/]")
        return
    console.print(f"[dim]Estado: {save_state(vault_path, run.state)}[/]")
    if alert_file:
        lines = write_alert_file(alert_file, run)
        console.print(
            f"[dim]{len(lines)} linha(s) para notificação em {alert_file}.[/]"
        )
    if report:
        from iip.obsidian.macro_alerts_report import write_alerts_report

        console.print(f"[dim]{write_alerts_report(vault_path, run)}[/]")
    # alerta não é falha: o código de saída só reflete configuração inválida


@cli.command("target-policy")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--init",
    is_flag=True,
    default=False,
    help="Cria 02_Portfolio/Politica_Pesos_Alvo.json a partir do Current.md, com todos os "
    "pesos, tolerâncias e limites VAZIOS (nunca sobrescreve um arquivo existente).",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 02_Portfolio/Politica_Pesos_Alvo.md (tabela de decisão).",
)
def target_policy_command(vault: str | None, init: bool, report: bool) -> None:
    """Mostra e valida a política de pesos-alvo por ativo contra o Current.md.

    É uma camada de política: não compra, vende, aporta nem rebalanceia, e nenhum percentual é
    preenchido por este comando. Política ou snapshot inválidos param com o motivo."""
    import datetime as _dt

    from iip.portfolio.target_policy import (
        POLICY_RELATIVE_PATH,
        SNAPSHOT_RELATIVE_PATH,
        SUM_INDIVIDUAL_REFERENCES,
        build_initial_policy,
        load_policy,
        read_snapshot_rows,
        reconcile,
        save_policy,
        target_sum,
    )

    vault_path = vault or str(get_settings().obsidian_vault)
    # data de calendário (versão da política e idade do dado), não timestamp
    hoje = _dt.date.today()  # noqa: DTZ011
    try:
        policy = load_policy(vault_path)
        rows = read_snapshot_rows(Path(vault_path) / SNAPSHOT_RELATIVE_PATH)
        if policy is None:
            if not init:
                console.print(
                    "[yellow]Sem política de pesos-alvo. Rode com --init para criar a partir "
                    "do Current.md, com todos os percentuais vazios.[/]"
                )
                raise SystemExit(1)
            policy = build_initial_policy(rows, version=f"{hoje.isoformat()}.1")
            console.print(f"[dim]Criado: {save_policy(vault_path, policy)}[/]")
    except ValueError as exc:
        console.print(f"[bold red]Política de pesos-alvo inválida:[/] {exc}")
        raise SystemExit(1) from exc

    rec = reconcile(policy, rows)
    status_count: dict[str, int] = {}
    for line in policy.lines:
        status_count[line.status] = status_count.get(line.status, 0) + 1
    console.print(
        f"[bold]Política {policy.version}[/] (hash {policy.content_hash}) — "
        f"{POLICY_RELATIVE_PATH.as_posix()}"
    )
    console.print(
        f"Status: {policy.approval_status}; base {policy.base_id}; monitoramento "
        f"{'ligado' if policy.monitoring_enabled else 'desligado'}; regra de soma: "
        f"{policy.sum_rule or 'em aberto'}."
    )
    if policy.sum_rule == SUM_INDIVIDUAL_REFERENCES:
        console.print(
            f"Soma dos alvos individuais definidos: {target_sum(policy):g}% (informativa: "
            "referencias por ativo, nao uma carteira-alvo)."
        )
    table = Table(title=f"Linhas da política — snapshot de R$ {rec.total:,.2f}")
    table.add_column("Linha")
    table.add_column("Classe")
    table.add_column("Valor", justify="right")
    table.add_column("Peso atual", justify="right")
    table.add_column("Alvo", justify="right")
    table.add_column("Status")
    for item in sorted(rec.weights, key=lambda w: -w.weight_pct)[:12]:
        target = "—" if item.line.target_pct is None else f"{item.line.target_pct:.2f}%"
        table.add_row(
            item.line.id,
            item.line.asset_class,
            f"{item.value:,.2f}",
            f"{item.weight_pct:.2f}%",
            target,
            item.line.status,
        )
    console.print(table)
    console.print(
        f"[dim]{len(policy.lines)} linhas ("
        + ", ".join(f"{n} {s}" for s, n in sorted(status_count.items()))
        + f"); as 12 maiores acima; {len(policy.retired)} posições zeradas fora do "
        "universo.[/]"
    )
    for row in rec.uncovered:
        console.print(f"[yellow]Posição sem linha na política:[/] {row.id}")
    for line in rec.absent_lines:
        console.print(f"[yellow]Linha sem posição no snapshot:[/] {line.id}")
    for row in rec.reopened:
        console.print(f"[yellow]Posição zerada que voltou ao snapshot:[/] {row.id}")
    for group, member in rec.missing_members:
        console.print(f"[yellow]Registro que saiu de {group}:[/] {member}")
    for group, row in rec.new_members:
        console.print(f"[yellow]Registro novo em {group}:[/] {row.id}")
    if rec.consistent and not rec.missing_members:
        console.print("[green]Política e snapshot batem.[/]")
    console.print(
        "[dim]Política, não ordem: nada é comprado, vendido, aportado nem rebalanceado.[/]"
    )
    if report:
        from iip.obsidian.target_policy_report import write_policy_report

        console.print(f"[dim]{write_policy_report(vault_path, policy, rec, hoje)}[/]")


@cli.command("monitoring-events")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 02_Portfolio/Monitoramento.md (sobrescrita a cada execução).",
)
def monitoring_events_command(vault: str | None, report: bool) -> None:
    """Leitura estruturada do monitoramento de pesos-alvo: um evento por linha da política.

    Camada só de leitura: não decide, não executa, não notifica e não liga o monitoramento.
    `automatic_action` é sempre "nenhuma", mesmo nas linhas em desvio. Rodado manualmente; não
    faz parte do job diário e não chama `decide-portfolio`."""
    import datetime as _dt

    from iip.portfolio.monitoring_event import (
        SEVERITY_DEVIATION,
        build_monitoring_events,
    )
    from iip.portfolio.target_policy import (
        SNAPSHOT_RELATIVE_PATH,
        load_policy,
        read_snapshot_rows,
        reconcile,
    )

    vault_path = vault or str(get_settings().obsidian_vault)
    # data de calendário (idade do dado), não timestamp
    hoje = _dt.date.today()  # noqa: DTZ011
    try:
        policy = load_policy(vault_path)
        rows = read_snapshot_rows(Path(vault_path) / SNAPSHOT_RELATIVE_PATH)
    except ValueError as exc:
        console.print(f"[bold red]Política ou snapshot inválidos:[/] {exc}")
        raise SystemExit(1) from exc
    if policy is None:
        console.print(
            "[yellow]Sem política de pesos-alvo. Rode `iip target-policy --init` primeiro.[/]"
        )
        raise SystemExit(1)

    rec = reconcile(policy, rows)
    events = build_monitoring_events(policy, rec, hoje.isoformat())
    deviations = [event for event in events if event.severity == SEVERITY_DEVIATION]

    console.print(
        f"[bold]Eventos de monitoramento[/] — política {policy.version} (hash "
        f"{policy.content_hash}), {len(events)} linhas."
    )
    console.print(
        "Monitoramento (campo da política): "
        f"{'ligado' if policy.monitoring_enabled else 'desligado'}; este comando só lê, nunca "
        "decide, executa ou notifica."
    )
    if deviations:
        table = Table(title=f"Linhas em desvio ({len(deviations)} de {len(events)})")
        table.add_column("Linha")
        table.add_column("Peso atual", justify="right")
        table.add_column("Faixa", justify="right")
        table.add_column("Estado")
        table.add_column("Tipo de desvio")
        for event in sorted(deviations, key=lambda e: -e.current_weight_pct):
            band = (
                "—"
                if event.band_low is None
                else f"{event.band_low:.2f}–{event.band_high:.2f}%"
            )
            table.add_row(
                event.line_id,
                f"{event.current_weight_pct:.2f}%",
                band,
                event.state,
                event.deviation_type or "—",
            )
        console.print(table)
    else:
        console.print("[green]Nenhuma linha em desvio.[/]")
    console.print(
        f"[dim]{len(events)} linhas lidas; {len(deviations)} em desvio; automatic_action "
        "sempre 'nenhuma'. Leitura, não ordem: nada é decidido, executado ou notificado.[/]"
    )
    if report:
        from iip.obsidian.monitoring_event_report import write_monitoring_report

        console.print(
            f"[dim]{write_monitoring_report(vault_path, events, policy, hoje)}[/]"
        )


@cli.command("portfolio-layers")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 02_Portfolio/Camadas.md (sobrescrita a cada execução).",
)
def portfolio_layers_command(vault: str | None, report: bool) -> None:
    """Mostra o patrimônio em camadas: classe, ativo, ações (consolidado, setor, segmento) e
    FIIs (tipo e segmento), cada percentual com o seu denominador.

    Só leitura do Current.md e do registro de ativos (e, se existir, do que a política de
    pesos-alvo já define): não define alvos nem limites, não altera a política e não decide,
    aporta nem rebalanceia."""
    import datetime as _dt

    from iip.portfolio.layers import build_layers
    from iip.portfolio.target_policy import (
        SNAPSHOT_RELATIVE_PATH,
        load_policy,
        read_snapshot_rows,
    )

    vault_path = vault or str(get_settings().obsidian_vault)
    snapshot_path = Path(vault_path) / SNAPSHOT_RELATIVE_PATH
    try:
        rows = read_snapshot_rows(snapshot_path)
        policy = load_policy(vault_path)
        layers = build_layers(rows, policy)
    except ValueError as exc:
        console.print(f"[bold red]Camadas do patrimônio:[/] {exc}")
        raise SystemExit(1) from exc

    # data de calendário (idade do snapshot), não timestamp
    hoje = _dt.date.today()  # noqa: DTZ011
    snapshot_date = _dt.date.fromtimestamp(snapshot_path.stat().st_mtime)
    console.print(
        f"[bold]{layers.position_count} posições, R$ {layers.total:,.2f}[/] "
        f"(snapshot de {snapshot_date:%d/%m/%Y}, {(hoje - snapshot_date).days} dias)"
    )
    table = Table(
        title="1. Patrimônio por classe (peso_total_pct: sobre o patrimônio total)"
    )
    table.add_column("Classe")
    table.add_column("Ativos", justify="right")
    table.add_column("Valor", justify="right")
    table.add_column("peso_total_pct", justify="right")
    for group in layers.classes:
        table.add_row(
            group.label,
            str(len(group.holdings)),
            f"{group.value:,.2f}",
            f"{group.weight_total_pct:.2f}%",
        )
    console.print(table)
    if layers.stocks:
        table = Table(title="3. Ações (peso_classe_pct: sobre o valor das ações)")
        table.add_column("Ação")
        table.add_column("peso_total_pct", justify="right")
        table.add_column("peso_classe_pct", justify="right")
        for holding in layers.stocks.holdings[:5]:
            table.add_row(
                holding.id,
                f"{holding.weight_total_pct:.2f}%",
                f"{layers.stocks.weight_group_pct(holding):.2f}%",
            )
        console.print(table)
    defined = sum(1 for h in layers.assets if h.target_pct is not None)
    console.print(
        f"[dim]{len(layers.assets)} linhas de ativo, {defined} com alvo definido na política "
        f"({policy.approval_status if policy else 'sem política'}). Só leitura: nada é "
        "definido, sinalizado, comprado, vendido, aportado nem rebalanceado.[/]"
    )
    if layers.unclassified:
        console.print(
            f"[yellow]Sem classificação no registro:[/] {', '.join(layers.unclassified)}"
        )
    if report:
        from iip.obsidian.layers_report import write_layers_report

        console.print(
            "[dim]"
            + str(
                write_layers_report(
                    vault_path,
                    layers,
                    today=hoje,
                    snapshot_date=snapshot_date,
                    policy_hash=policy.content_hash if policy else None,
                    policy_status=policy.approval_status if policy else None,
                )
            )
            + "[/]"
        )


@cli.command("valuation-exceptions")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--init",
    is_flag=True,
    default=False,
    help="Cria 02_Portfolio/Excecoes_Valuation.json com as exceções declaradas pelo usuário "
    "(CSUD3: Graham excluído), se ainda não existir (nunca sobrescreve um arquivo editado).",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 02_Portfolio/Excecoes_Valuation.md (sobrescrita a cada execução).",
)
def valuation_exceptions_command(vault: str | None, init: bool, report: bool) -> None:
    """Mostra e valida as exceções metodológicas de valuation (por ativo, com motivo e data de
    revisão obrigatória), que prevalecem sobre as palavras-chave do setor.

    Uma exceção vencida continua aplicada e é sinalizada; nada a remove sozinho. Não altera
    valuation nem decisão: só descreve o que as regras declaradas fazem. Arquivo inválido para
    o comando com o motivo."""
    import datetime as _dt

    from iip.obsidian.valuation_exceptions_report import (
        effect_of,
        write_exceptions_report,
    )
    from iip.portfolio_data.valuation_exceptions import (
        DEFAULT_EXCEPTIONS,
        EXCEPTIONS_RELATIVE_PATH,
        NO_EXCEPTIONS,
        load_exceptions,
        save_exceptions,
    )

    vault_path = vault or str(get_settings().obsidian_vault)
    try:
        exceptions = load_exceptions(vault_path)
        if exceptions is None and init:
            console.print(
                f"[dim]Criado: {save_exceptions(vault_path, DEFAULT_EXCEPTIONS)}[/]"
            )
            exceptions = DEFAULT_EXCEPTIONS
    except ValueError as exc:
        console.print(
            f"[bold red]Exceções metodológicas de valuation inválidas:[/] {exc}"
        )
        raise SystemExit(1) from exc
    if exceptions is None:
        console.print(
            "[yellow]Sem arquivo de exceções: valem só as regras por palavra-chave do setor. "
            "Rode com --init para criar a partir das exceções declaradas (editável).[/]"
        )
        exceptions = NO_EXCEPTIONS

    # data de calendário (vencimento das revisões), não timestamp
    hoje = _dt.date.today()  # noqa: DTZ011
    console.print(
        f"[bold]Exceções {exceptions.version}[/] (hash {exceptions.content_hash}) — "
        f"{EXCEPTIONS_RELATIVE_PATH.as_posix()}"
    )
    table = Table(title="Exceções metodológicas de valuation")
    table.add_column("Id")
    table.add_column("Ativo")
    table.add_column("Ação")
    table.add_column("Efeito hoje")
    table.add_column("Revisão até")
    table.add_column("Situação")
    for item in exceptions.items:
        vencida = item.overdue(hoje)
        table.add_row(
            item.id,
            item.ticker,
            "exclui" if item.action == "exclude" else "lidera",
            effect_of(item, exceptions),
            item.review_by,
            "[red]VENCIDA[/]" if vencida else "vigente",
        )
    console.print(table)
    for item in exceptions.overdue(hoje):
        console.print(
            f"[yellow]{item.id} está com a revisão vencida (era até {item.review_by}): "
            "continua aplicada; revise ou renove a data.[/]"
        )
    console.print(
        "[dim]Exceção é regra metodológica declarada, não conclusão sobre o valor justo; "
        "prevalece sobre as palavras-chave do setor.[/]"
    )
    if report:
        console.print(
            f"[dim]{write_exceptions_report(vault_path, exceptions, hoje)}[/]"
        )


@cli.command("decide-portfolio")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env).",
)
@click.option(
    "--ano",
    type=int,
    default=None,
    help="Ano fiscal da DFP (padrão: ano anterior). Os FIIs usam sempre o ano corrente.",
)
@click.option(
    "--persist",
    is_flag=True,
    default=False,
    help="Grava cada decisão em 03_Decisions (DEC-<ticker>-<data>, append-only: rodar "
    "de novo no mesmo dia não regrava). Sem esta opção nada é gravado.",
)
@click.option(
    "--ticker",
    "tickers",
    multiple=True,
    help="Decide só estas posições da carteira (repita a opção). Padrão: todas.",
)
@click.option(
    "--alert-file",
    type=click.Path(),
    default=None,
    help="Grava aqui uma linha por decisão que mudou desde a anterior (pioras primeiro); "
    "sem mudança, apaga o arquivo da rodada anterior. É o que o agendador lê para "
    "notificar.",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 02_Portfolio/Decisoes.md (sobrescrita a cada execução, exceto se "
    "nenhuma posição foi decidida); independente de --persist.",
)
def decide_portfolio_command(
    vault: str | None,
    ano: int | None,
    persist: bool,
    report: bool,
    tickers: tuple[str, ...],
    alert_file: str | None,
) -> None:
    """Decide a carteira inteira: análise + valuation + evidência real -> decisão.

    Uma busca por posição alimenta o analisador e o valuation (a cota do bolsai não é
    gasta duas vezes). Cita as evidências mais recentes que já existem no vault; sem
    nenhuma, a posição é pulada. O sinal de tese é sempre Neutro. Nunca inventa dado."""
    from iip.portfolio.batch_decide import decide_portfolio
    from iip.portfolio.registry import assets_refreshable_now

    positions = None
    if tickers:
        wanted = {t.strip().upper() for t in tickers}
        positions = tuple(a for a in assets_refreshable_now() if a.ticker in wanted)
        unknown = wanted - {a.ticker for a in positions}
        if unknown:
            console.print(
                f"[bold red]Fora da carteira (ou sem fetch): {', '.join(sorted(unknown))}[/]"
            )
            raise SystemExit(1)

    bolsai_key = _unwrap_secret(get_settings().bolsai_api_key)
    brapi_token = _unwrap_secret(get_settings().brapi_token)
    vault_path = vault or str(get_settings().obsidian_vault)

    if not bolsai_key:
        console.print(
            "[dim]IIP_BOLSAI_API_KEY não definida — sem preço/LPA/VPA, várias posições "
            "ficam sem dado.[/]"
        )

    console.print("[dim]Decidindo a carteira...[/]\n")
    resultado = decide_portfolio(
        bolsai_api_key=bolsai_key,
        brapi_token=brapi_token,
        vault_path=vault_path,
        persist=persist,
        ano=ano,
        positions=positions,
    )
    console.print(f"[dim]{resultado.ntnb_note}[/]\n")

    table = Table(title=f"Decisões da carteira — {resultado.decision_date:%d/%m/%Y}")
    table.add_column("Ticker")
    table.add_column("Decisão")
    table.add_column("Anterior")
    table.add_column("Score", justify="right")
    table.add_column("Conf.", justify="right")
    table.add_column("Análise", justify="right")
    table.add_column("Valuation", justify="right")
    table.add_column("Status")

    verdict_color = {
        "COMPRAR": "bold green",
        "MANTER": "green",
        "AGUARDAR": "yellow",
        "REDUZIR": "red",
        "VENDER": "bold red",
    }
    for outcome in resultado.outcomes:
        cor = {"ok": "green", "erro": "red", "pulado": "yellow"}[outcome.status]
        if outcome.status == "ok":
            table.add_row(
                outcome.ticker,
                f"[{verdict_color.get(outcome.verdict, 'white')}]{outcome.verdict}[/]",
                outcome.previous_verdict or "—",
                f"{outcome.score:.2f}",
                f"{outcome.confidence:.2f}",
                f"{outcome.analysis_score:.1f}",
                (
                    "—"
                    if outcome.valuation_score is None
                    else f"{outcome.valuation_score:.2f}"
                ),
                f"[{cor}]{outcome.persisted or 'ok'}[/]",
            )
        else:
            table.add_row(
                outcome.ticker,
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
                f"[{cor}]{outcome.status}[/]",
            )
    console.print(table)

    for outcome in (*resultado.skipped, *resultado.failed):
        console.print(f"[dim]{outcome.ticker} · {outcome.status}: {outcome.detail}[/]")
    from iip.portfolio.decision_alerts import decision_changes, write_alert_file

    for change in decision_changes(resultado):
        console.print(
            f"[bold]{change.ticker}:[/] {change.previous} -> {change.current}"
            f" ({change.direction})"
        )
    if alert_file:
        write_alert_file(alert_file, resultado)
    console.print(
        f"\n[bold]Resumo:[/] {len(resultado.succeeded)} decididas, "
        f"{len(resultado.failed)} erro, {len(resultado.skipped)} pulado"
    )
    console.print(
        "[dim]A decisão resume o que o projeto mede; não é ordem de compra ou venda. "
        "Sinal de tese: Neutro; sem valuation a nota é neutra (5,0).[/]"
    )

    if report and not resultado.succeeded:
        console.print(
            "[yellow]Relatório NÃO gravado: nenhuma posição foi decidida nesta rodada; "
            "a nota anterior foi mantida.[/]"
        )
    elif report:
        from iip.obsidian.decision_report import write_decision_report

        console.print(
            f"[dim]Relatório de decisões: {write_decision_report(vault_path, resultado)}[/]"
        )

    if resultado.failed:
        raise SystemExit(1)


@cli.command("value-portfolio")
@click.option(
    "--vault",
    default=None,
    help="Caminho do vault (padrão: IIP_OBSIDIAN_VAULT do .env). Só usado com --persist.",
)
@click.option(
    "--ano",
    type=int,
    default=None,
    help="Ano fiscal da DFP (padrão: ano anterior — a DFP só sai meses depois).",
)
@click.option(
    "--persist",
    is_flag=True,
    default=False,
    help="Grava no vault o primeiro método que produziu valor (a nota de score "
    "guarda um só snapshot de valuation). Sem esta opção nada é gravado.",
)
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Grava a nota 02_Portfolio/Valuation.md no vault com todos os métodos por "
    "ativo (tabelas por classe, motivos dos métodos sem valor, guia de leitura). "
    "Sobrescrita a cada execução (exceto se nenhuma posição foi avaliada — aí a "
    "nota anterior é mantida); independente de --persist.",
)
def value_portfolio_command(
    vault: str | None, ano: int | None, persist: bool, report: bool
) -> None:
    """Valuation da carteira: cada posição é avaliada por TODOS os métodos
    que cabem nela (Graham, Bazin...), lado a lado, com valor e margem de
    segurança contra o preço atual.

    Bazin usa como taxa exigida o yield REAL atual da NTN-B longa (Tesouro
    Transparente), buscado uma vez por rodada — nunca os 6% fixos. Sem a
    taxa, Bazin fica sem valor e o motivo é mostrado.

    Só avalia classes com método implementado (ações: Graham/Bazin; FIIs:
    NAV/Yield); o resto aparece como "pulado" com o motivo. O ano dos FIIs é
    sempre o corrente; --ano vale só para a DFP das ações. Nunca inventa valor: onde nenhum método
    produz, a linha diz por quê.
    """
    from iip.portfolio.batch_value import NO_METHOD_PREFIX, value_portfolio

    bolsai_key = _unwrap_secret(get_settings().bolsai_api_key)
    brapi_token = _unwrap_secret(get_settings().brapi_token)
    vault_path = vault or str(get_settings().obsidian_vault)

    if not bolsai_key:
        console.print(
            "[dim]IIP_BOLSAI_API_KEY não definida — sem preço/LPA/VPA, Graham não calcula.[/]"
        )

    exceptions = _load_valuation_exceptions(vault_path)
    console.print("[dim]Avaliando carteira...[/]\n")
    resultado = value_portfolio(
        bolsai_api_key=bolsai_key,
        brapi_token=brapi_token,
        vault_path=vault_path,
        persist=persist,
        ano=ano,
        exceptions=exceptions,
    )
    console.print(f"[dim]{resultado.ntnb_note}[/]\n")

    table = Table(
        title="Valuation da carteira — valor justo/teto (margem de segurança)"
    )
    table.add_column("Ticker")
    table.add_column("Preço", justify="right")
    table.add_column("Método principal")
    table.add_column("Valor (margem)", justify="right")
    table.add_column("Demais métodos")
    table.add_column("Status")

    # Positions of a class with no implemented method would be N identical
    # "pulado" rows; summarize them per class in one line instead.
    class_skips: dict[str, list[str]] = {}
    shown = []
    for outcome in resultado.outcomes:
        if outcome.status == "pulado" and outcome.detail.startswith(NO_METHOD_PREFIX):
            class_skips.setdefault(outcome.detail, []).append(outcome.ticker)
        else:
            shown.append(outcome)

    for outcome in shown:
        cor = {"ok": "green", "erro": "red", "pulado": "yellow"}[outcome.status]
        table.add_row(
            outcome.ticker,
            f"{outcome.price:.2f}" if outcome.price is not None else "—",
            *_lead_and_others(outcome.attempts),
            f"[{cor}]{outcome.status}[/]",
        )

    console.print(table)
    for outcome in shown:
        for attempt in outcome.attempts:
            if attempt.status in ("not_applicable", "insufficient_data"):
                console.print(
                    f"[dim]{outcome.ticker} · {attempt.method.value} sem valor: {attempt.reason}[/]"
                )
    for detail, tickers in class_skips.items():
        console.print(
            f"[yellow]pulado[/] ({len(tickers)}): {detail} — {', '.join(tickers)}"
        )
    console.print(
        f"\n[bold]Resumo:[/] {len(resultado.succeeded)} ok, "
        f"{len(resultado.failed)} erro, {len(resultado.skipped)} pulado"
    )
    console.print(
        "[dim]Valor justo não é recomendação: Graham parte do patrimônio (fraco para "
        "tecnologia e ativos intangíveis); Bazin usa o caixa pago no ano fiscal; "
        "NAV é o patrimônio por cota; Yield capitaliza a renda de 12 meses pela "
        "NTN-B real + prêmio de 3 p.p. (só FIIs de tijolo).[/]"
    )

    if report and not resultado.succeeded:
        # Nothing was valued (typically the bolsai daily quota): overwriting the note
        # would replace the last good valuation with a page of errors.
        console.print(
            "[yellow]Relatório de valuation NÃO gravado: nenhuma posição foi avaliada "
            "nesta rodada; a nota anterior foi mantida.[/]"
        )
    elif report:
        import datetime as _dt

        from iip.obsidian.valuation_report import write_valuation_report

        written = write_valuation_report(
            vault_path,
            resultado,
            # data de calendário do usuário (a mesma das decisões), não timestamp
            as_of=_dt.date.today(),  # noqa: DTZ011
        )
        console.print(f"[dim]Relatório de valuation: {written}[/]")

        from iip.portfolio.valuation_inputs import (
            build_valuation_inputs,
            save_valuation_inputs,
        )

        # data de calendário (a data da rodada), não timestamp
        run_date = _dt.date.today()  # noqa: DTZ011
        saved = save_valuation_inputs(
            vault_path, build_valuation_inputs(resultado, run_date=run_date)
        )
        console.print(f"[dim]Insumos do valuation (para a sensibilidade): {saved}[/]")

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
@click.option(
    "--auto-valuation",
    "auto_valuation",
    is_flag=True,
    default=False,
    help="Só com --decide e --type equity, fii, agro, etf ou fixed_income: calcula a nota "
    "de valuation pelo método principal do catálogo (ações: Bazin em setores de "
    "dividendo, Graham nos demais; FIIs e FIAGRO (--type agro): NAV, o patrimônio por "
    "cota; FI-Infra listado (--type fixed_income): NAV, a cota da CVM contra o preço; ETF (--type etf): NAV, a cota da gestora contra o "
    "preço; o FMP-FGTS (AXIA3) só sai no value-portfolio, que busca a carteira na CDA; "
    "Bazin/Yield usam a NTN-B longa, buscada agora). O --data-file precisa trazer os "
    "insumos (lpa/vpa/dividend_per_share nas ações; nav_per_share nos demais, mais o "
    "preço) e, nos fundos, sector/industry = estrutura/segmento (Tijolo, Papel...). "
    "Um --valuation-score explícito tem precedência. Se nenhum método produz valor "
    "(ex.: fixed_income sem preço de mercado), fica neutro (5.0) e o motivo é mostrado.",
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
    auto_valuation: bool,
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
        # falha ao gravar no vault não deve impedir a análise em si de ser exibida
        except Exception as exc:  # noqa: BLE001
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

        if auto_valuation and valuation_score is None:
            valuation_score = _auto_valuation_score(
                symbol, asset_type, raw, data.price, data.financials
            )
        elif auto_valuation:
            console.print(
                "[dim]--auto-valuation ignorado: --valuation-score explícito tem precedência.[/]"
            )

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
                # data de calendário (data da decisão), não timestamp
                decision_id=f"DEC-{symbol.upper()}-{_dt.date.today().isoformat()}",  # noqa: DTZ011
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
@click.option(
    "--ticker", required=True, help="Ticker do ativo que essa evidência sustenta."
)
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
        # data de calendário (data da evidência), não timestamp
        data_evidencia = _dt.date.today()  # noqa: DTZ011

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


@cli.command("collect-sparta-history")
@click.option(
    "--ticker",
    default="CRAA11",
    help="Ticker de um fundo Sparta (ex.: CRAA11, JURO11, CDII11).",
)
@click.option(
    "--desde",
    default="2025-01",
    help="Mês inicial YYYY-MM (padrão: 2025-01, primeiro mês confirmado "
    "disponível no site da Sparta -- ver iip.sources.sparta_reports).",
)
@click.option(
    "--ate",
    default=None,
    help="Mês final YYYY-MM (padrão: mês atual).",
)
@click.option(
    "--vault",
    type=click.Path(),
    default=None,
    help="Caminho do vault Obsidian (padrão: IIP_OBSIDIAN_VAULT).",
)
@click.option(
    "--sem-evidencia",
    is_flag=True,
    default=False,
    help="Não persiste evidência Atlas no vault, só a série histórica em "
    "02_Portfolio/Historical.",
)
def collect_sparta_history_command(
    ticker: str, desde: str, ate: str | None, vault: str | None, sem_evidencia: bool
) -> None:
    """Coleta e persiste o histórico de cota patrimonial de um fundo
    Sparta a partir dos relatórios mensais em PDF do próprio site
    (``iip.sources.sparta_reports``).

    Motivado pelo CRAA11 (Sparta Fiagro): confirmado que seu CNPJ não
    aparece no dataset FIAGRO aberto da CVM (ver o aviso de
    ``iip analyze-portfolio``/``fetch-template --type fiagro`` para
    esse ticker), então esse fundo fica sem patrimônio/cota via CVM.
    Este comando busca a mesma informação direto do relatório gerencial
    da própria gestora -- a única fonte real encontrada para esse gap.

    Um mês cujo relatório ainda não foi publicado (404) ou cujo layout
    de PDF não bate com o esperado é registrado como não-casado e
    pulado, nunca inventado -- ver a tabela de saída.
    """
    import datetime as _dt

    from iip.knowledge.bridge import KnowledgeBridge
    from iip.portfolio.historical_series import (
        HistoricalSeriesStore,
        collect_sparta_report_history,
    )

    def _parse_year_month(value: str, label: str) -> tuple[int, int]:
        try:
            ano_str, mes_str = value.split("-", 1)
            ano, mes = int(ano_str), int(mes_str)
            if not (1 <= mes <= 12):
                raise ValueError
            return ano, mes
        except ValueError as exc:
            console.print(f"[bold red]{label} precisa ser YYYY-MM, recebi: {value}[/]")
            raise SystemExit(1) from exc

    ano_inicio, mes_inicio = _parse_year_month(desde, "--desde")
    if ate:
        ano_fim, mes_fim = _parse_year_month(ate, "--ate")
    else:
        # data de calendário (mês de referência padrão), não timestamp
        hoje = _dt.date.today()  # noqa: DTZ011
        ano_fim, mes_fim = hoje.year, hoje.month

    if (ano_inicio, mes_inicio) > (ano_fim, mes_fim):
        console.print("[bold red]--desde não pode ser depois de --ate.[/]")
        raise SystemExit(1)

    year_months: list[tuple[int, int]] = []
    ano, mes = ano_inicio, mes_inicio
    while (ano, mes) <= (ano_fim, mes_fim):
        year_months.append((ano, mes))
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    vault_path = vault or str(get_settings().obsidian_vault)
    store = HistoricalSeriesStore(vault_path)
    bridge = None if sem_evidencia else KnowledgeBridge(vault_path)

    console.print(
        f"[dim]Coletando histórico Sparta para {ticker.upper()} "
        f"({year_months[0][0]:04d}-{year_months[0][1]:02d} a "
        f"{year_months[-1][0]:04d}-{year_months[-1][1]:02d})...[/]\n"
    )

    series = collect_sparta_report_history(
        ticker, tuple(year_months), store=store, bridge=bridge
    )

    observations_by_period = {o.period: o for o in series.observations}

    table = Table(title=f"Histórico Sparta — {series.ticker}")
    table.add_column("Período")
    table.add_column("Cota patrimonial")
    table.add_column("Status")

    for doc in series.source_documents:
        periodo = f"{doc['ano']:04d}-{doc['mes']:02d}"
        observation = observations_by_period.get(f"{periodo}-01")
        if observation is not None:
            table.add_row(
                periodo, f"R$ {observation.valor_patrimonial_cotas:.2f}", "[green]ok[/]"
            )
        else:
            motivo = doc.get("error", "layout do PDF não reconhecido")
            table.add_row(periodo, "-", f"[yellow]{motivo}[/]")

    console.print(table)
    console.print(
        f"\n[green]{len(series.observations)} observação(ões)[/] salva(s) em "
        f"{store.path_for(series.ticker)}"
    )
    if bridge is not None:
        console.print("[dim]Evidência Atlas persistida no vault (04_Evidence).[/]")


@cli.command("collect-patria-documents")
@click.option(
    "--ticker",
    required=True,
    help="Fundo Pátria com config MZIQ registrada: HGRU11, LVBI11, HGCR11, "
    "PVBI11 ou PCIP11.",
)
@click.option(
    "--ano",
    type=int,
    default=None,
    help="Ano dos documentos (padrão: ano mais recente disponível).",
)
@click.option(
    "--categoria",
    multiple=True,
    help="Filtra por categoria(s) MZIQ (ex.: lvbi11_relatorio_de_gestao). "
    "Pode repetir. Padrão: todas as categorias do fundo.",
)
@click.option(
    "--limite",
    type=int,
    default=None,
    help="Baixa só os N primeiros documentos encontrados (útil pra "
    "teste/preview antes de rodar sem limite).",
)
@click.option(
    "--vault",
    type=click.Path(),
    default=None,
    help="Caminho do vault Obsidian (padrão: IIP_OBSIDIAN_VAULT).",
)
@click.option(
    "--sem-evidencia",
    is_flag=True,
    default=False,
    help="Não persiste evidência Atlas no vault -- só lista/baixa os documentos.",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Diretório onde também salvar uma cópia dos arquivos baixados "
    "(padrão: não salva cópia local além da evidência no vault).",
)
def collect_patria_documents_command(
    ticker: str,
    ano: int | None,
    categoria: tuple[str, ...],
    limite: int | None,
    vault: str | None,
    sem_evidencia: bool,
    output_dir: str | None,
) -> None:
    """Lista e baixa documentos reais de um fundo da Pátria via MZIQ
    (``iip.sources.patria_mziq``) -- alternativa leve (HTTP puro, sem
    Playwright) ao scraper de navegador ``iip.harvest.patria``.

    Não busca NAV/cota patrimonial de propósito: o PDF "Informe Mensal
    Estruturado" de cada fundo é a mesma informação regulatória que
    ``iip refresh-portfolio``/CVM já cobrem -- ver o docstring de
    ``iip.sources.patria_mziq`` para a confirmação. Isso aqui é pra
    documentos que a CVM não replica (relatório de gestão, fatos
    relevantes, apresentações etc.).
    """
    from iip.sources import patria_mziq

    _collect_mziq_manager_documents(
        manager_label="Pátria",
        provider_name="patria_mziq",
        fund_module=patria_mziq,
        funds_registry=patria_mziq.PATRIA_MZIQ_FUNDS,
        ticker=ticker,
        ano=ano,
        categoria=categoria,
        limite=limite,
        vault=vault,
        sem_evidencia=sem_evidencia,
        output_dir=output_dir,
    )


@cli.command("collect-btg-documents")
@click.option(
    "--ticker",
    required=True,
    help="Fundo BTG Pactual com config MZIQ registrada: hoje só BTLG11 "
    "(BTCI11 está numa plataforma diferente, ainda não investigada).",
)
@click.option(
    "--ano",
    type=int,
    default=None,
    help="Ano dos documentos (padrão: ano mais recente disponível).",
)
@click.option(
    "--categoria",
    multiple=True,
    help="Filtra por categoria(s) MZIQ (ex.: relatorios_gerenciais). "
    "Pode repetir. Padrão: todas as categorias do fundo.",
)
@click.option(
    "--limite",
    type=int,
    default=None,
    help="Baixa só os N primeiros documentos encontrados (útil pra "
    "teste/preview antes de rodar sem limite).",
)
@click.option(
    "--vault",
    type=click.Path(),
    default=None,
    help="Caminho do vault Obsidian (padrão: IIP_OBSIDIAN_VAULT).",
)
@click.option(
    "--sem-evidencia",
    is_flag=True,
    default=False,
    help="Não persiste evidência Atlas no vault -- só lista/baixa os documentos.",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Diretório onde também salvar uma cópia dos arquivos baixados "
    "(padrão: não salva cópia local além da evidência no vault).",
)
def collect_btg_documents_command(
    ticker: str,
    ano: int | None,
    categoria: tuple[str, ...],
    limite: int | None,
    vault: str | None,
    sem_evidencia: bool,
    output_dir: str | None,
) -> None:
    """Lista e baixa documentos reais de um fundo da BTG Pactual via MZIQ
    (``iip.sources.btg_mziq``) -- mesma abordagem leve do
    ``collect-patria-documents``, aplicada à BTLG11.

    Confirmado ao vivo só pra BTLG11: seu company_id/categorias MZIQ
    estão expostos direto no HTML estático da própria página, sem
    precisar de Playwright nem pra descoberta. BTCI11 (o outro fundo da
    BTG na carteira) está numa plataforma diferente (Astro, não MZIQ) e
    ainda não foi investigado -- ver ``iip.sources.btg_mziq`` docstring.
    """
    from iip.sources import btg_mziq

    _collect_mziq_manager_documents(
        manager_label="BTG",
        provider_name="btg_mziq",
        fund_module=btg_mziq,
        funds_registry=btg_mziq.BTG_MZIQ_FUNDS,
        ticker=ticker,
        ano=ano,
        categoria=categoria,
        limite=limite,
        vault=vault,
        sem_evidencia=sem_evidencia,
        output_dir=output_dir,
    )


@cli.command("collect-investo-documents")
@click.option(
    "--ticker",
    required=True,
    help="ETF da Investo com config MZIQ registrada: hoje só LFTB11.",
)
@click.option(
    "--ano",
    type=int,
    default=None,
    help="Ano dos documentos (padrão: ano mais recente disponível). "
    "Os documentos do LFTB11 estão em 2025 e 2024: rode uma vez por ano.",
)
@click.option(
    "--categoria",
    multiple=True,
    help="Filtra por categoria(s) MZIQ (ex.: LFTB11_Regulamento). "
    "Pode repetir. Padrão: todas as categorias do fundo.",
)
@click.option(
    "--limite",
    type=int,
    default=None,
    help="Baixa só os N primeiros documentos encontrados (útil pra "
    "teste/preview antes de rodar sem limite).",
)
@click.option(
    "--vault",
    type=click.Path(),
    default=None,
    help="Caminho do vault Obsidian (padrão: IIP_OBSIDIAN_VAULT).",
)
@click.option(
    "--sem-evidencia",
    is_flag=True,
    default=False,
    help="Não persiste evidência Atlas no vault -- só lista/baixa os documentos.",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Diretório onde também salvar uma cópia dos arquivos baixados "
    "(padrão: não salva cópia local além da evidência no vault).",
)
def collect_investo_documents_command(
    ticker: str,
    ano: int | None,
    categoria: tuple[str, ...],
    limite: int | None,
    vault: str | None,
    sem_evidencia: bool,
    output_dir: str | None,
) -> None:
    """Lista e baixa os documentos de um ETF da Investo via MZIQ
    (``iip.sources.investo_mziq``): regulamento, índice, tributação,
    fatores de risco, comunicados e "as cotas". Mesma abordagem do
    ``collect-btg-documents``; confirmado ao vivo só pro LFTB11."""
    from iip.sources import investo_mziq

    _collect_mziq_manager_documents(
        manager_label="Investo",
        provider_name="investo_mziq",
        fund_module=investo_mziq,
        funds_registry=investo_mziq.INVESTO_MZIQ_FUNDS,
        ticker=ticker,
        ano=ano,
        categoria=categoria,
        limite=limite,
        vault=vault,
        sem_evidencia=sem_evidencia,
        output_dir=output_dir,
    )


@cli.command("etf-composition")
@click.option("--ticker", required=True, help="ETF de renda fixa da carteira (LFTB11).")
@click.option(
    "--persist",
    is_flag=True,
    default=False,
    help="Grava a seção IIP:portfolio_composition na nota 'Carteira e Crédito' do ativo "
    "no vault. Sem esta opção só mostra.",
)
@click.option(
    "--vault",
    type=click.Path(),
    default=None,
    help="Caminho do vault Obsidian (padrão: IIP_OBSIDIAN_VAULT). Só usado com --persist.",
)
def etf_composition_command(ticker: str, persist: bool, vault: str | None) -> None:
    """Mostra a composição da carteira de um ETF de renda fixa, lida da CDA da CVM
    (``iip.sources.cvm_cda_etf``): peso por vencimento, prazo médio e o que vence em mais
    de 10 anos. Só descreve; não entra em score nem valuation."""
    from iip.portfolio.etf_composition import default_fetch_etf_cda, render_composition
    from iip.portfolio.registry import get_asset
    from iip.sources.cvm_cda import CdaError

    symbol = ticker.strip().upper()
    asset = get_asset(symbol)
    if asset is None or asset.subtype != "ETF Renda Fixa" or not asset.cnpj:
        console.print(
            f"[bold red]{symbol} não é um ETF de renda fixa com CNPJ no registro.[/]"
        )
        raise SystemExit(1)

    try:
        fetched = default_fetch_etf_cda(asset.cnpj)
    except CdaError as exc:
        console.print(f"[bold red]Não consegui ler a carteira de {symbol}:[/] {exc}")
        raise SystemExit(1) from exc

    content = render_composition(fetched.portfolio, fetched.url)
    console.print(content, markup=False, highlight=False)

    if persist:
        from iip.knowledge.bridge import KnowledgeBridge

        vault_path = vault or str(get_settings().obsidian_vault)
        result = KnowledgeBridge(vault_path).sync_asset_section(
            symbol, "etf", "portfolio", "IIP:portfolio_composition", content
        )
        console.print(f"[dim]Vault: {result.status.value} — {result.path}[/]")


@cli.command("collect-equity-documents")
@click.option(
    "--ticker",
    required=True,
    help="Ação com config MZIQ registrada: ABCB4, BBSE3, CXSE3, SAUD3, "
    "ALOS3, VBBR3, KLBN4, FESA4, LEVE3 ou PASS3.",
)
@click.option(
    "--ano",
    type=int,
    default=None,
    help="Ano dos documentos (padrão: ano mais recente disponível).",
)
@click.option(
    "--categoria",
    multiple=True,
    help="Filtra por categoria(s) MZIQ (ex.: central-resultados-earnings-release). "
    "Pode repetir. Padrão: todas as categorias da empresa.",
)
@click.option(
    "--limite",
    type=int,
    default=None,
    help="Baixa só os N primeiros documentos encontrados (útil pra "
    "teste/preview antes de rodar sem limite).",
)
@click.option(
    "--vault",
    type=click.Path(),
    default=None,
    help="Caminho do vault Obsidian (padrão: IIP_OBSIDIAN_VAULT).",
)
@click.option(
    "--sem-evidencia",
    is_flag=True,
    default=False,
    help="Não persiste evidência Atlas no vault -- só lista/baixa os documentos.",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Diretório onde também salvar uma cópia dos arquivos baixados "
    "(padrão: não salva cópia local além da evidência no vault).",
)
def collect_equity_documents_command(
    ticker: str,
    ano: int | None,
    categoria: tuple[str, ...],
    limite: int | None,
    vault: str | None,
    sem_evidencia: bool,
    output_dir: str | None,
) -> None:
    """Lista e baixa documentos reais de RI de uma ação via MZIQ
    (``iip.sources.equity_mziq``) -- mesma abordagem leve dos comandos
    `collect-patria-documents`/`collect-btg-documents`, cobrindo 10 das
    14 ações da carteira confirmadas na plataforma MZIQ (as outras 4 --
    ISAE4, CPFE3, CMIG4, CSUD3 -- usam plataformas de RI diferentes,
    ver docstring de ``iip.sources.equity_mziq``).
    """
    from iip.sources import equity_mziq

    _collect_mziq_manager_documents(
        manager_label="Equity",
        provider_name="equity_mziq",
        fund_module=equity_mziq,
        funds_registry=equity_mziq.EQUITY_MZIQ_COMPANIES,
        ticker=ticker,
        ano=ano,
        categoria=categoria,
        limite=limite,
        vault=vault,
        sem_evidencia=sem_evidencia,
        output_dir=output_dir,
    )


def _collect_mziq_manager_documents(
    *,
    manager_label: str,
    provider_name: str,
    fund_module: Any,
    funds_registry: dict[str, Any],
    ticker: str,
    ano: int | None,
    categoria: tuple[str, ...],
    limite: int | None,
    vault: str | None,
    sem_evidencia: bool,
    output_dir: str | None,
) -> None:
    """Shared implementation behind collect-patria-documents and
    collect-btg-documents -- both wrap the same MZIQ document-catalog
    protocol (``iip.sources.mziq``), differing only in which manager's
    static fund-config module (``fund_for_ticker``/``build_years_target``/
    ``build_documents_target``) they look tickers up in."""
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from iip.atlas.knowledge_adapter import AtlasKnowledgeAdapter
    from iip.atlas.models import AtlasDocument
    from iip.knowledge.bridge import KnowledgeBridge
    from iip.sources.mziq_harvester import MziqHTTPHarvester

    normalized_ticker = ticker.strip().upper()
    if fund_module.fund_for_ticker(normalized_ticker) is None:
        console.print(
            f"[bold red]Sem config MZIQ registrada para {normalized_ticker}.[/] "
            f"Fundos disponíveis: {', '.join(sorted(funds_registry)) or '(nenhum)'}"
        )
        raise SystemExit(1)

    harvester = MziqHTTPHarvester()

    ano_efetivo = ano
    if ano_efetivo is None:
        anos = harvester.fetch_years(fund_module.build_years_target(normalized_ticker))
        if not anos:
            console.print(
                f"[bold red]Nenhum ano disponível via MZIQ para {normalized_ticker}.[/]"
            )
            raise SystemExit(1)
        ano_efetivo = max(anos)

    console.print(
        f"[dim]Buscando documentos de {normalized_ticker} ({ano_efetivo})...[/]\n"
    )

    documents = harvester.fetch_documents(
        fund_module.build_documents_target(normalized_ticker, ano_efetivo)
    )
    if categoria:
        wanted = set(categoria)
        documents = tuple(d for d in documents if d.category in wanted)
    if limite is not None:
        documents = documents[:limite]

    vault_path = vault or str(get_settings().obsidian_vault)
    bridge = None if sem_evidencia else KnowledgeBridge(vault_path)
    out_dir = (
        Path(output_dir) / normalized_ticker / str(ano_efetivo) if output_dir else None
    )
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    table = Table(
        title=f"Documentos {manager_label}/MZIQ — {normalized_ticker} ({ano_efetivo})"
    )
    table.add_column("Categoria")
    table.add_column("Título")
    table.add_column("Status")

    baixados = 0
    for document in documents:
        if not document.url:
            table.add_row(
                document.category or "-",
                document.file_title or "-",
                "[yellow]sem URL[/]",
            )
            continue
        try:
            request = Request(
                document.url, headers={"User-Agent": "IIP-D-OBSIDIAN/1.0"}
            )
            # URL vem da própria API MZIQ, não de entrada externa
            with urlopen(request, timeout=30.0) as response:  # noqa: S310
                body = response.read()
                content_type = response.headers.get(
                    "Content-Type", "application/octet-stream"
                )
        except HTTPError as exc:
            table.add_row(
                document.category or "-",
                document.file_title or "-",
                f"[red]HTTP {exc.code}[/]",
            )
            continue
        # hospedagens variadas (arquivo truncado, timeout, SSL); um documento ruim não deve abortar a coleta inteira
        except Exception as exc:  # noqa: BLE001
            table.add_row(
                document.category or "-",
                document.file_title or "-",
                f"[red]{type(exc).__name__}[/]",
            )
            continue

        if out_dir is not None:
            suffix = Path(document.url.split("?", 1)[0]).suffix or ".bin"
            filename = (
                f"{document.id}{suffix}" if document.id else f"{baixados}{suffix}"
            )
            (out_dir / filename).write_bytes(body)

        if bridge is not None:
            atlas_document = AtlasDocument.build(
                ticker=normalized_ticker,
                provider=provider_name,
                role=document.category or "investor_relations_document",
                url=document.url,
                final_url=document.url,
                content_type=content_type,
                status_code=200,
                body=body,
                discovered_year=document.file_year or ano_efetivo,
                title=document.file_title or document.file_name_original,
            )
            evidence = AtlasKnowledgeAdapter.to_evidence(atlas_document)
            try:
                bridge.persist_evidence(evidence)
            except FileExistsError:
                pass

        baixados += 1
        table.add_row(
            document.category or "-", document.file_title or "-", "[green]ok[/]"
        )

    console.print(table)
    console.print(
        f"\n[green]{baixados}/{len(documents)} documento(s)[/] baixado(s) com sucesso."
    )
    if out_dir is not None:
        console.print(f"[dim]Cópias salvas em {out_dir}[/]")
    if bridge is not None:
        console.print("[dim]Evidência Atlas persistida no vault (04_Evidence).[/]")


@cli.command("collect-static-documents")
@click.option(
    "--ticker",
    required=True,
    help="Ativo com listagem de documentos em HTML estático: os fundos TRXF11, "
    "VGIP11, CPTI11, MANA11, RBVA11, HGBS11 e KNRI11, e as empresas ISAE4 e CMIG4.",
)
@click.option(
    "--anos-historico",
    type=int,
    default=3,
    show_default=True,
    help="Só para quem tem seletor de ano na página (ISAE4, CMIG4): quantos anos, contando o "
    "corrente, buscar. Os fundos listam tudo numa página e ignoram esta opção.",
)
@click.option(
    "--limite",
    type=int,
    default=None,
    help="Baixa só os N primeiros documentos encontrados na página "
    "(útil pra teste/preview -- RBVA11 sozinho tem ~1200 documentos).",
)
@click.option(
    "--vault",
    type=click.Path(),
    default=None,
    help="Caminho do vault Obsidian (padrão: IIP_OBSIDIAN_VAULT).",
)
@click.option(
    "--sem-evidencia",
    is_flag=True,
    default=False,
    help="Não persiste evidência Atlas no vault -- só lista/baixa os documentos.",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Diretório onde também salvar uma cópia dos arquivos baixados "
    "(padrão: não salva cópia local além da evidência no vault).",
)
def collect_static_documents_command(
    ticker: str,
    anos_historico: int,
    limite: int | None,
    vault: str | None,
    sem_evidencia: bool,
    output_dir: str | None,
) -> None:
    """Lista e baixa documentos reais de fundos cuja gestora expõe tudo
    como links PDF diretos em HTML estático
    (``iip.sources.static_pdf_listing``) -- nem API, nem Playwright,
    só um GET na página de documentos do próprio fundo.

    Cobre os 7 gestores que sobraram sem nenhum adapter (TRX, Valora,
    Capitânia, Manati, Rio Bravo, Hedge, Kinea) -- ao contrário da
    Pátria/BTG (plataforma MZIQ), nenhum desses usa uma API JSON; o
    HTML da própria página já lista todos os PDFs.

    Como os outros comandos `collect-*-documents`, não busca NAV/cota
    patrimonial de propósito -- todos os 7 fundos aqui são FII com
    CNPJ verificado, então a CVM (``iip.sources.cvm_fii``) já cobre
    isso. Isso é só pra documentos que a CVM não replica.
    """
    import re
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from iip.atlas.knowledge_adapter import AtlasKnowledgeAdapter
    from iip.atlas.models import AtlasDocument
    from iip.knowledge.bridge import KnowledgeBridge
    from iip.sources.static_pdf_listing import (
        STATIC_PDF_LISTING_FUNDS,
        fund_for_ticker,
    )
    from iip.sources.static_pdf_listing_harvester import StaticPdfListingHTTPHarvester

    normalized_ticker = ticker.strip().upper()
    fund = fund_for_ticker(normalized_ticker)
    if fund is None:
        console.print(
            f"[bold red]Sem config de listagem estática para {normalized_ticker}.[/] "
            f"Fundos disponíveis: {', '.join(sorted(STATIC_PDF_LISTING_FUNDS))}"
        )
        raise SystemExit(1)

    console.print(
        f"[dim]Buscando página de documentos de {normalized_ticker} "
        f"({fund.page_url})...[/]\n"
    )

    import datetime as _dt

    # ano de calendário (histórico de documentos), não timestamp
    this_year = _dt.date.today().year  # noqa: DTZ011
    harvester = StaticPdfListingHTTPHarvester()
    documents = harvester.collect(
        normalized_ticker,
        years=tuple(range(this_year, this_year - max(anos_historico, 1), -1)),
    )
    for problem in harvester.last_errors:
        console.print(f"[yellow]Aviso: página ignorada — {problem}[/]")
    if limite is not None:
        documents = documents[:limite]

    vault_path = vault or str(get_settings().obsidian_vault)
    bridge = None if sem_evidencia else KnowledgeBridge(vault_path)
    out_dir = Path(output_dir) / normalized_ticker if output_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    table = Table(title=f"Documentos {fund.manager} — {normalized_ticker}")
    table.add_column("Título")
    table.add_column("Status")

    baixados = 0
    for document in documents:
        try:
            request = Request(
                document.url, headers={"User-Agent": "IIP-D-OBSIDIAN/1.0"}
            )
            # URL vem da própria página do fundo, não de entrada externa
            with urlopen(request, timeout=30.0) as response:  # noqa: S310
                body = response.read()
                content_type = response.headers.get("Content-Type", "application/pdf")
        except HTTPError as exc:
            table.add_row(document.title, f"[red]HTTP {exc.code}[/]")
            continue
        # hospedagens variadas (timeout, SSL, DNS); um documento ruim não deve abortar a coleta inteira
        except Exception as exc:  # noqa: BLE001
            table.add_row(document.title, f"[red]{type(exc).__name__}[/]")
            continue

        if out_dir is not None:
            suffix = Path(document.url.split("?", 1)[0]).suffix or ".pdf"
            safe_name = re.sub(r"[^\w.-]", "_", document.title)[:150]
            (out_dir / f"{safe_name}{suffix}").write_bytes(body)

        if bridge is not None:
            atlas_document = AtlasDocument.build(
                ticker=normalized_ticker,
                provider="static_pdf_listing",
                role="investor_relations_document",
                url=document.url,
                final_url=document.url,
                content_type=content_type,
                status_code=200,
                body=body,
                discovered_year=None,
                title=document.title,
            )
            evidence = AtlasKnowledgeAdapter.to_evidence(atlas_document)
            try:
                bridge.persist_evidence(evidence)
            except FileExistsError:
                pass

        baixados += 1
        table.add_row(document.title, "[green]ok[/]")

    console.print(table)
    console.print(
        f"\n[green]{baixados}/{len(documents)} documento(s)[/] baixado(s) com sucesso."
    )
    if out_dir is not None:
        console.print(f"[dim]Cópias salvas em {out_dir}[/]")
    if bridge is not None:
        console.print("[dim]Evidência Atlas persistida no vault (04_Evidence).[/]")


@cli.command("collect-solutions-ir-documents")
@click.option(
    "--ticker",
    required=True,
    help="Ativo com config Solutions IR registrada: BTCI11 (fundo) e CSUD3 (empresa).",
)
@click.option(
    "--categoria",
    multiple=True,
    help="Filtra por sigla de categoria (ex.: RM, INFOMEN, ATA). Pode "
    "repetir. Padrão: todas as categorias.",
)
@click.option(
    "--ano",
    type=int,
    default=None,
    help="Filtra por ano (ex.: 2026). Padrão: todos os anos disponíveis.",
)
@click.option(
    "--limite",
    type=int,
    default=None,
    help="Baixa só os N primeiros documentos encontrados (útil pra "
    "teste/preview -- BTCI11 sozinho tem ~800 documentos).",
)
@click.option(
    "--anos-historico",
    type=int,
    default=3,
    show_default=True,
    help="Só para empresas (ex.: CSUD3): quantos anos, contando o corrente, buscar "
    "-- a API devolve um ano por chamada. Fundos (BTCI11) ignoram: vêm de uma vez.",
)
@click.option(
    "--incluir-midia",
    is_flag=True,
    default=False,
    help="Também baixa áudio e vídeo (mp3/mp4...). Por padrão são pulados: são pesados "
    "e não viram evidência textual.",
)
@click.option(
    "--vault",
    type=click.Path(),
    default=None,
    help="Caminho do vault Obsidian (padrão: IIP_OBSIDIAN_VAULT).",
)
@click.option(
    "--sem-evidencia",
    is_flag=True,
    default=False,
    help="Não persiste evidência Atlas no vault -- só lista/baixa os documentos.",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Diretório onde também salvar uma cópia dos arquivos baixados "
    "(padrão: não salva cópia local além da evidência no vault).",
)
def collect_solutions_ir_documents_command(
    ticker: str,
    categoria: tuple[str, ...],
    ano: int | None,
    limite: int | None,
    anos_historico: int,
    incluir_midia: bool,
    vault: str | None,
    sem_evidencia: bool,
    output_dir: str | None,
) -> None:
    """Lista e baixa documentos reais via a API da plataforma "Solutions
    IR" (``iip.sources.solutions_ir``) -- fecha o gap do BTCI11, o
    único ativo da carteira sem nenhum provider de documentos até
    agora (ver docstring do módulo para como o endpoint real foi
    encontrado: a página é um app Astro sem MZIQ e bloqueou o
    Playwright ativamente; a URL da API veio de leitura estática do
    bundle JS da própria página, nunca de execução de navegador).

    Diferente do MZIQ, essa API não pagina por ano/categoria -- devolve
    tudo numa resposta só (confirmado: 803 documentos reais pro
    BTCI11), então os filtros aqui (--categoria/--ano) são aplicados
    localmente sobre a resposta completa.
    """
    import re
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from iip.atlas.knowledge_adapter import AtlasKnowledgeAdapter
    from iip.atlas.models import AtlasDocument
    from iip.knowledge.bridge import KnowledgeBridge
    from iip.sources.solutions_ir import (
        SOLUTIONS_IR_COMPANIES,
        company_for_ticker,
    )
    from iip.sources.solutions_ir_harvester import SolutionsIrHTTPHarvester

    normalized_ticker = ticker.strip().upper()
    if company_for_ticker(normalized_ticker) is None:
        console.print(
            f"[bold red]Sem config Solutions IR registrada para {normalized_ticker}.[/] "
            f"Ativos disponíveis: {', '.join(sorted(SOLUTIONS_IR_COMPANIES))}"
        )
        raise SystemExit(1)

    console.print(
        f"[dim]Buscando documentos de {normalized_ticker} via Solutions IR...[/]\n"
    )

    import datetime as _dt

    # ano de calendário (histórico de documentos), não timestamp
    this_year = _dt.date.today().year  # noqa: DTZ011
    documents = SolutionsIrHTTPHarvester().collect(
        normalized_ticker,
        years=tuple(range(this_year, this_year - max(anos_historico, 1), -1)),
    )
    if not incluir_midia:
        media = {".mp3", ".mp4", ".wav", ".m4a", ".mov", ".avi"}
        documents = tuple(
            d
            for d in documents
            if Path(d.url.split("?", 1)[0]).suffix.lower() not in media
        )
    if categoria:
        wanted = set(categoria)
        documents = tuple(d for d in documents if d.category_sigla in wanted)
    if ano is not None:
        documents = tuple(d for d in documents if d.year == str(ano))
    if limite is not None:
        documents = documents[:limite]

    vault_path = vault or str(get_settings().obsidian_vault)
    bridge = None if sem_evidencia else KnowledgeBridge(vault_path)
    out_dir = Path(output_dir) / normalized_ticker if output_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    table = Table(title=f"Documentos Solutions IR — {normalized_ticker}")
    table.add_column("Categoria")
    table.add_column("Ano")
    table.add_column("Título")
    table.add_column("Status")

    baixados = 0
    for document in documents:
        try:
            request = Request(
                document.url, headers={"User-Agent": "IIP-D-OBSIDIAN/1.0"}
            )
            # URL vem da própria API Solutions IR, não de entrada externa
            with urlopen(request, timeout=30.0) as response:  # noqa: S310
                body = response.read()
                content_type = response.headers.get("Content-Type", "application/pdf")
        except HTTPError as exc:
            table.add_row(
                document.category_sigla,
                document.year,
                document.title,
                f"[red]HTTP {exc.code}[/]",
            )
            continue
        # hospedagem estática de terceiro (static.btgpactual.com); um documento ruim não deve abortar a coleta inteira
        except Exception as exc:  # noqa: BLE001
            table.add_row(
                document.category_sigla,
                document.year,
                document.title,
                f"[red]{type(exc).__name__}[/]",
            )
            continue

        if out_dir is not None:
            suffix = Path(document.url.split("?", 1)[0]).suffix or ".pdf"
            safe_name = re.sub(r"[^\w.-]", "_", document.title)[:150]
            (out_dir / f"{safe_name}{suffix}").write_bytes(body)

        if bridge is not None:
            atlas_document = AtlasDocument.build(
                ticker=normalized_ticker,
                provider="solutions_ir",
                role=document.category_sigla or "investor_relations_document",
                url=document.url,
                final_url=document.url,
                content_type=content_type,
                status_code=200,
                body=body,
                discovered_year=int(document.year) if document.year.isdigit() else None,
                title=document.title,
            )
            evidence = AtlasKnowledgeAdapter.to_evidence(atlas_document)
            try:
                bridge.persist_evidence(evidence)
            except FileExistsError:
                pass

        baixados += 1
        table.add_row(
            document.category_sigla, document.year, document.title, "[green]ok[/]"
        )

    console.print(table)
    console.print(
        f"\n[green]{baixados}/{len(documents)} documento(s)[/] baixado(s) com sucesso."
    )
    if out_dir is not None:
        console.print(f"[dim]Cópias salvas em {out_dir}[/]")
    if bridge is not None:
        console.print("[dim]Evidência Atlas persistida no vault (04_Evidence).[/]")


@cli.command("collect-cpfl-documents")
@click.option(
    "--anos-historico",
    type=int,
    default=3,
    show_default=True,
    help="Quantos anos, contando o corrente, coletar (a página lista de 2002 até hoje).",
)
@click.option(
    "--incluir-midia",
    is_flag=True,
    default=False,
    help="Também baixa áudio e vídeo das conferências. Por padrão são pulados: são "
    "pesados e não viram evidência textual.",
)
@click.option(
    "--limite",
    type=int,
    default=None,
    help="Baixa só os N primeiros documentos (útil pra teste/preview).",
)
@click.option(
    "--vault",
    type=click.Path(),
    default=None,
    help="Caminho do vault Obsidian (padrão: IIP_OBSIDIAN_VAULT).",
)
@click.option(
    "--sem-evidencia",
    is_flag=True,
    default=False,
    help="Não persiste evidência Atlas no vault -- só lista/baixa os documentos.",
)
def collect_cpfl_documents_command(
    anos_historico: int,
    incluir_midia: bool,
    limite: int | None,
    vault: str | None,
    sem_evidencia: bool,
) -> None:
    """Lista e baixa documentos reais do RI da CPFL Energia (CPFE3) — Release
    e Apresentação de Resultados, Demonstrações Financeiras, transcrições —
    do CMS legado ``ri.cpfl.com.br`` (``iip.sources.cpfl_ri``): a "Central de
    Resultados" traz todos os anos numa página e cada arquivo sai de
    ``Download.aspx``, com HTTP simples, sem navegador.
    """
    import datetime as _dt
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from iip.atlas.knowledge_adapter import AtlasKnowledgeAdapter
    from iip.atlas.models import AtlasDocument
    from iip.knowledge.bridge import KnowledgeBridge
    from iip.sources.cpfl_ri_harvester import CpflRiHTTPHarvester

    console.print(
        "[dim]Buscando a Central de Resultados de CPFE3 (ri.cpfl.com.br)...[/]\n"
    )
    documents = CpflRiHTTPHarvester().fetch().documents
    # ano de calendário (histórico de documentos), não timestamp
    first_year = _dt.date.today().year - max(anos_historico, 1) + 1  # noqa: DTZ011
    documents = tuple(d for d in documents if d.year >= first_year)
    if not incluir_midia:
        documents = tuple(d for d in documents if not d.is_media)
    if limite is not None:
        documents = documents[:limite]

    vault_path = vault or str(get_settings().obsidian_vault)
    bridge = None if sem_evidencia else KnowledgeBridge(vault_path)

    table = Table(title="Documentos RI — CPFE3 (CPFL Energia)")
    table.add_column("Título")
    table.add_column("Status")

    baixados = 0
    for document in documents:
        try:
            request = Request(
                document.url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; IIP-D-OBSIDIAN/1.0)"},
            )
            # URL vem da própria Central de Resultados do RI, não de entrada externa
            with urlopen(request, timeout=60.0) as response:  # noqa: S310
                body = response.read()
                content_type = response.headers.get("Content-Type", "application/pdf")
        except HTTPError as exc:
            table.add_row(document.title, f"[red]HTTP {exc.code}[/]")
            continue
        # um documento ruim não deve abortar a coleta inteira
        except Exception as exc:  # noqa: BLE001
            table.add_row(document.title, f"[red]{type(exc).__name__}[/]")
            continue

        if bridge is not None:
            atlas_document = AtlasDocument.build(
                ticker="CPFE3",
                provider="cpfl_ri",
                role="investor_relations_document",
                url=document.url,
                final_url=document.url,
                content_type=content_type,
                status_code=200,
                body=body,
                discovered_year=document.year,
                title=document.title,
            )
            evidence = AtlasKnowledgeAdapter.to_evidence(atlas_document)
            try:
                bridge.persist_evidence(evidence)
            except FileExistsError:
                pass

        baixados += 1
        table.add_row(document.title, "[green]ok[/]")

    console.print(table)
    console.print(
        f"\n[green]{baixados}/{len(documents)} documento(s)[/] baixado(s) com sucesso."
    )
    if bridge is not None:
        console.print("[dim]Evidência Atlas persistida no vault (04_Evidence).[/]")


if __name__ == "__main__":
    cli()
