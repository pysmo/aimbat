.PHONY: help check-uv build clean docs format format-check lint python sync tests upgrade

ifeq ($(OS),Windows_NT)
  UV_VERSION := $(shell uv --version 2> NUL)
else
  UV_VERSION := $(shell command uv --version 2> /dev/null)
endif

help: ## List all commands.
	@echo -e "\nThis makefile executes mostly uv commands. To view all uv commands available run 'uv help'."
	@echo -e "\n\033[1mCommands:\033[0m"
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

clean: ## Remove existing builds.
	rm -rf build dist .egg pysmo.aimbat.egg-info docs/build

docs: check-uv sync ## Build html docs.
	uv run make -C docs html

format: check-uv ## Sort imports AND format code.
	uv run ruff check --fix .
	uv run ruff format .

format-check: check-uv ## See what 'make format' would change.
	uv run ruff check --diff .
	uv run ruff format --diff .

lint: check-uv ## Run all linting checks.
	uv run ruff check .
	uv run ruff format --check .

python: check-uv ## Start an interactive python shell in the project virtual environment.
	uv run python

sync: check-uv ## Install this project and its dependencies in a virtual environment.
	uv sync --locked --extra dev

tests: check-uv ## Run all tests with pytest.
	uv run pytest

upgrade: check-uv ## Upgrade dependencies to their latest versions.
	uv sync --upgrade
