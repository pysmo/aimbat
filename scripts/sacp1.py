#!/usr/bin/env python
#------------------------------------------------
# Filename: sacp1.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009-2012 Xiaoting Lou
#------------------------------------------------
"""
Python script fo SAC p1 style of plotting.

:copyright:
	Xiaoting Lou

:license:
	GNU General Public License, Version 3 (GPLv3) 
	http://www.gnu.org/licenses/gpl.html
""" 

from matplotlib.pyplot import show
from pysmo.aimbat.plotphase import getDataOpts, getAxes, sacp1

gsac, opts = getDataOpts()
axss = getAxes(opts)
ssg = sacp1(gsac.saclist, opts, axss)

show()


