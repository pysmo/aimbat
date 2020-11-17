.PHONY: docs dist clean test develop shell lint

PIPENV := $(shell command -v pipenv 2> /dev/null)

init:
ifndef PIPENV
	pip install pipenv
endif
	pipenv install --dev

develop: init
	pipenv run python setup.py develop

lint:
	pipenv run pylint setup.py pysmo test

test: init
	pipenv run py.test -v tests

shell: init
	pipenv shell

docs: develop
	cd docs && pipenv run make html

dist: clean
	pipenv run python setup.py sdist bdist_wheel

clean:
	pipenv clean
	rm -rf build dist .egg pysmo.aimbat.egg-info docs/build
