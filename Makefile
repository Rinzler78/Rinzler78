.PHONY: setup validate-data generate validate test coverage lint format \
        format-check security audit precommit check

setup:
	uv pip install -e ".[dev]"
	# default_install_hook_types in .pre-commit-config.yaml covers
	# pre-commit, pre-push and pre-merge-commit in this one call.
	pre-commit install --install-hooks

validate-data:
	python scripts/validate_data.py

generate:
	python scripts/generate.py

validate:
	python scripts/validate.py

test:
	pytest -q

coverage:
	pytest -q --cov --cov-report=term-missing --cov-fail-under=90

lint:
	ruff check scripts tests

format:
	ruff format scripts tests

format-check:
	ruff format --check scripts tests

security:
	bandit -c pyproject.toml -r scripts

audit:
	pip-audit

precommit:
	pre-commit run --all-files

check: validate-data generate validate lint format-check security coverage
	git diff --exit-code
