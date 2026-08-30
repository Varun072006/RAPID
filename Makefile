.PHONY: help install data train evaluate test test-unit test-failures coverage demo clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies with uv
	uv sync --all-extras

data:  ## Generate 100K synthetic payment scenarios
	uv run python scripts/generate-data.py

train:  ## Train failure classifier + recovery models
	uv run python scripts/train.py

evaluate:  ## Run full evaluation (baselines + ablation + distribution shift)
	uv run python scripts/evaluate.py

test:  ## Run full test suite
	uv run pytest tests/ -v

test-unit:  ## Run unit tests only (fast)
	uv run pytest tests/unit/ -v

test-integration:  ## Run integration tests
	uv run pytest tests/integration/ -v

test-failures:  ## Run failure injection tests (timeout, duplicate, out-of-order)
	uv run pytest tests/failure_injection/ -v

test-contract:  ## Run payment semantic contract tests
	uv run pytest tests/contract/ -v

test-property:  ## Run Hypothesis property tests
	uv run pytest tests/property/ -v

coverage:  ## Generate coverage report
	uv run pytest tests/ --cov=packages --cov=apps --cov-report=html --cov-report=term-missing
	@echo "HTML report: htmlcov/index.html"

lint:  ## Run ruff linter
	uv run ruff check packages/ apps/ tests/ scripts/
	uv run black --check packages/ apps/ tests/ scripts/

format:  ## Auto-format code
	uv run ruff check --fix packages/ apps/ tests/ scripts/
	uv run black packages/ apps/ tests/ scripts/

demo:  ## Run interactive demo script
	uv run python scripts/demo.py

db-init:  ## Create database tables
	uv run python -c "from packages.domain.payments.models import Base; from sqlalchemy import create_engine; import os; engine = create_engine(os.environ['DATABASE_URL']); Base.metadata.create_all(engine)"

up:  ## Start all services
	docker-compose up -d

down:  ## Stop all services
	docker-compose down

clean:  ## Remove generated artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete; \
	find . -name ".coverage" -delete; \
	rm -rf htmlcov/ .pytest_cache/; \
	rm -f packages/ml/models/*.pkl packages/ml/simulation/*.parquet; \
	echo "Cleaned."
