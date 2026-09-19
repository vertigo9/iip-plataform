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

    Equity: preenche price/market_cap/dividend_yield (via bolsai/brapi)
    e, desde 18/09/2026, também equity/net_income/revenue/ebit/
    invested_capital/crescimento 3y a partir da DFP real da CVM (ver
    ``iip.sources.cvm_dfp``) — ebit e invested_capital ficam vazios
    para bancos/instituições financeiras (sem linha equivalente na
    DFP), e debt_to_equity continua no valor-padrão de propósito (ver
    docstring de ``fetch_equity_template_live``).

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

    if asset_type in ("fii", "etf", "fixed_income", "agro", "equity") and not cnpj:
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


def _auto_valuation_score(
    symbol: str, asset_type: str, raw: dict, price: float | None, financials: dict
) -> float | None:
    """Valuation score for ``analyze --decide --auto-valuation`` (see
    ``iip.decision.catalog_valuation``). ``None`` keeps the neutral default."""
    from iip.decision.catalog_valuation import catalog_valuation_for_decision
    from iip.portfolio.batch_value import _default_fetch_rate

    rate = None
    try:
        found = _default_fetch_rate()
        rate = found.real_yield if found else None
        if found:
            console.print(
                f"[dim]NTN-B longa (venc. {found.maturity:%d/%m/%Y}, ref. "
                f"{found.reference_date:%d/%m/%Y}): IPCA + {found.real_yield:.2%}[/]"
            )
    except Exception as exc:  # noqa: BLE001 — a taxa é consulta de mercado opcional; sem ela o Bazin fica sem valor, a decisão segue
        console.print(f"[yellow]Aviso: não consegui buscar a taxa da NTN-B: {exc}[/]")

    result = catalog_valuation_for_decision(
        ticker=symbol,
        asset_class=asset_type,
        sector=raw["sector"],
        industry=raw["industry"],
        price=price,
        financials=financials,
        ntnb_real_yield=rate,
    )
    if result.score is None:
        console.print(f"[yellow]Aviso: valuation automático sem valor — {result.explanation}[/]")
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
    "Sobrescrita a cada execução; independente de --persist.",
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
        console.print("[dim]IIP_BOLSAI_API_KEY não definida — sem preço/LPA/VPA, Graham não calcula.[/]")

    console.print("[dim]Avaliando carteira...[/]\n")
    resultado = value_portfolio(
        bolsai_api_key=bolsai_key,
        brapi_token=brapi_token,
        vault_path=vault_path,
        persist=persist,
        ano=ano,
    )
    console.print(f"[dim]{resultado.ntnb_note}[/]\n")

    table = Table(title="Valuation da carteira — valor justo/teto (margem de segurança)")
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
        console.print(f"[yellow]pulado[/] ({len(tickers)}): {detail} — {', '.join(tickers)}")
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

    if report:
        import datetime as _dt

        from iip.obsidian.valuation_report import write_valuation_report

        written = write_valuation_report(
            vault_path,
            resultado,
            as_of=_dt.date.today(),  # noqa: DTZ011 — data de calendário do usuário (a mesma das decisões), não timestamp
        )
        console.print(f"[dim]Relatório de valuation: {written}[/]")

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
    help="Só com --decide e --type equity ou fii: calcula a nota de valuation pelo "
    "método principal do catálogo (ações: Bazin em setores de dividendo, Graham nos "
    "demais; FIIs: NAV, o patrimônio por cota; Bazin/Yield usam a NTN-B longa, "
    "buscada agora). O --data-file precisa trazer os insumos (lpa/vpa/"
    "dividend_per_share nas ações; nav_per_share nos FIIs) e, nos FIIs, sector/"
    "industry = estrutura/segmento (Tijolo, Papel...). Um --valuation-score "
    "explícito tem precedência. Se nenhum método produz valor, fica neutro (5.0) "
    "e o motivo é mostrado.",
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
        hoje = _dt.date.today()  # noqa: DTZ011 — data de calendário (mês de referência padrão), não timestamp
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
            console.print(f"[bold red]Nenhum ano disponível via MZIQ para {normalized_ticker}.[/]")
            raise SystemExit(1)
        ano_efetivo = max(anos)

    console.print(f"[dim]Buscando documentos de {normalized_ticker} ({ano_efetivo})...[/]\n")

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
    out_dir = Path(output_dir) / normalized_ticker / str(ano_efetivo) if output_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    table = Table(title=f"Documentos {manager_label}/MZIQ — {normalized_ticker} ({ano_efetivo})")
    table.add_column("Categoria")
    table.add_column("Título")
    table.add_column("Status")

    baixados = 0
    for document in documents:
        if not document.url:
            table.add_row(document.category or "-", document.file_title or "-", "[yellow]sem URL[/]")
            continue
        try:
            request = Request(document.url, headers={"User-Agent": "IIP-D-OBSIDIAN/1.0"})
            with urlopen(request, timeout=30.0) as response:  # noqa: S310 — URL vem da própria API MZIQ, não de entrada externa
                body = response.read()
                content_type = response.headers.get("Content-Type", "application/octet-stream")
        except HTTPError as exc:
            table.add_row(document.category or "-", document.file_title or "-", f"[red]HTTP {exc.code}[/]")
            continue
        except Exception as exc:  # noqa: BLE001 — hospedagens variadas (arquivo truncado, timeout, SSL); um documento ruim não deve abortar a coleta inteira
            table.add_row(document.category or "-", document.file_title or "-", f"[red]{type(exc).__name__}[/]")
            continue

        if out_dir is not None:
            suffix = Path(document.url.split("?", 1)[0]).suffix or ".bin"
            filename = f"{document.id}{suffix}" if document.id else f"{baixados}{suffix}"
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
        table.add_row(document.category or "-", document.file_title or "-", "[green]ok[/]")

    console.print(table)
    console.print(f"\n[green]{baixados}/{len(documents)} documento(s)[/] baixado(s) com sucesso.")
    if out_dir is not None:
        console.print(f"[dim]Cópias salvas em {out_dir}[/]")
    if bridge is not None:
        console.print("[dim]Evidência Atlas persistida no vault (04_Evidence).[/]")


@cli.command("collect-static-documents")
@click.option(
    "--ticker",
    required=True,
    help="Fundo com listagem de documentos em HTML estático: TRXF11, "
    "VGIP11, CPTI11, MANA11, RBVA11, HGBS11 ou KNRI11.",
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
        build_target,
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

    listing = StaticPdfListingHTTPHarvester().fetch(build_target(normalized_ticker))
    documents = listing.documents
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
            request = Request(document.url, headers={"User-Agent": "IIP-D-OBSIDIAN/1.0"})
            with urlopen(request, timeout=30.0) as response:  # noqa: S310 — URL vem da própria página do fundo, não de entrada externa
                body = response.read()
                content_type = response.headers.get("Content-Type", "application/pdf")
        except HTTPError as exc:
            table.add_row(document.title, f"[red]HTTP {exc.code}[/]")
            continue
        except Exception as exc:  # noqa: BLE001 — hospedagens variadas (timeout, SSL, DNS); um documento ruim não deve abortar a coleta inteira
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
    console.print(f"\n[green]{baixados}/{len(documents)} documento(s)[/] baixado(s) com sucesso.")
    if out_dir is not None:
        console.print(f"[dim]Cópias salvas em {out_dir}[/]")
    if bridge is not None:
        console.print("[dim]Evidência Atlas persistida no vault (04_Evidence).[/]")


@cli.command("collect-solutions-ir-documents")
@click.option(
    "--ticker",
    required=True,
    help="Ativo com config Solutions IR registrada: hoje só BTCI11.",
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
        build_documents_target,
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

    console.print(f"[dim]Buscando documentos de {normalized_ticker} via Solutions IR...[/]\n")

    result = SolutionsIrHTTPHarvester().fetch(build_documents_target(normalized_ticker))
    documents = result.documents
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
            request = Request(document.url, headers={"User-Agent": "IIP-D-OBSIDIAN/1.0"})
            with urlopen(request, timeout=30.0) as response:  # noqa: S310 — URL vem da própria API Solutions IR, não de entrada externa
                body = response.read()
                content_type = response.headers.get("Content-Type", "application/pdf")
        except HTTPError as exc:
            table.add_row(document.category_sigla, document.year, document.title, f"[red]HTTP {exc.code}[/]")
            continue
        except Exception as exc:  # noqa: BLE001 — hospedagem estática de terceiro (static.btgpactual.com); um documento ruim não deve abortar a coleta inteira
            table.add_row(document.category_sigla, document.year, document.title, f"[red]{type(exc).__name__}[/]")
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
        table.add_row(document.category_sigla, document.year, document.title, "[green]ok[/]")

    console.print(table)
    console.print(f"\n[green]{baixados}/{len(documents)} documento(s)[/] baixado(s) com sucesso.")
    if out_dir is not None:
        console.print(f"[dim]Cópias salvas em {out_dir}[/]")
    if bridge is not None:
        console.print("[dim]Evidência Atlas persistida no vault (04_Evidence).[/]")


if __name__ == "__main__":
    cli()
