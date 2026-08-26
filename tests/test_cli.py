from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from heston_arb_lab.cli import app


def test_demo_is_offline_and_writes_no_artifacts() -> None:
    result = CliRunner().invoke(app, ["demo"])

    assert result.exit_code == 0, result.output
    assert "label=SYNTHETIC" in result.output
    assert "mode=offline-synthetic" in result.output
    assert "execution_candidates_accepted=0" in result.output
    assert "network_request=none" in result.output
    assert "artifacts_written=none" in result.output


def test_provider_status_never_connects() -> None:
    result = CliRunner().invoke(app, ["provider-status"])

    assert result.exit_code == 0, result.output
    assert "mode=dry-run" in result.output
    assert "network_request=none" in result.output


def test_synthetic_evidence_command_writes_only_labelled_outputs(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["synthetic-evidence", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "label=SYNTHETIC" in result.output
    assert "network_request=none" in result.output
    assert (tmp_path / "synthetic_evidence.json").is_file()
    assert (tmp_path / "synthetic_evidence.svg").is_file()
