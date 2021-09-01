.PHONY: init install test-figs tests docs build clean shell help

POETRY_VERSION := $(shell command poetry --version 2> /dev/null)

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
	poetry run flake8 --statistics --max-line-length=120 --extend-exclude=old

test-figs: check-poetry ## Generate baseline figures for testing. Only run this if you know what you are doing!
	poetry run py.test --mpl-generate-path=tests/baseline

tests: check-poetry ## Run tests with pytest.
	poetry run py.test --cov=pysmo/aimbat --cov-report=xml --mpl -v tests

docs: install check-poetry ## Build html docs.
	poetry run make -C docs html

build: clean check-poetry ## Build distribution.
	poetry build

publish: check-poetry build ## Publish package to PyPI (you will be asked for PyPI username and password).
	poetry publish

clean: ## Remove existing builds.
	rm -rf build dist .egg pysmo.aimbat.egg-info docs/build

shell: check-poetry ## Start a shell in the project virtual environment.
	poetry shell
