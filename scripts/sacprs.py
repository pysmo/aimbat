#!/usr/bin/env python
#------------------------------------------------
# Filename: sacprs.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009-2012 Xiaoting Lou
#------------------------------------------------
"""
Python script fo SAC PRS style of plotting: record section.

:copyright:
	Xiaoting Lou

:license:
	GNU General Public License, Version 3 (GPLv3) 
	http://www.gnu.org/licenses/gpl.html
""" 

from matplotlib.pyplot import show
from pysmo.aimbat.plotphase import getDataOpts, getAxes, sacprs

gsac, opts = getDataOpts()
axss = getAxes(opts)
ssg = sacprs(gsac.saclist, opts, axss)

show()

