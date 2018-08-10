#!/usr/bin/env python
""" 
AIMBAT: Automated and Interactive Measurement of Body-wave Arrival Times.

AIMBAT is an open-source software package for efficiently measuring teleseismic 
body wave arrival times for large seismic arrays (Lou et al., 2013). It is 
based on a widely used method called MCCC (multi-channel cross-correlation) 
developed by VanDecar and Crosson (1990). The package is automated in the 
sense of initially aligning seismograms for MCCC which is achieved by an 
ICCS (iterative cross-correlation and stack) algorithm. Meanwhile, a 
graphical user interface is built to perform seismogram quality control 
interactively. Therefore, user processing time is reduced while valuable 
input from a user\'s expertise is retained. As a byproduct, SAC (Goldstein 
et al., 2003) plotting and phase picking functionalities are replicated 
and enhanced.
"""

from setuptools import find_packages
from numpy.distutils.core import setup, Extension

doclines = __doc__.split("\n")
version = open('Version.txt').read().split()[0]

setup(
    name='pysmo.aimbat',
    version=version,
    description=doclines[0],
    long_description="\n".join(doclines[2:]),
    author='Xiaoting Lou',
    author_email='xlou@u.northwestern.edu',
    license='GNU General Public License, Version 3 (GPLv3)',
    url='http://www.earth.northwestern.edu/~xlou/aimbat.html',
    package_data={'pysmo.aimbat': ['ttdefaults.conf', 'Readme.txt', 'Version.txt', 'License.txt', 'Changelog.txt']},
    package_dir={'':'src' },
    packages=find_packages(where='./src'),
    ext_package='pysmo.aimbat',
    ext_modules=[Extension('xcorrf90', ['src/pysmo/aimbat/xcorr.f90'])],
    zip_safe=False,
    platforms=['Mac OS X', 'Linux/Unix', 'Windows']
)
