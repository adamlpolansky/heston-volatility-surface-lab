from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_publication_guard_accepts_the_repository() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/publication_guard.py"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_provider_adapter_defaults_to_dry_run() -> None:
    from heston_arb_lab.data.thetadata_client import FakeThetaDataClient, ThetaDataAdapter

    adapter = ThetaDataAdapter()

    assert isinstance(adapter.connect(), FakeThetaDataClient)
