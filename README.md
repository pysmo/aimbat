AIMBAT 
======
 
Copyright
---------
[GNU General Public License](http://www.gnu.org/licenses/gpl.html), Version 3 (GPLv3) 

Copyright (c) 2009-2012 Xiaoting Lou


Overview
--------
AIMBAT (Automated and Interactive Measurement of Body-wave Arrival Times) is an open-source software package for efficiently measuring teleseismic body wave arrival times for large seismic arrays [Lou et al., 2013](http://www.earth.northwestern.edu/~xlou/aimbat_files/Lou_etal_2013_SRL_AIMBAT.pdf). It is 
based on a widely used method called MCCC (multi-channel cross-correlation) developed by [VanDecar and Crosson (1990)](http://bssa.geoscienceworld.org/content/80/1/150.abstract). The package is automated in the sense of initially aligning seismograms for MCCC which is achieved by an ICCS (iterative cross-correlation and stack) algorithm. Meanwhile, a graphical user interface is built to perform seismogram quality control interactively. Therefore, user processing time is reduced while valuable input from a user's expertise is retained. As a byproduct, SAC [Goldstein et al., 2003](http://oasis.crs.inogs.it/static/doc/GoldsteinEtAl_2003_iaspei_sac.pdf) plotting and phase picking functionalities are replicated and enhanced.

For more informaton visit the [project website](http://www.earth.northwestern.edu/~xlou/aimbat.html) or the [Pysmo repository](https://github.com/pysmo).

Documentation
-------------
Read about the features and their usage in the latest version of AIMBAT on github [here](http://aimbat.readthedocs.org/en/latest/index.html).

Dependencies
------------
* [Python](http://www.python.org/)
* [Numpy](http://www.numpy.org/)
* [Scipy](http://www.scipy.org/)
* [Matplotlib](http://matplotlib.org/)
* [pysmo.sac](https://github.com/pysmo/sac)
* [Tkinter](https://wiki.python.org/moin/TkInter)
* [Basemap](http://matplotlib.org/basemap/index.html)
* [GFortran](https://gcc.gnu.org/wiki/GFortranBinaries)

Filtering Data
--------------
	evsacbp.sh <name of file>.sac f0 f1
where `f0` is the lower frequency. and `f1` is the higher frequency, in hertz.

Building
--------

Each time you make changes to any of the files in this repository, run

	sudo python setup.py build --fcompiler=gfortran
	sudo python setup.py install
	
To build again to allow the changes to take place.

Running Unit Tests
------------------
[Unit Tests](https://docs.python.org/2/library/unittest.html#) are used to ensure robustness of the program. They should be run each time you make a significant change to AIMBAT, to ensure you did not accidentally break some functionality. Inside the repository ``aimbat/src/pysmo/unit_tests``, run

	python run_unit_tests.py

The modification by Xin Song
------------------
* Colour alarm for traces with very large traveltimes

When the measured relative traveltime after MCCC exceeds the traveltime thresholds, the corresponding traces will show different colours. This feature is to avoid some high risky traces that might have very large traveltimes. It can have 3 traveltime thresholds maximum.

This feature is set in the `ttconfig.py` in either `aimbat/src/pysmo/aimbat/` or either local directory

For example in `ttconfig.py`:
```
thresholds = 2 2.5 3
colorthresholds = green magenta red
```
It means the colour of trace will become green, magenta, or red if the traveltime of this trace is over 2s, 2.5s, or 3s after MCCC.

* Perform the MCCC without changing the polarity of traces by setting `xcorr_func` in the `ttconfig.py`:

`xcorr_func = xcorr_full_polarity`


