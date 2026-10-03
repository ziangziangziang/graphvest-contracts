.PHONY: setup lint format typecheck test check
UV_CACHE_DIR ?= .uv-cache
export UV_CACHE_DIR

setup:
	uv sync --locked
lint:
	uv run --offline --frozen ruff check .
	uv run --offline --frozen ruff format --check .
format:
	uv run --offline --frozen ruff check --fix .
	uv run --offline --frozen ruff format .
typecheck:
	uv run --offline --frozen mypy src tests
test:
	uv run --offline --frozen pytest
check: lint typecheck test