.PHONY: lint format test check import-check serve dev

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

test:
	uv run pytest tests/ -v

check: lint test

import-check:
	uv run python -c "from cortex.api.main import create_app; print('OK')"

serve:
	uv run cortex serve

dev:
	uv sync --extra dev --extra local-embeddings
