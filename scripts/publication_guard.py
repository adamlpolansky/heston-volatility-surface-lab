"""Fail closed when the tracked publication boundary contains disallowed material."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".gitattributes",
    ".gitignore",
    ".pre-commit-config.yaml",
    "CITATION.cff",
    "LICENSE",
    "Makefile",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
}
EXACT_FILES = {
    ".github/workflows/ci.yml",
    "constraints/py312.txt",
    "docs/ARCHITECTURE.md",
    "docs/DATA_CONTRACTS.md",
    "docs/LIMITATIONS.md",
    "docs/METHODOLOGY.md",
    "docs/PROVIDERS.md",
    "docs/PUBLIC_DATA_POLICY.md",
    "docs/REPRODUCIBILITY.md",
    "docs/USAGE.md",
    "scripts/check_markdown_links.py",
    "scripts/publication_guard.py",
}
SYNTHETIC_ARTIFACTS = {
    "docs/assets/synthetic_evidence.json",
    "docs/assets/synthetic_evidence.svg",
}
PYTHON_PREFIXES = ("src/heston_arb_lab/", "tests/")
FORBIDDEN_SUFFIXES = {
    ".7z",
    ".arrow",
    ".csv",
    ".db",
    ".duckdb",
    ".feather",
    ".gz",
    ".html",
    ".ipynb",
    ".json",
    ".jsonl",
    ".parquet",
    ".pdf",
    ".pfx",
    ".png",
    ".sqlite",
    ".svg",
    ".tar",
    ".tsv",
    ".xls",
    ".xlsx",
    ".zip",
}
FORBIDDEN_PARTS = {
    ".ipynb_checkpoints",
    "backtests",
    "candidates",
    "data",
    "external",
    "figures",
    "interim",
    "notebooks",
    "outputs",
    "plots",
    "private",
    "processed",
    "provider_exports",
    "raw",
    "reports",
    "results",
}
FORBIDDEN_NAME_FRAGMENTS = (
    "agent" + "s.md",
    "prompt",
    "research_report",
    "research_status",
    "experiment_status",
)
FORBIDDEN_TEXT_DIGESTS = {
    "35da52e03109190fb247b7126454d8bde7594d86fefab86e9cc5d0d8393a862e",
    "b923405ba2c6a80ac557a30930e6119300a1c0805536c8dd0795340970591324",
    "199dc38e1a4d3008afbe8de87653c31bd4143a501f47539022b8340ebdfecc30",
    "06791fde6345849b7dd688ce8e8a79e6ba947fe0af2571f2f3f4b8ebf0d9cb47",
    "771eace85b7d642b92aa43e8015aa80fbdbf61d80633288c759bc5775de450d8",
    "9896cbc5690b517727b05f71e641f907ceb5cb9f555002d022ec268853382529",
    "7cc8dd96aac3dd85b76c435bf4f12031304e99e03e89a06976f7647c6ff55d14",
    "f4b723e7d05ce8a0c8e30376b0bf7b8e21f00ee94a8d9cc4ec410c4cac228000",
    "2399158583673b7bf1aed87d6cc572dee6037aa054566882311f94407f9c0179",
    "6973dddd3ef9cb6a2932702f31777faad9c9bf3124d147a84f31aadb6d139546",
}
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SECRET_PATTERNS = {
    "private key": re.compile(("-----" + "BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY").encode()),
    "cloud access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GitHub token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "API token": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "credential URL": re.compile(rb"[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@"),
    "secret assignment": re.compile(
        rb"(?i)(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*[\"']"
        rb"[A-Za-z0-9+/=_-]{16,}[\"']"
    ),
}


def _candidate_files() -> list[Path]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if tracked.returncode != 0:
        detail = tracked.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(f"publication guard could not enumerate Git files: {detail}")
    return sorted(ROOT / item.decode("utf-8") for item in tracked.stdout.split(b"\0") if item)


def _is_allowlisted(relative: str) -> bool:
    if relative in ROOT_FILES or relative in EXACT_FILES or relative in SYNTHETIC_ARTIFACTS:
        return True
    return relative.endswith(".py") and relative.startswith(PYTHON_PREFIXES)


def _contains_forbidden_digest(text: str) -> bool:
    tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.casefold())
    for width in range(1, 5):
        for index in range(len(tokens) - width + 1):
            candidate = " ".join(tokens[index : index + width])
            if hashlib.sha256(candidate.encode()).hexdigest() in FORBIDDEN_TEXT_DIGESTS:
                return True
    return False


def _local_machine_reference(text: str) -> bool:
    windows_home = re.compile(r"[A-Za-z]:[\\/]" + "Users" + r"[\\/]")
    unix_home = "/" + "home/"
    mac_home = "/" + "Users/"
    hostname = os.environ.get("COMPUTERNAME", "")
    return bool(
        windows_home.search(text)
        or unix_home in text
        or mac_home in text
        or (hostname and hostname.casefold() in text.casefold())
    )


def main() -> None:
    failures: list[str] = []
    files = _candidate_files()
    total_size = 0
    largest = (0, "")
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        top_level = path.relative_to(ROOT).parts[0]
        lower_name = path.name.casefold()
        if not _is_allowlisted(relative):
            failures.append(f"outside allowlist: {relative}")
        if path.is_symlink():
            failures.append(f"symlink: {relative}")
        if (
            path.suffix.casefold() in FORBIDDEN_SUFFIXES and relative not in SYNTHETIC_ARTIFACTS
        ) or top_level in FORBIDDEN_PARTS:
            failures.append(f"forbidden path type: {relative}")
        if any(fragment in lower_name for fragment in FORBIDDEN_NAME_FRAGMENTS):
            failures.append(f"internal filename: {relative}")
        data = path.read_bytes()
        total_size += len(data)
        largest = max(largest, (len(data), relative))
        if len(data) > 512_000:
            failures.append(f"unexpected large file: {relative}")
        if b"\0" in data:
            failures.append(f"unexpected binary file: {relative}")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            failures.append(f"non-UTF-8 file: {relative}")
            continue
        if relative in SYNTHETIC_ARTIFACTS and "SYNTHETIC" not in text:
            failures.append(f"unlabelled synthetic artifact: {relative}")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                failures.append(f"{label}: {relative}")
        if EMAIL.search(text):
            failures.append(f"email address: {relative}")
        if _local_machine_reference(text):
            failures.append(f"local machine reference: {relative}")
        if _contains_forbidden_digest(text):
            failures.append(f"private-study identifier or outcome: {relative}")

    if failures:
        raise SystemExit("publication guard failed:\n" + "\n".join(sorted(set(failures))))
    print(
        f"publication guard passed: files={len(files)} total_bytes={total_size} "
        f"largest={largest[1]}:{largest[0]}"
    )


if __name__ == "__main__":
    main()
