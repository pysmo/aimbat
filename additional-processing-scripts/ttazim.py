#!/usr/bin/env python
"""
Divide events by (back) azimuth

xlou since 06/10/2010
"""

from pylab import *
import os, sys, glob
from optparse import OptionParser
from ttcommon import readPickle, writePickle, readStation, saveStation
from deltaz import deltaz, azdelt



if __name__ == '__main__':	

	teqs = 'ref.teqs'

	# baz range and map/station center
	#azrange = [15, 105, 210, 285]
	azrange = [10, 100, 200, 280]
	lat0, lon0 = 40, -110

	evdict = readStation(teqs)

	naz = len(azrange)
	alist = [ {} for i in range(naz) ]

	for ev in sorted(evdict):
		elat, elon, edep = evdict[ev][6:9]
		delt, azim = deltaz(lat0, lon0, elat, elon)
		if azim < 0: azim += 360
		ai = searchsorted(azrange, azim) - 1
		# -1 puts azim < arange[0] to the lst group
		alist[ai][ev] = [azim, delt, edep]

	for ai in range(naz):
		ofile = 'evaz{:d}'.format(ai)
		saveStation(alist[ai], ofile)

