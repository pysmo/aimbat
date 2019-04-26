Changelog
=========

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

* Use new pysmo.core.sac.SacIO (pysmo-pysmo-v0.7.0) instead of pysmo.sac.sacio.SacFile
* New setup.py:

   * Wrap all scripts into a callable function and add them to entry_point, e.g., aimbat-ttpick is automatically generated in your bin folder.
   * Use git commit/tag to determine version automatically.

* SAC plotting and aimbat-ttpick are still using Matplotlib GUI.
* New GUI (aimbat-qtpick) using pyqtgraph for fast plotting. Similar user interactions as v0.3:

   *  Key pressed event handler in pyqtgraph is redefined 
   * Use mouse to change time window and press key 'w' to set <-- work on stack only
   * Press key 't[0-9]' to set time picks like SAC PPK        <-- work on both stack and traces
   * Mouse click on waveform to change trace selection status <-- work on trace only

* Better separation between data and plot.
* Filter and sort are both in the main GUI controlled by a parameter tree.


aimbat-v0.3-alpha1
------------------
June 3, 2018:

* Upgrade to python3 (May not back-compatible with python2). No change in functionalities from v0.2.
* Include sacio in the same aimbat source package.


aimbat-v0.2
-----------
Main contributor: lkloh. Last update on Aug 23, 2016

May 13, 2014:

* Added a warning button if you hit ICCS-A or ICCS-B button, to make sure do did not hit it by accident. 
* Hitting one of those buttons will undo all the work you did in manually picking arrival times.

May 14, 2014:

* Added a button to allow you to jump to the front page. Note that hitting MCCC again will do just that. 
* Added a summary of the event at the top right hand corner. 
* Parameters:

   * Magnitude
   * Location
   * Depth

May 17, 2014:

* Added a GUI to allow sorting of the seismograms according to header, time difference, file name, ...
* Added a button to return to original screen after you zoom in/out


aimbat-0.1.2
------------
Dec 19, 2012:

* Change sci format for scientific notation of sacp2: from 1e-5 to 10^{-5}
* Change font properties for station label to "monospace" for equal width
* Minor changes in program descriptions, example scripts 


aimbat-0.1.1
------------
Sep 27, 2012:

* Change setup.py and package directory: modules --> src/pysmo/aimbat. 
* AIMBAT becomes a part of pysmo (https://github.com/pysmo/aimbat). 
* Python usage: import aimbat --> from pysmo import aimbat
* Minor changes in help messages for scripts using the OptionParser module.
* Adjust figsize-related function of ttpick.py to support backends other than Tk.


aimbat-0.1
----------
First release on Sep 19, 2012
