.PHONY: help check-uv \
	build changelog clean docs format format-check lint live-docs mypy \
	publish python sync test-figs tests tests-full upgrade

ifeq ($(OS),Windows_NT)
  UV_VERSION := $(shell uv --version 2> NUL)
  PYTHON_VERSION := python
else
  UV_VERSION := $(shell command uv --version 2> /dev/null)
  PYTHON_VERSION := python3
endif

help: ## List all commands.
	@echo -e "\nThis makefile executes mostly uv commands. To view all uv commands available run 'uv help'."
	@echo -e "\n\033[1mAVAILABLE COMMANDS\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9 -]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 | "sort"}' $(MAKEFILE_LIST)

check-uv: ## Check if uv is installed.
ifndef UV_VERSION
	@echo "Please install uv first. See https://docs.astral.sh/uv/ for instructions."
	@exit 1
else
	@echo "Found ${UV_VERSION}";
endif

build: clean check-uv sync ## Build distribution.
	uv build

changelog: check-uv sync ## Generate CHANGELOG.md
	uv run git-cliff v1.0.7..HEAD --config cliff.toml --output CHANGELOG.md

clean: ## Remove existing builds.
	rm -rf build dist .egg aimbat.egg-info docs/build site

docs: check-uv sync changelog ## Build html docs.
	uv run python -m aimbat._config > docs/usage/defaults-table.md
	uv run zensical build --clean

format: check-uv ## Sort imports and format code.
	uv run ruff check --fix .
	uv run ruff format .

format-check: check-uv ## See what 'make format' would change.
	uv run ruff check  --diff .
	uv run ruff format --diff .

lint: check-uv ## Run all linting checks.
	uv run ruff check  .
	uv run ruff format --check .

live-docs: check-uv sync ## Live build html docs. They are served on http://localhost:8000
	uv run python -m aimbat._config > docs/usage/defaults-table.md
	uv run zensical serve

mypy: check-uv ## Run typing tests with pytest.
	uv run pytest --mypy -m mypy src tests

python: check-uv ## Start an interactive python shell in the project virtual environment.
	uv run python

sync: check-uv ## Install this project and its dependencies in a virtual environment.
	uv sync --locked --all-extras

test-figs: check-uv ## Generate baseline figures for testing (then manually move them to the test directories).
	uv run py.test --mpl-generate-path=baseline

tests: check-uv mypy ## Run tests with pytest (excludes slow functional tests).
	uv run pytest --cov --cov-report=term-missing --cov-report=html --mpl -m "not slow"

tests-full: check-uv mypy ## Run all tests including slow functional tests.
	uv run pytest --cov --cov-report=term-missing --cov-report=html --mpl

upgrade: check-uv ## Upgrade dependencies to their latest versions.
	uv sync --upgrade
