Changelog
=========


aimbat-v1.0.5
-------------
Aug 17, 2019:
Main contributor: smlloyd, xlougeo.

* Lots of code clean and restructure, including src, docs, and tests. 
* Package installation: make fortran optional, update dependencis, update travis, setup pipenv.
* Update documentation.
* Bug fixes.


aimbat-v1.0.4
-------------
Dec 23, 2018:

* Add SAC P1 Button to the main GUI
* Plot only a subset of traces for faster data QC and (de)selection. All labels are plotted. Add a button to plot more traces


aimbat-v1.0.3
-------------
Dec 7, 2018:

* Some GUI setting changes


aimbat-v1.0.2
-------------
Dec 5, 2018:

* Add option to plot simple delay time map by matplotlib.pyplot


aimbat-v1.0.1
-------------
Dec 4, 2018:

* Fix bugs in changing trace selection status (QC), manual phase picking, and trace label.
* Change in GUI settings. Using right button dragging is enough and give up on QScrollArea.
* In cross-correlation, do not allow reverse polarity which causes cycle skipping too often.


aimbat-v1.0.0
-------------
Dec 3, 2018:
Main contributor: smlloyd:

* Use new pysmo.core.sac.SacIO (pysmo-pysmo-v0.7.0) instead of pysmo.sac.sacio.SacFile
* New setup.py:
   * Wrap all scripts into a callable function and add them to entry_point, e.g., aimbat-ttpick is automatically generated in your bin folder.
   * Use git commit/tag to determine version automatically.
   * Setup travis
* Package uploaded to pypi.org for each release since this.

Main contributor: xlougeo, ASankaran:
* SAC plotting and aimbat-ttpick are still using Matplotlib GUI.
* New GUI (aimbat-qttpick) using pyqtgraph for fast plotting. Similar user interactions as v0.3:
   * Key pressed event handler in pyqtgraph is redefined 
   * Use mouse to change time window and press key 'w' to set <-- work on stack only
   * Press key 't[0-9]' to set time picks like SAC PPK        <-- work on both stack and traces
   * Mouse click on waveform to change trace selection status <-- work on trace only
* Better separation between data and plot.
* Filter and sort are both in the main GUI controlled by a parameter tree.


aimbat-v0.3-alpha1
------------------
June 3, 2018:
Main contributor: xlougeo

* Upgrade to python3 (May not back-compatible with python2). No change in functionalities from v0.2.


aimbat-v0.2
-----------
Main contributor: lkloh. 
For changes made between Dec 19, 2012 (v0.1.2) and Aug 23, 2016

* Added a warning button if you hit ICCS-A or ICCS-B button, to make sure do did not hit it by accident. 
* Hitting one of those buttons will undo all the work you did in manually picking arrival times.
* Added a button to allow you to jump to the front page. Note that hitting MCCC again will do just that. 
* Added a summary of the event at the top right hand corner: Magnitude, Location, Depth
* Added a GUI to allow sorting of the seismograms according to header, time difference, file name, ...
* Added a button to return to original screen after you zoom in/out


aimbat-0.1.2
------------
Dec 19, 2012:
Main contributor: xlougeo

* Change sci format for scientific notation of sacp2: from 1e-5 to 10^{-5}
* Change font properties for station label to "monospace" for equal width
* Minor changes in program descriptions, example scripts 
* Further code development on github.com after this version.

aimbat-0.1.1
------------
Sep 27, 2012:
Main contributor: xlougeo

* Change setup.py and package directory: modules --> src/pysmo/aimbat. 
* AIMBAT becomes a part of pysmo (https://github.com/pysmo/aimbat). 
* Python usage: import aimbat --> from pysmo import aimbat
* Minor changes in help messages for scripts using the OptionParser module.
* Adjust figsize-related function of ttpick.py to support backends other than Tk.


aimbat-0.1
----------
Sep 19, 2012:
First release on Northwestern website.
Main contributor: xlougeo