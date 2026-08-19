"""Check local Markdown links and exact path casing on every platform."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "work"}
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def _markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
    )


def _case_exact(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    current = ROOT
    for part in relative.parts:
        if not current.is_dir() or part not in {entry.name for entry in current.iterdir()}:
            return False
        current /= part
    return current.exists()


def _target_path(markdown: Path, raw_target: str) -> Path | None:
    target = raw_target.strip().strip("<>")
    if not target or target.startswith("#"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    clean_path = unquote(parsed.path).replace("/", str(Path("/").anchor or "/"))
    if not clean_path:
        return None
    return (markdown.parent / Path(clean_path)).resolve()


def main() -> None:
    failures: list[str] = []
    checked = 0
    for markdown in _markdown_files():
        for line_number, line in enumerate(markdown.read_text(encoding="utf-8").splitlines(), 1):
            for match in LINK_PATTERN.finditer(line):
                target = _target_path(markdown, match.group(1))
                if target is None:
                    continue
                checked += 1
                if not _case_exact(target):
                    source = markdown.relative_to(ROOT).as_posix()
                    failures.append(f"{source}:{line_number}: {match.group(1)}")
    if failures:
        raise SystemExit("broken or case-mismatched local Markdown links:\n" + "\n".join(failures))
    print(f"checked {checked} local Markdown links case-sensitively")


if __name__ == "__main__":
    main()
