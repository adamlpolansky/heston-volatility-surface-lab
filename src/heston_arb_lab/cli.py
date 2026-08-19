"""Credential-free command-line entry points."""

from __future__ import annotations

import importlib.util
import platform
from datetime import date

import typer

from heston_arb_lab import __version__
from heston_arb_lab.config import resolve_thetadata_credentials
from heston_arb_lab.signals.parity import scan_put_call_parity
from heston_arb_lab.signals.ranking import rank_signals
from heston_arb_lab.surface.no_arbitrage import run_no_arbitrage_checks
from heston_arb_lab.surface.surface_builder import (
    SurfaceBuildConfig,
    build_surface,
    synthetic_option_chain,
)

app = typer.Typer(
    name="heston-lab",
    help="Offline-first Heston/SSVI and static-arbitrage diagnostics.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def doctor() -> None:
    """Print a secret-free environment summary without network access."""

    provider_installed = importlib.util.find_spec("thetadata") is not None
    credentials, _ = resolve_thetadata_credentials()
    typer.echo(f"heston_arb_lab={__version__}")
    typer.echo(f"python={platform.python_version()}")
    typer.echo(f"thetadata_extra={'installed' if provider_installed else 'not-installed'}")
    typer.echo(f"thetadata_credentials={'present' if credentials.present else 'missing'}")
    typer.echo("network_request=none")


@app.command("provider-status")
def provider_status() -> None:
    """Describe optional provider readiness without connecting or exposing secrets."""

    installed = importlib.util.find_spec("thetadata") is not None
    credentials, _ = resolve_thetadata_credentials()
    typer.echo("mode=dry-run")
    typer.echo(f"client={'installed' if installed else 'not-installed'}")
    typer.echo(f"credentials={'present' if credentials.present else 'missing'}")
    typer.echo("network_request=none")


@app.command()
def demo() -> None:
    """Run an in-memory artificial surface and diagnostic smoke test."""

    asof = date(2040, 1, 15)
    quotes = synthetic_option_chain(asof=asof, symbol="SYNTH")
    surface = build_surface(
        quotes,
        SurfaceBuildConfig(spot=100.0, asof=asof, rate=0.04),
    )
    violations = run_no_arbitrage_checks(surface, rate=0.04)
    parity = scan_put_call_parity(
        surface,
        spot=100.0,
        rate=0.04,
        min_abs_residual=0.002,
    )
    ranked = rank_signals(parity, min_net_edge=0.0)

    typer.echo("mode=offline-artificial")
    typer.echo(f"surface_rows={len(surface)}")
    typer.echo(f"necessary_condition_flags={len(violations)}")
    typer.echo(f"execution_filtered_candidates={len(ranked)}")
    typer.echo("network_request=none")
    typer.echo("artifacts_written=none")


if __name__ == "__main__":
    app()
