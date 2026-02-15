# Changelog

All notable changes to the **AIMBAT** project will be documented in this file.

## [Unreleased]

### ⚙️ DevOps & Infrastructure

- Artifact@v4

### 🐛 Bug Fixes

- Fix type hint
- Fix importlib error for Python 3.7
- Fix typo on readme
- Listing snapshots when there were non causes error

### 📚 Documentation

- Correct links in badges
- Add AIMBAT workflow
- Link to contributros.md in root folder
- Update data section
- Add notebook to docs ([#168](https://github.com/pysmo/aimbat/issues/168))
- Add CNAME file
- Installation instructions using uv ([#190](https://github.com/pysmo/aimbat/issues/190))
- Add asciinema

### 🔍 Other Changes

- Create CNAME
- Switch from pipenv to poetry
- Add new aimbat cli and setup defaults framework
- Remove old stuff and add aimbat V2 files.
- Add github actions and initial tests for the cli
- Don't fail-fast (i.e. continue checks for other python versions)
- Add command to download sample data
- Use descriptors for defaults
- Merge pull request #109 from pysmo/descriptor-defaults

Use descriptors for defaults
- Cleanup aimbat defaults class
- Merge branch 'aimbat_V2'
- Add checkdata command
- Merge branch 'checkdata'
- Rename package from pysmo.aimbat to aimbat ([#129](https://github.com/pysmo/aimbat/issues/129))

* rename package from pysmo.aimbat to aimbat
* add tox
* add workflows
* update deps
* Add docs packages to pyproject
- Setup docs structure ([#130](https://github.com/pysmo/aimbat/issues/130))

* Setup docs structure
- Cleanup defaults script
- Merge pull request #131 from pysmo/defaults

cleanup defaults script
- Add cli for project
- Merge pull request #132 from pysmo/cli-project

add cli for project
- Switch to using sqlmodel to save project metadata.
- Merge pull request #133 from pysmo/project-defaults

Switch to using sqlmodel to save project metadata.
- Add devcontainer config
- Add .tox and nohup.out to gitignore
- Add autodoc to docs ([#134](https://github.com/pysmo/aimbat/issues/134))

* Add autodoc to docs

* Dont lint docs foler with flake8
- Merge "command" files into "lib" files.
- Merge pull request #135 from pysmo/move-commands-into-lib

Merge "command" files into "lib" files.
- Update Readme
- Fix text alignment
- Add accent colour to theme and add watch directory to make live-docs
- Add id column to default table
- Merge pull request #136 from pysmo/defaults-table

refactor: add id column to default table
- Merge pull request #137 from pysmo/docs-flowchart

docs: add AIMBAT workflow
- Merge pull request #139 from pysmo/checkdata

feat: initial checks in checkdata lib
- Switch to formatting with black
- Ignore black commit in git blame
- Merge pull request #140 from pysmo/black

Introduce Black formatting to project
- Bump urllib3 from 2.0.4 to 2.0.7

Bumps [urllib3](https://github.com/urllib3/urllib3) from 2.0.4 to 2.0.7.
- [Release notes](https://github.com/urllib3/urllib3/releases)
- [Changelog](https://github.com/urllib3/urllib3/blob/main/CHANGES.rst)
- [Commits](https://github.com/urllib3/urllib3/compare/2.0.4...2.0.7)

---
updated-dependencies:
- dependency-name: urllib3
  dependency-type: indirect
...

Signed-off-by: dependabot[bot] <support@github.com>
- Merge pull request #143 from pysmo/dependabot/pip/urllib3-2.0.7

Bump urllib3 from 2.0.4 to 2.0.7
- Bump pillow from 10.0.0 to 10.0.1

Bumps [pillow](https://github.com/python-pillow/Pillow) from 10.0.0 to 10.0.1.
- [Release notes](https://github.com/python-pillow/Pillow/releases)
- [Changelog](https://github.com/python-pillow/Pillow/blob/main/CHANGES.rst)
- [Commits](https://github.com/python-pillow/Pillow/compare/10.0.0...10.0.1)

---
updated-dependencies:
- dependency-name: pillow
  dependency-type: indirect
...

Signed-off-by: dependabot[bot] <support@github.com>
- Merge pull request #142 from pysmo/dependabot/pip/pillow-10.0.1

Bump pillow from 10.0.0 to 10.0.1
- Add py312 to matrix
- Merge pull request #144 from pysmo/py312

chore: add py312 to matrix
- Merge pull request #149 from pysmo/add-data

feat: add add-data to project
- Bump actions/setup-python from 4 to 5

Bumps [actions/setup-python](https://github.com/actions/setup-python) from 4 to 5.
- [Release notes](https://github.com/actions/setup-python/releases)
- [Commits](https://github.com/actions/setup-python/compare/v4...v5)

---
updated-dependencies:
- dependency-name: actions/setup-python
  dependency-type: direct:production
  update-type: version-update:semver-major
...

Signed-off-by: dependabot[bot] <support@github.com>
- Merge pull request #150 from pysmo/dependabot/github_actions/actions/setup-python-5

Bump actions/setup-python from 4 to 5
- Bump codecov/codecov-action from 3 to 4

Bumps [codecov/codecov-action](https://github.com/codecov/codecov-action) from 3 to 4.
- [Release notes](https://github.com/codecov/codecov-action/releases)
- [Changelog](https://github.com/codecov/codecov-action/blob/main/CHANGELOG.md)
- [Commits](https://github.com/codecov/codecov-action/compare/v3...v4)

---
updated-dependencies:
- dependency-name: codecov/codecov-action
  dependency-type: direct:production
  update-type: version-update:semver-major
...

Signed-off-by: dependabot[bot] <support@github.com>
- Merge pull request #151 from pysmo/dependabot/github_actions/codecov/codecov-action-4

Bump codecov/codecov-action from 3 to 4
- Bump actions/checkout from 3 to 4

Bumps [actions/checkout](https://github.com/actions/checkout) from 3 to 4.
- [Release notes](https://github.com/actions/checkout/releases)
- [Changelog](https://github.com/actions/checkout/blob/main/CHANGELOG.md)
- [Commits](https://github.com/actions/checkout/compare/v3...v4)

---
updated-dependencies:
- dependency-name: actions/checkout
  dependency-type: direct:production
  update-type: version-update:semver-major
...

Signed-off-by: dependabot[bot] <support@github.com>
- Merge pull request #153 from pysmo/dependabot/github_actions/actions/checkout-4

Bump actions/checkout from 3 to 4
- Merge pull request #155 from pysmo/fix-artifactsV4

ci: artifact@v4
- Merge pull request #156 from pysmo/data-list

feat: list data
- Merge pull request #159 from pysmo/parameter-tables

feat: add parameters to data
- Merge pull request #162 from pysmo/snapshots

feat: add parameter snapshots
- Merge pull request #163 from pysmo/docs-data

docs: update data section
- Merge pull request #164 from pysmo/utils-plotseis

feat: add plotseis
- Merge pull request #166 from pysmo/icecream

feat: add icecream to print debug information
- Merge pull request #169 from pysmo/event-select

feat: add event select function and cli command
- Bump codecov/codecov-action from 4 to 5

Bumps [codecov/codecov-action](https://github.com/codecov/codecov-action) from 4 to 5.
- [Release notes](https://github.com/codecov/codecov-action/releases)
- [Changelog](https://github.com/codecov/codecov-action/blob/main/CHANGELOG.md)
- [Commits](https://github.com/codecov/codecov-action/compare/v4...v5)

---
updated-dependencies:
- dependency-name: codecov/codecov-action
  dependency-type: direct:production
  update-type: version-update:semver-major
...

Signed-off-by: dependabot[bot] <support@github.com>
- Merge pull request #167 from pysmo/dependabot/github_actions/codecov/codecov-action-5

Bump codecov/codecov-action from 4 to 5
- Split lib and cli files to speed up cli ([#170](https://github.com/pysmo/aimbat/issues/170))
- Merge pull request #173 from pysmo/feat-filter-tables

feat: print table data for active events by default
- Merge pull request #174 from pysmo/feat-rollback

feat: add snapshot rollback
- Move AimbatDefaults class to other models and rename some things.
- Merge pull request #175 from pysmo/move-defaults

refactor: move AimbatDefaults class to other models and rename some t…
- Save active event in a single row table
- Merge pull request #176 from pysmo/active-event-table

refactor: save active event in a single row table
- Add test data for 3 events instead of just a single sac file
- Merge pull request #177 from pysmo/test-data

test: add test data for 3 events instead of just a single sac file
- Move defaults directly to model instead of the yaml nonsense
- Merge pull request #178 from pysmo/simplify-defaults

refactor: move defaults directly to model instead of the yaml nonsense
- Merge pull request #179 from pysmo/more-enums

feat: add enum types for Event and Seismogram parameters
- Switch to uv
- Merge pull request #186 from pysmo/switch-to-uv

chore: switch to uv
- Merge pull request #187 from pysmo/plot-cmd

feat: add plot command group
- Merge pull request #188 from pysmo/iccs-tw-pick

feat: add time window picker
- Add logging ([#189](https://github.com/pysmo/aimbat/issues/189))

* feat: Add logging

* format tutorial

* add logging to checkdata

* remove unused import
- Rename some commands to group them a bit better
- Merge pull request #191 from pysmo/rename-commands

refactor: rename some commands to group them a bit better
- Use more classes for tests ([#192](https://github.com/pysmo/aimbat/issues/192))
- Rely on pydantic for validation instead of doing it manually ([#193](https://github.com/pysmo/aimbat/issues/193))
- Merge pull request #194 from pysmo/iccs-select-ccnorm

feat: add iccs ccnorm selector
- Update to new pysmo names
- Merge pull request #195 from pysmo/iccs-select-ccnorm

chore: update to new pysmo names
- Merge pull request #196 from pysmo/active-event-db-trigger

feat: use a trigger to ensure only one event can be active
- Use uuid as datbase id instead of int
- Merge pull request #197 from pysmo/uuid-keys

refactor: use uuid as datbase id instead of int
- Merge pull request #198 from pysmo/update-iccs-options

feat: update cli and lib to use new iccs options
- Use window_pre and window_post as defaults instead of the whole timewindow
- Merge pull request #199 from pysmo/window-defaults

refactor: use window_pre and window_post as defaults instead of the w…
- Merge pull request #200 from pysmo/fix-uuid-when-none-available

fix: listing snapshots when there were non causes error
- Merge pull request #201 from pysmo/feat-delete-items

feat: add ability to delete seismograms, events, and stations from pr…
- Better relationships between tables
- Merge pull request #202 from pysmo/reverse-data-dep

refactor: better relationships between tables
- Use env vars for defaults
- Merge pull request #203 from pysmo/dotenv

refactor: use env vars for defaults
- Merge pull request #204 from pysmo/pydantic-settings

feat: use pydantic-settings
- Single uuid function for all classes
- Merge pull request #205 from pysmo/single-uuid-func

refactor: single uuid function for all classes
- Make data reading more modular
- Merge pull request #206 from pysmo/datasource

refactor: make data reading more modular
- Merge pull request #207 from pysmo/feat-dump

feat: add dump option to main tables
- Merge pull request #208 from pysmo/short-exceptions

feat: add simple errors to cli
- Merge pull request #209 from pysmo/asciinema

docs: add asciinema
- Merge pull request #210 from pysmo/station-loc-channel

feat: use channel and location in station table
- Merge pull request #211 from pysmo/feat-use-pysmo-iccs-defaults

feat: use pysmo defaults for ICCS
- Move aimbat source to src directory
- Merge pull request #212 from pysmo/mv-src

refactor: move aimbat source to src directory

### 🚀 New Features

- Initial checks in checkdata lib
- Add-data to project
- List data
- Add parameters to data
- Add parameter snapshots
- Add plotseis
- Add pyqtgraph plot option ([#165](https://github.com/pysmo/aimbat/issues/165))
- Add icecream to print debug information
- Add event select function and cli command
- Switch to typer ([#172](https://github.com/pysmo/aimbat/issues/172))
- Print table data for active events by default
- Add snapshot rollback
- Add enum types for Event and Seismogram parameters
- Add initial iccs functionality ([#185](https://github.com/pysmo/aimbat/issues/185))
- Add plot command group
- Add time window picker
- Add iccs ccnorm selector
- Use a trigger to ensure only one event can be active
- Update cli and lib to use new iccs options
- Add ability to delete seismograms, events, and stations from project
- Use pydantic-settings
- Add dump option to main tables
- Add simple errors to cli
- Use channel and location in station table
- Use pysmo defaults for ICCS

