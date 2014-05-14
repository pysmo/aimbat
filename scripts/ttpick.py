#!/usr/bin/env python
#------------------------------------------------
# Filename: ttpick.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009-2012 Xiaoting Lou
#------------------------------------------------
"""
Python script to run the graphic user interface of AIMBAT for travel time picking and quality control.


:copyright:
	Xiaoting Lou

:license:
	GNU General Public License, Version 3 (GPLv3) 
	http://www.gnu.org/licenses/gpl.html
""" 

from matplotlib.pyplot import *
from pysmo.aimbat.qualctrl import getDataOpts, getAxes, PickPhaseMenuMore

# def getAxes(opts):
# 	""" Get axes for plotting """
# 	fig = figure(figsize=(13.6, 12.7))
# 	backend = get_backend().lower()
# 	if backend == 'tkagg':
# 		get_current_fig_manager().window.wm_geometry("1100x1050+700+0")
# 	rcParams['legend.fontsize'] = 10
# 	rectseis = [0.12, 0.04, 0.66, 0.82]
# 	rectfstk = [0.12, 0.89, 0.66, 0.08]
# 	xx = 0.06
# 	yy = 0.04
# 	xm = 0.02
# 	dy = 0.05
# 	y2 = rectfstk[1] + rectfstk[3] - yy
# 	yccim = y2 
# 	ysync = y2 - dy*1
# 	yccff = y2 - dy*2
# 	ymccc = y2 - dy*3
# 	y1 = ymccc - 1.5*dy
# 	yprev = y1 - dy*0
# 	ynext = y1 - dy*1
# 	ysave = y1 - dy*2
# 	yquit = y1 - dy*3
# 	ysac2 = yquit - dy*1.5

# 	rectprev = [xm, yprev, xx, yy]
# 	rectnext = [xm, ynext, xx, yy]
# 	rectsave = [xm, ysave, xx, yy]
# 	rectquit = [xm, yquit, xx, yy]
# 	rectccim = [xm, yccim, xx, yy]
# 	rectsync = [xm, ysync, xx, yy]
# 	rectccff = [xm, yccff, xx, yy]
# 	rectmccc = [xm, ymccc, xx, yy]
# 	rectsac2 = [xm, ysac2, xx, yy]

# 	axs = {}
# 	axs['Seis'] = fig.add_axes(rectseis)
# 	axs['Fstk'] = fig.add_axes(rectfstk, sharex=axs['Seis'])
# 	axs['Prev'] = fig.add_axes(rectprev)
# 	axs['Next'] = fig.add_axes(rectnext)
# 	axs['Save'] = fig.add_axes(rectsave)
# 	axs['Quit'] = fig.add_axes(rectquit)
# 	axs['CCIM'] = fig.add_axes(rectccim)
# 	axs['Sync'] = fig.add_axes(rectsync)
# 	axs['CCFF'] = fig.add_axes(rectccff)
# 	axs['MCCC'] = fig.add_axes(rectmccc)
# 	axs['SAC2'] = fig.add_axes(rectsac2)

# 	return axs


def main():
	gsac, opts = getDataOpts()
	axs = getAxes(opts)
	ppmm = PickPhaseMenuMore(gsac, opts, axs)
	fmt = 'png'
	fmt = 'pdf'
	if opts.savefig:
		if opts.pklfile is None:
			fignm = 'ttpick.' + fmt
		else:
			fignm = opts.pklfile + '.' + fmt
		savefig(fignm, format=fmt)
	else:
		show()

if __name__ == "__main__":
	main()

