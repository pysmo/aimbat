.. image:: https://travis-ci.org/pysmo/aimbat.svg?branch=master
      :target: https://travis-ci.org/pysmo/aimbat

======
AIMBAT
======

Overview
--------
AIMBAT (Automated and Interactive Measurement of Body wave Arrival Times) is an open-source software package for efficiently measuring teleseismic body wave arrival times for large seismic arrays [LouVanDerLeeLloyd2013]_. It is based on a widely used method called MCCC (Multi-Channel Cross-Correlation) [VanDecarCrosson1990]_. The package is automated in the sense of initially aligning seismograms for MCCC, which is achieved by an ICCS (Iterative Cross Correlation and Stack) algorithm. Meanwhile, a GUI (graphical user interface) is built to perform seismogram quality control interactively. Therefore, user processing time is reduced while valuable input from a user's expertise is retained. As a byproduct, SAC [GoldsteinDodge2003]_ plotting and phase picking functionalities are replicated and enhanced.

Modules and scripts included in the AIMBAT package were developed using `Python <http://www.python.org/>`_ and its open-source modules on the Mac OS X platform since 2009. The original MCCC [VanDecarCrosson1990]_ code was transcribed into Python. The GUI of AIMBAT was inspired and initiated at the `2009 EarthScope USArray Data Processing and Analysis Short Course <http://www.iris.edu/hq/es_course/content/2009.html>`_. AIMBAT runs on Mac OS X, Linux/Unix and Windows thanks to the platform-independent feature of Python. It has been tested on Mac OS 10.6.8 and 10.7, and Fedora 29.

For more information visit the `project website <http://www.earth.northwestern.edu/~xlou/aimbat.html>`_ or the `Pysmo repository <https://github.com/pysmo>`_.

Documentation
-------------
For detailed installation and usage instructions see: https://aimbat.readthedocs.org.

Requirements
------------

* Python version 3.6 or higher
* Fortran (optional, but highly recommended for better performance)

Installation
------------

::
   
   $ pip install pysmo.aimbat


Citation
--------

AIMBAT: A Python/Matplotlib Tool for Measuring Teleseismic Arrival Times. Xiaoting Lou, Suzan van der Lee, and Simon Lloyd (2013), Seismol. Res. Lett., 84(1), 85-93, doi:10.1785/0220120033.

* :download:`Seismological Research Letters Paper <Lou_etal_2013_SRL_AIMBAT.pdf>`

.. _authors-contacts:

Authors' Contacts
-----------------


* `Xiaoting Lou <http://geophysics.earth.northwestern.edu/people/xlou/aimbat.html>`_ Email: xlou at u.northwestern.edu

* `Suzan van der Lee <http://geophysics.earth.northwestern.edu/seismology/suzan/>`_ Email: suzan at northwestern.edu

* `Simon Lloyd <https://www.slloyd.net/>`_ Email: simon at slloyd.net

Contributors
------------
* Lay Kuan Loh

Licence
-------
The AIMBAT software package is distributed under the `GNU General Public License Version 3 (GPLv3) <http://www.gnu.org/licenses/gpl.html>`_ as published by the Free Software Foundation.

Copyright (c) 2009-2019 Xiaoting Lou
