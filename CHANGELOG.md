# Changelog

All notable changes to the **AIMBAT** project will be documented in this file.

## [Unreleased]

### ⚙️ DevOps & Infrastructure

- Artifact@v4
- Use vcs versioning

### 🎨 Styling

- Switch to formatting with black

### 🐛 Bug Fixes

- Fix type hint
- Fix importlib error for Python 3.7
- Fix typo on readme
- Listing snapshots when there were non causes error
- Debug flag from cli commands didn't do anything

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
- Re-arange api reference
- Restructure usage section into workflow-based pages and TUI improvements

### 📦 Miscellaneous

- Ignore black commit in git blame
- Add py312 to matrix
- Switch to uv
- Rename some commands to group them a bit better
- Update to new pysmo names
- Update deps and cleanup code

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
- Use pandas Timestamp and Timedelta
- Improve docstrings, io DI pattern, and data source terminology
- **(core)** Re-arange core, move set_default_event and friends out of core.
- Active event -> default event
- Use default event concept only for cli commands
- Update plot seismograms.
- Remove dead code ([#231](https://github.com/pysmo/aimbat/issues/231))
- Quality stats integrated into read models and tui
- Quality stats integrated into read models and tui ([#232](https://github.com/pysmo/aimbat/issues/232))
- Tighten note constraint, consolidate formatters, improve TUI staleness handling
- Split TUI panels into own module and unify duplicated logic

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
- Add mccc
- Add in-memory seismogram data cache
- Add JSON datasource
- Add TUI and supporting changes
- Implement interactive shell and major documentation update for v2
- Store ICCS/MCCC quality metrics in database
- Add JSON export functionality for snapshot results

### 🧪 Testing

- Add test data for 3 events instead of just a single sac file
- Add integration and functional test suite ([#218](https://github.com/pysmo/aimbat/issues/218))

## [1.0.7](https://github.com/pysmo/aimbat/compare/v1.0.6...v1.0.7) - 2021-09-06

### 🔍 Other Changes

- Update setup and add manifest

## [1.0.6](https://github.com/pysmo/aimbat/compare/v1.0.5...v1.0.6) - 2021-09-05

### 🐛 Bug Fixes

- Fix email address

### 🔍 Other Changes

- Add vscode settings to gitignore
- A bit of code cleanup ([#92](https://github.com/pysmo/aimbat/issues/92))
- Add pyside2 to pipfile
- Simple test homepage
- Move index.html to root folder
- Update issue templates
- Create bug report form
- Remove empty lines in bug_report.yml
- Tweak bug_report.yml
- Remove invalid keys
- Add title placeholder
- Update Suzan's and Xiaoting's url
- Make Makefile more userfriendly and update 3rd party packages
- Remove __init__.py to avoid conflicts with pysmo
- Remove extra loop that caused header values to be written to the wrong sac files

## [1.0.5](https://github.com/pysmo/aimbat/compare/v1.0.4...v1.0.5) - 2019-08-18

### 🐛 Bug Fixes

- Fix bug of datamem in algiccs
- Fix bug in sync window and pick in ttguiqt.py
- Fix bug in ttqtgui.py. GUI crashed when clicking 'Map Delay Times'

### 🔍 Other Changes

- Copy docs from aimbat-docs
- Build without fortran if it is unavailable.
- Code cleanup
- Code cleanup
- Use importlib instead of exec
- Removed now obsolete lines. Always tries to import from fortan first.
- Make setup a bit more verbose, define function for loading CC function.
- Change travis to use only python 3.6 and 3.7
- Change travis matrix
- Initial pipenv setup
- Update some package versions.
- Update dependencies.
- Move src/pysmo/aimbat to pysmo/aimbat. Move tests to own dir.
- Adjust setup.py to new paths
- Osx travis ([#87](https://github.com/pysmo/aimbat/issues/87))
- Update docs ([#88](https://github.com/pysmo/aimbat/issues/88))
- Overwrite mpl backend to TkAgg
- Update docs on the new qt gui and more ttdefault.conf parameters
- More docs updated for the new qtgui
- Update docs on qttpick
- Update usage doc on PickingTravelTimes
- Update docs on qt gui
- Edit changelog
- Edit changelog

## [1.0.4](https://github.com/pysmo/aimbat/compare/v1.0.3...v1.0.4) - 2018-12-24

### 🔍 Other Changes

- Add sacp1 button to the main GUI
- File name change
- Plot a subset of traces
- Plot a subset of traces
- Plot a subset of traces
- Plot a subset of traces 4
- Plot a subset of traces 5

## [1.0.3](https://github.com/pysmo/aimbat/compare/v1.0.2...v1.0.3) - 2018-12-06

### 🔍 Other Changes

- Filt parameter and changelog
- Stick trace label to the left edge of viewbox
- Add label for cursor location
- Xy range and limit
- Reset time window for stack

## [1.0.2](https://github.com/pysmo/aimbat/compare/v1.0.1...v1.0.2) - 2018-12-05

### 🔍 Other Changes

- Typo
- Map delay times by matplotlib.pyplot
- Changelog

## [1.0.1](https://github.com/pysmo/aimbat/compare/v1.0.0...v1.0.1) - 2018-12-05

### 🐛 Bug Fixes

- Fix bug in manual ppt after sorting
- Fix bug in manual ppt after iccs and mccc
- Fix bugs in manual trace selection and phase picking
- Fix bug in "Refine" step

### 🔍 Other Changes

- Edit change log
- Update requirements to install pysmo v0.7.1.
- Minor change in station label
- Option to not use QScrollArea
- Update trace label after running align or refine
- GUI setting changes
- Adjust to new SacIO behavior.
- Minor GUI setting changes
- Add xcorr_full_polarity function to support mccc without changing polarity
- Xcorr avoid reverse polarity

## [1.0.0](https://github.com/pysmo/aimbat/compare/v0.9.0...v1.0.0) - 2018-12-03

### 🐛 Bug Fixes

- Fix bug in loading stack file
- Fix bug in loading stack file
- Fix bug in reading and saving filter parameters

### 🔍 Other Changes

- Range(n) format
- Stack data
- Add pyqtgraph to requirement
- Add line in setup.py to make use_scm_version work.
- Add pyqtgraph to requirement
- Filter on stack
- Filter on stack
- Add sorting by header diff like T1-T0
- Setup
- Add delay time plot to plotutils

## [0.9.0](https://github.com/pysmo/aimbat/compare/v0.2...v0.9.0) - 2018-12-01

### 🔍 Other Changes

- Add requirements to setup.py and use scm_version instead of setting it manually.
- Add requirements-travis.txt
- Use pyqtgraph for fast plotting
- Add all non-example scripts to setup.py entry_points
- Remove obsolete scripts but keep example scripts.
- Add sacp2GUI

## [0.2] - 2018-06-03

### ⚙️ DevOps & Infrastructure

- Building out the figure

### 🐛 Bug Fixes

- Fixed spelling mistakes
- Fixed the sorting
- Fixed layout again
- Fixed axs
- Fixed freq probem
- Fixed freq
- Fixed front buttons
- Fixed dumb mistake
- Fixing
- Fixed
- Fixed error
- Fix proke test
- Fixed
- Fixed saco
- Fixed
- Fix bug in sacpickle.py for sacio
- Fixed colors
- Fixed filter error
- Fixed bug

### 🔍 Other Changes

- Initial commit
- Initial import
- Modify in scripts/egplot.py and scripts/egsac.py:
- Ver 0.1.2
- Ver 0.1.2
- Ver 0.1.2
- Added warning
- Update README.md
- Delete Readme.txt
- Update README.md
- Update README.md
- These are not needed
- Added button to allow u to go to front
- Update Version.txt
- Update Version.txt
- Added axes for info
- Adding text nicely
- Added summary
- Removed debug code
- Update Version.txt
- Changed magnitude
- Update README.md
- Update README.md
- Added some comments
- Added sort button
- Expanded size
- Added backed
- Sth works
- Work to this pt
- Some basic functionality works
- Needs more immediate action
- Added more buttons
- Buttons work now
- Redrawing fig
- Stack will redraw
- Sorting gui added
- Disconnecting
- Disconnect fixed
- Update Version.txt
- Add summary field
- Added explanation
- Zoom back if you enlarged
- Update Version.txt
- Added status
- Added filter button
- REVERT TO HERE IF U MESS UP
- Got the right data
- This is working
- Added decent axes
- Added some sort of graph
- Done with plots
- No do over
- Part of it is colored
- More filters
- REVERT HERE IF WRONG
- Resize added
- Able to revert
- Added filtering
- Amplitude spectrun
- Need to make
- Normalized
- No more old signal
- Hit added
- Added labels
- Butter
- Order is bugg
- Update README.md
- Update README.md
- Update README.md
- Update README.md
- Update README.md
- Update README.md
- Update README.md
- Removed most dumb mistakes
- Unnormalized
- Choose to normaliz
- Revert here if wrong
- Lots of bugs
- Debugged a bit
- Amplitude is wrong
- Also plot clusters
- No need zoom
- Rid of buttons
- Filtering is right
- Freq we got suck
- Wipe before begin
- Somethings wrong again
- Something is very very wrong
- Removed rewrite
- STUPID ME
- This looks right again
- Changed order place
- Order is screwed
- Order works now
- Hopefully this is what we want
- Removed debugging code
- Plot again
- Ok
- Application works
- Tweak
- This sucks
- Filter is applied now
- Filter fix
- Not error yet
- Disconnected
- Nearly done
- Low sort of works
- Corrected general filter
- Works but buggy
- Bug
- Works
- Application works
- Added
- Defended
- Aimbat change
- Added obspy hdr
- Write to trace
- Sac added
- Sac added
- Work to here
- Way
- Added more headers
- Backend always ok now
- Added avg gcarc avg
- Order 2 default
- Unapply filter
- No need tkinter
- Rid of some closing errors
- Rid one more error
- Stop being angry sorting
- Finished is ok
- Btn disconnect problem
- Not need init everything
- Correct
- Close all
- Removed one problem
- Backend still problematic
- Changed to opts
- Removed unneeded
- Built structure
- Interface made
- Need to pass opts in
- Ready to override
- Filtering
- Able to override
- Choose or not
- Add appropriate alerts
- Disconnect
- Removed weired problem
- Write params to file
- Override filter defaults
- Life sucks
- Ok or not
- Shiftinf
- Tidied sort
- Be more responsive
- Responsive text
- Added response
- Mobile
- Revert
- Added some non working test
- Kinda works setup
- Weird
- Import more
- This has worked
- Importing files
- 4 tests here
- New problem
- Yolo it works
- Removed weird code
- 4 tests work
- Adding tests
- Folders exist
- Added travis yml
- Added requirements
- Install
- Scipy
- Fortran
- Lol
- Nned
- YOLO running now
- Data opts
- Added new name
- More
- Twk
- Rm pt
- Added back
- Better test name
- Run many
- New way to run
- Update README.md
- Update README.md
- Update README.md
- Update README.md
- Delete .travis.yml
- Delete requirements.txt
- Update README.md
- Update README.md
- Update README.md
- Update README.md
- Update README.md
- Update README.md
- Update README.md
- Added more tests
- Added event
- Sanity check passing
- Sort by file index
- Adding the sorting
- Need ned library
- Need to add real fig
- Seems to click button
- Fig exists
- Runs ok
- This is annoying
- Printing event messes it up
- Tweak
- Added view tests
- Filenames ok
- Order ok
- Split more
- Finally got click work
- High freq works
- Clicking ok
- Close
- Unapply
- Adding
- Need to trigger mouse event
- Had to separate
- Works ok
- Correct test
- Check if file exists
- Update
- Added zip mode
- Read ok
- Check filer
- Update README.md
- Adding freq
- Mv filter worjs
- Compartmentalize more
- Separated to mvc
- Added spike
- Second frequency
- Freq spike
- Rid spike
- Multiple
- Params right
- How to save stuff
- Save data
- Saving successfully
- This is probably right
- Need to stark
- Clicking the save button
- Write to different file
- Add to fake file
- Not equal
- Saving it right
- New override data
- Not equal headers
- Update README.md
- Setup to plot stations
- Thats dumb
- Thats better
- Get delay times
- Name is more meaningful
- Added lat long
- Plot elsewhere
- Ripped off the code
- Sort of looks ok
- Shifted to a class
- Added map
- PLOTTING BY DELAY TIMES
- Map
- Plot right
- Picking ok now
- WORST EVER
- Selected station
- Added station
- Added stations
- Added titles
- Added stations
- Added lib
- Changed place
- Added scripts
- Added stuff
- Plot
- Names
- Added getsta
- Sws
- Sws
- Ser
- Added
- Added
- Removed unneeded
- Rm map
- Rm stations
- Removed examples
- Rm plot
- Added more script
- Update README.md
- Update README.md
- Added
- Added models
- Added mdoel
- Getsta
- Removed
- Update README.md
- Plot sta
- Added back
- Update sacpickle.py
- Got delay times
- Changed coastline resolution to 'i' for nicer maps
- Removed onspy ref
- Save to main
- Get delay times
- Color by delay times
- Removed stla,lo,el from list of headers written in obj2sac
- Separated
- Output both files
- Sacppk.py uses getAxes from pickphase.py now to avoid key error on 'Shdo'
- GUI additions/removals and bug fixes
- Added option to run filter a second time in reverse
- 1. Changed map boundaries for mpl_toolkits.basemap.basemap
- Tag aimbat-0.2
- To tag aimbat-0.2

### 🧪 Testing

- Test fails
- Tested hour
- Test runs
- Test not working

