.PHONY: docs dist clean tests develop shell lint init help

PIPENV_VERSION := $(shell command pipenv --version 2> /dev/null)

help: ## List all commands.
	@echo -e "\nThis makefile executes mostly pipenv commands. To view all pipenv commands availabile run 'pipenv --help'."
	@echo -e "\n\033[1mAVAILABLE COMMANDS\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9 -]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 | "sort"}' $(MAKEFILE_LIST)


check-pipenv: ## Check if Pipenv is installed. If not it is installed with pip.
ifndef PIPENV_VERSION
	@echo "Installing pipenv with pip"
	pip install pipenv
else
	@echo "Found ${PIPENV_VERSION}";
endif

install: check-pipenv ## Install this project's dependencies in a virtual environment.
	pipenv install --dev

develop: install ## Install this project in a virtual environment.
	pipenv run python setup.py develop

lint: check-pipenv ## Run pylint to check code quality.
	pipenv run pylint **/*.py

tests: check-pipenv ## Run unit tests.
	pipenv run pytest --cov=pysmo/aimbat --cov-report=xml --mpl -v tests

shell: check-pipenv ## Start a shell in the project virtual environment.
	pipenv shell

docs: develop ## Build html docs.
	cd docs && pipenv run make html

dist: clean ## Build distribution.
	pipenv run python setup.py sdist bdist_wheel

clean: check-pipenv ## Remove existing builds.
	pipenv clean
	rm -rf build dist .egg pysmo.aimbat.egg-info docs/build
