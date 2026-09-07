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
from iip.versioning import VersionManager

console = Console()

ANALYZERS: dict[str, type] = {
    "equity": EquityAnalyzer,
    "fii": FIIAnalyzer,
    "infra": InfraAnalyzer,
    "agro": AgroAnalyzer,
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
        json.dumps({"vault": str(vault), "exists": vault.exists(), **counts}, indent=2)
    )


@cli.command()
def health():
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
    console.print(json.dumps(info, indent=2))


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
    console.print(json.dumps(summary, indent=2))


@cli.command()
def replication():
    """Show replication status."""
    status = ReplicationEngine.status()
    console.print(json.dumps(status, indent=2))


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
        }
        console.print(json.dumps(info, indent=2))


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
    except Exception:
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
def analyze(
    symbol: str, asset_type: str, data_file: str, output_format: str, output: str | None
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


if __name__ == "__main__":
    cli()
