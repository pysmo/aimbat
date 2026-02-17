# Changelog

All notable changes to the **AIMBAT** project will be documented in this file.

## [Unreleased]

### ⚙️ DevOps & Infrastructure

- Artifact@v4

### 🎨 Styling

- Switch to formatting with black

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
- Switch to zensical

### 📦 Miscellaneous

- Ignore black commit in git blame
- Add py312 to matrix
- Switch to uv
- Rename some commands to group them a bit better
- Update to new pysmo names

### 🔍 Other Changes

- Create CNAME
- Switch from pipenv to poetry
- Add new aimbat cli and setup defaults framework
- Remove old stuff and add aimbat V2 files.
- Add github actions and initial tests for the cli
- Don't fail-fast (i.e. continue checks for other python versions)
- Add command to download sample data
- Use descriptors for defaults
- Cleanup aimbat defaults class
- Add checkdata command
- Rename package from pysmo.aimbat to aimbat ([#129](https://github.com/pysmo/aimbat/issues/129))
- Setup docs structure ([#130](https://github.com/pysmo/aimbat/issues/130))
- Cleanup defaults script
- Add cli for project
- Switch to using sqlmodel to save project metadata.
- Add devcontainer config
- Add .tox and nohup.out to gitignore
- Add autodoc to docs ([#134](https://github.com/pysmo/aimbat/issues/134))
- Update Readme
- Fix text alignment
- Add accent colour to theme and add watch directory to make live-docs
- Add logging ([#189](https://github.com/pysmo/aimbat/issues/189))

### 🔧 Refactoring

- Add id column to default table
- Split lib and cli files to speed up cli ([#170](https://github.com/pysmo/aimbat/issues/170))
- Move AimbatDefaults class to other models and rename some things.
- Save active event in a single row table
- Move defaults directly to model instead of the yaml nonsense
- Use more classes for tests ([#192](https://github.com/pysmo/aimbat/issues/192))
- Rely on pydantic for validation instead of doing it manually ([#193](https://github.com/pysmo/aimbat/issues/193))
- Use uuid as datbase id instead of int
- Use window_pre and window_post as defaults instead of the whole timewindow
- Better relationships between tables
- Use env vars for defaults
- Single uuid function for all classes
- Make data reading more modular
- Move aimbat source to src directory

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
- Add bandpass filtering ([#214](https://github.com/pysmo/aimbat/issues/214))

### 🧪 Testing

- Add test data for 3 events instead of just a single sac file

