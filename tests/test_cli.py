from __future__ import annotations

from typer.testing import CliRunner

from heston_arb_lab.cli import app


def test_demo_is_offline_and_writes_no_artifacts() -> None:
    result = CliRunner().invoke(app, ["demo"])

    assert result.exit_code == 0, result.output
    assert "mode=offline-artificial" in result.output
    assert "network_request=none" in result.output
    assert "artifacts_written=none" in result.output


def test_provider_status_never_connects() -> None:
    result = CliRunner().invoke(app, ["provider-status"])

    assert result.exit_code == 0, result.output
    assert "mode=dry-run" in result.output
    assert "network_request=none" in result.output
