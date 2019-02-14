.PHONY: docs dist clean test develop shell

PIPENV := $(shell command -v pipenv 2> /dev/null)

init:
ifndef PIPENV
	pip install pipenv
endif
	pipenv install --dev

develop:
	pipenv run python setup.py develop

test:
	pipenv run py.test -v tests

shell:
	pipenv shell

docs: develop
	cd docs && pipenv run make html

dist: clean
	pipenv run python setup.py sdist bdist_wheel

clean:
	rm -rf build dist .egg pysmo.aimbat.egg-info docs/build
