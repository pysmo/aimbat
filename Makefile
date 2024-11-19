.PHONY: help check-poetry install update lint test-figs test-tutorial tests \
	mypy docs docs-export live-docs notebook build publish clean shell python \
	format format-check

ifeq ($(OS),Windows_NT)
  POETRY_VERSION := $(shell poetry --version 2> NUL)
  PYTHON_VERSION := python
else
  POETRY_VERSION := $(shell command poetry --version 2> /dev/null)
  PYTHON_VERSION := python3
endif

help: ## List all commands.
	@echo -e "\nThis makefile executes mostly poetry commands. To view all poetry commands available run 'poetry help'."
	@echo -e "\n\033[1mAVAILABLE COMMANDS\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9 -]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 | "sort"}' $(MAKEFILE_LIST)

check-poetry: ## Check if Poetry is installed.
ifndef POETRY_VERSION
	@echo "Please install Poetry first. See https://python-poetry.org for instructions."
	@exit 1
else
	@echo "Found ${POETRY_VERSION}";
endif

install: check-poetry ## Install this project and its dependencies in a virtual environment.
	poetry install

update: check-poetry ## Update dependencies to their latest versions.
	poetry update

lint: check-poetry ## Check formatting with black and lint code with ruff.
	poetry run black . --check --diff --color
	poetry run ruff check .

test-figs: check-poetry ## Generate baseline figures for testing. Only run this if you know what you are doing!
	poetry run py.test --mpl-generate-path=tests/baseline

test-tutorial: check-poetry ## Check if the tutorial notebook runs error-free.
	poetry run py.test --nbmake docs/examples/tutorial.ipynb

tests: check-poetry mypy test-tutorial ## Run all tests with pytest.
	poetry run pytest --mypy --cov=aimbat --cov-report=term-missing --mpl -v

mypy: check-poetry ## Run typing tests with pytest.
	poetry run pytest --mypy -m mypy -v aimbat

docs: check-poetry install ## Build html docs.
	poetry run mkdocs build

docs-export: check-poetry install ## Export installed package information to docs/requirements.txt.
	poetry export --only=docs -o docs/requirements.txt

live-docs: check-poetry install ## Live build html docs. They are served on http://localhost:8000
	poetry run mkdocs serve -w README.md -w aimbat

notebook: check-poetry install ## Run a jupyter notebook in the poetry environment
	poetry run jupyter-lab

build: clean check-poetry install ## Build distribution.
	poetry build

publish: check-poetry build ## Publish package to PyPI (you will be asked for PyPI username and password).
	poetry publish

clean: ## Remove existing builds.
	rm -rf build dist .egg aimbat.egg-info docs/build site

shell: check-poetry ## Start a shell in the project virtual environment.
	poetry shell

python: check-poetry ## Start an interactive python shell in the project virtual environment.
	poetry run python

format: check-poetry ## Format python code with black.
	poetry run black .

format-check: check-poetry ## See what running 'make format' would change instead of actually running it.
	poetry run black . --diff --color
