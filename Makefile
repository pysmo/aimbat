.PHONY: help check-uv install upgrade lint test-figs test-tutorial tests \
	mypy docs docs-export live-docs notebook build publish clean python \
	format format-check

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
	uv sync

upgrade: check-uv ## Upgrade dependencies to their latest versions.
	uv sync --upgrade

lint: check-uv ## Check formatting with black and lint code with ruff.
	uv run black . --check --diff --color
	uv run ruff check .

test-figs: check-uv ## Generate baseline figures for testing.
	uv run py.test --mpl-generate-path=baseline

test-tutorial: check-uv ## Check if the tutorial notebook runs error-free.
	uv run py.test --nbmake docs/examples/tutorial.ipynb

tests: check-uv mypy test-tutorial ## Run all tests with pytest.
	uv run pytest --cov=aimbat --cov-report=term-missing --cov-report=html --mpl

mypy: check-uv ## Run typing tests with pytest.
	uv run pytest --mypy -m mypy aimbat tests

docs: check-uv install ## Build html docs.
	uv run mkdocs build

docs-export: check-uv install ## Export installed package information to docs/requirements.txt.
	uv export --only=docs -o docs/requirements.txt

live-docs: check-uv install ## Live build html docs. They are served on http://localhost:8000
	uv run mkdocs serve -w README.md -w aimbat

notebook: check-uv install ## Run a jupyter notebook in the uv environment
	uv run jupyter-lab

build: clean check-uv install ## Build distribution.
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
