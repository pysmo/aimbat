.. image:: NU_Logo_purple.jpg

============
Introduction
============

About AIMBAT
------------

AIMBAT (Automated and Interactive Measurement of Body wave Arrival Times) is an open-source software package for efficiently measuring teleseismic body wave arrival times for large seismic arrays [LouVanDerLee2013]_. It is based on a widely used method called MCCC (Multi-Channel Cross-Correlation) [VanDecarCrosson1990]_. The package is automated in the sense of initially aligning seismograms for MCCC, which is achieved by an ICCS (Iterative Cross Correlation and Stack) algorithm. Meanwhile, a GUI (graphical user interface) is built to perform seismogram quality control interactively. Therefore, user processing time is reduced while valuable input from a user's expertise is retained. As a byproduct, SAC [GoldsteinDodge2003]_ plotting and phase picking functionalities are replicated and enhanced.

Modules and scripts included in the AIMBAT package were developed using `Python programming language <http://www.python.org/>`_ and its open-source modules on the Mac OS X platform since 2009. The original MCCC [VanDecarCrosson1990]_ code was transcribed into Python. The GUI of AIMBAT was inspired and initiated at the `2009 EarthScope USArray Data Processing and Analysis Short Course <http://www.iris.edu/hq/es_course/content/2009.html>`_. AIMBAT runs on Mac OS X, Linux/Unix and Windows thanks to the platform-independent feature of Python. It has been tested on Mac OS 10.6.8 and 10.7, and Fedora 16.

The AIMBAT software package is distributed under the `GNU General Public License Version 3 (GPLv3) <http://www.gnu.org/licenses/gpl.html>`_ as published by the Free Software Foundation.

TEST EDIT

Associated Documents
--------------------

* :download:`Seismological Research Letters Paper <Lou_etal_2013_SRL_AIMBAT.pdf>`
* :download:`PDF Version of Manual <../build/latex/AIMBAT.pdf>`. Automatically generated from these online docs; please excuse minor issues that may arise from automated conversion.


.. _authors-contacts:

Authors' Contacts
-----------------

* `Lay Kuan Loh <http://lkloh2410.wordpress.com/>`_

  Email: lloh at ece.cmu.edu

* `Xiaoting Lou <http://www.earth.northwestern.edu/~xlou/Welcome.html>`_

  Email: xlou at u.northwestern.edu

* `Suzan van der Lee <http://www.earth.northwestern.edu/research/suzan/>`_

  Email: suzan at earth.northwestern.edu
