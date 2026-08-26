"""Credential-free command-line entry points."""

from __future__ import annotations

import importlib.util
import platform
from pathlib import Path

import typer

from heston_arb_lab import __version__
from heston_arb_lab.config import resolve_thetadata_credentials
from heston_arb_lab.synthetic_evidence import run_synthetic_evidence, write_synthetic_evidence

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
    """Run the complete synthetic evidence pipeline without writing artifacts."""

    run = run_synthetic_evidence()
    typer.echo("label=SYNTHETIC")
    typer.echo("mode=offline-synthetic")
    typer.echo(f"clean_quote_rows={run.summary['pipeline']['clean_quote_rows']}")
    typer.echo(
        f"price_space_violations={run.summary['price_space_static_arbitrage']['violations']}"
    )
    typer.echo(
        f"execution_candidates_accepted={run.summary['execution_gates']['accepted_as_executable']}"
    )
    typer.echo("network_request=none")
    typer.echo("artifacts_written=none")


@app.command("synthetic-evidence")
def synthetic_evidence(
    output_dir: Path | None = typer.Option(
        None,
        help="Output directory; defaults to the committed docs/assets evidence directory.",
    ),
) -> None:
    """Regenerate the labelled aggregate JSON and SVG evidence pack."""

    destination = output_dir or Path(__file__).resolve().parents[2] / "docs" / "assets"
    run = write_synthetic_evidence(destination)
    typer.echo("label=SYNTHETIC")
    typer.echo(f"seed={run.summary['seed']}")
    typer.echo(f"summary={destination / 'synthetic_evidence.json'}")
    typer.echo(f"visual={destination / 'synthetic_evidence.svg'}")
    typer.echo("network_request=none")


if __name__ == "__main__":
    app()
