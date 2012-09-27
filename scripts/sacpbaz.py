#!/usr/bin/env python
#------------------------------------------------
# Filename: sacpbaz.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009-2012 Xiaoting Lou
#------------------------------------------------
"""
Python script fo SAC plotting along backazimuth.

:copyright:
	Xiaoting Lou

:license:
	GNU General Public License, Version 3 (GPLv3) 
	http://www.gnu.org/licenses/gpl.html
""" 

from matplotlib.pyplot import show
from pysmo.aimbat.plotphase import getDataOpts, getAxes, sacpbaz

gsac, opts = getDataOpts()
axss = getAxes(opts)
ssg = sacpbaz(gsac.saclist, opts, axss)

show()
