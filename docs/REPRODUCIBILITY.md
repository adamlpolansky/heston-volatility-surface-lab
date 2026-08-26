# Reproducibility

The tested environment is Python 3.12 with versions constrained by
`constraints/py312.txt`. The same validation contract runs locally and on Ubuntu and Windows
in GitHub Actions.

```bash
python -m pip install -c constraints/py312.txt -e ".[dev]"
python -m pip check
python -m heston_arb_lab.cli synthetic-evidence
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

The evidence command must reproduce `docs/assets/synthetic_evidence.json` and
`docs/assets/synthetic_evidence.svg` byte for byte. CI runs it before checking that the tracked
tree is unchanged. Only aggregate synthetic evidence is versioned; quote rows are generated in
memory and never written.

Seed, date, generator parameters and Heston structural settings are constants in
`heston_arb_lab.synthetic_evidence`. No network or credential is used after dependencies are
installed.
