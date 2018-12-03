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

setup(
    name='pysmo.aimbat',
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
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
    platforms=['Mac OS X', 'Linux/Unix', 'Windows'],
    install_requires=[i.strip() for i in open("requirements.txt").readlines()],
    entry_points={
        'console_scripts': [
            'aimbat-mccc=pysmo.aimbat.algmccc:main',
            'aimbat-iccs=pysmo.aimbat.algiccs:main',
            'aimbat-sac2pkl=pysmo.aimbat.sacpickle:main',
            'aimbat-sacp1=pysmo.aimbat.plotphase:sacp1_standalone',
            'aimbat-sacp2=pysmo.aimbat.plotphase:sacp2_standalone',
            'aimbat-sacpaz=pysmo.aimbat.plotphase:sacpaz_standalone',
            'aimbat-sacpbaz=pysmo.aimbat.plotphase:sacpbaz_standalone',
            'aimbat-sacplot=pysmo.aimbat.plotphase:sacplot_standalone',
            'aimbat-sacprs=pysmo.aimbat.plotphase:sacprs_standalone',
            'aimbat-sacppk=pysmo.aimbat.pickphase:sacppk_standalone',
            'aimbat-ttpick=pysmo.aimbat.qualctrl:main',
            'aimbat-qtpick=pysmo.aimbat.ttgui:main',
        ]
    },
)
