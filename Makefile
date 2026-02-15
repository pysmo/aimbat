.PHONY: help check-uv sync upgrade lint test-figs tests \
	mypy docs live-docs build publish clean python \
	format format-check changelog

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

sync: check-uv ## Install this project and its dependencies in a virtual environment.
	uv sync --locked --all-extras

upgrade: check-uv ## Upgrade dependencies to their latest versions.
	uv sync --upgrade

lint: check-uv ## Check formatting with black and lint code with ruff.
	uv run black . --check --diff --color
	uv run ruff check .

test-figs: check-uv ## Generate baseline figures for testing (then manually move them to the test directories).
	uv run py.test --mpl-generate-path=baseline

tests: check-uv mypy ## Run all tests with pytest.
	uv run pytest --cov --cov-report=term-missing --cov-report=html --mpl

mypy: check-uv ## Run typing tests with pytest.
	uv run pytest --mypy -m mypy src tests

docs: check-uv sync ## Build html docs.
	uv run zensical build --clean

live-docs: check-uv sync ## Live build html docs. They are served on http://localhost:8000
	uv run zensical serve

changelog: check-uv sync ## Generate CHANGELOG.md
	uv run git-cliff v1.0.7..HEAD --config cliff.toml --output CHANGELOG.md
	
build: clean check-uv sync ## Build distribution.
	uv build

publish: check-uv build ## Publish package to PyPI (you will be asked for PyPI username and password).
	uv publish

clean: ## Remove existing builds.
	rm -rf build dist .egg aimbat.egg-info docs/build site

python: check-uv ## Start an interactive python shell in the project virtual environment.
	uv run python

format: check-uv ## Format python code with black.
	uv run black .

format-check: check-uv ## See what running 'make format' would change instead of actually running it.
	uv run black . --diff --color
