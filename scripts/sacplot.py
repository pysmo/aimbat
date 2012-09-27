#!/usr/bin/env python
#------------------------------------------------
# Filename: sacplot.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009-2012 Xiaoting Lou
#------------------------------------------------
"""
Python script fo SAC plotting (p1, p2, prs, paz, pbaz).

:copyright:
	Xiaoting Lou

:license:
	GNU General Public License, Version 3 (GPLv3) 
	http://www.gnu.org/licenses/gpl.html
""" 

from matplotlib.pyplot import show
from pysmo.aimbat.plotphase import getDataOpts, getAxes, SingleSeisGather

gsac, opts = getDataOpts()
axss = getAxes(opts)
ssg = SingleSeisGather(gsac.saclist, opts, axss)

show()


