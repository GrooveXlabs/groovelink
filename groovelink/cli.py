"""Click CLI for GrooveLink health monitoring."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.table import Table

from groovelink.client import GrooveLinkClient, GrooveLinkSync
from groovelink.health import HealthStatus

console = Console()


def _run_sync_health(url: str, path: str, samples: int) -> None:
    client = GrooveLinkSync(base_url=url)
    with client:
        for i in range(samples):
            result = client.health_check(path)
            color = {
                HealthStatus.HEALTHY: "green",
                HealthStatus.DEGRADED: "yellow",
                HealthStatus.UNHEALTHY: "red",
            }.get(result.status, "white")
            console.print(
                f"[{i+1}/{samples}] {result.status.value.upper()} — "
                f"{result.response_time_ms:.1f}ms — {result.message}",
                style=color,
            )

        summary = client.health_monitor.summary()
        table = Table(title="Health Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Status", summary["status"])
        table.add_row("Samples", str(summary["samples"]))
        table.add_row("Avg (ms)", f"{summary['avg_ms']:.1f}")
        table.add_row("Min (ms)", f"{summary['min_ms']:.1f}")
        table.add_row("Max (ms)", f"{summary['max_ms']:.1f}")
        console.print(table)


async def _run_async_health(url: str, path: str, samples: int) -> None:
    client = GrooveLinkClient(base_url=url)
    async with client:
        for i in range(samples):
            result = await client.health_check(path)
            color = {
                HealthStatus.HEALTHY: "green",
                HealthStatus.DEGRADED: "yellow",
                HealthStatus.UNHEALTHY: "red",
            }.get(result.status, "white")
            console.print(
                f"[{i+1}/{samples}] {result.status.value.upper()} — "
                f"{result.response_time_ms:.1f}ms — {result.message}",
                style=color,
            )

        summary = client.health_monitor.summary()
        table = Table(title="Health Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Status", summary["status"])
        table.add_row("Samples", str(summary["samples"]))
        table.add_row("Avg (ms)", f"{summary['avg_ms']:.1f}")
        table.add_row("Min (ms)", f"{summary['min_ms']:.1f}")
        table.add_row("Max (ms)", f"{summary['max_ms']:.1f}")
        console.print(table)


@click.group()
def cli() -> None:
    """GrooveLink — resilient API client CLI."""
    pass


@cli.command()
@click.argument("url")
@click.option("--path", default="/", help="Health check endpoint path.")
@click.option("--samples", default=3, help="Number of health probes.")
@click.option("--async", "use_async", is_flag=True, help="Use async client.")
def health(url: str, path: str, samples: int, use_async: bool) -> None:
    """Monitor endpoint health."""
    if use_async:
        asyncio.run(_run_async_health(url, path, samples))
    else:
        _run_sync_health(url, path, samples)


def main() -> None:
    cli()
