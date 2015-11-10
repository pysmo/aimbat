#!/usr/bin/env python
#------------------------------------------------
# Filename: sacppk.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009-2012 Xiaoting Lou
#------------------------------------------------
"""
Python script fo SAC phase picking (ppk).

:copyright:
	Xiaoting Lou

:license:
	GNU General Public License, Version 3 (GPLv3) 
	http://www.gnu.org/licenses/gpl.html
""" 

from matplotlib.pyplot import *
from pysmo.aimbat.pickphase import getDataOpts, PickPhaseMenu, getAxes

#def getAxes(opts):
#	'Get axes for plotting'
#	fig = figure(figsize=(13, 11))
#	rcParams['legend.fontsize'] = 11
#	if opts.labelqual:
#		rectseis = [0.1, 0.06, 0.65, 0.85]
#	else:
#		rectseis = [0.1, 0.06, 0.75, 0.85]
#	axpp = fig.add_axes(rectseis)
#	axs = {}
#	axs['Seis'] = axpp
#	dx = 0.07
#	x0 = rectseis[0] + rectseis[2] + 0.01
#	xf = x0 - dx*1
#	xq = x0 - dx*2
#	xs = x0 - dx*3
#	xn = x0 - dx*4
#	xz = x0 - dx*5
#	xp = x0 - dx*6
#	rectfron = [xf, 0.93, 0.06, 0.04]
#	rectprev = [xp, 0.93, 0.06, 0.04]
#	rectnext = [xn, 0.93, 0.06, 0.04]
#	rectzoba = [xz, 0.93, 0.06, 0.04]
#	rectsave = [xs, 0.93, 0.06, 0.04]
#	rectquit = [xq, 0.93, 0.06, 0.04]
#	axs['Fron'] = fig.add_axes(rectfron)
#	axs['Prev'] = fig.add_axes(rectprev)
#	axs['Next'] = fig.add_axes(rectnext)
#	axs['Zoba'] = fig.add_axes(rectzoba)
#	axs['Save'] = fig.add_axes(rectsave)
#	axs['Quit'] = fig.add_axes(rectquit)
#	return axs


if __name__ == "__main__":
	gsac, opts = getDataOpts()
	axs = getAxes(opts)
	ppm = PickPhaseMenu(gsac, opts, axs)

	show()

