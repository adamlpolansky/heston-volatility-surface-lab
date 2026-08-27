from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from scripts import publication_guard

ROOT = Path(__file__).resolve().parents[1]


def _copy_approved_publication(tmp_path: Path) -> Path:
    source = ROOT / publication_guard.APPROVED_DIRECTORY
    target = tmp_path / publication_guard.APPROVED_DIRECTORY
    shutil.copytree(source, target)
    shutil.copy2(ROOT / "README.md", tmp_path / "README.md")
    return tmp_path


def test_publication_guard_accepts_the_repository() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/publication_guard.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_approved_publication_accepts_allowlisted_artifacts(tmp_path: Path) -> None:
    root = _copy_approved_publication(tmp_path)

    assert publication_guard.approved_publication_failures(root) == []


def test_approved_publication_rejects_hash_drift(tmp_path: Path) -> None:
    root = _copy_approved_publication(tmp_path)
    artifact = root / publication_guard.APPROVED_DIRECTORY / "03_oot_aggregate_table.csv"
    artifact.write_bytes(artifact.read_bytes() + b"\n")

    failures = publication_guard.approved_publication_failures(root)

    assert any("approved artifact hash drift" in failure for failure in failures)


def test_approved_publication_rejects_extra_file(tmp_path: Path) -> None:
    root = _copy_approved_publication(tmp_path)
    extra = root / publication_guard.APPROVED_DIRECTORY / "extra.csv"
    extra.write_text("not,approved\n", encoding="utf-8")

    failures = publication_guard.approved_publication_failures(root)

    assert any("unexpected file in approved directory" in failure for failure in failures)


def test_approved_publication_rejects_missing_attribution(tmp_path: Path) -> None:
    root = _copy_approved_publication(tmp_path)
    readme = root / "README.md"
    image_reference = (
        f"{publication_guard.APPROVED_DIRECTORY}/01_normalized_heston_model_surface.png)"
    )
    text = readme.read_text(encoding="utf-8")
    text = text.replace(
        f"{image_reference}\n\n{publication_guard.ATTRIBUTION}",
        f"{image_reference}\n\nAttribution intentionally removed for this test.",
        1,
    )
    readme.write_text(text, encoding="utf-8")

    failures = publication_guard.approved_publication_failures(root)

    assert any("missing adjacent attribution" in failure for failure in failures)


def test_provider_adapter_defaults_to_dry_run() -> None:
    from heston_arb_lab.data.thetadata_client import FakeThetaDataClient, ThetaDataAdapter

    adapter = ThetaDataAdapter()

    assert isinstance(adapter.connect(), FakeThetaDataClient)
