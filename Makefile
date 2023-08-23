.PHONY: help check-poetry install update lint test-figs tests mypy docs docs-export \
	live-docs notebook build publish clean shell python

ifeq ($(OS),Windows_NT)
  POETRY_VERSION := $(shell poetry --version 2> NUL)
  PYTHON_VERSION := python
else
  POETRY_VERSION := $(shell command poetry --version 2> /dev/null)
  PYTHON_VERSION := python3
endif

help: ## List all commands.
	@echo -e "\nThis makefile executes mostly poetry commands. To view all poetry commands availabile run 'poetry help'."
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

lint: check-poetry ## Lint code with flake8
	poetry run flake8 --statistics

test-figs: check-poetry ## Generate baseline figures for testing. Only run this if you know what you are doing!
	poetry run py.test --mpl-generate-path=tests/baseline

tests: check-poetry lint mypy ## Run all tests with pytest.
	poetry run pytest --mypy --cov=aimbat --cov-report=xml --mpl -v tests

mypy: check-poetry ## Run typing tests with pytest.
	poetry run pytest --mypy -m mypy -v aimbat

docs: check-poetry install ## Build html docs.
	poetry run mkdocs build

docs-export: check-poetry install ## Export installed package information to docs/requirements.txt.
	poetry export --only=docs -o docs/requirements.txt

live-docs: check-poetry install ## Live build html docs. They are served on http://localhost:8000
	poetry run mkdocs serve

notebook: check-poetry install ## Run a jupyter-notebook in the poetry environment
	poetry run jupyter-notebook

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
