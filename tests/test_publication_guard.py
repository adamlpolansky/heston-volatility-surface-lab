from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("relative", sorted(publication_guard.APPROVED_FILE_HASHES))
def test_approved_publication_rejects_every_approved_file_hash_drift(
    tmp_path: Path, relative: str
) -> None:
    root = _copy_approved_publication(tmp_path)
    artifact = root / relative
    artifact.write_bytes(artifact.read_bytes() + b"SYNTHETIC-DRIFT-SENTINEL")

    failures = publication_guard.approved_publication_failures(root)

    assert f"approved file hash drift: {relative}" in failures


def test_approved_publication_rejects_extra_file(tmp_path: Path) -> None:
    root = _copy_approved_publication(tmp_path)
    extra = root / publication_guard.APPROVED_DIRECTORY / "extra.csv"
    extra.write_text("not,approved\n", encoding="utf-8")

    failures = publication_guard.approved_publication_failures(root)

    assert any("unexpected file in approved directory" in failure for failure in failures)


def test_approved_publication_rejects_missing_file(tmp_path: Path) -> None:
    root = _copy_approved_publication(tmp_path)
    relative = f"{publication_guard.APPROVED_DIRECTORY}/07_audit_summary.csv"
    (root / relative).unlink()

    failures = publication_guard.approved_publication_failures(root)

    assert f"missing approved file: {relative}" in failures


def test_approved_publication_rejects_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _copy_approved_publication(tmp_path)
    relative = f"{publication_guard.APPROVED_DIRECTORY}/07_audit_summary.csv"
    target = root / relative
    original = target.read_bytes()
    target.unlink()
    try:
        target.symlink_to("README.md")
    except OSError:
        target.write_bytes(original)
        real_is_symlink = publication_guard._is_symlink
        monkeypatch.setattr(
            publication_guard,
            "_is_symlink",
            lambda path: path == target or real_is_symlink(path),
        )

    failures = publication_guard.approved_publication_failures(root)

    assert f"approved file is a symlink: {relative}" in failures


def _remove_adjacent_attribution(path: Path, reference: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        f"{reference}\n\n{publication_guard.ATTRIBUTION}",
        f"{reference}\n\nSYNTHETIC ATTRIBUTION-REMOVAL SENTINEL.",
        1,
    )
    path.write_text(text, encoding="utf-8")


def test_approved_publication_rejects_missing_root_attribution(tmp_path: Path) -> None:
    root = _copy_approved_publication(tmp_path)
    readme = root / "README.md"
    image_reference = (
        f"{publication_guard.APPROVED_DIRECTORY}/01_normalized_heston_model_surface.png)"
    )
    _remove_adjacent_attribution(readme, image_reference)

    failures = publication_guard.approved_publication_failures(root)

    assert any("missing adjacent attribution" in failure for failure in failures)


def test_approved_publication_rejects_missing_evidence_index_attribution(
    tmp_path: Path,
) -> None:
    root = _copy_approved_publication(tmp_path)
    readme = root / publication_guard.APPROVED_DIRECTORY / "README.md"
    _remove_adjacent_attribution(readme, "01_normalized_heston_model_surface.png)")

    failures = publication_guard.approved_publication_failures(root)

    assert any("missing adjacent attribution" in failure for failure in failures)


def test_approved_publication_rejects_missing_disclaimer(tmp_path: Path) -> None:
    root = _copy_approved_publication(tmp_path)
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8").replace(
        publication_guard.DISCLAIMER,
        "SYNTHETIC DISCLAIMER-REMOVAL SENTINEL.",
        1,
    )
    readme.write_text(text, encoding="utf-8")

    failures = publication_guard.approved_publication_failures(root)

    assert "missing Theta Data disclaimer: README.md" in failures


def test_approved_publication_rejects_missing_licence_carve_out(tmp_path: Path) -> None:
    root = _copy_approved_publication(tmp_path)
    readme = root / "README.md"
    marker = publication_guard.CARVE_OUT_MARKERS[0]
    text = readme.read_text(encoding="utf-8").replace(
        marker,
        "SYNTHETIC LICENCE-REMOVAL SENTINEL",
        1,
    )
    readme.write_text(text, encoding="utf-8")

    failures = publication_guard.approved_publication_failures(root)

    assert any("missing licence carve-out in README.md" in failure for failure in failures)


def test_approved_markdown_rejects_synthetic_forbidden_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _copy_approved_publication(tmp_path)
    sentinel = "synthetic forbidden observation"
    monkeypatch.setattr(
        publication_guard,
        "FORBIDDEN_TEXT_DIGESTS",
        publication_guard.FORBIDDEN_TEXT_DIGESTS | {hashlib.sha256(sentinel.encode()).hexdigest()},
    )
    provenance = (
        root
        / publication_guard.APPROVED_DIRECTORY
        / "08_data_provenance_and_public_private_boundary.md"
    )
    provenance.write_text(
        provenance.read_text(encoding="utf-8") + f"\n{sentinel}\n",
        encoding="utf-8",
    )

    failures = publication_guard.approved_publication_failures(root)

    assert any("private-study identifier or outcome" in failure for failure in failures)


def test_python_allowlist_rejects_nested_results_module(tmp_path: Path) -> None:
    relative = "src/heston_arb_lab/results/leak.py"
    leak = tmp_path / relative
    leak.parent.mkdir(parents=True)
    leak.write_text("SYNTHETIC_SENTINEL = True\n", encoding="utf-8")

    failures = publication_guard._path_policy_failures(leak.relative_to(tmp_path).as_posix())

    assert "outside allowlist" in failures
    assert "forbidden path type" in failures


def test_python_allowlist_keeps_existing_data_module() -> None:
    assert publication_guard._path_policy_failures("src/heston_arb_lab/data/storage.py") == []


def _write_gitattributes(root: Path, *lines: str) -> None:
    (root / ".gitattributes").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_exact_approved_gitattributes_line_passes(tmp_path: Path) -> None:
    _write_gitattributes(tmp_path, publication_guard.APPROVED_GITATTRIBUTES_LINE)

    assert publication_guard._current_gitattributes_failures(tmp_path) == []
    assert not publication_guard._contains_forbidden_digest_for_path(
        ".gitattributes",
        publication_guard.APPROVED_GITATTRIBUTES_LINE,
    )


def test_missing_approved_gitattributes_line_fails(tmp_path: Path) -> None:
    _write_gitattributes(tmp_path, "* text=auto eol=lf")

    assert publication_guard._current_gitattributes_failures(tmp_path)


def test_duplicate_approved_gitattributes_line_fails(tmp_path: Path) -> None:
    line = publication_guard.APPROVED_GITATTRIBUTES_LINE
    _write_gitattributes(tmp_path, line, line)

    assert publication_guard._current_gitattributes_failures(tmp_path)


@pytest.mark.parametrize(
    "line",
    [
        f"{publication_guard.APPROVED_GITATTRIBUTES_LINE} # trailing comment",
        publication_guard.APPROVED_GITATTRIBUTES_LINE.replace("/* -text", "/nested/* -text"),
    ],
)
def test_modified_approved_gitattributes_line_fails(tmp_path: Path, line: str) -> None:
    _write_gitattributes(tmp_path, line)

    assert publication_guard._current_gitattributes_failures(tmp_path)
    assert publication_guard._contains_forbidden_digest_for_path(".gitattributes", line)


def test_approved_gitattributes_text_in_another_path_fails() -> None:
    assert publication_guard._contains_forbidden_digest_for_path(
        ".gitignore",
        publication_guard.APPROVED_GITATTRIBUTES_LINE,
    )


def test_approved_gitattributes_line_does_not_hide_another_study_token() -> None:
    protected_token = next(
        token
        for token in publication_guard.APPROVED_STUDY_TOKENS
        if token in publication_guard.APPROVED_GITATTRIBUTES_LINE.casefold()
    )
    text = f"{publication_guard.APPROVED_GITATTRIBUTES_LINE}\n{protected_token}\n"

    assert publication_guard._contains_forbidden_digest_for_path(".gitattributes", text)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={repo.resolve()}", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _synthetic_git_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "synthetic-history-repository"
    repo.mkdir()
    _git(repo, "init", "-b", "review-head")
    _git(repo, "config", "user.name", "Synthetic Tester")
    _git(repo, "config", "user.email", "synthetic.invalid")
    (repo / "README.md").write_text("SYNTHETIC TEST REPOSITORY\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "synthetic baseline")
    return repo


def test_history_rejects_deleted_synthetic_forbidden_artifact(tmp_path: Path) -> None:
    repo = _synthetic_git_repository(tmp_path)
    forbidden = repo / "results" / "raw_quotes.csv"
    forbidden.parent.mkdir()
    forbidden.write_text("SYNTHETIC_SENTINEL_ONLY\n", encoding="utf-8")
    _git(repo, "add", "results/raw_quotes.csv")
    _git(repo, "commit", "-m", "add synthetic forbidden sentinel")
    forbidden.unlink()
    forbidden.parent.rmdir()
    _git(repo, "add", "--update")
    _git(repo, "commit", "-m", "remove synthetic forbidden sentinel")

    failures = publication_guard.history_failures(repo)

    assert any(
        "historical forbidden path type: results/raw_quotes.csv" in failure for failure in failures
    )


def test_history_ignores_unrelated_branch_outside_head(tmp_path: Path) -> None:
    repo = _synthetic_git_repository(tmp_path)
    _git(repo, "switch", "-c", "outside-head")
    forbidden = repo / "results" / "raw_quotes.csv"
    forbidden.parent.mkdir()
    forbidden.write_text("SYNTHETIC_SENTINEL_ONLY\n", encoding="utf-8")
    _git(repo, "add", "results/raw_quotes.csv")
    _git(repo, "commit", "-m", "side-branch synthetic sentinel")
    _git(repo, "switch", "review-head")

    assert publication_guard.history_failures(repo) == []


def test_history_accepts_exact_approved_gitattributes_line(tmp_path: Path) -> None:
    repo = _synthetic_git_repository(tmp_path)
    _write_gitattributes(repo, publication_guard.APPROVED_GITATTRIBUTES_LINE)
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "add synthetic attributes sentinel")

    assert publication_guard.history_failures(repo) == []


@pytest.mark.parametrize("include_additional_token", [False, True])
def test_history_rejects_non_exact_approved_gitattributes_content(
    tmp_path: Path, include_additional_token: bool
) -> None:
    repo = _synthetic_git_repository(tmp_path)
    protected_token = next(
        token
        for token in publication_guard.APPROVED_STUDY_TOKENS
        if token in publication_guard.APPROVED_GITATTRIBUTES_LINE.casefold()
    )
    lines = [publication_guard.APPROVED_GITATTRIBUTES_LINE]
    if include_additional_token:
        lines.append(protected_token)
    else:
        lines[0] += " # trailing comment"
    _write_gitattributes(repo, *lines)
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "add non-exact synthetic attributes sentinel")

    failures = publication_guard.history_failures(repo)

    assert any("historical private-study identifier or outcome" in failure for failure in failures)


def test_provider_adapter_defaults_to_dry_run() -> None:
    from heston_arb_lab.data.thetadata_client import FakeThetaDataClient, ThetaDataAdapter

    adapter = ThetaDataAdapter()

    assert isinstance(adapter.connect(), FakeThetaDataClient)
