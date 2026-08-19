# Reproducibility

The tested environment is Python 3.12 with versions constrained by
`constraints/py312.txt`. The same validation contract runs locally and on Ubuntu and Windows
in GitHub Actions.

```bash
python -m pip install -c constraints/py312.txt -e ".[dev,providers]"
python -m pip check
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pre_commit validate-config .pre-commit-config.yaml
python -m pre_commit run --all-files
python scripts/publication_guard.py
python scripts/check_markdown_links.py
python -m build
python -m heston_arb_lab.cli demo
```

Tests generate artificial values at runtime and use temporary directories for file-system
behavior. No empirical input, fitted surface, report, or test-output file is versioned.
