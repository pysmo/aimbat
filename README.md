package AIMBAT 
==============
 
Copyright
---------
GNU General Public License, Version 3 (GPLv3) 
http://www.gnu.org/licenses/gpl.html

Copyright (c) 2009-2012 Xiaoting Lou


Overview
--------
AIMBAT (Automated and Interactive Measurement of Body-wave Arrival Times) 
is an open-source software package for efficiently measuring teleseismic 
body wave arrival times for large seismic arrays (Lou et al., 2013). It is 
based on a widely used method called MCCC (multi-channel cross-correlation) 
developed by VanDecar and Crosson (1990). The package is automated in the 
sense of initially aligning seismograms for MCCC which is achieved by an 
ICCS (iterative cross-correlation and stack) algorithm. Meanwhile, a 
graphical user interface is built to perform seismogram quality control 
interactively. Therefore, user processing time is reduced while valuable 
input from a user's expertise is retained. As a byproduct, SAC (Goldstein 
et al., 2003) plotting and phase picking functionalities are replicated 
and enhanced.

For more informaton visit 
http://www.earth.northwestern.edu/~xlou/aimbat.html
https://github.com/pysmo/aimbat

Documentation
-------------
* http://aimbat.readthedocs.org/en/latest/index.html

Dependencies
------------
* python
* numpy
* scipy
* matplotlib
* pysmo.sac
* Tkinter

Installation
------------
* Install the dependent packages
* Download the latest release of aimbat, e.g. pysmo-aimbat-0.1.1.tar.gz, and decompress:
	tar zxvf pysmo-aimbat-0.1.1.tar.gz
* In the package main directory pysmo-aimbat-0.1.1, install it to the python <site-packages> directory:
	python setup.py build --fcompiler=gfortran
	python setup.py install
* Add the directory pysmo-aimbat-0.1.1/scripts to environment variable $PATH

Filtering Data
--------------
* `evsacbp/sh <name of file>.sac f0 f1`, where `f0` is the lower frequency. and `f1` is the higher frequency. in hertz

Building
--------

Each time you make changes to any of the files in this repository, run

	sudo python setup.py build --fcompiler=gfortran
	sudo python setup.py install
	
To build again to allow the changes to take place.


