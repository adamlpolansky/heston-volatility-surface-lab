.PHONY: install install-providers lint format format-check typecheck test guard links build check demo

install:
	python -m pip install -c constraints/py312.txt -e ".[dev]"

install-providers:
	python -m pip install -c constraints/py312.txt -e ".[dev,providers]"

lint:
	python -m ruff check .

format:
	python -m ruff format .

format-check:
	python -m ruff format --check .

typecheck:
	python -m mypy src

test:
	python -m pytest -q

guard:
	python scripts/publication_guard.py

links:
	python scripts/check_markdown_links.py

build:
	python -m build

demo:
	python -m heston_arb_lab.cli demo

check: lint format-check typecheck test guard links demo
