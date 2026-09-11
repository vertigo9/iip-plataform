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
from iip.sources.b3_brapi import build_target as build_brapi_target
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester
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
    type=click.Choice(["fii", "etf"]),
    default="fii",
    help="Asset type. Only FII and ETF are wired to real data fetching so "
    "far — equity/infra/agro still need `iip analyze-template` + manual entry.",
)
@click.option("--cnpj", required=True, help="CNPJ do fundo (formato livre, com ou sem pontuação).")
@click.option(
    "--ano", type=int, default=None, help="Ano de referência CVM (padrão: ano atual)."
)
@click.option(
    "--mes",
    type=int,
    default=None,
    help="Mês de referência CVM, 1-12 (só para --type etf; padrão: mês atual).",
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
    cnpj: str,
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

    Em ambos os casos, os campos de julgamento qualitativo (ocupação,
    governança, tracking error, taxa de administração, liquidez etc.)
    continuam com os valores-padrão do analisador — sem isso, editar à
    mão.
    """
    import datetime as _dt

    from iip.cli.fetch_template import fetch_etf_template_live, fetch_fii_template_live

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

    else:  # etf
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
    verificado — hoje FII, ETF e fixed_income (fundos regulados pela
    CVM) têm fetch automático; ações e CDBs bancários ainda não (CDB
    não tem fonte de dado pública/gratuita — não é uma limitação
    nossa, é como o mercado de CDB funciona).

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
def analyze(
    symbol: str,
    asset_type: str,
    data_file: str,
    output_format: str,
    output: str | None,
    persist: bool,
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


@cli.command("fetch-fii-template")
@click.argument("symbol")
@click.option("--cnpj", required=True, help="CNPJ do fundo (formato: 00.000.000/0001-00).")
@click.option("--ano", type=int, default=None, help="Ano de referência (padrão: ano atual).")
@click.option(
    "--brapi-token",
    default=None,
    help="Token da brapi.dev para buscar o preço atual (opcional — sem ele, price fica null).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Onde salvar o template JSON. Imprime no console se omitido.",
)
def fetch_fii_template(
    symbol: str, cnpj: str, ano: int | None, brapi_token: str | None, output: str | None
) -> None:
    """Busca dados reais (CVM FII + brapi.dev) e pré-preenche um template
    de análise para `iip analyze --type fii`.

    NÃO preenche os campos qualitativos (ocupação, governança, histórico
    do gestor etc.) — esses exigem leitura do relatório gerencial, sem
    fonte automática disponível. O comando deixa claro o que foi
    preenchido de verdade e o que ainda precisa da sua análise.
    """
    import datetime

    from iip.integration.fii_template import build_fii_template
    from iip.sources.cvm_fii import build_target as build_cvm_target

    ano_alvo = ano or datetime.date.today().year  # noqa: DTZ011 — data de calendário (ano de competência CVM), não timestamp

    console.print(f"Buscando informe CVM FII de {ano_alvo} para CNPJ {cnpj}...")
    try:
        cvm_result = CvmFiiHTTPHarvester().fetch(build_cvm_target(ano_alvo))
    except Exception as exc:
        console.print(f"[bold red]Erro ao buscar dados da CVM:[/] {exc}")
        raise SystemExit(1) from exc

    price: float | None = None
    if brapi_token:
        console.print(f"Buscando preço atual de {symbol} via brapi.dev...")
        try:
            brapi_result = BrapiHTTPHarvester(token=brapi_token).fetch(
                build_brapi_target((symbol,))
            )
            if brapi_result.quotes:
                price = brapi_result.quotes[0].regular_market_price
        except Exception as exc:  # noqa: BLE001 — preço é opcional, mesmo padrão do fetch-template atual
            console.print(f"[yellow]Aviso: não consegui buscar o preço ({exc}) — seguindo sem ele.[/]")
    else:
        console.print(
            "[dim]Sem --brapi-token: o campo 'price' vai ficar null "
            "(pode preencher manualmente depois).[/]"
        )

    base = {
        "symbol": symbol.upper(),
        "sector": "REPLACE_WITH_SECTOR",
        "industry": "REPLACE_WITH_INDUSTRY",
        "market_cap": None,
        "price": None,
        "financials": _template_financials(ANALYZERS["fii"]),
    }

    resultado = build_fii_template(
        cnpj, cvm_result.geral, cvm_result.complemento, base, price=price
    )

    payload = json.dumps(resultado.template, indent=2, ensure_ascii=False)
    if output:
        Path(output).write_text(payload, encoding="utf-8")
        console.print(f"\n[green]Template salvo em {output}[/]")
    else:
        console.print(payload)

    console.print(
        f"\n[bold green]Preenchido automaticamente ({len(resultado.auto_filled)}):[/] "
        f"{', '.join(resultado.auto_filled) or '(nenhum — CNPJ não encontrado nos dados de ' + str(ano_alvo) + '?)'}"
    )
    if resultado.months_summed_for_yield:
        console.print(
            f"[dim]dividend_yield somado a partir de {resultado.months_summed_for_yield} "
            f"mês(es) disponível(is) em {ano_alvo} — não necessariamente 12 meses completos.[/]"
        )
    console.print(
        f"[bold yellow]Ainda precisa da sua análise ({len(resultado.still_needs_completion)} "
        f"campo(s) qualitativos):[/] {', '.join(resultado.still_needs_completion)}"
    )
    console.print(
        "\n[dim]Tip: edite os campos pendentes e rode:\n"
        f"  iip analyze {symbol.upper()} --type fii --data-file <arquivo>.json[/]"
    )


if __name__ == "__main__":
    cli()